from __future__ import annotations

import re
import shutil
from typing import Any

from tools.base_tool import BaseTool

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class YsoserialTool(BaseTool):
    name = "ysoserial"
    phase = "exploitation"

    def __init__(self, *, timeout_s: float, web_scheme: str, proxy: str | None = None) -> None:
        super().__init__(timeout_s=timeout_s, proxy=proxy)

    def check_installed(self) -> bool:
        # ysoserial is typically a JAR file
        import os
        jar_paths = [
            shutil.which("ysoserial"),
            "/opt/ysoserial/ysoserial.jar",
            "/usr/share/ysoserial/ysoserial.jar",
        ]
        return any(p and (shutil.which(p) is not None or os.path.isfile(p)) for p in jar_paths if p)

    def build_command(self, target: str) -> list[str]:
        # List available gadget chains for the target
        return ["java", "-jar", "/opt/ysoserial/ysoserial.jar"]

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        text = ANSI_ESCAPE_RE.sub("", raw_output)
        gadgets: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            # ysoserial lists gadget chains in its help output
            if re.match(r"^\s*(CommonsCollections|Spring|Groovy|BeanShell|Clojure|CommonsBeanutils)\w*", line):
                gadgets.append(line.split()[0] if line.split() else line)
        return {"findings": gadgets, "gadget_chains": gadgets, "raw": raw_output}
