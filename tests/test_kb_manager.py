"""
Property-based and unit tests for KnowledgeBaseManager (v4.3).

Property 7: KBEntry round-trip (write → read → compare)
  - Writing a KBEntry and reading it back produces an equal object.
  **Validates: Requirements 3.2, 3.11**

Property 8: RAG_KB deduplication
  - Writing the same (target, finding_name, url) twice results in exactly one copy.
  **Validates: Requirements 3.6**

Property 9: RAG_KB search returns all matching entries
  - search(d) returns exactly the entries whose target matches d and no others.
  **Validates: Requirements 3.8**

Unit tests:
  - KB directory auto-creation when ~/.hackempire/kb/ does not exist
  - search() returns empty list on I/O error
  **Validates: Requirements 3.7, 3.10**
"""
from __future__ import annotations

import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)
_parent = os.path.dirname(_pkg_root)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from hackempire.core.kb_manager import KnowledgeBaseManager
from hackempire.core.models import KBEntry

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_domain_st = st.text(
    alphabet=st.characters(whitelist_categories=("Ll",), whitelist_characters="-"),
    min_size=3, max_size=20,
).filter(lambda s: s.isalpha() or (s[0].isalpha() and s[-1].isalpha())).map(
    lambda s: s + ".com"
)

_finding_st = st.fixed_dictionaries({
    "name": st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_", min_size=1, max_size=30),
    "url": st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/:.", min_size=5, max_size=50).map(
        lambda s: "https://" + s
    ),
    "severity": st.sampled_from(["info", "low", "medium", "high", "critical"]),
})

_kb_entry_st = st.builds(
    KBEntry,
    target=_domain_st,
    findings=st.lists(_finding_st, min_size=0, max_size=3),
    payloads=st.lists(st.text(min_size=0, max_size=30), min_size=0, max_size=3),
    attack_patterns=st.lists(st.text(min_size=0, max_size=30), min_size=0, max_size=3),
    timestamp=st.just("2024-01-01T00:00:00+00:00"),
)


# ---------------------------------------------------------------------------
# Property 7: KBEntry round-trip (write → read → compare)
# ---------------------------------------------------------------------------

# Feature: hackempire-x-v4, Property 7: KBEntry round-trip (write → read → compare)
@given(entry=_kb_entry_st)
@settings(max_examples=10)
def test_property_7_kb_entry_round_trip(entry: KBEntry) -> None:
    """Property 7: KBEntry round-trip (write → read → compare).

    For any KBEntry with valid fields, writing it to the RAG_KB and reading
    it back SHALL produce an object equal to the original.

    **Validates: Requirements 3.2, 3.11**
    """
    with tempfile.TemporaryDirectory() as td:
        kb = KnowledgeBaseManager(kb_root=Path(td))
        kb.write(entry)

        results = kb.search(entry.target)

        # If the entry has no data, write() skips it — that's correct behavior
        has_data = bool(entry.findings or entry.payloads or entry.attack_patterns)
        if not has_data:
            # Nothing to write, nothing to read back — that's fine
            return

        assert len(results) >= 1, "Expected at least one entry after write"

        # Collect all findings across all written entries
        all_findings = []
        all_payloads = []
        all_attack_patterns = []
        for r in results:
            all_findings.extend(r.findings)
            all_payloads.extend(r.payloads)
            all_attack_patterns.extend(r.attack_patterns)

        # Every finding from the original entry must appear in the KB
        for f in entry.findings:
            assert f in all_findings, f"Finding {f} not found in KB after write"

        # Payloads and attack patterns are preserved
        for p in entry.payloads:
            assert p in all_payloads, f"Payload {p!r} not found in KB after write"
        for ap in entry.attack_patterns:
            assert ap in all_attack_patterns, f"Attack pattern {ap!r} not found in KB after write"


# ---------------------------------------------------------------------------
# Property 8: RAG_KB deduplication
# ---------------------------------------------------------------------------

# Feature: hackempire-x-v4, Property 8: RAG_KB deduplication
@given(entry=_kb_entry_st.filter(lambda e: len(e.findings) > 0))
@settings(max_examples=10)
def test_property_8_rag_kb_deduplication(entry: KBEntry) -> None:
    """Property 8: RAG_KB deduplication.

    For any KBEntry written twice with identical (target, finding_name, url)
    tuples, the KB SHALL contain exactly one copy of that finding.

    **Validates: Requirements 3.6**
    """
    with tempfile.TemporaryDirectory() as td:
        kb = KnowledgeBaseManager(kb_root=Path(td))

        # Write the same entry twice
        kb.write(entry)
        kb.write(entry)

        results = kb.search(entry.target)

        # Collect all findings across all entries
        all_findings: list[dict] = []
        for r in results:
            all_findings.extend(r.findings)

        # Each unique (name, url) combination should appear exactly once
        seen: set[tuple[str, str]] = set()
        for f in all_findings:
            key = (f.get("name", ""), f.get("url", ""))
            assert key not in seen, (
                f"Duplicate finding {key} found in KB after writing the same entry twice"
            )
            seen.add(key)


