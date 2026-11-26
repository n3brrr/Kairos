"""Dependencies between tasks and the derived "blocked" state (design §6.3, §6.7).

Edges point from a task to the tasks that block it (`Task.blocked_by`).
"""

from collections.abc import Mapping

from kairos.domain.model import Task
from kairos.domain.status import CLOSED, Status


def would_create_cycle(
    blocked_by: Mapping[str, frozenset[str]], blocker_id: str, blocked_id: str
) -> bool:
    """True if "`blocked_id` is blocked by `blocker_id`" would close a loop (including a self-edge).

    The loop closes when `blocked_id` is already reachable from `blocker_id` by following blockers.
    """
    if blocker_id == blocked_id:
        return True
    seen: set[str] = set()
    pending = [blocker_id]
    while pending:
        current = pending.pop()
        if current == blocked_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(blocked_by.get(current, frozenset()))
    return False


def open_blockers(task: Task, statuses: Mapping[str, Status]) -> frozenset[str]:
    """Blockers that are not done or cancelled. A blocker with an unknown status counts as open."""
    return frozenset(
        blocker
        for blocker in task.blocked_by
        if statuses.get(blocker) is None or statuses[blocker] not in CLOSED
    )


def cancelled_blockers(task: Task, statuses: Mapping[str, Status]) -> frozenset[str]:
    """Blockers that were cancelled: they count as resolved, but the owner is warned."""
    return frozenset(b for b in task.blocked_by if statuses.get(b) is Status.CANCELLED)


def is_blocked(task: Task, statuses: Mapping[str, Status]) -> bool:
    return bool(open_blockers(task, statuses))
