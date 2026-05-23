"""
Jarvis Activity Store — The "Memory" for Non-Agentic Parts.

This is the SINGLE SOURCE OF TRUTH for everything Jarvis needs to know
about that ISN'T handled by an agentic variant. The Activity Store records
every user action, billing event, channel event, system event, and admin
action so Jarvis has AWARENESS of the entire system.

Why this exists:
  - AGENTIC parts (Mini PARWA, PARWA, PARWA High): Jarvis can ASK the
    variant agents directly via variant_bridge. They reason and answer.
  - NON-AGENTIC parts (billing, UI, channels, config, admin actions):
    No agent to ask — the Activity Store IS the answer.

Architecture:
  +----------------------+     +----------------------+
  |   AGENTIC PARTS      |     |  NON-AGENTIC PARTS   |
  |  (variant agents)    |     |  (billing, UI, etc.) |
  |                      |     |                      |
  |  Jarvis ASKS agents  |     |  Events written HERE |
  |  via variant_bridge  |     |  Jarvis READS here   |
  +----------+-----------+     +----------+-----------+
             |                            |
             |     +--------------+       |
             +-----|   JARVIS     |-------+
                   |  AWARENESS   |
                   +--------------+

Event Sources:
  - user_action:    Button clicks, page views, settings changes
  - billing:        Payment failed, subscription created, refund issued
  - channel:        Email bounced, SMS failed, call dropped, webhook received
  - admin:          Upgrade, downgrade, pause service, config change
  - system:         Cron job completed, alert triggered, error logged
  - integration:    API key rotated, webhook configured, third-party connected

Tenant Scoping:
  - Every event has company_id (BC-001)
  - Every event has variant_scope (which variant this relates to)
  - Jarvis reads ONLY events for the tenant's active variants
  - Admin sees everything; tenants see only their scope

Control Boundaries:
  - process_refund:     AGENTIC (variant agent can do this) -> safety_level=approval
  - upgrade/downgrade:  NOT in Jarvis function registry -> human-only
  - pause_ai:           AGENTIC (Jarvis can do this) -> safety_level=confirmation
  - payment_failed:     NOTIFICATION ONLY -> Jarvis sees it, can't fix it
  - email_bounced:      NOTIFICATION ONLY -> Jarvis sees it, can react

BC-001: company_id first parameter, indexed on every table.
BC-008: Graceful degradation - never crash on write failure.
BC-012: All timestamps UTC.
"""

from datetime import datetime, timezone

import uuid

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Integer, Numeric,
    String, Text, Index, ForeignKey,
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# Enum-like value sets (used by CHECK constraints)

_EVENT_SOURCES = (
    "'user_action','billing','channel','admin',"
    "'system','integration','agent_action','unknown'"
)
_EVENT_SEVERITIES = "'info','warning','critical','emergency'"
_EVENT_CATEGORIES = (
    "'ui','subscription','payment','refund','channel_email',"
    "'channel_sms','channel_voice','channel_chat','channel_webhook',"
    "'config','security','integration','cron','agent',"
    "'sla','escalation','quality','training',"
    # New categories for full Jarvis awareness
    "'shadow_mode','dashboard','variant_ops','knowledge_ops',"
    "'onboarding','notification','approval_flow'"
)


