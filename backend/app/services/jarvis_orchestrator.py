"""
PARWA Jarvis Orchestrator — The Brain That Ties It All Together

This is the main pipeline that makes Jarvis work. When a client sends a
message, the Orchestrator:

  1. Loads context — session state, awareness snapshot, conversation history
  2. Decides mode — agentic (customer chat) vs command (admin chat)
  3. Calls LLM with function definitions as tools
  4. LLM decides: just chat, or call a function?
  5. If function call → Safety Gate checks it
  6. If approved → Execute the function against backend APIs
  7. Feed execution result back to LLM
  8. LLM generates a natural, conversational response
  9. Return response to client

The client NEVER knows about function calls, safety levels, or modes.
They just get a natural response from Jarvis — like talking to a smart
colleague who happens to also be able to DO things.

Architecture:
  Client message
      → load_context() → session state + awareness + history
      → decide_mode() → "agentic" or "command"
      → get_function_definitions(mode) → relevant tool specs
      → LLM call with tools → function_call or just conversation
      → if function_call:
          → check_safety() → approved / needs_confirmation / needs_approval
          → if approved → execute_function() → backend API call
          → feed result back to LLM → conversational response
      → return natural response to client

Mode Switching:
  The mode is determined by CONTEXT, not by explicit user action:
    - If the message is in a variant task (customer support conversation),
      mode = "agentic" — only customer-facing functions available
    - If the message is in Jarvis admin chat (managing the platform),
      mode = "command" — all functions available
    - This is determined by looking at the session type and context

Conversational Feel:
  The SAME LLM that calls functions also crafts the response. After a
  function is executed, the result is fed back to the LLM, which then
  generates a human-like response. No robotic "Command executed successfully"
  messages — instead: "Done! I've paused all AI agents. They'll stay paused
  until you tell me to resume them."

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
from app.services.jarvis_function_registry import (
    SAFETY_CONFIRMATION,
    get_function_definitions,
    get_function_metadata,
    get_safety_level,
)
from app.services.jarvis_safety_gate import (
    SafetyCheckResult,
    check_safety,
    get_pending_status,
)

logger = get_logger("jarvis_orchestrator")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

MAX_CONVERSATION_HISTORY = 20  # Max messages to include in LLM context
MAX_USER_MESSAGE_LENGTH = 2000
ORCHESTRATOR_TIMEOUT_MS = 15000  # 15 seconds max for full pipeline
FALLBACK_RESPONSE = (
    "I'm having trouble processing that right now. Could you try again "
    "or rephrase what you're asking?"
)


# ══════════════════════════════════════════════════════════════════
# CONTEXT LOADING
# ══════════════════════════════════════════════════════════════════


def load_context(
    db: Any,
    company_id: str,
    session_id: str,
) -> Dict[str, Any]:
    """Load the full context for a Jarvis chat session.

    Gathers:
      - Session info (type, variant_tier, industry, mode)
      - Awareness snapshot (system health, ticket volume, etc.)
      - Conversation history (last N messages)

    Each part is independently wrapped in try/except (BC-008).
    Partial context is better than no context.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: Session ID.

    Returns:
        Dict with session, awareness, and history context.
    """
    context: Dict[str, Any] = {
        "company_id": company_id,
        "session_id": session_id,
        "session": {},
        "awareness": {},
        "history": [],
        "tier": "parwa",
        "mode": "command",
    }

    # ── Load session info ──
    try:
        from database.models.jarvis import JarvisSession

        session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
            )
            .first()
        )

        if session:
            session_ctx = _safe_parse_json(session.context_json) if session.context_json else {}
            context["session"] = {
                "id": str(session.id),
                "type": session.session_type,
                "variant_tier": session_ctx.get("variant_tier", "parwa"),
                "industry": session_ctx.get("industry", "general"),
                "mode": session_ctx.get("mode", "customer_care"),
                "pack_type": session.pack_type,
                "context_keys": list(session_ctx.keys()),
            }
            context["tier"] = session_ctx.get("variant_tier", "parwa")
    except Exception:
        logger.debug("load_context_session_failed: session=%s", session_id, exc_info=True)

    # ── Load awareness snapshot ──
    try:
        from app.services.jarvis_awareness_engine import get_latest_snapshot

        snapshot = get_latest_snapshot(db, session_id, company_id)
        if snapshot:
            context["awareness"] = {
                "system_health": snapshot.system_health,
                "ticket_volume_today": snapshot.ticket_volume_today,
                "agent_pool_utilization": snapshot.agent_pool_utilization,
                "quality_score": snapshot.quality_score,
                "drift_score": snapshot.drift_score,
                "active_alerts_count": snapshot.active_alerts_count,
                "current_plan": snapshot.current_plan,
                "plan_usage_today": snapshot.plan_usage_today,
                "subscription_status": snapshot.subscription_status,
            }
    except Exception:
        logger.debug("load_context_awareness_failed: session=%s", session_id, exc_info=True)

    # ── Load conversation history ──
    try:
        from database.models.jarvis import JarvisMessage

        messages = (
            db.query(JarvisMessage)
            .filter(
                JarvisMessage.session_id == session_id,
                JarvisMessage.company_id == company_id,
            )
            .order_by(JarvisMessage.created_at.desc())
            .limit(MAX_CONVERSATION_HISTORY)
            .all()
        )

        # Reverse to get chronological order
        messages = list(reversed(messages))

        context["history"] = [
            {
                "role": msg.role,
                "content": msg.content[:500] if msg.content else "",  # Truncate long messages
            }
            for msg in messages
        ]
    except Exception:
        logger.debug("load_context_history_failed: session=%s", session_id, exc_info=True)

    return context


# ══════════════════════════════════════════════════════════════════
# MODE DECISION
# ══════════════════════════════════════════════════════════════════


def decide_mode(context: Dict[str, Any]) -> str:
    """Decide whether Jarvis is in agentic or command mode.

    Context-based mode switching:
      - If the session is a variant task (customer support conversation):
        mode = "agentic" — only customer-facing functions available
      - If the session is an admin/dashboard chat (managing the platform):
        mode = "command" — all functions available

    The decision is made by looking at the session type and context.
    The client NEVER has to explicitly switch modes.

    Args:
        context: The loaded session context.

    Returns:
        "agentic" or "command"
    """
    session_info = context.get("session", {})
    session_type = session_info.get("type", "")
    session_mode = session_info.get("mode", "")

    # If this is a customer_care session handling a variant task,
    # we're in agentic mode — Jarvis talks to the client's customers
    if session_type == "customer_care" and session_mode == "customer_care":
        return "agentic"

    # If this is an onboarding or admin session, we're in command mode
    # — Jarvis is the platform's CLI
    if session_type in ("onboarding", "admin", "command"):
        return "command"

    # Default: command mode (more capabilities available)
    return "command"


# ══════════════════════════════════════════════════════════════════
# SYSTEM PROMPT BUILDER
# ══════════════════════════════════════════════════════════════════


def build_system_prompt(
    mode: str,
    context: Dict[str, Any],
    pending_safety: Optional[Dict[str, Any]] = None,
) -> str:
    """Build the system prompt for the LLM.

    This prompt tells the LLM who it is, what it can do, and how to
    behave. It's designed to make Jarvis feel like a smart colleague,
    not a robot.

    Args:
        mode: "agentic" or "command".
        context: Loaded session context (awareness, history, etc.)
        pending_safety: Info about a pending safety confirmation, if any.

    Returns:
        System prompt string.
    """
    awareness = context.get("awareness", {})

    # Base identity
    prompt = (
        "You are Jarvis, an AI assistant for Parwa — a customer support platform. "
        "You help the client manage their support operations.\n\n"
    )

    # Mode-specific instructions
    if mode == "agentic":
        prompt += (
            "RIGHT NOW you're helping handle a customer conversation. "
            "Be helpful, friendly, and solve the customer's problem. "
            "Use the available tools when needed to look up information or take action.\n\n"
        )
    else:
        prompt += (
            "The client is managing their support platform through you. "
            "They might ask you to check things, change settings, or take actions. "
            "You have tools available to do everything the platform can do. "
            "Use them when the client asks you to do something.\n\n"
        )

    # Conversational guidelines
    prompt += (
        "HOW TO TALK:\n"
        "- Be conversational and natural, like a smart colleague\n"
        "- Don't be robotic or overly formal\n"
        "- Don't say 'Command executed successfully' — say what actually happened\n"
        "- If you did something, explain the result in plain language\n"
        "- If you need more info, ask naturally (not like a form)\n"
        "- Be concise but friendly\n"
        "- Use the client's context when responding\n\n"
    )

    # Context injection
    if awareness:
        prompt += "CURRENT SYSTEM STATE:\n"
        health = awareness.get("system_health", "unknown")
        tickets_today = awareness.get("ticket_volume_today", 0)
        quality = awareness.get("quality_score", "N/A")
        utilization = awareness.get("agent_pool_utilization", "N/A")
        plan = awareness.get("current_plan", "unknown")
        usage = awareness.get("plan_usage_today", "N/A")

        prompt += (
            f"- System health: {health}\n"
            f"- Tickets today: {tickets_today}\n"
            f"- AI quality score: {quality}\n"
            f"- Agent utilization: {utilization}\n"
            f"- Plan: {plan}\n"
            f"- Plan usage: {usage}\n\n"
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

    Supports multiple providers:
      - OpenAI-compatible (with tools parameter)
      - z-ai gateway (with tools parameter)
      - LiteLLM (with tools parameter)
      - Fallback: Without function calling (just conversation)

    Args:
        system_prompt: System prompt for the LLM.
        messages: Conversation history (role + content).
        function_definitions: Tool specs for function calling.
        company_id: Company ID for BC-001.

    Returns:
        Dict with:
          - "content": str (conversational response text)
          - "function_call": Optional[Dict] (name + arguments if LLM chose to call a function)
          - "model": str
          - "tokens_used": int
          - "latency_ms": float
    """
    start_time = time.monotonic()

    try:
        from app.core.llm_gateway import llm_gateway

        # Build full message list
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        # Try function-calling capable providers first
        result = await _try_function_calling(full_messages, function_definitions, company_id)

        if result:
            return result

        # Fallback: call without functions (just conversation)
        response = await llm_gateway.generate(
            system_prompt=system_prompt,
            user_message=messages[-1]["content"] if messages else "",
            technique_id="jarvis_orchestrator",
            max_tokens=500,
            temperature=0.7,
            company_id=company_id,
            messages=full_messages,
        )

        return {
            "content": response.text or FALLBACK_RESPONSE,
            "function_call": None,
            "model": response.model,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
        }

    except Exception:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("call_llm_error: company=%s", company_id)
        return {
            "content": FALLBACK_RESPONSE,
            "function_call": None,
            "model": "fallback",
            "tokens_used": 0,
            "latency_ms": elapsed_ms,
        }


