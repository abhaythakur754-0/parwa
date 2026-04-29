"""
Training Schemas — F-100/F-101

Pydantic models for training API request/response validation.

Building Codes:
- BC-001: All schemas include company_id scoping
- BC-012: Structured error responses
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════════════════════════
# F-101: Mistake Threshold Schemas
# ═══════════════════════════════════════════════════════════════════════════════


class MistakeReportRequest(BaseModel):
    """Request to report an agent mistake."""

    agent_id: str = Field(..., description="Agent that made the mistake")
    ticket_id: Optional[str] = Field(None, description="Related ticket ID")
    mistake_type: str = Field(
        "incorrect_response",
        description="Type of mistake (incorrect_response, hallucination, tone_issue, incomplete, policy_violation, escalation_needed, other)",
    )
    original_response: Optional[str] = Field(
        None, description="The incorrect AI response"
    )
    expected_response: Optional[str] = Field(
        None, description="What the response should have been"
    )
    correction: Optional[str] = Field(None, description="Correction or action taken")
    severity: str = Field(
        "medium", description="Severity level (low, medium, high, critical)"
    )


class MistakeReportResponse(BaseModel):
    """Response after reporting a mistake."""

    status: str = "reported"
    mistake_id: str
    agent_id: str
    current_count: int
    threshold: int = 50  # LOCKED per BC-007 rule 10
    training_triggered: bool = False
    training_run_id: Optional[str] = None


class ThresholdStatusResponse(BaseModel):
    """Threshold status for an agent."""

    agent_id: str
    current_count: int
    threshold: int = 50  # LOCKED
    percentage: float
    triggered: bool
    remaining: int


class MistakeHistoryItem(BaseModel):
    """Single mistake history item."""

    id: str
    ticket_id: Optional[str] = None
    mistake_type: str
    severity: str
    original_response: Optional[str] = None
    used_in_training: bool = False
    created_at: Optional[str] = None


class MistakeHistoryResponse(BaseModel):
    """Mistake history list response."""

    mistakes: List[MistakeHistoryItem]
    total: int
    limit: int
    offset: int


class MistakeStatsResponse(BaseModel):
    """Mistake statistics for an agent."""

    total_mistakes: int
    threshold: int = 50
    percentage_to_threshold: float
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    used_in_training: int
    available_for_training: int


# ═══════════════════════════════════════════════════════════════════════════════
# F-100: Training Run Schemas
# ═══════════════════════════════════════════════════════════════════════════════


class TrainingRunCreateRequest(BaseModel):
    """Request to create a training run."""

    agent_id: str = Field(..., description="Agent to train")
    dataset_id: str = Field(..., description="Dataset to use for training")
    name: Optional[str] = Field(None, description="Optional run name")
    trigger: str = Field(
        "manual",
        description="Trigger type (manual, auto_threshold, scheduled, cold_start)",
    )
    base_model: Optional[str] = Field(None, description="Base model to fine-tune")
    epochs: int = Field(3, ge=1, le=10, description="Number of training epochs")
    learning_rate: float = Field(0.0001, ge=1e-6, le=1e-2, description="Learning rate")
    batch_size: int = Field(16, ge=1, le=64, description="Batch size")


class TrainingRunCreateResponse(BaseModel):
    """Response after creating a training run."""

    status: str
    run_id: Optional[str] = None
    agent_id: str
    dataset_id: str
    trigger: str
    epochs: int
    estimated_completion_minutes: Optional[int] = None
    error: Optional[str] = None


class TrainingRunResponse(BaseModel):
    """Full training run details."""

    id: str
    company_id: str
    agent_id: str
    dataset_id: Optional[str] = None
    name: Optional[str] = None
    trigger: str
    base_model: Optional[str] = None
    status: str
    progress_pct: float = 0.0
    current_epoch: int = 0
    total_epochs: int = 3
    epochs: int = 3
    learning_rate: Optional[float] = None
    batch_size: int = 16
    metrics: Dict[str, Any] = Field(default_factory=dict)
    model_path: Optional[str] = None
    checkpoint_path: Optional[str] = None
    provider: Optional[str] = None
    instance_id: Optional[str] = None
    gpu_type: Optional[str] = None
    cost_usd: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None
    error_message: Optional[str] = None


class TrainingRunListResponse(BaseModel):
    """List of training runs."""

    runs: List[TrainingRunResponse]
    total: int
    limit: int
    offset: int


class TrainingRunProgressUpdate(BaseModel):
    """Training progress update (internal use)."""

    epoch: int
    progress_pct: float
    metrics: Optional[Dict[str, Any]] = None


class TrainingRunCancelResponse(BaseModel):
    """Response after cancelling a training run."""

    status: str
    run_id: str


# ═══════════════════════════════════════════════════════════════════════════════
# Training Stats Schemas
# ═══════════════════════════════════════════════════════════════════════════════


class TrainingStatsResponse(BaseModel):
    """Training statistics for a tenant or agent."""

    total_runs: int
    completed: int
    failed: int
    running: int
    queued: int
    total_cost_usd: float
    by_trigger: Dict[str, int] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Checkpoint Schemas
# ═══════════════════════════════════════════════════════════════════════════════


class CheckpointCreateRequest(BaseModel):
    """Request to create a checkpoint."""

    epoch: int = Field(..., ge=1, description="Epoch number")
    checkpoint_name: str = Field(..., description="Name for the checkpoint")
    model_path: Optional[str] = None
    s3_path: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    is_best: bool = False


class CheckpointResponse(BaseModel):
    """Checkpoint details."""

    checkpoint_id: str
    checkpoint_name: str
    model_path: Optional[str] = None
    s3_path: Optional[str] = None
    epoch: int
    metrics: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class CheckpointCreateResponse(BaseModel):
    """Response after creating a checkpoint."""

    status: str
    checkpoint_id: str
    is_best: bool
