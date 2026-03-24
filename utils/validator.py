from __future__ import annotations

import ipaddress
import re
from pathlib import Path
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


def load_target_file(path: str) -> list[str]:
    """
    Read a target file (one target per line) and return a list of valid targets.

    Lines starting with '#' are treated as comments and skipped.
    Empty lines are skipped.
    Invalid targets are skipped with a warning printed to stderr.

    Returns:
        list[str]: Validated, deduplicated targets in file order.
    """
    import sys

    file_path = Path(path)
    if not file_path.exists():
        print(f"[error] Target file not found: {path}", file=sys.stderr)
        return []
    if not file_path.is_file():
        print(f"[error] Target file path is not a file: {path}", file=sys.stderr)
        return []

    targets: list[str] = []
    seen: set[str] = set()

    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        print(f"[error] Cannot read target file: {exc}", file=sys.stderr)
        return []

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not validate_target(line):
            print(f"[warn] Skipping invalid target in file: '{line}'", file=sys.stderr)
            continue
        if line not in seen:
            seen.add(line)
            targets.append(line)

    return targets

