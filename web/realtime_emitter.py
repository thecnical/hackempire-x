"""
RealTimeEmitter — wraps flask-socketio to broadcast live scan events to the web UI.

All emit methods are fire-and-forget: exceptions are caught, logged, and never
propagated to the caller.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class RealTimeEmitter:
    """Thin wrapper around a flask_socketio.SocketIO instance.

    Parameters
    ----------
    socketio:
        A ``flask_socketio.SocketIO`` instance, or ``None`` / a mock object.
        When ``None`` is passed every emit call is a no-op (logged at DEBUG level).
    """

    def __init__(self, socketio: Any) -> None:
        self._socketio = socketio

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _emit(self, event: str, payload: dict) -> None:
        """Emit *event* with *payload*, swallowing any exception."""
        if self._socketio is None:
            logger.debug("RealTimeEmitter: socketio is None, skipping emit '%s'", event)
            return
        try:
            self._socketio.emit(event, payload)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "RealTimeEmitter: failed to emit event '%s': %s",
                event,
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Public emit methods
    # ------------------------------------------------------------------

    def emit_tool_start(self, phase: str, tool: str, target: str) -> None:
        """Broadcast that a tool has started running."""
        self._emit(
            "tool_start",
            {
                "event": "tool_start",
                "timestamp": _now_iso(),
                "phase": phase,
                "tool": tool,
                "target": target,
            },
        )

    def emit_tool_result(self, phase: str, tool: str, result: dict) -> None:
        """Broadcast the result produced by a tool."""
        self._emit(
            "tool_result",
            {
                "event": "tool_result",
                "timestamp": _now_iso(),
                "phase": phase,
                "tool": tool,
                "result": result,
            },
        )

    def emit_tool_error(self, phase: str, tool: str, error: str) -> None:
        """Broadcast that a tool encountered an error."""
        self._emit(
            "tool_error",
            {
                "event": "tool_error",
                "timestamp": _now_iso(),
                "phase": phase,
                "tool": tool,
                "error": error,
            },
        )

    def emit_phase_complete(self, phase: str, result: Any) -> None:
        """Broadcast that a scan phase has completed."""
        self._emit(
            "phase_complete",
            {
                "event": "phase_complete",
                "timestamp": _now_iso(),
                "phase": phase,
                "result": result,
            },
        )

    def emit_todo_update(self, todo: Any) -> None:
        """Broadcast an updated todo-list state."""
        self._emit(
            "todo_update",
            {
                "event": "todo_update",
                "timestamp": _now_iso(),
                "todo": todo,
            },
        )

    def emit_scan_complete(self, report: Any) -> None:
        """Broadcast that the full scan has completed."""
        self._emit(
            "scan_complete",
            {
                "event": "scan_complete",
                "timestamp": _now_iso(),
                "report": report,
            },
        )

    def emit_vuln_found(self, vuln: Any) -> None:
        """Broadcast that a vulnerability was discovered."""
        self._emit(
            "vuln_found",
            {
                "event": "vuln_found",
                "timestamp": _now_iso(),
                "vuln": vuln,
            },
        )

    def emit_terminal_output(self, data: str) -> None:
        """Broadcast a line of terminal / tool output."""
        self._emit(
            "terminal_output",
            {
                "event": "terminal_output",
                "timestamp": _now_iso(),
                "data": data,
            },
        )
