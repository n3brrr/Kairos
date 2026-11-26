"""The result of a domain decision: `Allowed` (new state and events) or `Rejected`."""

from dataclasses import dataclass
from enum import StrEnum

from kairos.domain.events import Event
from kairos.domain.model import ApprovalRequest, Task


class RejectionCode(StrEnum):
    NOT_PERMITTED = "not_permitted"
    INVALID_TRANSITION = "invalid_transition"
    GATE_FAILED = "gate_failed"
    REASON_REQUIRED = "reason_required"
    ALREADY_ASSIGNED = "already_assigned"
    OUT_OF_SCOPE = "out_of_scope"
    QUEUE_FULL = "queue_full"
    NOT_ASSIGNED = "not_assigned"
    WRONG_STATUS = "wrong_status"
    DEPENDENCY_CYCLE = "dependency_cycle"
    UNKNOWN_DEPENDENCY = "unknown_dependency"
    FIELD_NOT_ALLOWED = "field_not_allowed"
    UNKNOWN_CRITERION = "unknown_criterion"
    EMPTY_TEXT = "empty_text"
    REQUEST_NOT_PENDING = "request_not_pending"
    DUPLICATE_REQUEST = "duplicate_request"
    UNKNOWN_SUBTASK = "unknown_subtask"
    DUPLICATE_SUBTASK = "duplicate_subtask"


class GateCode(StrEnum):
    NO_CRITERIA = "no_criteria"
    OPEN_DEPENDENCIES = "open_dependencies"
    NOT_ASSIGNED_TO_ACTOR = "not_assigned_to_actor"
    AGENT_BUSY = "agent_busy"
    MISSING_REQUIRED_FIELDS = "missing_required_fields"
    CRITERIA_WITHOUT_EVIDENCE = "criteria_without_evidence"
    PENDING_SUBTASKS = "pending_subtasks"
    EMPTY_DELIVERY_SUMMARY = "empty_delivery_summary"


@dataclass(frozen=True)
class GateFailure:
    code: GateCode
    message: str


@dataclass(frozen=True)
class Rejected:
    code: RejectionCode
    message: str
    gates: tuple[GateFailure, ...] = ()


@dataclass(frozen=True)
class Allowed:
    """The new state of the task plus the events (and request) the use case must persist."""

    task: Task
    events: tuple[Event, ...]
    warnings: tuple[str, ...] = ()
    request: ApprovalRequest | None = None


type Decision = Allowed | Rejected
