from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class GhauriTool(BaseTool):
    name = "ghauri"
    phase = "vuln_scan"
    venv_packages = []  # ghauri needs git clone install — not pip

    def __init__(
        self,
        *,
        timeout_s: float,
        web_scheme: str,
        proxy: str | None = None,
        venv_python: Optional[Path] = None,
    ) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)
        self._web_scheme = web_scheme
        self._venv_python = None  # Never use venv for ghauri

    def check_installed(self) -> bool:
        return shutil.which("ghauri") is not None or Path("/opt/ghauri/ghauri.py").exists()

    def build_command(self, target: str) -> list[str]:
        base = f"{self._web_scheme}://{target}"
        if Path("/opt/ghauri/ghauri.py").exists():
            cmd = ["python3", "/opt/ghauri/ghauri.py", "-u", base, "--batch"]
        else:
            cmd = ["ghauri", "-u", base, "--batch"]
        if self._proxy:
            cmd += ["--proxy", self._proxy]
        return cmd

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        vulns: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if "injectable" in line.lower() or "parameter" in line.lower():
                vulns.append({"title": line, "severity": "high", "name": "SQLi"})
        return {"vulnerabilities": vulns}
