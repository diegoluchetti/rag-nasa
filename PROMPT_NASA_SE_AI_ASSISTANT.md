# Prompt Específico: AI Systems Engineering Assistant (NASA SE Edition)

> **Tipo**: Blueprint de Desenvolvimento / Especificação de Sistema  
> **Base de Conhecimento**: NASA Systems Engineering Handbook (SP-2016-6105-REV2)  
> **Objetivo**: Sistema de IA para Engenharia de Sistemas — parsing de alta fidelidade, recuperação (Neo4j) + LLM que pré-processa o contexto com **fontes preservadas** (Design Decision 19), e fine-tuning de SLM para entrega em **.gguf** e **.ipynb**, com foco em **escalabilidade e restrições financeiras** (evitar APIs pagas no fluxo final).

---

## 1. Visão Geral do Sistema

O **AI Systems Engineering Assistant**:

- Utiliza o **NASA Systems Engineering Handbook** como única fonte de verdade.
- **Fase 1:** Parsing de alta fidelidade (Docling → Markdown), chunker hierarchy-aware, **propagação de página/parágrafo** até a resposta.
- **Fase 2 (implementado):** Recuperação full-text no **Neo4j**; **LLM pequeno** pré-processa o contexto para resposta mais clara; **fontes (seção, página, parágrafo) são injetadas pela aplicação** (não geradas pelo LLM) para evitar alucinações. Modelo de processamento: pequeno (ex.: 4B–7B), local (Ollama).
- **Fase 3 (implementado):** Dataset sintético (pares instrução/resposta) para fine-tuning; geração via Ollama ou fallback sem LLM.
- **Fases 4–5 (objetivo final):** Fine-tuning do SLM (Unsloth/LoRA), **export para .gguf**, integração RAG-tuned, avaliação (métricas), e **entregáveis ao cliente: um notebook executável (.ipynb) e o modelo .gguf** para uso local, testável e mensurável, sem dependência de APIs pagas.

**Regras de ouro:**

1. Não avance de fase sem validar o checkpoint anterior.
2. Priorize **ferramentas locais e gratuitas** (Ollama, Neo4j community/Aura free, Unsloth) para manter custos controlados e solução escalável.
3. **Fontes de citação** (página, parágrafo, seção) vêm sempre dos metadados do retrieval; o LLM não gera nem altera referências (Design Decision 19).

---

## 2. Stack Tecnológica (atual e alvo)

| Componente        | Implementado / alvo                 | Observação                                      |
|-------------------|-------------------------------------|-------------------------------------------------|
| **Parsing**       | IBM Docling                         | PDF → Markdown; marcadores `<!-- page N -->`   |
| **Chunks**        | Hierarchy Aware Chunker             | JSONL com page, paragraph, section_title        |
| **Recuperação**   | **Neo4j** (full-text)               | Sem API paga; local ou Aura free                |
| **Resposta**      | **Ollama** (LLM pequeno, ex. 3B)    | Pré-processa contexto; fontes injetadas pela app |
| **Dataset (Fase 3)** | Ollama ou fallback               | Geração de pares para fine-tuning               |
| **Fine-Tuning**   | Unsloth (Llama/Qwen 3B)             | LoRA/QLoRA; export para **.gguf**               |
| **Entregáveis**   | **.ipynb + .gguf**                  | Cliente: notebook + modelo para uso local      |
| *(Alternativas)* | ChromaDB/LanceDB + reranker         | Opcional para variante com busca semântica      |

---

## 3. Fase 1 — Ingestão Estruturada (Checkpoint 1)

**Objetivo:** Converter o PDF da NASA em um formato que a IA “entenda” perfeitamente (Markdown estruturado, tabelas e seções preservadas).

### Tarefa 1.1 — Script Docling

- Implementar script que usa **Docling** para converter o PDF do Handbook para **Markdown**.
- Garantir que **tabelas** e **hierarquia de títulos** (H1, H2, H3, etc.) sejam extraídas com alta fidelidade.
- Definir **table_format** configurável: **Markdown** vs **HTML** — testar qual o LLM entende melhor em downstream.

### Tarefa 1.2 — Hierarchy Aware Chunker

- Criar um **“Hierarchy Aware Chunker”** que respeite as seções do documento.
- Exemplo: **Apêndice C** deve ser tratado como bloco coeso quando fizer sentido (não cortar no meio de subseções críticas).
- Parâmetros ajustáveis:
  - `chunk_size`: sugerido **1000 tokens**
  - `chunk_overlap`: sugerido **15%**
  - `table_format`: Markdown ou HTML (conforme teste)

### Métricas Ajustáveis (Fase 1)

```yaml
chunk_size: 1000        # tokens
chunk_overlap: 0.15     # 15%
table_format: markdown  # ou html
```

### Checkpoint 1 — Critério de Validação

