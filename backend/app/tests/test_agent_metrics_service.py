"""
Tests for Agent Metrics Service (F-098)

Covers:
- Constants validation
- get_metrics: valid period, invalid period, insufficient data,
  daily granularity, weekly aggregation
- get_thresholds: get existing, create default when missing
- update_thresholds: update valid, warn on impossible CSAT, invalid key
- compare_agents: compare 3 agents, exclude low-ticket agents,
  empty agent_ids
- compute_and_store_daily_metrics: active agent, paused agent,
  error fallback
- evaluate_alerts: new alert created, consecutive days increment,
  alert resolved on recovery, no alert for 1 day
- Trend determination: up, down, stable, single value
"""

from __future__ import annotations
from app.exceptions import ValidationError

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# Mock structlog and app.logger before importing service modules
# (same pattern as test_cost_protection_service.py)
_mock_logger = MagicMock()
with patch.dict("sys.modules", {"structlog": MagicMock(), "app.logger": MagicMock(get_logger=lambda name: _mock_logger)}):
    from app.services.agent_metrics_service import (
        AgentMetricsService,
        DEFAULT_THRESHOLDS,
        MIN_TICKETS_FOR_ALERTS,
        CONSECUTIVE_DAYS_THRESHOLD,
        VALID_PERIODS,
        VALID_GRANULARITIES,
        METRIC_BELOW_CHECKS,
    )


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def company_id():
    return "test-company-f098"


@pytest.fixture
def service(mock_db):
    return AgentMetricsService(db=mock_db)


def _make_agent(
    agent_id: str = "agent-001",
    name: str = "Test Agent",
    status: str = "active",
):
    """Create a mock Agent ORM object."""
    agent = MagicMock()
    agent.id = agent_id
    agent.name = name
    agent.status = status
    agent.company_id = "test-company-f098"
    return agent


def _make_daily_metric(
    agent_id: str = "agent-001",
    metric_date: date = None,
    tickets_handled: int = 20,
    resolved_count: int = 15,
    escalated_count: int = 3,
    avg_confidence: float = 78.5,
    avg_csat: float = 4.2,
    avg_handle_time_seconds: int = 180,
    resolution_rate: float = 75.0,
    escalation_rate: float = 15.0,
):
    """Create a mock AgentMetricsDaily ORM object."""
    if metric_date is None:
        metric_date = date.today() - timedelta(days=1)
    dm = MagicMock()
    dm.agent_id = agent_id
    dm.company_id = "test-company-f098"
    dm.date = metric_date
    dm.tickets_handled = tickets_handled
    dm.resolved_count = resolved_count
    dm.escalated_count = escalated_count
    dm.avg_confidence = Decimal(str(avg_confidence))
    dm.avg_csat = Decimal(str(avg_csat))
    dm.avg_handle_time_seconds = avg_handle_time_seconds
    dm.resolution_rate = Decimal(str(resolution_rate))
    dm.escalation_rate = Decimal(str(escalation_rate))
    return dm


def _make_threshold(
    agent_id: str = "agent-001",
    resolution_rate_min: float = 70.0,
    confidence_min: float = 65.0,
    csat_min: float = 3.5,
    escalation_max_pct: float = 15.0,
):
    """Create a mock AgentMetricThreshold ORM object."""
    t = MagicMock()
    t.agent_id = agent_id
    t.company_id = "test-company-f098"
    t.resolution_rate_min = Decimal(str(resolution_rate_min))
    t.confidence_min = Decimal(str(confidence_min))
    t.csat_min = Decimal(str(csat_min))
    t.escalation_max_pct = Decimal(str(escalation_max_pct))
    t.updated_at = datetime.utcnow()
    return t


# ═══════════════════════════════════════════════════════════════════
# 1. Constants
# ═══════════════════════════════════════════════════════════════════


