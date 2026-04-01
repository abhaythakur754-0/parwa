**PARWA**

**Execution Roadmap --- Week 1 --- Project Skeleton + Database**

*Zai Single-Agent-Per-Day · Files CAN depend within day · Each day ends with
Testing + Loophole Check · Day 6 is Final Integration + Cross-Day Audit*

+-----------------------------------------------------------------------+
| WEEK 1 RULES:                                                         |
|                                                                       |
| ✅ Within a day: files CAN depend on each other (sequential build)    |
|                                                                       |
| ❌ Across days: files CANNOT depend on each other (parallel days)     |
|                                                                       |
| ✅ Infrastructure (Docker, CI, Nginx, configs) already exists.        |
| This roadmap covers ONLY what needs to be built.                     |
|                                                                       |
| 🔴 EVERY DAY ends with 2 phases:                                      |
|   Phase A: Unit Tests --- pytest that day's code → all MUST pass       |
|   Phase B: Loophole Check --- scan that day's code against Building   |
|   Codes using the provided docs as rulebook                           |
|                                                                       |
| 🟢 NO COMMIT until Phase A + Phase B pass                            |
|                                                                       |
| 📦 6 commits total (one per day), each pushed to GitHub               |
|                                                                       |
| 🐙 GitHub CI MUST be green on every commit (no local Docker)          |
|                                                                       |
| 📋 worklog.md --- all agents read/write from there                    |
+-----------------------------------------------------------------------+

**What already exists (DO NOT rebuild):**

+-----------------------------------------------------------------------+
| ✅ docker-compose.yml (dev: postgres, redis, backend, frontend)        |
| ✅ docker-compose.prod.yml (8 services + monitoring)                   |
| ✅ infra/docker/backend.Dockerfile (multi-stage, python:3.11)         |
| ✅ infra/docker/worker.Dockerfile (multi-stage, python:3.11)          |
| ✅ infra/docker/frontend.Dockerfile (multi-stage, node:20)            |
| ✅ infra/docker/mcp.Dockerfile (multi-stage, python:3.11)              |
| ✅ infra/docker/nginx.conf (reverse proxy, rate limiting)              |
| ✅ infra/docker/nginx-default.conf (routing rules)                    |
| ✅ infra/docker/postgresql.conf (optimized for PARWA workload)        |
| ✅ infra/docker/redis.conf (AOF persistence, LRU, 256MB)             |
| ✅ infra/docker/pg_hba.conf (auth config)                             |
| ✅ .env.example (all env vars listed)                                 |
| ✅ .gitignore (comprehensive)                                          |
| ✅ .github/workflows/ci.yml (backend + frontend CI)                   |
| ✅ .github/workflows/deploy-backend.yml (placeholder)                 |
| ✅ .github/workflows/deploy-frontend.yml (placeholder)                |
+-----------------------------------------------------------------------+

**What needs to be built:**

+-----------------------------------------------------------------------+
| ❌ backend/ directory (FastAPI application)                           |
| ❌ frontend/ directory (Next.js application)                          |
| ❌ shared/ directory (shared utilities across backend/frontend)        |
| ❌ database/ directory (Alembic migrations, 50+ tables)               |
| ❌ security/ directory (auth, encryption, rate limiting)               |
| ❌ requirements.txt (Python dependencies)                             |
| ❌ Alembic setup with 8 migration groups                              |
| ❌ Base error handling + structured responses                          |
| ❌ Structured logging + audit trail table                             |
| ❌ Health check endpoints (/health, /ready, /metrics)                 |
| ❌ Multi-tenant middleware (BC-001 foundation)                         |
| ❌ Tests for everything above                                          |
+-----------------------------------------------------------------------+

---

**Day 1 --- Project Skeleton + Config + Logger**

Build the project structure, configuration, logging, and health check
foundation. Every future file depends on these.

**BUILD Phase (Steps 1-7):**

  ------- --------------------------------------------------- ---------------------- ------------------------------
  **STEP  **Files to Build (in order)**                      **Depends On**         **Unit Test / Notes**
  **1**

  **1**   requirements.txt                                  None                  Verify: pip install -r
                                                                       requirements.txt
                                                                       succeeds

  **2**   backend/__init__.py                              None                  Empty init

  **3**   backend/app/__init__.py                          None                  Empty init

  **4**   backend/app/config.py                            None                  Test: loads all env
                                                                       vars, raises error on
                                                                       missing required

  **5**   backend/app/main.py                              config.py (same day)  Test: /health
                                                                       returns 200
                                                                       Test: /ready returns
                                                                       200
                                                                       Test: /metrics
                                                                       returns 200
                                                                       Test: unknown route
                                                                       returns structured
                                                                       404 JSON (BC-012)

  **6**   backend/app/logger.py                            config.py (same day)  Test: structured
                                                                       JSON output, no
                                                                       stack traces
                                                                       (BC-012)

  **7**   backend/app/exceptions.py                       config.py (same day)  Test: base exceptions
                                                                       defined with error
                                                                       codes
                                                                       Test: HTTPException
                                                                       returns structured
                                                                       JSON (BC-012)
  ------- --------------------------------------------------- ---------------------- ------------------------------

