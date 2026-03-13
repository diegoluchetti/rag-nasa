"""
Executa a indexação GraphRAG no workspace (graphrag index).
Requer: (1) input já preparado (scripts/run_graphrag_prepare_input.py), (2) graphrag instalado, (3) .env com API key.
Uso (na raiz do projeto): python scripts/run_graphrag_index.py [--dry-run]
"""
import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.config_loader import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa graphrag index no workspace")
    parser.add_argument("--dry-run", action="store_true", help="Só valida config, não executa")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
    args = parser.parse_args()

    config = load_config()
    graphrag = config.get("graphrag", {})
    workspace_dir = graphrag.get("workspace_dir")
    if not workspace_dir:
        print("Erro: graphrag.workspace_dir não definido em configs/default.yaml", file=sys.stderr)
        sys.exit(1)
    root = Path(workspace_dir)
    if not root.is_absolute():
        root = PROJECT_ROOT / workspace_dir
    if not root.exists():
        print(f"Erro: workspace não existe: {root}", file=sys.stderr)
        sys.exit(1)

    cmd = ["graphrag", "index", "--root", str(root)]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.verbose:
        cmd.append("--verbose")

    print(f"Executando: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)
    print("Indexação concluída. Saída em", root / "output")


if __name__ == "__main__":
    main()
