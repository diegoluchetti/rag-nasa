# Plano de Implementação — Fase 4: Fine-Tuning e Export para .gguf

> **Referências:** [PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md](../PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md), [PROMPT_NASA_SE_AI_ASSISTANT.md](../PROMPT_NASA_SE_AI_ASSISTANT.md)  
> **Objetivo:** Detalhar passo a passo a Fase 4: treinar um SLM com Unsloth (SFT + LoRA/QLoRA) no dataset da Fase 3 e exportar o modelo para **.gguf** para entrega ao cliente (inferência local, sem custo de API). Foco em restrições de custo e escalabilidade (ambiente local quando possível).

---

## 1. Objetivo e critérios de sucesso

| Item | Descrição |
|------|-----------|
| **Objetivo** | Ensinar o “dialeto” NASA SE ao modelo (requisitos Shall, terminologia Verification/Validation, processos oficiais) via SFT no dataset sintético da Fase 3; entregar modelo em **.gguf** para uso local. |
| **Entregável principal** | Modelo fine-tunado em **.gguf** em `models/` (ex.: `nasa_se_assistant_3b.gguf`), pronto para Ollama/llama.cpp. |
| **Checkpoint 4 concluído quando** | (1) Curva de loss plotada e saudável; (2) teste comparativo modelo base vs tunado mostra que o tunado segue melhor o formato NASA; (3) arquivo .gguf carrega e gera respostas coerentes. |

**Não avançar para a Fase 5 sem validar o Checkpoint 4.**

---

## 2. Pré-requisitos

- **Fase 3 concluída:** Dataset em `data/datasets/nasa_se_synthetic_train.jsonl` e `nasa_se_synthetic_val.jsonl` com ≥100 exemplos válidos; verificador Fase 3 em PASS.
- **Hardware:** GPU com CUDA (recomendado ≥8 GB VRAM para 3B; <8 GB considerar 1B ou QLoRA 4-bit).
- **Ambiente:** Python 3.10+; `configs/default.yaml` com seção `finetuning` e `paths.models` (já existente).
- **Design Decision 19:** O modelo tunado será usado apenas para **pré-processar o contexto** (resposta em prosa); as **fontes** (seção, página, parágrafo) continuam injetadas pela aplicação — o fine-tuning não altera essa regra.

---

## 3. Entradas e saídas

| Tipo | Caminho / origem | Descrição |
|------|-------------------|-----------|
| **Entrada** | `data/datasets/nasa_se_synthetic_train.jsonl` | Dataset de treino (Fase 3); campos: `instruction`, `response`, e outros do `DatasetExample`. |
| **Entrada** | `data/datasets/nasa_se_synthetic_val.jsonl` | Dataset de validação (Fase 3). |
| **Entrada** | `configs/default.yaml` | Seção `finetuning` e `paths`; opcionalmente nova seção `finetuning.model_name`, `batch_size`, `use_qlora`. |
| **Saída** | `models/nasa_se_3b_lora/` (ou similar) | Checkpoints LoRA por época. |
| **Saída** | `models/nasa_se_assistant_3b.gguf` | Modelo mesclado (base + LoRA) em formato GGUF para entrega. |
| **Saída** | `log/phase4_*.json` ou `log/phase4_*.png` | Curva de loss e métricas de treino (opcional). |

---

## 4. Configuração (configs/default.yaml)

A seção **finetuning** já existe. Recomenda-se estender para:

```yaml
finetuning:
  learning_rate: 2.0e-4
  epochs: 3
  lora_rank: 16
  lora_alpha: 32
  lora_dropout: 0.05
  target_modules:
    - q_proj
    - k_proj
    - v_proj
    - o_proj
  # Novos (sugestão)
  model_name: "unsloth/Llama-3.2-3B-Instruct"   # ou unsloth/Qwen2.5-3B-Instruct
  per_device_train_batch_size: 2
  gradient_accumulation_steps: 4
  use_qlora: false                              # true se VRAM < 8GB
  max_seq_length: 1024
  save_steps: 100
  logging_steps: 10
  output_dir: "models/nasa_se_3b_lora"
  gguf_output_name: "nasa_se_assistant_3b"
```

