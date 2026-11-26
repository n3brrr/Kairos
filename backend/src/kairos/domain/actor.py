"""Who performs an action, and the scope an agent was given."""

from dataclasses import dataclass
from enum import StrEnum


class ActorKind(StrEnum):
    OWNER = "owner"
    AGENT = "agent"
    ORCHESTRATOR = "orchestrator"
    SYSTEM = "system"


@dataclass(frozen=True)
class Actor:
    """The caller of a use case. `via` names the subagent that acted, as attribution only."""

    kind: ActorKind
    id: str
    via: str | None = None


@dataclass(frozen=True)
class AgentProfile:
    """What an agent or the orchestrator may work on. `kind` is `AGENT` or `ORCHESTRATOR`."""

    id: str
    kind: ActorKind
    allowed_task_types: frozenset[str]
    allowed_project_ids: frozenset[str]
    queue_limit: int = 3
