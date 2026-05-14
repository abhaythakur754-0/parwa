"""
Unit Tests for PARWA Jarvis Awareness API Endpoints (Phase 2.2)

Tests cover:
  1. Awareness schema validation — tick, snapshot, alert, delta schemas
  2. Response helpers — _snapshot_to_response, _alert_to_response, _safe_parse_json
  3. Endpoint logic — tick, snapshot, snapshots, alerts, acknowledge, dismiss, resolve, delta
  4. Edge cases — no company, no snapshot, invalid tick type, alert not found
  5. Router registration — 16 routes including 8 new awareness routes

All tests mock the service layer directly and avoid importing through
the app.api.__init__ chain (which requires many runtime dependencies).
Instead, we import the jarvis_cc module directly after mocking the
dependency chain.
"""

from __future__ import annotations

import json
import sys
import types
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict
from unittest.mock import MagicMock, patch


# ========================================================================
# FIXTURES
# ========================================================================


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    user = MagicMock()
    user.id = "user_001"
    user.company_id = "company_001"
    user.is_active = True
    return user


@pytest.fixture
def mock_user_no_company():
    """Create a mock user with no company."""
    user = MagicMock()
    user.id = "user_002"
    user.company_id = None
    user.is_active = True
    return user


@pytest.fixture
def mock_db():
    """Create a mock SQLAlchemy session."""
    return MagicMock()


@pytest.fixture
def sample_snapshot():
    """Create a sample JarvisAwarenessSnapshot."""
    snap = MagicMock()
    snap.id = "snap_001"
    snap.session_id = "cc_session_001"
    snap.company_id = "company_001"
    snap.snapshot_type = "periodic"
    snap.tick_number = 42
    snap.current_plan = "pro"
    snap.plan_usage_today = Decimal("65.50")
    snap.subscription_status = "active"
    snap.days_until_renewal = 14
    snap.system_health = "healthy"
    snap.channel_health_json = json.dumps({"email": "healthy", "sms": "degraded"})
    snap.active_alerts_count = 2
    snap.active_alerts_json = json.dumps([
        {"alert_id": "alert_001", "severity": "warning", "message": "High volume"},
    ])
    snap.ticket_volume_today = 87
    snap.ticket_volume_avg = Decimal("45.30")
    snap.ticket_volume_spike = True
    snap.active_agents = 3
    snap.agent_pool_capacity = 5
    snap.agent_pool_utilization = Decimal("60.00")
    snap.training_running = False
    snap.training_mistake_count = 2
    snap.training_model_version = "v2.3"
    snap.drift_status = "slight"
    snap.drift_score = Decimal("0.15")
    snap.quality_score = Decimal("0.82")
    snap.quality_alerts_json = json.dumps([])
    snap.last_5_errors_json = json.dumps([
        {"error": "timeout", "node": "classify", "timestamp": "2026-01-01T00:00:00Z"},
    ])
    snap.raw_state_json = json.dumps({
        "system_health": "healthy",
        "quality_score": 0.82,
        "drift_score": 0.15,
        "ticket_volume_today": 87,
        "ticket_volume_spike": True,
    })
    snap.created_at = datetime.now(timezone.utc)
    return snap


@pytest.fixture
def sample_snapshot_minimal():
    """Create a minimal snapshot with many None/defaults."""
    snap = MagicMock()
    snap.id = "snap_002"
    snap.session_id = "cc_session_001"
    snap.company_id = "company_001"
    snap.snapshot_type = None
    snap.tick_number = None
    snap.current_plan = None
    snap.plan_usage_today = None
    snap.subscription_status = None
    snap.days_until_renewal = None
    snap.system_health = None
    snap.channel_health_json = None
    snap.active_alerts_count = None
    snap.active_alerts_json = None
    snap.ticket_volume_today = None
    snap.ticket_volume_avg = None
    snap.ticket_volume_spike = None
    snap.active_agents = None
    snap.agent_pool_capacity = None
    snap.agent_pool_utilization = None
    snap.training_running = None
    snap.training_mistake_count = None
    snap.training_model_version = None
    snap.drift_status = None
    snap.drift_score = None
    snap.quality_score = None
    snap.quality_alerts_json = None
    snap.last_5_errors_json = None
    snap.raw_state_json = None
    snap.created_at = None
    return snap


@pytest.fixture
def sample_alert_active():
    """Create a sample active JarvisProactiveAlert."""
    alert = MagicMock()
    alert.id = "alert_001"
    alert.session_id = "cc_session_001"
    alert.company_id = "company_001"
    alert.alert_type = "ticket_volume_spike"
    alert.severity = "warning"
    alert.category = "ticket_volume"
    alert.title = "Ticket Volume Spike Detected"
    alert.message = "Today's ticket volume (87) is 2x the 7-day average (43)."
    alert.details_json = json.dumps({
        "today": 87,
        "avg": 43,
        "multiplier": 2.0,
        "_dedup_key": "ticket_volume_spike",
    })
    alert.status = "active"
    alert.action_required = True
    alert.action_url = "/dashboard/tickets"
    alert.ttl_seconds = 14400
    alert.related_snapshot_id = "snap_001"
    alert.acknowledged_by = None
    alert.acknowledged_at = None
    alert.resolved_at = None
    alert.created_at = datetime.now(timezone.utc)
    alert.updated_at = datetime.now(timezone.utc)
    return alert


@pytest.fixture
def sample_alert_acknowledged():
    """Create a sample acknowledged alert."""
    alert = MagicMock()
    alert.id = "alert_002"
    alert.session_id = "cc_session_001"
    alert.company_id = "company_001"
    alert.alert_type = "quality_drop"
    alert.severity = "critical"
    alert.category = "quality"
    alert.title = "Quality Score Below Critical Threshold"
    alert.message = "Quality score dropped to 0.45, below the 0.50 critical threshold."
    alert.details_json = json.dumps({"quality_score": 0.45, "threshold": 0.50})
    alert.status = "acknowledged"
    alert.action_required = True
    alert.action_url = None
    alert.ttl_seconds = 86400
    alert.related_snapshot_id = "snap_001"
    alert.acknowledged_by = "user_001"
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.resolved_at = None
    alert.created_at = datetime.now(timezone.utc)
    alert.updated_at = datetime.now(timezone.utc)
    return alert


@pytest.fixture
def sample_tick_result():
    """Create a sample tick result dict."""
    return {
        "snapshot_id": "snap_001",
        "tick_type": "manual",
        "tick_number": 42,
        "alerts_created": 2,
        "alert_ids": ["alert_001", "alert_002"],
        "system_health": "healthy",
        "quality_score": 0.82,
        "drift_score": 0.15,
        "delta_significant": True,
        "total_ms": 45.3,
    }


