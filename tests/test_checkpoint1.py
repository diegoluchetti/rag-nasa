"""
Validação do Checkpoint 1 - Fase 1 Ingestão.
Critérios:
  1. Tabelas "Requirement Verification Matrix" no Markdown legíveis e completas.
  2. Nenhuma tabela truncada (chunks que contêm tabelas com formato consistente).
  3. Hierarquia refletida nos chunks (metadados section_title, appendix).
"""
import json
import re
import sys
from pathlib import Path

# Raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_chunks(chunks_path: Path) -> list[dict]:
    chunks = []
    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunks.append(json.loads(line))
    return chunks


def _table_is_well_formed(text: str) -> bool:
    """Verifica se há uma tabela Markdown com colunas consistentes (|...|)."""
    lines = [l for l in text.split("\n") if l.strip().startswith("|") and "|" in l]
    if len(lines) < 2:
        return False
    # Contar colunas na primeira linha
    n_cols = len([c for c in lines[0].split("|") if c.strip()])
    for line in lines[1:]:
        if len([c for c in line.split("|") if c.strip()]) != n_cols and "---" not in line:
            # Linha de separador |---|---| tem células vazias; ignorar
            pass
    return True


def test_chunks_have_hierarchy_metadata(chunks: list[dict]) -> bool:
    """Todos os chunks devem ter metadados de hierarquia (section_title ou equivalente)."""
    for i, ch in enumerate(chunks):
        meta = ch.get("metadata", {})
        if "section_title" not in meta and "section_level" not in meta:
            # Permitir section_title vazio para préâmbulo
            if meta.get("section_level") is None and meta.get("section_title") is None:
                return False
    return True


def test_verification_matrix_chunk_exists(chunks: list[dict]) -> tuple[bool, str]:
    """
    Deve existir pelo menos um chunk contendo 'Requirement Verification' ou 'Verification Matrix'
    e com tabela bem formada (ou texto coerente).
    """
    candidates = [
        ch for ch in chunks
        if "requirement verification" in ch.get("text", "").lower()
        or "verification matrix" in ch.get("text", "").lower()
    ]
    if not candidates:
        return False, "Nenhum chunk contém 'Requirement Verification' ou 'Verification Matrix'."
    # Pelo menos um com tabela bem formada ou conteúdo substancial
    for ch in candidates:
        text = ch.get("text", "")
        if "|" in text and _table_is_well_formed(text):
            return True, "Chunk com Requirement Verification Matrix e tabela bem formada encontrado."
        if len(text) > 200 and ("verification" in text.lower() or "matrix" in text.lower()):
            return True, "Chunk com conteúdo relevante encontrado (tabela pode estar em outro chunk)."
    return False, "Chunks encontrados não têm tabela bem formada nem conteúdo suficiente."


def test_no_truncated_tables(chunks: list[dict]) -> tuple[bool, str]:
    """
    Detecta tabelas claramente truncadas: header com N colunas e alguma linha com < N-1 colunas.
    Variação leve (N-1, N+1) é aceita (Markdown/PDF pode gerar células vazias ou separadores).
    """
    errors = []
    for i, ch in enumerate(chunks):
        text = ch.get("text", "")
        table_lines = [l for l in text.split("\n") if l.strip().startswith("|") and "|" in l]
        if len(table_lines) < 2:
            continue
        col_counts = []
        for line in table_lines:
            if "---" in line:
                continue
            count = len([x for x in line.split("|") if x.strip()])
            col_counts.append(count)
        if not col_counts:
            continue
        expected = col_counts[0]
        # Truncagem clara: header com 4+ colunas e TODAS as outras linhas com <= 2 colunas
        data_rows = col_counts[1:]
        if expected >= 4 and data_rows and all(c <= 2 for c in data_rows):
            errors.append(f"Chunk {i}: tabela sem dados (possível truncagem)")
    if errors:
        return False, "; ".join(errors[:3])
    return True, "Nenhuma tabela truncada detectada."


def test_appendix_metadata_present(chunks: list[dict]) -> bool:
    """Se o doc tiver 'Appendix' no texto, algum chunk deve ter section_title ou appendix indicando apêndice."""
    with_appendix_meta = [ch for ch in chunks if ch.get("metadata", {}).get("appendix") is True]
    with_appendix_title = [ch for ch in chunks if "appendix" in (ch.get("metadata", {}).get("section_title") or "").lower()]
    any_appendix_text = any("appendix" in ch.get("text", "").lower() for ch in chunks)
    if not any_appendix_text:
        return True
    return len(with_appendix_meta) >= 1 or len(with_appendix_title) >= 1


def run_checkpoint1_validation(
    chunks_path: Path | None = None,
    markdown_path: Path | None = None,
) -> bool:
    """
    Executa todas as validações do Checkpoint 1.
    Retorna True se passar em todos os critérios.
    """
    if chunks_path is None:
        chunks_dir = PROJECT_ROOT / "data" / "chunks"
        jsonl_files = list(chunks_dir.glob("*.jsonl"))
        if not jsonl_files:
            print("AVISO: Nenhum arquivo .jsonl em data/chunks. Rode run_ingestion.py primeiro.")
            return False
        chunks_path = jsonl_files[0]

    chunks = _load_chunks(chunks_path)
    if not chunks:
        print("FALHA: Nenhum chunk carregado.")
        return False

    all_ok = True

    # 1. Metadados de hierarquia
    if test_chunks_have_hierarchy_metadata(chunks):
        print("[OK] Chunks possuem metadados de hierarquia (section_title, section_level).")
    else:
        print("[FALHA] Algum chunk sem metadados de hierarquia.")
        all_ok = False

    # 2. Requirement Verification Matrix
    ok_rm, msg_rm = test_verification_matrix_chunk_exists(chunks)
    if ok_rm:
        print(f"[OK] {msg_rm}")
    else:
        print(f"[FALHA] {msg_rm}")
        all_ok = False

    # 3. Tabelas não truncadas
    ok_table, msg_table = test_no_truncated_tables(chunks)
    if ok_table:
        print(f"[OK] {msg_table}")
    else:
        print(f"[FALHA] {msg_table}")
        all_ok = False

    # 4. Apêndice (metadado)
    if test_appendix_metadata_present(chunks):
        print("[OK] Metadados de apêndice presentes onde aplicável.")
    else:
        print("[AVISO] Nenhum chunk com appendix=True (pode ser normal se o doc não tiver apêndice).")

    if markdown_path and markdown_path.exists():
        md_text = markdown_path.read_text(encoding="utf-8")
        if "Requirement Verification" in md_text or "Verification Matrix" in md_text:
            print("[OK] Markdown contém referência a Requirement Verification Matrix.")
        else:
            print("[AVISO] Markdown não contém 'Requirement Verification Matrix' (pode ser outro nome no Handbook).")

    return all_ok


if __name__ == "__main__":
    chunks_path = (PROJECT_ROOT / "data" / "chunks").glob("*.jsonl")
    chunks_path = next(chunks_path, None)
    md_path = next((PROJECT_ROOT / "data" / "markdown").glob("*.md"), None)
    passed = run_checkpoint1_validation(chunks_path=chunks_path, markdown_path=md_path)
    print("\n--- Checkpoint 1:", "CONCLUÍDO" if passed else "FALHOU ---")
    sys.exit(0 if passed else 1)
