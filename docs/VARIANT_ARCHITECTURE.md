# Parwa Variant System Architecture

> **Status**: Architecture Document — Pre-Implementation  
> **Last Updated**: 2026-04-23  
> **Scope**: Variant naming, inheritance, smart routing, multi-instance hiring, utilization, overflow, AI pipeline awareness, cross-system connections, end-to-end data flows

---

## Table of Contents

1. [Overview](#1-overview)
2. [Canonical Naming](#2-canonical-naming)
3. [Variant Inheritance Model](#3-variant-inheritance-model)
4. [Multi-Variant Hiring & Per-Instance Tracking](#4-multi-variant-hiring--per-instance-tracking)
5. [Smart Routing V2 with Overflow Chain](#5-smart-routing-v2-with-overflow-chain)
6. [Limit Overflow Engine](#6-limit-overflow-engine)
7. [Utilization Tracking API](#7-utilization-tracking-api)
8. [Industry Add-Ons (Per-Instance)](#8-industry-add-ons-per-instance)
9. [Variant-Aware AI Pipeline](#9-variant-aware-ai-pipeline)
10. [Upgrade / Downgrade Flows](#10-upgrade--downgrade-flows)
11. [Database Schema Changes](#11-database-schema-changes)
12. [Naming Migration Plan](#12-naming-migration-plan)
13. [Implementation Roadmap](#13-implementation-roadmap)
14. [Cross-System Connections](#14-cross-system-connections)
15. [Data Flow: End-to-End Ticket Journey](#15-data-flow-end-to-end-ticket-journey)

---

## 1. Overview

Parwa is a multi-product SaaS customer care platform with three core product variants. The Variant System is the backbone that determines feature availability, pricing, routing behavior, AI processing depth, and capacity limits for every company on the platform.

This document captures the complete architecture for the Variant System including naming conventions, inheritance relationships, smart routing with overflow, multi-instance hiring, utilization tracking, and the integration with the AI pipeline.

### Current State vs. Target State

| Aspect | Current State | Target State |
|--------|--------------|--------------|
| Variant Names | `starter`/`growth`/`high` (billing), `mini_parwa`/`parwa`/`parwa_high` (orchestration) | Unified: `mini_parwa`/`parwa`/`high_parwa` everywhere |
| Instance Model | Single subscription per company | Multiple instances per company (same or different types) |
| Routing | Basic least-loaded / round-robin | Smart routing with overflow chain (same type → higher → never down) |
| Overflow | No overflow logic — hard block on limit | Overflow to higher variant instances; suggest purchase when all full |
| Utilization | Per-company aggregate | Per-instance + per-variant + company-wide with visual indicators |
| AI Pipeline | `variant_type` defaults to `"parwa"`, no variant-specific behavior | Variant-aware prompts, RAG depth, confidence thresholds, guardrails |
| Industry Add-ons | Per-company | Per-instance (cleaner with multi-instance) |

---

## 2. Canonical Naming

### 2.1 The Three Core Variants

| Code Name | Display Name | Monthly Price | Yearly Price |
|-----------|-------------|---------------|--------------|
| `mini_parwa` | Mini Parwa | $999 | $9,590 |
| `parwa` | Parwa | $2,499 | $23,990 |
| `high_parwa` | High Parwa | $3,999 | $38,390 |

### 2.2 Naming Rules

- **Code-level** (enums, DB columns, API fields): Always use `mini_parwa`, `parwa`, `high_parwa`
- **Display-level** (UI, emails, invoices): Use "Mini Parwa", "Parwa", "High Parwa"
- **Paddle price IDs**: `price_mini_parwa_monthly`, `price_parwa_monthly`, `price_high_parwa_monthly`
- **Logging**: Use code names for structured logs (`variant=mini_parwa`)

### 2.3 Naming Migration (Critical Fix)

The current codebase has a naming mismatch that MUST be resolved:

| System | Current Values | Target Values |
|--------|---------------|---------------|
| `billing/schemas.py` — `VariantType` enum | `STARTER="starter"`, `GROWTH="growth"`, `HIGH="high"` | `MINI_PARWA="mini_parwa"`, `PARWA="parwa"`, `HIGH_PARWA="high_parwa"` |
| `billing/schemas.py` — `VARIANT_LIMITS` dict | Keys: `VariantType.STARTER`, etc. | Keys: `VariantType.MINI_PARWA`, etc. |
| `variant_limit_service.py` — `_HARDCODED_LIMITS` | `"starter"`, `"growth"`, `"high"` | `"mini_parwa"`, `"parwa"`, `"high_parwa"` |
| `variant_orchestration_service.py` — `VARIANT_PRIORITY` | `"parwa_high": 3` | `"high_parwa": 3` |
| `ai_pipeline.py` — `PipelineContext.variant_type` | Default: `"parwa"` | Default: `"parwa"` (correct, no change needed) |

**Migration approach**: See [Section 12 — Naming Migration Plan](#12-naming-migration-plan).

---

## 3. Variant Inheritance Model

### 3.1 Inheritance Chain

```
Mini Parwa  ⊂  Parwa  ⊂  High Parwa
```

This means:
- **Mini Parwa** has the base feature set (the "core" Parwa experience)
- **Parwa** inherits all Mini Parwa features AND adds more capabilities
- **High Parwa** inherits all Parwa features AND adds the premium tier

### 3.2 Feature Inheritance Matrix

| Feature | Mini Parwa | Parwa | High Parwa |
|---------|-----------|-------|------------|
| **Monthly Tickets** | 2,000 | 5,000 | 15,000 |
| **AI Agents** | 1 | 3 | 5 |
| **Team Members** | 3 | 10 | 25 |
| **Voice Slots** | 0 | 2 | 5 |
| **KB Documents** | 100 | 500 | 2,000 |
| **Basic AI Pipeline** | Yes | Yes | Yes |
| **Smart Routing** | Basic | Standard | Priority |
| **RAG Depth** | Shallow (top-3) | Medium (top-5) | Deep (top-10 + rerank) |
| **AI Model Tier** | Light only | Light + Medium | Light + Medium + Heavy |
| **Confidence Threshold** | 60% | 70% | 80% |
| **Custom System Prompts** | No | Yes | Yes + Brand Voice |
| **Industry Add-ons** | Yes (per-instance) | Yes (per-instance) | Yes (per-instance) |
| **API Access** | Read-only | Read + Write | Full (Read + Write + Webhooks) |
| **Analytics** | Basic dashboard | Advanced + Export | Advanced + Export + Custom |
| **Priority Support** | No | Standard | Dedicated CSM |
| **SLA** | 99.5% | 99.9% | 99.99% |
| **Custom Guardrails** | Default only | Custom rules | Custom rules + AI-generated |

### 3.3 Inheritance Configuration (Code)

```python
# backend/app/config/variant_inheritance.py

VARIANT_INHERITANCE = {
    "mini_parwa": {
        "inherits_from": None,  # Base tier
        "features": [
            "basic_ai_pipeline",
            "ticket_management",
            "kb_search",
            "industry_addons",
            "basic_analytics",
            "api_readonly",
        ],
    },
    "parwa": {
        "inherits_from": "mini_parwa",
        "additional_features": [
            "smart_routing_standard",
            "rag_medium_depth",
            "ai_model_medium",
            "custom_system_prompts",
            "brand_voice",
            "api_readwrite",
            "advanced_analytics",
            "standard_support",
        ],
    },
    "high_parwa": {
        "inherits_from": "parwa",
        "additional_features": [
            "smart_routing_priority",
            "rag_deep_rerank",
            "ai_model_heavy",
            "custom_guardrails_ai",
            "custom_guardrails_rules",
            "api_full_webhooks",
            "custom_analytics",
            "dedicated_csm",
            "premium_sla",
            "confidence_threshold_high",
        ],
    },
}

def get_variant_features(variant_type: str) -> set[str]:
    """Resolve full feature set by walking inheritance chain."""
    features = set()
    current = variant_type
    while current:
        config = VARIANT_INHERITANCE[current]
        if "features" in config:
            features.update(config["features"])
        if "additional_features" in config:
            features.update(config["additional_features"])
        current = config.get("inherits_from")
    return features
```

### 3.4 Feature Gating Usage

```python
# Check if a variant has a feature
from app.config.variant_inheritance import get_variant_features

features = get_variant_features("parwa")
# Returns: {basic_ai_pipeline, ticket_management, kb_search, industry_addons,
#           basic_analytics, api_readonly, smart_routing_standard, rag_medium_depth,
#           ai_model_medium, custom_system_prompts, brand_voice, api_readwrite,
#           advanced_analytics, standard_support}

if "voice_slots" in features:
    # Allow voice channel
```

---

## 4. Multi-Variant Hiring & Per-Instance Tracking

### 4.1 Concept

A company can hire **multiple instances** of the same or different variants. Each instance is a separate charge and is tracked independently.

**Examples:**
- 2x Mini Parwa = $999 × 2 = $1,998/month
- 1x Mini Parwa + 1x Parwa = $999 + $2,499 = $3,498/month
- 1x Parwa + 1x High Parwa = $2,499 + $3,999 = $6,498/month
- 3x High Parwa = $3,999 × 3 = $11,997/month

### 4.2 Instance Model

Each purchased variant creates a **VariantInstance** record with its own:

- Unique `instance_id`
- `variant_type` (mini_parwa / parwa / high_parwa)
- `instance_name` (user-assigned, e.g., "US Support Team", "EU Escalation")
- `status` (active / suspended / cancelled)
- Own capacity counters (tickets used, active tickets)
- Own industry add-ons
- Own channel assignments (optional)

### 4.3 Instance Lifecycle

```
[Created] ──→ [Active] ──→ [Suspended] ──→ [Cancelled]
                  │                              │
                  │         (re-activate)        │
                  ←──────────────────────────────←
                  │
                  └──→ [Downgrade Scheduled] ──→ [Downgraded at Period End]
```

- **Create**: When a company purchases a new variant instance
- **Active**: Processing tickets, counted toward capacity
- **Suspended**: Payment failure or manual suspension — no new tickets routed
- **Cancelled**: Period-end cancellation — instance removed, data archived
- **Downgrade Scheduled**: Instance type change scheduled for period end

### 4.4 Per-Instance Billing

Each instance has its own Paddle subscription item. This enables:
- Independent upgrade/downgrade per instance
- Independent cancellation per instance
- Clear line-item billing on invoices
- Per-instance proration on mid-cycle changes

### 4.5 Instance Selection at Purchase

When a company purchases a new variant:
1. They choose the variant type (Mini / Parwa / High)
2. They optionally assign an instance name
3. They optionally assign channels (or leave for auto-routing)
4. A new `VariantInstance` record is created
5. A Paddle subscription item is added
6. The instance immediately becomes available for routing

---

## 5. Smart Routing V2 with Overflow Chain

### 5.1 Routing Algorithm

When a new ticket arrives, the routing engine follows this decision tree:

```
1. IDENTIFY: Determine ticket complexity + channel + urgency
2. MATCH: Find the "best-fit" instance based on:
   a. Channel assignment (if ticket comes from a pinned channel)
   b. Complexity → variant type (simple → mini, medium → parwa, complex → high)
3. ROUTE: Try instances in this order:
   a. Same variant type, least-loaded, with capacity
   b. Same variant type, least-loaded, any capacity (overloaded OK)
   c. Higher variant type, least-loaded, with capacity (OVERFLOW UP)
   d. All full → SUGGEST PURCHASE
4. NEVER overflow downward (High full → cannot route to Parwa/Mini)
```

### 5.2 Overflow Chain Visualization

```
Mini Parwa instances full?
  → Try another Mini Parwa instance (if exists)
  → Try Parwa instance (if exists) — OVERFLOW UP
  → Try High Parwa instance (if exists) — OVERFLOW UP
  → All full → Show "Purchase Another Instance" prompt

Parwa instances full?
  → Try another Parwa instance (if exists)
  → Try High Parwa instance (if exists) — OVERFLOW UP
  → All full → Show "Purchase Another Instance" prompt

High Parwa instances full?
  → Try another High Parwa instance (if exists)
  → All full → Show "Purchase Another Instance" prompt
  → NEVER overflow to Parwa or Mini
```

### 5.3 Overflow Rules Summary

| Current Variant | Overflow Step 1 | Overflow Step 2 | Overflow Step 3 | Hard Stop |
|----------------|----------------|----------------|----------------|-----------|
| Mini Parwa | Another Mini | Parwa | High Parwa | Suggest purchase |
| Parwa | Another Parwa | High Parwa | — | Suggest purchase |
| High Parwa | Another High | — | — | Suggest purchase |

**Key principle**: Overflow only goes UP, never DOWN. This prevents higher-paying customers' tickets from being handled by lower-tier instances (which would degrade their experience).

### 5.4 Smart Router V2 Implementation Outline

```python
# backend/app/services/smart_router_v2.py

class SmartRouterV2:
    """Variant-aware ticket router with overflow chain."""

    VARIANT_OVERFLOW_CHAIN = {
        "mini_parwa": ["mini_parwa", "parwa", "high_parwa"],
        "parwa":      ["parwa", "high_parwa"],
        "high_parwa": ["high_parwa"],
    }

    def route_ticket(
        self,
        company_id: str,
        ticket_id: str,
        preferred_variant: str | None = None,
        channel: str | None = None,
        complexity: float = 0.5,
    ) -> RoutingResult:
        """Route a ticket through the overflow chain.

        Steps:
        1. Determine ideal variant based on complexity
        2. Walk the overflow chain for that variant
        3. For each variant in the chain:
           a. Find least-loaded active instance with capacity
           b. If found → route there
           c. If not → move to next variant in chain
        4. If no instance found → return suggestion to purchase

        Returns:
            RoutingResult with instance_id, variant_type,
            overflowed (bool), overflow_from (str | None)
        """
        # Determine ideal variant from complexity
        ideal_variant = self._complexity_to_variant(complexity)
        if preferred_variant:
            ideal_variant = preferred_variant

        # Walk overflow chain
        chain = self.VARIANT_OVERFLOW_CHAIN[ideal_variant]
        overflow_from = None

        for variant_type in chain:
            instance = self._find_available_instance(
                company_id=company_id,
                variant_type=variant_type,
                channel=channel,
            )
            if instance:
                overflowed = variant_type != ideal_variant
                return RoutingResult(
                    instance_id=instance.id,
                    variant_type=variant_type,
                    overflowed=overflowed,
                    overflow_from=ideal_variant if overflowed else None,
                    strategy="smart_overflow",
                )

        # All instances full — suggest purchase
        return RoutingResult(
            instance_id=None,
            variant_type=None,
            overflowed=False,
            overflow_from=None,
            strategy="suggest_purchase",
            suggestion=self._build_purchase_suggestion(
                company_id, ideal_variant,
            ),
        )

    def _complexity_to_variant(self, complexity: float) -> str:
        """Map complexity score to ideal variant."""
        if complexity <= 0.3:
            return "mini_parwa"
        elif complexity <= 0.7:
            return "parwa"
        else:
            return "high_parwa"

    def _find_available_instance(
        self,
        company_id: str,
        variant_type: str,
        channel: str | None = None,
    ) -> VariantInstance | None:
        """Find least-loaded active instance of given variant type."""
        # Query: active instances of this variant for this company
        # Sort by: (active_tickets_count ASC, total_tickets_handled ASC)
        # Filter: capacity not exceeded
        # If channel pinned: prefer channel-matched instances
        ...

    def _build_purchase_suggestion(
        self,
        company_id: str,
        ideal_variant: str,
    ) -> dict:
        """Build purchase suggestion with pricing."""
        return {
            "message": f"All {ideal_variant.replace('_', ' ').title()} instances are at capacity.",
            "suggested_action": "purchase_new_instance",
            "suggested_variant": ideal_variant,
            "price_monthly": VARIANT_PRICES[ideal_variant],
            "cta_url": "/billing/instances/new",
        }
```

### 5.5 Routing Context Data

The router receives context from the AI pipeline stages 1-5:

| Signal | Source | Usage |
|--------|--------|-------|
| `complexity` | Signal Extraction (Stage 3) | Determines ideal variant |
| `intent_type` | Classification (Stage 4) | Special routing for billing/complaint intents |
| `urgency_level` | Sentiment (Stage 5) | High urgency → prefer higher variant |
| `channel` | Ticket metadata | Channel-pinned instance matching |
| `customer_tier` | Customer metadata | VIP customers → prefer higher variant |

---

## 6. Limit Overflow Engine

### 6.1 Per-Instance Limits

Each instance has its own limits derived from its variant type:

```python
VARIANT_LIMITS = {
    "mini_parwa": {
        "monthly_tickets": 2000,
        "ai_agents": 1,
        "team_members": 3,
        "voice_slots": 0,
        "kb_docs": 100,
        "price_monthly": Decimal("999.00"),
    },
    "parwa": {
        "monthly_tickets": 5000,
        "ai_agents": 3,
        "team_members": 10,
        "voice_slots": 2,
        "kb_docs": 500,
        "price_monthly": Decimal("2499.00"),
    },
    "high_parwa": {
        "monthly_tickets": 15000,
        "ai_agents": 5,
        "team_members": 25,
        "voice_slots": 5,
        "kb_docs": 2000,
        "price_monthly": Decimal("3999.00"),
    },
}
```

### 6.2 Effective Limits Calculation

For a company with multiple instances, effective limits are computed as:

```python
# Example: Company has 2x Mini Parwa + 1x High Parwa
# Effective ticket limit = (2 × 2,000) + (1 × 15,000) = 19,000
# But per-instance tracking shows: Mini #1: 1,800/2,000, Mini #2: 500/2,000, High #1: 12,000/15,000
```

**Ticket limit** is shared across instances (overflow allows redistribution).  
**Agent/team/voice limits** are per-instance (each instance has its own allocation).

### 6.3 Limit Check Flow

```
1. New ticket arrives → Smart Router selects instance
2. Check instance's monthly ticket count vs. limit
3. If under limit → allow, route to instance
4. If at limit → trigger overflow:
   a. Find another instance of same variant with capacity
   b. If none → find higher variant instance with capacity
   c. If none → suggest purchase
5. Never block at company level if any instance has capacity
```

### 6.4 Limit Overflow Service

```python
# backend/app/services/limit_overflow_engine.py

class LimitOverflowEngine:
    """Handles limit overflow routing across instances."""

    def check_and_route(
        self,
        company_id: str,
        instance_id: str,
        limit_type: str,  # "tickets", "ai_agents", etc.
    ) -> OverflowResult:
        """Check if an instance has hit its limit and find overflow target.

        For tickets: overflow to another instance
        For other resources: hard block (cannot overflow agents/team)
        """
        if limit_type == "tickets":
            return self._check_ticket_overflow(company_id, instance_id)
        else:
            return self._check_hard_limit(company_id, instance_id, limit_type)

    def _check_ticket_overflow(
        self,
        company_id: str,
        instance_id: str,
    ) -> OverflowResult:
        """Check ticket limit and attempt overflow if needed."""
        instance = self._get_instance(company_id, instance_id)
        variant_limits = VARIANT_LIMITS[instance.variant_type]

        if instance.tickets_this_month < variant_limits["monthly_tickets"]:
            # Under limit — no overflow needed
            return OverflowResult(action="allow", instance_id=instance_id)

        # At limit — try overflow
        chain = SmartRouterV2.VARIANT_OVERFLOW_CHAIN[instance.variant_type]
        for target_variant in chain[1:]:  # Skip self
            available = self._find_available_instance(
                company_id, target_variant, "tickets",
            )
            if available:
                return OverflowResult(
                    action="overflow",
                    target_instance_id=available.id,
                    target_variant_type=target_variant,
                    overflow_from=instance.variant_type,
                )

        # No overflow available — suggest purchase
        return OverflowResult(
            action="suggest_purchase",
            message=f"Ticket limit reached on all instances.",
            suggested_variant=instance.variant_type,
        )

    def _check_hard_limit(
        self,
        company_id: str,
        instance_id: str,
        limit_type: str,
    ) -> OverflowResult:
        """Non-ticket limits: hard block, no overflow."""
        instance = self._get_instance(company_id, instance_id)
        variant_limits = VARIANT_LIMITS[instance.variant_type]
        limit = variant_limits.get(limit_type, 0)
        current = self._get_current_count(company_id, instance_id, limit_type)

        if current < limit:
            return OverflowResult(action="allow", instance_id=instance_id)

        return OverflowResult(
            action="block",
            message=f"{limit_type} limit reached ({current}/{limit}) on instance {instance.instance_name}.",
            suggested_action="upgrade_instance",
        )
```

---

## 7. Utilization Tracking API

### 7.1 Per-Instance Utilization

Each instance tracks its own utilization:

```python
# GET /api/v1/billing/instances/{instance_id}/utilization

{
    "instance_id": "inst_abc123",
    "instance_name": "US Support Team",
    "variant_type": "parwa",
    "limits": {
        "monthly_tickets": 5000,
        "ai_agents": 3,
        "team_members": 10,
        "voice_slots": 2,
        "kb_docs": 500,
    },
    "usage": {
        "tickets_this_month": 3200,
        "ai_agents_active": 2,
        "team_members_active": 7,
        "voice_slots_active": 1,
        "kb_docs_count": 342,
    },
    "utilization": {
        "tickets_pct": 64.0,
        "ai_agents_pct": 66.7,
        "team_members_pct": 70.0,
        "voice_slots_pct": 50.0,
        "kb_docs_pct": 68.4,
    },
    "status": "healthy",  # healthy | approaching | critical | exceeded
    "alerts": []
}
```

### 7.2 Per-Variant Aggregation

Across all instances of a given variant type:

```python
# GET /api/v1/billing/variants/parwa/utilization?company_id=xxx

{
    "variant_type": "parwa",
    "instance_count": 2,
    "aggregate_limits": {
        "monthly_tickets": 10000,  # 5000 × 2
        "ai_agents": 6,           # 3 × 2
        "team_members": 20,       # 10 × 2
        "voice_slots": 4,         # 2 × 2
        "kb_docs": 1000,          # 500 × 2
    },
    "aggregate_usage": {
        "tickets_this_month": 6800,
        "ai_agents_active": 4,
        "team_members_active": 14,
        "voice_slots_active": 3,
        "kb_docs_count": 712,
    },
    "per_instance": [
        {
            "instance_id": "inst_abc123",
            "instance_name": "US Support Team",
            "tickets_this_month": 3200,
            "tickets_limit": 5000,
            "utilization_pct": 64.0,
        },
        {
            "instance_id": "inst_def456",
            "instance_name": "EU Support Team",
            "tickets_this_month": 3600,
            "tickets_limit": 5000,
            "utilization_pct": 72.0,
        }
    ]
}
```

### 7.3 Company-Wide Dashboard

```python
# GET /api/v1/billing/utilization?company_id=xxx

{
    "company_id": "comp_xyz789",
    "total_instances": 3,
    "total_monthly_spend": "$6,497.00",
    "variants": {
        "mini_parwa": {
            "instance_count": 1,
            "aggregate_tickets_used": 1800,
            "aggregate_tickets_limit": 2000,
            "overall_pct": 90.0,
            "status": "approaching",
        },
        "parwa": {
            "instance_count": 2,
            "aggregate_tickets_used": 6800,
            "aggregate_tickets_limit": 10000,
            "overall_pct": 68.0,
            "status": "healthy",
        },
        "high_parwa": {
            "instance_count": 0,
        }
    },
    "visual_indicators": {
        "mini_parwa": "amber",   # >80% = amber, >95% = red
        "parwa": "green",        # <80% = green
        "high_parwa": "none",    # No instances
    },
    "recommendations": [
        {
            "type": "upgrade_suggestion",
            "message": "Mini Parwa instance is at 90% capacity. Consider upgrading to Parwa or adding another Mini Parwa.",
            "variant": "mini_parwa",
            "action": "upgrade_or_add",
        }
    ]
}
```

### 7.4 Utilization Status Thresholds

| Status | Ticket Utilization | Visual |
|--------|-------------------|--------|
| Healthy | 0% – 79% | Green |
| Approaching | 80% – 94% | Amber |
| Critical | 95% – 99% | Red |
| Exceeded | 100%+ | Red + Alert |

---

## 8. Industry Add-Ons (Per-Instance)

### 8.1 Per-Instance Model

Industry add-ons (ecommerce, SaaS, logistics, others) are attached to **specific instances**, not to the company as a whole. This is cleaner with multi-instance because:

1. Each instance has its own purpose (e.g., "E-commerce Support Team")
2. An e-commerce add-on on one Mini Parwa instance only adds tickets/KB docs to that instance
3. A company with 2 Mini Parwa instances can have e-commerce on one and SaaS on the other

### 8.2 Add-On Stacking Rules (Per-Instance)

| Resource | Stacks with Add-on? | Scope |
|----------|---------------------|-------|
| Tickets | Yes (+500 for ecommerce, etc.) | Added to that instance's ticket limit |
| KB Docs | Yes (+50 for ecommerce, etc.) | Added to that instance's KB doc limit |
| AI Agents | No | Instance base limit only |
| Team Members | No | Instance base limit only |
| Voice Slots | No | Instance base limit only |

### 8.3 Add-On Lifecycle (Per-Instance)

```
[Add to Instance] → [Active] → [Mark for Removal] → [Archived at Period End]
                                                    → [Restore from Archive]
```

- **Add**: Attaches to specific `instance_id`, creates Paddle subscription item
- **Remove**: Sets status to `inactive`, scheduled for removal at period end
- **Archive**: Period-end cron removes Paddle item, archives KB docs tagged with this add-on
- **Restore**: Re-activates from archived, creates new Paddle item

### 8.4 Add-On Schema Update

```python
# CompanyVariant table needs an instance_id column added

class CompanyVariant(Base):
    """Industry variant add-on attached to a specific instance."""
    __tablename__ = "company_variants"

    id = Column(UUID, primary_key=True)
    company_id = Column(UUID, ForeignKey("companies.id"))
    instance_id = Column(UUID, ForeignKey("variant_instances.id"), nullable=True)  # NEW
    variant_id = Column(String)    # ecommerce, saas, logistics, others
    display_name = Column(String)
    status = Column(String)        # active, inactive, archived
    price_per_month = Column(Numeric)
    tickets_added = Column(Integer)
    kb_docs_added = Column(Integer)
    activated_at = Column(DateTime)
    deactivated_at = Column(DateTime)
    paddle_subscription_item_id = Column(String)
    created_at = Column(DateTime)
```

### 8.5 Current Add-On Pricing (No Change)

| Add-On | Monthly | Yearly | Tickets Added | KB Docs Added | Description |
|--------|---------|--------|---------------|---------------|-------------|
| E-commerce | $79 | $790 | +500 | +50 | Order tracking, refund handling, product FAQ |
| SaaS | $59 | $590 | +300 | +30 | Technical support, bug triage, feature requests |
| Logistics | $69 | $690 | +400 | +40 | Shipment tracking, delivery updates, returns |
| Others | $39 | $390 | +200 | +20 | General support, FAQ, escalation |

---

## 9. Variant-Aware AI Pipeline

### 9.1 Current Gaps

The AI pipeline (`AIPipeline` class) currently:
- Defaults `variant_type` to `"parwa"` in `PipelineContext`
- Has NO variant-specific system prompts
- Has NO variant-specific confidence thresholds
- Has NO variant-specific RAG depth
- Has NO variant-specific guardrails
- Passes `variant_type` to sub-services but they don't use it meaningfully

### 9.2 Variant-Aware Pipeline Configuration

```python
# backend/app/config/variant_pipeline_config.py

VARIANT_PIPELINE_CONFIG = {
    "mini_parwa": {
        "system_prompt_suffix": (
            "You are a helpful customer support assistant for Mini Parwa. "
            "Keep responses concise and direct. Escalate complex issues."
        ),
        "model_tiers": ["light"],
        "rag_depth": {
            "top_k": 3,
            "rerank": False,
            "chunk_size": 512,
        },
        "confidence_threshold": 60.0,
        "auto_action_threshold": 80.0,
        "technique_tiers": ["simple"],
        "guardrails_level": "standard",
        "max_response_length": 500,
        "brand_voice": False,
        "escalation_on_low_confidence": True,
    },
    "parwa": {
        "system_prompt_suffix": (
            "You are a knowledgeable customer support assistant for Parwa. "
            "Provide detailed, helpful responses. Use available knowledge base. "
            "Apply brand voice guidelines when provided."
        ),
        "model_tiers": ["light", "medium"],
        "rag_depth": {
            "top_k": 5,
            "rerank": True,
            "chunk_size": 768,
        },
        "confidence_threshold": 70.0,
        "auto_action_threshold": 85.0,
        "technique_tiers": ["simple", "moderate"],
        "guardrails_level": "enhanced",
        "max_response_length": 1000,
        "brand_voice": True,
        "escalation_on_low_confidence": True,
    },
    "high_parwa": {
        "system_prompt_suffix": (
            "You are an expert customer support assistant for High Parwa. "
            "Provide comprehensive, precise responses with citations. "
            "Apply brand voice, custom guardrails, and industry-specific knowledge. "
            "Handle complex multi-step issues autonomously when confidence is high."
        ),
        "model_tiers": ["light", "medium", "heavy"],
        "rag_depth": {
            "top_k": 10,
            "rerank": True,
            "chunk_size": 1024,
        },
        "confidence_threshold": 80.0,
        "auto_action_threshold": 90.0,
        "technique_tiers": ["simple", "moderate", "complex"],
        "guardrails_level": "premium",
        "max_response_length": 2000,
        "brand_voice": True,
        "custom_guardrails": True,
        "escalation_on_low_confidence": False,  # High Parwa handles more autonomously
    },
}
```

### 9.3 Pipeline Stage Modifications

| Pipeline Stage | Mini Parwa Behavior | Parwa Behavior | High Parwa Behavior |
|---------------|--------------------|--------------------|---------------------|
| **Stage 6: Smart Router** | Light model only | Light/Medium by complexity | Light/Medium/Heavy by complexity |
| **Stage 7: Technique Router** | Simple techniques only | Simple/Moderate techniques | All technique tiers |
| **Stage 8: RAG Retrieval** | top-3, no rerank | top-5, with rerank | top-10, with rerank + deep context |
| **Stage 9: Response Gen** | Max 500 chars | Max 1000 chars | Max 2000 chars |
| **Stage 12: Confidence** | Threshold 60% | Threshold 70% | Threshold 80% |
| **Stage 11: Guardrails** | Standard (8 layers) | Enhanced (+brand tone) | Premium (+custom rules + AI guardrails) |
| **Stage 13: Brand Voice** | Not applied | Applied | Applied + custom rules |

### 9.4 Pipeline Integration Points

```python
# In AIPipeline.process(), after variant_type is determined:

from app.config.variant_pipeline_config import VARIANT_PIPELINE_CONFIG

config = VARIANT_PIPELINE_CONFIG.get(ctx.variant_type, VARIANT_PIPELINE_CONFIG["parwa"])

# Apply to PipelineContext
ctx.system_prompt = (ctx.system_prompt or "") + "\n" + config["system_prompt_suffix"]
ctx.confidence_threshold = config["confidence_threshold"]
ctx.max_response_length = config.get("max_response_length", 1000)

# Config is passed down to individual stages via ctx
# Each stage reads config from ctx or from VARIANT_PIPELINE_CONFIG directly
```

---

## 10. Upgrade / Downgrade Flows

### 10.1 Upgrade Flow

Upgrading an instance from one variant to a higher variant:

```
1. User selects instance → clicks "Upgrade"
2. System shows available upgrades:
   - Mini → Parwa or High
   - Parwa → High
3. User selects target variant
4. System calculates proration:
   - Unused credit from current variant (remaining days × daily rate)
   - New charge for target variant (remaining days × daily rate)
   - Net charge = new - credit
5. User confirms + pays
6. Instance immediately upgraded:
   - variant_type updated
   - Limits immediately reflect new variant
   - Paddle subscription item updated
   - AI pipeline uses new variant config on next ticket
```

### 10.2 Downgrade Flow

Downgrading is scheduled at period end (existing billing pattern):

```
1. User selects instance → clicks "Downgrade"
2. System shows available downgrades:
   - Parwa → Mini
   - High → Parwa or Mini
3. User selects target variant
4. System schedules downgrade:
   - pending_downgrade_variant set on VariantInstance
   - downgrade_scheduled_at = current period end
   - No immediate changes — instance continues at current tier
5. At period end, cron job executes:
   - variant_type updated to new variant
   - Limits adjusted to new variant
   - If usage exceeds new variant limits: tickets still processed via overflow
   - Paddle subscription item updated
   - Notification sent to user
```

### 10.3 Cross-Instance Operations

- **Cannot merge instances**: Each instance is independent
- **Cannot split instances**: Must purchase a new instance instead
- **Can cancel one instance** while keeping others active
- **Can have different variants** simultaneously (1x Mini + 1x High is valid)

---

## 11. Database Schema Changes

### 11.1 New Tables

```sql
-- Variant Instance (already exists, needs updates)
CREATE TABLE variant_instances (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    variant_type VARCHAR(20) NOT NULL,  -- mini_parwa, parwa, high_parwa
    instance_name VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active',
    active_tickets_count INTEGER DEFAULT 0,
    total_tickets_handled INTEGER DEFAULT 0,
    capacity_config JSONB DEFAULT '{}',
    channel_assignment JSONB DEFAULT '[]',
    pending_downgrade_variant VARCHAR(20),  -- NEW: scheduled downgrade
    downgrade_scheduled_at TIMESTAMP,        -- NEW: when downgrade happens
    last_activity_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Instance Utilization Snapshots (NEW)
CREATE TABLE instance_utilization_snapshots (
    id UUID PRIMARY KEY,
    instance_id UUID NOT NULL REFERENCES variant_instances(id),
    company_id UUID NOT NULL REFERENCES companies(id),
    record_month VARCHAR(7) NOT NULL,  -- YYYY-MM
    variant_type VARCHAR(20) NOT NULL,
    tickets_used INTEGER DEFAULT 0,
    tickets_limit INTEGER DEFAULT 0,
    ai_agents_active INTEGER DEFAULT 0,
    team_members_active INTEGER DEFAULT 0,
    voice_slots_active INTEGER DEFAULT 0,
    kb_docs_count INTEGER DEFAULT 0,
    utilization_pct DECIMAL(5,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'healthy',
    snapshot_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(instance_id, record_month)
);

-- Overflow Audit Log (NEW)
CREATE TABLE overflow_audit_log (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL,
    ticket_id UUID NOT NULL,
    source_instance_id UUID,
    source_variant_type VARCHAR(20),
    target_instance_id UUID,
    target_variant_type VARCHAR(20),
    overflow_type VARCHAR(20),  -- same_variant, higher_variant, suggest_purchase
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 11.2 Modified Tables

```sql
-- company_variants: add instance_id
ALTER TABLE company_variants
    ADD COLUMN instance_id UUID REFERENCES variant_instances(id);

-- subscriptions: rename tier values
-- Migration script will update:
--   'starter' → 'mini_parwa'
--   'growth'  → 'parwa'
--   'high'    → 'high_parwa'

-- variant_limits: rename variant_name values
-- Migration script will update:
--   'starter' → 'mini_parwa'
--   'growth'  → 'parwa'
--   'high'    → 'high_parwa'
```

---

## 12. Naming Migration Plan

### 12.1 Files Requiring Changes

| File | Current | Change Required |
|------|---------|----------------|
| `backend/app/schemas/billing.py` | `VariantType.STARTER/GROWTH/HIGH` | Rename to `MINI_PARWA/PARWA/HIGH_PARWA` |
| `backend/app/schemas/billing.py` | `VARIANT_LIMITS` dict keys | Use new enum values |
| `backend/app/services/variant_limit_service.py` | `_HARDCODED_LIMITS` uses `"starter"/"growth"/"high"` | Change to `"mini_parwa"/"parwa"/"high_parwa"` |
| `backend/app/services/variant_orchestration_service.py` | `VARIANT_PRIORITY["parwa_high"]` | Change to `"high_parwa"` |
| `backend/app/services/variant_addon_service.py` | Uses `VariantType(tier_key)` | Will work after enum rename |
| `backend/app/core/ai_pipeline.py` | Default `"parwa"` | Correct, no change needed |
| `database/models/billing_extended.py` | `get_variant_limits()` keys | Change to new names |
| `database/models/variant_engine.py` | `VariantInstance.variant_type` values | Change to new names |
| All Paddle price IDs | `price_starter_*`, `price_growth_*`, `price_high_*` | Update to `price_mini_parwa_*`, `price_parwa_*`, `price_high_parwa_*` |

### 12.2 Migration Strategy

1. **Phase 1 — Add new names alongside old**: Create a mapping layer so both old and new names work
2. **Phase 2 — Update all code references**: Change all Python code to use new canonical names
3. **Phase 3 — Database migration**: Run SQL migration to update stored values
4. **Phase 4 — Remove old names**: Remove backward-compat mapping layer

### 12.3 Backward Compatibility Mapping

```python
# backend/app/config/variant_name_mapping.py

# Mapping from old billing names to canonical names
BILLING_TO_CANONICAL = {
    "starter": "mini_parwa",
    "growth": "parwa",
    "high": "high_parwa",
}

# Mapping from old orchestration name to canonical
ORCHESTRATION_TO_CANONICAL = {
    "mini_parwa": "mini_parwa",   # Already canonical
    "parwa": "parwa",             # Already canonical
    "parwa_high": "high_parwa",   # Rename
}

# Reverse mapping for Paddle (Paddle price IDs may still use old names)
CANONICAL_TO_PADDLE = {
    "mini_parwa": "starter",
    "parwa": "growth",
    "high_parwa": "high",
}

def canonicalize_variant(variant_name: str) -> str:
    """Convert any variant name to its canonical form."""
    name = variant_name.lower().strip()
    return (
        BILLING_TO_CANONICAL.get(name)
        or ORCHESTRATION_TO_CANONICAL.get(name)
        or name
    )
```

---

## 13. Implementation Roadmap

### Phase 1: Canonical Naming Unification
- [ ] Create `variant_name_mapping.py` with backward-compat layer
- [ ] Rename `VariantType` enum values in `billing/schemas.py`
- [ ] Update `_HARDCODED_LIMITS` in `variant_limit_service.py`
- [ ] Update `VARIANT_PRIORITY` in `variant_orchestration_service.py`
- [ ] Update all DB queries and model references
- [ ] Run database migration for stored values

### Phase 2: Variant Inheritance Config
- [ ] Create `variant_inheritance.py` config
- [ ] Create `variant_pipeline_config.py` for AI pipeline
- [ ] Add `get_variant_features()` utility function
- [ ] Add feature gating checks in relevant services

### Phase 3: Smart Router V2 + Overflow Engine
- [ ] Implement `SmartRouterV2` with overflow chain
- [ ] Implement `LimitOverflowEngine`
- [ ] Create `overflow_audit_log` table
- [ ] Add overflow tracking to `VariantWorkloadDistribution`
- [ ] Update `route_ticket()` to use Smart Router V2

### Phase 4: Multi-Instance Support
- [ ] Add `instance_name`, `pending_downgrade_variant`, `downgrade_scheduled_at` to `VariantInstance`
- [ ] Add `instance_id` to `CompanyVariant` (per-instance add-ons)
- [ ] Create instance purchase/management API endpoints
- [ ] Update billing service for per-instance Paddle items
- [ ] Add instance-level limit checks (replace company-level)

### Phase 5: Utilization Tracking
- [ ] Create `instance_utilization_snapshots` table
- [ ] Implement per-instance utilization API
- [ ] Implement per-variant aggregation API
- [ ] Implement company-wide dashboard API
- [ ] Add visual indicators (green/amber/red)
- [ ] Add purchase recommendations engine

### Phase 6: Variant-Aware AI Pipeline
- [ ] Update `PipelineContext` with variant config from `VARIANT_PIPELINE_CONFIG`
- [ ] Make Smart Router variant-aware (model tier filtering)
- [ ] Make Technique Router variant-aware (technique tier filtering)
- [ ] Make RAG retrieval variant-aware (top_k, rerank, chunk_size)
- [ ] Make confidence thresholds variant-aware
- [ ] Make guardrails variant-aware (standard/enhanced/premium)
- [ ] Make brand voice conditional on variant

### Phase 7: Upgrade/Downgrade Flows
- [ ] Implement instance upgrade flow with proration
- [ ] Implement instance downgrade scheduling
- [ ] Create period-end downgrade cron job
- [ ] Add upgrade/downgrade API endpoints
- [ ] Test cross-variant scenarios

---

## 14. Cross-System Connections

The Variant System is NOT an isolated module — it touches nearly every system in Parwa. This section maps every connection point, how data flows between systems, and what changes when variants are involved.

### 14.1 Complete System Connection Map

```
                              ┌─────────────────────┐
                              │   VARIANT SYSTEM     │
                              │  (Source of Truth)   │
                              └──────────┬──────────┘
                                         │
           ┌──────────────┬──────────────┼──────────────┬──────────────┐
           │              │              │              │              │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼─────┐ ┌────▼──────┐ ┌────▼──────┐
    │  Dashboard  │ │  Tickets   │ │   AI     │ │  Shadow   │ │  Billing  │
    │  System     │ │  System    │ │ Pipeline │ │  Mode     │ │  System   │
    └──────┬──────┘ └─────┬──────┘ └────┬─────┘ └────┬──────┘ └────┬──────┘
           │              │              │              │              │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼─────┐ ┌────▼──────┐ ┌────▼──────┐
    │  Channels   │ │   RAG /    │ │ Entitle- │ │   Token   │ │  Onboard │
    │  (Email/    │ │   KB       │ │ ment     │ │  Budget   │ │  /Cold   │
    │   Chat/SMS) │ │            │ │Middleware│ │  Service  │ │  Start   │
    └─────────────┘ └────────────┘ └──────────┘ └──────────┘ └──────────┘
```

### 14.2 Dashboard Connection

**Current State**: The dashboard (`/api/dashboard/`) shows company-wide metrics (ticket summary, KPIs, SLA, volume trend, activity feed) with NO variant awareness.

**Target State**: The dashboard must show per-instance and per-variant metrics.

| Dashboard Widget | Current Behavior | Variant-Aware Behavior |
|-----------------|-----------------|----------------------|
| **Ticket Summary** | Total open/closed/pending | Breakdown by variant instance (Mini: 45 open, Parwa: 120 open, High: 30 open) |
| **KPI Cards** | Company-wide averages | Per-variant KPIs + company aggregate; color-coded by variant |
| **Volume Trend** | Single trend line | Stacked area chart: tickets per variant instance over time |
| **SLA Metrics** | Single SLA target | Per-variant SLA (Mini: 99.5%, Parwa: 99.9%, High: 99.99%) |
| **Utilization** | Not shown | Per-instance capacity bars with green/amber/red indicators |
| **Cost Widget** | Not shown | Monthly spend per instance, total spend, projected next month |
| **Activity Feed** | All tickets mixed | Filterable by instance/variant; overflow events visible |
| **Savings Widget** | Not shown | "AI resolved tickets" per variant, cost savings per tier |

**API Changes Required**:

```python
# GET /api/dashboard/home — add variant breakdown
{
    "ticket_summary": {
        "total_open": 195,
        "by_variant": {
            "mini_parwa": {"open": 45, "in_progress": 12},
            "parwa": {"open": 120, "in_progress": 35},
            "high_parwa": {"open": 30, "in_progress": 8},
        },
        "by_instance": [
            {"instance_id": "inst_1", "name": "US Support", "open": 45, "variant": "mini_parwa"},
            {"instance_id": "inst_2", "name": "EU Support", "open": 120, "variant": "parwa"},
        ]
    },
    "utilization": {
        "by_variant": {
            "mini_parwa": {"pct": 90.0, "status": "approaching", "color": "amber"},
            "parwa": {"pct": 68.0, "status": "healthy", "color": "green"},
            "high_parwa": {"pct": 12.0, "status": "healthy", "color": "green"},
        }
    },
    "overflow_events_today": 3,  # Tickets that overflowed to higher variant
}
```

### 14.3 Tickets System Connection

**Current State**: Tickets reference `plan_tier` for attachment limits but have NO variant instance tracking.

**Target State**: Every ticket must be associated with a variant instance and tracked through the overflow chain.

| Ticket Field | Current | Target |
|-------------|---------|--------|
| `variant_type` | Not stored on ticket | Stored at creation time based on routing |
| `instance_id` | Not on ticket | FK to `variant_instances.id` — which instance is handling it |
| `overflow_from` | Not tracked | If ticket overflowed, which variant it was originally routed to |
| `overflow_to` | Not tracked | Which variant it overflowed to |
| `routing_strategy` | Not stored | `smart_overflow`, `channel_pinned`, `least_loaded`, etc. |

**Ticket Creation Flow with Variants**:

```
1. Customer sends message → Ticket created
2. Smart Router V2 evaluates:
   a. Signal extraction → complexity score
   b. Channel → channel-pinned instance check
   c. Customer tier → VIP routing preference
3. Router selects instance (with overflow if needed)
4. Ticket record updated:
   - instance_id = selected instance
   - variant_type = instance's variant type
   - routing_strategy = "smart_overflow"
   - overflow_from = None (or original variant if overflowed)
5. Instance's active_tickets_count incremented
6. Ticket enters AI pipeline with variant_type from instance
```

**Ticket Lifecycle Variant Interactions**:

```
[Ticket Created] → [Routed to Instance] → [AI Pipeline (variant-aware)]
                                              ↓
                                         [Response Generated]
                                              ↓
                                    ┌─── Confidence ≥ Threshold? ───┐
                                    │                                │
                                 YES                                NO
                                    │                                │
                              [Auto-send]                    [Shadow Mode Hold]
                                    │                                │
                              [Ticket Closed]           [Manager Approves/Rejects]
```

**Key API Files**:
- `backend/app/api/tickets.py` — Line 650: `plan_tier = current_user.get("plan_tier", "starter")` → must canonicalize and use for instance routing
- `backend/app/api/ticket_analytics.py` — Must add per-variant breakdown
- `backend/app/api/ticket_assignment.py` — Must integrate with Smart Router V2
- `backend/app/api/ticket_lifecycle.py` — Must update instance counters on status changes

### 14.4 Shadow Mode Connection

**Current State**: Shadow mode operates at company level with 3 modes (shadow, supervised, graduated). NO variant awareness — all instances share the same mode.

**Target State**: Shadow mode behavior varies by variant, with different auto-execute thresholds and risk tolerances.

| Shadow Mode Aspect | Mini Parwa | Parwa | High Parwa |
|-------------------|-----------|-------|------------|
| **Default Mode** | `shadow` (most restrictive) | `supervised` | `graduated` (most autonomous) |
| **Auto-execute Risk Threshold** | 0.3 (only low-risk) | 0.5 (moderate risk OK) | 0.7 (high-risk auto-execute) |
| **Undo Window** | 30 min (default) | 30 min | 60 min (more time) |
| **Per-Category Defaults** | All shadow | Refund: supervised, FAQ: graduated | Most categories: graduated |
| **Approval Required For** | ALL actions | Refunds, SMS, escalations | Only high-risk (refund > $500) |
| **Batch Approve** | Not available | Available | Available with auto-approve rules |

**Shadow Mode Variant Flow**:

```
AI Pipeline produces response
       │
       ▼
Shadow Mode Interceptor evaluates:
  1. Company-wide mode setting (shadow/supervised/graduated)
  2. Per-category preference (if any)
  3. VARIANT-SPECIFIC defaults:
     - mini_parwa → more conservative, always require approval
     - parwa → balanced, auto-execute moderate risk
     - high_parwa → aggressive, auto-execute most actions
  4. Risk score from 4-layer evaluation
       │
       ▼
Decision:
  risk < variant_threshold AND mode allows → AUTO-EXECUTE + log to undo queue
  risk ≥ variant_threshold → HOLD for manager approval
```

**Code Integration Points**:
- `backend/app/interceptors/base_interceptor.py` — `ShadowInterceptor.evaluate_shadow()` must receive `variant_type` and apply variant-specific thresholds
- `backend/app/interceptors/email_shadow.py` — Email actions with variant-aware risk thresholds
- `backend/app/interceptors/chat_shadow.py` — Chat actions with variant-aware auto-execute
- `backend/app/interceptors/sms_shadow.py` — SMS: Mini must always hold, Parwa+ can auto-execute
- `backend/app/interceptors/voice_shadow.py` — Voice: Only High Parwa gets auto-execute
- `backend/app/api/shadow.py` — Config endpoint must return variant-specific thresholds
- `backend/app/services/shadow_mode_service.py` — `evaluate_action_risk()` must factor in variant type

**Variant Shadow Config**:

```python
VARIANT_SHADOW_DEFAULTS = {
    "mini_parwa": {
        "default_mode": "shadow",
        "auto_execute_threshold": 0.3,
        "undo_window_minutes": 30,
        "always_require_approval": ["refund", "sms", "escalation"],
    },
    "parwa": {
        "default_mode": "supervised",
        "auto_execute_threshold": 0.5,
        "undo_window_minutes": 30,
        "always_require_approval": ["refund", "escalation"],
    },
    "high_parwa": {
        "default_mode": "graduated",
        "auto_execute_threshold": 0.7,
        "undo_window_minutes": 60,
        "always_require_approval": ["high_value_refund"],  # Only >$500 refunds
    },
}
```

### 14.5 Billing System Connection

**Current State**: Billing uses `VariantType` enum (`STARTER/GROWTH/HIGH`) with a single subscription per company.

**Target State**: Billing must support per-instance subscriptions with canonical naming.

| Billing Component | Current | Target |
|------------------|---------|--------|
| `VariantType` enum | `STARTER/GROWTH/HIGH` | `MINI_PARWA/PARWA/HIGH_PARWA` |
| `Subscription.tier` | `"starter"/"growth"/"high"` | `"mini_parwa"/"parwa"/"high_parwa"` |
| Paddle price IDs | `price_starter_*` | `price_mini_parwa_*` |
| Per-instance billing | Not supported | Each instance = separate Paddle subscription item |
| Invoice line items | One line per subscription | One line per instance (e.g., "Mini Parwa - US Team: $999") |
| Proration | Per subscription change | Per instance change (upgrade/downgrade/cancel) |
| Webhook handling | Single subscription events | Must match instance-level Paddle items |
| Downgrade handling | `pending_downgrade_tier` on Subscription | `pending_downgrade_variant` on VariantInstance |

**Billing Flow for Multi-Instance**:

```
Company purchases 2nd instance (Parwa):
1. Create VariantInstance(variant_type="parwa", instance_name="EU Team")
2. Paddle: Add subscription item to existing subscription
3. Invoice: New line item "Parwa - EU Team: $2,499/mo"
4. Proration: Charge for remaining days in current period
5. Instance becomes active immediately
6. Smart Router can now route tickets to this instance
```

**Key Billing Files**:
- `backend/app/api/billing.py` — All endpoints need instance-level awareness
- `backend/app/api/billing_webhooks.py` — Must route Paddle events to correct instance
- `backend/app/services/subscription_service.py` — Lines 154-155 use old `VariantType`; must update
- `backend/app/schemas/billing.py` — `VariantType` enum rename, new instance schemas
- `backend/app/services/variant_addon_service.py` — Must accept `instance_id` for per-instance add-ons

### 14.6 Channel System Connection

**Current State**: Channels (email, chat, SMS, voice, social) have NO variant awareness. All channels treated equally.

**Target State**: Channel availability and AI quality vary by variant.

| Channel | Mini Parwa | Parwa | High Parwa |
|---------|-----------|-------|------------|
| **Email** | Full AI | Full AI | Full AI + priority routing |
| **Chat** | Full AI | Full AI | Full AI + priority routing |
| **SMS** | AI-assisted only | Full AI | Full AI + auto-send |
| **Voice** | NOT available | AI-assisted | Full AI with voice slots |
| **Social** | AI-assisted only | Full AI | Full AI + proactive |
| **WhatsApp** | Not available | Full AI | Full AI + proactive |
| **Web Widget** | Basic | Advanced | Advanced + custom branding |

**Channel-Instance Pinning**:

Each instance can be pinned to specific channels via `channel_assignment` (JSON array on `VariantInstance`):

```python
# Instance "E-commerce Team" pinned to email + chat
instance.channel_assignment = ["email", "chat"]

# Instance "VIP Support" pinned to voice + whatsapp
instance.channel_assignment = ["voice", "whatsapp"]
```

When a ticket arrives on a pinned channel, the router first checks instances pinned to that channel before falling back to general routing.

**Voice Channel Special Rules**:
- Mini Parwa: `voice_slots = 0` → No voice at all
- Parwa: `voice_slots = 2` → Up to 2 simultaneous voice sessions
- High Parwa: `voice_slots = 5` → Up to 5 simultaneous voice sessions

**Channel API Files**:
- `backend/app/api/channels.py` — Must check variant entitlements
- `backend/app/api/email_channel.py` — Shadow mode variant thresholds
- `backend/app/api/sms_channel.py` — Must block SMS AI for mini_parwa if needed
- `backend/app/api/twilio_channels.py` — Voice slot enforcement per variant

### 14.7 Knowledge Base (RAG) Connection

**Current State**: RAG retrieval is the same for all variants. The `variant_type` is passed to the RAG endpoint but ignored.

**Target State**: RAG depth, chunk count, reranking, and retrieval strategy vary by variant.

| RAG Feature | Mini Parwa | Parwa | High Parwa |
|-------------|-----------|-------|------------|
| **Top-K Results** | 3 | 5 | 10 |
| **Reranking** | No | Yes (cross-encoder) | Yes (cross-encoder + MMR diversity) |
| **Chunk Size** | 512 tokens | 768 tokens | 1024 tokens |
| **Hybrid Search** | Vector only | BM25 + Vector | BM25 + Vector + Knowledge Graph |
| **Citation** | No citations | Source links | Full citations with confidence |
| **Cross-Lingual** | No | No | Yes |
| **Context Compression** | No | Yes | Yes + summarization |
| **Multi-Source Fusion** | No | No | Yes (KB + docs + web) |

**RAG Endpoint Integration**:
- `backend/app/api/rag.py` — Line 72: `variant_type = body.get("variant_type", "parwa")` — must use for depth config
- Line 73: Validates against `("mini_parwa", "parwa", "parwa_high")` — must update to `high_parwa`

### 14.8 AI Agent System Connection

**Current State**: AI agents are limited by plan tier but not by instance.

**Target State**: AI agent limits are per-instance, and agent capabilities vary by variant.

| Agent Feature | Mini Parwa | Parwa | High Parwa |
|--------------|-----------|-------|------------|
| **Max AI Agents** | 1 | 3 | 5 |
| **Agent Type** | FAQ bot only | FAQ + Triage + Escalation | All types including proactive |
| **Proactive Engagement** | No | No | Yes |
| **Multi-Step Conversations** | No | Yes (limited) | Yes (full) |
| **Custom Agent Training** | No | Yes | Yes + fine-tuning |
| **Agent Collaboration** | No | No | Yes (agent teams) |

**Agent Provisioning Integration**:
- `backend/app/api/agent_provisioning.py` — Line 85: `tier: str` field → must resolve to instance-level limit
- Line 226: `Get agent limit information for the company's subscription tier` → must be per-instance

### 14.9 Entitlement Middleware Connection

**Current State**: Already exists and works! `entitlement_middleware.py` checks feature availability per variant type with instance-level overrides.

**Key Point**: The entitlement system already uses canonical names (`mini_parwa`, `parwa`, `parwa_high`) internally, but pricing displays wrong values.

**Changes Needed**:
- Fix `PLAN_PRICING` in `entitlement_middleware.py` — currently shows `$499/mo` for Mini and `$9,999/mo` for High (wrong)
- Rename `parwa_high` → `high_parwa` in `PLAN_DISPLAY_NAMES`, `PLAN_PRICING`, `ORDERED_VARIANT_TYPES`
- Add `VARIANT_LEVELS` key `high_parwa` (currently `parwa_high`)

**Current (Wrong) Values**:
```python
PLAN_PRICING = {
    "mini_parwa": "$499/mo",     # WRONG — should be $999/mo
    "parwa": "$2,499/mo",        # Correct
    "parwa_high": "$9,999/mo",   # WRONG name and price — should be high_parwa / $3,999/mo
}
```

### 14.10 Token Budget Service Connection

**Current State**: `TokenBudgetService` already has variant-aware token budgets with per-variant max tokens.

**Current Config** (already correct naming, just needs `parwa_high` → `high_parwa`):
```python
VARIANT_TOKEN_BUDGETS = {
    "mini_parwa": {"max_tokens": 4096, ...},
    "parwa": {"max_tokens": 8192, ...},
    "parwa_high": {"max_tokens": 16384, ...},  # Rename to high_parwa
}
```

**Target Token Budgets** (with updated names and refined thresholds):

| Variant | Max Tokens | Warning Threshold | Critical Threshold | Effective Max (after 10% safety margin) |
|---------|-----------|------------------|-------------------|---------------------------------------|
| Mini Parwa | 4,096 | 70% | 90% | 3,686 |
| Parwa | 8,192 | 70% | 90% | 7,372 |
| High Parwa | 16,384 | 75% | 92% | 14,745 |

### 14.11 Onboarding & Cold Start Connection

**Current State**: Onboarding already maps company size to variant type.

```python
# backend/app/api/onboarding.py — Lines 248-258
variant_type = "mini_parwa"  # Default
size_to_variant = {
    "1-10": "mini_parwa",
    "11-50": "parwa",
    "51-200": "parwa",
    "200+": "high_parwa",  # Currently "parwa_high" — needs rename
}
```

**Changes Needed**:
- Update `size_to_variant` to use `high_parwa` instead of `parwa_high`
- Cold start service (`variant_instance_service.py`) must create the initial `VariantInstance` record during onboarding
- `VARIANT_PRIORITY` in `variant_instance_service.py` uses `"parwa_high": 3` → rename to `"high_parwa": 3`

### 14.12 Cold Start Service Connection

**Current State**: `cold_start_service.py` recovers tenant warmup with variant type.

**Integration**: When a new company onboards:
1. Cold start service determines `variant_type` from company size
2. `variant_instance_service.register_instance()` creates the first instance
3. `variant_capability_service.initialize_variant_matrix()` populates 170+ feature capabilities
4. Token budget is initialized for the variant
5. Shadow mode defaults are set based on variant

### 14.13 Monitoring & Analytics Connection

**Current State**: Monitoring exists but aggregates everything company-wide.

**Variant-Aware Monitoring Metrics**:

| Metric | Per-Instance | Per-Variant | Company-Wide |
|--------|-------------|-------------|-------------|
| Ticket volume | Yes | Sum of instances | Sum of all |
| AI confidence scores | Yes | Average of instances | Average of all |
| Response time | Yes | Average of instances | Average of all |
| Overflow events | Yes | Count per variant | Total count |
| Token usage | Yes | Sum of instances | Sum of all |
| Cost per ticket | Yes | Average per variant | Weighted average |
| SLA compliance | Per-instance SLA | Variant-specific SLA | Weighted SLA |
| Shadow mode holds | Yes | Count per variant | Total count |

**Monitoring Service Files**:
- `backend/app/core/ai_monitoring_service.py` — Must store `variant_type` and `instance_id` per query
- `backend/app/api/agent_dashboard.py` — Must add variant breakdown
- `backend/app/api/ticket_analytics.py` — Must add per-variant ticket analytics

### 14.14 Webhook & Event System Connection

**New Variant Events** (to be emitted):

| Event | Trigger | Payload |
|-------|---------|---------|
| `variant:instance_created` | New instance purchased | `instance_id`, `variant_type`, `company_id` |
| `variant:instance_suspended` | Instance suspended | `instance_id`, `reason` |
| `variant:instance_upgraded` | Instance tier upgraded | `instance_id`, `old_variant`, `new_variant` |
| `variant:instance_downgraded` | Instance downgraded at period end | `instance_id`, `old_variant`, `new_variant` |
| `variant:overflow_triggered` | Ticket overflowed to higher variant | `ticket_id`, `from_instance`, `to_instance` |
| `variant:limit_exceeded` | Instance hit hard limit | `instance_id`, `limit_type`, `current`, `max` |
| `variant:addon_added` | Industry add-on attached to instance | `instance_id`, `addon_id` |
| `variant:addon_removed` | Industry add-on removed from instance | `instance_id`, `addon_id` |
| `variant:utilization_warning` | Instance reached 80%/95% | `instance_id`, `pct`, `status` |

### 14.15 Complete Feature Registry (170+ Features by Variant)

The existing `FEATURE_REGISTRY` in `variant_capability_service.py` defines 170+ features mapped to variant levels. Here is the summary by category and variant:

| Category | Mini Parwa (Level 1) | Parwa (Level 2) | High Parwa (Level 3) |
|----------|---------------------|-----------------|---------------------|
| **Routing** | 6 features | +2 more | 0 additional |
| **Classification** | 5 features | +3 more | +3 more |
| **RAG** | 4 features | +4 more | +4 more |
| **Confidence** | 2 features | 0 additional | 0 additional |
| **Response Gen** | 3 features | +5 more | +3 more |
| **Technique (Tier 1)** | 3 features | — | — |
| **Technique (Tier 2)** | — | 7 features | — |
| **Technique (Tier 3)** | — | — | 6 features |
| **Guardrails** | 7 features | +3 more | +1 more |
| **Monitoring** | 5 features | +4 more | +3 more |
| **Orchestration** | 5 features | +8 more | +4 more |
| **Signals** | 4 features | +7 more | 0 additional |
| **GSD/State** | — | 3 features | +1 more |
| **Channels** | 2 features | +3 more | +1 more |
| **Additional** | 1 feature | +10 more | +11 more |
| **TOTAL** | ~47 features | ~64 features | ~89 features |

**Key Feature Gating Examples**:
- `F-054`: Smart Router (3-tier LLM) → Level 1 (all variants)
- `F-056`: Context Window Manager → Level 2 (Parwa+ only)
- `F-068`: Multi-Intent Detection → Level 3 (High Parwa only)
- `F-088`: Multi-Source Fusion → Level 3 (High Parwa only)
- `F-106`: Response A/B Testing → Level 3 (High Parwa only)
- `F-150`: CLARA (Contrastive Learning) → Level 3 (High Parwa only)
- `F-204`: Auto-Scaling Orchestration → Level 3 (High Parwa only)
- `F-253`: Voice Channel AI → Level 3 (High Parwa only)

---

## 15. Data Flow: End-to-End Ticket Journey

This section shows the complete journey of a ticket from creation to resolution, showing every variant touchpoint.

### 15.1 Ticket Creation Journey

```
Step 1: CUSTOMER SENDS MESSAGE
   │  Channel: email/chat/SMS/voice
   │  Company: comp_xyz (has 1x Mini Parwa + 1x High Parwa)
   ▼
Step 2: CHANNEL INTERCEPTOR
   │  email_shadow.py / chat_shadow.py / sms_shadow.py / voice_shadow.py
   │  → Checks: Is this channel available for this company's variants?
   │  → Mini Parwa: email, chat OK; voice NOT OK
   │  → High Parwa: all channels OK
   ▼
Step 3: ENTITLEMENT CHECK
   │  entitlement_middleware.py → check_entitlement()
   │  → Is the requested AI feature available for this variant?
   │  → Example: "F-253 Voice Channel AI" requires Level 3 (High Parwa)
   ▼
Step 4: SMART ROUTER V2
   │  smart_router_v2.py → route_ticket()
   │  → Signal extraction: complexity = 0.8 (high)
   │  → Ideal variant: high_parwa
   │  → Find least-loaded High Parwa instance: "VIP Support" (12/15,000 tickets)
   │  → Route to inst_high_001
   ▼
Step 5: LIMIT CHECK
   │  limit_overflow_engine.py → check_and_route()
   │  → inst_high_001: 12/15,000 tickets → ALLOW
   │  → If full: overflow chain → try another High Parwa → suggest purchase
   ▼
Step 6: TOKEN BUDGET INIT
   │  token_budget_service.py → initialize_budget()
   │  → variant_type = "high_parwa"
   │  → max_tokens = 14,745 (16,384 - 10% safety margin)
   ▼
Step 7: AI PIPELINE (13 stages, variant-aware)
   │  ai_pipeline.py → process(PipelineContext)
   │  → variant_type = "high_parwa"
   │  → config = VARIANT_PIPELINE_CONFIG["high_parwa"]
   │
   │  Stage 1: Edge Case Detection — variant-aware handler filtering
   │  Stage 2: Prompt Injection Scan — standard for all
   │  Stage 3: Signal Extraction — all 10 signals
   │  Stage 4: Classification — AI-powered (High Parwa has SmartRouter)
   │  Stage 5: Sentiment Analysis — full analysis
   │  Stage 6: Smart Router — Light/Medium/Heavy model by complexity
   │  Stage 7: Technique Router — all tiers available (including CLARA, GoT)
   │  Stage 8: RAG Retrieval — top-10, rerank, deep context, citations
   │  Stage 9: Response Generation — up to 2000 chars, brand voice applied
   │  Stage 10: CLARA Quality Gate — 5-stage quality check
   │  Stage 11: Guardrails — premium (8 layers + custom rules + AI guardrails)
   │  Stage 12: Confidence Scoring — threshold 80%
   │  Stage 13: Brand Voice — applied with custom rules
   ▼
Step 8: SHADOW MODE EVALUATION
   │  shadow_mode_service.py → evaluate_action_risk()
   │  → High Parwa default: "graduated" mode
   │  → auto_execute_threshold: 0.7
   │  → Risk score: 0.4 → AUTO-EXECUTE (below 0.7 threshold)
   │  → Log to undo queue (60-minute undo window)
   ▼
Step 9: TICKET RESOLUTION
   │  → Response auto-sent to customer
   │  → Instance counters updated: active_tickets_count - 1
   │  → Utilization snapshot updated
   │  → Overflow audit log (if overflow occurred)
   │  → AI monitoring record saved with variant_type + instance_id
```

### 15.2 Comparison: Same Ticket on Different Variants

| Step | Mini Parwa | Parwa | High Parwa |
|------|-----------|-------|------------|
| Router model | Light only | Medium | Heavy |
| Technique | Chain-of-Thought | CRP + Self-Consistency | CLARA + Graph-of-Thought |
| RAG depth | top-3, no rerank | top-5, with rerank | top-10, rerank + citations |
| Response length | 500 chars | 1000 chars | 2000 chars |
| Confidence threshold | 60% | 70% | 80% |
| Shadow mode | HOLD (shadow) | Conditional (supervised) | AUTO-EXECUTE (graduated) |
| Brand voice | Not applied | Applied | Applied + custom |
| Token budget | 3,686 tokens | 7,372 tokens | 14,745 tokens |
| Voice available | No | AI-assisted | Full AI |

---

## Appendix A: Variant Priority Map

```python
VARIANT_PRIORITY = {
    "mini_parwa": 1,
    "parwa": 2,
    "high_parwa": 3,
}

VARIANT_PRICES = {
    "mini_parwa": Decimal("999.00"),
    "parwa": Decimal("2499.00"),
    "high_parwa": Decimal("3999.00"),
}

VARIANT_DISPLAY_NAMES = {
    "mini_parwa": "Mini Parwa",
    "parwa": "Parwa",
    "high_parwa": "High Parwa",
}
```

## Appendix B: Decision Log

| # | Decision | Rationale | Date |
|---|----------|-----------|------|
| 1 | Canonical names: `mini_parwa`, `parwa`, `high_parwa` | Product identity, consistency, removes `parwa_high` awkwardness | 2026-04-23 |
| 2 | Inheritance model: Mini ⊂ Parwa ⊂ High | Simpler feature resolution, natural upgrade path | 2026-04-23 |
| 3 | Overflow: same type first, then higher, never down | Protects higher-tier customer experience, logical capacity model | 2026-04-23 |
| 4 | Multi-variant hiring: each instance separate charge | Fair pricing, clear billing, scalable per-team/region | 2026-04-23 |
| 5 | Industry add-ons: per-instance, not per-company | Cleaner with multi-instance, supports team-specific add-ons | 2026-04-23 |
| 6 | Downgrade: scheduled at period end | Follows existing billing pattern, prevents mid-cycle disruption | 2026-04-23 |
| 7 | High Parwa full → must buy another High Parwa | No downgrade overflow preserves premium SLA and experience | 2026-04-23 |
| 8 | Unify naming: billing `starter/growth/high` → `mini_parwa/parwa/high_parwa` | Single source of truth, eliminates mapping confusion | 2026-04-23 |