# ========================================================================
# HELPER: Import jarvis_cc module bypassing __init__
# ========================================================================


def _import_jarvis_cc_module():
    """Import the jarvis_cc module directly, bypassing app.api.__init__.

    This avoids the dependency chain in __init__.py that requires
    jose, pyotp, etc. We create mock modules for the deps chain.

    Always reloads the module from disk to pick up code changes.
    """
    # Pre-import required submodules
    import app.schemas.jarvis_cc
    import app.services.jarvis_cc_service
    import app.services.jarvis_awareness_engine
    import app.exceptions

    # Mock the app.api.deps module
    if "app.api.deps" not in sys.modules:
        deps_mock = types.ModuleType("app.api.deps")
        deps_mock.get_current_user = lambda: None
        sys.modules["app.api.deps"] = deps_mock

    # Mock database.base
    if "database.base" not in sys.modules:
        db_mock = types.ModuleType("database.base")
        db_mock.get_db = lambda: None
        sys.modules["database.base"] = db_mock

    # Mock database.models.core
    if "database.models.core" not in sys.modules:
        core_mock = types.ModuleType("database.models.core")
        core_mock.User = type("User", (), {})
        sys.modules["database.models.core"] = core_mock

    # Always reload from disk to pick up code changes
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "app.api.jarvis_cc",
        "/home/z/my-project/parwa/backend/app/api/jarvis_cc.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["app.api.jarvis_cc"] = module
    spec.loader.exec_module(module)
    return module


# ========================================================================
# AWARENESS SCHEMA VALIDATION TESTS
# ========================================================================


class TestJarvisAwarenessTickRequest:
    """Tests for JarvisAwarenessTickRequest schema."""

    def test_valid_tick_request(self):
        from app.schemas.jarvis_cc import JarvisAwarenessTickRequest
        req = JarvisAwarenessTickRequest(session_id="cc_session_001")
        assert req.session_id == "cc_session_001"
        assert req.tick_type == "manual"  # default

    def test_valid_tick_with_type(self):
        from app.schemas.jarvis_cc import JarvisAwarenessTickRequest
        req = JarvisAwarenessTickRequest(
            session_id="cc_session_001",
            tick_type="emergency",
        )
        assert req.tick_type == "emergency"

    def test_rejects_invalid_tick_type(self):
        from app.schemas.jarvis_cc import JarvisAwarenessTickRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            JarvisAwarenessTickRequest(
                session_id="cc_session_001",
                tick_type="invalid_type",
            )

    def test_all_valid_tick_types(self):
        from app.schemas.jarvis_cc import JarvisAwarenessTickRequest
        for tick_type in ("periodic", "on_change", "manual", "emergency"):
            req = JarvisAwarenessTickRequest(
                session_id="cc_session_001",
                tick_type=tick_type,
            )
            assert req.tick_type == tick_type


class TestJarvisAwarenessTickResponse:
    """Tests for JarvisAwarenessTickResponse schema."""

    def test_valid_response(self):
        from app.schemas.jarvis_cc import JarvisAwarenessTickResponse
        resp = JarvisAwarenessTickResponse(
            snapshot_id="snap_001",
            tick_type="manual",
            tick_number=1,
        )
        assert resp.snapshot_id == "snap_001"
        assert resp.alerts_created == 0
        assert resp.delta_significant is False

    def test_full_response(self):
        from app.schemas.jarvis_cc import JarvisAwarenessTickResponse
        resp = JarvisAwarenessTickResponse(
            snapshot_id="snap_001",
            tick_type="emergency",
            tick_number=5,
            alerts_created=3,
            alert_ids=["a1", "a2", "a3"],
            system_health="critical",
            quality_score=0.45,
            drift_score=0.65,
            delta_significant=True,
            total_ms=120.5,
        )
        assert resp.alert_ids == ["a1", "a2", "a3"]
        assert resp.system_health == "critical"
        assert resp.total_ms == 120.5


class TestJarvisAwarenessSnapshotResponse:
    """Tests for JarvisAwarenessSnapshotResponse schema."""

    def test_valid_snapshot_response(self):
        from app.schemas.jarvis_cc import JarvisAwarenessSnapshotResponse
        resp = JarvisAwarenessSnapshotResponse(
            id="snap_001",
            session_id="cc_session_001",
            company_id="company_001",
        )
        assert resp.id == "snap_001"
        assert resp.system_health == "unknown"
        assert resp.snapshot_type == "periodic"

    def test_full_snapshot_response(self):
        from app.schemas.jarvis_cc import JarvisAwarenessSnapshotResponse
        resp = JarvisAwarenessSnapshotResponse(
            id="snap_001",
            session_id="cc_session_001",
            company_id="company_001",
            snapshot_type="emergency",
            tick_number=99,
            current_plan="pro",
            plan_usage_today=85.0,
            subscription_status="active",
            days_until_renewal=5,
            system_health="degraded",
            channel_health={"email": "healthy", "sms": "degraded"},
            active_alerts_count=3,
            active_alerts=[{"severity": "warning"}],
            ticket_volume_today=100,
            ticket_volume_avg=50.0,
            ticket_volume_spike=True,
            active_agents=5,
            agent_pool_capacity=5,
            agent_pool_utilization=100.0,
            training_running=True,
            training_mistake_count=5,
            training_model_version="v3.0",
            drift_status="moderate",
            drift_score=0.45,
            quality_score=0.60,
            quality_alerts=[{"metric": "empathy", "threshold": 0.8}],
            last_5_errors=[{"error": "timeout"}],
            created_at="2026-01-01T00:00:00+00:00",
        )
        assert resp.ticket_volume_spike is True
        assert resp.agent_pool_utilization == 100.0
        assert resp.drift_status == "moderate"


class TestJarvisProactiveAlertResponse:
    """Tests for JarvisProactiveAlertResponse schema."""

    def test_valid_alert_response(self):
        from app.schemas.jarvis_cc import JarvisProactiveAlertResponse
        resp = JarvisProactiveAlertResponse(
            id="alert_001",
            session_id="cc_session_001",
            company_id="company_001",
            alert_type="ticket_volume_spike",
            title="Volume Spike",
            message="Ticket volume is high",
        )
        assert resp.id == "alert_001"
        assert resp.severity == "info"
        assert resp.status == "active"
        assert resp.action_required is False

    def test_alert_with_full_lifecycle(self):
        from app.schemas.jarvis_cc import JarvisProactiveAlertResponse
        resp = JarvisProactiveAlertResponse(
            id="alert_001",
            session_id="cc_session_001",
            company_id="company_001",
            alert_type="quality_drop",
            severity="critical",
            category="quality",
            title="Quality Critical",
            message="Quality below threshold",
            details={"quality_score": 0.45},
            status="acknowledged",
            action_required=True,
            ttl_seconds=86400,
            acknowledged_by="user_001",
            acknowledged_at="2026-01-01T12:00:00+00:00",
            created_at="2026-01-01T11:00:00+00:00",
        )
        assert resp.status == "acknowledged"
        assert resp.acknowledged_by == "user_001"
        assert resp.details["quality_score"] == 0.45


