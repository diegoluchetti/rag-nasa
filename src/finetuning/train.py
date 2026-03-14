"""
Treino SFT com Unsloth (LoRA/QLoRA) no dataset preparado pelo data_loader.

Fluxo:
  1. Carregar modelo base com FastLanguageModel (4-bit se use_qlora).
  2. Aplicar LoRA com get_peft_model.
  3. Instanciar SFTTrainer (TRL) com dataset instruction/output.
  4. Treinar e salvar checkpoints no output_dir.

As importações Unsloth/TRL são feitas dentro da função para não exigir GPU/CUDA
ao importar o pacote (ex.: em máquinas que só rodam Fase 3).

Ref.: docs/PLANO_FASE4_FINETUNING_GGUF.md — Passos 4.2, 4.3, 4.4.
"""

from pathlib import Path
from typing import Any

from datasets import Dataset


def run_training(
    train_dataset: Dataset,
    val_dataset: Dataset,
    output_dir: str | Path,
    *,
    model_name: str = "unsloth/Llama-3.2-3B-Instruct",
    use_qlora: bool = False,
    max_seq_length: int = 1024,
    lora_rank: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    target_modules: list[str] | None = None,
    learning_rate: float = 2.0e-4,
    epochs: int = 3,
    per_device_train_batch_size: int = 2,
    gradient_accumulation_steps: int = 4,
    logging_steps: int = 10,
    save_steps: int = 100,
    save_strategy: str = "epoch",
) -> Any:
    """
    Executa o treino SFT com Unsloth (LoRA/QLoRA) e salva o modelo no output_dir.

    O modelo e o tokenizer retornados já têm os adaptadores LoRA aplicados;
    use export_gguf.merge_and_export_gguf() para mesclar e exportar para .gguf.

    Args:
        train_dataset: Dataset com colunas 'instruction' e 'output' (Alpaca).
        val_dataset: Dataset de validação (mesmo formato).
        output_dir: Diretório onde salvar checkpoints e modelo final.
        model_name: Nome do modelo no Hugging Face (ex.: unsloth/Llama-3.2-3B-Instruct).
        use_qlora: Se True, carrega modelo em 4-bit (menos VRAM).
        max_seq_length: Comprimento máximo da sequência (1024 ou 2048 conforme modelo).
        lora_rank, lora_alpha, lora_dropout: Parâmetros LoRA.
        target_modules: Módulos a adaptar (default: q_proj, k_proj, v_proj, o_proj).
        learning_rate, epochs: Hiperparâmetros de treino.
        per_device_train_batch_size, gradient_accumulation_steps: Batch e acumulação.
        logging_steps, save_steps, save_strategy: Log e salvamento.

    Returns:
        Objeto trainer (Unsloth/TRL) após train(), para uso em merge/export.
    """
    # Import pesado só quando for realmente treinar (ex.: em Colab com GPU).
    from unsloth import FastLanguageModel
    from trl import SFTTrainer
    from transformers import TrainingArguments

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if target_modules is None:
        target_modules = ["q_proj", "k_proj", "v_proj", "o_proj"]

    # 1) Carregar modelo e tokenizer com Unsloth (2x mais rápido, menos memória).
    # load_in_4bit=True reduz VRAM para Colab T4 (~15 GB).
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=max_seq_length,
        load_in_4bit=use_qlora,
        load_in_8bit=False,
    )

    # 2) Configurar LoRA e aplicar ao modelo.
    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_rank,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        target_modules=target_modules,
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    # 3) Training arguments.
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=per_device_train_batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        num_train_epochs=epochs,
        learning_rate=learning_rate,
        logging_steps=logging_steps,
        save_steps=save_steps,
        save_strategy=save_strategy,
        fp16=not use_qlora,
        bf16=use_qlora,
        warmup_ratio=0.05,
        optim="adamw_8bit" if use_qlora else "adamw_torch",
        report_to="none",
    )

    # 4) Montar coluna "text" no formato chat (user + assistant) para o SFTTrainer.
    # O modelo base (Llama 3.2 / Qwen) usa tokens especiais; este template é compatível.
    def _format_alpaca(examples: dict) -> dict:
        instructions = examples.get("instruction", [])
        outputs = examples.get("output", [])
        texts = []
        for instr, out in zip(instructions, outputs):
            t = f"<|user|>\n{instr}\n<|assistant|>\n{out}"
            texts.append(t)
        return {"text": texts}

    train_dataset = train_dataset.map(_format_alpaca, batched=True, remove_columns=["instruction", "output"])
    val_dataset = val_dataset.map(_format_alpaca, batched=True, remove_columns=["instruction", "output"])

    # 5) SFTTrainer com dataset que tem coluna "text".
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        dataset_num_proc=2,
        packing=False,
        args=training_args,
    )

    trainer.train()
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    return trainer
