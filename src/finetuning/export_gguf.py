"""
Mescla os adaptadores LoRA no modelo base e exporta para formato .gguf.

O modelo treinado (PEFT) é mesclado em um único modelo 16-bit e depois exportado
para GGUF (quantizado opcionalmente) para uso em Ollama ou llama.cpp.

Ref.: docs/PLANO_FASE4_FINETUNING_GGUF.md — Passo 4.5.
"""

from pathlib import Path
from typing import Any


def merge_and_export_gguf(
    trainer_or_model: Any,
    tokenizer: Any,
    output_path: str | Path,
    *,
    quantization_method: str = "q4_k_m",
) -> Path:
    """
    Mescla LoRA no modelo e exporta para um arquivo/diretório .gguf.

    Args:
        trainer_or_model: Objeto SFTTrainer (após train()) ou (model, tokenizer).
        tokenizer: Tokenizer (se trainer_or_model for o trainer, usa trainer.tokenizer).
        output_path: Caminho do arquivo .gguf ou diretório onde salvar (Unsloth pode salvar um dir).
        quantization_method: "q4_k_m" (menor), "q8_0", "f16" (sem quantização). Ver Unsloth docs.

    Returns:
        Path do arquivo ou diretório onde o .gguf foi salvo.
    """
    # Import só quando for exportar (evita dep de Unsloth ao importar o pacote).
    try:
        from unsloth import FastLanguageModel
    except Exception as e:
        raise RuntimeError("Unsloth não está instalado. Instale com: pip install unsloth") from e

    output_path = Path(output_path)

    # Aceitar trainer (tem .model e .tokenizer) ou (model, tokenizer).
    if hasattr(trainer_or_model, "model") and hasattr(trainer_or_model, "tokenizer"):
        model = trainer_or_model.model
        tok = trainer_or_model.tokenizer
    else:
        model = trainer_or_model
        tok = tokenizer

    # Mesclar adaptadores LoRA no modelo base (necessário antes de exportar para GGUF).
    model = FastLanguageModel.for_inference(model)

    # Salvar em GGUF. Unsloth salva em um diretório com o .gguf dentro.
    if output_path.suffix.lower() == ".gguf":
        save_dir = output_path.parent / output_path.stem
    else:
        save_dir = output_path
    save_dir.mkdir(parents=True, exist_ok=True)

    # API Unsloth: save_pretrained_gguf(directory, tokenizer, quantization_method=...)
    model.save_pretrained_gguf(str(save_dir), tok, quantization_method=quantization_method)

    # Unsloth pode gerar um arquivo .gguf dentro do dir; retornamos o dir ou o .gguf se existir.
    gguf_files = list(save_dir.glob("*.gguf"))
    if gguf_files:
        return gguf_files[0]
    return save_dir
