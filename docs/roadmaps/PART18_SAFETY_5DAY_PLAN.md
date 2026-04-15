# Part 18: Safety & Compliance — 5-Day Execution Plan

> **Start:** Day 1
> **Duration:** 5 days
> **Priority:** P0 — Cannot launch without this
> **Docker:** All services run in Docker (Redis, PostgreSQL, backend, worker, frontend)
> **No HIPAA/Healthcare:** Removed from scope. PARWA serves e-commerce, SaaS, and logistics.

---

## Complete Safety Requirements Audit

After going through the entire codebase (92 service files, 74 core modules, 49 API routes, 991+ tests), here is the FULL list of safety/compliance work needed:

### Category A: PII Redaction Engine (Current: 40% accuracy → Target: 90%+)
| # | Item | File | Status | Severity |
|---|------|------|--------|----------|
| A1 | Short email detection (a@b.c) | `pii_redaction_engine.py` | Broken | Critical |
| A2 | IP address detection (v4 + v6) | `pii_redaction_engine.py` | Partial | High |
| A3 | Partial phone numbers (last 4 digits) | `pii_redaction_engine.py` | Missing | High |
| A4 | Names in context (need NER or heuristic) | `pii_redaction_engine.py` | Missing | High |
| A5 | Address detection improvement | `pii_redaction_engine.py` | Partial | Medium |
| A6 | Record number / Insurance ID patterns | `pii_redaction_engine.py` | Exists | Low |
| A7 | Validate all 15 PII types with real data | Tests | Missing | Critical |
| A8 | PII in LLM response output (not just input) | Guardrails | Partial | Critical |

### Category B: Prompt Injection Defense (Current: 15% detection → Target: 95%+)
| # | Item | File | Status | Severity |
|---|------|------|--------|----------|
| B1 | SQL injection patterns | `prompt_injection_defense.py` | Missing | Critical |
| B2 | XSS patterns (script tags, event handlers) | `prompt_injection_defense.py` | Missing | Critical |
| B3 | Command injection (shell, system calls) | `prompt_injection_defense.py` | Missing | Critical |
| B4 | Role-play attacks ("pretend you are") | `prompt_injection_defense.py` | Partial | High |
| B5 | System prompt extraction attempts | `prompt_injection_defense.py` | Missing | Critical |
| B6 | Multi-turn injection (gradual manipulation) | `prompt_injection_defense.py` | Missing | High |
| B7 | Token smuggling / encoding tricks | `prompt_injection_defense.py` | Missing | High |
| B8 | Validate against 100+ real attack patterns | Tests | Missing | Critical |

### Category C: Multi-Tenant Data Isolation (Current: partial → Target: 100%)
| # | Item | File | Status | Severity |
|---|------|------|--------|----------|
| C1 | All DB queries filter by company_id | All services | Partial | Critical |
| C2 | Redis keys namespaced by company_id | `redis.py` | Partial | High |
| C3 | Knowledge base search scoped per tenant | `vector_search.py` | **STUB (MockVectorStore)** | Critical |
| C4 | Training data never crosses tenants | Training tasks | Missing | Critical |
| C5 | Celery tasks scoped by company_id | All tasks | Partial | High |
| C6 | Socket.io rooms isolated per tenant | `socketio.py` | Exists | Medium |
| C7 | API endpoints enforce tenant ownership | All API routes | Partial | Critical |
| C8 | Audit log proves no cross-tenant access | Audit service | Missing | High |
| C9 | One tenant's KB not visible in another's AI responses | AI pipeline | Not verified | Critical |
| C10 | File uploads scoped to tenant | Storage | Partial | High |

### Category D: Information Leakage Prevention (NEW — 0% → Target: 100%)
| # | Item | Description | Status | Severity |
|---|------|-------------|--------|----------|
| D1 | Block revealing which LLMs are used | System prompt layer | Missing | Critical |
| D2 | Block revealing routing strategy | System prompt layer | Missing | Critical |
| D3 | Block revealing internal workflow details | System prompt layer | Missing | High |
| D4 | Block revealing system prompts | Input sanitization | Missing | Critical |
| D5 | Block revealing other tenants' existence | AI pipeline | Missing | Critical |
| D6 | Block revealing internal API structure | System prompt layer | Missing | High |
| D7 | Add "I cannot discuss PARWA's internal systems" response | Response template | Missing | Medium |

