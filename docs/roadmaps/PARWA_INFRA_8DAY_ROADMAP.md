# PARWA Infra 8-Day Roadmap

**Version:** 2.0 (Post-Reset Assessment)
**Date:** April 17, 2026
**Status:** ACTIVE

---

## Overview

This 8-day infrastructure roadmap addresses every identified gap across PARWA's 18-part production readiness plan. Following the comprehensive v2.0 reset on April 16, 2026, the project was audited against honest completion metrics. The result: while the codebase contains approximately 2.7 MB of backend core logic across 95+ files, multiple critical infrastructure layers remain either unimplemented, partially wired, or running in stub/mock mode.

This roadmap prioritizes ruthlessly by blast radius: security vulnerabilities first (data exposure), then billing architecture bugs (revenue impact), then operational infrastructure (reliability at scale).

---

## Gap Analysis Summary

### Critical Severity (Immediate Revenue/Data Risk)

| Gap ID | Category | Description | Roadmap Part |
|--------|----------|-------------|--------------|
| BG-13 | Billing | Real-time usage counting not metered; tickets consumed without tracking | Part 15 |
| BG-16 | Billing | Payment failure does not trigger immediate service stop (Netflix rule violated) | Part 15 |
| BG-14 | Billing | Feature blocking on variant limits not enforced (entitlements bypass) | Part 3/15 |
| A1 | Security | Hardcoded refresh token pepper with insecure default in production config | Part 18 |
| D1 | Security | CORS wildcard fallback with credentials enabled on API endpoints | Part 18 |
| F1 | Security | All service ports exposed to 0.0.0.0 in development docker-compose | Part 18 |
| F2 | Security | No Redis authentication configured in any environment | Part 18 |
| E1 | Security | PostgreSQL internal SSL disabled between services | Part 18 |
| I1 | Tech Debt | RAG pipeline uses MockVectorStore with random similarity scores | Part 1 |

### High Severity (Operational Risk)

| Gap ID | Category | Description | Roadmap Part |
|--------|----------|-------------|--------------|
| BG-01 | Billing | Only 5 of 25+ Paddle webhook events handled | Part 15 |
| BG-07 | Billing | Webhook ordering/parallel processing causes race conditions | Part 15 |
| BG-08 | Billing | No idempotency key storage for payment operations | Part 15 |
| BG-15 | Billing | No missed webhook detection mechanism | Part 15 |
| A2 | Security | Frontend tokens stored in localStorage (XSS-extractable) | Part 18 |
| A3 | Security | No CSRF protection on any state-changing endpoint | Part 18 |
| F3 | Security | Weak default database password in production config | Part 18 |
| F6 | Security | Celery worker has no health check in production deployment | Part 1 |
| MON-1 | Monitoring | Prometheus/Grafana/Alertmanager config files do not exist | Part 1 |
| HEALTH-1 | Infra | ProviderHealthTracker uses in-memory state; breaks with 2+ worker replicas | Part 1 |
| GSD-1 | Infra | GSD tenant configs stored in-memory only; lost on restart | Part 1 |
| GSD-2 | Infra | shared/gsd_engine/ Redis dual-storage persistence directory missing | Part 1 |

### Forward-Looking Gaps (Parts 7-18 Dependencies)

| Gap ID | Category | Description | Blocks Part |
|--------|----------|-------------|-------------|
| SHADOW-1 | Shadow Mode | system_mode enum on Company model not implemented | Part 11 |
| SHADOW-2 | Shadow Mode | shadow_log DB table not created | Part 11 |
| SHADOW-3 | Shadow Mode | Channel interceptor middleware for outbound interception missing | Part 11 |
| CHANNEL-1 | Channels | Chat widget Socket.io client library completely absent | Part 14 |
| CHANNEL-2 | Channels | SMS/Voice Twilio integration infrastructure not wired | Part 14 |
| CHANNEL-3 | Channels | Social media webhook handlers (Twitter/Instagram/FB) not built | Part 14 |
| CONTEXT-1 | Memory | Omnichannel session linking tables and cross-channel identity bridge missing | Part 8 |
| DSPY-1 | AI Engine | DSPy running in stub mode; optimization pipeline inactive | Part 9 |
| LITELLM-1 | AI Engine | LiteLLM imported but not used; raw httpx calls to provider APIs | Part 9 |
| MAKER-1 | MAKER | Multi-agent orchestration system entirely stubs (~15%) | Part 7 |
| CI/CD-1 | DevOps | deploy-backend.yml and deploy-frontend.yml are echo placeholders | All |
| K8S-1 | DevOps | Zero Kubernetes manifests exist for any service | Part 1 |
| GCS-1 | Storage | GCP Storage Backend raises NotImplementedError; falls back to local filesystem | Part 12 |

