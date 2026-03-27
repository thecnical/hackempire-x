"""
Property-based tests for v4 Config key resolution.

Property 14: Bytez API key is read from config file or environment variable
  - When ~/.hackempire/config.json contains bytez_key/bytez_api_key, it is used
  - When the file is absent/empty, BYTEZ_API_KEY env var is used
  - When both are absent, bytez_key is None
  **Validates: Requirements 7.2**
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from core.config import Config, _load_bytez_key

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KEY_STRATEGY = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=8,
    max_size=64,
)


def _make_config_json(key: str, field: str = "bytez_key") -> dict:
    return {field: key}


# ---------------------------------------------------------------------------
# Property 14 — Bytez API key resolution
# ---------------------------------------------------------------------------


@given(key=_KEY_STRATEGY)
@settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_14a_key_from_config_file_bytez_key(key: str, tmp_path: Path) -> None:
    """Property 14a: bytez_key field in config.json is returned by _load_bytez_key().

    **Validates: Requirements 7.2**
    """
    config_dir = tmp_path / ".hackempire"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({"bytez_key": key}), encoding="utf-8")

    with patch("core.config.Path.home", return_value=tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            result = _load_bytez_key()

    assert result == key, f"Expected {key!r}, got {result!r}"


@given(key=_KEY_STRATEGY)
@settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_14b_key_from_config_file_bytez_api_key(key: str, tmp_path: Path) -> None:
    """Property 14b: bytez_api_key field in config.json is also accepted.

    **Validates: Requirements 7.2**
    """
    config_dir = tmp_path / ".hackempire"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({"bytez_api_key": key}), encoding="utf-8")

    with patch("core.config.Path.home", return_value=tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            result = _load_bytez_key()

    assert result == key, f"Expected {key!r}, got {result!r}"


@given(key=_KEY_STRATEGY)
@settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_14c_key_from_env_var_when_no_config_file(key: str, tmp_path: Path) -> None:
    """Property 14c: BYTEZ_API_KEY env var is used when config file is absent.

    **Validates: Requirements 7.2**
    """
    # tmp_path has no .hackempire/config.json
    with patch("core.config.Path.home", return_value=tmp_path):
        with patch.dict(os.environ, {"BYTEZ_API_KEY": key}, clear=True):
            result = _load_bytez_key()

    assert result == key, f"Expected {key!r}, got {result!r}"


@given(key_file=_KEY_STRATEGY, key_env=_KEY_STRATEGY)
@settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_14d_config_file_takes_priority_over_env(
    key_file: str, key_env: str, tmp_path: Path
) -> None:
    """Property 14d: config file key takes priority over BYTEZ_API_KEY env var.

    **Validates: Requirements 7.2**
    """
    config_dir = tmp_path / ".hackempire"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({"bytez_key": key_file}), encoding="utf-8")

    with patch("core.config.Path.home", return_value=tmp_path):
        with patch.dict(os.environ, {"BYTEZ_API_KEY": key_env}, clear=True):
            result = _load_bytez_key()

    assert result == key_file, (
        f"Config file key {key_file!r} should take priority over env key {key_env!r}, got {result!r}"
    )


def test_property_14e_none_when_both_absent(tmp_path: Path) -> None:
    """Property 14e: bytez_key is None when both config file and env var are absent.

    **Validates: Requirements 7.2**
    """
    with patch("core.config.Path.home", return_value=tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            result = _load_bytez_key()

    assert result is None, f"Expected None, got {result!r}"


def test_property_14f_none_when_config_file_has_no_key(tmp_path: Path) -> None:
    """Property 14f: bytez_key is None when config.json exists but has no key fields.

    **Validates: Requirements 7.2**
    """
    config_dir = tmp_path / ".hackempire"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({"other_setting": "value"}), encoding="utf-8")

    with patch("core.config.Path.home", return_value=tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            result = _load_bytez_key()

    assert result is None, f"Expected None, got {result!r}"


def test_property_14g_none_when_config_file_is_malformed(tmp_path: Path) -> None:
    """Property 14g: _load_bytez_key never raises — returns None on malformed JSON.

    **Validates: Requirements 7.2**
    """
    config_dir = tmp_path / ".hackempire"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    config_file.write_text("NOT VALID JSON {{{{", encoding="utf-8")

    with patch("core.config.Path.home", return_value=tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            result = _load_bytez_key()

    assert result is None, f"Expected None on malformed JSON, got {result!r}"


# ---------------------------------------------------------------------------
# Config.create() integration — bytez_key and autonomous wired correctly
# ---------------------------------------------------------------------------


def test_config_create_loads_bytez_key_from_env(tmp_path: Path) -> None:
    """Config.create() populates bytez_key via _load_bytez_key()."""
    with patch("core.config.Path.home", return_value=tmp_path):
        with patch.dict(os.environ, {"BYTEZ_API_KEY": "test-key-123"}, clear=True):
            cfg = Config.create(target="example.com", mode="standard")

    assert cfg.bytez_key == "test-key-123"


def test_config_create_autonomous_false_by_default(tmp_path: Path) -> None:
    """Config.create() sets autonomous=False in standard mode."""
    with patch("core.config.Path.home", return_value=tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            cfg = Config.create(target="example.com", mode="standard")

    assert cfg.autonomous is False


def test_config_create_ultra_mode_sets_autonomous_true(tmp_path: Path) -> None:
    """Config.create() sets autonomous=True when mode='ultra'."""
    with patch("core.config.Path.home", return_value=tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            cfg = Config.create(target="example.com", mode="ultra")

    assert cfg.autonomous is True
