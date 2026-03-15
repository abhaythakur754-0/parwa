# AGENT_COMMS.md — Week 3 Day 2
# Last updated: 2026-03-14
# Current status: IN PROGRESS

═══════════════════════════════════════════════════════════
## MANAGER → WEEK 3 DAY 2 ASSIGNMENTS
═══════════════════════════════════════════════════════════
Written by: Manager Agent (Antigravity)
Date: 2026-03-14

> Week 3 Day 1 is COMPLETE. All 9 core ORM models were verified and merged.
> Today is Day 2: Backend Schemas. We are building the Pydantic V2 schemas that mirror the models from Day 1. 
> These schemas are fully independent of each other. All 4 agents run in parallel.
> RULE REMINDER: Build → Unit Test passes → THEN push. One push per file.
> Write your "Actual Output" in the STATUS section when DONE.

---

### AGENT 1
**File to Build:** `backend/schemas/user.py` AND `backend/schemas/company.py` (optional, can combine both if small enough)

**What Is This File?:**
Pydantic V2 schemas for validating incoming API requests and serializing outbound API responses for Users and Companies.

**Responsibilities:**
- `user.py`:
  - `UserBase`: email (EmailStr), role (enum: admin/manager/viewer), is_active (bool, default True)
  - `UserCreate`: inherits `UserBase`, adds `password` (str, min_length=8), `company_id` (UUID)
  - `UserUpdate`: optional fields from base + password
  - `UserResponse`: inherits `UserBase`, adds `id` (UUID), `company_id` (UUID), `created_at`, `updated_at`. Must use `model_config = ConfigDict(from_attributes=True)` to parse SQLAlchemy models.
- `company.py`:
  - `CompanyBase`: name (str), industry (str), plan_tier (enum: mini/parwa/parwa_high), is_active (bool, default True)
  - `CompanyCreate`: inherits `CompanyBase`
  - `CompanyUpdate`: optional fields
  - `CompanyResponse`: inherits `CompanyBase`, adds `id` (UUID), `rls_policy_id` (str, nullable), `created_at`, `updated_at`. Must have `from_attributes=True`.

**Depends On:**
- `backend/models/user.py` and `company.py` (Day 1) — for conceptual alignment, do not import the SQLAlchemy models directly into the schemas.

**Expected Output:**
Pydantic schemas that strictly validate the data types. `UserResponse` and `CompanyResponse` can serialize from the SQLAlchemy objects created on Day 1.

**Unit Test File:** `tests/unit/test_schemas.py`
- Test: Valid dict parses into `UserCreate` successfully.
- Test: Invalid email format in `UserCreate` raises `ValidationError`.
- Test: Password < 8 chars in `UserCreate` raises `ValidationError`.
- Test: `UserResponse.model_validate(sqlalchemy_obj)` works correctly.
- Test: Missing required fields in `CompanyCreate` raise error.

**BDD Scenario:** `docs/bdd_scenarios/parwa_bdd.md` — User Registration & Multi-Tenancy

**Error Handling:**
- Strict Pydantic validation handles 422 Unprocessable Entity errors natively via FastAPI later. Ensure the schemas cover edge cases natively.

**Security Requirements:**
- `UserResponse` MUST NOT contain `password_hash` or `password`. Ever.
- `email` should be validated using Pydantic's `EmailStr`.

**Integration Points:**
- `backend/api/auth.py` and `backend/api/dashboard.py` will use these schemas (Week 4).

**Code Quality:**
- Pydantic V2 syntax (`model_config`, `Field`, etc.)
- Type hints on all fields
- Max 40 lines per class/function

**Pass Criteria:**
`pytest tests/unit/test_schemas.py::TestUserSchemas` and `TestCompanySchemas` pass with 0 failures. Pushed to GitHub with commit: `feat(schemas): add User and Company Pydantic schemas (Wk3 Day2)`

---

### AGENT 2
**File to Build:** `backend/schemas/license.py` AND `backend/schemas/subscription.py`

**What Is This File?:**
Pydantic V2 schemas for validating API requests regarding Licenses and Billing Subscriptions.

**Responsibilities:**
- `license.py`:
  - `LicenseBase`: license_key (str), tier (enum: mini/parwa/parwa_high), status (enum: active/suspended/expired), max_seats (int)
  - `LicenseCreate`: inherits `LicenseBase`, adds `company_id` (UUID)
  - `LicenseUpdate`: optional fields
  - `LicenseResponse`: adds `id` (UUID), `issued_at`, `expires_at`, `created_at`. `from_attributes=True`
