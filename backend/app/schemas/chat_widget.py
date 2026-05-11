"""
Chat Widget Schemas — Week 13 Day 4 (F-122: Live Chat Widget)

Pydantic models for chat widget API requests and responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Chat Widget Session Schemas ────────────────────────────────

class ChatSessionCreate(BaseModel):
    """Request to create a new chat widget session."""
    company_id: str = Field(..., min_length=1, max_length=36)
    visitor_name: Optional[str] = Field(None, max_length=100)
    visitor_email: Optional[str] = Field(None, max_length=254)
    visitor_phone: Optional[str] = Field(None, max_length=30)
    visitor_ip: Optional[str] = Field(None, max_length=45)
    visitor_user_agent: Optional[str] = Field(None, max_length=500)
    visitor_page_url: Optional[str] = Field(None, max_length=1000)
    visitor_referrer: Optional[str] = Field(None, max_length=1000)
    department: Optional[str] = Field(None, max_length=100)


class ChatSessionResponse(BaseModel):
    """Chat session data returned by API."""
    id: str
    company_id: str
    visitor_name: Optional[str]
    visitor_email: Optional[str]
    visitor_phone: Optional[str]
    status: str
    assigned_agent_id: Optional[str]
    department: Optional[str]
    ticket_id: Optional[str]
    customer_id: Optional[str]
    message_count: int
    visitor_message_count: int
    csat_rating: Optional[int]
    first_message_at: Optional[str]
    last_message_at: Optional[str]
    closed_at: Optional[str]
    created_at: Optional[str]


class ChatSessionListResponse(BaseModel):
    """Paginated list of chat sessions."""
    items: List[ChatSessionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Chat Message Schemas ──────────────────────────────────────

class ChatMessageCreate(BaseModel):
    """Request to send a message in a chat session."""
    session_id: str = Field(..., min_length=1, max_length=36)
    content: Optional[str] = Field(None, max_length=10000)
    message_type: str = Field("text", max_length=20)
    sender_name: Optional[str] = Field(None, max_length=100)
    attachments_json: Optional[str] = "[]"
    quick_replies_json: Optional[str] = "[]"
    event_name: Optional[str] = Field(None, max_length=50)
    event_data_json: Optional[str] = "{}"


class ChatMessageResponse(BaseModel):
    """Chat message data returned by API."""
    id: str
    session_id: str
    company_id: str
    sender_id: Optional[str]
    sender_name: Optional[str]
    role: str
    content: Optional[str]
    message_type: str
    attachments: Optional[str]
    quick_replies: Optional[str]
    event_name: Optional[str]
    event_data: Optional[str]
    is_ai_generated: bool
    ai_confidence: Optional[int]
    is_read: bool
    read_at: Optional[str]
    created_at: Optional[str]


class ChatMessageListResponse(BaseModel):
    """Paginated list of chat messages."""
    items: List[ChatMessageResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Typing Indicator Schema ────────────────────────────────────

class TypingIndicator(BaseModel):
    """Typing indicator event."""
    session_id: str
    user_id: Optional[str]
    role: str = Field("visitor", pattern="^(visitor|agent|bot|system)$")
    is_typing: bool


# ── CSAT Rating Schema ────────────────────────────────────────

class CsatRatingSubmit(BaseModel):
    """CSAT rating submission from visitor."""
    session_id: str = Field(..., min_length=1, max_length=36)
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)


# ── Widget Config Schemas ──────────────────────────────────────

class WidgetConfigUpdate(BaseModel):
    """Request to update widget configuration."""
    widget_title: Optional[str] = Field(None, max_length=100)
    welcome_message: Optional[str] = Field(None, max_length=2000)
    placeholder_text: Optional[str] = Field(None, max_length=200)
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    widget_position: Optional[str] = Field(
        None,
        pattern="^(bottom_right|bottom_left|top_right|top_left)$",
    )
    is_enabled: Optional[bool] = None
    auto_greeting_enabled: Optional[bool] = None
    auto_greeting_delay_seconds: Optional[int] = Field(None, ge=0)
    bot_enabled: Optional[bool] = None
    max_file_size_mb: Optional[int] = Field(None, ge=1)
    max_queue_size: Optional[int] = Field(None, ge=1)
    queue_message: Optional[str] = Field(None, max_length=1000)
    offline_message: Optional[str] = Field(None, max_length=1000)
    require_visitor_name: Optional[bool] = None
    require_visitor_email: Optional[bool] = None


class WidgetConfigResponse(BaseModel):
    """Widget configuration returned by API (public)."""
    id: str
    company_id: str
    widget_title: str
    welcome_message: str
    placeholder_text: str
    primary_color: str
    widget_position: str
    is_enabled: bool
    auto_greeting_enabled: bool
    auto_greeting_delay_seconds: int
    bot_enabled: bool
    max_file_size_mb: int
    queue_message: Optional[str]
    offline_message: Optional[str]
    require_visitor_name: bool
    require_visitor_email: bool


# ── Widget Embed Code Schema ──────────────────────────────────

class WidgetEmbedResponse(BaseModel):
    """Widget embed code for website integration."""
    company_id: str
    widget_id: str
    embed_url: str
    script_tag: str


# ── Canned Response Schemas ────────────────────────────────────

class CannedResponseCreate(BaseModel):
    """Request to create a canned response."""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    category: str = Field("general", max_length=50)
    shortcut: Optional[str] = Field(None, max_length=50)
    sort_order: int = Field(0, ge=0)


class CannedResponseUpdate(BaseModel):
    """Request to update a canned response."""
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    shortcut: Optional[str] = Field(None, max_length=50)
    sort_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class CannedResponseResponse(BaseModel):
    """Canned response data returned by API."""
    id: str
    company_id: str
    title: str
    content: str
    category: str
    shortcut: Optional[str]
    sort_order: int
    is_active: bool
