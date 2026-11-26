from collections.abc import Callable, Iterator
from dataclasses import replace
from itertools import count

import pytest
from sqlalchemy import Engine

from kairos.domain.actor import ActorKind, AgentProfile
from kairos.domain.model import Task
from kairos.domain.registry import Epic, Project
from kairos.features.registry.repository import RegistryRepository
from kairos.features.registry.service import RegistryService
from kairos.features.tasks.queries import TaskQueries
from kairos.features.tasks.service import TaskService

from .support import AT, Env


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
def env(migrated_engine: Engine) -> Iterator[Env]:
    with migrated_engine.begin() as conn:
        registry = RegistryRepository(conn)
        registry.save_agent(
            AgentProfile("a1", ActorKind.AGENT, frozenset({"bug"}), frozenset({"p1"}))
        )
        registry.save_agent(
            AgentProfile(
                "a2", ActorKind.AGENT, frozenset({"bug"}), frozenset({"p1"}), queue_limit=1
            )
        )
        registry.save_agent(
            AgentProfile("o1", ActorKind.ORCHESTRATOR, frozenset({"bug"}), frozenset({"p1"}))
        )
        registry.save_project(Project("p1", "Kairos", "Development"))
        registry.save_project(Project("p2", "Other", "Personal"))
        registry.save_epic(Epic("e1", "p1", "Epic one"))
        registry.save_epic(Epic("e2", "p2", "Epic two"))
    ids = count(1)

    def new_id() -> str:
        return f"id{next(ids)}"

    yield Env(
        migrated_engine,
        TaskService(migrated_engine, lambda: AT, new_id),
        RegistryService(migrated_engine, lambda: AT, new_id),
        TaskQueries(migrated_engine),
    )
