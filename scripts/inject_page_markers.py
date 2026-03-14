"""
Injeta marcadores <!-- page N --> em um Markdown existente (heurística por tamanho).
Útil quando o MD foi gerado sem Docling em lotes (ex.: sem docling instalado).
Uso: python scripts/inject_page_markers.py [data/markdown/arquivo.md]
"""
import sys
from pathlib import Path

# raiz do projeto
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHARS_PER_PAGE = 4000  # heurística: ~1 página de texto


def inject_heuristic_page_markers(md_path: Path, chars_per_page: int = CHARS_PER_PAGE) -> None:
    """Lê o MD, insere <!-- page N --> a cada chars_per_page caracteres, salva no mesmo arquivo."""
    text = md_path.read_text(encoding="utf-8")
    if "<!-- page " in text:
        print(f"Arquivo já contém marcadores de página; nada a fazer: {md_path}")
        return
    parts: list[str] = []
    page = 1
    start = 0
    while start < len(text):
        end = min(start + chars_per_page, len(text))
        chunk = text[start:end]
        if page == 1 and not parts:
            chunk = "\n\n<!-- page 1 -->\n\n" + chunk.lstrip()
        else:
            chunk = f"\n\n<!-- page {page} -->\n\n" + chunk.lstrip()
        parts.append(chunk)
        page += 1
        start = end
    md_path.write_text("".join(parts), encoding="utf-8")
    print(f"Marcadores injetados: páginas 1 a {page - 1} (~{chars_per_page} chars/página). Salvo: {md_path}")


def main() -> None:
    if len(sys.argv) > 1:
        md_path = Path(sys.argv[1]).resolve()
    else:
        md_dir = ROOT / "data" / "markdown"
        mds = [f for f in md_dir.glob("*.md") if f.name != "test.md"]
        if not mds:
            print("Nenhum .md em data/markdown. Passe o caminho: python scripts/inject_page_markers.py <arquivo.md>")
            sys.exit(1)
        md_path = mds[0]
    if not md_path.exists():
        print(f"Arquivo não encontrado: {md_path}")
        sys.exit(1)
    inject_heuristic_page_markers(md_path)


if __name__ == "__main__":
    main()
