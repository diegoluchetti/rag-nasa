"""
Testes do Checkpoint 2 (Fase 2 — grafo em Neo4j).
Verifica: config Neo4j, prompt NASA, ingestão (helper) e comportamento sem índice.
Não requer Neo4j rodando nem API (exceto testes que conectam ao banco).
"""
import sys
from pathlib import Path

import pytest

# Raiz do projeto
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_config_has_neo4j_section():
    from src.ingestion.config_loader import load_config
    config = load_config()
    assert "neo4j" in config
    g = config["neo4j"]
    assert g.get("uri")
    assert "database" in g  # pode ser "" para usar banco padrão do Aura
    assert g.get("default_query_method") in ("fulltext", "full_text", "by_section")


def test_nasa_system_prompt_loadable():
    from src.graphrag.query_engine import get_nasa_system_prompt
    prompt = get_nasa_system_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 50
    assert "NASA" in prompt or "Handbook" in prompt
    assert "Verification" in prompt or "Validation" in prompt or "Verificação" in prompt or "Validação" in prompt


def test_neo4j_ingest_chunks_helper():
    """neo4j_store usa _iter_chunks para ler chunks (mesma fonte que prepare_input)."""
    from src.graphrag.neo4j_store import _iter_chunks
    from src.ingestion.config_loader import load_config
    config = load_config()
    try:
        chunks = _iter_chunks(config)
        assert isinstance(chunks, list)
        if chunks:
            text, meta = chunks[0]
            assert isinstance(text, str)
            assert isinstance(meta, dict)
    except FileNotFoundError:
        pytest.skip("data/chunks/*.jsonl não encontrado (Fase 1 não rodou)")


def test_query_raises_when_index_missing():
    """ensure_index_exists deve levantar RuntimeError quando não há chunks no Neo4j."""
    from src.graphrag.query_engine import ensure_index_exists
    from unittest.mock import patch, MagicMock
    mock_driver = MagicMock()
    with patch("src.graphrag.query_engine.get_driver", return_value=mock_driver):
        with patch("src.graphrag.query_engine.get_chunk_count", return_value=0):
            with pytest.raises(RuntimeError) as exc_info:
                ensure_index_exists({"neo4j": {"uri": "bolt://localhost:7687", "database": "neo4j"}})
            msg = str(exc_info.value).lower()
            assert "chunk" in msg or "neo4j" in msg or "inger" in msg


def test_requirements_fase2_doc_exists():
    """Documento de requisitos Fase 2 existe e contém FR e NFR."""
    req_path = ROOT / "docs" / "REQUIREMENTS_FASE2.md"
    assert req_path.exists()
    text = req_path.read_text(encoding="utf-8")
    assert "FR-2.1.1" in text
    assert "NFR-2.1.1" in text
    assert "Neo4j" in text or "GraphRAG" in text


def test_format_hit_includes_page_paragraph_when_available():
    """_format_hit deve mencionar página e parágrafo quando presentes."""
    from src.graphrag.query_engine import _format_hit

    row = {
        "section_title": "3.1.1 Systems Engineering Overview",
        "text": "Some text",
        "page": 42,
        "paragraph": 3,
    }
    formatted = _format_hit(row, 1)
    assert "p.42" in formatted
    assert "parágrafo 3" in formatted
