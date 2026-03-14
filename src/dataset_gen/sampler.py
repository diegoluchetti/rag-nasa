"""
Sampler da Fase 3: lê chunks da Fase 1 (JSONL) e gera contextos para geração de exemplos.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from src.ingestion.config_loader import load_config, get_path


@dataclass
class ContextSpec:
  """Contexto base para geração de exemplos."""

  id: str
  text: str
  section_title: str
  section_path: str
  source_chunks: List[str]
  tags: List[str]


def _load_all_chunks(config: Dict[str, Any]) -> List[Dict[str, Any]]:
  """Carrega todos os chunks de data/chunks/*.jsonl."""
  chunks_dir = get_path(config, "data_chunks")
  jsonl_files = sorted(chunks_dir.glob("*.jsonl"))
  if not jsonl_files:
    raise FileNotFoundError(f"Nenhum arquivo .jsonl em {chunks_dir}")

  chunks: List[Dict[str, Any]] = []
  for fp in jsonl_files:
    with fp.open(encoding="utf-8") as f:
      for line in f:
        line = line.strip()
        if not line:
          continue
        obj = json.loads(line)
        chunks.append(obj)
  return chunks


def sample_contexts_by_section(
  num_contexts: int,
  seed: int | None = None,
  config_name: str = "default",
) -> List[ContextSpec]:
  """
  Amostra contextos a partir de seções do Handbook.

  Estratégia simples:
  - Agrupa chunks por section_title.
  - Para cada seção, junta texto de 1–3 chunks consecutivos (quando houver).
  - Amostra até num_contexts contextos no total.
  """
  config = load_config(config_name)
  rng = random.Random(seed)
  chunks = _load_all_chunks(config)

  # Agrupar por section_title
  by_section: Dict[str, List[Dict[str, Any]]] = {}
  for ch in chunks:
    meta = ch.get("metadata", {})
    section = meta.get("section_title") or "Unknown"
    by_section.setdefault(section, []).append(ch)

  # Criar candidatos de ContextSpec por seção
  contexts: List[ContextSpec] = []
  for section_title, ch_list in by_section.items():
    if not ch_list:
      continue
    # Ordenar estavelmente por algum campo opcionalmente (não essencial aqui)
    for idx, ch in enumerate(ch_list):
      meta = ch.get("metadata", {})
      text = ch.get("text", "")
      if not text.strip():
        continue
      ctx_id = f"{section_title}_{idx}"
      section_path = section_title  # placeholder; pode ser enriquecido depois
      source_id = meta.get("id") or meta.get("chunk_id") or f"chunk_{idx}"
      tags: List[str] = []
      if "verification" in text.lower() or "validação" in text.lower() or "validation" in text.lower():
        tags.append("vv")
      if "shall" in text.lower():
        tags.append("requirements")

      contexts.append(
        ContextSpec(
          id=ctx_id,
          text=text,
          section_title=section_title,
          section_path=section_path,
          source_chunks=[str(source_id)],
          tags=tags,
        )
      )

  if not contexts:
    raise RuntimeError("Nenhum contexto elegível encontrado a partir dos chunks.")

  rng.shuffle(contexts)
  return contexts[:num_contexts]

