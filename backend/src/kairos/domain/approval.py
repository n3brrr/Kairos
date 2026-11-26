"""Approval requests: the pull-request-like way agents ask the owner to decide (design §6.6).

Moving a task to `IN_REVIEW` already creates the delivery request (see `decide_transition`).
An agent that wants to cancel or close a task creates a cancellation request here. Only the
owner resolves a request.
"""

from dataclasses import replace

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.decision import Allowed, Decision, Rejected, RejectionCode
from kairos.domain.events import Event, EventType
from kairos.domain.gates import GateContext
from kairos.domain.model import ApprovalRequest, RequestKind, RequestState, Task, is_blank
from kairos.domain.policy import decide_transition
from kairos.domain.status import CLOSED, Status


def decide_request_cancellation(
    task: Task, actor: Actor, reason: str | None, pending_exists: bool
) -> Decision:
    """The agent carrying `task` asks the owner to cancel it. The task itself does not change."""
    if actor.kind is not ActorKind.AGENT:
        return Rejected(
            RejectionCode.NOT_PERMITTED, "Only the assigned agent requests cancellation."
        )
    if task.assignee != actor.id:
        return Rejected(RejectionCode.NOT_ASSIGNED, "The task is not assigned to this agent.")
    if task.status in CLOSED:
        return Rejected(RejectionCode.WRONG_STATUS, "The task is already closed.")
    if reason is None or is_blank(reason):
        return Rejected(RejectionCode.REASON_REQUIRED, "A cancellation request needs a reason.")
    if pending_exists:
        return Rejected(RejectionCode.DUPLICATE_REQUEST, "A request is already pending.")
    request = ApprovalRequest(task.id, RequestKind.CANCELLATION, actor.id, reason)
    event = Event(
        EventType.APPROVAL_REQUESTED,
        task.id,
        actor,
        {"kind": RequestKind.CANCELLATION.value},
        reason,
    )
    return Allowed(task, (event,), request=request)


def decide_resolve_request(
    task: Task,
    request: ApprovalRequest,
    actor: Actor,
    approve: bool,
    note: str | None,
    ctx: GateContext,
) -> Decision:
    """The owner approves or rejects a pending request; rejecting needs a note.

    Approving a delivery marks the task `DONE`; rejecting it returns it to `READY`, keeping the
    assignment. Approving a cancellation cancels the task; rejecting it changes nothing.
    """
    if request.task_id != task.id:
        raise ValueError(f"request for {request.task_id} resolved against task {task.id}")
    if actor.kind is not ActorKind.OWNER:
        return Rejected(RejectionCode.NOT_PERMITTED, "Only the owner resolves requests.")
    if request.state is not RequestState.PENDING:
        return Rejected(RejectionCode.REQUEST_NOT_PENDING, "The request was already resolved.")
    if not approve and (note is None or is_blank(note)):
        return Rejected(RejectionCode.REASON_REQUIRED, "Rejecting a request needs a note.")

    target: Status | None
    if request.kind is RequestKind.DELIVERY:
        target = Status.DONE if approve else Status.READY
    else:
        target = Status.CANCELLED if approve else None

    new_task, events, warnings = task, [], ()
    if target is not None:
        moved = decide_transition(task, actor, target, ctx, reason=note)
        if isinstance(moved, Rejected):
            return moved
        new_task, events, warnings = moved.task, list(moved.events), moved.warnings
    state = RequestState.APPROVED if approve else RequestState.REJECTED
    events.append(
        Event(
            EventType.APPROVAL_RESOLVED,
            task.id,
            actor,
            {"kind": request.kind.value, "approved": approve},
            note,
        )
    )
    return Allowed(new_task, tuple(events), warnings, replace(request, state=state, note=note))
