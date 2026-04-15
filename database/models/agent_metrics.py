"""
PARWA Agent Metrics Models (F-098)

SQLAlchemy models for agent performance metrics tracking, performance
alerts, and per-agent metric threshold configuration.

Tables:
- AgentMetricsDaily: Daily aggregated metrics per agent
- AgentPerformanceAlert: Alerts for metrics below threshold
- AgentMetricThreshold: Per-agent threshold configuration

Building Codes: BC-001 (multi-tenant), BC-012 (graceful errors)
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, Integer,
    Numeric, String, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enum-like value sets (used by CHECK constraints) ────────────

_ALERT_STATUSES = "'active','acknowledged','resolved'"


# ── Agent Metrics Daily ────────────────────────────────────────

class AgentMetricsDaily(Base):
    """Daily aggregated performance metrics for an agent.

    One row per agent per day. Metrics include tickets handled,
    resolution rate, escalation rate, CSAT, confidence, and
    average handle time. Computed by the Celery daily metrics job.

    BC-001: Scoped by company_id.
    """
    __tablename__ = "agent_metrics_daily"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    agent_id = Column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    date = Column(Date, nullable=False)
    tickets_handled = Column(Integer, nullable=False, default=0)
    resolved_count = Column(Integer, nullable=False, default=0)
    escalated_count = Column(Integer, nullable=False, default=0)
    avg_confidence = Column(Numeric(5, 2), nullable=True)
    avg_csat = Column(Numeric(3, 1), nullable=True)
    avg_handle_time_seconds = Column(Integer, nullable=True)
    resolution_rate = Column(Numeric(5, 2), nullable=True)
    escalation_rate = Column(Numeric(5, 2), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    # ── Relationships ──
    agent = relationship("Agent")

    __table_args__ = (
        UniqueConstraint(
            "agent_id", "date",
            name="uq_agent_metrics_daily_agent_date",
        ),
        Index(
            "ix_agent_metrics_daily_company_date",
            "company_id", "date",
        ),
        {"schema": None},
    )


# ── Agent Performance Alert ────────────────────────────────────

class AgentPerformanceAlert(Base):
    """Alert raised when an agent metric falls below its threshold
    for consecutive days.

    Tracked metrics: resolution_rate, avg_confidence, avg_csat,
    escalation_rate. Status flows through: active → acknowledged
    → resolved.

    BC-001: Scoped by company_id.
    """
    __tablename__ = "agent_performance_alerts"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    agent_id = Column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # resolution_rate, avg_confidence, avg_csat, escalation_rate
    metric_name = Column(String(50), nullable=False)
    current_value = Column(Numeric(5, 2), nullable=True)
    threshold_value = Column(Numeric(5, 2), nullable=True)
    consecutive_days_below = Column(Integer, nullable=False, default=1)
    # active, acknowledged, resolved
    status = Column(String(20), nullable=False, default="active")
    triggered_training = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # ── Relationships ──
    agent = relationship("Agent")

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_ALERT_STATUSES})",
            name="ck_agent_performance_alert_status",
        ),
        Index(
            "ix_agent_performance_alerts_company_status",
            "company_id", "status",
        ),
        {"schema": None},
    )


# ── Agent Metric Threshold ─────────────────────────────────────

class AgentMetricThreshold(Base):
    """Per-agent metric threshold configuration.

    One record per agent per tenant. Defines the minimum acceptable
    values for resolution_rate, confidence, CSAT, and maximum
    acceptable escalation rate.

    BC-001: Scoped by company_id.
    """
    __tablename__ = "agent_metric_thresholds"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    agent_id = Column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    resolution_rate_min = Column(
        Numeric(5, 2), nullable=False, default=70.00,
    )
    confidence_min = Column(
        Numeric(5, 2), nullable=False, default=65.00,
    )
    csat_min = Column(
        Numeric(3, 1), nullable=False, default=3.5,
    )
    escalation_max_pct = Column(
        Numeric(5, 2), nullable=False, default=15.00,
    )
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    # ── Relationships ──
    agent = relationship("Agent")

    __table_args__ = (
        UniqueConstraint(
            "company_id", "agent_id",
            name="uq_agent_metric_thresholds_company_agent",
        ),
        {"schema": None},
    )
