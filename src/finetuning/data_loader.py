"""
Carrega o dataset da Fase 3 (JSONL) e converte para o formato esperado pelo Unsloth (Alpaca).

O JSONL gerado pela Fase 3 usa os campos do DatasetExample: instruction, response,
section_title, tags, etc. O Unsloth/SFTTrainer espera formato Alpaca: instruction + output.
Por isso mapeamos response → output e removemos colunas extras para o treino.

Ref.: docs/PLANO_FASE4_FINETUNING_GGUF.md — Passo 4.1.
"""

from pathlib import Path
from typing import Optional, Union

from datasets import Dataset, load_dataset


def load_dataset_for_unsloth(
    train_path: Union[str, Path],
    val_path: Union[str, Path],
    *,
    min_instruction_chars: int = 1,
    min_output_chars: int = 1,
) -> tuple[Dataset, Dataset]:
    """
    Carrega os JSONL de treino e validação da Fase 3 e converte para formato Unsloth (Alpaca).

    O que é feito:
    1. Carrega os arquivos via datasets.load_dataset("json", data_files=...).
    2. Cria a coluna 'output' a partir de 'response' (Unsloth espera instruction + output).
    3. Filtra linhas com instruction ou output vazios ou muito curtos (opcional).
    4. Retorna (dataset_train, dataset_val) prontos para o SFTTrainer.

    Args:
        train_path: Caminho para nasa_se_synthetic_train.jsonl.
        val_path: Caminho para nasa_se_synthetic_val.jsonl.
        min_instruction_chars: Mínimo de caracteres em instruction para manter a linha (0 = não filtrar).
        min_output_chars: Mínimo de caracteres em output para manter a linha (0 = não filtrar).

    Returns:
        (train_dataset, val_dataset) com colunas compatíveis com Alpaca (instruction, output).
    """
    train_path = Path(train_path)
    val_path = Path(val_path)
    if not train_path.exists():
        raise FileNotFoundError(f"Dataset de treino não encontrado: {train_path}")
    if not val_path.exists():
        raise FileNotFoundError(f"Dataset de validação não encontrado: {val_path}")

    # Carregar JSONL: uma linha por exemplo com instruction, response, etc.
    data_files = {
        "train": [str(train_path)],
        "validation": [str(val_path)],
    }
    dataset = load_dataset("json", data_files=data_files, split=None)
    train_ds = dataset["train"]
    val_ds = dataset["validation"]

    def _map_to_alpaca(example: dict) -> dict:
        # Unsloth/Alpaca usa 'output'; nosso schema usa 'response'.
        instruction = example.get("instruction") or ""
        response = example.get("response") or ""
        return {
            "instruction": instruction,
            "output": response,
        }

    def _filter_quality(example: dict) -> bool:
        if min_instruction_chars <= 0 and min_output_chars <= 0:
            return True
        instr = (example.get("instruction") or "").strip()
        out = (example.get("output") or "").strip()
        if min_instruction_chars > 0 and len(instr) < min_instruction_chars:
            return False
        if min_output_chars > 0 and len(out) < min_output_chars:
            return False
        return True

    # Mapear para colunas instruction + output; remover as antigas (response, id, tags, etc.).
    # O map adiciona "output"; mantemos "instruction". Removemos tudo que não faz parte do resultado.
    cols_to_remove_train = [c for c in train_ds.column_names if c != "instruction"]
    cols_to_remove_val = [c for c in val_ds.column_names if c != "instruction"]
    train_ds = train_ds.map(
        _map_to_alpaca,
        remove_columns=cols_to_remove_train,
        desc="Convert to Alpaca",
    )
    val_ds = val_ds.map(
        _map_to_alpaca,
        remove_columns=cols_to_remove_val,
        desc="Convert to Alpaca",
    )

    # Garantir que a chave é "output" (alguns datasets já vêm com "response" renomeado).
    # Após o map, temos instruction e output.

    if min_instruction_chars > 0 or min_output_chars > 0:
        train_ds = train_ds.filter(_filter_quality, desc="Filter quality")
        val_ds = val_ds.filter(_filter_quality, desc="Filter quality")

    return train_ds, val_ds
