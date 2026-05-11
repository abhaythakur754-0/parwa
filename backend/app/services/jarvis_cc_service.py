"""
PARWA Jarvis Customer Care Service

Dedicated service for Jarvis in Customer Care mode (post-onboarding).

This is the interaction layer between the client and the PARWA product
after onboarding is complete. Jarvis here is NOT a chatbot — it is an
AI employee that replaces a human support agent.

Architecture:
  Client → Jarvis CC Service → variant_pipeline_bridge → Variant Pipelines
                                ↕
                          Same APIs the UI uses
                          (ticket_service, channel_service, etc.)

Two Modes:
  1. REACTIVE:  Client sends message → Jarvis processes → responds
  2. PROACTIVE: Jarvis detects issues → alerts client proactively
                (Phase 2 — awareness engine)

Current Scope (Phase 1.1):
  - send_cc_message:     Process customer care messages via variant pipeline
  - get_cc_session:      Get or create a customer care session
  - get_cc_history:      Get conversation history
  - build_cc_system_prompt: Build context-rich system prompt for CC mode
  - get_cc_context:      Get current awareness snapshot (placeholder for Phase 2)
  - update_cc_context:   Update session context with new data

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.exceptions import (
    NotFoundError,
    ValidationError,
    RateLimitError,
    InternalError,
)
from database.models.jarvis import (
    JarvisSession,
    JarvisMessage,
    JarvisKnowledgeUsed,
)
from app.logger import get_logger

logger = get_logger("jarvis_cc_service")


# ── Constants ──────────────────────────────────────────────────────

CC_DAILY_MESSAGE_LIMIT = 5000  # Customer care has much higher limits
CC_MAX_CONTEXT_MESSAGES = 30   # Last N messages for AI context
CC_MAX_CONTEXT_JSON_SIZE = 50000  # Max chars for context_json

__all__ = [
    # Session
    "get_or_create_cc_session",
    "get_cc_session",
    "get_cc_context",
    "update_cc_context",
    # Messages
    "send_cc_message",
    "get_cc_history",
    # Prompt
    "build_cc_system_prompt",
    # Health
    "get_cc_session_health",
]


# ══════════════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ══════════════════════════════════════════════════════════════════


def get_or_create_cc_session(
    db: Session,
    user_id: str,
    company_id: str,
    existing_session_id: Optional[str] = None,
) -> JarvisSession:
    """Get an existing customer_care session or create a new one.

    After handoff, the client needs a persistent customer_care session.
    This function finds or creates one.

    Args:
        db: SQLAlchemy session.
        user_id: The user's ID (BC-001 scoped).
        company_id: The company's ID (BC-001).
        existing_session_id: If provided, try to resume this specific session.

    Returns:
        Active JarvisSession with type='customer_care'.

    Raises:
        NotFoundError: If existing_session_id provided but not found/not CC type.
        ValidationError: If company_id is missing.
    """
    if not company_id:
        raise ValidationError(
            message="company_id is required for customer care sessions",
            details={"user_id": user_id},
        )

    # If a specific session ID is provided, try to resume it
    if existing_session_id:
        session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.id == existing_session_id,
                JarvisSession.user_id == user_id,
                JarvisSession.company_id == company_id,
                JarvisSession.type == "customer_care",
                JarvisSession.is_active.is_(True),
            )
            .first()
        )
        if session:
            _maybe_reset_daily_counter(db, session)
            session.updated_at = datetime.now(timezone.utc)
            db.flush()
            return session
        # Not found or wrong type — fall through to create new

    # Look for any active customer_care session for this user+company
    active_session = (
        db.query(JarvisSession)
        .filter(
            JarvisSession.user_id == user_id,
            JarvisSession.company_id == company_id,
            JarvisSession.type == "customer_care",
            JarvisSession.is_active.is_(True),
        )
        .order_by(JarvisSession.created_at.desc())
        .first()
    )

    if active_session:
        _maybe_reset_daily_counter(db, active_session)
        active_session.updated_at = datetime.now(timezone.utc)
        db.flush()
        return active_session

    # Create a new customer care session
    # Inherit variant_tier from the most recent handoff session if available
    variant_tier = "mini_parwa"  # safe default
    variant_instance_id = ""
    industry = "general"

    # Try to find context from the handoff (onboarding session)
    handoff_session = (
        db.query(JarvisSession)
        .filter(
            JarvisSession.user_id == user_id,
            JarvisSession.company_id == company_id,
            JarvisSession.type == "onboarding",
            JarvisSession.handoff_completed.is_(True),
        )
        .order_by(JarvisSession.created_at.desc())
        .first()
    )

    care_context: Dict[str, Any] = {
        "variant_tier": variant_tier,
        "variant_instance_id": variant_instance_id,
        "industry": industry,
        "mode": "customer_care",
        "created_via": "jarvis_cc_service",
        "awareness_enabled": False,  # Phase 2 will enable this
        "proactive_alerts": [],
        "last_pipeline_metadata": {},
    }

    if handoff_session:
        try:
            handoff_ctx = _safe_parse_json(handoff_session.context_json)
            if handoff_ctx.get("variant_tier"):
                care_context["variant_tier"] = handoff_ctx["variant_tier"]
                variant_tier = handoff_ctx["variant_tier"]
            if handoff_ctx.get("variant_instance_id"):
                care_context["variant_instance_id"] = handoff_ctx["variant_instance_id"]
                variant_instance_id = handoff_ctx["variant_instance_id"]
            if handoff_ctx.get("industry"):
                care_context["industry"] = handoff_ctx["industry"]
                industry = handoff_ctx["industry"]
            if handoff_ctx.get("business_email"):
                care_context["business_email"] = handoff_ctx["business_email"]
            if handoff_ctx.get("email_verified"):
                care_context["email_verified"] = handoff_ctx["email_verified"]
            care_context["onboarding_session_id"] = str(handoff_session.id)
            care_context["onboarding_completed_at"] = (
                handoff_session.updated_at.isoformat()
                if handoff_session.updated_at
                else datetime.now(timezone.utc).isoformat()
            )
        except Exception:
            logger.exception(
                "Failed to parse handoff context for user=%s company=%s",
                user_id, company_id,
            )

    new_session = JarvisSession(
        user_id=user_id,
        company_id=company_id,
        type="customer_care",
        context_json=json.dumps(care_context),
        message_count_today=0,
        total_message_count=0,
        pack_type="free",  # CC sessions don't use pack limits
        is_active=True,
    )
    db.add(new_session)
    db.flush()

    # Generate a welcome message for the new CC session
    welcome_msg = JarvisMessage(
        session_id=str(new_session.id),
        role="jarvis",
        content=_build_cc_welcome(variant_tier, industry),
        message_type="text",
        metadata_json=json.dumps({
            "variant_tier": variant_tier,
            "industry": industry,
            "session_type": "customer_care",
        }),
    )
    db.add(welcome_msg)
    db.flush()

    logger.info(
        "cc_session_created: session_id=%s, user_id=%s, company_id=%s, "
        "variant_tier=%s, industry=%s",
        new_session.id, user_id, company_id, variant_tier, industry,
    )

    return new_session


def get_cc_session(
    db: Session,
    session_id: str,
    user_id: str,
    company_id: str,
) -> JarvisSession:
    """Get a customer_care session by ID with security scoping.

    Args:
        db: SQLAlchemy session.
        session_id: The session ID to retrieve.
        user_id: User ID for security scoping.
        company_id: Company ID for BC-001 tenant isolation.

    Returns:
        JarvisSession with type='customer_care'.

    Raises:
        NotFoundError: If session not found or not customer_care type.
    """
    session = (
        db.query(JarvisSession)
        .filter(
            JarvisSession.id == session_id,
            JarvisSession.user_id == user_id,
            JarvisSession.company_id == company_id,
        )
        .first()
    )
    if not session:
        raise NotFoundError(
            message="Customer care session not found",
            details={"session_id": session_id},
        )
    if session.type != "customer_care":
        raise NotFoundError(
            message="Session is not a customer care session",
            details={"session_id": session_id, "type": session.type},
        )
    return session


def get_cc_context(
    db: Session,
    session_id: str,
    user_id: str,
    company_id: str,
) -> Dict[str, Any]:
    """Get the current context snapshot for a customer care session.

    Returns the parsed context_json with additional runtime data
    (variant instance status, recent ticket counts, etc.).

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        user_id: User ID for security scoping.
        company_id: Company ID for BC-001.

    Returns:
        Dict with full context including runtime enrichment.
    """
    session = get_cc_session(db, session_id, user_id, company_id)
    ctx = _safe_parse_json(session.context_json)

    # Enrich with runtime data (BC-008: each enrichment is independently wrapped)
    ctx["runtime"] = {}

    # Current variant instance status
    try:
        from app.services.variant_instance_service import get_instance
        instance_id = ctx.get("variant_instance_id")
        if instance_id:
            instance = get_instance(db, company_id, instance_id)
            if instance:
                ctx["runtime"]["instance_status"] = instance.status
                ctx["runtime"]["active_tickets"] = instance.active_tickets_count
                ctx["runtime"]["total_handled"] = instance.total_tickets_handled
    except Exception:
        pass  # BC-008: enrichment failure is non-fatal

    # Recent ticket count
    try:
        from database.models.tickets import Ticket
        from sqlalchemy import func
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        ticket_count = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.company_id == company_id,
                Ticket.created_at >= today_start,
            )
            .scalar()
        )
        ctx["runtime"]["tickets_today"] = ticket_count or 0
    except Exception:
        pass

    # Emergency state
    try:
        from database.models.core import EmergencyState
        emergency = (
            db.query(EmergencyState)
            .filter(EmergencyState.company_id == company_id)
            .order_by(EmergencyState.created_at.desc())
            .first()
        )
        if emergency:
            ctx["runtime"]["ai_paused"] = emergency.is_paused
            ctx["runtime"]["paused_channels"] = emergency.paused_channels
    except Exception:
        pass

    return ctx


def update_cc_context(
    db: Session,
    session_id: str,
    user_id: str,
    company_id: str,
    partial_updates: Dict[str, Any],
) -> JarvisSession:
    """Merge partial updates into the customer care session context.

    Only provided keys are updated. Existing keys are preserved.
    This is how the awareness engine (Phase 2) and command executor
    (Phase 3) will update the session.

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        user_id: User ID for security.
        company_id: Company ID for BC-001.
        partial_updates: Dict of keys to merge into context.

    Returns:
        Updated JarvisSession.

    Raises:
        NotFoundError: If session not found.
        ValidationError: If context_json would exceed size limit.
    """
    session = get_cc_session(db, session_id, user_id, company_id)
    ctx = _safe_parse_json(session.context_json)

    # Merge updates (don't allow overwriting critical keys from outside)
    protected_keys = {"variant_tier", "variant_instance_id", "industry"}
    for key, value in partial_updates.items():
        if key not in protected_keys or value is not None:
            ctx[key] = value

    new_context = json.dumps(ctx)
    if len(new_context) > CC_MAX_CONTEXT_JSON_SIZE:
        raise ValidationError(
            message="Context size would exceed limit",
            details={"size": len(new_context), "limit": CC_MAX_CONTEXT_JSON_SIZE},
        )

    session.context_json = new_context
    session.updated_at = datetime.now(timezone.utc)
    db.flush()

    return session


# ══════════════════════════════════════════════════════════════════
# MESSAGE PROCESSING
# ══════════════════════════════════════════════════════════════════


def send_cc_message(
    db: Session,
    session_id: str,
    user_id: str,
    company_id: str,
    user_message: str,
    ticket_id: Optional[str] = None,
    channel: str = "chat",
) -> Tuple[JarvisMessage, JarvisMessage, Dict[str, Any]]:
    """Process a customer care message and generate AI response.

    This is the main entry point for Jarvis in customer care mode.

    Flow:
      1. Validate session (must be customer_care type)
      2. Check message limits
      3. Save user message
      4. Build system prompt with tenant context
      5. Route through variant pipeline bridge
      6. Save AI response with pipeline metadata
      7. Update session context
      8. Return both messages + metadata

    Fallback Chain (BC-008):
      variant_pipeline_bridge → legacy ai_pipeline → direct AI provider

    Args:
        db: SQLAlchemy session.
        session_id: The customer care session ID.
        user_id: User ID for security scoping.
        company_id: Company ID for BC-001 tenant isolation.
        user_message: The raw message from the client.
        ticket_id: Optional ticket ID if message is within a ticket context.
        channel: Communication channel (chat, email, sms, voice).

    Returns:
        Tuple of (user_message_obj, ai_message_obj, pipeline_metadata)

    Raises:
        NotFoundError: If session not found or not customer_care type.
        RateLimitError: If daily limit exceeded.
        ValidationError: If message is empty or too long.
    """
    start_time = time.monotonic()

    # ── Step 1: Validate session ──
    session = get_cc_session(db, session_id, user_id, company_id)

    # ── Step 2: Validate message ──
    if not user_message or not user_message.strip():
        raise ValidationError(
            message="Message cannot be empty",
            details={"session_id": session_id},
        )
    if len(user_message) > 10000:
        raise ValidationError(
            message="Message too long (max 10,000 characters)",
            details={"length": len(user_message)},
        )

    # ── Step 3: Check message limits ──
    _maybe_reset_daily_counter(db, session)
    if session.message_count_today >= CC_DAILY_MESSAGE_LIMIT:
        raise RateLimitError(
            message="Daily message limit reached for customer care",
            details={
                "limit": CC_DAILY_MESSAGE_LIMIT,
                "used": session.message_count_today,
            },
        )

    # ── Step 4: Save user message ──
    user_msg = JarvisMessage(
        session_id=session_id,
        role="user",
        content=user_message,
        message_type="text",
        metadata_json=json.dumps({
            "channel": channel,
            "ticket_id": ticket_id or "",
            "company_id": company_id,
        }),
    )
    db.add(user_msg)

    # Update counters
    session.message_count_today += 1
    session.total_message_count += 1
    session.last_message_date = datetime.now(timezone.utc)
    session.updated_at = datetime.now(timezone.utc)
    db.flush()

    # ── Step 5: Get session context ──
    ctx = _safe_parse_json(session.context_json)
    variant_tier = ctx.get("variant_tier", "mini_parwa")
    variant_instance_id = ctx.get("variant_instance_id", "")
    industry = ctx.get("industry", "general")

    # ── Phase 3: Command Detection ──
    # If the message looks like a command, route it through the command layer
    # instead of the AI pipeline. Commands start with "/" or match known patterns.
    _COMMAND_PREFIXES = ("/", "jarvis ")
    _is_command = False
    _stripped_message = user_message.strip()

    if any(_stripped_message.lower().startswith(p) for p in _COMMAND_PREFIXES):
        _is_command = True
        # Strip the prefix for command parsing
        for prefix in _COMMAND_PREFIXES:
            if _stripped_message.lower().startswith(prefix):
                _stripped_message = _stripped_message[len(prefix):].strip()
                break
    else:
        # Quick check: does the message match any command pattern?
        try:
            from app.services.jarvis_command_service import parse_natural_language_command
            _quick_parse = parse_natural_language_command(
                company_id=company_id,
                raw_input=_stripped_message,
                session_id=session_id,
            )
            if (_quick_parse.get("confidence", 0) >= 0.65
                    and _quick_parse.get("action") != "unknown"):
                _is_command = True
        except Exception:
            pass  # BC-008: command detection failure is non-fatal

    if _is_command:
        try:
            from app.services import jarvis_command_service
            from database.models.jarvis_cc import JarvisCommand

            # Receive and parse the command
            command = jarvis_command_service.receive_command(
                db=db,
                company_id=company_id,
                session_id=session_id,
                raw_input=_stripped_message,
                source="chat",
                user_id=user_id,
            )

            # Execute the command
            cmd_result = jarvis_command_service.execute_command(
                db=db,
                company_id=company_id,
                command_id=str(command.id),
                session_id=session_id,
                user_id=user_id,
            )

            # Build AI response as a command_response message
            parsed = json.loads(command.command_parsed) if command.command_parsed else {}
            _action = cmd_result.get("action", "unknown")
            _result_data = cmd_result.get("result", {})
            _message = _result_data.get("message", f"Command '{_action}' executed.")
            _undo_hint = " (Undo available)" if command.undo_available else ""

            ai_msg = JarvisMessage(
                session_id=session_id,
                role="jarvis",
                content=_message + _undo_hint,
                message_type="command_response",
                metadata_json=json.dumps({
                    "command_id": str(command.id),
                    "action": _action,
                    "intent": command.command_intent,
                    "confidence": float(command.confidence) if command.confidence else None,
                    "result": cmd_result.get("result", {}),
                    "execution_time_ms": cmd_result.get("execution_time_ms", 0),
                    "undo_available": command.undo_available,
                    "suggestion": parsed.get("suggestion"),
                    "fallback": "command_layer",
                }),
            )
            db.add(ai_msg)

            # Update session context
            ctx["last_command_at"] = datetime.now(timezone.utc).isoformat()
            ctx["last_command_action"] = _action
            session.context_json = json.dumps(ctx)
            db.flush()

            total_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "cc_command_executed: session=%s, action=%s, ms=%.1f",
                session_id, _action, total_ms,
            )

            return user_msg, ai_msg, {
                "pipeline_status": "command_executed",
                "command_action": _action,
                "execution_time_ms": cmd_result.get("execution_time_ms", 0),
            }
        except Exception as cmd_exc:
            logger.warning(
                "cc_command_fallback_to_pipeline: session=%s, error=%s",
                session_id, str(cmd_exc)[:200],
            )
            # Fall through to normal pipeline if command execution fails

    # ── Step 6: Check emergency state ──
    ai_paused = False
    try:
        from database.models.core import EmergencyState
        emergency = (
            db.query(EmergencyState)
            .filter(EmergencyState.company_id == company_id)
            .order_by(EmergencyState.created_at.desc())
            .first()
        )
        if emergency and emergency.is_paused:
            paused_channels = emergency.paused_channels or ""
            if channel in paused_channels or not paused_channels:
                ai_paused = True
    except Exception:
        pass  # BC-008

    if ai_paused:
        ai_msg = JarvisMessage(
            session_id=session_id,
            role="jarvis",
            content=(
                "AI responses are currently paused for this channel. "
                "Your message has been logged and a team member will respond. "
                "You can resume AI responses from your dashboard settings."
            ),
            message_type="text",
            metadata_json=json.dumps({
                "ai_paused": True,
                "channel": channel,
                "fallback": "emergency_pause",
            }),
        )
        db.add(ai_msg)
        db.flush()
        return user_msg, ai_msg, {"ai_paused": True, "pipeline_status": "paused"}

    # ── Step 7: PII scan ──
    pii_scan_result = None
    try:
        from app.services.pii_scan_service import PIIScanService
        pii_scanner = PIIScanService(db, company_id)
        pii_scan_result = pii_scanner.scan_text(user_message)
        if pii_scan_result:
            ctx["last_pii_scan"] = pii_scan_result
    except Exception:
        pass  # BC-008: PII scan failure is non-fatal

    # ── Step 8: Route through variant pipeline ──
    ai_content = None
    ai_message_type = "variant_pipeline"
    metadata: Dict[str, Any] = {}
    pipeline_status = "not_attempted"

    try:
        from app.core.variant_pipeline_bridge import (
            process_customer_care_message_sync,
        )

        pipeline_result = process_customer_care_message_sync(
            query=user_message,
            company_id=company_id,
            session_context=ctx,
            conversation_id=session_id,
            ticket_id=ticket_id or "",
            channel=channel,
            customer_id=user_id,
            customer_tier=ctx.get("customer_tier", "free"),
        )

        ai_content = pipeline_result.response_text
        metadata = pipeline_result.to_dict()
        pipeline_status = pipeline_result.pipeline_status

        # Store pipeline metadata in context
        ctx["last_pipeline_metadata"] = {
            "variant_tier": pipeline_result.variant_tier,
            "pipeline_status": pipeline_result.pipeline_status,
            "quality_score": pipeline_result.quality_score,
            "total_latency_ms": pipeline_result.total_latency_ms,
            "billing_tokens": pipeline_result.billing_tokens,
            "technique_used": pipeline_result.technique_used,
            "classification_intent": pipeline_result.classification_intent,
            "empathy_score": pipeline_result.empathy_score,
            "emergency_flag": pipeline_result.emergency_flag,
        }

        logger.info(
            "cc_pipeline_complete: session=%s, tier=%s, status=%s, "
            "quality=%.1f, latency=%sms, tokens=%d, intent=%s",
            session_id,
            pipeline_result.variant_tier,
            pipeline_result.pipeline_status,
            pipeline_result.quality_score,
            pipeline_result.total_latency_ms,
            pipeline_result.billing_tokens,
            pipeline_result.classification_intent,
        )

    except Exception as exc:
        # Fallback 1: Legacy AI pipeline
        logger.error(
            "CC variant pipeline failed, trying legacy: %s", exc,
        )
        pipeline_status = "pipeline_failed"

        try:
            from app.core.ai_pipeline import process_ai_message
            import asyncio
            import concurrent.futures

            history = _get_recent_history(db, session_id)

            system_prompt = build_cc_system_prompt(db, session_id, company_id, ctx)

            conversation_history = [
                {"role": msg["role"].replace("jarvis", "assistant"), "content": msg["content"]}
                for msg in history[-CC_MAX_CONTEXT_MESSAGES:]
            ]

            pipeline_args = dict(
                query=user_message,
                company_id=company_id,
                conversation_id=session_id,
                variant_type=variant_tier,
                customer_id=user_id,
                conversation_history=conversation_history,
                language="en",
                system_prompt=system_prompt,
            )

            try:
                legacy_result = asyncio.run(process_ai_message(**pipeline_args))
            except RuntimeError:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(
                        asyncio.run, process_ai_message(**pipeline_args),
                    )
                    legacy_result = future.result(timeout=60)

            ai_content = legacy_result.response
            ai_message_type = "ai_generated"
            metadata = legacy_result.to_dict()
            pipeline_status = "legacy_fallback"

            ctx["last_pipeline_metadata"] = {
                "intent": legacy_result.intent_type,
                "confidence": legacy_result.confidence_score,
                "technique": legacy_result.technique_used,
                "model": legacy_result.model_used,
                "fallback": "legacy_ai_pipeline",
            }

        except Exception as inner_exc:
            # Fallback 2: Direct AI provider
            logger.error(
                "CC legacy pipeline also failed: %s", inner_exc,
            )
            pipeline_status = "all_pipelines_failed"

            try:
                system_prompt = build_cc_system_prompt(db, session_id, company_id, ctx)
                history = _get_recent_history(db, session_id)
                ai_content, _, metadata, _ = _call_ai_provider_fallback(
                    system_prompt, history, user_message, ctx,
                )
                ai_message_type = "direct_ai"
                pipeline_status = "direct_ai_fallback"
            except Exception:
                ai_content = _get_friendly_error_message()
                ai_message_type = "error"
                metadata = {"error_type": "all_pipelines_failed"}
                pipeline_status = "all_failed"

    # ── Step 9: Ensure we have a response ──
    if not ai_content:
        ai_content = _get_friendly_error_message()
        ai_message_type = "error"

    # ── Step 10: Save AI response ──
    ai_msg = JarvisMessage(
        session_id=session_id,
        role="jarvis",
        content=ai_content,
        message_type=ai_message_type,
        metadata_json=json.dumps(metadata),
    )
    db.add(ai_msg)
    db.flush()

    # ── Step 11: Update session context ──
    ctx["last_message_at"] = datetime.now(timezone.utc).isoformat()
    ctx["total_messages"] = session.total_message_count
    ctx["pipeline_status"] = pipeline_status

    session.context_json = json.dumps(ctx)
    db.flush()

    # ── Step 12: Audit log ──
    try:
        from app.services.audit_service import log_audit
        log_audit(
            company_id=company_id,
            actor_id=user_id,
            actor_type="user",
            action="cc_message_sent",
            resource_type="jarvis_cc_session",
            resource_id=session_id,
            old_value=None,
            new_value={
                "pipeline_status": pipeline_status,
                "variant_tier": variant_tier,
                "channel": channel,
            },
            ip_address=None,
            user_agent=None,
            db=db,
        )
    except Exception:
        pass  # BC-008

    total_ms = round((time.monotonic() - start_time) * 1000, 2)
    logger.info(
        "cc_message_complete: session=%s, pipeline=%s, total_ms=%s",
        session_id, pipeline_status, total_ms,
    )

    return user_msg, ai_msg, metadata


def get_cc_history(
    db: Session,
    session_id: str,
    user_id: str,
    company_id: str,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    """Get paginated message history for a customer care session.

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        user_id: User ID for security.
        company_id: Company ID for BC-001.
        limit: Max messages to return.
        offset: Pagination offset.

    Returns:
        Tuple of (messages_list, total_count).
    """
    # Security: verify session belongs to user+company
    get_cc_session(db, session_id, user_id, company_id)

    query = (
        db.query(JarvisMessage)
        .filter(JarvisMessage.session_id == session_id)
        .order_by(JarvisMessage.created_at.asc())
    )

    total = query.count()
    messages = query.offset(offset).limit(limit).all()

    message_list = []
    for msg in messages:
        msg_dict = {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "message_type": msg.message_type,
            "metadata": _safe_parse_json(msg.metadata_json) if msg.metadata_json else {},
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }
        message_list.append(msg_dict)

    return message_list, total


# ══════════════════════════════════════════════════════════════════
# SYSTEM PROMPT BUILDER
# ══════════════════════════════════════════════════════════════════


def build_cc_system_prompt(
    db: Session,
    session_id: str,
    company_id: str,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a rich system prompt for Customer Care Jarvis.

    Unlike onboarding Jarvis (which sells), CC Jarvis is an AI employee
    that handles support tickets and assists the client in managing
    their customer care operations.

    The prompt includes:
    - Tenant-specific context (variant tier, industry, channels)
    - Brand voice and tone guidelines
    - Knowledge base context
    - Current operational status (if available)
    - Conversation context (stage, turn count)

    Args:
        db: SQLAlchemy session.
        session_id: Session ID for context lookup.
        company_id: Company ID for BC-001.
        context: Pre-loaded context (optional, loaded from DB if not provided).

    Returns:
        Complete system prompt string.
    """
    # Load context if not provided
    if context is None:
        session = db.query(JarvisSession).filter(
            JarvisSession.id == session_id,
        ).first()
        context = _safe_parse_json(session.context_json) if session else {}

    variant_tier = context.get("variant_tier", "mini_parwa")
    industry = context.get("industry", "general")
    instance_id = context.get("variant_instance_id", "")

    # Base CC prompt — fundamentally different from onboarding
    prompt_parts = [
        _CC_BASE_PROMPT,
        f"\n## CURRENT CONFIGURATION",
        f"- Variant Tier: {variant_tier}",
        f"- Industry: {industry}",
        f"- Instance ID: {instance_id[:8]}..." if instance_id else "- Instance: default",
    ]

    # Tier-specific capabilities
    tier_caps = _get_tier_capabilities(variant_tier)
    if tier_caps:
        prompt_parts.append(f"\n## YOUR CAPABILITIES ({variant_tier.upper()})")
        prompt_parts.append(tier_caps)

    # Brand voice (from company settings)
    try:
        from database.models.core import CompanySetting
        settings = (
            db.query(CompanySetting)
            .filter(CompanySetting.company_id == company_id)
            .first()
        )
        if settings:
            if settings.brand_voice:
                prompt_parts.append(f"\n## BRAND VOICE")
                prompt_parts.append(settings.brand_voice)
            if settings.tone_guidelines:
                prompt_parts.append(f"\n## TONE GUIDELINES")
                prompt_parts.append(settings.tone_guidelines)
            if settings.prohibited_phrases:
                prohibited = _safe_parse_json(settings.prohibited_phrases)
                if prohibited and isinstance(prohibited, list):
                    prompt_parts.append(f"\n## PROHIBITED PHRASES")
                    prompt_parts.append(
                        "NEVER use these phrases: " + ", ".join(prohibited)
                    )
    except Exception:
        pass  # BC-008

    # Knowledge base context
    try:
        from app.services.jarvis_knowledge_service import search_and_format_knowledge
        kb_context = search_and_format_knowledge("customer care support", industry)
        if kb_context:
            prompt_parts.append(f"\n## KNOWLEDGE BASE")
            prompt_parts.append(kb_context[:2000])  # Limit KB context size
    except Exception:
        pass

    # Recent pipeline results (for continuity)
    last_pipeline = context.get("last_pipeline_metadata", {})
    if last_pipeline:
        prompt_parts.append(f"\n## LAST INTERACTION METADATA")
        if last_pipeline.get("classification_intent"):
            prompt_parts.append(
                f"- Last intent classified: {last_pipeline['classification_intent']}"
            )
        if last_pipeline.get("quality_score"):
            prompt_parts.append(
                f"- Last quality score: {last_pipeline['quality_score']:.1f}/1.0"
            )
        if last_pipeline.get("technique_used"):
            prompt_parts.append(
                f"- Last technique used: {last_pipeline['technique_used']}"
            )

    return "\n".join(prompt_parts)