- [ ] As tabelas de **“Requirement Verification Matrix”** no Markdown gerado estão **legíveis e completas**.
- [ ] Nenhuma tabela truncada ou coluna perdida.
- [ ] Hierarquia de seções (ex.: Apêndice C) refletida nos chunks.

**Não avance para a Fase 2 sem cumprir o Checkpoint 1.**

---

## 4. Fase 2 — Query: Neo4j + LLM com fontes intactas (Checkpoint 2) ✅ Implementado

**Objetivo:** Recuperar trechos relevantes (full-text Neo4j) e produzir uma resposta clara usando um **LLM pequeno** que **pré-processa** o contexto, com a **informação de fonte (seção, página, parágrafo) preservada e injetada pela aplicação** (Design Decision 19 — evita alucinações em citações).

### Implementado

- **Recuperação:** Neo4j com índice full-text nos chunks (sem API paga; local ou Aura free). Top-K configurável.
- **LLM (pré-processamento):** Envio ao modelo apenas do **texto** dos trechos (sem metadados de fonte). O LLM devolve prosa/resumo; a aplicação monta a seção **Fontes** com os metadados exatos do retrieval (section_title, page, paragraph). Modelo pequeno (ex.: 3B–7B) via Ollama.
- **Prompt de sistema NASA:** Em `configs/prompts_nasa_system.txt`; instrui a responder apenas com base no contexto e a não inventar fontes (as referências são adicionadas automaticamente).
- **Métricas:** Conjunto gold (`data/phase2_gold_questions.json`); Hit Rate e MRR computados e registrados em `log/`. Verificador de requisitos (PASS/FAIL) para validar o Checkpoint 2.

### Métricas Ajustáveis (Fase 2)

```yaml
neo4j.top_k: 5
neo4j.use_llm_for_response: true
neo4j.llm_model: "qwen2.5:3b"
neo4j.ollama_url: "http://localhost:11434"
temperature: 0.0
```

### Checkpoint 2 — Critério de Validação

- [ ] Hit Rate e MRR computados a partir do conjunto gold.
- [ ] Resposta para **“Qual a diferença entre Verificação e Validação?”** alinhada ao Handbook; fontes exibidas são as do retrieval (não geradas pelo LLM).
- [ ] Verificador Fase 2: todos os itens PASS (sem SKIP; pré-condições não atendidas = FAIL).

---

## 5. Fase 3 — Geração de Dataset Sintético (Checkpoint 3) ✅ Implementado

**Objetivo:** Produzir pares Instrução/Resposta para **Fine-Tuning** do SLM; formato JSONL (train/val); geração via LLM (Ollama) ou **fallback sem LLM** (para rodar sem custo de API).

### Implementado

- **Pacote** `src/dataset_gen/`: schema (DatasetExample), sampler (chunks por seção), generator (Ollama ou fallback sintético), postprocess, export. Config: `dataset_gen.num_pairs`, `seed`, **`use_llm`** (true = Ollama; false = fallback).
- **Saída:** `data/datasets/nasa_se_synthetic_train.jsonl` e `_val.jsonl` (split 90/10). Métricas em `log/dataset_phase3_*.json`.
- **Tipos de exemplo:** qa, rewrite, critique (compatível com diversidade: requisitos, processos, Verification vs Validation).
- **Verificador Fase 3:** PASS/FAIL (schema, arquivos, ≥100 exemplos, cobertura por tags).

### Checkpoint 3 — Critério de Validação

- [ ] Dataset gerado com ≥100 exemplos válidos; train e val presentes.
- [ ] Verificador Fase 3: todos os itens PASS.
- [ ] Revisão manual de amostras recomendada (lógica de engenharia, formato NASA).

---

## 6. Fase 4 — Fine-Tuning do SLM (Checkpoint 4)

**Objetivo:** Ensinar o “dialeto” NASA ao modelo pequeno (ex.: **Llama 3.2 3B**).

### Tarefa 4.1 — Unsloth SFT

- Configurar **Unsloth** para **Supervised Fine-Tuning (SFT)**.
- Base: **Llama 3.2 3B** ou **Qwen 2.5 3B** (3B preferido com 8–12GB VRAM; 1B se restrição de memória).

### Tarefa 4.2 — LoRA/QLoRA

- Aplicar **LoRA** ou **QLoRA** para eficiência de memória.
- Parâmetros sugeridos:

```yaml
learning_rate: 2e-4
epochs: 3
lora_rank: 16          # ou 32
lora_alpha: 32
target_modules:
  - q_proj
  - k_proj
  - v_proj
  - o_proj
```

### Checkpoint 4 — Critério de Validação

- [ ] Plotar **curva de Loss** (treino/validação).
- [ ] **Teste comparativo:** Modelo Base vs Modelo Tunado.
- [ ] O modelo **tunado** deve seguir **melhor** o formato de requisitos da NASA (Shall, estrutura, terminologia).

**Não avance para a Fase 5 sem cumprir o Checkpoint 4.**

---

