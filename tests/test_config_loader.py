"""
Testes unitários para src.ingestion.config_loader.
"""
import pytest
from pathlib import Path

# Raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.config_loader import get_project_root, load_config, get_path


def test_get_project_root_returns_path():
    root = get_project_root()
    assert isinstance(root, Path)
    assert root.is_dir()
    assert (root / "configs").is_dir()
    assert (root / "src").is_dir()


def test_get_project_root_contains_configs():
    root = get_project_root()
    assert (root / "configs" / "default.yaml").exists()


def test_load_config_returns_dict():
    config = load_config()
    assert isinstance(config, dict)
    assert "ingestion" in config or "paths" in config


def test_load_config_ingestion_section():
    config = load_config()
    ing = config.get("ingestion", {})
    assert "chunk_size" in ing or "chunk_overlap" in ing or "pdf_page_batch_size" in ing


def test_load_config_paths_are_absolute():
    config = load_config()
    paths = config.get("paths", {})
    for key, value in paths.items():
        assert isinstance(value, str)
        assert Path(value).is_absolute() or key not in paths  # all path values should be absolute


def test_get_path_returns_path():
    config = load_config()
    p = get_path(config, "data_raw")
    assert isinstance(p, Path)
    assert "raw" in str(p).replace("\\", "/")


def test_load_config_nonexistent_raises():
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent_config_12345")
