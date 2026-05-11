"""
Router Agent Node — Group 3 (Third node in the pipeline)

Classifies the user's intent, estimates query complexity, selects
the target domain agent, determines the model tier, and builds
the technique stack based on variant_tier access rules.

State Contract:
  Reads:  pii_redacted_message, tenant_id, variant_tier,
          sentiment_score, customer_tier
  Writes: intent, complexity_score, target_agent, model_tier,
          technique_stack, signals_extracted, errors

BC-008: Never crash — returns safe defaults on any failure.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from app.core.langgraph.config import (
    get_available_agents,
    get_available_techniques,
    get_variant_config,
    map_intent_to_agent,
)
from app.logger import get_logger

logger = get_logger("node_router_agent")


# ──────────────────────────────────────────────────────────────
# Default fallback values
# ──────────────────────────────────────────────────────────────

_DEFAULT_STATE: Dict[str, Any] = {
    "intent": "general",
    "complexity_score": 0.0,
    "target_agent": "faq",
    "model_tier": "medium",
    "technique_stack": [],
    "signals_extracted": {},
}


# ──────────────────────────────────────────────────────────────
# Fallback intent classification (keyword-based)
# Used when classification_engine is unavailable.
# ──────────────────────────────────────────────────────────────

_INTENT_KEYWORDS: Dict[str, List[str]] = {
    "refund": [
        "refund", "money back", "return", "cancel order", "cancellation",
        "wrong item", "damaged", "defective", "exchange",
    ],
    "billing": [
        "bill", "invoice", "charge", "payment", "subscription",
        "overcharged", "double charged", "receipt", "pricing",
    ],
    "technical": [
        "not working", "error", "bug", "crash", "broken", "install",
        "setup", "configure", "troubleshoot", "can't access",
        "login issue", "slow", "loading",
    ],
    "complaint": [
        "complaint", "terrible", "horrible", "worst", "unacceptable",
        "disgusted", "furious", "angry", "filing a complaint",
    ],
    "escalation": [
        "manager", "supervisor", "escalate", "speak to someone",
        "human", "real person", "lawyer", "legal", "attorney",
    ],
    "faq": [
        "how do i", "what is", "where is", "when does", "can i",
        "help", "question", "info", "information", "faq",
    ],
}

_COMPLEXITY_INDICATORS_HIGH: List[str] = [
    "multiple", "several", "also", "additionally", "and also",
    "furthermore", "moreover", "both", "complex", "complicated",
]

_COMPLEXITY_INDICATORS_LOW: List[str] = [
    "just", "simply", "only", "quick question", "simple",
]


def _fallback_classify_intent(message: str) -> str:
    """
    Keyword-based intent classification fallback.

    Scores each intent category by counting keyword matches and
    returns the highest-scoring intent. Returns 'general' if no
    keywords match.

    Args:
        message: The PII-redacted message to classify.

    Returns:
        Intent string (faq, refund, technical, billing, complaint, escalation, general).
    """
    message_lower = message.lower()
    best_intent = "general"
    best_score = 0

    for intent, keywords in _INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in message_lower)
        if score > best_score:
            best_score = score
            best_intent = intent

    return best_intent


def _fallback_estimate_complexity(message: str) -> float:
    """
    Heuristic complexity estimation based on message length,
    sentence count, and presence of complexity indicators.

    Args:
        message: The PII-redacted message.

    Returns:
        Complexity score 0.0–1.0.
    """
    # Base complexity from message length
    word_count = len(message.split())
    if word_count <= 10:
        length_score = 0.1
    elif word_count <= 30:
        length_score = 0.3
    elif word_count <= 60:
        length_score = 0.5
    elif word_count <= 100:
        length_score = 0.7
    else:
        length_score = 0.9

    # Adjust for sentence count (multi-sentence = more complex)
    sentence_count = max(1, len(re.split(r'[.!?]+', message)))
    sentence_factor = min(1.0, sentence_count / 5.0) * 0.2

    # Adjust for complexity indicators
    message_lower = message.lower()
    high_indicators = sum(1 for kw in _COMPLEXITY_INDICATORS_HIGH if kw in message_lower)
    low_indicators = sum(1 for kw in _COMPLEXITY_INDICATORS_LOW if kw in message_lower)

    indicator_adjustment = min(0.2, high_indicators * 0.05) - min(0.2, low_indicators * 0.05)

    complexity = length_score + sentence_factor + indicator_adjustment
    return round(max(0.0, min(1.0, complexity)), 2)


def _select_model_tier(
    complexity_score: float,
    sentiment_score: float,
    variant_tier: str,
) -> str:
    """
    Select the LLM model tier based on complexity, sentiment,
    and variant_tier.

    Logic:
      - High complexity (>= 0.7) or very negative sentiment (<= 0.2) → heavy
      - Medium complexity (0.3-0.7) → medium
      - Low complexity (< 0.3) → light
      - Mini tier never uses heavy (cost control)

    Args:
        complexity_score: Query complexity 0.0-1.0.
        sentiment_score: Sentiment score 0.0-1.0.
        variant_tier: Variant tier string.

    Returns:
        Model tier string: 'light', 'medium', 'heavy'.
    """
    if complexity_score >= 0.7 or sentiment_score <= 0.2:
        model_tier = "heavy"
    elif complexity_score >= 0.3:
        model_tier = "medium"
    else:
        model_tier = "light"

    # Mini tier: cap at medium for cost control
    if variant_tier == "mini" and model_tier == "heavy":
        model_tier = "medium"

    return model_tier


def _build_technique_stack(
    variant_tier: str,
    intent: str,
    complexity_score: float,
    signals: Dict[str, Any],
) -> List[str]:
    """
    Build the ordered technique stack based on variant_tier access,
    intent, and extracted signals.

    Technique selection logic:
      1. Start with base techniques always available for the tier
      2. Add intent-specific techniques if available
      3. Add signal-driven techniques if available
      4. Respect variant_tier technique access limits

    Args:
        variant_tier: Variant tier string.
        intent: Classified intent.
        complexity_score: Query complexity.
        signals: Extracted query signals dict.

    Returns:
        Ordered list of technique IDs.
    """
    available = get_available_techniques(variant_tier)

    # Base techniques: always include CLARA + CRP + GSD (Tier 1)
    base_techniques = ["clara", "crp", "gsd"]
    stack = [t for t in base_techniques if t in available]

    # Complexity-driven additions
    if complexity_score >= 0.5 and "chain_of_thought" in available:
        stack.append("chain_of_thought")

    if complexity_score >= 0.7 and "step_back" in available:
        stack.append("step_back")

    # Intent-driven additions
    if intent in ("technical", "troubleshoot") and "react" in available:
        stack.append("react")

    if intent in ("complaint", "escalation") and "reverse_thinking" in available:
        stack.append("reverse_thinking")

    # Signal-driven additions
    if signals.get("multi_step", False) and "thread_of_thought" in available:
        stack.append("thread_of_thought")

    if complexity_score >= 0.8 and "tree_of_thoughts" in available:
        stack.append("tree_of_thoughts")

    return stack


def _fallback_extract_signals(message: str) -> Dict[str, Any]:
    """
    Basic signal extraction fallback when signal_extraction module
    is unavailable.

    Extracts simple boolean and count signals from the message.

    Args:
        message: The PII-redacted message.

    Returns:
        Dict of extracted signals.
    """
    message_lower = message.lower()
    sentences = [s.strip() for s in re.split(r'[.!?]+', message) if s.strip()]

    return {
        "word_count": len(message.split()),
        "sentence_count": len(sentences),
        "has_question": "?" in message,
        "multi_step": len(sentences) > 2,
        "contains_numbers": bool(re.search(r'\d+', message)),
        "contains_url": bool(re.search(r'https?://', message_lower)),
    }


def router_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Router Agent Node — LangGraph agent node.

    Classifies the user's intent, estimates complexity, selects
    the target domain agent, determines model tier, and builds
    the technique stack. Uses production engines when available,
    falls back to heuristic-based logic.

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with intent, complexity_score,
        target_agent, model_tier, technique_stack, signals_extracted,
        and optionally errors.
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")
    message = state.get("pii_redacted_message", "") or state.get("message", "")
    sentiment_score = state.get("sentiment_score", 0.5)
    customer_tier = state.get("customer_tier", "free")

    logger.info(
        "router_agent_node_start",
        tenant_id=tenant_id,
        variant_tier=variant_tier,
        customer_tier=customer_tier,
        message_length=len(message),
    )

    try:
        # ══════════════════════════════════════════════════════════
        # STEP 1: Intent Classification
        # ══════════════════════════════════════════════════════════
        intent = "general"
        try:
            from app.core.classification_engine import classify_intent  # type: ignore[import-untyped]

            intent = str(classify_intent(message, tenant_id=tenant_id))
            logger.info(
                "classification_engine_success",
                tenant_id=tenant_id,
                intent=intent,
            )
        except ImportError:
            intent = _fallback_classify_intent(message)
            logger.info(
                "classification_engine_unavailable_using_fallback",
                tenant_id=tenant_id,
                intent=intent,
            )
        except Exception as cls_exc:
            intent = _fallback_classify_intent(message)
            logger.warning(
                "classification_engine_error_using_fallback",
                tenant_id=tenant_id,
                error=str(cls_exc),
                intent=intent,
            )

        # ══════════════════════════════════════════════════════════
        # STEP 2: Complexity Estimation
        # ══════════════════════════════════════════════════════════
        complexity_score = 0.0
        try:
            from app.core.classification_engine import estimate_complexity  # type: ignore[import-untyped]

            complexity_score = float(estimate_complexity(message, tenant_id=tenant_id))
            complexity_score = round(max(0.0, min(1.0, complexity_score)), 2)
            logger.info(
                "complexity_estimation_success",
                tenant_id=tenant_id,
                complexity_score=complexity_score,
            )
        except (ImportError, AttributeError):
            complexity_score = _fallback_estimate_complexity(message)
            logger.info(
                "complexity_estimation_fallback",
                tenant_id=tenant_id,
                complexity_score=complexity_score,
            )
        except Exception as cmp_exc:
            complexity_score = _fallback_estimate_complexity(message)
            logger.warning(
                "complexity_estimation_error_using_fallback",
                tenant_id=tenant_id,
                error=str(cmp_exc),
                complexity_score=complexity_score,
            )

        # ══════════════════════════════════════════════════════════
        # STEP 3: Signal Extraction
        # ══════════════════════════════════════════════════════════
        signals_extracted: Dict[str, Any] = {}
        try:
            from app.core.signal_extraction import extract_signals  # type: ignore[import-untyped]

            signals_extracted = extract_signals(message, tenant_id=tenant_id)
            if not isinstance(signals_extracted, dict):
                signals_extracted = {}
            logger.info(
                "signal_extraction_success",
                tenant_id=tenant_id,
                signal_count=len(signals_extracted),
            )
        except ImportError:
            signals_extracted = _fallback_extract_signals(message)
            logger.info(
                "signal_extraction_unavailable_using_fallback",
                tenant_id=tenant_id,
            )
        except Exception as sig_exc:
            signals_extracted = _fallback_extract_signals(message)
            logger.warning(
                "signal_extraction_error_using_fallback",
                tenant_id=tenant_id,
                error=str(sig_exc),
            )

        # ══════════════════════════════════════════════════════════
        # STEP 4: Target Agent Selection (uses config)
        # ══════════════════════════════════════════════════════════
        target_agent = map_intent_to_agent(intent, variant_tier)

        logger.info(
            "target_agent_selected",
            tenant_id=tenant_id,
            intent=intent,
            target_agent=target_agent,
            variant_tier=variant_tier,
        )

        # ══════════════════════════════════════════════════════════
        # STEP 5: Model Tier Selection
        # ══════════════════════════════════════════════════════════
        model_tier = _select_model_tier(complexity_score, sentiment_score, variant_tier)

        # ══════════════════════════════════════════════════════════
        # STEP 6: Technique Stack Assembly
        # ══════════════════════════════════════════════════════════
        technique_stack = _build_technique_stack(
            variant_tier=variant_tier,
            intent=intent,
            complexity_score=complexity_score,
            signals=signals_extracted,
        )

        logger.info(
            "router_agent_node_success",
            tenant_id=tenant_id,
            intent=intent,
            complexity_score=complexity_score,
            target_agent=target_agent,
            model_tier=model_tier,
            technique_stack=technique_stack,
        )

        return {
            "intent": intent,
            "complexity_score": complexity_score,
            "target_agent": target_agent,
            "model_tier": model_tier,
            "technique_stack": technique_stack,
            "signals_extracted": signals_extracted,
        }

    except Exception as exc:
        # ── Total failure: return safe defaults ─────────────────
        logger.error(
            "router_agent_node_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )
        return {
            **_DEFAULT_STATE,
            "errors": [f"Router agent failed: {exc}"],
        }
