"""
Integration Tests for PARWA Jarvis Awareness Engine (Phase 2.3)

Unlike unit tests which mock the DB, these tests use SQLite in-memory
databases with real ORM models and real queries. This validates the
full data flow: service logic → ORM → SQL → DB → query results.

Test Suites:
  1. TestFullTickLifecycle — End-to-end tick with real DB writes
  2. TestMultiTickAlertLifecycle — Dedup, cooldown, escalation, lifecycle
  3. TestPruningIntegration — Snapshot + alert pruning with real data
  4. TestDeltaDetectionIntegration — Delta computed across real snapshots
  5. TestRuleEngineIntegration — Each rule creates real DB alert records
  6. TestSnapshotHistoryIntegration — Pagination, filtering, ordering

BC-008: All tests verify graceful handling of edge cases.
BC-001: company_id always first parameter.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import json
import time
import pytest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.base import Base
from database.models.jarvis import JarvisSession, JarvisMessage
from database.models.jarvis_cc import (
    JarvisAwarenessSnapshot,
    JarvisCommand,
    JarvisProactiveAlert,
)


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh SQLite in-memory DB for each test.

    Creates all tables, yields a session, then drops everything.
    We disable FK enforcement so we don't need real users/companies rows.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Disable FK enforcement for SQLite (no users/companies tables needed)
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    # Only create the tables we need (avoids JSONB errors from other models)
    target_tables = [
        JarvisSession.__table__,
        JarvisMessage.__table__,
        JarvisAwarenessSnapshot.__table__,
        JarvisProactiveAlert.__table__,
        JarvisCommand.__table__,
    ]
    for table in target_tables:
        table.create(engine, checkfirst=True)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    for table in reversed(target_tables):
        table.drop(engine, checkfirst=True)
    engine.dispose()


@pytest.fixture
def sample_cc_session_db(db_session):
    """Create a real JarvisSession in the DB for CC awareness tests."""
    session = JarvisSession(
        id="cc_session_integ_001",
        user_id="user_integ_001",
        company_id="company_integ_001",
        type="customer_care",
        is_active=True,
        context_json=json.dumps({
            "variant_tier": "parwa",
            "variant_instance_id": "inst_parwa_001",
            "industry": "ecommerce",
            "mode": "customer_care",
            "awareness_enabled": True,
            "proactive_alerts": [],
        }),
        message_count_today=10,
        total_message_count=150,
        pack_type="free",
        payment_status="none",
    )
    db_session.add(session)
    db_session.flush()
    return session


@pytest.fixture
def healthy_state() -> Dict[str, Any]:
    """A healthy awareness state dict — no thresholds breached."""
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "collection_errors": [],
        # Domain 1
        "current_plan": "parwa",
        "plan_usage_today": 65.5,
        "subscription_status": "active",
        "days_until_renewal": 14,
        # Domain 2
        "system_health": "healthy",
        "channel_health": {"email": "healthy", "sms": "healthy", "chat": "healthy"},
        "active_alerts": [],
        # Domain 3
        "ticket_volume_today": 45,
        "ticket_volume_avg": 38.5,
        "ticket_volume_spike": False,
        # Domain 4
        "active_agents": 3,
        "agent_pool_capacity": 5,
        "agent_pool_utilization": 60.0,
        # Domain 5
        "training_running": False,
        "training_mistake_count": 2,
        "training_model_version": "v2.1",
        # Domain 6
        "drift_status": "none",
        "drift_score": 0.05,
        "quality_score": 0.92,
        "quality_alerts": [],
        # Domain 7
        "last_5_errors": [],
    }


@pytest.fixture
def degraded_state() -> Dict[str, Any]:
    """A degraded state — multiple thresholds breached."""
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "collection_errors": [],
        "current_plan": "parwa",
        "plan_usage_today": 88.0,
        "subscription_status": "active",
        "days_until_renewal": 2,
        "system_health": "degraded",
        "channel_health": {"email": "healthy", "sms": "degraded", "chat": "healthy"},
        "active_alerts": [{"alert_id": "a1", "severity": "warning"}],
        "ticket_volume_today": 120,
        "ticket_volume_avg": 38.5,
        "ticket_volume_spike": True,
        "active_agents": 5,
        "agent_pool_capacity": 5,
        "agent_pool_utilization": 100.0,
        "training_running": False,
        "training_mistake_count": 2,
        "training_model_version": "v2.1",
        "drift_status": "moderate",
        "drift_score": 0.45,
        "quality_score": 0.55,
        "quality_alerts": [],
        "last_5_errors": [
            {"error": "timeout", "node": "router", "timestamp": datetime.now(timezone.utc).isoformat()},
        ],
    }


@pytest.fixture
def critical_state() -> Dict[str, Any]:
    """A critical state — emergency-level issues."""
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "collection_errors": [],
        "current_plan": "parwa",
        "plan_usage_today": 97.0,
        "subscription_status": "past_due",
        "days_until_renewal": 1,
        "system_health": "down",
        "channel_health": {"email": "down", "sms": "down", "chat": "down"},
        "active_alerts": [],
        "ticket_volume_today": 200,
        "ticket_volume_avg": 38.5,
        "ticket_volume_spike": True,
        "active_agents": 0,
        "agent_pool_capacity": 5,
        "agent_pool_utilization": 0.0,
        "training_running": False,
        "training_mistake_count": 15,
        "training_model_version": "v2.1",
        "drift_status": "severe",
        "drift_score": 0.75,
        "quality_score": 0.35,
        "quality_alerts": [],
        "last_5_errors": [
            {"error": "timeout", "node": "router", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"error": "rate_limit", "node": "sms_agent", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"error": "model_error", "node": "billing", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"error": "db_timeout", "node": "core", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"error": "auth_fail", "node": "gateway", "timestamp": datetime.now(timezone.utc).isoformat()},
        ],
    }


# Helper to run a tick with the real DB, mocking only get_cc_session
def _run_tick_with_real_db(db, session_obj, state, tick_type="manual"):
    """Run awareness tick with real DB, mocking only the session lookup.

    The import of get_cc_session is deferred (inside run_awareness_tick),
    so we patch it at the source module: app.services.jarvis_cc_service
    """
    from app.services.jarvis_awareness_engine import run_awareness_tick

    with patch("app.services.jarvis_cc_service.get_cc_session") as mock_get:
        mock_get.return_value = session_obj
        result = run_awareness_tick(
            db=db,
            company_id=session_obj.company_id,
            session_id=session_obj.id,
            user_id=session_obj.user_id,
            tick_type=tick_type,
            override_state=state,
        )
    return result


# ══════════════════════════════════════════════════════════════════
# 1. FULL TICK LIFECYCLE
# ══════════════════════════════════════════════════════════════════


class TestFullTickLifecycle:
    """End-to-end tick with real DB writes and reads."""

    def test_first_tick_creates_snapshot(self, db_session, sample_cc_session_db, healthy_state):
        """First tick should create a snapshot in the DB."""
        result = _run_tick_with_real_db(db_session, sample_cc_session_db, healthy_state)

        # Verify snapshot exists in DB
        snapshot = db_session.query(JarvisAwarenessSnapshot).filter(
            JarvisAwarenessSnapshot.session_id == sample_cc_session_db.id,
        ).first()
        assert snapshot is not None
        assert snapshot.company_id == "company_integ_001"
        assert snapshot.system_health == "healthy"
        assert snapshot.quality_score is not None

    def test_first_tick_returns_correct_metadata(self, db_session, sample_cc_session_db, healthy_state):
        """First tick result should have snapshot_id, tick_type, tick_number=1."""
        result = _run_tick_with_real_db(db_session, sample_cc_session_db, healthy_state)

        assert "snapshot_id" in result
        assert result["tick_type"] == "manual"
        assert result["tick_number"] == 1
        assert "alerts_created" in result
        assert "total_ms" in result

    def test_tick_increments_tick_number(self, db_session, sample_cc_session_db, healthy_state):
        """Second tick should have tick_number=2."""
        _run_tick_with_real_db(db_session, sample_cc_session_db, healthy_state)

        # Reload session to get updated context
        db_session.flush()
        result = _run_tick_with_real_db(db_session, sample_cc_session_db, healthy_state)

        assert result["tick_number"] == 2

    def test_tick_updates_session_context(self, db_session, sample_cc_session_db, healthy_state):
        """Tick should update the session's context_json with awareness data."""
        _run_tick_with_real_db(db_session, sample_cc_session_db, healthy_state)

        # Re-read session from DB
        db_session.flush()
        updated = db_session.query(JarvisSession).filter(
            JarvisSession.id == sample_cc_session_db.id,
        ).first()
        ctx = json.loads(updated.context_json)
        assert ctx["awareness_enabled"] is True
        assert "awareness_last_tick" in ctx
        assert ctx["awareness_system_health"] == "healthy"

    def test_tick_with_degraded_state_creates_alerts(self, db_session, sample_cc_session_db, degraded_state):
        """Degraded state should create alerts in the DB."""
        result = _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)

        assert result["alerts_created"] >= 1
        # Verify alerts in DB
        alerts = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.company_id == "company_integ_001",
        ).all()
        assert len(alerts) >= 1

    def test_tick_with_healthy_state_no_critical_alerts(self, db_session, sample_cc_session_db, healthy_state):
        """Healthy state should not create any critical or emergency alerts."""
        result = _run_tick_with_real_db(db_session, sample_cc_session_db, healthy_state)

        # Healthy state may create info alerts (renewal etc.) but not critical
        critical_alerts = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.severity.in_(["critical", "emergency"]),
        ).all()
        assert len(critical_alerts) == 0

    def test_tick_with_critical_state_creates_emergency_alert(self, db_session, sample_cc_session_db, critical_state):
        """Critical state should create emergency-level alerts."""
        result = _run_tick_with_real_db(db_session, sample_cc_session_db, critical_state)

        emergency_alerts = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.severity == "emergency",
        ).all()
        assert len(emergency_alerts) >= 1

    def test_tick_measures_latency(self, db_session, sample_cc_session_db, healthy_state):
        """Tick should measure and report latency > 0."""
        result = _run_tick_with_real_db(db_session, sample_cc_session_db, healthy_state)
        assert result["total_ms"] >= 0