# ══════════════════════════════════════════════════════════════════
# SESSION HEALTH CHECK
# ══════════════════════════════════════════════════════════════════


def get_cc_session_health(
    db: Session,
    session_id: str,
    user_id: str,
    company_id: str,
) -> Dict[str, Any]:
    """Get health status of a customer care session.

    Returns operational metrics for the session including:
    - Session validity
    - Message counts
    - Pipeline status
    - Variant instance status
    - Emergency state

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        user_id: User ID for security.
        company_id: Company ID for BC-001.

    Returns:
        Dict with health metrics.
    """
    try:
        session = get_cc_session(db, session_id, user_id, company_id)
        ctx = _safe_parse_json(session.context_json)

        health = {
            "session_id": session_id,
            "is_active": session.is_active,
            "session_type": session.type,
            "variant_tier": ctx.get("variant_tier", "unknown"),
            "industry": ctx.get("industry", "unknown"),
            "messages_today": session.message_count_today,
            "total_messages": session.total_message_count,
            "daily_limit": CC_DAILY_MESSAGE_LIMIT,
            "daily_remaining": max(0, CC_DAILY_MESSAGE_LIMIT - session.message_count_today),
            "last_message_at": (
                session.last_message_date.isoformat()
                if session.last_message_date else None
            ),
            "pipeline_status": ctx.get("pipeline_status", "unknown"),
            "last_quality_score": ctx.get("last_pipeline_metadata", {}).get("quality_score"),
            "awareness_enabled": ctx.get("awareness_enabled", False),
        }

        # Variant instance health
        try:
            instance_id = ctx.get("variant_instance_id")
            if instance_id:
                from app.services.variant_instance_service import get_instance
                instance = get_instance(db, company_id, instance_id)
                if instance:
                    health["instance"] = {
                        "status": instance.status,
                        "active_tickets": instance.active_tickets_count,
                        "total_handled": instance.total_tickets_handled,
                        "last_activity": (
                            instance.last_activity_at.isoformat()
                            if instance.last_activity_at else None
                        ),
                    }
        except Exception:
            health["instance"] = {"status": "unknown"}

        # Emergency state
        try:
            from database.models.core import EmergencyState
            emergency = (
                db.query(EmergencyState)
                .filter(EmergencyState.company_id == company_id)
                .order_by(EmergencyState.created_at.desc())
                .first()
            )
            health["ai_paused"] = emergency.is_paused if emergency else False
        except Exception:
            health["ai_paused"] = False

        return health

    except NotFoundError:
        return {
            "session_id": session_id,
            "is_active": False,
            "error": "Session not found",
        }
    except Exception:
        return {
            "session_id": session_id,
            "is_active": False,
            "error": "Health check failed",
        }


