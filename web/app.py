"""
HackEmpire X — Flask Web GUI entry point.

Start standalone:
    python web/app.py

Or launched automatically by CLI with --web flag.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure hackempire root is on sys.path when run directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from flask import Flask
from web.routes import bp


def create_app() -> Flask:
    template_dir = Path(__file__).resolve().parent / "templates"
    app = Flask(__name__, template_folder=str(template_dir))
    app.config["SECRET_KEY"] = os.environ.get("HACKEMPIRE_SECRET_KEY", "hackempire-dev-key")
    app.register_blueprint(bp)
    return app


def run_server(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    app = create_app()
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    run_server(debug=True)
