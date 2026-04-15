# ERROR_LOG.md — Error Tracking Log

> **Technical Assistant v9 Requirement** — Track recurring errors, patterns, and resolutions.

## Protocol

- Log errors that require investigation or reveal systemic issues
- Include resolution steps taken
- Mark resolved entries with ✅

---

## 2026-04-03 [Day 35] Week 4 Complete

**Status:** ✅ Week 4 (Days 24-35) completed successfully.

**Summary:**
- 3896 total tests passing
- All 70 items from WEEK4_ROADMAP.md implemented
- Shared test fixtures created at `tests/fixtures/ticket_fixtures.py`
- No test isolation issues found (BL09 resolved or not present)
- Documentation updated for Week 4 completion

**Key Items Implemented:**
- BL01-BL09: All code loopholes fixed
- PS01-PS17: All MUST and SHOULD production situation handlers
- MF01-MF12: All MUST and SHOULD missing features
- F-046 to F-052, F-070: All original roadmap features

---

## 2026-04-02 [Day 23] Webhook handler import issues

**Error:** `ImportError: cannot import name 'dispatch_event'` when importing webhook_tasks before handlers are registered.

**Root Cause:** Handlers use `@register_handler` decorator which registers them at import time. If `dispatch_event` is called before the handler module is imported, the registry is empty.

**Resolution:** ✅ `webhook_tasks.py` imports all 4 handler modules at the bottom of the file with `noqa: F401`, ensuring registration happens before any task execution.

---

## 2026-04-01 [Day 22] Celery tasks fail in test without ENVIRONMENT=test

**Error:** `CELERY_BROKER_URL` not set causes tasks to fail during test collection.

**Resolution:** ✅ `tests/conftest.py` sets `os.environ["ENVIRONMENT"] = "test"` before any app imports. `test_day22_setup.py` calls `setup_day22_tests()` at module level to configure Celery.

---

## 2026-04-01 [Day 21] Health check bottleneck

**Error:** Health endpoint called too frequently causes DB connection pool exhaustion.

**Resolution:** ✅ Health results cached for 10 seconds using `functools.lru_cache` with time-based invalidation (L64).

---

## 2026-03-31 [Day 20] Cross-tenant data leak in raw SQL

**Error:** Raw SQL queries bypass SQLAlchemy's automatic tenant filtering.

**Resolution:** ✅ Created `@bypass_tenant` decorator with admin-only access. All raw SQL queries require explicit opt-in with audit logging.

---

## 2026-03-30 [Day 19] Socket.io event rate limiting

**Error:** Clients can spam events without rate limiting, causing server overload.

**Resolution:** ✅ Added per-tenant rate limiting (100 events/sec) with Redis-backed token bucket (L59).

---

## 2026-03-29 [Day 16] Dead letter queue routing

**Error:** Tasks failing after max retries were silently dropped.

**Resolution:** ✅ Added DLQ routing in `ParwaTask.on_failure` when retries exhausted. `ParwaBaseTask` routes to `dead_letter` queue.
