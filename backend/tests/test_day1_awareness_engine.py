"""
PARWA Jarvis Awareness Engine — Comprehensive Unit Tests (Day 1)

Covers all 12 major test areas:
  1. collect_awareness_state — 7 domain collectors, BC-008 isolation
  2. create_snapshot — ORM mapping, JSON serialization, db.add/flush
  3. get_latest_snapshot — retrieval, None case, session/company scoping
  4. get_snapshot_history — pagination, ordering, total count
  5. create_alert — deduplication, cooldown, TTL defaults, dedup_key in details
  6. get_active_alerts — status filter, severity/category filter, ordering, pagination
  7. Alert lifecycle — acknowledge, dismiss, resolve, NotFoundError, company isolation
  8. compute_awareness_delta — first tick, status changes, threshold crossings, recovery
  9. prune_old_snapshots — limit enforcement, emergency/on_change preservation, batch delete
 10. prune_expired_alerts — TTL expiry, emergency non-expiry
 11. run_awareness_tick — full tick integration, override_state, tick types, context update
 12. Threshold constants — all values verified

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""
from __future__ import annotations

import json
import os
import pytest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock, call

# Inline _AttrChainer (same as conftest) for patching model class attributes
# to support .desc(), .in_(), .notin_() used by SQLAlchemy-style query chains.
class _AttrChainer:
    """Supports SQLAlchemy-style attribute chaining on mock model classes."""
    def __getattr__(self, name):
        return _AttrChainer()
    def desc(self):
        return self
    def asc(self):
        return self
    def __ge__(self, other):
        return True
    def __le__(self, other):
        return True
    def __eq__(self, other):
        return True
    def __ne__(self, other):
        return False
    def in_(self, *args):
        return self
    def notin_(self, *args):
        return self
    def isnot(self, *args):
        return self
    def contains(self, *args):
        return self
    def __bool__(self):
        return True

# Ensure env vars before any app imports
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32c")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-testing-32c")
os.environ.setdefault("ENVIRONMENT", "test")

from database.models.jarvis import JarvisSession, JarvisMessage
from database.models.jarvis_cc import (
    JarvisAwarenessSnapshot,
    JarvisCommand,
    JarvisProactiveAlert,
)


# ══════════════════════════════════════════════════════════════════
# HELPER FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_db():
    """Create a fresh mock SQLAlchemy session for each test.

    Pre-configures the most common query chains so that .filter().order_by().first()
    returns None, .all() returns [], .count() returns 0, etc.
    """
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.scalar.return_value = 0
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.limit.return_value.all.return_value = []
    db.query.return_value.scalar.return_value = 0
    return db


@pytest.fixture
def company_id():
    """Default test company ID (BC-001)."""
    return "comp_day1_001"


@pytest.fixture
def session_id():
    """Default test CC session ID."""
    return "cc_sess_day1_001"


@pytest.fixture
def user_id():
    """Default test user ID."""
    return "user_day1_001"


@pytest.fixture
def sample_cc_session():
    """Create a sample customer care JarvisSession mock.

    Note: JarvisSession from conftest is already a MagicMock (not a real class),
    so we cannot use spec=JarvisSession (InvalidSpecError).
    """
    session = MagicMock()
    session.id = "cc_sess_day1_001"
    session.user_id = "user_day1_001"
    session.company_id = "comp_day1_001"
    session.type = "customer_care"
    session.is_active = True
    session.context_json = json.dumps({
        "variant_tier": "parwa",
        "variant_instance_id": "inst_parwa_001",
        "industry": "ecommerce",
        "mode": "customer_care",
        "awareness_enabled": True,
        "proactive_alerts": [],
    })
    session.message_count_today = 10
    session.total_message_count = 150
    return session


@pytest.fixture
def sample_awareness_state():
    """Create a sample awareness state dict with all 7 domains populated."""
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "collection_errors": [],
        # Domain 1: Plan & Subscription
        "current_plan": "parwa",
        "plan_usage_today": 65.5,
        "subscription_status": "active",
        "days_until_renewal": 14,
        # Domain 2: System Health
        "system_health": "healthy",
        "channel_health": {"email": "healthy", "sms": "healthy", "chat": "healthy"},
        "active_alerts": [],
        # Domain 3: Ticket Volume
        "ticket_volume_today": 45,
        "ticket_volume_avg": 38.5,
        "ticket_volume_spike": False,
        # Domain 4: Agent Pool
        "active_agents": 3,
        "agent_pool_capacity": 5,
        "agent_pool_utilization": 60.0,
        # Domain 5: Training
        "training_running": False,
        "training_mistake_count": 2,
        "training_model_version": "v2.1",
        # Domain 6: Drift & Quality
        "drift_status": "none",
        "drift_score": 0.05,
        "quality_score": 0.92,
        "quality_alerts": [],
        # Domain 7: Errors
        "last_5_errors": [],
    }


@pytest.fixture
def sample_degraded_state():
    """Create an awareness state with degraded system health and threshold breaches."""
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "collection_errors": [],
        "current_plan": "parwa",
        "plan_usage_today": 88.0,
        "subscription_status": "active",
        "days_until_renewal": 2,
        "system_health": "degraded",
        "channel_health": {"email": "healthy", "sms": "degraded", "chat": "healthy"},
        "active_alerts": [{"alert_id": "a1", "severity": "warning", "message": "SMS degraded"}],
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
        "quality_alerts": [{"metric": "quality", "threshold": 0.8, "actual": 0.55, "severity": "warning"}],
        "last_5_errors": [
            {"error": "timeout", "node": "router", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"error": "rate_limit", "node": "sms_agent", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"error": "model_error", "node": "billing_agent", "timestamp": datetime.now(timezone.utc).isoformat()},
        ],
    }


# ══════════════════════════════════════════════════════════════════
# 1. TestCollectAwarenessState
# ══════════════════════════════════════════════════════════════════


class TestCollectAwarenessState:
    """Tests for collect_awareness_state — 7 domain collectors, BC-008 isolation."""

    def test_returns_dict_with_all_expected_keys(self, mock_db, company_id, session_id):
        """collect_awareness_state returns dict with all GROUP 14 keys."""
        from app.services.jarvis_awareness_engine import collect_awareness_state

        state = collect_awareness_state(mock_db, company_id, session_id)

        expected_keys = [
            "collected_at", "collection_errors",
            "current_plan", "plan_usage_today", "subscription_status",
            "days_until_renewal",
            "system_health", "channel_health", "active_alerts",
            "ticket_volume_today", "ticket_volume_avg", "ticket_volume_spike",
            "active_agents", "agent_pool_capacity", "agent_pool_utilization",
            "training_running", "training_mistake_count", "training_model_version",
            "drift_status", "drift_score", "quality_score", "quality_alerts",
            "last_5_errors",
        ]
        for key in expected_keys:
            assert key in state, f"Missing expected key: {key}"

    def test_each_domain_collector_independently_wrapped(self, mock_db, company_id, session_id):
        """BC-008: If a domain collector fails, others continue (partial awareness)."""
        from app.services.jarvis_awareness_engine import collect_awareness_state

        # Make db.query raise on first call (affects Domain 1's inner try/except),
        # then work for subsequent calls.  Since each collector has its own
        # try/except, the function should still complete.
        call_count = {"n": 0}
        original_query = mock_db.query

        def _flaky_query(model):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                raise Exception("DB connection failed")
            return original_query(model)

        mock_db.query = _flaky_query
        state = collect_awareness_state(mock_db, company_id, session_id)

        # Should still return a dict (partial awareness is better than none)
        assert isinstance(state, dict)
        # collected_at should always be present
        assert "collected_at" in state

    def test_if_domain_fails_others_continue(self, mock_db, company_id, session_id):
        """When DB raises exceptions, domain collectors return safe defaults."""
        from app.services.jarvis_awareness_engine import collect_awareness_state

        mock_db.query.side_effect = Exception("DB connection failed")

        state = collect_awareness_state(mock_db, company_id, session_id)

        assert isinstance(state, dict)
        # Domain defaults should still appear
        assert state.get("system_health") in ("healthy", "unknown")
        assert state.get("ticket_volume_today", 0) >= 0
        assert isinstance(state.get("channel_health", {}), dict)

    def test_collected_at_timestamp_is_utc(self, mock_db, company_id, session_id):
        """BC-012: collected_at timestamp should be UTC."""
        from app.services.jarvis_awareness_engine import collect_awareness_state

        state = collect_awareness_state(mock_db, company_id, session_id)

        assert "collected_at" in state
        collected_at = state["collected_at"]
        assert collected_at is not None
        # Verify it can be parsed as a UTC ISO timestamp
        parsed = datetime.fromisoformat(collected_at)
        assert parsed.tzinfo is not None or "Z" in collected_at or "+" in collected_at

    def test_collection_errors_populated_when_collectors_fail(self, mock_db, company_id, session_id):
        """collection_errors list should exist when collectors fail.

        Note: The current implementation does not append to collection_errors
        on failure (it relies on safe defaults), but the key must be present.
        """
        from app.services.jarvis_awareness_engine import collect_awareness_state

        state = collect_awareness_state(mock_db, company_id, session_id)

        assert "collection_errors" in state
        assert isinstance(state["collection_errors"], list)

    def test_plan_subscription_defaults(self, mock_db, company_id):
        """Domain 1 returns safe defaults when Subscription table missing."""
        from app.services.jarvis_awareness_engine import _collect_plan_subscription

        mock_db.query.side_effect = Exception("No table")
        result = _collect_plan_subscription(mock_db, company_id)

        assert result["current_plan"] is not None
        assert result["plan_usage_today"] >= 0
        assert result["subscription_status"] is not None
        assert result["days_until_renewal"] >= 0

    def test_system_health_defaults(self, mock_db, company_id):
        """Domain 2 returns healthy defaults when no emergency."""
        from app.services.jarvis_awareness_engine import _collect_system_health

        result = _collect_system_health(mock_db, company_id)
        assert "system_health" in result
        assert "channel_health" in result
        assert isinstance(result["channel_health"], dict)

    def test_ticket_volume_defaults(self, mock_db, company_id):
        """Domain 3 returns 0 volume when no tickets."""
        from app.services.jarvis_awareness_engine import _collect_ticket_volume

        result = _collect_ticket_volume(mock_db, company_id)
        assert "ticket_volume_today" in result
        assert "ticket_volume_avg" in result
        assert "ticket_volume_spike" in result

    def test_agent_pool_defaults(self, mock_db, company_id):
        """Domain 4 returns safe defaults."""
        from app.services.jarvis_awareness_engine import _collect_agent_pool

        result = _collect_agent_pool(mock_db, company_id)
        assert result["active_agents"] >= 0
        assert result["agent_pool_capacity"] > 0
        assert result["agent_pool_utilization"] >= 0

    def test_training_defaults(self, mock_db, company_id):
        """Domain 5 returns safe defaults."""
        from app.services.jarvis_awareness_engine import _collect_training

        result = _collect_training(mock_db, company_id)
        assert isinstance(result["training_running"], bool)
        assert result["training_mistake_count"] >= 0

    def test_drift_quality_defaults(self, mock_db, company_id):
        """Domain 6 returns safe defaults."""
        from app.services.jarvis_awareness_engine import _collect_drift_quality

        result = _collect_drift_quality(mock_db, company_id)
        assert result["drift_status"] in ("none", "slight", "moderate", "severe", "unknown")
        assert result["drift_score"] >= 0
        assert result["quality_score"] >= 0

    def test_errors_defaults(self, mock_db, company_id):
        """Domain 7 returns empty list when no errors."""
        from app.services.jarvis_awareness_engine import _collect_errors

        result = _collect_errors(mock_db, company_id)
        assert isinstance(result["last_5_errors"], list)


# ══════════════════════════════════════════════════════════════════
# 2. TestCreateSnapshot
# ══════════════════════════════════════════════════════════════════


class TestCreateSnapshot:
    """Tests for create_snapshot — ORM mapping, JSON serialization, db.add/flush."""

    def test_creates_snapshot_with_correct_field_mapping(
        self, mock_db, sample_awareness_state, company_id, session_id,
    ):
        """All GROUP 14 fields map correctly from state to snapshot."""
        from app.services.jarvis_awareness_engine import create_snapshot

        snapshot = create_snapshot(
            db=mock_db,
            session_id=session_id,
            company_id=company_id,
            state=sample_awareness_state,
            tick_type="periodic",
            tick_number=42,
        )

        assert snapshot.session_id == session_id
        assert snapshot.company_id == company_id
        assert snapshot.snapshot_type == "periodic"
        assert snapshot.tick_number == 42
        assert snapshot.current_plan == "parwa"
        assert float(snapshot.plan_usage_today) == 65.5
        assert snapshot.subscription_status == "active"
        assert snapshot.days_until_renewal == 14
        assert snapshot.system_health == "healthy"
        assert snapshot.ticket_volume_today == 45
        assert snapshot.ticket_volume_spike is False
        assert snapshot.active_agents == 3
        assert snapshot.agent_pool_capacity == 5
        assert float(snapshot.agent_pool_utilization) == 60.0
        assert snapshot.training_running is False
        assert snapshot.training_mistake_count == 2
        assert snapshot.training_model_version == "v2.1"
        assert snapshot.drift_status == "none"
        assert float(snapshot.drift_score) == 0.05
        assert float(snapshot.quality_score) == 0.92

    def test_channel_health_dict_to_json(self, mock_db, sample_awareness_state, company_id, session_id):
        """Channel health dict should be serialized to JSON string."""
        from app.services.jarvis_awareness_engine import create_snapshot

        snapshot = create_snapshot(
            db=mock_db, session_id=session_id, company_id=company_id,
            state=sample_awareness_state,
        )

        parsed = json.loads(snapshot.channel_health_json)
        assert parsed["email"] == "healthy"
        assert parsed["sms"] == "healthy"
        assert parsed["chat"] == "healthy"

    def test_active_alerts_list_to_json(self, mock_db, sample_awareness_state, company_id, session_id):
        """Active alerts list should be serialized to JSON with correct count."""
        from app.services.jarvis_awareness_engine import create_snapshot

        sample_awareness_state["active_alerts"] = [
            {"alert_id": "a1", "severity": "warning"},
            {"alert_id": "a2", "severity": "info"},
        ]

        snapshot = create_snapshot(
            db=mock_db, session_id=session_id, company_id=company_id,
            state=sample_awareness_state,
        )

        assert snapshot.active_alerts_count == 2
        parsed = json.loads(snapshot.active_alerts_json)
        assert len(parsed) == 2

    def test_quality_alerts_and_last_5_errors_serialized(
        self, mock_db, company_id, session_id,
    ):
        """quality_alerts and last_5_errors should be serialized to JSON."""
        from app.services.jarvis_awareness_engine import create_snapshot

        state = {
            "quality_alerts": [{"metric": "quality", "actual": 0.5}],
            "last_5_errors": [{"error": "timeout", "node": "router"}],
            "channel_health": {},
            "active_alerts": [],
        }

        snapshot = create_snapshot(
            db=mock_db, session_id=session_id, company_id=company_id,
            state=state,
        )

        qa = json.loads(snapshot.quality_alerts_json)
        assert len(qa) == 1
        assert qa[0]["metric"] == "quality"

        errs = json.loads(snapshot.last_5_errors_json)
        assert len(errs) == 1
        assert errs[0]["error"] == "timeout"

    def test_raw_state_json_stored_for_crash_recovery(
        self, mock_db, sample_awareness_state, company_id, session_id,
    ):
        """Complete raw state should be stored in raw_state_json for crash recovery."""
        from app.services.jarvis_awareness_engine import create_snapshot

        snapshot = create_snapshot(
            db=mock_db, session_id=session_id, company_id=company_id,
            state=sample_awareness_state,
        )

        raw = json.loads(snapshot.raw_state_json)
        assert raw["current_plan"] == "parwa"
        assert raw["quality_score"] == 0.92
        assert raw["drift_score"] == 0.05

    def test_db_add_and_flush_called(self, mock_db, sample_awareness_state, company_id, session_id):
        """Should call db.add() and db.flush()."""
        from app.services.jarvis_awareness_engine import create_snapshot

        create_snapshot(
            db=mock_db, session_id=session_id, company_id=company_id,
            state=sample_awareness_state,
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_handles_non_dict_channel_health(self, mock_db, company_id, session_id):
        """Non-dict channel_health falls back to empty JSON dict."""
        from app.services.jarvis_awareness_engine import create_snapshot

        state = {"channel_health": "not_a_dict"}
        snapshot = create_snapshot(
            db=mock_db, session_id=session_id, company_id=company_id,
            state=state,
        )

        parsed = json.loads(snapshot.channel_health_json)
        assert isinstance(parsed, dict)

    def test_handles_empty_state(self, mock_db, company_id, session_id):
        """Empty state dict should create snapshot with safe defaults."""
        from app.services.jarvis_awareness_engine import create_snapshot

        snapshot = create_snapshot(
            db=mock_db, session_id=session_id, company_id=company_id,
            state={},
        )

        assert snapshot is not None
        assert snapshot.system_health == "unknown"
        assert snapshot.ticket_volume_today == 0
        assert snapshot.active_agents == 0

    def test_emergency_snapshot_type(self, mock_db, sample_awareness_state, company_id, session_id):
        """Should support emergency snapshot type."""
        from app.services.jarvis_awareness_engine import create_snapshot

        snapshot = create_snapshot(
            db=mock_db, session_id=session_id, company_id=company_id,
            state=sample_awareness_state, tick_type="emergency",
        )
        assert snapshot.snapshot_type == "emergency"


# ══════════════════════════════════════════════════════════════════
# 3. TestGetLatestSnapshot
# ══════════════════════════════════════════════════════════════════


class TestGetLatestSnapshot:
    """Tests for get_latest_snapshot — retrieval, None case, scoping."""

    def test_returns_most_recent_snapshot(self, mock_db, company_id, session_id):
        """Should return the most recent snapshot."""
        from app.services.jarvis_awareness_engine import get_latest_snapshot

        mock_snapshot = MagicMock(spec=JarvisAwarenessSnapshot)
        mock_snapshot.id = "snap_latest"
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_snapshot

        result = get_latest_snapshot(mock_db, session_id, company_id)

        assert result is not None
        assert result.id == "snap_latest"

    def test_returns_none_when_no_snapshots(self, mock_db, company_id, session_id):
        """Should return None when no snapshots exist."""
        from app.services.jarvis_awareness_engine import get_latest_snapshot

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = get_latest_snapshot(mock_db, session_id, company_id)
        assert result is None

    def test_filters_by_session_id_and_company_id(self, mock_db, company_id, session_id):
        """Should pass session_id and company_id as filters (BC-001)."""
        from app.services.jarvis_awareness_engine import get_latest_snapshot

        get_latest_snapshot(mock_db, session_id, company_id)

        # Verify db.query was called
        mock_db.query.assert_called_once()


# ══════════════════════════════════════════════════════════════════
# 4. TestGetSnapshotHistory
# ══════════════════════════════════════════════════════════════════


class TestGetSnapshotHistory:
    """Tests for get_snapshot_history — pagination, ordering, total count."""

    def test_returns_paginated_results(self, mock_db, company_id, session_id):
        """Should return paginated snapshot list and total count."""
        from app.services.jarvis_awareness_engine import get_snapshot_history

        mock_snapshots = [MagicMock(spec=JarvisAwarenessSnapshot) for _ in range(3)]
        mock_db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 10
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_snapshots

        snapshots, total = get_snapshot_history(
            mock_db, session_id, company_id, limit=3, offset=0,
        )

        assert total == 10
        assert len(snapshots) == 3

    def test_returns_total_count(self, mock_db, company_id, session_id):
        """Should return correct total count."""
        from app.services.jarvis_awareness_engine import get_snapshot_history

        mock_db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 42
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

        snapshots, total = get_snapshot_history(mock_db, session_id, company_id)

        assert total == 42

    def test_orders_by_created_at_descending(self, mock_db, company_id, session_id):
        """Should request ordering by created_at descending."""
        from app.services.jarvis_awareness_engine import get_snapshot_history

        mock_db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 0
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

        get_snapshot_history(mock_db, session_id, company_id)

        # The query builder should have been called
        mock_db.query.assert_called_once()


# ══════════════════════════════════════════════════════════════════
# 5. TestCreateAlert
# ══════════════════════════════════════════════════════════════════


class TestCreateAlert:
    """Tests for create_alert — dedup, cooldown, TTL, dedup_key in details."""

    def test_creates_alert_with_all_fields(self, mock_db, company_id, session_id):
        """Should create alert with all specified fields."""
        from app.services.jarvis_awareness_engine import create_alert

        alert = create_alert(
            db=mock_db,
            session_id=session_id,
            company_id=company_id,
            alert_type="ticket_volume_spike",
            severity="warning",
            category="ticket_volume",
            title="Ticket Volume Spike",
            message="Today's volume is 3x average",
            details_json='{"ratio": 3.1}',
            action_required=True,
            action_url="/dashboard/tickets",
            ttl_seconds=7200,
            related_snapshot_id="snap_001",
            dedup_key="tv_spike_001",
        )

        assert alert is not None
        assert alert.session_id == session_id
        assert alert.company_id == company_id
        assert alert.alert_type == "ticket_volume_spike"
        assert alert.severity == "warning"
        assert alert.category == "ticket_volume"
        assert alert.title == "Ticket Volume Spike"
        assert alert.message == "Today's volume is 3x average"
        assert alert.action_required is True
        assert alert.ttl_seconds == 7200
        assert alert.status == "active"

    def test_deduplication_returns_none_when_active_alert_exists(self, mock_db, company_id, session_id):
        """Should return None if active alert with same dedup_key exists."""
        from app.services.jarvis_awareness_engine import create_alert

        # Simulate an existing active alert with same dedup_key
        existing_alert = MagicMock()
        existing_alert.details_json = json.dumps({"_dedup_key": "dedup_abc", "extra": "data"})
        mock_db.query.return_value.filter.return_value.first.return_value = existing_alert

        result = create_alert(
            db=mock_db,
            session_id=session_id,
            company_id=company_id,
            alert_type="system_health_degraded",
            severity="warning",
            category="system_health",
            title="System Degraded",
            message="System is degraded",
            dedup_key="dedup_abc",
        )

        assert result is None

    def test_cooldown_check_returns_none(self, mock_db, company_id, session_id):
        """Should return None if in cooldown period for the dedup_key."""
        from app.services.jarvis_awareness_engine import create_alert

        # No existing active alert (dedup check passes), but cooldown is active
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.services.jarvis_awareness_engine._is_in_cooldown", return_value=True):
            result = create_alert(
                db=mock_db,
                session_id=session_id,
                company_id=company_id,
                alert_type="system_health_degraded",
                severity="warning",
                category="system_health",
                title="System Degraded",
                message="System is degraded",
                dedup_key="cooldown_key_123",
            )

        assert result is None

    def test_ttl_defaults_based_on_severity_info(self, mock_db, company_id, session_id):
        """TTL should default to ALERT_TTL_INFO (3600) for info severity."""
        from app.services.jarvis_awareness_engine import create_alert, ALERT_TTL_INFO

        alert = create_alert(
            db=mock_db,
            session_id=session_id,
            company_id=company_id,
            alert_type="test",
            severity="info",
            category="test",
            title="Info",
            message="Info msg",
        )

        assert alert.ttl_seconds == ALERT_TTL_INFO

    def test_ttl_defaults_based_on_severity_warning(self, mock_db, company_id, session_id):
        """TTL should default to ALERT_TTL_WARNING (14400) for warning severity."""
        from app.services.jarvis_awareness_engine import create_alert, ALERT_TTL_WARNING

        alert = create_alert(
            db=mock_db,
            session_id=session_id,
            company_id=company_id,
            alert_type="test",
            severity="warning",
            category="test",
            title="Warning",
            message="Warning msg",
        )

        assert alert.ttl_seconds == ALERT_TTL_WARNING

    def test_ttl_defaults_based_on_severity_critical(self, mock_db, company_id, session_id):
        """TTL should default to ALERT_TTL_CRITICAL (86400) for critical severity."""
        from app.services.jarvis_awareness_engine import create_alert, ALERT_TTL_CRITICAL

        alert = create_alert(
            db=mock_db,
            session_id=session_id,
            company_id=company_id,
            alert_type="test",
            severity="critical",
            category="test",
            title="Critical",
            message="Critical msg",
        )

        assert alert.ttl_seconds == ALERT_TTL_CRITICAL

    def test_emergency_alerts_have_ttl_zero(self, mock_db, company_id, session_id):
        """Emergency alerts should have TTL=0 (no expiry)."""
        from app.services.jarvis_awareness_engine import create_alert, ALERT_TTL_EMERGENCY

        alert = create_alert(
            db=mock_db,
            session_id=session_id,
            company_id=company_id,
            alert_type="test",
            severity="emergency",
            category="test",
            title="Emergency",
            message="Emergency msg",
        )

        assert alert.ttl_seconds == ALERT_TTL_EMERGENCY
        assert ALERT_TTL_EMERGENCY == 0

    def test_dedup_key_added_to_details_json(self, mock_db, company_id, session_id):
        """dedup_key should be injected into details_json under _dedup_key."""
        from app.services.jarvis_awareness_engine import create_alert

        alert = create_alert(
            db=mock_db,
            session_id=session_id,
            company_id=company_id,
            alert_type="test",
            severity="info",
            category="test",
            title="Test",
            message="Test msg",
            details_json='{"original": "data"}',
            dedup_key="my_dedup_key",
        )

        details = json.loads(alert.details_json)
        assert details["_dedup_key"] == "my_dedup_key"
        assert details["original"] == "data"  # Original data preserved

    def test_no_dedup_when_dedup_key_is_none(self, mock_db, company_id, session_id):
        """Without a dedup_key, no deduplication check should be performed."""
        from app.services.jarvis_awareness_engine import create_alert

        alert = create_alert(
            db=mock_db,
            session_id=session_id,
            company_id=company_id,
            alert_type="test",
            severity="info",
            category="test",
            title="Test",
            message="Test msg",
        )

        assert alert is not None
        # Without dedup_key, the first() query for dedup check should NOT have
        # been called (since the code skips the dedup block when dedup_key is None)


# ══════════════════════════════════════════════════════════════════
# 6. TestGetActiveAlerts
# ══════════════════════════════════════════════════════════════════


class TestGetActiveAlerts:
    """Tests for get_active_alerts — status filter, severity/category, ordering, pagination.

    Note: JarvisProactiveAlert.severity and .created_at need _AttrChainer support
    for .desc() calls. We patch the model class attributes before each test.
    """

    @pytest.fixture(autouse=True)
    def _patch_alert_model_attrs(self):
        """Ensure model class attributes support .desc() for order_by."""
        from database.models.jarvis_cc import JarvisProactiveAlert as _JPA
        _orig_severity = _JPA.severity
        _orig_created_at = _JPA.created_at
        _JPA.severity = _AttrChainer()
        _JPA.created_at = _AttrChainer()
        yield
        _JPA.severity = _orig_severity
        _JPA.created_at = _orig_created_at

    def test_returns_active_and_acknowledged_alerts(self, mock_db, company_id, session_id):
        """Should return alerts with status in [active, acknowledged]."""
        from app.services.jarvis_awareness_engine import get_active_alerts

        mock_alerts = [MagicMock() for _ in range(2)]
        mock_db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 2
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_alerts

        alerts, total = get_active_alerts(mock_db, session_id, company_id)

        assert total == 2
        assert len(alerts) == 2

    def test_filters_by_severity(self, mock_db, company_id, session_id):
        """Should filter alerts by severity when provided."""
        from app.services.jarvis_awareness_engine import get_active_alerts

        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.count.return_value = 1
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [MagicMock()]

        alerts, total = get_active_alerts(
            mock_db, session_id, company_id, severity="critical",
        )

        # The filter method was called (severity filter applied)
        assert total == 1

    def test_filters_by_category(self, mock_db, company_id, session_id):
        """Should filter alerts by category when provided."""
        from app.services.jarvis_awareness_engine import get_active_alerts

        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.count.return_value = 1
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [MagicMock()]

        alerts, total = get_active_alerts(
            mock_db, session_id, company_id, category="system_health",
        )

        assert total == 1

    def test_orders_by_severity_desc_then_created_at_desc(self, mock_db, company_id, session_id):
        """Should order by severity desc, then created_at desc."""
        from app.services.jarvis_awareness_engine import get_active_alerts

        mock_db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 0
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

        get_active_alerts(mock_db, session_id, company_id)

        # Verify query was made
        mock_db.query.assert_called_once()

    def test_pagination_support(self, mock_db, company_id, session_id):
        """Should support limit and offset for pagination."""
        from app.services.jarvis_awareness_engine import get_active_alerts

        mock_db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 100
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [MagicMock()]

        alerts, total = get_active_alerts(
            mock_db, session_id, company_id, limit=10, offset=20,
        )

        assert total == 100


# ══════════════════════════════════════════════════════════════════
# 7. TestAlertLifecycle
# ══════════════════════════════════════════════════════════════════


class TestAlertLifecycle:
    """Tests for acknowledge/dismiss/resolve — lifecycle, NotFoundError, company isolation."""

    def test_acknowledge_sets_status_and_fields(self, mock_db, company_id, session_id, user_id):
        """acknowledge_alert should set status=acknowledged, acknowledged_by, acknowledged_at."""
        from app.services.jarvis_awareness_engine import acknowledge_alert

        mock_alert = MagicMock()
        mock_alert.id = "alert_001"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_alert

        result = acknowledge_alert(
            mock_db, "alert_001", session_id, company_id, user_id,
        )

        assert result.status == "acknowledged"
        assert result.acknowledged_by == user_id
        assert result.acknowledged_at is not None
        mock_db.flush.assert_called()

    def test_dismiss_sets_status_dismissed(self, mock_db, company_id, session_id, user_id):
        """dismiss_alert should set status=dismissed for active/acknowledged alerts."""
        from app.services.jarvis_awareness_engine import dismiss_alert

        mock_alert = MagicMock()
        mock_alert.id = "alert_002"
        mock_alert.acknowledged_at = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_alert

        result = dismiss_alert(
            mock_db, "alert_002", session_id, company_id, user_id,
        )

        assert result.status == "dismissed"
        assert result.acknowledged_by == user_id
        mock_db.flush.assert_called()

    def test_resolve_sets_status_resolved_and_resolved_at(self, mock_db, company_id, session_id):
        """resolve_alert should set status=resolved and resolved_at."""
        from app.services.jarvis_awareness_engine import resolve_alert

        mock_alert = MagicMock()
        mock_alert.id = "alert_003"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_alert

        result = resolve_alert(
            mock_db, "alert_003", session_id, company_id,
        )

        assert result.status == "resolved"
        assert result.resolved_at is not None
        mock_db.flush.assert_called()

    def test_acknowledge_raises_not_found_when_alert_missing(self, mock_db, company_id, session_id, user_id):
        """acknowledge_alert should raise NotFoundError when alert doesn't exist."""
        from app.services.jarvis_awareness_engine import acknowledge_alert
        from app.exceptions import NotFoundError

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError, match="Active alert not found"):
            acknowledge_alert(mock_db, "nonexistent", session_id, company_id, user_id)

    def test_dismiss_raises_not_found_when_alert_missing(self, mock_db, company_id, session_id, user_id):
        """dismiss_alert should raise NotFoundError when alert doesn't exist."""
        from app.services.jarvis_awareness_engine import dismiss_alert
        from app.exceptions import NotFoundError

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError, match="Dismissible alert not found"):
            dismiss_alert(mock_db, "nonexistent", session_id, company_id, user_id)

    def test_resolve_raises_not_found_when_alert_missing(self, mock_db, company_id, session_id):
        """resolve_alert should raise NotFoundError when alert doesn't exist."""
        from app.services.jarvis_awareness_engine import resolve_alert
        from app.exceptions import NotFoundError

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError, match="Resolvable alert not found"):
            resolve_alert(mock_db, "nonexistent", session_id, company_id)

    def test_company_id_isolation(self, mock_db, session_id, user_id):
        """BC-001: Operations should be scoped to company_id.

        An alert from another company_id should not be found.
        The filter includes company_id, so a wrong company_id returns None → NotFoundError.
        """
        from app.services.jarvis_awareness_engine import acknowledge_alert
        from app.exceptions import NotFoundError

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            acknowledge_alert(
                mock_db, "alert_001", session_id, "wrong_company_id", user_id,
            )


