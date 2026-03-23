from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool


class NmapTool(BaseTool):
    name = "nmap"
    phase = "recon"

    def __init__(self, *, timeout_s: float, web_scheme: str) -> None:
        super().__init__(timeout_s=timeout_s)

    def check_installed(self) -> bool:
        return shutil.which("nmap") is not None

    def build_command(self, target: str) -> list[str]:
        return ["nmap", "-sV", "-T4", target]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        # Example line:
        # 22/tcp open  ssh  OpenSSH 9.6p1 Ubuntu 3ubuntu0.1
        open_ports: list[dict[str, str | int]] = []
        pattern = re.compile(r"^(?P<port>\d+)\/(?P<proto>tcp|udp)\s+open\s+(?P<service>[\w\-.]+)", re.MULTILINE)
        for m in pattern.finditer(raw_output):
            port = int(m.group("port"))
            service = m.group("service")
            open_ports.append({"port": port, "service": service, "state": "open"})

        # As a fallback, parse lines containing " open " and "/tcp".
        if not open_ports:
            pattern2 = re.compile(r"^(?P<port>\d+)\/tcp\s+open\s+(?P<service>[\w\-.]+)", re.MULTILINE)
            for m in pattern2.finditer(raw_output):
                port = int(m.group("port"))
                service = m.group("service")
                open_ports.append({"port": port, "service": service, "state": "open"})

        return {"ports": open_ports}

