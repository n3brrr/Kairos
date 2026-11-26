import json
import subprocess
import sys
from pathlib import Path

import pytest
from guard_bash import check_command

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "guard_bash.py"


@pytest.mark.parametrize(
    "cmd",
    [
        "git push --force",
        "git push -f origin feat/x",
        "git push origin main",
        "git push origin HEAD:main",
        "cd x && git push --force-with-lease",
        "git add .",
        "git add -A",
        "git commit -m x --no-verify",
        "git reset --hard HEAD~1",
        "gh pr merge 3 --squash",
        "docker compose down -v",
        "docker volume rm kairos_kairos-data",
        "docker system prune -af",
        "npm install",
        "npx biome check",
        "yarn add x",
        # variants that must not slip through
        "git push --force-with-lease=main origin feat/x",
        "git push origin +feat/x",
        "git push -u origin refs/heads/main",
        "git add --all",
        "git commit -n -m x",
        "echo ok; git push --force",
        "false || npm test",
        "FOO=1 npm run build",
        "docker compose down --volumes",
        "docker-compose down -v",
        "git status\ngit push --force",
        "docker volume prune -f",
    ],
)
def test_blocks_destructive_commands(cmd):
    assert check_command(cmd) is not None


@pytest.mark.parametrize(
    "cmd",
    [
        "git status",
        "git push -u origin feat/BOOT-004-x",
        "git add backend/src/kairos/main.py",
        "python tools/check.py",
        "docker compose down",
        "pnpm test",
        "pnpm install --frozen-lockfile",
        "pnpm exec biome check .",
        "pnpm dlx some-tool",
        "git add .github/workflows/ci.yml",
        "git add .claude/settings.json",
        "git add -- .gitignore",
        "git push -u origin docs/main-notes",
        # dangerous words that are only data, not commands
        'git commit -m "never run git push --force or npm install"',
        "echo npm install",
        "git commit -m \"$(cat <<'EOF'\nfix: x\n\ngit add . is banned\nEOF\n)\"",
    ],
)
def test_allows_normal_commands(cmd):
    assert check_command(cmd) is None


def _run_hook(command: str) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, check=False
    )


def test_hook_exits_2_with_reason_on_stderr_when_blocked():
    result = _run_hook("git push --force")
    assert result.returncode == 2
    assert result.stderr.strip()


def test_hook_exits_0_for_a_harmless_command():
    assert _run_hook("git status").returncode == 0


def test_hook_does_not_block_on_malformed_input():
    result = subprocess.run(
        [sys.executable, str(HOOK)], input="not json", capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
