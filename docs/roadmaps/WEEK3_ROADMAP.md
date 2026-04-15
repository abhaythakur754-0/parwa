# PARWA Week 3 Roadmap — Background Jobs + Real-Time + Middleware

> **Phase 1 Final Week** — After this week, the Foundation is 100% complete.
>
> Days 15-18 were infrastructure hardening overflow from Weeks 1-2.
> Days 19-23 are the TRUE Week 3 scope from the Build Roadmap.
>
> **Depends on:** Week 1 (database, Redis, error handling) + Week 2 (auth middleware)
> **Unblocks:** Phase 2 — Core Business Logic (Tickets, Billing, Onboarding, Approval)

---

## Week 3 Scope (From Build Roadmap Lines 67-83)

| Module | Purpose | Building Codes | Status |
|--------|---------|----------------|--------|
| Celery infrastructure | Worker setup, 7 queues, task base class, retry/backoff/DLQ | BC-004 | ⚠️ Partial (queues defined, task modules missing) |
| Socket.io server | Room pattern, event buffer, heartbeat, reconnection | BC-005 | ⚠️ Partial (skeleton exists, business handlers missing) |
| Multi-tenant middleware | Extract company_id from JWT, inject into DB queries, reject cross-tenant | BC-001 | ⚠️ Partial (basic exists, needs deep hardening) |
| Webhook base framework | HMAC verification, idempotency via event_id, async processing, response < 3s | BC-003 | ⚠️ Partial (verification done, provider handlers missing) |
| Health check system | Per-subsystem health (DB, Redis, Celery, external APIs), global health endpoint | BC-012 | ⚠️ Partial (basic exists, needs full subsystem coverage) |

**Outcome:** Background tasks queued and processed. Real-time events pushed to browsers. Every API call tenant-isolated. Incoming webhooks have reusable verification layer.

---

## Day 19 — Socket.io Business Event System

**Goal:** Transform the Socket.io skeleton into a full real-time event system with typed events, emit helpers, and business event handlers.

### What Already Exists
- `backend/app/core/socketio.py` — Async Socket.io server with JWT auth, tenant rooms, connect/disconnect
- `backend/app/core/event_buffer.py` — Redis sorted-set buffer for reconnection recovery
- `tests/unit/test_socketio.py` — 30+ unit tests
- `tests/unit/test_socketio_auth.py` — Auth tests

### What To Build

| File | Description | Tests |
|------|-------------|-------|
| `backend/app/core/events.py` | Event type registry (enum/class), event payload schemas, event validation | 30+ tests |
| `backend/app/core/event_emitter.py` | High-level emit helpers: `emit_ticket_event()`, `emit_ai_event()`, `emit_approval_event()`, `emit_notification_event()`, `emit_system_event()` | 25+ tests |
| `backend/app/core/socketio.py` (UPDATE) | Register business event handlers for each event type | — |
| `backend/app/tasks/event_tasks.py` | Celery task for async event emission (fan-out to rooms, retries) | 15+ tests |
| `tests/unit/test_events.py` | Event registry, validation, payload tests | — |
| `tests/unit/test_event_emitter.py` | Emit helper tests with mocked Socket.io | — |
| `tests/integration/test_socketio_events.py` | Integration: emit → handler → room broadcast flow | — |

### Event Types to Define (BC-005)

```
# Ticket Events
ticket:new          — New ticket created
ticket:assigned     — Ticket assigned to agent
ticket:updated      — Ticket status/priority changed
ticket:resolved     — Ticket marked as resolved
ticket:escalated    — Ticket escalated (sentiment > 80 or VIP)
ticket:message_new  — New message added to ticket

# AI Events
ai:draft_ready      — AI draft response generated (co-pilot mode)
ai:response_sent    — AI auto-response sent to customer
ai:confidence_low   — Confidence score dropped below threshold
ai:classification   — Ticket classified by AI

# Approval Events
approval:pending    — New approval queued
approval:approved   — Action approved
approval:rejected   — Action rejected
approval:timeout    — Approval timed out (72h)
approval:batch      — Batch approval completed

# Notification Events
notification:new    — New notification for user
notification:read   — User read notification
notification:bulk   — Bulk notification (team-wide)

# System Events
system:health       — Subsystem health status change
system:queue_depth  — Queue depth warning
system:error        — Critical error occurred
system:maintenance  — Maintenance mode toggle
```

