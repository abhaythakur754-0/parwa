"""
PARWA Analytics Service (Week 9 — Event Tracking & Metrics)

Tracks user interactions, AI responses, and business events
throughout the Jarvis onboarding flow. Provides metrics
for dashboards and reporting.

Event categories:
- message: User messages sent, AI responses generated
- sentiment: Sentiment analysis results
- lead: Lead capture and status changes
- payment: Demo pack purchases, variant payments
- escalation: Escalation triggers and resolutions
- session: Session lifecycle events
- funnel: Onboarding funnel progression

Integrates with:
- jarvis_service (event emission during message flow)
- lead_service (lead events)
- sentiment_engine (sentiment tracking)
- graceful_escalation (escalation events)
"""

from __future__ import annotations

import json
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("analytics_service")


@dataclass
class AnalyticsEvent:
    """A single analytics event."""
    event_id: str
    event_type: str  # e.g., "message_sent", "lead_captured"
    event_category: str  # e.g., "message", "lead", "payment"
    user_id: str
    company_id: str = ""
    session_id: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    source: str = "jarvis_onboarding"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_category": self.event_category,
            "user_id": self.user_id,
            "company_id": self.company_id,
            "session_id": self.session_id,
            "properties": self.properties,
            "timestamp": self.timestamp,
            "source": self.source,
        }


# ── In-memory event store ──────────────────────────────────────────

_events: List[AnalyticsEvent] = []
_event_counter = 0
_lock = threading.Lock()
_max_events = 10000  # Prevent unbounded memory growth


def track_event(
    event_type: str,
    event_category: str,
    user_id: str,
    company_id: str = "",
    session_id: str = "",
    properties: Optional[Dict[str, Any]] = None,
    source: str = "jarvis_onboarding",
) -> AnalyticsEvent:
    """Record an analytics event.

    Args:
        event_type: Specific event name (e.g., "message_sent").
        event_category: Event category (e.g., "message", "lead").
        user_id: User identifier.
        company_id: Company identifier.
        session_id: Session identifier.
        properties: Additional event properties.
        source: Event source.

    Returns:
        AnalyticsEvent that was recorded.
    """
    global _event_counter

    with _lock:
        _event_counter += 1
        event = AnalyticsEvent(
            event_id=f"evt_{_event_counter:06d}",
            event_type=event_type,
            event_category=event_category,
            user_id=user_id,
            company_id=company_id,
            session_id=session_id,
            properties=properties or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
            source=source,
        )
        _events.append(event)

        # Trim old events if over limit
        if len(_events) > _max_events:
            del _events[: len(_events) - _max_events]

    logger.debug(
        "analytics_event",
        event_type=event_type,
        category=event_category,
        user_id=user_id,
        session_id=session_id,
    )
    return event


def get_metrics(
    company_id: str = "",
    session_id: str = "",
    since: Optional[str] = None,
) -> Dict[str, Any]:
    """Get aggregated analytics metrics.

    Args:
        company_id: Filter by company.
        session_id: Filter by session.
        since: ISO timestamp to filter events after.

    Returns:
        Dictionary with aggregated metrics.
    """
    with _lock:
        filtered = _events

        if company_id:
            filtered = [e for e in filtered if e.company_id == company_id]
        if session_id:
            filtered = [e for e in filtered if e.session_id == session_id]
        if since:
            filtered = [e for e in filtered if e.timestamp >= since]

    # Aggregate by category
    by_category: Dict[str, int] = defaultdict(int)
    by_type: Dict[str, int] = defaultdict(int)
    by_user: Dict[str, int] = defaultdict(int)

    for event in filtered:
        by_category[event.event_category] += 1
        by_type[event.event_type] += 1
        by_user[event.user_id] += 1

    # Unique users/sessions
    unique_users = len(set(e.user_id for e in filtered))
    unique_sessions = len(set(e.session_id for e in filtered if e.session_id))

    # Time range
    timestamps = [e.timestamp for e in filtered if e.timestamp]
    time_range = {
        "earliest": min(timestamps) if timestamps else None,
        "latest": max(timestamps) if timestamps else None,
    }

    return {
        "total_events": len(filtered),
        "unique_users": unique_users,
        "unique_sessions": unique_sessions,
        "by_category": dict(by_category),
        "by_type": dict(by_type),
        "by_user": dict(by_user),
        "time_range": time_range,
    }


