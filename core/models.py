from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


@dataclass
class Vulnerability:
    name: str
    severity: Literal["info", "low", "medium", "high", "critical"]
    confidence: float  # 0.0 to 1.0
    target: str
    url: str
    cve_ids: list[str] = field(default_factory=list)
    cwe_ids: list[str] = field(default_factory=list)
    evidence: str = ""
    tool_sources: list[str] = field(default_factory=list)
    exploit_available: bool = False
    remediation: str = ""
    cvss_score: float | None = None


@dataclass
class ToolAttempt:
    tool_name: str
    status: str
    error: str | None = None


@dataclass
class ChainResult:
    phase: str
    succeeded_tool: str | None
    results: dict = field(default_factory=dict)
    tool_attempts: list[ToolAttempt] = field(default_factory=list)
    degraded: bool = False


@dataclass
class TodoTask:
    index: int
    description: str
    tool: str
    status: Literal["pending", "running", "done", "failed", "skipped"] = "pending"
    result_summary: str | None = None


@dataclass
class TodoList:
    target: str
    phases: dict[str, list[TodoTask]] = field(default_factory=dict)
    created_at: str = ""


@dataclass
class PhaseResult:
    phase: str
    succeeded: bool
    degraded: bool
    chain_result: Any | None = None
    started_at: str = ""
    completed_at: str | None = None


@dataclass
class AIDecision:
    phase: str
    summary: str
    suggested_tools: list[str] = field(default_factory=list)
    exploit_chains: list[str] = field(default_factory=list)
    confidence: float = 0.0
    # Phase 2 — AI Brain upgrade fields
    attack_surface: list[str] = field(default_factory=list)
    priority_targets: list[str] = field(default_factory=list)
    vuln_hypotheses: list[str] = field(default_factory=list)


@dataclass
class WafResult:
    detected: bool
    vendor: str | None = None
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# v4.1 — ModelResult: tracks which AI model produced a response
# ---------------------------------------------------------------------------

@dataclass
class ModelResult:
    """Result from ModelChain.send() — includes which model/provider responded."""
    raw_text: str
    status_code: int
    model_name: str   # e.g. "Qwen/Qwen3-4B"
    provider: str     # "bytez" | "openrouter" | "offline_kb"


# ---------------------------------------------------------------------------
# v4.2 — AutonomousDecision: AI decision during autonomous scan mode
# ---------------------------------------------------------------------------

class AutonomousAction(str, Enum):
    CONTINUE    = "continue"     # run next tool in same phase
    SWITCH_TOOL = "switch_tool"  # skip to a different tool
    NEXT_PHASE  = "next_phase"   # advance pipeline to next phase


@dataclass
class AutonomousDecision:
    """A single decision made by AutonomousEngine during a scan."""
    action: AutonomousAction
    phase: str
    reason: str
    next_tool: str | None = None
    timestamp: str = ""


# ---------------------------------------------------------------------------
# v4.3 — KBEntry: a single record in the RAG Knowledge Base
# ---------------------------------------------------------------------------

@dataclass
class KBEntry:
    """
    A single scan result record stored in ~/.hackempire/kb/{domain}/entries.jsonl.
    Used by RAG_KB to provide context to the AI on future scans.
    """
    target: str
    findings: list[dict] = field(default_factory=list)
    payloads: list[str] = field(default_factory=list)
    attack_patterns: list[str] = field(default_factory=list)
    timestamp: str = ""  # UTC ISO 8601

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "findings": self.findings,
            "payloads": self.payloads,
            "attack_patterns": self.attack_patterns,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KBEntry":
        return cls(
            target=str(d.get("target", "")),
            findings=list(d.get("findings", [])),
            payloads=list(d.get("payloads", [])),
            attack_patterns=list(d.get("attack_patterns", [])),
            timestamp=str(d.get("timestamp", "")),
        )


# ---------------------------------------------------------------------------
# ScanContext — updated for v4
# ---------------------------------------------------------------------------

@dataclass
class ScanContext:
    target: str
    mode: str
    session_id: str
    phase_results: dict = field(default_factory=dict)
    tool_health: dict = field(default_factory=dict)
    todo_list: Any | None = None
    ai_decisions: dict = field(default_factory=dict)
    started_at: str = ""
    waf_result: Any | None = None
    # v4.2 — autonomous mode tracking
    autonomous: bool = False
    autonomous_decisions: list[AutonomousDecision] = field(default_factory=list)
    # v4.3 — RAG KB entries retrieved for this target
    kb_entries: list[KBEntry] = field(default_factory=list)