### Acceptance Criteria
- [ ] Event registry validates event types and payloads at registration
- [ ] Each emit helper validates payload schema before emitting
- [ ] Events are emitted only to the correct tenant room (BC-001)
- [ ] Failed emissions are logged but never crash the server
- [ ] Event buffer captures all emitted events for reconnection recovery
- [ ] All events include correlation_id for tracing
- [ ] Integration test proves: emit → handler → room broadcast end-to-end

### Loophole Checks
- [ ] No cross-tenant event leakage
- [ ] Large payloads are truncated/rejected (max 10KB per event)
- [ ] Rate limit on event emission per tenant (max 100 events/sec)
- [ ] Socket.io auth is verified on every event handler, not just connect

---

## Day 20 — Multi-Tenant Middleware Hardening

**Goal:** Make BC-001 multi-tenant isolation bulletproof — automatic company_id injection into ALL database queries, Celery task propagation, and Redis key enforcement.

### What Already Exists
- `backend/app/middleware/tenant.py` — Extracts company_id from JWT, sets request.state
- `database/base.py` — SQLAlchemy engine, SessionLocal
- `backend/app/core/redis.py` — make_key() with tenant scoping
- `backend/app/tasks/base.py` — ParwaTask with company_id decorator
- `tests/unit/test_tenant_middleware.py` — 25+ tests
- `tests/unit/test_tenant_middleware_deep.py` — Deep isolation tests

### What To Build

| File | Description | Tests |
|------|-------------|-------|
| `database/base.py` (UPDATE) | Auto-inject company_id filter into all queries via session events | 20+ tests |
| `backend/app/middleware/tenant.py` (UPDATE) | Add tenant context propagation to Celery, thread-local storage | 15+ tests |
| `backend/app/core/redis.py` (UPDATE) | Enforce tenant key prefix validation on ALL operations | 10+ tests |
| `backend/app/tasks/base.py` (UPDATE) | Auto-inject company_id from tenant context into all tasks | 10+ tests |
| `tests/unit/test_tenant_auto_inject.py` | Verify every DB query has company_id filter | — |
| `tests/unit/test_tenant_celery_propagation.py` | Verify company_id flows from API → Celery → DB | — |
| `tests/unit/test_tenant_redis_isolation.py` | Verify no cross-tenant Redis access | — |
| `tests/integration/test_tenant_e2e.py` | Full flow: API → middleware → DB → Celery → Redis, all tenant-scoped | — |

### Key Implementation Details

**DB Auto-Injection:**
- Use SQLAlchemy `@event.listens_for(Session, 'before_flush')` to inject company_id
- Every model query automatically gets `WHERE company_id = :tenant_id`
- Explicit opt-out mechanism with `@bypass_tenant` decorator for admin/system queries
- Block any query that returns rows without company_id match

**Celery Propagation:**
- Store company_id in task headers during API request
- ParwaTask base class auto-extracts from headers
- Periodic tasks pass company_id from their iteration context

**Redis Enforcement:**
- All Redis operations MUST go through `make_key()` — no raw key access
- Audit all Redis calls in existing code for raw key usage
- Add key prefix validation: reject keys not matching `parwa:{company_id}:*`

### Acceptance Criteria
- [ ] No query can return data from a different company_id without explicit bypass
- [ ] Celery tasks inherit company_id from the originating API request
- [ ] All Redis keys follow `parwa:{company_id}:*` pattern
- [ ] Admin endpoints can bypass tenant filter (with audit logging)
- [ ] Bypass attempts from non-admin users are rejected and logged
- [ ] 100% coverage on all tenant isolation paths

