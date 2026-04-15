# PROJECT_STATE.md — Live Project State Memory

> **Technical Assistant v9 Requirement** — Current state of the project for agent continuity.

## Project Overview

- **Name:** PARWA AI Workforce
- **Stack:** FastAPI + Next.js 15 + PostgreSQL + Redis + Celery + Socket.io + Paddle + Brevo + Twilio
- **Phase:** Phase 4 — Dashboard + Analytics (Week 15 CURRENT)
- **Current Status:** Phase 3 AI Engine COMPLETE (Weeks 8-12) → Week 13 Channels COMPLETE → Week 14 Jarvis Command Center COMPLETE → Moving to Week 15 (Dashboard + Analytics)
- **Total Tests:** ~6,519+ test functions across tests/ and backend/app/tests/

## Progress

| Week | Phase | Tests | Status |
|------|-------|-------|--------|
| Week 1 | Foundation (Days 1-7) | 1-700 | ✅ Complete |
| Week 2 | Auth System (Days 8-14) | 700-1370 | ✅ Complete |
| Week 3 | Infrastructure (Days 15-23) | 1370-2100 | ✅ Complete |
| Week 4 | Ticket System (Days 24-35) | 2100-3896 | ✅ Complete |
| Week 5 | Billing System | 3896+ | ✅ Complete |
| Week 6 | Onboarding | +new | ✅ Complete |
| Week 7 | Approval System | +new | ✅ Complete |
| Week 8 | AI Engine Core (Phase 3) | +523 | ✅ Complete |
| Week 9 | AI Core (Classification + RAG) | +new | ✅ Complete |
| Week 10 | AI Core (GSD + Workflow) | +new | ✅ Complete |
| Week 10.5 | 14 AI Techniques | +new | ✅ Complete |
| Week 11-12 | AI Advanced + Hardening | +new | ✅ Complete |
| **Week 13** | **Communication Channels** | — | ✅ Complete |
| **Week 14** | **Jarvis Command Center** | +93 | ✅ Complete |
| **Week 15** | **Dashboard + Analytics** | — | **🔵 CURRENT** |

## Key Architecture Decisions

1. **Tenant Isolation:** company_id flows from JWT → middleware → DB queries → Celery tasks → Redis keys
2. **Task Pattern:** All Celery tasks use `ParwaBaseTask` + `@with_company_id` + exponential backoff
3. **Webhook Flow:** HMAC verify → store event → dispatch to Celery → provider handler via registry
4. **Event System:** Socket.io with typed events, emit helpers, tenant rooms, reconnection buffer
5. **Health Checks:** Dependency-aware with Prometheus metrics, Grafana dashboards, alerting rules
6. **Smart Router:** 3-tier LLM routing (Light/Medium/Heavy) with variant gating per tenant plan
7. **AI Pipeline:** Signal Extraction → Classification → RAG → Technique Selection → Response Generation → CLARA Quality Gate
8. **GSD Engine:** 6-state machine (NEW → GREETING → DIAGNOSIS → RESOLUTION → FOLLOW-UP → CLOSED)
9. **LangGraph Workflow:** Graph-based orchestration with per-variant pipeline graphs
10. **14 AI Techniques:** Tier 1 (CLARA, CRP, GSD), Tier 2 (CoT, ReAct, ThoT, Reverse, Step-Back), Tier 3 (GST, UoT, ToT, Self-Consistency, Reflexion, Least-to-Most)

## File Structure (Key Dirs)

```
backend/app/
├── api/               # FastAPI routes (30+ route files)
├── core/              # AI engines, socketio, health, metrics, events
│   ├── techniques/    # 14 AI reasoning techniques
│   └── react_tools/   # ReAct tool integrations (order, billing, crm, ticket)
├── middleware/         # Auth, tenant, CORS, AI entitlement
├── models/            # SQLAlchemy models
├── schemas/           # Pydantic schemas
├── security/          # HMAC, JWT, encryption
├── services/          # Business logic (40+ service files)
├── shared/            # Shared modules (knowledge_base/)
├── tasks/             # Celery tasks (7 queues)
├── templates/emails/  # Jinja2 email templates (22)
├── tests/             # Inline tests (3,154+ test functions)
├── webhooks/          # Provider webhook handlers (brevo, twilio, paddle, shopify)
└── main.py            # FastAPI app
```

