"""Data flow & error architecture routes (PHASE 15 — GAP 13).

Provides endpoints to:
  - Inspect circuit breaker states
  - Inspect cache stats
  - Reset circuit breakers
  - Invalidate caches
  - Get structured error info
"""
import json
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, AuditLog
from app.auth import get_current_user
from app.services.external_tool_bus import get_tool_bus

router = APIRouter(prefix="/api/v1/dataflow", tags=["dataflow"])


class ResetCircuitRequest(BaseModel):
    integration_id: str


class InvalidateCacheRequest(BaseModel):
    integration_id: str
    path: str = None


@router.get("/circuit-states")
def get_circuit_states(
    current_user: User = Depends(get_current_user),
):
    """Get circuit breaker states for all integrations."""
    bus = get_tool_bus()
    states = bus.get_circuit_states()
    return {
        "circuits": states,
        "total": len(states),
    }


@router.post("/reset-circuit")
def reset_circuit(
    req: ResetCircuitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually reset a circuit breaker for an integration."""
    bus = get_tool_bus()
    bus.reset_circuit(req.integration_id)

    # Log audit event
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="dataflow.circuit_reset",
        actor=current_user.email,
        resource_type="integration",
        resource_id=req.integration_id,
        details=json.dumps({"action": "circuit_breaker_reset"}),
        severity="info",
    )
    db.add(audit)
    db.commit()

    return {
        "message": f"Circuit breaker reset for {req.integration_id}",
        "integration_id": req.integration_id,
        "new_state": "closed",
    }


@router.get("/cache-stats")
def get_cache_stats(
    current_user: User = Depends(get_current_user),
):
    """Get cache statistics."""
    bus = get_tool_bus()
    return bus.get_cache_stats()


@router.post("/invalidate-cache")
def invalidate_cache(
    req: InvalidateCacheRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Invalidate cache for an integration."""
    bus = get_tool_bus()
    bus.invalidate_cache(req.integration_id, req.path)

    # Log audit event
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="dataflow.cache_invalidated",
        actor=current_user.email,
        resource_type="integration",
        resource_id=req.integration_id,
        details=json.dumps({"path": req.path or "all"}),
        severity="info",
    )
    db.add(audit)
    db.commit()

    return {
        "message": f"Cache invalidated for {req.integration_id}",
        "integration_id": req.integration_id,
        "path": req.path or "all",
    }


@router.get("/health")
def get_dataflow_health(
    current_user: User = Depends(get_current_user),
):
    """Get overall data flow health — circuit states + cache stats."""
    bus = get_tool_bus()
    circuits = bus.get_circuit_states()
    cache_stats = bus.get_cache_stats()

    open_circuits = sum(1 for c in circuits.values() if c.get("state") == "open")
    half_open = sum(1 for c in circuits.values() if c.get("state") == "half_open")

    return {
        "status": "degraded" if open_circuits > 0 else "healthy",
        "circuit_breakers": {
            "total": len(circuits),
            "closed": len(circuits) - open_circuits - half_open,
            "open": open_circuits,
            "half_open": half_open,
        },
        "cache": cache_stats,
    }


@router.get("/error-codes")
def get_error_codes():
    """Get all possible error codes and their descriptions (for frontend error handling)."""
    from app.services.external_tool_bus import ToolBusError
    return {
        "error_codes": ToolBusError.ERROR_CODES,
        "retry_policy": {
            "max_retries": 3,
            "backoff_base_seconds": 1,
            "retriable_status_codes": [408, 429, 500, 502, 503, 504],
        },
        "circuit_breaker_policy": {
            "failure_threshold": 5,
            "recovery_timeout_seconds": 60,
        },
        "cache_ttl_policy": {
            "realtime": 300,
            "semi_static": 900,
            "static": 3600,
        },
    }
