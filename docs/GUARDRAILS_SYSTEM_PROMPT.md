# Guardrails do System Prompt — AI Systems Engineering Assistant

> **Objetivo:** Mapear e detalhar todos os guardrails que se aplicam ao prompt de sistema usado quando o LLM pré-processa o contexto (Fase 2). Este documento é a referência única para regras de comportamento do modelo; o texto efetivo do prompt está em `configs/prompts_nasa_system.txt`.

---

## 1. Visão geral

Os guardrails garantem que a resposta do assistente:

- Esteja **ancorada no Handbook** (sem alucinação).
- Use **terminologia e formato NASA** (shall, Verification/Validation, processos oficiais).
- **Nunca invente ou altere referências de fonte** (página, seção, parágrafo) — essas são injetadas pela aplicação (Design Decision 19).

Cada guardrail abaixo indica: **onde** é aplicado (texto do system prompt vs. lógica da aplicação) e **por quê** (requisito, decisão de design ou rastreabilidade).

---

## 2. Mapeamento dos guardrails

### G1 — Responder apenas com base no contexto fornecido

| Campo | Descrição |
|-------|------------|
| **ID** | G1 |
| **Regra** | O modelo deve responder **estritamente** com base no contexto (trechos do Handbook) fornecido no prompt do usuário. Não usar conhecimento externo nem inferências fora do texto dos blocos. |
| **No system prompt** | *"Your role is to answer questions strictly based on the provided context from the Handbook."* |
| **Rationale** | Evitar alucinação; garantir que a resposta seja verificável a partir dos trechos recuperados (rastreabilidade, FR-2.3.x). |
| **Enforcement** | Instrução no system prompt. A aplicação envia apenas os textos recuperados como contexto (não envia o Handbook inteiro). |

---

### G2 — Terminologia NASA: "shall" para requisitos

| Campo | Descrição |
|-------|------------|
| **ID** | G2 |
| **Regra** | Usar a linguagem de requisitos da NASA: **"shall"** para exigências obrigatórias; evitar redação vaga ou não normativa quando o contexto for sobre requisitos. |
| **No system prompt** | *"Use NASA terminology: 'shall' statements for requirements"* |
| **Rationale** | Alinhamento ao Handbook (SP-2016-6105-REV2) e à prática de engenharia de sistemas NASA. |
| **Enforcement** | Instrução no system prompt. |

---

### G3 — Distinguir Verificação e Validação

| Campo | Descrição |
|-------|------------|
| **ID** | G3 |
| **Regra** | Diferenciar claramente **Verification** (verificar que o produto atende aos requisitos) e **Validation** (validar que o produto atende às necessidades do usuário/uso). Não confundir nem usar os termos de forma intercambiável. |
| **No system prompt** | *"distinguish clearly between Verification and Validation"* |
| **Rationale** | Checkpoint 2 e perguntas de referência (ex.: "Qual a diferença entre Verificação e Validação?"); requisito de qualidade da resposta. |
| **Enforcement** | Instrução no system prompt. |

---

### G4 — Processos pelos nomes oficiais e inputs/outputs

| Campo | Descrição |
|-------|------------|
| **ID** | G4 |
| **Regra** | Ao referir processos de engenharia de sistemas, usar os **nomes oficiais** do Handbook e, quando relevante, **inputs e outputs** conforme o documento. Não renomear nem inventar processos. |
| **No system prompt** | *"refer to processes by their official names and inputs/outputs"* |
| **Rationale** | Consistência com a base de conhecimento e uso em contexto profissional. |
| **Enforcement** | Instrução no system prompt. |

---

### G5 — Admitir quando o contexto for insuficiente

| Campo | Descrição |
|-------|------------|
| **ID** | G5 |
| **Regra** | Se o contexto recuperado **não contiver** informação suficiente para responder à pergunta, o modelo deve **dizer isso explicitamente** (ex.: "O contexto fornecido não contém informações sobre X"). Não preencher lacunas com suposições ou conhecimento externo. |
| **No system prompt** | *"If the context does not contain enough information, say so."* |
| **Rationale** | Evitar alucinação; manter confiança e rastreabilidade. |
| **Enforcement** | Instrução no system prompt. |

---

### G6 — Não inventar definições ou procedimentos

| Campo | Descrição |
|-------|------------|
| **ID** | G6 |
| **Regra** | **Não inventar** definições, procedimentos, requisitos ou passos que não estejam no contexto. Reformular e resumir é permitido; acrescentar conteúdo novo não é. |
| **No system prompt** | *"Do not invent definitions or procedures."* |
| **Rationale** | Integridade da resposta e conformidade com FR (resposta baseada no Handbook). |
| **Enforcement** | Instrução no system prompt. |

---

### G7 — Não gerar referências de fonte (página, seção, parágrafo)

| Campo | Descrição |
|-------|------------|
| **ID** | G7 |
| **Regra** | O modelo **não** deve gerar, inferir ou alterar **referências de fonte** (número de página, número de seção, número de parágrafo, nome de apêndice como citação). As referências são **adicionadas automaticamente** pela aplicação a partir dos metadados do retrieval (Design Decision 19). |
| **No system prompt** | *"Do not invent or generate source references (page numbers, section numbers); they will be added automatically from the retrieval metadata."* |
| **Rationale** | Evitar alucinações em citações (ex.: "conforme p. 99" quando a informação veio de outro trecho); garantir que a seção "Fontes" da resposta contenha apenas dados reais do retrieval (FR-2.3.6). |
| **Enforcement** | **Prompt:** instrução explícita. **Aplicação:** o contexto enviado ao LLM contém apenas o **texto** dos blocos (sem page/section no corpo); a montagem da resposta final usa apenas `_format_source_line()` com metadados do Neo4j — nunca se usa texto gerado pelo LLM para extrair página ou seção. |

---

## 3. Resumo por tipo de enforcement

| Guardrail | No system prompt | Na aplicação |
|-----------|------------------|---------------|
| G1 — Só contexto | ✓ | Envio apenas dos trechos recuperados |
| G2 — Shall | ✓ | — |
| G3 — V&V | ✓ | — |
| G4 — Processos oficiais | ✓ | — |
| G5 — Dizer se falta contexto | ✓ | — |
| G6 — Não inventar | ✓ | — |
| G7 — Não gerar fontes | ✓ | Fontes sempre injetadas a partir do retrieval |

---

## 4. Referências cruzadas

- **Texto do prompt:** `configs/prompts_nasa_system.txt`
- **Uso do prompt:** `src/graphrag/query_engine.py` (`get_nasa_system_prompt`, `_call_llm_for_response`, montagem da seção "Fontes")
- **Design Decision 19:** `docs/DESIGN_DECISIONS.md` — LLM pré-processa contexto; fonte intacta e injetada pela aplicação
- **Design Decision 18:** `docs/DESIGN_DECISIONS.md` — Propagação de página e parágrafo (FR-2.3.6)
- **Requisitos Fase 2:** `docs/REQUIREMENTS_FASE2.md` (FR-2.3.x, FR-2.4.x)

---

## 5. Manutenção

- Ao **alterar** o texto em `configs/prompts_nasa_system.txt`, atualizar este documento se uma nova regra for introduzida ou uma existente for removida/alterada.
- Ao **adicionar** um guardrail (ex.: "não responder em outro idioma que não o da pergunta"), criar nova entrada na seção 2 (G8, G9, …) e atualizar a tabela da seção 3.

---

*Documento de guardrails do system prompt — NASA SE Assistant. Última atualização alinhada ao Design Decision 19 e ao fluxo de fontes injetadas pela aplicação.*
