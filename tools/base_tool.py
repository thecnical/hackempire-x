from __future__ import annotations

import abc
import subprocess
from typing import Any


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
    """

    name: str
    phase: str

    def __init__(self, *, timeout_s: float) -> None:
        self._timeout_s = timeout_s

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

    def run(self, target: str) -> dict[str, Any]:
        if not self.check_installed():
            raise ToolNotInstalledError(f"Tool '{self.name}' is not installed or not available.")

        try:
            cmd = self.build_command(target)
        except Exception as exc:
            raise ToolExecutionError(f"Tool '{self.name}' cannot build a command for target.") from exc
        if not cmd:
            raise ToolExecutionError(f"Tool '{self.name}' is not applicable for the given target.")

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=self._timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolTimeoutError(f"Tool '{self.name}' timed out after {self._timeout_s}s") from exc
        except OSError as exc:
            raise ToolExecutionError(f"Tool '{self.name}' failed to execute") from exc

        raw_output = proc.stdout or ""
        if proc.returncode != 0 and not raw_output.strip():
            # If the tool failed and didn't print anything, treat as failure.
            raise ToolExecutionError(
                f"Tool '{self.name}' failed with exit code {proc.returncode} (no output)."
            )

        return self.parse_output(raw_output)

