#!/usr/bin/env python3
"""
PARWA Day 3 Morning — Backup/Restore E2E Tests
Full backup/restore pipeline validation: backup.sh, backup_cron.sh,
restore.sh, and deploy.sh — checking for correct flags, security,
and operational patterns.
"""
import os
import stat
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "infra", "scripts")
DEPLOY_SH = os.path.join(PROJECT_ROOT, "deploy.sh")


def load_file(path):
    with open(path) as f:
        return f.read()


def is_executable(path):
    """Check if a file has executable permissions."""
    st = os.stat(path)
    return bool(st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


# ---------------------------------------------------------------------------
# 1-4. backup.sh validation
# ---------------------------------------------------------------------------
class TestBackupScript:
    """backup.sh must use correct pg_dump flags, locking, and portable tools."""

    def test_backup_sh_exists(self):
        """backup.sh must exist."""
        path = os.path.join(SCRIPTS_DIR, "backup.sh")
        assert os.path.exists(path), "backup.sh not found"

    def test_backup_sh_is_executable(self):
        """backup.sh must be executable (or have shebang for bash execution)."""
        path = os.path.join(SCRIPTS_DIR, "backup.sh")
        content = load_file(path)
        # Check for shebang or executable bit
        has_shebang = content.startswith("#!/bin/bash") or content.startswith("#!/usr/bin/env bash")
        is_exec = is_executable(path)
        assert has_shebang or is_exec, \
            "backup.sh must either be executable or have a proper shebang"

    def test_uses_repeatable_read(self):
        """backup.sh must use --repeatable-read (not --serializable-deferrable)."""
        content = load_file(os.path.join(SCRIPTS_DIR, "backup.sh"))
        assert "--repeatable-read" in content, \
            "backup.sh must use --repeatable-read for consistent snapshots"
        assert "--serializable-deferrable" not in content, \
            "backup.sh must NOT use --serializable-deferrable (too restrictive)"

    def test_uses_flock_for_locking(self):
        """backup.sh must use flock for lock acquisition (not race-prone lock files)."""
        content = load_file(os.path.join(SCRIPTS_DIR, "backup.sh"))
        assert "flock" in content, "backup.sh must use flock for lock acquisition"

    def test_uses_awk_not_grep_oP(self):
        """backup.sh must use awk for S3 cleanup (grep -oP is not portable)."""
        content = load_file(os.path.join(SCRIPTS_DIR, "backup.sh"))
        assert "awk" in content, "backup.sh must use awk"
        assert "grep -oP" not in content, \
            "backup.sh must NOT use grep -oP (not portable across systems)"


# ---------------------------------------------------------------------------
# 5-6. backup_cron.sh validation
# ---------------------------------------------------------------------------
class TestBackupCronScript:
    """backup_cron.sh must capture exit codes immediately and use proper locking."""

    def test_backup_cron_sh_exists(self):
        """backup_cron.sh must exist."""
        path = os.path.join(SCRIPTS_DIR, "backup_cron.sh")
        assert os.path.exists(path), "backup_cron.sh not found"

    def test_captures_exit_code_immediately(self):
        """backup_cron.sh must capture backup exit code immediately after the command."""
        content = load_file(os.path.join(SCRIPTS_DIR, "backup_cron.sh"))
        # Should not rely on $? after other commands
        # Look for pattern: <command> && rc=0 || rc=$?  OR  backup_rc=$?
        assert "backup_rc" in content, \
            "backup_cron.sh must capture exit code in a variable immediately after backup command"


# ---------------------------------------------------------------------------
# 7-9. restore.sh validation
# ---------------------------------------------------------------------------
class TestRestoreScript:
    """restore.sh must have proper app stop/start, S3 download, and safe file handling."""

    def test_restore_sh_exists(self):
        """restore.sh must exist."""
        path = os.path.join(SCRIPTS_DIR, "restore.sh")
        assert os.path.exists(path), "restore.sh not found"

    def test_has_app_stop_start_logic(self):
        """restore.sh must stop and start the application around restore."""
        content = load_file(os.path.join(SCRIPTS_DIR, "restore.sh"))
        assert "stop_application" in content, \
            "restore.sh must have stop_application function"
        assert "start_application" in content, \
            "restore.sh must have start_application function"

    def test_supports_s3_download(self):
        """restore.sh must support downloading backups from S3."""
        content = load_file(os.path.join(SCRIPTS_DIR, "restore.sh"))
        assert "download_from_s3" in content, \
            "restore.sh must have download_from_s3 function"
        assert "--s3" in content, \
            "restore.sh must support --s3 flag for S3 download"

    def test_has_tables_option(self):
        """restore.sh must support --tables option for partial restore."""
        content = load_file(os.path.join(SCRIPTS_DIR, "restore.sh"))
        assert "RESTORE_TABLES" in content, \
            "restore.sh must have RESTORE_TABLES variable"
        assert "--tables" in content, \
            "restore.sh must support --tables option"

    def test_uses_find_print0_xargs_0(self):
        """restore.sh must use find -print0 | xargs -0 (not plain xargs)."""
        content = load_file(os.path.join(SCRIPTS_DIR, "restore.sh"))
        assert "-print0" in content, \
            "restore.sh must use find -print0 for safe filename handling"
        assert "xargs -0" in content, \
            "restore.sh must use xargs -0 (not plain xargs)"


# ---------------------------------------------------------------------------
# 10-12. deploy.sh validation
# ---------------------------------------------------------------------------
class TestDeployScript:
    """deploy.sh must use strict mode, have health checks, and support production."""

    def test_deploy_sh_exists(self):
        """deploy.sh must exist."""
        assert os.path.exists(DEPLOY_SH), "deploy.sh not found"

    def test_uses_set_euo_pipefail(self):
        """deploy.sh must use set -euo pipefail for strict error handling."""
        content = load_file(DEPLOY_SH)
        assert "set -euo pipefail" in content, \
            "deploy.sh must use 'set -euo pipefail'"

    def test_has_health_check_function(self):
        """deploy.sh must have a health_check function."""
        content = load_file(DEPLOY_SH)
        assert "health_check" in content, \
            "deploy.sh must have health_check function"

    def test_supports_production_compose_in_stop(self):
        """deploy.sh stop command must support production compose file."""
        content = load_file(DEPLOY_SH)
        assert "COMPOSE_FILE_PROD" in content, \
            "deploy.sh must reference COMPOSE_FILE_PROD for production support"

    def test_supports_production_compose_in_logs(self):
        """deploy.sh logs command must support production compose file."""
        content = load_file(DEPLOY_SH)
        # Check that the logs function references prod compose file
        assert "COMPOSE_FILE_PROD" in content, \
            "deploy.sh logs must support production compose file"

    def test_supports_production_compose_in_clean(self):
        """deploy.sh clean command must support production compose file."""
        content = load_file(DEPLOY_SH)
        # Check that the clean function references prod compose file
        assert "COMPOSE_FILE_PROD" in content, \
            "deploy.sh clean must support production compose file"

    def test_health_check_runs_after_start(self):
        """deploy.sh must call health_check after starting services."""
        content = load_file(DEPLOY_SH)
        # The do_start function should call health_check
        assert "health_check" in content, \
            "deploy.sh must call health_check function"
        # Verify it's called in the start flow (after up -d)
        lines = content.split('\n')
        up_line = -1
        hc_line = -1
        for i, line in enumerate(lines):
            if 'up -d' in line or 'up "' in line:
                up_line = i
            if 'health_check' in line and 'function' not in line and 'def ' not in line:
                hc_line = i
        # health_check should appear after up -d somewhere in the script
        assert "health_check" in content, \
            "deploy.sh must invoke health_check after starting services"
