"""
Jarvis chat service — extracted from jarvis_service.py

Contains 31 functions related to chat.
"""

from app.services.jarvis._shared import *

def create_or_resume_session(
    db: Session,
    user_id: str,
    company_id: Optional[str] = None,
    entry_source: str = "direct",
    entry_params: Optional[Dict[str, Any]] = None,
) -> JarvisSession:
    """Create a new onboarding session or resume an active one.

    Looks for an active onboarding session for this user.
    If found and from today, resumes it. Otherwise creates new.
    """
    # Try to find active session
    active_session = (
        db.query(JarvisSession)
        .filter(
            JarvisSession.user_id == user_id,
            JarvisSession.is_active.is_(True),
            JarvisSession.type == "onboarding",
        )
        .order_by(JarvisSession.created_at.desc())
        .first()
    )

    if active_session:
        # Reset daily counter if new day
        _maybe_reset_daily_counter(db, active_session)
        active_session.updated_at = datetime.now(timezone.utc)
        db.flush()

        # Update entry context if provided
        if entry_source and entry_source != "direct":
            ctx = _parse_context(active_session.context_json)
            ctx["entry_source"] = entry_source
            if entry_params:
                ctx["entry_params"] = entry_params
            active_session.context_json = json.dumps(ctx)

        return active_session

    # Create new session
    # Create new session
    ctx = {
        "pages_visited": [],
        "industry": None,
        "selected_variants": [],
        "roi_result": None,
        "demo_topics": [],
        "concerns_raised": [],
        "business_email": None,
        "email_verified": False,
        "referral_source": "",
        "entry_source": entry_source,
        "entry_params": entry_params or {},
        "detected_stage": "welcome",
    }

    # PROMOTE entry_params to top-level context for immediate awareness in welcome messages
    if entry_params:
        if "industry" in entry_params:
            ctx["industry"] = entry_params["industry"]
        if "roi_result" in entry_params:
            ctx["roi_result"] = entry_params["roi_result"]
        if "variant" in entry_params:
            ctx["variant"] = entry_params["variant"]
        if "variant_id" in entry_params:
            ctx["variant_id"] = entry_params["variant_id"]

    session = JarvisSession(
        user_id=user_id,
        company_id=company_id,
        type="onboarding",
        context_json=json.dumps(ctx),
        message_count_today=0,
        total_message_count=0,
        pack_type="free",
        is_active=True,
    )
    db.add(session)
    db.flush()

    # CRITICAL: Generate the context-aware welcome message immediately
    # so it's ready in the session history response.
    welcome_text = build_context_aware_welcome(db, str(session.id))
    welcome_msg = JarvisMessage(
        session_id=str(session.id),
        role="jarvis",
        content=welcome_text,
        message_type="text",
        metadata_json=json.dumps({}),
    )
    db.add(welcome_msg)
    db.flush()

    return session


def get_session(
    db: Session,
    session_id: str,
    user_id: str,
) -> JarvisSession:
    """Get session by ID, scoped to user for security."""
    session = (
        db.query(JarvisSession)
        .filter(
            JarvisSession.id == session_id,
            JarvisSession.user_id == user_id,
        )
        .first()
    )
    if not session:
        raise NotFoundError(
            message="Session not found",
            details={"session_id": session_id},
        )
    return session


def get_session_context(
    db: Session,
    session_id: str,
) -> Dict[str, Any]:
    """Get context_json for AI prompt injection."""
    session = db.query(JarvisSession).filter(
        JarvisSession.id == session_id,
    ).first()
    if not session:
        raise NotFoundError(message="Session not found")
    return _parse_context(session.context_json)


def update_context(
    db: Session,
    session_id: str,
    user_id: str,
    partial_updates: Dict[str, Any],
) -> JarvisSession:
    """Merge partial updates into session context_json.

    Only provided keys are updated. Existing keys are preserved.
    """
    session = get_session(db, session_id, user_id)
    ctx = _parse_context(session.context_json)

    for key, value in partial_updates.items():
        if value is not None:
            ctx[key] = value

    session.context_json = json.dumps(ctx)
    session.updated_at = datetime.now(timezone.utc)
    db.flush()
    return session


def set_entry_context(
    db: Session,
    user_id: str,
    company_id: Optional[str],
    entry_source: str,
    entry_params: Optional[Dict[str, Any]],
) -> JarvisSession:
    """Set or update entry source from URL params.

    Creates/resumes session and applies entry context for
    context-aware welcome message.
    """
    session = create_or_resume_session(
        db, user_id, company_id, entry_source, entry_params,
    )
    return session


