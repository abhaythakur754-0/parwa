# PARWA
# Complete Infrastructure Documentation
## Based on GitHub Repository Implementation
### Version 1.0 (Corrected)
#### March 2025
Repository: github.com/abhaythakur754-0/parwa

---

## Table of Contents

1. **Architecture Overview** - Infrastructure architecture and design principles
2. **Backend Infrastructure** - FastAPI, services, workers, and API structure
3. **Frontend Infrastructure** - Next.js 15, TypeScript, and component architecture
4. **Database Infrastructure** - PostgreSQL on GCP VM, Redis, migrations, and schema
5. **MCP Servers** - Model Context Protocol servers architecture
6. **AI/ML Infrastructure** - GSD Engine, Smart Router, Agent Lightning
7. **External Integrations** - Paddle, Twilio, Shopify, and other services
8. **Security Infrastructure** - Rate limiting, authentication, encryption
9. **Monitoring & Observability** - Prometheus, Grafana, logging, and alerting
10. **Container Infrastructure** - Docker Compose and container architecture
11. **Kubernetes Infrastructure** - Deployments, HPA, and scaling strategies
12. **Local Training Infrastructure** - Agent Lightning fine-tuning setup
13. **CI/CD Pipeline** - Deployment automation and workflows
14. **Disaster Recovery** - Backup, recovery, and business continuity
15. **Cost Estimation** - Monthly costs and scaling economics
16. **Pre-Launch Checklist** - Complete deployment verification

---

## 1. Architecture Overview

### 1.1 System Architecture

PARWA is a multi-tenant AI customer care platform built on a modern microservices architecture. The system is designed for high availability, horizontal scalability, and enterprise-grade security. The architecture follows a layered approach with clear separation between frontend presentation, backend business logic, AI processing, and data persistence layers.

**Hosting Architecture:** GCP Compute Engine VM (all backend services) + Vercel Hobby (frontend only). The backend runs on a single GCP VM during early stage, with the frontend deployed on Vercel's free tier. This architecture keeps costs at ~$25-30/mo for the first 10-12 months using GCP free tier credits.

### 1.2 Core Components

| Component | Technology | Purpose |
|---|---|---|
| Backend API | FastAPI (Python 3.11+) | REST API, business logic, orchestration |
| Frontend | Next.js 15 + TypeScript | Web UI, dashboard, admin panel (hosted on Vercel) |
| Database | PostgreSQL 15+ (self-hosted on GCP VM) | Primary data store |
| Cache/Queue | Redis 7+ | Caching, sessions, Celery task queues |
| Real-time | Socket.io | Real-time bidirectional communication |
| Job Queue | Celery + Redis | Background job processing, scheduled tasks |
| Auth | Self-built JWT auth (FastAPI + PostgreSQL) + Google OAuth | Email/password + Google OAuth authentication |
| File Storage | GCP Cloud Storage | Document storage, model weights, exports |
| Email Receiving | Brevo Inbound Parse | Inbound email processing |
| AI Engine | GSD Engine + Smart Router | State management, LLM routing |
| MCP Servers | Python FastAPI | Knowledge, integrations, tools |
| Workers | Python Celery | Background jobs, scheduled tasks |
| Monitoring | Prometheus + Grafana | Metrics, dashboards, alerting |
| Container | Docker + Docker Compose | Containerization, orchestration |
| Orchestration | Kubernetes (production) | Production deployment, autoscaling |

*Table 1.1: Core Infrastructure Components*

### 1.3 Key Design Principles

The infrastructure follows several critical design principles that ensure reliability, maintainability, and scalability.

1. **Multi-tenant isolation:** Each client organization is isolated at the database level using tenant_id foreign keys with application-level row-level security via middleware, ensuring complete data separation.

2. **Approval gate pattern:** All financial operations require explicit approval records before any payment processing through Paddle.

3. **Async-first backend:** Leveraging Python asyncpg for database connections and async/await patterns for all I/O operations.

4. **GCP VM + Vercel architecture:** Backend services (FastAPI, PostgreSQL, Redis, Celery workers) all run on a single GCP Compute Engine VM. Frontend is deployed on Vercel Hobby (free tier).

5. **Self-built JWT authentication:** Authentication uses FastAPI + PostgreSQL with self-built JWT token management. Google OAuth is supported for social login. No Microsoft OAuth.

6. **Daily overage billing:** Overage charges are processed daily at $0.10/ticket with anti-scam protection, rather than end-of-month billing.

7. **Onboarding duration varies by client complexity:** No fixed timeline promises for onboarding.

---

## 2. Backend Infrastructure

### 2.1 FastAPI Application Structure

