# PARWA Autoscaling Guide

This guide covers the autoscaling infrastructure for PARWA, supporting 50 clients and 2000 concurrent users.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Horizontal Pod Autoscaler (HPA)](#horizontal-pod-autoscaler-hpa)
3. [KEDA Event-Driven Scaling](#keda-event-driven-scaling)
4. [Vertical Pod Autoscaler (VPA)](#vertical-pod-autoscaler-vpa)
5. [PgBouncer Connection Pooling](#pgbouncer-connection-pooling)
6. [Monitoring and Alerting](#monitoring-and-alerting)
7. [Troubleshooting](#troubleshooting)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Load Balancer                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │ Backend  │   │ Backend  │   │ Backend  │
    │  (HPA)   │   │  (HPA)   │   │  (HPA)   │
    │  2-20    │   │  2-20    │   │  2-20    │
    └────┬─────┘   └────┬─────┘   └────┬─────┘
         │              │              │
         └──────────────┼──────────────┘
                        │
              ┌─────────┴─────────┐
              │   PgBouncer (x3)   │
              │  Connection Pool   │
              └─────────┬─────────┘
                        │
              ┌─────────┴─────────┐
              │    PostgreSQL     │
              │    Primary        │
              └───────────────────┘
```

## Horizontal Pod Autoscaler (HPA)

### Overview

HPA automatically scales pods based on CPU and memory utilization.

### Configuration

```yaml
# infra/k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: parwa-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: parwa-backend
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### Key Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| minReplicas | 2 | Minimum pods running |
| maxReplicas | 20 | Maximum pods under load |
| CPU threshold | 70% | Scale up trigger |
| Memory threshold | 80% | Scale up trigger |

### Managing HPA

```bash
# Apply HPA
kubectl apply -f infra/k8s/hpa.yaml

# Check status
kubectl get hpa -n parwa

# Watch scaling
kubectl get hpa parwa-backend-hpa -n parwa -w

# Describe for details
kubectl describe hpa parwa-backend-hpa -n parwa
```

## KEDA Event-Driven Scaling

### Overview

KEDA scales workers based on queue depth, enabling responsive scaling for background tasks.

### Configuration

```yaml
# infra/k8s/keda-scaler.yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: parwa-worker-scaler
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: parwa-worker
  minReplicaCount: 1
  maxReplicaCount: 20
  triggers:
    - type: redis
      metadata:
        host: redis-master.parwa.svc.cluster.local
        port: "6379"
        listName: "parwa:tasks:pending"
        listLength: "100"
```

### Key Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| pollingInterval | 15s | Queue check frequency |
| cooldownPeriod | 300s | Wait before scale down |
| listLength | 100 | Queue depth trigger |

### Managing KEDA

```bash
# Apply KEDA scalers
kubectl apply -f infra/k8s/keda-scaler.yaml

# Check ScaledObjects
kubectl get scaledobjects -n parwa

# View scaling events
kubectl logs -n keda -l app=keda-operator
```

## Vertical Pod Autoscaler (VPA)

### Overview

VPA automatically adjusts resource requests and limits based on usage patterns.

### Configuration

```yaml
# infra/k8s/vpa.yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: parwa-backend-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: parwa-backend
  updatePolicy:
    updateMode: Auto
  resourcePolicy:
    containerPolicies:
      - containerName: parwa-backend
        minAllowed:
          cpu: 100m
          memory: 256Mi
        maxAllowed:
          cpu: 4000m
          memory: 8Gi
```

### Update Modes

| Mode | Description |
|------|-------------|
| Auto | Automatically applies recommendations |
| Recreate | Recreates pods with new resources |
| Off | Only provides recommendations |

### Managing VPA

```bash
# Apply VPA
kubectl apply -f infra/k8s/vpa.yaml

# View recommendations
kubectl describe vpa parwa-backend-vpa -n parwa

# Check all VPAs
kubectl get vpa -n parwa
```

## PgBouncer Connection Pooling

### Overview

PgBouncer manages database connections efficiently, allowing 2000 client connections with only 500 database connections.

### Configuration

Key settings in `infra/k8s/pgbouncer.yaml`:

```ini
[pgbouncer]
pool_mode = transaction
max_client_conn = 2000
max_db_connections = 500
default_pool_size = 50
```

### Pool Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| session | One connection per client | Long transactions |
| transaction | Shared during transaction | High concurrency |
| statement | Shared per statement | Read-heavy workloads |

### Managing PgBouncer

```bash
# Apply PgBouncer
kubectl apply -f infra/k8s/pgbouncer.yaml

# Check status
kubectl get pods -l app=pgbouncer -n parwa

# View pool statistics
kubectl exec -n parwa deploy/pgbouncer -- \
  psql -p 6432 pgbouncer -c "SHOW POOLS;"
```

## Monitoring and Alerting

### Prometheus Metrics

```promql
# HPA metrics
kube_hpa_status_current_replicas{namespace="parwa"}
kube_hpa_status_desired_replicas{namespace="parwa"}

# KEDA metrics
keda_scaledobject_replicas{namespace="parwa"}

# PgBouncer metrics
pgbouncer_pools_server_active_connections
pgbouncer_pools_client_active_connections
```

### Grafana Dashboards

Import dashboards for:
- HPA scaling events
- KEDA queue depth
- PgBouncer connection pools
- Resource utilization trends

### Alert Rules

| Alert | Condition | Action |
|-------|-----------|--------|
| HPAAtMaxReplicas | replicas == maxReplicas | Scale infrastructure |
| KEDANotScaling | queue_depth > threshold for 5m | Check KEDA operator |
| PgBouncerConnectionsHigh | connections > 1800 | Increase pool size |

## Troubleshooting

### HPA Not Scaling

1. **Check metrics server:**
   ```bash
   kubectl top pods -n parwa
   kubectl top nodes
   ```

2. **Verify HPA can read metrics:**
   ```bash
   kubectl describe hpa parwa-backend-hpa -n parwa
   ```

3. **Check resource requests:**
   ```bash
   kubectl get pod -n parwa -o jsonpath='{.items[*].spec.containers[*].resources}'
   ```

### KEDA Not Scaling

1. **Verify Redis connectivity:**
   ```bash
   kubectl run redis-cli --rm -it --image=redis -- \
     redis-cli -h redis-master.parwa.svc.cluster.local LLEN parwa:tasks:pending
   ```

2. **Check KEDA operator logs:**
   ```bash
   kubectl logs -n keda -l app=keda-operator
   ```

3. **Verify trigger authentication:**
   ```bash
   kubectl get triggerauthentications -n parwa
   ```

### PgBouncer Connection Issues

1. **Check PgBouncer logs:**
   ```bash
   kubectl logs -n parwa -l app=pgbouncer
   ```

2. **Verify PostgreSQL connectivity:**
   ```bash
   kubectl exec -n parwa deploy/pgbouncer -- \
     psql -h postgres-primary -U parwa_app -d parwa -c "SELECT 1"
   ```

3. **Check connection count:**
   ```bash
   kubectl exec -n parwa deploy/pgbouncer -- \
     psql -p 6432 pgbouncer -c "SHOW DATABASES;"
   ```

### VPA Not Updating Resources

1. **Check VPA mode:**
   ```bash
   kubectl get vpa parwa-backend-vpa -n parwa -o yaml | grep updateMode
   ```

2. **View recommendations:**
   ```bash
   kubectl describe vpa parwa-backend-vpa -n parwa
   ```

---

**Last Updated:** 2026-03-28
