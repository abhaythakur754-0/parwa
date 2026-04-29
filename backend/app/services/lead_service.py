"""
PARWA Lead Service (Week 9 — Lead Capture & Management)

Captures and manages sales leads from onboarding conversations.
Tracks lead lifecycle: identified → contacted → qualified → converted.

Lead capture triggers:
- Business email provided (via OTP verification)
- Industry specified
- Variants selected (buying intent)
- Demo pack purchased (high intent)
- Payment completed (conversion)

Integrates with:
- Jarvis onboarding flow (session context)
- Analytics service (lead events)
- Email service (follow-up notifications)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("lead_service")


@dataclass
class LeadData:
    """Represents a captured lead."""
    lead_id: str
    user_id: str
    company_id: str
    session_id: str
    business_email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    selected_variants: List[Dict[str, Any]] = field(default_factory=list)
    lead_source: str = "jarvis_onboarding"
    lead_status: str = "identified"
    email_verified: bool = False
    demo_pack_purchased: bool = False
    payment_completed: bool = False
    estimated_monthly_value: float = 0.0
    conversation_stage: str = "welcome"
    entry_source: str = "direct"
    entry_params: Dict[str, Any] = field(default_factory=dict)
    sentiment_summary: Optional[Dict[str, Any]] = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lead_id": self.lead_id,
            "user_id": self.user_id,
            "company_id": self.company_id,
            "session_id": self.session_id,
            "business_email": self.business_email,
            "full_name": self.full_name,
            "phone": self.phone,
            "industry": self.industry,
            "selected_variants": self.selected_variants,
            "lead_source": self.lead_source,
            "lead_status": self.lead_status,
            "email_verified": self.email_verified,
            "demo_pack_purchased": self.demo_pack_purchased,
            "payment_completed": self.payment_completed,
            "estimated_monthly_value": self.estimated_monthly_value,
            "conversation_stage": self.conversation_stage,
            "entry_source": self.entry_source,
            "sentiment_summary": self.sentiment_summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# In-memory lead store (production would use database)
_leads: Dict[str, LeadData] = {}
_user_to_lead: Dict[str, str] = {}  # user_id → lead_id


def capture_lead(
    session_id: str,
    user_id: str,
    company_id: Optional[str] = None,
    session_context: Optional[Dict[str, Any]] = None,
    sentiment_data: Optional[Dict[str, Any]] = None,
) -> LeadData:
    """Capture or update a lead from session context.

    Called by jarvis_service.send_message() after each interaction.
    Extracts lead signals from the session context and creates/updates
    a lead record.

    Args:
        session_id: Current Jarvis session ID.
        user_id: User identifier.
        company_id: Company identifier (may be None for onboarding).
        session_context: Current session context JSON.
        sentiment_data: Latest sentiment analysis data.

    Returns:
        LeadData with captured lead information.
    """
    ctx = session_context or {}
    now = datetime.now(timezone.utc)

    # Check if lead already exists for this user
    existing_lead_id = _user_to_lead.get(user_id)
    if existing_lead_id and existing_lead_id in _leads:
        lead = _leads[existing_lead_id]
        _update_lead_from_context(lead, ctx, sentiment_data)
        lead.updated_at = now.isoformat()
        logger.info(
            "lead_updated",
            lead_id=lead.lead_id,
            user_id=user_id,
            status=lead.lead_status,
        )
        return lead

    # Create new lead
    lead_id = f"lead_{user_id[:12]}_{now.strftime('%Y%m%d%H%M%S')}"

    lead = LeadData(
        lead_id=lead_id,
        user_id=user_id,
        company_id=company_id or "",
        session_id=session_id,
        business_email=ctx.get("business_email"),
        industry=ctx.get("industry"),
        selected_variants=ctx.get("selected_variants", []),
        email_verified=ctx.get("email_verified", False),
        conversation_stage=ctx.get("detected_stage", "welcome"),
        entry_source=ctx.get("entry_source", "direct"),
        entry_params=ctx.get("entry_params", {}),
        sentiment_summary=_build_sentiment_summary(sentiment_data),
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )

    # Determine initial lead status
    lead.lead_status = _determine_lead_status(ctx)

    # Calculate estimated monthly value
    lead.estimated_monthly_value = _estimate_monthly_value(
        ctx.get("selected_variants", []),
    )

    _leads[lead_id] = lead
    _user_to_lead[user_id] = lead_id

    logger.info(
        "lead_captured",
        lead_id=lead_id,
        user_id=user_id,
        email=lead.business_email,
        industry=lead.industry,
        status=lead.lead_status,
        source=lead.lead_source,
    )

    return lead


def get_lead(user_id: str) -> Optional[LeadData]:
    """Get lead data for a user."""
    lead_id = _user_to_lead.get(user_id)
    if lead_id and lead_id in _leads:
        return _leads[lead_id]
    return None


def update_lead_status(
        user_id: str,
        status: str,
        **kwargs) -> Optional[LeadData]:
    """Update a lead's status and optional fields."""
    lead = get_lead(user_id)
    if not lead:
        return None

    lead.lead_status = status
    lead.updated_at = datetime.now(timezone.utc).isoformat()

    if "email_verified" in kwargs:
        lead.email_verified = kwargs["email_verified"]
    if "demo_pack_purchased" in kwargs:
        lead.demo_pack_purchased = kwargs["demo_pack_purchased"]
    if "payment_completed" in kwargs:
        lead.payment_completed = kwargs["payment_completed"]
    if "conversation_stage" in kwargs:
        lead.conversation_stage = kwargs["conversation_stage"]
    if "selected_variants" in kwargs:
        lead.selected_variants = kwargs["selected_variants"]
    if "business_email" in kwargs:
        lead.business_email = kwargs["business_email"]
    if "industry" in kwargs:
        lead.industry = kwargs["industry"]

    # Recalculate value and status
    lead.estimated_monthly_value = _estimate_monthly_value(
        lead.selected_variants)
    if status not in ("converted", "lost"):
        lead.lead_status = _determine_lead_status({
            "business_email": lead.business_email,
            "industry": lead.industry,
            "selected_variants": lead.selected_variants,
            "email_verified": lead.email_verified,
            "payment_completed": lead.payment_completed,
        })

    _leads[lead.lead_id] = lead
    return lead