The backend is built on FastAPI, a modern Python web framework optimized for building APIs with automatic OpenAPI documentation. The application follows a modular structure with clear separation of concerns, implementing the repository pattern for data access and dependency injection for service composition. The main application entry point is located at backend/app/main.py, with routers organized by domain.

### 2.2 Backend Directory Structure

```
backend/
├── app/
│   ├── main.py          # FastAPI entry point
│   ├── config.py        # Application configuration
│   ├── database.py      # PostgreSQL connection (GCP VM)
│   ├── dependencies.py  # Dependency injection
│   └── middleware.py     # Request/response middleware
├── api/
│   ├── auth.py          # Authentication endpoints (JWT + Google OAuth)
│   ├── analytics.py     # Analytics endpoints
│   ├── jarvis.py        # Jarvis command endpoints
│   ├── billing.py       # Billing endpoints
│   ├── compliance.py    # Compliance endpoints
│   ├── integrations.py  # Integration management
│   ├── webhooks/        # Webhook handlers (Paddle, Brevo Inbound Parse)
│   └── routes/          # Feature-specific routes
├── services/
│   ├── approval_service.py
│   ├── billing_service.py
│   ├── compliance_service.py
│   ├── cold_start/
│   ├── burst_mode/
│   ├── undo_manager/
│   └── client_success/
├── workers/             # Celery workers (replacing BullMQ)
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic schemas
├── security/            # Security utilities (self-built JWT)
├── nlp/                 # NLP processing
├── quality_coach/       # Quality coaching (PARWA High)
├── billing/             # Enterprise billing
├── compliance/          # Compliance management
├── optimization/        # Resource optimization
└── sso/                 # SSO/SAML integration
```

### 2.3 Core Services

| Service | File | Description |
|---|---|---|
| Approval Service | approval_service.py | Manages approval workflows for AI actions |
| Billing Service | billing_service.py | Subscription and payment management (Paddle) |
| Compliance Service | compliance_service.py | GDPR, SOC 2 compliance enforcement |
| SLA Service | sla_service.py | SLA tracking and breach detection |
| Onboarding Service | onboarding_service.py | Client onboarding (duration varies by complexity) |
| Notification Service | notification_service.py | Multi-channel notifications (10 HTML templates via Brevo) |
| Escalation Service | escalation_service.py | Escalation ladder management |
| User Service | user_service.py | User management, JWT auth, Google OAuth |
| Voice Handler | voice_handler.py | Voice call processing (phone number required for demo) |
| License Service | license_service.py | License management for enterprise |

*Table 2.1: Backend Core Services*

### 2.4 Background Workers (Celery + Redis)

PARWA implements a robust background worker system using **Celery + Redis** for task queue management. Workers handle long-running tasks asynchronously, ensuring the main API remains responsive. The Celery workers module includes specialized handlers for different task types, each with retry logic and error handling.

| Worker | Purpose | Trigger |
|---|---|---|
| recall_handler.py | Process recall requests | Webhook/API |
| kb_indexer.py | Index knowledge base documents | File upload |
| proactive_outreach.py | Send proactive notifications | Scheduled |
| report_generator.py | Generate analytics reports | Scheduled |
| overage_billing.py | Process daily overage charges | Daily scheduled ($0.10/ticket) |
| email_parse_handler.py | Process Brevo Inbound Parse webhooks | Email received |

*Table 2.2: Background Workers (Celery)*

### 2.5 Authentication

PARWA uses **self-built JWT authentication** (FastAPI + PostgreSQL) with Google OAuth as the sole social login provider.

- **Email + Password:** Standard JWT token-based authentication
- **Google OAuth:** Social login via Google only (no Microsoft OAuth)
- **Token Management:** JWT access tokens with refresh token rotation
- **Environment Variables:** `DATABASE_URL`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`

---

## 3. Frontend Infrastructure

### 3.1 Next.js 15 Architecture

The frontend is built on Next.js 15 with TypeScript, leveraging the App Router for modern server-side rendering and streaming capabilities. The application is **deployed on Vercel Hobby (free tier)** for cost optimization. It follows a component-based architecture with shadcn/ui for consistent styling and Radix UI primitives for accessibility. State management is handled through Zustand stores, with React Query for server state synchronization. **Socket.io** provides real-time bidirectional communication between the frontend and backend.

### 3.2 Frontend Directory Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   ├── register/
│   │   │   └── forgot-password/
│   │   ├── dashboard/
│   │   │   ├── approvals/
│   │   │   ├── agents/
│   │   │   ├── analytics/
│   │   │   ├── settings/
│   │   │   └── jarvis/
│   │   ├── onboarding/
│   │   ├── variants/
│   │   └── globals.css
│   ├── components/
│   │   ├── ui/              # Base UI components (shadcn/ui)
│   │   ├── dashboard/       # Dashboard components
│   │   ├── onboarding/      # Onboarding wizard
│   │   ├── pricing/         # Pricing calculator
│   │   ├── variants/        # Variant cards
│   │   ├── analytics/       # Charts and metrics
│   │   ├── settings/        # Settings panels
│   │   ├── financial/       # Financial widgets
│   │   └── enterprise/      # Enterprise components
│   ├── hooks/
│   ├── services/
│   ├── stores/
│   ├── utils/
│   ├── validations/
│   ├── lib/
│   │   └── socket.ts        # Socket.io client configuration
│   └── package.json
```

