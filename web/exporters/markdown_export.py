"""Markdown report exporter for HackEmpire X."""
from __future__ import annotations

from typing import Any

from utils.validator import sanitize_for_html as _escape_md


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _severity_label(confidence: float) -> str:
    if confidence >= 0.85:
        return "critical"
    if confidence >= 0.70:
        return "high"
    if confidence >= 0.55:
        return "medium"
    return "low"


def generate_markdown(state: dict[str, Any]) -> str:
    """Return a Markdown string report from scan state."""
    target = _escape_md(state.get("target") or "—")
    mode = _escape_md(state.get("mode") or "—")
    tool_health = state.get("tool_health") or {}
    data = state.get("data") or {}
    recon = data.get("recon") or {}
    vuln_data = data.get("vuln") or {}
    vulns = vuln_data.get("vulnerabilities") or []

    lines: list[str] = []
    lines.append(f"# HackEmpire X — Scan Report")
    lines.append(f"")
    lines.append(f"**Target:** {target}  ")
    lines.append(f"**Mode:** {mode}  ")
    lines.append(f"")

    # Findings table
    lines.append("## Findings")
    lines.append("")
    lines.append("| # | Name | Severity | Confidence | URL | Evidence | Tool Sources |")
    lines.append("|---|------|----------|------------|-----|----------|--------------|")
    for i, v in enumerate(
        sorted(vulns, key=lambda x: _safe_float(x.get("confidence", 0)), reverse=True), 1
    ):
        if not isinstance(v, dict):
            continue
        conf = _safe_float(v.get("confidence", 0))
        sev = _severity_label(conf)
        name = _escape_md(str(v.get("name") or v.get("title") or "—")).replace("|", "\\|")
        url = _escape_md(str(v.get("target") or v.get("url") or "—")).replace("|", "\\|")
        evidence = _escape_md(str(v.get("evidence") or "—")).replace("|", "\\|")
        sources = _escape_md(", ".join(v.get("sources") or [])).replace("|", "\\|")
        lines.append(f"| {i} | {name} | {sev} | {conf * 100:.0f}% | {url} | {evidence} | {sources} |")

    lines.append("")

    # Tool health
    lines.append("## Tool Health")
    lines.append("")
    lines.append("| Tool | Status |")
    lines.append("|------|--------|")
    for tool, status in tool_health.items():
        lines.append(f"| {_escape_md(str(tool)).replace('|', chr(92)+'|')} | {_escape_md(str(status)).replace('|', chr(92)+'|')} |")

    lines.append("")
    return "\n".join(lines)
