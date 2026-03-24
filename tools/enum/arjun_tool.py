from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class ArjunTool(BaseTool):
    name = "arjun"
    phase = "enumeration"
    venv_packages = ["arjun"]

    def __init__(
        self,
        *,
        timeout_s: float,
        web_scheme: str,
        proxy: str | None = None,
        venv_python: Optional[Path] = None,
    ) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)
        self._web_scheme = web_scheme
        self._venv_python = venv_python

    def check_installed(self) -> bool:
        if self._venv_python and self._venv_python.exists():
            return True
        return shutil.which(self.name) is not None

    def build_command(self, target: str) -> list[str]:
        base = f"{self._web_scheme}://{target}"
        if self._venv_python:
            cmd = [str(self._venv_python), "-m", "arjun", "-u", base]
        else:
            cmd = ["arjun", "-u", base]
        return cmd

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        params: list[str] = []
        param_re = re.compile(r"\[.*?\]\s+(\w+)")
        for line in text.splitlines():
            m = param_re.search(line)
            if m:
                params.append(m.group(1))
        return {"parameters": sorted(set(params))}
