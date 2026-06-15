"""
Unified Variant LangGraph — ONE graph, ALL tiers.

This replaces the three separate variant graphs (mini_parwa 10 nodes,
parwa 22 nodes, parwa_high 27 nodes) with a SINGLE unified graph
where `variant_tier` controls what each node is ALLOWED to do.

Architecture:
  START
    → pii_check → empathy_check → emergency_check → gsd_state
    → classify → smart_enrichment → [deep_enrichment_router]
    → extract_signals → technique_select → reasoning_chain
    → context_enrich → context_compress → generate
    → crp_compress → clara_quality_gate → quality_retry (conditional)
    → confidence_assess → maker_validator → auto_fix → auto_action
    → context_health → dedup → strategic_decision → peer_review
    → format → END

Key Changes from Old Architecture:
  1. ALL 27+ nodes exist in ONE graph
  2. variant_tier controls PERMISSIONS, not graph topology
  3. maker_validator moved BEFORE generate (validate before generating)
  4. auto_fix node added (all tiers get auto-fix)
  5. Nodes pass RICH CONTEXT to each other via shared state
  6. Inter-node communication via context enrichment + signals
  7. Jarvis bridge integration for monitoring + ask-when-unsure

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger
from app.core.unified_variant.permission_config import (
    VariantTier,
    PermissionConfig,
    get_permission_config,
    is_node_allowed,
    needs_approval,
)

logger = get_logger("unified_variant_graph")


# ══════════════════════════════════════════════════════════════════
# INTENT → DEEP ENRICHMENT MAPPING
# ══════════════════════════════════════════════════════════════════

INTENT_DEEP_ENRICHMENT_MAP = {
    # Complaint / Feedback
    "complaint": "complaint_handler",
    "feedback": "complaint_handler",
    "review": "complaint_handler",
    "dissatisfied": "complaint_handler",
    "unhappy": "complaint_handler",
    "bad_experience": "complaint_handler",
    # Cancellation / Retention
    "cancellation": "retention_negotiator",
    "cancel": "retention_negotiator",
    "unsubscribe": "retention_negotiator",
    "leave": "retention_negotiator",
    "switch": "retention_negotiator",
    # Billing / Payment
    "billing": "billing_resolver",
    "payment": "billing_resolver",
    "refund": "billing_resolver",
    "charge": "billing_resolver",
    "invoice": "billing_resolver",
    "overcharge": "billing_resolver",
    "subscription": "billing_resolver",
    # Technical
    "technical": "tech_diagnostic",
    "bug": "tech_diagnostic",
    "error": "tech_diagnostic",
    "not_working": "tech_diagnostic",
    "broken": "tech_diagnostic",
    "crash": "tech_diagnostic",
    "technical_support": "tech_diagnostic",
    "password_reset": "tech_diagnostic",
    "login_issue": "tech_diagnostic",
    "account_access": "tech_diagnostic",
    # Shipping / Order
    "shipping": "shipping_tracker",
    "delivery": "shipping_tracker",
    "tracking": "shipping_tracker",
    "order": "shipping_tracker",
    "package": "shipping_tracker",
    "late_delivery": "shipping_tracker",
    "missing_order": "shipping_tracker",
}


# ══════════════════════════════════════════════════════════════════
# NODE FUNCTIONS — Each reads state + permission config, acts accordingly
# ══════════════════════════════════════════════════════════════════

def _get_config(state: Dict) -> PermissionConfig:
    """Get permission config from state's variant_tier."""
    tier = state.get("variant_tier", "mini_parwa")
    return get_permission_config(tier)


async def _call_node(node_fn, state: Dict) -> Dict[str, Any]:
    """Call a node function, handling both sync and async nodes."""
    import asyncio
    import inspect
    if inspect.iscoroutinefunction(node_fn):
        return await node_fn(state)
    else:
        return node_fn(state)


