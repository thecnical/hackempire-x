from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True, slots=True)
class Config:
    """
    Immutable runtime configuration for HackEmpire X.
    """

    target: str
    mode: str
    ai_key: Optional[str]
    web_enabled: bool
    # Proxy URL for all tool HTTP traffic, e.g. "http://127.0.0.1:8080" (Burp)
    proxy: Optional[str] = None
    # Path to a file containing one target per line (multi-target mode)
    target_file: Optional[str] = None

