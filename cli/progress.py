"""
HackEmpire X — Rich progress rendering helpers for CLI.
"""
from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Hacker theme style constants
# ---------------------------------------------------------------------------

HACKER_THEME: dict[str, str] = {
    "background": "on black",
    "primary": "bold green",
    "secondary": "dim green",
    "accent": "bold cyan",
    "warning": "bold yellow",
    "error": "bold red",
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "green",
    "info": "dim white",
    "border": "green",
    "panel_title": "bold green on black",
    "bar_complete": "green",
    "bar_incomplete": "dim green",
}

_SEVERITY_STYLES: dict[str, str] = {
    "critical": HACKER_THEME["critical"],
    "high": HACKER_THEME["high"],
    "medium": HACKER_THEME["medium"],
    "low": HACKER_THEME["low"],
}


# ---------------------------------------------------------------------------
# render_phase_progress
# ---------------------------------------------------------------------------

def render_phase_progress(console: Console, phase_statuses: dict[str, str]) -> None:
    """
    Print a Rich table showing each phase with a progress bar.

    phase_statuses: mapping of phase_name -> status string
      e.g. {"recon": "complete", "enum": "running", "vuln": "pending"}

    Status values:
      "complete" / "done"  → 100% bar, green
      "running"            → 50% bar, yellow (in-progress indicator)
      "error" / "failed"   → 100% bar, red
      anything else        → 0% bar, dim
    """
    table = Table(
        title="[bold green]Phase Progress[/bold green]",
        border_style=HACKER_THEME["border"],
        show_lines=True,
        expand=False,
    )
    table.add_column("Phase", style=HACKER_THEME["accent"], min_width=20)
    table.add_column("Status", justify="center", min_width=10)
    table.add_column("Progress", min_width=30)

    for phase_name, status in phase_statuses.items():
        status_lower = status.lower()

        if status_lower in ("complete", "done", "success"):
            pct = 100
            bar_style = HACKER_THEME["bar_complete"]
            status_text = Text("DONE", style=HACKER_THEME["primary"])
        elif status_lower in ("running", "in_progress", "active"):
            pct = 50
            bar_style = HACKER_THEME["warning"]
            status_text = Text("RUNNING", style=HACKER_THEME["warning"])
        elif status_lower in ("error", "failed", "fail"):
            pct = 100
            bar_style = HACKER_THEME["error"]
            status_text = Text("ERROR", style=HACKER_THEME["error"])
        else:
            pct = 0
            bar_style = HACKER_THEME["secondary"]
            status_text = Text("PENDING", style=HACKER_THEME["info"])

        # Build a simple ASCII progress bar
        bar_width = 28
        filled = int(bar_width * pct / 100)
        bar_str = "█" * filled + "░" * (bar_width - filled)
        bar_text = Text(f"[{bar_str}] {pct:3d}%", style=bar_style)

        table.add_row(phase_name, status_text, bar_text)

    console.print(table)


# ---------------------------------------------------------------------------
# render_finding
# ---------------------------------------------------------------------------

def render_finding(console: Console, vuln: dict[str, Any]) -> None:
    """
    Print a Rich panel with finding details, severity-colored border.

    Expected vuln keys (all optional):
      name / title, severity, confidence, url, target, evidence,
      cve_ids, cwe_ids, remediation, tool_sources
    """
    name = str(vuln.get("name") or vuln.get("title") or "Unknown Finding")
    severity = str(vuln.get("severity") or "low").lower()
    confidence = vuln.get("confidence")
    url = vuln.get("url") or vuln.get("target") or ""
    evidence = vuln.get("evidence") or ""
    cve_ids = vuln.get("cve_ids") or []
    cwe_ids = vuln.get("cwe_ids") or []
    remediation = vuln.get("remediation") or ""
    tool_sources = vuln.get("tool_sources") or []

    border_style = _SEVERITY_STYLES.get(severity, HACKER_THEME["info"])

    lines: list[str] = []
    lines.append(f"[{HACKER_THEME['accent']}]Severity:[/{HACKER_THEME['accent']}] "
                 f"[{border_style}]{severity.upper()}[/{border_style}]")

    if confidence is not None:
        try:
            conf_pct = int(float(confidence) * 100)
        except (TypeError, ValueError):
            conf_pct = 0
        lines.append(f"[{HACKER_THEME['accent']}]Confidence:[/{HACKER_THEME['accent']}] {conf_pct}%")

    if url:
        lines.append(f"[{HACKER_THEME['accent']}]URL:[/{HACKER_THEME['accent']}] [dim]{url}[/dim]")

    if evidence:
        lines.append(f"[{HACKER_THEME['accent']}]Evidence:[/{HACKER_THEME['accent']}] {evidence[:200]}")

    if cve_ids:
        lines.append(f"[{HACKER_THEME['accent']}]CVEs:[/{HACKER_THEME['accent']}] {', '.join(str(c) for c in cve_ids)}")

    if cwe_ids:
        lines.append(f"[{HACKER_THEME['accent']}]CWEs:[/{HACKER_THEME['accent']}] {', '.join(str(c) for c in cwe_ids)}")

    if tool_sources:
        lines.append(f"[{HACKER_THEME['accent']}]Tools:[/{HACKER_THEME['accent']}] {', '.join(str(t) for t in tool_sources)}")

    if remediation:
        lines.append(f"[{HACKER_THEME['accent']}]Remediation:[/{HACKER_THEME['accent']}] [dim]{remediation[:300]}[/dim]")

    body = "\n".join(lines)

    console.print(
        Panel(
            body,
            title=f"[{border_style}]{name}[/{border_style}]",
            border_style=border_style,
            expand=False,
        )
    )
