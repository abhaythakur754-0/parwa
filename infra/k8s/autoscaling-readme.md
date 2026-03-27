# PARWA Autoscaling Infrastructure

This directory contains Kubernetes autoscaling configurations for the PARWA platform, supporting 50 clients and 2000 concurrent users.

## Components

### 1. Horizontal Pod Autoscaler (HPA)

**File:** `hpa.yaml`

Scales pods based on resource utilization:
- **Backend:** 2-20 pods (CPU: 70%, Memory: 80%)
- **MCP:** 2-10 pods (CPU: 75%, Memory: 85%)
- **Workers:** 1-15 pods (CPU: 70%)

```bash
# Apply HPA configuration
kubectl apply -f hpa.yaml

# Check HPA status
kubectl get hpa -n parwa
```

### 2. KEDA Scalers

**File:** `keda-scaler.yaml`

Event-driven autoscaling based on queue depth:
- **Redis Queue:** Scale workers when >100 pending tasks
- **Kafka:** Scale consumers based on lag
- **Polling Interval:** 15 seconds
- **Cooldown:** 5 minutes

```bash
# Apply KEDA configuration
kubectl apply -f keda-scaler.yaml

# Check ScaledObjects
kubectl get scaledobjects -n parwa
```

### 3. PgBouncer Connection Pooler

**File:** `pgbouncer.yaml`

Manages PostgreSQL connections efficiently:
- **Pool Mode:** Transaction (maximizes concurrency)
- **Max Client Connections:** 2000
- **Max DB Connections:** 500
- **Default Pool Size:** 50 per database
- **Replicas:** 3 (HA)

```bash
# Apply PgBouncer configuration
kubectl apply -f pgbouncer.yaml

# Check PgBouncer status
kubectl get pods -l app=pgbouncer -n parwa
```

### 4. Vertical Pod Autoscaler (VPA)

**File:** `vpa.yaml`

Automatically adjusts resource requests/limits:
- **Update Mode:** Auto (applies recommendations automatically)
- **Backend:** 100m-4000m CPU, 256Mi-8Gi Memory
- **Workers:** 50m-2000m CPU, 128Mi-4Gi Memory
- **PgBouncer:** 50m-500m CPU, 64Mi-512Mi Memory

```bash
# Apply VPA configuration
kubectl apply -f vpa.yaml

# Check VPA recommendations
kubectl get vpa -n parwa
kubectl describe vpa parwa-backend-vpa -n parwa
```

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │         Load Balancer               │
                    └──────────────┬──────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
    ┌───────────┐           ┌───────────┐           ┌───────────┐
    │  Backend  │           │  Backend  │           │  Backend  │
    │   (HPA)   │◄──────────│   (HPA)   │◄──────────│   (HPA)   │
    │   2-20    │           │   2-20    │           │   2-20    │
    └─────┬─────┘           └─────┬─────┘           └─────┬─────┘
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │       PgBouncer (x3)       │
                    │     Connection Pooler      │
                    │    Max: 2000 clients       │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │     PostgreSQL Primary     │
                    │    Max: 500 connections    │
                    └───────────────────────────┘
```

## Scaling Metrics

| Component | Min | Max | Trigger | Threshold |
|-----------|-----|-----|---------|-----------|
| Backend HPA | 2 | 20 | CPU | 70% |
| Backend HPA | 2 | 20 | Memory | 80% |
| MCP HPA | 2 | 10 | CPU | 75% |
| Worker HPA | 1 | 15 | CPU | 70% |
| Worker KEDA | 1 | 20 | Redis Queue | 100 items |
| PgBouncer | 3 | 10 | CPU | 70% |

## Performance Targets

- **P95 Latency:** <300ms at 2000 concurrent users
- **Throughput:** 100+ requests/second
- **Scale Time:** <60 seconds from 2 to 20 pods
- **Connection Pooling:** 500 DB connections for 2000 clients

## Monitoring

### Prometheus Metrics

```promql
# HPA metrics
kube_hpa_status_current_replicas{namespace="parwa"}
kube_hpa_status_desired_replicas{namespace="parwa"}

# KEDA metrics
keda_scaledobject_replicas{namespace="parwa"}
keda_trigger_value{namespace="parwa"}

# PgBouncer metrics
pgbouncer_pools_server_active_connections
pgbouncer_pools_client_active_connections
```

### Grafana Dashboard

Import the autoscaling dashboard to monitor:
- Pod scaling events
- Resource utilization trends
- Queue depths
- Connection pool status

## Prerequisites

1. **KEDA Installation:**
   ```bash
   helm repo add kedacore https://kedacore.github.io/charts
   helm install keda kedacore/keda --namespace parwa --create-namespace
   ```

2. **VPA Installation:**
   ```bash
   kubectl apply -f https://github.com/kubernetes/autoscaler/releases/latest/download/vertical-pod-autoscaler.yaml
   ```

3. **Metrics Server:**
   ```bash
   kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
   ```

## Troubleshooting

### HPA not scaling

```bash
# Check metrics server
kubectl top pods -n parwa

# Check HPA events
kubectl describe hpa parwa-backend-hpa -n parwa
```

### KEDA not scaling

```bash
# Check KEDA operator logs
kubectl logs -n keda -l app=keda-operator

# Check ScaledObject status
kubectl describe scaledobject parwa-worker-scaler -n parwa
```

### PgBouncer connection issues

```bash
# Check PgBouncer logs
kubectl logs -n parwa -l app=pgbouncer

# Check connection stats
kubectl exec -n parwa deploy/pgbouncer -- pgbouncer -q admin show pools
```

## Best Practices

1. **Test scaling in staging** before production
2. **Monitor P95 latency** during scale events
3. **Set appropriate cooldown periods** to prevent thrashing
4. **Use VPA Auto mode** cautiously - test with Off mode first
5. **Configure resource limits** to prevent runaway scaling

## Files

| File | Description |
|------|-------------|
| `hpa.yaml` | Horizontal Pod Autoscaler configs |
| `keda-scaler.yaml` | KEDA event-driven scalers |
| `pgbouncer.yaml` | PgBouncer connection pooler |
| `vpa.yaml` | Vertical Pod Autoscaler configs |

## Related Documentation

- [HPA Documentation](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [KEDA Documentation](https://keda.sh/docs/)
- [PgBouncer Documentation](https://www.pgbouncer.org/)
- [VPA Documentation](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)
