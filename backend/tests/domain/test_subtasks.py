from dataclasses import replace

import pytest

from kairos.domain.actor import Actor, ActorKind, AgentProfile
from kairos.domain.approval import decide_resolve_request
from kairos.domain.changes import decide_create, decide_update_fields
from kairos.domain.decision import Allowed, Rejected, RejectionCode
from kairos.domain.events import EventType
from kairos.domain.gates import GateContext
from kairos.domain.model import ApprovalRequest, RequestKind, Subtask, Task, TaskType
from kairos.domain.status import Status, SubtaskStatus
from kairos.domain.subtasks import decide_add_subtask, decide_move_subtask

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
AGENT = Actor(ActorKind.AGENT, "a1")
SUBAGENT = Actor(ActorKind.AGENT, "a1", via="reviewer-sub")
OTHER = Actor(ActorKind.AGENT, "a2")
SYSTEM = Actor(ActorKind.SYSTEM, "sys")
TODO, DOING, REVIEW, DONE, CANCELLED = (
    SubtaskStatus.TODO,
    SubtaskStatus.IN_PROGRESS,
    SubtaskStatus.IN_REVIEW,
    SubtaskStatus.DONE,
    SubtaskStatus.CANCELLED,
)
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


def _with(subtask_status: SubtaskStatus, status: Status = Status.IN_PROGRESS) -> Task:
    return _task(status, subtasks=(Subtask("s1", "Step", subtask_status),))


def _ok(decision: object) -> Allowed:
    assert isinstance(decision, Allowed), decision
    return decision


def _rejected(decision: object, code: RejectionCode) -> None:
    assert isinstance(decision, Rejected), decision
    assert decision.code is code, decision


# The expected matrix, written out by hand from the plan (Task 1): who may move a subtask
# from `source` to `target`. The agent column assumes it carries the task while it is in progress.
_WORKING = (TODO, DOING, REVIEW)
_ALL = (TODO, DOING, REVIEW, DONE, CANCELLED)
_WORKERS = frozenset({ActorKind.OWNER, ActorKind.ORCHESTRATOR, ActorKind.AGENT})


def _expected_actors(source: SubtaskStatus, target: SubtaskStatus) -> frozenset[ActorKind]:
    if source in _WORKING and target in _WORKING:
        return _WORKERS
    if source in _WORKING and target in (DONE, CANCELLED):
        return frozenset({ActorKind.OWNER})
    if source in (DONE, CANCELLED) and target is TODO:
        return frozenset({ActorKind.OWNER})
    return frozenset()


_CASES = [(s, t) for s in _ALL for t in _ALL if s is not t]
_ACTORS = {ActorKind.OWNER: OWNER, ActorKind.ORCHESTRATOR: ORCH, ActorKind.AGENT: AGENT}


@pytest.mark.parametrize(("source", "target"), _CASES)
@pytest.mark.parametrize("kind", list(_ACTORS))
def test_move_matrix(kind: ActorKind, source: SubtaskStatus, target: SubtaskStatus):
    decision = decide_move_subtask(_with(source), _ACTORS[kind], "s1", target, reason="because")
    allowed = _expected_actors(source, target)
    if kind in allowed:
        moved = _ok(decision)
        assert moved.task.subtasks == (Subtask("s1", "Step", target),)
        (event,) = moved.events
        assert event.type is EventType.SUBTASK_STATUS_CHANGED
        assert event.payload == {"subtask": "s1", "from": source.value, "to": target.value}
        assert event.entity_id == "t1"
    else:
        _rejected(
            decision, RejectionCode.NOT_PERMITTED if allowed else RejectionCode.INVALID_TRANSITION
        )


def test_system_actor_cannot_move_a_subtask():
    _rejected(decide_move_subtask(_with(TODO), SYSTEM, "s1", DOING), RejectionCode.NOT_PERMITTED)


def test_a_subagent_moves_a_subtask_and_the_event_names_it():
    moved = _ok(decide_move_subtask(_with(TODO), SUBAGENT, "s1", DOING))
    assert moved.events[0].actor.via == "reviewer-sub"


