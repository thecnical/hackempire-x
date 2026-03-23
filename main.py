from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    """
    Clean program entry point for `python main.py ...` runs.
    """
    this_dir = Path(__file__).resolve().parent
    if str(this_dir) not in sys.path:
        sys.path.insert(0, str(this_dir))

    from cli.cli import run_cli

    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())

