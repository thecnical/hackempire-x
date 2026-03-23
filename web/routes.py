"""
Flask route handlers for HackEmpire X Web GUI.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, render_template, jsonify, send_file
import io

from web.state_bridge import read_state

bp = Blueprint("main", __name__)

_LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "hackempire.log"
_LOG_TAIL_LINES = 200


# ---------------------------------------------------------------------------
# Helpers  (defined first so routes can reference them)
# ---------------------------------------------------------------------------

def _tail_log(n: int = _LOG_TAIL_LINES) -> list[str]:
    """Return the last n lines of the log file."""
    if not _LOG_FILE.exists():
        return ["No log file found yet."]
    try:
        lines = _LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-n:] if len(lines) > n else lines
    except OSError:
        return ["Could not read log file."]


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


def _recommendation(vuln: dict[str, Any]) -> str:
    severity = _severity_label(_safe_float(vuln.get("confidence", 0)))
    title = str(vuln.get("name") or vuln.get("title") or "").lower()
    if "xss" in title:
        return "Sanitize and encode all user-supplied output. Implement a Content Security Policy."
    if "sql" in title:
        return "Use parameterized queries / prepared statements. Never interpolate user input into SQL."
    if "rce" in title or "exec" in title:
        return "Restrict command execution. Validate and whitelist all inputs."
    if "lfi" in title or "path" in title:
        return "Validate file paths. Use allowlists and chroot/jail where possible."
    if severity == "critical":
        return "Patch immediately. Restrict access until resolved."
    if severity == "high":
        return "Prioritize remediation in the next sprint."
    if severity == "medium":
        return "Schedule remediation. Apply defense-in-depth controls."
    return "Review and apply vendor security advisories."


def _build_attack_tree(state: dict[str, Any]) -> dict[str, Any]:
    """Build a nested dict representing the attack tree from scan state."""
    data = state.get("data") or {}
    recon = data.get("recon") or {}
    enum = data.get("enum") or {}
    vuln = data.get("vuln") or {}

    ports = recon.get("ports") or []
    subdomains = recon.get("subdomains") or []
    urls = enum.get("urls") or []
    vulns = vuln.get("vulnerabilities") or []

    return {
        "label": state.get("target") or "Target",
        "children": [
            {
                "label": "Recon",
                "children": [
                    {"label": f"Ports ({len(ports)})", "children": [
                        {"label": f"{p.get('port')}/{p.get('service', '?')}", "children": []}
                        for p in ports[:10] if isinstance(p, dict)
                    ]},
                    {"label": f"Subdomains ({len(subdomains)})", "children": [
                        {"label": str(s), "children": []} for s in subdomains[:10]
                    ]},
                ],
            },
            {
                "label": "Enum",
                "children": [
                    {"label": f"URLs ({len(urls)})", "children": [
                        {"label": str(u), "children": []} for u in urls[:10]
                    ]},
                ],
            },
            {
                "label": "Vuln",
                "children": [
                    {
                        "label": (
                            f"[{_severity_label(_safe_float(v.get('confidence', 0)))}] "
                            f"{v.get('name') or v.get('title') or 'unknown'}"
                        ),
                        "children": [],
                    }
                    for v in vulns[:20] if isinstance(v, dict)
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route("/")
@bp.route("/dashboard")
def dashboard() -> str:
    state = read_state()
    data = state.get("data", {})
    recon = data.get("recon", {})
    enum = data.get("enum", {})
    vuln = data.get("vuln", {})

    ports = recon.get("ports") or []
    subdomains = recon.get("subdomains") or []
    urls = enum.get("urls") or []
    vulns = vuln.get("vulnerabilities") or []

    high_conf_vulns = [
        v for v in vulns
        if isinstance(v, dict) and _safe_float(v.get("confidence", 0)) >= 0.70
    ]

    tool_health = state.get("tool_health") or {}
    attack_tree = _build_attack_tree(state)

    return render_template(
        "dashboard.html",
        target=state.get("target", "—"),
        mode=state.get("mode", "—"),
        current_phase=state.get("current_phase", "—"),
        ports_count=len(ports),
        subdomains_count=len(subdomains),
        urls_count=len(urls),
        vulns_count=len(vulns),
        high_conf_vulns=high_conf_vulns,
        tool_health=tool_health,
        attack_tree=attack_tree,
    )


@bp.route("/logs")
def logs() -> str:
    lines = _tail_log()
    return render_template("logs.html", log_lines=lines)


@bp.route("/api/logs")
def api_logs() -> Response:
    """JSON endpoint for auto-refresh polling."""
    return jsonify({"lines": _tail_log(100)})


@bp.route("/report")
def report() -> str:
    state = read_state()
    data = state.get("data", {})
    vuln = data.get("vuln", {})
    vulns = vuln.get("vulnerabilities") or []

    enriched = []
    for v in vulns:
        if not isinstance(v, dict):
            continue
        conf = _safe_float(v.get("confidence", 0))
        enriched.append({
            **v,
            "severity_label": _severity_label(conf),
            "recommendation": _recommendation(v),
        })
    enriched.sort(key=lambda x: _safe_float(x.get("confidence", 0)), reverse=True)

    ai_decisions = {
        phase: (data.get(phase) or {}).get("ai_decision")
        for phase in ("recon", "enum", "vuln")
    }

    return render_template(
        "report.html",
        target=state.get("target", "—"),
        mode=state.get("mode", "—"),
        vulnerabilities=enriched,
        tool_health=state.get("tool_health") or {},
        ai_decisions={k: v for k, v in ai_decisions.items() if v},
    )


@bp.route("/api/report/json")
def report_json() -> Response:
    """Download full scan state as JSON."""
    state = read_state()
    data = state.get("data", {})
    vuln = data.get("vuln", {})
    vulns = vuln.get("vulnerabilities") or []

    report_data = {
        "target": state.get("target"),
        "mode": state.get("mode"),
        "tool_health": state.get("tool_health"),
        "findings": {
            "ports": (data.get("recon") or {}).get("ports") or [],
            "subdomains": (data.get("recon") or {}).get("subdomains") or [],
            "urls": (data.get("enum") or {}).get("urls") or [],
            "vulnerabilities": [
                {**v, "severity": _severity_label(_safe_float(v.get("confidence", 0)))}
                for v in vulns if isinstance(v, dict)
            ],
        },
        "ai_decisions": {
            phase: (data.get(phase) or {}).get("ai_decision")
            for phase in ("recon", "enum", "vuln")
        },
    }
    buf = io.BytesIO(json.dumps(report_data, indent=2, default=str).encode())
    buf.seek(0)
    return send_file(buf, mimetype="application/json", as_attachment=True, download_name="hackempire_report.json")


@bp.route("/api/state")
def api_state() -> Response:
    """Raw state JSON for debugging."""
    return jsonify(read_state())
