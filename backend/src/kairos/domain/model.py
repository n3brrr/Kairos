"""The item model: hierarchy, tasks, criteria, evidence and approval requests."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from kairos.domain.status import Status, SubtaskStatus


class ItemKind(StrEnum):
    PROJECT = "project"
    EPIC = "epic"
    TASK = "task"
    SUBTASK = "subtask"


_PARENTS: dict[ItemKind, frozenset[ItemKind | None]] = {
    ItemKind.PROJECT: frozenset({None}),
    ItemKind.EPIC: frozenset({ItemKind.PROJECT}),
    ItemKind.TASK: frozenset({ItemKind.PROJECT, ItemKind.EPIC}),
    ItemKind.SUBTASK: frozenset({ItemKind.TASK}),
}


def can_parent(parent: ItemKind | None, child: ItemKind) -> bool:
    """Project > Epic > Task > Subtask; a task may hang directly from a project."""
    return parent in _PARENTS[child]


def is_blank(text: str | None) -> bool:
    """True for `None`, the empty string and whitespace-only text."""
    return text is None or not text.strip()


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class EvidenceKind(StrEnum):
    TEXT = "text"
    LINK = "link"
    COMMAND_OUTPUT = "command_output"


@dataclass(frozen=True)
class Evidence:
    kind: EvidenceKind
    content: str
    added_by: str


@dataclass(frozen=True)
class Criterion:
    id: str
    text: str
    evidence: tuple[Evidence, ...] = ()


# Base fields a task type may require to be non-empty before a task goes to review.
REQUIRED_FIELD_NAMES: frozenset[str] = frozenset(
    {"description", "priority", "labels", "start_date", "due_date"}
)


@dataclass(frozen=True)
class TaskType:
    name: str
    required_fields: frozenset[str]
    criteria_template: tuple[str, ...] = ()


@dataclass(frozen=True)
class Task:
    """A task's state. `blocked_by` holds the ids of the tasks that block this one."""

    id: str
    title: str
    type: str
    project_id: str
    created_by: str
    parent_id: str | None = None
    status: Status = Status.PROPOSED
    priority: Priority = Priority.P2
    description: str = ""
    labels: tuple[str, ...] = ()
    start_date: date | None = None
    due_date: date | None = None
    recurrence: str | None = None
    criteria: tuple[Criterion, ...] = ()
    subtasks: tuple[SubtaskStatus, ...] = ()
    blocked_by: frozenset[str] = frozenset()
    assignee: str | None = None
    delivery_summary: str = ""
    working_notes: str = ""


class RequestKind(StrEnum):
    DELIVERY = "delivery"
    CANCELLATION = "cancellation"


class RequestState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ApprovalRequest:
    """A pull-request-like request the owner decides (design §6.6)."""

    task_id: str
    kind: RequestKind
    requested_by: str
    reason: str
    state: RequestState = RequestState.PENDING
    note: str | None = None
