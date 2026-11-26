from dataclasses import replace

import pytest

from kairos.domain.actor import Actor, ActorKind, AgentProfile
from kairos.domain.changes import (
    decide_add_dependency,
    decide_attach_evidence,
    decide_comment,
    decide_create,
    decide_remove_dependency,
    decide_update_fields,
)
from kairos.domain.decision import Allowed, Rejected, RejectionCode
from kairos.domain.events import EventType
from kairos.domain.model import Criterion, Evidence, EvidenceKind, Priority, Task
from kairos.domain.status import Status

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
AGENT = Actor(ActorKind.AGENT, "a1")
OTHER = Actor(ActorKind.AGENT, "a2")
SYSTEM = Actor(ActorKind.SYSTEM, "sys")
PROFILE = AgentProfile("a1", ActorKind.AGENT, frozenset({"bug"}), frozenset({"p1"}))
ORCH_PROFILE = AgentProfile("o1", ActorKind.ORCHESTRATOR, frozenset({"bug"}), frozenset({"p1"}))
PROOF = Evidence(EvidenceKind.TEXT, "ran it", "someone")


def _task(status: Status = Status.IN_PROGRESS, **changes: object) -> Task:
    base = Task(
        id="t1",
        title="T",
        type="bug",
        project_id="p1",
        created_by="owner",
        status=status,
        assignee="a1",
        criteria=(Criterion("c1", "works"),),
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def _ok(decision: object) -> Allowed:
    assert isinstance(decision, Allowed), decision
    return decision


def _code(decision: object) -> RejectionCode:
    assert isinstance(decision, Rejected), decision
    return decision.code


# --- create ---------------------------------------------------------------------------------


def test_owner_creates_in_backlog():
    draft = _task(Status.READY, assignee="a1", created_by="x")
    allowed = _ok(decide_create(OWNER, None, draft))
    assert allowed.task.status is Status.BACKLOG
    assert allowed.task.created_by == "owner"
    assert allowed.task.assignee is None
    assert [e.type for e in allowed.events] == [EventType.ITEM_CREATED]


def test_agent_creates_a_proposal_inside_its_scope():
    allowed = _ok(decide_create(AGENT, PROFILE, _task(Status.BACKLOG)))
    assert allowed.task.status is Status.PROPOSED
    assert allowed.task.created_by == "a1"


def test_orchestrator_creates_proposals_too():
    assert _ok(decide_create(ORCH, ORCH_PROFILE, _task())).task.status is Status.PROPOSED


def test_agent_outside_scope_is_rejected():
    assert _code(decide_create(AGENT, PROFILE, _task(type="feature"))) is RejectionCode.OUT_OF_SCOPE
    assert (
        _code(decide_create(AGENT, PROFILE, _task(project_id="p2"))) is RejectionCode.OUT_OF_SCOPE
    )


def test_agent_without_a_profile_is_rejected():
    assert _code(decide_create(AGENT, None, _task())) is RejectionCode.NOT_PERMITTED


def test_agent_can_draft_criteria_in_a_proposal():
    draft = _task(criteria=(Criterion("c1", "a"), Criterion("c2", "b")))
    assert len(_ok(decide_create(AGENT, PROFILE, draft)).task.criteria) == 2


def test_agent_cannot_draft_dependencies():
    draft = _task(blocked_by=frozenset({"t9"}))
    assert _code(decide_create(AGENT, PROFILE, draft)) is RejectionCode.FIELD_NOT_ALLOWED


@pytest.mark.parametrize("title", ["", "   "])
def test_blank_title_is_rejected_on_create(title: str):
    assert _code(decide_create(OWNER, None, _task(title=title))) is RejectionCode.EMPTY_TEXT


def test_system_cannot_create():
    assert _code(decide_create(SYSTEM, None, _task())) is RejectionCode.NOT_PERMITTED


# --- update fields --------------------------------------------------------------------------


def test_owner_updates_any_editable_field_even_on_a_closed_task():
    allowed = _ok(decide_update_fields(_task(Status.DONE), OWNER, {"priority": Priority.P0}))
    assert allowed.task.priority is Priority.P0
    assert allowed.events[0].type is EventType.FIELDS_UPDATED
    assert allowed.events[0].payload == {"fields": ("priority",)}


def test_orchestrator_defines_criteria_but_not_on_closed_tasks():
    criteria = (Criterion("c9", "new"),)
    backlog = _task(Status.BACKLOG, assignee=None)
    assert (
        _ok(decide_update_fields(backlog, ORCH, {"criteria": criteria})).task.criteria == criteria
    )
    done = _task(Status.DONE)
    assert _code(decide_update_fields(done, ORCH, {"criteria": criteria})) is (
        RejectionCode.WRONG_STATUS
    )


def test_agent_can_edit_everything_in_its_own_proposal():
    proposal = _task(Status.PROPOSED, created_by="a1", assignee=None)
    changes: dict[str, object] = {"title": "New", "criteria": (Criterion("c2", "x"),)}
    assert isinstance(decide_update_fields(proposal, AGENT, changes), Allowed)


def test_agent_cannot_edit_criteria_after_triage():
    changes: dict[str, object] = {"criteria": (Criterion("c2", "x"),)}
    backlog = _task(Status.BACKLOG, created_by="a1", assignee=None)
    assert _code(decide_update_fields(backlog, AGENT, changes)) is RejectionCode.NOT_PERMITTED
    in_progress = _task(Status.IN_PROGRESS)
    assert _code(decide_update_fields(in_progress, AGENT, changes)) is (
        RejectionCode.FIELD_NOT_ALLOWED
    )


def test_agent_can_edit_its_summary_and_notes_while_in_progress():
    changes: dict[str, object] = {"delivery_summary": "Done.", "working_notes": "notes"}
    allowed = _ok(decide_update_fields(_task(Status.IN_PROGRESS), AGENT, changes))
    assert allowed.task.delivery_summary == "Done."


@pytest.mark.parametrize(
    "field",
    ["title", "type", "priority", "start_date", "due_date", "parent_id", "recurrence", "labels"],
)
def test_agent_cannot_change_the_base_fields_of_its_task(field: str):
    decision = decide_update_fields(_task(Status.IN_PROGRESS), AGENT, {field: None})
    assert _code(decision) is RejectionCode.FIELD_NOT_ALLOWED


def test_agent_cannot_edit_another_agents_task():
    changes: dict[str, object] = {"working_notes": "x"}
    assert _code(decide_update_fields(_task(), OTHER, changes)) is RejectionCode.NOT_PERMITTED


@pytest.mark.parametrize(
    "field", ["status", "assignee", "blocked_by", "id", "created_by", "project_id", "nope"]
)
def test_protected_and_unknown_fields_are_rejected_for_everyone(field: str):
    for actor in (OWNER, ORCH):
        decision = decide_update_fields(_task(Status.BACKLOG), actor, {field: "x"})
        assert _code(decision) is RejectionCode.FIELD_NOT_ALLOWED


def test_empty_change_set_is_rejected():
    assert _code(decide_update_fields(_task(), OWNER, {})) is RejectionCode.FIELD_NOT_ALLOWED


def test_blank_title_is_rejected_on_update():
    assert _code(decide_update_fields(_task(), OWNER, {"title": "  "})) is RejectionCode.EMPTY_TEXT


def test_system_cannot_update():
    decision = decide_update_fields(_task(), SYSTEM, {"title": "x"})
    assert _code(decision) is RejectionCode.NOT_PERMITTED


# --- evidence and comments ------------------------------------------------------------------


def test_assignee_attaches_evidence_while_in_progress():
    allowed = _ok(decide_attach_evidence(_task(), AGENT, "c1", PROOF))
    attached = allowed.task.criteria[0].evidence
    assert len(attached) == 1 and attached[0].added_by == "a1"
    assert allowed.events[0].type is EventType.EVIDENCE_ATTACHED


def test_blank_evidence_is_rejected():
    blank = replace(PROOF, content="   ")
    assert _code(decide_attach_evidence(_task(), AGENT, "c1", blank)) is RejectionCode.EMPTY_TEXT


def test_evidence_for_an_unknown_criterion_is_rejected():
    decision = decide_attach_evidence(_task(), AGENT, "nope", PROOF)
    assert _code(decision) is RejectionCode.UNKNOWN_CRITERION


def test_agent_cannot_attach_evidence_outside_in_progress():
    decision = decide_attach_evidence(_task(Status.IN_REVIEW), AGENT, "c1", PROOF)
    assert _code(decision) is RejectionCode.WRONG_STATUS


def test_agent_cannot_attach_evidence_to_another_agents_task():
    assert _code(decide_attach_evidence(_task(), OTHER, "c1", PROOF)) is RejectionCode.NOT_ASSIGNED


def test_orchestrator_and_system_cannot_attach_evidence():
    for actor in (ORCH, SYSTEM):
        decision = decide_attach_evidence(_task(), actor, "c1", PROOF)
        assert _code(decision) is RejectionCode.NOT_PERMITTED


def test_owner_attaches_evidence_in_any_status():
    assert isinstance(decide_attach_evidence(_task(Status.DONE), OWNER, "c1", PROOF), Allowed)


def test_comments_by_owner_orchestrator_and_assignee():
    for actor in (OWNER, ORCH, AGENT):
        allowed = _ok(decide_comment(_task(), actor, "looks good"))
        assert allowed.task == _task()
        assert allowed.events[0].type is EventType.COMMENT_ADDED


def test_comment_rules():
    assert _code(decide_comment(_task(), OTHER, "hi")) is RejectionCode.NOT_PERMITTED
    assert _code(decide_comment(_task(), SYSTEM, "hi")) is RejectionCode.NOT_PERMITTED
    for blank in ("", "   "):
        assert _code(decide_comment(_task(), OWNER, blank)) is RejectionCode.EMPTY_TEXT


# --- dependencies ---------------------------------------------------------------------------

GRAPH: dict[str, frozenset[str]] = {"t1": frozenset(), "t2": frozenset(), "t3": frozenset({"t1"})}


def test_owner_and_orchestrator_add_a_dependency():
    for actor in (OWNER, ORCH):
        allowed = _ok(decide_add_dependency(_task(), actor, "t2", GRAPH))
        assert allowed.task.blocked_by == frozenset({"t2"})
        assert allowed.events[0].type is EventType.DEPENDENCY_ADDED


def test_agent_cannot_change_dependencies():
    assert _code(decide_add_dependency(_task(), AGENT, "t2", GRAPH)) is RejectionCode.NOT_PERMITTED
    blocked = _task(blocked_by=frozenset({"t2"}))
    assert _code(decide_remove_dependency(blocked, AGENT, "t2")) is RejectionCode.NOT_PERMITTED


def test_self_dependency_is_rejected():
    decision = decide_add_dependency(_task(), OWNER, "t1", GRAPH)
    assert _code(decision) is RejectionCode.DEPENDENCY_CYCLE


def test_cycle_is_rejected():
    # t3 is blocked by t1; making t1 blocked by t3 closes the loop.
    decision = decide_add_dependency(_task(), OWNER, "t3", GRAPH)
    assert _code(decision) is RejectionCode.DEPENDENCY_CYCLE


def test_unknown_blocker_is_rejected():
    decision = decide_add_dependency(_task(), OWNER, "ghost", GRAPH)
    assert _code(decision) is RejectionCode.UNKNOWN_DEPENDENCY


def test_remove_a_dependency():
    task = _task(blocked_by=frozenset({"t2"}))
    allowed = _ok(decide_remove_dependency(task, OWNER, "t2"))
    assert allowed.task.blocked_by == frozenset()
    assert allowed.events[0].type is EventType.DEPENDENCY_REMOVED
    assert _code(decide_remove_dependency(task, OWNER, "t9")) is RejectionCode.UNKNOWN_DEPENDENCY