class TestJarvisAlertRequestSchemas:
    """Tests for alert lifecycle request schemas."""

    def test_acknowledge_request(self):
        from app.schemas.jarvis_cc import JarvisAlertAcknowledgeRequest
        req = JarvisAlertAcknowledgeRequest(alert_id="alert_001")
        assert req.alert_id == "alert_001"

    def test_dismiss_request(self):
        from app.schemas.jarvis_cc import JarvisAlertDismissRequest
        req = JarvisAlertDismissRequest(alert_id="alert_001")
        assert req.alert_id == "alert_001"

    def test_resolve_request(self):
        from app.schemas.jarvis_cc import JarvisAlertResolveRequest
        req = JarvisAlertResolveRequest(alert_id="alert_001")
        assert req.alert_id == "alert_001"


class TestJarvisAwarenessDeltaResponse:
    """Tests for JarvisAwarenessDeltaResponse schema."""

    def test_default_delta(self):
        from app.schemas.jarvis_cc import JarvisAwarenessDeltaResponse
        delta = JarvisAwarenessDeltaResponse()
        assert delta.has_significant_changes is False
        assert delta.is_first_tick is False
        assert delta.changed_fields == {}
        assert delta.new_alerts == []
        assert delta.recovered == []

    def test_first_tick_delta(self):
        from app.schemas.jarvis_cc import JarvisAwarenessDeltaResponse
        delta = JarvisAwarenessDeltaResponse(
            has_significant_changes=True,
            is_first_tick=True,
        )
        assert delta.is_first_tick is True

    def test_delta_with_changes(self):
        from app.schemas.jarvis_cc import JarvisAwarenessDeltaResponse
        delta = JarvisAwarenessDeltaResponse(
            changed_fields={"system_health": {"from": "healthy", "to": "degraded"}},
            has_significant_changes=True,
            new_alerts=[{"field": "system_health", "change": "worsened"}],
            recovered=[{"field": "quality_score", "change": "recovered_above_warning"}],
            is_first_tick=False,
        )
        assert "system_health" in delta.changed_fields
        assert len(delta.new_alerts) == 1
        assert len(delta.recovered) == 1


# ========================================================================
# RESPONSE HELPER TESTS
# ========================================================================


