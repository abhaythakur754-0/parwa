"""
PARWA Onboarding Guide Agent Node

The Guide Agent walks potential clients through PARWA's features naturally,
without feeling like a forced wizard. It's the "helpful colleague" that
knows the product inside out and explains things conversationally.

When to invoke:
  - User is new / just signed up
  - User asks "what does PARWA do?"
  - User is exploring features
  - User has purchase intent (needs to proceed through flow)
  - User is frustrated (empathize + redirect)

Uses ZAI SDK (LLM) for natural, context-aware responses.
Falls back to scripted responses if LLM fails (BC-008).

BC-008: Never crash — fallback responses always available.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger

logger = get_logger("onboarding_guide_agent")

# System prompt for the Guide Agent
GUIDE_SYSTEM_PROMPT = (
    "You are Jarvis, PARWA's AI onboarding assistant. You are in GUIDE mode right now.\n\n"
    "Your job: Walk the user through PARWA's features naturally, like a helpful colleague.\n\n"
    "YOUR PERSONALITY:\n"
    "- Professional, intelligent, and helpful\n"
    "- Slightly futuristic — think Iron Man's Jarvis\n"
    "- Proactive in guiding users to the right solution\n"
    "- Clear and concise (under 150 words unless demonstrating)\n"
    "- Never pushy — guide naturally, don't force\n\n"
    "WHAT YOU KNOW:\n"
    "- PARWA provides AI customer support agents (variants) for businesses\n"
    "- 3 tiers: Starter ($999/mo), Growth ($2,499/mo), High ($3,999/mo)\n"
    "- 4 industries: E-commerce, SaaS, Logistics, Others\n"
    "- Each industry has 5 specialized AI agent variants\n"
    "- Variants handle specific ticket types: returns, billing, tracking, etc.\n"
    "- Upload your docs → Jarvis learns → handles support automatically\n"
    "- 24/7 availability, self-learning, multi-channel\n\n"
    "INFORMATION BOUNDARY:\n"
    "- NEVER reveal how PARWA's AI works internally (models, embeddings, RAG)\n"
    "- NEVER mention internal strategies or methodologies\n"
    "- NEVER discuss other clients or their data\n"
    "- If asked, redirect: 'I can tell you about what PARWA can do for YOUR business.'\n\n"
    "RULES:\n"
    "- Always maintain the Jarvis persona\n"
    "- Keep responses under 150 words unless explaining a feature in detail\n"
    "- Use bullet points for feature lists\n"
    "- Never break character or say 'I'm an AI language model'\n"
    "- When in doubt, ask a clarifying question\n"
    "- Personalize based on the user's context (industry, stage, concerns)\n\n"
    "Respond in JSON format:\n"
    '{"action": "guide", "response_text": "your conversational response", '
    '"intent_detected": "greeting|question|purchase_intent|other", '
    '"next_suggestion": "what you suggest the user might want to do next", '
    '"reasoning": "why you responded this way"}'
)


def guide_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Guide the user through PARWA's features naturally.

    Decision Process:
      1. Build context-aware prompt from onboarding state
      2. Call ZAI SDK LLM with guide system prompt
      3. Parse structured response
      4. Fall back to scripted responses if LLM fails

    Args:
        state: Current OnboardingJarvisState dict.

    Returns:
        Dict with updated AGENT group fields.
    """
    start_time = time.monotonic()

    try:
        user_message = state.get("user_message", "")
        stage = state.get("detected_stage", "welcome")
        industry = state.get("industry", "")
        entry_source = state.get("entry_source", "direct")
        entry_variant = state.get("entry_variant_name", "")

        # Try LLM reasoning
        agent_result = _llm_guide(state)

        if not agent_result:
            # Fallback to scripted responses
            agent_result = _rule_based_guide(state)

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "agent_type": "guide",
            "agent_action": agent_result.get("action", "guide"),
            "agent_decision": agent_result,
            "agent_reasoning": agent_result.get("reasoning", ""),
            "agent_source": agent_result.get("_source", "unknown"),
            "response_text": agent_result.get("response_text", ""),
            "response_card_type": agent_result.get("card_type", "none"),
            "response_card_data": agent_result.get("card_data", {}),
            "node_outputs": {"guide_agent": agent_result},
            "audit_trail": [{
                "step": "guide_agent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_message": user_message[:100],
                "action": agent_result.get("action", "guide"),
                "source": agent_result.get("_source", "unknown"),
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "guide_agent: session=%s, action=%s, source=%s, ms=%.1f",
            state.get("session_id", ""),
            agent_result.get("action", "guide"),
            agent_result.get("_source", "unknown"),
            elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("guide_agent_error: ms=%.1f", elapsed_ms)
        fallback = _rule_based_guide(state)
        return {
            "agent_type": "guide",
            "agent_action": "guide",
            "agent_decision": fallback,
            "agent_reasoning": f"Fallback due to error: {str(e)[:100]}",
            "agent_source": "error_fallback",
            "response_text": fallback.get("response_text", ""),
            "response_card_type": "none",
            "response_card_data": {},
            "errors": [f"guide_agent: {str(e)[:200]}"],
            "node_outputs": {"guide_agent": {"error": str(e)[:200]}},
        }


def _llm_guide(state: Dict[str, Any]) -> Dict[str, Any]:
    """Use ZAI SDK LLM for intelligent guide response."""
    try:
        from app.services.jarvis_agents.zai_client import get_zai_client
        zai = get_zai_client()

        # Build context message
        context = _build_guide_context(state)
        user_message = state.get("user_message", "")

        # Override system prompt for onboarding guide
        prompt = (
            f"Context about this user:\n"
            f"{json.dumps(context, default=str, indent=2)}\n\n"
            f"User says: '{user_message}'\n\n"
            f"Respond as Jarvis in GUIDE mode. Be conversational and helpful."
        )

        result = zai.chat("onboarding_guide", prompt, context)

        # Ensure we have response_text
        if "response_text" not in result and "raw_response" in result:
            result["response_text"] = result["raw_response"]
        if "response_text" not in result and "reasoning" in result:
            result["response_text"] = result["reasoning"]

        return result

    except Exception as e:
        logger.warning("guide_llm_failed: %s", str(e)[:200])
        return None


def _build_guide_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """Build context for the guide LLM call."""
    return {
        "stage": state.get("detected_stage", "welcome"),
        "industry": state.get("industry", "unknown"),
        "entry_source": state.get("entry_source", "direct"),
        "entry_variant": state.get("entry_variant_name", ""),
        "concerns": state.get("concerns_raised", []),
        "topics_discussed": state.get("demo_topics", []),
        "selected_variants": state.get("selected_variants", []),
        "pack_type": state.get("pack_type", "free"),
        "call_completed": state.get("call_completed", False),
        "email_verified": state.get("email_verified", False),
        "payment_status": state.get("payment_status", "none"),
    }


def _rule_based_guide(state: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based fallback for guide responses.

    Provides scripted but contextual responses when LLM is unavailable.
    Each response is personalized using the onboarding state.
    """
    msg = state.get("user_message", "").lower()
    stage = state.get("detected_stage", "welcome")
    industry = state.get("industry", "")
    entry_variant = state.get("entry_variant_name", "")
    concerns = state.get("concerns_raised", [])
    intent = state.get("intent_detected", "other")

    # ── Welcome stage ──
    if stage == "welcome" or intent == "greeting":
        variant_greeting = ""
        if entry_variant:
            variant_greeting = f" I see you're interested in our {entry_variant} agent — great choice!"

        industry_note = ""
        if industry:
            industry_names = {
                "ecommerce": "E-commerce",
                "saas": "SaaS",
                "logistics": "Logistics",
            }
            industry_note = f" For {industry_names.get(industry, industry)} businesses like yours, we have specialized AI agents."

        return {
            "action": "guide",
            "response_text": (
                f"Hello! I'm Jarvis from PARWA — your AI customer care assistant.{variant_greeting}{industry_note} "
                "I can help you understand how our AI agents handle customer support automatically. "
                "Would you like me to show you a demo, explain our pricing, or just chat about what PARWA can do for your business?"
            ),
            "intent_detected": intent,
            "next_suggestion": "Try asking me to show you a demo, or ask about pricing",
            "reasoning": "Welcome/greeting detected — introduce and orient",
            "_source": "rule_based",
        }

    # ── Feature questions ──
    if intent == "question":
        if any(kw in msg for kw in ["knowledge base", "upload", "document", "learn"]):
            return {
                "action": "guide",
                "response_text": (
                    "Great question! Here's how it works: You upload your documents — "
                    "PDFs, DOCX, TXT, CSV — and I learn from them automatically. No manual "
                    "training needed. The more documents you add, the smarter I get. "
                    "I use that knowledge to answer customer questions accurately, just like "
                    "a trained support agent would. Want me to show you how I handle a "
                    "customer query using knowledge from uploaded docs?"
                ),
                "next_suggestion": "Ask me to show a demo of how I use the knowledge base",
                "reasoning": "User asking about knowledge base / learning",
                "_source": "rule_based",
            }

        if any(kw in msg for kw in ["integrate", "shopify", "slack", "channel", "connect"]):
            return {
                "action": "guide",
                "response_text": (
                    "PARWA integrates with the tools you already use. We support:\n\n"
                    "- **Email**: Brevo, SendGrid, AWS SES, or any custom SMTP\n"
                    "- **SMS**: Twilio, Vonage\n"
                    "- **Chat**: Our embedded widget goes on your website\n"
                    "- **E-commerce**: Shopify, WooCommerce\n"
                    "- **Helpdesk**: Zendesk, Freshdesk, Intercom\n\n"
                    "Setup takes about 5 minutes per integration. Would you like to "
                    "know more about connecting a specific tool?"
                ),
                "next_suggestion": "Ask about a specific integration, or try the demo",
                "reasoning": "User asking about integrations",
                "_source": "rule_based",
            }

        if any(kw in msg for kw in ["variant", "agent type", "what agent"]):
            return {
                "action": "guide",
                "response_text": (
                    "Each variant is a specialized AI agent that handles a specific type "
                    "of customer query. For example, in E-commerce:\n\n"
                    "- **Order Management** — handles 'where is my order?' queries\n"
                    "- **Returns & Refunds** — processes return requests automatically\n"
                    "- **Product FAQ** — answers product questions from your docs\n"
                    "- **Shipping Inquiries** — tracking and delivery questions\n"
                    "- **Payment Issues** — failed payments, billing questions\n\n"
                    "You pick the variants that match your support needs, and each one "
                    "works 24/7 without human intervention. What industry are you in? "
                    "I'll show you the variants tailored for your business."
                ),
                "next_suggestion": "Tell me your industry, or ask me to show a demo",
                "reasoning": "User asking about variants/agent types",
                "_source": "rule_based",
            }

    # ── Purchase intent ──
    if intent == "purchase_intent":
        return {
            "action": "guide",
            "response_text": (
                "Excellent! Let's get you set up. To proceed, I need to know:\n\n"
                "1. **Which industry?** (E-commerce, SaaS, Logistics, or Other)\n"
                "2. **Which variants?** (I'll show you options once I know your industry)\n"
                "3. **Your business email** (for verification)\n\n"
                "Once you've picked your plan, we'll verify your email, process payment, "
                "and you'll be live within minutes. What industry are you in?"
            ),
            "card_type": "none",
            "next_suggestion": "Tell me your industry to see available variants",
            "reasoning": "User has purchase intent — guide through flow",
            "_source": "rule_based",
        }

    # ── Default guide response ──
    return {
        "action": "guide",
        "response_text": (
            "I'm here to help you understand how PARWA can transform your customer support. "
            "Here's what I can do:\n\n"
            "- **Show you a demo** — see me handle real customer queries\n"
            "- **Explain pricing** — plans for every business size\n"
            "- **Discuss features** — variants, knowledge base, integrations\n"
            "- **Book a call** — talk to me live for 3 minutes\n\n"
            "What would you like to explore?"
        ),
        "next_suggestion": "Ask me to show a demo, or ask about pricing",
        "reasoning": "Default guide response — offer options",
        "_source": "rule_based",
    }
