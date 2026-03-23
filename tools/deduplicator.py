"""
Result deduplication and normalization utilities for HackEmpire X.

Handles:
- URL normalization and deduplication
- Subdomain normalization and deduplication
- Port deduplication by (port, service) key
- Vulnerability deduplication by (name, target) key
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    """Normalize a URL: lowercase scheme/host, strip trailing slash, drop fragment."""
    value = (url or "").strip()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        parts = urlsplit(value)
        scheme = (parts.scheme or "").lower()
        netloc = (parts.netloc or "").lower()
        path = parts.path or ""
        if path.endswith("/") and path != "/":
            path = path.rstrip("/")
        return urlunsplit((scheme, netloc, path, parts.query, "")).rstrip("/")
    # Relative path
    return value.rstrip("/") if value != "/" else value


def normalize_domain(host: str) -> str:
    """Lowercase, strip whitespace and trailing dot."""
    h = (host or "").strip().lower()
    return h[:-1] if h.endswith(".") else h


def deduplicate_urls(urls: list[str]) -> list[str]:
    """Return sorted unique normalized URLs, filtering empty strings."""
    seen: set[str] = set()
    result: list[str] = []
    for u in urls:
        norm = normalize_url(u)
        if norm and norm not in seen:
            seen.add(norm)
            result.append(norm)
    return sorted(result)


def deduplicate_subdomains(subdomains: list[str]) -> list[str]:
    """Return sorted unique normalized subdomains."""
    seen: set[str] = set()
    result: list[str] = []
    for s in subdomains:
        norm = normalize_domain(s)
        if norm and norm not in seen:
            seen.add(norm)
            result.append(norm)
    return sorted(result)


def deduplicate_ports(ports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate ports by (port_int, service) key, preserving first occurrence."""
    seen: set[tuple[int, str]] = set()
    result: list[dict[str, Any]] = []
    for p in ports:
        if not isinstance(p, dict):
            continue
        try:
            port_int = int(p.get("port", 0))
        except (TypeError, ValueError):
            continue
        service = str(p.get("service", "")).strip().lower()
        key = (port_int, service)
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result
