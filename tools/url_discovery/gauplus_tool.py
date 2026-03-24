from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class GauTool(BaseTool):
    name = "gau"
    phase = "url_discovery"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)

    def check_installed(self) -> bool:
        return shutil.which("gau") is not None

    def build_command(self, target: str) -> list[str]:
        return ["gau", target]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        url_re = re.compile(r"(https?://\S+)")
        urls = [m.group(1) for line in text.splitlines() for m in [url_re.search(line)] if m]
        return {"urls": sorted(set(urls))}
