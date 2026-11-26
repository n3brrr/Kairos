"""Alembic environment: migrations run on the engine the caller passes in."""

from alembic import context
from sqlalchemy import Engine

from kairos.adapters.db.schema import metadata

engine: Engine = context.config.attributes["engine"]

with engine.begin() as connection:
    context.configure(connection=connection, target_metadata=metadata)
    context.run_migrations()
