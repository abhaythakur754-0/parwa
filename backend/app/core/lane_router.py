"""
Lane Router — 3-Lane Message Classification (Commit 2).

Classifies a customer message into one of 5 message types, which maps to
one of 3 processing lanes:

  Message Type          →  Lane       →  Pipeline Flow
  ─────────────────────────────────────────────────────────────
  NEW_ISSUE             →  FULL       →  Node 1 → 2 → 3 → 3.5 → 4 → 4.5 → 5 → 6 → END
  FOLLOW_UP             →  QUICK      →  Node 1 → 7 (Simple Resolver) → END
  CLARIFICATION         →  QUICK      →  Node 1 → 7 (Simple Resolver) → END
  GRATITUDE             →  INSTANT    →  Node 1 → finalize (canned response) → END
  SIMPLE_QUESTION       →  INSTANT    →  Node 1 → finalize (canned response) → END

ALL 16 non-LLM techniques run in Node 1 for EVERY lane (they're free —
zero API cost). The lane only controls what happens AFTER Node 1:

  - FULL lane:    ~15 LLM calls (Nodes 2-6 reasoning + quality loop)
  - QUICK lane:   0-3 LLM calls (Node 7 Simple Resolver only)
  - INSTANT lane: 0-1 LLM calls (canned response, no LLM needed)

Thread detection: a message is a FOLLOW_UP if the ticket already has
an AI response (i.e., this is a customer replying to an existing
conversation, not starting a new one).

Business rationale (P-004): 80% of customer messages are follow-ups
or simple questions that don't need the full 8-node reasoning pipeline.
Routing them to QUICK/INSTANT lanes cuts average LLM cost by ~70% and
cuts response time from ~15s to ~2s for simple messages.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.lane_router")


# ── Message Type Constants ─────────────────────────────────────────

NEW_ISSUE = "NEW_ISSUE"
FOLLOW_UP = "FOLLOW_UP"
CLARIFICATION = "CLARIFICATION"
GRATITUDE = "GRATITUDE"
SIMPLE_QUESTION = "SIMPLE_QUESTION"

# Lane constants
LANE_FULL = "FULL"
LANE_QUICK = "QUICK"
LANE_INSTANT = "INSTANT"

# Message type → Lane mapping
MESSAGE_TYPE_TO_LANE: Dict[str, str] = {
    NEW_ISSUE: LANE_FULL,
    FOLLOW_UP: LANE_QUICK,
    CLARIFICATION: LANE_QUICK,
    GRATITUDE: LANE_INSTANT,
    SIMPLE_QUESTION: LANE_INSTANT,
}


# ── Pattern definitions (non-LLM, regex-based) ────────────────────

# Gratitude patterns — "thanks", "thank you", "appreciate it", etc.
# Matches both short ("thanks!") and longer ("thank you so much for your help!")
# messages. Uses word-boundary matching so "thanks" matches even with trailing text.
GRATITUDE_PATTERNS: List[str] = [
    r"^\s*thank(s| you)?\s*[!.]?\s*$",
    r"^\s*thx\s*[!.]?\s*$",
    r"^\s*thank(s| you)?\s+(so much|a lot|again|for your help|for everything|for the help|for your assistance)\b",
    r"^\s*i\s+appreciate(d)?\s+(it|that|your help|the help|your assistance)\b",
    r"^\s*great(,?\s*thanks?)?\s*[!.]?\s*$",
    r"^\s*awesome,?\s*thanks?\s*[!.]?\s*$",
    r"^\s*perfect,?\s*thanks?\s*[!.]?\s*$",
    r"^\s*got it,?\s*thanks?\s*[!.]?\s*$",
    r"^\s*you've been (very )?helpful\b",
    r"^\s*cheers\s*[!.]?\s*$",
    r"^\s*cool,?\s*thanks?\s*[!.]?\s*$",
]

# Simple question patterns — short, single-question, FAQ-like.
# Must be SHORT (under 80 chars) AND match a simple-question shape.
SIMPLE_QUESTION_SHAPES: List[str] = [
    r"^\s*what (are|is) your (hours|phone number|email|address)\s*\?\s*$",
    r"^\s*how (do|can) i (contact|reach|call) you\s*\?\s*$",
    r"^\s*where (are|is) you (located|based)\s*\?\s*$",
    r"^\s*do you have (a|an) (phone|app|website|phone number|email)\s*\?\s*$",
    r"^\s*what time (do|are) you (open|available)\s*\?\s*$",
    r"^\s*what(?:'s| is) your (support )?(phone|email|address|hours)\s*\?\s*$",
]

# Clarification patterns — customer asking for more info about a previous response
CLARIFICATION_PATTERNS: List[str] = [
    r"^\s*what do you mean\b",
    r"^\s*i don't understand\b",
    r"^\s*can you (explain|clarify|elaborate)\b",
    r"^\s*could you (explain|clarify|elaborate)\b",
    r"^\s*more details\b",
    r"^\s*what (exactly|specifically) (do|did) you (mean|say)\b",
]

# Follow-up signal patterns — customer responding to a previous AI reply
FOLLOW_UP_SIGNALS: List[str] = [
    r"^\s*(yes|no|ok|okay|sure|got it|understood|sounds good)\b",
    r"^\s*(i tried|i did|i tried that|i did that)\b",
    r"^\s*(that (didn't|did not) work|still (not working|broken|failing))\b",
    r"^\s*(it worked|that worked|problem solved|issue resolved)\b",
    r"^\s*(still (waiting|no response|nothing))\b",
    r"^\s*(any update|any news|status\?)\b",
    r"^\s*(i also (have|need|want)|another (thing|question|issue))\b",
]


def _matches_any(patterns: List[str], text: str) -> bool:
    """Check if text matches any of the regex patterns (case-insensitive)."""
    text_lower = text.lower().strip()
    for pat in patterns:
        if re.search(pat, text_lower, re.IGNORECASE):
            return True
    return False


def classify_message_type(
    query: str,
    ticket_history: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Classify a customer message into one of 5 message types.

    Args:
        query: The customer's message text.
        ticket_history: List of previous messages on this ticket.
            Each dict should have a "role" key ("customer" or "ai").
            If empty or None, this is a new ticket → NEW_ISSUE (unless
            the message itself is gratitude/simple_question).

    Returns:
        One of: NEW_ISSUE, FOLLOW_UP, CLARIFICATION, GRATITUDE, SIMPLE_QUESTION

    Classification order (first match wins):
        1. GRATITUDE — short "thank you" messages
        2. SIMPLE_QUESTION — short FAQ-style questions
        3. CLARIFICATION — "what do you mean?" type messages
        4. FOLLOW_UP — reply to existing AI conversation
        5. NEW_ISSUE — default for new tickets with substantive content
    """
    if not query or not query.strip():
        return NEW_ISSUE

    query_stripped = query.strip()

    # 1. GRATITUDE — short thank-you messages (highest priority for INSTANT lane)
    if _matches_any(GRATITUDE_PATTERNS, query_stripped):
        return GRATITUDE

    # 2. SIMPLE_QUESTION — short FAQ-style questions
    if len(query_stripped) <= 80 and _matches_any(SIMPLE_QUESTION_SHAPES, query_stripped):
        return SIMPLE_QUESTION

    # 3. CLARIFICATION — customer asking for more info about a previous response
    if _matches_any(CLARIFICATION_PATTERNS, query_stripped):
        return CLARIFICATION

    # 4. FOLLOW_UP — is this a reply on an existing AI conversation?
    has_ai_history = bool(ticket_history) and any(
        msg.get("role") == "ai" for msg in (ticket_history or [])
    )
    if has_ai_history:
        # If the customer is replying on an existing ticket that already
        # has an AI response, treat as FOLLOW_UP (unless it's clearly a
        # new issue — e.g. "I have a different problem")
        if _matches_any(FOLLOW_UP_SIGNALS, query_stripped):
            return FOLLOW_UP
        # Even without explicit signals, a reply on an AI conversation
        # is likely a follow-up
        return FOLLOW_UP

    # 5. NEW_ISSUE — default for new tickets with substantive content
    return NEW_ISSUE


def get_lane_for_message_type(message_type: str) -> str:
    """Map a message type to its processing lane."""
    return MESSAGE_TYPE_TO_LANE.get(message_type, LANE_FULL)


def generate_instant_response(message_type: str, query: str) -> str:
    """Generate a canned response for INSTANT lane messages.

    GRATITUDE and SIMPLE_QUESTION messages don't need LLM reasoning —
    a friendly canned response is faster and costs zero API calls.

    Args:
        message_type: GRATITUDE or SIMPLE_QUESTION
        query: The original customer message (for light personalization)

    Returns:
        A customer-facing response string.
    """
    if message_type == GRATITUDE:
        return (
            "You're very welcome! I'm glad I could help. "
            "If you have any other questions or need further assistance, "
            "please don't hesitate to reach out. Have a great day!"
        )

    if message_type == SIMPLE_QUESTION:
        # Light personalization based on the question type
        q_lower = query.lower()
        if "hours" in q_lower or "open" in q_lower or "available" in q_lower:
            return (
                "Our support team is available 24/7 to help you with any questions or concerns. "
                "You can reach us anytime through this chat, by email, or by phone. "
                "Is there anything specific I can help you with today?"
            )
        if "contact" in q_lower or "reach" in q_lower or "call" in q_lower:
            return (
                "You can reach our support team through this chat, by email at support@parwa.buzz, "
                "or by submitting a ticket through your dashboard. We're here 24/7 to help. "
                "What can I assist you with?"
            )
        if "located" in q_lower or "based" in q_lower or "address" in q_lower:
            return (
                "PARWA is a cloud-based platform, so we're available wherever you are. "
                "Our team operates globally to provide 24/7 support. "
                "Is there anything specific I can help you with?"
            )
        # Generic fallback for simple questions
        return (
            "Great question! I'd be happy to help you with that. "
            "Could you provide a bit more detail so I can give you the most accurate answer? "
            "Alternatively, our support team is available 24/7 if you need immediate assistance."
        )

    # Fallback (shouldn't reach here for INSTANT lane)
    return (
        "Thank you for your message. I've noted your request and our team will follow up "
        "if any further action is needed. Is there anything else I can help you with?"
    )


def classify_lane(
    query: str,
    ticket_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, str]:
    """Classify a message and return both message_type and lane.

    Convenience wrapper that returns a dict with both fields, ready
    to be merged into PipelineV2State.

    Returns:
        {"message_type": "...", "lane": "..."}
    """
    msg_type = classify_message_type(query, ticket_history)
    lane = get_lane_for_message_type(msg_type)
    return {"message_type": msg_type, "lane": lane}
