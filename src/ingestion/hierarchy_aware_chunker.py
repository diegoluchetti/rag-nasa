"""
Hierarchy Aware Chunker: divide Markdown em chunks que respeitam seções e tabelas.
Não corta no meio de subseções; usa chunk_size (tokens) e chunk_overlap (15%).
Tarefa 1.2 - PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md
"""
import json
import re
from pathlib import Path
from typing import Any

import tiktoken

from .config_loader import load_config


def _get_tokenizer(encoding: str = "cl100k_base") -> tiktoken.Encoding:
    try:
        return tiktoken.get_encoding(encoding)
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str, enc: tiktoken.Encoding) -> int:
    return len(enc.encode(text))


# Comentário HTML inserido por docling_to_markdown para propagação de página (FR-2.3.6)
PAGE_MARKER_RE = re.compile(r"^\s*<!--\s*page\s+(\d+)\s*-->\s*$", re.I)


def _split_into_blocks(md_text: str) -> list[tuple[int, str, str, int]]:
    """
    Divide o Markdown em blocos lógicos: (nível do título, título, conteúdo, página).
    Nível 0 = sem título (préâmbulo). Títulos #=1, ##=2, ###=3, ####=4.
    Reconhece marcadores <!-- page N --> (inseridos na conversão PDF→MD) para página.
    """
    blocks: list[tuple[int, str, str, int]] = []
    lines = md_text.split("\n")
    i = 0
    current_level = 0
    current_title = ""
    current_content: list[str] = []
    current_page = 0

    def flush(title: str, level: int, content: str, page: int) -> None:
        if content.strip():
            blocks.append((level, title, content.strip(), page))

    while i < len(lines):
        line = lines[i]
        page_match = PAGE_MARKER_RE.match(line.strip())
        if page_match:
            flush(current_title, current_level, "\n".join(current_content), current_page)
            current_page = int(page_match.group(1))
            current_content = []
            i += 1
            continue
        match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if match:
            flush(current_title, current_level, "\n".join(current_content), current_page)
            current_level = len(match.group(1))
            current_title = match.group(2).strip()
            current_content = []
            i += 1
            continue
        current_content.append(line)
        i += 1

    flush(current_title, current_level, "\n".join(current_content), current_page)
    return blocks


def _extract_table_blocks(text: str) -> list[tuple[int, int, str]]:
    """Retorna lista de (start_line, end_line, table_text) para cada tabela Markdown."""
    tables: list[tuple[int, int, str]] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and "|" in lines[i]:
            start = i
            table_lines = [lines[i]]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|") and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            tables.append((start, i - 1, "\n".join(table_lines)))
            continue
        i += 1
    return tables


def _split_block_by_paragraphs(content: str, max_tokens: int, enc: tiktoken.Encoding) -> list[str]:
    """Subdivide um bloco por parágrafos (duas quebras de linha) sem exceder max_tokens."""
    parts: list[str] = []
    paragraphs = re.split(r"\n\s*\n", content)
    current: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _count_tokens(para, enc)
        if para_tokens > max_tokens:
            # Parágrafo gigante: cortar por linha
            for line in para.split("\n"):
                line_tokens = _count_tokens(line, enc)
                if current_tokens + line_tokens > max_tokens and current:
                    parts.append("\n\n".join(current))
                    current = [line]
                    current_tokens = line_tokens
                else:
                    current.append(line)
                    current_tokens += line_tokens
            continue
        if current_tokens + para_tokens > max_tokens and current:
            parts.append("\n\n".join(current))
            current = [para]
            current_tokens = para_tokens
        else:
            current.append(para)
            current_tokens += para_tokens

    if current:
        parts.append("\n\n".join(current))
    return parts


