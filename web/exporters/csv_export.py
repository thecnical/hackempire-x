"""CSV report exporter for HackEmpire X."""
from __future__ import annotations

import csv
import io
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def generate_csv(state: dict[str, Any]) -> str:
    """Return a CSV string with vulnerability findings from scan state.

    Columns: name, severity, confidence, url, evidence, tool_sources
    """
    data = state.get("data") or {}
    vuln_data = data.get("vuln") or {}
    vulns = vuln_data.get("vulnerabilities") or []

    buf = io.StringIO()
    writer = csv.writer(buf)
    # The csv module handles all necessary escaping (quoting, commas, newlines) automatically.
    # No additional sanitization is required here.
    writer.writerow(["name", "severity", "confidence", "url", "evidence", "tool_sources"])

    for v in vulns:
        if not isinstance(v, dict):
            continue
        conf = _safe_float(v.get("confidence", 0))
        if conf >= 0.85:
            sev = "critical"
        elif conf >= 0.70:
            sev = "high"
        elif conf >= 0.55:
            sev = "medium"
        else:
            sev = "low"
        writer.writerow([
            v.get("name") or v.get("title") or "",
            sev,
            f"{conf:.2f}",
            v.get("target") or v.get("url") or "",
            v.get("evidence") or "",
            ", ".join(v.get("sources") or []),
        ])

    return buf.getvalue()
