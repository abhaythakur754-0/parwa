"""
LangGraph Dead Letter Queue Model

Persists failed LangGraph graph executions for later inspection,
manual retry, or analysis.

BC-001: company_id on every row, indexed.
BC-008: Graceful degradation — nullable columns for partial data.
BC-012: All timestamps UTC.
"""

from datetime import datetime, timezone

import uuid

from sqlalchemy import (
    Column, DateTime, Index, String, Text,
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class LanggraphDLQEntry(Base):
    """Dead Letter Queue entry for failed LangGraph executions.

    Each row represents a single failed graph execution that was
    captured for later inspection, retry, or purge.

    Mirrors the Redis DLQ entry fields but in a durable SQL table.
    """

    __tablename__ = "langgraph_dlq_entries"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        nullable=False, index=True,
    )

    dlq_id = Column(String(36), nullable=False, unique=True, index=True)
    graph_id = Column(String(255), nullable=True)
    thread_id = Column(String(255), nullable=False, index=True)

    error_message = Column(Text, nullable=True)
    error_type = Column(String(255), nullable=True)

    state_snapshot = Column(Text, default="{}")
    # JSON-serialized snapshot of graph state at failure

    status = Column(String(50), default="pending")
    # pending, retried, cleared

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index(
            "ix_dlq_comp_created",
            "company_id", "created_at",
        ),
        Index(
            "ix_dlq_comp_status",
            "company_id", "status",
        ),
        Index(
            "ix_dlq_comp_thread",
            "company_id", "thread_id",
        ),
    )
