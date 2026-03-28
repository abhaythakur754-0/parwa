"""
Churn Models

SQLAlchemy models for churn prediction and prevention including:
- ChurnPrediction: Predictions for client churn
- RiskScore: Risk scores for clients
- RetentionAction: Actions taken to prevent churn
- Intervention: Automated interventions
"""
import enum
import uuid
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import Column, String, Boolean, DateTime, Date, Enum, ForeignKey, Numeric, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import validates, relationship
from sqlalchemy.sql import func
from backend.app.database import Base


class ChurnRiskLevel(str, enum.Enum):
    """Churn risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(str, enum.Enum):
    """Categories of risk."""
    USAGE = "usage"
    QUALITY = "quality"
    SUPPORT = "support"
    FINANCIAL = "financial"
    ENGAGEMENT = "engagement"


class ActionType(str, enum.Enum):
    """Types of retention actions."""
    CHECK_IN = "check_in"
    TRAINING = "training"
    FEATURE_DEMO = "feature_demo"
    SUCCESS_REVIEW = "success_review"
    ESCALATION = "escalation"
    DISCOUNT = "discount"
    PLAN_UPGRADE = "plan_upgrade"
    PERSONALIZED_OUTREACH = "personalized_outreach"
    ONBOARDING_REVIEW = "onboarding_review"
    EXECUTIVE_SPONSOR = "executive_sponsor"


class ActionStatus(str, enum.Enum):
    """Status of retention actions."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InterventionType(str, enum.Enum):
    """Types of automated interventions."""
    AUTOMATED_CHECK_IN = "automated_check_in"
    PROACTIVE_SUPPORT = "proactive_support"
    FEATURE_NUDGE = "feature_nudge"
    SUCCESS_MANAGER_ALERT = "success_manager_alert"
    WIN_BACK_CAMPAIGN = "win_back_campaign"
    USAGE_TIP = "usage_tip"
    TRAINING_OFFER = "training_offer"
    RENEWAL_REMINDER = "renewal_reminder"


class InterventionStatus(str, enum.Enum):
    """Status of an intervention."""
    PENDING = "pending"
    TRIGGERED = "triggered"
    SENT = "sent"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ChurnPrediction(Base):
    """
    SQLAlchemy model for churn predictions.

    Stores weekly churn predictions for each client.
    """
    __tablename__ = "churn_predictions"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    prediction_id: Column[str] = Column(String(50), unique=True, nullable=False)
    client_id: Column[str] = Column(String(50), nullable=False, index=True)
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    prediction_date: Column[date] = Column(
        Date, nullable=False, index=True,
        server_default=func.current_date()
    )

    # Prediction results
    churn_probability: Column[float] = Column(Numeric(5, 4), nullable=False)
    risk_level: Column[ChurnRiskLevel] = Column(
        Enum(ChurnRiskLevel), nullable=False, index=True
    )
    confidence_score: Column[float] = Column(Numeric(3, 2), default=0.0)

    # Risk factors (JSON)
    risk_factors: Column[dict] = Column(JSONB, default=list)

    # Recommendations
    recommended_actions: Column[list] = Column(JSONB, default=list)

    # Accuracy tracking
    actual_outcome: Column[bool] = Column(Boolean, nullable=True)
    prediction_accurate: Column[bool] = Column(Boolean, nullable=True)
    outcome_recorded_at: Column[datetime] = Column(DateTime, nullable=True)

    # Metadata
    model_version: Column[str] = Column(String(50), default="rule_based_v1")
    metadata_json: Column[dict] = Column(JSONB, default=dict)

    # Timestamps
    created_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Column[datetime] = Column(
        DateTime, onupdate=func.now(), default=datetime.utcnow
    )

    # Relationships
    company = relationship("Company", back_populates="churn_predictions")

    @validates("churn_probability")
    def validate_probability(self, key: str, value: float) -> float:
        """Validate probability is between 0 and 1."""
        if value < 0 or value > 1:
            raise ValueError("Probability must be between 0 and 1")
        return value

    def __repr__(self) -> str:
        return f"<ChurnPrediction(client={self.client_id}, probability={self.churn_probability:.2%})>"


