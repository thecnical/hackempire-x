from __future__ import annotations

import ipaddress
import re
from typing import Final


_LABEL_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)$"
)


def _is_valid_domain(domain: str) -> bool:
    # Strip a trailing dot (FQDN format).
    if domain.endswith("."):
        domain = domain[:-1]

    if not domain or len(domain) > 253:
        return False

    # No schemes, paths, or whitespace.
    if any(ch.isspace() for ch in domain):
        return False
    lowered = domain.lower()
    if "://" in lowered or "/" in lowered or "\\" in lowered or "@" in lowered:
        return False

    labels = lowered.split(".")
    return all(_LABEL_RE.match(label) for label in labels)


def validate_target(target: str) -> bool:
    """
    Validate a target as either a domain name or an IP address.

    Returns:
        bool: True if valid, False otherwise.
    """

    if target is None:
        return False

    candidate = target.strip()
    if not candidate:
        return False

    # Reject obvious non-target formats early.
    lowered = candidate.lower()
    if any(x in lowered for x in ("http://", "https://")):
        return False
    if any(x in candidate for x in ("/", "\\", "@")):
        return False

    # IP validation.
    try:
        ipaddress.ip_address(candidate)
        return True
    except ValueError:
        pass

    # Domain validation.
    return _is_valid_domain(candidate)

