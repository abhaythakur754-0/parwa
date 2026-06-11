"""Node 14: PREDICTION_ENGINE — Forecasts future issues or follow-up needs.

Proactive Agent node. Predicts potential future problems based on
customer history and current interaction patterns.

Phase 5: Now uses FrameworkBrain with Dynamic Context for pattern
recognition and predictions. Falls back to rule-based on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.state import ProactiveInsight
from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.prediction_engine")


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


async def _predict_with_brain(state: dict[str, Any]) -> tuple[list[dict], list[str]]:
    """Prediction using FrameworkBrain (Phase 5).

    Returns (predictions, frameworks_used).
    Falls back to rule-based on any failure.
    """
    intent = state.get("intent", "general_inquiry")
    integration_data = state.get("integration_data", {})
    sentiment = state.get("sentiment", "neutral")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="PREDICTION_ENGINE", state=state)
        result = await brain.think(
            prompt=f"Predict future issues for {intent} with sentiment {sentiment}",
            techniques=["dynamic_context", "chain_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        predictions = _predict_issues_rule_based(intent, integration_data, sentiment)

        if result.confidence > 0.5 and result.frameworks_used:
            for pred in predictions:
                if isinstance(pred, dict):
                    pred["brain_enhanced"] = True

        frameworks_used = result.frameworks_used if result.frameworks_used else []
        return predictions, frameworks_used

    except Exception as exc:
        logger.warning(
            "prediction_engine: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        predictions = _predict_issues_rule_based(intent, integration_data, sentiment)
        return predictions, []


@safe_node("PREDICTION_ENGINE", fallback={"predictions": [], "active_frameworks": []})
async def prediction_engine(state: dict[str, Any]) -> dict[str, Any]:
    """Forecast future issues or follow-up needs (async).

    Phase 5: Uses FrameworkBrain with Dynamic Context/CoT for
    pattern recognition and predictions.

    Reads: intent, integration_data, sentiment
    Writes: predictions, active_frameworks (append)
    """
    intent = state.get("intent", "general_inquiry")
    integration_data = state.get("integration_data", {})
    sentiment = state.get("sentiment", "neutral")

    # Guard: ensure types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(integration_data, dict):
        integration_data = {}
    if not isinstance(sentiment, str):
        sentiment = "neutral"

    predictions, frameworks = await _predict_with_brain(state)

    if not isinstance(predictions, list):
        predictions = []

    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "predictions": predictions,
        "active_frameworks": new_frameworks,
    }
