# PARWA Operations Runbook

## Overview

This runbook provides operational procedures for PARWA production environments. It covers service management, incident response, and maintenance procedures for on-call engineers.

## Table of Contents

1. [Service Overview](#service-overview)
2. [Health Check Endpoints](#health-check-endpoints)
3. [Common Alerts and Responses](#common-alerts-and-responses)
4. [Escalation Procedures](#escalation-procedures)
5. [Backup and Restore](#backup-and-restore)
6. [Maintenance Windows](#maintenance-windows)
7. [Contact Information](#contact-information)

---

## Service Overview

### Architecture Components

| Service | Port | Replicas | Description |
|---------|------|----------|-------------|
| Backend | 8000 | 3-10 | FastAPI application server |
| Frontend | 3000 | 2-5 | Next.js web application |
| Worker | - | 2-10 | ARQ async task processor |
| MCP | 8001-8003 | 2-5 | Model Context Protocol servers |
| Redis | 6379 | 1 | Cache and message queue |
| PostgreSQL | 5432 | 1 | Primary database |

### Service Dependencies

```
Frontend → Backend → PostgreSQL
                   → Redis
                   → OpenAI API
                   
Worker → PostgreSQL
       → Redis
       → OpenAI API

MCP → PostgreSQL
    → Redis
```

### Resource Allocation

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---------|-------------|-----------|----------------|--------------|
| Backend | 250m | 1000m | 512Mi | 2Gi |
| Frontend | 100m | 500m | 128Mi | 512Mi |
| Worker | 250m | 1000m | 512Mi | 2Gi |
| MCP | 100m | 500m | 256Mi | 1Gi |
| Redis | 100m | 500m | 256Mi | 1Gi |
| PostgreSQL | 250m | 2000m | 512Mi | 4Gi |

---

## Health Check Endpoints

### Backend Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `/health/live` | Liveness probe | 200 OK |
| `/health/ready` | Readiness probe | 200 OK |
| `/health/startup` | Startup probe | 200 OK |
| `/health/detailed` | Detailed health | JSON with component status |

**Example Health Check:**

```bash
curl -s https://api.parwa.ai/health/detailed | jq
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-03-22T10:00:00Z",
  "components": {
    "database": "healthy",
    "redis": "healthy",
    "openai": "healthy"
  },
  "version": "1.0.0"
}
```

### Frontend Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `/health` | Health check | 200 OK |

### MCP Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `/health` | Service health | 200 OK |
| `/ready` | Ready to serve | 200 OK |

### Kubernetes Health Probes

```bash
# Check pod health
kubectl describe pod <pod-name> -n parwa | grep -A 10 "Liveness\|Readiness"

# Check recent events
kubectl get events -n parwa --sort-by='.lastTimestamp'
```

---

## Common Alerts and Responses

### Alert: High CPU Usage

**Symptoms:**
- CPU utilization > 80% for 5+ minutes
- HPA scaling events
- Slow response times

**Investigation:**

```bash
# Check CPU usage by pod
kubectl top pods -n parwa

# Check HPA status
kubectl describe hpa parwa-backend-hpa -n parwa

# View application logs
kubectl logs -l app.kubernetes.io/component=backend -n parwa --tail=100
```

**Resolution:**
1. If HPA is scaling correctly, monitor until stable
2. If HPA is maxed out, consider increasing maxReplicas
3. If scaling issue, check for runaway processes or memory leaks

### Alert: High Memory Usage

**Symptoms:**
- Memory utilization > 85%
- OOMKilled pods
- Frequent pod restarts

**Investigation:**

```bash
# Check memory usage
kubectl top pods -n parwa

# Check for OOMKilled pods
kubectl get pods -n parwa -o json | jq '.items[] | select(.status.containerStatuses[].lastState.terminated.reason=="OOMKilled")'

# Check memory limits
kubectl describe pod <pod-name> -n parwa | grep -A 5 "Limits:"
```

**Resolution:**
1. Increase memory limits in deployment
2. Check for memory leaks in application code
3. Enable memory profiling for debugging

### Alert: Database Connection Pool Exhausted

**Symptoms:**
- Connection timeouts
- "Too many connections" errors
- Slow database queries

**Investigation:**

```bash
# Check active connections
kubectl exec -it deployment/parwa-backend -n parwa -- python -c "
from sqlalchemy import create_engine, text
engine = create_engine('$DATABASE_URL')
with engine.connect() as conn:
    result = conn.execute(text('SELECT count(*) FROM pg_stat_activity'))
    print(result.scalar())
"

# Check connection pool status
kubectl logs -l app.kubernetes.io/component=backend -n parwa | grep -i "connection"
```

**Resolution:**
1. Scale backend replicas to distribute load
2. Increase connection pool size
3. Check for long-running transactions

### Alert: Redis Connection Issues

**Symptoms:**
- Redis timeout errors
- Cache misses increasing
- Queue processing delays

**Investigation:**

```bash
# Check Redis status
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli ping

# Check Redis memory
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli info memory

# Check queue length
kubectl exec -it statefulset/parwa-redis -n parwa -- redis-cli llen "arq:queue"
```

**Resolution:**
1. Clear stale cache entries
2. Increase Redis memory limit
3. Check for memory-hungry keys

### Alert: High Error Rate

**Symptoms:**
- 5xx errors > 1% of requests
- Error logs increasing
- User reports of failures

**Investigation:**

```bash
# Check error logs
kubectl logs -l app.kubernetes.io/component=backend -n parwa --since=1h | grep -i error

# Check ingress errors
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx | grep -i " 5[0-9][0-9] "

# Check error metrics
curl -s http://parwa-backend:9090/metrics | grep http_requests_failed_total
```

**Resolution:**
1. Identify error patterns in logs
2. Check for upstream service failures
3. Roll back if recent deployment caused issue

### Alert: Certificate Expiring

**Symptoms:**
- TLS certificate expiring in < 7 days
- cert-manager stuck in pending state

**Investigation:**

```bash
# Check certificate status
kubectl get certificate -n parwa

# Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager

# Check ACME challenges
kubectl get challenges -n parwa
```

**Resolution:**
1. Verify DNS records are correct
2. Check cert-manager service account permissions
3. Manually trigger renewal if needed

---

## Escalation Procedures

### Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| P1 - Critical | Service down, data loss risk | 15 minutes | Complete outage, security breach |
| P2 - High | Major feature unavailable | 30 minutes | Payment failures, login issues |
| P3 - Medium | Degraded performance | 2 hours | Slow responses, partial feature loss |
| P4 - Low | Minor issues | 24 hours | Non-critical bugs, cosmetic issues |

### Escalation Path

```
On-Call Engineer (L1)
    ↓ (15 min no response)
Engineering Lead (L2)
    ↓ (30 min no response)
CTO / Engineering Director (L3)
```

### Escalation Contacts

| Role | Name | Phone | Slack | Email |
|------|------|-------|-------|-------|
| On-Call L1 | PagerDuty | - | @oncall | oncall@parwa.ai |
| Engineering Lead | - | - | @eng-lead | lead@parwa.ai |
| CTO | - | - | @cto | cto@parwa.ai |

### Incident Communication

1. **Initial Response**: Acknowledge alert within 5 minutes
2. **Status Update**: Post to #incidents Slack channel every 15 minutes
3. **Resolution**: Post summary when resolved
4. **Post-mortem**: Schedule within 48 hours for P1/P2 incidents

---

## Backup and Restore

### Backup Schedule

| Component | Frequency | Retention | Location |
|-----------|-----------|-----------|----------|
| PostgreSQL | Hourly | 30 days | S3: parwa-backups/db/ |
| Redis | Daily | 7 days | S3: parwa-backups/redis/ |
| Kubernetes manifests | On change | 90 days | Git repository |

### Manual Backup

```bash
# Backup PostgreSQL
kubectl exec -it statefulset/parwa-postgres -n parwa -- \
  pg_dump -U parwa parwa | gzip > parwa_backup_$(date +%Y%m%d).sql.gz

# Backup to S3
aws s3 cp parwa_backup_$(date +%Y%m%d).sql.gz s3://parwa-backups/db/
```

### Restore Procedure

```bash
# Download backup
aws s3 cp s3://parwa-backups/db/parwa_backup_20260322.sql.gz .

# Restore to PostgreSQL
gunzip -c parwa_backup_20260322.sql.gz | kubectl exec -i statefulset/parwa-postgres -n parwa -- \
  psql -U parwa parwa
```

### Point-in-Time Recovery

For PostgreSQL with WAL archiving:

```bash
# Restore to specific timestamp
kubectl exec -it statefulset/parwa-postgres -n parwa -- \
  pg_restore --target-time="2026-03-22 10:00:00" /backup/base.tar
```

---

## Maintenance Windows

### Scheduled Maintenance

- **Weekly**: Sundays 02:00-04:00 UTC
- **Monthly**: First Sunday of month, extended window

### Maintenance Procedures

1. **Announce Maintenance**:
   - Post to #announcements 48 hours in advance
   - Update status page

2. **Enable Maintenance Mode**:
   ```bash
   kubectl apply -f infra/k8s/maintenance-mode.yaml
   ```

3. **Perform Maintenance**:
   - Apply updates
   - Run migrations
   - Verify changes

4. **Disable Maintenance Mode**:
   ```bash
   kubectl delete -f infra/k8s/maintenance-mode.yaml
   ```

5. **Verify Services**:
   ```bash
   ./scripts/smoke-test.sh
   ```

### Emergency Maintenance

For unplanned maintenance:

1. Post immediate notification to #incidents
2. Follow standard maintenance procedure
3. Conduct post-mortem after resolution

---

## Contact Information

### Internal Contacts

| Team | Slack Channel | Email |
|------|--------------|-------|
| Platform | #platform | platform@parwa.ai |
| Backend | #backend | backend@parwa.ai |
| Frontend | #frontend | frontend@parwa.ai |
| DevOps | #devops | devops@parwa.ai |
| Security | #security | security@parwa.ai |

### External Contacts

| Service | Support | Status Page |
|---------|---------|-------------|
| Supabase | support@supabase.com | status.supabase.com |
| OpenAI | support@openai.com | status.openai.com |
| Paddle | seller-support@paddle.com | status.paddle.com |
| AWS | AWS Support | status.aws.amazon.com |

### Useful Commands

```bash
# Quick status check
kubectl get all -n parwa

# Resource usage
kubectl top pods -n parwa

# Recent events
kubectl get events -n parwa --sort-by='.lastTimestamp' | head -20

# Logs aggregation
kubectl logs -l app.kubernetes.io/name=parwa -n parwa --tail=100 -f
```
