"""
conftest.py — pytest bootstrap for HackEmpire X.

Imports _bootstrap which registers the `hackempire` module alias and fixes
sys.path so all `from hackempire.xxx` imports work in CI and locally.
"""
import sys
from pathlib import Path

# Ensure _bootstrap itself is findable (it lives next to this file)
_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

import _bootstrap  # noqa: F401
