# PARWA Troubleshooting Guide

## Overview

This document provides solutions for common issues encountered when operating PARWA. Use this guide to diagnose and resolve problems quickly.

## Table of Contents

1. [Common Issues](#common-issues)
2. [Diagnostic Commands](#diagnostic-commands)
3. [Log Locations](#log-locations)
4. [Performance Debugging](#performance-debugging)
5. [Known Limitations](#known-limitations)
6. [FAQ](#faq)

---

## Common Issues

### Application Won't Start

**Symptoms:**
- Pods stuck in `Pending` or `CrashLoopBackOff` state
- No logs appearing
- Health checks failing

**Diagnosis:**

```bash
# Check pod status
kubectl get pods -n parwa

# Describe pod for events
kubectl describe pod <pod-name> -n parwa

# Check logs
kubectl logs <pod-name> -n parwa --previous

# Check resource constraints
kubectl describe resourcequota -n parwa
```

**Common Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Missing secrets | Verify secrets exist: `kubectl get secrets -n parwa` |
| Resource limits | Increase limits in deployment or quota |
| Image pull error | Verify image exists and credentials are correct |
| ConfigMap missing | Apply ConfigMap: `kubectl apply -f infra/k8s/configmap.yaml` |

### Database Connection Errors

**Symptoms:**
- "Connection refused" errors
- Timeout errors
- "Too many connections" errors

**Diagnosis:**

```bash
# Check PostgreSQL status
kubectl exec -it statefulset/parwa-postgres -n parwa -- pg_isready

# Check active connections
kubectl exec -it statefulset/parwa-postgres -n parwa -- psql -c "SELECT count(*) FROM pg_stat_activity;"

# Check for blocked queries
kubectl exec -it statefulset/parwa-postgres -n parwa -- psql -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# Check backend logs for connection errors
kubectl logs -l app.kubernetes.io/component=backend -n parwa | grep -i "connection"
```

**Solutions:**

1. **Connection pool exhausted:**
   ```bash
   # Increase pool size in ConfigMap
   kubectl edit configmap parwa-config -n parwa
   # Set DB_POOL_SIZE to higher value
   ```

2. **Database overloaded:**
   ```bash
   # Check for long-running queries
   kubectl exec -it statefulset/parwa-postgres -n parwa -- psql -c "
     SELECT pid, now() - pg_stat_activity.query_start AS duration, query
     FROM pg_stat_activity
     WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';
   "
   
   # Kill long-running query
   kubectl exec -it statefulset/parwa-postgres -n parwa -- psql -c "SELECT pg_terminate_backend(<pid>);"
   ```

3. **Network connectivity:**
   ```bash
   # Test connectivity from backend
   kubectl exec -it deployment/parwa-backend -n parwa -- nc -zv parwa-postgres 5432
   ```

### Redis Connection Issues

**Symptoms:**
- "Redis connection refused" errors
- Cache misses increasing
- Queue processing delays

**Diagnosis:**

```bash
# Check Redis status
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli ping

# Check Redis memory
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli info memory

# Check queue length
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli llen "arq:queue"

# Check connected clients
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli client list
```

**Solutions:**

1. **Redis memory full:**
   ```bash
   # Check maxmemory setting
   kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli config get maxmemory
   
   # Clear stale cache entries
   kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli --scan --pattern "cache:*" | xargs redis-cli del
   ```

2. **Queue backlog:**
   ```bash
   # Check queue contents
   kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli lrange "arq:queue" 0 10
   
   # Clear queue (caution: loses jobs)
   kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli del "arq:queue"
   ```

### High Latency

**Symptoms:**
- Slow API responses
- Timeouts in frontend
- User complaints about speed

**Diagnosis:**

```bash
# Check P95 latency
curl -s http://parwa-backend:9090/metrics | grep http_request_duration_seconds

# Check slow queries in PostgreSQL
kubectl exec -it statefulset/parwa-postgres -n parwa -- psql -c "
  SELECT query, calls, total_time, mean_time
  FROM pg_stat_statements
  ORDER BY mean_time DESC
  LIMIT 10;
"

# Check Redis latency
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli --latency

# Check pod resource usage
kubectl top pods -n parwa
```

**Solutions:**

1. **Database slow queries:**
   - Add missing indexes
   - Optimize query patterns
   - Consider read replicas for heavy read workloads

2. **High CPU usage:**
   ```bash
   # Scale backend
   kubectl scale deployment parwa-backend --replicas=5 -n parwa
   ```

3. **External API latency:**
   - Implement circuit breakers
   - Add caching for external API responses
   - Check OpenAI API status

### Authentication Failures

**Symptoms:**
- Users unable to log in
- "Invalid token" errors
- Session timeout errors

**Diagnosis:**

```bash
# Check auth service logs
kubectl logs -l app.kubernetes.io/component=backend -n parwa | grep -i auth

# Verify JWT secret is consistent
kubectl get secret parwa-secrets -n parwa -o jsonpath='{.data.JWT_SECRET}' | base64 -d

# Check token expiry settings
kubectl get configmap parwa-config -n parwa -o yaml | grep -i token

# Test login endpoint
curl -X POST https://api.parwa.ai/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"wrong"}'
```

**Solutions:**

1. **JWT secret mismatch:**
   - Ensure same secret across all pods
   - Restart pods after secret update

2. **Token expired:**
   - Implement token refresh in frontend
   - Increase token expiry time

3. **Database auth issues:**
   ```bash
   # Check user exists
   kubectl exec -it statefulset/parwa-postgres -n parwa -- psql -c "
     SELECT id, email, is_active FROM users WHERE email = 'user@example.com';
   "
   
   # Reset password (use bcrypt hash)
   kubectl exec -it statefulset/parwa-postgres -n parwa -- psql -c "
     UPDATE users SET password_hash = '<new_hash>' WHERE email = 'user@example.com';
   "
   ```

### OpenAI API Issues

**Symptoms:**
- Jarvis not responding
- AI features timing out
- Rate limit errors

**Diagnosis:**

```bash
# Check OpenAI API status
curl -s https://status.openai.com/api/v2/status.json | jq

# Check API key validity
kubectl logs -l app.kubernetes.io/component=backend -n parwa | grep -i "openai"

# Check rate limits
kubectl logs -l app.kubernetes.io/component=backend -n parwa | grep -i "rate limit"
```

**Solutions:**

1. **Rate limiting:**
   - Implement exponential backoff
   - Add request queuing
   - Consider higher tier API plan

2. **API key issues:**
   ```bash
   # Update API key
   kubectl create secret generic parwa-secrets \
     --from-literal=OPENAI_API_KEY='sk-new-key' \
     --dry-run=client -o yaml | kubectl apply -f - -n parwa
   
   # Restart backend
   kubectl rollout restart deployment/parwa-backend -n parwa
   ```

---

## Diagnostic Commands

### Kubernetes

```bash
# Get all resources
kubectl get all -n parwa

# Get events sorted by time
kubectl get events -n parwa --sort-by='.lastTimestamp'

# Check resource usage
kubectl top pods -n parwa
kubectl top nodes

# Port forward for local debugging
kubectl port-forward svc/parwa-backend 8000:8000 -n parwa

# Execute command in pod
kubectl exec -it deployment/parwa-backend -n parwa -- /bin/bash

# Copy files from pod
kubectl cp parwa/backend-pod:/app/logs ./logs -n parwa

# Check network policies
kubectl get networkpolicy -n parwa
```

### Database

```bash
# Connect to PostgreSQL
kubectl exec -it statefulset/parwa-postgres -n parwa -- psql -U parwa -d parwa

# Run query
kubectl exec -it statefulset/parwa-postgres -n parwa -- psql -c "SELECT 1;"

# Export database
kubectl exec statefulset/parwa-postgres -n parwa -- pg_dump -U parwa parwa > backup.sql

# Import database
cat backup.sql | kubectl exec -i statefulset/parwa-postgres -n parwa -- psql -U parwa parwa

# Check table sizes
kubectl exec -it statefulset/parwa-postgres -n parwa -- psql -c "
  SELECT
    relname AS table,
    pg_size_pretty(pg_total_relation_size(relid)) AS size
  FROM pg_catalog.pg_statio_user_tables
  ORDER BY pg_total_relation_size(relid) DESC;
"
```

### Redis

```bash
# Connect to Redis
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli

# Get all keys
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli keys '*'

# Monitor commands
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli monitor

# Get memory info
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli info memory

# Flush database (caution!)
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli flushdb
```

### Application Logs

```bash
# Stream logs
kubectl logs -f deployment/parwa-backend -n parwa

# Logs from all backend pods
kubectl logs -l app.kubernetes.io/component=backend -n parwa --max-log-requests=10

# Logs with time range
kubectl logs deployment/parwa-backend -n parwa --since=1h

# Logs to file
kubectl logs deployment/parwa-backend -n parwa > backend.log

# Search logs
kubectl logs deployment/parwa-backend -n parwa | grep -i error
```

---

## Log Locations

### Kubernetes Logs

| Component | Location |
|-----------|----------|
| Application logs | `kubectl logs <pod> -n parwa` |
| Container stdout | `/var/log/containers/<pod>*` |
| Kubelet logs | `/var/log/kubelet.log` |

### Application Log Files

| Log | Path | Purpose |
|-----|------|---------|
| Application | `/app/logs/app.log` | General application logs |
| Access | `/app/logs/access.log` | HTTP request logs |
| Error | `/app/logs/error.log` | Error-only logs |
| Audit | `/app/logs/audit.log` | Audit trail |

### Log Levels

| Level | Use Case |
|-------|----------|
| DEBUG | Detailed debugging information |
| INFO | General operational messages |
| WARNING | Potential issues, non-critical |
| ERROR | Errors requiring attention |
| CRITICAL | System-wide issues |

### Configure Log Level

```bash
# Via ConfigMap
kubectl edit configmap parwa-config -n parwa
# Change LOG_LEVEL value

# Restart pods
kubectl rollout restart deployment/parwa-backend -n parwa
```

---

## Performance Debugging

### Profiling

```bash
# Enable Python profiler
kubectl exec -it deployment/parwa-backend -n parwa -- python -m cProfile -o profile.stats app/main.py

# Download profile results
kubectl cp parwa/backend-pod:/app/profile.stats ./profile.stats

# Analyze with snakeviz
pip install snakeviz
snakeviz profile.stats
```

### Memory Debugging

```bash
# Check memory usage
kubectl top pods -n parwa

# Memory dump (Python)
kubectl exec -it deployment/parwa-backend -n parwa -- python -c "
import tracemalloc
import snapshot
tracemalloc.start()
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
for stat in top_stats[:10]:
    print(stat)
"

# Heap analysis
kubectl exec -it deployment/parwa-backend -n parwa -- python -c "
import objgraph
objgraph.show_most_common_types(limit=20)
"
```

### Database Performance

```sql
-- Enable query timing
\timing on

-- Explain analyze query
EXPLAIN ANALYZE SELECT * FROM tickets WHERE status = 'open';

-- Check missing indexes
SELECT
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE tablename = 'tickets';

-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;
```

### Load Testing

```bash
# Install locust
pip install locust

# Run load test
locust -f tests/performance/test_load.py \
  --host https://api.parwa.ai \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --headless

# Results saved to:
# - locust_stats.csv
# - locust_stats_history.csv
```

---

## Known Limitations

### Technical Limitations

| Limitation | Value | Notes |
|------------|-------|-------|
| Max file upload size | 50 MB | Configurable in ingress |
| Max team members | 50 | Per tenant |
| Max tickets per tenant | 10,000 (Mini) / 50,000 (Senior) | Per variant |
| Max API request size | 10 MB | Request body limit |
| WebSocket connection timeout | 5 minutes | Idle timeout |
| Max concurrent WebSocket | 1,000 | Per backend pod |

### Feature Limitations

1. **Multi-tenant search**: Full-text search is per-tenant, not cross-tenant
2. **Real-time updates**: Requires WebSocket connection; polling fallback available
3. **File uploads**: Not replicated across regions
4. **AI responses**: Dependent on OpenAI API availability

### Scaling Considerations

| Component | Max Tested Scale | Scaling Strategy |
|-----------|------------------|------------------|
| Backend pods | 50 replicas | Horizontal |
| Worker pods | 20 replicas | Horizontal |
| Database connections | 200 | Connection pooling |
| Redis memory | 4 GB | Vertical |
| Concurrent users | 10,000 | Horizontal |

---

## FAQ

### General

**Q: How do I reset a user's password?**

A: Use the admin API or database:
```bash
# Via API (requires admin token)
curl -X POST https://api.parwa.ai/api/v1/admin/users/{id}/reset-password \
  -H "Authorization: Bearer <admin-token>"

# Via database (generate bcrypt hash first)
kubectl exec -it statefulset/parwa-postgres -n parwa -- psql -c "
  UPDATE users SET password_hash = '<bcrypt-hash>' WHERE id = '<user-id>';
"
```

**Q: How do I clear all cached data?**

A: Flush Redis cache:
```bash
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli FLUSHALL
```

**Q: How do I enable debug logging?**

A: Update ConfigMap and restart:
```bash
kubectl set env deployment/parwa-backend LOG_LEVEL=DEBUG -n parwa
kubectl rollout restart deployment/parwa-backend -n parwa
```

### Performance

**Q: Why is my API slow?**

A: Check in order:
1. Database query performance
2. Redis cache hit rate
3. External API latency (OpenAI)
4. Pod resource usage
5. Network latency

**Q: How do I increase throughput?**

A:
1. Scale backend pods: `kubectl scale deployment parwa-backend --replicas=10 -n parwa`
2. Increase connection pool size
3. Add read replicas for database
4. Enable response caching

### Security

**Q: How do I rotate secrets?**

A:
```bash
# Update secret in secret manager
aws secretsmanager update-secret --secret-id parwa/production --secret-string '{"key":"value"}'

# Trigger External Secrets refresh
kubectl annotate externalsecret parwa-secrets force-sync=$(date +%s) -n parwa

# Restart pods
kubectl rollout restart deployment -n parwa
```

**Q: How do I audit user actions?**

A: Query audit logs:
```sql
SELECT * FROM audit_logs
WHERE user_id = '<user-id>'
ORDER BY timestamp DESC
LIMIT 100;
```

### Troubleshooting

**Q: My pod keeps crashing, what do I do?**

A:
```bash
# Check previous container logs
kubectl logs <pod> --previous -n parwa

# Check pod events
kubectl describe pod <pod> -n parwa

# Check if it's OOMKilled
kubectl get pod <pod> -n parwa -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'
```

**Q: How do I debug network issues?**

A:
```bash
# Test DNS resolution
kubectl exec -it deployment/parwa-backend -n parwa -- nslookup parwa-postgres

# Test connectivity
kubectl exec -it deployment/parwa-backend -n parwa -- nc -zv parwa-postgres 5432

# Check network policies
kubectl get networkpolicy -n parwa
kubectl describe networkpolicy <policy-name> -n parwa
```

---

## Getting Help

### Internal Resources

- **Documentation**: https://docs.parwa.ai
- **Runbooks**: https://docs.parwa.ai/runbooks
- **API Reference**: https://docs.parwa.ai/api

### Contact

- **Slack**: #parwa-support
- **Email**: support@parwa.ai
- **Emergency**: PagerDuty on-call
