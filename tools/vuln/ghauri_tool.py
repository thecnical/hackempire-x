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
    venv_packages = ["ghauri"]

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
        self._venv_python = venv_python

    def check_installed(self) -> bool:
        if self._venv_python and self._venv_python.exists():
            return True
        return shutil.which(self.name) is not None

    def build_command(self, target: str) -> list[str]:
        base = f"{self._web_scheme}://{target}"
        if self._venv_python:
            cmd = [str(self._venv_python), "-m", "ghauri", "-u", base, "--batch"]
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
