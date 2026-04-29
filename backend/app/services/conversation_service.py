"""
PARWA Conversation Service (Week 9 — Conversation Management)

Manages conversation lifecycle and context for AI interactions.
Provides conversation tracking, context retrieval, and message history
management. Bridges Jarvis sessions with the broader AI pipeline.

Features:
- Create/resume conversations
- Track conversation messages with metadata
- Retrieve conversation context for AI prompt building
- Manage conversation analytics (turn count, duration, sentiment trend)
- Multi-session support (onboarding → customer_care handoff)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.logger import get_logger

logger = get_logger("conversation_service")


@dataclass
class ConversationContext:
    """Rich context object for a conversation session."""
    conversation_id: str
    user_id: str
    company_id: Optional[str]
    session_type: str = "onboarding"
    turn_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    industry: Optional[str] = None
    business_email: Optional[str] = None
    email_verified: bool = False
    detected_stage: str = "welcome"
    selected_variants: List[Dict[str, Any]] = field(default_factory=list)
    entry_source: str = "direct"
    sentiment_trend: str = "stable"
    last_sentiment: Optional[Dict[str, Any]] = None
    pages_visited: List[str] = field(default_factory=list)
    concerns_raised: List[str] = field(default_factory=list)
    custom_data: Dict[str, Any] = field(default_factory=dict)

    def to_prompt_dict(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for AI prompt injection."""
        return {
            "conversation_id": self.conversation_id,
            "turn_count": self.turn_count,
            "industry": self.industry,
            "business_email": self.business_email,
            "email_verified": self.email_verified,
            "detected_stage": self.detected_stage,
            "selected_variants": self.selected_variants,
            "entry_source": self.entry_source,
            "sentiment_trend": self.sentiment_trend,
            "last_sentiment": self.last_sentiment,
            "pages_visited": self.pages_visited,
            "concerns_raised": self.concerns_raised,
        }


def create_conversation(
    conversation_id: str,
    user_id: str,
    company_id: Optional[str] = None,
    session_type: str = "onboarding",
) -> ConversationContext:
    """Create a new conversation context.

    Args:
        conversation_id: Unique conversation identifier.
        user_id: User identifier.
        company_id: Company identifier.
        session_type: onboarding or customer_care.

    Returns:
        ConversationContext with initialized fields.
    """
    now = datetime.now(timezone.utc).isoformat()
    ctx = ConversationContext(
        conversation_id=conversation_id,
        user_id=user_id,
        company_id=company_id,
        session_type=session_type,
        turn_count=0,
        created_at=now,
        updated_at=now,
    )
    logger.info(
        "conversation_created",
        conversation_id=conversation_id,
        user_id=user_id,
        type=session_type,
    )
    return ctx


def get_conversation_context(
    conversation_id: str,
    db: Optional[Session] = None,
    session_context: Optional[Dict[str, Any]] = None,
) -> ConversationContext:
    """Build a ConversationContext from a Jarvis session.

    Reconstructs a rich context object from the session's context_json.
    If db is provided, also counts message history for turn count.

    Args:
        conversation_id: Session/conversation ID.
        db: Optional SQLAlchemy session for message counting.
        session_context: Parsed session context JSON.

    Returns:
        ConversationContext with all available data.
    """
    ctx = session_context or {}

    context = ConversationContext(
        conversation_id=conversation_id,
        user_id=ctx.get("user_id", ""),
        company_id=ctx.get("company_id"),
        session_type=ctx.get("type", "onboarding"),
        turn_count=ctx.get("total_message_count", 0),
        created_at=ctx.get("created_at", ""),
        updated_at=ctx.get("updated_at", ""),
        industry=ctx.get("industry"),
        business_email=ctx.get("business_email"),
        email_verified=ctx.get("email_verified", False),
        detected_stage=ctx.get("detected_stage", "welcome"),
        selected_variants=ctx.get("selected_variants", []),
        entry_source=ctx.get("entry_source", "direct"),
        sentiment_trend=ctx.get("last_sentiment", {}).get("trend", "stable"),
        last_sentiment=ctx.get("last_sentiment"),
        pages_visited=ctx.get("pages_visited", []),
        concerns_raised=ctx.get("concerns_raised", []),
        custom_data={
            k: v for k, v in ctx.items()
            if k not in (
                "user_id", "company_id", "type", "industry",
                "business_email", "email_verified", "detected_stage",
                "selected_variants", "entry_source", "pages_visited",
                "concerns_raised", "last_sentiment",
            )
        },
    )

    # Get turn count from DB if available
    if db:
        try:
            from database.models.jarvis import JarvisMessage

            count = (
                db.query(JarvisMessage)
                .filter(
                    JarvisMessage.session_id == conversation_id,
                    JarvisMessage.role == "user",
                )
                .count()
            )
            context.turn_count = count
        except Exception:
            pass

    return context


