# AGENT_COMMS.md — Week 3 Day 1
# Last updated: 2026-03-14
# Current status: IN PROGRESS

═══════════════════════════════════════════════════════════
## MANAGER → WEEK 3 DAY 1 ASSIGNMENTS
═══════════════════════════════════════════════════════════
Written by: Manager Agent (Antigravity)
Date: 2026-03-14

> Week 2 is CLOSED. Tester verified all files — ALL CLEAR. Great work by all agents.
> We are entering Week 3 — Backend Models & Schemas. Today (Day 1) we build the 4 core SQLAlchemy model files.
> All 4 agents start SIMULTANEOUSLY. Models are fully independent of each other.
> RULE REMINDER: Build → Unit Test passes → THEN push. One push per file. Never before tests pass.
> Write your "Actual Output" in the STATUS section when DONE.

---

### AGENT 1
**File to Build:** `backend/models/user.py` AND `backend/models/company.py`

**What Is This File?:**
`user.py` defines the SQLAlchemy ORM model for platform users (managers, admins). `company.py` defines the model for client companies (tenants) that subscribe to PARWA.

**Responsibilities:**
- `user.py`:
  - `User` class inheriting from `Base` (SQLAlchemy declarative base from `backend/app/database.py`)
  - Fields: `id` (UUID pk), `company_id` (FK → companies.id), `email` (unique, indexed), `password_hash` (str), `role` (enum: admin/manager/viewer), `is_active` (bool, default True), `created_at` (datetime, server_default=now), `updated_at` (datetime, onupdate=now)
  - Relationship: `company` → `Company` (many-to-one)
  - `__repr__` method for debugging
- `company.py`:
  - `Company` class inheriting from `Base`
  - Fields: `id` (UUID pk), `name` (str, indexed), `industry` (str), `plan_tier` (enum: mini/parwa/parwa_high), `is_active` (bool, default True), `rls_policy_id` (str, nullable), `created_at` (datetime), `updated_at` (datetime)
  - Relationship: `users` → list of `User` (one-to-many, back_populates)
  - `__repr__` method

**Depends On:**
- `backend/app/database.py` — Week 2, Day 3 (provides `Base`, `engine`)
- `shared/core_functions/config.py` — Week 1, Day 2 (env vars)

**Expected Output:**
Both files importable without errors. `User` and `Company` tables created correctly when `Base.metadata.create_all(engine)` is called. All fields present with correct types. FK relationship between `User.company_id → Company.id` works.

**Unit Test File:** `tests/unit/test_models.py`
- Test: `User` table created with all expected columns
- Test: `Company` table created with all expected columns
- Test: `User.company_id` FK references `Company.id` — relationship resolves correctly
- Test: `User.role` accepts only valid enum values (admin/manager/viewer)
- Test: `Company.plan_tier` accepts only valid enum values (mini/parwa/parwa_high)
- Test: `repr(user)` returns a readable string (does not raise)

**BDD Scenario:** `docs/bdd_scenarios/parwa_bdd.md` — User Registration & Multi-Tenancy sections

**Error Handling:**
- Invalid `role` or `plan_tier` enum value must raise `ValueError` at model level
- Duplicate `email` must be caught at DB level (unique constraint) — not silently ignored
- Missing required fields must raise `IntegrityError` at DB insert

**Security Requirements:**
- `password_hash` must be a hashed string — the model must NOT store plaintext passwords
- `company_id` must be validated as a valid UUID — no raw string injection
- `email` field must be lowercased before storage — add `@validates('email')` decorator

**Integration Points:**
- `backend/app/database.py` — imports `Base`
- `backend/schemas/user.py` — will read this model (Day 2)
- `security/rls_policies.sql` — will reference `company_id` column (Day 3)

**Code Quality:**
- Type hints on ALL functions and class attributes
- Docstrings on both classes and all methods
- PEP 8 compliance
- Max 40 lines per function
- No circular imports

**Pass Criteria:**
`pytest tests/unit/test_models.py::TestUserModel` and `pytest tests/unit/test_models.py::TestCompanyModel` both pass with 0 failures. File pushed to GitHub with a commit message: `feat(models): add User and Company SQLAlchemy models (Wk3 Day1)`

---

### AGENT 2
**File to Build:** `backend/models/license.py` AND `backend/models/subscription.py`

**What Is This File?:**
`license.py` defines the model for PARWA license keys issued to clients. `subscription.py` defines the model for billing subscriptions tied to a company.

**Responsibilities:**
- `license.py`:
  - `License` class inheriting from `Base`
  - Fields: `id` (UUID pk), `company_id` (FK → companies.id), `license_key` (str, unique, indexed), `tier` (enum: mini/parwa/parwa_high), `status` (enum: active/suspended/expired), `issued_at` (datetime), `expires_at` (datetime, nullable), `max_seats` (int, default 1), `created_at` (datetime)
  - Relationship: `company` → `Company` (many-to-one)
  - `is_valid()` method: returns True if status is active and not expired
  - `__repr__` method
