"""
OOO Detection Schemas — Week 13 Day 3 (F-122)

Pydantic models for OOO detection API endpoints and service responses.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ── Check Endpoint Schemas ──────────────────────────────────────


class OOOCheckRequest(BaseModel):
    """Request body for POST /api/email/ooo/check."""

    email_headers: Optional[dict] = Field(None, description="Email headers as dict")
    body_text: Optional[str] = Field(None, description="Email body text")
    body_html: Optional[str] = Field(None, description="Email body HTML")
    subject: Optional[str] = Field(None, description="Email subject line")
    sender_email: Optional[str] = Field(None, description="Sender email address")


class OOOCheckResponse(BaseModel):
    """Response from OOO check endpoint."""

    is_auto_reply: bool = False
    type: Optional[str] = Field(None, description="ooo/auto_reply/cyclic/spam")
    confidence: Optional[str] = Field(None, description="high/medium/low")
    detection_source: Optional[str] = Field(
        None, description="header/subject/body/rule"
    )
    detected_signals: List[str] = Field(default_factory=list)
    reason: Optional[str] = None
    ooo_until: Optional[str] = Field(
        None, description="ISO date if return date extracted"
    )
    rule_ids_matched: List[str] = Field(default_factory=list)


# ── Rules CRUD Schemas ─────────────────────────────────────────


class OOORuleCreate(BaseModel):
    """Request to create a custom OOO detection rule."""

    pattern: str = Field(
        ..., min_length=1, max_length=500, description="Detection pattern"
    )
    pattern_type: str = Field("regex", description="regex/substring/contains")
    rule_type: str = Field("body", description="header/body/sender_behavior/frequency")
    classification: str = Field("ooo", description="ooo/auto_reply/cyclic/spam")
    active: bool = Field(True, description="Whether rule is active")


class OOORuleUpdate(BaseModel):
    """Request to update an OOO detection rule."""

    pattern: Optional[str] = Field(None, max_length=500)
    pattern_type: Optional[str] = None
    rule_type: Optional[str] = None
    classification: Optional[str] = None
    active: Optional[bool] = None


class OOORuleResponse(BaseModel):
    """Single OOO detection rule."""

    id: str
    company_id: Optional[str] = None
    rule_type: str
    pattern: str
    pattern_type: str
    classification: str
    active: bool
    match_count: int = 0
    last_matched_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OOORulesListResponse(BaseModel):
    """Response for GET /api/email/ooo/rules."""

    custom_rules: List[OOORuleResponse] = []
    global_rules_count: int = 0


class OOORuleActionResponse(BaseModel):
    """Response for rule create/update/delete."""

    rule_id: Optional[str] = None
    status: str = Field(..., description="created/updated/deleted")


# ── Stats Schemas ───────────────────────────────────────────────


class OOOStatsResponse(BaseModel):
    """Response for GET /api/email/ooo/stats."""

    detected_count: int = 0
    by_type: dict = Field(default_factory=dict)
    top_senders: List[dict] = Field(default_factory=list)
    loop_prevented_count: int = 0
    range_days: int = 7


# ── Sender Profile Schema ───────────────────────────────────────


class OOOSenderProfileResponse(BaseModel):
    """Sender OOO profile."""

    sender_email: str
    ooo_detected_count: int = 0
    last_ooo_at: Optional[str] = None
    ooo_until: Optional[str] = None
    active_ooo: bool = False
