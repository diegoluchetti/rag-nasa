"""
Conversão PDF → Markdown via IBM Docling.
Preserva tabelas e hierarquia de títulos (# ## ###).
Processa em lotes de páginas para evitar std::bad_alloc (falta de RAM) em PDFs grandes.
Tarefa 1.1 - PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md
"""
import gc
import logging
import sys
from pathlib import Path

from .config_loader import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
LOG = logging.getLogger(__name__)


def _get_pdf_page_count(pdf_path: Path) -> int:
    """Retorna o número de páginas do PDF (via pypdf, sem carregar conteúdo)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        return len(reader.pages)
    except Exception as e:
        LOG.warning("Não foi possível obter número de páginas com pypdf: %s. Usando batch único.", e)
        return 0


def convert_pdf_to_markdown(
    pdf_path: str | Path,
    output_dir: str | Path,
    output_stem: str | None = None,
    table_format: str = "markdown",
    pdf_page_batch_size: int | None = 15,
) -> Path:
    """
    Converte um PDF para Markdown usando Docling.

    Para PDFs grandes (ex.: NASA SE Handbook 300+ páginas), processa em lotes de
    páginas para evitar std::bad_alloc (falta de RAM) no estágio preprocess do Docling.

    Args:
        pdf_path: Caminho do PDF (ex.: data/raw/NASA_SE_Handbook.pdf).
        output_dir: Diretório de saída (ex.: data/markdown).
        output_stem: Nome do arquivo de saída sem extensão. Se None, usa o stem do PDF.
        table_format: "markdown" ou "html". Docling exporta tabelas em Markdown por padrão.
        pdf_page_batch_size: Número de páginas por lote (ex.: 15). None = processar
            tudo de uma vez (pode dar bad_alloc em PDFs grandes).

    Returns:
        Caminho do arquivo .md gerado.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = output_stem or pdf_path.stem
    out_path = output_dir / f"{stem}.md"

    from docling.document_converter import DocumentConverter

    num_pages = _get_pdf_page_count(pdf_path)
    use_batches = pdf_page_batch_size and pdf_page_batch_size > 0 and num_pages > 0

    if use_batches and num_pages > pdf_page_batch_size:
        # Processar em lotes para reduzir uso de RAM (evita std::bad_alloc)
        # Docling usa page_range 1-based e inclusivo: (1, 5) = páginas 1 a 5
        # Novo converter por lote + gc para liberar memória entre lotes
        LOG.info(
            "Conversão em lotes de %s páginas (total: %s) para evitar falta de memória.",
            pdf_page_batch_size,
            num_pages,
        )
        md_parts: list[str] = []
        total_tables = 0
        start = 1  # 1-based
        batch_num = 0
        converter = DocumentConverter()
        while start <= num_pages:
            end = min(start + pdf_page_batch_size - 1, num_pages)  # inclusivo
            batch_num += 1
            LOG.info("Lote %s: páginas %s a %s", batch_num, start, end)
            try:
                result = converter.convert(str(pdf_path), page_range=(start, end))
                part = result.document.export_to_markdown()
                md_parts.append(part)
                if hasattr(result.document, "tables"):
                    total_tables += len(result.document.tables)
            except Exception as e:
                LOG.error("Falha no lote páginas %s-%s: %s", start, end, e)
                raise
            finally:
                gc.collect()
            start = end + 1
        md_content = "\n\n---\n\n".join(md_parts)
        num_tables = total_tables
    else:
        # PDF pequeno ou número de páginas desconhecido: processar de uma vez
        LOG.info("Iniciando conversão com Docling (documento inteiro): %s", pdf_path)
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        md_content = result.document.export_to_markdown()
        num_tables = len(result.document.tables) if hasattr(result.document, "tables") else 0

    if table_format == "html":
        LOG.warning("table_format=html solicitado; Docling exporta tabelas em Markdown por padrão.")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    LOG.info(
        "Conversão concluída. Saída: %s | Tabelas detectadas: %s",
        out_path,
        num_tables,
    )
    return out_path


def main() -> None:
    """Entrada por CLI: usa config e caminhos padrão."""
    config = load_config()
    paths = config.get("paths", {})
    ingestion = config.get("ingestion", {})
    table_format = ingestion.get("table_format", "markdown")
    pdf_page_batch_size = ingestion.get("pdf_page_batch_size", 15)

    raw_dir = Path(paths.get("data_raw", "data/raw"))
    md_dir = Path(paths.get("data_markdown", "data/markdown"))

    # Buscar primeiro PDF em data/raw
    pdfs = list(raw_dir.glob("*.pdf"))
    if not pdfs:
        LOG.error("Nenhum PDF encontrado em %s. Coloque o NASA SE Handbook em data/raw/.", raw_dir)
        sys.exit(1)

    pdf_path = pdfs[0]
    out_path = convert_pdf_to_markdown(
        pdf_path=pdf_path,
        output_dir=md_dir,
        output_stem=None,
        table_format=table_format,
        pdf_page_batch_size=pdf_page_batch_size,
    )
    print(f"Markdown salvo em: {out_path}")


if __name__ == "__main__":
    main()