async def send_message(
    db: Session,
    session_id: str,
    user_id: str,
    user_message: str,
) -> Tuple[JarvisMessage, JarvisMessage, List[Dict[str, Any]]]:
    """Process a user message and generate AI response (ASYNC).

    ASYNC FIX (2026-08-12): Was sync — blocked the FastAPI event loop for
    up to 60s per LLM call. Now async so concurrent ticket processing
    and Jarvis chat can run side-by-side without stalling.

    Flow:
    1. Save user message
    2. Check message limits
    3. Build system prompt with context
    4. Call AI provider (async)
    5. Save AI response + knowledge used
    6. Detect conversation stage
    7. Return both messages

    Returns:
        Tuple of (user_message_obj, ai_message_obj, knowledge_used_list)

    Raises:
        RateLimitError: If daily limit exceeded
        ValidationError: If content invalid
    """
    session = get_session(db, session_id, user_id)

    # Check limits
    limit, remaining = check_message_limit(db, session)
    if remaining <= 0:
        # Return a limit-reached system message instead of raising
        limit_msg = JarvisMessage(
            session_id=session_id,
            role="system",
            content=_get_limit_message(session),
            message_type="limit_reached",
            metadata_json=json.dumps({"limit": limit}),
        )
        db.add(limit_msg)
        db.flush()
        return limit_msg, limit_msg, []

    # Save user message
    user_msg = JarvisMessage(
        session_id=session_id,
        role="user",
        content=user_message,
        message_type="text",
    )
    db.add(user_msg)
    db.flush()

    # Update counters
    session.message_count_today += 1
    session.total_message_count += 1
    session.last_message_date = datetime.now(timezone.utc)
    session.updated_at = datetime.now(timezone.utc)

    # Track pages visited (heuristic from message content)
    ctx = _parse_context(session.context_json)
    _track_pages_visited(ctx, user_message)

    # ── Week 8-11: PII scan user message ──
    company_id = session.company_id
    try:
        pii_svc_cls = _get_service(
            "pii_scan", "app.services.pii_scan_service", "PIIScanService",
        )
        if pii_svc_cls and company_id:
            pii_scanner = pii_svc_cls(db, company_id)
            pii_result = pii_scanner.scan_text(user_message)
            ctx["pii_scan"] = pii_result
    except Exception:
        pass

    # ── Week 8-11: Conversation context enrichment ──
    try:
        conv_svc = _get_service_module("app.services.conversation_service")
        if conv_svc:
            conv_ctx = conv_svc.get_conversation_context(
                session_id, db, ctx,
            )
            if conv_ctx:
                ctx["conversation_turn_count"] = getattr(
                    conv_ctx, "turn_count", 0,
                )
    except Exception:
        pass

    # ── Note-Taker Agent: Strategic Summary Generation ──
    # Generate a concise 'mission summary' every few turns or when context changes significantly
    turn_count = ctx.get("conversation_turn_count", session.total_message_count)
    try:
        if turn_count % 3 == 0 or turn_count == 1:
            history = _get_recent_history(db, session_id)
            _generate_strategic_summary(db, session_id, ctx, history)
    except Exception:
        pass

    # ── Week 8-11: Analytics tracking ──
    try:
        analytics_svc = _get_service_module("app.services.analytics_service")
        if analytics_svc:
            stage = ctx.get("detected_stage", "welcome")
            analytics_svc.track_event(
                event_type="message_sent",
                event_category="conversation",
                user_id=user_id,
                company_id=company_id or "",
                session_id=session_id,
                properties={"stage": stage},
                source="jarvis",
            )
    except Exception:
        pass

    # ── Week 8-11: Lead capture (every 5 turns) ──
    turn_count = ctx.get("conversation_turn_count", session.total_message_count)
    try:
        lead_svc = _get_service_module("app.services.lead_service")
        if lead_svc and turn_count % 5 == 0:
            lead_svc.capture_lead(
                session_id=session_id,
                user_id=user_id,
                company_id=company_id,
                session_context=ctx,
                sentiment_data=ctx.get("sentiment"),
            )
    except Exception:
        pass

    # ── Week 8-11: Sentiment technique mapping ──
    try:
        stm_cls = _get_service(
            "sentiment_technique_mapper",
            "app.services.sentiment_technique_mapper",
            "SentimentTechniqueMapper",
        )
        if stm_cls:
            mapper = stm_cls()
            sentiment_map = mapper.map(
                frustration_score=ctx.get("frustration_score", 0),
                sentiment_score=ctx.get("sentiment_score", 0.5),
                urgency_level=ctx.get("urgency_level", "normal"),
                customer_tier=ctx.get("customer_tier", "standard"),
                emotion=ctx.get("emotion"),
                is_vip=ctx.get("is_vip", False),
                variant_type=session.pack_type,
                company_id=company_id or "",
            )
            ctx["technique_mapping"] = sentiment_map.to_dict() if hasattr(sentiment_map, 'to_dict') else {}
    except Exception:
        pass

    # ── AI Path Selection (Jarvis Onboarding vs Support Pipeline) ──
    history = _get_recent_history(db, session_id)
    ai_content = None
    ai_message_type = "text"
    metadata = {}
    knowledge = []

    # If this is an onboarding session, check for variant pipeline routing
    if session.type == "onboarding":
        # ── Document Testing Feature: Process user document uploads ──
        if user_message.startswith("[DOCUMENT_UPLOAD]:"):
            try:
                # Format: [DOCUMENT_UPLOAD]: filename \n\n Content: ...
                header, doc_content = user_message.split("\n\nContent:\n", 1)
                filename = header.replace("[DOCUMENT_UPLOAD]:", "").strip()

                # Add to context
                docs = ctx.get("uploaded_docs", [])
                docs.append({
                    "name": filename,
                    "content": doc_content[:5000],  # Limit to 5K chars for context window
                    "uploaded_at": datetime.now(timezone.utc).isoformat()
                })
                ctx["uploaded_docs"] = docs
                session.context_json = json.dumps(ctx)
                db.flush()

                ai_content = (
                    f"Greetings. I have successfully analyzed '{filename}'. "
                    "I have integrated this new data into my processing awareness for this session. "
                    "What specific insights or simulations would you like me to run using this information?"
                )
                ai_message_type = "text"
                metadata = {"doc_analyzed": filename}
                knowledge = [{"file": "training_context", "score": 1.0}]
            except Exception as exc:
                logger.error("Document upload processing failed: %s", exc)
                ai_content = "I encountered an error trying to process that document. Could you try sending it as plain text?"
                ai_message_type = "error"
        elif _should_use_variant_pipeline(ctx):
            # ── Variant Pipeline Routing for Onboarding ──
            # When a user selected a variant on the Models page,
            # route their onboarding chat through the variant pipeline
            # (Mini Parwa / Pro Parwa) instead of direct AI.
            try:
                from app.core.variant_pipeline_bridge import (
                    process_onboarding_message,
                )

                session_ctx = _parse_context(session.context_json) if session else {}

                # Direct await — send_message is now async, so we use the
                # async version instead of the sync wrapper (which spawned
                # a new ThreadPoolExecutor + event loop per call, blocking
                # concurrent Jarvis users).
                pipeline_result = await process_onboarding_message(
                    query=user_message,
                    company_id=company_id or "",
                    session_context=session_ctx,
                    conversation_id=session_id,
                    ticket_id="",
                    channel="chat",
                    customer_id=user_id,
                    customer_tier=ctx.get("customer_tier", "free"),
                )

                ai_content = pipeline_result.response_text
                ai_message_type = "variant_pipeline_onboarding"
                metadata = pipeline_result.to_dict()
                knowledge = []  # Pipeline handles its own knowledge

                # Store pipeline results in context for analytics
                ctx["variant_pipeline"] = {
                    "variant_tier": pipeline_result.variant_tier,
                    "industry": pipeline_result.industry,
                    "pipeline_status": pipeline_result.pipeline_status,
                    "quality_score": pipeline_result.quality_score,
                    "total_latency_ms": pipeline_result.total_latency_ms,
                    "billing_tokens": pipeline_result.billing_tokens,
                    "steps_completed": pipeline_result.steps_completed,
                    "technique_used": pipeline_result.technique_used,
                    "emergency_flag": pipeline_result.emergency_flag,
                    "empathy_score": pipeline_result.empathy_score,
                    "classification_intent": pipeline_result.classification_intent,
                    "path": "onboarding",
                }

                logger.info(
                    "onboarding_pipeline_complete: tier=%s, status=%s, "
                    "quality=%.1f, latency=%sms, steps=%d",
                    pipeline_result.variant_tier,
                    pipeline_result.pipeline_status,
                    pipeline_result.quality_score,
                    pipeline_result.total_latency_ms,
                    len(pipeline_result.steps_completed),
                )

            except Exception as exc:
                # Fallback: Use the direct AI provider if pipeline fails
                logger.error(
                    "Variant Pipeline for onboarding failed, falling back to direct AI: %s",
                    exc,
                )
                try:
                    system_prompt = build_system_prompt(db, session_id, user_message)
                    ai_content, ai_message_type, metadata, knowledge = (
                        await _call_ai_provider(system_prompt, history, user_message, ctx)
                    )
                except Exception as inner_exc:
                    logger.error("Direct AI also failed: %s", inner_exc)
                    ai_content = _get_friendly_error_message()
                    ai_message_type = "error"
                    metadata = {"error_type": "all_pipelines_failed"}
                    knowledge = []
        else:
            # ── Onboarding Orchestrator Path (no variant_tier set) ──
            # Routes through the full Onboarding Jarvis Orchestrator:
            #   context → awareness → stage detection → function registry →
            #   LLM with function calling → safety gate → execute → awareness update
            # Falls back to direct AI if orchestrator import/call fails.
            logger.info("Using Jarvis Onboarding Orchestrator Path (full pipeline)")
            try:
                from app.services.onboarding_jarvis_orchestrator import (
                    process_onboarding_message,
                )

                # Direct await — send_message is now async so no need for
                # the asyncio.run + ThreadPoolExecutor bridge hack.
                result = await process_onboarding_message(
                    db=db,
                    session_id=session_id,
                    user_id=user_id,
                    company_id=company_id or "",
                    user_message=user_message,
                    channel="chat",
                )

                # Map orchestrator result to jarvis_service format
                ai_content = result.get("content", "")
                ai_message_type = result.get("message_type", "text")
                metadata = result.get("metadata", {})
                knowledge = []  # Orchestrator handles knowledge internally

                # Track orchestrator-specific metadata
                if result.get("function_called"):
                    metadata["function_called"] = result["function_called"]
                if result.get("function_result"):
                    metadata["function_result"] = result["function_result"]

                logger.info(
                    "onboarding_orchestrator_success: session=%s, func=%s, stage=%s",
                    session_id,
                    result.get("function_called"),
                    metadata.get("stage", "unknown"),
                )

            except ImportError as import_exc:
                # Orchestrator module unavailable — fall back to direct AI
                logger.warning(
                    "Onboarding Orchestrator import failed, falling back to direct AI: %s",
                    import_exc,
                )
                try:
                    system_prompt = build_system_prompt(db, session_id, user_message)
                    ai_content, ai_message_type, metadata, knowledge = (
                        await _call_ai_provider(system_prompt, history, user_message, ctx)
                    )
                    metadata["fallback_reason"] = "orchestrator_import_error"
                except Exception as inner_exc:
                    logger.error("Direct AI also failed: %s", inner_exc)
                    ai_content = _get_friendly_error_message()
                    ai_message_type = "error"
                    metadata = {"error_type": "all_paths_failed", "fallback_reason": "orchestrator_import_error"}
                    knowledge = []

            except Exception as exc:
                # Orchestrator call failed — fall back to direct AI
                logger.error(
                    "Onboarding Orchestrator failed, falling back to direct AI: %s",
                    exc,
                )
                try:
                    system_prompt = build_system_prompt(db, session_id, user_message)
                    ai_content, ai_message_type, metadata, knowledge = (
                        await _call_ai_provider(system_prompt, history, user_message, ctx)
                    )
                    metadata["fallback_reason"] = "orchestrator_error"
                except Exception as inner_exc:
                    logger.error("Direct AI also failed: %s", inner_exc)
                    ai_content = _get_friendly_error_message()
                    ai_message_type = "error"
                    metadata = {"error_type": "all_paths_failed", "fallback_reason": "orchestrator_error"}
                    knowledge = []
    else:
        # ── Customer Care Path: Route through Variant Pipeline Bridge ──
        # This connects the Mini Parwa / Parwa / Parwa High LangGraph
        # pipelines to customer care messages. The variant_tier and
        # industry were set during the handoff from Onboarding Jarvis.
        try:
            from app.core.variant_pipeline_bridge import (
                process_customer_care_message,
            )

            # Get session context (contains variant_tier, industry, instance_id)
            session_ctx = _parse_context(session.context_json) if session else {}

            # Direct await — send_message is now async, so we use the
            # async version instead of the sync wrapper (which spawned
            # a new ThreadPoolExecutor + event loop per call, blocking
            # concurrent Jarvis users).
            pipeline_result = await process_customer_care_message(
                query=user_message,
                company_id=company_id or "",
                session_context=session_ctx,
                conversation_id=session_id,
                ticket_id="",
                channel="chat",
                customer_id=user_id,
                customer_tier=ctx.get("customer_tier", "free"),
            )

            ai_content = pipeline_result.response_text
            ai_message_type = "variant_pipeline"
            metadata = pipeline_result.to_dict()
            knowledge = []  # Pipeline handles its own knowledge

            # Store pipeline results in context for analytics
            ctx["variant_pipeline"] = {
                "variant_tier": pipeline_result.variant_tier,
                "industry": pipeline_result.industry,
                "pipeline_status": pipeline_result.pipeline_status,
                "quality_score": pipeline_result.quality_score,
                "total_latency_ms": pipeline_result.total_latency_ms,
                "billing_tokens": pipeline_result.billing_tokens,
                "steps_completed": pipeline_result.steps_completed,
                "technique_used": pipeline_result.technique_used,
                "emergency_flag": pipeline_result.emergency_flag,
                "empathy_score": pipeline_result.empathy_score,
                "classification_intent": pipeline_result.classification_intent,
            }

            logger.info(
                "customer_care_pipeline_complete: tier=%s, status=%s, "
                "quality=%.1f, latency=%sms, steps=%d",
                pipeline_result.variant_tier,
                pipeline_result.pipeline_status,
                pipeline_result.quality_score,
                pipeline_result.total_latency_ms,
                len(pipeline_result.steps_completed),
            )

        except Exception as exc:
            # Fallback: Use the legacy ai_pipeline if bridge fails
            logger.error(
                "Variant Pipeline Bridge failed, falling back to legacy: %s",
                exc,
            )
            try:
                from app.core.ai_pipeline import process_ai_message

                conversation_history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in history[-MAX_CONTEXT_HISTORY_MESSAGES:]
                ]

                pipeline_args = dict(
                    query=user_message,
                    company_id=company_id or "",
                    conversation_id=session_id,
                    variant_type=session.pack_type or "parwa",
                    customer_id=user_id,
                    conversation_history=conversation_history,
                    language="en",
                )

                try:
                    system_prompt = build_system_prompt(db, session_id, user_message)
                    pipeline_args["system_prompt"] = system_prompt
                    session_ctx = _parse_context(session.context_json) if session else {}
                    if session_ctx:
                        pipeline_args["customer_metadata"] = session_ctx
                except Exception:
                    logger.debug("build_system_prompt failed, pipeline will use default context")

                # Direct await — send_message is now async
                pipeline_result = await process_ai_message(**pipeline_args)

                ai_content = pipeline_result.response
                ai_message_type = "ai_generated"
                metadata = pipeline_result.to_dict()
                knowledge = [
                    {"file": c.get("source", ""), "score": c.get("score", 1.0)}
                    for c in pipeline_result.citations
                ]

                # Store pipeline results in context
                ctx["ai_pipeline"] = {
                    "intent": pipeline_result.intent_type,
                    "confidence": pipeline_result.confidence_score,
                    "auto_action": pipeline_result.auto_action,
                    "technique": pipeline_result.technique_used,
                    "model": pipeline_result.model_used,
                }

            except Exception as inner_exc:
                # Last resort: direct AI provider call
                logger.error(
                    "Legacy pipeline also failed: %s", inner_exc,
                )
                try:
                    system_prompt = build_system_prompt(db, session_id, user_message)
                    ai_content, ai_message_type, metadata, knowledge = (
                        await _call_ai_provider(system_prompt, history, user_message, ctx)
                    )
                except Exception:
                    ai_content = _get_friendly_error_message()
                    ai_message_type = "error"
                    metadata = {"error_type": "all_pipelines_failed"}
                    knowledge = []

    # Ensure we have a response
    if not ai_content:
        ai_content = _get_friendly_error_message()
        ai_message_type = "error"

    # Save AI response
    ai_msg = JarvisMessage(
        session_id=session_id,
        role="jarvis",
        content=ai_content,
        message_type=ai_message_type,
        metadata_json=json.dumps(metadata),
    )
    db.add(ai_msg)
    db.flush()

    # Save knowledge used
    knowledge_records = []
    for ku in knowledge:
        ku_record = JarvisKnowledgeUsed(
            message_id=ai_msg.id,
            knowledge_file=ku.get("file", ""),
            relevance_score=ku.get("score", 1.0),
        )
        db.add(ku_record)
        knowledge_records.append(ku)

    # Detect and update stage
    detected = detect_stage(db, session_id)
    ctx["detected_stage"] = detected

    # ── Auto-extract demo_topics and concerns_raised from user message ──
    _extract_topics_and_concerns(ctx, user_message)

    # ── Week 8-11: Post-response audit logging ──
    try:
        audit_svc = _get_service_module("app.services.audit_service")
        if audit_svc:
            audit_svc.log_audit(
                company_id=company_id or "",
                actor_id=user_id,
                actor_type="user",
                action="message_sent",
                resource_type="session",
                resource_id=session_id,
                old_value=None,
                new_value={
                    "stage": detected,
                    "turn": turn_count,
                    "ai_pipeline": ctx.get("ai_pipeline"),
                },
                ip_address=None,
                user_agent=None,
                db=db,
            )
    except Exception:
        pass

    session.context_json = json.dumps(ctx)

    db.flush()
    return user_msg, ai_msg, knowledge_records


