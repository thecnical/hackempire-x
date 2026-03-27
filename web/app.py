"""
HackEmpire X — Flask Web GUI entry point.

Start standalone:
    python web/app.py

Or launched automatically by CLI with --web flag.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Ensure hackempire root is on sys.path when run directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from flask import Flask
from web.routes import bp
from web.tls_manager import ensure_tls_cert

_log = logging.getLogger(__name__)

try:
    from flask_socketio import SocketIO
    _SOCKETIO_AVAILABLE = True
except ImportError:
    _SOCKETIO_AVAILABLE = False
    SocketIO = None  # type: ignore[assignment,misc]


def create_app() -> Flask:
    template_dir = Path(__file__).resolve().parent / "templates"
    static_dir = Path(__file__).resolve().parent / "static"
    app = Flask(__name__, template_folder=str(template_dir),
                static_folder=str(static_dir))
    app.config["SECRET_KEY"] = os.environ.get("HACKEMPIRE_SECRET_KEY", "hackempire-dev-key")
    app.register_blueprint(bp)

    if _SOCKETIO_AVAILABLE:
        socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode="threading",
            logger=False,
            engineio_logger=False,
        )
        app.extensions["socketio"] = socketio
        _register_socketio_handlers(socketio)

    return app


def _register_socketio_handlers(socketio: "SocketIO") -> None:
    """Register SocketIO event handlers for terminal I/O."""
    from web.terminal_launcher import TerminalLauncher

    terminal_launcher = TerminalLauncher(socketio=socketio)

    @socketio.on("terminal_input")
    def handle_terminal_input(data: dict) -> None:
        session_id = data.get("session_id", "")
        input_data = data.get("data", "")
        terminal_launcher.write(session_id, input_data)

    @socketio.on("terminal_resize")
    def handle_terminal_resize(data: dict) -> None:
        session_id = data.get("session_id", "")
        rows = int(data.get("rows", 24))
        cols = int(data.get("cols", 80))
        terminal_launcher.resize(session_id, rows, cols)


def run_server(host: str = "127.0.0.1", port: int = 5443, debug: bool = False) -> None:
    import socket as _socket

    # Check if port is already in use — if so, skip starting a new server
    def _port_in_use(p: int) -> bool:
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, p))
                return False
            except OSError:
                return True

    if _port_in_use(port):
        _log.warning("Port %d already in use — dashboard already running at https://%s:%d/dashboard", port, host, port)
        return

    app = create_app()
    socketio = app.extensions.get("socketio") if _SOCKETIO_AVAILABLE else None

    # Try TLS first, fall back to plain HTTP
    ssl_ctx = None
    try:
        cert_path, key_path = ensure_tls_cert()
        ssl_ctx = (cert_path, key_path)
    except Exception as exc:
        _log.warning("TLS cert unavailable, using HTTP: %s", exc)

    try:
        if socketio is not None:
            socketio.run(
                app, host=host, port=port, debug=debug,
                use_reloader=False, allow_unsafe_werkzeug=True,
                ssl_context=ssl_ctx,
            )
        else:
            app.run(
                host=host, port=port, debug=debug,
                use_reloader=False, ssl_context=ssl_ctx,
            )
    except Exception as exc:
        _log.warning("Server on port %d failed (%s), trying HTTP on port 5000", port, exc)
        try:
            if not _port_in_use(5000):
                if socketio is not None:
                    socketio.run(app, host=host, port=5000, debug=debug,
                                 use_reloader=False, allow_unsafe_werkzeug=True)
                else:
                    app.run(host=host, port=5000, debug=debug, use_reloader=False)
        except Exception as exc2:
            _log.error("Web server failed to start: %s", exc2)


if __name__ == "__main__":
    run_server(debug=True)
