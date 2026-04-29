"""
Analytics Models: metric_aggregates, roi_snapshots, drift_reports,
qa_scores, training_runs.

Source: CORRECTED_PARWA_Complete_Backend_Documentation.md
BC-001: Every table has company_id.
BC-002: Financial metrics use DECIMAL(10,2).
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    ForeignKey,
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class MetricAggregate(Base):
    __tablename__ = "metric_aggregates"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_type = Column(String(100), nullable=False)
    # daily, weekly, monthly
    period = Column(String(20), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    value = Column(Numeric(10, 2), nullable=False)  # BC-002
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class ROISnapshot(Base):
    __tablename__ = "roi_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period = Column(String(20), nullable=False)
    tickets_ai_resolved = Column(Integer, default=0)
    tickets_human_resolved = Column(Integer, default=0)
    avg_ai_cost = Column(Numeric(10, 2))  # BC-002
    avg_human_cost = Column(Numeric(10, 2))  # BC-002
    total_savings = Column(Numeric(10, 2), default=0)  # BC-002
    ai_accuracy_pct = Column(Numeric(5, 2))
    snapshot_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class DriftReport(Base):
    __tablename__ = "drift_reports"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id = Column(String(36), ForeignKey("agents.id"))
    metric_type = Column(String(100), nullable=False)
    baseline_value = Column(Numeric(10, 2))
    current_value = Column(Numeric(10, 2))
    drift_pct = Column(Numeric(5, 2))
    severity = Column(String(20), default="low")
    report_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class QAScore(Base):
    __tablename__ = "qa_scores"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(String(36), ForeignKey("tickets.id"))
    agent_id = Column(String(36), ForeignKey("agents.id"))
    accuracy = Column(Numeric(5, 2))
    tone = Column(Numeric(5, 2))
    completeness = Column(Numeric(5, 2))
    overall = Column(Numeric(5, 2))
    scored_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id = Column(String(36), ForeignKey("agents.id"))
    dataset_id = Column(String(36), ForeignKey("training_datasets.id"))
    name = Column(String(255))
    # manual, auto_threshold, scheduled, cold_start
    trigger = Column(String(50), nullable=False)
    base_model = Column(String(255))
    status = Column(
        String(50), default="queued"
    )  # queued, initializing, running, completed, failed, cancelled
    progress_pct = Column(Numeric(5, 2), default=0)
    current_epoch = Column(Integer, default=0)
    total_epochs = Column(Integer, default=3)
    epochs = Column(Integer, default=3)
    learning_rate = Column(Numeric(10, 8), default=0.0001)
    batch_size = Column(Integer, default=16)
    # Mistake count at trigger (for F-101)
    mistake_count_at_trigger = Column(Integer, default=0)
    dataset_size = Column(Integer, default=0)
    # Model storage paths
    model_path = Column(Text)
    checkpoint_path = Column(Text)
    # GPU Provider info (F-102)
    provider = Column(String(50))  # local, colab, runpod
    instance_id = Column(String(255))
    gpu_type = Column(String(50))  # T4, A100, V100, A10G
    cost_usd = Column(Numeric(10, 4), default=0)
    # Timestamps
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    # Metrics JSON (loss, accuracy, quality_score, etc.)
    metrics = Column(Text)
    # Model management
    previous_model_id = Column(String(255))
    new_model_id = Column(String(255))
    rolled_back = Column(Boolean, default=False)
    error_message = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
