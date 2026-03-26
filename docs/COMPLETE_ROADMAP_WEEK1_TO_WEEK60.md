# PARWA Complete Roadmap: Week 1 to Week 60
# ============================================
# VERSION: 2.0 - Complete Production Roadmap
# UPDATED: 2024
# PAYMENT: Paddle ONLY (Merchant of Record)
# VOICE/SMS: Twilio (placeholder for testing, swappable later)
# ============================================

## PARALLEL EXECUTION RULES

```
+-----------------------------------------------------------------------+
| PARALLEL RULE (STRICT):                                               |
|                                                                       |
| ✅ Within a DAY: files CAN depend on each other (sequential build)    |
|    One builder builds files in order, top to bottom                   |
|                                                                       |
| ❌ Across DAYS of same WEEK: files CANNOT depend on each other        |
|    All 5 builders run in PARALLEL                                     |
|                                                                       |
| ✅ Across WEEKS: files CAN depend on any file from previous weeks     |
|    (already built)                                                    |
|                                                                       |
| TOOL: Zai agent (builder)                                             |
|                                                                       |
| TESTING: Tester Agent runs ONCE at end of week (Day 6)                |
|          Day 6 tests: CURRENT WEEK + ALL PREVIOUS WEEKS INTEGRATION   |
|                                                                       |
| GIT: Agent commits and pushes each file after its unit test passes    |
+-----------------------------------------------------------------------+
```

---

## PHASE OVERVIEW

| Phase | Weeks | Goal | Status |
|-------|-------|------|--------|
| 1 | 1-2 | Foundation (Monorepo, Config, Database) | ✅ COMPLETE |
| 2 | 3-4 | Security + Backend APIs | ✅ COMPLETE |
| 3 | 5-8 | Core AI Engine (GSD, Router, KB, TRIVYA, MCP) | ✅ COMPLETE |
| 4 | 9-14 | Variants & Integrations | 🔵 IN PROGRESS (Week 9 done) |
| 5 | 15-18 | Frontend Foundation | ⬜ Pending |
| 6 | 19-20 | First Clients | ⬜ Pending |
| 7 | 21-27 | Scale to 20 Clients + Polish | ⬜ Pending |
| 8 | 28-40 | Enterprise Preparation | ⬜ Pending |
| 9 | 41-44 | Cloud Migration | ⬜ Pending |
| 10 | 45-46 | Billing System | ⬜ Pending |
| 11 | 47-49 | Mobile App | ⬜ Pending |
| 12 | 50-52 | Enterprise SSO | ⬜ Pending |
| 13 | 53-55 | High Availability | ⬜ Pending |
| 14 | 56-60 | SOC 2 Compliance | ⬜ Pending |

---

# PHASE 1: FOUNDATION (Weeks 1-2) ✅ COMPLETE

---

## WEEK 1 — Monorepo Setup + Core Config

**Goal:** Set up monorepo structure, config, logger, AI safety, BDD rulebooks

### Files Built (All Complete):

| File | Purpose |
|------|---------|
| `shared/__init__.py` | Shared module init |
| `shared/core_functions/__init__.py` | Core functions init |
| `shared/core_functions/config.py` | Environment config with Pydantic |
| `shared/core_functions/logger.py` | Structured JSON logging |
| `shared/core_functions/security.py` | Security utilities |
| `shared/core_functions/ai_safety.py` | AI safety helpers |
| `shared/core_functions/compliance.py` | Compliance base |
| `shared/core_functions/audit_trail.py` | Audit logging |
| `shared/core_functions/pricing_optimizer.py` | Anti-arbitrage pricing |
| `shared/utils/__init__.py` | Utils init |
| `shared/utils/cache.py` | Redis caching |
| `shared/utils/monitoring.py` | Prometheus metrics |
| `shared/utils/storage.py` | File storage |
| `shared/utils/message_queue.py` | ARQ message queue |
| `feature_flags/*.json` | Feature flags for all variants |
| `conftest.py` | Pytest configuration |
| `pytest.ini` | Pytest settings |
| `requirements.txt` | Python dependencies |

### TESTER AGENT (Day 6)

**Command:**
```bash
pytest tests/integration/test_week1_foundation.py -v
```

**Pass Criteria:**
- Config loads without errors
- Logger outputs JSON format
- Redis cache connects
- All core functions import correctly

---

## WEEK 2 — Database Layer + Alembic Migrations

**Goal:** Set up PostgreSQL, Alembic, seed data, ORM models

### Files Built (All Complete):

| File | Purpose |
|------|---------|
| `database/migrations/env.py` | Alembic environment |
| `database/migrations/versions/001_initial_schema.py` | Initial DB schema |
| `database/migrations/versions/002_agent_lightning.py` | Training tables |
| `database/migrations/versions/003_audit_trail.py` | Audit tables |
| `database/migrations/versions/004_compliance.py` | Compliance tables |
| `database/migrations/versions/005_feature_flags.py` | Feature flag tables |
| `database/migrations/versions/006_sessions_interactions.py` | Session tables |
| `database/schema.sql` | SQL schema |
| `database/seeds/users.sql` | Seed users |
| `database/seeds/clients.sql` | Seed clients |
| `database/seeds/sample_tickets.sql` | Sample tickets |
| `backend/models/*.py` | SQLAlchemy ORM models |
| `backend/schemas/*.py` | Pydantic schemas |
| `backend/app/database.py` | DB connection |

### TESTER AGENT (Day 6)

**Command:**
```bash
pytest tests/integration/test_week2_database.py tests/integration/test_week1_foundation.py -v
```

**Pass Criteria:**
- All migrations run without errors
- RLS (Row Level Security) policies work
- Seed data loads correctly
- ORM models connect to DB
- Integration with Week 1 config works

---

# PHASE 2: SECURITY + BACKEND APIs (Weeks 3-4) ✅ COMPLETE

---

## WEEK 3 — Security Layer + ORM + Schemas

**Goal:** Build security utilities, HMAC verification, KYC/AML, RLS policies

### Files Built (All Complete):

| File | Purpose |
|------|---------|
| `security/hmac_verification.py` | Webhook HMAC verification |
| `security/rate_limiter.py` | Rate limiting |
| `security/feature_flags.py` | Feature flag service |
| `security/kyc_aml.py` | KYC/AML compliance |
| `security/rls_policies.sql` | Row Level Security |
| `backend/core/auth.py` | Authentication core |
| `backend/core/config.py` | Backend config |
| `backend/core/license_manager.py` | License management |
| `backend/core/error_handler.py` | Error handling |
| `backend/api/auth.py` | Auth API endpoints |
| `backend/api/licenses.py` | License API endpoints |

### TESTER AGENT (Day 6)

**Command:**
```bash
pytest tests/integration/test_week1_foundation.py tests/integration/test_week2_database.py tests/unit/test_security.py -v
```

**Pass Criteria:**
- HMAC verification works
- Rate limiting enforced
- RLS isolation works (cross-tenant blocked)
- Auth endpoints work
- Integration with Weeks 1-2 works

---

## WEEK 4 — Backend APIs + Services + Webhooks

**Goal:** Build all backend APIs, services, webhook handlers

### Files Built (All Complete):

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI main app |
| `backend/app/middleware.py` | Request middleware |
| `backend/app/dependencies.py` | Dependency injection |
| `backend/api/dashboard.py` | Dashboard API |
| `backend/api/analytics.py` | Analytics API |
| `backend/api/support.py` | Support API |
| `backend/api/compliance.py` | Compliance API |
| `backend/api/billing.py` | Billing API |
| `backend/api/jarvis.py` | Jarvis command API |
| `backend/api/integrations.py` | Integrations API |
| `backend/api/webhooks/__init__.py` | Webhooks init |
| `backend/api/webhooks/shopify.py` | Shopify webhooks |
| `backend/api/webhooks/stripe.py` | Stripe webhooks (legacy, migrating to Paddle) |
| `backend/api/webhooks/error_handlers.py` | Webhook error handling |
| `backend/api/webhook_malformation_handler.py` | Malformed webhook handling |
| `backend/services/billing_service.py` | Billing service |
| `backend/services/notification_service.py` | Notification service |
| `backend/services/license_service.py` | License service |
| `backend/services/user_service.py` | User service |
| `backend/services/analytics_service.py` | Analytics service |
| `backend/services/sla_service.py` | SLA service |
| `backend/services/support_service.py` | Support service |
| `backend/services/onboarding_service.py` | Onboarding service |
| `backend/services/compliance_service.py` | Compliance service |
| `backend/services/service_errors.py` | Service errors |

### TESTER AGENT (Day 6)

**Command:**
```bash
pytest tests/integration/test_week1_foundation.py tests/integration/test_week2_database.py tests/unit/test_security.py tests/unit/test_app.py -v
```

**Pass Criteria:**
- All API endpoints respond correctly
- Webhooks process without errors
- Services initialize correctly
- Integration with Weeks 1-3 works

---

# PHASE 3: CORE AI ENGINE (Weeks 5-8) ✅ COMPLETE

---

## WEEK 5 — GSD State Engine + Smart Router + Knowledge Base + MCP Client

**Goal:** Build the GSD State Engine, Smart Router, Knowledge Base, MCP Client

### BUILDER 1 (Day 1) — GSD State Engine

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `shared/gsd_engine/__init__.py` | None | N/A |
| 2 | `shared/gsd_engine/state_schema.py` | config.py (Wk1) | Test: schema validates |
| 3 | `shared/gsd_engine/state_engine.py` | state_schema.py | Test: 20-msg compresses to <200 tokens |
| 4 | `shared/gsd_engine/context_health.py` | state_schema.py | Test: health flags correct |
| 5 | `shared/gsd_engine/compression.py` | state_engine.py | Test: >85% token reduction |
| 6 | `tests/unit/test_gsd_engine.py` | All above | PUSH AFTER PASS |

