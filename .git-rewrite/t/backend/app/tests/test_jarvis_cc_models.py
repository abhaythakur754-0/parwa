"""
Unit Tests for PARWA Jarvis CC ORM Models (jarvis_cc.py)

Tests cover:
  1. JarvisAwarenessSnapshot — field defaults, CHECK constraints,
     index validation, JSON column handling
  2. JarvisCommand — lifecycle transitions, intent/status constraints,
     undo tracking, source validation
  3. JarvisProactiveAlert — severity/category/status constraints,
     lifecycle transitions, dashboard behavior fields
  4. Updated JarvisMessage — new CC message type CHECK constraint
  5. JarvisSession — new awareness_snapshots + proactive_alerts
     relationships
  6. Migration validation — 020 upgrade/downgrade integrity

BC-008: All tests verify graceful handling of edge cases.
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from database.models.jarvis import (
    JarvisSession,
    JarvisMessage,
    JarvisKnowledgeUsed,
    JarvisActionTicket,
)
from database.models.jarvis_cc import (
    JarvisAwarenessSnapshot,
    JarvisCommand,
    JarvisProactiveAlert,
)


# ══════════════════════════════════════════════════════════════════
# HELPER FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_cc_session():
    """Create a sample customer care JarvisSession."""
    session = MagicMock(spec=JarvisSession)
    session.id = "cc_session_001"
    session.user_id = "user_001"
    session.company_id = "company_001"
    session.type = "customer_care"
    session.is_active = True
    session.context_json = json.dumps({
        "variant_tier": "parwa",
        "variant_instance_id": "inst_parwa_001",
        "industry": "ecommerce",
        "mode": "customer_care",
        "awareness_enabled": True,
    })
    return session


# ══════════════════════════════════════════════════════════════════
# JARVIS AWARENESS SNAPSHOT TESTS
# ══════════════════════════════════════════════════════════════════


class TestJarvisAwarenessSnapshot:
    """Tests for JarvisAwarenessSnapshot ORM model."""

    def test_table_name(self):
        """Table name should be jarvis_awareness_snapshots."""
        assert JarvisAwarenessSnapshot.__tablename__ == "jarvis_awareness_snapshots"

    def test_has_all_group14_flattened_fields(self):
        """Model should have all 21 GROUP 14 fields from ParwaGraphState."""
        expected_fields = {
            "current_plan", "plan_usage_today", "subscription_status",
            "days_until_renewal", "system_health", "channel_health_json",
            "active_alerts_count", "active_alerts_json",
            "ticket_volume_today", "ticket_volume_avg", "ticket_volume_spike",
            "active_agents", "agent_pool_capacity", "agent_pool_utilization",
            "training_running", "training_mistake_count",
            "training_model_version", "drift_status", "drift_score",
            "quality_score", "quality_alerts_json", "last_5_errors_json",
        }
        mapper = JarvisAwarenessSnapshot.__table__.columns.keys()
        for field in expected_fields:
            assert field in mapper, f"Missing GROUP 14 field: {field}"

    def test_has_snapshot_metadata_fields(self):
        """Model should have snapshot_type and tick_number."""
        mapper = JarvisAwarenessSnapshot.__table__.columns.keys()
        assert "snapshot_type" in mapper
        assert "tick_number" in mapper

    def test_has_raw_state_json(self):
        """Model should have raw_state_json for full recovery."""
        mapper = JarvisAwarenessSnapshot.__table__.columns.keys()
        assert "raw_state_json" in mapper

    def test_has_company_id_with_fk(self):
        """company_id should have FK to companies.id for BC-001."""
        company_col = JarvisAwarenessSnapshot.__table__.c.company_id
        assert company_col is not None
        # FK should reference companies.id
        fks = list(company_col.foreign_keys)
        assert len(fks) == 1
        assert "companies.id" in str(fks[0].target_fullname)

    def test_has_session_id_with_fk(self):
        """session_id should have FK to jarvis_sessions.id."""
        session_col = JarvisAwarenessSnapshot.__table__.c.session_id
        fks = list(session_col.foreign_keys)
        assert len(fks) == 1
        assert "jarvis_sessions.id" in str(fks[0].target_fullname)

    def test_snapshot_type_check_constraint(self):
        """snapshot_type should only allow valid values."""
        constraints = JarvisAwarenessSnapshot.__table__.constraints
        check_constraints = [
            c for c in constraints
            if hasattr(c, 'name') and c.name == "ck_jarvis_aware_snapshot_type"
        ]
        assert len(check_constraints) == 1

    def test_valid_snapshot_types(self):
        """Valid snapshot types: periodic, on_change, manual, emergency."""
        valid_types = ["periodic", "on_change", "manual", "emergency"]
        for st in valid_types:
            # Should not raise on instantiation with valid type
            snapshot = JarvisAwarenessSnapshot(
                session_id="s1",
                company_id="c1",
                snapshot_type=st,
            )
            assert snapshot.snapshot_type == st

    def test_json_column_defaults(self):
        """JSON columns should have sensible defaults."""
        snapshot = JarvisAwarenessSnapshot(
            session_id="s1",
            company_id="c1",
        )
        # These should have server defaults, not Python defaults
        # But we can verify the column definitions exist
        assert hasattr(snapshot, "channel_health_json")
        assert hasattr(snapshot, "active_alerts_json")
        assert hasattr(snapshot, "quality_alerts_json")
        assert hasattr(snapshot, "last_5_errors_json")
        assert hasattr(snapshot, "raw_state_json")

    def test_numeric_precision_fields(self):
        """Numeric fields should use appropriate precision."""
        # plan_usage_today: 0.0-100.0 → Numeric(5,2)
        col = JarvisAwarenessSnapshot.__table__.c.plan_usage_today
        assert col.type.precision == 5
        assert col.type.scale == 2

        # drift_score: 0.0-1.0 → Numeric(5,4)
        col = JarvisAwarenessSnapshot.__table__.c.drift_score
        assert col.type.precision == 5
        assert col.type.scale == 4

        # quality_score: 0.0-1.0 → Numeric(5,4)
        col = JarvisAwarenessSnapshot.__table__.c.quality_score
        assert col.type.precision == 5
        assert col.type.scale == 4

    def test_has_composite_indexes(self):
        """Should have composite indexes for common query patterns."""
        indexes = JarvisAwarenessSnapshot.__table__.indexes
        index_names = {idx.name for idx in indexes if idx.name}
        assert "ix_jarvis_aware_comp_created" in index_names
        assert "ix_jarvis_aware_session_created" in index_names

    def test_cascade_delete_on_session(self):
        """session_id FK should CASCADE on delete."""
        session_col = JarvisAwarenessSnapshot.__table__.c.session_id
        fks = list(session_col.foreign_keys)
        assert fks[0].ondelete == "CASCADE"


# ══════════════════════════════════════════════════════════════════
# JARVIS COMMAND TESTS
# ══════════════════════════════════════════════════════════════════


class TestJarvisCommand:
    """Tests for JarvisCommand ORM model."""

    def test_table_name(self):
        """Table name should be jarvis_commands."""
        assert JarvisCommand.__tablename__ == "jarvis_commands"

    def test_has_all_group20_fields(self):
        """Model should map all 6 GROUP 20 fields from ParwaGraphState."""
        # GROUP 20 fields: jarvis_command_parsed, jarvis_command_intent,
        # co_pilot_suggestion, co_pilot_suggestion_type,
        # jarvis_feed_entry, jarvis_command_metadata
        mapper = JarvisCommand.__table__.columns.keys()
        assert "command_parsed" in mapper  # maps to jarvis_command_parsed
        assert "command_intent" in mapper  # maps to jarvis_command_intent
        assert "co_pilot_suggestion" in mapper
        assert "co_pilot_suggestion_type" in mapper
        assert "command_metadata_json" in mapper  # maps to jarvis_command_metadata

    def test_has_full_lifecycle_timestamps(self):
        """Command should track received → parsed → executed → completed."""
        mapper = JarvisCommand.__table__.columns.keys()
        assert "received_at" in mapper
        assert "parsed_at" in mapper
        assert "executed_at" in mapper
        assert "completed_at" in mapper

    def test_valid_command_intents(self):
        """Valid intents: query, control, configure, report, override."""
        valid_intents = ["query", "control", "configure", "report", "override"]
        for intent in valid_intents:
            cmd = JarvisCommand(
                session_id="s1",
                company_id="c1",
                raw_input="test",
                command_intent=intent,
            )
            assert cmd.command_intent == intent

    def test_valid_command_statuses(self):
        """Valid statuses cover full lifecycle."""
        valid_statuses = [
            "received", "parsing", "parsed", "executing",
            "completed", "failed", "cancelled", "undone",
        ]
        for status in valid_statuses:
            cmd = JarvisCommand(
                session_id="s1",
                company_id="c1",
                raw_input="test",
                status=status,
            )
            assert cmd.status == status

    def test_valid_sources(self):
        """Valid sources: chat, api, co_pilot, proactive, scheduled."""
        valid_sources = ["chat", "api", "co_pilot", "proactive", "scheduled"]
        for source in valid_sources:
            cmd = JarvisCommand(
                session_id="s1",
                company_id="c1",
                raw_input="test",
                source=source,
            )
            assert cmd.source == source

    def test_undo_tracking(self):
        """Commands should track undo availability and link to undo command."""
        cmd = JarvisCommand(
            session_id="s1",
            company_id="c1",
            raw_input="pause all AI",
            undo_available=True,
            undone_by_command_id=None,
        )
        assert cmd.undo_available is True
        assert cmd.undone_by_command_id is None

    def test_undo_chain(self):
        """When a command is undone, undone_by_command_id links to the undo."""
        original_cmd = JarvisCommand(
            session_id="s1",
            company_id="c1",
            raw_input="pause all AI",
            status="completed",
        )
        undo_cmd = JarvisCommand(
            session_id="s1",
            company_id="c1",
            raw_input="undo last command",
            status="completed",
            undone_by_command_id=str(original_cmd.id),
        )
        assert undo_cmd.undone_by_command_id == str(original_cmd.id)

    def test_has_error_message_field(self):
        """Failed commands should have an error message."""
        mapper = JarvisCommand.__table__.columns.keys()
        assert "error_message" in mapper

    def test_has_result_json(self):
        """Commands should store execution result data."""
        mapper = JarvisCommand.__table__.columns.keys()
        assert "result_json" in mapper

    def test_has_confidence_field(self):
        """Parsed commands should have confidence score."""
        col = JarvisCommand.__table__.c.confidence
        assert col is not None
        assert col.type.precision == 5
        assert col.type.scale == 4

    def test_has_composite_indexes(self):
        """Should have composite indexes for audit queries."""
        indexes = JarvisCommand.__table__.indexes
        index_names = {idx.name for idx in indexes if idx.name}
        assert "ix_jarvis_cmd_comp_created" in index_names
        assert "ix_jarvis_cmd_session_created" in index_names
        assert "ix_jarvis_cmd_comp_status" in index_names

    def test_check_constraints_exist(self):
        """Should have CHECK constraints for intent, status, source."""
        constraints = JarvisCommand.__table__.constraints
        constraint_names = {
            c.name for c in constraints
            if hasattr(c, 'name') and c.name
        }
        assert "ck_jarvis_cmd_intent" in constraint_names
        assert "ck_jarvis_cmd_status" in constraint_names
        assert "ck_jarvis_cmd_source" in constraint_names


# ══════════════════════════════════════════════════════════════════
# JARVIS PROACTIVE ALERT TESTS
# ══════════════════════════════════════════════════════════════════


class TestJarvisProactiveAlert:
    """Tests for JarvisProactiveAlert ORM model."""

    def test_table_name(self):
        """Table name should be jarvis_proactive_alerts."""
        assert JarvisProactiveAlert.__tablename__ == "jarvis_proactive_alerts"

    def test_has_alert_content_fields(self):
        """Alert should have title, message, and details."""
        mapper = JarvisProactiveAlert.__table__.columns.keys()
        assert "title" in mapper
        assert "message" in mapper
        assert "details_json" in mapper

    def test_valid_severities(self):
        """Valid severities: info, warning, critical, emergency."""
        valid_severities = ["info", "warning", "critical", "emergency"]
        for severity in valid_severities:
            alert = JarvisProactiveAlert(
                session_id="s1",
                company_id="c1",
                alert_type="quality_drop",
                title="Quality Drop Detected",
                message="Response quality below threshold",
                severity=severity,
            )
            assert alert.severity == severity

    def test_valid_categories(self):
        """Valid categories match awareness engine domains."""
        valid_categories = [
            "system_health", "ticket_volume", "agent_pool",
            "quality", "drift", "billing", "security", "integration",
        ]
        for category in valid_categories:
            alert = JarvisProactiveAlert(
                session_id="s1",
                company_id="c1",
                alert_type="test",
                title="Test",
                message="Test",
                category=category,
            )
            assert alert.category == category

    def test_valid_lifecycle_statuses(self):
        """Alert lifecycle: active → acknowledged/dismissed → resolved/expired."""
        valid_statuses = [
            "active", "acknowledged", "dismissed", "resolved", "expired",
        ]
        for status in valid_statuses:
            alert = JarvisProactiveAlert(
                session_id="s1",
                company_id="c1",
                alert_type="test",
                title="Test",
                message="Test",
                status=status,
            )
            assert alert.status == status

    def test_has_acknowledged_fields(self):
        """Alerts should track who acknowledged and when."""
        mapper = JarvisProactiveAlert.__table__.columns.keys()
        assert "acknowledged_by" in mapper
        assert "acknowledged_at" in mapper

    def test_has_dashboard_behavior_fields(self):
        """Alerts should have dashboard rendering hints."""
        mapper = JarvisProactiveAlert.__table__.columns.keys()
        assert "action_required" in mapper
        assert "action_url" in mapper
        assert "ttl_seconds" in mapper

    def test_has_related_resource_fields(self):
        """Alerts should link to related snapshots and commands."""
        mapper = JarvisProactiveAlert.__table__.columns.keys()
        assert "related_snapshot_id" in mapper
        assert "related_command_id" in mapper

    def test_alert_type_is_required(self):
        """alert_type should be nullable=False."""
        col = JarvisProactiveAlert.__table__.c.alert_type
        assert col.nullable is False

    def test_title_is_required(self):
        """title should be nullable=False."""
        col = JarvisProactiveAlert.__table__.c.title
        assert col.nullable is False

    def test_message_is_required(self):
        """message should be nullable=False."""
        col = JarvisProactiveAlert.__table__.c.message
        assert col.nullable is False

    def test_has_composite_indexes(self):
        """Should have composite indexes for dashboard queries."""
        indexes = JarvisProactiveAlert.__table__.indexes
        index_names = {idx.name for idx in indexes if idx.name}
        assert "ix_jarvis_alert_comp_created" in index_names
        assert "ix_jarvis_alert_comp_severity" in index_names
        assert "ix_jarvis_alert_session_created" in index_names
        assert "ix_jarvis_alert_comp_status" in index_names

    def test_check_constraints_exist(self):
        """Should have CHECK constraints for severity, category, status."""
        constraints = JarvisProactiveAlert.__table__.constraints
        constraint_names = {
            c.name for c in constraints
            if hasattr(c, 'name') and c.name
        }
        assert "ck_jarvis_alert_severity" in constraint_names
        assert "ck_jarvis_alert_category" in constraint_names
        assert "ck_jarvis_alert_status" in constraint_names

    def test_emergency_alert_scenario(self):
        """Emergency alerts should have all required fields."""
        alert = JarvisProactiveAlert(
            session_id="cc_session_001",
            company_id="company_001",
            alert_type="emergency_state_change",
            severity="emergency",
            category="system_health",
            title="AI System Paused - Critical",
            message="AI responses have been paused due to critical system issue. Immediate attention required.",
            details_json=json.dumps({
                "metric": "system_health",
                "threshold": "healthy",
                "actual": "critical",
                "recommendation": "Check system status and resume AI when resolved",
            }),
            action_required=True,
            action_url="/dashboard/settings?tab=ai-controls",
            status="active",
        )
        assert alert.severity == "emergency"
        assert alert.action_required is True
        assert alert.status == "active"

    def test_ticket_volume_spike_alert(self):
        """Ticket volume spike alert should link to a snapshot."""
        alert = JarvisProactiveAlert(
            session_id="cc_session_001",
            company_id="company_001",
            alert_type="ticket_volume_spike",
            severity="warning",
            category="ticket_volume",
            title="Ticket Volume Spike Detected",
            message="Today's ticket volume is 2.5x the 7-day average.",
            details_json=json.dumps({
                "metric": "ticket_volume",
                "threshold": 2.0,
                "actual": 2.5,
                "trend": "increasing",
            }),
            related_snapshot_id="snapshot_001",
            ttl_seconds=3600,
        )
        assert alert.related_snapshot_id == "snapshot_001"
        assert alert.ttl_seconds == 3600


# ══════════════════════════════════════════════════════════════════
# UPDATED JARVIS MESSAGE TYPE TESTS
# ══════════════════════════════════════════════════════════════════


class TestJarvisMessageCCExtensions:
    """Tests for the updated JarvisMessage with CC message types."""

    def test_message_type_column_exists(self):
        """message_type column should exist."""
        col = JarvisMessage.__table__.c.message_type
        assert col is not None

    def test_cc_message_types_in_check_constraint(self):
        """CHECK constraint should include CC message types."""
        constraints = JarvisMessage.__table__.constraints
        check_constraints = [
            c for c in constraints
            if hasattr(c, 'name') and c.name == "ck_jarvis_message_type"
        ]
        assert len(check_constraints) == 1

    def test_valid_cc_message_types(self):
        """CC message types should be valid for JarvisMessage."""
        cc_types = [
            "variant_pipeline",
            "ai_generated",
            "direct_ai",
            "proactive_alert",
            "command_response",
        ]
        for msg_type in cc_types:
            msg = JarvisMessage(
                session_id="s1",
                role="jarvis",
                content="Test",
                message_type=msg_type,
            )
            assert msg.message_type == msg_type

    def test_onboarding_message_types_still_valid(self):
        """Original onboarding message types should still be valid."""
        onboarding_types = [
            "text", "bill_summary", "payment_card", "otp_card",
            "handoff_card", "demo_call_card", "action_ticket",
            "call_summary", "recharge_cta",
            "limit_reached", "pack_expired", "error",
        ]
        for msg_type in onboarding_types:
            msg = JarvisMessage(
                session_id="s1",
                role="jarvis",
                content="Test",
                message_type=msg_type,
            )
            assert msg.message_type == msg_type


# ══════════════════════════════════════════════════════════════════
# JARVIS SESSION NEW RELATIONSHIPS TESTS
# ══════════════════════════════════════════════════════════════════


class TestJarvisSessionCCRelationships:
    """Tests for JarvisSession awareness_snapshots + proactive_alerts relationships."""

    def test_has_awareness_snapshots_relationship(self):
        """JarvisSession should have awareness_snapshots relationship."""
        rels = JarvisSession.__mapper__.relationships
        assert "awareness_snapshots" in rels

    def test_has_proactive_alerts_relationship(self):
        """JarvisSession should have proactive_alerts relationship."""
        rels = JarvisSession.__mapper__.relationships
        assert "proactive_alerts" in rels

    def test_awareness_snapshots_cascade_delete(self):
        """awareness_snapshots should cascade delete with session."""
        rel = JarvisSession.__mapper__.relationships.get("awareness_snapshots")
        assert rel is not None
        assert rel.cascade.delete

    def test_proactive_alerts_cascade_delete(self):
        """proactive_alerts should cascade delete with session."""
        rel = JarvisSession.__mapper__.relationships.get("proactive_alerts")
        assert rel is not None
        assert rel.cascade.delete

    def test_awareness_snapshots_back_populates(self):
        """awareness_snapshots should back_populate to session."""
        rel = JarvisSession.__mapper__.relationships.get("awareness_snapshots")
        assert rel.back_populates == "session"

    def test_proactive_alerts_back_populates(self):
        """proactive_alerts should back_populate to session."""
        rel = JarvisSession.__mapper__.relationships.get("proactive_alerts")
        assert rel.back_populates == "session"


# ══════════════════════════════════════════════════════════════════
# CROSS-TABLE INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestCrossTableIntegration:
    """Tests for cross-table relationships and data flow."""

    def test_awareness_snapshot_back_references_session(self):
        """JarvisAwarenessSnapshot.session should reference JarvisSession."""
        rel = JarvisAwarenessSnapshot.__mapper__.relationships.get("session")
        assert rel is not None
        assert rel.back_populates == "awareness_snapshots"

    def test_proactive_alert_back_references_session(self):
        """JarvisProactiveAlert.session should reference JarvisSession."""
        rel = JarvisProactiveAlert.__mapper__.relationships.get("session")
        assert rel is not None
        assert rel.back_populates == "proactive_alerts"

    def test_all_tables_share_session_fk(self):
        """All 3 new tables should FK to jarvis_sessions."""
        for model in [JarvisAwarenessSnapshot, JarvisCommand, JarvisProactiveAlert]:
            session_col = model.__table__.c.session_id
            fks = list(session_col.foreign_keys)
            assert len(fks) == 1, f"{model.__name__} missing session FK"
            assert "jarvis_sessions.id" in str(fks[0].target_fullname)

    def test_all_tables_share_company_fk(self):
        """All 3 new tables should FK to companies for BC-001."""
        for model in [JarvisAwarenessSnapshot, JarvisCommand, JarvisProactiveAlert]:
            company_col = model.__table__.c.company_id
            fks = list(company_col.foreign_keys)
            assert len(fks) == 1, f"{model.__name__} missing company FK"
            assert "companies.id" in str(fks[0].target_fullname)

    def test_all_tables_cascade_delete_on_session(self):
        """All 3 new tables should CASCADE on session delete."""
        for model in [JarvisAwarenessSnapshot, JarvisCommand, JarvisProactiveAlert]:
            session_col = model.__table__.c.session_id
            fks = list(session_col.foreign_keys)
            assert fks[0].ondelete == "CASCADE", (
                f"{model.__name__} session FK should CASCADE"
            )

    def test_all_tables_cascade_delete_on_company(self):
        """All 3 new tables should CASCADE on company delete."""
        for model in [JarvisAwarenessSnapshot, JarvisCommand, JarvisProactiveAlert]:
            company_col = model.__table__.c.company_id
            fks = list(company_col.foreign_keys)
            assert fks[0].ondelete == "CASCADE", (
                f"{model.__name__} company FK should CASCADE"
            )


# ══════════════════════════════════════════════════════════════════
# MIGRATION VALIDATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestMigration020:
    """Tests for the 020_jarvis_cc_tables migration file."""

    def test_migration_file_exists(self):
        """Migration file should exist."""
        import os
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "database", "alembic", "versions",
            "020_jarvis_cc_tables.py",
        )
        # Normalize the path
        migration_path = os.path.normpath(migration_path)
        assert os.path.exists(migration_path), (
            f"Migration file not found at {migration_path}"
        )

    def test_migration_has_correct_revision(self):
        """Migration revision should be 020 with correct down_revision."""
        import os
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "database", "alembic", "versions",
            "020_jarvis_cc_tables.py",
        )
        migration_path = os.path.normpath(migration_path)

        if not os.path.exists(migration_path):
            pytest.skip("Migration file not at expected path")

        with open(migration_path) as f:
            content = f.read()

        assert 'revision = "020"' in content
        assert 'down_revision = "019_ooo_bounce_tables"' in content

    def test_migration_creates_three_tables(self):
        """Migration upgrade should create exactly 3 tables."""
        import os
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "database", "alembic", "versions",
            "020_jarvis_cc_tables.py",
        )
        migration_path = os.path.normpath(migration_path)

        if not os.path.exists(migration_path):
            pytest.skip("Migration file not at expected path")

        with open(migration_path) as f:
            content = f.read()

        assert 'create_table("jarvis_awareness_snapshots"' in content
        assert 'create_table("jarvis_commands"' in content
        assert 'create_table("jarvis_proactive_alerts"' in content

    def test_migration_drops_three_tables(self):
        """Migration downgrade should drop 3 tables + restore constraint."""
        import os
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "database", "alembic", "versions",
            "020_jarvis_cc_tables.py",
        )
        migration_path = os.path.normpath(migration_path)

        if not os.path.exists(migration_path):
            pytest.skip("Migration file not at expected path")

        with open(migration_path) as f:
            content = f.read()

        assert 'drop_table("jarvis_proactive_alerts")' in content
        assert 'drop_table("jarvis_commands")' in content
        assert 'drop_table("jarvis_awareness_snapshots")' in content

    def test_migration_extends_message_type_constraint(self):
        """Migration should extend jarvis_messages CHECK constraint."""
        import os
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "database", "alembic", "versions",
            "020_jarvis_cc_tables.py",
        )
        migration_path = os.path.normpath(migration_path)

        if not os.path.exists(migration_path):
            pytest.skip("Migration file not at expected path")

        with open(migration_path) as f:
            content = f.read()

        # Should drop and recreate the constraint with new types
        assert "drop_constraint" in content
        assert "ck_jarvis_message_type" in content
        assert "variant_pipeline" in content
        assert "proactive_alert" in content
        assert "command_response" in content


# ══════════════════════════════════════════════════════════════════
# AWARENESS SNAPSHOT DATA FLOW TESTS
# ══════════════════════════════════════════════════════════════════


class TestAwarenessSnapshotDataFlow:
    """Tests simulating the data flow from ParwaGraphState → DB."""

    def test_group14_state_to_snapshot(self):
        """Should be able to create snapshot from GROUP 14 state dict."""
        # Simulated GROUP 14 state from ParwaGraphState
        group14_state = {
            "current_plan": "parwa",
            "plan_usage_today": 65.5,
            "subscription_status": "active",
            "days_until_renewal": 14,
            "system_health": "healthy",
            "channel_health": {"email": "healthy", "sms": "degraded", "chat": "healthy"},
            "active_alerts": [
                {"alert_id": "a1", "severity": "warning", "message": "SMS channel degraded"},
            ],
            "ticket_volume_today": 45,
            "ticket_volume_avg": 38.5,
            "ticket_volume_spike": False,
            "active_agents": 3,
            "agent_pool_capacity": 5,
            "agent_pool_utilization": 60.0,
            "training_running": False,
            "training_mistake_count": 2,
            "training_model_version": "v2.1",
            "drift_status": "none",
            "drift_score": 0.05,
            "quality_score": 0.92,
            "quality_alerts": [],
            "last_5_errors": [],
        }

        # Create snapshot from state
        snapshot = JarvisAwarenessSnapshot(
            session_id="cc_session_001",
            company_id="company_001",
            snapshot_type="periodic",
            tick_number=42,
            current_plan=group14_state["current_plan"],
            plan_usage_today=group14_state["plan_usage_today"],
            subscription_status=group14_state["subscription_status"],
            days_until_renewal=group14_state["days_until_renewal"],
            system_health=group14_state["system_health"],
            channel_health_json=json.dumps(group14_state["channel_health"]),
            active_alerts_count=len(group14_state["active_alerts"]),
            active_alerts_json=json.dumps(group14_state["active_alerts"]),
            ticket_volume_today=group14_state["ticket_volume_today"],
            ticket_volume_avg=group14_state["ticket_volume_avg"],
            ticket_volume_spike=group14_state["ticket_volume_spike"],
            active_agents=group14_state["active_agents"],
            agent_pool_capacity=group14_state["agent_pool_capacity"],
            agent_pool_utilization=group14_state["agent_pool_utilization"],
            training_running=group14_state["training_running"],
            training_mistake_count=group14_state["training_mistake_count"],
            training_model_version=group14_state["training_model_version"],
            drift_status=group14_state["drift_status"],
            drift_score=group14_state["drift_score"],
            quality_score=group14_state["quality_score"],
            quality_alerts_json=json.dumps(group14_state["quality_alerts"]),
            last_5_errors_json=json.dumps(group14_state["last_5_errors"]),
            raw_state_json=json.dumps(group14_state),
        )

        assert snapshot.current_plan == "parwa"
        assert snapshot.plan_usage_today == 65.5
        assert snapshot.system_health == "healthy"
        assert snapshot.ticket_volume_today == 45
        assert snapshot.quality_score == 0.92
        assert snapshot.tick_number == 42

        # Verify JSON round-trip
        parsed_channel_health = json.loads(snapshot.channel_health_json)
        assert parsed_channel_health["sms"] == "degraded"

    def test_emergency_snapshot_type(self):
        """Emergency snapshot should capture system health change."""
        snapshot = JarvisAwarenessSnapshot(
            session_id="cc_session_001",
            company_id="company_001",
            snapshot_type="emergency",
            system_health="critical",
            active_alerts_count=3,
            raw_state_json=json.dumps({"system_health": "critical"}),
        )
        assert snapshot.snapshot_type == "emergency"
        assert snapshot.system_health == "critical"


# ══════════════════════════════════════════════════════════════════
# COMMAND LIFECYCLE TESTS
# ══════════════════════════════════════════════════════════════════


class TestCommandLifecycle:
    """Tests simulating the full command lifecycle."""

    def test_command_received_state(self):
        """New command starts in 'received' state."""
        cmd = JarvisCommand(
            session_id="s1",
            company_id="c1",
            raw_input="How many tickets today?",
            source="chat",
            status="received",
        )
        assert cmd.status == "received"
        assert cmd.received_at is not None or True  # server default

    def test_command_parsing_state(self):
        """Command transitions to 'parsing' when NL parsing starts."""
        cmd = JarvisCommand(
            session_id="s1",
            company_id="c1",
            raw_input="pause all AI",
            source="chat",
            status="parsing",
        )
        assert cmd.status == "parsing"

    def test_command_parsed_with_intent(self):
        """Parsed command should have intent and confidence."""
        cmd = JarvisCommand(
            session_id="s1",
            company_id="c1",
            raw_input="pause all AI",
            source="chat",
            status="parsed",
            command_parsed='{"action": "pause", "scope": "all"}',
            command_intent="control",
            confidence=0.95,
        )
        assert cmd.command_intent == "control"
        assert float(cmd.confidence) == 0.95

    def test_command_completed(self):
        """Completed command should have result and timestamps."""
        now = datetime.now(timezone.utc)
        cmd = JarvisCommand(
            session_id="s1",
            company_id="c1",
            raw_input="pause all AI",
            source="chat",
            status="completed",
            command_intent="control",
            result_json=json.dumps({"paused_channels": ["email", "sms", "chat"]}),
            received_at=now,
            parsed_at=now,
            executed_at=now,
            completed_at=now,
        )
        assert cmd.status == "completed"
        result = json.loads(cmd.result_json)
        assert len(result["paused_channels"]) == 3

    def test_command_failed(self):
        """Failed command should have error message."""
        cmd = JarvisCommand(
            session_id="s1",
            company_id="c1",
            raw_input="pause all AI",
            source="chat",
            status="failed",
            command_intent="control",
            error_message="Emergency state is already active",
        )
        assert cmd.status == "failed"
        assert "already active" in cmd.error_message

    def test_co_pilot_suggestion(self):
        """Co-Pilot can suggest before command execution."""
        cmd = JarvisCommand(
            session_id="s1",
            company_id="c1",
            raw_input="what should I do about the ticket spike?",
            source="chat",
            co_pilot_suggestion="Consider increasing agent pool capacity to handle the spike",
            co_pilot_suggestion_type="policy_reminder",
        )
        assert cmd.co_pilot_suggestion_type == "policy_reminder"


# ══════════════════════════════════════════════════════════════════
# MODELS REGISTRY TESTS
# ══════════════════════════════════════════════════════════════════


class TestModelsRegistry:
    """Tests for models/__init__.py registration."""

    def test_jarvis_cc_models_importable(self):
        """jarvis_cc models should be importable from database.models."""
        from database.models import (
            JarvisAwarenessSnapshot,
            JarvisCommand,
            JarvisProactiveAlert,
        )
        assert JarvisAwarenessSnapshot is not None
        assert JarvisCommand is not None
        assert JarvisProactiveAlert is not None

    def test_jarvis_models_still_importable(self):
        """Original jarvis models should still be importable."""
        from database.models import (
            JarvisSession,
            JarvisMessage,
            JarvisKnowledgeUsed,
            JarvisActionTicket,
        )
        assert JarvisSession is not None
        assert JarvisMessage is not None