---

## Day 1: Security Hardening - Critical Fixes

**Target:** All 12 CRITICAL security findings from the 76-item security audit.

### 1.1 Authentication & Token Security (A1, A2)
- Generate 256-bit cryptographic pepper at deployment time via secret management
- Migrate frontend token storage from localStorage to httpOnly secure cookies (SameSite=Strict)
- Add startup validation that refuses boot if pepper matches insecure default
- Update backend auth middleware to read tokens from cookies for browser requests

### 1.2 CORS & CSRF Protection (A3, D1)
- Remove wildcard CORS fallback; require explicit ALLOWED_ORIGINS env var
- Implement CSRF double-submit cookie pattern (X-CSRF-Token header validation)
- Block all state-changing requests (POST/PUT/DELETE/PATCH) without valid CSRF token

### 1.3 Network & Docker Security (F1, F2, F3, E1)
- Bind all internal service ports to 127.0.0.1 in production compose (only Nginx on 80/443)
- Enable Redis requirepass with strong password from env vars
- Enable PostgreSQL SSL for inter-service communication (ssl=on in postgresql.conf)
- Replace default database password with generated strong password

### 1.4 Additional Critical Items
- F4: Restrict Prometheus lifecycle API to monitoring network only
- F5: Remove production frontend port 3000 exposure; route only via Nginx TLS
- Add security headers middleware (X-Frame-Options, CSP, X-Content-Type-Options, HSTS)
- Fix admin endpoints using wrong role check
- Add HMAC signature verification to all webhook endpoints

### Deliverables
| Deliverable | Verification Method |
|-------------|-------------------|
| Cryptographic pepper generation script | Script outputs 256-bit hex; startup rejects insecure default |
| httpOnly cookie auth middleware | Browser DevTools shows cookies; no tokens in localStorage |
| CSRF double-submit middleware | POST without X-CSRF-Token returns 403 |
| CORS strict origin config | Request from unlisted origin returns CORS error |
| Redis auth configuration | redis-cli ping fails without -a flag |
| PostgreSQL SSL enabled | pg_isready reports SSL connection |
| Security headers present | curl -I shows X-Frame-Options, CSP, HSTS |

---

## Day 2: Safety & Compliance - PII, Injection, Guardrails

**Target:** PII 40% → 90%+, Prompt Injection 15% → 95%+, Guardrails on real output, GDPR endpoints

### 2.1 PII Redaction Engine Upgrade
- Add NER-based fallback detection using spaCy
- Handle short emails, IP addresses (IPv4/IPv6), partial phone numbers, context names
- Verify AES-256-GCM encryption vault with tenant-scoped keys
- Add audit log entries for every redaction (type, position, one-way hash)

### 2.2 Prompt Injection Defense Upgrade
- Add SQL injection, XSS, command injection, role-play, system prompt extraction detection
- Implement multi-turn detection (conversation-level state)
- Add token smuggling detection (unicode homoglyphs, zero-width chars)
- Risk scoring system: 80+ blocks, 50-79 human review, 20-49 logging

### 2.3 Guardrails on Real LLM Outputs
- Wire all 8 guardrail layers to actual Smart Router pipeline responses
- Middleware intercepts every LLM response before response generator
- Blocked responses route to BlockedResponseManager for admin review
- Information leakage prevention: block LLM names, routing strategy, system prompts

### 2.4 GDPR Compliance Endpoints
- DELETE /api/gdpr/erasure - Cascading delete with anonymized analytics retention
- GET /api/gdpr/export - ZIP archive of all personal data in structured JSON
- Both endpoints require re-authentication (password confirmation)

