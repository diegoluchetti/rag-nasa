"""
Pipeline de ingestão Fase 1 (Checkpoint 1):
  1. PDF → Markdown (Docling)
  2. Markdown → Chunks (Hierarchy Aware Chunker)
  3. Salva chunks em data/chunks/*.jsonl

Uso (na raiz do projeto):
  python run_ingestion.py
  python run_ingestion.py --pdf path/to/file.pdf
  python run_ingestion.py --markdown path/to/file.md   # pula Docling, só chunka
"""
import argparse
import logging
import sys
from pathlib import Path

# Garantir que o projeto está no path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.ingestion.config_loader import load_config
from src.ingestion.docling_to_markdown import convert_pdf_to_markdown
from src.ingestion.hierarchy_aware_chunker import run_chunker_from_config, save_chunks_to_jsonl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
LOG = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestão Fase 1: PDF → Markdown → Chunks")
    parser.add_argument("--pdf", type=str, default=None, help="Caminho do PDF (senão usa primeiro PDF em data/raw)")
    parser.add_argument("--markdown", type=str, default=None, help="Se informado, pula Docling e só executa o chunker neste .md")
    parser.add_argument("--no-docling", action="store_true", help="Não rodar Docling; espera que o .md já exista em data/markdown")
    args = parser.parse_args()

    config = load_config()
    paths = config.get("paths", {})
    raw_dir = Path(paths.get("data_raw", "data/raw"))
    md_dir = Path(paths.get("data_markdown", "data/markdown"))
    chunks_dir = Path(paths.get("data_chunks", "data/chunks"))
    ingestion = config.get("ingestion", {})

    md_path: Path | None = None

    if args.markdown:
        md_path = Path(args.markdown)
        if not md_path.exists():
            LOG.error("Arquivo Markdown não encontrado: %s", md_path)
            sys.exit(1)
        LOG.info("Usando Markdown informado: %s", md_path)
    elif args.no_docling:
        md_files = list(md_dir.glob("*.md"))
        if not md_files:
            LOG.error("Nenhum .md em %s. Rode sem --no-docling ou informe --markdown.", md_dir)
            sys.exit(1)
        md_path = md_files[0]
        LOG.info("Usando Markdown existente: %s", md_path)
    else:
        pdf_path = args.pdf
        if not pdf_path:
            pdfs = list(raw_dir.glob("*.pdf"))
            if not pdfs:
                LOG.error("Nenhum PDF em %s. Coloque o NASA SE Handbook em data/raw/ ou use --pdf.", raw_dir)
                sys.exit(1)
            pdf_path = str(pdfs[0])
        else:
            pdf_path = str(Path(pdf_path).resolve())
        table_format = ingestion.get("table_format", "markdown")
        pdf_page_batch_size = ingestion.get("pdf_page_batch_size", 15)
        md_path = convert_pdf_to_markdown(
            pdf_path=pdf_path,
            output_dir=md_dir,
            output_stem=None,
            table_format=table_format,
            pdf_page_batch_size=pdf_page_batch_size,
        )

    chunks = run_chunker_from_config(md_path, chunks_out_path=None)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    out_name = md_path.stem + "_chunks.jsonl"
    out_path = chunks_dir / out_name
    save_chunks_to_jsonl(chunks, out_path)
    LOG.info("Chunks salvos: %s (total: %s)", out_path, len(chunks))
    print(f"Checkpoint 1 pipeline concluído. Markdown: {md_path} | Chunks: {out_path} ({len(chunks)} chunks)")


if __name__ == "__main__":
    main()
