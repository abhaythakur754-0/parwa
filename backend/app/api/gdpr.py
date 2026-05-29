"""
GDPR & Data Lifecycle API Endpoints.

BC-010: GDPR right-to-erasure compliance.
GDPR Art. 15: Right of access (data export).
GDPR Art. 17: Right to erasure (right to be forgotten).
GDPR Art. 20: Right to data portability.
GDPR Art. 7: Conditions for consent.

All endpoints require authentication and tenant scoping.
Admin-level endpoints require supervisor+ role.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.schemas.gdpr import (
    AuditImmutabilityCheck,
    ConsentResponse,
    ConsentUpdate,
    DataExportRequest,
    DataExportResponse,
    ErasureExecutionResult,
    ErasureRequestCreate,
    ErasureRequestResponse,
    ErasureRequestVerify,
    RetentionEnforcementResult,
    RetentionPolicyCreate,
    RetentionPolicyResponse,
)
from app.services.gdpr_service import (
    AuditImmutabilityService,
    GDPRConsentService,
    GDPRErasureService,
    GDPRExportService,
    GDPRRetentionService,
)
from database.base import get_db
from database.models.core import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/gdpr", tags=["gdpr"])


# ── Helper ────────────────────────────────────────────────────────


def _get_company_id(request: Request) -> str:
    """Extract company_id from request state (set by TenantMiddleware)."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail={"error": "AUTHORIZATION_ERROR", "message": "Tenant identification required"},
        )
    return company_id


# ── Right to Erasure Endpoints (GDPR Art. 17, BC-010) ────────────


@router.post(
    "/erasure-request",
    response_model=ErasureRequestResponse,
    summary="Create GDPR erasure request (Art. 17)",
    description="Submit a right-to-erasure request for a data subject. "
                "The request must be verified before execution.",
)
async def create_erasure_request(
    body: ErasureRequestCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new GDPR right-to-erasure request."""
    company_id = _get_company_id(request)

    service = GDPRErasureService(db)
    result = service.create_erasure_request(
        company_id=company_id,
        customer_email=body.customer_email,
        scope=body.scope,
        reason=body.reason,
        request_source=body.request_source,
        requested_by=current_user.id,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result)

    return result


@router.post(
    "/erasure-request/{erasure_id}/verify",
    response_model=ErasureRequestResponse,
    summary="Verify erasure request",
    description="Verify an erasure request before it can be executed. "
                "Requires supervisor+ role.",
)
async def verify_erasure_request(
    erasure_id: str,
    body: ErasureRequestVerify,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify an erasure request for execution."""
    company_id = _get_company_id(request)

    # Only supervisors and owners can verify erasure requests
    if current_user.role not in ("owner", "supervisor", "admin"):
        raise HTTPException(
            status_code=403,
            detail={"error": "AUTHORIZATION_ERROR", "message": "Only supervisors can verify erasure requests"},
        )

    service = GDPRErasureService(db)
    result = service.verify_erasure_request(
        erasure_request_id=erasure_id,
        company_id=company_id,
        verified=body.verified,
        verified_by=current_user.id,
    )

    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=result)

    return result


