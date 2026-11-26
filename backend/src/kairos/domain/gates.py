"""Automatic gates a status transition must pass (design §6.4)."""

from dataclasses import dataclass

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.decision import GateCode, GateFailure
from kairos.domain.model import Task, TaskType, is_blank
from kairos.domain.status import SUBTASK_OPEN, Status


@dataclass(frozen=True)
class GateContext:
    """What the gates need to know about the world, computed by the use case.

    `other_in_progress` holds the ids of the *other* `IN_PROGRESS` tasks of the agent who would
    carry the task: the acting agent, or the task's assignee when someone else moves it.
    `cancelled_blockers` only produces warnings (design §6.7); it is not a gate.
    """

    task_type: TaskType
    open_blockers: frozenset[str]
    other_in_progress: frozenset[str]
    cancelled_blockers: frozenset[str] = frozenset()


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return not is_blank(value)
    if isinstance(value, tuple):
        return len(value) > 0  # pyright: ignore[reportUnknownArgumentType]
    return True


def _missing_required_fields(task: Task, task_type: TaskType) -> list[str]:
    """Required field names with no value. A name the task does not have fails closed."""
    return sorted(
        name for name in task_type.required_fields if not _has_value(getattr(task, name, None))
    )


def check_gates(
    task: Task, target: Status, actor: Actor, ctx: GateContext
) -> tuple[GateFailure, ...]:
    """Every gate failure for moving `task` to `target`; empty when the gates hold."""
    failures: list[GateFailure] = []

    def fail(code: GateCode, message: str) -> None:
        failures.append(GateFailure(code, message))

    if target is Status.READY and not task.criteria:
        fail(GateCode.NO_CRITERIA, "A task needs at least one acceptance criterion to be ready.")

    if target is Status.IN_PROGRESS:
        if ctx.open_blockers:
            fail(GateCode.OPEN_DEPENDENCIES, _blocked_message(ctx))
        if actor.kind is ActorKind.AGENT and task.assignee != actor.id:
            fail(GateCode.NOT_ASSIGNED_TO_ACTOR, "The task is not assigned to this agent.")
        # One `IN_PROGRESS` task per agent binds whoever moves the task, the owner included.
        if ctx.other_in_progress and (actor.kind is ActorKind.AGENT or task.assignee is not None):
            fail(GateCode.AGENT_BUSY, "The agent already has a task in progress.")

    if target is Status.IN_REVIEW:
        missing = _missing_required_fields(task, ctx.task_type)
        if missing:
            fail(
                GateCode.MISSING_REQUIRED_FIELDS,
                f"Required fields are empty: {', '.join(missing)}.",
            )
        if not task.criteria or any(not criterion.evidence for criterion in task.criteria):
            fail(
                GateCode.CRITERIA_WITHOUT_EVIDENCE,
                "The task needs at least one criterion, and every criterion needs evidence.",
            )
        if any(subtask.status in SUBTASK_OPEN for subtask in task.subtasks):
            fail(GateCode.PENDING_SUBTASKS, "Every subtask must be in review, done or cancelled.")
        if ctx.open_blockers:
            fail(GateCode.OPEN_DEPENDENCIES, _blocked_message(ctx))
        if is_blank(task.delivery_summary):
            fail(GateCode.EMPTY_DELIVERY_SUMMARY, "A delivery summary is required.")

    return tuple(failures)


def _blocked_message(ctx: GateContext) -> str:
    return f"Open dependencies: {', '.join(sorted(ctx.open_blockers))}."
