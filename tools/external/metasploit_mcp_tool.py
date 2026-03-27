from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class MetasploitMCPTool(BaseTool):
    name = "MetasploitMCP"
    phase = "exploitation"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)

    def check_installed(self) -> bool:
        return shutil.which("msfconsole") is not None

    def build_command(self, target: str) -> list[str]:
        # Run msfconsole in resource script mode for basic scan
        return ["msfconsole", "-q", "-x", f"db_nmap -sV {target}; exit"]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        sessions: list[str] = []
        exploits: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if "session" in line.lower() and ("opened" in line.lower() or "meterpreter" in line.lower()):
                sessions.append(line)
            if "exploit" in line.lower() and ("success" in line.lower() or "shell" in line.lower()):
                exploits.append({"title": line, "severity": "critical"})
        return {"findings": sessions + [e["title"] for e in exploits], "sessions": sessions, "vulnerabilities": exploits, "raw": raw_output}