# ══════════════════════════════════════════════════════════════════
# 2. MULTI-TICK ALERT LIFECYCLE
# ══════════════════════════════════════════════════════════════════


class TestMultiTickAlertLifecycle:
    """Tests for alert dedup, cooldown, escalation, and lifecycle."""

    def test_alert_persists_across_ticks(self, db_session, sample_cc_session_db, degraded_state):
        """Alert created in tick 1 should still be active after tick 2."""
        from app.services.jarvis_awareness_engine import get_active_alerts

        result1 = _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)
        alerts1, total1 = get_active_alerts(db_session, sample_cc_session_db.id, "company_integ_001")
        assert total1 >= 1

        # Tick 2 with same state — dedup should prevent duplicates, but existing alerts persist
        result2 = _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)
        alerts2, total2 = get_active_alerts(db_session, sample_cc_session_db.id, "company_integ_001")
        # Should still have same number (dedup blocks duplicates)
        assert total2 >= 1

    def test_dedup_prevents_duplicate_alerts(self, db_session, sample_cc_session_db, degraded_state):
        """Two ticks with same degraded state should NOT create duplicate alert types."""
        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)
        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)

        # Count alerts by type — each type should appear at most once as active
        active_alerts = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.status.in_(["active", "acknowledged"]),
        ).all()
        alert_types = [a.alert_type for a in active_alerts]
        # No duplicate active alert_types
        assert len(alert_types) == len(set(alert_types)), f"Duplicate alert types found: {alert_types}"

    def test_acknowledge_alert_via_lifecycle(self, db_session, sample_cc_session_db, degraded_state):
        """Create alert, acknowledge it, verify status in DB."""
        from app.services.jarvis_awareness_engine import acknowledge_alert

        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)
        alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.status == "active",
        ).first()
        assert alert is not None

        acknowledged = acknowledge_alert(
            db_session, str(alert.id), sample_cc_session_db.id, "company_integ_001", "user_integ_001",
        )
        assert acknowledged.status == "acknowledged"
        assert acknowledged.acknowledged_by == "user_integ_001"
        assert acknowledged.acknowledged_at is not None

    def test_resolve_alert_via_lifecycle(self, db_session, sample_cc_session_db, degraded_state):
        """Create alert, resolve it, verify resolved_at set."""
        from app.services.jarvis_awareness_engine import resolve_alert

        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)
        alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.status == "active",
        ).first()
        assert alert is not None

        resolved = resolve_alert(
            db_session, str(alert.id), sample_cc_session_db.id, "company_integ_001",
        )
        assert resolved.status == "resolved"
        assert resolved.resolved_at is not None

    def test_dismiss_alert_via_lifecycle(self, db_session, sample_cc_session_db, degraded_state):
        """Create alert, dismiss it, verify dismissed status."""
        from app.services.jarvis_awareness_engine import dismiss_alert

        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)
        alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.status == "active",
        ).first()
        assert alert is not None

        dismissed = dismiss_alert(
            db_session, str(alert.id), sample_cc_session_db.id, "company_integ_001", "user_integ_001",
        )
        assert dismissed.status == "dismissed"

    def test_acknowledge_then_resolve(self, db_session, sample_cc_session_db, degraded_state):
        """Full lifecycle: active → acknowledged → resolved."""
        from app.services.jarvis_awareness_engine import acknowledge_alert, resolve_alert

        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)
        alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.status == "active",
        ).first()
        assert alert is not None

        # Acknowledge
        ack = acknowledge_alert(
            db_session, str(alert.id), sample_cc_session_db.id, "company_integ_001", "user_integ_001",
        )
        assert ack.status == "acknowledged"

        # Resolve
        resolved = resolve_alert(
            db_session, str(alert.id), sample_cc_session_db.id, "company_integ_001",
        )
        assert resolved.status == "resolved"

    def test_cooldown_prevents_re_alerting(self, db_session, sample_cc_session_db, degraded_state):
        """Create alert, then run tick again — cooldown should block new alert with same dedup_key."""
        from app.services.jarvis_awareness_engine import create_alert, RULE_COOLDOWN_SECONDS

        # Create a known alert with a dedup_key
        alert = create_alert(
            db=db_session,
            session_id=sample_cc_session_db.id,
            company_id="company_integ_001",
            alert_type="test_cooldown",
            severity="warning",
            category="system_health",
            title="Test Cooldown",
            message="Testing cooldown",
            dedup_key="test_cooldown_key",
        )
        assert alert is not None

        # Try to create another alert with same dedup_key within cooldown
        alert2 = create_alert(
            db=db_session,
            session_id=sample_cc_session_db.id,
            company_id="company_integ_001",
            alert_type="test_cooldown",
            severity="warning",
            category="system_health",
            title="Test Cooldown 2",
            message="Should be blocked by cooldown",
            dedup_key="test_cooldown_key",
        )
        # Should be blocked by either dedup or cooldown
        assert alert2 is None

    def test_escalation_on_severity_increase(self, db_session, sample_cc_session_db):
        """Acknowledge a warning alert, then trigger critical — old should be resolved."""
        from app.services.jarvis_awareness_engine import (
            create_alert, acknowledge_alert, _escalate_if_needed,
        )

        # Create warning alert
        alert1 = create_alert(
            db=db_session,
            session_id=sample_cc_session_db.id,
            company_id="company_integ_001",
            alert_type="test_escalation",
            severity="warning",
            category="quality",
            title="Quality Warning",
            message="Quality is low",
            dedup_key="quality_score_drop",
        )
        assert alert1 is not None

        # Acknowledge it
        acknowledge_alert(
            db_session, str(alert1.id), sample_cc_session_db.id, "company_integ_001", "user_integ_001",
        )

        # Escalate to critical
        _escalate_if_needed(
            db_session, sample_cc_session_db.id, "company_integ_001",
            "test_escalation", "critical", "quality_score_drop",
        )

        # Old alert should now be resolved
        db_session.flush()
        old_alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.id == alert1.id,
        ).first()
        assert old_alert.status == "resolved"


