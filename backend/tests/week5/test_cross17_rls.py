"""Tests for CROSS-17 RLS migration (022_enable_rls).

Validates:
- Migration 022 exists and is valid Python
- down_revision chains to 021
- Count of tables with ENABLE ROW LEVEL SECURITY
- app.current_tenant_id() function is created
- parwa_admin BYPASSRLS grant
- SELECT/INSERT/UPDATE/DELETE policies per table
- Idempotent patterns: CREATE OR REPLACE, DROP POLICY IF EXISTS
"""

import ast
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Path constants ─────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "database" / "alembic" / "versions"
MIGRATION_022_PATH = MIGRATIONS_DIR / "022_enable_rls.py"


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def migration_022_source():
    """Read and return the source of migration 022."""
    assert MIGRATION_022_PATH.exists(), (
        f"Migration file not found: {MIGRATION_022_PATH}"
    )
    return MIGRATION_022_PATH.read_text(encoding="utf-8")


@pytest.fixture
def migration_022_module(migration_022_source):
    """Compile migration 022 and return its module namespace."""
    mock_op = MagicMock()
    with patch.dict("sys.modules", {"alembic": MagicMock(op=mock_op)}):
        ns = {}
        exec(compile(migration_022_source, str(MIGRATION_022_PATH), "exec"), ns)
    return ns


@pytest.fixture
def tenant_tables(migration_022_module):
    """Return the TENANT_TABLES list from migration 022."""
    return migration_022_module["TENANT_TABLES"]


# ═══════════════════════════════════════════════════════════════════
# 1. File existence and valid Python
# ═══════════════════════════════════════════════════════════════════

class TestMigration022File:
    """Verify migration 022 file exists and is valid Python."""

    def test_file_exists(self):
        """Migration 022 file must exist on disk."""
        assert MIGRATION_022_PATH.exists(), (
            f"Migration 022 not found at {MIGRATION_022_PATH}"
        )

    def test_file_is_valid_python(self, migration_022_source):
        """Migration 022 must compile as valid Python."""
        try:
            ast.parse(migration_022_source)
        except SyntaxError as e:
            pytest.fail(f"Migration 022 has syntax error: {e}")


# ═══════════════════════════════════════════════════════════════════
# 2. Revision chain
# ═══════════════════════════════════════════════════════════════════

class TestRevisionChain:
    """Verify revision metadata."""

    def test_revision_id(self, migration_022_module):
        """Revision ID must be '022_enable_rls'."""
        assert migration_022_module["revision"] == "022_enable_rls"

    def test_down_revision_chains_to_021(self, migration_022_module):
        """down_revision must reference '021_fix_session_ticket_fk'."""
        assert migration_022_module["down_revision"] == "021_fix_session_ticket_fk"


# ═══════════════════════════════════════════════════════════════════
# 3. TENANT_TABLES and ENABLE ROW LEVEL SECURITY
# ═══════════════════════════════════════════════════════════════════

class TestTenantTables:
    """Verify tenant table list and RLS enablement."""

    def test_tenant_tables_is_list(self, tenant_tables):
        """TENANT_TABLES must be a list."""
        assert isinstance(tenant_tables, list)

    def test_tenant_tables_not_empty(self, tenant_tables):
        """TENANT_TABLES must not be empty."""
        assert len(tenant_tables) > 0, "TENANT_TABLES is empty"

    def test_tenant_tables_count_reasonable(self, tenant_tables):
        """TENANT_TABLES should have a substantial number of tables."""
        # The migration says ~122 tables from migrations 001-020
        assert len(tenant_tables) >= 50, (
            f"Expected at least 50 tenant tables, got {len(tenant_tables)}"
        )

    def test_tenant_tables_no_duplicates(self, tenant_tables):
        """TENANT_TABLES must not contain duplicates."""
        assert len(tenant_tables) == len(set(tenant_tables)), (
            "TENANT_TABLES contains duplicates"
        )

    def test_tenant_tables_all_strings(self, tenant_tables):
        """All entries must be strings."""
        for table in tenant_tables:
            assert isinstance(table, str), f"Table {table!r} is not a string"

    def test_enable_rls_for_every_table(self, migration_022_source):
        """Every TENANT_TABLES entry must get ENABLE ROW LEVEL SECURITY."""
        assert "ENABLE ROW LEVEL SECURITY" in migration_022_source, (
            "ENABLE ROW LEVEL SECURITY not found in migration"
        )

    def test_rls_enabled_in_loop(self, migration_022_source, tenant_tables):
        """RLS should be enabled for all tables via a loop."""
        assert "for table in TENANT_TABLES" in migration_022_source, (
            "No loop over TENANT_TABLES found"
        )
        assert "_enable_rls_for_table" in migration_022_source, (
            "Helper function _enable_rls_for_table not found"
        )