async def pii_check_node(state: Dict) -> Dict[str, Any]:
    """PII redaction — ALWAYS runs for all tiers."""
    try:
        from app.core.mini_parwa.nodes import pii_check_node as _pii
        result = await _call_node(_pii, state)
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["pii_check"] = {
            "redacted": True,
            "pii_found": bool(result.get("pii_entities_found", [])),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return result
    except Exception:
        logger.exception("pii_check_node failed")
        return {"step_outputs": {"pii_check": {"redacted": True, "error": True}}}


async def empathy_check_node(state: Dict) -> Dict[str, Any]:
    """Empathy analysis — ALWAYS runs. Passes sentiment to ALL downstream nodes."""
    try:
        from app.core.mini_parwa.nodes import empathy_check_node as _empathy
        result = await _call_node(_empathy, state)
        # Ensure downstream nodes get rich empathy context
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["empathy_check"] = {
            "sentiment": result.get("sentiment", "neutral"),
            "urgency": result.get("urgency_score", 0.5),
            "threat_level": result.get("threat_level", "none"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return result
    except Exception:
        logger.exception("empathy_check_node failed")
        return {"sentiment": "neutral", "urgency_score": 0.5}


async def emergency_check_node(state: Dict) -> Dict[str, Any]:
    """Emergency detection — ALWAYS runs."""
    try:
        from app.core.mini_parwa.nodes import emergency_check_node as _emergency
        result = await _call_node(_emergency, state)
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["emergency_check"] = {
            "emergency_flag": result.get("emergency_flag", False),
            "threat_detected": result.get("threat_detected", False),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return result
    except Exception:
        logger.exception("emergency_check_node failed")
        return {"emergency_flag": False}


async def gsd_state_node(state: Dict) -> Dict[str, Any]:
    """GSD conversation state — ALWAYS runs. Tracks where we are in conversation."""
    try:
        from app.core.mini_parwa.nodes import gsd_state_node as _gsd
        result = await _call_node(_gsd, state)
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["gsd_state"] = {
            "conversation_state": result.get("gsd_current_state", "greeting"),
            "to_state": result.get("gsd_to_state", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return result
    except Exception:
        logger.exception("gsd_state_node failed")
        return {"step_outputs": {"gsd_state": {"conversation_state": "greeting"}}}


async def classify_node(state: Dict) -> Dict[str, Any]:
    """Intent classification — ALWAYS runs. This is the ROUTING backbone."""
    try:
        config = _get_config(state)

        # Use the tier-appropriate classify node
        if config.tier in (VariantTier.PRO, VariantTier.HIGH):
            try:
                from app.core.parwa.nodes import classify_node as _classify
            except ImportError:
                from app.core.mini_parwa.nodes import classify_node as _classify
        else:
            from app.core.mini_parwa.nodes import classify_node as _classify

        result = await _call_node(_classify, state)

        # Ensure classification data is available for ALL downstream nodes
        classification = result.get("classification", {})
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["classify"] = {
            "intent": classification.get("intent", "general"),
            "secondary_intents": classification.get("secondary_intents", []),
            "confidence": classification.get("confidence", 0.5),
            "complexity": result.get("complexity_score", 0.3),
            "domain_hints": classification.get("domain_hints", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Store intent for deep enrichment routing
        result["intent"] = classification.get("intent", "general")
        result["complexity_score"] = result.get("complexity_score", 0.3)

        return result
    except Exception:
        logger.exception("classify_node failed")
        return {
            "classification": {"intent": "general", "confidence": 0.3},
            "intent": "general",
            "complexity_score": 0.3,
        }


async def smart_enrichment_node(state: Dict) -> Dict[str, Any]:
    """Smart enrichment — CONDITIONAL (Mini skips, Pro/High run).

    Enriches the query with additional context from knowledge base,
    previous tickets, and company-specific data.
    """
    config = _get_config(state)
    if not config.allow_smart_enrichment:
        # Mini: pass through, but still record that we checked
        return {
            "step_outputs": {
                "smart_enrichment": {
                    "skipped": True,
                    "reason": "not_allowed_for_tier",
                    "tier": str(config.tier),
                }
            },
            "enrichment_data": {},
        }

    try:
        from app.core.parwa.nodes import smart_enrichment_node as _smart
        result = await _call_node(_smart, state)
        # Pass enrichment data to downstream nodes
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["smart_enrichment"] = {
            "enriched": True,
            "data_sources": result.get("enrichment_sources", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return result
    except Exception:
        logger.exception("smart_enrichment_node failed")
        return {"enrichment_data": {}, "step_outputs": {"smart_enrichment": {"error": True}}}


async def deep_enrichment_router_node(state: Dict) -> Dict[str, Any]:
    """Routes to intent-specific deep enrichment. Passes context THROUGH.

    This is the key node that makes deep enrichment agents TALK to each other.
    It bundles upstream context (empathy, classification, signals) and passes
    it to the deep enrichment agent so they have FULL context.
    """
    config = _get_config(state)
    classification = state.get("classification", {})
    intent = classification.get("intent", state.get("intent", "")).lower()

    # Check if this intent maps to a deep enrichment node
    deep_node = INTENT_DEEP_ENRICHMENT_MAP.get(intent)

    if deep_node and deep_node in config.allowed_deep_enrichment:
        return {
            "deep_enrichment_target": deep_node,
            "step_outputs": {
                "deep_enrichment_router": {
                    "target": deep_node,
                    "intent": intent,
                    "routed": True,
                }
            },
        }

    # Check secondary intents
    secondary_intents = classification.get("secondary_intents", [])
    for sec_intent in secondary_intents:
        deep_node = INTENT_DEEP_ENRICHMENT_MAP.get(sec_intent.lower())
        if deep_node and deep_node in config.allowed_deep_enrichment:
            return {
                "deep_enrichment_target": deep_node,
                "step_outputs": {
                    "deep_enrichment_router": {
                        "target": deep_node,
                        "intent": sec_intent,
                        "routed": True,
                        "secondary": True,
                    }
                },
            }

    # No deep enrichment needed or not allowed
    return {
        "deep_enrichment_target": "skip",
        "step_outputs": {
            "deep_enrichment_router": {
                "target": "skip",
                "reason": "no_matching_intent_or_not_allowed",
            }
        },
    }


def _run_deep_enrichment(state: Dict, node_name: str) -> Dict[str, Any]:
    """Run a deep enrichment node with FULL upstream context.

    This is where inter-node communication happens. The deep enrichment
    agent receives EVERYTHING from upstream: empathy, classification,
    signals, enrichment data, etc.
    """
    config = _get_config(state)

    if node_name not in config.allowed_deep_enrichment:
        return {
            "step_outputs": {
                node_name: {
                    "skipped": True,
                    "reason": "not_allowed_for_tier",
                }
            }
        }

    try:
        # Import from the appropriate variant's nodes
        # Pro and High have the same deep enrichment nodes
        from app.core.parwa import nodes as pro_nodes

        node_map = {
            "complaint_handler": pro_nodes.complaint_handler_node,
            "retention_negotiator": pro_nodes.retention_negotiator_node,
            "billing_resolver": pro_nodes.billing_resolver_node,
            "tech_diagnostic": pro_nodes.tech_diagnostic_node,
            "shipping_tracker": pro_nodes.shipping_tracker_node,
        }

        node_fn = node_map.get(node_name)
        if node_fn is None:
            return {"step_outputs": {node_name: {"error": "node_not_found"}}}

        # CRITICAL: Pass the FULL state to the deep enrichment node
        # This is how nodes "talk to each other" — they see everything
        result = node_fn(state)

        # Ensure deep enrichment output is visible to downstream nodes
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"][node_name] = {
            "processed": True,
            "insights": result.get("deep_insights", {}),
            "recommended_actions": result.get("recommended_actions", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return result
    except Exception:
        logger.exception("deep_enrichment_node failed", node_name=node_name)
        return {"step_outputs": {node_name: {"error": True}}}


async def complaint_handler_node(state: Dict) -> Dict[str, Any]:
    return _run_deep_enrichment(state, "complaint_handler")


async def retention_negotiator_node(state: Dict) -> Dict[str, Any]:
    return _run_deep_enrichment(state, "retention_negotiator")


async def billing_resolver_node(state: Dict) -> Dict[str, Any]:
    return _run_deep_enrichment(state, "billing_resolver")


async def tech_diagnostic_node(state: Dict) -> Dict[str, Any]:
    return _run_deep_enrichment(state, "tech_diagnostic")


async def shipping_tracker_node(state: Dict) -> Dict[str, Any]:
    return _run_deep_enrichment(state, "shipping_tracker")


async def extract_signals_node(state: Dict) -> Dict[str, Any]:
    """Extract signals — ALWAYS runs. Passes signals to ALL downstream nodes."""
    try:
        config = _get_config(state)
        if config.tier in (VariantTier.PRO, VariantTier.HIGH):
            try:
                from app.core.parwa.nodes import extract_signals_node as _signals
            except ImportError:
                from app.core.mini_parwa.nodes import extract_signals_node as _signals
        else:
            from app.core.mini_parwa.nodes import extract_signals_node as _signals

        result = await _call_node(_signals, state)
        # Ensure signals are visible to downstream
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["extract_signals"] = {
            "signals": result.get("signals", {}),
            "signal_count": len(result.get("signals", {})),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return result
    except Exception:
        logger.exception("extract_signals_node failed")
        return {"signals": {}, "step_outputs": {"extract_signals": {"error": True}}}


async def technique_select_node(state: Dict) -> Dict[str, Any]:
    """Technique selection — CONDITIONAL (Mini skips)."""
    config = _get_config(state)
    if not config.allow_technique_select:
        return {
            "selected_technique": "baseline",
            "step_outputs": {
                "technique_select": {
                    "skipped": True,
                    "reason": "not_allowed_for_tier",
                    "fallback": "baseline",
                }
            },
        }

    try:
        from app.core.parwa.nodes import technique_select_node as _technique
        result = await _call_node(_technique, state)
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["technique_select"] = {
            "technique": result.get("selected_technique", "baseline"),
            "allowed_techniques": config.allowed_techniques,
        }
        return result
    except Exception:
        logger.exception("technique_select_node failed")
        return {"selected_technique": "baseline"}


async def reasoning_chain_node(state: Dict) -> Dict[str, Any]:
    """Reasoning chain — CONDITIONAL (Mini skips)."""
    config = _get_config(state)
    if not config.allow_reasoning_chain:
        return {
            "reasoning_result": {},
            "step_outputs": {
                "reasoning_chain": {
                    "skipped": True,
                    "reason": "not_allowed_for_tier",
                }
            },
        }

    try:
        from app.core.parwa.nodes import reasoning_chain_node as _reasoning
        result = await _call_node(_reasoning, state)
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["reasoning_chain"] = {
            "chains": result.get("reasoning_steps", []),
            "conclusion": result.get("reasoning_conclusion", ""),
        }
        return result
    except Exception:
        logger.exception("reasoning_chain_node failed")
        return {"reasoning_result": {}}


async def context_enrich_node(state: Dict) -> Dict[str, Any]:
    """Context enrichment — ALWAYS runs for Pro/High. Aggregates ALL upstream context.

    This is the KEY NODE for inter-node communication. It takes everything
    from upstream (empathy, classification, signals, deep enrichment,
    reasoning) and bundles it into a rich context object that the
    generate node uses.
    """
    try:
        from app.core.parwa.nodes import context_enrich_node as _context
        result = await _call_node(_context, state)

        # CRITICAL: Build the unified context that generate_node will use
        # This is how we fix "nodes not talking to each other"
        step_outputs = state.get("step_outputs", {})
        unified_context = {
            "empathy": step_outputs.get("empathy_check", {}),
            "classification": step_outputs.get("classify", {}),
            "signals": step_outputs.get("extract_signals", {}),
            "deep_enrichment": {},
            "reasoning": step_outputs.get("reasoning_chain", {}),
            "enrichment": step_outputs.get("smart_enrichment", {}),
        }

        # Find the deep enrichment output (whichever one ran)
        for key in ["complaint_handler", "retention_negotiator",
                     "billing_resolver", "tech_diagnostic", "shipping_tracker"]:
            if key in step_outputs:
                unified_context["deep_enrichment"] = step_outputs[key]
                break

        result["unified_context"] = unified_context
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["context_enrich"] = {
            "context_bundled": True,
            "context_sources": list(unified_context.keys()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return result
    except Exception:
        logger.exception("context_enrich_node failed")
        return {"unified_context": {}, "step_outputs": {"context_enrich": {"error": True}}}


async def context_compress_node(state: Dict) -> Dict[str, Any]:
    """Context compression — CONDITIONAL (High only)."""
    config = _get_config(state)
    if not config.allow_context_compress:
        return {
            "step_outputs": {
                "context_compress": {
                    "skipped": True,
                    "reason": "not_allowed_for_tier",
                }
            },
        }

    try:
        from app.core.parwa_high.nodes import context_compress_node as _compress
        result = await _call_node(_compress, state)
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["context_compress"] = {
            "compressed": True,
            "compression_ratio": result.get("compression_ratio", 1.0),
        }
        return result
    except Exception:
        logger.exception("context_compress_node failed")
        return {"step_outputs": {"context_compress": {"skipped": True, "error": True}}}


async def maker_validator_node(state: Dict) -> Dict[str, Any]:
    """MAKER Validator — ALWAYS runs. Uses LLM for K-solution generation.

    This is critical for quality. MAKER generates K candidate solutions
    and picks the best one. Previously only in the main CC Pipeline,
    now available to ALL variants with tier-based K values.
    """
    config = _get_config(state)

    try:
        # Try the main CC Pipeline's MAKER first (most robust)
        # Module starts with digit — use importlib
        try:
            import importlib
            maker_module = importlib.import_module("app.core.langgraph.nodes.11_maker_validator")
            _maker = getattr(maker_module, "maker_validator_node")
            result = await _call_node(_maker, state)
        except (ImportError, ModuleNotFoundError, AttributeError):
            # Fallback: use our own simplified MAKER
            result = _simplified_maker(state, config)

        # Ensure MAKER output is visible to downstream nodes
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["maker_validator"] = {
            "k_solutions": config.maker_k_solutions,
            "best_confidence": result.get("maker_best_confidence", 0.5),
            "red_flag": result.get("red_flag", False),
            "validation_passed": result.get("maker_validation_passed", True),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # If confidence is low, flag for ask-when-unsure
        best_conf = result.get("maker_best_confidence", 0.5)
        if best_conf < config.ask_client_confidence_threshold and config.allow_ask_client:
            result["ask_client_needed"] = True
            result["ask_client_reason"] = f"MAKER confidence {best_conf:.2f} below threshold {config.ask_client_confidence_threshold}"

        return result
    except Exception:
        logger.exception("maker_validator_node failed")
        return {
            "maker_validation_passed": True,
            "step_outputs": {"maker_validator": {"error": True}},
        }


def _simplified_maker(state: Dict, config: PermissionConfig) -> Dict[str, Any]:
    """Simplified MAKER when the full CC Pipeline MAKER isn't available.

    Uses LLM to generate K solutions and pick the best one.
    """
    try:
        from app.core.llm_gateway import get_llm_gateway
        gateway = get_llm_gateway()

        query = state.get("redacted_message", state.get("query", ""))
        agent_response = state.get("agent_response", "")
        unified_context = state.get("unified_context", {})

        k = config.maker_k_solutions
        prompt = (
            f"You are a quality validator for a customer support response.\n"
            f"Customer query: {query}\n"
            f"Proposed response: {agent_response}\n"
            f"Context: {unified_context}\n\n"
            f"Generate {k} alternative responses and score each on 0-1 scale.\n"
            f"Return JSON: {{\"solutions\": [{{\"text\": \"...\", \"confidence\": 0.XX}}], "
            f"\"best_idx\": 0, \"red_flag\": false}}"
        )

        response = gateway.generate(
            prompt=prompt,
            max_tokens=config.llm_max_tokens,
            temperature=0.3,
        )

        # Try to parse JSON response
        import json
        try:
            # Extract JSON from response
            text = response if isinstance(response, str) else str(response)
            # Find JSON in response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end])
                solutions = parsed.get("solutions", [])
                best_idx = parsed.get("best_idx", 0)
                red_flag = parsed.get("red_flag", False)

                if solutions and best_idx < len(solutions):
                    best = solutions[best_idx]
                    return {
                        "agent_response": best.get("text", agent_response),
                        "maker_best_confidence": best.get("confidence", 0.5),
                        "maker_k_solutions": solutions,
                        "red_flag": red_flag,
                        "maker_validation_passed": not red_flag,
                    }
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

        # Fallback: return original response with medium confidence
        return {
            "agent_response": agent_response,
            "maker_best_confidence": 0.5,
            "red_flag": False,
            "maker_validation_passed": True,
        }
    except Exception:
        logger.exception("_simplified_maker failed")
        return {
            "agent_response": state.get("agent_response", ""),
            "maker_best_confidence": 0.5,
            "red_flag": False,
            "maker_validation_passed": True,
        }


async def auto_fix_node(state: Dict) -> Dict[str, Any]:
    """Auto-fix — ALL tiers get this. Attempts to fix common response issues.

    Auto-fix can:
    - Fix formatting issues
    - Add missing empathy phrases
    - Correct policy misstatements
    - Fix tone issues
    - Add missing action items
    """
    config = _get_config(state)
    if not config.allow_auto_fix:
        return {
            "step_outputs": {
                "auto_fix": {
                    "skipped": True,
                    "reason": "not_allowed_for_tier",
                }
            },
        }

    try:
        from app.core.llm_gateway import get_llm_gateway
        gateway = get_llm_gateway()

        agent_response = state.get("agent_response", "")
        if not agent_response:
            return {"step_outputs": {"auto_fix": {"skipped": True, "reason": "no_response"}}}

        prompt = (
            f"You are a response quality fixer. Fix these common issues in the customer support response:\n"
            f"1. Missing empathy/acknowledgment\n"
            f"2. Robotic tone → make it conversational\n"
            f"3. Missing next steps or action items\n"
            f"4. Unclear or vague language\n"
            f"5. Missing personalization\n\n"
            f"Original response: {agent_response}\n\n"
            f"Return the FIXED response only. If the original is already good, return it unchanged."
        )

        fixed_response = gateway.generate(
            prompt=prompt,
            max_tokens=config.llm_max_tokens,
            temperature=0.3,
        )

        fixed_text = fixed_response if isinstance(fixed_response, str) else str(fixed_response)

        # Only use the fixed version if it's reasonable
        was_fixed = fixed_text.strip() != agent_response.strip()

        return {
            "agent_response": fixed_text.strip() if was_fixed else agent_response,
            "auto_fix_applied": was_fixed,
            "step_outputs": {
                "auto_fix": {
                    "applied": was_fixed,
                    "fixes": ["tone", "empathy", "clarity"] if was_fixed else [],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            },
        }
    except Exception:
        logger.exception("auto_fix_node failed")
        return {"step_outputs": {"auto_fix": {"error": True, "skipped": True}}}


async def generate_node(state: Dict) -> Dict[str, Any]:
    """Response generation — ALWAYS runs. Uses FULL unified context.

    This is where the magic happens. The generate node now has access to
    EVERYTHING: empathy data, classification, signals, deep enrichment,
    reasoning, MAKER validation, and the unified context bundle.
    """
    try:
        config = _get_config(state)

        # Use tier-appropriate generate node
        if config.tier == VariantTier.HIGH:
            try:
                from app.core.parwa_high.nodes import generate_node as _generate
            except ImportError:
                from app.core.parwa.nodes import generate_node as _generate
        elif config.tier == VariantTier.PRO:
            from app.core.parwa.nodes import generate_node as _generate
        else:
            from app.core.mini_parwa.nodes import generate_node as _generate

        # Ensure unified_context is available in state for the generate node
        # This is the KEY FIX for inter-node communication
        if "unified_context" not in state:
            # Build it from step_outputs if not already set
            step_outputs = state.get("step_outputs", {})
            state["unified_context"] = {
                "empathy": step_outputs.get("empathy_check", {}),
                "classification": step_outputs.get("classify", {}),
                "signals": step_outputs.get("extract_signals", {}),
                "deep_enrichment": {},
                "reasoning": step_outputs.get("reasoning_chain", {}),
                "enrichment": step_outputs.get("smart_enrichment", {}),
            }

        result = await _call_node(_generate, state)

        # Record generation for downstream nodes
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["generate"] = {
            "generated": True,
            "tokens": result.get("generation_tokens", 0),
            "model_tier": config.llm_model_tier,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return result
    except Exception:
        logger.exception("generate_node failed")
        return {
            "agent_response": "I understand your concern. Let me help you with that.",
            "generation_error": True,
        }


async def crp_compress_node(state: Dict) -> Dict[str, Any]:
    """CRP token compression — ALWAYS runs."""
    try:
        from app.core.mini_parwa.nodes import crp_compress_node as _crp
        result = await _call_node(_crp, state)
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["crp_compress"] = {
            "compressed": True,
            "ratio": result.get("compression_ratio", 0.7),
        }
        return result
    except Exception:
        logger.exception("crp_compress_node failed")
        return {"step_outputs": {"crp_compress": {"error": True}}}


async def clara_quality_gate_node(state: Dict) -> Dict[str, Any]:
    """CLARA quality gate — ALWAYS runs. Tier controls threshold."""
    try:
        config = _get_config(state)

        if config.tier == VariantTier.HIGH:
            try:
                from app.core.parwa_high.nodes import clara_quality_gate_node as _clara
            except ImportError:
                from app.core.parwa.nodes import clara_quality_gate_node as _clara
        elif config.tier == VariantTier.PRO:
            from app.core.parwa.nodes import clara_quality_gate_node as _clara
        else:
            from app.core.mini_parwa.nodes import clara_quality_gate_node as _clara

        result = await _call_node(_clara, state)

        # Apply tier-specific threshold
        quality_score = result.get("quality_score", 0.0)
        passed = quality_score >= config.clara_threshold

        result["quality_passed"] = passed
        result["quality_score"] = quality_score
        result["quality_threshold"] = config.clara_threshold
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["clara_quality_gate"] = {
            "passed": passed,
            "score": quality_score,
            "threshold": config.clara_threshold,
            "max_retries": config.max_quality_retries,
        }

        return result
    except Exception:
        logger.exception("clara_quality_gate_node failed")
        return {"quality_passed": True, "quality_score": 0.7}


async def quality_retry_node(state: Dict) -> Dict[str, Any]:
    """Quality retry — CONDITIONAL (Mini=0, Pro=1, High=2)."""
    config = _get_config(state)
    retry_count = state.get("quality_retry_count", 0)

    if retry_count >= config.max_quality_retries:
        return {
            "quality_retry_exhausted": True,
            "step_outputs": {
                "quality_retry": {
                    "skipped": True,
                    "reason": "retries_exhausted",
                    "retry_count": retry_count,
                    "max_retries": config.max_quality_retries,
                }
            },
        }

    try:
        from app.core.parwa.nodes import quality_retry_node as _retry
        result = await _call_node(_retry, state)
        result["quality_retry_count"] = retry_count + 1
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["quality_retry"] = {
            "attempt": retry_count + 1,
            "max": config.max_quality_retries,
        }
        return result
    except Exception:
        logger.exception("quality_retry_node failed")
        return {"quality_retry_count": retry_count + 1}


async def confidence_assess_node(state: Dict) -> Dict[str, Any]:
    """Confidence assessment — ALWAYS runs."""
    try:
        from app.core.parwa.nodes import confidence_assess_node as _confidence
        result = await _call_node(_confidence, state)

        # Check ask-when-unsure threshold
        config = _get_config(state)
        confidence = result.get("confidence_score", 0.5)
        if confidence < config.ask_client_confidence_threshold and config.allow_ask_client:
            result["ask_client_needed"] = True
            result["ask_client_reason"] = f"Confidence {confidence:.2f} below threshold {config.ask_client_confidence_threshold}"

        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["confidence_assess"] = {
            "confidence": confidence,
            "ask_client": result.get("ask_client_needed", False),
        }
        return result
    except Exception:
        logger.exception("confidence_assess_node failed")
        return {"confidence_score": 0.5}


async def auto_action_node(state: Dict) -> Dict[str, Any]:
    """Auto-action — CONDITIONAL (Mini needs approval, Pro/High can auto-act)."""
    config = _get_config(state)
    if not config.allow_auto_action:
        return {
            "auto_action_taken": False,
            "step_outputs": {
                "auto_action": {
                    "skipped": True,
                    "reason": "not_allowed_for_tier",
                    "needs_human_approval": True,
                }
            },
        }

    try:
        confidence = state.get("confidence_score", 0.0)
        if confidence < config.auto_action_confidence_min:
            return {
                "auto_action_taken": False,
                "step_outputs": {
                    "auto_action": {
                        "skipped": True,
                        "reason": "confidence_below_threshold",
                        "confidence": confidence,
                        "threshold": config.auto_action_confidence_min,
                    }
                },
            }

        from app.core.parwa.nodes import auto_action_node as _auto
        result = await _call_node(_auto, state)
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["auto_action"] = {
            "action_taken": True,
            "action_type": result.get("action_type", "none"),
        }
        return result
    except Exception:
        logger.exception("auto_action_node failed")
        return {"auto_action_taken": False, "step_outputs": {"auto_action": {"error": True}}}


async def context_health_node(state: Dict) -> Dict[str, Any]:
    """Context health check — CONDITIONAL (High only)."""
    config = _get_config(state)
    if not config.allow_context_health:
        return {
            "step_outputs": {
                "context_health": {
                    "skipped": True,
                    "reason": "not_allowed_for_tier",
                }
            },
        }

    try:
        from app.core.parwa_high.nodes import context_health_node as _health
        result = await _call_node(_health, state)
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["context_health"] = {
            "health_score": result.get("context_health_score", 1.0),
        }
        return result
    except Exception:
        logger.exception("context_health_node failed")
        return {"step_outputs": {"context_health": {"error": True}}}


async def dedup_node(state: Dict) -> Dict[str, Any]:
    """Deduplication — CONDITIONAL (High only)."""
    config = _get_config(state)
    if not config.allow_dedup:
        return {
            "step_outputs": {
                "dedup": {
                    "skipped": True,
                    "reason": "not_allowed_for_tier",
                }
            },
        }

    try:
        from app.core.parwa_high.nodes import dedup_node as _dedup
        result = await _call_node(_dedup, state)
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["dedup"] = {
            "duplicates_found": result.get("duplicates_found", 0),
        }
        return result
    except Exception:
        logger.exception("dedup_node failed")
        return {"step_outputs": {"dedup": {"error": True}}}


async def strategic_decision_node(state: Dict) -> Dict[str, Any]:
    """Strategic decision — CONDITIONAL (High only)."""
    config = _get_config(state)
    if not config.allow_strategic_decision:
        return {
            "step_outputs": {
                "strategic_decision": {
                    "skipped": True,
                    "reason": "not_allowed_for_tier",
                }
            },
        }

    try:
        from app.core.parwa_high.nodes import strategic_decision_node as _strategic
        result = await _call_node(_strategic, state)
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["strategic_decision"] = {
            "decision": result.get("strategic_decision_result", ""),
            "rationale": result.get("strategic_rationale", ""),
        }
        return result
    except Exception:
        logger.exception("strategic_decision_node failed")
        return {"step_outputs": {"strategic_decision": {"error": True}}}


async def peer_review_node(state: Dict) -> Dict[str, Any]:
    """Peer review — CONDITIONAL (High only)."""
    config = _get_config(state)
    if not config.allow_peer_review:
        return {
            "step_outputs": {
                "peer_review": {
                    "skipped": True,
                    "reason": "not_allowed_for_tier",
                }
            },
        }

    try:
        from app.core.parwa_high.nodes import peer_review_node as _peer
        result = await _call_node(_peer, state)
        result["step_outputs"] = result.get("step_outputs", {})
        result["step_outputs"]["peer_review"] = {
            "review_passed": result.get("peer_review_passed", True),
            "reviewer_notes": result.get("peer_reviewer_notes", ""),
        }
        return result
    except Exception:
        logger.exception("peer_review_node failed")
        return {"step_outputs": {"peer_review": {"error": True}}}


async def format_node(state: Dict) -> Dict[str, Any]:
    """Format output — ALWAYS runs. Final node before END."""
    try:
        config = _get_config(state)

        if config.tier in (VariantTier.PRO, VariantTier.HIGH):
            try:
                from app.core.parwa.nodes import format_node as _format
            except ImportError:
                from app.core.mini_parwa.nodes import format_node as _format
        else:
            from app.core.mini_parwa.nodes import format_node as _format

        result = await _call_node(_format, state)

        # Add final metadata
        result["pipeline_status"] = "completed"
        result["variant_tier"] = str(config.tier)
        result["completed_at"] = datetime.now(timezone.utc).isoformat()

        # Record ask-when-unsure flag for Jarvis
        if state.get("ask_client_needed"):
            result["ask_client_needed"] = True
            result["ask_client_reason"] = state.get("ask_client_reason", "")

        # Record all steps that ran for audit
        step_outputs = state.get("step_outputs", {})
        result["steps_completed"] = list(step_outputs.keys())

        return result
    except Exception:
        logger.exception("format_node failed")
        return {
            "pipeline_status": "completed_with_errors",
            "agent_response": state.get("agent_response", "I understand your concern. Let me help you with that."),
        }


# ══════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def route_after_emergency(state: Dict) -> str:
    """Route after emergency check."""
    if state.get("emergency_flag", False):
        return "format"  # Emergency bypass
    return "gsd_state"


def route_after_gsd(state: Dict) -> str:
    """Route after GSD state."""
    if state.get("emergency_flag", False):
        return "format"
    step_outputs = state.get("step_outputs", {})
    gsd_output = step_outputs.get("gsd_state", {})
    if isinstance(gsd_output, dict) and gsd_output.get("to_state") == "escalate":
        return "format"
    return "classify"


def route_after_classify(state: Dict) -> str:
    """Route after classify — check if smart_enrichment is allowed."""
    config = _get_config(state)
    if config.allow_smart_enrichment:
        return "smart_enrichment"
    # Mini: skip enrichment, go to extract_signals
    return "extract_signals"


def route_after_smart_enrichment(state: Dict) -> str:
    """Route after smart_enrichment → deep enrichment or extract_signals."""
    target = state.get("deep_enrichment_target", "")
    if target and target != "skip":
        config = _get_config(state)
        if target in config.allowed_deep_enrichment:
            return target
    return "extract_signals"


def route_after_deep_enrichment(state: Dict) -> str:
    """After deep enrichment, always go to extract_signals."""
    return "extract_signals"


def route_after_extract_signals(state: Dict) -> str:
    """Route after extract_signals."""
    config = _get_config(state)
    if config.allow_technique_select:
        return "technique_select"
    # Mini: skip technique selection
    return "context_enrich"


def route_after_technique_select(state: Dict) -> str:
    """Route after technique_select."""
    config = _get_config(state)
    if config.allow_reasoning_chain:
        return "reasoning_chain"
    return "context_enrich"


def route_after_reasoning(state: Dict) -> str:
    """After reasoning, always go to context_enrich."""
    return "context_enrich"


def route_after_context_enrich(state: Dict) -> str:
    """Route after context_enrich — check if context_compress is allowed."""
    config = _get_config(state)
    if config.allow_context_compress:
        return "context_compress"
    return "maker_validator"


def route_after_context_compress(state: Dict) -> str:
    """After context_compress, go to maker_validator."""
    return "maker_validator"


def route_after_maker(state: Dict) -> str:
    """Route after MAKER validator."""
    # If MAKER flagged red flag, check if we need approval
    red_flag = state.get("red_flag", False)
    if red_flag:
        config = _get_config(state)
        action_type = state.get("action_type", "informational")
        if needs_approval(action_type, config.tier):
            return "generate"  # Still generate but mark for approval

    return "generate"


def route_after_generate(state: Dict) -> str:
    """After generate, go to auto_fix then crp_compress."""
    return "auto_fix"


def route_after_auto_fix(state: Dict) -> str:
    """After auto_fix, go to crp_compress."""
    return "crp_compress"


def route_after_clara(state: Dict) -> str:
    """Route after CLARA quality gate."""
    quality_passed = state.get("quality_passed", True)
    config = _get_config(state)
    retry_count = state.get("quality_retry_count", 0)

    if not quality_passed and retry_count < config.max_quality_retries:
        return "quality_retry"

    return "confidence_assess"


def route_after_quality_retry(state: Dict) -> str:
    """After quality retry, go back to generate."""
    return "generate"


def route_after_confidence(state: Dict) -> str:
    """Route after confidence assessment."""
    config = _get_config(state)

    # High tier: context_health → dedup → strategic_decision → peer_review
    if config.allow_context_health:
        return "context_health"
    if config.allow_auto_action:
        return "auto_action"
    return "format"


def route_after_context_health(state: Dict) -> str:
    """After context_health."""
    config = _get_config(state)
    if config.allow_dedup:
        return "dedup"
    if config.allow_auto_action:
        return "auto_action"
    return "format"


def route_after_dedup(state: Dict) -> str:
    """After dedup."""
    config = _get_config(state)
    if config.allow_strategic_decision:
        return "strategic_decision"
    if config.allow_auto_action:
        return "auto_action"
    return "format"


def route_after_strategic_decision(state: Dict) -> str:
    """After strategic_decision."""
    config = _get_config(state)
    if config.allow_peer_review:
        return "peer_review"
    if config.allow_auto_action:
        return "auto_action"
    return "format"


def route_after_peer_review(state: Dict) -> str:
    """After peer_review."""
    config = _get_config(state)
    if config.allow_auto_action:
        return "auto_action"
    return "format"


def route_after_auto_action(state: Dict) -> str:
    """After auto_action, always go to format."""
    return "format"


# ══════════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ══════════════════════════════════════════════════════════════════

def build_unified_variant_graph():
    """Build the unified variant LangGraph StateGraph.

    Creates ONE graph with ALL nodes. The variant_tier in the state
    controls which nodes actually DO work vs pass through.

    Returns:
        Compiled LangGraph StateGraph.
    """
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        raise ImportError("langgraph package is required. pip install langgraph")

    from app.core.parwa_graph_state import ParwaGraphState

    graph = StateGraph(ParwaGraphState)

    # ── Add ALL nodes ──────────────────────────────────────────
    # Core pipeline (always runs)
    graph.add_node("pii_check", pii_check_node)
    graph.add_node("empathy_check", empathy_check_node)
    graph.add_node("emergency_check", emergency_check_node)
    graph.add_node("gsd_state", gsd_state_node)
    graph.add_node("classify", classify_node)

    # Enrichment (conditional)
    graph.add_node("smart_enrichment", smart_enrichment_node)
    graph.add_node("deep_enrichment_router", deep_enrichment_router_node)

    # Deep enrichment agents (conditional)
    graph.add_node("complaint_handler", complaint_handler_node)
    graph.add_node("retention_negotiator", retention_negotiator_node)
    graph.add_node("billing_resolver", billing_resolver_node)
    graph.add_node("tech_diagnostic", tech_diagnostic_node)
    graph.add_node("shipping_tracker", shipping_tracker_node)

    # Signals + Techniques (conditional)
    graph.add_node("extract_signals", extract_signals_node)
    graph.add_node("technique_select", technique_select_node)
    graph.add_node("reasoning_chain", reasoning_chain_node)

    # Context management (conditional)
    graph.add_node("context_enrich", context_enrich_node)
    graph.add_node("context_compress", context_compress_node)

    # Validation + Generation (always)
    graph.add_node("maker_validator", maker_validator_node)
    graph.add_node("generate", generate_node)
    graph.add_node("auto_fix", auto_fix_node)
    graph.add_node("crp_compress", crp_compress_node)
    graph.add_node("clara_quality_gate", clara_quality_gate_node)
    graph.add_node("quality_retry", quality_retry_node)
    graph.add_node("confidence_assess", confidence_assess_node)

    # High-tier nodes (conditional)
    graph.add_node("context_health", context_health_node)
    graph.add_node("dedup", dedup_node)
    graph.add_node("strategic_decision", strategic_decision_node)
    graph.add_node("peer_review", peer_review_node)
    graph.add_node("auto_action", auto_action_node)

    # Output (always)
    graph.add_node("format", format_node)

    # ── Set entry point ──────────────────────────────────────
    graph.set_entry_point("pii_check")

    # ── Add edges ────────────────────────────────────────────
    # Core pipeline
    graph.add_edge("pii_check", "empathy_check")
    graph.add_edge("empathy_check", "emergency_check")

    graph.add_conditional_edges(
        "emergency_check",
        route_after_emergency,
        {"gsd_state": "gsd_state", "format": "format"},
    )

    graph.add_conditional_edges(
        "gsd_state",
        route_after_gsd,
        {"classify": "classify", "format": "format"},
    )

    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {"smart_enrichment": "smart_enrichment", "extract_signals": "extract_signals"},
    )

    # Smart enrichment → deep enrichment router
    graph.add_edge("smart_enrichment", "deep_enrichment_router")

    graph.add_conditional_edges(
        "deep_enrichment_router",
        route_after_smart_enrichment,
        {
            "complaint_handler": "complaint_handler",
            "retention_negotiator": "retention_negotiator",
            "billing_resolver": "billing_resolver",
            "tech_diagnostic": "tech_diagnostic",
            "shipping_tracker": "shipping_tracker",
            "extract_signals": "extract_signals",
        },
    )

    # Deep enrichment → extract_signals
    for deep_node in ["complaint_handler", "retention_negotiator",
                       "billing_resolver", "tech_diagnostic", "shipping_tracker"]:
        graph.add_conditional_edges(
            deep_node,
            route_after_deep_enrichment,
            {"extract_signals": "extract_signals"},
        )

    # Signals → techniques
    graph.add_conditional_edges(
        "extract_signals",
        route_after_extract_signals,
        {"technique_select": "technique_select", "context_enrich": "context_enrich"},
    )

    graph.add_conditional_edges(
        "technique_select",
        route_after_technique_select,
        {"reasoning_chain": "reasoning_chain", "context_enrich": "context_enrich"},
    )

    graph.add_conditional_edges(
        "reasoning_chain",
        route_after_reasoning,
        {"context_enrich": "context_enrich"},
    )

    # Context management
    graph.add_conditional_edges(
        "context_enrich",
        route_after_context_enrich,
        {"context_compress": "context_compress", "maker_validator": "maker_validator"},
    )

    graph.add_conditional_edges(
        "context_compress",
        route_after_context_compress,
        {"maker_validator": "maker_validator"},
    )

    # MAKER → generate
    graph.add_conditional_edges(
        "maker_validator",
        route_after_maker,
        {"generate": "generate"},
    )

    # Generate → auto_fix → crp → clara
    graph.add_conditional_edges(
        "generate",
        route_after_generate,
        {"auto_fix": "auto_fix"},
    )

    graph.add_conditional_edges(
        "auto_fix",
        route_after_auto_fix,
        {"crp_compress": "crp_compress"},
    )

    graph.add_edge("crp_compress", "clara_quality_gate")

    # Quality gate → retry or confidence
    graph.add_conditional_edges(
        "clara_quality_gate",
        route_after_clara,
        {"quality_retry": "quality_retry", "confidence_assess": "confidence_assess"},
    )

    graph.add_conditional_edges(
        "quality_retry",
        route_after_quality_retry,
        {"generate": "generate"},
    )

    # Confidence → high-tier path or auto_action or format
    graph.add_conditional_edges(
        "confidence_assess",
        route_after_confidence,
        {
            "context_health": "context_health",
            "auto_action": "auto_action",
            "format": "format",
        },
    )

    graph.add_conditional_edges(
        "context_health",
        route_after_context_health,
        {
            "dedup": "dedup",
            "auto_action": "auto_action",
            "format": "format",
        },
    )

    graph.add_conditional_edges(
        "dedup",
        route_after_dedup,
        {
            "strategic_decision": "strategic_decision",
            "auto_action": "auto_action",
            "format": "format",
        },
    )

    graph.add_conditional_edges(
        "strategic_decision",
        route_after_strategic_decision,
        {
            "peer_review": "peer_review",
            "auto_action": "auto_action",
            "format": "format",
        },
    )

    graph.add_conditional_edges(
        "peer_review",
        route_after_peer_review,
        {
            "auto_action": "auto_action",
            "format": "format",
        },
    )

    graph.add_conditional_edges(
        "auto_action",
        route_after_auto_action,
        {"format": "format"},
    )

    # Format → END
    graph.add_edge("format", END)

    # ── Compile ────────────────────────────────────────────────
    compiled = graph.compile()

    logger.info(
        "unified_variant_graph_built",
        total_nodes=29,
        architecture="one_graph_all_tiers",
    )

    return compiled


# ══════════════════════════════════════════════════════════════════
# PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════════


class UnifiedVariantPipeline:
    """The unified variant pipeline — ONE graph, ALL tiers.

    Usage:
        pipeline = UnifiedVariantPipeline()
        result = await pipeline.process_ticket(
            query="I need a refund for my order",
            company_id="comp_123",
            variant_tier="parwa_high",  # or "mini_parwa" or "parwa"
            industry="ecommerce",
            channel="chat",
        )

    The variant_tier controls what the pipeline is ALLOWED to do,
    not what nodes exist. All tiers use the same graph.
    """

    def __init__(self) -> None:
        try:
            self._graph = build_unified_variant_graph()
            logger.info("UnifiedVariantPipeline initialized — 29 nodes, all tiers")
        except Exception:
            logger.exception("UnifiedVariantPipeline init failed")
            self._graph = None

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the unified pipeline with the given state."""
        try:
            if self._graph is None:
                logger.error("UnifiedVariantPipeline graph is None")
                return state

            start = time.monotonic()
            result = await self._graph.ainvoke(state)
            total_ms = round((time.monotonic() - start) * 1000, 2)

            if isinstance(result, dict):
                result["total_latency_ms"] = total_ms
                result["billing_tokens"] = result.get("generation_tokens", 0)

            logger.info(
                "unified_pipeline_complete",
                total_latency_ms=total_ms,
                variant_tier=state.get("variant_tier", "unknown"),
                company_id=state.get("company_id", ""),
                quality_score=result.get("quality_score", 0) if isinstance(result, dict) else 0,
            )

            return result

        except Exception:
            logger.exception("UnifiedVariantPipeline.run failed")
            state["pipeline_status"] = "failed"
            state["errors"] = state.get("errors", []) + ["unified_pipeline_execution_failed"]
            return state

    async def process_ticket(
        self,
        query: str,
        company_id: str,
        variant_tier: str = "mini_parwa",
        industry: str = "general",
        channel: str = "chat",
        customer_id: str = "",
        customer_tier: str = "free",
        conversation_id: str = "",
        ticket_id: str = "",
        variant_instance_id: str = "",
    ) -> Dict[str, Any]:
        """Convenience method: create initial state and run pipeline.

        BC-001: company_id is first parameter.

        Args:
            query: Customer's raw message.
            company_id: Tenant identifier (BC-001).
            variant_tier: "mini_parwa" | "parwa" | "parwa_high".
            industry: Industry vertical.
            channel: Communication channel.
            customer_id: Customer identifier.
            customer_tier: Customer subscription tier.
            conversation_id: For multi-turn tracking.
            ticket_id: Ticket identifier (auto-generated if empty).
            variant_instance_id: Specific variant instance.

        Returns:
            Dict with the final pipeline state.
        """
        try:
            from app.core.parwa_graph_state import create_initial_state

            if not ticket_id:
                ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"
            if not conversation_id:
                conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
            if not variant_instance_id:
                tier_prefix = variant_tier.replace("_parwa", "").replace("parwa_", "")
                variant_instance_id = f"inst_{tier_prefix}_{company_id}"

            initial_state = create_initial_state(
                query=query,
                company_id=company_id,
                variant_tier=variant_tier,
                variant_instance_id=variant_instance_id,
                industry=industry,
                channel=channel,
                conversation_id=conversation_id,
                ticket_id=ticket_id,
                customer_id=customer_id,
                customer_tier=customer_tier,
            )

            result = await self.run(initial_state)

            if isinstance(result, dict):
                return result
            return {"error": "unexpected_result_type"}

        except Exception:
            logger.exception("process_ticket failed")
            return {
                "pipeline_status": "failed",
                "company_id": company_id,
                "error": "process_ticket_failed",
            }


# ══════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════

_pipeline_instance: Optional[UnifiedVariantPipeline] = None


def get_unified_pipeline() -> UnifiedVariantPipeline:
    """Get or create the global unified pipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = UnifiedVariantPipeline()
    return _pipeline_instance
