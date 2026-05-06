# PARWA Deployment Guide

## Prerequisites

- Docker 24.x or later
- Kubernetes 1.28+ (for production)
- PostgreSQL 15+
- Redis 7+
- Node.js 20.x (for frontend)
- Python 3.12+ (for backend)

## Quick Start (Development)

### 1. Clone Repository
```bash
git clone https://github.com/abhaythakur754-0/parwa.git
cd parwa
```

### 2. Environment Setup
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Docker Compose
```bash
docker-compose up -d
```

### 4. Run Migrations
```bash
docker-compose exec backend alembic upgrade head
```

### 5. Seed Data
```bash
docker-compose exec backend python -m backend.seeds.seed_all
```

## Production Deployment

### Kubernetes Deployment

#### 1. Create Namespace
```bash
kubectl create namespace parwa
```

#### 2. Create Secrets
```bash
kubectl create secret generic parwa-secrets \
  --from-literal=database-url=<url> \
  --from-literal=redis-url=<url> \
  --from-literal=jwt-secret=<secret> \
  -n parwa
```

#### 3. Apply ConfigMaps
```bash
kubectl apply -f infra/k8s/configmaps/ -n parwa
```

#### 4. Deploy Components
```bash
kubectl apply -f infra/k8s/backend/ -n parwa
kubectl apply -f infra/k8s/frontend/ -n parwa
kubectl apply -f infra/k8s/workers/ -n parwa
```

#### 5. Configure Ingress
```bash
kubectl apply -f infra/k8s/ingress/ -n parwa
```

### High Availability Setup

#### HPA Configuration
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: parwa-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: parwa-backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

#### PgBouncer Connection Pooling
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pgbouncer
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: pgbouncer
        image: edoburu/pgbouncer:latest
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: parwa-secrets
              key: database-url
        - name: POOL_MODE
          value: transaction
        - name: MAX_CLIENT_CONN
          value: "1000"
        - name: DEFAULT_POOL_SIZE
          value: "25"
```

## Monitoring

### Prometheus & Grafana
```bash
kubectl apply -f infra/k8s/monitoring/ -n parwa
```

### Log Aggregation
```bash
kubectl apply -f infra/k8s/logging/ -n parwa
```

## Health Checks

### Backend Health
```bash
curl https://api.parwa.ai/health
```

Expected Response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "version": "1.0.0"
}
```

### Frontend Health
```bash
curl https://parwa.ai/api/health
```

## Scaling Guidelines

| Metric | Scale Trigger |
|--------|--------------|
| CPU > 70% | Add backend pods |
| Memory > 80% | Add backend pods |
| P95 Latency > 300ms | Add backend pods |
| Queue Depth > 1000 | Add worker pods |

## Troubleshooting

### Common Issues

1. **Database Connection Pool Exhausted**
   - Increase PgBouncer pool size
   - Check for connection leaks

2. **High Memory Usage**
   - Check for memory leaks in workers
   - Restart pods periodically

3. **Slow API Response**
   - Check database query performance
   - Verify Redis caching is working
