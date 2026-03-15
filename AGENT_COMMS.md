# AGENT_COMMS.md — Week 3 Day 6
# Last updated: 2026-03-14
# Current status: TESTING IN PROGRESS

═══════════════════════════════════════════════════════════
## MANAGER → WEEK 3 DAY 6 ASSIGNMENT (INTEGRATION)
═══════════════════════════════════════════════════════════
Written by: Manager Agent (Antigravity)
Date: 2026-03-14

> **Phase: Weekly Integration**
> All development for Week 3 is finished.
> **TESTER AGENT:** You are tasked with running the full integration suite to close the week.
> **Command:** `pytest tests/integration/test_week3_integration.py -v`
> 
> **Verification Requirements:**
> 1. Confirm all backend models result in correct DB table creation.
> 2. Verify RLS policies correctly isolate company data (Cross-Tenant check).
> 3. Verify Smart Router failover resilience.
> 4. Verify HMAC security utilities for webhook safety.
>
> Report results in ## TESTER AGENT → VERIFICATION. Use status "WEEK COMPLETE" only if all tests PASS.
Written by: Manager Agent (Antigravity)
Date: 2026-03-14

> Week 3 Day 4 (Smart Router) is COMPLETE. All failover and cost logic verified.
> Today is Day 5: Backend Core & Rate Limiting.
> We are building the FastAPI entry point and the core security middlewares. This is the "Glue" that connects models and schemas to the web.
> RULE REMINDER: Build → Unit Test passes → THEN push.

---

### AGENT 1
**File to Build:** `security/rate_limiter.py`

**What Is This File?:**
Redis-backed rate limiting utility for protects our API endpoints from abuse.

**Responsibilities:**
- `RateLimiter` class.
- `is_allowed(key: str, limit: int, window: int) -> bool` function.
- Integrated with Redis (from `shared/utils/cache.py`).

**Depends On:**
- `shared/core_functions/config.py` (Wk1)
- `shared/utils/cache.py` (Wk2)

**Expected Output:**
Rate limiter correctly rejects requests exceeding the threshold.

**Unit Test File:** `tests/unit/test_security.py`
- Test: Consecutive calls within window increment counter.
- Test: Limit exceeded returns `False`.

**BDD Scenario:** `docs/bdd_scenarios/parwa_bdd.md` — Rate Limiting section.

---

### AGENT 2
**File to Build:** `security/feature_flags.py`

**What Is This File?:**
Utility to check feature status per-company or globally.

**Responsibilities:**
- `FeatureManager` class.
- `is_enabled(feature_name: str, company_id: UUID) -> bool`.
- Loads flags from `feature_flags/*.json` (Wk1) and caches in Redis.

**Depends On:**
- `shared/utils/cache.py`
- `shared/core_functions/config.py`

**Expected Output:**
Ability to toggle features like "Agent Lightning" or "Smart Router" dynamically.

**Unit Test File:** `tests/unit/test_security.py`
- Test: Override flag for specific company works.

---

### AGENT 3
**Actual Output:** Successfully initialized the FastAPI application with a dedicated `/health` endpoint and shared dependencies. Implemented a robust `get_db` async generator in `dependencies.py` for automated session lifecycle management. Verified app liveness and dependency injection with unit tests.
- File Built: `backend/app/main.py` + `backend/app/dependencies.py`
- Unit Test: PASS (via `tests/unit/test_app.py`)
- Commit: 379826e781a327247b464669133dfbc

---

### AGENT 4
**File to Build:** `backend/app/middleware.py` AND `backend/app/config.py`

**What Is This File?:**
Global application configuration and custom middlewares (Logging, RLS context, Error handling).

**Responsibilities:**
- `middleware.py`: `ContextMiddleware` to inject correlation IDs and `app.current_company_id` for RLS.
- `config.py`: Specialized app-level settings (FastAPI specific).

**Depends On:**
- `shared/utils/logger.py`
- `shared/utils/error_handlers.py`

**Expected Output:**
Middleware correctly traces requests and sets SQL context variables.

**Unit Test File:** `tests/unit/test_app.py`
- Test: Middleware attaches X-Correlation-ID to Response.

---

═══════════════════════════════════════════════════════════
## AGENT STATUS
═══════════════════════════════════════════════════════════
### AGENT 2
**Actual Output:** Implemented the `FeatureManager` in `security/feature_flags.py`. The utility supports global tiered flags (loaded from JSON) and per-company overrides with Redis caching. Precedence: Override > Cache > JSON.
- File Built: `security/feature_flags.py`
- Unit Test: PASS (10 tests in `tests/unit/test_security.py`)
- Commit: ca6ef4d

### AGENT 4
**Actual Output:** Successfully implemented global `ContextMiddleware` for request tracing and RLS support. Created `AppConfig` for FastAPI settings. Verified headers and request state injection with unit tests.
- File Built: `backend/app/middleware.py` + `backend/app/config.py`
- Unit Test: PASS
- Commit: b5d9450

### AGENT 1
**Actual Output:** Completed. `RateLimiter` implemented with Redis increment/expire logic. Verified sliding-window/fixed-window isolation via unit tests.
- File Built: `security/rate_limiter.py`
- Unit Test: PASS
- Commit: d82f1b4

---

═══════════════════════════════════════════════════════════
## TESTER AGENT → VERIFICATION
═══════════════════════════════════════════════════════════
**Task:** Verify all 4 agents' Actual Output for Backend Core & Rate Limiting. Run all regression tests.

**Verification Result:** Week 3 Day 5 verified. 
- `backend/app/main.py`: Verified. Healthy liveness check.
- `backend/app/middleware.py`: Verified. Tracing and RLS context injected correctly.
- `security/feature_flags.py`: Verified. Correct precedence logic.
- `security/rate_limiter.py`: Verified. Atomic Redis-backed counts.

Total Project Tests: 161. All PASS (Unit + Integration).

---

═══════════════════════════════════════════════════════════
## MANAGER → ADVICE
═══════════════════════════════════════════════════════════
Tester Note: Backend core is now stable. In Week 4, we will begin mounting routers for specific entities (Users, Tickets, etc.). The middleware is set up to handle the boilerplate tracing and multi-tenant isolation automatically.

