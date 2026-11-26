from format_on_edit import formatter_for


def test_python_files_use_ruff():
    for path in ("backend/src/kairos/main.py", "tools/check.py", "tools/hooks/guard_bash.py"):
        assert formatter_for(path) == [
            "uv", "run", "--project", "backend", "ruff", "format",
            "--config", "backend/pyproject.toml", path,
        ]  # fmt: skip


def test_frontend_files_use_biome():
    for path in ("frontend/src/App.tsx", "frontend/src/messages.ts", "frontend/package.json"):
        assert formatter_for(path) == [
            "pnpm", "--dir", "frontend", "exec", "biome", "format", "--write", path,
        ]  # fmt: skip


def test_other_files_are_left_alone():
    for path in ("README.md", "docs/STATUS.md", "Dockerfile", "compose.yaml", "scripts/x.py"):
        assert formatter_for(path) is None


def test_generated_and_vendored_files_are_left_alone():
    for path in ("frontend/src/api/schema.d.ts", "frontend/node_modules/x/index.ts"):
        assert formatter_for(path) is None


def test_windows_separators_are_understood():
    assert formatter_for("backend\src\kairos\main.py") is not None
