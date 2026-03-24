"""
Property-based tests for RealTimeEmitter.

Property 8: RealTimeEmitter Never Raises — no exception for any emit sequence
in any SocketIO state.
  **Validates: Requirements 4.6, 4.7**
"""

import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)      # hackempire/
_parent = os.path.dirname(_pkg_root)    # repo root (contains hackempire/)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.web.realtime_emitter import RealTimeEmitter


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
@settings(max_examples=300)
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
