"""
Teste rápido do motor de inferência via Ollama (Qwen 2.5 / Qwen3.x).

Uso (na raiz do projeto):
  python scripts/test_inference_ollama.py

Pré-requisitos:
- Ollama rodando em http://localhost:11434
- Modelo configurado em configs/default.yaml (dataset_gen.llm_model), ex.:
    llm_model: qwen2.5:latest
  e já puxado com:
    ollama pull qwen2.5:latest
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.config_loader import load_config
from src.dataset_gen.generator import call_llm


def main() -> None:
  config = load_config()
  neo_cfg = config.get("neo4j", {})
  system_prompt_path = neo_cfg.get("system_prompt_path")
  system_prompt = ""
  if system_prompt_path:
    try:
      with open(system_prompt_path, encoding="utf-8") as f:
        system_prompt = f.read()
    except FileNotFoundError:
      system_prompt = ""

  user_prompt = (
    "Explique brevemente, em linguagem técnica, qual é o papel da Engenharia de Sistemas "
    "no contexto de um projeto espacial, segundo o NASA Systems Engineering Handbook."
  )

  response = call_llm(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=256, config=config)
  print("=== RESPOSTA DO LLM (Ollama) ===")
  print(response)


if __name__ == "__main__":
  main()

