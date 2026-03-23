"""
DependencyChecker — environment validation for HackEmpire X.

Checks:
- Python version (>= 3.11)
- Required pip packages (from requirements.txt or hardcoded list)
- Required environment variables
"""
from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from utils.logger import Logger


# ---------------------------------------------------------------------------
# Required pip packages (importable name → pip package name)
# ---------------------------------------------------------------------------

REQUIRED_PACKAGES: dict[str, str] = {
    "rich": "rich",
    "requests": "requests",
    "flask": "flask",
}

# Environment variables that are optional but worth flagging if absent
OPTIONAL_ENV_VARS: list[str] = [
    "HACKEMPIRE_TOOL_TIMEOUT_S",
    "HACKEMPIRE_MAX_WORKERS",
    "HACKEMPIRE_WEB_SCHEME",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_MODEL",
]


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class DependencyReport:
    python_ok: bool
    python_version: str
    missing_packages: list[str] = field(default_factory=list)
    missing_env_vars: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return self.python_ok and not self.missing_packages and not self.issues

    def to_dict(self) -> dict:
        return {
            "python_ok": self.python_ok,
            "python_version": self.python_version,
            "missing_packages": self.missing_packages,
            "missing_env_vars": self.missing_env_vars,
            "issues": self.issues,
        }


# ---------------------------------------------------------------------------
# DependencyChecker
# ---------------------------------------------------------------------------

class DependencyChecker:
    """
    Validates the runtime environment before tool execution begins.

    Usage:
        checker = DependencyChecker(logger=logger)
        report = checker.run()
        if not report.is_healthy:
            ...
    """

    MIN_PYTHON: tuple[int, int] = (3, 11)

    def __init__(
        self,
        *,
        logger: Logger,
        extra_packages: Optional[dict[str, str]] = None,
        extra_env_vars: Optional[list[str]] = None,
    ) -> None:
        self._logger = logger
        self._packages = {**REQUIRED_PACKAGES, **(extra_packages or {})}
        self._env_vars = OPTIONAL_ENV_VARS + (extra_env_vars or [])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> DependencyReport:
        """Run all checks and return a structured DependencyReport."""
        report = DependencyReport(
            python_ok=False,
            python_version=self._python_version_str(),
        )

        self._check_python(report)
        self._check_packages(report)
        self._check_env_vars(report)
        self._log_report(report)
        return report

    # ------------------------------------------------------------------
    # Internal checks
    # ------------------------------------------------------------------

    def _python_version_str(self) -> str:
        v = sys.version_info
        return f"{v.major}.{v.minor}.{v.micro}"

    def _check_python(self, report: DependencyReport) -> None:
        v = sys.version_info
        if (v.major, v.minor) >= self.MIN_PYTHON:
            report.python_ok = True
            self._logger.info(
                f"[deps] Python {report.python_version} — OK "
                f"(required >= {self.MIN_PYTHON[0]}.{self.MIN_PYTHON[1]})"
            )
        else:
            msg = (
                f"Python {report.python_version} is below the required "
                f"{self.MIN_PYTHON[0]}.{self.MIN_PYTHON[1]}."
            )
            report.issues.append(msg)
            self._logger.error(f"[deps] {msg}")

    def _check_packages(self, report: DependencyReport) -> None:
        for import_name, pip_name in self._packages.items():
            if importlib.util.find_spec(import_name) is None:
                report.missing_packages.append(pip_name)
                self._logger.warning(f"[deps] Missing package: '{pip_name}' (import: '{import_name}')")
            else:
                self._logger.info(f"[deps] Package '{pip_name}' — OK")

    def _check_env_vars(self, report: DependencyReport) -> None:
        for var in self._env_vars:
            if not os.environ.get(var):
                report.missing_env_vars.append(var)
                self._logger.info(f"[deps] Optional env var '{var}' not set (using default).")

    def _log_report(self, report: DependencyReport) -> None:
        if report.is_healthy:
            self._logger.success("[deps] All dependency checks passed.")
        else:
            self._logger.warning(
                f"[deps] Dependency issues found: "
                f"{len(report.issues)} critical, "
                f"{len(report.missing_packages)} missing packages."
            )
