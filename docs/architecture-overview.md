# PARWA Architecture Overview

## System Overview

PARWA is an AI-powered customer support automation platform that provides three tiers of service: Mini, Junior, and Senior. The platform combines modern web technologies with advanced AI capabilities to automate customer support workflows while maintaining human oversight for critical decisions.

## Table of Contents

1. [System Diagram](#system-diagram)
2. [Component Overview](#component-overview)
3. [Data Flow](#data-flow)
4. [Integration Points](#integration-points)
5. [Technology Stack](#technology-stack)
6. [Design Decisions](#design-decisions)

---

## System Diagram

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SERVICES                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Paddle  │  │ OpenAI   │  │ Supabase │  │ SendGrid │  │   S3     │       │
│  │ Payments │  │   API    │  │   DB     │  │  Email   │  │ Storage  │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
└───────┼─────────────┼─────────────┼─────────────┼─────────────┼──────────────┘
        │             │             │             │             │
        └─────────────┴─────────────┴──────┬──────┴─────────────┘
                                            │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INGRESS LAYER                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    NGINX Ingress Controller                           │   │
│  │         TLS Termination • Rate Limiting • WAF                        │   │
│  └──────────────────────────────┬───────────────────────────────────────┘   │
└─────────────────────────────────┼───────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│   FRONTEND    │         │    BACKEND    │         │   WEBSOCKET   │
│   (Next.js)   │         │   (FastAPI)   │         │   (FastAPI)   │
│   Port: 3000  │         │   Port: 8000  │         │   Port: 8000  │
│               │         │               │         │               │
│ 2-5 replicas  │         │  3-10 replicas│         │  Streaming    │
│ Static Files  │         │  REST API     │         │  Jarvis AI    │
│ SSR/SSG       │         │  Business     │         │               │
│               │         │  Logic        │         │               │
└───────┬───────┘         └───────┬───────┘         └───────┬───────┘
        │                         │                         │
        └─────────────────────────┼─────────────────────────┘
                                  │
┌─────────────────────────────────┼───────────────────────────────────────────┐
│                         INTERNAL SERVICES                                     │
│                               │                                              │
│  ┌──────────────┐  ┌──────────┴──────────┐  ┌────────────────────────────┐  │
│  │    WORKER    │  │       REDIS         │  │    MCP SERVERS             │  │
│  │   (ARQ)      │  │   (Cache/Queue)     │  │  (Model Context Protocol)  │  │
│  │              │  │                     │  │                            │  │
│  │ Background   │  │ - Session cache     │  │ - Knowledge MCP (8001)     │  │
│  │ Tasks        │  │ - Rate limiting     │  │ - Analytics MCP (8002)     │  │
│  │ Scheduled    │  │ - Job queue         │  │ - Actions MCP (8003)       │  │
│  │ Jobs         │  │ - Pub/Sub           │  │                            │  │
│  └──────┬───────┘  └──────────┬──────────┘  └─────────────┬──────────────┘  │
│         │                     │                           │                  │
└─────────┼─────────────────────┼───────────────────────────┼──────────────────┘
          │                     │                           │
          └─────────────────────┼───────────────────────────┘
                                │
┌───────────────────────────────┼───────────────────────────────────────────────┐
│                         DATA LAYER                                            │
│                               │                                               │
│  ┌────────────────────────────┴───────────────────────────────────────────┐  │
│  │                         POSTGRESQL                                      │  │
│  │                    (Supabase Pro / Self-hosted)                         │  │
│  │                                                                         │  │
│  │  Tables: users, tenants, tickets, approvals, agents, analytics          │  │
│  │  Extensions: pgvector, uuid-ossp, pgcrypto, pg_trgm                     │  │
│  │  Features: Row Level Security (RLS), Full-text search                   │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Overview

### Frontend (Next.js)

The frontend is a Next.js 14 application using the App Router architecture with server-side rendering and static generation capabilities.

**Key Responsibilities:**
- User interface for dashboard, tickets, approvals, and settings
- Authentication and session management
- Real-time updates via WebSocket connections
- Responsive design with Tailwind CSS

**Key Technologies:**
- Next.js 14 (App Router)
- React 18
- TypeScript
- Tailwind CSS
- shadcn/ui components
- Zustand for state management
- React Query for data fetching

**Directory Structure:**
```
frontend/
├── src/
│   ├── app/              # App Router pages
│   │   ├── (auth)/       # Auth routes
│   │   ├── dashboard/    # Dashboard pages
│   │   └── api/          # API routes
│   ├── components/       # React components
│   ├── hooks/            # Custom hooks
│   ├── services/         # API services
│   ├── stores/           # Zustand stores
│   └── lib/              # Utilities
├── public/               # Static assets
└── tests/                # Test files
```

### Backend (FastAPI)

The backend is a FastAPI application providing RESTful APIs and WebSocket connections for real-time features.

**Key Responsibilities:**
- REST API for CRUD operations
- WebSocket for Jarvis AI streaming
- Authentication and authorization
- Business logic for tickets, approvals, analytics
- Integration with external services (OpenAI, Paddle, Supabase)

**Key Technologies:**
- FastAPI
- SQLAlchemy 2.0 (async)
- Pydantic v2
- LangChain / LangGraph for AI workflows
- DSPy for AI optimization
- ARQ for background tasks

**Directory Structure:**
```
backend/
├── app/
│   ├── api/              # API routes
│   │   ├── v1/           # API version 1
│   │   └── websocket.py  # WebSocket handlers
│   ├── core/             # Core configuration
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── agents/           # AI agents (Jarvis)
│   └── utils/            # Utilities
├── migrations/           # Alembic migrations
└── tests/                # Test files
```

### Worker (ARQ)

Background worker for async task processing using ARQ (Async Redis Queue).

**Key Responsibilities:**
- Email sending
- Report generation
- Data synchronization
- Scheduled cleanup tasks
- Webhook delivery

**Task Categories:**
- `email_tasks`: Send transactional emails
- `report_tasks`: Generate analytics reports
- `sync_tasks`: Sync with external services
- `cleanup_tasks`: Remove stale data

### MCP Servers

Model Context Protocol servers for specialized AI capabilities.

| Server | Port | Purpose |
|--------|------|---------|
| Knowledge | 8001 | Knowledge base management, document processing |
| Analytics | 8002 | Analytics queries, metric calculations |
| Actions | 8003 | External actions (refunds, escalations) |

### Redis

In-memory data store for caching and message queuing.

**Use Cases:**
- Session storage
- Rate limiting counters
- Job queue (ARQ)
- Pub/Sub for real-time updates
- API response caching

### PostgreSQL

Primary database with Row Level Security for multi-tenant isolation.

**Key Features:**
- Multi-tenant RLS policies
- pgvector for AI embeddings
- Full-text search with pg_trgm
- JSONB for flexible schemas
- Real-time subscriptions via Supabase

---

## Data Flow

### User Authentication Flow

```
1. User submits credentials
   Frontend → Backend /auth/login
   
2. Backend validates credentials
   Backend → PostgreSQL (users table)
   
3. Backend creates session
   Backend → Redis (session store)
   
4. Backend returns tokens
   Backend → Frontend (access + refresh tokens)
   
5. Frontend stores tokens
   Frontend → Zustand store + HttpOnly cookies
```

### Ticket Creation Flow

```
1. User creates ticket via UI
   Frontend → Backend POST /api/v1/tickets
   
2. Backend validates and stores
   Backend → PostgreSQL (tickets table)
   
3. Backend triggers AI classification
   Backend → Worker (ARQ queue)
   
4. Worker calls OpenAI
   Worker → OpenAI API
   
5. Worker updates ticket
   Worker → PostgreSQL (update category/priority)
   
6. Real-time notification
   Backend → WebSocket → Frontend
```

### Approval Workflow Flow

```
1. AI agent detects action needing approval
   Agent → Backend (create approval record)
   
2. Backend notifies admin
   Backend → WebSocket + Email
   
3. Admin reviews and approves/denies
   Frontend → Backend POST /api/v1/approvals/{id}/approve
   
4. Backend executes approved action
   Backend → External API (Paddle for refunds)
   
5. Backend updates records
   Backend → PostgreSQL (approval + audit log)
   
6. Backend notifies stakeholder
   Backend → Email + WebSocket
```

### Jarvis AI Streaming Flow

```
1. User sends command
   Frontend → Backend WebSocket /ws/jarvis
   
2. Backend initializes LangGraph agent
   Backend → LangGraph (agent state)
   
3. Agent processes with streaming
   Agent → OpenAI API (streaming)
   
4. Backend streams chunks
   Backend → WebSocket chunks → Frontend
   
5. Frontend renders response
   Frontend → JarvisTerminal component
   
6. Command logged
   Backend → PostgreSQL (jarvis_history)
```

---

## Integration Points

### External APIs

| Service | Purpose | Auth Method | Rate Limit |
|---------|---------|-------------|------------|
| OpenAI | AI completions, embeddings | API Key | 60 req/min |
| Paddle | Subscription management | API Key | 100 req/min |
| Supabase | Database, auth, storage | Service Key | Unlimited |
| SendGrid | Transactional email | API Key | 600 req/min |
| Stripe | Alternative payments | API Key | 100 req/min |

### Webhooks

**Incoming Webhooks:**
- Paddle webhook: `/webhooks/paddle`
- Stripe webhook: `/webhooks/stripe`
- Slack webhook: `/webhooks/slack`

**Outgoing Webhooks:**
- Ticket events (created, updated, closed)
- Approval events (created, approved, denied)
- System events (alerts, errors)

---

## Technology Stack

### Frontend Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Framework | Next.js | 14.x |
| UI Library | React | 18.x |
| Language | TypeScript | 5.x |
| Styling | Tailwind CSS | 3.x |
| Components | shadcn/ui | latest |
| State | Zustand | 4.x |
| Data Fetching | React Query | 5.x |
| Forms | React Hook Form | 7.x |
| Validation | Zod | 3.x |

### Backend Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Framework | FastAPI | 0.109+ |
| Language | Python | 3.11+ |
| ORM | SQLAlchemy | 2.0+ |
| Validation | Pydantic | 2.x |
| AI/LLM | LangChain | 0.1+ |
| AI Workflows | LangGraph | 0.0.20+ |
| AI Optimization | DSPy | 2.x |
| Task Queue | ARQ | 0.25+ |
| Cache | Redis | 7.x |
| Database | PostgreSQL | 15+ |

### Infrastructure Stack

| Layer | Technology |
|-------|------------|
| Container Runtime | Docker |
| Orchestration | Kubernetes |
| Ingress | NGINX Ingress Controller |
| TLS | cert-manager + Let's Encrypt |
| Secrets | External Secrets Operator |
| Monitoring | Prometheus + Grafana |
| Logging | Loki + Grafana |
| Tracing | Jaeger |

---

## Design Decisions

### Multi-Tenant Architecture

**Decision:** Use PostgreSQL Row Level Security (RLS) for tenant isolation.

**Rationale:**
- Native database-level isolation
- No application code changes for isolation
- Prevents cross-tenant data access even with SQL injection
- Simplifies queries (no manual tenant filtering)

### Human-in-the-Loop for Critical Actions

**Decision:** AI agents never execute financial actions autonomously.

**Rationale:**
- Compliance with financial regulations
- Prevents erroneous refunds
- Maintains human accountability
- Builds user trust

### Streaming Responses for AI

**Decision:** Use WebSocket streaming for Jarvis AI responses.

**Rationale:**
- Better perceived performance
- Allows cancellation mid-stream
- Enables progressive rendering
- Reduces timeout issues for long responses

### Event-Driven Architecture

**Decision:** Use Redis pub/sub for real-time updates.

**Rationale:**
- Decouples services
- Enables horizontal scaling
- Provides reliable delivery
- Supports multiple subscribers

### Microservices vs Monolith

**Decision:** Modular monolith with clear service boundaries.

**Rationale:**
- Simpler deployment initially
- Lower operational overhead
- Easier debugging
- Can extract services later if needed