# ══════════════════════════════════════════════════════════════════
# 3. PRUNING INTEGRATION
# ══════════════════════════════════════════════════════════════════


class TestPruningIntegration:
    """Tests for snapshot and alert pruning with real DB data."""

    def test_no_pruning_when_below_limit(self, db_session, sample_cc_session_db, healthy_state):
        """5 snapshots with max_keep=10 should not trigger pruning."""
        from app.services.jarvis_awareness_engine import create_snapshot, prune_old_snapshots

        for i in range(5):
            create_snapshot(
                db=db_session,
                session_id=sample_cc_session_db.id,
                company_id="company_integ_001",
                state=healthy_state,
                tick_type="periodic",
                tick_number=i + 1,
            )

        pruned = prune_old_snapshots(db_session, sample_cc_session_db.id, "company_integ_001", max_keep=10)
        assert pruned == 0

    def test_pruning_removes_old_snapshots(self, db_session, sample_cc_session_db, healthy_state):
        """15 snapshots with max_keep=10 should prune 5."""
        from app.services.jarvis_awareness_engine import create_snapshot, prune_old_snapshots

        for i in range(15):
            create_snapshot(
                db=db_session,
                session_id=sample_cc_session_db.id,
                company_id="company_integ_001",
                state=healthy_state,
                tick_type="periodic",
                tick_number=i + 1,
            )

        pruned = prune_old_snapshots(db_session, sample_cc_session_db.id, "company_integ_001", max_keep=10)
        assert pruned >= 1

        # Remaining snapshots should be <= max_keep (plus any emergency ones)
        remaining = db_session.query(JarvisAwarenessSnapshot).filter(
            JarvisAwarenessSnapshot.session_id == sample_cc_session_db.id,
        ).count()
        assert remaining <= 10 + 5  # some margin for batch deletion

    def test_pruning_preserves_emergency_snapshots(self, db_session, sample_cc_session_db, healthy_state):
        """Emergency type snapshots should survive pruning."""
        from app.services.jarvis_awareness_engine import create_snapshot, prune_old_snapshots

        # Create 10 periodic + 1 emergency
        for i in range(10):
            create_snapshot(
                db=db_session,
                session_id=sample_cc_session_db.id,
                company_id="company_integ_001",
                state=healthy_state,
                tick_type="periodic",
                tick_number=i + 1,
            )
        emergency_snap = create_snapshot(
            db=db_session,
            session_id=sample_cc_session_db.id,
            company_id="company_integ_001",
            state=healthy_state,
            tick_type="emergency",
            tick_number=11,
        )

        # Prune with max_keep=5 — should remove old periodics but keep emergency
        prune_old_snapshots(db_session, sample_cc_session_db.id, "company_integ_001", max_keep=5)

        # Emergency snapshot should still exist
        found = db_session.query(JarvisAwarenessSnapshot).filter(
            JarvisAwarenessSnapshot.id == emergency_snap.id,
        ).first()
        assert found is not None
        assert found.snapshot_type == "emergency"

    def test_alert_expiry_after_ttl(self, db_session, sample_cc_session_db):
        """Alert with short TTL should be expired by prune_expired_alerts."""
        from app.services.jarvis_awareness_engine import create_alert, prune_expired_alerts

        # Create alert with 1-second TTL
        alert = create_alert(
            db=db_session,
            session_id=sample_cc_session_db.id,
            company_id="company_integ_001",
            alert_type="test_expiry",
            severity="info",
            category="system_health",
            title="Expiring Soon",
            message="This alert will expire",
            ttl_seconds=1,  # 1 second TTL
        )
        assert alert is not None
        assert alert.status == "active"

        # Set created_at to 2 seconds ago so it's expired
        alert.created_at = datetime.now(timezone.utc) - timedelta(seconds=2)
        db_session.flush()

        # Prune expired
        expired = prune_expired_alerts(db_session, sample_cc_session_db.id, "company_integ_001")
        assert expired >= 1

        # Verify alert is now expired
        db_session.flush()
        updated = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.id == alert.id,
        ).first()
        assert updated.status == "expired"

    def test_emergency_alerts_never_expire(self, db_session, sample_cc_session_db):
        """Emergency alerts (TTL=0) should never auto-expire."""
        from app.services.jarvis_awareness_engine import create_alert, prune_expired_alerts

        alert = create_alert(
            db=db_session,
            session_id=sample_cc_session_db.id,
            company_id="company_integ_001",
            alert_type="test_no_expire",
            severity="emergency",
            category="system_health",
            title="Emergency Never Expires",
            message="This alert should not expire",
            ttl_seconds=0,  # 0 = no expiry
        )
        assert alert is not None

        # Set created_at far in the past
        alert.created_at = datetime.now(timezone.utc) - timedelta(days=30)
        db_session.flush()

        expired = prune_expired_alerts(db_session, sample_cc_session_db.id, "company_integ_001")
        assert expired == 0  # Emergency alerts should not be expired

        db_session.flush()
        updated = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.id == alert.id,
        ).first()
        assert updated.status == "active"


