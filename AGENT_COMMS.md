# AGENT_COMMS.md — Inter-Agent Communication Log

> **Technical Assistant v9 Requirement** — This file tracks decisions, handoffs, and context between AI agents working on PARWA.

## Protocol

- Every agent MUST read this file before starting work
- Every agent MUST append a new section when making architectural decisions
- Format: `## [Date] [Agent Name] — [Decision/Handoff]`

---

## 2026-04-03 Day 35 Agent — Week 4 Complete (Ticket System)

**Decision:** Week 4 (Days 24-35) completed with full ticket system implementation.

**Summary:**
- 12 days of development (Days 24-35)
- 3896 total tests passing
- 70 items from WEEK4_ROADMAP.md implemented
- Created shared test fixtures at `tests/fixtures/ticket_fixtures.py`

**Architecture Decisions Made:**
- Ticket state machine with 12 statuses and validated transitions
- SLA timer system with breach detection and escalation
- Omnichannel support with customer identity resolution
- Notification system with templates and preferences
- Bulk actions with undo capability
- Collision detection via Redis for concurrent editing
- Real-time events via Socket.io (16 event types)
- Celery tasks for async processing (SLA, stale, spam, bulk)

**Key Services Implemented:**
- `ticket_service.py` — Core CRUD with state machine
- `sla_service.py` — SLA policy and timer management
- `assignment_service.py` — Score-based routing
- `notification_service.py` — Multi-channel dispatch
- `template_service.py` — Response templates
- `trigger_service.py` — Automation rules engine
- `collision_service.py` — Concurrent editing detection
- `ticket_analytics_service.py` — Dashboard metrics

**Next Steps:** Week 5 - Paddle billing integration

---

## 2026-04-02 Day 23 Agent — Webhook Handler Registry Architecture

**Decision:** Created a registry pattern for webhook handlers instead of if/else chains.

- `backend/app/webhooks/__init__.py` — Central handler registry with `register_handler` decorator
- Each provider handler registers itself via `@register_handler("provider")`
- `dispatch_event(provider, event)` routes to the correct handler
- `webhook_tasks.py` updated to use `dispatch_event()` instead of direct `_process_*` functions
- **Rationale:** Open-closed principle — new providers can be added without modifying existing code
- **Trade-off:** Slightly more indirection, but much cleaner separation of concerns

---

## 2026-04-02 Day 23 Agent — Email Template Design Decisions

**Decision:** All 8 email templates use Jinja2 inheritance from `base.html`.

- Templates use `{{ variable }}` syntax for dynamic content (XSS safe in Jinja2 auto-escaping)
- No raw HTML insertion from user data — all variables pass through Jinja2's auto-escape
- Templates include actionable CTA buttons linking to PARWA dashboard
- Footer is standardized across all templates

---

## 2026-04-01 Day 22 Agent — Celery Task Module Pattern

**Decision:** All Day 22 task modules follow a consistent pattern.

- `ParwaBaseTask` as base class with `@with_company_id` decorator
- Each task returns a structured dict with `status`, relevant IDs, and timestamps
- Queue routing via `@app.task(queue=..., base=ParwaBaseTask)`
- Time limits: `soft_time_limit < time_limit` on every task (L67)
- Beat dispatch tasks wrap business tasks with error handling for empty company lists

---

## 2026-04-01 Day 21 Agent — Health Check Architecture

**Decision:** Health checks follow a dependency-aware pattern.

- If DB is down, Celery and Redis-dependent checks show "degraded" not "down"
- Health results cached for 10s to prevent bottleneck
- External API checks are non-blocking with configurable timeouts
- Prometheus metrics follow standard naming: `parwa_<subsystem>_<metric>`

---

## 2026-03-31 Day 20 Agent — Tenant Context Propagation

**Decision:** company_id flows from API → Celery → DB → Redis.

- `set_task_tenant_header(company_id)` creates headers for task dispatch
- `ParwaTask.__call__()` auto-sets tenant context from headers
- `@inject_tenant_context` decorator as safety net for tasks bypassing base class
- Thread-local storage for tenant context in sync code
