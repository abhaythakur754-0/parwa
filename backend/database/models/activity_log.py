"""
PARWA Activity Log Model — Jarvis Awareness Store for Non-Agentic Parts

This is the FOUNDATION of Jarvis's awareness for everything that is NOT
handled by the variant agents (Mini PARWA, PARWA, PARWA High).

Architecture Decision (confirmed with product owner):
  - AGENTIC parts:     Jarvis asks variant agents directly -> they reason & answer
  - NON-AGENTIC parts: This Activity Log records EVERY action -> Jarvis reads it
                       for awareness

The Activity Log captures:
  - User actions: button clicks, page views, form submissions, navigation
  - Billing events: subscription changes, payment attempts, invoice generated
  - System events: API calls, webhook deliveries, cron job runs, errors
  - Channel events: emails sent/received, SMS sent, calls made/missed
  - Workflow events: ticket created/updated/resolved, assignments, escalations
  - Configuration: settings changed, integrations toggled, rules modified

Jarvis reads this log to gain AWARENESS of non-agentic parts. It does NOT
control these parts directly (that would make it "like a normal chatbot").
Instead, it KNOWS what happened and can REACT by delegating to variant agents
or notifying humans.

Tenant Scoping (BC-001):
  Every activity log entry is scoped to company_id. If a tenant only has
  Mini PARWA, Jarvis only sees Mini PARWA's activity stream. This is
  enforced at the query level — no cross-tenant awareness is possible.

Control vs Awareness Boundary:
  - Jarvis CAN: refund, respond to tickets, make calls (agent-level actions)
  - Jarvis CANNOT: upgrade/downgrade subscription, change billing (human-required)
  - Jarvis SHOULD: be AWARE of everything so it can react appropriately

Design Decisions:
  - JSON details_json column for flexible, schema-free event data
  - actor_type distinguishes who caused the action (user, system, agent, jarvis)
  - category + action provide structured querying without needing to parse details
  - session_id links to jarvis_sessions when the action happened during a CC session
  - entity_type + entity_id provide polymorphic references to affected objects
  - TTL-based pruning prevents unbounded growth
  - Indexed for fast querying by company_id, category, entity, and timestamp

BC-001: company_id first parameter, indexed on every table.
BC-008: Graceful degradation — null-safe columns.
BC-012: All timestamps UTC.
"""

from datetime import datetime, timezone

import uuid

from sqlalchemy import (
    Column, DateTime, Integer, String, Text, Index, CheckConstraint,
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enum-like value sets (used by CHECK constraints) ────────────

_ACTOR_TYPES = "'user','system','agent','jarvis','cron','webhook','api'"
_CATEGORIES = (
    "'user_action','billing','system','channel','workflow',"
    "'configuration','security','integration','notification','training'"
)


class ActivityLog(Base):
    """Universal activity log for non-agentic awareness.

    Every action in the system that is NOT handled by a variant agent
    should be recorded here. This gives Jarvis full awareness of what
    is happening in the tenant's world, without needing to hardcode
    500+ awareness functions.

    Jarvis reads this log to answer questions like:
      - "Did the user click the upgrade button?" -> YES, at 14:32
      - "What billing events happened today?" -> 3 payments, 1 refund
      - "Has anyone changed the SLA config recently?" -> YES, admin at 10:15
      - "What pages did the user visit in the last hour?" -> Dashboard, Tickets, Settings

    This is NOT a chatbot query tool. This is a structured event store
    that Jarvis reads passively for awareness. When Jarvis needs to
    ACT, it delegates to the appropriate variant agent via variant_bridge.
    """

    __tablename__ = "activity_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        nullable=False, index=True,
    )

    # ── Who caused this action ──
    actor_type = Column(String(20), nullable=False, default="system")
    actor_id = Column(String(36), nullable=True)
    actor_name = Column(String(255), nullable=True)

    # ── What happened ──
    category = Column(String(30), nullable=False)
    action = Column(String(100), nullable=False)
    label = Column(String(255), nullable=True)

    # ── What was affected ──
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String(36), nullable=True)

    # ── Context ──
    session_id = Column(String(36), nullable=True)
    route = Column(String(500), nullable=True)
    method = Column(String(10), nullable=True)

    # ── Structured details ──
    details_json = Column(Text, default="{}")

    # ── Importance ──
    importance = Column(String(10), nullable=False, default="info")

    # ── Timestamps ──
    occurred_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Pruning ──
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"actor_type IN ({_ACTOR_TYPES})",
            name="ck_activity_actor_type",
        ),
        CheckConstraint(
            f"category IN ({_CATEGORIES})",
            name="ck_activity_category",
        ),
        CheckConstraint(
            f"importance IN ('info','low','medium','high','critical')",
            name="ck_activity_importance",
        ),
        Index(
            "ix_activity_comp_created",
            "company_id", "created_at",
        ),
        Index(
            "ix_activity_comp_category",
            "company_id", "category",
        ),
        Index(
            "ix_activity_comp_entity",
            "company_id", "entity_type", "entity_id",
        ),
        Index(
            "ix_activity_comp_importance",
            "company_id", "importance",
        ),
        Index(
            "ix_activity_comp_occurred",
            "company_id", "occurred_at",
        ),
        Index(
            "ix_activity_session",
            "session_id",
        ),
        Index(
            "ix_activity_actor",
            "company_id", "actor_type", "actor_id",
        ),
        {"schema": None},
    )

    def __repr__(self) -> str:
        return (
            f"<ActivityLog id={self.id!r} company={self.company_id!r} "
            f"category={self.category!r} action={self.action!r} "
            f"importance={self.importance!r}>"
        )


# ── Importance-based TTL defaults (days) ─────────────────────

IMPORTANCE_TTL_DAYS = {
    "critical": None,   # Never expire (compliance)
    "high": 365,        # 1 year
    "medium": 90,       # 90 days
    "low": 30,          # 30 days
    "info": 7,          # 7 days
}

# ── Category-specific importance defaults ─────────────────────

CATEGORY_IMPORTANCE_DEFAULTS = {
    "billing": "high",
    "security": "critical",
    "configuration": "high",
    "workflow": "medium",
    "channel": "medium",
    "integration": "medium",
    "system": "low",
    "notification": "low",
    "training": "medium",
    "user_action": "low",
}
