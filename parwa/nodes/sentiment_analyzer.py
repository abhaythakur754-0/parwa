"""Node 18: SENTIMENT_ANALYZER — Detects customer emotion and urgency.

Router Agent node. Analyzes customer sentiment to influence routing
and tone of the response. Angry customers get different handling.
"""

from __future__ import annotations

from typing import Any

from parwa.state import SentimentType
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node


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
    """Analyze sentiment using LLM (async). Returns (sentiment, urgency)."""
    prompt = (
        f"Analyze the sentiment of this customer message.\n\n"
        f"Customer message: {message}\n\n"
        f"Reply with ONLY: sentiment|urgency where sentiment is one of: "
        f"happy, neutral, frustrated, angry and urgency is 0.0-1.0"
    )
    text = await ainvoke_llm(prompt)
    parts = text.strip().split("|")
    sentiment = parts[0].lower() if parts else "neutral"
    try:
        urgency = float(parts[1]) if len(parts) > 1 else 0.5
    except (ValueError, IndexError):
        urgency = 0.5
    return sentiment, urgency


@safe_node("SENTIMENT_ANALYZER")
async def sentiment_analyzer(state: dict[str, Any]) -> dict[str, Any]:
    """Analyze customer sentiment and urgency (async).

    Reads: raw_message
    Writes: sentiment, sentiment_urgency
    """
    raw_message = state.get("raw_message", "")

    sentiment_str, urgency = _analyze_sentiment_rule_based(raw_message)

    # If neutral and not in mock mode, try LLM for nuance
    if sentiment_str == SentimentType.NEUTRAL and not MOCK_MODE:
        sentiment_str, urgency = await _analyze_sentiment_llm(raw_message)

    # Validate sentiment against enum values
    valid_sentiments = {e.value for e in SentimentType}
    if sentiment_str not in valid_sentiments:
        sentiment_str = SentimentType.NEUTRAL

    return {
        "sentiment": sentiment_str,
        "sentiment_urgency": urgency,
    }
