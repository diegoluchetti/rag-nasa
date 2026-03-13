"""
Motor de query sobre o grafo Neo4j (Fase 2).
Busca full-text nos chunks, retorna contexto; opcionalmente aplica prompt NASA se houver LLM configurado.
Neo4j não requer API externa (apenas conexão ao banco).
"""
import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any

from src.ingestion.config_loader import load_config
from src.graphrag.neo4j_store import get_driver, query_fulltext, get_chunk_count, FULLTEXT_INDEX_NAME

LOG = logging.getLogger(__name__)


def get_nasa_system_prompt(config: dict[str, Any] | None = None) -> str:
    """Retorna o texto do prompt de sistema NASA (configs/prompts_nasa_system.txt)."""
    if config is None:
        config = load_config()
    neo4j_cfg = config.get("neo4j", {})
    path_str = neo4j_cfg.get("system_prompt_path")
    if not path_str:
        return ""
    path = Path(path_str)
    if not path.exists():
        LOG.warning("Arquivo de system prompt não encontrado: %s", path)
        return ""
    return path.read_text(encoding="utf-8").strip()


def ensure_index_exists(config: dict[str, Any]) -> int:
    """Verifica se há chunks no Neo4j. Retorna contagem; levanta RuntimeError se zero."""
    driver = get_driver(config)
    neo = config.get("neo4j", {})
    database = neo.get("database", "neo4j")
    try:
        n = get_chunk_count(driver, database)
        if n == 0:
            driver.close()
            raise RuntimeError(
                "Nenhum chunk no Neo4j. Execute a ingestão primeiro: python scripts/run_neo4j_ingest.py"
            )
        driver.close()
        return n
    except Exception as e:
        try:
            driver.close()
        except Exception:
            pass
        raise RuntimeError(f"Neo4j indisponível ou sem chunks: {e}") from e


def run_query(
    question: str,
    method: str | None = None,
    config_name: str = "default",
    log_dir: Path | str | None = None,
    verbose: bool = False,
) -> str:
    """
    Busca no Neo4j (full-text nos chunks) e retorna o contexto concatenado como resposta.
    Não chama LLM (Neo4j não precisa de API); o texto retornado é o contexto recuperado.
    Para gerar resposta com LLM + prompt NASA, use um pipeline externo que chame run_query
    para obter contexto e depois o LLM.
    """
    config = load_config(config_name)
    ensure_index_exists(config)

    neo = config.get("neo4j", {})
    method = method or neo.get("default_query_method", "fulltext")
    top_k = int(neo.get("top_k", 5))
    db_raw = neo.get("database")
    database = None if (db_raw is not None and str(db_raw).strip() == "") else (db_raw or "neo4j")

    driver = get_driver(config)
    try:
        if method in ("fulltext", "full_text"):
            rows = query_fulltext(driver, question, top_k=top_k, database=database)
        else:
            # by_section: poderia filtrar por section_title; por simplicidade usa fulltext
            rows = query_fulltext(driver, question, top_k=top_k, database=database)

        if not rows:
            response = "(Nenhum trecho encontrado para a busca no Handbook.)"
        else:
            parts = []
            for i, r in enumerate(rows, 1):
                sec = r.get("section_title") or "(sem seção)"
                text = r.get("text") or ""
                parts.append(f"[{i}] {sec}\n{text}")
            response = "\n\n---\n\n".join(parts)
    finally:
        driver.close()

    run_id = str(uuid.uuid4())[:8]
    response_hash = hashlib.sha256(response.encode("utf-8")).hexdigest()[:16]
    LOG.info("Neo4j query: method=%s top_k=%s run_id=%s response_len=%s", method, top_k, run_id, len(response))

    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / f"neo4j_query_{run_id}.txt"
        log_file.write_text(
            f"run_id={run_id}\nmethod={method}\nquestion={question}\nresponse_hash={response_hash}\nresponse_len={len(response)}\n\n---\n\n{response}",
            encoding="utf-8",
        )
        LOG.info("Query log gravado em %s", log_file)

    return response
