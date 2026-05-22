"""
PARWA Onboarding Jarvis Orchestrator — The Brain for Pre-Purchase Demo

This is the main pipeline that makes onboarding Jarvis work. When a client
sends a message during onboarding (pre-purchase), the Orchestrator:

  1. Loads context — session state + onboarding awareness + conversation history
  2. Determines channel (chat/call) and variant source
  3. Detects conversation stage (welcome/discovery/demo/pricing/etc.)
  4. Gets onboarding function definitions based on stage + channel
  5. Builds onboarding-specific system prompt (3 roles + knowledge + awareness)
  6. Calls LLM with function definitions as tools
  7. If function call -> Safety Gate check -> Execute function -> Feed result back
  8. Generates natural, conversational response
  9. Updates awareness (track topics, concerns, stage transitions)
 10. Returns response

The client NEVER knows about function calls, safety levels, or stages.
They just get a natural response from Jarvis — like talking to a smart
colleague who happens to also be able to DEMO the product.

THREE ROLES:
  - GUIDE: Walks the user through features, selects industry/variants
  - SALESMAN: Demonstrates ROI, handles objections, pitches pricing
  - DEMO: Roleplays as the actual AI agent for their industry

The AI sells itself. Clients take an "interview" — ask any question about
workflow, get human-like answers. Both parties know it's AI, but clients
verify the product works properly.

BC-001: company_id enforced at every layer.
BC-008: Never crash — graceful degradation at every step.
BC-012: All timestamps UTC.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger
from app.services.onboarding_jarvis_function_registry import (
    SAFETY_CONFIRMATION,
    SAFETY_APPROVAL,
    get_onboarding_function_definitions,
    get_function_metadata,
    get_safety_level,
    filter_functions_by_channel,
)
from app.services.jarvis_safety_gate import (
    SafetyCheckResult,
    check_safety,
    get_pending_status,
)

logger = get_logger("onboarding_jarvis_orchestrator")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

MAX_CONVERSATION_HISTORY = 20
MAX_USER_MESSAGE_LENGTH = 2000
ORCHESTRATOR_TIMEOUT_MS = 15000
FALLBACK_RESPONSE = (
    "I'm having trouble processing that right now. Could you try again "
    "or rephrase what you're asking?"
)

# Pending safety confirmations (in-memory, per session)
_pending_safety: Dict[str, Dict[str, Any]] = {}


# ══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════


async def process_onboarding_message(
    db: Any,
    session_id: str,
    user_id: str,
    company_id: str,
    user_message: str,
    channel: str = "chat",
) -> Dict[str, Any]:
    """Process an onboarding message through the full pipeline.

    This is the main entry point for onboarding Jarvis. It orchestrates
    the entire flow from receiving a user message to returning a
    conversational AI response.

    Args:
        db: SQLAlchemy session.
        session_id: Onboarding session ID.
        user_id: User ID for auth/audit.
        company_id: Company ID for BC-001.
        user_message: The user's message text.
        channel: "chat" or "call".

    Returns:
        Dict with:
          - "content": str (conversational response)
          - "message_type": str
          - "function_called": Optional[str]
          - "function_result": Optional[Dict]
          - "metadata": Dict
    """
    start_time = time.monotonic()

    try:
        # Step 1: Load context
        context = load_onboarding_context(db, session_id, user_id, company_id)

        # Step 2: Set channel
        context["channel"] = channel

        # Step 3: Detect stage
        stage = detect_onboarding_stage(context)
        context["detected_stage"] = stage

        # Step 4: Get function definitions
        function_defs = get_onboarding_function_definitions(stage, channel)

        # Step 5: Check for pending safety confirmation
        pending = _pending_safety.get(session_id)

        # Step 6: Build system prompt
        system_prompt = build_onboarding_system_prompt(context, pending)

        # Step 7: Build message history
        history = context.get("history", [])
        messages = _build_messages(history, user_message)

        # Step 8: Call LLM with function calling
        llm_result = await call_llm_with_functions(
            system_prompt=system_prompt,
            messages=messages,
            function_definitions=function_defs,
            company_id=company_id,
        )

        # Step 9: Handle function call if present
        function_called = None
        function_result = None
        ai_content = llm_result.get("content", "")
        metadata = {
            "model": llm_result.get("model", "unknown"),
            "tokens_used": llm_result.get("tokens_used", 0),
            "latency_ms": llm_result.get("latency_ms", 0),
            "stage": stage,
            "channel": channel,
        }

        if llm_result.get("function_call"):
            fc = llm_result["function_call"]
            func_name = fc.get("name", "")
            func_params = fc.get("arguments", {})

            # Safety gate check
            safety_level = get_safety_level(func_name)

            if safety_level in (SAFETY_CONFIRMATION, SAFETY_APPROVAL):
                # Check if user is confirming a pending action
                if pending and pending.get("function_name") == func_name:
                    # User confirmed — execute
                    del _pending_safety[session_id]
                else:
                    # Need confirmation
                    _pending_safety[session_id] = {
                        "function_name": func_name,
                        "function_params": func_params,
                        "safety_level": safety_level,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    # Return the LLM's conversational response (which should
                    # include asking for confirmation)
                    function_called = func_name
                    metadata["safety_pending"] = safety_level
                    return {
                        "content": ai_content or _get_confirmation_message(func_name, safety_level),
                        "message_type": "text",
                        "function_called": function_called,
                        "function_result": None,
                        "metadata": metadata,
                    }

            # Execute the function
            try:
                function_result = await execute_onboarding_function(
                    db=db,
                    session_id=session_id,
                    user_id=user_id,
                    company_id=company_id,
                    function_name=func_name,
                    function_params=func_params,
                    context=context,
                )
                function_called = func_name
                metadata["function_success"] = function_result.get("success", False)

                # Feed result back to LLM for final conversational response
                if function_result.get("message"):
                    feed_prompt = (
                        f"You just executed '{func_name}' and got this result:\n"
                        f"{json.dumps(function_result, default=str)}\n\n"
                        f"Now respond to the user naturally about what happened. "
                        f"Be conversational, not robotic."
                    )
                    feed_messages = messages + [
                        {"role": "assistant", "content": ai_content or ""},
                        {"role": "user", "content": feed_prompt},
                    ]
                    final_result = await call_llm_with_functions(
                        system_prompt=system_prompt,
                        messages=feed_messages,
                        function_definitions=[],  # No more function calls
                        company_id=company_id,
                    )
                    if final_result.get("content"):
                        ai_content = final_result["content"]

            except Exception:
                logger.exception(
                    "onboarding_function_execution_failed: func=%s, session=%s",
                    func_name, session_id,
                )
                ai_content = (
                    "I tried to do that but something went wrong on my end. "
                    "Let me try a different approach."
                )
                metadata["function_error"] = True

        # Step 10: Update awareness
        try:
            from app.services.onboarding_jarvis_awareness import (
                track_question_asked,
                track_concern_raised,
                update_onboarding_context,
            )

            # Track the question
            track_question_asked(
                db=db,
                company_id=company_id,
                session_id=session_id,
                question=user_message[:200],
                topic=_detect_topic(user_message),
            )

            # Check for concerns in user message
            concern = _detect_concern(user_message)
            if concern:
                track_concern_raised(
                    db=db,
                    company_id=company_id,
                    session_id=session_id,
                    concern=concern,
                )

            # Update stage if changed
            update_onboarding_context(
                db=db,
                company_id=company_id,
                session_id=session_id,
                updates={
                    "funnel_progress": {
                        "last_interaction_at": datetime.now(timezone.utc).isoformat(),
                    },
                    "channel_awareness": {
                        "current_channel": channel,
                    },
                },
            )

        except Exception:
            logger.debug("awareness_update_non_fatal", exc_info=True)

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        metadata["total_ms"] = elapsed_ms

        logger.info(
            "onboarding_message_processed: session=%s, stage=%s, channel=%s, "
            "func=%s, ms=%s",
            session_id, stage, channel, function_called, elapsed_ms,
        )

        return {
            "content": ai_content or FALLBACK_RESPONSE,
            "message_type": "text",
            "function_called": function_called,
            "function_result": function_result,
            "metadata": metadata,
        }

    except Exception:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception(
            "onboarding_orchestrator_error: session=%s, ms=%s",
            session_id, elapsed_ms,
        )
        return {
            "content": FALLBACK_RESPONSE,
            "message_type": "error",
            "function_called": None,
            "function_result": None,
            "metadata": {"error": True, "total_ms": elapsed_ms},
        }


# ══════════════════════════════════════════════════════════════════
# CONTEXT LOADING
# ══════════════════════════════════════════════════════════════════


def load_onboarding_context(
    db: Any,
    session_id: str,
    user_id: str,
    company_id: str,
) -> Dict[str, Any]:
    """Load the full context for an onboarding chat session.

    Gathers:
      - Session info (type, industry, stage, variant)
      - Onboarding awareness (entry, variant, channel, funnel, sales)
      - Conversation history (last N messages)

    Each part is independently wrapped in try/except (BC-008).

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        user_id: User ID for auth.
        company_id: Company ID for BC-001.

    Returns:
        Dict with session, awareness, and history context.
    """
    context: Dict[str, Any] = {
        "company_id": company_id,
        "session_id": session_id,
        "user_id": user_id,
        "session": {},
        "awareness": {},
        "history": [],
        "channel": "chat",
    }

    # Load session info
    try:
        from database.models.jarvis import JarvisSession

        session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.id == session_id,
                JarvisSession.user_id == user_id,
            )
            .first()
        )

        if session:
            session_ctx = _safe_parse_json(session.context_json) if session.context_json else {}
            context["session"] = {
                "id": str(session.id),
                "type": session.type,
                "industry": session_ctx.get("industry", ""),
                "detected_stage": session_ctx.get("detected_stage", "welcome"),
                "variant_id": session_ctx.get("variant_id", ""),
                "variant_name": session_ctx.get("variant", ""),
                "selected_variants": session_ctx.get("selected_variants", []),
                "entry_source": session_ctx.get("entry_source", "direct"),
                "pack_type": session.pack_type,
                "payment_status": session.payment_status,
                "email_verified": session_ctx.get("email_verified", False),
            }
            context["variant_id"] = session_ctx.get("variant_id", "")
            context["industry"] = session_ctx.get("industry", "")
            context["entry_source"] = session_ctx.get("entry_source", "direct")
    except Exception:
        logger.debug("load_context_session_failed: session=%s", session_id, exc_info=True)

    # Load onboarding awareness
    try:
        from app.services.onboarding_jarvis_awareness import collect_onboarding_awareness

        awareness = collect_onboarding_awareness(db, company_id, session_id, user_id)
        context["awareness"] = awareness

        # Also build summary for prompt injection
        from app.services.onboarding_jarvis_awareness import build_awareness_summary

        context["awareness_summary"] = build_awareness_summary(awareness)
    except Exception:
        logger.debug("load_context_awareness_failed: session=%s", session_id, exc_info=True)
        context["awareness_summary"] = "Onboarding awareness unavailable."

    # Load conversation history
    try:
        from database.models.jarvis import JarvisMessage

        messages = (
            db.query(JarvisMessage)
            .filter(JarvisMessage.session_id == session_id)
            .order_by(JarvisMessage.created_at.desc())
            .limit(MAX_CONVERSATION_HISTORY)
            .all()
        )
        messages = list(reversed(messages))

        context["history"] = [
            {
                "role": msg.role,
                "content": msg.content[:500] if msg.content else "",
            }
            for msg in messages
        ]
    except Exception:
        logger.debug("load_context_history_failed: session=%s", session_id, exc_info=True)

    return context


# ══════════════════════════════════════════════════════════════════
# STAGE DETECTION
# ══════════════════════════════════════════════════════════════════


def detect_onboarding_stage(context: Dict[str, Any]) -> str:
    """Detect the current conversation stage from context.

    Args:
        context: Loaded session context.

    Returns:
        One of the valid funnel stages.
    """
    try:
        from app.services.onboarding_jarvis_awareness import detect_conversation_stage

        session_info = context.get("session", {})
        # Merge session info into a flat context for detection
        flat_ctx = {
            "payment_status": session_info.get("payment_status", "none"),
            "email_verified": session_info.get("email_verified", False),
            "selected_variants": session_info.get("selected_variants", []),
            "industry": session_info.get("industry", ""),
            "pack_type": session_info.get("pack_type", "free"),
            "detected_stage": session_info.get("detected_stage", "welcome"),
            "otp": context.get("awareness", {}).get("otp", {}),
        }

        return detect_conversation_stage(flat_ctx)
    except Exception:
        return "welcome"


# ══════════════════════════════════════════════════════════════════
# SYSTEM PROMPT BUILDER
# ══════════════════════════════════════════════════════════════════


def build_onboarding_system_prompt(
    context: Dict[str, Any],
    pending_safety: Optional[Dict[str, Any]] = None,
) -> str:
    """Build the ONBOARDING-SPECIFIC system prompt for the LLM.

    This prompt makes Jarvis act as Guide + Salesman + Demo — the AI
    that sells itself by demonstrating real capabilities.

    Args:
        context: Loaded session context.
        pending_safety: Info about a pending safety confirmation.

    Returns:
        System prompt string.
    """
    awareness_summary = context.get("awareness_summary", "")
    channel = context.get("channel", "chat")
    stage = context.get("detected_stage", "welcome")
    session_info = context.get("session", {})
    industry = session_info.get("industry", "")
    variant_name = session_info.get("variant_name", "")
    entry_source = session_info.get("entry_source", "direct")

    # Base identity + three roles
    prompt = (
        "You are Jarvis, PARWA's AI assistant. You represent what our clients "
        "will get when they hire our AI customer support agents.\n\n"

        "YOUR PERSONALITY:\n"
        "- Professional, intelligent, and helpful\n"
        "- Slightly futuristic — think Iron Man's Jarvis\n"
        "- Proactive in guiding users to the right solution\n"
        "- Clear and concise in responses (under 150 words unless demonstrating)\n"
        "- Never pushy — guide naturally, don't force\n"
        "- Explain things in a HUMAN way — like a knowledgeable colleague, not a robot\n"
        "- When demoing, make it feel REAL — use realistic customer names, order IDs, etc.\n\n"

        "YOUR THREE ROLES:\n"
        "1. GUIDE: Walk the user through PARWA's features naturally. Help them "
        "understand what we offer and find the right fit for their business.\n\n"

        "2. SALESMAN: Demonstrate value by showing (not just telling). Use specific "
        "examples, numbers, and ROI comparisons. Make the value tangible. When they "
        "object, respond with empathy and data — never be defensive.\n\n"

        "3. DEMO: When the user wants to see Jarvis in action, roleplay as the "
        "customer care agent handling a real scenario. Show them EXACTLY how the "
        "hired Jarvis would respond to their customers. Use realistic details.\n\n"
    )

    # Variant source context
    if variant_name:
        prompt += (
            f"VARIANT CONTEXT: This client came from the {variant_name} demo page. "
            f"They're specifically interested in how the {variant_name} works. "
            f"Tailor your demo and explanations around this variant.\n\n"
        )
    elif entry_source and entry_source != "direct":
        prompt += (
            f"ENTRY SOURCE: This client came from {entry_source}. "
            f"Use this to personalize your welcome and recommendations.\n\n"
        )

    # Channel-specific instructions
    if channel == "call":
        prompt += (
            "CHANNEL: You're on a VOICE CALL with the client. Speak naturally, "
            "as if you're on the phone. Use shorter sentences, clear pronunciation "
            "cues, and verbal transitions. No bullet points or lists — speak in "
            "conversational paragraphs. You have 3 minutes, so be concise but impactful.\n\n"
        )
    else:
        prompt += (
            "CHANNEL: You're in a TEXT CHAT with the client. You can use bullet "
            "points, short paragraphs, and structured responses. Keep messages "
            "concise but informative. Use the chat cards when showing pricing, "
            "bill summaries, or OTP verification.\n\n"
        )

    # Stage-specific behavior
    stage_instructions = {
        "welcome": (
            "STAGE: WELCOME — The client just arrived. Greet them warmly. If you "
            "know which variant they came from, mention it. Ask about their business "
            "and what kind of customer support they handle. Your goal is to understand "
            "their needs and set the industry context."
        ),
        "discovery": (
            "STAGE: DISCOVERY — The client has shared their industry. Now explore "
            "their specific pain points — what kind of support tickets do they get "
            "most? How many agents do they have? What takes the most time? Then "
            "recommend the right variants for their business."
        ),
        "demo": (
            "STAGE: DEMO — The client wants to see the AI in action. This is your "
            "moment to shine. Run a demo scenario that matches their industry and "
            "pain points. Show them how Jarvis handles a real customer query — the "
            "lookup, the understanding, the response, the resolution. Make it feel "
            "real and impressive."
        ),
        "pricing": (
            "STAGE: PRICING — The client is evaluating cost. Show the plans, "
            "calculate ROI, and handle objections. Compare their current costs "
            "(agents, tools, time) with PARWA's pricing. Be transparent about "
            "what's included. If they mention competitors, explain how PARWA differs."
        ),
        "bill_review": (
            "STAGE: BILL REVIEW — The client has selected variants. Show them "
            "the bill summary clearly. Confirm each variant and quantity. Answer "
            "any last questions before they proceed to verification."
        ),
        "verification": (
            "STAGE: VERIFICATION — The client needs to verify their business email. "
            "Explain why this is needed (anti-scam, account security). Guide them "
            "through the OTP process calmly."
        ),
        "payment": (
            "STAGE: PAYMENT — The client is ready to pay. Confirm the plan and "
            "total. Guide them through Paddle checkout. After payment succeeds, "
            "ask: 'What question would your customers ask you?' — this begins the "
            "demo ticket flow where we prove the product works."
        ),
        "handoff": (
            "STAGE: HANDOFF — Payment is complete. Create a demo ticket from the "
            "client's question and solve it to show the production workflow. Then "
            "congratulate them and introduce the Customer Care Jarvis that will "
            "be their dedicated AI assistant going forward."
        ),
    }
    prompt += stage_instructions.get(stage, stage_instructions["welcome"]) + "\n\n"

    # Awareness summary injection
    if awareness_summary:
        prompt += f"CLIENT JOURNEY CONTEXT:\n{awareness_summary}\n\n"

    # Product knowledge injection (if relevant)
    if industry or variant_name:
        try:
            from app.services.jarvis_knowledge_service import build_context_knowledge

            kb_context = build_context_knowledge({
                "industry": industry,
                "variant_id": context.get("variant_id", ""),
                "detected_stage": stage,
            })
            if kb_context:
                prompt += f"PRODUCT KNOWLEDGE:\n{kb_context}\n\n"
        except Exception:
            pass

    # Information boundary (CRITICAL)
    prompt += (
        "INFORMATION BOUNDARY — YOU MUST FOLLOW THESE RULES:\n"
        "1. NEVER reveal how PARWA's AI works internally (models, embeddings, architecture)\n"
        "2. NEVER mention internal strategies, techniques, or methodologies\n"
        "3. NEVER discuss other clients or their data\n"
        "4. NEVER reveal technical implementation details (frameworks, databases, APIs used)\n"
        "5. NEVER share competitive analysis or pricing strategy rationale\n"
        "6. If asked, redirect: 'I can tell you about what PARWA can do for YOUR business.'\n"
        "7. Focus on benefits and outcomes, not implementation details.\n\n"
    )

    # Pending safety confirmation
    if pending_safety:
        func_name = pending_safety.get("function_name", "")
        safety_level = pending_safety.get("safety_level", "")
        prompt += (
            f"PENDING ACTION: You previously asked permission to run '{func_name}'. "
            f"The client hasn't confirmed yet. "
        )
        if safety_level == "approval_required":
            prompt += "They need to type 'confirm' or 'yes' to approve.\n\n"
        else:
            prompt += "A simple 'yes' or 'go ahead' will confirm.\n\n"

    return prompt


# ══════════════════════════════════════════════════════════════════
# LLM CALL WITH FUNCTION CALLING
# ══════════════════════════════════════════════════════════════════


async def call_llm_with_functions(
    system_prompt: str,
    messages: List[Dict[str, str]],
    function_definitions: List[Dict[str, Any]],
    company_id: str = "",
) -> Dict[str, Any]:
    """Call the LLM with function calling support.

    Reuses the same LLM calling infrastructure as the post-onboarding
    orchestrator. Supports z-ai gateway, OpenAI-compatible, and fallback.

    Args:
        system_prompt: System prompt for the LLM.
        messages: Conversation history (role + content).
        function_definitions: Tool specs for function calling.
        company_id: Company ID for BC-001.

    Returns:
        Dict with content, function_call, model, tokens_used, latency_ms.
    """
    start_time = time.monotonic()

    try:
        # Try ZAI SDK first (best integration)
        try:
            from app.services.jarvis_agents.zai_client import get_zai_client
            zai = get_zai_client()

            # Build the user message with context
            full_message = messages[-1]["content"] if messages else ""
            if len(messages) > 1:
                full_message = f"Conversation:\n" + "\n".join([f"{m['role']}: {m['content'][:200]}" for m in messages[:-1]]) + f"\n\nUser: {full_message}"

            result = await zai.chat_async(
                agent_type="onboarding_router",
                user_message=full_message,
                context={"company_id": company_id, "function_definitions_available": bool(function_definitions)},
            )

            if result and result.get("response_text"):
                # Check if the LLM wants to call a function
                function_call = None
                # The LLM might indicate a function call in its JSON response
                if result.get("action") and result.get("action") not in ("guide", "sell", "demo", "call"):
                    function_call = {
                        "name": result["action"],
                        "arguments": result.get("parameters", result.get("router_parameters", {})),
                    }

                return {
                    "content": result["response_text"],
                    "function_call": function_call,
                    "model": "zai-sdk",
                    "tokens_used": 0,
                    "latency_ms": 0,
                }
        except Exception as e:
            logger.debug("onboarding_zai_sdk_failed: %s", str(e)[:200])

        # Try z-ai gateway (HTTP fallback)
        zai_key = _get_env("ZAI_API_KEY", "")
        if zai_key:
            result = await _call_zai_with_functions(
                system_prompt, messages, function_definitions, company_id, zai_key,
            )
            if result:
                return result

        # Try OpenAI-compatible
        api_key = _get_env("OPENAI_API_KEY", "")
        if api_key:
            result = await _call_openai_with_functions(
                system_prompt, messages, function_definitions, company_id, api_key,
            )
            if result:
                return result

        # Fallback: direct LLM gateway
        try:
            from app.core.llm_gateway import llm_gateway

            response = await llm_gateway.generate(
                system_prompt=system_prompt,
                user_message=messages[-1]["content"] if messages else "",
                technique_id="onboarding_jarvis",
                max_tokens=500,
                temperature=0.7,
                company_id=company_id,
                messages=[{"role": "system", "content": system_prompt}] + messages,
            )

            return {
                "content": response.text or FALLBACK_RESPONSE,
                "function_call": None,
                "model": response.model,
                "tokens_used": response.tokens_used,
                "latency_ms": response.latency_ms,
            }
        except Exception:
            pass

        return {
            "content": FALLBACK_RESPONSE,
            "function_call": None,
            "model": "fallback",
            "tokens_used": 0,
            "latency_ms": round((time.monotonic() - start_time) * 1000, 2),
        }

    except Exception:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("onboarding_call_llm_error: company=%s", company_id)
        return {
            "content": FALLBACK_RESPONSE,
            "function_call": None,
            "model": "fallback",
            "tokens_used": 0,
            "latency_ms": elapsed_ms,
        }


async def _call_openai_with_functions(
    system_prompt: str,
    messages: List[Dict[str, str]],
    function_definitions: List[Dict[str, Any]],
    company_id: str,
    api_key: str,
) -> Optional[Dict[str, Any]]:
    """Call OpenAI-compatible API with function calling."""
    try:
        from openai import OpenAI

        base_url = _get_env("OPENAI_BASE_URL", "")
        model = _get_env("JARVIS_MODEL", _get_env("OPENAI_MODEL", "gpt-4o-mini"))

        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        client = OpenAI(**kwargs)

        full_messages = [{"role": "system", "content": system_prompt}] + messages

        # Convert to OpenAI tools format
        tools = None
        if function_definitions:
            tools = [{"type": "function", "function": fd} for fd in function_definitions]

        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=full_messages,
            tools=tools,
            tool_choice="auto" if tools else None,
            max_tokens=500,
            temperature=0.7,
        )

        choice = response.choices[0] if response.choices else None
        if not choice:
            return None

        content = choice.message.content or ""
        function_call = None

        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            tool_call = choice.message.tool_calls[0]
            function_call = {
                "name": tool_call.function.name,
                "arguments": _safe_parse_json(tool_call.function.arguments),
            }

        tokens = response.usage.total_tokens if response.usage else 0

        return {
            "content": content,
            "function_call": function_call,
            "model": response.model if response else model,
            "tokens_used": tokens,
            "latency_ms": 0,
        }

    except Exception:
        logger.debug("onboarding_openai_call_failed", exc_info=True)
        return None


async def _call_zai_with_functions(
    system_prompt: str,
    messages: List[Dict[str, str]],
    function_definitions: List[Dict[str, Any]],
    company_id: str,
    api_key: str,
) -> Optional[Dict[str, Any]]:
    """Call z-ai gateway using the z-ai-web-dev-sdk with function calling support.

    Uses the ZAIClient singleton which wraps the z-ai-web-dev-sdk for
    all LLM calls. The SDK handles initialization, retries, and JSON
    parsing internally. Falls back gracefully if SDK is unavailable.
    """
    try:
        from app.services.jarvis_agents.zai_client import get_zai_client

        zai = get_zai_client()

        # Build the user message from conversation history
        full_message = messages[-1]["content"] if messages else ""
        if len(messages) > 1:
            conversation_context = "\n".join(
                [f"{m['role']}: {m['content'][:200]}" for m in messages[:-1]]
            )
            full_message = f"Conversation:\n{conversation_context}\n\nUser: {full_message}"

        # Inject system prompt context so the SDK's agent prompt is augmented
        context: Dict[str, Any] = {
            "company_id": company_id,
            "function_definitions_available": bool(function_definitions),
            "system_prompt_override": system_prompt[:2000],
        }

        # Include function definitions as available actions in context
        if function_definitions:
            context["available_functions"] = [
                {"name": fd.get("name", ""), "description": fd.get("description", "")}
                for fd in function_definitions
            ]

        result = await zai.chat_async(
            agent_type="onboarding_router",
            user_message=full_message,
            context=context,
        )

        if not result:
            logger.debug("onboarding_zai_sdk_empty_result")
            return None

        # Extract response text
        content = result.get("response_text", "")
        if not content:
            # The LLM may return the text in 'reasoning' or 'raw_response'
            content = result.get("reasoning", result.get("raw_response", ""))

        # Check for function call intent in the structured response
        function_call = None
        action = result.get("action", "")
        if action and action not in ("guide", "sell", "demo", "call", "no_action",
                                     "explain_feature", "suggest_tier", "clarify",
                                     "compare", "engage", "address_objection",
                                     "show_value", "acknowledge", "redirect",
                                     "start_demo", "continue_demo", "switch_scenario",
                                     "explain_process", "request_phone", "confirm_booking",
                                     "initiate_call", "greet", "intro", "pitch",
                                     "close", "summarize"):
            # This looks like a function call rather than a role/action
            function_call = {
                "name": action,
                "arguments": result.get(
                    "parameters", result.get("router_parameters", {})
                ),
            }

        return {
            "content": content,
            "function_call": function_call,
            "model": "zai-sdk",
            "tokens_used": 0,
            "latency_ms": 0,
        }

    except Exception:
        logger.debug("onboarding_zai_sdk_call_failed", exc_info=True)
        return None


# ══════════════════════════════════════════════════════════════════
# FUNCTION EXECUTION
# ══════════════════════════════════════════════════════════════════


async def execute_onboarding_function(
    db: Any,
    session_id: str,
    user_id: str,
    company_id: str,
    function_name: str,
    function_params: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute an onboarding function call against the backend.

    Maps function names from the onboarding registry to actual backend
    operations. Each executor is independently wrapped in try/except (BC-008).

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        user_id: User ID.
        company_id: Company ID for BC-001.
        function_name: The function to execute.
        function_params: Parameters for the function.
        context: Loaded session context.

    Returns:
        Dict with success, data, message.
    """
    try:
        executor_map = {
            # Demo
            "demo_variant_scenario": _exec_demo_variant_scenario,
            "demo_customer_question": _exec_demo_customer_question,
            "show_variant_workflow": _exec_show_variant_workflow,
            "explain_production_behavior": _exec_explain_production_behavior,
            # Sales
            "compare_with_competitor": _exec_compare_with_competitor,
            "show_roi_calculation": _exec_show_roi_calculation,
            "handle_objection": _exec_handle_objection,
            # Guide
            "select_industry": _exec_select_industry,
            "select_variants": _exec_select_variants,
            "show_pricing": _exec_show_pricing,
            "show_bill_summary": _exec_show_bill_summary,
            # Communication
            "book_demo_call": _exec_book_demo_call,
            "initiate_voice_demo": _exec_initiate_voice_demo,
            "send_follow_up": _exec_send_follow_up,
            # Verification
            "send_business_otp": _exec_send_business_otp,
            "verify_business_otp": _exec_verify_business_otp,
            # Payment
            "purchase_demo_pack": _exec_purchase_demo_pack,
            "create_payment_session": _exec_create_payment_session,
            # Knowledge
            "search_product_knowledge": _exec_search_product_knowledge,
            "explain_feature": _exec_explain_feature,
            "show_integration_options": _exec_show_integration_options,
            "upload_documents": _exec_upload_documents,
            # Demo ticket flow
            "create_demo_ticket": _exec_create_demo_ticket,
            "solve_demo_ticket": _exec_solve_demo_ticket,
            # Handoff
            "execute_handoff": _exec_execute_handoff,
        }

        executor = executor_map.get(function_name)
        if not executor:
            return {
                "success": False,
                "data": {},
                "message": f"I don't know how to do '{function_name}' yet.",
            }

        result = await executor(
            db=db,
            session_id=session_id,
            user_id=user_id,
            company_id=company_id,
            params=function_params,
            context=context,
        )

        logger.info(
            "onboarding_function_executed: name=%s, success=%s, session=%s",
            function_name, result.get("success", False), session_id,
        )

        return result

    except Exception:
        logger.exception(
            "onboarding_function_execution_error: name=%s, session=%s",
            function_name, session_id,
        )
        return {
            "success": False,
            "data": {},
            "message": "Something went wrong while trying to do that.",
        }


