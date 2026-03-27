"""
Property-based tests for AegisBridge.

Property 14: AegisBridge Never Raises
  - run() always returns ChainResult, never raises
  **Validates: Requirements 10.3**
"""

import sys
import os
import json
import subprocess
from unittest.mock import MagicMock, patch

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)          # hackempire/
_parent = os.path.dirname(_pkg_root)        # repo root (contains hackempire/)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.tools.external.aegis_bridge import AegisBridge
from hackempire.core.models import ChainResult


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_target_st = st.text(min_size=1, max_size=80)
_phase_st = st.text(min_size=1, max_size=40)

_json_record_types = ["subdomain", "url", "vulnerability", "unknown_type"]

@st.composite
def _valid_json_lines_st(draw):
    """Generate stdout bytes with zero or more valid JSON lines."""
    n = draw(st.integers(min_value=0, max_value=5))
    lines = []
    for _ in range(n):
        rtype = draw(st.sampled_from(_json_record_types))
        if rtype == "subdomain":
            lines.append(json.dumps({"type": "subdomain", "value": draw(st.text(min_size=1, max_size=30))}))
        elif rtype == "url":
            lines.append(json.dumps({"type": "url", "value": draw(st.text(min_size=1, max_size=50))}))
        elif rtype == "vulnerability":
            lines.append(json.dumps({
                "type": "vulnerability",
                "name": draw(st.text(min_size=1, max_size=20)),
                "severity": draw(st.sampled_from(["info", "low", "medium", "high", "critical"])),
                "url": draw(st.text(min_size=1, max_size=50)),
                "evidence": draw(st.text(max_size=30)),
            }))
        else:
            lines.append(json.dumps({"type": "unknown_type", "value": "x"}))
    return "\n".join(lines).encode()


@st.composite
def _invalid_json_stdout_st(draw):
    """Generate stdout bytes that are NOT valid JSON lines."""
    garbage = draw(st.text(min_size=0, max_size=200))
    return garbage.encode(errors="replace")


# ---------------------------------------------------------------------------
# Property 14: AegisBridge Never Raises
# ---------------------------------------------------------------------------

@given(target=_target_st, phase=_phase_st)
@settings(max_examples=10)
def test_property_14_aegis_not_available_ensure_fails(target, phase):
    """Property 14 (case 1): aegis not available, ensure_installed fails → degraded ChainResult.

    **Validates: Requirements 10.3**
    """
    bridge = AegisBridge()
    with patch.object(bridge, "is_available", return_value=False), \
         patch.object(bridge, "ensure_installed", return_value=False):
        try:
            result = bridge.run(target, phase)
        except Exception as exc:
            raise AssertionError(
                f"AegisBridge.run() raised {type(exc).__name__}: {exc}"
            ) from exc

    assert isinstance(result, ChainResult), f"Expected ChainResult, got {type(result)}"
    assert result.degraded is True


@given(target=_target_st, phase=_phase_st, stdout=_valid_json_lines_st())
@settings(max_examples=10)
def test_property_14_aegis_available_subprocess_succeeds(target, phase, stdout):
    """Property 14 (case 2): aegis available, subprocess succeeds with valid JSON lines → non-degraded ChainResult.

    **Validates: Requirements 10.3**
    """
    bridge = AegisBridge()
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = stdout
    mock_proc.stderr = b""

    with patch.object(bridge, "is_available", return_value=True), \
         patch("hackempire.tools.external.aegis_bridge.subprocess.run", return_value=mock_proc):
        try:
            result = bridge.run(target, phase)
        except Exception as exc:
            raise AssertionError(
                f"AegisBridge.run() raised {type(exc).__name__}: {exc}"
            ) from exc

    assert isinstance(result, ChainResult), f"Expected ChainResult, got {type(result)}"
    # When stdout is non-empty, result should not be degraded
    if stdout:
        assert result.degraded is False
    else:
        # empty stdout → treated as failure
        assert result.degraded is True


@given(target=_target_st, phase=_phase_st)
@settings(max_examples=10)
def test_property_14_aegis_available_subprocess_fails(target, phase):
    """Property 14 (case 3): aegis available, subprocess fails (returncode != 0) → degraded ChainResult.

    **Validates: Requirements 10.3**
    """
    bridge = AegisBridge()
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = b""
    mock_proc.stderr = b"some error"

    with patch.object(bridge, "is_available", return_value=True), \
         patch("hackempire.tools.external.aegis_bridge.subprocess.run", return_value=mock_proc):
        try:
            result = bridge.run(target, phase)
        except Exception as exc:
            raise AssertionError(
                f"AegisBridge.run() raised {type(exc).__name__}: {exc}"
            ) from exc

    assert isinstance(result, ChainResult), f"Expected ChainResult, got {type(result)}"
    assert result.degraded is True


@given(target=_target_st, phase=_phase_st)
@settings(max_examples=10)
def test_property_14_aegis_available_subprocess_raises(target, phase):
    """Property 14 (case 4): aegis available, subprocess raises exception → degraded ChainResult.

    **Validates: Requirements 10.3**
    """
    bridge = AegisBridge()

    with patch.object(bridge, "is_available", return_value=True), \
         patch("hackempire.tools.external.aegis_bridge.subprocess.run", side_effect=OSError("binary not found")):
        try:
            result = bridge.run(target, phase)
        except Exception as exc:
            raise AssertionError(
                f"AegisBridge.run() raised {type(exc).__name__}: {exc}"
            ) from exc

    assert isinstance(result, ChainResult), f"Expected ChainResult, got {type(result)}"
    assert result.degraded is True


@given(target=_target_st, phase=_phase_st, stdout=_invalid_json_stdout_st())
@settings(max_examples=10)
def test_property_14_aegis_available_invalid_json(target, phase, stdout):
    """Property 14 (case 5): aegis available, subprocess returns invalid JSON → degraded or empty results ChainResult.

    **Validates: Requirements 10.3**
    """
    bridge = AegisBridge()
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = stdout
    mock_proc.stderr = b""

    with patch.object(bridge, "is_available", return_value=True), \
         patch("hackempire.tools.external.aegis_bridge.subprocess.run", return_value=mock_proc):
        try:
            result = bridge.run(target, phase)
        except Exception as exc:
            raise AssertionError(
                f"AegisBridge.run() raised {type(exc).__name__}: {exc}"
            ) from exc

    assert isinstance(result, ChainResult), f"Expected ChainResult, got {type(result)}"
    # Either degraded (empty stdout) or non-degraded with empty results (all lines invalid JSON)
    assert result.degraded is True or isinstance(result.results, dict)