### 3.3 Key UI Components

| Component Category | Components | Count |
|---|---|---|
| Base UI (shadcn/ui) | Button, Input, Dialog, Table, Tabs, Badge, etc. | 20+ |
| Dashboard Widgets | StatsCard, ApprovalQueue, JarvisTerminal, AgentStatus | 15+ |
| Onboarding | OnboardingWizard, IndustrySelect, KnowledgeUpload | 10+ |
| Pricing | PricingCalculator, ROIComparison, VariantCard | 6+ |
| Analytics | Chart, MetricsGrid, DateRangePicker, ExportButton | 8+ |
| Settings | SettingsNav, ProfileForm, TeamManager, BillingPanel | 12+ |
| Enterprise | SSOConfigWizard, ContractViewer, CompliancePanel | 5+ |

*Table 3.1: Frontend Component Categories*

### 3.4 Custom Hooks

| Hook | Purpose |
|---|---|
| useAuth | Authentication state and login/logout actions |
| useTickets | Ticket fetching and management |
| useApprovals | Approval queue management |
| useAgents | AI agent status and management |
| useJarvis | Jarvis command interface |
| useAnalytics | Analytics data fetching |
| useNotifications | Real-time notification handling (via Socket.io) |
| useSearch | Search functionality |
| useTheme | Theme switching and persistence |
| useMediaQuery | Responsive design utilities |
| useSocket | Socket.io connection and event management |

*Table 3.2: Custom React Hooks*

---

## 4. Database Infrastructure

### 4.1 PostgreSQL Configuration (Self-Hosted on GCP VM)

PARWA uses **PostgreSQL 15+ self-hosted on GCP VM** as its primary database. This is a single self-hosted PostgreSQL instance running directly on the GCP Compute Engine VM — no managed services like Supabase. The database is configured with:

- Connection pooling via PgBouncer
- SSL encryption for all connections
- **Application-level row-level security via middleware** (not database-level RLS)
- Multi-tenancy with tenant_id foreign keys on all tenant-scoped tables
- All migrations managed through **Alembic** (D39)

Environment variable: `DATABASE_URL` (PostgreSQL connection string)

### 4.2 Core Database Tables

| Table | Purpose | Key Fields |
|---|---|---|
| tenants | Organizations/companies | id, name, tier, settings, is_active |
| users | Dashboard users | id, tenant_id, email, role, password_hash |
| api_keys | Integration API keys | id, tenant_id, name, key_hash, permissions |
| customers | End customers | id, tenant_id, external_id, email, phone |
| sessions | Conversation sessions | id, tenant_id, customer_id, channel, status |
| interactions | Chat/voice logs | id, session_id, role, content, model_used |
| human_corrections | Agent Lightning training | id, interaction_id, ai_draft, human_approved |
| audit_logs | Audit trail | id, tenant_id, actor_type, action_type, details |
| overage_charges | Daily overage billing | id, tenant_id, date, tickets_over, amount, status |
| approval_records | Approval gate for financial ops | id, tenant_id, action_type, status, approver_id |

*Table 4.1: Core Database Tables*

### 4.3 Database Migrations

Database migrations are managed through **Alembic** (D39), providing version-controlled schema changes. The migrations directory contains sequential migration files for each phase of development, allowing for both forward migrations and rollbacks.

| Migration | Description |
|---|---|
| 001_initial_schema.py | Core tables: tenants, users, customers, sessions |
| 002_agent_lightning.py | Training tables and human corrections |
| 003_audit_trail.py | Audit logging infrastructure |
| 004_compliance.py | GDPR/SOC 2 compliance tables |
| 005_feature_flags.py | Feature flag system |
| 006_multi_region.py | Multi-region data residency |
| 007_sessions_interactions.py | Session and interaction enhancements |
| 008_financial_services.py | Financial services features |
| 009_performance.py | Performance optimization indexes |
| 010_overage_charges.py | Daily overage billing table |
| 011_phase8_week28.py | Phase 8 enhancements |