def test_agent_must_carry_the_task():
    _rejected(decide_move_subtask(_with(TODO), OTHER, "s1", DOING), RejectionCode.NOT_ASSIGNED)


@pytest.mark.parametrize("status", [Status.READY, Status.IN_REVIEW, Status.DONE])
def test_agent_moves_subtasks_only_while_the_task_is_in_progress(status: Status):
    _rejected(
        decide_move_subtask(_with(TODO, status=status), AGENT, "s1", DOING),
        RejectionCode.WRONG_STATUS,
    )


@pytest.mark.parametrize("status", [Status.DONE, Status.CANCELLED])
@pytest.mark.parametrize("actor", [OWNER, ORCH])
def test_nobody_moves_subtasks_of_a_closed_task(actor: Actor, status: Status):
    _rejected(
        decide_move_subtask(_with(TODO, status=status), actor, "s1", DOING, reason="r"),
        RejectionCode.WRONG_STATUS,
    )


def test_the_orchestrator_moves_subtasks_of_an_unstarted_task():
    _ok(decide_move_subtask(_with(TODO, status=Status.READY), ORCH, "s1", DOING))


def test_unknown_subtask_is_rejected():
    _rejected(decide_move_subtask(_with(TODO), OWNER, "nope", DOING), RejectionCode.UNKNOWN_SUBTASK)


@pytest.mark.parametrize("source", [DONE, CANCELLED])
@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reopening_needs_a_reason(source: SubtaskStatus, reason: str | None):
    _rejected(
        decide_move_subtask(_with(source), OWNER, "s1", TODO, reason=reason),
        RejectionCode.REASON_REQUIRED,
    )


def test_moving_leaves_the_other_subtasks_alone():
    task = _task(subtasks=(Subtask("s1", "A"), Subtask("s2", "B"), Subtask("s3", "C")))
    moved = _ok(decide_move_subtask(task, AGENT, "s2", DOING))
    assert [s.status for s in moved.task.subtasks] == [TODO, DOING, TODO]
    assert [s.id for s in moved.task.subtasks] == ["s1", "s2", "s3"]


# --- adding


def test_the_owner_adds_a_subtask():
    added = _ok(decide_add_subtask(_task(), OWNER, Subtask("s1", "Step")))
    assert added.task.subtasks == (Subtask("s1", "Step", TODO),)
    assert added.events[0].type is EventType.SUBTASK_ADDED
    assert added.events[0].payload == {"subtask": "s1", "title": "Step"}


def test_the_orchestrator_adds_a_subtask():
    _ok(decide_add_subtask(_task(Status.READY), ORCH, Subtask("s1", "Step")))


def test_an_agent_cannot_add_a_subtask_to_an_assigned_task():
    _rejected(
        decide_add_subtask(_task(), AGENT, Subtask("s1", "Step")), RejectionCode.NOT_PERMITTED
    )


def test_an_agent_drafts_subtasks_inside_its_own_proposal():
    proposal = _task(Status.PROPOSED, created_by="a1", assignee=None)
    _ok(decide_add_subtask(proposal, AGENT, Subtask("s1", "Step")))
    _rejected(
        decide_add_subtask(proposal, OTHER, Subtask("s1", "Step")), RejectionCode.NOT_PERMITTED
    )


def test_add_rejects_blank_title_duplicate_id_non_todo_status_and_closed_task():
    existing = _with(TODO)
    _rejected(decide_add_subtask(existing, OWNER, Subtask("s2", "  ")), RejectionCode.EMPTY_TEXT)
    _rejected(
        decide_add_subtask(existing, OWNER, Subtask("s1", "Again")), RejectionCode.DUPLICATE_SUBTASK
    )
    _rejected(
        decide_add_subtask(existing, OWNER, Subtask("s2", "X", DONE)),
        RejectionCode.FIELD_NOT_ALLOWED,
    )
    _rejected(
        decide_add_subtask(_task(Status.DONE), OWNER, Subtask("s2", "X")),
        RejectionCode.WRONG_STATUS,
    )


# --- the field is no longer editable, and drafts are validated


