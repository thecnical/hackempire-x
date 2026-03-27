from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class ReconNgTool(BaseTool):
    name = "recon-ng"
    phase = "recon"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)

    def check_installed(self) -> bool:
        return shutil.which("recon-ng") is not None

    def build_command(self, target: str) -> list[str]:
        # Run recon-ng in script mode with basic host enumeration
        return ["recon-ng", "-r", f"marketplace install recon/domains-hosts/hackertarget\nmodules load recon/domains-hosts/hackertarget\noptions set SOURCE {target}\nrun\nexit"]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        hosts: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if re.match(r"^[\w.-]+\.[a-zA-Z]{2,}$", line):
                hosts.append(line)
        return {"findings": hosts, "subdomains": hosts, "raw": raw_output}
