"""
FalsePositiveFilter — AI-powered false positive detection for HackEmpire X.

Every vulnerability found by scanners goes through this filter before
being included in the final report. Confidence < threshold = filtered out.

Filter logic (3 layers):
  1. Rule-based pre-filter (fast, no AI needed)
  2. AI verification (Bytez → OpenRouter → KB heuristic)
  3. Confidence scoring — final decision
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from hackempire.core.models import Vulnerability

logger = logging.getLogger(__name__)

# Minimum confidence to keep a finding
DEFAULT_CONFIDENCE_THRESHOLD = 0.60

# Patterns that are almost always false positives
# NOTE: Use full-word matching to avoid false filtering of valid targets
# e.g. "testphp.vulnweb.com" is a valid bug bounty target
_FP_URL_PATTERNS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "example.com",
    "placeholder",
    "dummy",
]

# Vuln names that scanners commonly false-positive on
_NOISY_VULN_NAMES = {
    "missing x-frame-options",
    "missing content-security-policy",
    "missing x-content-type-options",
    "server version disclosure",
    "x-powered-by header",
    "clickjacking",
    "autocomplete enabled",
    "cookie without httponly",
    "cookie without secure",
}


@dataclass
class FilterResult:
    vuln: Vulnerability
    kept: bool
    reason: str
    final_confidence: float


class FalsePositiveFilter:
    """
    Filters scanner findings to remove false positives.

    Usage:
        fp_filter = FalsePositiveFilter(ai_engine=ai_engine)
        clean_vulns = fp_filter.filter(raw_vulns)
    """

    def __init__(
        self,
        ai_engine: Any = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._ai = ai_engine
        self._threshold = confidence_threshold

    def filter(self, vulns: list[Vulnerability]) -> list[Vulnerability]:
        """
        Filter a list of vulnerabilities. Returns only real findings.
        Never raises — on any error, keeps the finding (safe default).
        """
        if not vulns:
            return []

        results: list[FilterResult] = []
        for vuln in vulns:
            try:
                result = self._evaluate(vuln)
                results.append(result)
            except Exception as exc:
                logger.warning(f"[fp_filter] Error evaluating {vuln.name}: {exc} — keeping")
                results.append(FilterResult(
                    vuln=vuln, kept=True,
                    reason="filter_error_keep",
                    final_confidence=vuln.confidence,
                ))

        kept = [r.vuln for r in results if r.kept]
        filtered = len(vulns) - len(kept)
        if filtered > 0:
            logger.info(f"[fp_filter] Filtered {filtered}/{len(vulns)} false positives")

        return kept

    def filter_with_details(self, vulns: list[Vulnerability]) -> list[FilterResult]:
        """Same as filter() but returns full FilterResult list for reporting."""
        results = []
        for vuln in vulns:
            try:
                results.append(self._evaluate(vuln))
            except Exception as exc:
                logger.warning(f"[fp_filter] Error: {exc}")
                results.append(FilterResult(
                    vuln=vuln, kept=True,
                    reason="filter_error_keep",
                    final_confidence=vuln.confidence,
                ))
        return results

    # ── Internal ─────────────────────────────────────────────────────────

    def _evaluate(self, vuln: Vulnerability) -> FilterResult:
        """3-layer evaluation pipeline."""

        # Layer 1: Rule-based pre-filter (instant)
        rule_result = self._rule_based_check(vuln)
        if rule_result is not None:
            return rule_result

        # Layer 2: AI verification (if available)
        if self._ai is not None:
            ai_confidence = self._ai_verify(vuln)
            if ai_confidence is not None:
                final_conf = (vuln.confidence * 0.4) + (ai_confidence * 0.6)
                kept = final_conf >= self._threshold
                return FilterResult(
                    vuln=vuln, kept=kept,
                    reason="ai_verified" if kept else "ai_rejected",
                    final_confidence=round(final_conf, 3),
                )

        # Layer 3: Heuristic confidence check
        return self._heuristic_check(vuln)

    def _rule_based_check(self, vuln: Vulnerability) -> FilterResult | None:
        """Fast rule-based checks. Returns None if no rule matches."""

        # Always keep critical/high severity
        if vuln.severity in ("critical", "high") and vuln.confidence >= 0.5:
            return FilterResult(
                vuln=vuln, kept=True,
                reason="high_severity_keep",
                final_confidence=vuln.confidence,
            )

        # Filter known noisy vuln names
        name_lower = vuln.name.lower().strip()
        if name_lower in _NOISY_VULN_NAMES:
            return FilterResult(
                vuln=vuln, kept=False,
                reason="noisy_vuln_filtered",
                final_confidence=vuln.confidence,
            )

        # Filter if URL contains obvious FP indicators
        url_lower = (vuln.url or "").lower()
        for indicator in _FP_URL_PATTERNS:
            if indicator in url_lower and vuln.severity in ("info", "low"):
                return FilterResult(
                    vuln=vuln, kept=False,
                    reason=f"fp_url_{indicator.replace('.', '_')}",
                    final_confidence=vuln.confidence,
                )

        # Filter info severity with very low confidence
        if vuln.severity == "info" and vuln.confidence < 0.4:
            return FilterResult(
                vuln=vuln, kept=False,
                reason="info_low_confidence",
                final_confidence=vuln.confidence,
            )

        return None  # No rule matched — proceed to AI

    def _ai_verify(self, vuln: Vulnerability) -> float | None:
        """
        Ask AI to verify if this finding is real.
        Returns confidence float (0.0-1.0) or None if AI unavailable.
        """
        try:
            prompt = self._build_verify_prompt(vuln)
            # Use public verify_finding method if available, else _send as fallback
            if hasattr(self._ai, "verify_finding"):
                return self._ai.verify_finding(prompt)
            elif hasattr(self._ai, "_send"):
                response = self._ai._send(prompt)
                if response.get("status_code") != 200 or not response.get("raw_text"):
                    return None
                return self._parse_verify_response(response["raw_text"])
            return None
        except Exception as exc:
            logger.debug(f"[fp_filter] AI verify failed: {exc}")
            return None

    def _build_verify_prompt(self, vuln: Vulnerability) -> str:
        tool_str = ", ".join(vuln.tool_sources) if vuln.tool_sources else "unknown"
        return (
            "You are a senior penetration tester reviewing scanner findings.\n\n"
            f"Vulnerability: {vuln.name}\n"
            f"Severity: {vuln.severity}\n"
            f"URL: {vuln.url}\n"
            f"Evidence: {(vuln.evidence or 'none')[:300]}\n"
            f"Tool: {tool_str}\n"
            f"Scanner confidence: {vuln.confidence:.0%}\n\n"
            "Is this a real vulnerability or a false positive?\n"
            "Consider: Is the evidence convincing? Is the URL realistic? "
            "Does the evidence match the vulnerability type?\n\n"
            'OUTPUT (strict JSON only): {"real": true, "confidence": 0.85, "reason": "..."}\n'
            "RULES: Output ONLY valid JSON. No explanation. No markdown."
        )

    def _parse_verify_response(self, raw_text: str) -> float | None:
        """Parse AI verification response. Returns confidence or None."""
        try:
            text = raw_text.strip()
            brace = text.find("{")
            if brace == -1:
                return None
            data = json.loads(text[brace:])
            if not isinstance(data, dict):
                return None
            is_real = data.get("real", True)
            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
            # If AI says not real, return low confidence
            return confidence if is_real else (confidence * 0.2)
        except Exception:
            return None

    def _heuristic_check(self, vuln: Vulnerability) -> FilterResult:
        """Final heuristic check based on confidence score."""
        kept = vuln.confidence >= self._threshold
        return FilterResult(
            vuln=vuln, kept=kept,
            reason="confidence_threshold" if kept else "below_threshold",
            final_confidence=vuln.confidence,
        )
