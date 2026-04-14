"""
OOO Detection Models — Week 13 Day 3 (F-122)

Tables:
- ooo_detection_rules: Custom tenant-specific OOO detection rules
- ooo_detection_log: Structured log of every OOO detection
- ooo_sender_profiles: Per-sender OOO tracking (frequency, return dates)

Building Codes:
- BC-001: Multi-tenant isolation (company_id on every row)
- BC-006: Email communication (OOO prevents ticket creation)
- BC-010: GDPR (respect customer availability signals)
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class OOODetectionRule(Base):
    """Custom OOO detection rule.

    Tenants can define custom patterns to detect OOO emails
    that the built-in patterns might miss (e.g., company-specific
    auto-reply subjects, non-standard headers).
    """

    __tablename__ = "ooo_detection_rules"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        nullable=True,
        index=True,
    )  # NULL = global rule

    # Rule definition
    rule_type = Column(String(50), nullable=False, default="body")
    # Values: header, body, subject, sender_behavior, frequency
    pattern = Column(Text, nullable=False)
    pattern_type = Column(String(50), nullable=False, default="regex")
    # Values: regex, substring, contains
    classification = Column(String(50), nullable=False, default="ooo")
    # Values: ooo, auto_reply, cyclic, spam
    active = Column(Boolean, nullable=False, default=True)

    # Stats
    match_count = Column(Integer, nullable=False, default=0)
    last_matched_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "rule_type": self.rule_type,
            "pattern": self.pattern,
            "pattern_type": self.pattern_type,
            "classification": self.classification,
            "active": self.active,
            "match_count": self.match_count or 0,
            "last_matched_at": self.last_matched_at.isoformat() if self.last_matched_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class OOODetectionLog(Base):
    """Structured log of OOO detection events.

    Every OOO detection (header/subject/body/rule/profile) creates
    an entry here for analytics and reporting.
    """

    __tablename__ = "ooo_detection_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        nullable=False,
        index=True,
    )

    # Who triggered it
    sender_email = Column(String(254), nullable=False, index=True)
    thread_id = Column(String(36), nullable=True)
    related_ticket_id = Column(String(36), nullable=True)
    message_id = Column(String(255), nullable=True)

    # Detection details
    classification = Column(String(50), nullable=False, default="ooo")
    # Values: ooo, auto_reply, cyclic, spam
    confidence = Column(
        String(10), nullable=False, default="medium",
    )  # high, medium, low
    detected_signals = Column(Text, nullable=True, default="[]")
    rule_ids_matched = Column(Text, nullable=True, default="[]")

    # Action taken
    action_taken = Column(String(50), nullable=False, default="tagged")
    # Values: tagged, thread_paused, ignored

    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "sender_email": self.sender_email,
            "thread_id": self.thread_id,
            "related_ticket_id": self.related_ticket_id,
            "message_id": self.message_id,
            "classification": self.classification,
            "confidence": self.confidence,
            "detected_signals": self.detected_signals,
            "rule_ids_matched": self.rule_ids_matched,
            "action_taken": self.action_taken,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OOOSenderProfile(Base):
    """Per-sender OOO tracking.

    Tracks how many times a sender has triggered OOO detection
    and their extracted return date. Used for:
    - Frequency-based cyclic auto-reply detection
    - Smart follow-up scheduling (pause until return date)
    - Dashboard analytics
    """

    __tablename__ = "ooo_sender_profiles"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        nullable=False,
        index=True,
    )
    sender_email = Column(String(254), nullable=False, index=True)

    # Tracking
    ooo_detected_count = Column(Integer, nullable=False, default=0)
    last_ooo_at = Column(DateTime, nullable=True)
    ooo_until = Column(DateTime, nullable=True)
    active_ooo = Column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "sender_email": self.sender_email,
            "ooo_detected_count": self.ooo_detected_count or 0,
            "last_ooo_at": self.last_ooo_at.isoformat() if self.last_ooo_at else None,
            "ooo_until": self.ooo_until.isoformat() if self.ooo_until else None,
            "active_ooo": self.active_ooo,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
