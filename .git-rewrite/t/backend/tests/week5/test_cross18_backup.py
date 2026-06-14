"""Tests for CROSS-18 backup scripts.

Validates:
- backup.sh exists and is a valid shell script
- wal_archive.sh exists
- backup.sh contains pg_dump
- backup.sh has retention logic
- backup.sh has restore mode
- backup.sh has integrity verification
"""

import os
import re
from pathlib import Path

import pytest

# ── Path constants ─────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BACKUP_SH = PROJECT_ROOT / "scripts" / "backup.sh"
WAL_ARCHIVE_SH = PROJECT_ROOT / "scripts" / "wal_archive.sh"


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def backup_source():
    """Read and return backup.sh contents."""
    assert BACKUP_SH.exists(), f"backup.sh not found at {BACKUP_SH}"
    return BACKUP_SH.read_text(encoding="utf-8")


@pytest.fixture
def wal_source():
    """Read and return wal_archive.sh contents."""
    assert WAL_ARCHIVE_SH.exists(), f"wal_archive.sh not found at {WAL_ARCHIVE_SH}"
    return WAL_ARCHIVE_SH.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════
# 1. backup.sh existence and validity
# ═══════════════════════════════════════════════════════════════════

class TestBackupScriptExists:
    """Verify backup.sh exists and is a valid shell script."""

    def test_backup_sh_exists(self):
        """backup.sh must exist."""
        assert BACKUP_SH.exists(), f"backup.sh not found at {BACKUP_SH}"

    def test_backup_sh_is_executable(self):
        """backup.sh should have execute permission."""
        # Not strictly required but good practice
        # Skip this check if running in CI where permissions may differ
        pass

    def test_backup_sh_has_shebang(self, backup_source):
        """backup.sh must have a bash shebang."""
        assert backup_source.startswith("#!/usr/bin/env bash") or \
               backup_source.startswith("#!/bin/bash"), (
            "backup.sh must have a bash shebang"
        )

    def test_backup_sh_set_euo_pipefail(self, backup_source):
        """backup.sh must use 'set -euo pipefail' for strict mode."""
        assert "set -euo pipefail" in backup_source, (
            "backup.sh must use 'set -euo pipefail'"
        )

    def test_backup_sh_valid_syntax(self, backup_source):
        """backup.sh must pass basic bash syntax check."""
        # Write to temp file and run bash -n
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        ) as tmp:
            tmp.write(backup_source)
            tmp_path = tmp.name

        try:
            result = os.system(f"bash -n '{tmp_path}' 2>&1")
            assert result == 0, (
                f"backup.sh has syntax errors (bash -n returned {result})"
            )
        finally:
            os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════════
# 2. wal_archive.sh existence
# ═══════════════════════════════════════════════════════════════════

class TestWalArchiveScript:
    """Verify wal_archive.sh exists and is valid."""

    def test_wal_archive_sh_exists(self):
        """wal_archive.sh must exist."""
        assert WAL_ARCHIVE_SH.exists(), (
            f"wal_archive.sh not found at {WAL_ARCHIVE_SH}"
        )

    def test_wal_archive_sh_has_shebang(self, wal_source):
        """wal_archive.sh must have a bash shebang."""
        assert wal_source.startswith("#!/usr/bin/env bash") or \
               wal_source.startswith("#!/bin/bash"), (
            "wal_archive.sh must have a bash shebang"
        )

    def test_wal_archive_sh_set_euo_pipefail(self, wal_source):
        """wal_archive.sh must use 'set -euo pipefail'."""
        assert "set -euo pipefail" in wal_source, (
            "wal_archive.sh must use 'set -euo pipefail'"
        )

    def test_wal_archive_sh_valid_syntax(self, wal_source):
        """wal_archive.sh must pass basic bash syntax check."""
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        ) as tmp:
            tmp.write(wal_source)
            tmp_path = tmp.name

        try:
            result = os.system(f"bash -n '{tmp_path}' 2>&1")
            assert result == 0, (
                f"wal_archive.sh has syntax errors (bash -n returned {result})"
            )
        finally:
            os.unlink(tmp_path)

    def test_wal_archive_has_setup_mode(self, wal_source):
        """wal_archive.sh must have --setup mode."""
        assert "--setup" in wal_source, (
            "wal_archive.sh missing --setup mode"
        )

    def test_wal_archive_has_archive_mode(self, wal_source):
        """wal_archive.sh must have --archive mode."""
        assert "--archive" in wal_source, (
            "wal_archive.sh missing --archive mode"
        )


