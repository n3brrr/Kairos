"""Stored statuses of items (design §6.3). "Blocked" is derived, never stored."""

from enum import StrEnum


class Status(StrEnum):
    PROPOSED = "proposed"
    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    CANCELLED = "cancelled"


# The forward lifecycle. `CANCELLED` is outside it: it can be reached from any open status.
ORDER: tuple[Status, ...] = (
    Status.PROPOSED,
    Status.BACKLOG,
    Status.READY,
    Status.IN_PROGRESS,
    Status.IN_REVIEW,
    Status.DONE,
)

CLOSED: frozenset[Status] = frozenset({Status.DONE, Status.CANCELLED})


class SubtaskStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"


class EpicStatus(StrEnum):
    """Derived from an epic's children, never stored (design §6.1)."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    QUEUED = "queued"
    PAUSED = "paused"
    ARCHIVED = "archived"