### Category E: Guardrails Validation (Current: 8 layers exist → Target: all validated)
| # | Item | File | Status | Severity |
|---|------|------|--------|----------|
| E1 | Content Safety guard tested on real LLM outputs | Tests | Stub tests only | High |
| E2 | Topic Relevance guard validated | Tests | Stub tests only | High |
| E3 | Hallucination Check guard validated | Tests | Stub tests only | High |
| E4 | Policy Compliance guard validated | Tests | Stub tests only | High |
| E5 | Tone Validation guard validated | Tests | Stub tests only | Medium |
| E6 | Length Control guard validated | Tests | Stub tests only | Low |
| E7 | PII Leak Prevention guard validated | Tests | Stub tests only | Critical |
| E8 | Confidence Gate validated | Tests | Stub tests only | High |
| E9 | Guardrails run on EVERY AI response in production | AI pipeline | Not wired | Critical |

### Category F: GDPR Compliance
| # | Item | Description | Status | Severity |
|---|------|-------------|--------|----------|
| F1 | Right-to-erasure API endpoint | `/api/gdpr/erase` | Missing | Critical |
| F2 | Data export endpoint | `/api/gdpr/export` | Missing | High |
| F3 | Consent tracking | User model | Missing | High |
| F4 | Data retention enforcement (365 days) | Background task | Missing | High |
| F5 | Audit log retention (2555 days = 7 years) | Background task | Missing | Medium |

### Category G: Docker & Infrastructure Security
| # | Item | File | Status | Severity |
|---|------|------|--------|----------|
| G1 | Redis password authentication | `docker-compose.prod.yml` | **Exists** (prod only) | Done |
| G2 | Redis password in dev docker-compose | `docker-compose.yml` | **MISSING** | High |
| G3 | Non-root container users | Dockerfiles | **Dockerfiles missing** | Critical |
| G4 | Network isolation (backend_network internal) | `docker-compose.prod.yml` | **Exists** (prod) | Done |
| G5 | Resource limits on all containers | `docker-compose.prod.yml` | **Exists** (prod) | Done |
| G6 | No secrets in environment variables | All compose files | Partial | High |
| G7 | Database not exposed to internet | `docker-compose.prod.yml` | Isolated | Done |
| G8 | Create missing Dockerfiles | `infra/docker/` | **Directory missing** | Critical |

### Category H: Authentication & Authorization
| # | Item | File | Status | Severity |
|---|------|------|--------|----------|
| H1 | JWT validation middleware | `auth.py` + middleware | Exists | Done |
| H2 | API key rotation mechanism | Auth service | Partial | Medium |
| H3 | Session expiry handling | Auth middleware | Exists | Low |
| H4 | RBAC enforcement on all endpoints | All API routes | Partial | High |
| H5 | 2FA enforcement option | User settings | Partial | Medium |

### Category I: Rate Limiting & Abuse Prevention
| # | Item | File | Status | Severity |
|---|------|------|--------|----------|
| I1 | API rate limiting | `rate_limit.py` | Exists | Done |
| I2 | Per-tenant rate limits | Rate limit service | Partial | Medium |
| I3 | Burst protection | `usage_burst_protection.py` | Exists | Done |
| I4 | Spam detection | `spam_detection_service.py` | Exists | Done |

### Category J: Logging & Monitoring Safety
| # | Item | File | Status | Severity |
|---|------|------|--------|----------|
| J1 | No PII/secrets in application logs | Logger config | Not verified | High |
| J2 | Security event logging (failed logins, blocked injections) | Audit service | Partial | High |
| J3 | Prometheus security metrics | Monitoring | Partial | Medium |

### Category K: Input Validation
| # | Item | File | Status | Severity |
|---|------|------|--------|----------|
| K1 | SQL injection prevention (all DB queries) | All services | Partial (ORM) | High |
| K2 | XSS prevention in responses | Response handlers | Partial | High |
| K3 | File upload validation (type, size) | Upload endpoints | Missing check | High |
| K4 | Webhook signature verification | Webhook handlers | Exists (HMAC) | Done |

### Category L: CORS & Headers
| # | Item | File | Status | Severity |
|---|------|------|--------|----------|
| L1 | CORS configuration | `main.py` | Exists | Done |
| L2 | Security headers (X-Frame-Options, CSP, etc.) | `main.py` | Partial | Medium |