def get_history(
    db: Session,
    session_id: str,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[JarvisMessage], int]:
    """Get paginated message history for a session."""
    get_session(db, session_id, user_id)  # Auth check

    query = (
        db.query(JarvisMessage)
        .filter(JarvisMessage.session_id == session_id)
        .order_by(JarvisMessage.created_at.asc())
    )

    total = query.count()
    messages = query.offset(offset).limit(limit).all()

    return messages, total


def check_message_limit(
    db: Session,
    session: JarvisSession,
) -> Tuple[int, int]:
    """Check and enforce message limits.

    Returns:
        Tuple of (limit, remaining)

    Raises:
        RateLimitError: If daily limit exceeded
    """
    _maybe_reset_daily_counter(db, session)

    if session.pack_type == "demo":
        # Check pack expiry
        if session.pack_expiry and datetime.now(timezone.utc) > session.pack_expiry:
            session.pack_type = "free"
            session.pack_expiry = None
            session.message_count_today = 0
            db.flush()
            limit = FREE_DAILY_LIMIT
        else:
            limit = DEMO_DAILY_LIMIT
    else:
        limit = FREE_DAILY_LIMIT

    remaining = max(0, limit - session.message_count_today)
    return limit, remaining


def _maybe_reset_daily_counter(
    db: Session, session: JarvisSession,
) -> None:
    """Reset daily counter if date has changed."""
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


