"""
Business Email OTP Model (Week 6 Day 10-11)

Stores OTP codes for business email verification.
Used in onboarding flow to verify user's business email.

BC-001: Scoped by company_id.
BC-011: OTP codes are hashed (SHA-256).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String,
)

from database.base import Base


class BusinessEmailOTP(Base):
    """OTP codes for business email verification.
    
    Flow:
    1. User enters business email
    2. System generates 6-digit OTP, hashes it, stores here
    3. Email sent via Brevo with the OTP code
    4. User enters OTP code
    5. System verifies against hash
    
    Features:
    - Rate limiting (max 3 requests per hour per email)
    - OTP expires in 10 minutes
    - Max 5 verification attempts
    - Single-use codes
    """
    __tablename__ = "business_email_otps"

    id = Column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    # The business email being verified
    email = Column(String(255), nullable=False, index=True)
    # Company context
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # User who requested verification
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # SHA-256 hash of the 6-digit OTP
    code_hash = Column(String(64), nullable=False)
    # Whether this OTP has been verified
    verified = Column(Boolean, default=False, nullable=False)
    # When the OTP expires (10 minutes from creation)
    expires_at = Column(DateTime, nullable=False)
    # Number of verification attempts
    attempts = Column(Integer, default=0, nullable=False)
    # Timestamps
    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
        nullable=False,
    )
    verified_at = Column(DateTime, nullable=True)
