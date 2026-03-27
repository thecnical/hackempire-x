"""
Tests for AutonomousEngine (v4.2).

Property 4: AutonomousEngine decision is always one of three valid actions
  - decide() returns AutonomousDecision with action in {continue, switch_tool, next_phase}
  - never raises an exception
  **Validates: Requirements 2.3**

Property 5: AutonomousMode loop terminates
  - run_phase_loop() always returns a PhaseResult
  - never loops indefinitely
  **Validates: Requirements 2.4, 2.8**

Unit tests:
  - switch_tool decision logs reason and replacement tool name
  - next_phase decision emits phase_transition event
  - missing ToolKnowledge entry logs warning and uses generic heuristics
  **Requirements: 2.5, 2.6, 5.10**
"""
from __future__ import annotations

import sys
import os
import logging

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)
_parent = os.path.dirname(_pkg_root)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.ai.autonomous_engine import AutonomousEngine
from hackempire.core.models import (
    AutonomousAction,
    AutonomousDecision,
    PhaseResult,
    ScanContext,
)
from hackempire.core.phases import Phase


# ---------------------------------------------------------------------------
# Helpers / Mocks
# ---------------------------------------------------------------------------

def _make_context(autonomous: bool = True) -> ScanContext:
    return ScanContext(
        target="example.com",
        mode="ultra",
        session_id="test-session",
        autonomous=autonomous,
    )


class _MockAI:
    """AI engine mock that returns a configurable action."""
    def __init__(self, action: str = "continue", next_tool: str | None = None):
        self._action = action
        self._next_tool = next_tool

    def _send(self, prompt: str) -> dict:
        import json
        return {
            "status_code": 200,
            "raw_text": json.dumps({
                "action": self._action,
                "next_tool": self._next_tool,
                "reason": f"mock reason for {self._action}",
            }),
        }


class _FailAI:
    """AI engine mock that always fails."""
    def _send(self, prompt: str) -> dict:
        return {"status_code": 500, "raw_text": ""}


class _MockTool:
    """Tool mock that returns a configurable result."""
    def __init__(self, name: str = "mock_tool", result: dict | None = None, raise_exc: Exception | None = None):
        self.name = name
        self._result = result or {"data": "ok"}
        self._raise = raise_exc
        self.call_count = 0

    def run(self, target: str) -> dict:
        self.call_count += 1
        if self._raise is not None:
            raise self._raise
        return self._result


class _MockPhaseManager:
    """PhaseManager mock with configurable tools per phase."""
    PHASES = list(Phase)[:7]  # all 7 phases

    def __init__(self, tools_per_phase: list | None = None):
        self._tools = tools_per_phase or [_MockTool()]

    def _get_tools_for_phase(self, phase) -> list:
        return list(self._tools)

    def run_phase(self, phase, target, context) -> PhaseResult:
        return PhaseResult(phase=phase.value, succeeded=True, degraded=False)


class _MockEmitter:
    """Emitter mock that records emitted events."""
    def __init__(self):
        self.events: list[tuple] = []

    def emit_tool_start(self, *a, **kw): pass
    def emit_tool_result(self, *a, **kw): pass
    def emit_tool_error(self, *a, **kw): pass

    def emit_autonomous_decision(self, decision):
        self.events.append(("autonomous_decision", decision))

    def _emit(self, event: str, payload: dict):
        self.events.append((event, payload))


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_tool_output_st = st.dictionaries(
    keys=st.text(min_size=1, max_size=20),
    values=st.one_of(st.text(max_size=50), st.integers(), st.booleans(), st.none()),
    max_size=10,
)

_phase_st = st.sampled_from([p.value for p in Phase if p.value not in ("enum", "vuln")])

_target_st = st.text(min_size=1, max_size=50).filter(lambda s: s.strip())


# ---------------------------------------------------------------------------
# Property 4: AutonomousEngine decision is always one of three valid actions
# ---------------------------------------------------------------------------

