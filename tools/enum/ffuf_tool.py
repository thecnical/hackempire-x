from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from tools.base_tool import BaseTool


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class FFUFTool(BaseTool):
    name = "ffuf"
    phase = "enum"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)
        self._web_scheme = web_scheme
        self._wordlist_path = os.environ.get("FFUF_WORDLIST", "wordlist.txt")

    def check_installed(self) -> bool:
        if shutil.which("ffuf") is None:
            return False
        wl = Path(self._wordlist_path)
        return wl.exists() and wl.is_file()

    def build_command(self, target: str) -> list[str]:
        base_url = f"{self._web_scheme}://{target}".rstrip("/")
        cmd = ["ffuf", "-u", f"{base_url}/FUZZ", "-w", self._wordlist_path]
        if self._proxy:
            cmd += ["-x", self._proxy]
        return cmd

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        base_url = None

        # Best-effort: infer base URL from the ffuf URL line.
        url_match = re.search(r"-u\s+(https?://[^\s]+)", text)
        if url_match:
            base_url = url_match.group(1).rstrip("/")

        urls: set[str] = set()

        # Typical result line:
        # admin [Status: 200, Size: ...]
        p1 = re.compile(r"^\s*(?P<endpoint>[A-Za-z0-9._%/\-]+)\s+\[Status:\s*(?P<status>\d{3})", re.MULTILINE)
        for m in p1.finditer(text):
            endpoint = m.group("endpoint").strip()
            endpoint = endpoint.strip("/")
            if not endpoint:
                continue

            if base_url:
                urls.add(f"{base_url}/{endpoint}")
            else:
                # No base URL detected; keep relative endpoint.
                urls.add(f"/{endpoint}")

        # Fallback: look for lines containing "=>"
        if not urls:
            p2 = re.compile(r"^\s*(?P<endpoint>[A-Za-z0-9._%/\-]+)\s+=>\s*(?P<rest>.*)$", re.MULTILINE)
            for m in p2.finditer(text):
                endpoint = m.group("endpoint").strip().strip("/")
                if endpoint:
                    if base_url:
                        urls.add(f"{base_url}/{endpoint}")
                    else:
                        urls.add(f"/{endpoint}")

        return {"urls": sorted(urls)}

