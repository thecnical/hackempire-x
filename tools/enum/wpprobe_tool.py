from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class WPProbeTool(BaseTool):
    name = "WPProbe"
    phase = "enumeration"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)
        self._web_scheme = web_scheme

    def check_installed(self) -> bool:
        return shutil.which("wpprobe") is not None or shutil.which("WPProbe") is not None

    def build_command(self, target: str) -> list[str]:
        binary = "WPProbe" if shutil.which("WPProbe") else "wpprobe"
        url = target if target.startswith("http") else f"{self._web_scheme}://{target}"
        return [binary, "-u", url]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        plugins: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if "plugin" in line.lower() or re.search(r"wp-content/plugins/[\w-]+", line):
                match = re.search(r"wp-content/plugins/([\w-]+)", line)
                if match:
                    plugins.append(match.group(1))
                elif line:
                    plugins.append(line)
        return {"findings": plugins, "plugins": plugins, "raw": raw_output}
