"""
PARWA Technique Schemas

Pydantic v2 models for the AI Technique Framework (TRIVYA v1.0) — BC-013, F-140 to F-148.
- TechniqueConfiguration: Per-tenant technique enable/disable settings.
- TechniqueExecution: Technique activation logs, token usage, latency, fallback.
- TechniqueVersion: Versioned technique implementations with A/B test metadata.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Technique Configuration Schemas ──────────────────────────────────


class TechniqueConfigurationCreate(BaseModel):
    """Schema for creating a new technique configuration."""

    company_id: str = Field(..., description="Company identifier")
    technique_id: str = Field(
        ...,
        max_length=50,
        description="Technique identifier, e.g. 'reverse_thinking', 'step_back', 'cot'",
    )
    tier: Literal["tier_2", "tier_3"] = Field(
        ...,
        description="Technique tier — only tier_2 and tier_3 are configurable",
    )
    is_enabled: bool = Field(default=True, description="Whether the technique is enabled for this tenant")
    custom_token_budget: Optional[int] = Field(
        None,
        description="Override token budget; NULL = use system default",
    )
    custom_trigger_threshold: Optional[float] = Field(
        None,
        description="Override trigger threshold; NULL = use system default",
    )
    custom_timeout_ms: Optional[int] = Field(
        None,
        description="Override max execution time in ms; NULL = use system default",
    )
    updated_by: Optional[str] = Field(None, description="User ID who last updated this configuration")


class TechniqueConfigurationUpdate(BaseModel):
    """Schema for updating an existing technique configuration."""

    technique_id: Optional[str] = Field(
        None,
        max_length=50,
        description="Technique identifier, e.g. 'reverse_thinking', 'step_back', 'cot'",
    )
    tier: Optional[Literal["tier_2", "tier_3"]] = Field(
        None,
        description="Technique tier — only tier_2 and tier_3 are configurable",
    )
    is_enabled: Optional[bool] = Field(None, description="Whether the technique is enabled for this tenant")
    custom_token_budget: Optional[int] = Field(
        None,
        description="Override token budget; NULL = use system default",
    )
    custom_trigger_threshold: Optional[float] = Field(
        None,
        description="Override trigger threshold; NULL = use system default",
    )
    custom_timeout_ms: Optional[int] = Field(
        None,
        description="Override max execution time in ms; NULL = use system default",
    )
    updated_by: Optional[str] = Field(None, description="User ID who last updated this configuration")


class TechniqueConfigurationResponse(BaseModel):
    """Full technique configuration response schema."""

    id: str = Field(..., description="Unique configuration identifier")
    company_id: str = Field(..., description="Company identifier")
    technique_id: str = Field(..., description="Technique identifier")
    tier: str = Field(..., description="Technique tier (tier_2 or tier_3)")
    is_enabled: bool = Field(..., description="Whether the technique is enabled for this tenant")
    custom_token_budget: Optional[int] = Field(None, description="Override token budget; NULL = system default")
    custom_trigger_threshold: Optional[float] = Field(None, description="Override trigger threshold; NULL = system default")
    custom_timeout_ms: Optional[int] = Field(None, description="Override max execution time in ms; NULL = system default")
    updated_by: Optional[str] = Field(None, description="User ID who last updated this configuration")
    created_at: datetime = Field(..., description="Configuration creation timestamp")
    updated_at: datetime = Field(..., description="Configuration last update timestamp")

    model_config = ConfigDict(from_attributes=True)


# ── Technique Execution Schemas ──────────────────────────────────────


class TechniqueExecutionCreate(BaseModel):
    """Schema for creating a new technique execution log."""

    company_id: str = Field(..., description="Company identifier")
    ticket_id: Optional[str] = Field(None, description="Associated ticket identifier")
    conversation_id: Optional[str] = Field(None, description="Associated conversation identifier")
    technique_id: str = Field(..., max_length=50, description="Technique identifier")
    tier: str = Field(..., max_length=10, description="Technique tier at time of activation")

    # Input signals
    query_complexity: Optional[float] = Field(None, description="Query complexity score at activation time")
    confidence_score: Optional[float] = Field(None, description="Confidence score at activation time")
    sentiment_score: Optional[float] = Field(None, description="Sentiment score at activation time")
    customer_tier: Optional[str] = Field(None, max_length=20, description="Customer tier label")
    monetary_value: Optional[Decimal] = Field(None, description="Monetary value associated with the conversation")
    turn_count: Optional[int] = Field(None, description="Conversation turn count at activation time")
    intent_type: Optional[str] = Field(None, max_length=50, description="Detected intent type")

    # Trigger rules
    trigger_rules: str = Field(
        default="[]",
        description="JSON list of rule numbers that activated this technique, e.g. '[\"2\", \"4\"]'",
    )

    # Execution metrics
    tokens_input: int = Field(default=0, ge=0, description="Number of input tokens consumed")
    tokens_output: int = Field(default=0, ge=0, description="Number of output tokens consumed")
    tokens_overhead: int = Field(default=0, ge=0, description="Extra tokens consumed by the technique itself")
    latency_ms: int = Field(default=0, ge=0, description="Total execution time in milliseconds")

    # Result
    result_status: Literal["success", "fallback", "timeout", "error", "skipped_budget"] = Field(
        default="success",
        description="Outcome of the technique execution",
    )
    fallback_technique: Optional[str] = Field(
        None,
        max_length=50,
        description="Technique used as fallback when result_status is 'fallback'",
    )
    fallback_reason: Optional[str] = Field(
        None,
        max_length=255,
        description="Human-readable reason for fallback, e.g. 'token budget exceeded'",
    )
    error_message: Optional[str] = Field(None, description="Error details when result_status is 'error'")


class TechniqueExecutionUpdate(BaseModel):
    """Schema for updating an existing technique execution log."""

    ticket_id: Optional[str] = Field(None, description="Associated ticket identifier")
    conversation_id: Optional[str] = Field(None, description="Associated conversation identifier")
    technique_id: Optional[str] = Field(None, max_length=50, description="Technique identifier")
    tier: Optional[str] = Field(None, max_length=10, description="Technique tier at time of activation")

    # Input signals
    query_complexity: Optional[float] = Field(None, description="Query complexity score at activation time")
    confidence_score: Optional[float] = Field(None, description="Confidence score at activation time")
    sentiment_score: Optional[float] = Field(None, description="Sentiment score at activation time")
    customer_tier: Optional[str] = Field(None, max_length=20, description="Customer tier label")
    monetary_value: Optional[Decimal] = Field(None, description="Monetary value associated with the conversation")
    turn_count: Optional[int] = Field(None, description="Conversation turn count at activation time")
    intent_type: Optional[str] = Field(None, max_length=50, description="Detected intent type")

    # Trigger rules
    trigger_rules: Optional[str] = Field(
        None,
        description="JSON list of rule numbers that activated this technique",
    )

    # Execution metrics
    tokens_input: Optional[int] = Field(None, ge=0, description="Number of input tokens consumed")
    tokens_output: Optional[int] = Field(None, ge=0, description="Number of output tokens consumed")
    tokens_overhead: Optional[int] = Field(None, ge=0, description="Extra tokens consumed by the technique itself")
    latency_ms: Optional[int] = Field(None, ge=0, description="Total execution time in milliseconds")

    # Result
    result_status: Optional[Literal["success", "fallback", "timeout", "error", "skipped_budget"]] = Field(
        None,
        description="Outcome of the technique execution",
    )
    fallback_technique: Optional[str] = Field(
        None,
        max_length=50,
        description="Technique used as fallback when result_status is 'fallback'",
    )
    fallback_reason: Optional[str] = Field(
        None,
        max_length=255,
        description="Human-readable reason for fallback",
    )
    error_message: Optional[str] = Field(None, description="Error details when result_status is 'error'")


class TechniqueExecutionResponse(BaseModel):
    """Full technique execution response schema."""

    id: str = Field(..., description="Unique execution identifier")
    company_id: str = Field(..., description="Company identifier")
    ticket_id: Optional[str] = Field(None, description="Associated ticket identifier")
    conversation_id: Optional[str] = Field(None, description="Associated conversation identifier")
    technique_id: str = Field(..., description="Technique identifier")
    tier: str = Field(..., description="Technique tier at time of activation")

    # Input signals
    query_complexity: Optional[float] = Field(None, description="Query complexity score at activation time")
    confidence_score: Optional[float] = Field(None, description="Confidence score at activation time")
    sentiment_score: Optional[float] = Field(None, description="Sentiment score at activation time")
    customer_tier: Optional[str] = Field(None, description="Customer tier label")
    monetary_value: Optional[Decimal] = Field(None, description="Monetary value associated with the conversation")
    turn_count: Optional[int] = Field(None, description="Conversation turn count at activation time")
    intent_type: Optional[str] = Field(None, description="Detected intent type")

    # Trigger rules
    trigger_rules: str = Field(..., description="JSON list of rule numbers that activated this technique")

    # Execution metrics
    tokens_input: int = Field(..., ge=0, description="Number of input tokens consumed")
    tokens_output: int = Field(..., ge=0, description="Number of output tokens consumed")
    tokens_overhead: int = Field(..., ge=0, description="Extra tokens consumed by the technique itself")
    latency_ms: int = Field(..., ge=0, description="Total execution time in milliseconds")

    # Result
    result_status: str = Field(..., description="Outcome of the technique execution")
    fallback_technique: Optional[str] = Field(None, description="Technique used as fallback")
    fallback_reason: Optional[str] = Field(None, description="Human-readable reason for fallback")
    error_message: Optional[str] = Field(None, description="Error details")

    created_at: datetime = Field(..., description="Execution creation timestamp")

    model_config = ConfigDict(from_attributes=True)


# ── Technique Version Schemas ────────────────────────────────────────


class TechniqueVersionCreate(BaseModel):
    """Schema for creating a new technique version."""

    company_id: str = Field(..., description="Company identifier")
    technique_id: str = Field(..., max_length=50, description="Technique identifier, e.g. 'cot'")
    version: str = Field(..., max_length=10, description="Version tag, e.g. 'v1', 'v2'")
    label: str = Field(..., max_length=100, description="Human-readable label, e.g. 'Chain of Thought v2 (compressed prompts)'")
    is_active: bool = Field(default=True, description="Whether this version is active")
    is_default: bool = Field(default=False, description="Whether this version is the default for the technique")

    # A/B testing metadata
    ab_test_enabled: bool = Field(default=False, description="Whether A/B testing is enabled for this version")
    ab_test_traffic_pct: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Percentage of traffic routed to this version during A/B test",
    )

    # Performance metrics
    total_activations: int = Field(default=0, ge=0, description="Total number of activations for this version")
    avg_accuracy_lift: Optional[float] = Field(None, description="Accuracy improvement when this version is active vs inactive")
    avg_tokens_consumed: Optional[float] = Field(None, description="Average tokens consumed per activation")
    avg_latency_ms: Optional[int] = Field(None, description="Average execution latency in milliseconds")
    csat_delta: Optional[float] = Field(None, description="Customer satisfaction delta for this version")

    # Prompt/template content
    prompt_template: Optional[str] = Field(None, description="The actual prompt template for this version")
    configuration: str = Field(default="{}", description="JSON blob with technique-specific parameters")

    created_by: Optional[str] = Field(None, description="User ID who created this version")


class TechniqueVersionUpdate(BaseModel):
    """Schema for updating an existing technique version."""

    technique_id: Optional[str] = Field(None, max_length=50, description="Technique identifier")
    version: Optional[str] = Field(None, max_length=10, description="Version tag, e.g. 'v1', 'v2'")
    label: Optional[str] = Field(None, max_length=100, description="Human-readable label")
    is_active: Optional[bool] = Field(None, description="Whether this version is active")
    is_default: Optional[bool] = Field(None, description="Whether this version is the default for the technique")

    # A/B testing metadata
    ab_test_enabled: Optional[bool] = Field(None, description="Whether A/B testing is enabled for this version")
    ab_test_traffic_pct: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Percentage of traffic routed to this version during A/B test",
    )

    # Performance metrics
    total_activations: Optional[int] = Field(None, ge=0, description="Total number of activations for this version")
    avg_accuracy_lift: Optional[float] = Field(None, description="Accuracy improvement when this version is active vs inactive")
    avg_tokens_consumed: Optional[float] = Field(None, description="Average tokens consumed per activation")
    avg_latency_ms: Optional[int] = Field(None, description="Average execution latency in milliseconds")
    csat_delta: Optional[float] = Field(None, description="Customer satisfaction delta for this version")

    # Prompt/template content
    prompt_template: Optional[str] = Field(None, description="The actual prompt template for this version")
    configuration: Optional[str] = Field(None, description="JSON blob with technique-specific parameters")

    created_by: Optional[str] = Field(None, description="User ID who created this version")


class TechniqueVersionResponse(BaseModel):
    """Full technique version response schema."""

    id: str = Field(..., description="Unique version identifier")
    company_id: str = Field(..., description="Company identifier")
    technique_id: str = Field(..., description="Technique identifier")
    version: str = Field(..., description="Version tag, e.g. 'v1', 'v2'")
    label: str = Field(..., description="Human-readable label")
    is_active: bool = Field(..., description="Whether this version is active")
    is_default: bool = Field(..., description="Whether this version is the default for the technique")

    # A/B testing metadata
    ab_test_enabled: bool = Field(..., description="Whether A/B testing is enabled for this version")
    ab_test_traffic_pct: int = Field(..., description="Percentage of traffic routed to this version during A/B test")

    # Performance metrics
    total_activations: int = Field(..., description="Total number of activations for this version")
    avg_accuracy_lift: Optional[float] = Field(None, description="Accuracy improvement when this version is active vs inactive")
    avg_tokens_consumed: Optional[float] = Field(None, description="Average tokens consumed per activation")
    avg_latency_ms: Optional[int] = Field(None, description="Average execution latency in milliseconds")
    csat_delta: Optional[float] = Field(None, description="Customer satisfaction delta for this version")

    # Prompt/template content
    prompt_template: Optional[str] = Field(None, description="The actual prompt template for this version")
    configuration: str = Field(..., description="JSON blob with technique-specific parameters")

    created_by: Optional[str] = Field(None, description="User ID who created this version")
    created_at: datetime = Field(..., description="Version creation timestamp")
    updated_at: datetime = Field(..., description="Version last update timestamp")

    model_config = ConfigDict(from_attributes=True)
