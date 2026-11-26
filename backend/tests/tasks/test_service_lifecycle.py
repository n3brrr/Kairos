"""One task from idea to done through the use cases, as the owner, the orchestrator and an agent."""

from collections.abc import Callable

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.decision import Allowed
from kairos.domain.events import EventType
from kairos.domain.model import (
    ApprovalRequest,
    Criterion,
    Evidence,
    EvidenceKind,
    Priority,
    RequestKind,
    Subtask,
    Task,
)
from kairos.domain.status import Status, SubtaskStatus

from .support import Env

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
A1 = Actor(ActorKind.AGENT, "a1", via="helper")


def ok(decision: object) -> Allowed:
    assert isinstance(decision, Allowed), decision
    return decision


def test_a_task_goes_from_creation_to_done_and_the_history_tells_the_story(env: Env):
    service = env.service
    draft = Task(
        id="t1",
        title="Add the approval queue",
        type="bug",
        project_id="p1",
        created_by="owner",
        description="The owner needs one place to decide",
        priority=Priority.P1,
    )
    ok(service.create_task(OWNER, draft))
    ok(
        service.update_fields(
            OWNER, "t1", {"criteria": (Criterion("c1", "The queue lists requests"),)}
        )
    )
    ok(service.add_subtask(ORCH, "t1", Subtask("s1", "Write the query")))
    ok(service.move_task(ORCH, "t1", Status.READY))
    ok(service.assign_task(ORCH, "t1", "a1"))

    ok(service.move_task(A1, "t1", Status.IN_PROGRESS))
    ok(service.move_subtask(A1, "t1", "s1", SubtaskStatus.IN_PROGRESS))
    ok(service.move_subtask(A1, "t1", "s1", SubtaskStatus.IN_REVIEW))
    proof = Evidence(EvidenceKind.COMMAND_OUTPUT, "3 passed", "a1")
    ok(service.attach_evidence(A1, "t1", "c1", proof))
    ok(service.update_fields(A1, "t1", {"delivery_summary": "Query and tests added"}))
    ok(service.move_task(A1, "t1", Status.IN_REVIEW))
    assert env.pending("t1") is not None

    ok(service.resolve_request(OWNER, "t1", True, None))

    task = env.task("t1")
    assert task is not None
    assert task.status is Status.DONE
    assert task.assignee == "a1"  # who delivered stays on record
    assert [s.status for s in task.subtasks] == [SubtaskStatus.DONE]
    assert task.criteria[0].evidence == (proof,)
    assert env.pending("t1") is None

    story = [(e.type, e.actor_kind, e.via) for e in env.events()]
    owner, orch, agent = ActorKind.OWNER, ActorKind.ORCHESTRATOR, ActorKind.AGENT
    assert story == [
        (EventType.ITEM_CREATED, owner, None),
        (EventType.FIELDS_UPDATED, owner, None),
        (EventType.SUBTASK_ADDED, orch, None),
        (EventType.STATUS_CHANGED, orch, None),
        (EventType.ASSIGNED, orch, None),
        (EventType.STATUS_CHANGED, agent, "helper"),
        (EventType.SUBTASK_STATUS_CHANGED, agent, "helper"),
        (EventType.SUBTASK_STATUS_CHANGED, agent, "helper"),
        (EventType.EVIDENCE_ATTACHED, agent, "helper"),
        (EventType.FIELDS_UPDATED, agent, "helper"),
        (EventType.STATUS_CHANGED, agent, "helper"),
        (EventType.APPROVAL_REQUESTED, agent, "helper"),
        (EventType.STATUS_CHANGED, owner, None),
        (EventType.SUBTASK_STATUS_CHANGED, owner, None),
        (EventType.APPROVAL_RESOLVED, owner, None),
    ]
    assert env.verify().ok


def test_returning_a_delivery_lets_the_agent_fix_it_and_submit_again(
    env: Env, make_task: Callable[..., Task]
):
    proof = Evidence(EvidenceKind.TEXT, "ok", "a1")
    env.put(
        make_task(
            status=Status.IN_REVIEW,
            assignee="a1",
            criteria=(Criterion("c1", "works", (proof,)),),
            delivery_summary="First try",
        )
    )
    env.put_request(ApprovalRequest("t1", RequestKind.DELIVERY, "a1", "First try"))
    ok(env.service.resolve_request(OWNER, "t1", False, "Add a test for the empty case"))
    ok(env.service.move_task(A1, "t1", Status.IN_PROGRESS))
    ok(env.service.update_fields(A1, "t1", {"delivery_summary": "Second try, with the test"}))
    ok(env.service.move_task(A1, "t1", Status.IN_REVIEW))
    pending = env.pending("t1")
    assert pending is not None and pending.reason == "Second try, with the test"
    ok(env.service.resolve_request(OWNER, "t1", True, None))
    task = env.task("t1")
    assert task is not None and task.status is Status.DONE
    assert env.verify().ok