### BUILDER 2 (Day 2) — Smart Router

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `shared/smart_router/__init__.py` | None | N/A |
| 2 | `shared/smart_router/tier_config.py` | config.py (Wk1) | Test: OpenRouter IDs valid |
| 3 | `shared/smart_router/provider_config.py` | config.py | Test: providers configured |
| 4 | `shared/smart_router/failover.py` | config.py, logger.py | Test: failover on rate limit |
| 5 | `shared/smart_router/complexity_scorer.py` | tier_config.py | Test: FAQ scores 0-2, refund 9+ |
| 6 | `shared/smart_router/cost_optimizer.py` | router.py | Test: cost tracking |
| 7 | `shared/smart_router/routing_engine.py` | all above | Test: routing works |
| 8 | `shared/smart_router/router.py` | routing_engine.py | Test: FAQ→Light, refund→Heavy |
| 9 | `tests/unit/test_smart_router.py` | All above | PUSH AFTER PASS |

### BUILDER 3 (Day 3) — Knowledge Base

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `shared/knowledge_base/__init__.py` | None | N/A |
| 2 | `shared/knowledge_base/vector_store.py` | config.py, database.py | Test: embeddings stored/retrieved |
| 3 | `shared/knowledge_base/kb_manager.py` | config.py | Test: KB manager initializes |
| 4 | `shared/knowledge_base/hyde.py` | config.py | Test: HyDE generates hypothetical doc |
| 5 | `shared/knowledge_base/multi_query.py` | config.py | Test: generates 3 query variants |
| 6 | `shared/knowledge_base/rag_pipeline.py` | all above | Test: ingest + retrieve works |
| 7 | `tests/unit/test_knowledge_base.py` | All above | PUSH AFTER PASS |

### BUILDER 4 (Day 4) — MCP Client

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `shared/mcp_client/__init__.py` | None | N/A |
| 2 | `shared/mcp_client/client.py` | config.py | Test: client initializes |
| 3 | `shared/mcp_client/auth.py` | config.py, security.py | Test: auth tokens generated |
| 4 | `shared/mcp_client/registry.py` | config.py | Test: registry connects |
| 5 | `tests/unit/test_mcp_client.py` | All above | PUSH AFTER PASS |

### BUILDER 5 (Day 5) — Pricing + Docs

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/unit/test_pricing_optimizer.py` | pricing_optimizer.py (Wk1) | Test: anti-arbitrage formula |
| 2 | `docs/architecture_decisions/004_openrouter.md` | None | Doc only |
| 3 | `backend/api/webhook_malformation_handler.py` | webhooks (Wk4) | Test: malformed webhook handled |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/integration/test_week2_gsd_kb.py -v

# Integration with ALL previous weeks
pytest tests/integration/test_week1_foundation.py -v
pytest tests/integration/test_week2_database.py -v
pytest tests/unit/test_security.py -v
pytest tests/unit/test_app.py -v
```

**Pass Criteria:**
- GSD: 20-msg conversation → <200 tokens
- Smart Router: FAQ→Light, refund→Heavy
- Failover: simulated rate limit triggers switch
- KB: ingest + retrieve works
- MCP client: connects to registry
- Integration: GSD → Router → KB pipeline works
- **ALL previous weeks tests pass**

---

## WEEK 6 — TRIVYA Tier 1 + Tier 2 + Confidence + Sentiment

**Goal:** Build TRIVYA T1, T2, confidence scoring, sentiment analysis

### BUILDER 1 (Day 1) — TRIVYA Tier 1

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `shared/trivya_techniques/__init__.py` | None | N/A |
| 2 | `shared/trivya_techniques/tier1/__init__.py` | None | N/A |
| 3 | `shared/trivya_techniques/tier1/clara.py` | rag_pipeline.py, hyde.py | Test: CLARA retrieves context |
| 4 | `shared/trivya_techniques/tier1/crp.py` | gsd_engine.py | Test: CRP compresses |
| 5 | `shared/trivya_techniques/tier1/gsd_integration.py` | state_engine.py | Test: GSD integrates with T1 |
| 6 | `shared/trivya_techniques/orchestrator.py` | config.py, router.py, T1 | Test: T1 fires on every query |
| 7 | `tests/unit/test_trivya_tier1.py` | All above | PUSH AFTER PASS |

### BUILDER 2 (Day 2) — TRIVYA Tier 2

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `shared/trivya_techniques/tier2/__init__.py` | None | N/A |
| 2 | `shared/trivya_techniques/tier2/trigger_detector.py` | config.py | Test: detects decision_needed |
| 3 | `shared/trivya_techniques/tier2/chain_of_thought.py` | config.py | Test: step-by-step reasoning |
| 4 | `shared/trivya_techniques/tier2/react.py` | config.py | Test: reason+act loop |
| 5 | `shared/trivya_techniques/tier2/reverse_thinking.py` | config.py | Test: reverse approach |
| 6 | `shared/trivya_techniques/tier2/step_back.py` | config.py | Test: abstracts question |
| 7 | `shared/trivya_techniques/tier2/thread_of_thought.py` | gsd_engine.py | Test: thread maintains context |
| 8 | `tests/unit/test_trivya_tier2.py` | All above | PUSH AFTER PASS |

### BUILDER 3 (Day 3) — Confidence + Compliance Tests

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `shared/confidence/__init__.py` | None | N/A |
| 2 | `shared/confidence/thresholds.py` | config.py | Test: GRADUATE=95%, ESCALATE=70% |
| 3 | `shared/confidence/scorer.py` | thresholds.py | Test: weighted avg correct |
| 4 | `tests/unit/test_confidence_scorer.py` | All above | PUSH AFTER PASS |
| 5 | `tests/unit/test_compliance.py` | compliance.py | PUSH AFTER PASS |
| 6 | `tests/unit/test_audit_trail.py` | audit_trail.py | PUSH AFTER PASS |

### BUILDER 4 (Day 4) — Sentiment

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `shared/sentiment/__init__.py` | None | N/A |
| 2 | `shared/sentiment/analyzer.py` | router.py | Test: anger routes to High pathway |
| 3 | `shared/sentiment/routing_rules.py` | thresholds.py, analyzer.py | Test: routing rules apply |
| 4 | `tests/unit/test_sentiment.py` | All above | PUSH AFTER PASS |

### BUILDER 5 (Day 5) — Cold Start + T1+T2 Integration

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `shared/knowledge_base/cold_start.py` | kb_manager.py | Test: bootstraps with industry FAQs |
| 2 | `tests/unit/test_trivya_tier1_tier2.py` | All T1+T2 | PUSH AFTER PASS |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/unit/test_trivya_tier1.py tests/unit/test_trivya_tier2.py tests/unit/test_confidence_scorer.py tests/unit/test_sentiment.py -v

# Integration with ALL previous weeks
pytest tests/integration/test_week1_foundation.py tests/integration/test_week2_database.py tests/integration/test_week2_gsd_kb.py -v
```

**Pass Criteria:**
- TRIVYA T1 fires on every query
- T2 trigger only on decision_needed/multi_step
- Confidence: 95%+ → GRADUATE, <70% → ESCALATE
- Sentiment: high anger routes to PARWA High
- All 6 T2 techniques produce different outputs
- Cold start bootstraps new client KB
- **ALL previous weeks tests pass**

---

## WEEK 7 — TRIVYA Tier 3 + Integration Clients + Compliance Layer

**Goal:** Build T3 techniques, all integration clients, compliance layer

### BUILDER 1 (Day 1) — TRIVYA Tier 3

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `shared/trivya_techniques/tier3/__init__.py` | None | N/A |
| 2 | `shared/trivya_techniques/tier3/trigger_detector.py` | confidence/scorer.py | Test: fires on VIP/amount>$100/anger>80% |
| 3 | `shared/trivya_techniques/tier3/gst.py` | config.py | Test: structured thought output |
| 4 | `shared/trivya_techniques/tier3/universe_of_thoughts.py` | config.py | Test: multiple solution paths |
| 5 | `shared/trivya_techniques/tier3/tree_of_thoughts.py` | config.py | Test: tree structure generated |
| 6 | `shared/trivya_techniques/tier3/self_consistency.py` | config.py | Test: majority vote across paths |
| 7 | `shared/trivya_techniques/tier3/reflexion.py` | config.py | Test: reflection loop runs |
| 8 | `shared/trivya_techniques/tier3/least_to_most.py` | config.py | Test: decomposes complex query |
| 9 | `tests/unit/test_trivya_tier3.py` | All above | PUSH AFTER PASS |

### BUILDER 2 (Day 2) — E-commerce + Comms Clients

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `shared/integrations/__init__.py` | None | N/A |
| 2 | `shared/integrations/shopify_client.py` | config.py, logger.py | Test: mock connection |
| 3 | `shared/integrations/paddle_client.py` | config.py, logger.py | Test: **REFUND GATE ENFORCED** |
| 4 | `shared/integrations/twilio_client.py` | config.py, logger.py | Test: SMS + voice mock (placeholder) |
| 5 | `shared/integrations/email_client.py` | config.py, logger.py | Test: email send mocked |
| 6 | `shared/integrations/zendesk_client.py` | config.py, logger.py | Test: ticket create mocked |

### BUILDER 3 (Day 3) — Dev + Logistics + EHR Clients

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `shared/integrations/github_client.py` | config.py | Test: repo access mocked |
| 2 | `shared/integrations/aftership_client.py` | config.py | Test: tracking mocked |
| 3 | `shared/integrations/epic_ehr_client.py` | config.py | Test: read-only EHR access |
| 4 | `tests/unit/test_integration_clients.py` | All clients | PUSH AFTER PASS |

### BUILDER 4 (Day 4) — Compliance Layer

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `shared/compliance/__init__.py` | None | N/A |
| 2 | `shared/compliance/jurisdiction.py` | config.py | Test: IN client → TCPA rules |
| 3 | `shared/compliance/sla_calculator.py` | config.py | Test: SLA breach calculated |
| 4 | `shared/compliance/gdpr_engine.py` | compliance.py | Test: export + soft-delete |
| 5 | `shared/compliance/healthcare_guard.py` | compliance.py | Test: BAA check, no PHI in logs |
| 6 | `tests/unit/test_compliance_layer.py` | All above | PUSH AFTER PASS |

### BUILDER 5 (Day 5) — T1+T2+T3 Integration

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/unit/test_trivya_tier1_tier2.py` (update) | Full T1+T2+T3 | PUSH AFTER PASS |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/unit/test_trivya_tier3.py tests/unit/test_integration_clients.py tests/unit/test_compliance_layer.py -v

