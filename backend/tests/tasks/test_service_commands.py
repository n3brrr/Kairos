"""Every `TaskService` method: what it persists when allowed, and that it can say no."""

from collections.abc import Callable
from dataclasses import replace

import pytest

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.decision import Allowed, Rejected, RejectionCode
from kairos.domain.events import EventType
from kairos.domain.model import (
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
A2 = Actor(ActorKind.AGENT, "a2")
PROOF = Evidence(EvidenceKind.TEXT, "it works", "a1")

MakeTask = Callable[..., Task]


def allowed(decision: object) -> Allowed:
    assert isinstance(decision, Allowed), decision
    return decision


def rejected(decision: object, code: RejectionCode) -> Rejected:
    assert isinstance(decision, Rejected), decision
    assert decision.code is code, decision
    return decision


def event_types(env: Env) -> list[EventType]:
    return [e.type for e in env.events()]


# --- creating -----------------------------------------------------------------------------


def test_the_owner_creates_a_backlog_task_and_the_event_is_logged(env: Env, make_task: MakeTask):
    created = allowed(env.service.create_task(OWNER, make_task(id="t1")))
    assert created.task.status is Status.BACKLOG
    assert env.task("t1") == created.task
    assert [(e.type, e.entity_id, e.actor_id) for e in env.events()] == [
        (EventType.ITEM_CREATED, "t1", "owner")
    ]
    assert env.verify().ok


def test_an_agent_creates_a_proposal_inside_its_scope_only(env: Env, make_task: MakeTask):
    proposal = allowed(env.service.create_task(A1, make_task(id="t1", created_by="a1")))
    assert proposal.task.status is Status.PROPOSED
    rejected(
        env.service.create_task(A1, make_task(id="t2", type="chore")), RejectionCode.OUT_OF_SCOPE
    )
    assert env.task("t2") is None


@pytest.mark.parametrize(
    "changes",
    [
        {"project_id": "ghost"},
        {"type": "ghost"},
        {"parent_id": "ghost"},
        {"parent_id": "e2"},  # an epic of another project
        {"parent_id": "p1"},  # a project is not an epic
    ],
)
def test_a_task_must_point_at_things_that_exist(
    env: Env, make_task: MakeTask, changes: dict[str, object]
):
    before = env.snapshot()
    rejected(env.service.create_task(OWNER, make_task(**changes)), RejectionCode.NOT_FOUND)
    assert env.snapshot() == before


def test_a_task_may_hang_from_an_epic_of_its_project(env: Env, make_task: MakeTask):
    created = allowed(env.service.create_task(OWNER, make_task(parent_id="e1")))
    assert env.task("t1") == created.task


def test_a_duplicate_id_is_refused_and_changes_nothing(env: Env, make_task: MakeTask):
    allowed(env.service.create_task(OWNER, make_task(id="t1")))
    before = env.snapshot()
    rejected(env.service.create_task(OWNER, make_task(id="t1")), RejectionCode.ALREADY_EXISTS)
    assert env.snapshot() == before


# --- moving, with the gates built from the database ---------------------------------------


def _reviewable(make_task: MakeTask, **changes: object) -> Task:
    fields: dict[str, object] = {
        "status": Status.IN_PROGRESS,
        "assignee": "a1",
        "criteria": (Criterion("c1", "works", (PROOF,)),),
        "delivery_summary": "Done and tested",
    }
    return make_task(**{**fields, **changes})


def test_an_agent_starts_then_submits_and_the_delivery_request_is_stored(
    env: Env, make_task: MakeTask
):
    env.put(_reviewable(make_task, status=Status.READY))
    started = allowed(env.service.move_task(A1, "t1", Status.IN_PROGRESS))
    assert started.task.status is Status.IN_PROGRESS
    submitted = allowed(env.service.move_task(A1, "t1", Status.IN_REVIEW))
    assert submitted.request is not None
    stored = env.pending("t1")
    assert stored is not None and stored.kind is RequestKind.DELIVERY
    assert stored.reason == "Done and tested"
    assert event_types(env) == [
        EventType.STATUS_CHANGED,
        EventType.STATUS_CHANGED,
        EventType.APPROVAL_REQUESTED,
    ]
    assert env.verify().ok


def test_an_open_dependency_blocks_starting_and_a_cancelled_one_only_warns(
    env: Env, make_task: MakeTask
):
    env.put(
        make_task(id="blocker", status=Status.BACKLOG),
        make_task(id="t1", status=Status.READY, assignee="a1", blocked_by=frozenset({"blocker"})),
    )
    refused = rejected(
        env.service.move_task(A1, "t1", Status.IN_PROGRESS), RejectionCode.GATE_FAILED
    )
    assert [g.code.value for g in refused.gates] == ["open_dependencies"]
    env.put(make_task(id="blocker", status=Status.CANCELLED))
    started = allowed(env.service.move_task(A1, "t1", Status.IN_PROGRESS))
    assert started.warnings == ("Dependency blocker was cancelled and counts as resolved.",)


def test_a_done_dependency_lets_the_task_start_without_a_warning(env: Env, make_task: MakeTask):
    env.put(
        make_task(id="blocker", status=Status.DONE),
        make_task(id="t1", status=Status.READY, assignee="a1", blocked_by=frozenset({"blocker"})),
    )
    assert allowed(env.service.move_task(A1, "t1", Status.IN_PROGRESS)).warnings == ()


def test_an_agent_cannot_start_a_second_task_and_neither_can_the_owner_for_it(
    env: Env, make_task: MakeTask
):
    env.put(
        make_task(id="t1", status=Status.IN_PROGRESS, assignee="a1"),
        make_task(id="t2", status=Status.READY, assignee="a1"),
    )
    for actor in (A1, OWNER):
        refused = rejected(
            env.service.move_task(actor, "t2", Status.IN_PROGRESS), RejectionCode.GATE_FAILED
        )
        assert [g.code.value for g in refused.gates] == ["agent_busy"]
    assert env.events() == []


def test_the_owner_overrides_a_gate_with_a_reason_and_it_is_recorded(env: Env, make_task: MakeTask):
    env.put(make_task(status=Status.IN_PROGRESS, assignee="a1"))  # no criteria, no summary
    rejected(env.service.move_task(OWNER, "t1", Status.IN_REVIEW), RejectionCode.GATE_FAILED)
    allowed(env.service.move_task(OWNER, "t1", Status.IN_REVIEW, override_reason="Urgent"))
    assert event_types(env) == [
        EventType.STATUS_CHANGED,
        EventType.GATE_OVERRIDDEN,
        EventType.APPROVAL_REQUESTED,
    ]
    assert env.events()[1].reason == "Urgent"


def test_a_missing_task_and_a_task_nobody_may_see_are_both_not_found(env: Env, make_task: MakeTask):
    env.put(make_task(id="t1", status=Status.IN_PROGRESS, assignee="a1"))
    before = env.snapshot()
    rejected(env.service.move_task(OWNER, "ghost", Status.READY), RejectionCode.NOT_FOUND)
    rejected(env.service.move_task(A2, "t1", Status.IN_REVIEW), RejectionCode.NOT_FOUND)
    assert env.snapshot() == before


def test_submitting_while_a_cancellation_is_pending_is_refused_by_the_database(
    env: Env, make_task: MakeTask
):
    env.put(_reviewable(make_task))
    allowed(env.service.request_cancellation(A1, "t1", "Not needed"))
    before = env.snapshot()
    rejected(env.service.move_task(A1, "t1", Status.IN_REVIEW), RejectionCode.DUPLICATE_REQUEST)
    assert env.snapshot() == before
    assert env.task("t1") == _reviewable(make_task)  # still in progress


# --- assigning ----------------------------------------------------------------------------


def test_assigning_reserves_and_the_queue_limit_comes_from_the_database(
    env: Env, make_task: MakeTask
):
    env.put(make_task(id="t1", status=Status.READY), make_task(id="t2", status=Status.READY))
    assigned = allowed(env.service.assign_task(ORCH, "t1", "a2"))
    assert assigned.task.assignee == "a2"
    assert env.task("t1") == assigned.task
    rejected(env.service.assign_task(ORCH, "t2", "a2"), RejectionCode.QUEUE_FULL)  # a2's limit is 1
    rejected(env.service.assign_task(OWNER, "t2", "ghost"), RejectionCode.NOT_FOUND)
    rejected(env.service.assign_task(A1, "t2", "a1"), RejectionCode.NOT_FOUND)
    assert event_types(env) == [EventType.ASSIGNED]


def test_a_task_in_review_does_not_take_a_queue_slot(env: Env, make_task: MakeTask):
    env.put(
        make_task(id="t1", status=Status.IN_REVIEW, assignee="a2"),
        make_task(id="t2", status=Status.READY),
    )
    allowed(env.service.assign_task(OWNER, "t2", "a2"))


def test_unassigning_clears_the_assignee(env: Env, make_task: MakeTask):
    env.put(make_task(status=Status.READY, assignee="a1"))
    allowed(env.service.unassign_task(OWNER, "t1", "Reassign"))
    task = env.task("t1")
    assert task is not None and task.assignee is None
    assert event_types(env) == [EventType.UNASSIGNED]


# --- fields, evidence, comments -----------------------------------------------------------


def test_fields_change_and_the_criteria_are_stored(env: Env, make_task: MakeTask):
    env.put(make_task(status=Status.BACKLOG))
    allowed(
        env.service.update_fields(
            OWNER, "t1", {"title": "Renamed", "criteria": (Criterion("c1", "It works"),)}
        )
    )
    task = env.task("t1")
    assert task is not None
    assert task.title == "Renamed" and task.criteria == (Criterion("c1", "It works"),)
    assert event_types(env) == [EventType.FIELDS_UPDATED]


def test_a_changed_type_or_parent_must_exist(env: Env, make_task: MakeTask):
    env.put(make_task(status=Status.BACKLOG))
    before = env.snapshot()
    rejected(env.service.update_fields(OWNER, "t1", {"type": "ghost"}), RejectionCode.NOT_FOUND)
    rejected(env.service.update_fields(OWNER, "t1", {"parent_id": "e2"}), RejectionCode.NOT_FOUND)
    assert env.snapshot() == before
    allowed(env.service.update_fields(OWNER, "t1", {"parent_id": "e1", "type": "feature"}))


def test_an_agent_drafts_inside_its_own_proposal_and_nowhere_else(env: Env, make_task: MakeTask):
    env.put(
        make_task(id="mine", status=Status.PROPOSED, created_by="a1"),
        make_task(id="theirs", status=Status.BACKLOG),
    )
    allowed(env.service.update_fields(A1, "mine", {"title": "Better"}))
    rejected(env.service.update_fields(A1, "theirs", {"title": "Nope"}), RejectionCode.NOT_FOUND)


def test_evidence_is_attached_to_a_criterion(env: Env, make_task: MakeTask):
    env.put(make_task(status=Status.IN_PROGRESS, assignee="a1", criteria=(Criterion("c1", "ok"),)))
    allowed(
        env.service.attach_evidence(A1, "t1", "c1", Evidence(EvidenceKind.LINK, "http://x", "a1"))
    )
    task = env.task("t1")
    assert task is not None
    assert [e.content for e in task.criteria[0].evidence] == ["http://x"]
    assert event_types(env) == [EventType.EVIDENCE_ATTACHED]
    rejected(env.service.attach_evidence(A1, "t1", "nope", PROOF), RejectionCode.UNKNOWN_CRITERION)


def test_a_comment_is_logged_and_stored_with_its_time(env: Env, make_task: MakeTask):
    env.put(make_task(status=Status.IN_PROGRESS, assignee="a1"))
    allowed(env.service.comment(A1, "t1", "Halfway there"))
    rejected(env.service.comment(A1, "t1", "   "), RejectionCode.EMPTY_TEXT)
    (comment,) = env.comments("t1")
    assert (comment.author, comment.text) == ("a1", "Halfway there")
    assert event_types(env) == [EventType.COMMENT_ADDED]


# --- dependencies and subtasks ------------------------------------------------------------


def test_dependencies_reject_cycles_and_unknown_tasks(env: Env, make_task: MakeTask):
    env.put(make_task(id="a", status=Status.BACKLOG), make_task(id="b", status=Status.BACKLOG))
    allowed(env.service.add_dependency(OWNER, "a", "b"))  # a is blocked by b
    rejected(env.service.add_dependency(OWNER, "b", "a"), RejectionCode.DEPENDENCY_CYCLE)
    rejected(env.service.add_dependency(OWNER, "a", "a"), RejectionCode.DEPENDENCY_CYCLE)
    rejected(env.service.add_dependency(OWNER, "a", "ghost"), RejectionCode.UNKNOWN_DEPENDENCY)
    rejected(env.service.add_dependency(A1, "a", "b"), RejectionCode.NOT_FOUND)
    task = env.task("a")
    assert task is not None and task.blocked_by == frozenset({"b"})
    allowed(env.service.remove_dependency(ORCH, "a", "b"))
    task = env.task("a")
    assert task is not None and task.blocked_by == frozenset()


def test_longer_cycles_are_refused_too(env: Env, make_task: MakeTask):
    env.put(*(make_task(id=name, status=Status.BACKLOG) for name in "abc"))
    allowed(env.service.add_dependency(OWNER, "a", "b"))
    allowed(env.service.add_dependency(OWNER, "b", "c"))
    rejected(env.service.add_dependency(OWNER, "c", "a"), RejectionCode.DEPENDENCY_CYCLE)


def test_subtasks_are_added_and_moved_by_who_carries_the_task(env: Env, make_task: MakeTask):
    env.put(make_task(status=Status.IN_PROGRESS, assignee="a1"))
    allowed(env.service.add_subtask(OWNER, "t1", Subtask("s1", "Step one")))
    rejected(
        env.service.add_subtask(A1, "t1", Subtask("s2", "Sneaky")), RejectionCode.NOT_PERMITTED
    )
    allowed(env.service.move_subtask(A1, "t1", "s1", SubtaskStatus.IN_REVIEW))
    rejected(
        env.service.move_subtask(A1, "t1", "s1", SubtaskStatus.DONE), RejectionCode.NOT_PERMITTED
    )
    allowed(env.service.move_subtask(OWNER, "t1", "s1", SubtaskStatus.DONE))
    task = env.task("t1")
    assert task is not None and task.subtasks == (Subtask("s1", "Step one", SubtaskStatus.DONE),)
    assert event_types(env) == [
        EventType.SUBTASK_ADDED,
        EventType.SUBTASK_STATUS_CHANGED,
        EventType.SUBTASK_STATUS_CHANGED,
    ]


# --- approval requests --------------------------------------------------------------------


def test_a_cancellation_request_is_stored_and_the_owner_resolves_it(env: Env, make_task: MakeTask):
    env.put(make_task(status=Status.IN_PROGRESS, assignee="a1"))
    allowed(env.service.request_cancellation(A1, "t1", "Obsolete"))
    pending = env.pending("t1")
    assert pending is not None and pending.kind is RequestKind.CANCELLATION
    rejected(env.service.request_cancellation(A1, "t1", "Again"), RejectionCode.DUPLICATE_REQUEST)
    rejected(env.service.resolve_request(A1, "t1", True, None), RejectionCode.NOT_PERMITTED)
    rejected(env.service.resolve_request(OWNER, "t1", False, "  "), RejectionCode.REASON_REQUIRED)
    allowed(env.service.resolve_request(OWNER, "t1", True, None))
    task = env.task("t1")
    assert task is not None
    assert task.status is Status.CANCELLED and task.assignee is None
    assert env.pending("t1") is None
    rejected(
        env.service.resolve_request(OWNER, "t1", True, None), RejectionCode.REQUEST_NOT_PENDING
    )


def test_rejecting_a_cancellation_leaves_the_task_alone(env: Env, make_task: MakeTask):
    env.put(make_task(status=Status.IN_PROGRESS, assignee="a1"))
    allowed(env.service.request_cancellation(A1, "t1", "Obsolete"))
    allowed(env.service.resolve_request(OWNER, "t1", False, "Keep going"))
    task = env.task("t1")
    assert task is not None and task.status is Status.IN_PROGRESS and task.assignee == "a1"
    assert env.pending("t1") is None


def test_approving_a_delivery_completes_the_task_and_its_subtasks_in_review(
    env: Env, make_task: MakeTask
):
    env.put(
        _reviewable(
            make_task,
            subtasks=(
                Subtask("s1", "A", SubtaskStatus.IN_REVIEW),
                Subtask("s2", "B", SubtaskStatus.CANCELLED),
            ),
        )
    )
    allowed(env.service.move_task(A1, "t1", Status.IN_REVIEW))
    rejected(env.service.resolve_request(ORCH, "t1", True, None), RejectionCode.NOT_PERMITTED)
    allowed(env.service.resolve_request(OWNER, "t1", True, None))
    task = env.task("t1")
    assert task is not None and task.status is Status.DONE
    assert [s.status for s in task.subtasks] == [SubtaskStatus.DONE, SubtaskStatus.CANCELLED]
    assert env.pending("t1") is None
    assert env.verify().ok


def test_returning_a_delivery_keeps_the_assignment(env: Env, make_task: MakeTask):
    env.put(_reviewable(make_task))
    allowed(env.service.move_task(A1, "t1", Status.IN_REVIEW))
    allowed(env.service.resolve_request(OWNER, "t1", False, "Please redo the tests"))
    task = env.task("t1")
    assert task is not None and task.status is Status.READY and task.assignee == "a1"


def test_an_event_names_the_subagent_that_acted(env: Env, make_task: MakeTask):
    env.put(make_task(status=Status.IN_PROGRESS, assignee="a1"))
    subagent = replace(A1, via="reviewer-sub")
    allowed(env.service.comment(subagent, "t1", "From a helper"))
    (event,) = env.events()
    assert (event.actor_id, event.via) == ("a1", "reviewer-sub")