class TestConstants:
    def test_default_thresholds_has_all_keys(self):
        assert "resolution_rate_min" in DEFAULT_THRESHOLDS
        assert "confidence_min" in DEFAULT_THRESHOLDS
        assert "csat_min" in DEFAULT_THRESHOLDS
        assert "escalation_max_pct" in DEFAULT_THRESHOLDS

    def test_default_thresholds_values(self):
        assert DEFAULT_THRESHOLDS["resolution_rate_min"] == 70.0
        assert DEFAULT_THRESHOLDS["confidence_min"] == 65.0
        assert DEFAULT_THRESHOLDS["csat_min"] == 3.5
        assert DEFAULT_THRESHOLDS["escalation_max_pct"] == 15.0

    def test_valid_periods(self):
        assert "7d" in VALID_PERIODS
        assert "14d" in VALID_PERIODS
        assert "30d" in VALID_PERIODS
        assert "90d" in VALID_PERIODS
        assert VALID_PERIODS["7d"] == 7
        assert VALID_PERIODS["30d"] == 30

    def test_valid_granularities(self):
        assert "daily" in VALID_GRANULARITIES
        assert "weekly" in VALID_GRANULARITIES

    def test_consecutive_days_threshold(self):
        assert CONSECUTIVE_DAYS_THRESHOLD == 2

    def test_min_tickets_for_alerts(self):
        assert MIN_TICKETS_FOR_ALERTS == 5

    def test_metric_below_checks(self):
        assert METRIC_BELOW_CHECKS["resolution_rate"] == "below"
        assert METRIC_BELOW_CHECKS["avg_confidence"] == "below"
        assert METRIC_BELOW_CHECKS["avg_csat"] == "below"
        assert METRIC_BELOW_CHECKS["escalation_rate"] == "above"


# ═══════════════════════════════════════════════════════════════════
# 2. get_metrics
# ═══════════════════════════════════════════════════════════════════


class TestGetMetrics:
    def test_valid_period(self, service, mock_db, company_id):
        """Should return metrics for a valid period."""
        today = date.today()
        metrics_rows = [
            _make_daily_metric(metric_date=today - timedelta(days=i))
            for i in range(6, 0, -1)
        ]

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = metrics_rows

        result = service.get_metrics(
            agent_id="agent-001",
            company_id=company_id,
            period="7d",
        )

        assert result["agent_id"] == "agent-001"
        assert result["period"] == "7d"
        assert result["granularity"] == "daily"
        assert len(result["data_points"]) == 6
        assert result["summary"]["total_tickets"] == 120  # 6 days * 20 tickets

    def test_invalid_period_raises(self, service, company_id):
        with pytest.raises(ValidationError) as exc_info:
            service.get_metrics(
                agent_id="agent-001",
                company_id=company_id,
                period="1y",
            )
        assert "Invalid period" in exc_info.value.message

    def test_invalid_granularity_raises(self, service, company_id):
        with pytest.raises(ValidationError) as exc_info:
            service.get_metrics(
                agent_id="agent-001",
                company_id=company_id,
                period="7d",
                granularity="monthly",
            )
        assert "Invalid granularity" in exc_info.value.message

    def test_insufficient_data(self, service, mock_db, company_id):
        """Should flag insufficient_data when tickets < 5."""
        metrics_rows = [
            _make_daily_metric(tickets_handled=2, resolved_count=1)
        ]

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = metrics_rows

        result = service.get_metrics(
            agent_id="agent-001",
            company_id=company_id,
            period="7d",
        )

        assert result["insufficient_data"] is True

    def test_daily_granularity(self, service, mock_db, company_id):
        """Should return one data point per day."""
        today = date.today()
        metrics_rows = [
            _make_daily_metric(metric_date=today - timedelta(days=i))
            for i in range(3, 0, -1)
        ]

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = metrics_rows

        result = service.get_metrics(
            agent_id="agent-001",
            company_id=company_id,
            period="7d",
            granularity="daily",
        )

        assert len(result["data_points"]) == 3
        for dp in result["data_points"]:
            assert "date" in dp
            assert "resolution_rate" in dp
            assert "avg_confidence" in dp
            assert "avg_csat" in dp
            assert "escalation_rate" in dp
            assert "avg_handle_time" in dp
            assert "tickets_handled" in dp

    def test_weekly_aggregation(self, service, mock_db, company_id):
        """Should aggregate data into weekly buckets."""
        today = date.today()
        # Create 10 days of data spanning 2 weeks
        metrics_rows = [
            _make_daily_metric(metric_date=today - timedelta(days=i))
            for i in range(10, 0, -1)
        ]

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = metrics_rows

        result = service.get_metrics(
            agent_id="agent-001",
            company_id=company_id,
            period="14d",
            granularity="weekly",
        )

        assert len(result["data_points"]) >= 1
        # Weekly keys should be in ISO week format
        for dp in result["data_points"]:
            assert "W" in dp["date"]

    def test_empty_data_returns_safe_default(
            self, service, mock_db, company_id):
        """Should return safe defaults when no data."""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = []

        result = service.get_metrics(
            agent_id="agent-001",
            company_id=company_id,
            period="7d",
        )

        assert result["data_points"] == []
        assert result["summary"]["total_tickets"] == 0
        assert result["insufficient_data"] is True


