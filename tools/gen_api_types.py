"""Generate `frontend/src/api/schema.d.ts` from the backend's OpenAPI schema.

Run: `uv run --project backend python tools/gen_api_types.py [--check]`

With `--check` nothing is written: the types are generated into a temporary file and compared
with the committed one. Line endings are normalized first, so Windows (CRLF) and CI (LF) agree.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
SCHEMA_PATH = FRONTEND / "src" / "api" / "schema.d.ts"
STALE_MESSAGE = (
    "frontend/src/api/schema.d.ts is out of date; "
    "run: uv run --project backend python tools/gen_api_types.py"
)


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n")


def is_up_to_date(generated: str, committed: str) -> bool:
    return normalize(generated) == normalize(committed)


def _generate(openapi_json: Path, output: Path) -> None:
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise SystemExit("pnpm was not found on PATH")
    subprocess.run(
        [pnpm, "exec", "openapi-typescript", str(openapi_json), "-o", str(output)],
        cwd=FRONTEND,
        check=True,
    )


def main(argv: list[str]) -> int:
    from kairos.config import Settings
    from kairos.main import create_app

    check = "--check" in argv
    with tempfile.TemporaryDirectory() as tmp:
        openapi_json = Path(tmp) / "openapi.json"
        openapi_json.write_text(json.dumps(create_app(Settings()).openapi()), encoding="utf-8")
        target = Path(tmp) / "schema.d.ts" if check else SCHEMA_PATH
        _generate(openapi_json, target)
        if not check:
            print(f"wrote {SCHEMA_PATH.relative_to(ROOT)}")
            return 0
        committed = SCHEMA_PATH.read_text(encoding="utf-8") if SCHEMA_PATH.is_file() else ""
        if is_up_to_date(target.read_text(encoding="utf-8"), committed):
            print("API types are up to date")
            return 0
        print(STALE_MESSAGE)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
