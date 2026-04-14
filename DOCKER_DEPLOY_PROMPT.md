---
Task: Deploy PARWA AI Customer Support SaaS to production using Docker Compose

## Context
PARWA is a full-stack AI customer support SaaS with:
- **Backend**: FastAPI (Python 3.12) at `/backend/` 
- **Frontend**: Next.js 15 at `/frontend/` (or `/src/` — check both)
- **Database**: PostgreSQL 15 with pgvector extension
- **Cache/Queue**: Redis 7
- **Worker**: Celery async task processor
- **Monitoring**: Prometheus + Grafana + Alertmanager
- **Reverse Proxy**: Nginx with SSL termination
- **MCP Server**: AI tool server for agent integration

## Project Structure
```
parwa/
├── backend/              # FastAPI application
│   ├── app/              # Application code (api/, services/, core/, models/)
│   ├── tests/            # Backend tests
│   └── requirements.txt  # Python dependencies
├── frontend/             # Next.js application (or src/ in some branches)
│   └── ...               # Next.js 15 app
├── database/             # Alembic migrations + schema
│   └── alembic/
├── nginx/                # Nginx config + SSL
├── monitoring/           # Prometheus, Grafana configs
├── infra/docker/         # Dockerfiles (backend.Dockerfile, worker.Dockerfile, etc.)
├── docker-compose.prod.yml  # Production compose (already written)
└── .env                  # Environment variables (already configured)
```

## What to Deploy

### 1. Create Missing Dockerfiles

**backend.Dockerfile** (create at `infra/docker/backend.Dockerfile`):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY database/ /app/database/
COPY shared/ /app/shared/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**worker.Dockerfile** (create at `infra/docker/worker.Dockerfile`):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY database/ /app/database/
COPY shared/ /app/shared/
CMD ["celery", "-A", "app.tasks.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
```

**frontend.Dockerfile** (create at `infra/docker/frontend.Dockerfile`):
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

**mcp.Dockerfile** (create at `infra/docker/mcp.Dockerfile`):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY database/ /app/database/
COPY shared/ /app/shared/
EXPOSE 5100
CMD ["uvicorn", "app.mcp_server:app", "--host", "0.0.0.0", "--port", "5100"]
```

### 2. Create Missing Monitoring Configs

**monitoring/prometheus.yml**:
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'parwa-backend'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['backend:8000']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: 'parwa-backend'

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

**monitoring/alertmanager/alertmanager.yml**:
```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 5m
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical'

receivers:
  - name: 'default'
  - name: 'critical'
```

**monitoring/alerting/rules.yml**:
```yaml
groups:
  - name: parwa_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"

      - alert: HighLatency
        expr: histogram_quantile(0.95, http_request_duration_seconds_bucket) > 2
        for: 5m
        labels:
          severity: warning
```

### 3. Create `.env.prod` from `.env` (copy the existing .env — already configured with all API keys)

### 4. Create Database Init Script
Create `database/schema.sql` with:
```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### 5. Deploy Command
```bash
# From parwa/ directory:
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# Run migrations:
docker exec parwa_prod_backend alembic upgrade head

# Check health:
curl http://localhost:8000/health
curl http://localhost:3000/
```

### 6. Paddle Webhook Setup (AFTER deployment)
After the app is running:
1. Go to https://vendors.paddle.com/notifications
2. Create webhook endpoint: `https://parwa.ai/api/webhooks/paddle`
3. Subscribe to events: `subscription.created`, `subscription.updated`, `subscription.canceled`, `subscription.paused`, `subscription.resumed`, `payment.completed`, `payment.failed`
4. Copy the webhook signing secret → add to `.env.prod` as `PADDLE_WEBHOOK_SECRET=`
5. Redeploy: `docker compose -f docker-compose.prod.yml restart backend worker`

### 7. Google OAuth Setup
1. Go to https://console.cloud.google.com/apis/credentials
2. Add redirect URI: `https://parwa.ai/api/auth/google/callback`
3. Client ID and Secret already in `.env`

### Environment Variables Already Configured
- ✅ Google AI API Key (Gemini - Primary LLM)
- ✅ Cerebras API Key (Fast inference)
- ✅ Groq API Key (Fallback)
- ✅ Brevo API Key (Email)
- ✅ Twilio credentials (SMS/Voice)
- ✅ Paddle Client Token + API Key (Payments - LIVE)
- ✅ Google OAuth Client ID + Secret
- ⚠️ Paddle Webhook Secret — add after deployment
- ⚠️ Redis password — set a strong password in .env.prod

### Key Ports (Production)
- 80/443: Nginx (HTTPS termination)
- 3000: Frontend (Next.js)
- 3001: Grafana monitoring
- 8000: Backend API (internal only, via nginx proxy)
- 5432: PostgreSQL (internal only)
- 6379: Redis (internal only)
