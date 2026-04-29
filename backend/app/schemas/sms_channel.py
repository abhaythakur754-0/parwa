"""
SMS Channel Schemas — Week 13 Day 5 (F-123: SMS Channel)

Pydantic models for SMS channel API requests and responses.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


# ── SMS Message Schemas ────────────────────────────────────────

class SMSMessageResponse(BaseModel):
    """SMS message data returned by API."""
    id: str
    company_id: str
    conversation_id: Optional[str]
    direction: str
    from_number: str
    to_number: str
    body: str
    num_segments: Optional[int]
    char_count: Optional[int]
    twilio_message_sid: Optional[str]
    twilio_status: str
    ticket_id: Optional[str]
    ticket_message_id: Optional[str]
    sender_id: Optional[str]
    sender_role: str
    is_ai_generated: bool
    ai_confidence: Optional[int]
    ai_model: Optional[str]
    is_opt_out: bool
    error_message: Optional[str]
    retry_count: int
    sent_at: Optional[str]
    delivered_at: Optional[str]
    created_at: Optional[str]


class SMSMessageListResponse(BaseModel):
    """Paginated list of SMS messages."""
    items: List[SMSMessageResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SMSSendRequest(BaseModel):
    """Request to send an outbound SMS message."""
    to_number: str = Field(..., min_length=1, max_length=30,
                           description="Recipient phone in E.164")
    body: str = Field(..., min_length=1, max_length=1600,
                      description="SMS body text")
    conversation_id: Optional[str] = Field(None, max_length=36)
    ticket_id: Optional[str] = Field(None, max_length=36)
    sender_role: str = Field("agent", pattern="^(agent|bot|system)$")


class SMSSendResponse(BaseModel):
    """Response after sending an outbound SMS."""
    id: str
    conversation_id: str
    twilio_message_sid: Optional[str]
    twilio_status: str
    direction: str
    from_number: str
    to_number: str
    body: str
    num_segments: int


# ── SMS Conversation Schemas ──────────────────────────────────

class SMSConversationResponse(BaseModel):
    """SMS conversation data returned by API."""
    id: str
    company_id: str
    customer_number: str
    twilio_number: str
    ticket_id: Optional[str]
    customer_id: Optional[str]
    message_count: int
    last_message_at: Optional[str]
    is_opted_out: bool
    opt_out_keyword: Optional[str]
    opt_out_at: Optional[str]
    created_at: Optional[str]


class SMSConversationListResponse(BaseModel):
    """Paginated list of SMS conversations."""
    items: List[SMSConversationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── SMS Channel Config Schemas ────────────────────────────────

class SMSConfigCreate(BaseModel):
    """Request to create/update SMS channel config."""
    twilio_account_sid: str = Field(..., min_length=1, max_length=64)
    twilio_auth_token: str = Field(..., min_length=1)
    twilio_phone_number: str = Field(..., min_length=1, max_length=30)
    is_enabled: bool = True
    auto_create_ticket: bool = True
    char_limit: int = Field(1600, gt=0, le=1600)
    max_outbound_per_hour: int = Field(5, gt=0)
    max_outbound_per_day: int = Field(50, gt=0)
    opt_out_keywords: str = "STOP,STOPALL,UNSUBSCRIBE,CANCEL,QUIT,END"
    opt_in_keywords: str = "START,YES,UNSTOP,CONTINUE"
    opt_out_response: str = "You have been opted out. Reply START to resume."
    auto_reply_enabled: bool = False
    auto_reply_message: Optional[str] = "Thanks for your message! An agent will respond shortly."
    auto_reply_delay_seconds: int = Field(10, ge=0)
    after_hours_message: Optional[str] = "We're currently closed. We'll respond during business hours."
    business_hours_json: str = "{}"


class SMSConfigUpdate(BaseModel):
    """Request to update SMS channel config (partial)."""
    is_enabled: Optional[bool] = None
    auto_create_ticket: Optional[bool] = None
    char_limit: Optional[int] = Field(None, gt=0, le=1600)
    max_outbound_per_hour: Optional[int] = Field(None, gt=0)
    max_outbound_per_day: Optional[int] = Field(None, gt=0)
    opt_out_keywords: Optional[str] = None
    opt_in_keywords: Optional[str] = None
    opt_out_response: Optional[str] = None
    auto_reply_enabled: Optional[bool] = None
    auto_reply_message: Optional[str] = None
    auto_reply_delay_seconds: Optional[int] = Field(None, ge=0)
    after_hours_message: Optional[str] = None
    business_hours_json: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_number: Optional[str] = Field(None, max_length=30)


class SMSConfigResponse(BaseModel):
    """SMS channel config returned by API (secrets redacted)."""
    id: str
    company_id: str
    twilio_account_sid: str
    twilio_phone_number: str
    is_enabled: bool
    auto_create_ticket: bool
    char_limit: int
    max_outbound_per_hour: int
    max_outbound_per_day: int
    opt_out_keywords: str
    opt_in_keywords: str
    opt_out_response: str
    auto_reply_enabled: bool
    auto_reply_message: Optional[str]
    auto_reply_delay_seconds: int
    after_hours_message: Optional[str]
    business_hours: str
    created_at: Optional[str]
    updated_at: Optional[str]


# ── SMS Consent Schemas ────────────────────────────────────────

class SMSConsentRecord(BaseModel):
    """SMS consent record for TCPA compliance."""
    conversation_id: str
    customer_number: str
    is_opted_out: bool
    opt_out_keyword: Optional[str]
    opt_out_at: Optional[str]
