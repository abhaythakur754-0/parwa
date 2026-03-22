# PARWA Performance Tuning Guide

## Overview

This guide provides comprehensive performance tuning recommendations for the PARWA platform. Use this as a reference for optimizing system performance, troubleshooting latency issues, and ensuring SLA compliance.

## Table of Contents

1. [Performance SLAs](#performance-slas)
2. [Database Optimization](#database-optimization)
3. [Caching Strategies](#caching-strategies)
4. [Connection Pooling](#connection-pooling)
5. [Known Bottlenecks](#known-bottlenecks)
6. [Monitoring and Profiling](#monitoring-and-profiling)
7. [Quick Reference](#quick-reference)

---

## Performance SLAs

### Target Metrics

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| API P95 Latency | < 300ms | 500ms |
| API P99 Latency | < 500ms | 1000ms |
| Database Query Avg | < 50ms | 100ms |
| Database Query P95 | < 100ms | 200ms |
| Cache Hit Rate | > 85% | 70% |
| Error Rate | < 0.1% | 1% |
| Throughput | > 200 RPS | 100 RPS |

### Client-Specific SLAs

| Client Tier | Concurrent Users | P95 Latency |
|-------------|------------------|-------------|
| Mini | 10 | < 500ms |
| Junior | 50 | < 500ms |
| Senior | 100 | < 500ms |

---

## Database Optimization

### Index Recommendations

#### Critical Indexes (Always Create)

```sql
-- Client isolation
CREATE INDEX CONCURRENTLY idx_tickets_client_id ON tickets(client_id);
CREATE INDEX CONCURRENTLY idx_approvals_client_id ON approvals(client_id);
CREATE INDEX CONCURRENTLY idx_analytics_client_id ON analytics(client_id);

-- Status filtering
CREATE INDEX CONCURRENTLY idx_tickets_status ON tickets(status);
CREATE INDEX CONCURRENTLY idx_approvals_status ON approvals(status);

-- Time-based queries
CREATE INDEX CONCURRENTLY idx_tickets_created_at ON tickets(created_at);
CREATE INDEX CONCURRENTLY idx_analytics_created_at ON analytics(created_at);

-- User lookups
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
CREATE INDEX CONCURRENTLY idx_users_tenant_id ON users(tenant_id);

-- Audit trail
CREATE INDEX CONCURRENTLY idx_audit_logs_tenant_id ON audit_logs(tenant_id);
CREATE INDEX CONCURRENTLY idx_audit_logs_timestamp ON audit_logs(timestamp);
```

#### Composite Indexes for Common Queries

```sql
-- Ticket listing by client and status
CREATE INDEX CONCURRENTLY idx_tickets_client_status 
ON tickets(client_id, status) 
INCLUDE (subject, priority, created_at);

-- Approval queue queries
CREATE INDEX CONCURRENTLY idx_approvals_client_status_created 
ON approvals(client_id, status, created_at DESC);

-- Analytics date range queries
CREATE INDEX CONCURRENTLY idx_analytics_client_date 
ON analytics(client_id, created_at DESC);
```

#### Partial Indexes for Performance

```sql
-- Only index active tickets
CREATE INDEX CONCURRENTLY idx_tickets_active 
ON tickets(client_id, updated_at) 
WHERE status NOT IN ('closed', 'resolved');

-- Only pending approvals
CREATE INDEX CONCURRENTLY idx_approvals_pending 
ON approvals(client_id, created_at) 
WHERE status = 'pending';
```

### Query Optimization Patterns

#### Avoid N+1 Queries

```python
# ❌ Bad: N+1 query pattern
for ticket in tickets:
    customer = db.query(Customer).get(ticket.customer_id)  # N queries
    
# ✅ Good: Eager loading
tickets = db.query(Ticket).options(joinedload(Ticket.customer)).all()
```

#### Use Batch Operations

```python
# ❌ Bad: Individual inserts
for item in items:
    db.add(item)
    db.commit()  # N commits

# ✅ Good: Batch insert
db.bulk_insert_mappings(Item, items)
db.commit()  # Single commit
```

#### Optimize Pagination

```python
# ❌ Bad: OFFSET with large pages
SELECT * FROM tickets ORDER BY id LIMIT 20 OFFSET 10000;

# ✅ Good: Cursor-based pagination
SELECT * FROM tickets WHERE id > last_seen_id ORDER BY id LIMIT 20;
```

### Query Plan Analysis

```sql
-- Enable query timing
EXPLAIN ANALYZE SELECT * FROM tickets WHERE client_id = 'client_001' AND status = 'open';

-- Check for sequential scans
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public'
ORDER BY tablename;

-- Find missing indexes
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    CASE 
        WHEN n_distinct > 100 THEN 'index_recommended'
        ELSE 'ok'
    END as recommendation
FROM pg_stats
WHERE schemaname = 'public'
AND n_distinct > 100;
```

### Database Configuration

```sql
-- Connection pooling (pgbouncer)
max_connections = 200
default_pool_size = 50
min_pool_size = 10
reserve_pool_size = 5

-- Memory settings
shared_buffers = 256MB
work_mem = 16MB
maintenance_work_mem = 128MB
effective_cache_size = 1GB

-- Query planning
random_page_cost = 1.1  -- For SSD
effective_io_concurrency = 200

-- WAL settings
wal_buffers = 64MB
checkpoint_completion_target = 0.9
```

---

## Caching Strategies

### Redis Configuration

```redis
# Memory management
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence (optional for cache)
save ""  # Disable RDB for pure cache
appendonly no

# Performance
tcp-keepalive 300
timeout 0
tcp-backlog 511
```

### Caching Patterns

#### 1. Cache-Aside Pattern

```python
def get_tickets(client_id: str):
    cache_key = f"tickets:{client_id}"
    
    # Try cache first
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Cache miss - query database
    tickets = db.query(Ticket).filter_by(client_id=client_id).all()
    
    # Store in cache
    redis.setex(cache_key, 300, json.dumps(tickets))  # 5 min TTL
    return tickets
```

#### 2. Write-Through Pattern

```python
def update_ticket(ticket_id: str, data: dict):
    # Update database
    ticket = db.query(Ticket).get(ticket_id)
    ticket.update(data)
    db.commit()
    
    # Update cache
    cache_key = f"ticket:{ticket_id}"
    redis.setex(cache_key, 300, json.dumps(ticket.to_dict()))
```

#### 3. Cache Invalidation

```python
def invalidate_client_cache(client_id: str):
    """Invalidate all cache entries for a client."""
    pattern = f"*:{client_id}*"
    keys = redis.keys(pattern)
    if keys:
        redis.delete(*keys)
```

### Cache Key Design

```python
# Good cache key design
f"tickets:{client_id}:page:{page}:status:{status}"
f"approval:{approval_id}"
f"analytics:{client_id}:{date}:metrics"

# Use consistent prefixes for easy invalidation
f"parwa:{client_id}:tickets:list"
f"parwa:{client_id}:user:{user_id}"
```

### Cache Warming

```python
async def warm_client_cache(client_id: str):
    """Pre-populate cache on client onboarding."""
    # Warm tickets
    tickets = await get_tickets(client_id)
    redis.setex(f"tickets:{client_id}", 300, json.dumps(tickets))
    
    # Warm knowledge base
    kb = await load_knowledge_base(client_id)
    redis.setex(f"kb:{client_id}", 3600, json.dumps(kb))
    
    # Warm analytics
    analytics = await get_analytics_summary(client_id)
    redis.setex(f"analytics:{client_id}", 300, json.dumps(analytics))
```

---

## Connection Pooling

### Database Connection Pool (PgBouncer)

```ini
[databases]
parwa = host=postgres port=5432 dbname=parwa

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/users.txt
pool_mode = transaction
max_client_conn = 500
default_pool_size = 50
min_pool_size = 10
reserve_pool_size = 5
reserve_pool_timeout = 3
max_db_connections = 200
```

### Application Connection Pool

```python
# SQLAlchemy configuration
SQLALCHEMY_POOL_SIZE = 20
SQLALCHEMY_MAX_OVERFLOW = 10
SQLALCHEMY_POOL_TIMEOUT = 30
SQLALCHEMY_POOL_RECYCLE = 3600
SQLALCHEMY_POOL_PRE_PING = True

# Connection string
DATABASE_URL = "postgresql://user:pass@pgbouncer:6432/parwa"
```

### Redis Connection Pool

```python
import redis
from redis.connection import ConnectionPool

pool = ConnectionPool(
    host='redis',
    port=6379,
    max_connections=50,
    socket_timeout=5,
    socket_connect_timeout=5,
    retry_on_timeout=True
)

redis_client = redis.Redis(connection_pool=pool)
```

### HTTP Connection Pool

```python
import httpx

# Async client with connection pooling
async_client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
        keepalive_expiry=30.0
    ),
    timeout=httpx.Timeout(10.0, connect=5.0)
)
```

---

## Known Bottlenecks

### 1. N+1 Queries in Ticket List

**Location:** `backend/app/services/ticket_service.py`

**Symptom:** Slow ticket listing with many tickets per page

**Solution:**
```python
# Use joinedload for relations
tickets = db.query(Ticket).options(
    joinedload(Ticket.customer),
    joinedload(Ticket.assignee)
).filter_by(client_id=client_id).all()
```

### 2. Missing Index on Analytics Table

**Location:** `analytics` table

**Symptom:** Slow analytics dashboard loading

**Solution:**
```sql
CREATE INDEX CONCURRENTLY idx_analytics_client_created 
ON analytics(client_id, created_at DESC);
```

### 3. Redis Memory Fragmentation

**Location:** Redis cache

**Symptom:** Higher memory usage than expected

**Solution:**
```redis
# Enable memory fragmentation info
CONFIG SET activedefrag yes
CONFIG SET active-defrag-cycle-min 1
CONFIG SET active-defrag-cycle-max 25
```

### 4. Large JSON Payloads

**Location:** Jarvis command responses

**Symptom:** Slow response times for complex queries

**Solution:**
```python
# Paginate large responses
def get_jarvis_response(command: str):
    response = jarvis.process(command)
    if len(response) > 10000:
        return {
            "summary": response[:500],
            "full_response": response,
            "truncated": True
        }
    return response
```

### 5. Connection Leaks

**Location:** Background workers

**Symptom:** Database connection pool exhaustion

**Solution:**
```python
# Always use context managers
def process_task():
    with SessionLocal() as db:
        # Work here
        pass
    # Connection automatically closed
```

---

## Monitoring and Profiling

### Performance Metrics to Monitor

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `http_request_duration_seconds` | API latency histogram | P95 > 500ms |
| `pg_stat_activity_count` | DB connections | > 150 |
| `redis_memory_used_bytes` | Cache memory | > 85% max |
| `redis_keyspace_hits/misses` | Cache hit rate | < 70% |
| `container_cpu_usage_seconds` | CPU usage | > 90% |
| `container_memory_usage_bytes` | Memory usage | > 85% |

### Profiling Tools

#### Python Profiling

```python
import cProfile
import pstats

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Function to profile
    result = expensive_operation()
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)
    
    return result
```

#### Database Query Logging

```python
# Enable SQLAlchemy query logging
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

#### APM Integration

```python
# OpenTelemetry tracing
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

tracer = trace.get_tracer(__name__)

async def process_request(request):
    with tracer.start_as_current_span("process_request"):
        # Traced code
        result = await handle_request(request)
        return result
```

### Performance Debugging Checklist

1. [ ] Check slow query log
2. [ ] Verify indexes are being used (EXPLAIN ANALYZE)
3. [ ] Check cache hit rate
4. [ ] Review connection pool stats
5. [ ] Profile application code
6. [ ] Check for memory leaks
7. [ ] Verify network latency
8. [ ] Review background job queue depth

---

## Quick Reference

### Performance Commands

```bash
# Check database query times
psql -c "SELECT query, calls, total_time/calls as avg_time 
         FROM pg_stat_statements ORDER BY avg_time DESC LIMIT 10;"

# Check connection count
psql -c "SELECT count(*) FROM pg_stat_activity;"

# Check index usage
psql -c "SELECT schemaname, tablename, indexname, idx_scan 
         FROM pg_stat_user_indexes ORDER BY idx_scan ASC;"

# Redis memory usage
redis-cli info memory

# Redis slow log
redis-cli slowlog get 10

# Check pod resource usage
kubectl top pods -n parwa

# Check HPA status
kubectl get hpa -n parwa
```

### Emergency Performance Fixes

```bash
# Clear Redis cache if corrupted
redis-cli FLUSHALL

# Restart slow workers
kubectl rollout restart deployment/parwa-worker -n parwa

# Scale backend if overloaded
kubectl scale deployment/parwa-backend --replicas=10 -n parwa

# Kill long-running queries
psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
         WHERE state = 'active' AND query_start < now() - interval '5 minutes';"
```

### Configuration Files

| File | Location | Purpose |
|------|----------|---------|
| PostgreSQL | `/etc/postgresql/postgresql.conf` | DB settings |
| Redis | `/etc/redis/redis.conf` | Cache settings |
| PgBouncer | `/etc/pgbouncer/pgbouncer.ini` | Connection pool |
| Nginx | `/etc/nginx/nginx.conf` | Web server tuning |

---

## Support

For performance support, contact:
- **Slack**: #parwa-performance
- **Email**: performance@parwa.ai
- **Runbooks**: https://docs.parwa.ai/runbooks