*Table 4.2: Database Migrations (Alembic)*

### 4.4 Redis Configuration

Redis 7+ serves multiple purposes in the PARWA infrastructure: session storage for distributed sessions, caching layer for API responses and computed values, message broker for **Celery** task processing, and real-time state management for **Socket.io** clustering. The Redis instance is configured with AOF persistence for durability and runs on the same GCP VM as the backend.

```properties
# Redis Configuration (redis.conf)
# Memory Management
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence
appendonly yes
appendfsync everysec
save 900 1
save 300 10
save 60 10000

# Network
bind 127.0.0.1
port 6379
protected-mode yes
requirepass ${REDIS_PASSWORD}

# Performance
tcp-keepalive 300
timeout 0
```

---

## 5. MCP Servers Infrastructure

### 5.1 MCP Architecture Overview

PARWA implements the Model Context Protocol (MCP) for standardized AI tool and knowledge access. MCP servers are specialized FastAPI services that expose tools, resources, and prompts to the AI orchestration layer. Each server is independently deployable and scalable, with its own health endpoints and metrics collection.

### 5.2 MCP Server Categories

| Category | Server | Port | Purpose |
|---|---|---|---|
| Knowledge | mcp-faq-server | 5001 | FAQ retrieval and matching |
| Knowledge | mcp-rag-server | 5002 | RAG-based document retrieval |
| Knowledge | mcp-kb-server | 5003 | Knowledge base management |
| Integration | mcp-email-server | 5101 | Email sending and templates |
| Integration | mcp-voice-server | 5102 | Voice call handling |
| Integration | mcp-chat-server | 5103 | Chat message processing |
| Integration | mcp-ticketing-server | 5104 | Ticket management integration |
| Tools | mcp-notification-server | 5201 | Multi-channel notifications |
| Tools | mcp-compliance-server | 5202 | Compliance checking |
| Tools | mcp-sla-server | 5203 | SLA monitoring |

*Table 5.1: MCP Server Inventory*

### 5.3 MCP Client Implementation

The MCP client (shared/mcp_client/) provides a Python interface for connecting to MCP servers, discovering available tools and resources, and executing tool calls. The client handles authentication, connection pooling, and automatic reconnection on failure.

---

## 6. AI/ML Infrastructure

### 6.1 GSD State Engine

The GSD (Get Stuff Done) State Engine manages the execution state for AI-driven workflows. **GSD runs INSIDE LangGraph as a dedicated node, executing on EVERY conversation.** It tracks context health, manages state compression when context windows fill up, and provides visibility into AI decision-making processes. The engine is implemented in shared/gsd_engine/.

| Module | Purpose |
|---|---|
| state_engine.py | Core state management and transitions (LangGraph node) |
| state_schema.py | Pydantic models for state structure |
| context_health.py | Context window health monitoring |
| compression.py | State compression algorithms |

*Table 6.1: GSD Engine Components*

### 6.2 Smart Router

The Smart Router intelligently routes AI requests to appropriate LLM providers based on task complexity, cost optimization, and latency requirements. It implements ML-based classification to determine the optimal model tier (Light, Medium, Heavy) and selects providers from a configurable pool.

| Module | Purpose |
|---|---|
| routing_engine.py | Main routing logic |
| ml_classifier.py | ML-based complexity classification |
| complexity_scorer.py | Task complexity scoring |
| cost_optimizer.py | Cost-aware routing decisions |
| failover.py | Provider failover handling |
| selection/model_selector.py | Model selection logic |
| selection/latency_manager.py | Latency optimization |
| selection/fallback_chain.py | Fallback provider chains |

*Table 6.2: Smart Router Components*

### 6.2.1 Confidence Scoring Weights (D21)

```python
DEFAULT_CONFIDENCE_WEIGHTS = {
    "pattern_match": 0.25,
    "policy_alignment": 0.20,
    "historical_success": 0.15,
    "risk_signals": 0.15,
    "context_completeness": 0.10,
    "ambiguity": 0.05,
    "model_certainty": 0.05,
    "sentiment": 0.05
}
```

**Thresholds:** >80 auto-execute, 50-80 approval queue, <50 escalate

### 6.2.2 Approval Timeout Ladder (D40)

Where the approval queue is active, the following escalation ladder applies:

- **2 hours** -> reminder to approver
- **4 hours** -> escalate to team lead
- **8 hours** -> auto-assign next manager
- **24 hours** -> notify company admin
- **72 hours** -> auto-reject

### 6.3 Agent Lightning (Local Training)

Agent Lightning is PARWA's continuous learning system that fine-tunes AI models on client-specific data. Training is performed **LOCALLY** on client hardware (not in the cloud) to protect data privacy. The system exports training data from human corrections, processes it locally, and uploads the resulting model weights to **GCP Cloud Storage** for deployment.

