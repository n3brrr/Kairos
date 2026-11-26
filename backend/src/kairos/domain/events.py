"""Event types the domain asks to record. Persisting and hashing them is slice 2."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from kairos.domain.actor import Actor


class EventType(StrEnum):
    ITEM_CREATED = "item_created"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    GATE_OVERRIDDEN = "gate_overridden"
    FIELDS_UPDATED = "fields_updated"
    EVIDENCE_ATTACHED = "evidence_attached"
    COMMENT_ADDED = "comment_added"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    DEPENDENCY_ADDED = "dependency_added"
    DEPENDENCY_REMOVED = "dependency_removed"
    SUBTASK_ADDED = "subtask_added"
    SUBTASK_STATUS_CHANGED = "subtask_status_changed"
    AGENT_REGISTERED = "agent_registered"


@dataclass(frozen=True)
class Event:
    """One recorded fact. The actor carries `via` (the subagent), when there is one."""

    type: EventType
    entity_id: str
    actor: Actor
    payload: Mapping[str, object]
    reason: str | None = None
