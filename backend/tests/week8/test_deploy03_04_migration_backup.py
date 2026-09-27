"""
Week 8 Tests: DEPLOY-03/04 — Migration and Backup Scripts

Validates:
- migrate_production.sh exists with proper structure
- verify_backup.sh exists with proper structure
- Scripts have correct shebang lines
- Key functions present
- Exit codes defined
"""

import os
import re
import pytest


SCRIPTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "scripts"
)
MIGRATE_SCRIPT = os.path.join(SCRIPTS_DIR, "migrate_production.sh")
VERIFY_SCRIPT = os.path.join(SCRIPTS_DIR, "verify_backup.sh")
BACKUP_DOCKERFILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "infra", "docker", "backup.Dockerfile"
)
BACKUP_ENTRYPOINT = os.path.join(SCRIPTS_DIR, "backup_entrypoint.sh")
RUN_BACKUP = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "infra", "docker", "run_backup.sh"
)
HEALTHCHECK = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "infra", "docker", "healthcheck.sh"
)


def _read(path):
    with open(path, "r") as f:
        return f.read()


class TestMigrationScript:
    """Validate production migration script."""

    def test_script_exists(self):
        """migrate_production.sh must exist."""
        assert os.path.exists(MIGRATE_SCRIPT), "migrate_production.sh not found"

    def test_shebang(self):
        """Must have bash shebang."""
        content = _read(MIGRATE_SCRIPT)
        assert content.startswith("#!/usr/bin/env bash") or content.startswith("#!/bin/bash")

    def test_set_euo_pipefail(self):
        """Must use set -euo pipefail for safety."""
        content = _read(MIGRATE_SCRIPT)
        assert "set -euo pipefail" in content, "Missing set -euo pipefail"

    def test_has_check_prerequisites(self):
        """Must have check_prerequisites function."""
        content = _read(MIGRATE_SCRIPT)
        assert "check_prerequisites" in content, "Missing check_prerequisites function"

    def test_has_backup_database(self):
        """Must have backup_database function."""
        content = _read(MIGRATE_SCRIPT)
        assert "backup_database" in content, "Missing backup_database function"

    def test_has_run_migration(self):
        """Must have run_migration function."""
        content = _read(MIGRATE_SCRIPT)
        assert "run_migration" in content or "alembic upgrade head" in content

    def test_has_verify_migration(self):
        """Must have verify_migration function."""
        content = _read(MIGRATE_SCRIPT)
        assert "verify_migration" in content, "Missing verify_migration function"

    def test_has_rollback(self):
        """Must have rollback function."""
        content = _read(MIGRATE_SCRIPT)
        assert "rollback" in content, "Missing rollback function"

    def test_has_dry_run_flag(self):
        """Must support --dry-run flag."""
        content = _read(MIGRATE_SCRIPT)
        assert "--dry-run" in content or "DRY_RUN" in content

    def test_references_alembic(self):
        """Must reference alembic for migrations."""
        content = _read(MIGRATE_SCRIPT)
        assert "alembic" in content, "Must use alembic for migrations"

    def test_exit_codes_defined(self):
        """Must define meaningful exit codes (0, 1, 2, 3)."""
        content = _read(MIGRATE_SCRIPT)
        assert re.search(r"exit\s+0", content), "Missing exit 0"
        assert re.search(r"exit\s+[123]", content), "Missing error exit codes"

    def test_database_url_check(self):
        """Must check DATABASE_URL environment variable."""
        content = _read(MIGRATE_SCRIPT)
        assert "DATABASE_URL" in content, "Must check DATABASE_URL"


