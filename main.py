from __future__ import annotations

# Bootstrap MUST be first — registers `hackempire` module alias and fixes sys.path
# so both `from core.xxx` and `from hackempire.core.xxx` imports work regardless
# of how/where the repo was cloned.
import _bootstrap  # noqa: F401

from cli.cli import run_cli


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
