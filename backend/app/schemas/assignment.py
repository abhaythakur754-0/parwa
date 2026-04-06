"""
PARWA Assignment Schemas

Pydantic models for ticket assignment rules and scoring.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


# ── Assignment Rule Schemas ───────────────────────────────────────────────────


class AssignmentRuleCreate(BaseModel):
    """Schema for creating an assignment rule."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable rule name",
    )
    conditions: Dict[str, Any] = Field(
        ...,
        description="Rule conditions (e.g., category, priority filters)",
    )
    action: Dict[str, Any] = Field(
        ...,
        description="Action to take when conditions match (e.g., assign to user/team)",
    )
    priority_order: int = Field(
        default=0,
        ge=0,
        description="Rule evaluation order (lower = higher priority)",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the rule is active",
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Rule name cannot be blank")
        return v.strip()


class AssignmentRuleUpdate(BaseModel):
    """Schema for updating an assignment rule."""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Human-readable rule name",
    )
    conditions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Rule conditions",
    )
    action: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Action to take when conditions match",
    )
    priority_order: Optional[int] = Field(
        default=None,
        ge=0,
        description="Rule evaluation order",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Whether the rule is active",
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("Rule name cannot be blank")
            return v.strip()
        return v


class AssignmentRuleResponse(BaseModel):
    """Schema for assignment rule response."""

    id: str
    name: str
    conditions: Dict[str, Any]
    action: Dict[str, Any]
    priority_order: int
    is_active: bool
    company_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Assignment Scoring Schemas ───────────────────────────────────────────────


class AssignmentScore(BaseModel):
    """Schema for assignment scoring result."""

    ticket_id: str = Field(
        ...,
        description="Ticket being assigned",
    )
    candidate_scores: Dict[str, float] = Field(
        ...,
        description="Map of user_id to assignment score",
    )
    final_assignee_id: Optional[str] = Field(
        default=None,
        description="ID of the selected assignee (user or team)",
    )
    final_assignee_type: Optional[str] = Field(
        default=None,
        description="Type of assignee: 'user' or 'team'",
    )
    reason: str = Field(
        ...,
        description="Explanation of assignment decision",
    )


# ── Ticket Assignment Record Schemas ─────────────────────────────────────────


class TicketAssignmentResponse(BaseModel):
    """Schema for ticket assignment record response."""

    id: str
    ticket_id: str
    assignee_type: str = Field(
        description="Type of assignee: 'user', 'team', or 'unassigned'",
    )
    assignee_id: Optional[str] = Field(
        default=None,
        description="ID of the assignee",
    )
    score: Optional[float] = Field(
        default=None,
        description="Assignment score (if rule-based)",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Reason for assignment",
    )
    assigned_at: datetime
    assigned_by: Optional[str] = Field(
        default=None,
        description="User ID who made the assignment (if manual)",
    )

    model_config = {"from_attributes": True}