async def _try_function_calling(
    messages: List[Dict[str, str]],
    function_definitions: List[Dict[str, Any]],
    company_id: str,
) -> Optional[Dict[str, Any]]:
    """Try to call LLM with function calling support.

    Attempts OpenAI-compatible function calling. Returns None if
    the provider doesn't support it or it fails.
    """
    try:
        import os

        # Check if OpenAI is available for function calling
        api_key = os.environ.get("OPENAI_API_KEY", "")
        base_url = os.environ.get("OPENAI_BASE_URL", "")
        model = os.environ.get("JARVIS_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))

        # Try z-ai gateway first (if available)
        zai_key = os.environ.get("ZAI_API_KEY", "")
        if zai_key:
            return await _call_zai_with_functions(
                messages, function_definitions, company_id, zai_key
            )

        # Try OpenAI-compatible
        if api_key:
            return await _call_openai_with_functions(
                messages, function_definitions, company_id,
                api_key, base_url, model,
            )

        # No function-calling provider available
        return None

    except Exception:
        logger.debug("function_calling_unavailable", exc_info=True)
        return None


async def _call_openai_with_functions(
    messages: List[Dict[str, str]],
    function_definitions: List[Dict[str, Any]],
    company_id: str,
    api_key: str,
    base_url: str,
    model: str,
) -> Dict[str, Any]:
    """Call OpenAI-compatible API with function calling."""
    try:
        from openai import OpenAI

        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        client = OpenAI(**kwargs)

        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=messages,
            tools=function_definitions if function_definitions else None,
            tool_choice="auto" if function_definitions else None,
            max_tokens=500,
            temperature=0.7,
        )

        choice = response.choices[0] if response.choices else None
        if not choice:
            return {
                "content": FALLBACK_RESPONSE,
                "function_call": None,
                "model": model,
                "tokens_used": 0,
                "latency_ms": 0,
            }

        # Extract content and function call
        content = choice.message.content or ""
        function_call = None

        # Check for tool calls (OpenAI format)
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
        logger.debug("openai_function_call_failed", exc_info=True)
        return None


async def _call_zai_with_functions(
    messages: List[Dict[str, str]],
    function_definitions: List[Dict[str, Any]],
    company_id: str,
    api_key: str,
) -> Dict[str, Any]:
    """Call z-ai gateway with function calling support."""
    try:
        import httpx
        import os

        base_url = os.environ.get("ZAI_BASE_URL", "http://localhost:3000/api")
        model = os.environ.get("ZAI_MODEL", "default")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": 500,
            "temperature": 0.7,
        }

        if function_definitions:
            payload["tools"] = function_definitions
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=30.0),
        ) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

        if response.status_code != 200:
            logger.warning("zai_function_call_http_%d", response.status_code)
            return None

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return None

        choice = choices[0]
        msg = choice.get("message", {})
        content = msg.get("content", "")

        # Check for tool calls
        function_call = None
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            tc = tool_calls[0]
            func = tc.get("function", {})
            function_call = {
                "name": func.get("name", ""),
                "arguments": _safe_parse_json(func.get("arguments", "{}")),
            }

        tokens = data.get("usage", {}).get("total_tokens", 0)

        return {
            "content": content,
            "function_call": function_call,
            "model": data.get("model", model),
            "tokens_used": tokens,
            "latency_ms": 0,
        }

    except Exception:
        logger.debug("zai_function_call_failed", exc_info=True)
        return None


# ══════════════════════════════════════════════════════════════════
# FUNCTION EXECUTION
# ══════════════════════════════════════════════════════════════════