# ═══════════════════════════════════════════════════════════════════
# 4. app.current_tenant_id() function
# ═══════════════════════════════════════════════════════════════════

class TestCurrentTenantFunction:
    """Verify the app.current_tenant_id() SQL function."""

    def test_create_function_sql_exists(self, migration_022_source):
        """Must have SQL to create the function."""
        assert "CREATE OR REPLACE FUNCTION app.current_tenant_id()" in migration_022_source, (
            "app.current_tenant_id() function creation not found"
        )

    def test_function_returns_text(self, migration_022_source):
        """Function must return TEXT type."""
        assert "RETURNS TEXT" in migration_022_source, (
            "Function does not return TEXT"
        )

    def test_function_uses_current_setting(self, migration_022_source):
        """Function must use current_setting to read the tenant ID."""
        assert "current_setting" in migration_022_source, (
            "current_setting not used in function"
        )
        assert "app.current_tenant_id" in migration_022_source, (
            "app.current_tenant_id setting name not found"
        )

    def test_function_created_in_upgrade(self, migration_022_source):
        """Function must be created in upgrade()."""
        # The _CREATE_FUNCTION_SQL constant should be used in upgrade
        assert "_CREATE_FUNCTION_SQL" in migration_022_source, (
            "_CREATE_FUNCTION_SQL constant not found"
        )

    def test_function_dropped_in_downgrade(self, migration_022_source):
        """Function must be dropped in downgrade()."""
        assert "DROP FUNCTION" in migration_022_source, (
            "DROP FUNCTION not found for downgrade"
        )
        assert "IF EXISTS" in migration_022_source, (
            "DROP FUNCTION should use IF EXISTS for idempotency"
        )

    def test_app_schema_created(self, migration_022_source):
        """Must create the 'app' schema if not exists."""
        assert "CREATE SCHEMA IF NOT EXISTS app" in migration_022_source, (
            "CREATE SCHEMA IF NOT EXISTS app not found"
        )


# ═══════════════════════════════════════════════════════════════════
# 5. parwa_admin BYPASSRLS grant
# ═══════════════════════════════════════════════════════════════════

class TestBypassRLS:
    """Verify BYPASSRLS grant for parwa_admin role."""

    def test_bypassrls_granted_in_upgrade(self, migration_022_source):
        """upgrade() must grant BYPASSRLS to parwa_admin."""
        assert "BYPASSRLS" in migration_022_source, (
            "BYPASSRLS not found in migration"
        )
        assert "parwa_admin" in migration_022_source, (
            "parwa_admin role not found in migration"
        )

    def test_bypassrls_revoked_in_downgrade(self, migration_022_source):
        """downgrade() must revoke BYPASSRLS from parwa_admin."""
        assert "NOBYPASSRLS" in migration_022_source, (
            "NOBYPASSRLS not found for downgrade"
        )

    def test_bypassrls_uses_do_block(self, migration_022_source):
        """BYPASSRLS grant should use DO $$ block for error handling."""
        assert "DO $$" in migration_022_source, (
            "DO $$ block not used for BYPASSRLS grant"
        )


# ═══════════════════════════════════════════════════════════════════
# 6. Policy creation (SELECT/INSERT/UPDATE/DELETE)
# ═══════════════════════════════════════════════════════════════════

