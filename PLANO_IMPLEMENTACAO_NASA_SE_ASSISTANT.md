# Plano de Implementação Passo a Passo — AI Systems Engineering Assistant (NASA SE Edition)

> **Referência:** [PROMPT_NASA_SE_AI_ASSISTANT.md](./PROMPT_NASA_SE_AI_ASSISTANT.md)  
> **Objetivo deste documento:** Detalhar cada passo da implementação, explicando o *o quê*, *por quê* e *como* em cada etapa, para execução ordenada e validada por checkpoints.

---

## Índice

1. [Preparação do Ambiente](#0-preparação-do-ambiente)
2. [Fase 1 — Ingestão Estruturada](#1-fase-1--ingestão-estruturada-checkpoint-1)
3. [Fase 2 — RAG Avançado com Reranking](#2-fase-2--rag-avançado-com-reranking-checkpoint-2)
4. [Fase 3 — Geração de Dataset Sintético](#3-fase-3--geração-de-dataset-sintético-checkpoint-3)
5. [Fase 4 — Fine-Tuning do SLM](#4-fase-4--fine-tuning-do-slm-checkpoint-4)
6. [Fase 5 — Integração Final e Avaliação](#5-fase-5--integração-final-e-avaliação)

---

## 0. Preparação do Ambiente

### Passo 0.1 — Estrutura de Diretórios

**O que fazer:** Criar a árvore de pastas do projeto para separar dados, código, modelos e artefatos.

**Por quê:** Evita mistura de PDFs, scripts, chunks, vetores e checkpoints; facilita versionamento e reprodução.

**Como:**

```
rag-nasa/
├── data/
│   ├── raw/                    # PDF original (NASA SE Handbook)
│   ├── markdown/               # Saída do Docling
│   └── chunks/                 # Chunks após Hierarchy Aware Chunker
├── src/
│   ├── ingestion/              # Scripts Fase 1 (Docling + Chunker)
│   ├── rag/                    # Pipeline RAG + Reranker (Fase 2)
│   ├── dataset_gen/            # Geração de pares instrução/resposta (Fase 3)
│   └── evaluation/             # Scripts RAGAS e métricas (Fase 5)
├── models/                     # LoRA/checkpoints do fine-tuning (Fase 4)
├── vector_store/               # ChromaDB ou LanceDB persistido
├── configs/                    # YAML/JSON de parâmetros por fase
├── tests/                      # Testes e validação de checkpoints
└── docs/                       # Documentação e relatórios
```

**Detalhe:** O PDF do Handbook (SP-2016-6105-REV2) deve ser colocado em `data/raw/`. Se ainda não tiver o arquivo, obter da fonte oficial NASA.

---

### Passo 0.2 — Ambiente Virtual e Dependências

**O que fazer:** Criar ambiente Python isolado e instalar dependências por fase.

**Por quê:** Docling, LangChain/LlamaIndex, Unsloth e RAGAS têm requisitos diferentes; isolar evita conflitos de versão.

**Como:**

1. Criar ambiente: `python -m venv .venv` (ou conda).
2. Criar `requirements.txt` (ou `pyproject.toml`) com:
   - **Fase 1:** `docling`, `pypdf`, `tiktoken` (para contagem de tokens no chunker).
   - **Fase 2:** `chromadb` ou `lancedb`, `langchain` ou `llamaindex`, `sentence-transformers` ou cliente Nomic, `FlagEmbedding` (para bge-reranker).
   - **Fase 3:** `openai` ou modelo local para geração de pares (opcional: `llama-cpp`, `vllm`).
   - **Fase 4:** `unsloth`, `transformers`, `datasets`, `peft`, `accelerate`.
   - **Fase 5:** `ragas`, `langsmith` (opcional para tracing).

**Detalhe:** Instalar em etapas conforme for avançando nas fases reduz risco de falha de build (ex.: Unsloth pode exigir CUDA específico).

---

### Passo 0.3 — Arquivo de Configuração Central

**O que fazer:** Definir um `configs/default.yaml` (ou similar) com todos os parâmetros ajustáveis citados no prompt.

**Por quê:** Evita “magic numbers” no código; permite reexperimentar chunk_size, top_k, learning_rate etc. sem alterar código.

**Como:** Incluir seções: `ingestion` (chunk_size, chunk_overlap, table_format), `rag` (top_k_retrieval, top_n_rerank, rerank_threshold, temperature), `dataset_gen` (num_pairs, seed), `finetuning` (learning_rate, epochs, lora_rank, lora_alpha, target_modules). Carregar esse YAML no início de cada script relevante.

---

## 1. Fase 1 — Ingestão Estruturada (Checkpoint 1)

**Objetivo:** PDF → Markdown fiel (tabelas + hierarquia) → Chunks que respeitam seções.

---

### Passo 1.1.1 — Instalar e Configurar o Docling

**O que fazer:** Instalar a biblioteca IBM Docling e verificar que consegue abrir um PDF e exportar Markdown.

**Por quê:** Docling é o motor de parsing escolhido para alta fidelidade de tabelas e estrutura; é preciso garantir que está operacional antes de escrever o script completo.

**Como:**

1. `pip install docling` (verificar versão compatível com seu Python).
2. Na documentação Docling, identificar:
   - Classe/API para carregar PDF (ex.: `DocumentConverter` ou equivalente).
   - Opção de export para Markdown e **formato de tabela** (Markdown vs HTML).
3. Fazer um script mínimo: carregar um PDF de teste (uma página com tabela), exportar para Markdown, inspecionar o arquivo gerado manualmente.

**Detalhe:** Anotar o nome exato do parâmetro que controla `table_format` (ex.: `table_strategy="markdown"` ou similar) para usar no Passo 1.1.2.

---

### Passo 1.1.2 — Script de Conversão PDF → Markdown (Tarefa 1.1)

**O que fazer:** Implementar script (`src/ingestion/docling_to_markdown.py` ou equivalente) que:

- Recebe como entrada o caminho do PDF (ex.: `data/raw/NASA_SE_Handbook.pdf`).
- Usa Docling para converter para Markdown.
- Permite escolher **table_format** via argumento ou config: `markdown` ou `html`.
- Salva o resultado em `data/markdown/` (ex.: um arquivo `.md` por documento ou um único arquivo com todo o Handbook).

**Por quê:** Centralizar a conversão em um único script reproduzível; table_format configurável permite testar depois qual formato o LLM utiliza melhor no RAG.

**Como:**

1. Carregar config (ex.: `configs/default.yaml`) para ler `table_format`.
2. Inicializar o pipeline Docling com:
   - Export para Markdown.
   - Opção de tabela = `table_format` (markdown ou html).
3. Processar o PDF (página a página ou documento inteiro, conforme API Docling).
4. Garantir que **títulos** sejam exportados com níveis corretos (# ## ### etc.) para preservar hierarquia.
5. Escrever o Markdown em disco (encoding UTF-8).
6. Opcional: logar número de páginas, número de tabelas detectadas, e caminho do arquivo de saída.

**Detalhe:** Se o Handbook for muito grande, verificar se Docling suporta processamento em batch ou em partes; do contrário, processar o PDF inteiro de uma vez e monitorar uso de memória.

---

### Passo 1.1.3 — Inspeção Manual do Markdown (Pré-validação)

**O que fazer:** Abrir o Markdown gerado e localizar manualmente:

- Uma tabela de **“Requirement Verification Matrix”** (ou similar).
- Apêndice C (ou outra seção com subseções claras).

**Por quê:** Validação informal antes do chunker: se as tabelas e o Apêndice C já estiverem quebrados ou ilegíveis no Markdown, o problema está no Docling ou no PDF, não no chunker.

**Como:** Abrir o `.md` em um editor, buscar por “Requirement Verification” e “Appendix C”. Verificar: tabelas com colunas/células completas, títulos de seção em níveis corretos. Anotar qualquer problema (ex.: tabela cortada, caracteres estranhos) para corrigir no Docling ou no script.

---

### Passo 1.2.1 — Contagem de Tokens e Estratégia de Chunking

**O que fazer:** Definir como você vai “medir” o tamanho dos chunks (em tokens) e como vai respeitar a hierarquia.

**Por quê:** O prompt pede chunk_size em **tokens** (sugerido 1000) e chunk_overlap 15%; além disso, o chunker deve ser “hierarchy aware”, ou seja, não cortar no meio de uma subseção quando possível.

**Como:**

1. Escolher um tokenizer (ex.: `tiktoken` com encoding `cl100k_base` para compatibilidade com muitos modelos, ou o mesmo que será usado no embedding).
2. Decidir a regra de hierarquia: por exemplo, “nunca cortar dentro de um bloco que começa com `##` ou `###`; se um bloco exceder chunk_size, subdividir apenas por parágrafos ou por `####`”.
3. Definir overlap: 15% de 1000 = 150 tokens; ao criar chunk N+1, incluir os últimos 150 tokens do chunk N no início do próximo (ou por número de sentenças/parágrafos que aproximem isso).

**Detalhe:** Para “Apêndice C como bloco coeso”: se o Apêndice C couber em um único chunk (< 1000 tokens), manter inteiro; se não couber, dividir por subseções (ex.: C.1, C.2) em vez de cortar ao meio de um parágrafo.

---

### Passo 1.2.2 — Implementar o Hierarchy Aware Chunker (Tarefa 1.2)

**O que fazer:** Implementar função ou classe (ex.: `src/ingestion/hierarchy_aware_chunker.py`) que:

- Lê o Markdown gerado no Passo 1.1.2.
- Parseia o documento por cabeçalhos (# ## ### ####) e opcionalmente por tabelas (blocos que começam com `|`).
- Agrupa o texto em “blocos lógicos” (ex.: cada seção até o próximo cabeçalho de mesmo ou maior nível).
- Aplica `chunk_size` (em tokens) e `chunk_overlap` (15%) **dentro** desses blocos: se um bloco for maior que chunk_size, subdivide por parágrafo ou por subseção; se for menor, pode juntar blocos adjacentes até aproximar chunk_size, respeitando um máximo.
- Retorna uma lista de chunks (strings ou objetos com metadados: source_section, page_range se disponível).
- Lê `chunk_size`, `chunk_overlap` e `table_format` do config.

**Por quê:** Chunks que respeitam seções melhoram a qualidade do RAG (o retriever devolve blocos semânticos completos); overlap evita perder informação nas fronteiras.

**Como:**

1. Percorrer o Markdown linha a linha (ou usar regex/split por `\n# `) para identificar cabeçalhos e níveis.
2. Construir uma lista de “blocos”: cada bloco = título + conteúdo até o próximo título de nível igual ou superior.
3. Para cada bloco, contar tokens; se > chunk_size, subdividir (ex.: por `\n\n` ou por `\n###`).
4. Ao montar o texto final de cada chunk, adicionar overlap com o chunk anterior (últimos 15% em tokens).
5. Anexar metadados a cada chunk (ex.: `section_title`, `appendix` se for o caso) para uso na Fase 2 (filtros ou exibição).
6. Salvar os chunks em `data/chunks/` (ex.: JSONL onde cada linha = `{"text": "...", "metadata": {...}}`).

**Detalhe:** Manter tabelas inteiras dentro de um chunk quando possível (não cortar uma tabela ao meio).

---

### Passo 1.3 — Validação do Checkpoint 1

**O que fazer:** Verificar formalmente os critérios do Checkpoint 1.

**Critérios:**

1. As tabelas de “Requirement Verification Matrix” no Markdown estão **legíveis e completas** (inspeção no MD e, se possível, nos chunks que as contêm).
2. Nenhuma tabela truncada ou coluna perdida (amostragem de chunks que contêm tabelas).
3. Hierarquia refletida nos chunks (metadados de seção presentes; nenhum chunk que corte no meio de um título de Apêndice C).

**Como:** Script de teste (ex.: em `tests/test_checkpoint1.py`) que:

- Carrega os chunks.
- Filtra chunks que contêm a string “Requirement Verification” ou “Verification Matrix”.
- Verifica que existe pelo menos um chunk com uma tabela bem formada (ex.: linhas com `|` e número de colunas consistente).
- Verifica que chunks têm metadados de hierarquia (ex.: `section` ou `appendix`).

Executar o script; se passar, marcar **Checkpoint 1 concluído** e só então avançar para a Fase 2.

---

## 2. Fase 2 — RAG Avançado com Reranking (Checkpoint 2)

**Objetivo:** Busca semântica (Top-20) + Reranker (Top-3) + LLM com prompt NASA para respostas precisas.

---

### Passo 2.1.1 — Escolher e Configurar o Modelo de Embedding

**O que fazer:** Integrar um modelo de embeddings (nomic-embed-text ou bge-small-en-v1.5) para converter cada chunk em vetor.

**Por quê:** A busca no vector store é por similaridade de vetores; a qualidade do embedding determina a qualidade do Top-K.

**Como:**

1. Escolher um: **nomic-embed-text** (Nomic) ou **BGE small** (BAAI). Instalar dependências (ex.: `sentence-transformers` para BGE, ou SDK Nomic para nomic-embed-text).
2. Carregar o modelo uma vez; criar uma função `embed(text: str) -> list[float]` (ou em batch `embed(texts: list[str]) -> list[list[float]]`).
3. Verificar dimensão do vetor (ex.: 768 ou 1024) para configurar o vector store na criação da coleção.

**Detalhe:** Se usar API Nomic em vez de modelo local, respeitar rate limits e custo; para desenvolvimento, modelo local (BGE ou Nomic local) é mais estável.

---

### Passo 2.1.2 — Criar e Popular o Vector Store (Tarefa 2.1)

**O que fazer:** Configurar ChromaDB (ou LanceDB), criar uma coleção, embedar todos os chunks da Fase 1 e inserir (texto + vetor + metadados).

**Por quê:** O RAG precisa recuperar rapidamente os trechos mais similares à pergunta; o vector store é a estrutura que permite essa busca.

**Como:**

1. Instanciar o cliente (ChromaDB ou LanceDB) e criar uma coleção com a dimensão correta (ex.: 768 para BGE small).
2. Carregar os chunks de `data/chunks/` (JSONL).
3. Em batches (ex.: 50 chunks por vez), chamar a função de embedding e inserir na coleção: id, embedding, documento (texto), metadados (section, etc.).
4. Persistir o vector store em disco (ex.: `vector_store/`); garantir que o caminho está no config e que não será commitado o conteúdo binário no git (apenas o script de construção).

**Detalhe:** Top-K será 20 na recuperação; não é necessário configurar no índice, apenas na query.

---

### Passo 2.1.3 — Implementar a Recuperação Top-K

**O que fazer:** Função que recebe a pergunta do usuário, embeda a pergunta, consulta o vector store com K=20 e retorna os 20 chunks mais similares (com texto e metadados).

**Por quê:** Esta é a primeira etapa do pipeline RAG: muitos candidatos são melhor filtrados depois pelo reranker.

**Como:** Query ao vector store: `collection.query(query_embeddings=[embed(question)], n_results=20, include=["documents","metadatas"])`. Retornar lista de documentos e metadados para o próximo passo.

---

### Passo 2.2.1 — Instalar e Carregar o Reranker (Tarefa 2.2)

**O que fazer:** Integrar o modelo BAAI/bge-reranker-v2-m3 como cross-encoder: entrada = (query, documento); saída = score de relevância.

**Por quê:** O cross-encoder compara pergunta e cada candidato em conjunto, dando scores mais confiáveis que apenas similaridade de embedding; assim reduzimos 20 candidatos para os 3 (ou 5) mais relevantes.

**Como:**

1. Instalar (ex.: `FlagEmbedding` ou `sentence-transformers` conforme documentação do bge-reranker-v2-m3).
2. Carregar o modelo (ex.: `FlagEmbeddingReranker('BAAI/bge-reranker-v2-m3')`).
3. Implementar função `rerank(query: str, documents: list[str], top_n: int = 3, threshold: float | None = 0.7)`:
   - Para cada (query, doc) calcular score.
   - Ordenar por score decrescente.
   - Opcional: filtrar por threshold (ex.: manter só score >= 0.7).
   - Retornar os top_n documentos (e scores se quiser logar).

**Detalhe:** rerank_threshold pode deixar menos que top_n documentos se muitos ficarem abaixo; definir se aceita retornar 1 ou 2 quando isso acontece ou se preenche com os seguintes até top_n.

---

### Passo 2.2.2 — Encadear Retriever + Reranker

**O que fazer:** Pipeline único: pergunta → embed → Top-20 → rerank → Top-3 (ou Top-N). Expor uma função `retrieve(query: str) -> list[str]` (ou list[dict] com texto e metadados).

**Por quê:** O orquestrador (LangChain/LlamaIndex) ou seu código de aplicação só precisa chamar “retrieve”; a lógica de K=20 e N=3 fica encapsulada.

**Como:** Chamar Passo 2.1.3 com a query; passar os 20 documentos para o reranker; retornar os top_n (e opcionalmente metadados dos selecionados). Ler top_k_retrieval, top_n_rerank e rerank_threshold do config.

---

### Passo 2.3.1 — Definir o Prompt de Sistema (Persona NASA) (Tarefa 2.3)

**O que fazer:** Usar o prompt de sistema sugerido no PROMPT_NASA_SE_AI_ASSISTANT.md (Seção 9) e colocá-lo em constante ou arquivo (ex.: `configs/prompts.yaml` ou `src/rag/prompts.py`).

**Por quê:** O LLM deve se comportar como assistente NASA: só responder com base no contexto, usar “shall”, distinguir Verificação/Validação, citar seções.

**Como:** Copiar o texto do prompt de sistema para o código; no momento de chamar o LLM, enviar esse texto como “system” e o contexto (chunks reranked) + pergunta do usuário como “user” (ou em template: “Context: … Question: …”).

---

### Passo 2.3.2 — Integrar LLM e Montar o RAG Completo

**O que fazer:** Após recuperar os Top-3 (ou Top-N), concatenar os textos em um único “contexto”, montar o prompt do usuário com esse contexto e a pergunta, chamar o LLM (temperature=0.0) e devolver a resposta.

**Por quê:** Este é o fluxo completo RAG: retrieve → rerank → generate.

**Como:**

1. Chamar `retrieve(query)` para obter os chunks finais.
2. Formatar: `Context:\n{chunk1}\n\n{chunk2}\n\n{chunk3}\n\nQuestion: {query}`.
3. Chamar o LLM com system prompt NASA, user = esse texto, temperature = 0.0 (do config).
4. Retornar a resposta; opcional: anexar citações (metadados dos chunks) na resposta.

**Detalhe:** Se usar LangChain: usar LCEL para encadear retriever customizado (que já inclui reranker) + prompt template + llm; se LlamaIndex, usar custom retriever + response synthesizer. Em ambos, configurar temperature via configuração do modelo.

---

### Passo 2.4 — Logging e Tracing (Recomendação do Prompt)

**O que fazer:** Instrumentar o pipeline para logar (ou enviar para LangSmith): query, Top-20 doc ids/scores, Top-3 após rerank (ids e scores), e resposta final.

**Por quê:** Ajuda a debugar quando o Reranker filtra um trecho importante; permite medir Hit Rate e MRR com dados reais.

**Como:** Em cada chamada ao RAG, logar em arquivo ou enviar para LangSmith (span por etapa: retrieve, rerank, generate). Guardar um “run_id” para correlacionar.

---

### Passo 2.5 — Validação do Checkpoint 2

**O que fazer:** Medir Hit Rate e MRR e validar a pergunta “Qual a diferença entre Verificação e Validação?”.

**Critérios:**

1. Construir um pequeno conjunto de avaliação: 10–20 perguntas com resposta esperada (ou pelo menos com “trecho ideal” conhecido). Para cada pergunta, rodar o RAG e verificar se o trecho correto está nos Top-3 e se a resposta é correta.
2. **Hit Rate:** % de perguntas em que o documento “gold” está nos Top-3 recuperados (após rerank).
3. **MRR:** Para cada pergunta, reciprocal rank do primeiro documento relevante (1/rank); média sobre todas as perguntas.
4. Pergunta específica: “Qual a diferença entre Verificação e Validação?” — resposta deve estar alinhada ao Handbook, sem alucinação; idealmente citando seção/apêndice.

**Como:** Script em `tests/test_checkpoint2.py` ou `src/evaluation/rag_metrics.py` que: (1) carrega as perguntas e gold docs; (2) chama o pipeline RAG para cada pergunta; (3) calcula Hit Rate e MRR; (4) chama o RAG para a pergunta de Verificação vs Validação e inspeciona (ou compara com um snippet esperado). Se Hit Rate e MRR forem aceitáveis e a resposta da pergunta-chave for “perfeita”, marcar **Checkpoint 2 concluído**.

---

## 3. Fase 3 — Geração de Dataset Sintético (Checkpoint 3)

**Objetivo:** Produzir 1.000 pares instrução/resposta a partir do Markdown (Apêndice C e Processos), em JSONL, para fine-tuning.

---

### Passo 3.1.1 — Extrair e Indexar Conteúdo Relevante (Apêndice C e Processos)

**O que fazer:** Do Markdown da Fase 1, extrair e indexar (por seção) o conteúdo do Apêndice C e das seções que descrevem processos de SE (inputs/outputs, diagramas).

**Por quê:** O dataset deve ser focado nesses tópicos para o modelo aprender “requisitos NASA” e “processos SE”; ter os textos separados facilita a geração de pares.

**Como:** Script que percorre o MD, identifica “Appendix C” e seções com “Process”, “Input”, “Output”, “Activity”; extrai blocos de texto (e tabelas) e salva em estruturas (ex.: dict por seção) ou em arquivos intermediários. Opcional: usar os chunks já gerados e filtrar por metadados (section/appendix).

---

### Passo 3.1.2 — Definir Templates de Instrução/Resposta (Tarefa 3.1 e 3.2)

**O que fazer:** Definir tipos de pares que você quer no dataset:

1. **Transformação de requisitos:** Instrução = “Reescreva o seguinte requisito no padrão NASA (shall statements): …”; Resposta = requisito reescrito.
2. **Explicação de processos:** Instrução = “Descreva os inputs e outputs do processo X” ou “Explique o processo Y”; Resposta = parágrafo baseado no Handbook.
3. **Checklists/Definições:** Instrução = “O que é Verificação segundo o NASA SE Handbook?”; Resposta = definição extraída.
4. **Correções:** Instrução = “O seguinte requisito está ambíguo: … Corrija no formato NASA.”; Resposta = versão corrigida.

**Por quê:** Diversidade (checklists, definições, correções) e foco em Shall e processos atendem ao prompt.

**Como:** Documentar 5–10 templates em código (strings com placeholders) ou em um arquivo YAML; cada template terá um “gerador” que preenche o placeholder com um trecho do Handbook (ex.: um requisito ambíguo inventado ou extraído, ou o nome de um processo).

---

### Passo 3.2.1 — Gerar os 1.000 Pares

**O que fazer:** Automatizar a geração: para cada template, amostrar trechos do Apêndice C e Processos (ou usar LLM para gerar instruções a partir de um trecho e depois gerar a resposta com o mesmo ou outro LLM usando o trecho como contexto).

**Por quê:** Gerar manualmente 1.000 pares é inviável; usar o próprio Handbook como contexto garante alinhamento com a fonte.

**Como (exemplo com LLM):**

1. Amostrar N trechos do Handbook (ex.: 200 trechos de Apêndice C, 200 de Processos).
2. Para cada trecho, chamar um LLM com prompt do tipo: “Com base no seguinte trecho do NASA SE Handbook, gere uma pergunta que um engenheiro faria e a resposta ideal (baseada apenas no trecho). Formato: JSON com 'instruction' e 'output'.”
3. Coletar as saídas, validar formato (instruction, output) e remover duplicatas; completar até 1.000 pares (re-amostrando ou variando prompts).
4. Garantir diversidade: misturar os 4 tipos (transformação, explicação, definição, correção) em proporções definidas (ex.: 25% cada).

**Detalhe:** Se não quiser usar LLM para gerar, pode criar pares “semi-manuais”: lista de perguntas fixas (ex.: 50) e para cada uma escrever a resposta a partir do Handbook; depois replicar com variações (paráfrase da pergunta) até chegar perto de 1.000. A qualidade pode ser maior, mas o esforço também.

---

### Passo 3.2.2 — Formato JSONL e Compatibilidade Unsloth/HuggingFace

**O que fazer:** Salvar o dataset em JSONL: uma linha por exemplo, com campos aceitos pelo Unsloth (ex.: `instruction` e `output`, ou `text` no formato “instruction + response” concatenado conforme template do modelo).

**Por quê:** Unsloth e HuggingFace datasets esperam formatos específicos; JSONL é universal e fácil de carregar.

**Como:** Para cada par (instruction, output), escrever uma linha: `{"instruction": "...", "output": "..."}` (ou o schema exato do Unsloth, ex.: `{"text": "<|user|>\n...\n<|assistant|>\n..."}`). Salvar em `data/dataset/nasa_se_sft_1k.jsonl`. Verificar na documentação Unsloth o formato esperado (Alpaca, ShareGPT, etc.) e ajustar os nomes dos campos.

---

### Passo 3.3 — Validação do Checkpoint 3

**O que fazer:** Revisão manual de 20 amostras e checagem de lógica de engenharia.

**Critérios:**

1. Amostrar 20 linhas do JSONL (aleatório ou estratificado por tipo).
2. Para cada uma: a instrução é clara? A resposta está correta segundo o Handbook? O formato NASA (Shall, termos oficiais) está respeitado?
3. Registrar erros (ex.: resposta inventada, requisito mal formatado) e corrigir o pipeline de geração ou editar manualmente essas 20 e mais algumas até ter confiança.

**Como:** Script que amostra 20 e gera um arquivo Markdown ou planilha para revisão humana. Após revisão, marcar **Checkpoint 3 concluído**.

---

## 4. Fase 4 — Fine-Tuning do SLM (Checkpoint 4)

**Objetivo:** Fine-tunar Llama 3.2 3B (ou Qwen 2.5 3B) com Unsloth (SFT + LoRA/QLoRA) no dataset da Fase 3.

---

### Passo 4.1.1 — Ambiente de Fine-Tuning (CUDA e Unsloth)

**O que fazer:** Garantir que o ambiente tem CUDA disponível e instalar Unsloth com suporte ao modelo escolhido (Llama 3.2 3B ou Qwen 2.5 3B).

**Por quê:** Unsloth otimiza para GPU; sem CUDA o treino será lento ou inviável. Verificar compatibilidade evita erros de “model not found”.

**Como:** `pip install unsloth` (e dependências); verificar `torch.cuda.is_available()`. Escolher modelo: ex. `unsloth/Llama-3.2-3B` ou `unsloth/Qwen2.5-3B` (conforme documentação Unsloth). Se VRAM < 8GB, considerar 1B.

---

### Passo 4.1.2 — Carregar Dataset e Modelo no Formato Unsloth (Tarefa 4.1)

**O que fazer:** Carregar o JSONL da Fase 3, converter para o formato esperado pelo Unsloth (ex.: dataset com colunas `instruction` e `output`, ou `text`), e carregar o modelo base com `FastLanguageModel` (ou equivalente Unsloth).

**Por quê:** Unsloth tem API específica para SFT; o dataset deve estar no formato que o script de treino espera.

**Como:** Usar `datasets.load_dataset("json", data_files="data/dataset/nasa_se_sft_1k.jsonl")` e mapear para o template de prompt do modelo (ex.: “<|user|>\n{instruction}\n<|assistant|>\n{output}”). Carregar modelo com `FastLanguageModel.for_pretrained(...)` e aplicar `get_peft_model` com config LoRA (Passo 4.2.1).

---

### Passo 4.2.1 — Configurar LoRA/QLoRA (Tarefa 4.2)

**O que fazer:** Aplicar LoRA (ou QLoRA para menor VRAM) com os parâmetros do prompt: rank 16 ou 32, alpha 32, target_modules = q_proj, k_proj, v_proj, o_proj.

**Por quê:** LoRA treina apenas adaptadores, reduzindo memória e tempo; os módulos indicados são os que mais impactam a geração (attention).

**Como:** Criar `LoraConfig`: r=16 (ou 32), lora_alpha=32, target_modules=["q_proj","k_proj","v_proj","o_proj"], lora_dropout=0.05 (ou 0). Se usar QLoRA, configurar quantização (ex.: 4-bit) no carregamento do modelo. Passar esse config para o trainer do Unsloth.

---

### Passo 4.2.2 — Treinar com SFT (Supervised Fine-Tuning)

**O que fazer:** Configurar o Trainer (Unsloth ou HuggingFace) com learning_rate=2e-4, epochs=3, e treinar no dataset.

**Por quê:** SFT ensina o modelo a seguir o formato e o conteúdo dos pares (instrução/resposta NASA); 3 épocas e LR moderado evitam overfitting e instabilidade.

**Como:** Definir `TrainingArguments`: num_train_epochs=3, per_device_train_batch_size=2 (ou 1 se VRAM baixa), gradient_accumulation_steps se necessário, learning_rate=2e-4, logging_steps=10, save_strategy="epoch", output_dir="models/nasa_se_3b_lora". Treinar; salvar checkpoint em `models/`.

---

### Passo 4.3 — Validação do Checkpoint 4

**O que fazer:** Plotar curva de loss e comparar modelo base vs tunado.

**Critérios:**

1. **Curva de Loss:** Durante o treino, logar loss de treino (e validação se houver split); ao final, plotar gráfico (epoch vs loss) e salvar em `docs/` ou `models/`.
2. **Teste comparativo:** Para 5–10 prompts (ex.: “Escreva um requisito NASA para que o sistema deve registrar logs”), gerar resposta com modelo base e com modelo tunado. O tunado deve seguir melhor o formato NASA (Shall, estrutura, terminologia) e não inventar fora do estilo.

**Como:** Usar callbacks ou logs do Trainer para extrair loss por step/epoch; script em Python (matplotlib) para gerar o plot. Script de inferência que carrega base e tunado (merge do LoRA ou carregar adapter) e gera para os mesmos prompts; comparação qualitativa (e opcionalmente métricas de similaridade com respostas de referência). Marcar **Checkpoint 4 concluído** quando a curva for saudável e o tunado for claramente melhor no formato NASA.

---

## 5. Fase 5 — Integração Final e Avaliação

**Objetivo:** Integrar o modelo fine-tunado ao pipeline RAG (RAG-tuned) e avaliar com RAGAS.

---

### Passo 5.1.1 — Integrar Modelo Tunado ao RAG

**O que fazer:** Substituir o LLM usado na Fase 2 pelo modelo fine-tunado (Llama 3.2 3B + LoRA NASA): mesmo fluxo retrieve → rerank → generate, mas o “generate” usa o modelo tunado.

**Por quê:** O sistema final é “RAG-tuned”: recuperação de contexto + geração no “dialeto” NASA.

**Como:** Carregar o checkpoint da Fase 4 (modelo base + adapter LoRA); usar como LangChain LLM ou como função de geração (tokenizer + model.generate). Manter temperature=0.0 e o mesmo system prompt (ou um ajustado para o modelo tunado). Garantir que o contexto (Top-3) continua sendo passado no user prompt.

---

### Passo 5.1.2 — Avaliar com RAGAS (Tarefa 5.1)

**O que fazer:** Para um conjunto de perguntas com respostas de referência (e opcionalmente contextos gold), calcular Faithfulness, Answer Relevance e Context Precision usando RAGAS.

**Por quê:** RAGAS fornece métricas padrão para RAG; assim você compara versões (só RAG vs RAG-tuned) e documenta a qualidade.

**Como:**

1. Instalar `ragas`.
2. Preparar dataset de avaliação: lista de dicts com `question`, `answer` (resposta do sistema), `contexts` (lista dos chunks passados ao LLM), e opcionalmente `ground_truth` (resposta ideal).
3. Chamar `evaluate` da RAGAS com as métricas: faithfulness (resposta baseada no contexto?), answer_relevance (resposta relevante para a pergunta?), context_precision (os contextos recuperados eram os certos?). Registrar os scores.
4. Repetir para o pipeline “só RAG” (modelo base) e “RAG-tuned” (modelo tunado); gerar um pequeno relatório (ex.: tabela em `docs/evaluation_report.md`).

**Detalhe:** Faithfulness e Answer Relevance podem usar o próprio LLM como “evaluator” na RAGAS; seguir a documentação para o formato exato do dataset.

---

### Passo 5.2 — Entregáveis Finais

**O que fazer:** Consolidar artefatos e documentação.

- **Pipeline RAG + Reranker:** Código versionado em `src/rag/`, config em `configs/`, e instruções em `README.md` ou `docs/run_rag.md` para: ingestão (Fase 1), construção do vector store, e execução de uma pergunta.
- **Modelo fine-tunado:** LoRA/checkpoint em `models/` e instruções para carregar e mesclar (ou exportar para HuggingFace).
- **Relatório de métricas:** Hit Rate, MRR (Checkpoint 2), Faithfulness, Answer Relevance, Context Precision (Fase 5) em `docs/evaluation_report.md`.
- **Documentação:** Como executar ingestão, treino e inferência (passo a passo ou comandos) em `docs/`.

---

## Resumo da Ordem de Execução

| # | Passo | Fase | Checkpoint |
|---|--------|------|------------|
| 0 | Preparação (diretórios, venv, config) | - | - |
| 1 | Docling: script PDF→MD + Hierarchy Aware Chunker + validação tabelas/hierarquia | 1 | ✅ Checkpoint 1 |
| 2 | Vector store + embedding + Top-K; Reranker Top-20→Top-3; prompt NASA; Hit Rate/MRR + pergunta Verificação vs Validação | 2 | ✅ Checkpoint 2 |
| 3 | Dataset 1k pares (Apêndice C + Processos); JSONL; revisão 20 amostras | 3 | ✅ Checkpoint 3 |
| 4 | Unsloth SFT + LoRA; treino; curva de loss; comparação base vs tunado | 4 | ✅ Checkpoint 4 |
| 5 | RAG-tuned integrado; RAGAS; relatório e documentação final | 5 | Entregáveis |

---

*Plano de implementação baseado em [PROMPT_NASA_SE_AI_ASSISTANT.md](./PROMPT_NASA_SE_AI_ASSISTANT.md). Execute na ordem e valide cada checkpoint antes de avançar.*
