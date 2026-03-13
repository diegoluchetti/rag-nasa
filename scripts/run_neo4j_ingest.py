"""
Ingere chunks da Fase 1 (data/chunks/*.jsonl) no Neo4j como nós Chunk com índice full-text.
Não requer API externa; apenas Neo4j rodando (local ou remoto) e senha em config ou NEO4J_PASSWORD.
Uso (na raiz do projeto): python scripts/run_neo4j_ingest.py
"""
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graphrag.neo4j_store import ingest_chunks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main() -> None:
    n = ingest_chunks()
    print(f"Ok: {n} chunks ingeridos no Neo4j. Use scripts/run_neo4j_query.py para consultar.")


if __name__ == "__main__":
    main()
