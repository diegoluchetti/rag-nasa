"""
Pós-processamento e filtros de qualidade para exemplos da Fase 3.

No estado atual, implementa apenas validações simples de comprimento
e campos obrigatórios.
"""
from __future__ import annotations

from typing import List

from src.dataset_gen.schema import DatasetExample


def is_valid_example(ex: DatasetExample, min_len: int = 20) -> bool:
  """Valida um exemplo de forma simples."""
  if not ex.instruction or not ex.response:
    return False
  if len(ex.instruction.strip()) < min_len:
    return False
  if len(ex.response.strip()) < min_len:
    return False
  if not ex.section_title:
    return False
  if not ex.tags:
    return False
  return True


def filter_examples(examples: List[DatasetExample], min_len: int = 20) -> List[DatasetExample]:
  """Filtra apenas exemplos válidos."""
  return [ex for ex in examples if is_valid_example(ex, min_len=min_len)]