**🧪 Phase A --- Unit Tests (Steps 8-10):**

  ------- --------------------------------------------------- ---------------------- ------------------------------
  **STEP  **Files to Build**                                **Depends On**         **Notes**
  **1A**

  **8**   tests/conftest.py                                None                  Test: fixtures load
                                                                       correctly

  **9**   tests/unit/test_config.py                        config.py (Day 1)     Tests all env vars
                                                                       loaded, missing
                                                                       required raises
                                                                       error

  **10**  tests/unit/test_health.py                        main.py (Day 1)       Tests /health /ready
                                                                       /metrics return 200
                                                                       Tests 404 structured
                                                                       JSON (BC-012)
  ------- --------------------------------------------------- ---------------------- ------------------------------

**🔍 Phase B --- Loophole Check (Day 1):**

+-----------------------------------------------------------------------+
| CHECK                        | SOURCE (from docs)                      |
|------------------------------|----------------------------------------|
| Are ALL env vars from        | .env.example vs config.py              |
| .env.example loaded?         | Missing any = security hole            |
| Is SECRET_KEY required?      | BC-011 — no default secrets            |
| Is JWT_SECRET_KEY required?  | BC-011 — no hardcoded JWT secrets     |
| Is DATABASE_URL required?    | No default DB connection string        |
| Does 404 return structured   | BC-012 — no raw stack traces to users  |
| JSON (no stack traces)?      |                                        |
| Does /health exist?          | BC-012 — health endpoint mandatory     |
| Does /ready exist?           | BC-012 — readiness probe mandatory     |
| Does /metrics exist?         | BC-012 — monitoring endpoint mandatory |
| Logger outputs JSON?         | BC-012 — structured logging only       |
| No print() statements?       | BC-012 — no console dumps              |
+-----------------------------------------------------------------------+

**COMMIT 1**: "Week 1 Day 1: Project skeleton, config, logger, health endpoints"
→ Push to GitHub → Verify CI green ✅

---

**Day 2 --- Database Models + Alembic + Multi-Tenant Middleware**

Build the PostgreSQL database layer with all 50+ tables across 8
migration groups, Alembic setup, and the BC-001 multi-tenant isolation
middleware.

