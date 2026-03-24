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
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
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
    app = create_app()
    socketio = app.extensions.get("socketio") if _SOCKETIO_AVAILABLE else None
    try:
        cert_path, key_path = ensure_tls_cert()
        if socketio is not None:
            socketio.run(app, host=host, port=port, debug=debug, use_reloader=False,
                         ssl_context=(cert_path, key_path))
        else:
            app.run(host=host, port=port, debug=debug, use_reloader=False,
                    ssl_context=(cert_path, key_path))
    except RuntimeError as exc:
        _log.warning("TLS setup failed, falling back to HTTP on port 5000: %s", exc)
        if socketio is not None:
            socketio.run(app, host=host, port=5000, debug=debug, use_reloader=False)
        else:
            app.run(host=host, port=5000, debug=debug, use_reloader=False)


if __name__ == "__main__":
    run_server(debug=True)
