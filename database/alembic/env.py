"""
Alembic environment configuration.

Imports all models so autogenerate detects them.
Works with both PostgreSQL (production) and SQLite (CI tests).
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

from database.base import Base

config = context.config

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
