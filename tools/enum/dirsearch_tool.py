from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from tools.base_tool import BaseTool


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class DirsearchTool(BaseTool):
    name = "dirsearch"
    phase = "enum"

    def __init__(self, *, timeout_s: float, web_scheme: str) -> None:
        super().__init__(timeout_s=timeout_s)
        self._web_scheme = web_scheme
        self._script_path = os.environ.get("DIRSEARCH_SCRIPT", "dirsearch.py")

    def check_installed(self) -> bool:
        # dirsearch is a Python script, not a system binary.
        # Check that python3 is available AND the script file exists.
        if shutil.which("python3") is None and shutil.which("python") is None:
            return False
        script = Path(self._script_path)
        return script.exists() and script.is_file()

    def build_command(self, target: str) -> list[str]:
        base_url = f"{self._web_scheme}://{target}"
        python_bin = shutil.which("python3") or shutil.which("python") or "python3"
        return [python_bin, self._script_path, "-u", base_url, "--plain-text-report", "/dev/stdout"]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        base_url = None

        # Best-effort: infer base URL if the output includes it.
        # dirsearch commonly prints target at the top; if not found, we still return paths.
        # We'll keep it simple: only build full URLs when we can reliably detect the scheme prefix.
        # Otherwise return paths as "urls".
        url_prefix_match = re.search(r"(https?://[^\s]+)\s*$", text, flags=re.MULTILINE)
        if url_prefix_match:
            base_url = url_prefix_match.group(1).rstrip("/")

        found_paths: set[str] = set()

        p1 = re.compile(r"^\s*\[\s*(?P<status>\d{3})\]\s*(?P<path>\/\S+)\s*$", re.MULTILINE)
        for m in p1.finditer(text):
            found_paths.add(m.group("path"))

        p2 = re.compile(r"^\s*(?P<status>\d{3})\s*[-:]\s*(?P<path>\/\S+)\s*$", re.MULTILINE)
        for m in p2.finditer(text):
            found_paths.add(m.group("path"))

        # If output doesn't follow known patterns, fallback to any "/path" tokens.
        if not found_paths:
            p3 = re.compile(r"(\/[A-Za-z0-9._\-\/]{1,120})")
            for m in p3.finditer(text):
                candidate = m.group(1)
                if len(candidate) <= 120:
                    found_paths.add(candidate)

        # Produce unified "urls" list.
        if base_url:
            urls = [f"{base_url}{p}" if p.startswith("/") else f"{base_url}/{p}" for p in sorted(found_paths)]
        else:
            urls = sorted(found_paths)

        return {"urls": urls}

