"""Alembic migration environment for the Security Master service.

Imports the shared declarative ``Base`` and every model module so that all
tables register on ``Base.metadata`` before autogenerate inspects the schema.
The SQLAlchemy URL is read from the ``DATABASE_URL`` environment variable when
set, otherwise it falls back to the ``sqlalchemy.url`` value in alembic.ini.
"""
# ruff: noqa: INP001
# env.py is Alembic's script_location entrypoint, run by file path rather than
# imported as a package member. Adding an __init__.py here would make sql/ a
# package and break script_location resolution, so INP001 is suppressed.

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importing every module that defines tables ensures they all attach to the
# shared Base.metadata before autogenerate runs. models.py owns Base; pp_models
# and transaction_models register additional tables against the same Base.
from security_master.storage import (
    account_models,  # noqa: F401  -- registers the account_mappings table
    entity,  # noqa: F401  -- registers clients + legal_entities Entity Registry tables
    models,  # noqa: F401  -- registers core + Kubera tables, defines Base
    position_models,  # noqa: F401  -- registers broker position-snapshot tables
    pp_models,  # noqa: F401  -- registers pp_* Portfolio Performance tables
    transaction_models,  # noqa: F401  -- registers broker transaction tables
)
from security_master.storage.models import Base

# Alembic Config object providing access to alembic.ini values.
config = context.config

# Configure Python logging from the alembic.ini file when present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Prefer the DATABASE_URL environment variable; fall back to alembic.ini.
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Target metadata for autogenerate. All model modules above feed into this.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode, emitting SQL without a live connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode against a live database connection."""
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
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
