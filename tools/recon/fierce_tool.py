from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class FierceTool(BaseTool):
    name = "fierce"
    phase = "recon"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)

    def check_installed(self) -> bool:
        return shutil.which("fierce") is not None

    def build_command(self, target: str) -> list[str]:
        return ["fierce", "--domain", target]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        subdomains: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            # fierce outputs lines like: "Found: sub.domain.com. (1.2.3.4)"
            match = re.search(r"Found:\s+([\w.-]+\.[a-zA-Z]{2,})", line)
            if match:
                subdomains.append(match.group(1).rstrip("."))
        return {"findings": subdomains, "subdomains": subdomains, "raw": raw_output}
