"""Creating tasks and changing their fields, evidence, comments and dependencies.

Who may change what is design §6.5: the owner and the orchestrator define a task; an agent
may only draft inside its own proposal, and afterwards attach evidence and write its delivery
summary and working notes.
"""

from collections.abc import Mapping
from dataclasses import replace

from kairos.domain.actor import Actor, ActorKind, AgentProfile
from kairos.domain.decision import Allowed, Decision, Rejected, RejectionCode
from kairos.domain.events import Event, EventType
from kairos.domain.graph import would_create_cycle
from kairos.domain.model import Criterion, Evidence, Task, is_blank
from kairos.domain.status import CLOSED, Status

# Fields that `decide_update_fields` may change. `status`, `assignee` and `blocked_by` have their
# own decisions; `id`, `created_by` and `project_id` never change.
EDITABLE_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "description",
        "type",
        "priority",
        "labels",
        "parent_id",
        "start_date",
        "due_date",
        "recurrence",
        "criteria",
        "subtasks",
        "delivery_summary",
        "working_notes",
    }
)
# What an agent may change on the task it carries, once the task has been triaged.
ASSIGNEE_FIELDS: frozenset[str] = frozenset({"delivery_summary", "working_notes"})

_DEFINERS = frozenset({ActorKind.OWNER, ActorKind.ORCHESTRATOR})
_AGENT_KINDS = frozenset({ActorKind.AGENT, ActorKind.ORCHESTRATOR})


def _not_permitted(message: str) -> Rejected:
    return Rejected(RejectionCode.NOT_PERMITTED, message)


def decide_create(actor: Actor, profile: AgentProfile | None, draft: Task) -> Decision:
    """Create a task from `draft`: the owner in `BACKLOG`, everyone else as a proposal."""
    if actor.kind is ActorKind.SYSTEM:
        return _not_permitted("The system actor cannot create tasks yet.")
    if is_blank(draft.title):
        return Rejected(RejectionCode.EMPTY_TEXT, "A task needs a title.")
    status = Status.BACKLOG
    if actor.kind in _AGENT_KINDS:
        if profile is None:
            return _not_permitted("An agent needs a profile to create a proposal.")
        if draft.type not in profile.allowed_task_types or (
            draft.project_id not in profile.allowed_project_ids
        ):
            return Rejected(
                RejectionCode.OUT_OF_SCOPE, "The proposal is outside the agent's scope."
            )
        if draft.blocked_by:
            return Rejected(
                RejectionCode.FIELD_NOT_ALLOWED, "An agent cannot set dependencies on a proposal."
            )
        status = Status.PROPOSED
    task = replace(draft, status=status, created_by=actor.id, assignee=None)
    event = Event(
        EventType.ITEM_CREATED, task.id, actor, {"status": status.value, "type": task.type}
    )
    return Allowed(task, (event,))


def _agent_may_edit(task: Task, actor: Actor, fields: frozenset[str]) -> Rejected | None:
    """Why an agent may not apply `fields` to `task`, or None if it may."""
    if task.status is Status.PROPOSED and task.created_by == actor.id:
        return None  # drafting its own proposal: anything editable
    if task.assignee == actor.id and task.status is Status.IN_PROGRESS:
        if fields <= ASSIGNEE_FIELDS:
            return None
        return Rejected(
            RejectionCode.FIELD_NOT_ALLOWED,
            "An agent may only change the delivery summary and working notes of its task.",
        )
    return _not_permitted("An agent can only edit its own proposal or the task it is working on.")


def decide_update_fields(task: Task, actor: Actor, changes: Mapping[str, object]) -> Decision:
    """Change editable fields of `task`."""
    fields = frozenset(changes)
    if not fields or not fields <= EDITABLE_FIELDS:
        return Rejected(RejectionCode.FIELD_NOT_ALLOWED, "No fields, or fields that cannot be set.")
    if actor.kind is ActorKind.ORCHESTRATOR:
        if task.status in CLOSED:
            return Rejected(RejectionCode.WRONG_STATUS, "A closed task cannot be edited.")
    elif actor.kind is ActorKind.AGENT:
        refusal = _agent_may_edit(task, actor, fields)
        if refusal is not None:
            return refusal
    elif actor.kind is not ActorKind.OWNER:
        return _not_permitted("The system actor cannot edit tasks yet.")
    # Validate values only after the actor is known to be allowed to change these fields.
    title = changes.get("title")
    if "title" in changes and (not isinstance(title, str) or is_blank(title)):
        return Rejected(RejectionCode.EMPTY_TEXT, "A task needs a title.")
    event = Event(EventType.FIELDS_UPDATED, task.id, actor, {"fields": tuple(sorted(fields))})
    return Allowed(replace(task, **dict(changes)), (event,))


