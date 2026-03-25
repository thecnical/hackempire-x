"""
Property-based tests for OrchestratorV2.

Property 1: Full Scan Never Raises
  - run_full_scan(target) returns a dict without raising for any valid target
  **Validates: Requirements 1.2, 1.4**
"""

import sys
import os
from unittest.mock import patch

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)
_parent = os.path.dirname(_pkg_root)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.core.orchestrator import OrchestratorV2


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------

class _Config:
    def __init__(self, mode="full", web_enabled=False, ai_key=None):
        self.mode = mode
        self.web_enabled = web_enabled
        self.ai_key = ai_key
        self.target = "example.com"
        self.proxy = None


class _Logger:
    def info(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def success(self, *a, **kw): pass


# ---------------------------------------------------------------------------
# Property 1: Full Scan Never Raises
# **Validates: Requirements 1.2, 1.4**
# ---------------------------------------------------------------------------

_valid_targets = st.one_of(
    st.just("example.com"),
    st.just("192.168.1.1"),
    st.just("sub.domain.org"),
    st.just("test.example.co.uk"),
    st.from_regex(r"[a-z]{3,10}\.[a-z]{2,5}", fullmatch=True),
)

_modes = st.sampled_from(["full", "recon-only", "stealth", "exploit"])


@given(target=_valid_targets, mode=_modes)
@settings(max_examples=30, deadline=None)
def test_full_scan_never_raises(target: str, mode: str) -> None:
    """
    Property 1: Full Scan Never Raises

    For any valid target string and any mode, run_full_scan(target) SHALL
    return a dict without raising an exception.

    Tor is mocked so stealth mode does not attempt systemctl/service calls
    in CI environments where interactive auth is unavailable.

    **Validates: Requirements 1.2, 1.4**
    """
    config = _Config(mode=mode)
    logger = _Logger()

    # Mock TorManager.start so stealth mode doesn't block waiting 30s for Tor
    # and doesn't attempt `service tor start` (requires root/interactive auth in CI)
    with patch("hackempire.core.tor_manager.TorManager.start", return_value=False), \
         patch("hackempire.core.tor_manager.TorManager.stop", return_value=None), \
         patch("hackempire.core.tor_manager.subprocess.run", return_value=None):

        orch = OrchestratorV2(config=config, logger=logger)

        # No PhaseManager injected — phases are skipped, but the method must not raise
        result = orch.run_full_scan(target)

    assert isinstance(result, dict), "run_full_scan must return a dict"
    assert "target" in result, "result must contain 'target'"
    assert "phase_results" in result, "result must contain 'phase_results'"
    assert "waf_result" in result, "result must contain 'waf_result'"
    assert "ai_decisions" in result, "result must contain 'ai_decisions'"
    assert "todo_list" in result, "result must contain 'todo_list'"