- `subscription.py`:
  - `SubscriptionBase`: plan_tier (enum), status (enum: active/past_due/canceled/trialing), amount_cents (int), currency (str)
  - `SubscriptionCreate`: adds `company_id` (UUID), `current_period_start`, `current_period_end`
  - `SubscriptionUpdate`: optional status, current_period_end
  - `SubscriptionResponse`: adds `id` (UUID), `stripe_subscription_id`, `created_at`, `updated_at`. `from_attributes=True`

**Depends On:**
- `backend/models/license.py` and `subscription.py` (Day 1) — conceptual alignment.

**Expected Output:**
Pydantic schemas that accurately validate inputs and serialize model outputs.

**Unit Test File:** `tests/unit/test_schemas.py`
- Test: Valid dict parses into `LicenseCreate`.
- Test: Negative `amount_cents` in `SubscriptionCreate` raises `ValidationError` (add Pydantic Field > 0 constraint).
- Test: Invalid enum in `SubscriptionBase` raises error.
- Test: Model instantiation via `model_validate(obj)`.

**BDD Scenario:** `docs/bdd_scenarios/parwa_bdd.md` — License Management & Billing

**Error Handling:**
- Pydantic automatically handles bad data types. Provide strict constraints.

**Security Requirements:**
- Ensure `stripe_subscription_id` is passed correctly but maybe obscured in specific logs later. For the schema, standard string validation is fine.

**Integration Points:**
- `backend/api/licenses.py` and `backend/api/billing.py` (Week 4).

**Code Quality:**
- Pydantic V2 syntax.
- Clear field descriptions where necessary.
- PEP 8.

**Pass Criteria:**
Tests pass. Pushed with commit: `feat(schemas): add License and Subscription schemas (Wk3 Day2)`

---

### AGENT 3
**File to Build:** `backend/schemas/support.py` AND `backend/schemas/audit.py`

**What Is This File?:**
Pydantic V2 schemas for Support Tickets and Audit Trail logs.

**Responsibilities:**
- `support.py`:
  - `TicketBase`: customer_email (EmailStr), channel (enum), category (str), subject (str), body (str)
  - `TicketCreate`: inherits base
  - `TicketUpdate`: optional fields (status, assigned_to etc.)
  - `TicketResponse`: adds `id`, `company_id`, `status`, `ai_recommendation`, `ai_confidence`, `ai_tier_used`, `sentiment`, `resolved_at`, `created_at`. `from_attributes=True`.
- `audit.py`:
  - `AuditTrailBase`: action (str), details (dict)
  - `AuditTrailCreate`: adds `company_id`, `ticket_id` (optional), `actor`. `previous_hash` and `entry_hash` are handled by backend logic, not client creation, but schemas can reflect them.
  - `AuditTrailResponse`: full layout including hashes, `created_at`. `from_attributes=True`.

**Depends On:**
- `backend/models/support_ticket.py` and `audit_trail.py` (Day 1)

**Expected Output:**
Accurate serialization schemas. 

**Unit Test File:** `tests/unit/test_schemas.py`
- Test: `TicketCreate` requires valid email.
- Test: `ai_confidence` in `TicketResponse` must be >= 0.0 and <= 1.0 (ensure schema respects model types).
- Test: `AuditTrailCreate` accepts valid dict for `details`.

**BDD Scenario:** `docs/bdd_scenarios/parwa_bdd.md` — Refund Workflow & Audit Trail

**Error Handling:**
- Strict Pydantic parsing.

**Security Requirements:**
- Schemas themselves don't enforce DB INSERT constraints, but they should mirror the types rigorously.
- Create schemas should NEVER accept `entry_hash` from the client. That is computed server-side.

**Integration Points:**
- `backend/api/support.py` (Week 4).

**Code Quality:**
- Pydantic V2 syntax. Type hinting. PEP 8.

**Pass Criteria:**
Tests pass. Pushed with commit: `feat(schemas): add Support and Audit schemas (Wk3 Day2)`

---

### AGENT 4
**File to Build:** `backend/schemas/compliance.py` AND `backend/schemas/usage.py`

**What Is This File?:**
Pydantic schemas for Compliance Requests, SLA Breaches, and Usage Logs.

