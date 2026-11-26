from pathlib import Path
from types import SimpleNamespace

from check import Step, StepResult, build_steps, run_steps, summarize

ROOT = Path("/repo")


def _steps() -> list[Step]:
    return [Step(name, ["x"], ROOT) for name in ("one", "two", "three")]


def _runner(failing: set[str]):
    def run(argv: list[str], cwd: Path, **_: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=1 if cwd.name in failing else 0)

    return run


def test_all_steps_run_even_after_a_failure():
    steps = [Step(name, ["x"], Path(name)) for name in ("one", "two", "three")]
    results = run_steps(steps, runner=_runner({"one"}))
    assert [r.step.name for r in results] == ["one", "two", "three"]
    assert [r.returncode for r in results] == [1, 0, 0]


def test_exit_code_is_one_when_any_step_fails():
    step = _steps()[0]
    assert summarize([StepResult(step, 0), StepResult(step, 2)])[1] == 1
    assert summarize([StepResult(step, 0)])[1] == 0


def test_summary_lists_every_step_with_its_status():
    one, two, _ = _steps()
    text, _code = summarize([StepResult(one, 0), StepResult(two, 1)])
    assert "PASS" in text.splitlines()[0] and "one" in text.splitlines()[0]
    assert "FAIL" in text.splitlines()[1] and "two" in text.splitlines()[1]


def test_build_steps_cover_backend_frontend_and_contracts():
    names = [s.name for s in build_steps(ROOT)]
    assert names == [
        "backend:format",
        "backend:lint",
        "backend:types",
        "backend:test",
        "tools:test",
        "contracts",
        "frontend:lint",
        "frontend:types",
        "frontend:test",
        "frontend:build",
    ]