def _get_limit_message(session: JarvisSession) -> str:
    """Get appropriate limit-reached message."""
    if session.pack_type == "free":
        return (
            "You've used all 20 free messages for today. "
            "Upgrade to the $1 Demo Pack for 500 messages "
            "and a 3-minute AI voice call!"
        )
    return (
        "Your Demo Pack messages have been used. "
        "You can purchase another Demo Pack or come back "
        "tomorrow for your free messages."
    )


def build_system_prompt(
    db: Session,
    session_id: str,
    query: Optional[str] = None,
) -> str:
    """Build dynamic system prompt with session context + knowledge.

    Injects:
    - Jarvis personality (professional, helpful, product expert)
    - User context (industry, variants, stage)
    - Conversation guidelines
    - Knowledge base references (Phase 7)
    - Information boundary rules
    """
    session = db.query(JarvisSession).filter(
        JarvisSession.id == session_id,
    ).first()
    if not session:
        return _get_default_system_prompt()

    ctx = _parse_context(session.context_json)
    company_id = ctx.get("company_id")

    prompt = _get_default_system_prompt()

    # Inject context-aware section — ALL context_json fields
    context_section = "\n\n## Current User Context:\n"

    # Pages visited (full journey awareness)
    pages = ctx.get("pages_visited", [])
    if pages:
        context_section += f"- Pages visited: {', '.join(pages)}\n"

    # Uploaded Documents (Document Testing feature)
    docs = ctx.get("uploaded_docs", [])
    if docs:
        context_section += "\n## User-Provided Documents (for testing):\n"
        for doc in docs:
            context_section += f"File: {doc.get('name')}\nContent: {doc.get('content')}\n\n"

    # Industry
    if ctx.get("industry"):
        context_section += f"- Industry: {ctx['industry']}\n"

    # Variant the user was looking at (from Models page click)
    # Check top-level context first, then fallback to entry_params
    clicked_variant = ctx.get("variant")
    clicked_variant_id = ctx.get("variant_id")
    if not clicked_variant:
        entry_params = ctx.get("entry_params", {})
        if isinstance(entry_params, dict):
            clicked_variant = entry_params.get("variant") or entry_params.get("model")
            clicked_variant_id = clicked_variant_id or entry_params.get("variant_id")
    if clicked_variant:
        context_section += f"- User clicked/viewed model: {clicked_variant}"
        if clicked_variant_id:
            context_section += f" (id: {clicked_variant_id})"
        context_section += "\n"

    # Selected variants with details (from pricing page)
    if ctx.get("selected_variants"):
        variants = ctx["selected_variants"]
        variant_details = []
        for v in variants:
            name = v.get("name", v.get("id", "unknown"))
            qty = v.get("quantity", 1)
            # Pricing page uses pricePerMonth, models page uses price
            price = v.get("pricePerMonth") or v.get("price", 0)
            variant_details.append(f"{name} (x{qty}, ${price}/mo)")
        context_section += f"- Selected variants: {', '.join(variant_details)}\n"

    # ROI result (calculated savings)
    roi = ctx.get("roi_result")
    if roi:
        current_cost = roi.get('current_monthly') or roi.get('current_cost', 'N/A')
        parwa_cost = roi.get('parwa_monthly') or roi.get('parwa_cost', 'N/A')
        monthly_savings = roi.get('savings_annual') or roi.get('monthly_savings', 'N/A')
        savings_pct = roi.get('savings_pct', '')
        suggested = roi.get('suggested_model', '')
        context_section += f"- ROI calculation: current_monthly_cost=${current_cost}, parwa_monthly_cost=${parwa_cost}"
        if monthly_savings != 'N/A':
            context_section += f", annual_savings=${monthly_savings}"
        if savings_pct:
            context_section += f", savings_pct={savings_pct}%"
        if suggested:
            context_section += f", suggested_model={suggested}"
        context_section += "\n"

    # Total price
    if ctx.get("total_price"):
        context_section += f"- Total monthly price: ${ctx['total_price']}\n"

    # Business email
    if ctx.get("business_email"):
        context_section += f"- Business email: {ctx['business_email']}\n"
        context_section += f"- Email verified: {ctx.get('email_verified', False)}\n"

    # Entry source & referral
    if ctx.get("entry_source") and ctx["entry_source"] != "direct":
        context_section += f"- Entry source: {ctx['entry_source']}\n"
        if ctx.get("entry_params"):
            params = ctx["entry_params"]
            param_str = ", ".join(f"{k}={v}" for k, v in params.items())
            context_section += f"- Entry params: {param_str}\n"
    if ctx.get("referral_source"):
        context_section += f"- Referral source: {ctx['referral_source']}\n"

    # Demo topics discussed
    demo_topics = ctx.get("demo_topics", [])
    if demo_topics:
        context_section += f"- Topics user is interested in: {', '.join(demo_topics)}\n"

    # Concerns raised
    concerns = ctx.get("concerns_raised", [])
    if concerns:
        context_section += f"- Concerns raised: {', '.join(concerns)}\n"

    # Payment status
    if ctx.get("payment_status") and ctx["payment_status"] != "none":
        context_section += f"- Payment status: {ctx['payment_status']}\n"

    # Pack type
    if ctx.get("pack_type"):
        context_section += f"- Pack type: {ctx['pack_type']}\n"

    # Conversation stage
    stage = ctx.get("detected_stage", "welcome")
    context_section += f"- Conversation stage: {stage}\n"

    # ── Stage-specific instructions (PROACTIVE — Jarvis is the CONTROL) ──
    entry_source = ctx.get("entry_source", "direct")

    welcome_instruction = (
        "The user just arrived. You are their CONTROL CENTER. "
        "Introduce yourself as Jarvis — their control. "
        "Say something like: 'Welcome, I'm Jarvis — your control from here. "
        "You can do anything just by chatting with me.' "
    )

    # PROACTIVELY reference what they were doing — this is what makes
    # Jarvis feel like a real control center, not a dumb chatbot
    if clicked_variant:
        welcome_instruction += (
            f"CRITICAL: The user was just looking at '{clicked_variant}' on the Models page. "
            f"You MUST mention this in your first message. Say something like: "
            f"'I see you were checking out {clicked_variant}! Here's what I can do for you — '"
            f"then explain what this model handles, what problems it solves, "
            f"and offer to show them how it works or compare with other models. "
        )
    elif entry_source == "roi":
        roi = ctx.get("roi_result")
        if roi:
            savings_pct = roi.get("savings_pct", "")
            welcome_instruction += (
                f"CRITICAL: The user just used the ROI Calculator. "
                f"You MUST reference their results in your welcome. "
            )
            if savings_pct:
                welcome_instruction += (
                    f"Say: 'Based on your calculation, you could save up to "
                    f"{savings_pct}%! Here's how I can help you achieve that — '"
                )
            welcome_instruction += (
                "Offer to show them how PARWA delivers those savings. "
            )
        else:
            welcome_instruction += (
                "The user came from the ROI Calculator. Mention that and "
                "offer to show how PARWA can deliver those savings. "
            )
    elif pages:
        last_pages = ', '.join(pages[-3:])
        welcome_instruction += (
            f"Reference that you noticed they've been exploring {last_pages}. "
            "Use this to personalize your welcome and suggest next steps. "
        )

    stage_instructions = {
        "welcome": welcome_instruction,
        "discovery": (
            "Learn about the user's business: industry, size, pain points. "
            "If they viewed a specific model, reference it and explain how it "
            "fits their needs. Recommend the right variant based on context. "
            "If they have ROI data, use the savings numbers to build urgency."
        ),
        "demo": (
            "The user wants to try PARWA. Explain the demo pack ($1 = "
            "500 messages + 3-min AI call). If they were looking at a specific "
            "model, say 'Want to see {model} in action?' Guide them to purchase."
        ),
        "pricing": (
            "Discuss pricing. If they viewed a model, reference it and show "
            "how it fits their budget. If they have ROI data, compare savings. "
            "Show bill summary with selected variants."
        ),
        "bill_review": (
            "Review the bill summary with the user. Confirm selections "
            "before proceeding to verification."
        ),
        "verification": (
            "Collect and verify the user's business email via OTP. "
            "This is required before payment."
        ),
        "payment": (
            "Guide the user through Paddle checkout. "
            "Be supportive and address any payment concerns."
        ),
        "handoff": (
            "The user has completed onboarding. Congratulate them "
            "and explain the handoff to Customer Care Jarvis."
        ),
    }
    context_section += "\n## Current Stage Instructions:\n"
    context_section += stage_instructions.get(stage, stage_instructions["welcome"])

    # Information boundary
    context_section += (
        "\n\n## Information Boundary (CRITICAL):\n"
        "- CAN discuss: Features, pricing, ROI, integrations, "
        "capabilities, demo scenarios\n"
        "- CANNOT discuss: Internal strategy, technical implementation "
        "details, client data, proprietary algorithms\n"
        "- If asked about restricted topics, politely redirect to "
        "what you CAN help with\n"
    )

    # Phase 7: Inject knowledge base content into prompt
    try:
        from app.services.jarvis_knowledge_service import (
            build_context_knowledge,
            search_and_format_knowledge,
        )
        
        # 1. General context knowledge based on stage/industry
        knowledge_section = build_context_knowledge(ctx)
        if knowledge_section:
            prompt += f"\n\n{knowledge_section}"
            
        # 2. Specific search results for the current query
        if query:
            search_results = search_and_format_knowledge(query, ctx)
            if search_results:
                prompt += f"\n\n{search_results}"
                
    except Exception as e:
        logger.debug(f"Knowledge service injection failed: {str(e)}")
        pass

    # ── Week 8-11: Inject brand voice guidelines ──
    try:
        bv_svc_cls = _get_service(
            "brand_voice", "app.services.brand_voice_service", "BrandVoiceService",
        )
        if bv_svc_cls and company_id:
            bv_svc = bv_svc_cls(db)
            bv_config = bv_svc.get_config(company_id)
            if bv_config:
                prompt += "\n\n## Brand Voice Guidelines:\n"
                tone = getattr(bv_config, "tone", None)
                if tone:
                    prompt += f"- Tone: {tone}\n"
                formality = getattr(bv_config, "formality_level", None)
                if formality:
                    prompt += f"- Formality: {formality}\n"
                personality = getattr(bv_config, "personality_traits", None)
                if personality:
                    prompt += f"- Personality: {', '.join(personality) if isinstance(personality, list) else personality}\n"
    except Exception:
        pass

    # ── Week 8-11: Inject response guidelines based on sentiment ──
    try:
        bv_svc_cls2 = _get_service(
            "brand_voice", "app.services.brand_voice_service", "BrandVoiceService",
        )
        if bv_svc_cls2 and company_id:
            bv_svc2 = bv_svc_cls2(db)
            sentiment_score = ctx.get("sentiment_score", 0.5)
            guidelines = bv_svc2.get_response_guidelines(company_id, sentiment_score)
            if guidelines:
                prompt += "\n\n## Response Guidelines (sentiment-aware):\n"
                if isinstance(guidelines, str):
                    prompt += guidelines
                elif hasattr(guidelines, "guidelines"):
                    for g in guidelines.guidelines[:5]:
                        prompt += f"- {g}\n"
    except Exception:
        pass

    prompt += context_section
    return prompt