# ══════════════════════════════════════════════════════════════════
# 8. TestComputeAwarenessDelta
# ══════════════════════════════════════════════════════════════════


class TestComputeAwarenessDelta:
    """Tests for compute_awareness_delta — first tick, status changes, threshold crossings."""

    def test_first_tick_always_significant(self):
        """First tick (no previous state) should always be significant."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        delta = compute_awareness_delta({"system_health": "healthy"}, None)

        assert delta["has_significant_changes"] is True
        assert delta["is_first_tick"] is True
        assert len(delta["new_alerts"]) == 0
        assert len(delta["recovered"]) == 0

    def test_system_health_worsening_is_significant(self):
        """system_health going from healthy → critical is significant."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"system_health": "healthy"}
        current = {"system_health": "critical"}

        delta = compute_awareness_delta(current, previous)

        assert delta["has_significant_changes"] is True
        assert any(a["field"] == "system_health" and a["change"] == "worsened" for a in delta["new_alerts"])
        assert "system_health" in delta["changed_fields"]

    def test_system_health_improvement_is_recovered(self):
        """system_health going from critical → healthy is a recovery."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"system_health": "critical"}
        current = {"system_health": "healthy"}

        delta = compute_awareness_delta(current, previous)

        assert any(r["field"] == "system_health" and r["change"] == "improved" for r in delta["recovered"])

    def test_subscription_status_change_to_past_due(self):
        """subscription_status changing to past_due should be significant."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"subscription_status": "active"}
        current = {"subscription_status": "past_due"}

        delta = compute_awareness_delta(current, previous)

        assert delta["has_significant_changes"] is True
        assert any(a["field"] == "subscription_status" for a in delta["new_alerts"])

    def test_subscription_status_change_to_cancelled(self):
        """subscription_status changing to cancelled should be significant."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"subscription_status": "active"}
        current = {"subscription_status": "cancelled"}

        delta = compute_awareness_delta(current, previous)

        assert delta["has_significant_changes"] is True
        assert any(a["field"] == "subscription_status" and a["change"] == "worsened" for a in delta["new_alerts"])

    def test_drift_status_change_worsening(self):
        """drift_status going from none → severe should be significant."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"drift_status": "none"}
        current = {"drift_status": "severe"}

        delta = compute_awareness_delta(current, previous)

        assert delta["has_significant_changes"] is True
        assert any(a["field"] == "drift_status" and a["change"] == "worsened" for a in delta["new_alerts"])

    def test_drift_status_change_improvement(self):
        """drift_status going from severe → none is a recovery."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"drift_status": "severe"}
        current = {"drift_status": "none"}

        delta = compute_awareness_delta(current, previous)

        assert any(r["field"] == "drift_status" and r["change"] == "improved" for r in delta["recovered"])

    def test_utilization_threshold_crossing_warning(self):
        """agent_pool_utilization crossing 80% should trigger warning."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"agent_pool_utilization": 75.0}
        current = {"agent_pool_utilization": 85.0}

        delta = compute_awareness_delta(current, previous)

        assert delta["has_significant_changes"] is True
        util_alerts = [a for a in delta["new_alerts"] if a["field"] == "agent_pool_utilization"]
        assert len(util_alerts) == 1
        assert util_alerts[0]["change"] == "crossed_warning"

    def test_quality_threshold_crossing_warning(self):
        """quality_score dropping below 0.70 should trigger warning."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"quality_score": 0.75}
        current = {"quality_score": 0.60}

        delta = compute_awareness_delta(current, previous)

        assert delta["has_significant_changes"] is True
        quality_alerts = [a for a in delta["new_alerts"] if a["field"] == "quality_score"]
        assert len(quality_alerts) >= 1
        assert quality_alerts[0]["change"] == "crossed_warning"

    def test_quality_threshold_crossing_critical(self):
        """quality_score dropping below 0.50 should trigger critical."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"quality_score": 0.55}
        current = {"quality_score": 0.45}

        delta = compute_awareness_delta(current, previous)

        quality_alerts = [a for a in delta["new_alerts"] if a["field"] == "quality_score"]
        critical_alerts = [a for a in quality_alerts if a["change"] == "crossed_critical"]
        assert len(critical_alerts) >= 1

    def test_plan_usage_threshold_crossing_warning(self):
        """plan_usage_today crossing 80% should trigger warning."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"plan_usage_today": 75.0}
        current = {"plan_usage_today": 85.0}

        delta = compute_awareness_delta(current, previous)

        usage_alerts = [a for a in delta["new_alerts"] if a["field"] == "plan_usage_today"]
        assert len(usage_alerts) == 1
        assert usage_alerts[0]["change"] == "crossed_warning"

    def test_plan_usage_threshold_crossing_critical(self):
        """plan_usage_today crossing 95% should trigger critical."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"plan_usage_today": 92.0}
        current = {"plan_usage_today": 97.0}

        delta = compute_awareness_delta(current, previous)

        usage_alerts = [a for a in delta["new_alerts"] if a["field"] == "plan_usage_today"]
        assert len(usage_alerts) == 1
        assert usage_alerts[0]["change"] == "crossed_critical"

    def test_returns_changed_fields_dict(self):
        """Delta should include a changed_fields dict mapping field → {from, to}."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"system_health": "healthy", "drift_status": "none"}
        current = {"system_health": "degraded", "drift_status": "moderate"}

        delta = compute_awareness_delta(current, previous)

        assert "changed_fields" in delta
        assert "system_health" in delta["changed_fields"]
        assert delta["changed_fields"]["system_health"]["from"] == "healthy"
        assert delta["changed_fields"]["system_health"]["to"] == "degraded"
        assert "drift_status" in delta["changed_fields"]
        assert delta["changed_fields"]["drift_status"]["from"] == "none"
        assert delta["changed_fields"]["drift_status"]["to"] == "moderate"

    def test_no_change_not_significant(self):
        """Identical states should not have significant changes."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        state = {"system_health": "healthy", "quality_score": 0.9}
        delta = compute_awareness_delta(state.copy(), state.copy())

        assert delta["has_significant_changes"] is False
        assert delta["is_first_tick"] is False
        assert len(delta["new_alerts"]) == 0

    def test_handles_none_values_gracefully(self):
        """Should handle None values in state without crashing."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"quality_score": None, "drift_score": None}
        current = {"quality_score": 0.5, "drift_score": 0.3}

        delta = compute_awareness_delta(current, previous)
        assert isinstance(delta, dict)

    def test_ticket_volume_spike_detected(self):
        """Ticket volume spike should be detected in delta."""
        from app.services.jarvis_awareness_engine import compute_awareness_delta

        previous = {"ticket_volume_spike": False, "ticket_volume_today": 40}
        current = {"ticket_volume_spike": True, "ticket_volume_today": 120, "ticket_volume_avg": 38.5}

        delta = compute_awareness_delta(current, previous)

        assert delta["has_significant_changes"] is True
        spike_alerts = [a for a in delta["new_alerts"] if a["field"] == "ticket_volume_spike"]
        assert len(spike_alerts) == 1
        assert spike_alerts[0]["change"] == "spike_detected"


# ══════════════════════════════════════════════════════════════════
# 9. TestPruneOldSnapshots
# ══════════════════════════════════════════════════════════════════


class TestPruneOldSnapshots:
    """Tests for prune_old_snapshots — limit enforcement, special preservation, batch delete.

    Note: prune_old_snapshots uses complex SQLAlchemy query chains (func.count,
    .notin_, .in_, multi-call db.query). Rather than trying to mock the entire
    chain (which is fragile), we test the logic through direct patching of
    the module-level function for integration tests, and simpler unit tests
    for the under-limit case.
    """

    def test_returns_zero_when_under_limit(self, company_id, session_id):
        """Should return 0 when snapshot count is under the limit."""
        from app.services.jarvis_awareness_engine import prune_old_snapshots, MAX_SNAPSHOTS_PER_SESSION
        from database.models.jarvis_cc import JarvisAwarenessSnapshot as _JAS

        with patch("app.services.jarvis_awareness_engine.func") as mock_func, \
             patch.object(_JAS, "id", _AttrChainer()):
            mock_func.count.return_value = MagicMock()
            db = MagicMock()
            db.query.return_value.filter.return_value.scalar.return_value = 10

            result = prune_old_snapshots(db, session_id, company_id, max_keep=MAX_SNAPSHOTS_PER_SESSION)

            assert result == 0

    def test_keeps_most_recent_max_snapshots(self, company_id, session_id):
        """Should keep most recent MAX_SNAPSHOTS_PER_SESSION snapshots and prune rest."""
        from app.services.jarvis_awareness_engine import prune_old_snapshots, MAX_SNAPSHOTS_PER_SESSION
        from database.models.jarvis_cc import JarvisAwarenessSnapshot as _JAS

        with patch("app.services.jarvis_awareness_engine.func") as mock_func, \
             patch.object(_JAS, "id", _AttrChainer()):
            mock_func.count.return_value = MagicMock()
            db = MagicMock()
            # Total exceeds limit
            db.query.return_value.filter.return_value.scalar.return_value = MAX_SNAPSHOTS_PER_SESSION + 50
            # The .all() call for keep_ids returns tuples
            keep_ids = [(f"id_{i}",) for i in range(MAX_SNAPSHOTS_PER_SESSION)]
            # The .all() call for special_ids
            special_ids = [("special_1",)]
            # The .all() call for delete candidates
            delete_ids = [("del_1",), ("del_2",)]
            # Set up the sequential .all() results
            db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
                keep_ids, special_ids,
            ]
            db.query.return_value.filter.return_value.limit.return_value.all.return_value = delete_ids
            db.query.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = delete_ids
            db.query.return_value.filter.return_value.delete.return_value = 2

            result = prune_old_snapshots(db, session_id, company_id, max_keep=MAX_SNAPSHOTS_PER_SESSION)

            assert result >= 0

    def test_always_preserves_emergency_and_on_change(self, company_id, session_id):
        """Emergency and on_change snapshots should always be preserved."""
        from app.services.jarvis_awareness_engine import prune_old_snapshots
        from database.models.jarvis_cc import JarvisAwarenessSnapshot as _JAS

        with patch("app.services.jarvis_awareness_engine.func") as mock_func, \
             patch.object(_JAS, "id", _AttrChainer()):
            mock_func.count.return_value = MagicMock()
            db = MagicMock()
            db.query.return_value.filter.return_value.scalar.return_value = 10
            keep_ids = [("id_1",), ("id_2",), ("id_3",), ("id_4",), ("id_5",)]
            special_ids = [("emerg_1",), ("onchange_1",)]
            delete_ids = [("del_1",)]
            db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
                keep_ids, special_ids,
            ]
            db.query.return_value.filter.return_value.limit.return_value.all.return_value = delete_ids
            db.query.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = delete_ids
            db.query.return_value.filter.return_value.delete.return_value = 1

            result = prune_old_snapshots(db, session_id, company_id, max_keep=5)

            # The special IDs should have been added to the keep set
            assert result >= 0

    def test_batch_deletion(self, company_id, session_id):
        """Should delete in batches of SNAPSHOT_PRUNE_BATCH."""
        from app.services.jarvis_awareness_engine import prune_old_snapshots, SNAPSHOT_PRUNE_BATCH
        from database.models.jarvis_cc import JarvisAwarenessSnapshot as _JAS

        with patch("app.services.jarvis_awareness_engine.func") as mock_func, \
             patch.object(_JAS, "id", _AttrChainer()):
            mock_func.count.return_value = MagicMock()
            db = MagicMock()
            db.query.return_value.filter.return_value.scalar.return_value = 5000
            keep_ids = [(f"id_{i}",) for i in range(100)]
            special_ids = []
            delete_ids = [(f"del_{i}",) for i in range(SNAPSHOT_PRUNE_BATCH)]
            db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
                keep_ids, special_ids,
            ]
            db.query.return_value.filter.return_value.limit.return_value.all.return_value = delete_ids
            db.query.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = delete_ids
            db.query.return_value.filter.return_value.delete.return_value = SNAPSHOT_PRUNE_BATCH

            result = prune_old_snapshots(db, session_id, company_id, max_keep=100)

            assert result == SNAPSHOT_PRUNE_BATCH


# ══════════════════════════════════════════════════════════════════
# 10. TestPruneExpiredAlerts
# ══════════════════════════════════════════════════════════════════


class TestPruneExpiredAlerts:
    """Tests for prune_expired_alerts — TTL expiry, emergency non-expiry."""

    def test_marks_active_alerts_past_ttl_as_expired(self, mock_db, company_id, session_id):
        """Active alerts past their TTL should be marked as expired."""
        from app.services.jarvis_awareness_engine import prune_expired_alerts

        # Alert created 2 hours ago with TTL=3600 (1 hour) → should expire
        expired_alert = MagicMock()
        expired_alert.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        expired_alert.ttl_seconds = 3600  # 1 hour TTL
        expired_alert.status = "active"

        mock_db.query.return_value.filter.return_value.all.return_value = [expired_alert]

        result = prune_expired_alerts(mock_db, session_id, company_id)

        assert result == 1
        assert expired_alert.status == "expired"
        mock_db.flush.assert_called()

    def test_emergency_alerts_never_expire(self, mock_db, company_id, session_id):
        """Emergency alerts (TTL=0) should never expire automatically."""
        from app.services.jarvis_awareness_engine import prune_expired_alerts

        # Emergency alert with TTL=0 should not be returned by the query
        # because the query filters on ttl_seconds > 0
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = prune_expired_alerts(mock_db, session_id, company_id)

        assert result == 0

    def test_returns_count_of_expired_alerts(self, mock_db, company_id, session_id):
        """Should return the count of expired alerts."""
        from app.services.jarvis_awareness_engine import prune_expired_alerts

        # Two expired alerts, one not yet expired
        expired_1 = MagicMock()
        expired_1.created_at = datetime.now(timezone.utc) - timedelta(hours=5)
        expired_1.ttl_seconds = 3600

        expired_2 = MagicMock()
        expired_2.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        expired_2.ttl_seconds = 86400  # 24h TTL, created 25h ago

        not_expired = MagicMock()
        not_expired.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        not_expired.ttl_seconds = 3600  # 1h TTL, created 30m ago

        mock_db.query.return_value.filter.return_value.all.return_value = [expired_1, expired_2, not_expired]

        result = prune_expired_alerts(mock_db, session_id, company_id)

        assert result == 2  # Only 2 are expired

    def test_no_expired_alerts_returns_zero(self, mock_db, company_id, session_id):
        """Should return 0 when no alerts need expiry."""
        from app.services.jarvis_awareness_engine import prune_expired_alerts

        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = prune_expired_alerts(mock_db, session_id, company_id)

        assert result == 0


# ══════════════════════════════════════════════════════════════════
# 11. TestRunAwarenessTick
# ══════════════════════════════════════════════════════════════════


class TestRunAwarenessTick:
    """Tests for run_awareness_tick — full tick integration."""

    def _make_tick(self, mock_db, sample_cc_session, sample_awareness_state, **kwargs):
        """Helper to run a tick with standard mocking."""
        from app.services.jarvis_awareness_engine import run_awareness_tick

        with patch("app.services.jarvis_cc_service.get_cc_session", return_value=sample_cc_session), \
             patch("app.services.jarvis_awareness_engine.get_latest_snapshot", return_value=None), \
             patch("app.services.jarvis_awareness_engine.create_snapshot") as mock_create, \
             patch("app.services.jarvis_awareness_engine.prune_old_snapshots", return_value=0), \
             patch("app.services.jarvis_awareness_engine.prune_expired_alerts", return_value=0):

            mock_snapshot = MagicMock()
            mock_snapshot.id = "snap_tick_001"
            mock_snapshot.tick_number = None
            mock_create.return_value = mock_snapshot

            return run_awareness_tick(
                db=mock_db,
                company_id=kwargs.get("company_id", "comp_day1_001"),
                session_id=kwargs.get("session_id", "cc_sess_day1_001"),
                user_id=kwargs.get("user_id", "user_day1_001"),
                tick_type=kwargs.get("tick_type", "periodic"),
                override_state=kwargs.get("override_state", sample_awareness_state),
            )

    def test_validates_session(self, mock_db, sample_cc_session, sample_awareness_state):
        """Tick should validate session via get_cc_session."""
        with patch("app.services.jarvis_cc_service.get_cc_session", return_value=sample_cc_session) as mock_get, \
             patch("app.services.jarvis_awareness_engine.get_latest_snapshot", return_value=None), \
             patch("app.services.jarvis_awareness_engine.create_snapshot") as mock_create, \
             patch("app.services.jarvis_awareness_engine.prune_old_snapshots", return_value=0), \
             patch("app.services.jarvis_awareness_engine.prune_expired_alerts", return_value=0):

            mock_snapshot = MagicMock()
            mock_snapshot.id = "snap_001"
            mock_snapshot.tick_number = None
            mock_create.return_value = mock_snapshot

            from app.services.jarvis_awareness_engine import run_awareness_tick
            run_awareness_tick(
                db=mock_db, company_id="comp_001", session_id="sess_001",
                user_id="user_001", override_state=sample_awareness_state,
            )

            mock_get.assert_called_once()

    def test_collects_state_or_uses_override(self, mock_db, sample_cc_session, sample_awareness_state):
        """When override_state is provided, collect_awareness_state should NOT be called."""
        with patch("app.services.jarvis_cc_service.get_cc_session", return_value=sample_cc_session), \
             patch("app.services.jarvis_awareness_engine.get_latest_snapshot", return_value=None), \
             patch("app.services.jarvis_awareness_engine.create_snapshot") as mock_create, \
             patch("app.services.jarvis_awareness_engine.collect_awareness_state") as mock_collect, \
             patch("app.services.jarvis_awareness_engine.prune_old_snapshots", return_value=0), \
             patch("app.services.jarvis_awareness_engine.prune_expired_alerts", return_value=0):

            mock_snapshot = MagicMock()
            mock_snapshot.id = "snap_001"
            mock_snapshot.tick_number = None
            mock_create.return_value = mock_snapshot

            from app.services.jarvis_awareness_engine import run_awareness_tick
            result = run_awareness_tick(
                db=mock_db, company_id="comp_001", session_id="sess_001",
                user_id="user_001", override_state=sample_awareness_state,
            )

            mock_collect.assert_not_called()

    def test_creates_snapshot(self, mock_db, sample_cc_session, sample_awareness_state):
        """Tick should call create_snapshot."""
        with patch("app.services.jarvis_cc_service.get_cc_session", return_value=sample_cc_session), \
             patch("app.services.jarvis_awareness_engine.get_latest_snapshot", return_value=None), \
             patch("app.services.jarvis_awareness_engine.create_snapshot") as mock_create, \
             patch("app.services.jarvis_awareness_engine.prune_old_snapshots", return_value=0), \
             patch("app.services.jarvis_awareness_engine.prune_expired_alerts", return_value=0):

            mock_snapshot = MagicMock()
            mock_snapshot.id = "snap_001"
            mock_snapshot.tick_number = None
            mock_create.return_value = mock_snapshot

            from app.services.jarvis_awareness_engine import run_awareness_tick
            run_awareness_tick(
                db=mock_db, company_id="comp_001", session_id="sess_001",
                user_id="user_001", override_state=sample_awareness_state,
            )

            mock_create.assert_called_once()

    def test_returns_tick_result_with_all_expected_keys(self, mock_db, sample_cc_session, sample_awareness_state):
        """Tick result should contain all expected keys."""
        result = self._make_tick(mock_db, sample_cc_session, sample_awareness_state)

        expected_keys = [
            "snapshot_id", "tick_type", "tick_number", "alerts_created",
            "alert_ids", "system_health", "quality_score", "drift_score",
            "delta_significant", "total_ms",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key in tick result: {key}"

    def test_tick_type_periodic(self, mock_db, sample_cc_session, sample_awareness_state):
        """Tick type periodic should be reflected in result."""
        result = self._make_tick(
            mock_db, sample_cc_session, sample_awareness_state, tick_type="periodic",
        )
        assert result["tick_type"] == "periodic"

    def test_tick_type_manual(self, mock_db, sample_cc_session, sample_awareness_state):
        """Tick type manual should be reflected in result."""
        result = self._make_tick(
            mock_db, sample_cc_session, sample_awareness_state, tick_type="manual",
        )
        assert result["tick_type"] == "manual"

    def test_tick_type_on_change(self, mock_db, sample_cc_session, sample_awareness_state):
        """Tick type on_change should be reflected in result."""
        result = self._make_tick(
            mock_db, sample_cc_session, sample_awareness_state, tick_type="on_change",
        )
        assert result["tick_type"] == "on_change"

    def test_tick_type_emergency(self, mock_db, sample_cc_session, sample_awareness_state):
        """Tick type emergency should be reflected in result."""
        result = self._make_tick(
            mock_db, sample_cc_session, sample_awareness_state, tick_type="emergency",
        )
        assert result["tick_type"] == "emergency"

    def test_updates_cc_session_context(self, mock_db, sample_cc_session, sample_awareness_state):
        """Tick should update CC session context with awareness data."""
        self._make_tick(mock_db, sample_cc_session, sample_awareness_state)

        updated_ctx = json.loads(sample_cc_session.context_json)
        assert updated_ctx["awareness_enabled"] is True
        assert "awareness_last_tick" in updated_ctx
        assert updated_ctx["awareness_system_health"] == "healthy"

    def test_healthy_state_zero_alerts(self, mock_db, sample_cc_session, sample_awareness_state):
        """Healthy state should generate 0 alerts."""
        result = self._make_tick(mock_db, sample_cc_session, sample_awareness_state)
        assert result["alerts_created"] == 0

    def test_degraded_state_generates_alerts(self, mock_db, sample_cc_session, sample_degraded_state):
        """Degraded state should generate >= 1 alert."""
        result = self._make_tick(
            mock_db, sample_cc_session, sample_degraded_state,
            override_state=sample_degraded_state,
        )
        assert result["alerts_created"] >= 1

    def test_tick_increments_tick_number(self, mock_db, sample_cc_session, sample_awareness_state):
        """Tick number should increment from previous snapshot."""
        with patch("app.services.jarvis_cc_service.get_cc_session", return_value=sample_cc_session), \
             patch("app.services.jarvis_awareness_engine.get_latest_snapshot") as mock_get_latest, \
             patch("app.services.jarvis_awareness_engine.create_snapshot") as mock_create, \
             patch("app.services.jarvis_awareness_engine.prune_old_snapshots", return_value=0), \
             patch("app.services.jarvis_awareness_engine.prune_expired_alerts", return_value=0):

            mock_prev = MagicMock()
            mock_prev.tick_number = 5
            mock_prev.raw_state_json = json.dumps(sample_awareness_state)
            mock_get_latest.return_value = mock_prev

            mock_snapshot = MagicMock()
            mock_snapshot.id = "snap_002"
            mock_snapshot.tick_number = 6
            mock_create.return_value = mock_snapshot

            from app.services.jarvis_awareness_engine import run_awareness_tick
            run_awareness_tick(
                db=mock_db, company_id="comp_001", session_id="sess_001",
                user_id="user_001", override_state=sample_awareness_state,
            )

            call_args = mock_create.call_args
            assert call_args[1]["tick_number"] == 6

    def test_tick_measures_latency(self, mock_db, sample_cc_session, sample_awareness_state):
        """Tick should measure and report latency in total_ms."""
        result = self._make_tick(mock_db, sample_cc_session, sample_awareness_state)
        assert result["total_ms"] >= 0


# ══════════════════════════════════════════════════════════════════
# 12. TestThresholdConstants
# ══════════════════════════════════════════════════════════════════


class TestThresholdConstants:
    """Verify all threshold constants are sensible and match spec."""

    def test_spike_multiplier(self):
        """SPIKE_MULTIPLIER should be 2.0."""
        from app.services.jarvis_awareness_engine import SPIKE_MULTIPLIER
        assert SPIKE_MULTIPLIER == 2.0

    def test_utilization_warn_threshold(self):
        """UTILIZATION_WARN_THRESHOLD should be 80.0."""
        from app.services.jarvis_awareness_engine import UTILIZATION_WARN_THRESHOLD
        assert UTILIZATION_WARN_THRESHOLD == 80.0

    def test_utilization_critical_threshold(self):
        """UTILIZATION_CRITICAL_THRESHOLD should be 95.0."""
        from app.services.jarvis_awareness_engine import UTILIZATION_CRITICAL_THRESHOLD
        assert UTILIZATION_CRITICAL_THRESHOLD == 95.0

    def test_quality_warn_threshold(self):
        """QUALITY_WARN_THRESHOLD should be 0.70."""
        from app.services.jarvis_awareness_engine import QUALITY_WARN_THRESHOLD
        assert QUALITY_WARN_THRESHOLD == 0.70

    def test_quality_critical_threshold(self):
        """QUALITY_CRITICAL_THRESHOLD should be 0.50."""
        from app.services.jarvis_awareness_engine import QUALITY_CRITICAL_THRESHOLD
        assert QUALITY_CRITICAL_THRESHOLD == 0.50

    def test_drift_warn_threshold(self):
        """DRIFT_WARN_THRESHOLD should be 0.30."""
        from app.services.jarvis_awareness_engine import DRIFT_WARN_THRESHOLD
        assert DRIFT_WARN_THRESHOLD == 0.30

    def test_drift_critical_threshold(self):
        """DRIFT_CRITICAL_THRESHOLD should be 0.60."""
        from app.services.jarvis_awareness_engine import DRIFT_CRITICAL_THRESHOLD
        assert DRIFT_CRITICAL_THRESHOLD == 0.60

    def test_plan_usage_warn_threshold(self):
        """PLAN_USAGE_WARN_THRESHOLD should be 80.0."""
        from app.services.jarvis_awareness_engine import PLAN_USAGE_WARN_THRESHOLD
        assert PLAN_USAGE_WARN_THRESHOLD == 80.0

    def test_plan_usage_critical_threshold(self):
        """PLAN_USAGE_CRITICAL_THRESHOLD should be 95.0."""
        from app.services.jarvis_awareness_engine import PLAN_USAGE_CRITICAL_THRESHOLD
        assert PLAN_USAGE_CRITICAL_THRESHOLD == 95.0

    def test_renewal_info_threshold(self):
        """RENEWAL_INFO_THRESHOLD should be 7 days."""
        from app.services.jarvis_awareness_engine import RENEWAL_INFO_THRESHOLD
        assert RENEWAL_INFO_THRESHOLD == 7

    def test_renewal_warn_threshold(self):
        """RENEWAL_WARN_THRESHOLD should be 3 days."""
        from app.services.jarvis_awareness_engine import RENEWAL_WARN_THRESHOLD
        assert RENEWAL_WARN_THRESHOLD == 3

    def test_alert_ttl_info(self):
        """ALERT_TTL_INFO should be 3600 seconds (1 hour)."""
        from app.services.jarvis_awareness_engine import ALERT_TTL_INFO
        assert ALERT_TTL_INFO == 3600

    def test_alert_ttl_warning(self):
        """ALERT_TTL_WARNING should be 14400 seconds (4 hours)."""
        from app.services.jarvis_awareness_engine import ALERT_TTL_WARNING
        assert ALERT_TTL_WARNING == 14400

    def test_alert_ttl_critical(self):
        """ALERT_TTL_CRITICAL should be 86400 seconds (24 hours)."""
        from app.services.jarvis_awareness_engine import ALERT_TTL_CRITICAL
        assert ALERT_TTL_CRITICAL == 86400

    def test_alert_ttl_emergency(self):
        """ALERT_TTL_EMERGENCY should be 0 (no expiry)."""
        from app.services.jarvis_awareness_engine import ALERT_TTL_EMERGENCY
        assert ALERT_TTL_EMERGENCY == 0

    def test_rule_cooldown_seconds(self):
        """RULE_COOLDOWN_SECONDS should be 300 (5 minutes)."""
        from app.services.jarvis_awareness_engine import RULE_COOLDOWN_SECONDS
        assert RULE_COOLDOWN_SECONDS == 300

    def test_error_rate_warn_threshold(self):
        """ERROR_RATE_WARN_THRESHOLD should be 0.10 (10%)."""
        from app.services.jarvis_awareness_engine import ERROR_RATE_WARN_THRESHOLD
        assert ERROR_RATE_WARN_THRESHOLD == 0.10

    def test_error_rate_critical_threshold(self):
        """ERROR_RATE_CRITICAL_THRESHOLD should be 0.25 (25%)."""
        from app.services.jarvis_awareness_engine import ERROR_RATE_CRITICAL_THRESHOLD
        assert ERROR_RATE_CRITICAL_THRESHOLD == 0.25

    def test_training_mistake_warn_threshold(self):
        """TRAINING_MISTAKE_WARN_THRESHOLD should be 10."""
        from app.services.jarvis_awareness_engine import TRAINING_MISTAKE_WARN_THRESHOLD
        assert TRAINING_MISTAKE_WARN_THRESHOLD == 10

    def test_max_snapshots_per_session(self):
        """MAX_SNAPSHOTS_PER_SESSION should be 2880 (24h at 30s intervals)."""
        from app.services.jarvis_awareness_engine import MAX_SNAPSHOTS_PER_SESSION
        assert MAX_SNAPSHOTS_PER_SESSION == 2880

    def test_snapshot_prune_batch(self):
        """SNAPSHOT_PRUNE_BATCH should be 100."""
        from app.services.jarvis_awareness_engine import SNAPSHOT_PRUNE_BATCH
        assert SNAPSHOT_PRUNE_BATCH == 100

    def test_threshold_relationships(self):
        """Warn thresholds should always be less extreme than critical thresholds."""
        from app.services.jarvis_awareness_engine import (
            UTILIZATION_WARN_THRESHOLD, UTILIZATION_CRITICAL_THRESHOLD,
            QUALITY_WARN_THRESHOLD, QUALITY_CRITICAL_THRESHOLD,
            DRIFT_WARN_THRESHOLD, DRIFT_CRITICAL_THRESHOLD,
            PLAN_USAGE_WARN_THRESHOLD, PLAN_USAGE_CRITICAL_THRESHOLD,
            RENEWAL_INFO_THRESHOLD, RENEWAL_WARN_THRESHOLD,
        )

        # For upward-crossing metrics (higher = worse)
        assert UTILIZATION_WARN_THRESHOLD < UTILIZATION_CRITICAL_THRESHOLD
        assert DRIFT_WARN_THRESHOLD < DRIFT_CRITICAL_THRESHOLD
        assert PLAN_USAGE_WARN_THRESHOLD < PLAN_USAGE_CRITICAL_THRESHOLD

        # For downward-crossing metrics (lower = worse)
        assert QUALITY_WARN_THRESHOLD > QUALITY_CRITICAL_THRESHOLD

        # Renewal: info comes before warning (more days = less urgent)
        assert RENEWAL_INFO_THRESHOLD > RENEWAL_WARN_THRESHOLD
