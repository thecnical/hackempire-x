"""
ToolManager — intelligent, adaptive, production-grade tool engine for HackEmpire X.

Extends the original architecture with:
- Result deduplication via deduplicator.py
- Confidence scoring via confidence_engine.py
- Tool health tracking via health_tracker.py
- Adaptive skip logic (driven by orchestrator via skip_tools param)
- Parallel execution with configurable max_workers
- Robust per-tool error handling (no crash on failure)
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from core.phases import Phase
from tools.base_tool import BaseTool, ToolExecutionError, ToolNotInstalledError, ToolTimeoutError
from tools.confidence_engine import base_confidence, build_vulnerability_record, merge_vulnerability
from tools.deduplicator import (
    deduplicate_ports,
    deduplicate_subdomains,
    deduplicate_urls,
    normalize_domain,
)
from tools.health_tracker import ToolHealthTracker
from utils.logger import Logger

from tools.recon.nmap_tool import NmapTool
from tools.recon.subfinder_tool import SubfinderTool
from tools.enum.dirsearch_tool import DirsearchTool
from tools.enum.ffuf_tool import FFUFTool
from tools.vuln.nuclei_tool import NucleiTool


class ToolManager:
    """
    Executes external recon/enum/vuln tools via subprocess and normalizes outputs.

    Produces a merged, deduplicated, confidence-scored result dict:
      {
        "ports": [...],
        "subdomains": [...],
        "urls": [...],
        "vulnerabilities": [...],   # sorted high-confidence first
        "tool_status": {...},
      }
    """

    TOOL_REGISTRY: dict[str, list[type[BaseTool]]] = {
        Phase.RECON.value: [NmapTool, SubfinderTool],
        Phase.ENUM.value: [DirsearchTool, FFUFTool],
        Phase.VULN.value: [NucleiTool],
    }

    def __init__(
        self,
        *,
        logger: Logger,
        timeout_s: float,
        execution_mode: str,
        max_workers: int,
        web_scheme: str,
        health_tracker: Optional[ToolHealthTracker] = None,
    ) -> None:
        self._logger = logger
        self._timeout_s = timeout_s
        self._execution_mode = execution_mode
        self._max_workers = max_workers
        self._web_scheme = web_scheme
        # Shared health tracker — injected or created locally.
        self._health_tracker: ToolHealthTracker = health_tracker or ToolHealthTracker()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_phase_tool_names(self, phase: Phase) -> list[str]:
        return [cls.name for cls in self.TOOL_REGISTRY.get(phase.value, [])]

    def get_health_tracker(self) -> ToolHealthTracker:
        return self._health_tracker

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def run_phase_tools(
        self,
        phase: Phase,
        target: str,
        ai_tool_priorities: Optional[list[str]] = None,
        skip_tools: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Run all tools for a phase and return a normalized, deduplicated,
        confidence-scored result dict.

        Args:
            phase: The current execution phase.
            target: The scan target (domain or IP).
            ai_tool_priorities: Tool names the AI suggested running first.
            skip_tools: Tool names to skip (adaptive skip from orchestrator).
        """
        tool_classes = self._select_tools(phase, ai_tool_priorities, skip_tools)
        tool_instances = self._instantiate_tools(tool_classes)

        normalized: dict[str, Any] = {
            "ports": [],
            "subdomains": [],
            "urls": [],
            "vulnerabilities": [],
            "tool_status": {},
        }

        if not tool_instances:
            self._logger.warning(f"No tools to run for phase '{phase.value}'.")
            return normalized

        # Accumulator for vulnerability merge (keyed by (name_lower, target_norm)).
        vuln_records: dict[tuple[str, str], dict[str, Any]] = {}
        target_norm = normalize_domain(target)
        phase_tool_status: dict[str, str] = {}

        if self._execution_mode == "parallel" and len(tool_instances) > 1:
            self._run_parallel(
                tool_instances, target, normalized, vuln_records, phase_tool_status, target_norm
            )
        else:
            self._run_sequential(
                tool_instances, target, normalized, vuln_records, phase_tool_status, target_norm
            )

        # Finalize: deduplicate + sort.
        normalized["ports"] = deduplicate_ports(normalized["ports"])
        normalized["subdomains"] = deduplicate_subdomains(normalized["subdomains"])
        normalized["urls"] = deduplicate_urls(normalized["urls"])

        vulns = list(vuln_records.values())
        vulns.sort(key=lambda v: float(v.get("confidence", 0.0)), reverse=True)
        normalized["vulnerabilities"] = vulns

        normalized["tool_status"] = phase_tool_status

        # Persist health into the shared tracker.
        self._health_tracker.merge_phase_status(phase_tool_status)

        self._logger.info(
            f"Phase '{phase.value}' results: "
            f"{len(normalized['ports'])} ports, "
            f"{len(normalized['subdomains'])} subdomains, "
            f"{len(normalized['urls'])} URLs, "
            f"{len(normalized['vulnerabilities'])} vulns | "
            f"tool_status={phase_tool_status}"
        )
        return normalized

    # ------------------------------------------------------------------
    # Internal: tool selection
    # ------------------------------------------------------------------

    def _select_tools(
        self,
        phase: Phase,
        ai_tool_priorities: Optional[list[str]],
        skip_tools: Optional[list[str]],
    ) -> list[type[BaseTool]]:
        default_tools = self.TOOL_REGISTRY.get(phase.value, [])
        if not default_tools:
            return []

        skip_set: set[str] = {t.lower() for t in (skip_tools or [])}
        filtered = [cls for cls in default_tools if cls.name.lower() not in skip_set]

        if skip_set:
            skipped_names = [cls.name for cls in default_tools if cls.name.lower() in skip_set]
            for name in skipped_names:
                self._logger.warning(f"Adaptive skip: tool '{name}' skipped for phase '{phase.value}'.")
                self._health_tracker.record(name, "skipped")

        ai_set: set[str] = {t.lower() for t in (ai_tool_priorities or [])}
        if not ai_set:
            return filtered

        prioritized = [cls for cls in filtered if cls.name.lower() in ai_set]
        remainder = [cls for cls in filtered if cls.name.lower() not in ai_set]
        return prioritized + remainder

    def _instantiate_tools(self, tool_classes: list[type[BaseTool]]) -> list[BaseTool]:
        return [
            cls(timeout_s=self._timeout_s, web_scheme=self._web_scheme)  # type: ignore[arg-type]
            for cls in tool_classes
        ]

    # ------------------------------------------------------------------
    # Internal: execution strategies
    # ------------------------------------------------------------------

    def _run_parallel(
        self,
        tools: list[BaseTool],
        target: str,
        normalized: dict[str, Any],
        vuln_records: dict[tuple[str, str], dict[str, Any]],
        phase_tool_status: dict[str, str],
        target_norm: str,
    ) -> None:
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_tool = {executor.submit(t.run, target): t for t in tools}
            for future in as_completed(future_to_tool):
                tool = future_to_tool[future]
                try:
                    result = future.result()
                    self._merge_tool_output(normalized, vuln_records, tool.name, result, target_norm)
                    phase_tool_status[tool.name] = "ok"
                except Exception as exc:
                    phase_tool_status[tool.name] = self._classify_error(exc)
                    self._logger.error(
                        f"Tool '{tool.name}' error ({phase_tool_status[tool.name]}).", exc=exc
                    )

    def _run_sequential(
        self,
        tools: list[BaseTool],
        target: str,
        normalized: dict[str, Any],
        vuln_records: dict[tuple[str, str], dict[str, Any]],
        phase_tool_status: dict[str, str],
        target_norm: str,
    ) -> None:
        for tool in tools:
            try:
                result = tool.run(target)
                self._merge_tool_output(normalized, vuln_records, tool.name, result, target_norm)
                phase_tool_status[tool.name] = "ok"
            except Exception as exc:
                phase_tool_status[tool.name] = self._classify_error(exc)
                self._logger.error(
                    f"Tool '{tool.name}' error ({phase_tool_status[tool.name]}).", exc=exc
                )

    # ------------------------------------------------------------------
    # Internal: result merging
    # ------------------------------------------------------------------

    def _merge_tool_output(
        self,
        normalized: dict[str, Any],
        vuln_records: dict[tuple[str, str], dict[str, Any]],
        tool_name: str,
        tool_result: dict[str, Any],
        target_norm: str,
    ) -> None:
        if isinstance(tool_result.get("ports"), list):
            normalized["ports"].extend(tool_result["ports"])

        if isinstance(tool_result.get("subdomains"), list):
            normalized["subdomains"].extend(tool_result["subdomains"])

        if isinstance(tool_result.get("urls"), list):
            normalized["urls"].extend(tool_result["urls"])

        vulns = tool_result.get("vulnerabilities")
        if not isinstance(vulns, list):
            return

        for item in vulns:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("title") or "unknown").strip()
            vuln_target = normalize_domain(str(item.get("target") or target_norm))
            key = (name.lower(), vuln_target)

            if key in vuln_records:
                merge_vulnerability(vuln_records[key], tool_name, item)
            else:
                vuln_records[key] = build_vulnerability_record(tool_name, name, vuln_target, item)

    # ------------------------------------------------------------------
    # Internal: error classification
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_error(exc: BaseException) -> str:
        if isinstance(exc, ToolTimeoutError):
            return "timeout"
        if isinstance(exc, ToolNotInstalledError):
            return "not_installed"
        if isinstance(exc, ToolExecutionError):
            return "failed"
        return "failed"
