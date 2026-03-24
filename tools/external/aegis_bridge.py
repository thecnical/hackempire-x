from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from hackempire.core.models import ChainResult, ToolAttempt

AEGIS_REPO = "https://github.com/thecnical/aegis"
AEGIS_DIR = Path("tools/external/aegis")
AEGIS_BINARY = AEGIS_DIR / "aegis"

AEGIS_TYPE_MAP = {
    "subdomain": lambda r: {"subdomains": [r["value"]]},
    "url": lambda r: {"urls": [r["value"]]},
    "vulnerability": lambda r: {
        "vulnerabilities": [
            {
                "name": r.get("name", "unknown"),
                "severity": r.get("severity", "info"),
                "url": r.get("url"),
                "evidence": r.get("evidence", ""),
                "tool_sources": ["aegis"],
            }
        ]
    },
}


class AegisBridge:
    """Bridge to the external aegis CLI tool."""

    def is_available(self) -> bool:
        try:
            return AEGIS_DIR.exists() and AEGIS_BINARY.exists() and os.access(AEGIS_BINARY, os.X_OK)
        except Exception:
            return False

    def ensure_installed(self) -> bool:
        try:
            if AEGIS_DIR.exists():
                return True
            result = subprocess.run(
                ["git", "clone", AEGIS_REPO, str(AEGIS_DIR)],
                shell=False,
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def run(self, target: str, phase: str) -> ChainResult:
        try:
            if not self.is_available():
                if not self.ensure_installed():
                    return ChainResult(
                        phase=phase,
                        succeeded_tool=None,
                        results={},
                        tool_attempts=[ToolAttempt("aegis", "not_installed", "aegis not available")],
                        degraded=True,
                    )

            if not self.is_available():
                return ChainResult(
                    phase=phase,
                    succeeded_tool=None,
                    results={},
                    tool_attempts=[ToolAttempt("aegis", "not_installed", "aegis not available after install attempt")],
                    degraded=True,
                )

            proc = subprocess.run(
                [str(AEGIS_BINARY), "--target", target, "--phase", phase, "--json"],
                capture_output=True,
                timeout=120,
                shell=False,
            )

            if proc.returncode != 0 or not proc.stdout:
                error_msg = proc.stderr.decode(errors="replace") if proc.stderr else "empty output"
                return ChainResult(
                    phase=phase,
                    succeeded_tool=None,
                    results={},
                    tool_attempts=[ToolAttempt("aegis", "failed", error_msg)],
                    degraded=True,
                )

            parsed = self._parse_aegis_output(proc.stdout.decode(errors="replace"), phase)
            return ChainResult(
                phase=phase,
                succeeded_tool="aegis",
                results=parsed,
                tool_attempts=[ToolAttempt("aegis", "success")],
                degraded=False,
            )

        except Exception as e:
            return ChainResult(
                phase=phase,
                succeeded_tool=None,
                results={},
                tool_attempts=[ToolAttempt("aegis", "error", str(e))],
                degraded=True,
            )

    def _parse_aegis_output(self, raw: str, phase: str) -> dict:
        try:
            merged: dict = {}
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                record_type = record.get("type")
                mapper = AEGIS_TYPE_MAP.get(record_type)
                if mapper is None:
                    continue
                partial = mapper(record)
                for key, value in partial.items():
                    if key in merged and isinstance(merged[key], list):
                        merged[key].extend(value)
                    else:
                        merged[key] = value
            return merged
        except Exception:
            return {}
