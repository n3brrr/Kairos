"""Helpers shared by the service tests: a seeded database and ways to look inside it."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, inspect, text

from kairos.domain.model import ApprovalRequest, Task
from kairos.features.history.log import EventRecord, list_events
from kairos.features.history.verify import VerifyResult, verify_chain
from kairos.features.tasks.repository import Comment, TaskRepository
from kairos.features.tasks.service import TaskService

AT = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)


@dataclass
class Env:
    """A migrated database seeded with two agents, an orchestrator, two projects and an epic."""

    engine: Engine
    service: TaskService

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
