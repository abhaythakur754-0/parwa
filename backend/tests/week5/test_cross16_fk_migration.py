"""Tests for CROSS-16 FK mismatch migration (021_fix_session_ticket_fk).

Validates:
- Migration file exists and is valid Python
- References correct 14 tables
- down_revision chains to 020
- ORPHAN_SESSION_FKS has exactly 14 entries
- Each table name matches actual tables from source migrations
- upgrade() uses batch_alter_table
- downgrade() re-creates FK constraints
"""

import ast
import os
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Path constants ─────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "database" / "alembic" / "versions"
MIGRATION_021_PATH = MIGRATIONS_DIR / "021_fix_session_ticket_fk.py"
MIGRATION_020_PATH = MIGRATIONS_DIR / "020_jarvis_cc_tables.py"

# Source migrations that created the tables with orphan FKs
SOURCE_MIGRATIONS = {
    "003_ai_pipeline_tables": MIGRATIONS_DIR / "003_ai_pipeline_tables.py",
    "004_integration_tables": MIGRATIONS_DIR / "004_integration_tables.py",
    "006_analytics_onboarding": MIGRATIONS_DIR / "006_analytics_onboarding_tables.py",
    "007_remaining_gap_tables": MIGRATIONS_DIR / "007_remaining_gap_tables.py",
}

# Expected tables per source migration
EXPECTED_TABLES_BY_MIGRATION = {
    "003_ai_pipeline_tables": [
        "gsd_sessions",
        "confidence_scores",
        "guardrail_blocks",
        "model_usage_logs",
    ],
    "004_integration_tables": [
        "event_buffer",
    ],
    "006_analytics_onboarding": [
        "qa_scores",
        "agent_mistakes",
    ],
    "007_remaining_gap_tables": [
        "approval_queues",
        "executed_actions",
        "classification_log",
        "guardrails_audit_log",
        "guardrails_blocked_queue",
        "ai_response_feedback",
        "human_corrections",
    ],
}