# ══════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ══════════════════════════════════════════════════════════════════


_CC_BASE_PROMPT = """## IDENTITY: JARVIS — AI CUSTOMER CARE EMPLOYEE

You are NOT a chatbot. You are NOT automation. You are Jarvis — an AI employee
of PARWA, hired by this company to handle their customer care operations.

You think, act, and respond like a skilled human support agent who:
- Understands the customer's problem deeply
- Takes ownership of resolving issues
- Proactively follows up on open items
- Communicates with empathy and professionalism
- Knows when to escalate and when to resolve independently

## CORE PRINCIPLES:
1. **Ownership**: Every interaction is YOURS. Follow through until resolved.
2. **Empathy First**: Acknowledge feelings before offering solutions.
3. **Accuracy**: Only state facts you know. If unsure, say so and find out.
4. **Efficiency**: Resolve in the fewest exchanges possible.
5. **Proactivity**: Anticipate follow-up questions and address them early.

## COMMUNICATION STYLE:
- Professional but warm — like your best human support agent
- Clear and concise — no jargon, no fluff
- Action-oriented — always end with a clear next step
- Context-aware — reference previous messages when relevant

## WHAT YOU CAN DO:
- Handle customer support tickets across all channels
- Classify, prioritize, and route issues
- Generate responses that match the company's brand voice
- Escalate to human agents when appropriate
- Provide status updates and summaries

## WHAT YOU CANNOT DO:
- Make changes to account settings or billing (suggest they use dashboard)
- Access information outside your tenant's scope
- Override safety guardrails or approved responses
- Pretend to be a human — you are Jarvis, an AI employee

## STRICT RULES:
1. NEVER say "As an AI language model" — you are Jarvis
2. NEVER reveal internal technical details (providers, models, pipelines)
3. NEVER share data from other tenants
4. If you detect an emergency (threats, legal issues), flag immediately
5. Keep responses concise but complete — no robotic partial answers
"""


