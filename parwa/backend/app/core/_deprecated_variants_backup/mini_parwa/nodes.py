"""
Mini Parwa Pipeline Nodes — 10 agent-nodes for the LangGraph pipeline.

Pipeline: pii_check -> empathy_check -> emergency_check -> gsd_state
        -> extract_signals -> classify -> generate -> crp_compress
        -> clara_quality_gate -> format -> END

Each node:
  - Takes ParwaGraphState dict as input
  - Returns a dict with ONLY the fields it modified (LangGraph merges these)
  - Is wrapped in try/except (BC-008: never crash)
  - Appends to audit_log and errors using reducer pattern
  - Tracks timing in step_outputs

Connected Frameworks (Tier 1 — Always Active, Even in Mini):
  - CLARA (Concise Logical Adaptive Response Architecture) — Quality gate
  - CRP (Concise Response Protocol) — Token waste elimination
  - GSD (Guided Support Dialogue) — State machine tracking
  - Smart Router (F-054) — Model tier selection (Light only for Mini)
  - Technique Router (BC-013) — Technique selection (Tier 1 only for Mini)
  - Confidence Scoring (F-059) — Response confidence assessment

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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

logger = get_logger("mini_parwa_nodes")


# ══════════════════════════════════════════════════════════════════
# SHARED RESOURCES (lazy-initialized singletons)
# ══════════════════════════════════════════════════════════════════

_pii_detector: Optional[PIIDetector] = None
_keyword_classifier: Optional[KeywordClassifier] = None
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
    """Get or create the TechniqueRouter singleton (Mini: Light tier, Tier 1 only)."""
    global _technique_router
    if _technique_router is None:
        try:
            from app.core.technique_router import (
                TechniqueRouter,
                TechniqueID,
                TechniqueTier,
            )
            # Mini only enables Tier 1 techniques (CLARA, CRP, GSD)
            enabled = {
                TechniqueID.CLARA,
                TechniqueID.CRP,
                TechniqueID.GSD,
            }
            _technique_router = TechniqueRouter(
                model_tier="light",
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
    """Check text for emergency signals using keyword matching.

    This is a safety gate — always runs, always FREE (no LLM).

    Args:
        text: The text to check.

    Returns:
        Dict with emergency_flag, emergency_type, and matched_keywords.
    """
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
    """Simple keyword-based empathy/sentiment analysis.

    Used as a FREE fallback when LLM is unavailable.

    Args:
        text: The text to analyze.

    Returns:
        Dict with empathy_score and empathy_flags.
    """
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
        "We understand this is important to you. "
        "Our team will review your request and get back to you within 24 hours. "
        "Your ticket has been created and you'll receive updates via email."
    ),
    "technical": (
        "Thank you for reporting this technical issue. "
        "We're sorry for the inconvenience. "
        "Our technical team has been notified and will investigate. "
        "We'll provide an update as soon as possible."
    ),
    "billing": (
        "Thank you for your billing inquiry. "
        "We take billing questions seriously. "
        "Our billing team will review your account and respond within 24 hours. "
        "Please don't hesitate to reach out if you need immediate assistance."
    ),
    "complaint": (
        "We're sorry to hear about your experience. "
        "Your feedback is very important to us. "
        "A senior team member will review your complaint and reach out personally. "
        "We're committed to resolving this for you."
    ),
    "cancellation": (
        "We're sorry to see you go. "
        "Your cancellation request has been received. "
        "A team member will contact you to confirm and discuss any alternatives. "
        "Is there anything we can do to change your mind?"
    ),
    "shipping": (
        "Thank you for your shipping inquiry. "
        "Let me help you with that. "
        "Our logistics team is checking your shipment status. "
        "You'll receive an update shortly."
    ),
    "account": (
        "Thank you for your account-related inquiry. "
        "For your security, we'll need to verify some details. "
        "Our support team will assist you shortly."
    ),
    "general": (
        "Thank you for reaching out to us. "
        "We've received your message and our team will get back to you as soon as possible. "
        "If your matter is urgent, please let us know and we'll prioritize it."
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

    Removes filler phrases, redundant sentences, and verbose
    language while preserving all factual content.

    Target: 30-40% token reduction with >95% information retention.

    Args:
        text: The response text to compress.

    Returns:
        Dict with compressed_text, tokens_removed, compression_ratio.
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
            # Case-insensitive replacement
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            compressed = pattern.sub("", compressed)
            phrases_removed.append(phrase)

    # Step 2: Clean up double spaces and orphaned punctuation
    compressed = re.sub(r'\s{2,}', ' ', compressed)
    compressed = re.sub(r'\.\s*\.', '.', compressed)  # double periods
    compressed = re.sub(r'^\s+|\s+$', '', compressed, flags=re.MULTILINE)
    compressed = compressed.strip()

    # Step 3: Remove redundant "Thank you" when it appears multiple times
    thank_you_count = len(re.findall(r'\bthank you\b', compressed, re.IGNORECASE))
    if thank_you_count > 1:
        # Keep only the first occurrence
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
# CLARA QUALITY GATE — Response validation pipeline
# ══════════════════════════════════════════════════════════════════

def _run_clara_quality_gate(
    response: str,
    query: str,
    industry: str,
    tone: str,
    empathy_score: float,
) -> Dict[str, Any]:
    """Run the CLARA quality gate pipeline on a generated response.

    CLARA = Concise Logical Adaptive Response Architecture.
    Validates: Structure -> Logic -> Brand -> Tone -> Delivery

    For Mini: Uses keyword/rule-based checks (FREE, no LLM).
    For Pro/High: Would use LLM-based validation.

    Args:
        response: The generated response to validate.
        query: The original customer query.
        industry: Industry context for brand validation.
        tone: Expected brand tone.
        empathy_score: Customer empathy score for tone validation.

    Returns:
        Dict with passed, score, issues, and adjusted_response.
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
        r'\b(understand|sorry|apologize|acknowledge|we see)\b',
        response, re.IGNORECASE,
    ))
    has_action = bool(re.search(
        r'\b(will|can|let me|our team|we\'ll|we will)\b',
        response, re.IGNORECASE,
    ))

    structure_score = 0
    if has_greeting or has_acknowledgment:
        structure_score += 40
    if has_action:
        structure_score += 40
    if len(response.split('.')) >= 2:  # Has multiple sentences
        structure_score += 20

    if structure_score < 40:
        issues.append("poor_structure")
        score -= 20

    checks["structure"] = {
        "score": structure_score,
        "has_greeting": has_greeting,
        "has_acknowledgment": has_acknowledgment,
        "has_action": has_action,
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

    if logic_score < 20:
        issues.append("off_topic")
        score -= 25

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
    tone_score = 80  # Default good
    if empathy_score < 0.3 and not has_acknowledgment:
        # Customer is distressed but no empathy shown
        tone_score = 40
        issues.append("insufficient_empathy")
        score -= 15
    elif empathy_score > 0.6:
        tone_score = 90  # Neutral customer, neutral response is fine

    checks["tone"] = {
        "score": tone_score,
        "empathy_score": empathy_score,
        "has_acknowledgment": has_acknowledgment,
    }

    # Check 5: DELIVERY — Is the response complete and deliverable?
    delivery_score = 80
    if len(response.strip()) < 20:
        delivery_score = 30
        issues.append("response_too_short")
        score -= 20
    elif len(response.strip()) > 1000:
        delivery_score = 70
        # Not a failure, just info

    # Check for placeholder text that shouldn't be delivered
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

    # Compute final score
    final_score = max(0.0, min(100.0, score))
    passed = final_score >= 60.0  # Mini threshold: 60 (lower than Pro's 85)

    # Auto-fix: adjust response if minor issues
    adjusted_response = response
    if issues and "unresolved_placeholders" in issues:
        # Remove any unresolved template placeholders
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
# NODE FUNCTIONS — 10 Agent Nodes
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

        # Simple redaction: replace PII values with tokens
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
                "pii_check": {
                    "status": "error",
                    "error": str(exc),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": [append_audit_entry(
                state, "pii_check", "error",
                duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


async def empathy_check_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 2: Empathy Check — Score empathy and detect emotional flags.

    Uses LLM for sentiment/empathy analysis (via MiniLLMClient).
    FALLBACK: If LLM fails, uses keyword-based detection.

    Also integrates with Smart Router for model selection.

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

        # Try LLM-based empathy check first
        empathy_score = 0.5
        empathy_flags: List[str] = []
        method = "keyword"

        try:
            from app.core.mini_parwa.llm_client import MiniLLMClient

            client = MiniLLMClient()
            if client.is_available:
                llm_response, tokens = await client.chat(
                    system_prompt=(
                        "Analyze the customer's emotional state. "
                        "Return JSON: {\"empathy_score\": <0.0-1.0>, "
                        "\"flags\": [\"frustrated\"|\"angry\"|\"sad\"|\"urgent\"|\"confused\"]}\n"
                        "Lower empathy_score means more distressed customer."
                    ),
                    user_message=query,
                    max_tokens=100,
                    temperature=0.3,
                )

                if llm_response:
                    import json
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
            logger.info("empathy_llm_fallback_to_keyword")

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
                "empathy_check": {
                    "status": "error",
                    "error": str(exc),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": [append_audit_entry(
                state, "empathy_check", "error",
                duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def emergency_check_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 3: Emergency Check — Detect emergency signals.

    Uses keyword matching (FREE, no LLM) — this is a safety gate.
    If emergency detected, the pipeline skips to format with an
    escalation message.

    Writes: emergency_flag, emergency_type, current_step
    """
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
                "emergency_check": {
                    "status": "error",
                    "error": str(exc),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": [append_audit_entry(
                state, "emergency_check", "error",
                duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def gsd_state_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 4: GSD State — Track and update conversation state machine.

    GSD = Guided Support Dialogue (F-053).
    State machine: NEW -> GREETING -> DIAGNOSIS -> RESOLUTION -> FOLLOW-UP -> CLOSED

    For Mini: Simplified state transitions with keyword-based detection.
    Tracks state in SharedGSDManager for analytics and recovery.

    Writes: gsd_state, current_step
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

        # Determine next state based on signals (code-orchestrated = FREE)
        if emergency_flag:
            next_state = "escalate"
        elif current_gsd_state == "new":
            next_state = "greeting"
        elif current_gsd_state == "greeting":
            # Has classification? Move to diagnosis
            if classification and classification.get("intent", "general") != "general":
                next_state = "diagnosis"
            else:
                next_state = "diagnosis"  # Default progression
        elif current_gsd_state == "diagnosis":
            # Has generated response? Move to resolution
            if state.get("generated_response"):
                next_state = "resolution"
            else:
                next_state = "diagnosis"  # Stay in diagnosis
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
                    "variant_tier": "mini_parwa",
                },
            )

        # Check for stuck tickets and get recovery suggestions
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
                "gsd_state": {
                    "status": "error",
                    "error": str(exc),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": [append_audit_entry(
                state, "gsd_state", "error",
                duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def extract_signals_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 5: Extract Signals — Derive query signals for technique routing.

    Extracts: complexity, sentiment, monetary value, intent, etc.
    These signals feed into the Technique Router (BC-013).

    For Mini: Keyword/rule-based signal extraction (FREE, no LLM).
    Writes to state.signals which the Technique Router reads.

    Writes: signals, technique, current_step
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

        # 1. Query complexity (based on word count, question marks, multi-part)
        word_count = len(query.split())
        question_marks = query.count("?")
        has_multi_part = bool(re.search(
            r'\b(and|also|furthermore|moreover|as well|additionally)\b',
            query, re.IGNORECASE,
        ))
        complexity = min(1.0, (word_count / 50) * 0.4 + question_marks * 0.15 + (0.3 if has_multi_part else 0.0))

        # 2. Sentiment score (derived from empathy)
        sentiment = empathy_score

        # 3. Monetary value detection
        monetary_match = re.search(
            r'\$(\d+(?:,\d+)*(?:\.\d{2})?)',
            query,
        )
        monetary_value = 0.0
        if monetary_match:
            monetary_value = float(monetary_match.group(1).replace(",", ""))

        # 4. Intent type (from classification if available)
        intent_type = classification.get("intent", "general") if classification else "general"

        # 5. Turn count (from conversation_id presence)
        conversation_id = state.get("conversation_id", "")
        turn_count = 1 if conversation_id else 0

        # 6. Resolution path count (estimate from query complexity)
        resolution_path_count = 1
        if complexity > 0.5 or intent_type in ("technical", "billing"):
            resolution_path_count = 3
        elif complexity > 0.3:
            resolution_path_count = 2

        # 7. External data required (detect order IDs, account numbers)
        external_data = bool(re.search(
            r'(order|account|invoice|ticket|tracking)\s*#?\s*\d+',
            query, re.IGNORECASE,
        ))

        # 8. Reasoning loop detection (check step outputs for repeated steps)
        reasoning_loop = False
        step_outputs = state.get("step_outputs", {})
        if isinstance(step_outputs, dict):
            completed_steps = [k for k, v in step_outputs.items()
                             if isinstance(v, dict) and v.get("status") == "completed"]
            if completed_steps.count("classify") > 1:
                reasoning_loop = True

        # 9. Frustration score (derived from empathy + flags)
        frustration_score = 0.0
        if empathy_flags:
            frustration_map = {
                "frustrated": 50, "angry": 80, "urgent": 60,
                "sad": 40, "confused": 30,
            }
            frustration_score = max(
                frustration_map.get(f, 20) for f in empathy_flags
            )

        signals = {
            "query_complexity": round(complexity, 3),
            "confidence_score": 1.0,  # Will be updated by confidence scoring
            "sentiment_score": round(sentiment, 3),
            "frustration_score": frustration_score,
            "customer_tier": customer_tier,
            "monetary_value": monetary_value,
            "turn_count": turn_count,
            "intent_type": intent_type,
            "previous_response_status": "none",
            "reasoning_loop_detected": reasoning_loop,
            "resolution_path_count": resolution_path_count,
            "external_data_required": external_data,
            "is_strategic_decision": False,
        }

        # ── Technique Router (BC-013) ──────────────────────────
        technique_result = {}
        try:
            router = _get_technique_router()
            if router:
                from app.core.technique_router import QuerySignals
                query_signals = QuerySignals(
                    query_complexity=signals["query_complexity"],
                    confidence_score=signals["confidence_score"],
                    sentiment_score=signals["sentiment_score"],
                    frustration_score=signals["frustration_score"],
                    customer_tier=signals["customer_tier"],
                    monetary_value=signals["monetary_value"],
                    turn_count=signals["turn_count"],
                    intent_type=signals["intent_type"],
                    previous_response_status=signals["previous_response_status"],
                    reasoning_loop_detected=signals["reasoning_loop_detected"],
                    resolution_path_count=signals["resolution_path_count"],
                    external_data_required=signals["external_data_required"],
                    is_strategic_decision=signals["is_strategic_decision"],
                )
                router_result = router.route(query_signals)
                technique_result = {
                    "technique": "tier_1_only",
                    "activated_techniques": [
                        t.technique_id.value for t in router_result.activated_techniques
                    ],
                    "model_tier": router_result.model_tier,
                    "trigger_rules_evaluated": router_result.trigger_rules_evaluated,
                    "trigger_rules_matched": router_result.trigger_rules_matched,
                    "total_estimated_tokens": router_result.total_estimated_tokens,
                    "method": "technique_router",
                }
        except Exception:
            logger.info("technique_router_fallback_to_defaults")
            technique_result = {
                "technique": "tier_1_only",
                "activated_techniques": ["clara", "crp", "gsd"],
                "model_tier": "light",
                "trigger_rules_evaluated": 0,
                "trigger_rules_matched": 0,
                "total_estimated_tokens": 100,
                "method": "fallback_defaults",
            }

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="extract_signals",
            action="signals_extracted",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "complexity": signals["query_complexity"],
                "sentiment": signals["sentiment_score"],
                "monetary_value": signals["monetary_value"],
                "techniques_activated": technique_result.get("activated_techniques", []),
            },
        )

        return {
            "signals": signals,
            "technique": technique_result,
            "current_step": "extract_signals",
            "step_outputs": {
                "extract_signals": {
                    "status": "completed",
                    "complexity": signals["query_complexity"],
                    "sentiment": signals["sentiment_score"],
                    "monetary_value": signals["monetary_value"],
                    "techniques": technique_result.get("activated_techniques", []),
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
            "technique": {
                "technique": "tier_1_only",
                "activated_techniques": ["clara", "crp", "gsd"],
                "model_tier": "light",
                "method": "error_fallback",
            },
            "current_step": "extract_signals",
            "errors": [f"extract_signals: {str(exc)}"],
            "step_outputs": {
                "extract_signals": {
                    "status": "error",
                    "error": str(exc),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": [append_audit_entry(
                state, "extract_signals", "error",
                duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def classify_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 6: Classify — Intent classification using keyword matching.

    For Mini: uses keyword classification (no AI, saves cost).
    Uses ClassificationEngine with use_ai=False.

    Writes: classification, current_step
    """
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query") or state.get("query", "")

        if not query:
            return {
                "classification": {
                    "intent": "general",
                    "confidence": 0.0,
                    "secondary_intents": [],
                    "method": "fallback",
                },
                "current_step": "classify",
                "step_outputs": {"classify": {"status": "skipped", "reason": "empty_query"}},
                "audit_log": [append_audit_entry(state, "classify", "skipped_empty_query")["audit_log"][0]],
            }

        # Use keyword classifier (FREE, no AI for Mini)
        classifier = _get_keyword_classifier()
        result = classifier.classify(query)

        classification = {
            "intent": result.primary_intent,
            "confidence": result.primary_confidence,
            "secondary_intents": [
                {"intent": intent, "confidence": conf}
                for intent, conf in result.secondary_intents
            ],
            "method": result.classification_method,
        }

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="classify",
            action="classification_complete",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "intent": classification["intent"],
                "confidence": classification["confidence"],
                "method": classification["method"],
            },
        )

        return {
            "classification": classification,
            "current_step": "classify",
            "step_outputs": {
                "classify": {
                    "status": "completed",
                    "intent": classification["intent"],
                    "confidence": classification["confidence"],
                    "method": classification["method"],
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("classify_node_failed", error=str(exc))
        return {
            "classification": {
                "intent": "general",
                "confidence": 0.0,
                "secondary_intents": [],
                "method": "fallback",
            },
            "current_step": "classify",
            "errors": [f"classify: {str(exc)}"],
            "step_outputs": {
                "classify": {
                    "status": "error",
                    "error": str(exc),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": [append_audit_entry(
                state, "classify", "error",
                duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


async def generate_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 7: Generate — Generate response using LLM.

    Uses MiniLLMClient (gpt-4o-mini) for generation.
    Integrates with Smart Router (F-054) for model selection.
    FALLBACK: If LLM fails, uses template-based response.

    Builds prompt from: industry system prompt + classification +
    empathy context + GSD state + technique context + query.

    Writes: generated_response, generation_model, generation_tokens, current_step
    """
    start = time.monotonic()
    try:
        query = state.get("pii_redacted_query") or state.get("query", "")
        industry = state.get("industry", "general")
        classification = state.get("classification", {})
        empathy_score = state.get("empathy_score", 0.5)
        empathy_flags = state.get("empathy_flags", [])
        emergency_flag = state.get("emergency_flag", False)
        ticket_id = state.get("ticket_id", "")
        technique = state.get("technique", {})
        signals = state.get("signals", {})

        # If emergency was detected, use emergency template
        if emergency_flag:
            emergency_type = state.get("emergency_type", "")
            emergency_response = EMERGENCY_RESPONSE_TEMPLATE.format(
                ticket_id=ticket_id or "N/A"
            )
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            return {
                "generated_response": emergency_response,
                "generation_model": "template",
                "generation_tokens": 0,
                "current_step": "generate",
                "step_outputs": {
                    "generate": {
                        "status": "completed",
                        "method": "emergency_template",
                        "emergency_type": emergency_type,
                        "duration_ms": duration_ms,
                    }
                },
                "audit_log": append_audit_entry(
                    state,
                    step="generate",
                    action="emergency_template_generated",
                    duration_ms=duration_ms,
                    tokens_used=0,
                    details={"emergency_type": emergency_type},
                )["audit_log"],
            }

        # Build the generation prompt
        system_prompt = get_industry_prompt(industry)

        # Add GSD state context
        step_outputs = state.get("step_outputs", {})
        gsd_output = step_outputs.get("gsd_state", {})
        if isinstance(gsd_output, dict) and gsd_output.get("to_state"):
            system_prompt += (
                f"\n\nConversation state: {gsd_output['to_state'].upper()}. "
                "Respond appropriately for this conversation stage."
            )

        # Add technique context (Tier 1: CLARA structure guidance)
        activated = technique.get("activated_techniques", [])
        if "clara" in activated:
            system_prompt += (
                "\n\nRESPONSE STRUCTURE (CLARA): "
                "1) Acknowledge the customer's concern. "
                "2) Provide the solution or explanation. "
                "3) State any action items or next steps. "
                "4) Close with a helpful statement."
            )

        # Add empathy context
        if empathy_flags and empathy_score < 0.5:
            system_prompt += (
                "\n\nIMPORTANT: The customer appears to be distressed "
                f"(empathy score: {empathy_score:.1f}, flags: {', '.join(empathy_flags)}). "
                "Be extra empathetic, acknowledge their feelings, "
                "and prioritize resolving their issue."
            )

        # Add classification context
        intent = classification.get("intent", "general")
        confidence = classification.get("confidence", 0.0)
        system_prompt += (
            f"\n\nThe customer's intent is classified as '{intent}' "
            f"(confidence: {confidence:.1%}). "
            f"Tailor your response accordingly."
        )

        # Try LLM generation (with Smart Router awareness)
        generated_response = ""
        generation_tokens = 0
        generation_model = "template"
        method = "template"

        try:
            from app.core.mini_parwa.llm_client import MiniLLMClient

            client = MiniLLMClient()
            if client.is_available:
                fallback_text = TEMPLATE_RESPONSES.get(
                    intent, TEMPLATE_RESPONSES["general"]
                )
                response_text, tokens = await client.chat_with_fallback(
                    system_prompt=system_prompt,
                    user_message=query,
                    fallback_text=fallback_text,
                    max_tokens=256,
                    temperature=0.7,
                )
                if response_text:
                    generated_response = response_text
                    generation_tokens = tokens
                    generation_model = client.model
                    method = "llm"
        except Exception:
            logger.info("generate_llm_fallback_to_template")

        # Fallback to template if LLM didn't produce output
        if not generated_response:
            generated_response = TEMPLATE_RESPONSES.get(
                intent, TEMPLATE_RESPONSES["general"]
            )
            method = "template"

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="generate",
            action="response_generated",
            duration_ms=duration_ms,
            tokens_used=generation_tokens,
            details={
                "method": method,
                "model": generation_model,
                "intent": intent,
                "techniques_active": activated,
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
                    "method": method,
                    "model": generation_model,
                    "tokens": generation_tokens,
                    "techniques_active": activated,
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("generate_node_failed", error=str(exc))

        fallback = TEMPLATE_RESPONSES["general"]

        return {
            "generated_response": fallback,
            "generation_model": "template",
            "generation_tokens": 0,
            "current_step": "generate",
            "errors": [f"generate: {str(exc)}"],
            "step_outputs": {
                "generate": {
                    "status": "error",
                    "error": str(exc),
                    "method": "template_fallback",
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": [append_audit_entry(
                state, "generate", "error_template_fallback",
                duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def crp_compress_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 8: CRP Compress — Apply Concise Response Protocol (F-140).

    CRP = Tier 1 technique, always active for ALL variants (even Mini).
    Eliminates filler phrases, redundancy, and verbose language.
    Target: 30-40% token reduction, >95% information retention.

    This is a FREE step (rule-based, no LLM).

    Writes: generated_response (updated), crp_compression_ratio, current_step
    """
    start = time.monotonic()
    try:
        generated_response = state.get("generated_response", "")
        technique = state.get("technique", {})

        # Only run CRP if it's activated by the technique router
        activated = technique.get("activated_techniques", [])
        crp_active = "crp" in activated or not activated  # Default active

        if not generated_response or not crp_active:
            return {
                "current_step": "crp_compress",
                "step_outputs": {
                    "crp_compress": {
                        "status": "skipped",
                        "reason": "empty_response" if not generated_response else "crp_not_active",
                        "duration_ms": round((time.monotonic() - start) * 1000, 2),
                    }
                },
                "audit_log": [append_audit_entry(
                    state, "crp_compress", "skipped",
                    duration_ms=round((time.monotonic() - start) * 1000, 2),
                    details={"reason": "crp_not_active_or_empty"},
                )["audit_log"][0]],
            }

        # Apply CRP compression
        result = _apply_crp_compression(generated_response)
        compressed = result["compressed_text"]

        # Use compressed text as the new generated_response
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="crp_compress",
            action="crp_compression_applied",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "tokens_removed": result["tokens_removed"],
                "compression_ratio": result["compression_ratio"],
                "phrases_removed": result["phrases_removed"],
            },
        )

        return {
            "generated_response": compressed,
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
        # CRP failure is non-fatal — just pass through the response
        return {
            "current_step": "crp_compress",
            "errors": [f"crp_compress: {str(exc)}"],
            "step_outputs": {
                "crp_compress": {
                    "status": "error",
                    "error": str(exc),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": [append_audit_entry(
                state, "crp_compress", "error",
                duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def clara_quality_gate_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 9: CLARA Quality Gate — Validate response quality (Tier 1).

    CLARA = Concise Logical Adaptive Response Architecture.
    Always active for ALL variants (even Mini).

    Validates: Structure -> Logic -> Brand -> Tone -> Delivery
    For Mini: Rule-based checks (FREE, no LLM).
    For Pro/High: Would use LLM-based validation + retry loop.

    If response fails quality gate: auto-fix minor issues, log major ones.
    Writes: quality_score, quality_passed, quality_issues, current_step
    """
    start = time.monotonic()
    try:
        generated_response = state.get("generated_response", "")
        query = state.get("pii_redacted_query") or state.get("query", "")
        industry = state.get("industry", "general")
        empathy_score = state.get("empathy_score", 0.5)
        technique = state.get("technique", {})

        # Only run CLARA if it's activated by the technique router
        activated = technique.get("activated_techniques", [])
        clara_active = "clara" in activated or not activated  # Default active

        if not generated_response or not clara_active:
            return {
                "quality_score": 0.0,
                "quality_passed": True,  # Default pass if skipped
                "quality_issues": [],
                "quality_retry_count": 0,
                "current_step": "clara_quality_gate",
                "step_outputs": {
                    "clara_quality_gate": {
                        "status": "skipped",
                        "reason": "empty_response" if not generated_response else "clara_not_active",
                        "duration_ms": round((time.monotonic() - start) * 1000, 2),
                    }
                },
                "audit_log": [append_audit_entry(
                    state, "clara_quality_gate", "skipped",
                    duration_ms=round((time.monotonic() - start) * 1000, 2),
                    details={"reason": "clara_not_active_or_empty"},
                )["audit_log"][0]],
            }

        # Run CLARA quality gate
        tone = get_industry_tone(industry)
        result = _run_clara_quality_gate(
            response=generated_response,
            query=query,
            industry=industry,
            tone=tone,
            empathy_score=empathy_score,
        )

        # If auto-fix was applied, update the generated_response
        final_response = result["adjusted_response"]

        # Run Confidence Scoring Engine (F-059) for additional validation
        confidence_result = None
        try:
            confidence_engine = _get_confidence_engine()
            if confidence_engine:
                confidence_result = confidence_engine.score_response(
                    company_id=state.get("company_id", ""),
                    query=query,
                    response=final_response,
                    context={
                        "model_tier": "tier_2",  # Mini uses light/mini models
                        "pii_redacted": state.get("pii_detected", False),
                    },
                    config=None,  # Use defaults for Mini
                )
        except Exception:
            logger.info("confidence_scoring_fallback")

        # Combine CLARA score with confidence score
        quality_score = result["score"] / 100.0  # Normalize to 0-1
        if confidence_result:
            # Weighted: 60% CLARA + 40% confidence
            quality_score = (result["score"] * 0.6 + confidence_result.overall_score * 0.4) / 100.0

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="clara_quality_gate",
            action="quality_gate_complete",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "clara_score": result["score"],
                "clara_passed": result["passed"],
                "clara_issues": result["issues"],
                "confidence_score": confidence_result.overall_score if confidence_result else None,
                "final_quality_score": round(quality_score, 3),
            },
        )

        return {
            "generated_response": final_response,
            "quality_score": round(quality_score, 3),
            "quality_passed": result["passed"],
            "quality_issues": result["issues"],
            "quality_retry_count": 0,
            "current_step": "clara_quality_gate",
            "step_outputs": {
                "clara_quality_gate": {
                    "status": "completed",
                    "clara_score": result["score"],
                    "clara_passed": result["passed"],
                    "clara_issues": result["issues"],
                    "confidence_score": confidence_result.overall_score if confidence_result else None,
                    "final_quality_score": round(quality_score, 3),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("clara_quality_gate_node_failed", error=str(exc))
        # Quality gate failure is non-fatal — pass through
        return {
            "quality_score": 0.5,
            "quality_passed": True,  # Default pass on error
            "quality_issues": [f"clara_error: {str(exc)}"],
            "quality_retry_count": 0,
            "current_step": "clara_quality_gate",
            "errors": [f"clara_quality_gate: {str(exc)}"],
            "step_outputs": {
                "clara_quality_gate": {
                    "status": "error",
                    "error": str(exc),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": [append_audit_entry(
                state, "clara_quality_gate", "error",
                duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }


def format_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Agent 10: Format — Format the generated response.

    Uses FormatterRegistry with Mini defaults:
    - token_limit, markdown, whitespace (3 formatters)

    Writes: formatted_response, final_response, response_format,
            pipeline_status, steps_completed, current_step
    """
    start = time.monotonic()
    try:
        generated_response = state.get("generated_response", "")
        industry = state.get("industry", "general")
        channel = state.get("channel", "chat")
        emergency_flag = state.get("emergency_flag", False)
        emergency_type = state.get("emergency_type", "")
        empathy_score = state.get("empathy_score", 0.5)
        customer_tier = state.get("customer_tier", "free")
        classification = state.get("classification", {})
        intent = classification.get("intent", "general") if classification else "general"
        ticket_id = state.get("ticket_id", "")
        tone = get_industry_tone(industry)

        # Handle emergency bypass: if emergency flagged and generate was skipped,
        # produce the emergency response here
        if emergency_flag and not generated_response:
            generated_response = EMERGENCY_RESPONSE_TEMPLATE.format(
                ticket_id=ticket_id or "N/A"
            )

        # Determine response format based on channel
        format_map = {
            "chat": "chat",
            "email": "email",
            "phone": "phone_transcript",
            "web_widget": "chat",
            "social": "social",
        }
        response_format = format_map.get(channel, "chat")

        # Build formatting context
        context = FormattingContext(
            company_id=state.get("company_id", ""),
            variant_type="mini_parwa",
            brand_voice=tone.replace("_", " ") if "_" in tone else tone,
            model_tier="mini",
            customer_tier=customer_tier,
            intent_type=intent,
            sentiment_score=empathy_score,
            formality_level="medium",
        )

        # Apply formatters
        registry = _get_formatter_registry()
        format_result = registry.apply_all(generated_response, context)

        formatted_response = format_result.formatted_text
        formatters_applied = format_result.formatters_applied

        # Build steps_completed from step_outputs
        existing_steps = state.get("steps_completed", [])
        completed = list(existing_steps)
        completed.append("format")

        # Track which pipeline steps completed
        step_outputs = state.get("step_outputs", {})
        for step_name in [
            "pii_check", "empathy_check", "emergency_check",
            "gsd_state", "extract_signals", "classify",
            "generate", "crp_compress", "clara_quality_gate",
        ]:
            step_data = step_outputs.get(step_name, {})
            if isinstance(step_data, dict) and step_data.get("status") == "completed":
                if step_name not in completed:
                    completed.append(step_name)

        # Ensure order
        all_steps = [
            "pii_check", "empathy_check", "emergency_check",
            "gsd_state", "extract_signals", "classify",
            "generate", "crp_compress", "clara_quality_gate", "format",
        ]
        ordered_completed = [s for s in all_steps if s in completed]

        # Determine pipeline status
        has_errors = bool(state.get("errors", []))
        if emergency_flag:
            pipeline_status = "success"
        elif has_errors:
            pipeline_status = "partial"
        else:
            pipeline_status = "success"

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        audit_entry = append_audit_entry(
            state,
            step="format",
            action="response_formatted",
            duration_ms=duration_ms,
            tokens_used=0,
            details={
                "formatters_applied": formatters_applied,
                "response_format": response_format,
                "pipeline_status": pipeline_status,
                "steps_completed": ordered_completed,
            },
        )

        return {
            "formatted_response": formatted_response,
            "final_response": formatted_response,
            "response_format": response_format,
            "pipeline_status": pipeline_status,
            "steps_completed": ordered_completed,
            "current_step": "format",
            "step_outputs": {
                "format": {
                    "status": "completed",
                    "formatters_applied": formatters_applied,
                    "response_format": response_format,
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("format_node_failed", error=str(exc))

        generated_response = state.get("generated_response", "")
        channel = state.get("channel", "chat")

        return {
            "formatted_response": generated_response,
            "final_response": generated_response,
            "response_format": channel,
            "pipeline_status": "partial",
            "steps_completed": ["format"],
            "current_step": "format",
            "errors": [f"format: {str(exc)}"],
            "step_outputs": {
                "format": {
                    "status": "error",
                    "error": str(exc),
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": [append_audit_entry(
                state, "format", "error",
                duration_ms=duration_ms,
                details={"error": str(exc)},
            )["audit_log"][0]],
        }
