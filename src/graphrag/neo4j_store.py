"""
Grafo de conhecimento em Neo4j (Fase 2).
Ingere chunks da Fase 1 como nós Chunk; cria relação NEXT entre consecutivos e índice full-text.
Não requer API externa (apenas conexão Neo4j).
"""
import json
import logging
import os
from pathlib import Path
from typing import Any

from src.ingestion.config_loader import load_config

LOG = logging.getLogger(__name__)

CHUNK_LABEL = "Chunk"
FULLTEXT_INDEX_NAME = "ChunkText"


def _chunks_source_dir(config: dict[str, Any]) -> Path:
    """Diretório onde estão os JSONL de chunks (Fase 1)."""
    paths = config.get("paths", {})
    chunks_dir = paths.get("data_chunks", "data/chunks")
    root = Path(__file__).resolve().parent.parent.parent
    p = Path(chunks_dir)
    if not p.is_absolute():
        p = root / chunks_dir
    return p


def _iter_chunks(config: dict[str, Any]) -> list[tuple[str, dict]]:
    """Lê todos os chunks de data/chunks/*.jsonl. Retorna lista de (text, metadata)."""
    chunks_dir = _chunks_source_dir(config)
    if not chunks_dir.exists():
        raise FileNotFoundError(f"Diretório de chunks não encontrado: {chunks_dir}")
    jsonl_files = sorted(chunks_dir.glob("*.jsonl"))
    if not jsonl_files:
        raise FileNotFoundError(f"Nenhum arquivo .jsonl em {chunks_dir}")
    out: list[tuple[str, dict]] = []
    for fp in jsonl_files:
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                text = obj.get("text", "")
                meta = obj.get("metadata", {})
                out.append((text, meta))
    return out


def get_driver(config: dict[str, Any] | None = None):
    """Retorna driver Neo4j (lazy import para não exigir neo4j se não usar)."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        raise ImportError("Instale o driver: pip install neo4j")
    if config is None:
        config = load_config()
    neo = config.get("neo4j", {})
    uri = neo.get("uri", "bolt://localhost:7687")
    user = neo.get("user", "neo4j")
    password = neo.get("password") or os.environ.get("NEO4J_PASSWORD", "")
    if not password:
        LOG.warning("Neo4j password não definido em config nem em NEO4J_PASSWORD")
    return GraphDatabase.driver(uri, auth=(user, password))


def create_schema_and_index(driver, database: str | None = "neo4j") -> None:
    """Cria índice full-text para Chunk.text (idempotente)."""
    db = _normalize_database(database)
    with driver.session(database=db) as session:
        # Neo4j 5: CREATE FULLTEXT INDEX ... IF NOT EXISTS
        session.run(
            f"CREATE FULLTEXT INDEX {FULLTEXT_INDEX_NAME} IF NOT EXISTS "
            f"FOR (c:{CHUNK_LABEL}) ON EACH [c.text]"
        )
    LOG.info("Índice full-text %s verificado/criado.", FULLTEXT_INDEX_NAME)


def ingest_chunks(config: dict[str, Any] | None = None) -> int:
    """
    Lê chunks de data/chunks/*.jsonl, insere como nós Chunk no Neo4j e cria NEXT entre consecutivos.
    Retorna número de chunks inseridos.
    """
    if config is None:
        config = load_config()
    chunks = _iter_chunks(config)
    if not chunks:
        raise ValueError("Nenhum chunk encontrado em data/chunks/*.jsonl")

    driver = get_driver(config)
    neo = config.get("neo4j", {})
    db_raw = neo.get("database")
    database = "neo4j" if db_raw is None else (None if str(db_raw).strip() == "" else db_raw)
    database = _normalize_database(database)

    with driver.session(database=database) as session:
        # Limpar nós Chunk existentes (re-ingestão)
        session.run(f"MATCH (c:{CHUNK_LABEL}) DETACH DELETE c")
        LOG.info("Chunks anteriores removidos (se existiam).")

        # Inserir chunks
        for i, (text, meta) in enumerate(chunks):
            chunk_id = f"chunk_{i+1:04d}"
            section_title = meta.get("section_title") or ""
            section_level = int(meta.get("section_level", 0))
            source_file = meta.get("source_file") or ""
            appendix = bool(meta.get("appendix", False))
            session.run(
                f"""
                CREATE (c:{CHUNK_LABEL} {{
                    id: $id,
                    text: $text,
                    section_title: $section_title,
                    section_level: $section_level,
                    source_file: $source_file,
                    appendix: $appendix
                }})
                """,
                id=chunk_id,
                text=text,
                section_title=section_title,
                section_level=section_level,
                source_file=source_file,
                appendix=appendix,
            )

        # Criar relação NEXT entre consecutivos (grafo de sequência)
        result = session.run(
            f"MATCH (c:{CHUNK_LABEL}) WITH c ORDER BY c.id ASC WITH collect(c) AS nodes "
            "UNWIND range(0, size(nodes)-2) AS i "
            f"WITH nodes[i] AS a, nodes[i+1] AS b MERGE (a)-[:NEXT]->(b)"
        )
        result.consume()

    create_schema_and_index(driver, database)
    driver.close()
    LOG.info("Ingestão Neo4j: %s chunks inseridos.", len(chunks))
    return len(chunks)


def _normalize_database(database: str | None) -> str | None:
    """Retorna None se database for vazio (usa banco padrão do servidor)."""
    if database is None or (isinstance(database, str) and database.strip() == ""):
        return None
    return database


def query_fulltext(
    driver,
    query_text: str,
    top_k: int = 5,
    database: str | None = "neo4j",
) -> list[dict[str, Any]]:
    """
    Busca full-text nos nós Chunk. Retorna lista de dict com text, section_title, score.
    """
    db = _normalize_database(database)
    with driver.session(database=db) as session:
        # Escapar aspas no texto da query para Cypher
        q = query_text.replace("\\", "\\\\").replace("'", "\\'")
        result = session.run(
            """
            CALL db.index.fulltext.queryNodes($index_name, $search_phrase)
            YIELD node, score
            RETURN node.text AS text, node.section_title AS section_title, node.id AS id, score
            ORDER BY score DESC
            LIMIT $top_k
            """,
            index_name=FULLTEXT_INDEX_NAME,
            search_phrase=q,
            top_k=top_k,
        )
        rows = [dict(r) for r in result]
    return rows


def get_chunk_count(driver, database: str | None = "neo4j") -> int:
    """Retorna número de nós Chunk no banco."""
    db = _normalize_database(database)
    with driver.session(database=db) as session:
        result = session.run(f"MATCH (c:{CHUNK_LABEL}) RETURN count(c) AS n")
        record = result.single()
        return record["n"] if record else 0
