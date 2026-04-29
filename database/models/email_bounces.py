"""
Email Bounce & Complaint Models — Week 13 Day 3 (F-124)

Tables:
- email_bounces: Individual bounce/complaint event records
- customer_email_status: Per-email delivery status tracking
- email_deliverability_alerts: Alerting for reputation issues

Building Codes:
- BC-001: Multi-tenant isolation (company_id on every row)
- BC-003: Idempotent webhook processing
- BC-006: Email communication rules
- BC-010: GDPR (complaint = stop all emails)
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


class EmailBounce(Base):
    """Individual bounce/complaint event record.

    One row per bounce or complaint event received from Brevo.
    Tracks the reason, provider, and what happened to the
    customer's email status.
    """

    __tablename__ = "email_bounces"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        nullable=False,
        index=True,
    )

    # Contact info
    customer_email = Column(String(254), nullable=False, index=True)
    bounce_type = Column(String(50), nullable=False, index=True)
    # Values: hard_bounce, soft_bounce, complaint

    # Event details
    bounce_reason = Column(Text, nullable=True)
    provider = Column(String(50), nullable=False, default="other")
    provider_code = Column(String(50), nullable=True)

    # Correlation
    event_id = Column(String(255), nullable=True, unique=True)
    related_ticket_id = Column(String(36), nullable=True)

    # Status transition tracking
    email_status_before = Column(String(50), nullable=False, default="active")
    email_status_after = Column(String(50), nullable=False, default="active")

    # Whitelist management
    whitelisted = Column(Boolean, nullable=False, default=False)
    whitelist_justification = Column(Text, nullable=True)
    whitelisted_by = Column(String(36), nullable=True)
    whitelisted_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "customer_email": self.customer_email,
            "bounce_type": self.bounce_type,
            "bounce_reason": self.bounce_reason,
            "provider": self.provider,
            "provider_code": self.provider_code,
            "event_id": self.event_id,
            "related_ticket_id": self.related_ticket_id,
            "email_status_before": self.email_status_before,
            "email_status_after": self.email_status_after,
            "whitelisted": self.whitelisted,
            "whitelist_justification": self.whitelist_justification,
            "whitelisted_by": self.whitelisted_by,
            "whitelisted_at": (
                self.whitelisted_at.isoformat() if self.whitelisted_at else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CustomerEmailStatus(Base):
    """Per-email delivery status tracking.

    Aggregates bounce/complaint counts for each email address.
    Used by the suppression list to prevent sending to invalid
    or complained addresses.
    """

    __tablename__ = "customer_email_status"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        nullable=False,
        index=True,
    )
    customer_email = Column(
        String(254),
        nullable=False,
        index=True,
    )

    # Current status
    email_status = Column(
        String(50),
        nullable=False,
        default="active",
        index=True,
    )
    # Values: active, soft_bounced, hard_bounced, complained, suppressed

    # Counters
    bounce_count = Column(Integer, nullable=False, default=0)
    complaint_count = Column(Integer, nullable=False, default=0)
    last_bounce_at = Column(DateTime, nullable=True)
    last_complaint_at = Column(DateTime, nullable=True)

    # Suppression
    suppressed_at = Column(DateTime, nullable=True)
    whitelisted = Column(Boolean, nullable=False, default=False)

    # Timestamps
    updated_at = Column(
        DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow()
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "customer_email": self.customer_email,
            "email_status": self.email_status,
            "bounce_count": self.bounce_count or 0,
            "complaint_count": self.complaint_count or 0,
            "last_bounce_at": (
                self.last_bounce_at.isoformat() if self.last_bounce_at else None
            ),
            "last_complaint_at": (
                self.last_complaint_at.isoformat() if self.last_complaint_at else None
            ),
            "suppressed_at": (
                self.suppressed_at.isoformat() if self.suppressed_at else None
            ),
            "whitelisted": self.whitelisted,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class EmailDeliverabilityAlert(Base):
    """Deliverability alert for tenant notification.

    Created when bounce rates spike, complaint thresholds are
    exceeded, or Gmail sender reputation is at risk.
    """

    __tablename__ = "email_deliverability_alerts"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        nullable=False,
        index=True,
    )

    # Alert details
    alert_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(50), nullable=False, default="medium")
    # Values: low, medium, high, critical
    message = Column(Text, nullable=False)

    # Metrics
    metric_value = Column(String(255), nullable=True)
    threshold = Column(String(255), nullable=True)

    # Acknowledgment
    acknowledged = Column(Boolean, nullable=False, default=False)
    acknowledged_by = Column(String(36), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