### Loophole Checks
- [ ] Test: raw SQL query without company_id is blocked
- [ ] Test: Celery task without company_id is rejected
- [ ] Test: Redis MGET with keys from different tenants returns empty for unauthorized
- [ ] Test: JWT with tampered company_id is rejected
- [ ] Test: API key auth also enforces tenant isolation

---

## Day 21 — Health Check System + Monitoring Config

**Goal:** Complete the health check system with per-subsystem monitoring, dependency-aware health, Prometheus metrics endpoint, and create the missing monitoring config files.

### What Already Exists
- `backend/app/main.py` — `/health` and `/ready` endpoints (basic DB + Redis ping)
- `backend/app/tasks/celery_health.py` — Celery broker connectivity check
- `backend/app/core/redis.py` — `redis_health_check()`
- `database/base.py` — `check_db_health()`

### What To Build

| File | Description | Tests |
|------|-------------|-------|
| `backend/app/core/health.py` | Health check orchestrator: aggregate all subsystem checks, dependency graph, degraded state | 30+ tests |
| `backend/app/core/metrics.py` | Prometheus metrics: counters, histograms, gauges for all subsystems | 20+ tests |
| `backend/app/api/health.py` | Health API routes: `/health`, `/ready`, `/metrics`, `/health/detail` | 15+ tests |
| `monitoring/prometheus.yml` | Prometheus scrape configuration for all services | — |
| `monitoring/grafana_dashboards/system-overview.json` | Main system dashboard | — |
| `monitoring/grafana_dashboards/celery-queues.json` | Celery queue depth dashboard | — |
| `monitoring/grafana_dashboards/api-performance.json` | API latency dashboard | — |
| `monitoring/alerting/rules.yml` | Alertmanager rules for critical thresholds | — |
| `tests/unit/test_health.py` (UPDATE) | Expand with subsystem health tests | — |
| `tests/unit/test_metrics.py` | Prometheus metrics format and correctness | — |

### Subsystem Health Checks

| Subsystem | Check Method | Degraded Threshold | Down Threshold |
|-----------|-------------|-------------------|----------------|
| PostgreSQL | `SELECT 1` + connection pool stats | Pool > 80% used | Connection fails |
| Redis | `PING` + memory usage | Memory > 80% | Ping fails |
| Celery | Active workers count + queue depths | No workers or queue > 1000 | Broker unreachable |
| Celery Queues | Per-queue depth: default, ai_heavy, ai_light, email, webhook, analytics, training | Any queue > 500 | Queue > 5000 |
| Socket.io | Connected clients count + room count | — | Server not running |
| External: Paddle | HTTPS connectivity check | Timeout > 2s | Timeout > 5s |
| External: Brevo | HTTPS connectivity check | Timeout > 2s | Timeout > 5s |
| External: Twilio | HTTPS connectivity check | Timeout > 2s | Timeout > 5s |
| Disk Space | `os.statvfs()` | < 20% free | < 5% free |

### Health Response Format
```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2026-04-02T10:00:00Z",
  "version": "0.3.0",
  "uptime_seconds": 86400,
  "subsystems": {
    "postgresql": {"status": "healthy", "latency_ms": 2, "pool_used": 5, "pool_max": 20},
    "redis": {"status": "healthy", "latency_ms": 1, "memory_used_mb": 128, "memory_max_mb": 2048},
    "celery": {"status": "degraded", "workers": 1, "expected_workers": 2, "queues": {...}},
    "socketio": {"status": "healthy", "connected_clients": 42},
    "external_paddle": {"status": "healthy", "latency_ms": 150},
    "external_brevo": {"status": "healthy", "latency_ms": 80},
    "external_twilio": {"status": "unhealthy", "error": "connection timeout"}
  },
  "checks_total": 9,
  "checks_healthy": 7,
  "checks_degraded": 1,
  "checks_unhealthy": 1
}
```

