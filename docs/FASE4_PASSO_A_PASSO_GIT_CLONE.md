# Passo a passo — Fine-tuning Fase 4 (começando com git clone)

Guia em ordem: clonar o repositório, preparar ambiente, rodar o fine-tuning e obter o modelo .gguf. Para máquina com **GPU CUDA** (ex.: Tesla T4).

---

## Passo 1 — Clonar o repositório

**Linux/macOS:**
```bash
git clone https://github.com/diegoluchetti/rag-nasa.git
cd rag-nasa
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/diegoluchetti/rag-nasa.git
cd rag-nasa
```

---

## Passo 2 — Garantir o dataset da Fase 3

O fine-tuning usa os arquivos em `data/datasets/`. **Se você clonou o repo em outra máquina (ex.: VM com GPU), a pasta `data/datasets/` pode estar vazia ou não existir** (muitos repos não versionam dados). É obrigatório ter:

- `data/datasets/nasa_se_synthetic_train.jsonl`
- `data/datasets/nasa_se_synthetic_val.jsonl`

Verifique se existem:

```bash
# Linux/macOS / Git Bash
ls -la data/datasets/nasa_se_synthetic_train.jsonl data/datasets/nasa_se_synthetic_val.jsonl
```

```powershell
# Windows PowerShell
Test-Path data/datasets/nasa_se_synthetic_train.jsonl; Test-Path data/datasets/nasa_se_synthetic_val.jsonl
```

- **Se os dois arquivos existirem:** siga para o Passo 3.
- **Se não existirem:**
  - **Opção A — Gerar na própria máquina (não precisa de GPU):** crie o ambiente, instale dependências da Fase 3 e rode:
    ```bash
    pip install PyYAML tiktoken
    pip install -r requirements-phase1.txt   # ou o necessário para run_dataset_gen
    python scripts/run_dataset_gen.py
    ```
  - **Opção B — Copiar da máquina onde já existe:** se você já gerou o dataset em outro PC (ex.: Windows), copie para a VM:
    ```bash
    mkdir -p data/datasets
    # Depois use scp, rsync ou upload para colar:
    #   data/datasets/nasa_se_synthetic_train.jsonl
    #   data/datasets/nasa_se_synthetic_val.jsonl
    ```
    Exemplo com `scp` (na sua máquina local):  
    `scp data/datasets/nasa_se_synthetic_*.jsonl diegorego@boeing-student-12:/efs/workspace/rag-nasa/data/datasets/`

  Depois confira de novo e siga para o Passo 3.

---

## Passo 3 — Criar ambiente virtual e ativar

**Linux/macOS:**
```bash
cd rag-nasa
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
cd rag-nasa
python -m venv .venv
.venv\Scripts\activate
```

O prompt deve mostrar `(.venv)`.

---

## Passo 4 — Instalar dependências da Fase 4

Com o ambiente ativado:

```bash
pip install --upgrade pip
pip install -r requirements-phase4.txt
```

Se aparecer erro de CUDA/PyTorch, instale primeiro o PyTorch com CUDA para a sua versão e depois o restante (veja [Unsloth](https://github.com/unslothai/unsloth) para detalhes).

---

## Passo 5 — Verificar GPU (CUDA)

```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
```

- Deve aparecer **CUDA: True** e o nome da GPU (ex.: Tesla T4).
- Se aparecer **CUDA: False**, instale/configure o driver e o PyTorch com suporte CUDA antes de continuar.

---

## Passo 6 — Rodar o fine-tuning

Na raiz do projeto (`rag-nasa`), com o `.venv` ativado:

```bash
python scripts/run_finetuning.py
```

O script vai:

1. Ler `configs/default.yaml` e os paths de `data/datasets/`.
2. Carregar o modelo base (ex.: Llama 3.2 3B) e aplicar LoRA.
3. Treinar no dataset e salvar checkpoints em `models/nasa_se_3b_lora/`.
4. Mesclar LoRA e exportar o .gguf em `models/nasa_se_3b_lora/gguf/`.

O processo pode levar de dezenas de minutos a algumas horas, conforme dataset e hardware.

---

## Passo 7 — Onde estão os resultados

| O quê | Onde |
|-------|------|
| Checkpoints do treino | `models/nasa_se_3b_lora/` |
| Modelo .gguf | `models/nasa_se_3b_lora/gguf/*.gguf` |
| Log da execução | `log/phase4_finetuning_*.json` |

Use o arquivo `.gguf` no Ollama ou no llama.cpp (Fase 5).

---

## Opções úteis

- **Só treinar, sem exportar .gguf agora:**
  ```bash
  python scripts/run_finetuning.py --skip-gguf
  ```

- **Falta de memória (OOM):** edite `configs/default.yaml`, seção `finetuning`:
  - `use_qlora: true`
  - `per_device_train_batch_size: 1`
  - `gradient_accumulation_steps: 8`

---

## Resumo em uma linha (após o clone)

```bash
cd rag-nasa && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-phase4.txt && python -c "import torch; print('CUDA:', torch.cuda.is_available())" && python scripts/run_finetuning.py
```

(No Windows use `python` e `.venv\Scripts\activate`.)
