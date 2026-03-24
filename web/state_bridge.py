from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any

# Resolved relative to this file: hackempire/web/ → hackempire/logs/
_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = _ROOT / "logs" / "scan_state.json"

_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Writer side (called from CLI / Orchestrator)
# ---------------------------------------------------------------------------

def write_state(
    *,
    target: str,
    mode: str,
    current_phase: str,
    data: dict[str, Any],
    tool_health: dict[str, str],
    todo_list: Any = None,
    ai_decisions: Any = None,
    waf_result: Any = None,
) -> None:
    """Persist the current scan state to disk atomically."""
    payload: dict[str, Any] = {
        "target": target,
        "mode": mode,
        "current_phase": current_phase,
        "data": data,
        "tool_health": tool_health,
        "todo_list": todo_list,
        "ai_decisions": ai_decisions if ai_decisions is not None else {},
        "waf_result": waf_result,
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    with _lock:
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp.replace(STATE_FILE)


# ---------------------------------------------------------------------------
# Reader side (called from Flask routes)
# ---------------------------------------------------------------------------

_EMPTY_TEMPLATE: dict[str, Any] = {
    "target": "",
    "mode": "",
    "current_phase": "",
    "data": {"recon": {}, "enum": {}, "vuln": {}},
    "tool_health": {},
    "todo_list": None,
    "ai_decisions": {},
    "waf_result": None,
}


def read_state() -> dict[str, Any]:
    """Read the latest scan state from disk. Returns a fresh empty skeleton if missing."""
    with _lock:
        if not STATE_FILE.exists():
            return copy.deepcopy(_EMPTY_TEMPLATE)
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return copy.deepcopy(_EMPTY_TEMPLATE)
