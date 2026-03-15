import uuid
import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID

from backend.app.database import Base

class SLABreach(Base):
    """
    Model for logging SLA violations (e.g., tickets stuck for 24+ hrs without approval).
    """
    __tablename__ = "sla_breaches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("support_tickets.id"), nullable=False)
    breach_phase = Column(Integer, CheckConstraint('breach_phase IN (1, 2, 3)'), nullable=False)
    breach_triggered_at = Column(DateTime(timezone=True), nullable=False)
    hours_overdue = Column(Float, nullable=False)
    notified_to = Column(String, nullable=False) # email or role
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    def is_resolved(self) -> bool:
        """Returns True if resolved_at is set."""
        return self.resolved_at is not None

    def __repr__(self) -> str:
        return f"<SLABreach(id={self.id}, ticket_id={self.ticket_id}, phase={self.breach_phase}, overdue={self.hours_overdue})>"
