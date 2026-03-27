"""
KnowledgeBaseManager — RAG-style persistent knowledge base for HackEmpire X v4.

Stores scan results to ~/.hackempire/kb/{domain}/entries.jsonl.
On next scan, AI queries KB for prior findings to make smarter decisions.

Features:
- Write KBEntry records (deduplicated by target+finding+url hash)
- Search by domain or CIDR prefix
- Append working payloads immediately when confirmed
- Thread-safe file append
- Zero cost — plain JSON files, no database
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Optional

from hackempire.core.models import KBEntry

logger = logging.getLogger(__name__)

KB_ROOT = Path.home() / ".hackempire" / "kb"

# Thread lock for concurrent write safety
_write_lock = threading.Lock()


def _domain_from_target(target: str) -> str:
    """Extract domain from target string (strips scheme, port, path)."""
    target = target.strip().lower()
    # Remove scheme
    for scheme in ("https://", "http://", "ftp://"):
        if target.startswith(scheme):
            target = target[len(scheme):]
    # Remove path and port
    target = target.split("/")[0].split(":")[0]
    return target or "unknown"


def _finding_hash(target: str, finding_name: str, url: str, severity: str = "") -> str:
    """Stable hash for deduplication: (target, finding_name, url, severity)."""
    key = f"{target}|{finding_name}|{url}|{severity}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class KnowledgeBaseManager:
    """
    Manages the RAG Knowledge Base at ~/.hackempire/kb/.

    Usage:
        kb = KnowledgeBaseManager()
        kb.write(entry)
        results = kb.search("example.com")
        kb.append_payload("example.com", "' OR 1=1--")
    """

    def __init__(self, kb_root: Optional[Path] = None) -> None:
        self._root = kb_root or KB_ROOT

    # ── Public API ────────────────────────────────────────────────────────

    def write(self, entry: KBEntry) -> None:
        """
        Write a KBEntry to ~/.hackempire/kb/{domain}/entries.jsonl.
        Deduplicates findings by (target, finding_name, url) hash.
        Never raises — logs and returns on any error.
        """
        try:
            domain = _domain_from_target(entry.target)
            entry_dir = self._root / domain
            entry_dir.mkdir(parents=True, exist_ok=True)
            entries_file = entry_dir / "entries.jsonl"

            # Load existing hashes and data for deduplication
            existing_hashes, existing_payloads, existing_attack_patterns, existing_name_url = self._load_existing(entries_file)

            # Deduplicate findings — use (name, url) as the unique key (severity ignored)
            new_findings = []
            seen_name_url: set[tuple[str, str]] = set()
            for finding in entry.findings:
                name = finding.get("name", "")
                url = finding.get("url", "")
                severity = finding.get("severity", "")
                name_url_key = (name, url)
                h = _finding_hash(entry.target, name, url, severity)
                if name_url_key not in seen_name_url and name_url_key not in existing_name_url and h not in existing_hashes:
                    new_findings.append(finding)
                    existing_hashes.add(h)
                    seen_name_url.add(name_url_key)

            # Deduplicate payloads and attack_patterns
            new_payloads = [p for p in entry.payloads if p not in existing_payloads]
            new_attack_patterns = [ap for ap in entry.attack_patterns if ap not in existing_attack_patterns]

            if not new_findings and not new_payloads and not new_attack_patterns:
                logger.debug("[kb] No new data to write for %s", domain)
                return

            # Write deduplicated entry
            write_entry = KBEntry(
                target=entry.target,
                findings=new_findings,
                payloads=new_payloads,
                attack_patterns=new_attack_patterns,
                timestamp=entry.timestamp,
            )

            with _write_lock:
                with entries_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(write_entry.to_dict(), ensure_ascii=False) + "\n")

            logger.info("[kb] Wrote %d findings for %s", len(new_findings), domain)

        except Exception as exc:
            logger.warning("[kb] Write failed for %s: %s", entry.target, exc)

    def search(self, domain_or_cidr: str) -> list[KBEntry]:
        """
        Return all KBEntry records whose target matches the given domain.
        Returns [] on any I/O error.
        """
        try:
            domain = _domain_from_target(domain_or_cidr)
            entries_file = self._root / domain / "entries.jsonl"

            if not entries_file.exists():
                return []

            results: list[KBEntry] = []
            with entries_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        results.append(KBEntry.from_dict(data))
                    except (json.JSONDecodeError, KeyError):
                        continue

            logger.debug("[kb] Found %d entries for %s", len(results), domain)
            return results

        except Exception as exc:
            logger.warning("[kb] Search failed for %s: %s", domain_or_cidr, exc)
            return []

    def append_payload(self, domain: str, payload: str) -> None:
        """
        Immediately append a confirmed working payload to the KB.
        Called when a payload is confirmed during EXPLOITATION or POST_EXPLOIT.
        Never raises.
        """
        try:
            clean_domain = _domain_from_target(domain)
            entry_dir = self._root / clean_domain
            entry_dir.mkdir(parents=True, exist_ok=True)
            payload_file = entry_dir / "payloads.txt"

            with _write_lock:
                with payload_file.open("a", encoding="utf-8") as f:
                    f.write(payload + "\n")

            logger.info("[kb] Appended payload for %s", clean_domain)

        except Exception as exc:
            logger.warning("[kb] append_payload failed for %s: %s", domain, exc)

    def get_context_for_ai(self, target: str) -> str:
        """
        Build a concise context string from KB entries for injection into AI prompts.
        Returns empty string if no prior data exists.
        """
        entries = self.search(target)
        if not entries:
            return ""

        lines = [f"Prior scan data for {target}:"]
        for entry in entries[-3:]:  # last 3 scans max
            if entry.findings:
                for f in entry.findings[:5]:  # top 5 findings
                    name = f.get("name", "unknown")
                    url = f.get("url", "")
                    sev = f.get("severity", "")
                    lines.append(f"  - {name} ({sev}) at {url}")
            if entry.payloads:
                lines.append(f"  Working payloads: {', '.join(entry.payloads[:3])}")

        return "\n".join(lines)

    # ── Internal ─────────────────────────────────────────────────────────

    def _load_existing(self, entries_file: Path) -> tuple[set[str], set[str], set[str], set[tuple[str, str]]]:
        """Load existing finding hashes, payloads, attack_patterns, and (name,url) keys for deduplication."""
        hashes: set[str] = set()
        payloads: set[str] = set()
        attack_patterns: set[str] = set()
        name_url_keys: set[tuple[str, str]] = set()
        if not entries_file.exists():
            return hashes, payloads, attack_patterns, name_url_keys
        try:
            with entries_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        target = data.get("target", "")
                        for finding in data.get("findings", []):
                            name = finding.get("name", "")
                            url = finding.get("url", "")
                            h = _finding_hash(target, name, url, finding.get("severity", ""))
                            hashes.add(h)
                            name_url_keys.add((name, url))
                        payloads.update(data.get("payloads", []))
                        attack_patterns.update(data.get("attack_patterns", []))
                    except (json.JSONDecodeError, KeyError):
                        continue
        except Exception:
            pass
        return hashes, payloads, attack_patterns, name_url_keys