**Training Threshold:** 50 accumulated mistakes trigger retraining (not 100). Additionally, a **time-based fallback** triggers every 2 weeks regardless of mistake count.

**Training Workflow:**

1. **Data Collection:** Human corrections from approval rejections are logged in human_corrections table.
2. **Export:** Training data is exported as JSONL format for processing.
3. **Local Training:** Fine-tuning runs on local GPU (RTX 3090/4090 recommended).
4. **Model Upload:** Trained weights are uploaded to **GCP Cloud Storage**.
5. **Activation:** New model version is activated for the client.

---

## 7. External Integrations

### 7.1 Paddle (Payments)

Paddle serves as the Merchant of Record for PARWA, handling subscription billing, tax compliance, and refund processing. The integration includes a critical approval gate pattern: Paddle refunds CANNOT be processed without a corresponding pending_approval record in the database.

**Environment Variable:** `PADDLE_API_KEY` (replaces any STRIPE_SECRET_KEY)

| Feature | Implementation |
|---|---|
| Subscription Management | create_subscription(), cancel_subscription(), get_subscription() |
| Refund Processing | process_refund() with approval gate validation (Paddle refund API) |
| Webhook Handling | verify_webhook() with HMAC-SHA256 signature verification |
| Customer Management | get_customer(), customer data synchronization |
| Environment Support | Sandbox and Production environments |

*Table 7.1: Paddle Integration Features*

### 7.2 Twilio (SMS/Voice)

Twilio integration enables SMS and voice communication with end customers. **Phone number is required before any voice demo can start** (D14). The client supports both sandbox and production environments, with comprehensive error handling and status tracking.

| Feature | Implementation |
|---|---|
| SMS Sending | send_sms() with E.164 format support |
| WhatsApp Messaging | send_whatsapp() for WhatsApp Business API |
| Voice Calls | make_call() with TwiML URL support |
| Phone Validation | validate_phone_number() with carrier info |
| Status Tracking | get_message_status(), get_call_status() |

*Table 7.2: Twilio Integration Features*

### 7.3 Brevo (Email)

Brevo handles all transactional email sending as well as **inbound email processing via Brevo Inbound Parse** (D9). The system includes 10 pre-built HTML templates: welcome, verify_email, password_reset, weekly_wins, invoice, approval_notification, cancellation, first_victory, training_complete, data_export_ready.

| Feature | Implementation |
|---|---|
| Transactional Email | send_email() with template support |
| Inbound Parse | Brevo Inbound Parse webhook for receiving emails |
| Templates | 10 HTML email templates |
| Domain Config | SPF, DKIM, DMARC verified |

*Table 7.3: Brevo Integration Features*

### 7.4 Other Integrations

| Integration | File | Purpose |
|---|---|---|
| Shopify | shopify_client.py | E-commerce order and customer sync |
| GitHub | github_client.py | Issue tracking and repository access |
| Zendesk | zendesk_client.py | Ticket system integration |
| AfterShip | aftership_client.py | Shipment tracking |
| Salesforce | salesforce_client.py | CRM and customer data sync |

*Table 7.4: Additional Integrations*

---

## 8. Security Infrastructure

### 8.1 Rate Limiting

PARWA implements an advanced rate limiter with multiple strategies and per-tenant limits. The rate limiter supports fixed window, sliding window, token bucket, and leaky bucket algorithms. Each tenant can be assigned to a tier (free, basic, pro, enterprise) with different limits.

| Tier | Req/Sec | Req/Min | Req/Hour | Burst |
|---|---|---|---|---|
| Free | 2 | 30 | 500 | 5 |
| Basic | 5 | 100 | 2,000 | 20 |
| Pro | 10 | 300 | 10,000 | 50 |
| Enterprise | 50 | 2,000 | 100,000 | 200 |

*Table 8.1: Rate Limit Tiers*

### 8.2 Security Components

| Component | File | Purpose |
|---|---|---|
| Session Manager | session_manager.py | Secure session handling |
| Rate Limiter | rate_limiter_advanced.py | API rate limiting |
| API Key Manager | api_key_manager.py | API key generation and validation |
| IP Allowlist | ip_allowlist.py | IP-based access control |
| HMAC Verification | hmac_verification.py | Webhook signature verification |
| Feature Flags | feature_flags.py | Feature access control |

*Table 8.2: Security Components*

> **Note:** KYC / Stripe Identity is **skipped for v1 entirely** (D1).

### 8.3 Audit and Compliance

The security/audit/ directory contains tools for ongoing security compliance, including OWASP scanning, CVE checking, penetration testing, and compliance matrix validation. All security audit results are logged and tracked for compliance reporting.