def _ensure_overlap(
    chunks: list[dict[str, Any]],
    overlap_ratio: float,
    enc: tiktoken.Encoding,
) -> list[dict[str, Any]]:
    """
    Adiciona overlap entre chunks: os últimos overlap_ratio*token_count tokens
    do chunk N são repetidos no início do chunk N+1.
    """
    if overlap_ratio <= 0 or len(chunks) <= 1:
        return chunks
    result: list[dict[str, Any]] = []
    for i, ch in enumerate(chunks):
        text = ch["text"]
        tokens = enc.encode(text)
        if i == 0:
            result.append(ch)
            continue
        prev = result[-1]["text"]
        prev_tokens = enc.encode(prev)
        overlap_len = int(len(prev_tokens) * overlap_ratio)
        if overlap_len > 0 and len(prev_tokens) >= overlap_len:
            overlap_tokens = prev_tokens[-overlap_len:]
            overlap_text = enc.decode(overlap_tokens)
            new_text = overlap_text + "\n\n" + text
            result.append({**ch, "text": new_text})
        else:
            result.append(ch)
    return result


def chunk_markdown_file(
    md_path: str | Path,
    chunk_size: int = 1000,
    chunk_overlap: float = 0.15,
    tokenizer_encoding: str = "cl100k_base",
) -> list[dict[str, Any]]:
    """
    Lê um arquivo Markdown e retorna lista de chunks com metadados.

    Cada chunk é um dict: {"text": "...", "metadata": {"section_title", "section_level", "appendix", ...}}.

    - Respeita blocos por cabeçalho; não corta no meio de um título.
    - Blocos maiores que chunk_size são subdivididos por parágrafos.
    - Tabelas (blocos de linhas |...|) são mantidas inteiras dentro de um chunk quando possível.
    - Overlap de 15% entre chunks consecutivos.
    """
    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {md_path}")
    md_text = md_path.read_text(encoding="utf-8")
    enc = _get_tokenizer(tokenizer_encoding)
    blocks = _split_into_blocks(md_text)
    chunks: list[dict[str, Any]] = []
    chunk_id = 0

    for level, title, content, page in blocks:
        # Detectar apêndice (ex.: Appendix C, Apêndice C)
        is_appendix = bool(re.search(r"appendix\s+[a-z0-9]+", title, re.I))
        meta_base = {
            "section_title": title,
            "section_level": level,
            "appendix": is_appendix,
            "source_file": md_path.name,
            "page": page,
        }
        content_tokens = _count_tokens(content, enc)

        if content_tokens <= chunk_size:
            chunk_id += 1
            chunks.append({
                "id": chunk_id,
                "text": f"# {title}\n\n{content}" if title else content,
                "metadata": {**meta_base, "paragraph": 1},
            })
            continue

        # Subdividir por parágrafos; manter tabelas inteiras (não quebrar linhas que são |...|)
        sub_parts = _split_block_by_paragraphs(content, chunk_size, enc)
        for j, part in enumerate(sub_parts):
            chunk_id += 1
            header = f"# {title}\n\n" if title else ""
            chunks.append({
                "id": chunk_id,
                "text": header + part,
                "metadata": {**meta_base, "sub_section_index": j, "paragraph": j + 1},
            })

    # Aplicar overlap
    chunks = _ensure_overlap(chunks, chunk_overlap, enc)
    return chunks


def load_config_for_chunker() -> tuple[int, float, str]:
    """Retorna (chunk_size, chunk_overlap, tokenizer_encoding) do config."""
    config = load_config()
    ing = config.get("ingestion", {})
    return (
        int(ing.get("chunk_size", 1000)),
        float(ing.get("chunk_overlap", 0.15)),
        str(ing.get("tokenizer_encoding", "cl100k_base")),
    )


def save_chunks_to_jsonl(chunks: list[dict[str, Any]], out_path: str | Path) -> Path:
    """Salva chunks em JSONL: uma linha por chunk, campos "text" e "metadata"."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for ch in chunks:
            record = {"text": ch["text"], "metadata": ch.get("metadata", {})}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return out_path


def run_chunker_from_config(md_path: str | Path, chunks_out_path: str | Path | None = None) -> list[dict[str, Any]]:
    """
    Executa o chunker com parâmetros do config e opcionalmente salva em JSONL.
    """
    chunk_size, chunk_overlap, encoding = load_config_for_chunker()
    chunks = chunk_markdown_file(md_path, chunk_size=chunk_size, chunk_overlap=chunk_overlap, tokenizer_encoding=encoding)
    if chunks_out_path is not None:
        save_chunks_to_jsonl(chunks, chunks_out_path)
    return chunks