### Deliverables
| Deliverable | Target | Verification |
|-------------|--------|-------------|
| PII detection coverage | 40% to 90%+ | 200-sample test suite with known PII patterns |
| Prompt injection coverage | 15% to 95%+ | OWASP LLM Top 10 attack patterns |
| Risk scoring system | 0-100 score with 3 tiers | Score 85+ blocks, 60 flags, 30 logs |
| Multi-turn detection | Active across conversation | Split payload across 3 turns detected |
| Guardrails on real output | All 8 layers active | 100 real responses; zero false negatives on safety |
| GDPR erasure endpoint | Cascading delete functional | Data purged; analytics anonymized |
| GDPR export endpoint | ZIP with structured JSON | Export matches manual DB query |

---

## Day 3: Billing Architecture - Critical Bug Fixes

**Target:** 5 critical architectural bugs in billing system

### 3.1 Downgrade Execution (Never Fires)
- Implement downgrade_execution Celery task firing at period end
- Cascade: update subscription → reduce quota → deprovision agents → reduce KB limit → disable voice channels → update variant config → send confirmation email
- Each step atomic with rollback mechanism

### 3.2 Usage Metering System (BG-13)
- Hook into ticket lifecycle at creation time
- Redis counter: `parwa:{company_id}:usage:{period_id}:tickets` (atomic INCR)
- PostgreSQL persistence for reconciliation
- Block on overage with $0.10/ticket charge trigger
- Celery beat daily reconciliation + period reset

### 3.3 Variant-Entitlement Disconnection (BG-14)
- Centralized entitlements service with `can_access(resource_type, count)` method
- Enforce all 6 dimensions: tickets, agents, team members, voice channels, KB docs, AI techniques
- Redis-cached plan limits with PostgreSQL fallback
- Clear denial messages with upgrade prompts

### 3.4 Calendar vs Billing Period Mismatch
- Migrate all period calculations to Paddle's billing cycle dates
- Store current_period_start and current_period_end on subscription record
- Data migration script to realign all existing periods

### 3.5 Payment Failure Immediate Stop (BG-16)
- payment_failure_handler Celery task on payment_failed webhook
- Immediate: SUSPEND company → revoke tokens → block channels → show payment-required → send notification → start 7-day data retention timer
- Idempotent with full audit logging

### Deliverables
| Deliverable | Verification |
|-------------|-------------|
| Downgrade execution task | High to Mini: agents deprovisioned, limits reduced, voice disabled |
| Usage metering with Redis + PG | Create 2000 tickets on Mini plan; 2001st blocked |
| Overage billing trigger | Over-limit ticket triggers $0.10 charge via Paddle API |
| Entitlements service | 6th agent on Mini (limit 1) returns denial with upgrade link |
| Period alignment migration | All subscription periods match Paddle billing cycle dates |
| Payment failure immediate stop | Failed payment suspends company within 60 seconds |

---

## Day 4: Billing - Webhook & Payment Infrastructure

**Target:** Complete webhook coverage, idempotency, payment reliability

### 4.1 Complete Paddle Webhook Coverage (BG-01)
- Handle all 25+ Paddle events (subscription.*, payment.*, customer.*, transaction.*, notification.*, bill.*)
- HMAC verification on all events
- Idempotent processing within single DB transaction per event

### 4.2 Idempotency & Webhook Reliability (BG-07, BG-08, BG-15)
- idempotency_keys table with UNIQUE constraint on key_hash
- Sequence number enforcement per company (reject out-of-order)
- Missed webhook detection Celery beat task (every 15 min, compare with Paddle API)
- Dead letter queue monitoring with alerts

### 4.3 Payment Infrastructure Services (10 modules)
1. paddle_client.py - Typed Paddle API wrapper with retry + circuit breaker
2. subscription_service.py - CRUD with Paddle sync
3. proration_service.py - Mid-period plan change calculations
4. usage_service.py - Real-time metering with Redis counters
5. invoice_service.py - Invoice generation + PDF export
6. refund_service.py - Refund processing via Paddle API
7. payment_method_service.py - Payment method management
8. entitlement_service.py - Centralized access control
9. billing_cycle_service.py - Period management and alignment
10. notification_service.py - Payment-related email/SMS notifications