---

## Summary: 62 Items Total

| Category | Items | Critical | High | Done/Medium/Low |
|----------|-------|----------|------|-----------------|
| A: PII Redaction | 8 | 4 | 2 | 2 |
| B: Prompt Injection | 8 | 4 | 3 | 1 |
| C: Data Isolation | 10 | 5 | 4 | 1 |
| D: Info Leakage (NEW) | 7 | 4 | 2 | 1 |
| E: Guardrails Validation | 9 | 2 | 5 | 2 |
| F: GDPR | 5 | 1 | 3 | 1 |
| G: Docker Security | 8 | 2 | 2 | 4 |
| H: Auth | 5 | 0 | 2 | 3 |
| I: Rate Limiting | 4 | 0 | 1 | 3 |
| J: Logging | 3 | 0 | 2 | 1 |
| K: Input Validation | 4 | 0 | 3 | 1 |
| L: CORS/Headers | 2 | 0 | 1 | 1 |
| **TOTAL** | **63** | **22** | **30** | **11** |

---

## 5-Day Execution Plan

### DAY 1 — Critical PII & Prompt Injection Fixes

**Focus:** Fix the two biggest accuracy gaps that directly leak customer data or allow manipulation.

**Tasks:**
- [ ] A1: Fix short email regex (handle a@b.co, a@b.c edge cases)
- [ ] A2: Fix IP address detection (combine v4+v6, reduce false positives)
- [ ] A3: Add partial phone detection (last 4 digits, masked formats like XXX-XXX-1234)
- [ ] A4: Add name-in-context heuristic (common first/last name lists + title patterns like "Mr./Mrs./Dr.")
- [ ] A7: Write 50+ real-world PII test cases (mixed formats, edge cases, international)
- [ ] A8: Ensure PII check runs on LLM OUTPUT (not just input)
- [ ] B1: Add SQL injection detection patterns (SELECT/DROP/DELETE/INSERT/UPDATE/UNION)
- [ ] B2: Add XSS detection patterns (script tags, onerror, onclick, javascript: URI)
- [ ] B3: Add command injection patterns (rm -rf, /etc/passwd, curl, wget, exec)
- [ ] B5: Add system prompt extraction detection ("repeat your instructions", "what are your rules")
- [ ] B7: Add token smuggling detection (base64, ROT13, unicode escapes)

**Deliverables:** PII accuracy 70%+, Injection detection 60%+, all tests passing
**Files touched:** `pii_redaction_engine.py`, `prompt_injection_defense.py`, `test_pii_redaction.py`, `test_prompt_injection.py`

---

### DAY 2 — Data Isolation & Docker Security

**Focus:** Ensure zero cross-tenant data access and harden Docker setup.

**Tasks:**
- [ ] C1: Audit ALL database queries — verify company_id filter on every query
- [ ] C2: Audit ALL Redis keys — verify company_id namespacing
- [ ] C3: Verify KB vector search is tenant-scoped (document the MockVectorStore gap)
- [ ] C5: Audit all Celery tasks — verify @with_company_id decorator present
- [ ] C7: Add tenant ownership checks on all API endpoints (middleware level)
- [ ] C8: Write audit trail test proving no cross-tenant access
- [ ] C10: Verify file upload storage is tenant-scoped
- [ ] G2: Add Redis password to dev docker-compose.yml
- [ ] G3: Create Dockerfiles in infra/docker/ with non-root users
- [ ] G6: Audit for secrets in env vars vs vault/secret management

**Deliverables:** 100% tenant isolation verified, Docker hardening complete
**Files touched:** `docker-compose.yml`, `infra/docker/*.Dockerfile`, `tenant.py` middleware, Redis config, all task files

---

### DAY 3 — Information Leakage Prevention & Guardrails Wiring

**Focus:** Block AI from revealing internal details, wire guardrails into live pipeline.

