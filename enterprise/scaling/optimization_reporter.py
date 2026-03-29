"""
Optimization Reporter Module - Week 52, Builder 5
Optimization reports and recommendations
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Type of optimization report"""
    PERFORMANCE_SUMMARY = "performance_summary"
    BOTTLENECK_ANALYSIS = "bottleneck_analysis"
    CAPACITY_PLANNING = "capacity_planning"
    COST_OPTIMIZATION = "cost_optimization"
    SECURITY_OPTIMIZATION = "security_optimization"
    COMPREHENSIVE = "comprehensive"


class Priority(Enum):
    """Optimization priority"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OptimizationCategory(Enum):
    """Category of optimization"""
    PERFORMANCE = "performance"
    COST = "cost"
    RELIABILITY = "reliability"
    SCALABILITY = "scalability"
    SECURITY = "security"


@dataclass
class OptimizationItem:
    """Single optimization recommendation"""
    title: str
    category: OptimizationCategory
    priority: Priority
    description: str
    current_state: str
    recommended_state: str
    estimated_impact: str
    effort: str  # low, medium, high
    cost: str  # free, low, medium, high
    implementation_steps: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    metrics_affected: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "title": self.title,
            "category": self.category.value,
            "priority": self.priority.value,
            "description": self.description,
            "current_state": self.current_state,
            "recommended_state": self.recommended_state,
            "estimated_impact": self.estimated_impact,
            "effort": self.effort,
            "cost": self.cost,
            "implementation_steps": self.implementation_steps,
            "risks": self.risks,
        }


@dataclass
class OptimizationReport:
    """Complete optimization report"""
    report_id: str
    report_type: ReportType
    generated_at: datetime = field(default_factory=datetime.utcnow)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    optimizations: List[OptimizationItem] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "generated_at": self.generated_at.isoformat(),
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "optimizations": [o.to_dict() for o in self.optimizations],
            "summary": self.summary,
            "metrics": self.metrics,
        }


class OptimizationEngine:
    """
    Engine for generating optimization recommendations.
    """

    def __init__(self):
        self.optimizations: List[OptimizationItem] = []
        self._rules: List[Dict[str, Any]] = []
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        """Setup default optimization rules"""
        # CPU optimization rules
        self._rules.append({
            "category": OptimizationCategory.PERFORMANCE,
            "condition": lambda m: m.get("cpu_avg", 0) > 70,
            "generator": self._generate_cpu_optimization,
        })

        # Memory optimization rules
        self._rules.append({
            "category": OptimizationCategory.PERFORMANCE,
            "condition": lambda m: m.get("memory_avg", 0) > 75,
            "generator": self._generate_memory_optimization,
        })

        # Latency optimization rules
        self._rules.append({
            "category": OptimizationCategory.PERFORMANCE,
            "condition": lambda m: m.get("latency_p95", 0) > 500,
            "generator": self._generate_latency_optimization,
        })

        # Error rate optimization rules
        self._rules.append({
            "category": OptimizationCategory.RELIABILITY,
            "condition": lambda m: m.get("error_rate", 0) > 1,
            "generator": self._generate_error_optimization,
        })

        # Cost optimization rules
        self._rules.append({
            "category": OptimizationCategory.COST,
            "condition": lambda m: m.get("resource_utilization", 100) < 30,
            "generator": self._generate_cost_optimization,
        })

    def _generate_cpu_optimization(self, metrics: Dict[str, Any]) -> OptimizationItem:
        """Generate CPU optimization recommendation"""
        return OptimizationItem(
            title="Optimize CPU Utilization",
            category=OptimizationCategory.PERFORMANCE,
            priority=Priority.HIGH,
            description="CPU utilization is high and may impact performance",
            current_state=f"CPU average at {metrics.get('cpu_avg', 0):.1f}%",
            recommended_state="CPU utilization below 70%",
            estimated_impact="20-30% performance improvement",
            effort="medium",
            cost="low",
            implementation_steps=[
                "Profile application to identify CPU hotspots",
                "Optimize algorithms in identified areas",
                "Consider implementing caching",
                "Enable horizontal scaling if needed",
            ],
            risks=["May require code changes", "Testing required"],
            metrics_affected=["cpu_usage", "response_time", "throughput"],
        )

    def _generate_memory_optimization(self, metrics: Dict[str, Any]) -> OptimizationItem:
        """Generate memory optimization recommendation"""
        return OptimizationItem(
            title="Optimize Memory Usage",
            category=OptimizationCategory.PERFORMANCE,
            priority=Priority.HIGH,
            description="Memory utilization is high and may cause performance issues",
            current_state=f"Memory average at {metrics.get('memory_avg', 0):.1f}%",
            recommended_state="Memory utilization below 75%",
            estimated_impact="Reduced garbage collection, better stability",
            effort="medium",
            cost="low",
            implementation_steps=[
                "Analyze memory usage patterns",
                "Identify and fix memory leaks",
                "Optimize data structures",
                "Implement object pooling where appropriate",
            ],
            risks=["May require significant refactoring"],
            metrics_affected=["memory_usage", "gc_pause_time", "response_time"],
        )

    def _generate_latency_optimization(self, metrics: Dict[str, Any]) -> OptimizationItem:
        """Generate latency optimization recommendation"""
        return OptimizationItem(
            title="Reduce Response Latency",
            category=OptimizationCategory.PERFORMANCE,
            priority=Priority.HIGH,
            description="Response latency is above acceptable threshold",
            current_state=f"P95 latency at {metrics.get('latency_p95', 0):.0f}ms",
            recommended_state="P95 latency below 200ms",
            estimated_impact="Improved user experience, better conversion",
            effort="medium",
            cost="low",
            implementation_steps=[
                "Identify slow operations through tracing",
                "Add caching for frequently accessed data",
                "Optimize database queries",
                "Consider async processing for long operations",
            ],
            risks=["May require architectural changes"],
            metrics_affected=["latency_p50", "latency_p95", "latency_p99"],
        )

    def _generate_error_optimization(self, metrics: Dict[str, Any]) -> OptimizationItem:
        """Generate error rate optimization recommendation"""
        return OptimizationItem(
            title="Reduce Error Rate",
            category=OptimizationCategory.RELIABILITY,
            priority=Priority.CRITICAL,
            description="Error rate is above acceptable threshold",
            current_state=f"Error rate at {metrics.get('error_rate', 0):.2f}%",
            recommended_state="Error rate below 0.1%",
            estimated_impact="Improved reliability and user experience",
            effort="high",
            cost="low",
            implementation_steps=[
                "Analyze error logs and patterns",
                "Fix root causes of common errors",
                "Implement circuit breakers",
                "Add retry logic with exponential backoff",
            ],
            risks=["May require significant debugging"],
            metrics_affected=["error_rate", "availability", "user_satisfaction"],
        )

    def _generate_cost_optimization(self, metrics: Dict[str, Any]) -> OptimizationItem:
        """Generate cost optimization recommendation"""
        return OptimizationItem(
            title="Optimize Resource Costs",
            category=OptimizationCategory.COST,
            priority=Priority.MEDIUM,
            description="Resources are under-utilized, potential cost savings",
            current_state=f"Resource utilization at {metrics.get('resource_utilization', 0):.1f}%",
            recommended_state="Resource utilization above 50%",
            estimated_impact="Potential 30-50% cost reduction",
            effort="low",
            cost="free",
            implementation_steps=[
                "Review current resource allocation",
                "Implement autoscaling",
                "Right-size instances based on usage",
                "Consider reserved instances for stable workloads",
            ],
            risks=["May impact performance during traffic spikes"],
            metrics_affected=["cost", "resource_utilization"],
        )

    def analyze(self, metrics: Dict[str, Any]) -> List[OptimizationItem]:
        """Analyze metrics and generate recommendations"""
        recommendations = []

        for rule in self._rules:
            try:
                if rule["condition"](metrics):
                    optimization = rule["generator"](metrics)
                    recommendations.append(optimization)
            except Exception as e:
                logger.error(f"Rule evaluation failed: {e}")

        # Sort by priority
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
        }
        recommendations.sort(key=lambda o: priority_order.get(o.priority, 3))

        self.optimizations = recommendations
        return recommendations

    def add_custom_rule(
        self,
        category: OptimizationCategory,
        condition: callable,
        generator: callable,
    ) -> None:
        """Add a custom optimization rule"""
        self._rules.append({
            "category": category,
            "condition": condition,
            "generator": generator,
        })


class OptimizationReporter:
    """
    Main optimization reporting engine.
    """

    def __init__(self):
        self.engine = OptimizationEngine()
        self.reports: Dict[str, OptimizationReport] = {}

    def generate_report(
        self,
        report_type: ReportType,
        metrics: Dict[str, Any],
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> OptimizationReport:
        """Generate an optimization report"""
        import uuid
        report_id = str(uuid.uuid4())[:8]

        # Generate optimizations
        optimizations = self.engine.analyze(metrics)

        # Create summary
        summary = self._create_summary(optimizations, metrics)

        report = OptimizationReport(
            report_id=report_id,
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            optimizations=optimizations,
            summary=summary,
            metrics=metrics,
        )

        self.reports[report_id] = report
        return report

    def _create_summary(
        self,
        optimizations: List[OptimizationItem],
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create report summary"""
        summary = {
            "total_optimizations": len(optimizations),
            "by_priority": {},
            "by_category": {},
            "quick_wins": [],
            "high_impact": [],
        }

        # Count by priority
        for priority in Priority:
            count = sum(1 for o in optimizations if o.priority == priority)
            summary["by_priority"][priority.value] = count

        # Count by category
        for category in OptimizationCategory:
            count = sum(1 for o in optimizations if o.category == category)
            summary["by_category"][category.value] = count

        # Quick wins (low effort + low/medium cost)
        summary["quick_wins"] = [
            o.title for o in optimizations
            if o.effort == "low" and o.cost in ["free", "low"]
        ]

        # High impact (critical or high priority)
        summary["high_impact"] = [
            o.title for o in optimizations
            if o.priority in [Priority.CRITICAL, Priority.HIGH]
        ]

        return summary

    def get_report(self, report_id: str) -> Optional[OptimizationReport]:
        """Get a report by ID"""
        return self.reports.get(report_id)

    def get_all_reports(self) -> List[OptimizationReport]:
        """Get all reports"""
        return list(self.reports.values())

    def export_report(
        self,
        report_id: str,
        format: str = "json",
    ) -> Optional[str]:
        """Export report to specified format"""
        report = self.get_report(report_id)
        if not report:
            return None

        if format == "json":
            return json.dumps(report.to_dict(), indent=2)

        return str(report.to_dict())

    def compare_reports(
        self,
        report_id1: str,
        report_id2: str,
    ) -> Dict[str, Any]:
        """Compare two reports"""
        report1 = self.get_report(report_id1)
        report2 = self.get_report(report_id2)

        if not report1 or not report2:
            return {"error": "One or both reports not found"}

        # Compare optimization counts
        count_diff = len(report2.optimizations) - len(report1.optimizations)

        # Compare categories
        categories1 = set(o.category.value for o in report1.optimizations)
        categories2 = set(o.category.value for o in report2.optimizations)

        # Compare priorities
        critical1 = sum(1 for o in report1.optimizations if o.priority == Priority.CRITICAL)
        critical2 = sum(1 for o in report2.optimizations if o.priority == Priority.CRITICAL)

        return {
            "report1_date": report1.generated_at.isoformat(),
            "report2_date": report2.generated_at.isoformat(),
            "optimization_count_change": count_diff,
            "categories_added": list(categories2 - categories1),
            "categories_removed": list(categories1 - categories2),
            "critical_count_change": critical2 - critical1,
            "improvement": critical2 < critical1,
        }

    def get_trending_optimizations(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get trending optimizations over time"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        recent_reports = [
            r for r in self.reports.values()
            if r.generated_at >= cutoff
        ]

        if not recent_reports:
            return {"trending": [], "message": "No reports in the specified period"}

        # Count optimization occurrences
        optimization_counts: Dict[str, int] = {}
        for report in recent_reports:
            for opt in report.optimizations:
                key = opt.title
                optimization_counts[key] = optimization_counts.get(key, 0) + 1

        # Sort by frequency
        trending = sorted(
            optimization_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return {
            "period_days": days,
            "report_count": len(recent_reports),
            "trending": [
                {"title": t[0], "occurrences": t[1]}
                for t in trending
            ],
        }
