"""
PARWA Agent Schemas (Week 14 Day 4 — F-095, F-096)

Pydantic models for the Agent Provisioning and Dynamic Instruction
Workflow APIs.

Covers:
- Agent creation, listing, and setup tracking (F-095)
- Instruction set CRUD, versioning, and A/B testing (F-096)

Building Codes: BC-001 (tenant isolation), BC-007 (AI model),
               BC-008 (state management), BC-009 (approval), BC-011 (auth)
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════
# F-095: Agent Provisioning Schemas
# ══════════════════════════════════════════════════════════════════

VALID_AGENT_STATUSES = (
    "initializing", "training", "active", "paused",
    "deprovisioned", "error",
)
VALID_SPECIALTIES = (
    "billing_specialist", "returns_specialist", "technical_support",
    "general_support", "sales_assistant", "onboarding_guide",
    "vip_concierge", "feedback_collector", "custom",
)
VALID_PERMISSION_LEVELS = ("basic", "standard", "advanced", "admin")
VALID_SETUP_STEPS = (
    "configuration", "training", "integration_setup",
    "permission_config", "testing", "activation",
)
VALID_CHANNELS = ("chat", "email", "sms", "whatsapp", "voice")


class AgentCreateRequest(BaseModel):
    """Request to create a new AI agent.

    Includes all configuration needed to provision an agent:
    name, specialty, description, channel list, and permission level.
    """
    name: str = Field(
        min_length=1, max_length=200,
        description="Agent display name",
    )
    specialty: str = Field(
        description="Agent specialty type",
    )
    description: Optional[str] = Field(
        default=None, max_length=2000,
        description="Agent description / purpose",
    )
    channels: List[str] = Field(
        default_factory=lambda: ["chat"],
        description="Supported channels",
    )
    permission_level: str = Field(
        default="standard",
        description="Permission level: basic/standard/advanced/admin",
    )
    base_model: Optional[str] = Field(
        default=None,
        description="AI model to use (e.g., gpt-4, claude-3)",
    )
    custom_permissions: Optional[List[str]] = Field(
        default=None,
        description="Additional custom permissions beyond the level",
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether this agent requires approval (BC-009)",
    )


class AgentConfig(BaseModel):
    """Internal agent configuration used during provisioning.

    Resolved from the create request after validation and parsing.
    """
    name: str
    specialty: str
    description: Optional[str] = None
    channels: List[str] = Field(default_factory=list)
    permissions: Dict[str, Any] = Field(default_factory=dict)
    base_model: Optional[str] = None
    requires_approval: bool = False
    clarification_needed: bool = False
    clarification_questions: List[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    """Agent record returned from API endpoints."""
    id: str
    company_id: str
    name: str
    specialty: str
    description: Optional[str] = None
    status: str
    channels: Dict[str, Any] = Field(default_factory=dict)
    permissions: Dict[str, Any] = Field(default_factory=dict)
    base_model: Optional[str] = None
    model_checkpoint_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    activated_at: Optional[str] = None
    updated_at: Optional[str] = None


class AgentListResponse(BaseModel):
    """Paginated list of agents."""
    agents: List[AgentResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0


class AgentCreateResponse(BaseModel):
    """Response from agent creation endpoint."""
    agent: AgentResponse
    requires_approval: bool = False
    clarification_needed: bool = False
    clarification_questions: List[str] = Field(default_factory=list)
    message: str = "Agent created successfully"


class SetupLogEntry(BaseModel):
    """Single setup step status."""
    step: str
    status: str
    configuration: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class SetupStatusResponse(BaseModel):
    """Agent setup progress status."""
    agent_id: str
    overall_status: str
    steps: List[SetupLogEntry] = Field(default_factory=list)
    completed_steps: int = 0
    total_steps: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class CompleteSetupRequest(BaseModel):
    """Request to complete agent setup with final configuration."""
    configuration: Dict[str, Any] = Field(
        default_factory=dict,
        description="Final configuration for activation",
    )
    skip_training: bool = Field(
        default=False,
        description="Skip training step (only for testing)",
    )


class CompleteSetupResponse(BaseModel):
    """Response after completing agent setup."""
    agent_id: str
    status: str
    message: str
    activated_at: Optional[str] = None


class PlanLimitsResponse(BaseModel):
    """Current agent count vs plan limit."""
    current_agents: int = 0
    max_agents: int = 0
    available_slots: int = 0
    can_create: bool = True


class AgentStatusDetail(BaseModel):
    """Detailed agent status with metrics."""
    agent: AgentResponse
    setup_status: Optional[SetupStatusResponse] = None
    active_instructions: Optional[Dict[str, Any]] = None
    active_ab_test: Optional[Dict[str, Any]] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════
# F-095: Specialty Template Schemas
# ══════════════════════════════════════════════════════════════════

class SpecialtyTemplate(BaseModel):
    """Pre-defined specialty template for agent creation."""
    specialty: str
    display_name: str
    description: str
    default_channels: List[str] = Field(default_factory=list)
    default_permission_level: str = "standard"
    suggested_base_model: Optional[str] = None
    is_financial: bool = False
    default_instructions: Dict[str, Any] = Field(default_factory=dict)


class SpecialtyTemplatesResponse(BaseModel):
    """List of all available specialty templates."""
    templates: List[SpecialtyTemplate] = Field(default_factory=list)
    total: int = 0


# ══════════════════════════════════════════════════════════════════
# F-096: Dynamic Instruction Workflow Schemas
# ══════════════════════════════════════════════════════════════════

VALID_INSTRUCTION_STATUSES = ("draft", "active", "archived")
VALID_AB_TEST_STATUSES = ("running", "completed", "cancelled")


class InstructionContent(BaseModel):
    """Full instruction set content (JSONB schema).

    Defines the behavioral rules, tone guidelines, escalation triggers,
    response templates, and confidence thresholds for an agent.
    """
    behavioral_rules: List[str] = Field(
        default_factory=list,
        description="Rules the agent must follow (e.g., 'Always greet by name')",
    )
    tone_guidelines: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tone configuration (formality, empathy_level, etc.)",
    )
    escalation_triggers: List[str] = Field(
        default_factory=list,
        description="Conditions that trigger escalation (e.g., 'refund > $100')",
    )
    response_templates: Dict[str, str] = Field(
        default_factory=dict,
        description="Named response templates (greeting, closing, escalation)",
    )
    prohibited_actions: List[str] = Field(
        default_factory=list,
        description="Actions the agent must never take",
    )
    confidence_thresholds: Dict[str, int] = Field(
        default_factory=dict,
        description="Thresholds for auto-approve, require-review, etc.",
    )


class InstructionSetCreateRequest(BaseModel):
    """Request to create a new instruction set."""
    name: str = Field(
        min_length=1, max_length=200,
        description="Instruction set name",
    )
    agent_id: str = Field(
        description="Agent ID this instruction set belongs to",
    )
    instructions: InstructionContent = Field(
        description="Instruction content",
    )
    is_default: bool = Field(
        default=False,
        description="Whether this should be the default instruction set",
    )


class InstructionSetUpdateRequest(BaseModel):
    """Request to update an existing instruction set (draft only)."""
    name: Optional[str] = Field(
        default=None, max_length=200,
        description="Updated instruction set name",
    )
    instructions: Optional[InstructionContent] = Field(
        default=None,
        description="Updated instruction content",
    )
    change_summary: Optional[str] = Field(
        default=None, max_length=1000,
        description="Description of changes made",
    )


class InstructionSetResponse(BaseModel):
    """Instruction set returned from API endpoints."""
    id: str
    company_id: str
    agent_id: str
    name: str
    version: int
    status: str
    instructions: Dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False
    created_by: Optional[str] = None
    published_by: Optional[str] = None
    published_at: Optional[str] = None
    change_summary: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class InstructionSetListResponse(BaseModel):
    """Paginated list of instruction sets."""
    sets: List[InstructionSetResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0


class InstructionVersionResponse(BaseModel):
    """A single version in the instruction set history."""
    id: str
    set_id: str
    company_id: str
    version: int
    instructions: Dict[str, Any] = Field(default_factory=dict)
    change_summary: Optional[str] = None
    published_by: Optional[str] = None
    published_at: Optional[str] = None
    created_at: Optional[str] = None


class VersionHistoryResponse(BaseModel):
    """Version history for an instruction set."""
    set_id: str
    versions: List[InstructionVersionResponse] = Field(
        default_factory=list,
    )
    total: int = 0


class PublishResponse(BaseModel):
    """Response from publishing an instruction set."""
    set_id: str
    previous_version: int
    new_version: int
    status: str
    published_at: Optional[str] = None
    message: str = "Instruction set published successfully"


class ArchiveResponse(BaseModel):
    """Response from archiving an instruction set."""
    set_id: str
    status: str
    message: str = "Instruction set archived successfully"


class RollbackResponse(BaseModel):
    """Response from rolling back to a previous version."""
    set_id: str
    previous_version: int
    rolled_back_to: int
    message: str = "Rolled back to previous version successfully"


# ══════════════════════════════════════════════════════════════════
# F-096: A/B Testing Schemas
# ══════════════════════════════════════════════════════════════════


class ABTestCreateRequest(BaseModel):
    """Request to create a new A/B test."""
    agent_id: str = Field(
        description="Agent to run the A/B test on",
    )
    set_a_id: str = Field(
        description="Instruction set for variant A",
    )
    set_b_id: str = Field(
        description="Instruction set for variant B",
    )
    traffic_split: int = Field(
        default=50, ge=0, le=100,
        description="Percentage of traffic for variant A (0-100)",
    )
    success_metric: str = Field(
        default="csat",
        description="Primary metric: csat, resolution_rate, or both",
    )
    duration_days: int = Field(
        default=14, ge=1, le=90,
        description="Maximum test duration in days",
    )


class ABTestResponse(BaseModel):
    """A/B test returned from API endpoints."""
    id: str
    company_id: str
    agent_id: str
    set_a_id: str
    set_b_id: str
    traffic_split: int = 50
    success_metric: str = "csat"
    duration_days: int = 14
    status: str = "running"
    winner_id: Optional[str] = None
    # Metrics
    tickets_a: int = 0
    tickets_b: int = 0
    csat_a: Optional[float] = None
    csat_b: Optional[float] = None
    resolution_a: Optional[float] = None
    resolution_b: Optional[float] = None
    # Timestamps
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


class ABTestDetailResponse(ABTestResponse):
    """Detailed A/B test response with set info and evaluation."""
    set_a_name: Optional[str] = None
    set_b_name: Optional[str] = None
    winner_name: Optional[str] = None
    evaluation: Optional[Dict[str, Any]] = None


class ABTestListResponse(BaseModel):
    """Paginated list of A/B tests."""
    tests: List[ABTestResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0


class ABTestStopRequest(BaseModel):
    """Request to stop an A/B test."""
    winner_id: Optional[str] = Field(
        default=None,
        description="Optional: manually select a winner when stopping",
    )


class ABTestStopResponse(BaseModel):
    """Response from stopping an A/B test."""
    test_id: str
    status: str
    winner_id: Optional[str] = None
    evaluation: Optional[Dict[str, Any]] = None
    message: str = "A/B test stopped successfully"


class ABTestEvaluation(BaseModel):
    """Statistical evaluation results for an A/B test."""
    test_id: str
    is_significant: bool = False
    p_value: Optional[float] = None
    winner: Optional[str] = None  # "A", "B", or None
    confidence_level: Optional[float] = None
    recommendation: str = "Insufficient data"
    tickets_a: int = 0
    tickets_b: int = 0
    min_required: int = 100


class ABAssignmentResponse(BaseModel):
    """Result of assigning a ticket to an A/B variant."""
    test_id: str
    ticket_id: str
    variant: str
    set_id: str
    is_deterministic: bool = True


class ActiveInstructionsResponse(BaseModel):
    """Active instructions for an agent (may be from A/B test)."""
    agent_id: str
    source: str = Field(
        description="Source type: 'instruction_set' or 'ab_test'",
    )
    set_id: Optional[str] = None
    set_name: Optional[str] = None
    test_id: Optional[str] = None
    variant: Optional[str] = None
    instructions: Dict[str, Any] = Field(default_factory=dict)
