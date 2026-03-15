# AGENT_COMMS.md — Week 4 Day 2
# Last updated: 2026-03-28
# Current status: WEEK 4 DAY 2 STARTED

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 4 DAY 2 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-28

> **Phase: Phase 2 — Core AI Engine (API Layer)**
> Day 1 is COMPLETE ✅ — Auth API, License API, Auth Core, License Manager all built.
> 316 tests passing. All builders verified.
>
> Day 2: Building Support, Dashboard, Billing, and Compliance APIs.
> All 4 API routes are independent — build in parallel.
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
8. If PASS → `git add [file] && git commit -m "Week 4 Day 2: Builder 1 - [description]" && git push origin main`
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
8. If PASS → `git add [file] && git commit -m "Week 4 Day 2: Builder 2 - [description]" && git push origin main`
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
8. If PASS → `git add [file] && git commit -m "Week 4 Day 2: Builder 3 - [description]" && git push origin main`
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
8. If PASS → `git add [file] && git commit -m "Week 4 Day 2: Builder 4 - [description]" && git push origin main`
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
## MANAGER → DAY 2 TASK ASSIGNMENTS
═══════════════════════════════════════════════════════════════════════════════

### AGENT 1

**File:** `backend/api/support.py`
**What:** Support ticket API routes — create, list, update, escalate tickets
**Depends On:**
- `backend/models/support_ticket.py` (Wk3)
- `backend/models/user.py` (Wk3)
- `backend/models/company.py` (Wk3)
- `backend/app/database.py` (Wk2)
- `backend/core/auth.py` (Wk4 Day 1)
**Test File:** `tests/unit/test_support.py`
**BDD:** `docs/bdd_scenarios/parwa_bdd.md` — Support Ticket section
**Pass Criteria:** Unit test passes, pushed to GitHub, CI green

**Responsibilities:**
- `POST /support/tickets` — Create new support ticket
- `GET /support/tickets` — List tickets with filtering (status, priority, assignee)
- `GET /support/tickets/{id}` — Get ticket details
- `PUT /support/tickets/{id}` — Update ticket (status, priority, assignee)
- `POST /support/tickets/{id}/escalate` — Escalate ticket to manager
- `POST /support/tickets/{id}/messages` — Add message to ticket
- Input validation on all endpoints
- Company-scoped data access (RLS enforcement)

---

### AGENT 2

**File:** `backend/api/dashboard.py`
**What:** Dashboard API routes — stats, metrics, activity feed
**Depends On:**
- `backend/models/*.py` (all models from Wk3)
- `backend/app/database.py` (Wk2)
- `backend/core/auth.py` (Wk4 Day 1)
**Test File:** `tests/unit/test_dashboard.py`
**BDD:** `docs/bdd_scenarios/parwa_bdd.md` — Dashboard section
**Pass Criteria:** Unit test passes, pushed to GitHub, CI green

**Responsibilities:**
- `GET /dashboard/stats` — Get company statistics (tickets, users, SLA)
- `GET /dashboard/activity` — Get recent activity feed
- `GET /dashboard/metrics` — Get KPI metrics (response time, resolution rate)
- `GET /dashboard/tickets/summary` — Get ticket summary by status/priority
- `GET /dashboard/team/performance` — Get team performance metrics
- Date range filtering on all metrics endpoints
- Company-scoped data access

---

### AGENT 3

**File:** `backend/api/billing.py`
**What:** Billing API routes — subscriptions, invoices, payment methods
**Depends On:**
- `backend/models/subscription.py` (Wk3)
- `backend/models/company.py` (Wk3)
- `backend/app/database.py` (Wk2)
- `backend/core/auth.py` (Wk4 Day 1)
**Test File:** `tests/unit/test_billing.py`
**BDD:** `docs/bdd_scenarios/parwa_bdd.md` — Billing section
**Pass Criteria:** Unit test passes, pushed to GitHub, CI green

