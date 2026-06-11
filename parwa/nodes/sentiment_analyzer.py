"""Node 18: SENTIMENT_ANALYZER — Detects customer emotion and urgency.

Router Agent node. Analyzes customer sentiment to influence routing
and tone of the response. Angry customers get different handling.
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


@safe_node("SENTIMENT_ANALYZER", fallback={"sentiment": "neutral", "sentiment_urgency": 0.3})
async def sentiment_analyzer(state: dict[str, Any]) -> dict[str, Any]:
    """Analyze customer sentiment and urgency (async).

    Reads: raw_message
    Writes: sentiment, sentiment_urgency
    """
    raw_message = state.get("raw_message", "")

    # Guard: empty or non-string message
    if not isinstance(raw_message, str) or not raw_message.strip():
        return {
            "sentiment": SentimentType.NEUTRAL,
            "sentiment_urgency": 0.3,
        }

    sentiment_str, urgency = _analyze_sentiment_rule_based(raw_message)

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

    return {
        "sentiment": sentiment_str,
        "sentiment_urgency": urgency,
    }