class RiskScore(Base):
    """
    SQLAlchemy model for risk scores.

    Stores detailed risk scores for clients.
    """
    __tablename__ = "risk_scores"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    score_id: Column[str] = Column(String(50), unique=True, nullable=False)
    client_id: Column[str] = Column(String(50), nullable=False, index=True)
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Overall score
    overall_score: Column[float] = Column(Numeric(5, 2), nullable=False)
    risk_level: Column[str] = Column(String(20), nullable=False, index=True)

    # Component scores
    usage_risk_score: Column[float] = Column(Numeric(5, 2), default=0.0)
    quality_risk_score: Column[float] = Column(Numeric(5, 2), default=0.0)
    support_risk_score: Column[float] = Column(Numeric(5, 2), default=0.0)
    financial_risk_score: Column[float] = Column(Numeric(5, 2), default=0.0)
    engagement_risk_score: Column[float] = Column(Numeric(5, 2), default=0.0)

    # Trend
    trend_direction: Column[str] = Column(String(20), default="stable")
    previous_score: Column[float] = Column(Numeric(5, 2), nullable=True)

    # Primary risk factor
    primary_risk_factor: Column[str] = Column(String(50), nullable=True)

    # Details (JSON)
    component_details: Column[dict] = Column(JSONB, default=dict)

    # Timestamps
    calculated_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
    created_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<RiskScore(client={self.client_id}, score={self.overall_score}, level={self.risk_level})>"


class RetentionAction(Base):
    """
    SQLAlchemy model for retention actions.

    Stores actions taken to prevent client churn.
    """
    __tablename__ = "retention_actions"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    action_id: Column[str] = Column(String(50), unique=True, nullable=False)
    client_id: Column[str] = Column(String(50), nullable=False, index=True)
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Action details
    action_type: Column[ActionType] = Column(
        Enum(ActionType), nullable=False, index=True
    )
    priority: Column[str] = Column(String(20), nullable=False)
    status: Column[ActionStatus] = Column(
        Enum(ActionStatus), nullable=False, index=True
    )
    title: Column[str] = Column(String(255), nullable=False)
    description: Column[str] = Column(Text, nullable=True)

    # Assignment
    assigned_to: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Scheduling
    scheduled_for: Column[datetime] = Column(DateTime, nullable=True)
    completed_at: Column[datetime] = Column(DateTime, nullable=True)

    # Outcome
    outcome: Column[str] = Column(Text, nullable=True)
    success: Column[bool] = Column(Boolean, nullable=True)
    impact_score: Column[float] = Column(Numeric(5, 2), default=0.0)

    # Metadata
    metadata_json: Column[dict] = Column(JSONB, default=dict)

    # Timestamps
    created_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Column[datetime] = Column(
        DateTime, onupdate=func.now(), default=datetime.utcnow
    )

    # Relationships
    company = relationship("Company", back_populates="retention_actions")

    def __repr__(self) -> str:
        return f"<RetentionAction(id={self.action_id}, client={self.client_id}, type={self.action_type})>"


class Intervention(Base):
    """
    SQLAlchemy model for automated interventions.

    Stores records of automated interventions triggered.
    """
    __tablename__ = "interventions"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    intervention_id: Column[str] = Column(String(50), unique=True, nullable=False)
    client_id: Column[str] = Column(String(50), nullable=False, index=True)
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Intervention details
    intervention_type: Column[InterventionType] = Column(
        Enum(InterventionType), nullable=False, index=True
    )
    status: Column[InterventionStatus] = Column(
        Enum(InterventionStatus), nullable=False, index=True
    )
    trigger_condition: Column[str] = Column(String(50), nullable=False)
    template_used: Column[str] = Column(String(100), nullable=True)

    # Channel and content
    channel: Column[str] = Column(String(20), nullable=True)
    recipient: Column[str] = Column(String(255), nullable=True)
    subject: Column[str] = Column(String(255), nullable=True)
    body: Column[str] = Column(Text, nullable=True)

    # Timing
    triggered_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
    sent_at: Column[datetime] = Column(DateTime, nullable=True)
    completed_at: Column[datetime] = Column(DateTime, nullable=True)

    # Response tracking
    response_received: Column[bool] = Column(Boolean, default=False)
    response_at: Column[datetime] = Column(DateTime, nullable=True)
    response_content: Column[str] = Column(Text, nullable=True)

    # Metadata
    metadata_json: Column[dict] = Column(JSONB, default=dict)
    created_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    company = relationship("Company", back_populates="interventions")

    def __repr__(self) -> str:
        return f"<Intervention(id={self.intervention_id}, client={self.client_id}, type={self.intervention_type})>"


class ChurnSummary:
    """
    Non-persisted model for churn summary data.

    Used for aggregating and presenting churn data.
    """
    def __init__(
        self,
        client_id: str,
        company_id: uuid.UUID,
        churn_probability: float,
        risk_level: ChurnRiskLevel,
        risk_score: float,
        recent_interventions: List[dict],
        recommended_actions: List[str]
    ):
        self.client_id = client_id
        self.company_id = company_id
        self.churn_probability = churn_probability
        self.risk_level = risk_level
        self.risk_score = risk_score
        self.recent_interventions = recent_interventions
        self.recommended_actions = recommended_actions
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "client_id": self.client_id,
            "company_id": str(self.company_id),
            "churn_probability": round(self.churn_probability * 100, 1),
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "recent_interventions": self.recent_interventions,
            "recommended_actions": self.recommended_actions,
            "timestamp": self.timestamp.isoformat(),
        }
