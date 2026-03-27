from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class CertipyTool(BaseTool):
    name = "certipy"
    phase = "exploitation"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)

    def check_installed(self) -> bool:
        return shutil.which("certipy") is not None or shutil.which("certipy-ad") is not None

    def build_command(self, target: str) -> list[str]:
        binary = "certipy" if shutil.which("certipy") else "certipy-ad"
        return [binary, "find", "-target", target, "-vulnerable"]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        vulns: list[dict[str, Any]] = []
        templates: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            # Certipy outputs ESC vulnerabilities
            esc_match = re.search(r"(ESC\d+)", line)
            if esc_match:
                vulns.append({"title": line, "severity": "high", "technique": esc_match.group(1)})
            tmpl_match = re.search(r"Template Name\s*:\s*(.+)", line)
            if tmpl_match:
                templates.append(tmpl_match.group(1).strip())
        return {"findings": [v["title"] for v in vulns], "vulnerabilities": vulns, "templates": templates, "raw": raw_output}
