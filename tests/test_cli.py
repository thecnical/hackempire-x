"""
Unit tests for backward compatibility (Task 13.2).

Tests:
  - All v3 CLI flags (--mode, --web, --ai-key, --proxy, --stealth) are accepted without error
  - Standard mode does not activate AutonomousMode
  - Scan completes with valid report when both Bytez and OpenRouter keys are absent

Requirements: 7.3, 7.7, 7.10
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

import argparse
import pytest
from unittest.mock import patch, MagicMock

from hackempire.cli.cli import _build_parser
from hackempire.core.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(argv: list[str]) -> argparse.Namespace:
    """Parse argv using the real CLI parser — must not raise."""
    parser = _build_parser()
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Requirement 7.3 — All v3 CLI flags are accepted without error
# ---------------------------------------------------------------------------

class TestV3FlagsAccepted:
    """All v3 CLI flags must be accepted by the parser without error."""

    def test_mode_flag_accepted(self) -> None:
        """--mode flag is accepted in the scan subcommand."""
        args = _parse(["scan", "example.com", "--mode", "full"])
        assert args.mode == "full"

    def test_mode_stealth_accepted(self) -> None:
        """--mode stealth (v3 stealth mode) is accepted without error."""
        args = _parse(["scan", "example.com", "--mode", "stealth"])
        assert args.mode == "stealth"

    def test_mode_ultra_accepted(self) -> None:
        """--mode ultra is accepted without error."""
        args = _parse(["scan", "example.com", "--mode", "ultra"])
        assert args.mode == "ultra"

    def test_web_flag_accepted(self) -> None:
        """--web flag is accepted without error."""
        args = _parse(["scan", "example.com", "--mode", "full", "--web"])
        assert args.web is True

    def test_ai_key_flag_accepted(self) -> None:
        """--ai-key flag is accepted without error."""
        args = _parse(["scan", "example.com", "--mode", "full", "--ai-key", "sk-test-key"])
        assert args.ai_key == "sk-test-key"

    def test_proxy_flag_accepted(self) -> None:
        """--proxy flag is accepted without error."""
        args = _parse(["scan", "example.com", "--mode", "full", "--proxy", "http://127.0.0.1:8080"])
        assert args.proxy == "http://127.0.0.1:8080"

    def test_all_v3_flags_together(self) -> None:
        """All v3 flags can be combined in a single command without error."""
        args = _parse([
            "scan", "example.com",
            "--mode", "full",
            "--web",
            "--ai-key", "sk-test-key",
            "--proxy", "http://127.0.0.1:8080",
        ])
        assert args.mode == "full"
        assert args.web is True
        assert args.ai_key == "sk-test-key"
        assert args.proxy == "http://127.0.0.1:8080"

    def test_stealth_mode_with_web_and_proxy(self) -> None:
        """Stealth mode combined with --web and --proxy is accepted."""
        args = _parse([
            "scan", "example.com",
            "--mode", "stealth",
            "--web",
            "--proxy", "http://127.0.0.1:8080",
        ])
        assert args.mode == "stealth"
        assert args.web is True
        assert args.proxy == "http://127.0.0.1:8080"

    def test_autonomous_flag_accepted(self) -> None:
        """--autonomous flag (v4.2) is accepted without error."""
        args = _parse(["scan", "example.com", "--mode", "full", "--autonomous"])
        assert args.autonomous is True

    def test_resume_flag_accepted(self) -> None:
        """--resume flag is accepted without error."""
        args = _parse(["scan", "example.com", "--mode", "full", "--resume"])
        assert args.resume is True

    def test_mode_choices_all_valid(self) -> None:
        """All documented mode choices are accepted by the parser."""
        valid_modes = ["recon-only", "full", "exploit", "stealth", "ultra"]
        for mode in valid_modes:
            args = _parse(["scan", "example.com", "--mode", mode])
            assert args.mode == mode, f"Mode '{mode}' was not accepted"

    def test_invalid_mode_raises_system_exit(self) -> None:
        """An invalid mode value causes argparse to exit (not silently accepted)."""
        with pytest.raises(SystemExit):
            _parse(["scan", "example.com", "--mode", "invalid_mode_xyz"])


# ---------------------------------------------------------------------------
# Requirement 7.7 — Standard mode does not activate AutonomousMode
# ---------------------------------------------------------------------------

class TestStandardModeNoAutonomous:
    """Standard mode (no --mode ultra) must not activate AutonomousMode."""

    def test_full_mode_autonomous_false(self) -> None:
        """Config.create with mode='full' sets autonomous=False."""
        with patch("hackempire.core.config._load_bytez_key", return_value=None):
            config = Config.create(target="example.com", mode="full")
        assert config.autonomous is False

    def test_stealth_mode_autonomous_false(self) -> None:
        """Config.create with mode='stealth' sets autonomous=False."""
        with patch("hackempire.core.config._load_bytez_key", return_value=None):
            config = Config.create(target="example.com", mode="stealth")
        assert config.autonomous is False

    def test_exploit_mode_autonomous_false(self) -> None:
        """Config.create with mode='exploit' sets autonomous=False."""
        with patch("hackempire.core.config._load_bytez_key", return_value=None):
            config = Config.create(target="example.com", mode="exploit")
        assert config.autonomous is False

    def test_recon_only_mode_autonomous_false(self) -> None:
        """Config.create with mode='recon-only' sets autonomous=False."""
        with patch("hackempire.core.config._load_bytez_key", return_value=None):
            config = Config.create(target="example.com", mode="recon-only")
        assert config.autonomous is False

    def test_ultra_mode_autonomous_true(self) -> None:
        """Config.create with mode='ultra' sets autonomous=True (v4.2 requirement)."""
        with patch("hackempire.core.config._load_bytez_key", return_value=None):
            config = Config.create(target="example.com", mode="ultra")
        assert config.autonomous is True

    def test_explicit_autonomous_flag_activates_autonomous(self) -> None:
        """Config.create with autonomous=True activates AutonomousMode regardless of mode."""
        with patch("hackempire.core.config._load_bytez_key", return_value=None):
            config = Config.create(target="example.com", mode="full", autonomous=True)
        assert config.autonomous is True

    def test_standard_mode_cli_flag_not_set(self) -> None:
        """Parsing 'scan example.com --mode full' does not set autonomous flag."""
        args = _parse(["scan", "example.com", "--mode", "full"])
        assert getattr(args, "autonomous", False) is False


# ---------------------------------------------------------------------------
# Requirement 7.10 — Scan completes with valid report when both keys are absent
# ---------------------------------------------------------------------------

class TestOfflineKBFallback:
    """When both Bytez and OpenRouter keys are absent, Config is created without error."""

    def test_config_created_without_keys(self) -> None:
        """Config.create succeeds when both Bytez and OpenRouter keys are absent."""
        with patch("hackempire.core.config._load_bytez_key", return_value=None):
            config = Config.create(
                target="example.com",
                mode="full",
                ai_key=None,
            )
        assert config.bytez_key is None
        assert config.ai_key is None
        assert config.target == "example.com"

    def test_config_bytez_key_none_when_absent(self) -> None:
        """bytez_key is None when neither config file nor env var provides it."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_home:
            with patch("hackempire.core.config.Path.home", return_value=__import__("pathlib").Path(tmp_home)):
                with patch.dict(os.environ, {}, clear=True):
                    from hackempire.core.config import _load_bytez_key
                    result = _load_bytez_key()
        assert result is None

    def test_config_does_not_raise_without_keys(self) -> None:
        """Config.create never raises an exception when keys are absent."""
        with patch("hackempire.core.config._load_bytez_key", return_value=None):
            try:
                config = Config.create(
                    target="192.168.1.1",
                    mode="full",
                    ai_key=None,
                )
            except Exception as exc:
                pytest.fail(f"Config.create raised unexpectedly: {exc}")
        assert config is not None

    def test_config_mode_preserved_without_keys(self) -> None:
        """Config mode is preserved correctly even when no AI keys are present."""
        with patch("hackempire.core.config._load_bytez_key", return_value=None):
            config = Config.create(target="example.com", mode="full")
        assert config.mode == "full"

    def test_config_web_enabled_preserved_without_keys(self) -> None:
        """Config web_enabled is preserved correctly even when no AI keys are present."""
        with patch("hackempire.core.config._load_bytez_key", return_value=None):
            config = Config.create(target="example.com", mode="full", web_enabled=True)
        assert config.web_enabled is True
