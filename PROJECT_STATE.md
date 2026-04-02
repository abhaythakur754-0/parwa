# PROJECT_STATE.md — Live Project State Memory

> **Technical Assistant v9 Requirement** — Current state of the project for agent continuity.

## Project Overview

- **Name:** PARWA AI Workforce
- **Stack:** FastAPI + Next.js 15 + PostgreSQL + Redis + Celery + Socket.io + Paddle + Brevo + Twilio
- **Phase:** Phase 1 — Foundation (Week 3 of 3, Day 23 of 23)
- **Current Status:** Week 3 Day 23 in progress — Final day of Phase 1

## Progress

| Week | Days | Tests | Loopholes | Status |
|------|------|-------|-----------|--------|
| Week 1 | Days 1-7 | 1-700 | L1-L15 | ✅ Complete |
| Week 2 | Days 8-14 | 700-1370 | L16-L44 | ✅ Complete |
| Week 3 (Infra) | Days 15-18 | 1370-1471 | L45-L58 | ✅ Complete |
| Week 3 (Real) | Days 19-22 | 1471-2029 | L59-L68 | ✅ Complete |
| Week 3 (Final) | Day 23 | 2029→~2100 | L68→~L74 | 🔲 In Progress |

## Key Architecture Decisions

1. **Tenant Isolation:** company_id flows from JWT → middleware → DB queries → Celery tasks → Redis keys
2. **Task Pattern:** All Celery tasks use `ParwaBaseTask` + `@with_company_id` + exponential backoff
3. **Webhook Flow:** HMAC verify → store event → dispatch to Celery → provider handler via registry
4. **Event System:** Socket.io with typed events, emit helpers, tenant rooms, reconnection buffer
5. **Health Checks:** Dependency-aware with Prometheus metrics, Grafana dashboards, alerting rules

## File Structure (Key Dirs)

```
backend/app/
├── api/           # FastAPI routes
├── core/          # Config, socketio, health, metrics, events
├── middleware/     # Auth, tenant, CORS
├── models/        # SQLAlchemy models
├── schemas/       # Pydantic schemas
├── security/      # HMAC, JWT, encryption
├── services/      # Business logic
├── tasks/         # Celery tasks (7 queues)
├── templates/emails/  # Jinja2 email templates (8)
├── webhooks/      # Provider webhook handlers (Day 23)
└── main.py        # FastAPI app
```

## Testing

- **Framework:** pytest
- **Location:** `tests/unit/`
- **Pattern:** `tests/conftest.py` sets ENVIRONMENT=test before imports
- **Celery:** Tests use EAGER mode via `setup_day22_tests()`

## Build Codes (Active)

- BC-001: Multi-tenant isolation
- BC-003: Webhook processing (idempotent, <3s, async)
- BC-004: Celery task pattern
- BC-005: Socket.io event system
- BC-011: HMAC constant-time comparison
- BC-012: Structured logging (no stack traces)

## Next Steps (After Day 23)

- Phase 2: Core Business Logic
- Week 5: Paddle billing integration (F-020 to F-027)
- Week 6: Email pipeline (F-120 to F-124)
- Week 13: SMS/voice (F-126, F-127)
- Week 17: Shopify integration (F-131)
