"""
ModelChain — Multi-model Bytez AI fallback chain for HackEmpire X v4.

Priority order (all free on Bytez):
  1. Qwen/Qwen3-4B          — fast, good reasoning
  2. mistralai/Mistral-7B-Instruct-v0.3 — deep analysis
  3. google/gemma-3-4b-it   — reliable instruction following
  4. openai/gpt-4o-mini     — smart, free tier
  5. openai/gpt-4.1-mini    — best quality, free tier

If all 5 fail → OpenRouter fallback → Offline KB.
Total budget: 90 seconds across all 5 models.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from hackempire.ai.bytez_client import BytezClient
from hackempire.core.models import ModelResult

logger = logging.getLogger(__name__)

# Ordered list of free Bytez models — tried in this exact sequence
BYTEZ_FREE_MODELS: list[str] = [
    "Qwen/Qwen3-4B",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "google/gemma-3-4b-it",
    "openai/gpt-4o-mini",
    "openai/gpt-4.1-mini",
]

# Total time budget for all 5 models combined
TOTAL_BUDGET_S: float = 90.0

# Per-model timeout — each model gets at most this long
PER_MODEL_TIMEOUT_S: float = 20.0


class ModelChain:
    """
    Tries Bytez free models in priority order until one succeeds.

    Usage:
        chain = ModelChain(api_key="bz-xxx")
        result = chain.send("Your prompt here")
        # result.model_name tells you which model responded
        # result.provider == "bytez"
    """

    # Class-level constants (spec requirement: ModelChain.MODELS, ModelChain.TIMEOUT_S)
    MODELS: list[str] = BYTEZ_FREE_MODELS
    TIMEOUT_S: float = TOTAL_BUDGET_S

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        # One BytezClient per model — all share the same key
        self._clients: list[tuple[str, BytezClient]] = [
            (model_id, BytezClient(api_key=api_key, model=model_id, timeout_s=PER_MODEL_TIMEOUT_S))
            for model_id in BYTEZ_FREE_MODELS
        ]

    def send(self, prompt: str) -> ModelResult:
        """
        Send prompt through the model chain.

        Returns ModelResult with:
          - raw_text: the AI response
          - status_code: HTTP status of the successful call
          - model_name: which model responded
          - provider: "bytez"

        If all models fail, returns ModelResult with empty raw_text,
        status_code=0, model_name="", provider="bytez_exhausted".
        Never raises.
        """
        if not prompt.strip():
            return ModelResult(raw_text="", status_code=0, model_name="", provider="bytez_exhausted")

        budget_start = time.monotonic()

        for model_id, client in self._clients:
            # Check remaining budget before each attempt
            elapsed = time.monotonic() - budget_start
            if elapsed >= TOTAL_BUDGET_S:
                logger.warning("[model_chain] Budget exhausted (%.1fs) — skipping remaining models", elapsed)
                break

            try:
                logger.debug("[model_chain] Trying model: %s", model_id)
                resp = client.send_request(prompt)
                status = resp.get("status_code", 0)
                text = resp.get("raw_text", "")

                if status == 200 and text:
                    logger.info("[model_chain] Success with model: %s", model_id)
                    return ModelResult(
                        raw_text=text,
                        status_code=status,
                        model_name=model_id,
                        provider="bytez",
                    )

                logger.debug("[model_chain] Model %s returned status=%s, empty=%s — trying next",
                             model_id, status, not text)

            except Exception as exc:
                logger.debug("[model_chain] Model %s raised %s — trying next", model_id, exc)

        # All models exhausted
        logger.warning("[model_chain] All %d Bytez models failed", len(self._clients))
        return ModelResult(raw_text="", status_code=0, model_name="", provider="bytez_exhausted")

    @property
    def models(self) -> list[str]:
        """Return the ordered list of model IDs in this chain."""
        return [m for m, _ in self._clients]