- `subscription.py`:
  - `Subscription` class inheriting from `Base`
  - Fields: `id` (UUID pk), `company_id` (FK → companies.id), `stripe_subscription_id` (str, nullable, indexed), `plan_tier` (enum: mini/parwa/parwa_high), `status` (enum: active/past_due/canceled/trialing), `current_period_start` (datetime), `current_period_end` (datetime), `amount_cents` (int), `currency` (str, default 'usd'), `created_at` (datetime), `updated_at` (datetime)
  - `is_active_subscription()` method: returns True if status == 'active'
  - `__repr__` method

**Depends On:**
- `backend/app/database.py` — Week 2, Day 3 (provides `Base`)
- `backend/models/company.py` — Week 3, Day 1 (Agent 1 — same day, but no import needed, FK by string reference only)

**Expected Output:**
Both files importable cleanly. `License` and `Subscription` tables created with all columns. `License.is_valid()` returns False for expired/suspended licenses. `Subscription.is_active_subscription()` returns True only when status='active'.

**Unit Test File:** `tests/unit/test_models.py`
- Test: `License` table has all expected columns
- Test: `Subscription` table has all expected columns
- Test: `License.is_valid()` returns False when status='expired'
- Test: `License.is_valid()` returns False when `expires_at` is in the past
- Test: `License.is_valid()` returns True when status='active' and not expired
- Test: `Subscription.is_active_subscription()` returns True only for status='active'

**BDD Scenario:** `docs/bdd_scenarios/parwa_bdd.md` — License Management & Billing sections

**Error Handling:**
- `license_key` duplicate must raise `IntegrityError` (unique constraint)
- `stripe_subscription_id` can be NULL before Stripe is connected
- Invalid `status` enum values must raise `ValueError`

**Security Requirements:**
- `stripe_subscription_id` must never be logged in plaintext (treat as sensitive)
- `amount_cents` must be a positive integer — add `CheckConstraint('amount_cents > 0')`
- `company_id` must be a valid UUID FK

**Integration Points:**
- `backend/core/license_manager.py` — will use `License.is_valid()` (Week 4)
- `backend/services/billing_service.py` — will use `Subscription` model (Week 4)
- `backend/schemas/license.py` — mirrors this model (Day 2)

**Code Quality:**
- Type hints on ALL functions and class attributes
- Docstrings on both classes and all methods
- PEP 8 compliance
- Max 40 lines per function

**Pass Criteria:**
`pytest tests/unit/test_models.py::TestLicenseModel` and `pytest tests/unit/test_models.py::TestSubscriptionModel` both pass with 0 failures. File pushed to GitHub with commit: `feat(models): add License and Subscription SQLAlchemy models (Wk3 Day1)`

---

### AGENT 3
**File to Build:** `backend/models/support_ticket.py` AND `backend/models/audit_trail.py`

**What Is This File?:**
`support_ticket.py` is the core ticket model for all customer support requests processed by PARWA. `audit_trail.py` is the immutable audit log model for all AI decisions and human overrides — critical for compliance.

**Responsibilities:**
- `support_ticket.py`:
  - `SupportTicket` class inheriting from `Base`
  - Fields: `id` (UUID pk), `company_id` (FK → companies.id), `customer_email` (str), `channel` (enum: chat/email/sms/voice), `status` (enum: open/pending_approval/resolved/escalated), `category` (str, nullable), `subject` (str), `body` (Text), `ai_recommendation` (Text, nullable), `ai_confidence` (float, nullable), `ai_tier_used` (enum: light/medium/heavy, nullable), `sentiment` (enum: positive/neutral/negative, nullable), `assigned_to` (UUID, nullable), `resolved_at` (datetime, nullable), `created_at` (datetime), `updated_at` (datetime)
  - `is_pending_approval()` method: returns True if status == 'pending_approval'
  - `__repr__` method
- `audit_trail.py`:
  - `AuditTrail` class inheriting from `Base`
  - Fields: `id` (UUID pk), `company_id` (FK → companies.id), `ticket_id` (UUID, FK → support_tickets.id, nullable), `actor` (str — 'ai' or user email), `action` (str — e.g. 'approve_refund', 'deny_refund'), `details` (JSON), `previous_hash` (str, nullable), `entry_hash` (str — SHA-256 of this record), `created_at` (datetime, server_default=now)
  - `compute_hash()` method: SHA-256 of `f"{previous_hash}{actor}{action}{details}{created_at}"`
  - IMPORTANT: This table must be INSERT-ONLY. Add a PostgreSQL event listener or `__table_args__` note instructing that UPDATE and DELETE must be blocked via DB trigger (document this in a comment — the trigger itself is in database/schema.sql)