# ═══════════════════════════════════════════════════════════════════
# 3. get_thresholds
# ═══════════════════════════════════════════════════════════════════


class TestGetThresholds:
    def test_get_existing_thresholds(self, service, mock_db, company_id):
        """Should return existing thresholds."""
        threshold = _make_threshold()

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = threshold

        result = service.get_thresholds(
            agent_id="agent-001",
            company_id=company_id,
        )

        assert result["agent_id"] == "agent-001"
        assert result["resolution_rate_min"] == 70.0
        assert result["confidence_min"] == 65.0
        assert result["csat_min"] == 3.5
        assert result["escalation_max_pct"] == 15.0

    def test_create_default_when_missing(self, service, mock_db, company_id):
        """Should create default thresholds when none exist."""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = service.get_thresholds(
            agent_id="agent-001",
            company_id=company_id,
        )

        # Should have called db.add to create defaults
        mock_db.add.assert_called_once()
        assert result["resolution_rate_min"] == 70.0
        assert result["confidence_min"] == 65.0


# ═══════════════════════════════════════════════════════════════════
# 4. update_thresholds
# ═══════════════════════════════════════════════════════════════════


class TestUpdateThresholds:
    def test_update_valid_fields(self, service, mock_db, company_id):
        """Should update valid threshold fields."""
        threshold = _make_threshold()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = threshold

        result = service.update_thresholds(
            agent_id="agent-001",
            company_id=company_id,
            updates={"resolution_rate_min": 80.0},
        )

        assert result["resolution_rate_min"] == 80.0
        assert result["confidence_min"] == 65.0  # Unchanged

    def test_warn_on_impossible_csat(self, service, mock_db, company_id):
        """Should warn when csat_min > 5.0."""
        threshold = _make_threshold()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = threshold

        result = service.update_thresholds(
            agent_id="agent-001",
            company_id=company_id,
            updates={"csat_min": 7.0},
        )

        assert result["csat_min"] == 7.0
        assert "warnings" in result
        assert len(result["warnings"]) == 1
        assert "impossible" in result["warnings"][0].lower()

    def test_invalid_key_raises(self, service, company_id):
        """Should raise ValidationError for invalid keys."""
        with pytest.raises(ValidationError) as exc_info:
            service.update_thresholds(
                agent_id="agent-001",
                company_id=company_id,
                updates={"not_a_real_key": 42.0},
            )
        assert "Invalid threshold keys" in exc_info.value.message


# ═══════════════════════════════════════════════════════════════════
# 5. compare_agents
# ═══════════════════════════════════════════════════════════════════


class TestCompareAgents:
    def test_compare_three_agents(self, service, mock_db, company_id):
        """Should return summaries for 3 agents with sufficient tickets."""
        today = date.today()

        # Mock daily metrics for each agent
        def make_side_effect(agent_id):
            metrics_rows = [
                _make_daily_metric(
                    agent_id=agent_id,
                    metric_date=today - timedelta(days=i),
                )
                for i in range(6, 0, -1)
            ]
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = metrics_rows
            return mock_q

        mock_db.query.side_effect = [
            make_side_effect("agent-001"),
            make_side_effect("agent-002"),
            make_side_effect("agent-003"),
        ]

        result = service.compare_agents(
            agent_ids=["agent-001", "agent-002", "agent-003"],
            company_id=company_id,
            period="7d",
        )

        assert len(result) == 3
        for r in result:
            assert "agent_id" in r
            assert "trend" in r
            assert r["total_tickets"] >= MIN_TICKETS_FOR_ALERTS if "total_tickets" in r else True

    def test_exclude_low_ticket_agents(self, service, mock_db, company_id):
        """Should exclude agents with fewer than 5 tickets."""
        # Agent with only 3 tickets (insufficient)
        metrics_rows = [
            _make_daily_metric(tickets_handled=1, resolved_count=1),
        ]

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = metrics_rows

        result = service.compare_agents(
            agent_ids=["agent-low-tickets"],
            company_id=company_id,
        )

        assert len(result) == 0

    def test_empty_agent_ids(self, service, company_id):
        """Should return empty list for empty agent_ids."""
        result = service.compare_agents(
            agent_ids=[],
            company_id=company_id,
        )
        assert result == []


