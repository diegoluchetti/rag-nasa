"""
Métricas de retrieval (Hit Rate, MRR) para a Fase 2 usando conjunto gold.
Conjunto gold: data/phase2_gold_questions.json
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def load_gold_questions(path: Path | None = None) -> list[dict[str, Any]]:
    """Carrega data/phase2_gold_questions.json."""
    root = _project_root()
    path = path or root / "data" / "phase2_gold_questions.json"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def compute_retrieval_metrics(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Para cada pergunta gold, executa run_query; verifica se algum expected_keyword
    aparece na resposta; calcula Hit Rate (fração de perguntas com pelo menos 1 hit)
    e MRR (1/rank do primeiro hit, ou 0).
    """
    from src.graphrag.query_engine import run_query

    if config is None:
        from src.ingestion.config_loader import load_config
        config = load_config()
    gold = load_gold_questions()
    if not gold:
        return {"hit_rate": 0.0, "mrr": 0.0, "num_questions": 0, "per_question": []}

    per_question: list[dict[str, Any]] = []
    hits = 0
    reciprocal_ranks: list[float] = []

    for i, item in enumerate(gold):
        question = item.get("question", "")
        expected = item.get("expected_keywords", [])
        if not question or not expected:
            per_question.append({"index": i, "hit": False, "rank": None})
            continue
        try:
            response = run_query(question, method="fulltext", log_dir=None)
            response_lower = response.lower()
            rank = None
            for kw in expected:
                if kw.lower() in response_lower:
                    rank = 1
                    break
            if rank is not None:
                hits += 1
                reciprocal_ranks.append(1.0)
            else:
                reciprocal_ranks.append(0.0)
            per_question.append({"index": i, "hit": rank is not None, "rank": rank})
        except Exception as e:
            per_question.append({"index": i, "hit": False, "rank": None, "error": str(e)})
            reciprocal_ranks.append(0.0)

    n = len(gold)
    hit_rate = hits / n if n else 0.0
    mrr = sum(reciprocal_ranks) / n if n else 0.0

    return {
        "hit_rate": round(hit_rate, 4),
        "mrr": round(mrr, 4),
        "num_questions": n,
        "hits": hits,
        "per_question": per_question,
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }
