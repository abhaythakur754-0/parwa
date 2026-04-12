"""
F-147: Reflexion — Tier 3 Premium AI Reasoning Technique

Self-correction engine that activates when a previous response was
rejected, corrected, or when confidence drops mid-conversation. Uses
deterministic heuristic-based reflection (no LLM calls) to:

  1. Failure Detection    — identify what went wrong from customer feedback
  2. Self-Reflection      — analyze failure mode and root cause
  3. Strategy Adjustment  — select corrective strategy based on failure type
  4. Improved Generation  — produce new response with adjusted approach
  5. Meta-Reasoning Trace — log reflection process for continuous improvement

Performance target: ~400 tokens, sub-100ms processing.

Building Codes: BC-001 (company isolation), BC-008 (never crash),
               BC-012 (graceful degradation)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.core.technique_router import TechniqueID
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
)
from app.logger import get_logger

logger = get_logger("reflexion")


# ── Failure Modes ──────────────────────────────────────────────────


class FailureMode(str, Enum):
    """Categories of failures detected from customer feedback."""

    MISUNDERSTOOD_QUERY = "misunderstood_query"
    INCORRECT_INFO = "incorrect_information"
    BAD_TONE = "inappropriate_tone"
    MISSED_CONTEXT = "missed_context"
    INCOMPLETE_RESPONSE = "incomplete_response"
    WRONG_SCOPE = "wrong_scope"


# ── Strategy Adjustments ───────────────────────────────────────────


class StrategyAdjustment(str, Enum):
    """Corrective strategies triggered by specific failure modes."""

    SWITCH_TO_INVESTIGATIVE = "investigative"
    SWITCH_TO_EMPATHETIC = "empathetic"
    ADD_MORE_DETAIL = "detailed"
    SIMPLIFY_RESPONSE = "simplified"
    FOCUS_SPECIFICS = "specific_focused"
    PROVIDE_ALTERNATIVES = "alternatives"


# ── Failure Mode Detection Patterns ────────────────────────────────
#
# Ordered by specificity: more specific patterns first so that
# compound signals (e.g. "that's wrong and rude") are classified
# by the most descriptive failure mode.


_FAILURE_MODE_PATTERNS: List[Tuple[re.Pattern, FailureMode]] = [
    # ── MISUNDERSTOOD_QUERY ────────────────────────────────────────
    # "that's not what I asked", "you're not listening", "I didn't say that"
    (
        re.compile(
            r"\b(not\s+what\s+i\s+(?:asked|said|meant)|you'?re?\s+not\s+listening|"
            r"i\s+didn'?t\s+(?:say|ask|mean)\s+that|you\s+(?:completely\s+)?misunderstood|"
            r"read\s+my\s+question\s+again|pay\s+attention)\b",
            re.I,
        ),
        FailureMode.MISUNDERSTOOD_QUERY,
    ),
    # ── INCORRECT_INFO ─────────────────────────────────────────────
    # "that's wrong", "incorrect", "not right", "that's not true"
    (
        re.compile(
            r"\b(that'?s?\s+(?:wrong|incorrect|not\s+right|not\s+true|false)|"
            r"that\s+info\s+is\s+wrong|your\s+answer\s+is\s+incorrect|"
            r"that\s+is\s+not\s+(?:correct|accurate|right)|bad\s+info|"
            r"that\s+doesn'?t\s+match\s+my\s+records)\b",
            re.I,
        ),
        FailureMode.INCORRECT_INFO,
    ),
    # ── BAD_TONE ───────────────────────────────────────────────────
    # "rude", "unhelpful", "condescending", "dismissive"
    (
        re.compile(
            r"\b(rude|unhelpful|condescending|dismissive|insensitive|"
            r"arrogant|robotic|cold|not\s+empathetic|you\s+sound\s+(?:rude|robotic)|"
            r"terrible\s+service|worst\s+(?:support|service|experience))\b",
            re.I,
        ),
        FailureMode.BAD_TONE,
    ),
    # ── MISSED_CONTEXT ─────────────────────────────────────────────
    # "you missed", "didn't mention", "what about", "ignored"
    (
        re.compile(
            r"\b(you\s+(?:missed|skipped|ignored|forgot|overlooked)|"
            r"didn'?t\s+(?:mention|address|consider|include|cover)|"
            r"what\s+about\s+(?:the\s+)?(?:fact\s+that|my\s+|the\s+)|"
            r"you\s+didn'?t\s+read\s+(?:my\s+)?ticket|leaving\s+out)\b",
            re.I,
        ),
        FailureMode.MISSED_CONTEXT,
    ),
    # ── INCOMPLETE_RESPONSE ────────────────────────────────────────
    # "not enough", "incomplete", "tell me more", "that's all?"
    (
        re.compile(
            r"\b(not\s+enough\s+(?:info|information|detail)|incomplete\s+(?:answer|response)|"
            r"that'?s?\s+(?:all|it)\?|you\s+(?:barely|hardly)\s+(?:answered|helped)|"
            r"tell\s+me\s+more|i\s+need\s+more\s+details|"
            r"that\s+doesn'?t\s+(?:fully|completely)\s+answer|half\s+answer)\b",
            re.I,
        ),
        FailureMode.INCOMPLETE_RESPONSE,
    ),
    # ── WRONG_SCOPE ────────────────────────────────────────────────
    # "not about", "different topic", "off-topic", "irrelevant"
    (
        re.compile(
            r"\b(that'?s?\s+(?:not\s+(?:about|related\s+to)|off.?(?:topic|point))|"
            r"different\s+(?:topic|subject|issue|question|matter)|"
            r"not\s+(?:relevant|what\s+i\s+need|the\s+right\s+topic)|"
            r"you'?re?\s+(?:talking\s+about|addressing|discussing)\s+something\s+else|"
            r"completely\s+(?:unrelated|irrelevant|different))\b",
            re.I,
        ),
        FailureMode.WRONG_SCOPE,
    ),
]

# Additional catch-all patterns for dissatisfaction that map to
# the most likely failure mode (MISUNDERSTOOD_QUERY as default).
_DISSATISFACTION_PATTERNS: List[Tuple[re.Pattern, FailureMode]] = [
    (
        re.compile(
            r"\b(i'?m\s+(?:unhappy|dissatisfied|frustrated|annoyed|disappointed)|"
            r"this\s+is\s+(?:unacceptable|terrible|useless)|"
            r"not\s+(?:helpful|satisfactory|what\s+i\s+expected)|"
            r"try\s+again|let\s+me\s+rephrase|you\s+need\s+to\s+do\s+better)\b",
            re.I,
        ),
        FailureMode.MISUNDERSTOOD_QUERY,
    ),
]


# ── Strategy Adjustment Mapping ────────────────────────────────────
#
# Each failure mode maps to a prioritised list of corrective strategies.
# The first strategy is the primary adjustment; others are fallbacks.


_FAILURE_TO_STRATEGY: Dict[FailureMode, List[StrategyAdjustment]] = {
    FailureMode.MISUNDERSTOOD_QUERY: [
        StrategyAdjustment.SWITCH_TO_INVESTIGATIVE,
        StrategyAdjustment.FOCUS_SPECIFICS,
    ],
    FailureMode.INCORRECT_INFO: [
        StrategyAdjustment.SWITCH_TO_INVESTIGATIVE,
        StrategyAdjustment.ADD_MORE_DETAIL,
    ],
    FailureMode.BAD_TONE: [
        StrategyAdjustment.SWITCH_TO_EMPATHETIC,
        StrategyAdjustment.SIMPLIFY_RESPONSE,
    ],
    FailureMode.MISSED_CONTEXT: [
        StrategyAdjustment.ADD_MORE_DETAIL,
        StrategyAdjustment.PROVIDE_ALTERNATIVES,
    ],
    FailureMode.INCOMPLETE_RESPONSE: [
        StrategyAdjustment.ADD_MORE_DETAIL,
        StrategyAdjustment.FOCUS_SPECIFICS,
    ],
    FailureMode.WRONG_SCOPE: [
        StrategyAdjustment.SWITCH_TO_INVESTIGATIVE,
        StrategyAdjustment.FOCUS_SPECIFICS,
    ],
}


# ── Improved Response Templates ────────────────────────────────────
#
# For every (failure_mode, strategy) pair in _FAILURE_TO_STRATEGY,
# we provide at least two response templates.  Each template contains:
#   approach_description — internal description for the meta-trace
#   response_prefix      — empathetic opening that acknowledges the issue
#   response_body        — structured guidance using the adjusted strategy


_IMPROVED_RESPONSE_TEMPLATES: Dict[
    FailureMode,
    Dict[StrategyAdjustment, List[Dict[str, str]]],
] = {
    # ── MISUNDERSTOOD_QUERY ────────────────────────────────────────
    FailureMode.MISUNDERSTOOD_QUERY: {
        StrategyAdjustment.SWITCH_TO_INVESTIGATIVE: [
            {
                "approach_description": (
                    "Switch to investigative approach: ask clarifying "
                    "questions to re-align with customer intent."
                ),
                "response_prefix": (
                    "I apologize for the confusion. Let me make sure "
                    "I fully understand your question before proceeding."
                ),
                "response_body": (
                    "Could you clarify: are you asking about {topic}? "
                    "I want to ensure I address the right issue. "
                    "Once I understand your intent precisely, "
                    "I'll provide a focused and accurate response."
                ),
            },
            {
                "approach_description": (
                    "Investigative approach with paraphrase: repeat "
                    "back what was understood to confirm alignment."
                ),
                "response_prefix": (
                    "I'm sorry I missed the mark. Let me restate "
                    "what I understand so we can get on the same page."
                ),
                "response_body": (
                    "It sounds like you're trying to {topic}. "
                    "Is that correct? If so, here's what I can do: "
                    "I'll investigate {topic} specifically and walk "
                    "you through the resolution step by step."
                ),
            },
        ],
        StrategyAdjustment.FOCUS_SPECIFICS: [
            {
                "approach_description": (
                    "Focus on specifics: narrow the scope to the "
                    "exact question the customer is asking."
                ),
                "response_prefix": (
                    "I understand now — you need a direct answer "
                    "about a specific concern. Let me focus on that."
                ),
                "response_body": (
                    "Regarding {topic}, the key point is: "
                    "{guidance}. If there's a particular aspect "
                    "you'd like me to dive deeper into, "
                    "just let me know and I'll be specific."
                ),
            },
            {
                "approach_description": (
                    "Focus on specifics with step-by-step breakdown "
                    "of the customer's exact question."
                ),
                "response_prefix": (
                    "Thank you for clarifying. I'll address your "
                    "specific question directly."
                ),
                "response_body": (
                    "To answer your question about {topic}: "
                    "first, {step1}; second, {step2}; "
                    "finally, {step3}. Let me know if any of "
                    "these steps need further detail."
                ),
            },
        ],
    },
    # ── INCORRECT_INFO ─────────────────────────────────────────────
    FailureMode.INCORRECT_INFO: {
        StrategyAdjustment.SWITCH_TO_INVESTIGATIVE: [
            {
                "approach_description": (
                    "Investigate the discrepancy: acknowledge the "
                    "error and offer to verify facts from the source."
                ),
                "response_prefix": (
                    "I'm sorry for providing incorrect information. "
                    "Let me investigate this properly."
                ),
                "response_body": (
                    "You're right — my previous response was inaccurate. "
                    "Let me look into {topic} and verify the details "
                    "against your account records. "
                    "Could you share {verification_detail} so I can "
                    "confirm the correct information?"
                ),
            },
            {
                "approach_description": (
                    "Investigative with correction: clearly state the "
                    "correct information and explain the discrepancy."
                ),
                "response_prefix": (
                    "Thank you for catching that. I want to make sure "
                    "you have the correct information."
                ),
                "response_body": (
                    "After reviewing {topic}, the correct details are: "
                    "{corrected_info}. I apologize for the earlier "
                    "inaccuracy. Let me know if you need any further "
                    "clarification on this matter."
                ),
            },
        ],
        StrategyAdjustment.ADD_MORE_DETAIL: [
            {
                "approach_description": (
                    "Add more detail to correct the record: provide "
                    "comprehensive, verified information."
                ),
                "response_prefix": (
                    "I appreciate you pointing that out. Let me provide "
                    "you with the full and accurate details."
                ),
                "response_body": (
                    "Here is the complete information about {topic}: "
                    "{detailed_explanation}. If any of this doesn't "
                    "match what you're seeing on your end, please "
                    "let me know so I can investigate further."
                ),
            },
            {
                "approach_description": (
                    "Detailed corrective response with source "
                    "attribution for trust rebuilding."
                ),
                "response_prefix": (
                    "You're correct, and I want to set the record "
                    "straight with verified information."
                ),
                "response_body": (
                    "According to {source}, the accurate information "
                    "regarding {topic} is: {corrected_detail}. "
                    "I've verified this against current records. "
                    "Please accept my apologies for the confusion."
                ),
            },
        ],
    },
    # ── BAD_TONE ───────────────────────────────────────────────────
    FailureMode.BAD_TONE: {
        StrategyAdjustment.SWITCH_TO_EMPATHETIC: [
            {
                "approach_description": (
                    "Switch to empathetic tone: acknowledge the "
                    "customer's feelings and express genuine concern."
                ),
                "response_prefix": (
                    "I'm truly sorry if my previous response came "
                    "across poorly. Your experience matters to me."
                ),
                "response_body": (
                    "I understand how frustrating this must be. "
                    "Let me approach {topic} with fresh eyes and "
                    "make sure I'm providing the support you deserve. "
                    "How can I best help you right now?"
                ),
            },
            {
                "approach_description": (
                    "Empathetic approach with ownership: take "
                    "responsibility and pivot to helpful action."
                ),
                "response_prefix": (
                    "I hear you, and I apologise for not meeting "
                    "the standard of service you expect."
                ),
                "response_body": (
                    "Let me make this right. Regarding {topic}, "
                    "I want to help you resolve this. "
                    "I'll focus on what you actually need and "
                    "keep things clear and supportive throughout."
                ),
            },
        ],
        StrategyAdjustment.SIMPLIFY_RESPONSE: [
            {
                "approach_description": (
                    "Simplify the response: remove jargon and "
                    "provide a clear, concise, and warm answer."
                ),
                "response_prefix": (
                    "Let me start over and keep things simple and "
                    "straightforward for you."
                ),
                "response_body": (
                    "Here's the plain answer about {topic}: "
                    "{simple_answer}. That's really all there is "
                    "to it. If you need me to elaborate on any "
                    "part, just ask."
                ),
            },
            {
                "approach_description": (
                    "Simplified response with warm, conversational "
                    "tone to rebuild rapport."
                ),
                "response_prefix": (
                    "I appreciate your patience. Let me give you "
                    "a clear and simple answer this time."
                ),
                "response_body": (
                    "In short, for {topic}: {simple_answer}. "
                    "I hope that's clearer. I'm here to help, "
                    "so please don't hesitate to ask follow-up "
                    "questions."
                ),
            },
        ],
    },
    # ── MISSED_CONTEXT ─────────────────────────────────────────────
    FailureMode.MISSED_CONTEXT: {
        StrategyAdjustment.ADD_MORE_DETAIL: [
            {
                "approach_description": (
                    "Add context that was previously missed: cover "
                    "all relevant aspects of the customer's situation."
                ),
                "response_prefix": (
                    "Good catch — I should have included that "
                    "information. Let me fill in the gaps."
                ),
                "response_body": (
                    "In addition to what I mentioned earlier about "
                    "{topic}, there are important details I missed: "
                    "{missed_detail}. I apologise for the oversight. "
                    "Does this give you the full picture you need?"
                ),
            },
            {
                "approach_description": (
                    "Detailed response covering previously overlooked "
                    "factors with comprehensive context."
                ),
                "response_prefix": (
                    "You're absolutely right — I left out some "
                    "important information. Let me address that now."
                ),
                "response_body": (
                    "Looking at the full picture for {topic}, "
                    "there are several additional factors: "
                    "{additional_factors}. I should have covered "
                    "these from the start. Let me know if "
                    "there's anything else I'm still missing."
                ),
            },
        ],
        StrategyAdjustment.PROVIDE_ALTERNATIVES: [
            {
                "approach_description": (
                    "Provide alternatives that account for the "
                    "missed context and different scenarios."
                ),
                "response_prefix": (
                    "I see what I missed. Let me offer you some "
                    "alternative approaches that may better fit "
                    "your situation."
                ),
                "response_body": (
                    "Given the context around {topic}, here are "
                    "your options: {option_a}; or {option_b}; "
                    "alternatively, {option_c}. Each has different "
                    "trade-offs, so let me know your preference "
                    "and I'll elaborate."
                ),
            },
            {
                "approach_description": (
                    "Alternative solutions with pros/cons to give "
                    "the customer control over the approach."
                ),
                "response_prefix": (
                    "You make a valid point. Let me present the "
                    "full range of options for {topic}."
                ),
                "response_body": (
                    "Here are the alternatives for {topic}: "
                    "{alternative_with_details}. I recommend "
                    "{recommended_option} based on your situation, "
                    "but the choice is entirely yours."
                ),
            },
        ],
    },
    # ── INCOMPLETE_RESPONSE ────────────────────────────────────────
    FailureMode.INCOMPLETE_RESPONSE: {
        StrategyAdjustment.ADD_MORE_DETAIL: [
            {
                "approach_description": (
                    "Add comprehensive detail to the response: "
                    "expand on all aspects of the original answer."
                ),
                "response_prefix": (
                    "I understand you need more information. "
                    "Let me provide a thorough and detailed answer."
                ),
                "response_body": (
                    "Here's a complete breakdown for {topic}: "
                    "{detailed_breakdown}. I've included all the "
                    "key details this time. If any section needs "
                    "even more depth, just let me know."
                ),
            },
            {
                "approach_description": (
                    "Detailed expansion with step-by-step coverage "
                    "of the topic from start to finish."
                ),
                "response_prefix": (
                    "You're right — my previous answer was too brief. "
                    "Let me give you everything you need."
                ),
                "response_body": (
                    "For {topic}, here's the full picture: "
                    "step 1: {step1_detail}; step 2: {step2_detail}; "
                    "step 3: {step3_detail}. I've also included "
                    "additional context: {extra_context}. "
                    "I hope this covers everything."
                ),
            },
        ],
        StrategyAdjustment.FOCUS_SPECIFICS: [
            {
                "approach_description": (
                    "Focus on specific details the customer needs: "
                    "target the exact areas that were insufficient."
                ),
                "response_prefix": (
                    "I hear you — let me zero in on the specific "
                    "details that matter most."
                ),
                "response_body": (
                    "To specifically address {topic}: "
                    "the key details are {specific_details}. "
                    "If there's a particular aspect you'd like "
                    "me to expand on further, please point it out."
                ),
            },
            {
                "approach_description": (
                    "Specific-focused response with targeted "
                    "information and actionable next steps."
                ),
                "response_prefix": (
                    "Let me be more specific this time and give "
                    "you the details you're looking for."
                ),
                "response_body": (
                    "For {topic}, the specifics you need: "
                    "{specific_info}. As next steps: "
                    "{next_steps}. This should give you a "
                    "clear and complete picture."
                ),
            },
        ],
    },
    # ── WRONG_SCOPE ────────────────────────────────────────────────
    FailureMode.WRONG_SCOPE: {
        StrategyAdjustment.SWITCH_TO_INVESTIGATIVE: [
            {
                "approach_description": (
                    "Investigative pivot: redirect to the actual "
                    "topic the customer is asking about."
                ),
                "response_prefix": (
                    "I see — I was addressing the wrong topic. "
                    "Let me redirect to what you actually need."
                ),
                "response_body": (
                    "You're asking about {topic}, not what I "
                    "covered earlier. Let me look into this "
                    "specifically. To help me provide the most "
                    "relevant answer, could you share {detail}?"
                ),
            },
            {
                "approach_description": (
                    "Investigative approach with scope confirmation: "
                    "verify the correct topic before responding."
                ),
                "response_prefix": (
                    "My apologies for going off-topic. Let me "
                    "address your actual concern."
                ),
                "response_body": (
                    "To make sure I stay on track this time: "
                    "you need help with {topic}. Is that right? "
                    "I'll investigate {topic} and provide a "
                    "focused, on-point response."
                ),
            },
        ],
        StrategyAdjustment.FOCUS_SPECIFICS: [
            {
                "approach_description": (
                    "Focus on the correct scope: narrow down to "
                    "exactly what the customer needs."
                ),
                "response_prefix": (
                    "I understand — let me focus specifically "
                    "on what you're asking about."
                ),
                "response_body": (
                    "Addressing your actual question about {topic}: "
                    "{focused_answer}. I'll keep this focused on "
                    "exactly what you asked and avoid going "
                    "off on tangents."
                ),
            },
            {
                "approach_description": (
                    "Specific scope correction with boundary "
                    "acknowledgment to prevent future drift."
                ),
                "response_prefix": (
                    "You're right, I should have stayed on "
                    "topic. Let me correct that."
                ),
                "response_body": (
                    "Focusing specifically on {topic}: "
                    "{specific_answer}. I'll keep my response "
                    "targeted to this area only. Let me know "
                    "if this is the information you needed."
                ),
            },
        ],
    },
}


# ── Reflection Question Templates ──────────────────────────────────
#
# Used by the self-reflection step to produce structured analysis
# of what went wrong. Each failure mode has dedicated question prompts.


_REFLECTION_PROMPTS: Dict[FailureMode, List[str]] = {
    FailureMode.MISUNDERSTOOD_QUERY: [
        "Did I correctly identify the customer's core intent?",
        "Which part of the query did I interpret incorrectly?",
    ],
    FailureMode.INCORRECT_INFO: [
        "Was the information I provided verified against current records?",
        "What factual error did the customer identify?",
    ],
    FailureMode.BAD_TONE: [
        "Did my response language come across as dismissive or robotic?",
        "Was the level of empathy appropriate for the situation?",
    ],
    FailureMode.MISSED_CONTEXT: [
        "What contextual information did I overlook?",
        "Were there signals in the query I failed to address?",
    ],
    FailureMode.INCOMPLETE_RESPONSE: [
        "Did my response cover all aspects of the customer's question?",
        "What details should have been included but were omitted?",
    ],
    FailureMode.WRONG_SCOPE: [
        "Did I address the correct topic or problem area?",
        "What was the customer actually asking about?",
    ],
}


# ── Context Update Templates ───────────────────────────────────────
#
# Each failure mode produces a structured context update that can
# be stored for downstream techniques or future conversation turns.


_CONTEXT_UPDATE_TEMPLATES: Dict[FailureMode, str] = {
    FailureMode.MISUNDERSTOOD_QUERY: (
        "Customer intent was misidentified. Previous response addressed "
        "a different question than intended. Re-alignment required."
    ),
    FailureMode.INCORRECT_INFO: (
        "Previous response contained factually incorrect information. "
        "Customer flagged the error. Correction and verification needed."
    ),
    FailureMode.BAD_TONE: (
        "Previous response tone was inappropriate or insufficiently "
        "empathetic. Customer expressed dissatisfaction with delivery. "
        "Empathy and warmth adjustment required."
    ),
    FailureMode.MISSED_CONTEXT: (
        "Previous response omitted important contextual information "
        "that the customer explicitly needed. Coverage gap identified."
    ),
    FailureMode.INCOMPLETE_RESPONSE: (
        "Previous response was insufficient in depth or detail. "
        "Customer needs a more comprehensive answer."
    ),
    FailureMode.WRONG_SCOPE: (
        "Previous response addressed the wrong topic or scope. "
        "Customer's actual question is on a different subject. "
        "Topic redirection required."
    ),
}


# ── Confidence Impact Mapping ──────────────────────────────────────
#
# Each failure mode has an associated confidence impact value
# (negative) and a potential recovery boost when reflexion succeeds.


_CONFIDENCE_IMPACTS: Dict[FailureMode, Dict[str, float]] = {
    FailureMode.MISUNDERSTOOD_QUERY: {"penalty": -0.15, "recovery": 0.10},
    FailureMode.INCORRECT_INFO: {"penalty": -0.20, "recovery": 0.12},
    FailureMode.BAD_TONE: {"penalty": -0.10, "recovery": 0.08},
    FailureMode.MISSED_CONTEXT: {"penalty": -0.12, "recovery": 0.09},
    FailureMode.INCOMPLETE_RESPONSE: {"penalty": -0.08, "recovery": 0.07},
    FailureMode.WRONG_SCOPE: {"penalty": -0.18, "recovery": 0.11},
}


# ── Data Structures ────────────────────────────────────────────────


@dataclass(frozen=True)
class ReflexionConfig:
    """
    Immutable configuration for Reflexion processing (BC-001).

    Attributes:
        company_id: Tenant identifier for company isolation.
        max_reflection_depth: Maximum number of reflection cycles
            (prevents runaway self-correction loops).
        enable_meta_trace: Whether to build and return the
            meta-reasoning trace for learning.
    """

    company_id: str = ""
    max_reflection_depth: int = 3
    enable_meta_trace: bool = True


@dataclass
class ReflectionAnalysis:
    """
    Output of the self-reflection step.

    Attributes:
        failure_mode: Detected failure mode enum value.
        what_went_wrong: Human-readable description of the failure.
        strategy_changes: List of strategy adjustments to apply.
        context_update: Structured context update for downstream use.
        confidence_impact: Net confidence adjustment from this analysis.
    """

    failure_mode: str = ""
    what_went_wrong: str = ""
    strategy_changes: List[str] = field(default_factory=list)
    context_update: str = ""
    confidence_impact: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize analysis to dictionary."""
        return {
            "failure_mode": self.failure_mode,
            "what_went_wrong": self.what_went_wrong,
            "strategy_changes": list(self.strategy_changes),
            "context_update": self.context_update,
            "confidence_impact": round(self.confidence_impact, 4),
        }


