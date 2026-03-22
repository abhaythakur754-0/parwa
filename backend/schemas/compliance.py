import uuid
import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from backend.models.compliance_request import ComplianceRequestType, ComplianceRequestStatus

class ComplianceRequestCreate(BaseModel):
    request_type: ComplianceRequestType
    customer_email: EmailStr

class ComplianceRequestResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    request_type: ComplianceRequestType
    customer_email: EmailStr
    status: ComplianceRequestStatus
    requested_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None
    result_url: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class SLABreachCreate(BaseModel):
    ticket_id: uuid.UUID
    breach_phase: int = Field(ge=1, le=3)
    hours_overdue: float
    notified_to: str

class SLABreachResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    ticket_id: uuid.UUID
    breach_phase: int
    breach_triggered_at: datetime.datetime
    hours_overdue: float
    notified_to: str
    resolved_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
