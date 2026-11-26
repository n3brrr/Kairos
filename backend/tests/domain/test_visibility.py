from dataclasses import replace

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.model import Task
from kairos.domain.status import Status
from kairos.domain.visibility import can_view_task


def _task(**changes: object) -> Task:
    base = Task(
        id="t1",
        title="T",
        type="bug",
        project_id="p1",
        created_by="owner",
        status=Status.READY,
        assignee="a1",
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def test_owner_and_orchestrator_see_every_task():
    for kind in (ActorKind.OWNER, ActorKind.ORCHESTRATOR):
        assert can_view_task(Actor(kind, "x"), _task())
        assert can_view_task(Actor(kind, "x"), _task(assignee=None))


def test_an_agent_sees_what_it_carries_or_proposed():
    agent = Actor(ActorKind.AGENT, "a1")
    assert can_view_task(agent, _task(assignee="a1"))
    assert can_view_task(agent, _task(assignee=None, created_by="a1", status=Status.PROPOSED))


def test_an_agent_does_not_see_other_agents_tasks():
    other = Actor(ActorKind.AGENT, "a2")
    assert not can_view_task(other, _task(assignee="a1"))
    assert not can_view_task(other, _task(assignee=None))


def test_the_system_actor_sees_nothing_yet():
    assert not can_view_task(Actor(ActorKind.SYSTEM, "sys"), _task())
