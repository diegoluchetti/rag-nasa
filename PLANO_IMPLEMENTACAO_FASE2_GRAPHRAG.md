# Plano de Implementação — Fase 2: GraphRAG (NASA SE Edition)

> **Pivot em relação ao plano original:** Em vez de RAG com reranking (vector store + cross-encoder), a Fase 2 conecta a **ingestão da Fase 1** a um pipeline **GraphRAG**: grafo de conhecimento extraído dos chunks, com busca global (resumos de comunidades) e local (entidades e relações), mantendo a Persona NASA e a avaliação de qualidade.
>
> **Fase 1:** Permanece **as is** — Docling → Markdown → Hierarchy Aware Chunker → chunks em `data/chunks/*.jsonl`. Esses chunks são a **entrada** do GraphRAG.

---

## 1. Visão geral da Fase 2 (GraphRAG)

### 1.1 Objetivo

- Construir um **grafo de conhecimento** a partir dos chunks gerados na Fase 1.
- Oferecer **recuperação em dois níveis**: **global** (visão de alto nível, temas/processos do Handbook) e **local** (entidades e relações específicas, ex.: “Verificação vs Validação”, requisitos, inputs/outputs de processos).
- Integrar um **motor de query** (global + local) com **LLM** e **prompt de sistema NASA** para respostas fundamentadas no Handbook, sem alucinação.

### 1.2 Por que GraphRAG em vez de RAG reranked?

| Aspecto | RAG Reranked | GraphRAG |
|--------|---------------|----------|
| Representação | Chunks como vetores; reranker filtra Top-K. | Entidades + relações em grafo; comunidades com resumos. |
| Perguntas de síntese | Limitado ao que cabe nos Top-N chunks. | Busca **global** sobre resumos de comunidades (visão do documento inteiro). |
| Perguntas multi-hop | Difícil conectar informações distantes. | **Local** explora vizinhança do grafo (cadeias de relações). |
| Domínio NASA SE | Bom para trechos específicos. | Melhor para “quais processos usam X?”, “como se relacionam Verificação e Validação?”. |

### 1.3 Entrada da Fase 2 (saída da Fase 1)

- **Arquivos:** `data/chunks/*.jsonl` (ex.: `nasa_systems_engineering_handbook_0_chunks.jsonl`).
- **Formato por linha:** `{"text": "...", "metadata": {"section_title", "section_level", "appendix", "source_file"}}`.
- **Opcional:** `data/markdown/*.md` para alimentar o GraphRAG com texto contínuo por seção (dependendo da ferramenta escolhida).

---

## 2. Opções de arquitetura GraphRAG

### Opção A — Microsoft GraphRAG (recomendada para primeiro ciclo)

