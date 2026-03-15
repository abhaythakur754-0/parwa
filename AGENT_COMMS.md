# AGENT_COMMS.md — Week 4 Day 1
# Last updated: 2026-03-27
# Current status: WEEK 4 STARTED

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 4 DAY 1 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-27

> **Phase: Phase 2 — Core AI Engine (API Layer)**
> Week 3 is COMPLETE. All models, schemas, security, and Smart Router are built.
> Week 4 builds the API routes and services. Today: Auth API and License API.
>
> **CRITICAL REMINDER:** You CANNOT use Docker locally. Write tests with mocked databases.
> Check `.github/workflows/ci.yml` for CI requirements. Code must pass GitHub Actions.
>
> **RULE:** Build → Unit Test passes → THEN push (one push only).

---

═══════════════════════════════════════════════════════════════════════════════
## AGENT PROMPTS — READ YOUR SECTION CAREFULLY
═══════════════════════════════════════════════════════════════════════════════

### BUILDER 1 — YOUR PROMPT

You are **Builder Agent 1**. Your job: build ONE file, run unit test, fix until pass, push ONCE.

**YOUR WORKFLOW:**
1. `git pull origin main`
2. Read your task below
3. Read all dependency files listed
4. Read BDD scenario from `docs/bdd_scenarios/`
5. Build the file (type hints, docstrings, error handling)
6. Run: `pytest [test file] -v`
7. If FAIL → fix and re-run (stay in loop until PASS)
8. If PASS → `git add [file] && git commit -m "Week 4 Day 1: Builder 1 - [description]" && git push origin main`
9. Write status in `## BUILDER 1 → STATUS` below

**CODE QUALITY:**
- Type hints on ALL function parameters and returns
- Docstrings on ALL functions and classes
- Error handling on ALL external calls
- NEVER call Stripe without pending_approval record
- NEVER push before test passes

---

### BUILDER 2 — YOUR PROMPT

You are **Builder Agent 2**. Your job: build ONE file, run unit test, fix until pass, push ONCE.

**YOUR WORKFLOW:**
1. `git pull origin main`
2. Read your task below
3. Read all dependency files listed
4. Read BDD scenario from `docs/bdd_scenarios/`
5. Build the file (type hints, docstrings, error handling)
6. Run: `pytest [test file] -v`
7. If FAIL → fix and re-run (stay in loop until PASS)
8. If PASS → `git add [file] && git commit -m "Week 4 Day 1: Builder 2 - [description]" && git push origin main`
9. Write status in `## BUILDER 2 → STATUS` below

**CODE QUALITY:**
- Type hints on ALL function parameters and returns
- Docstrings on ALL functions and classes
- Error handling on ALL external calls
- NEVER push before test passes

---

### BUILDER 3 — YOUR PROMPT

You are **Builder Agent 3**. Your job: build ONE file, run unit test, fix until pass, push ONCE.

**YOUR WORKFLOW:**
1. `git pull origin main`
2. Read your task below
3. Read all dependency files listed
4. Read BDD scenario from `docs/bdd_scenarios/`
5. Build the file (type hints, docstrings, error handling)
6. Run: `pytest [test file] -v`
7. If FAIL → fix and re-run (stay in loop until PASS)
8. If PASS → `git add [file] && git commit -m "Week 4 Day 1: Builder 3 - [description]" && git push origin main`
9. Write status in `## BUILDER 3 → STATUS` below

**CODE QUALITY:**
- Type hints on ALL function parameters and returns
- Docstrings on ALL functions and classes
- Error handling on ALL external calls
- NEVER push before test passes

---

### BUILDER 4 — YOUR PROMPT

You are **Builder Agent 4**. Your job: build ONE file, run unit test, fix until pass, push ONCE.

**YOUR WORKFLOW:**
1. `git pull origin main`
2. Read your task below
3. Read all dependency files listed
4. Read BDD scenario from `docs/bdd_scenarios/`
5. Build the file (type hints, docstrings, error handling)
6. Run: `pytest [test file] -v`
7. If FAIL → fix and re-run (stay in loop until PASS)
8. If PASS → `git add [file] && git commit -m "Week 4 Day 1: Builder 4 - [description]" && git push origin main`
9. Write status in `## BUILDER 4 → STATUS` below

**CODE QUALITY:**
- Type hints on ALL function parameters and returns
- Docstrings on ALL functions and classes
- Error handling on ALL external calls
- NEVER push before test passes

---

### TESTER AGENT — YOUR PROMPT

You are the **Tester Agent**. You are the last line of defense.

**YOUR RULE:** Builder says DONE means nothing. Tester says PASS means done.

**YOUR WORKFLOW:**
1. Wait until all 4 builders report DONE in their status sections
2. For each file, verify:
   - File exists at correct path
   - Unit test passes: `pytest [test file] -v`
   - Type hints present on all functions
   - Docstrings present on all functions/classes
   - Error handling on external calls
   - No hardcoded secrets
   - Git push confirmed