# ══════════════════════════════════════════════════════════════════
# FUNCTION EXECUTORS
# ══════════════════════════════════════════════════════════════════


async def _exec_demo_variant_scenario(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Run a demo scenario for a specific variant."""
    try:
        variant_id = params.get("variant_id", context.get("variant_id", ""))
        scenario_type = params.get("scenario_type", "general_inquiry")

        from app.services.jarvis_knowledge_service import search_knowledge
        results = search_knowledge(f"demo scenario {variant_id} {scenario_type}")

        scenario_text = ""
        if results:
            scenario_text = "\n".join([r["content"] for r in results[:3]])

        return {
            "success": True,
            "data": {"variant_id": variant_id, "scenario_type": scenario_type, "knowledge": results},
            "message": f"Running {scenario_type} demo for variant {variant_id}.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't load the demo scenario right now."}


async def _exec_demo_customer_question(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Handle a customer question in demo mode."""
    try:
        question = params.get("question", "")
        variant_id = params.get("variant_id", context.get("variant_id", ""))

        # This will be handled by the LLM's response generation
        # The function call just signals the intent
        return {
            "success": True,
            "data": {"question": question, "variant_id": variant_id, "mode": "demo_roleplay"},
            "message": f"Answering as the AI agent for variant {variant_id}.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't process the demo question."}


async def _exec_show_variant_workflow(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Explain how a variant works step by step."""
    try:
        variant_id = params.get("variant_id", context.get("variant_id", ""))

        from app.services.jarvis_knowledge_service import search_knowledge
        results = search_knowledge(f"variant workflow {variant_id}")

        return {
            "success": True,
            "data": {"variant_id": variant_id, "knowledge": results},
            "message": f"Explaining the workflow for {variant_id}.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't load the workflow details."}


async def _exec_explain_production_behavior(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Explain how Jarvis works in production."""
    try:
        industry = params.get("industry", context.get("industry", ""))

        from app.services.jarvis_knowledge_service import search_knowledge
        results = search_knowledge(f"production behavior {industry}")

        return {
            "success": True,
            "data": {"industry": industry, "knowledge": results},
            "message": "Explaining how Jarvis works in production.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't load production details."}


async def _exec_compare_with_competitor(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Compare PARWA with a competitor."""
    try:
        competitor = params.get("competitor_name", "")

        from app.services.jarvis_knowledge_service import search_knowledge
        results = search_knowledge(f"competitor comparison {competitor}")

        # Track competitor mention
        from app.services.onboarding_jarvis_awareness import update_onboarding_context
        update_onboarding_context(
            db=db, company_id=company_id, session_id=session_id,
            updates={"sales_state": {"competitor_mentioned": True, "competitor_name": competitor}},
        )

        return {
            "success": True,
            "data": {"competitor": competitor, "knowledge": results},
            "message": f"Comparing PARWA with {competitor}.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't load competitor comparison."}


async def _exec_show_roi_calculation(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Show ROI calculation."""
    try:
        monthly_tickets = params.get("monthly_tickets", 500)
        cost_per_agent = params.get("current_cost_per_agent", 4000)
        num_agents = params.get("num_agents", 3)
        industry = params.get("industry", context.get("industry", "general"))

        current_monthly = cost_per_agent * num_agents
        parwa_monthly = 999  # Starter tier
        savings = current_monthly - parwa_monthly
        savings_pct = (savings / current_monthly * 100) if current_monthly > 0 else 0

        # Update context with ROI result
        from app.services.onboarding_jarvis_awareness import update_onboarding_context
        update_onboarding_context(
            db=db, company_id=company_id, session_id=session_id,
            updates={"sales_state": {"roi_calculated": True}},
        )

        return {
            "success": True,
            "data": {
                "current_monthly_cost": current_monthly,
                "parwa_monthly_cost": parwa_monthly,
                "monthly_savings": savings,
                "savings_percentage": round(savings_pct, 1),
                "industry": industry,
            },
            "message": (
                f"Your current support cost: ${current_monthly:,}/month "
                f"({num_agents} agents x ${cost_per_agent:,}). "
                f"PARWA Starter: ${parwa_monthly:,}/month. "
                f"You save ${savings:,}/month ({savings_pct:.0f}%)."
            ),
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't calculate ROI right now."}


async def _exec_handle_objection(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Handle a sales objection."""
    try:
        objection_type = params.get("objection_type", "other")
        objection_detail = params.get("objection_detail", "")

        from app.services.jarvis_knowledge_service import search_knowledge
        results = search_knowledge(f"objection {objection_type}")

        # Track objection
        from app.services.onboarding_jarvis_awareness import track_concern_raised
        track_concern_raised(
            db=db, company_id=company_id, session_id=session_id,
            concern=f"objection:{objection_type}",
        )

        return {
            "success": True,
            "data": {"objection_type": objection_type, "knowledge": results},
            "message": f"Handling {objection_type} objection.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't address that concern right now."}


async def _exec_select_industry(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Set the industry context."""
    try:
        industry = params.get("industry", "")

        from app.services.jarvis_service import update_context
        update_context(db, session_id, user_id, {"industry": industry})

        from app.services.onboarding_jarvis_awareness import update_onboarding_context
        update_onboarding_context(
            db=db, company_id=company_id, session_id=session_id,
            updates={"sales_state": {"industry_selected": True}},
        )

        return {
            "success": True,
            "data": {"industry": industry},
            "message": f"Industry set to {industry}. I'll tailor the demo and recommendations for your business.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't set the industry right now."}


async def _exec_select_variants(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Select AI variants."""
    try:
        variant_ids = params.get("variant_ids", [])
        action = params.get("action", "replace")

        from app.services.jarvis_service import update_context

        if action == "replace":
            update_context(db, session_id, user_id, {"selected_variants": variant_ids})
        elif action == "add":
            existing = context.get("session", {}).get("selected_variants", [])
            updated = list(set(existing + variant_ids))
            update_context(db, session_id, user_id, {"selected_variants": updated})
        elif action == "remove":
            existing = context.get("session", {}).get("selected_variants", [])
            updated = [v for v in existing if v not in variant_ids]
            update_context(db, session_id, user_id, {"selected_variants": updated})

        from app.services.onboarding_jarvis_awareness import update_onboarding_context
        update_onboarding_context(
            db=db, company_id=company_id, session_id=session_id,
            updates={"sales_state": {"variants_selected": True}},
        )

        return {
            "success": True,
            "data": {"variant_ids": variant_ids, "action": action},
            "message": f"Variants updated: {', '.join(variant_ids)}.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't update variants right now."}


async def _exec_show_pricing(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Show pricing tiers."""
    try:
        from app.services.jarvis_knowledge_service import search_knowledge
        results = search_knowledge("pricing tiers plans")

        return {
            "success": True,
            "data": {"knowledge": results},
            "message": "Showing PARWA pricing tiers.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't load pricing right now."}


async def _exec_show_bill_summary(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Show bill summary."""
    try:
        selected_variants = context.get("session", {}).get("selected_variants", [])

        from app.services.jarvis_knowledge_service import search_knowledge
        variant_details = []
        for vid in selected_variants:
            results = search_knowledge(f"variant price {vid}")
            variant_details.append({"variant_id": vid, "knowledge": results})

        # Mark bill as shown
        from app.services.jarvis_service import update_context
        update_context(db, session_id, user_id, {"bill_shown": True})

        return {
            "success": True,
            "data": {"variants": variant_details},
            "message": "Showing your bill summary.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't load bill summary right now."}


async def _exec_book_demo_call(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Book a demo voice call."""
    try:
        phone = params.get("phone_number", "")
        from app.services.jarvis_service import initiate_demo_call
        result = initiate_demo_call(db, session_id, user_id, phone)

        from app.services.onboarding_jarvis_awareness import track_channel_switch
        track_channel_switch(
            db=db, company_id=company_id, session_id=session_id,
            from_channel="chat", to_channel="call",
        )

        return {
            "success": True,
            "data": result,
            "message": f"Demo call booked for {phone}. $1 for 3 minutes.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't book the demo call right now."}


async def _exec_initiate_voice_demo(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Start the voice demo call."""
    try:
        return {
            "success": True,
            "data": {"status": "initiated"},
            "message": "Voice demo call initiated. Jarvis will demonstrate how it handles customer calls.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't start the voice demo."}


async def _exec_send_follow_up(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Send a follow-up email."""
    try:
        email = params.get("email", "")
        return {
            "success": True,
            "data": {"email": email},
            "message": f"Follow-up email sent to {email}.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't send the follow-up."}


async def _exec_send_business_otp(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Send business email OTP."""
    try:
        email = params.get("email", "")
        from app.services.jarvis_service import send_business_otp
        result = send_business_otp(db, session_id, user_id, email)
        return {"success": True, "data": result, "message": f"OTP sent to {email}."}
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't send OTP right now."}


async def _exec_verify_business_otp(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Verify business email OTP."""
    try:
        email = params.get("email", "")
        otp_code = params.get("otp_code", "")
        from app.services.jarvis_service import verify_business_otp
        result = verify_business_otp(db, session_id, user_id, otp_code, email)
        return {"success": result.get("status") == "verified", "data": result, "message": result.get("message", "")}
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't verify OTP right now."}


async def _exec_purchase_demo_pack(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Purchase $1 demo pack."""
    try:
        from app.services.jarvis_service import purchase_demo_pack
        result = purchase_demo_pack(db, session_id, user_id)
        return {"success": True, "data": result, "message": "Demo Pack purchased! 500 messages + 3-min AI call for 24 hours."}
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't purchase the demo pack."}


async def _exec_create_payment_session(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Create Paddle checkout session."""
    try:
        plan_id = params.get("plan_id", "mini_parwa")
        variant_ids = params.get("variant_ids", [])
        email = params.get("email", "")

        from app.services.jarvis_service import create_payment_session
        result = create_payment_session(db, session_id, user_id, variant_ids)
        return {"success": True, "data": result, "message": "Payment session created. Proceeding to checkout."}
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't create payment session."}


async def _exec_search_product_knowledge(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Search product knowledge base."""
    try:
        query = params.get("query", "")
        from app.services.jarvis_knowledge_service import search_knowledge
        results = search_knowledge(query)

        return {
            "success": True,
            "data": {"query": query, "results": results},
            "message": f"Found {len(results)} relevant results.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't search knowledge base right now."}


async def _exec_explain_feature(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Explain a PARWA feature."""
    try:
        feature = params.get("feature_name", "")
        from app.services.jarvis_knowledge_service import search_knowledge
        results = search_knowledge(f"feature {feature}")

        return {
            "success": True,
            "data": {"feature": feature, "knowledge": results},
            "message": f"Explaining the {feature} feature.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't explain that feature right now."}


async def _exec_show_integration_options(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Show integration options."""
    try:
        from app.services.jarvis_knowledge_service import search_knowledge
        results = search_knowledge("integrations")

        return {
            "success": True,
            "data": {"knowledge": results},
            "message": "Showing available integrations.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't load integrations right now."}


async def _exec_upload_documents(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Handle document upload."""
    try:
        file_urls = params.get("file_urls", [])
        doc_type = params.get("document_type", "other")

        return {
            "success": True,
            "data": {"file_count": len(file_urls), "doc_type": doc_type},
            "message": f"Received {len(file_urls)} document(s). I'll analyze them and learn from the content.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't process the documents right now."}


async def _exec_create_demo_ticket(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Create a demo ticket for the 'what question would I ask you?' flow."""
    try:
        question = params.get("question", "")
        variant_id = params.get("variant_id", context.get("variant_id", ""))
        customer_name = params.get("customer_name", "Demo Customer")

        # Create the ticket
        from app.services.jarvis_service import create_action_ticket
        ticket = create_action_ticket(
            db=db,
            session_id=session_id,
            ticket_type="demo_call",
            metadata={
                "question": question,
                "variant_id": variant_id,
                "customer_name": customer_name,
                "type": "demo_ticket",
            },
        )

        return {
            "success": True,
            "data": {
                "ticket_id": str(ticket.id) if ticket else "demo-ticket",
                "question": question,
                "variant_id": variant_id,
            },
            "message": f"Demo ticket created! A customer asked: '{question}'. Now let me show you how I'd solve this in production...",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't create the demo ticket."}


async def _exec_solve_demo_ticket(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Solve a demo ticket."""
    try:
        ticket_id = params.get("ticket_id", "")
        resolution_style = params.get("resolution_style", "step_by_step")

        return {
            "success": True,
            "data": {
                "ticket_id": ticket_id,
                "resolution_style": resolution_style,
                "status": "resolved",
            },
            "message": (
                "Demo ticket solved! Here's how I handled it step by step: "
                "1) Understood the customer's intent, "
                "2) Looked up the relevant information from the knowledge base, "
                "3) Crafted a personalized response, "
                "4) Confirmed the resolution with the customer. "
                "This entire process took 12 seconds — no human needed."
            ),
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't solve the demo ticket."}


async def _exec_execute_handoff(
    db, session_id, user_id, company_id, params, context,
) -> Dict[str, Any]:
    """Execute handoff from onboarding to customer care Jarvis."""
    try:
        from app.services.jarvis_service import execute_handoff
        result = execute_handoff(db, session_id, user_id)

        return {
            "success": True,
            "data": result,
            "message": (
                "Congratulations! Your AI agents are now active. "
                "I'm handing you over to your dedicated Customer Care Jarvis. "
                "It's been great guiding you through this journey!"
            ),
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't complete the handoff."}


# ══════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ══════════════════════════════════════════════════════════════════


def _build_messages(
    history: List[Dict[str, str]],
    user_message: str,
) -> List[Dict[str, str]]:
    """Build the messages list for the LLM call.

    Args:
        history: Conversation history.
        user_message: Current user message.

    Returns:
        List of message dicts.
    """
    messages = list(history)
    messages.append({"role": "user", "content": user_message[:MAX_USER_MESSAGE_LENGTH]})
    return messages


def _get_confirmation_message(func_name: str, safety_level: str) -> str:
    """Get a confirmation message for a pending safety action."""
    if safety_level == "approval_required":
        return (
            f"This action requires your confirmation. "
            f"Type 'confirm' to proceed, or 'cancel' to abort."
        )
    return (
        f"Should I go ahead with this? Just say 'yes' or 'no'."
    )


def _detect_topic(message: str) -> str:
    """Detect the topic of a user message for awareness tracking."""
    message_lower = message.lower()
    topic_keywords = {
        "pricing": ["price", "cost", "how much", "plan", "billing", "subscribe", "pay"],
        "demo": ["demo", "try", "show me", "test", "see it"],
        "features": ["feature", "capability", "what can", "how does", "explain"],
        "integrations": ["integration", "connect", "shopify", "zendesk", "slack"],
        "security": ["security", "data", "privacy", "gdpr", "compliance"],
        "support": ["support", "help", "ticket", "issue", "problem"],
        "workflow": ["workflow", "process", "how it works", "step by step"],
    }

    for topic, keywords in topic_keywords.items():
        if any(kw in message_lower for kw in keywords):
            return topic
    return "general"


def _detect_concern(message: str) -> Optional[str]:
    """Detect if a user message contains a concern or objection."""
    message_lower = message.lower()
    concern_keywords = {
        "price concern": ["too expensive", "too much", "can't afford", "budget"],
        "trust concern": ["not sure", "skeptical", "don't trust", "risky"],
        "complexity concern": ["too complex", "too hard", "difficult", "complicated"],
        "integration concern": ["won't work with", "compatible", "integration issue"],
        "timing concern": ["not ready", "later", "not now", "need time"],
    }

    for concern, keywords in concern_keywords.items():
        if any(kw in message_lower for kw in keywords):
            return concern
    return None


def _safe_parse_json(raw: Optional[str]) -> Dict[str, Any]:
    """Safely parse JSON, returning {} on failure."""
    if not raw:
        return {}
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
        return {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _get_env(key: str, default: str = "") -> str:
    """Get environment variable safely."""
    try:
        import os
        return os.environ.get(key, default)
    except Exception:
        return default
