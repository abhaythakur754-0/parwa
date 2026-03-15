from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field
from backend.models.company import PlanTierEnum


class CompanyBase(BaseModel):
    name: str = Field(..., description="The name of the company")
    industry: str = Field(..., description="The industry the company operates in")
    plan_tier: PlanTierEnum = Field(..., description="The subscription tier")
    is_active: bool = Field(default=True, description="Whether the company is currently active")


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    plan_tier: Optional[PlanTierEnum] = None
    is_active: Optional[bool] = None


class CompanyResponse(CompanyBase):
    id: uuid.UUID
    rls_policy_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
