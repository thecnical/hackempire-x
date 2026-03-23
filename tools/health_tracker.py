"""
Tool health tracking for HackEmpire X.

Maintains per-tool status across all phases:
  "ok" | "failed" | "timeout" | "not_installed" | "skipped"

Stored in StateManager under the "tool_health" key so the orchestrator
and AI context can access it for smarter decisions.
"""
from __future__ import annotations

from typing import Literal

ToolStatus = Literal["ok", "failed", "timeout", "not_installed", "skipped", "unknown"]

_VALID_STATUSES: frozenset[str] = frozenset(
    {"ok", "failed", "timeout", "not_installed", "skipped", "unknown"}
)


class ToolHealthTracker:
    """
    Tracks cumulative tool health across all phases in a single run.

    Usage:
        tracker = ToolHealthTracker()
        tracker.record("nmap", "ok")
        tracker.record("ffuf", "timeout")
        health = tracker.snapshot()  # {"nmap": "ok", "ffuf": "timeout"}
    """

    def __init__(self) -> None:
        self._health: dict[str, str] = {}

    def record(self, tool_name: str, status: str) -> None:
        """Record or update the status for a tool."""
        if not tool_name:
            return
        normalized = status.lower() if status else "unknown"
        if normalized not in _VALID_STATUSES:
            normalized = "unknown"
        self._health[tool_name] = normalized

    def get(self, tool_name: str) -> str:
        """Return the current status for a tool, defaulting to 'unknown'."""
        return self._health.get(tool_name, "unknown")

    def is_healthy(self, tool_name: str) -> bool:
        """Return True only if the tool's last recorded status was 'ok'."""
        return self._health.get(tool_name) == "ok"

    def has_failures(self) -> bool:
        """Return True if any tool has a non-ok status."""
        return any(v != "ok" for v in self._health.values())

    def snapshot(self) -> dict[str, str]:
        """Return a copy of the current health map."""
        return dict(self._health)

    def merge_phase_status(self, phase_tool_status: dict[str, str]) -> None:
        """
        Merge a phase's tool_status dict into the global health tracker.
        Later phases can overwrite earlier statuses for the same tool.
        """
        for tool_name, status in phase_tool_status.items():
            self.record(tool_name, status)
