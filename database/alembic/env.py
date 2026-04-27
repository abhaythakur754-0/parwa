"""
Alembic environment configuration.

Imports all models so autogenerate detects them.
Works with both PostgreSQL (production) and SQLite (CI tests).

Bug Fix Day 4: script_location can be overridden via ALEMBIC_MIGRATIONS_DIR
environment variable.  When set, it replaces the path from alembic.ini.
Defaults to the current ``alembic/`` relative path for backward compatibility.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Import all models for autogenerate
import database.models.core  # noqa: F401
import database.models.billing  # noqa: F401
import database.models.tickets  # noqa: F401
import database.models.ai_pipeline  # noqa: F401
import database.models.approval  # noqa: F401
import database.models.analytics  # noqa: F401
import database.models.training  # noqa: F401
import database.models.integration  # noqa: F401
import database.models.onboarding  # noqa: F401
import database.models.core_rate_limit  # noqa: F401
import database.models.phone_otp  # noqa: F401
import database.models.api_key_audit  # noqa: F401
import database.models.webhook_event  # noqa: F401
import database.models.remaining  # noqa: F401
import database.models.jarvis  # noqa: F401
import database.models.billing_extended  # noqa: F401
import database.models.user_details  # noqa: F401
import database.models.variant_engine  # noqa: F401
import database.models.technique  # noqa: F401

from database.base import Base

config = context.config

# Bug Fix Day 4: Allow ALEMBIC_MIGRATIONS_DIR to override script_location.
# This supports deploying from different directory structures (Docker,
# CI, bare metal) without modifying alembic.ini.
import os
_migrations_dir = os.environ.get("ALEMBIC_MIGRATIONS_DIR", "")
if _migrations_dir:
    config.set_main_option("script_location", _migrations_dir)

# Override sqlalchemy.url from DATABASE_URL environment variable
# This is required for Docker deployments where the URL comes from env
_database_url = os.environ.get("DATABASE_URL", "")
if _database_url:
    config.set_main_option("sqlalchemy.url", _database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