**Depends On:**
- `backend/app/database.py` — Week 2, Day 3 (provides `Base`)
- `shared/core_functions/audit_trail.py` — Week 1, Day 5 (hash chain logic reference)

**Expected Output:**
Both files importable. `SupportTicket` and `AuditTrail` tables created correctly. `audit_trail.compute_hash()` produces a consistent SHA-256 hash. `SupportTicket.is_pending_approval()` returns True only when status='pending_approval'.

**Unit Test File:** `tests/unit/test_models.py`
- Test: `SupportTicket` table has all expected columns
- Test: `SupportTicket.is_pending_approval()` returns True only for 'pending_approval' status
- Test: `AuditTrail` table has all expected columns
- Test: `AuditTrail.compute_hash()` returns a 64-character hex string (SHA-256)
- Test: Changing any field in the hash input changes the resulting hash (immutability test)
- Test: Hash chain: entry N's `previous_hash` matches entry N-1's `entry_hash`

**BDD Scenario:** `docs/bdd_scenarios/parwa_bdd.md` — Refund Workflow & Audit Trail sections

**Error Handling:**
- `ai_confidence` must be between 0.0 and 1.0 — add `CheckConstraint`
- `entry_hash` must be non-null — enforce at model level
- `actor` and `action` fields must be non-empty strings

**Security Requirements:**
- `AuditTrail` must be INSERT-ONLY — document the DB-level block (trigger will be in schema.sql)
- `customer_email` in `SupportTicket` must be stored as-is but masked in `__repr__` (show only first 3 chars + asterisks)
- No raw user input can be placed directly into `action` field — must be from a predefined enum set

**Integration Points:**
- `backend/api/support.py` — will create SupportTicket records (Week 4)
- `shared/core_functions/audit_trail.py` — uses the hash chain pattern (Week 1)
- `backend/services/compliance_service.py` — reads AuditTrail for GDPR export (Week 4)

**Code Quality:**
- Type hints on ALL functions and class attributes
- Docstrings on both classes and all methods
- PEP 8 compliance
- Max 40 lines per function
- Import `hashlib` for SHA-256, not any other library

**Pass Criteria:**
`pytest tests/unit/test_models.py::TestSupportTicketModel` and `pytest tests/unit/test_models.py::TestAuditTrailModel` both pass with 0 failures. File pushed to GitHub with commit: `feat(models): add SupportTicket and AuditTrail SQLAlchemy models (Wk3 Day1)`

---

### AGENT 4
**File to Build:** `backend/models/compliance_request.py` AND `backend/models/sla_breach.py` AND `backend/models/usage_log.py`

**What Is This File?:**
`compliance_request.py` tracks GDPR/TCPA data requests from clients. `sla_breach.py` logs SLA violations (e.g., tickets stuck for 24+ hrs without approval). `usage_log.py` tracks per-company API and AI usage for billing and analytics.

**Responsibilities:**
- `compliance_request.py`:
  - `ComplianceRequest` class inheriting from `Base`
  - Fields: `id` (UUID pk), `company_id` (FK → companies.id), `request_type` (enum: gdpr_export/gdpr_delete/tcpa_optout/hipaa_access), `customer_email` (str), `status` (enum: pending/processing/completed/failed), `requested_at` (datetime), `completed_at` (datetime, nullable), `result_url` (str, nullable), `created_at` (datetime)
  - `is_complete()` method: returns True if status == 'completed'
- `sla_breach.py`:
  - `SLABreach` class inheriting from `Base`
  - Fields: `id` (UUID pk), `company_id` (FK → companies.id), `ticket_id` (UUID, FK → support_tickets.id), `breach_phase` (int — 1, 2, or 3 as per escalation ladder), `breach_triggered_at` (datetime), `hours_overdue` (float), `notified_to` (str — email/role), `resolved_at` (datetime, nullable), `created_at` (datetime)
  - `is_resolved()` method: returns True if resolved_at is not None
- `usage_log.py`:
  - `UsageLog` class inheriting from `Base`
  - Fields: `id` (UUID pk), `company_id` (FK → companies.id), `log_date` (date, indexed), `ai_tier` (enum: light/medium/heavy), `request_count` (int, default 0), `token_count` (int, default 0), `error_count` (int, default 0), `avg_latency_ms` (float, nullable), `created_at` (datetime)
  - `__repr__` method for all three models

**Depends On:**
- `backend/app/database.py` — Week 2, Day 3 (provides `Base`)
- `backend/models/support_ticket.py` — Week 3, Day 1 (Agent 3 — FK reference by string only, not import)

