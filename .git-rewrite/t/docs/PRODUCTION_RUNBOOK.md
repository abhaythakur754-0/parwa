# PARWA Production Runbook

> **Version:** 1.0  
> **Last Updated:** 2025-07-10  
> **Classification:** Internal — Operations Team  
> **System:** PARWA AI Customer Care Platform (parwa.ai)

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Deployment](#2-deployment)
3. [SSL/TLS Configuration](#3-ssltls-configuration)
4. [Monitoring & Alerting](#4-monitoring--alerting)
5. [Rollback Procedures](#5-rollback-procedures)
6. [Troubleshooting](#6-troubleshooting)
7. [Maintenance](#7-maintenance)
8. [Security Checklist](#8-security-checklist)

---

## 1. Environment Setup

### 1.1 Prerequisites

| Component | Minimum Version | Purpose |
|-----------|----------------|---------|
| Docker | 24.0+ | Container runtime |
| Docker Compose | 2.20+ (v2 plugin) | Container orchestration |
| certbot | 2.0+ | Let's Encrypt SSL certificates |
| openssl | 3.0+ | SSL verification, DH params |
| curl | 7.88+ | Health checks, SSL testing |
| jq | 1.6+ | JSON parsing in scripts |
| git | 2.40+ | Source control |

**Domain Requirements:**
- `parwa.ai` — Primary application domain
- `www.parwa.ai` — WWW alias (CNAME to parwa.ai)
- `monitoring.parwa.ai` — Grafana dashboard (A record)
- `api.parwa.ai` — Reserved for future API gateway

**DNS Records (example):**

| Type | Name | Value |
|------|------|-------|
| A | parwa.ai | `<SERVER_IP>` |
| A | www.parwa.ai | `<SERVER_IP>` |
| A | monitoring.parwa.ai | `<SERVER_IP>` |
| A | api.parwa.ai | `<SERVER_IP>` |

### 1.2 Environment Variables

The production environment file is `.env.prod`. Below is the complete reference.

#### Application Core

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | **Yes** | `production` | Must be `production` in prod |
| `SECRET_KEY` | **Yes** | `<64-char-random>` | General application secret |
| `DEBUG` | No | `false` | Debug mode (always false in prod) |
| `VERSION` | No | `1.2.3` | Application version for image tagging |

#### Database

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | **Yes** | `postgresql://parwa:<pass>@db:5432/parwa_db` | PostgreSQL connection string |
| `POSTGRES_USER` | **Yes** | `parwa` | PostgreSQL username |
| `POSTGRES_PASSWORD` | **Yes** | `<strong-password>` | PostgreSQL password |
| `POSTGRES_DB` | **Yes** | `parwa_db` | Database name |

#### Redis

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | **Yes** | `redis://:<pass>@redis:6379/0` | Redis cache URL (DB 0) |
| `REDIS_PASSWORD` | **Yes** | `<strong-password>` | Redis authentication password |
| `CELERY_BROKER_URL` | **Yes** | `redis://:<pass>@redis:6379/1` | Celery broker (DB 1) |
| `CELERY_RESULT_BACKEND` | **Yes** | `redis://:<pass>@redis:6379/2` | Celery results (DB 2) |

#### JWT Authentication

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET_KEY` | **Yes** | `<64-char-random>` | HS256 signing key |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `15` | Access token TTL |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token TTL |
| `JWT_ALGORITHM` | No | `HS256` | `HS256` or `RS256` |
| `JWT_PRIVATE_KEY_PATH` | No | `/secrets/private.pem` | RSA private key path (RS256) |
| `JWT_PUBLIC_KEY_PATH` | No | `/secrets/public.pem` | RSA public key path (RS256) |
| `JWT_KID` | No | `parwa-key-v1` | Key ID for JWT header |

#### AI / LLM Providers

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `GOOGLE_AI_API_KEY` | No | `AIza...` | Google AI (Gemini) API key |
| `GROQ_API_KEY` | No | `gsk_...` | Groq API key (fallback) |
| `CEREBRAS_API_KEY` | No | `csk-...` | Cerebras API key |
| `LLM_PRIMARY_PROVIDER` | No | `google` | Primary LLM provider |
| `LLM_FALLBACK_PROVIDER` | No | `groq` | Fallback LLM provider |
| `AI_LIGHT_MODEL` | No | `gemini-2.0-flash` | Light model for classification |
| `AI_MEDIUM_MODEL` | No | `gemini-1.5-pro` | Medium model for responses |
| `AI_HEAVY_MODEL` | No | `gemini-1.5-pro` | Heavy model for complex tasks |

#### Email (Brevo)

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `BREVO_API_KEY` | No | `xkeysib-...` | Brevo (Sendinblue) API key |
| `FROM_EMAIL` | No | `noreply@parwa.ai` | Sender email address |

#### SMS/Voice (Twilio)

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `TWILIO_ACCOUNT_SID` | No | `AC...` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | No | `<auth-token>` | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | No | `+1234567890` | Twilio phone number |

#### Payments (Paddle)

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `PADDLE_CLIENT_TOKEN` | No | `<paddle-token>` | Paddle client-side token |
| `PADDLE_API_KEY` | No | `<paddle-api-key>` | Paddle server-side API key |
| `PADDLE_WEBHOOK_SECRET` | No | `<webhook-secret>` | Paddle webhook signing secret |

#### Monitoring

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `SENTRY_DSN` | No | `https://...@sentry.io/...` | Sentry error tracking DSN |
| `SENTRY_TRACES_SAMPLE_RATE` | No | `0.1` | Sentry performance tracing sample rate |
| `SENTRY_ENVIRONMENT` | No | `production` | Sentry environment tag |
| `GRAFANA_API_KEY` | No | `<grafana-key>` | Grafana API key |

#### Security

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `DATA_ENCRYPTION_KEY` | **Yes** | `<32-char-exactly>` | Fernet key for data encryption |
| `PRICING_SIGNING_KEY` | **Yes** | `<32-char-exactly>` | HMAC key for pricing integrity |
| `CORS_ORIGINS` | No | `https://parwa.ai` | Comma-separated CORS origins |
| `IP_ALLOWLIST_ENABLED` | No | `false` | Enable IP allowlist middleware |

#### Compliance

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `GDPR_RETENTION_DAYS` | No | `365` | Data retention period |
| `AUDIT_LOG_RETENTION_DAYS` | No | `2555` | Audit log retention (7 years) |

#### Frontend

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | No | `https://parwa.ai` | Public API URL for frontend |
| `NEXT_PUBLIC_PADDLE_KEY` | No | `pk_live_...` | Paddle public key |
| `FRONTEND_URL` | No | `https://parwa.ai` | Frontend URL (CORS) |

### 1.3 Server Directory Structure

```bash
/srv/parwa/
├── docker-compose.prod.yml    # Production compose
├── .env.prod                  # Production env vars (chmod 600)
├── nginx/
│   ├── nginx.conf             # Production nginx config
│   ├── ssl/                   # SSL certificates (chmod 600)
│   │   ├── fullchain.pem
│   │   ├── privkey.pem
│   │   └── chain.pem
│   └── ssl-setup.sh           # SSL certificate setup script
├── scripts/
│   ├── backup.sh              # Database backup
│   ├── restore.sh             # Database restore
│   └── wal_archive.sh         # WAL archiving
├── monitoring/
│   ├── prometheus.yml
│   ├── alertmanager/
│   │   └── alertmanager.yml
│   ├── alerting/
│   │   └── rules.yml
│   └── grafana/
│       └── provisioning/
│           ├── datasources/
│           │   └── datasource.yml
│           └── dashboards/
│               └── dashboards.yml
├── secrets/                   # RSA keys (chmod 600)
│   ├── private.pem
│   └── public.pem
└── backups/                   # Database backups
```

---

## 2. Deployment

### 2.1 First-Time Deployment

```bash
# 1. Clone the repository
git clone https://github.com/abhaythakur754-0/parwa.git /srv/parwa
cd /srv/parwa

# 2. Create production environment file
cp .env.prod.example .env.prod
chmod 600 .env.prod

# 3. Edit environment variables (set ALL required vars)
nano .env.prod
# At minimum set: ENVIRONMENT, SECRET_KEY, JWT_SECRET_KEY,
# DATABASE_URL, REDIS_PASSWORD, DATA_ENCRYPTION_KEY

# 4. Generate RSA keys for JWT (if using RS256)
python3 scripts/generate_rsa_keys.py --output-dir secrets/
chmod 600 secrets/*.pem

# 5. Build Docker images
docker compose -f docker-compose.prod.yml build

# 6. Run database migrations
docker compose -f docker-compose.prod.yml run --rm backend \
  alembic -c /app/database/alembic.ini upgrade head

# 7. Verify database connectivity
docker compose -f docker-compose.prod.yml run --rm backend \
  python -c "from database.base import engine; from sqlalchemy import text; print(engine.connect().execute(text('SELECT 1')).scalar())"

# 8. Start all services
docker compose -f docker-compose.prod.yml up -d

# 9. Verify health
curl -sf http://localhost:8000/health | jq .
curl -sf http://localhost:8000/api/health/ready | jq .
curl -sf http://localhost:8000/api/health/live | jq .

# 10. Verify all containers are healthy
docker compose -f docker-compose.prod.yml ps
```

### 2.2 Subsequent Deployments

```bash
cd /srv/parwa

# 1. Pull latest code
git pull origin main

# 2. Rebuild images with new version
export VERSION=$(cat VERSION 2>/dev/null || echo "latest")
docker compose -f docker-compose.prod.yml build \
  --build-arg VERSION=${VERSION}

# 3. Run any new database migrations
docker compose -f docker-compose.prod.yml run --rm backend \
  alembic -c /app/database/alembic.ini upgrade head

# 4. Rolling restart (zero-downtime)
# Backend and worker restart with health check verification
docker compose -f docker-compose.prod.yml up -d \
  --no-deps --build backend
docker compose -f docker-compose.prod.yml up -d \
  --no-deps --build worker

# Wait for health checks to pass before restarting frontend
sleep 30
docker compose -f docker-compose.prod.yml up -d \
  --no-deps --build frontend

# 5. Verify deployment
docker compose -f docker-compose.prod.yml ps
curl -sf https://parwa.ai/health
curl -sf https://parwa.ai/api/health/ready | jq .
```

### 2.3 Docker Image Tagging Strategy

| Tag | Purpose | Example |
|-----|---------|---------|
| `latest` | Latest main branch build | `parwa-backend:latest` |
| `v1.2.3` | Semantic version release | `parwa-backend:v1.2.3` |
| `sha-abc1234` | Git SHA for traceability | `parwa-backend:sha-abc1234` |
| `staging` | Staging environment build | `parwa-backend:staging` |

```bash
# Build with version tag
docker build --build-arg VERSION=v1.2.3 \
  -t parwa-backend:v1.2.3 \
  -t parwa-backend:latest \
  -f infra/docker/backend.Dockerfile .

# Tag specific commit
docker tag parwa-backend:latest parwa-backend:sha-$(git rev-parse --short HEAD)
```

### 2.4 Zero-Downtime Deployment Strategy

PARWA uses rolling updates with health checks:

1. **Nginx** routes traffic to healthy upstreams only
2. **Docker health checks** on every container (30s interval, 3 retries)
3. **Database migrations** run before app restart (backward-compatible)
4. **Worker restart** happens before backend (prevents orphaned tasks)

```bash
# Step 1: Restart worker first (processes remaining tasks, then stops)
docker compose -f docker-compose.prod.yml stop worker
docker compose -f docker-compose.prod.yml up -d --no-deps --build worker
# Wait for worker health: docker compose -f docker-compose.prod.yml ps worker

# Step 2: Restart backend (old instance handles traffic until new is healthy)
docker compose -f docker-compose.prod.yml up -d --no-deps --build backend
# Wait for backend health: docker compose -f docker-compose.prod.yml ps backend

# Step 3: Restart frontend (new backend is already handling API traffic)
docker compose -f docker-compose.prod.yml up -d --no-deps --build frontend
```

### 2.5 Database Migration Procedure

PARWA uses Alembic for database migrations. All migrations are in `database/alembic/versions/`.

```bash
# Run all pending migrations
docker compose -f docker-compose.prod.yml exec backend \
  alembic -c /app/database/alembic.ini upgrade head

# Check current migration version
docker compose -f docker-compose.prod.yml exec backend \
  alembic -c /app/database/alembic.ini current

# View migration history
docker compose -f docker-compose.prod.yml exec backend \
  alembic -c /app/database/alembic.ini history --verbose

# Rollback ONE migration step
docker compose -f docker-compose.prod.yml exec backend \
  alembic -c /app/database/alembic.ini downgrade -1

# Rollback to specific migration
docker compose -f docker-compose.prod.yml exec backend \
  alembic -c /app/database/alembic.ini downgrade <revision_id>

# Generate a new migration (development only)
alembic -c database/alembic.ini revision --autogenerate -m "description"
```

**Current migration chain (as of latest):**
```
001_initial_schema → 002_ticketing_tables → 003_ai_pipeline_tables →
004_integration_tables → 005_audit_billing_tables → 006_analytics_onboarding_tables →
007_remaining_gap_tables → 008_technique_tables → 009_billing_extended_tables →
010_onboarding_extended → 011_phase3_variant_engine → 012_jarvis_system →
015_business_email_otp → 016_email_channel_tables → 017_outbound_email →
018_email_delivery_events → 019_ooo_bounce_tables → 020_jarvis_cc_tables →
021_fix_session_ticket_fk → 022_enable_rls → 023_paddle_reconciliation
```

---

## 3. SSL/TLS Configuration

### 3.1 Certificate Management with Let's Encrypt

PARWA uses Let's Encrypt with certbot for free, auto-renewing SSL certificates.

```bash
# Run the SSL setup script (first time only)
cd /srv/parwa
sudo bash nginx/ssl-setup.sh

# With custom configuration
sudo DOMAIN=parwa.ai \
     EMAIL=admin@parwa.ai \
     SSL_DIR=/srv/parwa/nginx/ssl \
     bash nginx/ssl-setup.sh

# Test with Let's Encrypt staging (avoids rate limits)
sudo STAGING=true bash nginx/ssl-setup.sh
```

### 3.2 ssl-setup.sh Script Reference

The script (`nginx/ssl-setup.sh`) performs these steps:

1. **Prerequisites check** — Verifies certbot, nginx, root access
2. **DH parameters generation** — 2048-bit Diffie-Hellman params (`/etc/nginx/ssl/dhparam.pem`)
3. **Certificate obtainment** — certbot webroot authentication
4. **Nginx configuration** — Tests and reloads nginx
5. **Auto-renewal setup** — cron job at 00:00 and 12:00 UTC
6. **SSL verification** — Certificate/key match, expiry check, HTTPS test

### 3.3 SSL Labs A+ Verification

```bash
# 1. Verify SSL configuration locally
openssl s_client -connect parwa.ai:443 -tls1_3 </dev/null 2>/dev/null | \
  openssl x509 -noout -dates -issuer -subject

# 2. Test HTTPS connection
curl -vI https://parwa.ai 2>&1 | head -20

# 3. Verify certificate chain
openssl s_client -connect parwa.ai:443 -showcerts </dev/null 2>/dev/null | \
  grep -E "subject=|issuer=|Verify return"

# 4. Check TLS protocols
openssl s_client -connect parwa.ai:443 -tls1_2 </dev/null 2>&1 | grep "Protocol"
openssl s_client -connect parwa.ai:443 -tls1_3 </dev/null 2>&1 | grep "Protocol"

# 5. Run SSL Labs test (external)
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=parwa.ai
# Target: A+ rating
```

**Expected SSL profile:**
- TLS 1.2 and TLS 1.3 only (no SSLv3, TLS 1.0, TLS 1.1)
- Mozilla Modern cipher suite
- HSTS: `max-age=63072000; includeSubDomains; preload` (2 years)
- OCSP Stapling enabled
- DH parameters: 2048-bit minimum

### 3.4 Certificate Renewal Automation

Certificates are auto-renewed via cron:

```bash
# View renewal cron
cat /etc/cron.d/parwa-ssl-renewal

# Manual renewal test (dry run)
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew --force-renewal

# Check certificate expiry
openssl x509 -noout -enddate -in /srv/parwa/nginx/ssl/fullchain.pem

# Verify renewal log
tail -20 /var/log/parwa/ssl-renewal.log
```

### 3.5 Emergency Certificate Rotation

```bash
# If certificate is compromised or expiring imminently:

# 1. Force immediate renewal
sudo certbot certonly --force-renewal \
  --domain parwa.ai \
  --domain www.parwa.ai \
  --email admin@parwa.ai \
  --webroot \
  --webroot-path /var/www/certbot

# 2. Copy new certificate to nginx SSL directory
sudo cp -L /etc/letsencrypt/live/parwa.ai/fullchain.pem \
  /srv/parwa/nginx/ssl/fullchain.pem
sudo cp -L /etc/letsencrypt/live/parwa.ai/privkey.pem \
  /srv/parwa/nginx/ssl/privkey.pem
sudo chmod 600 /srv/parwa/nginx/ssl/privkey.pem

# 3. Test and reload nginx
sudo nginx -t && sudo nginx -s reload

# 4. Verify new certificate
openssl s_client -connect parwa.ai:443 </dev/null 2>/dev/null | \
  openssl x509 -noout -enddate
```

---

## 4. Monitoring & Alerting

### 4.1 Grafana Access

| Property | Value |
|----------|-------|
| **URL** | `https://monitoring.parwa.ai` (or `http://<server-ip>:3000`) |
| **Default User** | `admin` |
| **Default Password** | Change immediately on first login |

**Change default credentials:**
```bash
# Via docker exec
docker compose -f docker-compose.prod.yml exec grafana \
  grafana-cli admin reset-admin-password <new-strong-password>
```

### 4.2 Key Dashboards

| Dashboard | Description | Key Panels |
|-----------|-------------|------------|
| **System Overview** | High-level system health | Container status, CPU, memory, network I/O |
| **API Performance** | Backend HTTP metrics | P50/P95/P99 latency, 5xx rate, request throughput |
| **Celery Queues** | Background job health | Queue depth per queue, task success/failure rate, worker count |
| **AI Pipeline Metrics** | LLM pipeline performance | Tokens used, pipeline duration, model fallback rate |

### 4.3 Prometheus Targets Verification

```bash
# Check Prometheus targets are being scraped
curl -sf http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastScrape: .lastScrape}'

# Expected targets:
# - parwa_backend (backend:8000)
# - parwa_celery (worker:8080)
# - redis (redis-exporter:9121)
# - postgresql (postgres-exporter:9187)
# - node (node-exporter:9100)

# Check Prometheus is receiving metrics
curl -sf http://localhost:9090/api/v1/query?query=up | jq .
```

### 4.4 AlertManager Configuration

AlertManager runs at `alertmanager:9093` inside the Docker network.

**Receivers:**

| Receiver | Channels | Trigger |
|----------|----------|---------|
| `default-receiver` | Webhook to backend | Any unmatched alert |
| `critical-receiver` | Webhook + Slack + Email | `severity: critical` |
| `warning-receiver` | Email only | `severity: warning` |

**Alert routing rules:**
- Critical alerts: Immediate (group_wait: 0s), repeat every 1 hour
- Warning alerts: 10s group wait, repeat every 4 hours
- Inhibition: Critical alerts suppress warnings for same alertname/service

### 4.5 Custom Alert Thresholds

| Alert | Severity | Threshold | Duration |
|-------|----------|-----------|----------|
| PostgreSQL unhealthy | Critical | Connection fails | 1 min |
| Redis unhealthy | Critical | PING fails | 1 min |
| Celery queue depth high | Warning | > 500 tasks | 5 min |
| Celery queue depth critical | Critical | > 5,000 tasks | 1 min |
| Celery task failure rate | Warning | > 10% failures | 5 min |
| API 5xx error rate | Warning | > 5% of requests | 5 min |
| API P95 latency | Warning | > 2 seconds | 5 min |
| API P99 latency | Critical | > 5 seconds | 2 min |
| DB pool exhausted | Warning | > 90% pool used | 5 min |
| DB slow queries | Warning | P95 > 1 second | 5 min |
| Redis slow commands | Warning | P95 > 100ms | 5 min |
| System degraded | Warning | Any subsystem degraded | 5 min |
| Disk space low | Warning | < 20% free | Immediate |
| Disk space critical | Critical | < 5% free | Immediate |

### 4.6 Health Check Endpoints

```bash
# Liveness (always 200 if process is running)
curl -sf https://parwa.ai/api/health/live

# Readiness (200 only when all critical subsystems healthy)
curl -sf https://parwa.ai/api/health/ready | jq .

# Full health (detailed subsystem status, cached 10s)
curl -sf https://parwa.ai/api/health | jq .
```

**Subsystem health statuses:**
- `healthy` — Operating normally
- `degraded` — Functional but impaired (e.g., pool > 80%, memory > 80%)
- `unhealthy` — Not operational

**Critical subsystems** (readiness gate): PostgreSQL, Redis

**Non-critical subsystems**: Celery, Socket.io, Paddle, Brevo, Twilio, disk space

---

## 5. Rollback Procedures

### 5.1 Application Rollback

```bash
# 1. Identify the previous working version
docker images parwa-backend --format "{{.Tag}}\t{{.CreatedAt}}"
git log --oneline -5

# 2. Checkout the previous commit
git checkout <previous-commit-sha>

# 3. Rebuild and restart with previous version
docker compose -f docker-compose.prod.yml up -d \
  --no-deps --build backend worker frontend

# 4. Verify rollback
curl -sf https://parwa.ai/api/health/ready | jq .
docker compose -f docker-compose.prod.yml ps

# 5. If using specific image tag
docker tag parwa-backend:v1.2.2 parwa-backend:rollback
docker compose -f docker-compose.prod.yml up -d \
  --no-deps backend worker frontend
```

### 5.2 Database Rollback

```bash
# Option A: Alembic downgrade (one step)
docker compose -f docker-compose.prod.yml exec backend \
  alembic -c /app/database/alembic.ini downgrade -1

# Option B: Alembic downgrade (to specific revision)
docker compose -f docker-compose.prod.yml exec backend \
  alembic -c /app/database/alembic.ini downgrade <revision_id>

# Option C: Full backup restore (nuclear option)
# Step 1: Stop backend and worker
docker compose -f docker-compose.prod.yml stop backend worker

# Step 2: Restore from backup
docker compose -f docker-compose.prod.yml exec db \
  bash /app/scripts/restore.sh /backups/parwa_backup_YYYYMMDD_HHMMSS.sql.gz

# Step 3: Verify data integrity
docker compose -f docker-compose.prod.yml exec db \
  psql -U parwa -d parwa_db -c "SELECT count(*) FROM companies;"

# Step 4: Restart all services
docker compose -f docker-compose.prod.yml up -d
```

### 5.3 SSL Certificate Rollback

```bash
# If new certificate causes issues, restore from Let's Encrypt archive
sudo cp /etc/letsencrypt/archive/parwa.ai/fullchain1.pem \
  /srv/parwa/nginx/ssl/fullchain.pem
sudo cp /etc/letsencrypt/archive/parwa.ai/privkey1.pem \
  /srv/parwa/nginx/ssl/privkey.pem
sudo chmod 600 /srv/parwa/nginx/ssl/privkey.pem
sudo nginx -t && sudo nginx -s reload
```

### 5.4 Configuration Rollback

```bash
# Rollback .env.prod to previous version
cp .env.prod .env.prod.broken
cp .env.prod.backup .env.prod
chmod 600 .env.prod

# Restart services with restored config
docker compose -f docker-compose.prod.yml up -d

# Rollback nginx config
sudo cp /etc/nginx/nginx.conf.backup /etc/nginx/nginx.conf
sudo nginx -t && sudo nginx -s reload
```

### 5.5 Emergency Rollback (< 5 Minutes)

```bash
# ONE-COMMAND EMERGENCY ROLLBACK
# Restores previous git commit, rebuilds, and restarts
cd /srv/parwa && \
git stash && \
git checkout HEAD~1 && \
docker compose -f docker-compose.prod.yml up -d \
  --no-deps --build backend worker frontend && \
echo "EMERGENCY ROLLBACK COMPLETE at $(date)" && \
curl -sf https://parwa.ai/api/health/ready | jq .

# If database migration is the issue, also downgrade:
docker compose -f docker-compose.prod.yml exec backend \
  alembic -c /app/database/alembic.ini downgrade -1

# If all else fails, full database restore from latest backup:
LATEST_BACKUP=$(ls -t /backups/parwa_backup_*.sql.gz | head -1)
docker compose -f docker-compose.prod.yml exec db \
  bash /app/scripts/restore.sh "${LATEST_BACKUP}"
```

---

## 6. Troubleshooting

### 6.1 Backend Won't Start

**Symptoms:** Container exits immediately or health check fails.

```bash
# Check container logs
docker compose -f docker-compose.prod.yml logs --tail=100 backend

# Check if the container is running
docker compose -f docker-compose.prod.yml ps backend

# Check for port conflicts
ss -tlnp | grep 8000

# Common causes:
# 1. Missing/wrong environment variables
docker compose -f docker-compose.prod.yml exec backend env | grep -E "DATABASE_URL|REDIS_URL|ENVIRONMENT"

# 2. Database connectivity
docker compose -f docker-compose.prod.yml exec backend \
  python -c "from database.base import engine; engine.connect()"

# 3. Alembic migration failure
docker compose -f docker-compose.prod.yml exec backend \
  alembic -c /app/database/alembic.ini current

# 4. Redis connectivity
docker compose -f docker-compose.prod.yml exec backend \
  python -c "import asyncio; from app.core.redis import get_redis; print(asyncio.run(get_redis()).ping())"
```

### 6.2 Database Connection Pool Exhausted

**Symptoms:** `TimeoutError: QueuePool limit of size X reached`, slow API responses.

```bash
# Check pool usage via health endpoint
curl -sf https://parwa.ai/api/health | jq '.subsystems.postgresql.details'

# Check active connections
docker compose -f docker-compose.prod.yml exec db \
  psql -U parwa -d parwa_db -c \
  "SELECT count(*) as connections, state FROM pg_stat_activity GROUP BY state;"

# Check for long-running queries
docker compose -f docker-compose.prod.yml exec db \
  psql -U parwa -d parwa_db -c \
  "SELECT pid, state, query, now() - query_start AS duration \
   FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC LIMIT 10;"

# Check for locked tables
docker compose -f docker-compose.prod.yml exec db \
  psql -U parwa -d parwa_db -c \
  "SELECT relation::regclass, mode, pid FROM pg_locks WHERE NOT granted;"

# Kill long-running queries if needed
docker compose -f docker-compose.prod.yml exec db \
  psql -U parwa -d parwa_db -c "SELECT pg_cancel_backend(<pid>);"
```

**Fix:** Increase pool size in DATABASE_URL: `?pool_size=20&max_overflow=10`

### 6.3 Redis Connection Failures

**Symptoms:** Cache misses, Celery tasks not queued, health check shows Redis unhealthy.

```bash
# Check Redis is running
docker compose -f docker-compose.prod.yml ps redis

# Check Redis logs
docker compose -f docker-compose.prod.yml logs --tail=50 redis

# Test Redis connectivity
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a "${REDIS_PASSWORD}" ping

# Check Redis memory usage
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a "${REDIS_PASSWORD}" info memory | grep -E "used_memory|maxmemory"

# Check Redis key count
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a "${REDIS_PASSWORD}" dbsize

# Check for blocked clients
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a "${REDIS_PASSWORD}" info clients | grep blocked
```

**Common fixes:**
- Verify `REDIS_PASSWORD` matches between backend and Redis
- Check network connectivity between backend and Redis containers
- Clear memory if maxmemory reached: `redis-cli -a <pass> MEMORY PURGE`

### 6.4 Celery Workers Not Processing

**Symptoms:** Tasks stuck in queue, no task execution.

```bash
# Check worker status
docker compose -f docker-compose.prod.yml ps worker

# Check worker logs
docker compose -f docker-compose.prod.yml logs --tail=100 worker

# Check active workers
docker compose -f docker-compose.prod.yml exec backend \
  python -c "
from app.tasks.celery_app import app
inspect = app.control.inspect()
print('Active workers:', list((inspect.active() or {}).keys()))
print('Registered:', list((inspect.registered() or {}).keys()))
"

# Check queue depths
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a "${REDIS_PASSWORD}" -n 1 llen default
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a "${REDIS_PASSWORD}" -n 1 llen ai_heavy
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a "${REDIS_PASSWORD}" -n 1 llen email

# Check for revoked/failed tasks
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a "${REDIS_PASSWORD}" -n 2 keys "celery-task-meta-*" | wc -l

# Restart worker
docker compose -f docker-compose.prod.yml restart worker
```

**Common fixes:**
- Broker URL mismatch — verify `CELERY_BROKER_URL` in `.env.prod`
- Worker crashed — check logs for OOM or exception
- Beat scheduler not running — ensure beat process is started

### 6.5 LLM API Failures

**Symptoms:** AI responses timing out, fallback to generic responses, Smart Router errors.

```bash
# Check Smart Router health
curl -sf https://parwa.ai/api/health | jq '.subsystems.external_*'

# Check LLM provider status pages:
# Google AI: https://status.cloud.google.com
# Groq: https://status.groq.com
# OpenRouter: https://openrouter.ai/status

# Check API keys are configured
docker compose -f docker-compose.prod.yml exec backend \
  python -c "
from app.config import get_settings
s = get_settings()
print('Primary:', s.LLM_PRIMARY_PROVIDER, '→ key set:', bool(s.GOOGLE_AI_API_KEY))
print('Fallback:', s.LLM_FALLBACK_PROVIDER, '→ key set:', bool(s.GROQ_API_KEY))
"

# Check rate limit status in Redis (if Redis health tracker active)
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a "${REDIS_PASSWORD}" keys "health:*"
```

### 6.6 High Memory Usage

**Symptoms:** Containers being killed by OOM, system swap activity.

```bash
# Check container resource usage
docker stats --no-stream

# Check system memory
free -h
df -h /

# Check specific container memory
docker compose -f docker-compose.prod.yml exec backend \
  python -c "import resource; print(f'Memory: {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB')"

# Restart memory-heavy containers
docker compose -f docker-compose.prod.yml restart backend worker

# Check for memory leaks (restart and monitor)
docker compose -f docker-compose.prod.yml restart --timeout 30 backend
docker stats --no-stream backend worker
```

### 6.7 SSL Certificate Errors

**Symptoms:** Browser warnings, API client SSL errors, `curl: (60) SSL certificate problem`.

```bash
# Check certificate expiry
openssl x509 -noout -enddate -in /srv/parwa/nginx/ssl/fullchain.pem

# Verify certificate chain
openssl verify -CAfile /srv/parwa/nginx/ssl/chain.pem \
  /srv/parwa/nginx/ssl/fullchain.pem

# Check certificate and key match
CERT_MOD=$(openssl x509 -noout -modulus -in /srv/parwa/nginx/ssl/fullchain.pem | openssl md5)
KEY_MOD=$(openssl rsa -noout -modulus -in /srv/parwa/nginx/ssl/privkey.pem | openssl md5)
[ "$CERT_MOD" = "$KEY_MOD" ] && echo "MATCH" || echo "MISMATCH"

# Check file permissions
ls -la /srv/parwa/nginx/ssl/
# fullchain.pem should be 644, privkey.pem should be 600

# Check nginx SSL configuration
sudo nginx -t 2>&1 | grep -i ssl
```

### 6.8 Slow API Responses

**Symptoms:** P95 latency > 2s, API timeouts.

```bash
# Check nginx upstream response times
docker compose -f docker-compose.prod.yml logs --tail=20 nginx | grep upstream

# Check nginx buffers
docker compose -f docker-compose.prod.yml exec nginx \
  cat /etc/nginx/nginx.conf | grep -A5 proxy_buffer

# Check for slow database queries
docker compose -f docker-compose.prod.yml exec db \
  psql -U parwa -d parwa_db -c \
  "SELECT query, mean_exec_time, calls FROM pg_stat_statements \
   ORDER BY mean_exec_time DESC LIMIT 10;"

# Check Celery backlog (tasks blocking API)
curl -sf https://parwa.ai/api/health | jq '.subsystems.celery_queues.details'

# Check Redis response time
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a "${REDIS_PASSWORD}" --latency

# Profile a specific endpoint
curl -w "\n\nTime: %{time_total}s\nDNS: %{time_namelookup}s\nConnect: %{time_connect}s\nTTFB: %{time_starttransfer}s\n" \
  -o /dev/null -s https://parwa.ai/api/v1/tickets
```

---

## 7. Maintenance

### 7.1 Database Backup Verification

```bash
# Run a backup
cd /srv/parwa
PGHOST=db PGUSER=parwa PGPASSWORD=<pass> PGDATABASE=parwa_db \
  BACKUP_DIR=/backups ./scripts/backup.sh

# Verify latest backup
LATEST=$(ls -t /backups/parwa_backup_*.sql.gz | head -1)
./scripts/backup.sh --verify "${LATEST}"

# Check backup size (should be proportional to data)
ls -lh /backups/parwa_backup_*.sql.gz

# Verify backup cron is configured
crontab -l | grep backup
# or
systemctl list-timers | grep backup

# Recommended: Weekly restore test to a scratch database
docker compose -f docker-compose.prod.yml exec db \
  createdb -U parwa parwa_db_test_restore
PGDATABASE=parwa_db_test_restore \
  ./scripts/backup.sh --restore "${LATEST}"
docker compose -f docker-compose.prod.yml exec db \
  dropdb -U parwa parwa_db_test_restore
```

### 7.2 Log Rotation and Cleanup

```bash
# Docker container logs (configure in daemon.json)
cat /etc/docker/daemon.json
# {
#   "log-driver": "json-file",
#   "log-opts": {
#     "max-size": "100m",
#     "max-file": "5"
#   }
# }

# Nginx logs (logrotate)
cat /etc/logrotate.d/nginx
# /var/log/nginx/*.log {
#   daily
#   missingok
#   rotate 14
#   compress
#   delaycompress
#   notifempty
#   create 0640 nginx adm
#   sharedscripts
#   postrotate
#     [ -f /var/run/nginx.pid ] && kill -USR1 $(cat /var/run/nginx.pid)
#   endscript
# }

# Force rotate all logs
sudo logrotate -f /etc/logrotate.conf

# Application logs (inside container)
docker compose -f docker-compose.prod.yml exec backend \
  find /var/log -name "*.log" -mtime +30 -ls

# Celery worker logs
docker compose -f docker-compose.prod.yml logs --since 24h worker | wc -l
```

### 7.3 Docker Image Cleanup

```bash
# Remove dangling images
docker image prune -f

# Remove all unused images (be careful)
docker image prune -a -f

# Remove unused volumes (be very careful)
docker volume prune -f

# Full system prune (removes everything not in use)
docker system prune -f

# Check disk usage
docker system df

# Remove old parwa images (keep last 3 versions)
docker images parwa-backend --format "{{.Tag}}\t{{.CreatedAt}}" | \
  sort -k2 | head -n -3 | awk '{print $1}' | \
  xargs -r docker rmi

# Remove build cache
docker builder prune -f --filter "until=168h"  # Older than 7 days
```

### 7.4 Monitoring Disk Usage

```bash
# Overall disk usage
df -h /

# Docker disk usage
docker system df -v

# Largest directories
du -sh /srv/parwa/*/ 2>/dev/null | sort -rh

# PostgreSQL data directory
docker compose -f docker-compose.prod.yml exec db \
  du -sh /var/lib/postgresql/data

# Redis persistence
docker compose -f docker-compose.prod.yml exec redis \
  du -sh /data

# Backup directory
du -sh /backups/

# Set up disk usage alert (already configured in health checks)
# Disk space < 20% → degraded, < 5% → unhealthy
```

### 7.5 Security Updates

```bash
# Check for base image updates
docker pull postgres:15-alpine
docker pull redis:7-alpine

# Rebuild with updated base images
docker compose -f docker-compose.prod.yml build --pull

# Python package security audit
docker compose -f docker-compose.prod.yml exec backend \
  pip audit --desc 2>/dev/null || pip install pip-audit && pip audit

# npm audit for frontend
docker compose -f docker-compose.prod.yml exec frontend \
  npm audit --production

# Check for CVEs in running containers
docker scout cves parwa_backend:latest 2>/dev/null || \
  echo "docker scout not available — use manual audit"

# Update system packages (if using custom Dockerfiles)
docker compose -f docker-compose.prod.yml build --no-cache backend
```

---

## 8. Security Checklist

Run this checklist **weekly** and before every deployment.

### 8.1 Environment Security

- [ ] **Environment variables not in git** — Verify `.env.prod` is in `.gitignore`
  ```bash
  git ls-files | grep -E "\.env\.prod$" && echo "FAIL: .env.prod tracked!" || echo "PASS"
  ```

- [ ] **No default secrets in production**
  ```bash
  docker compose -f docker-compose.prod.yml exec backend \
    python -c "
from app.config import get_settings
s = get_settings()
assert not s.SECRET_KEY.startswith('dev-'), 'SECRET_KEY is default!'
assert not s.JWT_SECRET_KEY.startswith('dev-'), 'JWT_SECRET_KEY is default!'
assert len(s.DATA_ENCRYPTION_KEY) == 32, 'DATA_ENCRYPTION_KEY wrong length!'
assert s.REDIS_PASSWORD != '', 'REDIS_PASSWORD is empty!'
print('PASS: No default secrets detected')
"
  ```

- [ ] **File permissions correct**
  ```bash
  stat -c "%a %n" .env.prod  # Should be 600
  stat -c "%a %n" secrets/private.pem  # Should be 600
  stat -c "%a %n" nginx/ssl/privkey.pem  # Should be 600
  ```

### 8.2 SSL/TLS

- [ ] **SSL certificates valid** (not expired, not < 30 days from expiry)
  ```bash
  EXPIRY=$(openssl x509 -noout -enddate -in nginx/ssl/fullchain.pem | cut -d= -f2)
  EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s)
  NOW_EPOCH=$(date +%s)
  DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))
  [ "$DAYS_LEFT" -gt 30 ] && echo "PASS: ${DAYS_LEFT} days remaining" || echo "FAIL: Only ${DAYS_LEFT} days remaining"
  ```

- [ ] **HTTPS redirect working**
  ```bash
  curl -sf -o /dev/null -w "%{redirect_url}" http://parwa.ai/health | grep -q "https://" && echo "PASS" || echo "FAIL"
  ```

- [ ] **HSTS header present**
  ```bash
  curl -sI https://parwa.ai | grep -i "strict-transport-security" | grep -q "max-age=63072000" && echo "PASS" || echo "FAIL"
  ```

### 8.3 Authentication & Authorization

- [ ] **Database passwords rotated** (quarterly)
  - Document rotation date: ____________
  - Verify password complexity: min 24 characters, mixed case + numbers + symbols

- [ ] **API keys rotated** (monthly)
  - Paddle keys: ____________
  - Brevo key: ____________
  - Twilio key: ____________
  - Sentry DSN: ____________

- [ ] **JWT keys valid**
  ```bash
  docker compose -f docker-compose.prod.yml exec backend \
    python -c "
from app.core.auth import create_access_token, verify_access_token
token = create_access_token({'sub': 'test', 'company_id': 'test'})
payload = verify_access_token(token)
assert payload['sub'] == 'test'
print('PASS: JWT create/verify works')
"
  ```

### 8.4 Error Tracking

- [ ] **Sentry DSN configured**
  ```bash
  docker compose -f docker-compose.prod.yml exec backend \
    python -c "
from app.config import get_settings
s = get_settings()
assert s.SENTRY_DSN != '', 'Sentry DSN not configured!'
print('PASS: Sentry DSN configured')
"
  ```

- [ ] **Sentry receiving events** — Check Sentry dashboard for recent errors

### 8.5 Firewall & Network

- [ ] **Only required ports exposed** (80, 443)
  ```bash
  sudo ufw status numbered
  # Expected: 80/tcp ALLOW, 443/tcp ALLOW
  # Internal ports (5432, 6379, 8000, 3000) NOT exposed to 0.0.0.0
  ```

- [ ] **No host port binding for internal services**
  ```bash
  docker compose -f docker-compose.prod.yml config | \
    grep -A3 "ports:" | \
    grep -v "127.0.0.1" | \
    grep -E "5432|6379|8000|3000" && echo "FAIL: Internal ports exposed!" || echo "PASS"
  ```

### 8.6 Container Security

- [ ] **Non-root containers verified**
  ```bash
  docker compose -f docker-compose.prod.yml exec backend whoami
  docker compose -f docker-compose.prod.yml exec frontend whoami
  docker compose -f docker-compose.prod.yml exec worker whoami
  # None should return "root"
  ```

- [ ] **Resource limits configured**
  ```bash
  docker compose -f docker-compose.prod.yml config | \
    grep -E "deploy|mem_limit|cpus" | head -20
  ```

- [ ] **No sensitive data in container logs**
  ```bash
  docker compose -f docker-compose.prod.yml logs --tail=500 backend 2>&1 | \
    grep -iE "(password|secret|token|api_key).*=.{8,}" | \
    grep -v "*****" | \
    grep -v "masked" && echo "FAIL: Possible secrets in logs!" || echo "PASS"
  ```

---

## Appendix A: Quick Reference Commands

```bash
# Full system status
docker compose -f docker-compose.prod.yml ps
docker stats --no-stream
curl -sf https://parwa.ai/api/health | jq .

# Restart everything
docker compose -f docker-compose.prod.yml restart

# View logs (all services, last 50 lines)
docker compose -f docker-compose.prod.yml logs --tail=50

# Database backup
PGPASSWORD=<pass> ./scripts/backup.sh

# Database migration
docker compose -f docker-compose.prod.yml exec backend \
  alembic -c /app/database/alembic.ini upgrade head

# SSL renewal check
sudo certbot certificates

# Prometheus query
curl -sf "http://localhost:9090/api/v1/query?query=up" | jq .

# Force clean restart
docker compose -f docker-compose.prod.yml down && \
docker compose -f docker-compose.prod.yml up -d
```

## Appendix B: Escalation Contacts

| Role | Contact | Escalation Time |
|------|---------|-----------------|
| On-Call Engineer | <on-call@parwa.ai> | Immediate |
| Engineering Lead | <lead@parwa.ai> | < 30 min |
| Infrastructure | <infra@parwa.ai> | < 1 hour |
| Security | <security@parwa.ai> | < 15 min (security incidents) |

## Appendix C: Incident Response Flow

```
1. Alert fires (Slack #alerts / email)
2. Acknowledge alert in AlertManager
3. Check health endpoint: curl https://parwa.ai/api/health
4. Identify affected subsystem from health check
5. Follow relevant troubleshooting section (§6.x)
6. If unresolvable in 15 min → escalate to Engineering Lead
7. If data loss risk → consider emergency rollback (§5.5)
8. After resolution → run Security Checklist (§8)
9. Post incident → document in runbook updates
```
