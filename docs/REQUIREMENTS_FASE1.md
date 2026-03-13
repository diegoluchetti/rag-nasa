# Requisitos da Fase 1 — Ingestão Estruturada

> Requisitos funcionais (FR) e não funcionais (NFR) que detalham a arquitetura da Fase 1 do AI Systems Engineering Assistant (NASA SE Edition).

---

## 1. Visão da Fase 1

A Fase 1 converte o PDF do NASA Systems Engineering Handbook em Markdown de alta fidelidade (tabelas e hierarquia preservadas) e, em seguida, em chunks semânticos em JSONL, para alimentar o pipeline RAG da Fase 2.

---

## 2. Requisitos Funcionais (FR)

### FR-1.1 Conversão PDF → Markdown

| ID     | Descrição | Critério de aceite |
|--------|-----------|---------------------|
| FR-1.1 | O sistema deve converter um PDF de entrada em um único arquivo Markdown. | Um arquivo `.md` é gerado em `data/markdown/` com nome derivado do PDF (ex.: `{stem}.md`). |
| FR-1.2 | A conversão deve preservar a hierarquia de títulos do documento. | Títulos exportados com níveis Markdown (# ## ### ####) correspondentes à estrutura do PDF. |
| FR-1.3 | A conversão deve preservar tabelas no formato Markdown (ou configurável). | Tabelas presentes no PDF aparecem no Markdown como tabelas Markdown (`| ... |`) ou conforme `table_format` em config. |
| FR-1.4 | O sistema deve processar o PDF em lotes de páginas quando o documento for grande. | Parâmetro `page_range` (1-based, inclusivo) é usado; tamanho do lote configurável por `pdf_page_batch_size`. |
| FR-1.5 | O sistema deve obter o número de páginas do PDF antes da conversão. | Contagem de páginas via pypdf (ou equivalente) para definir os intervalos de lotes. |

### FR-2.1 Chunking hierarchy-aware

| ID     | Descrição | Critério de aceite |
|--------|-----------|---------------------|
| FR-2.1 | O sistema deve dividir o Markdown em chunks que respeitam seções (cabeçalhos). | Nenhum chunk deve cortar no meio de um título de seção; blocos são delimitados por # ## ### ####. |
| FR-2.2 | O tamanho dos chunks deve ser limitado em tokens. | Cada chunk (após overlap) não excede `chunk_size` tokens (configurável; padrão 1000). |
| FR-2.3 | Deve haver sobreposição configurável entre chunks consecutivos. | Overlap de `chunk_overlap` (ex.: 15%) aplicado entre chunk N e N+1. |
| FR-2.4 | Blocos maiores que `chunk_size` devem ser subdivididos por parágrafos. | Subdivisão por `\n\n`; tabelas mantidas inteiras quando possível. |
| FR-2.5 | Cada chunk deve ter metadados de hierarquia. | Presença de `section_title`, `section_level`, `source_file`; `appendix` quando o título indicar apêndice. |

### FR-3.1 Saída e integração

| ID     | Descrição | Critério de aceite |
|--------|-----------|---------------------|
| FR-3.1 | Os chunks devem ser persistidos em JSONL. | Um arquivo `{stem}_chunks.jsonl` em `data/chunks/`, uma linha por chunk com campos `text` e `metadata`. |
| FR-3.2 | O sistema deve usar configuração centralizada. | Parâmetros lidos de `configs/default.yaml` (paths, ingestion.chunk_size, ingestion.chunk_overlap, etc.). |
| FR-3.3 | O pipeline de ingestão deve poder ser executado por CLI. | Comando `python run_ingestion.py` executa PDF→Markdown→Chunks; opções `--pdf`, `--markdown`, `--no-docling`. |

### FR-4.1 Validação (Checkpoint 1)

| ID     | Descrição | Critério de aceite |
|--------|-----------|---------------------|
| FR-4.1 | Deve existir ao menos um chunk contendo "Requirement Verification" ou "Verification Matrix" com tabela bem formada ou conteúdo relevante. | Teste automatizado em `tests/test_checkpoint1.py` verifica presença e qualidade. |
| FR-4.2 | Chunks devem possuir metadados de hierarquia. | Todo chunk tem `section_title` ou `section_level` em `metadata`. |
| FR-4.3 | Tabelas não devem estar truncadas de forma grosseira. | Critério: falhar apenas se header tiver ≥4 colunas e todas as linhas de dados tiverem ≤2 colunas. |
| FR-4.4 | Onde o documento tiver apêndice, metadados de apêndice devem estar presentes. | Chunks de seções tipo "Appendix C" devem ter `appendix: true` ou `section_title` indicando apêndice. |

---

## 3. Requisitos Não Funcionais (NFR)

### NFR-1 Performance e recursos

| ID      | Descrição | Critério de aceite |
|---------|-----------|---------------------|
| NFR-1.1 | O processo de conversão não deve esgotar a RAM em máquinas com recursos limitados. | Uso de lotes de páginas e `gc.collect()` entre lotes; sem `std::bad_alloc` com `pdf_page_batch_size` configurado (ex.: 3). |
| NFR-1.2 | O tamanho do lote de páginas deve ser configurável. | Parâmetro `ingestion.pdf_page_batch_size` em `configs/default.yaml`; valor padrão adequado a ~8–16 GB RAM. |
| NFR-1.3 | A contagem de tokens deve usar encoding reproduzível. | Uso de tiktoken com encoding configurável (ex.: `cl100k_base`) para consistência com modelos downstream. |

### NFR-2 Confiabilidade e operação

| ID      | Descrição | Critério de aceite |
|---------|-----------|---------------------|
| NFR-2.1 | Paths devem ser resolvidos de forma absoluta a partir da raiz do projeto. | Carregamento de config resolve `paths` para caminhos absolutos; raiz inferida a partir da localização do módulo de config. |
| NFR-2.2 | O sistema deve funcionar sem Docling instalado para operações que não convertem PDF. | Import do Docling é lazy (dentro da função de conversão); chunker e testes podem rodar sem Docling. |
| NFR-2.3 | Saídas devem ser codificadas em UTF-8. | Arquivos Markdown e JSONL gravados com `encoding="utf-8"`. |

### NFR-3 Manutenibilidade e rastreabilidade

| ID      | Descrição | Critério de aceite |
|---------|-----------|---------------------|
| NFR-3.1 | Decisões de design devem estar documentadas. | Documento `docs/DESIGN_DECISIONS.md` com decisões (lotes, page_range, gc, critério de tabela truncada, etc.). |
| NFR-3.2 | Métricas da Fase 1 devem ser coletáveis e registradas. | Script ou processo que gera métricas (ex.: número de chunks, tamanho de arquivos, resultado do Checkpoint 1) e grava em `log/`. |
| NFR-3.3 | Testes unitários devem cobrir config e chunker. | Testes em `tests/test_config_loader.py` e `tests/test_chunker_unit.py`; resultados gravados em `log/` quando aplicável. |

### NFR-4 Usabilidade

| ID      | Descrição | Critério de aceite |
|---------|-----------|---------------------|
| NFR-4.1 | Documentação de uso da Fase 1 deve existir. | `docs/FASE1_CHECKPOINT1.md` com instruções de instalação, uso e troubleshooting (ex.: bad_alloc). |
| NFR-4.2 | Requisitos da Fase 1 devem estar explícitos. | Este documento (`docs/REQUIREMENTS_FASE1.md`) com FR e NFR listados e critérios de aceite. |

---

## 4. Arquitetura resumida (Fase 1)

```
[PDF em data/raw/]
        │
        ▼
  Docling (lotes de páginas; page_range 1-based)
        │
        ▼
[Markdown em data/markdown/]
        │
        ▼
  Hierarchy Aware Chunker (tiktoken, chunk_size, overlap)
        │
        ▼
[JSONL em data/chunks/]
        │
        ▼
  Checkpoint 1 (test_checkpoint1.py)
```

- **Config:** `configs/default.yaml` (ingestion, paths).
- **Componentes:** `src.ingestion.docling_to_markdown`, `src.ingestion.hierarchy_aware_chunker`, `src.ingestion.config_loader`.
- **Pipeline:** `run_ingestion.py`.
- **Validação:** `tests/test_checkpoint1.py`; métricas e resultados em `log/`.
- **Métricas e testes:** `python scripts/run_phase1_metrics.py` gera em `log/`: `metrics_phase1_*.json`, `checkpoint1_phase1_*.txt`, `pytest_phase1_*.xml`, `summary_phase1_*.txt`. Ver `log/README.md`.

---

## 5. Referências

- [PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md](../PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md)
- [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)
- [FASE1_CHECKPOINT1.md](FASE1_CHECKPOINT1.md)
- [ARQUITETURA_FASE1.md](ARQUITETURA_FASE1.md)
- [log/README.md](../log/README.md) — convenção de arquivos de métricas e testes em `log/`
