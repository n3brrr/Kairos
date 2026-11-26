"""Baseline schema: items, history, defense-in-depth indexes and triggers, seeded task types.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GENESIS = "0" * 64

# The five starting task types. The design fixes the idea, not the values.
TASK_TYPES: list[dict[str, object]] = [
    {"name": "bug", "required_fields": ["description"], "criteria_template": []},
    {"name": "feature", "required_fields": ["description", "priority"], "criteria_template": []},
    {"name": "chore", "required_fields": [], "criteria_template": []},
    {"name": "research", "required_fields": ["description"], "criteria_template": []},
    {"name": "personal", "required_fields": [], "criteria_template": []},
]


def upgrade() -> None:
    task_types = op.create_table(
        "task_types",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("required_fields", sa.JSON(), nullable=False),
        sa.Column("criteria_template", sa.JSON(), nullable=False),
    )
    op.bulk_insert(task_types, TASK_TYPES)

    op.create_table(
        "agents",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("allowed_task_types", sa.JSON(), nullable=False),
        sa.Column("allowed_project_ids", sa.JSON(), nullable=False),
        sa.Column("queue_limit", sa.Integer(), nullable=False),
        sa.CheckConstraint("kind IN ('agent', 'orchestrator')", name="ck_agents_kind"),
        sa.CheckConstraint("queue_limit >= 1", name="ck_agents_queue_limit"),
    )

    op.create_table(
        "items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Text(), sa.ForeignKey("items.id")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("area", sa.Text()),
        sa.Column("project_id", sa.Text(), sa.ForeignKey("items.id")),
        sa.Column("type", sa.Text(), sa.ForeignKey("task_types.name")),
        sa.Column("priority", sa.Text()),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("labels", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("start_date", sa.Date()),
        sa.Column("due_date", sa.Date()),
        sa.Column("recurrence", sa.Text()),
        sa.Column("created_by", sa.Text()),
        sa.Column("assignee_id", sa.Text(), sa.ForeignKey("agents.id")),
        sa.Column("delivery_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("working_notes", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("kind IN ('project', 'epic', 'task', 'subtask')", name="ck_items_kind"),
        sa.CheckConstraint(
            "(kind = 'project' AND status IN ('active', 'queued', 'paused', 'archived'))"
            " OR (kind = 'epic' AND status IS NULL)"
            " OR (kind = 'task' AND status IN ('proposed', 'backlog', 'ready', 'in_progress',"
            " 'in_review', 'done', 'cancelled'))"
            " OR (kind = 'subtask' AND status IN ('todo', 'in_progress', 'in_review', 'done',"
            " 'cancelled'))",
            name="ck_items_status",
        ),
        sa.CheckConstraint(
            "(kind = 'project' AND parent_id IS NULL)"
            " OR (kind IN ('epic', 'subtask') AND parent_id IS NOT NULL)"
            " OR kind = 'task'",
            name="ck_items_parent",
        ),
        sa.CheckConstraint("(kind = 'project') = (area IS NOT NULL)", name="ck_items_area"),
        sa.CheckConstraint(
            "(kind = 'task' AND project_id IS NOT NULL AND type IS NOT NULL"
            " AND priority IS NOT NULL AND created_by IS NOT NULL)"
            " OR (kind <> 'task' AND project_id IS NULL AND type IS NULL AND priority IS NULL"
            " AND created_by IS NULL AND assignee_id IS NULL)",
            name="ck_items_task_fields",
        ),
        sa.CheckConstraint(
            "priority IS NULL OR priority IN ('P0', 'P1', 'P2', 'P3')", name="ck_items_priority"
        ),
    )
    op.create_index("ix_items_parent", "items", ["parent_id"])
    op.create_index(
        "one_in_progress_per_agent",
        "items",
        ["assignee_id"],
        unique=True,
        sqlite_where=sa.text("kind = 'task' AND status = 'in_progress'"),
    )

    op.create_table(
        "criteria",
        sa.Column("task_id", sa.Text(), sa.ForeignKey("items.id"), primary_key=True),
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
    )
    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("criterion_id", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("added_by", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["task_id", "criterion_id"], ["criteria.task_id", "criteria.id"]),
        sa.CheckConstraint("kind IN ('text', 'link', 'command_output')", name="ck_evidence_kind"),
    )
    op.create_table(
        "dependencies",
        sa.Column("task_id", sa.Text(), sa.ForeignKey("items.id"), primary_key=True),
        sa.Column("blocker_id", sa.Text(), sa.ForeignKey("items.id"), primary_key=True),
        sa.CheckConstraint("task_id <> blocker_id", name="ck_dependencies_not_self"),
    )
    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Text(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("at", sa.Text(), nullable=False),
    )
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Text(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.CheckConstraint("kind IN ('delivery', 'cancellation')", name="ck_requests_kind"),
        sa.CheckConstraint(
            "state IN ('pending', 'approved', 'rejected')", name="ck_requests_state"
        ),
    )
    op.create_index(
        "one_pending_request_per_task",
        "approval_requests",
        ["task_id"],
        unique=True,
        sqlite_where=sa.text("state = 'pending'"),
    )

    op.create_table(
        "events",
        sa.Column("seq", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id", sa.Text(), nullable=False, unique=True),
        sa.Column("at", sa.Text(), nullable=False),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("via", sa.Text()),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("prev_hash", sa.Text(), nullable=False),
        sa.Column("hash", sa.Text(), nullable=False, unique=True),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_events_entity", "events", ["entity_id", "seq"])
    for verb in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER events_no_{verb.lower()} BEFORE {verb} ON events "
            "BEGIN SELECT RAISE(ABORT, 'events is append-only'); END"
        )
    op.execute(
        "CREATE TRIGGER events_chain_check BEFORE INSERT ON events "
        "WHEN NEW.prev_hash IS NOT COALESCE("
        f"(SELECT hash FROM events ORDER BY seq DESC LIMIT 1), '{GENESIS}') "
        "BEGIN SELECT RAISE(ABORT, 'events chain broken: prev_hash is not the last hash'); END"
    )


def downgrade() -> None:
    for trigger in ("events_chain_check", "events_no_delete", "events_no_update"):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    op.drop_index("ix_events_entity", "events")
    op.drop_table("events")
    op.drop_index("one_pending_request_per_task", "approval_requests")
    op.drop_table("approval_requests")
    op.drop_table("comments")
    op.drop_table("dependencies")
    op.drop_table("evidence")
    op.drop_table("criteria")
    op.drop_index("one_in_progress_per_agent", "items")
    op.drop_index("ix_items_parent", "items")
    op.drop_table("items")
    op.drop_table("agents")
    op.drop_table("task_types")
