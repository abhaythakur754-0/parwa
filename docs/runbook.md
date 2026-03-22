# PARWA Operations Runbook

**Version:** 1.0.0
**Last Updated:** 2026-03-22
**Owner:** Platform Operations Team

---

## Table of Contents

1. [Incident Response Overview](#incident-response-overview)
2. [Alert Response Guides](#alert-response-guides)
3. [Escalation Procedures](#escalation-procedures)
4. [Common Issues and Resolutions](#common-issues-and-resolutions)
5. [On-Call Procedures](#on-call-procedures)
6. [System Architecture](#system-architecture)
7. [Contact Information](#contact-information)

---

## Incident Response Overview

### Incident Severity Levels

| Severity | Definition | Response Time | Escalation |
|----------|------------|---------------|------------|
| **P1 - Critical** | Complete service outage, data loss risk, security breach | < 5 minutes | Immediate escalation to all teams |
| **P2 - High** | Major feature unavailable, significant degradation | < 15 minutes | Escalate after 30 min if unresolved |
| **P3 - Medium** | Minor feature issues, workaround available | < 1 hour | Escalate after 4 hours if unresolved |
| **P4 - Low** | Cosmetic issues, non-urgent improvements | < 24 hours | Standard ticket process |

### Incident Response Workflow

```
1. DETECT → Alert fires / User report / Internal discovery
2. ASSESS → Determine severity, impact scope, affected components
3. CONTAIN → Stop bleeding, prevent further damage
4. RESOLVE → Fix the root cause
5. RECOVER → Restore full service, verify functionality
6. REVIEW → Post-incident review, document learnings
```

### Initial Response Checklist

- [ ] Acknowledge the alert in monitoring system
- [ ] Join incident channel: #parwa-incidents
- [ ] Assess severity level (P1-P4)
- [ ] Notify relevant stakeholders
- [ ] Start incident timer
- [ ] Begin troubleshooting with relevant runbook section

---

## Alert Response Guides

### HighErrorRate

**Alert Condition:** Error rate > 5% for 5 minutes

**Severity:** Warning → Critical (if sustained > 15 min)

**Impact:** Users experiencing failed requests, potential data inconsistencies

**Immediate Actions:**

1. **Identify affected service:**
   ```bash
   # Check which service has high error rate
   curl -s http://prometheus:9090/api/v1/query?query=rate(http_requests_total{status=~"5.."}[5m])
   ```

2. **Check recent deployments:**
   ```bash
   # View recent deployments
   kubectl rollout history deployment/parwa-backend
   git log --oneline -10
   ```

3. **Examine logs for errors:**
   ```bash
   # Search for error patterns
   kubectl logs -l app=parwa-backend --since=10m | grep -i error
   ```

4. **Check downstream dependencies:**
   - PostgreSQL: `pg_isready -h postgres -p 5432`
   - Redis: `redis-cli ping`
   - Paddle API: Check status.paddle.com

**Resolution Steps:**

| Cause | Resolution |
|-------|------------|
| Recent deployment issue | Rollback: `kubectl rollout undo deployment/parwa-backend` |
| Database connection pool exhaustion | Restart pods, check pool settings |
| External API failure | Enable circuit breaker, use fallback |
| Memory pressure | Scale horizontally, check for leaks |

**Escalation:** If unresolved after 15 minutes, escalate to P1.

---

### HighLatency

**Alert Condition:** P95 latency > 1s for 5 minutes

**Severity:** Warning → Critical (if > 2s sustained)

**Impact:** Slow user experience, potential timeout failures

**Immediate Actions:**

1. **Identify slow endpoints:**
   ```bash
   # Query P95 latency by endpoint
   curl -s 'http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(http_request_duration_seconds_bucket[5m]))by(le,path))'
   ```

2. **Check database query performance:**
   ```sql
   -- Find slow queries
   SELECT query, mean_exec_time, calls
   FROM pg_stat_statements
   ORDER BY mean_exec_time DESC
   LIMIT 10;
   ```

3. **Check cache hit rates:**
   ```bash
   redis-cli info stats | grep keyspace
   ```

4. **Review GSD engine compression:**
   ```bash
   # Check compression ratios
   curl http://localhost:8001/metrics | grep gsd_compression
   ```

**Resolution Steps:**

| Cause | Resolution |
|-------|------------|
| Missing database index | Add appropriate index, analyze query plan |
| Cache miss spike | Warm cache, review cache invalidation logic |
| Large context in GSD | Trigger manual compression, review message limits |
| Network issues | Check network policies, DNS resolution |
| Resource constraints | Scale horizontally or vertically |

**Escalation:** If latency > 2s for 10+ minutes, escalate to P1.

---

### SLABreach

**Alert Condition:** SLA breach detected (ticket exceeds time threshold)

**Severity:** Critical

**Impact:** Customer dissatisfaction, potential penalties for enterprise customers

**Immediate Actions:**

1. **Identify breached ticket:**
   ```bash
   # Get ticket details from alert
   # Alert includes: ticket_id, priority, time_elapsed
   ```

2. **Check ticket status:**
   ```sql
   SELECT id, priority, created_at, sla_due_at, status, assigned_agent
   FROM tickets WHERE id = '{ticket_id}';
   ```

3. **Review conversation history:**
   ```bash
   # Check conversation context
   curl "http://localhost:8000/api/tickets/{ticket_id}/context"
   ```

4. **Assign to senior agent immediately:**
   - Escalate to human agent with highest priority
   - Notify customer of delay

**Resolution Steps:**

| Cause | Resolution |
|-------|------------|
| Agent overload | Reassign ticket, check queue balance |
| Complex issue | Escalate to Tier 2, request specialist |
| Integration failure | Fix integration, re-process ticket |
| Missing context | Retrieve full context from GSD engine |

**Post-Resolution:**

1. Document why SLA was breached
2. Identify systemic issues
3. Update SLA thresholds if needed
4. Customer follow-up within 24 hours

---

### RefundGateViolation

**Alert Condition:** Paddle called without approval

**Severity:** Critical (Security Alert)

**Impact:** Financial risk, compliance violation, potential fraud

**Immediate Actions:**

1. **STOP all refund processing:**
   ```bash
   # Use Jarvis to pause refunds
   curl -X POST http://localhost:8000/api/jarvis/pause_refunds
   ```

2. **Identify unauthorized call:**
   ```bash
   # Check audit logs
   kubectl logs -l app=parwa-backend --since=30m | grep -i paddle
   ```

3. **Review approval queue:**
   ```sql
   SELECT * FROM approval_requests
   WHERE status = 'pending' OR created_at > NOW() - INTERVAL '1 hour'
   ORDER BY created_at DESC;
   ```

4. **Check for code bypass:**
   ```bash
   # Find any direct Paddle calls bypassing approval service
   git log --all --oneline --grep="paddle" --since="1 day ago"
   ```

**Resolution Steps:**

| Cause | Resolution |
|-------|------------|
| Code bug | Emergency patch, deploy fix |
| Configuration error | Fix environment variables |
| Security breach | Rotate Paddle credentials, audit access |
| Test code in prod | Remove, review deployment process |

**Required Actions:**

1. Document all unauthorized transactions
2. Notify finance team immediately
3. Review all refund attempts in last 24 hours
4. Enable additional approval gates if needed

**Escalation:** IMMEDIATE escalation to Security team and Finance.

---

### ModelDrift

**Alert Condition:** Agent Lightning model accuracy < 85%

**Severity:** Warning

**Impact:** Poor AI responses, increased escalations, customer satisfaction drop

**Immediate Actions:**

1. **Check model metrics:**
   ```bash
   # Query model accuracy history
   curl 'http://prometheus:9090/api/v1/query?query=agent_lightning_model_accuracy'
   ```

2. **Review recent training data:**
   ```bash
   # Check training data quality
   ls -la agent_lightning/data/
   wc -l agent_lightning/data/training.jsonl
   ```

3. **Compare with baseline:**
   ```sql
   SELECT version, accuracy, deployed_at
   FROM model_registry
   WHERE deployed = true
   ORDER BY deployed_at DESC
   LIMIT 5;
   ```

4. **Check quality coach scores:**
   ```bash
   curl 'http://prometheus:9090/api/v1/query?query=quality_coach_accuracy_avg'
   ```

**Resolution Steps:**

| Cause | Resolution |
|-------|------------|
| Data quality issue | Review training data, fix labeling errors |
| Concept drift | Retrain with recent data |
| Edge cases | Add specific training examples |
| Feature changes | Update feature engineering |

**Actions:**

1. If accuracy < 80%, consider rollback to previous model version
2. Trigger retraining pipeline with quality data
3. Review Quality Coach feedback for common failures
4. Deploy new model only when accuracy > 90%

---

### WorkerDown

**Alert Condition:** Worker not responding for 2+ minutes

**Severity:** Critical

**Impact:** Background tasks not processing (recalls, outreach, reports)

**Immediate Actions:**

1. **Identify affected worker:**
   ```bash
   # Check worker heartbeats
   redis-cli get "worker:heartbeat:*"
   ```

2. **Check worker process:**
   ```bash
   # List worker pods
   kubectl get pods -l component=worker

   # Check worker logs
   kubectl logs -l component=worker --tail=100
   ```

3. **Check Redis connection:**
   ```bash
   redis-cli ping
   redis-cli info clients
   ```

4. **Check ARQ queue:**
   ```bash
   # Check pending jobs
   redis-cli llen "arq:queue"
   ```

**Resolution Steps:**

| Cause | Resolution |
|-------|------------|
| Crash loop | Check logs, fix error, restart pod |
| Memory exhaustion | Increase memory limit, check for leaks |
| Redis connection lost | Fix network, restart worker |
| Dependency failure | Fix dependency, restart worker |
| Deadlock | Restart worker, review concurrency code |

**Worker Recovery:**

```bash
# Restart specific worker
kubectl rollout restart deployment/worker-recall
kubectl rollout restart deployment/worker-outreach
kubectl rollout restart deployment/worker-report
kubectl rollout restart deployment/worker-kb-indexer
```

---

## Escalation Procedures

### Escalation Matrix

| Severity | 0-15 min | 15-30 min | 30-60 min | 60+ min |
|----------|----------|-----------|-----------|---------|
| P1 | On-call + Lead | + Manager | + Director | + VP |
| P2 | On-call | On-call + Lead | + Manager | + Director |
| P3 | On-call | On-call | On-call + Lead | + Manager |
| P4 | Ticket | Ticket | Ticket | Ticket |

### Escalation Contacts

| Role | Primary | Backup |
|------|---------|--------|
| On-Call Engineer | PagerDuty Rotation | See PagerDuty Schedule |
| Team Lead | @lead-parwa | @lead-backup |
| Engineering Manager | @eng-manager | @eng-director |
| Security | @security-team | security@company.com |
| Finance | @finance-team | finance@company.com |

### Communication Templates

**Internal Incident Notification:**
```
🚨 INCIDENT [SEVERITY]: [Brief Description]

- Impact: [Affected users/features]
- Current Status: [Investigating/Identified/Monitoring]
- Incident Channel: #parwa-incidents
- Incident Commander: @username
- Next Update: [time]
```

**Customer Communication (P1/P2):**
```
We are currently experiencing issues with [feature/service].
Our team is actively working to resolve this.
We will provide an update within [timeframe].
Status page: status.parwa.io
```

---

## Common Issues and Resolutions

### Database Issues

#### Connection Pool Exhaustion
```
Symptoms: "Connection pool exhausted" errors, timeouts
Diagnosis: Check active connections
Resolution:
1. kubectl rollout restart deployment/parwa-backend
2. Review pool size settings in config
3. Check for long-running queries
```

#### Slow Queries
```
Symptoms: High latency, database CPU spike
Diagnosis:
SELECT * FROM pg_stat_activity WHERE state = 'active';
EXPLAIN ANALYZE [slow_query];
Resolution:
1. Add missing indexes
2. Optimize query
3. Consider materialized views for reports
```

### Redis Issues

#### Memory Pressure
```
Symptoms: Evictions, OOM errors
Diagnosis: redis-cli info memory
Resolution:
1. Increase memory limit
2. Review cache TTL settings
3. Clear stale keys: redis-cli --scan --pattern 'cache:*' | xargs redis-cli del
```

#### Connection Issues
```
Symptoms: Timeout errors, refused connections
Diagnosis: redis-cli ping, check max clients
Resolution:
1. Check network policies
2. Increase max clients
3. Check for connection leaks
```

### MCP Server Issues

#### Server Not Responding
```
Symptoms: Tool calls timing out
Diagnosis:
1. Check server logs
2. Verify port is listening
3. Check resource usage
Resolution:
1. Restart specific MCP server
2. Check for memory leaks
3. Review rate limiting settings
```

### AI/Guardrails Issues

#### High Hallucination Rate
```
Symptoms: Incorrect AI responses, customer complaints
Diagnosis: Check guardrails metrics
Resolution:
1. Review blocked hallucinations in logs
2. Add specific guardrails rules
3. Retrain with corrections
```

#### TRIVYA Tier Escalation Issues
```
Symptoms: Wrong tier assignments, missed escalations
Diagnosis: Check TRIVYA metrics
Resolution:
1. Review tier thresholds
2. Check confidence scores
3. Verify sentiment analysis
```

---

## On-Call Procedures

### Pre-Shift Checklist

- [ ] Review pending incidents
- [ ] Check system health dashboard
- [ ] Verify access to all systems
- [ ] Update PagerDuty contact info
- [ ] Review recent changes

### During Shift Responsibilities

1. **Monitor alerts** - Acknowledge within 5 minutes
2. **Triage issues** - Classify severity
3. **Resolve or escalate** - Follow runbooks
4. **Document everything** - Update incident tickets
5. **Handoff** - Brief next on-call

### Post-Incident Checklist

- [ ] Incident resolved
- [ ] Root cause identified
- [ ] Incident report created
- [ ] Follow-up tasks created
- [ ] Runbook updated if needed
- [ ] Customer notified (if applicable)

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           LOAD BALANCER                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌───────────┐   ┌───────────┐   ┌───────────┐
            │  Backend  │   │  Backend  │   │  Backend  │
            │   API     │   │   API     │   │   API     │
            └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
                  │               │               │
    ┌─────────────┼───────────────┼───────────────┼─────────────┐
    │             │               │               │             │
    ▼             ▼               ▼               ▼             ▼
┌────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐
│Postgres│  │  Redis   │  │ MCP Servers  │  │ Workers  │  │ Jarvis   │
│   DB   │  │  Cache   │  │ (11 servers) │  │  (ARQ)   │  │  Agent   │
└────────┘  └──────────┘  └──────────────┘  └──────────┘  └──────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │   FAQ    │   │   RAG    │   │   KB     │
        │  Server  │   │  Server  │   │  Server  │
        └──────────┘   └──────────┘   └──────────┘
```

### Key Metrics Endpoints

| Component | Metrics URL | Health URL |
|-----------|-------------|------------|
| Backend API | http://api:8000/metrics | http://api:8000/health |
| GSD Engine | http://gsd:8001/metrics | http://gsd:8001/health |
| Smart Router | http://router:8002/metrics | http://router:8002/health |
| Prometheus | http://prometheus:9090/metrics | http://prometheus:9090/-/healthy |
| Grafana | http://grafana:3000/metrics | http://grafana:3000/api/health |

### Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment name | development |
| `LOG_LEVEL` | Logging level | INFO |
| `DATABASE_URL` | PostgreSQL connection | Required |
| `REDIS_URL` | Redis connection | Required |
| `PADDLE_API_KEY` | Paddle API key | Required |
| `SLACK_WEBHOOK_URL` | Slack alerts webhook | Optional |

---

## Contact Information

### Internal Teams

| Team | Slack Channel | Email |
|------|---------------|-------|
| Platform | #parwa-platform | platform@company.com |
| Security | #security-team | security@company.com |
| SRE | #sre-team | sre@company.com |
| Finance | #finance-team | finance@company.com |

### External Vendors

| Vendor | Support | Status Page |
|--------|---------|-------------|
| Paddle | support@paddle.com | status.paddle.com |
| AWS | AWS Support | status.aws.amazon.com |
| OpenAI | support.openai.com | status.openai.com |

### Emergency Contacts

- **Security Incident:** security-emergency@company.com
- **Finance Emergency:** finance-emergency@company.com
- **On-Call Escalation:** PagerDuty escalation policy "PARWA Critical"

---

*This runbook is maintained by the Platform Operations Team. For updates or corrections, submit a PR to the parwa repository.*
