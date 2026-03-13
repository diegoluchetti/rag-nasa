# Requisitos da Fase 2 — Grafo de conhecimento (Neo4j)

> Requisitos funcionais (FR) e não funcionais (NFR) que detalham a arquitetura da Fase 2 do AI Systems Engineering Assistant. **Implementação atual:** grafo em **Neo4j** (sem API externa). Entrada: chunks da Fase 1 (`data/chunks/*.jsonl`). Saída: nós Chunk no Neo4j, índice full-text e motor de query.

---

## 1. Visão da Fase 2

A Fase 2 constrói um **grafo de conhecimento** a partir dos chunks da Fase 1 no **Neo4j**: nós `Chunk` (texto e metadados), relação `NEXT` entre consecutivos e índice full-text. O motor de query faz busca full-text e retorna trechos recuperados (contexto). **Neo4j não requer API externa** (apenas conexão ao banco). O prompt de sistema NASA permanece configurável para uso futuro com LLM (opcional).

---

## 2. Requisitos Funcionais (FR)

### FR-2.1 Preparação de entrada (chunks → Neo4j)

| ID     | Descrição | Critério de aceite |
|--------|-----------|---------------------|
| FR-2.1.1 | O sistema deve ler os chunks da Fase 1 em `data/chunks/*.jsonl`. | Leitura de todos os arquivos JSONL em `paths.data_chunks`; cada linha com `text` e `metadata`. |
| FR-2.1.2 | O sistema deve ingerir os chunks no Neo4j como nós Chunk. | Chunks disponíveis no Neo4j (contagem > 0); ingestão via script `run_neo4j_ingest.py`. |
| FR-2.1.3 | O método de query deve ser configurável. | Parâmetro `neo4j.default_query_method`: `fulltext` \| `by_section`. |
| FR-2.1.4 | IDs dos nós Chunk devem ser estáveis e reproduzíveis. | IDs no formato `chunk_0001`, `chunk_0002`, ... por ordem de leitura. |

### FR-2.2 Neo4j e indexação

| ID     | Descrição | Critério de aceite |
|--------|-----------|---------------------|
| FR-2.2.1 | O sistema deve utilizar Neo4j como armazenamento do grafo. | Config `neo4j.uri`, `neo4j.user`, `neo4j.database`; conexão verificável (sem API externa). |
| FR-2.2.2 | O sistema deve suportar a execução da ingestão a partir do projeto. | Script `scripts/run_neo4j_ingest.py` que lê chunks e insere no Neo4j. |
| FR-2.2.3 | Após a ingestão, o Neo4j deve conter nós Chunk e índice full-text. | Contagem de nós Chunk > 0; índice full-text em `Chunk.text` para busca. |
| FR-2.2.4 | A ingestão deve poder ser disparada por script (pipeline automatizável). | Comando `python scripts/run_neo4j_ingest.py` executa a ingestão. |

### FR-2.3 Motor de query (full-text)

| ID     | Descrição | Critério de aceite |
|--------|-----------|---------------------|
| FR-2.3.1 | O sistema deve suportar busca full-text nos chunks. | Query full-text retorna trechos relevantes (contexto) a partir do Neo4j. |
| FR-2.3.2 | O sistema deve retornar contexto (trechos) para a pergunta. | Resposta = concatenação dos chunks recuperados (ou uso posterior com LLM opcional). |
| FR-2.3.3 | O método de query deve ser configurável por config. | Parâmetro `neo4j.default_query_method` e `neo4j.top_k`. |
| FR-2.3.4 | O prompt de sistema NASA deve estar disponível para uso com LLM (quando aplicável). | Arquivo configurável em `neo4j.system_prompt_path` (ex.: `configs/prompts_nasa_system.txt`). |
| FR-2.3.5 | Temperatura configurável para geração com LLM (quando aplicável). | `neo4j.temperature` (ex.: 0.0). |

### FR-2.4 Checkpoint 2 e qualidade

| ID     | Descrição | Critério de aceite |
|--------|-----------|---------------------|
| FR-2.4.1 | O sistema deve responder à pergunta de referência "Qual a diferença entre Verificação e Validação?" de forma alinhada ao Handbook. | Resposta fundamentada no contexto recuperado; distinção Verificação vs Validação presente; sem invenção de definições; citação de seção/apêndice quando relevante. |
| FR-2.4.2 | Deve existir um mecanismo de validação (Checkpoint 2) para a resposta de referência. | Teste ou script que executa a query de referência e verifica presença de termos/conceitos esperados (ex.: "verification", "validation", "requirements") e ausência de disclaimer genérico sem conteúdo. |
| FR-2.4.3 | Métricas de retrieval (Hit Rate, MRR) devem ser computáveis sobre um conjunto de perguntas de teste. | Conjunto de perguntas com "resposta ideal" ou "trecho gold" definido; métricas calculadas e registradas em `log/` (ex.: `phase2_retrieval_metrics_*.json`). |

