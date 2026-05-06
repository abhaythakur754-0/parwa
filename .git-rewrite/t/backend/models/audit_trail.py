import uuid
import hashlib
import json
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.sql import func

from backend.app.database import Base

class AuditTrail(Base):
    """
    Immutable audit log model for all AI decisions and human overrides.
    Important: This table must be INSERT-ONLY. A PostgreSQL event listener or 
    db trigger (defined in database/schema.sql) must block UPDATE and DELETE.
    """
    __tablename__ = "audit_trails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("support_tickets.id"), nullable=True)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    details = Column(JSON, nullable=False)
    previous_hash = Column(String, nullable=True)
    entry_hash = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = {
        'comment': 'INSERT-ONLY table. UPDATE and DELETE operations are blocked via DB trigger.'
    }

    def compute_hash(self) -> str:
        """
        Computes SHA-256 hash of the entry.
        Hash format: '{previous_hash}{actor}{action}{details}{created_at}'
        """
        # Convert created_at to a consistent string, handle None if not yet saved to DB
        dt_str = self.created_at.isoformat() if self.created_at else ""
        prev = self.previous_hash if self.previous_hash else "None"
        
        # Consistent JSON dump without spaces for predictable hashing
        details_str = json.dumps(self.details, sort_keys=True) if self.details is not None else "null"
        
        raw_string = f"{prev}{self.actor}{self.action}{details_str}{dt_str}"
        return hashlib.sha256(raw_string.encode('utf-8')).hexdigest()

    def __repr__(self) -> str:
        return f"<AuditTrail(id={self.id}, actor='{self.actor}', action='{self.action}', entry_hash='{self.entry_hash}')>"
