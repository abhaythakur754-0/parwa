import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import validates
from backend.app.database import Base


class TrainingData(Base):
    """
    SQLAlchemy model for storing anonymized support interactions for AI fine-tuning.
    """
    __tablename__ = "training_data"

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    ticket_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="SET NULL"), nullable=True
    )
    
    # CRITICAL: raw_interaction contains PII and must be treated as sensitive.
    # It should be encrypted at rest or moved to a more secure store in production.
    raw_interaction: Column[str] = Column(Text, nullable=False)
    
    anonymized_interaction: Column[str] = Column(Text, nullable=False)
    
    sentiment_score: Column[float] = Column(Float, nullable=False)
    
    extra_metadata: Column[dict] = Column(JSON, nullable=True)
    
    created_at: Column[datetime] = Column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    @validates("sentiment_score")
    def validate_sentiment_score(self, key: str, value: float) -> float:
        """
        Validates that sentiment_score is between -1.0 and 1.0.
        """
        if not -1.0 <= value <= 1.0:
            raise ValueError(f"sentiment_score must be between -1 and 1. Got: {value}")
        return value

    def anonymize(self) -> str:
        """
        Stub for anonymization logic to be implemented in Week 4.
        Currently returns a placeholder.
        """
        # TODO: Implement actual PII scrubbing logic
        return "[ANONYMIZED INTERACTION]"

    def __repr__(self) -> str:
        return f"<TrainingData(id={self.id}, company_id={self.company_id}, sentiment={self.sentiment_score})>"
