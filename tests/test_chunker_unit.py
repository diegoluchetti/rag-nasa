"""
Testes unitários para src.ingestion.hierarchy_aware_chunker.
"""
import json
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.hierarchy_aware_chunker import (
    chunk_markdown_file,
    save_chunks_to_jsonl,
    load_config_for_chunker,
    _split_into_blocks,
    _get_tokenizer,
    _count_tokens,
)


def test_split_into_blocks_single_header():
    md = "# Title\n\nSome content."
    blocks = _split_into_blocks(md)
    assert len(blocks) >= 1
    level, title, content, page = blocks[0]
    assert level == 1
    assert "Title" in title
    assert "Some content" in content
    assert page == 0  # sem marcador <!-- page N -->


def test_split_into_blocks_two_sections():
    md = "# A\n\nText A.\n\n## B\n\nText B."
    blocks = _split_into_blocks(md)
    assert len(blocks) >= 2
    _, t1, c1, _ = blocks[0]
    _, t2, c2, _ = blocks[1]
    assert "A" in t1 and "Text A" in c1
    assert "B" in t2 and "Text B" in c2


def test_split_into_blocks_appendix_style():
    md = "# Appendix C\n\n## C.1\n\nContent."
    blocks = _split_into_blocks(md)
    assert len(blocks) >= 1
    # Primeiro bloco pode ser (1, "Appendix C", ...) ou (2, "C.1", "Content.") conforme flush
    level, title, content, page = blocks[0]
    assert level >= 1
    assert "Appendix" in title or "C" in title or "C.1" in title
    assert isinstance(page, int)


def test_split_into_blocks_page_marker():
    """Marcador <!-- page N --> deve preencher page nos blocos (propagação FR-2.3.6)."""
    md = "\n\n<!-- page 5 -->\n\n# Section\n\nContent after page 5."
    blocks = _split_into_blocks(md)
    assert len(blocks) >= 1
    _, title, content, page = blocks[0]
    assert page == 5
    assert "Section" in title and "Content" in content


def test_chunk_markdown_file_has_page_paragraph_metadata(tmp_path):
    """Chunks devem ter page e paragraph em metadata quando há marcador de página."""
    md_file = tmp_path / "with_page.md"
    md_file.write_text(
        "\n\n<!-- page 3 -->\n\n# Sec\n\nShort text.",
        encoding="utf-8",
    )
    chunks = chunk_markdown_file(md_file, chunk_size=1000, chunk_overlap=0)
    assert len(chunks) >= 1
    meta = chunks[0]["metadata"]
    assert meta.get("page") == 3
    assert meta.get("paragraph") == 1


def test_get_tokenizer():
    enc = _get_tokenizer("cl100k_base")
    assert enc is not None


def test_count_tokens():
    enc = _get_tokenizer("cl100k_base")
    n = _count_tokens("Hello world", enc)
    assert n >= 2
    assert _count_tokens("", enc) == 0


def test_chunk_markdown_file_small(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("# Section 1\n\nShort text.\n\n## Section 2\n\nMore text.", encoding="utf-8")
    chunks = chunk_markdown_file(md_file, chunk_size=1000, chunk_overlap=0.15)
    assert len(chunks) >= 1
    for ch in chunks:
        assert "text" in ch
        assert "metadata" in ch
        meta = ch["metadata"]
        assert "section_title" in meta or "section_level" in meta
        assert "source_file" in meta
        assert meta["source_file"] == "test.md"


def test_chunk_markdown_file_respects_chunk_size(tmp_path):
    md_file = tmp_path / "big.md"
    # Conteúdo grande: muitas linhas para forçar mais de um chunk se chunk_size pequeno
    content = "# Big\n\n" + "\n\n".join([f"Paragraph {i} with some text." for i in range(200)])
    md_file.write_text(content, encoding="utf-8")
    chunks = chunk_markdown_file(md_file, chunk_size=50, chunk_overlap=0.1)
    assert len(chunks) >= 2


def test_save_chunks_to_jsonl(tmp_path):
    chunks = [
        {"text": "Hello", "metadata": {"section_title": "A", "section_level": 1}},
        {"text": "World", "metadata": {"section_title": "B", "section_level": 2}},
    ]
    out = tmp_path / "out.jsonl"
    save_chunks_to_jsonl(chunks, out)
    assert out.exists()
    lines = out.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    for line in lines:
        rec = json.loads(line)
        assert "text" in rec and "metadata" in rec


def test_load_config_for_chunker():
    chunk_size, overlap, encoding = load_config_for_chunker()
    assert chunk_size > 0
    assert 0 <= overlap <= 1
    assert encoding in ("cl100k_base", "cl100k")


def test_chunk_markdown_file_nonexistent_raises():
    with pytest.raises(FileNotFoundError):
        chunk_markdown_file(Path("/nonexistent/file_12345.md"))