def get_funnel_metrics() -> Dict[str, Any]:
    """Get onboarding funnel metrics.

    Tracks progression: visit → welcome → discovery → pricing →
    verification → payment → handoff.

    Returns:
        Dictionary with funnel stage counts and conversion rates.
    """
    funnel_stages = {
        "visit": 0,
        "welcome_sent": 0,
        "industry_provided": 0,
        "variants_selected": 0,
        "email_provided": 0,
        "email_verified": 0,
        "demo_pack_purchased": 0,
        "payment_initiated": 0,
        "payment_completed": 0,
        "handoff_completed": 0,
    }

    with _lock:
        for event in _events:
            if event.event_type == "session_created":
                funnel_stages["visit"] += 1
            elif event.event_type == "welcome_sent":
                funnel_stages["welcome_sent"] += 1
            elif event.event_type == "industry_provided":
                funnel_stages["industry_provided"] += 1
            elif event.event_type == "variants_selected":
                funnel_stages["variants_selected"] += 1
            elif event.event_type == "email_provided":
                funnel_stages["email_provided"] += 1
            elif event.event_type == "email_verified":
                funnel_stages["email_verified"] += 1
            elif event.event_type == "demo_pack_purchased":
                funnel_stages["demo_pack_purchased"] += 1
            elif event.event_type == "payment_initiated":
                funnel_stages["payment_initiated"] += 1
            elif event.event_type == "payment_completed":
                funnel_stages["payment_completed"] += 1
            elif event.event_type == "handoff_completed":
                funnel_stages["handoff_completed"] += 1

    # Calculate conversion rates
    visits = max(funnel_stages["visit"], 1)
    conversion_rates = {}
    for stage, count in funnel_stages.items():
        if stage == "visit":
            conversion_rates[stage] = 1.0
        else:
            conversion_rates[stage] = round(count / visits, 4)

    return {
        "funnel_stages": funnel_stages,
        "conversion_rates": conversion_rates,
    }


def get_sentiment_metrics(session_id: str = "") -> Dict[str, Any]:
    """Get sentiment analysis metrics.

    Args:
        session_id: Filter by session.

    Returns:
        Dictionary with sentiment statistics.
    """
    sentiment_events = []
    with _lock:
        for event in _events:
            if event.event_category == "sentiment":
                if not session_id or event.session_id == session_id:
                    sentiment_events.append(event)

    if not sentiment_events:
        return {"total_analyses": 0}

    frustration_scores = [
        e.properties.get("frustration_score", 0)
        for e in sentiment_events
        if "frustration_score" in e.properties
    ]

    emotions = [
        e.properties.get("emotion", "neutral")
        for e in sentiment_events
        if "emotion" in e.properties
    ]

    tone_counts: Dict[str, int] = defaultdict(int)
    for e in sentiment_events:
        tone = e.properties.get("tone_recommendation", "standard")
        tone_counts[tone] += 1

    escalation_count = sum(
        1 for e in sentiment_events
        if e.properties.get("escalation_triggered", False)
    )

    avg_frustration = (
        sum(frustration_scores) / len(frustration_scores)
        if frustration_scores
        else 0.0
    )

    return {
        "total_analyses": len(sentiment_events),
        "average_frustration": round(avg_frustration, 2),
        "max_frustration": max(frustration_scores) if frustration_scores else 0,
        "min_frustration": min(frustration_scores) if frustration_scores else 0,
        "emotion_distribution": _count_items(emotions),
        "tone_distribution": dict(tone_counts),
        "escalation_count": escalation_count,
        "escalation_rate": round(
            escalation_count / max(len(sentiment_events), 1), 4
        ),
    }


def get_recent_events(
    limit: int = 100,
    event_category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get recent analytics events.

    Args:
        limit: Max events to return.
        event_category: Filter by category.

    Returns:
        List of event dictionaries.
    """
    with _lock:
        filtered = _events
        if event_category:
            filtered = [e for e in filtered if e.event_category == event_category]

        recent = filtered[-limit:]
        return [e.to_dict() for e in recent]


# ── Helper ────────────────────────────────────────────────────────


def _count_items(items: List[str]) -> Dict[str, int]:
    """Count occurrences of items in a list."""
    counts: Dict[str, int] = defaultdict(int)
    for item in items:
        counts[item] += 1
    return dict(counts)
