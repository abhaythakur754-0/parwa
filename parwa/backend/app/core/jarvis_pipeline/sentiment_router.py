"""
Jarvis Sentiment Router — Wave 5C: Empathy Engine

Route customers based on emotional state, not just logic:
  - Angry/Frustrated (sentiment < 0.3): Route directly to human. Alert manager.
  - Happy/Neutral (sentiment > 0.6): Handle by AI autonomously.
  - Mixed/Uncertain (0.3-0.6): Handle by AI but flag for review.

Sentiment analysis uses a lightweight keyword-based approach (no LLM calls).
The sentiment score flows through PARWA state. Jarvis reads it and applies rules.

Zero new dependencies.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("jarvis.sentiment")

# ── Thresholds ─────────────────────────────────────────────────

ANGRY_THRESHOLD = 0.3
HAPPY_THRESHOLD = 0.6

# ── Routing labels ─────────────────────────────────────────────

ROUTE_HUMAN = "human"
ROUTE_AI_FLAGGED = "ai_flagged"
ROUTE_AI_AUTO = "ai_auto"

# ── Sentiment keyword lists ────────────────────────────────────

ANGRY_WORDS = {
    "angry", "furious", "terrible", "horrible", "worst", "unacceptable",
    "ridiculous", "disgusting", "outrageous", "appalling", "pathetic",
    "useless", "garbage", "scam", "cheat", "liar", "fraud", "sue",
    "lawsuit", "complaint", " BBB ", " attorney ", "unbelievable",
    "disappointed", "frustrated", "infuriating", "mad", "pissed",
    "refund", "money back", "cancel subscription", "never again",
    "worst experience", "terrible service", "ridiculous wait",
    "your company", "report you", "regulator", "consumer protection",
    "speak to manager", "supervisor", "demand", "insist",
}

HAPPY_WORDS = {
    "thanks", "thank you", "great", "awesome", "love", "amazing",
    "perfect", "excellent", "wonderful", "fantastic", "helpful",
    "appreciate", "brilliant", "superb", "outstanding", "impressive",
    "fast", "quick", "easy", "simple", "smooth", "happy", "pleased",
    "satisfied", "delighted", "recommend", "best", "good job",
    "well done", "keep it up", "cheers", "no problem", "all good",
}

INTENSIFIERS = {
    "very": 1.3, "really": 1.3, "extremely": 1.5, "absolutely": 1.4,
    "completely": 1.4, "totally": 1.3, "utterly": 1.5, "incredibly": 1.4,
    "so": 1.2, "such": 1.2, "never": 1.3, "always": 1.2,
}

NEGATORS = {"not", "no", "never", "don't", "dont", "doesn't", "doesnt",
            "didn't", "didnt", "won't", "wont", "can't", "cant",
            "isn't", "isnt", "aren't", "arent", "wasn't", "wasnt",
            "shouldn't", "shouldnt", "wouldn't", "wouldnt", "couldn't", "couldnt"}


def compute_sentiment(text: str) -> Dict[str, Any]:
    """Compute a sentiment score from text using keyword matching.

    Returns:
        {
            "score": float (0-1, 0=angry, 1=happy),
            "label": str (angry/mixed/happy),
            "route": str (human/ai_flagged/ai_auto),
            "angry_keywords_found": list[str],
            "happy_keywords_found": list[str],
            "has_intensifier": bool,
            "has_negation": bool,
        }

    No LLM calls. Pure keyword matching with intensifier/negation handling.
    """
    if not text:
        return {
            "score": 0.5,
            "label": "mixed",
            "route": ROUTE_AI_FLAGGED,
            "angry_keywords_found": [],
            "happy_keywords_found": [],
            "has_intensifier": False,
            "has_negation": False,
        }

    text_lower = text.lower()
    words = re.findall(r"\b\w+\b", text_lower)

    # Check for negation (affects the next 3 words)
    negated_indices = set()
    for i, w in enumerate(words):
        if w in NEGATORS:
            for j in range(i, min(i + 4, len(words))):
                negated_indices.add(j)

    # Find angry/happy keywords
    angry_found = []
    happy_found = []
    has_intensifier = False

    for i, word in enumerate(words):
        # Check intensifiers
        if word in INTENSIFIERS:
            has_intensifier = True

        # Skip negated words (negation reverses sentiment)
        if i in negated_indices:
            continue

        if word in ANGRY_WORDS or any(word in kw for kw in ANGRY_WORDS if " " in kw):
            angry_found.append(word)
        if word in HAPPY_WORDS or any(word in kw for kw in HAPPY_WORDS if " " in kw):
            happy_found.append(word)

    # Also check multi-word angry/happy phrases
    for kw in ANGRY_WORDS:
        if " " in kw and kw in text_lower:
            for w in kw.split():
                if w not in angry_found:
                    angry_found.append(w)
    for kw in HAPPY_WORDS:
        if " " in kw and kw in text_lower:
            for w in kw.split():
                if w not in happy_found:
                    happy_found.append(w)

    # Compute raw sentiment
    angry_count = len(set(angry_found))
    happy_count = len(set(happy_found))
    total_signal = angry_count + happy_count

    if total_signal == 0:
        # No sentiment signal — neutral
        score = 0.55  # slightly positive neutral
    else:
        # Raw: ratio of happy to total signals
        raw_score = happy_count / total_signal  # 0 = all angry, 1 = all happy

        # Apply intensifier (amplify sentiment)
        if has_intensifier:
            if raw_score < 0.5:
                raw_score *= 0.7  # amplify anger
            else:
                raw_score *= 1.1  # amplify happiness
                raw_score = min(1.0, raw_score)

        score = raw_score

    score = round(max(0.0, min(1.0, score)), 4)

    # Classify
    if score < ANGRY_THRESHOLD:
        label = "angry"
        route = ROUTE_HUMAN
    elif score >= HAPPY_THRESHOLD:
        label = "happy"
        route = ROUTE_AI_AUTO
    else:
        label = "mixed"
        route = ROUTE_AI_FLAGGED

    return {
        "score": score,
        "label": label,
        "route": route,
        "angry_keywords_found": list(set(angry_found))[:10],
        "happy_keywords_found": list(set(happy_found))[:10],
        "has_intensifier": has_intensifier,
        "has_negation": bool(negated_indices),
    }


async def route_by_sentiment(
    tenant_id: str,
    ticket_id: str,
    query: str,
    customer_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Full sentiment routing decision.

    Combines text sentiment with customer context (VIP, repeat contact).

    Returns:
        {
            "ticket_id": str,
            "sentiment": {...},  # full sentiment analysis
            "route": str,
            "escalate": bool,
            "reason": str,
        }
    """
    sentiment = compute_sentiment(query)
    ctx = customer_context or {}

    route = sentiment["route"]
    escalate = False
    reasons = []

    # VIP overrides: VIP angry → always escalate
    is_vip = ctx.get("is_vip", False)
    if is_vip and sentiment["label"] == "angry":
        route = ROUTE_HUMAN
        escalate = True
        reasons.append("VIP customer is upset — immediate human attention")

    # Repeat contact: if contacted 3+ times about same issue → human
    contact_count = ctx.get("contact_count", 0)
    if contact_count >= 3:
        route = ROUTE_HUMAN
        escalate = True
        reasons.append(f"Customer contacted {contact_count} times about this issue")

    # High-value transaction: always flag
    value_usd = ctx.get("value_usd", 0)
    if value_usd > 500:
        route = ROUTE_HUMAN if sentiment["label"] != "happy" else ROUTE_AI_FLAGGED
        escalate = sentiment["label"] != "happy"
        reasons.append(f"High-value transaction (${value_usd:.2f})")

    if not reasons:
        if route == ROUTE_HUMAN:
            reasons.append(f"Negative sentiment detected (score={sentiment['score']:.2f})")
        elif route == ROUTE_AI_FLAGGED:
            reasons.append("Uncertain sentiment — AI handles with manager review")
        else:
            reasons.append("Positive sentiment — AI handles autonomously")

    result = {
        "ticket_id": ticket_id,
        "sentiment": sentiment,
        "route": route,
        "escalate": escalate,
        "reason": "; ".join(reasons),
        "customer_context_applied": {
            "is_vip": is_vip,
            "contact_count": contact_count,
            "value_usd": value_usd,
        },
    }

    logger.info("Sentiment route: ticket=%s score=%.2f route=%s escalate=%s",
                ticket_id, sentiment["score"], route, escalate)

    return result