**Tasks:**
- [ ] D1: Add "internal systems" blocked topic to guardrails (which LLMs, models, strategy)
- [ ] D2: Add "routing strategy" blocked topic
- [ ] D3: Add "internal workflow" blocked topic
- [ ] D4: Add system prompt extraction prevention (input sanitization layer)
- [ ] D5: Add "other tenants" blocked topic in AI responses
- [ ] D7: Create canned response: "I can't discuss PARWA's internal systems"
- [ ] E9: Wire ALL 8 guardrail layers into the live AI pipeline (not just tests)
- [ ] E1-E8: Validate each guardrail layer with 20+ real LLM output samples
- [ ] B4: Add role-play attack patterns (DAN,AIM,dev mode, etc.)
- [ ] B6: Add multi-turn injection tracking (session-level injection score)
- [ ] B8: Run penetration test with 100+ attack patterns, achieve 95%+ block rate

**Deliverables:** Info leakage blocked, guardrails wired to production, injection 95%+
**Files touched:** `guardrails_engine.py`, `prompt_injection_defense.py`, `ai_pipeline.py`, new `info_leak_guard.py`

---

### DAY 4 — GDPR Endpoints & Security Hardening

**Focus:** GDPR compliance, logging safety, input validation, security headers.

**Tasks:**
- [ ] F1: Build `/api/gdpr/erase` endpoint (delete all data for a user, cascade through tables)
- [ ] F2: Build `/api/gdpr/export` endpoint (export all user data as JSON/CSV)
- [ ] F3: Add consent tracking fields to User model + API
- [ ] F4: Build data retention enforcement background task (GDPR_RETENTION_DAYS=365)
- [ ] F5: Build audit log retention cleanup (AUDIT_LOG_RETENTION_DAYS=2555)
- [ ] J1: Audit ALL log statements — ensure no PII, passwords, tokens logged
- [ ] J2: Add security event logging (failed auth, blocked injections, rate limit hits)
- [ ] K2: Add XSS sanitization to all API response fields
- [ ] K3: Add file upload validation (allowed types, max size 10MB, virus scan placeholder)
- [ ] L2: Add security headers (X-Frame-Options, X-Content-Type-Options, CSP, HSTS)
- [ ] H4: Audit RBAC on all endpoints — ensure non-admin can't access admin routes

**Deliverables:** GDPR endpoints live, logging safe, security headers in place
**Files touched:** New `gdpr.py` API route, `audit_service.py`, `main.py`, middleware, User model migration

---

### DAY 5 — Integration Testing, Validation & Verification

**Focus:** End-to-end testing of everything built in Days 1-4. Verify all targets met.

**Tasks:**
- [ ] Run full PII redaction test suite — verify 90%+ accuracy on 200+ test cases
- [ ] Run full prompt injection test suite — verify 95%+ detection on 200+ attack patterns
- [ ] Run cross-tenant isolation test — verify zero data leakage between 5 test tenants
- [ ] Run GDPR erasure test — verify complete data deletion with cascade
- [ ] Run GDPR export test — verify export matches all stored data
- [ ] Run guardrail validation — verify all 8 layers fire on real LLM outputs
- [ ] Run information leakage test — verify AI never reveals LLM names, strategy, workflows
- [ ] Run Docker security scan — verify non-root, Redis auth, network isolation
- [ ] Run rate limit stress test — verify burst protection works under load
- [ ] Run security header validation — verify all headers present on API responses
- [ ] Fix any bugs found during testing
- [ ] Update all test files with real test data (no stubs)
- [ ] Update PROJECT_STATUS.md with Part 18 completion

**Deliverables:** All 63 safety items verified, Part 18 COMPLETE
**Files touched:** All test files, PROJECT_STATUS.md

---

## Success Criteria — Part 18 Complete

| Metric | Current | Target |
|--------|---------|--------|
| PII redaction accuracy | 40% | 90%+ |
| Prompt injection detection | 15% | 95%+ |
| Tenant data isolation | Partial | 100% verified |
| Information leakage blocked | 0% | 100% |
| GDPR compliance | Missing | Endpoints live |
| Guardrails in production | Test-only | All 8 layers live |
| Docker security | Partial | Hardened |
| Redis auth (dev) | Missing | Enabled |
| Dockerfiles | Missing | Created with non-root |
| Security headers | Partial | All present |
| Tests (real data, not stubs) | Mostly stubs | 200+ real cases |

---

## Dependencies

**None.** Part 18 has zero dependencies on other parts. Can start immediately.

## Parallel Work Possible

While Part 18 is being built, these can run in parallel:
- Part 12 (Dashboard) — no safety dependency
- Part 15 (Billing) — no safety dependency
- Part 1 (Infrastructure) — Docker files overlap (coordinate Day 2)
