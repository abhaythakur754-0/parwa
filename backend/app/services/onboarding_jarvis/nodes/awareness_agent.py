"""
PARWA Onboarding Awareness Agent Node

The Awareness Agent enriches the onboarding context without directly
responding to the user. It detects stage transitions, identifies new
concerns, tracks topics, and updates the onboarding state.

This agent runs AFTER the specialist agent has produced a response,
updating context for future turns. It does NOT produce a user-facing
response — it only updates the awareness namespace.

BC-008: Never crash — all detection wrapped in try/except.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.logger import get_logger

logger = get_logger("onboarding_awareness_agent")


def awareness_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich onboarding context by detecting signals from the conversation.

    This node runs after the specialist agent to:
      1. Detect new concerns from the user message
      2. Track demo topics discussed
      3. Detect intent and sentiment shifts
      4. Determine if stage transition is needed
      5. Update awareness context for future turns

    Args:
        state: Current OnboardingJarvisState dict.

    Returns:
        Dict with updated AWARENESS group fields.
    """
    start_time = time.monotonic()

    try:
        user_message = state.get("user_message", "").lower()
        current_stage = state.get("detected_stage", "welcome")

        # Detect new concerns
        new_concerns = _detect_concerns(user_message)

        # Track topics
        new_topics = _detect_topics(user_message, state.get("industry", ""))

        # Detect intent
        intent_detected = _detect_intent(user_message)

        # Detect sentiment
        sentiment = _detect_sentiment(user_message)

        # Determine if stage should transition
        stage_transition = _detect_stage_transition(state, intent_detected)

        # Build awareness changes
        awareness_changes: Dict[str, Any] = {}
        if new_concerns:
            awareness_changes["new_concerns"] = new_concerns
        if new_topics:
            awareness_changes["new_topics"] = new_topics
        if intent_detected:
            awareness_changes["intent_detected"] = intent_detected
        if sentiment != "neutral":
            awareness_changes["sentiment"] = sentiment
        if stage_transition:
            awareness_changes["stage_transition"] = stage_transition

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "awareness_updated": bool(awareness_changes),
            "awareness_changes": awareness_changes,
            "stage_transition": stage_transition,
            "new_concerns": new_concerns,
            "new_topics": new_topics,
            "intent_detected": intent_detected,
            "sentiment": sentiment,
            "node_outputs": {"awareness_agent": awareness_changes},
            "audit_trail": [{
                "step": "awareness_agent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "concerns_found": len(new_concerns),
                "topics_found": len(new_topics),
                "intent": intent_detected,
                "sentiment": sentiment,
                "stage_transition": stage_transition,
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "awareness_agent: session=%s, concerns=%d, topics=%d, "
            "intent=%s, sentiment=%s, transition=%s, ms=%.1f",
            state.get("session_id", ""),
            len(new_concerns),
            len(new_topics),
            intent_detected,
            sentiment,
            stage_transition,
            elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("awareness_agent_error: ms=%.1f", elapsed_ms)
        return {
            "awareness_updated": False,
            "awareness_changes": {},
            "stage_transition": None,
            "new_concerns": [],
            "new_topics": [],
            "intent_detected": "unknown",
            "sentiment": "neutral",
            "errors": [f"awareness_agent: {str(e)[:200]}"],
        }


# ── Concern Detection ──────────────────────────────────────────────

CONCERN_PATTERNS = {
    "cost": ["expensive", "too much", "costly", "afford", "budget", "price"],
    "complexity": ["complex", "too hard", "complicated", "difficult", "confusing"],
    "competition": ["zendesk", "intercom", "freshdesk", "already use", "competitor"],
    "security": ["security", "data safe", "privacy", "trust", "gdpr", "encrypted"],
    "setup": ["setup", "how long", "configure", "implement", "deploy"],
    "quality": ["wrong answer", "mistake", "hallucinate", "accuracy", "make up"],
    "control": ["control", "customize", "flexible", "rigid", "locked in"],
    "timing": ["not ready", "think about", "later", "not now", "maybe"],
}


def _detect_concerns(message: str) -> List[str]:
    """Detect concerns from user message."""
    concerns = []
    try:
        for concern_type, keywords in CONCERN_PATTERNS.items():
            if any(kw in message for kw in keywords):
                concerns.append(concern_type)
    except Exception:
        logger.debug("concern_detection_failed", exc_info=True)
    return concerns


# ── Topic Detection ────────────────────────────────────────────────

TOPIC_PATTERNS = {
    "pricing": ["price", "cost", "plan", "tier", "subscription", "billing"],
    "demo": ["demo", "show me", "try it", "test", "see it work"],
    "features": ["feature", "capability", "what can", "does it", "integrate"],
    "returns": ["return", "refund", "money back", "send back"],
    "tracking": ["track", "where is", "order status", "delivery"],
    "billing_inquiry": ["charge", "invoice", "payment", "bill"],
    "technical": ["bug", "error", "api", "technical", "not working"],
    "knowledge_base": ["knowledge", "upload", "document", "learn", "train"],
    "voice": ["call", "phone", "voice", "talk", "speak"],
    "industry": ["ecommerce", "saas", "logistics", "retail", "my business"],
}


def _detect_topics(message: str, industry: str) -> List[str]:
    """Detect topics discussed in the user message."""
    topics = []
    try:
        for topic, keywords in TOPIC_PATTERNS.items():
            if any(kw in message for kw in keywords):
                topics.append(topic)
        if industry and industry in message:
            if "industry" not in topics:
                topics.append("industry")
    except Exception:
        logger.debug("topic_detection_failed", exc_info=True)
    return topics


# ── Intent Detection ───────────────────────────────────────────────

def _detect_intent(message: str) -> str:
    """Detect user intent from message."""
    import re
    try:
        if re.match(r'^(hi|hello|hey|namaste)\b', message):
            return "greeting"
        if any(kw in message for kw in ["show me", "demo", "demonstrate"]):
            return "demo_request"
        if any(kw in message for kw in ["call", "phone", "voice"]):
            return "call_request"
        if any(kw in message for kw in ["price", "cost", "how much", "plan"]):
            return "pricing_inquiry"
        if any(kw in message for kw in ["buy", "subscribe", "sign up", "purchase"]):
            return "purchase_intent"
        if any(kw in message for kw in ["upload", "document", "knowledge base"]):
            return "document_upload"
        if any(kw in message for kw in ["expensive", "not sure", "worried", "security"]):
            return "objection"
        if any(kw in message for kw in ["how does", "what is", "can it", "explain"]):
            return "question"
        return "other"
    except Exception:
        return "unknown"


# ── Sentiment Detection ───────────────────────────────────────────

def _detect_sentiment(message: str) -> str:
    """Detect user sentiment from message."""
    try:
        positive_kw = ["great", "awesome", "love", "perfect", "excellent", "impressive", "amazing"]
        excited_kw = ["wow", "cool", "excited", "can't wait", "let's do it", "ready"]
        negative_kw = ["bad", "terrible", "horrible", "waste", "stupid", "broken"]
        frustrated_kw = ["frustrated", "annoyed", "angry", "unacceptable", "fed up"]
        skeptical_kw = ["not convinced", "doubt", "skeptical", "really", "sure about"]

        if any(kw in message for kw in excited_kw):
            return "excited"
        if any(kw in message for kw in positive_kw):
            return "positive"
        if any(kw in message for kw in frustrated_kw):
            return "frustrated"
        if any(kw in message for kw in negative_kw):
            return "negative"
        if any(kw in message for kw in skeptical_kw):
            return "skeptical"
        return "neutral"
    except Exception:
        return "neutral"


# ── Stage Transition Detection ─────────────────────────────────────

STAGE_ORDER = [
    "welcome", "discovery", "demo", "pricing",
    "bill_review", "verification", "payment", "handoff",
]

INTENT_TO_STAGE = {
    "purchase_intent": "pricing",
    "call_request": "demo",
    "demo_request": "demo",
    "document_upload": "demo",
}


def _detect_stage_transition(state: Dict[str, Any], intent: str) -> str | None:
    """Determine if the conversation stage should transition.

    Returns the new stage name if a transition should happen, or None.
    """
    try:
        current_stage = state.get("detected_stage", "welcome")
        payment_status = state.get("payment_status", "none")
        email_verified = state.get("email_verified", False)
        selected_variants = state.get("selected_variants", [])

        # Hard transitions based on state
        if payment_status == "completed":
            return "handoff"
        if payment_status == "pending":
            return "payment"
        if email_verified and selected_variants:
            return "payment"

        # Intent-based transitions
        target_stage = INTENT_TO_STAGE.get(intent)
        if target_stage:
            current_idx = STAGE_ORDER.index(current_stage) if current_stage in STAGE_ORDER else 0
            target_idx = STAGE_ORDER.index(target_stage) if target_stage in STAGE_ORDER else 0
            # Only allow forward transitions
            if target_idx > current_idx:
                return target_stage

        # State-based transitions
        if current_stage == "welcome" and state.get("industry"):
            return "discovery"
        if current_stage == "discovery" and selected_variants:
            return "pricing"

        return None
    except Exception:
        logger.debug("stage_transition_detection_failed", exc_info=True)
        return None
