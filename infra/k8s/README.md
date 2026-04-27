# PARWA Kubernetes Manifests

> **Note:** PARWA currently deploys to **AWS ECS** (Fargate). The production
> infrastructure uses ECS for orchestration, ECR for container images, and
> CloudFront/S3 for the frontend.
>
> The manifests in this directory are provided as **future-ready skeletons**.
> They are NOT yet used in any deployment pipeline. When the team decides to
> migrate to Kubernetes (EKS or any other cluster), these files serve as the
> starting point.

## Current Deployment (ECS)

| Component   | ECS Cluster   | ECS Service      | ECR Repo            |
|-------------|---------------|------------------|---------------------|
| Backend     | `parwa-prod`  | `parwa-backend`  | `parwa-backend`     |
| Worker      | `parwa-prod`  | —                | `parwa-worker`      |
| Frontend    | S3 + CloudFront (static) | — | — |

### Key Files

- `.github/workflows/deploy-backend.yml` — ECS deployment via `amazon-ecs-deploy-task-definition`
- `.github/workflows/deploy-frontend.yml` — S3 sync + CloudFront invalidation
- `.github/workflows/rollback.yml` — ECS service rollback using SSM parameter store
- `docker-compose.prod.yml` — Full production compose (Docker-in-Docker / single-host)

### Required GitHub Secrets

```
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
FRONTEND_BUCKET_NAME
CF_DISTRIBUTION_ID
NEXT_PUBLIC_PADDLE_KEY
```

## K8s Manifests

```
infra/k8s/
├── README.md                    ← this file
├── namespace.yaml               ← parwa namespace
├── configmap.yaml               ← non-sensitive env vars (APP_ENV, LOG_LEVEL, etc.)
├── ingress.yaml                 ← NGINX Ingress with TLS (/api → backend, / → frontend)
├── hpa.yaml                     ← HorizontalPodAutoscaler (backend 2-10, frontend 2-5)
├── networkpolicy.yaml           ← NetworkPolicies (backend→Redis/Postgres, frontend ingress-only)
├── backend/
│   ├── deployment.yaml          ← backend API (2 replicas, security-hardened)
│   └── service.yaml             ← ClusterIP :8000
├── frontend/
│   ├── deployment.yaml          ← Next.js frontend (2 replicas)
│   └── service.yaml             ← ClusterIP :3000
├── redis/
│   ├── deployment.yaml          ← Redis StatefulSet (1 replica, 5Gi PVC)
│   └── service.yaml             ← ClusterIP :6379
└── celery/
    ├── worker-deployment.yaml   ← Celery workers (2 replicas, concurrency=4)
    └── beat-deployment.yaml     ← Celery beat scheduler (1 replica)
```

### Required Secrets (create before deploying)

```bash
kubectl create secret generic parwa-backend-secrets \
  --from-literal=database-url='postgresql://...' \
  --from-literal=redis-url='redis://parwa-redis:6379/0' \
  --from-literal=secret-key='...' \
  -n parwa
```

### Required Prerequisites

- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/) installed
- [cert-manager](https://cert-manager.io/) with `letsencrypt-prod` ClusterIssuer
- StorageClass `gp3` available (or modify `redis/deployment.yaml`)

### Deploy Order

```bash
# 1. Namespace first
kubectl apply -f infra/k8s/namespace.yaml

# 2. ConfigMap and secrets
kubectl apply -f infra/k8s/configmap.yaml

# 3. Stateful services (Redis)
kubectl apply -f infra/k8s/redis/

# 4. Core services
kubectl apply -f infra/k8s/backend/
kubectl apply -f infra/k8s/frontend/

# 5. Background workers
kubectl apply -f infra/k8s/celery/

# 6. Networking and autoscaling
kubectl apply -f infra/k8s/networkpolicy.yaml
kubectl apply -f infra/k8s/ingress.yaml
kubectl apply -f infra/k8s/hpa.yaml
```

### Image Tag Substitution

Before deploying, replace the `{{ECR_REGISTRY}}` placeholder:

```bash
sed -i 's|{{ECR_REGISTRY}}|123456789012.dkr.ecr.us-east-1.amazonaws.com|g' \
  infra/k8s/backend/deployment.yaml \
  infra/k8s/frontend/deployment.yaml \
  infra/k8s/celery/worker-deployment.yaml \
  infra/k8s/celery/beat-deployment.yaml
```
