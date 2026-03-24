"""
CVE Correlator — maps nmap port/service findings to real CVEs via the NVD API.

Uses the NIST NVD REST API v2 (no key required for basic use, rate-limited to 5 req/30s).
Falls back gracefully if the network is unavailable or the API is rate-limited.

Output added to recon state:
  "cve_findings": [
    {
      "port": 22,
      "service": "ssh",
      "cve_id": "CVE-2023-38408",
      "description": "...",
      "cvss_score": 9.8,
      "severity": "critical",
      "published": "2023-07-19",
      "references": ["https://..."]
    },
    ...
  ]
"""
from __future__ import annotations

import os
import time
from typing import Any, Optional

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

from utils.logger import Logger

# NVD API v2 endpoint
_NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"

# Seconds to wait between NVD requests to respect rate limit (5 req / 30s)
_NVD_RATE_DELAY = 6.5

# Max CVEs to fetch per service keyword
_MAX_CVE_PER_SERVICE = 5

# CVSS score → severity label
def _cvss_severity(score: float) -> str:
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"


class CVECorrelator:
    """
    Correlates nmap port/service results with CVEs from the NVD API.

    Usage:
        correlator = CVECorrelator(logger=logger, proxy=None)
        cve_findings = correlator.correlate(ports)
    """

    def __init__(
        self,
        *,
        logger: Logger,
        proxy: Optional[str] = None,
        timeout_s: float = 10.0,
        api_key: Optional[str] = None,
    ) -> None:
        self._logger = logger
        self._proxy = proxy or os.environ.get("HACKEMPIRE_PROXY")
        self._timeout_s = timeout_s
        # NVD API key (optional — raises rate limit from 5/30s to 50/30s)
        self._api_key = api_key or os.environ.get("NVD_API_KEY")

    def correlate(self, ports: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Given a list of port dicts from nmap, return CVE findings.
        Never raises — returns empty list on any failure.
        """
        if not _REQUESTS_AVAILABLE:
            self._logger.warning("[cve] requests library not available — CVE correlation skipped.")
            return []

        if not ports:
            return []

        # Deduplicate service keywords to avoid redundant API calls
        seen_services: set[str] = set()
        cve_findings: list[dict[str, Any]] = []

        for port_entry in ports:
            if not isinstance(port_entry, dict):
                continue
            service = str(port_entry.get("service") or "").strip().lower()
            port_num = port_entry.get("port")

            if not service or service in seen_services:
                continue
            seen_services.add(service)

            self._logger.info(f"[cve] Querying NVD for service: {service} (port {port_num})")
            cves = self._fetch_cves(service)

            for cve in cves:
                cve["port"] = port_num
                cve["service"] = service
                cve_findings.append(cve)

            # Respect NVD rate limit
            time.sleep(_NVD_RATE_DELAY)

        self._logger.info(f"[cve] Correlation complete: {len(cve_findings)} CVE(s) found.")
        return cve_findings

    def _fetch_cves(self, keyword: str) -> list[dict[str, Any]]:
        """Query NVD API for CVEs matching a service keyword."""
        params: dict[str, Any] = {
            "keywordSearch": keyword,
            "resultsPerPage": _MAX_CVE_PER_SERVICE,
            "startIndex": 0,
        }
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._api_key:
            headers["apiKey"] = self._api_key

        proxies = {"http": self._proxy, "https": self._proxy} if self._proxy else None

        try:
            resp = _requests.get(
                _NVD_BASE,
                params=params,
                headers=headers,
                timeout=self._timeout_s,
                proxies=proxies,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            self._logger.warning(f"[cve] NVD API request failed for '{keyword}': {exc}")
            return []

        results: list[dict[str, Any]] = []
        for item in data.get("vulnerabilities") or []:
            cve_obj = item.get("cve") or {}
            cve_id = cve_obj.get("id", "")
            if not cve_id:
                continue

            # Description (English preferred)
            descriptions = cve_obj.get("descriptions") or []
            description = ""
            for d in descriptions:
                if isinstance(d, dict) and d.get("lang") == "en":
                    description = d.get("value", "")
                    break

            # CVSS score — try v3.1 first, then v3.0, then v2
            cvss_score = 0.0
            metrics = cve_obj.get("metrics") or {}
            for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                metric_list = metrics.get(key)
                if metric_list and isinstance(metric_list, list):
                    cvss_data = metric_list[0].get("cvssData") or {}
                    cvss_score = float(cvss_data.get("baseScore") or 0.0)
                    break

            # Published date
            published = str(cve_obj.get("published") or "")[:10]

            # References
            refs = [
                r.get("url", "")
                for r in (cve_obj.get("references") or [])
                if isinstance(r, dict) and r.get("url")
            ][:3]

            results.append({
                "cve_id": cve_id,
                "description": description[:300],
                "cvss_score": cvss_score,
                "severity": _cvss_severity(cvss_score),
                "published": published,
                "references": refs,
            })

        return results