### Prometheus Metrics
- `parwa_http_requests_total` (counter) — by method, path, status_code
- `parwa_http_request_duration_seconds` (histogram) — by method, path
- `parwa_active_websocket_connections` (gauge)
- `parwa_celery_queue_depth` (gauge) — by queue_name
- `parwa_celery_task_duration_seconds` (histogram) — by task_name
- `parwa_celery_task_total` (counter) — by task_name, status
- `parwa_db_query_duration_seconds` (histogram)
- `parwa_db_pool_size` (gauge)
- `parwa_redis_commands_total` (counter) — by command
- `parwa_redis_operation_duration_seconds` (histogram)

### Acceptance Criteria
- [ ] `/health` returns aggregate status with all subsystem details
- [ ] `/ready` returns 200 only if ALL critical subsystems are healthy
- [ ] `/metrics` returns Prometheus-formatted metrics
- [ ] `/health/detail` includes full subsystem breakdown with latencies
- [ ] Dependency graph: if DB is down, Celery shows "degraded" (not independent "down")
- [ ] External API checks have configurable timeouts and don't block startup
- [ ] `monitoring/prometheus.yml` exists and docker-compose.prod.yml mounts it correctly
- [ ] Grafana dashboards load without errors
- [ ] Alerting rules trigger on: unhealthy subsystem, high queue depth, high latency

### Loophole Checks
- [ ] Health endpoint itself doesn't leak company data
- [ ] Metrics endpoint doesn't expose tenant-specific counts
- [ ] External health checks don't send real data (only connectivity probes)
- [ ] Health check doesn't become a bottleneck (cached for 10s)

---

## Day 22 — Celery Task Modules + Beat Schedule Expansion

**Goal:** Create task modules for all 7 defined Celery queues and expand the Beat schedule with business-critical periodic tasks.

### What Already Exists
- `backend/app/tasks/celery_app.py` — 8 queues defined, task routing configured
- `backend/app/tasks/base.py` — ParwaTask, ParwaBaseTask, with_company_id decorator
- `backend/app/tasks/periodic.py` — 5 periodic tasks
- `backend/app/tasks/webhook_tasks.py` — 5 webhook provider stubs
- `backend/app/tasks/example_tasks.py` — Example tasks

### What To Build

| File | Queue | Description | Tests |
|------|-------|-------------|-------|
| `backend/app/tasks/email_tasks.py` | `email` | send_email_task (Brevo), render_template_task, send_bulk_notification_task | 25+ tests |
| `backend/app/tasks/analytics_tasks.py` | `analytics` | aggregate_metrics_task, calculate_roi_task, drift_detection_task | 20+ tests |
| `backend/app/tasks/ai_tasks.py` | `ai_heavy`, `ai_light` | classify_ticket_task (light), generate_response_task (heavy), score_confidence_task (light) | 20+ tests |
| `backend/app/tasks/training_tasks.py` | `training` | prepare_dataset_task, check_mistake_threshold_task, schedule_training_task | 15+ tests |
| `backend/app/tasks/approval_tasks.py` | `default` | approval_timeout_check_task, approval_reminder_task, batch_approval_task | 20+ tests |
| `backend/app/tasks/billing_tasks.py` | `default` | daily_overage_charge_task, invoice_sync_task, subscription_check_task | 20+ tests |
| `backend/app/tasks/periodic.py` (UPDATE) | — | Add 4 new Beat schedules | — |
| `backend/app/tasks/celery_app.py` (UPDATE) | — | Register all new task modules in routing | — |
| `tests/unit/test_email_tasks.py` | — | Email task tests | — |
| `tests/unit/test_analytics_tasks.py` | — | Analytics task tests | — |
| `tests/unit/test_ai_tasks.py` | — | AI task stub tests | — |
| `tests/unit/test_training_tasks.py` | — | Training task tests | — |
| `tests/unit/test_approval_tasks.py` | — | Approval task tests | — |
| `tests/unit/test_billing_tasks.py` | — | Billing task tests | — |

### New Beat Schedule Entries

