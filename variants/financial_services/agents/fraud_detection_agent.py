"""
Fraud Detection Agent for Financial Services.

Provides fraud detection and risk analysis:
- Transaction pattern analysis
- Anomaly detection
- Risk scoring
- Suspicious behavior flagging
- Alert generation

CRITICAL: All fraud alerts must be investigated within regulatory timelines.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import math

from variants.financial_services.config import (
    FinancialServicesConfig,
    get_financial_services_config,
)

logger = logging.getLogger(__name__)


class FraudRiskLevel(str, Enum):
    """Fraud risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of fraud alerts."""
    UNUSUAL_AMOUNT = "unusual_amount"
    UNUSUAL_FREQUENCY = "unusual_frequency"
    UNUSUAL_LOCATION = "unusual_location"
    UNUSUAL_TIME = "unusual_time"
    VELOCITY_CHECK = "velocity_check"
    PATTERN_MATCH = "pattern_match"
    BEHAVIORAL_ANOMALY = "behavioral_anomaly"
    ACCOUNT_TAKEOVER = "account_takeover"
    STRUCTURING = "structuring"
    MONEY_LAUNDERING = "money_laundering"


@dataclass
class FraudAlert:
    """
    Fraud alert for suspicious activity.

    All alerts require investigation per regulatory requirements.
    """
    alert_id: str
    alert_type: AlertType
    risk_level: FraudRiskLevel
    customer_id: str
    description: str
    detected_at: datetime = field(default_factory=datetime.utcnow)
    transaction_ids: List[str] = field(default_factory=list)
    risk_score: float = 0.0
    factors: List[str] = field(default_factory=list)
    investigation_status: str = "pending"  # pending, investigating, resolved, false_positive
    assigned_to: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None


@dataclass
class RiskAssessment:
    """Risk assessment result for a transaction or customer."""
    customer_id: str
    overall_risk_score: float  # 0.0 to 1.0
    risk_level: FraudRiskLevel
    factors: Dict[str, float]  # factor -> score
    recommendations: List[str]
    requires_review: bool
    review_priority: str  # low, medium, high, urgent


class FraudDetectionAgent:
    """
    Agent for fraud detection in financial services.

    Features:
    - Real-time transaction monitoring
    - Pattern analysis
    - Anomaly detection
    - Risk scoring
    - Alert generation
    - Behavioral analysis

    Detection Methods:
    - Velocity checks
    - Amount analysis
    - Geographic analysis
    - Time-based analysis
    - Behavioral profiling
    - Machine learning scoring (ready for ML integration)
    """

    # Risk thresholds
    RISK_THRESHOLDS = {
        FraudRiskLevel.LOW: 0.3,
        FraudRiskLevel.MEDIUM: 0.5,
        FraudRiskLevel.HIGH: 0.7,
        FraudRiskLevel.CRITICAL: 0.9,
    }

    # Velocity limits
    VELOCITY_LIMITS = {
        "transactions_per_hour": 10,
        "transactions_per_day": 50,
        "amount_per_hour": 5000,
        "amount_per_day": 25000,
    }

    def __init__(
        self,
        config: Optional[FinancialServicesConfig] = None
    ):
        """
        Initialize fraud detection agent.

        Args:
            config: Financial services configuration
        """
        self.config = config or get_financial_services_config()
        self._alerts: List[FraudAlert] = []
        self._transaction_history: Dict[str, List[Dict[str, Any]]] = {}
        self._customer_profiles: Dict[str, Dict[str, Any]] = {}

    def analyze_transaction(
        self,
        customer_id: str,
        transaction_id: str,
        amount: float,
        transaction_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RiskAssessment:
        """
        Analyze transaction for fraud risk.

        Args:
            customer_id: Customer identifier
            transaction_id: Transaction identifier
            amount: Transaction amount
            transaction_type: Type of transaction
            metadata: Additional transaction metadata

        Returns:
            RiskAssessment with risk score and factors
        """
        metadata = metadata or {}

        # Get or create customer profile
        profile = self._get_customer_profile(customer_id)

        # Calculate risk factors
        factors = {}

        # Amount risk factor
        factors["amount"] = self._calculate_amount_risk(
            amount, profile.get("avg_transaction_amount", 100)
        )

        # Velocity risk factor
        factors["velocity"] = self._calculate_velocity_risk(customer_id, amount)

        # Time risk factor
        factors["time"] = self._calculate_time_risk(metadata)

        # Location risk factor
        factors["location"] = self._calculate_location_risk(
            customer_id, metadata.get("location")
        )

        # Pattern risk factor
        factors["pattern"] = self._calculate_pattern_risk(
            customer_id, transaction_type, amount
        )

        # Calculate overall risk score
        weights = {
            "amount": 0.25,
            "velocity": 0.25,
            "time": 0.15,
            "location": 0.15,
            "pattern": 0.20,
        }

        overall_score = sum(
            factors[key] * weights[key] for key in factors
        )

        # Determine risk level
        risk_level = self._determine_risk_level(overall_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(factors, risk_level)

        # Record transaction
        self._record_transaction(customer_id, transaction_id, amount, transaction_type)

        assessment = RiskAssessment(
            customer_id=customer_id,
            overall_risk_score=round(overall_score, 3),
            risk_level=risk_level,
            factors=factors,
            recommendations=recommendations,
            requires_review=risk_level in [FraudRiskLevel.HIGH, FraudRiskLevel.CRITICAL],
            review_priority="urgent" if risk_level == FraudRiskLevel.CRITICAL else
                          "high" if risk_level == FraudRiskLevel.HIGH else "medium"
        )

        logger.info({
            "event": "fraud_risk_assessment",
            "customer_id": customer_id,
            "transaction_id": transaction_id,
            "risk_score": overall_score,
            "risk_level": risk_level.value,
        })

        # Generate alert if high risk
        if risk_level in [FraudRiskLevel.HIGH, FraudRiskLevel.CRITICAL]:
            self._create_alert(
                customer_id=customer_id,
                alert_type=AlertType.BEHAVIORAL_ANOMALY,
                risk_level=risk_level,
                description=f"High risk transaction detected (score: {overall_score:.2f})",
                transaction_ids=[transaction_id],
                risk_score=overall_score,
                factors=[f"{k}: {v:.2f}" for k, v in factors.items()]
            )

        return assessment

    def detect_anomalies(
        self,
        customer_id: str,
        lookback_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in customer transaction history.

        Args:
            customer_id: Customer to analyze
            lookback_days: Days to analyze

        Returns:
            List of detected anomalies
        """
        anomalies = []
        transactions = self._transaction_history.get(customer_id, [])

        if len(transactions) < 5:
            return anomalies  # Not enough data

        # Calculate baseline
        amounts = [t["amount"] for t in transactions]
        avg_amount = sum(amounts) / len(amounts)
        std_amount = math.sqrt(sum((a - avg_amount) ** 2 for a in amounts) / len(amounts))

        # Find outliers (more than 3 standard deviations)
        threshold = avg_amount + (3 * std_amount) if std_amount > 0 else avg_amount * 3

        for txn in transactions:
            if txn["amount"] > threshold:
                anomalies.append({
                    "type": "unusual_amount",
                    "transaction_id": txn["id"],
                    "amount": txn["amount"],
                    "expected_max": round(threshold, 2),
                    "deviation": round((txn["amount"] - avg_amount) / std_amount, 2) if std_amount > 0 else 0,
                })

        # Check for velocity anomalies
        recent_count = len([t for t in transactions if
            datetime.fromisoformat(t["timestamp"]) > datetime.utcnow() - timedelta(hours=24)])

        if recent_count > self.VELOCITY_LIMITS["transactions_per_day"]:
            anomalies.append({
                "type": "velocity_anomaly",
                "transactions_in_24h": recent_count,
                "limit": self.VELOCITY_LIMITS["transactions_per_day"],
            })

        return anomalies

    def get_active_alerts(
        self,
        risk_level: Optional[FraudRiskLevel] = None
    ) -> List[FraudAlert]:
        """
        Get active fraud alerts.

        Args:
            risk_level: Optional filter by risk level

        Returns:
            List of active alerts
        """
        alerts = [a for a in self._alerts if a.investigation_status == "pending"]

        if risk_level:
            alerts = [a for a in alerts if a.risk_level == risk_level]

        return sorted(alerts, key=lambda a: a.risk_score, reverse=True)

    def resolve_alert(
        self,
        alert_id: str,
        resolution: str,
        resolved_by: str,
        is_false_positive: bool = False
    ) -> Dict[str, Any]:
        """
        Resolve a fraud alert.

        Args:
            alert_id: Alert to resolve
            resolution: Resolution description
            resolved_by: User resolving the alert
            is_false_positive: Whether alert was false positive

        Returns:
            Dict with resolution result
        """
        alert = next((a for a in self._alerts if a.alert_id == alert_id), None)

        if not alert:
            return {"success": False, "message": "Alert not found"}

        alert.investigation_status = "false_positive" if is_false_positive else "resolved"
        alert.resolved_at = datetime.utcnow()
        alert.resolution_notes = resolution
        alert.assigned_to = resolved_by

        logger.info({
            "event": "fraud_alert_resolved",
            "alert_id": alert_id,
            "resolved_by": resolved_by,
            "is_false_positive": is_false_positive,
        })

        return {
            "success": True,
            "alert_id": alert_id,
            "status": alert.investigation_status,
            "resolved_at": alert.resolved_at.isoformat()
        }

    def get_customer_risk_summary(
        self,
        customer_id: str
    ) -> Dict[str, Any]:
        """
        Get risk summary for a customer.

        Args:
            customer_id: Customer to analyze

        Returns:
            Dict with risk summary
        """
        profile = self._get_customer_profile(customer_id)
        transactions = self._transaction_history.get(customer_id, [])
        alerts = [a for a in self._alerts if a.customer_id == customer_id]

        return {
            "customer_id": customer_id,
            "total_transactions": len(transactions),
            "total_alerts": len(alerts),
            "pending_alerts": len([a for a in alerts if a.investigation_status == "pending"]),
            "average_transaction_amount": profile.get("avg_transaction_amount", 0),
            "risk_flags": profile.get("risk_flags", []),
            "last_activity": transactions[-1]["timestamp"] if transactions else None,
        }

    def _get_customer_profile(self, customer_id: str) -> Dict[str, Any]:
        """Get or create customer profile."""
        if customer_id not in self._customer_profiles:
            self._customer_profiles[customer_id] = {
                "created_at": datetime.utcnow().isoformat(),
                "avg_transaction_amount": 100.0,
                "usual_locations": [],
                "usual_transaction_times": [],
                "risk_flags": [],
            }
        return self._customer_profiles[customer_id]

    def _calculate_amount_risk(
        self,
        amount: float,
        avg_amount: float
    ) -> float:
        """Calculate risk based on amount."""
        if avg_amount == 0:
            return 0.5

        ratio = amount / avg_amount

        if ratio <= 2:
            return 0.1
        elif ratio <= 5:
            return 0.3
        elif ratio <= 10:
            return 0.6
        else:
            return min(1.0, 0.6 + (ratio - 10) * 0.02)

    def _calculate_velocity_risk(
        self,
        customer_id: str,
        amount: float
    ) -> float:
        """Calculate risk based on transaction velocity."""
        transactions = self._transaction_history.get(customer_id, [])

        # Count recent transactions
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_hour = [t for t in transactions
                       if datetime.fromisoformat(t["timestamp"]) > one_hour_ago]

        if len(recent_hour) > self.VELOCITY_LIMITS["transactions_per_hour"]:
            return 0.9

        # Calculate amount velocity
        recent_amount = sum(t["amount"] for t in recent_hour) + amount
        if recent_amount > self.VELOCITY_LIMITS["amount_per_hour"]:
            return 0.8

        if len(recent_hour) > self.VELOCITY_LIMITS["transactions_per_hour"] / 2:
            return 0.5

        return 0.1

    def _calculate_time_risk(
        self,
        metadata: Dict[str, Any]
    ) -> float:
        """Calculate risk based on transaction time."""
        hour = datetime.utcnow().hour

        # Higher risk for off-hours (10 PM - 6 AM)
        if 22 <= hour or hour <= 6:
            return 0.6

        return 0.1

    def _calculate_location_risk(
        self,
        customer_id: str,
        location: Optional[str]
    ) -> float:
        """Calculate risk based on location."""
        if not location:
            return 0.2  # Unknown location

        profile = self._get_customer_profile(customer_id)
        usual_locations = profile.get("usual_locations", [])

        if location in usual_locations:
            return 0.1

        # New location
        return 0.5

    def _calculate_pattern_risk(
        self,
        customer_id: str,
        transaction_type: str,
        amount: float
    ) -> float:
        """Calculate risk based on transaction patterns."""
        # Check for structuring (amounts just under reporting threshold)
        # This check should happen regardless of history
        if 9000 <= amount <= 9999:
            return 0.7

        # Check for round amounts (often suspicious)
        if amount % 1000 == 0 and amount >= 1000:
            return 0.4

        transactions = self._transaction_history.get(customer_id, [])

        if len(transactions) < 3:
            return 0.1  # Not enough history

        return 0.1

    def _determine_risk_level(self, score: float) -> FraudRiskLevel:
        """Determine risk level from score."""
        if score >= self.RISK_THRESHOLDS[FraudRiskLevel.CRITICAL]:
            return FraudRiskLevel.CRITICAL
        elif score >= self.RISK_THRESHOLDS[FraudRiskLevel.HIGH]:
            return FraudRiskLevel.HIGH
        elif score >= self.RISK_THRESHOLDS[FraudRiskLevel.MEDIUM]:
            return FraudRiskLevel.MEDIUM
        else:
            return FraudRiskLevel.LOW

    def _generate_recommendations(
        self,
        factors: Dict[str, float],
        risk_level: FraudRiskLevel
    ) -> List[str]:
        """Generate recommendations based on risk factors."""
        recommendations = []

        if factors.get("amount", 0) > 0.6:
            recommendations.append("Verify large transaction with customer")

        if factors.get("velocity", 0) > 0.6:
            recommendations.append("Review recent transaction activity")

        if factors.get("time", 0) > 0.5:
            recommendations.append("Off-hours transaction - additional verification recommended")

        if factors.get("location", 0) > 0.4:
            recommendations.append("New location detected - verify customer identity")

        if risk_level == FraudRiskLevel.CRITICAL:
            recommendations.insert(0, "URGENT: Block transaction pending review")

        elif risk_level == FraudRiskLevel.HIGH:
            recommendations.insert(0, "Hold for supervisor review")

        return recommendations

    def _record_transaction(
        self,
        customer_id: str,
        transaction_id: str,
        amount: float,
        transaction_type: str
    ):
        """Record transaction for history tracking."""
        if customer_id not in self._transaction_history:
            self._transaction_history[customer_id] = []

        self._transaction_history[customer_id].append({
            "id": transaction_id,
            "amount": amount,
            "type": transaction_type,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Update profile average
        transactions = self._transaction_history[customer_id]
        avg = sum(t["amount"] for t in transactions) / len(transactions)
        self._customer_profiles[customer_id]["avg_transaction_amount"] = avg

    def _create_alert(
        self,
        customer_id: str,
        alert_type: AlertType,
        risk_level: FraudRiskLevel,
        description: str,
        transaction_ids: List[str],
        risk_score: float,
        factors: List[str]
    ) -> FraudAlert:
        """Create a fraud alert."""
        import uuid

        alert = FraudAlert(
            alert_id=f"ALR-{uuid.uuid4().hex[:8].upper()}",
            alert_type=alert_type,
            risk_level=risk_level,
            customer_id=customer_id,
            description=description,
            transaction_ids=transaction_ids,
            risk_score=risk_score,
            factors=factors,
        )

        self._alerts.append(alert)

        logger.warning({
            "event": "fraud_alert_created",
            "alert_id": alert.alert_id,
            "risk_level": risk_level.value,
            "customer_id": customer_id,
            "risk_score": risk_score,
        })

        return alert
