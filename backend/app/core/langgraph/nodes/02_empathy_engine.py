"""
Empathy Engine Node — Group 2 (Second node in the pipeline)

Analyzes the PII-redacted message for sentiment, urgency, and
legal threat signals. Produces a comprehensive emotional profile
that drives downstream routing and response generation.

State Contract:
  Reads:  pii_redacted_message, tenant_id, variant_tier, conversation_id
  Writes: sentiment_score, sentiment_intensity, legal_threat_detected,
          urgency, sentiment_trend, errors

BC-008: Never crash — returns neutral defaults on any failure.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from app.core.langgraph.config import get_variant_config
from app.logger import get_logger

logger = get_logger("node_empathy_engine")


# ──────────────────────────────────────────────────────────────
# Default fallback values (neutral / low-risk)
# ──────────────────────────────────────────────────────────────

_DEFAULT_STATE: Dict[str, Any] = {
    "sentiment_score": 0.5,
    "sentiment_intensity": "low",
    "legal_threat_detected": False,
    "urgency": "low",
    "sentiment_trend": "stable",
}


# ──────────────────────────────────────────────────────────────
# Fallback keyword-based sentiment analysis
# Used when sentiment_engine module is unavailable.
# ──────────────────────────────────────────────────────────────

_NEGATIVE_KEYWORDS: List[str] = [
    "angry", "furious", "terrible", "horrible", "worst", "hate",
    "disappointed", "frustrated", "upset", "annoyed", "unacceptable",
    "pathetic", "disgusted", "outraged", "livid", "appalled",
]

_POSITIVE_KEYWORDS: List[str] = [
    "great", "excellent", "wonderful", "amazing", "thank", "thanks",
    "love", "happy", "satisfied", "perfect", "awesome", "good",
    "appreciate", "pleased", "delighted",
]

_URGENCY_KEYWORDS: Dict[str, List[str]] = {
    "critical": ["urgent", "emergency", "immediately", "asap", "right now", "critical"],
    "high": ["soon", "quickly", "important", "need help", "can't wait"],
    "medium": ["when possible", "at your convenience", "sometime"],
}

_LEGAL_THREAT_KEYWORDS: List[str] = [
    "lawyer", "attorney", "sue", "lawsuit", "legal action", "court",
    "regulatory", "compliance violation", "fcc", "ftc", "bbb",
    "consumer protection", "class action", "breach of contract",
]


def _fallback_sentiment_analysis(message: str) -> Dict[str, Any]:
    """
    Keyword-based sentiment analysis as a fallback when the
    sentiment_engine module is unavailable.

    Produces a rough sentiment score, intensity, urgency level,
    and legal threat flag based on keyword matching.

    Args:
        message: The PII-redacted message to analyze.

    Returns:
        Dict with empathy engine output fields.
    """
    message_lower = message.lower()

    # ── Sentiment score ────────────────────────────────────────
    neg_count = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in message_lower)
    pos_count = sum(1 for kw in _POSITIVE_KEYWORDS if kw in message_lower)

    total = neg_count + pos_count
    if total == 0:
        sentiment_score = 0.5  # neutral
    else:
        # Map to 0.0–1.0 range: all negative = 0.1, all positive = 0.9
        sentiment_score = 0.1 + (0.8 * (pos_count / total))
    sentiment_score = round(max(0.0, min(1.0, sentiment_score)), 2)

    # ── Sentiment intensity ────────────────────────────────────
    if total >= 4:
        sentiment_intensity = "extreme"
    elif total >= 3:
        sentiment_intensity = "high"
    elif total >= 2:
        sentiment_intensity = "medium"
    else:
        sentiment_intensity = "low"

    # ── Urgency ────────────────────────────────────────────────
    urgency = "low"
    for level in ("critical", "high", "medium"):
        if any(kw in message_lower for kw in _URGENCY_KEYWORDS[level]):
            urgency = level
            break

    # ── Legal threat detection ─────────────────────────────────
    legal_threat_detected = any(kw in message_lower for kw in _LEGAL_THREAT_KEYWORDS)

    # ── Sentiment trend (always 'stable' in fallback — needs ───
    #    conversation history for real trend analysis) ──────────
    sentiment_trend = "stable"

    # Escalate urgency if legal threat detected
    if legal_threat_detected and urgency in ("low", "medium"):
        urgency = "high"

    return {
        "sentiment_score": sentiment_score,
        "sentiment_intensity": sentiment_intensity,
        "legal_threat_detected": legal_threat_detected,
        "urgency": urgency,
        "sentiment_trend": sentiment_trend,
    }


def empathy_engine_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Empathy Engine Node — LangGraph agent node.

    Analyzes the PII-redacted message for sentiment, urgency,
    and legal threat signals using the production sentiment engine
    when available, falling back to keyword-based analysis.

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with sentiment_score, sentiment_intensity,
        legal_threat_detected, urgency, sentiment_trend, and optionally
        errors.
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")
    conversation_id = state.get("conversation_id", "")
    message = state.get("pii_redacted_message", "") or state.get("message", "")

    logger.info(
        "empathy_engine_node_start",
        tenant_id=tenant_id,
        variant_tier=variant_tier,
        conversation_id=conversation_id,
        message_length=len(message),
    )

    try:
        # ── Attempt production sentiment engine ─────────────────
        try:
            from app.core.sentiment_engine import analyze_sentiment  # type: ignore[import-untyped]

            result = analyze_sentiment(
                message=message,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
            )

            sentiment_score = float(result.get("sentiment_score", 0.5))
            sentiment_intensity = str(result.get("sentiment_intensity", "low"))
            legal_threat_detected = bool(result.get("legal_threat_detected", False))
            urgency = str(result.get("urgency", "low"))
            sentiment_trend = str(result.get("sentiment_trend", "stable"))

            # Clamp sentiment_score to valid range
            sentiment_score = round(max(0.0, min(1.0, sentiment_score)), 2)

            # Validate enum-like fields
            if sentiment_intensity not in ("low", "medium", "high", "extreme"):
                sentiment_intensity = "low"
            if urgency not in ("low", "medium", "high", "critical"):
                urgency = "low"
            if sentiment_trend not in ("improving", "stable", "declining", "spiraling"):
                sentiment_trend = "stable"

            logger.info(
                "sentiment_engine_success",
                tenant_id=tenant_id,
                sentiment_score=sentiment_score,
                sentiment_intensity=sentiment_intensity,
                urgency=urgency,
                legal_threat_detected=legal_threat_detected,
                sentiment_trend=sentiment_trend,
            )

            return {
                "sentiment_score": sentiment_score,
                "sentiment_intensity": sentiment_intensity,
                "legal_threat_detected": legal_threat_detected,
                "urgency": urgency,
                "sentiment_trend": sentiment_trend,
            }

        except ImportError:
            logger.warning(
                "sentiment_engine_unavailable_using_fallback",
                tenant_id=tenant_id,
            )
        except Exception as engine_exc:
            logger.warning(
                "sentiment_engine_error_using_fallback",
                tenant_id=tenant_id,
                error=str(engine_exc),
            )

        # ── Fallback: keyword-based analysis ────────────────────
        fallback_result = _fallback_sentiment_analysis(message)

        logger.info(
            "empathy_engine_fallback_success",
            tenant_id=tenant_id,
            sentiment_score=fallback_result["sentiment_score"],
            urgency=fallback_result["urgency"],
            legal_threat_detected=fallback_result["legal_threat_detected"],
        )

        return fallback_result

    except Exception as exc:
        # ── Total failure: return neutral defaults ──────────────
        logger.error(
            "empathy_engine_node_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )
        return {
            **_DEFAULT_STATE,
            "errors": [f"Empathy engine failed: {exc}"],
        }
