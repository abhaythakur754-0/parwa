# PARWA Troubleshooting Guide

## Common Issues and Solutions

### 1. API Errors

#### 401 Unauthorized
**Symptoms**: API requests fail with 401 status code

**Causes**:
- Expired JWT token
- Invalid API key
- Missing Authorization header

**Solutions**:
```bash
# Refresh token
curl -X POST https://api.parwa.ai/auth/refresh \
  -H "Authorization: Bearer <refresh_token>"

# Verify API key
curl https://api.parwa.ai/auth/verify \
  -H "X-API-Key: <your-api-key>"
```

#### 429 Rate Limited
**Symptoms**: Requests fail with 429 status code

**Causes**:
- Exceeded rate limit for tier

**Solutions**:
- Implement exponential backoff
- Upgrade subscription tier
- Request temporary limit increase

### 2. Database Issues

#### Connection Pool Exhausted
**Symptoms**: "Connection pool exhausted" errors

**Diagnosis**:
```bash
# Check PgBouncer stats
kubectl exec -it pgbouncer-0 -- psql -c "SHOW POOLS;"
```

**Solutions**:
1. Increase pool size:
```yaml
DEFAULT_POOL_SIZE: "50"
MAX_CLIENT_CONN: "2000"
```

2. Check for connection leaks:
```python
# Ensure connections are closed
async with get_session() as session:
    # Your code here
    pass  # Auto-closes
```

#### Slow Queries
**Symptoms**: High database CPU, slow API responses

**Diagnosis**:
```sql
-- Find slow queries
SELECT query, mean_exec_time, calls 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;
```

**Solutions**:
- Add missing indexes
- Optimize query with EXPLAIN ANALYZE
- Consider denormalization

### 3. Redis Issues

#### High Memory Usage
**Symptoms**: Redis OOM errors

**Diagnosis**:
```bash
redis-cli INFO memory
```

**Solutions**:
```bash
# Clear expired keys
redis-cli --scan --pattern "*expired*" | xargs redis-cli DEL

# Set memory limit
redis-cli CONFIG SET maxmemory 4gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

#### Connection Timeouts
**Symptoms**: "Redis connection timeout" errors

**Solutions**:
1. Check network connectivity
2. Increase timeout:
```python
Redis(timeout=5, socket_timeout=5)
```

### 4. Agent Issues

#### Low Accuracy
**Symptoms**: Agent responses are incorrect

**Diagnosis**:
```bash
# Check accuracy metrics
curl https://api.parwa.ai/analytics/accuracy?client_id=xxx
```

**Solutions**:
- Update knowledge base
- Retrain Agent Lightning
- Add more training examples

#### Slow Response Time
**Symptoms**: P95 latency > 300ms

**Diagnosis**:
```bash
# Check latency breakdown
curl https://api.parwa.ai/analytics/latency
```

**Solutions**:
- Check database query performance
- Verify cache hit rate
- Scale backend pods

### 5. Frontend Issues

#### Build Failures
**Symptoms**: `npm run build` fails

**Common Causes**:
- Missing dependencies
- TypeScript errors
- Environment variable issues

**Solutions**:
```bash
# Clear cache
rm -rf .next node_modules
npm install
npm run build
```

#### Hydration Errors
**Symptoms**: React hydration mismatch warnings

**Solutions**:
```tsx
// Use client-only rendering
'use client';

// Or suppress hydration
<div suppressHydrationWarning>
  {content}
</div>
```

### 6. Kubernetes Issues

#### Pod CrashLoopBackOff
**Symptoms**: Pods continuously restart

**Diagnosis**:
```bash
kubectl logs <pod-name> --previous
kubectl describe pod <pod-name>
```

**Solutions**:
- Check resource limits
- Verify environment variables
- Check health check configuration

#### High CPU Usage
**Symptoms**: Nodes at high CPU

**Diagnosis**:
```bash
kubectl top pods
kubectl top nodes
```

**Solutions**:
- Scale horizontally with HPA
- Optimize code
- Increase node size

### 7. Multi-Tenant Issues

#### Cross-Tenant Data Access
**Symptoms**: Client sees another client's data

**IMPORTANT**: This should never happen. If it does:
1. Immediately disable the affected endpoints
2. Check RLS policies
3. Review recent schema changes
4. Contact security team

**Verification**:
```sql
-- Check RLS is enabled
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public';

-- Test isolation
SET app.current_client = 'client_001';
SELECT * FROM tickets;  -- Should only return client_001's data
```

## Logging and Debugging

### Enable Debug Logging
```python
import logging
logging.getLogger("parwa").setLevel(logging.DEBUG)
```

### View Logs
```bash
# Kubernetes
kubectl logs -f deployment/parwa-backend -n parwa

# Docker Compose
docker-compose logs -f backend
```

### Structured Logging
```json
{
  "timestamp": "2026-03-28T00:00:00Z",
  "level": "INFO",
  "client_id": "client_001",
  "request_id": "uuid",
  "message": "Request processed",
  "duration_ms": 245
}
```

## Getting Help

1. **Documentation**: https://docs.parwa.ai
2. **Status Page**: https://status.parwa.ai
3. **Support**: support@parwa.ai
4. **Emergency**: +1-XXX-XXX-XXXX
