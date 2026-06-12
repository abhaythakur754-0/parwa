"""
PARWA Phase 3 — Custom Connector Model

User-defined connectors for extending PARWA's integration surface
via manual definition or OpenAPI import.

BC-001: Every table carries ``company_id`` for strict tenant boundaries.
All timestamps are UTC. Primary keys are UUID strings.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, _uuid, _utcnow


# ---------------------------------------------------------------------------
# CustomConnector
# ---------------------------------------------------------------------------

class CustomConnector(Base):
    __tablename__ = "custom_connectors"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    auth_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="E.g. none, api_key, oauth2, basic, bearer",
    )
    encrypted_auth: Mapped[str | None] = mapped_column(Text, nullable=True)
    actions: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON schema of available actions/endpoints",
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual",
        comment="One of: manual, openapi_import",
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
        Index("ix_custom_connectors_company_id", "company_id"),
        Index("ix_custom_connectors_company_active", "company_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<CustomConnector id={self.id!r} name={self.name!r} "
            f"source={self.source!r}>"
        )