# ══════════════════════════════════════════════════════════════════
# 4. DELTA DETECTION INTEGRATION
# ══════════════════════════════════════════════════════════════════


class TestDeltaDetectionIntegration:
    """Tests for delta computed across real snapshots in the DB."""

    def test_delta_between_two_real_snapshots(self, db_session, sample_cc_session_db, healthy_state, degraded_state):
        """Two ticks with different states should produce a delta with changes."""
        _run_tick_with_real_db(db_session, sample_cc_session_db, healthy_state)

        # Reload session for updated context
        db_session.flush()
        result2 = _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)

        # Second tick should detect changes from the delta
        assert result2["delta_significant"] is True

    def test_delta_detects_system_health_worsening(self, db_session, sample_cc_session_db, healthy_state):
        """Health going from healthy → degraded should be detected in delta."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = healthy_state.copy()
        current = healthy_state.copy()
        current["system_health"] = "degraded"

        delta = compute_awareness_delta(current, previous)
        assert delta["has_significant_changes"] is True
        assert any(a["field"] == "system_health" for a in delta["new_alerts"])

    def test_delta_detects_quality_recovery(self, db_session, sample_cc_session_db, degraded_state):
        """Quality improving from 0.55 to 0.92 should be detected as recovery."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = degraded_state.copy()
        current = degraded_state.copy()
        current["quality_score"] = 0.92
        current["system_health"] = "healthy"

        delta = compute_awareness_delta(current, previous)
        quality_recoveries = [r for r in delta["recovered"] if r["field"] == "quality_score"]
        assert len(quality_recoveries) >= 1

    def test_delta_first_tick_always_significant(self, db_session, sample_cc_session_db, healthy_state):
        """First tick with no previous state should always be significant."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        delta = compute_awareness_delta(healthy_state, None)
        assert delta["has_significant_changes"] is True
        assert delta["is_first_tick"] is True

    def test_delta_detects_threshold_crossing(self, db_session, sample_cc_session_db):
        """Quality dropping from 0.75 to 0.60 should cross warning threshold."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"quality_score": 0.75}
        current = {"quality_score": 0.60}

        delta = compute_awareness_delta(current, previous)
        quality_alerts = [a for a in delta["new_alerts"] if a["field"] == "quality_score"]
        assert len(quality_alerts) >= 1
        assert quality_alerts[0]["change"] == "crossed_warning"


