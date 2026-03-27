"""
Property-based tests for TorManager.

Property 13: TorManager wrap_command Does Not Mutate Input
  - original list unchanged after wrap_command
  **Validates: Requirements 9.5**
"""

import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)       # hackempire/
_parent = os.path.dirname(_pkg_root)     # repo root (contains hackempire/)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.core.tor_manager import TorManager


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_cmd_st = st.lists(
    st.text(min_size=1, max_size=40).filter(lambda s: "\x00" not in s),
    min_size=0,
    max_size=10,
)


# ---------------------------------------------------------------------------
# Property 13: wrap_command Does Not Mutate Input
# ---------------------------------------------------------------------------

@given(cmd=_cmd_st)
@settings(max_examples=20)
def test_property_13_wrap_command_does_not_mutate_input(cmd):
    """Property 13: TorManager wrap_command Does Not Mutate Input — original
    list unchanged after wrap_command.

    **Validates: Requirements 9.5**
    """
    manager = TorManager()
    original_copy = list(cmd)

    result = manager.wrap_command(cmd)

    # Original list must be unchanged
    assert cmd == original_copy, (
        f"wrap_command mutated the input: before={original_copy!r}, after={cmd!r}"
    )

    # Result must start with the proxychains4 prefix
    assert result[:2] == ["proxychains4", "-q"], (
        f"Expected result to start with ['proxychains4', '-q'], got {result[:2]!r}"
    )

    # Result must contain all original elements after the prefix
    assert result[2:] == original_copy, (
        f"Expected result[2:] == original cmd, got {result[2:]!r}"
    )

    # Result must be a new list object (not the same reference)
    assert result is not cmd, "wrap_command returned the same list object as input"


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_wrap_command_empty_list():
    """wrap_command with empty list returns ['proxychains4', '-q']."""
    manager = TorManager()
    assert manager.wrap_command([]) == ["proxychains4", "-q"]


def test_wrap_command_single_element():
    """wrap_command with single element returns ['proxychains4', '-q', element]."""
    manager = TorManager()
    assert manager.wrap_command(["nmap"]) == ["proxychains4", "-q", "nmap"]


def test_wrap_command_result_length():
    """wrap_command result length equals len(cmd) + 2."""
    manager = TorManager()
    cmd = ["nmap", "-sV", "10.0.0.1"]
    result = manager.wrap_command(cmd)
    assert len(result) == len(cmd) + 2
