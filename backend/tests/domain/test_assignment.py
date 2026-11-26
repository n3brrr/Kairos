from dataclasses import replace

import pytest

from kairos.domain.actor import Actor, ActorKind, AgentProfile
from kairos.domain.assignment import decide_assign, decide_unassign, queue_load
from kairos.domain.decision import Allowed, Rejected, RejectionCode
from kairos.domain.events import EventType
from kairos.domain.model import Task
from kairos.domain.status import Status

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
AGENT = Actor(ActorKind.AGENT, "a1")
SYSTEM = Actor(ActorKind.SYSTEM, "sys")
PROFILE = AgentProfile("a1", ActorKind.AGENT, frozenset({"bug"}), frozenset({"p1"}), queue_limit=3)


def _task(status: Status = Status.READY, **changes: object) -> Task:
    base = Task(id="t1", title="T", type="bug", project_id="p1", created_by="owner", status=status)
    return replace(base, **changes)  # type: ignore[arg-type]


def _code(decision: object) -> RejectionCode:
    assert isinstance(decision, Rejected), decision
    return decision.code


def test_owner_assigns_a_ready_task():
    decision = decide_assign(_task(), OWNER, PROFILE, load=0)
    assert isinstance(decision, Allowed)
    assert decision.task.assignee == "a1"
    assert [e.type for e in decision.events] == [EventType.ASSIGNED]
    assert decision.events[0].payload == {"agent": "a1"}


def test_orchestrator_assigns_too():
    assert isinstance(decide_assign(_task(), ORCH, PROFILE, load=0), Allowed)


@pytest.mark.parametrize("actor", [AGENT, SYSTEM])
def test_only_owner_and_orchestrator_assign(actor: Actor):
    assert _code(decide_assign(_task(), actor, PROFILE, load=0)) is RejectionCode.NOT_PERMITTED


@pytest.mark.parametrize("status", [s for s in Status if s is not Status.READY])
def test_only_ready_tasks_are_assigned(status: Status):
    assert _code(decide_assign(_task(status), OWNER, PROFILE, load=0)) is RejectionCode.WRONG_STATUS


def test_one_agent_per_task():
    task = _task(assignee="a2")
    assert _code(decide_assign(task, OWNER, PROFILE, load=0)) is RejectionCode.ALREADY_ASSIGNED


def test_task_type_must_be_in_scope():
    task = _task(type="feature")
    assert _code(decide_assign(task, OWNER, PROFILE, load=0)) is RejectionCode.OUT_OF_SCOPE


def test_project_must_be_in_scope():
    task = _task(project_id="p2")
    assert _code(decide_assign(task, OWNER, PROFILE, load=0)) is RejectionCode.OUT_OF_SCOPE


def test_load_below_the_limit_is_accepted_and_at_the_limit_is_rejected():
    assert isinstance(decide_assign(_task(), OWNER, PROFILE, load=2), Allowed)
    assert _code(decide_assign(_task(), OWNER, PROFILE, load=3)) is RejectionCode.QUEUE_FULL


def test_limit_is_per_agent():
    small = replace(PROFILE, queue_limit=1)
    assert _code(decide_assign(_task(), OWNER, small, load=1)) is RejectionCode.QUEUE_FULL
    assert isinstance(
        decide_assign(_task(), OWNER, replace(PROFILE, queue_limit=5), load=4), Allowed
    )


def test_orchestrator_obeys_the_same_invariants():
    # Scope and queue limit bind the orchestrator exactly like the owner.
    assert _code(decide_assign(_task(type="feature"), ORCH, PROFILE, load=0)) is (
        RejectionCode.OUT_OF_SCOPE
    )
    assert _code(decide_assign(_task(), ORCH, PROFILE, load=3)) is RejectionCode.QUEUE_FULL
    assert _code(decide_assign(_task(assignee="a2"), ORCH, PROFILE, load=0)) is (
        RejectionCode.ALREADY_ASSIGNED
    )


def test_queue_load_counts_only_ready_and_in_progress_of_that_agent():
    mine = [
        _task(Status.READY, id="1", assignee="a1"),
        _task(Status.IN_PROGRESS, id="2", assignee="a1"),
        # Review Focus 5: tasks waiting for the owner, or closed, do not take a slot.
        _task(Status.IN_REVIEW, id="3", assignee="a1"),
        _task(Status.DONE, id="4", assignee="a1"),
        _task(Status.CANCELLED, id="5", assignee="a1"),
        _task(Status.READY, id="6", assignee="a2"),
        _task(Status.READY, id="7"),
    ]
    assert queue_load(mine, "a1") == 2


def test_an_agent_whose_queue_is_full_of_reviews_can_take_new_work():
    tasks = [_task(Status.IN_REVIEW, id=str(n), assignee="a1") for n in range(3)]
    load = queue_load(tasks, "a1")
    assert isinstance(decide_assign(_task(id="new"), OWNER, PROFILE, load), Allowed)


def test_unassign_a_ready_task_with_a_reason():
    decision = decide_unassign(_task(assignee="a1"), OWNER, "reassigning")
    assert isinstance(decision, Allowed)
    assert decision.task.assignee is None
    assert [e.type for e in decision.events] == [EventType.UNASSIGNED]


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_unassign_needs_a_reason(reason: str | None):
    task = _task(assignee="a1")
    assert _code(decide_unassign(task, OWNER, reason)) is RejectionCode.REASON_REQUIRED


def test_unassign_rules():
    assert _code(decide_unassign(_task(assignee="a1"), AGENT, "x")) is RejectionCode.NOT_PERMITTED
    assert _code(decide_unassign(_task(), OWNER, "x")) is RejectionCode.NOT_ASSIGNED
    in_progress = _task(Status.IN_PROGRESS, assignee="a1")
    assert _code(decide_unassign(in_progress, OWNER, "x")) is RejectionCode.WRONG_STATUS
