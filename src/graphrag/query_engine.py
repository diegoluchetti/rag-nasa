"""
Motor de query sobre o grafo Neo4j (Fase 2).
Busca full-text nos chunks; opcionalmente LLM pré-processa o contexto (Design Decision 19).
Fontes (seção, página, parágrafo) são sempre injetadas pela aplicação a partir do retrieval.
"""
import hashlib
import json
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


def _format_hit(row: dict[str, Any], index: int) -> str:
    """Formata um hit retornado do Neo4j, incluindo página/parágrafo quando disponíveis."""
    sec = row.get("section_title") or "(sem seção)"
    text = row.get("text") or ""
    page = row.get("page")
    paragraph = row.get("paragraph")

    origin_bits: list[str] = []
    if isinstance(page, int) and page > 0:
        origin_bits.append(f"p.{page}")
    if isinstance(paragraph, int) and paragraph > 0:
        origin_bits.append(f"parágrafo {paragraph}")

    origin_str = ""
    if origin_bits:
        origin_str = " (" + ", ".join(origin_bits) + ")"

    header = f"[{index}] {sec}{origin_str}"
    return f"{header}\n{text}"


def _format_source_line(row: dict[str, Any], index: int) -> str:
    """Formata uma linha da seção Fontes (apenas metadados do retrieval; Design Decision 19)."""
    sec = row.get("section_title") or "(sem seção)"
    page = row.get("page")
    paragraph = row.get("paragraph")
    origin_bits: list[str] = []
    if isinstance(page, int) and page > 0:
        origin_bits.append(f"p.{page}")
    if isinstance(paragraph, int) and paragraph > 0:
        origin_bits.append(f"parágrafo {paragraph}")
    origin_str = " (" + ", ".join(origin_bits) + ")" if origin_bits else ""
    return f"[{index}] {sec}{origin_str}"


def _call_llm_for_response(
    question: str,
    context_plain: str,
    system_prompt: str,
    config: dict[str, Any],
) -> str | None:
    """
    Envia pergunta + contexto (apenas texto) ao LLM pequeno (Ollama).
    Retorna a resposta processada ou None em caso de erro.
    Não envia nem pede fontes ao modelo; a aplicação injeta depois.
    """
    neo = config.get("neo4j", {})
    model = neo.get("llm_model", "qwen2.5:3b")
    temperature = float(neo.get("temperature", 0.0))
    timeout = int(neo.get("llm_timeout", 90))
    url = neo.get("ollama_url", "http://localhost:11434").rstrip("/") + "/api/generate"

    user_prompt = (
        "Contexto do NASA Systems Engineering Handbook (trechos recuperados):\n\n"
        f"{context_plain}\n\n"
        "Pergunta do usuário:\n"
        f"{question}\n\n"
        "Responda de forma clara e objetiva com base apenas no contexto acima. "
        "Não invente fontes, páginas ou seções; as referências serão adicionadas automaticamente."
    )
    payload = {
        "model": model,
        "system": system_prompt or "",
        "prompt": user_prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": 1024},
    }
    try:
        from urllib.request import Request, urlopen
        from urllib.error import URLError, HTTPError
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=timeout) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        return (out.get("response") or "").strip()
    except (URLError, HTTPError, OSError, ValueError) as e:
        LOG.warning("LLM para resposta indisponível (%s); retornando apenas contexto.", e)
        return None


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
    Busca no Neo4j (full-text nos chunks). Se neo4j.use_llm_for_response for True,
    o contexto (apenas texto) é enviado a um LLM pequeno para pré-processamento;
    as fontes (seção, página, parágrafo) são injetadas pela aplicação (Design Decision 19).
    Caso contrário, retorna os trechos formatados como hoje.
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
            rows = query_fulltext(driver, question, top_k=top_k, database=database)

        if not rows:
            response = "(Nenhum trecho encontrado para a busca no Handbook.)"
        else:
            use_llm = bool(neo.get("use_llm_for_response", False))
            system_prompt = get_nasa_system_prompt(config) if use_llm else ""
            # Contexto só com texto (sem metadados) para o LLM; fontes injetadas depois
            context_plain = "\n\n".join(
                f"Bloco {i}:\n{(r.get('text') or '').strip()}" for i, r in enumerate(rows, 1)
            )
            sources_section = "\n".join(_format_source_line(r, i) for i, r in enumerate(rows, 1))

            if use_llm and system_prompt and context_plain:
                llm_response = _call_llm_for_response(question, context_plain, system_prompt, config)
                if llm_response:
                    response = f"{llm_response}\n\n---\n\nFontes:\n{sources_section}"
                else:
                    parts = [_format_hit(r, i) for i, r in enumerate(rows, 1)]
                    response = "\n\n---\n\n".join(parts)
            else:
                parts = [_format_hit(r, i) for i, r in enumerate(rows, 1)]
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
