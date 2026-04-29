"""
PARWA Custom Field API - Custom Ticket Field Endpoints (Day 33: MF09)

Endpoints for managing custom ticket fields.
"""

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.exceptions import NotFoundError, ValidationError
from app.services.custom_field_service import CustomFieldService
from database.models.core import User


router = APIRouter(
    prefix="/custom-fields",
    tags=["Custom Fields"],
    dependencies=[Depends(require_roles("owner", "admin"))],
)


# ── Schemas ────────────────────────────────────────────────────────────────


class CustomFieldCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    field_key: str = Field(..., min_length=1, max_length=100)
    field_type: str = Field(...,
                            description="text, number, dropdown, multi_select, date, checkbox")
    config: Optional[Dict[str, Any]] = None
    applicable_categories: Optional[List[str]] = None
    is_required: bool = False
    sort_order: int = 0


class CustomFieldUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    config: Optional[Dict[str, Any]] = None
    applicable_categories: Optional[List[str]] = None
    is_required: Optional[bool] = None
    sort_order: Optional[int] = None


class CustomFieldResponse(BaseModel):
    id: str
    name: str
    field_key: str
    field_type: str
    config: Dict[str, Any]
    applicable_categories: List[str]
    is_required: bool
    is_active: bool
    sort_order: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class FieldValidationRequest(BaseModel):
    field_key: str
    value: Any


class TicketFieldsValidationRequest(BaseModel):
    category: Optional[str] = None
    field_values: Dict[str, Any]


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("", response_model=CustomFieldResponse)
def create_custom_field(
    data: CustomFieldCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new custom field."""
    service = CustomFieldService(db, current_user.company_id)

    try:
        field = service.create_field(
            name=data.name,
            field_key=data.field_key,
            field_type=data.field_type,
            config=data.config,
            applicable_categories=data.applicable_categories,
            is_required=data.is_required,
            sort_order=data.sort_order,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CustomFieldResponse(
        id=field.id,
        name=field.name,
        field_key=field.field_key,
        field_type=field.field_type,
        config=json.loads(field.config or "{}"),
        applicable_categories=json.loads(field.applicable_categories or "[]"),
        is_required=field.is_required,
        is_active=field.is_active,
        sort_order=field.sort_order,
        created_at=field.created_at.isoformat(),
        updated_at=field.updated_at.isoformat(),
    )


@router.get("", response_model=Dict[str, Any])
def list_custom_fields(
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List custom fields with filters."""
    service = CustomFieldService(db, current_user.company_id)

    fields, total = service.list_fields(
        category=category,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    return {
        "fields": [
            CustomFieldResponse(
                id=f.id,
                name=f.name,
                field_key=f.field_key,
                field_type=f.field_type,
                config=json.loads(f.config or "{}"),
                applicable_categories=json.loads(f.applicable_categories or "[]"),
                is_required=f.is_required,
                is_active=f.is_active,
                sort_order=f.sort_order,
                created_at=f.created_at.isoformat(),
                updated_at=f.updated_at.isoformat(),
            )
            for f in fields
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{field_id}", response_model=CustomFieldResponse)
def get_custom_field(
    field_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a custom field by ID."""
    service = CustomFieldService(db, current_user.company_id)

    try:
        field = service.get_field(field_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return CustomFieldResponse(
        id=field.id,
        name=field.name,
        field_key=field.field_key,
        field_type=field.field_type,
        config=json.loads(field.config or "{}"),
        applicable_categories=json.loads(field.applicable_categories or "[]"),
        is_required=field.is_required,
        is_active=field.is_active,
        sort_order=field.sort_order,
        created_at=field.created_at.isoformat(),
        updated_at=field.updated_at.isoformat(),
    )


@router.put("/{field_id}", response_model=CustomFieldResponse)
def update_custom_field(
    field_id: str,
    data: CustomFieldUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a custom field."""
    service = CustomFieldService(db, current_user.company_id)

    try:
        field = service.update_field(
            field_id=field_id,
            name=data.name,
            config=data.config,
            applicable_categories=data.applicable_categories,
            is_required=data.is_required,
            sort_order=data.sort_order,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CustomFieldResponse(
        id=field.id,
        name=field.name,
        field_key=field.field_key,
        field_type=field.field_type,
        config=json.loads(field.config or "{}"),
        applicable_categories=json.loads(field.applicable_categories or "[]"),
        is_required=field.is_required,
        is_active=field.is_active,
        sort_order=field.sort_order,
        created_at=field.created_at.isoformat(),
        updated_at=field.updated_at.isoformat(),
    )


@router.delete("/{field_id}")
def delete_custom_field(
    field_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a custom field (soft delete)."""
    service = CustomFieldService(db, current_user.company_id)

    try:
        service.delete_field(field_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"success": True, "message": "Custom field deleted"}


@router.post("/validate")
def validate_field_value(
    data: FieldValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate a value against a custom field's type and config."""
    service = CustomFieldService(db, current_user.company_id)

    is_valid, error = service.validate_field_value(data.field_key, data.value)

    return {
        "field_key": data.field_key,
        "is_valid": is_valid,
        "error": error,
    }


@router.post("/validate-ticket")
def validate_ticket_fields(
    data: TicketFieldsValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate all custom field values for a ticket."""
    service = CustomFieldService(db, current_user.company_id)

    is_valid, errors = service.validate_ticket_fields(
        category=data.category,
        field_values=data.field_values,
    )

    return {
        "is_valid": is_valid,
        "errors": errors,
    }
