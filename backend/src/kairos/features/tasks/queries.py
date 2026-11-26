"""Reading tasks, requests and history, filtered by what the actor may see (design §6.9)."""

from sqlalchemy import Engine

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.decision import Rejected, RejectionCode
from kairos.domain.model import ApprovalRequest, Task
from kairos.domain.status import Status
from kairos.domain.visibility import can_view_task
from kairos.features.history.log import EventRecord, list_events
from kairos.features.tasks.repository import TaskRepository

_HISTORY_LIMIT = 1000
_QUEUE_VIEWERS = frozenset({ActorKind.OWNER, ActorKind.ORCHESTRATOR})
_NOT_FOUND = Rejected(RejectionCode.NOT_FOUND, "No such task.")


class TaskQueries:
    """A task the actor may not see answers exactly like one that does not exist."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_task(self, actor: Actor, task_id: str) -> Task | Rejected:
        with self._engine.connect() as conn:
            task = TaskRepository(conn).get(task_id)
        return task if task is not None and can_view_task(actor, task) else _NOT_FOUND

    def list_tasks(
        self, actor: Actor, *, status: Status | None = None, assignee: str | None = None
    ) -> list[Task]:
        with self._engine.connect() as conn:
            tasks = TaskRepository(conn).list_tasks(status=status, assignee=assignee)
        return [task for task in tasks if can_view_task(actor, task)]

    def pending_requests(self, actor: Actor) -> list[ApprovalRequest]:
        """The approval queue: for the owner and the orchestrator. Agents see none."""
        if actor.kind not in _QUEUE_VIEWERS:
            return []
        with self._engine.connect() as conn:
            return TaskRepository(conn).pending_requests()

    def task_history(self, actor: Actor, task_id: str) -> list[EventRecord] | Rejected:
        with self._engine.connect() as conn:
            task = TaskRepository(conn).get(task_id)
            if task is None or not can_view_task(actor, task):
                return _NOT_FOUND
            return list_events(conn, entity_id=task_id, limit=_HISTORY_LIMIT)
