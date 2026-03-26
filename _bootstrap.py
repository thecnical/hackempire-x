"""
_bootstrap.py — HackEmpire X import path bootstrap.

Call `import _bootstrap` (or `from _bootstrap import *`) as the VERY FIRST
import in any entry point (main.py, setup.sh launcher, etc.).

What it does:
  1. Adds the package root (this directory) to sys.path so that
     `from core.xxx import ...` style imports work.
  2. Registers a `hackempire` module alias pointing to this directory,
     so that `from hackempire.core.xxx import ...` also works — regardless
     of whether the repo was cloned as `hackempire/` or `hackempire-x/`.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent

# 1. Direct imports: `from core.xxx import ...`
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

# 2. Also add parent so `import hackempire` works when cloned locally
_REPO_ROOT = _PKG_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(1, str(_REPO_ROOT))

# 3. Register `hackempire` alias if not already importable
if "hackempire" not in sys.modules:
    _init = _PKG_ROOT / "__init__.py"
    _spec = importlib.util.spec_from_file_location(
        "hackempire",
        str(_init),
        submodule_search_locations=[str(_PKG_ROOT)],
    )
    if _spec is not None:
        _mod = importlib.util.module_from_spec(_spec)
        _mod.__path__ = [str(_PKG_ROOT)]  # type: ignore[attr-defined]
        _mod.__package__ = "hackempire"
        sys.modules["hackempire"] = _mod
        try:
            _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
        except Exception:
            pass
