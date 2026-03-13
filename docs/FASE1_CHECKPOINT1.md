# Fase 1 — Ingestão Estruturada (Checkpoint 1)

## Objetivo

Converter o PDF do NASA Systems Engineering Handbook em Markdown fiel (tabelas e hierarquia) e em seguida em chunks que respeitam seções, para uso no RAG (Fase 2).

## Pré-requisitos

1. **Python 3.10+**
2. **PDF do Handbook** em `data/raw/`  
   - Nome esperado: qualquer `.pdf` (ex.: `NASA_SE_Handbook.pdf`).  
   - O script usa o primeiro PDF encontrado em `data/raw/` se nenhum for passado por argumento.

## Instalação (Fase 1)

```bash
cd c:\Users\Administrator\Documents\rag-nasa
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements-phase1.txt
```

## Uso

### Pipeline completo (PDF → Markdown → Chunks)

```bash
python run_ingestion.py
```

- Converte o primeiro PDF em `data/raw/` para Markdown em `data/markdown/`.
- Gera chunks em `data/chunks/<nome_do_pdf>_chunks.jsonl`.

### Especificar PDF

```bash
python run_ingestion.py --pdf path\to\handbook.pdf
```

### Só chunking (Markdown já existente)

```bash
python run_ingestion.py --markdown data\markdown\handbook.md
```

ou

```bash
python run_ingestion.py --no-docling
```

(usa o primeiro `.md` em `data/markdown/`.)

## Validação — Checkpoint 1

```bash
python -m pytest tests/test_checkpoint1.py -v
```

ou, sem pytest:

```bash
python tests/test_checkpoint1.py
```

**Critérios:**

1. Chunks possuem metadados de hierarquia (`section_title`, `section_level`).
2. Existe pelo menos um chunk contendo "Requirement Verification" ou "Verification Matrix", com tabela bem formada ou conteúdo relevante.
3. Nenhuma tabela truncada (colunas consistentes nas tabelas em Markdown).
4. Onde houver apêndice no documento, metadados de apêndice presentes.

Só avance para a **Fase 2** após o Checkpoint 1 ser aprovado.

## Estrutura gerada

- `data/raw/` — PDF(s) de entrada.
- `data/markdown/` — Um `.md` por documento convertido (Docling).
- `data/chunks/` — Um `.jsonl` por documento: cada linha é `{"text": "...", "metadata": {...}}`.

## Parâmetros (configs/default.yaml)

| Parâmetro               | Descrição                    | Sugerido   |
|-------------------------|------------------------------|------------|
| `chunk_size`            | Tamanho do chunk (tokens)    | 1000       |
| `chunk_overlap`         | Overlap entre chunks          | 0.15 (15%) |
| `table_format`          | Formato de tabela             | markdown   |
| `tokenizer_encoding`    | Encoding tiktoken             | cl100k_base |
| `pdf_page_batch_size`   | Páginas por lote na conversão Docling | 15  |

## Troubleshooting: `std::bad_alloc` no Docling

Se aparecer **`Stage preprocess failed for run 1, pages [N]: std::bad_alloc`**, é **falta de memória (RAM)** ao processar o PDF inteiro. O pipeline foi ajustado para:

1. **Processar o PDF em lotes de páginas** (ex.: 15 por vez), usando o parâmetro `pdf_page_batch_size` em `configs/default.yaml`.
2. Cada lote é convertido e o Markdown é concatenado; assim o uso de RAM não cresce com o tamanho do documento.

**Se ainda der erro de memória:** reduza o lote em `configs/default.yaml`, por exemplo:

```yaml
ingestion:
  pdf_page_batch_size: 10   # ou 8
```

Reinstale a dependência para contagem de páginas (usada para decidir os lotes):

```bash
pip install pypdf
```
