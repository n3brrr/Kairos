"""PreToolUse hook for Bash: blocks commands the project forbids.

Reads the hook JSON on stdin (`tool_input.command`). When a command is blocked it prints the
reason to stderr and exits 2, which makes Claude Code refuse the call and show the reason.
Anything else, including unreadable input, exits 0: the guard never breaks a session.
"""

import json
import re
import shlex
import sys

_PUNCTUATION = ";&|()\n"
_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_MAIN_REFS = {"main", "refs/heads/main"}


def _segments(command: str) -> list[list[str]]:
    """Split a shell command into simple commands, ignoring separators inside quotes."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=_PUNCTUATION)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:  # unbalanced quotes: fall back to a plain split, still inspected
        tokens = [t for t in re.split(r"(\|\||&&|[;&|()\n])|\s+", command) if t]
    segments: list[list[str]] = [[]]
    for token in tokens:
        if set(token) <= set(_PUNCTUATION):
            segments.append([])
        else:
            segments[-1].append(token)
    return [s for s in segments if s]


def _words(segment: list[str]) -> list[str]:
    """The segment without leading `VAR=value` assignments."""
    index = 0
    while index < len(segment) and _ENV_ASSIGNMENT.match(segment[index]):
        index += 1
    return segment[index:]


def _short_flags(args: list[str]) -> set[str]:
    return {c for a in args if a.startswith("-") and not a.startswith("--") for c in a[1:]}


def _check_git_push(args: list[str]) -> str | None:
    forced = any(
        a == "--force" or a == "--force-with-lease" or a.startswith("--force-with-lease=")
        for a in args
    )
    if forced or "f" in _short_flags(args):
        return "force-pushing is blocked: published history is never rewritten"
    operands = [a for a in args if not a.startswith("-")]
    for operand in operands[1:]:  # operands[0] is the remote
        if operand.startswith("+"):
            return "a '+' refspec is a force push, which is blocked"
        if operand in _MAIN_REFS or operand.endswith((":main", ":refs/heads/main")):
            return "pushing to main is blocked: open a pull request instead"
    return None


def _check_git(rest: list[str]) -> str | None:
    sub = next((a for a in rest if not a.startswith("-")), None)
    if sub is None:
        return None
    args = rest[rest.index(sub) + 1 :]
    if sub == "push":
        return _check_git_push(args)
    if sub == "add" and any(a in (".", "./", "-A", "--all") for a in args):
        return "add files by name: `git add .`, `-A` and `--all` are blocked"
    if sub == "commit" and ("--no-verify" in args or "n" in _short_flags(args)):
        return "skipping hooks (`--no-verify` / `-n`) is blocked"
    if sub == "reset" and "--hard" in args:
        return "`git reset --hard` discards work and is blocked"
    return None


def _check_docker(rest: list[str]) -> str | None:
    compose = rest[:1] == ["compose"]
    if compose:
        rest = rest[1:]
    if compose and rest[:1] == ["down"] and any(a in ("-v", "--volumes") for a in rest):
        return "`docker compose down -v` deletes the data volume and is blocked"
    if not compose and rest[:2] in (["volume", "rm"], ["volume", "prune"]):
        return "removing Docker volumes is blocked: it deletes data"
    if not compose and rest[:2] == ["system", "prune"]:
        return "`docker system prune` is blocked"
    return None


def check_command(command: str) -> str | None:
    """Return why `command` must be blocked, or None if it may run."""
    for segment in _segments(command):
        words = _words(segment)
        if not words:
            continue
        program, rest = words[0], words[1:]
        reason: str | None = None
        if program in ("npm", "npx", "yarn"):
            reason = f"`{program}` is blocked: this project uses pnpm only"
        elif program == "git":
            reason = _check_git(rest)
        elif program == "gh" and rest[:2] == ["pr", "merge"]:
            reason = "agents never merge: the owner merges pull requests"
        elif program == "docker":
            reason = _check_docker(rest)
        elif program == "docker-compose":
            reason = _check_docker(["compose", *rest])
        if reason:
            return reason
    return None


def main() -> int:
    try:
        command = json.load(sys.stdin)["tool_input"]["command"]
        if not isinstance(command, str):
            return 0
    except (ValueError, KeyError, TypeError):
        return 0
    reason = check_command(command)
    if reason:
        print(f"Blocked by project guard: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