# Integration with ALL previous weeks
pytest tests/integration/test_week1_foundation.py tests/integration/test_week2_database.py tests/integration/test_week2_gsd_kb.py tests/unit/test_trivya_tier1_tier2.py -v
```

**Pass Criteria:**
- Full TRIVYA T1+T2+T3 fires correctly on triggers
- T3 does NOT activate on simple FAQ
- T3 DOES activate on VIP + amount>$100 + anger>80%
- All integration clients initialize (mocked)
- GDPR export + soft-delete work
- Healthcare guard: BAA enforced, no PHI logs
- **ALL previous weeks tests pass**

---

## WEEK 8 — MCP Servers + Guardrails

**Goal:** Build all 11 MCP servers + guardrails

### BUILDER 1 (Day 1) — Base Server + Knowledge MCPs

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `mcp_servers/__init__.py` | None | N/A |
| 2 | `mcp_servers/base_server.py` | config.py, security.py | Test: base server starts |
| 3 | `mcp_servers/knowledge/__init__.py` | None | N/A |
| 4 | `mcp_servers/knowledge/faq_server.py` | base_server.py | Test: FAQ tool responds |
| 5 | `mcp_servers/knowledge/rag_server.py` | base_server.py, rag_pipeline.py | Test: RAG round trip |
| 6 | `mcp_servers/knowledge/kb_server.py` | base_server.py, kb_manager.py | Test: KB tool responds |
| 7 | `tests/unit/test_mcp_knowledge.py` | All above | PUSH AFTER PASS |

### BUILDER 2 (Day 2) — Voice + Chat + Ticketing MCPs

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `mcp_servers/integrations/__init__.py` | None | N/A |
| 2 | `mcp_servers/integrations/email_server.py` | base_server.py, email_client.py | Test: responds <2s |
| 3 | `mcp_servers/integrations/voice_server.py` | base_server.py, twilio_client.py | Test: responds <2s |
| 4 | `mcp_servers/integrations/chat_server.py` | base_server.py | Test: responds <2s |
| 5 | `mcp_servers/integrations/ticketing_server.py` | base_server.py | Test: responds <2s |
| 6 | `tests/unit/test_mcp_integrations.py` | All above | PUSH AFTER PASS |

### BUILDER 3 (Day 3) — E-commerce + CRM + Analytics MCPs

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `mcp_servers/integrations/ecommerce_server.py` | base_server.py, shopify_client.py | Test: ecommerce tool responds |
| 2 | `mcp_servers/integrations/crm_server.py` | base_server.py | Test: CRM tool responds |
| 3 | `mcp_servers/tools/__init__.py` | None | N/A |
| 4 | `mcp_servers/tools/analytics_server.py` | base_server.py | Test: analytics tool responds |
| 5 | `mcp_servers/tools/monitoring_server.py` | base_server.py | Test: monitoring tool responds |

### BUILDER 4 (Day 4) — Notification + Compliance + SLA MCPs + Guardrails

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `mcp_servers/tools/notification_server.py` | base_server.py, notification_service.py | Test: notification tool responds |
| 2 | `mcp_servers/tools/compliance_server.py` | base_server.py, gdpr_engine.py | Test: compliance tool responds |
| 3 | `mcp_servers/tools/sla_server.py` | base_server.py | Test: SLA tool responds |
| 4 | `shared/guardrails/__init__.py` | None | N/A |
| 5 | `shared/guardrails/guardrails.py` | smart_router.py, trivya/ | Test: hallucination blocked, competitor blocked |
| 6 | `shared/guardrails/approval_enforcer.py` | guardrails.py | Test: refund bypass blocked |
| 7 | `tests/unit/test_guardrails.py` | All above | PUSH AFTER PASS |

### BUILDER 5 (Day 5) — Monitoring + Integration Tests

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `monitoring/prometheus.yml` | None | Verify: scrapes all services |
| 2 | `monitoring/alerts.yml` | prometheus.yml | Test: alerts fire correctly |
| 3 | `tests/unit/test_mcp_servers.py` | All MCP files | PUSH AFTER PASS |
| 4 | `tests/integration/test_week8_mcp.py` | All MCP servers | MCP round-trip test |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/integration/test_week8_mcp.py tests/unit/test_guardrails.py tests/unit/test_mcp_servers.py -v

# Integration with ALL previous weeks
pytest tests/integration/test_week1_foundation.py tests/integration/test_week2_database.py tests/integration/test_week2_gsd_kb.py tests/unit/test_trivya_tier1_tier2.py tests/unit/test_trivya_tier3.py tests/unit/test_integration_clients.py -v
```

**Pass Criteria:**
- All 11 MCP servers start without errors
- MCP client connects to all servers via registry
- Each MCP server responds <2 seconds
- Full chain: GSD → TRIVYA → MCP → integration client completes
- Guardrails: hallucination + competitor mention blocked
- Approval enforcer: refund bypass blocked
- Prometheus scrapes all services
- **ALL previous weeks tests pass**

---

# PHASE 4: VARIANTS & INTEGRATIONS (Weeks 9-14) 🔵 IN PROGRESS

---

## WEEK 9 — Mini PARWA Variant ✅ COMPLETE

**Goal:** Build all base agents and Mini PARWA variant

**Status:** COMPLETE - 40 files, 180+ tests passing

### Files Built:

**Builder 1 - Base Agents (12 files):**
- `variants/__init__.py`
- `variants/base_agents/__init__.py`
- `variants/base_agents/base_agent.py`
- `variants/base_agents/base_faq_agent.py`
- `variants/base_agents/base_email_agent.py`
- `variants/base_agents/base_chat_agent.py`
- `variants/base_agents/base_sms_agent.py`
- `variants/base_agents/base_voice_agent.py`
- `variants/base_agents/base_ticket_agent.py`
- `variants/base_agents/base_escalation_agent.py`
- `variants/base_agents/base_refund_agent.py`
- `tests/unit/test_base_agents.py`

**Builder 2 - Mini Config (4 files):**
- `variants/mini/__init__.py`
- `variants/mini/config.py`
- `variants/mini/anti_arbitrage_config.py`
- `tests/unit/test_mini_config.py`

**Builder 3 + 4 - Mini Agents (9 files):**
- All 8 Mini agents
- `tests/unit/test_mini_agents.py`
- `tests/unit/test_base_refund_agent.py`

**Builder 5 - Tools + Workflows (12 files):**
- 5 Tools: faq_search, order_lookup, ticket_create, notification, refund_verification
- 5 Workflows: inquiry, ticket_creation, escalation, order_status, refund_verification
- `tests/unit/test_mini_workflows.py`

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/unit/test_base_agents.py tests/unit/test_mini_config.py tests/unit/test_mini_agents.py tests/unit/test_base_refund_agent.py tests/unit/test_mini_workflows.py -v

# Integration with ALL previous weeks (Weeks 1-8)
pytest tests/integration/test_week1_foundation.py tests/integration/test_week2_database.py tests/integration/test_week2_gsd_kb.py tests/integration/test_week8_mcp.py -v
```

**Pass Criteria:**
- Mini PARWA: FAQ query routes to Light tier
- Mini PARWA: refund creates pending_approval — **Paddle NOT called**
- Mini PARWA: escalation triggers human handoff
- All 8 base agents initialize without errors
- **CRITICAL: Paddle refund gate enforced**
- **ALL previous weeks tests pass**

---

## WEEK 10 — Mini Tasks + PARWA Junior Variant

**Goal:** Build Mini tasks and PARWA Junior variant

### BUILDER 1 (Day 1) — Mini Tasks

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `variants/mini/tasks/__init__.py` | None | N/A |
| 2 | `variants/mini/tasks/answer_faq.py` | Mini agents (Wk9) | Test: FAQ answered |
| 3 | `variants/mini/tasks/process_email.py` | Mini agents | Test: email processed |
| 4 | `variants/mini/tasks/handle_chat.py` | Mini agents | Test: chat handled |
| 5 | `variants/mini/tasks/make_call.py` | Mini agents | Test: call initiated |
| 6 | `variants/mini/tasks/create_ticket.py` | Mini agents | Test: ticket created |
| 7 | `variants/mini/tasks/escalate.py` | Mini agents | Test: escalation fires |
| 8 | `variants/mini/tasks/verify_refund.py` | Mini agents | Test: refund verified (not executed) |
| 9 | `tests/unit/test_mini_tasks.py` | All above | PUSH AFTER PASS |

### BUILDER 2 (Day 2) — PARWA Config + Core Agents

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `variants/parwa/__init__.py` | None | N/A |
| 2 | `variants/parwa/config.py` | config.py (Wk1) | Test: PARWA config loads |
| 3 | `variants/parwa/anti_arbitrage_config.py` | pricing_optimizer.py | Test: 1x PARWA shows 0.5 hrs/day |
| 4 | `variants/parwa/agents/__init__.py` | None | N/A |
| 5 | `variants/parwa/agents/faq_agent.py` | base_faq_agent.py | Test: PARWA FAQ routes to Light |
| 6 | `variants/parwa/agents/email_agent.py` | base_email_agent.py | Test: PARWA email processes |
| 7 | `variants/parwa/agents/chat_agent.py` | base_chat_agent.py | Test: PARWA chat responds |
| 8 | `variants/parwa/agents/sms_agent.py` | base_sms_agent.py | Test: PARWA SMS sends |
| 9 | `variants/parwa/agents/voice_agent.py` | base_voice_agent.py | Test: PARWA voice handles call |
| 10 | `variants/parwa/agents/ticket_agent.py` | base_ticket_agent.py | Test: PARWA ticket created |
| 11 | `variants/parwa/agents/escalation_agent.py` | base_escalation_agent.py | Test: PARWA escalates |
| 12 | `variants/parwa/agents/refund_agent.py` | base_refund_agent.py | Test: PARWA refund → APPROVE/REVIEW/DENY |

### BUILDER 3 (Day 3) — PARWA Unique Agents + Tools

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `variants/parwa/agents/learning_agent.py` | base_agent.py, training_data model | Test: negative_reward on rejection |
| 2 | `variants/parwa/agents/safety_agent.py` | ai_safety.py, base_agent.py | Test: competitor mention blocked |
| 3 | `variants/parwa/tools/__init__.py` | None | N/A |
| 4 | `variants/parwa/tools/knowledge_update.py` | kb_manager.py | Test: KB updated |
| 5 | `variants/parwa/tools/refund_recommendation_tools.py` | paddle_client.py | Test: APPROVE/REVIEW/DENY with reasoning |
| 6 | `variants/parwa/tools/safety_tools.py` | ai_safety.py | Test: safety check runs |

### BUILDER 4 (Day 4) — PARWA Workflows + Tasks

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `variants/parwa/workflows/__init__.py` | None | N/A |
| 2 | `variants/parwa/workflows/refund_recommendation.py` | PARWA agents | Test: recommendation includes reasoning |
| 3 | `variants/parwa/workflows/knowledge_update.py` | PARWA agents | Test: KB updated after resolution |
| 4 | `variants/parwa/workflows/safety_workflow.py` | PARWA agents | Test: safety check before response |
| 5 | `variants/parwa/tasks/__init__.py` | None | N/A |
| 6 | `variants/parwa/tasks/recommend_refund.py` | PARWA agents | Test: APPROVE/REVIEW/DENY returned |
| 7 | `variants/parwa/tasks/update_knowledge.py` | PARWA agents | Test: KB entry added |
| 8 | `variants/parwa/tasks/compliance_check.py` | compliance.py | Test: compliance check runs |

### BUILDER 5 (Day 5) — PARWA Tests + Manager Time

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/unit/test_parwa_agents.py` | All PARWA agents | PUSH AFTER PASS |
| 2 | `tests/unit/test_parwa_workflows.py` | PARWA workflows | PUSH AFTER PASS |
| 3 | `backend/services/manager_time_calculator.py` | pricing_optimizer.py | Test: manager time formula correct |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/unit/test_mini_tasks.py tests/unit/test_parwa_agents.py tests/unit/test_parwa_workflows.py -v

