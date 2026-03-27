from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _load_bytez_key() -> Optional[str]:
    """
    Load Bytez API key from ~/.hackempire/config.json first,
    then fall back to BYTEZ_API_KEY environment variable.
    Returns None when both are absent — never raises.
    """
    try:
        config_file = Path.home() / ".hackempire" / "config.json"
        if config_file.exists():
            data = json.loads(config_file.read_text(encoding="utf-8"))
            key = data.get("bytez_key") or data.get("bytez_api_key")
            if key:
                return str(key)
    except Exception:
        pass
    return os.environ.get("BYTEZ_API_KEY") or None


@dataclass(frozen=True, slots=True)
class Config:
    """
    Immutable runtime configuration for HackEmpire X v4.
    """

    target: str
    mode: str
    ai_key: Optional[str]           # OpenRouter key (backward compat)
    web_enabled: bool
    proxy: Optional[str] = None
    target_file: Optional[str] = None
    # v4.1 — Bytez API key (auto-loaded from config file / env var)
    bytez_key: Optional[str] = None
    # v4.2 — Autonomous mode flag
    autonomous: bool = False

    @classmethod
    def create(
        cls,
        target: str,
        mode: str,
        ai_key: Optional[str] = None,
        web_enabled: bool = False,
        proxy: Optional[str] = None,
        target_file: Optional[str] = None,
        autonomous: bool = False,
    ) -> "Config":
        """
        Factory method that auto-loads bytez_key from config/env.
        Use this instead of direct constructor when possible.
        """
        bytez_key = _load_bytez_key()
        # ultra mode always enables autonomous
        if mode == "ultra":
            autonomous = True
        return cls(
            target=target,
            mode=mode,
            ai_key=ai_key,
            web_enabled=web_enabled,
            proxy=proxy,
            target_file=target_file,
            bytez_key=bytez_key,
            autonomous=autonomous,
        )