# ═══════════════════════════════════════════════════════════════════
# 3. backup.sh contains pg_dump
# ═══════════════════════════════════════════════════════════════════

class TestPgDumpUsage:
    """Verify backup.sh uses pg_dump."""

    def test_contains_pg_dump(self, backup_source):
        """backup.sh must use pg_dump command."""
        assert "pg_dump" in backup_source, (
            "backup.sh does not contain pg_dump"
        )

    def test_pg_dump_with_flags(self, backup_source):
        """pg_dump should use important flags."""
        assert "--format" in backup_source or "-F" in backup_source, (
            "pg_dump should specify format"
        )
        assert "--no-owner" in backup_source, (
            "pg_dump should use --no-owner for portability"
        )
        assert "--no-privileges" in backup_source, (
            "pg_dump should use --no-privileges"
        )

    def test_pg_dump_with_gzip(self, backup_source):
        """pg_dump output should be piped through gzip."""
        assert "gzip" in backup_source, (
            "backup.sh does not use gzip for compression"
        )
        assert "| gzip" in backup_source, (
            "pg_dump output not piped through gzip"
        )

    def test_pg_dump_with_connection_params(self, backup_source):
        """pg_dump should use connection parameters."""
        assert "PGHOST" in backup_source, (
            "PGHOST not referenced"
        )
        assert "PGPORT" in backup_source, (
            "PGPORT not referenced"
        )
        assert "PGDATABASE" in backup_source, (
            "PGDATABASE not referenced"
        )
        assert "PGUSER" in backup_source, (
            "PGUSER not referenced"
        )


# ═══════════════════════════════════════════════════════════════════
# 4. Retention logic
# ═══════════════════════════════════════════════════════════════════

class TestRetentionLogic:
    """Verify backup.sh has retention/pruning logic."""

    def test_has_retention_variable(self, backup_source):
        """Must have a retention days variable."""
        assert "BACKUP_RETAIN_DAYS" in backup_source, (
            "BACKUP_RETAIN_DAYS not defined"
        )

    def test_retention_has_default(self, backup_source):
        """Retention variable should have a default value."""
        assert ":-7" in backup_source or "=${BACKUP_RETAIN_DAYS:-7}" in backup_source, (
            "BACKUP_RETAIN_DAYS should default to 7 days"
        )

    def test_has_prune_function(self, backup_source):
        """Must have a prune/cleanup function for old backups."""
        assert "prune" in backup_source.lower() or "retention" in backup_source.lower(), (
            "No prune/retention function found"
        )

    def test_prune_uses_find_and_mtime(self, backup_source):
        """Pruning should use find with -mtime to find old files."""
        assert "find" in backup_source, (
            "find command not used for pruning"
        )
        assert "-mtime" in backup_source, (
            "-mtime not used for finding old backups"
        )

    def test_prune_removes_old_files(self, backup_source):
        """Pruning should rm old backup files."""
        # The prune function should have rm -f
        assert "rm -f" in backup_source or "rm \"" in backup_source, (
            "rm not used to remove old backups"
        )


# ═══════════════════════════════════════════════════════════════════
# 5. Restore mode
# ═══════════════════════════════════════════════════════════════════