def get_all_leads() -> List[LeadData]:
    """Get all captured leads."""
    return list(_leads.values())


def get_leads_by_status(status: str) -> List[LeadData]:
    """Get leads filtered by status."""
    return [l for l in _leads.values() if l.lead_status == status]


def get_lead_stats() -> Dict[str, Any]:
    """Get aggregate lead statistics."""
    all_leads = list(_leads.values())
    total = len(all_leads)

    by_status = {}
    for lead in all_leads:
        by_status[lead.lead_status] = by_status.get(lead.lead_status, 0) + 1

    by_industry = {}
    for lead in all_leads:
        if lead.industry:
            by_industry[lead.industry] = by_industry.get(lead.industry, 0) + 1

    by_source = {}
    for lead in all_leads:
        by_source[lead.entry_source] = by_source.get(lead.entry_source, 0) + 1

    verified_count = sum(1 for l in all_leads if l.email_verified)
    demo_count = sum(1 for l in all_leads if l.demo_pack_purchased)
    converted_count = sum(1 for l in all_leads if l.payment_completed)
    total_estimated_value = sum(l.estimated_monthly_value for l in all_leads)

    return {
        "total_leads": total,
        "by_status": by_status,
        "by_industry": by_industry,
        "by_source": by_source,
        "emails_verified": verified_count,
        "demo_packs_purchased": demo_count,
        "payments_completed": converted_count,
        "total_estimated_monthly_value": round(total_estimated_value, 2),
    }


# ── Internal Helpers ─────────────────────────────────────────────


def _update_lead_from_context(
    lead: LeadData,
    ctx: Dict[str, Any],
    sentiment_data: Optional[Dict[str, Any]],
) -> None:
    """Update lead fields from latest session context."""
    if ctx.get("business_email"):
        lead.business_email = ctx["business_email"]
    if ctx.get("industry"):
        lead.industry = ctx["industry"]
    if ctx.get("selected_variants"):
        lead.selected_variants = ctx["selected_variants"]
    if ctx.get("email_verified"):
        lead.email_verified = ctx["email_verified"]
    if ctx.get("detected_stage"):
        lead.conversation_stage = ctx["detected_stage"]
    if sentiment_data:
        lead.sentiment_summary = _build_sentiment_summary(sentiment_data)


def _determine_lead_status(ctx: Dict[str, Any]) -> str:
    """Determine lead status from context signals."""
    if ctx.get("payment_completed"):
        return "converted"
    if ctx.get("payment_status") == "completed":
        return "converted"
    if ctx.get("pack_type") == "demo":
        return "contacted"
    if ctx.get("selected_variants"):
        return "qualified"
    if ctx.get("business_email") and ctx.get("email_verified"):
        return "contacted"
    if ctx.get("business_email"):
        return "identified"
    if ctx.get("industry"):
        return "identified"
    return "identified"


def _estimate_monthly_value(variants: List[Dict[str, Any]]) -> float:
    """Estimate monthly value from selected variants."""
    total = 0.0
    for v in variants:
        price = v.get("price", 0)
        quantity = v.get("quantity", 1)
        total += price * quantity
    return round(total, 2)


def _build_sentiment_summary(
    sentiment_data: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Build a compact sentiment summary for lead record."""
    if not sentiment_data:
        return None
    return {
        "frustration_score": sentiment_data.get("frustration_score", 0),
        "emotion": sentiment_data.get("emotion", "neutral"),
        "urgency": sentiment_data.get("urgency_level", "low"),
        "tone": sentiment_data.get("tone_recommendation", "standard"),
        "trend": sentiment_data.get("conversation_trend", "stable"),
    }
