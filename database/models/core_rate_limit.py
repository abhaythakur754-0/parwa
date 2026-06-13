"""
Rate Limit Event Model (F-018)

Tracks per-endpoint-category rate limit events,
failure counts, and lockout state for progressive backoff.
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey,
)

from database.base import Base


class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"

    id = Column(String(36), primary_key=True)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key = Column(String(255), nullable=False, index=True)
    endpoint_category = Column(
        String(50), nullable=False, index=True,
    )
    failure_count = Column(Integer, default=0)
    lockout_until = Column(DateTime, nullable=True)
    last_attempt_at = Column(DateTime, nullable=True)
