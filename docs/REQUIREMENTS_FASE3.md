# Requisitos da Fase 3 — Geração de Dataset Sintético

> Requisitos funcionais (FR) e não funcionais (NFR) que detalham a arquitetura da Fase 3 do AI Systems Engineering Assistant. Entrada: chunks e/ou grafo da Fase 1/2; saída: dataset sintético de pares instrução/resposta para treino/avaliação.

---

## 1. Visão da Fase 3

A Fase 3 constrói um **dataset sintético** de exemplos de Engenharia de Sistemas (NASA SE) a partir do Handbook: pares **instrução/resposta** ancorados em contexto do manual, com metadados (seção, tipo de exemplo, dificuldade, tags). Esse dataset alimenta a Fase 4 (fine-tuning do SLM) e a Fase 5 (avaliação).

---

## 2. Requisitos Funcionais (FR)

### FR-3.1 Schema e estrutura dos exemplos

| ID       | Descrição | Critério de aceite |
|----------|-----------|---------------------|
| FR-3.1.1 | O sistema deve definir um schema explícito para cada exemplo. | Schema `DatasetExample` (dataclass/Pydantic) em `src/dataset_gen/schema.py` com campos: `id`, `instruction`, `response`, `difficulty`, `example_type`, `section_title`, `section_path`, `source_chunks`, `tags`, `notes` (opcional). |
| FR-3.1.2 | Cada exemplo gerado deve seguir o schema. | Todos os registros dos arquivos de dataset podem ser carregados em `DatasetExample` sem erro. |
| FR-3.1.3 | Cada exemplo deve conter, no mínimo, uma instrução, uma resposta e metadados básicos. | Campos `instruction`, `response`, `section_title` e `tags` não vazios. |

### FR-3.2 Fonte de contexto

| ID       | Descrição | Critério de aceite |
|----------|-----------|---------------------|
| FR-3.2.1 | O sistema deve usar como fonte de contexto os chunks da Fase 1. | Leitura de `data/chunks/*.jsonl` (via função em `src/dataset_gen/sampler.py`); cada linha com `text` e `metadata`. |
| FR-3.2.2 | Opcionalmente, o sistema pode usar o grafo Neo4j da Fase 2 para seleção de contexto. | Interface em `sampler.py` preparada para, futuramente, receber contextos via Neo4j (não obrigatório para o Checkpoint 3). |

### FR-3.3 Geração de exemplos

| ID       | Descrição | Critério de aceite |
|----------|-----------|---------------------|
| FR-3.3.1 | O sistema deve ser capaz de gerar exemplos de diferentes tipos. | Suporte a pelo menos 3 tipos (`example_type`): `qa`, `rewrite`, `critique` (perguntas/respostas, reescrita de requisitos, crítica/análise). |
| FR-3.3.2 | Cada exemplo deve estar ancorado em um contexto do Handbook. | Campo `source_chunks` com pelo menos um id de chunk; `section_title`/`section_path` refletem a origem. |
| FR-3.3.3 | O sistema deve gerar até `dataset_gen.num_pairs` exemplos válidos por execução. | Contagem final de exemplos aceitos (após filtros) ≤ `num_pairs`; tentativa de gerar exemplos até atingir esse limite ou exaurir o budget de contexto. |

### FR-3.4 Export e organização do dataset

| ID       | Descrição | Critério de aceite |
|----------|-----------|---------------------|
| FR-3.4.1 | O sistema deve salvar o dataset em formato JSONL. | Arquivos `data/datasets/nasa_se_synthetic_train.jsonl` e `data/datasets/nasa_se_synthetic_val.jsonl` gerados (ou caminhos configuráveis). |
| FR-3.4.2 | O dataset deve ser particionado em splits de treino e validação. | Split padrão 90/10 (`train`/`val`) ou valores configuráveis; cada exemplo pertence a exatamente um split. |
| FR-3.4.3 | Os arquivos devem ser auto-suficientes. | Cada linha JSON contém todos os campos necessários do `DatasetExample` (não depende de arquivos auxiliares para interpretação). |

### FR-3.5 Checkpoint 3 — Qualidade mínima