---

## 9. Monitoring & Observability

### 9.1 Prometheus Configuration

Prometheus is configured to scrape metrics from all PARWA components, including the backend API, GSD engine, Smart Router, and all MCP servers. Metrics are collected every 10-15 seconds depending on the service criticality.

| Job Name | Target | Interval |
|---|---|---|
| parwa-backend-api | localhost:8000 | 10s |
| parwa-gsd-engine | localhost:8001 | 10s |
| parwa-smart-router | localhost:8002 | 10s |
| mcp-knowledge-servers | localhost:5001-5003 | 15s |
| mcp-integration-servers | localhost:5101-5104 | 15s |
| mcp-tool-servers | localhost:5201-5203 | 15s |
| redis | localhost:9121 | 30s |
| postgresql | localhost:9187 | 30s |
| node | localhost:9100 | 30s |

*Table 9.1: Prometheus Scrape Targets*

### 9.2 Grafana Dashboards

| Dashboard | Purpose |
|---|---|
| main-dashboard.json | System-wide overview and health |
| multi_client_dashboard.json | Multi-tenant client metrics |
| performance_dashboard.json | Performance and latency metrics |
| compliance-dashboard.json | GDPR/SOC 2 compliance status |
| sla-dashboard.json | SLA tracking and breach alerts |
| quality.json | AI response quality metrics |
| mcp-dashboard.json | MCP server health and performance |
| financial_services.json | Financial services metrics |
| client_success_dashboard.json | Client health and retention |

*Table 9.2: Grafana Dashboards*

---

## 10. Container Infrastructure

### 10.1 Docker Compose Production

The production Docker Compose configuration (docker-compose.prod.yml) defines all services with health checks, resource limits, and network isolation. The configuration supports horizontal scaling through replica counts and implements the principle of least privilege with no-new-privileges security options.

| Service | Image | Memory | Replicas |
|---|---|---|---|
| db | postgres:15-alpine | 1GB limit | 1 |
| redis | redis:7-alpine | 512MB limit | 1 |
| backend | parwa/backend | 1GB limit | 2 |
| celery-worker | parwa/worker | 512MB limit | 2 |
| celery-beat | parwa/beat | 256MB limit | 1 |
| mcp | parwa/mcp | 512MB limit | 1 |
| frontend | parwa/frontend | 512MB limit | 1 |
| prometheus | prom/prometheus:v2.45.0 | 512MB limit | 1 |
| grafana | grafana/grafana:10.0.0 | 256MB limit | 1 |
| nginx | nginx:alpine | 128MB limit | 1 |

*Table 10.1: Docker Compose Services*

### 10.2 Network Isolation

The Docker Compose configuration implements network isolation with three separate networks: backend_network (internal, not accessible from outside), frontend_network (bridge for external access), and monitoring_network (internal for Prometheus/Grafana). This ensures the database and internal services are not directly exposed to the internet.

---

## 11. Kubernetes Infrastructure

### 11.1 Horizontal Pod Autoscaler

The Kubernetes deployment includes a Horizontal Pod Autoscaler (HPA) configuration for the backend service, enabling automatic scaling from 3 to 50 replicas based on CPU and memory utilization. The HPA is configured with conservative scale-down policies to prevent thrashing.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: parwa-backend-hpa
spec:
  scaleTargetRef:
    kind: Deployment
    name: parwa-backend
  minReplicas: 3
  maxReplicas: 50
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
    scaleUp:
      stabilizationWindowSeconds: 60