Carregar essa config no script de treino (ex.: `src/ingestion/config_loader.load_config`) e usar os valores em vez de constantes no código.

---

## 5. Formato do dataset e compatibilidade Unsloth

- O JSONL da Fase 3 usa **`instruction`** e **`response`** (schema `DatasetExample`).
- Unsloth aceita formato **Alpaca**: `instruction`, `input` (opcional), **`output`**.
- **Ação:** Ao carregar para o Unsloth, mapear `response` → `output` (ou criar coluna `output = response`). Campos extras (tags, section_title, etc.) podem ser ignorados para o SFT.
- **Chat template:** O modelo base (Llama 3.2 / Qwen 2.5) já define um template (ex.: `<|user|>`, `<|assistant|>`). O Unsloth monta o texto de treino a partir de `instruction` + `output` conforme o template do modelo; garantir que o dataset passado ao trainer tenha as colunas esperadas (geralmente `instruction` e `output` ou formato conversação).
- Referência: [Unsloth Datasets Guide](https://docs.unsloth.ai/basics/datasets-guide) e [Chat Templates](https://docs.unsloth.ai/basics/chat-templates).

---

## 6. Passos de implementação

### Passo 4.0 — Preparação do ambiente

**O que fazer:** Criar ambiente com CUDA e instalar Unsloth + dependências.

**Como:**

1. Verificar CUDA: `python -c "import torch; print(torch.cuda.is_available())"`.
2. Instalar Unsloth (ver [Unsloth install](https://github.com/unslothai/unsloth)):  
   `pip install unsloth` (ou versão compatível com seu PyTorch/CUDA).
3. Dependências típicas: `transformers`, `datasets`, `peft`, `accelerate`, `bitsandbytes` (se QLoRA).
4. Adicionar ao `requirements.txt` (ou `pyproject.toml`) um bloco **Fase 4:** `unsloth`, `transformers`, `datasets`, `peft`, `accelerate`.

**Critério:** `import unsloth` e `torch.cuda.is_available()` True. Dependências listadas em **`requirements-phase4.txt`** (para ambiente local com CUDA); no Colab o notebook instala Unsloth a partir do repositório oficial.

---

### Passo 4.1 — Carregar dataset e converter para formato Unsloth (Tarefa 4.1)

**O que fazer:** Ler os JSONL train/val da Fase 3, converter para o formato esperado pelo Unsloth (colunas compatíveis com SFT, ex.: `instruction` e `output`).

**Como:**

1. Usar `datasets.load_dataset("json", data_files={"train": [train_path], "validation": [val_path]})` com `train_path` e `val_path` lidos de `config` (`paths.data_datasets` + nomes fixos `nasa_se_synthetic_train.jsonl` / `nasa_se_synthetic_val.jsonl`).
2. Mapear colunas: criar coluna `output` = `response` (ou renomear) e manter `instruction`. Remover ou ignorar colunas desnecessárias para o treino.
3. (Opcional) Aplicar filtros de qualidade: remover linhas com `instruction` ou `output` vazios ou muito curtos.
4. Verificar que o dataset tem colunas esperadas pelo `SFTTrainer` do Unsloth (ex.: formato Alpaca ou o que o método `train()` aceita).

**Artefato:** Função ou script em `src/finetuning/` (ou `scripts/`) que recebe config e retorna `Dataset` (train/val) pronto para o trainer.

---

### Passo 4.2 — Escolher modelo base e carregar com Unsloth

**O que fazer:** Escolher SLM base (ex.: Llama 3.2 3B ou Qwen 2.5 3B), carregar com `FastLanguageModel` do Unsloth e aplicar LoRA (Passo 4.3).

**Como:**

1. Modelo: ler de config (`finetuning.model_name`), ex.: `unsloth/Llama-3.2-3B-Instruct` ou `unsloth/Qwen2.5-3B-Instruct`. Se VRAM < 8 GB, considerar `unsloth/Llama-3.2-1B` ou ativar QLoRA.
2. Carregar: `FastLanguageModel.for_pretrained(..., load_in_4bit=use_qlora, ...)` conforme documentação Unsloth.
3. Aplicar adaptadores LoRA (ver Passo 4.3) e obter o modelo preparado para treino.

**Detalhe:** Usar `max_seq_length` do config; Unsloth pode exigir um valor compatível com o modelo (ex.: 2048 ou 1024).

---

### Passo 4.3 — Configurar LoRA/QLoRA (Tarefa 4.2)

**O que fazer:** Aplicar LoRA (ou QLoRA) com os parâmetros definidos no prompt e no `configs/default.yaml`.

**Como:**

1. Criar `LoraConfig` (ou equivalente Unsloth) com:  
   `r=finetuning.lora_rank` (16 ou 32),  
   `lora_alpha=finetuning.lora_alpha` (32),  
   `target_modules=finetuning.target_modules` (q_proj, k_proj, v_proj, o_proj),  
   `lora_dropout=finetuning.lora_dropout` (0.05 ou 0).
2. Se QLoRA: carregar modelo em 4-bit e usar o mesmo `LoraConfig`; bitsandbytes config conforme Unsloth.
3. Passar o config para o modelo (Unsloth costuma aplicar LoRA via API própria; seguir a doc oficial).

---

### Passo 4.4 — Treinar com SFT (Supervised Fine-Tuning)

**O que fazer:** Configurar o Trainer (Unsloth `SFTTrainer` ou equivalente) e rodar o treino; salvar checkpoints em `models/`.

**Como:**

1. `TrainingArguments`:  
   `num_train_epochs=finetuning.epochs`,  
   `per_device_train_batch_size=finetuning.per_device_train_batch_size`,  
   `gradient_accumulation_steps=finetuning.gradient_accumulation_steps`,  
   `learning_rate=finetuning.learning_rate`,  
   `logging_steps=finetuning.logging_steps`,  
   `save_strategy="epoch"` (ou `save_steps`),  
   `output_dir=finetuning.output_dir` (ou `paths.models` + subpasta).
2. Instanciar o trainer com modelo, tokenizer, dataset train/val e training arguments.
3. `trainer.train()`; `trainer.save_model()` (e opcionalmente salvar o tokenizer).
4. Registrar curva de loss (ex.: tensorboard ou log em `log/phase4_train_log.json`).

**Critério:** Treino completa sem erro; checkpoints em `output_dir`; curva de loss decrescente e estável.

---

### Passo 4.5 — Mesclar LoRA no modelo base e exportar para .gguf

**O que fazer:** Mesclar os adaptadores LoRA no modelo base e exportar o modelo resultante para **formato .gguf** em `models/`.

**Como:**

1. **Merge:** Usar API Unsloth para mesclar LoRA no modelo base (ex.: `model.save_pretrained_merged(...)` ou equivalente na documentação atual).
2. **Export GGUF:** Unsloth oferece export para GGUF (ex.: `model.save_pretrained_gguf(...)` ou script recomendado). Salvar em `models/<gguf_output_name>.gguf` (nome vindo do config).
3. Documentar no plano (e depois no .ipynb da Fase 5) como carregar o .gguf no Ollama ou llama.cpp.

**Referência:** [Unsloth GGUF export](https://docs.unsloth.ai/get-started/export) (verificar doc mais recente).

---

### Passo 4.6 — Validação do Checkpoint 4

**O que fazer:** Garantir que a Fase 4 está concluída antes de passar à Fase 5.

**Critérios:**

1. **Curva de loss:** Plotar loss de treino (e validação se disponível); curva deve ser saudável (decrescente, sem picos anômalos).
2. **Teste comparativo:** Mesmas perguntas (ex.: 5–10) no **modelo base** e no **modelo tunado**; o tunado deve seguir melhor o formato NASA (Shall, Verification vs Validation, terminologia do Handbook).
3. **.gguf em uso:** Carregar o arquivo .gguf (Ollama ou llama.cpp), fazer inferência com uma pergunta de exemplo e verificar que a resposta é coerente e no estilo esperado.

**Artefato (opcional):** Script `scripts/run_phase4_requirements_verifier.py` que verifica: existência de `models/*.gguf`, existência de diretório de checkpoints, e opcionalmente gera um relatório mínimo (loss, caminho do .gguf).

---

## 7. Estrutura de código sugerida

```
rag-nasa/
├── configs/
│   └── default.yaml              # finetuning + paths (estendido)
├── src/
│   └── finetuning/               # (novo) módulos Fase 4
│       ├── __init__.py
│       ├── data_loader.py       # carrega JSONL, mapeia response→output
│       ├── train.py             # modelo + LoRA + SFTTrainer
│       └── export_gguf.py       # merge + export .gguf
├── scripts/
│   ├── run_finetuning.py        # orquestra: data → train → export
│   └── run_phase4_requirements_verifier.py  # opcional
├── models/
│   ├── nasa_se_3b_lora/        # checkpoints
│   └── nasa_se_assistant_3b.gguf
└── log/
    └── phase4_*.json / *.png
```

Alternativa: manter um único script `scripts/run_finetuning.py` que faz load config → load data → load model → LoRA → train → merge → export, sem precisar criar o pacote `src/finetuning/` no primeiro incremento.

---

## 8. Troubleshooting e alternativas

| Situação | Ação sugerida |
|----------|----------------|
| **Sem CUDA** | Treino em CPU é lento; **usar Google Colab** (Design Decision 20): notebook `notebooks/fase4_finetuning_colab.ipynb` instala Unsloth, usa dataset (clone ou upload) e salva .gguf no Drive ou download. |
| **VRAM insuficiente** | Ativar QLoRA (4-bit), reduzir `per_device_train_batch_size` a 1, aumentar `gradient_accumulation_steps`; ou usar modelo 1B. |
| **Erro de formato de dataset** | Confirmar que as colunas se chamam como o Unsloth espera (ex.: `instruction`/`output` para Alpaca); usar `dataset = dataset.map(...)` para renomear. |
| **Export .gguf falha** | Verificar versão do Unsloth e se o modelo mesclado é suportado para GGUF; em último caso, usar script de conversão Hugging Face → GGUF (ex.: llama.cpp) a partir do modelo mesclado salvo em HF. |

---

## 9. Execução no Google Colab (sem GPU local)

Quando não houver poder computacional local (Design Decision 20), use o notebook **`notebooks/fase4_finetuning_colab.ipynb`**:

1. Abra o notebook no Google Colab e ative **Runtime → Change runtime type → T4 GPU**.
2. Execute as células em ordem: verificar GPU → instalar Unsloth → preparar dataset (clone do repo ou upload dos dois JSONL) → treinar e exportar .gguf → salvar no Drive ou download.
3. O mesmo código (`src.finetuning`) é usado no Colab e no script `scripts/run_finetuning.py`; no Colab os paths são definidos nas células (ex.: `/content/rag-nasa`, `/content/output_fase4`).
4. Após o treino, copie o .gguf para `models/` no seu repositório local para uso na Fase 5.

---

## 10. Ordem de execução e dependências

1. **Fase 3** → dataset train/val em `data/datasets/` e verificador PASS.  
2. **Passo 4.0** → ambiente Unsloth + CUDA (local ou Colab).  
3. **Passos 4.1–4.4** → dados → modelo → LoRA → treino.  
4. **Passo 4.5** → merge + export .gguf.  
5. **Passo 4.6** → validação Checkpoint 4.  

Após concluir, a **Fase 5** usará o `.gguf` no pipeline RAG-tuned e preparará o entregável (.ipynb + modelo .gguf).

---

## 11. Referências

- [Unsloth — Datasets Guide](https://docs.unsloth.ai/basics/datasets-guide)
- [Unsloth — Chat Templates](https://docs.unsloth.ai/basics/chat-templates)
- [Unsloth — Export (GGUF)](https://docs.unsloth.ai/get-started/export) (verificar URL atual)
- [PROMPT_NASA_SE_AI_ASSISTANT.md](../PROMPT_NASA_SE_AI_ASSISTANT.md) — Tarefas 4.1, 4.2 e Checkpoint 4
- [PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md](../PLANO_IMPLEMENTACAO_NASA_SE_ASSISTANT.md) — Fase 4 (visão geral)

---

*Plano Fase 4 — Fine-Tuning e export para .gguf. Alinhado ao estado atual: Fase 3 implementada; entregável final .ipynb + .gguf na Fase 5.*
