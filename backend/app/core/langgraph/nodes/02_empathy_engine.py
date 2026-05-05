"""
Empathy Engine Node — Group 2 (Second node in the pipeline)

Analyzes the PII-redacted message for sentiment, urgency, and
legal threat signals. Produces a comprehensive emotional profile
that drives downstream routing and response generation.

Tier Behavior:
  Mini: Basic keyword sentiment only (fast, cheap, no conversation history)
  Pro:  Keyword + conversation trend analysis (sentiment over last N messages)
  High: Keyword + trend + legal threat escalation (auto-escalate to legal team,
        track spiraling sentiment across sessions)

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


# ═══════════════════════════════════════════════════════════════
# Tier-specific upgrades: Trend analysis (Pro/High)
# ═══════════════════════════════════════════════════════════════


def _analyze_sentiment_trend(message: str, conversation_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Analyze sentiment trend across conversation history.

    Loads the last N messages in the conversation and determines
    whether the customer's sentiment is improving, stable, declining,
    or spiraling (rapidly worsening). Only runs for Pro and High tiers.

    Falls back to 'stable' if conversation history is unavailable.

    Args:
        message: The PII-redacted message to analyze.
        conversation_id: Conversation ID for history lookup.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Dict with 'sentiment_trend' and 'trend_confidence'.
    """
    try:
        from app.core.conversation_history import get_sentiment_trend  # type: ignore[import-untyped]

        result = get_sentiment_trend(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            current_message=message,
        )

        trend = result.get("sentiment_trend", "stable")
        trend_confidence = float(result.get("confidence", 0.0))

        # Validate trend value
        if trend not in ("improving", "stable", "declining", "spiraling"):
            trend = "stable"

        logger.info(
            "empathy_trend_analyzed",
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            sentiment_trend=trend,
            trend_confidence=trend_confidence,
        )

        return {
            "sentiment_trend": trend,
            "trend_confidence": round(max(0.0, min(1.0, trend_confidence)), 2),
        }

    except ImportError:
        logger.info(
            "empathy_trend_engine_unavailable",
            tenant_id=tenant_id,
            note="Conversation history module not installed; skipping trend analysis",
        )
    except Exception as trend_exc:
        logger.warning(
            "empathy_trend_analysis_error",
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            error=str(trend_exc),
        )

    # Fallback: no trend data available
    return {
        "sentiment_trend": "stable",
        "trend_confidence": 0.0,
    }


# ═══════════════════════════════════════════════════════════════
# Tier-specific upgrades: Legal threat escalation (High only)
# ═══════════════════════════════════════════════════════════════


