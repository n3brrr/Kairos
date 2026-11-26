"""Single `check` command: runs every verification and fails if any step fails.

Run: `python tools/check.py` (standard library only). Every step runs, even after a failure,
so one run shows everything that is broken.
"""

import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple


class Step(NamedTuple):
    name: str
    argv: list[str]
    cwd: Path


class StepResult(NamedTuple):
    step: Step
    returncode: int


def _exe(name: str) -> str:
    """Resolve an executable so `pnpm.cmd` works on Windows; fall back to the bare name."""
    return shutil.which(name) or name


def build_steps(root: Path) -> list[Step]:
    backend, frontend = root / "backend", root / "frontend"
    uv, pnpm = _exe("uv"), _exe("pnpm")
    ruff_paths = [".", "../tools"]
    return [
        Step(
            "backend:format",
            [uv, "run", "ruff", "format", "--check", "--config", "pyproject.toml", *ruff_paths],
            backend,
        ),
        Step(
            "backend:lint",
            [uv, "run", "ruff", "check", "--config", "pyproject.toml", *ruff_paths],
            backend,
        ),
        Step("backend:types", [uv, "run", "pyright"], backend),
        Step("backend:test", [uv, "run", "pytest", "-q"], backend),
        Step(
            "tools:test",
            [uv, "run", "--project", "backend", "pytest", "tools/tests", "-q"],
            root,
        ),
        Step(
            "contracts",
            [uv, "run", "--project", "backend", "python", "tools/gen_api_types.py", "--check"],
            root,
        ),
        Step("frontend:lint", [pnpm, "lint"], frontend),
        Step("frontend:types", [pnpm, "typecheck"], frontend),
        Step("frontend:test", [pnpm, "test"], frontend),
        Step("frontend:build", [pnpm, "build"], frontend),
    ]


def run_steps(steps: list[Step], runner: Callable[..., Any] = subprocess.run) -> list[StepResult]:
    results: list[StepResult] = []
    for step in steps:
        print(f"\n=== {step.name}: {' '.join(step.argv)}", flush=True)
        results.append(StepResult(step, runner(step.argv, cwd=step.cwd).returncode))
    return results


def summarize(results: list[StepResult]) -> tuple[str, int]:
    lines = [f"{'PASS' if r.returncode == 0 else 'FAIL'}  {r.step.name}" for r in results]
    return "\n".join(lines), 0 if all(r.returncode == 0 for r in results) else 1


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    text, code = summarize(run_steps(build_steps(root)))
    print(f"\n{text}\n\ncheck: {'OK' if code == 0 else 'FAILED'}")
    return code


if __name__ == "__main__":
    sys.exit(main())
