"""
Executa uma query no índice GraphRAG e opcionalmente grava log em log/.
Uso (na raiz do projeto):
  python scripts/run_graphrag_query.py "Qual a diferença entre Verificação e Validação?"
  python scripts/run_graphrag_query.py "Quais são os principais processos de SE?" --method global
  python scripts/run_graphrag_query.py "Qual a diferença entre Verificação e Validação?" --log-dir log
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graphrag.query_engine import run_query


def main() -> None:
    parser = argparse.ArgumentParser(description="Query GraphRAG (global ou local)")
    parser.add_argument("question", type=str, help="Pergunta")
    parser.add_argument("--method", choices=("global", "local"), default=None, help="Método (default: da config)")
    parser.add_argument("--log-dir", type=str, default=None, help="Gravar log da query (ex.: log)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    log_dir = Path(args.log_dir) if args.log_dir else (PROJECT_ROOT / "log")
    if not args.log_dir:
        log_dir = None  # só gravar em log/ se --log-dir informado

    try:
        response = run_query(
            question=args.question,
            method=args.method,
            log_dir=log_dir or (PROJECT_ROOT / "log"),
            verbose=args.verbose,
        )
        print(response)
    except FileNotFoundError as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
