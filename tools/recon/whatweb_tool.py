"""
WhatWeb Tool — Technology fingerprinting for HackEmpire X.

Detects CMS, frameworks, server software, WAF, and JS libraries.
Results are stored in recon state so the AI and downstream phases
can make smarter decisions (e.g. skip PHP-specific enum on a Node app).
"""
from __future__ import annotations

import json
import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class WhatWebTool(BaseTool):
    name = "whatweb"
    phase = "recon"

    def __init__(self, *, timeout_s: float, web_scheme: str) -> None:
        super().__init__(timeout_s=timeout_s)
        self._web_scheme = web_scheme

    def check_installed(self) -> bool:
        return shutil.which("whatweb") is not None

    def build_command(self, target: str) -> list[str]:
        url = f"{self._web_scheme}://{target}"
        # --log-json=- streams JSON to stdout; --quiet suppresses progress
        return ["whatweb", "--log-json=-", "--quiet", url]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output).strip()
        technologies: list[dict[str, Any]] = []

        # WhatWeb --log-json=- outputs one JSON object per line
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Each object: {"target": "...", "http_status": 200, "plugins": {...}}
            plugins = obj.get("plugins") or {}
            for plugin_name, plugin_data in plugins.items():
                entry: dict[str, Any] = {"name": plugin_name}
                # Extract version strings if present
                versions = plugin_data.get("version") if isinstance(plugin_data, dict) else None
                if versions:
                    entry["version"] = versions[0] if isinstance(versions, list) else str(versions)
                # Extract string evidence
                strings = plugin_data.get("string") if isinstance(plugin_data, dict) else None
                if strings and isinstance(strings, list):
                    entry["detail"] = strings[0]
                technologies.append(entry)

        # Fallback: plain-text parsing if JSON mode not available
        if not technologies and text:
            # e.g. "http://example.com [200 OK] Apache[2.4.41], PHP[7.4.3], WordPress[5.8]"
            bracket_re = re.compile(r"([A-Za-z0-9._\-]+)\[([^\]]+)\]")
            for m in bracket_re.finditer(text):
                name, detail = m.group(1), m.group(2)
                if name.lower() in ("http", "https", "200", "301", "302", "404"):
                    continue
                technologies.append({"name": name, "detail": detail})

        return {"technologies": technologies}
