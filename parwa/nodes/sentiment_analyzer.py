"""Node 18: SENTIMENT_ANALYZER — Detects customer emotion and urgency.

Router Agent node. Analyzes customer sentiment to influence routing
and tone of the response. Angry customers get different handling.

Phase 5: Now uses FrameworkBrain with CoT for nuanced sentiment analysis.
Falls back to rule-based on FrameworkBrain failure.
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
# Month 1: Expanded to catch more nuanced frustration patterns
# Month 1 v2: Added demand/imperative language for ANGRY detection
_SENTIMENT_KEYWORDS: dict[SentimentType, list[str]] = {
    SentimentType.ANGRY: [
        "furious", "outraged", "disgusted", "lawyer", "lawsuit", "attorney", "sue",
        "legal action", "i demand", "right now",
        "this is ridiculous", "going to contact",
        "nobody has responded", "worst service", "third email", "fourth attempt",
        "fraud", "illegal", "demand to speak", "speak to a manager",
        # Month 4: More angry patterns
        "other vendors", "looking at other", "done with your", "so done",
        "completely unacceptable", "i've had enough",
    ],
    SentimentType.FRUSTRATED: [
        "frustrated", "unacceptable", "ridiculous", "upset", "disappointed",
        "terrible", "worst", "charged twice", "overcharged", "wrong amount",
        "not working", "broken", "crashing", "still waiting", "hasn't arrived",
        "has been 10 days", "weeks", "needs to be fixed", "immediately",
        "error", "can't access", "cannot access", "doesn't work", "not responding",
        "very disappointed", "incredibly slow", "card was declined",
        # Month 2: Additional frustrated keywords
        "waiting for", "not happy", "not what i expected", "misleading",
        "nothing but problems", "complicated", "inconvenient", "quality",
        "billing is wrong", "shipping delay", "refund from", "again",
        "second time", "second month", "doesn't match", "on hold",
        "unacceptably", "shouldn't be so hard", "this is really",
        "i've tried everything", "product doesn't match", "lost all my work",
        "broke after", "no one told us", "paid for doesn't work",
        "suspended by mistake", "declined",
        "fix this", "please fix", "not ideal",
        "unacceptable", "keep crashing", "third time reporting",
        # Month 4: More frustration patterns
        "trying to reach", "all day", "running out of time",
        "nothing has happened", "keep getting", "automated system",
        "should not take this long", "this is really frustrating",
        "at this point", "change my mind", "get it somewhere else",
        "level of service", "absolutely terrible", "no idea",
        "had enough", "garbage", "stupid", "done with",
        "terrible level of service", "waste of time", "joke",
        # NOTE: Removed "i need", "i want", "where is my" — these are too generic
        # and incorrectly match neutral order-status and account-modification queries
    ],
    SentimentType.HAPPY: ["great", "awesome", "love", "thank you", "perfect", "wonderful", "excellent", "happy", "good job"],
}


def _analyze_sentiment_rule_based(message: str) -> tuple[str, float]:
    """Analyze sentiment using keyword matching with priority scoring.

    Month 1 v2: ANGRY takes priority over FRUSTRATED. If ANY angry keyword
    matches, the sentiment is ANGRY (even if frustrated keywords also match).
    This prevents 'I demand to speak to a manager right now!' from being
    classified as neutral just because the word 'demand' wasn't in the list.

    Returns (sentiment, urgency).
    """
    message_lower = message.lower()

    # Check ANGRY first — highest priority
    for kw in _SENTIMENT_KEYWORDS[SentimentType.ANGRY]:
        if kw in message_lower:
            return SentimentType.ANGRY, 0.95

    # Then check FRUSTRATED
    for kw in _SENTIMENT_KEYWORDS[SentimentType.FRUSTRATED]:
        if kw in message_lower:
            return SentimentType.FRUSTRATED, 0.75

    # Then check HAPPY
    for kw in _SENTIMENT_KEYWORDS[SentimentType.HAPPY]:
        if kw in message_lower:
            return SentimentType.HAPPY, 0.1

    return SentimentType.NEUTRAL, 0.3


async def _analyze_sentiment_llm(message: str, *, ticket_id: str = "", variant: str = "parwa", complexity: str = "simple") -> tuple[str, float]:
    """Analyze sentiment using LLM (async). Returns (sentiment, urgency).

    Uses structured output parsing and sanitized prompt.

    Month 1 fixes:
    - Alphabetically ordered sentiment list (eliminates first-position bias)
    - Few-shot examples for each sentiment type
    - Reduced max_tokens for classification
    """
    system_instructions = (
        "Analyze the sentiment of the customer message.\n\n"
        "Reply with ONLY: sentiment|urgency where sentiment is one of: "
        "angry, frustrated, happy, neutral and urgency is 0.0-1.0\n\n"
        "CRITICAL DISTINCTIONS:\n"
        "- ANGRY = threatening legal action, extreme outrage, ALL CAPS, demanding, insulting, "
        "saying 'I've had enough', threatening to leave, mentioning attorneys/lawyers\n"
        "- FRUSTRATED = disappointed, annoyed, impatient, saying 'trying to reach someone all day', "
        "'running out of time', 'this is really frustrating', 'nothing has happened', "
        "'keep getting automated system', 'should not take this long', "
        "expressing urgency without threats\n"
        "- HAPPY = grateful, satisfied, praising\n"
        "- NEUTRAL = simple factual questions with NO emotional words, purely informational\n\n"
        "IMPORTANT: If the customer expresses ANY impatience, disappointment, or urgency "
        "beyond a simple question, classify as FRUSTRATED, not NEUTRAL.\n\n"
        "Examples:\n"
        "Customer: 'I will contact my attorney about this fraud' → angry|0.95\n"
        "Customer: 'I am absolutely disgusted with your service' → angry|0.90\n"
        "Customer: 'I've been trying to reach someone all day and keep getting the automated system' → frustrated|0.70\n"
        "Customer: 'This is really frustrating because I paid for it and nothing has happened' → frustrated|0.75\n"
        "Customer: 'It's now been 3 days and the tracking hasn't updated at all' → frustrated|0.65\n"
        "Customer: 'This should not take this long' → frustrated|0.60\n"
        "Customer: 'I'm running out of time and need to know' → frustrated|0.70\n"
        "Customer: 'I am disappointed with the delay' → frustrated|0.60\n"
        "Customer: 'Thank you so much for your help!' → happy|0.10\n"
        "Customer: 'When will my order arrive?' → neutral|0.30\n"
        "Customer: 'What is your return policy?' → neutral|0.20\n"
    )
    prompt = build_safe_prompt(system_instructions, message)
    text = await ainvoke_llm(
        prompt,
        node_name="SENTIMENT_ANALYZER",
        ticket_id=ticket_id,
        variant=variant,
        complexity=complexity,
        # max_tokens removed — uses generous default from _NODE_MAX_TOKENS
    )
    return parse_sentiment_response(text)


async def _analyze_sentiment_with_brain(state: dict[str, Any]) -> tuple[str, float, list[str]]:
    """Analyze sentiment using FrameworkBrain (Phase 5).

    Uses CoT for nuanced sentiment detection.
    Returns (sentiment_str, urgency, frameworks_used).
    Falls back to rule-based on any failure.
    """
    raw_message = state.get("raw_message", "")
    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="SENTIMENT_ANALYZER", state=state)
        result = await brain.think(
            prompt=raw_message,
            techniques=["chain_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Extract sentiment from brain output
        output = result.output.lower() if result.output else ""
        confidence = result.confidence if result.confidence > 0 else 0.5
        frameworks = result.frameworks_used if result.frameworks_used else []

        # Try to parse sentiment from output
        sentiment_str = SentimentType.NEUTRAL
        if "angry" in output or "furious" in output:
            sentiment_str = SentimentType.ANGRY
        elif "frustrated" in output or "upset" in output or "disappointed" in output:
            sentiment_str = SentimentType.FRUSTRATED
        elif "happy" in output or "satisfied" in output or "pleased" in output:
            sentiment_str = SentimentType.HAPPY

        urgency = confidence if sentiment_str != SentimentType.NEUTRAL else 0.3

        if sentiment_str == SentimentType.NEUTRAL and "neutral" not in output:
            logger.debug("sentiment_analyzer: FrameworkBrain couldn't determine sentiment, falling back")
            sentiment_str, urgency = _analyze_sentiment_rule_based(raw_message)
            frameworks = ["chain_of_thought"]

        return sentiment_str, urgency, frameworks

    except Exception as exc:
        logger.warning(
            "sentiment_analyzer: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        sentiment_str, urgency = _analyze_sentiment_rule_based(raw_message)
        return sentiment_str, urgency, ["chain_of_thought"]


@safe_node("SENTIMENT_ANALYZER", fallback={"sentiment": "neutral", "sentiment_urgency": 0.3})
async def sentiment_analyzer(state: dict[str, Any]) -> dict[str, Any]:
    """Analyze customer sentiment and urgency (async).

    Phase 5: Uses FrameworkBrain with CoT for nuanced sentiment.
    Falls back to rule-based + LLM on FrameworkBrain failure.

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

    # Month 4 TPM optimization: Skip FrameworkBrain for speed.
    # Use rule-based first (free, instant), then LLM only if neutral.
    # This cuts LLM calls per ticket from 2 to 0-1 for this node.
    sentiment_str, urgency = _analyze_sentiment_rule_based(raw_message)
    frameworks = []

    # Only call LLM if rule-based says neutral (might miss nuance)
    if sentiment_str == SentimentType.NEUTRAL and not MOCK_MODE:
        try:
            llm_sentiment, llm_urgency = await _analyze_sentiment_llm(
                raw_message,
                ticket_id=state.get("ticket_id", ""),
                variant=state.get("variant", "parwa"),
                complexity=state.get("complexity", "simple"),
            )
            if llm_sentiment != SentimentType.NEUTRAL:
                sentiment_str, urgency = llm_sentiment, llm_urgency
        except Exception as exc:
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

    # Track frameworks used
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