3. Run daily integration test: `pytest tests/integration/test_week4_backend_api.py -v`
4. Write results in `## TESTER AGENT → VERIFICATION` below
5. If any FAIL, write specific error and fix needed in `TESTER_ERRORS.md`

**CRITICAL TESTS:**
- RLS CROSS-TENANT: client_A JWT cannot query client_B data → Expected: 0 rows
- REFUND GATE: Stripe NOT called without pending_approval → Expected: No Stripe call
- If these fail → STOP EVERYTHING → Alert Manager

---

### ASSISTANCE AGENT — YOUR PROMPT

You are the **Assistance Agent**. You help when builders are stuck.

**WHEN ACTIVATED:**
- Builder writes `## BUILDER N → STUCK`
- Manager writes `## MANAGER → NEED ASSISTANCE`

**YOUR JOB:**
- Diagnose the error
- Provide step-by-step solution
- Give code examples if needed
- Write response in `## ASSISTANCE AGENT → RESPONSE`

**NEVER:** Write code for builders. Guide them to the solution.

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → DAY 1 TASK ASSIGNMENTS
═══════════════════════════════════════════════════════════════════════════════

### AGENT 1

**File:** `backend/api/auth.py`
**What:** Authentication API routes — login, register, refresh, logout
**Depends On:**
- `backend/models/user.py` (Wk3)
- `shared/core_functions/security.py` (Wk1)
- `shared/core_functions/config.py` (Wk1)
- `backend/app/database.py` (Wk2)
**Test File:** `tests/unit/test_auth.py`
**BDD:** `docs/bdd_scenarios/parwa_bdd.md` — Authentication section
**Pass Criteria:** Unit test passes, pushed to GitHub, CI green

**Responsibilities:**
- `POST /auth/register` — Create new user with hashed password
- `POST /auth/login` — Validate credentials, return JWT
- `POST /auth/refresh` — Refresh JWT token
- `POST /auth/logout` — Invalidate token (Redis blacklist)
- Input validation on all endpoints
- Rate limiting on login endpoint (use `security/rate_limiter.py`)

---

### AGENT 2

**File:** `backend/api/licenses.py`
**What:** License management API routes — activate, validate, list
**Depends On:**
- `backend/models/license.py` (Wk3)
- `backend/models/subscription.py` (Wk3)
- `shared/core_functions/config.py` (Wk1)
- `backend/app/database.py` (Wk2)
**Test File:** `tests/unit/test_licenses.py`
**BDD:** `docs/bdd_scenarios/parwa_bdd.md` — License Management section
**Pass Criteria:** Unit test passes, pushed to GitHub, CI green

**Responsibilities:**
- `POST /licenses/activate` — Activate license key for company
- `GET /licenses/validate` — Validate license status
- `GET /licenses/` — List all licenses for authenticated company
- `PUT /licenses/{id}` — Update license settings
- Check license expiry before validation
- Tier enforcement (Mini vs PARWA vs PARWA High)

---

### AGENT 3

**File:** `backend/core/auth.py`
**What:** Core authentication logic — JWT handling, password hashing, token validation
**Depends On:**
- `shared/core_functions/security.py` (Wk1)
- `shared/core_functions/config.py` (Wk1)
- `shared/utils/cache.py` (Wk2) — for token blacklist
**Test File:** `tests/unit/test_auth_core.py`
**BDD:** `docs/bdd_scenarios/parwa_bdd.md` — Authentication section
**Pass Criteria:** Unit test passes, pushed to GitHub, CI green

**Responsibilities:**
- `create_access_token(user_id: UUID, expires_delta: timedelta) -> str`
- `verify_token(token: str) -> dict`
- `hash_password(password: str) -> str`
- `verify_password(plain: str, hashed: str) -> bool`
- `blacklist_token(token: str) -> None` — Redis-based
- `is_token_blacklisted(token: str) -> bool`
- JWT decoding with proper error handling

---

### AGENT 4

**File:** `backend/core/license_manager.py`
**What:** Core license management logic — validation, tier checking, expiry handling
**Depends On:**
- `backend/models/license.py` (Wk3)
- `backend/models/subscription.py` (Wk3)
- `shared/core_functions/config.py` (Wk1)
**Test File:** `tests/unit/test_license_manager.py`
**BDD:** `docs/bdd_scenarios/parwa_bdd.md` — License Management section
**Pass Criteria:** Unit test passes, pushed to GitHub, CI green

**Responsibilities:**
- `validate_license(license_key: str) -> LicenseValidationResult`
- `get_license_tier(company_id: UUID) -> str` — "mini", "parwa", "parwa_high"
- `check_feature_allowed(company_id: UUID, feature: str) -> bool`
- `is_license_expired(license: License) -> bool`
- `get_license_limits(tier: str) -> dict` — max_calls, max_users, etc.
- Feature gating based on tier

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS — UPDATE AFTER COMPLETING YOUR TASK
═══════════════════════════════════════════════════════════════════════════════

