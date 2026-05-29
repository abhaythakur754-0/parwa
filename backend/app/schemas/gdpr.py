"""
GDPR & Data Lifecycle Pydantic Schemas.

BC-010: GDPR right-to-erasure compliance.
GDPR Art. 17: Right to erasure (right to be forgotten).
GDPR Art. 20: Right to data portability.
GDPR Art. 15: Right of access (data export).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, EmailStr


# ── Erasure Request Schemas ───────────────────────────────────────


class ErasureRequestCreate(BaseModel):
    """Schema for creating a new GDPR erasure request."""
    customer_email: str = Field(
        ..., description="Email of the data subject whose data should be erased"
    )
    scope: str = Field(
        default="full",
        description="Erasure scope: full, profile_only, messages_only, tickets_only",
        pattern="^(full|profile_only|messages_only|tickets_only)$",
    )
    reason: Optional[str] = Field(
        default=None, description="Reason for the erasure request"
    )
    request_source: str = Field(
        default="api",
        description="How the request was received: api, email, manual",
        pattern="^(api|email|manual)$",
    )


class ErasureRequestVerify(BaseModel):
    """Schema for verifying an erasure request before execution."""
    erasure_request_id: str = Field(
        ..., description="ID of the erasure request to verify"
    )
    verified: bool = Field(
        ..., description="Whether the request is verified for execution"
    )
    note: Optional[str] = Field(
        default=None, description="Optional note about verification"
    )


class ErasureRequestResponse(BaseModel):
    """Schema for erasure request response."""
    id: str
    company_id: str
    customer_email: str
    scope: str
    status: str
    verification_status: str
    reason: Optional[str] = None
    request_source: str
    customers_anonymized: int = 0
    tickets_affected: int = 0
    messages_redacted: int = 0
    redis_keys_purged: int = 0
    error_message: Optional[str] = None
    requested_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ErasureExecutionResult(BaseModel):
    """Schema for the result of executing an erasure request."""
    erasure_request_id: str
    status: str
    customers_anonymized: int = 0
    tickets_affected: int = 0
    messages_redacted: int = 0
    redis_keys_purged: int = 0
    audit_trail_preserved: bool = True
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None


# ── Data Export Schemas ───────────────────────────────────────────


class DataExportRequest(BaseModel):
    """Schema for GDPR data portability / access request (Art. 15/20)."""
    customer_email: str = Field(
        ..., description="Email of the data subject whose data should be exported"
    )
    format: str = Field(
        default="json",
        description="Export format: json or csv",
        pattern="^(json|csv)$",
    )
    include_categories: Optional[List[str]] = Field(
        default=None,
        description="Data categories to include. None = all categories.",
    )


class DataExportResponse(BaseModel):
    """Schema for data export response."""
    customer_email: str
    format: str
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Exported data organized by category",
    )
    categories_included: List[str] = Field(
        default_factory=list,
        description="List of data categories included in the export",
    )
    total_records: int = 0
    exported_at: Optional[datetime] = None


# ── Data Retention Schemas ───────────────────────────────────────


class RetentionPolicyCreate(BaseModel):
    """Schema for creating a data retention policy."""
    category: str = Field(
        ..., description="Data category (tickets, messages, customers, audit_logs, etc.)"
    )
    retention_days: int = Field(
        default=365, ge=1, description="Retention period in days"
    )
    action_on_expiry: str = Field(
        default="archive",
        description="Action on expiry: archive, delete, anonymize",
        pattern="^(archive|delete|anonymize)$",
    )


class RetentionPolicyResponse(BaseModel):
    """Schema for retention policy response."""
    id: str
    company_id: str
    category: str
    retention_days: int
    action_on_expiry: str
    is_active: bool
    last_enforced_at: Optional[datetime] = None
    last_records_affected: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RetentionEnforcementResult(BaseModel):
    """Schema for the result of running retention enforcement."""
    policies_enforced: int = 0
    total_records_affected: int = 0
    details: List[Dict[str, Any]] = Field(default_factory=list)


# ── Consent Management Schemas ───────────────────────────────────


class ConsentUpdate(BaseModel):
    """Schema for updating consent records."""
    consent_type: str = Field(
        ..., description="Consent type: gdpr, tcpa, call_recording, data_processing"
    )
    granted: bool = Field(
        ..., description="Whether consent is granted"
    )
    consent_version: str = Field(
        default="1.0", description="Version of the consent agreement"
    )


class ConsentResponse(BaseModel):
    """Schema for consent record response."""
    id: str
    company_id: str
    user_id: str
    consent_type: str
    consent_version: str
    granted: bool
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Audit Trail Immutability Check ───────────────────────────────


class AuditImmutabilityCheck(BaseModel):
    """Schema for audit trail immutability verification result."""
    has_delete_route: bool
    has_update_route: bool
    is_immutable: bool
    details: str
