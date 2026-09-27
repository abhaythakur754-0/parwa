"""
PARWA Jarvis Chat Schemas — Request/Response Models for the Chat API

Pydantic models for the Jarvis chat endpoint. Clients just send a
message and get a natural response back. They don't need to know
about function calls, safety levels, or modes — all that is handled
internally by the orchestrator.

BC-001: company_id from auth, not request body.
BC-008: Graceful error handling.
BC-012: All timestamps UTC.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ══════════════════════════════════════════════════════════════════


class JarvisChatRequest(BaseModel):
    """Send a message to Jarvis and get a natural response.

    The client just sends their message. Jarvis figures out what to do.
    """
    session_id: str = Field(..., description="Active Jarvis session ID")
    message: str = Field(..., min_length=1, max_length=2000, description="Your message to Jarvis")
    context: Optional[Dict[str, Any]] = Field(None, description="Optional extra context (e.g., current page, selected ticket)")


class JarvisChatCreateSession(BaseModel):
    """Create a new Jarvis chat session."""
    existing_session_id: Optional[str] = Field(None, description="Resume an existing session if provided")
    industry: Optional[str] = Field(None, description="Industry type (auto-detected if not provided)")
    variant_tier: Optional[str] = Field(None, description="Subscription tier (auto-detected if not provided)")


# ══════════════════════════════════════════════════════════════════
# RESPONSE MODELS
# ══════════════════════════════════════════════════════════════════


class JarvisChatResponse(BaseModel):
    """Response from Jarvis. Natural, conversational, and helpful.

    The client sees the 'response' field — everything else is metadata
    for the frontend (e.g., showing what action was taken).
    """
    response: str = Field(..., description="Jarvis's conversational response")
    mode: str = Field("command", description="Current mode: agentic or command")
    function_called: Optional[str] = Field(None, description="Name of function called (if any)")
    safety_status: Optional[str] = Field(None, description="Safety gate status (if function was called)")
    execution_result: Optional[Dict[str, Any]] = Field(None, description="Function execution result (if any)")
    latency_ms: float = Field(0, description="Total pipeline latency in milliseconds")
    model: str = Field("unknown", description="LLM model used")
    tokens_used: int = Field(0, description="Total tokens consumed")


class JarvisChatSessionResponse(BaseModel):
    """Response from creating a Jarvis chat session."""
    session_id: str
    session_type: str = "customer_care"
    variant_tier: str = "parwa"
    mode: str = "command"
    message: str = "Hey! I'm Jarvis. How can I help you today?"


class JarvisChatHistoryResponse(BaseModel):
    """Paginated chat history response."""
    messages: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int
    has_more: bool


class JarvisChatHealthResponse(BaseModel):
    """Health check response for the Jarvis chat system."""
    status: str = "healthy"
    mode: str = "command"
    functions_available: int = 0
    pending_confirmation: bool = False
    model_available: bool = False


__all__ = [
    "JarvisChatRequest",
    "JarvisChatCreateSession",
    "JarvisChatResponse",
    "JarvisChatSessionResponse",
    "JarvisChatHistoryResponse",
    "JarvisChatHealthResponse",
]
