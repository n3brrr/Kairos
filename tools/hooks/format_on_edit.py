"""PostToolUse hook for Edit|Write: formats the touched file with the project's formatter.

It uses the same configuration as `python tools/check.py`, so the hook and `check` never
disagree. It never fails the tool call: a formatter problem is `check`'s job to report.
"""

import json
import subprocess
import sys
from pathlib import Path

_FRONTEND_SUFFIXES = (".ts", ".tsx", ".json")
_SKIPPED_FRONTEND = ("frontend/src/api/schema.d.ts", "frontend/node_modules/", "frontend/dist/")


def formatter_for(path: str) -> list[str] | None:
    """The formatter command for a repo-relative `path`, or None to leave it alone."""
    path = path.replace("\\", "/")
    if path.endswith(".py") and path.startswith(("backend/", "tools/")):
        return [
            "uv",
            "run",
            "--project",
            "backend",
            "ruff",
            "format",
            "--config",
            "backend/pyproject.toml",
            path,
        ]
    if (
        path.startswith("frontend/")
        and path.endswith(_FRONTEND_SUFFIXES)
        and not path.startswith(_SKIPPED_FRONTEND)
    ):
        return ["pnpm", "--dir", "frontend", "exec", "biome", "format", "--write", path]
    return None


def main() -> int:
    try:
        file_path = json.load(sys.stdin)["tool_input"]["file_path"]
        root = Path(__file__).resolve().parents[2]
        relative = Path(file_path).resolve().relative_to(root).as_posix()
    except (ValueError, KeyError, TypeError, OSError):
        return 0
    command = formatter_for(relative)
    if command is not None:
        subprocess.run(command, cwd=root, capture_output=True, check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
