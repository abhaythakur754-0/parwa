"""
PARWA Channel Schemas

Pydantic models for channel configuration API responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChannelConfigUpdateResponse(BaseModel):
    """Response after updating channel configuration."""

    channel_type: str
    is_enabled: bool
    config: Dict[str, Any] = Field(default_factory=dict)
    auto_create_ticket: bool
    char_limit: int
    allowed_file_types: List[str] = Field(default_factory=list)
    max_file_size: int
    updated_at: Optional[str] = None


class ChannelTestResponse(BaseModel):
    """Response from testing channel connectivity."""

    success: bool
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ChannelFormatMessageResponse(BaseModel):
    """Response from formatting a message for a channel."""

    original_length: int
    formatted_length: int
    channel_type: str
    content: str


class ChannelFileValidationResponse(BaseModel):
    """Response from validating a file for a channel."""

    is_valid: bool
    error: Optional[str] = None
    filename: str
    channel_type: str
