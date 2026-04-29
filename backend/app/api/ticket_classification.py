"""
PARWA Ticket Classification API - F-049 Classification Endpoints (Day 28)

Implements F-049: Ticket classification API with:
- Trigger classification (AI or manual override)
- Get classification result
- Human correction workflow
- Correction list for training data

BC-001: All endpoints are tenant-isolated.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.services.classification_service import (
    ClassificationService,
    IntentCategory,
    UrgencyLevel,
)
from app.exceptions import NotFoundError


router = APIRouter(
    prefix="/tickets",
    tags=["ticket-classification"],
    dependencies=[Depends(require_roles("owner", "admin", "agent"))],
)


# ── SCHEMAS ────────────────────────────────────────────────────────────────

class ClassificationResult(BaseModel):
    """Classification result."""
    ticket_id: str
    intent: str
    urgency: str
    confidence: float
    intent_confidence: Optional[float] = None
    urgency_confidence: Optional[float] = None
    already_classified: Optional[bool] = None
    suggested_priority: Optional[str] = None


class TextClassificationRequest(BaseModel):
    """Text classification request."""
    subject: Optional[str] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TextClassificationResult(BaseModel):
    """Text classification result."""
    intent: str
    urgency: str
    confidence: float
    intent_confidence: float
    urgency_confidence: float
    all_intent_scores: Dict[str, float]
    all_urgency_scores: Dict[str, float]
    suggested_priority: str


class CorrectionRequest(BaseModel):
    """Correction request."""
    corrected_intent: str = Field(...,
                                  description="Correct intent classification")
    corrected_urgency: Optional[str] = Field(
        None, description="Correct urgency level")
    reason: Optional[str] = Field(None, description="Reason for correction")


class CorrectionResponse(BaseModel):
    """Correction response."""
    id: str
    ticket_id: str
    original_intent: str
    corrected_intent: str
    original_urgency: Optional[str]
    corrected_urgency: Optional[str]
    corrected_by: Optional[str]
    reason: Optional[str]
    created_at: str


class CorrectionListResponse(BaseModel):
    """Correction list response."""
    items: List[CorrectionResponse]
    total: int
    page: int
    page_size: int


class ClassificationStatsResponse(BaseModel):
    """Classification statistics response."""
    total_classifications: int
    total_corrections: int
    correction_rate: float
    average_confidence: float
    intent_distribution: Dict[str, int]
    urgency_distribution: Dict[str, int]


class IntentListResponse(BaseModel):
    """Available intents response."""
    intents: List[str]
    urgencies: List[str]


# ── ENDPOINTS ──────────────────────────────────────────────────────────────

@router.post(
    "/{ticket_id}/classify",
    response_model=ClassificationResult,
    summary="Trigger ticket classification",
)
async def classify_ticket(
    ticket_id: str,
    force_reclassify: bool = Query(
        False, description="Force reclassification"
    ),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Trigger classification for a ticket.

    F-049: Classify ticket intent and urgency.
    Week 4: Rule-based classification.
    Week 9: AI-based classification.
    """
    company_id = current_user.get("company_id")

    service = ClassificationService(db, company_id)

    try:
        result = service.classify(ticket_id, force_reclassify)
        return ClassificationResult(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/{ticket_id}/classification",
    response_model=ClassificationResult,
    summary="Get ticket classification",
)
async def get_classification(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Get classification for a ticket.

    F-049: Retrieve existing classification.
    """
    company_id = current_user.get("company_id")

    service = ClassificationService(db, company_id)

    try:
        result = service.classify(ticket_id, force_reclassify=False)
        return ClassificationResult(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/{ticket_id}/classification",
    response_model=CorrectionResponse,
    summary="Correct ticket classification",
)
async def correct_classification(
    ticket_id: str,
    data: CorrectionRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Correct ticket classification (human override).

    F-049: Human correction to AI classification.
    Corrections are logged for training data.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    # Validate intent
    if data.corrected_intent not in IntentCategory.ALL:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid intent. Must be one of: {IntentCategory.ALL}",
        )

    # Validate urgency if provided
    if data.corrected_urgency and data.corrected_urgency not in UrgencyLevel.ALL:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid urgency. Must be one of: {UrgencyLevel.ALL}",
        )

    service = ClassificationService(db, company_id)

    try:
        # Get current classification
        current = service.classify(ticket_id, force_reclassify=False)

        # Record correction
        correction = service.record_correction(
            ticket_id=ticket_id,
            original_intent=current["intent"],
            corrected_intent=data.corrected_intent,
            original_urgency=current.get("urgency"),
            corrected_urgency=data.corrected_urgency,
            corrected_by=user_id,
            reason=data.reason,
        )

        return CorrectionResponse(
            id=correction.id,
            ticket_id=correction.ticket_id,
            original_intent=correction.original_intent,
            corrected_intent=correction.corrected_intent,
            original_urgency=correction.original_urgency,
            corrected_urgency=correction.corrected_urgency,
            corrected_by=correction.corrected_by,
            reason=correction.reason,
            created_at=correction.created_at.isoformat(),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/classify-text",
    response_model=TextClassificationResult,
    summary="Classify text without ticket",
)
async def classify_text(
    data: TextClassificationRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Classify text without creating a ticket.

    F-049: Preview classification before ticket creation.
    Useful for UI to suggest category/priority.
    """
    company_id = current_user.get("company_id")

    service = ClassificationService(db, company_id)

    result = service.classify_text(
        subject=data.subject,
        message=data.message,
        metadata=data.metadata,
    )

    return TextClassificationResult(**result)


@router.get(
    "/classification/corrections",
    response_model=CorrectionListResponse,
    summary="List all corrections",
)
async def list_corrections(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    intent: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """List all corrections for training data.

    F-049: Export corrections for AI model training.
    """
    company_id = current_user.get("company_id")

    service = ClassificationService(db, company_id)

    corrections, total = service.get_corrections(
        page=page,
        page_size=page_size,
        intent_filter=intent,
    )

    return CorrectionListResponse(
        items=[CorrectionResponse(**c) for c in corrections],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/classification/stats",
    response_model=ClassificationStatsResponse,
    summary="Get classification statistics",
)
async def get_classification_stats(
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Get classification statistics.

    F-049: Overview of classification performance.
    """
    company_id = current_user.get("company_id")

    service = ClassificationService(db, company_id)

    stats = service.get_classification_stats()

    return ClassificationStatsResponse(**stats)


@router.get(
    "/classification/intents",
    response_model=IntentListResponse,
    summary="Get available intents",
)
async def get_available_intents() -> Any:
    """Get available intent categories and urgency levels.

    F-049: List all valid classification values.
    """
    return IntentListResponse(
        intents=IntentCategory.ALL,
        urgencies=UrgencyLevel.ALL,
    )
