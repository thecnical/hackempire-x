from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class TheHarvesterTool(BaseTool):
    name = "theHarvester"
    phase = "recon"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)

    def check_installed(self) -> bool:
        return shutil.which("theHarvester") is not None or shutil.which("theharvester") is not None

    def build_command(self, target: str) -> list[str]:
        binary = "theHarvester" if shutil.which("theHarvester") else "theharvester"
        return [binary, "-d", target, "-b", "all", "-l", "200"]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        emails: list[str] = []
        subdomains: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", line):
                emails.append(line)
            elif re.match(r"^[\w.-]+\.[a-zA-Z]{2,}$", line) and "." in line:
                subdomains.append(line)
        return {"findings": emails + subdomains, "emails": emails, "subdomains": subdomains, "raw": raw_output}
