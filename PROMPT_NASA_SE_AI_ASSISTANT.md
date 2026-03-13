# Prompt Específico: AI Systems Engineering Assistant (NASA SE Edition)

> **Tipo**: Blueprint de Desenvolvimento / Especificação de Sistema  
> **Base de Conhecimento**: NASA Systems Engineering Handbook (SP-2016-6105-REV2)  
> **Objetivo**: Sistema de IA de elite para Engenharia de Sistemas — parsing de alta fidelidade, RAG com reranking e fine-tuning de SLM para escrita de requisitos e análise de processos.

---

## 1. Visão Geral do Sistema

Você está desenvolvendo um **AI Systems Engineering Assistant** que:

- Utiliza o **NASA Systems Engineering Handbook** como única fonte de verdade.
- Garante **parsing de alta fidelidade** (tabelas e hierarquia preservadas).
- Oferece **recuperação precisa** via RAG com reranking.
- Possui um **modelo especializado** (SLM fine-tunado) no “dialeto” NASA para requisitos e processos.

**Regras de ouro para o desenvolvedor:**

1. **Não avance de fase sem validar o checkpoint anterior.** Comece pela Fase 1 e valide o output do Docling antes de prosseguir.
2. **Priorize o modelo de 3B parâmetros** no fine-tuning se houver VRAM disponível (mínimo 8GB–12GB); caso contrário use 1B.
3. Use **LangSmith ou ferramentas de log** para rastrear cada chamada do RAG e identificar onde o Reranker filtra informações críticas.

---

## 2. Stack Tecnológica Obrigatória

| Componente        | Tecnologia                          | Observação                                      |
|-------------------|-------------------------------------|-------------------------------------------------|
| **Parsing**       | IBM Docling                         | Extração de tabelas e hierarquia em Markdown   |
| **Vetorização**   | nomic-embed-text ou bge-small-en-v1.5 | Embeddings para busca semântica               |
| **Banco Vetorial**| ChromaDB ou LanceDB                 | Persistência de vetores                        |
| **Reranker**      | BAAI/bge-reranker-v2-m3            | Cross-encoder para Top-K → Top-N               |
| **Orquestração**  | LangChain ou LlamaIndex             | Pipeline RAG e encadeamento                     |
| **Fine-Tuning**   | Unsloth                             | Llama 3.2 3B ou Qwen 2.5 3B                    |
| **Dados**         | NASA SE Handbook (SP-2016-6105-REV2)| PDF oficial                                    |

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

## 4. Fase 2 — RAG Avançado com Reranking (Checkpoint 2)

**Objetivo:** Garantir que o sistema encontre a **informação exata** entre 300+ páginas (recuperação + reranking).

### Tarefa 2.1 — Vector Store e Busca Semântica

- Configurar **Vector Store** (ChromaDB ou LanceDB) com os chunks da Fase 1.
- Usar embeddings: **nomic-embed-text** ou **bge-small-en-v1.5**.
- Busca semântica com **Top-K: 20** candidatos.

### Tarefa 2.2 — Cross-Encoder Reranker

- Integrar **BAAI/bge-reranker-v2-m3** como cross-encoder.
- Fluxo: **Top-20** (busca vetorial) → Reranker → **Top-3** (ou Top-N configurável) mais relevantes.
- Opcional: aplicar **rerank_threshold** (sugerido **0.7**) para filtrar por score.

### Tarefa 2.3 — Prompt de Sistema (Persona NASA)

- Implementar **prompt de sistema** especializado em **Engenharia de Sistemas**, tom de voz **NASA**:
  - Responder com base **apenas** no Handbook (sem alucinar).
  - Usar terminologia e estrutura de requisitos (“Shall statements”, Verification/Validation, etc.).
  - Citar seções ou apêndices quando relevante.

### Métricas Ajustáveis (Fase 2)

```yaml
top_k_retrieval: 20
top_n_rerank: 3        # ou 5
rerank_threshold: 0.7
temperature: 0.0       # precisão técnica
```

### Checkpoint 2 — Critério de Validação

- [ ] Medir **Hit Rate** e **MRR** (Mean Reciprocal Rank) em um conjunto de perguntas de teste.
- [ ] A resposta para **“Qual a diferença entre Verificação e Validação?”** deve ser **perfeita** (alinhada ao Handbook, sem invenção).

**Não avance para a Fase 3 sem cumprir o Checkpoint 2.**

