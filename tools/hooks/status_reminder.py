"""Stop hook: reminds the agent to update docs/STATUS.md when code changed after it.

Exits 2 (which makes Claude continue with the reminder) at most once per stop: when
`stop_hook_active` is true the agent already saw the reminder, so the hook lets it finish.
"""

import json
import subprocess
import sys
from pathlib import Path

REMINDER = "Update docs/STATUS.md before finishing"


def needs_status_update(status_mtime: float, changed: dict[str, float]) -> bool:
    """True when any changed path outside docs/ is newer than STATUS.md."""
    return any(mtime > status_mtime for mtime in changed.values())


def _changed_outside_docs(root: Path) -> dict[str, float]:
    out = subprocess.run(
        ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    changed: dict[str, float] = {}
    entries = iter(out.split("\0"))
    for entry in entries:
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            next(entries, None)  # the original path of a rename follows
        file = root / path
        if not path.startswith("docs/") and file.is_file():
            changed[path] = file.stat().st_mtime
    return changed


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}
    if isinstance(payload, dict) and payload.get("stop_hook_active"):
        return 0
    root = Path(__file__).resolve().parents[2]
    status = root / "docs" / "STATUS.md"
    if not status.is_file():
        return 0
    if needs_status_update(status.stat().st_mtime, _changed_outside_docs(root)):
        print(REMINDER, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
