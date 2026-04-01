"""
Analytics Models: metric_aggregates, roi_snapshots, drift_reports,
qa_scores, training_runs.

Source: CORRECTED_PARWA_Complete_Backend_Documentation.md
BC-001: Every table has company_id.
BC-002: Financial metrics use DECIMAL(10,2).
"""

import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, Numeric, String, Text, ForeignKey
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class MetricAggregate(Base):
    __tablename__ = "metric_aggregates"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_type = Column(String(100), nullable=False)
    period = Column(String(20), nullable=False)  # daily, weekly, monthly
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    value = Column(Numeric(10, 2), nullable=False)  # BC-002
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: None)


class ROISnapshot(Base):
    __tablename__ = "roi_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    period = Column(String(20), nullable=False)
    tickets_ai_resolved = Column(Integer, default=0)
    tickets_human_resolved = Column(Integer, default=0)
    avg_ai_cost = Column(Numeric(10, 2))  # BC-002
    avg_human_cost = Column(Numeric(10, 2))  # BC-002
    total_savings = Column(Numeric(10, 2), default=0)  # BC-002
    ai_accuracy_pct = Column(Numeric(5, 2))
    snapshot_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: None)


class DriftReport(Base):
    __tablename__ = "drift_reports"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"))
    metric_type = Column(String(100), nullable=False)
    baseline_value = Column(Numeric(10, 2))
    current_value = Column(Numeric(10, 2))
    drift_pct = Column(Numeric(5, 2))
    severity = Column(String(20), default="low")
    report_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: None)


class QAScore(Base):
    __tablename__ = "qa_scores"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id"))
    agent_id = Column(String(36), ForeignKey("agents.id"))
    accuracy = Column(Numeric(5, 2))
    tone = Column(Numeric(5, 2))
    completeness = Column(Numeric(5, 2))
    overall = Column(Numeric(5, 2))
    scored_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: None)


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"))
    trigger = Column(String(50), nullable=False)  # auto_mistake_threshold, time_fallback, manual
    mistake_count_at_trigger = Column(Integer, default=0)
    status = Column(String(50), default="pending")
    dataset_size = Column(Integer, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    metrics = Column(Text)  # JSON
    previous_model_id = Column(String(255))
    new_model_id = Column(String(255))
    rolled_back = Column(Boolean, default=False)
    error_message = Column(Text)
    created_at = Column(DateTime, default=lambda: None)
