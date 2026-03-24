"""
TerminalLauncher — spawns PTY-backed /bin/bash sessions for the web terminal.

Each session gets a unique session_id (UUID4). stdout/stderr are streamed to
the SocketIO channel ``terminal_output`` in a dedicated daemon thread.

On platforms where ``pty`` is unavailable (e.g. Windows) or when
``pty.openpty()`` fails, ``launch()`` returns ``None`` so the scan continues
normally with the terminal feature disabled.

Bind PTY WebSocket only to 127.0.0.1 (enforced at the Flask/SocketIO layer).
"""
from __future__ import annotations

import logging
import os
import shutil
import struct
import subprocess
import threading
import uuid
from dataclasses import dataclass
from typing import Any

try:
    import fcntl
    import termios
    _UNIX_AVAILABLE = True
except ImportError:
    _UNIX_AVAILABLE = False

logger = logging.getLogger(__name__)

_READ_SIZE = 1024


@dataclass
class TerminalSession:
    """Represents a single PTY-backed bash session."""

    session_id: str
    pid: int
    fd: int
    process: subprocess.Popen


class TerminalLauncher:
    """Manages PTY-backed terminal sessions.

    Parameters
    ----------
    socketio:
        Optional ``flask_socketio.SocketIO`` instance used to emit
        ``terminal_output`` events.  Pass ``None`` to disable streaming.
    """

    def __init__(self, socketio: Any = None) -> None:
        self._socketio = socketio
        self._sessions: dict[str, TerminalSession] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def launch(self, tools: list[str]) -> TerminalSession | None:
        """Spawn a PTY-backed ``/bin/bash`` with tool binaries on PATH.

        Parameters
        ----------
        tools:
            List of tool binary names to add to PATH.

        Returns
        -------
        TerminalSession | None
            A new session, or ``None`` if PTY creation fails.
        """
        try:
            import pty  # noqa: PLC0415 — lazy import for Windows compat
        except ImportError:
            logger.warning("TerminalLauncher: pty module not available; terminal disabled")
            return None

        try:
            master_fd, slave_fd = pty.openpty()
        except OSError as exc:
            logger.warning("TerminalLauncher: pty.openpty() failed: %s; terminal disabled", exc)
            return None

        try:
            env = dict(os.environ)
            extra_dirs = [
                os.path.dirname(shutil.which(t))
                for t in tools
                if shutil.which(t)
            ]
            if extra_dirs:
                env["PATH"] = env.get("PATH", "") + ":" + ":".join(extra_dirs)

            proc = subprocess.Popen(
                ["/bin/bash"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                close_fds=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("TerminalLauncher: Popen failed: %s; terminal disabled", exc)
            try:
                os.close(master_fd)
                os.close(slave_fd)
            except OSError:
                pass
            return None

        # slave_fd is now owned by the child process; close our copy
        try:
            os.close(slave_fd)
        except OSError:
            pass

        session = TerminalSession(
            session_id=str(uuid.uuid4()),
            pid=proc.pid,
            fd=master_fd,
            process=proc,
        )

        with self._lock:
            self._sessions[session.session_id] = session

        # Start reader thread
        t = threading.Thread(
            target=self._reader_thread,
            args=(session,),
            daemon=True,
            name=f"terminal-reader-{session.session_id[:8]}",
        )
        t.start()

        return session

    def write(self, session_id: str, data: str) -> None:
        """Write *data* to the PTY stdin of *session_id*."""
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            return
        try:
            os.write(session.fd, data.encode())
        except OSError:
            pass

    def resize(self, session_id: str, rows: int, cols: int) -> None:
        """Resize the PTY window for *session_id*."""
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            return
        if not _UNIX_AVAILABLE:
            return
        try:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(session.fd, termios.TIOCSWINSZ, winsize)  # type: ignore[name-defined]
        except OSError:
            pass

    def kill(self, session_id: str) -> None:
        """Terminate the PTY process for *session_id*."""
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return
        try:
            session.process.terminate()
        except OSError:
            pass
        try:
            os.close(session.fd)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reader_thread(self, session: TerminalSession) -> None:
        """Read from master PTY fd and emit via SocketIO."""
        while True:
            try:
                data = os.read(session.fd, _READ_SIZE)
            except OSError:
                break
            if not data:
                break
            if self._socketio is not None:
                try:
                    self._socketio.emit(
                        "terminal_output",
                        {"session_id": session.session_id, "data": data.decode("utf-8", errors="replace")},
                    )
                except Exception:  # noqa: BLE001
                    pass
