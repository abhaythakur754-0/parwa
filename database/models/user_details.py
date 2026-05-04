"""
User Details Model: Post-payment details collection

Week 6 Day 1: Collect user details after successful payment.
BC-001: Table has company_id for tenant isolation.

Fields:
- full_name: Account owner's full name
- company_name: Business name
- work_email: Optional work email (can differ from signup email)
- work_email_verified: Whether work email has been verified
- industry: Business industry for AI customization
- company_size: Optional company size category
- website: Optional company website
"""

from datetime import datetime
from typing import Optional

import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, ForeignKey
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class UserDetails(Base):
    """Post-payment user details for onboarding.

    Created after successful Paddle payment.
    Required before user can proceed to onboarding wizard.
    """
    __tablename__ = "user_details"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36), ForeignKey("users.id"),
        unique=True, nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    full_name = Column(String(100), nullable=False)
    company_name = Column(String(100), nullable=False)
    work_email = Column(String(255), nullable=True)
    work_email_verified = Column(Boolean, default=False)
    work_email_verification_token = Column(String(64), nullable=True)
    work_email_verification_sent_at = Column(DateTime, nullable=True)
    industry = Column(String(50), nullable=False)
    company_size = Column(String(20), nullable=True)
    website = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    def __repr__(self) -> str:
        return f"<UserDetails {self.id} user={self.user_id}>"