def _escalate_legal_threat(
    message: str,
    tenant_id: str,
    legal_threat_detected: bool,
    sentiment_trend: str,
    urgency: str,
) -> Dict[str, Any]:
    """
    Escalate legal threats for High tier tenants.

    When a legal threat is detected or the customer is spiraling,
    this function triggers an automatic escalation to the legal
    team and flags the conversation for priority human review.
    Only runs for High tier.

    Falls back gracefully if the escalation module is unavailable.

    Args:
        message: The PII-redacted message.
        tenant_id: Tenant identifier (BC-001).
        legal_threat_detected: Whether legal keywords were found.
        sentiment_trend: The computed sentiment trend.
        urgency: The computed urgency level.

    Returns:
        Dict with 'urgency' (possibly upgraded), 'legal_escalated',
        and 'escalation_reason'.
    """
    escalation_reason = ""
    legal_escalated = False

    # Escalate if legal threat detected
    if legal_threat_detected:
        escalation_reason = "Legal threat keywords detected in customer message"
        legal_escalated = True

    # Escalate if customer is spiraling
    if sentiment_trend == "spiraling":
        if escalation_reason:
            escalation_reason += "; "
        escalation_reason += "Customer sentiment is spiraling (rapidly worsening)"
        legal_escalated = True

    if not legal_escalated:
        return {
            "urgency": urgency,
            "legal_escalated": False,
            "escalation_reason": "",
        }

    # Attempt to notify the escalation system
    try:
        from app.core.legal_escalation import trigger_legal_escalation  # type: ignore[import-untyped]

        trigger_legal_escalation(
            tenant_id=tenant_id,
            reason=escalation_reason,
            message_preview=message[:500],  # Truncate for safety
        )

        logger.warning(
            "empathy_legal_threat_escalated",
            tenant_id=tenant_id,
            escalation_reason=escalation_reason,
            original_urgency=urgency,
        )

    except ImportError:
        logger.info(
            "empathy_legal_escalation_unavailable",
            tenant_id=tenant_id,
            note="Legal escalation module not installed; flagging urgency only",
        )
    except Exception as esc_exc:
        logger.warning(
            "empathy_legal_escalation_error",
            tenant_id=tenant_id,
            error=str(esc_exc),
        )

    # Upgrade urgency to critical if legal threat
    upgraded_urgency = urgency
    if legal_threat_detected and urgency != "critical":
        upgraded_urgency = "high"
    if sentiment_trend == "spiraling" and urgency in ("low", "medium"):
        upgraded_urgency = "high"

    return {
        "urgency": upgraded_urgency,
        "legal_escalated": legal_escalated,
        "escalation_reason": escalation_reason,
    }


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def empathy_engine_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Empathy Engine Node — LangGraph agent node.

    Analyzes the PII-redacted message for sentiment, urgency,
    and legal threat signals. Behavior varies by variant_tier:

      Mini: Basic keyword sentiment only (fast, cheap)
      Pro:  Keyword + conversation trend analysis
      High: Keyword + trend + legal threat auto-escalation

    Uses the production sentiment engine when available,
    falling back to keyword-based analysis.

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
        # ── Step 1: Base sentiment analysis (all tiers) ───────────
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
                variant_tier=variant_tier,
                sentiment_score=sentiment_score,
                sentiment_intensity=sentiment_intensity,
                urgency=urgency,
                legal_threat_detected=legal_threat_detected,
                sentiment_trend=sentiment_trend,
            )

        except ImportError:
            logger.warning(
                "sentiment_engine_unavailable_using_fallback",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
            )
            # Use keyword-based fallback
            fallback = _fallback_sentiment_analysis(message)
            sentiment_score = fallback["sentiment_score"]
            sentiment_intensity = fallback["sentiment_intensity"]
            legal_threat_detected = fallback["legal_threat_detected"]
            urgency = fallback["urgency"]
            sentiment_trend = fallback["sentiment_trend"]  # always 'stable' in fallback

        except Exception as engine_exc:
            logger.warning(
                "sentiment_engine_error_using_fallback",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
                error=str(engine_exc),
            )
            fallback = _fallback_sentiment_analysis(message)
            sentiment_score = fallback["sentiment_score"]
            sentiment_intensity = fallback["sentiment_intensity"]
            legal_threat_detected = fallback["legal_threat_detected"]
            urgency = fallback["urgency"]
            sentiment_trend = fallback["sentiment_trend"]

        # ── Step 2: Pro/High — Conversation trend analysis ────────
        if variant_tier in ("pro", "high"):
            trend_result = _analyze_sentiment_trend(
                message=message,
                conversation_id=conversation_id,
                tenant_id=tenant_id,
            )
            # Only override trend if the engine returned useful data
            if trend_result["trend_confidence"] > 0.0:
                sentiment_trend = trend_result["sentiment_trend"]

        # ── Step 3: High — Legal threat escalation ────────────────
        escalation_result = None
        if variant_tier == "high":
            escalation_result = _escalate_legal_threat(
                message=message,
                tenant_id=tenant_id,
                legal_threat_detected=legal_threat_detected,
                sentiment_trend=sentiment_trend,
                urgency=urgency,
            )
            if escalation_result.get("urgency") != urgency:
                urgency = escalation_result["urgency"]

        # ── Build final result ────────────────────────────────────
        result = {
            "sentiment_score": sentiment_score,
            "sentiment_intensity": sentiment_intensity,
            "legal_threat_detected": legal_threat_detected,
            "urgency": urgency,
            "sentiment_trend": sentiment_trend,
        }

        logger.info(
            "empathy_engine_node_success",
            tenant_id=tenant_id,
            variant_tier=variant_tier,
            sentiment_score=sentiment_score,
            urgency=urgency,
            sentiment_trend=sentiment_trend,
            legal_threat_detected=legal_threat_detected,
            legal_escalated=escalation_result.get("legal_escalated", False) if escalation_result else False,
        )

        return result

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
