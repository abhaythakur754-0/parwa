"""SuperglueActionSafety model — persisted safety classification for Superglue tools.

Avoids reclassifying on every call. BC-001: every table has company_id.
BC-002: no money fields (this is metadata, not transactions).
"""

from datetime import datetime, timezone

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SuperglueActionSafety(Base):
    __tablename__ = "superglue_action_safety"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tool_id = Column(String(100), nullable=False, index=True)
    tool_name = Column(String(255), nullable=False)
    safety_level = Column(String(50), nullable=False)
    needs_approval = Column(Boolean, default=False)
    regulatory_frameworks = Column(Text, nullable=True)  # JSON list
    output_schema = Column(Text, nullable=True)  # JSON dict
    approval_required_override = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    classified_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