**Responsibilities:**
- `GET /billing/subscription` — Get current subscription details
- `PUT /billing/subscription` — Update subscription tier
- `GET /billing/invoices` — List invoices
- `GET /billing/invoices/{id}` — Get invoice details
- `POST /billing/payment-method` — Add payment method (mocked)
- `GET /billing/usage` — Get current usage vs limits
- **CRITICAL:** Never call Stripe without pending_approval record
- Tier upgrade/downgrade logic

---

### AGENT 4

**File:** `backend/api/compliance.py`
**What:** Compliance API routes — GDPR requests, data export, audit logs
**Depends On:**
- `backend/models/compliance_request.py` (Wk3)
- `backend/models/audit_trail.py` (Wk3)
- `backend/app/database.py` (Wk2)
- `backend/core/auth.py` (Wk4 Day 1)
**Test File:** `tests/unit/test_compliance_api.py`
**BDD:** `docs/bdd_scenarios/parwa_bdd.md` — Compliance section
**Pass Criteria:** Unit test passes, pushed to GitHub, CI green

**Responsibilities:**
- `POST /compliance/gdpr/export` — Request data export (GDPR)
- `POST /compliance/gdpr/delete` — Request data deletion (GDPR)
- `GET /compliance/requests` — List compliance requests
- `GET /compliance/audit-log` — Get audit log entries
- `GET /compliance/audit-log/{id}` — Get specific audit entry
- `POST /compliance/retention/check` — Check data retention status
- Request status tracking (pending, processing, completed)

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS — UPDATE AFTER COMPLETING YOUR TASK
═══════════════════════════════════════════════════════════════════════════════

## BUILDER 1 → STATUS
**File:** `backend/api/support.py`
**Status:** DONE
**Unit Test:** PASS (32 tests, 0 failures)
**Test File:** `tests/unit/test_support.py`
**Pushed:** YES
**Commit:** 29c96e5
**Initiative Files:** NONE
**Notes:**
- Implemented Support Ticket API with 6 endpoints:
  - POST /support/tickets — Create new support ticket
  - GET /support/tickets — List tickets with filtering (status, channel, assignee)
  - GET /support/tickets/{id} — Get ticket details
  - PUT /support/tickets/{id} — Update ticket (status, category, assignee, AI fields)
  - POST /support/tickets/{id}/escalate — Escalate ticket to manager
  - POST /support/tickets/{id}/messages — Add message to ticket
- All endpoints include proper input validation, error handling, and structured logging
- Company-scoped data access (RLS enforcement) - users can only access tickets from their company
- Type hints and docstrings on all functions and classes
- Tests cover: schema validation, enum values, helper functions, auth requirements, UUID validation, pagination

---

## BUILDER 2 → STATUS
**File:** backend/api/dashboard.py
**Status:** DONE
**Unit Test:** PASS (15/15 tests)
**Test File:** tests/unit/test_dashboard.py
**Pushed:** YES
**Initiative Files:** NONE
**Notes:** Built 5 dashboard endpoints: GET /dashboard/stats, GET /dashboard/activity, GET /dashboard/metrics, GET /dashboard/tickets/summary, GET /dashboard/team/performance. All with date range filtering and company-scoped data access (RLS). Type hints and docstrings on all functions. Error handling on all external calls.

---

## BUILDER 3 → STATUS
**File:** [fill after completion]
**Status:** PENDING / IN PROGRESS / DONE / STUCK
**Unit Test:** [PASS/FAIL]
**Test File:** tests/unit/test_billing.py
**Pushed:** [YES/NO]
**Initiative Files:** [any extra files or NONE]
**Notes:** [anything relevant]

---

## BUILDER 4 → STATUS
**File:** [fill after completion]
**Status:** PENDING / IN PROGRESS / DONE / STUCK
**Unit Test:** [PASS/FAIL]
**Test File:** tests/unit/test_compliance_api.py
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