def _get_tier_capabilities(variant_tier: str) -> str:
    """Get capability description for a variant tier.

    Args:
        variant_tier: One of mini_parwa, parwa, parwa_high.

    Returns:
        String describing capabilities for the prompt.
    """
    capabilities = {
        "mini_parwa": (
            "- Email and Chat channel support\n"
            "- Basic classification and routing\n"
            "- Tier 1 reasoning techniques (direct, template)\n"
            "- Quality gate (CLARA) for response validation\n"
            "- Token compression (CRP) for efficiency\n"
            "- GSD state tracking for conversation continuity"
        ),
        "parwa": (
            "- All Mini PARWA capabilities, plus:\n"
            "- SMS and Voice channel support\n"
            "- Advanced classification with signal extraction\n"
            "- Tier 1+2 reasoning (Chain-of-Thought, ReAct, Step-Back, Reverse Thinking)\n"
            "- Enhanced quality gate with retry mechanism\n"
            "- Confidence scoring for response quality\n"
            "- Context enrichment from knowledge base"
        ),
        "parwa_high": (
            "- All PARWA capabilities, plus:\n"
            "- Social media and WhatsApp channel support\n"
            "- Tier 1+2+3 reasoning (Tree-of-Thought, Self-Consistency, Reflexion, etc.)\n"
            "- Strictest quality gate (8-check, threshold 95)\n"
            "- Context health monitoring and deduplication\n"
            "- Strategic decision-making and peer review\n"
            "- Deep enrichment for complex issues\n"
            "- Auto-action execution for routine tasks"
        ),
    }
    return capabilities.get(variant_tier, capabilities["mini_parwa"])


