from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class NiktoTool(BaseTool):
    name = "nikto"
    phase = "vuln_scan"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)
        self._web_scheme = web_scheme

    def check_installed(self) -> bool:
        return shutil.which("nikto") is not None

    def build_command(self, target: str) -> list[str]:
        cmd = ["nikto", "-h", target, "-nointeractive"]
        if self._proxy:
            cmd += ["-useproxy", self._proxy]
        return cmd

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        vulns: list[dict[str, Any]] = []
        # Nikto lines start with "+ " for findings
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("+ ") and "OSVDB" in line or (line.startswith("+") and ":" in line):
                vulns.append({"title": line.lstrip("+ "), "severity": "info"})
        return {"vulnerabilities": vulns}
