"""
conftest.py — pytest path setup for HackEmpire X.

Ensures both the repo root (parent of hackempire/) and hackempire/ itself
are on sys.path so that:
  - `from hackempire.core.xxx import ...`  works (package-style imports in tests)
  - `from core.xxx import ...`             works (direct imports in source files)

This file is picked up automatically by pytest before any test collection.
"""
from __future__ import annotations

import sys
from pathlib import Path

# hackempire/ directory (where main.py lives)
_PKG_ROOT = Path(__file__).resolve().parent

# repo root (parent of hackempire/) — this is what makes `import hackempire` work
_REPO_ROOT = _PKG_ROOT.parent

for _p in (_PKG_ROOT, _REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
