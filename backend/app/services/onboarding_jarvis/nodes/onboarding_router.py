"""
PARWA Onboarding Router Agent Node

The FIRST node in the onboarding agent graph. When a user sends a message,
this node analyzes the message + onboarding context and decides which
specialist agent should handle it.

Uses ZAI SDK (LLM) for intelligent routing. Falls back to rule-based
routing if LLM fails (BC-008).

Agent Selection Logic:
  - guide_agent:     User is exploring, asking about features, needs direction
  - salesman_agent:  User is hesitant, comparing, or at a decision point
  - demo_agent:      User wants to see Jarvis in action, asks "show me"
  - call_agent:      User wants to book/take a demo call
  - awareness_agent: Context enrichment only (no direct response to user)

BC-008: Never crash — rule-based fallback always available.
"""

import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger

logger = get_logger("onboarding_router")


def onboarding_router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Route a user message to the appropriate onboarding agent.

    Decision Process:
      1. Try rule-based intent detection first (fast, no LLM)
      2. If confidence < 0.7, use ZAI SDK LLM for intelligent routing
      3. If LLM fails: Fall back to rule-based routing
      4. Write routing decision to state

    Args:
        state: Current OnboardingJarvisState dict.

    Returns:
        Dict with updated ROUTER group fields.
    """
    start_time = time.monotonic()

    try:
        user_message = state.get("user_message", "")
        detected_stage = state.get("detected_stage", "welcome")
        company_id = state.get("company_id", "")

        # Step 1: Rule-based intent detection (fast path)
        rule_result = _rule_based_route(state)

        if rule_result.get("confidence", 0) >= 0.7:
            router_result = rule_result
        else:
            # Step 2: LLM routing via ZAI SDK
            try:
                from app.services.jarvis_agents.zai_client import get_zai_client
                zai = get_zai_client()
                context = _build_router_context(state)
                user_prompt = _build_llm_prompt(state, rule_result)
                llm_result = zai.chat("onboarding_router", user_prompt, context)
                router_result = _validate_llm_route(llm_result)
            except Exception as e:
                logger.warning(
                    "onboarding_router_llm_failed: %s, using_rules", str(e)[:200],
                )
                router_result = rule_result

        valid_agents = {
            "guide", "salesman", "demo", "call", "awareness", "no_action",
        }
        selected_agent = router_result.get("agent", "guide")
        if selected_agent not in valid_agents:
            selected_agent = "guide"

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "router_decision": selected_agent,
            "router_reasoning": router_result.get("reasoning", ""),
            "router_confidence": router_result.get("confidence", 0.5),
            "router_source": router_result.get("_source", "unknown"),
            "router_parameters": router_result.get("parameters", {}),
            "intent_detected": router_result.get("intent", ""),
            "sentiment": router_result.get("sentiment", "neutral"),
            "node_outputs": {"onboarding_router": router_result},
            "audit_trail": [{
                "step": "onboarding_router",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_message": user_message[:100],
                "selected_agent": selected_agent,
                "intent": router_result.get("intent", ""),
                "confidence": router_result.get("confidence", 0),
                "source": router_result.get("_source", "unknown"),
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "onboarding_router: session=%s, agent=%s, intent=%s, "
            "confidence=%.2f, source=%s, ms=%.1f",
            state.get("session_id", ""),
            selected_agent,
            router_result.get("intent", ""),
            router_result.get("confidence", 0),
            router_result.get("_source", "unknown"),
            elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("onboarding_router_error: ms=%.1f", elapsed_ms)
        return {
            "router_decision": "guide",
            "router_reasoning": f"Router error: {str(e)[:200]}",
            "router_confidence": 0.3,
            "router_source": "error_fallback",
            "router_parameters": {},
            "intent_detected": "unknown",
            "sentiment": "neutral",
            "errors": [f"onboarding_router: {str(e)[:200]}"],
            "node_outputs": {"onboarding_router": {"error": str(e)[:200]}},
        }


def _rule_based_route(state: Dict[str, Any]) -> Dict[str, Any]:
    """Fast rule-based routing using keyword/regex matching.

    Returns a dict with agent, reasoning, confidence, intent, sentiment.
    """
    msg = state.get("user_message", "").lower().strip()
    stage = state.get("detected_stage", "welcome")
    entry_source = state.get("entry_source", "direct")
    concerns = state.get("concerns_raised", [])

    # Default
    result = {
        "agent": "guide",
        "reasoning": "Default routing for general messages",
        "confidence": 0.5,
        "intent": "other",
        "sentiment": "neutral",
        "_source": "rule_based",
    }

    # ── Greeting / Welcome ──
    if re.match(r'^(hi|hello|hey|namaste|good morning|good evening|howdy)\b', msg):
        result.update({
            "agent": "guide",
            "reasoning": "User greeting detected — guide should welcome and orient",
            "confidence": 0.9,
            "intent": "greeting",
            "sentiment": "positive",
        })
        return result

    # ── Demo / Show me ──
    if any(kw in msg for kw in ["show me", "demo", "demonstrate", "let me see", "try it", "how would you handle", "show me how"]):
        result.update({
            "agent": "demo",
            "reasoning": "User wants to see Jarvis in action — demo agent should roleplay",
            "confidence": 0.9,
            "intent": "demo_request",
            "sentiment": "excited",
        })
        return result

    # ── Call / Voice ──
    if any(kw in msg for kw in ["call", "phone", "voice", "talk to someone", "speak", "ring me", "call me"]):
        result.update({
            "agent": "call",
            "reasoning": "User wants a demo call — call agent should handle booking/execution",
            "confidence": 0.9,
            "intent": "call_request",
            "sentiment": "positive",
        })
        return result

    # ── Objections / Concerns / Skepticism ──
    objection_keywords = [
        "expensive", "too much", "not sure", "thinking about it",
        "competitor", "already use", "zendesk", "intercom", "freshdesk",
        "what if", "worried", "scam", "trust", "security", "data safe",
        "wrong answer", "mistake", "not convinced", "don't need",
    ]
    if any(kw in msg for kw in objection_keywords):
        result.update({
            "agent": "salesman",
            "reasoning": "User has objections/concerns — salesman should address them",
            "confidence": 0.85,
            "intent": "objection",
            "sentiment": "skeptical",
        })
        return result

    # ── Pricing / Cost / Value ──
    pricing_keywords = [
        "price", "cost", "how much", "pricing", "plan", "tier",
        "subscribe", "payment", "afford", "budget", "roi", "value",
        "worth it", "compare",
    ]
    if any(kw in msg for kw in pricing_keywords):
        result.update({
            "agent": "salesman",
            "reasoning": "User asking about pricing/value — salesman should demonstrate ROI",
            "confidence": 0.85,
            "intent": "pricing_inquiry",
            "sentiment": "neutral",
        })
        return result

    # ── Purchase / Subscribe intent ──
    purchase_keywords = [
        "buy", "subscribe", "sign up", "get started", "i want", "purchase",
        "proceed", "pay", "checkout", "ready to go",
    ]
    if any(kw in msg for kw in purchase_keywords):
        result.update({
            "agent": "guide",
            "reasoning": "User has purchase intent — guide should walk them through flow",
            "confidence": 0.85,
            "intent": "purchase_intent",
            "sentiment": "positive",
        })
        return result

    # ── Feature / Product questions ──
    feature_keywords = [
        "how does", "what is", "can it", "does it", "feature", "capability",
        "integrate", "shopify", "slack", "email", "sms", "channel",
        "knowledge base", "upload", "document",
    ]
    if any(kw in msg for kw in feature_keywords):
        result.update({
            "agent": "guide",
            "reasoning": "User asking about features — guide should explain capabilities",
            "confidence": 0.8,
            "intent": "question",
            "sentiment": "neutral",
        })
        return result

    # ── Industry-specific questions ──
    industry_keywords = [
        "ecommerce", "e-commerce", "saas", "logistics", "retail",
        "industry", "my business", "my company",
    ]
    if any(kw in msg for kw in industry_keywords):
        result.update({
            "agent": "salesman",
            "reasoning": "User asking about industry fit — salesman should tailor pitch",
            "confidence": 0.75,
            "intent": "question",
            "sentiment": "neutral",
        })
        return result

    # ── Frustration ──
    frustration_keywords = [
        "frustrated", "annoyed", "waste", "stupid", "doesn't work",
        "broken", "bad", "terrible", "horrible",
    ]
    if any(kw in msg for kw in frustration_keywords):
        result.update({
            "agent": "guide",
            "reasoning": "User is frustrated — guide should empathize and redirect",
            "confidence": 0.8,
            "intent": "other",
            "sentiment": "frustrated",
        })
        return result

    return result


def _build_router_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """Build the context dict for the LLM."""
    return {
        "company_id": state.get("company_id", ""),
        "entry_source": state.get("entry_source", "direct"),
        "entry_variant": state.get("entry_variant_name", ""),
        "industry": state.get("industry", ""),
        "detected_stage": state.get("detected_stage", "welcome"),
        "message_count_today": state.get("message_count_today", 0),
        "pack_type": state.get("pack_type", "free"),
        "payment_status": state.get("payment_status", "none"),
        "concerns_raised": state.get("concerns_raised", []),
        "selected_variants": state.get("selected_variants", []),
        "demo_topics": state.get("demo_topics", []),
        "call_completed": state.get("call_completed", False),
        "email_verified": state.get("email_verified", False),
    }


def _build_llm_prompt(state: Dict[str, Any], rule_result: Dict[str, Any]) -> str:
    """Build the LLM prompt for routing."""
    return (
        f"User message: '{state.get('user_message', '')}'\n\n"
        f"Current stage: {state.get('detected_stage', 'welcome')}\n"
        f"Entry source: {state.get('entry_source', 'direct')}\n"
        f"Industry: {state.get('industry', 'unknown')}\n"
        f"Rule-based suggestion: {rule_result.get('agent', 'guide')} "
        f"(confidence: {rule_result.get('confidence', 0)})\n\n"
        f"Which onboarding agent should handle this? "
        f"Consider the user's intent, sentiment, and stage in the journey."
    )


def _validate_llm_route(llm_result: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize the LLM routing result."""
    valid_agents = {"guide", "salesman", "demo", "call", "awareness", "no_action"}
    agent = llm_result.get("agent", "guide")
    if agent not in valid_agents:
        # Try adding _agent suffix
        if agent.replace("_agent", "") in valid_agents:
            agent = agent.replace("_agent", "")
        else:
            agent = "guide"

    return {
        "agent": agent,
        "reasoning": llm_result.get("reasoning", ""),
        "confidence": min(1.0, max(0.0, float(llm_result.get("confidence", 0.5)))),
        "intent": llm_result.get("intent", "other"),
        "sentiment": llm_result.get("sentiment", "neutral"),
        "_source": "zai_llm",
        "parameters": llm_result.get("parameters", {}),
    }
