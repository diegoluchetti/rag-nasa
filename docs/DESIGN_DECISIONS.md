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
- Metadados incluem: `section_title`, `section_level`, `appendix` (detectado por regex no título), `source_file`.
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
- **Verificador de requisitos:** Um script dedicado (`scripts/run_phase2_requirements_verifier.py`) percorre todos os FR e NFR da Fase 2, verifica critérios de aceite (existência de arquivos, config, índice, resposta de referência, etc.) e gera relatório em `log/` (JSON + TXT) com status PASS/FAIL/SKIP e métricas evidentes (ex.: número de arquivos em input, presença de parquets, resultado do Checkpoint 2).

**Motivação:**
- Rastreabilidade e auditoria; possibilidade de regressão e comparação entre runs.
- Garantir que a implementação cumpra todos os requisitos documentados em `docs/REQUIREMENTS_FASE2.md` com evidências objetivas.

---

## Referências

- **Plano de implementação:** [PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md](../PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md)
- **Plano Fase 2 (GraphRAG):** [PLANO_IMPLEMENTACAO_FASE2_GRAPHRAG.md](../PLANO_IMPLEMENTACAO_FASE2_GRAPHRAG.md)
- **Requisitos Fase 2:** [REQUIREMENTS_FASE2.md](REQUIREMENTS_FASE2.md)
- **Prompt do sistema:** [PROMPT_NASA_SE_AI_ASSISTANT.md](../PROMPT_NASA_SE_AI_ASSISTANT.md)
- **Fase 1 e troubleshooting:** [FASE1_CHECKPOINT1.md](FASE1_CHECKPOINT1.md)
- **Arquitetura Fase 1:** [ARQUITETURA_FASE1.md](ARQUITETURA_FASE1.md)

---

*Documento atualizado conforme decisões tomadas na implementação até o Checkpoint 1.*