# ═══════════════════════════════════════════════════════════════════
# 6. compute_and_store_daily_metrics
# ═══════════════════════════════════════════════════════════════════


class TestComputeDailyMetrics:
    @patch("app.services.agent_metrics_service.AgentMetricsService._compute_agent_daily_metrics")
    def test_compute_for_active_agent(
        self, mock_compute, service, mock_db, company_id,
    ):
        """Should compute metrics for all active agents."""
        agent = _make_agent(agent_id="agent-001", status="active")
        mock_compute.return_value = {
            "tickets_handled": 25,
            "resolved_count": 20,
            "escalated_count": 2,
            "avg_confidence": Decimal("80.0"),
            "avg_csat": Decimal("4.3"),
            "avg_handle_time_seconds": 120,
            "resolution_rate": Decimal("80.0"),
            "escalation_rate": Decimal("8.0"),
        }

        # Mock agent query
        mock_agent_query = MagicMock()
        mock_db.query.return_value = mock_agent_query
        mock_agent_query.filter.return_value = [agent]

        # Mock no existing daily metric (for insert path)
        mock_dm_query = MagicMock()
        mock_dm_query.filter.return_value.first.return_value = None
        mock_db.query.side_effect = [
            mock_agent_query.filter.return_value,  # agents
            mock_dm_query,  # existing daily metric check
        ]
        mock_db.query.return_value = mock_agent_query
        mock_agent_query.filter.return_value = [agent]

        result = service.compute_and_store_daily_metrics(company_id)

        assert result["company_id"] == company_id
        assert result["agents_processed"] == 1
        assert result["errors"] == 0

    @patch("app.services.agent_metrics_service.AgentMetricsService._compute_agent_daily_metrics")
    def test_handle_paused_agent(
        self, mock_compute, service, mock_db, company_id,
    ):
        """Should skip paused agents (only active are queried)."""
        agent = _make_agent(agent_id="agent-001", status="paused")

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = [agent]

        result = service.compute_and_store_daily_metrics(company_id)

        # Paused agent should NOT be in filter result since
        # the filter checks Agent.status == "active"
        mock_compute.assert_not_called()

    def test_error_fallback(self, service, mock_db, company_id):
        """Should return safe dict on DB error."""
        mock_db.query.side_effect = Exception("DB connection lost")

        result = service.compute_and_store_daily_metrics(company_id)

        assert result["agents_processed"] == 0
        assert result["errors"] == 1
        assert result["metrics"] == []


# ═══════════════════════════════════════════════════════════════════
# 7. evaluate_alerts
# ═══════════════════════════════════════════════════════════════════


