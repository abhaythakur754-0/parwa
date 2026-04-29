"""
PARWA Agent Metrics Service (F-098)

Service for computing, storing, and evaluating AI agent performance
metrics. Provides daily metric aggregation, threshold management,
agent comparison, and automated alert evaluation.

Methods:
- get_metrics()                   — Historical metrics for an agent
- get_thresholds()                — Get threshold config for an agent
- update_thresholds()             — Update threshold config
- compare_agents()                — Compare metrics across agents
- compute_and_store_daily_metrics() — Celery task: compute yesterday's metrics
- evaluate_alerts()               — Celery task: check threshold breaches

Building Codes: BC-001 (multi-tenant), BC-012 (graceful errors)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.logger import get_logger

logger = get_logger("agent_metrics_service")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

DEFAULT_THRESHOLDS = {
    "resolution_rate_min": 70.0,
    "confidence_min": 65.0,
    "csat_min": 3.5,
    "escalation_max_pct": 15.0,
}

MIN_TICKETS_FOR_ALERTS = 5
CONSECUTIVE_DAYS_THRESHOLD = 2

VALID_PERIODS = {"7d": 7, "14d": 14, "30d": 30, "90d": 90}
VALID_GRANULARITIES = {"daily", "weekly"}

# Metric name → whether breach is "below" or "above" the threshold
METRIC_BELOW_CHECKS = {
    "resolution_rate": "below",
    "avg_confidence": "below",
    "avg_csat": "below",
    "escalation_rate": "above",
}


# ══════════════════════════════════════════════════════════════════
# SERVICE CLASS
# ══════════════════════════════════════════════════════════════════


class AgentMetricsService:
    """Agent Metrics Service (F-098).

    Computes, stores, and evaluates AI agent performance metrics.
    All queries are scoped by company_id (BC-001) and wrapped in
    try/except with safe defaults (BC-012).
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Public API ────────────────────────────────────────────

    def get_metrics(
        self,
        agent_id: str,
        company_id: str,
        period: str = "7d",
        granularity: str = "daily",
    ) -> Dict[str, Any]:
        """Return historical metrics for an agent.

        Args:
            agent_id: Agent UUID.
            company_id: Tenant UUID (BC-001).
            period: Time period key (7d, 14d, 30d, 90d).
            granularity: Aggregation level (daily, weekly).

        Returns:
            Dict with agent_id, period, granularity, data_points,
            summary, and optional insufficient_data flag.

        Raises:
            ValidationError: If period or granularity is invalid.
        """
        from app.exceptions import ValidationError

        # Validate period
        if period not in VALID_PERIODS:
            raise ValidationError(
                message=f"Invalid period: {period}. " f"Must be one of {
                    list(
                        VALID_PERIODS.keys())}",
                details={"field": "period", "valid_values": list(VALID_PERIODS.keys())},
            )

        # Validate granularity
        if granularity not in VALID_GRANULARITIES:
            raise ValidationError(
                message=f"Invalid granularity: {granularity}. " f"Must be one of {
                    list(VALID_GRANULARITIES)}",
                details={
                    "field": "granularity",
                    "valid_values": list(VALID_GRANULARITIES),
                },
            )

        try:
            from database.models.agent_metrics import AgentMetricsDaily

            days = VALID_PERIODS[period]
            end_date = date.today()
            start_date = end_date - timedelta(days=days - 1)

            rows = (
                self.db.query(AgentMetricsDaily)
                .filter(
                    AgentMetricsDaily.agent_id == agent_id,
                    AgentMetricsDaily.company_id == company_id,
                    AgentMetricsDaily.date >= start_date,
                    AgentMetricsDaily.date <= end_date,
                )
                .order_by(AgentMetricsDaily.date.asc())
                .all()
            )

            data_points: List[Dict[str, Any]] = []
            for row in rows:
                data_points.append(
                    {
                        "date": row.date.isoformat() if row.date else None,
                        "resolution_rate": (
                            float(row.resolution_rate)
                            if row.resolution_rate is not None
                            else None
                        ),
                        "avg_confidence": (
                            float(row.avg_confidence)
                            if row.avg_confidence is not None
                            else None
                        ),
                        "avg_csat": (
                            float(row.avg_csat) if row.avg_csat is not None else None
                        ),
                        "escalation_rate": (
                            float(row.escalation_rate)
                            if row.escalation_rate is not None
                            else None
                        ),
                        "avg_handle_time": (
                            int(row.avg_handle_time_seconds)
                            if row.avg_handle_time_seconds is not None
                            else None
                        ),
                        "tickets_handled": row.tickets_handled or 0,
                    }
                )

            # Aggregate by week if requested
            if granularity == "weekly" and data_points:
                data_points = self._aggregate_weekly(data_points)

            # Compute summary
            total_tickets = sum(dp.get("tickets_handled", 0) for dp in data_points)
            resolution_rates = [
                dp["resolution_rate"]
                for dp in data_points
                if dp.get("resolution_rate") is not None
            ]
            confidences = [
                dp["avg_confidence"]
                for dp in data_points
                if dp.get("avg_confidence") is not None
            ]
            csats = [
                dp["avg_csat"] for dp in data_points if dp.get("avg_csat") is not None
            ]
            escalation_rates = [
                dp["escalation_rate"]
                for dp in data_points
                if dp.get("escalation_rate") is not None
            ]

            summary = {
                "avg_resolution_rate": (
                    round(sum(resolution_rates) / len(resolution_rates), 2)
                    if resolution_rates
                    else None
                ),
                "avg_confidence": (
                    round(sum(confidences) / len(confidences), 2)
                    if confidences
                    else None
                ),
                "avg_csat": (round(sum(csats) / len(csats), 1) if csats else None),
                "avg_escalation_rate": (
                    round(sum(escalation_rates) / len(escalation_rates), 2)
                    if escalation_rates
                    else None
                ),
                "total_tickets": total_tickets,
            }

            result = {
                "agent_id": agent_id,
                "period": period,
                "granularity": granularity,
                "data_points": data_points,
                "summary": summary,
            }

            # Flag insufficient data
            if total_tickets < MIN_TICKETS_FOR_ALERTS:
                result["insufficient_data"] = True

            return result

        except ValidationError:
            raise
        except Exception as exc:
            logger.error(
                "get_metrics_error",
                company_id=company_id,
                agent_id=agent_id,
                error=str(exc),
            )
            return {
                "agent_id": agent_id,
                "period": period,
                "granularity": granularity,
                "data_points": [],
                "summary": {
                    "avg_resolution_rate": None,
                    "avg_confidence": None,
                    "avg_csat": None,
                    "avg_escalation_rate": None,
                    "total_tickets": 0,
                },
                "insufficient_data": True,
            }

    def get_thresholds(
        self,
        agent_id: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """Get threshold configuration for an agent.

        Creates default thresholds if none exist.

        Args:
            agent_id: Agent UUID.
            company_id: Tenant UUID (BC-001).

        Returns:
            Dict with threshold values.
        """
        try:
            threshold = self._get_or_create_thresholds(agent_id, company_id)
            return {
                "agent_id": agent_id,
                "resolution_rate_min": float(threshold.resolution_rate_min),
                "confidence_min": float(threshold.confidence_min),
                "csat_min": float(threshold.csat_min),
                "escalation_max_pct": float(threshold.escalation_max_pct),
            }
        except Exception as exc:
            logger.error(
                "get_thresholds_error",
                company_id=company_id,
                agent_id=agent_id,
                error=str(exc),
            )
            return {
                "agent_id": agent_id,
                **DEFAULT_THRESHOLDS,
            }

    def update_thresholds(
        self,
        agent_id: str,
        company_id: str,
        updates: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update threshold configuration for an agent.

        Args:
            agent_id: Agent UUID.
            company_id: Tenant UUID (BC-001).
            updates: Dict of threshold fields to update.
            user_id: Optional user performing the update.

        Returns:
            Updated threshold dict with warnings if any.

        Raises:
            ValidationError: If invalid keys are provided.
        """
        from app.exceptions import ValidationError

        valid_keys = set(DEFAULT_THRESHOLDS.keys())
        warnings: List[str] = []

        # Validate keys
        provided_keys = set(updates.keys())
        invalid_keys = provided_keys - valid_keys
        if invalid_keys:
            raise ValidationError(
                message=f"Invalid threshold keys: {invalid_keys}",
                details={
                    "field": "thresholds",
                    "valid_keys": list(valid_keys),
                    "invalid_keys": list(invalid_keys),
                },
            )

        # Warn on impossible CSAT > 5.0
        if "csat_min" in updates and updates["csat_min"] > 5.0:
            warnings.append(
                "csat_min > 5.0 is impossible on a 5-point CSAT scale. "
                "Value accepted but may indicate a configuration error."
            )

        try:
            threshold = self._get_or_create_thresholds(agent_id, company_id)
            now = datetime.utcnow()

            if "resolution_rate_min" in updates:
                threshold.resolution_rate_min = Decimal(
                    str(updates["resolution_rate_min"])
                )
            if "confidence_min" in updates:
                threshold.confidence_min = Decimal(str(updates["confidence_min"]))
            if "csat_min" in updates:
                threshold.csat_min = Decimal(str(updates["csat_min"]))
            if "escalation_max_pct" in updates:
                threshold.escalation_max_pct = Decimal(
                    str(updates["escalation_max_pct"])
                )

            threshold.updated_at = now
            self.db.flush()

            logger.info(
                "thresholds_updated",
                company_id=company_id,
                agent_id=agent_id,
                user_id=user_id,
                updates=updates,
            )

            result = {
                "agent_id": agent_id,
                "resolution_rate_min": float(threshold.resolution_rate_min),
                "confidence_min": float(threshold.confidence_min),
                "csat_min": float(threshold.csat_min),
                "escalation_max_pct": float(threshold.escalation_max_pct),
            }

            if warnings:
                result["warnings"] = warnings

            return result

        except ValidationError:
            raise
        except Exception as exc:
            logger.error(
                "update_thresholds_error",
                company_id=company_id,
                agent_id=agent_id,
                error=str(exc),
            )
            raise

    def compare_agents(
        self,
        agent_ids: List[str],
        company_id: str,
        period: str = "30d",
    ) -> List[Dict[str, Any]]:
        """Compare metrics across multiple agents.

        Args:
            agent_ids: List of agent UUIDs.
            company_id: Tenant UUID (BC-001).
            period: Time period key.

        Returns:
            List of per-agent summary dicts with trend indicators.
            Excludes agents with fewer than 5 tickets.
        """
        if not agent_ids:
            return []

        results: List[Dict[str, Any]] = []

        for agent_id in agent_ids:
            try:
                metrics = self.get_metrics(
                    agent_id=agent_id,
                    company_id=company_id,
                    period=period,
                    granularity="daily",
                )

                summary = metrics.get("summary", {})
                total_tickets = summary.get("total_tickets", 0)

                # Exclude agents with insufficient data
                if total_tickets < MIN_TICKETS_FOR_ALERTS:
                    continue

                # Determine trend from resolution rate
                data_points = metrics.get("data_points", [])
                resolution_values = [
                    dp["resolution_rate"]
                    for dp in data_points
                    if dp.get("resolution_rate") is not None
                ]
                trend = self._determine_trend(resolution_values)

                results.append(
                    {
                        "agent_id": agent_id,
                        **summary,
                        "trend": trend,
                        "data_point_count": len(data_points),
                    }
                )

            except Exception as exc:
                logger.warning(
                    "compare_agents_skip_error",
                    company_id=company_id,
                    agent_id=agent_id,
                    error=str(exc),
                )
                continue

        return results

    def compute_and_store_daily_metrics(
        self,
        company_id: str,
    ) -> Dict[str, Any]:
        """Compute and store yesterday's metrics for all active agents.

        Designed to run as a Celery task.

        Args:
            company_id: Tenant UUID (BC-001).

        Returns:
            Summary dict with computed metrics per agent.
        """
        try:
            from database.models.agent import Agent
            from database.models.agent_metrics import AgentMetricsDaily

            yesterday = date.today() - timedelta(days=1)
            agents = (
                self.db.query(Agent)
                .filter(
                    Agent.company_id == company_id,
                    Agent.status == "active",
                )
                .all()
            )

            computed: List[Dict[str, Any]] = []
            errors: int = 0

            for agent in agents:
                try:
                    metrics = self._compute_agent_daily_metrics(
                        agent=agent,
                        target_date=yesterday,
                        company_id=company_id,
                    )

                    # Upsert: check if record already exists
                    existing = (
                        self.db.query(AgentMetricsDaily)
                        .filter(
                            AgentMetricsDaily.agent_id == agent.id,
                            AgentMetricsDaily.company_id == company_id,
                            AgentMetricsDaily.date == yesterday,
                        )
                        .first()
                    )

                    if existing:
                        existing.tickets_handled = metrics["tickets_handled"]
                        existing.resolved_count = metrics["resolved_count"]
                        existing.escalated_count = metrics["escalated_count"]
                        existing.avg_confidence = metrics.get("avg_confidence")
                        existing.avg_csat = metrics.get("avg_csat")
                        existing.avg_handle_time_seconds = metrics.get(
                            "avg_handle_time_seconds"
                        )
                        existing.resolution_rate = metrics.get("resolution_rate")
                        existing.escalation_rate = metrics.get("escalation_rate")
                    else:
                        record = AgentMetricsDaily(
                            agent_id=agent.id,
                            company_id=company_id,
                            date=yesterday,
                            tickets_handled=metrics["tickets_handled"],
                            resolved_count=metrics["resolved_count"],
                            escalated_count=metrics["escalated_count"],
                            avg_confidence=metrics.get("avg_confidence"),
                            avg_csat=metrics.get("avg_csat"),
                            avg_handle_time_seconds=metrics.get(
                                "avg_handle_time_seconds"
                            ),
                            resolution_rate=metrics.get("resolution_rate"),
                            escalation_rate=metrics.get("escalation_rate"),
                        )
                        self.db.add(record)

                    computed.append(
                        {
                            "agent_id": agent.id,
                            "agent_name": agent.name,
                            "date": yesterday.isoformat(),
                            **metrics,
                        }
                    )

                except Exception as exc:
                    errors += 1
                    logger.error(
                        "compute_daily_metrics_agent_error",
                        company_id=company_id,
                        agent_id=agent.id,
                        error=str(exc),
                    )
                    continue

            self.db.flush()

            return {
                "company_id": company_id,
                "date": yesterday.isoformat(),
                "agents_processed": len(computed),
                "errors": errors,
                "metrics": computed,
            }

        except Exception as exc:
            logger.error(
                "compute_daily_metrics_error",
                company_id=company_id,
                error=str(exc),
            )
            return {
                "company_id": company_id,
                "date": (date.today() - timedelta(days=1)).isoformat(),
                "agents_processed": 0,
                "errors": 1,
                "metrics": [],
            }

    def evaluate_alerts(
        self,
        company_id: str,
    ) -> List[Dict[str, Any]]:
        """Evaluate agent metrics against thresholds and manage alerts.

        Checks if any metric has been below threshold for 2+ consecutive
        days. Creates new alerts or updates existing ones.

        Designed to run as a Celery task.

        Args:
            company_id: Tenant UUID (BC-001).

        Returns:
            List of new/updated alert dicts.
        """
        try:
            from database.models.agent import Agent
            from database.models.agent_metrics import (
                AgentMetricThreshold,
                AgentMetricsDaily,
                AgentPerformanceAlert,
            )

            alerts_result: List[Dict[str, Any]] = []

            # Get all active agents with thresholds
            agents = (
                self.db.query(Agent)
                .filter(
                    Agent.company_id == company_id,
                    Agent.status == "active",
                )
                .all()
            )

            yesterday = date.today() - timedelta(days=1)

            for agent in agents:
                try:
                    threshold = (
                        self.db.query(AgentMetricThreshold)
                        .filter(
                            AgentMetricThreshold.company_id == company_id,
                            AgentMetricThreshold.agent_id == agent.id,
                        )
                        .first()
                    )

                    if not threshold:
                        continue

                    # Get recent metrics (last 7 days for evaluation)
                    seven_days_ago = yesterday - timedelta(days=6)
                    daily_metrics = (
                        self.db.query(AgentMetricsDaily)
                        .filter(
                            AgentMetricsDaily.agent_id == agent.id,
                            AgentMetricsDaily.company_id == company_id,
                            AgentMetricsDaily.date >= seven_days_ago,
                            AgentMetricsDaily.date <= yesterday,
                        )
                        .order_by(AgentMetricsDaily.date.desc())
                        .all()
                    )

                    if not daily_metrics:
                        continue

                    # Map metric names to threshold values
                    metric_threshold_map = {
                        "resolution_rate": float(threshold.resolution_rate_min),
                        "avg_confidence": float(threshold.confidence_min),
                        "avg_csat": float(threshold.csat_min),
                        "escalation_rate": float(threshold.escalation_max_pct),
                    }

                    for metric_name, threshold_val in metric_threshold_map.items():
                        consecutive_below = 0
                        latest_value = None

                        for dm in daily_metrics:
                            value = getattr(dm, metric_name, None)
                            if value is None:
                                # Gap in data — reset streak
                                break
                            value = float(value)
                            if metric_name == "escalation_rate":
                                # For escalation_rate, breach is ABOVE
                                # threshold
                                if value > threshold_val:
                                    consecutive_below += 1
                                else:
                                    break
                            else:
                                # For other metrics, breach is BELOW threshold
                                if value < threshold_val:
                                    consecutive_below += 1
                                else:
                                    break

                        if consecutive_below == 0:
                            # Metric recovered — resolve any active alerts
                            active_alert = (
                                self.db.query(
                                    AgentPerformanceAlert,
                                )
                                .filter(
                                    AgentPerformanceAlert.company_id == company_id,
                                    AgentPerformanceAlert.agent_id == agent.id,
                                    AgentPerformanceAlert.metric_name == metric_name,
                                    AgentPerformanceAlert.status == "active",
                                )
                                .first()
                            )

                            if active_alert:
                                active_alert.status = "resolved"
                                active_alert.resolved_at = datetime.utcnow()
                                alerts_result.append(
                                    {
                                        "alert_id": active_alert.id,
                                        "agent_id": agent.id,
                                        "metric_name": metric_name,
                                        "action": "resolved",
                                    }
                                )
                            continue

                        # Get the latest value for the alert
                        latest_dm = daily_metrics[0]
                        latest_value = float(getattr(latest_dm, metric_name, 0))

                        # Check minimum ticket threshold for first entry
                        total_tickets = sum(
                            dm.tickets_handled or 0 for dm in daily_metrics
                        )
                        if total_tickets < MIN_TICKETS_FOR_ALERTS:
                            continue

                        # Check if an active alert already exists
                        existing_alert = (
                            self.db.query(
                                AgentPerformanceAlert,
                            )
                            .filter(
                                AgentPerformanceAlert.company_id == company_id,
                                AgentPerformanceAlert.agent_id == agent.id,
                                AgentPerformanceAlert.metric_name == metric_name,
                                AgentPerformanceAlert.status == "active",
                            )
                            .first()
                        )

                        if existing_alert:
                            existing_alert.current_value = Decimal(str(latest_value))
                            existing_alert.consecutive_days_below = consecutive_below
                            self.db.flush()
                            alerts_result.append(
                                {
                                    "alert_id": existing_alert.id,
                                    "agent_id": agent.id,
                                    "metric_name": metric_name,
                                    "action": "updated",
                                    "consecutive_days_below": consecutive_below,
                                }
                            )
                        elif consecutive_below >= CONSECUTIVE_DAYS_THRESHOLD:
                            # Create new alert
                            new_alert = AgentPerformanceAlert(
                                company_id=company_id,
                                agent_id=agent.id,
                                metric_name=metric_name,
                                current_value=Decimal(str(latest_value)),
                                threshold_value=Decimal(str(threshold_val)),
                                consecutive_days_below=consecutive_below,
                                status="active",
                            )
                            self.db.add(new_alert)
                            self.db.flush()
                            alerts_result.append(
                                {
                                    "alert_id": new_alert.id,
                                    "agent_id": agent.id,
                                    "metric_name": metric_name,
                                    "action": "created",
                                    "consecutive_days_below": consecutive_below,
                                }
                            )

                except Exception as exc:
                    logger.error(
                        "evaluate_alerts_agent_error",
                        company_id=company_id,
                        agent_id=agent.id,
                        error=str(exc),
                    )
                    continue

            return alerts_result

        except Exception as exc:
            logger.error(
                "evaluate_alerts_error",
                company_id=company_id,
                error=str(exc),
            )
            return []

    # ── Private Helpers ───────────────────────────────────────

    def _get_or_create_thresholds(
        self,
        agent_id: str,
        company_id: str,
    ) -> Any:
        """Get or create threshold config for an agent.

        Args:
            agent_id: Agent UUID.
            company_id: Tenant UUID (BC-001).

        Returns:
            AgentMetricThreshold ORM object.
        """
        from database.models.agent_metrics import AgentMetricThreshold

        threshold = (
            self.db.query(AgentMetricThreshold)
            .filter(
                AgentMetricThreshold.company_id == company_id,
                AgentMetricThreshold.agent_id == agent_id,
            )
            .first()
        )

        if threshold:
            return threshold

        # Create with defaults
        now = datetime.utcnow()
        threshold = AgentMetricThreshold(
            company_id=company_id,
            agent_id=agent_id,
            resolution_rate_min=Decimal(str(DEFAULT_THRESHOLDS["resolution_rate_min"])),
            confidence_min=Decimal(str(DEFAULT_THRESHOLDS["confidence_min"])),
            csat_min=Decimal(str(DEFAULT_THRESHOLDS["csat_min"])),
            escalation_max_pct=Decimal(str(DEFAULT_THRESHOLDS["escalation_max_pct"])),
            created_at=now,
            updated_at=now,
        )
        self.db.add(threshold)
        self.db.flush()

        return threshold

    def _check_threshold_breach(
        self,
        agent_id: str,
        company_id: str,
        metric_name: str,
        current_value: float,
        threshold: Any,
    ) -> bool:
        """Check if a metric value breaches the threshold.

        Args:
            agent_id: Agent UUID.
            company_id: Tenant UUID.
            metric_name: Name of the metric to check.
            current_value: Current metric value.
            threshold: AgentMetricThreshold ORM object.

        Returns:
            True if the metric breaches the threshold.
        """
        check_type = METRIC_BELOW_CHECKS.get(metric_name, "below")
        threshold_map = {
            "resolution_rate": float(threshold.resolution_rate_min),
            "avg_confidence": float(threshold.confidence_min),
            "avg_csat": float(threshold.csat_min),
            "escalation_rate": float(threshold.escalation_max_pct),
        }
        threshold_val = threshold_map.get(metric_name)
        if threshold_val is None:
            return False

        if check_type == "above":
            return current_value > threshold_val
        return current_value < threshold_val

    def _compute_agent_daily_metrics(
        self,
        agent: Any,
        target_date: date,
        company_id: str,
    ) -> Dict[str, Any]:
        """Compute daily metrics for an agent from raw ticket data.

        Args:
            agent: Agent ORM object.
            target_date: The date to compute metrics for.
            company_id: Tenant UUID (BC-001).

        Returns:
            Dict with computed metric values.
        """
        try:
            from database.models.tickets import (
                Ticket,
                TicketFeedback,
                TicketAssignment,
            )

            day_start = datetime.combine(target_date, datetime.min.time())
            day_end = day_start + timedelta(days=1)

            # Total tickets handled
            tickets_handled = (
                self.db.query(
                    func.count(TicketAssignment.id),
                )
                .join(
                    Ticket,
                    Ticket.id == TicketAssignment.ticket_id,
                )
                .filter(
                    TicketAssignment.company_id == company_id,
                    TicketAssignment.assignee_id == agent.id,
                    TicketAssignment.assigned_at >= day_start,
                    TicketAssignment.assigned_at < day_end,
                )
                .scalar()
                or 0
            )

            if tickets_handled == 0:
                return {
                    "tickets_handled": 0,
                    "resolved_count": 0,
                    "escalated_count": 0,
                    "avg_confidence": None,
                    "avg_csat": None,
                    "avg_handle_time_seconds": None,
                    "resolution_rate": None,
                    "escalation_rate": None,
                }

            # Resolved count
            resolved_count = (
                self.db.query(
                    func.count(TicketAssignment.id),
                )
                .join(
                    Ticket,
                    Ticket.id == TicketAssignment.ticket_id,
                )
                .filter(
                    TicketAssignment.company_id == company_id,
                    TicketAssignment.assignee_id == agent.id,
                    TicketAssignment.assigned_at >= day_start,
                    TicketAssignment.assigned_at < day_end,
                    Ticket.status.in_(["resolved", "closed"]),
                )
                .scalar()
                or 0
            )

            # Escalated count
            escalated_count = (
                self.db.query(
                    func.count(TicketAssignment.id),
                )
                .join(
                    Ticket,
                    Ticket.id == TicketAssignment.ticket_id,
                )
                .filter(
                    TicketAssignment.company_id == company_id,
                    TicketAssignment.assignee_id == agent.id,
                    TicketAssignment.assigned_at >= day_start,
                    TicketAssignment.assigned_at < day_end,
                    Ticket.status.in_(["escalated", "awaiting_human"]),
                )
                .scalar()
                or 0
            )

            # Resolution rate
            resolution_rate = (
                round(resolved_count / tickets_handled * 100, 2)
                if tickets_handled > 0
                else None
            )

            # Escalation rate
            escalation_rate = (
                round(escalated_count / tickets_handled * 100, 2)
                if tickets_handled > 0
                else None
            )

            # Avg CSAT
            avg_csat_val = (
                self.db.query(
                    func.avg(TicketFeedback.rating),
                )
                .join(
                    Ticket,
                    Ticket.id == TicketFeedback.ticket_id,
                )
                .join(
                    TicketAssignment,
                    TicketAssignment.ticket_id == Ticket.id,
                )
                .filter(
                    TicketAssignment.company_id == company_id,
                    TicketAssignment.assignee_id == agent.id,
                    TicketFeedback.created_at >= day_start,
                    TicketFeedback.created_at < day_end,
                )
                .scalar()
            )
            avg_csat = (
                Decimal(str(round(float(avg_csat_val), 1))) if avg_csat_val else None
            )

            # Avg confidence
            avg_confidence_val = self._get_avg_confidence_for_date(
                agent.id,
                company_id,
                day_start,
                day_end,
            )

            # Avg handle time
            avg_handle_time = self._get_avg_handle_time_for_date(
                agent.id,
                company_id,
                day_start,
                day_end,
            )

            return {
                "tickets_handled": tickets_handled,
                "resolved_count": resolved_count,
                "escalated_count": escalated_count,
                "avg_confidence": avg_confidence_val,
                "avg_csat": avg_csat,
                "avg_handle_time_seconds": avg_handle_time,
                "resolution_rate": (
                    Decimal(str(resolution_rate))
                    if resolution_rate is not None
                    else None
                ),
                "escalation_rate": (
                    Decimal(str(escalation_rate))
                    if escalation_rate is not None
                    else None
                ),
            }

        except Exception as exc:
            logger.error(
                "compute_agent_daily_metrics_error",
                company_id=company_id,
                agent_id=agent.id,
                error=str(exc),
            )
            return {
                "tickets_handled": 0,
                "resolved_count": 0,
                "escalated_count": 0,
                "avg_confidence": None,
                "avg_csat": None,
                "avg_handle_time_seconds": None,
                "resolution_rate": None,
                "escalation_rate": None,
            }

    def _get_avg_confidence_for_date(
        self,
        agent_id: str,
        company_id: str,
        day_start: datetime,
        day_end: datetime,
    ) -> Optional[Decimal]:
        """Get average AI confidence for agent's tickets on a date."""
        try:
            from database.models.tickets import Ticket, TicketAssignment

            ticket_model = Ticket.__table__.columns
            if "ai_confidence" not in ticket_model:
                return None

            avg_conf = (
                self.db.query(func.avg(Ticket.ai_confidence))
                .join(
                    TicketAssignment,
                    TicketAssignment.ticket_id == Ticket.id,
                )
                .filter(
                    TicketAssignment.company_id == company_id,
                    TicketAssignment.assignee_id == agent_id,
                    TicketAssignment.assigned_at >= day_start,
                    TicketAssignment.assigned_at < day_end,
                    Ticket.ai_confidence.isnot(None),
                )
                .scalar()
            )

            return Decimal(str(round(float(avg_conf), 2))) if avg_conf else None

        except Exception:
            return None

    def _get_avg_handle_time_for_date(
        self,
        agent_id: str,
        company_id: str,
        day_start: datetime,
        day_end: datetime,
    ) -> Optional[int]:
        """Get average handling time in seconds for agent's tickets."""
        try:
            from database.models.tickets import Ticket, TicketAssignment

            tickets = (
                self.db.query(Ticket)
                .join(
                    TicketAssignment,
                    TicketAssignment.ticket_id == Ticket.id,
                )
                .filter(
                    TicketAssignment.company_id == company_id,
                    TicketAssignment.assignee_id == agent_id,
                    TicketAssignment.assigned_at >= day_start,
                    TicketAssignment.assigned_at < day_end,
                    Ticket.first_response_at.isnot(None),
                )
                .all()
            )

            if not tickets:
                return None

            times: List[float] = []
            for t in tickets:
                if t.first_response_at and t.created_at:
                    seconds = (t.first_response_at - t.created_at).total_seconds()
                    times.append(seconds)

            return int(round(sum(times) / len(times))) if times else None

        except Exception:
            return None

    def _aggregate_weekly(
        self,
        data_points: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Aggregate daily data points into weekly buckets.

        Args:
            data_points: List of daily data point dicts.

        Returns:
            List of weekly aggregated dicts.
        """
        if not data_points:
            return []

        from datetime import datetime as dt

        weeks: Dict[str, List[Dict[str, Any]]] = {}
        for dp in data_points:
            dp_date_str = dp.get("date")
            if not dp_date_str:
                continue
            dp_date = dt.strptime(dp_date_str, "%Y-%m-%d").date()
            # ISO week key
            iso_year, iso_week, _ = dp_date.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            if week_key not in weeks:
                weeks[week_key] = []
            weeks[week_key].append(dp)

        result: List[Dict[str, Any]] = []
        for week_key in sorted(weeks.keys()):
            week_data = weeks[week_key]
            total_tickets = sum(dp.get("tickets_handled", 0) for dp in week_data)

            resolution_rates = [
                dp["resolution_rate"]
                for dp in week_data
                if dp.get("resolution_rate") is not None
            ]
            confidences = [
                dp["avg_confidence"]
                for dp in week_data
                if dp.get("avg_confidence") is not None
            ]
            csats = [
                dp["avg_csat"] for dp in week_data if dp.get("avg_csat") is not None
            ]
            escalation_rates = [
                dp["escalation_rate"]
                for dp in week_data
                if dp.get("escalation_rate") is not None
            ]
            handle_times = [
                dp["avg_handle_time"]
                for dp in week_data
                if dp.get("avg_handle_time") is not None
            ]

            result.append(
                {
                    "date": week_key,
                    "resolution_rate": (
                        round(sum(resolution_rates) / len(resolution_rates), 2)
                        if resolution_rates
                        else None
                    ),
                    "avg_confidence": (
                        round(sum(confidences) / len(confidences), 2)
                        if confidences
                        else None
                    ),
                    "avg_csat": (round(sum(csats) / len(csats), 1) if csats else None),
                    "escalation_rate": (
                        round(sum(escalation_rates) / len(escalation_rates), 2)
                        if escalation_rates
                        else None
                    ),
                    "avg_handle_time": (
                        int(sum(handle_times) / len(handle_times))
                        if handle_times
                        else None
                    ),
                    "tickets_handled": total_tickets,
                }
            )

        return result

    @staticmethod
    def _determine_trend(values: List[float]) -> str:
        """Determine trend direction from a list of values.

        Compares the average of the last 3 values to the average of
        the previous 3 values (or available data). For 2 values,
        compares the most recent to the previous directly.

        Args:
            values: List of numeric values (most recent last).

        Returns:
            "up", "down", or "stable".
        """
        if len(values) < 2:
            return "stable"

        # For exactly 2 values, compare directly
        if len(values) == 2:
            diff = values[-1] - values[-2]
            if values[-2] > 0 and abs(diff / values[-2]) < 0.02:
                return "stable"
            elif diff > 0:
                return "up"
            else:
                return "down"

        # For 3+ values, use up to 3 most recent vs previous 3
        recent = values[-3:]
        prev = values[-6:-3] if len(values) >= 6 else values[:-3]

        if not prev:
            return "stable"

        avg_recent = sum(recent) / len(recent)
        avg_previous = sum(prev) / len(prev)

        diff = avg_recent - avg_previous
        # 2% threshold for stability
        if avg_previous > 0 and abs(diff / avg_previous) < 0.02:
            return "stable"
        elif diff > 0:
            return "up"
        else:
            return "down"


__all__ = [
    "AgentMetricsService",
    "DEFAULT_THRESHOLDS",
    "MIN_TICKETS_FOR_ALERTS",
    "CONSECUTIVE_DAYS_THRESHOLD",
    "VALID_PERIODS",
    "VALID_GRANULARITIES",
    "METRIC_BELOW_CHECKS",
]
