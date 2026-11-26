"""Guards that exist in exactly one place each: a regression there must fail a test."""

from dataclasses import replace

import pytest

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.changes import decide_update_fields
from kairos.domain.decision import Rejected, RejectionCode
from kairos.domain.gates import GateContext
from kairos.domain.model import Criterion, Evidence, EvidenceKind, Task, TaskType
from kairos.domain.policy import decide_transition
from kairos.domain.status import Status

AGENT = Actor(ActorKind.AGENT, "a1")
CLEAR = GateContext(TaskType("bug", frozenset()), frozenset(), frozenset())
PROOF = Evidence(EvidenceKind.TEXT, "ran it", "a2")


def _task(status: Status, **changes: object) -> Task:
    base = Task(
        id="t1",
        title="T",
        type="bug",
        project_id="p1",
        created_by="owner",
        status=status,
        assignee="a2",
        criteria=(Criterion("c1", "works", (PROOF,)),),
        delivery_summary="Done.",
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def _code(decision: object) -> RejectionCode:
    assert isinstance(decision, Rejected), decision
    return decision.code


@pytest.mark.parametrize("target", [Status.READY, Status.IN_REVIEW])
def test_an_agent_cannot_release_or_submit_a_task_carried_by_another_agent(target: Status):
    task = _task(Status.IN_PROGRESS)  # carried by a2, acted on by a1
    decision = decide_transition(task, AGENT, target, CLEAR, reason="mine now")
    assert _code(decision) is RejectionCode.NOT_ASSIGNED


@pytest.mark.parametrize("status", [Status.READY, Status.IN_REVIEW, Status.DONE])
def test_an_agent_edits_its_summary_only_while_in_progress(status: Status):
    carried = _task(status, assignee="a1")
    decision = decide_update_fields(carried, AGENT, {"delivery_summary": "changed"})
    assert _code(decision) is RejectionCode.NOT_PERMITTED


def test_an_agent_cannot_edit_another_agents_proposal():
    proposal = _task(Status.PROPOSED, created_by="a2", assignee=None)
    decision = decide_update_fields(proposal, AGENT, {"title": "hijacked"})
    assert _code(decision) is RejectionCode.NOT_PERMITTED
