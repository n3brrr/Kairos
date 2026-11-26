"""Who may see which task (design §6.9). Field-level context (parent summary, blockers) is the
read model's job in later slices; this is the rule it must apply."""

from kairos.domain.actor import Actor, ActorKind
from kairos.domain.model import Task


def can_view_task(actor: Actor, task: Task) -> bool:
    """The owner and the orchestrator see every task; an agent sees what it carries or proposed."""
    if actor.kind in (ActorKind.OWNER, ActorKind.ORCHESTRATOR):
        return True
    if actor.kind is ActorKind.AGENT:
        return task.assignee == actor.id or task.created_by == actor.id
    return False
