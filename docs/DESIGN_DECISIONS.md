# Design Decisions — AI Systems Engineering Assistant (NASA SE Edition)

> Registro das decisões de design e modificações realizadas durante a implementação, em especial da Fase 1 (Ingestão) e validação do Checkpoint 1.

---

## 1. Processamento do PDF em lotes de páginas

### Problema

Ao converter o NASA SE Handbook (297 páginas) com **Docling** em uma única chamada, o estágio **preprocess** do pipeline gerava **`std::bad_alloc`** (falha de alocação de memória em C++). O erro surgia a partir de certas páginas (ex.: 16 em diante), indicando esgotamento de RAM ao processar o documento inteiro.

### Decisão

- Processar o PDF em **lotes de páginas** usando o parâmetro **`page_range`** do `DocumentConverter.convert()`.
- Tamanho do lote configurável em **`configs/default.yaml`** via **`ingestion.pdf_page_batch_size`**.
- Cada lote é convertido, o Markdown é acumulado em memória e os lotes são concatenados ao final com separador `---`.

### Parâmetros e evolução

| Valor inicial | Valor final | Motivo |
|---------------|-------------|--------|
| 15 páginas    | 5 páginas   | Com 15, `bad_alloc` continuava na última página de cada lote. |
| 5 páginas     | 3 páginas   | Para máxima segurança em máquinas com pouca RAM; ingestão concluída sem erros. |

**Configuração atual:** `pdf_page_batch_size: 3` (recomendado manter em 3; aumentar apenas se houver RAM suficiente).

---

## 2. API do Docling: page_range 1-based e inclusivo

### Problema

Uso de **`page_range=(0, 15)`** (índices 0-based, estilo Python) gerava erro de validação do Docling:

```text
Invalid page range: start must be ≥ 1 and end must be ≥ start.
```

### Decisão

- **Docling usa página 1-based e intervalo inclusivo.**
- Formato correto: `page_range=(start, end)` com `start >= 1` e `end >= start`, onde `(1, 15)` = páginas 1 a 15.
- Implementação: `start = 1`; a cada lote `end = min(start + pdf_page_batch_size - 1, num_pages)`; próximo lote `start = end + 1`.

---

## 3. Contagem de páginas com pypdf

### Decisão

- Usar **pypdf** (`PdfReader`) apenas para obter o **número de páginas** do PDF, sem carregar o conteúdo.
- Isso permite saber o total de páginas e calcular os intervalos dos lotes antes de chamar o Docling.
- Dependência registrada em **`requirements-phase1.txt`** (`pypdf>=4.0.0`).
- Se a contagem falhar (`num_pages == 0`), o script faz fallback para processar o documento inteiro (com risco de `bad_alloc` em PDFs grandes).

---

## 4. Liberação de memória entre lotes (gc)

### Decisão

- Chamar **`gc.collect()`** no bloco **`finally`** após cada lote de conversão Docling.
- Objetivo: liberar memória entre lotes e reduzir acúmulo que poderia levar a `bad_alloc` nos lotes seguintes.
- Não se cria um novo `DocumentConverter` a cada lote (evita recarregar modelos e aumentar pico de memória); usa-se uma única instância por execução.

---

## 5. Import lazy do Docling

### Decisão

- O **import do Docling** (`DocumentConverter`) é feito **dentro** da função `convert_pdf_to_markdown()`, não no topo do módulo.
- Motivo: permitir que o restante do pacote (config_loader, hierarchy_aware_chunker, testes) seja importado e usado **sem** ter o Docling instalado (ex.: só chunker, só validação de Checkpoint 1 com chunks já gerados).

---

## 6. Validação do Checkpoint 1 — Critério de “tabela truncada”

### Problema

O teste **`test_no_truncated_tables`** exigia que **todas** as linhas de uma tabela Markdown tivessem o **mesmo número de colunas**. No Handbook real, tabelas exportadas pelo Docling podem ter:

