"""
PARWA Customers API - Customer Management Endpoints (Day 30)

Implements F-070: Customer management API.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.exceptions import NotFoundError, ValidationError
from app.services.customer_service import CustomerService
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerMergeRequest,
    CustomerChannelCreate,
    CustomerChannelResponse,
)


router = APIRouter(
    prefix="/api/customers",
    tags=["customers"],
    dependencies=[Depends(require_roles("owner", "admin", "agent"))],
)


def _customer_to_response(customer: Any) -> Dict[str, Any]:
    """Convert Customer model to response dict."""
    import json

    metadata_json = {}
    if customer.metadata_json:
        try:
            metadata_json = json.loads(customer.metadata_json)
        except (json.JSONDecodeError, TypeError):
            metadata_json = {}

    return {
        "id": customer.id,
        "email": customer.email,
        "phone": customer.phone,
        "name": customer.name,
        "external_id": customer.external_id,
        "company_id": customer.company_id,
        "is_verified": customer.metadata_json and json.loads(customer.metadata_json).get("verified", False) if customer.metadata_json else False,
        "metadata_json": metadata_json,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
        "updated_at": customer.updated_at.isoformat() if customer.updated_at else None,
    }


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer",
)
async def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Create a new customer."""
    company_id = current_user.get("company_id")

    service = CustomerService(db, company_id)

    try:
        customer = service.create_customer(
            email=data.email,
            phone=data.phone,
            name=data.name,
            external_id=data.external_id,
            metadata_json=data.metadata_json,
        )
        return _customer_to_response(customer)

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    summary="List customers",
)
async def list_customers(
    search: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    external_id: Optional[str] = Query(None),
    has_open_tickets: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """List customers with filters and pagination."""
    company_id = current_user.get("company_id")

    service = CustomerService(db, company_id)

    customers, total = service.list_customers(
        search=search,
        email=email,
        phone=phone,
        external_id=external_id,
        has_open_tickets=has_open_tickets,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [_customer_to_response(c) for c in customers],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer",
)
async def get_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Get customer by ID."""
    company_id = current_user.get("company_id")

    service = CustomerService(db, company_id)

    try:
        customer = service.get_customer(customer_id)
        return _customer_to_response(customer)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update customer",
)
async def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Update customer fields."""
    company_id = current_user.get("company_id")

    service = CustomerService(db, company_id)

    try:
        customer = service.update_customer(
            customer_id=customer_id,
            email=data.email,
            phone=data.phone,
            name=data.name,
            external_id=data.external_id,
            metadata_json=data.metadata_json,
        )
        return _customer_to_response(customer)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{customer_id}",
    summary="Delete customer",
)
async def delete_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Delete a customer (anonymizes data)."""
    company_id = current_user.get("company_id")

    service = CustomerService(db, company_id)

    try:
        service.delete_customer(customer_id)
        return {"deleted": True, "customer_id": customer_id}

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{customer_id}/tickets",
    summary="Get customer tickets",
)
async def get_customer_tickets(
    customer_id: str,
    status: Optional[List[str]] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Get tickets for a customer."""
    company_id = current_user.get("company_id")

    service = CustomerService(db, company_id)

    try:
        tickets, total = service.get_customer_tickets(
            customer_id=customer_id,
            status=status,
            page=page,
            page_size=page_size,
        )

        return {
            "items": [
                {
                    "id": t.id,
                    "subject": t.subject,
                    "status": t.status,
                    "priority": t.priority,
                    "channel": t.channel,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in tickets
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{customer_id}/channels",
    summary="Get customer channels",
)
async def get_customer_channels(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Get channels linked to a customer."""
    company_id = current_user.get("company_id")

    service = CustomerService(db, company_id)

    try:
        channels = service.get_customer_channels(customer_id)

        return [
            {
                "id": c.id,
                "customer_id": c.customer_id,
                "channel_type": c.channel_type,
                "external_id": c.external_id,
                "is_verified": c.is_verified,
                "verified_at": c.verified_at.isoformat() if c.verified_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in channels
        ]

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/{customer_id}/channels",
    status_code=status.HTTP_201_CREATED,
    summary="Link channel to customer",
)
async def link_channel(
    customer_id: str,
    data: CustomerChannelCreate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Link a communication channel to a customer."""
    company_id = current_user.get("company_id")

    service = CustomerService(db, company_id)

    try:
        channel = service.link_channel(
            customer_id=customer_id,
            channel_type=data.channel_type,
            external_id=data.external_id,
            is_verified=data.is_verified,
        )

        return {
            "id": channel.id,
            "customer_id": channel.customer_id,
            "channel_type": channel.channel_type,
            "external_id": channel.external_id,
            "is_verified": channel.is_verified,
            "created_at": channel.created_at.isoformat() if channel.created_at else None,
        }

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{customer_id}/channels/{channel_id}",
    summary="Unlink channel from customer",
)
async def unlink_channel(
    customer_id: str,
    channel_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Unlink a channel from a customer."""
    company_id = current_user.get("company_id")

    service = CustomerService(db, company_id)

    try:
        service.unlink_channel(customer_id, channel_id)
        return {"unlinked": True, "channel_id": channel_id}

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/merge",
    summary="Merge customers",
)
async def merge_customers(
    data: CustomerMergeRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Merge multiple customers into one."""
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = CustomerService(db, company_id)

    try:
        customer = service.merge_customers(
            primary_customer_id=data.primary_customer_id,
            merged_customer_ids=data.merged_customer_ids,
            reason=data.reason,
            user_id=user_id,
        )

        return {
            "id": customer.id,
            "email": customer.email,
            "phone": customer.phone,
            "name": customer.name,
            "merged_count": len(data.merged_customer_ids),
        }

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
