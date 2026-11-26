"""Registering projects, epics and agent profiles: the owner decides, the database remembers."""

from collections.abc import Callable

from sqlalchemy import Engine

from kairos.adapters.runtime import Clock, NewId
from kairos.domain.actor import Actor, AgentProfile
from kairos.domain.decision import Rejected, RejectionCode
from kairos.domain.registry import (
    Created,
    Epic,
    Project,
    RegistryDecision,
    decide_create_epic,
    decide_create_project,
    decide_register_agent,
)
from kairos.features.history.log import append_events
from kairos.features.tasks.unit_of_work import UnitOfWork


def _exists(what: str) -> Rejected:
    return Rejected(RejectionCode.ALREADY_EXISTS, f"That {what} already exists.")


class RegistryService:
    def __init__(self, engine: Engine, clock: Clock, new_id: NewId) -> None:
        self._engine = engine
        self._clock = clock
        self._new_id = new_id

    def create_project(self, actor: Actor, project: Project) -> RegistryDecision[Project]:
        with UnitOfWork(self._engine) as uow:
            decision = decide_create_project(actor, project)
            if isinstance(decision, Created) and uow.registry.item_exists(project.id):
                decision = _exists("project")
            return self._finish(uow, decision, uow.registry.save_project)

    def create_epic(self, actor: Actor, epic: Epic) -> RegistryDecision[Epic]:
        with UnitOfWork(self._engine) as uow:
            decision = decide_create_epic(actor, epic, uow.registry.project_exists(epic.project_id))
            if isinstance(decision, Created) and uow.registry.item_exists(epic.id):
                decision = _exists("epic")
            return self._finish(uow, decision, uow.registry.save_epic)

    def register_agent(self, actor: Actor, profile: AgentProfile) -> RegistryDecision[AgentProfile]:
        with UnitOfWork(self._engine) as uow:
            decision = decide_register_agent(actor, profile)
            if isinstance(decision, Created) and uow.registry.get_agent(profile.id) is not None:
                decision = _exists("agent")
            return self._finish(uow, decision, uow.registry.save_agent)

    def _finish[T](
        self, uow: UnitOfWork, decision: RegistryDecision[T], save: Callable[[T], None]
    ) -> RegistryDecision[T]:
        if isinstance(decision, Rejected):
            uow.rollback()
            return decision
        save(decision.item)
        append_events(uow.conn, decision.events, self._clock(), self._new_id)
        return decision