@dataclass
class ReflexionResult:
    """
    Output of the full Reflexion pipeline.

    Attributes:
        reflection: The self-reflection analysis produced.
        improved_response: The corrected response text.
        meta_trace: Structured entries recording the reflection process.
        steps_applied: Names of pipeline steps that were executed.
        confidence_boost: Estimated net confidence change.
    """

    reflection: ReflectionAnalysis = field(default_factory=ReflectionAnalysis)
    improved_response: str = ""
    meta_trace: List[Dict[str, str]] = field(default_factory=list)
    steps_applied: List[str] = field(default_factory=list)
    confidence_boost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary for recording in state."""
        return {
            "reflection": self.reflection.to_dict(),
            "improved_response": self.improved_response,
            "meta_trace": list(self.meta_trace),
            "steps_applied": list(self.steps_applied),
            "confidence_boost": round(self.confidence_boost, 4),
        }


# ── Reflexion Processor ────────────────────────────────────────────


class ReflexionProcessor:
    """
    Deterministic Reflexion processor (F-147).

    Uses pattern matching and heuristic rules to simulate the
    self-correction reasoning process without any LLM calls.

    Pipeline:
      1. Failure Detection    — classify what went wrong from feedback
      2. Self-Reflection      — analyse root cause and determine strategy
      3. Strategy Adjustment  — select corrective approach
      4. Improved Generation  — produce corrected response
      5. Meta-Reasoning Trace — log process for continuous improvement
    """

    def __init__(
        self, config: Optional[ReflexionConfig] = None,
    ):
        self.config = config or ReflexionConfig()
        self._reflection_depth: int = 0

    # ── Step 1: Failure Detection ──────────────────────────────────

    async def detect_failure_mode(
        self,
        query: str,
        previous_response: str = "",
    ) -> FailureMode:
        """
        Detect the failure mode from the customer's latest query.

        Scans the query against compiled regex patterns to determine
        what category of failure the previous response falls into.

        Args:
            query: The customer's new query (feedback message).
            previous_response: The AI's previous response that was
                rejected or corrected (used for supplementary analysis).

        Returns:
            The detected FailureMode. Falls back to
            MISUNDERSTOOD_QUERY if no pattern matches but the
            query contains general dissatisfaction signals.
        """
        if not query or not query.strip():
            return FailureMode.MISUNDERSTOOD_QUERY

        query_lower = query.lower().strip()

        # Check specific failure mode patterns first
        for pattern, mode in _FAILURE_MODE_PATTERNS:
            if pattern.search(query_lower):
                logger.debug(
                    "reflexion_failure_mode_detected",
                    failure_mode=mode.value,
                    query_length=len(query),
                    company_id=self.config.company_id,
                )
                return mode

        # Check general dissatisfaction patterns as fallback
        for pattern, mode in _DISSATISFACTION_PATTERNS:
            if pattern.search(query_lower):
                logger.debug(
                    "reflexion_dissatisfaction_detected",
                    fallback_mode=mode.value,
                    query_length=len(query),
                    company_id=self.config.company_id,
                )
                return mode

        # If previous response exists and the query signals rejection,
        # default to MISUNDERSTOOD_QUERY as the safest assumption
        if previous_response and _has_rejection_signal(query_lower):
            logger.debug(
                "reflexion_default_failure_mode",
                default_mode=FailureMode.MISUNDERSTOOD_QUERY.value,
                company_id=self.config.company_id,
            )
            return FailureMode.MISUNDERSTOOD_QUERY

        return FailureMode.MISUNDERSTOOD_QUERY

    # ── Step 2: Self-Reflection ────────────────────────────────────

    async def reflect_on_failure(
        self,
        failure_mode: FailureMode,
        query: str,
        previous_response: str = "",
    ) -> ReflectionAnalysis:
        """
        Analyse the failure and produce a structured reflection.

        Determines what went wrong, which strategies to apply,
        what context update to store, and the confidence impact.

        Args:
            failure_mode: The detected failure category.
            query: The customer's feedback query.
            previous_response: The previous AI response that failed.

        Returns:
            A ReflectionAnalysis with the full self-reflection output.
        """
        if not failure_mode or not isinstance(failure_mode, FailureMode):
            return ReflectionAnalysis()

        # Determine what went wrong
        what_went_wrong = self._describe_failure(
            failure_mode, query, previous_response,
        )

        # Determine strategy changes
        strategies = _FAILURE_TO_STRATEGY.get(failure_mode, [])
        strategy_names = [s.value for s in strategies]

        # Determine context update
        context_update = _CONTEXT_UPDATE_TEMPLATES.get(
            failure_mode, "Unknown failure detected.",
        )

        # Calculate confidence impact (penalty for failure,
        # partial recovery for successful reflection)
        impacts = _CONFIDENCE_IMPACTS.get(
            failure_mode, {"penalty": -0.10, "recovery": 0.05},
        )
        confidence_impact = impacts["penalty"] + impacts["recovery"]

        logger.debug(
            "reflexion_self_reflection_complete",
            failure_mode=failure_mode.value,
            strategies=strategy_names,
            confidence_impact=round(confidence_impact, 4),
            company_id=self.config.company_id,
        )

        return ReflectionAnalysis(
            failure_mode=failure_mode.value,
            what_went_wrong=what_went_wrong,
            strategy_changes=strategy_names,
            context_update=context_update,
            confidence_impact=confidence_impact,
        )

    # ── Step 3: Improved Response Generation ───────────────────────

    async def generate_improved_response(
        self,
        reflection: ReflectionAnalysis,
        query: str,
    ) -> str:
        """
        Generate an improved response using the adjusted strategy.

        Selects a template based on (failure_mode, strategy) and
        fills it with context extracted from the query.

        Args:
            reflection: The reflection analysis containing the failure
                mode and strategy changes.
            query: The customer's feedback query.

        Returns:
            An improved response string.
        """
        if not reflection or not reflection.failure_mode:
            return ""

        # Parse failure mode back to enum
        try:
            failure_mode = FailureMode(reflection.failure_mode)
        except ValueError:
            logger.warning(
                "reflexion_invalid_failure_mode",
                failure_mode=reflection.failure_mode,
                company_id=self.config.company_id,
            )
            return ""

        # Get the primary strategy
        strategy_names = reflection.strategy_changes
        if not strategy_names:
            return ""

        try:
            primary_strategy = StrategyAdjustment(strategy_names[0])
        except ValueError:
            logger.warning(
                "reflexion_invalid_strategy",
                strategy=strategy_names[0],
                company_id=self.config.company_id,
            )
            return ""

        # Look up templates for this (failure_mode, strategy) pair
        mode_templates = _IMPROVED_RESPONSE_TEMPLATES.get(failure_mode, {})
        templates = mode_templates.get(primary_strategy, [])

        if not templates:
            logger.warning(
                "reflexion_no_templates_found",
                failure_mode=failure_mode.value,
                strategy=primary_strategy.value,
                company_id=self.config.company_id,
            )
            return ""

        # Select the best template (use first as primary)
        selected_template = templates[0]

        # Extract topic and contextual details from the query
        topic = self._extract_topic(query)
        guidance_parts = self._generate_guidance(query, failure_mode)

        # Build the improved response
        prefix = selected_template.get("response_prefix", "")
        body_template = selected_template.get("response_body", "")

        # Fill in the body template with available context
        body = body_template.format(
            topic=topic,
            guidance=guidance_parts.get("guidance", ""),
            step1=guidance_parts.get("step1", ""),
            step2=guidance_parts.get("step2", ""),
            step3=guidance_parts.get("step3", ""),
            step1_detail=guidance_parts.get("step1_detail", ""),
            step2_detail=guidance_parts.get("step2_detail", ""),
            step3_detail=guidance_parts.get("step3_detail", ""),
            verification_detail=guidance_parts.get("verification_detail", ""),
            corrected_info=guidance_parts.get("corrected_info", ""),
            detailed_explanation=guidance_parts.get("detailed_explanation", ""),
            source=guidance_parts.get("source", "our current records"),
            corrected_detail=guidance_parts.get("corrected_detail", ""),
            simple_answer=guidance_parts.get("simple_answer", topic),
            missed_detail=guidance_parts.get("missed_detail", ""),
            additional_factors=guidance_parts.get("additional_factors", ""),
            option_a=guidance_parts.get("option_a", ""),
            option_b=guidance_parts.get("option_b", ""),
            option_c=guidance_parts.get("option_c", ""),
            alternative_with_details=guidance_parts.get(
                "alternative_with_details", "",
            ),
            recommended_option=guidance_parts.get(
                "recommended_option", "",
            ),
            detailed_breakdown=guidance_parts.get(
                "detailed_breakdown", "",
            ),
            extra_context=guidance_parts.get("extra_context", ""),
            specific_details=guidance_parts.get("specific_details", ""),
            specific_info=guidance_parts.get("specific_info", ""),
            next_steps=guidance_parts.get("next_steps", ""),
            focused_answer=guidance_parts.get("focused_answer", topic),
            specific_answer=guidance_parts.get("specific_answer", topic),
        )

        improved_response = f"{prefix} {body}".strip()

        logger.debug(
            "reflexion_improved_response_generated",
            response_length=len(improved_response),
            failure_mode=failure_mode.value,
            strategy=primary_strategy.value,
            company_id=self.config.company_id,
        )

        return improved_response

    # ── Step 4: Meta-Reasoning Trace ───────────────────────────────

    async def build_meta_trace(
        self,
        reflection: ReflectionAnalysis,
        original_response: str,
        improved_response: str,
    ) -> List[Dict[str, str]]:
        """
        Build a structured meta-reasoning trace for learning.

        Each trace entry records one aspect of the reflection process
        for analysis in continuous improvement systems.

        Args:
            reflection: The reflection analysis.
            original_response: The previous (failed) response.
            improved_response: The new improved response.

        Returns:
            List of trace entry dictionaries.
        """
        trace: List[Dict[str, str]] = []

        # Entry 1: Failure detection
        trace.append({
            "step": "failure_detection",
            "failure_mode": reflection.failure_mode,
            "what_went_wrong": reflection.what_went_wrong,
            "timestamp": _utcnow_iso(),
        })

        # Entry 2: Reflection questions
        failure_mode = reflection.failure_mode
        reflection_questions = _REFLECTION_PROMPTS.get(
            FailureMode(failure_mode) if failure_mode else FailureMode.MISUNDERSTOOD_QUERY,
            [],
        )
        trace.append({
            "step": "self_reflection",
            "reflection_questions_asked": "; ".join(reflection_questions),
            "strategy_changes_applied": "; ".join(reflection.strategy_changes),
            "timestamp": _utcnow_iso(),
        })

        # Entry 3: Strategy adjustment
        trace.append({
            "step": "strategy_adjustment",
            "primary_strategy": reflection.strategy_changes[0]
            if reflection.strategy_changes else "none",
            "fallback_strategy": reflection.strategy_changes[1]
            if len(reflection.strategy_changes) > 1 else "none",
            "context_update": reflection.context_update,
            "timestamp": _utcnow_iso(),
        })

        # Entry 4: Response improvement
        trace.append({
            "step": "improved_generation",
            "original_response_length": str(len(original_response)),
            "improved_response_length": str(len(improved_response)),
            "length_change": str(len(improved_response) - len(original_response)),
            "confidence_impact": str(round(reflection.confidence_impact, 4)),
            "timestamp": _utcnow_iso(),
        })

        # Entry 5: Reflection depth tracking
        trace.append({
            "step": "reflection_depth",
            "current_depth": str(self._reflection_depth),
            "max_depth": str(self.config.max_reflection_depth),
            "depth_remaining": str(
                self.config.max_reflection_depth - self._reflection_depth,
            ),
            "timestamp": _utcnow_iso(),
        })

        logger.debug(
            "reflexion_meta_trace_built",
            trace_entries=len(trace),
            company_id=self.config.company_id,
        )

        return trace

    # ── Full Pipeline ──────────────────────────────────────────────

    async def process(
        self,
        query: str,
        previous_response: str = "",
        conversation_history: Optional[List[str]] = None,
    ) -> ReflexionResult:
        """
        Run the full 5-step Reflexion pipeline.

        The pipeline executes:
          1. Failure Detection    — classify failure from customer feedback
          2. Self-Reflection      — analyse root cause
          3. Strategy Adjustment  — select corrective approach
          4. Improved Generation  — produce corrected response
          5. Meta-Reasoning Trace — log for learning (optional)

        Supports recursive reflection up to max_reflection_depth when
        the generated response still shows quality concerns.

        Args:
            query: The customer's feedback query.
            previous_response: The AI's previous response that failed.
            conversation_history: Optional list of prior conversation
                turns for additional context.

        Returns:
            ReflexionResult with all pipeline outputs.
        """
        steps_applied: List[str] = []
        confidence_boost = 0.0
        meta_trace: List[Dict[str, str]] = []
        reflection = ReflectionAnalysis()
        improved_response = ""

        if not query or not query.strip():
            return ReflexionResult(
                steps_applied=["empty_input"],
                confidence_boost=0.0,
            )

        try:
            # Step 1: Failure Detection
            failure_mode = await self.detect_failure_mode(
                query, previous_response,
            )
            steps_applied.append("failure_detection")
            confidence_boost -= 0.02  # small cost for detection

            # Step 2: Self-Reflection
            reflection = await self.reflect_on_failure(
                failure_mode, query, previous_response,
            )
            if reflection.failure_mode:
                steps_applied.append("self_reflection")
            confidence_boost += reflection.confidence_impact

            # Step 3 + 4: Strategy Adjustment + Improved Generation
            improved_response = await self.generate_improved_response(
                reflection, query,
            )
            if improved_response:
                steps_applied.append("strategy_adjustment")
                steps_applied.append("improved_generation")
                confidence_boost += 0.05  # base boost for generating response

            # Step 5: Meta-Reasoning Trace
            if self.config.enable_meta_trace:
                meta_trace = await self.build_meta_trace(
                    reflection, previous_response or "", improved_response,
                )
                if meta_trace:
                    steps_applied.append("meta_trace")

            # Recursive reflection if depth allows and response
            # quality is still low (heuristic check)
            if (
                self._reflection_depth < self.config.max_reflection_depth - 1
                and improved_response
                and _response_needs_further_improvement(improved_response)
            ):
                self._reflection_depth += 1
                logger.debug(
                    "reflexion_recursive_reflection",
                    depth=self._reflection_depth,
                    company_id=self.config.company_id,
                )

                inner_result = await self.process(
                    query=query,
                    previous_response=improved_response,
                    conversation_history=conversation_history,
                )

                # Merge results: prefer inner (refined) response
                if inner_result.improved_response:
                    improved_response = inner_result.improved_response
                    steps_applied.append(
                        f"recursive_reflection_depth_{self._reflection_depth}",
                    )
                    confidence_boost += inner_result.confidence_boost * 0.5
                    if inner_result.meta_trace:
                        meta_trace.extend(inner_result.meta_trace)

        except Exception as exc:
            # BC-008: Never crash — return graceful fallback
            logger.warning(
                "reflexion_processing_error",
                error=str(exc),
                company_id=self.config.company_id,
            )
            return ReflexionResult(
                reflection=reflection,
                improved_response=improved_response,
                meta_trace=meta_trace,
                steps_applied=steps_applied + ["error_fallback"]
                if isinstance(steps_applied, list) else ["error_fallback"],
                confidence_boost=0.0,
            )

        # Cap confidence boost at reasonable maximum
        confidence_boost = min(confidence_boost, 0.25)

        return ReflexionResult(
            reflection=reflection,
            improved_response=improved_response,
            meta_trace=meta_trace,
            steps_applied=steps_applied,
            confidence_boost=round(confidence_boost, 4),
        )

    # ── Utility Methods ───────────────────────────────────────────

    @staticmethod
    def _describe_failure(
        failure_mode: FailureMode,
        query: str,
        previous_response: str,
    ) -> str:
        """
        Generate a human-readable description of the failure.

        Combines the failure mode context with evidence from the
        query and previous response.

        Args:
            failure_mode: The detected failure category.
            query: The customer's feedback query.
            previous_response: The previous AI response.

        Returns:
            Descriptive string explaining what went wrong.
        """
        descriptions: Dict[FailureMode, str] = {
            FailureMode.MISUNDERSTOOD_QUERY: (
                "The customer's query intent was misidentified. "
                "The response addressed a different question than "
                "what the customer was actually asking."
            ),
            FailureMode.INCORRECT_INFO: (
                "The previous response contained factually incorrect "
                "information. The customer flagged specific inaccuracies."
            ),
            FailureMode.BAD_TONE: (
                "The tone or delivery of the previous response was "
                "perceived as inappropriate, dismissive, or unhelpful."
            ),
            FailureMode.MISSED_CONTEXT: (
                "Important contextual information was overlooked in "
                "the previous response, leaving the customer's "
                "concern only partially addressed."
            ),
            FailureMode.INCOMPLETE_RESPONSE: (
                "The previous response lacked sufficient detail or "
                "depth to fully answer the customer's question."
            ),
            FailureMode.WRONG_SCOPE: (
                "The previous response addressed a different topic "
                "or scope than what the customer needed help with."
            ),
        }

        base = descriptions.get(
            failure_mode,
            "An unspecified failure occurred in the previous response.",
        )

        # Trim previous response for context (first 100 chars)
        prev_preview = ""
        if previous_response:
            prev_preview = previous_response[:100].strip()
            if len(previous_response) > 100:
                prev_preview += "..."

        parts = [base]
        if prev_preview:
            parts.append(f"Previous response preview: \"{prev_preview}\"")

        return " ".join(parts)

    @staticmethod
    def _extract_topic(query: str) -> str:
        """
        Extract the main topic from a customer query.

        Uses keyword extraction with stop-word filtering to identify
        the most significant terms in the query.

        Args:
            query: The customer query text.

        Returns:
            A topic string (up to 5 key words).
        """
        _STOP_WORDS: frozenset = frozenset({
            "i", "me", "my", "we", "you", "your", "it", "its",
            "is", "am", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might",
            "shall", "can", "to", "of", "in", "for", "on",
            "with", "at", "by", "from", "as", "into",
            "the", "a", "an", "and", "or", "but", "if",
            "not", "no", "this", "that", "these", "those",
            "what", "how", "when", "where", "why", "who",
            "which", "about", "up", "out", "just", "so",
            "than", "too", "very", "also", "then", "here",
            "there", "all", "each", "every", "both", "few",
            "more", "most", "other", "some", "such", "only",
            "same", "don", "t", "s", "ve", "ll", "re", "d",
            "m", "didn", "doesn", "wasn", "weren", "won",
            "wouldn", "couldn", "shouldn", "isn", "aren",
            "haven", "hasn", "hadn",
        })

        words = re.findall(r"\b[a-zA-Z]{3,}\b", query.lower())
        filtered = [w for w in words if w not in _STOP_WORDS]

        # Deduplicate while preserving order
        seen: set = set()
        unique: List[str] = []
        for word in filtered:
            if word not in seen:
                seen.add(word)
                unique.append(word)

        if not unique:
            return "your concern"

        topic = " ".join(unique[:5])
        return topic

    @staticmethod
    def _generate_guidance(
        query: str,
        failure_mode: FailureMode,
    ) -> Dict[str, str]:
        """
        Generate contextual guidance fields for template filling.

        Produces placeholder-safe guidance text that can be used
        in response templates without causing KeyError on format().

        Args:
            query: The customer's feedback query.
            failure_mode: The detected failure category.

        Returns:
            Dictionary of guidance fields for template formatting.
        """
        topic = ReflexionProcessor._extract_topic(query)

        base: Dict[str, str] = {
            "topic": topic,
            "guidance": f"the details regarding {topic}",
            "step1": "review the relevant information",
            "step2": "identify the specific issue",
            "step3": "provide the resolution",
            "step1_detail": "First, I'll review the current information in our system to understand your situation.",
            "step2_detail": "Second, I'll identify the specific issue or discrepancy that needs to be addressed.",
            "step3_detail": "Third, I'll provide a clear resolution or next steps for you to follow.",
            "verification_detail": "any relevant order or transaction details",
            "corrected_info": "the updated and verified information",
            "detailed_explanation": (
                "here is the complete information covering all "
                "relevant aspects of your inquiry"
            ),
            "source": "our updated records",
            "corrected_detail": "the verified and accurate information",
            "simple_answer": topic,
            "missed_detail": "the additional context that was previously omitted",
            "additional_factors": "several additional considerations that should be taken into account",
            "option_a": "Option A — proceed with the standard approach",
            "option_b": "Option B — try an alternative method",
            "option_c": "Option C — escalate for specialised assistance",
            "alternative_with_details": (
                f"Option A: the standard resolution for {topic}; "
                f"Option B: an alternative approach that may be faster; "
                f"Option C: escalate to a specialist if needed"
            ),
            "recommended_option": "Option A, as it follows the standard process",
            "detailed_breakdown": (
                "here is the complete breakdown of all relevant "
                "details, covering every aspect of your question"
            ),
            "extra_context": "additional background information that may be helpful",
            "specific_details": "the precise details relevant to your situation",
            "specific_info": "the targeted information you need",
            "next_steps": "here are the clear next steps you can take",
            "focused_answer": f"the specific answer regarding {topic}",
            "specific_answer": f"the direct answer to your question about {topic}",
        }

        # Mode-specific enrichment
        if failure_mode == FailureMode.INCORRECT_INFO:
            base["guidance"] = (
                "the corrected information verified against your records"
            )
            base["corrected_info"] = (
                "the accurate, verified information from our system"
            )
        elif failure_mode == FailureMode.BAD_TONE:
            base["simple_answer"] = (
                "here is the clear and straightforward answer"
            )
        elif failure_mode == FailureMode.WRONG_SCOPE:
            base["focused_answer"] = (
                f"the answer focused on {topic} specifically"
            )

        return base


# ── Reflexion Node (LangGraph compatible) ─────────────────────────


class ReflexionNode(BaseTechniqueNode):
    """
    F-147: Reflexion — Tier 3 Premium.

    Extends BaseTechniqueNode for integration into the LangGraph
    pipeline (F-060).

    Activation triggers:
      - previous_response_status in ("rejected", "corrected"), OR
      - customer_tier == "vip" (premium feature)
    """

    def __init__(
        self, config: Optional[ReflexionConfig] = None,
    ):
        self._config = config or ReflexionConfig()
        self._processor = ReflexionProcessor(config=self._config)
        # Call parent init after config is set (reads TECHNIQUE_REGISTRY)
        super().__init__()

    @property
    def technique_id(self) -> TechniqueID:
        """Return the TechniqueID for this node."""
        return TechniqueID.REFLEXION

    async def should_activate(self, state: ConversationState) -> bool:
        """
        Check if Reflexion should activate.

        Triggers when:
          - A previous response was rejected or corrected, OR
          - The customer is a VIP (premium technique activation).
        """
        return (
            state.signals.previous_response_status in ("rejected", "corrected")
            or state.signals.customer_tier == "vip"
        )

    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the Reflexion pipeline.

        Implements the 5-step self-correction process:
          1. Failure Detection
          2. Self-Reflection
          3. Strategy Adjustment
          4. Improved Generation
          5. Meta-Reasoning Trace

        Retrieves the previous response from state.response_parts
        or state.reflexion_trace. Records the result, updates
        confidence, and stores meta_trace for continuous learning.

        On error (BC-008), returns the original state unchanged.
        """
        original_state = state

        try:
            # Retrieve previous response for context
            previous_response = ""
            if state.response_parts:
                previous_response = state.response_parts[-1]

            # Build conversation history from response_parts
            conversation_history = list(state.response_parts)

            # Run the Reflexion pipeline
            result = await self._processor.process(
                query=state.query,
                previous_response=previous_response,
                conversation_history=conversation_history,
            )

            # Record result in state
            self.record_result(state, result.to_dict())

            # Update confidence score in signals
            new_confidence = min(
                state.signals.confidence_score + result.confidence_boost,
                1.0,
            )
            state.signals.confidence_score = max(new_confidence, 0.0)

            # If we have an improved response, replace the last
            # response part or append it
            if result.improved_response:
                if (
                    state.response_parts
                    and state.signals.previous_response_status
                    in ("rejected", "corrected")
                ):
                    # Replace the failed response
                    state.response_parts[-1] = result.improved_response
                else:
                    # Append as a new improved response
                    state.response_parts.append(result.improved_response)

            # Store meta trace in state for learning
            if result.meta_trace:
                state.reflexion_trace = {
                    "failure_mode": result.reflection.failure_mode,
                    "steps_applied": result.steps_applied,
                    "confidence_boost": result.confidence_boost,
                    "meta_trace": result.meta_trace,
                    "context_update": result.reflection.context_update,
                }

            logger.info(
                "reflexion_executed",
                failure_mode=result.reflection.failure_mode,
                steps_applied=result.steps_applied,
                confidence_boost=result.confidence_boost,
                meta_trace_entries=len(result.meta_trace),
                company_id=self._config.company_id,
            )

            return state

        except Exception as exc:
            # BC-008: Never crash — return original state
            logger.warning(
                "reflexion_execute_error",
                error=str(exc),
                company_id=self._config.company_id,
            )
            return original_state


