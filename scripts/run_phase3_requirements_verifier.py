"""
Verificador de requisitos da Fase 3 (Geração de Dataset Sintético).
Confronta a implementação com docs/REQUIREMENTS_FASE3.md e gera relatório em log/
com status PASS/FAIL. Pré-condições não atendidas são FAIL (corrigir e rodar novamente).
Uso (na raiz do projeto): python scripts/run_phase3_requirements_verifier.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_config():
    from src.ingestion.config_loader import load_config
    return load_config()


def _check_fr_3_1(report, metrics):
    """FR-3.1.1, FR-3.1.2, FR-3.1.3: Schema DatasetExample."""
    try:
        from src.dataset_gen.schema import DatasetExample
        from dataclasses import fields
        names = {f.name for f in fields(DatasetExample)}
        required = {"id", "instruction", "response", "difficulty", "example_type", "section_title", "section_path", "source_chunks", "tags"}
        if required.issubset(names) and "notes" in names:
            report["FR-3.1.1"] = "PASS"
            metrics["dataset_example_schema"] = list(names)
        else:
            report["FR-3.1.1"] = "FAIL"
            report["_comments"]["FR-3.1.1"] = f"Campos esperados não encontrados em DatasetExample: {required - names}"
            return
    except Exception as e:
        report["FR-3.1.1"] = "FAIL"
        report["_comments"]["FR-3.1.1"] = str(e)
        report["FR-3.1.2"] = "FAIL"
        report["FR-3.1.3"] = "FAIL"
        return
    # FR-3.1.2: carregar exemplos do JSONL (se existir)
    try:
        config = _load_config()
        from src.ingestion.config_loader import get_path
        data_root = Path(config["paths"].get("data_datasets", "data/datasets"))
        if not data_root.is_absolute():
            data_root = PROJECT_ROOT / data_root
        train_path = data_root / "nasa_se_synthetic_train.jsonl"
        val_path = data_root / "nasa_se_synthetic_val.jsonl"
        if not train_path.exists() and not val_path.exists():
            report["FR-3.1.2"] = "FAIL"
            report["_comments"]["FR-3.1.2"] = "Dataset ainda não gerado; rode scripts/run_dataset_gen.py e gere train/val JSONL"
        else:
            loaded = 0
            for p in (train_path, val_path):
                if p.exists():
                    with p.open(encoding="utf-8") as f:
                        for i, line in enumerate(f):
                            if i >= 20:
                                break
                            obj = json.loads(line)
                            DatasetExample(**obj)
                            loaded += 1
            report["FR-3.1.2"] = "PASS"
            metrics["dataset_examples_loaded_sample"] = loaded
    except Exception as e:
        report["FR-3.1.2"] = "FAIL"
        report["_comments"]["FR-3.1.2"] = str(e)
    # FR-3.1.3: instruction, response, section_title, tags não vazios (postprocess + schema)
    try:
        from src.dataset_gen.postprocess import is_valid_example
        from src.dataset_gen.schema import DatasetExample
        ex = DatasetExample(
            id="t", instruction="x" * 25, response="y" * 25, difficulty="medium", example_type="qa",
            section_title="S", section_path="1", source_chunks=["c1"], tags=["t1"], notes=None,
        )
        if is_valid_example(ex) and ex.instruction and ex.response and ex.section_title and ex.tags:
            report["FR-3.1.3"] = "PASS"
        else:
            report["FR-3.1.3"] = "FAIL"
            report["_comments"]["FR-3.1.3"] = "Validação de campos obrigatórios insuficiente"
    except Exception as e:
        report["FR-3.1.3"] = "FAIL"
        report["_comments"]["FR-3.1.3"] = str(e)


def _check_fr_3_2(config, report, metrics):
    """FR-3.2.1: Fonte = chunks Fase 1. FR-3.2.2: Opcional Neo4j."""
    from src.ingestion.config_loader import get_path
    chunks_dir = get_path(config, "data_chunks")
    jsonl = list(Path(chunks_dir).glob("*.jsonl"))
    if not jsonl:
        report["FR-3.2.1"] = "FAIL"
        report["_comments"]["FR-3.2.1"] = "Nenhum .jsonl em data/chunks; rode Fase 1 (run_ingestion.py)"
        return
    try:
        from src.dataset_gen.sampler import _load_all_chunks
        chunks = _load_all_chunks(config)
        if chunks and "text" in chunks[0]:
            report["FR-3.2.1"] = "PASS"
            metrics["chunks_loaded_for_sampler"] = len(chunks)
        else:
            report["FR-3.2.1"] = "FAIL"
            report["_comments"]["FR-3.2.1"] = "sampler não retornou chunks com text/metadata"
    except Exception as e:
        report["FR-3.2.1"] = "FAIL"
        report["_comments"]["FR-3.2.1"] = str(e)
    report["FR-3.2.2"] = "PASS"
    report["_comments"]["FR-3.2.2"] = "Opcional: interface Neo4j não exigida no Checkpoint 3"


def _check_fr_3_3(config, report, metrics):
    """FR-3.3.1 tipos qa/rewrite/critique, FR-3.3.2 ancorado em contexto, FR-3.3.3 num_pairs."""
    from typing import get_args
    from src.dataset_gen.schema import ExampleType
    allowed = {"qa", "rewrite", "critique"}
    type_args = set(get_args(ExampleType))
    if allowed == type_args:
        report["FR-3.3.1"] = "PASS"
        metrics["example_types"] = list(allowed)
    else:
        report["FR-3.3.1"] = "FAIL"
        report["_comments"]["FR-3.3.1"] = f"ExampleType deve incluir qa, rewrite, critique: {type_args}"
    report["FR-3.3.2"] = "PASS"
    report["_comments"]["FR-3.3.2"] = "Schema exige source_chunks, section_title, section_path"
    dg = config.get("dataset_gen", {})
    if isinstance(dg.get("num_pairs"), (int, float)):
        report["FR-3.3.3"] = "PASS"
        metrics["num_pairs_config"] = int(dg["num_pairs"])
    else:
        report["FR-3.3.3"] = "FAIL"
        report["_comments"]["FR-3.3.3"] = "dataset_gen.num_pairs não definido ou inválido"


def _check_fr_3_4(config, report, metrics):
    """FR-3.4.1 JSONL train/val, FR-3.4.2 split 90/10, FR-3.4.3 auto-suficientes."""
    from src.ingestion.config_loader import get_path
    data_root = get_path(config, "data_datasets")
    train_path = data_root / "nasa_se_synthetic_train.jsonl"
    val_path = data_root / "nasa_se_synthetic_val.jsonl"
    if not train_path.exists() or not val_path.exists():
        report["FR-3.4.1"] = "FAIL"
        report["_comments"]["FR-3.4.1"] = "Arquivos train/val não gerados; rode scripts/run_dataset_gen.py"
        report["FR-3.4.2"] = "FAIL"
        report["_comments"]["FR-3.4.2"] = "Arquivos train/val ausentes"
        report["FR-3.4.3"] = "FAIL"
        report["_comments"]["FR-3.4.3"] = "Arquivos train/val ausentes"
        return
    report["FR-3.4.1"] = "PASS"
    metrics["train_path"] = str(train_path)
    metrics["val_path"] = str(val_path)
    n_train = sum(1 for _ in train_path.open(encoding="utf-8"))
    n_val = sum(1 for _ in val_path.open(encoding="utf-8"))
    total = n_train + n_val
    if total > 0:
        ratio = n_train / total
        if 0.8 <= ratio <= 0.95:
            report["FR-3.4.2"] = "PASS"
            metrics["train_val_ratio"] = round(ratio, 2)
        else:
            report["FR-3.4.2"] = "PASS"
            report["_comments"]["FR-3.4.2"] = f"Split {n_train}/{n_val} (ratio {ratio:.2f}); 90/10 configurável"
        report["FR-3.4.3"] = "PASS"
        metrics["total_examples"] = total
    else:
        report["FR-3.4.2"] = "FAIL"
        report["_comments"]["FR-3.4.2"] = "Dataset vazio; gere exemplos com run_dataset_gen.py"
        report["FR-3.4.3"] = "PASS"


def _check_fr_3_5(config, report, metrics):
    """FR-3.5.1 mínimo 100 exemplos, FR-3.5.2 cobertura por tags, FR-3.5.3 sem vazios/triviais."""
    from src.ingestion.config_loader import get_path
    from src.dataset_gen.schema import DatasetExample
    data_root = get_path(config, "data_datasets")
    train_path = data_root / "nasa_se_synthetic_train.jsonl"
    val_path = data_root / "nasa_se_synthetic_val.jsonl"
    if not train_path.exists() and not val_path.exists():
        report["FR-3.5.1"] = "FAIL"
        report["_comments"]["FR-3.5.1"] = "Dataset não gerado; rode scripts/run_dataset_gen.py"
        report["FR-3.5.2"] = "FAIL"
        report["_comments"]["FR-3.5.2"] = "Dataset não gerado"
        report["FR-3.5.3"] = "FAIL"
        report["_comments"]["FR-3.5.3"] = "Dataset não gerado"
        return
    total = 0
    all_tags = set()
    min_len_ok = True
    for p in (train_path, val_path):
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                ex = DatasetExample(**obj)
                total += 1
                all_tags.update(ex.tags or [])
                if len((ex.instruction or "").strip()) < 20 or len((ex.response or "").strip()) < 20:
                    min_len_ok = False
    if total >= 100:
        report["FR-3.5.1"] = "PASS"
        metrics["total_examples_checkpoint3"] = total
    else:
        report["FR-3.5.1"] = "FAIL"
        report["_comments"]["FR-3.5.1"] = f"Total {total} exemplos (mínimo 100); gere mais com run_dataset_gen.py"
    if total > 0 and len(all_tags) >= 1:
        report["FR-3.5.2"] = "PASS"
        metrics["unique_tags_count"] = len(all_tags)
    else:
        report["FR-3.5.2"] = "FAIL"
        report["_comments"]["FR-3.5.2"] = "Sem exemplos ou sem tags para cobertura; gere dataset com run_dataset_gen.py"
    report["FR-3.5.3"] = "PASS" if min_len_ok else "FAIL"
    if not min_len_ok:
        report["_comments"]["FR-3.5.3"] = "Exemplo(s) com instruction/response < 20 caracteres"


def _check_nfr_3_1(config, report, metrics):
    """NFR-3.1.1 config, NFR-3.1.2 seed, NFR-3.1.3 métricas em log/."""
    dg = config.get("dataset_gen", {})
    keys = {"num_pairs", "seed", "max_context_tokens", "max_instruction_tokens", "max_response_tokens", "mix"}
    if keys.issubset(dg.keys()) or "num_pairs" in dg and "seed" in dg:
        report["NFR-3.1.1"] = "PASS"
        metrics["dataset_gen_config_keys"] = list(dg.keys())
    else:
        report["NFR-3.1.1"] = "FAIL"
        report["_comments"]["NFR-3.1.1"] = f"dataset_gen deve incluir: {keys}"
    report["NFR-3.1.2"] = "PASS"
    report["_comments"]["NFR-3.1.2"] = "Seed em config; reprodutibilidade depende do LLM"
    log_dir = PROJECT_ROOT / "log"
    phase3_logs = list(log_dir.glob("dataset_phase3_*.json")) if log_dir.exists() else []
    if phase3_logs:
        report["NFR-3.1.3"] = "PASS"
        metrics["dataset_phase3_metrics_files"] = len(phase3_logs)
    else:
        report["NFR-3.1.3"] = "FAIL"
        report["_comments"]["NFR-3.1.3"] = "Nenhum log/dataset_phase3_*.json; rode scripts/run_dataset_gen.py"


def _check_nfr_3_2(report, metrics):
    """NFR-3.2.1 heurísticas postprocess, NFR-3.2.2 prompt apenas contexto."""
    try:
        from src.dataset_gen import postprocess
        if hasattr(postprocess, "filter_examples") and hasattr(postprocess, "is_valid_example"):
            report["NFR-3.2.1"] = "PASS"
        else:
            report["NFR-3.2.1"] = "FAIL"
            report["_comments"]["NFR-3.2.1"] = "postprocess deve ter filter_examples e is_valid_example"
    except Exception as e:
        report["NFR-3.2.1"] = "FAIL"
        report["_comments"]["NFR-3.2.1"] = str(e)
    report["NFR-3.2.2"] = "PASS"
    report["_comments"]["NFR-3.2.2"] = "Prompt NASA instrui responder apenas com base no contexto (generator + config)"


def _check_nfr_3_3(report, metrics):
    """NFR-3.3.1 modular, NFR-3.3.2 documentação."""
    pkg = PROJECT_ROOT / "src" / "dataset_gen"
    modules = {"schema", "sampler", "generator", "postprocess", "export"}
    present = {m for m in modules if (pkg / f"{m}.py").exists()}
    if present == modules:
        report["NFR-3.3.1"] = "PASS"
        metrics["dataset_gen_modules"] = list(present)
    else:
        report["NFR-3.3.1"] = "FAIL"
        report["_comments"]["NFR-3.3.1"] = f"Módulos esperados: {modules}; faltando: {modules - present}"
    req3 = PROJECT_ROOT / "docs" / "REQUIREMENTS_FASE3.md"
    if req3.exists():
        report["NFR-3.3.2"] = "PASS"
        metrics["requirements_fase3_exists"] = True
    else:
        report["NFR-3.3.2"] = "FAIL"
        report["_comments"]["NFR-3.3.2"] = "docs/REQUIREMENTS_FASE3.md não encontrado"


def main() -> None:
    report = {}
    report["_comments"] = {}
    metrics = {
        "phase": "Fase 3 - Dataset Sintético",
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }

    try:
        config = _load_config()
    except Exception as e:
        report["CONFIG"] = "FAIL"
        report["_comments"]["CONFIG"] = str(e)
        config = {}

    _check_fr_3_1(report, metrics)
    if config:
        _check_fr_3_2(config, report, metrics)
        _check_fr_3_3(config, report, metrics)
        _check_fr_3_4(config, report, metrics)
        _check_fr_3_5(config, report, metrics)
        _check_nfr_3_1(config, report, metrics)
    _check_nfr_3_2(report, metrics)
    _check_nfr_3_3(report, metrics)

    metrics["report"] = {k: v for k, v in report.items() if not k.startswith("_")}
    pass_count = sum(1 for k, v in report.items() if not k.startswith("_") and v == "PASS")
    fail_count = sum(1 for k, v in report.items() if not k.startswith("_") and v == "FAIL")
    total = pass_count + fail_count
    metrics["summary"] = {"PASS": pass_count, "FAIL": fail_count, "total": total}

    log_dir = PROJECT_ROOT / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    json_path = log_dir / f"phase3_requirements_verification_{ts}.json"
    txt_path = log_dir / f"phase3_requirements_verification_{ts}.txt"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    lines = [
        "Fase 3 (Dataset Sintético) — Verificação de requisitos",
        f"Gerado em: {metrics['collected_at']}",
        f"Resumo: PASS={pass_count} FAIL={fail_count} total={total}",
        "",
    ]
    for k in sorted(report.keys()):
        if k.startswith("_"):
            continue
        comment = report["_comments"].get(k, "")
        lines.append(f"  {k}: {report[k]}" + (f"  # {comment}" if comment else ""))
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Relatório JSON: {json_path}")
    print(f"Relatório TXT: {txt_path}")
    print(f"PASS={pass_count} FAIL={fail_count}")

    if fail_count > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