```

### 11.2 Deployment Strategy

Kubernetes deployments follow a rolling update strategy with maxSurge and maxUnavailable settings configured for zero-downtime deployments. Each deployment includes liveness and readiness probes to ensure traffic is only routed to healthy pods.

---

## 12. Local Training Infrastructure

### 12.1 Hardware Requirements

Agent Lightning training runs on LOCAL hardware, not in the cloud. This ensures data privacy and gives clients full control over their training data. The recommended hardware configuration depends on the base model being fine-tuned and the training dataset size.

| Component | Minimum | Recommended |
|---|---|---|
| CPU | 8 cores | 16+ cores |
| GPU | RTX 3090 (24GB) | RTX 4090 / A100 |
| RAM | 32GB | 64GB+ |
| Storage | 500GB NVMe SSD | 1TB+ NVMe SSD |
| CUDA | 11.8+ | 12.0+ |

*Table 12.1: Local Training Hardware Requirements*

### 12.2 Training Data Flow

1. Human corrections are logged in the database when managers override AI decisions.
2. Training data export API extracts corrections as JSONL format.
3. JSONL files are downloaded to local training machine.
4. Fine-tuning script runs locally using LoRA for efficient training.
5. Trained model weights are uploaded to **GCP Cloud Storage**.
6. Model version is activated for the client through API.

---

## 13. CI/CD Pipeline

### 13.1 Deployment Workflow

PARWA uses a GitOps-style deployment workflow with automated testing, building, and deployment. The pipeline runs on every push to main branch and includes comprehensive testing, security scanning, and deployment verification steps.

| Step | Action | On Failure |
|---|---|---|
| 1 | Checkout Clone repository | Stop pipeline |
| 2 | Setup Install Node.js, Python | Stop pipeline |
| 3 | Install npm ci, pip install | Stop pipeline |
| 4 | Lint Run linters | Stop pipeline |
| 5 | Test Run unit/integration tests | Stop pipeline |
| 6 | Build Build frontend/backend | Stop pipeline |
| 7 | Security Scan Dependency check, CVE scan | Alert, continue |
| 8 | Deploy Deploy to target environment | Rollback |
| 9 | Verify Health check, smoke tests | Rollback |
| 10 | Notify Slack notification | N/A |

*Table 13.1: CI/CD Pipeline Steps*

---

## 14. Disaster Recovery

### 14.1 Backup Strategy

| Component | Backup Type | Frequency | Retention |
|---|---|---|---|
| PostgreSQL (GCP VM) | Full backup + WAL | Daily + Continuous | 30 days + PITR |
| Redis | RDB snapshot + AOF | Hourly + Real-time | 7 days |
| Model Weights (GCP Cloud Storage) | Full backup | On new version | Indefinite |
| Documents (GCP Cloud Storage) | Incremental | Daily | 90 days |
| Configuration | Git versioned | On change | Indefinite |

*Table 14.1: Backup Strategy*

### 14.2 Recovery Objectives

- **Recovery Time Objective (RTO):** 1 hour — Target time to restore service after a disaster.
- **Recovery Point Objective (RPO):** 1 hour — Maximum acceptable data loss measured in time.

These objectives are achieved through a combination of automated backups, point-in-time recovery for PostgreSQL, and redundant infrastructure components.

---

## 15. Cost Estimation

### 15.1 Monthly Operating Costs

> **Cost Model (D3):** ~$25-30/mo for the first 10-12 months using GCP free tier credits. After credits expire, costs scale based on usage.

| Service | Provider | Tier | Cost/Month |
|---|---|---|---|
| Compute (Backend) | GCP Compute Engine VM | e2-medium (4 vCPU, 12GB RAM) | ~$25-30 (with credits: $0) |
| Database | PostgreSQL (self-hosted on GCP VM) | Included in compute | $0 (included) |
| Redis | Self-hosted on GCP VM | Included in compute | $0 (included) |
| Frontend | Vercel Hobby | Free tier | $0 |
| Email | Brevo Starter (20k emails) | 20k emails | $25 |
| SMS/Voice | Twilio | Pay-per-use | $50-100 |
| LLM APIs | OpenRouter | Mixed tiers | $100-300 |
| Payments | Paddle | 5% + $0.50/txn | Variable |
| Domain | Cloudflare Pro | $20/mo | $20 |
| Monitoring | Self-hosted Prometheus/Grafana | On GCP VM | $0 (included) |
| File Storage | GCP Cloud Storage | Standard class | ~$5-20 |
| **TOTAL (with GCP credits)** | | | **~$100-445** |
| **TOTAL (after credits expire)** | | | **~$125-475** |

*Table 15.1: Monthly Operating Costs*

### 15.2 Per-Client Economics

| Plan | Revenue/Month | Variable Cost | Gross Margin |
|---|---|---|---|
| PARWA Starter | $999 | $5-20 | ~$979 |
| PARWA Growth | $2,499 | $15-50 | ~$2,449 |
| PARWA High | $3,999 | $30-100 | ~$3,899 |

*Table 15.2: Per-Client Economics*

### 15.3 Plan Details

#### PARWA Starter — $999/month
- Ticket Limit: 2,000 tickets/month
- Overage: $0.10 per additional ticket (daily billing)
- AI Agents: 1 agent
- Channels: Email + Live Chat
- Voice: Not included
- SMS: Not included
- Knowledge Base: 100 documents
- Team Members: 3 users
- Onboarding: Self-serve

#### PARWA Growth — $2,499/month
- Ticket Limit: 5,000 tickets/month
- Overage: $0.10 per additional ticket (daily billing)
- AI Agents: 3 agents
- Channels: Email + Live Chat + SMS
- Voice: 2 concurrent voice slots
- Knowledge Base: 500 documents
- Team Members: 10 users
- Onboarding: Guided + setup assistance

#### PARWA High — $3,999/month
- Ticket Limit: 15,000 tickets/month
- Overage: $0.10 per additional ticket (daily billing)
- AI Agents: 5 agents
- Channels: Email + Live Chat + SMS + Voice + Social
- Voice: 5 concurrent voice slots
- Knowledge Base: 2,000 documents
- Team Members: 25 users
- Onboarding: White-glove

### 15.4 Add-On Services

| Add-On | Price |
|---|---|
| Managed Training | $50/month |
| Voice Demo | $1 one-time (phone number required) |
| Extra Agent | $200/month |
| Extra Voice Slot | $100/month |
| SMS Pack (1000) | $15/month |
| Social Media Pack | $100/month |

### 15.5 Cancellation & Refund Policy (D13)

#### Cancellation Policy (Netflix-Style)

| Rule | Description |
|------|-------------|
| **No Refunds** | No refunds for cancelled subscriptions - once paid, no money back |
| **Cancel Anytime** | Client can cancel auto-renewal anytime during the month |
| **Access Until Month End** | After cancellation, access continues until the billing period ends |
| **No Partial Refunds** | No refund for unused days in the month |

**Flow:**
```
Client pays for Month X (e.g., April 1-30)
        ↓
