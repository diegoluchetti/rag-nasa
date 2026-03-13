"""
Carrega configs/default.yaml e resolve paths relativos à raiz do projeto.
Uso: from src.ingestion.config_loader import load_config, get_project_root
"""
from pathlib import Path
from typing import Any

import yaml


def get_project_root() -> Path:
    """Raiz do projeto (pasta que contém configs/)."""
    # Assume que este arquivo está em src/ingestion/
    current = Path(__file__).resolve()
    # subir: ingestion -> src -> raiz
    return current.parent.parent.parent


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    """Mescla override em base (in-place). Dicionários aninhados são mesclados."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def load_config(config_name: str = "default") -> dict[str, Any]:
    """Carrega configs/{config_name}.yaml e, se existir, configs/local.yaml (override). Resolve paths absolutos."""
    root = get_project_root()
    config_path = root / "configs" / f"{config_name}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config não encontrado: {config_path}")
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not config:
        config = {}
    # Override com configs/local.yaml (credenciais, etc.; não versionado)
    local_path = root / "configs" / "local.yaml"
    if local_path.exists():
        with open(local_path, encoding="utf-8") as f:
            local = yaml.safe_load(f)
        if local:
            _deep_merge(config, local)
    # Resolver paths
    if "paths" in config:
        for key, value in config["paths"].items():
            if isinstance(value, str) and not Path(value).is_absolute():
                config["paths"][key] = str(root / value)
    # Resolver paths do Neo4j (Fase 2) — system_prompt_path
    if "neo4j" in config:
        root_path = root
        if "system_prompt_path" in config["neo4j"] and isinstance(config["neo4j"].get("system_prompt_path"), str):
            p = config["neo4j"]["system_prompt_path"]
            if not Path(p).is_absolute():
                config["neo4j"]["system_prompt_path"] = str(root_path / p)
    return config


def get_path(config: dict[str, Any], path_key: str) -> Path:
    """Retorna Path absoluto para config['paths'][path_key]."""
    return Path(config["paths"][path_key])
