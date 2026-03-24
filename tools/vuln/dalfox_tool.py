from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class DalfoxTool(BaseTool):
    name = "dalfox"
    phase = "vuln_scan"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)
        self._web_scheme = web_scheme

    def check_installed(self) -> bool:
        return shutil.which("dalfox") is not None

    def build_command(self, target: str) -> list[str]:
        base = f"{self._web_scheme}://{target}"
        cmd = ["dalfox", "url", base, "--silence"]
        if self._proxy:
            cmd += ["--proxy", self._proxy]
        return cmd

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        vulns: list[dict[str, Any]] = []
        # dalfox prints [POC] or [VULN] lines
        for line in text.splitlines():
            line = line.strip()
            if "[POC]" in line or "[VULN]" in line:
                vulns.append({"title": line, "severity": "high", "name": "XSS"})
        return {"vulnerabilities": vulns}
