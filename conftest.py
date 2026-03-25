"""
conftest.py — pytest path + package alias setup for HackEmpire X.

The repo root IS the hackempire package (main.py, core/, tools/, etc. live here).
Tests import via `from hackempire.core.xxx import ...` — so we register this
directory as the `hackempire` package in sys.modules at collection time.

This works regardless of what the cloned folder is named (hackempire-x on GitHub,
hackempire locally, etc.).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

# This file lives at the repo root (same level as main.py, core/, tools/, etc.)
_REPO_ROOT = Path(__file__).resolve().parent

# Ensure the repo root is on sys.path so bare imports work:
#   from core.xxx import ...   (used inside source files)
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Also ensure the PARENT is on sys.path (belt-and-suspenders for any edge cases)
_PARENT = _REPO_ROOT.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

# Register this directory as the `hackempire` package so that:
#   from hackempire.core.xxx import ...   works in tests
# regardless of what the cloned folder is named on disk.
if "hackempire" not in sys.modules:
    import importlib.util as _ilu

    # Create a package spec pointing at this directory
    _spec = _ilu.spec_from_file_location(
        "hackempire",
        str(_REPO_ROOT / "__init__.py"),
        submodule_search_locations=[str(_REPO_ROOT)],
    )
    _pkg = _ilu.module_from_spec(_spec)
    _pkg.__path__ = [str(_REPO_ROOT)]  # type: ignore[attr-defined]
    _pkg.__package__ = "hackempire"
    sys.modules["hackempire"] = _pkg
    _spec.loader.exec_module(_pkg)  # type: ignore[union-attr]
