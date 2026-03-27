"""
Property-based tests for ToolKnowledge registry (v4.5).

Property 12: Every registered tool has a complete ToolKnowledge entry
  - For any tool name in TOOL_KNOWLEDGE, the entry SHALL have non-empty values
    for all six required fields: when_to_use, what_to_look_for, success_indicator,
    failure_action, next_tool (or None), and next_phase_trigger.
  **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**
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

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.ai.tool_knowledge import TOOL_KNOWLEDGE, ToolKnowledge

# ---------------------------------------------------------------------------
# Property 12: Every registered tool has a complete ToolKnowledge entry
# ---------------------------------------------------------------------------

# Feature: hackempire-x-v4, Property 12: Every registered tool has a complete ToolKnowledge entry
@given(st.sampled_from(list(TOOL_KNOWLEDGE.keys())))
@settings(max_examples=100)
def test_property_12_tool_knowledge_completeness(tool_name: str) -> None:
    """Property 12: Every registered tool has a complete ToolKnowledge entry.

    For any tool name present in TOOL_KNOWLEDGE, the entry SHALL exist and
    SHALL have non-empty values for all six required fields: when_to_use,
    what_to_look_for, success_indicator, failure_action, next_tool (or None),
    and next_phase_trigger.

    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**
    """
    assert tool_name in TOOL_KNOWLEDGE, (
        f"Tool '{tool_name}' is missing from TOOL_KNOWLEDGE"
    )

    entry: ToolKnowledge = TOOL_KNOWLEDGE[tool_name]

    # when_to_use must be a non-empty string (Req 5.2)
    assert isinstance(entry.when_to_use, str) and entry.when_to_use.strip(), (
        f"Tool '{tool_name}': when_to_use must be a non-empty string"
    )

    # what_to_look_for must be a non-empty string (Req 5.3)
    assert isinstance(entry.what_to_look_for, str) and entry.what_to_look_for.strip(), (
        f"Tool '{tool_name}': what_to_look_for must be a non-empty string"
    )

    # success_indicator must be a non-empty string (Req 5.4)
    assert isinstance(entry.success_indicator, str) and entry.success_indicator.strip(), (
        f"Tool '{tool_name}': success_indicator must be a non-empty string"
    )

    # failure_action must be one of the three valid values (Req 5.5)
    valid_failure_actions = {"try_next_tool", "skip_phase", "escalate_to_ai"}
    assert entry.failure_action in valid_failure_actions, (
        f"Tool '{tool_name}': failure_action={entry.failure_action!r} must be one of "
        f"{valid_failure_actions}"
    )

    # next_tool must be None or a non-empty string (Req 5.6)
    assert entry.next_tool is None or (
        isinstance(entry.next_tool, str) and entry.next_tool.strip()
    ), (
        f"Tool '{tool_name}': next_tool must be None or a non-empty string, "
        f"got {entry.next_tool!r}"
    )

    # next_phase_trigger must be a non-empty string (Req 5.7)
    assert isinstance(entry.next_phase_trigger, str) and entry.next_phase_trigger.strip(), (
        f"Tool '{tool_name}': next_phase_trigger must be a non-empty string"
    )


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_tool_knowledge_dict_is_not_empty() -> None:
    """TOOL_KNOWLEDGE must contain at least one entry."""
    assert len(TOOL_KNOWLEDGE) > 0, "TOOL_KNOWLEDGE must not be empty"


def test_tool_knowledge_all_keys_are_strings() -> None:
    """All keys in TOOL_KNOWLEDGE must be non-empty strings."""
    for key in TOOL_KNOWLEDGE:
        assert isinstance(key, str) and key.strip(), (
            f"TOOL_KNOWLEDGE key {key!r} must be a non-empty string"
        )


def test_tool_knowledge_all_entries_are_tool_knowledge_instances() -> None:
    """All values in TOOL_KNOWLEDGE must be ToolKnowledge instances."""
    for tool_name, entry in TOOL_KNOWLEDGE.items():
        assert isinstance(entry, ToolKnowledge), (
            f"TOOL_KNOWLEDGE[{tool_name!r}] must be a ToolKnowledge instance, "
            f"got {type(entry)}"
        )


def test_tool_knowledge_registry_tool_names_present() -> None:
    """All tools registered in ToolManager.TOOL_REGISTRY must have TOOL_KNOWLEDGE entries."""
    from hackempire.tools.tool_manager import ToolManager

    # Collect all unique tool names from TOOL_REGISTRY
    registry_tool_names: set[str] = set()
    for tool_classes in ToolManager.TOOL_REGISTRY.values():
        for cls in tool_classes:
            registry_tool_names.add(cls.name)

    missing = registry_tool_names - set(TOOL_KNOWLEDGE.keys())
    assert not missing, (
        f"The following tools are in TOOL_REGISTRY but missing from TOOL_KNOWLEDGE: "
        f"{sorted(missing)}"
    )