- Linhas de separador (`|---|---|`) com contagem diferente de células.
- Células vazias ou mescladas que alteram o resultado de `split("|")`.
- Variação legítima de colunas por linha (conteúdo real do PDF).

Isso gerava **falsos positivos** (“tabela truncada”) e fazia o Checkpoint 1 falhar mesmo com ingestão correta.

### Decisão

- **Relaxar o critério** de truncagem:
  - **Antes:** falhar se qualquer linha tiver número de colunas diferente do header.
  - **Depois:** falhar **somente** quando o header tiver **≥ 4 colunas** e **todas** as linhas de dados tiverem **≤ 2 colunas** (tabela sem dados = possível corte grosseiro).
- Assim, variações normais de colunas (merged cells, separadores, etc.) não invalidam o checkpoint; apenas tabelas claramente sem dados são consideradas truncadas.

**Arquivo:** `tests/test_checkpoint1.py`, função `test_no_truncated_tables()`.

---

## 7. Estrutura de diretórios e configuração central

### Decisão

- **Configuração central** em **`configs/default.yaml`** (paths, ingestion, rag, dataset_gen, finetuning).
- Paths definidos como relativos à raiz do projeto e convertidos para **absolutos** no carregamento (`config_loader.py`), com base na localização do próprio `config_loader` (raiz = `src/ingestion/../../`).
- Evita “magic numbers” no código e permite reexperimentar parâmetros (chunk_size, top_k, pdf_page_batch_size, etc.) sem alterar código.

---

## 8. Formato de saída dos chunks (JSONL)

### Decisão

- Chunks salvos em **JSONL**: uma linha por chunk, cada registro com **`text`** e **`metadata`**.
- Metadados incluem: `section_title`, `section_level`, `appendix` (detectado por regex no título), `source_file`, **`page`** e **`paragraph`** (quando disponíveis; ver decisão 18).
- Nome do arquivo: `{stem_do_markdown}_chunks.jsonl` em `data/chunks/`.

---

## 9. Pivot Fase 2: RAG Reranked → GraphRAG

**Decisão:** A Fase 2 foi redirecionada de **RAG com reranking** (vector store + cross-encoder) para um **grafo de conhecimento**. A Fase 1 permanece **as is**; os chunks em `data/chunks/*.jsonl` são a entrada do pipeline.

**Motivação:** Grafo permite modelar sequência e relações entre trechos; busca full-text no grafo alinha ao domínio NASA SE. Plano: [PLANO_IMPLEMENTACAO_FASE2_GRAPHRAG.md](../PLANO_IMPLEMENTACAO_FASE2_GRAPHRAG.md).

---

## 9b. Pivot Fase 2: Microsoft GraphRAG → Neo4j

**Decisão:** A implementação da Fase 2 usa **Neo4j** como armazenamento do grafo em vez do **Microsoft GraphRAG** (CLI + Parquet).

**Motivação:**
- **Neo4j não requer API externa** (OpenAI/Azure): apenas conexão ao banco (bolt). Sem custo de LLM na indexação.
- Chunks viram nós `Chunk` com propriedades (text, section_title, section_level, etc.); relação `NEXT` entre consecutivos; índice full-text em `Chunk.text` para busca.
- Query = full-text no Neo4j → retorno de trechos (contexto); LLM + prompt NASA pode ser usado em pipeline externo (opcional).
- Config em `configs/default.yaml` (seção `neo4j`: uri, user, password/database); senha via `NEO4J_PASSWORD` recomendado.

---

## 10. Escolha do Microsoft GraphRAG (Opção A)

**Decisão:** Usar o **Microsoft GraphRAG** (`pip install graphrag`) como pilha de indexação e query na Fase 2, em vez de um grafo custom (LlamaIndex/LangChain).

**Motivação:**
- Pipeline completo: `graphrag init` → texto em `input/` → `graphrag index` → Parquet em `output/` → `graphrag query` com `--method global` ou `--method local`.
- Bem documentado; suporte a OpenAI e Azure OpenAI; CLI com `--root` para apontar o workspace.
- Permite validar o valor de GraphRAG no domínio NASA SE com menor esforço; depois é possível evoluir para híbrido ou custom reutilizando os mesmos chunks.

