"""Agents never approve, cancel or delete: tried through every way the service offers."""

import inspect
from collections.abc import Callable

import pytest

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.decision import Allowed, Rejected
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
from kairos.features.tasks.service import TaskService

from .support import Env

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
A1 = Actor(ActorKind.AGENT, "a1")
SUBAGENT = Actor(ActorKind.AGENT, "a1", via="helper")
NON_OWNERS = [A1, SUBAGENT, ORCH]
PROOF = Evidence(EvidenceKind.TEXT, "ok", "a1")
CLOSING = (Status.DONE, Status.CANCELLED)

MakeTask = Callable[..., Task]


def _state(make_task: MakeTask, status: Status) -> Task:
    return make_task(
        status=status,
        assignee="a1"
        if status not in (Status.PROPOSED, Status.BACKLOG, Status.CANCELLED)
        else None,
        criteria=(Criterion("c1", "works", (PROOF,)),),
        delivery_summary="Done",
        subtasks=(Subtask("s1", "Step", SubtaskStatus.IN_REVIEW),),
    )


@pytest.mark.parametrize("actor", NON_OWNERS, ids=["agent", "subagent", "orchestrator"])
def test_no_move_by_a_non_owner_ever_reaches_done_or_cancelled(
    env: Env, make_task: MakeTask, actor: Actor
):
    for source in Status:
        for target in Status:
            env.put(_state(make_task, source))
            result = env.service.move_task(
                actor, "t1", target, reason="Because", override_reason="Urgent"
            )
            if isinstance(result, Allowed):
                assert target not in CLOSING, (source, target, actor.kind)
                assert source not in CLOSING, (source, target, actor.kind)  # nor reopens
                assert env.task("t1") == result.task


@pytest.mark.parametrize("actor", NON_OWNERS, ids=["agent", "subagent", "orchestrator"])
@pytest.mark.parametrize("approve", [True, False])
def test_no_non_owner_resolves_a_request(
    env: Env, make_task: MakeTask, actor: Actor, approve: bool
):
    for kind in RequestKind:
        env.put(_state(make_task, Status.IN_REVIEW))
        env.put_request(ApprovalRequest("t1", kind, "a1", "Please"))
        before = env.snapshot()
        result = env.service.resolve_request(actor, "t1", approve, "Because")
        assert isinstance(result, Rejected), (kind, approve)
        assert env.snapshot() == before
        env.put(_state(make_task, Status.IN_REVIEW))  # same task row; clear the pending request
        with env.engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM approval_requests")


@pytest.mark.parametrize("actor", NON_OWNERS, ids=["agent", "subagent", "orchestrator"])
@pytest.mark.parametrize("target", [SubtaskStatus.DONE, SubtaskStatus.CANCELLED])
def test_no_non_owner_approves_or_cancels_a_subtask(
    env: Env, make_task: MakeTask, actor: Actor, target: SubtaskStatus
):
    for source in SubtaskStatus:
        env.put(
            make_task(
                status=Status.IN_PROGRESS, assignee="a1", subtasks=(Subtask("s1", "S", source),)
            )
        )
        result = env.service.move_subtask(actor, "t1", "s1", target, reason="Because")
        assert isinstance(result, Rejected), (source, target)


FORBIDDEN_CHANGES: dict[str, dict[str, object]] = {
    "status-done": {"status": Status.DONE},
    "status-cancelled": {"status": Status.CANCELLED},
    "assignee": {"assignee": "a1"},
    "blocked_by": {"blocked_by": frozenset()},
    "created_by": {"created_by": "a1"},
    "id": {"id": "other"},
    "project": {"project_id": "p2"},
}


@pytest.mark.parametrize("actor", NON_OWNERS, ids=["agent", "subagent", "orchestrator"])
@pytest.mark.parametrize("name", list(FORBIDDEN_CHANGES))
def test_no_non_owner_writes_status_or_ownership_through_the_fields(
    env: Env, make_task: MakeTask, actor: Actor, name: str
):
    env.put(_state(make_task, Status.IN_PROGRESS))
    before = env.snapshot()
    result = env.service.update_fields(actor, "t1", FORBIDDEN_CHANGES[name])
    assert isinstance(result, Rejected), name
    assert env.snapshot() == before


def test_the_service_has_no_way_to_delete_and_every_public_method_is_accounted_for():
    public = {
        name
        for name, _member in inspect.getmembers(TaskService, inspect.isfunction)
        if not name.startswith("_")
    }
    assert public == {
        "create_task",
        "update_fields",
        "attach_evidence",
        "comment",
        "move_task",
        "assign_task",
        "unassign_task",
        "add_dependency",
        "remove_dependency",
        "add_subtask",
        "move_subtask",
        "request_cancellation",
        "resolve_request",
    }, "a new use case needs a boundary test here (and nothing may delete)"
    assert not any("delete" in name or "remove_task" in name for name in public)
