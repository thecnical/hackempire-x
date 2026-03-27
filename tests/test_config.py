"""
Property-based tests for Config key resolution.

# Feature: hackempire-x-v4, Property 14: Bytez API key is read from config file or environment variable

For any combination of ~/.hackempire/config.json containing bytez_api_key and/or the
BYTEZ_API_KEY environment variable being set, Config SHALL resolve the key from the config
file first and fall back to the environment variable, and SHALL never raise an exception
when neither is present (returning None instead).

**Validates: Requirements 7.2**
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from core.config import Config, _load_bytez_key

# ---------------------------------------------------------------------------
# Strategy: non-empty API key strings (alphanumeric + common key chars)
# ---------------------------------------------------------------------------

_KEY_STRATEGY = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=8,
    max_size=64,
)


def _make_tmp_home_with_key(key: str) -> tempfile.TemporaryDirectory:
    """Create a temp dir acting as home with .hackempire/config.json containing bytez_api_key."""
    tmp = tempfile.TemporaryDirectory()
    config_dir = Path(tmp.name) / ".hackempire"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps({"bytez_api_key": key}), encoding="utf-8"
    )
    return tmp


# ---------------------------------------------------------------------------
# Property 14: Bytez API key is read from config file or environment variable
# ---------------------------------------------------------------------------

# Feature: hackempire-x-v4, Property 14: Bytez API key is read from config file or environment variable
@given(key=_KEY_STRATEGY)
@settings(max_examples=10)
def test_property14_config_file_takes_priority(key: str) -> None:
    """Case 1: Config file has key → returns config file value.

    **Validates: Requirements 7.2**
    """
    with _make_tmp_home_with_key(key) as tmp_home:
        with patch("core.config.Path.home", return_value=Path(tmp_home)):
            with patch.dict(os.environ, {}, clear=True):
                result = _load_bytez_key()

    assert result == key


# Feature: hackempire-x-v4, Property 14: Bytez API key is read from config file or environment variable
@given(key=_KEY_STRATEGY)
@settings(max_examples=10)
def test_property14_env_var_fallback(key: str) -> None:
    """Case 2: Config file absent, env var set → returns env var value.

    **Validates: Requirements 7.2**
    """
    with tempfile.TemporaryDirectory() as tmp_home:
        # tmp_home has no .hackempire/config.json
        with patch("core.config.Path.home", return_value=Path(tmp_home)):
            with patch.dict(os.environ, {"BYTEZ_API_KEY": key}, clear=True):
                result = _load_bytez_key()

    assert result == key


# Feature: hackempire-x-v4, Property 14: Bytez API key is read from config file or environment variable
@given(key_file=_KEY_STRATEGY, key_env=_KEY_STRATEGY)
@settings(max_examples=10)
def test_property14_config_file_priority_over_env(key_file: str, key_env: str) -> None:
    """Case 3: Both present → config file takes priority.

    **Validates: Requirements 7.2**
    """
    with _make_tmp_home_with_key(key_file) as tmp_home:
        with patch("core.config.Path.home", return_value=Path(tmp_home)):
            with patch.dict(os.environ, {"BYTEZ_API_KEY": key_env}, clear=True):
                result = _load_bytez_key()

    assert result == key_file, (
        f"Config file key {key_file!r} should take priority over env {key_env!r}, got {result!r}"
    )


# Feature: hackempire-x-v4, Property 14: Bytez API key is read from config file or environment variable
@given(st.none())
@settings(max_examples=10)
def test_property14_neither_present_returns_none(_: None) -> None:
    """Case 4: Neither present → returns None without exception.

    **Validates: Requirements 7.2**
    """
    with tempfile.TemporaryDirectory() as tmp_home:
        with patch("core.config.Path.home", return_value=Path(tmp_home)):
            with patch.dict(os.environ, {}, clear=True):
                result = _load_bytez_key()

    assert result is None