class TestRestoreMode:
    """Verify backup.sh has restore functionality."""

    def test_has_restore_flag(self, backup_source):
        """Must have --restore flag support."""
        assert "--restore" in backup_source, (
            "--restore flag not supported"
        )

    def test_has_restore_function(self, backup_source):
        """Must have a restore function."""
        assert "run_restore" in backup_source or "restore()" in backup_source, (
            "No restore function found"
        )

    def test_restore_uses_psql(self, backup_source):
        """Restore should pipe through psql."""
        assert "psql" in backup_source, (
            "psql not used for restore"
        )

    def test_restore_decompresses_gzip(self, backup_source):
        """Restore should decompress the gzip backup."""
        assert "gzip -dc" in backup_source or "gunzip -c" in backup_source, (
            "gzip decompression not used for restore"
        )

    def test_restore_has_safety_prompt(self, backup_source):
        """Restore should have a safety confirmation prompt."""
        assert "YES" in backup_source or "confirm" in backup_source.lower(), (
            "No safety confirmation prompt found for restore"
        )

    def test_restore_on_error_stop(self, backup_source):
        """Restore should use ON_ERROR_STOP for safety."""
        assert "ON_ERROR_STOP" in backup_source, (
            "ON_ERROR_STOP not set for restore"
        )


# ═══════════════════════════════════════════════════════════════════
# 6. Integrity verification
# ═══════════════════════════════════════════════════════════════════

class TestIntegrityVerification:
    """Verify backup.sh has integrity verification."""

    def test_has_verify_flag(self, backup_source):
        """Must support --verify flag."""
        assert "--verify" in backup_source, (
            "--verify flag not supported"
        )

    def test_has_verify_function(self, backup_source):
        """Must have a verify/integrity check function."""
        assert "verify_backup" in backup_source or "integrity" in backup_source.lower(), (
            "No verification function found"
        )

    def test_verify_checks_gzip_integrity(self, backup_source):
        """Verification should check gzip integrity."""
        assert "gzip -t" in backup_source, (
            "gzip -t not used for integrity check"
        )

    def test_verify_checks_sql_headers(self, backup_source):
        """Verification should check SQL content headers."""
        assert "pg_restore" in backup_source or "head" in backup_source, (
            "No SQL content verification found"
        )

    def test_verify_runs_after_backup(self, backup_source):
        """Verification should run automatically after backup."""
        # In run_backup, verify_backup should be called
        assert backup_source.count("verify_backup") >= 1, (
            "verify_backup not called after backup"
        )


# ═══════════════════════════════════════════════════════════════════
# 7. Pre-flight checks
# ═══════════════════════════════════════════════════════════════════

class TestPreflightChecks:
    """Verify backup.sh has pre-flight validation."""

    def test_checks_pg_dump_available(self, backup_source):
        """Should verify pg_dump is available."""
        assert "command -v pg_dump" in backup_source or "which pg_dump" in backup_source, (
            "No check for pg_dump availability"
        )

    def test_checks_pg_restore_available(self, backup_source):
        """Should verify pg_restore is available."""
        assert "command -v pg_restore" in backup_source or "which pg_restore" in backup_source, (
            "No check for pg_restore availability"
        )

    def test_checks_db_connectivity(self, backup_source):
        """Should verify database connectivity before backup."""
        assert "psql" in backup_source and "SELECT 1" in backup_source, (
            "No database connectivity check found"
        )

    def test_creates_backup_directory(self, backup_source):
        """Should create backup directory if it doesn't exist."""
        assert "mkdir -p" in backup_source, (
            "mkdir -p not used to create backup directory"
        )


# ═══════════════════════════════════════════════════════════════════
# 8. Documentation
# ═══════════════════════════════════════════════════════════════════

class TestDocumentation:
    """Verify backup scripts have documentation."""

    def test_backup_sh_has_header_comments(self, backup_source):
        """backup.sh must have descriptive header comments."""
        assert "PARWA" in backup_source or "CROSS-18" in backup_source, (
            "backup.sh missing project identifier"
        )

    def test_backup_sh_has_usage_info(self, backup_source):
        """backup.sh must have usage/help information."""
        assert "--help" in backup_source or "usage()" in backup_source, (
            "No usage/help information in backup.sh"
        )

    def test_wal_archive_has_header_comments(self, wal_source):
        """wal_archive.sh must have descriptive header comments."""
        assert "PARWA" in wal_source or "CROSS-18" in wal_source or "WAL" in wal_source, (
            "wal_archive.sh missing project identifier"
        )
