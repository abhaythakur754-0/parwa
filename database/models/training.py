"""
Training Models: training_datasets, training_checkpoints,
agent_mistakes, agent_performance.

BC-001: Every table has company_id.
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, Numeric, String, Text, ForeignKey
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class TrainingDataset(Base):
    __tablename__ = "training_datasets"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"))
    name = Column(String(255), nullable=False)
    record_count = Column(Integer, default=0)
    source = Column(String(50), nullable=False)  # mistakes, manual, export
    status = Column(String(50), default="draft")
    file_path = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class TrainingCheckpoint(Base):
    __tablename__ = "training_checkpoints"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    training_run_id = Column(String(36), ForeignKey("training_runs.id"), nullable=False, index=True)
    checkpoint_name = Column(String(255), nullable=False)
    model_path = Column(Text)
    metrics = Column(Text)  # JSON
    epoch = Column(Integer)
    is_best = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class AgentMistake(Base):
    __tablename__ = "agent_mistakes"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id"))
    mistake_type = Column(String(100), nullable=False)
    original_response = Column(Text)
    expected_response = Column(Text)
    correction = Column(Text)
    severity = Column(String(20), default="medium")
    used_in_training = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class AgentPerformance(Base):
    __tablename__ = "agent_performance"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    period = Column(String(20), nullable=False)
    period_start = Column(DateTime, nullable=False)
    tickets_resolved = Column(Integer, default=0)
    avg_confidence = Column(Numeric(5, 2))
    avg_resolution_time_min = Column(Numeric(10, 2))
    escalation_rate = Column(Numeric(5, 2))
    csat_score = Column(Numeric(5, 2))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
