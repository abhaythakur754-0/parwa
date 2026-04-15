"""
Phone OTP Model (C5: Phone OTP Login)

Stores phone OTP codes for authentication.
BC-001: Scoped by company_id.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String,
)

from database.base import Base


class PhoneOTP(Base):
    __tablename__ = "phone_otps"

    id = Column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    phone = Column(String(20), nullable=False, index=True)
    company_id = Column(
        String(36), ForeignKey("companies.id"),
        nullable=False, index=True,
    )
    code_hash = Column(String(64), nullable=False)
    verified = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, default=0)
    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
    )
