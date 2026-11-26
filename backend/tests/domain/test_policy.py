from dataclasses import replace
from itertools import product

import pytest

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.decision import Allowed, GateCode, Rejected, RejectionCode
from kairos.domain.events import EventType
from kairos.domain.gates import GateContext
from kairos.domain.model import Criterion, Evidence, EvidenceKind, RequestKind, Task, TaskType
from kairos.domain.policy import decide_transition
from kairos.domain.status import Status

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
AGENT = Actor(ActorKind.AGENT, "a1")
SYSTEM = Actor(ActorKind.SYSTEM, "sys")
ACTORS = {
    ActorKind.OWNER: OWNER,
    ActorKind.ORCHESTRATOR: ORCH,
    ActorKind.AGENT: AGENT,
    ActorKind.SYSTEM: SYSTEM,
}
PROOF = Evidence(EvidenceKind.TEXT, "ran it", "a1")
CLEAR = GateContext(TaskType("bug", frozenset()), frozenset(), frozenset())

S = Status
K = ActorKind

# The permission table of design §6.3, written out by hand and independently of the code.
TRIAGE = {K.OWNER, K.ORCHESTRATOR}
EXPECTED: dict[tuple[Status, Status], set[ActorKind]] = {
    (S.PROPOSED, S.BACKLOG): TRIAGE,
    (S.BACKLOG, S.READY): TRIAGE,
    (S.READY, S.IN_PROGRESS): {K.OWNER, K.AGENT},
    (S.IN_PROGRESS, S.IN_REVIEW): {K.OWNER, K.AGENT},
    (S.IN_REVIEW, S.DONE): {K.OWNER},
    (S.IN_REVIEW, S.READY): {K.OWNER},  # return a delivery
    (S.IN_PROGRESS, S.READY): {K.OWNER, K.ORCHESTRATOR, K.AGENT},  # release
    # moving backwards: owner only
    (S.BACKLOG, S.PROPOSED): {K.OWNER},
    (S.READY, S.PROPOSED): {K.OWNER},
    (S.READY, S.BACKLOG): {K.OWNER},
    (S.IN_PROGRESS, S.PROPOSED): {K.OWNER},
    (S.IN_PROGRESS, S.BACKLOG): {K.OWNER},
    (S.IN_REVIEW, S.PROPOSED): {K.OWNER},
    (S.IN_REVIEW, S.BACKLOG): {K.OWNER},
    (S.IN_REVIEW, S.IN_PROGRESS): {K.OWNER},
    # cancel (and discard a proposal): owner only
    (S.PROPOSED, S.CANCELLED): {K.OWNER},
    (S.BACKLOG, S.CANCELLED): {K.OWNER},
    (S.READY, S.CANCELLED): {K.OWNER},
    (S.IN_PROGRESS, S.CANCELLED): {K.OWNER},
    (S.IN_REVIEW, S.CANCELLED): {K.OWNER},
    # reopen closed tasks: owner only
    (S.DONE, S.BACKLOG): {K.OWNER},
    (S.DONE, S.READY): {K.OWNER},
    (S.CANCELLED, S.BACKLOG): {K.OWNER},
    (S.CANCELLED, S.READY): {K.OWNER},
}