# Integration with ALL previous weeks (Weeks 1-9)
pytest tests/integration/test_week1_foundation.py tests/integration/test_week2_database.py tests/integration/test_week2_gsd_kb.py tests/integration/test_week8_mcp.py tests/unit/test_mini_agents.py tests/unit/test_mini_workflows.py -v
```

**Pass Criteria:**
- PARWA recommendation: includes APPROVE/REVIEW/DENY with reasoning
- PARWA learning agent: negative_reward record on rejection
- PARWA safety agent: competitor mention blocked
- Mini still works alongside PARWA (no conflicts)
- Manager time calculator: 1x PARWA shows 0.5 hrs/day
- **ALL previous weeks tests pass**

---

## WEEK 11 — PARWA High Variant

**Goal:** Build PARWA High variant, verify all 3 variants coexist

### BUILDER 1 (Day 1) — PARWA High Config + Core Advanced Agents

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `variants/parwa_high/__init__.py` | None | N/A |
| 2 | `variants/parwa_high/config.py` | config.py | Test: High config loads |
| 3 | `variants/parwa_high/anti_arbitrage_config.py` | pricing_optimizer.py | Test: High anti-arbitrage correct |
| 4 | `variants/parwa_high/agents/__init__.py` | None | N/A |
| 5 | `variants/parwa_high/agents/video_agent.py` | base_agent.py | Test: video agent initializes |
| 6 | `variants/parwa_high/agents/analytics_agent.py` | base_agent.py | Test: analytics agent runs |
| 7 | `variants/parwa_high/agents/coordination_agent.py` | base_agent.py | Test: coordination manages 5 concurrent |

### BUILDER 2 (Day 2) — PARWA High Customer Success + Compliance Agents

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `variants/parwa_high/agents/customer_success_agent.py` | base_agent.py | Test: churn prediction has risk score |
| 2 | `variants/parwa_high/agents/sla_agent.py` | base_agent.py, sla_calculator.py | Test: SLA breach detected |
| 3 | `variants/parwa_high/agents/compliance_agent.py` | base_agent.py, healthcare_guard.py | Test: HIPAA enforced |
| 4 | `variants/parwa_high/agents/learning_agent.py` | base_agent.py | Test: learning records training data |
| 5 | `variants/parwa_high/agents/safety_agent.py` | base_agent.py | Test: safety blocks unsafe responses |

### BUILDER 3 (Day 3) — PARWA High Tools + Workflows

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `variants/parwa_high/tools/__init__.py` | None | N/A |
| 2 | `variants/parwa_high/tools/analytics_engine.py` | analytics_service.py | Test: insights generated |
| 3 | `variants/parwa_high/tools/team_coordination.py` | base_agent.py | Test: team coordinated |
| 4 | `variants/parwa_high/tools/customer_success_tools.py` | base_agent.py | Test: success tools run |
| 5 | `variants/parwa_high/workflows/__init__.py` | None | N/A |
| 6 | `variants/parwa_high/workflows/video_support.py` | High agents | Test: video workflow starts |
| 7 | `variants/parwa_high/workflows/analytics.py` | High agents | Test: analytics workflow runs |
| 8 | `variants/parwa_high/workflows/coordination.py` | High agents | Test: coordination manages load |
| 9 | `variants/parwa_high/workflows/customer_success.py` | High agents | Test: success workflow runs |

### BUILDER 4 (Day 4) — PARWA High Tasks + DB Migration

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `variants/parwa_high/tasks/__init__.py` | None | N/A |
| 2 | `variants/parwa_high/tasks/video_call.py` | High agents | Test: video call task runs |
| 3 | `variants/parwa_high/tasks/generate_insights.py` | High agents | Test: insights with risk score |
| 4 | `variants/parwa_high/tasks/coordinate_teams.py` | High agents | Test: teams coordinated |
| 5 | `variants/parwa_high/tasks/customer_success.py` | High agents | Test: success tasks complete |
| 6 | `tests/unit/test_parwa_high_agents.py` | High agents | PUSH AFTER PASS |
| 7 | `tests/unit/test_parwa_high_workflows.py` | High workflows | PUSH AFTER PASS |
| 8 | `database/migrations/versions/007_multi_region.py` | 001_initial_schema.py | Test: migration runs |

### BUILDER 5 (Day 5) — All 3 Variants Coexistence + BDD Tests

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/integration/test_week11_parwa_high.py` | All 3 variants | Test: same ticket through all 3 |
| 2 | `tests/integration/test_full_system.py` | All variants | Skeleton full system test |
| 3 | `tests/bdd/__init__.py` | None | N/A |
| 4 | `tests/bdd/test_mini_scenarios.py` | Mini variant | BDD: all Mini scenarios pass |
| 5 | `tests/bdd/test_parwa_scenarios.py` | PARWA variant | BDD: all PARWA scenarios pass |
| 6 | `tests/bdd/test_parwa_high_scenarios.py` | PARWA High | BDD: all High scenarios pass |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/integration/test_week11_parwa_high.py tests/integration/test_full_system.py tests/bdd/ -v

# Integration with ALL previous weeks (Weeks 1-10)
pytest tests/integration/test_week1_foundation.py tests/integration/test_week2_database.py tests/integration/test_week2_gsd_kb.py tests/integration/test_week8_mcp.py tests/unit/test_mini_agents.py tests/unit/test_parwa_agents.py -v
```

**Pass Criteria:**
- All 3 variants import simultaneously with zero conflicts
- PARWA High: churn prediction has risk score
- PARWA High: video agent initializes
- Same ticket through all 3: Mini collects, PARWA recommends, High executes on approval
- BDD scenarios: all pass for all 3 variants
- DB migration 007: runs without errors
- **ALL previous weeks tests pass**

---

## WEEK 12 — Backend Services Complete

**Goal:** Build approval, escalation, industry configs, Jarvis, webhooks, E2E tests

### BUILDER 1 (Day 1) — Industry Configs + Jarvis Commands

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `backend/core/__init__.py` | None | N/A |
| 2 | `backend/core/jarvis_commands.py` | cache.py, security.py | Test: pause_refunds Redis key <500ms |
| 3 | `backend/core/industry_configs/__init__.py` | None | N/A |
| 4 | `backend/core/industry_configs/ecommerce.py` | config.py | Test: ecommerce config loads |
| 5 | `backend/core/industry_configs/saas.py` | config.py | Test: saas config loads |
| 6 | `backend/core/industry_configs/healthcare.py` | config.py, healthcare_guard.py | Test: healthcare + BAA check |
| 7 | `backend/core/industry_configs/logistics.py` | config.py | Test: logistics config loads |
| 8 | `backend/api/incoming_calls.py` | config.py | Test: call answered <6s |
| 9 | `backend/services/voice_handler.py` | incoming_calls.py | Test: 5-step call flow runs |

### BUILDER 2 (Day 2) — Approval + Escalation Services

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `backend/services/__init__.py` | None | N/A |
| 2 | `backend/services/approval_service.py` | support_ticket, paddle_client.py | Test: pending_approval created, **Paddle NOT called** |
| 3 | `backend/services/escalation_ladder.py` | approval_service.py | Test: 4-phase escalation at correct hours |
| 4 | `backend/services/escalation_service.py` | support_ticket model | Test: escalation service runs |
| 5 | `backend/services/license_service.py` (update) | license model | Test: license checked |
| 6 | `backend/services/sla_service.py` (update) | sla_breach model | Test: SLA breach detected |

### BUILDER 3 (Day 3) — Webhook Handlers + Automation + NLP

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `backend/api/webhooks/twilio.py` | hmac_verification.py | Test: bad HMAC returns 401 |
| 2 | `backend/api/automation.py` | all agents | Test: automation endpoint works |
| 3 | `backend/services/manager_time_calculator.py` (update) | pricing_optimizer.py | Test: formula correct |
| 4 | `backend/services/non_financial_undo.py` | audit_trail.py, Redis | Test: non-money action undone, logged |
| 5 | `backend/nlp/__init__.py` | None | N/A |
| 6 | `backend/nlp/command_parser.py` | config.py | Test: Add 2 Mini → {action:provision,count:2,type:mini} |

### BUILDER 4 (Day 4) — E2E Test Files

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/e2e/__init__.py` | None | N/A |
| 2 | `tests/e2e/test_onboarding_flow.py` | All backend services | E2E: signup→onboarding→live |
| 3 | `tests/e2e/test_refund_workflow.py` | approval_service.py | E2E: **Paddle called ONCE after approval** |
| 4 | `tests/e2e/test_jarvis_commands.py` | jarvis_commands.py | E2E: pause_refunds Redis <500ms |
| 5 | `tests/e2e/test_stuck_ticket_escalation.py` | escalation_service.py | E2E: 4-phase at 24h/48h/72h |

