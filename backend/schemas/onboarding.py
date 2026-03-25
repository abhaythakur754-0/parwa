"""
Onboarding Schemas

Pydantic schemas for onboarding-related API requests and responses.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class OnboardingStepEnum(str, Enum):
    """Onboarding steps."""
    COMPANY_INFO = "company_info"
    BRANDING_SETUP = "branding_setup"
    VARIANT_SELECTION = "variant_selection"
    INTEGRATIONS = "integrations"
    KNOWLEDGE_BASE = "knowledge_base"
    TEAM_SETUP = "team_setup"
    TRAINING = "training"
    GO_LIVE = "go_live"


class OnboardingStatusEnum(str, Enum):
    """Onboarding status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    STUCK = "stuck"
    ABANDONED = "abandoned"


class MilestoneStatusEnum(str, Enum):
    """Milestone status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    MISSED = "missed"


# ============ Request Schemas ============

class StartOnboardingRequest(BaseModel):
    """Request to start onboarding for a client."""
    client_id: str = Field(..., description="Client identifier")
    variant: str = Field(..., description="Selected variant (mini, parwa, parwa_high)")
    industry: Optional[str] = Field(None, description="Client industry")
    company_name: Optional[str] = Field(None, description="Company name")

    @field_validator("variant")
    @classmethod
    def validate_variant(cls, v: str) -> str:
        valid = ["mini", "parwa", "parwa_high"]
        if v.lower() not in valid:
            raise ValueError(f"Variant must be one of {valid}")
        return v.lower()


class CompleteStepRequest(BaseModel):
    """Request to complete an onboarding step."""
    client_id: str = Field(..., description="Client identifier")
    step: OnboardingStepEnum = Field(..., description="Step to complete")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Step metadata")


class UpdateMilestoneProgressRequest(BaseModel):
    """Request to update milestone progress."""
    client_id: str = Field(..., description="Client identifier")
    milestone_type: str = Field(..., description="Type of milestone")
    current_value: float = Field(..., ge=0, description="Current value")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class CreateMilestoneRequest(BaseModel):
    """Request to create a custom milestone."""
    name: str = Field(..., min_length=1, max_length=100, description="Milestone name")
    description: str = Field(..., min_length=1, max_length=500, description="Milestone description")
    target_value: Optional[float] = Field(None, ge=0, description="Target value")
    target_unit: Optional[str] = Field(None, max_length=50, description="Unit for target value")
    due_days_from_start: Optional[int] = Field(None, ge=1, le=365, description="Days from start")
    is_required: bool = Field(True, description="Whether milestone is required")


# ============ Response Schemas ============

class StepProgressResponse(BaseModel):
    """Response for step progress."""
    step: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    time_spent_minutes: float = 0.0
    attempts: int = 0
    is_stuck: bool = False


class OnboardingProgressResponse(BaseModel):
    """Response for onboarding progress."""
    client_id: str
    status: OnboardingStatusEnum
    completion_percentage: float = Field(..., ge=0, le=100)
    current_step: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_time_minutes: float = 0.0
    variant: Optional[str] = None
    industry: Optional[str] = None
    steps: List[StepProgressResponse] = []

    model_config = {"from_attributes": True}


class OnboardingMilestoneResponse(BaseModel):
    """Response for onboarding milestone."""
    milestone_id: str
    name: str
    description: str
    milestone_type: str
    status: MilestoneStatusEnum
    current_value: Optional[float] = None
    target_value: Optional[float] = None
    progress_percentage: float = 0.0
    due_at: Optional[datetime] = None
    achieved_at: Optional[datetime] = None
    is_required: bool = True

    model_config = {"from_attributes": True}


class TimeMetricsResponse(BaseModel):
    """Response for time metrics."""
    average_time_minutes: float
    median_time_minutes: float
    min_time_minutes: float
    max_time_minutes: float
    sample_size: int


class IndustryStatsResponse(BaseModel):
    """Response for industry statistics."""
    industry: str
    total_clients: int
    completed: int
    stuck: int
    completion_rate: float
    average_time_minutes: float
    benchmark_multiplier: float


class VariantStatsResponse(BaseModel):
    """Response for variant statistics."""
    variant: str
    total_clients: int
    completed: int
    stuck: int
    completion_rate: float
    average_time_minutes: float
    benchmark_minutes: float
    vs_benchmark: float


class BottleneckResponse(BaseModel):
    """Response for bottleneck analysis."""
    step: str
    avg_time_minutes: float
    expected_time_minutes: float
    delay_factor: float
    stuck_count: int
    recommendation: str


class OnboardingAnalyticsResponse(BaseModel):
    """Comprehensive onboarding analytics response."""
    average_time: TimeMetricsResponse
    completion_by_industry: Dict[str, IndustryStatsResponse]
    completion_by_variant: Dict[str, VariantStatsResponse]
    bottlenecks: List[BottleneckResponse]
    insights: List[str]

    model_config = {"from_attributes": True}


class TrendDataPointResponse(BaseModel):
    """Response for trend data point."""
    date: datetime
    started_count: int
    completed_count: int
    completion_rate: float
    avg_time_minutes: float


class MilestoneSummaryResponse(BaseModel):
    """Response for milestone summary."""
    client_id: str
    total_milestones: int
    achieved: int
    pending: int
    in_progress: int
    missed: int
    completion_rate: float
    required_achieved: int


# ============ List Response Schemas ============

class OnboardingProgressListResponse(BaseModel):
    """Response for list of onboarding progress."""
    items: List[OnboardingProgressResponse]
    total: int
    by_status: Dict[str, int]
    average_completion: float


class MilestoneListResponse(BaseModel):
    """Response for list of milestones."""
    items: List[OnboardingMilestoneResponse]
    total: int
    achieved_count: int
    pending_count: int


class TrendAnalysisResponse(BaseModel):
    """Response for trend analysis."""
    period_days: int
    trend_data: List[TrendDataPointResponse]
    summary: Dict[str, Any]


class PeriodComparisonResponse(BaseModel):
    """Response for period comparison."""
    period1: Dict[str, Any]
    period2: Dict[str, Any]
    change: Dict[str, float]


# ============ Analytics Request Schemas ============

class OnboardingAnalyticsRequest(BaseModel):
    """Request for onboarding analytics."""
    variant: Optional[str] = Field(None, description="Filter by variant")
    industry: Optional[str] = Field(None, description="Filter by industry")
    days: int = Field(30, ge=1, le=365, description="Number of days to analyze")


class TrendAnalysisRequest(BaseModel):
    """Request for trend analysis."""
    days: int = Field(30, ge=7, le=365, description="Number of days for analysis")
    variant: Optional[str] = Field(None, description="Filter by variant")
    industry: Optional[str] = Field(None, description="Filter by industry")


class PeriodComparisonRequest(BaseModel):
    """Request for period comparison."""
    period1_days: int = Field(30, ge=7, le=180, description="First period length")
    period2_days: int = Field(30, ge=7, le=180, description="Second period length")