class TestSafeParseJson:
    """Tests for _safe_parse_json helper."""

    def test_parses_valid_json(self):
        cc = _import_jarvis_cc_module()
        result = cc._safe_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parses_list_json(self):
        cc = _import_jarvis_cc_module()
        result = cc._safe_parse_json('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_handles_invalid_json(self):
        cc = _import_jarvis_cc_module()
        result = cc._safe_parse_json("not json")
        assert result == {}

    def test_handles_none(self):
        cc = _import_jarvis_cc_module()
        result = cc._safe_parse_json(None)
        assert result == {}

    def test_handles_empty_string(self):
        cc = _import_jarvis_cc_module()
        result = cc._safe_parse_json("")
        assert result == {}


class TestSnapshotToResponse:
    """Tests for _snapshot_to_response helper."""

    def test_converts_full_snapshot(self, sample_snapshot):
        cc = _import_jarvis_cc_module()
        resp = cc._snapshot_to_response(sample_snapshot)
        assert resp.id == "snap_001"
        assert resp.session_id == "cc_session_001"
        assert resp.company_id == "company_001"
        assert resp.snapshot_type == "periodic"
        assert resp.tick_number == 42
        assert resp.current_plan == "pro"
        assert resp.plan_usage_today == 65.50
        assert resp.subscription_status == "active"
        assert resp.days_until_renewal == 14
        assert resp.system_health == "healthy"
        assert resp.channel_health == {"email": "healthy", "sms": "degraded"}
        assert resp.active_alerts_count == 2
        assert len(resp.active_alerts) == 1
        assert resp.ticket_volume_today == 87
        assert resp.ticket_volume_avg == 45.30
        assert resp.ticket_volume_spike is True
        assert resp.active_agents == 3
        assert resp.agent_pool_capacity == 5
        assert resp.agent_pool_utilization == 60.00
        assert resp.training_running is False
        assert resp.training_mistake_count == 2
        assert resp.training_model_version == "v2.3"
        assert resp.drift_status == "slight"
        assert resp.drift_score == 0.15
        assert resp.quality_score == 0.82
        assert resp.quality_alerts == []
        assert len(resp.last_5_errors) == 1
        assert resp.created_at is not None

    def test_converts_minimal_snapshot(self, sample_snapshot_minimal):
        cc = _import_jarvis_cc_module()
        resp = cc._snapshot_to_response(sample_snapshot_minimal)
        assert resp.id == "snap_002"
        assert resp.snapshot_type == "periodic"  # default
        assert resp.system_health == "unknown"  # default
        assert resp.plan_usage_today is None
        assert resp.channel_health == {}
        assert resp.active_alerts == []
        assert resp.ticket_volume_today == 0
        assert resp.ticket_volume_spike is False
        assert resp.active_agents == 0
        assert resp.drift_status == "none"
        assert resp.quality_score is None
        assert resp.quality_alerts == []
        assert resp.last_5_errors == []
        assert resp.created_at is None

    def test_handles_invalid_channel_health_json(self):
        cc = _import_jarvis_cc_module()
        snap = MagicMock()
        snap.id = "snap_003"
        snap.session_id = "cc_session_001"
        snap.company_id = "company_001"
        snap.snapshot_type = "periodic"
        snap.tick_number = 1
        snap.channel_health_json = "not json"
        snap.active_alerts_json = None
        snap.quality_alerts_json = "broken"
        snap.last_5_errors_json = None
        snap.current_plan = None
        snap.plan_usage_today = None
        snap.subscription_status = None
        snap.days_until_renewal = None
        snap.system_health = "healthy"
        snap.active_alerts_count = 0
        snap.ticket_volume_today = 0
        snap.ticket_volume_avg = None
        snap.ticket_volume_spike = False
        snap.active_agents = 0
        snap.agent_pool_capacity = 0
        snap.agent_pool_utilization = None
        snap.training_running = False
        snap.training_mistake_count = 0
        snap.training_model_version = None
        snap.drift_status = None
        snap.drift_score = None
        snap.quality_score = None
        snap.created_at = None
        resp = cc._snapshot_to_response(snap)
        assert resp.channel_health == {}
        assert resp.active_alerts == []
        assert resp.quality_alerts == []

    def test_handles_list_channel_health_gracefully(self):
        """If channel_health_json contains a list, it should be handled."""
        cc = _import_jarvis_cc_module()
        snap = MagicMock()
        snap.id = "snap_004"
        snap.session_id = "cc_session_001"
        snap.company_id = "company_001"
        snap.snapshot_type = "periodic"
        snap.tick_number = 1
        snap.channel_health_json = json.dumps([1, 2, 3])  # Not a dict
        snap.active_alerts_json = json.dumps([1, 2, 3])    # Not a list of alerts
        snap.quality_alerts_json = json.dumps("string")     # Not a list
        snap.last_5_errors_json = json.dumps(42)            # Not a list
        snap.current_plan = None
        snap.plan_usage_today = None
        snap.subscription_status = None
        snap.days_until_renewal = None
        snap.system_health = None
        snap.active_alerts_count = None
        snap.ticket_volume_today = None
        snap.ticket_volume_avg = None
        snap.ticket_volume_spike = None
        snap.active_agents = None
        snap.agent_pool_capacity = None
        snap.agent_pool_utilization = None
        snap.training_running = None
        snap.training_mistake_count = None
        snap.training_model_version = None
        snap.drift_status = None
        snap.drift_score = None
        snap.quality_score = None
        snap.created_at = None
        resp = cc._snapshot_to_response(snap)
        # channel_health is a list not dict, so isinstance check returns {}
        assert resp.channel_health == {}
        # active_alerts is [1,2,3] but items are not dicts, so validation returns []
        assert resp.active_alerts == []
        # quality_alerts and last_5_errors also fail validation
        assert resp.quality_alerts == []
        assert resp.last_5_errors == []


class TestAlertToResponse:
    """Tests for _alert_to_response helper."""

    def test_converts_active_alert(self, sample_alert_active):
        cc = _import_jarvis_cc_module()
        resp = cc._alert_to_response(sample_alert_active)
        assert resp.id == "alert_001"
        assert resp.session_id == "cc_session_001"
        assert resp.company_id == "company_001"
        assert resp.alert_type == "ticket_volume_spike"
        assert resp.severity == "warning"
        assert resp.category == "ticket_volume"
        assert resp.title == "Ticket Volume Spike Detected"
        assert resp.status == "active"
        assert resp.action_required is True
        assert resp.action_url == "/dashboard/tickets"
        assert resp.ttl_seconds == 14400
        assert resp.acknowledged_by is None
        assert resp.acknowledged_at is None
        assert resp.resolved_at is None
        assert resp.details["today"] == 87
        assert resp.details["_dedup_key"] == "ticket_volume_spike"
        assert resp.created_at is not None

    def test_converts_acknowledged_alert(self, sample_alert_acknowledged):
        cc = _import_jarvis_cc_module()
        resp = cc._alert_to_response(sample_alert_acknowledged)
        assert resp.id == "alert_002"
        assert resp.status == "acknowledged"
        assert resp.severity == "critical"
        assert resp.acknowledged_by == "user_001"
        assert resp.acknowledged_at is not None
        assert resp.details["quality_score"] == 0.45

    def test_handles_invalid_details_json(self):
        cc = _import_jarvis_cc_module()
        alert = MagicMock()
        alert.id = "alert_003"
        alert.session_id = "cc_session_001"
        alert.company_id = "company_001"
        alert.alert_type = "test"
        alert.severity = "info"
        alert.category = "system_health"
        alert.title = "Test"
        alert.message = "Test alert"
        alert.details_json = "not json"
        alert.status = "active"
        alert.action_required = False
        alert.action_url = None
        alert.ttl_seconds = 0
        alert.related_snapshot_id = None
        alert.acknowledged_by = None
        alert.acknowledged_at = None
        alert.resolved_at = None
        alert.created_at = None
        alert.updated_at = None
        resp = cc._alert_to_response(alert)
        assert resp.details == {}

    def test_handles_none_fields(self):
        cc = _import_jarvis_cc_module()
        alert = MagicMock()
        alert.id = "alert_004"
        alert.session_id = "cc_session_001"
        alert.company_id = "company_001"
        alert.alert_type = "test"
        alert.severity = None
        alert.category = None
        alert.title = "Test"
        alert.message = "Test"
        alert.details_json = None
        alert.status = None
        alert.action_required = None
        alert.action_url = None
        alert.ttl_seconds = None
        alert.related_snapshot_id = None
        alert.acknowledged_by = None
        alert.acknowledged_at = None
        alert.resolved_at = None
        alert.created_at = None
        alert.updated_at = None
        resp = cc._alert_to_response(alert)
        assert resp.severity == "info"      # default
        assert resp.category == "system_health"  # default
        assert resp.status == "active"      # default
        assert resp.action_required is False  # default
        assert resp.ttl_seconds == 0        # default
        assert resp.details == {}


# ========================================================================
# AWARENESS TICK ENDPOINT TESTS
# ========================================================================


class TestAwarenessTickEndpoint:
    """Tests for awareness_tick endpoint."""

    def test_tick_successfully(self, mock_user, sample_tick_result):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.run_awareness_tick.return_value = sample_tick_result

            from app.schemas.jarvis_cc import JarvisAwarenessTickRequest
            body = JarvisAwarenessTickRequest(
                session_id="cc_session_001",
                tick_type="manual",
            )
            result = cc.awareness_tick(body=body, user=mock_user, db=MagicMock())

        assert result.snapshot_id == "snap_001"
        assert result.tick_number == 42
        assert result.alerts_created == 2
        assert result.system_health == "healthy"

    def test_tick_with_emergency_type(self, mock_user, sample_tick_result):
        cc = _import_jarvis_cc_module()
        sample_tick_result["tick_type"] = "emergency"

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.run_awareness_tick.return_value = sample_tick_result

            from app.schemas.jarvis_cc import JarvisAwarenessTickRequest
            body = JarvisAwarenessTickRequest(
                session_id="cc_session_001",
                tick_type="emergency",
            )
            result = cc.awareness_tick(body=body, user=mock_user, db=MagicMock())

        assert result.tick_type == "emergency"

    def test_tick_no_company(self, mock_user_no_company):
        cc = _import_jarvis_cc_module()

        from app.schemas.jarvis_cc import JarvisAwarenessTickRequest
        body = JarvisAwarenessTickRequest(session_id="cc_session_001")
        result = cc.awareness_tick(
            body=body, user=mock_user_no_company, db=MagicMock(),
        )

        assert isinstance(result, dict)
        assert result["error"]["code"] == "VALIDATION_ERROR"

    def test_tick_internal_error(self, mock_user):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.run_awareness_tick.side_effect = Exception("DB connection lost")

            from app.schemas.jarvis_cc import JarvisAwarenessTickRequest
            body = JarvisAwarenessTickRequest(session_id="cc_session_001")
            result = cc.awareness_tick(body=body, user=mock_user, db=MagicMock())

        assert isinstance(result, dict)
        assert result["error"]["code"] == "INTERNAL_ERROR"

    def test_tick_passes_correct_params(self, mock_user, sample_tick_result):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.run_awareness_tick.return_value = sample_tick_result

            from app.schemas.jarvis_cc import JarvisAwarenessTickRequest
            body = JarvisAwarenessTickRequest(
                session_id="cc_session_001",
                tick_type="periodic",
            )
            cc.awareness_tick(body=body, user=mock_user, db=MagicMock())

        call_kwargs = mock_engine.run_awareness_tick.call_args[1]
        assert call_kwargs["company_id"] == "company_001"
        assert call_kwargs["session_id"] == "cc_session_001"
        assert call_kwargs["user_id"] == "user_001"
        assert call_kwargs["tick_type"] == "periodic"


# ========================================================================
# AWARENESS SNAPSHOT ENDPOINT TESTS
# ========================================================================


class TestGetAwarenessSnapshotEndpoint:
    """Tests for get_awareness_snapshot endpoint."""

    def test_gets_latest_snapshot(self, mock_user, sample_snapshot):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_latest_snapshot.return_value = sample_snapshot

            result = cc.get_awareness_snapshot(
                session_id="cc_session_001", user=mock_user, db=MagicMock(),
            )

        assert result.id == "snap_001"
        assert result.system_health == "healthy"
        assert result.quality_score == 0.82

    def test_returns_not_found_when_no_snapshot(self, mock_user):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_latest_snapshot.return_value = None

            result = cc.get_awareness_snapshot(
                session_id="cc_session_001", user=mock_user, db=MagicMock(),
            )

        assert isinstance(result, dict)
        assert result["error"]["code"] == "NOT_FOUND"

    def test_no_company_returns_error(self, mock_user_no_company):
        cc = _import_jarvis_cc_module()

        result = cc.get_awareness_snapshot(
            session_id="cc_session_001",
            user=mock_user_no_company,
            db=MagicMock(),
        )

        assert isinstance(result, dict)
        assert result["error"]["code"] == "VALIDATION_ERROR"

    def test_internal_error(self, mock_user):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_latest_snapshot.side_effect = Exception("DB error")

            result = cc.get_awareness_snapshot(
                session_id="cc_session_001", user=mock_user, db=MagicMock(),
            )

        assert isinstance(result, dict)
        assert result["error"]["code"] == "INTERNAL_ERROR"


class TestGetAwarenessSnapshotsEndpoint:
    """Tests for get_awareness_snapshots (paginated) endpoint."""

    def test_gets_paginated_snapshots(self, mock_user, sample_snapshot):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_snapshot_history.return_value = (
                [sample_snapshot], 1,
            )

            result = cc.get_awareness_snapshots(
                session_id="cc_session_001", user=mock_user, db=MagicMock(),
            )

        assert result.total == 1
        assert len(result.snapshots) == 1
        assert result.has_more is False

    def test_pagination_with_more(self, mock_user, sample_snapshot):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_snapshot_history.return_value = (
                [sample_snapshot], 150,
            )

            result = cc.get_awareness_snapshots(
                session_id="cc_session_001",
                limit=50,
                offset=0,
                user=mock_user,
                db=MagicMock(),
            )

        assert result.total == 150
        assert result.has_more is True  # 0 + 50 < 150

    def test_pagination_without_more(self, mock_user, sample_snapshot):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_snapshot_history.return_value = (
                [sample_snapshot], 50,
            )

            result = cc.get_awareness_snapshots(
                session_id="cc_session_001",
                limit=50,
                offset=0,
                user=mock_user,
                db=MagicMock(),
            )

        assert result.has_more is False  # 0 + 50 == 50, not < 50

    def test_no_company_returns_error(self, mock_user_no_company):
        cc = _import_jarvis_cc_module()

        result = cc.get_awareness_snapshots(
            session_id="cc_session_001",
            user=mock_user_no_company,
            db=MagicMock(),
        )

        assert isinstance(result, dict)
        assert result["error"]["code"] == "VALIDATION_ERROR"

    def test_empty_snapshots(self, mock_user):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_snapshot_history.return_value = ([], 0)

            result = cc.get_awareness_snapshots(
                session_id="cc_session_001", user=mock_user, db=MagicMock(),
            )

        assert result.total == 0
        assert result.snapshots == []
        assert result.has_more is False


# ========================================================================
# AWARENESS ALERTS ENDPOINT TESTS
# ========================================================================


class TestGetAwarenessAlertsEndpoint:
    """Tests for get_awareness_alerts endpoint."""

    def test_gets_active_alerts(self, mock_user, sample_alert_active):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_active_alerts.return_value = (
                [sample_alert_active], 1,
            )

            result = cc.get_awareness_alerts(
                session_id="cc_session_001", user=mock_user, db=MagicMock(),
            )

        assert result.total == 1
        assert len(result.alerts) == 1
        assert result.alerts[0].alert_type == "ticket_volume_spike"

    def test_filters_by_severity(self, mock_user, sample_alert_active):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_active_alerts.return_value = (
                [sample_alert_active], 1,
            )

            result = cc.get_awareness_alerts(
                session_id="cc_session_001",
                severity="warning",
                user=mock_user,
                db=MagicMock(),
            )

        # Verify the filter was passed to the engine
        call_kwargs = mock_engine.get_active_alerts.call_args[1]
        assert call_kwargs["severity"] == "warning"

    def test_filters_by_category(self, mock_user, sample_alert_active):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_active_alerts.return_value = (
                [sample_alert_active], 1,
            )

            result = cc.get_awareness_alerts(
                session_id="cc_session_001",
                category="ticket_volume",
                user=mock_user,
                db=MagicMock(),
            )

        call_kwargs = mock_engine.get_active_alerts.call_args[1]
        assert call_kwargs["category"] == "ticket_volume"

    def test_no_company_returns_error(self, mock_user_no_company):
        cc = _import_jarvis_cc_module()

        result = cc.get_awareness_alerts(
            session_id="cc_session_001",
            user=mock_user_no_company,
            db=MagicMock(),
        )

        assert isinstance(result, dict)
        assert result["error"]["code"] == "VALIDATION_ERROR"

    def test_empty_alerts(self, mock_user):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_active_alerts.return_value = ([], 0)

            result = cc.get_awareness_alerts(
                session_id="cc_session_001", user=mock_user, db=MagicMock(),
            )

        assert result.total == 0
        assert result.alerts == []

    def test_multiple_alerts(self, mock_user, sample_alert_active, sample_alert_acknowledged):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_active_alerts.return_value = (
                [sample_alert_acknowledged, sample_alert_active], 2,
            )

            result = cc.get_awareness_alerts(
                session_id="cc_session_001", user=mock_user, db=MagicMock(),
            )

        assert result.total == 2
        assert len(result.alerts) == 2


# ========================================================================
# ALERT LIFECYCLE ENDPOINT TESTS
# ========================================================================


class TestAcknowledgeAlertEndpoint:
    """Tests for acknowledge_alert endpoint."""

    def test_acknowledges_active_alert(self, mock_user, sample_alert_active):
        cc = _import_jarvis_cc_module()
        # Simulate acknowledgment — status changes
        acknowledged = MagicMock()
        acknowledged.id = "alert_001"
        acknowledged.session_id = "cc_session_001"
        acknowledged.company_id = "company_001"
        acknowledged.alert_type = "ticket_volume_spike"
        acknowledged.severity = "warning"
        acknowledged.category = "ticket_volume"
        acknowledged.title = "Ticket Volume Spike Detected"
        acknowledged.message = "Today's ticket volume is high."
        acknowledged.details_json = "{}"
        acknowledged.status = "acknowledged"
        acknowledged.action_required = True
        acknowledged.action_url = "/dashboard/tickets"
        acknowledged.ttl_seconds = 14400
        acknowledged.related_snapshot_id = "snap_001"
        acknowledged.acknowledged_by = "user_001"
        acknowledged.acknowledged_at = datetime.now(timezone.utc)
        acknowledged.resolved_at = None
        acknowledged.created_at = datetime.now(timezone.utc)
        acknowledged.updated_at = datetime.now(timezone.utc)

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.acknowledge_alert.return_value = acknowledged

            from app.schemas.jarvis_cc import JarvisAlertAcknowledgeRequest
            body = JarvisAlertAcknowledgeRequest(alert_id="alert_001")
            result = cc.acknowledge_alert(
                body=body,
                session_id="cc_session_001",
                user=mock_user,
                db=MagicMock(),
            )

        assert result.status == "acknowledged"
        assert result.acknowledged_by == "user_001"

    def test_no_company_returns_error(self, mock_user_no_company):
        cc = _import_jarvis_cc_module()

        from app.schemas.jarvis_cc import JarvisAlertAcknowledgeRequest
        body = JarvisAlertAcknowledgeRequest(alert_id="alert_001")
        result = cc.acknowledge_alert(
            body=body,
            session_id="cc_session_001",
            user=mock_user_no_company,
            db=MagicMock(),
        )

        assert isinstance(result, dict)
        assert result["error"]["code"] == "VALIDATION_ERROR"

    def test_passes_correct_params(self, mock_user, sample_alert_active):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.acknowledge_alert.return_value = sample_alert_active

            from app.schemas.jarvis_cc import JarvisAlertAcknowledgeRequest
            body = JarvisAlertAcknowledgeRequest(alert_id="alert_001")
            cc.acknowledge_alert(
                body=body,
                session_id="cc_session_001",
                user=mock_user,
                db=MagicMock(),
            )

        call_kwargs = mock_engine.acknowledge_alert.call_args[1]
        assert call_kwargs["alert_id"] == "alert_001"
        assert call_kwargs["session_id"] == "cc_session_001"
        assert call_kwargs["company_id"] == "company_001"
        assert call_kwargs["user_id"] == "user_001"

    def test_internal_error(self, mock_user):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.acknowledge_alert.side_effect = Exception("DB error")

            from app.schemas.jarvis_cc import JarvisAlertAcknowledgeRequest
            body = JarvisAlertAcknowledgeRequest(alert_id="alert_001")
            result = cc.acknowledge_alert(
                body=body,
                session_id="cc_session_001",
                user=mock_user,
                db=MagicMock(),
            )

        assert isinstance(result, dict)
        assert result["error"]["code"] == "INTERNAL_ERROR"


class TestDismissAlertEndpoint:
    """Tests for dismiss_alert endpoint."""

    def test_dismisses_alert(self, mock_user, sample_alert_active):
        cc = _import_jarvis_cc_module()
        dismissed = MagicMock()
        dismissed.id = "alert_001"
        dismissed.session_id = "cc_session_001"
        dismissed.company_id = "company_001"
        dismissed.alert_type = "ticket_volume_spike"
        dismissed.severity = "warning"
        dismissed.category = "ticket_volume"
        dismissed.title = "Ticket Volume Spike Detected"
        dismissed.message = "High volume"
        dismissed.details_json = "{}"
        dismissed.status = "dismissed"
        dismissed.action_required = False
        dismissed.action_url = None
        dismissed.ttl_seconds = 14400
        dismissed.related_snapshot_id = None
        dismissed.acknowledged_by = "user_001"
        dismissed.acknowledged_at = datetime.now(timezone.utc)
        dismissed.resolved_at = None
        dismissed.created_at = datetime.now(timezone.utc)
        dismissed.updated_at = datetime.now(timezone.utc)

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.dismiss_alert.return_value = dismissed

            from app.schemas.jarvis_cc import JarvisAlertDismissRequest
            body = JarvisAlertDismissRequest(alert_id="alert_001")
            result = cc.dismiss_alert(
                body=body,
                session_id="cc_session_001",
                user=mock_user,
                db=MagicMock(),
            )

        assert result.status == "dismissed"

    def test_no_company_returns_error(self, mock_user_no_company):
        cc = _import_jarvis_cc_module()

        from app.schemas.jarvis_cc import JarvisAlertDismissRequest
        body = JarvisAlertDismissRequest(alert_id="alert_001")
        result = cc.dismiss_alert(
            body=body,
            session_id="cc_session_001",
            user=mock_user_no_company,
            db=MagicMock(),
        )

        assert isinstance(result, dict)
        assert result["error"]["code"] == "VALIDATION_ERROR"


class TestResolveAlertEndpoint:
    """Tests for resolve_alert endpoint."""

    def test_resolves_alert(self, mock_user, sample_alert_active):
        cc = _import_jarvis_cc_module()
        resolved = MagicMock()
        resolved.id = "alert_001"
        resolved.session_id = "cc_session_001"
        resolved.company_id = "company_001"
        resolved.alert_type = "ticket_volume_spike"
        resolved.severity = "warning"
        resolved.category = "ticket_volume"
        resolved.title = "Ticket Volume Spike Detected"
        resolved.message = "High volume"
        resolved.details_json = "{}"
        resolved.status = "resolved"
        resolved.action_required = False
        resolved.action_url = None
        resolved.ttl_seconds = 14400
        resolved.related_snapshot_id = None
        resolved.acknowledged_by = None
        resolved.acknowledged_at = None
        resolved.resolved_at = datetime.now(timezone.utc)
        resolved.created_at = datetime.now(timezone.utc)
        resolved.updated_at = datetime.now(timezone.utc)

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.resolve_alert.return_value = resolved

            from app.schemas.jarvis_cc import JarvisAlertResolveRequest
            body = JarvisAlertResolveRequest(alert_id="alert_001")
            result = cc.resolve_alert(
                body=body,
                session_id="cc_session_001",
                user=mock_user,
                db=MagicMock(),
            )

        assert result.status == "resolved"
        assert result.resolved_at is not None

    def test_no_company_returns_error(self, mock_user_no_company):
        cc = _import_jarvis_cc_module()

        from app.schemas.jarvis_cc import JarvisAlertResolveRequest
        body = JarvisAlertResolveRequest(alert_id="alert_001")
        result = cc.resolve_alert(
            body=body,
            session_id="cc_session_001",
            user=mock_user_no_company,
            db=MagicMock(),
        )

        assert isinstance(result, dict)
        assert result["error"]["code"] == "VALIDATION_ERROR"

    def test_resolve_does_not_require_user_id(self, mock_user, sample_alert_active):
        """Resolve alert doesn't need user_id (system can resolve)."""
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.resolve_alert.return_value = sample_alert_active

            from app.schemas.jarvis_cc import JarvisAlertResolveRequest
            body = JarvisAlertResolveRequest(alert_id="alert_001")
            cc.resolve_alert(
                body=body,
                session_id="cc_session_001",
                user=mock_user,
                db=MagicMock(),
            )

        call_kwargs = mock_engine.resolve_alert.call_args[1]
        assert "user_id" not in call_kwargs  # resolve doesn't take user_id
        assert call_kwargs["alert_id"] == "alert_001"
        assert call_kwargs["session_id"] == "cc_session_001"


# ========================================================================
# AWARENESS DELTA ENDPOINT TESTS
# ========================================================================


class TestGetAwarenessDeltaEndpoint:
    """Tests for get_awareness_delta endpoint."""

    def test_gets_delta_from_two_snapshots(self, mock_user, sample_snapshot):
        cc = _import_jarvis_cc_module()

        # Create two snapshots with different states
        snap_current = MagicMock()
        snap_current.raw_state_json = json.dumps({
            "system_health": "degraded",
            "quality_score": 0.65,
        })
        snap_current.created_at = datetime.now(timezone.utc)

        snap_previous = MagicMock()
        snap_previous.raw_state_json = json.dumps({
            "system_health": "healthy",
            "quality_score": 0.85,
        })
        snap_previous.created_at = datetime.now(timezone.utc)

        delta_result = {
            "changed_fields": {"system_health": {"from": "healthy", "to": "degraded"}},
            "has_significant_changes": True,
            "new_alerts": [{"field": "system_health", "change": "worsened"}],
            "recovered": [],
            "is_first_tick": False,
        }

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_snapshot_history.return_value = (
                [snap_current, snap_previous], 2,
            )
            mock_engine.compute_awareness_delta.return_value = delta_result

            result = cc.get_awareness_delta(
                session_id="cc_session_001", user=mock_user, db=MagicMock(),
            )

        assert result.has_significant_changes is True
        assert "system_health" in result.changed_fields
        assert len(result.new_alerts) == 1
        assert result.is_first_tick is False

    def test_returns_first_tick_when_no_snapshots(self, mock_user):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_snapshot_history.return_value = ([], 0)

            result = cc.get_awareness_delta(
                session_id="cc_session_001", user=mock_user, db=MagicMock(),
            )

        assert result.is_first_tick is True
        assert result.has_significant_changes is True
        assert result.changed_fields == {}

    def test_single_snapshot_treated_as_first_tick(self, mock_user, sample_snapshot):
        cc = _import_jarvis_cc_module()

        delta_result = {
            "changed_fields": {},
            "has_significant_changes": True,
            "new_alerts": [],
            "recovered": [],
            "is_first_tick": True,
        }

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_snapshot_history.return_value = (
                [sample_snapshot], 1,
            )
            mock_engine.compute_awareness_delta.return_value = delta_result

            result = cc.get_awareness_delta(
                session_id="cc_session_001", user=mock_user, db=MagicMock(),
            )

        assert result.is_first_tick is True

    def test_no_company_returns_error(self, mock_user_no_company):
        cc = _import_jarvis_cc_module()

        result = cc.get_awareness_delta(
            session_id="cc_session_001",
            user=mock_user_no_company,
            db=MagicMock(),
        )

        assert isinstance(result, dict)
        assert result["error"]["code"] == "VALIDATION_ERROR"

    def test_internal_error(self, mock_user):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_snapshot_history.side_effect = Exception("DB error")

            result = cc.get_awareness_delta(
                session_id="cc_session_001", user=mock_user, db=MagicMock(),
            )

        assert isinstance(result, dict)
        assert result["error"]["code"] == "INTERNAL_ERROR"


# ========================================================================
# ROUTER REGISTRATION TESTS (Updated for Phase 2.2)
# ========================================================================


class TestAwarenessRouterRegistration:
    """Tests that the CC router includes awareness endpoints."""

    def test_router_has_correct_prefix(self):
        cc = _import_jarvis_cc_module()
        assert cc.router.prefix == "/api/jarvis/cc"

    def test_router_has_sixteen_routes(self):
        cc = _import_jarvis_cc_module()
        route_count = len([r for r in cc.router.routes if hasattr(r, 'path')])
        # 8 original + 8 awareness + additional routes = 16+ routes
        assert route_count >= 16

    def test_awareness_routes_exist(self):
        cc = _import_jarvis_cc_module()
        routes = [route.path for route in cc.router.routes if hasattr(route, 'path')]
        route_suffixes = [r.replace("/api/jarvis/cc", "") for r in routes]

        # Original 8
        assert "/session" in route_suffixes
        assert "/message" in route_suffixes
        assert "/context" in route_suffixes
        assert "/history" in route_suffixes
        assert "/prompt" in route_suffixes
        assert "/session/health" in route_suffixes

        # New 8 awareness routes
        assert "/awareness/tick" in route_suffixes
        assert "/awareness/snapshot" in route_suffixes
        assert "/awareness/snapshots" in route_suffixes
        assert "/awareness/alerts" in route_suffixes
        assert "/awareness/alerts/acknowledge" in route_suffixes
        assert "/awareness/alerts/dismiss" in route_suffixes
        assert "/awareness/alerts/resolve" in route_suffixes
        assert "/awareness/delta" in route_suffixes

    def test_awareness_tick_is_post(self):
        cc = _import_jarvis_cc_module()
        tick_route = None
        for route in cc.router.routes:
            if hasattr(route, 'path') and route.path.endswith("/awareness/tick"):
                tick_route = route
                break
        assert tick_route is not None
        assert tick_route.methods is not None
        assert "POST" in tick_route.methods

    def test_awareness_snapshot_is_get(self):
        cc = _import_jarvis_cc_module()
        for route in cc.router.routes:
            if hasattr(route, 'path') and route.path.endswith("/awareness/snapshot"):
                # Could be /awareness/snapshot or /awareness/snapshots
                if "snapshots" not in route.path:
                    assert "GET" in route.methods
                    break

    def test_awareness_alert_acknowledge_is_post(self):
        cc = _import_jarvis_cc_module()
        for route in cc.router.routes:
            if hasattr(route, 'path') and "acknowledge" in route.path:
                assert "POST" in route.methods
                break


# ========================================================================
# EDGE CASE TESTS
# ========================================================================


class TestAwarenessEdgeCases:
    """Edge case tests for awareness API."""

    def test_tick_with_zero_alerts(self, mock_user):
        cc = _import_jarvis_cc_module()

        tick_result = {
            "snapshot_id": "snap_001",
            "tick_type": "periodic",
            "tick_number": 1,
            "alerts_created": 0,
            "alert_ids": [],
            "system_health": "healthy",
            "quality_score": 0.95,
            "drift_score": 0.05,
            "delta_significant": False,
            "total_ms": 12.5,
        }

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.run_awareness_tick.return_value = tick_result

            from app.schemas.jarvis_cc import JarvisAwarenessTickRequest
            body = JarvisAwarenessTickRequest(session_id="cc_session_001")
            result = cc.awareness_tick(body=body, user=mock_user, db=MagicMock())

        assert result.alerts_created == 0
        assert result.alert_ids == []
        assert result.delta_significant is False

    def test_snapshot_with_decimal_conversions(self, mock_user):
        """Verify Decimal fields are properly converted to float."""
        cc = _import_jarvis_cc_module()
        snap = MagicMock()
        snap.id = "snap_dec"
        snap.session_id = "cc_session_001"
        snap.company_id = "company_001"
        snap.snapshot_type = "periodic"
        snap.tick_number = 1
        snap.current_plan = None
        snap.plan_usage_today = Decimal("95.50")
        snap.subscription_status = None
        snap.days_until_renewal = None
        snap.system_health = "healthy"
        snap.channel_health_json = "{}"
        snap.active_alerts_count = 0
        snap.active_alerts_json = "[]"
        snap.ticket_volume_today = 10
        snap.ticket_volume_avg = Decimal("12.33")
        snap.ticket_volume_spike = False
        snap.active_agents = 2
        snap.agent_pool_capacity = 5
        snap.agent_pool_utilization = Decimal("40.00")
        snap.training_running = False
        snap.training_mistake_count = 0
        snap.training_model_version = None
        snap.drift_status = "none"
        snap.drift_score = Decimal("0.1234")
        snap.quality_score = Decimal("0.8765")
        snap.quality_alerts_json = "[]"
        snap.last_5_errors_json = "[]"
        snap.raw_state_json = "{}"
        snap.created_at = datetime.now(timezone.utc)

        resp = cc._snapshot_to_response(snap)

        # Verify Decimal -> float conversions
        assert isinstance(resp.plan_usage_today, float)
        assert resp.plan_usage_today == 95.50
        assert isinstance(resp.ticket_volume_avg, float)
        assert resp.ticket_volume_avg == 12.33
        assert isinstance(resp.agent_pool_utilization, float)
        assert resp.agent_pool_utilization == 40.00
        assert isinstance(resp.drift_score, float)
        assert resp.drift_score == 0.1234
        assert isinstance(resp.quality_score, float)
        assert resp.quality_score == 0.8765

    def test_delta_with_recovered_fields(self, mock_user, sample_snapshot):
        cc = _import_jarvis_cc_module()

        delta_result = {
            "changed_fields": {"quality_score": {"from": 0.45, "to": 0.85}},
            "has_significant_changes": True,
            "new_alerts": [],
            "recovered": [
                {"field": "quality_score", "change": "recovered_above_warning", "from": 0.45, "to": 0.85},
            ],
            "is_first_tick": False,
        }

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_snapshot_history.return_value = (
                [sample_snapshot], 1,
            )
            mock_engine.compute_awareness_delta.return_value = delta_result

            result = cc.get_awareness_delta(
                session_id="cc_session_001", user=mock_user, db=MagicMock(),
            )

        assert len(result.recovered) == 1
        assert result.recovered[0]["field"] == "quality_score"
        assert result.recovered[0]["change"] == "recovered_above_warning"

    def test_alert_list_pagination(self, mock_user, sample_alert_active):
        cc = _import_jarvis_cc_module()

        # Simulate 75 total alerts but only return 50 (limit)
        alerts = [sample_alert_active] * 50
        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_active_alerts.return_value = (alerts, 75)

            result = cc.get_awareness_alerts(
                session_id="cc_session_001",
                limit=50,
                offset=0,
                user=mock_user,
                db=MagicMock(),
            )

        assert result.total == 75
        assert len(result.alerts) == 50
        assert result.has_more is True  # 0 + 50 < 75

    def test_alert_list_no_more_pages(self, mock_user, sample_alert_active):
        cc = _import_jarvis_cc_module()

        with patch.object(cc, "jarvis_awareness_engine") as mock_engine:
            mock_engine.get_active_alerts.return_value = (
                [sample_alert_active], 1,
            )

            result = cc.get_awareness_alerts(
                session_id="cc_session_001",
                limit=50,
                offset=0,
                user=mock_user,
                db=MagicMock(),
            )

        assert result.has_more is False  # 0 + 50 >= 1
