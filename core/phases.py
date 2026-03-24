from __future__ import annotations

from enum import Enum


class Phase(Enum):
    RECON = "recon"
    URL_DISCOVERY = "url_discovery"
    ENUMERATION = "enumeration"
    VULN_SCAN = "vuln_scan"
    EXPLOITATION = "exploitation"
    POST_EXPLOIT = "post_exploit"
    REPORTING = "reporting"
    # Legacy aliases kept for backward compatibility
    ENUM = "enum"
    VULN = "vuln"

