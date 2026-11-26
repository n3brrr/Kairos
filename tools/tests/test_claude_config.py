import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CLAUDE = ROOT / ".claude"


def _frontmatter(path: Path) -> dict:
    match = re.match(r"^---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.DOTALL)
    assert match, f"{path} has no frontmatter"
    return yaml.safe_load(match.group(1))


def test_every_agent_has_name_and_description():
    agents = sorted((CLAUDE / "agents").glob("*.md"))
    assert agents
    for path in agents:
        meta = _frontmatter(path)
        assert meta.get("name"), path
        assert meta.get("description"), path


def test_agent_name_matches_filename():
    for path in (CLAUDE / "agents").glob("*.md"):
        assert _frontmatter(path)["name"] == path.stem


def test_every_skill_has_name_and_description():
    skills = sorted((CLAUDE / "skills").glob("*/SKILL.md"))
    assert skills
    for path in skills:
        meta = _frontmatter(path)
        assert meta.get("name") == path.parent.name, path
        assert meta.get("description"), path


def test_rules_declare_paths():
    rules = sorted((CLAUDE / "rules").glob("*.md"))
    assert rules
    for path in rules:
        paths = _frontmatter(path).get("paths")
        assert isinstance(paths, list) and paths, path


def test_agents_never_get_approval_powers():
    # Golden rule 2: nothing in the agent definitions may grant merge/approve/delete.
    for path in (CLAUDE / "agents").glob("*.md"):
        tools = _frontmatter(path).get("tools") or ""
        assert "merge" not in str(tools).lower(), path


def test_reviewer_is_read_only():
    tools = str(_frontmatter(CLAUDE / "agents" / "reviewer.md").get("tools"))
    for forbidden in ("Edit", "Write", "NotebookEdit"):
        assert forbidden not in tools


def test_settings_hooks_point_at_existing_scripts():
    settings = json.loads((CLAUDE / "settings.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for groups in settings["hooks"].values()
        for group in groups
        for hook in group["hooks"]
    ]
    assert commands
    for command in commands:
        script = re.search(r"tools/hooks/\w+\.py", command)
        assert script and (ROOT / script.group(0)).is_file(), command
