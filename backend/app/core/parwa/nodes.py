"""
Pro Parwa Pipeline Nodes — 15 agent-nodes for the LangGraph pipeline.

Pipeline: pii_check -> empathy_check -> emergency_check -> gsd_state
        -> classify -> extract_signals -> technique_select
        -> reasoning_chain -> context_enrich -> generate
        -> crp_compress -> clara_quality_gate -> quality_retry
        -> confidence_assess -> format -> END

Each node:
  - Takes ParwaGraphState dict as input
  - Returns a dict with ONLY the fields it modified (LangGraph merges these)
  - Is wrapped in try/except (BC-008: never crash)
  - Appends to audit_log and errors using reducer pattern
  - Tracks timing in step_outputs

Connected Frameworks (Tier 1 + Tier 2):
  Tier 1 (Always Active):
    - CLARA (Concise Logical Adaptive Response Architecture) — Quality gate
    - CRP (Concise Response Protocol) — Token waste elimination
    - GSD (Guided Support Dialogue) — State machine tracking
    - Smart Router (F-054) — Model tier selection (Medium for Pro)
    - Technique Router (BC-013) — Technique selection (Tier 1+2)
    - Confidence Scoring (F-059) — Response confidence assessment

  Tier 2 (Conditional — triggered by signal-based rules):
    - CoT (Chain of Thought) — Step-by-step reasoning
    - ReAct — Reasoning + acting with tool calls
    - Reverse Thinking — Inversion-based reasoning
    - Step-Back — Broader context seeking
    - ThoT (Thread of Thought) — Multi-turn continuity

Pro vs Mini differences in nodes:
  - classify_node: Uses AI classification (not just keyword)
  - technique_select_node: NEW — Selects Tier 1+2 techniques based on signals
  - reasoning_chain_node: NEW — Executes CoT/ReAct/Reverse/Step-Back/ThoT
  - context_enrich_node: NEW — Enriches context with reasoning output
  - clara_quality_gate_node: Higher threshold (85 vs 60), advanced checks
  - quality_retry_node: NEW — Retry generation if quality gate fails (max 1)
  - confidence_assess_node: NEW — Deep confidence assessment
  - generate_node: Technique-guided generation with reasoning context

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.core.parwa_graph_state import (
    ParwaGraphState,
    append_audit_entry,
)
from app.core.pii_redaction_engine import PIIDetector
from app.core.classification_engine import ClassificationEngine, KeywordClassifier
from app.core.response_formatters import (
    FormattingContext,
    FormatterRegistry,
    create_default_registry,
)
from app.core.industry_enum import get_industry_prompt, get_industry_tone
from app.logger import get_logger

logger = get_logger("parwa_nodes")


# ══════════════════════════════════════════════════════════════════
# SHARED RESOURCES (lazy-initialized singletons)
# ══════════════════════════════════════════════════════════════════

_pii_detector: Optional[PIIDetector] = None
_keyword_classifier: Optional[KeywordClassifier] = None
_classification_engine: Optional[ClassificationEngine] = None
_formatter_registry: Optional[FormatterRegistry] = None
_gsd_manager: Optional[Any] = None
_technique_router: Optional[Any] = None
_smart_router: Optional[Any] = None
_confidence_engine: Optional[Any] = None


def _get_pii_detector() -> PIIDetector:
    """Get or create the PII detector singleton."""
    global _pii_detector
    if _pii_detector is None:
        _pii_detector = PIIDetector()
    return _pii_detector


def _get_keyword_classifier() -> KeywordClassifier:
    """Get or create the keyword classifier singleton."""
    global _keyword_classifier
    if _keyword_classifier is None:
        _keyword_classifier = KeywordClassifier()
    return _keyword_classifier


def _get_classification_engine() -> ClassificationEngine:
    """Get or create the classification engine singleton (Pro uses AI classification)."""
    global _classification_engine
    if _classification_engine is None:
        try:
            _classification_engine = ClassificationEngine()
        except Exception:
            logger.warning("classification_engine_init_failed — falling back to keyword")
    return _classification_engine


def _get_formatter_registry() -> FormatterRegistry:
    """Get or create the formatter registry singleton."""
    global _formatter_registry
    if _formatter_registry is None:
        _formatter_registry = create_default_registry()
    return _formatter_registry


def _get_gsd_manager() -> Any:
    """Get or create the SharedGSDManager singleton."""
    global _gsd_manager
    if _gsd_manager is None:
        try:
            from app.core.shared_gsd import SharedGSDManager
            _gsd_manager = SharedGSDManager()
        except Exception:
            logger.warning("gsd_manager_import_failed")
    return _gsd_manager


def _get_technique_router() -> Any:
    """Get or create the TechniqueRouter singleton (Pro: Medium tier, Tier 1+2)."""
    global _technique_router
    if _technique_router is None:
        try:
            from app.core.technique_router import (
                TechniqueRouter,
                TechniqueID,
                TechniqueTier,
            )
            # Pro enables Tier 1 + Tier 2 techniques
            enabled = {
                # Tier 1
                TechniqueID.CLARA,
                TechniqueID.CRP,
                TechniqueID.GSD,
                # Tier 2
                TechniqueID.CHAIN_OF_THOUGHT,
                TechniqueID.REVERSE_THINKING,
                TechniqueID.REACT,
                TechniqueID.STEP_BACK,
                TechniqueID.THREAD_OF_THOUGHT,
            }
            _technique_router = TechniqueRouter(
                model_tier="medium",
                enabled_techniques=enabled,
            )
        except Exception:
            logger.warning("technique_router_import_failed")
    return _technique_router


def _get_smart_router() -> Any:
    """Get or create the SmartRouter singleton."""
    global _smart_router
    if _smart_router is None:
        try:
            from app.core.smart_router import SmartRouter
            _smart_router = SmartRouter()
        except Exception:
            logger.warning("smart_router_import_failed")
    return _smart_router


def _get_confidence_engine() -> Any:
    """Get or create the ConfidenceScoringEngine singleton."""
    global _confidence_engine
    if _confidence_engine is None:
        try:
            from app.core.confidence_scoring_engine import ConfidenceScoringEngine
            _confidence_engine = ConfidenceScoringEngine()
        except Exception:
            logger.warning("confidence_engine_import_failed")
    return _confidence_engine


# ══════════════════════════════════════════════════════════════════
# EMERGENCY KEYWORD PATTERNS (FREE — no LLM)
# ══════════════════════════════════════════════════════════════════

EMERGENCY_PATTERNS: Dict[str, List[str]] = {
    "legal_threat": [
        "lawsuit", "sue", "lawyer", "attorney", "legal action",
        "take legal", "legal counsel", "court", "litigation",
        "subpoena", "deposition", "class action",
    ],
    "safety": [
        "self-harm", "suicide", "kill myself", "end my life",
        "hurt myself", "dangerous", "unsafe", "threat",
        "violence", "abuse", "domestic violence", "harm myself",
        "want to die", "don't want to live",
    ],
    "compliance": [
        "gdpr", "regulatory", "compliance violation", "data breach",
        "privacy violation", "hipaa", "pci compliance",
        "regulatory fine", "government investigation",
    ],
    "media": [
        "press", "media", "reporter", "journalist", "news",
        "social media", "twitter", "going public", "viral",
    ],
}


def _check_emergency_keywords(text: str) -> Dict[str, Any]:
    """Check text for emergency signals using keyword matching (FREE)."""
    text_lower = text.lower()
    matched: Dict[str, List[str]] = {}

    for emergency_type, keywords in EMERGENCY_PATTERNS.items():
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text_lower):
                matched.setdefault(emergency_type, []).append(keyword)

    if matched:
        priority_order = ["safety", "legal_threat", "compliance", "media"]
        for etype in priority_order:
            if etype in matched:
                return {
                    "emergency_flag": True,
                    "emergency_type": etype,
                    "matched_keywords": matched,
                }

    return {
        "emergency_flag": False,
        "emergency_type": "",
        "matched_keywords": {},
    }


# ══════════════════════════════════════════════════════════════════
# EMPATHY KEYWORD PATTERNS (FALLBACK — used when LLM fails)
# ══════════════════════════════════════════════════════════════════

EMPATHY_PATTERNS: Dict[str, List[str]] = {
    "frustrated": [
        "frustrated", "annoyed", "irritated", "fed up",
        "can't stand", "sick of", "had enough",
    ],
    "angry": [
        "angry", "furious", "outraged", "mad", "livid",
        "unacceptable", "ridiculous", "appalling",
    ],
    "sad": [
        "sad", "disappointed", "devastated", "heartbroken",
        "upset", "crying", "depressed", "hopeless",
    ],
    "urgent": [
        "urgent", "asap", "emergency", "immediately",
        "right now", "critical", "deadline",
    ],
    "confused": [
        "confused", "don't understand", "unclear",
        "lost", "help me", "can't figure out",
    ],
}


def _keyword_empathy_check(text: str) -> Dict[str, Any]:
    """Simple keyword-based empathy/sentiment analysis (FREE fallback)."""
    text_lower = text.lower()
    flags: List[str] = []
    total_matches = 0

    for flag_name, keywords in EMPATHY_PATTERNS.items():
        for keyword in keywords:
            if " " in keyword:
                if keyword in text_lower:
                    flags.append(flag_name)
                    total_matches += 1
                    break
            else:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, text_lower):
                    flags.append(flag_name)
                    total_matches += 1
                    break

    if not flags:
        empathy_score = 0.7
    elif len(flags) == 1:
        empathy_score = 0.4
    elif len(flags) == 2:
        empathy_score = 0.25
    else:
        empathy_score = 0.1

    return {
        "empathy_score": empathy_score,
        "empathy_flags": flags,
    }


# ══════════════════════════════════════════════════════════════════
# TEMPLATE RESPONSES (FALLBACK — used when LLM fails)
# ══════════════════════════════════════════════════════════════════

TEMPLATE_RESPONSES: Dict[str, str] = {
    "refund": (
        "Thank you for contacting us about your refund request. "
        "We understand this is important to you and we want to help. "
        "Let me walk you through the refund process. First, I'll verify your "
        "order details. Then our team will review your request and process the "
        "refund within 24-48 hours. You'll receive email confirmation once it's "
        "initiated. Your ticket {ticket_id} has been created for tracking."
    ),
    "technical": (
        "Thank you for reporting this technical issue. I understand how "
        "frustrating this must be. Let me help you step by step. First, "
        "can you tell me when this issue started? Our technical team has been "
        "notified and will investigate. In the meantime, try clearing your "
        "cache and restarting — this resolves 60% of similar issues. "
        "We'll provide an update as soon as possible."
    ),
    "billing": (
        "Thank you for your billing inquiry. I understand billing concerns "
        "need careful attention. Let me review your account details. "
        "Our billing team will analyze the charges and respond within 24 hours. "
        "If there's been an error, we'll correct it immediately and adjust "
        "your next invoice. Please don't hesitate to ask if you need immediate "
        "assistance."
    ),
    "complaint": (
        "We sincerely apologize for your experience. Your feedback is "
        "invaluable to us and we take this very seriously. Here's what "
        "happens next: a senior team member will personally review your "
        "complaint within 4 hours. They'll reach out to discuss a resolution. "
        "We're committed to making this right for you."
    ),
    "cancellation": (
        "We're sorry to see you go, and we want to understand why. "
        "Your cancellation request has been received. Before we proceed, "
        "is there anything we could do differently? We offer several "
        "alternatives including plan adjustments, temporary suspension, or "
        "upgraded features at no extra cost. A retention specialist will "
        "contact you within 24 hours."
    ),
    "shipping": (
        "Thank you for your shipping inquiry. I'll help you track your "
        "order right away. Let me pull up the latest tracking information. "
        "Our logistics team monitors all shipments actively. If there's any "
        "delay, we'll proactively reach out with an updated ETA. "
        "You should receive a status update within the hour."
    ),
    "account": (
        "Thank you for your account-related inquiry. For your security, "
        "we'll need to verify some details before making changes. "
        "I can help with password resets, email updates, and security "
        "settings. Our support team is standing by to assist you. "
        "What specifically would you like to change?"
    ),
    "general": (
        "Thank you for reaching out to us. We've received your message "
        "and I'm here to help. Could you provide a bit more detail about "
        "what you need? This will help me direct you to the right team "
        "member or resolve it directly. If your matter is urgent, please "
        "let me know and we'll prioritize it."
    ),
}

EMERGENCY_RESPONSE_TEMPLATE = (
    "Your message has been flagged for priority handling. "
    "A senior team member will contact you directly within the hour. "
    "If this is an emergency requiring immediate attention, "
    "please call our emergency hotline. "
    "Your reference number is {ticket_id}."
)


# ══════════════════════════════════════════════════════════════════
# CRP FILLER PHRASES — Token waste to eliminate (F-140)
# ══════════════════════════════════════════════════════════════════

CRP_FILLER_PHRASES: List[str] = [
    "I'd be happy to help you with that.",
    "I'd be happy to help with that.",
    "I would be happy to help you with that.",
    "Certainly, I can assist.",
    "Certainly, I can assist you with that.",
    "Let me look into that for you.",
    "I understand your concern.",
    "I understand your frustration.",
    "Thank you for reaching out to us.",
    "Please don't hesitate to reach out",
    "If you have any further questions",
    "If you need anything else",
    "Feel free to reach out",
    "Please let me know if you need anything else.",
    "Is there anything else I can help you with?",
]


def _apply_crp_compression(text: str) -> Dict[str, Any]:
    """Apply CRP (Concise Response Protocol) compression.

    Target: 30-40% token reduction with >95% information retention.
    """
    if not text:
        return {
            "compressed_text": text,
            "tokens_removed": 0,
            "compression_ratio": 1.0,
            "phrases_removed": [],
        }

    original_tokens = len(text.split())
    compressed = text
    phrases_removed: List[str] = []

    # Step 1: Remove filler phrases
    for phrase in CRP_FILLER_PHRASES:
        if phrase.lower() in compressed.lower():
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            compressed = pattern.sub("", compressed)
            phrases_removed.append(phrase)

    # Step 2: Clean up double spaces and orphaned punctuation
    compressed = re.sub(r'\s{2,}', ' ', compressed)
    compressed = re.sub(r'\.\s*\.', '.', compressed)
    compressed = re.sub(r'^\s+|\s+$', '', compressed, flags=re.MULTILINE)
    compressed = compressed.strip()

    # Step 3: Remove redundant "Thank you"
    thank_you_count = len(re.findall(r'\bthank you\b', compressed, re.IGNORECASE))
    if thank_you_count > 1:
        first = True
        parts = re.split(r'(\bThank you\b|\bthank you\b)', compressed, flags=re.IGNORECASE)
        result_parts = []
        for part in parts:
            if re.match(r'\bthank you\b', part, re.IGNORECASE):
                if first:
                    result_parts.append(part)
                    first = False
                else:
                    phrases_removed.append("duplicate thank you")
            else:
                result_parts.append(part)
        compressed = "".join(result_parts)

    final_tokens = len(compressed.split())
    tokens_removed = max(0, original_tokens - final_tokens)
    compression_ratio = final_tokens / original_tokens if original_tokens > 0 else 1.0

    return {
        "compressed_text": compressed,
        "tokens_removed": tokens_removed,
        "compression_ratio": round(compression_ratio, 3),
        "phrases_removed": phrases_removed,
    }


# ══════════════════════════════════════════════════════════════════
# CLARA QUALITY GATE — Enhanced for Pro (threshold 85)
# ══════════════════════════════════════════════════════════════════

def _run_clara_quality_gate(
    response: str,
    query: str,
    industry: str,
    tone: str,
    empathy_score: float,
    reasoning_output: str = "",
    technique_used: str = "",
) -> Dict[str, Any]:
    """Run the CLARA quality gate pipeline on a generated response.

    CLARA = Concise Logical Adaptive Response Architecture.
    Validates: Structure -> Logic -> Brand -> Tone -> Delivery -> Reasoning Alignment

    Pro version: Higher threshold (85 vs Mini's 60), additional reasoning check.
    Uses keyword/rule-based checks (FREE, no LLM) with enhanced criteria.
    """
    if not response:
        return {
            "passed": False,
            "score": 0.0,
            "issues": ["empty_response"],
            "adjusted_response": response,
            "checks": {},
        }

    checks: Dict[str, Dict[str, Any]] = {}
    issues: List[str] = []
    score = 100.0

    # Check 1: STRUCTURE — Does response have logical structure?
    has_greeting = bool(re.search(
        r'\b(thank you|hello|hi|dear|greetings)\b',
        response, re.IGNORECASE,
    ))
    has_acknowledgment = bool(re.search(
        r'\b(understand|sorry|apologize|acknowledge|we see|I see)\b',
        response, re.IGNORECASE,
    ))
    has_action = bool(re.search(
        r'\b(will|can|let me|our team|we\'ll|we will|I\'ll|I will)\b',
        response, re.IGNORECASE,
    ))
    has_steps = bool(re.search(
        r'\b(first|then|next|finally|step \d)\b',
        response, re.IGNORECASE,
    ))

    structure_score = 0
    if has_greeting or has_acknowledgment:
        structure_score += 30
    if has_action:
        structure_score += 30
    if has_steps:
        structure_score += 20  # Pro bonus: step-by-step structure
    if len(response.split('.')) >= 3:  # Pro expects more sentences
        structure_score += 20

    if structure_score < 50:
        issues.append("poor_structure")
        score -= 20

    checks["structure"] = {
        "score": structure_score,
        "has_greeting": has_greeting,
        "has_acknowledgment": has_acknowledgment,
        "has_action": has_action,
        "has_steps": has_steps,
    }

    # Check 2: LOGIC — Does response address the query topic?
    query_tokens = set(re.findall(r'\b\w{4,}\b', query.lower()))
    response_tokens = set(re.findall(r'\b\w{4,}\b', response.lower()))
    stop_words = {
        "that", "this", "with", "have", "will", "been", "from",
        "they", "would", "could", "should", "there", "their",
        "about", "which", "when", "where", "your", "please",
    }
    query_content = query_tokens - stop_words
    response_content = response_tokens - stop_words
    overlap = query_content & response_content if query_content else set()
    logic_score = int(len(overlap) / max(len(query_content), 1) * 100)

    if logic_score < 30:
        issues.append("off_topic")
        score -= 25
    elif logic_score < 50:
        # Pro: partial topic coverage gets a warning
        issues.append("partial_topic_coverage")
        score -= 10

    checks["logic"] = {
        "score": logic_score,
        "overlap_count": len(overlap),
        "query_content_count": len(query_content),
    }

    # Check 3: BRAND — Is the tone appropriate for the industry?
    inappropriate_words = {
        "dude", "bro", "lol", "lmao", "rofl", "idk", "tbh",
        "ngl", "smh", "bruh", "yolo",
    }
    response_lower = response.lower()
    brand_violations = [w for w in inappropriate_words if w in response_lower.split()]
    brand_score = 100 - (len(brand_violations) * 25)

    if brand_violations:
        issues.append("brand_violation")
        score -= len(brand_violations) * 15

    checks["brand"] = {
        "score": max(0, brand_score),
        "violations": brand_violations,
    }

    # Check 4: TONE — Is the empathy level appropriate?
    tone_score = 80
    if empathy_score < 0.3 and not has_acknowledgment:
        tone_score = 30
        issues.append("insufficient_empathy")
        score -= 20
    elif empathy_score < 0.5 and not has_acknowledgment:
        # Pro: moderate distress needs acknowledgment too
        tone_score = 55
        issues.append("moderate_empathy_gap")
        score -= 10
    elif empathy_score > 0.6:
        tone_score = 90

    checks["tone"] = {
        "score": tone_score,
        "empathy_score": empathy_score,
        "has_acknowledgment": has_acknowledgment,
    }

    # Check 5: DELIVERY — Is the response complete and deliverable?
    delivery_score = 80
    if len(response.strip()) < 30:
        delivery_score = 25
        issues.append("response_too_short")
        score -= 25
    elif len(response.strip()) < 50:
        delivery_score = 50
        issues.append("response_brief")
        score -= 10
    elif len(response.strip()) > 1500:
        delivery_score = 70

    # Check for placeholder text
    placeholders = re.findall(r'\{+\w+\}+', response)
    if placeholders:
        issues.append("unresolved_placeholders")
        score -= 10
        delivery_score -= 20

    checks["delivery"] = {
        "score": delivery_score,
        "response_length": len(response),
        "has_placeholders": bool(placeholders),
    }

    # Check 6: REASONING ALIGNMENT (Pro-specific)
    # Does the response incorporate the reasoning from the technique?
    reasoning_score = 70  # Default for Pro
    if reasoning_output and technique_used:
        # Check if reasoning is reflected in the response
        reasoning_tokens = set(re.findall(r'\b\w{4,}\b', reasoning_output.lower()))
        response_tokens_for_reasoning = set(re.findall(r'\b\w{4,}\b', response.lower()))
        reasoning_overlap = reasoning_tokens & response_tokens_for_reasoning
        if len(reasoning_overlap) > 3:
            reasoning_score = 90
        elif len(reasoning_overlap) > 0:
            reasoning_score = 70
        else:
            reasoning_score = 40
            issues.append("reasoning_not_reflected")
            score -= 15

    checks["reasoning_alignment"] = {
        "score": reasoning_score,
        "technique_used": technique_used,
        "has_reasoning_input": bool(reasoning_output),
    }

    # Compute final score
    final_score = max(0.0, min(100.0, score))
    passed = final_score >= 85.0  # Pro threshold: 85 (higher than Mini's 60)

    # Auto-fix: adjust response if minor issues
    adjusted_response = response
    if issues and "unresolved_placeholders" in issues:
        adjusted_response = re.sub(r'\{+\w+\}+', '', adjusted_response)
        adjusted_response = re.sub(r'\s{2,}', ' ', adjusted_response).strip()

    return {
        "passed": passed,
        "score": round(final_score, 2),
        "issues": issues,
        "adjusted_response": adjusted_response,
        "checks": checks,
    }


# ══════════════════════════════════════════════════════════════════
# REASONING TECHNIQUE EXECUTORS (Tier 2)
# ══════════════════════════════════════════════════════════════════

async def _execute_cot_reasoning(
    query: str,
    classification: Dict[str, Any],
    industry: str,
    llm_client: Any,
) -> Dict[str, Any]:
    """Execute Chain of Thought reasoning.

    Breaks down the problem into sequential thinking steps,
    then derives the answer from those steps.
    """
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support reasoning engine. Think step by step about "
                "this customer's issue. Break it down into: 1) Understanding the "
                "core problem, 2) Identifying the root cause, 3) Determining the "
                "best resolution path, 4) Planning the response structure.\n"
                "Output your reasoning as numbered steps."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}\nIntent: {classification.get('intent', 'general')}",
                max_tokens=400,
                temperature=0.4,
            )
            if response:
                return {
                    "reasoning_text": response,
                    "technique": "chain_of_thought",
                    "tokens_used": tokens,
                    "success": True,
                }

        # Fallback: rule-based CoT
        steps = [
            f"1. Customer is asking about: {classification.get('intent', 'general')}",
            f"2. The core problem relates to: {query[:100]}",
            "3. Best approach: acknowledge, explain, offer resolution",
            "4. Response should include: empathy + action steps + timeline",
        ]
        return {
            "reasoning_text": "\n".join(steps),
            "technique": "chain_of_thought",
            "tokens_used": 0,
            "success": True,
            "method": "rule_based_fallback",
        }
    except Exception:
        return {
            "reasoning_text": "CoT reasoning failed — using direct approach",
            "technique": "chain_of_thought",
            "tokens_used": 0,
            "success": False,
        }


async def _execute_reverse_thinking(
    query: str,
    classification: Dict[str, Any],
    industry: str,
    llm_client: Any,
) -> Dict[str, Any]:
    """Execute Reverse Thinking reasoning.

    Starts from the desired outcome (satisfied customer) and works
    backward to determine what the response needs to contain.
    """
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support reasoning engine using reverse thinking. "
                "Start from the DESIRED OUTCOME (satisfied customer with resolved issue) "
                "and work backward. What must be true for the customer to be satisfied? "
                "What information do they need? What actions must happen?\n"
                "Output: Desired outcome → Required conditions → Response elements."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}\nDesired outcome: Customer satisfied and issue resolved",
                max_tokens=350,
                temperature=0.4,
            )
            if response:
                return {
                    "reasoning_text": response,
                    "technique": "reverse_thinking",
                    "tokens_used": tokens,
                    "success": True,
                }

        # Fallback: rule-based reverse thinking
        return {
            "reasoning_text": (
                "Desired outcome: Customer satisfied\n"
                "Required: Acknowledge problem + Provide clear resolution + Set timeline\n"
                "Response elements: Empathy statement + Action plan + Expected outcome + Follow-up"
            ),
            "technique": "reverse_thinking",
            "tokens_used": 0,
            "success": True,
            "method": "rule_based_fallback",
        }
    except Exception:
        return {
            "reasoning_text": "Reverse thinking failed — using direct approach",
            "technique": "reverse_thinking",
            "tokens_used": 0,
            "success": False,
        }


async def _execute_react_reasoning(
    query: str,
    classification: Dict[str, Any],
    industry: str,
    llm_client: Any,
) -> Dict[str, Any]:
    """Execute ReAct (Reasoning + Acting) reasoning.

    Alternates between thinking about what to do and simulating
    taking actions (like looking up information, checking systems).
    """
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support agent using ReAct (Reasoning + Acting). "
                "For this customer issue, alternate between:\n"
                "- Thought: What do I need to figure out next?\n"
                "- Action: What would I look up or check?\n"
                "- Observation: What would I find?\n"
                "Do 2-3 cycles of Thought→Action→Observation."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}",
                max_tokens=500,
                temperature=0.4,
            )
            if response:
                return {
                    "reasoning_text": response,
                    "technique": "react",
                    "tokens_used": tokens,
                    "success": True,
                }

        # Fallback: rule-based ReAct
        intent = classification.get("intent", "general")
        return {
            "reasoning_text": (
                f"Thought: Customer has a {intent} issue, need to verify details.\n"
                f"Action: Look up customer's account and recent {intent} activity.\n"
                f"Observation: Customer's request is valid, proceed with resolution.\n"
                f"Thought: Need to determine the best resolution path.\n"
                f"Action: Check available resolution options for {intent}.\n"
                f"Observation: Standard resolution process applies with priority handling."
            ),
            "technique": "react",
            "tokens_used": 0,
            "success": True,
            "method": "rule_based_fallback",
        }
    except Exception:
        return {
            "reasoning_text": "ReAct reasoning failed — using direct approach",
            "technique": "react",
            "tokens_used": 0,
            "success": False,
        }


async def _execute_step_back_reasoning(
    query: str,
    classification: Dict[str, Any],
    industry: str,
    llm_client: Any,
) -> Dict[str, Any]:
    """Execute Step-Back reasoning.

    Takes a step back from the specific query to consider the
    broader context and principles before formulating a response.
    """
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support reasoning engine using step-back prompting. "
                "Instead of answering directly, first consider:\n"
                "1. What is the broader category of this issue?\n"
                "2. What are the general principles that apply?\n"
                "3. How do these principles guide the specific response?\n"
                "Then derive the specific answer from the general principles."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}",
                max_tokens=350,
                temperature=0.4,
            )
            if response:
                return {
                    "reasoning_text": response,
                    "technique": "step_back",
                    "tokens_used": tokens,
                    "success": True,
                }

        # Fallback
        return {
            "reasoning_text": (
                "Broader category: Customer service resolution\n"
                "General principles: Timeliness, transparency, empathy, action-orientation\n"
                "Application: Acknowledge quickly, explain the process, take concrete action, "
                "set clear expectations for follow-up"
            ),
            "technique": "step_back",
            "tokens_used": 0,
            "success": True,
            "method": "rule_based_fallback",
        }
    except Exception:
        return {
            "reasoning_text": "Step-back reasoning failed — using direct approach",
            "technique": "step_back",
            "tokens_used": 0,
            "success": False,
        }


async def _execute_thot_reasoning(
    query: str,
    classification: Dict[str, Any],
    industry: str,
    llm_client: Any,
) -> Dict[str, Any]:
    """Execute Thread of Thought reasoning.

    Maintains a coherent thread of reasoning across the analysis,
    building understanding progressively rather than jumping to conclusions.
    """
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support reasoning engine using Thread of Thought. "
                "Build understanding progressively:\n"
                "1. Start with what the customer explicitly stated\n"
                "2. What might they also need but haven't mentioned?\n"
                "3. What's the complete picture for resolving this?\n"
                "Maintain a coherent thread throughout your analysis."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}",
                max_tokens=300,
                temperature=0.4,
            )
            if response:
                return {
                    "reasoning_text": response,
                    "technique": "thread_of_thought",
                    "tokens_used": tokens,
                    "success": True,
                }

        # Fallback
        return {
            "reasoning_text": (
                "Thread: Customer states a problem → likely also needs timeline → "
                "may need escalation option → wants reassurance → complete response "
                "should address stated need + implicit needs + next steps"
            ),
            "technique": "thread_of_thought",
            "tokens_used": 0,
            "success": True,
            "method": "rule_based_fallback",
        }
    except Exception:
        return {
            "reasoning_text": "ThoT reasoning failed — using direct approach",
            "technique": "thread_of_thought",
            "tokens_used": 0,
            "success": False,
        }


# ══════════════════════════════════════════════════════════════════
# NODE FUNCTIONS — 15 Agent Nodes
# ══════════════════════════════════════════════════════════════════


def pii_check_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 1: PII Check — Detect and redact PII in the query.

    Uses PIIDetector from app.core.pii_redaction_engine.
    This is a FREE step (regex-based, no LLM).

    Writes: pii_detected, pii_redacted_query, pii_entities, current_step
    """
    start = time.monotonic()
    try:
        query = state.get("query", "")
        company_id = state.get("company_id", "")

        if not query:
            return {
                "pii_detected": False,
                "pii_redacted_query": query,
                "pii_entities": [],
                "current_step": "pii_check",
                "step_outputs": {"pii_check": {"status": "skipped", "reason": "empty_query"}},
                "audit_log": [append_audit_entry(state, "pii_check", "skipped_empty_query")["audit_log"][0]],
            }

        # Detect PII
        detector = _get_pii_detector()
        matches = detector.detect(query)

        # Build PII entities list
        pii_entities = [
            {
                "type": m.pii_type,
                "value": m.value,
                "start": m.start,
                "end": m.end,
                "confidence": m.confidence,
            }
            for m in matches
        ]

        # Simple redaction
        pii_detected = len(matches) > 0
        redacted_query = query
        if pii_detected:
            for match in sorted(matches, key=lambda m: m.start, reverse=True):
                token = f"{{{{{match.pii_type}}}}}"
                redacted_query = redacted_query[:match.start] + token + redacted_query[match.end:]

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="pii_check",
            action="pii_detection_complete",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "pii_detected": pii_detected,
                "entity_count": len(matches),
                "entity_types": list(set(m.pii_type for m in matches)),
            },
        )

        return {
            "pii_detected": pii_detected,
            "pii_redacted_query": redacted_query,
            "pii_entities": pii_entities,
            "current_step": "pii_check",
            "step_outputs": {
                "pii_check": {
                    "status": "completed",
                    "pii_detected": pii_detected,
                    "entity_count": len(matches),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("pii_check_node_failed", error=str(exc))
        return {
            "pii_detected": False,
            "pii_redacted_query": state.get("query", ""),
            "pii_entities": [],
            "current_step": "pii_check",
            "errors": [f"pii_check: {str(exc)}"],
            "step_outputs": {
                "pii_check": {"status": "error", "error": str(exc), "duration_ms": duration_ms}
            },
            "audit_log": [append_audit_entry(
                state, "pii_check", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


async def empathy_check_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 2: Empathy Check — Score empathy and detect emotional flags.

    Pro uses LLM for deeper empathy analysis (not just keyword).
    FALLBACK: If LLM fails, uses keyword-based detection.

    Writes: empathy_score, empathy_flags, current_step
    """
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query") or state.get("query", "")

        if not query:
            return {
                "empathy_score": 0.5,
                "empathy_flags": [],
                "current_step": "empathy_check",
                "step_outputs": {"empathy_check": {"status": "skipped", "reason": "empty_query"}},
                "audit_log": [append_audit_entry(state, "empathy_check", "skipped_empty_query")["audit_log"][0]],
            }

        # Try LLM-based empathy check (Pro: more detailed analysis)
        empathy_score = 0.5
        empathy_flags: List[str] = []
        method = "keyword"

        try:
            from app.core.parwa.llm_client import ProLLMClient

            client = ProLLMClient()
            if client.is_available:
                llm_response, tokens = await client.chat(
                    system_prompt=(
                        "Analyze the customer's emotional state in detail. "
                        "Return JSON: {\"empathy_score\": <0.0-1.0>, "
                        "\"flags\": [\"frustrated\"|\"angry\"|\"sad\"|\"urgent\"|\"confused\"|\"desperate\"|\"resigned\"], "
                        "\"intensity\": \"low\"|\"medium\"|\"high\", "
                        "\"primary_emotion\": \"<emotion>\"}\n"
                        "Lower empathy_score means more distressed customer. "
                        "Be thorough — this is a Pro-tier analysis."
                    ),
                    user_message=query,
                    max_tokens=150,
                    temperature=0.3,
                )

                if llm_response:
                    json_match = re.search(r'\{[^}]+\}', llm_response)
                    if json_match:
                        data = json.loads(json_match.group())
                        empathy_score = float(data.get("empathy_score", 0.5))
                        empathy_score = max(0.0, min(1.0, empathy_score))
                        empathy_flags = data.get("flags", [])
                        if not isinstance(empathy_flags, list):
                            empathy_flags = []
                        method = "llm"
        except Exception:
            logger.info("empathy_pro_llm_fallback_to_keyword")

        # Fallback to keyword-based if LLM didn't work
        if method == "keyword":
            result = _keyword_empathy_check(query)
            empathy_score = result["empathy_score"]
            empathy_flags = result["empathy_flags"]

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="empathy_check",
            action="empathy_analysis_complete",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "empathy_score": empathy_score,
                "empathy_flags": empathy_flags,
                "method": method,
            },
        )

        return {
            "empathy_score": empathy_score,
            "empathy_flags": empathy_flags,
            "current_step": "empathy_check",
            "step_outputs": {
                "empathy_check": {
                    "status": "completed",
                    "empathy_score": empathy_score,
                    "empathy_flags": empathy_flags,
                    "method": method,
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("empathy_check_node_failed", error=str(exc))
        return {
            "empathy_score": 0.5,
            "empathy_flags": [],
            "current_step": "empathy_check",
            "errors": [f"empathy_check: {str(exc)}"],
            "step_outputs": {
                "empathy_check": {"status": "error", "error": str(exc), "duration_ms": duration_ms}
            },
            "audit_log": [append_audit_entry(
                state, "empathy_check", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def emergency_check_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 3: Emergency Check — Detect emergency signals (FREE, no LLM)."""
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query") or state.get("query", "")

        if not query:
            return {
                "emergency_flag": False,
                "emergency_type": "",
                "current_step": "emergency_check",
                "step_outputs": {"emergency_check": {"status": "skipped", "reason": "empty_query"}},
                "audit_log": [append_audit_entry(state, "emergency_check", "skipped_empty_query")["audit_log"][0]],
            }

        result = _check_emergency_keywords(query)
        emergency_flag = result["emergency_flag"]
        emergency_type = result["emergency_type"]

        if emergency_flag:
            logger.warning(
                "emergency_detected",
                emergency_type=emergency_type,
                company_id=state.get("company_id", ""),
                matched_keywords=result.get("matched_keywords", {}),
            )

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="emergency_check",
            action="emergency_detection_complete",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "emergency_flag": emergency_flag,
                "emergency_type": emergency_type,
                "matched_keywords": result.get("matched_keywords", {}),
            },
        )

        return {
            "emergency_flag": emergency_flag,
            "emergency_type": emergency_type,
            "current_step": "emergency_check",
            "step_outputs": {
                "emergency_check": {
                    "status": "completed",
                    "emergency_flag": emergency_flag,
                    "emergency_type": emergency_type,
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("emergency_check_node_failed", error=str(exc))
        return {
            "emergency_flag": False,
            "emergency_type": "",
            "current_step": "emergency_check",
            "errors": [f"emergency_check: {str(exc)}"],
            "step_outputs": {
                "emergency_check": {"status": "error", "error": str(exc), "duration_ms": duration_ms}
            },
            "audit_log": [append_audit_entry(
                state, "emergency_check", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def gsd_state_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 4: GSD State — Track and update conversation state machine.

    GSD = Guided Support Dialogue (F-053).
    State machine: NEW -> GREETING -> DIAGNOSIS -> RESOLUTION -> FOLLOW-UP -> CLOSED
    """
    start = time.monotonic()
    try:
        company_id = state.get("company_id", "")
        ticket_id = state.get("ticket_id", "")
        query = state.get("pii_redacted_query") or state.get("query", "")
        emergency_flag = state.get("emergency_flag", False)
        empathy_score = state.get("empathy_score", 0.5)
        classification = state.get("classification", {})

        # Determine the GSD state transition
        gsd_manager = _get_gsd_manager()
        current_gsd_state = "new"

        if gsd_manager:
            current_gsd_state = gsd_manager.get_current_state(
                company_id, ticket_id,
            ) or "new"

        # Determine next state
        if emergency_flag:
            next_state = "escalate"
        elif current_gsd_state == "new":
            next_state = "greeting"
        elif current_gsd_state == "greeting":
            next_state = "diagnosis"
        elif current_gsd_state == "diagnosis":
            if state.get("generated_response"):
                next_state = "resolution"
            else:
                next_state = "diagnosis"
        elif current_gsd_state == "resolution":
            next_state = "follow_up"
        elif current_gsd_state == "follow_up":
            next_state = "closed"
        else:
            next_state = current_gsd_state

        # Record the transition
        if gsd_manager and next_state != current_gsd_state:
            gsd_manager.record_transition(
                company_id=company_id,
                ticket_id=ticket_id,
                from_state=current_gsd_state,
                to_state=next_state,
                metadata={
                    "emergency": emergency_flag,
                    "empathy_score": empathy_score,
                    "variant_tier": "parwa",
                },
            )

        recovery_suggestions = []
        if gsd_manager:
            recovery_suggestions = gsd_manager.suggest_recovery(
                company_id, ticket_id,
            )

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="gsd_state",
            action="gsd_state_transition",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "from_state": current_gsd_state,
                "to_state": next_state,
                "emergency": emergency_flag,
            },
        )

        return {
            "current_step": "gsd_state",
            "step_outputs": {
                "gsd_state": {
                    "status": "completed",
                    "from_state": current_gsd_state,
                    "to_state": next_state,
                    "recovery_suggestions": recovery_suggestions,
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("gsd_state_node_failed", error=str(exc))
        return {
            "current_step": "gsd_state",
            "errors": [f"gsd_state: {str(exc)}"],
            "step_outputs": {
                "gsd_state": {"status": "error", "error": str(exc), "duration_ms": duration_ms}
            },
            "audit_log": [append_audit_entry(
                state, "gsd_state", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


async def classify_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 5: Classify — AI-based intent classification (Pro enhancement).

    Pro uses AI classification engine first, falls back to keyword.
    Mini uses keyword-only classification.
    """
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query") or state.get("query", "")
        company_id = state.get("company_id", "")
        industry = state.get("industry", "general")

        if not query:
            return {
                "classification": {"intent": "general", "confidence": 0.0, "method": "skipped"},
                "current_step": "classify",
                "step_outputs": {"classify": {"status": "skipped", "reason": "empty_query"}},
                "audit_log": [append_audit_entry(state, "classify", "skipped_empty_query")["audit_log"][0]],
            }

        classification: Dict[str, Any] = {}
        method = "keyword"

        # Pro: Try AI classification engine first
        try:
            engine = _get_classification_engine()
            if engine:
                ai_result = engine.classify(query, industry=industry)
                if ai_result and ai_result.get("confidence", 0) > 0.5:
                    classification = {
                        "intent": ai_result.get("intent", "general"),
                        "confidence": ai_result.get("confidence", 0.5),
                        "secondary_intents": ai_result.get("secondary_intents", []),
                        "method": "ai",
                    }
                    method = "ai"
        except Exception:
            logger.debug("ai_classification_fallback_to_keyword")

        # Fallback: keyword-based classification
        if method == "keyword":
            classifier = _get_keyword_classifier()
            result = classifier.classify(query)
            classification = {
                "intent": result.get("intent", "general"),
                "confidence": result.get("confidence", 0.5),
                "secondary_intents": result.get("secondary_intents", []),
                "method": "keyword",
            }

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="classify",
            action="classification_complete",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "intent": classification.get("intent", "general"),
                "confidence": classification.get("confidence", 0.0),
                "method": method,
            },
        )

        return {
            "classification": classification,
            "current_step": "classify",
            "step_outputs": {
                "classify": {
                    "status": "completed",
                    "intent": classification.get("intent", "general"),
                    "confidence": classification.get("confidence", 0.0),
                    "method": method,
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("classify_node_failed", error=str(exc))
        return {
            "classification": {"intent": "general", "confidence": 0.0, "method": "error"},
            "current_step": "classify",
            "errors": [f"classify: {str(exc)}"],
            "step_outputs": {
                "classify": {"status": "error", "error": str(exc), "duration_ms": duration_ms}
            },
            "audit_log": [append_audit_entry(
                state, "classify", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def extract_signals_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 6: Extract Signals — Derive query signals for technique routing.

    Pro version: Extracts 12 signals with deeper analysis.
    Feeds into Technique Router (BC-013) for Tier 1+2 technique selection.
    """
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query") or state.get("query", "")
        empathy_score = state.get("empathy_score", 0.5)
        empathy_flags = state.get("empathy_flags", [])
        customer_tier = state.get("customer_tier", "free")
        classification = state.get("classification", {})
        emergency_flag = state.get("emergency_flag", False)

        # ── Signal Extraction (code-orchestrated = FREE) ───────

        # 1. Query complexity
        word_count = len(query.split())
        question_marks = query.count("?")
        has_multi_part = bool(re.search(
            r'\b(and|also|furthermore|moreover|as well|additionally)\b',
            query, re.IGNORECASE,
        ))
        complexity = min(1.0, (word_count / 50) * 0.4 + question_marks * 0.15 + (0.3 if has_multi_part else 0.0))

        # 2. Sentiment score
        sentiment = empathy_score

        # 3. Monetary value detection
        monetary_match = re.search(r'\$(\d+(?:,\d+)*(?:\.\d{2})?)', query)
        monetary_value = float(monetary_match.group(1).replace(",", "")) if monetary_match else 0.0

        # 4. Intent type
        intent_type = classification.get("intent", "general") if classification else "general"

        # 5. Frustration score (from empathy flags)
        frustration_map = {"frustrated": 40, "angry": 70, "sad": 30, "urgent": 50, "confused": 20}
        frustration_score = sum(frustration_map.get(f, 0) for f in empathy_flags)

        # 6. Confidence score from classification
        confidence_score = classification.get("confidence", 0.5) if classification else 0.5

        # 7. Resolution path count
        resolution_path_count = 1
        if has_multi_part:
            resolution_path_count = 2
        if question_marks > 1:
            resolution_path_count = max(resolution_path_count, question_marks)

        # 8. External data required
        external_data_required = bool(re.search(
            r'\b(check|look up|verify|status|track|find|search)\b',
            query, re.IGNORECASE,
        ))

        # 9. Reasoning loop detection
        reasoning_loop_detected = bool(re.search(
            r'\b(still|again|same issue|repeated|keep getting|keep happening)\b',
            query, re.IGNORECASE,
        ))

        # 10. Is strategic decision
        is_strategic_decision = bool(re.search(
            r'\b(upgrade|downgrade|switch|cancel|migrate|enterprise|contract)\b',
            query, re.IGNORECASE,
        ))

        # 11. Previous response status
        previous_response_status = "none"
        if reasoning_loop_detected:
            previous_response_status = "rejected"

        # 12. Turn count (from conversation metadata)
        turn_count = 1  # Default for new conversation

        # Build signals dict
        signals = {
            "query_complexity": round(complexity, 3),
            "confidence_score": round(confidence_score, 3),
            "sentiment_score": round(sentiment, 3),
            "frustration_score": round(frustration_score, 1),
            "customer_tier": customer_tier,
            "monetary_value": round(monetary_value, 2),
            "turn_count": turn_count,
            "intent_type": intent_type,
            "previous_response_status": previous_response_status,
            "reasoning_loop_detected": reasoning_loop_detected,
            "resolution_path_count": resolution_path_count,
            "external_data_required": external_data_required,
            "is_strategic_decision": is_strategic_decision,
        }

        # Feed signals to Technique Router
        technique_router = _get_technique_router()
        technique_result: Dict[str, Any] = {}
        if technique_router:
            try:
                from app.core.technique_router import QuerySignals
                qs = QuerySignals(
                    query_complexity=complexity,
                    confidence_score=confidence_score,
                    sentiment_score=sentiment,
                    frustration_score=frustration_score,
                    customer_tier=customer_tier,
                    monetary_value=monetary_value,
                    turn_count=turn_count,
                    intent_type=intent_type,
                    previous_response_status=previous_response_status,
                    reasoning_loop_detected=reasoning_loop_detected,
                    resolution_path_count=resolution_path_count,
                    external_data_required=external_data_required,
                    is_strategic_decision=is_strategic_decision,
                )
                router_result = technique_router.route(qs)
                technique_result = {
                    "activated_techniques": [
                        {
                            "id": t.technique_id.value,
                            "tier": t.tier.value,
                            "triggered_by": t.triggered_by,
                        }
                        for t in router_result.activated_techniques
                    ],
                    "model_tier": router_result.model_tier,
                    "total_estimated_tokens": router_result.total_estimated_tokens,
                    "trigger_rules_matched": router_result.trigger_rules_matched,
                }
            except Exception:
                logger.debug("technique_router_signal_feed_failed")

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="extract_signals",
            action="signal_extraction_complete",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "complexity": round(complexity, 3),
                "intent": intent_type,
                "monetary_value": monetary_value,
                "techniques_activated": len(technique_result.get("activated_techniques", [])),
            },
        )

        return {
            "signals": signals,
            "technique": technique_result,
            "current_step": "extract_signals",
            "step_outputs": {
                "extract_signals": {
                    "status": "completed",
                    "complexity": round(complexity, 3),
                    "intent": intent_type,
                    "techniques_activated": len(technique_result.get("activated_techniques", [])),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("extract_signals_node_failed", error=str(exc))
        return {
            "signals": {},
            "technique": {},
            "current_step": "extract_signals",
            "errors": [f"extract_signals: {str(exc)}"],
            "step_outputs": {
                "extract_signals": {"status": "error", "error": str(exc), "duration_ms": duration_ms}
            },
            "audit_log": [append_audit_entry(
                state, "extract_signals", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def technique_select_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 7: Technique Select — Select the best reasoning technique (Pro-specific).

    Reads the technique result from extract_signals and selects the
    primary technique for the reasoning_chain node to execute.

    Pro uses Tier 1+2 techniques (CoT, ReAct, Reverse, Step-Back, ThoT).
    Mini only uses Tier 1 (CLARA, CRP, GSD) — doesn't have this node.
    """
    start = time.monotonic()
    try:
        technique_result = state.get("technique", {})
        signals = state.get("signals", {})
        classification = state.get("classification", {})

        # Determine the primary technique from activated techniques
        activated = technique_result.get("activated_techniques", [])

        # Priority: Tier 2 techniques first (they add the most value)
        tier2_techniques = [t for t in activated if t.get("tier") == "tier_2"]
        tier1_techniques = [t for t in activated if t.get("tier") == "tier_1"]

        # Select primary technique (highest value Tier 2 technique)
        technique_priority = {
            "react": 5,            # Most powerful for action-oriented queries
            "chain_of_thought": 4,  # Great for complex reasoning
            "reverse_thinking": 3,  # Good for resolution planning
            "step_back": 2,        # Good for context seeking
            "thread_of_thought": 1, # Good for continuity
        }

        primary_technique = "direct"  # Default: no technique, direct generation
        primary_tier = "tier_1"

        if tier2_techniques:
            # Pick the highest priority Tier 2 technique
            best = max(
                tier2_techniques,
                key=lambda t: technique_priority.get(t.get("id", ""), 0),
            )
            primary_technique = best.get("id", "direct")
            primary_tier = best.get("tier", "tier_2")

        # Build technique instruction for the reasoning chain
        technique_instruction = ""
        if primary_technique == "chain_of_thought":
            technique_instruction = "Think step by step about this issue and provide a structured reasoning chain."
        elif primary_technique == "react":
            technique_instruction = "Use Reasoning + Acting: alternate between thinking about what to do and simulating actions."
        elif primary_technique == "reverse_thinking":
            technique_instruction = "Start from the desired outcome (satisfied customer) and work backward to determine the response."
        elif primary_technique == "step_back":
            technique_instruction = "Take a step back: consider the broader category and principles before responding."
        elif primary_technique == "thread_of_thought":
            technique_instruction = "Build understanding progressively: stated need → implicit needs → complete resolution."

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="technique_select",
            action="technique_selected",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "primary_technique": primary_technique,
                "primary_tier": primary_tier,
                "activated_count": len(activated),
                "tier2_count": len(tier2_techniques),
            },
        )

        return {
            "current_step": "technique_select",
            "step_outputs": {
                "technique_select": {
                    "status": "completed",
                    "primary_technique": primary_technique,
                    "primary_tier": primary_tier,
                    "technique_instruction": technique_instruction,
                    "activated_count": len(activated),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("technique_select_node_failed", error=str(exc))
        return {
            "current_step": "technique_select",
            "errors": [f"technique_select: {str(exc)}"],
            "step_outputs": {
                "technique_select": {"status": "error", "error": str(exc), "duration_ms": duration_ms}
            },
            "audit_log": [append_audit_entry(
                state, "technique_select", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


async def reasoning_chain_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 8: Reasoning Chain — Execute the selected reasoning technique (Pro-specific).

    This is the core Pro enhancement: before generating a response,
    the pipeline runs a reasoning technique to produce a structured
    analysis. The generation node then uses this reasoning output
    to produce a higher-quality response.

    Mini doesn't have this node — it goes straight from classify to generate.
    """
    start = time.monotonic()
    try:
        technique_output = state.get("step_outputs", {}).get("technique_select", {})
        primary_technique = technique_output.get("primary_technique", "direct")
        query = state.get("pii_redacted_query") or state.get("query", "")
        classification = state.get("classification", {})
        industry = state.get("industry", "general")

        # Get LLM client for technique execution
        llm_client = None
        try:
            from app.core.parwa.llm_client import ProLLMClient
            llm_client = ProLLMClient()
        except Exception:
            logger.debug("pro_llm_client_unavailable_for_reasoning")

        reasoning_text = ""
        reasoning_technique = primary_technique
        tokens_used = 0

        # Execute the selected technique
        if primary_technique == "chain_of_thought":
            result = await _execute_cot_reasoning(query, classification, industry, llm_client)
            reasoning_text = result.get("reasoning_text", "")
            tokens_used = result.get("tokens_used", 0)
        elif primary_technique == "reverse_thinking":
            result = await _execute_reverse_thinking(query, classification, industry, llm_client)
            reasoning_text = result.get("reasoning_text", "")
            tokens_used = result.get("tokens_used", 0)
        elif primary_technique == "react":
            result = await _execute_react_reasoning(query, classification, industry, llm_client)
            reasoning_text = result.get("reasoning_text", "")
            tokens_used = result.get("tokens_used", 0)
        elif primary_technique == "step_back":
            result = await _execute_step_back_reasoning(query, classification, industry, llm_client)
            reasoning_text = result.get("reasoning_text", "")
            tokens_used = result.get("tokens_used", 0)
        elif primary_technique == "thread_of_thought":
            result = await _execute_thot_reasoning(query, classification, industry, llm_client)
            reasoning_text = result.get("reasoning_text", "")
            tokens_used = result.get("tokens_used", 0)
        else:
            # Direct: no reasoning technique, just basic analysis
            intent = classification.get("intent", "general")
            reasoning_text = f"Direct approach for {intent} query. Acknowledge and resolve directly."
            reasoning_technique = "direct"

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="reasoning_chain",
            action="reasoning_complete",
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            details={
                "technique": reasoning_technique,
                "reasoning_length": len(reasoning_text),
            },
        )

        return {
            "current_step": "reasoning_chain",
            "step_outputs": {
                "reasoning_chain": {
                    "status": "completed",
                    "technique": reasoning_technique,
                    "reasoning_text": reasoning_text,
                    "tokens_used": tokens_used,
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("reasoning_chain_node_failed", error=str(exc))
        return {
            "current_step": "reasoning_chain",
            "errors": [f"reasoning_chain: {str(exc)}"],
            "step_outputs": {
                "reasoning_chain": {
                    "status": "error",
                    "error": str(exc),
                    "reasoning_text": "",
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": [append_audit_entry(
                state, "reasoning_chain", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def context_enrich_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 9: Context Enrich — Enrich generation context with reasoning (Pro-specific).

    Takes the reasoning output from reasoning_chain and builds a rich
    context object that the generate node will use. This includes:
    - Reasoning text as guidance
    - Industry-specific adjustments
    - Technique-specific prompt modifications
    - Empathy-aware context framing

    Mini doesn't have this node.
    """
    start = time.monotonic()
    try:
        reasoning_output = state.get("step_outputs", {}).get("reasoning_chain", {})
        technique_output = state.get("step_outputs", {}).get("technique_select", {})
        classification = state.get("classification", {})
        industry = state.get("industry", "general")
        empathy_score = state.get("empathy_score", 0.5)
        emergency_flag = state.get("emergency_flag", False)

        reasoning_text = reasoning_output.get("reasoning_text", "")
        primary_technique = technique_output.get("primary_technique", "direct")
        intent = classification.get("intent", "general")

        # Build enriched context
        enriched_context = {
            "reasoning_guidance": reasoning_text,
            "technique_used": primary_technique,
            "intent": intent,
            "industry": industry,
            "empathy_level": "high" if empathy_score < 0.3 else "medium" if empathy_score < 0.6 else "low",
            "requires_escalation": emergency_flag,
            "response_strategy": "",
        }

        # Determine response strategy based on technique + empathy
        if emergency_flag:
            enriched_context["response_strategy"] = "escalate_immediately"
        elif empathy_score < 0.3:
            enriched_context["response_strategy"] = "empathy_first_then_resolve"
        elif primary_technique in ("chain_of_thought", "react"):
            enriched_context["response_strategy"] = "structured_step_by_step"
        elif primary_technique == "reverse_thinking":
            enriched_context["response_strategy"] = "outcome_focused"
        elif primary_technique == "step_back":
            enriched_context["response_strategy"] = "contextual_then_specific"
        elif primary_technique == "thread_of_thought":
            enriched_context["response_strategy"] = "progressive_resolution"
        else:
            enriched_context["response_strategy"] = "direct_resolution"

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="context_enrich",
            action="context_enrichment_complete",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "technique": primary_technique,
                "strategy": enriched_context["response_strategy"],
                "empathy_level": enriched_context["empathy_level"],
            },
        )

        return {
            "current_step": "context_enrich",
            "step_outputs": {
                "context_enrich": {
                    "status": "completed",
                    "enriched_context": enriched_context,
                    "strategy": enriched_context["response_strategy"],
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("context_enrich_node_failed", error=str(exc))
        return {
            "current_step": "context_enrich",
            "errors": [f"context_enrich: {str(exc)}"],
            "step_outputs": {
                "context_enrich": {
                    "status": "error",
                    "error": str(exc),
                    "enriched_context": {},
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": [append_audit_entry(
                state, "context_enrich", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


async def generate_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 10: Generate — Technique-guided response generation (enhanced for Pro).

    Pro generates using the reasoning chain output and enriched context.
    Mini generates directly from classification (no reasoning).
    """
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query") or state.get("query", "")
        company_id = state.get("company_id", "")
        industry = state.get("industry", "general")
        classification = state.get("classification", {})
        empathy_score = state.get("empathy_score", 0.5)
        emergency_flag = state.get("emergency_flag", False)

        # Get reasoning and context from Pro-specific nodes
        reasoning_output = state.get("step_outputs", {}).get("reasoning_chain", {})
        context_output = state.get("step_outputs", {}).get("context_enrich", {})
        reasoning_text = reasoning_output.get("reasoning_text", "")
        enriched_context = context_output.get("enriched_context", {})
        technique_used = enriched_context.get("technique_used", "direct")
        response_strategy = enriched_context.get("response_strategy", "direct_resolution")

        # Get industry prompts
        industry_prompt = get_industry_prompt(industry)
        industry_tone = get_industry_tone(industry)

        intent = classification.get("intent", "general") if classification else "general"

        generated_response = ""
        generation_model = "gpt-4o-mini"
        generation_tokens = 0

        # Try LLM generation with technique guidance
        try:
            from app.core.parwa.llm_client import ProLLMClient

            client = ProLLMClient()
            if client.is_available:
                # Build technique-aware system prompt
                technique_instruction = ""
                if reasoning_text:
                    technique_instruction = (
                        f"\n\nREASONING GUIDANCE (from {technique_used} analysis):\n"
                        f"{reasoning_text}\n\n"
                        f"Use this reasoning to inform your response. Follow the {response_strategy} strategy."
                    )

                empathy_instruction = ""
                if empathy_score < 0.3:
                    empathy_instruction = (
                        "\n\nIMPORTANT: This customer appears distressed. "
                        "Start with empathy, then address their issue."
                    )
                elif empathy_score < 0.5:
                    empathy_instruction = (
                        "\n\nNOTE: Customer shows moderate frustration. "
                        "Acknowledge their concern before providing solutions."
                    )

                system_prompt = (
                    f"{industry_prompt}\n\n"
                    f"You are a Pro-tier support agent. Provide detailed, "
                    f"step-by-step assistance. Be thorough but concise.\n"
                    f"Intent: {intent}\n"
                    f"Tone: {industry_tone}"
                    f"{technique_instruction}"
                    f"{empathy_instruction}"
                )

                generated_response, generation_tokens = await client.chat(
                    system_prompt=system_prompt,
                    user_message=query,
                    max_tokens=600,
                    temperature=0.5,
                )
                generation_model = client.model_name
        except Exception:
            logger.info("pro_llm_generation_failed — using template fallback")

        # Fallback to template response
        if not generated_response:
            generated_response = TEMPLATE_RESPONSES.get(
                intent, TEMPLATE_RESPONSES["general"],
            )
            # Replace ticket_id placeholder
            ticket_id = state.get("ticket_id", "N/A")
            generated_response = generated_response.replace("{ticket_id}", ticket_id)
            generation_model = "template"
            generation_tokens = 0

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="generate",
            action="response_generated",
            duration_ms=duration_ms,
            tokens_used=generation_tokens,
            details={
                "model": generation_model,
                "technique": technique_used,
                "strategy": response_strategy,
                "response_length": len(generated_response),
            },
        )

        return {
            "generated_response": generated_response,
            "generation_model": generation_model,
            "generation_tokens": generation_tokens,
            "current_step": "generate",
            "step_outputs": {
                "generate": {
                    "status": "completed",
                    "model": generation_model,
                    "technique": technique_used,
                    "tokens": generation_tokens,
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("generate_node_failed", error=str(exc))
        intent = state.get("classification", {}).get("intent", "general")
        return {
            "generated_response": TEMPLATE_RESPONSES.get(intent, TEMPLATE_RESPONSES["general"]),
            "generation_model": "template_fallback",
            "generation_tokens": 0,
            "current_step": "generate",
            "errors": [f"generate: {str(exc)}"],
            "step_outputs": {
                "generate": {"status": "error", "error": str(exc), "duration_ms": duration_ms}
            },
            "audit_log": [append_audit_entry(
                state, "generate", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def crp_compress_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 11: CRP Compress — Token waste elimination (Tier 1, always active).

    CRP = Concise Response Protocol. Removes filler phrases and
    redundant text while preserving all factual content.
    """
    start = time.monotonic()
    try:
        response = state.get("generated_response", "")

        if not response:
            return {
                "current_step": "crp_compress",
                "step_outputs": {"crp_compress": {"status": "skipped", "reason": "no_response"}},
                "audit_log": [append_audit_entry(state, "crp_compress", "skipped_no_response")["audit_log"][0]],
            }

        result = _apply_crp_compression(response)

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="crp_compress",
            action="crp_compression_complete",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "tokens_removed": result["tokens_removed"],
                "compression_ratio": result["compression_ratio"],
                "phrases_removed": result["phrases_removed"],
            },
        )

        return {
            "generated_response": result["compressed_text"],
            "current_step": "crp_compress",
            "step_outputs": {
                "crp_compress": {
                    "status": "completed",
                    "tokens_removed": result["tokens_removed"],
                    "compression_ratio": result["compression_ratio"],
                    "phrases_removed": result["phrases_removed"],
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("crp_compress_node_failed", error=str(exc))
        return {
            "current_step": "crp_compress",
            "errors": [f"crp_compress: {str(exc)}"],
            "step_outputs": {
                "crp_compress": {"status": "error", "error": str(exc), "duration_ms": duration_ms}
            },
            "audit_log": [append_audit_entry(
                state, "crp_compress", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def clara_quality_gate_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 12: CLARA Quality Gate — Enhanced response validation (Pro: threshold 85).

    CLARA = Concise Logical Adaptive Response Architecture.
    Validates: Structure -> Logic -> Brand -> Tone -> Delivery -> Reasoning Alignment

    Pro version: Higher threshold (85 vs Mini's 60), additional reasoning check.
    If quality fails, quality_retry node will handle the retry.
    """
    start = time.monotonic()
    try:
        response = state.get("generated_response", "")
        query = state.get("pii_redacted_query") or state.get("query", "")
        industry = state.get("industry", "general")
        empathy_score = state.get("empathy_score", 0.5)
        reasoning_output = state.get("step_outputs", {}).get("reasoning_chain", {})
        technique_output = state.get("step_outputs", {}).get("technique_select", {})

        tone = get_industry_tone(industry)

        # Run CLARA quality gate (Pro version with reasoning alignment)
        result = _run_clara_quality_gate(
            response=response,
            query=query,
            industry=industry,
            tone=tone,
            empathy_score=empathy_score,
            reasoning_output=reasoning_output.get("reasoning_text", ""),
            technique_used=technique_output.get("primary_technique", "direct"),
        )

        quality_passed = result["passed"]
        quality_score = result["score"]
        quality_issues = result["issues"]

        # Apply adjusted response if CLARA made fixes
        adjusted_response = result.get("adjusted_response", response)
        if adjusted_response != response:
            response = adjusted_response

        # Get current retry count (for quality_retry tracking)
        retry_count = state.get("quality_retry_count", 0)

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        # Compute combined confidence score: 60% CLARA + 40% Confidence Engine
        confidence_score = 0.0
        confidence_engine = _get_confidence_engine()
        if confidence_engine:
            try:
                cs_result = confidence_engine.score_response(
                    company_id=state.get("company_id", ""),
                    query=query,
                    response=response,
                    context={"industry": industry},
                    config={"tier": "parwa"},
                )
                confidence_score = cs_result if isinstance(cs_result, (int, float)) else 0.5
            except Exception:
                confidence_score = 0.5

        combined_quality = (quality_score * 0.6) + (confidence_score * 100 * 0.4)

        audit_entry = append_audit_entry(
            state,
            step="clara_quality_gate",
            action="quality_gate_complete",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "passed": quality_passed,
                "score": quality_score,
                "combined_score": round(combined_quality, 2),
                "issues": quality_issues,
                "retry_count": retry_count,
            },
        )

        return {
            "generated_response": response,
            "quality_score": round(combined_quality, 2),
            "quality_passed": quality_passed,
            "quality_issues": quality_issues,
            "quality_retry_count": retry_count,  # Not incremented yet
            "current_step": "clara_quality_gate",
            "step_outputs": {
                "clara_quality_gate": {
                    "status": "completed",
                    "passed": quality_passed,
                    "score": quality_score,
                    "combined_score": round(combined_quality, 2),
                    "issues": quality_issues,
                    "checks": result.get("checks", {}),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("clara_quality_gate_node_failed", error=str(exc))
        return {
            "quality_score": 0.0,
            "quality_passed": True,  # Allow pipeline to continue
            "quality_issues": [f"quality_gate_error: {str(exc)}"],
            "quality_retry_count": state.get("quality_retry_count", 0),
            "current_step": "clara_quality_gate",
            "errors": [f"clara_quality_gate: {str(exc)}"],
            "step_outputs": {
                "clara_quality_gate": {"status": "error", "error": str(exc), "duration_ms": duration_ms}
            },
            "audit_log": [append_audit_entry(
                state, "clara_quality_gate", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def quality_retry_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 13: Quality Retry — Retry generation if quality gate failed (Pro-specific).

    This node prepares state for a retry by:
    1. Incrementing the retry counter
    2. Adding quality feedback to the generation context
    3. Routing back to generate for a second attempt

    Max retries: 1 (Pro). Mini doesn't have this node at all.
    """
    start = time.monotonic()
    try:
        retry_count = state.get("quality_retry_count", 0) + 1
        quality_issues = state.get("quality_issues", [])
        quality_score = state.get("quality_score", 0.0)

        # Add retry feedback to step outputs so generate can use it
        retry_feedback = {
            "retry_number": retry_count,
            "previous_quality_score": quality_score,
            "issues_to_fix": quality_issues,
            "retry_instruction": "",
        }

        # Build specific retry instructions based on issues
        if "poor_structure" in quality_issues:
            retry_feedback["retry_instruction"] += (
                "Ensure the response has: greeting/acknowledgment, "
                "clear action steps, and a follow-up offer. "
            )
        if "off_topic" in quality_issues or "partial_topic_coverage" in quality_issues:
            retry_feedback["retry_instruction"] += (
                "Address the customer's specific question more directly. "
                "Use words from their query in your response. "
            )
        if "insufficient_empathy" in quality_issues or "moderate_empathy_gap" in quality_issues:
            retry_feedback["retry_instruction"] += (
                "Start with acknowledging the customer's concern. "
                "Show understanding before providing solutions. "
            )
        if "reasoning_not_reflected" in quality_issues:
            retry_feedback["retry_instruction"] += (
                "Incorporate the reasoning analysis into your response. "
                "Make the reasoning visible in how you structure the answer. "
            )
        if "response_too_short" in quality_issues or "response_brief" in quality_issues:
            retry_feedback["retry_instruction"] += (
                "Provide a more detailed response with step-by-step guidance. "
            )

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="quality_retry",
            action="quality_retry_initiated",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "retry_count": retry_count,
                "previous_score": quality_score,
                "issues": quality_issues,
            },
        )

        logger.info(
            "quality_retry_initiated: retry=%d, score=%.1f, issues=%s, company_id=%s",
            retry_count, quality_score, quality_issues,
            state.get("company_id", ""),
        )

        return {
            "quality_retry_count": retry_count,
            "current_step": "quality_retry",
            "step_outputs": {
                "quality_retry": {
                    "status": "completed",
                    "retry_count": retry_count,
                    "previous_score": quality_score,
                    "issues_to_fix": quality_issues,
                    "retry_instruction": retry_feedback["retry_instruction"],
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("quality_retry_node_failed", error=str(exc))
        return {
            "quality_retry_count": state.get("quality_retry_count", 0) + 1,
            "current_step": "quality_retry",
            "errors": [f"quality_retry: {str(exc)}"],
            "step_outputs": {
                "quality_retry": {"status": "error", "error": str(exc), "duration_ms": duration_ms}
            },
            "audit_log": [append_audit_entry(
                state, "quality_retry", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def confidence_assess_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 14: Confidence Assess — Deep confidence assessment (Pro-specific).

    Provides a thorough assessment of how confident we are in the response.
    Uses the Confidence Scoring Engine (F-059) with Pro-level analysis.

    Mini doesn't have this node — it goes straight from CLARA to format.
    """
    start = time.monotonic()
    try:
        response = state.get("generated_response", "")
        query = state.get("pii_redacted_query") or state.get("query", "")
        company_id = state.get("company_id", "")
        industry = state.get("industry", "general")
        quality_score = state.get("quality_score", 0.0)
        quality_passed = state.get("quality_passed", True)
        quality_issues = state.get("quality_issues", [])
        technique_used = state.get("step_outputs", {}).get("technique_select", {}).get(
            "primary_technique", "direct",
        )

        # Run confidence scoring engine
        confidence_score = 0.5
        confidence_details: Dict[str, Any] = {}

        confidence_engine = _get_confidence_engine()
        if confidence_engine:
            try:
                result = confidence_engine.score_response(
                    company_id=company_id,
                    query=query,
                    response=response,
                    context={
                        "industry": industry,
                        "quality_score": quality_score,
                        "quality_passed": quality_passed,
                        "technique_used": technique_used,
                    },
                    config={"tier": "parwa"},
                )
                if isinstance(result, (int, float)):
                    confidence_score = float(result)
                elif isinstance(result, dict):
                    confidence_score = float(result.get("score", 0.5))
                    confidence_details = result
            except Exception:
                confidence_score = 0.5

        # Compute final combined score: 60% CLARA quality + 40% confidence
        final_score = (quality_score * 0.6) + (confidence_score * 100 * 0.4)

        # Determine if escalation is needed based on confidence
        needs_escalation = False
        escalation_reason = ""
        if confidence_score < 0.3:
            needs_escalation = True
            escalation_reason = "low_confidence"
        elif not quality_passed and state.get("quality_retry_count", 0) >= 1:
            needs_escalation = True
            escalation_reason = "quality_failed_after_retry"

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="confidence_assess",
            action="confidence_assessment_complete",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "confidence_score": round(confidence_score, 3),
                "final_score": round(final_score, 2),
                "needs_escalation": needs_escalation,
                "technique_used": technique_used,
            },
        )

        return {
            "current_step": "confidence_assess",
            "step_outputs": {
                "confidence_assess": {
                    "status": "completed",
                    "confidence_score": round(confidence_score, 3),
                    "final_score": round(final_score, 2),
                    "needs_escalation": needs_escalation,
                    "escalation_reason": escalation_reason,
                    "technique_used": technique_used,
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("confidence_assess_node_failed", error=str(exc))
        return {
            "current_step": "confidence_assess",
            "errors": [f"confidence_assess: {str(exc)}"],
            "step_outputs": {
                "confidence_assess": {
                    "status": "error",
                    "error": str(exc),
                    "confidence_score": 0.5,
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": [append_audit_entry(
                state, "confidence_assess", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def format_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 15: Format — Channel-specific formatting and final assembly.

    Formats the response for the target channel (chat, email, etc.)
    and builds the final response + steps_completed list.
    """
    start = time.monotonic()
    try:
        response = state.get("generated_response", "")
        channel = state.get("channel", "chat")
        industry = state.get("industry", "general")
        emergency_flag = state.get("emergency_flag", False)
        ticket_id = state.get("ticket_id", "")

        # Handle emergency bypass (format was called before generate)
        if emergency_flag and not response:
            response = EMERGENCY_RESPONSE_TEMPLATE.format(ticket_id=ticket_id)

        # Ensure we have a response
        if not response:
            response = TEMPLATE_RESPONSES["general"]

        # Get formatter and format for channel
        formatter_registry = _get_formatter_registry()
        formatted_response = response

        if formatter_registry:
            try:
                tone = get_industry_tone(industry)
                classification = state.get("classification", {})
                intent_type = classification.get("intent", "general") if classification else "general"

                context = FormattingContext(
                    channel=channel,
                    intent_type=intent_type,
                    brand_voice=tone,
                    industry=industry,
                )
                formatted_response = formatter_registry.format(response, context)
            except Exception:
                formatted_response = response

        # Build the steps_completed list from step_outputs
        step_outputs = state.get("step_outputs", {})
        steps_completed = [
            step_name for step_name, output in step_outputs.items()
            if isinstance(output, dict) and output.get("status") == "completed"
        ]

        # Determine pipeline status
        errors = state.get("errors", [])
        if errors:
            pipeline_status = "partial"
        elif emergency_flag:
            pipeline_status = "escalated"
        else:
            pipeline_status = "success"

        # Update billing cost (Pro: ~$0.008/query)
        generation_tokens = state.get("generation_tokens", 0)
        estimated_cost = round(generation_tokens * 0.008 / 1000, 6)  # Rough estimate

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="format",
            action="formatting_complete",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "channel": channel,
                "steps_completed": steps_completed,
                "pipeline_status": pipeline_status,
            },
        )

        return {
            "formatted_response": formatted_response,
            "final_response": formatted_response,
            "response_format": channel,
            "steps_completed": steps_completed,
            "pipeline_status": pipeline_status,
            "billing_cost_usd": estimated_cost,
            "current_step": "format",
            "step_outputs": {
                "format": {
                    "status": "completed",
                    "channel": channel,
                    "pipeline_status": pipeline_status,
                    "steps_completed": steps_completed,
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("format_node_failed", error=str(exc))
        return {
            "formatted_response": state.get("generated_response", ""),
            "final_response": state.get("generated_response", ""),
            "pipeline_status": "partial",
            "current_step": "format",
            "errors": [f"format: {str(exc)}"],
            "step_outputs": {
                "format": {"status": "error", "error": str(exc), "duration_ms": duration_ms}
            },
            "audit_log": [append_audit_entry(
                state, "format", "error", duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }
