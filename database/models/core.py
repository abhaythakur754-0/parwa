"""
Core Models: companies, users, refresh_tokens, mfa_secrets, backup_codes,
api_keys, agents, emergency_states, user_notification_preferences.

Source: CORRECTED_PARWA_Complete_Backend_Documentation.md
BC-001: Every table has company_id (except companies which IS the root).
BC-002: Money fields use DECIMAL(10,2).
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, Numeric, String, Text, ForeignKey
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Companies (root tenant — no company_id) ────────────────────────

class Company(Base):
    __tablename__ = "companies"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    industry = Column(String(50), nullable=False)
    subscription_tier = Column(String(50), nullable=False)
    subscription_status = Column(String(50), default="active")
    mode = Column(String(50), default="shadow")
    paddle_customer_id = Column(String(255))
    paddle_subscription_id = Column(String(255))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    users = relationship(
        "User", back_populates="company",
        cascade="all, delete-orphan",
    )
    api_keys = relationship(
        "APIKey", back_populates="company",
        cascade="all, delete-orphan",
    )


# ── Users ──────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="viewer")
    is_active = Column(Boolean, default=True)
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    company = relationship("Company", back_populates="users")
    refresh_tokens = relationship(
        "RefreshToken", back_populates="user",
        cascade="all, delete-orphan",
    )
    backup_codes = relationship(
        "BackupCode", back_populates="user",
        cascade="all, delete-orphan",
    )


# ── Refresh Tokens (BC-011: max 5 sessions) ────────────────────────

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    token_hash = Column(String(255), nullable=False, unique=True)
    device_info = Column(String(255))
    ip_address = Column(String(45))
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    user = relationship("User", back_populates="refresh_tokens")


# ── MFA Secrets ────────────────────────────────────────────────────

class MFASecret(Base):
    __tablename__ = "mfa_secrets"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    secret_key = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Backup Codes ───────────────────────────────────────────────────

class BackupCode(Base):
    __tablename__ = "backup_codes"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    code_hash = Column(String(255), nullable=False)
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    user = relationship("User", back_populates="backup_codes")


# ── API Keys (BC-011: scopes read/write/admin/approval) ────────────

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)
    key_prefix = Column(String(8), nullable=False)
    scope = Column(String(50), nullable=False, default="read")
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    company = relationship("Company", back_populates="api_keys")


# ── Agents (AI agents per company) ─────────────────────────────────

class Agent(Base):
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(255), nullable=False)
    variant = Column(String(50), nullable=False)
    status = Column(String(50), default="active")
    capacity_used = Column(Integer, default=0)
    capacity_max = Column(Integer, default=100)
    accuracy_rate = Column(Numeric(5, 2), default=0)
    tickets_resolved = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Emergency States (pause controls) ──────────────────────────────

class EmergencyState(Base):
    __tablename__ = "emergency_states"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    is_paused = Column(Boolean, default=False)
    paused_channels = Column(Text, default="")
    paused_by = Column(String(36), ForeignKey("users.id"))
    paused_at = Column(DateTime)
    reason = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── User Notification Preferences ──────────────────────────────────

class UserNotificationPreference(Base):
    __tablename__ = "user_notification_preferences"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    channel = Column(String(50), nullable=False)
    event_type = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())
