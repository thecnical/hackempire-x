from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class JoomscanTool(BaseTool):
    name = "joomscan"
    phase = "enumeration"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)
        self._web_scheme = web_scheme

    def check_installed(self) -> bool:
        return shutil.which("joomscan") is not None

    def build_command(self, target: str) -> list[str]:
        url = target if target.startswith("http") else f"{self._web_scheme}://{target}"
        return ["joomscan", "-u", url]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        vulns: list[dict[str, Any]] = []
        version: str | None = None
        for line in text.splitlines():
            line = line.strip()
            ver_match = re.search(r"Joomla\s+([\d.]+)", line, re.IGNORECASE)
            if ver_match:
                version = ver_match.group(1)
            if "[!]" in line or "vulnerability" in line.lower() or "CVE" in line:
                vulns.append({"title": line, "severity": "medium"})
        findings = [v["title"] for v in vulns]
        if version:
            findings.insert(0, f"Joomla version: {version}")
        return {"findings": findings, "vulnerabilities": vulns, "version": version, "raw": raw_output}