**Responsibilities:**
- `compliance.py`:
  - `ComplianceRequestCreate`: request_type (enum), customer_email (EmailStr)
  - `ComplianceRequestResponse`: full fields including status, result_url, dates.
  - `SLABreachCreate`: ticket_id (UUID), breach_phase (int: 1,2,3), hours_overdue (float), notified_to (str)
  - `SLABreachResponse`: full fields.
- `usage.py`:
  - `UsageLogCreate`: log_date (date), ai_tier (enum), request_count (int), token_count (int), error_count (int), avg_latency_ms (float)
  - `UsageLogResponse`: full fields.

**Depends On:**
- `backend/models/compliance_request.py`, `sla_breach.py`, `usage_log.py` (Day 1)

**Expected Output:**
Schemas accurately mapping to models for payload validation.

**Unit Test File:** `tests/unit/test_schemas.py`
- Test: Invalid `breach_phase` (like 4) in `SLABreachCreate` raises `ValidationError` using Pydantic Field constraints (`Field(ge=1, le=3)`).
- Test: Negative token counts raise ValidationError.

**BDD Scenario:** `docs/bdd_scenarios/parwa_bdd.md` — GDPR & SLA

**Error Handling:**
- Standard Pydantic.

**Security Requirements:**
- Restrict bounds via Pydantic `Field` (e.g., `Field(ge=0)` for counts).

**Integration Points:**
- `backend/api/compliance.py` (Week 4).

**Code Quality:**
- Pydantic V2 syntax. PEP 8.

**Pass Criteria:**
Tests pass. Pushed with commit: `feat(schemas): add Compliance and Usage schemas (Wk3 Day2)`

---

═══════════════════════════════════════════════════════════
## AGENT STATUS (Fill this in when DONE)
═══════════════════════════════════════════════════════════

### AGENT 1
**Actual Output:** Completed. Pydantic V2 schemas for Company (CompanyBase, CompanyCreate, CompanyUpdate, CompanyResponse) and User (UserBase, UserCreate, UserUpdate, UserResponse) created. `model_config = ConfigDict(from_attributes=True)` is correctly applied to responses. 
- File Built: `backend/schemas/user.py` + `backend/schemas/company.py`
- Unit Test: PASS
- Commit: 1a7ebc1

### AGENT 2
**Actual Output:** Completed schemas for License and Subscription with Pydantic V2. Validated model extraction using `ConfigDict(from_attributes=True)` and strict constraints (`Field(gt=0)`).
- File Built: `backend/schemas/license.py` + `backend/schemas/subscription.py`
- Unit Test: PASS
- Commit: afa7c7a

### AGENT 3
**Actual Output:** Pydantic V2 schemas for Support Tickets and Audit Trail successfully created using ConfigDict(from_attributes=True). All requirements met, models validate accurately, and all unit tests passed.
- File Built: `backend/schemas/support.py` + `backend/schemas/audit.py`
- Unit Test: PASS
- Commit: 15d34b731b64811682b2b08850b2e49

### AGENT 4
**Actual Output:** Completed Pydantic V2 schema creation for Compliance and Usage logs with strict field validators. Unit tests all pass successfully.
- File Built: `backend/schemas/compliance.py` + `backend/schemas/usage.py`
- Unit Test: PASS
- Commit: 66041bb

---

═══════════════════════════════════════════════════════════
## TESTER AGENT → VERIFICATION
═══════════════════════════════════════════════════════════
**Task:** Verify all 4 agents' Actual Output against Expected Output. Run `pytest tests/unit/test_schemas.py -v` after all agents complete.

**Verification Result:** Week 3 Day 2 Pydantic schemas correctly created and verified. Verified that all 9 new schemas in `backend/schemas/` use `model_config = ConfigDict(from_attributes=True)` per Pydantic V2 specifics. All 15 tests in `pytest tests/unit/test_schemas.py -v` executed successfully with 0 failures, ensuring complete test coverage for validation, strict typing, and object instantiation patterns. Approved for merge.

---

═══════════════════════════════════════════════════════════
## MANAGER → ADVICE
═══════════════════════════════════════════════════════════
[Manager responses to stuck agents or tester failures — filled if needed]

---

═══════════════════════════════════════════════════════════
## TEAM DISCUSSION
═══════════════════════════════════════════════════════════
Manager Note: Welcome to Day 2. We are using Pydantic V2. Please ensure you are using `model_config = ConfigDict(from_attributes=True)` to parse SQLAlchemy models, NOT the deprecated `class Config: orm_mode = True` from V1.
