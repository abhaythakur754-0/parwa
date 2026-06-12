"""
PARWA Phase 3 — Integration Models

Integration and EventBuffer for third-party service connections and
event ingestion.

BC-001: Every table carries ``company_id`` for strict tenant boundaries.
All timestamps are UTC. Primary keys are UUID strings.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, _uuid, _utcnow


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    integration_type: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="E.g. shopify, zendesk, salesforce, hubspot, custom",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="E.g. crm, ecommerce, helpdesk, communication",
    )
    auth_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="E.g. oauth2, api_key, basic, bearer",
    )
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_test_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="One of: success, failure, timeout",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )

    # -- relationships -------------------------------------------------------
    company: Mapped["Company"] = relationship("Company", lazy="selectin")
    events: Mapped[list["EventBuffer"]] = relationship(
        "EventBuffer", back_populates="integration", lazy="selectin",
    )

    # -- indexes -------------------------------------------------------------
    __table_args__ = (
        Index("ix_integrations_company_id", "company_id"),
        Index("ix_integrations_company_type", "company_id", "integration_type"),
        Index("ix_integrations_company_active", "company_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Integration id={self.id!r} type={self.integration_type!r} name={self.name!r}>"


# ---------------------------------------------------------------------------
# EventBuffer
# ---------------------------------------------------------------------------

class EventBuffer(Base):
    __tablename__ = "event_buffer"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    integration_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="E.g. order.created, ticket.updated, contact.synced",
    )
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )

    # -- relationships -------------------------------------------------------
    integration: Mapped["Integration"] = relationship(
        "Integration", back_populates="events",
    )

    # -- indexes -------------------------------------------------------------
    __table_args__ = (
        Index("ix_event_buffer_company_id", "company_id"),
        Index("ix_event_buffer_integration_id", "integration_id"),
        Index("ix_event_buffer_company_processed", "company_id", "processed"),
        Index("ix_event_buffer_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<EventBuffer id={self.id!r} type={self.event_type!r} processed={self.processed!r}>"
