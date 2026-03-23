from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class Config:
    """
    Immutable runtime configuration for HackEmpire X (Phase 1).
    """

    target: str
    mode: str
    ai_key: Optional[str]
    web_enabled: bool