### 4.4 Database Schema (8 new tables)
- client_refunds, payment_methods, usage_records, variant_limits
- idempotency_keys, webhook_sequences, proration_audits, payment_failures

### Deliverables
| Deliverable | Verification |
|-------------|-------------|
| 20 additional webhook handlers | All 25 Paddle event types processed correctly |
| Idempotency key table + logic | Duplicate delivery = single DB update |
| Webhook sequence enforcement | Out-of-order event rejected |
| Missed webhook detection | Kill Celery 30 min; restart; detector backfills |
| 10 billing service modules | All pass unit tests with mocked Paddle |
| 8 Alembic migrations | Clean apply; correct indexes and FKs |

---

## Day 5: Monitoring, Health & Distributed State

**Target:** Observability stack, distributed health tracking, GSD persistence

### 5.1 Monitoring Stack Configuration (MON-1)
Create all missing config files:
- **monitoring/prometheus.yml** - Scrape backend, worker, Redis/PG/Node exporters (15s interval, 15d retention)
- **monitoring/alerting/rules.yml** - 6 rules: error rate >5%, p95 >2s, queue depth >100, Redis failures, PG replication lag, disk >80%
- **monitoring/alertmanager/alertmanager.yml** - Route to Slack + email, severity-based routing
- **monitoring/grafana/provisioning/** - 3 dashboards: System Overview, Application Metrics, Business Metrics
- **monitoring/grafana_dashboards/** - Pre-built JSON dashboard files

### 5.2 Distributed Provider Health Tracking (HEALTH-1)
- Migrate ProviderHealthTracker from in-memory to Redis
- Key structure: `parwa:global:health:{provider_name}`
- Fields: consecutive_failures, last_failure_at, circuit_state, avg_latency_ms, total_requests
- Redis WATCH/MULTI/EXEC for atomic read-modify-write
- Celery beat probe every 30 seconds

### 5.3 GSD Engine Tenant Config Persistence (GSD-1, GSD-2)
- Create `shared/gsd_engine/` directory with config_persistence.py, state_sync.py
- Hybrid persistence: PostgreSQL (JSONB, authoritative) → Redis (cache, 5min TTL) → memory (local, 30s refresh)
- Bootstrap from PostgreSQL on startup
- Create `shared/gsd_engine/` directory structure

### 5.4 Celery Worker Health Check (F6)
- HTTP health check server on port 8001 within worker process
- Reports: heartbeat status, active tasks, queue depths, memory usage, last task completion
- docker-compose.prod.yml healthcheck: 30s interval, 5s timeout, 3 failure threshold

### Deliverables
| Deliverable | Verification |
|-------------|-------------|
| Prometheus config | All targets show UP in status page |
| Grafana dashboards | 3 dashboards render with data |
| Alert rules (6 rules) | Test alert → Slack notification within 60s |
| Redis health tracking | Kill provider on worker A; worker B stops routing within 30s |
| GSD config persistence | Restart backend; configs restored from PostgreSQL |
| shared/gsd_engine/ created | Directory contains config_persistence.py, state_sync.py |
| Worker health check | curl localhost:8001/health returns JSON with all 5 fields |

---

## Day 6: RAG, pgvector, and AI Pipeline Hardening

**Target:** Replace all mock/stub AI infra with production implementations

### 6.1 pgvector Integration (I1)
- Enable pgvector extension: `CREATE EXTENSION IF NOT EXISTS vector`
- Add embedding column (vector(1536)) to knowledge_base_chunks table
- Create HNSW index for fast approximate nearest neighbor search
- Replace MockVectorStore with PgVectorStore using async SQLAlchemy
- Cosine distance similarity queries

### 6.2 Knowledge Base Pipeline Activation (F-033)
- Wire 4-stage pipeline: Extract → Chunk → Embed → Index
- Real embeddings via Smart Router embedding provider (OpenAI text-embedding-3-small)
- Celery beat task to reindex all existing documents
- 50-pair retrieval quality validation test (recall@5 target: 0.7+)

### 6.3 LiteLLM Integration (LITELLM-1)
- Activate litellm.acompletion() as primary routing (replace raw httpx)
- Leverage built-in retry, fallback, token counting, request/response logging
- Log all requests to model_usage_logs table for cost tracking
- Wire model_failover.py to LiteLLM's native error classification
- Remove raw httpx calls entirely

### 6.4 DSPy Optimization Pipeline (DSPY-1)
- Configure DSPy task definitions for each AI technique (DSPy Signatures)
- Set up BootstrapFewShot or MIPROv2 teleprompter
- Weekly optimization Celery beat task (2-4 AM UTC)
- Store optimized prompts in DB with A/B test metadata
- Wire results to technique_executor.py
- Preserve tier access controls (Tier 1 always, Tier 2 conditional, Tier 3 PARWA High)

### Deliverables
| Deliverable | Verification |
|-------------|-------------|
| pgvector extension enabled | SELECT extversion FROM pg_extension WHERE extname='vector' |
| Embedding column + index | HNSW index visible in pg_indexes |
| PgVectorStore replaces Mock | Query returns actual cosine similarity results |
| KB pipeline end-to-end | Upload PDF; query returns relevant chunks |
| 50-pair retrieval test | Average recall@5 above 0.7 |
| LiteLLM active | All LLM calls via litellm.acompletion(); no raw httpx |
| DSPy weekly optimization | Beat task runs; optimized prompts stored in DB |

---

## Day 7: Shadow Mode Infrastructure & Channel Foundation

**Target:** Shadow mode schema, interceptors, Socket.io client, Twilio infra

### 7.1 Shadow Mode Database Schema
- Add to companies table: `system_mode ENUM('SHADOW','SUPERVISED','GRADUATED') DEFAULT 'SHADOW'`, `undo_window_seconds INT DEFAULT 300`
- New table: shadow_log (id, company_id, ticket_id, action_type, action_payload JSONB, ai_confidence_score, risk_level, status, reviewed_by, timestamps)
- New table: shadow_email_hold (id, company_id, message_id, addresses, subject, body, ai_generated, held_at, status)
- New table: shadow_sms_hold (id, company_id, twilio_message_id, numbers, body, ai_generated, held_at, status)

### 7.2 Channel Interceptor Middleware
- Common interface with channel-specific adapters
- SHADOW mode: all outbound held for approval
- SUPERVISED mode: auto-execute LOW risk (confidence >90), hold HIGH risk
- GRADUATED mode: auto-execute all with async logging
- Adapters: EmailInterceptor (Brevo), SMSInterceptor (Twilio), VoiceInterceptor (Twilio), ChatInterceptor (Socket.io)
- Undo operation via Brevo recall API + Twilio message cancellation within undo_window_seconds

### 7.3 Socket.io Client Library (CHANNEL-1)
- Create frontend/src/lib/socket.ts
- JWT authentication, auto-reconnection with exponential backoff
- Event buffer for missed events during disconnection
- Typed event handlers for all server events
- Room management for tenant-scoped channels
- Export useSocket() React hook

### 7.4 Twilio Infrastructure Foundation (CHANNEL-2)
- Create backend/app/core/channels/twilio_client.py
- Webhook endpoints: POST /api/channels/sms/inbound, POST /api/channels/voice/inbound
- HMAC signature verification (X-Twilio-Signature header)
- TCPA consent tracking via consent_records table
- Message rate limiting: 5 per thread per 24 hours

### Deliverables
| Deliverable | Verification |
|-------------|-------------|
| system_mode enum + migration | Company model has SHADOW/SUPERVISED/GRADUATED |
| shadow_log table | Insert test entry; query returns with all JSONB fields |
| shadow hold queue tables | Hold email → verify in queue → approve → verify sent |
| Channel interceptor middleware | SHADOW company: email held, not delivered |
| Undo within window | Approve email → undo within 5 min → recall API called |
| Socket.io client library | Dashboard receives real-time ticket updates |
| Twilio client wrapper | Send test SMS; verify delivery |
| Twilio webhook HMAC | Unsigned = 401; signed = processes |

---

## Day 8: CI/CD, Storage, and Forward-Looking Infra

**Target:** Deployment pipelines, cloud storage, SSL, Wave 2-5 preparation

### 8.1 CI/CD Pipeline Activation (CI/CD-1)
**Backend pipeline:** lint (ruff) → test (pytest --cov) → build Docker → push to registry → deploy → smoke tests
**Frontend pipeline:** type check (tsc) → lint (eslint) → test (jest) → build Next.js → build Docker → push → deploy
**Security scanning:** Trivy container scan, dependency audit for CVEs
**Rollback:** Git SHA image tags, previous-version tag for single-command redeploy

### 8.2 GCP Storage Backend Completion (GCS-1)
- Implement all GCPStorageBackend methods (currently NotImplementedError)
- Upload/download/delete/signed URLs using google-cloud-storage SDK
- Chunked uploads (>5MB), multipart uploads (>100MB)
- Retry logic for transient GCS errors
- Credentials via GOOGLE_APPLICATION_CREDENTIALS env var

### 8.3 Nginx SSL Termination
- Verify infra/docker/generate-ssl-certs.sh for development
- Production Nginx config: SSL on 443, HTTP→HTTPS redirect, reverse proxy to frontend/backend, WebSocket upgrade (/ws), security headers
- Create nginx/ssl/ directory with Let's Encrypt renewal README

### 8.4 Forward-Looking Infra Dependencies (Wave 2-5)

| Future Part | Infra Prerequisite | Depends On Day |
|-------------|-------------------|----------------|
| Part 7 (MAKER) | Multi-agent Celery queues + Redis pub/sub | Day 5 |
| Part 8 (Context) | Omnichannel session tables + identity bridge | Day 7 |
| Part 9 (AI Techniques) | pgvector + LiteLLM + DSPy operational | Day 6 |
| Part 10 (Jarvis) | Socket.io client + billing context API | Day 5 + 7 |
| Part 11 (Shadow Mode) | Shadow schema + interceptors + Socket.io | Day 7 |
| Part 12 (Dashboard) | Socket.io client + all backend APIs wired | Day 7 + 8 |
| Part 13 (Tickets) | Dashboard UI page + SLA management tables | Day 8 |
| Part 14 (Channels) | Twilio infra + social media webhook handlers | Day 7 |
| Part 15 (Billing) | All billing services + webhook coverage + metering | Day 3 + 4 |
| Part 16 (Analytics) | Materialized views + Redis analytics cache | Day 5 |
| Part 17 (Integrations) | MCP server + webhook handler framework | Day 8 |
| Part 18 (Safety) | PII 90%+ + injection 95%+ + GDPR + Docker | Day 1 + 2 |

### Deliverables
| Deliverable | Verification |
|-------------|-------------|
| Backend CI/CD pipeline | Push to main → build, test, deploy, smoke test passes |
| Frontend CI/CD pipeline | Push → type check, lint, test, build, deploy |
| Container image scanning | Trivy runs; HIGH/CVSS 9+ blocks deploy |
| Rollback mechanism | Rollback workflow redeploys previous tagged image |
| GCP Storage Backend | Upload file → signed URL → download via URL |
| Nginx SSL config | HTTPS serves frontend; /api proxies; /ws upgrades |
| Forward-looking checklist | Each Part 7-17 has documented Day dependencies |

---

## Deliverable Summary

| Day | Focus Area | Key Deliverables | Gap Count |
|-----|-----------|-----------------|-----------|
| Day 1 | Security Hardening | Auth tokens, CORS/CSRF, Docker hardening, Redis auth, PG SSL, security headers | 12 critical |
| Day 2 | Safety & Compliance | PII 90%+, injection 95%+, guardrails on real output, GDPR endpoints | 15 high |
| Day 3 | Billing Critical Bugs | Downgrade execution, usage metering, entitlements, payment failure stop | 5 critical |
| Day 4 | Billing Infrastructure | 25 webhook handlers, idempotency, 10 billing services, 8 DB tables | 13 high |
| Day 5 | Monitoring & State | Prometheus/Grafana configs, distributed health, GSD persistence | 7 medium |
| Day 6 | AI Pipeline Hardening | pgvector activation, KB pipeline, LiteLLM routing, DSPy optimization | 6 critical |
| Day 7 | Shadow Mode & Channels | Shadow schema, interceptors, Socket.io client, Twilio infra | 10 high |
| Day 8 | CI/CD & Storage | GitHub Actions pipelines, GCP storage, Nginx SSL, Wave 2-5 checklist | 8 medium |

**Total: 76 infrastructure gaps** + 12 forward-looking prerequisites for Parts 7-17
