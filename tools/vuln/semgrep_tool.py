from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class SemgrepTool(BaseTool):
    name = "semgrep"
    phase = "vuln_scan"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)

    def check_installed(self) -> bool:
        return shutil.which("semgrep") is not None

    def build_command(self, target: str) -> list[str]:
        return ["semgrep", "--config=auto", "--json", target]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        vulns: list[dict[str, Any]] = []
        # Try JSON parsing first
        try:
            import json
            data = json.loads(text)
            for result in data.get("results", []):
                vulns.append({
                    "title": result.get("check_id", "semgrep-finding"),
                    "severity": result.get("extra", {}).get("severity", "warning").lower(),
                    "path": result.get("path", ""),
                    "line": result.get("start", {}).get("line", 0),
                })
        except Exception:
            # Fallback: parse text output
            for line in text.splitlines():
                line = line.strip()
                if re.search(r"(error|warning|finding)", line, re.IGNORECASE) and line:
                    vulns.append({"title": line, "severity": "warning"})
        return {"findings": [v["title"] for v in vulns], "vulnerabilities": vulns, "raw": raw_output}
