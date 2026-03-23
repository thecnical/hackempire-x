from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from rich.console import Console


class Logger:
    """
    Production-friendly logger wrapper for HackEmpire X.

    - Colored console output via Rich
    - Timestamped file output to logs/hackempire.log
    - Level helpers: info, success, warning, error
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

        # Avoid duplicate handlers if Logger is constructed multiple times.
        if not any(
            isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == str(self._log_file)
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

    def _print(self, level_tag: str, message: str, *, style: str) -> None:
        self._console.print(f"[{level_tag}] {message}", style=style)

    def _log(self, py_level: int, level_tag: str, message: str) -> None:
        # File logs keep the same tag format as the console output.
        self._logger.log(py_level, f"[{level_tag}] {message}")

    def info(self, message: str) -> None:
        self._print("INFO", message, style="bold cyan")
        self._log(logging.INFO, "INFO", message)

    def success(self, message: str) -> None:
        self._print("SUCCESS", message, style="bold green")
        self._log(logging.INFO, "SUCCESS", message)

    def warning(self, message: str) -> None:
        self._print("WARNING", message, style="bold yellow")
        self._log(logging.WARNING, "WARNING", message)

    def error(self, message: str, *, exc: Optional[BaseException] = None) -> None:
        if exc is not None:
            full_message = f"{message} | {exc.__class__.__name__}: {exc}"
        else:
            full_message = message
        self._console.print(f"[ERROR] {full_message}", style="bold red")
        self._log(logging.ERROR, "ERROR", full_message)

