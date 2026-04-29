"""
PARWA Dashboard Schemas (Week 15 — Dashboard + Analytics)

Pydantic schemas for all dashboard and analytics endpoints:
- F-036: Dashboard Home — unified widget data
- F-037: Activity Feed — real-time event stream
- F-038: Key Metrics Aggregation — KPIs
- F-039: Adaptation Tracker — 30-day AI learning progress
- F-040: Running Savings Counter — AI vs human cost comparison
- F-041: Workforce Allocation — AI vs human distribution
- F-042: Growth Nudge Alert — usage pattern analysis
- F-043: Ticket Volume Forecast — predictive analytics
- F-044: CSAT Trends — customer satisfaction analytics
- F-045: Export Reports — CSV/PDF report generation

Building Codes: BC-001 (multi-tenant), BC-011 (auth), BC-012 (responses)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ══════════════════════════════════════════════════════════════════
# F-036: DASHBOARD HOME — Unified Widget Data
# ══════════════════════════════════════════════════════════════════


class WidgetConfig(BaseModel):
    """Configuration for a single dashboard widget."""

    widget_id: str
    widget_type: str  # kpi, chart, feed, counter, table
    title: str
    position: Dict[str, int] = Field(
        default_factory=lambda: {"row": 0, "col": 0},
    )
    size: Dict[str, int] = Field(
        default_factory=lambda: {"width": 1, "height": 1},
    )
    enabled: bool = True
    refresh_interval_seconds: Optional[int] = None


class DashboardLayoutResponse(BaseModel):
    """Dashboard layout configuration."""

    layout_id: str
    widgets: List[WidgetConfig]
    is_default: bool = True


class DashboardHomeResponse(BaseModel):
    """Unified dashboard home data — single API call for all widgets.

    Aggregates data from multiple subsystems into one payload
    so the frontend can render the entire dashboard in one round-trip.
    """

    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Ticket summary counts (F-038)",
    )
    kpis: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key performance indicators (F-038)",
    )
    sla: Dict[str, Any] = Field(
        default_factory=dict,
        description="SLA metrics",
    )
    trend: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Ticket volume trend (last 30 days)",
    )
    by_category: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Category distribution",
    )
    activity_feed: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Recent activity events (F-037)",
    )
    savings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Running savings counter (F-040)",
    )
    workforce: Dict[str, Any] = Field(
        default_factory=dict,
        description="AI vs human workforce allocation (F-041)",
    )
    csat: Dict[str, Any] = Field(
        default_factory=dict,
        description="CSAT trend data (F-044)",
    )
    anomalies: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Detected anomalies / spike alerts",
    )
    layout: Optional[DashboardLayoutResponse] = None
    generated_at: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
# F-037: ACTIVITY FEED — Real-Time Event Stream
# ══════════════════════════════════════════════════════════════════


class ActivityEvent(BaseModel):
    """A single activity event in the global feed."""

    event_id: str
    event_type: str  # ticket_created, status_changed, assigned, resolved, etc.
    actor_id: Optional[str] = None
    actor_type: Optional[str] = None  # human, ai, system
    actor_name: Optional[str] = None
    description: str
    ticket_id: Optional[str] = None
    ticket_subject: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ActivityFeedResponse(BaseModel):
    """Paginated activity feed response."""

    events: List[ActivityEvent]
    total: int
    page: int
    page_size: int
    has_more: bool


# ══════════════════════════════════════════════════════════════════
# F-038: KEY METRICS AGGREGATION — KPIs
# ══════════════════════════════════════════════════════════════════


class KPIData(BaseModel):
    """A single KPI metric card."""

    key: str
    label: str
    value: Any
    previous_value: Optional[Any] = None
    change_pct: Optional[float] = None
    change_direction: Optional[str] = None  # up, down, neutral
    unit: Optional[str] = None  # %, hours, count, $
    is_anomaly: bool = False
    sparkline: List[float] = Field(default_factory=list)


class MetricsResponse(BaseModel):
    """Key metrics aggregation response."""

    kpis: List[KPIData]
    period: str  # last_7d, last_30d, last_90d
    generated_at: str


# ══════════════════════════════════════════════════════════════════
# F-039: ADAPTATION TRACKER — 30-Day AI Learning Progress
# ══════════════════════════════════════════════════════════════════


class AdaptationDayData(BaseModel):
    """Single day's adaptation data point."""

    date: str
    ai_accuracy: float
    human_accuracy: float
    gap: float
    tickets_processed: int
    mistakes_count: int
    mistake_rate: float


class AdaptationTrackerResponse(BaseModel):
    """30-day AI learning progress."""

    daily_data: List[AdaptationDayData]
    overall_improvement_pct: float
    current_accuracy: float
    starting_accuracy: float
    best_day: Optional[AdaptationDayData] = None
    worst_day: Optional[AdaptationDayData] = None
    training_runs_count: int = 0
    drift_reports_count: int = 0