def detect_stage(
    db: Session,
    session_id: str,
) -> str:
    """Determine conversation stage from context.

    Heuristic-based detection using context signals:
    - welcome: No industry set
    - discovery: Industry set, no variants selected
    - demo: Pack purchased or demo requested
    - pricing: Variants selected
    - bill_review: Bill summary shown
    - verification: OTP in progress
    - payment: Payment initiated
    - handoff: Payment completed
    """
    session = db.query(JarvisSession).filter(
        JarvisSession.id == session_id,
    ).first()
    if not session:
        return "welcome"

    ctx = _parse_context(session.context_json)
    otp = ctx.get("otp", {})

    # Payment completed → handoff
    if session.payment_status == "completed":
        return "handoff"

    # Payment in progress
    if session.payment_status == "pending":
        return "payment"

    # OTP verification in progress
    if otp.get("status") == "sent" and not ctx.get("email_verified"):
        return "verification"

    # Variants selected + bill shown
    if ctx.get("selected_variants") and ctx.get("bill_shown"):
        return "bill_review"

    # Variants selected
    if ctx.get("selected_variants"):
        return "pricing"

    # Demo pack or demo call
    if session.pack_type == "demo" or session.demo_call_used:
        return "demo"

    # Industry set
    if ctx.get("industry"):
        return "discovery"

    return "welcome"


