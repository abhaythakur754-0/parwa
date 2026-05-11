"""
Approval Models: approval_queues, auto_approve_rules,
executed_actions, undo_log.

Source: CORRECTED_PARWA_Complete_Backend_Documentation.md
BC-001: Every table has company_id.
BC-002: amount field DECIMAL(10,2).
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Numeric, String, Text, ForeignKey
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ApprovalQueue(Base):
    __tablename__ = "approval_queues"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    session_id = Column(String(36), ForeignKey("tickets.id"))
    action_type = Column(String(100), nullable=False)
    confidence_score = Column(Numeric(5, 2))
    risk_level = Column(String(50))
    amount = Column(Numeric(10, 2))  # BC-002
    reasoning = Column(Text)
    response_data = Column(Text)
    status = Column(String(50), default="pending")
    batch_id = Column(String(36))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    resolved_at = Column(DateTime)
    resolved_by = Column(String(36), ForeignKey("users.id"))


class AutoApproveRule(Base):
    __tablename__ = "auto_approve_rules"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    action_type = Column(String(100), nullable=False)
    min_confidence = Column(Numeric(5, 2), nullable=False)
    max_amount = Column(Numeric(10, 2))  # BC-002
    risk_levels = Column(Text, default="low")
    is_active = Column(Boolean, default=False)
    created_by = Column(
        String(36), ForeignKey("users.id"), nullable=False,
    )
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class ExecutedAction(Base):
    __tablename__ = "executed_actions"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    session_id = Column(String(36), ForeignKey("tickets.id"))
    approval_id = Column(
        String(36), ForeignKey("approval_queues.id"),
    )
    action_type = Column(String(100), nullable=False)
    action_data = Column(Text)
    response_data = Column(Text)
    amount = Column(Numeric(10, 2))  # BC-002
    executed_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class UndoLog(Base):
    __tablename__ = "undo_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    executed_action_id = Column(
        String(36), ForeignKey("executed_actions.id"),
        nullable=False,
    )
    # reversal, email_recall
    undo_type = Column(String(50), nullable=False)
    original_data = Column(Text)
    undo_data = Column(Text)
    undo_reason = Column(Text)
    undone_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
