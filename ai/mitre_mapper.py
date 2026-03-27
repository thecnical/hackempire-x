"""
MITRE ATT&CK Mapper — maps vulnerability categories to ATT&CK technique IDs and tactic names.

Used by Dashboard v2 MITREOverlay panel to annotate confirmed findings.
"""
from __future__ import annotations

# Static mapping: vulnerability category keyword → ATT&CK technique
_MITRE_MAP: dict[str, dict[str, str]] = {
    "sqli":               {"technique_id": "T1190",    "tactic": "Initial Access"},
    "sql injection":      {"technique_id": "T1190",    "tactic": "Initial Access"},
    "sql":                {"technique_id": "T1190",    "tactic": "Initial Access"},
    "xss":                {"technique_id": "T1059.007","tactic": "Execution"},
    "cross-site scripting": {"technique_id": "T1059.007", "tactic": "Execution"},
    "rce":                {"technique_id": "T1059",    "tactic": "Execution"},
    "remote code":        {"technique_id": "T1059",    "tactic": "Execution"},
    "command injection":  {"technique_id": "T1059",    "tactic": "Execution"},
    "ssrf":               {"technique_id": "T1090",    "tactic": "Command and Control"},
    "server-side request": {"technique_id": "T1090",   "tactic": "Command and Control"},
    "lfi":                {"technique_id": "T1083",    "tactic": "Discovery"},
    "rfi":                {"technique_id": "T1083",    "tactic": "Discovery"},
    "local file":         {"technique_id": "T1083",    "tactic": "Discovery"},
    "remote file":        {"technique_id": "T1083",    "tactic": "Discovery"},
    "path traversal":     {"technique_id": "T1083",    "tactic": "Discovery"},
    "directory traversal": {"technique_id": "T1083",   "tactic": "Discovery"},
    "ssti":               {"technique_id": "T1059",    "tactic": "Execution"},
    "template injection": {"technique_id": "T1059",    "tactic": "Execution"},
    "xxe":                {"technique_id": "T1005",    "tactic": "Collection"},
    "xml external":       {"technique_id": "T1005",    "tactic": "Collection"},
    "idor":               {"technique_id": "T1078",    "tactic": "Defense Evasion"},
    "insecure direct":    {"technique_id": "T1078",    "tactic": "Defense Evasion"},
    "auth bypass":        {"technique_id": "T1078",    "tactic": "Defense Evasion"},
    "authentication bypass": {"technique_id": "T1078", "tactic": "Defense Evasion"},
    "deserialization":    {"technique_id": "T1059",    "tactic": "Execution"},
    "open redirect":      {"technique_id": "T1566",    "tactic": "Initial Access"},
    "redirect":           {"technique_id": "T1566",    "tactic": "Initial Access"},
    "csrf":               {"technique_id": "T1185",    "tactic": "Collection"},
    "cross-site request": {"technique_id": "T1185",    "tactic": "Collection"},
    "subdomain takeover": {"technique_id": "T1584",    "tactic": "Resource Development"},
    "takeover":           {"technique_id": "T1584",    "tactic": "Resource Development"},
}

# Default when no match is found
_DEFAULT_MAPPING: dict[str, str] = {
    "technique_id": "T1190",
    "tactic": "Initial Access",
}


def map_finding(finding_name: str) -> dict:
    """Return the MITRE ATT&CK technique_id and tactic for a given finding name.

    Performs case-insensitive substring matching against known vulnerability
    categories. Returns a default mapping when no match is found.

    Parameters
    ----------
    finding_name:
        The vulnerability or finding name (e.g. "SQL Injection", "Reflected XSS").

    Returns
    -------
    dict
        ``{"technique_id": "T1190", "tactic": "Initial Access"}``
    """
    lower = finding_name.lower()
    for keyword, mapping in _MITRE_MAP.items():
        if keyword in lower:
            return dict(mapping)
    return dict(_DEFAULT_MAPPING)
