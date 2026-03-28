"""
Client Health Models

SQLAlchemy models for client health tracking including:
- ClientHealthScore: Overall health scores per client
- HealthMetric: Individual health metrics
- HealthAlert: Health alerts
- HealthTrend: Trend tracking
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


class HealthStatusEnum(str, enum.Enum):
    """Health status levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class AlertSeverityEnum(str, enum.Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertTypeEnum(str, enum.Enum):
    """Types of health alerts."""
    HEALTH_SCORE_DROP = "health_score_drop"
    INACTIVITY = "inactivity"
    ACCURACY_DROP = "accuracy_drop"
    RESPONSE_TIME_HIGH = "response_time_high"
    RESOLUTION_RATE_LOW = "resolution_rate_low"
    ENGAGEMENT_LOW = "engagement_low"
    CHURN_RISK = "churn_risk"


class TrendDirectionEnum(str, enum.Enum):
    """Trend direction for health metrics."""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    CRITICAL = "critical"


class ClientHealthScore(Base):
    """
    SQLAlchemy model for client health scores.

    Stores daily health scores and snapshots for each client.
    """
    __tablename__ = "client_health_scores"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Column[str] = Column(String(50), nullable=False, index=True)
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    score_date: Column[date] = Column(
        Date, nullable=False, index=True,
        server_default=func.current_date()
    )
    overall_score: Column[float] = Column(Numeric(5, 2), nullable=False)
    status: Column[HealthStatusEnum] = Column(
        Enum(HealthStatusEnum), nullable=False
    )
    grade: Column[str] = Column(String(1), nullable=False)

    # Component scores
    activity_level: Column[float] = Column(Numeric(5, 2), default=0.0)
    accuracy_score: Column[float] = Column(Numeric(5, 2), default=0.0)
    response_time_score: Column[float] = Column(Numeric(5, 2), default=0.0)
    resolution_rate: Column[float] = Column(Numeric(5, 2), default=0.0)
    engagement_score: Column[float] = Column(Numeric(5, 2), default=0.0)

    # Trend data
    trend_direction: Column[TrendDirectionEnum] = Column(
        Enum(TrendDirectionEnum), default=TrendDirectionEnum.STABLE
    )
    previous_score: Column[float] = Column(Numeric(5, 2), nullable=True)
    score_change: Column[float] = Column(Numeric(5, 2), default=0.0)

    # Raw metrics
    raw_metrics: Column[dict] = Column(JSONB, default=dict)

    # Timestamps
    created_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Column[datetime] = Column(
        DateTime, onupdate=func.now(), default=datetime.utcnow, nullable=False
    )

    # Relationships
    company = relationship("Company", back_populates="health_scores")

    @validates("overall_score")
    def validate_score(self, key: str, score: float) -> float:
        """Validate score is within valid range."""
        if score < 0 or score > 100:
            raise ValueError("Score must be between 0 and 100")
        return round(score, 2)

    @validates("grade")
    def validate_grade(self, key: str, grade: str) -> str:
        """Validate grade is valid."""
        valid_grades = ["A", "B", "C", "D", "F"]
        if grade.upper() not in valid_grades:
            raise ValueError(f"Grade must be one of {valid_grades}")
        return grade.upper()

    def __repr__(self) -> str:
        return f"<ClientHealthScore(client={self.client_id}, score={self.overall_score}, grade={self.grade})>"


class HealthMetric(Base):
    """
    SQLAlchemy model for individual health metrics.

    Stores detailed metrics that contribute to health scores.
    """
    __tablename__ = "health_metrics"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Column[str] = Column(String(50), nullable=False, index=True)
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    metric_date: Column[date] = Column(
        Date, nullable=False, index=True,
        server_default=func.current_date()
    )
    metric_name: Column[str] = Column(String(100), nullable=False, index=True)
    metric_value: Column[float] = Column(Numeric(10, 4), nullable=False)
    metric_unit: Column[str] = Column(String(50), nullable=True)

    # Trend and comparison
    trend_direction: Column[str] = Column(String(20), nullable=True)
    previous_value: Column[float] = Column(Numeric(10, 4), nullable=True)
    change_percentage: Column[float] = Column(Numeric(5, 2), nullable=True)

    # Thresholds
    threshold_warning: Column[float] = Column(Numeric(10, 4), nullable=True)
    threshold_critical: Column[float] = Column(Numeric(10, 4), nullable=True)
    is_alert_triggered: Column[bool] = Column(Boolean, default=False)

    # Metadata
    metadata_json: Column[dict] = Column(JSONB, default=dict)
    created_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False
    )

    @validates("metric_name")
    def validate_metric_name(self, key: str, name: str) -> str:
        """Validate metric name."""
        if not name or len(name.strip()) == 0:
            raise ValueError("Metric name cannot be empty")
        return name.strip().lower()

    def __repr__(self) -> str:
        return f"<HealthMetric(client={self.client_id}, name={self.metric_name}, value={self.metric_value})>"


