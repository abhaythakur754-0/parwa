"""
Jarvis handoff service — extracted from jarvis_service.py

Contains 10 functions related to handoff.
"""

from app.services.jarvis._shared import *

def execute_handoff(
    db: Session,
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Transition from Onboarding Jarvis to Customer Care Jarvis.

    Creates a new customer_care session with selective context transfer.
    The onboarding session is marked with handoff_completed=True.
    Chat memory is NOT transferred (fresh entity).

    MINI PARWA INTEGRATION:
      - Resolves variant_tier from the onboarding context
        (Starter → mini_parwa, Growth → parwa, High → parwa_high)
      - Resolves industry from the onboarding context
      - Creates a VariantInstance record in the database
      - Stores variant_tier, variant_instance_id, and industry
        in the customer care session context so the pipeline
        bridge can route messages correctly
    """
    session = get_session(db, session_id, user_id)

    if session.handoff_completed:
        return {
            "message": "Handoff already completed",
            "handoff_completed": True,
            "new_session_id": None,
            "handoff_at": None,
        }

    # Selective context transfer (NOT full chat memory)
    ctx = _parse_context(session.context_json)

    # ── MINI PARWA: Resolve variant tier from onboarding context ──
    variant_tier = "mini_parwa"  # safe default
    variant_instance_id = ""
    try:
        from app.core.variant_tier_mapper import (
            resolve_tier_from_context,
            resolve_industry_from_context,
        )

        # Resolve tier from variant_id, variant_name, or selected_variants
        variant_tier = resolve_tier_from_context(
            variant_id=ctx.get("variant_id"),
            variant_name=ctx.get("variant"),
            selected_variants=ctx.get("selected_variants"),
        )

        logger.info(
            "handoff_variant_tier_resolved: tier=%s, variant_id=%s, "
            "variant_name=%s, company_id=%s",
            variant_tier,
            ctx.get("variant_id"),
            ctx.get("variant"),
            session.company_id,
        )
    except Exception:
        logger.exception("handoff_variant_tier_resolution_failed — using mini_parwa")

    # ── MINI PARWA: Resolve industry enum value ──
    industry_enum = "general"
    try:
        from app.core.variant_tier_mapper import resolve_industry_from_context
        industry_enum = resolve_industry_from_context(
            industry=ctx.get("industry"),
        )
    except Exception:
        logger.exception("handoff_industry_resolution_failed — using general")

    # ── MINI PARWA: Create VariantInstance in database ──
    try:
        from app.services.variant_instance_service import register_instance

        if session.company_id:
            instance_name = f"{variant_tier}_{industry_enum}_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
            channels = _infer_channels_from_context(ctx, variant_tier)

            variant_instance = register_instance(
                db=db,
                company_id=session.company_id,
                instance_name=instance_name,
                variant_type=variant_tier,
                channel_assignment=channels,
                capacity_config=_get_default_capacity(variant_tier),
            )
            variant_instance_id = str(variant_instance.id)

            logger.info(
                "handoff_variant_instance_created: instance_id=%s, "
                "tier=%s, industry=%s, company_id=%s",
                variant_instance_id, variant_tier, industry_enum,
                session.company_id,
            )
    except Exception:
        logger.exception(
            "handoff_variant_instance_creation_failed — "
            "customer care will use tier from context only",
        )

    # Build care context with variant pipeline info
    care_context = {
        "industry": industry_enum,
        "industry_label": ctx.get("industry"),  # preserve original label
        "selected_variants": ctx.get("selected_variants", []),
        "business_email": ctx.get("business_email"),
        "email_verified": ctx.get("email_verified", False),
        "onboarding_session_id": session_id,
        "onboarding_completed_at": datetime.now(timezone.utc).isoformat(),
        # ── MINI PARWA: Pipeline routing keys ──
        "variant_tier": variant_tier,
        "variant_instance_id": variant_instance_id,
    }

    # Create customer care session (FRESH — no chat history)
    care_session = JarvisSession(
        user_id=user_id,
        company_id=session.company_id,
        type="customer_care",
        context_json=json.dumps(care_context),
        message_count_today=0,
        total_message_count=0,
        pack_type="free",
        is_active=True,
    )
    db.add(care_session)
    db.flush()

    # Mark onboarding session
    session.handoff_completed = True
    session.is_active = False
    session.updated_at = datetime.now(timezone.utc)

    # Create action tickets
    _complete_latest_ticket(db, session_id, "handoff", {
        "care_session_id": care_session.id,
        "variant_tier": variant_tier,
        "variant_instance_id": variant_instance_id,
    })
    _create_ticket(db, session_id, "handoff", {
        "care_session_id": care_session.id,
        "transferred_context_keys": list(care_context.keys()),
        "variant_tier": variant_tier,
        "variant_instance_id": variant_instance_id,
    })

    db.flush()

    return {
        "message": "Welcome to Customer Care Jarvis! I'm here to help.",
        "handoff_completed": True,
        "new_session_id": care_session.id,
        "handoff_at": datetime.now(timezone.utc).isoformat(),
        "variant_tier": variant_tier,
        "variant_instance_id": variant_instance_id,
    }


def _infer_channels_from_context(
    ctx: Dict[str, Any],
    variant_tier: str,
) -> List[str]:
    """Infer channel assignments from onboarding context + variant tier.

    Starter (mini_parwa): email, chat, phone (2 concurrent)
    Growth (parwa):       + sms, voice (3 concurrent)
    High (parwa_high):    + social, video (5 concurrent)

    Args:
        ctx: Onboarding session context.
        variant_tier: Resolved pipeline tier.

    Returns:
        List of channel strings.
    """
    try:
        base_channels = ["email", "chat"]

        if variant_tier in ("parwa", "parwa_high"):
            base_channels.extend(["sms", "voice"])

        if variant_tier == "parwa_high":
            base_channels.extend(["social", "whatsapp"])

        return base_channels
    except Exception:
        return ["email", "chat"]


def _get_default_capacity(variant_tier: str) -> Dict[str, Any]:
    """Get default capacity config for a variant tier.

    Args:
        variant_tier: Resolved pipeline tier.

    Returns:
        Capacity configuration dict.
    """
    try:
        capacities = {
            "mini_parwa": {
                "max_concurrent_tickets": 50,
                "monthly_ticket_limit": 1000,
            },
            "parwa": {
                "max_concurrent_tickets": 200,
                "monthly_ticket_limit": 5000,
            },
            "parwa_high": {
                "max_concurrent_tickets": 500,
                "monthly_ticket_limit": 15000,
            },
        }
        return capacities.get(variant_tier, capacities["mini_parwa"])
    except Exception:
        return {"max_concurrent_tickets": 50, "monthly_ticket_limit": 1000}


def get_handoff_status(
    db: Session,
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Check handoff status for a session."""
    session = get_session(db, session_id, user_id)

    # Check if customer care session was created
    care_session = None
    if session.handoff_completed:
        care_session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.user_id == user_id,
                JarvisSession.type == "customer_care",
            )
            .order_by(JarvisSession.created_at.desc())
            .first()
        )

    return {
        "handoff_completed": session.handoff_completed,
        "new_session_id": care_session.id if care_session else None,
        "handoff_at": (
            session.updated_at.isoformat()
            if session.handoff_completed and session.updated_at
            else None
        ),
    }