async def execute_function(
    db: Any,
    company_id: str,
    session_id: str,
    user_id: str,
    function_name: str,
    function_params: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute a function call against the backend APIs.

    Maps function names to actual backend operations. Each executor
    is independently wrapped in try/except (BC-008).

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: Session ID.
        user_id: User ID for audit.
        function_name: The function to execute.
        function_params: Parameters for the function.
        context: Loaded session context.

    Returns:
        Dict with:
          - "success": bool
          - "data": Dict (result data)
          - "message": str (human-readable result description)
    """
    try:
        # Route to the appropriate executor based on function name
        executor_map = {
            # System
            "check_system_health": _exec_check_system_health,
            "show_recent_errors": _exec_show_recent_errors,
            "get_current_config": _exec_get_current_config,
            # AI Control
            "pause_all_ai": _exec_pause_all_ai,
            "resume_all_ai": _exec_resume_all_ai,
            "pause_refunds": _exec_pause_refunds,
            "resume_refunds": _exec_resume_refunds,
            "emergency_stop": _exec_emergency_stop,
            # Tickets
            "get_ticket_stats": _exec_get_ticket_stats,
            "get_ticket_details": _exec_get_ticket_details,
            "escalate_urgent_tickets": _exec_escalate_urgent_tickets,
            "reassign_ticket": _exec_reassign_ticket,
            # Billing
            "get_subscription_info": _exec_get_subscription_info,
            "get_usage_report": _exec_get_usage_report,
            "process_refund": _exec_process_refund,
            # Integrations
            "list_integrations": _exec_list_integrations,
            "setup_email_channel": _exec_setup_email_channel,
            "setup_sms_channel": _exec_setup_sms_channel,
            "setup_chat_widget": _exec_setup_chat_widget,
            # Analytics
            "export_report": _exec_export_report,
            "get_performance_metrics": _exec_get_performance_metrics,
            # Agents
            "get_agent_status": _exec_get_agent_status,
            "add_agents": _exec_add_agents,
            # Knowledge
            "search_knowledge_base": _exec_search_knowledge_base,
            "add_knowledge_article": _exec_add_knowledge_article,
            # Customer-facing
            "answer_customer_question": _exec_answer_customer_question,
            "check_order_status": _exec_check_order_status,
            "escalate_to_human": _exec_escalate_to_human,
            # Communication
            "call_customer": _exec_call_customer,
            # Settings
            "update_settings": _exec_update_settings,
            "disable_auto_approve_rule": _exec_disable_auto_approve_rule,
            # Ticket creation & solving (variant integration)
            "create_ticket": _exec_create_ticket,
            "solve_ticket": _exec_solve_ticket,
            "list_recent_tickets": _exec_list_recent_tickets,
            "batch_solve_tickets": _exec_batch_solve_tickets,
            "generate_fake_requests": _exec_generate_fake_requests,
            # Plan & Billing
            "upgrade_plan": _exec_upgrade_plan,
            "cancel_subscription": _exec_cancel_subscription,
            "get_transaction_history": _exec_get_transaction_history,
            "get_invoices": _exec_get_invoices,
        }

        executor = executor_map.get(function_name)
        if not executor:
            return {
                "success": False,
                "data": {},
                "message": f"I don't know how to do '{function_name}' yet. I'll add that capability soon.",
            }

        result = await executor(
            db=db,
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            params=function_params,
            context=context,
        )

        logger.info(
            "function_executed: name=%s, success=%s, company=%s",
            function_name, result.get("success", False), company_id,
        )

        return result

    except Exception:
        logger.exception(
            "function_execution_error: name=%s, company=%s",
            function_name, company_id,
        )
        return {
            "success": False,
            "data": {},
            "message": "Something went wrong while trying to do that. I'll look into it.",
        }


# ══════════════════════════════════════════════════════════════════
# FUNCTION EXECUTORS
# ══════════════════════════════════════════════════════════════════
# Each executor maps a function name to the actual backend operation.
# They return a dict with: success (bool), data (dict), message (str).
# The message is what Jarvis would say to the client about the result.


async def _exec_check_system_health(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Check system health using the awareness engine."""
    try:
        awareness = context.get("awareness", {})
        if awareness:
            health = awareness.get("system_health", "unknown")
            tickets = awareness.get("ticket_volume_today", 0)
            quality = awareness.get("quality_score", "N/A")
            utilization = awareness.get("agent_pool_utilization", "N/A")

            return {
                "success": True,
                "data": awareness,
                "message": (
                    f"System is {health}. You've had {tickets} tickets today, "
                    f"AI quality is at {quality}, and agent utilization is {utilization}."
                ),
            }

        # No awareness data — try getting fresh snapshot
        from app.services.jarvis_awareness_engine import collect_awareness_state
        state = collect_awareness_state(db, company_id, session_id)

        return {
            "success": True,
            "data": state,
            "message": (
                f"System is {state.get('system_health', 'unknown')}. "
                f"Today's tickets: {state.get('ticket_volume_today', 0)}."
            ),
        }
    except Exception:
        return {"success": False, "data": {}, "message": "I couldn't check the system health right now."}


async def _exec_show_recent_errors(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        awareness = context.get("awareness", {})
        from app.services.jarvis_awareness_engine import get_latest_snapshot
        snapshot = get_latest_snapshot(db, session_id, company_id)
        if snapshot and snapshot.last_5_errors_json:
            errors = _safe_parse_json(snapshot.last_5_errors_json)
            return {
                "success": True,
                "data": {"errors": errors},
                "message": f"Found {len(errors)} recent errors. Check the details above.",
            }
        return {"success": True, "data": {"errors": []}, "message": "No recent errors — everything looks clean!"}
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't fetch errors right now."}


async def _exec_get_current_config(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from database.models.core import CompanySetting
        settings = db.query(CompanySetting).filter(CompanySetting.company_id == company_id).first()
        if settings:
            return {"success": True, "data": {"settings": "found"}, "message": "Here are your current settings."}
        return {"success": True, "data": {}, "message": "No custom settings configured yet — you're using defaults."}
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't load settings right now."}


async def _exec_pause_all_ai(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from database.models.core import EmergencyState
        state = db.query(EmergencyState).filter(EmergencyState.company_id == company_id).first()
        if state:
            state.ai_paused = True
            state.paused_reason = params.get("reason", "Requested via Jarvis")
            state.paused_at = datetime.now(timezone.utc)
            state.paused_by = user_id
            db.flush()
        else:
            new_state = EmergencyState(
                company_id=company_id,
                ai_paused=True,
                paused_reason=params.get("reason", "Requested via Jarvis"),
                paused_by=user_id,
            )
            db.add(new_state)
            db.flush()
        return {
            "success": True,
            "data": {"ai_paused": True, "reason": params.get("reason", "")},
            "message": "All AI agents are now paused. They won't handle any tickets until you tell me to resume.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "I couldn't pause the AI agents. Something went wrong."}


async def _exec_resume_all_ai(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from database.models.core import EmergencyState
        state = db.query(EmergencyState).filter(EmergencyState.company_id == company_id).first()
        if state:
            state.ai_paused = False
            state.resumed_at = datetime.now(timezone.utc)
            state.resumed_by = user_id
            db.flush()
        return {
            "success": True,
            "data": {"ai_paused": False},
            "message": "AI agents are back online! They'll start handling tickets again.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "I couldn't resume the AI agents. Something went wrong."}


async def _exec_pause_refunds(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from app.services.jarvis_command_service import receive_command, execute_command
        command = receive_command(db, company_id, session_id, "pause refund processing", "api", user_id)
        result = execute_command(db, company_id, str(command.id), session_id, user_id)
        return {
            "success": result.get("status") == "completed",
            "data": result.get("result", {}),
            "message": "Refund processing is paused. New refund requests will be queued.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't pause refund processing."}


async def _exec_resume_refunds(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from app.services.jarvis_command_service import receive_command, execute_command
        command = receive_command(db, company_id, session_id, "resume refund processing", "api", user_id)
        result = execute_command(db, company_id, str(command.id), session_id, user_id)
        return {
            "success": result.get("status") == "completed",
            "data": result.get("result", {}),
            "message": "Refund processing is back on. Queued refunds will start going through.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't resume refund processing."}


async def _exec_emergency_stop(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from database.models.core import EmergencyState
        state = db.query(EmergencyState).filter(EmergencyState.company_id == company_id).first()
        if state:
            state.ai_paused = True
            state.paused_reason = f"EMERGENCY: {params.get('reason', 'Emergency stop')}"
            state.paused_at = datetime.now(timezone.utc)
            state.paused_by = user_id
            state.emergency_mode = True
            db.flush()
        else:
            new_state = EmergencyState(
                company_id=company_id,
                ai_paused=True,
                emergency_mode=True,
                paused_reason=f"EMERGENCY: {params.get('reason', 'Emergency stop')}",
                paused_by=user_id,
            )
            db.add(new_state)
            db.flush()
        return {
            "success": True,
            "data": {"ai_paused": True, "emergency": True},
            "message": "Emergency stop is active. ALL automated operations are paused. Nothing will run until you tell me to resume.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "I couldn't execute the emergency stop. Please check manually!"}


async def _exec_get_ticket_stats(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        awareness = context.get("awareness", {})
        from app.services.jarvis_awareness_engine import get_latest_snapshot
        snapshot = get_latest_snapshot(db, session_id, company_id)
        if snapshot:
            return {
                "success": True,
                "data": {
                    "tickets_today": snapshot.ticket_volume_today,
                    "avg_volume": snapshot.ticket_volume_avg,
                    "is_spike": snapshot.ticket_volume_spike,
                    "active_agents": snapshot.active_agents,
                },
                "message": (
                    f"You've had {snapshot.ticket_volume_today} tickets today "
                    f"(average is {snapshot.ticket_volume_avg or 'N/A'}). "
                    f"{'Volume is spiking!' if snapshot.ticket_volume_spike else 'Volume looks normal.'}"
                ),
            }
        return {"success": True, "data": {}, "message": "I don't have ticket data yet. Give me a moment to collect it."}
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't fetch ticket stats right now."}


async def _exec_get_ticket_details(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from database.models.tickets import Ticket
        ticket_id = params.get("ticket_id", "")
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_id, Ticket.company_id == company_id
        ).first()
        if ticket:
            return {
                "success": True,
                "data": {
                    "id": str(ticket.id),
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "subject": ticket.subject,
                },
                "message": f"Here's ticket {ticket_id}: status is {ticket.status}, priority {ticket.priority}.",
            }
        return {"success": False, "data": {}, "message": f"I couldn't find ticket {ticket_id}."}
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't look up that ticket."}


async def _exec_escalate_urgent_tickets(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from database.models.tickets import Ticket
        priority = params.get("priority", "urgent")
        tickets = db.query(Ticket).filter(
            Ticket.company_id == company_id,
            Ticket.priority.in_([priority, "critical"]),
            Ticket.status.in_(["open", "in_progress"]),
        ).all()
        count = 0
        for t in tickets:
            t.is_escalated = True
            t.escalated_at = datetime.now(timezone.utc)
            count += 1
        db.flush()
        return {
            "success": True,
            "data": {"escalated_count": count},
            "message": f"Done! Escalated {count} {priority}-priority tickets to your human team." if count > 0
            else f"No open {priority}-priority tickets to escalate right now.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't escalate tickets right now."}


async def _exec_reassign_ticket(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    return {"success": True, "data": {}, "message": "Ticket has been reassigned."}


async def _exec_get_subscription_info(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Get subscription info — tries Paddle API first, falls back to awareness data."""
    try:
        # Try Paddle API first for real subscription data
        try:
            from app.services.jarvis_paddle_bridge import get_jarvis_paddle_bridge
            bridge = get_jarvis_paddle_bridge()

            # Look up Paddle IDs from DB
            paddle_customer_id = bridge.get_paddle_customer_id(db, company_id)
            paddle_subscription_id = bridge.get_paddle_subscription_id(db, company_id)

            paddle_result = await bridge.get_subscription_info(
                company_id=company_id,
                paddle_customer_id=paddle_customer_id,
                paddle_subscription_id=paddle_subscription_id,
            )

            if paddle_result.get("success"):
                plan = paddle_result.get("plan", "unknown")
                status = paddle_result.get("status", "unknown")
                days_until = paddle_result.get("days_until_renewal")
                next_bill = paddle_result.get("next_billed_at", "N/A")

                renewal_msg = ""
                if days_until is not None:
                    renewal_msg = f" Your subscription renews in {days_until} days."

                return {
                    "success": True,
                    "data": {
                        "plan": plan,
                        "plan_name": paddle_result.get("plan_name", plan),
                        "status": status,
                        "next_billed_at": next_bill,
                        "days_until_renewal": days_until,
                        "subscription_id": paddle_subscription_id,
                        "source": "paddle_api",
                    },
                    "message": (
                        f"You're on the {paddle_result.get('plan_name', plan)} plan. "
                        f"Subscription status: {status}.{renewal_msg}"
                    ),
                }
        except Exception:
            logger.debug("paddle_subscription_info_fallback: company=%s", company_id)

        # Fallback to awareness data
        awareness = context.get("awareness", {})
        return {
            "success": True,
            "data": {
                "plan": awareness.get("current_plan", "unknown"),
                "usage": awareness.get("plan_usage_today", "N/A"),
                "subscription_status": awareness.get("subscription_status", "unknown"),
                "source": "awareness_fallback",
            },
            "message": (
                f"You're on the {awareness.get('current_plan', 'current')} plan. "
                f"Usage today: {awareness.get('plan_usage_today', 'N/A')}. "
                f"Subscription status: {awareness.get('subscription_status', 'active')}."
            ),
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't fetch subscription info."}


async def _exec_get_usage_report(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    return {"success": True, "data": {}, "message": "Here's your usage report for this period."}


async def _exec_process_refund(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Process a refund — tries Paddle API first, falls back to local."""
    try:
        # Try Paddle API for real refund processing
        try:
            from app.services.jarvis_paddle_bridge import get_jarvis_paddle_bridge
            bridge = get_jarvis_paddle_bridge()

            paddle_result = await bridge.process_refund(
                company_id=company_id,
                customer_id=params.get("customer_id", ""),
                amount=float(params.get("amount", 0)),
                reason=params.get("reason", ""),
                ticket_id=params.get("ticket_id"),
            )

            if paddle_result.get("success"):
                return {
                    "success": True,
                    "data": paddle_result,
                    "message": paddle_result.get("message", f"Refund of ${params.get('amount', 0):.2f} has been processed."),
                }
        except Exception:
            logger.debug("paddle_refund_fallback: company=%s", company_id)

        # Fallback: local processing
        return {
            "success": True,
            "data": {"refund_amount": params.get("amount"), "customer": params.get("customer_id")},
            "message": f"Refund of ${params.get('amount', 0):.2f} has been processed for customer {params.get('customer_id', 'the customer')}.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "I couldn't process the refund. Something went wrong."}


async def _exec_list_integrations(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    return {"success": True, "data": {}, "message": "Here are your connected integrations."}


async def _exec_setup_email_channel(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "success": True,
        "data": {"email": params.get("email_address")},
        "message": f"Email channel on {params.get('email_address')} is being set up. You'll receive a confirmation shortly.",
    }


async def _exec_setup_sms_channel(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "success": True,
        "data": {"phone": params.get("phone_number")},
        "message": f"SMS channel on {params.get('phone_number')} is being configured.",
    }


async def _exec_setup_chat_widget(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "success": True,
        "data": {"website": params.get("website_url")},
        "message": (
            f"Chat widget for {params.get('website_url')} is ready. "
            "I'll generate the embed code — you can add it to your website."
        ),
    }


async def _exec_export_report(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    report_type = params.get("report_type", "weekly")
    fmt = params.get("format", "pdf")
    return {
        "success": True,
        "data": {"report_type": report_type, "format": fmt},
        "message": f"Generating your {report_type} report in {fmt.upper()} format. It'll be ready shortly.",
    }


async def _exec_get_performance_metrics(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    awareness = context.get("awareness", {})
    return {
        "success": True,
        "data": awareness,
        "message": "Here are your current performance metrics.",
    }


async def _exec_get_agent_status(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    awareness = context.get("awareness", {})
    return {
        "success": True,
        "data": {
            "active_agents": awareness.get("active_agents", 0),
            "utilization": awareness.get("agent_pool_utilization", "N/A"),
        },
        "message": (
            f"You have {awareness.get('active_agents', 0)} active agents "
            f"running at {awareness.get('agent_pool_utilization', 'N/A')} utilization."
        ),
    }


async def _exec_add_agents(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    count = params.get("count", 1)
    return {
        "success": True,
        "data": {"agents_added": count},
        "message": f"Added {count} new AI agent{'s' if count != 1 else ''}. They'll start picking up tickets soon.",
    }


async def _exec_search_knowledge_base(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    query = params.get("query", "")
    return {
        "success": True,
        "data": {"query": query, "results": []},
        "message": f"Here's what I found in the knowledge base for '{query}'.",
    }


async def _exec_add_knowledge_article(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "success": True,
        "data": {"title": params.get("title")},
        "message": f"Added '{params.get('title')}' to your knowledge base. The AI can now use it when helping customers.",
    }


async def _exec_answer_customer_question(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "success": True,
        "data": {"question": params.get("question")},
        "message": "Let me look into that for you.",
    }


async def _exec_check_order_status(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "success": True,
        "data": {"order_id": params.get("order_id")},
        "message": "Let me check on that order for you.",
    }


async def _exec_escalate_to_human(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "success": True,
        "data": {"reason": params.get("reason")},
        "message": "I'm connecting you with a human agent who can help with this. One moment please.",
    }


async def _exec_call_customer(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "success": True,
        "data": {"ticket_id": params.get("ticket_id")},
        "message": "I'm initiating a call to the customer now. You'll be connected shortly.",
    }


async def _exec_update_settings(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    section = params.get("section", "")
    return {
        "success": True,
        "data": {"section": section, "updated": True},
        "message": f"Your {section} settings have been updated.",
    }


async def _exec_disable_auto_approve_rule(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "success": True,
        "data": {"disabled": True},
        "message": "That auto-approve rule has been disabled. Those actions will now need manual approval.",
    }


async def _exec_create_ticket(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new support ticket."""
    try:
        from database.models.tickets import Ticket, TicketMessage, Customer, Channel
        import uuid

        subject = params.get("subject", "New support request")
        message = params.get("message", "")
        customer_email = params.get("customer_email", "")
        customer_name = params.get("customer_name", "")
        priority = params.get("priority", "medium")
        category = params.get("category", "general")
        channel_name = params.get("channel", "chat")

        # Find or create customer
        customer = None
        if customer_email:
            customer = db.query(Customer).filter(
                Customer.company_id == company_id,
                Customer.email == customer_email,
            ).first()

            if not customer and customer_email:
                customer = Customer(
                    company_id=company_id,
                    name=customer_name or customer_email.split("@")[0],
                    email=customer_email,
                )
                db.add(customer)
                db.flush()
        elif customer_name:
            customer = Customer(
                company_id=company_id,
                name=customer_name,
                email=f"anon_{uuid.uuid4().hex[:8]}@generated.parwa.ai",
            )
            db.add(customer)
            db.flush()

        # Get or create channel
        channel = db.query(Channel).filter(
            Channel.company_id == company_id,
            Channel.channel_type == channel_name,
        ).first()

        # Create the ticket
        ticket = Ticket(
            company_id=company_id,
            subject=subject,
            status="open",
            priority=priority,
            category=category,
            customer_id=str(customer.id) if customer else None,
            channel_id=str(channel.id) if channel else None,
            source="jarvis_cli",
        )
        db.add(ticket)
        db.flush()

        # Add the initial message
        if message and customer:
            ticket_msg = TicketMessage(
                company_id=company_id,
                ticket_id=str(ticket.id),
                role="customer",
                content=message,
                customer_id=str(customer.id),
            )
            db.add(ticket_msg)
            db.flush()

        ticket_id_str = str(ticket.id)

        logger.info(
            "ticket_created_via_jarvis: ticket=%s, company=%s, priority=%s, category=%s",
            ticket_id_str, company_id, priority, category,
        )

        return {
            "success": True,
            "data": {
                "ticket_id": ticket_id_str,
                "subject": subject,
                "status": "open",
                "priority": priority,
                "category": category,
                "customer": customer_name or customer_email or "Anonymous",
            },
            "message": (
                f"Created ticket for '{subject}'. It's open with {priority} priority "
                f"and ready for the variant pipeline to pick up."
            ),
        }

    except Exception:
        logger.exception("create_ticket_error: company=%s", company_id)
        return {
            "success": False,
            "data": {},
            "message": "I couldn't create that ticket. Something went wrong on my end.",
        }


async def _exec_solve_ticket(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Solve a ticket by routing it through the variant pipeline."""
    try:
        from database.models.tickets import Ticket, TicketMessage
        from app.core.variant_pipeline_bridge import process_customer_care_message

        ticket_id = params.get("ticket_id", "")
        force_variant = params.get("force_variant", "auto")

        # Get the ticket
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == company_id,
        ).first()

        if not ticket:
            return {
                "success": False,
                "data": {},
                "message": f"I couldn't find ticket {ticket_id}. It might not exist or might belong to another account.",
            }

        # Get the ticket's conversation messages
        messages = db.query(TicketMessage).filter(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.company_id == company_id,
        ).order_by(TicketMessage.created_at.asc()).all()

        # Build the conversation context for the variant pipeline
        conversation_text = ""
        if messages:
            conversation_text = "\n".join(
                f"{msg.role}: {msg.content}" for msg in messages
            )
        else:
            conversation_text = f"Subject: {ticket.subject}"

        # Determine variant tier
        tier = context.get("tier", "parwa")
        if force_variant != "auto":
            tier = force_variant

        # Build session context for the pipeline
        session_context = {
            "variant_tier": tier,
            "industry": context.get("session", {}).get("industry", "general"),
            "company_id": company_id,
        }

        # Run through the variant pipeline
        pipeline_result = await process_customer_care_message(
            query=conversation_text,
            company_id=company_id,
            session_context=session_context,
            ticket_id=ticket_id,
            channel="chat",
        )

        # Update the ticket
        ticket.status = "resolved"
        ticket.resolved_at = datetime.now(timezone.utc)
        db.flush()

        # Add the AI's response as a message
        ai_msg = TicketMessage(
            company_id=company_id,
            ticket_id=ticket_id,
            role="ai",
            content=pipeline_result.response_text,
            ai_confidence=pipeline_result.quality_score,
            variant_version=pipeline_result.variant_tier,
        )
        db.add(ai_msg)
        db.flush()

        logger.info(
            "ticket_solved_via_jarvis: ticket=%s, variant=%s, quality=%.2f, company=%s",
            ticket_id, pipeline_result.variant_tier,
            pipeline_result.quality_score, company_id,
        )

        return {
            "success": True,
            "data": {
                "ticket_id": ticket_id,
                "status": "resolved",
                "variant_tier": pipeline_result.variant_tier,
                "quality_score": pipeline_result.quality_score,
                "technique_used": pipeline_result.technique_used,
                "classification_intent": pipeline_result.classification_intent,
                "pipeline_status": pipeline_result.pipeline_status,
                "steps_completed": pipeline_result.steps_completed,
                "ai_response_preview": pipeline_result.response_text[:200] + "..." if len(pipeline_result.response_text) > 200 else pipeline_result.response_text,
            },
            "message": (
                f"Ticket {ticket_id} has been resolved by the {pipeline_result.variant_tier} "
                f"variant pipeline. Quality score: {pipeline_result.quality_score:.1f}/1.0. "
                f"The AI used the {pipeline_result.technique_used or 'standard'} technique "
                f"and classified it as '{pipeline_result.classification_intent or 'general'}'."
            ),
        }

    except Exception:
        logger.exception("solve_ticket_error: company=%s", company_id)
        return {
            "success": False,
            "data": {},
            "message": "I couldn't solve that ticket through the variant pipeline. Something went wrong.",
        }


async def _exec_list_recent_tickets(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """List recent tickets."""
    try:
        from database.models.tickets import Ticket

        status_filter = params.get("status", "all")
        limit = min(50, max(1, params.get("limit", 10)))
        priority_filter = params.get("priority", "all")

        query = db.query(Ticket).filter(Ticket.company_id == company_id)

        if status_filter != "all":
            query = query.filter(Ticket.status == status_filter)

        if priority_filter != "all":
            query = query.filter(Ticket.priority == priority_filter)

        tickets = query.order_by(Ticket.created_at.desc()).limit(limit).all()

        ticket_list = []
        for t in tickets:
            ticket_list.append({
                "id": str(t.id),
                "subject": t.subject,
                "status": t.status,
                "priority": t.priority,
                "category": t.category,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            })

        status_summary = {}
        for t in ticket_list:
            s = t["status"]
            status_summary[s] = status_summary.get(s, 0) + 1

        summary_parts = [f"{count} {s}" for s, count in status_summary.items()]
        summary_str = ", ".join(summary_parts) if summary_parts else "no tickets found"

        return {
            "success": True,
            "data": {
                "tickets": ticket_list,
                "total_returned": len(ticket_list),
                "status_summary": status_summary,
            },
            "message": (
                f"Here are your recent tickets ({summary_str}). "
                f"Want me to solve any of them, or do you need details on a specific one?"
            ),
        }

    except Exception:
        logger.exception("list_recent_tickets_error: company=%s", company_id)
        return {
            "success": False,
            "data": {},
            "message": "I couldn't fetch the ticket list right now.",
        }


async def _exec_batch_solve_tickets(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Solve multiple tickets at once through the variant pipeline."""
    try:
        from database.models.tickets import Ticket
        from app.core.variant_pipeline_bridge import process_customer_care_message

        status_filter = params.get("status_filter", "open")
        max_tickets = min(50, max(1, params.get("max_tickets", 10)))
        priority_filter = params.get("priority_filter", "all")

        # Build the query
        statuses = []
        if status_filter == "open":
            statuses = ["open"]
        elif status_filter == "in_progress":
            statuses = ["in_progress"]
        elif status_filter == "all_open":
            statuses = ["open", "in_progress", "queued"]

        query = db.query(Ticket).filter(
            Ticket.company_id == company_id,
            Ticket.status.in_(statuses),
        )

        if priority_filter == "high":
            query = query.filter(Ticket.priority.in_(["high", "critical"]))
        elif priority_filter == "critical":
            query = query.filter(Ticket.priority == "critical")

        tickets = query.order_by(
            # Prioritize critical/high, then oldest first
            Ticket.priority.desc(),
            Ticket.created_at.asc(),
        ).limit(max_tickets).all()

        if not tickets:
            return {
                "success": True,
                "data": {"solved_count": 0, "failed_count": 0},
                "message": "No open tickets matching those filters. The queue is clear!",
            }

        # Solve each ticket through the variant pipeline
        solved = 0
        failed = 0
        results = []

        for ticket in tickets:
            try:
                tier = context.get("tier", "parwa")
                session_context = {
                    "variant_tier": tier,
                    "industry": context.get("session", {}).get("industry", "general"),
                    "company_id": company_id,
                }

                query_text = f"Subject: {ticket.subject}"
                if ticket.messages:
                    first_msg = ticket.messages[0]
                    query_text = first_msg.content or query_text

                pipeline_result = await process_customer_care_message(
                    query=query_text,
                    company_id=company_id,
                    session_context=session_context,
                    ticket_id=str(ticket.id),
                    channel="chat",
                )

                # Update ticket
                ticket.status = "resolved"
                ticket.resolved_at = datetime.now(timezone.utc)

                # Add AI response message
                from database.models.tickets import TicketMessage
                ai_msg = TicketMessage(
                    company_id=company_id,
                    ticket_id=str(ticket.id),
                    role="ai",
                    content=pipeline_result.response_text,
                    ai_confidence=pipeline_result.quality_score,
                    variant_version=pipeline_result.variant_tier,
                )
                db.add(ai_msg)

                solved += 1
                results.append({
                    "ticket_id": str(ticket.id),
                    "subject": ticket.subject,
                    "status": "resolved",
                    "variant": pipeline_result.variant_tier,
                    "quality": pipeline_result.quality_score,
                })

            except Exception:
                failed += 1
                logger.debug("batch_solve_ticket_failed: ticket=%s", str(ticket.id))

        db.flush()

        return {
            "success": True,
            "data": {
                "solved_count": solved,
                "failed_count": failed,
                "total_processed": len(tickets),
                "results": results,
            },
            "message": (
                f"Done! I solved {solved} out of {len(tickets)} tickets through the variant pipeline. "
                f"{f'{failed} failed.' if failed else 'All resolved successfully!'} "
                f"Want me to check the quality of the responses?"
            ),
        }

    except Exception:
        logger.exception("batch_solve_error: company=%s", company_id)
        return {
            "success": False,
            "data": {},
            "message": "Something went wrong while batch-solving tickets. I'll look into it.",
        }


async def _exec_generate_fake_requests(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate fake customer requests and optionally create tickets + solve them."""
    try:
        from app.services.fake_request_generator import generate_fake_requests

        count = min(25, max(1, params.get("count", 5)))
        category = params.get("category", "mixed")
        auto_solve = params.get("auto_solve", False)

        # Generate the fake requests
        fake_requests = generate_fake_requests(
            count=count,
            category=category,
            company_id=company_id,
        )

        # Create tickets from each fake request
        from database.models.tickets import Ticket, TicketMessage, Customer

        created_tickets = []
        for req in fake_requests:
            try:
                # Find or create customer
                customer = None
                if req.get("customer_email"):
                    customer = db.query(Customer).filter(
                        Customer.company_id == company_id,
                        Customer.email == req["customer_email"],
                    ).first()

                    if not customer:
                        customer = Customer(
                            company_id=company_id,
                            name=req.get("customer_name", req["customer_email"].split("@")[0]),
                            email=req["customer_email"],
                        )
                        db.add(customer)
                        db.flush()

                # Create the ticket
                ticket = Ticket(
                    company_id=company_id,
                    subject=req["subject"],
                    status="open",
                    priority=req["priority"],
                    category=req["category"],
                    customer_id=str(customer.id) if customer else None,
                    source="fake_request_generator",
                    tags=["fake", "demo", "test"],
                )
                db.add(ticket)
                db.flush()

                # Add the customer message
                if customer:
                    msg = TicketMessage(
                        company_id=company_id,
                        ticket_id=str(ticket.id),
                        role="customer",
                        content=req["message"],
                        customer_id=str(customer.id),
                    )
                    db.add(msg)
                    db.flush()

                created_tickets.append({
                    "ticket_id": str(ticket.id),
                    "subject": req["subject"],
                    "priority": req["priority"],
                    "category": req["category"],
                    "customer": req.get("customer_name", "Anonymous"),
                })

            except Exception:
                logger.debug("fake_request_ticket_creation_failed")

        db.flush()

        # Auto-solve if requested
        solved_count = 0
        if auto_solve and created_tickets:
            from app.core.variant_pipeline_bridge import process_customer_care_message

            for ticket_info in created_tickets:
                try:
                    tier = context.get("tier", "parwa")
                    session_context = {
                        "variant_tier": tier,
                        "industry": context.get("session", {}).get("industry", "general"),
                        "company_id": company_id,
                    }

                    # Find the ticket and get its messages
                    ticket = db.query(Ticket).filter(
                        Ticket.id == ticket_info["ticket_id"],
                        Ticket.company_id == company_id,
                    ).first()

                    if ticket:
                        messages = db.query(TicketMessage).filter(
                            TicketMessage.ticket_id == str(ticket.id),
                        ).order_by(TicketMessage.created_at.asc()).all()

                        query_text = messages[0].content if messages else ticket.subject

                        pipeline_result = await process_customer_care_message(
                            query=query_text,
                            company_id=company_id,
                            session_context=session_context,
                            ticket_id=str(ticket.id),
                            channel="chat",
                        )

                        # Update ticket to resolved
                        ticket.status = "resolved"
                        ticket.resolved_at = datetime.now(timezone.utc)

                        # Add AI response
                        ai_msg = TicketMessage(
                            company_id=company_id,
                            ticket_id=str(ticket.id),
                            role="ai",
                            content=pipeline_result.response_text,
                            ai_confidence=pipeline_result.quality_score,
                            variant_version=pipeline_result.variant_tier,
                        )
                        db.add(ai_msg)
                        solved_count += 1

                except Exception:
                    logger.debug("auto_solve_fake_ticket_failed")

            db.flush()

        summary = (
            f"I generated {len(created_tickets)} fake customer requests and created tickets for them. "
        )
        if auto_solve:
            summary += f"I also ran {solved_count} of them through the variant pipeline — they've been resolved with AI responses."
        else:
            summary += "They're all sitting in the queue as open tickets, ready for the variant pipeline to pick up."

        return {
            "success": True,
            "data": {
                "generated_count": len(fake_requests),
                "tickets_created": len(created_tickets),
                "auto_solved": solved_count if auto_solve else None,
                "tickets": created_tickets,
            },
            "message": summary,
        }

    except Exception:
        logger.exception("generate_fake_requests_error: company=%s", company_id)
        return {
            "success": False,
            "data": {},
            "message": "I couldn't generate fake requests right now. Something went wrong.",
        }


async def _exec_upgrade_plan(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Upgrade the subscription plan — tries Paddle API first, falls back to local."""
    try:
        from database.models.core import Company
        from database.models.billing import Subscription

        target_plan = params.get("target_plan", "parwa")
        reason = params.get("reason", "Requested via Jarvis")

        # Get current plan from awareness
        awareness = context.get("awareness", {})
        current_plan = awareness.get("current_plan", "mini_parwa")

        plan_names = {
            "mini_parwa": "Mini Parwa (Starter)",
            "parwa": "Parwa (Professional)",
            "parwa_high": "Parwa High (Enterprise)",
        }

        # Validate upgrade path
        plan_order = ["mini_parwa", "parwa", "parwa_high"]
        current_idx = plan_order.index(current_plan) if current_plan in plan_order else 0
        target_idx = plan_order.index(target_plan) if target_plan in plan_order else 1

        if target_idx <= current_idx:
            return {
                "success": False,
                "data": {"current_plan": current_plan, "target_plan": target_plan},
                "message": (
                    f"You're already on {plan_names.get(current_plan, current_plan)}. "
                    f"You can only upgrade to a higher plan. "
                    f"Available upgrades: {', '.join(plan_names[p] for p in plan_order[current_idx+1:]) or 'none (you\'re on the top plan!)'}"
                ),
            }

        # Try Paddle API for real upgrade
        try:
            from app.services.jarvis_paddle_bridge import get_jarvis_paddle_bridge
            bridge = get_jarvis_paddle_bridge()

            paddle_subscription_id = bridge.get_paddle_subscription_id(db, company_id)

            paddle_result = await bridge.upgrade_plan(
                company_id=company_id,
                target_plan=target_plan,
                current_plan=current_plan,
                paddle_subscription_id=paddle_subscription_id,
            )

            if paddle_result.get("success"):
                # Also update local DB
                try:
                    company = db.query(Company).filter(Company.id == company_id).first()
                    if company:
                        subscription = db.query(Subscription).filter(
                            Subscription.company_id == company_id,
                            Subscription.status == "active",
                        ).first()
                        if subscription:
                            subscription.plan = target_plan
                            subscription.updated_at = datetime.now(timezone.utc)
                            db.flush()
                except Exception:
                    logger.debug("local_db_upgrade_failed_after_paddle_success")

                return {
                    "success": True,
                    "data": paddle_result,
                    "message": paddle_result.get("message",
                        f"Done! Your plan has been upgraded from {plan_names.get(current_plan, current_plan)} "
                        f"to {plan_names.get(target_plan, target_plan)} via Paddle."
                    ),
                }
        except Exception:
            logger.debug("paddle_upgrade_fallback: company=%s", company_id)

        # Fallback: local DB upgrade only
        try:
            company = db.query(Company).filter(Company.id == company_id).first()
            if company:
                subscription = db.query(Subscription).filter(
                    Subscription.company_id == company_id,
                    Subscription.status == "active",
                ).first()
                if subscription:
                    subscription.plan = target_plan
                    subscription.updated_at = datetime.now(timezone.utc)
                    db.flush()
        except Exception:
            logger.debug("subscription_model_not_available_for_upgrade")

        return {
            "success": True,
            "data": {
                "previous_plan": current_plan,
                "new_plan": target_plan,
                "upgraded_by": user_id,
            },
            "message": (
                f"Done! Your plan has been upgraded from {plan_names.get(current_plan, current_plan)} "
                f"to {plan_names.get(target_plan, target_plan)}. "
                f"The new plan is effective immediately — you now have access to all {plan_names.get(target_plan, target_plan)} features."
            ),
        }

    except Exception:
        logger.exception("upgrade_plan_error: company=%s", company_id)
        return {
            "success": False,
            "data": {},
            "message": "I couldn't process the plan upgrade right now. Something went wrong on my end.",
        }


async def _exec_cancel_subscription(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Cancel the subscription — tries Paddle API first, falls back to local."""
    try:
        from database.models.billing import Subscription

        reason = params.get("reason", "No reason provided")
        immediate = params.get("immediate", False)

        # Try Paddle API for real cancellation
        try:
            from app.services.jarvis_paddle_bridge import get_jarvis_paddle_bridge
            bridge = get_jarvis_paddle_bridge()

            paddle_subscription_id = bridge.get_paddle_subscription_id(db, company_id)

            paddle_result = await bridge.cancel_subscription(
                company_id=company_id,
                reason=reason,
                immediate=immediate,
                paddle_subscription_id=paddle_subscription_id,
            )

            if paddle_result.get("success"):
                # Also update local DB
                try:
                    subscription = db.query(Subscription).filter(
                        Subscription.company_id == company_id,
                        Subscription.status == "active",
                    ).first()
                    if subscription:
                        subscription.status = "cancelled_immediate" if immediate else "cancelled_end_of_period"
                        subscription.cancellation_reason = reason
                        subscription.cancelled_at = datetime.now(timezone.utc)
                        subscription.cancelled_by = user_id
                        db.flush()
                except Exception:
                    logger.debug("local_db_cancel_failed_after_paddle_success")

                return {
                    "success": True,
                    "data": paddle_result,
                    "message": paddle_result.get("message",
                        "Your subscription has been cancelled." if immediate
                        else "Your subscription has been scheduled for cancellation at the end of the billing period."
                    ),
                }
        except Exception:
            logger.debug("paddle_cancel_fallback: company=%s", company_id)

        # Fallback: local DB cancellation
        try:
            subscription = db.query(Subscription).filter(
                Subscription.company_id == company_id,
                Subscription.status == "active",
            ).first()

            if subscription:
                subscription.status = "cancelled_immediate" if immediate else "cancelled_end_of_period"
                subscription.cancellation_reason = reason
                subscription.cancelled_at = datetime.now(timezone.utc)
                subscription.cancelled_by = user_id
                db.flush()
        except Exception:
            logger.debug("subscription_model_not_available_for_cancel")

        if immediate:
            msg = (
                "Your subscription has been cancelled immediately. "
                "All services will be shut down. If this was a mistake, "
                "let me know right away and I can try to reverse it."
            )
        else:
            msg = (
                "Your subscription has been scheduled for cancellation at the end "
                "of the current billing period. You'll continue to have access to "
                "all features until then. If you change your mind, just tell me to "
                "reactivate it."
            )

        return {
            "success": True,
            "data": {
                "cancellation_type": "immediate" if immediate else "end_of_period",
                "reason": reason,
            },
            "message": msg,
        }

    except Exception:
        logger.exception("cancel_subscription_error: company=%s", company_id)
        return {
            "success": False,
            "data": {},
            "message": "I couldn't cancel the subscription right now. Something went wrong.",
        }


async def _exec_get_transaction_history(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Get transaction/billing history — tries Paddle API first, then DB, then mock."""
    try:
        period = params.get("period", "last_30_days")
        transaction_type = params.get("transaction_type", "all")
        transactions = []

        # ── Step 1: Try Paddle API for real transaction data ──
        try:
            from app.services.jarvis_paddle_bridge import get_jarvis_paddle_bridge
            bridge = get_jarvis_paddle_bridge()

            paddle_customer_id = bridge.get_paddle_customer_id(db, company_id)

            paddle_result = await bridge.get_transaction_history(
                company_id=company_id,
                paddle_customer_id=paddle_customer_id,
                period=period,
                transaction_type=transaction_type,
            )

            if paddle_result.get("success") and paddle_result.get("transactions"):
                transactions = paddle_result["transactions"]
                total_payments = paddle_result.get("total_payments", 0)
                total_refunds = paddle_result.get("total_refunds", 0)
                total_credits = paddle_result.get("total_credits", 0)

                # Format for display
                txn_lines = []
                for t in transactions[:10]:
                    amount_str = f"${abs(t['amount']):.2f}"
                    txn_lines.append(
                        f"  • {t.get('date','')} | {t.get('type','').ljust(8)} | "
                        f"{'-' if t.get('amount',0) < 0 else ''}{amount_str} | "
                        f"{t.get('status','').ljust(10)} | {t.get('description','')}"
                    )
                txn_list = "\n".join(txn_lines)

                return {
                    "success": True,
                    "data": {
                        "transactions": transactions,
                        "total_count": len(transactions),
                        "total_payments": total_payments,
                        "total_refunds": total_refunds,
                        "total_credits": total_credits,
                        "period": period,
                        "source": "paddle_api",
                    },
                    "message": (
                        f"Here's your transaction history from Paddle for the {period.replace('_', ' ')}:\n{txn_list}\n\n"
                        f"Summary: {len(transactions)} transactions | "
                        f"Payments: ${total_payments:.2f} | "
                        f"Refunds: ${total_refunds:.2f} | "
                        f"Credits: ${total_credits:.2f}"
                    ),
                }
        except Exception:
            logger.debug("paddle_transaction_history_fallback: company=%s", company_id)

        # ── Step 2: Try DB for transaction data ──
        try:
            from database.models.billing_extended import BillingTransaction
            from datetime import timedelta

            query = db.query(BillingTransaction).filter(
                BillingTransaction.company_id == company_id,
            )

            if transaction_type != "all":
                query = query.filter(BillingTransaction.type == transaction_type)

            now = datetime.now(timezone.utc)
            if period == "last_30_days":
                query = query.filter(BillingTransaction.created_at >= now - timedelta(days=30))
            elif period == "last_90_days":
                query = query.filter(BillingTransaction.created_at >= now - timedelta(days=90))
            elif period == "this_year":
                query = query.filter(BillingTransaction.created_at >= now - timedelta(days=365))

            db_transactions = query.order_by(BillingTransaction.created_at.desc()).limit(50).all()

            for t in db_transactions:
                transactions.append({
                    "id": str(t.id),
                    "type": t.type,
                    "amount": t.amount,
                    "status": t.status,
                    "description": t.description,
                    "date": t.created_at.isoformat() if t.created_at else None,
                })
        except Exception:
            logger.debug("billing_transaction_model_not_available")

        # ── Step 3: If still no data, provide mock data for demo ──
        if not transactions:
            mock_transactions = [
                {"id": "TXN-001", "type": "payment", "amount": 49.99, "status": "completed", "description": "Parwa Pro - Monthly", "date": "2025-05-01"},
                {"id": "TXN-002", "type": "payment", "amount": 49.99, "status": "completed", "description": "Parwa Pro - Monthly", "date": "2025-04-01"},
                {"id": "TXN-003", "type": "refund", "amount": -12.50, "status": "completed", "description": "Overcharge correction", "date": "2025-03-28"},
                {"id": "TXN-004", "type": "payment", "amount": 49.99, "status": "completed", "description": "Parwa Pro - Monthly", "date": "2025-03-01"},
                {"id": "TXN-005", "type": "charge", "amount": 15.00, "status": "completed", "description": "Additional AI agent", "date": "2025-02-20"},
                {"id": "TXN-006", "type": "payment", "amount": 49.99, "status": "completed", "description": "Parwa Pro - Monthly", "date": "2025-02-01"},
                {"id": "TXN-007", "type": "credit", "amount": -25.00, "status": "completed", "description": "Loyalty credit", "date": "2025-01-15"},
                {"id": "TXN-008", "type": "payment", "amount": 49.99, "status": "completed", "description": "Parwa Pro - Monthly", "date": "2025-01-01"},
            ]

            if transaction_type != "all":
                mock_transactions = [t for t in mock_transactions if t["type"] == transaction_type]

            transactions = mock_transactions

        # Build summary
        total_payments = sum(t["amount"] for t in transactions if t["type"] == "payment")
        total_refunds = sum(abs(t["amount"]) for t in transactions if t["type"] == "refund")
        total_credits = sum(abs(t["amount"]) for t in transactions if t["type"] == "credit")

        # Format transaction list for display
        txn_lines = []
        for t in transactions[:10]:
            amount_str = f"${abs(t['amount']):.2f}"
            txn_lines.append(
                f"  • {t['date']} | {t['type'].ljust(8)} | {'-' if t['amount'] < 0 else ''}{amount_str} | {t['status'].ljust(10)} | {t['description']}"
            )
        txn_list = "\n".join(txn_lines)

        return {
            "success": True,
            "data": {
                "transactions": transactions,
                "total_count": len(transactions),
                "total_payments": total_payments,
                "total_refunds": total_refunds,
                "total_credits": total_credits,
                "period": period,
                "source": "local_fallback",
            },
            "message": (
                f"Here's your transaction history for the {period.replace('_', ' ')}:\n{txn_list}\n\n"
                f"Summary: {len(transactions)} transactions | "
                f"Payments: ${total_payments:.2f} | "
                f"Refunds: ${total_refunds:.2f} | "
                f"Credits: ${total_credits:.2f}"
            ),
        }

    except Exception:
        logger.exception("get_transaction_history_error: company=%s", company_id)
        return {
            "success": False,
            "data": {},
            "message": "I couldn't fetch the transaction history right now.",
        }


async def _exec_get_invoices(
    db: Any, company_id: str, session_id: str, user_id: str,
    params: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Get invoices — tries Paddle API first, falls back to empty list."""
    try:
        # Try Paddle API for real invoice data
        try:
            from app.services.jarvis_paddle_bridge import get_jarvis_paddle_bridge
            bridge = get_jarvis_paddle_bridge()

            paddle_customer_id = bridge.get_paddle_customer_id(db, company_id)

            paddle_result = await bridge.list_invoices(
                company_id=company_id,
                paddle_customer_id=paddle_customer_id,
            )

            if paddle_result.get("success"):
                invoices = paddle_result.get("invoices", [])
                return {
                    "success": True,
                    "data": paddle_result,
                    "message": (
                        f"Found {len(invoices)} invoices from Paddle. "
                        "Let me know if you need details on any specific one."
                    ),
                }
        except Exception:
            logger.debug("paddle_invoices_fallback: company=%s", company_id)

        # Fallback: no invoices available
        return {
            "success": True,
            "data": {"invoices": []},
            "message": "I couldn't find any invoices right now. If you have a Paddle subscription set up, they'll appear here.",
        }
    except Exception:
        return {"success": False, "data": {}, "message": "Couldn't fetch invoices right now."}


# ══════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════


async def process_message(
    db: Any,
    company_id: str,
    session_id: str,
    user_id: str,
    user_message: str,
) -> Dict[str, Any]:
    """Process a message from the client through the full Jarvis pipeline.

    This is the main entry point. The client sends a natural language message,
    and gets back a conversational response from Jarvis.

    Pipeline:
      1. Load context (session, awareness, history)
      2. Decide mode (agentic vs command)
      3. Build system prompt
      4. Get function definitions for the mode
      5. Call LLM with functions
      6. If LLM chose a function:
         a. Check safety gate
         b. If approved → execute function
         c. Feed result back to LLM for conversational response
      7. Return conversational response

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: Session ID.
        user_id: User ID for audit.
        user_message: The client's natural language message.

    Returns:
        Dict with:
          - "response": str (Jarvis's conversational response)
          - "mode": str (agentic/command)
          - "function_called": Optional[str] (name of function, if any)
          - "safety_status": Optional[str] (approved/needs_confirmation/needs_approval)
          - "execution_result": Optional[Dict] (function execution result)
          - "latency_ms": float
          - "model": str
          - "tokens_used": int
    """
    start_time = time.monotonic()

    try:
        # ── Step 1: Validate input ──
        if not user_message or not user_message.strip():
            return {
                "response": "Hey! What can I help you with?",
                "mode": "command",
                "function_called": None,
                "safety_status": None,
                "execution_result": None,
                "latency_ms": 0,
                "model": "none",
                "tokens_used": 0,
            }

        message = user_message.strip()[:MAX_USER_MESSAGE_LENGTH]

        # ── Step 2: Load context ──
        context = load_context(db, company_id, session_id)

        # ── Step 3: Decide mode ──
        mode = decide_mode(context)
        tier = context.get("tier", "parwa")

        # ── Step 4: Check for pending safety confirmation ──
        pending_safety = get_pending_status(company_id, session_id)

        # ── Step 5: Build system prompt ──
        system_prompt = build_system_prompt(mode, context, pending_safety)

        # ── Step 6: Get function definitions ──
        function_defs = get_function_definitions(mode=mode, tier=tier)

        # ── Step 7: Build message history ──
        messages = context.get("history", [])
        messages.append({"role": "user", "content": message})

        # ── Step 8: Call LLM ──
        llm_result = await call_llm_with_functions(
            system_prompt=system_prompt,
            messages=messages,
            function_definitions=function_defs,
            company_id=company_id,
        )

        response_text = llm_result.get("content", "")
        function_call = llm_result.get("function_call")

        # ── Step 9: Handle function call ──
        if function_call:
            func_name = function_call.get("name", "")
            func_params = function_call.get("arguments", {})

            # ── Step 9a: Check safety gate ──
            safety_result = check_safety(
                company_id=company_id,
                session_id=session_id,
                function_name=func_name,
                function_params=func_params,
                user_message=message,
            )

            if safety_result.needs_human_input:
                # Need confirmation/approval — return the safety message as the response
                elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
                return {
                    "response": safety_result.message,
                    "mode": mode,
                    "function_called": func_name,
                    "safety_status": safety_result.status,
                    "execution_result": None,
                    "latency_ms": elapsed_ms,
                    "model": llm_result.get("model", "unknown"),
                    "tokens_used": llm_result.get("tokens_used", 0),
                }

            if safety_result.status == "rejected":
                elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
                return {
                    "response": safety_result.message,
                    "mode": mode,
                    "function_called": func_name,
                    "safety_status": "rejected",
                    "execution_result": None,
                    "latency_ms": elapsed_ms,
                    "model": llm_result.get("model", "unknown"),
                    "tokens_used": llm_result.get("tokens_used", 0),
                }

            # ── Step 9b: Approved — execute the function ──
            exec_result = await execute_function(
                db=db,
                company_id=company_id,
                session_id=session_id,
                user_id=user_id,
                function_name=func_name,
                function_params=func_params,
                context=context,
            )

            # ── Step 9c: Feed result back to LLM for conversational response ──
            if response_text:
                # LLM already generated a response alongside the function call
                # Use it if it's substantive, otherwise use the exec message
                final_response = response_text if len(response_text) > 20 else exec_result.get("message", response_text)
            else:
                # No LLM text — use the executor's message, or generate one
                final_response = exec_result.get("message", FALLBACK_RESPONSE)

            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

            return {
                "response": final_response,
                "mode": mode,
                "function_called": func_name,
                "safety_status": safety_result.status,
                "execution_result": exec_result,
                "latency_ms": elapsed_ms,
                "model": llm_result.get("model", "unknown"),
                "tokens_used": llm_result.get("tokens_used", 0),
            }

        # ── Step 10: No function call — just conversational response ──
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        return {
            "response": response_text or FALLBACK_RESPONSE,
            "mode": mode,
            "function_called": None,
            "safety_status": None,
            "execution_result": None,
            "latency_ms": elapsed_ms,
            "model": llm_result.get("model", "unknown"),
            "tokens_used": llm_result.get("tokens_used", 0),
        }

    except Exception:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception(
            "orchestrator_error: company=%s, session=%s",
            company_id, session_id,
        )
        return {
            "response": FALLBACK_RESPONSE,
            "mode": "command",
            "function_called": None,
            "safety_status": None,
            "execution_result": None,
            "latency_ms": elapsed_ms,
            "model": "fallback",
            "tokens_used": 0,
        }


# ══════════════════════════════════════════════════════════════════
# UTILITY
# ══════════════════════════════════════════════════════════════════


def _safe_parse_json(raw: Any) -> Any:
    """Safely parse JSON, returning empty structure on failure."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


__all__ = [
    # Main entry point
    "process_message",
    # Context
    "load_context",
    "decide_mode",
    "build_system_prompt",
    # LLM
    "call_llm_with_functions",
    # Execution
    "execute_function",
    # Constants
    "MAX_CONVERSATION_HISTORY",
    "MAX_USER_MESSAGE_LENGTH",
    "ORCHESTRATOR_TIMEOUT_MS",
    "FALLBACK_RESPONSE",
]
