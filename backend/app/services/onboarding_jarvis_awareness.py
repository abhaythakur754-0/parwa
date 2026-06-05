"""
PARWA Onboarding Jarvis Awareness Engine

Unlike the post-onboarding Awareness Engine (7 system monitoring domains),
this engine tracks the CLIENT JOURNEY and SALES FUNNEL during onboarding.
It gives onboarding Jarvis real-time context awareness about where the
client came from, which variant they're interested in, whether they're
chatting or on a call, what stage they're at, and what the sales state is.

Architecture:
  5 Onboarding Awareness Domains:
    1. ENTRY CONTEXT    — Where the client came from (landing page, pricing,
                          variant demo, ROI calculator, navigation bar)
    2. VARIANT AWARENESS — Which variant(s) the client is interested in,
                          where they clicked demo from
    3. CHANNEL AWARENESS — Whether it's chat or call, channel history
    4. FUNNEL PROGRESS  — Where in the sales funnel the client is,
                          stage transitions, concerns, objections
    5. SALES STATE      — Current state of the sales process:
                          industry, variants, email, payment, handoff

  Data Storage:
    All awareness data is stored in the JarvisSession context_json field.
    This keeps it simple and aligned with the existing architecture — no
    separate table needed. The awareness data lives under the
    "onboarding_awareness" key within context_json.

  Data Flow:
    Session context_json (onboarding_awareness namespace)
        -> collect_onboarding_awareness() reads from all 5 domains
        -> build_awareness_summary() produces human-readable string
        -> Summary is injected into every LLM call so Jarvis "remembers"

  Fallback Strategy:
    The engine NEVER crashes. If a domain collector fails, that domain's
    data is marked as "unknown" and the engine continues with the other
    domains. Partial awareness is better than no awareness.

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except -- never crash.
BC-012: All timestamps UTC.
"""

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.logger import get_logger
from database.models.jarvis import JarvisSession

logger = get_logger("onboarding_jarvis_awareness")


# ── Constants ──────────────────────────────────────────────────────

# Valid funnel stages (ordered by progression)
VALID_FUNNEL_STAGES = (
    "welcome",
    "discovery",
    "demo",
    "pricing",
    "bill_review",
    "verification",
    "payment",
    "handoff",
)

# Valid entry sources
VALID_ENTRY_SOURCES = (
    "landing_page",
    "pricing_page",
    "variant_demo",
    "roi_calculator",
    "navigation_bar",
    "direct",
    "pricing",
    "roi",
    "demo",
    "features",
    "referral",
    "ad",
    "organic",
    "email_campaign",
    "other",
)

# Valid channel types
VALID_CHANNEL_TYPES = ("chat", "call")

# Maximum items to keep in history lists (prevent unbounded growth)
MAX_CHANNEL_HISTORY = 20
MAX_STAGE_TRANSITIONS = 30
MAX_CONCERNS = 50
MAX_QUESTIONS = 50
MAX_OBJECTIONS = 30

# Key prefix for context_json namespace
AWARENESS_KEY = "onboarding_awareness"

__all__ = [
    # Main collection
    "collect_onboarding_awareness",
    # Domain-specific collectors
    "get_entry_context_awareness",
    "get_variant_source_awareness",
    "get_channel_awareness",
    "get_funnel_progress",
    "get_sales_state",
    # Stage detection
    "detect_conversation_stage",
    # Context updates
    "update_onboarding_context",
    # Summary builder
    "build_awareness_summary",
    # Tracking helpers
    "track_variant_click",
    "track_channel_switch",
    "track_concern_raised",
    "track_question_asked",
]


# ══════════════════════════════════════════════════════════════════
# MAIN COLLECTION: Gather awareness from all 5 domains
# ══════════════════════════════════════════════════════════════════


