# Fine-tuning local com Tesla T4 (ou outra GPU CUDA)

Se você tem uma VM ou máquina com **Tesla T4** (16 GB VRAM) ou GPU compatível, pode rodar o fine-tuning **localmente** sem usar o Google Colab. O script `scripts/run_finetuning.py` usa o `configs/default.yaml` e os datasets em `data/datasets/`.

---

## Pré-requisitos na VM

1. **CUDA** instalado (driver + toolkit compatível com PyTorch/Unsloth). T4 funciona com CUDA 11.x ou 12.x.
2. **Python 3.10+** e ambiente isolado (venv ou conda).
3. **Dataset Fase 3** já gerado: `data/datasets/nasa_se_synthetic_train.jsonl` e `nasa_se_synthetic_val.jsonl`.

---

## Passos

### 1. Clonar/copiar o projeto na VM

Se o código já está na VM, use esse diretório. Caso contrário:

```bash
git clone https://github.com/diegoluchetti/rag-nasa.git
cd rag-nasa
```

### 2. Criar ambiente e instalar dependências (Fase 4)

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

pip install -r requirements-phase4.txt
```

Se o Unsloth exigir uma versão específica do PyTorch/CUDA, siga a [documentação oficial do Unsloth](https://github.com/unslothai/unsloth) para sua versão de CUDA (ex.: `pip install unsloth` após instalar o PyTorch com suporte CUDA).

### 3. Verificar GPU

```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
```

Deve mostrar `CUDA: True` e o nome da GPU (ex.: Tesla T4).

### 4. Rodar o fine-tuning

Na raiz do projeto:

```bash
python scripts/run_finetuning.py
```

O script vai:

- Carregar o dataset de `data/datasets/` (train + val).
- Carregar o modelo base configurado em `configs/default.yaml` (ex.: `unsloth/Llama-3.2-3B-Instruct`).
- Treinar com LoRA e salvar checkpoints em `models/nasa_se_3b_lora/`.
- Mesclar LoRA e exportar o modelo em GGUF em `models/nasa_se_3b_lora/gguf/`.

Tempo estimado na T4: da ordem de dezenas de minutos a algumas horas, dependendo do tamanho do dataset e do número de épocas.

### 5. (Opcional) Só treinar, sem exportar .gguf

```bash
python scripts/run_finetuning.py --skip-gguf
```

Depois você pode exportar o .gguf em outra etapa (por exemplo, rodando apenas a parte de export no script ou no notebook).

---

## Ajustes no `configs/default.yaml` (se necessário)

- **Falta de memória (OOM) na T4:** Em `configs/default.yaml`, na seção `finetuning`, altere:
  - `use_qlora: true` (treino em 4-bit, usa menos VRAM).
  - `per_device_train_batch_size: 1` e aumente `gradient_accumulation_steps` (ex.: 8) para manter batch efetivo.
- **Salvar .gguf com outra quantização:** Adicione em `finetuning`:
  - `gguf_quantization: "q4_k_m"` (padrão, menor arquivo) ou `"q8_0"` / `"f16"` para maior qualidade.

---

## Saídas esperadas

| Saída | Descrição |
|-------|-----------|
| `models/nasa_se_3b_lora/` | Checkpoints do treino (por época). |
| `models/nasa_se_3b_lora/gguf/*.gguf` | Modelo em formato GGUF para Ollama/llama.cpp. |
| `log/phase4_finetuning_*.json` | Métricas da execução (paths, número de exemplos, timestamp). |

---

## Referências

- [docs/PLANO_FASE4_FINETUNING_GGUF.md](PLANO_FASE4_FINETUNING_GGUF.md) — Plano completo da Fase 4.
- [Design Decision 20](DESIGN_DECISIONS.md) — Uso do Colab quando não há GPU local; com T4 local, o Colab não é necessário.
