# PARWA Architecture Document

> **Version:** 1.0  
> **Last Updated:** 2025-07-10  
> **Classification:** Internal — Engineering Team  
> **Status:** Reflects the actual built system (not aspirational)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Technology Stack](#2-technology-stack)
3. [Backend Architecture](#3-backend-architecture)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Infrastructure](#5-infrastructure)
6. [Multi-Tenant Architecture](#6-multi-tenant-architecture)
7. [Security Architecture](#7-security-architecture)

---

## 1. System Overview

### 1.1 What is PARWA?

PARWA is an AI-powered workforce for customer care, delivered as a SaaS platform. It automates customer support conversations across email, chat, SMS, and voice channels using 12 distinct AI techniques orchestrated through a multi-node LangGraph pipeline with real LLM calls.

### 1.2 Product Variants

| Variant | Monthly Price | Target | Key Differentiators |
|---------|--------------|--------|---------------------|
| **Mini PARWA** | $1,000/mo | Small businesses | 3-step pipeline, no escalation, simplified GSD |
| **PARWA** | $2,500/mo | Mid-market | 6-step pipeline, escalation, CLARA RAG, FAKE Voting |
| **PARWA High** | $4,000/mo | Enterprise | 9-step pipeline, human handoff loop, context compression, deduplication |

### 1.3 Architecture Principles

- **BC-001**: Every operation scoped by `company_id` (tenant isolation)
- **BC-008**: Never crash — graceful degradation on all failure paths
- **BC-012**: All timestamps UTC, no stack traces to users
- **BC-007**: All LLM calls route through SmartRouter (provider failover)

### 1.4 System Context Diagram

```
                    ┌──────────────────────────────────────────────────┐
                    │                 Users / Customers                │
                    └──────┬───────────────┬──────────┬───────────────┘
                           │               │          │
                    ┌──────▼──────┐  ┌──────▼──────┐  │
                    │  Web Chat   │  │   Email     │  │  SMS / Voice
                    │  (Widget)   │  │  (Brevo)    │  │  (Twilio)
                    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
                           │               │                │
                    ┌──────▼───────────────▼────────────────▼──────┐
                    │               Nginx (SSL Termination)          │
                    │     Rate Limiting │ WebSocket │ CSP Headers    │
                    └──────┬────────────────────────┬───────────────┘
                           │                        │
              ┌────────────▼──────────┐  ┌─────────▼──────────┐
              │   Next.js Frontend   │  │   FastAPI Backend   │
              │   (port 3000)        │  │   (port 8000)       │
              │   Tailwind + Radix   │  │   LangGraph + DSPy  │
              └──────────────────────┘  └─────┬──────┬────────┘
                                             │      │
                              ┌──────────────▼──┐  ┌▼──────────────┐
                              │   PostgreSQL 15 │  │   Redis 7     │
                              │   + pgvector    │  │ Cache + Queue │
                              └─────────────────┘  └──────┬────────┘
                                                         │
                                              ┌──────────▼──────────┐
                                              │   Celery Workers     │
                                              │   8 queues, beat     │
                                              └─────────────────────┘
```

---

## 2. Technology Stack

### 2.1 Core Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Frontend** | Next.js | 16 (App Router) | React framework with SSR/SSG |
| **Styling** | Tailwind CSS | 4 | Utility-first CSS |
| **UI Components** | Radix UI | latest | Accessible primitives |
| **State** | Zustand | latest | Client-side state management |
| **Animations** | Framer Motion | latest | Page transitions, micro-interactions |
| **Backend** | FastAPI | 0.100+ | Async Python web framework |
| **AI Orchestration** | LangGraph | latest | Multi-node pipeline graphs |
| **AI Optimization** | DSPy | latest | Programmatic LLM prompt optimization |
| **Task Queue** | Celery | 5.3+ | Distributed background jobs |
| **Database** | PostgreSQL | 15 + pgvector | Relational DB + vector search |
| **Cache/Broker** | Redis | 7-alpine | Caching, message broker, sessions |
| **Monitoring** | Prometheus | 2.x | Metrics collection |
| **Dashboards** | Grafana | 10.x | Visualization and alerting |
| **Alerting** | AlertManager | 0.27+ | Alert routing and grouping |
| **Error Tracking** | Sentry | latest | Exception tracking and tracing |
| **Payments** | Paddle | latest | Subscription billing |
| **Email** | Brevo (Sendinblue) | latest | Transactional email |
| **SMS/Voice** | Twilio | latest | SMS, voice, WhatsApp |
| **LLM** | OpenRouter | latest | Multi-provider LLM routing |

### 2.2 Backend Python Dependencies

Key packages used in production:
- `fastapi`, `uvicorn` — ASGI web framework
- `sqlalchemy`, `alembic` — ORM and migrations
- `celery`, `redis` — Task queue and cache
- `langgraph`, `langchain-core` — AI pipeline orchestration
- `dspy-ai` — Programmatic LLM optimization
- `pydantic`, `pydantic-settings` — Data validation and config
- `python-jose[cryptography]` — JWT RS256/HS256 support
- `httpx`, `aiohttp` — Async HTTP clients
- `structlog` — Structured logging
- `pgvector` — Vector similarity search
- `prometheus-fastapi-instrumentator` — Metrics middleware
- `sentry-sdk[fastapi]` — Error tracking integration
- `python-socketio[asyncio]` — WebSocket real-time events

---

## 3. Backend Architecture

### 3.1 Application Entry Point

The backend is a FastAPI application defined in `backend/app/main.py`. Key responsibilities:

- **Lifespan management**: Alembic migrations, Redis pool, Socket.io mount, Jarvis knowledge pre-loading, LangGraph graph compilation
- **Middleware stack** (ordered outermost to innermost):
  1. `ErrorHandlerMiddleware` — Correlation ID + structured JSON errors
  2. `RequestLoggerMiddleware` — Audit trail for every request
  3. `TenantMiddleware` — BC-001 multi-tenant isolation (company_id extraction)
  4. `RateLimitMiddleware` — Per-IP rate limiting
  5. `APIKeyAuthMiddleware` — BC-011 API key authentication
  6. `SecurityHeadersMiddleware` — HSTS, CSP, X-Frame-Options
  7. `IPAllowlistMiddleware` — BC-012 IP restrictions (disabled by default)
  8. `AIEntitlementMiddleware` — Feature gating for `/api/ai/` paths
  9. `CORSMiddleware` — Cross-origin access (explicit origins only)

- **27 registered routers** covering: auth, MFA, API keys, clients, admin, webhooks, health, user details, public, pricing, AI engine, AI agent, Jarvis, Jarvis CC, onboarding, integrations, knowledge base, verification, analytics, email channel, OOO detection, bounce/complaint, chat widget, SMS channel, workflow, tickets, technique config

### 3.2 Custom GSD State Engine

The GSD (Guided Support Dialogue) engine in `backend/app/core/gsd_engine.py` manages multi-step conversation states.

**8 States:**

| State | Description |
|-------|-------------|
| `NEW` | Fresh ticket/conversation |
| `GREETING` | Initial AI greeting |
| `DIAGNOSIS` | Intent classification and information gathering |
| `RESOLUTION` | Generating and delivering the response |
| `FOLLOW_UP` | Post-resolution check for satisfaction |
| `ESCALATE` | Triggered escalation (auto or manual) |
| `HUMAN_HANDOFF` | Transferred to human agent |
| `CLOSED` | Conversation resolved |

**Variant-specific transitions:**
- **Mini PARWA**: Linear flow only (NEW → GREETING → DIAGNOSIS → RESOLUTION → CLOSED)
- **PARWA**: Full flow with escalation (adds ESCALATE → HUMAN_HANDOFF → DIAGNOSIS loop)
- **PARWA High**: Full flow + DIAGNOSIS loop after HUMAN_HANDOFF + FOLLOW_UP → DIAGNOSIS

**Auto-escalation triggers:**
- Frustration score exceeds threshold (default: 80/100)
- VIP customer tier detected
- Legal/sensitive intent detected
- Diagnosis loop count exceeds max (default: 3)
- Escalation cooldown: 5 minutes between escalations

### 3.3 LangGraph Pipeline (19 Nodes)

The AI response generation pipeline is built as a LangGraph StateGraph with 19 processing nodes:

| Node | File | Function |
|------|------|----------|
| `01_pii_redaction` | `01_pii_redaction.py` | Strips PII from user input before processing |
| `02_empathy_engine` | `02_empathy_engine.py` | Generates empathetic acknowledgment |
| `03_router_agent` | `03_router_agent.py` | Classifies intent and routes to domain agent |
| `04_base_domain_agent` | `04_base_domain_agent.py` | General knowledge response generation |
| `05_faq_agent` | `05_faq_agent.py` | FAQ-based response from knowledge base |
| `06_refund_agent` | `06_refund_agent.py` | Refund and billing inquiry handling |
| `07_technical_agent` | `07_technical_agent.py` | Technical support and troubleshooting |
| `08_billing_agent` | `08_billing_agent.py` | Invoice, subscription, payment queries |
| `09_complaint_agent` | `09_complaint_agent.py` | Complaint de-escalation and resolution |
| `10_escalation_agent` | `10_escalation_agent.py` | Human escalation management |
| `11_maker_validator` | `11_maker_validator.py` | MAKER Framework: K-solution generation + scoring |
| `12_control_system` | `12_control_system.py` | DSPy optimization and prompt tuning |
| `13_dspy_optimizer` | `13_dspy_optimizer.py` | DSPy metric evaluation and compilation |
| `14_guardrails` | `14_guardrails.py` | 5-check safety system (PII, Hallucination, Loophole, Prompt Injection, Brand Voice) |
| `15_channel_delivery` | `15_channel_delivery.py` | Formats response for delivery channel |
| `16_state_update` | `16_state_update.py` | Updates GSD state and ticket metadata |
| `17_email_agent` | `17_email_agent.py` | Email-specific response formatting |
| `18_sms_agent` | `18_sms_agent.py` | SMS-specific response (160 char limit) |
| `19_voice_agent` | `19_voice_agent.py` | Voice/Twilio response formatting |

**Pipeline topology by variant:**
- **Mini PARWA** (LangGraph Workflow): `classify → generate → format` (3 steps)
- **PARWA**: `classify → extract_signals → technique_select → generate → quality_gate → format` (6 steps)
- **PARWA High**: `classify → extract_signals → technique_select → context_compress → generate → quality_gate → context_health → dedup → format` (9 steps)

The 19-node LangGraph graph and the variant-specific workflow are complementary systems — the graph provides the domain-specific AI processing while the workflow manages the pipeline lifecycle and step orchestration.

### 3.4 MAKER Framework

Located in `backend/app/core/langgraph/nodes/11_maker_validator.py`:

- **M**aximal **A**gentic **K**-solution **E**ngine with **R**ed-flagging
- Generates K candidate solutions (variant-dependent: 3/5/7)
- Each solution scored across multiple dimensions
- Best solution selected by weighted scoring

### 3.5 FAKE Voting Sub-System

Located in `backend/app/core/fake_voting.py`:

- **F**ake **V**oting **A**ggregation with **K**onsensus **E**valuation
- Multi-evaluator consensus scoring with 5 evaluators:
  1. **Fluency** — Language quality assessment
  2. **Relevance** — Query-response alignment
  3. **Accuracy** — Factual correctness
  4. **Safety** — Harmlessness check
  5. **Empathy** — Emotional appropriateness
- Variant-specific configuration:

| Variant | Candidates | Evaluators | Consensus Threshold |
|---------|-----------|------------|---------------------|
| mini_parwa | 3 | 3 | 0.50 |
| parwa | 5 | 4 | 0.60 |
| parwa_high | 7 | 5 | 0.75 |

- **RedFlagEngine**: 5-category pre-evaluation (hallucination risk, PII leakage, off-topic, policy violation, confidence mismatch)
- All LLM calls via SmartRouter (BC-007)
- Heuristic fallbacks when LLM unavailable (BC-008)

### 3.6 CLARA RAG (Advanced Retrieval)

Located in `backend/app/core/rag/`:

- **HyDE Generator** (`hyde.py`): Hypothetical Document Embedding — generates a hypothetical answer to the user query, embeds it, and uses it as a search query for better semantic retrieval
- **Multi-Query Retriever** (`multi_query.py`): Generates alternative phrasings of the user query, retrieves documents for each, merges and deduplicates results, ranks by aggregate score
- **LLM Reranker** (`llm_reranker.py`): Batch-scoring reranker (5 chunks/call) that re-ranks retrieved documents using LLM evaluation with BM25 fallback
- All operations cached in Redis with 120s TTL
- All LLM calls via SmartRouter (BC-007)

### 3.7 Agent Lightning (Self-Learning)

Located in `backend/app/tasks/training_tasks.py` and related:

- Weekly self-learning system that collects agent mistakes from `AgentMistake` records
- `prepare_dataset_task`: Queries mistakes, formats training samples, creates `TrainingDataset`
- `check_mistake_threshold_task`: Counts mistakes by severity/type, auto-triggers dataset preparation
- `schedule_training_task`: Validates dataset, creates baseline checkpoint, estimates GPU duration
- `evaluate_training_task`: Computes A/B metrics, creates `AgentPerformance` record
- `cleanup_old_datasets_task`: Deletes stale datasets/checkpoints older than 90 days
- Fine-tunes LLaMA-3-8B via Unsloth + Google Colab (external)

### 3.8 Loophole Solutions Engine

Located in `backend/app/core/loophole_registry.py` and `loophole_engine.py`:

**25 loophole categories** with 130+ regex detection patterns:

| ID | Category | Severity | Group |
|----|----------|----------|-------|
| LH-001 | Hallucination | Critical | Accuracy |
| LH-002 | PII Leakage | Critical | Security |
| LH-003 | Unauthorized Access | Critical | Security |
| LH-004 | Emotional Manipulation | High | Ethics |
| LH-005 | Biased Responses | High | Compliance |
| LH-006 | Off-Topic Divergence | Medium | Reliability |
| LH-007 | Escalation Failure | High | Reliability |
| LH-008 | Brand Voice Violation | Medium | Brand |
| LH-009 | Regulatory Non-Compliance | Critical | Compliance |
| LH-010 | Circular Reasoning | Medium | Reliability |
| LH-011 | Overconfident Claims | Medium | Accuracy |
| LH-012 | Fabricated URLs/Links | High | Accuracy |
| LH-013 | Policy Fabrication | High | Accuracy |
| LH-014 | False Feature Claims | High | Brand |
| LH-015 | Prompt Injection Success | Critical | Security |
| LH-016 | Price/Plan Confusion | High | Accuracy |
| LH-017 | Freebie Exploitation | High | Ethics |
| LH-018 | Agent Impersonation | Medium | Ethics |
| LH-019 | Incomplete Resolution | Medium | Reliability |
| LH-020 | Contradictory Responses | Medium | Reliability |
| LH-021 | Sensitive Data in Logs | Critical | Security |
| LH-022 | Timeout Exploitation | Low | Reliability |
| LH-023 | Knowledge Boundary Violation | Medium | Reliability |
| LH-024 | Temporal Confusion | Medium | Accuracy |
| LH-025 | Numerical Precision Fraud | Medium | Accuracy |

**LoopholeDetectionEngine** features:
- 7 specialized detection methods (hallucination, PII, injection, price confusion, off-topic, brand violation, generalized)
- Confidence scoring with severity weight + match length + position factors
- Decision rules: critical/high @ 0.7+ confidence → block, medium @ 0.5+ → review

### 3.9 5-Check Guardrails System

Located in `backend/app/core/langgraph/nodes/14_guardrails.py`:

| Check | Order | Description |
|-------|-------|-------------|
| 1. PII Scrubbing | First | Detects and redacts personal information |
| 2. Hallucination Detection | Second | Checks for fabricated claims, overconfident statements |
| 3. Loophole Detection | Third | 25-category loophole scan (LH-001 through LH-025) |
| 4. Prompt Injection | Fourth | Detects successful injection/jailbreak attempts |
| 5. Brand Voice | Fifth | Validates tone consistency with brand guidelines |

### 3.10 Additional AI Components

- **Confidence Scoring Engine** (`confidence_scoring_engine.py`): Variant-specific thresholds (mini_parwa: 95, parwa: 85, parwa_high: 75)
- **Hallucination Detector** (`hallucination_detector.py`): Detects fabricated claims and overconfident language
- **Self-Healing Engine** (`self_healing_engine.py`): Records query results, detects patterns, applies 5+ healing rules
- **Circuit Breaker Manager** (`circuit_breaker_manager.py`): 9 pre-registered dependencies with Prometheus metrics
- **Smart Router** (`smart_router.py`): Multi-provider LLM routing with health tracking, rate limiting, and failover
- **Redis Health Tracker** (`redis_health_tracker.py`): Redis-backed provider health shared across Celery workers
- **Classification Engine** (`classification_engine.py`): Intent classification with AI + keyword fallback
- **Technique Router** (`technique_router.py`): Maps query signals to AI technique selection
- **Sentiment Engine** (`sentiment_engine.py`): Customer sentiment analysis
- **Blocked Response Manager** (`blocked_response_manager.py`): Manages canned responses for blocked content

### 3.11 AI Techniques (12 Techniques)

Located in `backend/app/core/techniques/`:

| Technique | File | Description |
|-----------|------|-------------|
| Chain of Thought | `chain_of_thought.py` | Step-by-step reasoning |
| Tree of Thoughts | `tree_of_thoughts.py` | Branching exploration of reasoning paths |
| React | `react.py` | Reasoning + Acting loop |
| React Tools | `react_tools.py` | React with tool use |
| Self-Consistency | `self_consistency.py` | Majority vote across multiple reasoning paths |
| Reverse Thinking | `reverse_thinking.py` | Solution-first backward reasoning |
| Least to Most | `least_to_most.py` | Decompose complex queries into simpler sub-problems |
| Step Back | `step_back.py` | Abstract reasoning before detailed analysis |
| Universe of Thoughts | `universe_of_thoughts.py` | Multi-perspective exploration |
| CRP | `crp.py` | Contextual Reasoning Protocol |
| Reflexion | `reflexion.py` | Self-reflection and iterative improvement |
| GST | `gst.py` | Goal-State Trees |

All techniques use real LLM calls via `SmartRouter` (NOT regex or template-based).

### 3.12 Celery Task Architecture

Located in `backend/app/tasks/celery_app.py`:

**8 specialized queues:**

| Queue | Purpose | Routing Pattern |
|-------|---------|-----------------|
| `default` | General tasks | `app.tasks.*` (fallback) |
| `ai_heavy` | Heavy AI (embeddings, batch) | `app.tasks.ai.heavy.*` |
| `ai_light` | Light AI (single classification) | `app.tasks.ai.light.*` |
| `email` | Email sending via Brevo | `app.tasks.email.*` |
| `webhook` | Webhook processing | `app.tasks.webhook.*` |
| `analytics` | Analytics aggregation | `app.tasks.analytics.*` |
| `training` | Model training/fine-tuning | `app.tasks.training.*` |
| `dead_letter` | Failed task DLQ | Manually routed |

**Task configuration:**
- Soft time limit: 5 minutes (300s)
- Hard time limit: 5.5 minutes (330s)
- Prefetch multiplier: 1 (one task at a time per worker)
- ACK late: true (acknowledge after completion)
- Reject on worker lost: true
- Max tasks per child: 1000 (auto-restart to prevent leaks)
- Max memory per child: 200MB
- Max payload: 1MB (M-32 enforcement)

**Beat scheduler** runs 20+ periodic tasks including:
- Session cleanup (daily)
- DLQ purge (hourly)
- Webhook health check (5 min)
- Audit trail cleanup (daily 03:00 UTC)
- Metric aggregation (5 min)
- Training mistake check (hourly)
- OOO profile cleanup (hourly)
- Soft bounce retry (2 hours)
- Redis key audit (hourly), TTL fix (daily), orphan cleanup (weekly)
- Jarvis awareness tick (30 seconds), prune (6 hours)
- AI workload rebalance (60s), budget reset (midnight)
- Approval timeout check (15 min), reminder (30 min)

---

## 4. Frontend Architecture

### 4.1 Framework & Routing

- **Next.js 16** with App Router (`src/app/`)
- All pages use server components by default, client components where needed (`"use client"`)
- Route groups: `(auth)` for login/signup/reset, `(dashboard)` for authenticated pages

### 4.2 Dashboard Pages

Located in `src/app/dashboard/`:

| Page | Path | Description |
|------|------|-------------|
| **Dashboard Home** | `/dashboard` | Overview metrics, quick actions |
| **Tickets** | `/dashboard/tickets` | Ticket list, filters, bulk actions, detection |
| **Agents** | `/dashboard/agents` | AI agent management, performance |
| **Variants** | `/dashboard/variants` | PARWA variant configuration |
| **Channels** | `/dashboard/channels` | Email, SMS, chat channel management |
| **Knowledge** | `/dashboard/knowledge` | Knowledge base document management |
| **Monitoring** | `/dashboard/monitoring` | System health, AI pipeline metrics |
| **Billing** | `/dashboard/billing` | Subscription management, invoices |
| **Settings** | `/dashboard/settings` | Company settings, API keys, team |
| **Jarvis CC** | `/dashboard/jarvis` | Jarvis Customer Care chat interface |

### 4.3 Public Pages

| Page | Path | Description |
|------|------|-------------|
| **Landing** | `/` | Marketing homepage |
| **Pricing** | `/pricing` | Pricing tiers comparison |
| **ROI Calculator** | `/roi-calculator` | Return on investment calculator |
| **Jarvis Chat** | `/jarvis` | Public Jarvis onboarding chat |
| **Models** | `/models` | AI model information |
| **Book Demo** | `/book-demo` | Demo scheduling |
| **Onboarding** | `/onboarding` | New customer onboarding wizard |

### 4.4 Auth Pages

| Page | Path | Description |
|------|------|-------------|
| Login | `/(auth)/login` | Email/password + Google OAuth |
| Signup | `/(auth)/signup` | New account registration |
| Forgot Password | `/(auth)/forgot-password` | Password reset request |
| Reset Password | `/(auth)/reset-password` | Set new password |
| Profile | `/profile` | User profile management |

### 4.5 Key Frontend Libraries

| Library | Purpose |
|---------|---------|
| `zustand` | Client-side state management |
| `framer-motion` | Animations and page transitions |
| `jose` | JWT RS256/HS256 verification in browser |
| `react-icons` | Icon library |
| `uuid` | Unique ID generation |
| `next-themes` | Dark/light theme switching |
| `sonner` | Toast notifications |
| `cmdk` | Command palette |

### 4.6 Jarvis CC Chat Interface

The Jarvis Customer Care chat (`/dashboard/jarvis`) is the primary AI interaction interface:
- Real-time WebSocket via Socket.io (`/ws` path)
- Awareness Feed: proactive notifications surfaced during chat
- Command Palette: quick actions accessible via keyboard shortcut
- ROI-aware responses: considers customer's subscription tier
- Pages-visited context: tracks user navigation for contextual responses

### 4.7 Frontend API Routes

Located in `src/app/api/`:
- `auth/*` — Login, register, Google OAuth, password reset, email verification
- `chat/route.ts` — AI chat endpoint
- `onboarding/route.ts` — Onboarding wizard data
- `analytics/route.ts` — Analytics data fetching
- `channel-status/route.ts` — Channel connectivity status
- `send-email/route.ts` — Email sending (with `sanitizeEmailContent()`)
- `send-sms/route.ts` — SMS sending
- `ticket-solve/route.ts` — Ticket resolution
- `integrations/route.ts` — Third-party integration management
- `book-demo/route.ts` — Demo booking form
- `kb/documents/[id]/route.ts` — Knowledge base document CRUD

---

## 5. Infrastructure

### 5.1 Docker Compose Production Services

The production deployment uses Docker Compose with 14+ services:

| Service | Image | Purpose | Health Check |
|---------|-------|---------|--------------|
| `db` | `postgres:15-alpine` | PostgreSQL + pgvector | `pg_isready` (10s/5s/5 retries) |
| `redis` | `redis:7-alpine` | Cache + message broker | `redis-cli ping` (10s/5s/5 retries) |
| `backend` | Custom (`infra/docker/backend.Dockerfile`) | FastAPI API server | `curl -f http://localhost:8000/health` (30s/10s/3) |
| `worker` | Custom (`infra/docker/worker.Dockerfile`) | Celery worker | Process-level monitoring |
| `frontend` | Custom (`infra/docker/frontend.prod.Dockerfile`) | Next.js production build | Nginx health |
| `nginx` | Custom (`infra/docker/nginx.Dockerfile`) | Reverse proxy + SSL | `nginx -t` + health endpoint |
| `mcp` | Custom (`infra/docker/mcp.Dockerfile`) | MCP server for integrations | HTTP health |
| `prometheus` | `prom/prometheus` | Metrics collection | `/api/v1/health` |
| `grafana` | `grafana/grafana` | Dashboards | `/api/health` |
| `alertmanager` | `prom/alertmanager` | Alert routing | `/api/v2/status` |
| `redis-exporter` | `oliver006/redis_exporter` | Redis metrics | `/metrics` |
| `postgres-exporter` `prometheuscommunity/postgres-exporter` | PostgreSQL metrics | `/metrics` |
| `node-exporter` | `prom/node-exporter` | Host system metrics | `/metrics` |

### 5.2 Network Isolation

Three Docker networks provide service isolation:

| Network | Services | Purpose |
|---------|----------|---------|
| `backend_network` | backend, worker, db, redis | Internal backend communication |
| `frontend_network` | frontend, nginx, backend | Frontend ↔ backend proxy |
| `monitoring_network` | prometheus, grafana, alertmanager, exporters | Monitoring stack isolation |

### 5.3 Nginx Configuration

Located in `nginx/nginx.conf`:

**Rate Limiting Zones:**
- `api_limit`: 10 requests/second (burst: 20)
- `login_limit`: 5 requests/minute (burst: 3)
- `general_limit`: 30 requests/second (burst: 50)

**SSL/TLS:**
- TLS 1.2 + TLS 1.3 only
- Mozilla Modern cipher suite
- OCSP Stapling enabled
- HSTS: 2 years with preload
- Session cache: 10m shared, 1 day timeout

**Security Headers:**
- `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- Content-Security-Policy with explicit `script-src`, `connect-src`, Paddle CDN allowances

**Blocking:**
- All dotfiles (`.env`, `.git`, etc.)
- Sensitive file extensions (`.env`, `.git`, `.sql`, `.log`, `.sh`, `.config`, `.bak`)

### 5.4 Container Security

- **Non-root containers**: All containers run as non-root user
- **Resource limits**: Memory and CPU limits on all services
- **Read-only root filesystem**: Where applicable
- **Health checks**: All services have health checks
- **Restart policies**: `unless-stopped` for all services
- **No host port binding**: Internal services (db, redis) bind to `127.0.0.1` only

### 5.5 Kubernetes Manifests (Optional)

Located in `infra/k8s/` (33 files):

- Namespace, ConfigMap, Secrets
- Ingress, NetworkPolicy, PodDisruptionBudget
- Deployments with HPA:
  - Backend: 2-10 replicas @ 70% CPU
  - Worker: 2-8 replicas @ 60% CPU
- StatefulSets for PostgreSQL and Redis with PVC
- Prometheus, Grafana, AlertManager deployments

---

## 6. Multi-Tenant Architecture

### 6.1 Tenant Context

Every request is scoped to a `company_id`:

1. **API Key auth path**: `APIKeyAuthMiddleware` extracts `company_id` from API key → sets `request.state.company_id`
2. **JWT auth path**: `TenantMiddleware` extracts `company_id` from JWT claims → sets `request.state.company_id`
3. **Fallback**: If neither auth method provides `company_id`, the request proceeds without tenant context (for public routes)

### 6.2 Row-Level Security (RLS)

Enabled via Alembic migration 022 (`022_enable_rls.py`):

- RLS enabled on 122 tables
- 488 row-level security policies
- `app.current_tenant_id()` PostgreSQL function provides tenant context
- Every query automatically filtered by `company_id`
- Enforced at the database level (not just application level)

### 6.3 API Key Authentication

- Each company can generate API keys via `/api/api-keys`
- API keys stored hashed (SHA-256) in `api_keys` table
- `APIKeyAuthMiddleware` validates key on every request
- API key audit trail in `api_key_audit` table

### 6.4 Rate Limiting Per Tenant

Three layers of rate limiting:
1. **Nginx**: Per-IP (10 r/s for API, 5 r/m for login, 30 r/s general)
2. **FastAPI middleware**: `RateLimitMiddleware` with configurable per-tenant limits
3. **Celery**: Task-level rate limiting via `usage_burst_protection` and `token_budget_service`

---

## 7. Security Architecture

### 7.1 JWT Authentication (RS256/HS256 Dual)

Located in `backend/app/core/auth.py`:

**Token creation:**
- Default: HS256 with `JWT_SECRET_KEY`
- Optional: RS256 with RSA private key (file path or base64 env var)
- Includes `kid` (Key ID) header for key rotation
- Access token: 15 minutes TTL
- Refresh token: 7 days TTL

**Token verification** (two-strategy):
1. If RS256 configured → try RS256 verification first
2. Fall back to HS256 verification (migration period)
3. Key rotation support via `JWT_PREVIOUS_KEYS`

**Key rotation procedure:**
```python
from app.core.auth import rotate_jwt_key
rotate_jwt_key()  # Adds current key to previous keys, generates new key
```

### 7.2 Cookie Security

- `httpOnly: true` — Prevents JavaScript access
- `secure: true` — Only sent over HTTPS
- `SameSite: Lax` — CSRF protection with navigation support
- Max 5 concurrent sessions per user (`MAX_SESSIONS_PER_USER`)
- JWT blacklisting via Redis with configurable TTL

### 7.3 RBAC (Role-Based Access Control)

| Role | Permissions |
|------|------------|
| **Super Admin** | Full system access, all companies |
| **Admin** | Full access within company, billing, team management |
| **Agent** | Ticket management, customer interactions |
| **Viewer** | Read-only dashboard access |

### 7.4 PII Protection

- **PII redaction** in AI pipeline (Node 01)
- **PII scan service** (`pii_scan_service.py`) for data at rest
- **Sentry PII scrubbing**: `sentry.py` strips sensitive fields before sending events
- **Encryption at rest**: `DATA_ENCRYPTION_KEY` (Fernet) for sensitive fields
- **Email sanitization**: `sanitizeEmailContent()` strips scripts, event handlers, dangerous tags

### 7.5 Webhook Security

- **HMAC verification** for all webhook providers (Paddle, Brevo, Twilio, Shopify)
- **Replay protection**: Timestamp validation (reject events older than 5 minutes)
- **IP allowlist** for Brevo inbound webhooks (`BREVO_INBOUND_IPS`)
- **DLQ** for permanently failed webhook processing tasks

### 7.6 CORS Configuration

- Explicit origin list only (never wildcard `["*"]` with credentials)
- Configured via `CORS_ORIGINS` env var (comma-separated)
- Falls back to `FRONTEND_URL` (defaults to `http://localhost:3000`)
- `allow_credentials: true` for cookie-based auth

### 7.7 CSP (Content Security Policy)

```
default-src 'self';
script-src 'self' https://cdn.paddle.com;
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
font-src 'self' https://fonts.gstatic.com;
img-src 'self' data: https:;
connect-src 'self' https://parwa.ai wss://parwa.ai;
frame-src 'self' https://cdn.paddle.com;
object-src 'none';
base-uri 'self';
form-action 'self' https://parwa.ai;
```

### 7.8 Database Migration Chain

23 Alembic migrations (001 through 023):

```
001_initial_schema           → Core tables (users, companies, tickets)
002_ticketing_tables        → Ticket messages, assignments, tags
003_ai_pipeline_tables      → AI pipeline execution, model registry
004_integration_tables      → Third-party integrations
005_audit_billing_tables    → Audit logs, billing, invoices
006_analytics_onboarding    → Analytics events, onboarding progress
007_remaining_gap_tables    → Remaining schema gaps
008_technique_tables        → AI technique configs, metrics
009_billing_extended        → Extended billing, proration
010_onboarding_extended     → Extended onboarding steps
011_phase3_variant_engine   → Variant capabilities, instances
012_jarvis_system           → Jarvis agents, awareness, commands
015_business_email_otp      → Business email OTP verification
016_email_channel           → Email channel management
017_outbound_email          → Outbound email templates
018_email_delivery_events   → Email delivery tracking
019_ooo_bounce              → OOO detection, bounce/complaint
020_jarvis_cc               → Jarvis CC tables
021_fix_session_ticket_fk   → Fix 14 orphan FK constraints
022_enable_rls              → Enable RLS on 122 tables + 488 policies
023_paddle_reconciliation   → Webhook events, reconciliation reports
```

---

## Appendix A: Key Files Reference

| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/main.py` | 545 | FastAPI application entry point |
| `backend/app/config.py` | 294 | Configuration (pydantic-settings) |
| `backend/app/core/auth.py` | 503 | JWT RS256/HS256 + key rotation |
| `backend/app/core/health.py` | 767 | Health check orchestrator (9 subsystems) |
| `backend/app/core/gsd_engine.py` | 1,100+ | GSD State Engine (8 states, 3 variants) |
| `backend/app/core/smart_router.py` | 1,902 | Multi-provider LLM routing |
| `backend/app/core/langgraph_workflow.py` | 1,000+ | LangGraph pipeline engine |
| `backend/app/core/fake_voting.py` | 458 | FAKE Voting sub-system |
| `backend/app/core/loophole_registry.py` | 756 | 25 loophole categories |
| `backend/app/core/loophole_engine.py` | 758 | Loophole detection engine |
| `backend/app/core/circuit_breaker_manager.py` | ~400 | Circuit breaker patterns |
| `backend/app/core/self_healing_engine.py` | ~350 | Self-healing rules engine |
| `backend/app/core/confidence_scoring_engine.py` | ~300 | Variant-specific confidence |
| `backend/app/core/hallucination_detector.py` | ~250 | Hallucination detection |
| `backend/app/tasks/celery_app.py` | 320 | Celery configuration + beat schedule |
| `docker-compose.yml` | 172 | Development Docker Compose |
| `nginx/nginx.conf` | 259 | Production nginx configuration |
| `monitoring/prometheus.yml` | 71 | Prometheus scrape targets |
| `monitoring/alertmanager/alertmanager.yml` | 139 | AlertManager routing |
| `monitoring/alerting/rules.yml` | 160 | Prometheus alert rules |
