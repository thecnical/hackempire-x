"""
Property-based tests for PhaseManager pipeline order.

# Feature: hackempire-x-v4, Property 15: 7-phase pipeline order is preserved

For any scan invocation, the phases executed by PhaseManager SHALL always be in the order
RECON → URL_DISCOVERY → ENUMERATION → VULN_SCAN → EXPLOITATION → POST_EXPLOIT → REPORTING,
regardless of mode or autonomous flag.

**Validates: Requirements 7.4**
"""
from __future__ import annotations

import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)
_parent = os.path.dirname(_pkg_root)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.core.phase_manager import PhaseManager
from hackempire.core.phases import Phase

# ---------------------------------------------------------------------------
# Expected phase order (canonical)
# ---------------------------------------------------------------------------

EXPECTED_PHASE_ORDER = [
    Phase.RECON,
    Phase.URL_DISCOVERY,
    Phase.ENUMERATION,
    Phase.VULN_SCAN,
    Phase.EXPLOITATION,
    Phase.POST_EXPLOIT,
    Phase.REPORTING,
]


# ---------------------------------------------------------------------------
# Property 15: 7-phase pipeline order is preserved
# ---------------------------------------------------------------------------

# Feature: hackempire-x-v4, Property 15: 7-phase pipeline order is preserved
@given(st.text())
@settings(max_examples=10)
def test_property15_phase_order_preserved(target: str) -> None:
    """For any target string, PhaseManager.PHASES SHALL be in the canonical 7-phase order.

    **Validates: Requirements 7.4**
    """
    # The PHASES class attribute defines the execution order — it must always
    # match the canonical pipeline regardless of target or mode.
    assert PhaseManager.PHASES == EXPECTED_PHASE_ORDER, (
        f"Phase order mismatch.\n"
        f"Expected: {[p.value for p in EXPECTED_PHASE_ORDER]}\n"
        f"Got:      {[p.value for p in PhaseManager.PHASES]}"
    )


def test_phase_order_exact_values() -> None:
    """Verify the exact phase values in order as a deterministic unit test."""
    phase_values = [p.value for p in PhaseManager.PHASES]
    assert phase_values == [
        "recon",
        "url_discovery",
        "enumeration",
        "vuln_scan",
        "exploitation",
        "post_exploit",
        "reporting",
    ]


def test_phase_count() -> None:
    """PhaseManager.PHASES must contain exactly 7 phases."""
    assert len(PhaseManager.PHASES) == 7


def test_no_duplicate_phases() -> None:
    """Each phase must appear exactly once in the pipeline."""
    assert len(PhaseManager.PHASES) == len(set(PhaseManager.PHASES))
