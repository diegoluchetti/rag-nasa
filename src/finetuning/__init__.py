"""
Fase 4 — Fine-tuning do SLM com Unsloth (SFT + LoRA/QLoRA) e export para .gguf.

Este pacote não importa Unsloth/TRL no carregamento, para permitir usar o projeto
sem GPU (ex.: apenas Fase 3). As dependências de treino são importadas dentro
das funções de train e export_gguf.

Uso:
  - Local: scripts/run_finetuning.py (carrega configs/default.yaml).
  - Colab: notebooks/fase4_finetuning_colab.ipynb (paths e params explícitos).
Ref.: docs/PLANO_FASE4_FINETUNING_GGUF.md, Design Decision 20.
"""

from src.finetuning.data_loader import load_dataset_for_unsloth

__all__ = ["load_dataset_for_unsloth"]
