"""
Prepara o diretório de input do GraphRAG a partir dos chunks da Fase 1 (data/chunks/*.jsonl).
Suporta one_file_per_chunk ou single_file (config: graphrag.input_mode).
"""
import json
import logging
from pathlib import Path
from typing import Any

from src.ingestion.config_loader import load_config

LOG = logging.getLogger(__name__)

CHUNK_DELIMITER = "\n--- CHUNK ---\n"


def _chunks_source_dir(config: dict[str, Any]) -> Path:
    """Diretório onde estão os JSONL de chunks (Fase 1)."""
    paths = config.get("paths", {})
    chunks_dir = paths.get("data_chunks", "data/chunks")
    root = Path(__file__).resolve().parent.parent.parent
    p = Path(chunks_dir)
    if not p.is_absolute():
        p = root / chunks_dir
    return p


def _iter_chunks(config: dict[str, Any]) -> list[tuple[str, dict]]:
    """Lê todos os chunks de data/chunks/*.jsonl. Retorna lista de (text, metadata)."""
    chunks_dir = _chunks_source_dir(config)
    if not chunks_dir.exists():
        raise FileNotFoundError(f"Diretório de chunks não encontrado: {chunks_dir}")
    jsonl_files = sorted(chunks_dir.glob("*.jsonl"))
    if not jsonl_files:
        raise FileNotFoundError(f"Nenhum arquivo .jsonl em {chunks_dir}")
    out: list[tuple[str, dict]] = []
    for fp in jsonl_files:
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                text = obj.get("text", "")
                meta = obj.get("metadata", {})
                out.append((text, meta))
    return out


def prepare_graphrag_input(
    input_dir: Path,
    chunks: list[tuple[str, dict]],
    input_mode: str = "one_file_per_chunk",
    include_metadata_header: bool = True,
) -> int:
    """
    Escreve os chunks no diretório de input do GraphRAG.
    - one_file_per_chunk: um .txt por chunk (chunk_001.txt, ...).
    - single_file: um único handbook_full.txt com CHUNK_DELIMITER entre chunks.
    Retorna o número de arquivos escritos.
    """
    input_dir = Path(input_dir)
    input_dir.mkdir(parents=True, exist_ok=True)

    if input_mode == "single_file":
        parts = []
        for text, meta in chunks:
            if include_metadata_header and meta:
                header = " ".join(f"{k}={meta.get(k)}" for k in ("section_title", "section_level") if meta.get(k))
                if header:
                    parts.append(header + "\n" + text)
                else:
                    parts.append(text)
            else:
                parts.append(text)
        content = CHUNK_DELIMITER.join(parts)
        out_file = input_dir / "handbook_full.txt"
        out_file.write_text(content, encoding="utf-8")
        return 1

    # one_file_per_chunk
    count = 0
    for i, (text, meta) in enumerate(chunks, start=1):
        name = f"chunk_{i:03d}.txt"
        if include_metadata_header and meta:
            header = " ".join(f"{k}={meta.get(k)}" for k in ("section_title", "section_level") if meta.get(k))
            if header:
                content = header + "\n\n" + text
            else:
                content = text
        else:
            content = text
        (input_dir / name).write_text(content, encoding="utf-8")
        count += 1
    return count


def prepare_graphrag_input_from_config(config_name: str = "default") -> int:
    """
    Carrega config, lê chunks de data/chunks/*.jsonl e preenche graphrag_workspace/input.
    Retorna número de arquivos escritos.
    """
    config = load_config(config_name)
    graphrag = config.get("graphrag", {})
    input_dir_str = graphrag.get("input_dir")
    if not input_dir_str:
        raise ValueError("config graphrag.input_dir não definido")
    input_dir = Path(input_dir_str)
    input_mode = graphrag.get("input_mode", "one_file_per_chunk")

    chunks = _iter_chunks(config)
    if not chunks:
        raise ValueError("Nenhum chunk encontrado em data/chunks/*.jsonl")

    n = prepare_graphrag_input(
        input_dir=input_dir,
        chunks=chunks,
        input_mode=input_mode,
        include_metadata_header=True,
    )
    LOG.info("Preparação GraphRAG input: %s arquivos em %s (modo=%s)", n, input_dir, input_mode)
    return n
