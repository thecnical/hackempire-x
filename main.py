from __future__ import annotations

# Bootstrap MUST be first — registers `hackempire` module alias and fixes sys.path
import _bootstrap  # noqa: F401

import json
from pathlib import Path


def _ensure_config() -> None:
    """
    Auto-create ~/.hackempire/config.json on first run.
    This ensures the config file always exists before any command runs.
    """
    config_dir = Path.home() / ".hackempire"
    config_file = config_dir / "config.json"
    config_dir.mkdir(parents=True, exist_ok=True)
    if not config_file.exists():
        config_file.write_text(json.dumps({
            "bytez_key": "",
            "openrouter_key": "",
            "proxy": ""
        }, indent=2), encoding="utf-8")


from cli.cli import run_cli


def main() -> int:
    _ensure_config()
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
