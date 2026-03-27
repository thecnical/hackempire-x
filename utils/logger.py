"""
Logger — HackEmpire X v4 logging wrapper.

- Rich colored console output
- Timestamped file output to logs/hackempire.log
- Structured log levels: info, success, warning, error, debug
- v4: scan_event() for structured scan lifecycle events
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


class Logger:
    """
    Production-friendly logger wrapper for HackEmpire X.

    - Colored console output via Rich
    - Timestamped file output to logs/hackempire.log
    - Level helpers: info, success, warning, error, debug
    - v4: scan_event() for structured scan lifecycle events
    """

    def __init__(
        self,
        *,
        log_file: Optional[Path] = None,
        name: str = "hackempire",
        console: Optional[Console] = None,
    ) -> None:
        self._console = console or Console()

        root_dir = Path(__file__).resolve().parent.parent
        logs_dir = root_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        self._log_file = log_file or (logs_dir / "hackempire.log")

        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        # Avoid duplicate handlers if Logger is constructed multiple times
        if not any(
            isinstance(h, logging.FileHandler)
            and getattr(h, "baseFilename", None) == str(self._log_file)
            for h in self._logger.handlers
        ):
            file_handler = logging.FileHandler(self._log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            self._logger.addHandler(file_handler)

    # ------------------------------------------------------------------
    # Core log methods
    # ------------------------------------------------------------------

    def _print(self, level_tag: str, message: str, *, style: str) -> None:
        self._console.print(f"[{level_tag}] {message}", style=style)

    def _log(self, py_level: int, level_tag: str, message: str) -> None:
        self._logger.log(py_level, f"[{level_tag}] {message}")

    def debug(self, message: str) -> None:
        self._log(logging.DEBUG, "DEBUG", message)

    def info(self, message: str, *args: object) -> None:
        if args:
            try:
                message = message % args
            except Exception:
                message = " ".join([message] + [str(a) for a in args])
        self._print("INFO", message, style="bold cyan")
        self._log(logging.INFO, "INFO", message)

    def success(self, message: str) -> None:
        self._print("SUCCESS", message, style="bold green")
        self._log(logging.INFO, "SUCCESS", message)

    def warning(self, message: str, *args: object) -> None:
        # Support both f-string style and % format style calls
        if args:
            try:
                message = message % args
            except Exception:
                message = " ".join([message] + [str(a) for a in args])
        self._print("WARNING", message, style="bold yellow")
        self._log(logging.WARNING, "WARNING", message)

    def error(self, message: str, *, exc: Optional[BaseException] = None) -> None:
        if exc is not None:
            full_message = f"{message} | {exc.__class__.__name__}: {exc}"
        else:
            full_message = message
        self._console.print(f"[ERROR] {full_message}", style="bold red")
        self._log(logging.ERROR, "ERROR", full_message)

    # ------------------------------------------------------------------
    # v4: structured scan lifecycle event logging
    # ------------------------------------------------------------------

    def scan_event(self, event: str, **kwargs: object) -> None:
        """
        Log a structured scan lifecycle event.

        Examples:
            logger.scan_event("phase_start", phase="recon", target="example.com")
            logger.scan_event("tool_result", tool="nmap", findings=3)
            logger.scan_event("autonomous_decision", action="switch_tool", reason="timeout")
            logger.scan_event("kb_write", domain="example.com", findings=5)
        """
        parts = [f"{k}={v!r}" for k, v in kwargs.items()]
        msg = f"[SCAN_EVENT] {event}" + (f" | {', '.join(parts)}" if parts else "")
        self._console.print(msg, style="dim white")
        self._log(logging.INFO, "SCAN_EVENT", msg)

    def phase_start(self, phase: str, target: str) -> None:
        self.scan_event("phase_start", phase=phase, target=target)

    def phase_complete(self, phase: str, succeeded: bool, findings: int = 0) -> None:
        self.scan_event("phase_complete", phase=phase, succeeded=succeeded, findings=findings)

    def tool_run(self, tool: str, phase: str, status: str) -> None:
        self.scan_event("tool_run", tool=tool, phase=phase, status=status)

    def autonomous_decision(self, action: str, phase: str, reason: str) -> None:
        self.scan_event("autonomous_decision", action=action, phase=phase, reason=reason)

    def kb_event(self, event: str, domain: str, **kwargs: object) -> None:
        self.scan_event(f"kb_{event}", domain=domain, **kwargs)
