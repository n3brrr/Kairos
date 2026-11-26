"""Who may move a task between statuses, and under which gates (design §6.3, §6.4).

The permissions are one data table (`TRANSITION_RULES`); `decide_transition` interprets it.
"""

from dataclasses import dataclass, replace

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.decision import Allowed, Decision, GateCode, GateFailure, Rejected, RejectionCode
from kairos.domain.events import Event, EventType
from kairos.domain.gates import GateContext, check_gates
from kairos.domain.model import ApprovalRequest, RequestKind, Task, is_blank
from kairos.domain.status import ORDER, Status

_OWNER = frozenset({ActorKind.OWNER})
_TRIAGE = frozenset({ActorKind.OWNER, ActorKind.ORCHESTRATOR})
_WORKER = frozenset({ActorKind.OWNER, ActorKind.AGENT})
_RELEASE = frozenset({ActorKind.OWNER, ActorKind.ORCHESTRATOR, ActorKind.AGENT})

# Gates that protect an invariant rather than a convention: nobody may override them.
_NOT_OVERRIDABLE = frozenset({GateCode.AGENT_BUSY})
# Targets whose gates look at dependencies: only there a cancelled blocker is worth a warning.
_DEPENDENCY_TARGETS = frozenset({Status.IN_PROGRESS, Status.IN_REVIEW})


@dataclass(frozen=True)
class Rule:
    source: Status
    target: Status
    actors: frozenset[ActorKind]
    agent_must_be_assignee: bool = False
    gated: bool = False
    requires_reason: bool = False
    clears_assignment: bool = False


def _build_rules() -> tuple[Rule, ...]:
    rules = [
        Rule(Status.PROPOSED, Status.BACKLOG, _TRIAGE),
        Rule(Status.BACKLOG, Status.READY, _TRIAGE, gated=True),
        Rule(Status.READY, Status.IN_PROGRESS, _WORKER, agent_must_be_assignee=True, gated=True),
        Rule(
            Status.IN_PROGRESS, Status.IN_REVIEW, _WORKER, agent_must_be_assignee=True, gated=True
        ),
        Rule(Status.IN_REVIEW, Status.DONE, _OWNER),
        # Return a delivery with a comment: keeps the assignment.
        Rule(Status.IN_REVIEW, Status.READY, _OWNER, requires_reason=True),
        # Release a task: removes the assignment.
        Rule(
            Status.IN_PROGRESS,
            Status.READY,
            _RELEASE,
            agent_must_be_assignee=True,
            requires_reason=True,
            clears_assignment=True,
        ),
    ]
    listed = {(rule.source, rule.target) for rule in rules}
    for index, source in enumerate(ORDER[:-1]):  # every open status
        for target in ORDER[:index]:  # moving backwards: owner only
            if (source, target) not in listed:
                rules.append(
                    Rule(
                        source,
                        target,
                        _OWNER,
                        gated=target is Status.IN_PROGRESS,
                        clears_assignment=target in (Status.PROPOSED, Status.BACKLOG),
                    )
                )
        # Cancel, or discard a proposal: owner only.
        rules.append(Rule(source, Status.CANCELLED, _OWNER, clears_assignment=True))
    for source in (Status.DONE, Status.CANCELLED):  # reopen: owner only, with a reason
        rules.append(
            Rule(source, Status.BACKLOG, _OWNER, requires_reason=True, clears_assignment=True)
        )
        rules.append(
            Rule(
                source,
                Status.READY,
                _OWNER,
                gated=True,
                requires_reason=True,
                clears_assignment=True,
            )
        )
    return tuple(rules)


TRANSITION_RULES: tuple[Rule, ...] = _build_rules()
_RULES: dict[tuple[Status, Status], Rule] = {(r.source, r.target): r for r in TRANSITION_RULES}


def _reject(code: RejectionCode, message: str, gates: tuple[GateFailure, ...] = ()) -> Rejected:
    return Rejected(code, message, gates)


def decide_transition(
    task: Task,
    actor: Actor,
    target: Status,
    ctx: GateContext,
    *,
    reason: str | None = None,
    override_reason: str | None = None,
) -> Decision:
    """Decide whether `actor` may move `task` to `target`, and what that records."""
    if actor.kind is ActorKind.SYSTEM:
        return _reject(RejectionCode.NOT_PERMITTED, "The system actor has no permissions yet.")
    rule = _RULES.get((task.status, target))
    if rule is None:
        return _reject(
            RejectionCode.INVALID_TRANSITION, f"A task cannot go from {task.status} to {target}."
        )
    if actor.kind not in rule.actors:
        return _reject(
            RejectionCode.NOT_PERMITTED, f"{actor.kind} may not move {task.status} to {target}."
        )
    if actor.kind is ActorKind.AGENT and rule.agent_must_be_assignee and task.assignee != actor.id:
        return _reject(RejectionCode.NOT_ASSIGNED, "The task is not assigned to this agent.")
    if rule.requires_reason and is_blank(reason):
        return _reject(RejectionCode.REASON_REQUIRED, "A reason is required for this transition.")

    events: list[Event] = []
    failures = check_gates(task, target, actor, ctx) if rule.gated else ()
    if failures:
        overridable = not any(f.code in _NOT_OVERRIDABLE for f in failures)
        if not (actor.kind is ActorKind.OWNER and overridable and not is_blank(override_reason)):
            return _reject(
                RejectionCode.GATE_FAILED, " ".join(f.message for f in failures), failures
            )

    changed = Event(
        EventType.STATUS_CHANGED,
        task.id,
        actor,
        {"from": task.status.value, "to": target.value},
        reason,
    )
    events.append(changed)
    if failures:
        events.append(
            Event(
                EventType.GATE_OVERRIDDEN,
                task.id,
                actor,
                {"gates": tuple(f.code.value for f in failures)},
                override_reason,
            )
        )
    new_task = replace(task, status=target)
    if rule.clears_assignment and task.assignee is not None:
        events.append(Event(EventType.UNASSIGNED, task.id, actor, {"agent": task.assignee}, reason))
        new_task = replace(new_task, assignee=None)

    request: ApprovalRequest | None = None
    if target is Status.IN_REVIEW:
        request = ApprovalRequest(task.id, RequestKind.DELIVERY, actor.id, task.delivery_summary)
        events.append(
            Event(
                EventType.APPROVAL_REQUESTED, task.id, actor, {"kind": RequestKind.DELIVERY.value}
            )
        )

    warnings = (
        tuple(
            f"Dependency {blocker} was cancelled and counts as resolved."
            for blocker in sorted(ctx.cancelled_blockers)
        )
        if target in _DEPENDENCY_TARGETS
        else ()
    )
    return Allowed(new_task, tuple(events), warnings, request)
