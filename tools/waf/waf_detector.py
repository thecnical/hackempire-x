from __future__ import annotations

import json
import shutil
import subprocess

from hackempire.core.models import WafResult


class WafDetector:
    """Detects WAF presence using wafw00f."""

    def detect(self, target: str) -> WafResult:
        """Run wafw00f against target and return a WafResult. Never raises."""
        try:
            if not shutil.which("wafw00f"):
                return WafResult(detected=False, vendor=None, confidence=0.0)

            result = subprocess.run(
                ["wafw00f", target, "-o", "-", "-f", "json"],
                capture_output=True,
                timeout=30,
                shell=False,
            )

            if result.returncode != 0 or not result.stdout:
                return WafResult(detected=False, vendor=None, confidence=0.0)

            data = json.loads(result.stdout.decode("utf-8", errors="replace"))

            # wafw00f JSON output: [{"url": "...", "detected": true/false, "firewall": "...", "manufacturer": "..."}]
            if not data or not isinstance(data, list):
                return WafResult(detected=False, vendor=None, confidence=0.0)

            entry = data[0]
            detected = bool(entry.get("detected", False))
            vendor = entry.get("firewall") if detected else None
            confidence = 0.8 if detected else 0.0

            return WafResult(detected=detected, vendor=vendor, confidence=confidence)

        except Exception:
            return WafResult(detected=False, vendor=None, confidence=0.0)
