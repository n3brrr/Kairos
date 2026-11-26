"""The use cases on tasks: load the state, ask the domain, persist what it decided.

Every public method is one transaction. The domain says yes or no and returns the new state and
the events; this module writes them together or, on a `Rejected`, writes nothing (ADR-0003,
ADR-0006). No rule lives here: the references and the gate context it checks are *facts read
from the database*, handed to the domain.
"""

from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError

from kairos.adapters.runtime import Clock, NewId
from kairos.domain.actor import Actor, ActorKind, AgentProfile
from kairos.domain.approval import (
    decide_move_task,
    decide_request_cancellation,
    decide_resolve_request,
)
from kairos.domain.assignment import decide_assign, decide_unassign
from kairos.domain.changes import (
    decide_add_dependency,
    decide_attach_evidence,
    decide_comment,
    decide_create,
    decide_remove_dependency,
    decide_update_fields,
)
from kairos.domain.decision import (
    Allowed,
    Decision,
    GateCode,
    GateFailure,
    Rejected,
    RejectionCode,
)
from kairos.domain.gates import GateContext
from kairos.domain.graph import cancelled_blockers, open_blockers
from kairos.domain.model import Evidence, Subtask, Task, TaskType
from kairos.domain.status import Status, SubtaskStatus
from kairos.domain.subtasks import decide_add_subtask, decide_move_subtask
from kairos.domain.visibility import can_view_task
from kairos.features.history.log import append_events
from kairos.features.tasks.repository import Comment
from kairos.features.tasks.unit_of_work import UnitOfWork

_AGENT_KINDS = frozenset({ActorKind.AGENT, ActorKind.ORCHESTRATOR})


def _not_found(what: str) -> Rejected:
    return Rejected(RejectionCode.NOT_FOUND, f"No such {what}.")


