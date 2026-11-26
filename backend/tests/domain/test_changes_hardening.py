"""Second doors: ways around the evidence, dependency and scope rules found by the final review."""

from dataclasses import replace

from kairos.domain.actor import Actor, ActorKind, AgentProfile
from kairos.domain.changes import decide_create, decide_update_fields
from kairos.domain.decision import Allowed, Rejected, RejectionCode
from kairos.domain.model import Criterion, Evidence, EvidenceKind, Task
from kairos.domain.status import Status

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
AGENT = Actor(ActorKind.AGENT, "a1")
PROFILE = AgentProfile("a1", ActorKind.AGENT, frozenset({"bug"}), frozenset({"p1"}))
ORCH_PROFILE = AgentProfile("o1", ActorKind.ORCHESTRATOR, frozenset({"bug"}), frozenset({"p1"}))
FORGED = Evidence(EvidenceKind.TEXT, "   ", "owner")
REAL = Evidence(EvidenceKind.TEXT, "ran it", "a1")
CREATORS = ((OWNER, None), (AGENT, PROFILE), (ORCH, ORCH_PROFILE))


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


def _code(decision: object) -> RejectionCode:
    assert isinstance(decision, Rejected), decision
    return decision.code


# --- evidence only enters through decide_attach_evidence ------------------------------------


def test_create_rejects_criteria_that_carry_evidence():
    draft = _task(Status.PROPOSED, assignee=None, criteria=(Criterion("c1", "x", (FORGED,)),))
    for actor, profile in CREATORS:
        assert _code(decide_create(actor, profile, draft)) is RejectionCode.FIELD_NOT_ALLOWED


def test_agent_cannot_preload_evidence_into_its_own_proposal():
    proposal = _task(Status.PROPOSED, created_by="a1", assignee=None)
    forged = {"criteria": (Criterion("c1", "works", (FORGED,)),)}
    assert _code(decide_update_fields(proposal, AGENT, forged, PROFILE)) is (
        RejectionCode.FIELD_NOT_ALLOWED
    )


def test_nobody_can_write_evidence_through_the_criteria_field():
    forged = {"criteria": (Criterion("c1", "works", (FORGED,)),)}
    for actor in (OWNER, ORCH):
        assert (
            _code(decide_update_fields(_task(), actor, forged)) is RejectionCode.FIELD_NOT_ALLOWED
        )


def test_editing_criteria_keeps_the_evidence_already_attached():
    task = _task(criteria=(Criterion("c1", "works", (REAL,)),))
    reworded = {"criteria": (Criterion("c1", "works well", (REAL,)), Criterion("c2", "new"))}
    decision = decide_update_fields(task, ORCH, reworded)
    assert isinstance(decision, Allowed)
    assert decision.task.criteria[0].evidence == (REAL,)
    wiped = {"criteria": (Criterion("c1", "works"),)}
    assert _code(decide_update_fields(task, ORCH, wiped)) is RejectionCode.FIELD_NOT_ALLOWED


def test_criteria_must_be_a_tuple_of_criterion():
    for bad in ("nope", [Criterion("c1", "x")], (object(),)):
        decision = decide_update_fields(_task(Status.BACKLOG), OWNER, {"criteria": bad})
        assert _code(decision) is RejectionCode.FIELD_NOT_ALLOWED


def test_orchestrator_cannot_change_what_the_owner_is_reviewing():
    in_review = _task(Status.IN_REVIEW)
    changes = {"criteria": (Criterion("c9", "different"),)}
    assert _code(decide_update_fields(in_review, ORCH, changes)) is RejectionCode.WRONG_STATUS
    assert isinstance(decide_update_fields(in_review, OWNER, changes), Allowed)


# --- dependencies only through decide_add_dependency ----------------------------------------


def test_create_rejects_dependencies_for_every_actor():
    draft = _task(Status.PROPOSED, assignee=None, blocked_by=frozenset({"t1", "ghost"}))
    for actor, profile in CREATORS:
        assert _code(decide_create(actor, profile, draft)) is RejectionCode.FIELD_NOT_ALLOWED


# --- scope: a task keeps the type its assignee was chosen for --------------------------------


def test_type_of_an_assigned_task_cannot_change():
    for status in (Status.READY, Status.IN_PROGRESS, Status.IN_REVIEW):
        for actor in (OWNER, ORCH):
            decision = decide_update_fields(_task(status), actor, {"type": "feature"})
            assert _code(decision) is RejectionCode.FIELD_NOT_ALLOWED


def test_type_of_an_unassigned_task_can_change():
    backlog = _task(Status.BACKLOG, assignee=None)
    for actor in (OWNER, ORCH):
        assert isinstance(decide_update_fields(backlog, actor, {"type": "feature"}), Allowed)


def test_agent_retyping_its_proposal_stays_inside_its_scope():
    proposal = _task(Status.PROPOSED, created_by="a1", assignee=None)
    outside = decide_update_fields(proposal, AGENT, {"type": "feature"}, PROFILE)
    assert _code(outside) is RejectionCode.OUT_OF_SCOPE
    assert _code(decide_update_fields(proposal, AGENT, {"type": "bug"})) is (
        RejectionCode.NOT_PERMITTED
    )
    assert isinstance(decide_update_fields(proposal, AGENT, {"type": "bug"}, PROFILE), Allowed)
