from __future__ import annotations

from core.config import Config
from core.state_manager import StateManager


class ContextManager:
    """
    Builds JSON-ready context for AI consumption.

    Enriched context includes:
    - per-phase findings (ports, subdomains, urls, vulnerabilities with confidence + sources)
    - global tool_health map so AI can reason about data reliability
    - summary statistics for quick AI triage
    """

    def __init__(self, config: Config, state_manager: StateManager) -> None:
        self._config = config
        self._state = state_manager

    def build_context(self) -> dict[str, object]:
        all_data = self._state.get_all()
        tool_health = self._state.get_tool_health()

        return {
            "target": self._config.target,
            "mode": self._config.mode,
            "current_phase": self._state.current_phase or "",
            "data": all_data,
            "tool_health": tool_health,
            "summary": self._build_summary(all_data),
        }

    def _build_summary(self, all_data: dict) -> dict[str, object]:
        """
        Compact summary of findings across all phases for quick AI triage.
        Includes confidence stats for vulnerabilities.
        """
        recon = all_data.get("recon", {})
        enum = all_data.get("enum", {})
        vuln = all_data.get("vuln", {})

        vulns: list[dict] = vuln.get("vulnerabilities", []) or []
        high_conf_vulns = [
            v for v in vulns
            if isinstance(v, dict) and _safe_float(v.get("confidence", 0)) >= 0.8
        ]
        multi_source_vulns = [
            v for v in vulns
            if isinstance(v, dict) and len(v.get("sources", [])) > 1
        ]

        return {
            "open_ports_count": len(recon.get("ports", []) or []),
            "subdomains_count": len(recon.get("subdomains", []) or []),
            "urls_count": len(enum.get("urls", []) or []),
            "vulnerabilities_count": len(vulns),
            "high_confidence_vulns": len(high_conf_vulns),
            "multi_source_vulns": len(multi_source_vulns),
        }


def _safe_float(value: object, default: float = 0.0) -> float:
    """Convert value to float safely, returning default on failure."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default

