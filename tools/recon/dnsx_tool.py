from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class DnsxTool(BaseTool):
    name = "dnsx"
    phase = "recon"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)

    def check_installed(self) -> bool:
        return shutil.which("dnsx") is not None

    def build_command(self, target: str) -> list[str]:
        return ["dnsx", "-d", target, "-silent", "-a", "-resp"]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        subdomains: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("["):
                # Lines like: sub.example.com [1.2.3.4]
                domain = line.split()[0]
                if domain:
                    subdomains.append(domain)
        return {"subdomains": sorted(set(subdomains))}