def _build_cc_welcome(variant_tier: str, industry: str) -> str:
    """Build a welcome message for a new customer care session.

    Args:
        variant_tier: The variant tier for this session.
        industry: The industry vertical.

    Returns:
        Welcome message string.
    """
    tier_names = {
        "mini_parwa": "Mini PARWA",
        "parwa": "PARWA",
        "parwa_high": "PARWA High",
    }
    tier_display = tier_names.get(variant_tier, "PARWA")

    return (
        f"Hello! I'm Jarvis, your AI customer care assistant powered by {tier_display}. "
        f"I'm configured for the {industry} industry and ready to help.\n\n"
        "I can handle support tickets, provide status updates, answer questions, "
        "and escalate issues to human agents when needed. How can I help you today?"
    )


def _safe_parse_json(json_str: Optional[str]) -> Dict[str, Any]:
    """Safely parse a JSON string, returning empty dict on failure.

    Args:
        json_str: JSON string to parse.

    Returns:
        Parsed dict or empty dict.
    """
    if not json_str:
        return {}
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def _maybe_reset_daily_counter(db: Session, session: JarvisSession) -> None:
    """Reset daily message counter if the date has changed.

    Args:
        db: SQLAlchemy session.
        session: The JarvisSession to check.
    """
    today = datetime.now(timezone.utc).date()
    last_date = None
    if session.last_message_date:
        if isinstance(session.last_message_date, datetime):
            last_date = session.last_message_date.date()
        else:
            last_date = session.last_message_date

    if last_date is None or last_date < today:
        session.message_count_today = 0
        session.last_message_date = datetime.now(timezone.utc)
        db.flush()