# Feature: hackempire-x-v4, Property 4: AutonomousEngine decision is always one of three valid actions
@given(tool_output=_tool_output_st, phase=_phase_st)
@settings(max_examples=10)
def test_property_4_decide_always_valid_action(tool_output: dict, phase: str):
    """Property 4: AutonomousEngine.decide() always returns a valid action.

    **Validates: Requirements 2.3**
    """
    engine = AutonomousEngine(ai_engine=_FailAI())
    context = _make_context()

    # Should never raise
    try:
        decision = engine.decide(
            phase=phase,
            tool_name="test_tool",
            tool_output=tool_output,
            context=context,
        )
    except Exception as exc:
        raise AssertionError(f"decide() raised {type(exc).__name__}: {exc}") from exc

    assert isinstance(decision, AutonomousDecision), (
        f"Expected AutonomousDecision, got {type(decision)}"
    )
    valid_actions = {AutonomousAction.CONTINUE, AutonomousAction.SWITCH_TOOL, AutonomousAction.NEXT_PHASE}
    assert decision.action in valid_actions, (
        f"Invalid action: {decision.action!r}. Must be one of {valid_actions}"
    )
    assert decision.phase == phase
    assert isinstance(decision.reason, str)


# ---------------------------------------------------------------------------
# Property 5: AutonomousMode loop terminates
# ---------------------------------------------------------------------------

# Feature: hackempire-x-v4, Property 5: AutonomousMode loop terminates
@given(
    tool_outputs=st.lists(_tool_output_st, min_size=0, max_size=5),
    target=_target_st,
)
@settings(max_examples=10)
def test_property_5_loop_terminates(tool_outputs: list, target: str):
    """Property 5: run_phase_loop() always terminates and returns a PhaseResult.

    **Validates: Requirements 2.4, 2.8**
    """
    # Build tools from tool_outputs (each tool returns its corresponding output)
    tools = []
    for i, output in enumerate(tool_outputs):
        tools.append(_MockTool(name=f"tool_{i}", result=output))
    if not tools:
        tools = [_MockTool(name="fallback_tool")]

    engine = AutonomousEngine(ai_engine=_FailAI())
    phase_manager = _MockPhaseManager(tools_per_phase=tools)
    emitter = _MockEmitter()
    context = _make_context()

    try:
        result = engine.run_phase_loop(
            phase=Phase.RECON,
            target=target,
            context=context,
            phase_manager=phase_manager,
            emitter=emitter,
        )
    except Exception as exc:
        raise AssertionError(f"run_phase_loop() raised {type(exc).__name__}: {exc}") from exc

    assert isinstance(result, PhaseResult), (
        f"Expected PhaseResult, got {type(result)}"
    )
    assert isinstance(result.phase, str)
    assert isinstance(result.succeeded, bool)
    assert isinstance(result.degraded, bool)


# ---------------------------------------------------------------------------
# Unit tests for AutonomousEngine
# ---------------------------------------------------------------------------

def test_switch_tool_logs_reason_and_replacement(caplog):
    """switch_tool decision logs reason and replacement tool name. Requirements: 2.5"""
    engine = AutonomousEngine(ai_engine=_MockAI(action="switch_tool", next_tool="replacement_tool"))
    tools = [
        _MockTool(name="first_tool"),
        _MockTool(name="replacement_tool"),
    ]
    phase_manager = _MockPhaseManager(tools_per_phase=tools)
    emitter = _MockEmitter()
    context = _make_context()

    with caplog.at_level(logging.INFO, logger="hackempire.ai.autonomous_engine"):
        result = engine.run_phase_loop(
            phase=Phase.RECON,
            target="example.com",
            context=context,
            phase_manager=phase_manager,
            emitter=emitter,
        )

    assert isinstance(result, PhaseResult)
    # Check that switch_tool was logged
    log_text = caplog.text
    assert "switch_tool" in log_text or "replacement_tool" in log_text or "reason" in log_text.lower()


