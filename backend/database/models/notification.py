"""
PARWA Phase 3 — Notification Model

In-app, email, and push notification records with severity levels
and composite indexes for efficient per-company queries.

BC-001: Every table carries ``company_id`` for strict tenant boundaries.
All timestamps are UTC. Primary keys are UUID strings.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, _uuid, _utcnow


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        comment="Nullable — when null the notification is company-wide",
    )
    category: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="E.g. ticket, integration, sla, system, billing",
    )
    severity: Mapped[str] = mapped_column(
        String(50), nullable=False, default="medium",
        comment="One of: low, medium, high, critical",
    )
    notification_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="E.g. in_app, email, push, sms",
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # -- relationships -------------------------------------------------------
    company: Mapped["Company"] = relationship("Company", lazy="selectin")
    user: Mapped["User | None"] = relationship("User", lazy="selectin")

    # -- composite indexes for per-company query patterns --------------------
    __table_args__ = (
        Index("ix_notifications_company_category", "company_id", "category"),
        Index("ix_notifications_company_read", "company_id", "read"),
        Index("ix_notifications_company_created_at", "company_id", "created_at"),
        Index("ix_notifications_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification id={self.id!r} category={self.category!r} "
            f"severity={self.severity!r} read={self.read!r}>"
        )
