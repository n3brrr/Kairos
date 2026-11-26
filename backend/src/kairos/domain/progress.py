"""Progress of tasks and containers, and the derived status of an epic (design §6.1, §6.5)."""

from collections.abc import Sequence
from dataclasses import dataclass

from kairos.domain.model import Task
from kairos.domain.status import CLOSED, EpicStatus, Status


@dataclass(frozen=True)
class ChildProgress:
    status: Status
    progress: float


def task_progress(task: Task) -> float:
    """1.0 when done; otherwise criteria with evidence over total (0.0 with no criteria)."""
    if task.status is Status.DONE:
        return 1.0
    if not task.criteria:
        return 0.0
    met = sum(1 for criterion in task.criteria if criterion.evidence)
    return met / len(task.criteria)


def container_progress(children: Sequence[ChildProgress]) -> float:
    """Unweighted mean over the non-cancelled children; 0.0 when there are none."""
    counted = [child.progress for child in children if child.status is not Status.CANCELLED]
    return sum(counted) / len(counted) if counted else 0.0


def epic_status(child_statuses: Sequence[Status]) -> EpicStatus:
    """Complete when every child is done or cancelled; in progress once any child has started."""
    if child_statuses and all(status in CLOSED for status in child_statuses):
        return EpicStatus.COMPLETE
    started = {Status.IN_PROGRESS, Status.IN_REVIEW, Status.DONE}
    if any(status in started for status in child_statuses):
        return EpicStatus.IN_PROGRESS
    return EpicStatus.NOT_STARTED