@router.post(
    "/erasure-request/{erasure_id}/execute",
    response_model=ErasureExecutionResult,
    summary="Execute erasure request (Art. 17, BC-010)",
    description="Execute a verified erasure request. Anonymizes customer PII, "
                "redacts messages, purges Redis caches. Audit trail is preserved.",
)
async def execute_erasure_request(
    erasure_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute a verified GDPR erasure request."""
    company_id = _get_company_id(request)

    # Only supervisors and owners can execute erasure requests
    if current_user.role not in ("owner", "supervisor", "admin"):
        raise HTTPException(
            status_code=403,
            detail={"error": "AUTHORIZATION_ERROR", "message": "Only supervisors can execute erasure requests"},
        )

    service = GDPRErasureService(db)
    result = service.execute_erasure(
        erasure_request_id=erasure_id,
        company_id=company_id,
        executed_by=current_user.id,
    )

    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=result)
    if result.get("status") == "not_verified":
        raise HTTPException(status_code=400, detail=result)

    return result


@router.get(
    "/erasure-request/{erasure_id}",
    response_model=ErasureRequestResponse,
    summary="Get erasure request status",
)
async def get_erasure_request(
    erasure_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status of an erasure request."""
    from database.models.gdpr import ErasureRequest

    company_id = _get_company_id(request)

    erasure = db.query(ErasureRequest).filter(
        ErasureRequest.id == erasure_id,
        ErasureRequest.company_id == company_id,
    ).first()

    if not erasure:
        raise HTTPException(status_code=404, detail={"error": "Erasure request not found"})

    return {
        "id": erasure.id,
        "company_id": erasure.company_id,
        "customer_email": erasure.customer_email,
        "scope": erasure.scope,
        "status": erasure.status,
        "verification_status": erasure.verification_status,
        "reason": erasure.reason,
        "request_source": erasure.request_source,
        "customers_anonymized": erasure.customers_anonymized,
        "tickets_affected": erasure.tickets_affected,
        "messages_redacted": erasure.messages_redacted,
        "redis_keys_purged": erasure.redis_keys_purged,
        "error_message": erasure.error_message,
        "requested_at": erasure.requested_at,
        "verified_at": erasure.verified_at,
        "completed_at": erasure.completed_at,
        "created_at": erasure.created_at,
    }


# ── Data Export / Portability Endpoints (GDPR Art. 15/20) ────────


@router.post(
    "/data-export",
    response_model=DataExportResponse,
    summary="Export customer data (Art. 15/20)",
    description="Export all data held about a customer in structured format. "
                "GDPR access request / data portability.",
)
async def export_customer_data(
    body: DataExportRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export all data for a customer (GDPR Art. 15/20)."""
    company_id = _get_company_id(request)

    service = GDPRExportService(db)
    result = service.export_customer_data(
        company_id=company_id,
        customer_email=body.customer_email,
        format=body.format,
        include_categories=body.include_categories,
    )

    return result


# ── Data Retention Endpoints ──────────────────────────────────────


@router.post(
    "/retention-policy",
    response_model=RetentionPolicyResponse,
    summary="Create data retention policy",
    description="Create or update a data retention policy for a specific data category.",
)
async def create_retention_policy(
    body: RetentionPolicyCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a data retention policy."""
    company_id = _get_company_id(request)

    # Only owners/admins can set retention policies
    if current_user.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail={"error": "AUTHORIZATION_ERROR", "message": "Only owners can set retention policies"},
        )

    service = GDPRRetentionService(db)
    result = service.create_retention_policy(
        company_id=company_id,
        category=body.category,
        retention_days=body.retention_days,
        action_on_expiry=body.action_on_expiry,
    )

    return {
        "id": result["id"],
        "company_id": result["company_id"],
        "category": result["category"],
        "retention_days": result["retention_days"],
        "action_on_expiry": result["action_on_expiry"],
        "is_active": True,
        "last_enforced_at": None,
        "last_records_affected": 0,
        "created_at": None,
    }


@router.post(
    "/retention/enforce",
    response_model=RetentionEnforcementResult,
    summary="Enforce data retention policies",
    description="Run data retention enforcement for the company. "
                "Supports dry_run mode to preview changes.",
)
async def enforce_retention(
    dry_run: bool = True,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enforce data retention policies."""
    company_id = _get_company_id(request)

    # Only owners/admins can enforce retention
    if current_user.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail={"error": "AUTHORIZATION_ERROR", "message": "Only owners can enforce retention"},
        )

    service = GDPRRetentionService(db)
    result = service.enforce_retention(
        company_id=company_id,
        dry_run=dry_run,
    )

    return result


# ── Audit Trail Immutability Check ───────────────────────────────


@router.get(
    "/audit-immutability",
    response_model=AuditImmutabilityCheck,
    summary="Verify audit trail immutability",
    description="Check that the audit_trail has no DELETE or UPDATE routes. "
                "Required for GDPR compliance and legal integrity.",
)
async def check_audit_immutability(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify that audit_trail is immutable (no DELETE/UPDATE API routes)."""
    service = AuditImmutabilityService(db)
    result = service.check_immutability()

    return {
        "has_delete_route": result["has_delete_route"],
        "has_update_route": result["has_update_route"],
        "is_immutable": result["is_immutable"],
        "details": result["details"],
    }


# ── Consent Management Endpoints (GDPR Art. 7) ───────────────────


@router.post(
    "/consent",
    response_model=ConsentResponse,
    summary="Record consent decision (Art. 7)",
    description="Record a consent decision (grant or withdraw) for a user.",
)
async def record_consent(
    body: ConsentUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a consent decision for the current user."""
    company_id = _get_company_id(request)

    service = GDPRConsentService(db)
    result = service.record_consent(
        company_id=company_id,
        user_id=current_user.id,
        consent_type=body.consent_type,
        granted=body.granted,
        consent_version=body.consent_version,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return result


@router.get(
    "/consent",
    response_model=List[ConsentResponse],
    summary="List consent records",
    description="List all consent records for the current user.",
)
async def list_consents(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all consent records for the current user."""
    company_id = _get_company_id(request)

    service = GDPRConsentService(db)
    return service.list_consents(
        company_id=company_id,
        user_id=current_user.id,
    )


@router.delete(
    "/consent/{consent_type}",
    response_model=ConsentResponse,
    summary="Withdraw consent (Art. 7)",
    description="Withdraw consent for a specific type. Creates a new record with granted=False.",
)
async def withdraw_consent(
    consent_type: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Withdraw consent for a specific type."""
    company_id = _get_company_id(request)

    service = GDPRConsentService(db)
    result = service.withdraw_consent(
        company_id=company_id,
        user_id=current_user.id,
        consent_type=consent_type,
    )

    return result
