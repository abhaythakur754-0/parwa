"""
PARWA Compliance API Routes.
Provides endpoints for GDPR requests, data export, data deletion, and audit logs.
All data access is company-scoped for RLS enforcement.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.models.compliance_request import (
    ComplianceRequest,
    ComplianceRequestType,
    ComplianceRequestStatus,
)
from backend.models.audit_trail import AuditTrail
from backend.models.user import User, RoleEnum
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.core_functions.security import (
    decode_access_token,
    sanitize_input,
)

# Initialize router and logger
router = APIRouter(prefix="/compliance", tags=["Compliance"])
logger = get_logger(__name__)
settings = get_settings()
security = HTTPBearer()


# --- Pydantic Schemas ---

class GDPRExportRequest(BaseModel):
    """Request schema for GDPR data export."""
    customer_email: EmailStr = Field(..., description="Customer email to export data for")


class GDPRDeleteRequest(BaseModel):
    """Request schema for GDPR data deletion."""
    customer_email: EmailStr = Field(..., description="Customer email to delete data for")
    confirm: bool = Field(..., description="Confirmation that deletion is intended")


class RetentionCheckRequest(BaseModel):
    """Request schema for data retention check."""
    customer_email: Optional[EmailStr] = Field(None, description="Customer email to check")
    ticket_id: Optional[uuid.UUID] = Field(None, description="Specific ticket ID to check")


class ComplianceRequestResponse(BaseModel):
    """Response schema for a compliance request."""
    id: uuid.UUID
    company_id: uuid.UUID
    request_type: str
    customer_email: str
    status: str
    requested_at: datetime
    completed_at: Optional[datetime]
    result_url: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ComplianceRequestListResponse(BaseModel):
    """Response schema for listing compliance requests."""
    requests: List[ComplianceRequestResponse]
    total: int
    page: int
    page_size: int


class AuditLogResponse(BaseModel):
    """Response schema for an audit log entry."""
    id: uuid.UUID
    company_id: uuid.UUID
    ticket_id: Optional[uuid.UUID]
    actor: str
    action: str
    details: Dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Response schema for listing audit log entries."""
    entries: List[AuditLogResponse]
    total: int
    page: int
    page_size: int


class RetentionStatusResponse(BaseModel):
    """Response schema for retention status check."""
    customer_email: Optional[str]
    ticket_id: Optional[uuid.UUID]
    retention_days: int
    deletion_scheduled: bool
    deletion_date: Optional[datetime]
    message: str


class MessageResponse(BaseModel):
    """Generic message response schema."""
    message: str = Field(..., description="Response message")
    request_id: Optional[uuid.UUID] = Field(None, description="Related request ID")