# ── Module-Level Helpers ───────────────────────────────────────────


def _has_rejection_signal(query: str) -> bool:
    """
    Check if a query contains general rejection signals.

    Uses a lightweight heuristic to detect implicit rejection
    when no specific failure mode pattern matched.

    Args:
        query: Lowercased query text.

    Returns:
        True if rejection signals are detected.
    """
    rejection_markers = [
        "no", "wrong", "bad", "not", "don't", "doesn't",
        "didn't", "isn't", "aren't", "wasn't", "weren't",
        "shouldn't", "wouldn't", "couldn't", "won't",
        "fail", "error", "mistake", "fix", "correct",
        "again", "redo", "retry", "re-do", "start over",
    ]
    query_lower = query.lower()
    return any(marker in query_lower for marker in rejection_markers)


def _response_needs_further_improvement(response: str) -> bool:
    """
    Heuristic check for whether a generated response needs
    another round of reflection.

    Evaluates based on:
      - Response length (too short may be insufficient)
      - Presence of hedge words (may indicate uncertainty)
      - Presence of negative absolutes

    Args:
        response: The generated improved response text.

    Returns:
        True if further improvement is recommended.
    """
    if not response:
        return True

    # Too short responses may need refinement
    if len(response) < 80:
        return True

    # Check for excessive hedge words (uncertainty indicators)
    hedge_words = [
        "i think", "maybe", "perhaps", "possibly", "i believe",
        "it seems", "i'm not sure", "i guess",
    ]
    response_lower = response.lower()
    hedge_count = sum(1 for w in hedge_words if w in response_lower)
    if hedge_count >= 3:
        return True

    # Check for negative absolutes that suggest the response
    # is still problematic
    negative_absolutes = re.findall(
        r"\b(never|always|impossible|cannot ever|no way|nothing can)\b",
        response_lower,
    )
    if len(negative_absolutes) >= 2:
        return True

    return False


def _utcnow_iso() -> str:
    """Return the current UTC time as an ISO-formatted string."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