---

## 5. Fase 3 — Geração de Dataset Sintético (Checkpoint 3)

**Objetivo:** Preparar dados para **Fine-Tuning** do SLM — pares Instrução/Resposta de alta qualidade.

### Tarefa 3.1 — Geração de Pares Instrução/Resposta

- Usar o **Markdown do Docling** (com foco em **Apêndice C** e seções de **Processos**) para gerar **1.000 pares** de Instrução/Resposta.

### Tarefa 3.2 — Foco do Dataset

- **Transformação de requisitos:** requisitos ambíguos → requisitos no padrão NASA (**Shall statements**).
- **Explicação de processos:** diagramas de entrada/saída de processos de SE (inputs, outputs, atividades).
- Garantir **diversidade**: checklists, definições, correções de redação, exemplos de Verification vs Validation.

### Métricas de Qualidade

- Diversidade de exemplos (checklists, definições, correções).
- Formato **JSONL** compatível com **Unsloth/HuggingFace** (campos: `instruction`, `output` ou equivalente).

### Checkpoint 3 — Critério de Validação

- [ ] **Revisão manual de 20 amostras** do dataset.
- [ ] A **lógica de engenharia** está correta? O formato NASA está sendo respeitado?

**Não avance para a Fase 4 sem cumprir o Checkpoint 3.**

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

## 7. Fase 5 — Integração Final e Avaliação

**Objetivo:** Otimizar o pipeline **“RAG-tuned”** (RAG + modelo fine-tunado) e medir performance com métricas padrão.

### Tarefa 5.1 — Avaliação com RAGAS

Comparar a performance final usando as métricas **RAGAS**:

| Métrica             | O que mede                                                                 |
|---------------------|----------------------------------------------------------------------------|
| **Faithfulness**    | O modelo inventou algo fora do manual? (grounding no contexto)             |
| **Answer Relevance**| A resposta é útil para um engenheiro? (relevância da resposta)           |
| **Context Precision** | O Reranker escolheu o trecho certo? (qualidade do contexto recuperado) |

### Entregáveis Finais

- Pipeline RAG + Reranker estável e versionado.
- Modelo fine-tunado (LoRA/QLoRA) exportado e integrado à orquestração.
- Relatório de métricas (Hit Rate, MRR, Faithfulness, Answer Relevance, Context Precision).
- Documentação de como executar ingestão, treino e inferência.

---

## 8. Resumo dos Checkpoints e Ordem de Execução

| Ordem | Fase   | Checkpoint                                                                 |
|-------|--------|----------------------------------------------------------------------------|
| 1     | Fase 1 | Tabelas “Requirement Verification Matrix” legíveis e completas no MD      |
| 2     | Fase 2 | Hit Rate e MRR ok; resposta “Verificação vs Validação” perfeita            |
| 3     | Fase 3 | 20 amostras revisadas; lógica de engenharia correta no dataset             |
| 4     | Fase 4 | Curva de Loss plotada; modelo tunado melhor que base em formato NASA       |
| 5     | Fase 5 | Métricas RAGAS reportadas; RAG-tuned integrado e documentado               |

---

## 9. Prompt de Sistema Sugerido (Persona NASA)

Use o texto abaixo como base para o **system prompt** do assistente RAG (ajuste conforme necessário):

```text
You are an expert Systems Engineering Assistant trained on the NASA Systems Engineering Handbook (SP-2016-6105-REV2). Your role is to answer questions strictly based on the provided context from the Handbook. Use NASA terminology: "shall" statements for requirements, distinguish clearly between Verification and Validation, and refer to processes by their official names and inputs/outputs. If the context does not contain enough information, say so. Do not invent definitions or procedures. When relevant, cite the section or appendix (e.g., Appendix C) from the context.
```

---

## 10. Referências Rápidas

- **NASA SE Handbook:** SP-2016-6105-REV2 (PDF).
- **Docling:** IBM Docling para PDF → Markdown.
- **Reranker:** BAAI/bge-reranker-v2-m3 (Hugging Face).
- **Unsloth:** Fine-tuning eficiente para Llama/Qwen.
- **RAGAS:** Framework de avaliação para pipelines RAG (Faithfulness, Answer Relevance, Context Precision).

---

*Documento gerado como prompt específico para o projeto AI Systems Engineering Assistant — NASA SE Edition. Desenvolva fase a fase e valide cada checkpoint antes de prosseguir.*
