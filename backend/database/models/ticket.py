"""
PARWA Phase 3 — Ticket Models

Ticket and TicketMessage for customer support case management
with SLA tracking, variant tiers, and channel attribution.

BC-001: Every table carries ``company_id`` for strict tenant boundaries.
All timestamps are UTC. Primary keys are UUID strings.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, _uuid, _utcnow


# ---------------------------------------------------------------------------
# Ticket
# ---------------------------------------------------------------------------

class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    customer_id: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="External customer identifier from the source system",
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="E.g. email, chat, whatsapp, phone, sms, web",
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="open",
        comment="One of: open, in_progress, resolved, closed",
    )
    priority: Mapped[str] = mapped_column(
        String(50), nullable=False, default="medium",
        comment="One of: low, medium, high, urgent",
    )
    variant: Mapped[str] = mapped_column(
        String(50), nullable=False, default="parwa",
        comment="One of: mini, parwa, high — determines service tier",
    )
    assigned_to: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    sla_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # -- relationships -------------------------------------------------------
    company: Mapped["Company"] = relationship("Company", lazy="selectin")
    assignee: Mapped["User | None"] = relationship("User", lazy="selectin")
    messages: Mapped[list["TicketMessage"]] = relationship(
        "TicketMessage", back_populates="ticket", lazy="selectin",
        order_by="TicketMessage.created_at",
    )

    # -- indexes -------------------------------------------------------------
    __table_args__ = (
        Index("ix_tickets_company_id", "company_id"),
        Index("ix_tickets_company_status", "company_id", "status"),
        Index("ix_tickets_company_priority", "company_id", "priority"),
        Index("ix_tickets_assigned_to", "assigned_to"),
        Index("ix_tickets_customer_id", "company_id", "customer_id"),
        Index("ix_tickets_sla_deadline", "company_id", "sla_deadline"),
    )

    def __repr__(self) -> str:
        return (
            f"<Ticket id={self.id!r} subject={self.subject!r} "
            f"status={self.status!r} priority={self.priority!r}>"
        )


# ---------------------------------------------------------------------------
# TicketMessage
# ---------------------------------------------------------------------------

class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False,
    )
    sender_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="One of: customer, agent, ai",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )

    # -- relationships -------------------------------------------------------
    company: Mapped["Company"] = relationship("Company", lazy="selectin")
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="messages")

    # -- indexes -------------------------------------------------------------
    __table_args__ = (
        Index("ix_ticket_messages_company_id", "company_id"),
        Index("ix_ticket_messages_ticket_id", "ticket_id"),
        Index("ix_ticket_messages_ticket_created", "ticket_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<TicketMessage id={self.id!r} ticket_id={self.ticket_id!r} "
            f"sender_type={self.sender_type!r}>"
        )
