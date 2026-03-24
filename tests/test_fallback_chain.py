"""
Property-based tests for FallbackChain.

Property 2: FallbackChain Stops on First Success
  - when tool[i] succeeds, tool[i+1] is never called
  **Validates: Requirements 2.1**

Property 3: FallbackChain Degraded on All Failures
  - all tools raising exceptions yields degraded=True
  **Validates: Requirements 2.5**

Property 4: FallbackChain Never Raises
  - no exception for any tool list and target combination
  **Validates: Requirements 2.6**

Property 5: Degraded Iff No Succeeded Tool
  - degraded == (succeeded_tool is None) always holds
  **Validates: Requirements 2.7**
"""

import sys
import os

# When running from the hackempire/ directory, add the parent so that
# `import hackempire` resolves (needed by fallback_chain.py's own imports).
_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)          # hackempire/
_parent = os.path.dirname(_pkg_root)        # repo root (contains hackempire/)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.core.fallback_chain import FallbackChain
from hackempire.core.models import ChainResult
from hackempire.tools.base_tool import ToolExecutionError, ToolNotInstalledError, ToolTimeoutError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_emitter():
    """Return a no-op emitter mock."""
    class _Emitter:
        def emit_tool_start(self, *a, **kw): pass
        def emit_tool_result(self, *a, **kw): pass
        def emit_tool_error(self, *a, **kw): pass
    return _Emitter()


class _SuccessTool:
    """Tool that always succeeds and records how many times run() was called."""
    def __init__(self, name: str = "success_tool"):
        self.name = name
        self.call_count = 0

    def run(self, target: str) -> dict:
        self.call_count += 1
        return {"data": "ok", "target": target}


class _FailTool:
    """Tool that always raises one of the three expected exception types."""
    def __init__(self, exc_class, name: str = "fail_tool"):
        self.name = name
        self._exc_class = exc_class
        self.call_count = 0

    def run(self, target: str) -> dict:
        self.call_count += 1
        raise self._exc_class(f"{self.name} failed")


class _WildTool:
    """Tool that raises an arbitrary (unexpected) exception."""
    def __init__(self, exc: Exception, name: str = "wild_tool"):
        self.name = name
        self._exc = exc

    def run(self, target: str) -> dict:
        raise self._exc


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_TOOL_ERRORS = [ToolNotInstalledError, ToolTimeoutError, ToolExecutionError]

# Strategy: pick a random known exception class
_exc_class_st = st.sampled_from(_TOOL_ERRORS)

# Strategy: a non-empty target string
_target_st = st.text(min_size=1, max_size=80).filter(lambda s: s.strip())

# Strategy: list of 1..6 failing tools (each raises a random known exception)
_all_fail_tools_st = st.lists(
    _exc_class_st.map(lambda ec: _FailTool(ec)),
    min_size=1,
    max_size=6,
)

# Strategy: index i in [0, n-1] and a list of n tools where tool[i] succeeds
# and all tools before i fail.
@st.composite
def _tools_with_success_at_i(draw):
    n = draw(st.integers(min_value=1, max_value=6))
    i = draw(st.integers(min_value=0, max_value=n - 1))
    tools = []
    for j in range(n):
        if j < i:
            exc_class = draw(_exc_class_st)
            tools.append(_FailTool(exc_class, name=f"fail_{j}"))
        elif j == i:
            tools.append(_SuccessTool(name=f"success_{j}"))
        else:
            tools.append(_SuccessTool(name=f"after_{j}"))
    return i, tools


# Strategy: tools that may raise any exception (including unexpected ones)
@st.composite
def _any_tools_st(draw):
    n = draw(st.integers(min_value=1, max_value=6))
    tools = []
    for j in range(n):
        kind = draw(st.integers(min_value=0, max_value=3))
        if kind == 0:
            tools.append(_SuccessTool(name=f"t{j}"))
        elif kind == 1:
            exc_class = draw(_exc_class_st)
            tools.append(_FailTool(exc_class, name=f"t{j}"))
        elif kind == 2:
            tools.append(_WildTool(RuntimeError("unexpected"), name=f"t{j}"))
        else:
            tools.append(_WildTool(ValueError("bad value"), name=f"t{j}"))
    return tools


# ---------------------------------------------------------------------------
# Property 2: FallbackChain Stops on First Success
# ---------------------------------------------------------------------------

@given(data=_tools_with_success_at_i(), target=_target_st)
@settings(max_examples=200)
def test_property_2_stops_on_first_success(data, target):
    """Property 2: FallbackChain Stops on First Success — when tool[i] succeeds,
    tool[i+1] is never called.

    **Validates: Requirements 2.1**
    """
    i, tools = data
    chain = FallbackChain(tools=tools, emitter=_make_emitter(), phase="test")
    result = chain.execute(target)

    # The chain must have stopped at tool[i]
    assert result.succeeded_tool == tools[i].name, (
        f"Expected succeeded_tool={tools[i].name!r}, got {result.succeeded_tool!r}"
    )

    # All tools after i must have call_count == 0
    for j in range(i + 1, len(tools)):
        assert tools[j].call_count == 0, (
            f"tool[{j}] ({tools[j].name}) was called after tool[{i}] succeeded"
        )


# ---------------------------------------------------------------------------
# Property 3: FallbackChain Degraded on All Failures
# ---------------------------------------------------------------------------

@given(tools=_all_fail_tools_st, target=_target_st)
@settings(max_examples=200)
def test_property_3_degraded_on_all_failures(tools, target):
    """Property 3: FallbackChain Degraded on All Failures — all tools raising
    exceptions yields degraded=True.

    **Validates: Requirements 2.5**
    """
    chain = FallbackChain(tools=tools, emitter=_make_emitter(), phase="test")
    result = chain.execute(target)

    assert result.degraded is True, (
        f"Expected degraded=True when all tools fail, got degraded={result.degraded}"
    )


# ---------------------------------------------------------------------------
# Property 4: FallbackChain Never Raises
# ---------------------------------------------------------------------------

@given(tools=_any_tools_st(), target=_target_st)
@settings(max_examples=200)
def test_property_4_never_raises(tools, target):
    """Property 4: FallbackChain Never Raises — no exception for any tool list
    and target combination.

    **Validates: Requirements 2.6**
    """
    chain = FallbackChain(tools=tools, emitter=_make_emitter(), phase="test")
    try:
        result = chain.execute(target)
    except Exception as exc:
        raise AssertionError(
            f"FallbackChain.execute() raised {type(exc).__name__}: {exc}"
        ) from exc

    assert isinstance(result, ChainResult), (
        f"Expected ChainResult, got {type(result)}"
    )


# ---------------------------------------------------------------------------
# Property 5: Degraded Iff No Succeeded Tool
# ---------------------------------------------------------------------------

@given(tools=_any_tools_st(), target=_target_st)
@settings(max_examples=200)
def test_property_5_degraded_iff_no_succeeded_tool(tools, target):
    """Property 5: Degraded Iff No Succeeded Tool — degraded == (succeeded_tool
    is None) always holds.

    **Validates: Requirements 2.7**
    """
    chain = FallbackChain(tools=tools, emitter=_make_emitter(), phase="test")
    result = chain.execute(target)

    assert result.degraded == (result.succeeded_tool is None), (
        f"Invariant violated: degraded={result.degraded}, "
        f"succeeded_tool={result.succeeded_tool!r}"
    )
