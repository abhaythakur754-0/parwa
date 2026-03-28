"""
Churn Predictor Service

Predicts client churn probability using rule-based scoring and ML-ready
architecture. Generates weekly predictions for all tracked clients.
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class ChurnRiskLevel(str, Enum):
    """Churn risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskFactor:
    """Individual risk factor contributing to churn."""
    name: str
    weight: float  # 0.0 to 1.0
    score: float  # 0.0 to 100.0 (higher = more risky)
    weighted_score: float
    description: str
    data_source: str


@dataclass
class ChurnPrediction:
    """Churn prediction for a client."""
    client_id: str
    prediction_date: datetime
    churn_probability: float  # 0.0 to 1.0 (percentage)
    risk_level: ChurnRiskLevel
    risk_factors: List[RiskFactor]
    confidence_score: float  # 0.0 to 1.0
    recommended_actions: List[str]
    historical_accuracy: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ChurnPredictor:
    """
    Predict client churn probability.

    Uses weighted risk factors to calculate churn probability.
    Architecture is ML-ready for future model integration.
    """

    # Risk factor weights (must sum to 1.0)
    RISK_WEIGHTS = {
        "declining_usage": 0.25,
        "low_accuracy": 0.25,
        "support_tickets": 0.20,
        "payment_issues": 0.15,
        "low_engagement": 0.15,
    }

    # Risk thresholds for classification
    RISK_THRESHOLDS = {
        ChurnRiskLevel.LOW: 0.20,
        ChurnRiskLevel.MEDIUM: 0.40,
        ChurnRiskLevel.HIGH: 0.60,
        ChurnRiskLevel.CRITICAL: 0.80,
    }

    # All supported clients
    SUPPORTED_CLIENTS = [
        "client_001", "client_002", "client_003", "client_004", "client_005",
        "client_006", "client_007", "client_008", "client_009", "client_010"
    ]

    def __init__(self):
        """Initialize churn predictor."""
        self._predictions: Dict[str, List[ChurnPrediction]] = {
            client: [] for client in self.SUPPORTED_CLIENTS
        }
        self._accuracy_history: List[float] = []

    def predict(
        self,
        client_id: str,
        usage_trend: float = 0.0,
        accuracy_rate: float = 100.0,
        support_tickets_30d: int = 0,
        payment_issues: int = 0,
        engagement_score: float = 100.0
    ) -> ChurnPrediction:
        """
        Predict churn probability for a client.

        Args:
            client_id: Client identifier
            usage_trend: Usage change percentage (negative = declining)
            accuracy_rate: Current accuracy rate (0-100)
            support_tickets_30d: Support tickets in last 30 days
            payment_issues: Number of payment issues
            engagement_score: Engagement score (0-100)

        Returns:
            ChurnPrediction with probability and risk factors
        """
        if client_id not in self.SUPPORTED_CLIENTS:
            raise ValueError(f"Unsupported client: {client_id}")

        # Calculate risk factors
        risk_factors = self._calculate_risk_factors(
            usage_trend=usage_trend,
            accuracy_rate=accuracy_rate,
            support_tickets=support_tickets_30d,
            payment_issues=payment_issues,
            engagement_score=engagement_score
        )

        # Calculate weighted churn probability
        total_weighted_score = sum(rf.weighted_score for rf in risk_factors)
        churn_probability = total_weighted_score / 100.0  # Normalize to 0-1

        # Determine risk level
        risk_level = self._determine_risk_level(churn_probability)

        # Calculate confidence based on data completeness
        confidence = self._calculate_confidence(risk_factors)

        # Generate recommendations
        recommendations = self._generate_recommendations(risk_factors, risk_level)

        prediction = ChurnPrediction(
            client_id=client_id,
            prediction_date=datetime.utcnow(),
            churn_probability=round(churn_probability, 4),
            risk_level=risk_level,
            risk_factors=risk_factors,
            confidence_score=confidence,
            recommended_actions=recommendations,
            metadata={
                "usage_trend": usage_trend,
                "accuracy_rate": accuracy_rate,
                "support_tickets_30d": support_tickets_30d,
                "payment_issues": payment_issues,
                "engagement_score": engagement_score,
            }
        )

        # Store prediction
        self._predictions[client_id].append(prediction)
        logger.info(f"Churn prediction for {client_id}: {churn_probability:.1%} ({risk_level.value})")

        return prediction

    def predict_all_clients(
        self,
        client_data: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, ChurnPrediction]:
        """
        Generate predictions for all 10 clients.

        Args:
            client_data: Optional dict with client metrics

        Returns:
            Dict mapping client_id to prediction
        """
        predictions = {}

        for client_id in self.SUPPORTED_CLIENTS:
            if client_data and client_id in client_data:
                data = client_data[client_id]
                prediction = self.predict(
                    client_id=client_id,
                    usage_trend=data.get("usage_trend", 0),
                    accuracy_rate=data.get("accuracy_rate", 85),
                    support_tickets_30d=data.get("support_tickets_30d", 2),
                    payment_issues=data.get("payment_issues", 0),
                    engagement_score=data.get("engagement_score", 75)
                )
            else:
                # Generate simulated prediction
                prediction = self._simulate_prediction(client_id)

            predictions[client_id] = prediction

        logger.info(f"Generated churn predictions for {len(predictions)} clients")
        return predictions

    def _calculate_risk_factors(
        self,
        usage_trend: float,
        accuracy_rate: float,
        support_tickets: int,
        payment_issues: int,
        engagement_score: float
    ) -> List[RiskFactor]:
        """Calculate individual risk factor scores."""
        factors = []

        # Declining usage risk (negative trend = higher risk)
        usage_score = max(0, min(100, abs(usage_trend) if usage_trend < 0 else 0))
        factors.append(RiskFactor(
            name="declining_usage",
            weight=self.RISK_WEIGHTS["declining_usage"],
            score=usage_score,
            weighted_score=usage_score * self.RISK_WEIGHTS["declining_usage"],
            description=f"Usage {'declined' if usage_trend < 0 else 'stable'} by {abs(usage_trend):.1f}%",
            data_source="usage_analytics"
        ))

        # Low accuracy risk
        accuracy_score = max(0, 100 - accuracy_rate) if accuracy_rate < 80 else 0
        factors.append(RiskFactor(
            name="low_accuracy",
            weight=self.RISK_WEIGHTS["low_accuracy"],
            score=accuracy_score,
            weighted_score=accuracy_score * self.RISK_WEIGHTS["low_accuracy"],
            description=f"Accuracy at {accuracy_rate:.1f}% (target: 80%+)",
            data_source="quality_metrics"
        ))

        # Support tickets risk (scale: 0 tickets = 0 risk, 10+ tickets = 100 risk)
        ticket_score = min(100, support_tickets * 10)
        factors.append(RiskFactor(
            name="support_tickets",
            weight=self.RISK_WEIGHTS["support_tickets"],
            score=ticket_score,
            weighted_score=ticket_score * self.RISK_WEIGHTS["support_tickets"],
            description=f"{support_tickets} support tickets in last 30 days",
            data_source="support_system"
        ))

        # Payment issues risk
        payment_score = min(100, payment_issues * 25)
        factors.append(RiskFactor(
            name="payment_issues",
            weight=self.RISK_WEIGHTS["payment_issues"],
            score=payment_score,
            weighted_score=payment_score * self.RISK_WEIGHTS["payment_issues"],
            description=f"{payment_issues} payment issue(s) detected",
            data_source="billing_system"
        ))

        # Low engagement risk
        engagement_score_calc = max(0, 100 - engagement_score) if engagement_score < 60 else 0
        factors.append(RiskFactor(
            name="low_engagement",
            weight=self.RISK_WEIGHTS["low_engagement"],
            score=engagement_score_calc,
            weighted_score=engagement_score_calc * self.RISK_WEIGHTS["low_engagement"],
            description=f"Engagement score: {engagement_score:.1f}%",
            data_source="engagement_tracking"
        ))

        return factors

    def _determine_risk_level(self, probability: float) -> ChurnRiskLevel:
        """Determine risk level from probability."""
        if probability >= self.RISK_THRESHOLDS[ChurnRiskLevel.CRITICAL]:
            return ChurnRiskLevel.CRITICAL
        elif probability >= self.RISK_THRESHOLDS[ChurnRiskLevel.HIGH]:
            return ChurnRiskLevel.HIGH
        elif probability >= self.RISK_THRESHOLDS[ChurnRiskLevel.MEDIUM]:
            return ChurnRiskLevel.MEDIUM
        else:
            return ChurnRiskLevel.LOW

    def _calculate_confidence(self, risk_factors: List[RiskFactor]) -> float:
        """Calculate prediction confidence score."""
        # Higher confidence when more factors have non-zero scores
        active_factors = sum(1 for rf in risk_factors if rf.score > 0)
        base_confidence = 0.6 + (active_factors / len(risk_factors)) * 0.3
        return round(min(1.0, base_confidence), 2)

    def _generate_recommendations(
        self,
        risk_factors: List[RiskFactor],
        risk_level: ChurnRiskLevel
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Sort by weighted score (highest risk first)
        sorted_factors = sorted(risk_factors, key=lambda rf: rf.weighted_score, reverse=True)

        for rf in sorted_factors:
            if rf.weighted_score < 5:
                continue

            if rf.name == "declining_usage":
                recommendations.append(
                    "Schedule proactive check-in to understand usage decline. "
                    "Consider feature adoption campaign."
                )
            elif rf.name == "low_accuracy":
                recommendations.append(
                    "Review AI training data quality. "
                    "Schedule knowledge base optimization session."
                )
            elif rf.name == "support_tickets":
                recommendations.append(
                    "Escalate to customer success manager. "
                    "Review recent support tickets for patterns."
                )
            elif rf.name == "payment_issues":
                recommendations.append(
                    "Contact billing team to resolve payment issues. "
                    "Consider payment plan options."
                )
            elif rf.name == "low_engagement":
                recommendations.append(
                    "Launch re-engagement campaign. "
                    "Offer training session on underutilized features."
                )

        if risk_level in [ChurnRiskLevel.HIGH, ChurnRiskLevel.CRITICAL]:
            recommendations.insert(0, "URGENT: Assign dedicated success manager for retention")

        return recommendations[:5]  # Top 5 recommendations

    def _simulate_prediction(self, client_id: str) -> ChurnPrediction:
        """Generate simulated prediction for testing."""
        import random

        # Seed based on client_id for consistency
        seed = hash(client_id) % 1000
        random.seed(seed)

        return self.predict(
            client_id=client_id,
            usage_trend=random.uniform(-20, 5),
            accuracy_rate=random.uniform(70, 95),
            support_tickets_30d=random.randint(0, 8),
            payment_issues=random.randint(0, 2),
            engagement_score=random.uniform(50, 95)
        )

    def get_prediction_history(
        self,
        client_id: str,
        weeks: int = 4
    ) -> List[ChurnPrediction]:
        """Get historical predictions for a client."""
        history = self._predictions.get(client_id, [])
        return history[-weeks:] if history else []

    def update_accuracy_tracking(
        self,
        client_id: str,
        actual_churn: bool
    ) -> Optional[float]:
        """
        Update prediction accuracy tracking.

        Args:
            client_id: Client identifier
            actual_churn: Whether client actually churned

        Returns:
            Updated accuracy percentage
        """
        history = self._predictions.get(client_id, [])
        if not history:
            return None

        last_prediction = history[-1]
        predicted_churn = last_prediction.churn_probability > 0.5

        # Calculate accuracy for this prediction
        correct = predicted_churn == actual_churn
        self._accuracy_history.append(1.0 if correct else 0.0)

        # Calculate overall accuracy
        if self._accuracy_history:
            return round(sum(self._accuracy_history) / len(self._accuracy_history) * 100, 1)
        return None

    def get_at_risk_clients(
        self,
        risk_level: Optional[ChurnRiskLevel] = None
    ) -> List[ChurnPrediction]:
        """
        Get clients at risk of churning.

        Args:
            risk_level: Optional filter by specific risk level

        Returns:
            List of predictions for at-risk clients
        """
        at_risk = []

        for client_id in self.SUPPORTED_CLIENTS:
            history = self._predictions.get(client_id, [])
            if not history:
                continue

            latest = history[-1]
            if latest.risk_level in [ChurnRiskLevel.HIGH, ChurnRiskLevel.CRITICAL]:
                if risk_level is None or latest.risk_level == risk_level:
                    at_risk.append(latest)

        # Sort by probability (highest first)
        at_risk.sort(key=lambda p: p.churn_probability, reverse=True)
        return at_risk

    def get_prediction_summary(self) -> Dict[str, Any]:
        """Get summary of all predictions."""
        if not any(self._predictions.values()):
            return {"status": "no_predictions", "clients_predicted": 0}

        total = 0
        by_risk = {level.value: 0 for level in ChurnRiskLevel}
        avg_probability = 0

        for client_id in self.SUPPORTED_CLIENTS:
            history = self._predictions.get(client_id, [])
            if history:
                latest = history[-1]
                total += 1
                by_risk[latest.risk_level.value] += 1
                avg_probability += latest.churn_probability

        avg_probability = avg_probability / total if total > 0 else 0

        return {
            "clients_predicted": total,
            "average_churn_probability": round(avg_probability * 100, 1),
            "by_risk_level": by_risk,
            "at_risk_count": by_risk["high"] + by_risk["critical"],
            "historical_accuracy": round(sum(self._accuracy_history) / len(self._accuracy_history) * 100, 1)
                                   if self._accuracy_history else None,
        }
