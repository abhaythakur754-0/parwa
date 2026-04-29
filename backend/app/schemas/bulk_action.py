"""
PARWA Bulk Action Schemas

Pydantic models for bulk operations on tickets including merge/unmerge.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class BulkActionType(str, Enum):
    """Types of bulk actions available."""

    STATUS_CHANGE = "status_change"
    REASSIGN = "reassign"
    TAG = "tag"
    PRIORITY = "priority"
    CLOSE = "close"


# ── Bulk Action Request/Response Schemas ─────────────────────────────────────


class BulkActionRequest(BaseModel):
    """Schema for requesting a bulk action on tickets."""

    action_type: BulkActionType = Field(
        ...,
        description="Type of bulk action to perform",
    )
    ticket_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of ticket IDs to act on (max 500)",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific parameters (e.g., new_status, assignee_id)",
    )

    @field_validator("ticket_ids")
    @classmethod
    def ticket_ids_must_not_have_duplicates(cls, v: List[str]) -> List[str]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate ticket IDs are not allowed")
        return v

    @model_validator(mode="after")
    def validate_params_for_action_type(self) -> "BulkActionRequest":
        """Validate that required params are present for the action type."""
        if self.action_type == BulkActionType.STATUS_CHANGE:
            if "new_status" not in self.params:
                raise ValueError(
                    "status_change action requires 'new_status' in params"
                )
        elif self.action_type == BulkActionType.REASSIGN:
            if "assignee_id" not in self.params:
                raise ValueError(
                    "reassign action requires 'assignee_id' in params")
        elif self.action_type == BulkActionType.TAG:
            if "tags" not in self.params:
                raise ValueError("tag action requires 'tags' in params")
        elif self.action_type == BulkActionType.PRIORITY:
            if "priority" not in self.params:
                raise ValueError(
                    "priority action requires 'priority' in params")
        return self


class BulkActionResponse(BaseModel):
    """Schema for bulk action result."""

    id: str = Field(
        ...,
        description="Unique bulk action ID for tracking",
    )
    action_type: BulkActionType = Field(
        ...,
        description="Type of action performed",
    )
    success_count: int = Field(
        ...,
        ge=0,
        description="Number of successful operations",
    )
    failure_count: int = Field(
        ...,
        ge=0,
        description="Number of failed operations",
    )
    undo_token: Optional[str] = Field(
        default=None,
        description="Token to undo this bulk action (if reversible)",
    )
    result_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed results including any errors",
    )


class BulkActionUndo(BaseModel):
    """Schema for undoing a bulk action."""

    undo_token: str = Field(
        ...,
        min_length=1,
        description="Token from the original bulk action response",
    )


# ── Ticket Merge/Unmerge Schemas ─────────────────────────────────────────────


class TicketMergeRequest(BaseModel):
    """Schema for merging tickets into a primary ticket."""

    primary_ticket_id: str = Field(
        ...,
        description="ID of the ticket that will be the primary (surviving) ticket",
    )
    merged_ticket_ids: List[str] = Field(
        ...,
        min_length=1,
        description="IDs of tickets to merge into the primary",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Reason for merging tickets",
    )

    @field_validator("merged_ticket_ids")
    @classmethod
    def merged_tickets_must_not_include_primary(
            cls, v: List[str], info) -> List[str]:
        # Access primary_ticket_id via info.data since we're in field_validator
        primary_id = info.data.get("primary_ticket_id")
        if primary_id and primary_id in v:
            raise ValueError(
                "Primary ticket cannot be in the merged_ticket_ids list"
            )
        if len(v) != len(set(v)):
            raise ValueError("Duplicate ticket IDs in merged_ticket_ids")
        return v


class TicketUnmergeRequest(BaseModel):
    """Schema for unmerging previously merged tickets."""

    merge_id: str = Field(
        ...,
        description="ID of the merge operation to undo",
    )


class TicketMergeResponse(BaseModel):
    """Schema for ticket merge operation result."""

    id: str = Field(
        ...,
        description="Unique merge operation ID",
    )
    primary_ticket_id: str = Field(
        ...,
        description="ID of the primary (surviving) ticket",
    )
    merged_ticket_ids: List[str] = Field(
        ...,
        description="IDs of tickets that were merged",
    )
    undo_token: Optional[str] = Field(
        default=None,
        description="Token to undo this merge operation",
    )
    undone: bool = Field(
        default=False,
        description="Whether this merge has been undone",
    )
    merged_at: Optional[datetime] = Field(
        default=None,
        description="When the merge was performed",
    )

    model_config = {"from_attributes": True}
