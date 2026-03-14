# AI Systems Engineering Assistant (NASA SE Edition)

Assistente de IA sobre o **NASA Systems Engineering Handbook** (SP-2016-6105-REV2): ingestão estruturada (Fase 1), grafo de conhecimento em Neo4j (Fase 2) e pipeline preparado para fases futuras (dataset, fine-tuning, avaliação).

## Estrutura

- **Fase 1:** PDF → Markdown (Docling) → Chunks JSONL (Hierarchy Aware Chunker). Ver `docs/REQUIREMENTS_FASE1.md`, `docs/FASE1_CHECKPOINT1.md`.
- **Fase 2:** Chunks → Neo4j (nós Chunk, full-text). Query sem API externa. Ver `docs/REQUIREMENTS_FASE2.md`, `docs/FASE2_GRAPHRAG.md`, `docs/NEO4J_SETUP.md`.

## Uso rápido

```bash
# Fase 1 — ingestão (requer PDF em data/raw/)
pip install -r requirements-phase1.txt
python run_ingestion.py

# Fase 2 — Neo4j (configurar configs/local.yaml ou NEO4J_PASSWORD)
pip install -r requirements-phase2.txt
python scripts/run_neo4j_ingest.py
python scripts/run_neo4j_query.py "Sua pergunta"
python scripts/run_phase2_requirements_verifier.py --run-reference-query
```

## Documentação

- [Plano geral](PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md) · [Plano Fase 2 (GraphRAG/Neo4j)](PLANO_IMPLEMENTACAO_FASE2_GRAPHRAG.md)
- [Setup Neo4j](docs/NEO4J_SETUP.md) · [Requisitos Fase 1](docs/REQUIREMENTS_FASE1.md) · [Requisitos Fase 2](docs/REQUIREMENTS_FASE2.md)
- [Decisões de design](docs/DESIGN_DECISIONS.md)

## Repositório remoto

Repositório Git já inicializado com commit inicial. Para enviar para um remoto (GitHub, GitLab, etc.):

1. Crie um repositório **vazio** no serviço (sem README, sem .gitignore).
2. Adicione o remote e faça o push:

```bash
git remote add origin https://github.com/diegoluchetti/rag-nasa.git
git branch -M main
git push -u origin main
```

Substitua a URL pela do seu repositório. Credenciais (senha ou token) podem ser solicitadas.