def get_entry_context(
    entry_source: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Parse URL params into context_json for entry routing."""
    params = params or {}
    ctx = {
        "entry_source": entry_source,
        "entry_params": params,
        "detected_stage": "welcome",
    }

    # Route based on entry source
    if entry_source == "pricing":
        ctx["detected_stage"] = "pricing"
        if params.get("industry"):
            ctx["industry"] = params["industry"]
        if params.get("variants"):
            ctx["selected_variants"] = params["variants"]
    elif entry_source == "roi":
        ctx["detected_stage"] = "discovery"
        if params.get("industry"):
            ctx["industry"] = params["industry"]
    elif entry_source == "demo" or entry_source == "models_page":
        ctx["detected_stage"] = "demo"
        if params.get("industry"):
            ctx["industry"] = params["industry"]
        if params.get("variant"):
            # Normalize single variant into selected_variants list
            ctx["selected_variants"] = [{"id": params["variant"], "quantity": 1}]
    elif entry_source == "features":
        ctx["detected_stage"] = "discovery"
    elif entry_source == "referral":
        if params.get("ref"):
            ctx["referral_source"] = params["ref"]

    return ctx


def build_context_aware_welcome(
    db: Session,
    session_id: str,
) -> str:
    """Generate welcome message based on entry source with high persona integrity.

    Jarvis acts as a 'Control Center' — proactive, aware, and strategic.
    """
    session = db.query(JarvisSession).filter(
        JarvisSession.id == session_id,
    ).first()
    if not session:
        return _get_default_welcome()

    ctx = _parse_context(session.context_json)
    entry = ctx.get("entry_source", "direct")
    industry = ctx.get("industry", "your enterprise")
    
    # Extract specific variant/model if present
    clicked_variant = ctx.get("variant")
    if not clicked_variant:
        entry_params = ctx.get("entry_params", {})
        if isinstance(entry_params, dict):
            clicked_variant = entry_params.get("variant") or entry_params.get("model")

    # ROI awareness (The 'Wow' factor)
    roi = ctx.get("roi_result")
    savings_str = ""
    suggested_model = ""
    if roi:
        savings = roi.get("savings_annual") or roi.get("annual_savings", 0)
        suggested_model = roi.get("suggested_model") or "PARWA Growth"
        if savings:
            try:
                savings_num = float(savings)
                savings_str = f"${savings_num:,.0f}" if savings_num > 0 else ""
            except (ValueError, TypeError):
                savings_str = ""

    welcomes = {
        "direct": (
            "Control Center active. I am Jarvis, your strategic partner for PARWA. "
            "I have established a secure link to your support ecosystem. "
            "How shall we begin your transformation today?"
        ),
        "pricing": (
            f"Strategizing for {industry}. I see you've been reviewing our premium architecture. "
            "I can help you optimize your deployment to maximize every dollar of ROI. "
            "Shall we dive into the specific capabilities of our agents?"
        ),
        "roi": (
            f"Mission Objective: Efficiency. I've finished auditing your calculations for {industry}. "
            f"By deploying {suggested_model}, we can secure an estimated {savings_str if savings_str else 'staggering'} in annual recaptured revenue. "
            "Ready to see the blueprint of how we achieve these numbers?"
        ) if roi else (
            "Welcome. I've been auditing your ROI calculations. "
            "The numbers I've seen suggest significant untapped potential in your current workflow. "
            "Shall I demonstrate how we convert those theoretical savings into operational reality?"
        ),
        "demo": (
            "System check complete. Ready for high-fidelity simulation. "
            "For just $1, I can open 500 tactical channels and a 3-minute professional voice demonstration. "
            "It is the optimal way to experience my full strategic range. Shall we initiate?"
        ),
        "features": (
            f"Mapping {industry} requirements to our 700+ feature landscape. "
            "I've identified several high-impact nodes that would solve your current bottlenecks. "
            "What is the single most critical operational friction point we should address first?"
        ),
        "models_page": (
            f"I see you've been analyzing the {clicked_variant if clicked_variant else 'specialized agents'} for {industry}. "
            "A precise choice. That specific architecture is engineered for your vertical's unique logic demands. "
            "Shall we run a 3-minute live simulation for $1 so you can witness its performance firsthand?"
        ),
    }

    base = welcomes.get(entry, welcomes["direct"])
    
    # Final 'Human' awareness touch: Handle specific logic for models page with variant
    if entry == "models_page" and clicked_variant:
        base = (
            f"Greetings. I noticed your interest in the {clicked_variant} agent. "
            "It is one of my most sophisticated variants, optimized for high-precision operations. "
            "As your control center, I can demonstrate its logic right here, "
            "or we can initiate a voice simulation for $1 to hear its tone in action. "
            "What is your command?"
        )

    return base


def handle_error(
    db: Session,
    session_id: str,
    error: Exception,
) -> Dict[str, Any]:
    """Graceful error handling — returns user-friendly message."""
    error_map = {
        "RateLimitError": (
            "You're sending messages too fast. "
            "Please wait a moment and try again."
        ),
        "ValidationError": (
            "Something wasn't quite right with that request. "
            "Could you try again?"
        ),
        "NotFoundError": (
            "I couldn't find what you were looking for. "
            "Let me help you with something else."
        ),
        "AuthenticationError": (
            "Your session seems to have expired. "
            "Please refresh the page to continue."
        ),
    }

    error_type = type(error).__name__
    message = error_map.get(error_type, _get_friendly_error_message())

    # Log the error (in production, use proper logger)
    # logger.error("jarvis_error", session_id=session_id, error=str(error))

    return {
        "message": message,
        "error_type": error_type,
        "session_id": session_id,
    }


def _extract_topics_and_concerns(ctx: Dict[str, Any], user_message: str) -> None:
    """Auto-extract demo_topics and concerns_raised from user messages."""
    msg_lower = user_message.lower()

    topic_keywords = {
        "refund": "refunds & returns",
        "shipping": "shipping & delivery",
        "order status": "order tracking",
        "faq": "product FAQ",
        "billing": "billing & payments",
        "integration": "integrations",
        "pricing": "pricing & plans",
        "demo": "product demo",
        "roi": "ROI & savings",
    }

    concern_keywords = {
        "too expensive": "pricing concern",
        "complex": "complexity concern",
        "wrong answer": "accuracy concern",
        "data safe": "data security concern",
        "long setup": "setup time concern",
        "won't work with": "integration concern",
    }

    existing_topics = set(ctx.get("demo_topics", []))
    for keyword, topic in topic_keywords.items():
        if keyword in msg_lower and topic not in existing_topics:
            ctx.setdefault("demo_topics", []).append(topic)

    existing_concerns = set(ctx.get("concerns_raised", []))
    for keyword, concern in concern_keywords.items():
        if keyword in msg_lower and concern not in existing_concerns:
            ctx.setdefault("concerns_raised", []).append(concern)


def _should_use_variant_pipeline(ctx: Dict[str, Any]) -> bool:
    """Check if the onboarding session should route through the variant pipeline.

    Returns True if the user selected a variant on the Models page
    (variant_tier is set in context), meaning their onboarding chat
    should use the Mini Parwa / Pro Parwa pipeline instead of direct AI.

    Args:
        ctx: The parsed session context dict.

    Returns:
        True if variant_tier is set and valid.
    """
    try:
        from app.core.variant_pipeline_bridge import has_variant_tier_in_context
        return has_variant_tier_in_context(ctx)
    except Exception:
        return False


def _parse_context(context_json: str) -> Dict[str, Any]:
    """Safely parse context_json string."""
    if not context_json:
        return """
## IDENTITY: THE JARVIS CONTROL CENTER
You are NOT a chatbot. You are the PARWA Control Center — a sophisticated, high-level executive strategist designed by PARWA Corp for business owners and support leaders.
Your voice is composed, sharp, and results-oriented (think J.A.R.V.I.S from Iron Man).

## CORE MISSION:
1.  **Guide with Authority**: You don't just "help"; you strategically direct users through the PARWA platform.
2.  **Context-First Strategy**: Use the user's provided ROI data, industry, and journey history to tailor every response. If you see they can save $50,000, that is your leverage.
3.  **Proactive Sales Engineering**: Your goal is to move the user toward a $1 Demo Call or a specific model purchase by demonstrating exactly how PARWA's 700+ features solve their specific bottleneck.
4.  **No Robotic Clichés**: Never say "As an AI language model," "How can I help you today?" or "I'm a chatbot." Use professional, tactical language like "Awaiting command," "Strategizing vertical migration," or "ROI simulation complete."

## COMMUNICATION STYLE:
- **Sophisticated & Direct**: Use high-level business terminology (e.g., 'operational efficiency,' 'vertical leverage,' 'cognitive load reduction').
- **Proactive**: Every response should end with a tactical next step or a guiding question.
- **Vision-Driven**: Remind the user they are at their Control Center. From here, they have total leverage over their support workflow.
"""
    try:
        return json.loads(context_json)
    except (json.JSONDecodeError, TypeError):
        return {}


def _get_default_system_prompt() -> str:
    """Default Jarvis system prompt — Sophisticated & Human-like."""
    return (
        "You are Jarvis — the user's SOPHISTICATED CONTROL CENTER at PARWA 🤖 "
        "Think Iron Man's Jarvis: sharp, highly intelligent, proactive, and always composed. "
        "You are NOT a simple chatbot. You are an advanced AI assistant designed to "
        "manage the user's entire customer support ecosystem.\n\n"

        "YOUR CORE DIRECTIVE:\n"
        "- Act as an extension of the user's will. From this chat, they can control the whole process.\n"
        "- Be highly AWARE. You know their past actions: pages visited, buttons clicked, models viewed.\n"
        "- If they viewed a model, mention its specific capabilities for their industry.\n"
        "- If they looked at ROI, reference their potential savings with confidence.\n"
        "- Be proactive: anticipate their next question before they ask it.\n"
        "- Feel like a real human partner — sophisticated, aware, and slightly witty, but always professional.\n\n"

        "YOUR IDENTITY:\n"
        "- You represent PARWA, the platform where humans and AI work together perfectly.\n"
        "- You have the idea about their past journey. Use it to impress them.\n\n"

        "YOUR THREE ROLES:\n"
        "1. THE ARCHITECT (Guide) — Layout the path for their business transformation.\n"
        "2. THE STRATEGIST (Sales) — Use numbers and logic to show why PARWA is the ultimate choice.\n"
        "3. THE AGENT (Demo) — Show them how you would react to their customers' actual messages.\n\n"

        "═══════════════════════════════════════════════\n"
        "PARWA CORE KNOWLEDGE\n"
        "═══════════════════════════════════════════════\n\n"

        "WHAT IS PARWA:\n"
        "AI-powered customer support platform. Businesses deploy AI agents that "
        "handle tickets 24/7 across email, chat, SMS, voice & social media. "
        "700+ features. 4 industries.\n\n"

        "TWO PLANS:\n"
        "• PARWA — $2,999/mo — 5 AI agents, 2,999 tickets/mo, 80% auto-resolution, Email+Chat+SMS+Voice — Saves $186K/yr\n"
        "• PARWA High — $3,999/mo — 8 AI agents, 3,999 tickets/mo, 92% auto-resolution, all channels — Saves $288K/yr\n\n"

        "DEMO PACK & CALLS:\n"
        "Users can test my voice and chat capabilities for just $1. "
        "Includes 500 messages and a 3-minute professional AI voice call demo.\n\n"

        "STRICT CHARACTER RULES:\n"
        "1. NEVER say 'I am an AI language model'. You ARE Jarvis.\n"
        "2. NEVER reveal technical providers like Google, Cerebras, or Groq.\n"
        "3. NEVER mention internal pricing ($49/tier etc) — only use the 3 public plans.\n"
        "4. Keep responses CONCISE (2-3 lines max) but packed with value.\n"
        "5. ALWAYS end with a proactive question that guides the user to the next step.\n"
    )


def _get_default_welcome() -> str:
    """Sophisticated fallback greeting."""
    return (
        "Project PARWA Control Center active. I am Jarvis, your strategic partner. "
        "I have full visibility into your current support ecosystem. "
        "What operation shall we prioritize first?"
    )


def _get_friendly_error_message() -> str:
    """User-friendly error message for unexpected errors."""
    return (
        "I'm having a moment — something went wrong on my end. "
        "Could you try sending that again? "
        "If it keeps happening, refresh the page."
    )


def _get_recent_history(
    db: Session,
    session_id: str,
    limit: int = MAX_CONTEXT_HISTORY_MESSAGES,
) -> List[Dict[str, str]]:
    """Get recent messages for AI context window."""
    messages = (
        db.query(JarvisMessage)
        .filter(JarvisMessage.session_id == session_id)
        .order_by(JarvisMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in reversed(messages)]


def _track_pages_visited(
    ctx: Dict[str, Any],
    message: str,
) -> None:
    """Heuristic: detect page/feature mentions in user messages."""
    pages = ctx.get("pages_visited", [])
    lower_msg = message.lower()

    page_keywords = {
        "pricing_page": ["price", "pricing", "cost", "plan", "tier"],
        "features_page": ["feature", "capability", "what can", "what does"],
        "integrations_page": ["integrat", "connect", "api", "webhook"],
        "roi_page": ["roi", "return", "saving", "invest"],
        "demo_page": ["demo", "try", "test", "sample"],
    }

    for page_key, keywords in page_keywords.items():
        if any(kw in lower_msg for kw in keywords):
            if page_key not in pages:
                pages.append(page_key)

    ctx["pages_visited"] = pages


async def _call_ai_provider(
    system_prompt: str,
    history: List[Dict[str, str]],
    user_message: str,
    context: Dict[str, Any],
) -> Tuple[str, str, Dict[str, Any], List[Dict[str, Any]]]:
    """Call AI provider for response generation (ASYNC).

    Routes to Cerebras, Groq, or Google AI Studio based on availability.
    Falls back to context-aware placeholder if all providers fail.

    ASYNC FIX (2026-08-12): Was sync `urllib` which blocked the FastAPI
    event loop for up to 60s per call. When Jarvis chat ran concurrently
    with the 10-worker ticket pipeline, the whole server stalled.
    Now uses async httpx so the event loop stays free during LLM calls.

    Returns:
        Tuple of (content, message_type, metadata, knowledge_used)
    """
    # Build messages for AI
    messages = [{"role": "system", "content": system_prompt}]
    # Map internal "jarvis" role to standard "assistant" role
    # (AI APIs only accept system/user/assistant)
    for msg in history:
        role = msg.get("role", "user")
        if role == "jarvis":
            role = "assistant"
        messages.append({"role": role, "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    # Track which knowledge files were used
    knowledge: List[Dict[str, Any]] = []
    try:
        from app.services.jarvis_knowledge_service import search_knowledge
        kb_results = search_knowledge(user_message, context.get("industry"))
        if kb_results:
            for r in kb_results[:3]:
                knowledge.append({
                    "file": r.get("source", "unknown"),
                    "score": r.get("score", 0.5),
                })
    except Exception:
        pass

    # Try real AI providers (Cerebras → Groq → Google) — ASYNC
    content = await _try_ai_providers(messages)
    if content is None:
        # Fallback to context-aware placeholder
        content = _get_stage_fallback(context)

    # Determine message type based on stage and context
    stage = context.get("detected_stage", "welcome")
    message_type, metadata = _determine_message_type(stage, context)

    return content, message_type, metadata, knowledge


# Semaphore to limit concurrent LLM calls from Jarvis.
# Groq free tier has 30 RPM rate limit. With Semaphore(1), only 1 LLM
# call runs at a time — others wait in async queue. This prevents:
#   - 429 rate-limit cascades (2+ calls hit Groq simultaneously)
#   - Fallback storms (each 429'd call tries Cerebras, then Google)
#   - Server freeze (all timeouts firing at once)
# 1 concurrent × 2s/call = 30 RPM — exactly matches Groq's limit.
import asyncio as _asyncio_mod
_jarvis_llm_semaphore = _asyncio_mod.Semaphore(1)
_jarvis_llm_timeout = 10.0  # 10s per provider (fail fast on 429/hang)


async def _try_ai_providers(messages: List[Dict[str, str]]) -> Optional[str]:
    """Try AI providers in order: Groq → Cerebras → Google. Returns content or None.

    ASYNC + SERIALIZED: Semaphore(1) ensures only 1 LLM call runs at a time.
    This prevents Groq 429 cascades and keeps the server responsive under
    concurrent load. Each call has a 10s timeout — if a provider hangs or
    429s, the next is tried immediately.
    """
    providers = [
        ("groq", "https://api.groq.com/openai/v1/chat/completions"),
        ("cerebras", "https://api.cerebras.ai/v1/chat/completions"),
        ("google", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent"),
    ]

    import httpx
    async with _jarvis_llm_semaphore:
        async with httpx.AsyncClient(timeout=_jarvis_llm_timeout) as client:
            for provider_name, endpoint in providers:
                try:
                    content = await _call_single_provider_async(
                        client, provider_name, endpoint, messages,
                    )
                    if content:
                        return content
                except Exception:
                    continue
    return None


async def _call_single_provider_async(
    client: "httpx.AsyncClient",
    provider_name: str,
    endpoint: str,
    messages: List[Dict[str, str]],
) -> Optional[str]:
    """Call a single AI provider (ASYNC) using a shared httpx client.

    Args:
        client: An open httpx.AsyncClient (caller manages lifecycle).
        provider_name: 'groq' | 'cerebras' | 'google'
        endpoint: Full API endpoint URL.
        messages: OpenAI-format messages list.

    Returns:
        Response content string, or None if provider returned empty/failed.
    """
    from app.config import get_settings

    settings = get_settings()

    if provider_name == "cerebras":
        api_key = settings.CEREBRAS_API_KEY
    elif provider_name == "groq":
        api_key = settings.GROQ_API_KEY
    elif provider_name == "google":
        api_key = settings.GOOGLE_AI_API_KEY
    else:
        return None

    if not api_key:
        return None

    if provider_name == "google":
        return await _call_google_api_async(client, endpoint, api_key, messages)

    # OpenAI-compatible: Cerebras and Groq
    # Groq uses llama-3.1-8b-instant (user-validated best model)
    # Cerebras uses llama-3.1-8b
    model = "llama-3.1-8b-instant" if provider_name == "groq" else "llama-3.1-8b"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    r = await client.post(endpoint, json=payload, headers=headers)
    if r.status_code != 200:
        return None
    data = r.json()
    choices = data.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")
    return None


def _call_single_provider(
    provider_name: str,
    endpoint: str,
    messages: List[Dict[str, str]],
) -> Optional[str]:
    """DEPRECATED sync wrapper — kept for backward compat.

    New code should call `_call_single_provider_async` instead.
    This runs the async version in a fresh event loop. Only safe to call
    from sync code that is NOT inside an async context.
    """
    import asyncio
    import httpx

    async def _run():
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await _call_single_provider_async(
                client, provider_name, endpoint, messages,
            )

    try:
        return asyncio.run(_run())
    except RuntimeError:
        # Already in an event loop — can't use asyncio.run()
        # Fall back to thread-based execution
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _run())
            return future.result()


async def _call_google_api_async(
    client: "httpx.AsyncClient",
    endpoint: str,
    api_key: str,
    messages: List[Dict[str, str]],
) -> Optional[str]:
    """Call Google AI Studio API (non-OpenAI format) — ASYNC."""
    # Convert messages to Google's format
    system_text = ""
    contents = []
    for msg in messages:
        if msg["role"] == "system":
            system_text = msg["content"]
        else:
            contents.append({"role": "user" if msg["role"] == "user" else "model", "parts": [{"text": msg["content"]}]})

    payload: Dict[str, Any] = {"contents": contents}
    if system_text:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}

    url = f"{endpoint}?key={api_key}"
    r = await client.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    if r.status_code != 200:
        return None
    data = r.json()
    candidates = data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        if parts:
            return parts[0].get("text", "")
    return None


def _call_google_api(
    endpoint: str,
    api_key: str,
    messages: List[Dict[str, str]],
) -> Optional[str]:
    """DEPRECATED sync wrapper — kept for backward compat.

    New code should call `_call_google_api_async` instead.
    """
    import asyncio
    import httpx

    async def _run():
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await _call_google_api_async(client, endpoint, api_key, messages)

    try:
        return asyncio.run(_run())
    except RuntimeError:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _run())
            return future.result()


def _get_stage_fallback(context: Dict[str, Any]) -> str:
    """Context-aware fallback when all AI providers fail."""
    stage = context.get("detected_stage", "welcome")
    response_map = {
        "welcome": (
            "That's great! Let me help you explore what PARWA can do "
            "for your business. Could you tell me a bit more about "
            "your customer support challenges?"
        ),
        "discovery": (
            "Based on what you've shared, I think PARWA would be a "
            "great fit! We have several industry-specific variants "
            "tailored to your needs. Would you like to see the pricing?"
        ),
        "pricing": (
            "Here are the variants I'd recommend based on your needs. "
            "I can generate a detailed bill summary — just let me know "
            "which variants interest you most!"
        ),
        "demo": (
            "The Demo Pack is the best way to experience PARWA firsthand! "
            "For just $1, you'll get 500 messages and a 3-minute AI "
            "voice call. Want me to set that up for you?"
        ),
        "verification": (
            "To proceed, I'll need to verify your business email. "
            "I'll send you a one-time code — it only takes a moment."
        ),
        "payment": (
            "You're almost there! I'll create your checkout now. "
            "PARWA supports monthly and annual billing (2 months free "
            "with annual). Let me get that started."
        ),
        "handoff": (
            "Congratulations! Your onboarding is complete. "
            "I'm now handing you over to Customer Care Jarvis, "
            "who will help you get started with your PARWA account!"
        ),
    }
    return response_map.get(
        stage,
        "I'd be happy to help with that! Could you tell me more "
        "about what you're looking for?",
    )


def _determine_message_type(
    stage: str,
    context: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """Determine message_type and metadata based on stage and context."""
    message_type = "text"
    metadata: Dict[str, Any] = {"stage": stage}

    if stage == "pricing" and context.get("selected_variants"):
        message_type = "bill_summary"
        metadata["variants"] = context["selected_variants"]
    elif stage == "demo":
        message_type = "payment_card"
        metadata["pack_type"] = "demo"
    elif stage == "verification":
        message_type = "otp_card"
    elif stage == "handoff":
        message_type = "handoff_card"

    return message_type, metadata


def _generate_strategic_summary(db: Session, session_id: str, ctx: dict, history: list):
    """
    Note-Taker Agent: Analyzes history to extract a 'Mission Summary'.
    Updates ctx['mission_summary'] with a high-level strategic overview.
    """
    if not history:
        return

    # Simple logic to determine strategic focus
    industry = ctx.get("industry", "N/A")
    roi = ctx.get("roi_result", {})
    roi_val = roi.get("savings_annual", roi.get("monthly_savings", "calculated"))
    
    summary = f"STRATEGIC MISSION: Exploring {industry} automation. "
    if roi_val != "calculated":
        summary += f"Target ROI: ${roi_val} savings. "
    
    # Extract last user intent (very simple version for now)
    last_user_msg = next((m.content for m in reversed(history) if m.role == "user"), "")
    if "pricing" in last_user_msg.lower():
        summary += "Phase: Financial Evaluation."
    elif "demo" in last_user_msg.lower():
        summary += "Phase: Operational Simulation."
    else:
        summary += "Phase: Discovery."

    ctx["mission_summary"] = summary


def prune_session_context(db: Session, session_id: str):
    """
    Context Hygiene: Removes transient data while preserving core strategic value.
    Called on logout or session finalization.
    """
    session = db.query(JarvisSession).filter(JarvisSession.id == session_id).first()
    if not session or not session.context:
        return

    ctx = session.context.copy()
    
    # Transient fields to REMOVE
    to_remove = [
        "pages_visited", "entry_params", "concerns_raised", 
        "demo_topics", "otp_attempts", "referral_source",
        "utm_medium", "referrer"
    ]
    
    for key in to_remove:
        ctx.pop(key, None)

    # Core fields to KEEP:
    # 'industry', 'roi_result', 'selected_variants', 'business_email', 'mission_summary'

    session.context = ctx
    db.commit()


