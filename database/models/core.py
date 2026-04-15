"""
Core Models: companies, users, refresh_tokens, mfa_secrets, backup_codes,
api_keys, agents, emergency_states, user_notification_preferences,
verification_tokens, password_reset_tokens, oauth_accounts, company_settings.

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

    # ── Day 6 additions ─────────────────────────────────────────────
    # MF4: currency — company billing currency
    currency = Column(String(3), default="USD")

    # MF6: billing_method — 'paddle' (default) or 'manual' (enterprise)
    billing_method = Column(String(20), default="paddle")

    users = relationship(
        "User", back_populates="company",
        cascade="all, delete-orphan",
    )
    api_keys = relationship(
        "APIKey", back_populates="company",
        cascade="all, delete-orphan",
    )
    # Billing extended relationships (Week 5)
    client_refunds = relationship(
        "ClientRefund", back_populates="company",
        cascade="all, delete-orphan",
    )
    payment_methods = relationship(
        "PaymentMethod", back_populates="company",
        cascade="all, delete-orphan",
    )
    usage_records = relationship(
        "UsageRecord", back_populates="company",
        cascade="all, delete-orphan",
    )
    proration_audits = relationship(
        "ProrationAudit", back_populates="company",
        cascade="all, delete-orphan",
    )
    payment_failures = relationship(
        "PaymentFailure", back_populates="company",
        cascade="all, delete-orphan",
    )
    # Day 5: Chargeback, CreditBalance, SpendingCap, RefundAudit
    chargebacks = relationship(
        "Chargeback", back_populates="company",
        cascade="all, delete-orphan",
    )
    credit_balances = relationship(
        "CreditBalance", back_populates="company",
        cascade="all, delete-orphan",
    )
    spending_caps = relationship(
        "SpendingCap", back_populates="company",
        cascade="all, delete-orphan",
    )
    refund_audits = relationship(
        "RefundAudit", back_populates="company",
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
    full_name = Column(String(255))
    phone = Column(String(20))
    avatar_url = Column(String(500))
    role = Column(String(50), nullable=False, default="owner")
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255))
    # Login lockout fields (F-013: progressive lockout)
    failed_login_count = Column(Integer, default=0)
    locked_until = Column(DateTime)
    last_failed_login_at = Column(DateTime)
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
    oauth_accounts = relationship(
        "OAuthAccount",
        back_populates="user",
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
    key_prefix = Column(String(24), nullable=False)
    scope = Column(String(50), nullable=False, default="read")
    scopes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime, nullable=True)
    rotated_from_id = Column(
        String(36), ForeignKey("api_keys.id"), nullable=True,
    )
    grace_ends_at = Column(DateTime, nullable=True)
    created_by = Column(
        String(36), ForeignKey("users.id"), nullable=True,
    )
    last_used_at = Column(DateTime)
    expires_at = Column(DateTime)
    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
    )

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


# ── Verification Tokens (F-012: email verification) ──────────────

class VerificationToken(Base):
    __tablename__ = "verification_tokens"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    token_hash = Column(String(255), nullable=False, index=True)
    purpose = Column(String(50), default="email_verification")
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Password Reset Tokens (F-014) ───────────────────────────────

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    token_hash = Column(String(255), nullable=False, index=True)
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── OAuth Accounts (F-011: Google OAuth) ────────────────────────

class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    provider = Column(String(50), nullable=False)
    provider_account_id = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    user = relationship("User", back_populates="oauth_accounts")


# ── Company Settings (used by ticket lifecycle, AI pipeline) ────────

class CompanySetting(Base):
    __tablename__ = "company_settings"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    # OOO detection (F-122)
    ooo_status = Column(String(20), default="inactive")
    ooo_message = Column(Text)
    ooo_until = Column(DateTime)
    # Brand voice for AI responses
    brand_voice = Column(Text)
    tone_guidelines = Column(Text)
    prohibited_phrases = Column(Text, default="[]")
    # PII patterns
    pii_patterns = Column(Text, default="[]")
    custom_regex = Column(Text, default="[]")
    # RAG config
    top_k = Column(Integer, default=5)
    similarity_threshold = Column(Numeric(5, 2), default=0.70)
    rerank_model = Column(String(255))
    # Classification config
    confidence_thresholds = Column(Text, default="{}")
    intent_labels = Column(Text, default="[]")
    custom_rules = Column(Text, default="[]")
    # Assignment rules
    assignment_rules = Column(Text, default="[]")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())
