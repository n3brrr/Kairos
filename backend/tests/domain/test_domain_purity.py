import ast
import sys
from pathlib import Path

DOMAIN = Path(__file__).resolve().parents[2] / "src" / "kairos" / "domain"


def _imported_modules(path: Path) -> list[tuple[str, int]]:
    """Every absolute module a file imports, with 0 for `import x` and the level for relative."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append((node.module or "", node.level))
    return found


def test_domain_imports_only_stdlib_and_itself():
    files = sorted(DOMAIN.glob("*.py"))
    assert files, "the domain package is empty"
    for path in files:
        for module, level in _imported_modules(path):
            if level > 0 or module.startswith("kairos.domain"):
                continue
            assert module.split(".")[0] in sys.stdlib_module_names, f"{path.name} imports {module}"
