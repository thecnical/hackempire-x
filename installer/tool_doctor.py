"""
ToolDoctor — automated tool health diagnostics and repair for HackEmpire X.

Responsibilities:
- Detect issues from tool_status (not_installed, failed, timeout)
- Attempt auto-fix (reinstall, permission repair)
- Generate structured diagnostic reports
- Integrate with ToolInstaller for reinstall attempts
"""
from __future__ import annotations

import os
import shutil
import stat
from dataclasses import dataclass
from typing import Literal, Optional

from utils.logger import Logger
from installer.tool_installer import ToolInstaller, TOOL_INSTALL_SPECS


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

IssueKind = Literal["not_installed", "failed", "timeout", "permission_error", "unknown"]
FixAction = Literal["reinstall", "fix_permissions", "manual_fix", "none"]


@dataclass
class DiagnosticReport:
    tool: str
    issue: IssueKind
    fix_attempted: FixAction
    fix_succeeded: bool
    suggestion: str
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "issue": self.issue,
            "fix": self._fix_command(),
            "fix_attempted": self.fix_attempted,
            "fix_succeeded": self.fix_succeeded,
            "suggestion": self.suggestion,
            "details": self.details,
        }

    def _fix_command(self) -> str:
        spec = TOOL_INSTALL_SPECS.get(self.tool)
        if spec is None:
            return f"Manually install '{self.tool}'"
        if spec.method == "apt":
            return f"apt install {spec.package}"
        if spec.method == "pip":
            return f"pip install {spec.package}"
        if spec.method == "git":
            return f"git clone {spec.package} {spec.git_dest or '/opt/' + self.tool}"
        return f"Manually install '{self.tool}'"


# ---------------------------------------------------------------------------
# ToolDoctor
# ---------------------------------------------------------------------------

