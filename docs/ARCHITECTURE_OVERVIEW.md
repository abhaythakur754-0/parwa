# PARWA Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           LOAD BALANCER (AWS ALB)                        │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
            ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
            │   Frontend   │  │   Frontend   │  │   Frontend   │
            │   (Next.js)  │  │   (Next.js)  │  │   (Next.js)  │
            │   Pod 1      │  │   Pod 2      │  │   Pod 3      │
            └──────────────┘  └──────────────┘  └──────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           API GATEWAY (Kong)                             │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
            ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
            │   Backend    │  │   Backend    │  │   Backend    │
            │   (FastAPI)  │  │   (FastAPI)  │  │   (FastAPI)  │
            │   Pod 1      │  │   Pod 2      │  │   Pod 3      │
            └──────────────┘  └──────────────┘  └──────────────┘
                    │                 │                 │
                    └─────────────────┼─────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         PgBouncer (Connection Pool)                      │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL (Multi-Region Cluster)                     │
│              ┌──────────┐  ┌──────────┐  ┌──────────┐                    │
│              │   EU     │  │   US     │  │   APAC   │                    │
│              │ Primary  │  │ Primary  │  │ Primary  │                    │
│              └──────────┘  └──────────┘  └──────────┘                    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Frontend (Next.js 16)
- **Framework**: Next.js 16 with App Router
- **Styling**: Tailwind CSS 4 + shadcn/ui
- **State Management**: Zustand
- **Data Fetching**: React Query (TanStack Query)
- **PWA Support**: Service Worker, Offline Support

### 2. Backend (FastAPI)
- **Framework**: FastAPI with async/await
- **ORM**: SQLAlchemy 2.0 with async support
- **Validation**: Pydantic v2
- **Authentication**: JWT + SAML SSO

### 3. AI Engine
- **Framework**: LangGraph + LangChain
- **Model**: DSPy for prompt optimization
- **Agents**: Multi-agent system with specialized roles
- **Training**: Agent Lightning continuous learning

### 4. Database
- **Primary**: PostgreSQL 15+ with RLS
- **Cache**: Redis 7+ for sessions and caching
- **Search**: Vector embeddings for knowledge base

### 5. Message Queue
- **Primary**: Redis Streams
- **Workers**: Celery for background tasks

## Multi-Tenancy

PARWA uses Row-Level Security (RLS) for multi-tenant isolation:

```sql
-- RLS Policy Example
CREATE POLICY client_isolation ON tickets
  USING (client_id = current_setting('app.current_client')::uuid);
```

### Tenant Context Flow
1. Request → API Gateway extracts client from JWT
2. Backend sets `app.current_client` session variable
3. PostgreSQL RLS automatically filters queries
4. Zero cross-tenant data access possible

## Agent System

### Variants

| Feature | Mini | PARWA Junior | PARWA High |
|---------|------|--------------|------------|
| Concurrent Calls | 2 | 5 | 10 |
| Refund Limit | $50 | $200 | $2000 |
| Escalation Threshold | 70% | 50% | 30% |
| Video Support | ❌ | ❌ | ✅ |
| Analytics | ❌ | ❌ | ✅ |

### Agent Roles
1. **FAQ Agent** - Handles common questions
2. **Email Agent** - Processes email tickets
3. **Chat Agent** - Real-time chat support
4. **Voice Agent** - Phone call handling
5. **Refund Agent** - Processes refund requests
6. **Escalation Agent** - Routes to human agents

## Security Architecture

### Authentication Flow
```
User → SSO Provider (SAML) → PARWA Backend → JWT Token
```

### Data Protection
- **At Rest**: AES-256 encryption
- **In Transit**: TLS 1.3
- **PII**: Anonymized for analytics

### Compliance
- HIPAA (Healthcare)
- PCI DSS (Financial)
- GDPR (EU)
- CCPA (California)

## Performance Targets

| Metric | Target |
|--------|--------|
| P95 Latency | < 300ms |
| Throughput | 2000 req/sec |
| Availability | 99.9% |
| Error Rate | < 0.1% |

## Monitoring Stack

- **Metrics**: Prometheus + Grafana
- **Logs**: ELK Stack
- **Tracing**: OpenTelemetry + Jaeger
- **Alerting**: PagerDuty
