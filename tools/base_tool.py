from __future__ import annotations

import abc
import os
import subprocess
from pathlib import Path
from typing import Any, Optional


class ToolExecutionError(RuntimeError):
    pass


class ToolNotInstalledError(ToolExecutionError):
    pass


class ToolTimeoutError(ToolExecutionError):
    pass


class BaseTool(abc.ABC):
    """
    Abstract base class for HackEmpire X tools.

    Concrete tools must implement:
      - check_installed
      - build_command
      - parse_output

    Venv enforcement:
      If a subclass declares `venv_packages: list[str]`, BaseTool will
      automatically ensure the tool's isolated venv exists before running.
      The resolved venv Python path is stored in self._venv_python so that
      build_command() can use it instead of the system binary.
    """

    name: str
    phase: str
    # Subclasses declare this to opt into automatic venv isolation
    venv_packages: list[str] = []

    def __init__(
        self,
        *,
        timeout_s: float,
        proxy: Optional[str] = None,
        venv_python: Optional[Path] = None,
    ) -> None:
        self._timeout_s = timeout_s
        self._proxy: Optional[str] = proxy or os.environ.get("HACKEMPIRE_PROXY")
        # Injected by ToolManager when venv already exists, or resolved lazily below
        self._venv_python: Optional[Path] = venv_python

    @abc.abstractmethod
    def check_installed(self) -> bool:
        raise NotImplementedError

    def install(self) -> None:
        """
        Install hook (intentionally not implemented here).

        Production note: automatic installs can be unsafe; prefer explicit user provisioning.
        """
        raise NotImplementedError("Automatic installation is not supported in this Phase.")

    @abc.abstractmethod
    def build_command(self, target: str) -> list[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def parse_output(self, raw_output: str) -> dict[str, Any]:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Venv enforcement
    # ------------------------------------------------------------------

    def _ensure_venv(self) -> None:
        """
        If this tool declares venv_packages and no venv_python has been
        injected yet, auto-create the isolated venv now.

        This is the safety net — ToolManager injects venv_python proactively,
        but if a tool is instantiated directly (e.g. from a methodology class
        or the AI engine), this ensures it still runs in isolation.
        """
        if self._venv_python is not None:
            return  # already resolved
        if not self.venv_packages:
            return  # not a pip-based tool

        try:
            from installer.tool_venv_manager import get_global_venv_manager
            manager = get_global_venv_manager()
            resolved = manager.ensure_venv(self.name, self.venv_packages)
            if resolved:
                self._venv_python = resolved
        except Exception:
            # Non-fatal — fall back to system binary
            pass

    # ------------------------------------------------------------------
    # Proxy env helper
    # ------------------------------------------------------------------

    def _build_proxy_env(self) -> dict[str, str] | None:
        """
        Return an env dict with HTTP_PROXY/HTTPS_PROXY set if a proxy is configured.
        Tools that don't support --proxy flags can use this via subprocess env.
        """
        if not self._proxy:
            return None
        import os as _os
        env = dict(_os.environ)
        env["http_proxy"] = self._proxy
        env["https_proxy"] = self._proxy
        env["HTTP_PROXY"] = self._proxy
        env["HTTPS_PROXY"] = self._proxy
        return env

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, target: str) -> dict[str, Any]:
        # Enforce venv isolation before anything else
        self._ensure_venv()

        if not self.check_installed():
            raise ToolNotInstalledError(f"Tool '{self.name}' is not installed or not available.")

        try:
            cmd = self.build_command(target)
        except Exception as exc:
            raise ToolExecutionError(f"Tool '{self.name}' cannot build a command for target.") from exc
        if not cmd:
            raise ToolExecutionError(f"Tool '{self.name}' is not applicable for the given target.")

        proxy_env = self._build_proxy_env()

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=self._timeout_s,
                check=False,
                env=proxy_env,  # None means inherit current env (no proxy)
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolTimeoutError(f"Tool '{self.name}' timed out after {self._timeout_s}s") from exc
        except OSError as exc:
            raise ToolExecutionError(f"Tool '{self.name}' failed to execute") from exc

        raw_output = proc.stdout or ""
        if proc.returncode != 0 and not raw_output.strip():
            raise ToolExecutionError(
                f"Tool '{self.name}' failed with exit code {proc.returncode} (no output)."
            )

        return self.parse_output(raw_output)

