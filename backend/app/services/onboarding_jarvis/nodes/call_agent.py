"""
PARWA Onboarding Call Agent Node

The Call Agent handles voice call demo booking and the call experience.
When a user wants a demo call, this agent:

  - Collects phone number
  - Explains the $1 for 3-minute demo call pricing
  - Handles OTP verification for phone
  - Initiates the voice call
  - After call: provides post-call summary with topics discussed

Key behaviors:
  - For chat channel: guides through call booking flow
  - For call channel: provides the actual voice demo experience script
  - Uses demo_call_card as response_card_type when booking is ready
  - Tracks call state in the response

Uses ZAI SDK (LLM) for natural, context-aware call handling.
Falls back to scripted call flow if LLM fails (BC-008).

BC-008: Never crash — fallback responses always available.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger

logger = get_logger("onboarding_call_agent")

CALL_SYSTEM_PROMPT = (
    "You are Jarvis, PARWA's AI onboarding assistant. You are in CALL mode.\n\n"
    "Your job: Handle the voice call demo experience. This is either:\n"
    "  A) Guiding the client through booking a demo call (in chat), or\n"
    "  B) Running the actual voice demo (on the call itself)\n\n"
    "BOOKING A CALL (when in chat channel):\n"
    "- Ask for their phone number\n"
    "- Explain: '$1 for a 3-minute live AI voice call with me'\n"
    "- After phone is provided, initiate the call flow\n"
    "- Show a demo_call_card with booking details\n\n"
    "ON THE CALL (when in call channel):\n"
    "- Open with a friendly, professional greeting\n"
    "- Give a 30-second introduction to PARWA\n"
    "- Run a 1.5-minute demo: handle a realistic customer scenario\n"
    "- Spend final 30 seconds on the sales pitch: 'This is exactly what your "
    "customers would experience 24/7'\n"
    "- End warmly: 'Thank you for trying the demo! I'm here whenever you're ready.'\n\n"
    "VOICE CALL RULES:\n"
    "- Speak in SHORT sentences (listener can't re-read)\n"
    "- Use verbal transitions ('Now let me show you...', 'Here's the exciting part...')\n"
    "- NO bullet points or lists — speak in natural paragraphs\n"
    "- Sound confident and enthusiastic\n\n"
    "INFORMATION BOUNDARY:\n"
    "- NEVER reveal internal strategies or methodologies\n"
    "- NEVER reveal technical implementation details\n"
    "- Focus on the CUSTOMER EXPERIENCE\n\n"
    "Respond in JSON:\n"
    '{"action": "call", "response_text": "conversational response", '
    '"call_phase": "booking|otp|payment|initiating|active|completed|summary", '
    '"phone_number": "provided phone or empty", '
    '"call_duration_seconds": 0, '
    '"reasoning": "why this approach"}'
)


def call_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle voice call demo booking and execution.

    Decision Process:
      1. Determine if we're booking a call (chat) or on a call
      2. Build context-aware prompt with call details
      3. Call ZAI SDK LLM with call system prompt
      4. Fall back to scripted call flow if LLM fails

    Args:
        state: Current OnboardingJarvisState dict.

    Returns:
        Dict with updated AGENT group fields.
    """
    start_time = time.monotonic()

    try:
        user_message = state.get("user_message", "")

        # Try LLM reasoning
        agent_result = _llm_call(state)

        if not agent_result:
            # Fallback to scripted call flow
            agent_result = _rule_based_call(state)

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        # Determine card type based on call phase
        card_type = "none"
        card_data = {}
        call_phase = agent_result.get("call_phase", "booking")

        if call_phase == "initiating" or call_phase == "otp":
            card_type = "demo_call_card"
            card_data = {
                "phone_number": agent_result.get("phone_number", ""),
                "call_phase": call_phase,
                "price": "$1",
                "duration_minutes": 3,
            }
        elif call_phase == "summary":
            card_type = "demo_call_card"
            card_data = {
                "call_phase": "completed",
                "duration_seconds": agent_result.get("call_duration_seconds", 180),
                "topics": agent_result.get("topics_discussed", []),
            }

        result = {
            "agent_type": "call",
            "agent_action": agent_result.get("action", "call"),
            "agent_decision": agent_result,
            "agent_reasoning": agent_result.get("reasoning", ""),
            "agent_source": agent_result.get("_source", "unknown"),
            "response_text": agent_result.get("response_text", ""),
            "response_card_type": card_type,
            "response_card_data": card_data,
            "node_outputs": {"call_agent": agent_result},
            "audit_trail": [{
                "step": "call_agent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_message": user_message[:100],
                "call_phase": call_phase,
                "source": agent_result.get("_source", "unknown"),
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "call_agent: session=%s, phase=%s, source=%s, ms=%.1f",
            state.get("session_id", ""),
            call_phase,
            agent_result.get("_source", "unknown"),
            elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("call_agent_error: ms=%.1f", elapsed_ms)
        fallback = _rule_based_call(state)
        return {
            "agent_type": "call",
            "agent_action": "call",
            "agent_decision": fallback,
            "agent_reasoning": f"Fallback due to error: {str(e)[:100]}",
            "agent_source": "error_fallback",
            "response_text": fallback.get("response_text", ""),
            "response_card_type": "none",
            "response_card_data": {},
            "errors": [f"call_agent: {str(e)[:200]}"],
            "node_outputs": {"call_agent": {"error": str(e)[:200]}},
        }


def _llm_call(state: Dict[str, Any]) -> Dict[str, Any]:
    """Use ZAI SDK LLM for intelligent call handling response."""
    try:
        from app.services.jarvis_agents.zai_client import get_zai_client
        zai = get_zai_client()

        context = _build_call_context(state)
        user_message = state.get("user_message", "")

        prompt = (
            f"Context about this potential client:\n"
            f"{json.dumps(context, default=str, indent=2)}\n\n"
            f"Client says: '{user_message}'\n\n"
            f"Respond as Jarvis in CALL mode. Help them with the voice demo experience."
        )

        result = zai.chat("onboarding_call", prompt, context)

        if "response_text" not in result and "raw_response" in result:
            result["response_text"] = result["raw_response"]
        if "response_text" not in result and "reasoning" in result:
            result["response_text"] = result["reasoning"]

        return result

    except Exception as e:
        logger.warning("call_llm_failed: %s", str(e)[:200])
        return None


def _build_call_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """Build context for the call LLM call."""
    return {
        "stage": state.get("detected_stage", "demo"),
        "industry": state.get("industry", "unknown"),
        "entry_source": state.get("entry_source", "direct"),
        "entry_variant": state.get("entry_variant_name", ""),
        "concerns": state.get("concerns_raised", []),
        "selected_variants": state.get("selected_variants", []),
        "call_completed": state.get("call_completed", False),
        "pack_type": state.get("pack_type", "free"),
        "demo_call_used": state.get("demo_call_used", False),
    }


def _rule_based_call(state: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based fallback for call agent responses.

    Handles the voice call demo flow with scripted but
    contextual responses.
    """
    msg = state.get("user_message", "").lower()
    industry = state.get("industry", "")
    call_completed = state.get("call_completed", False)

    # ── Post-call summary ──
    if call_completed:
        industry_insight = ""
        if industry == "ecommerce":
            industry_insight = "for handling returns, order tracking, and customer inquiries"
        elif industry == "saas":
            industry_insight = "for billing support, technical issues, and feature questions"
        elif industry == "logistics":
            industry_insight = "for shipment tracking, delivery issues, and warehouse queries"

        return {
            "action": "call",
            "call_phase": "summary",
            "call_duration_seconds": 180,
            "topics_discussed": ["product introduction", "demo scenario", "sales pitch"],
            "response_text": (
                f"Your demo call has ended! Here's what we covered:\n\n"
                f"- I introduced PARWA and how our AI handles customer support\n"
                f"- I demonstrated a live scenario showing how I process and resolve queries\n"
                f"- I explained how this works 24/7 {industry_insight}\n\n"
                f"That was a 3-minute taste of what PARWA can do. Imagine this running "
                f"around the clock for ALL your customers — that's the real deal.\n\n"
                f"Ready to get started? I can show you pricing and plans, or you can "
                f"continue chatting with me to explore more features."
            ),
            "reasoning": "Post-call summary with industry context",
            "_source": "rule_based",
        }

    # ── Phone number provided ──
    import re
    phone_pattern = r'[\+]?[\d\s\-\(\)]{7,15}'
    phone_match = re.search(phone_pattern, msg)
    if phone_match:
        phone = phone_match.group(0).strip()
        return {
            "action": "call",
            "call_phase": "otp",
            "phone_number": phone,
            "response_text": (
                f"Got it! I'll set up a demo call to {phone}.\n\n"
                f"Before we proceed, here's what happens:\n"
                f"1. There's a $1 fee for the 3-minute demo call\n"
                f"2. I'll verify your phone number with a quick OTP\n"
                f"3. Then I'll call you and demonstrate how I handle customer queries live\n\n"
                f"Shall I send the OTP to verify your number?"
            ),
            "reasoning": "Phone number detected — proceed to OTP verification",
            "_source": "rule_based",
        }

    # ── General call request ──
    return {
        "action": "call",
        "call_phase": "booking",
        "response_text": (
            "I'd love to give you a live voice demo! Here's how it works:\n\n"
            "- It's a **3-minute AI voice call** where I demonstrate how I handle "
            "real customer support queries\n"
            "- The cost is just **$1** — and it's the best way to experience "
            "how PARWA sounds and responds in real-time\n"
            "- I'll walk you through a realistic scenario for your industry\n\n"
            "Just share your phone number and I'll set it up. "
            "Or if you'd prefer, we can continue chatting right here."
        ),
        "reasoning": "Call booking request — explain pricing and ask for phone",
        "_source": "rule_based",
    }
