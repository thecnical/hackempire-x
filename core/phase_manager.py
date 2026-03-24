"""
PhaseManager — coordinates the 7-phase penetration testing pipeline.

Builds per-phase FallbackChains from ToolManager, tracks phase statuses,
and emits phase_complete events via RealTimeEmitter.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from hackempire.core.fallback_chain import FallbackChain
from hackempire.core.models import ChainResult, PhaseResult, ScanContext
from hackempire.core.phases import Phase

if TYPE_CHECKING:
    from hackempire.tools.tool_manager import ToolManager
    from hackempire.web.realtime_emitter import RealTimeEmitter

_STATUS_PENDING = "pending"
_STATUS_RUNNING = "running"
_STATUS_COMPLETE = "complete"
_STATUS_DEGRADED = "degraded"


class PhaseManager:
    """Manages the 7-phase pipeline, delegating tool execution to FallbackChain."""

    PHASES: list[Phase] = [
        Phase.RECON,
        Phase.URL_DISCOVERY,
        Phase.ENUMERATION,
        Phase.VULN_SCAN,
        Phase.EXPLOITATION,
        Phase.POST_EXPLOIT,
        Phase.REPORTING,
    ]

    def __init__(
        self,
        tool_manager: "ToolManager",
        emitter: Optional["RealTimeEmitter"] = None,
    ) -> None:
        self._tool_manager = tool_manager
        self._emitter = emitter
        self._phase_statuses: dict[str, str] = {
            phase.value: _STATUS_PENDING for phase in self.PHASES
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_phase(self, phase: Phase, target: str, context: ScanContext) -> PhaseResult:
        """
        Execute a single phase using a FallbackChain of tools.

        Never raises — returns a degraded PhaseResult on any error.
        """
        phase_value = phase.value
        started_at = datetime.utcnow().isoformat()
        self._phase_statuses[phase_value] = _STATUS_RUNNING

        try:
            tools = self._get_tools_for_phase(phase)

            if not tools:
                self._phase_statuses[phase_value] = _STATUS_DEGRADED
                return PhaseResult(
                    phase=phase_value,
                    succeeded=False,
                    degraded=True,
                    started_at=started_at,
                    completed_at=datetime.utcnow().isoformat(),
                )

            chain = FallbackChain(tools=tools, emitter=self._emitter, phase=phase_value)
            chain_result: ChainResult = chain.execute(target)

            succeeded = not chain_result.degraded
            self._phase_statuses[phase_value] = (
                _STATUS_COMPLETE if succeeded else _STATUS_DEGRADED
            )

            completed_at = datetime.utcnow().isoformat()
            phase_result = PhaseResult(
                phase=phase_value,
                succeeded=succeeded,
                degraded=chain_result.degraded,
                chain_result=chain_result,
                started_at=started_at,
                completed_at=completed_at,
            )

            self._emit_phase_complete(phase_value, phase_result)
            return phase_result

        except Exception as exc:  # noqa: BLE001
            self._phase_statuses[phase_value] = _STATUS_DEGRADED
            return PhaseResult(
                phase=phase_value,
                succeeded=False,
                degraded=True,
                started_at=started_at,
                completed_at=datetime.utcnow().isoformat(),
            )

    def get_phase_status(self) -> dict[str, str]:
        """Return a dict mapping each phase name to its current status string."""
        return dict(self._phase_statuses)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_tools_for_phase(self, phase: Phase) -> list[Any]:
        """Retrieve instantiated tool objects for the given phase."""
        tool_classes = self._tool_manager._select_tools(phase, None, None)
        return self._tool_manager._instantiate_tools(tool_classes)

    def _emit_phase_complete(self, phase_value: str, result: PhaseResult) -> None:
        """Fire phase_complete event via emitter, swallowing any error."""
        if self._emitter is None:
            return
        try:
            self._emitter.emit_phase_complete(phase_value, result)
        except Exception:  # noqa: BLE001
            pass
