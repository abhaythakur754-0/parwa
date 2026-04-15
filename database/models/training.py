"""
Training Models: training_datasets, training_checkpoints,
agent_mistakes, agent_performance, peer_reviews.

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
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    agent_id = Column(String(36), ForeignKey("agents.id"))
    name = Column(String(255), nullable=False)
    description = Column(Text)
    record_count = Column(Integer, default=0)
    source = Column(String(50), nullable=False)  # mistakes, manual, export, cold_start_template
    status = Column(String(50), default="draft")
    file_path = Column(Text)
    storage_path = Column(Text)  # Path to stored JSONL file
    quality_score = Column(Numeric(5, 3))
    format_version = Column(String(10), default="1.0")
    error_message = Column(Text)
    prepared_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class TrainingCheckpoint(Base):
    __tablename__ = "training_checkpoints"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    training_run_id = Column(
        String(36), ForeignKey("training_runs.id"),
        nullable=False, index=True,
    )
    checkpoint_name = Column(String(255), nullable=False)
    model_path = Column(Text)
    metrics = Column(Text)  # JSON
    loss = Column(Numeric(10, 6))
    accuracy = Column(Numeric(5, 4))
    epoch = Column(Integer)
    is_best = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class AgentMistake(Base):
    __tablename__ = "agent_mistakes"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    agent_id = Column(
        String(36), ForeignKey("agents.id"),
        nullable=False, index=True,
    )
    ticket_id = Column(String(36), ForeignKey("tickets.id"))
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
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    agent_id = Column(
        String(36), ForeignKey("agents.id"),
        nullable=False, index=True,
    )
    period = Column(String(20), nullable=False)
    period_start = Column(DateTime, nullable=False)
    tickets_resolved = Column(Integer, default=0)
    avg_confidence = Column(Numeric(5, 2))
    avg_resolution_time_min = Column(Numeric(10, 2))
    escalation_rate = Column(Numeric(5, 2))
    csat_score = Column(Numeric(5, 2))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class PeerReview(Base):
    """F-108: Peer Review / Escalation model for junior-to-senior escalation."""
    __tablename__ = "peer_reviews"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    junior_agent_id = Column(
        String(36), ForeignKey("agents.id"),
        nullable=False, index=True,
    )
    senior_agent_id = Column(
        String(36), ForeignKey("agents.id"),
        nullable=False, index=True,
    )
    ticket_id = Column(String(36), ForeignKey("tickets.id"))
    # low_confidence, complex_query, policy_violation_risk, customer_escalation, uncertainty, knowledge_gap
    reason = Column(String(50), nullable=False)
    # pending, in_progress, completed, dismissed, escalated_further
    status = Column(String(30), default="pending")
    # low, normal, high, urgent
    priority = Column(String(20), default="normal")
    # Original draft response from junior
    original_response = Column(Text)
    # Senior's corrected response
    reviewed_response = Column(Text)
    # Feedback from senior to junior
    feedback = Column(Text)
    # Junior's confidence score
    confidence_score = Column(Numeric(5, 4))
    # Additional context (JSON)
    context = Column(Text)
    # Whether original was approved
    approved = Column(Boolean, default=False)
    # Whether used for training
    used_for_training = Column(Boolean, default=False)
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    assigned_at = Column(DateTime)
    reviewed_at = Column(DateTime)
    completed_at = Column(DateTime)
