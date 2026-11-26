"""The scenarios an independent review ran against the services, as regression tests."""

from collections.abc import Callable

import pytest

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.decision import Allowed, Rejected, RejectionCode
from kairos.domain.model import (
    ApprovalRequest,
    Criterion,
    Evidence,
    EvidenceKind,
    RequestKind,
    Subtask,
    Task,
)
from kairos.domain.status import Status, SubtaskStatus

from .support import Env

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
A1 = Actor(ActorKind.AGENT, "a1")
PROOF = Evidence(EvidenceKind.TEXT, "the proof content", "a1")

MakeTask = Callable[..., Task]


def _in_review(make_task: MakeTask, **changes: object) -> Task:
    fields: dict[str, object] = {
        "status": Status.IN_REVIEW,
        "assignee": "a1",
        "criteria": (Criterion("c1", "works", (PROOF,)),),
        "delivery_summary": "Done",
    }
    return make_task(**{**fields, **changes})


def _submitted(env: Env, make_task: MakeTask, **changes: object) -> None:
    env.put(_in_review(make_task, **changes))
    env.put_request(ApprovalRequest("t1", RequestKind.DELIVERY, "a1", "Done"))


def _ok(decision: object) -> Allowed:
    assert isinstance(decision, Allowed), decision
    return decision


def _no(decision: object, code: RejectionCode) -> Rejected:
    assert isinstance(decision, Rejected), decision
    assert decision.code is code, decision
    return decision


# --- returning or approving with a plain move resolves the request ------------------------


def test_returning_a_delivery_with_a_move_lets_the_agent_resubmit(env: Env, make_task: MakeTask):
    _submitted(env, make_task)
    _ok(env.service.move_task(OWNER, "t1", Status.READY, reason="Redo the tests"))
    assert env.pending("t1") is None
    _ok(env.service.move_task(A1, "t1", Status.IN_PROGRESS))
    _ok(env.service.move_task(A1, "t1", Status.IN_REVIEW))  # was DUPLICATE_REQUEST before
    assert env.pending("t1") is not None
    assert env.queries.pending_requests(OWNER)[0].task_id == "t1"
    assert env.verify().ok


def test_approving_with_a_move_leaves_nothing_pending_and_approves_the_subtasks(
    env: Env, make_task: MakeTask
):
    _submitted(env, make_task, subtasks=(Subtask("s1", "A", SubtaskStatus.IN_REVIEW),))
    _ok(env.service.move_task(OWNER, "t1", Status.DONE))
    task = env.task("t1")
    assert task is not None and task.status is Status.DONE
    assert [s.status for s in task.subtasks] == [SubtaskStatus.DONE]
    assert env.pending("t1") is None
    assert env.queries.pending_requests(OWNER) == []
    _no(
        env.service.resolve_request(OWNER, "t1", False, "Too late"),
        RejectionCode.REQUEST_NOT_PENDING,
    )


@pytest.mark.parametrize("blocking", [SubtaskStatus.TODO, SubtaskStatus.IN_PROGRESS])
def test_open_subtasks_block_approval_through_both_doors(
    env: Env, make_task: MakeTask, blocking: SubtaskStatus
):
    _submitted(env, make_task, subtasks=(Subtask("s1", "A", blocking),))
    before = env.snapshot()
    _no(env.service.move_task(OWNER, "t1", Status.DONE), RejectionCode.GATE_FAILED)
    _no(env.service.resolve_request(OWNER, "t1", True, None), RejectionCode.GATE_FAILED)
    assert env.snapshot() == before


def test_the_orchestrator_cannot_reopen_subtasks_while_the_owner_reviews(
    env: Env, make_task: MakeTask
):
    _submitted(env, make_task, subtasks=(Subtask("s1", "A", SubtaskStatus.IN_REVIEW),))
    before = env.snapshot()
    _no(env.service.move_subtask(ORCH, "t1", "s1", SubtaskStatus.TODO), RejectionCode.WRONG_STATUS)
    _no(env.service.add_subtask(ORCH, "t1", Subtask("s2", "Late")), RejectionCode.WRONG_STATUS)
    assert env.snapshot() == before


# --- criteria ----------------------------------------------------------------------------


def test_duplicate_criterion_ids_are_a_rejection_not_a_database_error(
    env: Env, make_task: MakeTask
):
    twin = (Criterion("c1", "a"), Criterion("c1", "b"))
    before = env.snapshot()
    _no(
        env.service.create_task(OWNER, make_task(id="t9", criteria=twin)),
        RejectionCode.FIELD_NOT_ALLOWED,
    )
    assert env.snapshot() == before
    env.put(make_task(status=Status.BACKLOG))
    before = env.snapshot()
    _no(env.service.update_fields(OWNER, "t1", {"criteria": twin}), RejectionCode.FIELD_NOT_ALLOWED)
    assert env.snapshot() == before


def test_the_orchestrator_cannot_delete_evidence_by_dropping_its_criterion(
    env: Env, make_task: MakeTask
):
    env.put(
        make_task(
            status=Status.IN_PROGRESS,
            assignee="a1",
            criteria=(Criterion("c1", "a"), Criterion("c2", "b", (PROOF,))),
        )
    )
    before = env.snapshot()
    _no(
        env.service.update_fields(ORCH, "t1", {"criteria": (Criterion("c1", "a"),)}),
        RejectionCode.FIELD_NOT_ALLOWED,
    )
    assert env.snapshot() == before
    task = env.task("t1")
    assert task is not None and task.criteria[1].evidence == (PROOF,)


# --- the boundary test left these out ------------------------------------------------------


@pytest.mark.parametrize("actor", [A1, ORCH], ids=["agent", "orchestrator"])
@pytest.mark.parametrize("status", [Status.DONE, Status.CANCELLED, Status.IN_PROGRESS])
def test_a_draft_cannot_be_created_already_closed_or_assigned(
    env: Env, make_task: MakeTask, actor: Actor, status: Status
):
    result = env.service.create_task(
        actor, make_task(id="t9", created_by=actor.id, status=status, assignee="a1")
    )
    created = _ok(result)  # allowed, but only as an unassigned proposal
    assert created.task.status is Status.PROPOSED and created.task.assignee is None
    stored = env.task("t9")
    assert stored is not None and stored.status is Status.PROPOSED and stored.assignee is None


@pytest.mark.parametrize("actor", [A1, ORCH], ids=["agent", "orchestrator"])
@pytest.mark.parametrize("closed", [SubtaskStatus.DONE, SubtaskStatus.CANCELLED])
def test_subtasks_cannot_be_created_already_approved_or_cancelled(
    env: Env, make_task: MakeTask, actor: Actor, closed: SubtaskStatus
):
    before = env.snapshot()
    _no(
        env.service.create_task(
            actor, make_task(id="t9", created_by=actor.id, subtasks=(Subtask("s1", "A", closed),))
        ),
        RejectionCode.FIELD_NOT_ALLOWED,
    )
    env.put(make_task(status=Status.BACKLOG))
    before = env.snapshot()
    _no(
        env.service.add_subtask(ORCH, "t1", Subtask("s9", "B", closed)),
        RejectionCode.FIELD_NOT_ALLOWED,
    )
    assert env.snapshot() == before
