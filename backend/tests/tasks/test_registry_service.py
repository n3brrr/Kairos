from collections.abc import Callable

from kairos.domain.actor import Actor, ActorKind, AgentProfile
from kairos.domain.decision import Rejected, RejectionCode
from kairos.domain.events import EventType
from kairos.domain.model import Task
from kairos.domain.registry import Created, Epic, Project
from kairos.domain.status import Status
from kairos.features.registry.repository import RegistryRepository

from .support import Env

OWNER = Actor(ActorKind.OWNER, "owner")
ORCH = Actor(ActorKind.ORCHESTRATOR, "o1")
A1 = Actor(ActorKind.AGENT, "a1")


def test_the_owner_registers_a_project_an_epic_and_an_agent(env: Env):
    project = env.registry.create_project(OWNER, Project("p9", "New", "Personal"))
    epic = env.registry.create_epic(OWNER, Epic("e9", "p9", "Goal"))
    profile = AgentProfile("a9", ActorKind.AGENT, frozenset({"bug"}), frozenset({"p9"}))
    agent = env.registry.register_agent(OWNER, profile)
    assert all(isinstance(result, Created) for result in (project, epic, agent))
    with env.engine.connect() as conn:
        registry = RegistryRepository(conn)
        assert registry.project_exists("p9")
        assert registry.epic_project_id("e9") == "p9"
        assert registry.get_agent("a9") == profile
    tail = [e.type for e in env.events()]
    assert tail == [EventType.ITEM_CREATED, EventType.ITEM_CREATED, EventType.AGENT_REGISTERED]
    assert env.verify().ok


def test_nobody_but_the_owner_registers_anything_and_nothing_is_written(env: Env):
    before = env.snapshot()
    profile = AgentProfile("x", ActorKind.AGENT, frozenset(), frozenset())
    for actor in (ORCH, A1):
        results = (
            env.registry.create_project(actor, Project("px", "X", "Dev")),
            env.registry.create_epic(actor, Epic("ex", "p1", "X")),
            env.registry.register_agent(actor, profile),
        )
        for result in results:
            assert isinstance(result, Rejected)
            assert result.code is RejectionCode.NOT_PERMITTED
    assert env.snapshot() == before


def test_a_duplicate_id_is_refused_instead_of_replacing_what_exists(env: Env):
    before = env.snapshot()
    results = (
        env.registry.create_project(OWNER, Project("p1", "Again", "Dev")),
        env.registry.create_epic(OWNER, Epic("e1", "p1", "Again")),
        env.registry.create_epic(OWNER, Epic("p1", "p1", "Takes a project's id")),
        env.registry.register_agent(
            OWNER, AgentProfile("a1", ActorKind.AGENT, frozenset({"chore"}), frozenset({"p2"}))
        ),
    )
    for result in results:
        assert isinstance(result, Rejected)
        assert result.code is RejectionCode.ALREADY_EXISTS
    assert env.snapshot() == before


def test_an_epic_needs_an_existing_project(env: Env):
    result = env.registry.create_epic(OWNER, Epic("e9", "ghost", "Lost"))
    assert isinstance(result, Rejected) and result.code is RejectionCode.NOT_FOUND


def test_a_registered_agent_can_be_assigned_work(env: Env, make_task: Callable[..., Task]):
    env.registry.register_agent(
        OWNER, AgentProfile("a9", ActorKind.AGENT, frozenset({"bug"}), frozenset({"p1"}))
    )
    env.put(make_task(status=Status.READY))
    result = env.service.assign_task(OWNER, "t1", "a9")
    assert not isinstance(result, Rejected)