### BUILDER 5 (Day 5) — More E2E + NLP Provisioner + Voice Tests

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/e2e/test_agent_lightning.py` | training_data model | E2E: full training cycle |
| 2 | `tests/e2e/test_gdpr_compliance.py` | gdpr_engine.py | E2E: PII anonymised, row preserved |
| 3 | `backend/nlp/provisioner.py` | command_parser.py | Test: agents spun up, billing updated |
| 4 | `backend/nlp/intent_classifier.py` | command_parser.py | Test: intent classified |
| 5 | `tests/voice/__init__.py` | None | N/A |
| 6 | `tests/voice/test_incoming_calls.py` | incoming_calls.py, voice_handler.py | Test: answer <6s, recording disclosure |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/e2e/test_refund_workflow.py tests/e2e/test_jarvis_commands.py tests/integration/test_week12_backend.py -v

# Integration with ALL previous weeks (Weeks 1-11)
pytest tests/integration/test_week1_foundation.py tests/integration/test_week2_database.py tests/integration/test_week2_gsd_kb.py tests/integration/test_week8_mcp.py tests/integration/test_week11_parwa_high.py -v
```

**Pass Criteria:**
- Refund E2E: **Paddle called exactly once — after approval, NEVER before**
- Audit trail: hash chain validates after approval
- Stuck ticket: 4-phase escalation at 24h/48h/72h thresholds
- Jarvis: pause_refunds Redis key <500ms
- GDPR: export complete, deletion anonymises PII, row preserved
- Incoming calls: answered <6s, never IVR-only
- **ALL previous weeks tests pass**

---

## WEEK 13 — Agent Lightning Training System

**Goal:** Build Agent Lightning training system and all background workers

### BUILDER 1 (Day 1) — Data Export + Model Registry

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `agent_lightning/__init__.py` | None | N/A |
| 2 | `agent_lightning/data/__init__.py` | None | N/A |
| 3 | `agent_lightning/data/export_mistakes.py` | training_data model | Test: mistakes exported in JSONL |
| 4 | `agent_lightning/data/export_approvals.py` | training_data model | Test: approvals exported |
| 5 | `agent_lightning/data/dataset_builder.py` | export_mistakes.py, export_approvals.py | Test: JSONL dataset built |
| 6 | `agent_lightning/deployment/__init__.py` | None | N/A |
| 7 | `agent_lightning/deployment/model_registry.py` | config.py | Test: model version registered |

### BUILDER 2 (Day 2) — Training Pipeline

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `agent_lightning/training/__init__.py` | None | N/A |
| 2 | `agent_lightning/training/trainer.py` | config.py (uses Unsloth+Colab FREE) | Test: trainer initializes |
| 3 | `agent_lightning/training/unsloth_optimizer.py` | trainer.py | Test: Unsloth optimizer applies |
| 4 | `agent_lightning/deployment/deploy_model.py` | model_registry.py | Test: model deployed |
| 5 | `agent_lightning/deployment/rollback.py` | model_registry.py | Test: rollback restores previous |

### BUILDER 3 (Day 3) — Fine Tune + Validation + Monitoring

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `agent_lightning/training/fine_tune.py` | trainer.py, unsloth_optimizer.py | Test: fine tune runs on test dataset |
| 2 | `agent_lightning/training/validate.py` | trainer.py | Test: blocks at 89%, allows at 91% |
| 3 | `agent_lightning/monitoring/__init__.py` | None | N/A |
| 4 | `agent_lightning/monitoring/drift_detector.py` | model_registry.py | Test: drift detected after change |
| 5 | `agent_lightning/monitoring/accuracy_tracker.py` | model_registry.py | Test: accuracy tracked per category |

### BUILDER 4 (Day 4) — Background Workers

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `workers/__init__.py` | None | N/A |
| 2 | `workers/worker.py` | config.py, message_queue.py | Test: ARQ worker registers |
| 3 | `workers/batch_approval.py` | escalation_service.py | Test: batch processes |
| 4 | `workers/training_job.py` | fine_tune.py | Test: training job triggered |
| 5 | `workers/cleanup.py` | gdpr_engine.py | Test: cleanup runs, PII anonymised |
| 6 | `backend/services/burst_mode.py` | billing_service.py, feature_flags/ | Test: burst mode activates, billing updated |

### BUILDER 5 (Day 5) — Remaining Workers + Quality Coach

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `workers/recall_handler.py` | cache.py | Test: recall stops non-money actions |
| 2 | `workers/proactive_outreach.py` | notification_service.py | Test: outreach sent proactively |
| 3 | `workers/report_generator.py` | analytics_service.py | Test: report generated |
| 4 | `workers/kb_indexer.py` | rag_pipeline.py | Test: KB indexed |
| 5 | `backend/quality_coach/__init__.py` | None | N/A |
| 6 | `backend/quality_coach/analyzer.py` | config.py | Test: scores accuracy/empathy/efficiency |
| 7 | `backend/quality_coach/reporter.py` | analyzer.py | Test: weekly report generated |
| 8 | `backend/quality_coach/notifier.py` | analyzer.py | Test: real-time alert fires |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/e2e/test_agent_lightning.py tests/integration/test_week13_workers.py -v

# Integration with ALL previous weeks (Weeks 1-12)
pytest tests/integration/test_week1_foundation.py tests/integration/test_week2_database.py tests/integration/test_week2_gsd_kb.py tests/integration/test_week8_mcp.py tests/integration/test_week11_parwa_high.py tests/e2e/test_refund_workflow.py -v
```

**Pass Criteria:**
- Dataset builder: exports correct JSONL with 50+ mistakes
- validate.py: blocks deployment at <90% accuracy
- validate.py: allows deployment at 91%+ accuracy
- New model version registered after deployment
- All 8 workers start and register with ARQ
- Burst mode: activates instantly, billing updated, auto-expires
- **ALL previous weeks tests pass**

---

## WEEK 14 — Monitoring + Phase 1-3 Validation

**Goal:** Build monitoring dashboards, alerts, performance tests, Phase 1-3 validation

### BUILDER 1 (Day 1) — Grafana Dashboards

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `monitoring/grafana-dashboards/__init__.py` | None | N/A |
| 2 | `monitoring/grafana-dashboards/main-dashboard.json` | None | Verify: loads in Grafana |
| 3 | `monitoring/grafana-dashboards/mcp-dashboard.json` | None | Verify: MCP metrics shown |
| 4 | `monitoring/grafana-dashboards/compliance-dashboard.json` | None | Verify: compliance metrics |
| 5 | `monitoring/grafana-dashboards/sla-dashboard.json` | None | Verify: SLA metrics |
| 6 | `monitoring/grafana-dashboards/quality.json` | None | Verify: quality coach metrics |

### BUILDER 2 (Day 2) — Alert Rules + Logging Config

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `monitoring/alerts.yml` (update) | prometheus.yml | Test: all 6 alerts fire on conditions |
| 2 | `monitoring/grafana-config.yml` | None | Verify: Grafana config valid |
| 3 | `monitoring/logs/__init__.py` | None | N/A |
| 4 | `monitoring/logs/structured-logging-config.yml` | logger.py | Verify: logs in JSON format |
| 5 | `docs/runbook.md` | None | Doc only |

### BUILDER 3 (Day 3) — Performance + BDD + Integration Tests

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/performance/__init__.py` | None | N/A |
| 2 | `tests/performance/test_load.py` | All backend APIs | Test: P95 <500ms at 50 users |
| 3 | `tests/ui/__init__.py` | None | N/A |
| 4 | `tests/ui/test_approval_queue.py` | None | Test: approval queue renders |
| 5 | `tests/ui/test_roi_calculator.py` | None | Test: ROI calculator correct |
| 6 | `tests/ui/test_jarvis_terminal.py` | None | Test: Jarvis terminal works |
| 7 | `tests/bdd/__init__.py` (update) | None | N/A |
| 8 | `tests/bdd/test_mini_scenarios.py` (complete) | Mini variant | BDD: complete scenario suite |
| 9 | `tests/integration/test_week4_backend_api.py` | All APIs | Integration: full API layer |

### BUILDER 4 (Day 4) — Industry-Specific Integration Tests

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/integration/test_ecommerce_industry.py` | ecommerce config | Integration: ecommerce flow |
| 2 | `tests/integration/test_saas_industry.py` | saas config | Integration: SaaS flow |
| 3 | `tests/integration/test_healthcare_industry.py` | healthcare config | Integration: HIPAA enforced |
| 4 | `tests/integration/test_logistics_industry.py` | logistics config | Integration: logistics flow |

### BUILDER 5 (Day 5) — Full System Test + Dockerfiles + PROJECT_STATE

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/integration/test_full_system.py` (complete) | Everything | Full system: all 3 variants + backend + workers |
| 2 | `infra/docker/frontend.Dockerfile` | None | Test: builds <500MB |
| 3 | `docker-compose.prod.yml` (update) | All Dockerfiles | Test: all services start healthy |
| 4 | `PROJECT_STATE.md` (Phase 1-3 complete marker) | None | State: Phases 1-3 complete |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/integration/test_full_system.py tests/performance/test_load.py -v

