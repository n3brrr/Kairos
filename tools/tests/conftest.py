"""Puts `tools/` and `tools/hooks/` on `sys.path` so tests can import the scripts directly."""

import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent.parent
for _path in (_TOOLS, _TOOLS / "hooks"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
