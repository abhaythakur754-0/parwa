# Week 37: 50-Client Scale + Autoscaling Guide

This guide covers the setup and configuration for scaling PARWA to 50 clients with autoscaling infrastructure.

## Overview

Week 37 extends PARWA from 30 to 50 clients with:
- 20 new client configurations (clients 031-050)
- Autoscaling infrastructure (HPA, KEDA, VPA)
- Connection pooling (PgBouncer)
- Cost optimization tools

## Prerequisites

Before starting, ensure you have:
- Kubernetes cluster with metrics server
- KEDA operator installed
- VPA components installed
- Access to PostgreSQL database
- Redis cluster operational

## Step 1: Add New Clients

### Client Configuration

Each new client (031-050) has:
- `config.py` - Main configuration
- `__init__.py` - Module initialization
- `knowledge_base/__init__.py` - KB initialization

```python
# Example: clients/client_031/config.py
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import time

@dataclass
class ClientConfig:
    client_id: str
    client_name: str
    industry: str
    variant: str
    timezone: str
    # ... additional fields

def get_client_config() -> ClientConfig:
    return ClientConfig(
        client_id="client_031",
        client_name="EduTech Academy",
        industry="education_technology",
        variant="parwa_junior",
        timezone="America/New_York",
        # ...
    )
```

### Variant Distribution

| Variant | Count | Features |
|---------|-------|----------|
| mini_parwa | 4 | Basic support, 2 concurrent calls |
| parwa_junior | 10 | Learning, refund verification |
| parwa_high | 6 | Voice support, analytics |

## Step 2: Configure Autoscaling

### Horizontal Pod Autoscaler (HPA)

```bash
# Apply HPA configuration
kubectl apply -f infra/k8s/hpa.yaml

# Verify HPA status
kubectl get hpa -n parwa
```

**Configuration:**
- Backend: 2-20 pods (CPU 70%, Memory 80%)
- MCP: 2-10 pods (CPU 75%)
- Workers: 1-15 pods (CPU 70%)

### KEDA Event-Driven Scaling

```bash
# Apply KEDA scalers
kubectl apply -f infra/k8s/keda-scaler.yaml

# Check ScaledObjects
kubectl get scaledobjects -n parwa
```

**Configuration:**
- Redis queue trigger: Scale at >100 pending tasks
- Kafka consumer lag: Scale based on lag threshold

### PgBouncer Connection Pooler

```bash
# Apply PgBouncer
kubectl apply -f infra/k8s/pgbouncer.yaml

# Verify deployment
kubectl get pods -l app=pgbouncer -n parwa
```

**Configuration:**
- Pool mode: Transaction
- Max client connections: 2000
- Max DB connections: 500
- Default pool size: 50

### Vertical Pod Autoscaler (VPA)

```bash
# Apply VPA
kubectl apply -f infra/k8s/vpa.yaml

# Check recommendations
kubectl describe vpa parwa-backend-vpa -n parwa
```

## Step 3: Validate 50-Client Setup

### Run Validation Script

```bash
python scripts/validate_50_tenant.py --verbose
```

### Run Cross-Tenant Isolation Tests

```bash
pytest tests/integration/test_50_client_isolation.py -v
```

### Run Performance Tests

```bash
pytest tests/performance/test_50_client_load.py -v
```

## Step 4: Monitor Scaling

### Check HPA Status

```bash
kubectl get hpa parwa-backend-hpa -n parwa -w
```

### Check KEDA Metrics

```bash
kubectl logs -n keda -l app=keda-operator
```

### Check PgBouncer Stats

```bash
kubectl exec -n parwa deploy/pgbouncer -- \
  psql -p 6432 pgbouncer -c "SHOW POOLS;"
```

## Performance Targets

| Metric | Target | Validation |
|--------|--------|------------|
| Total Clients | 50 | `pytest tests/clients/ -v` |
| Cross-Tenant Tests | 500, 0 leaks | `pytest tests/integration/test_50_client_isolation.py -v` |
| Concurrent Users | 2000 | `pytest tests/performance/test_50_client_load.py -v` |
| P95 Latency | <300ms | Load test results |
| HPA Scaling | 10+ pods | `kubectl get hpa` |
| KEDA Workers | Auto-scale | `kubectl get scaledobjects` |

## Troubleshooting

### HPA Not Scaling

1. Check metrics server:
   ```bash
   kubectl top pods -n parwa
   ```

2. Verify HPA can read metrics:
   ```bash
   kubectl describe hpa parwa-backend-hpa -n parwa
   ```

### KEDA Not Scaling

1. Check Redis connectivity:
   ```bash
   kubectl run redis-cli --rm -it --image=redis -- \
     redis-cli -h redis-master.parwa.svc.cluster.local LLEN parwa:tasks:pending
   ```

2. Verify KEDA operator:
   ```bash
   kubectl logs -n keda -l app=keda-operator
   ```

### PgBouncer Connection Issues

1. Check PgBouncer logs:
   ```bash
   kubectl logs -n parwa -l app=pgbouncer
   ```

2. Verify PostgreSQL connectivity:
   ```bash
   kubectl exec -n parwa deploy/pgbouncer -- \
     psql -h postgres-primary -U parwa_app -d parwa -c "SELECT 1"
   ```

## Cost Optimization

See `reports/cost_optimization_report.md` for:
- Monthly cost analysis
- Optimization recommendations
- Potential savings

## Next Steps

After completing Week 37:
1. Run full test suite (Tester Agent)
2. Review performance metrics
3. Proceed to Week 38: Enterprise Pre-Preparation

---

**Last Updated:** 2026-03-28
