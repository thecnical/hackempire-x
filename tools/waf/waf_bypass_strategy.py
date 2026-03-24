from __future__ import annotations

WAF_TAMPER_MAP: dict[str, list[str]] = {
    "cloudflare":  ["space2comment", "randomcase", "between"],
    "akamai":      ["between", "charencode", "space2comment"],
    "modsecurity": ["space2comment", "charencode", "randomcomments"],
    "imperva":     ["between", "charencode", "space2randomblank"],
    "f5":          ["randomcase", "space2comment", "charencode"],
    "barracuda":   ["space2comment", "randomcase"],
    "sucuri":      ["charencode", "between"],
}

BYPASS_HEADERS: dict[str, str] = {
    "X-Forwarded-For":  "127.0.0.1",
    "X-Real-IP":        "127.0.0.1",
    "X-Originating-IP": "127.0.0.1",
    "X-Remote-IP":      "127.0.0.1",
    "X-Remote-Addr":    "127.0.0.1",
    "X-Client-IP":      "127.0.0.1",
    "CF-Connecting-IP": "127.0.0.1",
    "True-Client-IP":   "127.0.0.1",
}

_DEFAULT_TAMPERS = ["space2comment", "randomcase"]


class WafBypassStrategy:
    """Provides WAF bypass strategies for sqlmap, nuclei, and raw headers."""

    def get_sqlmap_tampers(self, waf_vendor: str | None) -> list[str]:
        """Return sqlmap tamper scripts for the given WAF vendor."""
        if waf_vendor is None:
            return list(_DEFAULT_TAMPERS)

        normalized = waf_vendor.lower()

        # Exact match first
        if normalized in WAF_TAMPER_MAP:
            return list(WAF_TAMPER_MAP[normalized])

        # Partial match
        for key, tampers in WAF_TAMPER_MAP.items():
            if key in normalized or normalized in key:
                return list(tampers)

        return list(_DEFAULT_TAMPERS)

    def get_bypass_headers(self, waf_vendor: str | None) -> dict[str, str]:
        """Return bypass headers dict (same for all vendors)."""
        return dict(BYPASS_HEADERS)

    def apply_to_nuclei_flags(self, waf_vendor: str | None) -> list[str]:
        """Return --header flag list for nuclei from BYPASS_HEADERS."""
        flags: list[str] = []
        for header, value in BYPASS_HEADERS.items():
            flags.append("--header")
            flags.append(f"{header}: {value}")
        return flags