class TestBackupVerificationScript:
    """Validate backup verification script."""

    def test_script_exists(self):
        """verify_backup.sh must exist."""
        assert os.path.exists(VERIFY_SCRIPT), "verify_backup.sh not found"

    def test_shebang(self):
        """Must have bash shebang."""
        content = _read(VERIFY_SCRIPT)
        assert content.startswith("#!/usr/bin/env bash") or content.startswith("#!/bin/bash")

    def test_set_euo_pipefail(self):
        """Must use set -euo pipefail."""
        content = _read(VERIFY_SCRIPT)
        assert "set -euo pipefail" in content

    def test_checks_file_existence(self):
        """Must check backup file exists."""
        content = _read(VERIFY_SCRIPT)
        assert any(kw in content for kw in ["-f ", "test -f", "file_exists"]), \
            "Must check file existence"

    def test_restores_to_temp_db(self):
        """Must restore to temporary database for verification."""
        content = _read(VERIFY_SCRIPT)
        assert any(kw in content for kw in ["pg_restore", "restore", "temp"]), \
            "Must restore backup for verification"

    def test_verifies_critical_tables(self):
        """Must verify critical tables exist (users, companies, tickets)."""
        content = _read(VERIFY_SCRIPT)
        critical = ["users", "companies", "tickets"]
        found = sum(1 for t in critical if t in content.lower())
        assert found >= 2, "Must verify critical tables"

    def test_has_cleanup(self):
        """Must cleanup temporary database after verification."""
        content = _read(VERIFY_SCRIPT)
        assert any(kw in content for kw in ["cleanup", "DROP", "rm -rf", "clean"]), \
            "Must cleanup temp resources"

    def test_exit_codes(self):
        """Must have meaningful exit codes."""
        content = _read(VERIFY_SCRIPT)
        assert re.search(r"exit\s+0", content), "Missing success exit code"


class TestBackupDockerSetup:
    """Validate backup Docker container setup."""

    def test_dockerfile_exists(self):
        """backup.Dockerfile must exist."""
        assert os.path.exists(BACKUP_DOCKERFILE)

    def test_dockerfile_uses_alpine(self):
        """Must use Alpine base image."""
        content = _read(BACKUP_DOCKERFILE)
        assert "alpine" in content.lower(), "Must use Alpine for minimal size"

    def test_dockerfile_installs_postgresql_client(self):
        """Must install PostgreSQL client for pg_dump."""
        content = _read(BACKUP_DOCKERFILE)
        assert "postgresql" in content.lower() or "pg_dump" in content.lower()

    def test_entrypoint_exists(self):
        """backup_entrypoint.sh must exist."""
        assert os.path.exists(BACKUP_ENTRYPOINT)

    def test_run_backup_exists(self):
        """run_backup.sh must exist for cron execution."""
        assert os.path.exists(RUN_BACKUP)

    def test_healthcheck_exists(self):
        """healthcheck.sh must exist for Docker HEALTHCHECK."""
        assert os.path.exists(HEALTHCHECK)

    def test_run_backup_uses_pg_dump(self):
        """run_backup.sh must use pg_dump."""
        content = _read(RUN_BACKUP)
        assert "pg_dump" in content, "Must use pg_dump"

    def test_run_backup_has_gzip(self):
        """run_backup.sh must gzip backups."""
        content = _read(RUN_BACKUP)
        assert "gzip" in content, "Must gzip backups"

    def test_healthcheck_verifies_age(self):
        """healthcheck.sh must verify backup age."""
        content = _read(HEALTHCHECK)
        # Should check that latest backup is not too old
        assert any(kw in content for kw in ["age", "hour", "time", "mtime"]), \
            "Must verify backup freshness"

    def test_entrypoint_sets_up_cron(self):
        """backup_entrypoint.sh must set up cron."""
        content = _read(BACKUP_ENTRYPOINT)
        assert "cron" in content.lower() or "crond" in content.lower()


class TestAlembicSetup:
    """Validate Alembic migration setup."""

    def test_alembic_ini_exists(self):
        """alembic.ini must exist."""
        alembic_ini = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "database", "alembic.ini"
        )
        assert os.path.exists(alembic_ini), "alembic.ini not found"

    def test_alembic_env_exists(self):
        """alembic/env.py must exist."""
        env_py = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "database", "alembic", "env.py"
        )
        assert os.path.exists(env_py), "alembic/env.py not found"

    def test_env_uses_database_url(self):
        """alembic/env.py must read DATABASE_URL from environment."""
        env_py = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "database", "alembic", "env.py"
        )
        content = _read(env_py)
        assert "DATABASE_URL" in content, "Must read DATABASE_URL from env"

    def test_migration_versions_exist(self):
        """Migration versions directory must exist and have files."""
        versions_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "database", "alembic", "versions"
        )
        assert os.path.isdir(versions_dir), "versions/ directory missing"
        versions = [f for f in os.listdir(versions_dir) if f.endswith(".py")]
        assert len(versions) >= 10, f"Expected >= 10 migrations, found {len(versions)}"

    def test_migrations_import_all_models(self):
        """env.py must import all model modules for autogenerate."""
        env_py = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "database", "alembic", "env.py"
        )
        content = _read(env_py)
        assert "import database.models" in content, "Must import database models"
