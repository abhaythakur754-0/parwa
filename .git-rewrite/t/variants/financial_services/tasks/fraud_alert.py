"""
Fraud Alert Task for Financial Services.

Generates and manages fraud alerts:
- Alert generation
- Priority classification
- Automatic escalation
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
import logging
import uuid

from variants.financial_services.config import get_financial_services_config
from variants.financial_services.agents.fraud_detection_agent import (
    FraudDetectionAgent,
    FraudRiskLevel,
)

logger = logging.getLogger(__name__)


@dataclass
class FraudAlertResult:
    """Result of fraud alert creation."""
    success: bool
    alert_id: str
    risk_level: str
    priority: str
    assigned_to: str
    audit_id: str
    escalated: bool


def create_fraud_alert(
    customer_id: str,
    alert_type: str,
    risk_factors: List[str],
    details: Dict[str, Any],
    actor: str = "fraud_detection_agent"
) -> FraudAlertResult:
    """
    Create fraud alert for review.

    Args:
        customer_id: Customer identifier
        alert_type: Type of fraud alert
        risk_factors: List of risk factors detected
        details: Alert details
        actor: Agent creating alert

    Returns:
        FraudAlertResult with alert status
    """
    config = get_financial_services_config()
    fraud_agent = FraudDetectionAgent(config)
    alert_id = f"ALR-{uuid.uuid4().hex[:8].upper()}"
    audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"

    # Assess risk level
    risk_score = _calculate_risk_score(risk_factors)
    risk_level = _determine_risk_level(risk_score)

    # Determine priority and assignment
    priority = "urgent" if risk_level in ["high", "critical"] else "normal"
    assigned_to = "fraud_investigation_team" if risk_level in ["high", "critical"] else "review_queue"

    # Escalate if critical
    escalated = risk_level == "critical"

    logger.warning({
        "event": "fraud_alert_created",
        "alert_id": alert_id,
        "customer_id": customer_id,
        "alert_type": alert_type,
        "risk_level": risk_level,
        "escalated": escalated,
        "audit_id": audit_id,
    })

    return FraudAlertResult(
        success=True,
        alert_id=alert_id,
        risk_level=risk_level,
        priority=priority,
        assigned_to=assigned_to,
        audit_id=audit_id,
        escalated=escalated
    )


def _calculate_risk_score(factors: List[str]) -> float:
    """Calculate risk score from factors."""
    weights = {
        "velocity": 0.3,
        "structuring": 0.4,
        "unusual_location": 0.2,
        "unusual_amount": 0.25,
        "off_hours": 0.15,
    }
    return sum(weights.get(f, 0.1) for f in factors)


def _determine_risk_level(score: float) -> str:
    """Determine risk level from score."""
    if score >= 0.7:
        return "critical"
    elif score >= 0.5:
        return "high"
    elif score >= 0.3:
        return "medium"
    return "low"