Client cancels auto-renewal on April 15
        ↓
Access continues until April 30 (month end)
        ↓
No charge for May (auto-renewal cancelled)
        ↓
No refund for April 16-30 (unused days)
```

**Subscription End Logic:**
- Subscription works until the ticket limit is hit OR the month ends — whichever is **last**
- This ensures clients always get full value from their subscription
- No fixed grace period

#### Refund Policy

| Scenario | Refund? |
|----------|---------|
| Client cancels mid-month | ❌ No refund |
| Client unused tickets | ❌ No refund |
| Client upgrades mid-month | Proration credit applied (not refund) |
| Service outage | Credit applied to next billing (not refund) |
| Billing error by PARWA | ✅ Full refund of erroneous charge |

**Key Principle:** Like Netflix - pay for the month, use the month. No money back.

---

## 16. Pre-Launch Checklist

### 16.1 Infrastructure Checklist

- [ ] GCP Compute Engine VM created and configured
- [ ] Static IP assigned and DNS configured
- [ ] SSL certificate installed (Let's Encrypt)
- [ ] Firewall rules configured (ports 80, 443 only)
- [ ] Nginx reverse proxy configured
- [ ] Vercel project created and connected to frontend repo

### 16.2 Database Checklist

- [ ] PostgreSQL installed and configured on GCP VM
- [ ] DATABASE_URL environment variable set
- [ ] Alembic migrations applied (all versions)
- [ ] Application-level row-level security middleware enabled
- [ ] GCP Cloud Storage buckets created (documents, model-weights, exports)
- [ ] Backups configured and tested

### 16.3 Services Checklist

- [ ] Paddle account verified (sandbox and production)
- [ ] PADDLE_API_KEY configured
- [ ] Twilio numbers provisioned and verified
- [ ] Brevo domain verified (SPF, DKIM, DMARC)
- [ ] Brevo Inbound Parse webhook configured
- [ ] LLM API keys obtained and tested
- [ ] All webhooks configured and tested
- [ ] Google OAuth configured (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
- [ ] Socket.io real-time layer tested

### 16.4 Security Checklist

- [ ] All secrets stored securely (not in code)
- [ ] JWT_SECRET configured for self-built auth
- [ ] Rate limiting enabled and tested
- [ ] CORS configured for production domain
- [ ] Security headers set (HSTS, CSP, X-Frame-Options)
- [ ] MFA enabled for admin accounts

### 16.5 Monitoring Checklist

- [ ] Health check endpoints working
- [ ] Prometheus scraping all targets
- [ ] Grafana dashboards configured
- [ ] Alert rules configured
- [ ] On-call rotation established

---

## Appendix: Environment Variables

| Variable | Description | Notes |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | GCP VM self-hosted |
| `REDIS_URL` | Redis connection string | GCP VM self-hosted |
| `JWT_SECRET` | JWT signing secret | Self-built auth |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | No Microsoft OAuth |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | |
| `PADDLE_API_KEY` | Paddle API key | Merchant of Record |
| `TWILIO_ACCOUNT_SID` | Twilio account | SMS/Voice |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | |
| `BREVO_API_KEY` | Brevo API key | Email sending |
| `OPENROUTER_API_KEY` | OpenRouter API key | LLM access |
| `GCP_STORAGE_BUCKET` | GCP Cloud Storage bucket | File storage |
| `CELERY_BROKER_URL` | Redis URL for Celery | Job queue broker |
