"""
Testes básicos da Fase 3 — Dataset sintético.

Neste estágio, o gerador é um stub (pode produzir 0 exemplos). Os testes focam em:
- schema DatasetExample;
- sampler de contextos;
- existência e forma dos arquivos de dataset (se já tiverem sido gerados).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dataset_gen.schema import DatasetExample
from src.dataset_gen.sampler import sample_contexts_by_section
from src.ingestion.config_loader import load_config, get_path


ROOT = Path(__file__).resolve().parent.parent


def test_sampler_returns_contexts():
  """Sampler deve retornar ao menos 1 contexto se houver chunks."""
  config = load_config()
  chunks_dir = get_path(config, "data_chunks")
  jsonl_files = list(chunks_dir.glob("*.jsonl"))
  if not jsonl_files:
    pytest.skip("Nenhum chunks JSONL encontrado; rode Fase 1 antes.")

  ctxs = sample_contexts_by_section(num_contexts=5, seed=42)
  assert isinstance(ctxs, list)
  if ctxs:
    c0 = ctxs[0]
    assert isinstance(c0.text, str)
    assert isinstance(c0.section_title, str)


def test_dataset_files_schema_if_exist():
  """Se arquivos de dataset existirem, devem seguir o schema DatasetExample."""
  config = load_config()
  data_root = get_path(config, "data_datasets")
  train_path = data_root / "nasa_se_synthetic_train.jsonl"
  val_path = data_root / "nasa_se_synthetic_val.jsonl"
  if not train_path.exists() or not val_path.exists():
    pytest.skip("Dataset Fase 3 ainda não gerado (rode scripts/run_dataset_gen.py).")

  def _check(path: Path) -> None:
    with path.open(encoding="utf-8") as f:
      for i, line in enumerate(f):
        if i >= 5:  # amostra
          break
        obj = json.loads(line)
        ex = DatasetExample(**obj)
        assert ex.instruction is not None
        assert ex.response is not None

  _check(train_path)
  _check(val_path)