| Task | Schedule | Queue | Building Code |
|------|----------|-------|--------------|
| `approval_timeout_check` | Every 15 minutes | `default` | BC-004, BC-009 |
| `approval_reminder_dispatch` | Every 30 minutes | `default` | BC-004, BC-006 |
| `daily_overage_charge` | Daily at 02:00 UTC | `default` | BC-004, BC-002 |
| `drift_detection_analysis` | Daily at 03:00 UTC | `analytics` | BC-004, BC-007 |
| `metric_aggregation` | Every 5 minutes | `analytics` | BC-004 |
| `training_mistake_check` | Every hour | `training` | BC-004, LOCKED #20 |

### Task Module Pattern (BC-004 Compliance)
Every task MUST:
1. Accept `company_id` as first parameter (via `@with_company_id` decorator)
2. Use `ParwaBaseTask` as base class (retry with exponential backoff, max_retries=3)
3. Route to correct queue via `@app.task(queue='...', base=ParwaBaseTask)`
4. Log structured JSON with correlation_id
5. Handle idempotency (check if work already done before executing)
6. Route failures to `dead_letter` queue after max retries

### Acceptance Criteria
- [ ] All 7 queues have at least one registered task module
- [ ] Every task follows BC-004 pattern (company_id first param, retry, DLQ)
- [ ] Beat schedule includes all 6 new periodic tasks
- [ ] Tasks are idempotent — running twice doesn't duplicate work
- [ ] Failed tasks route to dead_letter queue after 3 retries
- [ ] All tasks produce structured logs with correlation_id

### Loophole Checks
- [ ] Task without company_id is rejected at registration
- [ ] Task retry backoff is exponential (not linear)
- [ ] Dead letter queue is checked and purged periodically
- [ ] Long-running tasks have configurable soft/hard time limits
- [ ] Tasks don't share mutable state between executions

---

## Day 23 — Webhook Provider Handlers + Email Templates + Project Files + Cleanup

**Goal:** Implement actual webhook event processing for key providers, complete the email template library, create missing project management files, and clean up stale configs.

### What Already Exists
- `backend/app/security/hmac_verification.py` — HMAC verification for Paddle, Twilio, Shopify, Brevo
- `backend/app/services/webhook_service.py` — Base webhook processing (idempotency, audit)
- `backend/app/api/webhooks.py` — Webhook API routes
- `backend/app/tasks/webhook_tasks.py` — Async webhook processing stubs
- `backend/app/templates/emails/verification_email.html` — 1 template
- `backend/app/templates/emails/password_reset_email.html` — 1 template

### What To Build

#### Webhook Provider Handlers

| File | Provider | Events | Tests |
|------|----------|--------|-------|
| `backend/app/webhooks/paddle_handler.py` | Paddle | subscription.created, subscription.updated, subscription.cancelled, payment.succeeded, payment.failed | 30+ tests |
| `backend/app/webhooks/brevo_handler.py` | Brevo | inbound_email (parse → ticket creation) | 15+ tests |
| `backend/app/webhooks/twilio_handler.py` | Twilio | sms.incoming, voice.call.started, voice.call.ended | 15+ tests |
| `backend/app/webhooks/shopify_handler.py` | Shopify | orders.create, customers.create | 10+ tests |
| `backend/app/webhooks/__init__.py` | — | Handler registry, dispatch | — |
| `tests/unit/test_paddle_handler.py` | — | Paddle webhook tests | — |
| `tests/unit/test_brevo_handler.py` | — | Brevo webhook tests | — |
| `tests/unit/test_twilio_handler.py` | — | Twilio webhook tests | — |

#### Email Templates (BC-006)

| File | Purpose |
|------|---------|
| `backend/app/templates/emails/welcome_email.html` | New account welcome |
| `backend/app/templates/emails/mfa_enabled.html` | MFA activation confirmation |
| `backend/app/templates/emails/session_revoked.html` | Session revoked notification |
| `backend/app/templates/emails/api_key_created.html` | API key creation confirmation |
| `backend/app/templates/emails/approval_notification.html` | Approval pending notification |
| `backend/app/templates/emails/overage_notification.html` | Overage charge notification |

