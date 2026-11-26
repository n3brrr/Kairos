"""Storing tasks and what hangs from them. Works inside the caller's transaction, never commits.

A task is one `items` row plus rows in `criteria`, `evidence`, `dependencies` and, for its
subtasks, more `items` rows. `save` writes the whole task: the item is upserted and its children
are replaced (a task has a handful of them, and the history lives in `events`).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Connection, RowMapping, delete, func, insert, literal_column, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from kairos.adapters.db.schema import (
    approval_requests,
    comments,
    criteria,
    dependencies,
    evidence,
    items,
    task_types,
)
from kairos.domain.model import (
    ApprovalRequest,
    Criterion,
    Evidence,
    EvidenceKind,
    Priority,
    RequestKind,
    RequestState,
    Subtask,
    Task,
    TaskType,
)
from kairos.domain.status import Status, SubtaskStatus

_QUEUE_STATUSES = (Status.READY.value, Status.IN_PROGRESS.value)


@dataclass(frozen=True)
class Comment:
    task_id: str
    author: str
    text: str
    at: datetime


def _subtask_row_id(task_id: str, subtask_id: str) -> str:
    """Subtask ids are only unique within their task, but `items.id` is global."""
    return f"{task_id}:{subtask_id}"


class TaskRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    # --- tasks ---------------------------------------------------------------------------

    def get(self, task_id: str) -> Task | None:
        row = (
            self._conn.execute(select(items).where(items.c.id == task_id, items.c.kind == "task"))
            .mappings()
            .first()
        )
        return self._load(row) if row is not None else None

    def list_tasks(
        self, *, status: Status | None = None, assignee: str | None = None
    ) -> list[Task]:
        query = select(items.c.id).where(items.c.kind == "task")
        if status is not None:
            query = query.where(items.c.status == status.value)
        if assignee is not None:
            query = query.where(items.c.assignee_id == assignee)
        ids = self._conn.execute(query.order_by(literal_column("items.rowid"))).scalars().all()
        tasks = (self.get(task_id) for task_id in ids)
        return [task for task in tasks if task is not None]

    def save(self, task: Task) -> None:
        values: dict[str, object] = {
            "id": task.id,
            "kind": "task",
            "parent_id": task.parent_id,
            "title": task.title,
            "status": task.status.value,
            "project_id": task.project_id,
            "type": task.type,
            "priority": task.priority.value,
            "description": task.description,
            "labels": list(task.labels),
            "start_date": task.start_date,
            "due_date": task.due_date,
            "recurrence": task.recurrence,
            "created_by": task.created_by,
            "assignee_id": task.assignee,
            "delivery_summary": task.delivery_summary,
            "working_notes": task.working_notes,
        }
        statement = sqlite_insert(items).values(**values)
        changed = {key: statement.excluded[key] for key in values if key not in ("id", "kind")}
        self._conn.execute(statement.on_conflict_do_update(index_elements=["id"], set_=changed))
        self._replace_children(task)

    def _replace_children(self, task: Task) -> None:
        c = self._conn
        c.execute(delete(evidence).where(evidence.c.task_id == task.id))
        c.execute(delete(criteria).where(criteria.c.task_id == task.id))
        c.execute(delete(dependencies).where(dependencies.c.task_id == task.id))
        c.execute(delete(items).where(items.c.kind == "subtask", items.c.parent_id == task.id))
        for position, criterion in enumerate(task.criteria):
            c.execute(
                insert(criteria).values(
                    task_id=task.id, id=criterion.id, position=position, text=criterion.text
                )
            )
            for index, proof in enumerate(criterion.evidence):
                c.execute(
                    insert(evidence).values(
                        task_id=task.id,
                        criterion_id=criterion.id,
                        position=index,
                        kind=proof.kind.value,
                        content=proof.content,
                        added_by=proof.added_by,
                    )
                )
        for blocker in sorted(task.blocked_by):
            c.execute(insert(dependencies).values(task_id=task.id, blocker_id=blocker))
        for position, subtask in enumerate(task.subtasks):
            c.execute(
                insert(items).values(
                    id=_subtask_row_id(task.id, subtask.id),
                    kind="subtask",
                    parent_id=task.id,
                    title=subtask.title,
                    status=subtask.status.value,
                    position=position,
                )
            )

    def _load(self, row: RowMapping) -> Task:
        task_id: str = row["id"]
        c = self._conn
        proofs: dict[str, list[Evidence]] = {}
        evidence_rows = c.execute(
            select(evidence)
            .where(evidence.c.task_id == task_id)
            .order_by(evidence.c.criterion_id, evidence.c.position)
        ).mappings()
        for proof in evidence_rows:
            proofs.setdefault(proof["criterion_id"], []).append(
                Evidence(EvidenceKind(proof["kind"]), proof["content"], proof["added_by"])
            )
        criteria_rows = c.execute(
            select(criteria).where(criteria.c.task_id == task_id).order_by(criteria.c.position)
        ).mappings()
        blockers = c.execute(
            select(dependencies.c.blocker_id).where(dependencies.c.task_id == task_id)
        ).scalars()
        prefix = _subtask_row_id(task_id, "")
        subtask_rows = c.execute(
            select(items)
            .where(items.c.kind == "subtask", items.c.parent_id == task_id)
            .order_by(items.c.position)
        ).mappings()
        return Task(
            id=task_id,
            title=row["title"],
            type=row["type"],
            project_id=row["project_id"],
            created_by=row["created_by"],
            parent_id=row["parent_id"],
            status=Status(row["status"]),
            priority=Priority(row["priority"]),
            description=row["description"],
            labels=tuple(row["labels"]),
            start_date=row["start_date"],
            due_date=row["due_date"],
            recurrence=row["recurrence"],
            criteria=tuple(
                Criterion(crit["id"], crit["text"], tuple(proofs.get(crit["id"], ())))
                for crit in criteria_rows
            ),
            subtasks=tuple(
                Subtask(sub["id"].removeprefix(prefix), sub["title"], SubtaskStatus(sub["status"]))
                for sub in subtask_rows
            ),
            blocked_by=frozenset(blockers),
            assignee=row["assignee_id"],
            delivery_summary=row["delivery_summary"],
            working_notes=row["working_notes"],
        )

    # --- what the gates, the queue and dependencies need ----------------------------------

    def get_task_type(self, name: str) -> TaskType | None:
        row = (
            self._conn.execute(select(task_types).where(task_types.c.name == name))
            .mappings()
            .first()
        )
        if row is None:
            return None
        return TaskType(
            row["name"], frozenset(row["required_fields"]), tuple(row["criteria_template"])
        )

    def blocked_by_map(self) -> dict[str, frozenset[str]]:
        """Every task id mapped to the ids that block it (empty when none)."""
        found: dict[str, set[str]] = {
            task_id: set()
            for task_id in self._conn.execute(select(items.c.id).where(items.c.kind == "task"))
            .scalars()
            .all()
        }
        for row in self._conn.execute(select(dependencies)).mappings():
            found.setdefault(row["task_id"], set()).add(row["blocker_id"])
        return {task_id: frozenset(blockers) for task_id, blockers in found.items()}

    def statuses(self, ids: Iterable[str]) -> dict[str, Status]:
        wanted = list(ids)
        if not wanted:
            return {}
        rows = self._conn.execute(
            select(items.c.id, items.c.status).where(items.c.kind == "task", items.c.id.in_(wanted))
        )
        return {row.id: Status(row.status) for row in rows}

    def other_in_progress(self, agent_id: str, *, excluding: str) -> frozenset[str]:
        rows = self._conn.execute(
            select(items.c.id).where(
                items.c.kind == "task",
                items.c.status == Status.IN_PROGRESS.value,
                items.c.assignee_id == agent_id,
                items.c.id != excluding,
            )
        )
        return frozenset(rows.scalars().all())

    def load(self, agent_id: str) -> int:
        """How many of the agent's tasks take a slot of its queue (`READY` and `IN_PROGRESS`)."""
        count = self._conn.execute(
            select(func.count()).where(
                items.c.kind == "task",
                items.c.assignee_id == agent_id,
                items.c.status.in_(_QUEUE_STATUSES),
            )
        ).scalar_one()
        return int(count)

    # --- approval requests and comments ----------------------------------------------------

    def get_pending_request(self, task_id: str) -> ApprovalRequest | None:
        row = (
            self._conn.execute(
                select(approval_requests).where(
                    approval_requests.c.task_id == task_id,
                    approval_requests.c.state == RequestState.PENDING.value,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return ApprovalRequest(
            row["task_id"],
            RequestKind(row["kind"]),
            row["requested_by"],
            row["reason"],
            RequestState.PENDING,
            row["note"],
        )

    def pending_requests(self) -> list[ApprovalRequest]:
        rows = self._conn.execute(
            select(approval_requests)
            .where(approval_requests.c.state == RequestState.PENDING.value)
            .order_by(approval_requests.c.id)
        ).mappings()
        return [
            ApprovalRequest(
                row["task_id"],
                RequestKind(row["kind"]),
                row["requested_by"],
                row["reason"],
                RequestState.PENDING,
                row["note"],
            )
            for row in rows
        ]

    def save_request(self, request: ApprovalRequest) -> None:
        """Insert a new pending request, or resolve the pending one of the same kind in place."""
        if request.state is not RequestState.PENDING:
            resolved = self._conn.execute(
                update(approval_requests)
                .where(
                    approval_requests.c.task_id == request.task_id,
                    approval_requests.c.kind == request.kind.value,
                    approval_requests.c.state == RequestState.PENDING.value,
                )
                .values(state=request.state.value, note=request.note)
            )
            if resolved.rowcount:
                return
        self._conn.execute(
            insert(approval_requests).values(
                task_id=request.task_id,
                kind=request.kind.value,
                requested_by=request.requested_by,
                reason=request.reason,
                state=request.state.value,
                note=request.note,
            )
        )

    def add_comment(self, comment: Comment) -> None:
        self._conn.execute(
            insert(comments).values(
                task_id=comment.task_id,
                author=comment.author,
                text=comment.text,
                at=comment.at.astimezone(UTC).isoformat(),
            )
        )

    def comments(self, task_id: str) -> list[Comment]:
        rows = self._conn.execute(
            select(comments).where(comments.c.task_id == task_id).order_by(comments.c.id)
        ).mappings()
        return [
            Comment(row["task_id"], row["author"], row["text"], datetime.fromisoformat(row["at"]))
            for row in rows
        ]