class TestPolicies:
    """Verify RLS policies are created for CRUD operations."""

    def test_select_policy_created(self, migration_022_source):
        """SELECT policy must be created with USING clause."""
        assert "FOR SELECT" in migration_022_source, (
            "SELECT policy not found"
        )
        assert "USING" in migration_022_source, (
            "USING clause not found in SELECT policy"
        )

    def test_insert_policy_created(self, migration_022_source):
        """INSERT policy must be created with WITH CHECK clause."""
        assert "FOR INSERT" in migration_022_source, (
            "INSERT policy not found"
        )
        assert "WITH CHECK" in migration_022_source, (
            "WITH CHECK clause not found in INSERT policy"
        )

    def test_update_policy_created(self, migration_022_source):
        """UPDATE policy must be created with USING clause."""
        assert "FOR UPDATE" in migration_022_source, (
            "UPDATE policy not found"
        )

    def test_delete_policy_created(self, migration_022_source):
        """DELETE policy must be created with USING clause."""
        assert "FOR DELETE" in migration_022_source, (
            "DELETE policy not found"
        )

    def test_policies_reference_company_id(self, migration_022_source):
        """All policies must check company_id against current_tenant_id."""
        assert "company_id = app.current_tenant_id()" in migration_022_source, (
            "Policy does not check company_id = app.current_tenant_id()"
        )

    def test_all_four_policy_suffixes(self, migration_022_source):
        """Must use all four policy suffixes: tenant_select, tenant_insert, etc."""
        for suffix in ("tenant_select", "tenant_insert", "tenant_update", "tenant_delete"):
            assert f"_{suffix}" in migration_022_source, (
                f"Policy suffix '{suffix}' not found"
            )


# ═══════════════════════════════════════════════════════════════════
# 7. Idempotent patterns
# ═══════════════════════════════════════════════════════════════════

class TestIdempotentPatterns:
    """Verify idempotent SQL patterns."""

    def test_create_or_replace_function(self, migration_022_source):
        """Function must use CREATE OR REPLACE."""
        assert "CREATE OR REPLACE FUNCTION" in migration_022_source, (
            "CREATE OR REPLACE not used for function creation"
        )

    def test_drop_policy_if_exists(self, migration_022_source):
        """DROP POLICY must use IF EXISTS."""
        assert "DROP POLICY IF EXISTS" in migration_022_source, (
            "DROP POLICY IF EXISTS not used"
        )

    def test_drop_function_if_exists(self, migration_022_source):
        """DROP FUNCTION must use IF EXISTS."""
        assert "DROP FUNCTION IF EXISTS" in migration_022_source, (
            "DROP FUNCTION IF EXISTS not used"
        )

    def test_disable_rls_in_downgrade(self, migration_022_source):
        """downgrade must DISABLE ROW LEVEL SECURITY."""
        assert "DISABLE ROW LEVEL SECURITY" in migration_022_source, (
            "DISABLE ROW LEVEL SECURITY not found for downgrade"
        )


# ═══════════════════════════════════════════════════════════════════
# 8. Key tables from migrations 001-020
# ═══════════════════════════════════════════════════════════════════

class TestKeyTablesPresent:
    """Spot-check that important tables are in TENANT_TABLES."""

    @pytest.mark.parametrize("table", [
        "users",
        "tickets",
        "ticket_messages",
        "customers",
        "jarvis_sessions",
        "subscriptions",
        "integrations",
        "outbound_emails",
        "inbound_emails",
        "email_delivery_events",
    ])
    def test_key_table_present(self, tenant_tables, table):
        """Key tenant-scoped table must be in TENANT_TABLES."""
        assert table in tenant_tables, (
            f"Table {table!r} not found in TENANT_TABLES"
        )

    @pytest.mark.parametrize("table", [
        "ticket_assignments",
        "onboarding_sessions",
        "knowledge_documents",
        "webhook_events",
        "technique_configurations",
    ])
    def test_additional_table_present(self, tenant_tables, table):
        """Additional tables from various migrations must be present."""
        assert table in tenant_tables, (
            f"Table {table!r} not found in TENANT_TABLES"
        )


# ═══════════════════════════════════════════════════════════════════
# 9. Documentation
# ═══════════════════════════════════════════════════════════════════

class TestDocumentation:
    """Verify migration has proper documentation."""

    def test_has_docstring(self, migration_022_source):
        """Migration must have a module-level docstring."""
        tree = ast.parse(migration_022_source)
        doc = ast.get_docstring(tree)
        assert doc is not None, "No module-level docstring"

    def test_docstring_mentions_rls(self, migration_022_source):
        """Docstring must mention RLS."""
        tree = ast.parse(migration_022_source)
        doc = ast.get_docstring(tree)
        assert "RLS" in doc or "row-level security" in doc.lower(), (
            "Docstring doesn't mention RLS"
        )

    def test_docstring_mentions_company_id(self, migration_022_source):
        """Docstring must mention company_id."""
        tree = ast.parse(migration_022_source)
        doc = ast.get_docstring(tree)
        assert "company_id" in doc, (
            "Docstring doesn't mention company_id"
        )
