"""
Jarvis Confidence Engine — Wave 5A: Confidence-Based Routing

Every PARWA decision gets a confidence score (0-100%). Jarvis uses this
to decide what to show the manager:

| Confidence | Action  | Jarvis Behavior                                    |
|-----------|---------|----------------------------------------------------|
| 95%+      | AUTO    | Log only. No notification.                         |
| 85-95%    | BATCH   | Group similar decisions. One-click approval.       |
| 70-84%    | ASK     | Show detailed analysis. Manager reviews individually|
| <70%      | ESCALATE| Beyond AI capability. Human judgment required.     |

Confidence = weighted average of 4 factors:
  - Pattern match (how closely does this match training data?) — 30%
  - Policy alignment (does answer align with uploaded policies?) — 25%
  - Risk signals (fraud indicators, VIP customer, high value?) — 25%
  - Historical accuracy (has this type been resolved correctly before?) — 20%

All data comes from jarvis_db — no LLM calls needed for routing decisions.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.confidence")

# ── Routing thresholds ────────────────────────────────────────

AUTO_THRESHOLD = 0.95
BATCH_THRESHOLD = 0.85
ASK_THRESHOLD = 0.70
# Below ASK_THRESHOLD → ESCALATE

# ── Factor weights ────────────────────────────────────────────

W_PATTERN = 0.30
W_POLICY = 0.25
W_RISK = 0.25
W_HISTORY = 0.20

# ── Routing action labels ─────────────────────────────────────

ACTION_AUTO = "auto"
ACTION_BATCH = "batch"
ACTION_ASK = "ask"
ACTION_ESCALATE = "escalate"


def classify_routing(confidence: float) -> str:
    """Map confidence score to routing action."""
    if confidence >= AUTO_THRESHOLD:
        return ACTION_AUTO
    elif confidence >= BATCH_THRESHOLD:
        return ACTION_BATCH
    elif confidence >= ASK_THRESHOLD:
        return ACTION_ASK
    return ACTION_ESCALATE


def compute_confidence_score(
    pattern_match: float = 1.0,
    policy_alignment: float = 1.0,
    risk_score: float = 0.0,  # 0 = no risk, 1 = maximum risk → INVERTED for confidence
    historical_accuracy: float = 1.0,
) -> Tuple[float, Dict[str, float]]:
    """Compute weighted confidence score.

    Args:
        pattern_match: How closely this matches known training data (0-1).
        policy_alignment: How well the answer aligns with policies (0-1).
        risk_score: Risk level (0=none, 1=max). Inverted internally.
        historical_accuracy: Historical accuracy for this ticket type (0-1).

    Returns:
        (confidence_0_to_1, {factor_name: weighted_contribution})
    """
    # Risk is inverted: high risk → low confidence
    risk_confidence = 1.0 - risk_score

    factors = {
        "pattern_match": pattern_match * W_PATTERN,
        "policy_alignment": policy_alignment * W_POLICY,
        "risk_score": risk_confidence * W_RISK,
        "historical_accuracy": historical_accuracy * W_HISTORY,
    }

    total = sum(factors.values())
    return round(total, 4), factors


async def score_ticket_confidence(
    tenant_id: str,
    ticket_id: str,
    ticket_type: str = "",
    query: str = "",
    required_action: str = "",
    is_vip: bool = False,
    value_usd: float = 0.0,
    policy_count: int = 0,
    technique_log: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Score a ticket's confidence using real DB data.

    This is the main entry point called by PARWA bridge / evaluate node.

    Computes each factor from DB where possible, falls back to defaults.

    Returns:
        {
            "confidence": float,
            "routing": str (auto/batch/ask/escalate),
            "factors": {name: value},
            "ticket_id": str,
            "reason": str,
        }
    """
    from app.core.jarvis_pipeline.jarvis_db import get_db

    db = get_db()

    # 1. Pattern match: based on training data coverage for this ticket type
    pattern_match = 1.0
    if ticket_type:
        try:
            training = await db.get_training_data(tenant_id, signal_type="approved", limit=100)
            type_matches = [t for t in training if t.get("ticket_type") == ticket_type]
            if type_matches:
                # More approved examples → higher pattern match
                avg_quality = sum(t.get("quality_score", 0) for t in type_matches) / len(type_matches)
                pattern_match = min(1.0, avg_quality)
            else:
                # No training data for this type → lower pattern match
                pattern_match = 0.6
        except Exception:
            pass

    # 2. Policy alignment: based on how many policies exist
    policy_alignment = min(1.0, policy_count / 10.0) if policy_count else 0.5

    # 3. Risk score: VIP, high value, financial actions
    risk_score = 0.0
    if is_vip:
        risk_score += 0.3
    if value_usd > 100:
        risk_score += 0.2
    if required_action in ("refund", "return", "account_change", "credit"):
        risk_score += 0.3
    risk_score = min(1.0, risk_score)

    # 4. Historical accuracy: from quality scores for this ticket type
    historical_accuracy = 0.8  # default
    if ticket_type:
        try:
            stats = await db.get_quality_stats(tenant_id)
            if stats["total_tickets"] > 0:
                historical_accuracy = stats["avg_quality"]
        except Exception:
            pass

    confidence, factors = compute_confidence_score(
        pattern_match=pattern_match,
        policy_alignment=policy_alignment,
        risk_score=risk_score,
        historical_accuracy=historical_accuracy,
    )

    routing = classify_routing(confidence)

    # Build reason string
    reason = _build_reason(routing, confidence, risk_score, is_vip, required_action)

    result = {
        "ticket_id": ticket_id,
        "confidence": confidence,
        "routing": routing,
        "factors": {k: round(v, 4) for k, v in factors.items()},
        "pattern_match": round(pattern_match, 4),
        "policy_alignment": round(policy_alignment, 4),
        "risk_level": round(risk_score, 4),
        "historical_accuracy": round(historical_accuracy, 4),
        "reason": reason,
    }

    logger.info("Confidence: ticket=%s score=%.4f route=%s risk=%.2f",
                ticket_id, confidence, routing, risk_score)

    return result


def _build_reason(routing: str, confidence: float, risk: float,
                  is_vip: bool, action: str) -> str:
    """Human-readable reason for routing decision."""
    parts = []
    if routing == ACTION_AUTO:
        parts.append("High confidence")
    elif routing == ACTION_BATCH:
        parts.append("Good confidence, suitable for batch")
    elif routing == ACTION_ASK:
        parts.append("Moderate confidence, individual review recommended")
    else:
        parts.append("Low confidence, human judgment required")

    if risk > 0.5:
        parts.append("elevated risk detected")
    if is_vip:
        parts.append("VIP customer")
    if action in ("refund", "return"):
        parts.append(f"{action} action")

    return ". ".join(parts) + "."


async def batch_score_tickets(
    tenant_id: str,
    tickets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Score multiple tickets for batch routing.

    Returns list of scored results, sorted by confidence (ascending)
    so lowest confidence (most needing attention) comes first.
    """
    results = []
    for t in tickets:
        scored = await score_ticket_confidence(
            tenant_id=tenant_id,
            ticket_id=t.get("ticket_id", ""),
            ticket_type=t.get("ticket_type", ""),
            query=t.get("query", ""),
            required_action=t.get("required_action", ""),
            is_vip=t.get("is_vip", False),
            value_usd=t.get("value_usd", 0),
        )
        results.append(scored)

    results.sort(key=lambda r: r["confidence"])
    return results