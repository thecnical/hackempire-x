"""
Property-based tests for RealTimeEmitter.

Property 8: RealTimeEmitter Never Raises — no exception for any emit sequence
in any SocketIO state.
  **Validates: Requirements 4.6, 4.7**

Property 13: Dashboard panel data contains required fields
  **Validates: Requirements 6.1, 6.2, 6.3**
"""

import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)      # hackempire/
_parent = os.path.dirname(_pkg_root)    # repo root (contains hackempire/)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from unittest.mock import MagicMock
from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.web.realtime_emitter import RealTimeEmitter
from hackempire.core.models import Vulnerability


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_text_st = st.text(max_size=80)
_dict_st = st.dictionaries(
    keys=st.text(max_size=20),
    values=st.one_of(st.text(max_size=40), st.integers(), st.booleans(), st.none()),
    max_size=5,
)

# Exceptions that a misbehaving SocketIO might raise
_EXCEPTIONS = [
    RuntimeError("socket error"),
    ConnectionError("connection lost"),
    OSError("os error"),
    ValueError("bad value"),
    Exception("generic error"),
]

_exc_st = st.sampled_from(_EXCEPTIONS)


@st.composite
def _socketio_st(draw):
    """Return either None or a mock SocketIO that may raise on emit()."""
    kind = draw(st.integers(min_value=0, max_value=2))
    if kind == 0:
        return None
    elif kind == 1:
        # Well-behaved mock
        class _GoodSocketIO:
            def emit(self, event, payload):
                pass
        return _GoodSocketIO()
    else:
        # Misbehaving mock that raises
        exc = draw(_exc_st)
        class _BadSocketIO:
            def __init__(self, e):
                self._exc = e
            def emit(self, event, payload):
                raise self._exc
        return _BadSocketIO(exc)


# ---------------------------------------------------------------------------
# Property 8: RealTimeEmitter Never Raises
# ---------------------------------------------------------------------------

@given(
    socketio=_socketio_st(),
    phase=_text_st,
    tool=_text_st,
    target=_text_st,
    result=_dict_st,
    error=_text_st,
    data=_text_st,
)
@settings(max_examples=30)
def test_property_8_never_raises(socketio, phase, tool, target, result, error, data):
    """Property 8: RealTimeEmitter Never Raises — no exception for any emit
    sequence in any SocketIO state.

    **Validates: Requirements 4.6, 4.7**
    """
    emitter = RealTimeEmitter(socketio)

    try:
        emitter.emit_tool_start(phase, tool, target)
        emitter.emit_tool_result(phase, tool, result)
        emitter.emit_tool_error(phase, tool, error)
        emitter.emit_phase_complete(phase, result)
        emitter.emit_todo_update(result)
        emitter.emit_scan_complete(result)
        emitter.emit_vuln_found(result)
        emitter.emit_terminal_output(data)
    except Exception as exc:
        raise AssertionError(
            f"RealTimeEmitter raised {type(exc).__name__}: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Property 13: Dashboard panel data contains required fields
# Feature: hackempire-x-v4, Property 13: Dashboard panel data contains required fields
# ---------------------------------------------------------------------------

_severity_st = st.sampled_from(["info", "low", "medium", "high", "critical"])
_url_st = st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="/:.-_?=&"))
_host_st = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=".-_"))
_confidence_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

_vuln_st = st.builds(
    Vulnerability,
    name=st.text(min_size=1, max_size=80),
    severity=_severity_st,
    confidence=_confidence_st,
    target=_host_st,
    url=_url_st,
)


@given(vuln=_vuln_st)
@settings(max_examples=10)
def test_property_13_finding_update_required_fields(vuln: Vulnerability):
    """Property 13: Dashboard panel data contains required fields.

    For any finding_update SocketIO event emitted during a scan, the payload
    SHALL contain host, service, exploit_path fields for the AttackGraph and
    technique_id, tactic fields for the MITREOverlay.

    # Feature: hackempire-x-v4, Property 13: Dashboard panel data contains required fields
    **Validates: Requirements 6.1, 6.2, 6.3**
    """
    from hackempire.ai.mitre_mapper import map_finding

    emitted_payloads: list[dict] = []

    class _CapturingSocketIO:
        def emit(self, event, payload):
            if event == "finding_update":
                emitted_payloads.append(payload)

    emitter = RealTimeEmitter(_CapturingSocketIO())

    mitre = map_finding(vuln.name)
    finding_payload = {
        "host": vuln.target,
        "service": vuln.url,
        "exploit_path": vuln.url,
        "technique_id": mitre["technique_id"],
        "tactic": mitre["tactic"],
        "name": vuln.name,
    }
    emitter.emit_finding_update(finding_payload)

    assert len(emitted_payloads) == 1, "Expected exactly one finding_update event"
    payload = emitted_payloads[0]
    inner = payload.get("finding", payload)

    # AttackGraph required fields
    assert "host" in inner, f"Missing 'host' in finding_update payload: {inner}"
    assert "service" in inner, f"Missing 'service' in finding_update payload: {inner}"
    assert "exploit_path" in inner, f"Missing 'exploit_path' in finding_update payload: {inner}"

    # MITREOverlay required fields
    assert "technique_id" in inner, f"Missing 'technique_id' in finding_update payload: {inner}"
    assert "tactic" in inner, f"Missing 'tactic' in finding_update payload: {inner}"

    # Values must be non-empty strings
    assert isinstance(inner["technique_id"], str) and inner["technique_id"], \
        f"technique_id must be a non-empty string, got: {inner['technique_id']!r}"
    assert isinstance(inner["tactic"], str) and inner["tactic"], \
        f"tactic must be a non-empty string, got: {inner['tactic']!r}"


