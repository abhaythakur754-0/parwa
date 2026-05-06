from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class AuditTrailBase(BaseModel):
    action: str
    details: Dict[str, Any]

class AuditTrailCreate(AuditTrailBase):
    company_id: UUID
    ticket_id: Optional[UUID] = None
    actor: str

class AuditTrailResponse(AuditTrailBase):
    id: UUID
    company_id: UUID
    ticket_id: Optional[UUID] = None
    actor: str
    previous_hash: Optional[str] = None
    entry_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