def add_message_to_context(
    context: ConversationContext,
    role: str,
    content: str,
    sentiment_data: Optional[Dict[str, Any]] = None,
) -> ConversationContext:
    """Update context with a new message.

    Increments turn count, updates sentiment data, and updates timestamp.

    Args:
        context: Current ConversationContext.
        role: Message role (user, jarvis, system).
        content: Message content.
        sentiment_data: Optional sentiment analysis result.

    Returns:
        Updated ConversationContext.
    """
    if role == "user":
        context.turn_count += 1

    if sentiment_data:
        context.last_sentiment = {
            "frustration_score": sentiment_data.get("frustration_score", 0),
            "emotion": sentiment_data.get("emotion", "neutral"),
            "urgency": sentiment_data.get("urgency_level", "low"),
            "tone": sentiment_data.get("tone_recommendation", "standard"),
        }

    context.updated_at = datetime.now(timezone.utc).isoformat()
    return context


def update_conversation_context(
    context: ConversationContext,
    updates: Dict[str, Any],
) -> ConversationContext:
    """Apply partial updates to a conversation context.

    Args:
        context: Current ConversationContext.
        updates: Dictionary of fields to update.

    Returns:
        Updated ConversationContext.
    """
    for key, value in updates.items():
        if value is None:
            continue
        if hasattr(context, key):
            setattr(context, key, value)

    context.updated_at = datetime.now(timezone.utc).isoformat()
    return context


def get_conversation_history(
    db: Session,
    conversation_id: str,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, str]]:
    """Get conversation message history.

    Args:
        db: SQLAlchemy session.
        conversation_id: Session ID.
        limit: Max messages to return.
        offset: Pagination offset.

    Returns:
        List of {role, content} dicts in chronological order.
    """
    try:
        from database.models.jarvis import JarvisMessage

        messages = (
            db.query(JarvisMessage)
            .filter(JarvisMessage.session_id == conversation_id)
            .order_by(JarvisMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [{"role": m.role, "content": m.content} for m in messages]
    except Exception as exc:
        logger.warning("conversation_history_error", error=str(exc))
        return []


def build_conversation_summary(context: ConversationContext) -> Dict[str, Any]:
    """Build a summary of the conversation for analytics.

    Args:
        context: ConversationContext with all data.

    Returns:
        Summary dictionary with key metrics and signals.
    """
    return {
        "conversation_id": context.conversation_id,
        "user_id": context.user_id,
        "session_type": context.session_type,
        "turn_count": context.turn_count,
        "industry": context.industry,
        "has_email": bool(context.business_email),
        "email_verified": context.email_verified,
        "current_stage": context.detected_stage,
        "variants_selected": len(context.selected_variants),
        "entry_source": context.entry_source,
        "sentiment_trend": context.sentiment_trend,
        "last_frustration": (
            context.last_sentiment.get("frustration_score", 0)
            if context.last_sentiment else 0
        ),
        "concerns_count": len(context.concerns_raised),
        "pages_explored": len(context.pages_visited),
        "duration_minutes": _calculate_duration(context.created_at),
    }


def _calculate_duration(created_at: str) -> float:
    """Calculate conversation duration in minutes."""
    if not created_at:
        return 0.0
    try:
        start = datetime.fromisoformat(created_at)
        now = datetime.now(timezone.utc)
        return round((now - start).total_seconds() / 60, 1)
    except (ValueError, TypeError):
        return 0.0