# ══════════════════════════════════════════════════════════════════
# F-040: RUNNING SAVINGS COUNTER — AI vs Human Cost
# ══════════════════════════════════════════════════════════════════


class SavingsSnapshot(BaseModel):
    """Single savings data point."""

    period: str
    date: str
    tickets_ai: int
    tickets_human: int
    ai_cost: float
    human_cost: float
    savings: float
    cumulative_savings: float


class SavingsCounterResponse(BaseModel):
    """Running savings counter response."""

    current_month: SavingsSnapshot
    previous_month: SavingsSnapshot
    all_time_savings: float
    all_time_tickets_ai: int
    all_time_tickets_human: int
    monthly_trend: List[SavingsSnapshot]
    avg_cost_per_ticket_ai: float
    avg_cost_per_ticket_human: float
    savings_pct: float


# ══════════════════════════════════════════════════════════════════
# F-041: WORKFORCE ALLOCATION — AI vs Human Distribution
# ══════════════════════════════════════════════════════════════════


class WorkforceSplit(BaseModel):
    """AI vs human ticket distribution for a period."""

    period: str
    date: str
    ai_tickets: int
    human_tickets: int
    ai_pct: float
    human_pct: float
    total: int


class WorkforceAllocationResponse(BaseModel):
    """Workforce allocation response."""

    current_split: WorkforceSplit
    daily_trend: List[WorkforceSplit]
    by_channel: Dict[str, WorkforceSplit] = Field(
        default_factory=dict,
        description="Breakdown by channel (email, chat, sms, etc.)",
    )
    by_category: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Breakdown by ticket category",
    )
    ai_resolution_rate: float = 0.0
    human_resolution_rate: float = 0.0


# ══════════════════════════════════════════════════════════════════
# F-042: GROWTH NUDGE ALERT — Usage Pattern Analysis
# ══════════════════════════════════════════════════════════════════


class GrowthNudge(BaseModel):
    """A single growth nudge alert."""

    nudge_id: str
    nudge_type: str  # underutilized, scaling, upgrade, feature_discovery
    severity: str  # info, suggestion, recommendation, urgent
    title: str
    message: str
    action_label: Optional[str] = None
    action_url: Optional[str] = None
    dismissed: bool = False
    detected_at: str
    expires_at: Optional[str] = None


class GrowthNudgeResponse(BaseModel):
    """Growth nudge alerts response."""

    nudges: List[GrowthNudge]
    total: int
    dismissed_count: int


# ══════════════════════════════════════════════════════════════════
# F-043: TICKET VOLUME FORECAST — Predictive Analytics
# ══════════════════════════════════════════════════════════════════


class ForecastPoint(BaseModel):
    """Single forecast data point."""

    date: str
    predicted: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    actual: Optional[float] = None


class ForecastResponse(BaseModel):
    """Ticket volume forecast response."""

    historical: List[ForecastPoint]
    forecast: List[ForecastPoint]
    model_type: str  # moving_average, linear_regression, etc.
    confidence_level: float
    seasonality_detected: bool
    trend_direction: str  # increasing, decreasing, stable
    avg_daily_volume: float


# ══════════════════════════════════════════════════════════════════
# F-044: CSAT TRENDS — Customer Satisfaction Analytics
# ══════════════════════════════════════════════════════════════════


class CSATDayData(BaseModel):
    """Single day's CSAT data."""

    date: str
    avg_rating: float
    total_ratings: int
    distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown by rating (1-5)",
    )


class CSATByDimension(BaseModel):
    """CSAT broken down by a dimension (agent, category, channel)."""

    dimension_name: str
    avg_rating: float
    total_ratings: int
    total: int


class CSATResponse(BaseModel):
    """CSAT trend analytics response."""

    daily_trend: List[CSATDayData]
    overall_avg: float
    overall_total: int
    by_agent: List[CSATByDimension]
    by_category: List[CSATByDimension]
    by_channel: List[CSATByDimension]
    trend_direction: str  # improving, declining, stable
    change_vs_previous_period: Optional[float] = None


# ══════════════════════════════════════════════════════════════════
# F-045: EXPORT REPORTS — CSV/PDF Report Generation
# ══════════════════════════════════════════════════════════════════


class ExportRequest(BaseModel):
    """Report export request."""

    report_type: str  # summary, tickets, agents, sla, csat, forecast, full
    format: str  # csv, pdf
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    filters: Dict[str, Any] = Field(default_factory=dict)


class ExportJobResponse(BaseModel):
    """Export job status."""

    job_id: str
    report_type: str
    format: str
    status: str  # pending, processing, completed, failed
    download_url: Optional[str] = None
    file_size_bytes: Optional[int] = None
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
