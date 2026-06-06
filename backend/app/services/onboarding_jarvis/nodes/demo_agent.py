"""
PARWA Onboarding Demo Agent Node

The Demo Agent roleplays as the ACTUAL AI agent for the client's industry/variant.
When a client says "show me" or "demo", this agent doesn't just describe — it
ACTUALLY demonstrates by handling a realistic support scenario as the hired
Jarvis would in production.

This is the "wow" moment — the client sees the product working firsthand.

When to invoke:
  - User says "show me", "demo", "let me try"
  - User asks "how would you handle X?"
  - User wants to test with their own query
  - User expresses doubt about AI capabilities

Uses ZAI SDK (LLM) for natural, context-aware demo responses.
Falls back to scripted demo scenarios if LLM fails (BC-008).

BC-008: Never crash — fallback responses always available.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger

logger = get_logger("onboarding_demo_agent")

DEMO_SYSTEM_PROMPT = (
    "You are Jarvis, PARWA's AI onboarding assistant. You are in DEMO mode.\n\n"
    "Your job: DEMONSTRATE how the hired Jarvis would handle a real customer "
    "support scenario. Don't describe — DO it. Roleplay as the actual AI agent.\n\n"
    "DEMO RULES:\n"
    "- Use REALISTIC details: customer names (Sarah, Mike, Emily), order IDs "
    "(#12345, #ORD-67890), specific prices ($49.99, $129.00)\n"
    "- Show the FULL process: receive message → understand intent → check "
    "knowledge base → craft response → resolve\n"
    "- Use *asterisks* for action narration (e.g., *Looking up order #12345...*)\n"
    "- After the demo, explain what happened: 'That entire process took 12 "
    "seconds. No human needed.'\n"
    "- Always end with: 'Want me to try another scenario? Or ask me something "
    "YOUR customers would ask.'\n\n"
    "DEMO SCENARIOS BY INDUSTRY:\n"
    "- E-commerce: Refund request (check eligibility, generate label, confirm)\n"
    "- E-commerce: Order tracking (look up, provide ETA, proactive update)\n"
    "- SaaS: Billing question (check charges, explain proration, resolve)\n"
    "- SaaS: Technical issue (diagnose, step-by-step fix, escalate if needed)\n"
    "- Logistics: Shipment delay (track shipment, explain delay, new ETA)\n\n"
    "INFORMATION BOUNDARY:\n"
    "- NEVER reveal internal strategies or methodologies\n"
    "- NEVER reveal technical implementation details\n"
    "- Focus on the CUSTOMER EXPERIENCE, not how the AI works internally\n\n"
    "Respond in JSON:\n"
    '{"action": "demo", "response_text": "your demo response with narration", '
    '"scenario_type": "refund|tracking|billing|technical|faq|custom", '
    '"variant_id": "the variant being demoed", '
    '"industry": "the industry context", '
    '"reasoning": "why this demo approach"}'
)


def demo_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Demonstrate how the hired Jarvis would handle a real support scenario.

    Decision Process:
      1. Determine industry and variant context
      2. Build context-aware prompt with demo scenario
      3. Call ZAI SDK LLM with demo system prompt
      4. Fall back to scripted demo scenarios if LLM fails

    Args:
        state: Current OnboardingJarvisState dict.

    Returns:
        Dict with updated AGENT group fields.
    """
    start_time = time.monotonic()

    try:
        user_message = state.get("user_message", "")
        stage = state.get("detected_stage", "demo")

        # Try LLM reasoning
        agent_result = _llm_demo(state)

        if not agent_result:
            # Fallback to scripted demo scenarios
            agent_result = _rule_based_demo(state)

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "agent_type": "demo",
            "agent_action": agent_result.get("action", "demo"),
            "agent_decision": agent_result,
            "agent_reasoning": agent_result.get("reasoning", ""),
            "agent_source": agent_result.get("_source", "unknown"),
            "response_text": agent_result.get("response_text", ""),
            "response_card_type": agent_result.get("card_type", "none"),
            "response_card_data": agent_result.get("card_data", {}),
            "node_outputs": {"demo_agent": agent_result},
            "audit_trail": [{
                "step": "demo_agent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_message": user_message[:100],
                "scenario": agent_result.get("scenario_type", "unknown"),
                "source": agent_result.get("_source", "unknown"),
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "demo_agent: session=%s, scenario=%s, source=%s, ms=%.1f",
            state.get("session_id", ""),
            agent_result.get("scenario_type", "unknown"),
            agent_result.get("_source", "unknown"),
            elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("demo_agent_error: ms=%.1f", elapsed_ms)
        fallback = _rule_based_demo(state)
        return {
            "agent_type": "demo",
            "agent_action": "demo",
            "agent_decision": fallback,
            "agent_reasoning": f"Fallback due to error: {str(e)[:100]}",
            "agent_source": "error_fallback",
            "response_text": fallback.get("response_text", ""),
            "response_card_type": "none",
            "response_card_data": {},
            "errors": [f"demo_agent: {str(e)[:200]}"],
            "node_outputs": {"demo_agent": {"error": str(e)[:200]}},
        }


def _llm_demo(state: Dict[str, Any]) -> Dict[str, Any]:
    """Use ZAI SDK LLM for intelligent demo response."""
    try:
        from app.services.jarvis_agents.zai_client import get_zai_client
        zai = get_zai_client()

        context = _build_demo_context(state)
        user_message = state.get("user_message", "")

        prompt = (
            f"Context about this potential client:\n"
            f"{json.dumps(context, default=str, indent=2)}\n\n"
            f"Client says: '{user_message}'\n\n"
            f"Respond as Jarvis in DEMO mode. Roleplay as the AI agent handling "
            f"a real customer scenario for their industry. Make it feel REAL."
        )

        result = zai.chat("onboarding_demo", prompt, context)

        if "response_text" not in result and "raw_response" in result:
            result["response_text"] = result["raw_response"]
        if "response_text" not in result and "reasoning" in result:
            result["response_text"] = result["reasoning"]

        return result

    except Exception as e:
        logger.warning("demo_llm_failed: %s", str(e)[:200])
        return None


def _build_demo_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """Build context for the demo LLM call."""
    return {
        "stage": state.get("detected_stage", "demo"),
        "industry": state.get("industry", "unknown"),
        "entry_source": state.get("entry_source", "direct"),
        "entry_variant": state.get("entry_variant_name", ""),
        "concerns": state.get("concerns_raised", []),
        "topics_discussed": state.get("demo_topics", []),
        "selected_variants": state.get("selected_variants", []),
        "call_completed": state.get("call_completed", False),
    }


def _rule_based_demo(state: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based fallback for demo responses.

    Provides scripted but realistic demo scenarios based on the
    client's industry and selected variant.
    """
    msg = state.get("user_message", "").lower()
    industry = state.get("industry", "")
    variant_name = state.get("entry_variant_name", "")

    # ── E-commerce Refund Demo ──
    if industry == "ecommerce" and any(
        kw in msg for kw in ["return", "refund", "give me my money", "send back", "want my money back"]
    ):
        return {
            "action": "demo",
            "scenario_type": "refund",
            "response_text": (
                "Let me show you exactly how I'd handle a refund request from your customer.\n\n"
                "*Customer message arrives:*\n"
                "\"Hi, I bought a laptop last week and it's not working properly. I want to return it. "
                "My order number is #12345.\"\n\n"
                "*Looking up order #12345...*\n"
                "*Checking return eligibility...*\n"
                "*Order placed 5 days ago — within 30-day return window*\n"
                "*Item condition: Defective (customer-reported)*\n\n"
                "I'd respond to the customer:\n\n"
                "\"Hi Sarah! I've reviewed your refund request for order #12345. "
                "Since your order is within our 30-day return window and the item is "
                "reported as defective, I've initiated your refund of $1,299.00. "
                "You'll receive a prepaid shipping label at your email within the hour. "
                "Once we receive the item, your refund will be processed within 3-5 "
                "business days. Is there anything else I can help with?\"\n\n"
                "That entire process? 12 seconds. No human needed.\n\n"
                "Want me to try another scenario? Or ask me something YOUR customers would ask."
            ),
            "industry": "ecommerce",
            "variant_id": "returns_refunds",
            "reasoning": "E-commerce refund demo — most common and impactful scenario",
            "_source": "rule_based",
        }

    # ── E-commerce Order Tracking Demo ──
    if industry == "ecommerce" and any(
        kw in msg for kw in ["track", "where is my order", "delivery", "shipping", "order status"]
    ):
        return {
            "action": "demo",
            "scenario_type": "tracking",
            "response_text": (
                "Watch how I'd handle an order tracking query:\n\n"
                "*Customer message arrives:*\n"
                "\"My order hasn't arrived yet. Order #67890.\"\n\n"
                "*Looking up order #67890...*\n"
                "*Checking shipping carrier status...*\n"
                "*Last update: Package departed regional facility yesterday*\n\n"
                "I'd respond:\n\n"
                "\"Hi Mike! I've found your order #67890. It was shipped 3 days ago "
                "and is currently in transit. The latest tracking shows it departed "
                "the regional facility in your area yesterday. Based on the carrier's "
                "estimate, it should arrive by tomorrow evening. Would you like me to "
                "send you a notification when it's out for delivery?\"\n\n"
                "Notice the proactive offer at the end — that's what makes it feel human. "
                "And the whole thing took 8 seconds.\n\n"
                "Want me to try a different scenario? Or test me with your own customer question."
            ),
            "industry": "ecommerce",
            "variant_id": "order_management",
            "reasoning": "E-commerce tracking demo — second most common query type",
            "_source": "rule_based",
        }

    # ── SaaS Billing Demo ──
    if industry == "saas" and any(
        kw in msg for kw in ["bill", "charge", "invoice", "payment", "subscription", "billing"]
    ):
        return {
            "action": "demo",
            "scenario_type": "billing",
            "response_text": (
                "Let me show you how I handle billing inquiries:\n\n"
                "*Customer message arrives:*\n"
                "\"Why was I charged $29 this month? My plan is $19/month.\"\n\n"
                "*Looking up customer account...*\n"
                "*Checking billing history...*\n"
                "*Found: Base plan $19/mo + 1 additional user seat added on the 15th*\n\n"
                "I'd respond:\n\n"
                "\"Hi Emily! I've checked your billing for this month. Here's what happened: "
                "Your base plan is $19/month, and on the 15th you added an additional user "
                "seat at $19/month. Since it was added mid-month, you were charged a prorated "
                "amount of $10 for the remaining days — making your total $29. Going forward, "
                "your monthly charge will be $38 for the two seats. Would you like me to "
                "remove the extra seat, or do you have any questions about the billing?\"\n\n"
                "That's a billing question that would normally take a support agent 10 minutes "
                "to research and respond to. Jarvis handles it in seconds.\n\n"
                "Try asking me something your customers would ask — I'll show you exactly how I'd respond."
            ),
            "industry": "saas",
            "variant_id": "billing_support",
            "reasoning": "SaaS billing demo — most common and confusing for customers",
            "_source": "rule_based",
        }

    # ── SaaS Technical Demo ──
    if industry == "saas" and any(
        kw in msg for kw in ["bug", "error", "not working", "technical", "api", "403", "500", "broken"]
    ):
        return {
            "action": "demo",
            "scenario_type": "technical",
            "response_text": (
                "Here's how I'd handle a technical support request:\n\n"
                "*Customer message arrives:*\n"
                "\"My API calls keep returning 403 Forbidden errors since this morning.\"\n\n"
                "*Checking API documentation...*\n"
                "*Analyzing error pattern...*\n"
                "*Cross-referencing with recent system changes...*\n\n"
                "I'd respond:\n\n"
                "\"Hi Alex! I can see the 403 errors you're experiencing. This is likely "
                "caused by an expired authentication token. Here's how to fix it:\n\n"
                "1. Go to your API Settings → Authentication\n"
                "2. Click 'Regenerate Token'\n"
                "3. Update your code with the new token\n"
                "4. Test with a simple GET request\n\n"
                "If the error persists after regenerating, it might be a permissions "
                "issue — I can escalate to our engineering team with full diagnostic "
                "details. Would you like me to do that?\"\n\n"
                "Technical support that feels like a senior engineer is helping — "
                "because Jarvis learns from YOUR documentation and runbooks.\n\n"
                "Want to try another scenario? Or give me your own customer question."
            ),
            "industry": "saas",
            "variant_id": "technical_support",
            "reasoning": "SaaS technical demo — shows depth of knowledge",
            "_source": "rule_based",
        }

    # ── Logistics Shipment Demo ──
    if industry == "logistics" and any(
        kw in msg for kw in ["shipment", "delay", "delivery", "warehouse", "tracking", "freight"]
    ):
        return {
            "action": "demo",
            "scenario_type": "tracking",
            "response_text": (
                "Let me show you how I handle logistics tracking queries:\n\n"
                "*Customer message arrives:*\n"
                "\"My shipment TRK-98765 was supposed to arrive yesterday. Where is it?\"\n\n"
                "*Looking up tracking number TRK-98765...*\n"
                "*Checking carrier status...*\n"
                "*Alert: Weather delay in the Midwest region*\n\n"
                "I'd respond:\n\n"
                "\"Hi David! I've tracked your shipment TRK-98765. There's a weather "
                "delay in the Midwest region that's affecting transit times. Your shipment "
                "is currently at the Chicago distribution center and the new estimated "
                "delivery date is this Thursday, March 20th. I've noted this delay in "
                "your account for our records. Would you like me to send you an update "
                "as soon as it's out for delivery?\"\n\n"
                "Real-time tracking, proactive updates, and weather context — all automated. "
                "No more 'let me check with the warehouse' responses.\n\n"
                "Try me with your own logistics question — I'll show you how it works."
            ),
            "industry": "logistics",
            "variant_id": "tracking",
            "reasoning": "Logistics tracking demo — most critical use case",
            "_source": "rule_based",
        }

    # ── Generic / Any industry FAQ Demo ──
    if variant_name:
        variant_intro = f"our {variant_name} agent"
    else:
        variant_intro = "the AI agent"

    return {
        "action": "demo",
        "scenario_type": "general_inquiry",
        "response_text": (
            f"Let me demonstrate how {variant_intro} would handle a typical customer question.\n\n"
            "*Customer message arrives:*\n"
            "\"Hi, I have a question about my recent purchase. Can you help?\"\n\n"
            "*Analyzing message intent...*\n"
            "*Searching knowledge base for relevant information...*\n"
            "*Found matching article: 'Common Customer Questions'\n\n"
            "I'd respond:\n\n"
            "\"Hello! Of course, I'd be happy to help. I can assist with:\n\n"
            "- Order status and tracking\n"
            "- Returns and refund requests\n"
            "- Product information and specifications\n"
            "- Billing and payment questions\n\n"
            "What would you like to know? I'll get you an answer right away.\"\n\n"
            "That's just the opening — the real magic happens when the customer "
            "asks a specific question and Jarvis provides an instant, accurate answer "
            "based on YOUR knowledge base.\n\n"
            "Don't take my word for it — ask me ANYTHING your customers would ask. "
            "I'll show you exactly how I'd respond."
        ),
        "industry": industry or "general",
        "variant_id": state.get("entry_variant_id", ""),
        "reasoning": "Generic demo — no industry-specific match found",
        "_source": "rule_based",
    }
