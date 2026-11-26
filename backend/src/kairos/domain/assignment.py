"""Assigning tasks to agents and the agent's queue (design §6.8).

Assigning already reserves: there is no separate reservation. The owner and the orchestrator
assign; the invariants below bind both of them.
"""

from collections.abc import Iterable
from dataclasses import replace

from kairos.domain.actor import Actor, ActorKind, AgentProfile
from kairos.domain.decision import Allowed, Decision, Rejected, RejectionCode
from kairos.domain.events import Event, EventType
from kairos.domain.model import Task, is_blank
from kairos.domain.status import Status

_ASSIGNERS = frozenset({ActorKind.OWNER, ActorKind.ORCHESTRATOR})
# Only these statuses take a slot in an agent's queue: a task in review waits for the owner.
_QUEUE_STATUSES = frozenset({Status.READY, Status.IN_PROGRESS})


def queue_load(tasks: Iterable[Task], agent_id: str) -> int:
    """How many of the agent's assigned tasks take a slot of its queue."""
    return sum(1 for t in tasks if t.assignee == agent_id and t.status in _QUEUE_STATUSES)


def decide_assign(task: Task, actor: Actor, agent: AgentProfile, load: int) -> Decision:
    """Assign a `READY` task to `agent`, whose current queue load is `load` (see `queue_load`)."""
    if actor.kind not in _ASSIGNERS:
        return Rejected(RejectionCode.NOT_PERMITTED, "Only the owner or the orchestrator assigns.")
    if task.status is not Status.READY:
        return Rejected(RejectionCode.WRONG_STATUS, "Only a ready task can be assigned.")
    if task.assignee is not None:
        return Rejected(RejectionCode.ALREADY_ASSIGNED, "The task already has an assignee.")
    if (
        task.type not in agent.allowed_task_types
        or task.project_id not in agent.allowed_project_ids
    ):
        return Rejected(RejectionCode.OUT_OF_SCOPE, "The task is outside the agent's scope.")
    if load >= agent.queue_limit:
        return Rejected(RejectionCode.QUEUE_FULL, "The agent's queue is full.")
    event = Event(EventType.ASSIGNED, task.id, actor, {"agent": agent.id})
    return Allowed(replace(task, assignee=agent.id), (event,))


def decide_unassign(task: Task, actor: Actor, reason: str | None) -> Decision:
    """Remove the assignee of a `READY` task, with a reason."""
    if actor.kind not in _ASSIGNERS:
        return Rejected(
            RejectionCode.NOT_PERMITTED, "Only the owner or the orchestrator unassigns."
        )
    if task.status is not Status.READY:
        return Rejected(RejectionCode.WRONG_STATUS, "Only a ready task can be unassigned.")
    if task.assignee is None:
        return Rejected(RejectionCode.NOT_ASSIGNED, "The task has no assignee.")
    if is_blank(reason):
        return Rejected(RejectionCode.REASON_REQUIRED, "A reason is required.")
    event = Event(EventType.UNASSIGNED, task.id, actor, {"agent": task.assignee}, reason)
    return Allowed(replace(task, assignee=None), (event,))