@pytest.mark.parametrize("actor", [OWNER, ORCH, AGENT])
def test_subtasks_are_not_an_editable_field(actor: Actor):
    proposal = _task(Status.PROPOSED, created_by="a1", assignee=None)
    decision = decide_update_fields(proposal, actor, {"subtasks": (Subtask("s9", "Sneaky"),)})
    _rejected(decision, RejectionCode.FIELD_NOT_ALLOWED)


PROFILE = AgentProfile("a1", ActorKind.AGENT, frozenset({"bug"}), frozenset({"p1"}))


def test_create_accepts_todo_drafts_and_rejects_the_rest():
    base = Task(id="t9", title="T", type="bug", project_id="p1", created_by="a1")
    _ok(
        decide_create(
            AGENT, PROFILE, replace(base, subtasks=(Subtask("s1", "A"), Subtask("s2", "B")))
        )
    )
    for bad in (
        (Subtask("s1", "A", DOING),),
        (Subtask("s1", "A"), Subtask("s1", "B")),
        (Subtask("s1", " "),),
    ):
        _rejected(
            decide_create(AGENT, PROFILE, replace(base, subtasks=bad)),
            RejectionCode.FIELD_NOT_ALLOWED,
        )


# --- the review gate and the cascade


def _gate_codes(task: Task) -> set[str]:
    from kairos.domain.gates import check_gates

    return {f.code.value for f in check_gates(task, Status.IN_REVIEW, AGENT, CLEAR)}


def _reviewable(*subtasks: Subtask) -> Task:
    from kairos.domain.model import Criterion, Evidence, EvidenceKind

    proof = Evidence(EvidenceKind.TEXT, "ok", "a1")
    return _task(
        criteria=(Criterion("c1", "works", (proof,)),),
        delivery_summary="done",
        subtasks=subtasks,
    )


@pytest.mark.parametrize("blocking", [TODO, DOING])
def test_review_gate_rejects_open_subtasks(blocking: SubtaskStatus):
    assert _gate_codes(_reviewable(Subtask("s1", "A", DONE), Subtask("s2", "B", blocking))) == {
        "pending_subtasks"
    }


def test_review_gate_accepts_review_done_and_cancelled_subtasks():
    task = _reviewable(
        Subtask("s1", "A", REVIEW), Subtask("s2", "B", DONE), Subtask("s3", "C", CANCELLED)
    )
    assert _gate_codes(task) == set()


def _delivery() -> ApprovalRequest:
    return ApprovalRequest("t1", RequestKind.DELIVERY, "a1", "ready")


def test_approving_a_delivery_approves_the_subtasks_in_review():
    task = _task(
        Status.IN_REVIEW,
        subtasks=(
            Subtask("s1", "A", REVIEW),
            Subtask("s2", "B", CANCELLED),
            Subtask("s3", "C", REVIEW),
        ),
    )
    result = _ok(decide_resolve_request(task, _delivery(), OWNER, True, None, CLEAR))
    assert result.task.status is Status.DONE
    assert [s.status for s in result.task.subtasks] == [DONE, CANCELLED, DONE]
    changed = [e for e in result.events if e.type is EventType.SUBTASK_STATUS_CHANGED]
    assert [e.payload["subtask"] for e in changed] == ["s1", "s3"]
    assert all(e.actor == OWNER for e in changed)


def test_returning_a_delivery_leaves_the_subtasks_as_they_are():
    task = _task(Status.IN_REVIEW, subtasks=(Subtask("s1", "A", REVIEW),))
    result = _ok(decide_resolve_request(task, _delivery(), OWNER, False, "redo", CLEAR))
    assert result.task.status is Status.READY
    assert result.task.subtasks == (Subtask("s1", "A", REVIEW),)


def test_approving_a_cancellation_does_not_approve_subtasks():
    task = _task(subtasks=(Subtask("s1", "A", REVIEW),))
    cancellation = ApprovalRequest("t1", RequestKind.CANCELLATION, "a1", "why")
    result = _ok(decide_resolve_request(task, cancellation, OWNER, True, None, CLEAR))
    assert result.task.status is Status.CANCELLED
    assert result.task.subtasks == (Subtask("s1", "A", REVIEW),)
