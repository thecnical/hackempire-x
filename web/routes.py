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

EXPORT_MIME_TYPES = {
    "pdf": "application/pdf",
    "json": "application/json",
    "html": "text/html",
    "markdown": "text/markdown",
    "csv": "text/csv",
}

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
    technologies = recon.get("technologies") or []
    cve_findings = recon.get("cve_findings") or []

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
        cve_count=len(cve_findings),
        tech_count=len(technologies),
        high_conf_vulns=high_conf_vulns,
        tool_health=tool_health,
        attack_tree=attack_tree,
        technologies=technologies[:10],
        cve_findings=cve_findings[:10],
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
    recon = data.get("recon", {})
    vuln = data.get("vuln", {})
    vulns = vuln.get("vulnerabilities") or []
    cve_findings = recon.get("cve_findings") or []
    technologies = recon.get("technologies") or []

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

    # Enrich CVE findings with severity label
    enriched_cves = []
    for c in cve_findings:
        if not isinstance(c, dict):
            continue
        score = _safe_float(c.get("cvss_score", 0))
        enriched_cves.append({
            **c,
            "severity_label": c.get("severity") or _severity_label(score / 10.0),
        })

    ai_decisions = {
        phase: (data.get(phase) or {}).get("ai_decision")
        for phase in ("recon", "enum", "vuln")
    }

    from web.pdf_report import weasyprint_available

    return render_template(
        "report.html",
        target=state.get("target", "—"),
        mode=state.get("mode", "—"),
        vulnerabilities=enriched,
        cve_findings=enriched_cves,
        technologies=technologies,
        tool_health=state.get("tool_health") or {},
        ai_decisions={k: v for k, v in ai_decisions.items() if v},
        pdf_available=weasyprint_available(),
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
    """Raw state JSON for debugging, extended with v4 keys for state replay."""
    state = read_state()
    # v4.6: include new panel data with empty defaults for state replay
    state.setdefault("attack_graph", {"nodes": [], "edges": []})
    state.setdefault("mitre_overlay", [])
    state.setdefault("poc_preview", {})
    state.setdefault("autonomous_feed", [])
    state.setdefault("kb_entries", [])
    return jsonify(state)


# ---------------------------------------------------------------------------
# v4.6 Dashboard v2 routes
# ---------------------------------------------------------------------------

@bp.route("/api/attack-graph")
def api_attack_graph() -> Response:
    """Return graph data for the AttackGraph panel.

    Nodes represent discovered hosts/services; edges represent exploit paths.
    Falls back to empty graph when no scan data is available.
    """
    state = read_state()
    # Return pre-built attack_graph if present in state (written by OrchestratorV2)
    graph = state.get("attack_graph")
    if isinstance(graph, dict) and "nodes" in graph and "edges" in graph:
        return jsonify(graph)

    # Build a minimal graph from existing scan state
    data = state.get("data") or {}
    recon = data.get("recon") or {}
    vuln = data.get("vuln") or {}

    nodes: list[dict] = []
    edges: list[dict] = []

    target = state.get("target") or ""
    if target:
        nodes.append({"id": "target", "label": target, "type": "host"})

    for port_info in (recon.get("ports") or [])[:50]:
        if not isinstance(port_info, dict):
            continue
        port = port_info.get("port")
        service = port_info.get("service", "unknown")
        if port is None:
            continue
        node_id = f"svc_{port}"
        nodes.append({"id": node_id, "label": f"{port}/{service}", "type": "service"})
        if target:
            edges.append({"from": "target", "to": node_id, "label": "open"})

    for vuln_item in (vuln.get("vulnerabilities") or [])[:20]:
        if not isinstance(vuln_item, dict):
            continue
        name = vuln_item.get("name") or vuln_item.get("title") or "vuln"
        url = vuln_item.get("url") or ""
        node_id = f"vuln_{name[:30]}"
        nodes.append({"id": node_id, "label": name, "type": "exploit_path"})
        if url:
            edges.append({"from": "target", "to": node_id, "label": "exploitable"})

    return jsonify({"nodes": nodes, "edges": edges})


@bp.route("/api/mitre-overlay")
def api_mitre_overlay() -> Response:
    """Return MITRE ATT&CK overlay data for confirmed findings.

    Each entry has ``finding``, ``technique_id``, and ``tactic`` fields.
    Falls back to empty list when no data is available.
    """
    state = read_state()
    # Return pre-built overlay if present
    overlay = state.get("mitre_overlay")
    if isinstance(overlay, list):
        return jsonify(overlay)

    # Build from scan state using mitre_mapper if available
    data = state.get("data") or {}
    vuln = data.get("vuln") or {}
    vulns = vuln.get("vulnerabilities") or []

    result: list[dict] = []
    try:
        from ai.mitre_mapper import map_finding
        for v in vulns:
            if not isinstance(v, dict):
                continue
            name = v.get("name") or v.get("title") or ""
            mapping = map_finding(name)
            result.append({
                "finding": name,
                "technique_id": mapping.get("technique_id", ""),
                "tactic": mapping.get("tactic", ""),
            })
    except Exception:
        pass

    return jsonify(result)


@bp.route("/api/kb")
def api_kb() -> Response:
    """Return KBEntry records for the current scan target.

    Falls back to empty list when no KB data is available.
    """
    state = read_state()
    # Return pre-built kb_entries if present
    kb_entries = state.get("kb_entries")
    if isinstance(kb_entries, list):
        return jsonify(kb_entries)

    target = state.get("target") or ""
    if not target:
        return jsonify([])

    try:
        from core.kb_manager import KnowledgeBaseManager
        kb = KnowledgeBaseManager()
        entries = kb.search(target)
        return jsonify([e.to_dict() for e in entries])
    except Exception:
        return jsonify([])


@bp.route("/api/autonomous-feed")
def api_autonomous_feed() -> Response:
    """Return recent AutonomousDecision records for the AutonomousFeed panel.

    Falls back to empty list when not in autonomous mode or no decisions recorded.
    """
    state = read_state()
    # Return pre-built autonomous_feed if present
    feed = state.get("autonomous_feed")
    if isinstance(feed, list):
        return jsonify(feed)

    return jsonify([])


@bp.route("/api/report/pdf")
def report_pdf() -> Response:
    """Generate and download a PDF report."""
    from web.pdf_report import generate_pdf, generate_html, weasyprint_available
    state = read_state()

    if weasyprint_available():
        pdf_bytes = generate_pdf(state)
        if pdf_bytes:
            buf = io.BytesIO(pdf_bytes)
            buf.seek(0)
            return send_file(
                buf,
                mimetype="application/pdf",
                as_attachment=True,
                download_name="hackempire_report.pdf",
            )

    # Fallback: serve as HTML if WeasyPrint not installed
    html = generate_html(state)
    return Response(html, mimetype="text/html")


@bp.route("/api/export/<fmt>")
def export_report(fmt: str) -> Response:
    """Export the scan report in the requested format.

    Supported formats: pdf, json, html, markdown, csv.
    Returns HTTP 400 with JSON error body for unknown formats.
    """
    if fmt not in EXPORT_MIME_TYPES:
        return jsonify({"error": f"Unknown format: {fmt}"}), 400

    state = read_state()
    mime = EXPORT_MIME_TYPES[fmt]

    if fmt == "pdf":
        from web.pdf_report import generate_pdf, generate_html, weasyprint_available
        if weasyprint_available():
            pdf_bytes = generate_pdf(state)
            if pdf_bytes:
                buf = io.BytesIO(pdf_bytes)
                buf.seek(0)
                return send_file(buf, mimetype=mime, as_attachment=True,
                                 download_name="hackempire_report.pdf")
        html = generate_html(state)
        return Response(html, mimetype="text/html")

    if fmt == "json":
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
        }
        content = json.dumps(report_data, indent=2, default=str).encode()
        return Response(content, mimetype=mime)

    if fmt == "html":
        from web.pdf_report import generate_html
        html = generate_html(state)
        return Response(html, mimetype=mime)

    if fmt == "markdown":
        from web.exporters.markdown_export import generate_markdown
        content = generate_markdown(state)
        return Response(content, mimetype=mime)

    if fmt == "csv":
        from web.exporters.csv_export import generate_csv
        content = generate_csv(state)
        return Response(content, mimetype=mime)

    # Should never reach here
    return jsonify({"error": f"Unknown format: {fmt}"}), 400
