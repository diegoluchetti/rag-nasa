"""
Pipeline Fase 3 — geração de dataset sintético (stub).

Uso (na raiz do projeto):
  python scripts/run_dataset_gen.py

Com LLM indisponível, usa fallback que gera exemplos a partir do contexto (sem Ollama).
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.config_loader import load_config
from src.dataset_gen.generator import generate_dataset
from src.dataset_gen.postprocess import filter_examples
from src.dataset_gen.export import export_dataset


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger(__name__)


def main() -> None:
  config = load_config()
  cfg_gen = config.get("dataset_gen", {})
  num_pairs = int(cfg_gen.get("num_pairs", 1000))
  seed = int(cfg_gen.get("seed", 42))

  LOG.info("Fase 3: geração de dataset sintético (num_pairs=%s, seed=%s)", num_pairs, seed)

  raw_examples = generate_dataset(num_pairs=num_pairs, seed=seed)
  valid_examples = filter_examples(raw_examples)

  train_path, val_path = export_dataset(valid_examples, config_name="default")

  # Registrar métricas simples
  log_dir = Path("log")
  log_dir.mkdir(exist_ok=True)
  ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
  metrics_path = log_dir / f"dataset_phase3_{ts}.json"
  metrics = {
    "phase": "Fase 3 - Dataset Sintético",
    "generated_raw": len(raw_examples),
    "generated_valid": len(valid_examples),
    "train_path": str(train_path),
    "val_path": str(val_path),
    "collected_at": datetime.utcnow().isoformat() + "Z",
  }
  metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

  LOG.info(
    "Dataset Fase 3 gerado (stub). Ex.: raw=%s, valid=%s, train=%s, val=%s",
    len(raw_examples),
    len(valid_examples),
    train_path,
    val_path,
  )


if __name__ == "__main__":
  main()

