from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class WPScanTool(BaseTool):
    name = "wpscan"
    phase = "enumeration"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)
        self._web_scheme = web_scheme

    def check_installed(self) -> bool:
        return shutil.which("wpscan") is not None

    def build_command(self, target: str) -> list[str]:
        url = target if target.startswith("http") else f"{self._web_scheme}://{target}"
        cmd = ["wpscan", "--url", url, "--no-banner", "--format", "cli"]
        if self._proxy:
            cmd += ["--proxy", self._proxy]
        return cmd

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        vulns: list[dict[str, Any]] = []
        plugins: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if "[!]" in line or "vulnerability" in line.lower() or "CVE" in line:
                vulns.append({"title": line, "severity": "medium"})
            match = re.search(r"Plugin: ([\w -]+)", line)
            if match:
                plugins.append(match.group(1).strip())
        return {"findings": [v["title"] for v in vulns], "vulnerabilities": vulns, "plugins": plugins, "raw": raw_output}
