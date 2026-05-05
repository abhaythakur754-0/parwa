"""
Mini Parwa Pipeline Nodes — 6 node functions for the LangGraph pipeline.

Pipeline: pii_check -> empathy_check -> emergency_check -> classify -> generate -> format -> END

Each node:
  - Takes ParwaGraphState dict as input
  - Returns a dict with ONLY the fields it modified (LangGraph merges these)
  - Is wrapped in try/except (BC-008: never crash)
  - Appends to audit_log and errors using reducer pattern
  - Tracks timing in step_outputs

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
# SHARED RESOURCES (lazy-initialized)
# ══════════════════════════════════════════════════════════════════

_pii_detector: Optional[PIIDetector] = None
_keyword_classifier: Optional[KeywordClassifier] = None
_formatter_registry: Optional[FormatterRegistry] = None


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
            # Use word boundary matching to avoid false positives
            # e.g., "sue" should NOT match "issue", "court" should NOT match "courtney"
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text_lower):
                matched.setdefault(emergency_type, []).append(keyword)

    if matched:
        # Return the highest-priority emergency type
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
            # Use word boundary matching for multi-word phrases
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

    # Score: more flags = lower empathy (customer is distressed)
    if not flags:
        empathy_score = 0.7  # Neutral — no strong emotion detected
    elif len(flags) == 1:
        empathy_score = 0.4  # Mild distress
    elif len(flags) == 2:
        empathy_score = 0.25  # Moderate distress
    else:
        empathy_score = 0.1  # High distress

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
# NODE FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def pii_check_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Node 1: PII Check — Detect and redact PII in the query.

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
            # Replace in reverse order to preserve offsets
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
    """Node 2: Empathy Check — Score empathy and detect emotional flags.

    Uses LLM for sentiment/empathy analysis (via MiniLLMClient).
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

        # Try LLM-based empathy check first
        empathy_score = 0.5
        empathy_flags: List[str] = []
        method = "keyword"  # default fallback

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
                    # Try to parse JSON from response
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
    """Node 3: Emergency Check — Detect emergency signals.

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
        # Safety: default to no emergency on error (don't block pipeline)
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


def classify_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Node 4: Classify — Intent classification using keyword matching.

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
    """Node 5: Generate — Generate response using LLM.

    Uses MiniLLMClient (gpt-4o-mini) for generation.
    FALLBACK: If LLM fails, uses template-based response.

    Builds prompt from: industry system prompt + classification +
    empathy context + query.

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

        # Try LLM generation
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
                    "duration_ms": duration_ms,
                }
            },
            "audit_log": audit_entry["audit_log"],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("generate_node_failed", error=str(exc))

        # Ultimate fallback: general template
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


def format_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Node 6: Format — Format the generated response.

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
        for step_name in ["pii_check", "empathy_check", "emergency_check", "classify", "generate"]:
            step_data = step_outputs.get(step_name, {})
            if isinstance(step_data, dict) and step_data.get("status") == "completed":
                if step_name not in completed:
                    completed.append(step_name)

        # Ensure order
        ordered_completed = [s for s in ["pii_check", "empathy_check", "emergency_check", "classify", "generate", "format"] if s in completed]

        # Determine pipeline status
        has_errors = bool(state.get("errors", []))
        if emergency_flag:
            pipeline_status = "success"  # Emergency was handled, still successful
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

        # Fallback: use generated_response as-is
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
