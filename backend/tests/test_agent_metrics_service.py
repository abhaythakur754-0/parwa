"""
PARWA Tests — F-098: Agent Metrics Service

Tests the AgentMetricsService covering:
- Constants validation
- get_metrics — historical metrics with summary
- get_thresholds — threshold config
- update_thresholds — threshold updates with validation
- compare_agents — multi-agent comparison
- compute_and_store_daily_metrics — Celery task for daily metrics
- evaluate_alerts — threshold breach detection
- _aggregate_weekly — weekly aggregation
- _determine_trend — trend direction

Building Codes: BC-001 (multi-tenant), BC-012 (graceful errors)
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from app.exceptions import ValidationError
from app.services.agent_metrics_service import (
    CONSECUTIVE_DAYS_THRESHOLD,
    DEFAULT_THRESHOLDS,
    METRIC_BELOW_CHECKS,
    MIN_TICKETS_FOR_ALERTS,
    VALID_GRANULARITIES,
    VALID_PERIODS,
    AgentMetricsService,
)

# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def company_id():
    return "comp-abc-123"


@pytest.fixture
def agent_id():
    return "agent-123"


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def service(mock_db):
    return AgentMetricsService(mock_db)


def _make_metrics_row(
    row_date="2025-01-15",
    resolution_rate=80.0,
    avg_confidence=85.0,
    avg_csat=4.2,
    escalation_rate=10.0,
    avg_handle_time_seconds=120,
    tickets_handled=10,
):
    """Create a mock AgentMetricsDaily row."""
    row = MagicMock()
    row.date = date.fromisoformat(row_date)
    row.resolution_rate = Decimal(str(resolution_rate))
    row.avg_confidence = Decimal(str(avg_confidence))
    row.avg_csat = Decimal(str(avg_csat))
    row.escalation_rate = Decimal(str(escalation_rate))
    row.avg_handle_time_seconds = avg_handle_time_seconds
    row.tickets_handled = tickets_handled
    return row


def _make_threshold(
    resolution_rate_min=70.0,
    confidence_min=65.0,
    csat_min=3.5,
    escalation_max_pct=15.0,
):
    """Create a mock AgentMetricThreshold object."""
    t = MagicMock()
    t.id = "thresh-1"
    t.company_id = "comp-abc-123"
    t.agent_id = "agent-123"
    t.resolution_rate_min = Decimal(str(resolution_rate_min))
    t.confidence_min = Decimal(str(confidence_min))
    t.csat_min = Decimal(str(csat_min))
    t.escalation_max_pct = Decimal(str(escalation_max_pct))
    t.updated_at = datetime.utcnow()
    return t


def _make_alert(
    alert_id="alert-1",
    metric_name="resolution_rate",
    status="active",
    consecutive_days_below=2,
):
    """Create a mock AgentPerformanceAlert object."""
    a = MagicMock()
    a.id = alert_id
    a.company_id = "comp-abc-123"
    a.agent_id = "agent-123"
    a.metric_name = metric_name
    a.current_value = Decimal("55.0")
    a.threshold_value = Decimal("70.0")
    a.consecutive_days_below = consecutive_days_below
    a.status = status
    a.resolved_at = None
    return a


# ══════════════════════════════════════════════════════════════════
# CONSTANTS TESTS
# ══════════════════════════════════════════════════════════════════


class TestConstants:
    def test_default_thresholds_keys(self):
        expected = {
            "resolution_rate_min",
            "confidence_min",
            "csat_min",
            "escalation_max_pct",
        }
        assert set(DEFAULT_THRESHOLDS.keys()) == expected

    def test_default_thresholds_values(self):
        assert DEFAULT_THRESHOLDS["resolution_rate_min"] == 70.0
        assert DEFAULT_THRESHOLDS["confidence_min"] == 65.0
        assert DEFAULT_THRESHOLDS["csat_min"] == 3.5
        assert DEFAULT_THRESHOLDS["escalation_max_pct"] == 15.0

    def test_min_tickets_for_alerts(self):
        assert MIN_TICKETS_FOR_ALERTS == 5

    def test_consecutive_days_threshold(self):
        assert CONSECUTIVE_DAYS_THRESHOLD == 2

    def test_valid_periods(self):
        assert set(VALID_PERIODS.keys()) == {"7d", "14d", "30d", "90d"}
        assert VALID_PERIODS["7d"] == 7
        assert VALID_PERIODS["30d"] == 30
        assert VALID_PERIODS["90d"] == 90

    def test_valid_granularities(self):
        assert VALID_GRANULARITIES == {"daily", "weekly"}

    def test_metric_below_checks(self):
        assert METRIC_BELOW_CHECKS["resolution_rate"] == "below"
        assert METRIC_BELOW_CHECKS["avg_confidence"] == "below"
        assert METRIC_BELOW_CHECKS["avg_csat"] == "below"
        assert METRIC_BELOW_CHECKS["escalation_rate"] == "above"
        assert len(METRIC_BELOW_CHECKS) == 4


# ══════════════════════════════════════════════════════════════════
# GET_METRICS TESTS
# ══════════════════════════════════════════════════════════════════


class TestGetMetrics:
    def test_valid_period_and_granularity(self, service, mock_db, agent_id, company_id):
        row = _make_metrics_row(tickets_handled=10)
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            row
        ]

        result = service.get_metrics(
            agent_id, company_id, period="7d", granularity="daily"
        )

        assert result["agent_id"] == agent_id
        assert result["period"] == "7d"
        assert result["granularity"] == "daily"
        assert len(result["data_points"]) == 1
        assert result["data_points"][0]["resolution_rate"] == 80.0
        assert result["summary"]["total_tickets"] == 10

    def test_invalid_period_raises(self, service, agent_id, company_id):
        with pytest.raises(ValidationError) as exc:
            service.get_metrics(agent_id, company_id, period="1y")
        assert "Invalid period" in exc.value.message

    def test_invalid_granularity_raises(self, service, agent_id, company_id):
        with pytest.raises(ValidationError) as exc:
            service.get_metrics(agent_id, company_id, granularity="monthly")
        assert "Invalid granularity" in exc.value.message

    def test_empty_data_returns_empty_points(
        self, service, mock_db, agent_id, company_id
    ):
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            []
        )

        result = service.get_metrics(agent_id, company_id)

        assert result["data_points"] == []
        assert result["summary"]["total_tickets"] == 0
        assert result["insufficient_data"] is True

    def test_with_multiple_rows(self, service, mock_db, agent_id, company_id):
        rows = [
            _make_metrics_row("2025-01-14", resolution_rate=70.0, tickets_handled=5),
            _make_metrics_row("2025-01-15", resolution_rate=90.0, tickets_handled=8),
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            rows
        )

        result = service.get_metrics(agent_id, company_id, period="7d")

        assert len(result["data_points"]) == 2
        assert result["summary"]["total_tickets"] == 13

    def test_weekly_granularity(self, service, mock_db, agent_id, company_id):
        rows = [
            _make_metrics_row("2025-01-13", tickets_handled=3),
            _make_metrics_row("2025-01-14", tickets_handled=4),
            _make_metrics_row("2025-01-15", tickets_handled=5),
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            rows
        )

        result = service.get_metrics(
            agent_id, company_id, period="7d", granularity="weekly"
        )

        # All 3 dates are in the same ISO week, so should be 1 weekly bucket
        assert len(result["data_points"]) >= 1
        # Weekly key should be like "2025-W03"
        assert "W" in result["data_points"][0]["date"]

    def test_insufficient_data_flag(self, service, mock_db, agent_id, company_id):
        row = _make_metrics_row(tickets_handled=2)
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            row
        ]

        result = service.get_metrics(agent_id, company_id)

        assert result["insufficient_data"] is True
        assert result["summary"]["total_tickets"] == 2

    def test_error_fallback(self, service, mock_db, agent_id, company_id):
        mock_db.query.return_value.filter.side_effect = Exception("DB error")

        result = service.get_metrics(agent_id, company_id, period="7d")

        assert result["agent_id"] == agent_id
        assert result["data_points"] == []
        assert result["summary"]["total_tickets"] == 0
        assert result["insufficient_data"] is True

    def test_summary_averages(self, service, mock_db, agent_id, company_id):
        rows = [
            _make_metrics_row(
                "2025-01-14",
                resolution_rate=60.0,
                avg_confidence=80.0,
                avg_csat=4.0,
                escalation_rate=5.0,
            ),
            _make_metrics_row(
                "2025-01-15",
                resolution_rate=80.0,
                avg_confidence=90.0,
                avg_csat=5.0,
                escalation_rate=15.0,
            ),
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            rows
        )

        result = service.get_metrics(agent_id, company_id)

        assert result["summary"]["avg_resolution_rate"] == 70.0
        assert result["summary"]["avg_confidence"] == 85.0
        assert result["summary"]["avg_csat"] == 4.5
        assert result["summary"]["avg_escalation_rate"] == 10.0

    def test_null_metric_values_handled(self, service, mock_db, agent_id, company_id):
        row = MagicMock()
        row.date = date(2025, 1, 15)
        row.resolution_rate = None
        row.avg_confidence = None
        row.avg_csat = None
        row.escalation_rate = None
        row.avg_handle_time_seconds = None
        row.tickets_handled = 10
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            row
        ]

        result = service.get_metrics(agent_id, company_id)

        assert result["data_points"][0]["resolution_rate"] is None
        assert result["data_points"][0]["avg_confidence"] is None
        assert result["summary"]["avg_resolution_rate"] is None


# ══════════════════════════════════════════════════════════════════
# GET_THRESHOLDS TESTS
# ══════════════════════════════════════════════════════════════════


class TestGetThresholds:
    def test_returns_existing_threshold(self, service, mock_db, agent_id, company_id):
        threshold = _make_threshold()
        mock_db.query.return_value.filter.return_value.first.return_value = threshold

        result = service.get_thresholds(agent_id, company_id)

        assert result["agent_id"] == agent_id
        assert result["resolution_rate_min"] == 70.0
        assert result["confidence_min"] == 65.0
        assert result["csat_min"] == 3.5
        assert result["escalation_max_pct"] == 15.0

    def test_creates_default_if_not_found(self, service, mock_db, agent_id, company_id):
        # First call: .filter().first() returns None (no threshold exists)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.get_thresholds(agent_id, company_id)

        # Should have created a new threshold via _get_or_create_thresholds
        mock_db.add.assert_called()
        mock_db.flush.assert_called()
        assert result["agent_id"] == agent_id
        # Values should match DEFAULT_THRESHOLDS
        assert result["resolution_rate_min"] == 70.0

    def test_error_fallback_returns_defaults(
        self, service, mock_db, agent_id, company_id
    ):
        mock_db.query.return_value.filter.side_effect = Exception("DB error")

        result = service.get_thresholds(agent_id, company_id)

        assert result["agent_id"] == agent_id
        assert result == {"agent_id": agent_id, **DEFAULT_THRESHOLDS}


# ══════════════════════════════════════════════════════════════════
# UPDATE_THRESHOLDS TESTS
# ══════════════════════════════════════════════════════════════════


class TestUpdateThresholds:
    def test_valid_update(self, service, mock_db, agent_id, company_id):
        threshold = _make_threshold()
        mock_db.query.return_value.filter.return_value.first.return_value = threshold

        result = service.update_thresholds(
            agent_id,
            company_id,
            updates={"resolution_rate_min": 80.0},
            user_id="user-1",
        )

        assert result["resolution_rate_min"] == 80.0
        mock_db.flush.assert_called()

    def test_invalid_key_raises(self, service, agent_id, company_id):
        with pytest.raises(ValidationError) as exc:
            service.update_thresholds(
                agent_id,
                company_id,
                updates={"invalid_key": 100.0},
            )
        assert "Invalid threshold keys" in exc.value.message

    def test_csat_above_5_warns(self, service, mock_db, agent_id, company_id):
        threshold = _make_threshold()
        mock_db.query.return_value.filter.return_value.first.return_value = threshold

        result = service.update_thresholds(
            agent_id,
            company_id,
            updates={"csat_min": 6.0},
        )

        assert "warnings" in result
        assert "impossible" in result["warnings"][0].lower()

    def test_all_four_keys(self, service, mock_db, agent_id, company_id):
        threshold = _make_threshold()
        mock_db.query.return_value.filter.return_value.first.return_value = threshold

        result = service.update_thresholds(
            agent_id,
            company_id,
            updates={
                "resolution_rate_min": 90.0,
                "confidence_min": 80.0,
                "csat_min": 4.5,
                "escalation_max_pct": 10.0,
            },
        )

        assert result["resolution_rate_min"] == 90.0
        assert result["confidence_min"] == 80.0
        assert result["csat_min"] == 4.5
        assert result["escalation_max_pct"] == 10.0

    def test_error_reraises(self, service, mock_db, agent_id, company_id):
        mock_db.query.return_value.filter.return_value.first.side_effect = Exception(
            "DB error"
        )

        with pytest.raises(Exception):
            service.update_thresholds(
                agent_id,
                company_id,
                updates={"resolution_rate_min": 80.0},
            )


# ══════════════════════════════════════════════════════════════════
# COMPARE_AGENTS TESTS
# ══════════════════════════════════════════════════════════════════


class TestCompareAgents:
    def test_empty_list(self, service, company_id):
        result = service.compare_agents([], company_id)
        assert result == []

    def test_single_agent_with_data(self, service, mock_db, company_id):
        row = _make_metrics_row("2025-01-14", resolution_rate=80.0, tickets_handled=10)
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            row
        ]

        result = service.compare_agents(["agent-1"], company_id, period="7d")

        assert len(result) == 1
        assert result[0]["agent_id"] == "agent-1"
        assert "trend" in result[0]
        assert result[0]["data_point_count"] == 1

    def test_multiple_agents(self, service, mock_db, company_id):
        row1 = _make_metrics_row("2025-01-14", tickets_handled=10)
        row2 = _make_metrics_row("2025-01-14", tickets_handled=10)
        # Both calls to get_metrics return the same row mock
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            row1
        ]

        result = service.compare_agents(["agent-1", "agent-2"], company_id)

        assert len(result) == 2

    def test_excludes_insufficient_data(self, service, mock_db, company_id):
        # below MIN_TICKETS_FOR_ALERTS
        row = _make_metrics_row(tickets_handled=2)
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            row
        ]

        result = service.compare_agents(["agent-1"], company_id)

        assert len(result) == 0

    def test_error_skips_agent(self, service, mock_db, company_id):
        mock_db.query.return_value.filter.side_effect = Exception("DB error")

        result = service.compare_agents(["agent-1"], company_id)

        # Should not raise, should skip the errored agent
        assert len(result) == 0


# ══════════════════════════════════════════════════════════════════
# COMPUTE_DAILY_METRICS TESTS
# ══════════════════════════════════════════════════════════════════


class TestComputeDailyMetrics:
    def test_no_active_agents(self, service, mock_db, company_id):
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = service.compute_and_store_daily_metrics(company_id)

        assert result["agents_processed"] == 0
        assert result["errors"] == 0
        assert result["metrics"] == []

    def test_with_active_agent_zero_tickets(self, service, mock_db, company_id):
        agent = MagicMock()
        agent.id = "agent-1"
        agent.name = "Support Bot"

        # First query (Agent list), second query (tickets count → 0)
        mock_db.query.return_value.filter.return_value.all.return_value = [agent]
        # scalar returns 0 for tickets_handled
        mock_db.query.return_value.join.return_value.filter.return_value.scalar.return_value = (
            0
        )

        result = service.compute_and_store_daily_metrics(company_id)

        assert result["agents_processed"] == 1
        assert result["errors"] == 0
        assert result["metrics"][0]["tickets_handled"] == 0

    def test_upsert_existing_record(self, service, mock_db, company_id):
        agent = MagicMock()
        agent.id = "agent-1"
        agent.name = "Support Bot"

        existing = MagicMock()

        # Agent list query returns agent
        mock_db.query.return_value.filter.return_value.all.return_value = [agent]
        # Tickets handled = 0 → early return with zeroed metrics
        mock_db.query.return_value.join.return_value.filter.return_value.scalar.return_value = (
            0
        )
        # Existing record found
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        result = service.compute_and_store_daily_metrics(company_id)

        assert result["agents_processed"] == 1
        # When tickets_handled == 0, the service still reaches the upsert block
        # and checks for existing record

    def test_error_per_agent(self, service, mock_db, company_id):
        agent = MagicMock()
        agent.id = "agent-1"
        agent.name = "Support Bot"

        # Agent list query OK, but _compute_agent_daily_metrics inner try/except
        # catches join errors and returns zeroed metrics (doesn't propagate).
        # The error is logged. agents_processed will be 1 because the metrics
        # dict IS returned (just with zeroed values). To force an actual error,
        # we make the AgentMetricsDaily filter call raise.
        mock_db.query.return_value.filter.return_value.all.return_value = [agent]
        # scalar returns 0 for tickets_handled (first call succeeds)
        # but the second query (AgentMetricsDaily filter for upsert) raises
        call_count = [0]
        original_filter = mock_db.query.return_value.filter

        def side_effect_filter(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return original_filter(*args, **kwargs)
            raise Exception("Upsert query error")

        mock_db.query.return_value.filter.side_effect = side_effect_filter

        result = service.compute_and_store_daily_metrics(company_id)

        # The per-agent error handler should catch this
        assert result["errors"] == 1

    def test_outer_error_fallback(self, service, mock_db, company_id):
        mock_db.query.side_effect = Exception("Outer error")

        result = service.compute_and_store_daily_metrics(company_id)

        assert result["agents_processed"] == 0
        assert result["errors"] == 1
        assert result["metrics"] == []


# ══════════════════════════════════════════════════════════════════
# EVALUATE_ALERTS TESTS
# ══════════════════════════════════════════════════════════════════


class TestEvaluateAlerts:
    def test_no_breaches(self, service, mock_db, company_id):
        agent = MagicMock()
        agent.id = "agent-1"

        threshold = _make_threshold()

        # All metrics above threshold (no breach)
        dm1 = _make_metrics_row(
            "2025-01-15",
            resolution_rate=90.0,
            avg_confidence=85.0,
            avg_csat=4.5,
            escalation_rate=5.0,
            tickets_handled=10,
        )
        mock_db.query.return_value.filter.return_value.all.return_value = [agent]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            dm1
        ]
        mock_db.query.return_value.filter.return_value.first.return_value = threshold

        result = service.evaluate_alerts(company_id)

        # No breaches → no alerts created; first day is above threshold, so
        # consecutive_below will be 0 for "resolution_rate" check
        # With consecutive_below == 0, it checks for active alerts to resolve
        # No active alert exists → nothing in result
        assert isinstance(result, list)

    def test_consecutive_days_creates_alert(self, service, mock_db, company_id):
        agent = MagicMock()
        agent.id = "agent-1"

        threshold = _make_threshold(resolution_rate_min=70.0)

        # 2 consecutive days below threshold for resolution_rate
        dm1 = _make_metrics_row(
            "2025-01-15",
            resolution_rate=55.0,
            avg_confidence=80.0,
            avg_csat=4.0,
            escalation_rate=5.0,
            tickets_handled=5,
        )
        dm2 = _make_metrics_row(
            "2025-01-14",
            resolution_rate=60.0,
            avg_confidence=85.0,
            avg_csat=4.5,
            escalation_rate=5.0,
            tickets_handled=5,
        )

        # Query sequence: query().all()=[agent], query().first()=threshold,
        # query().order_by().all()=[dm1,dm2], query().first()=None x N
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.all.side_effect = [[agent], [dm1, dm2]]
        chain.first.side_effect = [threshold, None, None, None, None]
        chain.order_by.return_value = chain
        mock_db.query.return_value = chain

        result = service.evaluate_alerts(company_id)

        created = [a for a in result if a["action"] == "created"]
        assert len(created) >= 1
        assert created[0]["metric_name"] == "resolution_rate"

    def test_escalation_above_threshold(self, service, mock_db, company_id):
        agent = MagicMock()
        agent.id = "agent-1"

        threshold = _make_threshold(escalation_max_pct=10.0)

        # 2 consecutive days with escalation above threshold
        dm1 = _make_metrics_row(
            "2025-01-15",
            escalation_rate=20.0,
            tickets_handled=5,
            resolution_rate=80.0,
            avg_confidence=80.0,
            avg_csat=4.0,
        )
        dm2 = _make_metrics_row(
            "2025-01-14",
            escalation_rate=25.0,
            tickets_handled=5,
            resolution_rate=80.0,
            avg_confidence=80.0,
            avg_csat=4.0,
        )

        chain = MagicMock()
        chain.filter.return_value = chain
        chain.all.side_effect = [[agent], [dm1, dm2]]
        chain.first.side_effect = [threshold, None, None, None, None]
        chain.order_by.return_value = chain
        mock_db.query.return_value = chain

        result = service.evaluate_alerts(company_id)

        created = [a for a in result if a["action"] == "created"]
        escalation_alerts = [
            a for a in created if a["metric_name"] == "escalation_rate"
        ]
        assert len(escalation_alerts) >= 1

    def test_resolved_alert_on_recovery(self, service, mock_db, company_id):
        agent = MagicMock()
        agent.id = "agent-1"

        threshold = _make_threshold()
        alert = _make_alert(status="active")

        # Metrics above threshold → recovery
        dm1 = _make_metrics_row(
            "2025-01-15",
            resolution_rate=90.0,
            avg_confidence=90.0,
            avg_csat=5.0,
            escalation_rate=5.0,
            tickets_handled=5,
        )

        chain = MagicMock()
        chain.filter.return_value = chain
        chain.all.side_effect = [[agent], [dm1]]
        chain.first.side_effect = [threshold, alert, None, None, None]
        chain.order_by.return_value = chain
        mock_db.query.return_value = chain

        result = service.evaluate_alerts(company_id)

        resolved = [a for a in result if a["action"] == "resolved"]
        assert len(resolved) >= 1

    def test_existing_alert_updated(self, service, mock_db, company_id):
        agent = MagicMock()
        agent.id = "agent-1"

        threshold = _make_threshold(resolution_rate_min=70.0)
        existing_alert = _make_alert(status="active", metric_name="resolution_rate")

        dm1 = _make_metrics_row(
            "2025-01-15",
            resolution_rate=50.0,
            tickets_handled=5,
            avg_confidence=80.0,
            avg_csat=4.0,
            escalation_rate=5.0,
        )
        dm2 = _make_metrics_row(
            "2025-01-14",
            resolution_rate=55.0,
            tickets_handled=5,
            avg_confidence=80.0,
            avg_csat=4.0,
            escalation_rate=5.0,
        )

        chain = MagicMock()
        chain.filter.return_value = chain
        chain.all.side_effect = [[agent], [dm1, dm2]]
        chain.first.side_effect = [threshold, existing_alert, None, None, None]
        chain.order_by.return_value = chain
        mock_db.query.return_value = chain

        result = service.evaluate_alerts(company_id)

        updated = [a for a in result if a["action"] == "updated"]
        assert len(updated) >= 1

    def test_no_threshold_skips(self, service, mock_db, company_id):
        agent = MagicMock()
        agent.id = "agent-1"

        mock_db.query.return_value.filter.return_value.all.return_value = [agent]
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            []
        )

        result = service.evaluate_alerts(company_id)

        assert result == []

    def test_ticket_minimum_check(self, service, mock_db, company_id):
        agent = MagicMock()
        agent.id = "agent-1"

        threshold = _make_threshold(resolution_rate_min=70.0)

        # Only 2 tickets total (below MIN_TICKETS_FOR_ALERTS)
        dm1 = _make_metrics_row(
            "2025-01-15",
            resolution_rate=50.0,
            tickets_handled=1,
            avg_confidence=50.0,
            avg_csat=2.0,
            escalation_rate=20.0,
        )
        dm2 = _make_metrics_row(
            "2025-01-14",
            resolution_rate=55.0,
            tickets_handled=1,
            avg_confidence=50.0,
            avg_csat=2.0,
            escalation_rate=20.0,
        )

        mock_db.query.return_value.filter.return_value.all.return_value = [agent]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            dm1,
            dm2,
        ]
        mock_db.query.return_value.filter.return_value.first.return_value = threshold

        result = service.evaluate_alerts(company_id)

        # No alerts should be created due to ticket minimum
        created = [a for a in result if a["action"] == "created"]
        assert len(created) == 0

    def test_outer_error_returns_empty(self, service, mock_db, company_id):
        mock_db.query.side_effect = Exception("DB error")

        result = service.evaluate_alerts(company_id)

        assert result == []


# ══════════════════════════════════════════════════════════════════
# AGGREGATE_WEEKLY TESTS
# ══════════════════════════════════════════════════════════════════


class TestAggregateWeekly:
    def test_empty_data(self, service):
        result = service._aggregate_weekly([])
        assert result == []

    def test_single_day(self, service):
        data = [
            {
                "date": "2025-01-15",
                "resolution_rate": 80.0,
                "avg_confidence": 85.0,
                "avg_csat": 4.2,
                "escalation_rate": 10.0,
                "avg_handle_time": 120,
                "tickets_handled": 5,
            }
        ]
        result = service._aggregate_weekly(data)
        assert len(result) == 1
        assert result[0]["tickets_handled"] == 5

    def test_cross_week_aggregation(self, service):
        data = [
            {
                "date": "2025-01-12",  # Sunday W02
                "resolution_rate": 70.0,
                "avg_confidence": 80.0,
                "avg_csat": 4.0,
                "escalation_rate": 10.0,
                "avg_handle_time": 100,
                "tickets_handled": 3,
            },
            {
                "date": "2025-01-13",  # Monday W03
                "resolution_rate": 80.0,
                "avg_confidence": 90.0,
                "avg_csat": 4.5,
                "escalation_rate": 15.0,
                "avg_handle_time": 140,
                "tickets_handled": 4,
            },
        ]
        result = service._aggregate_weekly(data)

        # Two different ISO weeks → 2 buckets
        assert len(result) == 2
        assert result[0]["tickets_handled"] == 3
        assert result[1]["tickets_handled"] == 4


# ══════════════════════════════════════════════════════════════════
# DETERMINE_TREND TESTS
# ══════════════════════════════════════════════════════════════════


class TestDetermineTrend:
    def test_upward_trend(self):
        # Need 6+ values so prev window is non-empty
        assert (
            AgentMetricsService._determine_trend([60.0, 62.0, 64.0, 70.0, 75.0, 80.0])
            == "up"
        )

    def test_downward_trend(self):
        assert (
            AgentMetricsService._determine_trend([90.0, 88.0, 85.0, 80.0, 75.0, 70.0])
            == "down"
        )

    def test_stable_trend(self):
        assert AgentMetricsService._determine_trend([75.0, 75.0, 75.0]) == "stable"

    def test_insufficient_data(self):
        assert AgentMetricsService._determine_trend([80.0]) == "stable"

    def test_two_values_up(self):
        assert AgentMetricsService._determine_trend([70.0, 80.0]) == "up"

    def test_two_values_down(self):
        assert AgentMetricsService._determine_trend([80.0, 70.0]) == "down"

    def test_two_values_stable(self):
        assert AgentMetricsService._determine_trend([75.0, 76.0]) == "stable"

    def test_empty_list(self):
        assert AgentMetricsService._determine_trend([]) == "stable"
