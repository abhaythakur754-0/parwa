"""Node 14: PREDICTION_ENGINE — Forecasts future issues or follow-up needs.

Proactive Agent node. Predicts potential future problems based on
customer history and current interaction patterns.
"""

from __future__ import annotations

from typing import Any

from parwa.state import ProactiveInsight


def _predict_issues_rule_based(intent: str, integration_data: dict, sentiment: str) -> list[dict]:
    """Predict future issues based on current interaction."""
    predictions = []

    # Frustrated customers are more likely to churn
    if sentiment in ("frustrated", "angry"):
        predictions.append(ProactiveInsight(
            type="prediction",
            description="High churn risk — customer may cancel subscription",
            confidence=0.70,
            suggested_action="Consider retention offer or priority support",
        ).model_dump())

    # Refund requests often lead to follow-up questions about timeline
    if intent == "refund_request":
        predictions.append(ProactiveInsight(
            type="prediction",
            description="Customer will likely ask about refund processing time",
            confidence=0.80,
            suggested_action="Proactively include 3-5 business day timeline",
        ).model_dump())

    # Multiple charges might indicate subscription confusion
    charges = integration_data.get("charges", [])
    if len(charges) > 1:
        predictions.append(ProactiveInsight(
            type="prediction",
            description="Duplicate charges may indicate subscription billing confusion",
            confidence=0.55,
            suggested_action="Clarify billing schedule in response",
        ).model_dump())

    if not predictions:
        predictions.append(ProactiveInsight(
            type="prediction",
            description="No significant future issues predicted",
            confidence=0.90,
            suggested_action="Standard follow-up sufficient",
        ).model_dump())

    return predictions


def prediction_engine(state: dict[str, Any]) -> dict[str, Any]:
    """Forecast future issues or follow-up needs.

    Reads: intent, integration_data, sentiment
    Writes: predictions
    """
    intent = state.get("intent", "general_inquiry")
    integration_data = state.get("integration_data", {})
    sentiment = state.get("sentiment", "neutral")

    predictions = _predict_issues_rule_based(intent, integration_data, sentiment)

    return {"predictions": predictions}