**Contrapartida:** Indexação consome chamadas LLM (extração de entidades/relações, resumos); custo e tempo maiores para documentos longos. Configuração de modelos em `settings.yaml` e `.env` no workspace.

---

## 11. Workspace GraphRAG isolado

**Decisão:** Manter um **workspace dedicado** (ex.: `graphrag_workspace/`) na raiz do projeto, contendo `input/`, `output/`, `settings.yaml` e `.env`. O comando `graphrag` é invocado com `--root <workspace_dir>` para que leia/escreva nesse diretório.

**Motivação:**
- Separa dados do GraphRAG dos dados da Fase 1 (`data/chunks`, `data/markdown`).
- `.env` com chaves de API fica apenas no workspace e pode ser ignorado pelo git.
- Paths do workspace são configuráveis em `configs/default.yaml` (seção `graphrag.workspace_dir`, `input_dir`, `output_dir`); resolvidos para absolutos a partir da raiz do projeto.

---

## 12. Preparação de input: um arquivo por chunk vs arquivo único

**Decisão:** Suportar dois modos configuráveis via `graphrag.input_mode`:
- **`one_file_per_chunk`:** cada chunk vira um arquivo `.txt` em `input/` (ex.: `chunk_001.txt`, `chunk_002.txt`), com conteúdo = `text` do chunk; opcionalmente uma linha de metadados no topo (section_title, section_level) para o LLM “ver” a estrutura.
- **`single_file`:** um único arquivo (ex.: `handbook_full.txt`) com todos os chunks concatenados, separados por delimitador explícito (ex.: `\n--- CHUNK ---\n`).

**Motivação:**
- Um arquivo por chunk preserva fronteiras semânticas e pode melhorar extração de entidades por documento.
- Arquivo único reduz número de arquivos e pode simplificar o pipeline; útil para testes ou quando o GraphRAG tratar o documento como um todo.
- Nomes de arquivo estáveis (ex.: zero-padded `chunk_001.txt`) garantem reprodutibilidade.

---

## 13. Método de query: global vs local

**Decisão:** O motor de query deve suportar **global** (resumos de comunidades) e **local** (entidades e relações). O método pode ser escolhido por chamada ou por config (`graphrag.default_query_method`: `global` | `local`). Opcionalmente `auto` (heurística por palavras-chave ou classificador) para escolher automaticamente.

**Motivação:**
- Perguntas amplas (“Quais são os principais processos de SE no Handbook?”) beneficiam da busca global.
- Perguntas focadas (“Qual a diferença entre Verificação e Validação?”) beneficiam da busca local.
- O Checkpoint 2 exige resposta correta para “Verificação vs Validação”, tipicamente atendida por busca local.

---

## 14. Prompt de sistema NASA

**Decisão:** O texto do **prompt de sistema NASA** (persona: responder apenas com base no contexto, “shall”, Verificação/Validação, citar seções) é mantido em arquivo dedicado (ex.: `configs/prompts_nasa_system.txt`) e injetado em **toda** resposta gerada pelo LLM no fluxo de query GraphRAG. Caminho configurável em `graphrag.system_prompt_path`.

**Motivação:**
- Alinhamento com o PROMPT_NASA_SE_AI_ASSISTANT.md (Seção 9); uma única fonte de verdade para o texto do prompt.
- Se a CLI do GraphRAG não permitir system prompt custom, a orquestração (ex.: `query_engine.py`) pode pós-processar: obter contexto do GraphRAG e chamar o LLM separadamente com o prompt NASA, garantindo FR-2.3.4.

---

## 15. Logging de queries e verificador de requisitos

