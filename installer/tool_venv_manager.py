"""
ToolVenvManager — isolated per-tool virtual environment manager for HackEmpire X.

Responsibilities:
- Create isolated venvs under .hackempire/venvs/{tool_name}/
- Install pip packages into each venv
- Return the venv Python path for subprocess calls
- Idempotent: skip creation if venv already exists
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

from utils.logger import Logger


# ---------------------------------------------------------------------------
# Global singleton — used by BaseTool._ensure_venv() for auto-isolation
# ---------------------------------------------------------------------------

_GLOBAL_VENV_MANAGER: "ToolVenvManager | None" = None


def get_global_venv_manager() -> "ToolVenvManager":
    """
    Return the process-wide ToolVenvManager singleton.

    Created on first call with a no-op logger. The real logger is injected
    when ToolManager or DependencyResolver initialises their own instance
    via set_global_venv_manager().
    """
    global _GLOBAL_VENV_MANAGER
    if _GLOBAL_VENV_MANAGER is None:
        from utils.logger import Logger as _Logger
        _GLOBAL_VENV_MANAGER = ToolVenvManager(logger=_Logger())
    return _GLOBAL_VENV_MANAGER


def set_global_venv_manager(manager: "ToolVenvManager") -> None:
    """Register *manager* as the process-wide singleton."""
    global _GLOBAL_VENV_MANAGER
    _GLOBAL_VENV_MANAGER = manager


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VENV_BASE = Path(".hackempire/venvs")

TOOL_VENV_PACKAGES: dict[str, list[str]] = {
    "arjun": ["arjun"],
    "paramspider": ["paramspider"],
    "ghauri": ["ghauri"],
    "bloodhound": ["bloodhound"],
    "impacket": ["impacket"],
    "crackmapexec": ["crackmapexec"],
    "sqlmap": ["sqlmap"],
    "xsstrike": ["requests", "fuzzywuzzy"],
}


# ---------------------------------------------------------------------------
# ToolVenvManager
# ---------------------------------------------------------------------------

class ToolVenvManager:
    """
    Manages isolated Python virtual environments for pip-based tools.

    Usage:
        manager = ToolVenvManager(logger=logger)
        python_path = manager.ensure_venv("arjun", ["arjun"])
        # python_path is now the venv's Python interpreter
    """

    def __init__(self, *, logger: Logger) -> None:
        self._logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure_venv(self, tool_name: str, pip_packages: list[str]) -> Optional[Path]:
        """
        Ensure a venv exists for *tool_name* with *pip_packages* installed.

        - If the venv Python already exists, return it immediately (idempotent).
        - Otherwise create the venv, install packages, and return the Python path.
        - Returns None on any failure (never raises).
        """
        venv_dir = VENV_BASE / tool_name
        python_path = self._python_path(venv_dir)

        if python_path.exists():
            self._logger.info(f"[venv] '{tool_name}' venv already exists at {venv_dir}")
            return python_path

        self._logger.info(f"[venv] Creating venv for '{tool_name}' at {venv_dir}")
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                check=True,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as exc:
            self._logger.error(f"[venv] Failed to create venv for '{tool_name}'", exc=exc)
            return None

        for pkg in pip_packages:
            self._logger.info(f"[venv] Installing '{pkg}' into '{tool_name}' venv")
            try:
                subprocess.run(
                    [str(python_path), "-m", "pip", "install", "--quiet", pkg],
                    check=True,
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except Exception as exc:
                self._logger.error(
                    f"[venv] Failed to install '{pkg}' into '{tool_name}' venv", exc=exc
                )
                return None

        self._logger.success(f"[venv] '{tool_name}' venv ready at {python_path}")
        return python_path

    def get_venv_python(self, tool_name: str) -> Optional[Path]:
        """Return the venv Python path if it exists, else None."""
        python_path = self._python_path(VENV_BASE / tool_name)
        return python_path if python_path.exists() else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _python_path(venv_dir: Path) -> Path:
        """Return the platform-appropriate Python executable path inside *venv_dir*."""
        if sys.platform == "win32":
            return venv_dir / "Scripts" / "python.exe"
        return venv_dir / "bin" / "python"