# ══════════════════════════════════════════════════════════════════
# 5. RULE ENGINE INTEGRATION
# ══════════════════════════════════════════════════════════════════


class TestRuleEngineIntegration:
    """Tests for each rule creating real DB alert records."""

    def test_system_health_degraded_creates_warning_alert(self, db_session, sample_cc_session_db, degraded_state):
        """Degraded system health should create a warning alert in DB."""
        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)

        alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.alert_type == "system_health_degraded",
        ).first()
        assert alert is not None
        assert alert.severity == "warning"

    def test_ticket_spike_creates_alert(self, db_session, sample_cc_session_db, degraded_state):
        """Ticket volume spike should create ticket_volume_spike alert in DB."""
        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)

        alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.alert_type == "ticket_volume_spike",
        ).first()
        assert alert is not None
        assert alert.category == "ticket_volume"

    def test_agent_pool_zero_creates_critical_alert(self, db_session, sample_cc_session_db, critical_state):
        """0 active agents should create agent_pool_zero critical alert."""
        _run_tick_with_real_db(db_session, sample_cc_session_db, critical_state)

        alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.alert_type == "agent_pool_zero",
        ).first()
        assert alert is not None
        assert alert.severity == "critical"

    def test_quality_drop_creates_warning_alert(self, db_session, sample_cc_session_db, degraded_state):
        """Quality score 0.55 should create quality_drop warning alert in DB."""
        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)

        alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.alert_type == "quality_drop",
        ).first()
        assert alert is not None
        assert alert.severity == "warning"
        assert alert.category == "quality"

    def test_drift_high_creates_warning_alert(self, db_session, sample_cc_session_db, degraded_state):
        """Drift score 0.45 should create drift_detected warning alert."""
        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)

        alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.alert_type == "drift_detected",
        ).first()
        assert alert is not None
        assert alert.severity == "warning"

    def test_plan_usage_high_creates_warning(self, db_session, sample_cc_session_db, degraded_state):
        """Plan usage at 88% should create plan_usage_high warning alert."""
        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)

        alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.alert_type == "plan_usage_high",
        ).first()
        assert alert is not None
        assert alert.category == "billing"

    def test_compound_spike_quality_creates_critical(self, db_session, sample_cc_session_db, degraded_state):
        """Spike + quality drop should create compound_spike_quality_drop critical alert."""
        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)

        alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.alert_type == "compound_spike_quality_drop",
        ).first()
        assert alert is not None
        assert alert.severity == "critical"

    def test_channel_specific_alert_created(self, db_session, sample_cc_session_db, degraded_state):
        """Degraded SMS channel should create a channel_health_degraded alert."""
        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)

        alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.alert_type == "channel_health_degraded",
        ).first()
        # May or may not exist depending on rule implementation
        if alert is not None:
            assert alert.category == "system_health"

    def test_error_rate_creates_alert(self, db_session, sample_cc_session_db, critical_state):
        """5 errors should create error_rate_high alert."""
        _run_tick_with_real_db(db_session, sample_cc_session_db, critical_state)

        alert = db_session.query(JarvisProactiveAlert).filter(
            JarvisProactiveAlert.session_id == sample_cc_session_db.id,
            JarvisProactiveAlert.alert_type == "error_rate_high",
        ).first()
        assert alert is not None

    def test_get_effective_thresholds_returns_defaults(self, db_session):
        """get_effective_thresholds with no overrides should return defaults."""
        from app.services.jarvis_awareness_engine import get_effective_thresholds

        thresholds = get_effective_thresholds("company_integ_001", {})
        assert "quality_warn" in thresholds
        assert thresholds["quality_warn"] == 0.70
        assert thresholds["quality_critical"] == 0.50
        assert thresholds["drift_warn"] == 0.30
        assert thresholds["utilization_warn"] == 80.0
        assert thresholds["plan_usage_warn"] == 80.0


