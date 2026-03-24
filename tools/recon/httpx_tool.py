from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class HttpxTool(BaseTool):
    name = "httpx"
    phase = "recon"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)

    def check_installed(self) -> bool:
        return shutil.which("httpx") is not None

    def build_command(self, target: str) -> list[str]:
        cmd = ["httpx", "-u", target, "-silent", "-status-code", "-title"]
        if self._proxy:
            cmd += ["-http-proxy", self._proxy]
        return cmd

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        urls: list[str] = []
        url_re = re.compile(r"(https?://\S+)")
        for line in text.splitlines():
            m = url_re.search(line)
            if m:
                urls.append(m.group(1))
        return {"urls": sorted(set(urls))}