def _task(status: Status = Status.IN_PROGRESS, **changes: object) -> Task:
    """A task in `status` that passes every gate, assigned to agent a1."""
    base = Task(
        id="t1",
        title="T",
        type="bug",
        project_id="p1",
        created_by="a1",
        status=status,
        assignee="a1",
        criteria=(Criterion("c1", "works", (PROOF,)),),
        delivery_summary="Done and verified.",
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def _allowed(decision: object) -> Allowed:
    assert isinstance(decision, Allowed), decision
    return decision


def _rejected(decision: object) -> Rejected:
    assert isinstance(decision, Rejected), decision
    return decision


@pytest.mark.parametrize(
    ("source", "target", "kind"), list(product(Status, Status, ActorKind)), ids=str
)
def test_policy_matrix_matches_the_spec(source: Status, target: Status, kind: ActorKind):
    # A reason and an override reason are supplied everywhere: neither may elevate anybody.
    decision = decide_transition(
        _task(source), ACTORS[kind], target, CLEAR, reason="because", override_reason="override"
    )
    assert isinstance(decision, Allowed) is (kind in EXPECTED.get((source, target), set()))


def test_agent_cannot_start_a_task_assigned_to_someone_else():
    decision = decide_transition(_task(Status.READY, assignee="a2"), AGENT, S.IN_PROGRESS, CLEAR)
    assert _rejected(decision).code is RejectionCode.NOT_ASSIGNED


def test_system_actor_is_always_rejected():
    decision = decide_transition(_task(Status.PROPOSED), SYSTEM, S.BACKLOG, CLEAR, reason="r")
    assert _rejected(decision).code is RejectionCode.NOT_PERMITTED


def test_same_status_is_an_invalid_transition():
    decision = decide_transition(_task(Status.READY), OWNER, S.READY, CLEAR)
    assert _rejected(decision).code is RejectionCode.INVALID_TRANSITION


def test_submit_creates_a_delivery_request():
    allowed = _allowed(decide_transition(_task(), AGENT, S.IN_REVIEW, CLEAR))
    assert allowed.task.status is S.IN_REVIEW
    assert allowed.request is not None
    assert allowed.request.kind is RequestKind.DELIVERY
    assert allowed.request.requested_by == "a1"
    assert EventType.APPROVAL_REQUESTED in {e.type for e in allowed.events}


def test_release_requires_a_reason_and_clears_the_assignment():
    decision = decide_transition(_task(), AGENT, S.READY, CLEAR, reason="  ")
    assert _rejected(decision).code is RejectionCode.REASON_REQUIRED
    allowed = _allowed(decide_transition(_task(), AGENT, S.READY, CLEAR, reason="blocked on X"))
    assert allowed.task.assignee is None
    assert EventType.UNASSIGNED in {e.type for e in allowed.events}


def test_return_keeps_the_assignment_and_needs_a_reason():
    task = _task(Status.IN_REVIEW)
    assert (
        _rejected(decide_transition(task, OWNER, S.READY, CLEAR)).code
        is RejectionCode.REASON_REQUIRED
    )
    allowed = _allowed(decide_transition(task, OWNER, S.READY, CLEAR, reason="needs a retest"))
    assert allowed.task.assignee == "a1"


def test_cancel_clears_the_assignment():
    allowed = _allowed(decide_transition(_task(), OWNER, S.CANCELLED, CLEAR))
    assert allowed.task.status is S.CANCELLED and allowed.task.assignee is None


def test_moving_back_to_backlog_clears_the_assignment():
    allowed = _allowed(decide_transition(_task(Status.READY), OWNER, S.BACKLOG, CLEAR))
    assert allowed.task.assignee is None


def test_gate_failure_rejects_an_agent_with_every_failed_code():
    task = _task(criteria=(), delivery_summary="")
    rejected = _rejected(decide_transition(task, AGENT, S.IN_REVIEW, CLEAR))
    assert rejected.code is RejectionCode.GATE_FAILED
    assert {g.code for g in rejected.gates} == {
        GateCode.CRITERIA_WITHOUT_EVIDENCE,
        GateCode.EMPTY_DELIVERY_SUMMARY,
    }


def test_owner_override_records_gate_overridden():
    task = _task(Status.BACKLOG, criteria=())
    allowed = _allowed(
        decide_transition(task, OWNER, S.READY, CLEAR, override_reason="criteria come later")
    )
    assert allowed.task.status is S.READY
    overridden = [e for e in allowed.events if e.type is EventType.GATE_OVERRIDDEN]
    assert len(overridden) == 1
    assert overridden[0].reason == "criteria come later"
    assert overridden[0].payload["gates"] == (GateCode.NO_CRITERIA.value,)


def test_owner_override_with_a_blank_reason_is_rejected():
    task = _task(Status.BACKLOG, criteria=())
    for blank in (None, "", "   "):
        decision = decide_transition(task, OWNER, S.READY, CLEAR, override_reason=blank)
        assert _rejected(decision).code is RejectionCode.GATE_FAILED


def test_agent_override_reason_is_ignored():
    task = _task(criteria=())
    decision = decide_transition(task, AGENT, S.IN_REVIEW, CLEAR, override_reason="please")
    assert _rejected(decision).code is RejectionCode.GATE_FAILED


def test_busy_agent_cannot_be_overridden_even_by_the_owner():
    busy = GateContext(CLEAR.task_type, frozenset(), frozenset({"t2"}))
    decision = decide_transition(
        _task(Status.READY), OWNER, S.IN_PROGRESS, busy, override_reason="do it anyway"
    )
    rejected = _rejected(decision)
    assert rejected.code is RejectionCode.GATE_FAILED
    assert GateCode.AGENT_BUSY in {g.code for g in rejected.gates}


def test_cancelled_blocker_adds_a_warning():
    ctx = GateContext(CLEAR.task_type, frozenset(), frozenset(), frozenset({"d1"}))
    allowed = _allowed(decide_transition(_task(Status.READY), AGENT, S.IN_PROGRESS, ctx))
    assert any("d1" in warning for warning in allowed.warnings)


def test_events_carry_the_actor_and_the_subagent():
    via_agent = Actor(ActorKind.AGENT, "a1", via="subagent-1")
    allowed = _allowed(decide_transition(_task(Status.READY), via_agent, S.IN_PROGRESS, CLEAR))
    changed = next(e for e in allowed.events if e.type is EventType.STATUS_CHANGED)
    assert changed.actor.via == "subagent-1"
    assert changed.payload == {"from": "ready", "to": "in_progress"}