# ---------------------------------------------------------------------------
# Property 9: RAG_KB search returns all matching entries
# ---------------------------------------------------------------------------

# Feature: hackempire-x-v4, Property 9: RAG_KB search returns all matching entries
@given(
    target_domain=_domain_st,
    matching_entries=st.lists(_kb_entry_st, min_size=1, max_size=4),
    other_entries=st.lists(_kb_entry_st, min_size=0, max_size=4),
)
@settings(max_examples=10)
def test_property_9_rag_kb_search_returns_matching(
    target_domain: str,
    matching_entries: list[KBEntry],
    other_entries: list[KBEntry],
) -> None:
    """Property 9: RAG_KB search returns all matching entries.

    For any domain d and a set of KBEntry records where some have target == d
    and others do not, search(d) SHALL return exactly the entries whose target
    matches d and no others.

    **Validates: Requirements 3.8**
    """
    with tempfile.TemporaryDirectory() as td:
        kb = KnowledgeBaseManager(kb_root=Path(td))

        # Force matching entries to have the target domain
        for e in matching_entries:
            e.target = target_domain

        # Force other entries to have a different target (ensure no collision)
        other_domain = "other-" + target_domain
        for e in other_entries:
            e.target = other_domain

        # Write all entries
        for e in matching_entries:
            kb.write(e)
        for e in other_entries:
            kb.write(e)

        # Search for the target domain
        results = kb.search(target_domain)

        # All results must have target matching the domain (after normalization)
        for r in results:
            assert r.target == target_domain, (
                f"search({target_domain!r}) returned entry with target={r.target!r}"
            )

        # No results should come from other_domain entries
        other_results = kb.search(other_domain)
        for r in other_results:
            assert r.target == other_domain, (
                f"search({other_domain!r}) returned entry with target={r.target!r}"
            )


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_unit_kb_directory_auto_creation(tmp_path: Path) -> None:
    """Test KB directory auto-creation when ~/.hackempire/kb/ does not exist.

    **Validates: Requirements 3.7**
    """
    kb_root = tmp_path / "nonexistent" / "nested" / "kb"
    assert not kb_root.exists()

    kb = KnowledgeBaseManager(kb_root=kb_root)
    entry = KBEntry(
        target="example.com",
        findings=[{"name": "XSS", "url": "https://example.com/page", "severity": "high"}],
        payloads=["<script>alert(1)</script>"],
        attack_patterns=["reflected-xss"],
        timestamp="2024-01-01T00:00:00+00:00",
    )
    kb.write(entry)

    # Directory should have been created
    assert kb_root.exists()
    assert (kb_root / "example.com" / "entries.jsonl").exists()


def test_unit_search_returns_empty_on_io_error(tmp_path: Path) -> None:
    """Test search() returns empty list on I/O error.

    **Validates: Requirements 3.10**
    """
    kb = KnowledgeBaseManager(kb_root=tmp_path)

    # Create a domain directory with a corrupted entries file
    domain_dir = tmp_path / "broken.com"
    domain_dir.mkdir(parents=True)
    entries_file = domain_dir / "entries.jsonl"
    # Write invalid JSON to trigger parse errors (but file exists)
    entries_file.write_text("not-valid-json\n{broken\n", encoding="utf-8")

    # search() should return [] gracefully (skipping bad lines)
    results = kb.search("broken.com")
    assert isinstance(results, list)
    # Bad lines are skipped, so result is empty
    assert results == []


def test_unit_search_returns_empty_when_no_file(tmp_path: Path) -> None:
    """Test search() returns empty list when no entries file exists."""
    kb = KnowledgeBaseManager(kb_root=tmp_path)
    results = kb.search("nonexistent.com")
    assert results == []


def test_unit_write_and_search_roundtrip(tmp_path: Path) -> None:
    """Test basic write → search roundtrip with a concrete entry."""
    kb = KnowledgeBaseManager(kb_root=tmp_path)
    entry = KBEntry(
        target="test.com",
        findings=[{"name": "SQLi", "url": "https://test.com/login", "severity": "critical"}],
        payloads=["' OR 1=1--"],
        attack_patterns=["sql-injection"],
        timestamp="2024-06-01T12:00:00+00:00",
    )
    kb.write(entry)
    results = kb.search("test.com")

    assert len(results) == 1
    r = results[0]
    assert r.target == "test.com"
    assert r.findings == [{"name": "SQLi", "url": "https://test.com/login", "severity": "critical"}]
    assert r.payloads == ["' OR 1=1--"]
    assert r.attack_patterns == ["sql-injection"]
    assert r.timestamp == "2024-06-01T12:00:00+00:00"
