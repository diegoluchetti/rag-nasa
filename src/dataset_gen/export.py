"""
Export do dataset sintético (Fase 3) para JSONL com splits train/val.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import List, Tuple

from src.ingestion.config_loader import load_config, get_path
from src.dataset_gen.schema import DatasetExample


def export_dataset(
  examples: List[DatasetExample],
  train_ratio: float = 0.9,
  config_name: str = "default",
) -> Tuple[Path, Path]:
  """
  Salva o dataset em JSONL (train/val) e retorna os caminhos.

  Se não houver exemplos, ainda assim cria arquivos vazios.
  """
  config = load_config(config_name)
  data_root = get_path(config, "data_datasets")
  data_root.mkdir(parents=True, exist_ok=True)

  n_train = int(len(examples) * train_ratio)
  train = examples[:n_train]
  val = examples[n_train:]

  train_path = data_root / "nasa_se_synthetic_train.jsonl"
  val_path = data_root / "nasa_se_synthetic_val.jsonl"

  def _write(path: Path, items: List[DatasetExample]) -> None:
    with path.open("w", encoding="utf-8") as f:
      for ex in items:
        f.write(json.dumps(asdict(ex), ensure_ascii=False) + "\n")

  _write(train_path, train)
  _write(val_path, val)

  return train_path, val_path

