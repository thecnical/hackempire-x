from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import BaseTool
from tools.waf.waf_bypass_strategy import WafBypassStrategy

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class SqlmapTool(BaseTool):
    name = "sqlmap"
    phase = "exploitation"
    venv_packages = ["sqlmap"]

    def __init__(
        self,
        *,
        timeout_s: float,
        web_scheme: str,
        proxy: str | None = None,
        venv_python: Optional[Path] = None,
        waf_bypass: Optional[WafBypassStrategy] = None,
    ) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)
        self._web_scheme = web_scheme
        self._venv_python = venv_python
        self._waf_bypass = waf_bypass
        self._waf_vendor: Optional[str] = None

    def set_waf_vendor(self, vendor: str) -> None:
        self._waf_vendor = vendor

    def check_installed(self) -> bool:
        if self._venv_python and self._venv_python.exists():
            return True
        return shutil.which(self.name) is not None

    def build_command(self, target: str) -> list[str]:
        base = f"{self._web_scheme}://{target}"
        if self._venv_python:
            cmd = [str(self._venv_python), "-m", "sqlmap", "-u", base, "--batch", "--random-agent"]
        else:
            cmd = ["sqlmap", "-u", base, "--batch", "--random-agent"]

        if self._waf_bypass and self._waf_vendor:
            tampers = self._waf_bypass.get_sqlmap_tampers(self._waf_vendor)
            if tampers:
                cmd += ["--tamper", ",".join(tampers)]

        if self._proxy:
            cmd += ["--proxy", self._proxy]
        return cmd

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        vulns: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if "is vulnerable" in line.lower() or "parameter" in line.lower() and "injectable" in line.lower():
                vulns.append({"title": line, "severity": "critical", "name": "SQLi"})
        return {"vulnerabilities": vulns}
