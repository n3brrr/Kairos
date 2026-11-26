"""Helpers shared by the service tests: a seeded database and ways to look inside it."""

from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count
from typing import Any

from sqlalchemy import Engine, inspect, text

from kairos.domain.actor import ActorKind, AgentProfile
from kairos.domain.model import ApprovalRequest, Task
from kairos.domain.registry import Epic, Project
from kairos.features.history.log import EventRecord, list_events
from kairos.features.history.verify import VerifyResult, verify_chain
from kairos.features.registry.repository import RegistryRepository
from kairos.features.registry.service import RegistryService
from kairos.features.tasks.queries import TaskQueries
from kairos.features.tasks.repository import Comment, TaskRepository
from kairos.features.tasks.service import TaskService

AT = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)


@dataclass
class Env:
    """A migrated database seeded with two agents, an orchestrator, two projects and an epic."""

    engine: Engine
    service: TaskService
    registry: RegistryService
    queries: TaskQueries

    def put(self, *tasks: Task) -> None:
        """Store tasks directly, skipping the use cases, to set up a state quickly."""
        with self.engine.begin() as conn:
            repo = TaskRepository(conn)
            for task in tasks:
                repo.save(task)

    def put_request(self, request: ApprovalRequest) -> None:
        with self.engine.begin() as conn:
            TaskRepository(conn).save_request(request)

    def task(self, task_id: str) -> Task | None:
        with self.engine.connect() as conn:
            return TaskRepository(conn).get(task_id)

    def pending(self, task_id: str) -> ApprovalRequest | None:
        with self.engine.connect() as conn:
            return TaskRepository(conn).get_pending_request(task_id)

    def comments(self, task_id: str) -> list[Comment]:
        with self.engine.connect() as conn:
            return TaskRepository(conn).comments(task_id)

    def events(self) -> list[EventRecord]:
        with self.engine.connect() as conn:
            return list_events(conn, limit=10_000)

    def verify(self) -> VerifyResult:
        with self.engine.connect() as conn:
            return verify_chain(conn)

    def snapshot(self) -> dict[str, list[tuple[Any, ...]]]:
        """Every row of every table: two equal snapshots mean nothing was written."""
        with self.engine.connect() as conn:
            names = sorted(inspect(conn).get_table_names())
            return {
                name: [tuple(row) for row in conn.execute(text(f"SELECT * FROM {name}"))]
                for name in names
            }


def seed_registry(engine: Engine) -> None:
    """Two agents, an orchestrator, two projects and an epic in each (no events are logged)."""
    with engine.begin() as conn:
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


def make_env(engine: Engine) -> Env:
    """Seed `engine` and build the services over it, with a fixed clock and counting ids."""
    seed_registry(engine)
    ids = count(1)

    def new_id() -> str:
        return f"id{next(ids)}"

    return Env(
        engine,
        TaskService(engine, lambda: AT, new_id),
        RegistryService(engine, lambda: AT, new_id),
        TaskQueries(engine),
    )
