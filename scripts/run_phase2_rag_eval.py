"""
Avaliação robusta do RAG de grafos (Fase 2).

Executa dois tipos de métrica:
  1) Retrieval: para cada pergunta gold, recupera os top-k chunks (sem LLM) e verifica
     em qual posição (rank) aparece o primeiro chunk que contém algum expected_keyword.
     Calcula Hit@1, Hit@3, Hit@5, Hit@10 e MRR (Mean Reciprocal Rank).
  2) Resposta completa (opcional): chama run_query (retrieval + LLM) e verifica se a
     resposta final contém algum expected_keyword (métrica de “answer hit rate”).

Requer: Neo4j com chunks ingeridos, data/phase2_gold_questions.json.
Uso: python scripts/run_phase2_rag_eval.py [--full-rag] [--top-k 10]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _first_rank_with_keyword(chunks: list[dict], keywords: list[str]) -> int | None:
    """
    Retorna o rank (1-based) do primeiro chunk cujo texto contém algum keyword.
    None se nenhum chunk contiver nenhum keyword.
    """
    keywords_lower = [k.lower() for k in keywords if k]
    for rank, row in enumerate(chunks, 1):
        text = (row.get("text") or "").lower()
        if any(kw in text for kw in keywords_lower):
            return rank
    return None


def run_retrieval_eval(
    config: dict,
    gold: list[dict],
    top_k: int = 10,
) -> dict:
    """Avalia apenas o retrieval: Hit@1, Hit@3, Hit@5, Hit@10, MRR."""
    from src.graphrag.query_engine import retrieve_only

    results = []
    hit_at_1 = hit_at_3 = hit_at_5 = hit_at_10 = 0
    mrr_sum = 0.0

    for i, item in enumerate(gold):
        question = item.get("question", "").strip()
        expected = item.get("expected_keywords") or []
        if not question or not expected:
            results.append({"index": i, "question": question[:80], "rank": None, "hit": False})
            continue

        try:
            chunks = retrieve_only(question, top_k=top_k, config=config)
            rank = _first_rank_with_keyword(chunks, expected)
        except Exception as e:
            results.append({"index": i, "question": question[:80], "error": str(e), "rank": None})
            rank = None

        if rank is not None:
            hit_at_1 += 1 if rank <= 1 else 0
            hit_at_3 += 1 if rank <= 3 else 0
            hit_at_5 += 1 if rank <= 5 else 0
            hit_at_10 += 1 if rank <= 10 else 0
            mrr_sum += 1.0 / rank
            results.append({"index": i, "question": question[:80], "rank": rank, "hit": True})
        else:
            results.append({"index": i, "question": question[:80], "rank": None, "hit": False})

    n = len(gold)
    return {
        "retrieval": {
            "hit_at_1": round(hit_at_1 / n, 4) if n else 0,
            "hit_at_3": round(hit_at_3 / n, 4) if n else 0,
            "hit_at_5": round(hit_at_5 / n, 4) if n else 0,
            "hit_at_10": round(hit_at_10 / n, 4) if n else 0,
            "mrr": round(mrr_sum / n, 4) if n else 0,
            "num_questions": n,
            "top_k": top_k,
        },
        "per_question": results,
    }


def run_answer_eval(config: dict, gold: list[dict]) -> dict:
    """Avalia a resposta completa (retrieval + LLM): fração em que a resposta contém algum keyword."""
    from src.graphrag.query_engine import run_query

    answer_hits = 0
    per_question = []

    for i, item in enumerate(gold):
        question = item.get("question", "").strip()
        expected = item.get("expected_keywords") or []
        if not question or not expected:
            per_question.append({"index": i, "answer_hit": False})
            continue
        try:
            # run_query carrega config internamente (config_name="default")
            response = run_query(question, log_dir=None)
            response_lower = response.lower()
            hit = any(kw.lower() in response_lower for kw in expected)
            if hit:
                answer_hits += 1
            per_question.append({"index": i, "answer_hit": hit})
        except Exception as e:
            per_question.append({"index": i, "answer_hit": False, "error": str(e)})

    n = len(gold)
    return {
        "answer_hit_rate": round(answer_hits / n, 4) if n else 0,
        "num_questions": n,
        "per_question": per_question,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Avaliação robusta do RAG (retrieval + opcional resposta)")
    parser.add_argument("--full-rag", action="store_true", help="Incluir avaliação da resposta completa (retrieval + LLM)")
    parser.add_argument("--top-k", type=int, default=10, help="Número de chunks a recuperar por pergunta (default 10)")
    args = parser.parse_args()

    from src.ingestion.config_loader import load_config
    from src.graphrag.retrieval_metrics import load_gold_questions

    config = load_config()
    gold = load_gold_questions()
    if not gold:
        print("ERRO: data/phase2_gold_questions.json não encontrado ou vazio.")
        sys.exit(1)

    print(f"Perguntas gold: {len(gold)} | top_k: {args.top_k} | full_rag: {args.full_rag}")

    report = {
        "phase": "Fase 2 - RAG evaluation",
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "num_gold_questions": len(gold),
    }

    # Sempre: métricas de retrieval
    retrieval_result = run_retrieval_eval(config, gold, top_k=args.top_k)
    report["retrieval"] = retrieval_result["retrieval"]
    report["per_question_retrieval"] = retrieval_result["per_question"]

    r = report["retrieval"]
    print("\n--- Retrieval (apenas Neo4j full-text) ---")
    print(f"  Hit@1:  {r['hit_at_1']}  |  Hit@3:  {r['hit_at_3']}  |  Hit@5:  {r['hit_at_5']}  |  Hit@10: {r['hit_at_10']}")
    print(f"  MRR:    {r['mrr']}")

    if args.full_rag:
        answer_result = run_answer_eval(config, gold)
        report["answer"] = {
            "answer_hit_rate": answer_result["answer_hit_rate"],
            "num_questions": answer_result["num_questions"],
        }
        report["per_question_answer"] = answer_result["per_question"]
        print("\n--- Resposta completa (retrieval + LLM) ---")
        print(f"  Answer hit rate (resposta contém keyword): {report['answer']['answer_hit_rate']}")

    # Perguntas que falharam no retrieval (rank None)
    failed = [p for p in report["per_question_retrieval"] if not p.get("hit")]
    if failed:
        print("\n--- Perguntas sem hit no retrieval (top-k) ---")
        for p in failed[:10]:
            print(f"  [{p['index']}] {p.get('question', '')}...")
        if len(failed) > 10:
            print(f"  ... e mais {len(failed) - 10}")

    log_dir = PROJECT_ROOT / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    json_path = log_dir / f"phase2_rag_eval_{ts}.json"
    txt_path = log_dir / f"phase2_rag_eval_{ts}.txt"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    lines = [
        "Fase 2 — Avaliação RAG (retrieval + opcional resposta)",
        report["collected_at"],
        f"Perguntas gold: {report['num_gold_questions']}",
        "",
        "Retrieval (Hit@k = fração com chunk relevante no top-k):",
        f"  Hit@1={r['hit_at_1']}  Hit@3={r['hit_at_3']}  Hit@5={r['hit_at_5']}  Hit@10={r['hit_at_10']}  MRR={r['mrr']}",
    ]
    if "answer" in report:
        lines.append(f"\nResposta completa (answer hit rate): {report['answer']['answer_hit_rate']}")
    lines.append(f"\nRelatório completo: {json_path}")
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nRelatório JSON: {json_path}")
    print(f"Resumo TXT:    {txt_path}")


if __name__ == "__main__":
    main()
