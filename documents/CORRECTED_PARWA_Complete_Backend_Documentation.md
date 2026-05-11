# PARWA COMPLETE BACKEND DOCUMENTATION

## Version 3.0 - Full Stack Alignment Edition
### Existing Code Analysis | Gap Analysis | Complete API Reference | Database Schema

---

> **CORRECTION NOTICE**: This document has been corrected per the loopwholws.md locked decisions (D1-D48). The following changes were applied:
> - **D1**: Stripe removed — Paddle is the sole payment provider
> - **D2/D3**: Supabase Realtime removed — Socket.io is the real-time layer
> - **D3**: Database changed from Supabase to PostgreSQL on GCP VM (self-hosted)
> - **D4**: BullMQ replaced with Celery + Redis for all job queues
> - **D9**: Added Brevo Inbound Parse webhook for email receiving
> - **D10**: Added daily overage charging model ($0.10/ticket)
> - **D11**: Microsoft OAuth removed — Google OAuth + email/password only
> - **D13**: Cancellation & Refund Policy - Netflix style (no refunds, cancel anytime, access until month end, no free trials, payment fails = stop immediately)
> - **D19**: Added notification preferences table and APIs
> - **D22**: Added OutgoingWebhookService and outgoing_webhooks table
> - **D23**: Added CircuitBreakerService
> - **D29**: Added missing database tables (customers, sessions, interactions, etc.)
> - **D33**: Added cancellation_requests table
> - **D38**: Added newsletter subscribers
> - **D41**: Added CustomerResolutionService
> - **D45/D26**: Added training_runs table
> - **D47**: Added account data export APIs

---

# OUR AGREEMENTS (From Chat Discussion)

