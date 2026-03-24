"""
Property-based and unit tests for ToolVenvManager.

Property 12: ToolVenvManager Idempotence — calling ensure_venv twice returns
  same path without recreating.
  **Validates: Requirements 6.2**
"""

import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)          # hackempire/
_parent = os.path.dirname(_pkg_root)        # repo root (contains hackempire/)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.installer.tool_venv_manager import ToolVenvManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logger():
    logger = MagicMock()
    logger.info = MagicMock()
    logger.error = MagicMock()
    logger.success = MagicMock()
    return logger


# Windows reserved device names that cannot be used as directory names
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# Strategy: valid tool names (alphanumeric + underscore/hyphen, non-empty, not Windows reserved)
_tool_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=20,
).filter(lambda s: s.strip("-_") != "").filter(
    lambda s: s.upper() not in _WINDOWS_RESERVED
)

# Strategy: list of 1–4 pip package names
_packages_st = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_"),
        min_size=1,
        max_size=15,
    ).filter(lambda s: s.strip("-_") != ""),
    min_size=1,
    max_size=4,
)


# ---------------------------------------------------------------------------
# Property 12: ToolVenvManager Idempotence
# ---------------------------------------------------------------------------

@given(tool_name=_tool_name_st, packages=_packages_st)
@settings(max_examples=100)
def test_property_12_ensure_venv_idempotent(tool_name, packages):
    """Property 12: ToolVenvManager Idempotence — calling ensure_venv twice
    returns the same path without recreating the venv.

    **Validates: Requirements 6.2**
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        with patch("hackempire.installer.tool_venv_manager.VENV_BASE", tmp_path):
            logger = _make_logger()
            manager = ToolVenvManager(logger=logger)

            # Determine the expected python path for this tool
            venv_dir = tmp_path / tool_name
            if sys.platform == "win32":
                expected_python = venv_dir / "Scripts" / "python.exe"
            else:
                expected_python = venv_dir / "bin" / "python"

            def mock_subprocess_run(cmd, **kwargs):
                # When venv creation is called, create the python file so
                # subsequent calls see it as existing.
                if "-m" in cmd and "venv" in cmd:
                    expected_python.parent.mkdir(parents=True, exist_ok=True)
                    expected_python.touch()
                result = MagicMock()
                result.returncode = 0
                return result

            with patch("hackempire.installer.tool_venv_manager.subprocess.run",
                       side_effect=mock_subprocess_run) as mock_run:

                # First call — should create the venv
                path1 = manager.ensure_venv(tool_name, packages)

                # Second call — venv already exists, should skip creation
                path2 = manager.ensure_venv(tool_name, packages)

                # Both calls must return the same path
                assert path1 is not None, "First ensure_venv call returned None"
                assert path2 is not None, "Second ensure_venv call returned None"
                assert path1 == path2, (
                    f"ensure_venv returned different paths: {path1} vs {path2}"
                )

                # subprocess.run must have been called for venv creation + pip installs
                # on the first call only. The second call must NOT trigger subprocess.run.
                # Venv creation = 1 call, pip installs = len(packages) calls.
                expected_call_count = 1 + len(packages)
                assert mock_run.call_count == expected_call_count, (
                    f"subprocess.run called {mock_run.call_count} times, "
                    f"expected {expected_call_count} (1 venv + {len(packages)} pip installs). "
                    "Second ensure_venv call must not recreate the venv."
                )


# ---------------------------------------------------------------------------
# Unit test: ensure_venv returns None when subprocess.run fails
# ---------------------------------------------------------------------------

def test_ensure_venv_returns_none_on_failure():
    """ensure_venv returns None when venv creation fails."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        with patch("hackempire.installer.tool_venv_manager.VENV_BASE", tmp_path):
            logger = _make_logger()
            manager = ToolVenvManager(logger=logger)

            with patch(
                "hackempire.installer.tool_venv_manager.subprocess.run",
                side_effect=Exception("venv creation failed"),
            ):
                result = manager.ensure_venv("sometool", ["somepkg"])

            assert result is None, f"Expected None on failure, got {result}"


# ---------------------------------------------------------------------------
# Unit tests: get_venv_python
# ---------------------------------------------------------------------------

def test_get_venv_python_returns_none_when_venv_missing():
    """get_venv_python returns None when the venv does not exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        with patch("hackempire.installer.tool_venv_manager.VENV_BASE", tmp_path):
            logger = _make_logger()
            manager = ToolVenvManager(logger=logger)

            result = manager.get_venv_python("nonexistent_tool")

            assert result is None, f"Expected None for missing venv, got {result}"


def test_get_venv_python_returns_path_when_venv_exists():
    """get_venv_python returns the python path when the venv exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        with patch("hackempire.installer.tool_venv_manager.VENV_BASE", tmp_path):
            logger = _make_logger()
            manager = ToolVenvManager(logger=logger)

            # Manually create the expected python file
            venv_dir = tmp_path / "mytool"
            if sys.platform == "win32":
                python_path = venv_dir / "Scripts" / "python.exe"
            else:
                python_path = venv_dir / "bin" / "python"
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.touch()

            result = manager.get_venv_python("mytool")

            assert result == python_path, (
                f"Expected {python_path}, got {result}"
            )