**BUILD Phase (Steps 1-22):**

  ------- --------------------------------------------------- ---------------------- ------------------------------
  **STEP  **Files to Build (in order)**                      **Depends On**         **Unit Test / Notes**
  **2**

  **1**   database/__init__.py                             None                  Empty init

  **2**   database/base.py                                config.py (Day 1)     Test: engine and
                                                                       session factory
                                                                       created

  **3**   database/models/__init__.py                     None                  Empty init

  **4**   database/models/core.py                          base.py (same day)    Test: companies +
                                                                       users tables created
                                                                       Test: every table
                                                                       has company_id with
                                                                       index (BC-001)
                                                                       TABLES: companies,
                                                                       users, refresh_tokens,
                                                                       mfa_secrets,
                                                                       backup_codes, api_keys

  **5**   database/models/billing.py                       base.py (same day)    Test: subscriptions +
                                                                       invoices +
                                                                       overage_charges +
                                                                       transactions +
                                                                       webhook_events +
                                                                       cancellation_requests
                                                                       created
                                                                       Test: all money
                                                                       fields are
                                                                       DECIMAL(10,2) (BC-002)

  **6**   database/models/tickets.py                       base.py (same day)    Test: tickets +
                                                                       ticket_messages +
                                                                       ticket_attachments +
                                                                       ticket_internal_notes +
                                                                       customers +
                                                                       channels created
                                                                       Test: every table
                                                                       has company_id
                                                                       (BC-001)

  **7**   database/models/ai_pipeline.py                   base.py (same day)    Test: gsd_sessions +
                                                                       confidence_scores +
                                                                       guardrail_blocks +
                                                                       guardrail_rules +
                                                                       prompt_templates +
                                                                       model_usage_logs +
                                                                       api_providers created

  **8**   database/models/approval.py                      base.py (same day)    Test: approval_records +
                                                                       auto_approve_rules +
                                                                       executed_actions +
                                                                       undo_log created

  **9**   database/models/analytics.py                     base.py (same day)    Test: metric_aggregates
                                                                       + roi_snapshots +
                                                                       drift_reports +
                                                                       qa_scores +
                                                                       training_runs created

  **10**  database/models/training.py                      base.py (same day)    Test: training_datasets
                                                                       + training_checkpoints
                                                                       + agent_mistakes +
                                                                       agent_performance
                                                                       created

  **11**  database/models/integration.py                   base.py (same day)    Test: integrations +
                                                                       rest_connectors +
                                                                       webhook_integrations +
                                                                       mcp_connections +
                                                                       db_connections +
                                                                       event_buffer +
                                                                       error_log +
                                                                       audit_trail +
                                                                       outgoing_webhooks
                                                                       created

  **12**  database/models/onboarding.py                    base.py (same day)    Test: onboarding_sessions
                                                                       + consent_records +
                                                                       knowledge_documents +
                                                                       knowledge_chunks +
                                                                       demo_sessions +
                                                                       newsletter_subscribers
                                                                       created

  **13**  database/alembic.ini                             None                  Verify: points to
                                                                       migrations folder

  **14**  database/alembic/env.py                          base.py (Day 2 #2)   Verify: imports
                                                                       all models,
                                                                       connects to DB

  **15-22** database/migrations/001-008.sql                models (Day 2)        Test: each migration
                                                                       applies cleanly
                                                                       (CI uses SQLite in-memory)

  **23**  backend/app/middleware/tenant.py                  config.py (Day 1)    Test: extracts
                                                                       company_id from JWT
                                                                       Test: no company_id
                                                                       returns 403
                                                                       (BC-001)
  ------- --------------------------------------------------- ---------------------- ------------------------------

**🧪 Phase A --- Unit Tests (Steps 24-25):**

  ------- --------------------------------------------------- ---------------------- ------------------------------
  **STEP  **Files to Build**                                **Depends On**         **Notes**
  **2A**

  **24**  tests/unit/test_models_core.py                   All models (Day 2)    Test: tables created
                                                                       with correct columns
                                                                       Test: company_id on
                                                                       every table (BC-001)
                                                                       Test: DECIMAL(10,2)
                                                                       on money fields
                                                                       (BC-002)

  **25**  tests/unit/test_tenant_middleware.py              middleware (Day 2)    Test: company_id
                                                                       extraction from JWT
                                                                       Test: 403 on missing
                                                                       company_id (BC-001)
  ------- --------------------------------------------------- ---------------------- ------------------------------

**🔍 Phase B --- Loophole Check (Day 2):**

+-----------------------------------------------------------------------+
| CHECK                        | SOURCE (from docs)                      |
|------------------------------|----------------------------------------|
| EVERY table has company_id?  | BC-001 — multi-tenant isolation        |
| company_id has DB index?     | BC-001 — query performance + isolation |
| companies table does NOT     | BC-001 — root tenant has no parent     |
| have nullable company_id?    |                                        |
| Money fields are             | BC-002 — NEVER float for money         |
| DECIMAL(10,2) NOT float?    | Check: subscriptions, invoices,        |
|                              | overage_charges, transactions           |
| refresh_tokens has user_id   | BC-011 — max 5 sessions enforcement    |
| + company_id?                |                                        |
| api_keys has scope enum?     | BC-011 — read/write/admin/approval     |
| audit_trail table exists?    | Required for compliance tracking        |
| error_log table exists?      | BC-012 — centralized error storage      |
| consent_records table?       | BC-010 — GDPR consent tracking          |
| webhook_events table?        | BC-003 — idempotent webhook storage    |
| Alembic env.py imports ALL   | Missing model = missing table in prod   |
| models?                      |                                        |
| Tenant middleware returns     | BC-001 — no cross-tenant data leak     |
| 403 on missing company_id?   |                                        |
| No ORM eager loading of      | Security: prevent cross-tenant joins    |
| cross-tenant relations?      |                                        |
+-----------------------------------------------------------------------+

**COMMIT 2**: "Week 1 Day 2: Database models (50+ tables), Alembic, tenant middleware"
→ Push to GitHub → Verify CI green ✅

---

**Day 3 --- Error Handling + Audit Trail + Shared Utilities**

Build the complete error handling framework (BC-012), audit trail logging,
and shared utility functions used across the entire application.

**BUILD Phase (Steps 1-9):**

  ------- --------------------------------------------------- ---------------------- ------------------------------
  **STEP  **Files to Build (in order)**                      **Depends On**         **Unit Test / Notes**
  **3**

  **1**   shared/__init__.py                                None                  Empty init

  **2**   shared/utils/__init__.py                         None                  Empty init

  **3**   shared/utils/datetime.py                          None                  Test: UTC now, date
                                                                       formatting

  **4**   shared/utils/validators.py                       None                  Test: email, phone,
                                                                       UUID validation

  **5**   shared/utils/pagination.py                       None                  Test: offset/limit
                                                                       calculation

  **6**   shared/utils/security.py                         None                  Test: password hash
                                                                       (bcrypt cost 12)
                                                                       Test: AES-256
                                                                       encrypt/decrypt
                                                                       (BC-011)

  **7**   backend/app/middleware/error_handler.py           exceptions.py (Day 1)Test: structured JSON
                                              , config.py (Day 1)  error response
                                                                       Test: no stack traces
                                                                       to users (BC-012)
                                                                       Test: correlation_id
                                                                       in response

  **8**   backend/app/services/audit_service.py            database models     Test: audit log
                                              (Day 2), logger.py     created with all
                                              (Day 1)               required fields
                                                                       Test: actor_type
                                                                       enum validated

  **9**   backend/app/middleware/request_logger.py          logger.py (Day 1)     Test: every request
                                              , audit_service.py   logged
  ------- --------------------------------------------------- ---------------------- ------------------------------

**🧪 Phase A --- Unit Tests (Steps 10-13):**

  ------- --------------------------------------------------- ---------------------- ------------------------------
  **STEP  **Files to Build**                                **Depends On**         **Notes**
  **3A**

  **10**  backend/app/api/__init__.py                       None                  Empty init

  **11**  tests/unit/test_error_handler.py                 error_handler (Day 3) Test: structured JSON
                                                                       Test: no stack
                                                                       traces (BC-012)
                                                                       Test: correlation_id

  **12**  tests/unit/test_audit_service.py                  audit_service (Day 3) Test: all fields
                                                                       populated
                                                                       Test: actor_type enum

  **13**  tests/unit/test_shared_utils.py                   All utils (Day 3)     Test: datetime,
                                                                       validators,
                                                                       pagination,
                                                                       security utils
  ------- --------------------------------------------------- ---------------------- ------------------------------

**🔍 Phase B --- Loophole Check (Day 3):**

+-----------------------------------------------------------------------+
| CHECK                        | SOURCE (from docs)                      |
|------------------------------|----------------------------------------|
| bcrypt cost factor = 12?     | BC-011 — minimum cost 12, not default  |
| AES-256 used (not AES-128)?  | BC-011 — strong encryption only        |
| Encryption key from env?     | BC-011 — no hardcoded keys             |
| Error handler NEVER leaks    | BC-012 — check debug=False paths       |
| stack traces?                |                                        |
| Error response always has    | BC-012 — structured error format        |
| {error, code, message}?      |                                        |
| Correlation ID in every      | BC-012 — request tracing                |
| error response?              |                                        |
| Audit log records: actor,    | Required fields per backend docs        |
| action, resource, company_id?|                                        |
| Audit log is NOT bypassable? | Security: can't skip audit trail        |
| Request logger records       | BC-012 — full request audit trail       |
| method, path, status, timing?|                                        |
| Validators reject malformed  | Security: input validation              |
| emails/phones?               |                                        |
| Pagination has max limit?    | Security: prevent DoS via huge pages    |
| datetime always UTC?         | BC-012 — no timezone mixing bugs        |
+-----------------------------------------------------------------------+

**COMMIT 3**: "Week 1 Day 3: Error handling, audit trail, shared utilities"
→ Push to GitHub → Verify CI green ✅

---

**Day 4 --- Security + Rate Limiting + API Key Framework**

Build the security foundation: rate limiting (BC-011/BC-012), API key
management (BC-011), and the circuit breaker base (BC-012).

**BUILD Phase (Steps 1-6):**

  ------- --------------------------------------------------- ---------------------- ------------------------------
  **STEP  **Files to Build (in order)**                      **Depends On**         **Unit Test / Notes**
  **4**

  **1**   security/__init__.py                              None                  Empty init

  **2**   security/rate_limiter.py                          config.py (Day 1)    Test: sliding window
                                                                       rate limiting
                                                                       Test: progressive
                                                                       lockout delays
                                                                       Test: Redis down →
                                                                       fail-open
                                                                       (BC-011)

  **3**   security/api_keys.py                             security utils        Test: API key
                                              (Day 3)               generation
                                                                       Test: scope validation
                                                                       (read/write/admin/
                                                                       approval)
                                                                       Test: key rotation
                                                                       (BC-011)

  **4**   security/circuit_breaker.py                      None                  Test: CLOSED→OPEN
                                                                       after 5 failures
                                                                       Test: OPEN→HALF_OPEN
                                                                       after 60s
                                                                       Test: HALF_OPEN→CLOSED
                                                                       on success
                                                                       (BC-012)

  **5**   backend/app/middleware/rate_limit.py             rate_limiter.py      Test: 429 returned
                                              (Day 4)               on exceeded
                                                                       Test: headers
                                                                       X-RateLimit-* set

  **6**   backend/app/middleware/api_key_auth.py           api_keys.py          Test: valid key
                                              (Day 4)               authenticates
                                                                       Test: invalid key
                                                                       returns 401
                                                                       Test: read scope
                                                                       blocks writes
  ------- --------------------------------------------------- ---------------------- ------------------------------

**🧪 Phase A --- Unit Tests (Steps 7-9):**

  ------- --------------------------------------------------- ---------------------- ------------------------------
  **STEP  **Files to Build**                                **Depends On**         **Notes**
  **4A**

  **7**   tests/unit/test_rate_limiter.py                  rate_limiter (Day 4)  Test: sliding window
                                                                       Test: progressive
                                                                       lockout
                                                                       Test: fail-open on
                                                                       Redis down (BC-011)

  **8**   tests/unit/test_circuit_breaker.py               circuit_breaker      Test: state
                                              (Day 4)               transitions:
                                                                       CLOSED→OPEN→HALF_
                                                                       OPEN→CLOSED (BC-012)

  **9**   tests/unit/test_api_keys.py                      api_keys (Day 4)     Test: generation,
                                                                       scopes, rotation
                                                                       (BC-011)
  ------- --------------------------------------------------- ---------------------- ------------------------------

**🔍 Phase B --- Loophole Check (Day 4):**

+-----------------------------------------------------------------------+
| CHECK                        | SOURCE (from docs)                      |
|------------------------------|----------------------------------------|
| Rate limiter fails OPEN      | BC-011 — Redis down = allow requests   |
| (not closed) when Redis down?| not block everything                   |
| Progressive lockout delays?  | BC-011 — not just flat rate limit      |
| X-RateLimit headers set?     | BC-012 — RFC standard headers           |
| API key uses secure random?  | BC-011 — not predictable keys           |
| API key hashed in DB?        | BC-011 — never store raw keys          |
| Scopes enforced: read can't  | BC-011 — scope isolation               |
| write, write can't admin?    |                                        |
| Key rotation invalidates old | BC-011 — no stale key access           |
| key immediately?             |                                        |
| Circuit breaker: 5 failures  | BC-012 — not 3, not 10                  |
| threshold?                   |                                        |
| Circuit breaker: 60s timeout?| BC-012 — standard recovery window      |
| Rate limit per company_id    | BC-001 — tenant-isolated limits        |
| (not global)?                |                                        |
| API key has company_id?      | BC-001 — tenant isolation               |
| No timing attack on API key  | Security: constant-time comparison      |
| comparison?                  |                                        |
+-----------------------------------------------------------------------+

**COMMIT 4**: "Week 1 Day 4: Rate limiter, circuit breaker, API key framework"
→ Push to GitHub → Verify CI green ✅

---

**Day 5 --- Redis Layer + Socket.io Base + Integration Wiring**

Build the Redis connection layer, Socket.io server foundation (BC-005),
wire everything into main.py, and verify docker-compose up works.

**BUILD Phase (Steps 1-6):**

  ------- --------------------------------------------------- ---------------------- ------------------------------
  **STEP  **Files to Build (in order)**                      **Depends On**         **Unit Test / Notes**
  **5**

  **1**   backend/app/core/__init__.py                     None                  Empty init

  **2**   backend/app/core/redis.py                         config.py (Day 1)    Test: connection pool
                                                                       created
                                                                       Test: key namespace
                                                                       parwa:{company_id}:*
                                                                       (BC-001)

  **3**   backend/app/core/socketio.py                     redis.py (same day)  Test: server
                                                                       initialises
                                                                       Test: tenant room
                                                                       naming
                                                                       tenant_{company_id}
                                                                       (BC-005)

  **4**   backend/app/core/event_buffer.py                  redis.py (same day)  Test: event stored
                                                                       and retrieved
                                                                       Test: 24h TTL
                                                                       (BC-005)

  **5**   backend/app/main.py                              ALL above (Day 1-5) Test: all routers
                                              UPDATE existing      mounted
                                                                       Test: tenant
                                                                       middleware active
                                                                       Test: Socket.io
                                                                       attached
                                                                       Test: event buffer
                                                                       registered

  **6**   backend/app/api/health.py                         main.py (same day)    Test: /health → DB +
                                              UPDATE existing      Redis + all subsys
                                                                       checks
                                                                       Test: /ready → deps
                                                                       healthy
                                                                       Test: /metrics →
                                                                       Prometheus format
  ------- --------------------------------------------------- ---------------------- ------------------------------

**🧪 Phase A --- Unit Tests (Steps 7-9):**

  ------- --------------------------------------------------- ---------------------- ------------------------------
  **STEP  **Files to Build**                                **Depends On**         **Notes**
  **5A**

  **7**   tests/unit/test_redis.py                          redis.py (Day 5)     Test: namespace
                                                                       parwa:{company_id}:*
                                                                       (BC-001)

  **8**   tests/unit/test_socketio.py                       socketio (Day 5)    Test: room naming
                                                                       tenant_{company_id}
                                                                       (BC-005)

  **9**   tests/unit/test_event_buffer.py                   event_buffer (Day 5) Test: store + 24h TTL
                                                                       (BC-005)
  ------- --------------------------------------------------- ---------------------- ------------------------------

**🔍 Phase B --- Loophole Check (Day 5):**

+-----------------------------------------------------------------------+
| CHECK                        | SOURCE (from docs)                      |
|------------------------------|----------------------------------------|
| Redis keys ALWAYS include    | BC-001 — no global keys, tenant-only   |
| company_id in namespace?     | parwa:{company_id}:* format            |
| Socket.io rooms named        | BC-005 — tenant_{company_id} format     |
| tenant_{company_id}?         |                                        |
| No cross-tenant room join?   | BC-001 — can't subscribe to other      |
|                              | tenant's events                        |
| Event buffer has TTL (24h)?  | BC-005 — auto-cleanup, no memory leak   |
| Redis connection uses pool?  | Performance: connection reuse           |
| Redis URL from env var?      | Security: no hardcoded connection       |
| Socket.io auth required?     | BC-011 — no anonymous connections       |
| Health check tests Redis?    | BC-012 — detect Redis failures          |
| Health check tests DB?       | BC-012 — detect DB failures             |
| All middleware wired in       | Missing middleware = security hole      |
| main.py? (tenant, rate_limit,|                                        |
| error_handler, request_logger|                                        |
| API key auth on /api routes? | BC-011 — protect all API endpoints     |
+-----------------------------------------------------------------------+

**COMMIT 5**: "Week 1 Day 5: Redis, Socket.io, event buffer, full wiring"
→ Push to GitHub → Verify CI green ✅

---

**Day 6 --- Final Integration + Cross-Day Audit + Fix All**

This is NOT a build day. This day catches everything that slips through
daily checks and validates the FULL system works end-to-end.

**🧪 Phase A --- Full Week Unit Tests:**

+-----------------------------------------------------------------------+
| Command: pytest tests/ -v --tb=short                                 |
|                                                                       |
| Run ALL tests from Day 1-5:                                            |
| • tests/unit/test_config.py                                           |
| • tests/unit/test_health.py                                           |
| • tests/unit/test_models_core.py                                      |
| • tests/unit/test_tenant_middleware.py                                 |
| • tests/unit/test_error_handler.py                                    |
| • tests/unit/test_audit_service.py                                    |
| • tests/unit/test_shared_utils.py                                     |
| • tests/unit/test_rate_limiter.py                                     |
| • tests/unit/test_circuit_breaker.py                                  |
| • tests/unit/test_api_keys.py                                         |
| • tests/unit/test_redis.py                                            |
| • tests/unit/test_socketio.py                                         |
| • tests/unit/test_event_buffer.py                                     |
|                                                                       |
| ALL MUST PASS. Fix any failures.                                       |
+-----------------------------------------------------------------------+

**🔗 Phase B --- Integration Tests:**

+-----------------------------------------------------------------------+
| TEST                              | WHAT TO VERIFY                      |
|-----------------------------------|-------------------------------------|
| App starts without errors         | main.py loads all modules           |
| /health returns 200               | All subsystems checked              |
| /ready returns 200                | Dependencies healthy                |
| /metrics returns 200              | Prometheus format                    |
| Unknown route → 404 JSON          | BC-012 structured error             |
| Tenant middleware active           | BC-001 enforced                     |
| Rate limit middleware active       | BC-011 enforced                     |
| Error handler active              | BC-012 enforced                     |
| Socket.io attached                | BC-005 ready                        |
| All routers mounted               | No 404 on registered routes         |
+-----------------------------------------------------------------------+

**🔍 Phase C --- Cross-Day Loophole Audit:**

Scan ENTIRE codebase (Day 1-5 output) against ALL applicable Building
Codes and provided documents:

+-----------------------------------------------------------------------+
| CHECK                                | BC / DOC SOURCE                    |
|--------------------------------------|------------------------------------|
| BC-001: EVERY table has company_id   | Building Codes doc + backend doc    |
| + index — spot check all models      |                                    |
| BC-001: No global Redis keys         | All redis.py calls                  |
| BC-001: No global Socket.io rooms    | All socketio.py rooms               |
| BC-001: Tenant middleware on ALL     | main.py middleware list             |
| authenticated routes                 |                                    |
| BC-002: All money fields DECIMAL     | billing.py model fields             |
| BC-011: bcrypt cost = 12             | shared/utils/security.py            |
| BC-011: JWT from env, no defaults    | config.py                          |
| BC-011: API key hashed in DB         | api_keys storage                    |
| BC-011: Rate limit per-tenant        | rate_limiter.py                     |
| BC-012: Error responses structured   | All exception handlers              |
| BC-012: No stack traces to users     | error_handler.py                    |
| BC-012: Health endpoints exist       | /health /ready /metrics             |
| BC-012: Circuit breaker implemented  | circuit_breaker.py                  |
| BC-005: Socket.io rooms tenant_*     | socketio.py room names              |
| BC-005: Event buffer with TTL        | event_buffer.py                     |
| SECURITY: No hardcoded secrets       | Grep entire codebase                |
| SECURITY: No default passwords       | Grep entire codebase                |
| SECURITY: SQL injection safe         | All DB queries use ORM              |
| SECURITY: No raw SQL without param   | Alembic migrations                  |
| DOCS MATCH: Tables match backend     | Compare models vs backend doc       |
| docs table definitions               | table lists                         |
| DOCS MATCH: Fields match feature     | Compare model fields vs feature     |
| spec requirements                    | spec requirements                    |
| CI: pytest runs on all new tests     | ci.yml coverage                     |
| CI: flake8 passes on all files       | ci.yml lint step                    |
+-----------------------------------------------------------------------+

**📋 Phase D --- Document Findings:**

Create a report of any loopholes/vulnerabilities found:
- 🔴 Critical: Must fix before commit
- 🟡 Warning: Should fix, discuss with Architect
- 🟢 Info: Good practice notes

Fix all 🔴 Critical items. Discuss 🟡 with user.

**COMMIT 6**: "Week 1 Day 6: Integration tests, cross-day audit, fixes"
→ Push to GitHub → Verify CI green ✅

---

+-----------------------------------------------------------------------+
| **✅ WEEK COMPLETE WHEN ALL PASS:**                                   |
|                                                                       |
| 1. All 6 commits pushed to GitHub with green CI                     |
|                                                                       |
| 2. Alembic upgrade head → all 50+ tables created                     |
|                                                                       |
| 3. Every table has company_id with index (BC-001)                    |
|                                                                       |
| 4. /health + /ready + /metrics endpoints working                     |
|                                                                       |
| 5. Structured error responses (BC-012)                               |
|                                                                       |
| 6. Audit trail service writes to DB                                  |
|                                                                       |
| 7. Rate limiting returns 429 (BC-011)                                |
|                                                                       |
| 8. Circuit breaker state transitions work (BC-012)                   |
|                                                                       |
| 9. Redis + Socket.io layers initialised (BC-001, BC-005)             |
|                                                                       |
| 10. No loopholes or vulnerabilities found in audit                   |
|                                                                       |
| 11. GitHub CI pipeline green on ALL 6 commits                        |
+-----------------------------------------------------------------------+

---

**Building Code Compliance Checklist (Week 1):**

+-----------------------------------------------------------------------+
| BC    | Rule                                                | Day    |
|-------|-----------------------------------------------------|--------|
| 001   | Every DB table has company_id + index                 | Day 2  |
| 001   | Redis keys namespaced parwa:{company_id}:*             | Day 5  |
| 001   | Tenant middleware extracts company_id from JWT          | Day 2  |
| 001   | Rate limits per company_id                             | Day 4  |
| 001   | API keys scoped to company_id                          | Day 4  |
| 002   | All money fields DECIMAL(10,2)                        | Day 2  |
| 003   | (Not applicable this week — webhook framework later)    | —      |
| 004   | (Not applicable this week — Celery in Week 3)          | —      |
| 005   | Socket.io rooms tenant_{company_id}                   | Day 5  |
| 005   | Event buffer for reconnection recovery                | Day 5  |
| 006   | (Not applicable this week — email in Week 3+)          | —      |
| 007   | (Not applicable this week — AI in Week 8+)             | —      |
| 008   | (Not applicable this week — GSD in Week 10+)           | —      |
| 009   | (Not applicable this week — Approval in Week 7)        | —      |
| 010   | (Not applicable this week — GDPR in Week 7+)          | —      |
| 011   | bcrypt cost 12 for passwords                         | Day 3  |
| 011   | Max 5 sessions, JWT 15min, refresh 7d                | Day 2  |
| 011   | API key scopes (read/write/admin/approval)            | Day 4  |
| 011   | Rate limiting with progressive lockout               | Day 4  |
| 011   | AES-256 encryption                                    | Day 3  |
| 012   | Structured JSON error responses                       | Day 1  |
| 012   | No stack traces to users                             | Day 1  |
| 012   | Circuit breaker pattern                              | Day 4  |
| 012   | Health endpoints /health /ready /metrics             | Day 1  |
| 012   | Correlation ID in every error                         | Day 3  |
| 012   | Request logger middleware                            | Day 3  |
+-----------------------------------------------------------------------+

---

**Files Created This Week:**

+-----------------------------------------------------------------------+
| Day | File                                                        |
|-----|-------------------------------------------------------------|
| 1   | requirements.txt, backend/__init__.py, backend/app/__init__.py, |
|     | backend/app/config.py, backend/app/main.py, backend/app/logger.py, |
|     | backend/app/exceptions.py, tests/conftest.py,                    |
|     | tests/unit/test_config.py, tests/unit/test_health.py             |
| 2   | database/__init__.py, database/base.py, database/models/__init__.py, |
|     | database/models/core.py, database/models/billing.py,               |
|     | database/models/tickets.py, database/models/ai_pipeline.py,        |
|     | database/models/approval.py, database/models/analytics.py,        |
|     | database/models/training.py, database/models/integration.py,       |
|     | database/models/onboarding.py, database/alembic.ini,               |
|     | database/alembic/env.py, database/migrations/001-008.sql,        |
|     | backend/app/middleware/tenant.py,                                |
|     | tests/unit/test_models_core.py, tests/unit/test_tenant_middleware.py|
| 3   | shared/__init__.py, shared/utils/__init__.py,                      |
|     | shared/utils/datetime.py, shared/utils/validators.py,             |
|     | shared/utils/pagination.py, shared/utils/security.py,               |
|     | backend/app/middleware/error_handler.py,                          |
|     | backend/app/services/audit_service.py,                           |
|     | backend/app/middleware/request_logger.py,                         |
|     | tests/unit/test_error_handler.py, tests/unit/test_audit_service.py,|
|     | tests/unit/test_shared_utils.py                                    |
| 4   | security/__init__.py, security/rate_limiter.py,                    |
|     | security/api_keys.py, security/circuit_breaker.py,                 |
|     | backend/app/middleware/rate_limit.py,                             |
|     | backend/app/middleware/api_key_auth.py,                           |
|     | tests/unit/test_rate_limiter.py, tests/unit/test_circuit_breaker.py,|
|     | tests/unit/test_api_keys.py                                      |
| 5   | backend/app/core/__init__.py, backend/app/core/redis.py,           |
|     | backend/app/core/socketio.py, backend/app/core/event_buffer.py,    |
|     | backend/app/api/__init__.py, backend/app/api/health.py,             |
|     | tests/unit/test_redis.py, tests/unit/test_socketio.py,             |
|     | tests/unit/test_event_buffer.py                                     |
| 6   | tests/integration/test_week1_full.py (integration tests)           |
+-----------------------------------------------------------------------+

---

**Total files to build: ~80**
**6 commits: one per day, each CI-green**
**Every day: Build → Test → Loophole Check → Fix → Commit → Push**
