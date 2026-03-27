"""
AutonomousEngine — AI-driven autonomous scan mode for HackEmpire X v4.

When --mode ultra or --autonomous is set, the AI decides:
  - Which tool to run next
  - What to do with the output (continue / switch_tool / next_phase)
  - When to advance to the next pipeline phase

The engine never raises — all errors are caught and logged.
The loop always terminates — either all phases complete or no attack surface remains.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from hackempire.core.models import AutonomousAction, AutonomousDecision

logger = logging.getLogger(__name__)

# Maximum iterations per phase to prevent infinite loops
MAX_ITERATIONS_PER_PHASE = 12


class AutonomousEngine:
    """
    Drives the autonomous scan loop.

    Usage:
        engine = AutonomousEngine(ai_engine=ai_engine)
        decision = engine.decide(phase, tool_output, context, tool_name)
    """

    def __init__(self, ai_engine: Any = None) -> None:
        self._ai = ai_engine

    def decide(
        self,
        phase: str,
        tool_name: str,
        tool_output: dict,
        context: Any,
    ) -> AutonomousDecision:
        """
        Decide the next action after a tool completes.

        Returns AutonomousDecision with action one of:
          - continue: run next tool in same phase
          - switch_tool: skip to a different tool
          - next_phase: advance pipeline to next phase

        Never raises — falls back to heuristic decision on any error.
        """
        try:
            # Look up ToolKnowledge for this tool
            tool_knowledge = self._get_tool_knowledge(tool_name)

            # Try AI decision first
            if self._ai is not None:
                ai_decision = self._ai_decide(phase, tool_name, tool_output, context, tool_knowledge)
                if ai_decision is not None:
                    self._log_decision(ai_decision)
                    return ai_decision

            # Fallback: heuristic decision from ToolKnowledge
            return self._heuristic_decide(phase, tool_name, tool_output, tool_knowledge)

        except Exception as exc:
            logger.warning("[autonomous] decide() error for %s/%s: %s — defaulting to continue",
                           phase, tool_name, exc)
            return AutonomousDecision(
                action=AutonomousAction.CONTINUE,
                phase=phase,
                reason=f"Error in decision engine: {exc}",
                next_tool=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    # ── Internal ─────────────────────────────────────────────────────────

    def _get_tool_knowledge(self, tool_name: str) -> Optional[Any]:
        """Load ToolKnowledge entry for tool_name. Returns None if missing."""
        try:
            from hackempire.ai.tool_knowledge import TOOL_KNOWLEDGE  # noqa: PLC0415
            entry = TOOL_KNOWLEDGE.get(tool_name)
            if entry is None:
                logger.warning("[autonomous] No ToolKnowledge entry for '%s' — using generic heuristics",
                               tool_name)
            return entry
        except Exception as exc:
            logger.debug("[autonomous] ToolKnowledge load failed: %s", exc)
            return None

    def _ai_decide(
        self,
        phase: str,
        tool_name: str,
        tool_output: dict,
        context: Any,
        tool_knowledge: Any,
    ) -> Optional[AutonomousDecision]:
        """Ask AI to decide next action. Returns None if AI unavailable."""
        try:
            knowledge_str = ""
            if tool_knowledge:
                knowledge_str = (
                    f"Tool knowledge:\n"
                    f"  success_indicator: {tool_knowledge.success_indicator}\n"
                    f"  next_tool: {tool_knowledge.next_tool}\n"
                    f"  next_phase_trigger: {tool_knowledge.next_phase_trigger}\n"
                    f"  failure_action: {tool_knowledge.failure_action}\n"
                )

            output_summary = str(tool_output)[:500]
            prompt = (
                "You are an autonomous penetration testing AI.\n\n"
                f"Phase: {phase}\n"
                f"Tool just run: {tool_name}\n"
                f"Tool output summary: {output_summary}\n"
                f"{knowledge_str}\n"
                "Decide the next action.\n\n"
                'OUTPUT (strict JSON only): {"action": "continue|switch_tool|next_phase", '
                '"next_tool": "tool_name or null", "reason": "brief reason"}\n'
                "RULES: Output ONLY valid JSON. action must be one of the three values."
            )

            if not hasattr(self._ai, "_send"):
                return None

            response = self._ai._send(prompt)
            if response.get("status_code") != 200 or not response.get("raw_text"):
                return None

            return self._parse_ai_response(phase, response["raw_text"])

        except Exception as exc:
            logger.debug("[autonomous] AI decide failed: %s", exc)
            return None

    def _parse_ai_response(self, phase: str, raw_text: str) -> Optional[AutonomousDecision]:
        """Parse AI JSON response into AutonomousDecision."""
        import json  # noqa: PLC0415
        try:
            text = raw_text.strip()
            brace = text.find("{")
            if brace == -1:
                return None
            data = json.loads(text[brace:])
            if not isinstance(data, dict):
                return None

            action_str = str(data.get("action", "continue")).lower()
            action_map = {
                "continue": AutonomousAction.CONTINUE,
                "switch_tool": AutonomousAction.SWITCH_TOOL,
                "next_phase": AutonomousAction.NEXT_PHASE,
            }
            action = action_map.get(action_str, AutonomousAction.CONTINUE)

            return AutonomousDecision(
                action=action,
                phase=phase,
                reason=str(data.get("reason", "")),
                next_tool=data.get("next_tool") or None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception:
            return None

    def _heuristic_decide(
        self,
        phase: str,
        tool_name: str,
        tool_output: dict,
        tool_knowledge: Any,
    ) -> AutonomousDecision:
        """
        Heuristic decision based on ToolKnowledge and output.
        Used when AI is unavailable.
        """
        output_str = str(tool_output).lower()
        has_findings = bool(tool_output.get("vulnerabilities") or
                           tool_output.get("subdomains") or
                           tool_output.get("urls") or
                           tool_output.get("ports"))

        if tool_knowledge is None:
            # No knowledge — default to continue
            return AutonomousDecision(
                action=AutonomousAction.CONTINUE,
                phase=phase,
                reason="No ToolKnowledge entry — defaulting to continue",
                next_tool=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Check next_phase_trigger
        trigger = tool_knowledge.next_phase_trigger.lower()
        if has_findings and any(word in output_str for word in trigger.split()):
            return AutonomousDecision(
                action=AutonomousAction.NEXT_PHASE,
                phase=phase,
                reason=f"Phase trigger met: {tool_knowledge.next_phase_trigger}",
                next_tool=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Check failure_action
        if not has_findings:
            if tool_knowledge.failure_action == "skip_phase":
                return AutonomousDecision(
                    action=AutonomousAction.NEXT_PHASE,
                    phase=phase,
                    reason=f"No findings from {tool_name} — skipping phase per knowledge",
                    next_tool=None,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            # try_next_tool or escalate_to_ai → continue
            return AutonomousDecision(
                action=AutonomousAction.SWITCH_TOOL if tool_knowledge.next_tool else AutonomousAction.CONTINUE,
                phase=phase,
                reason=f"No findings from {tool_name} — trying next tool",
                next_tool=tool_knowledge.next_tool,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Has findings — suggest next_tool if available
        if tool_knowledge.next_tool:
            return AutonomousDecision(
                action=AutonomousAction.SWITCH_TOOL,
                phase=phase,
                reason=f"Findings from {tool_name} — switching to {tool_knowledge.next_tool}",
                next_tool=tool_knowledge.next_tool,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        return AutonomousDecision(
            action=AutonomousAction.CONTINUE,
            phase=phase,
            reason=f"Findings from {tool_name} — continuing phase",
            next_tool=None,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def run_phase_loop(
        self,
        phase: Any,
        target: str,
        context: Any,
        phase_manager: Any,
        emitter: Any,
    ) -> Any:
        """
        Autonomous phase loop: iterate FallbackChain tools, call decide() after each.

        Handles:
          - switch_tool: log reason + replacement tool, continue with that tool
          - next_phase: emit phase_transition event, return immediately
          - continue: proceed to next tool in chain

        Wraps each FallbackChain.execute() in try/except so tool errors apply
        FallbackChain logic without propagating.

        Terminates when all tools exhausted or no attack surface remains.
        Returns PhaseResult.
        """
        from hackempire.core.models import PhaseResult  # noqa: PLC0415
        from datetime import datetime, timezone  # noqa: PLC0415

        phase_value = phase.value if hasattr(phase, "value") else str(phase)
        started_at = datetime.now(timezone.utc).isoformat()

        try:
            # Get tools for this phase via phase_manager
            tools = []
            try:
                tools = phase_manager._get_tools_for_phase(phase)
            except Exception as exc:
                logger.warning("[autonomous] Could not get tools for phase %s: %s", phase_value, exc)

            if not tools:
                logger.warning("[autonomous] No tools for phase %s — skipping", phase_value)
                return PhaseResult(
                    phase=phase_value,
                    succeeded=False,
                    degraded=True,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

            last_chain_result = None
            iterations = 0
            tool_index = 0

            while tool_index < len(tools) and iterations < MAX_ITERATIONS_PER_PHASE:
                iterations += 1
                current_tool = tools[tool_index]
                tool_name = getattr(current_tool, "name", str(current_tool))

                # Execute the tool via FallbackChain (single tool)
                tool_output: dict = {}
                try:
                    from hackempire.core.fallback_chain import FallbackChain  # noqa: PLC0415
                    single_chain = FallbackChain(
                        tools=[current_tool],
                        emitter=emitter if emitter is not None else _NoOpEmitter(),
                        phase=phase_value,
                    )
                    chain_result = single_chain.execute(target)
                    last_chain_result = chain_result
                    tool_output = chain_result.results or {}
                    tool_output["_tool_name"] = tool_name
                    tool_output["_succeeded"] = not chain_result.degraded
                except Exception as exc:
                    logger.warning("[autonomous] Tool %s error: %s — applying FallbackChain logic", tool_name, exc)
                    tool_output = {"_tool_name": tool_name, "_succeeded": False, "error": str(exc)}

                # Ask AI to decide next action
                decision = self.decide(
                    phase=phase_value,
                    tool_name=tool_name,
                    tool_output=tool_output,
                    context=context,
                )

                # Stream decision to dashboard and append to context
                if emitter is not None:
                    try:
                        emitter.emit_autonomous_decision(decision)
                    except Exception:
                        pass
                try:
                    if hasattr(context, "autonomous_decisions"):
                        context.autonomous_decisions.append(decision)
                except Exception:
                    pass

                self._log_decision(decision)

                # Handle decision action
                if decision.action == AutonomousAction.NEXT_PHASE:
                    # Emit phase_transition event
                    if emitter is not None:
                        try:
                            emitter._emit("phase_transition", {
                                "event": "phase_transition",
                                "phase": phase_value,
                                "reason": decision.reason,
                            })
                        except Exception:
                            pass
                    logger.info("[autonomous] Phase transition triggered for %s: %s", phase_value, decision.reason)
                    # Return with current results
                    succeeded = last_chain_result is not None and not last_chain_result.degraded
                    return PhaseResult(
                        phase=phase_value,
                        succeeded=succeeded,
                        degraded=not succeeded,
                        chain_result=last_chain_result,
                        started_at=started_at,
                        completed_at=datetime.now(timezone.utc).isoformat(),
                    )

                elif decision.action == AutonomousAction.SWITCH_TOOL:
                    replacement = decision.next_tool
                    logger.info(
                        "[autonomous] switch_tool: reason=%s replacement=%s",
                        decision.reason,
                        replacement or "none",
                    )
                    # Try to find replacement tool in remaining tools
                    found_replacement = False
                    if replacement:
                        for j, t in enumerate(tools):
                            t_name = getattr(t, "name", str(t))
                            if t_name == replacement and j != tool_index:
                                tool_index = j
                                found_replacement = True
                                break
                    if not found_replacement:
                        # Move to next tool
                        tool_index += 1

                else:  # CONTINUE
                    tool_index += 1

            # All tools exhausted
            succeeded = last_chain_result is not None and not last_chain_result.degraded
            return PhaseResult(
                phase=phase_value,
                succeeded=succeeded,
                degraded=not succeeded,
                chain_result=last_chain_result,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as exc:
            logger.error("[autonomous] run_phase_loop error for %s: %s", phase_value, exc)
            return PhaseResult(
                phase=phase_value,
                succeeded=False,
                degraded=True,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

    def _log_decision(self, decision: AutonomousDecision) -> None:
        """Log the autonomous decision."""
        logger.info(
            "[autonomous] Phase=%s Action=%s NextTool=%s Reason=%s",
            decision.phase,
            decision.action.value,
            decision.next_tool or "none",
            decision.reason[:100],
        )


class _NoOpEmitter:
    """Minimal no-op emitter for when no emitter is provided."""
    def emit_tool_start(self, *a, **kw): pass
    def emit_tool_result(self, *a, **kw): pass
    def emit_tool_error(self, *a, **kw): pass
    def emit_autonomous_decision(self, *a, **kw): pass
    def _emit(self, *a, **kw): pass
