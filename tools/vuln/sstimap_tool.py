from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class SSTImapTool(BaseTool):
    name = "SSTImap"
    phase = "vuln_scan"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)
        self._web_scheme = web_scheme

    def check_installed(self) -> bool:
        return shutil.which("sstimap") is not None or shutil.which("SSTImap") is not None

    def build_command(self, target: str) -> list[str]:
        binary = "SSTImap" if shutil.which("SSTImap") else "sstimap"
        url = target if target.startswith("http") else f"{self._web_scheme}://{target}"
        return [binary, "-u", url]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        vulns: list[dict[str, Any]] = []
        engine: str | None = None
        for line in text.splitlines():
            line = line.strip()
            if "ssti" in line.lower() or "injection" in line.lower() or "vulnerable" in line.lower():
                vulns.append({"title": line, "severity": "high"})
            eng_match = re.search(r"(Jinja2|Twig|Freemarker|Mako|Velocity|Smarty)", line, re.IGNORECASE)
            if eng_match:
                engine = eng_match.group(1)
        return {"findings": [v["title"] for v in vulns], "vulnerabilities": vulns, "engine": engine, "raw": raw_output}
