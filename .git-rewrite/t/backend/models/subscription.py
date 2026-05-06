"""
SQLAlchemy model for Subscription.
"""
import uuid
import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship, validates
from sqlalchemy.dialects.postgresql import UUID
from backend.app.database import Base

class Subscription(Base):
    """
    Model representing a billing subscription tied to a company.
    """
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    stripe_subscription_id = Column(String, nullable=True, index=True)
    plan_tier = Column(String, nullable=False)
    status = Column(String, nullable=False)
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    amount_cents = Column(Integer, CheckConstraint('amount_cents > 0'), nullable=False)
    currency = Column(String, default='usd', nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    
    company = relationship("Company", backref="subscriptions")

    @validates('plan_tier')
    def validate_plan_tier(self, key: str, value: str) -> str:
        """Ensure plan_tier is one of the valid enum values."""
        if value not in ["mini", "parwa", "parwa_high"]:
            raise ValueError(f"Invalid {key}: {value}")
        return value

    @validates('status')
    def validate_status(self, key: str, value: str) -> str:
        """Ensure status is one of the valid enum values."""
        if value not in ["active", "past_due", "canceled", "trialing"]:
            raise ValueError(f"Invalid {key}: {value}")
        return value

    def is_active_subscription(self) -> bool:
        """
        Returns True if status is 'active'.
        """
        return self.status == 'active'

    def __repr__(self) -> str:
        """Readable representation of the model with masked sensitive data."""
        stripe_id = f"***{self.stripe_subscription_id[-4:]}" if self.stripe_subscription_id else "None"
        return f"<Subscription (Tier: {self.plan_tier}, Status: {self.status}, Stripe ID: {stripe_id})>"
