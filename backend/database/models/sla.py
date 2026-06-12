"""
PARWA Phase 3 — SLA Rule Model

SLARule for defining per-company, per-priority service level agreements
that drive ticket deadline computation and escalation.

BC-001: Every table carries ``company_id`` for strict tenant boundaries.
All timestamps are UTC. Primary keys are UUID strings.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, _uuid, _utcnow


# ---------------------------------------------------------------------------
# SLARule
# ---------------------------------------------------------------------------

class SLARule(Base):
    __tablename__ = "sla_rules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="One of: low, medium, high, urgent",
    )
    response_time_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Maximum minutes before first agent response",
    )
    resolution_time_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Maximum minutes before full resolution",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )

    # -- relationships -------------------------------------------------------
    company: Mapped["Company"] = relationship("Company", lazy="selectin")

    # -- indexes -------------------------------------------------------------
    __table_args__ = (
        Index("ix_sla_rules_company_id", "company_id"),
        Index("ix_sla_rules_company_priority", "company_id", "priority"),
        Index("ix_sla_rules_company_active", "company_id", "is_active"),
        Index("ix_sla_rules_company_priority_active", "company_id", "priority", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<SLARule id={self.id!r} name={self.name!r} "
            f"priority={self.priority!r} response={self.response_time_minutes}m "
            f"resolution={self.resolution_time_minutes}m>"
        )
