"""
Calcula métricas de retrieval (Hit Rate, MRR) para a Fase 2 usando conjunto gold.
Gera log/phase2_retrieval_metrics_<timestamp>.json.
Uso: python scripts/run_phase2_retrieval_metrics.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    from src.ingestion.config_loader import load_config
    from src.graphrag.retrieval_metrics import compute_retrieval_metrics
    config = load_config()
    metrics = compute_retrieval_metrics(config)
    log_dir = PROJECT_ROOT / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = log_dir / f"phase2_retrieval_metrics_{ts}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"Métricas de retrieval: {out_path}")
    print(f"  Hit Rate: {metrics['hit_rate']}, MRR: {metrics['mrr']}, perguntas: {metrics['num_questions']}")


if __name__ == "__main__":
    main()