| ID       | Descrição | Critério de aceite |
|----------|-----------|---------------------|
| FR-3.5.1 | Deve existir um mínimo de exemplos gerados. | Pelo menos 100 exemplos válidos em conjunto (`train` + `val`) para o Checkpoint 3 inicial (meta futura: 1000). |
| FR-3.5.2 | O dataset deve cobrir tópicos principais do Handbook. | Pelo menos 1 exemplo por grupo de tópicos chave (ex.: requisitos, V&V, processos de SE, apêndices relevantes), medidos via tags. |
| FR-3.5.3 | O dataset não deve conter exemplos vazios ou triviais. | Nenhum exemplo com `instruction` ou `response` de comprimento inferior a um limite mínimo (ex.: 20 caracteres) após trimming. |

---

## 3. Requisitos Não Funcionais (NFR)

### NFR-3.1 Configuração e reprodutibilidade

| ID        | Descrição | Critério de aceite |
|-----------|-----------|---------------------|
| NFR-3.1.1 | A geração deve ser configurável via `configs/default.yaml`. | Seção `dataset_gen` inclui pelo menos: `num_pairs`, `seed`, `max_context_tokens`, `max_instruction_tokens`, `max_response_tokens`, `mix` (proporções por tipo). |
| NFR-3.1.2 | A geração deve ser reprodutível para um dado seed. | Com o mesmo `seed` e parâmetros, duas execuções produzem resultados estatisticamente semelhantes (dentro da estocasticidade do LLM) e idênticos quando se usa um LLM determinístico. |
| NFR-3.1.3 | O processo deve registrar estatísticas da geração. | Arquivo de métricas em `log/dataset_phase3_*.json` contendo: total gerado, total aceito, total descartado, distribuição por tags/dificuldade/exemplo. |

### NFR-3.2 Qualidade e segurança

| ID        | Descrição | Critério de aceite |
|-----------|-----------|---------------------|
| NFR-3.2.1 | As respostas não devem contradizer explicitamente o contexto. | Regras heurísticas em `postprocess.py` rejeitam exemplos onde a resposta não menciona termos-chave do contexto ou contém disclaimers genéricos (\"I cannot answer\", etc.). |
| NFR-3.2.2 | O dataset não deve vazar informações fora do Handbook. | Quando for usado um LLM externo, o prompt deve instruir a responder **apenas** com base no contexto fornecido. Exemplos que mencionem fontes externas claramente não relacionadas ao Handbook devem ser descartados. |

### NFR-3.3 Manutenibilidade

| ID        | Descrição | Critério de aceite |
|-----------|-----------|---------------------|
| NFR-3.3.1 | O código da Fase 3 deve ser modular. | Pacote `src/dataset_gen/` separado em módulos (`schema`, `sampler`, `generator`, `postprocess`, `export`) com preocupações claras. |
| NFR-3.3.2 | Deve existir documentação mínima da Fase 3. | Este arquivo (`REQUIREMENTS_FASE3.md`) e, opcionalmente, uma seção em `docs/ARQUITETURA_FASE1.md` ou documento próprio para arquitetura da Fase 3. |

---

## 4. Checkpoint 3 e verificação automática

- **Checkpoint 3:** Pelo menos 100 exemplos válidos gerados; estrutura conforme `DatasetExample`; cobertura mínima de tópicos; arquivos `train`/`val` presentes.
- Deve existir um teste automatizado (ex.: `tests/test_dataset_phase3.py`) que:
  - Verifica a existência dos arquivos de dataset (ou usa `pytest.skip` se a geração ainda não foi executada).
  - Carrega alguns exemplos e valida contra o schema.
  - Verifica contagens mínimas (quando arquivos presentes).

---

## 5. Resumo de IDs para o verificador

O script de verificação da Fase 3 (futuro) deve considerar pelo menos:

- **Funcionais:** FR-3.1.1, FR-3.1.2, FR-3.1.3, FR-3.2.1, FR-3.3.1, FR-3.3.2, FR-3.3.3, FR-3.4.1, FR-3.4.2, FR-3.4.3, FR-3.5.1, FR-3.5.2, FR-3.5.3.
- **Não funcionais:** NFR-3.1.1, NFR-3.1.2, NFR-3.1.3, NFR-3.2.1, NFR-3.2.2, NFR-3.3.1, NFR-3.3.2.

Cada item deve resultar em **PASS** ou **FAIL**. Pré-condições não atendidas (ex.: dataset ainda não gerado) são tratadas como **FAIL**; corrigir (ex.: rodar `run_dataset_gen.py`) e rodar o verificador novamente.

---

*Documento de requisitos da Fase 3 — Geração de Dataset Sintético. Referência: [PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md](../PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md).*

