from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

from backend.models.support_ticket import (
    ChannelEnum,
    TicketStatusEnum,
    AITierEnum,
    SentimentEnum
)

class TicketBase(BaseModel):
    customer_email: EmailStr
    channel: ChannelEnum
    category: Optional[str] = None
    subject: str
    body: str

class TicketCreate(TicketBase):
    pass

class TicketUpdate(BaseModel):
    status: Optional[TicketStatusEnum] = None
    assigned_to: Optional[UUID] = None
    ai_recommendation: Optional[str] = None
    ai_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    ai_tier_used: Optional[AITierEnum] = None
    sentiment: Optional[SentimentEnum] = None
    resolved_at: Optional[datetime] = None

class TicketResponse(TicketBase):
    id: UUID
    company_id: UUID
    status: TicketStatusEnum
    assigned_to: Optional[UUID] = None
    ai_recommendation: Optional[str] = None
    ai_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    ai_tier_used: Optional[AITierEnum] = None
    sentiment: Optional[SentimentEnum] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