@given(vuln=_vuln_st)
@settings(max_examples=10)
def test_property_13_poc_ready_required_fields(vuln: Vulnerability):
    """Property 13 (poc_ready): For any poc_ready event, the payload SHALL
    contain curl_command and affected_url fields.

    # Feature: hackempire-x-v4, Property 13: Dashboard panel data contains required fields
    **Validates: Requirements 6.1, 6.2, 6.3**
    """
    emitted_payloads: list[dict] = []

    class _CapturingSocketIO:
        def emit(self, event, payload):
            if event == "poc_ready":
                emitted_payloads.append(payload)

    emitter = RealTimeEmitter(_CapturingSocketIO())

    poc_payload = {
        "curl_command": f"curl -sk '{vuln.url}'",
        "affected_url": vuln.url,
        "vuln_name": vuln.name,
    }
    emitter.emit_poc_ready(poc_payload)

    assert len(emitted_payloads) == 1, "Expected exactly one poc_ready event"
    payload = emitted_payloads[0]
    inner = payload.get("poc", payload)

    # PoCPreview required fields
    assert "curl_command" in inner, f"Missing 'curl_command' in poc_ready payload: {inner}"
    assert "affected_url" in inner, f"Missing 'affected_url' in poc_ready payload: {inner}"


# ---------------------------------------------------------------------------
# Task 9.2: Unit tests for new emitter methods — exception swallowing
# ---------------------------------------------------------------------------

class _RaisingSocketIO:
    """SocketIO mock that always raises on emit()."""
    def emit(self, event, payload):
        raise RuntimeError("SocketIO unavailable")


def test_emit_finding_update_swallows_exception():
    """emit_finding_update() must not raise when SocketIO raises.
    Requirements: 6.6, 6.7
    """
    emitter = RealTimeEmitter(_RaisingSocketIO())
    # Must not raise
    emitter.emit_finding_update({"host": "h", "service": "s", "exploit_path": "/", "technique_id": "T1190", "tactic": "Initial Access"})


def test_emit_poc_ready_swallows_exception():
    """emit_poc_ready() must not raise when SocketIO raises.
    Requirements: 6.6, 6.7
    """
    emitter = RealTimeEmitter(_RaisingSocketIO())
    emitter.emit_poc_ready({"curl_command": "curl -sk 'http://x'", "affected_url": "http://x"})


def test_emit_autonomous_decision_swallows_exception():
    """emit_autonomous_decision() must not raise when SocketIO raises.
    Requirements: 6.6, 6.7
    """
    emitter = RealTimeEmitter(_RaisingSocketIO())
    emitter.emit_autonomous_decision({"action": "continue", "phase": "RECON", "reason": "test"})


def test_emit_kb_update_swallows_exception():
    """emit_kb_update() must not raise when SocketIO raises.
    Requirements: 6.6, 6.7
    """
    emitter = RealTimeEmitter(_RaisingSocketIO())
    emitter.emit_kb_update({"target": "example.com", "findings": []})


def test_emit_finding_update_noop_when_socketio_none():
    """emit_finding_update() is a no-op when socketio is None.
    Requirements: 6.6, 6.7
    """
    emitter = RealTimeEmitter(None)
    emitter.emit_finding_update({"host": "h", "service": "s", "exploit_path": "/", "technique_id": "T1190", "tactic": "Initial Access"})


def test_emit_poc_ready_noop_when_socketio_none():
    """emit_poc_ready() is a no-op when socketio is None.
    Requirements: 6.6, 6.7
    """
    emitter = RealTimeEmitter(None)
    emitter.emit_poc_ready({"curl_command": "curl -sk 'http://x'", "affected_url": "http://x"})


def test_emit_autonomous_decision_noop_when_socketio_none():
    """emit_autonomous_decision() is a no-op when socketio is None.
    Requirements: 6.6, 6.7
    """
    emitter = RealTimeEmitter(None)
    emitter.emit_autonomous_decision({"action": "continue"})


def test_emit_kb_update_noop_when_socketio_none():
    """emit_kb_update() is a no-op when socketio is None.
    Requirements: 6.6, 6.7
    """
    emitter = RealTimeEmitter(None)
    emitter.emit_kb_update({"target": "example.com"})


def test_emit_finding_update_payload_structure():
    """emit_finding_update() emits a payload with the 'finding' key wrapping the data."""
    captured = []

    class _Cap:
        def emit(self, event, payload):
            captured.append((event, payload))

    emitter = RealTimeEmitter(_Cap())
    finding = {"host": "10.0.0.1", "service": "http", "exploit_path": "/admin",
               "technique_id": "T1190", "tactic": "Initial Access"}
    emitter.emit_finding_update(finding)

    assert len(captured) == 1
    event, payload = captured[0]
    assert event == "finding_update"
    assert payload["finding"] == finding
    assert "timestamp" in payload


def test_emit_poc_ready_payload_structure():
    """emit_poc_ready() emits a payload with the 'poc' key wrapping the data."""
    captured = []

    class _Cap:
        def emit(self, event, payload):
            captured.append((event, payload))

    emitter = RealTimeEmitter(_Cap())
    poc = {"curl_command": "curl -sk 'http://x'", "affected_url": "http://x"}
    emitter.emit_poc_ready(poc)

    assert len(captured) == 1
    event, payload = captured[0]
    assert event == "poc_ready"
    assert payload["poc"] == poc
    assert "timestamp" in payload

