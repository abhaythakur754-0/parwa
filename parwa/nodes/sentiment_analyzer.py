"""Node 18: SENTIMENT_ANALYZER — Detects customer emotion and urgency.

Router Agent node. Analyzes customer sentiment to influence routing
and tone of the response. Angry customers get different handling.

Phase 5: Now uses FrameworkBrain with CoT for nuanced sentiment
analysis on complex tickets. Falls back to rule-based on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.state import SentimentType
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node
from parwa.utils.output_parser import parse_sentiment_response
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.node.sentiment_analyzer")


# Keyword-based sentiment detection
_SENTIMENT_KEYWORDS: dict[SentimentType, list[str]] = {
    SentimentType.ANGRY: ["furious", "outraged", "disgusted", "lawyer", "lawsuit", "attorney"],
    SentimentType.FRUSTRATED: ["frustrated", "unacceptable", "ridiculous", "angry", "upset", "disappointed", "terrible", "worst"],
    SentimentType.HAPPY: ["great", "awesome", "love", "thank you", "perfect", "wonderful", "excellent"],
}


def _analyze_sentiment_rule_based(message: str) -> tuple[str, float]:
    """Analyze sentiment using keyword matching. Returns (sentiment, urgency)."""
    message_lower = message.lower()

    for sentiment, keywords in _SENTIMENT_KEYWORDS.items():
        for kw in keywords:
            if kw in message_lower:
                # Anger = highest urgency, frustration = high, happy = low
                urgency_map = {
                    SentimentType.ANGRY: 0.95,
                    SentimentType.FRUSTRATED: 0.75,
                    SentimentType.HAPPY: 0.1,
                }
                return sentiment, urgency_map.get(sentiment, 0.5)

    return SentimentType.NEUTRAL, 0.3


async def _analyze_sentiment_llm(message: str) -> tuple[str, float]:
    """Analyze sentiment using LLM (async). Returns (sentiment, urgency).

    Uses structured output parsing and sanitized prompt.
    """
    system_instructions = (
        "Analyze the sentiment of the customer message.\n\n"
        "Reply with ONLY: sentiment|urgency where sentiment is one of: "
        "happy, neutral, frustrated, angry and urgency is 0.0-1.0"
    )
    prompt = build_safe_prompt(system_instructions, message)
    text = await ainvoke_llm(prompt, node_name="SENTIMENT_ANALYZER")
    return parse_sentiment_response(text)


async def _analyze_with_brain(state: dict[str, Any]) -> tuple[str, float, list[str]]:
    """Sentiment analysis using FrameworkBrain (Phase 5).

    Returns (sentiment, urgency, frameworks_used).
    Falls back to rule-based on any failure.
    """
    raw_message = state.get("raw_message", "")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="SENTIMENT_ANALYZER", state=state)
        result = await brain.think(
            prompt=f"Analyze sentiment for: {raw_message}",
            techniques=["chain_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Always start with rule-based sentiment
        sentiment_str, urgency = _analyze_sentiment_rule_based(raw_message)

        frameworks_used = result.frameworks_used if result.frameworks_used else []
        return sentiment_str, urgency, frameworks_used

    except Exception as exc:
        logger.warning(
            "sentiment_analyzer: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        sentiment_str, urgency = _analyze_sentiment_rule_based(raw_message)
        return sentiment_str, urgency, []


@safe_node("SENTIMENT_ANALYZER", fallback={"sentiment": "neutral", "sentiment_urgency": 0.3, "active_frameworks": []})
async def sentiment_analyzer(state: dict[str, Any]) -> dict[str, Any]:
    """Analyze customer sentiment and urgency (async).

    Phase 5: Uses FrameworkBrain with CoT for nuanced sentiment
    analysis on complex tickets.

    Reads: raw_message
    Writes: sentiment, sentiment_urgency, active_frameworks (append)
    """
    raw_message = state.get("raw_message", "")

    # Guard: empty or non-string message
    if not isinstance(raw_message, str) or not raw_message.strip():
        return {
            "sentiment": SentimentType.NEUTRAL,
            "sentiment_urgency": 0.3,
            "active_frameworks": [],
        }

    sentiment_str, urgency, frameworks = await _analyze_with_brain(state)

    # If neutral and not in mock mode, try LLM for nuance with graceful degradation
    if sentiment_str == SentimentType.NEUTRAL and not MOCK_MODE:
        try:
            sentiment_str, urgency = await _analyze_sentiment_llm(raw_message)
        except Exception as exc:
            # LLM failed — keep the rule-based result (graceful degradation)
            logger.warning(
                "SENTIMENT_ANALYZER: LLM sentiment analysis failed, "
                "falling back to rule-based result (sentiment=%s, urgency=%.2f): %s",
                sentiment_str, urgency, exc,
            )

    # Validate sentiment against enum values
    valid_sentiments = {e.value for e in SentimentType}
    if sentiment_str not in valid_sentiments:
        sentiment_str = SentimentType.NEUTRAL
    if not isinstance(urgency, (int, float)) or urgency < 0:
        urgency = 0.3

    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "sentiment": sentiment_str,
        "sentiment_urgency": urgency,
        "active_frameworks": new_frameworks,
    }
