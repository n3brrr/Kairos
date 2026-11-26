from dataclasses import replace

import pytest

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.approval import decide_request_cancellation, decide_resolve_request
from kairos.domain.decision import Allowed, Rejected, RejectionCode
from kairos.domain.events import EventType
from kairos.domain.gates import GateContext
from kairos.domain.model import ApprovalRequest, RequestKind, RequestState, Task, TaskType
from kairos.domain.status import Status

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
AGENT = Actor(ActorKind.AGENT, "a1")
OTHER = Actor(ActorKind.AGENT, "a2")
SYSTEM = Actor(ActorKind.SYSTEM, "sys")
CLEAR = GateContext(TaskType("bug", frozenset()), frozenset(), frozenset())


def _task(status: Status = Status.IN_PROGRESS, **changes: object) -> Task:
    base = Task(
        id="t1",
        title="T",
        type="bug",
        project_id="p1",
        created_by="owner",
        status=status,
        assignee="a1",
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def _request(kind: RequestKind = RequestKind.DELIVERY, **changes: object) -> ApprovalRequest:
    base = ApprovalRequest("t1", kind, "a1", "because")
    return replace(base, **changes)  # type: ignore[arg-type]


def _ok(decision: object) -> Allowed:
    assert isinstance(decision, Allowed), decision
    return decision


def _code(decision: object) -> RejectionCode:
    assert isinstance(decision, Rejected), decision
    return decision.code


# --- request cancellation -------------------------------------------------------------------


def test_the_assignee_requests_a_cancellation():
    allowed = _ok(decide_request_cancellation(_task(), AGENT, "obsolete", pending_exists=False))
    assert allowed.task == _task()
    assert allowed.request == ApprovalRequest("t1", RequestKind.CANCELLATION, "a1", "obsolete")
    assert [e.type for e in allowed.events] == [EventType.APPROVAL_REQUESTED]


def test_only_the_assignee_requests_cancellation():
    other = decide_request_cancellation(_task(), OTHER, "x", pending_exists=False)
    assert _code(other) is RejectionCode.NOT_ASSIGNED
    for actor in (OWNER, ORCH, SYSTEM):
        decision = decide_request_cancellation(_task(), actor, "x", pending_exists=False)
        assert _code(decision) is RejectionCode.NOT_PERMITTED


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_cancellation_needs_a_reason(reason: str | None):
    decision = decide_request_cancellation(_task(), AGENT, reason, pending_exists=False)
    assert _code(decision) is RejectionCode.REASON_REQUIRED


def test_duplicate_pending_request_is_rejected():
    decision = decide_request_cancellation(_task(), AGENT, "x", pending_exists=True)
    assert _code(decision) is RejectionCode.DUPLICATE_REQUEST


def test_a_closed_task_cannot_be_cancelled_again():
    decision = decide_request_cancellation(_task(Status.DONE), AGENT, "x", pending_exists=False)
    assert _code(decision) is RejectionCode.WRONG_STATUS


# --- resolve --------------------------------------------------------------------------------


@pytest.mark.parametrize("actor", [AGENT, OTHER, ORCH, SYSTEM])
@pytest.mark.parametrize("approve", [True, False])
@pytest.mark.parametrize("kind", list(RequestKind))
def test_only_the_owner_resolves_requests(actor: Actor, approve: bool, kind: RequestKind):
    task = _task(Status.IN_REVIEW)
    decision = decide_resolve_request(task, _request(kind), actor, approve, "note", CLEAR)
    assert _code(decision) is RejectionCode.NOT_PERMITTED


def test_approving_a_delivery_marks_done():
    task = _task(Status.IN_REVIEW)
    allowed = _ok(decide_resolve_request(task, _request(), OWNER, True, None, CLEAR))
    assert allowed.task.status is Status.DONE
    assert allowed.task.assignee == "a1"
    assert allowed.request is not None and allowed.request.state is RequestState.APPROVED
    types = {e.type for e in allowed.events}
    assert {EventType.STATUS_CHANGED, EventType.APPROVAL_RESOLVED} <= types


def test_rejecting_a_delivery_needs_a_note_and_returns_to_ready():
    task = _task(Status.IN_REVIEW)
    for blank in (None, "", "  "):
        decision = decide_resolve_request(task, _request(), OWNER, False, blank, CLEAR)
        assert _code(decision) is RejectionCode.REASON_REQUIRED
    allowed = _ok(decide_resolve_request(task, _request(), OWNER, False, "retest it", CLEAR))
    assert allowed.task.status is Status.READY
    assert allowed.task.assignee == "a1"  # returning a delivery keeps the assignment
    assert allowed.request is not None
    assert allowed.request.state is RequestState.REJECTED and allowed.request.note == "retest it"


def test_approving_a_cancellation_cancels_and_clears_the_assignment():
    request = _request(RequestKind.CANCELLATION)
    allowed = _ok(decide_resolve_request(_task(), request, OWNER, True, None, CLEAR))
    assert allowed.task.status is Status.CANCELLED
    assert allowed.task.assignee is None
    assert allowed.request is not None and allowed.request.state is RequestState.APPROVED


def test_rejecting_a_cancellation_changes_nothing_but_needs_a_note():
    request = _request(RequestKind.CANCELLATION)
    refused = decide_resolve_request(_task(), request, OWNER, False, None, CLEAR)
    assert _code(refused) is RejectionCode.REASON_REQUIRED
    allowed = _ok(decide_resolve_request(_task(), request, OWNER, False, "keep going", CLEAR))
    assert allowed.task == _task()
    assert allowed.request is not None and allowed.request.state is RequestState.REJECTED
    assert [e.type for e in allowed.events] == [EventType.APPROVAL_RESOLVED]


def test_resolving_twice_is_rejected():
    for state in (RequestState.APPROVED, RequestState.REJECTED):
        decision = decide_resolve_request(
            _task(Status.IN_REVIEW), _request(state=state), OWNER, True, None, CLEAR
        )
        assert _code(decision) is RejectionCode.REQUEST_NOT_PENDING


def test_a_request_for_another_task_is_a_programming_error():
    with pytest.raises(ValueError):
        decide_resolve_request(_task(), _request(task_id="other"), OWNER, True, None, CLEAR)
