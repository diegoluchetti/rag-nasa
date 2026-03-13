"""
Prepara o input do GraphRAG a partir dos chunks da Fase 1 (data/chunks/*.jsonl).
Cria arquivos em graphrag_workspace/input/ conforme config (one_file_per_chunk ou single_file).
Uso (na raiz do projeto): python scripts/run_graphrag_prepare_input.py
"""
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graphrag.prepare_input import prepare_graphrag_input_from_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main() -> None:
    n = prepare_graphrag_input_from_config()
    print(f"Ok: {n} arquivo(s) de input gerado(s). Execute 'graphrag index' no workspace em seguida.")


if __name__ == "__main__":
    main()