def collect_onboarding_awareness(
    db: Session,
    company_id: str,
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Collect awareness from all 5 onboarding domains.

    Each domain collector is independently wrapped in try/except (BC-008).
    If a collector fails, its fields are set to safe defaults and
    the engine continues with the other domains.

    The awareness data is read from the session's context_json field
    under the "onboarding_awareness" key.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: Onboarding session ID.
        user_id: User ID for security scoping.

    Returns:
        Dict with all 5 domain fields populated.
    """
    start_time = time.monotonic()

    awareness: Dict[str, Any] = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "collection_errors": [],
    }

    # Domain 1: Entry Context
    try:
        awareness.update(get_entry_context_awareness(db, session_id))
    except Exception:
        logger.exception(
            "entry_context_collection_failed: session=%s", session_id,
        )
        awareness["collection_errors"].append("entry_context")
        awareness.update(_default_entry_context())

    # Domain 2: Variant Awareness
    try:
        awareness.update(get_variant_source_awareness(db, session_id))
    except Exception:
        logger.exception(
            "variant_awareness_collection_failed: session=%s", session_id,
        )
        awareness["collection_errors"].append("variant_awareness")
        awareness.update(_default_variant_awareness())

    # Domain 3: Channel Awareness
    try:
        awareness.update(get_channel_awareness(db, session_id))
    except Exception:
        logger.exception(
            "channel_awareness_collection_failed: session=%s", session_id,
        )
        awareness["collection_errors"].append("channel_awareness")
        awareness.update(_default_channel_awareness())

    # Domain 4: Funnel Progress
    try:
        awareness.update(get_funnel_progress(db, session_id))
    except Exception:
        logger.exception(
            "funnel_progress_collection_failed: session=%s", session_id,
        )
        awareness["collection_errors"].append("funnel_progress")
        awareness.update(_default_funnel_progress())

    # Domain 5: Sales State
    try:
        awareness.update(get_sales_state(db, session_id))
    except Exception:
        logger.exception(
            "sales_state_collection_failed: session=%s", session_id,
        )
        awareness["collection_errors"].append("sales_state")
        awareness.update(_default_sales_state())

    elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

    logger.info(
        "onboarding_awareness_collected: session=%s, errors=%d, ms=%s",
        session_id, len(awareness["collection_errors"]), elapsed_ms,
    )

    return awareness


# ══════════════════════════════════════════════════════════════════
# DOMAIN 1: ENTRY CONTEXT
# ══════════════════════════════════════════════════════════════════


def get_entry_context_awareness(
    db: Session,
    session_id: str,
) -> Dict[str, Any]:
    """Get entry context awareness — where the client came from.

    Tracks: entry_source, entry_params, referrer, utm_source

    Args:
        db: SQLAlchemy session.
        session_id: Onboarding session ID.

    Returns:
        Dict with entry_context fields.
    """
    ctx = _get_session_context(db, session_id)
    oa = _get_awareness_namespace(ctx)

    entry_ctx = oa.get("entry_context", {})

    return {
        "entry_source": ctx.get("entry_source", entry_ctx.get("entry_source", "direct")),
        "entry_params": ctx.get("entry_params", entry_ctx.get("entry_params", {})),
        "referrer": entry_ctx.get("referrer", ""),
        "utm_source": entry_ctx.get("utm_source", ""),
        "entry_timestamp": entry_ctx.get("entry_timestamp", ""),
    }


# ══════════════════════════════════════════════════════════════════
# DOMAIN 2: VARIANT AWARENESS
# ══════════════════════════════════════════════════════════════════


def get_variant_source_awareness(
    db: Session,
    session_id: str,
) -> Dict[str, Any]:
    """Get which variant the client came from for demo.

    Tracks: selected_variants, variant_id, variant_name,
    variant_industry, variant_tier, demo_variant_active,
    variant_source (which page they clicked demo from)

    Args:
        db: SQLAlchemy session.
        session_id: Onboarding session ID.

    Returns:
        Dict with variant_awareness fields.
    """
    ctx = _get_session_context(db, session_id)
    oa = _get_awareness_namespace(ctx)

    variant_ctx = oa.get("variant_awareness", {})

    # Also check top-level context for backward compatibility
    selected_variants = ctx.get("selected_variants", variant_ctx.get("selected_variants", []))

    return {
        "selected_variants": selected_variants,
        "variant_id": ctx.get("variant_id", variant_ctx.get("variant_id", "")),
        "variant_name": ctx.get("variant", variant_ctx.get("variant_name", "")),
        "variant_industry": variant_ctx.get("variant_industry", ctx.get("industry", "")),
        "variant_tier": variant_ctx.get("variant_tier", ctx.get("variant_tier", "")),
        "demo_variant_active": variant_ctx.get("demo_variant_active", False),
        "variant_source": variant_ctx.get("variant_source", ""),
    }


# ══════════════════════════════════════════════════════════════════
# DOMAIN 3: CHANNEL AWARENESS
# ══════════════════════════════════════════════════════════════════


def get_channel_awareness(
    db: Session,
    session_id: str,
) -> Dict[str, Any]:
    """Get current channel (chat/call) and history.

    Tracks: current_channel, channel_history, call_status,
    call_duration, chat_message_count

    Args:
        db: SQLAlchemy session.
        session_id: Onboarding session ID.

    Returns:
        Dict with channel_awareness fields.
    """
    ctx = _get_session_context(db, session_id)
    oa = _get_awareness_namespace(ctx)

    channel_ctx = oa.get("channel_awareness", {})

    # Derive chat_message_count from session
    session = _get_session(db, session_id)
    chat_message_count = session.total_message_count if session else 0

    return {
        "current_channel": channel_ctx.get("current_channel", "chat"),
        "channel_history": channel_ctx.get("channel_history", []),
        "call_status": channel_ctx.get("call_status", ""),
        "call_duration": channel_ctx.get("call_duration", 0),
        "chat_message_count": chat_message_count,
    }


# ══════════════════════════════════════════════════════════════════
# DOMAIN 4: FUNNEL PROGRESS
# ══════════════════════════════════════════════════════════════════


def get_funnel_progress(
    db: Session,
    session_id: str,
) -> Dict[str, Any]:
    """Get current funnel stage and transitions.

    Tracks: detected_stage, stage_transitions, time_in_stage,
    concerns_raised, questions_asked, objections_encountered

    Args:
        db: SQLAlchemy session.
        session_id: Onboarding session ID.

    Returns:
        Dict with funnel_progress fields.
    """
    ctx = _get_session_context(db, session_id)
    oa = _get_awareness_namespace(ctx)

    funnel_ctx = oa.get("funnel_progress", {})

    # Top-level detected_stage takes precedence
    detected_stage = ctx.get("detected_stage", funnel_ctx.get("detected_stage", "welcome"))
    if detected_stage not in VALID_FUNNEL_STAGES:
        detected_stage = "welcome"

    # Calculate time in current stage
    stage_entered_at = funnel_ctx.get("stage_entered_at", "")
    time_in_stage = ""
    if stage_entered_at:
        try:
            entered = datetime.fromisoformat(stage_entered_at)
            now = datetime.now(timezone.utc)
            delta = now - entered
            if delta.total_seconds() < 60:
                time_in_stage = f"{int(delta.total_seconds())}s"
            elif delta.total_seconds() < 3600:
                time_in_stage = f"{int(delta.total_seconds() / 60)}m"
            else:
                time_in_stage = f"{int(delta.total_seconds() / 3600)}h"
        except (ValueError, TypeError):
            pass

    # Top-level concerns_raised takes precedence
    concerns = ctx.get("concerns_raised", funnel_ctx.get("concerns_raised", []))

    return {
        "detected_stage": detected_stage,
        "stage_transitions": funnel_ctx.get("stage_transitions", []),
        "stage_entered_at": stage_entered_at,
        "time_in_stage": time_in_stage,
        "concerns_raised": concerns,
        "questions_asked": funnel_ctx.get("questions_asked", []),
        "objections_encountered": funnel_ctx.get("objections_encountered", []),
    }


# ══════════════════════════════════════════════════════════════════
# DOMAIN 5: SALES STATE
# ══════════════════════════════════════════════════════════════════


def get_sales_state(
    db: Session,
    session_id: str,
) -> Dict[str, Any]:
    """Get current sales state.

    Tracks: industry_selected, variants_selected, email_verified,
    demo_pack_purchased, payment_status, bill_total,
    handoff_completed, roi_calculated, competitor_mentioned

    Args:
        db: SQLAlchemy session.
        session_id: Onboarding session ID.

    Returns:
        Dict with sales_state fields.
    """
    ctx = _get_session_context(db, session_id)
    oa = _get_awareness_namespace(ctx)

    sales_ctx = oa.get("sales_state", {})

    # Derive from session + context
    session = _get_session(db, session_id)

    industry_selected = bool(ctx.get("industry", sales_ctx.get("industry_selected", "")))
    selected_variants = ctx.get("selected_variants", [])
    variants_selected = bool(selected_variants) or bool(sales_ctx.get("variants_selected", False))
    email_verified = bool(ctx.get("email_verified", sales_ctx.get("email_verified", False)))
    demo_pack_purchased = (
        session.pack_type == "demo"
        if session
        else sales_ctx.get("demo_pack_purchased", False)
    )
    payment_status = (
        session.payment_status
        if session and session.payment_status
        else sales_ctx.get("payment_status", "none")
    )
    bill_total = sales_ctx.get("bill_total", ctx.get("bill_total", 0))
    handoff_completed = (
        session.handoff_completed
        if session
        else sales_ctx.get("handoff_completed", False)
    )
    roi_calculated = bool(ctx.get("roi_result", sales_ctx.get("roi_calculated", False)))
    competitor_mentioned = sales_ctx.get("competitor_mentioned", False)

    return {
        "industry_selected": industry_selected,
        "variants_selected": variants_selected,
        "email_verified": email_verified,
        "demo_pack_purchased": demo_pack_purchased,
        "payment_status": payment_status,
        "bill_total": bill_total,
        "handoff_completed": handoff_completed,
        "roi_calculated": roi_calculated,
        "competitor_mentioned": competitor_mentioned,
    }


# ══════════════════════════════════════════════════════════════════
# CONVERSATION STAGE DETECTION
# ══════════════════════════════════════════════════════════════════


def detect_conversation_stage(context: Dict[str, Any]) -> str:
    """Detect the current conversation stage from context.

    Based on: what's been discussed, what actions taken, what info collected.

    Heuristic-based detection using context signals:
    - welcome: No industry set, just arrived
    - discovery: Industry set, no variants selected yet
    - demo: Pack purchased or demo requested/active
    - pricing: Variants selected, no bill shown yet
    - bill_review: Bill summary shown to client
    - verification: OTP in progress
    - payment: Payment initiated
    - handoff: Payment completed

    Args:
        context: Session context_json dict.

    Returns:
        One of VALID_FUNNEL_STAGES.
    """
    try:
        # Payment completed -> handoff
        payment_status = context.get("payment_status", "none")
        if payment_status == "completed":
            return "handoff"

        # Payment in progress
        if payment_status == "pending":
            return "payment"

        # OTP verification in progress
        otp = context.get("otp", {})
        if otp.get("status") == "sent" and not context.get("email_verified"):
            return "verification"

        # Variants selected + bill shown
        selected_variants = context.get("selected_variants", [])
        if selected_variants and context.get("bill_shown"):
            return "bill_review"

        # Variants selected
        if selected_variants:
            return "pricing"

        # Demo pack or demo call
        pack_type = context.get("pack_type", "free")
        demo_call_used = context.get("demo_call_used", False)
        if pack_type == "demo" or demo_call_used:
            return "demo"

        # Check awareness namespace for demo_variant_active
        oa = context.get(AWARENESS_KEY, {})
        variant_awareness = oa.get("variant_awareness", {})
        if variant_awareness.get("demo_variant_active"):
            return "demo"

        # Industry set
        if context.get("industry"):
            return "discovery"

        return "welcome"

    except Exception:
        logger.exception("detect_conversation_stage_failed")
        return "welcome"


# ══════════════════════════════════════════════════════════════════
# CONTEXT UPDATES
# ══════════════════════════════════════════════════════════════════


def update_onboarding_context(
    db: Session,
    company_id: str,
    session_id: str,
    updates: Dict[str, Any],
) -> None:
    """Update session context_json with new awareness data.

    Merges updates into the onboarding_awareness namespace within
    context_json. Only provided keys are updated; existing keys
    are preserved.

    Also re-detects the conversation stage and updates it if changed,
    recording the stage transition.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: Onboarding session ID.
        updates: Dict of awareness fields to merge.
    """
    try:
        session = _get_session(db, session_id)
        if not session:
            logger.warning("update_onboarding_context: session not found: %s", session_id)
            return

        ctx = _safe_parse_json(session.context_json)
        oa = ctx.get(AWARENESS_KEY, {})

        # Merge updates into awareness namespace
        oa = _deep_merge(oa, updates)

        # Re-detect conversation stage
        old_stage = ctx.get("detected_stage", "welcome")
        new_stage = detect_conversation_stage(ctx)

        if new_stage != old_stage:
            # Record stage transition
            transition = {
                "from": old_stage,
                "to": new_stage,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            funnel_progress = oa.get("funnel_progress", {})
            transitions = funnel_progress.get("stage_transitions", [])
            transitions.append(transition)
            # Cap list length
            if len(transitions) > MAX_STAGE_TRANSITIONS:
                transitions = transitions[-MAX_STAGE_TRANSITIONS:]
            funnel_progress["stage_transitions"] = transitions
            funnel_progress["stage_entered_at"] = datetime.now(timezone.utc).isoformat()
            oa["funnel_progress"] = funnel_progress

            # Update top-level detected_stage too
            ctx["detected_stage"] = new_stage

            logger.info(
                "stage_transition: session=%s, from=%s, to=%s",
                session_id, old_stage, new_stage,
            )

        ctx[AWARENESS_KEY] = oa
        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

    except Exception:
        logger.exception(
            "update_onboarding_context_failed: session=%s", session_id,
        )


# ══════════════════════════════════════════════════════════════════
# AWARENESS SUMMARY: Human-readable string for LLM injection
# ══════════════════════════════════════════════════════════════════


def build_awareness_summary(awareness: Dict[str, Any]) -> str:
    """Build a human-readable summary for LLM prompt injection.

    The summary is designed to be concise yet complete enough so
    that Jarvis "remembers" the full journey and can tailor responses.

    Example output:
        "Client came from the E-commerce Returns Agent demo page. They're
         chatting via chat. Currently in demo stage. They've asked about
         refund handling and pricing. No email verified yet. No payment made."

    Args:
        awareness: Collected awareness dict from collect_onboarding_awareness().

    Returns:
        Human-readable summary string for LLM prompt injection.
    """
    try:
        parts: List[str] = []

        # ── Entry source ──
        entry_source = awareness.get("entry_source", "direct")
        if entry_source and entry_source != "direct":
            source_labels = {
                "landing_page": "the landing page",
                "pricing_page": "the pricing page",
                "variant_demo": "a variant demo page",
                "roi_calculator": "the ROI calculator",
                "navigation_bar": "the navigation bar",
                "pricing": "the pricing page",
                "roi": "the ROI calculator",
                "demo": "a demo page",
                "features": "the features page",
                "referral": "a referral",
                "ad": "an advertisement",
                "organic": "organic search",
                "email_campaign": "an email campaign",
            }
            source_label = source_labels.get(entry_source, entry_source)
            parts.append(f"Client came from {source_label}")
        else:
            parts.append("Client came directly")

        # ── Variant awareness ──
        variant_name = awareness.get("variant_name", "")
        variant_source = awareness.get("variant_source", "")
        demo_variant_active = awareness.get("demo_variant_active", False)
        if variant_name:
            variant_desc = f"the {variant_name} variant"
            if variant_source:
                variant_desc += f" (clicked from {variant_source})"
            parts.append(f"interested in {variant_desc}")
        elif demo_variant_active:
            parts.append("currently viewing a variant demo")

        # ── Channel ──
        current_channel = awareness.get("current_channel", "chat")
        if current_channel == "call":
            call_status = awareness.get("call_status", "")
            call_duration = awareness.get("call_duration", 0)
            channel_desc = "on a call"
            if call_status:
                channel_desc += f" ({call_status})"
            if call_duration:
                channel_desc += f" for {call_duration}s"
            parts.append(f"They're on {channel_desc}")
        else:
            chat_count = awareness.get("chat_message_count", 0)
            parts.append(f"They're chatting via chat ({chat_count} messages)")

        # ── Funnel stage ──
        detected_stage = awareness.get("detected_stage", "welcome")
        time_in_stage = awareness.get("time_in_stage", "")
        stage_desc = f"Currently in {detected_stage} stage"
        if time_in_stage:
            stage_desc += f" (for {time_in_stage})"
        parts.append(stage_desc)

        # ── Concerns ──
        concerns = awareness.get("concerns_raised", [])
        if concerns:
            parts.append(f"They've raised concerns about: {', '.join(concerns[-5:])}")

        # ── Questions ──
        questions = awareness.get("questions_asked", [])
        if questions:
            recent_topics = [q.get("topic", "") for q in questions[-3:] if q.get("topic")]
            if recent_topics:
                parts.append(f"They've asked about: {', '.join(recent_topics)}")

        # ── Objections ──
        objections = awareness.get("objections_encountered", [])
        if objections:
            parts.append(f"Objections encountered: {', '.join(objections[-3:])}")

        # ── Sales state summary ──
        sales_parts: List[str] = []
        if not awareness.get("email_verified", False):
            sales_parts.append("No email verified yet")
        else:
            sales_parts.append("Email verified")

        if awareness.get("roi_calculated", False):
            sales_parts.append("ROI calculated")

        if awareness.get("competitor_mentioned", False):
            sales_parts.append("competitor mentioned")

        payment_status = awareness.get("payment_status", "none")
        if payment_status == "none":
            sales_parts.append("No payment made")
        elif payment_status == "pending":
            sales_parts.append("Payment in progress")
        elif payment_status == "completed":
            sales_parts.append("Payment completed")

        if awareness.get("handoff_completed", False):
            sales_parts.append("Handoff completed")

        if sales_parts:
            parts.append(". ".join(sales_parts))

        summary = ". ".join(parts) + "."

        return summary

    except Exception:
        logger.exception("build_awareness_summary_failed")
        return "Onboarding awareness unavailable."


# ══════════════════════════════════════════════════════════════════
# TRACKING HELPERS
# ══════════════════════════════════════════════════════════════════


def track_variant_click(
    db: Session,
    company_id: str,
    session_id: str,
    variant_id: str,
    variant_name: str,
    source_page: str,
) -> None:
    """Track when a client clicks on a variant demo from a specific page.

    Updates the variant_awareness namespace in context_json.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: Onboarding session ID.
        variant_id: The variant's ID.
        variant_name: Human-readable variant name.
        source_page: Which page they clicked demo from.
    """
    try:
        update_onboarding_context(
            db=db,
            company_id=company_id,
            session_id=session_id,
            updates={
                "variant_awareness": {
                    "variant_id": variant_id,
                    "variant_name": variant_name,
                    "variant_source": source_page,
                    "demo_variant_active": True,
                    "variant_clicked_at": datetime.now(timezone.utc).isoformat(),
                },
            },
        )
        logger.info(
            "variant_click_tracked: session=%s, variant=%s, source=%s",
            session_id, variant_name, source_page,
        )
    except Exception:
        logger.exception(
            "track_variant_click_failed: session=%s, variant=%s",
            session_id, variant_id,
        )


def track_channel_switch(
    db: Session,
    company_id: str,
    session_id: str,
    from_channel: str,
    to_channel: str,
) -> None:
    """Track when channel switches (e.g., from chat to call).

    Records the switch in channel_history and updates current_channel.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: Onboarding session ID.
        from_channel: Previous channel ('chat' or 'call').
        to_channel: New channel ('chat' or 'call').
    """
    try:
        # Get current channel history
        session = _get_session(db, session_id)
        if not session:
            logger.warning("track_channel_switch: session not found: %s", session_id)
            return

        ctx = _safe_parse_json(session.context_json)
        oa = ctx.get(AWARENESS_KEY, {})
        channel_ctx = oa.get("channel_awareness", {})

        # Append to history
        history = channel_ctx.get("channel_history", [])
        history.append({
            "from": from_channel,
            "to": to_channel,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Cap list length
        if len(history) > MAX_CHANNEL_HISTORY:
            history = history[-MAX_CHANNEL_HISTORY:]

        update_onboarding_context(
            db=db,
            company_id=company_id,
            session_id=session_id,
            updates={
                "channel_awareness": {
                    "current_channel": to_channel,
                    "channel_history": history,
                },
            },
        )
        logger.info(
            "channel_switch_tracked: session=%s, from=%s, to=%s",
            session_id, from_channel, to_channel,
        )
    except Exception:
        logger.exception(
            "track_channel_switch_failed: session=%s", session_id,
        )


def track_concern_raised(
    db: Session,
    company_id: str,
    session_id: str,
    concern: str,
) -> None:
    """Track concerns/objections raised by client.

    Adds the concern to both the top-level concerns_raised list
    and the funnel_progress.concerns_raised list in the awareness
    namespace.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: Onboarding session ID.
        concern: The concern text.
    """
    try:
        session = _get_session(db, session_id)
        if not session:
            logger.warning("track_concern_raised: session not found: %s", session_id)
            return

        ctx = _safe_parse_json(session.context_json)
        oa = ctx.get(AWARENESS_KEY, {})

        # Update top-level concerns_raised
        concerns = ctx.get("concerns_raised", [])
        if concern not in concerns:
            concerns.append(concern)
            if len(concerns) > MAX_CONCERNS:
                concerns = concerns[-MAX_CONCERNS:]
            ctx["concerns_raised"] = concerns

        # Also update funnel_progress namespace
        funnel_ctx = oa.get("funnel_progress", {})
        fp_concerns = funnel_ctx.get("concerns_raised", [])
        if concern not in fp_concerns:
            fp_concerns.append(concern)
            if len(fp_concerns) > MAX_CONCERNS:
                fp_concerns = fp_concerns[-MAX_CONCERNS:]
        funnel_ctx["concerns_raised"] = fp_concerns
        oa["funnel_progress"] = funnel_ctx

        ctx[AWARENESS_KEY] = oa
        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        logger.info(
            "concern_tracked: session=%s, concern=%s",
            session_id, concern[:100],
        )
    except Exception:
        logger.exception(
            "track_concern_raised_failed: session=%s", session_id,
        )


def track_question_asked(
    db: Session,
    company_id: str,
    session_id: str,
    question: str,
    topic: str,
) -> None:
    """Track questions asked by topic.

    Records each question with its topic in the funnel_progress
    namespace in context_json.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: Onboarding session ID.
        question: The question text (truncated for storage).
        topic: Topic category (e.g., 'pricing', 'features', 'demo').
    """
    try:
        session = _get_session(db, session_id)
        if not session:
            logger.warning("track_question_asked: session not found: %s", session_id)
            return

        ctx = _safe_parse_json(session.context_json)
        oa = ctx.get(AWARENESS_KEY, {})

        funnel_ctx = oa.get("funnel_progress", {})
        questions = funnel_ctx.get("questions_asked", [])
        questions.append({
            "question": question[:200],  # Truncate for storage
            "topic": topic,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Cap list length
        if len(questions) > MAX_QUESTIONS:
            questions = questions[-MAX_QUESTIONS:]

        funnel_ctx["questions_asked"] = questions
        oa["funnel_progress"] = funnel_ctx

        # Also update objections if it sounds like an objection
        objection_keywords = ("too expensive", "not sure", "don't need", "competitor", "alternative")
        question_lower = question.lower()
        for kw in objection_keywords:
            if kw in question_lower:
                objections = funnel_ctx.get("objections_encountered", [])
                if topic not in objections:
                    objections.append(topic)
                    if len(objections) > MAX_OBJECTIONS:
                        objections = objections[-MAX_OBJECTIONS:]
                funnel_ctx["objections_encountered"] = objections
                break

        oa["funnel_progress"] = funnel_ctx

        ctx[AWARENESS_KEY] = oa
        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        logger.info(
            "question_tracked: session=%s, topic=%s",
            session_id, topic,
        )
    except Exception:
        logger.exception(
            "track_question_asked_failed: session=%s", session_id,
        )


# ══════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ══════════════════════════════════════════════════════════════════


def _get_session(db: Session, session_id: str) -> Optional[JarvisSession]:
    """Get a JarvisSession by ID (no user scoping — internal use only).

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.

    Returns:
        JarvisSession or None.
    """
    return (
        db.query(JarvisSession)
        .filter(JarvisSession.id == session_id)
        .first()
    )


def _get_session_context(db: Session, session_id: str) -> Dict[str, Any]:
    """Get parsed context_json for a session.

    Args:
        db: SQLAlchemy session.
        session_id: Session ID.

    Returns:
        Parsed context dict (never None, never crashes).
    """
    try:
        session = _get_session(db, session_id)
        if session:
            return _safe_parse_json(session.context_json)
    except Exception:
        logger.exception("_get_session_context_failed: session=%s", session_id)
    return {}


def _get_awareness_namespace(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Get the onboarding_awareness namespace from context.

    Args:
        ctx: Session context dict.

    Returns:
        The awareness namespace dict.
    """
    return ctx.get(AWARENESS_KEY, {})


def _safe_parse_json(raw: Optional[str]) -> Dict[str, Any]:
    """Safely parse a JSON string, returning {} on any failure.

    Args:
        raw: JSON string or None.

    Returns:
        Parsed dict, or empty dict on failure.
    """
    if not raw:
        return {}
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
        return {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge override into base. Override values take precedence.

    For nested dicts, merges recursively. For all other types,
    override replaces base.

    Args:
        base: Base dict.
        override: Override dict (values take precedence).

    Returns:
        Merged dict.
    """
    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ── Default fallback values for each domain ──


def _default_entry_context() -> Dict[str, Any]:
    """Safe defaults for entry context domain."""
    return {
        "entry_source": "unknown",
        "entry_params": {},
        "referrer": "",
        "utm_source": "",
        "entry_timestamp": "",
    }


def _default_variant_awareness() -> Dict[str, Any]:
    """Safe defaults for variant awareness domain."""
    return {
        "selected_variants": [],
        "variant_id": "",
        "variant_name": "",
        "variant_industry": "",
        "variant_tier": "",
        "demo_variant_active": False,
        "variant_source": "",
    }


def _default_channel_awareness() -> Dict[str, Any]:
    """Safe defaults for channel awareness domain."""
    return {
        "current_channel": "chat",
        "channel_history": [],
        "call_status": "",
        "call_duration": 0,
        "chat_message_count": 0,
    }


def _default_funnel_progress() -> Dict[str, Any]:
    """Safe defaults for funnel progress domain."""
    return {
        "detected_stage": "welcome",
        "stage_transitions": [],
        "stage_entered_at": "",
        "time_in_stage": "",
        "concerns_raised": [],
        "questions_asked": [],
        "objections_encountered": [],
    }


def _default_sales_state() -> Dict[str, Any]:
    """Safe defaults for sales state domain."""
    return {
        "industry_selected": False,
        "variants_selected": False,
        "email_verified": False,
        "demo_pack_purchased": False,
        "payment_status": "none",
        "bill_total": 0,
        "handoff_completed": False,
        "roi_calculated": False,
        "competitor_mentioned": False,
    }
