# Multi-Tenant Architecture Documentation

> **PARWA - AI Customer Support Automation Platform**
> Version: Phase 5 - Multi-Tenant Architecture
> Last Updated: 2026-03-23

## Overview

PARWA is designed as a multi-tenant SaaS platform where multiple clients share the same infrastructure while maintaining complete data isolation.

## Architecture Principles

### 1. Shared Infrastructure, Isolated Data

- **Single Database**: All clients share the same PostgreSQL database
- **Row-Level Security (RLS)**: Database-level isolation using PostgreSQL RLS policies
- **Application-Level Isolation**: API and service layer enforce tenant boundaries
- **Complete Transparency**: Clients are unaware of other tenants

### 2. Tenant Identification

Every tenant is identified by:
- **Client ID**: Unique identifier (e.g., `client_001`, `client_002`)
- **Tenant ID**: Internal database identifier linked to client
- **API Key**: Authentication credential scoped to single tenant

### 3. Zero Trust Model

- All requests must include tenant context
- No implicit access based on session alone
- Every data access is validated against tenant ownership

## Data Isolation Strategy

### Database Layer - Row-Level Security (RLS)

```sql
-- Enable RLS on all tenant-scoped tables
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_base ENABLE ROW LEVEL SECURITY;

-- Create policies for tenant isolation
CREATE POLICY tenant_isolation ON tickets
    USING (client_id = current_setting('app.current_client_id'));
```

### Application Layer - API Middleware

```python
class TenantMiddleware:
    async def __call__(self, request, call_next):
        client_id = self._extract_client_id(request)
        request.state.client_id = client_id
        await db.execute(f"SET app.current_client_id = '{client_id}'")
        return await call_next(request)
```

## Tenant-Specific Configurations

### Client Configuration Structure

```
clients/
├── client_001/
│   ├── config.py           # Client-specific settings
│   └── knowledge_base/
│       ├── faq.json        # FAQ entries
│       ├── products.json   # Product catalog
│       └── policies.json   # Policies
├── client_002/
│   ├── config.py
│   └── knowledge_base/
│       └── ...
```

### Variant-Specific Features

| Feature | Mini PARWA | PARWA Junior | PARWA High |
|---------|------------|--------------|------------|
| Tickets/month | 500 | 2,000 | Unlimited |
| AI Accuracy Target | 70% | 72% | 75% |
| Knowledge Base | 50 entries | 200 entries | Unlimited |
| Integrations | Email | Email + Slack | All |

## API Isolation

### Request Flow

```
Client Request → API Gateway → Authentication → Tenant Context → RLS Enforcement → Service Layer
```

### API Endpoint Design

All API endpoints are tenant-scoped:

```
GET  /api/v1/tickets          # Returns only client's tickets
POST /api/v1/tickets          # Creates ticket for client
GET  /api/v1/knowledge-base   # Returns client's KB only
```

## Knowledge Base Isolation

- **Database**: Core entries in `knowledge_base` table with RLS
- **Files**: JSON files in client directory
- **Cache**: Redis with client-prefixed keys

## Dashboard Isolation

Each client's dashboard displays only their data:

```json
{
  "dashboard": "client_001_dashboard",
  "client_id": "client_001",
  "widgets": [
    {"type": "ticket_volume", "data_source": "client_001.tickets"}
  ]
}
```

## Security Considerations

### Authentication

- API keys are scoped to single tenant
- JWT tokens include client_id claim
- Session cookies include tenant binding

### Audit Logging

All cross-tenant access attempts are logged:

```python
async def log_access(client_id: str, resource: str, action: str):
    await db.execute("INSERT INTO audit_log ...")
```

### PII Handling

- PII is encrypted at rest
- PII is redacted in logs
- Cross-tenant PII access triggers alerts

## Performance Isolation

### Resource Limits

Each tenant has defined resource limits:

```python
@dataclass
class ResourceLimits:
    max_tickets_per_month: int
    max_api_requests_per_minute: int
    max_storage_mb: int
```

### Rate Limiting

Per-client rate limiting prevents noisy neighbor issues:

```python
async def check_limit(client_id: str) -> bool:
    key = f"rate:{client_id}"
    current = await redis.incr(key)
    return current <= limit
```

## Testing Strategy

### Isolation Tests

1. **Cross-Tenant Data Access**: 20+ tests verifying clients cannot access each other's data
2. **API Isolation**: 10+ tests for API endpoint isolation
3. **Database RLS**: 10+ tests for RLS policy enforcement
4. **Concurrent Operations**: Tests under parallel load

## Compliance

### GDPR

- Data isolation enables GDPR compliance
- Right to erasure scoped to tenant
- Data portability per client

### HIPAA

- PHI isolation per healthcare client
- Audit logging for access
- Encryption at rest and in transit

## Best Practices

### For Developers

1. Always validate client_id in service methods
2. Never bypass RLS with superuser queries
3. Use tenant-prefixed cache keys
4. Log all cross-tenant access attempts

### For Operations

1. Monitor tenant resource usage
2. Alert on isolation violations
3. Regular security audits
4. Backup per-tenant for data recovery

---

*This document is maintained by the PARWA architecture team.*
