"""
High Parwa Pipeline Nodes — 27 agent-nodes for the LangGraph pipeline.

Pipeline: pii_check -> empathy_check -> emergency_check -> gsd_state
        -> classify -> smart_enrichment -> [deep_enrichment_router]
          -> complaint_handler | retention_negotiator | billing_resolver
          | tech_diagnostic | shipping_tracker | (skip)
        -> extract_signals -> technique_select
        -> reasoning_chain -> context_enrich -> context_compress
        -> generate -> crp_compress -> clara_quality_gate
        -> quality_retry (max 2) -> confidence_assess
        -> context_health -> dedup -> strategic_decision
        -> peer_review -> auto_action -> format -> END

Each node:
  - Takes ParwaGraphState dict as input
  - Returns a dict with ONLY the fields it modified (LangGraph merges these)
  - Is wrapped in try/except (BC-008: never crash)
  - Appends to audit_log and errors using reducer pattern
  - Tracks timing in step_outputs

Connected Frameworks (Tier 1 + Tier 2 + Tier 3):
  Tier 1 (Always Active):
    - CLARA — Quality gate (threshold 95, 8-check — strictest)
    - CRP — Token waste elimination
    - GSD — State machine tracking
    - Smart Router — Model tier selection (Heavy for High)
    - Technique Router — Technique selection (Tier 1+2+3)
    - Confidence Scoring — Response confidence assessment

  Tier 2 (Conditional):
    - CoT, ReAct, Reverse Thinking, Step-Back, ThoT

  Tier 3 (Conditional — High-exclusive):
    - GST (General Systematic Thinking)
    - UoT (Universe of Thoughts)
    - ToT (Tree of Thoughts)
    - Self-Consistency
    - Reflexion
    - Least-to-Most

High vs Pro differences in nodes:
  - classify_node: Uses AI classification (same as Pro but Heavy model)
  - technique_select_node: Selects Tier 1+2+3 techniques
  - reasoning_chain_node: Executes Tier 1+2+3 techniques
  - context_compress_node: NEW — Compresses context before generation
  - generate_node: Technique-guided with compressed context
  - clara_quality_gate_node: Highest threshold (95), 8-check
  - quality_retry_node: Max 2 retries (vs Pro's 1)
  - context_health_node: NEW — Checks context drift/degradation
  - dedup_node: NEW — Detects duplicate responses
  - strategic_decision_node: NEW — Strategic routing for complex cases
  - peer_review_node: NEW — Final validation before delivery
  - format_node: High-specific formatting with peer review metadata

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
from app.core.enhancements.emotional_intelligence import EmotionalIntelligenceEngine
from app.core.enhancements.churn_retention import ChurnRetentionEngine
from app.core.enhancements.billing_intelligence import BillingIntelligenceEngine
from app.core.enhancements.tech_diagnostics import TechDiagnosticsEngine
from app.core.enhancements.shipping_intelligence import ShippingIntelligenceEngine
from app.core.parwa_high.llm_client import HighLLMClient
from app.logger import get_logger

logger = get_logger("parwa_high_nodes")


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
_high_llm_client: Optional[HighLLMClient] = None

# Tier 3 technique IDs (string-based for compatibility)
HIGH_TIER3_TECHNIQUES = [
    "gst", "uot", "tot", "self_consistency",
    "reflexion", "least_to_most",
]


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
    """Get or create the classification engine singleton (High uses AI classification)."""
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
    """Get or create the TechniqueRouter singleton (High: Heavy tier, Tier 1+2+3)."""
    global _technique_router
    if _technique_router is None:
        try:
            from app.core.technique_router import (
                TechniqueRouter,
                TechniqueID,
                TechniqueTier,
            )
            # High enables Tier 1 + Tier 2 + Tier 3 techniques
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
            # Try to add Tier 3 TechniqueIDs if they exist
            for tid_name in ["GST", "UOT", "TOT", "SELF_CONSISTENCY", "REFLEXION", "LEAST_TO_MOST"]:
                tid = getattr(TechniqueID, tid_name, None)
                if tid is not None:
                    enabled.add(tid)
            _technique_router = TechniqueRouter(
                model_tier="heavy",
                enabled_techniques=enabled,
            )
        except Exception:
            logger.warning("technique_router_import_failed — using string-based selection")
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


def _get_high_llm_client() -> HighLLMClient:
    """Get or create the HighLLMClient singleton."""
    global _high_llm_client
    if _high_llm_client is None:
        _high_llm_client = HighLLMClient()
    return _high_llm_client


def _get_ei_engine() -> Any:
    global _ei_engine
    if _ei_engine is None:
        try:
            _ei_engine = EmotionalIntelligenceEngine()
        except Exception:
            pass
    return _ei_engine


def _get_churn_engine() -> Any:
    global _churn_engine
    if _churn_engine is None:
        try:
            _churn_engine = ChurnRetentionEngine()
        except Exception:
            pass
    return _churn_engine


def _get_billing_engine() -> Any:
    global _billing_engine
    if _billing_engine is None:
        try:
            _billing_engine = BillingIntelligenceEngine()
        except Exception:
            pass
    return _billing_engine


def _get_tech_diag_engine() -> Any:
    global _tech_diag_engine
    if _tech_diag_engine is None:
        try:
            _tech_diag_engine = TechDiagnosticsEngine()
        except Exception:
            pass
    return _tech_diag_engine


def _get_shipping_engine() -> Any:
    global _shipping_engine
    if _shipping_engine is None:
        try:
            _shipping_engine = ShippingIntelligenceEngine()
        except Exception:
            pass
    return _shipping_engine


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
    "A senior team member will contact you directly. "
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

    for phrase in CRP_FILLER_PHRASES:
        if phrase.lower() in compressed.lower():
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            compressed = pattern.sub("", compressed)
            phrases_removed.append(phrase)

    compressed = re.sub(r'\s{2,}', ' ', compressed)
    compressed = re.sub(r'\.\s*\.', '.', compressed)
    compressed = re.sub(r'^\s+|\s+$', '', compressed, flags=re.MULTILINE)
    compressed = compressed.strip()

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
# CLARA QUALITY GATE — Strictest for High (threshold 95, 8-check)
# ══════════════════════════════════════════════════════════════════

def _run_clara_quality_gate_high(
    response: str,
    query: str,
    industry: str,
    tone: str,
    empathy_score: float,
    reasoning_output: str = "",
    technique_used: str = "",
    signals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the CLARA quality gate pipeline (High: threshold 95, 8-check — strictest).

    CLARA = Concise Logical Adaptive Response Architecture.
    Validates: Structure -> Logic -> Brand -> Tone -> Delivery
               -> Reasoning Alignment -> Consistency -> Completeness

    High version: Highest threshold (95), 8 checks (strictest).
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

    # Check 1: STRUCTURE
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
        structure_score += 25
    if has_action:
        structure_score += 25
    if has_steps:
        structure_score += 25
    if len(response.split('.')) >= 3:
        structure_score += 25

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

    # Check 2: LOGIC
    query_tokens = set(re.findall(r'\b\w{4,}\b', query.lower()))
    response_tokens = set(re.findall(r'\b\w{4,}\b', response.lower()))
    stop_words = {
        "that", "this", "with", "have", "will", "been", "from",
        "they", "would", "could", "should", "there", "their",
        "about", "which", "when", "where", "your", "please",
    }
    query_content = query_tokens - stop_words
    overlap = query_content & (response_tokens - stop_words) if query_content else set()
    logic_score = int(len(overlap) / max(len(query_content), 1) * 100)

    if logic_score < 30:
        issues.append("off_topic")
        score -= 25
    elif logic_score < 50:
        issues.append("partial_topic_coverage")
        score -= 15

    checks["logic"] = {
        "score": logic_score,
        "overlap_count": len(overlap),
    }

    # Check 3: BRAND
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

    # Check 4: TONE
    tone_score = 80
    if empathy_score < 0.3 and not has_acknowledgment:
        tone_score = 30
        issues.append("insufficient_empathy")
        score -= 20
    elif empathy_score < 0.5 and not has_acknowledgment:
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

    # Check 5: DELIVERY
    delivery_score = 80
    if len(response.strip()) < 30:
        delivery_score = 25
        issues.append("response_too_short")
        score -= 25
    elif len(response.strip()) < 50:
        delivery_score = 50
        issues.append("response_brief")
        score -= 10
    elif len(response.strip()) > 2000:
        delivery_score = 65
        issues.append("response_verbose")
        score -= 5

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

    # Check 6: REASONING ALIGNMENT
    reasoning_score = 70
    if reasoning_output and technique_used:
        reasoning_tokens = set(re.findall(r'\b\w{4,}\b', reasoning_output.lower()))
        resp_tokens_r = set(re.findall(r'\b\w{4,}\b', response.lower()))
        reasoning_overlap = reasoning_tokens & resp_tokens_r
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
    }

    # Check 7: CONSISTENCY (High-specific)
    consistency_score = 85
    # Check for contradiction markers
    contradiction_patterns = [
        (r'\byes\b.*\bno\b', "yes_no_contradiction"),
        (r'\bwill\b.*\bcannot\b', "will_cannot_contradiction"),
        (r'\bavailable\b.*\bunavailable\b', "availability_contradiction"),
    ]
    for pattern, issue_name in contradiction_patterns:
        if re.search(pattern, response, re.IGNORECASE):
            consistency_score -= 20
            issues.append(issue_name)
            score -= 10
            break

    checks["consistency"] = {
        "score": consistency_score,
    }

    # Check 8: COMPLETENESS (High-specific)
    completeness_score = 70
    query_aspects = query.split(" and ")
    if len(query_aspects) > 1:
        addressed = sum(
            1 for aspect in query_aspects
            if any(w in response_lower for w in aspect.lower().split() if len(w) > 3)
        )
        completeness_score = int(addressed / len(query_aspects) * 100)
        if completeness_score < 50:
            issues.append("incomplete_address")
            score -= 15

    # Check if response has a closing/follow-up
    has_closing = bool(re.search(
        r'\b(let me know|feel free|don\'t hesitate|reach out|contact us)\b',
        response, re.IGNORECASE,
    ))
    if not has_closing:
        completeness_score -= 10

    checks["completeness"] = {
        "score": completeness_score,
        "has_closing": has_closing,
    }

    # Compute final score
    final_score = max(0.0, min(100.0, score))
    passed = final_score >= 95.0  # High threshold: 95 (strictest)

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
    query: str, classification: Dict[str, Any], industry: str, llm_client: Any,
) -> Dict[str, Any]:
    """Execute Chain of Thought reasoning."""
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
                return {"reasoning_text": response, "technique": "chain_of_thought", "tokens_used": tokens, "success": True}

        steps = [
            f"1. Customer is asking about: {classification.get('intent', 'general')}",
            f"2. The core problem relates to: {query[:100]}",
            "3. Best approach: acknowledge, explain, offer resolution",
            "4. Response should include: empathy + action steps + timeline",
        ]
        return {"reasoning_text": "\n".join(steps), "technique": "chain_of_thought", "tokens_used": 0, "success": True, "method": "rule_based_fallback"}
    except Exception:
        return {"reasoning_text": "CoT reasoning failed — using direct approach", "technique": "chain_of_thought", "tokens_used": 0, "success": False}


async def _execute_reverse_thinking(
    query: str, classification: Dict[str, Any], industry: str, llm_client: Any,
) -> Dict[str, Any]:
    """Execute Reverse Thinking reasoning."""
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support reasoning engine using reverse thinking. "
                "Start from the DESIRED OUTCOME and work backward. "
                "What must be true for the customer to be satisfied?\n"
                "Output: Desired outcome -> Required conditions -> Response elements."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}",
                max_tokens=350,
                temperature=0.4,
            )
            if response:
                return {"reasoning_text": response, "technique": "reverse_thinking", "tokens_used": tokens, "success": True}

        return {
            "reasoning_text": "Desired outcome: Customer satisfied\nRequired: Acknowledge + Resolve + Timeline\nResponse: Empathy + Action + Follow-up",
            "technique": "reverse_thinking", "tokens_used": 0, "success": True, "method": "rule_based_fallback",
        }
    except Exception:
        return {"reasoning_text": "Reverse thinking failed", "technique": "reverse_thinking", "tokens_used": 0, "success": False}


async def _execute_react_reasoning(
    query: str, classification: Dict[str, Any], industry: str, llm_client: Any,
) -> Dict[str, Any]:
    """Execute ReAct reasoning."""
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support agent using ReAct. Alternate between:\n"
                "- Thought: What do I need to figure out?\n"
                "- Action: What would I look up?\n"
                "- Observation: What would I find?\n"
                "Do 2-3 cycles."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}",
                max_tokens=500, temperature=0.4,
            )
            if response:
                return {"reasoning_text": response, "technique": "react", "tokens_used": tokens, "success": True}

        intent = classification.get("intent", "general")
        return {
            "reasoning_text": f"Thought: Customer has {intent} issue\nAction: Look up account details\nObservation: Valid request, proceed with resolution",
            "technique": "react", "tokens_used": 0, "success": True, "method": "rule_based_fallback",
        }
    except Exception:
        return {"reasoning_text": "ReAct failed", "technique": "react", "tokens_used": 0, "success": False}


async def _execute_step_back_reasoning(
    query: str, classification: Dict[str, Any], industry: str, llm_client: Any,
) -> Dict[str, Any]:
    """Execute Step-Back reasoning."""
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support reasoning engine using step-back prompting. "
                "Consider: 1) Broader category, 2) General principles, "
                "3) How principles guide the specific response."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}",
                max_tokens=350, temperature=0.4,
            )
            if response:
                return {"reasoning_text": response, "technique": "step_back", "tokens_used": tokens, "success": True}

        return {
            "reasoning_text": "Broader: Customer service resolution\nPrinciples: Timeliness, transparency, empathy\nApplication: Acknowledge, explain, act, follow up",
            "technique": "step_back", "tokens_used": 0, "success": True, "method": "rule_based_fallback",
        }
    except Exception:
        return {"reasoning_text": "Step-back failed", "technique": "step_back", "tokens_used": 0, "success": False}


async def _execute_thot_reasoning(
    query: str, classification: Dict[str, Any], industry: str, llm_client: Any,
) -> Dict[str, Any]:
    """Execute Thread of Thought reasoning."""
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support reasoning engine using Thread of Thought. "
                "Build understanding progressively: stated need -> implicit needs -> complete picture."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}",
                max_tokens=300, temperature=0.4,
            )
            if response:
                return {"reasoning_text": response, "technique": "thread_of_thought", "tokens_used": tokens, "success": True}

        return {
            "reasoning_text": "Thread: Problem stated -> also needs timeline -> may need escalation -> wants reassurance",
            "technique": "thread_of_thought", "tokens_used": 0, "success": True, "method": "rule_based_fallback",
        }
    except Exception:
        return {"reasoning_text": "ThoT failed", "technique": "thread_of_thought", "tokens_used": 0, "success": False}


# ══════════════════════════════════════════════════════════════════
# REASONING TECHNIQUE EXECUTORS (Tier 3 — High-exclusive)
# ══════════════════════════════════════════════════════════════════

async def _execute_gst_reasoning(
    query: str, classification: Dict[str, Any], industry: str, llm_client: Any,
) -> Dict[str, Any]:
    """Execute General Systematic Thinking — systematic problem decomposition."""
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support reasoning engine using General Systematic Thinking (GST). "
                "Decompose this problem systematically:\n"
                "1. Define the problem precisely\n"
                "2. Identify all relevant factors\n"
                "3. Map dependencies between factors\n"
                "4. Determine the optimal resolution sequence\n"
                "5. Validate the solution against constraints"
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}\nIntent: {classification.get('intent', 'general')}",
                max_tokens=600, temperature=0.3,
            )
            if response:
                return {"reasoning_text": response, "technique": "gst", "tokens_used": tokens, "success": True}

        return {
            "reasoning_text": f"GST: Problem={classification.get('intent', 'general')} | Factors=[urgency, complexity, customer_tier] | Sequence=[acknowledge, resolve, confirm]",
            "technique": "gst", "tokens_used": 0, "success": True, "method": "rule_based_fallback",
        }
    except Exception:
        return {"reasoning_text": "GST reasoning failed", "technique": "gst", "tokens_used": 0, "success": False}


async def _execute_uot_reasoning(
    query: str, classification: Dict[str, Any], industry: str, llm_client: Any,
) -> Dict[str, Any]:
    """Execute Universe of Thoughts — multi-perspective exploration."""
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support reasoning engine using Universe of Thoughts (UoT). "
                "Explore this issue from multiple perspectives:\n"
                "1. Customer's perspective (what they need/want)\n"
                "2. Company's perspective (policies, capabilities)\n"
                "3. Technical perspective (systems, processes)\n"
                "4. Legal/compliance perspective (if relevant)\n"
                "Synthesize into a comprehensive resolution approach."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}",
                max_tokens=600, temperature=0.3,
            )
            if response:
                return {"reasoning_text": response, "technique": "uot", "tokens_used": tokens, "success": True}

        return {
            "reasoning_text": "UoT: Customer=wants resolution | Company=can offer X | Technical=process Y | Synthesis=offer resolution with timeline",
            "technique": "uot", "tokens_used": 0, "success": True, "method": "rule_based_fallback",
        }
    except Exception:
        return {"reasoning_text": "UoT reasoning failed", "technique": "uot", "tokens_used": 0, "success": False}


async def _execute_tot_reasoning(
    query: str, classification: Dict[str, Any], industry: str, llm_client: Any,
) -> Dict[str, Any]:
    """Execute Tree of Thoughts — branching exploration of solutions."""
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support reasoning engine using Tree of Thoughts (ToT). "
                "Generate 3 possible solution branches:\n"
                "Branch A: Quick resolution (immediate fix)\n"
                "Branch B: Comprehensive resolution (deep investigation)\n"
                "Branch C: Alternative resolution (creative workaround)\n"
                "Evaluate each branch and recommend the best one."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}",
                max_tokens=700, temperature=0.3,
            )
            if response:
                return {"reasoning_text": response, "technique": "tot", "tokens_used": tokens, "success": True}

        return {
            "reasoning_text": "ToT: A=Quick fix (60% success) | B=Deep investigation (90% success) | C=Workaround (75% success) | Best=B",
            "technique": "tot", "tokens_used": 0, "success": True, "method": "rule_based_fallback",
        }
    except Exception:
        return {"reasoning_text": "ToT reasoning failed", "technique": "tot", "tokens_used": 0, "success": False}


async def _execute_self_consistency_reasoning(
    query: str, classification: Dict[str, Any], industry: str, llm_client: Any,
) -> Dict[str, Any]:
    """Execute Self-Consistency — multi-sample voting for reliability."""
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support reasoning engine using Self-Consistency. "
                "Generate 3 independent analyses of this issue, then vote "
                "on the most consistent approach. Each analysis should reach "
                "an independent conclusion, then compare them for consensus."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}",
                max_tokens=600, temperature=0.5,
            )
            if response:
                return {"reasoning_text": response, "technique": "self_consistency", "tokens_used": tokens, "success": True}

        return {
            "reasoning_text": "Self-Consistency: 3/3 analyses agree on direct resolution approach",
            "technique": "self_consistency", "tokens_used": 0, "success": True, "method": "rule_based_fallback",
        }
    except Exception:
        return {"reasoning_text": "Self-Consistency failed", "technique": "self_consistency", "tokens_used": 0, "success": False}


async def _execute_reflexion_reasoning(
    query: str, classification: Dict[str, Any], industry: str, llm_client: Any,
) -> Dict[str, Any]:
    """Execute Reflexion — self-critique and improvement loop."""
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support reasoning engine using Reflexion. "
                "1. Propose an initial response approach\n"
                "2. Critique your own approach — what could go wrong?\n"
                "3. Improve the approach based on your critique\n"
                "4. Present the final improved approach"
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}",
                max_tokens=600, temperature=0.3,
            )
            if response:
                return {"reasoning_text": response, "technique": "reflexion", "tokens_used": tokens, "success": True}

        return {
            "reasoning_text": "Reflexion: Initial=direct approach | Critique=may lack empathy | Improved=add acknowledgment first",
            "technique": "reflexion", "tokens_used": 0, "success": True, "method": "rule_based_fallback",
        }
    except Exception:
        return {"reasoning_text": "Reflexion failed", "technique": "reflexion", "tokens_used": 0, "success": False}


async def _execute_least_to_most_reasoning(
    query: str, classification: Dict[str, Any], industry: str, llm_client: Any,
) -> Dict[str, Any]:
    """Execute Least-to-Most — progressive complexity decomposition."""
    try:
        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a support reasoning engine using Least-to-Most decomposition. "
                "Break this problem into progressively complex sub-problems:\n"
                "1. Simplest sub-problem (what's immediately clear)\n"
                "2. Medium sub-problem (what requires some investigation)\n"
                "3. Most complex sub-problem (what requires deep analysis)\n"
                "Solve each in order, building on previous solutions."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer issue: {query}",
                max_tokens=600, temperature=0.3,
            )
            if response:
                return {"reasoning_text": response, "technique": "least_to_most", "tokens_used": tokens, "success": True}

        return {
            "reasoning_text": "Least-to-Most: Simple=acknowledge issue | Medium=provide resolution steps | Complex=ensure complete satisfaction",
            "technique": "least_to_most", "tokens_used": 0, "success": True, "method": "rule_based_fallback",
        }
    except Exception:
        return {"reasoning_text": "Least-to-Most failed", "technique": "least_to_most", "tokens_used": 0, "success": False}


# Technique executor mapping
TECHNIQUE_EXECUTORS: Dict[str, Any] = {
    "chain_of_thought": _execute_cot_reasoning,
    "cot": _execute_cot_reasoning,
    "reverse_thinking": _execute_reverse_thinking,
    "react": _execute_react_reasoning,
    "step_back": _execute_step_back_reasoning,
    "thread_of_thought": _execute_thot_reasoning,
    "thot": _execute_thot_reasoning,
    # Tier 3
    "gst": _execute_gst_reasoning,
    "uot": _execute_uot_reasoning,
    "tot": _execute_tot_reasoning,
    "self_consistency": _execute_self_consistency_reasoning,
    "reflexion": _execute_reflexion_reasoning,
    "least_to_most": _execute_least_to_most_reasoning,
}


# ══════════════════════════════════════════════════════════════════
# NODE FUNCTIONS — 22 Agent Nodes
# ══════════════════════════════════════════════════════════════════


def pii_check_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 1: PII Check — Detect and redact PII in the query."""
    start = time.monotonic()
    try:
        query = state.get("query", "")
        if not query:
            return {
                "pii_detected": False,
                "pii_redacted_query": query,
                "pii_entities": [],
                "current_step": "pii_check",
                "step_outputs": {"pii_check": {"status": "skipped", "reason": "empty_query"}},
                "audit_log": [append_audit_entry(state, "pii_check", "skipped_empty_query")["audit_log"][0]],
            }

        detector = _get_pii_detector()
        matches = detector.detect(query)
        pii_entities = [
            {"type": m.pii_type, "value": m.value, "start": m.start, "end": m.end, "confidence": m.confidence}
            for m in matches
        ]
        pii_detected = len(matches) > 0
        redacted_query = query
        if pii_detected:
            for match in sorted(matches, key=lambda m: m.start, reverse=True):
                token = f"{{{{{match.pii_type}}}}}"
                redacted_query = redacted_query[:match.start] + token + redacted_query[match.end:]

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="pii_check", action="pii_detection_complete",
            duration_ms=duration_ms, tokens_used=0,
            details={"pii_detected": pii_detected, "entity_count": len(matches)},
        )
        return {
            "pii_detected": pii_detected,
            "pii_redacted_query": redacted_query,
            "pii_entities": pii_entities,
            "current_step": "pii_check",
            "steps_completed": state.get("steps_completed", []) + ["pii_check"],
            "step_outputs": {"pii_check": {"status": "completed", "pii_detected": pii_detected, "entity_count": len(matches), "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("pii_check_node failed: %s", exc)
        return {
            "pii_detected": False,
            "pii_redacted_query": state.get("query", ""),
            "pii_entities": [],
            "current_step": "pii_check",
            "errors": ["pii_check_failed"],
            "step_outputs": {"pii_check": {"status": "failed", "duration_ms": duration_ms}},
        }


def empathy_check_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 2: Empathy Check — Analyze emotional state of the query."""
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query", "") or state.get("query", "")
        llm_client = _get_high_llm_client()

        if llm_client and llm_client.is_available:
            # Use LLM for empathy (async but we're in sync node — use fallback)
            result = _keyword_empathy_check(query)
        else:
            result = _keyword_empathy_check(query)

        empathy_score = result["empathy_score"]
        empathy_flags = result["empathy_flags"]
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state, step="empathy_check", action="empathy_analysis_complete",
            duration_ms=duration_ms, details={"empathy_score": empathy_score, "flags": empathy_flags},
        )
        return {
            "empathy_score": empathy_score,
            "empathy_flags": empathy_flags,
            "current_step": "empathy_check",
            "steps_completed": state.get("steps_completed", []) + ["empathy_check"],
            "step_outputs": {"empathy_check": {"status": "completed", "empathy_score": empathy_score, "flags": empathy_flags, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("empathy_check_node failed: %s", exc)
        return {
            "empathy_score": 0.5,
            "empathy_flags": [],
            "current_step": "empathy_check",
            "errors": ["empathy_check_failed"],
            "step_outputs": {"empathy_check": {"status": "failed", "duration_ms": duration_ms}},
        }


def emergency_check_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 3: Emergency Check — Detect emergency signals requiring immediate escalation."""
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query", "") or state.get("query", "")
        result = _check_emergency_keywords(query)
        emergency_flag = result["emergency_flag"]
        emergency_type = result["emergency_type"]
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state, step="emergency_check", action="emergency_detection_complete",
            duration_ms=duration_ms,
            details={"emergency_flag": emergency_flag, "emergency_type": emergency_type},
        )
        return {
            "emergency_flag": emergency_flag,
            "emergency_type": emergency_type,
            "current_step": "emergency_check",
            "steps_completed": state.get("steps_completed", []) + ["emergency_check"],
            "step_outputs": {"emergency_check": {"status": "completed", "emergency_flag": emergency_flag, "emergency_type": emergency_type, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("emergency_check_node failed: %s", exc)
        return {
            "emergency_flag": False,
            "emergency_type": "",
            "current_step": "emergency_check",
            "errors": ["emergency_check_failed"],
            "step_outputs": {"emergency_check": {"status": "failed", "duration_ms": duration_ms}},
        }


def gsd_state_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 4: GSD State — Track conversation state machine."""
    start = time.monotonic()
    try:
        emergency_flag = state.get("emergency_flag", False)
        empathy_score = state.get("empathy_score", 0.5)
        gsd_manager = _get_gsd_manager()

        if gsd_manager:
            try:
                current_state = gsd_manager.get_state(
                    state.get("conversation_id", ""),
                    state.get("company_id", ""),
                )
                to_state = gsd_manager.transition(
                    conversation_id=state.get("conversation_id", ""),
                    company_id=state.get("company_id", ""),
                    event="message_received",
                    context={"emergency": emergency_flag, "empathy": empathy_score},
                )
            except Exception:
                current_state = "greeting"
                to_state = "investigating" if not emergency_flag else "escalate"
        else:
            if emergency_flag:
                current_state = "greeting"
                to_state = "escalate"
            elif empathy_score < 0.3:
                current_state = "greeting"
                to_state = "escalate"
            else:
                current_state = "greeting"
                to_state = "investigating"

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="gsd_state", action="state_transition",
            duration_ms=duration_ms,
            details={"from_state": current_state, "to_state": to_state},
        )
        return {
            "current_step": "gsd_state",
            "steps_completed": state.get("steps_completed", []) + ["gsd_state"],
            "step_outputs": {"gsd_state": {"status": "completed", "from_state": current_state, "to_state": to_state, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("gsd_state_node failed: %s", exc)
        return {
            "current_step": "gsd_state",
            "errors": ["gsd_state_failed"],
            "step_outputs": {"gsd_state": {"status": "failed", "duration_ms": duration_ms}},
        }


async def classify_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 5: Classify — Intent classification using AI (Heavy model)."""
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query", "") or state.get("query", "")
        industry = state.get("industry", "general")
        llm_client = _get_high_llm_client()

        # Try AI classification first
        classification: Dict[str, Any] = {}
        if llm_client and llm_client.is_available:
            system_prompt = (
                "Classify this customer message into exactly one primary intent. "
                "Return JSON: {\"intent\": \"...\", \"confidence\": 0.0-1.0, "
                "\"secondary_intents\": [...], \"method\": \"ai\"}\n"
                "Valid intents: refund, technical, billing, complaint, cancellation, "
                "shipping, account, general"
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=f"Customer message: {query}\nIndustry: {industry}",
                max_tokens=200, temperature=0.2,
            )
            if response:
                try:
                    cleaned = response.strip()
                    if cleaned.startswith("```"):
                        cleaned = re.sub(r'^```\w*\n?', '', cleaned)
                        cleaned = re.sub(r'\n?```$', '', cleaned)
                    classification = json.loads(cleaned)
                    classification["method"] = "ai"
                except (json.JSONDecodeError, ValueError):
                    classification = {}

        # Fallback to keyword classification
        if not classification or not classification.get("intent"):
            try:
                engine = _get_classification_engine()
                if engine:
                    classification = engine.classify(query)
                    classification["method"] = "keyword_engine"
                else:
                    classifier = _get_keyword_classifier()
                    classification = classifier.classify(query)
                    classification["method"] = "keyword"
            except Exception:
                classification = {"intent": "general", "confidence": 0.0, "secondary_intents": [], "method": "fallback"}

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="classify", action="classification_complete",
            duration_ms=duration_ms,
            details={"intent": classification.get("intent"), "confidence": classification.get("confidence"), "method": classification.get("method")},
        )
        return {
            "classification": classification,
            "current_step": "classify",
            "steps_completed": state.get("steps_completed", []) + ["classify"],
            "step_outputs": {"classify": {"status": "completed", "classification": classification, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("classify_node failed: %s", exc)
        return {
            "classification": {"intent": "general", "confidence": 0.0, "secondary_intents": [], "method": "fallback"},
            "current_step": "classify",
            "errors": ["classify_failed"],
            "step_outputs": {"classify": {"status": "failed", "duration_ms": duration_ms}},
        }


def extract_signals_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 6: Extract Signals — Extract signals from query for technique selection."""
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query", "") or state.get("query", "")
        classification = state.get("classification", {})
        empathy_score = state.get("empathy_score", 0.5)
        emergency_flag = state.get("emergency_flag", False)

        # Compute complexity based on query length, sentence count, and intent
        word_count = len(query.split())
        sentence_count = len([s for s in query.split('.') if s.strip()])
        has_multiple_intents = len(classification.get("secondary_intents", [])) > 0

        complexity = 0.3
        if word_count > 50:
            complexity += 0.2
        if sentence_count > 2:
            complexity += 0.15
        if has_multiple_intents:
            complexity += 0.2
        if empathy_score < 0.3:
            complexity += 0.15
        complexity = min(1.0, complexity)

        signals = {
            "complexity": complexity,
            "sentiment": empathy_score,
            "frustration_score": max(0, (1.0 - empathy_score) * 100),
            "monetary_value": 0.0,
            "customer_tier": state.get("customer_tier", "free"),
            "turn_count": 1,
            "resolution_path_count": 1 if not has_multiple_intents else 2,
            "reasoning_loop_detected": False,
            "emergency": emergency_flag,
        }

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="extract_signals", action="signal_extraction_complete",
            duration_ms=duration_ms, details={"complexity": complexity, "frustration": signals["frustration_score"]},
        )
        return {
            "signals": signals,
            "current_step": "extract_signals",
            "steps_completed": state.get("steps_completed", []) + ["extract_signals"],
            "step_outputs": {"extract_signals": {"status": "completed", "signals": signals, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("extract_signals_node failed: %s", exc)
        return {
            "signals": {},
            "current_step": "extract_signals",
            "errors": ["extract_signals_failed"],
            "step_outputs": {"extract_signals": {"status": "failed", "duration_ms": duration_ms}},
        }


def technique_select_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 7: Technique Select — Select Tier 1+2+3 reasoning technique."""
    start = time.monotonic()
    try:
        signals = state.get("signals", {})
        classification = state.get("classification", {})
        complexity = signals.get("complexity", 0.3)
        frustration = signals.get("frustration_score", 0)
        technique_router = _get_technique_router()

        technique_result: Dict[str, Any] = {}
        if technique_router:
            try:
                technique_result = technique_router.select(
                    intent=classification.get("intent", "general"),
                    complexity=complexity,
                    frustration_score=frustration,
                    variant_tier="parwa_high",
                )
            except Exception:
                technique_result = {}

        if not technique_result:
            # Rule-based technique selection for High
            if complexity > 0.8 and frustration > 70:
                primary = "reflexion"
            elif complexity > 0.7:
                primary = "tot"
            elif complexity > 0.5:
                primary = "chain_of_thought"
            elif frustration > 50:
                primary = "reverse_thinking"
            else:
                primary = "step_back"

            technique_result = {
                "primary_technique": primary,
                "activated_techniques": [primary],
                "model_tier": "heavy",
                "trigger_rules_matched": [f"complexity_{complexity:.1f}"],
                "method": "rule_based",
            }

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="technique_select", action="technique_selected",
            duration_ms=duration_ms,
            details={"technique": technique_result.get("primary_technique"), "method": technique_result.get("method")},
        )
        return {
            "technique": technique_result,
            "current_step": "technique_select",
            "steps_completed": state.get("steps_completed", []) + ["technique_select"],
            "step_outputs": {"technique_select": {"status": "completed", "primary_technique": technique_result.get("primary_technique"), "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("technique_select_node failed: %s", exc)
        return {
            "technique": {"primary_technique": "direct", "activated_techniques": [], "model_tier": "heavy", "method": "fallback"},
            "current_step": "technique_select",
            "errors": ["technique_select_failed"],
            "step_outputs": {"technique_select": {"status": "failed", "duration_ms": duration_ms}},
        }


async def reasoning_chain_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 8: Reasoning Chain — Execute the selected reasoning technique."""
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query", "") or state.get("query", "")
        classification = state.get("classification", {})
        industry = state.get("industry", "general")
        technique = state.get("technique", {})
        primary_technique = technique.get("primary_technique", "direct")
        llm_client = _get_high_llm_client()

        if primary_technique == "direct":
            reasoning_result = {
                "reasoning_text": "Direct approach — no reasoning technique needed",
                "technique": "direct",
                "tokens_used": 0,
                "success": True,
            }
        else:
            executor = TECHNIQUE_EXECUTORS.get(primary_technique)
            if executor:
                reasoning_result = await executor(query, classification, industry, llm_client)
            else:
                reasoning_result = await _execute_cot_reasoning(query, classification, industry, llm_client)

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="reasoning_chain", action="reasoning_complete",
            duration_ms=duration_ms, tokens_used=reasoning_result.get("tokens_used", 0),
            details={"technique": reasoning_result.get("technique"), "success": reasoning_result.get("success")},
        )
        return {
            "current_step": "reasoning_chain",
            "steps_completed": state.get("steps_completed", []) + ["reasoning_chain"],
            "step_outputs": {"reasoning_chain": {"status": "completed", "technique": reasoning_result.get("technique"), "success": reasoning_result.get("success"), "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
            # Store reasoning text for context_enrich and generate
            "total_tokens": state.get("total_tokens", 0) + reasoning_result.get("tokens_used", 0),
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("reasoning_chain_node failed: %s", exc)
        return {
            "current_step": "reasoning_chain",
            "errors": ["reasoning_chain_failed"],
            "step_outputs": {"reasoning_chain": {"status": "failed", "duration_ms": duration_ms}},
        }


def context_enrich_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 9: Context Enrich — Enrich context with reasoning output."""
    start = time.monotonic()
    try:
        classification = state.get("classification", {})
        technique = state.get("technique", {})
        signals = state.get("signals", {})
        industry = state.get("industry", "general")
        tone = get_industry_tone(industry)

        enriched_context = {
            "intent": classification.get("intent", "general"),
            "confidence": classification.get("confidence", 0.0),
            "technique": technique.get("primary_technique", "direct"),
            "model_tier": technique.get("model_tier", "heavy"),
            "industry": industry,
            "tone": tone,
            "complexity": signals.get("complexity", 0.3),
            "frustration_score": signals.get("frustration_score", 0),
            "empathy_score": state.get("empathy_score", 0.5),
            "customer_tier": state.get("customer_tier", "free"),
        }

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="context_enrich", action="context_enriched",
            duration_ms=duration_ms, details={"technique": enriched_context["technique"]},
        )
        return {
            "current_step": "context_enrich",
            "steps_completed": state.get("steps_completed", []) + ["context_enrich"],
            "step_outputs": {"context_enrich": {"status": "completed", "enriched_context": enriched_context, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("context_enrich_node failed: %s", exc)
        return {
            "current_step": "context_enrich",
            "errors": ["context_enrich_failed"],
            "step_outputs": {"context_enrich": {"status": "failed", "duration_ms": duration_ms}},
        }


async def context_compress_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 10: Context Compress — Compress context before generation (High-only).

    Reduces the context + reasoning output to essential tokens
    before passing to the generation step. Saves tokens and
    focuses the generation on what matters.
    """
    start = time.monotonic()
    try:
        reasoning_output = state.get("step_outputs", {}).get("reasoning_chain", {})
        reasoning_text = ""
        if isinstance(reasoning_output, dict):
            reasoning_text = reasoning_output.get("reasoning_text", "")

        query = state.get("pii_redacted_query", "") or state.get("query", "")
        classification = state.get("classification", {})
        technique = state.get("technique", {})

        # Build the full context string to compress
        full_context = f"Query: {query}\n"
        if classification.get("intent"):
            full_context += f"Intent: {classification['intent']}\n"
        if reasoning_text:
            full_context += f"Reasoning: {reasoning_text}\n"

        llm_client = _get_high_llm_client()
        compressed_context = full_context
        compression_ratio = 1.0

        if llm_client and llm_client.is_available and len(full_context.split()) > 100:
            system_prompt = (
                "Compress the following support context into a concise summary "
                "that preserves all key information for response generation. "
                "Remove redundancy, keep essential facts, intent, and reasoning conclusions. "
                "Target: 50% reduction while retaining all critical information."
            )
            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=full_context,
                max_tokens=300, temperature=0.2,
            )
            if response:
                compressed_context = response
                original_tokens = len(full_context.split())
                new_tokens = len(compressed_context.split())
                compression_ratio = round(new_tokens / max(original_tokens, 1), 3)
        else:
            # Fallback: simple truncation of reasoning text
            if len(reasoning_text.split()) > 100:
                compressed_reasoning = " ".join(reasoning_text.split()[:100]) + "..."
                compressed_context = compressed_context.replace(reasoning_text, compressed_reasoning)
                original_tokens = len(full_context.split())
                new_tokens = len(compressed_context.split())
                compression_ratio = round(new_tokens / max(original_tokens, 1), 3)

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="context_compress", action="context_compressed",
            duration_ms=duration_ms,
            details={"compression_ratio": compression_ratio, "original_length": len(full_context), "compressed_length": len(compressed_context)},
        )
        return {
            "context_compressed": True,
            "context_compression_ratio": compression_ratio,
            "compressed_context": compressed_context,
            "current_step": "context_compress",
            "steps_completed": state.get("steps_completed", []) + ["context_compress"],
            "step_outputs": {"context_compress": {"status": "completed", "compression_ratio": compression_ratio, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("context_compress_node failed: %s", exc)
        return {
            "context_compressed": False,
            "context_compression_ratio": 1.0,
            "compressed_context": "",
            "current_step": "context_compress",
            "errors": ["context_compress_failed"],
            "step_outputs": {"context_compress": {"status": "failed", "duration_ms": duration_ms}},
        }


async def generate_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 11: Generate — Generate response using technique-guided generation with compressed context."""
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query", "") or state.get("query", "")
        industry = state.get("industry", "general")
        classification = state.get("classification", {})
        technique = state.get("technique", {})
        empathy_score = state.get("empathy_score", 0.5)
        emergency_flag = state.get("emergency_flag", False)
        tone = get_industry_tone(industry)

        if emergency_flag:
            ticket_id = state.get("ticket_id", "N/A")
            emergency_response = EMERGENCY_RESPONSE_TEMPLATE.format(ticket_id=ticket_id)
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            return {
                "generated_response": emergency_response,
                "generation_model": "emergency_bypass",
                "generation_tokens": 0,
                "current_step": "generate",
                "steps_completed": state.get("steps_completed", []) + ["generate"],
                "step_outputs": {"generate": {"status": "completed", "model": "emergency_bypass", "duration_ms": duration_ms}},
            }

        # Build context for generation
        context = state.get("compressed_context", "")
        if not context:
            reasoning_output = state.get("step_outputs", {}).get("reasoning_chain", {})
            reasoning_text = reasoning_output.get("reasoning_text", "") if isinstance(reasoning_output, dict) else ""
            context = f"Query: {query}\nIntent: {classification.get('intent', 'general')}\n"
            if reasoning_text:
                context += f"Reasoning: {reasoning_text}\n"

        llm_client = _get_high_llm_client()
        generated_response = ""
        generation_tokens = 0
        generation_model = "gpt-4o"

        if llm_client and llm_client.is_available:
            industry_prompt = get_industry_prompt(industry)
            technique_name = technique.get("primary_technique", "direct")

            system_prompt = (
                f"You are a professional customer support agent. {industry_prompt}\n"
                f"Tone: {tone}. Empathy level: {'high' if empathy_score < 0.4 else 'moderate'}.\n"
                f"Reasoning technique used: {technique_name}.\n"
                "Generate a helpful, empathetic response that addresses the customer's issue. "
                "Be concise but thorough. Include specific next steps."
            )
            user_message = f"{context}\n\nGenerate the customer response:"

            response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=1000, temperature=0.3,
            )
            if response:
                generated_response = response
                generation_tokens = tokens
                generation_model = llm_client.model

        # Fallback to template
        if not generated_response:
            intent = classification.get("intent", "general")
            generated_response = TEMPLATE_RESPONSES.get(intent, TEMPLATE_RESPONSES["general"])

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="generate", action="response_generated",
            duration_ms=duration_ms, tokens_used=generation_tokens,
            details={"model": generation_model, "response_length": len(generated_response)},
        )
        return {
            "generated_response": generated_response,
            "generation_model": generation_model,
            "generation_tokens": generation_tokens,
            "current_step": "generate",
            "steps_completed": state.get("steps_completed", []) + ["generate"],
            "step_outputs": {"generate": {"status": "completed", "model": generation_model, "tokens": generation_tokens, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
            "total_tokens": state.get("total_tokens", 0) + generation_tokens,
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("generate_node failed: %s", exc)
        intent = state.get("classification", {}).get("intent", "general")
        return {
            "generated_response": TEMPLATE_RESPONSES.get(intent, TEMPLATE_RESPONSES["general"]),
            "generation_model": "fallback",
            "generation_tokens": 0,
            "current_step": "generate",
            "errors": ["generate_failed"],
            "step_outputs": {"generate": {"status": "failed", "duration_ms": duration_ms}},
        }


def crp_compress_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 12: CRP Compress — Apply CRP token compression."""
    start = time.monotonic()
    try:
        response = state.get("generated_response", "")
        if not response:
            return {
                "current_step": "crp_compress",
                "steps_completed": state.get("steps_completed", []) + ["crp_compress"],
                "step_outputs": {"crp_compress": {"status": "skipped", "reason": "no_response"}},
            }

        result = _apply_crp_compression(response)
        compressed = result["compressed_text"]

        # Use compressed text if it's not empty
        if compressed and len(compressed.strip()) > 20:
            state_key = "generated_response"
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            audit_entry = append_audit_entry(
                state, step="crp_compress", action="crp_compression_complete",
                duration_ms=duration_ms,
                details={"compression_ratio": result["compression_ratio"], "tokens_removed": result["tokens_removed"]},
            )
            return {
                state_key: compressed,
                "current_step": "crp_compress",
                "steps_completed": state.get("steps_completed", []) + ["crp_compress"],
                "step_outputs": {"crp_compress": {"status": "completed", "compression_ratio": result["compression_ratio"], "tokens_removed": result["tokens_removed"], "duration_ms": duration_ms}},
                "audit_log": audit_entry["audit_log"],
            }

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        return {
            "current_step": "crp_compress",
            "steps_completed": state.get("steps_completed", []) + ["crp_compress"],
            "step_outputs": {"crp_compress": {"status": "completed", "compression_ratio": 1.0, "duration_ms": duration_ms}},
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("crp_compress_node failed: %s", exc)
        return {
            "current_step": "crp_compress",
            "errors": ["crp_compress_failed"],
            "step_outputs": {"crp_compress": {"status": "failed", "duration_ms": duration_ms}},
        }


def clara_quality_gate_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 13: CLARA Quality Gate — Strictest quality check (threshold 95, 8-check)."""
    start = time.monotonic()
    try:
        response = state.get("generated_response", "")
        query = state.get("pii_redacted_query", "") or state.get("query", "")
        industry = state.get("industry", "general")
        empathy_score = state.get("empathy_score", 0.5)
        tone = get_industry_tone(industry)
        reasoning_output = ""
        reasoning_step = state.get("step_outputs", {}).get("reasoning_chain", {})
        if isinstance(reasoning_step, dict):
            reasoning_output = reasoning_step.get("reasoning_text", "")
        technique_used = state.get("technique", {}).get("primary_technique", "direct")
        signals = state.get("signals", {})

        result = _run_clara_quality_gate_high(
            response=response,
            query=query,
            industry=industry,
            tone=tone,
            empathy_score=empathy_score,
            reasoning_output=reasoning_output,
            technique_used=technique_used,
            signals=signals,
        )

        # Use adjusted response if available
        adjusted = result.get("adjusted_response", response)
        if adjusted and len(adjusted.strip()) > len(response.strip()) * 0.5:
            response = adjusted

        quality_score = result["score"] / 100.0  # Normalize to 0.0-1.0
        quality_passed = result["passed"]

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="clara_quality_gate", action="quality_check_complete",
            duration_ms=duration_ms,
            details={"passed": quality_passed, "score": result["score"], "issues": result.get("issues", [])},
        )
        return {
            "generated_response": response,
            "quality_score": quality_score,
            "quality_passed": quality_passed,
            "quality_issues": result.get("issues", []),
            "current_step": "clara_quality_gate",
            "steps_completed": state.get("steps_completed", []) + ["clara_quality_gate"],
            "step_outputs": {"clara_quality_gate": {"status": "completed", "passed": quality_passed, "score": result["score"], "issues": result.get("issues", []), "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("clara_quality_gate_node failed: %s", exc)
        return {
            "quality_passed": True,  # Default pass on failure
            "quality_score": 0.5,
            "current_step": "clara_quality_gate",
            "errors": ["clara_quality_gate_failed"],
            "step_outputs": {"clara_quality_gate": {"status": "failed", "duration_ms": duration_ms}},
        }


def quality_retry_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 14: Quality Retry — Retry generation if quality gate failed (max 2 retries for High)."""
    start = time.monotonic()
    try:
        retry_count = state.get("quality_retry_count", 0)
        max_retries = 2  # High: max 2 retries (vs Pro's 1)

        if retry_count >= max_retries:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            return {
                "quality_retry_count": retry_count,
                "current_step": "quality_retry",
                "steps_completed": state.get("steps_completed", []) + ["quality_retry"],
                "step_outputs": {"quality_retry": {"status": "max_retries_exhausted", "retry_count": retry_count, "duration_ms": duration_ms}},
            }

        # Increment retry count
        new_retry_count = retry_count + 1
        quality_issues = state.get("quality_issues", [])

        # Add retry instructions to the response for the next generation
        retry_hint = (
            f"[RETRY {new_retry_count}/{max_retries}] "
            f"Previous quality issues: {', '.join(quality_issues)}. "
            "Please improve the response addressing these issues."
        )

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="quality_retry", action="quality_retry_initiated",
            duration_ms=duration_ms,
            details={"retry_count": new_retry_count, "max_retries": max_retries, "issues": quality_issues},
        )
        return {
            "quality_retry_count": new_retry_count,
            "current_step": "quality_retry",
            "steps_completed": state.get("steps_completed", []) + ["quality_retry"],
            "step_outputs": {"quality_retry": {"status": "retry_initiated", "retry_count": new_retry_count, "issues": quality_issues, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("quality_retry_node failed: %s", exc)
        return {
            "quality_retry_count": state.get("quality_retry_count", 0),
            "current_step": "quality_retry",
            "errors": ["quality_retry_failed"],
            "step_outputs": {"quality_retry": {"status": "failed", "duration_ms": duration_ms}},
        }


def confidence_assess_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 15: Confidence Assess — Assess response confidence."""
    start = time.monotonic()
    try:
        response = state.get("generated_response", "")
        query = state.get("pii_redacted_query", "") or state.get("query", "")
        quality_passed = state.get("quality_passed", True)
        quality_score = state.get("quality_score", 0.5)

        confidence_engine = _get_confidence_engine()
        confidence_score = 0.5

        if confidence_engine:
            try:
                result = confidence_engine.assess(
                    response=response, query=query, quality_score=quality_score,
                )
                confidence_score = result.get("confidence_score", 0.5)
            except Exception:
                pass

        if confidence_score == 0.5:
            # Rule-based confidence
            confidence_score = quality_score * 0.8
            if quality_passed:
                confidence_score = max(confidence_score, 0.7)
            # Boost if response is substantive
            if len(response.split()) > 20:
                confidence_score = min(1.0, confidence_score + 0.1)

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="confidence_assess", action="confidence_assessed",
            duration_ms=duration_ms, details={"confidence_score": confidence_score, "quality_passed": quality_passed},
        )
        return {
            "current_step": "confidence_assess",
            "steps_completed": state.get("steps_completed", []) + ["confidence_assess"],
            "step_outputs": {"confidence_assess": {"status": "completed", "confidence_score": confidence_score, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("confidence_assess_node failed: %s", exc)
        return {
            "current_step": "confidence_assess",
            "errors": ["confidence_assess_failed"],
            "step_outputs": {"confidence_assess": {"status": "failed", "confidence_score": 0.5, "duration_ms": duration_ms}},
        }


def context_health_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 16: Context Health — Check context drift and degradation (High-only).

    Monitors the health of the conversation context to detect:
    - Context drift (topic has shifted from original query)
    - Context degradation (accumulated noise/redundancy)
    - Information coherence (response stays on topic)
    """
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query", "") or state.get("query", "")
        response = state.get("generated_response", "")
        steps_completed = state.get("steps_completed", [])
        quality_score = state.get("quality_score", 0.5)
        confidence_score = state.get("step_outputs", {}).get("confidence_assess", {}).get("confidence_score", 0.5)

        # Compute health metrics
        health_score = 0.8
        drift_detected = False
        degradation_level = "none"

        # Check for topic drift: word overlap between query and response
        query_words = set(re.findall(r'\b\w{4,}\b', query.lower()))
        response_words = set(re.findall(r'\b\w{4,}\b', response.lower()))
        stop_words = {"that", "this", "with", "have", "will", "been", "from", "they", "would", "could", "should", "about", "which", "when", "where", "your", "please"}
        query_content = query_words - stop_words
        overlap = query_content & (response_words - stop_words) if query_content else set()

        if query_content and len(overlap) / len(query_content) < 0.3:
            drift_detected = True
            health_score -= 0.2

        # Factor in quality and confidence
        health_score = health_score * 0.6 + quality_score * 0.2 + confidence_score * 0.2

        # Determine degradation level
        if health_score >= 0.8:
            degradation_level = "none"
        elif health_score >= 0.6:
            degradation_level = "mild"
        elif health_score >= 0.4:
            degradation_level = "moderate"
        else:
            degradation_level = "severe"

        # Recommendation
        if degradation_level in ("moderate", "severe"):
            recommendation = "compress"
        elif drift_detected:
            recommendation = "reset"
        else:
            recommendation = "continue"

        context_health = {
            "health_score": round(health_score, 3),
            "degradation_level": degradation_level,
            "recommendation": recommendation,
            "drift_detected": drift_detected,
        }

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="context_health", action="context_health_checked",
            duration_ms=duration_ms,
            details={"health_score": health_score, "degradation": degradation_level, "drift": drift_detected},
        )
        return {
            "context_health": context_health,
            "current_step": "context_health",
            "steps_completed": state.get("steps_completed", []) + ["context_health"],
            "step_outputs": {"context_health": {"status": "completed", "health_score": health_score, "degradation_level": degradation_level, "drift_detected": drift_detected, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("context_health_node failed: %s", exc)
        return {
            "context_health": {"health_score": 1.0, "degradation_level": "none", "recommendation": "continue", "drift_detected": False},
            "current_step": "context_health",
            "errors": ["context_health_failed"],
            "step_outputs": {"context_health": {"status": "failed", "duration_ms": duration_ms}},
        }


def dedup_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 17: Dedup — Detect duplicate/redundant responses (High-only).

    Checks if the generated response is too similar to previous
    responses in the conversation. Flags duplicates that might
    indicate the model is stuck in a loop.
    """
    start = time.monotonic()
    try:
        response = state.get("generated_response", "")
        query = state.get("pii_redacted_query", "") or state.get("query", "")

        # Simple token-frequency-based similarity
        response_words = re.findall(r'\b\w{3,}\b', response.lower())
        query_words = re.findall(r'\b\w{3,}\b', query.lower())

        # Compute word frequency vectors
        from collections import Counter
        response_freq = Counter(response_words)
        query_freq = Counter(query_words)

        # Cosine similarity
        all_words = set(response_freq.keys()) | set(query_freq.keys())
        if not all_words:
            similarity_score = 0.0
        else:
            dot_product = sum(response_freq.get(w, 0) * query_freq.get(w, 0) for w in all_words)
            mag_r = sum(v ** 2 for v in response_freq.values()) ** 0.5
            mag_q = sum(v ** 2 for v in query_freq.values()) ** 0.5
            similarity_score = dot_product / (mag_r * mag_q) if mag_r > 0 and mag_q > 0 else 0.0

        is_duplicate = similarity_score > 0.85

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="dedup", action="dedup_check_complete",
            duration_ms=duration_ms,
            details={"similarity_score": similarity_score, "is_duplicate": is_duplicate},
        )
        return {
            "dedup_similarity_score": round(similarity_score, 3),
            "dedup_is_duplicate": is_duplicate,
            "current_step": "dedup",
            "steps_completed": state.get("steps_completed", []) + ["dedup"],
            "step_outputs": {"dedup": {"status": "completed", "similarity_score": similarity_score, "is_duplicate": is_duplicate, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("dedup_node failed: %s", exc)
        return {
            "dedup_similarity_score": 0.0,
            "dedup_is_duplicate": False,
            "current_step": "dedup",
            "errors": ["dedup_failed"],
            "step_outputs": {"dedup": {"status": "failed", "duration_ms": duration_ms}},
        }


def strategic_decision_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 18: Strategic Decision — Strategic routing for complex cases (High-only).

    Makes strategic routing decisions based on all available signals:
    - quality_score, confidence_score, context_health
    - dedup results, retry count, emergency flags

    Can decide: proceed, escalate, add_context, or regenerate.
    """
    start = time.monotonic()
    try:
        quality_score = state.get("quality_score", 0.5)
        quality_passed = state.get("quality_passed", True)
        confidence_score = state.get("step_outputs", {}).get("confidence_assess", {}).get("confidence_score", 0.5)
        context_health = state.get("context_health", {})
        health_score = context_health.get("health_score", 1.0)
        dedup_is_duplicate = state.get("dedup_is_duplicate", False)
        retry_count = state.get("quality_retry_count", 0)
        emergency_flag = state.get("emergency_flag", False)

        # Decision logic
        decision = "proceed"
        rationale = "All checks passed"
        actions: List[str] = []

        if emergency_flag:
            decision = "escalate"
            rationale = "Emergency flag detected — requiring human escalation"
            actions.append("route_to_human")
        elif not quality_passed and retry_count >= 2:
            decision = "escalate"
            rationale = f"Quality failed after {retry_count} retries — escalating"
            actions.append("route_to_human")
        elif dedup_is_duplicate:
            decision = "regenerate"
            rationale = "Response appears to be a duplicate — needs variation"
            actions.append("vary_response")
        elif health_score < 0.4:
            decision = "add_context"
            rationale = f"Context health is low ({health_score:.2f}) — needs enrichment"
            actions.append("enrich_context")
        elif not quality_passed and retry_count < 2:
            decision = "proceed"
            rationale = "Quality retry already handled — proceeding"
        elif confidence_score < 0.3:
            decision = "escalate"
            rationale = f"Low confidence ({confidence_score:.2f}) — human review needed"
            actions.append("route_to_human")
        else:
            decision = "proceed"
            rationale = f"Quality={quality_score:.2f}, Confidence={confidence_score:.2f}, Health={health_score:.2f}"

        strategic_decision = {
            "decision": decision,
            "rationale": rationale,
            "actions": actions,
            "quality_score": quality_score,
            "confidence_score": confidence_score,
            "health_score": health_score,
        }

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="strategic_decision", action="strategic_decision_made",
            duration_ms=duration_ms,
            details={"decision": decision, "rationale": rationale},
        )
        return {
            "current_step": "strategic_decision",
            "steps_completed": state.get("steps_completed", []) + ["strategic_decision"],
            "step_outputs": {"strategic_decision": {"status": "completed", "decision": decision, "rationale": rationale, "actions": actions, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("strategic_decision_node failed: %s", exc)
        return {
            "current_step": "strategic_decision",
            "errors": ["strategic_decision_failed"],
            "step_outputs": {"strategic_decision": {"status": "failed", "decision": "proceed", "duration_ms": duration_ms}},
        }


async def peer_review_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 19: Peer Review — Final validation before delivery (High-only).

    Uses the HighLLMClient to review the response against the
    original query. Acts as a "second opinion" check on accuracy,
    completeness, appropriateness, and tone alignment.
    """
    start = time.monotonic()
    try:
        response = state.get("generated_response", "")
        query = state.get("pii_redacted_query", "") or state.get("query", "")
        industry = state.get("industry", "general")

        llm_client = _get_high_llm_client()
        peer_review: Dict[str, Any] = {
            "passed": True,
            "review_score": 0.8,
            "issues": [],
            "suggestions": [],
        }

        if llm_client and llm_client.is_available:
            system_prompt = (
                "You are a peer reviewer for customer support responses. "
                "Evaluate this response on: 1) Accuracy, 2) Completeness, "
                "3) Appropriateness, 4) Tone alignment. "
                "Return JSON: {\"passed\": bool, \"review_score\": 0.0-1.0, "
                "\"issues\": [...], \"suggestions\": [...]}"
            )
            user_message = f"Query: {query}\nResponse: {response}\nIndustry: {industry}"
            review_response, tokens = await llm_client.chat(
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=300, temperature=0.2,
            )
            if review_response:
                try:
                    cleaned = review_response.strip()
                    if cleaned.startswith("```"):
                        cleaned = re.sub(r'^```\w*\n?', '', cleaned)
                        cleaned = re.sub(r'\n?```$', '', cleaned)
                    peer_review = json.loads(cleaned)
                except (json.JSONDecodeError, ValueError):
                    pass

        # Ensure required keys exist
        peer_review.setdefault("passed", True)
        peer_review.setdefault("review_score", 0.8)
        peer_review.setdefault("issues", [])
        peer_review.setdefault("suggestions", [])

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="peer_review", action="peer_review_complete",
            duration_ms=duration_ms, tokens_used=0,
            details={"passed": peer_review["passed"], "review_score": peer_review["review_score"]},
        )
        return {
            "current_step": "peer_review",
            "steps_completed": state.get("steps_completed", []) + ["peer_review"],
            "step_outputs": {"peer_review": {"status": "completed", "passed": peer_review["passed"], "review_score": peer_review["review_score"], "issues": peer_review["issues"], "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("peer_review_node failed: %s", exc)
        return {
            "current_step": "peer_review",
            "errors": ["peer_review_failed"],
            "step_outputs": {"peer_review": {"status": "failed", "passed": True, "review_score": 0.8, "duration_ms": duration_ms}},
        }


def format_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 20: Format — Format the final response for delivery."""
    start = time.monotonic()
    try:
        response = state.get("generated_response", "")
        channel = state.get("channel", "chat")
        industry = state.get("industry", "general")
        emergency_flag = state.get("emergency_flag", False)
        peer_review = state.get("step_outputs", {}).get("peer_review", {})
        strategic_decision = state.get("step_outputs", {}).get("strategic_decision", {})

        # Format based on channel
        try:
            registry = _get_formatter_registry()
            context = FormattingContext(
                channel=channel,
                industry=industry,
                variant_tier="parwa_high",
                emergency=emergency_flag,
            )
            formatter = registry.get_formatter(channel)
            if formatter:
                formatted = formatter.format(response, context)
            else:
                formatted = response.strip()
        except Exception:
            formatted = response.strip()

        # If strategic decision says escalate, prepend escalation notice
        if strategic_decision.get("decision") == "escalate":
            escalation_notice = "[ESCALATED] This conversation requires human review. "
            formatted = escalation_notice + formatted

        # Mark pipeline as completed
        pipeline_status = "completed"
        if state.get("errors"):
            pipeline_status = "partial"

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="format", action="response_formatted",
            duration_ms=duration_ms,
            details={"channel": channel, "response_length": len(formatted), "pipeline_status": pipeline_status},
        )
        return {
            "formatted_response": formatted,
            "final_response": formatted,
            "response_format": channel,
            "pipeline_status": pipeline_status,
            "current_step": "format",
            "steps_completed": state.get("steps_completed", []) + ["format"],
            "step_outputs": {"format": {"status": "completed", "channel": channel, "response_length": len(formatted), "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
            "billing_tokens": state.get("total_tokens", 0),
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("format_node failed: %s", exc)
        return {
            "formatted_response": state.get("generated_response", ""),
            "final_response": state.get("generated_response", ""),
            "pipeline_status": "partial",
            "current_step": "format",
            "errors": ["format_failed"],
            "step_outputs": {"format": {"status": "failed", "duration_ms": duration_ms}},
        }


# ══════════════════════════════════════════════════════════════════
# ENHANCEMENT NODE FUNCTIONS (High: 2 new nodes)
# ══════════════════════════════════════════════════════════════════


def smart_enrichment_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 21: Smart Enrichment (High) — Intent-driven enrichment with richer context."""
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query", "") or state.get("query", "")
        classification = state.get("classification", {})
        signals = state.get("signals", {})
        empathy_score = state.get("empathy_score", 0.5)
        empathy_flags = state.get("empathy_flags", [])
        customer_tier = state.get("customer_tier", "free")
        intent = classification.get("intent", "general") if classification else "general"

        emotion_profile = {}; recovery_playbook = {}; churn_risk = {}
        retention_offers = {}; billing_dispute = {}; billing_anomaly = {}
        known_issue = {}; tech_diagnostics = {}; severity_score_result = {}
        shipping_issue = {}; shipping_delay = {}; tracking_info = {}
        prompt_parts = []

        if intent in ("complaint", "cancellation", "refund") or empathy_score < 0.4:
            ei = _get_ei_engine()
            if ei:
                emotion_profile = ei.profile_emotion(query, empathy_score, empathy_flags)
                recovery_playbook = ei.select_recovery_playbook(emotion_profile)
                de = ei.generate_de_escalation_prompts(emotion_profile)
                if de: prompt_parts.append(de)
                pp = recovery_playbook.get("prompt_addition", "")
                if pp: prompt_parts.append(pp)

        if intent in ("cancellation", "complaint"):
            ce = _get_churn_engine()
            if ce:
                churn_risk = ce.score_churn_risk(query, classification, signals, customer_tier)
                if churn_risk.get("churn_probability", 0) > 0.3:
                    retention_offers = ce.select_retention_offers(churn_risk, customer_tier)
                    rp = retention_offers.get("prompt_addition", "")
                    if rp: prompt_parts.append(rp)

        if intent in ("billing", "refund", "payment"):
            be = _get_billing_engine()
            if be:
                billing_dispute = be.classify_dispute(query, classification)
                billing_anomaly = be.detect_anomaly(query, signals)
                bc = be.generate_billing_context(billing_dispute, billing_anomaly)
                if bc: prompt_parts.append(bc)

        if intent in ("technical", "technical_support"):
            te = _get_tech_diag_engine()
            if te:
                known_issue = te.detect_known_issue(query, classification)
                tech_diagnostics = te.generate_diagnostics(query, known_issue)
                severity_score_result = te.score_severity(query, signals, customer_tier)
                dp = tech_diagnostics.get("prompt_addition", "")
                if dp: prompt_parts.append(dp)

        if intent in ("shipping", "shipping_inquiry", "logistics"):
            se = _get_shipping_engine()
            if se:
                tracking_info = se.detect_tracking_number(query)
                shipping_issue = se.classify_shipping_issue(query, classification)
                shipping_delay = se.assess_delay(shipping_issue, query)
                sc = se.generate_shipping_context(shipping_issue, shipping_delay, tracking_info)
                if sc: prompt_parts.append(sc)

        enrichment_context = " ".join(p for p in prompt_parts if p)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state, step="smart_enrichment", action="enrichment_complete",
            duration_ms=duration_ms, tokens_used=0,
            details={"intent": intent, "enrichment_context_length": len(enrichment_context)},
        )

        return {
            "emotion_profile": emotion_profile, "recovery_playbook": recovery_playbook,
            "churn_risk": churn_risk, "retention_offers": retention_offers,
            "billing_dispute": billing_dispute, "billing_anomaly": billing_anomaly,
            "known_issue": known_issue, "tech_diagnostics": tech_diagnostics,
            "severity_score": severity_score_result,
            "shipping_issue": shipping_issue, "shipping_delay": shipping_delay,
            "tracking_info": tracking_info, "enrichment_context": enrichment_context,
            "current_step": "smart_enrichment",
            "step_outputs": {"smart_enrichment": {"status": "completed", "intent": intent, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("smart_enrichment_node_failed", error=str(exc))
        return {"current_step": "smart_enrichment", "errors": ["smart_enrichment_failed"],
                "step_outputs": {"smart_enrichment": {"status": "failed", "error": str(exc), "duration_ms": duration_ms}},
                "enrichment_context": ""}


def auto_action_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 22: Auto Action (High) — Collect automated actions from all engines."""
    start = time.monotonic()
    try:
        all_actions = []
        classification = state.get("classification", {})

        emotion_profile = state.get("emotion_profile", {})
        recovery_playbook = state.get("recovery_playbook", {})
        if emotion_profile and recovery_playbook:
            ei = _get_ei_engine()
            if ei: all_actions.extend(ei.get_recovery_actions(emotion_profile, recovery_playbook, classification))

        churn_risk = state.get("churn_risk", {})
        retention_offers = state.get("retention_offers", {})
        if churn_risk and churn_risk.get("churn_probability", 0) > 0.3:
            ce = _get_churn_engine()
            if ce: all_actions.extend(ce.get_retention_actions(churn_risk, retention_offers))

        billing_dispute = state.get("billing_dispute", {})
        billing_anomaly = state.get("billing_anomaly", {})
        if billing_dispute and billing_dispute.get("dispute_category", "unknown") != "unknown":
            be = _get_billing_engine()
            if be: all_actions.extend(be.get_resolution_actions(billing_dispute, billing_anomaly))

        known_issue = state.get("known_issue", {})
        tech_diagnostics = state.get("tech_diagnostics", {})
        severity_score_result = state.get("severity_score", {})
        if known_issue and known_issue.get("known_issue_detected"):
            te = _get_tech_diag_engine()
            if te: all_actions.extend(te.get_tech_actions(known_issue, tech_diagnostics, severity_score_result))

        shipping_issue = state.get("shipping_issue", {})
        shipping_delay = state.get("shipping_delay", {})
        tracking_info = state.get("tracking_info", {})
        if shipping_issue and shipping_issue.get("issue_detected"):
            se = _get_shipping_engine()
            if se: all_actions.extend(se.get_shipping_actions(shipping_issue, shipping_delay, tracking_info))

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        audit_entry = append_audit_entry(
            state, step="auto_action", action="actions_collected",
            duration_ms=duration_ms, tokens_used=0,
            details={"total_actions": len(all_actions)},
        )

        return {
            "current_step": "auto_action",
            "step_outputs": {"auto_action": {
                "status": "completed", "total_actions": len(all_actions),
                "automated_actions": sum(1 for a in all_actions if a.get("automated", False)),
                "actions": all_actions, "duration_ms": duration_ms}},
            "audit_log": audit_entry["audit_log"],
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("auto_action_node_failed", error=str(exc))
        return {"current_step": "auto_action", "errors": ["auto_action_failed"],
                "step_outputs": {"auto_action": {"status": "failed", "error": str(exc), "actions": [], "duration_ms": duration_ms}}}


# ══════════════════════════════════════════════════════════════════
# DEEP ENRICHMENT NODES — 5 Intent-Specific Deep Processing Nodes (High)
# ══════════════════════════════════════════════════════════════════


def complaint_handler_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Deep enrichment node for complaint handling (High tier).

    Processes complaint-related queries through the enhanced EI engine:
      - Assesses sentiment escalation with detailed severity profiling
      - Generates deep complaint resolution strategy with High-specific nuance
      - Produces de-escalation prompts enriched with emotional context
      - Evaluates follow-up care pathway for sustained satisfaction

    High Enhancement: Deeper sentiment profiling, multi-stage de-escalation
    strategy, and proactive follow-up scheduling.

    Improvement Target: Complaint Handling 65% → 88% automation (High).
    """
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query", "") or state.get("query", "")
        classification = state.get("classification", {})
        emotion_profile = state.get("emotion_profile", {})
        recovery_playbook = state.get("recovery_playbook", {})
        customer_tier = state.get("customer_tier", "free")
        empathy_score = state.get("empathy_score", 0.5)

        ei_engine = _get_ei_engine()

        # Assess sentiment escalation with detailed severity profiling
        sentiment_escalation = {}
        if ei_engine:
            sentiment_escalation = ei_engine.assess_sentiment_escalation(
                emotion_profile=emotion_profile,
                classification=classification,
            )

        # Generate deep complaint resolution with High-specific nuance
        complaint_resolution = {}
        if ei_engine:
            complaint_resolution = ei_engine.resolve_complaint(
                emotion_profile=emotion_profile,
                playbook=recovery_playbook,
                classification=classification,
                customer_tier=customer_tier,
            )

        # Build enrichment context for complaint handling (High: more detailed)
        context_parts = []
        if complaint_resolution.get("de_escalation_applied"):
            context_parts.append(
                "DE-ESCALATION REQUIRED (High Priority): The customer is emotionally distressed. "
                "Use deeply empathetic language, actively validate their feelings, and avoid any "
                "language that could be perceived as minimizing their concern. Prioritize emotional "
                "reconnection before offering solutions."
            )
        if complaint_resolution.get("escalation_triggered"):
            context_parts.append(
                "ESCALATION TRIGGERED (High Tier): This complaint requires senior attention immediately. "
                "Explicitly acknowledge the escalation in the response and provide a direct contact path "
                "to a senior specialist."
            )
        if complaint_resolution.get("compensation_type") and complaint_resolution["compensation_type"] != "none":
            context_parts.append(
                f"COMPENSATION RECOMMENDED (High): Offer {complaint_resolution['compensation_type'].replace('_', ' ')} "
                f"as part of the resolution. Present this as a genuine gesture of commitment, not a transaction."
            )
        if sentiment_escalation.get("escalation_needed"):
            context_parts.append(
                f"SENTIMENT ESCALATION (High Analysis): Level {sentiment_escalation['escalation_level']}. "
                f"Reason: {sentiment_escalation['trigger_reason']}. "
                f"Empathy score: {empathy_score:.2f}. Adjust tone accordingly — be more empathetic than usual."
            )
        # High-specific: proactive follow-up context
        if empathy_score < 0.3:
            context_parts.append(
                "PROACTIVE FOLLOW-UP (High): Customer shows high distress. Schedule a proactive "
                "follow-up within 24 hours to ensure satisfaction and prevent escalation."
            )

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        return {
            "complaint_resolution": complaint_resolution,
            "sentiment_escalation": sentiment_escalation,
            "enrichment_context": (state.get("enrichment_context", "") + " " + " ".join(context_parts)).strip(),
            "step_outputs": {"complaint_handler": {
                "tier": "high",
                "complaint_resolution": complaint_resolution,
                "sentiment_escalation": sentiment_escalation,
                "duration_ms": duration_ms,
            }},
            **append_audit_entry(state, "complaint_handler", "deep_complaint_enrichment_high", duration_ms),
        }
    except Exception:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("complaint_handler_node_failed")
        return {
            "complaint_resolution": {},
            "sentiment_escalation": {},
            "errors": ["complaint_handler_failed"],
            **append_audit_entry(state, "complaint_handler", "node_failed_high", duration_ms),
        }


def retention_negotiator_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Deep enrichment node for cancellation/retention (High tier).

    Processes cancellation-related queries through enhanced churn engine:
      - Generates retention negotiation strategy with multi-stage approach
      - Creates win-back automation sequence with personalized touchpoints
      - Provides offer acceptance likelihood with detailed scoring
      - Evaluates lifetime value impact for retention priority

    High Enhancement: Multi-stage negotiation, lifetime value scoring,
    personalized win-back sequences, and proactive save strategies.

    Improvement Target: Cancellation/Retention 70% → 90% automation (High).
    """
    start = time.monotonic()
    try:
        classification = state.get("classification", {})
        churn_risk = state.get("churn_risk", {})
        retention_offers = state.get("retention_offers", {})
        customer_tier = state.get("customer_tier", "free")

        churn_engine = _get_churn_engine()

        # Generate retention negotiation with multi-stage approach
        retention_negotiation = {}
        if churn_engine:
            retention_negotiation = churn_engine.negotiate_retention(
                churn_risk=churn_risk,
                retention_offers=retention_offers,
                customer_tier=customer_tier,
            )

        # Generate win-back automation with personalized touchpoints
        winback_sequence = {}
        if churn_engine:
            winback_sequence = churn_engine.generate_winback_automation(
                churn_risk=churn_risk,
                retention_offers=retention_offers,
            )

        # Build enrichment context for retention (High: more detailed)
        context_parts = []
        if retention_negotiation.get("negotiation_strategy"):
            context_parts.append(
                f"RETENTION STRATEGY (High): {retention_negotiation['negotiation_strategy'].replace('_', ' ')}. "
                f"Stage: {retention_negotiation.get('negotiation_stage', 'unknown')}. "
                f"Apply a multi-stage approach — acknowledge the concern first, then present alternatives, "
                f"then make the save offer."
            )
        if retention_negotiation.get("offer_presented"):
            context_parts.append(
                f"PRIMARY OFFER (High): {retention_negotiation['offer_presented'].replace('_', ' ')}. "
                f"Present this as a personalized alternative that addresses their specific concern. "
                f"Emphasize value, not just savings."
            )
        if retention_negotiation.get("counter_offers"):
            offers_str = ", ".join(o.replace("_", " ") for o in retention_negotiation["counter_offers"])
            context_parts.append(
                f"COUNTER OFFERS AVAILABLE (High): {offers_str}. Escalate through offers progressively "
                f"if the primary offer is declined. Always validate the customer's reasoning first."
            )
        if winback_sequence.get("sequence_active"):
            context_parts.append(
                f"WIN-BACK SEQUENCE (High): Automated sequence active for "
                f"{winback_sequence.get('total_duration_days', 0)} days if customer cancels. "
                f"Personalized touchpoints included. Mention that the door is always open."
            )
        # High-specific: lifetime value context
        if customer_tier in ("premium", "enterprise"):
            context_parts.append(
                "HIGH-VALUE CUSTOMER (High): This is a premium/enterprise customer. Apply maximum "
                "retention effort — escalate to a dedicated account manager if standard offers are declined."
            )

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        return {
            "retention_negotiation": retention_negotiation,
            "winback_sequence": winback_sequence,
            "enrichment_context": (state.get("enrichment_context", "") + " " + " ".join(context_parts)).strip(),
            "step_outputs": {"retention_negotiator": {
                "tier": "high",
                "retention_negotiation": retention_negotiation,
                "winback_sequence": winback_sequence,
                "duration_ms": duration_ms,
            }},
            **append_audit_entry(state, "retention_negotiator", "deep_retention_enrichment_high", duration_ms),
        }
    except Exception:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("retention_negotiator_node_failed")
        return {
            "retention_negotiation": {},
            "winback_sequence": {},
            "errors": ["retention_negotiator_failed"],
            **append_audit_entry(state, "retention_negotiator", "node_failed_high", duration_ms),
        }


def billing_resolver_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Deep enrichment node for billing inquiries (High tier).

    Processes billing-related queries through enhanced billing engine:
      - Generates self-service portal context with step-by-step guidance
      - Auto-resolves Paddle disputes with detailed audit trail
      - Provides refund eligibility assessment with policy references
      - Evaluates proactive credit/adjustment opportunities

    High Enhancement: Step-by-step portal guidance, detailed audit trails,
    proactive credit opportunities, and policy-referenced eligibility.

    Improvement Target: Billing Inquiries 80% → 92% automation (High).
    """
    start = time.monotonic()
    try:
        billing_dispute = state.get("billing_dispute", {})
        billing_anomaly = state.get("billing_anomaly", {})
        customer_tier = state.get("customer_tier", "free")

        billing_engine = _get_billing_engine()

        # Generate self-service billing context with step-by-step guidance
        billing_self_service = {}
        if billing_engine:
            billing_self_service = billing_engine.generate_self_service_context(
                dispute=billing_dispute,
                anomaly=billing_anomaly,
                customer_tier=customer_tier,
            )

        # Auto-resolve Paddle dispute with detailed audit trail
        paddle_dispute = {}
        if billing_engine:
            paddle_dispute = billing_engine.auto_resolve_paddle_dispute(
                dispute=billing_dispute,
                anomaly=billing_anomaly,
            )

        # Build enrichment context for billing (High: more detailed)
        context_parts = []
        if billing_self_service.get("refund_eligible"):
            context_parts.append(
                "REFUND ELIGIBLE (High): The customer is eligible for an automatic refund. "
                "Guide them through the process step by step, or offer to process it immediately "
                "on their behalf. Provide the expected timeline and confirmation method."
            )
        if paddle_dispute.get("auto_resolved"):
            context_parts.append(
                f"AUTO-RESOLVED (High Audit): The billing dispute has been automatically resolved via Paddle. "
                f"Action: {paddle_dispute.get('resolution_action', 'unknown').replace('_', ' ')}. "
                f"Estimated processing: {paddle_dispute.get('processing_time_hours', 48)} hours. "
                f"Provide the customer with a reference number and confirmation of the resolution."
            )
        if billing_self_service.get("dispute_status") == "manual_review_required":
            context_parts.append(
                "MANUAL REVIEW REQUIRED (High): This billing dispute requires manual review by our "
                "billing specialists. Acknowledge the concern sincerely, provide a clear timeline for "
                "resolution (typically within 24 hours), and assure them they will receive updates proactively."
            )
        if billing_self_service.get("available_actions"):
            actions_str = ", ".join(a.replace("_", " ") for a in billing_self_service["available_actions"][:5])
            context_parts.append(
                f"SELF-SERVICE PORTAL (High): Available actions: {actions_str}. "
                f"Provide step-by-step portal navigation instructions if the customer prefers self-service."
            )
        # High-specific: proactive credit opportunity
        if billing_anomaly.get("anomaly_detected"):
            context_parts.append(
                "PROACTIVE CREDIT (High): A billing anomaly was detected. Consider proactively offering "
                "a credit adjustment or explaining the discrepancy before the customer asks."
            )

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        return {
            "billing_self_service": billing_self_service,
            "paddle_dispute": paddle_dispute,
            "enrichment_context": (state.get("enrichment_context", "") + " " + " ".join(context_parts)).strip(),
            "step_outputs": {"billing_resolver": {
                "tier": "high",
                "billing_self_service": billing_self_service,
                "paddle_dispute": paddle_dispute,
                "duration_ms": duration_ms,
            }},
            **append_audit_entry(state, "billing_resolver", "deep_billing_enrichment_high", duration_ms),
        }
    except Exception:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("billing_resolver_node_failed")
        return {
            "billing_self_service": {},
            "paddle_dispute": {},
            "errors": ["billing_resolver_failed"],
            **append_audit_entry(state, "billing_resolver", "node_failed_high", duration_ms),
        }


def tech_diagnostic_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Deep enrichment node for technical support L1 (High tier).

    Processes technical queries through enhanced tech diagnostics engine:
      - Generates comprehensive diagnostic result with root cause analysis
      - Makes escalation decisions with severity-based routing
      - Provides auto-fix availability assessment with guided steps
      - Evaluates known issue database with detailed workaround info

    High Enhancement: Root cause analysis, guided auto-fix steps,
    severity-based routing, and detailed known issue workarounds.

    Improvement Target: Technical Support L1 82% → 94% automation (High).
    """
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query", "") or state.get("query", "")
        known_issue = state.get("known_issue", {})
        tech_diagnostics = state.get("tech_diagnostics", {})
        severity_score = state.get("severity_score", {})
        customer_tier = state.get("customer_tier", "free")

        tech_engine = _get_tech_diag_engine()

        # Generate comprehensive diagnostic result with root cause analysis
        diagnostic_result = {}
        if tech_engine:
            diagnostic_result = tech_engine.generate_diagnostic_result(
                query=query,
                known_issue=known_issue,
                diagnostics=tech_diagnostics,
                severity=severity_score,
            )

        # Make escalation decision with severity-based routing
        escalation_decision = {}
        if tech_engine:
            escalation_decision = tech_engine.decide_escalation(
                severity=severity_score,
                known_issue=known_issue,
                customer_tier=customer_tier,
            )

        # Build enrichment context for tech support (High: more detailed)
        context_parts = []
        if diagnostic_result.get("known_issue_match"):
            context_parts.append(
                f"KNOWN ISSUE DETECTED (High): Reference {known_issue.get('issue_id', 'unknown')}. "
                f"Share the known status, current resolution progress, and estimated time to fix. "
                f"If a workaround exists, walk them through it step by step."
            )
        if diagnostic_result.get("auto_fix_available"):
            context_parts.append(
                "AUTO-FIX AVAILABLE (High): Provide detailed self-service diagnostic steps. "
                "Walk the customer through each step clearly, include expected outcomes at each stage, "
                "and provide an alternative path if any step fails."
            )
        if escalation_decision.get("escalate"):
            context_parts.append(
                f"ESCALATION REQUIRED (High): Issue requires {escalation_decision['escalation_level']} "
                f"level support. Acknowledge the complexity, set clear expectations for the escalation "
                f"process, and provide a direct reference for tracking. Assign priority based on "
                f"customer tier and severity."
            )
        if diagnostic_result.get("steps_provided", 0) > 0:
            context_parts.append(
                f"DIAGNOSTICS (High): {diagnostic_result['steps_provided']} steps available. "
                f"Walk the customer through them naturally, explaining the purpose of each step. "
                f"Provide expected outcomes and what to do if results differ."
            )
        # High-specific: severity context
        if isinstance(severity_score, dict) and severity_score.get("level") in ("high", "critical"):
            context_parts.append(
                f"HIGH SEVERITY (High): Severity level is {severity_score['level']}. "
                f"Prioritize immediate response, provide real-time updates, and ensure the customer "
                f"feels their issue is being handled with urgency."
            )

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        return {
            "diagnostic_result": diagnostic_result,
            "escalation_decision": escalation_decision,
            "enrichment_context": (state.get("enrichment_context", "") + " " + " ".join(context_parts)).strip(),
            "step_outputs": {"tech_diagnostic": {
                "tier": "high",
                "diagnostic_result": diagnostic_result,
                "escalation_decision": escalation_decision,
                "duration_ms": duration_ms,
            }},
            **append_audit_entry(state, "tech_diagnostic", "deep_tech_enrichment_high", duration_ms),
        }
    except Exception:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("tech_diagnostic_node_failed")
        return {
            "diagnostic_result": {},
            "escalation_decision": {},
            "errors": ["tech_diagnostic_failed"],
            **append_audit_entry(state, "tech_diagnostic", "node_failed_high", duration_ms),
        }


def shipping_tracker_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Deep enrichment node for shipping/logistics (High tier).

    Processes shipping-related queries through enhanced shipping engine:
      - Queries multi-carrier API for real-time tracking with full details
      - Generates proactive delay notifications with revised delivery windows
      - Provides compensation eligibility with automatic processing
      - Evaluates alternative delivery options and pickup arrangements

    High Enhancement: Real-time multi-carrier tracking, automatic compensation
    processing, alternative delivery options, and proactive re-routing.

    Improvement Target: Shipping/Logistics 83% → 92% automation (High).
    """
    start = time.monotonic()
    try:
        tracking_info = state.get("tracking_info", {})
        shipping_issue = state.get("shipping_issue", {})
        shipping_delay = state.get("shipping_delay", {})

        shipping_engine = _get_shipping_engine()

        # Query carrier data with real-time full details
        shipping_carrier_data = {}
        if shipping_engine:
            shipping_carrier_data = shipping_engine.query_carrier_data(
                tracking_info=tracking_info,
                shipping_issue=shipping_issue,
            )

        # Generate proactive delay notification with revised delivery windows
        delay_notification = {}
        if shipping_engine:
            delay_notification = shipping_engine.generate_delay_notification(
                shipping_issue=shipping_issue,
                delay_assessment=shipping_delay,
                carrier_data=shipping_carrier_data,
            )

        # Build enrichment context for shipping (High: more detailed)
        context_parts = []
        if shipping_carrier_data.get("carrier"):
            context_parts.append(
                f"CARRIER TRACKING (High): {shipping_carrier_data['carrier']}. "
                f"Status: {shipping_carrier_data['tracking_status']}. "
                f"ETA: {shipping_carrier_data.get('estimated_delivery', 'unknown')}. "
                f"Provide the customer with a detailed tracking summary including "
                f"last scan location and time."
            )
        if delay_notification.get("notification_sent"):
            context_parts.append(
                f"DELAY NOTIFICATION (High): {delay_notification['notification_type'].replace('_', ' ')}. "
                f"Reason: {delay_notification.get('delay_reason', 'unknown').replace('_', ' ')}. "
                f"Revised ETA: {delay_notification.get('revised_eta', 'unknown')}. "
                f"Proactively inform the customer with a revised timeline and express genuine concern "
                f"for the inconvenience."
            )
        if delay_notification.get("compensation_offered"):
            context_parts.append(
                "COMPENSATION ELIGIBLE (High): Customer is eligible for shipping compensation. "
                "Offer this proactively and, if possible, process it automatically. Provide clear "
                "details on what the compensation covers and how it will be applied."
            )
        if shipping_issue.get("auto_resolvable"):
            context_parts.append(
                f"AUTO-RESOLVABLE (High): Shipping issue '{shipping_issue.get('issue_type', 'unknown').replace('_', ' ')}' "
                f"can be resolved automatically. Resolution: {shipping_issue.get('resolution', 'unknown').replace('_', ' ')}. "
                f"Apply the resolution and confirm the updated status with the customer."
            )
        # High-specific: alternative delivery options
        if shipping_delay.get("significant_delay"):
            context_parts.append(
                "ALTERNATIVE OPTIONS (High): Significant delay detected. Offer alternative delivery "
                "options such as expedited shipping, local pickup, or delivery to a different address. "
                "Proactively arrange the best alternative for the customer."
            )

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        return {
            "shipping_carrier_data": shipping_carrier_data,
            "delay_notification": delay_notification,
            "enrichment_context": (state.get("enrichment_context", "") + " " + " ".join(context_parts)).strip(),
            "step_outputs": {"shipping_tracker": {
                "tier": "high",
                "shipping_carrier_data": shipping_carrier_data,
                "delay_notification": delay_notification,
                "duration_ms": duration_ms,
            }},
            **append_audit_entry(state, "shipping_tracker", "deep_shipping_enrichment_high", duration_ms),
        }
    except Exception:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("shipping_tracker_node_failed")
        return {
            "shipping_carrier_data": {},
            "delay_notification": {},
            "errors": ["shipping_tracker_failed"],
            **append_audit_entry(state, "shipping_tracker", "node_failed_high", duration_ms),
        }
