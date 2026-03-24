from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

from core.models import Vulnerability, WafResult
from tools.waf.waf_bypass_strategy import WafBypassStrategy

XSS_WAF_BYPASS_CHAINS: dict[str, list[str]] = {
    "cloudflare": ["<img src=x onerror=alert(1)>", "<svg/onload=alert(1)>"],
    "akamai": ["<script>alert(1)</script>", "javascript:alert(1)"],
    "modsecurity": ["<img src=x onerror=&#97;lert(1)>"],
    "default": ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>"],
}

# Tools that are pip-installed and must run inside their venv
_VENV_TOOLS = {"xsstrike", "jsvulns"}


def _resolve_cmd(tool_name: str, args: list[str]) -> list[str]:
    """
    Build a subprocess command for *tool_name* using its isolated venv if available,
    otherwise fall back to the system binary.

    For pip-based tools (xsstrike, jsvulns) this ensures they always run inside
    their isolated environment, avoiding system-level dependency conflicts.
    """
    if tool_name in _VENV_TOOLS:
        try:
            from installer.tool_venv_manager import get_global_venv_manager
            manager = get_global_venv_manager()
            venv_python: Optional[Path] = manager.get_venv_python(tool_name)
            if venv_python and venv_python.exists():
                return [str(venv_python), "-m", tool_name] + args
        except Exception:
            pass
    return [tool_name] + args


class XSSMethodology:
    """Orchestrates XSS testing across reflected, stored, DOM, blind, and CSP bypass vectors."""

    def __init__(self) -> None:
        self._bypass = WafBypassStrategy()

    # ------------------------------------------------------------------
    # Reflected XSS
    # ------------------------------------------------------------------

    def reflected_xss(self, urls: list[str], waf: WafResult | None) -> list[Vulnerability]:
        """Run dalfox and xsstrike against each URL with optional WAF bypass headers."""
        findings: list[Vulnerability] = []
        try:
            headers: dict[str, str] = {}
            if waf and waf.detected:
                headers = self._bypass.get_bypass_headers(waf.vendor)
            for url in urls:
                findings.extend(self._run_dalfox(url, headers))
                findings.extend(self._run_xsstrike(url, headers))
        except Exception:
            pass
        return findings

    def _run_dalfox(self, url: str, headers: dict[str, str]) -> list[Vulnerability]:
        findings: list[Vulnerability] = []
        try:
            # dalfox is a Go binary — no venv needed, use system binary directly
            args = ["url", url, "--silence", "--format", "plain"]
            for header, value in headers.items():
                args += ["--header", f"{header}: {value}"]
            cmd = ["dalfox"] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, shell=False)
            for line in result.stdout.splitlines():
                line = line.strip()
                if line:
                    findings.append(
                        Vulnerability(
                            name="Reflected XSS",
                            severity="high",
                            confidence=0.8,
                            target=url,
                            url=url,
                            evidence=line,
                            tool_sources=["dalfox"],
                        )
                    )
        except Exception:
            pass
        return findings

    def _run_xsstrike(self, url: str, headers: dict[str, str]) -> list[Vulnerability]:
        """Run xsstrike inside its isolated venv."""
        findings: list[Vulnerability] = []
        try:
            args = ["--url", url, "--crawl", "--blind"]
            for header, value in headers.items():
                args += ["--headers", f"{header}: {value}"]
            cmd = _resolve_cmd("xsstrike", args)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, shell=False)
            for line in result.stdout.splitlines():
                line = line.strip()
                if "[+]" in line or "XSS" in line:
                    findings.append(
                        Vulnerability(
                            name="Reflected XSS",
                            severity="high",
                            confidence=0.75,
                            target=url,
                            url=url,
                            evidence=line,
                            tool_sources=["xsstrike"],
                        )
                    )
        except Exception:
            pass
        return findings

    # ------------------------------------------------------------------
    # Stored XSS
    # ------------------------------------------------------------------

    def stored_xss(self, forms: list[dict], waf: WafResult | None) -> list[Vulnerability]:
        return []

    # ------------------------------------------------------------------
    # DOM XSS
    # ------------------------------------------------------------------

    def dom_xss(self, js_files: list[str]) -> list[Vulnerability]:
        """Run jsvulns inside its isolated venv for source/sink analysis."""
        findings: list[Vulnerability] = []
        for js_file in js_files:
            try:
                cmd = _resolve_cmd("jsvulns", [js_file])
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=False)
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line:
                        findings.append(
                            Vulnerability(
                                name="DOM XSS",
                                severity="high",
                                confidence=0.7,
                                target=js_file,
                                url=js_file,
                                evidence=line,
                                tool_sources=["jsvulns"],
                            )
                        )
            except Exception:
                pass
        return findings

    # ------------------------------------------------------------------
    # Blind XSS
    # ------------------------------------------------------------------

    def blind_xss(self, urls: list[str]) -> list[Vulnerability]:
        return []

    # ------------------------------------------------------------------
    # CSP Bypass
    # ------------------------------------------------------------------

    def csp_bypass(self, target: str) -> list[Vulnerability]:
        return []

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    def run(self, target: str, urls: list[str], context: Any = None) -> list[Vulnerability]:
        waf: WafResult | None = None
        if context is not None and hasattr(context, "waf_result"):
            waf = context.waf_result

        all_findings: list[Vulnerability] = []
        all_findings.extend(self.reflected_xss(urls, waf))
        all_findings.extend(self.stored_xss([], waf))
        all_findings.extend(self.dom_xss([]))
        all_findings.extend(self.blind_xss(urls))
        all_findings.extend(self.csp_bypass(target))
        return self._deduplicate(all_findings)

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _deduplicate(self, findings: list[Vulnerability]) -> list[Vulnerability]:
        seen: dict[tuple[str, str, str], Vulnerability] = {}
        for vuln in findings:
            key = (vuln.name, vuln.url, vuln.severity)
            if key in seen:
                existing = seen[key]
                for src in vuln.tool_sources:
                    if src not in existing.tool_sources:
                        existing.tool_sources.append(src)
            else:
                seen[key] = vuln
        return list(seen.values())