| Topic | Decision |
|-------|----------|
| **Payment** | Paddle (NOT Stripe) |
| **LLM Providers** | OpenRouter, Google AI, Cerebras, Groq - ALL configurable |
| **Admin Flexibility** | Admin can add/remove/modify ANY provider through UI |
| **Client Integrations** | Clients can connect ANY API - not just pre-built connectors |
| **Integration Methods** | Pre-built, Custom REST API, Webhooks, MCP, GraphQL, Database |
| **Hosting** | GCP Cloud (12GB RAM, 100GB storage) |
| **Database** | PostgreSQL on GCP VM (self-hosted) — single database |
| **Training** | LOCAL (user's own hardware, NOT cloud) |
| **Real-time** | Socket.io on same GCP instance |
| **Queues** | Celery + Redis |
| **Caching** | Redis |
| **PARWA Internal** | Twilio (SMS/Voice), Brevo (Email) |

---

# SECTION 1: EXISTING BACKEND ANALYSIS (From GitHub)

## 1.1 Current Architecture

```
parwa/
├── backend/
│   ├── api/                    # API Routes (FastAPI)
│   │   ├── auth.py             ✅ Implemented
│   │   ├── dashboard.py        ✅ Implemented
│   │   ├── jarvis.py           ✅ Implemented (Partial)
│   │   ├── integrations.py     ✅ Implemented
│   │   ├── analytics.py        ✅ Implemented
│   │   ├── billing.py          ✅ Implemented
│   │   ├── compliance.py       ✅ Implemented
│   │   ├── support.py          ✅ Implemented
│   │   ├── communication.py    ✅ Implemented
│   │   ├── automation.py       ✅ Implemented
│   │   ├── client_success.py   ✅ Implemented
│   │   ├── licenses.py         ✅ Implemented
│   │   ├── incoming_calls.py   ✅ Implemented
│   │   ├── webhooks/           ✅ Implemented (Shopify, Paddle, Twilio)
│   │   └── routes/             ✅ Implemented (burst, cold_start, undo)
│   ├── services/               # Business Logic
│   │   ├── approval_service.py     ✅ Implemented
│   │   ├── analytics_service.py    ✅ Implemented
│   │   ├── billing_service.py      ✅ Implemented
│   │   ├── compliance_service.py   ✅ Implemented
│   │   ├── notification_service.py ✅ Implemented
│   │   ├── user_service.py         ✅ Implemented
│   │   ├── voice_handler.py        ✅ Implemented
│   │   ├── burst_mode/             ✅ Implemented
│   │   ├── cold_start/             ✅ Implemented
│   │   ├── undo_manager/           ✅ Implemented
│   │   └── client_success/         ✅ Implemented (Full Suite)
│   ├── models/                 # Database Models
│   │   ├── user.py             ✅ Implemented
│   │   ├── company.py          ✅ Implemented
│   │   ├── subscription.py     ✅ Implemented
│   │   ├── support_ticket.py   ✅ Implemented
│   │   ├── audit_trail.py      ✅ Implemented
│   │   ├── usage_log.py        ✅ Implemented
│   │   ├── license.py          ✅ Implemented
│   │   └── compliance_request.py ✅ Implemented
│   ├── schemas/                # Pydantic Schemas
│   ├── core/                   # Core Config
│   │   ├── auth.py             ✅ Implemented
│   │   ├── config.py           ✅ Implemented
│   │   ├── jarvis_commands.py  ✅ Implemented
│   │   └── industry_configs/   ✅ Implemented (E-commerce, SaaS, Healthcare, Logistics)
│   ├── security/               # Security Modules
│   │   ├── session_manager.py      ✅ Implemented
│   │   ├── rate_limiter_advanced.py ✅ Implemented
│   │   └── api_key_manager.py      ✅ Implemented
│   ├── middleware/             # Middleware
│   │   ├── rate_limit_middleware.py  ✅ Implemented
│   │   ├── cache_middleware.py       ✅ Implemented
│   │   └── compression_middleware.py ✅ Implemented
│   ├── nlp/                    # NLP Processing
│   │   ├── intent_classifier.py ✅ Implemented
│   │   └── command_parser.py    ✅ Implemented
│   ├── quality_coach/          # Quality Coach (PARWA High)
│   │   ├── analyzer.py         ✅ Implemented
│   │   ├── reporter.py         ✅ Implemented
│   │   └── notifier.py         ✅ Implemented
│   ├── compliance/             # Compliance
│   │   ├── residency/          ✅ Implemented (GDPR, Region routing)
│   │   └── replication/        ✅ Implemented
│   └── app/                    # App Entry
│       ├── main.py             ✅ Implemented
│       ├── database.py         ✅ Implemented
│       └── middleware.py       ✅ Implemented
├── enterprise/                 # Enterprise Modules
│   ├── webhooks/               ✅ Implemented (Full Suite)
│   ├── api_gateway/            ✅ Implemented
│   ├── audit/                  ✅ Implemented
│   ├── multi_tenancy/          ✅ Implemented
│   ├── analytics/              ✅ Implemented
│   ├── sso/                    ✅ Implemented (SAML, LDAP, OAuth)
│   ├── scaling/                ✅ Implemented
│   ├── global_infra/           ✅ Implemented
│   ├── onboarding/             ✅ Implemented
│   ├── notifications/          ✅ Implemented
│   ├── security_hardening/     ✅ Implemented
│   ├── monitoring/             ✅ Implemented
│   ├── billing/                ✅ Implemented
│   ├── ai_optimization/        ✅ Implemented
│   ├── automation/             ✅ Implemented
│   ├── security/               ✅ Implemented
│   ├── integrations/           ✅ Implemented (Salesforce, SAP, Snowflake, BigQuery)
│   ├── data_pipeline/          ✅ Implemented
│   ├── support/                ✅ Implemented
│   └── ops/                    ✅ Implemented
├── agent_lightning/            # AI Training System
│   ├── training/               ✅ Implemented (Full Suite)
│   ├── deployment/             ✅ Implemented (with Auto-Rollback)
│   ├── monitoring/             ✅ Implemented (A/B Testing)
│   ├── validation/             ✅ Implemented
│   ├── optimization/           ✅ Implemented
│   ├── benchmark/              ✅ Implemented
│   ├── v2/                     ✅ Implemented (Enhanced Training)
│   └── data/                   ✅ Implemented
└── monitoring/                 # Monitoring Stack
    ├── prometheus.yml          ✅ Implemented
    ├── grafana_dashboards/     ✅ Implemented
    └── alerts/                 ✅ Implemented
```

## 1.2 Implementation Status Summary

| Category | Status | Completion |
|----------|--------|------------|
| Authentication APIs | ✅ Implemented | 95% |
| Dashboard APIs | ✅ Implemented | 90% |
| Jarvis APIs | ⚠️ Partial | 60% |
| Integration APIs | ⚠️ Partial | 70% |
| Analytics APIs | ✅ Implemented | 85% |
| Billing APIs | ⚠️ Partial | 65% |
| Compliance APIs | ✅ Implemented | 90% |
| Support APIs | ✅ Implemented | 85% |
| Enterprise Modules | ✅ Implemented | 95% |
| Agent Lightning | ✅ Implemented | 95% |
| Client Success | ✅ Implemented | 90% |
| Security Modules | ✅ Implemented | 90% |
| **OVERALL** | **⚠️ Partial** | **~80%** |

---

# SECTION 2: GAP ANALYSIS

## 2.1 Missing API Endpoints (Frontend Requires)

### A. Authentication APIs - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/auth/google` | GET | ❌ Missing | High |
| `/api/auth/mfa/setup` | POST | ❌ Missing | Medium |
| `/api/auth/mfa/verify` | POST | ❌ Missing | Medium |
| `/api/auth/mfa/backup-codes` | GET | ❌ Missing | Medium |
| `/api/auth/check-email` | POST | ❌ Missing | Low |

> **Note (D11):** Microsoft OAuth has been removed. Authentication is email/password + Google OAuth only.

### B. Client APIs - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/client/avatar` | POST | ❌ Missing | Low |
| `/api/client/password` | PUT | ❌ Missing | High |
| `/api/client/mfa` | POST | ❌ Missing | Medium |
| `/api/client/sessions` | GET | ❌ Missing | Medium |
| `/api/client/sessions/:id` | DELETE | ❌ Missing | Medium |
| `/api/client/api-keys` | GET/POST/DELETE | ❌ Missing | High |
| `/api/client/team/invite` | POST | ❌ Missing | High |
| `/api/client/team/:id` | PUT/DELETE | ❌ Missing | Medium |
| `/api/client/policies` | GET/PUT | ❌ Missing | High |
| `/api/client/notifications` | GET/PUT | ❌ Missing | Medium |
| `/api/client/notification-preferences` | GET/PUT | ❌ Missing | Medium |

### C. Dashboard APIs - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/dashboard/first-victory` | GET | ❌ Missing | High |
| `/api/dashboard/forecast` | GET | ❌ Missing | Medium |

### D. Approval APIs - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/approvals` | GET | ⚠️ Partial | High |
| `/api/approvals/batches` | GET | ❌ Missing | High |
| `/api/approvals/:id/approve` | POST | ⚠️ Partial | High |
| `/api/approvals/:id/reject` | POST | ⚠️ Partial | High |
| `/api/approvals/batch/:id/approve` | POST | ❌ Missing | High |
| `/api/approvals/auto-rule` | POST | ❌ Missing | Medium |

### E. Jarvis APIs - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/jarvis/pause` | POST | ❌ Missing | Critical |
| `/api/jarvis/undo` | POST | ❌ Missing | Critical |
| `/api/jarvis/errors` | GET | ❌ Missing | High |

### F. Agent APIs - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/agents` | GET | ❌ Missing | High |
| `/api/agents` | POST | ❌ Missing | High |
| `/api/agents/:id` | GET | ❌ Missing | Medium |
| `/api/agents/:id/performance` | GET | ❌ Missing | Medium |

### G. Knowledge APIs - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/knowledge` | GET | ❌ Missing | High |
| `/api/knowledge/upload` | POST | ❌ Missing | High |
| `/api/knowledge/:id` | GET | ❌ Missing | Medium |
| `/api/knowledge/:id` | DELETE | ❌ Missing | Medium |
| `/api/knowledge/:id/reprocess` | POST | ❌ Missing | Low |

### H. Demo APIs - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/demo/chat` | POST | ❌ Missing | High |
| `/api/demo/limits` | GET | ❌ Missing | High |
| `/api/demo/voice/init` | POST | ❌ Missing | Medium |
| `/api/demo/voice/status` | GET | ❌ Missing | Medium |

### I. Checkout/Payment APIs - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/checkout/session` | POST | ❌ Missing | Critical |
| `/api/webhooks/paddle` | POST | ❌ Missing | Critical |
| `/api/checkout/verify` | GET | ❌ Missing | High |
| `/api/pricing/calculate` | POST | ❌ Missing | High |
| `/api/pricing/compare` | GET | ❌ Missing | Medium |

### J. Onboarding APIs - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/onboarding/start` | POST | ❌ Missing | High |
| `/api/onboarding/consent` | POST | ❌ Missing | High |
| `/api/onboarding/activate` | POST | ❌ Missing | High |

### K. Emergency APIs - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/emergency/pause` | POST | ❌ Missing | Critical |
| `/api/emergency/channel` | POST | ❌ Missing | Critical |
| `/api/emergency/override` | POST | ❌ Missing | Critical |
| `/api/undo/email` | POST | ❌ Missing | High |
| `/api/undo/action` | POST | ❌ Missing | High |
| `/api/security/shield` | GET | ❌ Missing | Medium |

### L. Admin APIs - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/admin/clients` | GET | ❌ Missing | High |
| `/api/admin/clients/:id` | GET/PUT | ❌ Missing | High |
| `/api/admin/clients/:id/subscription` | PUT | ❌ Missing | High |
| `/api/admin/services` | GET/POST | ❌ Missing | High |
| `/api/admin/services/:id` | PUT/DELETE | ❌ Missing | Medium |
| `/api/admin/health` | GET | ❌ Missing | High |
| `/api/admin/monitoring/status` | GET | ❌ Missing | High |
| `/api/admin/monitoring/performance` | GET | ❌ Missing | Medium |
| `/api/admin/monitoring/costs` | GET | ❌ Missing | Medium |
| `/api/admin/incidents` | GET | ❌ Missing | Medium |
| `/api/admin/api-providers` | GET/POST/PUT/DELETE | ❌ Missing | Critical |

### M. Account Export APIs (D47) - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/account/export` | POST | ❌ Missing | Medium |
| `/api/account/export/status` | GET | ❌ Missing | Medium |

### N. Newsletter APIs (D38) - Missing Endpoints

| Endpoint | Method | Status | Priority |
|----------|--------|--------|----------|
| `/api/newsletter/subscribe` | POST | ❌ Missing | Low |

---

## 2.2 Missing Database Tables

### Existing Tables (From Models)

| Table | Status |
|-------|--------|
| users | ✅ Implemented |
| companies | ✅ Implemented |
| subscriptions | ✅ Implemented |
| support_tickets | ✅ Implemented |
| audit_trails | ✅ Implemented |
| usage_logs | ✅ Implemented |
| licenses | ✅ Implemented |
| compliance_requests | ✅ Implemented |
| sla_breaches | ✅ Implemented |
| client_health | ✅ Implemented |
| communications | ✅ Implemented |
| training_data | ✅ Implemented |
| churn | ✅ Implemented |

### Missing Tables (Frontend Requires)

| Table | Purpose | Priority |
|-------|---------|----------|
| `knowledge_documents` | Store uploaded knowledge base docs | High |
| `document_chunks` | Vector embeddings for RAG | High |
| `approval_queues` | Pending approval items | High |
| `approval_batches` | Batched approvals | High |
| `auto_handle_rules` | Auto-approval rules | Medium |
| `agents` | AI agent configurations | High |
| `agent_performance` | Agent metrics history | High |
| `emergency_states` | Emergency pause states | Critical |
| `undo_snapshots` | Undo action snapshots | High |
| `demo_sessions` | Guest demo sessions | Medium |
| `first_victories` | First victory tracking | Medium |
| `mfa_settings` | MFA configurations | Medium |
| `backup_codes` | MFA backup codes | Medium |
| `user_sessions` | Active user sessions | High |
| `api_keys` | Client API keys | High |
| `team_members` | Team member invitations | High |
| `notifications` | User notifications | Medium |
| `webhook_events` | Webhook event log | High |
| `integrations` | Client integrations config | High |
| `integration_health` | Integration status tracking | Medium |
| `onboarding_sessions` | Onboarding progress | High |
| `api_providers` | Admin-configurable API providers | Critical |
| `service_configs` | Dynamic service configurations | High |
| `growth_nudges` | Growth nudge tracking | Low |
| `feature_discovery` | Feature discovery state | Low |
| `contextual_help` | Help content storage | Low |
| `cancellation_flows` | Cancellation tracking | Low |

### Missing Tables (From loopwholws.md Decisions — D29, D10, D19, D22, D33, D38, D45/D26, D8/D35)

| Table | Purpose | Decision |
|-------|---------|----------|
| `customers` | End-customers (people reaching out for support) | D29 |
| `sessions` | Conversation sessions (threaded conversations) | D29 |
| `interactions` | Individual messages/interactions within sessions | D29 |
| `overage_charges` | Daily overage charges ($0.10/ticket beyond plan limit) | D10 |
| `user_notification_preferences` | Per-user notification channel preferences | D19 |
| `outgoing_webhooks` | Configured outgoing webhook destinations | D22 |
| `cancellation_requests` | Formal cancellation requests and reason tracking | D33 |
| `newsletter_subscribers` | Newsletter subscription list | D38 |
| `training_runs` | Training run history and status tracking | D45/D26 |

---

## 2.3 Missing Services

| Service | Purpose | Priority |
|---------|---------|----------|
| `PaddleService` | Paddle payment integration | Critical |
| `DemoService` | Guest demo management | High |
| `KnowledgeService` | Document upload & RAG | High |
| `AgentService` | AI agent management | High |
| `EmergencyService` | Emergency controls | Critical |
| `FirstVictoryService` | First victory tracking | Medium |
| `GrowthNudgeService` | Growth nudge detection | Low |
| `MFAService` | MFA management | Medium |
| `TeamService` | Team management | High |
| `APIKeyService` | API key management | High |
| `OnboardingService` | Onboarding wizard | High |
| `APIProviderService` | Admin API configuration | Critical |
| `CalculatorService` | ROI/Pricing calculator | High |
| `ContextService` | GSD State management | Critical |
| `SmartRouterService` | LLM routing | Critical |
| `OutgoingWebhookService` | Outgoing webhook delivery and retry | High (D22) |
| `CircuitBreakerService` | Circuit breaker for external integrations | High (D23) |
| `CustomerResolutionService` | Customer identity resolution across channels | High (D41) |

---

## 2.4 Missing Socket.io Events (Real-time)

| Event | Direction | Purpose |
|-------|-----------|---------|
| `activity:new` | Server → Client | New activity item |
| `approval:new` | Server → Client | New approval request |
| `approval:batch:new` | Server → Client | New batch created |
| `jarvis:response` | Server → Client | Jarvis response |
| `gsd:step` | Server → Client | GSD state update |
| `context:warning` | Server → Client | Context limit warning |
| `emergency:triggered` | Server → Client | Emergency state change |
| `agent:status` | Server → Client | Agent status change |
| `metrics:update` | Server → Client | Real-time metrics |
| `ticket:created` | Server → Client | New ticket |
| `ticket:resolved` | Server → Client | Ticket resolved |

---

# SECTION 3: COMPLETE API REFERENCE (Required)

## 3.1 Authentication APIs

```
POST   /api/auth/register          - Create new user
POST   /api/auth/login             - Authenticate user
POST   /api/auth/logout            - End session
POST   /api/auth/forgot-password   - Send reset email
POST   /api/auth/reset-password    - Reset with token
POST   /api/auth/verify-email      - Verify email
POST   /api/auth/resend-verification - Resend verification
GET    /api/auth/me                - Get current user
POST   /api/auth/mfa/setup         - Setup MFA
POST   /api/auth/mfa/verify        - Verify MFA code
GET    /api/auth/mfa/backup-codes  - Generate backup codes
GET    /api/auth/google            - Google OAuth
POST   /api/auth/check-email       - Check if email exists
```

> **Note (D11):** Microsoft OAuth removed. Google OAuth + email/password only.

## 3.2 Client APIs

```
GET    /api/client/profile         - Get profile
PUT    /api/client/profile         - Update profile
POST   /api/client/avatar          - Upload avatar
PUT    /api/client/password        - Change password
POST   /api/client/mfa             - Toggle MFA
GET    /api/client/sessions        - List sessions
DELETE /api/client/sessions/:id    - Revoke session
GET    /api/client/api-keys        - List API keys
POST   /api/client/api-keys        - Create API key
DELETE /api/client/api-keys/:id    - Delete API key
GET    /api/client/subscription    - Get subscription
PUT    /api/client/subscription    - Update subscription
GET    /api/client/invoices        - List invoices
GET    /api/client/team            - List team
POST   /api/client/team/invite     - Invite member
PUT    /api/client/team/:id        - Update member
DELETE /api/client/team/:id        - Remove member
GET    /api/client/policies        - Get policies
PUT    /api/client/policies        - Update policies
GET    /api/client/compliance      - Get compliance
PUT    /api/client/compliance      - Update compliance
GET    /api/client/notifications   - Get notifications
PUT    /api/client/notifications   - Update notifications
GET    /api/client/notification-preferences - Get notification prefs (D19)
PUT    /api/client/notification-preferences - Update notification prefs (D19)
```

## 3.3 Dashboard APIs

```
GET    /api/dashboard/overview     - Dashboard summary
GET    /api/dashboard/activity     - Activity feed
GET    /api/dashboard/metrics      - Key metrics
GET    /api/dashboard/first-victory - First victory status
GET    /api/dashboard/forecast     - Volume forecast
```

## 3.4 Ticket APIs

```
GET    /api/tickets                - List tickets (with filters)
GET    /api/tickets/:id            - Get ticket details
PUT    /api/tickets/:id            - Update ticket
POST   /api/tickets/bulk           - Bulk ticket actions
```

## 3.5 Approval APIs

```
GET    /api/approvals              - List pending approvals
GET    /api/approvals/batches      - Get batched approvals
POST   /api/approvals/:id/approve  - Approve single item
POST   /api/approvals/:id/reject   - Reject single item
POST   /api/approvals/batch/:id/approve - Approve entire batch
POST   /api/approvals/auto-rule    - Create auto-handle rule
```

## 3.6 Jarvis APIs

```
POST   /api/jarvis/command         - Execute command
GET    /api/jarvis/status          - System status
POST   /api/jarvis/pause           - Pause AI
POST   /api/jarvis/undo            - Undo action
GET    /api/jarvis/errors          - Recent errors
```

## 3.7 Agent APIs

```
GET    /api/agents                 - List agents
POST   /api/agents                 - Add agent
GET    /api/agents/:id             - Get agent
GET    /api/agents/:id/performance - Performance metrics
PUT    /api/agents/:id/status      - Update agent status
DELETE /api/agents/:id             - Remove agent
```

## 3.8 Analytics APIs

```
GET    /api/analytics/overview     - Overview
GET    /api/analytics/trends       - Trend data
GET    /api/analytics/roi          - ROI data
GET    /api/analytics/performance  - Performance
GET    /api/analytics/drift        - Drift report
GET    /api/analytics/export       - Export data
```

## 3.9 Knowledge APIs

```
GET    /api/knowledge              - List documents
POST   /api/knowledge/upload       - Upload document
GET    /api/knowledge/:id          - Get document
DELETE /api/knowledge/:id          - Delete document
POST   /api/knowledge/:id/reprocess - Reprocess
```

## 3.10 Audit Log APIs

```
GET    /api/audit-log              - List entries
GET    /api/audit-log/:id          - Get detail
GET    /api/audit-log/export       - Export
```

## 3.11 Integration APIs

```
GET    /api/integrations           - List all
POST   /api/integrations           - Create
PUT    /api/integrations/:id       - Update
DELETE /api/integrations/:id       - Delete
POST   /api/integrations/:id/test  - Test connection
GET    /api/integrations/:id/health - Health status
POST   /api/integrations/:provider/connect - OAuth connect
GET    /api/integrations/:provider/callback - OAuth callback
POST   /api/integrations/custom    - Create custom integration
POST   /api/integrations/mcp       - Create MCP integration
POST   /api/integrations/database  - Create DB connection
```

## 3.12 Webhook APIs

```
POST   /api/webhooks/shopify       - Shopify webhook
POST   /api/webhooks/paddle        - Paddle webhook
POST   /api/webhooks/twilio        - Twilio webhook (SMS/Voice)
POST   /api/webhooks/email         - Brevo Inbound Parse webhook (D9)
POST   /api/webhooks/custom/:id    - Custom webhook
```

> **Note (D1):** Stripe webhook removed. Paddle is the sole payment provider.

## 3.13 Admin APIs

```
GET    /api/admin/clients          - List clients
GET    /api/admin/clients/:id      - Get client
PUT    /api/admin/clients/:id      - Update client
PUT    /api/admin/clients/:id/subscription - Change subscription
GET    /api/admin/services         - List services
POST   /api/admin/services         - Add service
PUT    /api/admin/services/:id     - Update service
DELETE /api/admin/services/:id     - Delete service
GET    /api/admin/health           - System health
GET    /api/admin/monitoring/status - Service status
GET    /api/admin/monitoring/performance - Performance
GET    /api/admin/monitoring/costs - Cost tracking
GET    /api/admin/incidents        - List incidents
GET    /api/admin/api-providers    - List API providers
POST   /api/admin/api-providers    - Add API provider
PUT    /api/admin/api-providers/:id - Update provider
DELETE /api/admin/api-providers/:id - Delete provider
```

## 3.14 Demo APIs

```
POST   /api/demo/chat              - Demo chat
GET    /api/demo/limits            - Check guest limits
POST   /api/demo/voice/init        - Init voice demo
GET    /api/demo/voice/status      - Call status
```

## 3.15 Checkout/Pricing APIs

```
POST   /api/checkout/session       - Create checkout session (Paddle)
GET    /api/checkout/verify        - Verify payment status
POST   /api/pricing/calculate      - Calculate recommended tier
GET    /api/pricing/compare        - Get feature comparison
```

## 3.16 Onboarding APIs

```
POST   /api/onboarding/start       - Initialize onboarding
POST   /api/onboarding/consent     - Save legal consents
POST   /api/onboarding/activate    - Activate AI system
GET    /api/onboarding/status      - Get onboarding status
```

## 3.17 Emergency APIs

```
POST   /api/emergency/pause        - Pause all
POST   /api/emergency/channel      - Pause channel
POST   /api/emergency/override     - Emergency override
POST   /api/undo/email             - Recall email
POST   /api/undo/action            - Void action
GET    /api/security/shield        - Shield status
PUT    /api/security/whitelist     - Update whitelist
```

## 3.18 Account Export APIs (D47)

```
POST   /api/account/export         - Request data export
GET    /api/account/export/status  - Check export job status
```

## 3.19 Newsletter APIs (D38)

```
POST   /api/newsletter/subscribe   - Subscribe to newsletter
```

---

# SECTION 4: COMPLETE DATABASE SCHEMA

## 4.1 Core Tables

### users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT TRUE,
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### companies
```sql
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(50) NOT NULL,
    subscription_tier VARCHAR(50) NOT NULL,
    subscription_status VARCHAR(50) DEFAULT 'active',
    mode VARCHAR(50) DEFAULT 'shadow',
    paddle_customer_id VARCHAR(255),
    paddle_subscription_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### subscriptions
```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    tier VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### knowledge_documents
```sql
CREATE TABLE knowledge_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),
    file_size INTEGER,
    category VARCHAR(100),
    status VARCHAR(50) DEFAULT 'processing',
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### document_chunks
```sql
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    chunk_index INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### approval_queues
```sql
CREATE TABLE approval_queues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    ticket_id UUID REFERENCES support_tickets(id),
    type VARCHAR(100) NOT NULL,
    confidence_score DECIMAL(5,2),
    risk_level VARCHAR(50),
    amount DECIMAL(10,2),
    reasoning TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    batch_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    resolved_by UUID REFERENCES users(id)
);
```

### agents
```sql
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    name VARCHAR(255) NOT NULL,
    variant VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    capacity_used INTEGER DEFAULT 0,
    capacity_max INTEGER DEFAULT 100,
    accuracy_rate DECIMAL(5,2) DEFAULT 0,
    tickets_resolved INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### emergency_states
```sql
CREATE TABLE emergency_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    is_paused BOOLEAN DEFAULT FALSE,
    paused_channels TEXT[],
    paused_by UUID REFERENCES users(id),
    paused_at TIMESTAMP,
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### integrations
```sql
CREATE TABLE integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    type VARCHAR(100) NOT NULL,
    name VARCHAR(255),
    status VARCHAR(50) DEFAULT 'disconnected',
    credentials_encrypted TEXT,
    settings JSONB,
    last_sync TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### api_providers (Admin Configurable)
```sql
CREATE TABLE api_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    type VARCHAR(50) NOT NULL, -- 'llm', 'payment', 'email', 'sms', 'voice'
    description TEXT,
    required_fields JSONB,
    optional_fields JSONB,
    default_endpoint VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### service_configs (Dynamic Configurations)
```sql
CREATE TABLE service_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES api_providers(id),
    company_id UUID REFERENCES companies(id), -- NULL for global configs
    display_name VARCHAR(255),
    api_key_encrypted TEXT,
    api_secret_encrypted TEXT,
    endpoint VARCHAR(255),
    settings JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 4.2 Additional Tables (From loopwholws.md Decisions)

### customers (D29)
```sql
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    external_id VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    name VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### sessions (D29)
```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    channel VARCHAR(50) NOT NULL, -- 'email', 'chat', 'sms', 'voice'
    status VARCHAR(50) DEFAULT 'open',
    agent_id UUID REFERENCES agents(id),
    assigned_to UUID REFERENCES users(id),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    closed_at TIMESTAMP
);
```

### interactions (D29)
```sql
CREATE TABLE interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL, -- 'customer', 'agent', 'system'
    content TEXT NOT NULL,
    channel VARCHAR(50) NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);
```

### overage_charges (D10)
```sql
CREATE TABLE overage_charges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    tickets_over_limit INTEGER NOT NULL DEFAULT 0,
    charge_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    paddle_charge_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'charged', 'failed'
    created_at TIMESTAMP DEFAULT NOW()
);
```

### user_notification_preferences (D19)
```sql
CREATE TABLE user_notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel VARCHAR(50) NOT NULL, -- 'email', 'sms', 'in_app', 'push'
    event_type VARCHAR(100) NOT NULL, -- 'ticket_assigned', 'approval_pending', etc.
    enabled BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, channel, event_type)
);
```

### outgoing_webhooks (D22)
```sql
CREATE TABLE outgoing_webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    url VARCHAR(500) NOT NULL,
    secret VARCHAR(255),
    events TEXT[] NOT NULL, -- which events trigger this webhook
    is_active BOOLEAN DEFAULT TRUE,
    last_delivery_at TIMESTAMP,
    last_status VARCHAR(50),
    failure_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### cancellation_requests (D33)
```sql
CREATE TABLE cancellation_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    reason TEXT NOT NULL,
    feedback TEXT,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'contacted', 'retained', 'processed'
    contacted_at TIMESTAMP,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### newsletter_subscribers (D38)
```sql
CREATE TABLE newsletter_subscribers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    source VARCHAR(100), -- 'landing_page', 'footer', 'signup_form'
    is_active BOOLEAN DEFAULT TRUE,
    subscribed_at TIMESTAMP DEFAULT NOW(),
    unsubscribed_at TIMESTAMP
);
```

### training_runs (D45/D26)
```sql
CREATE TABLE training_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id),
    trigger VARCHAR(50) NOT NULL, -- 'auto_mistake_threshold', 'time_fallback', 'manual'
    mistake_count_at_trigger INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'rolled_back'
    dataset_size INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    metrics JSONB,
    previous_model_id VARCHAR(255),
    new_model_id VARCHAR(255),
    rolled_back BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### demo_sessions (D8/D35)
```sql
CREATE TABLE demo_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_email VARCHAR(255),
    guest_name VARCHAR(255),
    guest_phone VARCHAR(50),
    session_token VARCHAR(255) UNIQUE NOT NULL,
    messages_count INTEGER DEFAULT 0,
    max_messages INTEGER DEFAULT 10,
    is_voice BOOLEAN DEFAULT FALSE,
    voice_payment_id VARCHAR(255),
    voice_call_sid VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'expired', 'converted'
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

# SECTION 5: CELERY TASK DEFINITIONS

> **Note (D4):** BullMQ has been replaced with Celery + Redis. All queue processing uses Celery workers.

## 5.1 Task Definitions

| Task Name | Purpose | Concurrency |
|-----------|---------|-------------|
| `tickets.process` | Ticket processing | 3 |
| `approvals.workflow` | Approval workflows | 2 |
| `notifications.send` | Email/SMS sending | 2 |
| `training.run` | Agent Lightning training | 1 |
| `sync.integration` | Integration sync | 2 |
| `analytics.aggregate` | Analytics aggregation | 1 |
| `webhooks.deliver` | Outgoing webhook delivery | 3 |
| `voice.process` | Voice call processing | 2 |
| `overage.charge` | Daily overage billing (D10) | 1 |
| `training.check_threshold` | Check 50-mistake threshold (D7) | 1 |

## 5.2 Task Types

### tickets tasks
- `tickets.process` - Process incoming ticket (classify → route → respond)
- `tickets.classify` - Classify ticket type/intent
- `tickets.respond` - Generate AI response
- `tickets.escalate` - Escalate to human agent
- `tickets.resolve` - Mark resolved and update metrics

### approvals tasks
- `approvals.create` - New approval request created
- `approvals.batch` - Create approval batch
- `approvals.remind` - Send reminder (2h, 4h, 8h, 24h ladder — D40)
- `approvals.timeout` - Handle approval timeout (auto-reject at 72h — D40)

### training tasks
- `training.export_mistakes` - Export mistake log (triggers at 50 mistakes — D7)
- `training.prepare_dataset` - Build training dataset
- `training.run` - Execute training job (LOCAL on user's hardware)
- `training.validate` - Validate model performance
- `training.deploy` - Deploy new model with auto-rollback
- `training.check_fallback` - Time-based fallback: every 2 weeks regardless of count (D7)

### overage tasks (D10)
- `overage.daily_charge` - Calculate and charge daily overage at $0.10/ticket

### notification tasks
- `notifications.send_email` - Send email via Brevo
- `notifications.send_sms` - Send SMS via Twilio
- `notifications.send_in_app` - Create in-app notification

---

# SECTION 6: SOCKET.IO EVENTS

## 6.1 Server → Client Events

```javascript
// Activity updates
socket.emit('activity:new', { activityItem });

// Approval notifications
socket.emit('approval:new', { approval });
socket.emit('approval:batch:new', { batch });

// Jarvis responses
socket.emit('jarvis:response', { response });
socket.emit('gsd:step', { step, status });

// Context warnings
socket.emit('context:warning', { percentage, message });

// Emergency alerts
socket.emit('emergency:triggered', { state, reason });

// Agent status
socket.emit('agent:status', { agentId, status });

// Real-time metrics
socket.emit('metrics:update', { metrics });

// Ticket events
socket.emit('ticket:created', { ticket });
socket.emit('ticket:resolved', { ticketId });
```

## 6.2 Client → Server Events

```javascript
// Jarvis commands
socket.emit('jarvis:command', { command });

// Emergency controls
socket.emit('emergency:pause', { channels });
socket.emit('emergency:resume', {});

// Subscription management
socket.emit('subscribe:company', { companyId });
socket.emit('unsubscribe:company', { companyId });
```

---

# SECTION 7: API KEYS CONFIGURATION

## 7.1 LLM Providers (Admin Configurable)

| Provider | Environment Variable | Purpose |
|----------|---------------------|---------|
| OpenRouter | `OPENROUTER_API_KEY` | Multi-model access |
| Google AI | `GOOGLE_AI_API_KEY` | Gemini models |
| Cerebras | `CEREBRAS_API_KEY` | Fast inference |
| Groq | `GROQ_API_KEY` | Fast inference |
| LiteLLM | `LITELLM_API_KEY` | Unified proxy |

## 7.2 Payment Provider

| Provider | Environment Variable | Purpose |
|----------|---------------------|---------|
| Paddle | `PADDLE_CLIENT_TOKEN` | Checkout |
| Paddle | `PADDLE_API_KEY` | Management |
| Paddle | `PADDLE_WEBHOOK_SECRET` | Verification |

## 7.3 Communication Providers

| Provider | Environment Variable | Purpose |
|----------|---------------------|---------|
| Twilio | `TWILIO_ACCOUNT_SID` | SMS/Voice |
| Twilio | `TWILIO_AUTH_TOKEN` | Authentication |
| Brevo | `BREVO_API_KEY` | Email sending |
| Brevo | `BREVO_INBOUND_KEY` | Inbound Parse verification (D9) |

## 7.4 Database & Cache

| Service | Environment Variable | Purpose |
|---------|---------------------|---------|
| PostgreSQL | `DATABASE_URL` | Database connection string |
| Redis | `REDIS_URL` | Cache/Queue broker |

---

# SECTION 8: FILE STRUCTURE (Complete Required)

```
backend/
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── database.py             # Database connection (PostgreSQL on GCP VM)
│   ├── config.py               # App configuration
│   ├── dependencies.py         # Dependency injection
│   └── middleware.py           # Global middleware
├── api/
│   ├── __init__.py
│   ├── auth.py                 # Authentication endpoints
│   ├── client.py               # Client profile endpoints (NEW)
│   ├── dashboard.py            # Dashboard endpoints
│   ├── tickets.py              # Ticket endpoints (NEW)
│   ├── approvals.py            # Approval endpoints (NEW)
│   ├── jarvis.py               # Jarvis endpoints
│   ├── agents.py               # Agent endpoints (NEW)
│   ├── analytics.py            # Analytics endpoints
│   ├── knowledge.py            # Knowledge base endpoints (NEW)
│   ├── audit_log.py            # Audit log endpoints (NEW)
│   ├── integrations.py         # Integration endpoints
│   ├── webhooks/
│   │   ├── __init__.py
│   │   ├── shopify.py
│   │   ├── paddle.py           # Paddle webhooks
│   │   ├── twilio.py
│   │   ├── email.py            # Brevo Inbound Parse webhook (D9)
│   │   └── custom.py           # Custom webhooks
│   ├── admin/
│   │   ├── __init__.py
│   │   ├── clients.py          # Admin client management
│   │   ├── services.py         # Admin service management
│   │   ├── api_providers.py    # Admin API provider config
│   │   └── monitoring.py       # Admin monitoring
│   ├── demo/
│   │   ├── __init__.py
│   │   ├── chat.py             # Demo chat
│   │   └── voice.py            # Demo voice
│   ├── checkout/
│   │   ├── __init__.py
│   │   ├── session.py          # Checkout session (Paddle)
│   │   └── pricing.py          # Pricing calculator
│   ├── onboarding/
│   │   ├── __init__.py
│   │   └── wizard.py           # Onboarding wizard
│   ├── emergency/
│   │   ├── __init__.py
│   │   ├── pause.py            # Emergency pause
│   │   └── undo.py             # Undo actions
│   ├── newsletter/
│   │   ├── __init__.py
│   │   └── subscribe.py        # Newsletter subscription (D38)
│   └── account/
│       ├── __init__.py
│       └── export.py           # Data export (D47)
├── services/
│   ├── __init__.py
│   ├── auth_service.py
│   ├── client_service.py
│   ├── ticket_service.py
│   ├── approval_service.py
│   ├── jarvis_service.py
│   ├── agent_service.py
│   ├── analytics_service.py
│   ├── knowledge_service.py
│   ├── integration_service.py
│   ├── paddle_service.py       # Paddle integration
│   ├── demo_service.py
│   ├── emergency_service.py
│   ├── first_victory_service.py
│   ├── growth_nudge_service.py
│   ├── mfa_service.py
│   ├── team_service.py
│   ├── api_key_service.py
│   ├── onboarding_service.py
│   ├── api_provider_service.py
│   ├── calculator_service.py
│   ├── context_service.py      # GSD State
│   ├── smart_router_service.py # LLM routing
│   ├── outgoing_webhook_service.py  # Outgoing webhook delivery (D22)
│   ├── circuit_breaker_service.py   # Circuit breaker pattern (D23)
│   └── customer_resolution_service.py # Customer identity resolution (D41)
├── models/
│   ├── __init__.py
│   ├── user.py
│   ├── company.py
│   ├── subscription.py
│   ├── support_ticket.py
│   ├── audit_trail.py
│   ├── usage_log.py
│   ├── knowledge_document.py
│   ├── document_chunk.py
│   ├── approval_queue.py
│   ├── agent.py
│   ├── emergency_state.py
│   ├── integration.py
│   ├── api_provider.py
│   ├── service_config.py
│   ├── onboarding_session.py
│   ├── customer.py             # End-customers (D29)
│   ├── session.py              # Conversation sessions (D29)
│   ├── interaction.py          # Conversation interactions (D29)
│   ├── overage_charge.py       # Daily overage (D10)
│   ├── user_notification_preference.py # Notification prefs (D19)
│   ├── outgoing_webhook.py     # Outgoing webhooks (D22)
│   ├── cancellation_request.py # Cancellation tracking (D33)
│   ├── newsletter_subscriber.py # Newsletter (D38)
│   ├── training_run.py         # Training runs (D45/D26)
│   └── demo_session.py         # Demo sessions (D8/D35)
├── schemas/
│   ├── __init__.py
│   ├── user.py
│   ├── company.py
│   ├── subscription.py
│   ├── ticket.py
│   ├── approval.py
│   ├── agent.py
│   ├── knowledge.py
│   ├── integration.py
│   ├── admin.py
│   ├── emergency.py
│   ├── customer.py
│   ├── session.py
│   ├── interaction.py
│   ├── overage.py
│   └── notification_preference.py
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── security.py
│   ├── jarvis_commands.py
│   ├── industry_configs/
│   └── smart_router.py         # LLM smart routing
├── socket/
│   ├── __init__.py
│   ├── manager.py              # Socket.IO connection manager
│   ├── handlers.py             # Event handlers
│   └── rooms.py                # Room management
├── tasks/                      # Celery tasks (D4)
│   ├── __init__.py
│   ├── celery_app.py           # Celery app configuration
│   ├── ticket_tasks.py
│   ├── approval_tasks.py
│   ├── notification_tasks.py
│   ├── training_tasks.py
│   ├── sync_tasks.py
│   ├── webhook_tasks.py
│   ├── voice_tasks.py
│   └── overage_tasks.py        # Daily overage charging (D10)
├── middleware/
│   ├── __init__.py
│   ├── rate_limit.py
│   ├── cache.py
│   ├── auth.py
│   └── rls.py                  # Application-level row-level security (D3)
├── utils/
│   ├── __init__.py
│   ├── cache.py
│   ├── logger.py
│   ├── encryption.py
│   └── validators.py
├── migrations/                 # Alembic migrations (D39)
│   ├── env.py
│   ├── alembic.ini
│   └── versions/
│       └── ...
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_auth.py
    ├── test_tickets.py
    ├── test_approvals.py
    └── ...
```

---

# SECTION 9: PRIORITY IMPLEMENTATION ORDER

## Phase 1: Critical (Week 1-2)
1. ✅ Paddle Payment Integration
2. ✅ Emergency Controls API
3. ✅ Admin API Provider Management
4. ✅ GSD State Engine (context_service.py)
5. ✅ Smart Router Service (LLM routing)

## Phase 2: High Priority (Week 3-4)
1. ✅ Approval Queue with Batching
2. ✅ Knowledge Base Upload & RAG
3. ✅ Agent Management APIs
4. ✅ Demo System (Chat + Voice)
5. ✅ Onboarding Wizard APIs

## Phase 3: Medium Priority (Week 5-6)
1. ✅ MFA Setup & Backup Codes
2. ✅ Team Management APIs
3. ✅ API Key Management
4. ✅ Socket.io Real-time Events
5. ✅ First Victory Tracking

## Phase 4: Enhancement (Week 7-8)
1. ✅ Growth Nudge System
2. ✅ Feature Discovery Teaser
3. ✅ Cancellation Flow (with cancellation_requests table — D33)
4. ✅ Contextual Help System
5. ✅ Analytics Export

---

# SECTION 10: NOTES

## Important Reminders

1. **Paddle NOT Stripe** — All payment integration must use Paddle (D1)
2. **Admin Flexibility** — All API providers must be configurable via Admin UI
3. **Client Integrations** — Support ANY API through custom REST/webhooks
4. **Training is LOCAL** — Agent Lightning training runs on user's hardware
5. **GCP Hosting** — 12GB RAM, 100GB storage on GCP VM (self-hosted) (D3)
6. **Socket.io** — Same GCP instance for real-time (D2)
7. **RLS** — Application-level row-level security via middleware (not Supabase RLS) (D3)
8. **Celery + Redis** — All async job processing uses Celery (not BullMQ) (D4)
9. **Google OAuth Only** — No Microsoft OAuth; email/password + Google OAuth (D11)
10. **Brevo Inbound Parse** — Email receiving via Brevo (not CloudMailin) (D9)
11. **Daily Overage** — $0.10/ticket beyond plan limit, charged daily (D10)
12. **50 Mistake Threshold** — Training triggers at 50 accumulated mistakes, with 2-week fallback (D7)
13. **Alembic Migrations** — All schema migrations managed via Alembic (D39)
14. **GCP Cloud Storage** — File storage uses GCP Cloud Storage (not Supabase Storage) (D3)

## Tech Stack Confirmed

- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL on GCP VM (self-hosted)
- **Cache/Queue**: Redis + Celery
- **Real-time**: Socket.io
- **LLM**: OpenRouter, Google AI, Cerebras, Groq (via Smart Router)
- **Payment**: Paddle
- **SMS/Voice**: Twilio
- **Email**: Brevo (sending + inbound parse)
- **File Storage**: GCP Cloud Storage
- **Migrations**: Alembic
- **Frontend Hosting**: Vercel Hobby (Free)
- **Backend Hosting**: GCP Compute Engine VM

---

END OF DOCUMENT