**Decisão:**
- **Queries:** Para cada query, registrar em `log/` a pergunta, o método (global/local), timestamp ou run_id, e um identificador da resposta (hash ou primeiros caracteres) para reprodutibilidade e métricas.
- **Verificador de requisitos:** Um script dedicado (`scripts/run_phase2_requirements_verifier.py`) percorre todos os FR e NFR da Fase 2, verifica critérios de aceite (existência de arquivos, config, índice, resposta de referência, etc.) e gera relatório em `log/` (JSON + TXT) com status PASS/FAIL e métricas evidentes (ex.: número de arquivos em input, resultado do Checkpoint 2). Pré-condições não atendidas contam como FAIL.

**Motivação:**
- Rastreabilidade e auditoria; possibilidade de regressão e comparação entre runs.
- Garantir que a implementação cumpra todos os requisitos documentados em `docs/REQUIREMENTS_FASE2.md` com evidências objetivas.

---

## 16. Escolha de LLM para Fase 3 (PoC local com Ollama)

**Decisão:** Para a Fase 3 (geração de dataset sintético) será usado, em PoC, um LLM leve da família **Qwen 3.5 ~4B** rodando localmente via **Ollama** (backend de inferência), preferencialmente em formato **GGUF** (ex.: `unsloth/Qwen3.5-4B-GGUF`, em destaque na lista de modelos em tendência no Hugging Face — ver [Modelos em tendência](https://huggingface.co/models?p=1&sort=trending)).

**Motivação:**

- **Tamanho / custo:** ~4B parâmetros é pequeno o suficiente para rodar em GPU/CPU de desenvolvimento, mas grande o bastante para gerar instruções/respostas úteis e coerentes.
- **Qualidade / idioma:** Qwen 3.5 é instrução‑tunado, multilíngue e razoavelmente forte em raciocínio e escrita técnica, adequado para produzir texto em inglês e/ou português técnico de engenharia de sistemas.
- **Integração com Ollama:** modelos Qwen 3.x já são suportados ou facilmente importáveis em Ollama via GGUF, permitindo:
  - servidor local HTTP (`http://localhost:11434`) sem dependência de APIs externas,
  - controle total de parâmetros (temperature, top_p, num_ctx, etc.) por requisição.

**Arquitetura de inferência (Fase 3):**

- **Camada de geração:** função `call_llm(system_prompt, user_prompt, max_tokens)` em `src/dataset_gen/generator.py` será o ponto único de chamada ao LLM.
- **Backend:** `call_llm` faz requisições HTTP para o endpoint do Ollama (`/api/generate`), passando:
  - `model`: nome do modelo configurado (ex.: `qwen3.5-4b` ou equivalente no catálogo do Ollama),
  - `system`: prompt NASA (persona, restrição ao Handbook),
  - `prompt`: texto formatado com contexto + instrução de geração,
  - `options`: `{ "temperature": 0.3, "num_ctx": 8192, ... }`.
- **Config:** nome do modelo e parâmetros de inferência podem ser adicionados à seção `dataset_gen` no `configs/default.yaml` (futuro): `llm_model`, `temperature`, `max_new_tokens`, etc.

**Trade‑offs:**

- Para PoC, prioriza‑se rodar **tudo local** (sem custo de API), aceitando performance e qualidade moderadas.
- Caso a qualidade do dataset sintético com ~4B não seja suficiente, é possível:
  - subir temporariamente um modelo maior (ex.: Qwen 3.5 9B ou 14B),
  - ou usar um provedor externo (OpenAI, Azure) apenas para geração Fase 3, mantendo a mesma interface `call_llm`.

---

## 17. Estratégia de geração de dataset sintético (Fase 3)

**Decisão:** A Fase 3 foi implementada como um pipeline modular, separado em pacote `src/dataset_gen/`, com geração inicialmente em modo **stub** (sem LLM real), mas com todos os pontos de extensão e artefatos alinhados aos requisitos.

**Componentes principais:**

- `src/dataset_gen/schema.py`:
  - Define `DatasetExample` (FR-3.1.1), compatível com export JSONL e fácil uso em Fase 4 (fine‑tuning).
- `src/dataset_gen/sampler.py`:
  - Função `_load_all_chunks` lê `data/chunks/*.jsonl` (Fase 1).
  - `sample_contexts_by_section(num_contexts, seed, config_name)` agrupa por `section_title` e cria `ContextSpec` com texto, seção e ids de chunks; adiciona tags simples (`vv`, `requirements`) quando identifica termos relevantes.
- `src/dataset_gen/generator.py`:
  - Define `call_llm(...)` como ponto único de integração com o LLM (Ollama no PoC).
  - `generate_example_from_context(...)` hoje é um **stub** (retorna `None`), mas já recebe `ContextSpec`, `system_prompt` e limites de tokens – pronto para receber a chamada real ao LLM.
  - `generate_dataset(num_pairs, seed, config_name)` orquestra: lê config `dataset_gen`, carrega o prompt NASA de `neo4j.system_prompt_path`, amostra contextos e tenta gerar até `num_pairs` exemplos.
- `src/dataset_gen/postprocess.py`:
  - Implementa validações simples (`is_valid_example`, `filter_examples`): comprimentos mínimos, campos obrigatórios, presença de tags – base para NFR-3.2.x.
- `src/dataset_gen/export.py`:
  - Salva exemplos em `data/datasets/nasa_se_synthetic_train.jsonl` e `..._val.jsonl`, com split padrão 90/10 (FR-3.4.x).
- `scripts/run_dataset_gen.py`:
  - Pipeline CLI: lê config, roda geração, pós-processa, exporta dataset e grava métricas em `log/dataset_phase3_*.json`.

**Motivação:**

- Separar claramente **amostragem, geração, pós‑processo e export**:
  - facilita trocar o LLM ou ajustar heurísticas sem quebrar o restante,
  - permite rodar só partes do pipeline (ex.: apenas sampler + export de contextos).
- Começar com um **stub** evita dependência imediata de um LLM externo/local, mantendo testes e estrutura prontos. A ativação via Ollama será feita apenas em `call_llm`, sem tocar o resto do código.

**Impacto nos próximos passos:**

- Fase 4 pode consumir diretamente `data/datasets/*.jsonl` (carregando `DatasetExample` via `dataclasses` ou convertendo para `datasets.Dataset` do Hugging Face).
- Para subir a qualidade do dataset, basta:
  - implementar `call_llm` (Ollama + Qwen 3.5 4B),
  - enriquecer `generate_example_from_context` com prompts mais específicos (templates em um módulo futuro `prompt_templates.py`),
  - ajustar filtros em `postprocess.py`.

---

## 18. Propagação de página e parágrafo (FR-2.3.6)

### Problema

O FR-2.3.6 exige que a resposta do sistema mencione **página e parágrafo** de origem no PDF quando possível. Inicialmente os nós Chunk no Neo4j e os chunks JSONL da Fase 1 não tinham essas informações, então a resposta nunca as exibía.

### Decisão

- **Origem dos dados:** A página é inferida na **conversão PDF→Markdown** (Fase 1). Ao processar em lotes, o Docling recebe `page_range=(start, end)`; ao concatenar o Markdown de cada lote, inserimos um marcador HTML no texto: `<!-- page N -->` (onde N é a primeira página daquele lote). No fluxo sem lotes (documento inteiro), inserimos `<!-- page 1 -->` no início.
- **Chunker:** O `hierarchy_aware_chunker` reconhece o padrão `<!-- page N -->` ao dividir o Markdown em blocos. Cada bloco recebe o número da **última página** vista até aquele ponto. O **parágrafo** é o índice (1-based) do sub-bloco quando um bloco é subdividido por tamanho (ex.: 1 se o bloco coube em um chunk, 1/2/3 se foi dividido em três chunks).
- **JSONL:** Os metadados de cada chunk passam a incluir `page` (int) e `paragraph` (int). Valores 0 indicam ausência (documento convertido sem marcadores ou bloco sem página conhecida).
- **Neo4j:** Na ingestão (`neo4j_store.ingest_chunks`), os nós Chunk passam a ter propriedades **`page`** e **`paragraph`**, lidas dos metadados do JSONL. A query full-text já retorna `node.page` e `node.paragraph`; o `query_engine._format_hit` formata o cabeçalho de cada trecho como `[i] {section_title} (p.{page}, parágrafo {paragraph})` quando ambos são > 0.
- **Formato na resposta:** O usuário vê, por trecho, algo como “(p.42, parágrafo 2)”. Se `page` ou `paragraph` forem 0 ou ausentes, o cabeçalho não inclui essa parte (comportamento já implementado em `_format_hit`).

### Fluxo end-to-end

1. **Docling** (lotes): cada parte do MD é prefixada com `\n\n<!-- page {start} -->\n\n`.
2. **Chunker**: `_split_into_blocks` detecta o marcador e associa cada bloco a uma página; em `chunk_markdown_file`, cada chunk recebe `metadata["page"]` e `metadata["paragraph"]`.
3. **JSONL**: gravado com `page` e `paragraph` em cada linha.
4. **Neo4j ingest**: cria nós com `page` e `paragraph`.
5. **Query**: full-text devolve os campos; `_format_hit` exibe “(p.X, parágrafo Y)” quando disponível.

Para que as respostas passem a mostrar página/parágrafo, é necessário **re-executar** o pipeline a partir da conversão PDF→MD (ou pelo menos Markdown→chunks) e depois **re-ingestão** no Neo4j.

---

## 19. LLM para pré-processamento do contexto (resposta melhor, fonte intacta)

### Decisão

- O fluxo de resposta à pergunta do usuário deve usar um **LLM para pré-processar o contexto** recuperado (Neo4j), de modo a produzir uma **resposta mais clara, focada e legível** (resumo, reformulação, destaque do que é relevante à pergunta).
- **Restrição crítica:** a **informação de fonte** (seção, página, parágrafo — e, se aplicável, identificador do chunk) deve **permanecer intacta e não processada pelo LLM**. Ou seja: o modelo **não** deve gerar nem alterar referências de fonte; isso evita alucinações (citar página ou seção inexistentes). A aplicação é responsável por **anexar** ou **injetar** as referências exatas aos trechos, usando sempre os metadados retornados pelo retrieval.
- O **modelo de LLM** usado nesse passo deve ser **pequeno** (ex.: 4B–7B parâmetros), suficiente apenas para pré-processamento do texto (resumir, reformular), e pode rodar localmente (ex.: Ollama) para baixo custo e latência controlada.

### Abordagem de implementação sugerida

1. **Retrieval** continua como hoje: full-text no Neo4j retorna uma lista de **hits** com `text`, `section_title`, `page`, `paragraph` (e `id` do chunk).
2. **Entrada ao LLM:** a aplicação envia ao modelo apenas a **pergunta do usuário** e o **texto** dos trechos (opcionalmente identificados como “Bloco 1”, “Bloco 2”, etc., sem passar página/parágrafo no texto para o modelo gerar). O prompt instrui o LLM a responder **apenas** com base nesses trechos, sem inventar fontes.
3. **Saída do LLM:** o modelo devolve apenas o **conteúdo processado** (prosa, resumo ou resposta estruturada). A aplicação **não** usa a saída do LLM para extrair ou inferir página/parágrafo.
4. **Montagem da resposta final:** a aplicação associa cada parte da resposta (ou cada bloco utilizado) aos metadados do hit correspondente e **injeta** as referências exatas: por exemplo, “Segundo [Seção X, p.42, parágrafo 2]: …” ou uma seção “Fontes:” ao final listando (section_title, page, paragraph) dos hits usados, sempre a partir dos dados do retrieval, nunca do texto gerado pelo LLM.

### Resumo

| Aspecto | Decisão |
|--------|---------|
| Papel do LLM | Pré-processar o contexto para melhorar a resposta (clareza, foco). |
| Fonte (seção, p., parágrafo) | Intacta; não processada pelo LLM; anexada/injetada pela aplicação. |
| Tamanho do modelo | Pequeno (4B–7B), só para processamento. |
| Objetivo da restrição | Evitar alucinações em citações e manter rastreabilidade (FR-2.3.6). |

---

## 20. Fine-tuning da Fase 4 em Google Colab (falta de poder computacional local)

### Contexto

O fine-tuning com Unsloth (SFT + LoRA) e export para .gguf requer GPU com CUDA e VRAM adequada (recomendado ≥8 GB para modelos 3B). O ambiente de desenvolvimento do projeto pode não dispor desse hardware.

### Decisão

- **Executar o pipeline da Fase 4 (treino + export .gguf) em Google Colab** (ou ambiente equivalente, ex.: Kaggle, RunPod) quando não houver GPU local suficiente.
- O repositório continua com scripts e módulos **agnósticos de ambiente**: aceitam caminhos explícitos para dataset (train/val) e diretório de saída, de modo que:
  - **Local:** o script `run_finetuning.py` usa `configs/default.yaml` e paths relativos ao projeto.
  - **Colab:** um notebook (ex.: `notebooks/fase4_finetuning_colab.ipynb`) instala Unsloth, monta/copia o dataset (Drive ou upload), chama a mesma lógica de treino/export com paths no ambiente Colab (ex.: `/content/...`) e salva o .gguf no Google Drive ou faz download.
- **Documentação:** O plano da Fase 4 ([docs/PLANO_FASE4_FINETUNING_GGUF.md](PLANO_FASE4_FINETUNING_GGUF.md)) e o próprio notebook explicam como subir o dataset para o Colab (zip dos JSONL, Drive, ou clone do repo) e onde o .gguf é gravado.

### Implementação

- Módulos em `src/finetuning/` (**data_loader**, **train**, **export_gguf**) não dependem da raiz do projeto: recebem **train_path**, **val_path**, **output_dir** e um dicionário de parâmetros de treino (learning_rate, epochs, model_name, etc.).
- O script `scripts/run_finetuning.py` pode ser invocado com config do repo (modo local) ou com argumentos de linha de comando (modo Colab ou CI).
- O notebook Colab:
  1. Verifica/ativa GPU (T4 ou superior).
  2. Instala Unsloth (e dependências) com o wheel recomendado para Colab.
  3. Prepara o dataset: upload dos dois JSONL ou clone do repo e uso de `data/datasets/*.jsonl`.
  4. Chama as funções de load dataset → train → export GGUF com paths e params definidos na própria célula (ou lendo um YAML copiado).
  5. Salva o .gguf no Drive ou oferece download.

### Resumo

| Aspecto | Decisão |
|--------|---------|
| Onde rodar o treino | Google Colab (ou similar) quando não houver GPU local adequada. |
| Compatibilidade | Código aceita paths explícitos e params em dict; funciona local e Colab. |
| Entregável .gguf | Baixado do Colab ou copiado do Drive para `models/` no repo, para uso na Fase 5. |

---

## Referências

- **Plano de implementação:** [PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md](../PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md)
- **Plano Fase 2 (GraphRAG):** [PLANO_IMPLEMENTACAO_FASE2_GRAPHRAG.md](../PLANO_IMPLEMENTACAO_FASE2_GRAPHRAG.md)
- **Requisitos Fase 2:** [REQUIREMENTS_FASE2.md](REQUIREMENTS_FASE2.md)
- **Prompt do sistema:** [PROMPT_NASA_SE_AI_ASSISTANT.md](../PROMPT_NASA_SE_AI_ASSISTANT.md)
- **Fase 1 e troubleshooting:** [FASE1_CHECKPOINT1.md](FASE1_CHECKPOINT1.md)
- **Arquitetura Fase 1:** [ARQUITETURA_FASE1.md](ARQUITETURA_FASE1.md)
- **Guardrails do system prompt:** [GUARDRAILS_SYSTEM_PROMPT.md](GUARDRAILS_SYSTEM_PROMPT.md)

---

*Documento atualizado conforme decisões tomadas na implementação até o Checkpoint 1.*
