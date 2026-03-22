# PARWA Performance Tuning Guide

## Overview

This guide provides comprehensive performance tuning recommendations for PARWA production deployments. Follow these guidelines to optimize system performance and meet SLA requirements.

## Table of Contents

1. [Performance Targets](#performance-targets)
2. [Database Optimization](#database-optimization)
3. [Caching Strategies](#caching-strategies)
4. [Connection Pooling](#connection-pooling)
5. [Known Bottlenecks](#known-bottlenecks)
6. [Monitoring & Profiling](#monitoring--profiling)

---

## Performance Targets

### SLA Requirements

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| P95 Latency | < 500ms | > 500ms triggers alert |
| P99 Latency | < 1000ms | > 1000ms triggers alert |
| Error Rate | < 0.1% | > 1% triggers alert |
| Availability | 99.9% | < 99.9% SLO breach |
| Throughput | 1000 req/s | Per tenant |

### Key Performance Indicators

```
# Monitor these metrics
- http_request_duration_seconds (histogram)
- http_requests_total (counter)
- db_query_duration_seconds (histogram)
- cache_hit_rate (gauge)
- active_connections (gauge)
```

---

## Database Optimization

### Index Strategy

**Essential Indexes:**

```sql
-- Tickets table
CREATE INDEX idx_tickets_tenant_status ON tickets(tenant_id, status);
CREATE INDEX idx_tickets_tenant_created ON tickets(tenant_id, created_at DESC);
CREATE INDEX idx_tickets_customer ON tickets(customer_id);
CREATE INDEX idx_tickets_priority ON tickets(priority) WHERE status = 'open';

-- Customers table
CREATE INDEX idx_customers_tenant_email ON customers(tenant_id, email);
CREATE INDEX idx_customers_tenant_id ON customers(tenant_id);

-- Approvals table
CREATE INDEX idx_approvals_tenant_status ON approvals(tenant_id, status);
CREATE INDEX idx_approvals_created ON approvals(created_at DESC);

-- Audit logs (time-series)
CREATE INDEX idx_audit_logs_tenant_time ON audit_logs(tenant_id, timestamp DESC);
```

**Partial Indexes for Common Queries:**

```sql
-- Open tickets only (most common query)
CREATE INDEX idx_tickets_open ON tickets(tenant_id, created_at DESC)
WHERE status IN ('open', 'pending');

-- High priority tickets
CREATE INDEX idx_tickets_high_priority ON tickets(tenant_id, priority)
WHERE priority IN ('high', 'urgent') AND status = 'open';
```

### Query Optimization

**Avoid N+1 Queries:**

```python
# Bad: N+1 query pattern
for ticket in tickets:
    customer = await db.get_customer(ticket.customer_id)

# Good: Eager loading
tickets = await db.query(
    "SELECT t.*, c.* FROM tickets t "
    "LEFT JOIN customers c ON t.customer_id = c.id "
    "WHERE t.tenant_id = $1",
    tenant_id
)
```

**Use Query Batching:**

```python
# Bad: Multiple round trips
for id in ticket_ids:
    ticket = await db.get_ticket(id)

# Good: Batch query
tickets = await db.query(
    "SELECT * FROM tickets WHERE id = ANY($1)",
    ticket_ids
)
```

### Connection Settings

```sql
-- PostgreSQL configuration
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB
maintenance_work_mem = 128MB
random_page_cost = 1.1  -- For SSDs
effective_io_concurrency = 200
```

### RLS Performance

Row Level Security can impact query performance. Optimize with:

```sql
-- Create efficient RLS policies
CREATE POLICY tenant_isolation ON tickets
    USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Add index on RLS column
CREATE INDEX idx_tickets_rls ON tickets(tenant_id);

-- Use SECURITY DEFINER for complex policies
CREATE FUNCTION current_tenant() RETURNS uuid AS $$
    SELECT current_setting('app.tenant_id', true)::uuid;
$$ LANGUAGE sql SECURITY DEFINER;
```

---

## Caching Strategies

### Redis Cache Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CACHE LAYERS                             │
│                                                              │
│  L1: In-Memory (per process)                                │
│  ├── Session data (5 min TTL)                               │
│  └── User preferences (1 hour TTL)                          │
│                                                              │
│  L2: Redis (shared)                                          │
│  ├── FAQ lookups (1 hour TTL)                               │
│  ├── Customer profiles (30 min TTL)                         │
│  ├── Product catalog (2 hour TTL)                           │
│  └── API responses (5 min TTL)                              │
│                                                              │
│  L3: CDN (static assets)                                     │
│  └── Static files, images (24 hour TTL)                     │
└─────────────────────────────────────────────────────────────┘
```

### Cache Key Strategy

```python
# Namespace keys by tenant
cache_key = f"tenant:{tenant_id}:faq:{faq_id}"

# Version keys for easy invalidation
cache_key = f"tenant:{tenant_id}:products:v2:{product_id}"

# Pattern for bulk invalidation
# Delete: tenant:client_001:products:*
```

### Cache Warming

```python
async def warm_cache():
    """Pre-populate cache on startup."""
    # Top FAQs
    faqs = await get_top_faqs(limit=100)
    for faq in faqs:
        await cache.set(f"faq:{faq.id}", faq, ttl=3600)
    
    # Active customers
    customers = await get_active_customers(limit=1000)
    for customer in customers:
        await cache.set(f"customer:{customer.id}", customer, ttl=1800)
```

### Cache Hit Rate Optimization

```python
# Target: > 85% cache hit rate

# Monitor hit rate
hit_rate = cache.hits / (cache.hits + cache.misses)

# Alert if below threshold
if hit_rate < 0.85:
    alert("Cache hit rate below 85%")
```

---

## Connection Pooling

### Pool Sizing Formula

```
connections = (core_count * 2) + effective_spindle_count

For a 4-core server with SSD:
connections = (4 * 2) + 1 = 9 connections per service instance

With 10 backend replicas:
total = 9 * 10 = 90 connections (well under 200 limit)
```

### Pool Configuration

```python
# SQLAlchemy async pool
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,           # Normal pool size
    max_overflow=20,        # Additional connections under load
    pool_timeout=30,        # Wait time for connection
    pool_recycle=1800,      # Recycle connections after 30 min
    pool_pre_ping=True,     # Validate connections before use
    echo_pool=False,        # Don't log pool events in production
)
```

### Redis Connection Pool

```python
# Redis connection pool
import redis.asyncio as redis

redis_pool = redis.ConnectionPool(
    host='redis',
    port=6379,
    db=0,
    max_connections=50,
    socket_timeout=5,
    socket_connect_timeout=5,
    retry_on_timeout=True,
)

redis_client = redis.Redis(connection_pool=redis_pool)
```

---

## Known Bottlenecks

### 1. Full-Text Search Without Index

**Problem:** LIKE queries with leading wildcards don't use indexes.

```sql
-- Bad: Can't use index
WHERE subject LIKE '%refund%'

-- Good: Uses trigram index
CREATE EXTENSION pg_trgm;
CREATE INDEX idx_tickets_subject_trgm ON tickets USING gin(subject gin_trgm_ops);
WHERE subject ILIKE '%refund%'
```

### 2. JSONB Column Queries

**Problem:** JSONB queries without GIN index are slow.

```sql
-- Add GIN index for JSONB
CREATE INDEX idx_tickets_metadata ON tickets USING gin(metadata);

-- Or specific path index
CREATE INDEX idx_tickets_priority ON tickets((metadata->>'priority'));
```

### 3. Large Result Sets

**Problem:** Returning too many rows causes memory issues.

**Solution:** Always paginate large queries.

```python
# Use cursor-based pagination for large datasets
async def get_tickets_cursor(cursor: UUID = None, limit: int = 100):
    query = "SELECT * FROM tickets WHERE tenant_id = $1"
    params = [tenant_id]
    
    if cursor:
        query += " AND id < $2"
        params.append(cursor)
    
    query += " ORDER BY id DESC LIMIT $2"
    params.append(limit)
    
    return await db.query(query, params)
```

### 4. Synchronous External API Calls

**Problem:** Blocking on external APIs slows down the entire system.

**Solution:** Use async clients and timeouts.

```python
import httpx

async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get("https://api.openai.com/v1/...")
```

### 5. WebSocket Connection Memory

**Problem:** Each WebSocket connection consumes memory.

**Solution:** Implement connection limits and cleanup.

```python
# Limit connections per tenant
MAX_WS_CONNECTIONS_PER_TENANT = 100

# Implement heartbeat and cleanup
async def cleanup_inactive_connections():
    while True:
        await asyncio.sleep(60)
        for conn in websocket_connections:
            if conn.last_ping < time.time() - 300:
                await conn.close()
```

---

## Monitoring & Profiling

### Key Metrics to Monitor

```yaml
# Prometheus queries for dashboard

# P95 latency
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# Error rate
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# Database connections
pg_stat_activity_count

# Cache hit rate
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))

# Queue depth
redis_llen{queue="arq:queue"}
```

### Performance Profiling

```python
# Enable query logging for slow queries
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# Profile specific endpoints
from time import perf_counter

@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - start) * 1000
    response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
    return response
```

### Load Testing

```bash
# Using Locust for load testing
locust -f tests/performance/test_real_client_load.py \
    --host https://api.parwa.ai \
    --users 100 \
    --spawn-rate 10 \
    --run-time 5m \
    --headless
```

### Performance Test Checklist

- [ ] P95 latency < 500ms under normal load
- [ ] P95 latency < 500ms with 100 concurrent users
- [ ] Database queries use appropriate indexes
- [ ] Cache hit rate > 85%
- [ ] No memory leaks under sustained load
- [ ] Connection pool not exhausted under peak load
- [ ] External API timeouts handled gracefully
- [ ] WebSocket connections cleaned up properly

---

## Quick Reference

### Emergency Performance Tuning

```sql
-- Kill long-running queries
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'active'
AND query_start < now() - interval '5 minutes';

-- Check for table bloat
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;

-- Analyze tables for query planner
ANALYZE tickets;
ANALYZE customers;
ANALYZE approvals;
```

### Redis Performance Check

```bash
# Check Redis memory usage
redis-cli info memory | grep used_memory_human

# Monitor Redis commands
redis-cli monitor

# Check slow log
redis-cli slowlog get 10
```

For additional support, contact the Platform team at platform@parwa.ai.
