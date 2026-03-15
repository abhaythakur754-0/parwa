# PARWA
60-Week Parallel-Agent Roadmap — Version 7.0
Multiple Agents · Zero Same-Day Dependencies · Retry-Until-Pass · Single Push Per File
The 6 Rules of Parallel-Agent Development
Rule 1 Same-day files have ZERO dependencies on each other — multiple agents build in parallel
Rule 2 Files that depend on other files go on a LATER day — never the same day
```
Rule 3 Agent fails unit test → retries and fixes until it passes → THEN pushes (one push only)
```
Rule 4 End of each day → you manually trigger daily integration test for all that day's files
```
Rule 5 Day 6 every week → full week integration test (from the roadmap — unchanged)
```
Rule 6 Antigravity auto-updates PROJECT_STATE.md — you never touch it manually
What Changed in Version 6.0
These 7 changes are integrated into the roadmap at the correct weeks. Look for 'v6.0' annotations in Weeks 3, 4, 13, and
23.
# Change Details Slot
1 RLS Security
Testing
```
Was: weekly. Now: runs on EVERY commit from Wk3. CI job rls-test.yml added. 30+
```
isolation tests.
Wk
3
2 Instant Demo
System
```
NEW: Chat demo FREE (20 msgs/session, no login for first 10). Voice demo $1/call (5
```
```
min max, Stripe gate). Light/Medium tier routing. Files: demo_service.py,
```
DemoChatWidget.tsx, VoiceDemoPaywall.tsx, backend/api/demo.py
Wk
3-4
3 Incoming Call
Handling
```
NEW rule: PARWA MUST answer in <6 sec (2 rings). Never IVR-only. 5-step call flow.
```
```
Files: incoming_calls.py, voice_handler.py, tests/voice/
```
Wk
4
4 Quality Coach —
PARWA High
only
```
NEW: Scores accuracy/empathy/efficiency per conversation. Feeds Agent Lightning.
```
```
Files: analyzer.py, reporter.py, notifier.py, QualityDashboard.tsx, QualityAlerts.tsx + 3 DB
```
tables + 5 API endpoints
Wk
13
5 Agent Lightning
Training Platform
```
Was: RunPod paid GPU ($50/mo). Now: Unsloth + Google Colab — BOTH FREE. Files:
```
```
colab_trainer.py, unsloth_optimizer.py (new). trainer.py updated.
```
Wk
23
6 Training
Threshold
```
Was: 100 mistakes. Now: 50 mistakes — AI learns 2x faster. constants.py:
```
```
TRAINING_THRESHOLD=50. dataset_builder.py updated.
```
Wk
23
7 Business Model Was: hybrid free onboarding + paid. Now: paid subscription only from Day 1. All features
from Day 1. billing_service.py updated.
Wk
17
Phase 1 — Foundation & Infrastructure
Build the foundation. No AI yet. Just the infrastructure everything else depends on. Files within each day are fully
independent — multiple agents build them in parallel.
Week 1 — Foundation & Infrastructure
Goal for This Week
Set up the entire project foundation in parallel. Day 1 is special — it's the only day where you must do things
sequentially because the repo doesn't exist yet. From Day 2 onwards, multiple agents build truly independent files
simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Sequential setup day — do these in order before agents start
Day 1 Agent File to Build Depends On
```
Agent 1 You (manual) Create GitHub repo + monorepo
```
structure + .gitignore
None — fully independent
```
Agent 2 You (manual) docker-compose.yml +
```
.env.example
None — fully independent
```
Agent 3 You (manual) Makefile + README.md skeleton None — fully independent
```
Day 2: First parallel day — all 4 agents start simultaneously
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Config shared/core_functions/config.py None — fully independent
Agent 2 Agent 2 — Legal Doc 1 legal/privacy_policy.md None — fully independent
Agent 3 Agent 3 — Legal Doc 2 legal/terms_of_service.md None — fully independent
Agent 4 Agent 4 — Legal Doc 3 legal/data_processing_agreement.md None — fully independent
```
Day 3: Agent 1 needs config.py (Day 2). Agents 2-4 are independent of everything
```
Day 3 Agent File to Build Depends On
```
Agent 1 Agent 1 — Logger shared/core_functions/logger.py config.py (Day 2)
```
Agent 2 Agent 2 — Legal Doc 4 legal/liability_limitations.md None — fully independent
Agent 3 Agent 3 — Legal Doc 5 legal/tcpa_compliance_guide.md None — fully independent
Agent 4 Agent 4 — Feature Flags feature_flags/mini_parwa_flags.json
- parwa_flags.json +
parwa_high_flags.json
None — fully independent
```
Day 4: Agents 1-2 need config+logger (Days 2-3). Agents 3-4 are fully independent
```
Day 4 Agent File to Build Depends On
```
Agent 1 Agent 1 — Security shared/core_functions/security.py config.py, logger.py (Days
```
```
2-3)
```
```
Agent 2 Agent 2 — AI Safety shared/core_functions/ai_safety.py config.py, logger.py (Days
```
```
2-3)
```
Agent 3 Agent 3 — BDD Mini docs/bdd_scenarios/mini_parwa_bdd.md None — fully independent
Agent 4 Agent 4 — BDD PARWA docs/bdd_scenarios/parwa_bdd.md +
parwa_high_bdd.md
None — fully independent
```
Day 5: Agents 1-3 need security+ai_safety (Day 4). Agent 4 is independent
```
Day 5 Agent File to Build Depends On
```
Agent 1 Agent 1 — Compliance shared/core_functions/compliance.py security.py (Day 4)
```
Agent 2 Agent 2 — Audit Trail shared/core_functions/audit_trail.py security.py, logger.py
```
(Days 3-4)
```
Agent 3 Agent 3 — Pricing shared/core_functions/pricing_optimizer.py config.py, logger.py
```
(Days 2-3)
```
Agent 4 Agent 4 — ADR Docs docs/architecture_decisions/001_monorepo.md
- 002_modular_monolith.md +
003_openrouter.md
None — fully
independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test for all Week 1 files together. Verify: config loads all env vars → logger reads from config and
outputs structured JSON → security.py uses config for JWT secret → compliance.py calls logger correctly →
audit_trail.py hash chain validates → pricing_optimizer imports cleanly. Run: pytest
tests/integration/test_week1_foundation.py. Expected: all imports resolve, no circular dependencies, all modules
initialise without errors.
Week Complete When All Pass:
```
1 pytest tests/unit/ passes for all 5 Day files (config, logger, security, compliance, audit_trail)
```
2 No circular imports between any Week 1 files
3 docker-compose up starts without errors
4 All legal documents present and complete
5 All feature flag JSON files valid
6 Day 6 integration test: all modules initialise together without errors
Week 2 — Foundation & Infrastructure
Goal for This Week
```
Build all shared utilities and database layer in parallel. Utilities (monitoring, error handlers, cache, storage) are
```
fully independent of each other. Database setup is independent of utilities. All can be built simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: All 4 agents fully independent — no dependencies on each other
Day 1 Agent File to Build Depends On
```
Agent 1 Agent 1 — Monitoring shared/utils/monitoring.py config.py, logger.py (Wk1)
```
```
Agent 2 Agent 2 — Error Handlers shared/utils/error_handlers.py config.py, logger.py (Wk1)
```
```
Agent 3 Agent 3 — Cache shared/utils/cache.py config.py, logger.py (Wk1)
```
Agent 4 Agent 4 — DB Schema database/schema.sql None — fully independent
```
Day 2: Agents 1-3 independent of each other. Agent 4 needs schema (Day 1)
```
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Storage shared/utils/storage.py config.py, logger.py
```
(Wk1)
```
Agent 2 Agent 2 — Message
Queue
shared/utils/message_queue.py config.py, logger.py
```
(Wk1)
```
Agent 3 Agent 3 —
Compliance Helpers
```
shared/utils/compliance_helpers.py compliance.py (Wk1)
```
Agent 4 Agent 4 — DB
Migration 001
```
database/migrations/versions/001_initial_schema.py schema.sql (Day 1)
```
```
Day 3: Agents 1-3 independent of each other. Agent 4 needs migration 001 (Day 2)
```
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — DB
Engine
```
backend/app/database.py config.py (Wk1)
```
Agent 2 Agent 2 —
Migration 002
database/migrations/versions/002_agent_lightning.py 001_initial_schema.py
```
(Day 2)
```
Agent 3 Agent 3 —
Migration 003
database/migrations/versions/003_audit_trail.py 001_initial_schema.py
```
(Day 2)
```
Agent 4 Agent 4 —
Migration 004
database/migrations/versions/004_compliance.py 001_initial_schema.py
```
(Day 2)
```
Day 4: All agents independent of each other — seed data and config files
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 —
Migration 005
database/migrations/versions/005_feature_flags.py 001_initial_schema.py
```
(Day 2)
```
Agent 2 Agent 2 — DB
Seeds
```
database/seeds/clients.sql + users.sql schema.sql (Day 1)
```
Agent 3 Agent 3 — Sample
Tickets
```
database/seeds/sample_tickets.sql schema.sql (Day 1)
```
Agent 4 Agent 4 —
Alembic Config
```
database/migrations/env.py database.py (Day 3)
```
Day 5: All agents independent — CI/CD workflows have no cross-dependencies
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — CI Workflow .github/workflows/ci.yml None — fully independent
Agent 2 Agent 2 — Deploy Workflow .github/workflows/deploy-
backend.yml + deploy-
frontend.yml
None — fully independent
Agent 3 Agent 3 — Dockerfiles infra/docker/backend.Dockerfile
- worker.Dockerfile +
mcp.Dockerfile
None — fully independent
Agent 4 Agent 4 — Setup Scripts infra/scripts/setup.sh +
seed_db.py + reset_dev.sh
```
schema.sql, seeds (Days 1-
```
```
2)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test for all Week 2 files. Verify: database.py connects to PostgreSQL using config → all 5 migrations
run in sequence without errors → seed data loads correctly → cache.py connects to Redis → monitoring.py
exports Prometheus metrics → all utils import without conflicts. Run: pytest
tests/integration/test_week2_database.py. Run migrations: alembic upgrade head. Expected: all 5 tables created,
seed data present, no connection errors.
Week Complete When All Pass:
1 alembic upgrade head: all 5 migrations complete without errors
2 database/seeds load without FK violations
3 database.py connects to PostgreSQL and Redis without errors
4 All shared utils import cleanly with no circular dependencies
5 docker-compose up: all 4 containers healthy
6 Day 6 integration: full DB stack + utils layer works together
Week 3 — Foundation & Infrastructure
Goal for This Week
```
Build all backend models and schemas in parallel. Models are independent of each other (they all inherit from
```
```
Base but don't depend on each other). Schemas mirror models and are equally independent.
```
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: All 4 model agents fully independent — models don't depend on each other
Day 1 Agent File to Build Depends On
```
Agent 1 Agent 1 — User Model backend/models/user.py + company.py database.py (Wk2)
```
Agent 2 Agent 2 — License Model backend/models/license.py +
subscription.py
```
database.py (Wk2)
```
Agent 3 Agent 3 — Ticket Model backend/models/support_ticket.py +
audit_trail.py
```
database.py (Wk2)
```
Agent 4 Agent 4 — Compliance
Model
backend/models/compliance_request.py
- sla_breach.py + usage_log.py
```
database.py (Wk2)
```
Day 2: Schemas mirror models — all 4 agents fully independent of each other
Day 2 Agent File to Build Depends On
```
Agent 1 Agent 1 — User Schema backend/schemas/user.py user.py model (Day 1)
```
Agent 2 Agent 2 — License Schema backend/schemas/license.py +
subscription.py
```
license.py model (Day 1)
```
```
Agent 3 Agent 3 — Support Schema backend/schemas/support.py support_ticket.py model (Day
```
```
1)
```
Agent 4 Agent 4 — Compliance
Schema
backend/schemas/compliance.py compliance_request.py
```
model (Day 1)
```
Day 3: Training data model independent. RLS policies and security files independent
Day 3 Agent File to Build Depends On
```
Agent 1 Agent 1 — Training Model backend/models/training_data.py database.py (Wk2)
```
```
Agent 2 Agent 2 — RLS Policies security/rls_policies.sql schema.sql (Wk2)
```
```
Agent 3 Agent 3 — HMAC Verification security/hmac_verification.py config.py (Wk1)
```
```
Agent 4 Agent 4 — KYC/AML security/kyc_aml.py config.py, logger.py (Wk1)
```
Day 4: Rate limiter and feature flags security independent. App core files independent
Day 4 Agent File to Build Depends On
```
Agent 1 Agent 1 — Rate Limiter security/rate_limiter.py config.py, cache.py (Wks 1-
```
```
2)
```
Agent 2 Agent 2 — Feature Flags
Security
```
security/feature_flags.py config.py, cache.py (Wks 1-
```
```
2)
```
```
Agent 3 Agent 3 — FastAPI App backend/app/main.py database.py (Wk2)
```
Agent 4 Agent 4 — App Config/Deps backend/app/config.py +
dependencies.py + middleware.py
```
config.py (Wk1),
```
```
rate_limiter.py (Day 1)
```
Day 5: All agents independent — unit tests for all model and schema files
Day 5 Agent File to Build Depends On
```
Agent 1 Agent 1 — Model Tests tests/unit/test_models.py All models (Days 1-3)
```
```
Agent 2 Agent 2 — Schema Tests tests/unit/test_schemas.py All schemas (Day 2)
```
```
Agent 3 Agent 3 — Security Tests tests/unit/test_security.py security/ files (Days 3-4)
```
Agent 4 Agent 4 — Conftest tests/conftest.py All models, database.py
```
(Days 1-2)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
```
Integration test for Week 3. Verify: all models create tables correctly → RLS policies apply correctly (cross-tenant
```
```
query returns 0 rows) → HMAC verification rejects forged webhooks → rate limiter blocks at correct thresholds →
```
FastAPI app starts with all models loaded → all schemas validate correctly against test data. Run: pytest
tests/integration/test_week3_models_security.py. Critical test: client_A JWT cannot query client_B data.
Week Complete When All Pass:
1 All SQLAlchemy models create tables without errors
2 RLS cross-tenant test: client_A JWT returns 0 rows of client_B data
3 HMAC: forged signature returns 401
4 Rate limiter: 101st request returns 429
5 FastAPI app starts and /health returns 200
6 Day 6 integration: full security layer works with models
7 v6.0 - RLS test suite: run pytest tests/security/rls/ — 30+ isolation tests on THIS commit
```
8 v6.0 - Demo system Day 1: build backend/services/demo_service.py (rate limiting + model routing)
```
```
9 v6.0 - Demo system Day 2: build frontend/components/DemoChatWidget.tsx (FREE chat, 20-msg limit)
```
```
10 v6.0 - Demo system Day 3: build frontend/pages/demo.tsx (full demo landing page)
```
```
11 v6.0 - Demo system Day 4: build frontend/components/VoiceDemoPaywall.tsx (Stripe $1 gate)
```
```
12 v6.0 - Demo system Day 5: build backend/api/demo.py (POST /demo/chat, /demo/voice endpoints)
```
Week 4 — Foundation & Infrastructure
Goal for This Week
Build all backend API routes and services in parallel. Auth, support, billing, and Jarvis API routes are fully
independent of each other. Services are equally independent.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: All 4 auth-layer agents fully independent of each other
Day 1 Agent File to Build Depends On
```
Agent 1 Agent 1 — Auth API backend/api/auth.py user model, security.py (Wks
```
```
1-3)
```
```
Agent 2 Agent 2 — License API backend/api/licenses.py license model (Wk3)
```
Agent 3 Agent 3 — Auth Core backend/core/auth.py +
security.py
```
security.py, config.py (Wks 1-
```
```
3)
```
```
Agent 4 Agent 4 — License Manager backend/core/license_manager.py license model (Wk3)
```
Day 2: All 4 API route agents independent of each other
Day 2 Agent File to Build Depends On
```
Agent 1 Agent 1 — Support API backend/api/support.py support_ticket model (Wk3)
```
```
Agent 2 Agent 2 — Dashboard API backend/api/dashboard.py all models (Wk3)
```
```
Agent 3 Agent 3 — Billing API backend/api/billing.py subscription model (Wk3)
```
```
Agent 4 Agent 4 — Compliance API backend/api/compliance.py compliance model (Wk3)
```
Day 3: All 4 service agents independent of each other
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Support Service backend/services/support_service.py support_ticket model
```
(Wk3)
```
Agent 2 Agent 2 — Analytics
Service
```
backend/services/analytics_service.py all models (Wk3)
```
```
Agent 3 Agent 3 — Billing Service backend/services/billing_service.py subscription model (Wk3)
```
Agent 4 Agent 4 — Onboarding
Service
```
backend/services/onboarding_service.py all models (Wk3)
```
Day 4: Remaining APIs and services — all independent of each other
Day 4 Agent File to Build Depends On
```
Agent 1 Agent 1 — Jarvis API backend/api/jarvis.py config.py, cache.py (Wks
```
```
1-2)
```
```
Agent 2 Agent 2 — Analytics API backend/api/analytics.py analytics_service.py (Day
```
```
3)
```
Agent 3 Agent 3 — Integrations
API
```
backend/api/integrations.py config.py (Wk1)
```
Agent 4 Agent 4 — Notification
Service
```
backend/services/notification_service.py config.py (Wk1)
```
Day 5: Webhook handlers and remaining services — all independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Shopify
Webhook
backend/api/webhooks/shopify.py hmac_verification.py
```
(Wk3)
```
```
Agent 2 Agent 2 — Stripe Webhook backend/api/webhooks/stripe.py hmac_verification.py(Wk3)
```
Agent 3 Agent 3 — Compliance
Service
```
backend/services/compliance_service.py compliance model (Wk3)
```
Agent 4 Agent 4 —
SLA/License/User Services
backend/services/sla_service.py +
license_service.py + user_service.py
```
all models (Wk3)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test for Week 4 — full API layer. Run: pytest tests/integration/test_week4_backend_api.py. Test:
POST /register → POST /login → GET /dashboard → POST /tickets → POST /approvals. Critical: approval
endpoint must create pending_approval record and NOT call Stripe. Verify all webhooks reject bad HMAC. Verify
Jarvis command sets Redis key within 500ms.
Week Complete When All Pass:
1 Full auth flow: register → login → JWT → protected route works
2 Refund approval gate: Stripe NOT called without explicit approval
3 Shopify/Stripe webhooks: bad HMAC returns 401
4 Jarvis command: Redis key set within 500ms
5 All API routes return correct status codes
6 Day 6 integration: complete backend API functional end-to-end
Phase 2 — Core AI Engine
Build the AI brain: GSD State Engine, Smart Router, Knowledge Base, and TRIVYA techniques. Each day's files share zero
dependencies on each other.
Week 5 — Core AI Engine
Goal for This Week
Build the GSD State Engine and Smart Router in parallel. GSD files are independent of each other
```
(state_schema first, then the rest). Smart Router files are independent of GSD files — different agents build them
```
simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: State schema and tier config are independent foundations — build simultaneously
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — State
Schema
```
shared/gsd_engine/state_schema.py config.py (Wk1)
```
```
Agent 2 Agent 2 — Tier Config shared/smart_router/tier_config.py config.py (Wk1)
```
Agent 3 Agent 3 — Failover
Config
shared/smart_router/failover.py config.py, logger.py
```
(Wk1)
```
Agent 4 Agent 4 — ADR Doc docs/architecture_decisions/003_openrouter.md
```
(update)
```
None — fully
independent
Day 2: GSD engine and complexity scorer independent — build simultaneously
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — GSD State
Engine
```
shared/gsd_engine/state_engine.py state_schema.py (Day 1)
```
Agent 2 Agent 2 — Complexity
Scorer
```
shared/smart_router/complexity_scorer.py tier_config.py (Day 1)
```
Agent 3 Agent 3 — Context
Health
```
shared/gsd_engine/context_health.py state_schema.py (Day 1)
```
Agent 4 Agent 4 — Smart Router shared/smart_router/router.py tier_config.py,
complexity_scorer.py
```
(Days 1-2)
```
Day 3: Compression independent of router. All agents build in parallel
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — GSD
Compression
shared/gsd_engine/compression.py state_engine.py,
```
state_schema.py (Days 1-
```
```
2)
```
```
Agent 2 Agent 2 — GSD Unit Tests tests/unit/test_gsd_engine.py All GSD files (Days 1-2)
```
```
Agent 3 Agent 3 — Router Unit Tests tests/unit/test_smart_router.py All router files (Days 1-2)
```
Agent 4 Agent 4 — Pricing Unit
Tests
```
tests/unit/test_pricing_optimizer.py pricing_optimizer.py (Wk1)
```
Day 4: Knowledge base foundation — all independent of each other
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Vector Store shared/knowledge_base/vector_store.py config.py, database.py
```
(Wks 1-2)
```
```
Agent 2 Agent 2 — KB Manager shared/knowledge_base/kb_manager.py config.py (Wk1)
```
```
Agent 3 Agent 3 — HyDE shared/knowledge_base/hyde.py config.py (Wk1)
```
```
Agent 4 Agent 4 — Multi Query shared/knowledge_base/multi_query.py config.py (Wk1)
```
```
Day 5: RAG pipeline needs vector store (Day 4). MCP client files independent
```
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — RAG Pipeline shared/knowledge_base/rag_pipeline.py vector_store.py, hyde.py,
```
multi_query.py (Day 4)
```
```
Agent 2 Agent 2 — MCP Client shared/mcp_client/client.py config.py (Wk1)
```
```
Agent 3 Agent 3 — MCP Auth shared/mcp_client/auth.py config.py, security.py (Wks
```
```
1-3)
```
```
Agent 4 Agent 4 — MCP Registry shared/mcp_client/registry.py config.py (Wk1)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test: GSD + Smart Router + KB together. Verify: 20-message conversation compresses to <200
```
tokens → FAQ query scores 0-2 (routes to Light tier) → refund query scores 9+ (routes to Heavy tier) → KB
```
ingest + retrieve round trip works → MCP client initialises. Run: pytest tests/integration/test_week5_gsd_kb.py.
Token reduction must be >85% for simple queries.
Week Complete When All Pass:
1 GSD: 20-message conversation compresses to under 200 tokens
2 Smart Router: FAQ routes to Light, refund routes to Heavy
3 Failover: simulated rate limit triggers secondary model switch
4 KB: document ingest and retrieve round trip works
5 MCP client: initialises and connects to registry
6 Day 6 integration: GSD + Router + KB work as unified AI pipeline
7 ADDED Wk4 Day5 — backend/api/webhook_malformation_handler.py: handles half-corrupt Shopify/Stripe/Twilio
webhooks — saves valid fields, flags missing, triggers async re-sync. Depends on webhooks/shopify.py,
```
webhooks/stripe.py (same day Wk4).
```
Week 6 — Core AI Engine
Goal for This Week
```
Build TRIVYA Tier 1 and Tier 2 techniques in parallel. Tier 1 techniques (CLARA, CRP, GSD integration) are all
```
independent of each other. Tier 2 techniques are all independent of each other and of Tier 1.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: All Tier 1 and Tier 2 orchestrator files independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — TRIVYA
Orchestrator
shared/trivya_techniques/orchestrator.py config.py, router.py
```
(Wks 1-5)
```
Agent 2 Agent 2 — Trigger
Detector T2
```
shared/trivya_techniques/tier2/trigger_detector.py config.py (Wk1)
```
Agent 3 Agent 3 — CLARA shared/trivya_techniques/tier1/clara.py rag_pipeline.py,
```
hyde.py (Wk5)
```
```
Agent 4 Agent 4 — CRP shared/trivya_techniques/tier1/crp.py gsd_engine (Wk5)
```
Day 2: GSD integration for Tier 1. Tier 2 techniques all independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — GSD
Integration T1
shared/trivya_techniques/tier1/gsd_integration.py state_engine.py
```
(Wk5)
```
Agent 2 Agent 2 — Chain of
Thought
```
shared/trivya_techniques/tier2/chain_of_thought.py config.py (Wk1)
```
```
Agent 3 Agent 3 — ReAct shared/trivya_techniques/tier2/react.py config.py (Wk1)
```
Agent 4 Agent 4 — Reverse
Thinking
```
shared/trivya_techniques/tier2/reverse_thinking.py config.py (Wk1)
```
Day 3: All Tier 2 techniques independent of each other
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Step
Back
```
shared/trivya_techniques/tier2/step_back.py config.py (Wk1)
```
Agent 2 Agent 2 — Thread
of Thought
```
shared/trivya_techniques/tier2/thread_of_thought.py gsd_engine (Wk5)
```
Agent 3 Agent 3 —
Confidence Scorer
```
shared/confidence/scorer.py config.py (Wk1)
```
Agent 4 Agent 4 —
Confidence
Thresholds
```
shared/confidence/thresholds.py config.py (Wk1)
```
Day 4: Sentiment analyzer and routing rules independent of each other
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Sentiment
Analyzer
```
shared/sentiment/analyzer.py router.py (Wk5)
```
Agent 2 Agent 2 — Sentiment
Routing
```
shared/sentiment/routing_rules.py thresholds.py (Day 3)
```
Agent 3 Agent 3 — Confidence Tests tests/unit/test_confidence_scorer.py scorer.py, thresholds.py
```
(Day 3)
```
Agent 4 Agent 4 — Compliance
Tests
```
tests/unit/test_compliance.py compliance.py (Wk1)
```
Day 5: Tier 2 tests and audit trail tests — all independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — TRIVYA T1+T2
Tests
```
tests/unit/test_trivya_tier1_tier2.py All Tier 1+2 files (Days 1-
```
```
4)
```
```
Agent 2 Agent 2 — Audit Trail Tests tests/unit/test_audit_trail.py audit_trail.py (Wk1)
```
```
Agent 3 Agent 3 — Sentiment Tests tests/unit/test_sentiment.py analyzer.py (Day 4)
```
```
Agent 4 Agent 4 — KB Tests tests/unit/test_knowledge_base.py rag_pipeline.py (Wk5)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test: full TRIVYA Tier 1 + Tier 2 pipeline. Send a test query through orchestrator → verify Tier 1
always fires → verify Tier 2 fires only when trigger_detector detects complexity → verify confidence score outputs
```
correct threshold (GRADUATE/BATCH/ASK/ESCALATE). Run: pytest tests/integration/test_week6_trivya.py. All
```
4 Tier 2 techniques must produce meaningfully different outputs.
Week Complete When All Pass:
1 TRIVYA orchestrator: Tier 1 fires on every query
2 Tier 2 trigger: only activates on decision_needed or multi_step queries
3 Confidence scorer: 95%+ returns GRADUATE, <70% returns ESCALATE
4 Sentiment: high anger score routes to PARWA High pathway
5 All 5 Tier 2 techniques produce output without errors
6 Day 6 integration: complete TRIVYA Tier 1+2 pipeline functional
7 ADDED Wk6 Day4 — shared/knowledge_base/cold_start.py: bootstraps new client Day 1 with industry-template
```
FAQs, seeds first KB entries, pre-loads GSD state schema. Depends on kb_manager.py (Wk5), embedder.py
```
```
(Wk5).
```
Week 7 — Core AI Engine
Goal for This Week
Build TRIVYA Tier 3 and all integration API clients in parallel. Tier 3 techniques are fully independent of each
```
other. Integration clients (Shopify, Stripe, Twilio etc.) are fully independent of each other and of Tier 3.
```
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Tier 3 trigger detector and techniques all independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 —
Trigger
Detector T3
shared/trivya_techniques/tier3/trigger_detector.py confidence/scorer.py
```
(Wk6)
```
```
Agent 2 Agent 2 — GST shared/trivya_techniques/tier3/gst.py config.py (Wk1)
```
Agent 3 Agent 3 —
Universe of
Thoughts
```
shared/trivya_techniques/tier3/universe_of_thoughts.py config.py (Wk1)
```
Agent 4 Agent 4 — Tree
of Thoughts
```
shared/trivya_techniques/tier3/tree_of_thoughts.py config.py (Wk1)
```
Day 2: Remaining Tier 3 techniques independent. Integration clients independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Self
Consistency
```
shared/trivya_techniques/tier3/self_consistency.py config.py (Wk1)
```
```
Agent 2 Agent 2 — Reflexion shared/trivya_techniques/tier3/reflexion.py config.py (Wk1)
```
Agent 3 Agent 3 — Least to
Most
```
shared/trivya_techniques/tier3/least_to_most.py config.py (Wk1)
```
Agent 4 Agent 4 — Shopify
Client
shared/integrations/shopify_client.py config.py, logger.py
```
(Wk1)
```
Day 3: All integration clients independent of each other
Day 3 Agent File to Build Depends On
```
Agent 1 Agent 1 — Stripe Client shared/integrations/stripe_client.py config.py, logger.py (Wk1)
```
```
Agent 2 Agent 2 — Twilio Client shared/integrations/twilio_client.py config.py, logger.py (Wk1)
```
```
Agent 3 Agent 3 — Email Client shared/integrations/email_client.py config.py, logger.py (Wk1)
```
```
Agent 4 Agent 4 — Zendesk Client shared/integrations/zendesk_client.py config.py, logger.py (Wk1)
```
Day 4: Industry-specific clients all independent of each other
Day 4 Agent File to Build Depends On
```
Agent 1 Agent 1 — GitHub Client shared/integrations/github_client.py config.py (Wk1)
```
```
Agent 2 Agent 2 — AfterShip Client shared/integrations/aftership_client.py config.py (Wk1)
```
```
Agent 3 Agent 3 — Epic EHR Client shared/integrations/epic_ehr_client.py config.py (Wk1)
```
Agent 4 Agent 4 — Compliance
Layer
shared/compliance/jurisdiction.py +
sla_calculator.py
```
config.py (Wk1)
```
Day 5: GDPR engine and healthcare guard independent. Tier 3 tests independent
Day 5 Agent File to Build Depends On
```
Agent 1 Agent 1 — GDPR Engine shared/compliance/gdpr_engine.py compliance.py (Wk1)
```
Agent 2 Agent 2 — Healthcare
Guard
```
shared/compliance/healthcare_guard.py compliance.py (Wk1)
```
```
Agent 3 Agent 3 — Tier 3 Tests tests/unit/test_trivya_tier3.py All Tier 3 files (Days 1-3)
```
Agent 4 Agent 4 — Integration
Client Tests
```
tests/unit/test_integration_clients.py All clients (Days 2-4)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test: full TRIVYA pipeline Tier 1+2+3. Send a VIP + high-value + angry customer scenario → verify
Tier 3 triggers → verify all 3 tiers produce combined output → verify integration clients connect without errors.
```
Run: pytest tests/integration/test_week7_trivya_complete.py. Tier 3 must only activate on VIP / amount>$100 /
```
anger>80% scenarios.
Week Complete When All Pass:
1 Full TRIVYA pipeline: Tier 1+2+3 all fire correctly on correct triggers
2 Tier 3 does NOT activate on simple FAQ queries
3 Tier 3 DOES activate on VIP + high-value scenario
```
4 All integration clients initialise without credentials errors (mocked)
```
5 GDPR engine: export and soft-delete both work correctly
6 Day 6 integration: complete TRIVYA framework functional end-to-end
Week 8 — Core AI Engine
Goal for This Week
Build all MCP servers in parallel. Knowledge MCP servers, integration MCP servers, and tool MCP servers are all
fully independent of each other. All can be built simultaneously across 4 agents.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Base server and knowledge MCP servers independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Base MCP Server mcp_servers/base_server.py +
config.py
```
config.py, security.py (Wks
```
```
1-3)
```
```
Agent 2 Agent 2 — FAQ Server mcp_servers/knowledge/faq_server.py base_server.py (Day 1 —
```
```
wait for Agent 1)
```
Agent 3 Agent 3 — RAG Server mcp_servers/knowledge/rag_server.py base_server.py,
```
rag_pipeline.py (Wks 5,
```
```
Day 1)
```
Agent 4 Agent 4 — KB Server mcp_servers/knowledge/kb_server.py base_server.py,
```
kb_manager.py (Wks 5,
```
```
Day 1)
```
Day 2: Integration MCP servers all independent of each other
Day 2 Agent File to Build Depends On
```
Agent 1 Agent 1 — Email MCP mcp_servers/integrations/email_server.py base_server.py (Day 1
```
```
Wk8), email_client.py
```
```
(Wk7)
```
```
Agent 2 Agent 2 — Voice MCP mcp_servers/integrations/voice_server.py base_server.py (Day 1
```
```
Wk8), twilio_client.py
```
```
(Wk7)
```
```
Agent 3 Agent 3 — Chat MCP mcp_servers/integrations/chat_server.py base_server.py (Day 1
```
```
Wk8)
```
Agent 4 Agent 4 — Ticketing
MCP
```
mcp_servers/integrations/ticketing_server.py base_server.py (Day 1
```
```
Wk8)
```
Day 3: E-commerce and CRM MCP servers independent of each other
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Ecommerce
MCP
```
mcp_servers/integrations/ecommerce_server.py base_server.py (Day 1
```
```
Wk8), shopify_client.py
```
```
(Wk7)
```
```
Agent 2 Agent 2 — CRM MCP mcp_servers/integrations/crm_server.py base_server.py (Day 1
```
```
Wk8)
```
Agent 3 Agent 3 — Analytics
Tool MCP
```
mcp_servers/tools/analytics_server.py base_server.py (Day 1
```
```
Wk8)
```
Agent 4 Agent 4 — Monitoring
Tool MCP
```
mcp_servers/tools/monitoring_server.py base_server.py (Day 1
```
```
Wk8)
```
Day 4: Remaining tool MCP servers all independent of each other
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Notification
MCP
mcp_servers/tools/notification_server.py base_server.py,
notification_service.py
```
(Wks 4-8)
```
Agent 2 Agent 2 — Compliance
MCP
mcp_servers/tools/compliance_server.py base_server.py,
```
gdpr_engine.py (Wks 7-8)
```
```
Agent 3 Agent 3 — SLA Tool MCP mcp_servers/tools/sla_server.py base_server.py (Day 1
```
```
Wk8)
```
```
Agent 4 Agent 4 — MCP Tests tests/unit/test_mcp_servers.py All MCP servers (Days 1-3)
```
Day 5: Integration tests for MCP and full AI pipeline tests
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — MCP
Integration Test
tests/integration/test_week3_workflows.py
```
(MCP round-trip)
```
```
All MCP servers (Days 1-4)
```
Agent 2 Agent 2 — Full AI
Pipeline Test
tests/integration/test_week2_gsd_kb.py
```
(update)
```
GSD+KB+TRIVYA+MCP
all complete
Agent 3 Agent 3 — Compliance
Tests
```
tests/unit/test_compliance.py (update) gdpr_engine.py,
```
```
healthcare_guard.py (Wk7)
```
Agent 4 Agent 4 — Monitoring
Setup
monitoring/prometheus.yml None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test: MCP full round-trip. All MCP servers start → MCP client connects to each server → send test
tool call to each server → verify response. Run: pytest tests/integration/test_week8_mcp.py. Every MCP server
must respond to a test tool call within 2 seconds. The full chain GSD → TRIVYA → MCP server → integration
client must complete without errors.
Week Complete When All Pass:
1 All 11 MCP servers start without errors
2 MCP client connects to all servers via registry
3 Each MCP server responds to test tool call within 2 seconds
4 Full chain: GSD → TRIVYA → MCP → integration client completes
5 prometheus.yml scrapes all services
6 Day 6 integration: complete AI engine with MCP layer functional
7 ADDED Wk8 Day4 — shared/guardrails/guardrails.py: scans every AI response for hallucinations, competitor
```
mentions, data leaks. Depends on smart_router.py (Wk7), trivya_techniques/ (Wk6).
```
```
8 ADDED Wk8 Day5 — shared/guardrails/approval_enforcer.py: detects irreversible actions (refunds, account
```
```
changes), forces approval workflow even if AI tries to bypass. Hard-coded, cannot be overridden. Depends on
```
```
guardrails.py (Day4).
```
Phase 3 — Variants & Integrations
Build all three sellable variants: Mini, PARWA, and PARWA High. Agents build variant files in parallel — base agents first,
then each variant independently.
Week 9 — Variants & Integrations
Goal for This Week
```
Build all base agents in parallel. Each base agent (FAQ, email, chat, SMS, voice, ticket, escalation, refund) is
```
fully independent. Multiple agents build different base agent files simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
```
Day 1: Base agent abstract class first. Then 2 base agents in parallel (no cross-dependency)
```
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Base Agent variants/base_agents/base_agent.py confidence/scorer.py,
```
security.py (Wks 3-6)
```
Agent 2 Agent 2 — Base FAQ
Agent
```
variants/base_agents/base_faq_agent.py base_agent.py (Day 1 —
```
```
wait)
```
Agent 3 Agent 3 — Base Email
Agent
```
variants/base_agents/base_email_agent.py base_agent.py (Day 1 —
```
```
wait)
```
Agent 4 Agent 4 — Base Chat
Agent
```
variants/base_agents/base_chat_agent.py base_agent.py (Day 1 —
```
```
wait)
```
Day 2: Remaining base agents — all independent of each other
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Base SMS
Agent
```
variants/base_agents/base_sms_agent.py base_agent.py (Day 1)
```
Agent 2 Agent 2 — Base Voice
Agent
```
variants/base_agents/base_voice_agent.py base_agent.py (Day 1)
```
Agent 3 Agent 3 — Base Ticket
Agent
```
variants/base_agents/base_ticket_agent.py base_agent.py (Day 1)
```
Agent 4 Agent 4 — Base
Escalation Agent
```
variants/base_agents/base_escalation_agent.py base_agent.py (Day 1)
```
Day 3: Base refund agent independent. Mini config and anti-arbitrage independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Base Refund
Agent
variants/base_agents/base_refund_agent.py base_agent.py, approval
```
gates (Days 1-2)
```
```
Agent 2 Agent 2 — Mini Config variants/mini/config.py config.py (Wk1)
```
Agent 3 Agent 3 — Mini Anti-
Arbitrage
variants/mini/anti_arbitrage_config.py pricing_optimizer.py
```
(Wk1)
```
Agent 4 Agent 4 — Base Agent
Tests
```
tests/unit/test_base_agents.py All base agents (Days 1-2)
```
Day 4: Mini agents all independent of each other — build all 8 in parallel
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Mini
FAQ+Email Agents
variants/mini/agents/faq_agent.py +
email_agent.py
base_faq_agent.py,
```
base_email_agent.py (Days
```
```
1-2)
```
Agent 2 Agent 2 — Mini
Chat+SMS Agents
variants/mini/agents/chat_agent.py +
sms_agent.py
base_chat_agent.py,
```
base_sms_agent.py (Days
```
```
1-2)
```
Agent 3 Agent 3 — Mini
Voice+Ticket Agents
variants/mini/agents/voice_agent.py +
ticket_agent.py
base_voice_agent.py,
```
base_ticket_agent.py (Days
```
```
1-2)
```
Agent 4 Agent 4 — Mini
Escalation+Refund
Agents
variants/mini/agents/escalation_agent.py
- refund_agent.py
base_escalation_agent.py,
base_refund_agent.py
```
(Days 2-3)
```
Day 5: Mini tools and workflows — all independent of each other
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Mini Tools variants/mini/tools/faq_search.py +
order_lookup.py + ticket_create.py
```
shopify_client.py (Wk7)
```
Agent 2 Agent 2 — Mini Tools 2 variants/mini/tools/notification.py +
refund_verification_tools.py
twilio_client.py,
```
stripe_client.py (Wk7)
```
Agent 3 Agent 3 — Mini Workflows
1
variants/mini/workflows/inquiry.py +
ticket_creation.py + escalation.py
```
All mini agents (Day 4)
```
Agent 4 Agent 4 — Mini Workflows
2
variants/mini/workflows/order_status.py
- refund_verification.py
```
All mini agents (Day 4)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test: Mini PARWA complete variant. Spin up Mini with test Shopify credentials → send FAQ query →
verify Light tier used → send refund request → verify pending_approval created and Stripe NOT called → send
escalation trigger → verify human handoff. Run: pytest tests/integration/test_week9_mini_variant.py. Refund gate
is the critical test.
Week Complete When All Pass:
1 Mini PARWA: FAQ query routes to Light tier
2 Mini PARWA: refund request creates pending_approval, Stripe NOT called
3 Mini PARWA: escalation triggers human handoff correctly
4 All 8 base agents initialise without errors
5 Mini anti-arbitrage: 2x Mini cost shows manager time correctly
6 Day 6 integration: complete Mini PARWA variant functional
Week 10 — Variants & Integrations
Goal for This Week
Build Mini PARWA tasks, then PARWA Junior variant files. Mini tasks are independent. PARWA Junior agents
mirror Mini but with additions — all PARWA agents independent of each other.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Mini tasks all independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Mini Tasks 1 variants/mini/tasks/answer_faq.py +
process_email.py
```
Mini agents (Wk9)
```
Agent 2 Agent 2 — Mini Tasks 2 variants/mini/tasks/handle_chat.py +
make_call.py
```
Mini agents (Wk9)
```
Agent 3 Agent 3 — Mini Tasks 3 variants/mini/tasks/create_ticket.py
- escalate.py
```
Mini agents (Wk9)
```
```
Agent 4 Agent 4 — Mini Tasks 4 variants/mini/tasks/verify_refund.py Mini agents (Wk9)
```
Day 2: PARWA config independent. PARWA agents mirror Mini — all independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — PARWA Config variants/parwa/config.py +
anti_arbitrage_config.py
```
config.py (Wk1)
```
Agent 2 Agent 2 — PARWA Core
Agents
variants/parwa/agents/faq_agent.py +
email_agent.py + chat_agent.py
```
base agents (Wk9)
```
Agent 3 Agent 3 — PARWA
Communication Agents
variants/parwa/agents/sms_agent.py +
voice_agent.py
```
base agents (Wk9)
```
Agent 4 Agent 4 — PARWA Ticket
Agents
variants/parwa/agents/ticket_agent.py
- escalation_agent.py +
refund_agent.py
```
base agents (Wk9)
```
```
Day 3: PARWA unique agents (learning + safety) independent. PARWA tools independent
```
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — PARWA
Learning Agent
variants/parwa/agents/learning_agent.py base_agent.py,
```
training_data model (Wks
```
```
3-9)
```
Agent 2 Agent 2 — PARWA Safety
Agent
variants/parwa/agents/safety_agent.py ai_safety.py,
```
base_agent.py (Wks 1-9)
```
Agent 3 Agent 3 — PARWA Tools variants/parwa/tools/knowledge_update.py
- refund_recommendation_tools.py
```
kb_manager.py (Wk5)
```
Agent 4 Agent 4 — PARWA Tools
2
variants/parwa/tools/safety_tools.py +
```
(all mini tools inherited)
```
```
ai_safety.py (Wk1)
```
Day 4: PARWA workflows and tasks all independent of each other
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — PARWA
Workflows
variants/parwa/workflows/refund_recommendation.py
- knowledge_update.py
PARWA agents
```
(Days 2-3)
```
Agent 2 Agent 2 — PARWA
Workflows 2
variants/parwa/workflows/safety_workflow.py +
```
(inherited mini workflows)
```
PARWA agents
```
(Days 2-3)
```
Agent 3 Agent 3 — PARWA
Tasks
variants/parwa/tasks/recommend_refund.py +
update_knowledge.py
PARWA agents
```
(Days 2-3)
```
Agent 4 Agent 4 — PARWA
Tasks 2
variants/parwa/tasks/compliance_check.py +
```
(inherited mini tasks)
```
```
compliance.py (Wk1)
```
Day 5: All unit tests for this week — independent of each other
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Mini Tasks
Tests
```
tests/unit/test_mini_tasks.py All mini tasks (Day 1)
```
Agent 2 Agent 2 — PARWA
Agent Tests
```
tests/unit/test_parwa_agents.py All PARWA agents (Days
```
```
2-3)
```
Agent 3 Agent 3 — PARWA
Workflow Tests
```
tests/unit/test_parwa_workflows.py PARWA workflows (Day
```
```
4)
```
Agent 4 Agent 4 — Manager
Time Tests
backend/services/manager_time_calculator.py
- tests
pricing_optimizer.py
```
(Wk1)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test: PARWA Junior vs Mini comparison. Same refund scenario through both variants → verify
```
PARWA makes recommendation (Mini does not) → verify PARWA learning_agent records training data → verify
```
PARWA safety_agent blocks competitor mentions. Run: pytest tests/integration/test_week5_parwa_variant.py.
```
Key: PARWA recommendation must include APPROVE/REVIEW/DENY with reasoning.
```
Week Complete When All Pass:
1 PARWA recommendation: includes APPROVE/REVIEW/DENY with full reasoning
2 PARWA learning agent: negative_reward record created on rejection
3 PARWA safety agent: competitor mention blocked
```
4 Mini still works correctly alongside PARWA (no conflicts)
```
5 Manager time calculator: correct formula output
6 Day 6 integration: PARWA Junior variant fully functional
Week 11 — Variants & Integrations
Goal for This Week
Build PARWA High variant in parallel. All PARWA High agents are independent of each other. PARWA High tools
and workflows are independent. Build all simultaneously across multiple agents.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: PARWA High config independent. Advanced agents all independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — High
Config
variants/parwa_high/config.py +
anti_arbitrage_config.py
```
config.py (Wk1)
```
Agent 2 Agent 2 — High Video
Agent
```
variants/parwa_high/agents/video_agent.py base_agent.py (Wk9)
```
Agent 3 Agent 3 — High
Analytics Agent
```
variants/parwa_high/agents/analytics_agent.py base_agent.py (Wk9)
```
Agent 4 Agent 4 — High
Coordination Agent
```
variants/parwa_high/agents/coordination_agent.py base_agent.py (Wk9)
```
Day 2: Remaining High agents all independent of each other
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — High
Customer Success
Agent
```
variants/parwa_high/agents/customer_success_agent.py base_agent.py (Wk9)
```
Agent 2 Agent 2 — High
SLA Agent
variants/parwa_high/agents/sla_agent.py base_agent.py,
sla_calculator.py
```
(Wks 7-9)
```
Agent 3 Agent 3 — High
Compliance Agent
variants/parwa_high/agents/compliance_agent.py base_agent.py,
healthcare_guard.py
```
(Wks 7-9)
```
Agent 4 Agent 4 — High
Learning+Safety
Agents
variants/parwa_high/agents/learning_agent.py +
safety_agent.py
```
base_agent.py (Wk9)
```
Day 3: High tools and workflows all independent of each other
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — High
Tools
variants/parwa_high/tools/analytics_engine.py +
team_coordination.py
analytics_service.py
```
(Wk4)
```
Agent 2 Agent 2 — High
Tools 2
```
variants/parwa_high/tools/customer_success_tools.py base_agent.py (Wk9)
```
Agent 3 Agent 3 — High
Workflows
variants/parwa_high/workflows/video_support.py +
analytics.py
```
High agents (Days 1-2)
```
Agent 4 Agent 4 — High
Workflows 2
variants/parwa_high/workflows/coordination.py +
customer_success.py
```
High agents (Days 1-2)
```
Day 4: High tasks independent of each other
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — High
Tasks 1
variants/parwa_high/tasks/video_call.py +
generate_insights.py
```
High agents (Days 1-2)
```
Agent 2 Agent 2 — High
Tasks 2
variants/parwa_high/tasks/coordinate_teams.py +
customer_success.py
```
High agents (Days 1-2)
```
Agent 3 Agent 3 — High
Agent Tests
```
tests/unit/test_parwa_high_agents.py All High agents (Days 1-
```
```
2)
```
Agent 4 Agent 4 —
Migration 006
database/migrations/versions/006_multi_region.py 001_initial_schema.py
```
(Wk2)
```
Day 5: All 3 variants coexistence test. Integration test files independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — All 3 Variants
Test
tests/integration/test_week6_parwa_high.py All 3 variants complete
```
(Wks 9-11)
```
Agent 2 Agent 2 — Full System
Test
tests/integration/test_full_system.py
```
(skeleton)
```
```
All variants (Wks 9-11)
```
Agent 3 Agent 3 — BDD Tests tests/bdd/test_mini_scenarios.py +
test_parwa_scenarios.py +
test_parwa_high_scenarios.py
```
All 3 variants (Wks 9-
```
```
11)
```
Agent 4 Agent 4 — High
Workflow Tests
```
tests/unit/test_parwa_high_workflows.py High workflows (Days
```
```
3-4)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test: all 3 variants running simultaneously. Import all 3 variants → verify no module conflicts → send
```
same ticket through all 3 → verify different capability levels (Mini collects, PARWA recommends, High executes
```
```
on approval) → verify PARWA High churn prediction works → verify video agent initialises. Run: pytest
```
tests/integration/test_week6_parwa_high.py.
Week Complete When All Pass:
1 All 3 variants import simultaneously with zero conflicts
2 PARWA High: churn prediction output contains risk score
3 PARWA High: video agent initialises correctly
4 Same ticket through all 3: correctly different outputs per variant capability
5 BDD scenarios: all pass for all 3 variants
6 Day 6 integration: all 3 variants coexist and function correctly
Week 12 — Variants & Integrations
Goal for This Week
Build all backend services for ticket management, approvals, and the 4-phase escalation system. All services are
independent — build in parallel. Add industry-specific configurations simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Industry configs and Jarvis command handlers all independent
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Jarvis
Commands
backend/core/jarvis_commands.py cache.py, security.py
```
(Wks 1-3)
```
Agent 2 Agent 2 — Ecommerce
Config
```
backend/core/industry_configs/ecommerce.py config.py (Wk1)
```
```
Agent 3 Agent 3 — SaaS Config backend/core/industry_configs/saas.py config.py (Wk1)
```
Agent 4 Agent 4 — Healthcare
Config
backend/core/industry_configs/healthcare.py
- logistics.py
config.py,
healthcare_guard.py
```
(Wks 1-7)
```
Day 2: Approval service independent of escalation service
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Approval
Service
backend/services/approval_service.py support_ticket model,
```
stripe_client.py (Wks 3-7)
```
Agent 2 Agent 2 — Escalation
Service
backend/services/escalation_service.py support_ticket model
```
(Wk3)
```
```
Agent 3 Agent 3 — License Service backend/services/license_service.py license model (Wk3)
```
Agent 4 Agent 4 — SLA Service backend/services/sla_service.py
```
(complete)
```
```
sla_breach model (Wk3)
```
Day 3: Webhook handlers update independent of each other
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Twilio
Webhook
backend/api/webhooks/twilio.py hmac_verification.py
```
(Wk3)
```
Agent 2 Agent 2 —
Automation API
```
backend/api/automation.py all agents (Wks 9-11)
```
Agent 3 Agent 3 —
Manager Time
Calculator
backend/services/manager_time_calculator.py
```
(complete)
```
pricing_optimizer.py
```
(Wk1)
```
Agent 4 Agent 4 — ADR
Industry
docs/architecture_decisions/004_ecommerce_config.md
- 005_multi_region.md
None — fully
independent
Day 4: E2E test files all independent of each other
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — E2E
Onboarding Test
```
tests/e2e/test_onboarding_flow.py All backend services (Wks
```
```
4-12)
```
Agent 2 Agent 2 — E2E Refund
Test
```
tests/e2e/test_refund_workflow.py approval_service.py (Day
```
```
2)
```
Agent 3 Agent 3 — E2E Jarvis
Test
```
tests/e2e/test_jarvis_commands.py jarvis_commands.py (Day
```
```
1)
```
Agent 4 Agent 4 — E2E Stuck
Ticket Test
tests/e2e/test_stuck_ticket_escalation.py escalation_service.py
```
(Day 2)
```
Day 5: Agent Lightning E2E tests and business logic tests independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — E2E Agent
Lightning Test
tests/e2e/test_agent_lightning.py training_data model
```
(Wk3)
```
Agent 2 Agent 2 — E2E GDPR
Test
```
tests/e2e/test_gdpr_compliance.py gdpr_engine.py (Wk7)
```
Agent 3 Agent 3 — Business
Logic Tests
tests/business_logic/refund_edge_cases.md +
vip_handling_cases.md
None — fully
independent
Agent 4 Agent 4 —
Compliance
Verification
tests/business_logic/compliance_verification.md None — fully
independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test: full approval workflow end-to-end. POST a refund ticket → verify pending_approval created →
POST /approvals/:id/approve → verify Stripe called EXACTLY once → verify audit_trail entry with correct hash →
verify training_data positive_reward created. Run: pytest tests/e2e/test_refund_workflow.py. Also test 4-phase
stuck ticket escalation at 24h/48h/72h thresholds.
Week Complete When All Pass:
1 Refund E2E: Stripe called exactly once — after approval, never before
2 Audit trail: hash chain validates after approval event
3 Stuck ticket: 4-phase escalation fires at exact hour thresholds
4 MISSING FILE FIXED: backend/services/escalation_ladder.py — build Day 2 Wk12 alongside approval_service.py:
zombie ticket handler, 0-24h soft reminder, 24-48h backup admin alert, 48-72h forced auto-reject. Depends on
```
approval_service.py (same day — careful ordering).
```
5 Jarvis: pause_refunds Redis key set within 500ms
6 ADDED Wk12 Day3 — backend/services/non_financial_undo.py: Jarvis recall protocol — Redis publish stops non-
```
money actions (emails, tags, notes, address changes) instantly. Before/after state logged in audit trail. Depends on
```
```
audit_logger.py (Wk2), Redis (Wk1).
```
7 GDPR: export contains complete data, deletion anonymises PII
8 Day 6 integration: complete approval and escalation system functional
9 ADDED Wk12 Day4 — backend/nlp/command_parser.py: parses Jarvis natural language into structured
```
commands (action+count+variant+duration). e.g. Add 2 Mini Agents for the weekend → {action:provision, count:2,
```
```
type:mini, duration:weekend}.
```
10 ADDED Wk12 Day5 — backend/nlp/provisioner.py + intent_classifier.py: executes parsed Jarvis Create commands
```
— spins up agents, updates billing, starts workers. Depends on command_parser.py (Day4).
```
```
11 v6.0 - Incoming call system Day 1: build backend/api/incoming_calls.py (voice-first, <2 rings)
```
```
12 v6.0 - Incoming call system Day 2: build backend/services/voice_handler.py (5-step call flow)
```
```
13 v6.0 - Incoming call Day 3: write tests/voice/ suite (answer <6s, never IVR, recording test)
```
```
14 v6.0 - Demo DB: run database/migrations/demo_tables.py (demo_sessions, demo_payments tables)
```
Week 13 — Variants & Integrations
Goal for This Week
Build Agent Lightning — the self-improvement training system. Data pipeline files are independent of training
pipeline files. All can be built in parallel.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Data export files all independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Export
Mistakes
agent_lightning/data/export_mistakes.py training_data model
```
(Wk3)
```
Agent 2 Agent 2 — Export
Approvals
agent_lightning/data/export_approvals.py training_data model
```
(Wk3)
```
Agent 3 Agent 3 — Dataset
Builder
agent_lightning/data/dataset_builder.py export_mistakes.py,
export_approvals.py
```
(Day 1 — wait)
```
Agent 4 Agent 4 — Model
Registry
```
agent_lightning/deployment/model_registry.py config.py (Wk1)
```
Day 2: Training files independent of deployment files
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Trainer agent_lightning/training/trainer.py [v6.0:
uses Unsloth+Colab FREE, was RunPod $50/mo]
```
config.py (Wk1)
```
Agent 2 Agent 2 — Unsloth
Optimizer
```
agent_lightning/training/unsloth_optimizer.py trainer.py (Day 2 —
```
```
wait)
```
Agent 3 Agent 3 — Deploy
Model
```
agent_lightning/deployment/deploy_model.py model_registry.py (Day
```
```
1)
```
```
Agent 4 Agent 4 — Rollback agent_lightning/deployment/rollback.py model_registry.py (Day
```
```
1)
```
Day 3: Fine tune entry point and monitoring files all independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Fine Tune agent_lightning/training/fine_tune.py trainer.py,
unsloth_optimizer.py
```
(Day 2)
```
```
Agent 2 Agent 2 — Validate agent_lightning/training/validate.py trainer.py (Day 2)
```
Agent 3 Agent 3 — Drift
Detector
```
agent_lightning/monitoring/drift_detector.py model_registry.py (Day
```
```
1)
```
Agent 4 Agent 4 — Accuracy
Tracker
```
agent_lightning/monitoring/accuracy_tracker.py model_registry.py (Day
```
```
1)
```
Day 4: Workers are all independent of each other
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Worker Entry workers/worker.py config.py,
```
message_queue.py (Wks 1-
```
```
2)
```
Agent 2 Agent 2 — Batch Approval
Worker
```
workers/batch_approval.py escalation_service.py (Wk12)
```
```
Agent 3 Agent 3 — Training Job Worker workers/training_job.py fine_tune.py (Day 3)
```
```
Agent 4 Agent 4 — Cleanup Worker workers/cleanup.py gdpr_engine.py (Wk7)
```
Day 5: Remaining workers all independent. Agent Lightning tests independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Recall Handler
Worker
```
workers/recall_handler.py cache.py (Wk2)
```
Agent 2 Agent 2 — Proactive Outreach
Worker
```
workers/proactive_outreach.py notification_service.py (Wk4)
```
Agent 3 Agent 3 — Report Generator
Worker
```
workers/report_generator.py analytics_service.py (Wk4)
```
```
Agent 4 Agent 4 — KB Indexer Worker workers/kb_indexer.py rag_pipeline.py (Wk5)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test: full Agent Lightning training cycle. Seed 100 negative_reward records → trigger training_job
worker → verify JSONL dataset exported → run validate.py with mock 89% accuracy → verify deployment
BLOCKED → set mock to 91% → verify deployment proceeds → verify new model version in model_registry.
```
Run: pytest tests/e2e/test_agent_lightning.py.
```
Week Complete When All Pass:
1 Dataset builder exports correct JSONL format
2 Validate.py blocks deployment at <90% accuracy
3 Validate.py allows deployment at 91%+ accuracy
4 New model version registered in model_registry after deployment
5 All 8 workers start and register with ARQ without errors
6 ADDED Wk13 Day5 — backend/services/burst_mode.py: handles Burst Mode toggle — adds temporary agents at
```
+$400 prorated, activates instantly, auto-expires at end of selected period. Depends on billing_service.py (Wk4),
```
```
feature_flags/ (Wk1).
```
7 Day 6 integration: complete Agent Lightning cycle works end-to-end
```
8 v6.0 - Quality Coach Day 1: build backend/quality_coach/analyzer.py (score accuracy/empathy/efficiency per
```
```
conversation)
```
```
9 v6.0 - Quality Coach Day 2: build backend/quality_coach/reporter.py (weekly reports + training priority list)
```
```
10 v6.0 - Quality Coach Day 3: build backend/quality_coach/notifier.py (real-time alerts to managers)
```
```
11 v6.0 - Quality Coach Day 4: build frontend/components/QualityDashboard.tsx (score cards, trend charts)
```
```
12 v6.0 - Quality Coach Day 5: build frontend/components/QualityAlerts.tsx (alert cards, escalate, snooze)
```
13 v6.0 - Quality Coach Day 6: build workers/quality_coach_worker.py + backend/api/quality.py endpoints
```
14 v6.0 - Quality Coach DB: run database/migrations/quality_coach.py (quality_scores + quality_alerts +
```
```
training_suggestions)
```
15 v6.0 - Quality Coach monitoring: add monitoring/dashboards/quality.json Grafana board
Week 14 — Variants & Integrations
Goal for This Week
Build all monitoring, Grafana dashboards, and alerts in parallel. All 5 dashboards are independent. All 6 alert
rules are independent. Build simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: All 4 Grafana dashboards independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Main Dashboard monitoring/grafana-
dashboards/main-dashboard.json
None — fully independent
Agent 2 Agent 2 — MCP Dashboard monitoring/grafana-
dashboards/mcp-dashboard.json
None — fully independent
Agent 3 Agent 3 — Compliance
Dashboard
monitoring/grafana-
dashboards/compliance-
dashboard.json
None — fully independent
Agent 4 Agent 4 — SLA Dashboard monitoring/grafana-
dashboards/sla-dashboard.json
None — fully independent
Day 2: Alert rules all independent of each other
Day 2 Agent File to Build Depends On
```
Agent 1 Agent 1 — Alert Rules monitoring/alerts.yml (all 6
```
```
alert rules)
```
```
prometheus.yml (Wk8)
```
Agent 2 Agent 2 — Grafana Config monitoring/grafana-config.yml None — fully independent
Agent 3 Agent 3 — Log Config monitoring/logs/structured-
logging-config.yml
```
logger.py (Wk1)
```
Agent 4 Agent 4 — Runbook docs/runbook.md None — fully independent
Day 3: Performance tests and load tests independent of each other
Day 3 Agent File to Build Depends On
```
Agent 1 Agent 1 — Load Test tests/performance/test_load.py All backend APIs (Wks
```
```
4-12)
```
Agent 2 Agent 2 — UI Tests tests/ui/test_approval_queue.py +
test_roi_calculator.py +
test_jarvis_terminal.py
None — fully
independent
Agent 3 Agent 3 — BDD Test
Runner
```
tests/bdd/test_mini_scenarios.py (complete) Mini variant (Wk9)
```
Agent 4 Agent 4 — Integration
Test Update
tests/integration/test_week4_backend_api.py
```
(complete)
```
```
All APIs (Wks 4-12)
```
Day 4: Industry-specific test files all independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Ecommerce
Tests
tests/integration/test_ecommerce_industry.py ecommerce config
```
(Wk12)
```
```
Agent 2 Agent 2 — SaaS Tests tests/integration/test_saas_industry.py saas config (Wk12)
```
Agent 3 Agent 3 — Healthcare
Tests
tests/integration/test_healthcare_industry.py healthcare config
```
(Wk12)
```
Agent 4 Agent 4 — Logistics
Tests
```
tests/integration/test_logistics_industry.py logistics config (Wk12)
```
Day 5: Final integration test files and Dockerfiles — all independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Full System Test tests/integration/test_full_system.py
```
(complete)
```
```
Everything complete (Wks
```
```
1-13)
```
Agent 2 Agent 2 — Frontend
Dockerfile
infra/docker/frontend.Dockerfile None — fully independent
Agent 3 Agent 3 — Docker
Compose Prod
```
docker-compose.prod.yml (update) All Dockerfiles (Days 1-4)
```
```
Agent 4 Agent 4 — Project State PROJECT_STATE.md (Phase 1-3 complete
```
```
marker)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test: full system Phases 1-3. Run: pytest tests/integration/test_full_system.py. All 3 variants +
complete backend + all workers + monitoring must work together. Performance test: P95 latency <500ms at 50
concurrent users. All 6 Grafana alerts must fire correctly on simulated conditions. This is the Phase 3 completion
gate.
Week Complete When All Pass:
1 pytest tests/integration/test_full_system.py: all tests pass
```
2 P95 latency <500ms at 50 concurrent users (Locust)
```
3 All 6 monitoring alerts fire correctly on simulated conditions
4 All 4 industry configurations work without errors
5 docker-compose.prod.yml starts all services healthy
6 Day 6 integration: Phase 1-3 complete system validation passed
7 backend/safety/guardrails.py — hallucinatation blocked, competitor mention blocked, PII blocked
8 backend/safety/response_validator.py — pre-send confidence check rejects below threshold
Phase 4 — Backend API Complete
Build the complete backend API: all endpoints, services, webhooks, and security. API routes, services, and webhooks are
independent and built in parallel.
Week 15 — Backend API Complete
Goal for This Week
Build all frontend foundation files in parallel. Next.js config, layout, and landing page components are all
independent. Auth pages are independent of each other. Build simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: All frontend config files independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Next.js Config frontend/package.json +
next.config.js + tailwind.config.js
None — fully independent
Agent 2 Agent 2 — Root Layout frontend/src/app/layout.tsx None — fully independent
Agent 3 Agent 3 — Landing Page frontend/src/app/page.tsx None — fully independent
Agent 4 Agent 4 — Common UI frontend/src/components/ui/Button.tsx
- Input.tsx + Badge.tsx + Card.tsx
None — fully independent
Day 2: Common UI components all independent of each other
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Modal+Toast frontend/src/components/ui/Modal.tsx +
Toast.tsx + Table.tsx
None — fully
independent
Agent 2 Agent 2 — Common
Components
frontend/src/components/common/Header.tsx
- Footer.tsx + Loading.tsx +
ErrorBoundary.tsx
```
Button.tsx (Day 1)
```
```
Agent 3 Agent 3 — Auth Pages frontend/src/app/(auth)/login/page.tsx +
```
register/page.tsx
None — fully
independent
Agent 4 Agent 4 — Forgot
Password
```
frontend/src/app/(auth)/forgot-
```
password/page.tsx
None — fully
independent
Day 3: Variant cards all independent of each other
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Mini Card frontend/src/components/variants/MiniParwaCard.tsx Card.tsx,
```
Badge.tsx (Day 1)
```
Agent 2 Agent 2 — PARWA
Card
frontend/src/components/variants/ParwaCard.tsx Card.tsx,
```
Badge.tsx (Day 1)
```
Agent 3 Agent 3 — High Card frontend/src/components/variants/ParwaHighCard.tsx Card.tsx,
```
Badge.tsx (Day 1)
```
Agent 4 Agent 4 — Smart
Bundle+Manager Time
frontend/src/components/variants/SmartBundle.tsx +
ManagerTime.tsx
```
Card.tsx (Day 1)
```
Day 4: Frontend stores and API service all independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Agent Store frontend/src/stores/agentStore.ts None — fully independent
Agent 2 Agent 2 — Ticket Store frontend/src/stores/ticketStore.ts None — fully independent
Agent 3 Agent 3 — UI Store frontend/src/stores/uiStore.ts None — fully independent
Agent 4 Agent 4 — API Service frontend/src/services/api.ts config.py backend URL
```
(Wk1)
```
Day 5: Onboarding components all independent of each other
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 —
Onboarding
Wizard
frontend/src/components/onboarding/OnboardingWizard.tsx All UI primitives
```
(Days 1-2)
```
Agent 2 Agent 2 —
Integration Setup
frontend/src/components/onboarding/IntegrationSetup.tsx All UI primitives
```
(Days 1-2)
```
Agent 3 Agent 3 — KB
Upload
frontend/src/components/onboarding/KBUpload.tsx All UI primitives
```
(Days 1-2)
```
Agent 4 Agent 4 —
Payment Setup
frontend/src/components/onboarding/PaymentSetup.tsx +
Success.tsx
All UI primitives
```
(Days 1-2)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test: frontend foundation. Run Next.js dev server → verify landing page loads → verify all 3 variant
cards render correctly → verify auth pages render → verify onboarding wizard 5-step flow renders without errors.
```
Run: npm run test (Jest). All UI components render with no console errors. Tailwind styles apply correctly.
```
Week Complete When All Pass:
1 Next.js dev server starts without errors
2 Landing page: all 3 variant cards render correctly
3 Auth pages: login and register forms render and validate
4 Onboarding wizard: all 5 steps render in sequence
5 All Zustand stores initialise without errors
6 Day 6 integration: complete frontend foundation functional
Week 16 — Backend API Complete
Goal for This Week
```
Build all dashboard pages and hooks in parallel. Dashboard pages (home, tickets, approvals, agents) are
```
independent. Hooks are independent of pages. All build simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Dashboard layout and home independent. Jarvis components independent
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Dashboard
Layout
```
frontend/src/app/dashboard/layout.tsx Header.tsx (Wk15)
```
Agent 2 Agent 2 — Dashboard
Home
frontend/src/app/dashboard/page.tsx dashboard layout
```
(Day 1 — wait)
```
Agent 3 Agent 3 — Jarvis
Terminal
frontend/src/components/jarvis/GSDTerminal.tsx
- ContextHealthMeter.tsx
```
UI primitives (Wk15)
```
Agent 4 Agent 4 — Jarvis
Chat+Status
frontend/src/components/jarvis/JarvisChat.tsx
- SystemStatus.tsx
```
UI primitives (Wk15)
```
Day 2: Dashboard pages all independent of each other
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Tickets
Page
frontend/src/app/dashboard/tickets/page.tsx dashboard layout
```
(Day 1)
```
Agent 2 Agent 2 — Approvals
Page
frontend/src/app/dashboard/approvals/page.tsx dashboard layout
```
(Day 1)
```
```
Agent 3 Agent 3 — Agents Page frontend/src/app/dashboard/agents/page.tsx dashboard layout(Day 1)
```
Agent 4 Agent 4 — Analytics
Page
frontend/src/app/dashboard/analytics/page.tsx dashboard layout
```
(Day 1)
```
Day 3: Dashboard components all independent of each other
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Activity
Feed
frontend/src/components/dashboard/ActivityFeed.tsx
- Metrics.tsx
UI primitives
```
(Wk15)
```
Agent 2 Agent 2 —
Victory+Usage
frontend/src/components/dashboard/Victory.tsx +
Usage.tsx
UI primitives
```
(Wk15)
```
Agent 3 Agent 3 — Approval
Components
frontend/src/components/approvals/ApprovalQueue.tsx
- RefundCard.tsx + ConfidenceScore.tsx
UI primitives
```
(Wk15)
```
Agent 4 Agent 4 —
Burst+Escalation
frontend/src/components/dashboard/Burst.tsx +
Escalation.tsx + Insights.tsx + SLA.tsx
UI primitives
```
(Wk15)
```
Day 4: All hooks independent of each other
Day 4 Agent File to Build Depends On
```
Agent 1 Agent 1 — Realtime Hook frontend/src/hooks/useRealtime.ts ticketStore.ts (Wk15)
```
```
Agent 2 Agent 2 — Jarvis Hook frontend/src/hooks/useJarvis.ts uiStore.ts (Wk15)
```
Agent 3 Agent 3 — Agent Status
Hook
```
frontend/src/hooks/useAgentStatus.ts agentStore.ts (Wk15)
```
Agent 4 Agent 4 —
Tickets+Approvals Hooks
frontend/src/hooks/useTickets.ts +
useApprovals.ts
```
ticketStore.ts (Wk15)
```
Day 5: Remaining pages all independent of each other
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Knowledge
Page
```
frontend/src/app/dashboard/knowledge/page.tsx dashboard layout (Day
```
```
1)
```
Agent 2 Agent 2 — Audit Log
Page
```
frontend/src/app/dashboard/audit-log/page.tsx dashboard layout (Day
```
```
1)
```
Agent 3 Agent 3 — Jarvis Page frontend/src/app/dashboard/jarvis/page.tsx Jarvis components
```
(Day 1)
```
Agent 4 Agent 4 — Settings
Pages
```
frontend/src/app/dashboard/settings/ (6 sub-
```
```
pages)
```
```
dashboard layout (Day
```
```
1)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test: complete dashboard. Start Next.js → login → navigate to dashboard → verify activity feed loads
with real API data → verify approvals queue renders → verify Jarvis terminal sends command and receives
response → verify all hooks update stores correctly. Run: npm run test. API calls must reach backend correctly.
Week Complete When All Pass:
1 Dashboard home: activity feed loads real ticket data from API
2 Approvals page: queue renders and approve action calls correct API
3 Jarvis: command sends to backend and response streams back
4 All 5 hooks update their respective stores without errors
5 All 6 settings pages render without errors
6 Day 6 integration: complete dashboard functional with live API data
7 backend/services/cold_start.py — new client Day 1: Synthetic Warm-Up runs 100 Q&A, KB score >0.80 returns
answer, <0.80 escalates honestly
Week 17 — Backend API Complete
Goal for This Week
Build onboarding flow, analytics, and all remaining frontend pages in parallel. All page groups are independent.
Multiple agents build different page groups simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Onboarding pages all independent of each other
Day 1 Agent File to Build Depends On
Agent
1
Agent 1 —
Onboarding
Page
frontend/src/app/onboarding/page.tsx OnboardingWizard
```
component (Wk15)
```
Agent
2
Agent 2 —
Pricing Page
frontend/src/app/pricing/page.tsx Variant cards
```
(Wk15)
```
Agent
3
Agent 3 —
Analytics
Components
frontend/src/components/dashboard/ROICalculator.tsx +
ConfidenceTrend.tsx
```
UI primitives (Wk15)
```
Agent
4
Agent 4 —
Integration
Settings
frontend/src/app/dashboard/settings/integrations/page.tsx dashboard layout
```
(Wk16)
```
Day 2: All settings sub-pages independent of each other
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Billing
Settings
frontend/src/app/dashboard/settings/billing/page.tsx dashboard
```
layout (Wk16)
```
Agent 2 Agent 2 — Team
Settings
frontend/src/app/dashboard/settings/team/page.tsx dashboard
```
layout (Wk16)
```
Agent 3 Agent 3 —
Policies Settings
frontend/src/app/dashboard/settings/policies/page.tsx dashboard
```
layout (Wk16)
```
Agent 4 Agent 4 —
Compliance
Settings
frontend/src/app/dashboard/settings/compliance/page.tsx dashboard
```
layout (Wk16)
```
Day 3: Frontend test files all independent of each other
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Login+Register
Tests
```
tests/ui/test_auth_pages.tsx Auth pages (Wk15)
```
```
Agent 2 Agent 2 — Dashboard Tests tests/ui/test_dashboard.tsx Dashboard pages (Wk16)
```
```
Agent 3 Agent 3 — Onboarding Tests tests/ui/test_onboarding.tsx Onboarding (Day 1)
```
```
Agent 4 Agent 4 — Variant Cards Tests tests/ui/test_variant_cards.tsx Variant cards (Wk15)
```
Day 4: Final frontend integration wiring — connect frontend to all backend APIs
Day 4 Agent File to Build Depends On
```
Agent 1 Agent 1 — Auth Service frontend/src/services/authService.ts api.ts (Wk15), auth API
```
```
(Wk4)
```
```
Agent 2 Agent 2 — Ticket Service frontend/src/services/ticketService.ts api.ts (Wk15), support
```
```
API (Wk4)
```
Agent 3 Agent 3 — Analytics
Service
```
frontend/src/services/analyticsService.ts api.ts (Wk15), analytics
```
```
API (Wk4)
```
Agent 4 Agent 4 — Billing Service
Frontend
```
frontend/src/services/billingService.ts api.ts (Wk15), billing API
```
```
(Wk4)
```
Day 5: E2E frontend tests independent of each other
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Full Frontend
E2E
```
tests/e2e/test_frontend_full_flow.py All frontend pages (Wks
```
```
15-17)
```
Agent 2 Agent 2 — Lighthouse
Config
tests/performance/lighthouse.config.js None — fully independent
Agent 3 Agent 3 — Frontend Build
Test
```
.github/workflows/ci.yml (update for
```
```
frontend build)
```
None — fully independent
Agent 4 Agent 4 — Storybook
Config
```
frontend/.storybook/main.js (optional
```
```
component docs)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Integration test: complete frontend to backend. Run full login → onboarding → dashboard → approve refund →
check analytics cycle entirely through the UI. Run: pytest tests/e2e/test_frontend_full_flow.py. Lighthouse score
must be >80. All frontend service calls must reach backend and return real data.
Week Complete When All Pass:
1 Full UI flow: login → onboarding → dashboard works end-to-end
2 Approve refund through UI: Stripe called exactly once
3 Analytics page: real data loads from backend
4 Lighthouse score >80 on all pages
5 All frontend services connect to correct backend endpoints
6 Day 6 integration: complete full-stack frontend-to-backend functional
7 backend/services/escalation.py — stuck ticket at 24h triggers reminder email, 48h notifies backup admin, 72h auto-
```
resolves (approve if confidence>95% else reject)
```
8 backend/services/webhook_malformation_handler.py — malformed Shopify webhook caught, schema validated,
retry attempted, dead-letter queue populated on 3rd failure
9 backend/services/undo_manager.py — address change undone correctly, before/after state logged in audit trail
Week 18 — Backend API Complete
Goal for This Week
Final testing, bug fixes, production hardening, and deployment preparation. Tests run in parallel. Docker
production builds are independent. Final integration verification.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Full test suite runs — all test categories independent
Day 1 Agent File to Build Depends On
```
Agent 1 Agent 1 — Unit Test Suite pytest tests/unit/ (full run,
```
```
fix any failures)
```
```
All unit test files (Wks 1-17)
```
Agent 2 Agent 2 — Integration Test
Suite
```
pytest tests/integration/ (full
```
```
run)
```
```
All integration files (Wks 1-
```
```
17)
```
```
Agent 3 Agent 3 — E2E Test Suite pytest tests/e2e/ (full run) All e2e files (Wks 12-17)
```
```
Agent 4 Agent 4 — BDD Test Suite pytest tests/bdd/ (full run) All bdd files (Wks 9-14)
```
Day 2: Security and performance tests independent of each other
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — OWASP Security
Scan
Run OWASP ZAP + fix all
findings
```
Full backend (Wks 1-17)
```
Agent 2 Agent 2 — Snyk CVE Scan snyk test all Docker images +
fix critical CVEs
```
All Dockerfiles (Wks 2-17)
```
Agent 3 Agent 3 — Load Test locust -f
tests/performance/test_load.py
```
(100 users)
```
```
Full backend (Wks 1-17)
```
Agent 4 Agent 4 — RLS Penetration
Test
10 cross-tenant isolation tests security/rls_policies.sql
```
(Wk3)
```
Day 3: Production Docker builds and cloud prep all independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Backend Prod Build docker build backend.Dockerfile
— verify <500MB
```
backend/ (Wks 1-17)
```
Agent 2 Agent 2 — Frontend Prod Build docker build
frontend.Dockerfile — verify
<500MB
```
frontend/ (Wks 15-17)
```
```
Agent 3 Agent 3 — Worker Prod Build docker build worker.Dockerfile workers/ (Wk13)
```
```
Agent 4 Agent 4 — MCP Prod Build docker build mcp.Dockerfile mcp_servers/ (Wk8)
```
Day 4: Kubernetes manifests all independent of each other
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — K8s Backend infra/kubernetes/backend-
deployment.yaml + backend-
service.yaml
None — fully independent
Agent 2 Agent 2 — K8s Frontend infra/kubernetes/frontend-
deployment.yaml + frontend-
service.yaml
None — fully independent
Agent 3 Agent 3 — K8s Worker+MCP infra/kubernetes/worker-
deployment.yaml + mcp-
deployment.yaml
None — fully independent
Agent 4 Agent 4 — K8s
HPA+Namespace
infra/kubernetes/namespace.yaml
- autoscaling/hpa.yaml
None — fully independent
Day 5: Final docs and deployment prep — all independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Deployment Docs docs/deployment/production-
deployment-guide.md
None — fully independent
```
Agent 2 Agent 2 — API Docs docs/api/openapi.json (auto-
```
```
generate from FastAPI)
```
```
All API routes (Wks 4-12)
```
```
Agent 3 Agent 3 — Final README README.md (complete) None — fully independent
```
Agent 4 Agent 4 —
PROJECT_STATE.md
```
PROJECT_STATE.md (Phases 1-4
```
```
complete)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
FINAL PRODUCTION READINESS TEST for Weeks 1-40. Run pytest tests/ — target 100% pass. Verify: zero
critical CVEs, OWASP clean, RLS cross-tenant isolation confirmed, P95 <500ms at 100 concurrent users, all 3
variants functional, all workers running, monitoring alerts firing, full client journey works. This is the go/no-go gate
for first client.
Week Complete When All Pass:
1 pytest tests/: 100% pass rate
2 Zero critical CVEs on all Docker images
3 OWASP: all 10 checks pass
4 RLS: 10 cross-tenant isolation tests all return 0 rows
5 P95 latency <500ms at 100 concurrent users
6 Full client journey: signup → onboarding → ticket → approval works
7 backend/agents/workflow_parser.py — Jarvis natural language parsed into structured JSON steps, confirmation
loop fires
8 backend/services/burst_mode.py — >90% capacity for 3 days triggers temp agent spawn, billing meter updated
correctly
Phase 5 — Agent Lightning
Build Agent Lightning: the self-improvement system that makes AI smarter every Saturday. Data pipeline and training
pipeline files are independent of each other.
Week 19 — Agent Lightning
Goal for This Week
First client onboarding and real-world validation. Fix any issues found with real client data. Performance
monitoring and optimization.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Client setup files all independent
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Client Config First client industry config +
feature flags
```
industry configs (Wk12)
```
Agent 2 Agent 2 — KB Ingestion Ingest first client's knowledge
base documents
```
rag_pipeline.py (Wk5)
```
Agent 3 Agent 3 — Monitoring Config monitoring/dashboards/client-
specific-dashboard.json
None — fully independent
Agent 4 Agent 4 — SLA Config First client SLA targets and
alert thresholds
```
sla_service.py (Wk12)
```
Day 2: Shadow mode validation files independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Shadow
Mode Test
```
tests/integration/test_shadow_mode.py All agents (Wks 9-11)
```
Agent 2 Agent 2 — Accuracy
Baseline
agent_lightning/monitoring/accuracy_tracker.py
```
(baseline run)
```
accuracy_tracker.py
```
(Wk13)
```
Agent 3 Agent 3 —
Performance
Baseline
```
tests/performance/baseline_metrics.py monitoring (Wk14)
```
Agent 4 Agent 4 — Error Log
Review
monitoring/logs/error-patterns.md None — fully
independent
Day 3: Bug fixes from real usage — independent per component area
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Backend Fixes Fix any API issues found in
Days 1-2
Based on Day 1-2 findings
Agent 2 Agent 2 — Frontend Fixes Fix any UI issues found in Days
1-2
Based on Day 1-2 findings
Agent 3 Agent 3 — Agent Fixes Fix any agent behaviour issues
in Days 1-2
Based on Day 1-2 findings
Agent 4 Agent 4 — KB Fixes Fix any KB retrieval quality
issues
Based on Day 1-2 findings
Day 4: Optimisation files independent of each other
Day 4 Agent File to Build Depends On
```
Agent 1 Agent 1 — Cache Optimisation shared/utils/cache.py (tune
```
```
TTLs)
```
```
cache.py (Wk2)
```
```
Agent 2 Agent 2 — Query Optimisation database/ (add indexes for slow
```
```
queries)
```
```
schema.sql (Wk2)
```
Agent 3 Agent 3 — Token Optimisation shared/gsd_engine/compression.py
```
(tune thresholds)
```
```
compression.py (Wk5)
```
```
Agent 4 Agent 4 — Alert Tuning monitoring/alerts.yml (tune
```
```
thresholds from real data)
```
```
alerts.yml (Wk14)
```
Day 5: Week 1 client report and documentation — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Client Report docs/client-reports/week1-
report.md
None — fully independent
Agent 2 Agent 2 — Accuracy Report agent_lightning/monitoring/week1-
accuracy.md
```
accuracy_tracker.py (Wk13)
```
Agent 3 Agent 3 — Performance
Report
tests/performance/week1-
results.md
```
load test (Wk18)
```
```
Agent 4 Agent 4 — Runbook Update docs/runbook.md (update with real
```
```
issues found)
```
```
runbook.md (Wk14)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Week 19 integration test: real client data validation. Run 50 real tickets through the system in Shadow Mode.
```
Measure: accuracy rate, response time, confidence scores, false positive/negative rates. All metrics must match
```
or exceed baseline targets. No critical errors in 50-ticket run.
Week Complete When All Pass:
1 50 tickets processed in Shadow Mode without critical errors
```
2 Accuracy baseline established (target >72% approval rate Week 1)
```
3 P95 response time <500ms on real client data
4 No cross-tenant data leaks in real usage
5 Week 1 client report generated and accurate
6 Day 6: real client data validation passed
Week 20 — Agent Lightning
Goal for This Week
Second client onboarding and scaling test. Verify multi-client isolation with 2 real clients. Agent Lightning first
training run.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Second client setup — independent files per client
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Client 2
Config
Second client industry config + feature flags industry configs
```
(Wk12)
```
Agent 2 Agent 2 — Client 2
KB
```
Ingest second client knowledge base rag_pipeline.py (Wk5)
```
Agent 3 Agent 3 — Multi-
Client Test
```
tests/integration/test_multi_client_isolation.py All models, RLS (Wks
```
```
1-18)
```
Agent 4 Agent 4 — Client 2
Dashboard
monitoring/dashboards/client2-dashboard.json None — fully
independent
Day 2: Agent Lightning first run — data + training independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Export
Training Data
Run
agent_lightning/data/dataset_builder.py on
Client 1 data
dataset_builder.py
```
(Wk13)
```
Agent 2 Agent 2 — Run Fine
Tune
Run agent_lightning/training/fine_tune.py
```
(first real run)
```
```
fine_tune.py (Wk13)
```
Agent 3 Agent 3 — Validate
Model
```
Run agent_lightning/training/validate.py validate.py (Wk13)
```
Agent 4 Agent 4 — Deploy
Model
Run
agent_lightning/deployment/deploy_model.py
```
deploy_model.py (Wk13)
```
Day 3: Post-training validation — independent tests
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Accuracy After
Training
Compare accuracy before vs
after Agent Lightning
```
accuracy_tracker.py (Wk13)
```
Agent 2 Agent 2 — Drift Detection Run drift_detector.py on new
model
```
drift_detector.py (Wk13)
```
```
Agent 3 Agent 3 — Regression Test pytest tests/ (verify new model
```
```
didn't break anything)
```
```
All tests (Wks 1-19)
```
Agent 4 Agent 4 — Client 1+2 Isolation Run 20 cross-tenant isolation
tests with 2 real clients
```
rls_policies.sql (Wk3)
```
Day 4: Scaling tests and optimisation — independent
Day 4 Agent File to Build Depends On
```
Agent 1 Agent 1 — 2-Client Load Test locust (2 clients, 100 total
```
```
concurrent users)
```
```
test_load.py (Wk14)
```
Agent 2 Agent 2 — DB Connection Test Verify connection pool handles
2-client load
```
database.py (Wk2)
```
Agent 3 Agent 3 — Redis Memory Test Verify Redis memory usage with
2 clients
```
cache.py (Wk2)
```
Agent 4 Agent 4 — Worker Queue Test Verify ARQ workers handle 2-
client job volume
```
worker.py (Wk13)
```
Day 5: Weeks 19-20 consolidation — reports and docs independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Agent Lightning
Report
docs/agent-lightning/first-
training-results.md
None — fully independent
Agent 2 Agent 2 — Multi-Client Report docs/client-reports/multi-
client-validation.md
None — fully independent
Agent 3 Agent 3 — Scaling Report tests/performance/2-client-
scaling-results.md
None — fully independent
Agent 4 Agent 4 — PROJECT_STATE
Update
```
PROJECT_STATE.md (Phase 5 Agent
```
```
Lightning complete)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Week 20 integration test: 2-client isolation + Agent Lightning validation. Test: Client 1 and Client 2 data is
```
completely isolated (20 cross-tenant tests). Agent Lightning improved accuracy by at least 3% from baseline. 2-
```
client load test: P95 <500ms. New model passes all regression tests.
Week Complete When All Pass:
1 2-client cross-tenant isolation: 0 data leaks in 20 tests
2 Agent Lightning: accuracy improved ≥3% from Week 19 baseline
3 New model passes all regression tests
4 2-client load test: P95 <500ms at 100 concurrent users
5 ARQ worker queue handles 2-client volume without backing up
6 Day 6: 2-client isolation + Agent Lightning first run validated
Phase 6 — Security & Monitoring
Build all background workers and the monitoring system. Workers are independent of each other and built in parallel.
Week 21 — Security & Monitoring
Goal for This Week
```
Weeks 21-30: Continued client growth (3-10 clients), weekly Agent Lightning runs, performance optimisation, and
```
industry expansion. Each week focuses on one area with files built in parallel.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Client 3-5 onboarding configs — all independent
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 Client 3 config + KB ingestion onboarding_service.py
```
(Wk4)
```
```
Agent 2 Agent 2 Client 4 config + KB ingestion onboarding_service.py(Wk4)
```
Agent 3 Agent 3 Client 5 config + KB ingestion onboarding_service.py
```
(Wk4)
```
```
Agent 4 Agent 4 tests/integration/test_5_client_isolation.py rls_policies.sql (Wk3)
```
Day 2: Agent Lightning Week 3 run — steps independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 Export + build dataset for all
5 clients
```
dataset_builder.py (Wk13)
```
Agent 2 Agent 2 Fine tune on combined 5-client
dataset
```
fine_tune.py (Wk13)
```
```
Agent 3 Agent 3 Validate + deploy new model validate.py (Wk13)
```
Agent 4 Agent 4 Drift detection + accuracy
comparison
```
drift_detector.py (Wk13)
```
```
Day 3: Collective intelligence (cross-client learning without sharing PII) — independent files
```
Day 3 Agent File to Build Depends On
```
Agent 1 Agent 1 shared/utils/collective_intelligence.py dataset_builder.py (Wk13)
```
Agent 2 Agent 2 Cross-client pattern detection
```
(anonymised)
```
```
compliance.py (Wk1)
```
```
Agent 3 Agent 3 Industry benchmark aggregation analytics_service.py (Wk4)
```
Agent 4 Agent 4 tests/unit/test_collective_intelligence.py collective_intelligence.py
```
(Day 3)
```
Day 4: Performance optimisation files independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 Tune Redis cache hit rate
```
(target >70%)
```
```
cache.py (Wk2)
```
```
Agent 2 Agent 2 DB query optimisation (add
```
```
composite indexes)
```
```
schema.sql (Wk2)
```
```
Agent 3 Agent 3 Token usage optimisation (Light
```
```
tier >88% of queries)
```
```
router.py (Wk5)
```
```
Agent 4 Agent 4 Worker throughput optimisation worker.py (Wk13)
```
Day 5: New industry vertical files independent
Day 5 Agent File to Build Depends On
```
Agent 1 Agent 1 backend/core/industry_configs/financial_services.py config.py (Wk1)
```
```
Agent 2 Agent 2 backend/core/industry_configs/real_estate.py config.py (Wk1)
```
Agent 3 Agent 3 tests/integration/test_financial_services.py financial_services
```
config (Day 5)
```
Agent 4 Agent 4 5-client accuracy + performance report None — fully
independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
```
Week 21 integration: 5-client system validation. 5-client isolation test (zero leaks). Agent Lightning accuracy at
```
77%+. Redis cache hit rate >70%. Light tier handling >88% of queries. All 5 clients processing tickets without
errors.
Week Complete When All Pass:
1 5-client isolation: 0 data leaks across 50 cross-tenant tests
```
2 Agent Lightning accuracy: ≥77% (Week 3 target)
```
3 Redis cache hit rate: >70%
4 Light tier: >88% of queries
5 New industry verticals: configs load without errors
6 Day 6: 5-client system validation passed
Week 22 — Security & Monitoring
Goal for This Week
Weeks 22-30: Scale to 10 clients, achieve 85% accuracy target, complete platform hardening.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Clients 6-10 onboarding — all independent per client
Day 1 Agent File to Build Depends On
```
Agent 1 Agent 1 Clients 6-7 config + KB onboarding_service.py(Wk4)
```
Agent 2 Agent 2 Clients 8-9 config + KB onboarding_service.py
```
(Wk4)
```
Agent 3 Agent 3 Client 10 config + KB onboarding_service.py
```
(Wk4)
```
```
Agent 4 Agent 4 tests/integration/test_10_client_isolation.py rls_policies.sql (Wk3)
```
Day 2: Agent Lightning Week 6 run — independent steps
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 Export 10-client combined
dataset
```
dataset_builder.py (Wk13)
```
Agent 2 Agent 2 Fine tune + validate fine_tune.py, validate.py
```
(Wk13)
```
```
Agent 3 Agent 3 Deploy + drift check deploy_model.py (Wk13)
```
```
Agent 4 Agent 4 85% accuracy verification run accuracy_tracker.py (Wk13)
```
Day 3: Platform hardening — security files independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 Full OWASP re-scan at 10-client
scale
```
Full backend (Wks 1-21)
```
Agent 2 Agent 2 Penetration test: 10-client RLS
```
isolation (100 tests)
```
```
rls_policies.sql (Wk3)
```
Agent 3 Agent 3 Rate limiting tuning for 10-
client load
```
rate_limiter.py (Wk3)
```
Agent 4 Agent 4 Security hardening doc update None — fully independent
Day 4: 10-client performance tests independent
Day 4 Agent File to Build Depends On
```
Agent 1 Agent 1 10-client load test (500
```
```
concurrent users)
```
```
test_load.py (Wk14)
```
Agent 2 Agent 2 DB connection pool validation
```
(10 clients)
```
```
database.py (Wk2)
```
```
Agent 3 Agent 3 Horizontal scaling test (add
```
```
2nd backend pod)
```
```
K8s config (Wk18)
```
```
Agent 4 Agent 4 Worker queue depth test (10-
```
```
client volume)
```
```
worker.py (Wk13)
```
Day 5: 10-client milestone report — independent docs
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 10-client milestone report None — fully independent
```
Agent 2 Agent 2 Agent Lightning 6-week results accuracy_tracker.py (Wk13)
```
Agent 3 Agent 3 Platform hardening
certification doc
None — fully independent
```
Agent 4 Agent 4 PROJECT_STATE.md (10-client
```
```
milestone)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
10-client milestone gate. 100 cross-tenant isolation tests: 0 leaks. Agent Lightning accuracy ≥85%. 500
concurrent users: P95 <500ms. All 10 clients processing tickets. Platform hardening report complete.
Week Complete When All Pass:
1 10-client isolation: 0 data leaks in 100 cross-tenant tests
```
2 Agent Lightning: ≥85% accuracy (Week 6 target)
```
3 500 concurrent users: P95 <500ms
4 Horizontal scaling: 2nd backend pod handles traffic correctly
5 10-client milestone report complete and accurate
6 Day 6: 10-client milestone gate passed
Phase 7 — Frontend Complete
Build the complete frontend: every page, component, and user flow. Pages and components within each day have no cross-
dependencies.
Week 23 — Frontend Complete
Goal for This Week
Frontend polish: accessibility, mobile-responsive fixes, dark mode, error states. All component updates are fully
independent of each other — 4 agents update different component groups simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: All 4 agents work on completely different component groups — zero shared files
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — A11y frontend/src/components/ui/ — add aria-labels,
focus rings, tab order
```
All UI primitives (Wk15)
```
Agent 2 Agent 2 — Mobile frontend/src/app/ pages — add responsive
```
Tailwind classes (sm: md: lg:)
```
```
All pages (Wks 15-17)
```
Agent 3 Agent 3 — Dark
Mode
frontend/tailwind.config.js + dark: class
variants on all components
tailwind.config.js
```
(Wk15)
```
Agent 4 Agent 4 — Error
States
frontend/src/components/common/ErrorBoundary.tsx
— improve error UI
ErrorBoundary.tsx
```
(Wk15)
```
Day 2: Loading states, empty states, skeleton loaders — all independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Skeleton
Loaders
frontend/src/components/ui/Skeleton.tsx None — fully
independent
Agent 2 Agent 2 — Empty
States
```
frontend/src/components/common/EmptyState.tsx UI primitives (Wk15)
```
Agent 3 Agent 3 — Toast
System
frontend/src/components/ui/Toast.tsx —
improve queue + auto-dismiss
```
Toast.tsx (Wk15)
```
Agent 4 Agent 4 — Form
Validation
frontend/src/components/ui/Input.tsx — add
inline error + helper text
```
Input.tsx (Wk15)
```
Day 3: Dashboard component improvements all independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 —
Approval Queue
UX
frontend/src/components/approvals/ApprovalQueue.tsx
— keyboard shortcuts
ApprovalQueue.tsx
```
(Wk16)
```
Agent 2 Agent 2 —
Metrics Charts
frontend/src/components/dashboard/Metrics.tsx — add
sparklines
```
Metrics.tsx (Wk16)
```
Agent 3 Agent 3 —
Activity Feed
frontend/src/components/dashboard/ActivityFeed.tsx
— virtualise long list
ActivityFeed.tsx
```
(Wk16)
```
Agent 4 Agent 4 — Jarvis
Terminal
frontend/src/components/jarvis/GSDTerminal.tsx —
command history
GSDTerminal.tsx
```
(Wk16)
```
Day 4: Performance optimisation — independent per area
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Code Splitting frontend/next.config.js —
dynamic imports for heavy pages
```
next.config.js (Wk15)
```
Agent 2 Agent 2 — Image Optimisation frontend/src/components/ —
convert all <img> to <Image>
```
All components (Wks 15-17)
```
Agent 3 Agent 3 — Bundle Analysis frontend/.next/analyze — run
bundle-analyzer, fix large
chunks
None — fully independent
Agent 4 Agent 4 — API Response
Cache
frontend/src/services/api.ts —
add SWR caching layer
```
api.ts (Wk15)
```
Day 5: Frontend tests for all polish changes — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — A11y Tests tests/ui/test_accessibility.tsx —
axe-core audit on all pages
```
A11y changes (Day 1)
```
Agent 2 Agent 2 — Responsive Tests tests/ui/test_responsive.tsx —
viewport tests
```
(mobile/tablet/desktop)
```
```
Responsive changes (Day
```
```
1)
```
Agent 3 Agent 3 — Lighthouse Re-
run
tests/performance/lighthouse-
week23.json — target >90
```
All polish changes (Days 1-
```
```
4)
```
Agent 4 Agent 4 — Visual Regression tests/ui/test_visual_regression.tsx
— screenshot baseline
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Frontend polish integration test. Run Lighthouse on all key pages — target >90 score. Run axe-core accessibility
audit — zero violations. Run responsive tests on 3 viewport sizes. Check dark mode on all pages. Run: npm run
test. All visual regression snapshots must match.
Week Complete When All Pass:
1 Lighthouse score >90 on all key pages
2 axe-core: zero accessibility violations
3 Responsive: all pages render correctly at mobile/tablet/desktop
4 Dark mode: all pages switch correctly without layout breaks
5 Day 6: frontend polish integration passed
Week 24 — Frontend Complete
Goal for This Week
Client success tooling, health scores, and churn prediction. These are entirely new backend services — all
independent of each other. Build in parallel.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Health score and churn prediction models independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Health
Score
backend/services/client_health_service.py analytics_service.py
```
(Wk4)
```
Agent 2 Agent 2 — Churn
Predictor
backend/services/churn_prediction_service.py analytics_service.py
```
(Wk4)
```
Agent 3 Agent 3 — NPS
Service
backend/services/nps_service.py notification_service.py
```
(Wk4)
```
Agent 4 Agent 4 — Success
Metrics
backend/services/success_metrics_service.py analytics_service.py
```
(Wk4)
```
Day 2: API endpoints for new services all independent
Day 2 Agent File to Build Depends On
```
Agent 1 Agent 1 — Health Score API backend/api/client_health.py client_health_service.py (Day
```
```
1)
```
Agent 2 Agent 2 — Churn API backend/api/churn.py churn_prediction_service.py
```
(Day 1)
```
```
Agent 3 Agent 3 — NPS API backend/api/nps.py nps_service.py (Day 1)
```
Agent 4 Agent 4 — Success Dashboard
API
backend/api/client_success.py success_metrics_service.py
```
(Day 1)
```
Day 3: Frontend components for client success all independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Health
Score Widget
```
frontend/src/components/dashboard/HealthScore.tsx UI primitives (Wk15)
```
Agent 2 Agent 2 — Churn
Risk Banner
```
frontend/src/components/dashboard/ChurnRisk.tsx UI primitives (Wk15)
```
Agent 3 Agent 3 — NPS
Widget
```
frontend/src/components/dashboard/NPS.tsx UI primitives (Wk15)
```
Agent 4 Agent 4 — Success
Page
frontend/src/app/dashboard/client-
success/page.tsx
dashboard layout
```
(Wk16)
```
Day 4: Proactive outreach worker updates and churn alert rules independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Churn Alert Worker workers/proactive_outreach.py
```
(add churn alert)
```
churn_prediction_service.py
```
(Day 1)
```
```
Agent 2 Agent 2 — Health Alert Rule monitoring/alerts.yml (add
```
```
health score drop alert)
```
```
alerts.yml (Wk14)
```
Agent 3 Agent 3 — Monday Report
Update
workers/report_generator.py
```
(add health scores to report)
```
```
report_generator.py (Wk13)
```
Agent 4 Agent 4 — Churn Dashboard monitoring/grafana-
dashboards/churn-dashboard.json
None — fully independent
Day 5: Tests for all new client success features — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Health Score
Tests
tests/unit/test_client_health.py client_health_service.py
```
(Day 1)
```
Agent 2 Agent 2 — Churn Tests tests/unit/test_churn_prediction.py churn_prediction_service.py
```
(Day 1)
```
```
Agent 3 Agent 3 — NPS Tests tests/unit/test_nps.py nps_service.py (Day 1)
```
Agent 4 Agent 4 — Success E2E
Test
```
tests/e2e/test_client_success_flow.py All new services (Days 1-2)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Client success integration test. Seed test data → calculate health score → trigger churn alert → verify worker
sends outreach notification → verify NPS survey sends after ticket resolved → verify health dashboard shows
correct data. Run: pytest tests/integration/test_client_success.py.
Week Complete When All Pass:
1 Health score calculates correctly from ticket + approval data
2 Churn alert fires when health score drops below threshold
3 NPS survey sends automatically after ticket resolution
4 Monday report includes health scores for all clients
5 Day 6: client success tooling integration passed
Week 25 — Frontend Complete
Goal for This Week
Financial services industry vertical. All config, compliance, integration, and test files for financial services are
independent of each other.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Financial services config and compliance rules independent
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — FS
Config
backend/core/industry_configs/financial_services.py
```
(complete)
```
```
config.py (Wk1)
```
Agent 2 Agent 2 — FS
Compliance Rules
```
shared/compliance/financial_services_rules.py jurisdiction.py (Wk7)
```
Agent 3 Agent 3 — FS
Feature Flags
feature_flags/financial_services_flags.json None — fully
independent
Agent 4 Agent 4 — FS BDD
Scenarios
docs/bdd_scenarios/financial_services_bdd.md None — fully
independent
Day 2: FS-specific integrations independent of each other
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Plaid Client shared/integrations/plaid_client.py config.py, logger.py
```
(Wk1)
```
Agent 2 Agent 2 — Salesforce
Client
shared/integrations/salesforce_client.py config.py, logger.py
```
(Wk1)
```
Agent 3 Agent 3 — Bloomberg
Client
shared/integrations/bloomberg_client.py config.py, logger.py
```
(Wk1)
```
Agent 4 Agent 4 — FS MCP
Server
```
mcp_servers/integrations/financial_server.py base_server.py (Wk8)
```
Day 3: FS agents and workflows independent of each other
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — FS
Agents
```
variants/parwa_high/agents/financial_agent.py base_agent.py (Wk9)
```
Agent 2 Agent 2 — FS
Workflows
```
variants/parwa_high/workflows/financial_services.py financial_agent.py (Day
```
```
3 — wait)
```
Agent 3 Agent 3 — FS
Tools
```
variants/parwa_high/tools/financial_tools.py plaid_client.py (Day 2)
```
Agent 4 Agent 4 — FS
Onboarding
Config
```
backend/services/onboarding_service.py (FS
```
```
extension)
```
onboarding_service.py
```
(Wk4)
```
Day 4: FS-specific monitoring and alerts independent
Day 4 Agent File to Build Depends On
```
Agent 1 Agent 1 — FS Alert Rules monitoring/alerts.yml (add FS-
```
```
specific alerts)
```
```
alerts.yml (Wk14)
```
Agent 2 Agent 2 — FS Dashboard monitoring/grafana-
dashboards/financial-services-
dashboard.json
None — fully independent
```
Agent 3 Agent 3 — AML Enhancement security/kyc_aml.py (add FS-
```
```
specific AML rules)
```
```
kyc_aml.py (Wk3)
```
```
Agent 4 Agent 4 — FS Rate Limits security/rate_limiter.py (add
```
```
FS transaction rate limits)
```
```
rate_limiter.py (Wk3)
```
Day 5: FS tests all independent of each other
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — FS Config
Tests
```
tests/unit/test_financial_services_config.py FS config (Day 1)
```
Agent 2 Agent 2 — FS
Compliance Tests
tests/unit/test_fs_compliance.py FS compliance rules
```
(Day 1)
```
Agent 3 Agent 3 — FS
Integration Tests
tests/integration/test_financial_services.py FS agents+tools
```
(Days 2-3)
```
Agent 4 Agent 4 — FS BDD
Tests
```
tests/bdd/test_financial_services_scenarios.py FS BDD doc (Day 1)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Financial services vertical integration test. Onboard a test FS client → verify AML check fires on high-value
```
transaction → verify FS compliance rules apply correctly → verify Plaid connection works (mocked) → verify FS-
```
```
specific approval threshold ($500) applies. Run: pytest tests/integration/test_financial_services.py.
```
Week Complete When All Pass:
1 FS onboarding: industry config loads and applies correctly
```
2 AML: high-value transaction ($10k+) triggers enhanced review
```
3 FS compliance rules: correct jurisdiction applied
4 Plaid client: mock connection initialises without errors
5 Day 6: financial services vertical integration passed
Week 26 — Frontend Complete
Goal for This Week
Performance deep optimisation — target P95 <300ms. Cache, DB, router, and token optimisations are all
independent of each other. Build simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Caching strategy improvements — independent per layer
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Redis Strategy shared/utils/cache.py — multi-level
TTL + cache warming
```
cache.py (Wk2)
```
Agent 2 Agent 2 — Response Cache backend/app/middleware.py — add HTTP
response caching
```
middleware.py (Wk3)
```
Agent 3 Agent 3 — Query Cache backend/app/database.py — SQLAlchemy
query result caching
```
database.py (Wk2)
```
Agent 4 Agent 4 — KB Cache shared/knowledge_base/vector_store.py
— cache frequent embeddings
```
vector_store.py (Wk5)
```
Day 2: Database optimisation — indexes and query plans independent
Day 2 Agent File to Build Depends On
Agent
1
Agent 1 —
Ticket Indexes
database/migrations/versions/007_performance_indexes.py 001_initial_schema.py
```
(Wk2)
```
Agent
2
Agent 2 —
Slow Query
Log
```
database/slow-queries.sql — analyse and fix N+1 queries schema.sql (Wk2)
```
Agent
3
Agent 3 —
Connection
Pool
backend/app/database.py — tune pool size for 20-client
load
```
database.py (Wk2)
```
Agent
4
Agent 4 —
Audit Trail
Archive
database/migrations/versions/008_audit_archive.py —
partition old data
003_audit_trail.py
```
(Wk2)
```
Day 3: AI routing optimisation independent of DB optimisation
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Router Tuning shared/smart_router/router.py — tune
```
thresholds (target 90%+ Light)
```
```
router.py (Wk5)
```
Agent 2 Agent 2 — Complexity
Tuning
shared/smart_router/complexity_scorer.py
— recalibrate weights
complexity_scorer.py
```
(Wk5)
```
Agent 3 Agent 3 — GSD
Compression Tuning
shared/gsd_engine/compression.py — tune
85% threshold
```
compression.py (Wk5)
```
Agent 4 Agent 4 — Token Budget shared/trivya_techniques/orchestrator.py
— strict token budgets per tier
```
orchestrator.py (Wk6)
```
Day 4: Worker throughput and async improvements independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Worker
Concurrency
workers/worker.py — tune ARQ
concurrency settings
```
worker.py (Wk13)
```
Agent 2 Agent 2 — Async Endpoints backend/api/support.py — ensure
all DB calls are async
```
support.py (Wk4)
```
Agent 3 Agent 3 — Batch Operations backend/api/support.py — add
bulk ticket operations
```
support.py (Wk4)
```
Agent 4 Agent 4 — Frontend API frontend/src/services/api.ts —
add request deduplication
```
api.ts (Wk15)
```
Day 5: Performance benchmarks and optimisation tests independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Load Test P95 tests/performance/test_load.py — run at
200 concurrent users
```
Full backend (Wks 1-25)
```
Agent 2 Agent 2 — Cache Hit Rate
Test
tests/performance/test_cache_hit_rate.py cache.py optimisations
```
(Day 1)
```
Agent 3 Agent 3 — DB Query
Time Test
```
tests/performance/test_db_query_times.py DB optimisations (Day 2)
```
Agent 4 Agent 4 — Token Usage
Report
tests/performance/token-usage-report-
wk26.md
```
Router tuning (Day 3)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Performance validation. Run load test at 200 concurrent users — P95 must be <300ms. Cache hit rate must be
>75%. Light tier routing must be >90%. DB slow query log must show zero queries >100ms. Run: pytest
tests/performance/. Compare all metrics against Week 18 baseline.
Week Complete When All Pass:
1 P95 latency <300ms at 200 concurrent users
2 Cache hit rate >75%
3 Light tier routing >90% of all queries
4 Zero DB queries >100ms in slow query log
5 Day 6: performance optimisation targets all met
Week 27 — Frontend Complete
Goal for This Week
20-client scale validation. Each client's isolation test, load test, and Agent Lightning run are independent. Build all
test infrastructure simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Clients 11-20 onboarding — all independent per client group
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Clients 11-13 Industry configs + KB ingestion
for clients 11-13
```
onboarding_service.py (Wk4)
```
Agent 2 Agent 2 — Clients 14-16 Industry configs + KB ingestion
for clients 14-16
```
onboarding_service.py (Wk4)
```
Agent 3 Agent 3 — Clients 17-18 Industry configs + KB ingestion
for clients 17-18
```
onboarding_service.py (Wk4)
```
Agent 4 Agent 4 — Clients 19-20 Industry configs + KB ingestion
for clients 19-20
```
onboarding_service.py (Wk4)
```
Day 2: 20-client test infrastructure — independent test files
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Isolation
Test
```
tests/integration/test_20_client_isolation.py rls_policies.sql (Wk3)
```
Agent 2 Agent 2 — 20-Client
Load Test
```
tests/performance/test_20_client_load.py test_load.py (Wk14)
```
Agent 3 Agent 3 — KB
Isolation Test
```
tests/integration/test_20_client_kb_isolation.py vector_store.py (Wk5)
```
Agent 4 Agent 4 — Worker
Isolation Test
```
tests/integration/test_20_client_workers.py worker.py (Wk13)
```
Day 3: Agent Lightning week 12 run — pipeline steps independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Export Dataset Export 20-client combined
training dataset
```
dataset_builder.py (Wk13)
```
Agent 2 Agent 2 — Fine Tune Fine tune on 20-client dataset
```
(target 88%)
```
```
fine_tune.py (Wk13)
```
Agent 3 Agent 3 — Validate + Deploy Validate + deploy if >90%
accuracy
validate.py, deploy_model.py
```
(Wk13)
```
Agent 4 Agent 4 — Drift Detection Drift check across all 20
client models
```
drift_detector.py (Wk13)
```
Day 4: Infrastructure scaling for 20 clients — independent configs
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — K8s HPA Tuning infra/kubernetes/autoscaling/hpa.yaml
— tune for 20-client load
```
hpa.yaml (Wk18)
```
Agent 2 Agent 2 — Redis Cluster docker-compose.prod.yml — add Redis
sentinel for HA
docker-compose.prod.yml
```
(Wk2)
```
Agent 3 Agent 3 — DB Read
Replica
```
infra/scripts/setup-read-replica.sh database.py (Wk2)
```
Agent 4 Agent 4 — Monitoring
Scale
monitoring/prometheus.yml — add 20-
client scrape targets
```
prometheus.yml (Wk8)
```
Day 5: 20-client reports and docs — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — 20-Client
Report
docs/client-reports/20-client-milestone.md None — fully
independent
Agent 2 Agent 2 — Scaling
Architecture Doc
docs/architecture_decisions/006_20_client_scale.md None — fully
independent
Agent 3 Agent 3 —
Performance
Comparison
tests/performance/wk27-vs-wk18-comparison.md None — fully
independent
Agent 4 Agent 4 —
PROJECT_STATE
Update
```
PROJECT_STATE.md (20-client milestone) None — fully
```
independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
20-client scale validation gate. 200 cross-tenant isolation tests: 0 leaks. 500 concurrent users across 20 clients:
P95 <300ms. Agent Lightning accuracy ≥88%. All 20 client KBs isolated. Redis HA failover works. Run: pytest
tests/integration/test_20_client_isolation.py + pytest tests/performance/test_20_client_load.py.
Week Complete When All Pass:
1 20-client isolation: 0 data leaks in 200 cross-tenant tests
2 500 concurrent users: P95 <300ms
3 Agent Lightning: ≥88% accuracy
4 Redis HA: failover completes in <10 seconds
5 Day 6: 20-client scale validation passed
Week 28 — Integration, Testing & Launch
Goal for This Week
Agent Lightning 90%+ accuracy milestone. Training pipeline optimisation, collective intelligence improvements,
and monitoring enhancements. All independent.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Training pipeline optimisations — independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Data
Quality Filter
agent_lightning/data/dataset_builder.py — add
quality scoring filter
dataset_builder.py
```
(Wk13)
```
Agent 2 Agent 2 — Training
Hyperparams
agent_lightning/training/trainer.py — tune
LoRA rank and alpha
```
trainer.py (Wk13)
```
Agent 3 Agent 3 — Validation
Threshold
agent_lightning/training/validate.py — raise
threshold to 92%
```
validate.py (Wk13)
```
Agent 4 Agent 4 — Accuracy
Tracker v2
agent_lightning/monitoring/accuracy_tracker.py
— add per-category breakdown
accuracy_tracker.py
```
(Wk13)
```
Day 2: Collective intelligence improvements — independent files
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Cross-Client
Patterns
shared/utils/collective_intelligence.py
— improve anonymisation
collective_intelligence.py
```
(Wk21)
```
Agent 2 Agent 2 — Industry
Benchmarks
backend/services/analytics_service.py —
add industry benchmark comparison
```
analytics_service.py (Wk4)
```
Agent 3 Agent 3 — Insight
Generator
workers/report_generator.py — add
collective insights section
```
report_generator.py (Wk13)
```
Agent 4 Agent 4 — Benchmark
API
backend/api/analytics.py — add
/benchmarks endpoint
```
analytics.py (Wk4)
```
Day 3: Model versioning and rollback improvements — independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Model
Registry v2
agent_lightning/deployment/model_registry.py
— add metadata + tags
model_registry.py
```
(Wk13)
```
Agent 2 Agent 2 — A/B Testing agent_lightning/deployment/ab_testing.py —
route 10% to new model
model_registry.py
```
(Wk13)
```
Agent 3 Agent 3 — Rollback
Automation
agent_lightning/deployment/rollback.py —
auto-rollback on drift
rollback.py,
```
drift_detector.py (Wk13)
```
Agent 4 Agent 4 — Training
Job Monitor
workers/training_job.py — add Slack/email
notification on completion
```
training_job.py (Wk13)
```
Day 4: 90% accuracy target run — pipeline steps independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Export Best Dataset Export highest-quality 20-
client dataset with quality
filter
dataset_builder.py
```
improvements (Day 1)
```
Agent 2 Agent 2 — Fine Tune 90% Run Fine tune with tuned
hyperparams — target 90%+
trainer.py improvements
```
(Day 1)
```
Agent 3 Agent 3 — Validate 90%+ Validate — must pass new 92%
validation threshold
validate.py improvements
```
(Day 1)
```
```
Agent 4 Agent 4 — Deploy + A/B Deploy with 10% A/B test split ab_testing.py (Day 3)
```
Day 5: 90% accuracy milestone tests and docs — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Training Pipeline
Tests
tests/unit/test_training_pipeline.py
— test all improvements
All training improvements
```
(Days 1-3)
```
Agent 2 Agent 2 — A/B Test
Evaluation
```
tests/integration/test_ab_testing.py ab_testing.py (Day 3)
```
Agent 3 Agent 3 — 90% Milestone
Report
docs/agent-lightning/90-percent-
accuracy-milestone.md
None — fully independent
Agent 4 Agent 4 — Collective
Intelligence Report
docs/agent-lightning/collective-
intelligence-report.md
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Agent Lightning 90%+ milestone gate. Run full training pipeline with quality filter → validate → deploy. Accuracy
must reach 90%+. A/B test: new model serves 10% of traffic correctly. Auto-rollback: simulate drift → verify
rollback fires automatically. Run: pytest tests/unit/test_training_pipeline.py + pytest
tests/integration/test_ab_testing.py.
Week Complete When All Pass:
1 Agent Lightning accuracy: ≥90% on validation set
2 A/B test: new model correctly serves 10% of traffic
3 Auto-rollback: fires within 60 seconds of drift detection
```
4 Collective intelligence: anonymisation verified (no PII in cross-client data)
```
5 Day 6: 90% accuracy milestone gate passed
Week 29 — Integration, Testing & Launch
Goal for This Week
Multi-region data residency. Terraform files per region are independent. DB replication config is independent of
app-layer changes. All build in parallel.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Terraform infrastructure per region — independent files
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — EU Region Infra infra/terraform/regions/eu-
west-1.tf
```
infra/terraform/ (Wk18)
```
Agent 2 Agent 2 — US Region Infra infra/terraform/regions/us-
east-1.tf
```
infra/terraform/ (Wk18)
```
Agent 3 Agent 3 — APAC Region Infra infra/terraform/regions/ap-
southeast-1.tf
```
infra/terraform/ (Wk18)
```
Agent 4 Agent 4 — Region Config shared/core_functions/config.py
```
(add DATA_RESIDENCY env var)
```
```
config.py (Wk1)
```
Day 2: Data residency enforcement in app layer — independent files
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 —
Residency Router
```
backend/core/data_residency_router.py config.py update (Day 1)
```
Agent 2 Agent 2 — DB
Migration 009
database/migrations/versions/009_data_residency.py 001_initial_schema.py
```
(Wk2)
```
Agent 3 Agent 3 — GDPR
Region Rules
```
shared/compliance/jurisdiction.py (add region-
```
```
specific rules)
```
```
jurisdiction.py (Wk7)
```
Agent 4 Agent 4 — Region
Selection UI
frontend/src/app/dashboard/settings/data-
residency/page.tsx
dashboard layout
```
(Wk16)
```
Day 3: Cross-region replication and failover — independent per service
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — DB
Replication Config
```
infra/terraform/database-replication.tf database.tf (Wk18)
```
Agent 2 Agent 2 — Redis
Replication
```
infra/terraform/redis-replication.tf redis.tf (Wk18)
```
Agent 3 Agent 3 — S3
Replication
```
infra/terraform/storage-replication.tf storage.tf (Wk18)
```
Agent 4 Agent 4 — ADR Multi-
Region
docs/architecture_decisions/005_multi_region.md
```
(complete)
```
None — fully
independent
Day 4: Region compliance documentation — independent documents
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — GDPR EU Doc legal/gdpr-eu-data-residency-
compliance.md
None — fully independent
Agent 2 Agent 2 — UK PECR Doc legal/uk-pecr-compliance.md None — fully independent
Agent 3 Agent 3 — APAC Privacy Doc legal/apac-privacy-laws-
compliance.md
None — fully independent
Agent 4 Agent 4 — Data Map legal/data-flow-map.md — where
each data type is stored per
region
None — fully independent
Day 5: Multi-region tests — independent per region
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — EU
Residency Test
```
tests/integration/test_eu_data_residency.py EU config (Days 1-2)
```
Agent 2 Agent 2 — US
Residency Test
```
tests/integration/test_us_data_residency.py US config (Days 1-2)
```
Agent 3 Agent 3 — Cross-
Region Isolation Test
tests/integration/test_cross_region_isolation.py All region configs
```
(Days 1-2)
```
Agent 4 Agent 4 — Replication
Lag Test
```
tests/integration/test_replication_lag.py DB replication (Day
```
```
3)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Multi-region data residency integration test. EU client data must not appear in US region DB. US client data must
not appear in EU region DB. Replication lag must be <500ms. GDPR export must only contain data from client's
assigned region. Run: pytest tests/integration/test_eu_data_residency.py + test_cross_region_isolation.py.
Week Complete When All Pass:
1 EU client data confirmed absent from US region DB
2 Cross-region isolation: 0 data leaks in 50 tests
3 DB replication lag <500ms
4 GDPR export: only data from client's assigned region
5 Day 6: multi-region data residency integration passed
Week 30 — Integration, Testing & Launch
Goal for This Week
30-client milestone. Full regression run, security re-audit, Agent Lightning week 15. All test suites run in parallel
— they are independent of each other.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Clients 21-30 onboarding — independent per client group
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Clients 21-23 Industry configs + KB ingestion
for clients 21-23
```
onboarding_service.py (Wk4)
```
Agent 2 Agent 2 — Clients 24-26 Industry configs + KB ingestion
for clients 24-26
```
onboarding_service.py (Wk4)
```
Agent 3 Agent 3 — Clients 27-28 Industry configs + KB ingestion
for clients 27-28
```
onboarding_service.py (Wk4)
```
Agent 4 Agent 4 — Clients 29-30 Industry configs + KB ingestion
for clients 29-30
```
onboarding_service.py (Wk4)
```
Day 2: Full regression test suites — all independent categories
Day 2 Agent File to Build Depends On
```
Agent 1 Agent 1 — Unit Suite pytest tests/unit/ (full run —
```
```
30-client)
```
```
All unit tests (Wks 1-29)
```
```
Agent 2 Agent 2 — Integration Suite pytest tests/integration/ (full
```
```
run)
```
```
All integration tests (Wks 1-
```
```
29)
```
```
Agent 3 Agent 3 — E2E Suite pytest tests/e2e/ (full run) All e2e tests (Wks 1-29)
```
```
Agent 4 Agent 4 — BDD Suite pytest tests/bdd/ (full run) All bdd tests (Wks 1-29)
```
Day 3: Security re-audit — independent scans
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — OWASP Re-scan Full OWASP ZAP scan at 30-
client scale
Full backend
Agent 2 Agent 2 — 30-Client RLS Test 300 cross-tenant isolation
tests
```
rls_policies.sql (Wk3)
```
Agent 3 Agent 3 — CVE Re-scan snyk test all Docker images —
fix any new CVEs
All Dockerfiles
Agent 4 Agent 4 — Secrets Audit Audit all env vars — ensure no
hardcoded secrets
None — fully independent
Day 4: Agent Lightning week 15 run + 30-client load test — independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — AL Week
15 Run
```
Export + fine tune + validate + deploy (target
```
```
91%+)
```
fine_tune.py,
```
validate.py (Wk13)
```
Agent 2 Agent 2 — 30-Client
Load Test
```
locust — 30 clients, 1000 concurrent users test_load.py (Wk14)
```
Agent 3 Agent 3 — Memory
Profiling
tests/performance/memory_profile_30_clients.py None — fully
independent
Agent 4 Agent 4 — Cost
Analysis
docs/operations/30-client-cost-analysis.md None — fully
independent
Day 5: 30-client milestone docs — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — 30-Client Report docs/client-reports/30-client-
milestone.md
None — fully independent
Agent 2 Agent 2 — Security Audit
Report
docs/security/30-client-
security-audit.md
```
Security scans (Day 3)
```
Agent 3 Agent 3 — Performance Report tests/performance/30-client-
performance-report.md
```
Load test (Day 4)
```
Agent 4 Agent 4 — PROJECT_STATE
Update
```
PROJECT_STATE.md (30-client
```
```
milestone)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
30-client milestone gate. 300 cross-tenant isolation tests: 0 leaks. 1000 concurrent users: P95 <300ms. Agent
Lightning ≥91% accuracy. Full regression: all tests pass. OWASP: clean. CVEs: zero critical. This is the Phase 8
halfway checkpoint.
Week Complete When All Pass:
1 300 cross-tenant isolation tests: 0 data leaks
2 1000 concurrent users: P95 <300ms
3 Agent Lightning: ≥91% accuracy
4 Full regression: 100% pass rate
5 OWASP scan: clean. CVEs: zero critical
6 Day 6: 30-client milestone gate passed
Week 31 — Integration, Testing & Launch
Goal for This Week
E-commerce industry deep features. Shopify API updates, inventory management, abandoned cart recovery. All
new e-commerce files are independent.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Shopify advanced features — independent files
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Shopify
v2 Client
shared/integrations/shopify_client.py — add
inventory + abandoned cart APIs
shopify_client.py
```
(Wk7)
```
Agent 2 Agent 2 — Cart
Recovery Agent
```
variants/parwa_high/agents/cart_recovery_agent.py base_agent.py (Wk9)
```
Agent 3 Agent 3 —
Inventory Agent
```
variants/parwa/agents/inventory_agent.py base_agent.py (Wk9)
```
Agent 4 Agent 4 — Cart
Recovery Worker
workers/cart_recovery.py shopify_client.py
```
(Wk7)
```
Day 2: E-commerce workflows and tools independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Cart
Recovery Workflow
variants/parwa_high/workflows/cart_recovery.py cart_recovery_agent.py
```
(Day 1)
```
Agent 2 Agent 2 — Inventory
Workflow
```
variants/parwa/workflows/inventory_management.py inventory_agent.py (Day
```
```
1)
```
Agent 3 Agent 3 —
WooCommerce
Client
```
shared/integrations/woocommerce_client.py config.py (Wk1)
```
Agent 4 Agent 4 — Magento
Client
```
shared/integrations/magento_client.py config.py (Wk1)
```
Day 3: E-commerce MCP servers and tools independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 —
WooCommerce MCP
```
mcp_servers/integrations/woocommerce_server.py base_server.py (Wk8)
```
Agent 2 Agent 2 — Inventory
MCP
```
mcp_servers/tools/inventory_server.py base_server.py (Wk8)
```
Agent 3 Agent 3 — Cart
Recovery MCP
```
mcp_servers/tools/cart_recovery_server.py base_server.py (Wk8)
```
Agent 4 Agent 4 — E-commerce
Dashboard
monitoring/grafana-dashboards/ecommerce-
dashboard.json
None — fully
independent
Day 4: E-commerce frontend components independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Cart
Recovery UI
frontend/src/components/dashboard/CartRecovery.tsx UI primitives
```
(Wk15)
```
Agent 2 Agent 2 —
Inventory Widget
frontend/src/components/dashboard/Inventory.tsx UI primitives
```
(Wk15)
```
Agent 3 Agent 3 — E-
commerce
Settings
frontend/src/app/dashboard/settings/ecommerce/page.tsx dashboard layout
```
(Wk16)
```
Agent 4 Agent 4 —
Revenue Analytics
frontend/src/components/dashboard/RevenueAnalytics.tsx UI primitives
```
(Wk15)
```
Day 5: E-commerce tests all independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Cart Recovery
Tests
tests/unit/test_cart_recovery.py cart_recovery_agent.py
```
(Day 1)
```
Agent 2 Agent 2 — Inventory
Tests
```
tests/unit/test_inventory_management.py inventory_agent.py (Day 1)
```
Agent 3 Agent 3 —
WooCommerce Tests
tests/unit/test_woocommerce_client.py woocommerce_client.py
```
(Day 2)
```
Agent 4 Agent 4 — E2E Cart
Recovery
```
tests/e2e/test_cart_recovery_flow.py All e-commerce files (Days
```
```
1-3)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
E-commerce integration test. Abandoned cart detected → cart_recovery_agent triggers → email sent within 1
hour → customer replies → ticket created → resolved. Inventory check: out-of-stock item → agent notifies
customer proactively. Run: pytest tests/integration/test_ecommerce_advanced.py.
Week Complete When All Pass:
1 Cart recovery: email sent within 1 hour of abandonment
2 Inventory: out-of-stock proactive notification works
3 WooCommerce client: mock connection initialises
4 E-commerce dashboard: all widgets render with real data
5 Day 6: e-commerce advanced integration passed
Week 32 — Integration, Testing & Launch
Goal for This Week
SaaS industry deep features. GitHub deployment tracking, Zendesk integration, and SaaS-specific workflows. All
files independent.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: SaaS integrations independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — GitHub v2
Client
shared/integrations/github_client.py —
add deployment + PR tracking
```
github_client.py (Wk7)
```
Agent 2 Agent 2 — Zendesk v2
Client
shared/integrations/zendesk_client.py —
add macro + webhook support
```
zendesk_client.py (Wk7)
```
```
Agent 3 Agent 3 — Intercom Client shared/integrations/intercom_client.py config.py (Wk1)
```
Agent 4 Agent 4 — PagerDuty
Client
```
shared/integrations/pagerduty_client.py config.py (Wk1)
```
Day 2: SaaS agents and workflows independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Bug
Triage Agent
variants/parwa/agents/bug_triage_agent.py base_agent.py,
```
github_client.py (Wks 7-
```
```
9)
```
Agent 2 Agent 2 —
Deployment Agent
variants/parwa_high/agents/deployment_agent.py base_agent.py,
```
github_client.py (Wks 7-
```
```
9)
```
Agent 3 Agent 3 — Bug
Triage Workflow
variants/parwa/workflows/bug_triage.py bug_triage_agent.py
```
(Day 2 — wait)
```
Agent 4 Agent 4 — SaaS
Incident Workflow
variants/parwa_high/workflows/saas_incident.py deployment_agent.py
```
(Day 2 — wait)
```
Day 3: SaaS MCP servers and monitoring independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — GitHub MCP
Server
```
mcp_servers/integrations/github_server.py base_server.py (Wk8)
```
Agent 2 Agent 2 — Zendesk MCP
Server
```
mcp_servers/integrations/zendesk_server.py base_server.py (Wk8)
```
Agent 3 Agent 3 — SaaS
Dashboard
monitoring/grafana-dashboards/saas-
dashboard.json
None — fully
independent
Agent 4 Agent 4 — SaaS Alert
Rules
```
monitoring/alerts.yml (add SaaS deployment
```
```
failure alert)
```
```
alerts.yml (Wk14)
```
Day 4: SaaS frontend and DB migration independent
Day 4 Agent File to Build Depends On
Agent
1
Agent 1 —
Bug Tracker
Widget
```
frontend/src/components/dashboard/BugTracker.tsx UI primitives (Wk15)
```
Agent
2
Agent 2 —
Deployment
Timeline
```
frontend/src/components/dashboard/DeploymentTimeline.tsx UI primitives (Wk15)
```
Agent
3
Agent 3 —
SaaS Settings
frontend/src/app/dashboard/settings/saas/page.tsx dashboard layout
```
(Wk16)
```
Agent
4
Agent 4 — DB
Migration 010
database/migrations/versions/010_saas_features.py 001_initial_schema.py
```
(Wk2)
```
Day 5: SaaS tests all independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Bug Triage
Tests
```
tests/unit/test_bug_triage_agent.py bug_triage_agent.py (Day
```
```
2)
```
Agent 2 Agent 2 — Deployment
Tests
```
tests/unit/test_deployment_agent.py deployment_agent.py (Day
```
```
2)
```
Agent 3 Agent 3 — SaaS
Integration Tests
```
tests/integration/test_saas_advanced.py All SaaS files (Days 1-4)
```
Agent 4 Agent 4 — SaaS BDD
Tests
```
tests/bdd/test_saas_scenarios.py SaaS BDD doc (Wk25)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
SaaS integration test. GitHub deployment triggers → deployment_agent notifies affected customers → Zendesk
ticket auto-created → bug triage agent categorises by severity → PagerDuty alert for P0. Run: pytest
tests/integration/test_saas_advanced.py.
Week Complete When All Pass:
1 Deployment event: customer notification sent within 2 minutes
2 Bug triage: P0 triggers PagerDuty alert
3 Zendesk: ticket auto-created from GitHub issue
4 SaaS dashboard: all deployment/bug widgets render
5 Day 6: SaaS advanced integration passed
Week 33 — Integration, Testing & Launch
Goal for This Week
Healthcare HIPAA hardening and logistics industry. These are two separate work streams — healthcare files and
logistics files are completely independent.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Healthcare hardening independent of logistics
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — HIPAA Audit shared/compliance/healthcare_guard.py —
full HIPAA audit + fixes
```
healthcare_guard.py (Wk7)
```
Agent 2 Agent 2 — Epic EHR v2 shared/integrations/epic_ehr_client.py
```
— add appointment + results (read-only)
```
```
epic_ehr_client.py (Wk7)
```
Agent 3 Agent 3 — AfterShip v2 shared/integrations/aftership_client.py
— add real-time webhooks
```
aftership_client.py (Wk7)
```
```
Agent 4 Agent 4 — Freight Client shared/integrations/freight_client.py config.py (Wk1)
```
Day 2: Healthcare and logistics agents independent of each other
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Healthcare
Agent v2
variants/parwa_high/agents/healthcare_agent.py
— HIPAA improvements
base_agent.py,
healthcare_guard.py
```
(Wks 7-9)
```
Agent 2 Agent 2 —
Appointment Agent
variants/parwa/agents/appointment_agent.py base_agent.py,
```
epic_ehr_client.py (Day
```
```
1)
```
Agent 3 Agent 3 — Shipment
Agent
variants/parwa/agents/shipment_agent.py base_agent.py,
```
aftership_client.py (Day
```
```
1)
```
Agent 4 Agent 4 — Freight
Agent
variants/parwa_high/agents/freight_agent.py base_agent.py,
```
freight_client.py (Day 1)
```
Day 3: Workflows and MCP servers — healthcare and logistics independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 —
Healthcare
Workflow v2
variants/parwa_high/workflows/healthcare_v2.py healthcare_agent.py
```
(Day 2)
```
Agent 2 Agent 2 —
Appointment
Workflow
variants/parwa/workflows/appointment_management.py appointment_agent.py
```
(Day 2)
```
Agent 3 Agent 3 —
Shipment
Workflow
```
variants/parwa/workflows/shipment_tracking.py shipment_agent.py (Day
```
```
2)
```
Agent 4 Agent 4 —
Logistics MCP
Server
```
mcp_servers/integrations/logistics_server.py base_server.py (Wk8)
```
Day 4: BAA update and compliance docs — independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — BAA v2 legal/baa_template.md — update
with Epic EHR scope
None — fully independent
Agent 2 Agent 2 — HIPAA Checklist docs/compliance/hipaa-
implementation-checklist.md
None — fully independent
Agent 3 Agent 3 — Logistics
Compliance
docs/compliance/logistics-data-
handling.md
None — fully independent
Agent 4 Agent 4 — Healthcare
Dashboard
monitoring/grafana-
dashboards/healthcare-
dashboard.json
None — fully independent
Day 5: Healthcare and logistics tests — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — HIPAA
Tests
tests/integration/test_hipaa_compliance.py healthcare hardening
```
(Days 1-2)
```
Agent 2 Agent 2 —
Appointment Tests
tests/unit/test_appointment_agent.py appointment_agent.py
```
(Day 2)
```
Agent 3 Agent 3 — Shipment
Tests
```
tests/unit/test_shipment_agent.py shipment_agent.py (Day
```
```
2)
```
Agent 4 Agent 4 — Logistics
Integration
```
tests/integration/test_logistics_advanced.py All logistics files (Days 1-
```
```
3)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Healthcare + logistics integration test. Healthcare: PHI not logged, BAA check enforced, Epic EHR read-only
confirmed. Logistics: shipment update → proactive customer notification. Run: pytest
tests/integration/test_hipaa_compliance.py + test_logistics_advanced.py. HIPAA: PHI must not appear in any log
file.
Week Complete When All Pass:
1 HIPAA: PHI confirmed absent from all log files
2 BAA check: healthcare client without BAA blocked from PHI endpoints
3 Shipment: real-time update triggers customer notification
4 Logistics dashboard: tracking widget renders
5 Day 6: healthcare HIPAA + logistics integration passed
Week 34 — Integration, Testing & Launch
Goal for This Week
Frontend v2 improvements. Faster load times, improved UX patterns, and new dashboard widgets. All
component updates are independent.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Performance and UX improvements independent per component
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — React
Query
frontend — replace custom hooks with React Query
for data fetching
```
All hooks (Wk16)
```
Agent 2 Agent 2 —
Optimistic Updates
frontend/src/stores/ — add optimistic UI for
approvals
```
ticketStore.ts (Wk15)
```
Agent 3 Agent 3 — Infinite
Scroll
frontend/src/components/dashboard/ActivityFeed.tsx
— add infinite scroll
ActivityFeed.tsx
```
(Wk16)
```
Agent 4 Agent 4 —
Command Palette
frontend/src/components/common/CommandPalette.tsx
```
(Cmd+K)
```
```
UI primitives (Wk15)
```
Day 2: New dashboard widgets all independent of each other
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — ROI
Calculator Widget
frontend/src/components/dashboard/ROICalculator.tsx
```
(redesign)
```
UI primitives
```
(Wk15)
```
Agent 2 Agent 2 — Weekly
Wins Widget
frontend/src/components/dashboard/WeeklyWins.tsx UI primitives
```
(Wk15)
```
Agent 3 Agent 3 — Team
Leaderboard
frontend/src/components/dashboard/TeamLeaderboard.tsx UI primitives
```
(Wk15)
```
Agent 4 Agent 4 —
Notification Centre
frontend/src/components/common/NotificationCentre.tsx UI primitives
```
(Wk15)
```
Day 3: Auth improvements independent of dashboard improvements
Day 3 Agent File to Build Depends On
Agent
1
Agent 1 — 2FA
Frontend
```
frontend/src/app/(auth)/two-factor/page.tsx None — fully
```
independent
Agent
2
Agent 2 —
Session
Management
frontend/src/services/authService.ts — add session
timeout + refresh
```
authService.ts (Wk17)
```
Agent
3
Agent 3 —
Onboarding v2
frontend/src/components/onboarding/OnboardingWizard.tsx
— redesign
OnboardingWizard.tsx
```
(Wk15)
```
Agent
4
Agent 4 —
Pricing Page
v2
frontend/src/app/pricing/page.tsx — add comparison
table
```
pricing page (Wk17)
```
Day 4: Mobile web optimisations independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — PWA
Setup
frontend/public/manifest.json + service-worker.js None — fully
independent
Agent 2 Agent 2 — Touch
Gestures
frontend/src/components/approvals/ApprovalQueue.tsx
— swipe gestures
ApprovalQueue.tsx
```
(Wk16)
```
Agent 3 Agent 3 — Haptic
Feedback
```
frontend/src/hooks/useHaptic.ts (web vibration API) None — fully
```
independent
Agent 4 Agent 4 — Offline
Support
frontend/src/services/offlineQueue.ts — queue
actions when offline
```
api.ts (Wk15)
```
Day 5: Frontend v2 tests all independent
Day 5 Agent File to Build Depends On
```
Agent 1 Agent 1 — React Query Tests tests/ui/test_react_query_hooks.tsx React Query hooks (Day 1)
```
```
Agent 2 Agent 2 — New Widget Tests tests/ui/test_new_widgets.tsx New widgets (Day 2)
```
Agent 3 Agent 3 — Lighthouse v2 tests/performance/lighthouse-
wk34.json — target >92
```
All v2 changes (Days 1-4)
```
Agent 4 Agent 4 — PWA Test tests/ui/test_pwa.tsx — offline +
install prompt
```
PWA setup (Day 4)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Frontend v2 integration test. Lighthouse: all pages >92. PWA: offline queue works. Approval swipe: gesture
triggers approval API. Command palette: opens and finds any page. React Query: optimistic update shows
immediately, reverts on failure. Run: npm run test + lighthouse audit.
Week Complete When All Pass:
1 Lighthouse: all pages score >92
2 PWA: offline action queued and syncs on reconnect
3 Approval swipe: gesture triggers correct API call
4 Command palette: finds any page within 100ms
5 Day 6: frontend v2 integration passed
Week 35 — Integration, Testing & Launch
Goal for This Week
Smart Router optimisation to 92%+ Light tier routing. Advanced techniques and collective intelligence
improvements. Independent per optimisation area.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Router scoring improvements — independent per technique
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Router ML
Model
shared/smart_router/complexity_scorer.py —
train small ML classifier
complexity_scorer.py
```
(Wk5)
```
Agent 2 Agent 2 — Query
Fingerprinting
shared/smart_router/query_fingerprint.py —
cache routing decisions
```
cache.py (Wk2)
```
Agent 3 Agent 3 — Tier Budget
Enforcer
shared/smart_router/tier_budget.py — daily
token budget per client
```
router.py (Wk5)
```
Agent 4 Agent 4 — Router
Analytics
backend/services/router_analytics_service.py
— track routing decisions
analytics_service.py
```
(Wk4)
```
Day 2: Advanced TRIVYA optimisations — independent per tier
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — CLARA
Optimisation
shared/trivya_techniques/tier1/clara.py — reduce
retrieval latency
```
clara.py (Wk6)
```
Agent 2 Agent 2 — CRP
Optimisation
shared/trivya_techniques/tier1/crp.py — improve
compression ratio
```
crp.py (Wk6)
```
Agent 3 Agent 3 — CoT
Optimisation
shared/trivya_techniques/tier2/chain_of_thought.py
— token budget
chain_of_thought.py
```
(Wk6)
```
Agent 4 Agent 4 — Tier 3
Throttle
shared/trivya_techniques/tier3/trigger_detector.py
— stricter threshold
trigger_detector.py
```
(Wk7)
```
Day 3: Collective intelligence improvements — independent files
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 —
Pattern
Aggregator
shared/utils/collective_intelligence.py — better
industry patterns
collective_intelligence.py
```
(Wk21)
```
Agent 2 Agent 2 —
FAQ Auto-
Learn
shared/knowledge_base/kb_manager.py — auto-add high-
confidence answers
```
kb_manager.py (Wk5)
```
Agent 3 Agent 3 —
Routing
Feedback
agent_lightning/data/export_approvals.py — add
routing decision export
export_approvals.py
```
(Wk13)
```
Agent 4 Agent 4 —
Router
```
frontend/src/components/dashboard/RouterAnalytics.tsx UI primitives (Wk15)
```
Dashboard
Widget
Day 4: Router optimisation tests and benchmarks — independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Router
Unit Tests v2
tests/unit/test_smart_router.py — add ML
classifier tests
complexity_scorer.py ML
```
(Day 1)
```
Agent 2 Agent 2 — Token
Usage Test
tests/performance/test_token_usage.py —
verify <budget
```
tier_budget.py (Day 1)
```
Agent 3 Agent 3 — CLARA
Latency Test
tests/performance/test_clara_latency.py —
<200ms
```
CLARA optimisation (Day
```
```
2)
```
Agent 4 Agent 4 — Collective
Intelligence Tests
tests/unit/test_collective_intelligence_v2.py collective_intelligence.py
```
(Day 3)
```
Day 5: Week 35 reports and docs — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Router
Optimisation Report
docs/agent-lightning/router-optimisation-wk35.md None — fully
independent
Agent 2 Agent 2 — Token
Savings Report
docs/operations/token-savings-report-wk35.md None — fully
independent
Agent 3 Agent 3 — CLARA
Benchmark Doc
docs/architecture_decisions/007_clara_performance.md None — fully
independent
Agent 4 Agent 4 —
PROJECT_STATE
Update
```
PROJECT_STATE.md (router optimisation complete) None — fully
```
independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Router optimisation validation. Run 1000 test queries → Light tier must handle >92%. Token budget enforced: no
client exceeds daily budget. CLARA latency <200ms. ML classifier accuracy >85% on test set. Run: pytest
tests/unit/test_smart_router.py + tests/performance/test_token_usage.py.
Week Complete When All Pass:
1 Light tier routing: >92% of 1000 test queries
2 Token budget: enforced across all 30 test clients
3 CLARA latency: <200ms for KB retrieval
4 ML classifier: >85% accuracy on routing decisions
5 Day 6: router optimisation targets met
Week 36 — Integration, Testing & Launch
Goal for This Week
Agent Lightning 94% accuracy milestone. Final fine-tuning, per-category specialisation, and model performance
reporting.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Per-category model specialisation — independent per category
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Refund
Specialist
agent_lightning/training/fine_tune.py —
refund-category specialist model
```
fine_tune.py (Wk13)
```
Agent 2 Agent 2 — VIP
Specialist
agent_lightning/training/fine_tune.py — VIP-
category specialist model
```
fine_tune.py (Wk13)
```
Agent 3 Agent 3 — Technical
Specialist
agent_lightning/training/fine_tune.py —
technical-category specialist
```
fine_tune.py (Wk13)
```
Agent 4 Agent 4 — Category
Router
agent_lightning/deployment/category_router.py
— route to correct specialist
model_registry.py
```
(Wk13)
```
Day 2: Training data improvements — independent per data source
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Synthetic
Data
agent_lightning/data/synthetic_generator.py
— generate edge cases
dataset_builder.py
```
(Wk13)
```
Agent 2 Agent 2 — Human
Corrections
agent_lightning/data/human_corrections.py —
weight human-corrected examples 3x
dataset_builder.py
```
(Wk13)
```
Agent 3 Agent 3 — Industry
Templates
agent_lightning/data/industry_templates.py
— industry-specific training
dataset_builder.py
```
(Wk13)
```
Agent 4 Agent 4 — Data
Pipeline Tests
tests/unit/test_training_data_pipeline.py All data improvements
```
(Days 1-2)
```
Day 3: 94% accuracy target run — pipeline steps in dependency order
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Build 94% Dataset Build enhanced dataset with
synthetic + corrections +
templates
```
All data improvements (Day
```
```
2)
```
Agent 2 Agent 2 — Fine Tune 94% Run Fine tune with per-category
specialists
```
category_router.py (Day 1)
```
```
Agent 3 Agent 3 — Validate 94%+ Validate all specialist models validate.py (Wk13)
```
Agent 4 Agent 4 — Deploy Specialists Deploy all 3 specialist models
- category router
```
validate.py (Day 3 — wait)
```
Day 4: 94% milestone monitoring and reporting — independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Per-Category
Dashboard
monitoring/grafana-
dashboards/category-accuracy-
dashboard.json
None — fully independent
Agent 2 Agent 2 — Category Alert
Rules
monitoring/alerts.yml — per-
category accuracy drop alert
```
alerts.yml (Wk14)
```
Agent 3 Agent 3 — 94% Report docs/agent-lightning/94-
percent-accuracy-milestone.md
None — fully independent
Agent 4 Agent 4 — Client Win Email
Draft
docs/marketing/accuracy-
milestone-client-email.md
None — fully independent
Day 5: 94% milestone validation tests — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Category
Accuracy Tests
```
tests/unit/test_category_specialists.py specialist models (Day 3)
```
Agent 2 Agent 2 — Category Router
Tests
```
tests/unit/test_category_router.py category_router.py (Day
```
```
1)
```
Agent 3 Agent 3 — Regression
Tests
pytest tests/ — verify 94% didn't break
anything
Full test suite
Agent 4 Agent 4 —
PROJECT_STATE Update
```
PROJECT_STATE.md (94% accuracy
```
```
milestone)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
94% accuracy milestone gate. All 3 specialist models must achieve ≥94% on their category test sets. Category
```
router: correct specialist selected >97% of the time. Regression: all existing tests still pass. Run: pytest
```
tests/unit/test_category_specialists.py + pytest tests/.
Week Complete When All Pass:
1 Refund specialist: ≥94% accuracy on refund test set
2 VIP specialist: ≥94% accuracy on VIP test set
3 Technical specialist: ≥94% accuracy on technical test set
4 Category router: correct specialist selected >97%
5 Day 6: 94% accuracy milestone gate passed
Week 37 — Integration, Testing & Launch
Goal for This Week
50-client scale test and infrastructure autoscaling. Load tests, K8s HPA validation, and scaling documentation. All
independent.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Clients 31-50 onboarding — independent per group
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Clients 31-35 Industry configs + KB for
clients 31-35
```
onboarding_service.py (Wk4)
```
Agent 2 Agent 2 — Clients 36-40 Industry configs + KB for
clients 36-40
```
onboarding_service.py (Wk4)
```
Agent 3 Agent 3 — Clients 41-45 Industry configs + KB for
clients 41-45
```
onboarding_service.py (Wk4)
```
Agent 4 Agent 4 — Clients 46-50 Industry configs + KB for
clients 46-50
```
onboarding_service.py (Wk4)
```
Day 2: 50-client test infrastructure — independent test files
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — 50-Client
Isolation Test
```
tests/integration/test_50_client_isolation.py rls_policies.sql (Wk3)
```
Agent 2 Agent 2 — 50-Client
Load Test
tests/performance/test_50_client_load.py
```
(2000 concurrent)
```
```
test_load.py (Wk14)
```
Agent 3 Agent 3 — HPA Scale
Test
```
tests/performance/test_k8s_hpa_scaling.py hpa.yaml (Wk18)
```
Agent 4 Agent 4 — Worker
Scale Test
```
tests/performance/test_worker_scaling.py worker.py (Wk13)
```
Day 3: K8s autoscaling improvements — independent per service
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Backend HPA infra/kubernetes/autoscaling/hpa.yaml
— tune backend 2→20 pods
```
hpa.yaml (Wk18)
```
Agent 2 Agent 2 — Worker KEDA infra/kubernetes/autoscaling/keda-
worker.yaml — scale 1→50 on queue
depth
```
keda-worker.yaml (Wk18)
```
Agent 3 Agent 3 — DB Autoscaling infra/terraform/database.tf — enable
```
connection pooler (PgBouncer)
```
```
database.tf (Wk18)
```
Agent 4 Agent 4 — Vertical Pod
Autoscaler
infra/kubernetes/autoscaling/vpa.yaml
— add VPA for all deployments
None — fully independent
Day 4: Cost optimisation at 50-client scale — independent analysis
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Spot Instance
Config
infra/terraform/eks.tf — add
spot instance node group
```
eks.tf (Wk18)
```
Agent 2 Agent 2 — Reserved Capacity docs/operations/reserved-
capacity-analysis.md
None — fully independent
Agent 3 Agent 3 — Cost Per Client docs/operations/50-client-cost-
per-client.md
None — fully independent
Agent 4 Agent 4 — Cost Dashboard monitoring/grafana-
dashboards/cost-dashboard.json
None — fully independent
Day 5: 50-client milestone docs — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — 50-Client
Report
docs/client-reports/50-client-milestone.md None — fully
independent
Agent 2 Agent 2 — Autoscaling
Report
docs/infrastructure/autoscaling-results-wk37.md None — fully
independent
Agent 3 Agent 3 — Scaling
Architecture
docs/architecture_decisions/008_50_client_scale.md None — fully
independent
Agent 4 Agent 4 —
PROJECT_STATE
Update
```
PROJECT_STATE.md (50-client milestone) None — fully
```
independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
50-client scale gate. 500 cross-tenant isolation tests: 0 leaks. 2000 concurrent users: P95 <300ms. K8s HPA
scales from 2 to 10+ pods under load. KEDA scales workers. DB connection pool holds. Run: pytest
tests/integration/test_50_client_isolation.py + tests/performance/test_50_client_load.py.
Week Complete When All Pass:
1 500 cross-tenant isolation tests: 0 data leaks
2 2000 concurrent users: P95 <300ms
3 K8s HPA: backend scales to 10+ pods under load
4 KEDA: workers scale with queue depth
5 Day 6: 50-client scale gate passed
Week 38 — Integration, Testing & Launch
Goal for This Week
Pre-enterprise preparation. SSO placeholder, advanced compliance docs, security hardening for enterprise sales.
All independent.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Enterprise feature placeholders — independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — SSO
Placeholder
```
backend/api/sso.py (stub endpoints) auth.py (Wk4)
```
Agent 2 Agent 2 — SCIM
Placeholder
```
backend/api/scim.py (stub endpoints) auth.py (Wk4)
```
Agent 3 Agent 3 — Enterprise
Billing
backend/services/billing_service.py —
add enterprise contract billing
```
billing_service.py (Wk4)
```
Agent 4 Agent 4 — Enterprise
Onboarding
backend/services/onboarding_service.py
— add enterprise onboarding flow
onboarding_service.py
```
(Wk4)
```
Day 2: Enterprise security hardening — independent per area
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — IP Allowlist security/rate_limiter.py — add
IP allowlist for enterprise
```
rate_limiter.py (Wk3)
```
Agent 2 Agent 2 — Audit Export backend/api/compliance.py — add
audit log CSV export
```
compliance.py (Wk4)
```
Agent 3 Agent 3 — Session Hardening backend/core/auth.py — shorter
session tokens for enterprise
```
auth.py (Wk4)
```
Agent 4 Agent 4 — Penetration Test Security penetration test scope
doc
None — fully independent
Day 3: Enterprise compliance documentation — all independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Security Whitepaper docs/compliance/security-
whitepaper.md
None — fully independent
Agent 2 Agent 2 — Enterprise Trust
Page
docs/marketing/enterprise-
trust-and-security.md
None — fully independent
Agent 3 Agent 3 — Vendor Security
Questionnaire
docs/compliance/vendor-
security-questionnaire-
answers.md
None — fully independent
Agent 4 Agent 4 — SOC 2 Readiness docs/compliance/soc2-readiness-
pre-assessment.md
None — fully independent
Day 4: Enterprise frontend features independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 —
Enterprise
Settings
frontend/src/app/dashboard/settings/enterprise/page.tsx dashboard layout
```
(Wk16)
```
Agent 2 Agent 2 — Audit
Log Export UI
frontend/src/components/dashboard/AuditLogExport.tsx UI primitives
```
(Wk15)
```
Agent 3 Agent 3 —
Enterprise
Pricing Page
frontend/src/app/pricing/enterprise/page.tsx None — fully
independent
Agent 4 Agent 4 —
Contract Billing
UI
frontend/src/components/dashboard/ContractBilling.tsx UI primitives
```
(Wk15)
```
Day 5: Enterprise pre-assessment tests — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — SSO Stub
Tests
```
tests/unit/test_sso_stub.py sso.py stub (Day 1)
```
Agent 2 Agent 2 — Audit Export
Tests
```
tests/unit/test_audit_export.py audit export (Day 2)
```
Agent 3 Agent 3 — Enterprise
Billing Tests
```
tests/unit/test_enterprise_billing.py enterprise billing (Day
```
```
1)
```
Agent 4 Agent 4 — Security
Hardening Tests
tests/integration/test_enterprise_security.py Security hardening
```
(Days 1-2)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Enterprise readiness pre-check. SSO stub returns correct response. Audit log CSV export contains all required
fields. Enterprise billing creates contract invoice. IP allowlist blocks non-whitelisted IPs. Run: pytest
tests/unit/test_sso_stub.py + test_audit_export.py + test_enterprise_security.py.
Week Complete When All Pass:
1 SSO stub: returns correct SAML placeholder response
2 Audit log CSV: exports all required fields
3 Enterprise billing: contract invoice generated correctly
4 IP allowlist: non-whitelisted IP blocked
5 Day 6: enterprise pre-preparation gate passed
Week 39 — Integration, Testing & Launch
Goal for This Week
Weeks 1-40 final production readiness preparation. Fix all outstanding issues found in previous weeks, complete
documentation, final security audit.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Outstanding issue fixes — independent per area
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Backend Fixes Fix all non-critical backend
issues from Wks 19-38
Full backend
Agent 2 Agent 2 — Frontend Fixes Fix all non-critical frontend
issues from Wks 15-34
Full frontend
Agent 3 Agent 3 — Agent Fixes Fix all non-critical agent
issues from Wks 9-14
All variants
Agent 4 Agent 4 — Monitoring Fixes Fix all monitoring gaps found
in Wks 14-37
monitoring/
Day 2: Final documentation — all independent
Day 2 Agent File to Build Depends On
```
Agent 1 Agent 1 — Complete README README.md (final complete
```
```
version)
```
None — fully independent
```
Agent 2 Agent 2 — API Docs docs/api/openapi.json (final
```
```
complete)
```
All API routes
Agent 3 Agent 3 — Deployment Guide docs/deployment/production-
```
deployment-guide.md (final)
```
None — fully independent
Agent 4 Agent 4 — New Dev
Onboarding
docs/new-developer-
onboarding.md
None — fully independent
Day 3: Final security audit — independent scan types
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Final OWASP Scan Final OWASP ZAP scan — zero
findings required
Full backend
Agent 2 Agent 2 — Final CVE Scan Final snyk scan — zero critical
CVEs required
All Dockerfiles
Agent 3 Agent 3 — Final RLS Test 500 cross-tenant isolation
tests at 50-client scale
```
rls_policies.sql (Wk3)
```
Agent 4 Agent 4 — Final Secrets Audit Final secrets scan — no
hardcoded credentials anywhere
None — fully independent
Day 4: Final performance benchmarks — independent per metric
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Final Load Test locust — 100 concurrent users,
P95 <300ms target
```
test_load.py (Wk14)
```
Agent 2 Agent 2 — Final Token Usage Verify Light tier >92%, token
budget respected
```
router.py (Wk35)
```
Agent 3 Agent 3 — Final Cache Test Verify Redis cache hit rate
>75%
```
cache.py (Wk26)
```
Agent 4 Agent 4 — Final AL Accuracy Final Agent Lightning accuracy
```
report (target 94%)
```
```
accuracy_tracker.py (Wk13)
```
Day 5: Production readiness checklist — all independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Infrastructure
Checklist
docs/deployment/infrastructure-
production-checklist.md
None — fully independent
Agent 2 Agent 2 — Security Checklist docs/security/security-
production-checklist.md
None — fully independent
Agent 3 Agent 3 — Performance
Checklist
docs/operations/performance-
production-checklist.md
None — fully independent
Agent 4 Agent 4 — PROJECT_STATE
Update
```
PROJECT_STATE.md (Weeks 1-40
```
```
production ready)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Weeks 1-40 production readiness gate. This is the go/no-go for first paying enterprise client. All must pass:
OWASP clean, zero critical CVEs, 500 RLS isolation tests pass, P95 <300ms at 100 concurrent, Agent Lightning
≥94%, cache hit >75%, Light tier >92%, all 3 variants functional. Run full test suite: pytest tests/.
Week Complete When All Pass:
1 OWASP: clean. CVEs: zero critical
2 RLS: 500 cross-tenant isolation tests — 0 leaks
3 P95 <300ms at 100 concurrent users
4 Agent Lightning: ≥94% accuracy
5 Full test suite: 100% pass rate
6 Day 6: Weeks 1-40 production readiness gate PASSED
Week 40 — Integration, Testing & Launch
Goal for This Week
Weeks 1-40 final validation week. Run the complete production readiness checklist end-to-end. First enterprise
client demo preparation.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Final complete test suite run — all independent categories
Day 1 Agent File to Build Depends On
```
Agent 1 Agent 1 — Unit Suite pytest tests/unit/ (complete —
```
```
100% target)
```
All unit tests
Agent 2 Agent 2 — Integration Suite pytest tests/integration/
```
(complete)
```
All integration tests
```
Agent 3 Agent 3 — E2E Suite pytest tests/e2e/ (complete) All e2e tests
```
Agent 4 Agent 4 — Performance Suite pytest tests/performance/
```
(complete)
```
All performance tests
Day 2: Demo environment setup — independent per demo area
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Demo Data database/seeds/enterprise-demo-
data.sql
```
schema.sql (Wk2)
```
Agent 2 Agent 2 — Demo Scenarios docs/sales/enterprise-demo-
scenarios.md
None — fully independent
Agent 3 Agent 3 — Demo Environment docker-compose.demo.yml docker-compose.prod.yml
```
(Wk2)
```
Agent 4 Agent 4 — Demo Script docs/sales/enterprise-demo-
script.md
None — fully independent
Day 3: Staging environment final validation — independent checks
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Staging Deploy Deploy complete stack to
staging environment
```
All Dockerfiles (Wks 2-37)
```
Agent 2 Agent 2 — Staging Smoke Test Run all E2E tests against
```
staging (not local)
```
All e2e tests
Agent 3 Agent 3 — Staging Load Test Load test against staging — 100
concurrent users
```
test_load.py (Wk14)
```
Agent 4 Agent 4 — Staging Security
Scan
Final OWASP scan against
staging environment
None — fully independent
Day 4: Enterprise demo dry run — independent per scenario
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Onboarding Demo Run 10-minute onboarding demo
end-to-end
```
Demo environment (Day 2)
```
Agent 2 Agent 2 — Approval Demo Run refund approval workflow
demo
```
Demo environment (Day 2)
```
```
Agent 3 Agent 3 — Jarvis Demo Run Jarvis command demo Demo environment (Day 2)
```
Agent 4 Agent 4 — Analytics Demo Run ROI + accuracy dashboard
demo
```
Demo environment (Day 2)
```
Day 5: Weeks 1-40 completion docs — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Final Production
Report
docs/milestone-reports/weeks-1-
40-complete.md
None — fully independent
Agent 2 Agent 2 — First Client Prep
Checklist
docs/sales/first-enterprise-
client-checklist.md
None — fully independent
Agent 3 Agent 3 — Investor Update
Draft
docs/business/wk40-investor-
update.md
None — fully independent
Agent 4 Agent 4 — PROJECT_STATE
Final
```
PROJECT_STATE.md (Weeks 1-40
```
```
complete — enterprise ready)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Weeks 1-40 FINAL gate. Staging environment must pass all tests. Demo must run without errors. All production
checklists marked complete. This gate must pass before any enterprise client contract is signed.
Week Complete When All Pass:
1 Staging: all E2E tests pass against staging environment
2 Staging: P95 <300ms under load test
3 Demo: all 4 demo scenarios run without errors
4 All production checklists: 100% complete
5 Day 6: Weeks 1-40 FINAL gate PASSED — enterprise ready
Phase 9 — Cloud Migration & Infrastructure
```
Replace Railway/Vercel with real cloud. Terraform files are independent; K8s manifests are independent. Built in parallel per
```
layer.
Week 41 — Cloud Migration & Infrastructure
Goal for This Week
Cloud migration Week 1: account setup, VPC, K8s cluster, container registry. Terraform files for networking,
cluster, and registry are fully independent — build simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Cloud provider selection and account setup — parallel Terraform foundations
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Provider Config infra/cloud/README.md +
infra/terraform/providers.tf
None — fully independent
Agent 2 Agent 2 — Networking infra/terraform/networking.tf
```
(VPC, subnets, security groups)
```
None — fully independent
```
Agent 3 Agent 3 — IAM infra/terraform/iam.tf (service
```
```
accounts, roles, policies)
```
None — fully independent
Agent 4 Agent 4 — Container Registry infra/terraform/registry.tf
```
(ECR/GCR/ACR)
```
None — fully independent
Day 2: K8s cluster and managed DB — independent of registry
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — K8s Cluster infra/terraform/eks.tf / gke.tf
```
/ aks.tf (one per provider)
```
```
networking.tf (Day 1)
```
Agent 2 Agent 2 — Managed
PostgreSQL
infra/terraform/database.tf
```
(managed cloud PostgreSQL)
```
```
networking.tf (Day 1)
```
Agent 3 Agent 3 — Managed Redis infra/terraform/redis.tf
```
(managed cloud Redis)
```
```
networking.tf (Day 1)
```
Agent 4 Agent 4 — Cloud Provider
Abstraction
infra/cloud/provider_config.py
— swap via env var
None — fully independent
Day 3: K8s ingress and cert manager — independent of database
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — K8s Namespace infra/kubernetes/namespace.yaml
```
(activate)
```
```
K8s cluster (Day 2)
```
Agent 2 Agent 2 — Ingress Controller infra/kubernetes/ingress/ingress-
controller.yaml
```
K8s cluster (Day 2)
```
Agent 3 Agent 3 — Cert Manager infra/kubernetes/ingress/cert-
```
manager.yaml (TLS auto)
```
```
K8s cluster (Day 2)
```
Agent 4 Agent 4 — K8s Secrets infra/kubernetes/secrets/
```
(ExternalSecret from cloud vault)
```
```
K8s cluster, IAM (Days 1-2)
```
Day 4: GitHub Actions for Terraform — independent of K8s
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Terraform CI
Workflow
.github/workflows/terraform-
apply.yml
None — fully independent
Agent 2 Agent 2 — Deploy Backend
Workflow
.github/workflows/deploy-
```
backend.yml (update for cloud
```
```
K8s)
```
None — fully independent
Agent 3 Agent 3 — Deploy Frontend
Workflow
.github/workflows/deploy-
```
frontend.yml (update for cloud)
```
None — fully independent
Agent 4 Agent 4 — Deploy Worker
Workflow
.github/workflows/deploy-
worker.yml
None — fully independent
Day 5: Cloud migration test files — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Terraform
Validate
Run terraform validate + terraform plan
```
(review)
```
All terraform files
```
(Days 1-4)
```
Agent 2 Agent 2 — Cloud
Connectivity Test
```
tests/integration/test_cloud_connectivity.py All cloud setup (Days
```
```
1-4)
```
Agent 3 Agent 3 — Migration
Checklist
infra/cloud/migration-checklist.md None — fully
independent
Agent 4 Agent 4 — Cost
Calculator
infra/cloud/cost-calculator.md None — fully
independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Cloud migration Week 1 test. Run terraform apply → K8s cluster created → namespace active → ingress
controller running → cert manager issues test certificate → managed PostgreSQL accessible from K8s →
managed Redis accessible from K8s. All connectivity tests pass.
Week Complete When All Pass:
1 terraform apply: K8s cluster created without errors
2 Managed PostgreSQL: accessible from K8s pod
3 Managed Redis: accessible from K8s pod
4 Cert manager: test TLS certificate issued
5 Day 6: cloud Week 1 infrastructure validated
Week 42 — Cloud Migration & Infrastructure
Goal for This Week
Cloud migration Week 2: deploy all services to K8s. Backend, worker, MCP deployment YAMLs are independent
of each other — build simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Kubernetes deployment manifests — independent per service
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Backend
Deployment
infra/kubernetes/backend-
deployment.yaml + backend-
service.yaml
```
namespace.yaml (Wk41)
```
Agent 2 Agent 2 — Worker Deployment infra/kubernetes/worker-
deployment.yaml + worker-
service.yaml
```
namespace.yaml (Wk41)
```
Agent 3 Agent 3 — MCP Deployment infra/kubernetes/mcp-
deployment.yaml + mcp-
service.yaml
```
namespace.yaml (Wk41)
```
Agent 4 Agent 4 — K8s Migration Job infra/kubernetes/jobs/migration-
job.yaml
```
namespace.yaml (Wk41)
```
Day 2: Autoscaling configs — independent per service
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Backend HPA infra/kubernetes/autoscaling/hpa.yaml
```
(2→10 pods)
```
backend-deployment.yaml
```
(Day 1)
```
Agent 2 Agent 2 — Worker KEDA infra/kubernetes/autoscaling/keda-
```
worker.yaml (queue-based)
```
worker-deployment.yaml
```
(Day 1)
```
Agent 3 Agent 3 — Backend Ingress infra/kubernetes/ingress/backend-
ingress.yaml + TLS
ingress-controller.yaml
```
(Wk41)
```
Agent 4 Agent 4 — Updated
Dockerfiles
infra/docker/ — update all
Dockerfiles for cloud registry
```
All Dockerfiles (Wk18)
```
Day 3: Build and push Docker images — independent per image
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Build Backend
Image
docker build + push backend to
cloud registry
```
backend.Dockerfile (Wk18)
```
Agent 2 Agent 2 — Build Worker Image docker build + push worker to
cloud registry
```
worker.Dockerfile (Wk18)
```
Agent 3 Agent 3 — Build MCP Image docker build + push mcp to
cloud registry
```
mcp.Dockerfile (Wk18)
```
Agent 4 Agent 4 — Image Scan snyk container test all 3
images
```
All images (Day 3 — wait)
```
Day 4: Deploy to K8s and run migration — dependent on images being pushed
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Run Migration Job kubectl apply migration-
job.yaml → alembic upgrade head
on cloud DB
```
migration-job.yaml (Day 1),
```
```
images (Day 3)
```
Agent 2 Agent 2 — Deploy Backend kubectl apply backend-
deployment.yaml
```
migration done (Day 4 —
```
```
wait), backend image (Day 3)
```
Agent 3 Agent 3 — Deploy Worker kubectl apply worker-
deployment.yaml
```
backend deployed (Day 4 —
```
```
wait), worker image (Day 3)
```
Agent 4 Agent 4 — Deploy MCP kubectl apply mcp-
deployment.yaml
```
mcp image (Day 3)
```
Day 5: Cloud backend validation tests — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Cloud
Health Check
tests/integration/test_cloud_backend_health.py All services deployed
```
(Day 4)
```
Agent 2 Agent 2 — Cloud API
Tests
```
Run E2E tests against cloud backend (not
```
```
local)
```
All services deployed
```
(Day 4)
```
Agent 3 Agent 3 — Cloud Load
Test
locust against cloud backend — 100 concurrent
users
All services deployed
```
(Day 4)
```
Agent 4 Agent 4 — Cloud
Migration Report
```
infra/cloud/migration-checklist.md (update) None — fully
```
independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Cloud migration Week 2 gate. All services running on K8s. Run: kubectl get pods — all pods Running. Cloud
health check: /health returns 200. Cloud E2E: all tests pass. Cloud load test: P95 <500ms. DB migrations
applied. HPA: backend scales under load.
Week Complete When All Pass:
1 All K8s pods in Running state
2 Cloud /health endpoint returns 200
3 Cloud E2E tests: all pass
4 Cloud load test: P95 <500ms
5 HPA: backend scales under load
6 Day 6: cloud Week 2 all services deployed and validated
Week 43 — Cloud Migration & Infrastructure
Goal for This Week
```
Cloud migration Week 3: frontend to cloud, CDN, 3 environments (dev/staging/prod). Each environment and CDN
```
config is independent.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Frontend deployment to cloud — independent of backend
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Frontend
Deployment
infra/kubernetes/frontend-
deployment.yaml + frontend-
service.yaml
```
namespace.yaml (Wk41)
```
Agent 2 Agent 2 — Frontend Ingress infra/kubernetes/ingress/frontend-
ingress.yaml + TLS
ingress-controller.yaml
```
(Wk41)
```
Agent 3 Agent 3 — Build Frontend
Image
docker build + push frontend to
cloud registry
```
frontend.Dockerfile (Wk18)
```
```
Agent 4 Agent 4 — CDN Config infra/terraform/cdn.tf + dns.tf networking.tf (Wk41)
```
Day 2: 3-environment setup — environments are independent of each other
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Dev Namespace infra/kubernetes/environments/dev-
namespace.yaml
```
namespace.yaml (Wk41)
```
Agent 2 Agent 2 — Staging
Namespace
infra/kubernetes/environments/staging-
namespace.yaml
```
namespace.yaml (Wk41)
```
Agent 3 Agent 3 — Prod
Namespace
infra/kubernetes/environments/prod-
namespace.yaml
```
namespace.yaml (Wk41)
```
Agent 4 Agent 4 — Environment
Setup Script
```
infra/scripts/setup-environments.sh All 3 namespaces (Day 2
```
```
— wait)
```
Day 3: Next.js config updates and CDN integration — independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Next.js Cloud
Config
frontend/next.config.js —
update for cloud CDN URLs
```
next.config.js (Wk15)
```
Agent 2 Agent 2 — Static Asset CDN Configure Next.js to serve
static assets via CDN
```
cdn.tf (Day 1)
```
Agent 3 Agent 3 — Deploy Frontend
Workflow
.github/workflows/deploy-
```
frontend.yml (update for cloud)
```
frontend-deployment.yaml
```
(Day 1)
```
Agent 4 Agent 4 — Environment
Variables
Update all .env per environment
```
(dev/staging/prod)
```
```
All 3 namespaces (Day 2)
```
Day 4: PR preview environments and branch deployments — independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — PR Preview
Workflow
.github/workflows/preview-
deploy.yml
None — fully independent
Agent 2 Agent 2 — Auto-destroy
Preview
.github/workflows/preview-
cleanup.yml
None — fully independent
Agent 3 Agent 3 — Staging Auto-deploy .github/workflows/deploy-
```
backend.yml (add staging auto-
```
```
deploy)
```
None — fully independent
Agent 4 Agent 4 — Prod Deploy Gate .github/workflows/deploy-
```
backend.yml (add manual
```
```
approval for prod)
```
None — fully independent
Day 5: Frontend cloud validation tests — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Frontend Cloud
E2E
tests/e2e/test_frontend_cloud.py
```
(against cloud URL)
```
```
Frontend deployed (Day
```
```
1)
```
```
Agent 2 Agent 2 — CDN Cache Test tests/performance/test_cdn_cache.py CDN config (Day 1)
```
Agent 3 Agent 3 — 3-Environment
Test
tests/integration/test_environments.py
```
(dev/staging/prod isolated)
```
```
All 3 environments (Day
```
```
2)
```
```
Agent 4 Agent 4 — PR Preview Test tests/integration/test_pr_preview.py Preview workflows (Day
```
```
4)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
```
Cloud Week 3 gate. Frontend served from cloud CDN. All 3 environments isolated (dev/staging/prod). CDN
```
cache hit rate >80%. PR preview deployment works. Lighthouse score >90 from cloud URL. Run: pytest
tests/e2e/test_frontend_cloud.py + tests/integration/test_environments.py.
Week Complete When All Pass:
1 Frontend: served from cloud CDN with TLS
2 CDN cache hit rate: >80%
3 3 environments: dev/staging/prod all isolated
4 PR preview: new preview URL on every PR
5 Day 6: cloud Week 3 frontend + 3 environments validated
Week 44 — Cloud Migration & Infrastructure
Goal for This Week
Cloud migration Week 4: object storage, centralised logging, automated backups. All Terraform files independent
— build simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Storage and logging Terraform files independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Object Storage infra/terraform/storage.tf
```
(cloud object storage, one
```
```
bucket per client)
```
```
networking.tf (Wk41)
```
Agent 2 Agent 2 — Centralised Logging infra/terraform/logging.tf
```
(cloud log aggregation 90-day
```
```
retention)
```
```
networking.tf (Wk41)
```
Agent 3 Agent 3 — Alerting Config infra/terraform/alerting.tf
```
(cloud-native alerts)
```
```
networking.tf (Wk41)
```
Agent 4 Agent 4 — Backup Config infra/terraform/backup.tf
```
(daily DB snapshots, 30-day
```
```
retention)
```
```
database.tf (Wk41)
```
Day 2: FluentD and backup CronJob — independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — FluentD
DaemonSet
infra/kubernetes/logging/fluentd-
daemonset.yaml
```
K8s cluster (Wk41)
```
Agent 2 Agent 2 — PG Backup
CronJob
infra/kubernetes/backup/pg-backup-
cronjob.yaml
```
K8s cluster (Wk41)
```
Agent 3 Agent 3 — Storage Client
Update
shared/utils/storage.py — update to
use cloud object storage
```
storage.tf (Day 1)
```
Agent 4 Agent 4 — Log Shipping
Test
tests/integration/test_log_shipping.py fluentd-daemonset.yaml
```
(Day 2 — wait)
```
Day 3: Backup verification and restore tests — independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Backup
Verification
tests/integration/test_backup_restore.py pg-backup-
```
cronjob.yaml (Day
```
```
2)
```
Agent 2 Agent 2 — Storage
Isolation Test
```
tests/integration/test_client_storage_isolation.py storage.tf (Day 1)
```
Agent 3 Agent 3 — Log
Retention Test
```
tests/integration/test_log_retention.py logging.tf (Day 1)
```
Agent 4 Agent 4 — Disaster
Recovery Doc
docs/infrastructure/disaster-recovery-runbook.md None — fully
independent
Day 4: Cloud migration completion verification — independent checks
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Full
Cloud E2E
```
Run complete test suite against cloud (all
```
```
services)
```
All cloud services
```
(Wks 41-44)
```
Agent 2 Agent 2 — Cloud
Security Scan
OWASP scan against cloud endpoints All cloud services
```
(Wks 41-44)
```
Agent 3 Agent 3 — Cloud
Cost Review
```
infra/cloud/cost-calculator.md (final actual
```
```
costs)
```
None — fully
independent
Agent 4 Agent 4 — ADR
Cloud Doc
docs/architecture_decisions/006_cloud_migration.md
```
(complete)
```
None — fully
independent
Day 5: Cloud migration completion docs — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Migration Complete
Report
infra/cloud/migration-
```
checklist.md (final, all
```
```
ticked)
```
None — fully independent
Agent 2 Agent 2 — Cloud Architecture
Diagram
docs/architecture/cloud-
architecture.md
None — fully independent
Agent 3 Agent 3 — Railway/Vercel
Decommission
docs/infrastructure/old-infra-
decommission.md
None — fully independent
Agent 4 Agent 4 — PROJECT_STATE
Update
```
PROJECT_STATE.md (Phase 9 cloud
```
```
migration complete)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Cloud migration FINAL gate. All 4 Terraform modules applied. FluentD shipping logs to cloud. Backup CronJob
runs and backup verifiable. Object storage: per-client isolation confirmed. Full E2E test suite passes against
cloud. OWASP clean on cloud endpoints. This completes Phase 9.
Week Complete When All Pass:
1 FluentD: logs appearing in cloud logging within 30 seconds
2 Backup: PG backup restores successfully
3 Object storage: client isolation confirmed
4 Full E2E: all tests pass against cloud URLs
5 Day 6: cloud migration Phase 9 COMPLETE
Phase 10 — Payment Localisation
Unlock the Indian market with Razorpay, multi-currency billing, GST/VAT tax, and dunning. Payment provider files and tax
files are fully independent.
Week 45 — Payment Localisation
Goal for This Week
Razorpay integration and multi-currency billing. Razorpay client, currency utility, and migration are all
independent of each other — build simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: All 4 payment foundation files independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 —
Razorpay Client
shared/integrations/razorpay_client.py config.py, logger.py
```
(Wk1)
```
Agent 2 Agent 2 —
Currency Utility
```
shared/utils/currency.py (exchange rate fetch,
```
```
format_currency)
```
config.py, cache.py
```
(Wks 1-2)
```
Agent 3 Agent 3 — DB
Migration 011
database/migrations/versions/011_multi_currency.py 001_initial_schema.py
```
(Wk2)
```
Agent 4 Agent 4 —
Razorpay
Terraform
```
infra/terraform/tax.tf (Razorpay API key in
```
```
secrets manager)
```
```
networking.tf (Wk41)
```
Day 2: Razorpay webhook and billing service updates — independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Razorpay
Webhook
```
backend/api/webhooks/razorpay.py hmac_verification.py (Wk3),
```
```
razorpay_client.py (Day 1)
```
Agent 2 Agent 2 — Billing Service
Update
backend/services/billing_service.py
— add Razorpay subscription flow
```
billing_service.py (Wk4),
```
```
razorpay_client.py (Day 1)
```
Agent 3 Agent 3 — Multi-Currency
Pricing
backend/services/billing_service.py
```
— pricing engine (INR/GBP/EUR/USD)
```
```
currency.py (Day 1)
```
Agent 4 Agent 4 — Billing API
Update
backend/api/billing.py — add
currency parameter to endpoints
```
billing.py (Wk4)
```
Day 3: Frontend billing updates — independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Billing
Settings UI
frontend/src/app/dashboard/settings/billing/page.tsx
— add Razorpay
billing settings
```
(Wk17)
```
Agent 2 Agent 2 —
Currency Selector
frontend/src/components/common/CurrencySelector.tsx UI primitives
```
(Wk15)
```
Agent 3 Agent 3 — Pricing
Page INR
frontend/src/app/pricing/page.tsx — add INR pricing
tier
pricing page
```
(Wk17)
```
Agent 4 Agent 4 — Invoice
Model
```
backend/models/invoice.py database.py (Wk2)
```
Day 4: Razorpay MCP server and tests — independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Razorpay
MCP
```
mcp_servers/integrations/razorpay_server.py base_server.py (Wk8),
```
```
razorpay_client.py (Day
```
```
1)
```
Agent 2 Agent 2 — Razorpay
Client Tests
```
tests/unit/test_razorpay_client.py razorpay_client.py (Day
```
```
1)
```
Agent 3 Agent 3 — Currency
Tests
```
tests/unit/test_currency.py currency.py (Day 1)
```
Agent 4 Agent 4 — Billing Multi-
Currency Tests
tests/unit/test_billing_multi_currency.py billing service update
```
(Day 2)
```
Day 5: Razorpay integration tests — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Razorpay
Webhook Test
```
tests/integration/test_razorpay_webhook.py razorpay webhook (Day
```
```
2)
```
Agent 2 Agent 2 — Multi-
Currency E2E Test
tests/e2e/test_multi_currency_billing.py All currency features
```
(Days 1-3)
```
Agent 3 Agent 3 — INR Pricing
Test
```
tests/integration/test_inr_pricing.py INR pricing (Day 3)
```
Agent 4 Agent 4 — Tax Legal
Doc Update
legal/tax_compliance.md None — fully
independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
```
Payment localisation Week 1 gate. Razorpay: create subscription (mocked) → webhook received → HMAC
```
verified → subscription activated. Multi-currency: INR price calculated correctly. Currency cache: exchange rate
cached in Redis. Run: pytest tests/integration/test_razorpay_webhook.py + test_multi_currency_billing.py.
Week Complete When All Pass:
```
1 Razorpay: subscription flow works end-to-end (mocked)
```
2 Razorpay webhook: HMAC verification works
3 INR pricing: correct price calculated and displayed
4 Currency cache: exchange rate cached, refreshes every 1 hour
5 Day 6: Razorpay + multi-currency Week 1 validated
Week 46 — Payment Localisation
Goal for This Week
```
Tax handling (GST/VAT/US state tax), dunning management, and PDF invoice generation. All three are
```
completely independent of each other.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Tax service, dunning service, and invoice service — all independent
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Tax Service backend/services/tax_service.py
```
(GST 18% India, VAT 20% UK/EU,
```
```
TaxJar US)
```
config.py, billing_service.py
```
(Wks 1-4)
```
Agent 2 Agent 2 — Dunning Service backend/services/dunning_service.py
```
(Day1/3+email/7+warning/14 suspend)
```
```
billing_service.py (Wk4)
```
Agent 3 Agent 3 — Invoice Service backend/services/invoice_service.py
```
(PDF generation)
```
```
invoice model (Wk45)
```
```
Agent 4 Agent 4 — Dunning Worker workers/dunning_worker.py (daily
```
```
retry schedule)
```
```
dunning_service.py (Day 1
```
```
— wait)
```
Day 2: Tax API endpoint, invoice API, and dunning notifications — independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Tax API backend/api/billing.py — add
/tax/calculate endpoint
```
tax_service.py (Day 1)
```
Agent 2 Agent 2 — Invoice API backend/api/billing.py — add
/invoices/:id/pdf endpoint
```
invoice_service.py (Day 1)
```
Agent 3 Agent 3 — Dunning
Notification
workers/dunning_worker.py — add email
templates per retry day
```
dunning_worker.py (Day 1)
```
Agent 4 Agent 4 — Invoice Email
Template
backend/services/notification_service.py
— add invoice email
notification_service.py
```
(Wk4)
```
Day 3: Frontend tax and invoice UI — independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Tax
Display UI
frontend/src/components/dashboard/TaxBreakdown.tsx UI primitives
```
(Wk15)
```
Agent 2 Agent 2 — Invoice
Download UI
frontend/src/components/dashboard/InvoiceDownload.tsx UI primitives
```
(Wk15)
```
Agent 3 Agent 3 —
Dunning Banner
UI
frontend/src/components/dashboard/DunningBanner.tsx UI primitives
```
(Wk15)
```
Agent 4 Agent 4 — Legal
Tax Doc
```
legal/tax_compliance.md (complete per jurisdiction) None — fully
```
independent
Day 4: Tax and dunning tests — independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Tax Service Tests tests/unit/test_tax_service.py
```
(GST/VAT/US)
```
```
tax_service.py (Day 1)
```
Agent 2 Agent 2 — Dunning Tests tests/unit/test_dunning_service.py
```
(retry schedule)
```
```
dunning_service.py (Day 1)
```
Agent 3 Agent 3 — Invoice Tests tests/unit/test_invoice_service.py
```
(PDF content)
```
```
invoice_service.py (Day 1)
```
Agent 4 Agent 4 — Dunning Worker
Tests
```
tests/unit/test_dunning_worker.py dunning_worker.py (Day 1)
```
Day 5: Tax and payment E2E tests — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — GST E2E Test tests/e2e/test_gst_billing.py
```
(Indian client full flow)
```
tax_service.py,
```
invoice_service.py (Days 1-
```
```
2)
```
Agent 2 Agent 2 — VAT E2E Test tests/e2e/test_vat_billing.py
```
(UK client full flow)
```
```
tax_service.py (Day 1)
```
Agent 3 Agent 3 — Dunning E2E Test tests/e2e/test_dunning_flow.py
```
(Day1→Day14 simulate)
```
dunning_service.py,
```
dunning_worker.py (Days 1-
```
```
2)
```
Agent 4 Agent 4 — PROJECT_STATE
Update
```
PROJECT_STATE.md (Phase 10
```
```
payment localisation complete)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
```
Payment localisation FINAL gate (Phase 10). GST: Indian client invoice shows 18% GST. VAT: UK client invoice
```
```
shows 20% VAT. Dunning: Day 1 retry → Day 3 email → Day 7 warning → Day 14 suspension (simulated). PDF
```
```
invoice: downloads with correct tax breakdown. Run: pytest tests/e2e/test_gst_billing.py + test_dunning_flow.py.
```
Week Complete When All Pass:
1 GST: Indian client invoice shows 18% GST correctly
2 VAT: UK client invoice shows 20% VAT correctly
3 Dunning: all 4 retry stages fire at correct intervals
4 PDF invoice: contains correct tax entity details
5 Day 6: Phase 10 payment localisation COMPLETE
```
Phase 11 — Mobile App (iOS + Android)
```
One React Native codebase for iOS and Android. Screens, components, and services are independent within each day.
```
Week 47 — Mobile App (iOS + Android)
```
Goal for This Week
React Native + Expo project setup, navigation, auth screens, and API client. All foundation files are independent
— build simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Mobile project config and navigation — independent foundations
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Expo Config mobile/package.json + app.config.ts +
eas.json
None — fully independent
```
Agent 2 Agent 2 — App Navigator mobile/src/navigation/AppNavigator.tsx package.json (Day 1 —
```
```
wait)
```
```
Agent 3 Agent 3 — Auth Navigator mobile/src/navigation/AuthNavigator.tsx package.json (Day 1 —
```
```
wait)
```
Agent 4 Agent 4 — Main Navigator
```
(5 tabs)
```
```
mobile/src/navigation/MainNavigator.tsx package.json (Day 1 —
```
```
wait)
```
Day 2: Mobile UI primitives — all independent of each other
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Mobile
Button+Input
mobile/src/components/ui/Button.tsx
- Input.tsx
```
package.json (Day 1)
```
Agent 2 Agent 2 — Mobile
Card+Badge
mobile/src/components/ui/Card.tsx +
Badge.tsx
```
package.json (Day 1)
```
```
Agent 3 Agent 3 — Mobile Toast mobile/src/components/ui/Toast.tsx package.json (Day 1)
```
```
Agent 4 Agent 4 — Mobile API Client mobile/src/lib/api.ts + supabase.ts package.json (Day 1)
```
Day 3: Auth screens — independent of each other
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Login
Screen
```
mobile/src/screens/auth/LoginScreen.tsx UI primitives (Day 2)
```
Agent 2 Agent 2 — Register
Screen
```
mobile/src/screens/auth/RegisterScreen.tsx UI primitives (Day 2)
```
Agent 3 Agent 3 — Forgot
Password Screen
```
mobile/src/screens/auth/ForgotPasswordScreen.tsx UI primitives (Day 2)
```
Agent 4 Agent 4 — Mobile
Zustand Stores
mobile/src/stores/agentStore.ts + ticketStore.ts
- uiStore.ts
None — fully
independent
Day 4: Mobile hooks — all independent of each other
Day 4 Agent File to Build Depends On
```
Agent 1 Agent 1 — useAuth Hook mobile/src/hooks/useAuth.ts api.ts, agentStore.ts (Days
```
```
2-3)
```
```
Agent 2 Agent 2 — useTickets Hook mobile/src/hooks/useTickets.ts api.ts, ticketStore.ts (Days
```
```
2-3)
```
Agent 3 Agent 3 — useApprovals
Hook
```
mobile/src/hooks/useApprovals.ts api.ts, ticketStore.ts (Days
```
```
2-3)
```
Agent 4 Agent 4 — useAgentStatus
Hook
```
mobile/src/hooks/useAgentStatus.ts api.ts, agentStore.ts (Days
```
```
2-3)
```
Day 5: Mobile foundation tests — independent
Day 5 Agent File to Build Depends On
```
Agent 1 Agent 1 — Navigation Tests mobile/__tests__/navigation.test.tsx All navigators (Day 1)
```
Agent 2 Agent 2 — Auth Screen
Tests
```
mobile/__tests__/auth.test.tsx Auth screens (Day 3)
```
```
Agent 3 Agent 3 — API Client Tests mobile/__tests__/api.test.ts api.ts (Day 2)
```
Agent 4 Agent 4 — GitHub Actions
Mobile
.github/workflows/build-mobile.yml
```
(EAS Build)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Mobile foundation test. Run on Expo Go or simulator. Auth screens render. Login connects to backend API and
receives JWT. Navigation: all 5 tabs accessible. Stores initialise. API client makes authenticated request. Run:
npm test in mobile/. EAS Build workflow triggers without errors.
Week Complete When All Pass:
1 Login screen: connects to backend, JWT received
2 Navigation: all 5 tabs accessible without errors
3 All Zustand stores: initialise without errors
4 EAS Build: workflow triggers successfully
5 Day 6: mobile foundation validated
```
Week 48 — Mobile App (iOS + Android)
```
Goal for This Week
```
Mobile core screens: dashboard, approvals (swipe), Jarvis (voice), agents. All screens independent of each other
```
— build simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Dashboard and approval screens — independent
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Home
Screen
mobile/src/screens/dashboard/HomeScreen.tsx UI primitives
```
(Wk47)
```
Agent 2 Agent 2 —
Approvals Screen
```
mobile/src/screens/approvals/ApprovalsScreen.tsx (swipe
```
```
right=approve)
```
UI primitives
```
(Wk47)
```
Agent 3 Agent 3 — Ticket
Detail Screen
mobile/src/screens/approvals/TicketDetailScreen.tsx UI primitives
```
(Wk47)
```
Agent 4 Agent 4 —
Swipeable
Refund Card
mobile/src/components/approvals/SwipeableRefundCard.tsx
```
(haptic)
```
UI primitives
```
(Wk47)
```
Day 2: Jarvis and agents screens — independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Jarvis
Screen
mobile/src/screens/jarvis/JarvisScreen.tsx UI primitives
```
(Wk47)
```
Agent 2 Agent 2 — Voice
Command Button
mobile/src/components/jarvis/VoiceCommandButton.tsx
```
(hold-to-speak)
```
UI primitives
```
(Wk47)
```
Agent 3 Agent 3 — Agents
List Screen
mobile/src/screens/agents/AgentsScreen.tsx UI primitives
```
(Wk47)
```
Agent 4 Agent 4 — Agent
Detail Screen
mobile/src/screens/agents/AgentDetailScreen.tsx UI primitives
```
(Wk47)
```
Day 3: Additional approval components — independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Batch
Selector
```
mobile/src/components/approvals/BatchSelector.tsx UI primitives (Wk47)
```
Agent 2 Agent 2 —
Confidence Bar
```
mobile/src/components/approvals/ConfidenceBar.tsx UI primitives (Wk47)
```
Agent 3 Agent 3 — Jarvis
Chat Component
```
mobile/src/components/jarvis/JarvisChat.tsx UI primitives (Wk47)
```
Agent 4 Agent 4 —
Dashboard Metrics
Card
```
mobile/src/components/dashboard/MetricsCard.tsx UI primitives (Wk47)
```
Day 4: Push notification backend — independent of frontend
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 —
Device Token
Model
```
backend/models/device_token.py database.py (Wk2)
```
Agent 2 Agent 2 —
Notifications
API
```
backend/api/notifications.py (POST /register-device) device_token model
```
```
(Day 4 — wait)
```
Agent 3 Agent 3 — Push
Service
```
backend/services/notification_service.py (add Expo
```
```
push)
```
notification_service.py
```
(Wk4)
```
Agent 4 Agent 4 —
Approval Alert
Component
```
mobile/src/components/notifications/ApprovalAlert.tsx UI primitives (Wk47)
```
Day 5: Core screen tests — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Swipe
Approval Tests
mobile/__tests__/swipe_approval.test.tsx SwipeableRefundCard.tsx
```
(Day 1)
```
Agent 2 Agent 2 — Voice
Command Tests
mobile/__tests__/voice_command.test.tsx VoiceCommandButton.tsx
```
(Day 2)
```
Agent 3 Agent 3 — Push
Notification Tests
```
tests/unit/test_push_notifications.py notifications API (Day 4)
```
Agent 4 Agent 4 — Batch
Approval Tests
```
mobile/__tests__/batch_approval.test.tsx BatchSelector.tsx (Day 3)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Mobile core screens integration test on real device. Swipe right: approval sent to API. Swipe left: rejection sent.
```
Voice: hold button → speak → Jarvis responds. Push notification: approve from lock screen notification. Batch:
```
select 5 tickets → approve all. Run on iOS Simulator + Android Emulator.
Week Complete When All Pass:
1 Swipe approval: API called correctly on swipe right
2 Voice command: Jarvis response streams back
3 Push notification: approve action from lock screen works
4 Batch approval: all 5 tickets approved in one API call
5 Day 6: mobile core screens validated on device
```
Week 49 — Mobile App (iOS + Android)
```
Goal for This Week
Mobile analytics, knowledge, settings screens, push notifications, and App Store submission. All screens and the
App Store submission are independent.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Remaining screens — all independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 —
Analytics Screen
mobile/src/screens/analytics/AnalyticsScreen.tsx UI primitives
```
(Wk47)
```
Agent 2 Agent 2 —
Knowledge Screen
mobile/src/screens/knowledge/KnowledgeScreen.tsx
```
(camera upload)
```
UI primitives
```
(Wk47)
```
Agent 3 Agent 3 — Settings
Screen
mobile/src/screens/settings/SettingsScreen.tsx UI primitives
```
(Wk47)
```
Agent 4 Agent 4 — Billing
Settings Screen
mobile/src/screens/settings/BillingSettingsScreen.tsx UI primitives
```
(Wk47)
```
Day 2: Push notification full setup — independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Expo
Notifications
```
mobile/src/services/notifications.ts (register
```
```
token, receive)
```
```
package.json (Wk47)
```
Agent 2 Agent 2 — Notification
Permissions
```
mobile/src/hooks/useNotifications.ts notifications.ts (Day 2
```
```
— wait)
```
Agent 3 Agent 3 —
Background
Notifications
```
mobile/src/services/backgroundNotifications.ts notifications.ts (Day 2
```
```
— wait)
```
Agent 4 Agent 4 — Team +
Policies Screens
mobile/src/screens/settings/TeamScreen.tsx +
PoliciesScreen.tsx
```
UI primitives (Wk47)
```
Day 3: App Store assets — independent per platform
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — iOS App
Store Assets
mobile/assets/app-store/ — screenshots, icon,
description
None — fully
independent
Agent 2 Agent 2 — Android
Play Store Assets
mobile/assets/play-store/ — screenshots, icon,
description
None — fully
independent
Agent 3 Agent 3 — App
Store Submission
Guide
docs/mobile/app-store-submission.md None — fully
independent
Agent 4 Agent 4 — Privacy
Policy Mobile
mobile/src/screens/settings/PrivacyPolicyScreen.tsx UI primitives
```
(Wk47)
```
Day 4: EAS Build and submission — independent per platform
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — iOS EAS Build eas build --platform ios
```
(production build)
```
```
eas.json (Wk47)
```
Agent 2 Agent 2 — Android EAS Build eas build --platform android
```
(production build)
```
```
eas.json (Wk47)
```
Agent 3 Agent 3 — iOS TestFlight
Submit
```
eas submit --platform ios (to
```
```
TestFlight)
```
```
iOS build (Day 4 — wait)
```
Agent 4 Agent 4 — Android Internal
Submit
eas submit --platform android
```
(to internal track)
```
```
Android build (Day 4 — wait)
```
Day 5: Mobile final tests and PROJECT_STATE — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Analytics Screen
Tests
```
mobile/__tests__/analytics.test.tsx Analytics screen (Day 1)
```
Agent 2 Agent 2 — Notifications
E2E Test
```
mobile/__tests__/notifications.test.tsx All notification files (Day
```
```
2)
```
Agent 3 Agent 3 — Camera Upload
Test
```
mobile/__tests__/camera_upload.test.tsx Knowledge screen (Day
```
```
1)
```
Agent 4 Agent 4 —
PROJECT_STATE Update
```
PROJECT_STATE.md (Phase 11 mobile
```
```
complete)
```
None — fully
independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Mobile Phase 11 FINAL gate. App submitted to TestFlight and internal track. Push notifications work end-to-end.
Camera document upload sends to backend. All 5 tab screens render with real data. Run full mobile test suite:
npm test in mobile/. This completes Phase 11.
Week Complete When All Pass:
1 iOS app: submitted to TestFlight successfully
2 Android app: submitted to internal track successfully
3 Push notifications: end-to-end on real device
4 Camera upload: document sent to backend KB
5 Day 6: Phase 11 mobile app COMPLETE
Phase 12 — Enterprise SSO
SAML, Okta, Azure AD, SCIM. Each SSO provider implementation is independent of the others.
Week 50 — Enterprise SSO
Goal for This Week
SAML 2.0 SSO foundation. SP metadata, SAML provider, SSO API, frontend SSO page, and DB migration are all
independent of each other.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: SAML foundation files — independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — SAML
Provider
backend/core/sso/saml_provider.py
```
(python3-saml)
```
```
security.py (Wk1)
```
```
Agent 2 Agent 2 — SP Metadata backend/core/sso/metadata.py (XML SP
```
```
metadata)
```
```
config.py (Wk1)
```
Agent 3 Agent 3 — SSO Config
Model
backend/models/sso_config.py
```
(sso_configs table)
```
```
database.py (Wk2)
```
Agent 4 Agent 4 — DB Migration
012
database/migrations/versions/012_sso.py 001_initial_schema.py
```
(Wk2)
```
Day 2: SSO service and API — dependent on Day 1 SAML files
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — SSO Service backend/services/sso_service.py
```
(config CRUD, JIT provisioning)
```
saml_provider.py,
```
sso_config model (Day 1)
```
```
Agent 2 Agent 2 — SSO API backend/api/sso.py (GET
```
/metadata, POST /callback, GET
```
/login/:id)
```
```
sso_service.py (Day 2 —
```
```
wait)
```
Agent 3 Agent 3 — Security.py Update shared/core_functions/security.py
— add SSO JWT claims
```
security.py (Wk1)
```
Agent 4 Agent 4 — SSO Config
Schema
```
backend/schemas/sso.py sso_config model (Day 1)
```
Day 3: Frontend SSO pages — independent of each other
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — SSO
Login Page
```
frontend/src/app/(auth)/sso/page.tsx None — fully
```
independent
Agent 2 Agent 2 — SSO
Settings Page
frontend/src/app/dashboard/settings/sso/page.tsx dashboard layout
```
(Wk16)
```
Agent 3 Agent 3 — SSO
Setup Guide
docs/sso/saml-setup-guide.md None — fully
independent
Agent 4 Agent 4 — SSO
Admin Guide
docs/sso/enterprise-admin-guide.md None — fully
independent
Day 4: SSO tests — independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — SAML Provider
Tests
```
tests/unit/test_saml_provider.py saml_provider.py (Day 1)
```
```
Agent 2 Agent 2 — SP Metadata Tests tests/unit/test_sp_metadata.py metadata.py (Day 1)
```
```
Agent 3 Agent 3 — SSO Service Tests tests/unit/test_sso_service.py sso_service.py (Day 2)
```
```
Agent 4 Agent 4 — SSO API Tests tests/unit/test_sso_api.py sso.py API (Day 2)
```
Day 5: SSO integration tests — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — SAML Flow
Test
```
tests/integration/test_saml_flow.py (mock
```
```
IdP)
```
```
All SSO files (Days 1-4)
```
Agent 2 Agent 2 — JIT
Provisioning Test
```
tests/integration/test_jit_provisioning.py sso_service.py (Day 2)
```
Agent 3 Agent 3 — SSO Security
Test
tests/integration/test_sso_security.py
```
(replay attack)
```
```
saml_provider.py (Day 1)
```
```
Agent 4 Agent 4 — SSO E2E Test tests/e2e/test_sso_login_flow.py All SSO (Days 1-4)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
```
SSO SAML integration test (mock IdP). Configure SAML → upload IdP metadata → initiate SSO login → receive
```
```
SAMLResponse → validate → JWT issued → user provisioned (JIT). Replay attack: second submission rejected.
```
```
Run: pytest tests/integration/test_saml_flow.py + test_sso_security.py.
```
Week Complete When All Pass:
1 SAML flow: mock IdP → JWT issued successfully
2 JIT provisioning: new user created on first SSO login
3 Replay attack: duplicate SAMLResponse rejected
4 SP metadata: valid XML parseable by Okta/Azure/Google
5 Day 6: SAML 2.0 SSO integration validated
Week 51 — Enterprise SSO
Goal for This Week
Okta, Azure AD, Google Workspace SSO, and SCIM provisioning. Each provider is completely independent —
build all 3 simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: All 3 SSO provider implementations independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Okta
Provider
```
backend/core/sso/okta_provider.py (OIDC) security.py (Wk1)
```
Agent 2 Agent 2 — Azure AD
Provider
backend/core/sso/azure_ad_provider.py
```
(Microsoft Identity)
```
```
security.py (Wk1)
```
Agent 3 Agent 3 — Google
Workspace Provider
backend/core/sso/google_workspace_provider.py
```
(Google OAuth)
```
```
security.py (Wk1)
```
Agent 4 Agent 4 — SCIM Token
Model
backend/models/scim_token.py + DB migration
013
```
database.py (Wk2)
```
Day 2: SCIM service and provider guides — independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — SCIM Service backend/services/scim_service.py
```
(provision/update/deprovision)
```
```
sso_service.py (Wk50)
```
Agent 2 Agent 2 — SCIM API backend/api/scim.py
```
(GET/POST/PUT/DELETE Users and
```
```
Groups)
```
```
scim_service.py (Day 2 —
```
```
wait)
```
Agent 3 Agent 3 — Okta Guide docs/sso/okta-integration-
guide.md
None — fully independent
Agent 4 Agent 4 — Azure AD Guide docs/sso/azure-ad-guide.md +
google-workspace-guide.md
None — fully independent
Day 3: Provider-specific tests — independent per provider
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Okta
Tests
```
tests/unit/test_okta_provider.py okta_provider.py (Day 1)
```
Agent 2 Agent 2 — Azure
AD Tests
```
tests/unit/test_azure_ad_provider.py azure_ad_provider.py (Day 1)
```
Agent 3 Agent 3 — Google
Workspace Tests
tests/unit/test_google_workspace_provider.py google_workspace_provider.py
```
(Day 1)
```
Agent 4 Agent 4 — SCIM
Service Tests
```
tests/unit/test_scim_service.py scim_service.py (Day 2)
```
Day 4: SCIM integration tests and deprovisioning — independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — SCIM
Provisioning Test
```
tests/integration/test_scim_provisioning.py scim_service.py (Day 2)
```
Agent 2 Agent 2 — SCIM
Deprovisioning Test
```
tests/integration/test_scim_deprovisioning.py scim_service.py (Day 2)
```
Agent 3 Agent 3 — Okta SCIM
Integration Test
```
tests/integration/test_okta_scim.py (mock
```
```
Okta)
```
okta_provider.py,
```
scim_service.py (Days 1-
```
```
2)
```
Agent 4 Agent 4 — Azure SCIM
Test
```
tests/integration/test_azure_scim.py (mock
```
```
Azure)
```
azure_ad_provider.py,
```
scim_service.py (Days 1-
```
```
2)
```
Day 5: SCIM complete and SSO provider docs — independent
Day 5 Agent File to Build Depends On
```
Agent 1 Agent 1 — SCIM API Tests tests/unit/test_scim_api.py scim.py API (Day 2)
```
Agent 2 Agent 2 — SCIM E2E Test tests/e2e/test_scim_lifecycle.py
```
(create→update→delete)
```
```
All SCIM (Days 1-4)
```
Agent 3 Agent 3 — Provider
Comparison Doc
docs/sso/provider-comparison.md None — fully independent
Agent 4 Agent 4 — SCIM API Reference docs/api/scim-api-reference.md None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Okta + Azure AD + SCIM integration test. Mock Okta OIDC → login → JWT. Mock Azure AD → login → JWT.
```
SCIM: create user → verify provisioned → update user → verify updated → delete user → verify deprovisioned +
```
access revoked. Run: pytest tests/integration/test_okta_scim.py + test_scim_lifecycle.py.
Week Complete When All Pass:
1 Okta OIDC: mock login → JWT issued
2 Azure AD: mock login → JWT issued
```
3 SCIM: user lifecycle (create→update→delete) complete
```
4 SCIM deprovisioning: access revoked immediately on delete
5 Day 6: Okta + Azure AD + SCIM validated
Week 52 — Enterprise SSO
Goal for This Week
MFA enforcement, SSO audit logging, and enterprise admin UI. All three are independent — build
simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: MFA enforcer and audit service — independent
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — MFA Enforcer backend/core/sso/mfa_enforcer.py
```
(TOTP/hardware key policy)
```
```
security.py (Wk1)
```
Agent 2 Agent 2 — MFA API
Update
```
backend/api/mfa.py (enterprise MFA
```
```
management endpoints)
```
```
auth.py (Wk4)
```
Agent 3 Agent 3 — SSO Audit
Service
```
backend/services/audit_service.py (every
```
```
login/logout/MFA event)
```
```
audit_trail.py (Wk1)
```
Agent 4 Agent 4 — Access
Review Service
backend/services/access_review_service.py
```
(90+ day inactive flag)
```
```
user model (Wk3)
```
Day 2: SSO audit API and access review worker — independent
Day 2 Agent File to Build Depends On
Agent
1
Agent 1 —
SSO Audit
API
backend/api/sso.py — add /audit-log endpoint with CSV
export
```
audit_service.py (Day 1)
```
Agent
2
Agent 2 —
Access
Review
Worker
```
workers/access_review_worker.py (quarterly report) access_review_service.py
```
```
(Day 1)
```
Agent
3
Agent 3 —
SSO Audit
Page UI
```
frontend/src/app/dashboard/settings/sso/audit/page.tsx dashboard layout (Wk16)
```
Agent
4
Agent 4 —
Enterprise
Admin Guide
```
docs/sso/enterprise-admin-guide.md (complete) None — fully independent
```
Day 3: Security whitepaper and compliance docs — independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Security Whitepaper docs/sso/security-whitepaper.md
```
(enterprise procurement)
```
None — fully independent
Agent 2 Agent 2 — MFA Policy Doc docs/compliance/mfa-
enforcement-policy.md
None — fully independent
Agent 3 Agent 3 — SSO Compliance
Doc
docs/compliance/sso-compliance-
summary.md
None — fully independent
Agent 4 Agent 4 — Access Review
Template
compliance/soc2/evidence-
collection/access-
reviews/template.md
None — fully independent
Day 4: MFA and access review tests — independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — MFA
Enforcer Tests
```
tests/unit/test_mfa_enforcer.py mfa_enforcer.py (Day 1)
```
Agent 2 Agent 2 — Audit
Service Tests
```
tests/unit/test_audit_service.py audit_service.py (Day 1)
```
Agent 3 Agent 3 — Access
Review Tests
tests/unit/test_access_review_service.py access_review_service.py
```
(Day 1)
```
Agent 4 Agent 4 — SSO Audit
API Tests
```
tests/unit/test_sso_audit_api.py SSO audit API (Day 2)
```
Day 5: Enterprise SSO complete tests — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — MFA Flow
E2E
```
tests/e2e/test_mfa_enforcement.py mfa_enforcer.py (Day 1)
```
Agent 2 Agent 2 — Audit Log
Export Test
tests/integration/test_sso_audit_export.py
```
(CSV)
```
```
SSO audit API (Day 2)
```
Agent 3 Agent 3 — Access
Review E2E
tests/e2e/test_access_review_flow.py access_review_worker.py
```
(Day 2)
```
Agent 4 Agent 4 —
PROJECT_STATE
Update
```
PROJECT_STATE.md (Phase 12 SSO complete) None — fully independent
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Enterprise SSO Phase 12 FINAL gate. MFA: enterprise client without MFA enrolled → blocked from login. SSO
```
audit: every login logged with timestamp + IP + result. Access review: inactive 90-day user flagged. CSV export:
```
audit log downloads with all required fields. Run: pytest tests/e2e/test_mfa_enforcement.py +
test_sso_audit_export.py.
Week Complete When All Pass:
1 MFA enforcement: user without MFA blocked from enterprise tenant
2 SSO audit: every login event logged with IP + result
3 Audit CSV export: all required fields present
4 Access review: 90+ day inactive users flagged automatically
5 Day 6: Phase 12 enterprise SSO COMPLETE
Phase 13 — 99.99% Uptime & Multi-Region
Two regions, zero-downtime deploys, circuit breakers, chaos engineering. Infrastructure files are independent per day.
Week 53 — 99.99% Uptime & Multi-Region
Goal for This Week
Multi-region deployment. Primary and secondary region Terraform modules are independent of each other.
Global load balancer is independent of both regions.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Multi-region Terraform files independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Primary Region infra/terraform/multi-
region/primary-region.tf
```
providers.tf (Wk41)
```
Agent 2 Agent 2 — Secondary Region infra/terraform/multi-
region/secondary-region.tf
```
providers.tf (Wk41)
```
Agent 3 Agent 3 — Global Load
Balancer
infra/terraform/multi-
region/global-load-balancer.tf
```
networking.tf (Wk41)
```
Agent 4 Agent 4 — Multi-Region Health
Checks
infra/kubernetes/multi-
region/health-checks/
```
namespace.yaml (Wk41)
```
Day 2: DB and Redis replication — independent of LB
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — DB Replication infra/terraform/multi-
region/database-replication.tf
```
database.tf (Wk41)
```
Agent 2 Agent 2 — Redis Replication infra/terraform/multi-
region/redis-replication.tf
```
redis.tf (Wk41)
```
Agent 3 Agent 3 — Secondary K8s
Stack
infra/kubernetes/multi-
region/secondary/ manifests
```
secondary-region.tf (Day 1)
```
Agent 4 Agent 4 — Primary K8s Stack infra/kubernetes/multi-
region/primary/ manifests
```
primary-region.tf (Day 1)
```
Day 3: App-layer circuit breakers — independent per integration
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Circuit Breaker
Utility
shared/utils/circuit_breaker.py
```
(CLOSED→OPEN→HALF_OPEN)
```
```
config.py (Wk1)
```
Agent 2 Agent 2 — Shopify Circuit
Breaker
shared/integrations/shopify_client.py
— wrap with circuit breaker
```
circuit_breaker.py (Day 3
```
```
— wait), shopify_client.py
```
```
(Wk7)
```
Agent 3 Agent 3 — Stripe Circuit
Breaker
shared/integrations/stripe_client.py
— wrap with circuit breaker
```
circuit_breaker.py (Day 3
```
```
— wait), stripe_client.py
```
```
(Wk7)
```
Agent 4 Agent 4 — OpenRouter
Circuit Breaker
shared/smart_router/router.py — wrap
with circuit breaker
```
circuit_breaker.py (Day 3
```
```
— wait), router.py (Wk5)
```
Day 4: Multi-region tests — independent per region
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Primary
Region Test
```
tests/integration/test_primary_region.py Primary K8s (Day 2)
```
Agent 2 Agent 2 — Secondary
Region Test
```
tests/integration/test_secondary_region.py Secondary K8s (Day 2)
```
Agent 3 Agent 3 — Failover Test tests/integration/test_regional_failover.py
```
(<30s failover)
```
```
Global LB (Day 1)
```
Agent 4 Agent 4 — Circuit
Breaker Tests
```
tests/unit/test_circuit_breaker.py circuit_breaker.py (Day
```
```
3)
```
Day 5: Multi-region docs — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Uptime
Architecture Doc
docs/architecture/99-99-uptime-architecture.md None — fully
independent
Agent 2 Agent 2 — Failover
Runbook
```
docs/runbook.md (add multi-region failover section) runbook.md
```
```
(Wk14)
```
Agent 3 Agent 3 — Circuit
Breaker Doc
docs/architecture_decisions/009_circuit_breakers.md None — fully
independent
Agent 4 Agent 4 —
Replication Lag
Monitor
monitoring/grafana-dashboards/replication-
dashboard.json
None — fully
independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Multi-region integration test. Primary + secondary both running. Global LB routes to nearest. Simulate primary
failure → verify traffic moves to secondary in <30 seconds. DB replication lag <500ms. Circuit breaker: Shopify
down → circuit opens → fallback response. Run: pytest tests/integration/test_regional_failover.py.
Week Complete When All Pass:
1 Regional failover: traffic moves to secondary in <30 seconds
2 DB replication lag: <500ms
3 Circuit breaker: Shopify failure opens circuit correctly
4 Both regions: independent health checks passing
5 Day 6: multi-region failover validated
Week 54 — 99.99% Uptime & Multi-Region
Goal for This Week
Zero-downtime deploys, network policies, pod disruption budgets. All service-level configs are independent of
each other — build simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Pod disruption budgets and network policies — independent per service
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Backend PDB infra/kubernetes/pod-
disruption-budgets/backend-
```
pdb.yaml (min 1 pod)
```
backend-deployment.yaml
```
(Wk42)
```
Agent 2 Agent 2 — Worker PDB infra/kubernetes/pod-
disruption-budgets/worker-
pdb.yaml
worker-deployment.yaml
```
(Wk42)
```
Agent 3 Agent 3 — Network Policy
Default Deny
infra/kubernetes/network-
policies/default-deny.yaml
```
namespace.yaml (Wk41)
```
Agent 4 Agent 4 — Network Policy
Allow Rules
infra/kubernetes/network-
policies/allow-rules.yaml
```
default-deny.yaml (Day 1 —
```
```
wait)
```
Day 2: Zero-downtime rolling deploy configs — independent per service
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Backend Rolling
Deploy
infra/kubernetes/backend-
deployment.yaml —
```
maxUnavailable:0, maxSurge:1
```
backend-deployment.yaml
```
(Wk42)
```
Agent 2 Agent 2 — Worker Rolling
Deploy
infra/kubernetes/worker-
deployment.yaml — rolling
update strategy
worker-deployment.yaml
```
(Wk42)
```
Agent 3 Agent 3 — Frontend Rolling
Deploy
infra/kubernetes/frontend-
deployment.yaml — rolling
update strategy
frontend-deployment.yaml
```
(Wk42)
```
Agent 4 Agent 4 — Readiness Probes All deployment.yaml files — add
readiness/liveness probes
```
All deployments (Wk42)
```
Day 3: Tracing and monitoring — independent
Day 3 Agent File to Build Depends On
```
Agent 1 Agent 1 — OpenTelemetry shared/utils/tracing.py (trace
```
```
propagation)
```
```
config.py (Wk1)
```
```
Agent 2 Agent 2 — Tracing Terraform infra/terraform/tracing.tf (X-
```
```
Ray/Cloud Trace)
```
```
networking.tf (Wk41)
```
Agent 3 Agent 3 — Tracing Dashboard monitoring/grafana-
dashboards/tracing-
dashboard.json
None — fully independent
```
Agent 4 Agent 4 — Alert Updates monitoring/alerts.yml (add
```
uptime + replication lag
```
alerts)
```
```
alerts.yml (Wk14)
```
Day 4: SLA verification and runbook — independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — SLA
Verifier
tests/integration/test_sla_verification.py
```
(99.99% uptime calc)
```
```
sla_service.py (Wk12)
```
Agent 2 Agent 2 — Deploy
Verification
tests/integration/test_zero_downtime_deploy.py Rolling deploy config
```
(Day 2)
```
Agent 3 Agent 3 — Network
Policy Test
```
tests/integration/test_network_policies.py network-policies/ (Day
```
```
1)
```
Agent 4 Agent 4 — Runbook
Update
```
docs/runbook.md (add zero-downtime section) runbook.md (Wk14)
```
Day 5: Week 54 tests — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — PDB
Tests
```
tests/integration/test_pod_disruption_budgets.py PDBs (Day 1)
```
Agent 2 Agent 2 — Circuit
Breaker Integration
tests/integration/test_circuit_breakers_all.py circuit_breaker.py
```
(Wk53)
```
Agent 3 Agent 3 — Tracing
Tests
```
tests/unit/test_tracing.py tracing.py (Day 3)
```
Agent 4 Agent 4 — Main.py
Update
backend/app/main.py — add graceful shutdown +
health signal
```
main.py (Wk3)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Zero-downtime and network policy test. Rolling deploy: trigger deployment while load test running → P95 never
drops to 0 → all requests served. PDB: kubectl delete pod → second pod stays up. Network policy: cross-
namespace connection blocked. OpenTelemetry: traces appear in dashboard. Run: pytest
tests/integration/test_zero_downtime_deploy.py + test_network_policies.py.
Week Complete When All Pass:
1 Rolling deploy: zero dropped requests during deployment
2 PDB: minimum 1 pod always available
3 Network policy: cross-namespace blocked, in-namespace allowed
4 OpenTelemetry: traces visible in tracing dashboard
5 Day 6: zero-downtime + network policies validated
Week 55 — 99.99% Uptime & Multi-Region
Goal for This Week
Chaos engineering experiments and SLA verification. All chaos experiments are independent of each other —
build and run simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Chaos experiment manifests — all independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Pod Kill Experiment infra/chaos/pod-kill-
experiment.yaml
```
K8s cluster (Wk41)
```
Agent 2 Agent 2 — Network Delay
Experiment
infra/chaos/network-delay-
```
experiment.yaml (300ms delay)
```
```
K8s cluster (Wk41)
```
Agent 3 Agent 3 — DB Connection
Experiment
infra/chaos/db-connection-
experiment.yaml
```
K8s cluster (Wk41)
```
Agent 4 Agent 4 — Chaos Schedule infra/chaos/chaos-schedule.yaml
```
(weekly Sunday 2am staging)
```
```
K8s cluster (Wk41)
```
Day 2: Run each chaos experiment independently — staging only
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Pod Kill Test
```
(staging)
```
Run pod-kill-experiment on
staging → verify recovery
pod-kill-experiment.yaml
```
(Day 1)
```
Agent 2 Agent 2 — Network Delay Test
```
(staging)
```
Run network-delay-experiment →
verify P95 still <1s
network-delay-
```
experiment.yaml (Day 1)
```
Agent 3 Agent 3 — DB Connection Test
```
(staging)
```
Run db-connection-experiment →
verify circuit breaker opens
db-connection-
```
experiment.yaml (Day 1)
```
Agent 4 Agent 4 — Chaos Metrics
Capture
Capture all Prometheus metrics
during each experiment
```
All experiments (Days 1-2)
```
Day 3: Chaos test documentation and SLA calculation — independent
Day 3 Agent File to Build Depends On
```
Agent 1 Agent 1 — Pod Kill Results docs/chaos/pod-kill-results.md Pod kill test (Day 2)
```
Agent 2 Agent 2 — Network Delay
Results
```
docs/chaos/network-delay-results.md Network delay test (Day 2)
```
```
Agent 3 Agent 3 — DB Chaos Results docs/chaos/db-connection-results.md DB connection test (Day 2)
```
Agent 4 Agent 4 — SLA Calculation tests/integration/test_sla_99_99.py
— calculate actual uptime
```
All chaos results (Day 2)
```
Day 4: Chaos improvements based on results — independent per finding
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Fix Findings from
Pod Kill
Fix any issues found in pod
kill experiment
```
Pod kill results (Day 3)
```
Agent 2 Agent 2 — Fix Findings from
Network Delay
Fix any issues found in network
delay experiment
```
Network delay results (Day
```
```
3)
```
Agent 3 Agent 3 — Fix Findings from
DB Chaos
Fix any issues found in DB
connection experiment
```
DB chaos results (Day 3)
```
```
Agent 4 Agent 4 — Chaos Runbook docs/runbook.md (add chaos
```
```
experiment section)
```
None — fully independent
Day 5: Phase 13 completion docs and tests — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Chaos Schedule
Tests
tests/integration/test_chaos_schedule.py chaos-schedule.yaml
```
(Day 1)
```
Agent 2 Agent 2 — 99.99% Uptime
Certification
docs/compliance/99-99-uptime-
verification.md
```
SLA calculation (Day 3)
```
Agent 3 Agent 3 — Phase 13
Report
docs/milestone-reports/phase-13-uptime-
complete.md
None — fully
independent
Agent 4 Agent 4 —
PROJECT_STATE Update
```
PROJECT_STATE.md (Phase 13 99.99% uptime
```
```
complete)
```
None — fully
independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Phase 13 FINAL gate. All 3 chaos experiments run on staging without catastrophic failure. System recovers from
pod kill in <60 seconds. Circuit breaker opens on DB failure. Network delay: P95 stays <1 second with 300ms
delay. SLA calculation: ≥99.99% uptime verified. Run: pytest tests/integration/test_sla_99_99.py.
Week Complete When All Pass:
1 Pod kill: system recovers in <60 seconds
2 DB failure: circuit breaker opens, fallback response served
3 Network delay: P95 <1 second with 300ms injected
4 SLA calculation: ≥99.99% uptime verified
5 Day 6: Phase 13 99.99% uptime COMPLETE
Phase 14 — SOC 2 Type II Certification
SOC 2 Type II — policies, evidence collection, scanning, audit prep. Policy documents are fully independent of each other.
Week 56 — SOC 2 Type II Certification
Goal for This Week
SOC 2 gap assessment and all 6 policy documents. Policies are completely independent of each other — 4
agents write different policies simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Gap assessment and Vanta/Drata setup — independent foundations
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Gap Assessment compliance/soc2/gap-
assessment.md
None — fully independent
Agent 2 Agent 2 — Vanta/Drata Setup infra/terraform/compliance.tf
```
(compliance automation agent)
```
```
networking.tf (Wk41)
```
Agent 3 Agent 3 — SOC 2 README compliance/soc2/README.md None — fully independent
Agent 4 Agent 4 — SOC 2 Tooling Doc compliance/soc2/evidence-
collection/tooling.md
None — fully independent
```
Day 2: Policy documents — all independent of each other (write in parallel)
```
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — InfoSec Policy compliance/soc2/policies/information-
security-policy.md
None — fully independent
Agent 2 Agent 2 — Access Control
Policy
compliance/soc2/policies/access-
control-policy.md
None — fully independent
Agent 3 Agent 3 — Change
Management Policy
compliance/soc2/policies/change-
management-policy.md
None — fully independent
Agent 4 Agent 4 — Incident
Response Policy
compliance/soc2/policies/incident-
response-policy.md
None — fully independent
Day 3: Remaining policies — independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Vendor
Management Policy
compliance/soc2/policies/vendor-
management-policy.md
None — fully independent
Agent 2 Agent 2 — Business
Continuity Policy
compliance/soc2/policies/business-
continuity-policy.md
None — fully independent
Agent 3 Agent 3 — Sub-Processors
List
```
legal/sub_processors.md (complete
```
```
list for SOC 2)
```
None — fully independent
Agent 4 Agent 4 — Security Scanning
Terraform
infra/terraform/security-
```
scanning.tf (Snyk/Inspector)
```
```
networking.tf (Wk41)
```
Day 4: Security scanning GitHub Action and KMS — independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Snyk GitHub Action .github/workflows/security-
```
scan.yml (blocks PR on critical
```
```
CVE)
```
None — fully independent
```
Agent 2 Agent 2 — KMS Config infra/terraform/kms.tf (AES-
```
256, per-client keys, annual
```
rotation)
```
```
networking.tf (Wk41)
```
Agent 3 Agent 3 — Encryption
Verification
compliance/soc2/evidence-
collection/encryption-
verification.md
None — fully independent
Agent 4 Agent 4 — Log Retention
Config
compliance/soc2/evidence-
collection/log-retention-
config.md
None — fully independent
Day 5: SOC 2 Week 1 tests — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Policy
Review Test
```
tests/compliance/test_policy_completeness.py All 6 policies (Days 2-
```
```
3)
```
Agent 2 Agent 2 — Snyk Scan
Test
Run snyk test — verify GitHub Action blocks
critical CVEs
```
security-scan.yml (Day
```
```
4)
```
```
Agent 3 Agent 3 — KMS Test tests/integration/test_kms_encryption.py kms.tf (Day 4)
```
Agent 4 Agent 4 — Vanta/Drata
Test
```
Verify compliance agent collecting evidence compliance.tf (Day 1)
```
```
Day 6 — Daily Integration Test (Manual Trigger)
```
SOC 2 Week 1 gate. All 6 policies written and reviewed. Gap assessment complete. Vanta/Drata: evidence
collection active. Snyk: blocks PR with critical CVE. KMS: encryption keys created per client. Run: pytest
tests/compliance/test_policy_completeness.py. Observation period begins this week.
Week Complete When All Pass:
1 All 6 SOC 2 policies: written and reviewed
2 Gap assessment: all gaps identified with remediation plan
3 Vanta/Drata: collecting evidence automatically
4 Snyk: blocks PR with critical CVE
5 Day 6: SOC 2 Week 1 policies complete, observation period begins
Week 57 — SOC 2 Type II Certification
Goal for This Week
Vulnerability scanning, KMS encryption, TLS hardening, and network segmentation. All independent — build
simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: All security hardening files independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — TLS Hardening infra/kubernetes/ingress/ —
enforce TLS 1.2+ minimum
```
All ingress configs (Wk41-43)
```
Agent 2 Agent 2 — Network
Segmentation
infra/kubernetes/network-
policies/ — add SOC 2 compliant
policies
```
network-policies/ (Wk54)
```
Agent 3 Agent 3 — Secrets Rotation infra/terraform/kms.tf — add
90-day secret rotation schedule
```
kms.tf (Wk56)
```
Agent 4 Agent 4 — Container
Hardening
All Dockerfiles — run as non-
root user, read-only filesystem
```
All Dockerfiles (Wk18)
```
Day 2: Pen test scope and CVE remediation — independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Pen Test Scope compliance/soc2/penetration-
testing/scope.md
None — fully independent
Agent 2 Agent 2 — CVE Remediation
Log
compliance/soc2/penetration-
testing/remediation-log.md
None — fully independent
Agent 3 Agent 3 — Container CVE Scan Run snyk container test all
images — fix all critical CVEs
```
All Docker images (Wk42)
```
Agent 4 Agent 4 — Dependency CVE
Scan
Run snyk test backend/
frontend/ — fix all critical
CVEs
None — fully independent
Day 3: SOC 2 evidence files — independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Change
Management Evidence
```
evidence: all PRs reviewed
```
```
before merge (GitHub log)
```
None — fully independent
Agent 2 Agent 2 — Encryption
Evidence
compliance/soc2/evidence-
collection/encryption-
```
verification.md (complete)
```
None — fully independent
Agent 3 Agent 3 — Vulnerability Scan
Evidence
compliance/soc2/evidence-
collection/vulnerability-scan-
results.md
```
CVE scans (Day 2)
```
Agent 4 Agent 4 — Incident Response
Evidence
compliance/soc2/evidence-
collection/incident-response-
log.md
None — fully independent
Day 4: Security tests — independent
Day 4 Agent File to Build Depends On
```
Agent 1 Agent 1 — TLS Test tests/integration/test_tls_enforcement.py TLS hardening (Day
```
```
1)
```
Agent 2 Agent 2 — Container
Security Test
tests/integration/test_container_hardening.py Container hardening
```
(Day 1)
```
Agent 3 Agent 3 — Secrets
Rotation Test
```
tests/integration/test_secrets_rotation.py Secrets rotation (Day
```
```
1)
```
Agent 4 Agent 4 — Network
Segmentation Test
tests/integration/test_network_segmentation.py Network policies
```
(Day 1)
```
Day 5: Security hardening docs — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — TLS Compliance
Doc
docs/compliance/tls-
compliance.md
None — fully independent
Agent 2 Agent 2 — Container Security
Doc
docs/compliance/container-
security.md
None — fully independent
Agent 3 Agent 3 — Vulnerability
Management Doc
docs/compliance/vulnerability-
management.md
None — fully independent
Agent 4 Agent 4 — Security Hardening
Report
docs/security/wk57-security-
hardening-report.md
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
Security hardening gate. TLS 1.2+ enforced on all endpoints. All containers run as non-root. Zero critical CVEs on
all images. Network: backend cannot reach frontend namespace directly. KMS: secret rotation working. Run:
pytest tests/integration/test_tls_enforcement.py + test_container_hardening.py.
Week Complete When All Pass:
1 TLS: 1.2+ enforced, TLS 1.0/1.1 rejected
2 Containers: all running as non-root user
3 CVEs: zero critical on all images
4 Network segmentation: cross-namespace blocked
5 Day 6: security hardening validated for SOC 2
Week 58 — SOC 2 Type II Certification
Goal for This Week
Log retention, access reviews, anomaly detection, and SOC 2 controls mapping. All independent — build
simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Log retention and access review configs — independent
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — Log
Retention Policy
infra/terraform/logging.tf — 90-day active,
1-year audit, 7-year cold
```
logging.tf (Wk44)
```
Agent 2 Agent 2 — Access
Review Config
backend/services/access_review_service.py
```
(complete)
```
access_review_service.py
```
(Wk52)
```
Agent 3 Agent 3 — Anomaly
Detection
backend/services/anomaly_detection_service.py
```
(new country, mass download)
```
```
audit_trail.py (Wk1)
```
Agent 4 Agent 4 — Access
Review Worker
```
workers/access_review_worker.py (complete
```
```
quarterly report)
```
access_review_service.py
```
(Wk52)
```
Day 2: SOC 2 controls mapping and alert updates — independent
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Controls Mapping compliance/soc2/controls-
```
mapping.md (every control
```
```
mapped)
```
```
All compliance work (Wks
```
```
56-58)
```
```
Agent 2 Agent 2 — Anomaly Alerts monitoring/alerts.yml (add
```
```
anomaly detection alerts)
```
```
alerts.yml (Wk14)
```
Agent 3 Agent 3 — Log Retention
Evidence
compliance/soc2/evidence-
collection/log-retention-
```
config.md (complete)
```
```
logging.tf (Day 1)
```
Agent 4 Agent 4 — Quarterly Access
Review Template
compliance/soc2/evidence-
collection/access-
```
reviews/template.md (complete)
```
None — fully independent
Day 3: SOC 2 evidence collection automation — independent
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Backup Evidence compliance/soc2/evidence-
collection/backup-
verification.md
pg-backup-cronjob.yaml
```
(Wk44)
```
Agent 2 Agent 2 — Monitoring
Evidence
compliance/soc2/evidence-
collection/monitoring-alerts.md
alerts.yml
Agent 3 Agent 3 — Access Control
Evidence
compliance/soc2/evidence-
collection/access-control-
review.md
access_review_service.py
```
(Day 1)
```
Agent 4 Agent 4 — Change
Management Evidence
compliance/soc2/evidence-
collection/change-management-
log.md
None — fully independent
Day 4: Tests for new services — independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 —
Anomaly
Detection
Tests
tests/unit/test_anomaly_detection.py anomaly_detection_service.py
```
(Day 1)
```
Agent 2 Agent 2 — Log
Retention
Tests
```
tests/integration/test_log_retention_policy.py logging.tf (Day 1)
```
Agent 3 Agent 3 —
Access Review
Tests
tests/integration/test_access_review_quarterly.py access_review_worker.py
```
(Day 1)
```
Agent 4 Agent 4 —
Controls
Mapping
Review
Review all controls mapping — verify each has
evidence link
```
controls-mapping.md (Day 2)
```
Day 5: SOC 2 readiness check — independent per Trust Service Criteria
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Security Criteria
Check
docs/compliance/soc2-security-
criteria-check.md
None — fully independent
Agent 2 Agent 2 — Availability Criteria
Check
docs/compliance/soc2-
availability-criteria-check.md
None — fully independent
Agent 3 Agent 3 — Confidentiality
Criteria Check
docs/compliance/soc2-
confidentiality-criteria-
check.md
None — fully independent
Agent 4 Agent 4 — Privacy Criteria
Check
docs/compliance/soc2-privacy-
criteria-check.md
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
SOC 2 evidence and controls gate. All 5 Trust Service Criteria have at least one piece of evidence. Anomaly
```
detection: new-country login triggers alert. Log retention: 90-day retention confirmed in cloud. Access review:
```
quarterly report generated. Controls mapping: all controls have policy + technical control + evidence. Run: pytest
tests/unit/test_anomaly_detection.py + test_log_retention_policy.py.
Week Complete When All Pass:
1 All 5 SOC 2 Trust Service Criteria: evidence present
2 Anomaly detection: new-country login triggers alert
3 Log retention: 90-day confirmed, old logs archived
4 Access review: quarterly report generated with inactive users
5 Day 6: SOC 2 evidence and controls validated
Week 59 — SOC 2 Type II Certification
Goal for This Week
Mock audit, management assertion, system description, and auditor engagement. All document-creation tasks
are independent — build simultaneously.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: SOC 2 formal documents — independent of each other
Day 1 Agent File to Build Depends On
Agent 1 Agent 1 — System Description compliance/soc2/system-
```
description.md (formal system
```
```
scope)
```
None — fully independent
Agent 2 Agent 2 — Management
Assertion
compliance/soc2/management-
```
assertion.md (signed formal
```
```
letter)
```
None — fully independent
Agent 3 Agent 3 — Auditor Readiness
Checklist
compliance/soc2/auditor-
readiness-checklist.md
```
All SOC 2 work (Wks 56-58)
```
Agent 4 Agent 4 — Observation Period
Log
compliance/soc2/observation-
```
period-log.md (weekly log
```
```
template)
```
None — fully independent
Day 2: Mock audit questions and responses — independent per Trust Criterion
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Mock Audit
Questions
compliance/soc2/mock-
audit/audit-questions.md
None — fully independent
Agent 2 Agent 2 — Mock Audit
Responses
compliance/soc2/mock-
```
audit/responses.md (answer each
```
```
question)
```
```
audit-questions.md (Day 2 —
```
```
wait)
```
Agent 3 Agent 3 — Mock Audit Gaps
Found
compliance/soc2/mock-
audit/gaps-found.md
```
responses.md (Day 2 —
```
```
wait)
```
Agent 4 Agent 4 — Auditor
Engagement Email
docs/compliance/auditor-
engagement-email-template.md
None — fully independent
Day 3: Fix all gaps found in mock audit — independent per gap
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Fix Security Gaps Fix any security control gaps
from mock audit
```
gaps-found.md (Day 2)
```
Agent 2 Agent 2 — Fix Availability
Gaps
Fix any availability control
gaps from mock audit
```
gaps-found.md (Day 2)
```
Agent 3 Agent 3 — Fix Confidentiality
Gaps
Fix any confidentiality control
gaps from mock audit
```
gaps-found.md (Day 2)
```
Agent 4 Agent 4 — Fix Documentation
Gaps
Fix any documentation gaps from
mock audit
```
gaps-found.md (Day 2)
```
Day 4: Final evidence package — independent per Trust Criterion
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Security Evidence
Package
compliance/soc2/evidence-
packages/security.zip
```
All security evidence (Wks
```
```
56-59)
```
Agent 2 Agent 2 — Availability
Evidence Package
compliance/soc2/evidence-
packages/availability.zip
```
All availability evidence (Wks
```
```
56-59)
```
Agent 3 Agent 3 — Confidentiality
Evidence Package
compliance/soc2/evidence-
packages/confidentiality.zip
All confidentiality evidence
```
(Wks 56-59)
```
Agent 4 Agent 4 — Final Evidence
Index
compliance/soc2/evidence-
packages/index.md
```
All evidence packages (Day
```
```
4 — wait)
```
Day 5: Auditor engagement and final checks — independent
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Engage Auditor Send auditor engagement email +
first call scheduled
None — fully independent
Agent 2 Agent 2 — Observation Period
Week 1 Log
compliance/soc2/observation-
```
period-log.md (fill Week 1)
```
None — fully independent
Agent 3 Agent 3 — Final Security Scan Final OWASP + Snyk scan before
auditor call
None — fully independent
Agent 4 Agent 4 — PROJECT_STATE
Update
```
PROJECT_STATE.md (SOC 2
```
```
observation period active)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
SOC 2 pre-audit gate. Mock audit: all questions answered. All gaps fixed. Evidence packages complete. Auditor
engaged. Observation period log started. Final OWASP scan: clean. Final CVE scan: zero critical. Run: pytest
```
tests/compliance/ (all compliance tests pass).
```
Week Complete When All Pass:
1 Mock audit: all questions answered, all gaps remediated
2 Evidence packages: all 3 criteria packages ready
3 Auditor: engaged, first call scheduled
4 Observation period log: started and being maintained
5 Day 6: SOC 2 pre-audit gate passed
Week 60 — SOC 2 Type II Certification
Goal for This Week
WEEK 60 — FINAL PRODUCTION READY GATE. Run all test suites in parallel. Verify every system, every
integration, every compliance control. This is the 100% production ready certification.
```
Parallel Agent Schedule (Days 1–5)
```
Day 1: Final complete test suite — all categories run in parallel
Day 1 Agent File to Build Depends On
```
Agent 1 Agent 1 — Full Unit Suite pytest tests/unit/ (target:
```
```
100% pass)
```
```
All unit tests (Wks 1-59)
```
Agent 2 Agent 2 — Full Integration
Suite
pytest tests/integration/
```
(target: 100% pass)
```
```
All integration tests (Wks 1-
```
```
59)
```
```
Agent 3 Agent 3 — Full E2E Suite pytest tests/e2e/ (target: 100%
```
```
pass)
```
```
All e2e tests (Wks 1-59)
```
Agent 4 Agent 4 — Full Compliance
Suite
pytest tests/compliance/
```
(target: 100% pass)
```
```
All compliance tests (Wks
```
```
56-59)
```
Day 2: Final security validation — independent per scan type
Day 2 Agent File to Build Depends On
Agent 1 Agent 1 — Final OWASP OWASP ZAP final scan on cloud
URLs — must be clean
```
All cloud services (Wks 41-
```
```
59)
```
Agent 2 Agent 2 — Final CVE Scan snyk container test all images
— zero critical
All Docker images
Agent 3 Agent 3 — Final RLS Test 1000 cross-tenant isolation
tests — 0 leaks
```
rls_policies.sql (Wk3)
```
```
Agent 4 Agent 4 — Final Pen Test External pen test (if
```
```
scheduled) OR internal final
```
pen test
None — fully independent
Day 3: Final performance validation — independent metrics
Day 3 Agent File to Build Depends On
Agent 1 Agent 1 — Final Load Test locust — 200 concurrent, P95
<300ms target
All cloud services
Agent 2 Agent 2 — Final AL Accuracy Verify Agent Lightning ≥94% on
all categories
```
accuracy_tracker.py (Wk13)
```
Agent 3 Agent 3 — Final Token Usage Verify Light tier >92%, under
monthly token budget
```
router.py (Wk35)
```
Agent 4 Agent 4 — Final Cache Rate Verify Redis cache hit rate
>75%
```
cache.py (Wk26)
```
Day 4: Final documentation — all independent
Day 4 Agent File to Build Depends On
Agent 1 Agent 1 — Complete System
Overview
docs/complete-system-
overview.md
None — fully independent
Agent 2 Agent 2 — New Dev
Onboarding Doc
docs/new-developer-
```
onboarding.md (final)
```
None — fully independent
Agent 3 Agent 3 — Client Success
Playbook
docs/client-success-playbook.md None — fully independent
```
Agent 4 Agent 4 — Final README README.md (final complete 60-
```
```
week version)
```
None — fully independent
Day 5: Production ready certification — independent per area
Day 5 Agent File to Build Depends On
Agent 1 Agent 1 — Infrastructure
Certification
docs/certification/infrastructure-
production-ready.md
None — fully independent
Agent 2 Agent 2 — Security
Certification
docs/certification/security-
production-ready.md
None — fully independent
Agent 3 Agent 3 — Compliance
Certification
docs/certification/compliance-
production-ready.md
None — fully independent
Agent 4 Agent 4 — PROJECT_STATE
Final
```
PROJECT_STATE.md (PARWA 60 WEEKS
```
```
COMPLETE — 100% PRODUCTION READY)
```
None — fully independent
```
Day 6 — Daily Integration Test (Manual Trigger)
```
WEEK 60 FINAL GATE — 100% PRODUCTION READY CERTIFICATION. ALL must pass: pytest tests/ 100%,
OWASP clean, zero critical CVEs, 1000 RLS isolation tests pass, P95 <300ms at 200 concurrent, Agent
Lightning ≥94%, Light tier >92%, cache >75%, SOC 2 observation active, mobile apps in App Store + Play Store,
multi-region failover <30s, all enterprise SSO working. PARWA is production ready.
Week Complete When All Pass:
1 pytest tests/: 100% pass rate across all 60 weeks of tests
2 Security: OWASP clean, zero critical CVEs, 1000 RLS tests pass
3 Performance: P95 <300ms at 200 concurrent, Light tier >92%
4 Agent Lightning: ≥94% accuracy across all categories
5 Mobile: both apps live in App Store and Google Play
6 SOC 2: observation period active, auditor engaged
7 Multi-region: failover <30 seconds verified
8 Enterprise SSO: SAML + Okta + Azure AD all working
#### 9 PARWA: 100% PRODUCTION READY. 60 weeks complete.