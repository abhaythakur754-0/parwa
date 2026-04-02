"""
API Key Audit Log Model (F-019)

Tracks all API key lifecycle events:
created, rotated, revoked, used.
"""

from datetime import datetime

from sqlalchemy import (
    Column, String, DateTime, ForeignKey,
)

from database.base import Base


class APIKeyAuditLog(Base):
    __tablename__ = "api_key_audit_log"

    id = Column(String(36), primary_key=True)
    api_key_id = Column(
        String(36),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
    )
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action = Column(String(20), nullable=False)
    endpoint = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
    )