class TaskService:
    def __init__(self, engine: Engine, clock: Clock, new_id: NewId) -> None:
        self._engine = engine
        self._clock = clock
        self._new_id = new_id

    # --- creating and editing ------------------------------------------------------------

    def create_task(self, actor: Actor, draft: Task) -> Decision:
        with UnitOfWork(self._engine) as uow:
            decision = decide_create(actor, self._profile(uow, actor), draft)
            if isinstance(decision, Allowed):
                problem = self._reference_problem(uow, decision.task)
                if problem is None and uow.registry.item_exists(draft.id):
                    problem = Rejected(RejectionCode.ALREADY_EXISTS, f"{draft.id} already exists.")
                decision = problem or decision
            return self._finish(uow, decision)

    def update_fields(self, actor: Actor, task_id: str, changes: Mapping[str, object]) -> Decision:
        with UnitOfWork(self._engine) as uow:
            task = self._load(uow, actor, task_id)
            if isinstance(task, Rejected):
                return self._finish(uow, task)
            decision = decide_update_fields(task, actor, changes, self._profile(uow, actor))
            if isinstance(decision, Allowed) and ({"type", "parent_id"} & changes.keys()):
                decision = self._reference_problem(uow, decision.task) or decision
            return self._finish(uow, decision)

    def attach_evidence(
        self, actor: Actor, task_id: str, criterion_id: str, evidence: Evidence
    ) -> Decision:
        with UnitOfWork(self._engine) as uow:
            task = self._load(uow, actor, task_id)
            if isinstance(task, Rejected):
                return self._finish(uow, task)
            return self._finish(uow, decide_attach_evidence(task, actor, criterion_id, evidence))

    def comment(self, actor: Actor, task_id: str, text: str) -> Decision:
        with UnitOfWork(self._engine) as uow:
            task = self._load(uow, actor, task_id)
            if isinstance(task, Rejected):
                return self._finish(uow, task)
            now = self._clock()
            decision = self._finish(uow, decide_comment(task, actor, text), at=now)
            if isinstance(decision, Allowed):
                uow.tasks.add_comment(Comment(task_id, actor.id, text, now))
            return decision

    # --- status, assignment ---------------------------------------------------------------

    def move_task(
        self,
        actor: Actor,
        task_id: str,
        target: Status,
        *,
        reason: str | None = None,
        override_reason: str | None = None,
    ) -> Decision:
        with UnitOfWork(self._engine) as uow:
            task = self._load(uow, actor, task_id)
            if isinstance(task, Rejected):
                return self._finish(uow, task)
            ctx = self._gate_context(uow, task, actor)
            pending = uow.tasks.get_pending_request(task_id)
            decision = decide_move_task(
                task, actor, target, ctx, pending, reason=reason, override_reason=override_reason
            )
            return self._finish(uow, decision)

    def assign_task(self, actor: Actor, task_id: str, agent_id: str) -> Decision:
        with UnitOfWork(self._engine) as uow:
            task = self._load(uow, actor, task_id)
            if isinstance(task, Rejected):
                return self._finish(uow, task)
            agent = uow.registry.get_agent(agent_id)
            if agent is None:
                return self._finish(uow, _not_found("agent"))
            decision = decide_assign(task, actor, agent, uow.tasks.load(agent_id))
            return self._finish(uow, decision)

    def unassign_task(self, actor: Actor, task_id: str, reason: str | None) -> Decision:
        with UnitOfWork(self._engine) as uow:
            task = self._load(uow, actor, task_id)
            if isinstance(task, Rejected):
                return self._finish(uow, task)
            return self._finish(uow, decide_unassign(task, actor, reason))

    # --- dependencies and subtasks --------------------------------------------------------

    def add_dependency(self, actor: Actor, task_id: str, blocker_id: str) -> Decision:
        with UnitOfWork(self._engine) as uow:
            task = self._load(uow, actor, task_id)
            if isinstance(task, Rejected):
                return self._finish(uow, task)
            blocked_by = uow.tasks.blocked_by_map()
            return self._finish(uow, decide_add_dependency(task, actor, blocker_id, blocked_by))

    def remove_dependency(self, actor: Actor, task_id: str, blocker_id: str) -> Decision:
        with UnitOfWork(self._engine) as uow:
            task = self._load(uow, actor, task_id)
            if isinstance(task, Rejected):
                return self._finish(uow, task)
            return self._finish(uow, decide_remove_dependency(task, actor, blocker_id))

    def add_subtask(self, actor: Actor, task_id: str, subtask: Subtask) -> Decision:
        with UnitOfWork(self._engine) as uow:
            task = self._load(uow, actor, task_id)
            if isinstance(task, Rejected):
                return self._finish(uow, task)
            return self._finish(uow, decide_add_subtask(task, actor, subtask))

    def move_subtask(
        self,
        actor: Actor,
        task_id: str,
        subtask_id: str,
        target: SubtaskStatus,
        *,
        reason: str | None = None,
    ) -> Decision:
        with UnitOfWork(self._engine) as uow:
            task = self._load(uow, actor, task_id)
            if isinstance(task, Rejected):
                return self._finish(uow, task)
            decision = decide_move_subtask(task, actor, subtask_id, target, reason=reason)
            return self._finish(uow, decision)

    # --- approval requests ----------------------------------------------------------------

    def request_cancellation(self, actor: Actor, task_id: str, reason: str | None) -> Decision:
        with UnitOfWork(self._engine) as uow:
            task = self._load(uow, actor, task_id)
            if isinstance(task, Rejected):
                return self._finish(uow, task)
            pending = uow.tasks.get_pending_request(task_id) is not None
            return self._finish(uow, decide_request_cancellation(task, actor, reason, pending))

    def resolve_request(
        self, actor: Actor, task_id: str, approve: bool, note: str | None
    ) -> Decision:
        with UnitOfWork(self._engine) as uow:
            task = self._load(uow, actor, task_id)
            if isinstance(task, Rejected):
                return self._finish(uow, task)
            request = uow.tasks.get_pending_request(task_id)
            if request is None:
                rejection = Rejected(RejectionCode.REQUEST_NOT_PENDING, "No request is pending.")
                return self._finish(uow, rejection)
            ctx = self._gate_context(uow, task, actor)
            return self._finish(
                uow, decide_resolve_request(task, request, actor, approve, note, ctx)
            )

    # --- helpers --------------------------------------------------------------------------

    def _profile(self, uow: UnitOfWork, actor: Actor) -> AgentProfile | None:
        if actor.kind not in _AGENT_KINDS:
            return None
        return uow.registry.get_agent(actor.id)

    def _load(self, uow: UnitOfWork, actor: Actor, task_id: str) -> Task | Rejected:
        """The task, or `NOT_FOUND` when it does not exist or the actor may not see it."""
        task = uow.tasks.get(task_id)
        if task is None or not can_view_task(actor, task):
            return _not_found("task")
        return task

    def _reference_problem(self, uow: UnitOfWork, task: Task) -> Rejected | None:
        """The project, the type and the epic a task points at must exist (and match)."""
        if not uow.registry.project_exists(task.project_id):
            return _not_found("project")
        if uow.tasks.get_task_type(task.type) is None:
            return _not_found("task type")
        if task.parent_id is not None and uow.registry.epic_project_id(task.parent_id) != (
            task.project_id
        ):
            return _not_found("epic in this project")
        return None

    def _gate_context(self, uow: UnitOfWork, task: Task, actor: Actor) -> GateContext:
        """Facts the gates need: the type, the blockers' statuses, the carrier's other work."""
        task_type = uow.tasks.get_task_type(task.type) or TaskType(task.type, frozenset())
        statuses = uow.tasks.statuses(task.blocked_by)
        carrier = actor.id if actor.kind is ActorKind.AGENT else task.assignee
        others = (
            uow.tasks.other_in_progress(carrier, excluding=task.id) if carrier else frozenset[str]()
        )
        return GateContext(
            task_type,
            open_blockers(task, statuses),
            others,
            cancelled_blockers(task, statuses),
        )

    def _finish(
        self, uow: UnitOfWork, decision: Decision, *, at: datetime | None = None
    ) -> Decision:
        """Persist an `Allowed` (task, request, events); on a `Rejected`, write nothing."""
        if isinstance(decision, Rejected):
            uow.rollback()
            return decision
        try:
            uow.tasks.save(decision.task)
            if decision.request is not None:
                uow.tasks.save_request(decision.request)
            append_events(uow.conn, decision.events, at or self._clock(), self._new_id)
        except IntegrityError as error:
            uow.rollback()
            translated = _translate(error)
            if translated is None:
                raise
            return translated
        return decision


def _translate(error: IntegrityError) -> Rejected | None:
    """Turn a database guard that fired into the rejection the domain would have given."""
    message = str(error.orig)
    if "items.assignee_id" in message:
        message = "The agent already has a task in progress."
        failure = GateFailure(GateCode.AGENT_BUSY, message)
        return Rejected(RejectionCode.GATE_FAILED, message, (failure,))
    if "approval_requests.task_id" in message:
        return Rejected(RejectionCode.DUPLICATE_REQUEST, "A request is already pending.")
    if "items.id" in message:
        return Rejected(RejectionCode.ALREADY_EXISTS, "That id is already taken.")
    return None
