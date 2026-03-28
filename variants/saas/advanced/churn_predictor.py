"""
Churn Predictor for SaaS Advanced Module.

Provides ML-based churn prediction including:
- ML-based churn prediction
- Feature extraction from usage patterns
- Engagement metrics analysis
- Support ticket frequency analysis
- Payment history analysis
- Predictive model scoring
- Churn probability calculation
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


class ChurnRisk(str, Enum):
    """Churn risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChurnSignal(str, Enum):
    """Types of churn signals."""
    USAGE_DECLINE = "usage_decline"
    PAYMENT_FAILURE = "payment_failure"
    SUPPORT_ESCALATION = "support_escalation"
    ENGAGEMENT_DROP = "engagement_drop"
    FEATURE_ABANDONMENT = "feature_abandonment"
    NEGATIVE_SENTIMENT = "negative_sentiment"
    COMPETITOR_MENTION = "competitor_mention"
    CONTRACT_ENDING = "contract_ending"


@dataclass
class ChurnPrediction:
    """Represents a churn prediction result."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    prediction_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    churn_probability: float = 0.0
    risk_level: ChurnRisk = ChurnRisk.LOW
    signals: List[str] = field(default_factory=list)
    feature_scores: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    recommended_actions: List[str] = field(default_factory=list)
    predicted_churn_date: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "prediction_date": self.prediction_date.isoformat(),
            "churn_probability": round(self.churn_probability, 4),
            "risk_level": self.risk_level.value,
            "signals": self.signals,
            "feature_scores": self.feature_scores,
            "confidence": round(self.confidence, 4),
            "recommended_actions": self.recommended_actions,
            "predicted_churn_date": self.predicted_churn_date.isoformat() if self.predicted_churn_date else None,
        }


@dataclass
class CustomerFeatures:
    """Customer features for churn prediction."""
    client_id: str = ""
    days_since_signup: int = 0
    monthly_usage_trend: float = 0.0
    login_frequency_30d: int = 0
    feature_adoption_rate: float = 0.0
    support_tickets_30d: int = 0
    avg_ticket_sentiment: float = 0.0
    payment_failures_90d: int = 0
    days_since_last_payment: int = 0
    subscription_changes_90d: int = 0
    nps_score: Optional[int] = None
    last_feature_used_days: int = 0
    team_member_count: int = 1
    active_team_members: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "client_id": self.client_id,
            "days_since_signup": self.days_since_signup,
            "monthly_usage_trend": self.monthly_usage_trend,
            "login_frequency_30d": self.login_frequency_30d,
            "feature_adoption_rate": self.feature_adoption_rate,
            "support_tickets_30d": self.support_tickets_30d,
            "avg_ticket_sentiment": self.avg_ticket_sentiment,
            "payment_failures_90d": self.payment_failures_90d,
            "days_since_last_payment": self.days_since_last_payment,
            "subscription_changes_90d": self.subscription_changes_90d,
            "nps_score": self.nps_score,
            "last_feature_used_days": self.last_feature_used_days,
            "team_member_count": self.team_member_count,
            "active_team_members": self.active_team_members,
        }


# Feature weights for churn prediction model
FEATURE_WEIGHTS = {
    "days_since_signup": -0.05,  # Longer tenure = lower churn
    "monthly_usage_trend": -0.15,  # Positive trend = lower churn
    "login_frequency_30d": -0.10,  # More logins = lower churn
    "feature_adoption_rate": -0.12,  # Higher adoption = lower churn
    "support_tickets_30d": 0.08,  # More tickets = higher churn
    "avg_ticket_sentiment": -0.10,  # Positive sentiment = lower churn
    "payment_failures_90d": 0.20,  # Payment failures = higher churn
    "days_since_last_payment": 0.15,  # Longer since payment = higher churn
    "subscription_changes_90d": 0.10,  # More changes = higher churn
    "nps_score": -0.08,  # Higher NPS = lower churn
    "last_feature_used_days": 0.12,  # Longer since use = higher churn
    "team_engagement": -0.05,  # Higher engagement = lower churn
}

# Risk thresholds
RISK_THRESHOLDS = {
    ChurnRisk.LOW: 0.20,
    ChurnRisk.MEDIUM: 0.40,
    ChurnRisk.HIGH: 0.60,
    ChurnRisk.CRITICAL: 0.80,
}


class ChurnPredictor:
    """
    Predicts customer churn probability.

    Features:
    - ML-based prediction model
    - Feature extraction
    - Engagement analysis
    - Support ticket analysis
    - Payment history analysis
    - Action recommendations
    """

    def __init__(self, model_version: str = "1.0.0"):
        """
        Initialize churn predictor.

        Args:
            model_version: Model version to use
        """
        self.model_version = model_version
        self._predictions: Dict[str, ChurnPrediction] = {}

    async def predict(
        self,
        features: CustomerFeatures
    ) -> ChurnPrediction:
        """
        Predict churn probability for a customer.

        Args:
            features: Customer features for prediction

        Returns:
            ChurnPrediction with probability and risk level
        """
        # Extract and normalize features
        feature_scores = await self._calculate_feature_scores(features)

        # Calculate weighted probability
        probability = await self._calculate_probability(feature_scores)

        # Determine risk level
        risk_level = self._determine_risk_level(probability)

        # Identify churn signals
        signals = await self._identify_signals(features)

        # Generate recommendations
        recommendations = await self._generate_recommendations(
            risk_level, signals, features
        )

        # Predict churn date if high risk
        predicted_date = None
        if risk_level in [ChurnRisk.HIGH, ChurnRisk.CRITICAL]:
            days_to_churn = int(30 * (1 - probability + 0.5))
            predicted_date = datetime.now(timezone.utc) + timedelta(days=days_to_churn)

        prediction = ChurnPrediction(
            client_id=features.client_id,
            churn_probability=probability,
            risk_level=risk_level,
            signals=[s.value for s in signals],
            feature_scores=feature_scores,
            confidence=self._calculate_confidence(features),
            recommended_actions=recommendations,
            predicted_churn_date=predicted_date,
        )

        self._predictions[features.client_id] = prediction

        logger.info(
            "Churn prediction calculated",
            extra={
                "client_id": features.client_id,
                "probability": probability,
                "risk_level": risk_level.value,
            }
        )

        return prediction

    async def extract_features(
        self,
        client_id: str,
        usage_data: Dict[str, Any],
        support_data: Dict[str, Any],
        payment_data: Dict[str, Any],
        engagement_data: Dict[str, Any]
    ) -> CustomerFeatures:
        """
        Extract features for churn prediction.

        Args:
            client_id: Client identifier
            usage_data: Usage metrics data
            support_data: Support ticket data
            payment_data: Payment history data
            engagement_data: Engagement metrics data

        Returns:
            CustomerFeatures for prediction
        """
        features = CustomerFeatures(client_id=client_id)

        # Usage features
        features.days_since_signup = usage_data.get("days_since_signup", 0)
        features.monthly_usage_trend = usage_data.get("monthly_usage_trend", 0.0)
        features.feature_adoption_rate = usage_data.get("feature_adoption_rate", 0.0)
        features.last_feature_used_days = usage_data.get("last_feature_used_days", 0)

        # Support features
        features.support_tickets_30d = support_data.get("tickets_30d", 0)
        features.avg_ticket_sentiment = support_data.get("avg_sentiment", 0.5)

        # Payment features
        features.payment_failures_90d = payment_data.get("failures_90d", 0)
        features.days_since_last_payment = payment_data.get("days_since_last", 0)
        features.subscription_changes_90d = payment_data.get("changes_90d", 0)

        # Engagement features
        features.login_frequency_30d = engagement_data.get("logins_30d", 0)
        features.nps_score = engagement_data.get("nps_score")
        features.team_member_count = engagement_data.get("team_count", 1)
        features.active_team_members = engagement_data.get("active_members", 1)

        return features

    async def batch_predict(
        self,
        customers: List[CustomerFeatures]
    ) -> List[ChurnPrediction]:
        """
        Predict churn for multiple customers.

        Args:
            customers: List of customer features

        Returns:
            List of churn predictions
        """
        predictions = []
        for customer in customers:
            prediction = await self.predict(customer)
            predictions.append(prediction)

        # Sort by risk level
        risk_order = {
            ChurnRisk.CRITICAL: 0,
            ChurnRisk.HIGH: 1,
            ChurnRisk.MEDIUM: 2,
            ChurnRisk.LOW: 3,
        }
        predictions.sort(key=lambda p: risk_order[p.risk_level])

        return predictions

    async def get_at_risk_customers(
        self,
        min_risk: ChurnRisk = ChurnRisk.MEDIUM
    ) -> List[ChurnPrediction]:
        """
        Get customers at or above risk threshold.

        Args:
            min_risk: Minimum risk level

        Returns:
            List of at-risk predictions
        """
        risk_levels = {
            ChurnRisk.LOW: 0,
            ChurnRisk.MEDIUM: 1,
            ChurnRisk.HIGH: 2,
            ChurnRisk.CRITICAL: 3,
        }

        min_level = risk_levels.get(min_risk, 1)

        return [
            p for p in self._predictions.values()
            if risk_levels.get(p.risk_level, 0) >= min_level
        ]

    async def get_prediction(self, client_id: str) -> Optional[ChurnPrediction]:
        """
        Get cached prediction for a client.

        Args:
            client_id: Client identifier

        Returns:
            ChurnPrediction if exists
        """
        return self._predictions.get(client_id)

    async def _calculate_feature_scores(
        self,
        features: CustomerFeatures
    ) -> Dict[str, float]:
        """Calculate normalized feature scores."""
        scores = {}

        # Days since signup (normalize to 0-1, cap at 365 days)
        scores["days_since_signup"] = min(features.days_since_signup / 365, 1.0)

        # Usage trend (normalize to 0-1, range -1 to 1)
        scores["monthly_usage_trend"] = (features.monthly_usage_trend + 1) / 2

        # Login frequency (normalize, cap at 30 logins = daily)
        scores["login_frequency_30d"] = min(features.login_frequency_30d / 30, 1.0)

        # Feature adoption (already 0-1)
        scores["feature_adoption_rate"] = features.feature_adoption_rate

        # Support tickets (normalize, cap at 10)
        scores["support_tickets_30d"] = min(features.support_tickets_30d / 10, 1.0)

        # Sentiment (already 0-1)
        scores["avg_ticket_sentiment"] = features.avg_ticket_sentiment

        # Payment failures (normalize, cap at 3)
        scores["payment_failures_90d"] = min(features.payment_failures_90d / 3, 1.0)

        # Days since payment (normalize, cap at 45)
        scores["days_since_last_payment"] = min(features.days_since_last_payment / 45, 1.0)

        # Subscription changes (normalize, cap at 3)
        scores["subscription_changes_90d"] = min(features.subscription_changes_90d / 3, 1.0)

        # NPS score (normalize to 0-1)
        if features.nps_score is not None:
            scores["nps_score"] = (features.nps_score + 100) / 200
        else:
            scores["nps_score"] = 0.5  # Neutral if unknown

        # Last feature use (normalize, cap at 30)
        scores["last_feature_used_days"] = min(features.last_feature_used_days / 30, 1.0)

        # Team engagement
        if features.team_member_count > 0:
            scores["team_engagement"] = features.active_team_members / features.team_member_count
        else:
            scores["team_engagement"] = 1.0

        return scores

    async def _calculate_probability(
        self,
        feature_scores: Dict[str, float]
    ) -> float:
        """Calculate churn probability from feature scores."""
        weighted_sum = 0.0
        total_weight = 0.0

        for feature, score in feature_scores.items():
            weight = FEATURE_WEIGHTS.get(feature, 0.0)
            weighted_sum += score * abs(weight)
            total_weight += abs(weight)

        if total_weight == 0:
            return 0.5

        # Normalize to 0-1
        base_probability = weighted_sum / total_weight

        # Apply sigmoid for smooth probability
        probability = 1 / (1 + math.exp(-10 * (base_probability - 0.5)))

        return probability

    def _determine_risk_level(self, probability: float) -> ChurnRisk:
        """Determine risk level from probability."""
        if probability >= RISK_THRESHOLDS[ChurnRisk.CRITICAL]:
            return ChurnRisk.CRITICAL
        elif probability >= RISK_THRESHOLDS[ChurnRisk.HIGH]:
            return ChurnRisk.HIGH
        elif probability >= RISK_THRESHOLDS[ChurnRisk.MEDIUM]:
            return ChurnRisk.MEDIUM
        else:
            return ChurnRisk.LOW

    async def _identify_signals(
        self,
        features: CustomerFeatures
    ) -> List[ChurnSignal]:
        """Identify churn signals from features."""
        signals = []

        if features.monthly_usage_trend < -0.3:
            signals.append(ChurnSignal.USAGE_DECLINE)

        if features.payment_failures_90d > 0:
            signals.append(ChurnSignal.PAYMENT_FAILURE)

        if features.support_tickets_30d > 5:
            signals.append(ChurnSignal.SUPPORT_ESCALATION)

        if features.login_frequency_30d < 5:
            signals.append(ChurnSignal.ENGAGEMENT_DROP)

        if features.feature_adoption_rate < 0.3:
            signals.append(ChurnSignal.FEATURE_ABANDONMENT)

        if features.avg_ticket_sentiment < 0.3:
            signals.append(ChurnSignal.NEGATIVE_SENTIMENT)

        if features.last_feature_used_days > 14:
            signals.append(ChurnSignal.FEATURE_ABANDONMENT)

        return signals

    async def _generate_recommendations(
        self,
        risk_level: ChurnRisk,
        signals: List[str],
        features: CustomerFeatures
    ) -> List[str]:
        """Generate action recommendations."""
        recommendations = []

        if risk_level == ChurnRisk.CRITICAL:
            recommendations.append("Immediate outreach from customer success team")
            recommendations.append("Schedule executive business review")

        if risk_level in [ChurnRisk.HIGH, ChurnRisk.CRITICAL]:
            recommendations.append("Assign dedicated success manager")
            recommendations.append("Review recent support interactions")

        if ChurnSignal.USAGE_DECLINE.value in signals:
            recommendations.append("Proactive check-in on usage goals")
            recommendations.append("Offer training session on key features")

        if ChurnSignal.PAYMENT_FAILURE.value in signals:
            recommendations.append("Contact billing department")
            recommendations.append("Offer payment plan options")

        if ChurnSignal.SUPPORT_ESCALATION.value in signals:
            recommendations.append("Review open support tickets")
            recommendations.append("Escalate to senior support")

        if ChurnSignal.ENGAGEMENT_DROP.value in signals:
            recommendations.append("Send re-engagement campaign")
            recommendations.append("Offer feature spotlight email")

        if ChurnSignal.FEATURE_ABANDONMENT.value in signals:
            recommendations.append("Schedule product demo")
            recommendations.append("Share feature best practices")

        if features.nps_score is not None and features.nps_score < 0:
            recommendations.append("Conduct detractor follow-up call")

        return recommendations[:5]  # Limit to top 5

    def _calculate_confidence(self, features: CustomerFeatures) -> float:
        """Calculate prediction confidence based on data completeness."""
        confidence = 1.0

        if features.nps_score is None:
            confidence -= 0.1

        if features.days_since_signup < 30:
            confidence -= 0.15

        if features.login_frequency_30d == 0:
            confidence -= 0.1

        return max(0.5, confidence)


# Export for testing
__all__ = [
    "ChurnPredictor",
    "ChurnPrediction",
    "CustomerFeatures",
    "ChurnRisk",
    "ChurnSignal",
    "FEATURE_WEIGHTS",
    "RISK_THRESHOLDS",
]
