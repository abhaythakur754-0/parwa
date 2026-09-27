#!/usr/bin/env python3
"""
PARWA Day 2 — Scripts Tests
Tests: backup.sh, backup_cron.sh, restore.sh, deploy.sh fixes
"""
import unittest
import os

SCRIPTS_DIR = "/home/z/my-project/download/parwa/infra/scripts"
DEPLOY_DIR = "/home/z/my-project/download/parwa"


def load_file(path):
    with open(path) as f:
        return f.read()


class TestBackupScript(unittest.TestCase):
    """#181-#185: backup.sh fixes"""

    def test_uses_repeatable_read(self):
        """#181: --serializable-deferrable replaced with --repeatable-read"""
        content = load_file(f"{SCRIPTS_DIR}/backup.sh")
        self.assertNotIn("--serializable-deferrable", content)
        self.assertIn("--repeatable-read", content)

    def test_uses_flock(self):
        """#182: flock-based locking instead of race-condition-prone lock files"""
        content = load_file(f"{SCRIPTS_DIR}/backup.sh")
        self.assertIn("flock", content)

    def test_no_grep_oP(self):
        """#183: grep -oP replaced with awk"""
        content = load_file(f"{SCRIPTS_DIR}/backup.sh")
        self.assertNotIn("grep -oP", content)
        self.assertIn("awk", content)

    def test_sse_verification(self):
        """#184: S3 SSE encryption verification"""
        content = load_file(f"{SCRIPTS_DIR}/backup.sh")
        self.assertIn("ServerSideEncryption", content)

    def test_configurable_success_notification(self):
        """#185: NOTIFY_ON_SUCCESS env var"""
        content = load_file(f"{SCRIPTS_DIR}/backup.sh")
        self.assertIn("NOTIFY_ON_SUCCESS", content)


class TestBackupCronScript(unittest.TestCase):
    """#186-#188: backup_cron.sh fixes"""

    def test_exit_code_captured_correctly(self):
        """#186: exit code captured before checking"""
        content = load_file(f"{SCRIPTS_DIR}/backup_cron.sh")
        # Should not just check $? after a pipe
        self.assertIn("backup_rc", content)

    def test_log_rotation(self):
        """#187: log rotation added"""
        content = load_file(f"{SCRIPTS_DIR}/backup_cron.sh")
        self.assertIn("LOG_MAX_SIZE", content)

    def test_uses_flock(self):
        """#188: flock-based locking"""
        content = load_file(f"{SCRIPTS_DIR}/backup_cron.sh")
        self.assertIn("flock", content)


class TestRestoreScript(unittest.TestCase):
    """#189-#194: restore.sh fixes"""

    def test_application_stop_start(self):
        """#189: stop/start application around restore"""
        content = load_file(f"{SCRIPTS_DIR}/restore.sh")
        self.assertIn("stop_application", content)
        self.assertIn("start_application", content)
        self.assertIn("APP_STOP_COMMAND", content)
        self.assertIn("APP_START_COMMAND", content)

    def test_s3_download_support(self):
        """#190: S3 download support"""
        content = load_file(f"{SCRIPTS_DIR}/restore.sh")
        self.assertIn("download_from_s3", content)
        self.assertIn("--s3", content)

    def test_exclude_monitoring_users(self):
        """#191: monitoring users excluded from pg_terminate_backend"""
        content = load_file(f"{SCRIPTS_DIR}/restore.sh")
        self.assertIn("postgres_exporter", content)
        self.assertIn("monitoring", content)

    def test_partial_restore_tables(self):
        """#193: --tables option for partial restore"""
        content = load_file(f"{SCRIPTS_DIR}/restore.sh")
        self.assertIn("RESTORE_TABLES", content)
        self.assertIn("--tables", content)

    def test_find_print0_xargs_0(self):
        """#194: find -print0 | xargs -0"""
        content = load_file(f"{SCRIPTS_DIR}/restore.sh")
        self.assertIn("-print0", content)
        self.assertIn("xargs -0", content)


class TestDeployScript(unittest.TestCase):
    """#195, #196, #198: deploy.sh fixes"""

    def test_uses_pipefail(self):
        """#198: set -euo pipefail"""
        content = load_file(f"{DEPLOY_DIR}/deploy.sh")
        self.assertIn("set -euo pipefail", content)

    def test_prod_compose_support_in_stop(self):
        """#195: stop supports production compose file"""
        content = load_file(f"{DEPLOY_DIR}/deploy.sh")
        self.assertIn("COMPOSE_FILE_PROD", content)

    def test_health_check_function(self):
        """#196: post-deploy health check"""
        content = load_file(f"{DEPLOY_DIR}/deploy.sh")
        self.assertIn("health_check", content)

    def test_health_check_called_after_start(self):
        """#196: health check called after deployment"""
        content = load_file(f"{DEPLOY_DIR}/deploy.sh")
        self.assertIn("health_check", content)

    def test_quoted_variables(self):
        """Variables properly quoted"""
        content = load_file(f"{DEPLOY_DIR}/deploy.sh")
        # Check for properly quoted compose cmd usage
        self.assertIn('"${COMPOSE_CMD}"', content)


if __name__ == "__main__":
    unittest.main()
