"""Pydantic schemas for Superglue Actions API.

Separate from the MCP models (mcp_server/models.py). These are for the
internal REST API that manages action safety classifications.

BC-008: All schemas are strict — validation errors are caught by FastAPI.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ActionSafetyResponse(BaseModel):
    """Response for a persisted safety classification."""
    id: str
    tool_id: str
    tool_name: str
    safety_level: str
    needs_approval: bool
    regulatory_frameworks: list[str]
    is_active: bool


class ClassifyActionRequest(BaseModel):
    """Request to classify a tool name (ephemeral, no persist)."""
    tool_name: str = Field(..., min_length=1, max_length=255)
    tool_description: Optional[str] = Field(None, max_length=1000)


class ClassifyActionResponse(BaseModel):
    """Response from ephemeral classification."""
    safety_level: str
    needs_approval: bool
    matched_keyword: Optional[str]
    reasoning: str
    confidence: float
    regulatory_frameworks: list[str]


class OverrideRequest(BaseModel):
    """Request to toggle approval_required_override."""
    approval_required_override: bool


class PersistClassificationRequest(BaseModel):
    """Request to classify AND persist a tool's safety level."""
    tool_id: str = Field(..., min_length=1, max_length=100)
    tool_name: str = Field(..., min_length=1, max_length=255)
    tool_description: Optional[str] = Field(None, max_length=1000)
    output_schema: Optional[dict] = None


class PersistClassificationResponse(BaseModel):
    """Response after persisting a classification."""
    id: str
    tool_id: str
    tool_name: str
    safety_level: str
    needs_approval: bool
    regulatory_frameworks: list[str]
    is_active: bool
