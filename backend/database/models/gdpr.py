"""
GDPR & Data Lifecycle Models: erasure_requests, data_retention_policies.

BC-001: Every table has company_id.
BC-010: GDPR right-to-erasure compliance.
"""

from datetime import datetime, timezone

import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, ForeignKey
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ErasureRequest(Base):
    """Tracks GDPR right-to-erasure requests and their execution status.

    BC-010: Every erasure request is logged with full audit trail.
    Records the requestor, scope, status, and affected data counts.
    """
    __tablename__ = "erasure_requests"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Who requested the erasure (admin or the data subject themselves)
    requested_by = Column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # The customer whose data is being erased
    customer_id = Column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Email of the data subject (preserved even if customer record is anonymized)
    customer_email = Column(String(255), nullable=False)
    # Scope: what data categories to erase
    # full, profile_only, messages_only, tickets_only
    scope = Column(String(50), nullable=False, default="full")
    # Status: pending, processing, completed, failed, cancelled
    status = Column(String(50), nullable=False, default="pending")
    # Reason for the erasure request
    reason = Column(Text, nullable=True)
    # How the request was received: api, email, manual
    request_source = Column(String(50), nullable=False, default="api")
    # Verification status: unverified, verified
    verification_status = Column(String(50), nullable=False, default="unverified")
    # Counts of affected records
    customers_anonymized = Column(Integer, default=0)
    tickets_affected = Column(Integer, default=0)
    messages_redacted = Column(Integer, default=0)
    redis_keys_purged = Column(Integer, default=0)
    # Error details if status is failed
    error_message = Column(Text, nullable=True)
    # Operator who executed the erasure (may differ from requestor)
    executed_by = Column(String(36), nullable=True)
    # Timestamps
    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    verified_at = Column(DateTime, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DataRetentionPolicy(Base):
    """Data retention policies per company and data category.

    Enforces GDPR_RETENTION_DAYS from config as default,
    but allows per-company, per-category overrides.
    """
    __tablename__ = "data_retention_policies"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Data category: tickets, messages, customers, audit_logs, chat_sessions, etc.
    category = Column(String(100), nullable=False)
    # Retention period in days
    retention_days = Column(Integer, nullable=False, default=365)
    # Action after retention: archive, delete, anonymize
    action_on_expiry = Column(String(50), nullable=False, default="archive")
    # Whether the policy is active
    is_active = Column(Boolean, default=True, nullable=False)
    # Last time this policy was enforced
    last_enforced_at = Column(DateTime, nullable=True)
    # Records affected in last enforcement run
    last_records_affected = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
