"""
Executa uma query full-text no Neo4j e retorna os trechos recuperados (contexto).
Neo4j não requer API externa.
Uso (na raiz do projeto):
  python scripts/run_neo4j_query.py "Qual a diferença entre Verificação e Validação?"
  python scripts/run_neo4j_query.py "Sua pergunta" --log-dir log
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graphrag.query_engine import run_query


def main() -> None:
    parser = argparse.ArgumentParser(description="Query Neo4j (full-text nos chunks)")
    parser.add_argument("question", type=str, help="Pergunta ou termos de busca")
    parser.add_argument("--method", type=str, default=None, help="fulltext | by_section (default: da config)")
    parser.add_argument("--log-dir", type=str, default=None, help="Gravar log da query (ex.: log)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    log_dir = Path(args.log_dir) if args.log_dir else (PROJECT_ROOT / "log")

    try:
        response = run_query(
            question=args.question,
            method=args.method,
            log_dir=log_dir,
            verbose=args.verbose,
        )
        print(response)
    except RuntimeError as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
