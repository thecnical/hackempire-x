from __future__ import annotations

import ipaddress
import re
import shutil
from typing import Any

from tools.base_tool import BaseTool, ToolExecutionError


class SubfinderTool(BaseTool):
    name = "subfinder"
    phase = "recon"

    def __init__(self, *, timeout_s: float, web_scheme: str) -> None:
        super().__init__(timeout_s=timeout_s)

    def check_installed(self) -> bool:
        return shutil.which("subfinder") is not None

    def build_command(self, target: str) -> list[str]:
        # subfinder only works on domain names, not raw IPs.
        try:
            ipaddress.ip_address(target)
            raise ToolExecutionError(
                f"subfinder does not support IP targets (got '{target}'). Skipping."
            )
        except ValueError:
            # Not an IP — treat as domain.
            pass
        return ["subfinder", "-d", target, "-silent"]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        # subfinder prints one subdomain per line (with -silent, no banner).
        ansi_re = re.compile(r"\x1b\[[0-9;]*m")
        lines = [ansi_re.sub("", ln).strip() for ln in raw_output.splitlines()]
        subs = [ln for ln in lines if ln and not ln.lower().startswith(("using", "output", "["))]
        return {"subdomains": sorted(set(subs))}