## Phase 3 Key Files (Weeks 8-12)

### Core AI Engines
- `core/smart_router.py` — 3-tier LLM routing
- `core/model_failover.py` — Provider failover chains
- `core/pii_redaction_engine.py` — 15 PII types
- `core/guardrails_engine.py` — 8-layer safety
- `core/prompt_injection_defense.py` — 25+ rules
- `core/hallucination_detector.py` — 12 patterns
- `core/confidence_scoring_engine.py` — 7 weighted signals
- `core/blocked_response_manager.py` — Review queue
- `core/signal_extraction.py` — 10 signals
- `core/classification_engine.py` — 6 intent types
- `core/sentiment_engine.py` — Frustration scoring
- `core/rag_retrieval.py` — pgvector search
- `core/rag_reranking.py` — Cross-encoder reranking
- `core/response_generator.py` — Auto-response
- `core/clara_quality_gate.py` — 5-stage quality gate
- `core/gsd_engine.py` — GSD state machine
- `core/langgraph_workflow.py` — Graph orchestration
- `core/technique_router.py` — Technique selection (545 lines)
- `core/ai_pipeline.py` — Main pipeline orchestrator
- `core/draft_composer.py` — Co-pilot mode
- `core/edge_case_handlers.py` — 20 edge-case handlers

### 14 AI Techniques
- `core/techniques/crp.py` — Concise Response Protocol (T1)
- `core/techniques/chain_of_thought.py` — CoT (T2)
- `core/techniques/react.py` — ReAct (T2)
- `core/techniques/thread_of_thought.py` — ThoT (T2)
- `core/techniques/reverse_thinking.py` — Reverse Thinking (T2)
- `core/techniques/step_back.py` — Step-Back Prompting (T2)
- `core/techniques/gst.py` — Guided Sequential Thinking (T3)
- `core/techniques/universe_of_thoughts.py` — UoT (T3)
- `core/techniques/tree_of_thoughts.py` — ToT (T3)
- `core/techniques/self_consistency.py` — Self-Consistency (T3)
- `core/techniques/reflexion.py` — Reflexion (T3)
- `core/techniques/least_to_most.py` — Least-to-Most (T3)

## Testing

- **Framework:** pytest
- **Locations:** `tests/unit/`, `backend/app/tests/`
- **Pattern:** `tests/conftest.py` sets ENVIRONMENT=test before imports
- **Celery:** Tests use EAGER mode via `setup_day22_tests()`
- **Total:** ~6,519+ test functions across 285 test files

## Build Codes (Active)

- BC-001: Multi-tenant isolation
- BC-002: Financial actions
- BC-003: Webhook processing (idempotent, <3s, async)
- BC-004: Celery task pattern
- BC-005: Socket.io event system
- BC-006: Email communication (Brevo)
- BC-007: AI model interaction (Smart Router)
- BC-008: State management (GSD Engine)
- BC-009: Approval workflow
- BC-010: Data lifecycle & compliance (GDPR)
- BC-011: Authentication & security
- BC-012: Error handling & resilience
- BC-013: AI technique routing (3-tier)
- BC-014: Task decomposition (build process)

## Next Steps (Week 13 — Phase 4)

- Week 13: Communication Channels (F-120 to F-130) — Email, Chat, SMS, Voice, Social Media
- Week 14-15: Jarvis Command Center (F-087 to F-096)
- Week 16: Dashboard + Analytics (F-036 to F-045)
- Week 17: Integrations + Settings
- Week 18-21: Phase 5 — Public Facing + Training + Polish