#### Project Management Files

| File | Purpose |
|------|---------|
| `AGENT_COMMS.md` | Inter-agent communication log (Technical Assistant v9 requirement) |
| `ERROR_LOG.md` | Error tracking log (Technical Assistant v9 requirement) |
| `PROJECT_STATE.md` | Live project state memory (Technical Assistant v9 requirement) |

#### Cleanup

| Task | Description |
|------|-------------|
| Delete `infra/docker/docker-compose.prod.yml` | Remove stale file (root version is authoritative) |
| Delete `infra/docker/.env.example` | Remove stale file (references wrong API keys) |
| Update `PROJECT_STATUS.md` | Add Days 19-23 tracking rows |
| Update `INFRASTRUCTURE_GAPS_TRACKER.md` | Mark Week 3 items complete, add new future gaps |

### Acceptance Criteria
- [ ] Paddle webhook processes all subscription and payment events correctly
- [ ] Brevo inbound email webhook creates a ticket draft
- [ ] Twilio SMS webhook stores the message and triggers notification
- [ ] All webhook handlers verify HMAC before processing
- [ ] All webhook handlers are idempotent (duplicate event_id ignored)
- [ ] All webhook handlers respond within 3 seconds (async processing for heavy work)
- [ ] 8 email templates exist with consistent branding and layout
- [ ] AGENT_COMMS.md, ERROR_LOG.md, PROJECT_STATE.md created
- [ ] Stale infra files removed
- [ ] docker-compose.prod.yml mounts monitoring/ files without errors

### Loophole Checks
- [ ] Webhook handler rejects events without valid HMAC (even if payload looks valid)
- [ ] Webhook handler rejects oversized payloads (>1MB)
- [ ] Webhook handler logs all rejected events for debugging
- [ ] Email templates don't contain any dynamic user data that could be XSS
- [ ] Email templates have proper unsubscribe/management links
- [ ] Webhook processing doesn't block the main thread (all async)

---

## Week 3 Day-by-Day Summary

| Day | Focus | New Files | Est. New Tests | Gaps Closed |
|-----|-------|-----------|----------------|-------------|
| **Day 19** | Socket.io Business Event System | 4 new + 2 updates | ~70 | GAP 1.1 |
| **Day 20** | Multi-Tenant Middleware Hardening | 3 new + 3 updates | ~55 | GAP 1.2 |
| **Day 21** | Health Check System + Monitoring | 3 new + 4 monitoring configs | ~65 | GAP 1.3 + GAP 2.1 |
| **Day 22** | Celery Task Modules + Beat Schedule | 6 new + 2 updates | ~120 | GAP 1.4 + GAP 3.2 |
| **Day 23** | Webhook Handlers + Templates + Cleanup | 4 new + 6 templates + 3 project files | ~70 | GAP 1.5 + GAP 2.2 + GAP 3.1 |
| **TOTAL** | | **~17 new + ~11 updates** | **~380** | **All Week 3 gaps** |

**Expected Week 3 End State:**
- Tests: 1,497 → ~1,877
- All 5 roadmap Week 3 modules complete
- All infrastructure gaps from audit resolved
- Monitoring stack functional
- Phase 1 Foundation: 100% COMPLETE
- Ready for Phase 2: Core Business Logic

---

## Dependencies Within Week 3

```
Day 19 (Socket.io Events) ─── independent
Day 20 (Tenant Middleware) ─── independent
Day 21 (Health Checks) ────── independent
Day 22 (Celery Tasks) ─────── depends on Day 20 (tenant context in tasks)
Day 23 (Webhooks + Cleanup) ─ depends on Day 19 (emit events), Day 22 (billing tasks)
```

Days 19, 20, 21 are parallelizable. Days 22 and 23 depend on earlier days.

---

**END OF WEEK 3 ROADMAP**
