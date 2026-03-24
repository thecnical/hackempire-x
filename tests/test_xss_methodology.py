"""
Property-based tests for XSSMethodology deduplication.

Property 15: XSSMethodology Deduplicates Findings
  - run() returns no duplicate Vulnerability objects (keyed on name, url, severity)
  **Validates: Requirements 11.6**
"""

import sys
import os
from unittest.mock import patch, MagicMock

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)      # hackempire/
_parent = os.path.dirname(_pkg_root)    # repo root (contains hackempire/)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.core.models import Vulnerability
from hackempire.tools.methodology.xss_methodology import XSSMethodology

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

VALID_SEVERITIES = ["info", "low", "medium", "high", "critical"]

# Constrained text to keep keys realistic and avoid degenerate cases
_name_st = st.sampled_from(["Reflected XSS", "Stored XSS", "DOM XSS", "Blind XSS", "CSP Bypass"])
_url_st = st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="/:.-_"), min_size=1, max_size=80)
_severity_st = st.sampled_from(VALID_SEVERITIES)

_vulnerability_st = st.builds(
    Vulnerability,
    name=_name_st,
    severity=_severity_st,
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    target=st.text(min_size=1, max_size=80),
    url=_url_st,
    evidence=st.text(max_size=200),
    tool_sources=st.lists(st.sampled_from(["dalfox", "xsstrike", "nuclei", "jsluice"]), max_size=4),
)


# ---------------------------------------------------------------------------
# Property 15: XSSMethodology Deduplicates Findings
# ---------------------------------------------------------------------------

@given(findings=st.lists(_vulnerability_st, min_size=0, max_size=50))
@settings(max_examples=300)
def test_property_15_deduplicate_no_duplicates(findings: list[Vulnerability]) -> None:
    """Property 15: XSSMethodology Deduplicates Findings — _deduplicate() returns no
    duplicate (name, url, severity) tuples for any input list.

    **Validates: Requirements 11.6**
    """
    methodology = XSSMethodology()
    result = methodology._deduplicate(findings)

    keys = [(v.name, v.url, v.severity) for v in result]
    assert len(keys) == len(set(keys)), (
        f"Duplicate keys found in deduplicated result: "
        f"{[k for k in keys if keys.count(k) > 1]}"
    )


@given(findings=st.lists(_vulnerability_st, min_size=0, max_size=50))
@settings(max_examples=200)
def test_property_15_deduplicate_subset_of_input(findings: list[Vulnerability]) -> None:
    """Deduplication only removes entries — every result key was present in the input.

    **Validates: Requirements 11.6**
    """
    methodology = XSSMethodology()
    result = methodology._deduplicate(findings)

    input_keys = {(v.name, v.url, v.severity) for v in findings}
    result_keys = {(v.name, v.url, v.severity) for v in result}
    assert result_keys <= input_keys, (
        "Result contains keys not present in input"
    )


# ---------------------------------------------------------------------------
# Example-based test: run() returns no duplicates when tools produce duplicates
# ---------------------------------------------------------------------------

def _make_dalfox_output(url: str, lines: list[str]) -> MagicMock:
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = "\n".join(lines)
    return mock


def test_run_deduplicates_when_tools_produce_same_finding() -> None:
    """run() deduplicates when dalfox and xsstrike both report the same URL/severity.

    **Validates: Requirements 11.6**
    """
    target = "http://example.com"
    urls = ["http://example.com/search?q=1"]

    # Both dalfox and xsstrike will emit a line that produces a Reflected XSS finding
    dalfox_mock = MagicMock()
    dalfox_mock.returncode = 0
    dalfox_mock.stdout = "XSS found at param q"

    xsstrike_mock = MagicMock()
    xsstrike_mock.returncode = 0
    xsstrike_mock.stdout = "[+] XSS found"

    with patch("hackempire.tools.methodology.xss_methodology.subprocess.run") as mock_run:
        mock_run.side_effect = [dalfox_mock, xsstrike_mock]
        methodology = XSSMethodology()
        result = methodology.run(target, urls)

    keys = [(v.name, v.url, v.severity) for v in result]
    assert len(keys) == len(set(keys)), (
        f"run() returned duplicate findings: {[k for k in keys if keys.count(k) > 1]}"
    )


def test_run_merges_tool_sources_on_duplicate() -> None:
    """When two tools find the same (name, url, severity), tool_sources are merged.

    **Validates: Requirements 11.6**
    """
    target = "http://example.com"
    urls = ["http://example.com/page"]

    dalfox_mock = MagicMock()
    dalfox_mock.returncode = 0
    dalfox_mock.stdout = "XSS found"

    xsstrike_mock = MagicMock()
    xsstrike_mock.returncode = 0
    xsstrike_mock.stdout = "[+] XSS found"

    with patch("hackempire.tools.methodology.xss_methodology.subprocess.run") as mock_run:
        mock_run.side_effect = [dalfox_mock, xsstrike_mock]
        methodology = XSSMethodology()
        result = methodology.run(target, urls)

    # Both tools report Reflected XSS on the same URL — should be merged into one entry
    reflected = [v for v in result if v.name == "Reflected XSS"]
    assert len(reflected) == 1, (
        f"Expected 1 merged Reflected XSS finding, got {len(reflected)}"
    )
    assert "dalfox" in reflected[0].tool_sources
    assert "xsstrike" in reflected[0].tool_sources


def test_deduplicate_empty_list() -> None:
    """_deduplicate([]) returns an empty list."""
    methodology = XSSMethodology()
    assert methodology._deduplicate([]) == []


def test_deduplicate_no_duplicates_unchanged_count() -> None:
    """_deduplicate with all-unique keys preserves all entries."""
    methodology = XSSMethodology()
    findings = [
        Vulnerability(name="Reflected XSS", severity="high", confidence=0.8,
                      target="t", url="http://a.com", tool_sources=["dalfox"]),
        Vulnerability(name="DOM XSS", severity="medium", confidence=0.7,
                      target="t", url="http://a.com", tool_sources=["jsluice"]),
        Vulnerability(name="Reflected XSS", severity="high", confidence=0.8,
                      target="t", url="http://b.com", tool_sources=["dalfox"]),
    ]
    result = methodology._deduplicate(findings)
    assert len(result) == 3
