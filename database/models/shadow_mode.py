"""
Shadow Mode Models: shadow_log, shadow_preferences.

Dual-control system that allows AI actions to be executed in shadow mode
(observation only), supervised (requires manager approval), or graduated
(auto-approved based on confidence).

BC-001: Every table has company_id.
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Column, String, Float, Text, DateTime, ForeignKey,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ShadowLog(Base):
    __tablename__ = "shadow_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Action type: 'refund', 'sms_reply', 'email_reply', etc.
    action_type = Column(String(50), nullable=False)
    # Full action payload (JSONB for flexible schema)
    action_payload = Column(JSONB, nullable=False, default=dict)
    # Risk score computed by Jarvis heuristic engine (0.0 to 1.0)
    jarvis_risk_score = Column(Float, nullable=True)
    # Execution mode: shadow / supervised / graduated
    mode = Column(String(15), nullable=False, default="supervised")
    # Manager decision: approved / rejected / modified / null
    manager_decision = Column(String(15), nullable=True)
    manager_note = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_shadow_log_company", "company_id", created_at.desc()),
        Index("idx_shadow_log_mode", "mode", "manager_decision"),
    )


class ShadowPreference(Base):
    __tablename__ = "shadow_preferences"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Action category: 'refund', 'sms', 'email_reply', etc.
    action_category = Column(String(50), nullable=False)
    # Preferred mode for this category: shadow / supervised / graduated
    preferred_mode = Column(String(15), nullable=False, default="shadow")
    # How this preference was set: 'ui' or 'jarvis'
    set_via = Column(String(10), nullable=False, default="ui")
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "action_category",
            name="uq_shadow_prefs_company_category",
        ),
        Index("idx_shadow_prefs_company", "company_id"),
    )
