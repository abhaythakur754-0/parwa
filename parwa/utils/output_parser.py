"""Structured output parser for PARWA LLM responses.

Replaces fragile split("|") parsing with robust extraction patterns.
Handles various LLM response formats gracefully with multiple fallback
strategies for each expected output format.

Key parsers:
- Intent response: "refund_request|0.95" → ("refund_request", 0.95)
- Sentiment response: "frustrated|0.85" → ("frustrated", 0.85)
- Escalation response: "true|legal_threat" → (True, "legal_threat")
- Quality response: "85|accurate,complete" → (85.0, ["accurate", "complete"])
- FAQ response: "refund_policy|0.90|Refunds are..." → ("refund_policy", 0.90, "Refunds are...")
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger("parwa.output_parser")


def parse_pipe_delimited(text: str, expected_parts: int = 2) -> list[str]:
    """Safely parse a pipe-delimited response.

    Args:
        text: The raw LLM response text.
        expected_parts: Expected number of pipe-separated parts.

    Returns:
        List of trimmed parts, padded to expected_parts if needed.
    """
    if not text or not isinstance(text, str):
        return [""] * expected_parts

    parts = [p.strip() for p in text.strip().split("|")]
    # Pad with empty strings if we got fewer parts than expected
    while len(parts) < expected_parts:
        parts.append("")
    # Truncate if we got more (extra pipes in content)
    if len(parts) > expected_parts + 2:
        # Last part might contain pipes legitimately (e.g., FAQ content)
        # Rejoin everything beyond expected_parts-1 into the last part
        parts = parts[:expected_parts - 1] + ["|".join(parts[expected_parts - 1:])]

    return parts


def parse_intent_response(text: str) -> tuple[str, float]:
    """Parse an intent classification LLM response.

    Expected format: "intent_name|confidence"
    Example: "refund_request|0.95"

    Falls back to regex extraction, then keyword matching.

    Returns:
        Tuple of (intent_str, confidence_float).
    """
    if not text:
        return "general_inquiry", 0.5

    parts = parse_pipe_delimited(text, 2)
    intent_str = parts[0].lower().strip()
    confidence_str = parts[1].strip()

    # Parse confidence
    confidence = 0.75  # default
    try:
        val = float(confidence_str)
        # If value is clearly a percentage (e.g., 95 means 0.95),
        # convert. But values between 1.0 and 2.0 are likely scale
        # overflow — clamp rather than divide.
        if val > 100.0:
            # Definitely a percentage (e.g., 150 = 1.5 on 0-1 scale)
            confidence = val / 100.0
        elif val > 1.0:
            # Could be percentage (95 → 0.95) or overflow (1.5 → clamp to 1.0)
            # Heuristic: if it looks like a percentage (integer between 2-100),
            # convert. Otherwise clamp.
            if val == int(val) and val <= 100.0:
                confidence = val / 100.0  # e.g., 95 → 0.95
            else:
                confidence = val  # will be clamped later
        else:
            confidence = val
    except (ValueError, TypeError):
        # Try extracting a decimal number from the confidence part
        match = re.search(r'(\d+\.?\d*)', confidence_str)
        if match:
            val = float(match.group(1))
            if val > 100.0:
                confidence = val / 100.0
            elif val > 1.0:
                if val == int(val) and val <= 100.0:
                    confidence = val / 100.0
                else:
                    confidence = val
            else:
                confidence = val

    # Clamp confidence to [0, 1]
    confidence = max(0.0, min(1.0, confidence))

    # Validate intent against known values
    valid_intents = {
        "order_status", "refund_request", "cancellation", "billing_issue",
        "technical_support", "faq_question", "complaint",
        "account_modification", "escalation", "general_inquiry",
    }

    if intent_str not in valid_intents:
        # Try to extract a valid intent from the text using regex
        for valid in valid_intents:
            if valid in text.lower():
                intent_str = valid
                break
        else:
            intent_str = "general_inquiry"

    return intent_str, confidence


def parse_sentiment_response(text: str) -> tuple[str, float]:
    """Parse a sentiment analysis LLM response.

    Expected format: "sentiment|urgency"
    Example: "frustrated|0.85"

    Returns:
        Tuple of (sentiment_str, urgency_float).
    """
    if not text:
        return "neutral", 0.5

    parts = parse_pipe_delimited(text, 2)
    sentiment_str = parts[0].lower().strip()
    urgency_str = parts[1].strip()

    # Parse urgency
    urgency = 0.5
    try:
        urgency = float(urgency_str)
    except (ValueError, TypeError):
        match = re.search(r'(\d+\.?\d*)', urgency_str)
        if match:
            val = float(match.group(1))
            urgency = val / 100.0 if val > 1.0 else val

    urgency = max(0.0, min(1.0, urgency))

    # Validate sentiment
    valid_sentiments = {"happy", "neutral", "frustrated", "angry"}

    if sentiment_str not in valid_sentiments:
        for valid in valid_sentiments:
            if valid in text.lower():
                sentiment_str = valid
                break
        else:
            sentiment_str = "neutral"

    return sentiment_str, urgency


def parse_escalation_response(text: str) -> tuple[bool, str]:
    """Parse an escalation decision LLM response.

    Expected format: "true|reason" or "false|"
    Example: "true|legal_threat"

    Returns:
        Tuple of (should_escalate_bool, escalation_reason_str).
    """
    if not text:
        return False, ""

    parts = parse_pipe_delimited(text, 2)
    escalate_str = parts[0].lower().strip()
    reason = parts[1].strip()

    # Parse boolean - accept various formats
    should_escalate = escalate_str in ("true", "yes", "1", "escalate", "escalate_to_human")

    if not should_escalate and "escalat" in text.lower():
        should_escalate = True
        if not reason:
            reason = "detected_escalation_keyword"

    return should_escalate, reason


def parse_quality_response(text: str) -> tuple[float, list[str]]:
    """Parse a quality scoring LLM response.

    Expected format: "score|issue1,issue2"
    Example: "85|accurate,complete,compliant"

    Returns:
        Tuple of (score_float, issues_list).
    """
    if not text:
        return 50.0, ["no_response"]

    parts = parse_pipe_delimited(text, 2)
    score_str = parts[0].strip()
    issues_str = parts[1].strip()

    # Parse score
    score = 50.0
    try:
        score = float(score_str)
    except (ValueError, TypeError):
        match = re.search(r'(\d+\.?\d*)', score_str)
        if match:
            score = float(match.group(1))
        # If score > 100, normalize
        if score > 100:
            score = 50.0

    score = max(0.0, min(100.0, score))

    # Parse issues
    issues = []
    if issues_str:
        issues = [i.strip() for i in issues_str.split(",") if i.strip()]
    else:
        # Default issues based on score
        if score < 50:
            issues = ["low_quality"]
        elif score < 80:
            issues = ["needs_improvement"]

    return score, issues


def parse_faq_response(text: str) -> tuple[str, float, str]:
    """Parse an FAQ matching LLM response.

    Expected format: "faq_id|relevance_score|content"
    Example: "refund_policy|0.90|Refunds are available within 30 days..."

    Returns:
        Tuple of (faq_id, relevance_score, content).
    """
    if not text:
        return "no_match", 0.0, ""

    # FAQ content often contains pipes, so we parse more carefully
    parts = parse_pipe_delimited(text, 3)
    faq_id = parts[0].strip()
    relevance_str = parts[1].strip()
    content = parts[2].strip()

    # Parse relevance
    relevance = 0.0
    try:
        relevance = float(relevance_str)
    except (ValueError, TypeError):
        match = re.search(r'(\d+\.?\d*)', relevance_str)
        if match:
            val = float(match.group(1))
            relevance = val / 100.0 if val > 1.0 else val

    relevance = max(0.0, min(1.0, relevance))

    return faq_id, relevance, content


def parse_pii_response(text: str) -> tuple[bool, str]:
    """Parse a PII detection LLM response.

    Expected format: "true|description" or "false|No PII detected"
    Example: "true|Found SSN: XXX-XX-1234"

    Returns:
        Tuple of (pii_detected_bool, description_str).
    """
    if not text:
        return False, ""

    parts = parse_pipe_delimited(text, 2)
    detected_str = parts[0].lower().strip()
    description = parts[1].strip()

    detected = detected_str in ("true", "yes", "1", "found", "detected")

    return detected, description


def parse_reasoning_response(text: str) -> tuple[list[str], str]:
    """Parse a reasoning chain LLM response.

    Extracts the reasoning chain (step-by-step lines) and the conclusion
    from an LLM reasoning response. Replaces the fragile manual string
    split on "conclusion:" that was previously in reasoning_engine.

    Expected format:
        Step 1: ...
        Step 2: ...
        Conclusion: <the conclusion>

    Args:
        text: The raw LLM reasoning response.

    Returns:
        Tuple of (chain_list, conclusion_str).
    """
    if not text or not isinstance(text, str):
        return [], ""

    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]

    conclusion = ""
    chain = []

    for line in lines:
        # Check for conclusion patterns
        lower = line.lower()
        if lower.startswith("conclusion:"):
            conclusion = line[len("conclusion:"):].strip()
        elif lower.startswith("conclusion :"):
            conclusion = line[len("conclusion :"):].strip()
        elif "conclusion:" in lower:
            # Conclusion embedded in a line
            idx = lower.index("conclusion:")
            conclusion = line[idx + len("conclusion:"):].strip()
            # Add the part before conclusion to chain
            before = line[:idx].strip()
            if before:
                chain.append(before)
            continue
        else:
            chain.append(line)

    # If no explicit conclusion found, use the last line
    if not conclusion and chain:
        conclusion = chain[-1]

    return chain, conclusion


def try_parse_json(text: str) -> dict[str, Any] | None:
    """Try to parse text as JSON, with common LLM formatting fixes.

    Handles common LLM JSON issues:
    - Wrapped in markdown code blocks
    - Trailing commas
    - Single quotes instead of double quotes

    Returns:
        Parsed dict, or None if parsing fails.
    """
    if not text:
        return None

    # Strip markdown code blocks
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove ```json and ``` wrappers
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if len(lines) > 2 else lines)

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try fixing single quotes
    try:
        return json.loads(cleaned.replace("'", '"'))
    except json.JSONDecodeError:
        pass

    # Try extracting JSON object from text
    match = re.search(r'\{[^{}]*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None