class HealthAlert(Base):
    """
    SQLAlchemy model for health alerts.

    Stores alerts generated when health metrics breach thresholds.
    """
    __tablename__ = "health_alerts"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alert_id: Column[str] = Column(String(50), unique=True, nullable=False)
    client_id: Column[str] = Column(String(50), nullable=False, index=True)
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Alert details
    alert_type: Column[AlertTypeEnum] = Column(
        Enum(AlertTypeEnum), nullable=False, index=True
    )
    severity: Column[AlertSeverityEnum] = Column(
        Enum(AlertSeverityEnum), nullable=False, index=True
    )
    title: Column[str] = Column(String(255), nullable=False)
    message: Column[str] = Column(Text, nullable=False)

    # Status
    acknowledged: Column[bool] = Column(Boolean, default=False, index=True)
    acknowledged_by: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    acknowledged_at: Column[datetime] = Column(DateTime, nullable=True)
    resolved: Column[bool] = Column(Boolean, default=False)
    resolved_at: Column[datetime] = Column(DateTime, nullable=True)

    # Context
    metric_name: Column[str] = Column(String(100), nullable=True)
    metric_value: Column[float] = Column(Numeric(10, 4), nullable=True)
    threshold_value: Column[float] = Column(Numeric(10, 4), nullable=True)

    # Additional data
    metadata_json: Column[dict] = Column(JSONB, default=dict)

    # Timestamps
    triggered_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
    created_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Column[datetime] = Column(
        DateTime, onupdate=func.now(), default=datetime.utcnow
    )

    # Relationships
    company = relationship("Company", back_populates="health_alerts")

    @validates("severity")
    def validate_severity(self, key: str, severity: str) -> AlertSeverityEnum:
        """Validate and convert severity."""
        if isinstance(severity, AlertSeverityEnum):
            return severity
        try:
            return AlertSeverityEnum(severity.lower())
        except ValueError:
            raise ValueError(f"Invalid severity: {severity}")

    def acknowledge(self, user_id: uuid.UUID) -> None:
        """Mark alert as acknowledged."""
        self.acknowledged = True
        self.acknowledged_by = user_id
        self.acknowledged_at = datetime.utcnow()

    def resolve(self) -> None:
        """Mark alert as resolved."""
        self.resolved = True
        self.resolved_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<HealthAlert(id={self.alert_id}, client={self.client_id}, type={self.alert_type})>"


class HealthTrend(Base):
    """
    SQLAlchemy model for health trends.

    Stores historical trend data for analysis.
    """
    __tablename__ = "health_trends"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Column[str] = Column(String(50), nullable=False, index=True)
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Trend period
    period_start: Column[date] = Column(Date, nullable=False, index=True)
    period_end: Column[date] = Column(Date, nullable=False, index=True)
    period_type: Column[str] = Column(String(20), default="weekly")  # daily, weekly, monthly

    # Trend data
    trend_direction: Column[TrendDirectionEnum] = Column(
        Enum(TrendDirectionEnum), nullable=False
    )
    start_value: Column[float] = Column(Numeric(5, 2), nullable=False)
    end_value: Column[float] = Column(Numeric(5, 2), nullable=False)
    change_value: Column[float] = Column(Numeric(5, 2), nullable=False)
    change_percentage: Column[float] = Column(Numeric(5, 2), nullable=False)

    # Statistics
    min_value: Column[float] = Column(Numeric(5, 2), nullable=True)
    max_value: Column[float] = Column(Numeric(5, 2), nullable=True)
    avg_value: Column[float] = Column(Numeric(5, 2), nullable=True)
    volatility: Column[float] = Column(Numeric(5, 2), nullable=True)

    # Metric being tracked
    metric_name: Column[str] = Column(String(100), nullable=False)

    # Timestamps
    created_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<HealthTrend(client={self.client_id}, metric={self.metric_name}, trend={self.trend_direction})>"


class ClientHealthSummary:
    """
    Non-persisted model for client health summaries.

    Used for aggregating and presenting health data.
    """
    def __init__(
        self,
        client_id: str,
        company_id: uuid.UUID,
        overall_score: float,
        status: HealthStatusEnum,
        grade: str,
        trend: TrendDirectionEnum,
        metrics: List[dict],
        alerts: List[dict],
        recommendations: List[str]
    ):
        self.client_id = client_id
        self.company_id = company_id
        self.overall_score = overall_score
        self.status = status
        self.grade = grade
        self.trend = trend
        self.metrics = metrics
        self.alerts = alerts
        self.recommendations = recommendations
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "client_id": self.client_id,
            "company_id": str(self.company_id),
            "overall_score": self.overall_score,
            "status": self.status.value,
            "grade": self.grade,
            "trend": self.trend.value,
            "metrics": self.metrics,
            "alerts": self.alerts,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat(),
        }
