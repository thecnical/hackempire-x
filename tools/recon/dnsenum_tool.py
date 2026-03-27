from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class DnsEnumTool(BaseTool):
    name = "dnsenum"
    phase = "recon"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)

    def check_installed(self) -> bool:
        return shutil.which("dnsenum") is not None

    def build_command(self, target: str) -> list[str]:
        return ["dnsenum", "--nocolor", target]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        subdomains: list[str] = []
        zone_transfer = False
        for line in text.splitlines():
            line = line.strip()
            if "zone transfer" in line.lower() and "success" in line.lower():
                zone_transfer = True
            # Match lines like "sub.domain.com.  300  IN  A  1.2.3.4"
            match = re.match(r"^([\w.-]+\.[a-zA-Z]{2,})\.?\s+\d+\s+IN\s+", line)
            if match:
                subdomains.append(match.group(1).rstrip("."))
        findings = subdomains[:]
        if zone_transfer:
            findings.append("zone_transfer_success")
        return {"findings": findings, "subdomains": subdomains, "zone_transfer": zone_transfer, "raw": raw_output}
