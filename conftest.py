"""
conftest.py — pytest path + package alias setup for HackEmpire X.

The repo root IS the hackempire/ package directory. This means:
  - Locally: parent dir contains hackempire/ folder → `import hackempire` works
  - CI (GitHub Actions): repo cloned as hackempire-x/, no hackempire/ subfolder

This conftest handles both cases by injecting a `hackempire` module alias
that points to the current package root, so `from hackempire.core.xxx import ...`
works in all environments.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

# This file lives at the repo root (same dir as main.py, core/, tools/, etc.)
_PKG_ROOT = Path(__file__).resolve().parent

# Add repo root to sys.path so direct imports work: `from core.xxx import ...`
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

# Also add parent in case it contains a hackempire/ subfolder (local dev)
_REPO_ROOT = _PKG_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# If `hackempire` is not already importable as a package (CI case),
# inject a module alias so `from hackempire.core.xxx import ...` resolves
# to `from core.xxx import ...` transparently.
if "hackempire" not in sys.modules:
    import importlib
    import importlib.util

    # Create a package stub for `hackempire` pointing to _PKG_ROOT
    spec = importlib.util.spec_from_file_location(
        "hackempire",
        str(_PKG_ROOT / "__init__.py"),
        submodule_search_locations=[str(_PKG_ROOT)],
    )
    if spec is not None:
        mod = importlib.util.module_from_spec(spec)
        mod.__path__ = [str(_PKG_ROOT)]  # type: ignore[attr-defined]
        mod.__package__ = "hackempire"
        sys.modules["hackempire"] = mod
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except Exception:
            pass  # __init__.py is empty, that's fine
