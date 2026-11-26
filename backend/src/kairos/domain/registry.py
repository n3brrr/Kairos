"""Registering what tasks hang from: projects, epics and agent profiles. The owner only.

An agent cannot grant itself scope, and the orchestrator cannot create the containers it
assigns work into, so these decisions are the owner's (design §6.3, §6.8).
"""

from dataclasses import dataclass

from kairos.domain.actor import Actor, ActorKind, AgentProfile
from kairos.domain.decision import Rejected, RejectionCode
from kairos.domain.events import Event, EventType
from kairos.domain.model import is_blank
from kairos.domain.status import ProjectStatus


@dataclass(frozen=True)
class Project:
    """Highest-level container. A new project is `ACTIVE`; lifecycle changes come later."""

    id: str
    title: str
    area: str
    status: ProjectStatus = ProjectStatus.ACTIVE


@dataclass(frozen=True)
class Epic:
    """Groups tasks of one goal inside a project. Its status is derived, never stored."""

    id: str
    project_id: str
    title: str


@dataclass(frozen=True)
class Created[T]:
    """The thing to persist and the events to record with it."""

    item: T
    events: tuple[Event, ...]


type RegistryDecision[T] = Created[T] | Rejected


def _owner_only(actor: Actor) -> Rejected | None:
    if actor.kind is not ActorKind.OWNER:
        return Rejected(RejectionCode.NOT_PERMITTED, "Only the owner registers this.")
    return None


def decide_create_project(actor: Actor, project: Project) -> RegistryDecision[Project]:
    if (refusal := _owner_only(actor)) is not None:
        return refusal
    if is_blank(project.id) or is_blank(project.title) or is_blank(project.area):
        return Rejected(RejectionCode.EMPTY_TEXT, "A project needs an id, a title and an area.")
    event = Event(
        EventType.ITEM_CREATED, project.id, actor, {"kind": "project", "title": project.title}
    )
    return Created(project, (event,))


def decide_create_epic(actor: Actor, epic: Epic, project_exists: bool) -> RegistryDecision[Epic]:
    if (refusal := _owner_only(actor)) is not None:
        return refusal
    if is_blank(epic.id) or is_blank(epic.title):
        return Rejected(RejectionCode.EMPTY_TEXT, "An epic needs an id and a title.")
    if not project_exists:
        return Rejected(RejectionCode.NOT_FOUND, f"No project {epic.project_id}.")
    event = Event(
        EventType.ITEM_CREATED,
        epic.id,
        actor,
        {"kind": "epic", "title": epic.title, "project": epic.project_id},
    )
    return Created(epic, (event,))


def decide_register_agent(actor: Actor, profile: AgentProfile) -> RegistryDecision[AgentProfile]:
    if (refusal := _owner_only(actor)) is not None:
        return refusal
    if is_blank(profile.id):
        return Rejected(RejectionCode.EMPTY_TEXT, "An agent needs an id.")
    if profile.kind not in (ActorKind.AGENT, ActorKind.ORCHESTRATOR) or profile.queue_limit < 1:
        return Rejected(
            RejectionCode.FIELD_NOT_ALLOWED,
            "A profile describes an agent or the orchestrator, with a queue of at least one.",
        )
    event = Event(
        EventType.AGENT_REGISTERED,
        profile.id,
        actor,
        {"kind": profile.kind.value, "queue_limit": profile.queue_limit},
    )
    return Created(profile, (event,))