def jarvis_complete_onboarding_step(
    db: Session,
    user_id: str,
    company_id: str,
    step: str,
) -> Optional[Dict[str, Any]]:
    """Complete an onboarding step."""
    try:
        onboarding_svc = _get_service_module("app.services.onboarding_service")
        if onboarding_svc:
            return onboarding_svc.complete_step(
                db=db, user_id=user_id, company_id=company_id, step=step,
            )
    except Exception:
        pass
    return None


def jarvis_accept_legal_consents(
    db: Session,
    user_id: str,
    company_id: str,
    accept_terms: bool = True,
    accept_privacy: bool = True,
    accept_ai_data: bool = True,
    client_timestamp: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Accept legal consents during onboarding."""
    try:
        onboarding_svc = _get_service_module("app.services.onboarding_service")
        if onboarding_svc:
            return onboarding_svc.accept_legal_consents(
                db=db,
                user_id=user_id,
                company_id=company_id,
                accept_terms=accept_terms,
                accept_privacy=accept_privacy,
                accept_ai_data=accept_ai_data,
                client_timestamp=client_timestamp,
                ip_address=ip_address,
                user_agent=user_agent,
            )
    except Exception:
        pass
    return None


def jarvis_activate_ai(
    db: Session,
    user_id: str,
    company_id: str,
    ai_name: str = "Jarvis",
    ai_tone: str = "professional_friendly",
    ai_response_style: str = "concise",
    ai_greeting: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Activate AI for a company during onboarding."""
    try:
        onboarding_svc = _get_service_module("app.services.onboarding_service")
        if onboarding_svc:
            return onboarding_svc.activate_ai(
                db=db,
                user_id=user_id,
                company_id=company_id,
                ai_name=ai_name,
                ai_tone=ai_tone,
                ai_response_style=ai_response_style,
                ai_greeting=ai_greeting,
            )
    except Exception:
        pass
    return None


def jarvis_get_pricing_variants(
    industry: str,
    variant_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get pricing variant details."""
    try:
        pricing_svc = _get_service_module("app.services.pricing_service")
        if pricing_svc:
            if variant_id:
                return pricing_svc.get_variant_by_id(industry, variant_id)
            return {
                "cheapest": pricing_svc.get_cheapest_variant(industry),
                "popular": pricing_svc.get_popular_variant(industry),
            }
    except Exception:
        pass
    return None


def jarvis_validate_variant_selection(
    industry: str,
    selections: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Validate variant selections before purchase."""
    try:
        pricing_svc = _get_service_module("app.services.pricing_service")
        if pricing_svc:
            return pricing_svc.validate_variant_selection(industry, selections)
    except Exception:
        pass
    return None


def jarvis_calculate_totals(
    validated_selections: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Calculate pricing totals for validated selections."""
    try:
        pricing_svc = _get_service_module("app.services.pricing_service")
        if pricing_svc:
            return pricing_svc.calculate_totals(validated_selections)
    except Exception:
        pass
    return None