class JarvisActivityEvent(Base):
    """The Activity Store - records EVERY action that happens in the system.

    This is what Jarvis reads for AWARENESS of non-agentic parts.

    Key design decisions:
      1. SINGLE TABLE for all event types - no need for 50 separate tables
      2. event_source + event_category + action = unique classification
      3. variant_scope ties events to specific variant instances
      4. actor_type distinguishes who did it (user, system, agent, admin)
      5. context_json holds arbitrary structured data for each event
      6. jarvis_relevant flag - marks events Jarvis should pay attention to
      7. jarvis_control_boundary - what Jarvis can/cannot do about this event

    Example events:
      {source: "user_action", action: "upgrade_clicked", category: "ui",
       actor_type: "user", jarvis_relevant: true,
       jarvis_control_boundary: "notify_only"}

      {source: "billing", action: "payment_failed", category: "payment",
       actor_type: "system", jarvis_relevant: true,
       jarvis_control_boundary: "notify_only"}

      {source: "agent_action", action: "refund_issued", category: "refund",
       actor_type: "agent", jarvis_relevant: true,
       jarvis_control_boundary: "agent_controlled"}
    """

    __tablename__ = "jarvis_activity_events"

    id = Column(String(36), primary_key=True, default=_uuid)

    # Tenant scoping (BC-001)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Variant scoping
    # Which variant instance this event relates to.
    # NULL = applies to all variants (e.g., billing, config changes)
    variant_scope = Column(String(50), nullable=True)
    # mini_parwa, parwa, parwa_high, or NULL (all variants)

    instance_id = Column(String(36), nullable=True)
    # Specific variant instance ID (if applicable)

    # Event classification
    event_source = Column(String(30), nullable=False, default="system")
    # Where did this event come from?
    # user_action, billing, channel, admin, system, integration,
    # agent_action, unknown

    event_category = Column(String(30), nullable=False, default="config")
    # What domain does this event belong to?
    # ui, subscription, payment, refund, channel_email, channel_sms,
    # channel_voice, channel_chat, channel_webhook, config, security,
    # integration, cron, agent, sla, escalation, quality, training

    action = Column(String(100), nullable=False)
    # What happened? e.g., "upgrade_clicked", "payment_failed",
    # "email_bounced", "config_changed", "refund_issued"

    severity = Column(String(15), nullable=False, default="info")
    # How important is this? info, warning, critical, emergency

    # Actor
    actor_id = Column(String(36), nullable=True)
    # Who/what performed the action (user_id, system, agent_id)

    actor_type = Column(String(20), nullable=False, default="system")
    # user, admin, system, agent, api_key, cron

    # Event details
    description = Column(Text, nullable=True)
    # Human-readable description of the event

    context_json = Column(Text, default="{}")
    # Structured context data for this event.
    # e.g. {"page": "/billing", "button": "upgrade", "from_plan": "mini_parwa"}

    old_value = Column(Text, nullable=True)
    # Previous value (for change events)

    new_value = Column(Text, nullable=True)
    # New value (for change events)

    # Related resources
    resource_type = Column(String(50), nullable=True)
    # ticket, subscription, payment, channel, integration, user, etc.

    resource_id = Column(String(36), nullable=True)
    # ID of the affected resource

    # Jarvis awareness metadata
    jarvis_relevant = Column(Boolean, default=True, nullable=False)
    # Should Jarvis pay attention to this event?

    jarvis_control_boundary = Column(String(30), nullable=True, default="notify_only")
    # What can Jarvis do about this?
    # - "notify_only":      Jarvis sees it but can't control it (e.g., payment failed)
    # - "agent_controlled":  Variant agent handles this (e.g., refund)
    # - "jarvis_can_act":    Jarvis can take action (e.g., pause AI)
    # - "human_required":    Only a human can handle this (e.g., upgrade)

    # Session context
    session_id = Column(String(36), nullable=True)
    # Jarvis CC session ID if this event relates to an active session

    # Timestamps
    occurred_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    # When the event actually happened

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    # When this record was created

    __table_args__ = (
        CheckConstraint(
            f"event_source IN ({_EVENT_SOURCES})",
            name="ck_jarvis_act_event_source",
        ),
        CheckConstraint(
            f"severity IN ({_EVENT_SEVERITIES})",
            name="ck_jarvis_act_severity",
        ),
        CheckConstraint(
            f"event_category IN ({_EVENT_CATEGORIES})",
            name="ck_jarvis_act_category",
        ),
        CheckConstraint(
            "jarvis_control_boundary IN "
            "('notify_only','agent_controlled','jarvis_can_act','human_required')",
            name="ck_jarvis_act_control_boundary",
        ),
        CheckConstraint(
            "actor_type IN ('user','admin','system','agent','api_key','cron')",
            name="ck_jarvis_act_actor_type",
        ),
        # High-performance indexes for Jarvis queries
        Index(
            "ix_jarvis_act_comp_created",
            "company_id", "created_at",
        ),
        Index(
            "ix_jarvis_act_comp_source",
            "company_id", "event_source",
        ),
        Index(
            "ix_jarvis_act_comp_category",
            "company_id", "event_category",
        ),
        Index(
            "ix_jarvis_act_comp_relevant",
            "company_id", "jarvis_relevant", "created_at",
        ),
        Index(
            "ix_jarvis_act_comp_variant",
            "company_id", "variant_scope", "created_at",
        ),
        Index(
            "ix_jarvis_act_comp_severity",
            "company_id", "severity", "created_at",
        ),
        Index(
            "ix_jarvis_act_comp_resource",
            "company_id", "resource_type", "resource_id",
        ),
        Index(
            "ix_jarvis_act_comp_control",
            "company_id", "jarvis_control_boundary", "created_at",
        ),
        {"schema": None},
    )
