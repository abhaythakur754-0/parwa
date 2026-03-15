import uuid
import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.models.usage_log import AITier

class UsageLogCreate(BaseModel):
    log_date: datetime.date
    ai_tier: AITier
    request_count: int = Field(default=0, ge=0)
    token_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    avg_latency_ms: Optional[float] = None

class UsageLogResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    log_date: datetime.date
    ai_tier: AITier
    request_count: int
    token_count: int
    error_count: int
    avg_latency_ms: Optional[float] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
