import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import validates, relationship
from backend.app.database import Base


class PlanTierEnum(enum.Enum):
    mini = "mini"
    parwa = "parwa"
    parwa_high = "parwa_high"


class Company(Base):
    """
    SQLAlchemy model representing a client company subscribing to the PARWA platform.
    """
    __tablename__ = "companies"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Column[str] = Column(String, index=True, nullable=False)
    industry: Column[str] = Column(String, nullable=False)
    plan_tier: Column[PlanTierEnum] = Column(Enum(PlanTierEnum), nullable=False)
    is_active: Column[bool] = Column(Boolean, default=True, nullable=False)
    rls_policy_id: Column[str] = Column(String, nullable=True)
    created_at: Column[datetime] = Column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Column[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationship to User model
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")

    @validates("plan_tier")
    def validate_plan_tier(self, key: str, plan_tier: str | PlanTierEnum) -> PlanTierEnum:
        """
        Validates that the plan tier is a valid enum value.
        """
        if isinstance(plan_tier, PlanTierEnum):
            return plan_tier
        try:
            return PlanTierEnum(plan_tier)
        except ValueError:
            valid_values = [e.value for e in PlanTierEnum]
            raise ValueError(f"Invalid plan_tier: {plan_tier}. Must be one of {valid_values}.")

    def __repr__(self) -> str:
        """
        String representation for debugging.
        """
        return f"<Company(id={self.id}, name='{self.name}', tier='{self.plan_tier.name}')>"
