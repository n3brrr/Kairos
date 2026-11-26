from collections.abc import Callable
from dataclasses import replace

import pytest
from sqlalchemy import Engine

from kairos.domain.model import Task

from .support import Env, make_env


@pytest.fixture
def make_task() -> Callable[..., Task]:
    def _make(**changes: object) -> Task:
        base = Task(
            id="t1",
            title="T",
            type="bug",
            project_id="p1",
            created_by="owner",
            description="Something to do",
        )
        return replace(base, **changes)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def env(migrated_engine: Engine) -> Env:
    return make_env(migrated_engine)