# Integration with ALL previous weeks (Weeks 1-13)
pytest tests/integration/ tests/e2e/ -v --tb=short
```

**Pass Criteria:**
- test_full_system.py: all tests pass
- P95 latency <500ms at 50 concurrent users
- All 6 monitoring alerts fire correctly
- All 4 industry configurations work
- docker-compose.prod.yml: all services healthy
- BDD: all Mini scenarios pass
- Safety: guardrails.py blocks hallucination, competitor, PII
- **ALL previous weeks tests pass**
- **PHASE 1-3 COMPLETE**

---

# PHASE 5: FRONTEND FOUNDATION (Weeks 15-18)

---

## WEEK 15 — Frontend Foundation

**Goal:** Build Next.js frontend foundation

### BUILDER 1 (Day 1) — Next.js Config → Layout → Landing Page → UI Primitives

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `frontend/next.config.js` | None | Verify: Next.js config valid |
| 2 | `frontend/tailwind.config.js` | None | Verify: Tailwind config valid |
| 3 | `frontend/app/layout.tsx` | None | Test: layout renders |
| 4 | `frontend/app/page.tsx` | None | Test: landing page renders |
| 5 | `frontend/components/ui/button.tsx` | None | Test: button renders |
| 6 | `frontend/components/ui/input.tsx` | None | Test: input renders |
| 7 | `frontend/components/ui/card.tsx` | None | Test: card renders |

### BUILDER 2 (Day 2) — Common UI + Auth Pages

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `frontend/components/common/header.tsx` | None | Test: header renders |
| 2 | `frontend/components/common/sidebar.tsx` | None | Test: sidebar renders |
| 3 | `frontend/app/auth/login/page.tsx` | None | Test: login page renders |
| 4 | `frontend/app/auth/signup/page.tsx` | None | Test: signup page renders |
| 5 | `frontend/app/auth/forgot-password/page.tsx` | None | Test: forgot password renders |

### BUILDER 3 (Day 3) — Variant Cards

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `frontend/components/pricing/mini-card.tsx` | None | Test: Mini card renders |
| 2 | `frontend/components/pricing/parwa-card.tsx` | None | Test: PARWA card renders |
| 3 | `frontend/components/pricing/parwa-high-card.tsx` | None | Test: PARWA High card renders |
| 4 | `frontend/components/pricing/comparison-table.tsx` | All cards | Test: comparison renders |

### BUILDER 4 (Day 4) — Stores + API Service

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `frontend/stores/auth-store.ts` | None | Test: auth store initializes |
| 2 | `frontend/stores/tenant-store.ts` | None | Test: tenant store initializes |
| 3 | `frontend/stores/approval-store.ts` | None | Test: approval store initializes |
| 4 | `frontend/lib/api-client.ts` | None | Test: API client works |
| 5 | `frontend/lib/auth.ts` | None | Test: auth lib works |

### BUILDER 5 (Day 5) — Onboarding Components

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `frontend/components/onboarding/step-1.tsx` | None | Test: step 1 renders |
| 2 | `frontend/components/onboarding/step-2.tsx` | None | Test: step 2 renders |
| 3 | `frontend/components/onboarding/step-3.tsx` | None | Test: step 3 renders |
| 4 | `frontend/components/onboarding/step-4.tsx` | None | Test: step 4 renders |
| 5 | `frontend/components/onboarding/step-5.tsx` | None | Test: step 5 renders |
| 6 | `frontend/components/onboarding/wizard.tsx` | All steps | Test: wizard flow works |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
npm run test -- tests/ui/ && pytest tests/integration/test_week15_frontend.py

# Integration with ALL previous weeks (Weeks 1-14)
pytest tests/integration/test_week1_foundation.py tests/integration/test_week2_database.py tests/integration/test_week8_mcp.py tests/integration/test_full_system.py -v
```

**Pass Criteria:**
- Next.js dev server starts without errors
- All 3 variant cards render correctly
- Auth pages render and validate
- Onboarding wizard 5-step flow works
- All Zustand stores initialize
- **ALL previous weeks tests pass**

---

## WEEK 16 — Dashboard Pages + Hooks

**Goal:** Build all dashboard pages and hooks

### BUILDER 1 (Day 1) — Dashboard Layout + Home Page

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `frontend/app/dashboard/layout.tsx` | None | Test: dashboard layout renders |
| 2 | `frontend/app/dashboard/page.tsx` | None | Test: home page loads real API data |
| 3 | `frontend/components/dashboard/stats-card.tsx` | None | Test: stats card renders |

### BUILDER 2 (Day 2) — Tickets + Approvals + Agents + Analytics Pages

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `frontend/app/dashboard/tickets/page.tsx` | None | Test: tickets page renders |
| 2 | `frontend/app/dashboard/approvals/page.tsx` | None | Test: approvals queue renders + approve action |
| 3 | `frontend/app/dashboard/agents/page.tsx` | None | Test: agents page renders |
| 4 | `frontend/app/dashboard/analytics/page.tsx` | None | Test: analytics page renders |

### BUILDER 3 (Day 3) — Dashboard Components

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `frontend/components/dashboard/ticket-list.tsx` | None | Test: ticket list renders |
| 2 | `frontend/components/dashboard/approval-queue.tsx` | None | Test: approval queue renders |
| 3 | `frontend/components/dashboard/jarvis-terminal.tsx` | None | Test: Jarvis terminal streams response |
| 4 | `frontend/components/dashboard/agent-status.tsx` | None | Test: agent status renders |

### BUILDER 4 (Day 4) — All Hooks

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `frontend/hooks/use-auth.ts` | None | Test: use-auth hook works |
| 2 | `frontend/hooks/use-approvals.ts` | None | Test: use-approvals updates store |
| 3 | `frontend/hooks/use-tickets.ts` | None | Test: use-tickets hook works |
| 4 | `frontend/hooks/use-analytics.ts` | None | Test: use-analytics hook works |
| 5 | `frontend/hooks/use-jarvis.ts` | None | Test: use-jarvis hook works |

### BUILDER 5 (Day 5) — Settings Pages

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `frontend/app/dashboard/settings/page.tsx` | None | Test: settings page renders |
| 2 | `frontend/app/dashboard/settings/profile/page.tsx` | None | Test: profile settings renders |
| 3 | `frontend/app/dashboard/settings/billing/page.tsx` | None | Test: billing settings renders |
| 4 | `frontend/app/dashboard/settings/team/page.tsx` | None | Test: team settings renders |
| 5 | `frontend/app/dashboard/settings/integrations/page.tsx` | None | Test: integrations settings renders |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
npm run test && pytest tests/integration/test_week16_dashboard.py

# Integration with ALL previous weeks
pytest tests/integration/ tests/e2e/ -v --tb=short
```

**Pass Criteria:**
- Dashboard home loads real API data
- Approvals queue renders and approve action works
- Jarvis terminal streams response
- All 5 hooks update stores correctly
- **ALL previous weeks tests pass**

---

## WEEK 17 — Onboarding + Analytics + Frontend Wiring

**Goal:** Complete onboarding, analytics, frontend-backend wiring

### BUILDER 1 (Day 1) — Onboarding + Pricing + Analytics Components

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `frontend/components/onboarding/knowledge-upload.tsx` | None | Test: KB upload works |
| 2 | `frontend/components/onboarding/industry-select.tsx` | None | Test: industry select works |
| 3 | `frontend/components/pricing/calculator.tsx` | None | Test: pricing calculator works |
| 4 | `frontend/components/analytics/chart.tsx` | None | Test: chart renders |

### BUILDER 2 (Day 2) — Settings Sub-Pages

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `frontend/app/dashboard/settings/notifications/page.tsx` | None | Test: notification settings renders |
| 2 | `frontend/app/dashboard/settings/security/page.tsx` | None | Test: security settings renders |
| 3 | `frontend/app/dashboard/settings/api-keys/page.tsx` | None | Test: API keys settings renders |

### BUILDER 3 (Day 3) — Frontend Tests

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/ui/test_onboarding_flow.py` | All onboarding | Test: full onboarding flow |
| 2 | `tests/ui/test_dashboard_flow.py` | All dashboard | Test: full dashboard flow |
| 3 | `tests/ui/test_settings_flow.py` | All settings | Test: full settings flow |

### BUILDER 4 (Day 4) — Frontend → Backend Service Wiring

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `frontend/lib/services/approval-service.ts` | API client | Test: approval service works |
| 2 | `frontend/lib/services/ticket-service.ts` | API client | Test: ticket service works |
| 3 | `frontend/lib/services/analytics-service.ts` | API client | Test: analytics service works |
| 4 | `frontend/lib/services/jarvis-service.ts` | API client | Test: Jarvis service works |

### BUILDER 5 (Day 5) — E2E Frontend Tests

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/e2e/test_frontend_full_flow.py` | All frontend + backend | Test: full UI flow |
| 2 | `tests/e2e/test_ui_approval_flow.py` | Approval UI + backend | Test: approve refund through UI |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/e2e/test_frontend_full_flow.py

# Integration with ALL previous weeks
pytest tests/integration/ tests/e2e/ -v --tb=short
```

**Pass Criteria:**
- Full UI: login→onboarding→dashboard works
- Approve refund through UI: **Paddle called exactly once**
- Analytics page loads real backend data
- Lighthouse score >80
- **ALL previous weeks tests pass**

---

## WEEK 18 — Production Hardening + Kubernetes

**Goal:** Production hardening and Kubernetes deployment