**Expected Output:**
All three files importable cleanly. All three tables created with correct schemas. `ComplianceRequest.is_complete()`, `SLABreach.is_resolved()` return correct boolean values. GDPR-sensitive `customer_email` masked in `__repr__`.

**Unit Test File:** `tests/unit/test_models.py`
- Test: `ComplianceRequest` table has all expected columns
- Test: `ComplianceRequest.is_complete()` returns True only for status='completed'
- Test: `SLABreach` table has all expected columns
- Test: `SLABreach.is_resolved()` returns True only when resolved_at is set
- Test: `UsageLog` table has all expected columns
- Test: `UsageLog.request_count` defaults to 0

**BDD Scenario:** `docs/bdd_scenarios/parwa_bdd.md` — GDPR/Compliance & SLA Escalation sections

**Error Handling:**
- `breach_phase` must be 1, 2, or 3 only — add `CheckConstraint('breach_phase IN (1, 2, 3)')`
- `request_count` and `token_count` must be non-negative — add `CheckConstraint`
- `request_type` must be from the defined enum — invalid values raise `ValueError`

**Security Requirements:**
- `customer_email` in `ComplianceRequest` must be masked in `__repr__` (GDPR — no PII in logs)
- `result_url` must be a pre-signed URL (not a permanent link) — add a comment noting expiry requirement
- `company_id` must be UUID, validated as FK

**Integration Points:**
- `backend/api/compliance.py` — will create ComplianceRequest records (Week 4)
- `backend/services/sla_service.py` — will create SLABreach records (Week 4)
- `backend/services/analytics_service.py` — will read UsageLog (Week 4)

**Code Quality:**
- Type hints on ALL functions and class attributes
- Docstrings on all three classes and all methods
- PEP 8 compliance
- Max 40 lines per function

**Pass Criteria:**
`pytest tests/unit/test_models.py::TestComplianceRequestModel`, `pytest tests/unit/test_models.py::TestSLABreachModel`, and `pytest tests/unit/test_models.py::TestUsageLogModel` all pass with 0 failures. Files pushed to GitHub with commit: `feat(models): add ComplianceRequest, SLABreach, UsageLog models (Wk3 Day1)`

---

═══════════════════════════════════════════════════════════
## AGENT STATUS (Fill this in when DONE)
═══════════════════════════════════════════════════════════

### AGENT 1
**Actual Output:** Completed. Models created with all SQLAlchemy constraints, relationships, and validations.
- File Built: `backend/models/user.py` + `backend/models/company.py`
- Unit Test: PASS
- Commit: 52951a6

### AGENT 2
**Actual Output:** (Done by Agent 2)
- File Built: `backend/models/license.py` + `backend/models/subscription.py`
- Unit Test: PASS
- Commit: 9014f71

### AGENT 3
**Actual Output:** Successfully implemented both SupportTicket and AuditTrail ORM models as specified. Included hash computation for AuditTrail and masked representation for SupportTicket. Added test suites to test_models.py.
- File Built: `backend/models/support_ticket.py` + `backend/models/audit_trail.py`
- Unit Test: PASS
- Commit: 650e1dfc37073cb8c37144bd01bcec5470268c7e

### AGENT 4
**Actual Output:** Completed model creation and verified 100% pass rate in unit tests.
- File Built: `backend/models/compliance_request.py` + `backend/models/sla_breach.py` + `backend/models/usage_log.py`
- Unit Test: PASS
- Commit: 52ebd59

---

═══════════════════════════════════════════════════════════
## TESTER AGENT → VERIFICATION
═══════════════════════════════════════════════════════════
**Task:** Verify all 4 agents' Actual Output against Expected Output. Run `pytest tests/unit/test_models.py -v` after all agents complete.

**Verification Result:** All 9 models from the 4 Builder Agents have been created with correct syntax and specifications. `pytest tests/unit/test_models.py -v` executed successfully with 0 failures. Constraints, relationships, validations, and hashing properties logic are verified. All tests PASS. The Week 3 Day 1 tasks are verified and ready to be pushed.

---

═══════════════════════════════════════════════════════════
## MANAGER → ADVICE
═══════════════════════════════════════════════════════════
[Manager responses to stuck agents or tester failures — filled if needed]

---

═══════════════════════════════════════════════════════════
## TEAM DISCUSSION
═══════════════════════════════════════════════════════════
Manager Note: All 4 model agents today are building SQLAlchemy ORM models that inherit from `Base`. No agent imports another agent's model file directly — FK relationships use string references (e.g. `ForeignKey("companies.id")`) so there are ZERO same-day dependencies. This is fully parallel and safe.

The test file `tests/unit/test_models.py` is a single shared file — all 4 agents contribute tests to it. Each agent should add their test class to the file without overwriting others. If the file already exists from a previous agent, APPEND your test class — do not replace.
