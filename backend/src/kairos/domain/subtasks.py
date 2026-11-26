"""Subtasks: adding them and moving them across the kanban (design §6.1).

Whoever carries the task carries its subtasks, so the owner, the orchestrator and the assigned
agent (a subagent included) move them among `TODO`, `IN_PROGRESS` and `IN_REVIEW`. Approving
(`DONE`), cancelling and reopening are the owner's, exactly as for tasks (golden rule 2). The
permissions are one data table (`SUBTASK_RULES`); `decide_move_subtask` interprets it.
"""

from dataclasses import dataclass, replace

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.decision import Allowed, Decision, Rejected, RejectionCode
from kairos.domain.events import Event, EventType
from kairos.domain.model import Subtask, Task, is_blank
from kairos.domain.status import CLOSED, Status, SubtaskStatus

_OWNER = frozenset({ActorKind.OWNER})
_WORKERS = frozenset({ActorKind.OWNER, ActorKind.ORCHESTRATOR, ActorKind.AGENT})
_DEFINERS = frozenset({ActorKind.OWNER, ActorKind.ORCHESTRATOR})
_WORKING = (SubtaskStatus.TODO, SubtaskStatus.IN_PROGRESS, SubtaskStatus.IN_REVIEW)


@dataclass(frozen=True)
class SubtaskRule:
    source: SubtaskStatus
    target: SubtaskStatus
    actors: frozenset[ActorKind]
    requires_reason: bool = False


def _build_rules() -> tuple[SubtaskRule, ...]:
    rules: list[SubtaskRule] = []
    for source in _WORKING:
        rules.extend(
            SubtaskRule(source, target, _WORKERS) for target in _WORKING if target is not source
        )
        rules.append(SubtaskRule(source, SubtaskStatus.DONE, _OWNER))
        rules.append(SubtaskRule(source, SubtaskStatus.CANCELLED, _OWNER))
    for closed in (SubtaskStatus.DONE, SubtaskStatus.CANCELLED):
        rules.append(SubtaskRule(closed, SubtaskStatus.TODO, _OWNER, requires_reason=True))
    return tuple(rules)


SUBTASK_RULES: tuple[SubtaskRule, ...] = _build_rules()
_RULES: dict[tuple[SubtaskStatus, SubtaskStatus], SubtaskRule] = {
    (rule.source, rule.target): rule for rule in SUBTASK_RULES
}


def _not_permitted(message: str) -> Rejected:
    return Rejected(RejectionCode.NOT_PERMITTED, message)


def _reviewing(task: Task, actor: Actor) -> Rejected | None:
    """While the owner reviews a delivery, its subtasks are fixed for everybody else."""
    if task.status is Status.IN_REVIEW and actor.kind is not ActorKind.OWNER:
        return Rejected(
            RejectionCode.WRONG_STATUS, "The owner is reviewing this task: its subtasks are fixed."
        )
    return None


def decide_add_subtask(task: Task, actor: Actor, subtask: Subtask) -> Decision:
    """Add a `TODO` subtask: the owner or orchestrator, or an agent inside its own proposal."""
    drafting = (
        actor.kind is ActorKind.AGENT
        and task.status is Status.PROPOSED
        and task.created_by == actor.id
    )
    if actor.kind not in _DEFINERS and not drafting:
        return _not_permitted("This actor cannot add subtasks to this task.")
    if task.status in CLOSED:
        return Rejected(RejectionCode.WRONG_STATUS, "A closed task takes no new subtasks.")
    if (refusal := _reviewing(task, actor)) is not None:
        return refusal
    if is_blank(subtask.title):
        return Rejected(RejectionCode.EMPTY_TEXT, "A subtask needs a title.")
    if subtask.status is not SubtaskStatus.TODO:
        return Rejected(RejectionCode.FIELD_NOT_ALLOWED, "A new subtask starts as todo.")
    if any(existing.id == subtask.id for existing in task.subtasks):
        return Rejected(RejectionCode.DUPLICATE_SUBTASK, f"Subtask {subtask.id} already exists.")
    event = Event(
        EventType.SUBTASK_ADDED,
        task.id,
        actor,
        {"subtask": subtask.id, "title": subtask.title},
    )
    return Allowed(replace(task, subtasks=(*task.subtasks, subtask)), (event,))


def decide_move_subtask(
    task: Task,
    actor: Actor,
    subtask_id: str,
    target: SubtaskStatus,
    *,
    reason: str | None = None,
) -> Decision:
    """Move one subtask to `target`, if the actor may and the rule's conditions hold."""
    if actor.kind is ActorKind.SYSTEM:
        return _not_permitted("The system actor cannot move subtasks yet.")
    if actor.kind is ActorKind.AGENT:
        if task.assignee != actor.id:
            return Rejected(RejectionCode.NOT_ASSIGNED, "The task is not assigned to this agent.")
        if task.status is not Status.IN_PROGRESS:
            return Rejected(
                RejectionCode.WRONG_STATUS, "Subtasks move while the task is in progress."
            )
    if task.status in CLOSED:
        return Rejected(RejectionCode.WRONG_STATUS, "The subtasks of a closed task are fixed.")
    if (refusal := _reviewing(task, actor)) is not None:
        return refusal
    current = next((s for s in task.subtasks if s.id == subtask_id), None)
    if current is None:
        return Rejected(RejectionCode.UNKNOWN_SUBTASK, f"No subtask {subtask_id} on this task.")
    rule = _RULES.get((current.status, target))
    if rule is None:
        return Rejected(
            RejectionCode.INVALID_TRANSITION,
            f"A subtask cannot move from {current.status.value} to {target.value}.",
        )
    if actor.kind not in rule.actors:
        return _not_permitted("This actor cannot make that subtask move.")
    if rule.requires_reason and is_blank(reason):
        return Rejected(RejectionCode.REASON_REQUIRED, "Reopening a subtask needs a reason.")
    moved = replace(current, status=target)
    subtasks = tuple(moved if s.id == subtask_id else s for s in task.subtasks)
    event = Event(
        EventType.SUBTASK_STATUS_CHANGED,
        task.id,
        actor,
        {"subtask": subtask_id, "from": current.status.value, "to": target.value},
        reason,
    )
    return Allowed(replace(task, subtasks=subtasks), (event,))


def approve_pending_subtasks(task: Task, actor: Actor) -> tuple[Task, tuple[Event, ...]]:
    """Approve every subtask still `IN_REVIEW`, one event each (the owner approved the delivery)."""
    events: list[Event] = []
    subtasks: list[Subtask] = []
    for subtask in task.subtasks:
        if subtask.status is SubtaskStatus.IN_REVIEW:
            subtask = replace(subtask, status=SubtaskStatus.DONE)
            events.append(
                Event(
                    EventType.SUBTASK_STATUS_CHANGED,
                    task.id,
                    actor,
                    {"subtask": subtask.id, "from": "in_review", "to": "done"},
                )
            )
        subtasks.append(subtask)
    return replace(task, subtasks=tuple(subtasks)), tuple(events)
