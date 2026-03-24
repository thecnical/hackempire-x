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


_PRIVATE_IP_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|127\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|::1"
    r"|localhost)$",
    re.IGNORECASE,
)

_SHELL_METACHAR_RE: Final[re.Pattern[str]] = re.compile(r"[;|&$`\n\r\x00]")

_HTML_ESCAPE_TABLE: Final[dict[str, str]] = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#x27;",
}


def sanitize_for_html(value: str) -> str:
    """Escape HTML special characters to prevent XSS in generated reports."""
    for char, escaped in _HTML_ESCAPE_TABLE.items():
        value = value.replace(char, escaped)
    return value


def sanitize_for_shell(value: str) -> str:
    """Raise ValueError if value contains shell metacharacters.

    Prevents shell injection when values are used in subprocess arguments.
    """
    if _SHELL_METACHAR_RE.search(value):
        raise ValueError(f"Value contains disallowed shell metacharacters: {value!r}")
    return value


def validate_target_strict(target: str) -> bool:
    """Validate target like validate_target() but additionally reject private/loopback addresses.

    For use in production mode where scanning internal infrastructure is not permitted.
    Rejects: 10.x, 172.16-31.x, 192.168.x, 127.x, ::1, localhost.
    """
    if not validate_target(target):
        return False
    candidate = target.strip()
    if _PRIVATE_IP_RE.match(candidate):
        return False
    return True


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