### BUILDER 1 (Day 1) — Full Test Suite

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/reports/coverage-report.py` | All tests | Generate coverage report |
| 2 | Run full test suite | All tests | All tests pass |

### BUILDER 2 (Day 2) — Security + Performance Scans

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `security/owasp-scan.py` | None | OWASP: all 10 checks pass |
| 2 | `security/cve-scan.py` | All Docker images | Zero critical CVEs |
| 3 | `tests/security/rls-isolation-test.py` | All DB | RLS: 10 cross-tenant isolation tests |

### BUILDER 3 (Day 3) — Prod Docker Builds

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `infra/docker/backend.Dockerfile` (prod) | None | Test: builds <500MB |
| 2 | `infra/docker/worker.Dockerfile` (prod) | None | Test: builds <300MB |
| 3 | `infra/docker/mcp.Dockerfile` (prod) | None | Test: builds <300MB |

### BUILDER 4 (Day 4) — K8s Manifests

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `infra/k8s/namespace.yaml` | None | Verify: namespace valid |
| 2 | `infra/k8s/backend-deployment.yaml` | None | Verify: deployment valid |
| 3 | `infra/k8s/frontend-deployment.yaml` | None | Verify: deployment valid |
| 4 | `infra/k8s/worker-deployment.yaml` | None | Verify: deployment valid |
| 5 | `infra/k8s/mcp-deployment.yaml` | None | Verify: deployment valid |
| 6 | `infra/k8s/redis-deployment.yaml` | None | Verify: deployment valid |
| 7 | `infra/k8s/postgresql-deployment.yaml` | None | Verify: deployment valid |
| 8 | `infra/k8s/ingress.yaml` | None | Verify: ingress valid |
| 9 | `infra/k8s/configmap.yaml` | None | Verify: configmap valid |
| 10 | `infra/k8s/secrets.yaml` | None | Verify: secrets valid |

### BUILDER 5 (Day 5) — K8s Services + HPA + Final Validation

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `infra/k8s/services.yaml` | None | Verify: services valid |
| 2 | `infra/k8s/hpa.yaml` | None | Verify: HPA valid |
| 3 | `docker-compose.prod.yml` (final) | All Dockerfiles | Test: all services healthy |
| 4 | `PROJECT_STATE.md` (Phase 5 complete) | None | State: Phase 5 complete |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/ && snyk test && locust -f tests/performance/test_load.py --headless -u 100

# Full integration test
pytest tests/integration/ tests/e2e/ -v --tb=short
```

**Pass Criteria:**
- Full test suite: 100% pass rate
- Zero critical CVEs
- OWASP: clean
- P95 <500ms at 100 concurrent users
- docker-compose.prod.yml: all services healthy
- K8s manifests: all valid
- **ALL previous weeks tests pass**
- **PHASE 5 COMPLETE**

---

# PHASE 6: FIRST CLIENTS (Weeks 19-20)

---

## WEEK 19 — First Client Onboarding + Real Validation

**Goal:** Onboard first real client, validate system works with real data

### BUILDER 1 (Day 1) — Client 1 Config + Onboarding

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `clients/client_001/config.json` | config.py | Test: client config loads |
| 2 | `clients/client_001/knowledge/` | kb_manager.py | Test: KB initialized |
| 3 | `clients/client_001/agents/` | All variants | Test: agents configured |

### BUILDER 2 (Day 2) — Client 1 Data Migration

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `clients/client_001/migrations/` | database.py | Test: data migrated |
| 2 | `scripts/migrate_client_data.py` | None | Test: migration script works |

### BUILDER 3 (Day 3) — Shadow Mode Deployment

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `backend/services/shadow_mode.py` | All agents | Test: shadow mode works |
| 2 | `tests/integration/test_shadow_mode.py` | shadow_mode.py | Test: shadow logs correctly |

### BUILDER 4 (Day 4) — Client 1 Validation

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/integration/test_client_001.py` | All client 1 files | Test: client 1 end-to-end |
| 2 | `reports/client_001_validation.md` | None | Validation report |

### BUILDER 5 (Day 5) — Performance Baseline

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/performance/baseline_metrics.py` | None | Test: baseline established |
| 2 | `reports/performance_baseline.md` | None | Performance report |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/integration/test_shadow_mode.py tests/integration/test_client_001.py tests/performance/baseline_metrics.py

# Full integration (Weeks 1-18)
pytest tests/integration/ tests/e2e/ -v --tb=short
```

**Pass Criteria:**
- Shadow mode: logs correctly without affecting live
- Client 1 config: loads correctly
- Client 1 KB: initialized with real data
- Client 1 E2E: all workflows pass
- Performance baseline: documented
- **ALL previous weeks tests pass**

---

## WEEK 20 — Second Client + Agent Lightning First Run

**Goal:** Onboard second client, run first Agent Lightning training

### BUILDER 1 (Day 1) — Client 2 Config + Onboarding

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `clients/client_002/config.json` | config.py | Test: client 2 config loads |
| 2 | `clients/client_002/knowledge/` | kb_manager.py | Test: KB initialized |

### BUILDER 2 (Day 2) — Agent Lightning Week 1 Run

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | Run training cycle | training_data | Test: accuracy ≥80% |

### BUILDER 3 (Day 3) — Multi-Tenant Isolation Validation

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `tests/integration/test_multi_client_isolation.py` | All clients | Test: 2-client isolation |

### BUILDER 4 (Day 4) — Client Success Tooling

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `backend/services/client_success_service.py` | All services | Test: success metrics tracked |
| 2 | `frontend/app/dashboard/client-success/page.tsx` | None | Test: success dashboard renders |

### BUILDER 5 (Day 5) — Documentation + State Update

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `docs/client_onboarding_guide.md` | None | Doc only |
| 2 | `PROJECT_STATE.md` (Phase 6 complete) | None | State: Phase 6 complete |

### TESTER AGENT (Day 6)

**Command:**
```bash
# Current week tests
pytest tests/integration/test_multi_client_isolation.py && pytest tests/

