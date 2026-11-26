"""Storing projects, epics and agent profiles. Works inside the caller's transaction."""

from collections.abc import Mapping

from sqlalchemy import Connection, RowMapping, literal_column, select
from sqlalchemy.dialects.sqlite import insert

from kairos.adapters.db.schema import agents, items
from kairos.domain.actor import ActorKind, AgentProfile
from kairos.domain.registry import Epic, Project


class RegistryRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def save_project(self, project: Project) -> None:
        values = {
            "id": project.id,
            "kind": "project",
            "title": project.title,
            "status": project.status.value,
            "area": project.area,
        }
        self._upsert_item(values)

    def save_epic(self, epic: Epic) -> None:
        values = {
            "id": epic.id,
            "kind": "epic",
            "parent_id": epic.project_id,
            "title": epic.title,
        }
        self._upsert_item(values)

    def _upsert_item(self, values: Mapping[str, object]) -> None:
        statement = insert(items).values(**values)
        changed = {key: statement.excluded[key] for key in values if key not in ("id", "kind")}
        self._conn.execute(statement.on_conflict_do_update(index_elements=["id"], set_=changed))

    def project_exists(self, project_id: str) -> bool:
        found = self._conn.execute(
            select(items.c.id).where(items.c.id == project_id, items.c.kind == "project")
        ).first()
        return found is not None

    def save_agent(self, profile: AgentProfile) -> None:
        values = {
            "id": profile.id,
            "kind": profile.kind.value,
            "allowed_task_types": sorted(profile.allowed_task_types),
            "allowed_project_ids": sorted(profile.allowed_project_ids),
            "queue_limit": profile.queue_limit,
        }
        statement = insert(agents).values(**values)
        changed = {key: statement.excluded[key] for key in values if key != "id"}
        self._conn.execute(statement.on_conflict_do_update(index_elements=["id"], set_=changed))

    def get_agent(self, agent_id: str) -> AgentProfile | None:
        row = self._conn.execute(select(agents).where(agents.c.id == agent_id)).mappings().first()
        return _profile(row) if row is not None else None

    def list_agents(self) -> list[AgentProfile]:
        rows = self._conn.execute(select(agents).order_by(literal_column("agents.rowid")))
        return [_profile(row) for row in rows.mappings()]


def _profile(row: RowMapping) -> AgentProfile:
    return AgentProfile(
        id=row["id"],
        kind=ActorKind(row["kind"]),
        allowed_task_types=frozenset(row["allowed_task_types"]),
        allowed_project_ids=frozenset(row["allowed_project_ids"]),
        queue_limit=row["queue_limit"],
    )
