"""
Confidence scoring engine for HackEmpire X.

Rules:
- Each tool has a base confidence score.
- High-reliability tools (nuclei) get a higher base.
- When the same vulnerability appears from multiple tools, confidence increases.
- Final confidence is capped at 1.0.
"""
from __future__ import annotations

from typing import Any

# Base confidence per tool name (lowercase).
_TOOL_BASE_CONFIDENCE: dict[str, float] = {
    "nuclei": 0.85,
    "nmap": 0.75,
    "subfinder": 0.65,
    "ffuf": 0.60,
    "dirsearch": 0.60,
}

# Confidence boost when a second (or more) tool corroborates the same finding.
_CORROBORATION_BOOST: float = 0.10

# Default base confidence for unknown tools.
_DEFAULT_BASE_CONFIDENCE: float = 0.55


def base_confidence(tool_name: str) -> float:
    """Return the base confidence score for a given tool."""
    return _TOOL_BASE_CONFIDENCE.get((tool_name or "").lower(), _DEFAULT_BASE_CONFIDENCE)


def merge_vulnerability(
    existing: dict[str, Any],
    new_tool: str,
    new_item: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge a new vulnerability report into an existing record.

    If the tool is new (not already in sources), boost confidence.
    Returns the updated record (mutates in place and returns it).
    """
    sources: list[str] = existing.get("sources", [])
    if new_tool not in sources:
        sources.append(new_tool)
        existing["sources"] = sources
        existing["confidence"] = min(1.0, float(existing.get("confidence", 0.0)) + _CORROBORATION_BOOST)

    # Preserve additional evidence fields if not already present.
    for evidence_field in ("url", "severity", "description"):
        if evidence_field in new_item and evidence_field not in existing:
            existing[evidence_field] = new_item[evidence_field]

    return existing


def build_vulnerability_record(
    tool_name: str,
    name: str,
    target: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a new vulnerability record with initial confidence from the tool.
    """
    record: dict[str, Any] = {
        "name": name,
        "target": target,
        "confidence": base_confidence(tool_name),
        "sources": [tool_name],
    }
    for evidence_field in ("url", "severity", "description"):
        if evidence_field in item:
            record[evidence_field] = item[evidence_field]
    return record