# Full integration (Weeks 1-19)
pytest tests/integration/ tests/e2e/ -v --tb=short
```

**Pass Criteria:**
- 2-client isolation: 0 data leaks in 100 tests
- Agent Lightning: ≥80% accuracy after first run
- Client success dashboard: renders with real data
- Both clients: fully operational
- **ALL previous weeks tests pass**
- **PHASE 6 COMPLETE**

---

# PHASE 7: SCALE TO 20 CLIENTS (Weeks 21-27)

---

## WEEK 21 — Clients 3-5 + Collective Intelligence

**Goal:** Scale to 5 clients, build collective intelligence (NO PII)

### BUILDER 1-5 — Client Onboarding + Collective Intelligence

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `clients/client_003/` through `clients/client_005/` | config.py | Test: all configs load |
| 2 | `agent_lightning/collective/__init__.py` | None | N/A |
| 3 | `agent_lightning/collective/anonymizer.py` | None | Test: PII stripped |
| 4 | `agent_lightning/collective/aggregator.py` | anonymizer.py | Test: patterns aggregated |
| 5 | `tests/integration/test_collective_intelligence.py` | All above | Test: collective works, NO PII |

### TESTER AGENT (Day 6)

**Command:**
```bash
pytest tests/integration/test_multi_client_isolation.py tests/integration/test_collective_intelligence.py && pytest tests/
```

**Pass Criteria:**
- 5-client isolation: 0 data leaks
- Collective intelligence: patterns shared, PII stripped
- Agent Lightning Week 3 Run: ≥82% accuracy

---

## WEEK 22 — Clients 6-10 + 85% Accuracy Milestone

**Goal:** Scale to 10 clients, reach 85% Agent Lightning accuracy

### BUILDER 1-5 — Client Onboarding + Training Optimisation

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `clients/client_006/` through `clients/client_010/` | config.py | Test: all configs load |
| 2 | `tests/integration/test_10_client_isolation.py` | All clients | Test: 10-client isolation |
| 3 | `tests/performance/test_10_client_load.py` | All clients | Test: 500 concurrent users |
| 4 | Agent Lightning Week 6 Run | All training | Test: ≥85% accuracy |

### TESTER AGENT (Day 6)

**Command:**
```bash
pytest tests/integration/test_10_client_isolation.py && locust -u 500 && pytest tests/
```

**Pass Criteria:**
- 10-client isolation: 0 data leaks in 200 tests
- 500 concurrent users: P95 <500ms
- Agent Lightning: ≥85% accuracy

---

## WEEKS 23-27 — Polish + Client Success + Performance (Compact)

| Week | Goal | Key Files |
|------|------|-----------|
| 23 | Frontend Polish (A11y + Mobile + Dark Mode) | `frontend/` accessibility, responsive |
| 24 | Client Success Tooling | `backend/services/client_success/` |
| 25 | Financial Services Industry Vertical | `variants/financial_services/` |
| 26 | Performance Deep Optimisation (P95 <300ms) | `shared/utils/*_cache.py`, `database/indexes/` |
| 27 | 20-Client Scale Validation | `clients/011-020/`, `tests/performance/test_20_client_load.py` |

### TESTER AGENT (Day 6) — Each Week

**Command:**
```bash
pytest tests/integration/ tests/e2e/ tests/performance/ -v --tb=short
```

**Pass Criteria (Week 27):**
- 20-client isolation: 0 data leaks
- 500 concurrent users: P95 <300ms
- Agent Lightning: ≥88% accuracy
- **PHASE 7 COMPLETE**

---

# PHASE 8: ENTERPRISE PREPARATION (Weeks 28-40)

---

## WEEK 28 — Agent Lightning 90% Milestone

**Goal:** Reach 90% Agent Lightning accuracy

### BUILDER 1-5 — Training Pipeline Optimisations

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `agent_lightning/training/category_specialists.py` | trainer.py | Test: specialists work |
| 2 | `agent_lightning/training/active_learning.py` | None | Test: active learning works |
| 3 | `agent_lightning/monitoring/ab_testing.py` | None | Test: A/B test works |
| 4 | `agent_lightning/deployment/auto_rollback.py` | None | Test: rollback triggers |
| 5 | Training run with 90% target | All training | Test: accuracy ≥90% |

### TESTER AGENT (Day 6)

**Command:**
```bash
pytest tests/ && pytest tests/integration/ tests/e2e/ -v --tb=short
```

**Pass Criteria:**
- Agent Lightning accuracy ≥90%
- A/B test: new model serves 10% of traffic correctly
- Auto-rollback: fires within 60 seconds of drift
- Collective intelligence: no PII in cross-client data

---

## WEEK 29 — Multi-Region Data Residency

**Goal:** Build multi-region infrastructure for data compliance

### BUILDER 1-5 — Multi-Region Infrastructure

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | `infra/terraform/regions/eu/` | None | Test: EU region works |
| 2 | `infra/terraform/regions/us/` | None | Test: US region works |
| 3 | `infra/terraform/regions/apac/` | None | Test: APAC region works |
| 4 | `backend/compliance/residency_enforcer.py` | None | Test: residency enforced |
| 5 | `backend/compliance/cross_region_replication.py` | None | Test: replication works |

### TESTER AGENT (Day 6)

**Command:**
```bash
pytest tests/integration/ -v --tb=short
```

**Pass Criteria:**
- EU client data absent from US region DB
- Cross-region isolation: 0 leaks
- DB replication lag <500ms
- GDPR export: only data from client's assigned region

---

## WEEK 30 — 30-Client Milestone

**Goal:** Scale to 30 clients, validate all systems

### BUILDER 1-5 — Scale Validation

| # | File | Depends On | Test |
|---|------|------------|------|
| 1 | Clients 21-30 configs | config.py | Test: all configs load |
| 2 | Full regression all test suites | All tests | 100% pass rate |
| 3 | Security re-audit | All systems | Zero critical issues |
| 4 | Agent Lightning week 15 run | All training | ≥91% accuracy |
| 5 | 30-client load test | All clients | 1000 users P95 <300ms |

### TESTER AGENT (Day 6)

**Command:**
```bash
pytest tests/ && snyk test && locust -u 1000
```

**Pass Criteria:**
- 300 cross-tenant isolation tests: 0 data leaks
- 1000 concurrent users: P95 <300ms
- Agent Lightning: ≥91%
- Full regression: 100% pass rate
- OWASP clean, CVEs zero critical

---

## WEEKS 31-40 — Enterprise Preparation (Compact)

| Week | Goal | Key Files |
|------|------|-----------|
| 31 | E-commerce Advanced | `variants/ecommerce/advanced/` |
| 32 | SaaS Advanced | `variants/saas/advanced/` |
| 33 | Healthcare HIPAA + Logistics | `variants/healthcare/`, `variants/logistics/` |
| 34 | Frontend v2 (React Query + PWA) | `frontend/v2/` |
| 35 | Smart Router 92%+ | `shared/smart_router/ml_classifier.py` |
| 36 | Agent Lightning 94% | `agent_lightning/training/category_specialists.py` |
| 37 | 50-Client Scale + Autoscaling | `clients/` + `infra/k8s/hpa/` |
| 38 | Enterprise Pre-Preparation | `backend/sso/`, `backend/enterprise/` |
| 39 | Final Production Readiness | Security hardening, docs |
| 40 | Weeks 1-40 Final Validation | Full test suite, enterprise demo |

### TESTER AGENT (Day 6) — Week 40

**Command:**
```bash
pytest tests/ && snyk test && locust -u 2000
```

**Pass Criteria:**
- Full test suite: 100% pass
- Zero critical CVEs
- OWASP clean
- P95 <300ms at 2000 users
- Agent Lightning: ≥94%
- **PHASE 8 COMPLETE**

---

# PHASE 9: CLOUD MIGRATION (Weeks 41-44)

---

## WEEKS 41-44 — Cloud Migration

| Week | Goal | Key Files |
|------|------|-----------|
| 41 | Cloud Foundation | `infra/terraform/providers.tf`, `networking.tf`, `iam.tf` |
| 42 | Deploy Services | K8s deployment manifests, Docker images |
| 43 | Frontend + CDN + Environments | `frontend/cloud/`, CDN config, 3 environments |
| 44 | Storage + Logging + Backups | `infra/terraform/storage.tf`, `logging.tf`, `backup.tf` |

### TESTER AGENT (Day 6) — Week 44

**Pass Criteria:**
- Cloud infrastructure provisioned
- All services deployed
- 3 environments (dev, staging, prod)
- Backups configured
- **PHASE 9 COMPLETE**

---

# PHASE 10: BILLING SYSTEM (Weeks 45-46)

---

## WEEKS 45-46 — Billing System (Paddle)

| Week | Goal | Key Files |
|------|------|-----------|
| 45 | Paddle Integration Complete + Multi-Currency | `shared/integrations/paddle_client.py` (enhanced), multi-currency pricing |
| 46 | Tax + Dunning + PDF Invoices | `backend/services/tax_service.py`, `dunning_service.py`, invoice PDFs |

### TESTER AGENT (Day 6) — Week 46

**Pass Criteria:**
- Paddle billing: subscriptions work
- Multi-currency: INR, EUR, GBP supported
- Tax calculation: correct per jurisdiction
- Dunning: automated retry flows
- PDF invoices: generated correctly
- **PHASE 10 COMPLETE**

---

# PHASE 11: MOBILE APP (Weeks 47-49)

---

## WEEKS 47-49 — Mobile App (React Native + Expo)

| Week | Goal | Key Files |
|------|------|-----------|
| 47 | Mobile Foundation | `mobile/` setup, navigation |
| 48 | Mobile Core Screens | Dashboard, approvals, Jarvis |
| 49 | Remaining Screens + App Store | All screens, EAS build, submission |

### TESTER AGENT (Day 6) — Week 49

**Pass Criteria:**
- Mobile app builds successfully
- Core screens functional
- Push notifications work
- App Store submission ready
- **PHASE 11 COMPLETE**

---

# PHASE 12: ENTERPRISE SSO (Weeks 50-52)

---

## WEEKS 50-52 — Enterprise SSO

| Week | Goal | Key Files |
|------|------|-----------|
| 50 | SAML 2.0 Foundation | `backend/sso/saml_provider.py`, DB migration 012 |
| 51 | Okta + Azure AD + SCIM | Provider-specific implementations |
| 52 | MFA + SSO Audit | `backend/sso/mfa_enforcer.py`, audit logging |

### TESTER AGENT (Day 6) — Week 52

**Pass Criteria:**
- SAML 2.0: works with test IdP
- Okta: SSO flow works
- Azure AD: SSO flow works
- SCIM: user provisioning works
- MFA: enforced for enterprise
- **PHASE 12 COMPLETE**

---

# PHASE 13: HIGH AVAILABILITY (Weeks 53-55)

---

## WEEKS 53-55 — Multi-Region HA

| Week | Goal | Key Files |
|------|------|-----------|
| 53 | Multi-Region + Circuit Breakers | `infra/terraform/regions/`, `shared/utils/circuit_breaker.py` |
| 54 | Zero-Downtime Deploys + Network Policies | K8s PDBs, network policies, OpenTelemetry |
| 55 | Chaos Engineering + SLA Verification | Chaos experiments, 99.99% SLA verification |

### TESTER AGENT (Day 6) — Week 55

**Pass Criteria:**
- Multi-region: failover <10 seconds
- Zero-downtime deployment: verified
- Chaos engineering: all experiments pass
- SLA: 99.99% uptime verified
- **PHASE 13 COMPLETE**

---

# PHASE 14: SOC 2 COMPLIANCE (Weeks 56-60)

---

## WEEKS 56-60 — SOC 2 Type II

| Week | Goal | Key Files |
|------|------|-----------|
| 56 | Gap Assessment + All 6 Policies | `docs/compliance/policies/` |
| 57 | Vulnerability Scanning + TLS Hardening | Security scans, TLS config |
| 58 | Evidence Collection + Change Management | Automated evidence collection |
| 59 | Final Audit Preparation | Mock audit, documentation |
| 60 | SOC 2 Type II Complete + Production Ready | Final validation, all 60 weeks complete |

---

## WEEK 60 FINAL TESTER AGENT

**Command:**
```bash
pytest tests/ && snyk test && locust -u 100
```

**Pass Criteria:**
- Full test suite: 100% pass rate
- Zero critical CVEs
- OWASP: clean
- P95 <300ms at 100 concurrent users
- SOC 2 Type II: observation period complete, auditor engaged
- Agent Lightning: ≥94% accuracy
- **ALL 60 WEEKS COMPLETE — PRODUCTION READY**

---

# PAYMENT SYSTEM: PADDLE ONLY

```
+-----------------------------------------------------------------------+
| PAYMENT PROCESSOR: PADDLE (Merchant of Record)                        |
|                                                                       |
| ❌ NO Stripe - Paddle handles all payments                            |
|                                                                       |
| ✅ Paddle Features:                                                   |
|    - Subscription management                                          |
|    - Payment processing                                               |
|    - Tax compliance (global)                                          |
|    - Refunds (with approval gate)                                     |
|    - Chargebacks                                                      |
|                                                                       |
| ⚠️ CRITICAL: Paddle must NEVER be called without pending_approval    |
+-----------------------------------------------------------------------+
```

---

# VOICE/SMS: TWILIO (PLACEHOLDER)

```
+-----------------------------------------------------------------------+
| VOICE/SMS: TWILIO (Testing Placeholder)                               |
|                                                                       |
| Current: Twilio for testing                                           |
| Future: Swappable to another provider                                 |
|                                                                       |
| Architecture:                                                         |
| - `shared/integrations/twilio_client.py` - abstraction layer          |
| - Interface allows easy swap to:                                      |
|   - Vonage                                                            |
|   - MessageBird                                                       |
|   - AWS SNS/Pinpoint                                                  |
|   - Telnyx                                                            |
+-----------------------------------------------------------------------+
```

---

# FILE SUMMARY

| Phase | Weeks | Est. Files | Status |
|-------|-------|------------|--------|
| 1-2 | 1-2 | ~50 | ✅ COMPLETE |
| 3-4 | 3-4 | ~80 | ✅ COMPLETE |
| 5-8 | 5-8 | ~150 | ✅ COMPLETE |
| 9-14 | 9-14 | ~200 | 🔵 Week 9 done |
| 15-18 | 15-18 | ~150 | ⬜ Pending |
| 19-20 | 19-20 | ~50 | ⬜ Pending |
| 21-27 | 21-27 | ~150 | ⬜ Pending |
| 28-40 | 28-40 | ~300 | ⬜ Pending |
| 41-44 | 41-44 | ~80 | ⬜ Pending |
| 45-46 | 45-46 | ~40 | ⬜ Pending |
| 47-49 | 47-49 | ~100 | ⬜ Pending |
| 50-52 | 50-52 | ~60 | ⬜ Pending |
| 53-55 | 53-55 | ~50 | ⬜ Pending |
| 56-60 | 56-60 | ~80 | ⬜ Pending |
| **TOTAL** | **1-60** | **~1540 files** | **Week 9 done** |

---

# END OF ROADMAP
