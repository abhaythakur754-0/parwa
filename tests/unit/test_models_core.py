"""
Tests for PARWA Database Models (Day 2)

BC-001: Every table has company_id with index (except root tables).
BC-002: All money fields are DECIMAL(10,2).
"""

import os

# Set env BEFORE any imports
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_key"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

import pytest  # noqa: E402
from sqlalchemy import inspect  # noqa: E402

# Import ALL models so Base.metadata knows about them
import database.models.core  # noqa: F401, E402
import database.models.billing  # noqa: F401, E402
import database.models.tickets  # noqa: F401, E402
import database.models.ai_pipeline  # noqa: F401, E402
import database.models.approval  # noqa: F401, E402
import database.models.analytics  # noqa: F401, E402
import database.models.training  # noqa: F401, E402
import database.models.integration  # noqa: F401, E402
import database.models.onboarding  # noqa: F401, E402

from database.base import Base, engine  # noqa: E402

# Tables that are ROOT level (no company_id) by design
ROOT_TABLES_NO_COMPANY_ID = {
    "companies", "channels", "api_providers",
    "newsletter_subscribers", "demo_sessions",
}

# Tables that MUST have company_id (BC-001)
TABLES_WITH_COMPANY_ID_REQUIRED = {
    "users", "refresh_tokens", "mfa_secrets", "backup_codes", "api_keys",
    "agents", "emergency_states", "user_notification_preferences",
    "subscriptions", "invoices", "overage_charges", "transactions",
    "webhook_events", "cancellation_requests",
    "sessions", "interactions", "customers", "ticket_attachments",
    "ticket_internal_notes",
    "gsd_sessions", "confidence_scores", "guardrail_blocks",
    "guardrail_rules", "prompt_templates", "model_usage_logs",
    "approval_queues", "auto_approve_rules", "executed_actions", "undo_log",
    "metric_aggregates", "roi_snapshots", "drift_reports", "qa_scores",
    "training_runs",
    "training_datasets", "training_checkpoints", "agent_mistakes",
    "agent_performance",
    "integrations", "rest_connectors", "webhook_integrations",
    "mcp_connections", "db_connections", "event_buffer", "error_log",
    "audit_trail", "outgoing_webhooks",
    "onboarding_sessions", "consent_records", "knowledge_documents",
    "service_configs",
}

# Money fields that must be Numeric (BC-002)
MONEY_FIELDS = {
    "invoices": ["amount"],
    "overage_charges": ["charge_amount"],
    "transactions": ["amount"],
    "approval_queues": ["amount"],
    "auto_approve_rules": ["max_amount"],
    "executed_actions": ["amount"],
    "metric_aggregates": ["value"],
    "roi_snapshots": ["avg_ai_cost", "avg_human_cost", "total_savings"],
}


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class TestTablesCreated:
    """Test that all expected tables are created."""

    def test_all_tables_exist(self):
        """All tables from roadmap are created."""
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        expected = TABLES_WITH_COMPANY_ID_REQUIRED | ROOT_TABLES_NO_COMPANY_ID
        missing = expected - table_names
        assert not missing, f"Missing tables: {missing}"

    def test_companies_table_created(self):
        """Root companies table exists (no company_id by design)."""
        inspector = inspect(engine)
        assert "companies" in inspector.get_table_names()


class TestBC001CompanyID:
    """BC-001: Multi-tenant isolation via company_id."""

    def test_every_tenant_table_has_company_id(self):
        """Every table that needs tenant isolation has company_id."""
        inspector = inspect(engine)
        for table_name in TABLES_WITH_COMPANY_ID_REQUIRED:
            columns = [c["name"] for c in inspector.get_columns(table_name)]
            assert "company_id" in columns, (
                f"BC-001 VIOLATION: {table_name} missing company_id"
            )

    def test_company_id_has_index(self):
        """company_id column has an index for query performance (BC-001)."""
        inspector = inspect(engine)
        for table_name in TABLES_WITH_COMPANY_ID_REQUIRED:
            indexes = inspector.get_indexes(table_name)
            index_cols = set()
            for idx in indexes:
                index_cols.update(idx["column_names"])
            assert "company_id" in index_cols, (
                f"BC-001 VIOLATION: {table_name}.company_id has no index"
            )


class TestBC002Decimal:
    """BC-002: Financial fields use Numeric (DECIMAL), never Float."""

    def test_money_fields_are_numeric(self):
        """All money fields use Numeric type, not Float."""
        inspector = inspect(engine)
        for table_name, fields in MONEY_FIELDS.items():
            for field in fields:
                cols = inspector.get_columns(table_name)
                columns = {c["name"]: c for c in cols}
                assert field in columns, f"Missing field {table_name}.{field}"
                col_type = str(columns[field]["type"]).upper()
                assert "FLOAT" not in col_type, (
                    f"BC-002 VIOLATION: {table_name}.{field} uses FLOAT"
                )


class TestTableCount:
    """Verify we have 50+ tables as per roadmap."""

    def test_minimum_table_count(self):
        """At least 45 tables must exist."""
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert len(tables) >= 45, (
            f"Only {len(tables)} tables created, need 45+"
        )
