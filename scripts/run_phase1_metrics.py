"""
Coleta métricas da Fase 1 (Ingestão) e executa validação do Checkpoint 1.
Registra resultados em log/ (métricas em JSON, resultado do checkpoint e resumo).
Uso: python scripts/run_phase1_metrics.py
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_phase1_metrics() -> dict:
    """Coleta métricas a partir de data/markdown e data/chunks."""
    metrics = {
        "phase": "Fase 1 - Ingestão Estruturada",
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "markdown": {},
        "chunks": {},
        "checkpoint1": {},
    }

    md_dir = PROJECT_ROOT / "data" / "markdown"
    chunks_dir = PROJECT_ROOT / "data" / "chunks"

    # Métricas dos arquivos Markdown (excluindo test.md)
    md_files = [f for f in md_dir.glob("*.md") if f.name != "test.md"]
    if md_files:
        total_md_chars = 0
        total_md_bytes = 0
        for f in md_files:
            content = f.read_text(encoding="utf-8")
            total_md_chars += len(content)
            total_md_bytes += f.stat().st_size
        metrics["markdown"] = {
            "files_count": len(md_files),
            "file_names": [f.name for f in md_files],
            "total_characters": total_md_chars,
            "total_bytes": total_md_bytes,
            "approx_pages_assumption_3000_chars": round(total_md_chars / 3000, 1),
        }

    # Métricas dos chunks JSONL (excluindo test_chunks.jsonl)
    jsonl_files = [f for f in chunks_dir.glob("*.jsonl") if "test" not in f.name.lower()]
    if jsonl_files:
        all_chunks = []
        for f in jsonl_files:
            with open(f, encoding="utf-8") as fp:
                for line in fp:
                    line = line.strip()
                    if line:
                        all_chunks.append(json.loads(line))
        token_counts = []
        section_levels = []
        appendix_count = 0
        for ch in all_chunks:
            text = ch.get("text", "")
            # Aproximação de tokens: ~4 chars por token para inglês
            token_counts.append(len(text) // 4)
            meta = ch.get("metadata", {})
            section_levels.append(meta.get("section_level", 0))
            if meta.get("appendix"):
                appendix_count += 1
        metrics["chunks"] = {
            "files_count": len(jsonl_files),
            "file_names": [f.name for f in jsonl_files],
            "total_chunks": len(all_chunks),
            "total_chars": sum(len(c.get("text", "")) for c in all_chunks),
            "tokens_approx_min": min(token_counts) if token_counts else 0,
            "tokens_approx_max": max(token_counts) if token_counts else 0,
            "tokens_approx_mean": round(sum(token_counts) / len(token_counts), 1) if token_counts else 0,
            "chunks_with_appendix_metadata": appendix_count,
            "section_levels_present": len(set(s for s in section_levels if s is not None)),
        }
        metrics["chunks"]["jsonl_file_bytes"] = sum(f.stat().st_size for f in jsonl_files)

    return metrics


def run_checkpoint1_validation() -> tuple[bool, str]:
    """Executa tests/test_checkpoint1.py e retorna (passed, output)."""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "tests" / "test_checkpoint1.py")],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


def run_pytest_phase1(log_dir: Path, ts: str) -> tuple[bool, str]:
    """Executa pytest nos testes da Fase 1 e grava JUnit XML em log_dir."""
    junit_path = log_dir / f"pytest_phase1_{ts}.xml"
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            str(PROJECT_ROOT / "tests" / "test_config_loader.py"),
            str(PROJECT_ROOT / "tests" / "test_chunker_unit.py"),
            "-v",
            f"--junitxml={junit_path}",
            "--tb=short",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    out = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, out


def main():
    log_dir = PROJECT_ROOT / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # 1) Coletar métricas
    metrics = get_phase1_metrics()
    metrics_path = log_dir / f"metrics_phase1_{ts}.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"Métricas gravadas em: {metrics_path}")

    # 2) Executar validação Checkpoint 1
    checkpoint_passed, checkpoint_output = run_checkpoint1_validation()
    metrics["checkpoint1"] = {
        "passed": checkpoint_passed,
        "output_summary": checkpoint_output.strip()[-800:] if checkpoint_output else "",
    }
    # Atualizar JSON com resultado do checkpoint
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    # 3) Salvar saída completa do checkpoint em log
    checkpoint_log = log_dir / f"checkpoint1_phase1_{ts}.txt"
    with open(checkpoint_log, "w", encoding="utf-8") as f:
        f.write(checkpoint_output)
    print(f"Checkpoint 1 resultado: {'PASSOU' if checkpoint_passed else 'FALHOU'}")
    print(f"Log do checkpoint: {checkpoint_log}")

    # 4) Executar pytest (testes unitários + checkpoint) e gravar JUnit XML
    pytest_passed = False
    pytest_output = ""
    try:
        pytest_passed, pytest_output = run_pytest_phase1(log_dir, ts)
        junit_path = log_dir / f"pytest_phase1_{ts}.xml"
        if junit_path.exists():
            print(f"Pytest JUnit XML: {junit_path}")
        print(f"Pytest: {'PASSOU' if pytest_passed else 'FALHOU'}")
    except Exception as e:
        pytest_output = str(e)
        with open(log_dir / f"pytest_phase1_{ts}_error.txt", "w", encoding="utf-8") as f:
            f.write(pytest_output)

    metrics["pytest"] = {"passed": pytest_passed, "output_preview": pytest_output[-500:] if pytest_output else ""}
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    # 5) Resumo em texto
    summary_path = log_dir / f"summary_phase1_{ts}.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("=== Fase 1 - Resumo de Métricas e Testes ===\n\n")
        f.write(f"Data: {metrics['collected_at']}\n\n")
        f.write("Markdown:\n")
        for k, v in metrics.get("markdown", {}).items():
            f.write(f"  {k}: {v}\n")
        f.write("\nChunks:\n")
        for k, v in metrics.get("chunks", {}).items():
            f.write(f"  {k}: {v}\n")
        f.write(f"\nCheckpoint 1: {'PASSOU' if checkpoint_passed else 'FALHOU'}\n")
        f.write(f"Pytest (unitários + checkpoint): {'PASSOU' if pytest_passed else 'FALHOU'}\n")
        f.write(f"\nMétricas completas: {metrics_path.name}\n")
        f.write(f"Log checkpoint: {checkpoint_log.name}\n")
    print(f"Resumo: {summary_path}")

    return 0 if (checkpoint_passed and pytest_passed) else 1


if __name__ == "__main__":
    sys.exit(main())
