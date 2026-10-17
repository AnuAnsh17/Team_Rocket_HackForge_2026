"""Alembic environment.

The database URL is read from the application settings, so there is exactly one
source of database configuration and no credential can be committed to
``alembic.ini``.
"""

from __future__ import annotations

from logging.config import fileConfig

# Importing the model package populates Base.metadata. A model that is not
# imported by app.models is invisible to autogenerate, which is why that module
# imports every model explicitly.
import app.models  # noqa: F401
from alembic import context
from app.core.config import settings
from app.db.base import Base
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata

# Tables whose data migration must never be attempted by a generated script.
# audit_events is append-only: a mistaken UPDATE or DELETE in a migration would
# rewrite history, so those statements are excluded from autogenerate entirely.
EXCLUDED_FROM_AUTOGENERATE: set[str] = set()

# Naming gotcha: PostgreSQL requires index names to be unique per schema, while
# constraint names need only be unique per table. The naming convention in
# app/db/base.py therefore generates globally unique names for both. Do not
# reintroduce explicit `name=` arguments on UniqueConstraint.


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=False,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
