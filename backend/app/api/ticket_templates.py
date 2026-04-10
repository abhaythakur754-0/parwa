"""
PARWA Template API - Response Template Endpoints (Day 33: MF07)

Endpoints for managing response templates/macros.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.exceptions import NotFoundError, ValidationError
from app.services.template_service import TemplateService
from database.models.core import User


router = APIRouter(prefix="/templates", tags=["Templates"])


# ── Schemas ────────────────────────────────────────────────────────────────


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    template_text: str = Field(..., min_length=1)
    intent_type: Optional[str] = Field(None, max_length=100)
    variables: Optional[List[str]] = None
    language: str = Field("en", max_length=10)


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    template_text: Optional[str] = Field(None, min_length=1)
    intent_type: Optional[str] = Field(None, max_length=100)
    variables: Optional[List[str]] = None
    language: Optional[str] = Field(None, max_length=10)


class TemplateApply(BaseModel):
    variables: Optional[Dict[str, Any]] = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    template_text: str
    intent_type: Optional[str]
    variables: List[str]
    language: str
    is_active: bool
    version: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("", response_model=TemplateResponse)
def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new response template."""
    service = TemplateService(db, current_user.company_id)

    try:
        template = service.create_template(
            name=data.name,
            template_text=data.template_text,
            intent_type=data.intent_type,
            variables=data.variables,
            language=data.language,
            created_by=current_user.id,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return TemplateResponse(
        id=template.id,
        name=template.name,
        template_text=template.template_text,
        intent_type=template.intent_type,
        variables=service.get_template_variables(template.id),
        language=template.language,
        is_active=template.is_active,
        version=template.version,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.get("", response_model=Dict[str, Any])
def list_templates(
    intent_type: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List templates with filters."""
    service = TemplateService(db, current_user.company_id)

    templates, total = service.list_templates(
        intent_type=intent_type,
        language=language,
        is_active=is_active,
        search=search,
        page=page,
        page_size=page_size,
    )

    return {
        "templates": [
            TemplateResponse(
                id=t.id,
                name=t.name,
                template_text=t.template_text,
                intent_type=t.intent_type,
                variables=json.loads(t.variables or "[]"),
                language=t.language,
                is_active=t.is_active,
                version=t.version,
                created_at=t.created_at.isoformat(),
                updated_at=t.updated_at.isoformat(),
            )
            for t in templates
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


from datetime import datetime
import json


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a template by ID."""
    service = TemplateService(db, current_user.company_id)

    try:
        template = service.get_template(template_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return TemplateResponse(
        id=template.id,
        name=template.name,
        template_text=template.template_text,
        intent_type=template.intent_type,
        variables=json.loads(template.variables or "[]"),
        language=template.language,
        is_active=template.is_active,
        version=template.version,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.put("/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: str,
    data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a template."""
    service = TemplateService(db, current_user.company_id)

    try:
        template = service.update_template(
            template_id=template_id,
            name=data.name,
            template_text=data.template_text,
            intent_type=data.intent_type,
            variables=data.variables,
            language=data.language,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return TemplateResponse(
        id=template.id,
        name=template.name,
        template_text=template.template_text,
        intent_type=template.intent_type,
        variables=json.loads(template.variables or "[]"),
        language=template.language,
        is_active=template.is_active,
        version=template.version,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.delete("/{template_id}")
def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a template (soft delete)."""
    service = TemplateService(db, current_user.company_id)

    try:
        service.delete_template(template_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"success": True, "message": "Template deleted"}


@router.post("/{template_id}/apply")
def apply_template(
    template_id: str,
    data: TemplateApply,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply variables to a template and return rendered text."""
    service = TemplateService(db, current_user.company_id)

    try:
        rendered = service.apply_template(template_id, data.variables)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "template_id": template_id,
        "rendered_text": rendered,
    }


@router.get("/{template_id}/variables")
def get_template_variables(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get variables defined in a template."""
    service = TemplateService(db, current_user.company_id)

    try:
        variables = service.get_template_variables(template_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "template_id": template_id,
        "variables": variables,
    }