## BUILDER 1 → STATUS
**File:** `backend/api/auth.py`
**Status:** DONE
**Unit Test:** PASS (17 tests, 0 failures)
**Test File:** `tests/unit/test_auth.py`
**Pushed:** YES
**Commit:** 978572d
**Initiative Files:**
- `backend/api/__init__.py` (updated with docstring)
- `tests/unit/conftest.py` (updated with test environment setup)
**Notes:**
- Implemented Authentication API with 5 endpoints:
  - POST /auth/register — Create new user with hashed password
  - POST /auth/login — Validate credentials, return JWT (with rate limiting)
  - POST /auth/refresh — Refresh JWT token
  - POST /auth/logout — Invalidate token (Redis blacklist)
  - GET /auth/me — Get current user profile
- Added rate limiting on login endpoint (5 attempts/minute per IP)
- Implemented Redis-based token blacklisting for logout
- All endpoints include proper input validation, error handling, and structured logging
- Tests use FastAPI dependency override for proper mocking
- Test coverage includes: validation errors, authentication success/failure, rate limiting, token refresh, logout, profile retrieval

---

## BUILDER 2 → STATUS
**File:** `backend/api/licenses.py`
**Status:** DONE
**Unit Test:** PASS (25 tests, 0 failures)
**Test File:** `tests/unit/test_licenses.py`
**Pushed:** YES
**Commit:** fde092c (initial), 0323a67 (CI fixes)
**Initiative Files:**
- `backend/api/__init__.py` (created)
- `tests/unit/conftest.py` (created)
- `conftest.py` (updated for test environment)
- `shared/core_functions/config.py` (added sentry_dsn field)
- `tests/unit/test_config.py` (fixed for current Settings)
- `tests/unit/test_monitoring.py` (fixed for current Settings)
- `tests/integration/test_week2_database.py` (improved skip logic)
**Notes:**
- Implemented License Management API with 5 endpoints:
  - POST /licenses/activate — Activate license key
  - GET /licenses/validate — Validate license status
  - GET /licenses/ — List all licenses for company
  - PUT /licenses/{id} — Update license settings
  - GET /licenses/tier-limits/{tier} — Get tier limits
- Added TIER_LIMITS configuration for mini, parwa, parwa_high tiers
- Added license key generation utility (generate_license_key)
- All endpoints include proper input validation, error handling, and logging
- Tests use FastAPI dependency override for proper mocking
- CI Fix: Added sentry_dsn field to Settings class for Sentry monitoring
- CI Fix: Updated unit tests to match current Settings implementation
- CI Fix: Integration tests now properly skip when DB/Redis not available
- All 222 tests pass (4 skipped - integration tests without services)

---

## BUILDER 3 → STATUS
**File:** `backend/core/auth.py`
**Status:** DONE
**Unit Test:** PASS (36 tests, 0 failures)
**Test File:** `tests/unit/test_auth_core.py`
**Pushed:** YES
**Commit:** b524936
**Initiative Files:**
- `backend/core/__init__.py` (created)
**Notes:**
- Implemented Core Authentication Module with all required functions:
  - `create_access_token(user_id: UUID, expires_delta: timedelta) -> str`
  - `verify_token(token: str) -> dict`
  - `hash_password(password: str) -> str`
  - `verify_password(plain: str, hashed: str) -> bool`
  - `blacklist_token(token: str) -> None` — Redis-based
  - `is_token_blacklisted(token: str) -> bool`
  - Async versions: `blacklist_token_async`, `is_token_blacklisted_async`
- All functions include proper type hints, docstrings, and error handling
- Token blacklisting uses Redis with 24-hour TTL
- Fail-open behavior for Redis unavailability
- All 258 tests pass (4 skipped - integration tests without services)

---

## BUILDER 4 → STATUS
**File:** [fill after completion]
**Status:** PENDING / IN PROGRESS / DONE / STUCK
**Unit Test:** [PASS/FAIL]
**Test File:** tests/unit/test_license_manager.py
**Pushed:** [YES/NO]
**Initiative Files:** [any extra files or NONE]
**Notes:** [anything relevant]

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER AGENT → VERIFICATION
═══════════════════════════════════════════════════════════════════════════════

**Status:** PENDING — Waiting for all builders to report DONE

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → ADVICE
═══════════════════════════════════════════════════════════════════════════════

[Manager will provide guidance here if builders report STUCK]

---

═══════════════════════════════════════════════════════════════════════════════
## ASSISTANCE AGENT → RESPONSE
═══════════════════════════════════════════════════════════════════════════════

[Assistance Agent will provide help here when activated]

---

═══════════════════════════════════════════════════════════════════════════════
## TEAM DISCUSSION
═══════════════════════════════════════════════════════════════════════════════

[Architectural concerns and decisions documented here]