# --- Helper Functions ---

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extract and validate the current user from JWT token.

    Args:
        credentials: HTTP Bearer credentials containing the JWT token.
        db: Async database session.

    Returns:
        User: The authenticated user instance.

    Raises:
        HTTPException: If token is invalid, expired, or user not found.
    """
    token = credentials.credentials

    try:
        payload = decode_access_token(token, settings.secret_key.get_secret_value())
    except ValueError as e:
        logger.warning({"event": "token_decode_failed", "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


def mask_email(email: str) -> str:
    """
    Mask email for privacy in responses.

    Args:
        email: The email address to mask.

    Returns:
        str: Masked email address.
    """
    if not email or "@" not in email:
        return email
    parts = email.split("@")
    if len(parts[0]) <= 3:
        return f"{parts[0][0]}***@{parts[1]}"
    return f"{parts[0][:3]}***@{parts[1]}"


# --- API Endpoints ---

@router.post(
    "/gdpr/export",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request GDPR data export",
    description="Create a new GDPR data export request for a customer."
)
async def request_gdpr_export(
    request: GDPRExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """
    Create a GDPR data export request.

    This endpoint initiates a data export request for a customer's data
    under GDPR Article 20 (Right to data portability).

    Args:
        request: GDPR export request data containing customer email.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        MessageResponse: Success message with request ID.

    Raises:
        HTTPException: 400 if there's an existing pending request.
    """
    # Sanitize input
    customer_email = sanitize_input(request.customer_email.lower())

    # Check for existing pending/processing request for same email
    existing_result = await db.execute(
        select(ComplianceRequest).where(
            and_(
                ComplianceRequest.company_id == current_user.company_id,
                ComplianceRequest.customer_email == customer_email,
                ComplianceRequest.request_type == ComplianceRequestType.gdpr_export,
                ComplianceRequest.status.in_([
                    ComplianceRequestStatus.pending,
                    ComplianceRequestStatus.processing
                ])
            )
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pending or processing export request already exists for this email",
        )

    # Create new compliance request
    new_request = ComplianceRequest(
        company_id=current_user.company_id,
        request_type=ComplianceRequestType.gdpr_export,
        customer_email=customer_email,
        status=ComplianceRequestStatus.pending,
    )

    db.add(new_request)
    await db.flush()
    await db.refresh(new_request)

    logger.info({
        "event": "gdpr_export_requested",
        "request_id": str(new_request.id),
        "company_id": str(current_user.company_id),
        "customer_email": mask_email(customer_email),
    })

    return MessageResponse(
        message="GDPR export request created successfully. You will be notified when the export is ready.",
        request_id=new_request.id,
    )


@router.post(
    "/gdpr/delete",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request GDPR data deletion",
    description="Create a new GDPR data deletion request for a customer."
)
async def request_gdpr_delete(
    request: GDPRDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """
    Create a GDPR data deletion request.

    This endpoint initiates a data deletion request for a customer's data
    under GDPR Article 17 (Right to erasure).

    Args:
        request: GDPR delete request data containing customer email and confirmation.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        MessageResponse: Success message with request ID.

    Raises:
        HTTPException: 400 if confirmation is False or existing pending request.
    """
    # Validate confirmation
    if not request.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deletion must be explicitly confirmed",
        )

    # Sanitize input
    customer_email = sanitize_input(request.customer_email.lower())

    # Check for existing pending/processing request for same email
    existing_result = await db.execute(
        select(ComplianceRequest).where(
            and_(
                ComplianceRequest.company_id == current_user.company_id,
                ComplianceRequest.customer_email == customer_email,
                ComplianceRequest.request_type == ComplianceRequestType.gdpr_delete,
                ComplianceRequest.status.in_([
                    ComplianceRequestStatus.pending,
                    ComplianceRequestStatus.processing
                ])
            )
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pending or processing deletion request already exists for this email",
        )

    # Create new compliance request
    new_request = ComplianceRequest(
        company_id=current_user.company_id,
        request_type=ComplianceRequestType.gdpr_delete,
        customer_email=customer_email,
        status=ComplianceRequestStatus.pending,
    )

    db.add(new_request)
    await db.flush()
    await db.refresh(new_request)

    logger.info({
        "event": "gdpr_delete_requested",
        "request_id": str(new_request.id),
        "company_id": str(current_user.company_id),
        "customer_email": mask_email(customer_email),
        "requested_by": str(current_user.id),
    })

    return MessageResponse(
        message="GDPR deletion request created successfully. Data will be deleted after the retention period.",
        request_id=new_request.id,
    )


@router.get(
    "/requests",
    response_model=ComplianceRequestListResponse,
    summary="List compliance requests",
    description="List all compliance requests with optional filtering."
)
async def list_compliance_requests(
    request_type: Optional[ComplianceRequestType] = Query(
        None, alias="type", description="Filter by request type"
    ),
    status_filter: Optional[ComplianceRequestStatus] = Query(
        None, alias="status", description="Filter by status"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ComplianceRequestListResponse:
    """
    List compliance requests with filtering.

    Args:
        request_type: Filter by request type (gdpr_export, gdpr_delete, etc.).
        status_filter: Filter by status (pending, processing, completed, failed).
        page: Page number (1-indexed).
        page_size: Number of items per page.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        ComplianceRequestListResponse: List of requests with pagination info.
    """
    # Build query with company scoping (RLS enforcement)
    conditions = [ComplianceRequest.company_id == current_user.company_id]

    if request_type:
        conditions.append(ComplianceRequest.request_type == request_type)
    if status_filter:
        conditions.append(ComplianceRequest.status == status_filter)

    # Count total
    count_query = select(ComplianceRequest).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    # Get paginated results
    offset = (page - 1) * page_size
    query = select(ComplianceRequest).where(and_(*conditions)).order_by(
        ComplianceRequest.created_at.desc()
    ).offset(offset).limit(page_size)

    result = await db.execute(query)
    requests = result.scalars().all()

    logger.info({
        "event": "compliance_requests_listed",
        "company_id": str(current_user.company_id),
        "total": total,
        "page": page,
        "filters": {
            "type": request_type.value if request_type else None,
            "status": status_filter.value if status_filter else None,
        }
    })

    return ComplianceRequestListResponse(
        requests=[
            ComplianceRequestResponse(
                id=r.id,
                company_id=r.company_id,
                request_type=r.request_type.value,
                customer_email=mask_email(r.customer_email),
                status=r.status.value,
                requested_at=r.requested_at,
                completed_at=r.completed_at,
                result_url=r.result_url,
                created_at=r.created_at,
            )
            for r in requests
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/audit-log",
    response_model=AuditLogListResponse,
    summary="Get audit log entries",
    description="Retrieve audit log entries with optional filtering."
)
async def list_audit_log(
    ticket_id: Optional[uuid.UUID] = Query(None, description="Filter by ticket ID"),
    actor: Optional[str] = Query(None, description="Filter by actor"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    start_date: Optional[datetime] = Query(None, description="Filter entries after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter entries before this date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> AuditLogListResponse:
    """
    List audit log entries with filtering.

    Audit logs are immutable and provide a complete history of all actions
    taken within the system for compliance and debugging purposes.

    Args:
        ticket_id: Filter by associated ticket ID.
        actor: Filter by actor (user or system component).
        action: Filter by action type.
        start_date: Filter entries after this timestamp.
        end_date: Filter entries before this timestamp.
        page: Page number (1-indexed).
        page_size: Number of items per page.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        AuditLogListResponse: List of audit entries with pagination info.
    """
    # Build query with company scoping (RLS enforcement)
    conditions = [AuditTrail.company_id == current_user.company_id]

    if ticket_id:
        conditions.append(AuditTrail.ticket_id == ticket_id)
    if actor:
        conditions.append(AuditTrail.actor == sanitize_input(actor))
    if action:
        conditions.append(AuditTrail.action == sanitize_input(action))
    if start_date:
        conditions.append(AuditTrail.created_at >= start_date)
    if end_date:
        conditions.append(AuditTrail.created_at <= end_date)

    # Count total
    count_query = select(AuditTrail).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    # Get paginated results
    offset = (page - 1) * page_size
    query = select(AuditTrail).where(and_(*conditions)).order_by(
        AuditTrail.created_at.desc()
    ).offset(offset).limit(page_size)

    result = await db.execute(query)
    entries = result.scalars().all()

    logger.info({
        "event": "audit_log_listed",
        "company_id": str(current_user.company_id),
        "total": total,
        "page": page,
        "requested_by": str(current_user.id),
    })

    return AuditLogListResponse(
        entries=[
            AuditLogResponse(
                id=e.id,
                company_id=e.company_id,
                ticket_id=e.ticket_id,
                actor=e.actor,
                action=e.action,
                details=e.details if e.details else {},
                created_at=e.created_at,
            )
            for e in entries
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/audit-log/{entry_id}",
    response_model=AuditLogResponse,
    summary="Get specific audit log entry",
    description="Retrieve a specific audit log entry by ID."
)
async def get_audit_log_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> AuditLogResponse:
    """
    Get a specific audit log entry by ID.

    Args:
        entry_id: The audit log entry UUID.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        AuditLogResponse: The audit log entry data.

    Raises:
        HTTPException: 404 if entry not found or not in user's company.
    """
    result = await db.execute(
        select(AuditTrail).where(
            and_(
                AuditTrail.id == entry_id,
                AuditTrail.company_id == current_user.company_id
            )
        )
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log entry not found",
        )

    logger.info({
        "event": "audit_log_entry_retrieved",
        "entry_id": str(entry_id),
        "company_id": str(current_user.company_id),
        "requested_by": str(current_user.id),
    })

    return AuditLogResponse(
        id=entry.id,
        company_id=entry.company_id,
        ticket_id=entry.ticket_id,
        actor=entry.actor,
        action=entry.action,
        details=entry.details if entry.details else {},
        created_at=entry.created_at,
    )


@router.post(
    "/retention/check",
    response_model=RetentionStatusResponse,
    summary="Check data retention status",
    description="Check the data retention status for a customer or specific ticket."
)
async def check_retention_status(
    request: RetentionCheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> RetentionStatusResponse:
    """
    Check data retention status for a customer or ticket.

    GDPR requires data to be retained only for as long as necessary.
    This endpoint allows checking when data will be deleted.

    Args:
        request: Retention check request with customer email or ticket ID.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        RetentionStatusResponse: Retention status information.

    Raises:
        HTTPException: 400 if neither email nor ticket_id provided.
    """
    if not request.customer_email and not request.ticket_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either customer_email or ticket_id must be provided",
        )

    # Default retention period (90 days for GDPR compliance)
    retention_days = 90

    # Check for existing deletion request
    deletion_scheduled = False
    deletion_date = None

    if request.customer_email:
        customer_email = sanitize_input(request.customer_email.lower())

        # Check for existing deletion request
        deletion_request_result = await db.execute(
            select(ComplianceRequest).where(
                and_(
                    ComplianceRequest.company_id == current_user.company_id,
                    ComplianceRequest.customer_email == customer_email,
                    ComplianceRequest.request_type == ComplianceRequestType.gdpr_delete,
                    ComplianceRequest.status.in_([
                        ComplianceRequestStatus.pending,
                        ComplianceRequestStatus.processing
                    ])
                )
            )
        )
        deletion_request = deletion_request_result.scalar_one_or_none()

        if deletion_request:
            deletion_scheduled = True
            # Deletion typically happens 30 days after request
            deletion_date = deletion_request.requested_at.replace(
                tzinfo=timezone.utc
            ) + __import__('datetime').timedelta(days=30)

    logger.info({
        "event": "retention_status_checked",
        "company_id": str(current_user.company_id),
        "customer_email": mask_email(request.customer_email) if request.customer_email else None,
        "ticket_id": str(request.ticket_id) if request.ticket_id else None,
        "requested_by": str(current_user.id),
    })

    message = f"Data retention period is {retention_days} days."
    if deletion_scheduled:
        message += f" Deletion is scheduled for {deletion_date.strftime('%Y-%m-%d')}."

    return RetentionStatusResponse(
        customer_email=mask_email(request.customer_email) if request.customer_email else None,
        ticket_id=request.ticket_id,
        retention_days=retention_days,
        deletion_scheduled=deletion_scheduled,
        deletion_date=deletion_date,
        message=message,
    )