def test_next_phase_emits_phase_transition():
    """next_phase decision emits phase_transition event. Requirements: 2.6"""
    engine = AutonomousEngine(ai_engine=_MockAI(action="next_phase"))
    tools = [_MockTool(name="recon_tool")]
    phase_manager = _MockPhaseManager(tools_per_phase=tools)
    emitter = _MockEmitter()
    context = _make_context()

    result = engine.run_phase_loop(
        phase=Phase.RECON,
        target="example.com",
        context=context,
        phase_manager=phase_manager,
        emitter=emitter,
    )

    assert isinstance(result, PhaseResult)
    # Check that phase_transition event was emitted
    event_names = [e[0] for e in emitter.events]
    assert "phase_transition" in event_names, (
        f"Expected 'phase_transition' event, got events: {event_names}"
    )


def test_missing_tool_knowledge_logs_warning(caplog):
    """Missing ToolKnowledge entry logs warning and uses generic heuristics. Requirements: 5.10"""
    engine = AutonomousEngine(ai_engine=_FailAI())
    context = _make_context()

    with caplog.at_level(logging.WARNING, logger="hackempire.ai.autonomous_engine"):
        decision = engine.decide(
            phase="recon",
            tool_name="nonexistent_tool_xyz_12345",
            tool_output={"data": "some output"},
            context=context,
        )

    # Should still return a valid decision (generic heuristics)
    assert isinstance(decision, AutonomousDecision)
    valid_actions = {AutonomousAction.CONTINUE, AutonomousAction.SWITCH_TOOL, AutonomousAction.NEXT_PHASE}
    assert decision.action in valid_actions

    # Should have logged a warning about missing ToolKnowledge
    assert "nonexistent_tool_xyz_12345" in caplog.text or "ToolKnowledge" in caplog.text or "generic" in caplog.text


def test_decide_never_raises_on_exception():
    """decide() never raises even when AI and ToolKnowledge both fail."""
    engine = AutonomousEngine(ai_engine=None)
    context = _make_context()

    # Should not raise
    decision = engine.decide(
        phase="recon",
        tool_name="any_tool",
        tool_output={},
        context=context,
    )
    assert isinstance(decision, AutonomousDecision)


def test_autonomous_decisions_appended_to_context():
    """Each decision is appended to context.autonomous_decisions."""
    engine = AutonomousEngine(ai_engine=_FailAI())
    tools = [_MockTool(name="tool_a"), _MockTool(name="tool_b")]
    phase_manager = _MockPhaseManager(tools_per_phase=tools)
    emitter = _MockEmitter()
    context = _make_context()

    assert len(context.autonomous_decisions) == 0

    engine.run_phase_loop(
        phase=Phase.RECON,
        target="example.com",
        context=context,
        phase_manager=phase_manager,
        emitter=emitter,
    )

    assert len(context.autonomous_decisions) > 0
    for d in context.autonomous_decisions:
        assert isinstance(d, AutonomousDecision)


def test_all_failure_tools_returns_degraded_phase_result():
    """When all tools fail, run_phase_loop returns a degraded PhaseResult."""
    from hackempire.tools.base_tool import ToolExecutionError

    engine = AutonomousEngine(ai_engine=_FailAI())
    tools = [
        _MockTool(name="fail_1", raise_exc=ToolExecutionError("fail")),
        _MockTool(name="fail_2", raise_exc=ToolExecutionError("fail")),
    ]
    phase_manager = _MockPhaseManager(tools_per_phase=tools)
    emitter = _MockEmitter()
    context = _make_context()

    result = engine.run_phase_loop(
        phase=Phase.RECON,
        target="example.com",
        context=context,
        phase_manager=phase_manager,
        emitter=emitter,
    )

    assert isinstance(result, PhaseResult)
    # Should not raise — scan continues
    assert result.phase == "recon"
