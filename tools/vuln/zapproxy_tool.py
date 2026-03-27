from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class ZAPProxyTool(BaseTool):
    name = "zaproxy"
    phase = "vuln_scan"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)
        self._web_scheme = web_scheme

    def check_installed(self) -> bool:
        return shutil.which("zaproxy") is not None or shutil.which("zap.sh") is not None

    def build_command(self, target: str) -> list[str]:
        binary = "zaproxy" if shutil.which("zaproxy") else "zap.sh"
        url = target if target.startswith("http") else f"{self._web_scheme}://{target}"
        return [binary, "-cmd", "-quickurl", url, "-quickout", "/dev/stdout"]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        vulns: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            # ZAP outputs alerts with risk levels
            risk_match = re.search(r"(High|Medium|Low|Informational)\s*:\s*(.+)", line, re.IGNORECASE)
            if risk_match:
                severity = risk_match.group(1).lower()
                title = risk_match.group(2).strip()
                vulns.append({"title": title, "severity": severity})
            elif "alert" in line.lower() and line:
                vulns.append({"title": line, "severity": "info"})
        return {"findings": [v["title"] for v in vulns], "vulnerabilities": vulns, "raw": raw_output}
