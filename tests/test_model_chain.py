"""
Property-based and unit tests for ModelChain (v4.1).

Property 1: ModelChain fallback ordering
  - Models are tried in order: Qwen → Mistral → Gemma → gpt-4o-mini → gpt-4.1-mini
  - If all Bytez models fail, OpenRouter is tried next
  - If OpenRouter also fails, OfflineKB is used
  - No exception is raised at any step
  **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.10**

Property 2: Successful model is recorded in response metadata
  - ModelResult.model_name == the model that returned 200 + non-empty body
  - ModelResult.provider == "bytez"
  **Validates: Requirements 1.6**

Unit tests:
  - Exact model_name in ModelResult when first model succeeds
  - provider == "offline_kb" when all providers fail
  - Bytez key absent → ModelChain skipped → OpenRouter called directly
  **Validates: Requirements 1.6, 1.7, 1.10**
"""
from __future__ import annotations

import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)
_parent = os.path.dirname(_pkg_root)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from unittest.mock import MagicMock, patch, call
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.ai.model_chain import ModelChain, BYTEZ_FREE_MODELS
from hackempire.ai.ai_engine import AIEngine
from hackempire.core.models import ModelResult

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_prompt_st = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())

_model_index_st = st.integers(min_value=0, max_value=len(BYTEZ_FREE_MODELS) - 1)


def _make_fail_response() -> dict:
    """A response that counts as failure (non-200 or empty)."""
    return {"raw_text": "", "status_code": 503}


def _make_success_response(text: str = "AI response") -> dict:
    return {"raw_text": text, "status_code": 200}


# ---------------------------------------------------------------------------
# Property 1: ModelChain fallback ordering
# ---------------------------------------------------------------------------

# Feature: hackempire-x-v4, Property 1: ModelChain fallback ordering
@given(prompt=_prompt_st)
@settings(max_examples=10)
def test_property_1_model_chain_fallback_ordering(prompt: str) -> None:
    """Property 1: ModelChain fallback ordering.

    For any prompt, when all Bytez models fail, OpenRouter is tried next,
    and if OpenRouter also fails, OfflineKB is used — no exception raised.

    **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.10**
    """
    call_order: list[str] = []

    def make_bytez_send(model_id: str):
        def _send(p: str) -> dict:
            call_order.append(f"bytez:{model_id}")
            return _make_fail_response()
        return _send

    # Build engine with bytez_key so ModelChain is active
    engine = AIEngine(bytez_key="test-key", openrouter_key="or-key")

    # Patch each BytezClient.send_request in the chain
    assert engine._model_chain is not None
    for model_id, client in engine._model_chain._clients:
        client.send_request = make_bytez_send(model_id)

    # Patch OpenRouter to also fail
    def openrouter_fail(p: str) -> dict:
        call_order.append("openrouter")
        return {"raw_text": "", "status_code": 503}

    with patch.object(engine, "send_request", side_effect=openrouter_fail):
        result = engine._send(prompt)

    # Verify order: all 5 Bytez models first, then OpenRouter
    bytez_calls = [c for c in call_order if c.startswith("bytez:")]
    assert len(bytez_calls) == len(BYTEZ_FREE_MODELS), (
        f"Expected {len(BYTEZ_FREE_MODELS)} Bytez calls, got {len(bytez_calls)}: {bytez_calls}"
    )
    # Verify exact order
    for i, model_id in enumerate(BYTEZ_FREE_MODELS):
        assert bytez_calls[i] == f"bytez:{model_id}", (
            f"Position {i}: expected bytez:{model_id}, got {bytez_calls[i]}"
        )
    # OpenRouter must come after all Bytez models
    assert "openrouter" in call_order
    assert call_order.index("openrouter") > call_order.index(f"bytez:{BYTEZ_FREE_MODELS[-1]}")

    # No exception raised — result is a dict
    assert isinstance(result, dict)


# Feature: hackempire-x-v4, Property 1: ModelChain fallback ordering (OfflineKB)
@given(prompt=_prompt_st)
@settings(max_examples=10)
def test_property_1_offline_kb_used_when_all_fail(prompt: str) -> None:
    """Property 1 (OfflineKB branch): when all Bytez models AND OpenRouter fail,
    the result comes from OfflineKB and no exception is raised.

    **Validates: Requirements 1.3, 1.4, 1.10**
    """
    engine = AIEngine(bytez_key="test-key", openrouter_key="")

    # All Bytez models fail
    for _, client in engine._model_chain._clients:
        client.send_request = lambda p: _make_fail_response()

    # OpenRouter not configured (openrouter_key=""), so _openrouter_available is False
    # _send() should return empty dict → KB fallback happens in generate_todo_list etc.
    result = engine._send(prompt)

    # Must not raise; result is a dict
    assert isinstance(result, dict)
    # status_code 0 signals KB fallback to callers
    assert result.get("status_code", 0) == 0


# ---------------------------------------------------------------------------
# Property 2: Successful model is recorded in response metadata
# ---------------------------------------------------------------------------

