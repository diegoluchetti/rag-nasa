# Arquitetura implementada — até o fim do Checkpoint 1

## Visão geral

Foi implementada a **Fase 1 — Ingestão Estruturada** do [PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md](../PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md): preparação do ambiente, script Docling (PDF → Markdown), Hierarchy Aware Chunker (Markdown → chunks JSONL) e validação do Checkpoint 1.

---

## Estrutura de diretórios

```
rag-nasa/
├── configs/
│   └── default.yaml          # Parâmetros por fase (ingestion, rag, paths)
├── data/
│   ├── raw/                  # PDF do NASA SE Handbook
│   ├── markdown/             # Saída Docling (.md)
│   └── chunks/               # Chunks em JSONL
├── src/
│   ├── __init__.py
│   └── ingestion/
│       ├── __init__.py
│       ├── config_loader.py   # load_config(), get_project_root(), get_path()
│       ├── docling_to_markdown.py  # convert_pdf_to_markdown()
│       └── hierarchy_aware_chunker.py  # chunk_markdown_file(), save_chunks_to_jsonl()
├── tests/
│   ├── __init__.py
│   └── test_checkpoint1.py   # Validação formal do Checkpoint 1
├── docs/
│   ├── FASE1_CHECKPOINT1.md  # Instruções de uso Fase 1
│   └── ARQUITETURA_FASE1.md  # Este arquivo
├── run_ingestion.py          # Pipeline: PDF → MD → Chunks
├── requirements-phase1.txt  # docling, tiktoken, PyYAML
├── PROMPT_NASA_SE_AI_ASSISTANT.md
└── PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md
```

---

## Componentes

### 1. Configuração (`configs/default.yaml` + `src/ingestion/config_loader.py`)

- **default.yaml**: `ingestion` (chunk_size, chunk_overlap, table_format, tokenizer_encoding), `rag`, `dataset_gen`, `finetuning`, `paths`.
- **config_loader**: `load_config()` carrega o YAML e resolve `paths` para absolutos a partir da raiz do projeto; `get_project_root()` usa a localização de `config_loader.py` (src/ingestion).

### 2. Docling — PDF → Markdown (`src/ingestion/docling_to_markdown.py`)

- **Função**: `convert_pdf_to_markdown(pdf_path, output_dir, output_stem=None, table_format="markdown")`.
- **Detalhe**: Import do `DocumentConverter` é feito dentro da função (lazy) para que o resto do pacote funcione sem instalar o Docling (ex.: só chunker ou testes).
- **Saída**: Um arquivo `.md` em `data/markdown/` com tabelas e hierarquia (# ## ###) preservadas.
- **CLI**: `python run_ingestion.py` ou `python run_ingestion.py --pdf caminho.pdf`.

### 3. Hierarchy Aware Chunker (`src/ingestion/hierarchy_aware_chunker.py`)

- **Entrada**: Arquivo Markdown.
- **Lógica**:
  - `_split_into_blocks()`: divide por cabeçalhos (# a ####); cada bloco = (nível, título, conteúdo).
  - Blocos com mais de `chunk_size` tokens são subdivididos por parágrafos (`_split_block_by_paragraphs()`).
  - Overlap de 15% entre chunks consecutivos (`_ensure_overlap()`).
  - Metadados por chunk: `section_title`, `section_level`, `appendix` (detectado por regex), `source_file`.
- **Tokenização**: `tiktoken` com encoding configurável (padrão `cl100k_base`).
- **Saída**: Lista de dicts `{ "text", "metadata" }`; `save_chunks_to_jsonl()` grava em `data/chunks/<stem>_chunks.jsonl`.
- **Config**: `run_chunker_from_config(md_path, chunks_out_path)` lê chunk_size, chunk_overlap e tokenizer_encoding do `default.yaml`.

### 4. Pipeline de ingestão (`run_ingestion.py`)

- Carrega config, resolve `data/raw`, `data/markdown`, `data/chunks`.
- Se não for `--markdown` nem `--no-docling`: converte o primeiro PDF em `data/raw/` com Docling e grava em `data/markdown/`.
- Roda o chunker no Markdown (config) e salva o JSONL em `data/chunks/`.
- Uso: `python run_ingestion.py` | `--pdf file.pdf` | `--markdown file.md` | `--no-docling`.

### 5. Validação Checkpoint 1 (`tests/test_checkpoint1.py`)

- **Critérios**:
  1. Metadados de hierarquia em todos os chunks (`section_title`, `section_level`).
  2. Pelo menos um chunk com "Requirement Verification" ou "Verification Matrix" e tabela bem formada (ou conteúdo relevante).
  3. Tabelas não truncadas (colunas consistentes).
  4. Presença de metadados de apêndice quando o documento tem "Appendix" (section_title ou appendix=True).
- **Execução**: `python tests/test_checkpoint1.py` ou `pytest tests/test_checkpoint1.py -v`.
- **Entrada**: Primeiro `.jsonl` em `data/chunks/`; opcionalmente Markdown em `data/markdown/` para checar referência a Requirement Verification Matrix.

---

## Como rodar (resumo)

1. **Ambiente**:  
   `python -m venv .venv` → ativar → `pip install -r requirements-phase1.txt`

2. **Colocar o PDF** em `data/raw/` (ex.: NASA SE Handbook).

3. **Ingestão**:  
   `python run_ingestion.py`

4. **Validar Checkpoint 1**:  
   `python tests/test_checkpoint1.py`  
   Só seguir para a Fase 2 após o Checkpoint 1 ser aprovado.

---

## Próximos passos (Fase 2)

- Vector store (ChromaDB/LanceDB) com embeddings (nomic-embed-text ou bge-small-en-v1.5).
- Retriever Top-K=20 + Reranker bge-reranker-v2-m3 (Top-3).
- Prompt de sistema NASA e LLM com temperature=0.0.
- Métricas Hit Rate e MRR e pergunta “Verificação vs Validação”.
