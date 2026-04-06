# PROJECT_STATE.md — Live Project State Memory

> **Technical Assistant v9 Requirement** — Current state of the project for agent continuity.

## Project Overview

- **Name:** PARWA AI Workforce
- **Stack:** FastAPI + Next.js 15 + PostgreSQL + Redis + Celery + Socket.io + Paddle + Brevo + Twilio
- **Phase:** Phase 2 — Core Business Logic (Week 4 COMPLETE)
- **Current Status:** Week 4 Days 24-35 DONE — 3896 tests passing
- **Week 4 Roadmap:** `WEEK4_ROADMAP.md` — 12-day plan completed, 70 items implemented

## Progress

| Week | Days | Tests | Loopholes | Status |
|------|------|-------|-----------|--------|
| Week 1 | Days 1-7 | 1-700 | L1-L15 | ✅ Complete |
| Week 2 | Days 8-14 | 700-1370 | L16-L44 | ✅ Complete |
| Week 3 (Infra) | Days 15-18 | 1370-1471 | L45-L58 | ✅ Complete |
| Week 3 (Real) | Days 19-22 | 1471-2029 | L59-L68 | ✅ Complete |
| Week 3 (Final) | Day 23 | 2029→~2100 | L68→~L74 | ✅ Complete |
| Week 4 | Days 24-35 | 2100→3896 | BL01-BL09 | ✅ Complete |

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

## Week 4 Plan (Days 24-35)

See `WEEK4_ROADMAP.md` for complete 12-day breakdown.

| Day | Focus | Items |
|-----|-------|-------|
| 24 ✅ | Models + Enums + BL fixes | BL01, BL02 (models), BL04, MF01-03 |
| 25 ✅ | Migration + Schemas | BL02 (migration), F-046/047 schemas |
| 26 ✅ | Ticket CRUD + API | F-046, BL05, BL06, BL07, PS01/05/07/09 |
| 27 ✅ | Conversation + Activity Log | F-047, MF04, BL08 |
| 28 ✅ | Search + Classification + Assignment | F-048, F-049, F-050 |
| 29 ✅ | Bulk Actions + Merge + SLA | F-051, MF06, PS11, PS17 |
| 30 ✅ | Omnichannel + Identity | F-052, F-070, PS08/13/14 |
| 31 ✅ | Notifications + Email Templates | MF05, PS03/10 |
| 32 ✅ | Production Situation Handlers | PS01-10, PS15, BL09 |
| 33 ✅ | SHOULD-HAVE Features | MF07-12, PS12/16 |
| 34 ✅ | Socket.io + Tasks + Analytics | MF10, BL08, all event wiring |
| 35 ✅ | Full Tests + BL09 Fix + Docs | BL09, regression |

## Next Steps (After Week 4)

- Week 5: Paddle billing integration (F-020 to F-027)
- Week 6: Onboarding system (F-028 to F-035)
- Week 7: Approval system (F-074 to F-086)