def decide_attach_evidence(
    task: Task, actor: Actor, criterion_id: str, evidence: Evidence
) -> Decision:
    """Attach evidence to a criterion: the owner any time, the assignee while in progress."""
    if actor.kind is ActorKind.AGENT:
        if task.assignee != actor.id:
            return Rejected(RejectionCode.NOT_ASSIGNED, "The task is not assigned to this agent.")
        if task.status is not Status.IN_PROGRESS:
            return Rejected(RejectionCode.WRONG_STATUS, "Evidence is attached while in progress.")
    elif actor.kind is not ActorKind.OWNER:
        return _not_permitted("Only the owner or the assigned agent attaches evidence.")
    if is_blank(evidence.content):
        return Rejected(RejectionCode.EMPTY_TEXT, "Evidence cannot be empty.")
    if not any(criterion.id == criterion_id for criterion in task.criteria):
        return Rejected(
            RejectionCode.UNKNOWN_CRITERION, f"The task has no criterion {criterion_id}."
        )
    stamped = replace(evidence, added_by=actor.id)
    criteria = tuple(
        Criterion(c.id, c.text, (*c.evidence, stamped)) if c.id == criterion_id else c
        for c in task.criteria
    )
    event = Event(
        EventType.EVIDENCE_ATTACHED,
        task.id,
        actor,
        {"criterion": criterion_id, "kind": stamped.kind.value},
    )
    return Allowed(replace(task, criteria=criteria), (event,))


def decide_comment(task: Task, actor: Actor, text: str) -> Decision:
    """Add a comment: the owner and the orchestrator always, an agent on the task it carries."""
    if actor.kind not in _DEFINERS and not (
        actor.kind is ActorKind.AGENT and task.assignee == actor.id
    ):
        return _not_permitted("This actor cannot comment on this task.")
    if is_blank(text):
        return Rejected(RejectionCode.EMPTY_TEXT, "A comment cannot be empty.")
    return Allowed(task, (Event(EventType.COMMENT_ADDED, task.id, actor, {"text": text}),))


def decide_add_dependency(
    task: Task, actor: Actor, blocker_id: str, blocked_by: Mapping[str, frozenset[str]]
) -> Decision:
    """Make `task` blocked by `blocker_id`; `blocked_by` maps each known task id to its blockers."""
    if actor.kind not in _DEFINERS:
        return _not_permitted("Only the owner or the orchestrator changes dependencies.")
    if would_create_cycle(blocked_by, blocker_id, task.id):
        return Rejected(RejectionCode.DEPENDENCY_CYCLE, "That dependency would create a cycle.")
    if blocker_id not in blocked_by:
        return Rejected(RejectionCode.UNKNOWN_DEPENDENCY, f"Unknown task {blocker_id}.")
    if blocker_id in task.blocked_by:
        return Allowed(task, ())
    event = Event(EventType.DEPENDENCY_ADDED, task.id, actor, {"blocker": blocker_id})
    return Allowed(replace(task, blocked_by=task.blocked_by | {blocker_id}), (event,))


def decide_remove_dependency(task: Task, actor: Actor, blocker_id: str) -> Decision:
    if actor.kind not in _DEFINERS:
        return _not_permitted("Only the owner or the orchestrator changes dependencies.")
    if blocker_id not in task.blocked_by:
        return Rejected(RejectionCode.UNKNOWN_DEPENDENCY, f"{blocker_id} does not block this task.")
    event = Event(EventType.DEPENDENCY_REMOVED, task.id, actor, {"blocker": blocker_id})
    return Allowed(replace(task, blocked_by=task.blocked_by - {blocker_id}), (event,))
