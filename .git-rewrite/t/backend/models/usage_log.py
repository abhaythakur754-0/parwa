import uuid
import datetime
import enum
from sqlalchemy import Column, String, Date, DateTime, Integer, Float, ForeignKey, Enum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID

from backend.app.database import Base

class AITier(str, enum.Enum):
    light = "light"
    medium = "medium"
    heavy = "heavy"

class UsageLog(Base):
    """
    Model for tracking per-company API and AI usage for billing and analytics.
    """
    __tablename__ = "usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    log_date = Column(Date, index=True, nullable=False)
    ai_tier = Column(Enum(AITier, native_enum=False), nullable=False)
    request_count = Column(Integer, CheckConstraint('request_count >= 0'), nullable=False, default=0)
    token_count = Column(Integer, CheckConstraint('token_count >= 0'), nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    avg_latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if getattr(self, "request_count", None) is None:
            self.request_count = 0
        if getattr(self, "token_count", None) is None:
            self.token_count = 0
        if getattr(self, "error_count", None) is None:
            self.error_count = 0

    def __repr__(self) -> str:
        return f"<UsageLog(id={self.id}, company_id={self.company_id}, log_date={self.log_date}, tier={self.ai_tier}, tokens={self.token_count})>"
