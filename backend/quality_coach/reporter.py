"""
Quality Reporter for Weekly Quality Reports.

Generates weekly quality reports and tracks trends over time.

Features:
- Generate weekly quality reports
- Track quality trends
- Compare periods for analysis
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from shared.core_functions.logger import get_logger
from backend.quality_coach.analyzer import QualityLevel

logger = get_logger(__name__)


class ReportPeriod(str, Enum):
    """Report period types."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


@dataclass
class QualityTrend:
    """Quality trend data."""
    period_start: datetime
    period_end: datetime
    average_accuracy: float
    average_empathy: float
    average_efficiency: float
    average_overall: float
    total_interactions: int
    quality_distribution: Dict[str, int] = field(default_factory=dict)


@dataclass
class WeeklyReport:
    """Weekly quality report."""
    report_id: str
    company_id: str
    period_start: datetime
    period_end: datetime
    total_interactions: int
    average_scores: Dict[str, float]
    quality_distribution: Dict[str, int]
    top_performers: List[Dict[str, Any]]
    improvement_areas: List[str]
    trends: Dict[str, Any]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class QualityReporter:
    """
    Quality Reporter for generating quality reports.

    Features:
    - Generate weekly quality reports
    - Track quality trends over time
    - Compare different periods

    Example:
        reporter = QualityReporter()
        report = await reporter.generate_weekly_report("company_123")
    """

    def __init__(self) -> None:
        """Initialize Quality Reporter."""
        self._reports: Dict[str, WeeklyReport] = {}
        self._trends: Dict[str, List[QualityTrend]] = {}
        self._analyses: Dict[str, List[Dict[str, Any]]] = {}

        logger.info({
            "event": "quality_reporter_initialized"
        })

    async def generate_weekly_report(
        self,
        company_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate a weekly quality report.

        Args:
            company_id: Company identifier
            start_date: Report start date (default: 7 days ago)
            end_date: Report end date (default: now)

        Returns:
            Dict with weekly report data
        """
        report_id = f"qr_{uuid.uuid4().hex[:8]}"

        # Set date range
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=7)

        logger.info({
            "event": "weekly_report_generation_started",
            "report_id": report_id,
            "company_id": company_id,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat()
        })

        # Get analyses for the period
        company_analyses = self._analyses.get(company_id, [])
        period_analyses = [
            a for a in company_analyses
            if start_date <= datetime.fromisoformat(a.get("analyzed_at", "")) <= end_date
        ]

        # Calculate averages
        if period_analyses:
            avg_accuracy = sum(a.get("accuracy_score", 0) for a in period_analyses) / len(period_analyses)
            avg_empathy = sum(a.get("empathy_score", 0) for a in period_analyses) / len(period_analyses)
            avg_efficiency = sum(a.get("efficiency_score", 0) for a in period_analyses) / len(period_analyses)
            avg_overall = sum(a.get("overall_score", 0) for a in period_analyses) / len(period_analyses)
        else:
            # Default scores if no data
            avg_accuracy = 75.0
            avg_empathy = 75.0
            avg_efficiency = 75.0
            avg_overall = 75.0

        # Calculate quality distribution
        quality_distribution = {
            QualityLevel.EXCELLENT.value: 0,
            QualityLevel.GOOD.value: 0,
            QualityLevel.ACCEPTABLE.value: 0,
            QualityLevel.POOR.value: 0,
            QualityLevel.CRITICAL.value: 0
        }

        for analysis in period_analyses:
            level = analysis.get("quality_level", "acceptable")
            quality_distribution[level] = quality_distribution.get(level, 0) + 1

        # Identify top performers
        top_performers = self._identify_top_performers(period_analyses)

        # Identify improvement areas
        improvement_areas = self._identify_improvement_areas(avg_accuracy, avg_empathy, avg_efficiency)

        # Get trends
        trends = await self.get_trends(company_id, days=30)

        # Create report
        report = WeeklyReport(
            report_id=report_id,
            company_id=company_id,
            period_start=start_date,
            period_end=end_date,
            total_interactions=len(period_analyses),
            average_scores={
                "accuracy": round(avg_accuracy, 2),
                "empathy": round(avg_empathy, 2),
                "efficiency": round(avg_efficiency, 2),
                "overall": round(avg_overall, 2)
            },
            quality_distribution=quality_distribution,
            top_performers=top_performers,
            improvement_areas=improvement_areas,
            trends=trends
        )

        self._reports[report_id] = report

        logger.info({
            "event": "weekly_report_generated",
            "report_id": report_id,
            "company_id": company_id,
            "total_interactions": len(period_analyses),
            "average_overall": round(avg_overall, 2)
        })

        return {
            "success": True,
            "report_id": report_id,
            "company_id": company_id,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_interactions": len(period_analyses),
            "average_scores": report.average_scores,
            "quality_distribution": quality_distribution,
            "top_performers": top_performers,
            "improvement_areas": improvement_areas,
            "trends": trends,
            "generated_at": report.generated_at.isoformat()
        }

    def _identify_top_performers(
        self,
        analyses: List[Dict[str, Any]],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Identify top performing interactions."""
        sorted_analyses = sorted(
            analyses,
            key=lambda x: x.get("overall_score", 0),
            reverse=True
        )

        return [
            {
                "interaction_id": a.get("interaction_id"),
                "overall_score": a.get("overall_score"),
                "quality_level": a.get("quality_level")
            }
            for a in sorted_analyses[:limit]
            if a.get("overall_score", 0) >= 80
        ]

    def _identify_improvement_areas(
        self,
        avg_accuracy: float,
        avg_empathy: float,
        avg_efficiency: float
    ) -> List[str]:
        """Identify areas needing improvement."""
        areas = []

        if avg_accuracy < 70:
            areas.append("Accuracy needs improvement - review knowledge base")
        if avg_empathy < 70:
            areas.append("Empathy needs improvement - enhance active listening")
        if avg_efficiency < 70:
            areas.append("Efficiency needs improvement - optimize resolution paths")

        if not areas:
            areas.append("Maintain current quality standards")

        return areas

    async def get_trends(
        self,
        company_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get quality trends for a company.

        Args:
            company_id: Company identifier
            days: Number of days to analyze

        Returns:
            Dict with trend data
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        company_analyses = self._analyses.get(company_id, [])

        # Filter by date range
        period_analyses = [
            a for a in company_analyses
            if start_date <= datetime.fromisoformat(a.get("analyzed_at", "")) <= end_date
        ]

        if not period_analyses:
            return {
                "days_analyzed": days,
                "total_interactions": 0,
                "trend_direction": "stable",
                "daily_scores": []
            }

        # Group by day
        daily_scores: Dict[str, List[float]] = {}
        for analysis in period_analyses:
            date_key = datetime.fromisoformat(
                analysis.get("analyzed_at", "")
            ).strftime("%Y-%m-%d")
            if date_key not in daily_scores:
                daily_scores[date_key] = []
            daily_scores[date_key].append(analysis.get("overall_score", 0))

        # Calculate daily averages
        daily_averages = [
            {
                "date": date,
                "average_score": round(sum(scores) / len(scores), 2),
                "interaction_count": len(scores)
            }
            for date, scores in sorted(daily_scores.items())
        ]

        # Determine trend direction
        if len(daily_averages) >= 2:
            first_half = daily_averages[:len(daily_averages) // 2]
            second_half = daily_averages[len(daily_averages) // 2:]

            first_avg = sum(d["average_score"] for d in first_half) / len(first_half)
            second_avg = sum(d["average_score"] for d in second_half) / len(second_half)

            if second_avg > first_avg + 2:
                trend_direction = "improving"
            elif second_avg < first_avg - 2:
                trend_direction = "declining"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "stable"

        return {
            "days_analyzed": days,
            "total_interactions": len(period_analyses),
            "trend_direction": trend_direction,
            "daily_scores": daily_averages
        }

    async def compare_periods(
        self,
        company_id: str,
        period1: Dict[str, str],
        period2: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Compare quality between two periods.

        Args:
            company_id: Company identifier
            period1: First period {start, end}
            period2: Second period {start, end}

        Returns:
            Dict with comparison data
        """
        logger.info({
            "event": "period_comparison_started",
            "company_id": company_id
        })

        # Get analyses for each period
        company_analyses = self._analyses.get(company_id, [])

        def filter_period(analyses, period):
            start = datetime.fromisoformat(period["start"])
            end = datetime.fromisoformat(period["end"])
            return [
                a for a in analyses
                if start <= datetime.fromisoformat(a.get("analyzed_at", "")) <= end
            ]

        period1_analyses = filter_period(company_analyses, period1)
        period2_analyses = filter_period(company_analyses, period2)

        def calc_avg(analyses, key):
            if not analyses:
                return 0.0
            return sum(a.get(key, 0) for a in analyses) / len(analyses)

        period1_stats = {
            "total_interactions": len(period1_analyses),
            "average_accuracy": round(calc_avg(period1_analyses, "accuracy_score"), 2),
            "average_empathy": round(calc_avg(period1_analyses, "empathy_score"), 2),
            "average_efficiency": round(calc_avg(period1_analyses, "efficiency_score"), 2),
            "average_overall": round(calc_avg(period1_analyses, "overall_score"), 2)
        }

        period2_stats = {
            "total_interactions": len(period2_analyses),
            "average_accuracy": round(calc_avg(period2_analyses, "accuracy_score"), 2),
            "average_empathy": round(calc_avg(period2_analyses, "empathy_score"), 2),
            "average_efficiency": round(calc_avg(period2_analyses, "efficiency_score"), 2),
            "average_overall": round(calc_avg(period2_analyses, "overall_score"), 2)
        }

        # Calculate deltas
        deltas = {
            "accuracy": round(period2_stats["average_accuracy"] - period1_stats["average_accuracy"], 2),
            "empathy": round(period2_stats["average_empathy"] - period1_stats["average_empathy"], 2),
            "efficiency": round(period2_stats["average_efficiency"] - period1_stats["average_efficiency"], 2),
            "overall": round(period2_stats["average_overall"] - period1_stats["average_overall"], 2)
        }

        return {
            "success": True,
            "company_id": company_id,
            "period1": {
                "start": period1["start"],
                "end": period1["end"],
                "stats": period1_stats
            },
            "period2": {
                "start": period2["start"],
                "end": period2["end"],
                "stats": period2_stats
            },
            "deltas": deltas,
            "improvement": deltas["overall"] > 0
        }

    def add_analysis(
        self,
        company_id: str,
        analysis: Dict[str, Any]
    ) -> None:
        """Add an analysis to tracking."""
        if company_id not in self._analyses:
            self._analyses[company_id] = []
        self._analyses[company_id].append(analysis)

    def get_report(
        self,
        report_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a report by ID."""
        report = self._reports.get(report_id)
        if report:
            return {
                "report_id": report.report_id,
                "company_id": report.company_id,
                "period_start": report.period_start.isoformat(),
                "period_end": report.period_end.isoformat(),
                "total_interactions": report.total_interactions,
                "average_scores": report.average_scores,
                "quality_distribution": report.quality_distribution,
                "generated_at": report.generated_at.isoformat()
            }
        return None

    def get_company_reports(
        self,
        company_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get reports for a company."""
        reports = [
            r for r in self._reports.values()
            if r.company_id == company_id
        ]

        reports = sorted(reports, key=lambda r: r.generated_at, reverse=True)

        return [
            {
                "report_id": r.report_id,
                "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(),
                "average_overall": r.average_scores.get("overall", 0),
                "total_interactions": r.total_interactions
            }
            for r in reports[:limit]
        ]

    def get_status(self) -> Dict[str, Any]:
        """Get reporter status."""
        return {
            "total_reports": len(self._reports),
            "companies_tracked": len(self._analyses)
        }


def get_quality_reporter() -> QualityReporter:
    """
    Get a QualityReporter instance.

    Returns:
        QualityReporter instance
    """
    return QualityReporter()
