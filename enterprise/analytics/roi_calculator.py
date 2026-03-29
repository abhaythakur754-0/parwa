"""
Enterprise Analytics - ROI Calculator
Calculate return on investment for enterprise clients
"""
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ROIMetrics(BaseModel):
    """ROI calculation metrics"""
    total_investment: float
    total_savings: float
    time_saved_hours: float
    labor_cost_per_hour: float
    automation_rate: float

    model_config = ConfigDict()


class ROIResult(BaseModel):
    """ROI calculation result"""
    roi_percentage: float
    net_savings: float
    payback_period_months: float
    annual_savings: float

    model_config = ConfigDict()


class ROICalculator:
    """
    Calculate ROI for enterprise AI support automation.
    """

    DEFAULT_LABOR_COST = 25.0  # USD per hour
    DEFAULT_AUTOMATION_RATE = 0.85

    def __init__(self, client_id: str):
        self.client_id = client_id

    def calculate(
        self,
        monthly_tickets: int,
        avg_resolution_time_minutes: float = 5.0,
        labor_cost_per_hour: Optional[float] = None,
        automation_rate: Optional[float] = None,
        monthly_subscription_cost: float = 5000.0
    ) -> ROIResult:
        """Calculate ROI"""

        labor_cost = labor_cost_per_hour or self.DEFAULT_LABOR_COST
        auto_rate = automation_rate or self.DEFAULT_AUTOMATION_RATE

        # Calculate time saved
        manual_time_per_ticket = 15.0  # minutes
        time_saved_per_ticket = manual_time_per_ticket - avg_resolution_time_minutes
        automated_tickets = monthly_tickets * auto_rate

        # Calculate savings
        hours_saved = (time_saved_per_ticket * automated_tickets) / 60.0
        monthly_labor_savings = hours_saved * labor_cost
        annual_savings = (monthly_labor_savings - monthly_subscription_cost) * 12

        # Calculate ROI
        total_investment = monthly_subscription_cost * 12
        roi_percentage = (annual_savings / total_investment) * 100 if total_investment > 0 else 0

        # Calculate payback period
        monthly_net_savings = monthly_labor_savings - monthly_subscription_cost
        payback_months = monthly_subscription_cost / monthly_net_savings if monthly_net_savings > 0 else 0

        return ROIResult(
            roi_percentage=round(roi_percentage, 2),
            net_savings=round(annual_savings, 2),
            payback_period_months=round(payback_months, 1),
            annual_savings=round(annual_savings, 2)
        )

    def get_breakdown(self, metrics: ROIMetrics) -> Dict[str, Any]:
        """Get detailed ROI breakdown"""
        return {
            "investment": {
                "subscription": metrics.total_investment,
                "implementation": metrics.total_investment * 0.2
            },
            "savings": {
                "labor": metrics.time_saved_hours * metrics.labor_cost_per_hour,
                "efficiency": metrics.time_saved_hours * metrics.labor_cost_per_hour * 0.1,
                "quality": metrics.time_saved_hours * metrics.labor_cost_per_hour * 0.05
            },
            "automation_benefits": {
                "tickets_automated_percent": metrics.automation_rate * 100,
                "time_saved_hours": metrics.time_saved_hours
            }
        }
