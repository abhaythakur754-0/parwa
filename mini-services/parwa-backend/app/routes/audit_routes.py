"""Audit log routes for PARWA backend (Phase 9 features)."""
import json
import csv
import io
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, AuditLog
from app.auth import get_current_user
from app.encryption import encrypt_data

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


# --- Pydantic Models ---

class LogEntryRequest(BaseModel):
    action: str
    actor: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[dict] = None
    severity: str = "info"


# --- Routes ---

@router.get("/entries")
def list_audit_entries(
    category: Optional[str] = None,
    severity: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List audit entries for tenant with filters."""
    query = db.query(AuditLog).filter(AuditLog.tenant_id == current_user.tenant_id)

    if category:
        query = query.filter(AuditLog.action.like(f"{category}%"))
    if severity:
        query = query.filter(AuditLog.severity == severity)
    if date_from:
        try:
            from_dt = datetime.fromisoformat(date_from)
            query = query.filter(AuditLog.created_at >= from_dt)
        except ValueError:
            pass
    if date_to:
        try:
            to_dt = datetime.fromisoformat(date_to)
            query = query.filter(AuditLog.created_at <= to_dt)
        except ValueError:
            pass

    total = query.count()
    entries = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "entries": [
            {
                "id": e.id,
                "action": e.action,
                "actor": e.actor,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "details": json.loads(e.details) if e.details else None,
                "severity": e.severity,
                "checksum": e.checksum,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/entries/{entry_id}")
def get_audit_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single audit entry."""
    entry = (
        db.query(AuditLog)
        .filter(AuditLog.id == entry_id, AuditLog.tenant_id == current_user.tenant_id)
        .first()
    )

    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    return {
        "id": entry.id,
        "action": entry.action,
        "actor": entry.actor,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "details": json.loads(entry.details) if entry.details else None,
        "severity": entry.severity,
        "checksum": entry.checksum,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


@router.get("/stats")
def get_audit_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get audit log statistics."""
    # Total entries
    total = db.query(AuditLog).filter(AuditLog.tenant_id == current_user.tenant_id).count()

    # Last 24 hours
    yesterday = datetime.utcnow() - timedelta(hours=24)
    last_24h = (
        db.query(AuditLog)
        .filter(AuditLog.tenant_id == current_user.tenant_id, AuditLog.created_at >= yesterday)
        .count()
    )

    # Top action
    from sqlalchemy import func
    top_action_result = (
        db.query(AuditLog.action, func.count(AuditLog.id).label("count"))
        .filter(AuditLog.tenant_id == current_user.tenant_id)
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .first()
    )

    top_action = top_action_result[0] if top_action_result else None
    top_action_count = top_action_result[1] if top_action_result else 0

    # Severity breakdown
    severity_counts = {}
    for sev in ["info", "warning", "error", "critical"]:
        count = (
            db.query(AuditLog)
            .filter(AuditLog.tenant_id == current_user.tenant_id, AuditLog.severity == sev)
            .count()
        )
        severity_counts[sev] = count

    return {
        "total": total,
        "last_24h": last_24h,
        "top_action": top_action,
        "top_action_count": top_action_count,
        "severity_breakdown": severity_counts,
    }


@router.get("/export")
def export_audit_entries(
    format: str = Query("json", pattern="^(json|csv)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export audit entries in JSON or CSV format."""
    entries = (
        db.query(AuditLog)
        .filter(AuditLog.tenant_id == current_user.tenant_id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )

    entry_list = [
        {
            "id": e.id,
            "action": e.action,
            "actor": e.actor,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "details": e.details,
            "severity": e.severity,
            "checksum": e.checksum,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]

    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["id", "action", "actor", "resource_type", "resource_id", "details", "severity", "checksum", "created_at"])
        writer.writeheader()
        writer.writerows(entry_list)
        return {"format": "csv", "data": output.getvalue(), "count": len(entry_list)}

    return {"format": "json", "data": entry_list, "count": len(entry_list)}


@router.get("/alerts")
def get_security_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get security alerts (critical and warning severity entries)."""
    alerts = (
        db.query(AuditLog)
        .filter(
            AuditLog.tenant_id == current_user.tenant_id,
            AuditLog.severity.in_(["critical", "warning", "error"]),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(50)
        .all()
    )

    return {
        "alerts": [
            {
                "id": a.id,
                "action": a.action,
                "actor": a.actor,
                "resource_type": a.resource_type,
                "resource_id": a.resource_id,
                "details": json.loads(a.details) if a.details else None,
                "severity": a.severity,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ],
        "total": len(alerts),
    }


@router.post("/log")
def log_audit_entry(
    req: LogEntryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log a new audit entry."""
    # Generate checksum for integrity
    checksum_data = f"{req.action}:{req.actor}:{current_user.tenant_id}:{datetime.utcnow().isoformat()}"
    import hashlib
    checksum = hashlib.sha256(checksum_data.encode()).hexdigest()

    entry = AuditLog(
        tenant_id=current_user.tenant_id,
        action=req.action,
        actor=req.actor or current_user.email,
        resource_type=req.resource_type,
        resource_id=req.resource_id,
        details=json.dumps(req.details) if req.details else None,
        severity=req.severity,
        checksum=checksum,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return {
        "id": entry.id,
        "action": entry.action,
        "severity": entry.severity,
        "checksum": entry.checksum,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }
