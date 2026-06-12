"""
PARWA Phase 3 — Core Models

Company, User, and CompanySetting — the foundation of multi-tenant isolation.

BC-001: Every table carries ``company_id`` for strict tenant boundaries.
All timestamps are UTC. Primary keys are UUID strings.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, _uuid, _utcnow


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(
        String(50), nullable=False, default="general",
        comment="One of: ecommerce, saas, logistics, general",
    )
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    subscription_variant: Mapped[str] = mapped_column(
        String(50), nullable=False, default="mini",
        comment="One of: mini, parwa, high",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )

    # -- relationships -------------------------------------------------------
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="company", lazy="selectin",
    )
    company_settings: Mapped[list["CompanySetting"]] = relationship(
        "CompanySetting", back_populates="company", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Company id={self.id!r} name={self.name!r}>"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="agent",
        comment="One of: owner, admin, agent",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="bcrypt password hash — NULL for invite-pending users",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )

    # -- relationships -------------------------------------------------------
    company: Mapped["Company"] = relationship("Company", back_populates="users")

    # -- indexes -------------------------------------------------------------
    __table_args__ = (
        Index("ix_users_company_id", "company_id"),
        Index("ix_users_email_company", "company_id", "email", unique=True),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r} role={self.role!r}>"


# ---------------------------------------------------------------------------
# CompanySetting
# ---------------------------------------------------------------------------

class CompanySetting(Base):
    __tablename__ = "company_settings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )

    # -- relationships -------------------------------------------------------
    company: Mapped["Company"] = relationship(
        "Company", back_populates="company_settings",
    )

    # -- indexes -------------------------------------------------------------
    __table_args__ = (
        Index("ix_company_settings_company_id", "company_id"),
        Index("ix_company_settings_company_key", "company_id", "key", unique=True),
    )

    def __repr__(self) -> str:
        return f"<CompanySetting id={self.id!r} key={self.key!r}>"
