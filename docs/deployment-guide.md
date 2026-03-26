# PARWA Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying PARWA (AI-powered customer support automation platform) to production environments. PARWA supports multiple deployment strategies including Docker Compose for development and Kubernetes for production workloads.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Configuration Options](#configuration-options)
6. [Post-Deployment Validation](#post-deployment-validation)
7. [Rollback Procedures](#rollback-procedures)

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| Memory | 8 GB | 16+ GB |
| Storage | 50 GB SSD | 100+ GB SSD |
| Network | 100 Mbps | 1 Gbps |

### Software Requirements

- **Docker**: 24.0+ with Docker Compose v2
- **Kubernetes**: 1.28+ (EKS, GKE, AKS, or self-managed)
- **kubectl**: 1.28+ configured for your cluster
- **Helm**: 3.12+ (optional, for Helm deployments)
- **cert-manager**: 1.13+ (for TLS certificates)
- **External Secrets Operator**: 0.9+ (for secrets management)

### External Services

Before deploying PARWA, ensure you have access to the following external services:

1. **PostgreSQL Database**: Supabase Pro or self-hosted PostgreSQL 15+
2. **Redis Cache**: Upstash Redis or self-hosted Redis 7+
3. **OpenAI API**: GPT-4 access for AI features
4. **Paddle Account**: For subscription billing
5. **Email Service**: SendGrid, AWS SES, or similar
6. **Cloud Storage**: AWS S3, GCS, or compatible

---

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/parwa.git
cd parwa
```

### 2. Configure Environment Variables

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Edit `.env` with your production values:

```env
# Application
APP_ENV=production
APP_NAME=parwa
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://user:password@host:5432/parwa?sslmode=require
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# Redis
REDIS_URL=redis://:password@host:6379/0

# OpenAI
OPENAI_API_KEY=sk-your-api-key

# Paddle
PADDLE_VENDOR_ID=your-vendor-id
PADDLE_API_KEY=your-api-key

# Security
JWT_SECRET=your-256-bit-secret
ENCRYPTION_KEY=your-32-byte-key

# OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
```

### 3. Create Kubernetes Secrets

For Kubernetes deployments, create secrets in your cluster:

```bash
# Create namespace
kubectl create namespace parwa

# Create secrets from literal values
kubectl create secret generic parwa-secrets \
  --from-literal=DATABASE_URL='postgresql://...' \
  --from-literal=REDIS_URL='redis://...' \
  --from-literal=OPENAI_API_KEY='sk-...' \
  --namespace=parwa
```

For production, use External Secrets Operator:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: parwa-secrets
  namespace: parwa
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secretsmanager
    kind: SecretStore
  target:
    name: parwa-secrets
  data:
    - secretKey: DATABASE_URL
      remoteRef:
        key: parwa/production
        property: database_url
```

---

## Docker Deployment

### Quick Start (Development)

```bash
# Build all images
docker-compose build

# Start all services
docker-compose up -d

# Check service health
docker-compose ps

# View logs
docker-compose logs -f backend
```

### Production Docker Compose

Use the production compose file for production deployments:

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Verify all services are healthy
docker-compose -f docker-compose.prod.yml ps
```

### Environment-Specific Configuration

Override configurations for different environments:

```bash
# Staging
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Container Registry

Push images to your container registry:

```bash
# Tag images
docker tag parwa/backend:latest your-registry.com/parwa/backend:v1.0.0
docker tag parwa/frontend:latest your-registry.com/parwa/frontend:v1.0.0
docker tag parwa/worker:latest your-registry.com/parwa/worker:v1.0.0

# Push to registry
docker push your-registry.com/parwa/backend:v1.0.0
docker push your-registry.com/parwa/frontend:v1.0.0
docker push your-registry.com/parwa/worker:v1.0.0
```

---

## Kubernetes Deployment

### 1. Prerequisites Check

```bash
# Verify cluster access
kubectl cluster-info

# Verify namespace exists
kubectl get namespace parwa

# Verify cert-manager
kubectl get clusterissuer letsencrypt-prod
```

### 2. Apply ConfigMaps

```bash
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/configmap.yaml
```

### 3. Create Secrets

Using External Secrets Operator (recommended):

```bash
kubectl apply -f infra/k8s/secrets.yaml
```

Or manually:

```bash
kubectl create secret generic parwa-secrets \
  --from-env-file=.env \
  --namespace=parwa
```

### 4. Deploy Stateful Services

```bash
# Deploy PostgreSQL (if self-hosted)
kubectl apply -f infra/k8s/postgres-statefulset.yaml

# Wait for PostgreSQL to be ready
kubectl rollout status statefulset/parwa-postgres -n parwa

# Deploy Redis
kubectl apply -f infra/k8s/redis-statefulset.yaml

# Wait for Redis to be ready
kubectl rollout status statefulset/parwa-redis -n parwa
```

### 5. Run Database Migrations

```bash
# Run migrations job
kubectl apply -f infra/k8s/migrations-job.yaml

# Wait for completion
kubectl wait --for=condition=complete job/parwa-migrations -n parwa --timeout=300s
```

### 6. Deploy Application Services

```bash
# Deploy backend
kubectl apply -f infra/k8s/backend-deployment.yaml

# Deploy frontend
kubectl apply -f infra/k8s/frontend-deployment.yaml

# Deploy worker
kubectl apply -f infra/k8s/worker-deployment.yaml

# Deploy MCP servers
kubectl apply -f infra/k8s/mcp-deployment.yaml
```

### 7. Deploy Ingress

```bash
kubectl apply -f infra/k8s/ingress.yaml
```

### 8. Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n parwa

# Check services
kubectl get services -n parwa

# Check ingress
kubectl get ingress -n parwa

# Check HPA status
kubectl get hpa -n parwa
```

### One-Command Deployment

```bash
# Apply all manifests
kubectl apply -f infra/k8s/

# Or use kustomize
kubectl apply -k infra/k8s/
```

---

## Configuration Options

### Backend Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `BACKEND_HOST` | Server bind address | `0.0.0.0` |
| `BACKEND_PORT` | Server port | `8000` |
| `BACKEND_WORKERS` | Uvicorn workers | `4` |
| `DB_POOL_SIZE` | Database connection pool | `20` |
| `REDIS_MAX_CONNECTIONS` | Redis connection pool | `50` |

### Frontend Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `NEXT_PUBLIC_APP_URL` | Application URL | Required |
| `NEXT_PUBLIC_API_URL` | API URL | Required |
| `NEXT_PUBLIC_STRIPE_KEY` | Stripe public key | Required |

### Feature Flags

Configure features in the ConfigMap:

```yaml
feature_flags:
  analytics_enabled: true
  jarvis_enabled: true
  approvals_enabled: true
  webhooks_enabled: true
```

---

## Post-Deployment Validation

### Health Checks

```bash
# Backend health
curl https://api.parwa.ai/health

# Frontend health
curl https://app.parwa.ai/health

# Database connectivity
kubectl exec -it deployment/parwa-backend -n parwa -- python -c "from database import check_connection; check_connection()"
```

### Smoke Tests

```bash
# Run smoke tests
pytest tests/smoke/ -v

# Run full test suite
pytest tests/ -v --cov
```

### Performance Tests

```bash
# Run load tests
locust -f tests/performance/test_load.py --headless -u 100 -r 10 -t 5m --host https://api.parwa.ai
```

---

## Rollback Procedures

### Kubernetes Rollback

```bash
# View deployment history
kubectl rollout history deployment/parwa-backend -n parwa

# Rollback to previous version
kubectl rollout undo deployment/parwa-backend -n parwa

# Rollback to specific revision
kubectl rollout undo deployment/parwa-backend -n parwa --to-revision=2
```

### Database Rollback

```bash
# Rollback database migrations
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision>
```

### Emergency Procedures

1. **Scale down affected service**:
   ```bash
   kubectl scale deployment parwa-backend --replicas=0 -n parwa
   ```

2. **Restore from backup**:
   ```bash
   kubectl apply -f infra/k8s/restore-job.yaml
   ```

3. **Switch to previous image**:
   ```bash
   kubectl set image deployment/parwa-backend backend=parwa/backend:v1.0.0 -n parwa
   ```

---

## Troubleshooting

See [troubleshooting.md](./troubleshooting.md) for common issues and solutions.

## Support

For deployment support, contact:
- **Email**: devops@parwa.ai
- **Slack**: #parwa-deployments
- **Documentation**: https://docs.parwa.ai
