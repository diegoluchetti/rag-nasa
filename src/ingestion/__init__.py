# Fase 1 - Ingestão (Checkpoint 1)
from .config_loader import get_path, get_project_root, load_config
from .docling_to_markdown import convert_pdf_to_markdown
from .hierarchy_aware_chunker import (
    chunk_markdown_file,
    load_config_for_chunker,
    run_chunker_from_config,
    save_chunks_to_jsonl,
)

__all__ = [
    "load_config",
    "get_path",
    "get_project_root",
    "convert_pdf_to_markdown",
    "chunk_markdown_file",
    "load_config_for_chunker",
    "run_chunker_from_config",
    "save_chunks_to_jsonl",
]