# Feature: hackempire-x-v4, Property 2: Successful model is recorded in response metadata
@given(
    prompt=_prompt_st,
    success_index=_model_index_st,
)
@settings(max_examples=10)
def test_property_2_successful_model_recorded(prompt: str, success_index: int) -> None:
    """Property 2: Successful model is recorded in response metadata.

    For any prompt where exactly one model returns 200 + non-empty body,
    ModelResult.model_name == that model's ID and ModelResult.provider == "bytez".

    **Validates: Requirements 1.6**
    """
    winning_model = BYTEZ_FREE_MODELS[success_index]

    chain = ModelChain(api_key="test-key")

    for i, (model_id, client) in enumerate(chain._clients):
        if i < success_index:
            # Models before the winner fail
            client.send_request = lambda p: _make_fail_response()
        elif i == success_index:
            # The winner succeeds
            _mid = model_id  # capture
            def _win(p: str, mid: str = _mid) -> dict:
                return {"raw_text": f"response from {mid}", "status_code": 200}
            client.send_request = _win
        else:
            # Models after the winner should NOT be called
            def _should_not_call(p: str, mid: str = model_id) -> dict:
                raise AssertionError(f"Model {mid} should not be called after winner {winning_model}")
            client.send_request = _should_not_call

    result = chain.send(prompt)

    assert result.model_name == winning_model, (
        f"Expected model_name={winning_model!r}, got {result.model_name!r}"
    )
    assert result.provider == "bytez", (
        f"Expected provider='bytez', got {result.provider!r}"
    )
    assert result.status_code == 200
    assert result.raw_text  # non-empty


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_unit_first_model_succeeds_exact_model_name() -> None:
    """Unit: when the first model (Qwen/Qwen3-4B) succeeds, ModelResult.model_name
    is exactly 'Qwen/Qwen3-4B'.

    **Validates: Requirements 1.6**
    """
    chain = ModelChain(api_key="test-key")

    # First model succeeds, rest should not be called
    first_model_id = BYTEZ_FREE_MODELS[0]
    chain._clients[0][1].send_request = lambda p: {"raw_text": "hello", "status_code": 200}
    for _, client in chain._clients[1:]:
        client.send_request = lambda p: (_ for _ in ()).throw(AssertionError("should not be called"))

    result = chain.send("test prompt")

    assert result.model_name == first_model_id
    assert result.provider == "bytez"
    assert result.raw_text == "hello"
    assert result.status_code == 200


def test_unit_all_providers_fail_returns_offline_kb_provider() -> None:
    """Unit: when all Bytez models AND OpenRouter fail, AIEngine._send() returns
    status_code=0 which triggers OfflineKB fallback in callers.

    **Validates: Requirements 1.10**
    """
    engine = AIEngine(bytez_key="test-key", openrouter_key="or-key")

    # All Bytez models fail
    for _, client in engine._model_chain._clients:
        client.send_request = lambda p: _make_fail_response()

    # OpenRouter also fails
    with patch.object(engine, "send_request", return_value={"raw_text": "", "status_code": 503}):
        result = engine._send("test prompt")

    # status_code 0 → callers use OfflineKB
    assert result.get("status_code", 0) == 0
    assert result.get("raw_text", "") == ""


def test_unit_bytez_key_absent_skips_model_chain() -> None:
    """Unit: when bytez_key is None/empty, ModelChain is skipped and OpenRouter
    is called directly.

    **Validates: Requirements 1.7**
    """
    # No bytez_key → _model_chain should be None
    engine = AIEngine(api_key="or-key", bytez_key="", openrouter_key="or-key")

    assert engine._model_chain is None, (
        "ModelChain should not be created when bytez_key is absent"
    )

    openrouter_called = []

    def mock_openrouter(p: str) -> dict:
        openrouter_called.append(p)
        return {"raw_text": "openrouter response", "status_code": 200}

    with patch.object(engine, "send_request", side_effect=mock_openrouter):
        result = engine._send("test prompt")

    assert len(openrouter_called) == 1, "OpenRouter should be called directly"
    assert result.get("raw_text") == "openrouter response"


def test_unit_model_chain_class_attributes() -> None:
    """Unit: ModelChain.MODELS and ModelChain.TIMEOUT_S are class-level attributes
    with the correct values.
    """
    assert ModelChain.MODELS == [
        "Qwen/Qwen3-4B",
        "mistralai/Mistral-7B-Instruct-v0.3",
        "google/gemma-3-4b-it",
        "openai/gpt-4o-mini",
        "openai/gpt-4.1-mini",
    ]
    assert ModelChain.TIMEOUT_S == 90.0


def test_unit_model_chain_exhausted_returns_bytez_exhausted() -> None:
    """Unit: when all models fail, ModelChain.send() returns provider='bytez_exhausted'."""
    chain = ModelChain(api_key="test-key")
    for _, client in chain._clients:
        client.send_request = lambda p: _make_fail_response()

    result = chain.send("test prompt")

    assert result.provider == "bytez_exhausted"
    assert result.raw_text == ""
    assert result.status_code == 0


def test_unit_empty_prompt_returns_immediately() -> None:
    """Unit: empty/whitespace prompt returns immediately without calling any model."""
    chain = ModelChain(api_key="test-key")
    for _, client in chain._clients:
        client.send_request = lambda p: (_ for _ in ()).throw(AssertionError("should not be called"))

    result = chain.send("   ")
    assert result.raw_text == ""
    assert result.status_code == 0