class TestEvaluateAlerts:
    def test_new_alert_created(self, service, mock_db, company_id):
        """Should create alert when metric is below threshold for 2+ days."""
        agent = _make_agent(agent_id="agent-001", status="active")
        threshold = _make_threshold(agent_id="agent-001")

        yesterday = date.today() - timedelta(days=1)
        day_before = date.today() - timedelta(days=2)

        # Two days of low resolution rate
        dm1 = _make_daily_metric(
            agent_id="agent-001",
            metric_date=yesterday,
            resolution_rate=55.0,  # Below 70% threshold
            tickets_handled=20,
        )
        dm2 = _make_daily_metric(
            agent_id="agent-001",
            metric_date=day_before,
            resolution_rate=50.0,  # Below 70% threshold
            tickets_handled=20,
        )

        # Setup mock queries
        mock_agent_query = MagicMock()
        mock_agent_query.filter.return_value = [agent]

        mock_thresh_query = MagicMock()
        mock_thresh_query.filter.return_value.first.return_value = threshold

        mock_dm_query = MagicMock()
        mock_dm_query.filter.return_value.order_by.return_value = [dm1, dm2]

        mock_alert_query = MagicMock()
        mock_alert_query.filter.return_value.first.return_value = None

        # Chain of queries: agents, threshold, daily metrics, alert check
        call_count = [0]

        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_agent_query
            elif call_count[0] == 2:
                return mock_thresh_query
            elif call_count[0] == 3:
                return mock_dm_query
            elif call_count[0] == 4:
                return mock_alert_query
            else:
                return mock_alert_query

        mock_db.query.side_effect = query_side_effect

        result = service.evaluate_alerts(company_id)

        # Should create a new alert for resolution_rate
        created = [r for r in result if r.get("action") == "created"]
        assert len(created) >= 1
        assert created[0]["metric_name"] == "resolution_rate"

    def test_consecutive_days_increment(self, service, mock_db, company_id):
        """Should increment consecutive_days_below on existing alert."""
        agent = _make_agent(agent_id="agent-001", status="active")
        threshold = _make_threshold(agent_id="agent-001")

        yesterday = date.today() - timedelta(days=1)
        day_before = date.today() - timedelta(days=2)

        dm1 = _make_daily_metric(
            agent_id="agent-001",
            metric_date=yesterday,
            resolution_rate=55.0,
            tickets_handled=20,
        )
        dm2 = _make_daily_metric(
            agent_id="agent-001",
            metric_date=day_before,
            resolution_rate=50.0,
            tickets_handled=20,
        )

        # Existing alert
        existing_alert = MagicMock()
        existing_alert.id = "alert-001"
        existing_alert.status = "active"

        mock_agent_query = MagicMock()
        mock_agent_query.filter.return_value = [agent]

        mock_thresh_query = MagicMock()
        mock_thresh_query.filter.return_value.first.return_value = threshold

        mock_dm_query = MagicMock()
        mock_dm_query.filter.return_value.order_by.return_value = [dm1, dm2]

        mock_alert_query = MagicMock()
        mock_alert_query.filter.return_value.first.return_value = existing_alert

        call_count = [0]

        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_agent_query
            elif call_count[0] == 2:
                return mock_thresh_query
            elif call_count[0] == 3:
                return mock_dm_query
            else:
                return mock_alert_query

        mock_db.query.side_effect = query_side_effect

        result = service.evaluate_alerts(company_id)

        updated = [r for r in result if r.get("action") == "updated"]
        assert len(updated) >= 1
        assert existing_alert.consecutive_days_below == 2

    def test_alert_resolved_when_metric_recovers(
            self, service, mock_db, company_id):
        """Should resolve active alert when metric recovers."""
        agent = _make_agent(agent_id="agent-001", status="active")
        threshold = _make_threshold(agent_id="agent-001")

        yesterday = date.today() - timedelta(days=1)
        # Metric recovered above threshold
        dm1 = _make_daily_metric(
            agent_id="agent-001",
            metric_date=yesterday,
            resolution_rate=85.0,  # Above 70% — recovered!
            tickets_handled=20,
        )

        existing_alert = MagicMock()
        existing_alert.id = "alert-001"
        existing_alert.status = "active"

        mock_agent_query = MagicMock()
        mock_agent_query.filter.return_value = [agent]

        mock_thresh_query = MagicMock()
        mock_thresh_query.filter.return_value.first.return_value = threshold

        mock_dm_query = MagicMock()
        mock_dm_query.filter.return_value.order_by.return_value = [dm1]

        mock_alert_query = MagicMock()
        mock_alert_query.filter.return_value.first.return_value = existing_alert

        call_count = [0]

        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_agent_query
            elif call_count[0] == 2:
                return mock_thresh_query
            elif call_count[0] == 3:
                return mock_dm_query
            else:
                return mock_alert_query

        mock_db.query.side_effect = query_side_effect

        result = service.evaluate_alerts(company_id)

        resolved = [r for r in result if r.get("action") == "resolved"]
        assert len(resolved) >= 1

    def test_no_alert_for_one_day(self, service, mock_db, company_id):
        """Should NOT create alert if breach is only 1 day."""
        agent = _make_agent(agent_id="agent-001", status="active")
        threshold = _make_threshold(agent_id="agent-001")

        yesterday = date.today() - timedelta(days=1)
        dm1 = _make_daily_metric(
            agent_id="agent-001",
            metric_date=yesterday,
            resolution_rate=55.0,
            tickets_handled=20,
        )

        mock_agent_query = MagicMock()
        mock_agent_query.filter.return_value = [agent]

        mock_thresh_query = MagicMock()
        mock_thresh_query.filter.return_value.first.return_value = threshold

        mock_dm_query = MagicMock()
        mock_dm_query.filter.return_value.order_by.return_value = [dm1]

        mock_alert_query = MagicMock()
        mock_alert_query.filter.return_value.first.return_value = None

        call_count = [0]

        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_agent_query
            elif call_count[0] == 2:
                return mock_thresh_query
            elif call_count[0] == 3:
                return mock_dm_query
            else:
                return mock_alert_query

        mock_db.query.side_effect = query_side_effect

        result = service.evaluate_alerts(company_id)

        # Only 1 day below threshold — should NOT create alert
        created = [r for r in result if r.get("action") == "created"]
        # Should be 0 because CONSECUTIVE_DAYS_THRESHOLD = 2
        assert len(created) == 0


