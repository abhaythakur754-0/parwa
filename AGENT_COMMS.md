# AGENT_COMMS.md — Week 4 Day 3
# Last updated: 2026-03-29
# Current status: WEEK 4 DAY 3 STARTED

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 4 DAY 3 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-29

> **Phase: Phase 2 — Core AI Engine (API Layer)**
> Day 1 is COMPLETE ✅ — Auth API, License API, Auth Core, License Manager built. 138 tests.
> Day 2 is COMPLETE ✅ — Support API, Dashboard API, Billing API, Compliance API built. 106 tests.
> 422 total tests passing. All builders verified.
>
> Day 3: Building Support, Analytics, Billing, and Onboarding Services.
> All 4 service files are independent — build in parallel.
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
8. If PASS → `git add [file] && git commit -m "Week 4 Day 3: Builder 1 - [description]" && git push origin main`
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
8. If PASS → `git add [file] && git commit -m "Week 4 Day 3: Builder 2 - [description]" && git push origin main`
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
8. If PASS → `git add [file] && git commit -m "Week 4 Day 3: Builder 3 - [description]" && git push origin main`
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
8. If PASS → `git add [file] && git commit -m "Week 4 Day 3: Builder 4 - [description]" && git push origin main`
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
## MANAGER → DAY 3 TASK ASSIGNMENTS
═══════════════════════════════════════════════════════════════════════════════

### AGENT 1

**File:** `backend/services/support_service.py`
**What:** Support ticket service layer — business logic for ticket operations
**Depends On:**
- `backend/models/support_ticket.py` (Wk3)
- `backend/models/user.py` (Wk3)
- `backend/models/company.py` (Wk3)
- `backend/app/database.py` (Wk2)
- `backend/api/support.py` (Wk4 Day 2)
**Test File:** `tests/unit/test_support_service.py`
**BDD:** `docs/bdd_scenarios/parwa_bdd.md` — Support Ticket section
**Pass Criteria:** Unit test passes, pushed to GitHub, CI green

**Responsibilities:**
- `create_ticket()` — Create new support ticket with validation
- `get_ticket_by_id()` — Fetch ticket with company-scoped access
- `list_tickets()` — List tickets with filtering and pagination
- `update_ticket()` — Update ticket status, priority, assignee
- `escalate_ticket()` — Escalate ticket to higher tier support
- `add_message()` — Add message to ticket conversation
- `calculate_sla_status()` — Check if ticket is within SLA bounds
- Company-scoped data access (RLS enforcement)
- Audit trail logging for all operations

---

### AGENT 2

**File:** `backend/services/analytics_service.py`
**What:** Analytics service layer — business logic for metrics and reporting
**Depends On:**
- `backend/models/*.py` (all models from Wk3)
- `backend/app/database.py` (Wk2)
- `backend/api/dashboard.py` (Wk4 Day 2)
**Test File:** `tests/unit/test_analytics_service.py`
**BDD:** `docs/bdd_scenarios/parwa_bdd.md` — Dashboard section
**Pass Criteria:** Unit test passes, pushed to GitHub, CI green

**Responsibilities:**
- `get_company_stats()` — Get aggregated company statistics
- `get_ticket_metrics()` — Get ticket volume and resolution metrics
- `get_response_time_metrics()` — Get average response times
- `get_agent_performance()` — Get individual agent performance data
- `get_activity_feed()` — Get recent activity for dashboard
- `calculate_sla_compliance()` — Calculate SLA compliance percentage
- Date range filtering on all metrics methods
- Company-scoped data access

---

### AGENT 3

**File:** `backend/services/billing_service.py`
**What:** Billing service layer — subscription and payment business logic
**Depends On:**
- `backend/models/subscription.py` (Wk3)
- `backend/models/company.py` (Wk3)
- `backend/app/database.py` (Wk2)
- `backend/api/billing.py` (Wk4 Day 2)
**Test File:** `tests/unit/test_billing_service.py`
**BDD:** `docs/bdd_scenarios/parwa_bdd.md` — Billing section
**Pass Criteria:** Unit test passes, pushed to GitHub, CI green

**Responsibilities:**
- `get_subscription()` — Get current subscription details
- `update_subscription_tier()` — Handle tier upgrade/downgrade
- `get_invoices()` — List invoices for company
- `get_usage()` — Get current usage vs tier limits
- `check_usage_limits()` — Validate if action is within limits
- `calculate_billing()` — Calculate monthly billing amount
- `create_pending_approval()` — Create approval record for payment actions
- **CRITICAL:** Never call Stripe without pending_approval record
- Tier pricing configuration (mini=$1000, parwa=$2500, parwa_high=$4500/month)

---

### AGENT 4

**File:** `backend/services/onboarding_service.py`
**What:** Onboarding service layer — new client setup business logic
**Depends On:**
- `backend/models/company.py` (Wk3)
- `backend/models/user.py` (Wk3)
- `backend/models/subscription.py` (Wk3)
- `backend/app/database.py` (Wk2)
**Test File:** `tests/unit/test_onboarding_service.py`
**BDD:** `docs/bdd_scenarios/parwa_bdd.md` — Onboarding section
**Pass Criteria:** Unit test passes, pushed to GitHub, CI green

**Responsibilities:**
- `start_onboarding()` — Initialize onboarding for new company
- `complete_onboarding_step()` — Mark step as complete
- `get_onboarding_status()` — Get current onboarding progress
- `setup_company_defaults()` — Set up default settings for new company
- `create_admin_user()` — Create first admin user for company
- `initialize_subscription()` — Set up initial subscription
- `send_welcome_email()` — Trigger welcome email (mocked)
- `validate_onboarding_data()` — Validate onboarding form data
- Company-scoped operations

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS — UPDATE AFTER COMPLETING YOUR TASK
═══════════════════════════════════════════════════════════════════════════════

## BUILDER 1 → STATUS
**File:** `backend/services/support_service.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_support_service.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** NONE
**Notes:** Waiting to start

---

## BUILDER 2 → STATUS
**File:** `backend/services/analytics_service.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_analytics_service.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** NONE
**Notes:** Waiting to start

---

## BUILDER 3 → STATUS
**File:** `backend/services/billing_service.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_billing_service.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** NONE
**Notes:** Waiting to start

---

## BUILDER 4 → STATUS
**File:** `backend/services/onboarding_service.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_onboarding_service.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** NONE
**Notes:** Waiting to start

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER AGENT → VERIFICATION
═══════════════════════════════════════════════════════════════════════════════

**Status:** PENDING — Waiting for all builders to complete

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
