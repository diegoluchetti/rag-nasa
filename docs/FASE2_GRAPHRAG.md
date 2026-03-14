# Fase 2 — Grafo em Neo4j: uso e verificação

> A Fase 2 usa **Neo4j** como armazenamento do grafo (nós Chunk, relação NEXT, índice full-text). **Não requer API externa** (OpenAI/Azure); apenas o Neo4j rodando (local ou remoto).

**Instalação e configuração do Neo4j:** veja **[NEO4J_SETUP.md](NEO4J_SETUP.md)** (Docker, Desktop, Aura, senha, ingestão e reteste do verificador).

---

## 1. Pré-requisitos

- **Fase 1 concluída:** chunks em `data/chunks/*.jsonl` (gerados por `run_ingestion.py`).
- **Python:** `pip install neo4j` (ver `requirements-phase2.txt`).
- **Neo4j:** instância rodando. **Como instalar e configurar:** [NEO4J_SETUP.md](NEO4J_SETUP.md). Senha em variável de ambiente `NEO4J_PASSWORD` ou em `configs/default.yaml` (não versionar).

---

## 2. Fluxo em 2 passos

### 2.1 Ingerir chunks no Neo4j

Lê `data/chunks/*.jsonl` e insere nós `Chunk` no Neo4j (propriedades: `text`, `section_title`, `section_level`, `source_file`, `appendix`, `page`, `paragraph`), com relação `NEXT` entre consecutivos e índice full-text em `Chunk.text`. As propriedades `page` e `paragraph` vêm dos metadados da Fase 1 (marcadores no Markdown e chunker) e permitem que a resposta cite a origem no PDF (FR-2.3.6).

```bash
python scripts/run_neo4j_ingest.py
```

Requer: Neo4j acessível (uri/user/password em config ou `NEO4J_PASSWORD`).

### 2.2 Consultar (full-text)

Recupera trechos relevantes à pergunta:

```bash
python scripts/run_neo4j_query.py "Qual a diferença entre Verificação e Validação?"
python scripts/run_neo4j_query.py "Sua pergunta" --log-dir log
```

A saída é o **contexto** (chunks concatenados). Quando disponíveis, cada trecho inclui referência à página e ao parágrafo no PDF (ex.: “(p.42, parágrafo 2)”). Para gerar resposta com LLM + prompt NASA, use esse contexto em um pipeline externo (opcional).

---

## 3. Configuração

Em `configs/default.yaml`, seção `neo4j`:

- `uri`: ex. `bolt://localhost:7687`
- `user`: ex. `neo4j`
- `password`: deixe vazio e use `NEO4J_PASSWORD` no ambiente (recomendado)
- `database`: ex. `neo4j`
- `default_query_method`: `fulltext` | `by_section`
- `top_k`: número de chunks retornados por query (ex.: 5)
- `system_prompt_path`: caminho do prompt NASA (para uso futuro com LLM)

---

## 4. Verificador de requisitos

```bash
python scripts/run_phase2_requirements_verifier.py
```

Com Neo4j rodando e ingestão feita:

```bash
python scripts/run_phase2_requirements_verifier.py --run-reference-query
```

Relatórios em `log/phase2_requirements_verification_*.json` e `*.txt`.

---

## 5. Testes

```bash
python -m pytest tests/test_checkpoint2.py -v
```

---

## 6. Referências

- Requisitos Fase 2: [REQUIREMENTS_FASE2.md](REQUIREMENTS_FASE2.md)
- Design decisions: [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)
- Neo4j Python driver: https://neo4j.com/docs/python-manual/current/
