"""
PARWA Trigger API - Automated Trigger Endpoints (Day 33: MF08)

Endpoints for managing automated trigger rules.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.exceptions import NotFoundError, ValidationError
from app.services.trigger_service import TriggerService
from database.models.core import User


router = APIRouter(
    prefix="/triggers",
    tags=["Triggers"],
    dependencies=[Depends(require_roles("owner", "admin"))],
)


# ── Schemas ────────────────────────────────────────────────────────────────


class TriggerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    conditions: Dict[str, Any] = Field(..., description="Trigger conditions")
    action: Dict[str, Any] = Field(..., description="Trigger action")
    priority_order: int = Field(0, ge=0, le=1000)


class TriggerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    action: Optional[Dict[str, Any]] = None
    priority_order: Optional[int] = Field(None, ge=0, le=1000)


class TriggerToggle(BaseModel):
    is_active: bool


class TriggerResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    conditions: Dict[str, Any]
    action: Dict[str, Any]
    is_active: bool
    priority_order: int
    execution_count: int
    last_executed_at: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


import json


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("", response_model=TriggerResponse)
def create_trigger(
    data: TriggerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new trigger."""
    service = TriggerService(db, current_user.company_id)

    try:
        trigger = service.create_trigger(
            name=data.name,
            description=data.description,
            conditions=data.conditions,
            action=data.action,
            priority_order=data.priority_order,
            created_by=current_user.id,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return TriggerResponse(
        id=trigger.id,
        name=trigger.name,
        description=trigger.description,
        conditions=json.loads(trigger.conditions or "{}"),
        action=json.loads(trigger.action or "{}"),
        is_active=trigger.is_active,
        priority_order=trigger.priority_order,
        execution_count=trigger.execution_count or 0,
        last_executed_at=trigger.last_executed_at.isoformat() if trigger.last_executed_at else None,
        created_at=trigger.created_at.isoformat(),
        updated_at=trigger.updated_at.isoformat(),
    )


@router.get("", response_model=Dict[str, Any])
def list_triggers(
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List triggers with filters."""
    service = TriggerService(db, current_user.company_id)

    triggers, total = service.list_triggers(
        is_active=is_active,
        search=search,
        page=page,
        page_size=page_size,
    )

    return {
        "triggers": [
            TriggerResponse(
                id=t.id,
                name=t.name,
                description=t.description,
                conditions=json.loads(t.conditions or "{}"),
                action=json.loads(t.action or "{}"),
                is_active=t.is_active,
                priority_order=t.priority_order,
                execution_count=t.execution_count or 0,
                last_executed_at=t.last_executed_at.isoformat() if t.last_executed_at else None,
                created_at=t.created_at.isoformat(),
                updated_at=t.updated_at.isoformat(),
            )
            for t in triggers
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{trigger_id}", response_model=TriggerResponse)
def get_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a trigger by ID."""
    service = TriggerService(db, current_user.company_id)

    try:
        trigger = service.get_trigger(trigger_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return TriggerResponse(
        id=trigger.id,
        name=trigger.name,
        description=trigger.description,
        conditions=json.loads(trigger.conditions or "{}"),
        action=json.loads(trigger.action or "{}"),
        is_active=trigger.is_active,
        priority_order=trigger.priority_order,
        execution_count=trigger.execution_count or 0,
        last_executed_at=trigger.last_executed_at.isoformat() if trigger.last_executed_at else None,
        created_at=trigger.created_at.isoformat(),
        updated_at=trigger.updated_at.isoformat(),
    )


@router.put("/{trigger_id}", response_model=TriggerResponse)
def update_trigger(
    trigger_id: str,
    data: TriggerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a trigger."""
    service = TriggerService(db, current_user.company_id)

    try:
        trigger = service.update_trigger(
            trigger_id=trigger_id,
            name=data.name,
            description=data.description,
            conditions=data.conditions,
            action=data.action,
            priority_order=data.priority_order,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return TriggerResponse(
        id=trigger.id,
        name=trigger.name,
        description=trigger.description,
        conditions=json.loads(trigger.conditions or "{}"),
        action=json.loads(trigger.action or "{}"),
        is_active=trigger.is_active,
        priority_order=trigger.priority_order,
        execution_count=trigger.execution_count or 0,
        last_executed_at=trigger.last_executed_at.isoformat() if trigger.last_executed_at else None,
        created_at=trigger.created_at.isoformat(),
        updated_at=trigger.updated_at.isoformat(),
    )


@router.delete("/{trigger_id}")
def delete_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a trigger (soft delete)."""
    service = TriggerService(db, current_user.company_id)

    try:
        service.delete_trigger(trigger_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"success": True, "message": "Trigger deleted"}


@router.patch("/{trigger_id}/toggle", response_model=TriggerResponse)
def toggle_trigger(
    trigger_id: str,
    data: TriggerToggle,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enable or disable a trigger."""
    service = TriggerService(db, current_user.company_id)

    try:
        trigger = service.toggle_trigger(trigger_id, data.is_active)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return TriggerResponse(
        id=trigger.id,
        name=trigger.name,
        description=trigger.description,
        conditions=json.loads(trigger.conditions or "{}"),
        action=json.loads(trigger.action or "{}"),
        is_active=trigger.is_active,
        priority_order=trigger.priority_order,
        execution_count=trigger.execution_count or 0,
        last_executed_at=trigger.last_executed_at.isoformat() if trigger.last_executed_at else None,
        created_at=trigger.created_at.isoformat(),
        updated_at=trigger.updated_at.isoformat(),
    )


@router.get("/{trigger_id}/executions")
def get_trigger_executions(
    trigger_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get trigger execution history."""
    service = TriggerService(db, current_user.company_id)

    try:
        history = service.get_execution_history(
            trigger_id=trigger_id,
            page=page,
            page_size=page_size,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return history
