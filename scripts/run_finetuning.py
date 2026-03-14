"""
Pipeline Fase 4 — Fine-tuning com Unsloth (SFT + LoRA) e export para .gguf.

Uso local (na raiz do projeto, com configs/default.yaml):
  python scripts/run_finetuning.py

Uso Colab ou paths explícitos (sem depender do config do repo):
  python scripts/run_finetuning.py --colab --train /content/train.jsonl --val /content/val.jsonl --output-dir /content/output

Requer GPU com CUDA. Para rodar sem GPU local, use o notebook notebooks/fase4_finetuning_colab.ipynb
no Google Colab (Design Decision 20).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger(__name__)


def _get_finetuning_params_from_config(config: dict) -> dict:
    """Extrai parâmetros de fine-tuning do config (paths já resolvidos por load_config)."""
    paths = config.get("paths", {})
    data_datasets = Path(paths.get("data_datasets", str(PROJECT_ROOT / "data/datasets")))
    if not data_datasets.is_absolute():
        data_datasets = PROJECT_ROOT / data_datasets

    ft = config.get("finetuning", {})
    output_dir = Path(ft.get("output_dir", "models/nasa_se_3b_lora"))
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    return {
        "train_path": data_datasets / "nasa_se_synthetic_train.jsonl",
        "val_path": data_datasets / "nasa_se_synthetic_val.jsonl",
        "output_dir": output_dir,
        "model_name": ft.get("model_name", "unsloth/Llama-3.2-3B-Instruct"),
        "use_qlora": ft.get("use_qlora", False),
        "max_seq_length": int(ft.get("max_seq_length", 1024)),
        "lora_rank": int(ft.get("lora_rank", 16)),
        "lora_alpha": int(ft.get("lora_alpha", 32)),
        "lora_dropout": float(ft.get("lora_dropout", 0.05)),
        "target_modules": ft.get("target_modules", ["q_proj", "k_proj", "v_proj", "o_proj"]),
        "learning_rate": float(ft.get("learning_rate", 2.0e-4)),
        "epochs": int(ft.get("epochs", 3)),
        "per_device_train_batch_size": int(ft.get("per_device_train_batch_size", 2)),
        "gradient_accumulation_steps": int(ft.get("gradient_accumulation_steps", 4)),
        "logging_steps": int(ft.get("logging_steps", 10)),
        "save_steps": int(ft.get("save_steps", 100)),
        "save_strategy": str(ft.get("save_strategy", "epoch")),
        "gguf_output_name": ft.get("gguf_output_name", "nasa_se_assistant_3b"),
        "gguf_quantization": ft.get("gguf_quantization", "q4_k_m"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fase 4: Fine-tuning Unsloth + export .gguf")
    parser.add_argument("--config", default="default", help="Nome do config (configs/<name>.yaml)")
    parser.add_argument("--colab", action="store_true", help="Modo Colab: usar --train/--val/--output-dir em vez do config")
    parser.add_argument("--train", type=Path, help="Caminho do JSONL de treino (obrigatório se --colab)")
    parser.add_argument("--val", type=Path, help="Caminho do JSONL de validação (obrigatório se --colab)")
    parser.add_argument("--output-dir", type=Path, help="Diretório de saída (checkpoints + .gguf)")
    parser.add_argument("--skip-gguf", action="store_true", help="Só treinar, não exportar .gguf")
    args = parser.parse_args()

    if args.colab:
        if not args.train or not args.val or not args.output_dir:
            parser.error("--colab exige --train, --val e --output-dir")
        train_path = args.train
        val_path = args.val
        output_dir = args.output_dir
        # Params padrão (Colab T4: use_qlora=True recomendado)
        params = {
            "train_path": train_path,
            "val_path": val_path,
            "output_dir": output_dir,
            "model_name": "unsloth/Llama-3.2-3B-Instruct",
            "use_qlora": True,
            "max_seq_length": 1024,
            "lora_rank": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.05,
            "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
            "learning_rate": 2.0e-4,
            "epochs": 3,
            "per_device_train_batch_size": 2,
            "gradient_accumulation_steps": 4,
            "logging_steps": 10,
            "save_steps": 100,
            "save_strategy": "epoch",
            "gguf_output_name": "nasa_se_assistant_3b",
            "gguf_quantization": "q4_k_m",
        }
    else:
        from src.ingestion.config_loader import load_config
        config = load_config(args.config)
        params = _get_finetuning_params_from_config(config)
        train_path = params["train_path"]
        val_path = params["val_path"]
        output_dir = params["output_dir"]

    if not train_path.exists() or not val_path.exists():
        LOG.error(
            "Dataset não encontrado. Esperado: %s e %s. "
            "Gere com: python scripts/run_dataset_gen.py (ou copie os JSONL para data/datasets/). "
            "Ver docs/FASE4_PASSO_A_PASSO_GIT_CLONE.md — Passo 2.",
            train_path,
            val_path,
        )
        sys.exit(1)

    LOG.info("Fase 4: Fine-tuning Unsloth — train=%s, val=%s, output=%s", train_path, val_path, output_dir)

    from src.finetuning.data_loader import load_dataset_for_unsloth
    from src.finetuning.train import run_training
    from src.finetuning.export_gguf import merge_and_export_gguf

    train_ds, val_ds = load_dataset_for_unsloth(train_path, val_path)
    LOG.info("Dataset carregado: train=%s, val=%s exemplos", len(train_ds), len(val_ds))

    trainer = run_training(
        train_ds,
        val_ds,
        params["output_dir"],
        model_name=params["model_name"],
        use_qlora=params["use_qlora"],
        max_seq_length=params["max_seq_length"],
        lora_rank=params["lora_rank"],
        lora_alpha=params["lora_alpha"],
        lora_dropout=params["lora_dropout"],
        target_modules=params["target_modules"],
        learning_rate=params["learning_rate"],
        epochs=params["epochs"],
        per_device_train_batch_size=params["per_device_train_batch_size"],
        gradient_accumulation_steps=params["gradient_accumulation_steps"],
        logging_steps=params["logging_steps"],
        save_steps=params["save_steps"],
        save_strategy=params["save_strategy"],
    )

    if not args.skip_gguf:
        gguf_dir = output_dir / "gguf"
        gguf_dir.mkdir(parents=True, exist_ok=True)
        out_gguf = merge_and_export_gguf(
            trainer,
            trainer.tokenizer,
            gguf_dir,
            quantization_method=params.get("gguf_quantization", "q4_k_m"),
        )
        LOG.info("GGUF exportado: %s", out_gguf)

    log_dir = PROJECT_ROOT / "log"
    log_dir.mkdir(exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    metrics_path = log_dir / f"phase4_finetuning_{ts}.json"
    metrics = {
        "phase": "Fase 4 - Fine-tuning",
        "train_path": str(train_path),
        "val_path": str(val_path),
        "output_dir": str(output_dir),
        "train_examples": len(train_ds),
        "val_examples": len(val_ds),
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    LOG.info("Métricas em %s", metrics_path)


if __name__ == "__main__":
    main()
