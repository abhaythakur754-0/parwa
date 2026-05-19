"""
Approval Schemas

Pydantic v2 models for approval-related API requests and responses.
Covers: ApprovalQueue, AutoApproveRule, ExecutedAction, UndoLog.
All money fields use Decimal (never float) per BC-002.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ────────────────────────────────────────────────────────────────


class ApprovalStatus(str, Enum):
    """Valid statuses for an approval queue item."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class RiskLevel(str, Enum):
    """Risk level classifications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class UndoType(str, Enum):
    """Types of undo operations."""
    REVERSAL = "reversal"
    EMAIL_RECALL = "email_recall"


# ══════════════════════════════════════════════════════════════════════════
# ApprovalQueue
# ══════════════════════════════════════════════════════════════════════════


class ApprovalQueueCreate(BaseModel):
    """Request schema for creating an approval queue entry."""

    company_id: str = Field(..., description="Company that owns this approval entry")
    session_id: Optional[str] = Field(None, description="Associated ticket/session ID")
    action_type: str = Field(..., description="Type of action requiring approval")
    confidence_score: Optional[Decimal] = Field(
        None,
        max_digits=5,
        decimal_places=2,
        description="AI confidence score (0.00–100.00)",
    )
    risk_level: Optional[RiskLevel] = Field(
        None, description="Risk classification: low, medium, or high",
    )
    amount: Optional[Decimal] = Field(
        None,
        max_digits=10,
        decimal_places=2,
        description="Monetary amount involved (BC-002)",
    )
    reasoning: Optional[str] = Field(None, description="AI reasoning for the action")
    response_data: Optional[str] = Field(None, description="Proposed response payload")
    status: ApprovalStatus = Field(
        ApprovalStatus.PENDING,
        description="Current approval status",
    )
    batch_id: Optional[str] = Field(None, description="Batch identifier for bulk approvals")


class ApprovalQueueUpdate(BaseModel):
    """Request schema for updating an approval queue entry (PATCH)."""

    session_id: Optional[str] = Field(None, description="Associated ticket/session ID")
    action_type: Optional[str] = Field(None, description="Type of action requiring approval")
    confidence_score: Optional[Decimal] = Field(
        None,
        max_digits=5,
        decimal_places=2,
        description="AI confidence score (0.00–100.00)",
    )
    risk_level: Optional[RiskLevel] = Field(
        None, description="Risk classification: low, medium, or high",
    )
    amount: Optional[Decimal] = Field(
        None,
        max_digits=10,
        decimal_places=2,
        description="Monetary amount involved (BC-002)",
    )
    reasoning: Optional[str] = Field(None, description="AI reasoning for the action")
    response_data: Optional[str] = Field(None, description="Proposed response payload")
    status: Optional[ApprovalStatus] = Field(
        None, description="Current approval status",
    )
    batch_id: Optional[str] = Field(None, description="Batch identifier for bulk approvals")
    resolved_at: Optional[datetime] = Field(None, description="Timestamp when resolved")
    resolved_by: Optional[str] = Field(None, description="User ID who resolved the approval")


class ApprovalQueueResponse(BaseModel):
    """Response schema for an approval queue entry."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique approval queue entry ID")
    company_id: str = Field(..., description="Company that owns this approval entry")
    session_id: Optional[str] = Field(None, description="Associated ticket/session ID")
    action_type: str = Field(..., description="Type of action requiring approval")
    confidence_score: Optional[Decimal] = Field(
        None, description="AI confidence score (0.00–100.00)",
    )
    risk_level: Optional[RiskLevel] = Field(
        None, description="Risk classification: low, medium, or high",
    )
    amount: Optional[Decimal] = Field(
        None, description="Monetary amount involved (BC-002)",
    )
    reasoning: Optional[str] = Field(None, description="AI reasoning for the action")
    response_data: Optional[str] = Field(None, description="Proposed response payload")
    status: ApprovalStatus = Field(..., description="Current approval status")
    batch_id: Optional[str] = Field(None, description="Batch identifier for bulk approvals")
    created_at: datetime = Field(..., description="Timestamp when the entry was created")
    resolved_at: Optional[datetime] = Field(None, description="Timestamp when resolved")
    resolved_by: Optional[str] = Field(None, description="User ID who resolved the approval")


# ══════════════════════════════════════════════════════════════════════════
# AutoApproveRule
# ══════════════════════════════════════════════════════════════════════════


class AutoApproveRuleCreate(BaseModel):
    """Request schema for creating an auto-approve rule."""

    company_id: str = Field(..., description="Company that owns this rule")
    action_type: str = Field(..., description="Action type this rule applies to")
    min_confidence: Decimal = Field(
        ...,
        max_digits=5,
        decimal_places=2,
        description="Minimum confidence score to auto-approve (0.00–100.00)",
    )
    max_amount: Optional[Decimal] = Field(
        None,
        max_digits=10,
        decimal_places=2,
        description="Maximum monetary amount to auto-approve (BC-002)",
    )
    risk_levels: Optional[str] = Field(
        None,
        description="Comma-separated risk levels that are auto-approved (e.g. 'low,medium')",
    )
    is_active: bool = Field(False, description="Whether the rule is currently active")
    created_by: str = Field(..., description="User ID who created the rule")


class AutoApproveRuleUpdate(BaseModel):
    """Request schema for updating an auto-approve rule (PATCH)."""

    action_type: Optional[str] = Field(None, description="Action type this rule applies to")
    min_confidence: Optional[Decimal] = Field(
        None,
        max_digits=5,
        decimal_places=2,
        description="Minimum confidence score to auto-approve (0.00–100.00)",
    )
    max_amount: Optional[Decimal] = Field(
        None,
        max_digits=10,
        decimal_places=2,
        description="Maximum monetary amount to auto-approve (BC-002)",
    )
    risk_levels: Optional[str] = Field(
        None,
        description="Comma-separated risk levels that are auto-approved",
    )
    is_active: Optional[bool] = Field(None, description="Whether the rule is currently active")