## 7. Fase 5 — Integração Final, Avaliação e Entregáveis

**Objetivo:** Pipeline **RAG-tuned** (recuperação + modelo fine-tunado em .gguf), avaliado e **entregue ao cliente** em formato **escalável e com restrições de custo** (uso local, sem APIs pagas no fluxo final).

### Tarefa 5.1 — Avaliação

- Métricas: **Hit Rate**, **MRR** (Fase 2); **Faithfulness**, **Answer Relevance**, **Context Precision** (RAGAS ou equivalentes) para o pipeline final.
- Objetivo: modelo treinado **testável e mensurável**; resultados documentados (relatório ou células no .ipynb).

### Entregáveis Finais (cliente)

- **Notebook (.ipynb):** Um Jupyter notebook executável que documenta e executa o fluxo: carregar modelo .gguf (Ollama/llama.cpp), rodar perguntas de exemplo, exibir resposta e fontes, e opcionalmente células de avaliação. Reproduzível **sem custo de API**.
- **Modelo (.gguf):** Arquivo do LLM fine-tunado para inferência local (Ollama, llama.cpp), entregue junto ao projeto.
- **Relatório de métricas** (Hit Rate, MRR, Faithfulness, Answer Relevance, Context Precision) em `docs/` ou integrado ao .ipynb.
- **Documentação** de como executar o .ipynb e usar o .gguf; arquitetura pensada para **escalabilidade** e **restrições financeiras** (ferramentas locais/gratuitas quando possível).

---

## 8. Resumo dos Checkpoints e Ordem de Execução

| Ordem | Fase   | Checkpoint / Entregável                                                |
|-------|--------|-------------------------------------------------------------------------|
| 1     | Fase 1 | Tabelas legíveis no MD; chunks com page/paragraph; Checkpoint 1 ✅       |
| 2     | Fase 2 | Neo4j + LLM (fontes injetadas); Hit Rate/MRR; verificador PASS ✅       |
| 3     | Fase 3 | Dataset train/val JSONL; ≥100 exemplos; verificador PASS ✅              |
| 4     | Fase 4 | Fine-tuning (Unsloth/LoRA); curva de loss; **export para .gguf**         |
| 5     | Fase 5 | RAG-tuned; métricas; **entregáveis: .ipynb + modelo .gguf** para cliente |

---

## 9. Prompt de Sistema (Persona NASA)

O texto em **`configs/prompts_nasa_system.txt`** é usado como system prompt quando o LLM pré-processa o contexto (Fase 2). A aplicação **não** pede ao modelo para gerar citações de fonte; as referências (seção, página, parágrafo) são **injetadas** a partir dos metadados do retrieval (Design Decision 19).

**Guardrails:** Todas as regras de comportamento do system prompt estão mapeadas e detalhadas em **`docs/GUARDRAILS_SYSTEM_PROMPT.md`** (IDs G1–G7, rationale, enforcement no prompt vs. na aplicação). Use esse documento como referência única ao alterar ou estender o prompt.

```text
You are an expert Systems Engineering Assistant trained on the NASA Systems Engineering Handbook (SP-2016-6105-REV2). Your role is to answer questions strictly based on the provided context from the Handbook. Use NASA terminology: "shall" statements for requirements, distinguish clearly between Verification and Validation, and refer to processes by their official names and inputs/outputs. If the context does not contain enough information, say so. Do not invent definitions or procedures. Do not invent or generate source references (page, section); they will be added automatically.
```

---

## 10. Restrições Financeiras e Escalabilidade

- **Preferir:** Neo4j (local ou Aura free), Ollama (modelos locais), Unsloth (fine-tuning local), dataset gerado com fallback sem LLM. Evitar APIs pagas (OpenAI, etc.) no fluxo de produção e no entregável ao cliente.
- **Entregável final:** Cliente recebe **.ipynb** (notebook executável) e **.gguf** (modelo para inferência local). Uso sem custo por chamada; escalável em ambiente controlado.

---

## 11. Referências Rápidas

- **NASA SE Handbook:** SP-2016-6105-REV2 (PDF).
- **Docling:** IBM Docling para PDF → Markdown.
- **Neo4j:** Full-text search; sem API externa paga.
- **Ollama:** Inferência local (modelos pequenos para processamento e dataset).
- **Unsloth:** Fine-tuning; export para .gguf.
- **RAGAS:** Avaliação RAG (Faithfulness, Answer Relevance, Context Precision).
- **Design Decision 19:** LLM pré-processa contexto; fontes injetadas pela aplicação (`docs/DESIGN_DECISIONS.md`).
- **Guardrails do system prompt:** Mapeamento completo em `docs/GUARDRAILS_SYSTEM_PROMPT.md`.

---

*Documento alinhado ao estado atual da implementação (Fases 1–3 e motor de query). Fases 4–5 mantêm o objetivo: modelo fine-tunado testável e mensurável, entregue como .ipynb + .gguf.*