class ToolDoctor:
    """
    Diagnoses and attempts to repair broken or missing tools.

    Usage:
        doctor = ToolDoctor(logger=logger, installer=installer, mode="pro")
        reports = doctor.diagnose_and_fix(tool_status)
    """

    def __init__(
        self,
        *,
        logger: Logger,
        installer: ToolInstaller,
        mode: str = "pro",
    ) -> None:
        self._logger = logger
        self._installer = installer
        self._mode = mode.lower()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def diagnose_and_fix(
        self,
        tool_status: dict[str, str],
    ) -> list[DiagnosticReport]:
        """
        Inspect tool_status dict and attempt fixes for unhealthy tools.

        Args:
            tool_status: {tool_name: status} — e.g. {"nmap": "not_installed", "ffuf": "timeout"}

        Returns:
            List of DiagnosticReport for every unhealthy tool.
        """
        reports: list[DiagnosticReport] = []
        for tool_name, status in tool_status.items():
            if status in ("ok", "skipped", "already_installed"):
                continue
            issue = self._classify_issue(status)
            report = self._handle_issue(tool_name, issue)
            reports.append(report)
            self._log_report(report)
        return reports

    def generate_summary(self, reports: list[DiagnosticReport]) -> dict:
        """Return a JSON-serialisable summary of all diagnostic reports."""
        return {
            "total_issues": len(reports),
            "fixed": sum(1 for r in reports if r.fix_succeeded),
            "manual_action_required": [r.to_dict() for r in reports if not r.fix_succeeded],
            "reports": [r.to_dict() for r in reports],
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _classify_issue(self, status: str) -> IssueKind:
        mapping: dict[str, IssueKind] = {
            "not_installed": "not_installed",
            "failed": "failed",
            "timeout": "timeout",
        }
        return mapping.get(status, "unknown")

    def _handle_issue(self, tool_name: str, issue: IssueKind) -> DiagnosticReport:
        if issue == "not_installed":
            return self._fix_not_installed(tool_name)
        if issue == "failed":
            return self._fix_failed(tool_name)
        if issue == "timeout":
            return self._fix_timeout(tool_name)
        return DiagnosticReport(
            tool=tool_name,
            issue=issue,
            fix_attempted="none",
            fix_succeeded=False,
            suggestion=f"Unknown issue for '{tool_name}'. Check logs and reinstall manually.",
        )

    def _fix_not_installed(self, tool_name: str) -> DiagnosticReport:
        """Attempt reinstall for a missing tool."""
        self._logger.info(f"[doctor] '{tool_name}' not installed — attempting reinstall...")
        results = self._installer.ensure_tools([tool_name])
        result = results[0] if results else None
        succeeded = result is not None and result.status in ("installed", "already_installed")
        return DiagnosticReport(
            tool=tool_name,
            issue="not_installed",
            fix_attempted="reinstall",
            fix_succeeded=succeeded,
            suggestion=(
                "Tool installed successfully."
                if succeeded
                else self._manual_fix_suggestion(tool_name)
            ),
            details=result.message if result else "",
        )

    def _fix_failed(self, tool_name: str) -> DiagnosticReport:
        """
        For a failed tool: check permissions first, then attempt reinstall.
        """
        self._logger.info(f"[doctor] '{tool_name}' failed — checking permissions...")
        perm_fixed = self._attempt_permission_fix(tool_name)
        if perm_fixed:
            return DiagnosticReport(
                tool=tool_name,
                issue="failed",
                fix_attempted="fix_permissions",
                fix_succeeded=True,
                suggestion="Permissions repaired. Tool should work now.",
            )

        # Fallback: reinstall
        self._logger.info(f"[doctor] Permission fix did not resolve '{tool_name}' — attempting reinstall...")
        results = self._installer.ensure_tools([tool_name])
        result = results[0] if results else None
        succeeded = result is not None and result.status in ("installed", "already_installed")
        return DiagnosticReport(
            tool=tool_name,
            issue="failed",
            fix_attempted="reinstall",
            fix_succeeded=succeeded,
            suggestion=(
                "Reinstall succeeded."
                if succeeded
                else self._manual_fix_suggestion(tool_name)
            ),
            details=result.message if result else "",
        )

    def _fix_timeout(self, tool_name: str) -> DiagnosticReport:
        """
        Timeout is usually a network/performance issue, not a broken install.
        Suggest increasing HACKEMPIRE_TOOL_TIMEOUT_S.
        """
        self._logger.warning(
            f"[doctor] '{tool_name}' timed out. "
            "Consider increasing HACKEMPIRE_TOOL_TIMEOUT_S env var."
        )
        return DiagnosticReport(
            tool=tool_name,
            issue="timeout",
            fix_attempted="none",
            fix_succeeded=False,
            suggestion=(
                f"'{tool_name}' timed out. "
                "Increase HACKEMPIRE_TOOL_TIMEOUT_S (e.g. export HACKEMPIRE_TOOL_TIMEOUT_S=120) "
                "or check network connectivity."
            ),
        )

    def _attempt_permission_fix(self, tool_name: str) -> bool:
        """
        Try to make the tool binary executable if it exists but isn't runnable.
        Returns True if the fix was applied.
        """
        binary_path = shutil.which(tool_name)
        if binary_path is None:
            return False
        try:
            current = os.stat(binary_path).st_mode
            os.chmod(binary_path, current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            self._logger.info(f"[doctor] chmod +x applied to '{binary_path}'.")
            return True
        except OSError as exc:
            self._logger.warning(f"[doctor] Could not chmod '{binary_path}': {exc}")
            return False

    def _manual_fix_suggestion(self, tool_name: str) -> str:
        spec = TOOL_INSTALL_SPECS.get(tool_name)
        if spec is None:
            return f"Manually install '{tool_name}' and ensure it is on PATH."
        if spec.method == "apt":
            return f"Run: sudo apt install {spec.package}"
        if spec.method == "pip":
            return f"Run: pip install {spec.package}"
        if spec.method == "git":
            return f"Run: git clone {spec.package} {spec.git_dest or '/opt/' + tool_name}"
        return f"Manually install '{tool_name}'."

    def _log_report(self, report: DiagnosticReport) -> None:
        if self._mode == "beginner":
            self._logger.info(
                f"[doctor] Tool: {report.tool} | Issue: {report.issue} | "
                f"Fix attempted: {report.fix_attempted} | "
                f"Succeeded: {report.fix_succeeded}\n"
                f"  Suggestion: {report.suggestion}"
            )
        else:
            status = "FIXED" if report.fix_succeeded else "NEEDS MANUAL FIX"
            self._logger.info(
                f"[doctor] {report.tool} [{report.issue}] → {status} | {report.suggestion}"
            )
