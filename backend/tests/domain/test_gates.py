from dataclasses import replace

import pytest

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.decision import GateCode
from kairos.domain.gates import GateContext, check_gates
from kairos.domain.model import Criterion, Evidence, EvidenceKind, Subtask, Task, TaskType
from kairos.domain.status import Status, SubtaskStatus

AGENT = Actor(ActorKind.AGENT, "a1")
OWNER = Actor(ActorKind.OWNER, "owner")
PROOF = Evidence(EvidenceKind.TEXT, "ran it", "a1")
NO_TYPE = TaskType("bug", frozenset())


def _ctx(
    task_type: TaskType = NO_TYPE,
    open_blockers: frozenset[str] = frozenset(),
    other_in_progress: frozenset[str] = frozenset(),
) -> GateContext:
    return GateContext(task_type, open_blockers, other_in_progress)


def _task(**changes: object) -> Task:
    """A task that passes every gate: assigned to a1, one criterion with evidence, a summary."""
    base = Task(
        id="t1",
        title="T",
        type="bug",
        project_id="p1",
        created_by="a1",
        status=Status.IN_PROGRESS,
        assignee="a1",
        description="d",
        criteria=(Criterion("c1", "works", (PROOF,)),),
        delivery_summary="Done and verified.",
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def _codes(task: Task, target: Status, actor: Actor, ctx: GateContext) -> set[GateCode]:
    return {failure.code for failure in check_gates(task, target, actor, ctx)}


def test_ready_needs_a_criterion():
    assert _codes(_task(criteria=()), Status.READY, OWNER, _ctx()) == {GateCode.NO_CRITERIA}
    assert _codes(_task(), Status.READY, OWNER, _ctx()) == set()


def test_in_progress_rejects_open_dependencies():
    codes = _codes(_task(), Status.IN_PROGRESS, AGENT, _ctx(open_blockers=frozenset({"x"})))
    assert codes == {GateCode.OPEN_DEPENDENCIES}


def test_agent_must_be_the_assignee_to_start():
    codes = _codes(_task(assignee="a2"), Status.IN_PROGRESS, AGENT, _ctx())
    assert codes == {GateCode.NOT_ASSIGNED_TO_ACTOR}
    codes = _codes(_task(assignee=None), Status.IN_PROGRESS, AGENT, _ctx())
    assert codes == {GateCode.NOT_ASSIGNED_TO_ACTOR}


def test_agent_with_another_task_in_progress_is_busy():
    ctx = _ctx(other_in_progress=frozenset({"t2"}))
    assert _codes(_task(), Status.IN_PROGRESS, AGENT, ctx) == {GateCode.AGENT_BUSY}


def test_owner_is_not_subject_to_the_assignee_and_busy_gates():
    ctx = _ctx(other_in_progress=frozenset({"t2"}))
    assert _codes(_task(assignee=None), Status.IN_PROGRESS, OWNER, ctx) == set()
    blocked = _ctx(open_blockers=frozenset({"x"}))
    assert _codes(_task(assignee=None), Status.IN_PROGRESS, OWNER, blocked) == {
        GateCode.OPEN_DEPENDENCIES
    }


def test_a_complete_delivery_passes_the_review_gate():
    assert _codes(_task(), Status.IN_REVIEW, AGENT, _ctx()) == set()


def test_review_needs_the_required_fields_of_the_type():
    task_type = TaskType("bug", frozenset({"description", "labels"}))
    codes = _codes(_task(description="", labels=()), Status.IN_REVIEW, AGENT, _ctx(task_type))
    assert codes == {GateCode.MISSING_REQUIRED_FIELDS}
    assert _codes(_task(labels=("x",)), Status.IN_REVIEW, AGENT, _ctx(task_type)) == set()


def test_unknown_required_field_fails_closed():
    task_type = TaskType("bug", frozenset({"no_such_field"}))
    codes = _codes(_task(), Status.IN_REVIEW, AGENT, _ctx(task_type))
    assert codes == {GateCode.MISSING_REQUIRED_FIELDS}


def test_review_gate_rejects_a_task_with_zero_criteria():
    # "every criterion has evidence" must never be vacuously true.
    codes = _codes(_task(criteria=()), Status.IN_REVIEW, AGENT, _ctx())
    assert codes == {GateCode.CRITERIA_WITHOUT_EVIDENCE}


def test_review_needs_evidence_on_every_criterion():
    criteria = (Criterion("c1", "a", (PROOF,)), Criterion("c2", "b"))
    codes = _codes(_task(criteria=criteria), Status.IN_REVIEW, AGENT, _ctx())
    assert codes == {GateCode.CRITERIA_WITHOUT_EVIDENCE}


def test_review_rejects_pending_subtasks():
    task = _task(subtasks=(Subtask("s1", "A", SubtaskStatus.DONE), Subtask("s2", "B")))
    assert _codes(task, Status.IN_REVIEW, AGENT, _ctx()) == {GateCode.PENDING_SUBTASKS}


def test_review_rejects_open_dependencies():
    ctx = _ctx(open_blockers=frozenset({"x"}))
    assert _codes(_task(), Status.IN_REVIEW, AGENT, ctx) == {GateCode.OPEN_DEPENDENCIES}


@pytest.mark.parametrize("summary", ["", "   ", "\n\t"])
def test_blank_delivery_summary_fails(summary: str):
    codes = _codes(_task(delivery_summary=summary), Status.IN_REVIEW, AGENT, _ctx())
    assert codes == {GateCode.EMPTY_DELIVERY_SUMMARY}


def test_all_failures_are_reported_together():
    task = _task(criteria=(), delivery_summary="", subtasks=(Subtask("s1", "A"),))
    ctx = _ctx(open_blockers=frozenset({"x"}))
    assert _codes(task, Status.IN_REVIEW, AGENT, ctx) == {
        GateCode.CRITERIA_WITHOUT_EVIDENCE,
        GateCode.EMPTY_DELIVERY_SUMMARY,
        GateCode.PENDING_SUBTASKS,
        GateCode.OPEN_DEPENDENCIES,
    }


@pytest.mark.parametrize("target", [Status.PROPOSED, Status.BACKLOG, Status.DONE, Status.CANCELLED])
def test_ungated_targets_return_nothing(target: Status):
    bad = _task(criteria=(), delivery_summary="", assignee=None)
    assert check_gates(bad, target, AGENT, _ctx(open_blockers=frozenset({"x"}))) == ()


def test_owner_starting_a_task_of_a_busy_agent_is_busy():
    # The invariant "one in progress per agent" binds whoever moves the task, the owner included.
    ctx = _ctx(other_in_progress=frozenset({"t2"}))
    assert _codes(_task(assignee="a1"), Status.IN_PROGRESS, OWNER, ctx) == {GateCode.AGENT_BUSY}
