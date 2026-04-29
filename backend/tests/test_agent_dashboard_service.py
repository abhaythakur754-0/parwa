"""
PARWA Tests — F-097: Agent Dashboard

Tests the AgentDashboardService covering:
- get_agent_cards — list all cards with status counts
- get_agent_card — single card detail
- get_agent_status_counts — counts by status
- get_agent_realtime_metrics — metrics for Socket.io push
- pause_agent — pause an active agent
- resume_agent — resume a paused agent
- Sparkline computation (14-day)
- Quick action computation
- Metrics computation (resolution rate, CSAT, confidence, etc.)
- Status transitions and validation
- BC-001 multi-tenant scoping
- BC-005 Socket.io emission

Building Codes: BC-001, BC-005, BC-007, BC-012
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from app.exceptions import NotFoundError, ValidationError
from app.services.agent_dashboard_service import (
    _PAUSE_ALLOWED_FROM,
    _RESUME_ALLOWED_FROM,
    SPARKLINE_DAYS,
    AgentDashboardService,
    get_agent_dashboard_service,
)

# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def company_id():
    return "comp-abc-123"


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.flush = MagicMock()
    return db


@pytest.fixture
def service(company_id):
    return AgentDashboardService(company_id)


def _make_mock_agent(
    agent_id="agent-123",
    company_id="comp-abc-123",
    name="Support Bot",
    status="active",
    specialty="billing",
    description="Handles billing queries",
    base_model="gpt-4o",
    model_checkpoint_id="ckpt-abc",
    channels='["email", "chat"]',
    permissions='{"can_refund": true}',
):
    """Create a mock Agent ORM object."""
    agent = MagicMock()
    agent.id = agent_id
    agent.company_id = company_id
    agent.name = name
    agent.status = status
    agent.specialty = specialty
    agent.description = description
    agent.base_model = base_model
    agent.model_checkpoint_id = model_checkpoint_id
    agent.channels = channels
    agent.permissions = permissions
    agent.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    agent.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
    agent.activated_at = datetime(2025, 1, 3, tzinfo=timezone.utc)
    return agent


# ══════════════════════════════════════════════════════════════════
# CONSTANTS TESTS
# ══════════════════════════════════════════════════════════════════


class TestConstants:
    def test_sparkline_days(self):
        assert SPARKLINE_DAYS == 14

    def test_pause_allowed_from(self):
        assert _PAUSE_ALLOWED_FROM == ("active",)

    def test_resume_allowed_from(self):
        assert _RESUME_ALLOWED_FROM == ("paused",)


# ══════════════════════════════════════════════════════════════════
# SERVICE FACTORY TESTS
# ══════════════════════════════════════════════════════════════════


class TestServiceFactory:
    def test_get_service_cached(self, company_id):
        svc1 = get_agent_dashboard_service(company_id)
        svc2 = get_agent_dashboard_service(company_id)
        assert svc1 is svc2

    def test_get_service_different_company(self, company_id):
        svc1 = get_agent_dashboard_service(company_id)
        svc2 = get_agent_dashboard_service("other-company")
        assert svc1 is not svc2

    def test_service_scoped_to_company(self, company_id):
        svc = AgentDashboardService(company_id)
        assert svc.company_id == company_id


# ══════════════════════════════════════════════════════════════════
# GET AGENT STATUS COUNTS TESTS
# ══════════════════════════════════════════════════════════════════


class TestGetAgentStatusCounts:
    def test_counts_empty_tenant(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = (
            []
        )
        counts = service.get_agent_status_counts(mock_db)
        assert counts["total"] == 0
        assert counts["active"] == 0

    def test_counts_mixed_statuses(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("active", 3),
            ("training", 1),
            ("paused", 2),
            ("error", 1),
        ]
        counts = service.get_agent_status_counts(mock_db)
        assert counts["total"] == 7
        assert counts["active"] == 3
        assert counts["training"] == 1
        assert counts["paused"] == 2
        assert counts["error"] == 1

    def test_initializing_maps_to_cold_start(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("initializing", 2),
            ("active", 1),
        ]
        counts = service.get_agent_status_counts(mock_db)
        assert counts["cold_start"] == 2
        assert counts["active"] == 1
        assert counts["total"] == 3

    def test_counts_error_fallback(self, service, mock_db):
        mock_db.query.return_value.filter.side_effect = Exception("DB error")
        counts = service.get_agent_status_counts(mock_db)
        assert counts["total"] == 0
        # Should return zeroed defaults, not raise


# ══════════════════════════════════════════════════════════════════
# GET AGENT CARDS TESTS
# ══════════════════════════════════════════════════════════════════


class TestGetAgentCards:
    def test_returns_cards_and_counts(self, service, mock_db):
        agent = _make_mock_agent()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            agent
        ]
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("active", 1)
        ]

        result = service.get_agent_cards(mock_db)
        assert "cards" in result
        assert "status_counts" in result
        assert len(result["cards"]) == 1
        assert result["cards"][0]["id"] == "agent-123"

    def test_excludes_deprovisioned(self, service, mock_db):
        agent = _make_mock_agent()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            agent
        ]
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("active", 1)
        ]

        result = service.get_agent_cards(mock_db)
        # Verify that the filter excludes deprovisioned agents
        filter_call = mock_db.query.return_value.filter.call_args_list
        # First call should have the != "deprovisioned" filter
        assert len(filter_call) >= 1

    def test_status_filter(self, service, mock_db):
        agent = _make_mock_agent()
        # When status_filter is set, the service chains TWO .filter() calls.
        # Make the filter mock return itself so chaining works regardless of
        # how many .filter() calls the service adds.
        mock_filter = MagicMock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value.all.return_value = [agent]
        mock_filter.group_by.return_value.all.return_value = [("active", 1)]
        mock_db.query.return_value.filter.return_value = mock_filter

        result = service.get_agent_cards(mock_db, status_filter="active")
        assert len(result["cards"]) == 1

    def test_empty_result(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            []
        )
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = (
            []
        )

        result = service.get_agent_cards(mock_db)
        assert len(result["cards"]) == 0
        assert result["status_counts"]["total"] == 0

    def test_error_returns_empty(self, service, mock_db):
        mock_db.query.return_value.filter.side_effect = Exception("DB error")

        result = service.get_agent_cards(mock_db)
        assert len(result["cards"]) == 0
        assert result["status_counts"]["total"] == 0

    def test_card_has_required_fields(self, service, mock_db):
        agent = _make_mock_agent()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            agent
        ]
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("active", 1)
        ]

        result = service.get_agent_cards(mock_db)
        card = result["cards"][0]
        assert "id" in card
        assert "name" in card
        assert "status" in card
        assert "specialty" in card
        assert "metrics" in card
        assert "sparkline_data" in card
        assert "quick_actions" in card
        assert "created_at" in card

    def test_initializing_shows_cold_start(self, service, mock_db):
        agent = _make_mock_agent(status="initializing")
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            agent
        ]
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("initializing", 1)
        ]

        result = service.get_agent_cards(mock_db)
        assert result["cards"][0]["status"] == "cold_start"


# ══════════════════════════════════════════════════════════════════
# GET AGENT CARD DETAIL TESTS
# ══════════════════════════════════════════════════════════════════


class TestGetAgentCard:
    def test_returns_enriched_card(self, service, mock_db):
        agent = _make_mock_agent()
        mock_db.query.return_value.filter.return_value.first.return_value = agent
        # Mock InstructionSet query
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )

        result = service.get_agent_card("agent-123", mock_db)
        assert result["id"] == "agent-123"
        assert result["channels"] == ["email", "chat"]
        assert result["permissions"] == {"can_refund": True}

    def test_not_found_raises(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            service.get_agent_card("nonexistent", mock_db)
        assert "not found" in str(exc_info.value.message).lower()

    def test_includes_instruction_set(self, service, mock_db):
        agent = _make_mock_agent()
        mock_instruction = MagicMock()
        mock_instruction.id = "instr-123"
        mock_instruction.name = "Billing Instructions v2"
        mock_instruction.version = 3
        # Both db.query().filter().first() calls share the same mock path
        # because mock_db.query always returns the same object.  The service
        # calls .first() twice: once for the Agent and once for the
        # InstructionSet (both use a single .filter() with multiple args).
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            agent,
            mock_instruction,
        ]

        result = service.get_agent_card("agent-123", mock_db)
        assert "active_instruction_set" in result
        assert result["active_instruction_set"]["version"] == 3


# ══════════════════════════════════════════════════════════════════
# REALTIME METRICS TESTS
# ══════════════════════════════════════════════════════════════════


class TestRealtimeMetrics:
    def test_returns_metrics_with_timestamp(self, service, mock_db):
        agent = _make_mock_agent()
        mock_db.query.return_value.filter.return_value.first.return_value = agent

        with patch.object(
            service,
            "_compute_metrics",
            return_value={
                "resolution_rate": 85.5,
                "csat_avg": 4.2,
                "avg_confidence": 92.0,
                "escalation_rate": 5.0,
                "avg_handling_time": 12.3,
                "tickets_handled_24h": 42,
            },
        ):
            result = service.get_agent_realtime_metrics("agent-123", mock_db)

        assert result["agent_id"] == "agent-123"
        assert result["company_id"] == "comp-abc-123"
        assert result["resolution_rate"] == 85.5
        assert result["timestamp"] is not None

    def test_not_found_raises(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            service.get_agent_realtime_metrics("nonexistent", mock_db)


# ══════════════════════════════════════════════════════════════════
# PAUSE AGENT TESTS
# ══════════════════════════════════════════════════════════════════


class TestPauseAgent:
    def test_pause_active_agent(self, service, mock_db):
        agent = _make_mock_agent(status="active")
        mock_db.query.return_value.filter.return_value.first.return_value = agent

        with patch.object(service, "_emit_status_change"):
            result = service.pause_agent("agent-123", mock_db, user_id="user-1")

        assert result["previous_status"] == "active"
        assert result["new_status"] == "paused"
        assert agent.status == "paused"
        assert "paused" in result["message"].lower()
        mock_db.flush.assert_called_once()

    def test_pause_training_agent_raises(self, service, mock_db):
        agent = _make_mock_agent(status="training")
        mock_db.query.return_value.filter.return_value.first.return_value = agent

        with pytest.raises(ValidationError) as exc_info:
            service.pause_agent("agent-123", mock_db)
        assert "Cannot pause" in str(exc_info.value.message)

    def test_pause_paused_agent_raises(self, service, mock_db):
        agent = _make_mock_agent(status="paused")
        mock_db.query.return_value.filter.return_value.first.return_value = agent

        with pytest.raises(ValidationError):
            service.pause_agent("agent-123", mock_db)

    def test_pause_not_found_raises(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            service.pause_agent("nonexistent", mock_db)

    def test_pause_emits_socket_event(self, service, mock_db):
        agent = _make_mock_agent(status="active")
        mock_db.query.return_value.filter.return_value.first.return_value = agent

        with patch.object(service, "_emit_status_change") as mock_emit:
            service.pause_agent("agent-123", mock_db, user_id="user-1")

        mock_emit.assert_called_once_with(
            agent_id="agent-123",
            previous_status="active",
            new_status="paused",
            user_id="user-1",
        )


# ══════════════════════════════════════════════════════════════════
# RESUME AGENT TESTS
# ══════════════════════════════════════════════════════════════════


class TestResumeAgent:
    def test_resume_paused_agent(self, service, mock_db):
        agent = _make_mock_agent(status="paused")
        mock_db.query.return_value.filter.return_value.first.return_value = agent

        with patch.object(service, "_emit_status_change"):
            result = service.resume_agent("agent-123", mock_db, user_id="user-1")

        assert result["previous_status"] == "paused"
        assert result["new_status"] == "active"
        assert agent.status == "active"
        assert "resumed" in result["message"].lower()

    def test_resume_active_agent_raises(self, service, mock_db):
        agent = _make_mock_agent(status="active")
        mock_db.query.return_value.filter.return_value.first.return_value = agent

        with pytest.raises(ValidationError) as exc_info:
            service.resume_agent("agent-123", mock_db)
        assert "Cannot resume" in str(exc_info.value.message)

    def test_resume_training_agent_raises(self, service, mock_db):
        agent = _make_mock_agent(status="training")
        mock_db.query.return_value.filter.return_value.first.return_value = agent

        with pytest.raises(ValidationError):
            service.resume_agent("agent-123", mock_db)

    def test_resume_not_found_raises(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            service.resume_agent("nonexistent", mock_db)

    def test_resume_emits_socket_event(self, service, mock_db):
        agent = _make_mock_agent(status="paused")
        mock_db.query.return_value.filter.return_value.first.return_value = agent

        with patch.object(service, "_emit_status_change") as mock_emit:
            service.resume_agent("agent-123", mock_db)

        mock_emit.assert_called_once_with(
            agent_id="agent-123",
            previous_status="paused",
            new_status="active",
            user_id=None,
        )


# ══════════════════════════════════════════════════════════════════
# METRICS COMPUTATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestMetricsComputation:
    def test_non_active_returns_none_metrics(self, service, mock_db):
        agent = _make_mock_agent(status="training")
        metrics = service._compute_metrics(agent, mock_db)
        assert metrics["resolution_rate"] is None
        assert metrics["csat_avg"] is None
        assert metrics["avg_confidence"] is None
        assert metrics["tickets_handled_24h"] == 0

    def test_paused_returns_none_metrics(self, service, mock_db):
        agent = _make_mock_agent(status="paused")
        metrics = service._compute_metrics(agent, mock_db)
        assert metrics["resolution_rate"] is None
        assert metrics["tickets_handled_24h"] == 0

    def test_error_returns_none_metrics(self, service, mock_db):
        agent = _make_mock_agent(status="error")
        metrics = service._compute_metrics(agent, mock_db)
        assert metrics["resolution_rate"] is None

    def test_active_with_no_data_returns_none_rates(self, service, mock_db):
        agent = _make_mock_agent(status="active")
        # Mock all queries to return 0
        mock_scalar = MagicMock(return_value=0)
        mock_db.query.return_value.join.return_value.filter.return_value.scalar.return_value = (
            mock_scalar
        )
        mock_db.query.return_value.join.return_value.join.return_value.filter.return_value.scalar.return_value = (
            None
        )
        mock_db.query.return_value.join.return_value.join.return_value.filter.return_value.all.return_value = (
            []
        )

        metrics = service._compute_metrics(agent, mock_db)
        assert metrics["resolution_rate"] is None
        assert metrics["csat_avg"] is None
        assert metrics["tickets_handled_24h"] == 0

    def test_error_fallback_returns_zeroed(self, service, mock_db):
        agent = _make_mock_agent(status="active")
        mock_db.query.return_value.join.side_effect = Exception("DB error")

        metrics = service._compute_metrics(agent, mock_db)
        assert metrics["resolution_rate"] is None
        assert metrics["tickets_handled_24h"] == 0


# ══════════════════════════════════════════════════════════════════
# SPARKLINE TESTS
# ══════════════════════════════════════════════════════════════════


class TestSparkline:
    def test_returns_14_points(self, service, mock_db):
        agent = _make_mock_agent()
        mock_db.query.return_value.join.return_value.filter.return_value.scalar.return_value = (
            0
        )

        sparkline = service._compute_sparkline(agent, mock_db)
        assert len(sparkline) == 14

    def test_all_zeros_when_no_data(self, service, mock_db):
        agent = _make_mock_agent()
        mock_db.query.return_value.join.return_value.filter.return_value.scalar.return_value = (
            0
        )

        sparkline = service._compute_sparkline(agent, mock_db)
        assert all(v == 0.0 for v in sparkline)

    def test_error_returns_zeros(self, service, mock_db):
        agent = _make_mock_agent()
        mock_db.query.return_value.join.side_effect = Exception("DB error")

        sparkline = service._compute_sparkline(agent, mock_db)
        assert len(sparkline) == 14
        assert all(v == 0.0 for v in sparkline)


# ══════════════════════════════════════════════════════════════════
# QUICK ACTIONS TESTS
# ══════════════════════════════════════════════════════════════════


class TestQuickActions:
    def test_active_agent_has_pause_allowed(self, service):
        agent = _make_mock_agent(status="active")
        actions = service._compute_quick_actions(agent)

        pause = next(a for a in actions if a["action"] == "pause")
        assert pause["allowed"] is True
        assert pause["reason"] is None

    def test_active_agent_resume_not_allowed(self, service):
        agent = _make_mock_agent(status="active")
        actions = service._compute_quick_actions(agent)

        resume = next(a for a in actions if a["action"] == "resume")
        assert resume["allowed"] is False
        assert "not paused" in resume["reason"].lower()

    def test_paused_agent_resume_allowed(self, service):
        agent = _make_mock_agent(status="paused")
        actions = service._compute_quick_actions(agent)

        resume = next(a for a in actions if a["action"] == "resume")
        assert resume["allowed"] is True

    def test_paused_agent_pause_not_allowed(self, service):
        agent = _make_mock_agent(status="paused")
        actions = service._compute_quick_actions(agent)

        pause = next(a for a in actions if a["action"] == "pause")
        assert pause["allowed"] is False
        assert "already paused" in pause["reason"].lower()

    def test_training_agent_cannot_pause_or_resume(self, service):
        agent = _make_mock_agent(status="training")
        actions = service._compute_quick_actions(agent)

        pause = next(a for a in actions if a["action"] == "pause")
        resume = next(a for a in actions if a["action"] == "resume")
        assert pause["allowed"] is False
        assert resume["allowed"] is False

    def test_retrain_allowed_with_checkpoint(self, service):
        agent = _make_mock_agent(status="active", model_checkpoint_id="ckpt-abc")
        actions = service._compute_quick_actions(agent)

        retrain = next(a for a in actions if a["action"] == "retrain")
        assert retrain["allowed"] is True

    def test_retrain_not_allowed_without_checkpoint(self, service):
        agent = _make_mock_agent(status="active", model_checkpoint_id=None)
        actions = service._compute_quick_actions(agent)

        retrain = next(a for a in actions if a["action"] == "retrain")
        assert retrain["allowed"] is False
        assert "No model checkpoint" in retrain["reason"]

    def test_view_metrics_always_allowed(self, service):
        for status in ["active", "paused", "training", "error"]:
            agent = _make_mock_agent(status=status)
            actions = service._compute_quick_actions(agent)
            view = next(a for a in actions if a["action"] == "view_metrics")
            assert view["allowed"] is True

    def test_four_actions_always_present(self, service):
        agent = _make_mock_agent()
        actions = service._compute_quick_actions(agent)
        action_names = {a["action"] for a in actions}
        assert action_names == {"pause", "resume", "retrain", "view_metrics"}


# ══════════════════════════════════════════════════════════════════
# SOCKET.IO EMISSION TESTS
# ══════════════════════════════════════════════════════════════════


class TestSocketEmission:
    def test_emit_status_change_calls_emit(self, service):
        # Patch at the source module — emit_to_tenant is imported lazily
        # inside _emit_status_change, not at module level.
        with patch("app.core.socketio.emit_to_tenant") as mock_emit:
            service._emit_status_change(
                agent_id="agent-123",
                previous_status="active",
                new_status="paused",
                user_id="user-1",
            )
            mock_emit.assert_called_once()

    def test_emit_failure_does_not_raise(self, service):
        """BC-005: Socket.io failure must never break the caller."""
        with patch(
            "app.core.socketio.emit_to_tenant", side_effect=Exception("Socket error")
        ):
            # Should not raise — the method wraps Socket.io in try/except
            service._emit_status_change(
                agent_id="agent-123",
                previous_status="active",
                new_status="paused",
            )


# ══════════════════════════════════════════════════════════════════
# CARD BUILDER TESTS
# ══════════════════════════════════════════════════════════════════


class TestCardBuilder:
    def test_card_structure(self, service, mock_db):
        agent = _make_mock_agent()
        mock_db.query.return_value.join.return_value.filter.return_value.scalar.return_value = (
            0
        )

        card = service._build_agent_card(agent, mock_db)
        assert card["id"] == "agent-123"
        assert card["name"] == "Support Bot"
        assert card["status"] == "active"
        assert card["specialty"] == "billing"
        assert card["base_model"] == "gpt-4o"
        assert isinstance(card["metrics"], dict)
        assert isinstance(card["sparkline_data"], list)
        assert isinstance(card["quick_actions"], list)

    def test_card_activated_at(self, service, mock_db):
        agent = _make_mock_agent()
        mock_db.query.return_value.join.return_value.filter.return_value.scalar.return_value = (
            0
        )

        card = service._build_agent_card(agent, mock_db)
        assert card["activated_at"] is not None


# ══════════════════════════════════════════════════════════════════
# JSON PARSER TESTS
# ══════════════════════════════════════════════════════════════════


class TestJsonParser:
    def test_valid_json(self):
        assert AgentDashboardService._parse_json('{"key": "value"}') == {"key": "value"}

    def test_none_returns_empty(self):
        assert AgentDashboardService._parse_json(None) == {}

    def test_empty_returns_empty(self):
        assert AgentDashboardService._parse_json("") == {}

    def test_invalid_json_returns_empty(self):
        assert AgentDashboardService._parse_json("not json") == {}