class AutoApproveRuleResponse(BaseModel):
    """Response schema for an auto-approve rule."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique auto-approve rule ID")
    company_id: str = Field(..., description="Company that owns this rule")
    action_type: str = Field(..., description="Action type this rule applies to")
    min_confidence: Decimal = Field(
        ..., description="Minimum confidence score to auto-approve",
    )
    max_amount: Optional[Decimal] = Field(
        None, description="Maximum monetary amount to auto-approve (BC-002)",
    )
    risk_levels: Optional[str] = Field(
        None, description="Comma-separated risk levels that are auto-approved",
    )
    is_active: bool = Field(..., description="Whether the rule is currently active")
    created_by: str = Field(..., description="User ID who created the rule")
    created_at: datetime = Field(..., description="Timestamp when the rule was created")
    updated_at: datetime = Field(..., description="Timestamp when the rule was last updated")


# ══════════════════════════════════════════════════════════════════════════
# ExecutedAction
# ══════════════════════════════════════════════════════════════════════════


class ExecutedActionCreate(BaseModel):
    """Request schema for creating an executed action record."""

    company_id: str = Field(..., description="Company that owns this executed action")
    session_id: Optional[str] = Field(None, description="Associated ticket/session ID")
    approval_id: Optional[str] = Field(None, description="Approval queue entry that authorized this action")
    action_type: str = Field(..., description="Type of action that was executed")
    action_data: Optional[str] = Field(None, description="Payload of the executed action")
    response_data: Optional[str] = Field(None, description="Response received from executing the action")
    amount: Optional[Decimal] = Field(
        None,
        max_digits=10,
        decimal_places=2,
        description="Monetary amount involved in the action (BC-002)",
    )
    executed_by: Optional[str] = Field(None, description="User ID who executed the action")


class ExecutedActionUpdate(BaseModel):
    """Request schema for updating an executed action record (PATCH)."""

    session_id: Optional[str] = Field(None, description="Associated ticket/session ID")
    approval_id: Optional[str] = Field(None, description="Approval queue entry that authorized this action")
    action_type: Optional[str] = Field(None, description="Type of action that was executed")
    action_data: Optional[str] = Field(None, description="Payload of the executed action")
    response_data: Optional[str] = Field(None, description="Response received from executing the action")
    amount: Optional[Decimal] = Field(
        None,
        max_digits=10,
        decimal_places=2,
        description="Monetary amount involved in the action (BC-002)",
    )
    executed_by: Optional[str] = Field(None, description="User ID who executed the action")


class ExecutedActionResponse(BaseModel):
    """Response schema for an executed action record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique executed action ID")
    company_id: str = Field(..., description="Company that owns this executed action")
    session_id: Optional[str] = Field(None, description="Associated ticket/session ID")
    approval_id: Optional[str] = Field(None, description="Approval queue entry that authorized this action")
    action_type: str = Field(..., description="Type of action that was executed")
    action_data: Optional[str] = Field(None, description="Payload of the executed action")
    response_data: Optional[str] = Field(None, description="Response received from executing the action")
    amount: Optional[Decimal] = Field(
        None, description="Monetary amount involved in the action (BC-002)",
    )
    executed_by: Optional[str] = Field(None, description="User ID who executed the action")
    created_at: datetime = Field(..., description="Timestamp when the action was executed")


# ══════════════════════════════════════════════════════════════════════════
# UndoLog
# ══════════════════════════════════════════════════════════════════════════


class UndoLogCreate(BaseModel):
    """Request schema for creating an undo log entry."""

    company_id: str = Field(..., description="Company that owns this undo log entry")
    executed_action_id: str = Field(..., description="Executed action being undone")
    undo_type: UndoType = Field(
        ..., description="Type of undo: reversal or email_recall",
    )
    original_data: Optional[str] = Field(None, description="Original data before the action")
    undo_data: Optional[str] = Field(None, description="Data used to perform the undo")
    undo_reason: Optional[str] = Field(None, description="Reason for undoing the action")
    undone_by: Optional[str] = Field(None, description="User ID who performed the undo")


class UndoLogUpdate(BaseModel):
    """Request schema for updating an undo log entry (PATCH)."""

    undo_type: Optional[UndoType] = Field(
        None, description="Type of undo: reversal or email_recall",
    )
    original_data: Optional[str] = Field(None, description="Original data before the action")
    undo_data: Optional[str] = Field(None, description="Data used to perform the undo")
    undo_reason: Optional[str] = Field(None, description="Reason for undoing the action")
    undone_by: Optional[str] = Field(None, description="User ID who performed the undo")


class UndoLogResponse(BaseModel):
    """Response schema for an undo log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique undo log entry ID")
    company_id: str = Field(..., description="Company that owns this undo log entry")
    executed_action_id: str = Field(..., description="Executed action being undone")
    undo_type: UndoType = Field(..., description="Type of undo: reversal or email_recall")
    original_data: Optional[str] = Field(None, description="Original data before the action")
    undo_data: Optional[str] = Field(None, description="Data used to perform the undo")
    undo_reason: Optional[str] = Field(None, description="Reason for undoing the action")
    undone_by: Optional[str] = Field(None, description="User ID who performed the undo")
    created_at: datetime = Field(..., description="Timestamp when the undo was performed")