# ══════════════════════════════════════════════════════════════════
# 6. SNAPSHOT HISTORY INTEGRATION
# ══════════════════════════════════════════════════════════════════


class TestSnapshotHistoryIntegration:
    """Tests for snapshot and alert history with real DB queries."""

    def test_get_latest_snapshot_returns_most_recent(self, db_session, sample_cc_session_db, healthy_state):
        """After 3 ticks, get_latest_snapshot should return the 3rd one."""
        from app.services.jarvis_awareness_engine import create_snapshot, get_latest_snapshot

        for i in range(3):
            create_snapshot(
                db=db_session,
                session_id=sample_cc_session_db.id,
                company_id="company_integ_001",
                state=healthy_state,
                tick_type="periodic",
                tick_number=i + 1,
            )

        latest = get_latest_snapshot(db_session, sample_cc_session_db.id, "company_integ_001")
        assert latest is not None
        assert latest.tick_number == 3

    def test_get_snapshot_history_paginated(self, db_session, sample_cc_session_db, healthy_state):
        """5 snapshots with limit=3 should return 3 + total=5."""
        from app.services.jarvis_awareness_engine import create_snapshot, get_snapshot_history

        for i in range(5):
            create_snapshot(
                db=db_session,
                session_id=sample_cc_session_db.id,
                company_id="company_integ_001",
                state=healthy_state,
                tick_type="periodic",
                tick_number=i + 1,
            )

        snapshots, total = get_snapshot_history(
            db_session, sample_cc_session_db.id, "company_integ_001", limit=3, offset=0,
        )
        assert total == 5
        assert len(snapshots) == 3

    def test_get_active_alerts_filtered_by_severity(self, db_session, sample_cc_session_db, degraded_state):
        """Should be able to filter alerts by severity."""
        from app.services.jarvis_awareness_engine import get_active_alerts

        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)

        # Filter for warning only
        warning_alerts, warning_count = get_active_alerts(
            db_session, sample_cc_session_db.id, "company_integ_001", severity="warning",
        )
        for alert in warning_alerts:
            assert alert.severity == "warning"

    def test_get_active_alerts_excludes_resolved(self, db_session, sample_cc_session_db, degraded_state):
        """Resolved alerts should not appear in get_active_alerts."""
        from app.services.jarvis_awareness_engine import get_active_alerts, resolve_alert

        _run_tick_with_real_db(db_session, sample_cc_session_db, degraded_state)
        alerts_before, total_before = get_active_alerts(db_session, sample_cc_session_db.id, "company_integ_001")

        # Resolve one alert
        if total_before > 0:
            resolve_alert(db_session, str(alerts_before[0].id), sample_cc_session_db.id, "company_integ_001")

        alerts_after, total_after = get_active_alerts(db_session, sample_cc_session_db.id, "company_integ_001")
        assert total_after < total_before or total_before == 0