---

## 3. Requisitos Não Funcionais (NFR)

### NFR-2.1 Configuração

| ID      | Descrição | Critério de aceite |
|---------|-----------|---------------------|
| NFR-2.1.1 | Conexão Neo4j deve ser configurável via config central. | Seção `neo4j` em `configs/default.yaml` com `uri`, `user`, `database`; opcionalmente senha em variável de ambiente `NEO4J_PASSWORD`. |
| NFR-2.1.2 | Neo4j não requer inicialização de workspace (diferente de Microsoft GraphRAG). | Apenas banco Neo4j rodando e ingestão executada. |
| NFR-2.1.3 | Senha do Neo4j não deve ser versionada em claro. | Uso de `NEO4J_PASSWORD` ou config local não commitada; documentado. |

### NFR-2.2 Logging e rastreabilidade

| ID      | Descrição | Critério de aceite |
|---------|-----------|---------------------|
| NFR-2.2.1 | Cada query deve ser registrada para reprodutibilidade e métricas. | Log em `log/` com: query, method (global/local), timestamp/run_id, tamanho do contexto (se disponível), hash ou resumo da resposta. |
| NFR-2.2.2 | Resultados do verificador de requisitos da Fase 2 devem ser gravados em arquivo. | Script de verificação gera relatório em `log/` (ex.: `phase2_requirements_verification_*.json` e `phase2_requirements_verification_*.txt`) com status por FR/NFR e métricas. |

### NFR-2.3 Documentação e manutenibilidade

| ID      | Descrição | Critério de aceite |
|---------|-----------|---------------------|
| NFR-2.3.1 | Decisões de design da Fase 2 devem estar documentadas. | Documento `docs/DESIGN_DECISIONS.md` inclui seção(s) sobre: escolha Microsoft GraphRAG, preparação de input, método de query, prompt NASA, estrutura do workspace. |
| NFR-2.3.2 | Requisitos da Fase 2 devem estar documentados com critérios de aceite. | Este documento (`docs/REQUIREMENTS_FASE2.md`) com todos os FR e NFR e critérios de aceite. |
| NFR-2.3.3 | Deve existir um verificador automatizado que confronte a implementação com os requisitos. | Script (ex.: `scripts/run_phase2_requirements_verifier.py`) que verifica cada FR/NFR listado e produz relatório com pass/fail e métricas evidentes. |

### NFR-2.4 Robustez e operação

| ID      | Descrição | Critério de aceite |
|---------|-----------|---------------------|
| NFR-2.4.1 | A preparação de input deve falhar de forma explícita se não houver chunks. | Se `data/chunks/` estiver vazio ou não existir, o script de preparação levanta erro claro ou retorna código de saída não zero. |
| NFR-2.4.2 | A query deve falhar de forma explícita se o índice não existir. | Antes de executar query, verificar presença dos artefatos em `output/`; mensagem clara se o índice não tiver sido construído. |

---

## 4. Diagrama de arquitetura (Fase 2 — Neo4j)

```
data/chunks/*.jsonl  -->  [Ingestão Neo4j]  -->  Neo4j: nós Chunk, NEXT, índice full-text
                                                      |
User question ----------> [Query Engine]  -->  full-text search no Neo4j
                                                      |
                                                      +-- top_k chunks como contexto
                                                      +-- (opcional) System prompt NASA + LLM
                                                      v
                                                Contexto / Response (+ log)
```

---

## 5. Resumo de IDs para o verificador

O script de verificação de requisitos deve avaliar pelo menos os seguintes IDs:

**Funcionais:** FR-2.1.1, FR-2.1.2, FR-2.1.3, FR-2.1.4, FR-2.2.1, FR-2.2.2, FR-2.2.3, FR-2.2.4, FR-2.3.1, FR-2.3.2, FR-2.3.3, FR-2.3.4, FR-2.3.5, FR-2.4.1, FR-2.4.2, FR-2.4.3.

**Não funcionais:** NFR-2.1.1, NFR-2.1.2, NFR-2.1.3, NFR-2.2.1, NFR-2.2.2, NFR-2.3.1, NFR-2.3.2, NFR-2.3.3, NFR-2.4.1, NFR-2.4.2.

Cada item deve resultar em: **PASS** (critério de aceite atendido), **FAIL** (não atendido) ou **SKIP** (pré-condição não satisfeita, ex.: índice não construído). Métricas numéricas ou booleanas devem ser registradas onde aplicável (ex.: número de arquivos em input, presença de parquets, tamanho do contexto).

---

*Documento de requisitos da Fase 2 — GraphRAG. Referência: [PLANO_IMPLEMENTACAO_FASE2_GRAPHRAG.md](../PLANO_IMPLEMENTACAO_FASE2_GRAPHRAG.md).*
