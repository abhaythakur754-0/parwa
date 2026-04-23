# Parwa Variant System Architecture

> **Status**: Architecture Document — Pre-Implementation  
> **Last Updated**: 2026-04-23  
> **Scope**: Variant naming, inheritance, smart routing, multi-instance hiring, utilization, overflow, AI pipeline awareness

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