ALL_EXPECTED_TABLES = sorted(
    t for tables in EXPECTED_TABLES_BY_MIGRATION.values() for t in tables
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def migration_021_source():
    """Read and return the source of migration 021."""
    assert MIGRATION_021_PATH.exists(), (
        f"Migration file not found: {MIGRATION_021_PATH}"
    )
    return MIGRATION_021_PATH.read_text(encoding="utf-8")


@pytest.fixture
def migration_021_module(migration_021_source):
    """Compile migration 021 and return its module namespace."""
    # Mock alembic.op before importing
    mock_op = MagicMock()
    with patch.dict("sys.modules", {"alembic": MagicMock(op=mock_op)}):
        ns = {}
        exec(compile(migration_021_source, str(MIGRATION_021_PATH), "exec"), ns)
    return ns


@pytest.fixture
def orphan_fks(migration_021_module):
    """Return the ORPHAN_SESSION_FKS list from migration 021."""
    return migration_021_module["ORPHAN_SESSION_FKS"]


# ═══════════════════════════════════════════════════════════════════
# 1. File existence and valid Python
# ═══════════════════════════════════════════════════════════════════

class TestMigration021File:
    """Verify migration 021 file exists and is valid Python."""

    def test_file_exists(self):
        """Migration 021 file must exist on disk."""
        assert MIGRATION_021_PATH.exists(), (
            f"Migration 021 not found at {MIGRATION_021_PATH}"
        )

    def test_file_is_valid_python(self, migration_021_source):
        """Migration 021 must compile as valid Python."""
        try:
            ast.parse(migration_021_source)
        except SyntaxError as e:
            pytest.fail(f"Migration 021 has syntax error: {e}")

    def test_migration_020_exists(self):
        """Migration 020 must exist (prerequisite)."""
        assert MIGRATION_020_PATH.exists(), (
            f"Migration 020 not found at {MIGRATION_020_PATH}"
        )


# ═══════════════════════════════════════════════════════════════════
# 2. Revision chain
# ═══════════════════════════════════════════════════════════════════

class TestRevisionChain:
    """Verify revision metadata and chain integrity."""

    def test_revision_id(self, migration_021_module):
        """Revision ID must be '021_fix_session_ticket_fk'."""
        assert migration_021_module["revision"] == "021_fix_session_ticket_fk"

    def test_down_revision_chains_to_020(self, migration_021_module):
        """down_revision must reference '020_jarvis_cc_tables'."""
        assert migration_021_module["down_revision"] == "020_jarvis_cc_tables"

    def test_branch_labels_none(self, migration_021_module):
        """branch_labels must be None (linear history)."""
        assert migration_021_module["branch_labels"] is None

    def test_depends_on_none(self, migration_021_module):
        """depends_on must be None."""
        assert migration_021_module["depends_on"] is None


# ═══════════════════════════════════════════════════════════════════
# 3. ORPHAN_SESSION_FKS constant
# ═══════════════════════════════════════════════════════════════════

class TestOrphanSessionFKs:
    """Verify the ORPHAN_SESSION_FKS constant."""

    def test_has_exactly_14_entries(self, orphan_fks):
        """ORPHAN_SESSION_FKS must have exactly 14 entries."""
        assert len(orphan_fks) == 14, (
            f"Expected 14 orphan FKs, got {len(orphan_fks)}"
        )

    def test_each_entry_is_tuple_of_two_strings(self, orphan_fks):
        """Each entry must be a (table_name, fk_name) tuple of strings."""
        for entry in orphan_fks:
            assert isinstance(entry, tuple), f"Entry {entry} is not a tuple"
            assert len(entry) == 2, f"Entry {entry} does not have 2 elements"
            table_name, fk_name = entry
            assert isinstance(table_name, str), (
                f"Table name {table_name!r} is not a string"
            )
            assert isinstance(fk_name, str), (
                f"FK name {fk_name!r} is not a string"
            )

    def test_fk_naming_convention(self, orphan_fks):
        """FK names must follow convention: {table_name}_session_id_fkey."""
        for table_name, fk_name in orphan_fks:
            expected_fk = f"{table_name}_session_id_fkey"
            assert fk_name == expected_fk, (
                f"FK naming mismatch for {table_name}: "
                f"expected {expected_fk!r}, got {fk_name!r}"
            )

    def test_all_expected_tables_present(self, orphan_fks):
        """All 14 expected tables must be listed."""
        actual_tables = [entry[0] for entry in orphan_fks]
        for table in ALL_EXPECTED_TABLES:
            assert table in actual_tables, (
                f"Expected table {table!r} not found in ORPHAN_SESSION_FKS"
            )

    def test_no_extra_tables(self, orphan_fks):
        """No extra tables beyond the 14 expected."""
        actual_tables = set(entry[0] for entry in orphan_fks)
        expected_tables = set(ALL_EXPECTED_TABLES)
        extra = actual_tables - expected_tables
        assert not extra, f"Unexpected tables in ORPHAN_SESSION_FKS: {extra}"

    def test_tables_match_source_migrations(self, migration_021_source, orphan_fks):
        """Each table name must exist in its claimed source migration."""
        for mig_name, mig_path in SOURCE_MIGRATIONS.items():
            assert mig_path.exists(), f"Source migration {mig_path} not found"
            mig_source = mig_path.read_text(encoding="utf-8")
            for table_name in EXPECTED_TABLES_BY_MIGRATION[mig_name]:
                assert f"'{table_name}'" in mig_source or (
                    f'"{table_name}"' in mig_source
                ), (
                    f"Table {table_name!r} not found in migration {mig_name}"
                )


# ═══════════════════════════════════════════════════════════════════
# 4. upgrade() function
# ═══════════════════════════════════════════════════════════════════

class TestUpgradeFunction:
    """Verify upgrade() drops orphan FK constraints."""

    def test_upgrade_exists(self, migration_021_module):
        """upgrade() function must be defined."""
        assert "upgrade" in migration_021_module, "upgrade() not defined"

    def test_upgrade_uses_get_bind(self, migration_021_source):
        """upgrade() must call op.get_bind()."""
        assert "op.get_bind()" in migration_021_source, (
            "upgrade() does not call op.get_bind()"
        )

    def test_upgrade_calls_drop_orphan_fks(self, migration_021_source):
        """upgrade() must call _drop_orphan_fks helper."""
        assert "_drop_orphan_fks" in migration_021_source, (
            "upgrade() does not reference _drop_orphan_fks"
        )

    def test_drop_helper_uses_batch_alter_table(self, migration_021_source):
        """_drop_orphan_fks must use op.batch_alter_table."""
        assert "batch_alter_table" in migration_021_source, (
            "_drop_orphan_fks does not use batch_alter_table"
        )
        assert "drop_constraint" in migration_021_source, (
            "_drop_orphan_fks does not call drop_constraint"
        )

    def test_drop_constraint_type_is_foreignkey(self, migration_021_source):
        """drop_constraint must specify type_='foreignkey'."""
        assert 'type_="foreignkey"' in migration_021_source, (
            "drop_constraint does not specify type_='foreignkey'"
        )


# ═══════════════════════════════════════════════════════════════════
# 5. downgrade() function
# ═══════════════════════════════════════════════════════════════════

class TestDowngradeFunction:
    """Verify downgrade() re-creates FK constraints."""

    def test_downgrade_exists(self, migration_021_module):
        """downgrade() function must be defined."""
        assert "downgrade" in migration_021_module, "downgrade() not defined"

    def test_downgrade_creates_fks(self, migration_021_source):
        """downgrade() must call _create_session_fks helper."""
        assert "_create_session_fks" in migration_021_source, (
            "downgrade() does not reference _create_session_fks"
        )

    def test_create_fks_uses_batch_alter_table(self, migration_021_source):
        """_create_session_fks must use op.batch_alter_table."""
        # The source should have batch_alter_table in the create function
        assert migration_021_source.count("batch_alter_table") >= 2, (
            "batch_alter_table not used in both _drop and _create helpers"
        )

    def test_create_fks_references_sessions_table(self, migration_021_source):
        """_create_session_fks must reference the 'sessions' table."""
        assert '_SESSIONS_TABLE = "sessions"' in migration_021_source, (
            "_SESSIONS_TABLE constant not defined or wrong value"
        )
        assert "create_foreign_key" in migration_021_source, (
            "create_foreign_key not called in _create_session_fks"
        )


# ═══════════════════════════════════════════════════════════════════
# 6. Source code documentation
# ═══════════════════════════════════════════════════════════════════

class TestDocumentation:
    """Verify migration has proper documentation."""

    def test_has_docstring(self, migration_021_source):
        """Migration must have a module-level docstring."""
        tree = ast.parse(migration_021_source)
        assert tree.body and isinstance(tree.body[0], ast.Expr), (
            "No module-level docstring found"
        )
        assert isinstance(tree.body[0].value, ast.Constant), (
            "First statement is not a docstring"
        )

    def test_docstring_mentions_sessions(self, migration_021_source):
        """Docstring must mention the sessions table issue."""
        tree = ast.parse(migration_021_source)
        doc = ast.get_docstring(tree)
        assert doc is not None, "No docstring"
        assert "sessions" in doc.lower(), (
            "Docstring doesn't mention 'sessions'"
        )

    def test_docstring_mentions_migration_numbers(self, migration_021_source):
        """Docstring should mention affected migration numbers."""
        tree = ast.parse(migration_021_source)
        doc = ast.get_docstring(tree)
        assert doc is not None
        # Should mention at least one source migration number
        assert "003" in doc or "004" in doc or "006" in doc or "007" in doc, (
            "Docstring doesn't mention source migration numbers"
        )
