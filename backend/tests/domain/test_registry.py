from collections.abc import Callable
from typing import Any

import pytest

from kairos.domain.actor import Actor, ActorKind, AgentProfile
from kairos.domain.decision import Rejected, RejectionCode
from kairos.domain.events import EventType
from kairos.domain.registry import (
    Created,
    Epic,
    Project,
    RegistryDecision,
    decide_create_epic,
    decide_create_project,
    decide_register_agent,
)
from kairos.domain.status import ProjectStatus

ACTORS = {
    ActorKind.OWNER: Actor(ActorKind.OWNER, "owner"),
    ActorKind.ORCHESTRATOR: Actor(ActorKind.ORCHESTRATOR, "o1"),
    ActorKind.AGENT: Actor(ActorKind.AGENT, "a1"),
    ActorKind.SYSTEM: Actor(ActorKind.SYSTEM, "sys"),
}
OWNER = ACTORS[ActorKind.OWNER]
PROJECT = Project("p1", "Kairos", "Development")
EPIC = Epic("e1", "p1", "Persistence")
PROFILE = AgentProfile("a1", ActorKind.AGENT, frozenset({"bug"}), frozenset({"p1"}))

Decide = Callable[[Actor], RegistryDecision[Any]]
OPERATIONS: dict[str, Decide] = {
    "project": lambda actor: decide_create_project(actor, PROJECT),
    "epic": lambda actor: decide_create_epic(actor, EPIC, True),
    "agent": lambda actor: decide_register_agent(actor, PROFILE),
}


@pytest.mark.parametrize("operation", list(OPERATIONS))
@pytest.mark.parametrize("kind", list(ACTORS))
def test_only_the_owner_registers_anything(kind: ActorKind, operation: str):
    decision = OPERATIONS[operation](ACTORS[kind])
    if kind is ActorKind.OWNER:
        assert isinstance(decision, Created)
        assert len(decision.events) == 1
        assert decision.events[0].actor == OWNER
    else:
        assert isinstance(decision, Rejected)
        assert decision.code is RejectionCode.NOT_PERMITTED


def test_project_starts_active_and_records_item_created():
    created = decide_create_project(OWNER, PROJECT)
    assert isinstance(created, Created)
    assert created.item.status is ProjectStatus.ACTIVE
    (event,) = created.events
    assert event.type is EventType.ITEM_CREATED
    assert event.entity_id == "p1"
    assert event.payload == {"kind": "project", "title": "Kairos"}


def test_epic_records_item_created_with_its_project():
    created = decide_create_epic(OWNER, EPIC, True)
    assert isinstance(created, Created)
    (event,) = created.events
    assert event.type is EventType.ITEM_CREATED
    assert event.payload == {"kind": "epic", "title": "Persistence", "project": "p1"}


def test_agent_registration_records_its_kind_and_queue_limit():
    created = decide_register_agent(OWNER, PROFILE)
    assert isinstance(created, Created)
    assert created.item == PROFILE
    (event,) = created.events
    assert event.type is EventType.AGENT_REGISTERED
    assert event.entity_id == "a1"
    assert event.payload == {"kind": "agent", "queue_limit": 3}


def _code(decision: RegistryDecision[Any]) -> RejectionCode:
    assert isinstance(decision, Rejected), decision
    return decision.code


@pytest.mark.parametrize(
    "project",
    [
        Project("p1", "  ", "Development"),
        Project("p1", "Kairos", ""),
        Project(" ", "Kairos", "Development"),
    ],
)
def test_project_needs_id_title_and_area(project: Project):
    assert _code(decide_create_project(OWNER, project)) is RejectionCode.EMPTY_TEXT


@pytest.mark.parametrize("epic", [Epic("e1", "p1", " "), Epic("", "p1", "Title")])
def test_epic_needs_id_and_title(epic: Epic):
    assert _code(decide_create_epic(OWNER, epic, True)) is RejectionCode.EMPTY_TEXT


def test_epic_needs_an_existing_project():
    assert _code(decide_create_epic(OWNER, EPIC, False)) is RejectionCode.NOT_FOUND


def test_an_agent_profile_may_describe_the_orchestrator():
    orchestrator = AgentProfile("o1", ActorKind.ORCHESTRATOR, frozenset(), frozenset())
    assert isinstance(decide_register_agent(OWNER, orchestrator), Created)


@pytest.mark.parametrize("kind", [ActorKind.OWNER, ActorKind.SYSTEM])
def test_a_profile_cannot_be_an_owner_or_the_system(kind: ActorKind):
    profile = AgentProfile("x", kind, frozenset(), frozenset())
    assert _code(decide_register_agent(OWNER, profile)) is RejectionCode.FIELD_NOT_ALLOWED


@pytest.mark.parametrize("limit", [0, -1])
def test_queue_limit_is_at_least_one(limit: int):
    profile = AgentProfile("a1", ActorKind.AGENT, frozenset(), frozenset(), queue_limit=limit)
    assert _code(decide_register_agent(OWNER, profile)) is RejectionCode.FIELD_NOT_ALLOWED


def test_a_profile_needs_an_id():
    profile = AgentProfile(" ", ActorKind.AGENT, frozenset(), frozenset())
    assert _code(decide_register_agent(OWNER, profile)) is RejectionCode.EMPTY_TEXT
