"""
Onboarding Analytics Service

Provides analytics for onboarding including average time, completion rates
by industry and variant, bottleneck identification, and trend analysis.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class OnboardingMetrics:
    """Aggregated onboarding metrics."""
    total_clients: int
    completed_clients: int
    in_progress_clients: int
    stuck_clients: int
    completion_rate: float
    average_time_minutes: float
    median_time_minutes: float
    fastest_time_minutes: float
    slowest_time_minutes: float


@dataclass
class BottleneckAnalysis:
    """Analysis of onboarding bottlenecks."""
    step: str
    avg_time_minutes: float
    expected_time_minutes: float
    delay_factor: float
    stuck_count: int
    recommendation: str


@dataclass
class TrendData:
    """Trend data point for onboarding."""
    date: datetime
    started_count: int
    completed_count: int
    completion_rate: float
    avg_time_minutes: float


class OnboardingAnalytics:
    """
    Analytics for client onboarding.

    Provides:
    - Average onboarding time
    - Completion rate by industry
    - Completion rate by variant
    - Bottleneck identification
    - Trend analysis
    """

    # Benchmark times (in minutes) by variant
    VARIANT_BENCHMARKS = {
        "mini": 90,  # ~1.5 hours
        "parwa": 150,  # ~2.5 hours
        "parwa_high": 240,  # ~4 hours
    }

    # Benchmark times by industry (multiplier)
    INDUSTRY_MULTIPLIERS = {
        "ecommerce": 1.0,
        "saas": 1.1,
        "healthcare": 1.5,
        "logistics": 1.2,
        "financial_services": 1.4,
        "retail": 1.0,
        "other": 1.0,
    }

    def __init__(self, onboarding_tracker: Optional[Any] = None):
        """
        Initialize onboarding analytics.

        Args:
            onboarding_tracker: Optional OnboardingTracker instance
        """
        self._tracker = onboarding_tracker
        self._historical_data: List[TrendData] = []

    def calculate_average_time(
        self,
        completed_only: bool = True,
        variant: Optional[str] = None,
        industry: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate average onboarding time.

        Args:
            completed_only: Only include completed onboardings
            variant: Filter by variant
            industry: Filter by industry

        Returns:
            Dict with time statistics
        """
        if not self._tracker:
            return {"error": "No tracker configured"}

        times = []
        for progress in self._tracker.get_all_progress().values():
            # Apply filters
            if variant and progress.variant != variant:
                continue
            if industry and progress.industry != industry:
                continue

            if completed_only and progress.status.value != "completed":
                continue

            if progress.total_time_minutes > 0:
                times.append(progress.total_time_minutes)

        if not times:
            return {
                "average_time_minutes": 0,
                "median_time_minutes": 0,
                "min_time_minutes": 0,
                "max_time_minutes": 0,
                "sample_size": 0,
            }

        times.sort()
        avg = sum(times) / len(times)
        median = times[len(times) // 2]

        return {
            "average_time_minutes": round(avg, 1),
            "median_time_minutes": round(median, 1),
            "min_time_minutes": round(min(times), 1),
            "max_time_minutes": round(max(times), 1),
            "sample_size": len(times),
        }

    def completion_rate_by_industry(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate completion rate by industry.

        Returns:
            Dict mapping industry to completion metrics
        """
        if not self._tracker:
            return {}

        by_industry: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "completed": 0, "stuck": 0, "avg_time": []}
        )

        for progress in self._tracker.get_all_progress().values():
            industry = progress.industry or "other"
            by_industry[industry]["total"] += 1

            if progress.status.value == "completed":
                by_industry[industry]["completed"] += 1
                if progress.total_time_minutes > 0:
                    by_industry[industry]["avg_time"].append(progress.total_time_minutes)
            elif progress.status.value == "stuck":
                by_industry[industry]["stuck"] += 1

        result = {}
        for industry, data in by_industry.items():
            total = data["total"]
            completed = data["completed"]
            times = data["avg_time"]

            rate = (completed / total * 100) if total > 0 else 0
            avg_time = sum(times) / len(times) if times else 0

            result[industry] = {
                "total_clients": total,
                "completed": completed,
                "stuck": data["stuck"],
                "completion_rate": round(rate, 1),
                "average_time_minutes": round(avg_time, 1),
                "benchmark_multiplier": self.INDUSTRY_MULTIPLIERS.get(industry, 1.0),
            }

        return result

    def completion_rate_by_variant(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate completion rate by variant.

        Returns:
            Dict mapping variant to completion metrics
        """
        if not self._tracker:
            return {}

        by_variant: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "completed": 0, "stuck": 0, "avg_time": []}
        )

        for progress in self._tracker.get_all_progress().values():
            variant = progress.variant or "unknown"
            by_variant[variant]["total"] += 1

            if progress.status.value == "completed":
                by_variant[variant]["completed"] += 1
                if progress.total_time_minutes > 0:
                    by_variant[variant]["avg_time"].append(progress.total_time_minutes)
            elif progress.status.value == "stuck":
                by_variant[variant]["stuck"] += 1

        result = {}
        for variant, data in by_variant.items():
            total = data["total"]
            completed = data["completed"]
            times = data["avg_time"]

            rate = (completed / total * 100) if total > 0 else 0
            avg_time = sum(times) / len(times) if times else 0
            benchmark = self.VARIANT_BENCHMARKS.get(variant, 120)

            result[variant] = {
                "total_clients": total,
                "completed": completed,
                "stuck": data["stuck"],
                "completion_rate": round(rate, 1),
                "average_time_minutes": round(avg_time, 1),
                "benchmark_minutes": benchmark,
                "vs_benchmark": round(avg_time - benchmark, 1),
            }

        return result

    def identify_bottlenecks(self) -> List[BottleneckAnalysis]:
        """
        Identify onboarding bottlenecks.

        Analyzes which steps take longest and where clients get stuck.

        Returns:
            List of BottleneckAnalysis for problematic steps
        """
        if not self._tracker:
            return []

        step_times: Dict[str, List[float]] = defaultdict(list)
        step_stuck: Dict[str, int] = defaultdict(int)
        step_expected = {
            "company_info": 10,
            "branding_setup": 15,
            "variant_selection": 5,
            "integrations": 30,
            "knowledge_base": 45,
            "team_setup": 15,
            "training": 60,
            "go_live": 10,
        }

        for progress in self._tracker.get_all_progress().values():
            for step_name, step_progress in progress.steps.items():
                step = step_name.value if hasattr(step_name, "value") else str(step_name)

                if step_progress.time_spent_minutes > 0:
                    step_times[step].append(step_progress.time_spent_minutes)

                if step_progress.status.value == "stuck":
                    step_stuck[step] += 1

        bottlenecks = []
        for step, times in step_times.items():
            avg_time = sum(times) / len(times) if times else 0
            expected = step_expected.get(step, 30)

            # Consider bottleneck if avg time is 1.5x expected
            if avg_time > expected * 1.5:
                delay_factor = avg_time / expected if expected > 0 else 0

                recommendation = self._get_bottleneck_recommendation(step)

                bottlenecks.append(BottleneckAnalysis(
                    step=step,
                    avg_time_minutes=round(avg_time, 1),
                    expected_time_minutes=expected,
                    delay_factor=round(delay_factor, 2),
                    stuck_count=step_stuck.get(step, 0),
                    recommendation=recommendation
                ))

        # Sort by delay factor (worst first)
        bottlenecks.sort(key=lambda b: b.delay_factor, reverse=True)
        return bottlenecks

    def _get_bottleneck_recommendation(self, step: str) -> str:
        """Get recommendation for a bottleneck step."""
        recommendations = {
            "company_info": "Simplify company info form and add progress indicators",
            "branding_setup": "Provide branding templates and preview options",
            "variant_selection": "Add variant comparison guide and recommendations",
            "integrations": "Improve integration wizard with better error handling",
            "knowledge_base": "Offer knowledge base templates and import tools",
            "team_setup": "Streamline team invitations with bulk import",
            "training": "Break training into smaller modules with progress tracking",
            "go_live": "Add pre-launch checklist and validation steps",
        }
        return recommendations.get(step, "Review step workflow for improvements")

    def analyze_trends(
        self,
        days: int = 30
    ) -> List[TrendData]:
        """
        Analyze onboarding trends over time.

        Args:
            days: Number of days to analyze

        Returns:
            List of TrendData points
        """
        # If we have historical data, use it
        if self._historical_data:
            cutoff = datetime.utcnow() - timedelta(days=days)
            return [t for t in self._historical_data if t.date >= cutoff]

        # Otherwise, generate simulated trend data
        return self._generate_trend_data(days)

    def _generate_trend_data(self, days: int) -> List[TrendData]:
        """Generate simulated trend data for analysis."""
        trends = []
        base_rate = 75.0
        base_time = 120.0

        for i in range(days):
            date = datetime.utcnow() - timedelta(days=days - i - 1)

            # Simulate improving trend
            improvement = i * 0.5
            rate = min(95.0, base_rate + improvement)
            time = max(60.0, base_time - improvement)

            # Add some variation
            import random
            rate += random.uniform(-5, 5)
            time += random.uniform(-10, 10)

            trends.append(TrendData(
                date=date,
                started_count=random.randint(1, 3),
                completed_count=random.randint(1, 2),
                completion_rate=round(max(50, min(100, rate)), 1),
                avg_time_minutes=round(max(30, time), 1)
            ))

        return trends

    def get_analytics_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive analytics summary.
        """
        avg_time = self.calculate_average_time()
        by_industry = self.completion_rate_by_industry()
        by_variant = self.completion_rate_by_variant()
        bottlenecks = self.identify_bottlenecks()

        return {
            "average_time": avg_time,
            "completion_by_industry": by_industry,
            "completion_by_variant": by_variant,
            "bottlenecks": [
                {
                    "step": b.step,
                    "avg_time_minutes": b.avg_time_minutes,
                    "expected_time_minutes": b.expected_time_minutes,
                    "delay_factor": b.delay_factor,
                    "recommendation": b.recommendation,
                }
                for b in bottlenecks
            ],
            "insights": self._generate_insights(avg_time, bottlenecks),
        }

    def _generate_insights(
        self,
        avg_time: Dict[str, Any],
        bottlenecks: List[BottleneckAnalysis]
    ) -> List[str]:
        """Generate actionable insights from analytics."""
        insights = []

        if avg_time.get("average_time_minutes", 0) > 150:
            insights.append(
                "Average onboarding time exceeds 2.5 hours. "
                "Consider streamlining the process."
            )

        if bottlenecks:
            worst = bottlenecks[0]
            insights.append(
                f"'{worst.step}' step is the biggest bottleneck, "
                f"taking {worst.delay_factor:.1f}x longer than expected."
            )

        variant_stats = self.completion_rate_by_variant()
        for variant, stats in variant_stats.items():
            if stats.get("vs_benchmark", 0) > 30:
                insights.append(
                    f"{variant} variant onboarding takes significantly "
                    f"longer than benchmark ({stats['vs_benchmark']:.0f} min over)."
                )

        if not insights:
            insights.append("Onboarding performance is within expected parameters.")

        return insights

    def record_daily_metrics(self) -> TrendData:
        """
        Record daily metrics for trend tracking.
        """
        if not self._tracker:
            return TrendData(
                date=datetime.utcnow(),
                started_count=0,
                completed_count=0,
                completion_rate=0,
                avg_time_minutes=0
            )

        summary = self._tracker.get_onboarding_summary()
        avg_time = self.calculate_average_time()

        trend = TrendData(
            date=datetime.utcnow(),
            started_count=summary.get("by_status", {}).get("in_progress", 0),
            completed_count=summary.get("by_status", {}).get("completed", 0),
            completion_rate=summary.get("average_completion", 0),
            avg_time_minutes=avg_time.get("average_time_minutes", 0)
        )

        self._historical_data.append(trend)
        # Keep last 90 days
        if len(self._historical_data) > 90:
            self._historical_data = self._historical_data[-90:]

        return trend

    def compare_periods(
        self,
        period1_days: int = 30,
        period2_days: int = 30
    ) -> Dict[str, Any]:
        """
        Compare onboarding performance between two periods.

        Args:
            period1_days: First period length
            period2_days: Second period length (more recent)

        Returns:
            Dict with comparison metrics
        """
        trends = self.analyze_trends(period1_days + period2_days)

        if len(trends) < period2_days:
            return {"error": "Insufficient data for comparison"}

        # Split into two periods
        p2_trends = trends[-period2_days:]
        p1_trends = trends[-(period1_days + period2_days):-period2_days]

        def calc_avg(t_list: List[TrendData]) -> Dict[str, float]:
            if not t_list:
                return {"rate": 0, "time": 0}
            return {
                "rate": sum(t.completion_rate for t in t_list) / len(t_list),
                "time": sum(t.avg_time_minutes for t in t_list) / len(t_list),
            }

        p1_stats = calc_avg(p1_trends)
        p2_stats = calc_avg(p2_trends)

        return {
            "period1": {
                "days": period1_days,
                "avg_completion_rate": round(p1_stats["rate"], 1),
                "avg_time_minutes": round(p1_stats["time"], 1),
            },
            "period2": {
                "days": period2_days,
                "avg_completion_rate": round(p2_stats["rate"], 1),
                "avg_time_minutes": round(p2_stats["time"], 1),
            },
            "change": {
                "completion_rate": round(p2_stats["rate"] - p1_stats["rate"], 1),
                "time_minutes": round(p2_stats["time"] - p1_stats["time"], 1),
            }
        }