- **Fonte:** [microsoft/graphrag](https://github.com/microsoft/graphrag), pip: `graphrag`.
- **Fluxo:** Texto em arquivos (ex.: um `.txt` por chunk ou um único arquivo) → `graphrag index` → extração de entidades/relações (LLM), clustering (Leiden), resumos de comunidades → saída em **Parquet** (grafo + embeddings + resumos).
- **Query:** `graphrag query "pergunta"` com `--method global` ou `--method local`; usa os resumos e o grafo para montar o contexto e chamar o LLM.
- **Prós:** Pipeline completo, global + local, bem documentado.  
- **Contras:** Consome chamadas LLM na indexação (OpenAI/Azure); custo e tempo de indexação altos para 300+ páginas.

### Opção B — GraphRAG custom (LlamaIndex / LangChain)

- **Ideia:** Grafo em que **nós** = chunks ou entidades extraídas; **arestas** = relação “pertence à seção”, “menciona processo X” ou triplas (sujeito, relação, objeto) extraídas por LLM.
- **Ferramentas:** LlamaIndex (PropertyGraph, Neo4j ou in-memory) ou LangChain (graph retriever); embeddings opcionais nos nós para híbrido (grafo + vetorial).
- **Prós:** Controle total, possível uso de modelo local para extração, reuso de ChromaDB/LanceDB se desejar.  
- **Contras:** Mais desenvolvimento (extração de triplas, decisão de esquema, estratégia de retrieval).

**Recomendação:** Iniciar com **Opção A** (Microsoft GraphRAG) para validar o valor no domínio NASA SE; depois, se necessário, evoluir para uma solução híbrida ou custom (Opção B) reutilizando os mesmos chunks.

---

## 3. Stack tecnológica sugerida (Fase 2 — GraphRAG)

| Componente | Tecnologia | Observação |
|------------|------------|------------|
| **Indexação / Query** | Microsoft GraphRAG (`graphrag`) | Pipeline padrão: index + query global/local. |
| **LLM (indexação e query)** | OpenAI ou Azure OpenAI | Configurável em `settings.yaml` e `.env`. |
| **Embeddings** | Via GraphRAG (OpenAI/Azure) | Usados na indexação e na busca. |
| **Persistência do índice** | Parquet (output do `graphrag index`) | Em `output/` ou `graph_store/` no projeto. |
| **Prompt de sistema** | Persona NASA (texto fixo ou config) | Mesmo conteúdo do PROMPT_NASA_SE_AI_ASSISTANT.md; injetado na query. |
| **Orquestração opcional** | LangChain / LlamaIndex | Para integrar GraphRAG como retriever em um fluxo maior (ex.: agente, chain). |

A Fase 1 **não muda**: Docling, tiktoken, pypdf, chunker, JSONL. O vector store (ChromaDB/LanceDB) e o reranker (bge-reranker) do plano original **não são usados** na Fase 2 GraphRAG; podem ser mantidos em paralelo para comparação futura, se desejado.

---

## 4. Passos de implementação (Opção A — Microsoft GraphRAG)

### 4.1 Preparação do ambiente e do workspace GraphRAG

**Objetivo:** Ter um ambiente GraphRAG isolado (ou no mesmo venv) e um workspace com `input/`, `output/`, `settings.yaml`, `.env`.

**Ações:**

1. Criar diretório de trabalho GraphRAG (ex.: `graphrag_workspace/` na raiz do projeto ou usar a raiz com subpastas).
2. `pip install graphrag` (Python 3.10–3.12).
3. Executar `graphrag init` para gerar `settings.yaml`, `.env` e pasta `input/`.
4. Configurar em `settings.yaml` e `.env`:
   - Modelo de chat e de embeddings (OpenAI ou Azure).
   - Opcional: reduzir custo na indexação (modelos mais baratos ou menos passos).

**Configuração recomendada no projeto:**

- Manter `configs/default.yaml` com uma seção `graphrag` (paths do workspace, método de query padrão, modelo).
- Documentar em `docs/` que a Fase 2 usa GraphRAG e onde estão `settings.yaml` e `.env` (não versionar chaves).

---

### 4.2 Preparar entrada a partir dos chunks (Fase 1)

**Objetivo:** O GraphRAG espera texto em arquivos (ex.: `.txt`) em `input/`. Os chunks da Fase 1 estão em JSONL.

**Ações:**

1. Implementar script em `src/graphrag/` (ou `scripts/`): ler `data/chunks/*.jsonl`, para cada chunk escrever um arquivo de texto em `graphrag_workspace/input/` (ex.: `chunk_001.txt`, `chunk_002.txt`) com:
   - Conteúdo: `text` do chunk.
   - Opcional: no início do arquivo, uma linha com metadados (ex.: `section_title`, `section_level`) para o modelo “ver” a estrutura.
2. Alternativa: um único arquivo com todos os chunks concatenados (ex.: `handbook_full.txt`), separados por um delimitador claro (ex.: `\n--- CHUNK ---\n`). Isso reduz o número de arquivos e pode simplificar o pipeline; testar qual dá melhor extração de entidades.
3. Garantir encoding UTF-8 e nomes de arquivo estáveis para reprodutibilidade.

**Métricas ajustáveis (config):**

- `graphrag.input_mode`: `one_file_per_chunk` | `single_file`.
- `graphrag.input_dir`: caminho para `input/` (absoluto ou relativo à raiz).

---

### 4.3 Executar indexação GraphRAG

**Objetivo:** Rodar o pipeline de indexação (entidades, relações, clustering, resumos) e persistir o resultado em Parquet.

**Ações:**

1. Com `input/` preenchido, executar `graphrag index` no workspace (CLI ou via `subprocess` a partir de um script do projeto).
2. Validar que a pasta de **output** (ex.: `output/` ou `graph_store/`) contém os Parquets esperados (entidades, relações, comunidades, resumos, embeddings).
3. Documentar tempo de execução e uso aproximado de tokens/API para o Handbook (para referência e custo).
4. Opcional: script `scripts/run_graphrag_index.py` que (1) chama o script de preparação de chunks → input, (2) chama `graphrag index`, (3) copia ou linka `output/` para um diretório versionado no projeto (ex.: `graph_store/phase2/`).

**Checkpoint 2.1:** Indexação concluída sem erro; presença de arquivos de grafo e resumos no output.

---

### 4.4 Integrar motor de query (global + local) e prompt NASA

**Objetivo:** Responder perguntas usando busca global e/ou local do GraphRAG e um LLM com o prompt de sistema NASA.

**Ações:**

1. Definir **prompt de sistema NASA** em `configs/prompts.yaml` ou `src/rag/prompts.py` (mesmo texto do PROMPT_NASA_SE_AI_ASSISTANT.md, Seção 9): responder apenas com base no contexto, usar “shall”, distinguir Verificação/Validação, citar seções quando relevante.
2. Estratégia de query:
   - **Global:** para perguntas amplas (“Quais são os principais processos de engenharia de sistemas no Handbook?”, “Resuma a estrutura do documento.”). Usar `graphrag query "pergunta" --method global` (ou equivalente via API/CLI).
   - **Local:** para perguntas focadas (“Qual a diferença entre Verificação e Validação?”, “Quais são os inputs do processo X?”). Usar `graphrag query "pergunta" --method local`.
3. Implementar uma camada de orquestração (ex.: `src/graphrag/query_engine.py`):
   - Entrada: pergunta do usuário.
   - Decisão (heurística ou classificador): usar global ou local (ex.: por palavras-chave, ou sempre tentar local primeiro e fallback para global).
   - Chamada ao GraphRAG query com a pergunta.
   - Injeção do **system prompt NASA** na chamada ao LLM (se a CLI não permitir, usar a API Python do GraphRAG, se disponível, ou pós-processar o contexto retornado e chamar o LLM separadamente com o prompt NASA).
4. Garantir **temperature=0** (ou baixa) para respostas técnicas estáveis.
5. Resposta final: texto + opcionalmente citações (comunidade, entidades) quando o GraphRAG expuser metadados.

**Métricas ajustáveis (config):**

- `graphrag.default_method`: `global` | `local` | `auto`.
- `graphrag.temperature`: 0 (recomendado).
- `graphrag.system_prompt_path`: caminho para o texto do prompt NASA.

---

### 4.5 Logging e tracing

**Objetivo:** Rastrear perguntas, método usado (global/local), contexto retornado e resposta, para debug e métricas.

**Ações:**

1. Em cada query: logar (arquivo em `log/` ou LangSmith) query, method, tamanho do contexto, resposta (ou hash).
2. Manter um `run_id` ou timestamp para correlacionar com avaliações (Hit Rate, MRR, perguntas de teste).

---

### 4.6 Validação e Checkpoint 2

**Objetivo:** Garantir que o GraphRAG + LLM responde corretamente a perguntas-chave e que a decisão global vs local faz sentido.

**Critérios:**

1. **Pergunta de referência:** “Qual a diferença entre Verificação e Validação?” — a resposta deve estar alinhada ao Handbook, sem invenção, preferencialmente citando seção/apêndice.
2. **Métricas de retrieval (quando aplicável):** Hit Rate e MRR em um conjunto pequeno de perguntas com “resposta ideal” ou “trecho gold” conhecido (avaliar se o contexto retornado pelo GraphRAG contém o trecho ou a entidade correta).
3. **Regressão de qualidade:** Comparar, de forma qualitativa, uma resposta do GraphRAG com a que seria obtida com RAG reranked (se ainda disponível) para a mesma pergunta.

**Checkpoint 2 (GraphRAG):** Indexação ok; pergunta “Verificação vs Validação” respondida de forma correta e fundamentada; métricas de retrieval registradas em `log/`. Só então avançar para Fase 3 (dataset sintético) ou para fine-tuning (Fase 4).

---

## 5. Passos de implementação (Opção B — GraphRAG custom, resumido)

Caso se opte por uma solução **custom** com LlamaIndex ou LangChain:

1. **Esquema do grafo:** Definir nós (chunk_id, texto, section_title, opcionalmente entidades extraídas) e arestas (ex.: “pertence_seção”, “referencia_processo”, triplas sujeito-relação-objeto).
2. **Extração:** Para cada chunk, usar um LLM (ou regras) para extrair entidades e relações (ex.: processos, requisitos, métodos de verificação) e inserir no grafo.
3. **Store:** PropertyGraph (LlamaIndex) em memória ou Neo4j; opcionalmente embeddings nos nós e índice vetorial para híbrido.
4. **Retrieval:** Para uma pergunta: (a) buscar nós relevantes (por entidade ou por embedding), (b) expandir vizinhança no grafo (1–2 saltos), (c) montar contexto com texto dos nós e (d) gerar resposta com LLM + prompt NASA.
5. **Avaliação:** Mesmos critérios do Checkpoint 2 (pergunta Verificação vs Validação, Hit Rate/MRR em conjunto de teste).

Detalhes de implementação (classes, config, formato de triplas) podem ser expandidos em um documento separado quando a Opção B for adotada.

---

## 6. Configuração (configs/default.yaml) — Fase 2 GraphRAG

Sugestão de seção a adicionar:

```yaml
# --- Fase 2: GraphRAG ---
graphrag:
  workspace_dir: graphrag_workspace   # ou path absoluto
  input_dir: graphrag_workspace/input
  output_dir: graphrag_workspace/output  # ou graph_store/phase2
  input_mode: one_file_per_chunk      # one_file_per_chunk | single_file
  default_query_method: local         # global | local | auto
  temperature: 0.0
  system_prompt: configs/prompts_nasa_system.txt  # ou inline
  # Opcional: auto escolher global vs local
  use_auto_method: false
```

Manter as seções `rag` (ou renomear para referência histórica) apenas se for útil para comparação ou para um pipeline híbrido futuro.

---

## 7. Estrutura de diretórios sugerida (Fase 2)

```
rag-nasa/
├── data/
│   ├── raw/
│   ├── markdown/
│   └── chunks/              # Saída Fase 1 (entrada GraphRAG)
├── graphrag_workspace/      # Workspace Microsoft GraphRAG
│   ├── input/               # .txt gerados a partir dos chunks
│   ├── output/              # Parquet após graphrag index
│   ├── settings.yaml
│   └── .env                 # Não versionar
├── graph_store/             # Cópia ou link do output (opcional)
├── src/
│   ├── ingestion/           # Fase 1 (inalterado)
│   ├── graphrag/            # Scripts Fase 2: prepare_input, query_engine
│   ├── rag/                 # Opcional: RAG reranked para comparação
│   ├── dataset_gen/
│   └── evaluation/
├── configs/
│   ├── default.yaml         # + seção graphrag
│   └── prompts_nasa_system.txt
├── log/                     # Métricas e resultados (Checkpoint 2, etc.)
└── docs/
```

---

## 8. Resumo dos checkpoints e ordem de execução (Fase 2)

| Ordem | Etapa | Checkpoint / Entrega |
|-------|--------|----------------------|
| 1 | Fase 1 concluída | Checkpoint 1 aprovado; chunks em `data/chunks/*.jsonl`. |
| 2 | Ambiente GraphRAG + preparação de input | Chunks exportados para `graphrag_workspace/input/` (ou um único arquivo). |
| 3 | Indexação | `graphrag index` concluído; output Parquet presente. **Checkpoint 2.1.** |
| 4 | Query engine + prompt NASA | Integração global/local + system prompt; resposta à pergunta “Verificação vs Validação” correta. **Checkpoint 2.** |
| 5 | Métricas e log | Hit Rate, MRR (e opcionalmente comparação com RAG) registrados em `log/`. |

---

## 9. Requisitos funcionais e não funcionais (Fase 2 — GraphRAG)

### 9.1 Requisitos funcionais (resumo)

- **FR-2.1** O sistema deve construir um índice GraphRAG a partir dos chunks da Fase 1 (entrada em texto em `input/`).
- **FR-2.2** O sistema deve suportar busca **global** (resumos de comunidades) e **local** (entidades e relações).
- **FR-2.3** O sistema deve usar o **prompt de sistema NASA** em toda resposta gerada por LLM.
- **FR-2.4** O sistema deve responder à pergunta “Qual a diferença entre Verificação e Validação?” de forma alinhada ao Handbook (Checkpoint 2).

### 9.2 Requisitos não funcionais (resumo)

- **NFR-2.1** Configuração (paths, método de query, temperature) via `configs/default.yaml` e/ou `graphrag_workspace/settings.yaml`.
- **NFR-2.2** Logging de queries e resultados em `log/` para reprodutibilidade e métricas.
- **NFR-2.3** Documentação da decisão de pivot (RAG reranked → GraphRAG) e do plano de Fase 2 em `docs/` (este documento).

---

## 10. Referências

- **Fase 1 (inalterada):** [PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md](PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md) (Seção 1 e Checkpoint 1); [docs/REQUIREMENTS_FASE1.md](docs/REQUIREMENTS_FASE1.md).
- **Requisitos e uso Fase 2:** [docs/REQUIREMENTS_FASE2.md](docs/REQUIREMENTS_FASE2.md), [docs/FASE2_GRAPHRAG.md](docs/FASE2_GRAPHRAG.md).
- **Prompt e visão do sistema:** [PROMPT_NASA_SE_AI_ASSISTANT.md](PROMPT_NASA_SE_AI_ASSISTANT.md).
- **Microsoft GraphRAG:** [Getting Started](https://microsoft.github.io/graphrag/get_started/), [Overview](https://microsoft.github.io/graphrag/index/overview/), [Query Engine](https://microsoft.github.io/graphrag/query/overview/).
- **Design decisions (Fase 1 e Fase 2):** [docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md).

---

*Plano de implementação da Fase 2 — GraphRAG. Fase 1 permanece as is; os chunks são a entrada do pipeline de grafo. Validar Checkpoint 2 antes de seguir para Fase 3 (dataset sintético) ou Fase 4 (fine-tuning).*
