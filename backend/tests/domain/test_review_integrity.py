"""Review findings of slice 2: a task in review cannot be quietly emptied or left half-resolved."""

from dataclasses import replace

import pytest

from kairos.domain.actor import Actor, ActorKind, AgentProfile
from kairos.domain.approval import decide_move_task, decide_resolve_request
from kairos.domain.changes import decide_create, decide_update_fields
from kairos.domain.decision import Allowed, GateCode, Rejected, RejectionCode
from kairos.domain.events import EventType
from kairos.domain.gates import GateContext
from kairos.domain.model import (
    ApprovalRequest,
    Criterion,
    Evidence,
    EvidenceKind,
    RequestKind,
    RequestState,
    Subtask,
    Task,
    TaskType,
)
from kairos.domain.status import Status, SubtaskStatus
from kairos.domain.subtasks import decide_add_subtask, decide_move_subtask

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
AGENT = Actor(ActorKind.AGENT, "a1")
CLEAR = GateContext(TaskType("bug", frozenset()), frozenset(), frozenset())
PROOF = Evidence(EvidenceKind.TEXT, "it works", "a1")
PROFILE = AgentProfile("a1", ActorKind.AGENT, frozenset({"bug"}), frozenset({"p1"}))


def _task(status: Status = Status.IN_REVIEW, **changes: object) -> Task:
    base = Task(
        id="t1",
        title="T",
        type="bug",
        project_id="p1",
        created_by="owner",
        status=status,
        assignee="a1",
        criteria=(Criterion("c1", "works", (PROOF,)),),
        delivery_summary="Done",
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def _delivery(**changes: object) -> ApprovalRequest:
    return replace(ApprovalRequest("t1", RequestKind.DELIVERY, "a1", "Done"), **changes)  # type: ignore[arg-type]


def _allowed(decision: object) -> Allowed:
    assert isinstance(decision, Allowed), decision
    return decision


def _rejected(decision: object, code: RejectionCode) -> Rejected:
    assert isinstance(decision, Rejected), decision
    assert decision.code is code, decision
    return decision


# --- 1. leaving review through a plain move closes the request ------------------------------


def test_returning_a_delivery_with_a_plain_move_rejects_its_request():
    moved = _allowed(
        decide_move_task(_task(), OWNER, Status.READY, CLEAR, _delivery(), reason="Redo the tests")
    )
    assert moved.task.status is Status.READY and moved.task.assignee == "a1"
    assert moved.request is not None
    assert moved.request.state is RequestState.REJECTED
    assert moved.request.note == "Redo the tests"
    resolved = [e for e in moved.events if e.type is EventType.APPROVAL_RESOLVED]
    assert [e.payload for e in resolved] == [{"kind": "delivery", "approved": False}]


def test_approving_with_a_plain_move_approves_the_request_and_the_subtasks_in_review():
    task = _task(subtasks=(Subtask("s1", "A", SubtaskStatus.IN_REVIEW),))
    moved = _allowed(decide_move_task(task, OWNER, Status.DONE, CLEAR, _delivery()))
    assert moved.task.status is Status.DONE
    assert [s.status for s in moved.task.subtasks] == [SubtaskStatus.DONE]
    assert moved.request is not None and moved.request.state is RequestState.APPROVED
    kinds = [e.type for e in moved.events]
    assert kinds == [
        EventType.STATUS_CHANGED,
        EventType.SUBTASK_STATUS_CHANGED,
        EventType.APPROVAL_RESOLVED,
    ]


@pytest.mark.parametrize("blocking", [SubtaskStatus.TODO, SubtaskStatus.IN_PROGRESS])
def test_a_task_with_open_subtasks_cannot_be_approved_by_any_door(blocking: SubtaskStatus):
    task = _task(subtasks=(Subtask("s1", "A", blocking),))
    by_move = _rejected(
        decide_move_task(task, OWNER, Status.DONE, CLEAR, _delivery()), RejectionCode.GATE_FAILED
    )
    by_request = _rejected(
        decide_resolve_request(task, _delivery(), OWNER, True, None, CLEAR),
        RejectionCode.GATE_FAILED,
    )
    for refusal in (by_move, by_request):
        assert [g.code for g in refusal.gates] == [GateCode.PENDING_SUBTASKS]


def test_rejecting_a_delivery_does_not_need_the_subtasks_to_be_closed():
    task = _task(subtasks=(Subtask("s1", "A", SubtaskStatus.TODO),))
    _allowed(decide_resolve_request(task, _delivery(), OWNER, False, "Redo", CLEAR))


def test_moving_backwards_out_of_review_closes_the_request_as_rejected():
    moved = _allowed(
        decide_move_task(_task(), OWNER, Status.BACKLOG, CLEAR, _delivery(), reason="Rethink")
    )
    assert moved.request is not None and moved.request.state is RequestState.REJECTED


def test_a_move_without_a_pending_request_is_just_the_transition():
    moved = _allowed(decide_move_task(_task(), OWNER, Status.READY, CLEAR, None, reason="Redo"))
    assert moved.request is None
    assert [e.type for e in moved.events] == [EventType.STATUS_CHANGED]


def test_submitting_for_review_still_creates_the_delivery_request():
    task = _task(Status.IN_PROGRESS)
    moved = _allowed(decide_move_task(task, AGENT, Status.IN_REVIEW, CLEAR, None))
    assert moved.request is not None and moved.request.state is RequestState.PENDING


def test_cancelling_a_task_approves_its_pending_cancellation_request():
    task = _task(Status.IN_PROGRESS)
    request = ApprovalRequest("t1", RequestKind.CANCELLATION, "a1", "Obsolete")
    moved = _allowed(decide_move_task(task, OWNER, Status.CANCELLED, CLEAR, request))
    assert moved.request is not None and moved.request.state is RequestState.APPROVED


def test_other_moves_leave_a_pending_cancellation_request_alone():
    task = _task(Status.IN_PROGRESS)
    request = ApprovalRequest("t1", RequestKind.CANCELLATION, "a1", "Obsolete")
    moved = _allowed(decide_move_task(task, OWNER, Status.BACKLOG, CLEAR, request))
    assert moved.request is None


def test_a_rejected_move_returns_the_rejection_unchanged():
    _rejected(
        decide_move_task(_task(), AGENT, Status.DONE, CLEAR, _delivery()),
        RejectionCode.NOT_PERMITTED,
    )


# --- 2. nobody but the owner touches subtasks while the owner reviews -----------------------


def test_the_orchestrator_cannot_add_or_move_subtasks_during_review():
    task = _task(subtasks=(Subtask("s1", "A", SubtaskStatus.IN_REVIEW),))
    _rejected(decide_add_subtask(task, ORCH, Subtask("s2", "B")), RejectionCode.WRONG_STATUS)
    _rejected(decide_move_subtask(task, ORCH, "s1", SubtaskStatus.TODO), RejectionCode.WRONG_STATUS)


def test_the_owner_still_edits_subtasks_during_review():
    task = _task(subtasks=(Subtask("s1", "A", SubtaskStatus.IN_REVIEW),))
    _allowed(decide_add_subtask(task, OWNER, Subtask("s2", "B")))
    _allowed(decide_move_subtask(task, OWNER, "s1", SubtaskStatus.TODO))


# --- 3. criterion ids are unique ------------------------------------------------------------


def test_duplicate_criterion_ids_are_refused_when_creating_and_when_editing():
    twin = (Criterion("c1", "a"), Criterion("c1", "b"))
    draft = Task(id="t9", title="T", type="bug", project_id="p1", created_by="a1", criteria=twin)
    _rejected(decide_create(OWNER, None, draft), RejectionCode.FIELD_NOT_ALLOWED)
    _rejected(decide_create(AGENT, PROFILE, draft), RejectionCode.FIELD_NOT_ALLOWED)
    backlog = _task(Status.BACKLOG, criteria=(), assignee=None)
    _rejected(
        decide_update_fields(backlog, OWNER, {"criteria": twin}), RejectionCode.FIELD_NOT_ALLOWED
    )


# --- 4. only the owner may remove a criterion that already has evidence ---------------------


def test_the_orchestrator_cannot_drop_a_criterion_that_carries_evidence():
    task = _task(
        Status.IN_PROGRESS, criteria=(Criterion("c1", "a"), Criterion("c2", "b", (PROOF,)))
    )
    kept = (Criterion("c1", "a"),)
    refusal = _rejected(
        decide_update_fields(task, ORCH, {"criteria": kept}), RejectionCode.FIELD_NOT_ALLOWED
    )
    assert "evidence" in refusal.message.lower()


def test_the_orchestrator_may_drop_a_criterion_without_evidence_and_the_owner_any():
    task = _task(
        Status.IN_PROGRESS, criteria=(Criterion("c1", "a"), Criterion("c2", "b", (PROOF,)))
    )
    _allowed(decide_update_fields(task, ORCH, {"criteria": (Criterion("c2", "b", (PROOF,)),)}))
    _allowed(decide_update_fields(task, OWNER, {"criteria": (Criterion("c1", "a"),)}))