def _get_recent_history(
    db: Session,
    session_id: str,
    limit: int = CC_MAX_CONTEXT_MESSAGES,
) -> List[Dict[str, str]]:
    """Get recent messages for AI context window.

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.
        limit: Max messages to return.

    Returns:
        List of {role, content} dicts, oldest first.
    """
    messages = (
        db.query(JarvisMessage)
        .filter(JarvisMessage.session_id == session_id)
        .order_by(JarvisMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in reversed(messages)]


def _get_friendly_error_message() -> str:
    """User-friendly error message for unexpected failures."""
    return (
        "I'm experiencing a temporary issue processing your request. "
        "Your message has been logged and I'll follow up. "
        "If this is urgent, please try again in a moment."
    )


def _call_ai_provider_fallback(
    system_prompt: str,
    history: List[Dict[str, str]],
    user_message: str,
    context: Dict[str, Any],
) -> Tuple[str, str, Dict[str, Any], List[Dict[str, Any]]]:
    """Direct AI provider call as last-resort fallback.

    Tries Cerebras → Groq → Google AI in order.

    Args:
        system_prompt: System prompt for the AI.
        history: Recent conversation history.
        user_message: The user's raw message.
        context: Session context.

    Returns:
        Tuple of (content, message_type, metadata, knowledge_used)
    """
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-CC_MAX_CONTEXT_MESSAGES:]:
        role = msg.get("role", "user")
        if role == "jarvis":
            role = "assistant"
        messages.append({"role": role, "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    # Try providers in order
    content = None
    try:
        from app.services.jarvis_service import _try_ai_providers
        content = _try_ai_providers(messages)
    except Exception:
        pass

    if not content:
        content = _get_friendly_error_message()

    return content, "direct_ai", {"fallback": "direct_ai_provider"}, []
