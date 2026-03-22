"""
Database migration and seeding script for PARWA.

This script runs Alembic migrations and then seeds the database
with initial development data. It is designed to be run as a
standalone synchronous script (not async) to avoid conflicts with
Alembic's own asyncio.run() in env.py.
"""
import os
import sys
from pathlib import Path

# Add the project root to the python path so imports work correctly
project_root = str(Path(__file__).parent.parent.parent.absolute())
sys.path.insert(0, project_root)

import alembic.command as alembic_command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from shared.core_functions.logger import get_logger  # noqa: E402

logger = get_logger("seed_db")


def get_sync_db_url() -> str:
    """Build a synchronous database URL from environment/.env."""
    from shared.core_functions.config import get_settings
    settings = get_settings()
    db_url = str(settings.database_url)

    # For seeding we need a SYNCHRONOUS driver (pg8000),
    # not the async one (asyncpg).
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "+pg8000", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace(
            "postgresql://", "postgresql+pg8000://", 1
        )
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace(
            "postgres://", "postgresql+pg8000://", 1
        )
    return db_url


def run_migrations() -> None:
    """Run Alembic migrations up to head."""
    logger.info("Initializing Alembic configuration for migrations...")
    config_path = os.path.join(project_root, "alembic.ini")
    alembic_cfg = Config(config_path)
    script_location = os.path.join(
        project_root, "database", "migrations"
    )
    alembic_cfg.set_main_option("script_location", script_location)

    logger.info("Running `alembic upgrade head`...")
    alembic_command.upgrade(alembic_cfg, "head")
    logger.info("Migrations complete.")


def execute_sql_file(sync_engine, file_path: str) -> None:
    """Execute a raw SQL seed file using a synchronous engine."""
    abs_path = os.path.join(
        project_root, "database", "seeds", file_path
    )

    if not os.path.exists(abs_path):
        logger.warning(f"Seed file not found: {abs_path}")
        return

    logger.info(f"Executing seed file: {file_path}")
    with open(abs_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    try:
        with sync_engine.begin() as conn:
            conn.execute(text(sql_content))
        logger.info(f"Successfully seeded: {file_path}")
    except Exception as e:
        logger.error(
            f"Failed to execute seed {file_path}: {str(e)}"
        )
        raise


def seed_database() -> None:
    """Orchestrate the development environment seeding process."""
    logger.info("Starting local database seed process.")

    # 1. Run migrations first (this uses Alembic's own
    #    async engine internally via env.py)
    try:
        run_migrations()
    except Exception as e:
        logger.error(f"Migration phase failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 2. Create a synchronous engine for seeding
    db_url = get_sync_db_url()
    logger.info("Creating synchronous engine for seeding...")
    sync_engine = create_engine(db_url)

    # 3. Verify tables exist
    try:
        with sync_engine.connect() as conn:
            res = conn.execute(
                text(
                    "SELECT table_name "
                    "FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
            tables = [r[0] for r in res.fetchall()]
            logger.info(f"Existing tables: {tables}")

            if "tenants" not in tables:
                logger.error(
                    "Required table 'tenants' missing. "
                    "Migrations might have failed."
                )
                sys.exit(1)
    except Exception as e:
        logger.error(f"Table verification failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 4. Execute the seed scripts in deterministic order
    seeds_to_run = [
        "clients.sql",
        "users.sql",
        "sample_tickets.sql",
    ]

    for seed_file in seeds_to_run:
        try:
            execute_sql_file(sync_engine, seed_file)
        except Exception as e:
            logger.error(
                f"Seeding failed on {seed_file}: {str(e)}"
            )

    sync_engine.dispose()
    logger.info("Local database seed process complete!")


if __name__ == "__main__":
    try:
        seed_database()
    except Exception as e:
        logger.critical(
            f"Unhandled exception in seed_db: {str(e)}"
        )
        import traceback
        traceback.print_exc()
        sys.exit(1)