# ═══════════════════════════════════════════════════════════════════
# 8. Trend Determination
# ═══════════════════════════════════════════════════════════════════


class TestTrendDetermination:
    def test_up_trend(self):
        values = [60.0, 65.0, 70.0, 75.0, 80.0, 85.0]
        assert AgentMetricsService._determine_trend(values) == "up"

    def test_down_trend(self):
        values = [90.0, 85.0, 80.0, 75.0, 70.0, 65.0]
        assert AgentMetricsService._determine_trend(values) == "down"

    def test_stable_trend(self):
        values = [70.0, 70.5, 69.8, 70.2, 70.1, 69.9]
        assert AgentMetricsService._determine_trend(values) == "stable"

    def test_single_value(self):
        assert AgentMetricsService._determine_trend([75.0]) == "stable"

    def test_two_values_increasing(self):
        assert AgentMetricsService._determine_trend([70.0, 80.0]) == "up"

    def test_two_values_decreasing(self):
        assert AgentMetricsService._determine_trend([80.0, 70.0]) == "down"

    def test_empty_list(self):
        assert AgentMetricsService._determine_trend([]) == "stable"


# ═══════════════════════════════════════════════════════════════════
# 9. Helper methods
# ═══════════════════════════════════════════════════════════════════


class TestHelpers:
    def test_aggregate_weekly(self, service):
        """Should aggregate daily points into weekly buckets."""
        data_points = [
            {
                "date": (date.today() - timedelta(days=i)).isoformat(),
                "resolution_rate": 70.0 + i,
                "avg_confidence": 75.0 + i,
                "avg_csat": 4.0,
                "escalation_rate": 15.0 - i,
                "avg_handle_time": 120,
                "tickets_handled": 20,
            }
            for i in range(7)
        ]
        result = service._aggregate_weekly(data_points)
        assert len(result) >= 1

    def test_aggregate_weekly_empty(self, service):
        """Should return empty for no data points."""
        assert service._aggregate_weekly([]) == []

    def test_check_threshold_breach_below(self, service):
        """Should detect breach when value is below threshold."""
        threshold = _make_threshold(resolution_rate_min=70.0)
        assert service._check_threshold_breach(
            "agent-001", "co-1", "resolution_rate", 55.0, threshold,
        ) is True
        assert service._check_threshold_breach(
            "agent-001", "co-1", "resolution_rate", 80.0, threshold,
        ) is False

    def test_check_threshold_breach_above(self, service):
        """Should detect breach when escalation_rate is above threshold."""
        threshold = _make_threshold(escalation_max_pct=15.0)
        assert service._check_threshold_breach(
            "agent-001", "co-1", "escalation_rate", 25.0, threshold,
        ) is True
        assert service._check_threshold_breach(
            "agent-001", "co-1", "escalation_rate", 10.0, threshold,
        ) is False
