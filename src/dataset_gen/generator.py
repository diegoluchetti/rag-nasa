"""
Gerador de exemplos sintéticos (Fase 3).

IMPORTANTE: este módulo define a orquestração, mas não acopla um LLM específico.
Por padrão, a função de geração retorna None (no-op). Para uso real, o usuário
deve plugar um cliente OpenAI/Azure ou modelo local e implementar a função
`call_llm` abaixo.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

from src.ingestion.config_loader import load_config
from src.dataset_gen.schema import DatasetExample, Difficulty, ExampleType
from src.dataset_gen.sampler import ContextSpec, sample_contexts_by_section

LOG = logging.getLogger(__name__)


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int, config: Dict[str, Any] | None = None) -> str:
  """
  Chama o LLM via Ollama (http://localhost:11434/api/generate).

  Requer que o modelo especificado em dataset_gen.llm_model esteja disponível no Ollama,
  ex.: `ollama pull qwen2.5:latest`.
  """
  if config is None:
    config = load_config()
  cfg_gen: Dict[str, Any] = config.get("dataset_gen", {})
  model = cfg_gen.get("llm_model", "qwen2.5:latest")
  temperature = float(cfg_gen.get("temperature", 0.3))

  payload = {
    "model": model,
    "system": system_prompt or "",
    "prompt": user_prompt,
    "stream": False,
    "options": {
      "temperature": temperature,
      "num_predict": max_tokens,
    },
  }

  data = json.dumps(payload).encode("utf-8")
  req = Request(
    "http://localhost:11434/api/generate",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
  )
  try:
    with urlopen(req, timeout=120) as resp:
      resp_text = resp.read().decode("utf-8")
      obj = json.loads(resp_text)
      return obj.get("response", "").strip()
  except HTTPError as e:
    LOG.error("Erro HTTP ao chamar Ollama: %s", e)
    raise
  except URLError as e:
    LOG.error("Erro de conexão ao chamar Ollama (está rodando em localhost:11434?): %s", e)
    raise


def _default_difficulty() -> Difficulty:
  return "medium"


def _default_example_type() -> ExampleType:
  return "qa"


def generate_example_from_context(
  ctx: ContextSpec,
  system_prompt: str,
  max_instruction_tokens: int,
  max_response_tokens: int,
  example_type: ExampleType | None = None,
  use_llm: bool = True,
) -> DatasetExample | None:
  """
  Gera um único exemplo a partir de um ContextSpec.
  Se use_llm=False, usa fallback (exemplo sintético) sem chamar o LLM.
  """
  etype: ExampleType = example_type or _default_example_type()

  response: str | None = None
  if use_llm:
    user_prompt = (
      "Você receberá um trecho do NASA Systems Engineering Handbook como contexto.\n"
      "Gere uma pergunta útil de engenharia de sistemas sobre esse contexto e responda-a em seguida.\n\n"
      f"Contexto:\n{ctx.text}\n"
    )
    try:
      response = call_llm(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_response_tokens, config=None)
    except Exception:
      LOG.warning("LLM indisponível para ctx=%s; usando fallback (exemplo sintético).", ctx.id)

  instruction_text = "Pergunta e resposta geradas a partir do contexto fornecido do NASA SE Handbook."
  # Fallback sem LLM: gera exemplo válido a partir do contexto (permite verificação sem Ollama).
  if not response or not response.strip():
    min_len = 25
    response = (ctx.text.strip()[:500] + ("..." if len(ctx.text) > 500 else "")) or "Content from NASA SE Handbook."
    if len(response) < min_len:
      response = response + " " * (min_len - len(response))
    instruction_text = "What is the main content of this section from the NASA SE Handbook?"

  ex = DatasetExample(
    id=str(uuid.uuid4()),
    instruction=instruction_text,
    response=response.strip(),
    difficulty=_default_difficulty(),
    example_type=etype,
    section_title=ctx.section_title,
    section_path=ctx.section_path,
    source_chunks=ctx.source_chunks,
    tags=ctx.tags or ["generated"],
    notes=None,
  )
  return ex


def generate_dataset(
  num_pairs: int,
  seed: int,
  config_name: str = "default",
) -> List[DatasetExample]:
  """
  Orquestra geração de um dataset de tamanho aproximado num_pairs.

  Estratégia:
  - Amostrar contextos por seção.
  - Para cada contexto, tentar gerar 1 exemplo.
  - Parar quando atingir num_pairs ou esgotar contextos.

  No estado atual, a função retorna lista vazia (stub).
  """
  config = load_config(config_name)
  cfg_gen: Dict[str, Any] = config.get("dataset_gen", {})
  max_instruction_tokens = int(cfg_gen.get("max_instruction_tokens", 128))
  max_response_tokens = int(cfg_gen.get("max_response_tokens", 512))
  use_llm = cfg_gen.get("use_llm", True)

  # Carregar prompt NASA (pode ser reutilizado aqui para guiar o LLM no futuro)
  neo_cfg = config.get("neo4j", {})
  system_prompt_path = neo_cfg.get("system_prompt_path")
  system_prompt = ""
  if system_prompt_path:
    try:
      with open(system_prompt_path, encoding="utf-8") as f:
        system_prompt = f.read()
    except FileNotFoundError:
      LOG.warning("System prompt NASA não encontrado em %s", system_prompt_path)

  contexts = sample_contexts_by_section(num_pairs, seed=seed, config_name=config_name)
  examples: List[DatasetExample] = []
  for ctx in contexts:
    ex = generate_example_from_context(
      ctx=ctx,
      system_prompt=system_prompt,
      max_instruction_tokens=max_instruction_tokens,
      max_response_tokens=max_response_tokens,
      use_llm=use_llm,
    )
    if ex is None:
      continue
    if not ex.id:
      ex.id = str(uuid.uuid4())
    examples.append(ex)
    if len(examples) >= num_pairs:
      break

  LOG.info("Geração Fase 3 concluída: %s exemplos.", len(examples))
  return examples

