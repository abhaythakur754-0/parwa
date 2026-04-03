"""
PARWA Identity API - Identity Resolution Endpoints (Day 30)

Implements F-070: Identity resolution API.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.exceptions import NotFoundError, ValidationError
from backend.app.services.identity_resolution_service import IdentityResolutionService
from backend.app.schemas.customer import (
    IdentityMatchRequest,
    IdentityMatchResponse,
)


router = APIRouter(prefix="/identity", tags=["identity"])


@router.post(
    "/resolve",
    summary="Resolve customer identity",
)
async def resolve_identity(
    data: IdentityMatchRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Resolve customer identity from multiple identifiers.

    Tries to match existing customer by any provided identifier.
    Creates new customer if no match and auto_create is True.
    """
    company_id = current_user.get("company_id")

    body = await request.json() if await request.body() else {}
    auto_create = body.get("auto_create", True)
    auto_link_threshold = body.get("auto_link_threshold")

    service = IdentityResolutionService(db, company_id)

    result = service.resolve_identity(
        email=data.email,
        phone=data.phone,
        social_id=data.social_id,
        auto_create=auto_create,
        auto_link_threshold=auto_link_threshold,
    )

    return result


@router.get(
    "/matches",
    summary="Get potential duplicate customers",
)
async def get_potential_duplicates(
    customer_id: Optional[str] = Query(None),
    min_confidence: float = Query(0.5, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Get potential duplicate customers.

    Returns list of customer pairs that might be duplicates.
    """
    company_id = current_user.get("company_id")

    service = IdentityResolutionService(db, company_id)

    duplicates = service.find_potential_duplicates(
        customer_id=customer_id,
        min_confidence=min_confidence,
    )

    return {
        "duplicates": duplicates,
        "total": len(duplicates),
    }


@router.get(
    "/logs",
    summary="Get identity match logs",
)
async def get_match_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Get identity match logs.

    Returns history of identity resolution attempts.
    """
    company_id = current_user.get("company_id")

    service = IdentityResolutionService(db, company_id)

    logs, total = service.get_match_logs(
        page=page,
        page_size=page_size,
    )

    return {
        "items": [
            {
                "id": log.id,
                "input_email": log.input_email,
                "input_phone": log.input_phone,
                "matched_customer_id": log.matched_customer_id,
                "match_method": log.match_method,
                "confidence_score": float(log.confidence_score) if log.confidence_score else None,
                "action_taken": log.action_taken,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/grandfathered",
    summary="Get grandfathered tickets",
)
async def get_grandfathered_tickets(
    customer_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """PS14: Get tickets with grandfathered plan tiers.

    Open tickets retain the plan tier at creation time.
    """
    company_id = current_user.get("company_id")

    service = IdentityResolutionService(db, company_id)

    tickets = service.get_grandfathered_tickets(customer_id)

    return {
        "items": tickets,
        "total": len(tickets),
    }


@router.post(
    "/resolve-batch",
    summary="Batch resolve identities",
)
async def batch_resolve_identities(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Resolve multiple identities in batch.

    Useful for bulk importing or syncing.
    """
    company_id = current_user.get("company_id")

    body = await request.json()
    identities = body.get("identities", [])

    if not identities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No identities provided",
        )

    if len(identities) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 identities per batch",
        )

    service = IdentityResolutionService(db, company_id)

    results = []
    for identity in identities:
        result = service.resolve_identity(
            email=identity.get("email"),
            phone=identity.get("phone"),
            social_id=identity.get("social_id"),
            auto_create=identity.get("auto_create", True),
        )
        results.append(result)

    return {
        "results": results,
        "total": len(results),
    }
