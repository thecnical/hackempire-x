from __future__ import annotations

from dataclasses import dataclass, field
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
