"""
PDF Report Generator for HackEmpire X.

Uses WeasyPrint to render a styled HTML report to PDF.
Falls back gracefully if WeasyPrint is not installed.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any

try:
    from weasyprint import HTML as _WP_HTML
    _WEASYPRINT_AVAILABLE = True
except ImportError:
    _WEASYPRINT_AVAILABLE = False


def _severity_label(confidence: float) -> str:
    if confidence >= 0.85:
        return "critical"
    if confidence >= 0.70:
        return "high"
    if confidence >= 0.55:
        return "medium"
    return "low"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


_SEVERITY_COLORS = {
    "critical": "#da3633",
    "high": "#d29922",
    "medium": "#388bfd",
    "low": "#3fb950",
}


def _build_html(state: dict[str, Any]) -> str:
    """Render the full report as an HTML string."""
    target = state.get("target") or "—"
    mode = state.get("mode") or "—"
    tool_health = state.get("tool_health") or {}
    data = state.get("data") or {}
    recon = data.get("recon") or {}
    enum_data = data.get("enum") or {}
    vuln_data = data.get("vuln") or {}

    ports = recon.get("ports") or []
    subdomains = recon.get("subdomains") or []
    technologies = recon.get("technologies") or []
    cve_findings = recon.get("cve_findings") or []
    urls = enum_data.get("urls") or []
    vulns = vuln_data.get("vulnerabilities") or []

    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Build vulnerability rows
    vuln_rows = ""
    for i, v in enumerate(sorted(vulns, key=lambda x: _safe_float(x.get("confidence", 0)), reverse=True), 1):
        conf = _safe_float(v.get("confidence", 0))
        sev = _severity_label(conf)
        color = _SEVERITY_COLORS.get(sev, "#888")
        name = str(v.get("name") or v.get("title") or "—")
        tgt = str(v.get("target") or "—")
        sources = ", ".join(v.get("sources") or [])
        vuln_rows += f"""
        <tr>
          <td>{i}</td>
          <td>{name}</td>
          <td><span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">{sev}</span></td>
          <td>{conf * 100:.0f}%</td>
          <td>{tgt}</td>
          <td>{sources}</td>
        </tr>"""

    # CVE rows
    cve_rows = ""
    for c in cve_findings:
        score = _safe_float(c.get("cvss_score", 0))
        sev = c.get("severity") or _severity_label(score)
        color = _SEVERITY_COLORS.get(sev, "#888")
        refs = " ".join(f'<a href="{r}" style="color:#58a6ff;">[ref]</a>' for r in (c.get("references") or []))
        cve_rows += f"""
        <tr>
          <td><strong>{c.get("cve_id","—")}</strong></td>
          <td>{c.get("service","—")} / port {c.get("port","—")}</td>
          <td><span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">{sev}</span></td>
          <td>{score}</td>
          <td style="font-size:11px;">{(c.get("description") or "")[:200]}</td>
          <td>{refs}</td>
        </tr>"""

    # Tech rows
    tech_rows = ""
    for t in technologies:
        tech_rows += f"<tr><td>{t.get('name','—')}</td><td>{t.get('version','—')}</td><td>{t.get('detail','—')}</td></tr>"

    # Tool health rows
    health_rows = ""
    for tool, status in tool_health.items():
        color = "#3fb950" if status == "ok" else "#da3633" if status in ("failed", "not_installed") else "#888"
        health_rows += f'<tr><td>{tool}</td><td style="color:{color};font-weight:bold;">{status}</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>HackEmpire X — Scan Report</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #fff; color: #1a1a2e; margin: 0; padding: 0; }}
  .cover {{ background: #0d1117; color: #fff; padding: 60px 40px; }}
  .cover h1 {{ font-size: 2.4rem; color: #58a6ff; margin: 0 0 8px; }}
  .cover .sub {{ color: #8b949e; font-size: 1rem; }}
  .cover .meta {{ margin-top: 24px; font-size: 0.9rem; color: #c9d1d9; }}
  .cover .meta span {{ margin-right: 24px; }}
  section {{ padding: 32px 40px; border-bottom: 1px solid #e0e0e0; }}
  h2 {{ color: #0d1117; font-size: 1.2rem; border-left: 4px solid #58a6ff; padding-left: 10px; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #f0f4f8; text-align: left; padding: 8px 10px; font-size: 11px; text-transform: uppercase; color: #555; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }}
  tr:hover td {{ background: #f9f9f9; }}
  .footer {{ background: #0d1117; color: #8b949e; text-align: center; padding: 20px; font-size: 12px; }}
  .stat-grid {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; }}
  .stat {{ background: #f0f4f8; border-radius: 8px; padding: 16px 24px; text-align: center; min-width: 100px; }}
  .stat .num {{ font-size: 2rem; font-weight: bold; color: #58a6ff; }}
  .stat .lbl {{ font-size: 11px; color: #555; text-transform: uppercase; }}
</style>
</head>
<body>

<div class="cover">
  <h1>HackEmpire X</h1>
  <div class="sub">AI-Orchestrated Pentesting Report</div>
  <div class="meta">
    <span>Target: <strong>{target}</strong></span>
    <span>Mode: <strong>{mode.upper()}</strong></span>
    <span>Generated: <strong>{generated}</strong></span>
  </div>
</div>

<section>
  <h2>Executive Summary</h2>
  <div class="stat-grid">
    <div class="stat"><div class="num">{len(ports)}</div><div class="lbl">Open Ports</div></div>
    <div class="stat"><div class="num">{len(subdomains)}</div><div class="lbl">Subdomains</div></div>
    <div class="stat"><div class="num">{len(urls)}</div><div class="lbl">URLs</div></div>
    <div class="stat"><div class="num">{len(vulns)}</div><div class="lbl">Vulnerabilities</div></div>
    <div class="stat"><div class="num">{len(cve_findings)}</div><div class="lbl">CVEs Found</div></div>
    <div class="stat"><div class="num">{len(technologies)}</div><div class="lbl">Technologies</div></div>
  </div>
</section>

<section>
  <h2>Technology Fingerprint</h2>
  {"<table><thead><tr><th>Technology</th><th>Version</th><th>Detail</th></tr></thead><tbody>" + tech_rows + "</tbody></table>" if tech_rows else "<p style='color:#888;'>No technology data collected.</p>"}
</section>

<section>
  <h2>Open Ports</h2>
  {"<table><thead><tr><th>Port</th><th>Service</th><th>State</th></tr></thead><tbody>" + "".join(f"<tr><td>{p.get('port','—')}</td><td>{p.get('service','—')}</td><td>{p.get('state','open')}</td></tr>" for p in ports if isinstance(p, dict)) + "</tbody></table>" if ports else "<p style='color:#888;'>No open ports found.</p>"}
</section>

<section>
  <h2>CVE Correlation</h2>
  {"<table><thead><tr><th>CVE ID</th><th>Service / Port</th><th>Severity</th><th>CVSS</th><th>Description</th><th>References</th></tr></thead><tbody>" + cve_rows + "</tbody></table>" if cve_rows else "<p style='color:#888;'>No CVEs correlated.</p>"}
</section>

<section>
  <h2>Vulnerabilities</h2>
  {"<table><thead><tr><th>#</th><th>Name</th><th>Severity</th><th>Confidence</th><th>Target</th><th>Sources</th></tr></thead><tbody>" + vuln_rows + "</tbody></table>" if vuln_rows else "<p style='color:#888;'>No vulnerabilities recorded.</p>"}
</section>

<section>
  <h2>Subdomains ({len(subdomains)})</h2>
  {"<p>" + ", ".join(subdomains[:50]) + ("..." if len(subdomains) > 50 else "") + "</p>" if subdomains else "<p style='color:#888;'>None found.</p>"}
</section>

<section>
  <h2>Tool Health</h2>
  {"<table><thead><tr><th>Tool</th><th>Status</th></tr></thead><tbody>" + health_rows + "</tbody></table>" if health_rows else "<p style='color:#888;'>No tool data.</p>"}
</section>

<div class="footer">
  HackEmpire X — Made by Chandan Pandey &nbsp;|&nbsp; For authorized use only
</div>
</body>
</html>"""


def generate_pdf(state: dict[str, Any]) -> bytes | None:
    """
    Generate a PDF report from scan state.

    Returns:
        bytes: PDF content, or None if WeasyPrint is not available.
    """
    if not _WEASYPRINT_AVAILABLE:
        return None

    html_content = _build_html(state)
    buf = io.BytesIO()
    _WP_HTML(string=html_content).write_pdf(buf)
    buf.seek(0)
    return buf.read()


def generate_html(state: dict[str, Any]) -> str:
    """Return the report as an HTML string (always available, no WeasyPrint needed)."""
    return _build_html(state)


def weasyprint_available() -> bool:
    return _WEASYPRINT_AVAILABLE
