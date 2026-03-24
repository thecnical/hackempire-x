from __future__ import annotations

import re
import shutil
from typing import Any, Optional

from tools.base_tool import BaseTool
from tools.waf.waf_bypass_strategy import WafBypassStrategy


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class NucleiTool(BaseTool):
    name = "nuclei"
    phase = "vuln"

    def __init__(
        self,
        *,
        timeout_s: float,
        web_scheme: str,
        proxy: str | None = None,
        waf_bypass: Optional[WafBypassStrategy] = None,
    ) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)
        self._web_scheme = web_scheme
        self._waf_bypass = waf_bypass

    def check_installed(self) -> bool:
        return shutil.which("nuclei") is not None

    def build_command(self, target: str) -> list[str]:
        base = f"{self._web_scheme}://{target}".rstrip("/")
        cmd = ["nuclei", "-u", base]
        if self._proxy:
            cmd += ["-proxy", self._proxy]
        if self._waf_bypass:
            cmd += self._waf_bypass.apply_to_nuclei_flags(None)
        return cmd

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)

        vulns: list[dict[str, Any]] = []
        severity_re = re.compile(r"\[(info|low|medium|high|critical)\]", re.IGNORECASE)
        url_re = re.compile(r"(https?://[^\s\]]+)")

        for line in text.splitlines():
            if not line.strip():
                continue
            msev = severity_re.search(line)
            if not msev:
                continue
            severity = msev.group(1).lower()
            murl = url_re.search(line)
            url = murl.group(1) if murl else ""

            vulns.append(
                {
                    "severity": severity,
                    "title": line.strip(),
                    "url": url,
                }
            )

        return {"vulnerabilities": vulns}
