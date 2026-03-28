"""
Comparison Report Module

Generates comparison reports between tenants (anonymized).
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class ReportType(str, Enum):
    """Types of comparison reports"""
    PERFORMANCE = "performance"
    USAGE = "usage"
    COST = "cost"
    EFFICIENCY = "efficiency"
    COMPREHENSIVE = "comprehensive"


@dataclass
class ReportSection:
    """A section of a report"""
    title: str
    metrics: Dict[str, Any]
    insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ComparisonReport:
    """A complete comparison report"""
    report_id: str
    tenant_id: str
    report_type: ReportType
    generated_at: datetime = field(default_factory=datetime.utcnow)
    sections: List[ReportSection] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ComparisonReportGenerator:
    """
    Generates comparison reports for tenants.

    Features:
    - Multiple report types
    - Anonymized peer comparisons
    - Actionable insights
    - Trend analysis
    """

    def __init__(self):
        self._reports: List[ComparisonReport] = []
        self._report_counter = 0

    def generate_report(
        self,
        tenant_id: str,
        report_type: ReportType,
        tenant_data: Dict[str, Any],
        peer_aggregates: Dict[str, Any]
    ) -> ComparisonReport:
        """Generate a comparison report"""
        self._report_counter += 1
        report_id = f"report_{datetime.utcnow().strftime('%Y%m%d')}_{self._report_counter}"

        report = ComparisonReport(
            report_id=report_id,
            tenant_id=tenant_id,
            report_type=report_type
        )

        if report_type == ReportType.PERFORMANCE:
            report.sections = self._generate_performance_sections(tenant_data, peer_aggregates)
        elif report_type == ReportType.USAGE:
            report.sections = self._generate_usage_sections(tenant_data, peer_aggregates)
        elif report_type == ReportType.COST:
            report.sections = self._generate_cost_sections(tenant_data, peer_aggregates)
        elif report_type == ReportType.EFFICIENCY:
            report.sections = self._generate_efficiency_sections(tenant_data, peer_aggregates)
        else:
            report.sections = self._generate_comprehensive_sections(tenant_data, peer_aggregates)

        # Generate summary
        report.summary = self._generate_summary(report.sections)

        self._reports.append(report)
        return report

    def _generate_performance_sections(
        self,
        tenant_data: Dict[str, Any],
        peer_data: Dict[str, Any]
    ) -> List[ReportSection]:
        """Generate performance report sections"""
        sections = []

        # Response Time Section
        tenant_rt = tenant_data.get("avg_response_time", 0)
        peer_rt = peer_data.get("avg_response_time", 0)

        rt_section = ReportSection(
            title="Response Time",
            metrics={
                "tenant_value": tenant_rt,
                "peer_average": peer_rt,
                "difference_percent": self._calc_percent_diff(tenant_rt, peer_rt)
            }
        )

        if tenant_rt < peer_rt:
            rt_section.insights.append("Your response time is better than peer average")
        else:
            rt_section.recommendations.append("Consider optimizing response times")

        sections.append(rt_section)

        # Throughput Section
        tenant_tp = tenant_data.get("throughput", 0)
        peer_tp = peer_data.get("throughput", 0)

        tp_section = ReportSection(
            title="Throughput",
            metrics={
                "tenant_value": tenant_tp,
                "peer_average": peer_tp,
                "difference_percent": self._calc_percent_diff(tenant_tp, peer_tp)
            }
        )

        sections.append(tp_section)

        # Error Rate Section
        tenant_err = tenant_data.get("error_rate", 0)
        peer_err = peer_data.get("error_rate", 0)

        err_section = ReportSection(
            title="Error Rate",
            metrics={
                "tenant_value": f"{tenant_err}%",
                "peer_average": f"{peer_err}%",
                "difference_percent": self._calc_percent_diff(tenant_err, peer_err)
            }
        )

        if tenant_err > peer_err:
            err_section.recommendations.append("Error rate is above peer average - investigate causes")

        sections.append(err_section)

        return sections

    def _generate_usage_sections(
        self,
        tenant_data: Dict[str, Any],
        peer_data: Dict[str, Any]
    ) -> List[ReportSection]:
        """Generate usage report sections"""
        sections = []

        # API Usage
        tenant_api = tenant_data.get("api_calls", 0)
        peer_api = peer_data.get("api_calls", 0)

        sections.append(ReportSection(
            title="API Usage",
            metrics={
                "tenant_value": tenant_api,
                "peer_average": peer_api,
                "difference_percent": self._calc_percent_diff(tenant_api, peer_api)
            }
        ))

        # Feature Adoption
        tenant_features = tenant_data.get("features_used", 0)
        peer_features = peer_data.get("features_used", 0)

        feature_section = ReportSection(
            title="Feature Adoption",
            metrics={
                "tenant_value": tenant_features,
                "peer_average": peer_features,
                "difference_percent": self._calc_percent_diff(tenant_features, peer_features)
            }
        )

        if tenant_features < peer_features:
            feature_section.recommendations.append("Explore more available features")

        sections.append(feature_section)

        return sections

    def _generate_cost_sections(
        self,
        tenant_data: Dict[str, Any],
        peer_data: Dict[str, Any]
    ) -> List[ReportSection]:
        """Generate cost report sections"""
        sections = []

        # Cost Efficiency
        tenant_cost = tenant_data.get("monthly_cost", 0)
        peer_cost = peer_data.get("monthly_cost", 0)

        cost_section = ReportSection(
            title="Monthly Cost",
            metrics={
                "tenant_value": f"${tenant_cost}",
                "peer_average": f"${peer_cost}",
                "difference_percent": self._calc_percent_diff(tenant_cost, peer_cost)
            }
        )

        sections.append(cost_section)

        # Cost per User
        tenant_users = tenant_data.get("users", 1)
        tenant_cpu = tenant_cost / tenant_users if tenant_users else 0
        peer_users = peer_data.get("users", 1)
        peer_cpu = peer_cost / peer_users if peer_users else 0

        sections.append(ReportSection(
            title="Cost per User",
            metrics={
                "tenant_value": f"${tenant_cpu:.2f}",
                "peer_average": f"${peer_cpu:.2f}",
                "difference_percent": self._calc_percent_diff(tenant_cpu, peer_cpu)
            }
        ))

        return sections

    def _generate_efficiency_sections(
        self,
        tenant_data: Dict[str, Any],
        peer_data: Dict[str, Any]
    ) -> List[ReportSection]:
        """Generate efficiency report sections"""
        sections = []

        # Resource Utilization
        tenant_util = tenant_data.get("resource_utilization", 0)
        peer_util = peer_data.get("resource_utilization", 0)

        util_section = ReportSection(
            title="Resource Utilization",
            metrics={
                "tenant_value": f"{tenant_util}%",
                "peer_average": f"{peer_util}%",
                "difference_percent": self._calc_percent_diff(tenant_util, peer_util)
            }
        )

        if tenant_util < 50:
            util_section.recommendations.append("Resource utilization is low - consider downsizing")

        sections.append(util_section)

        # Automation Rate
        tenant_auto = tenant_data.get("automation_rate", 0)
        peer_auto = peer_data.get("automation_rate", 0)

        sections.append(ReportSection(
            title="Automation Rate",
            metrics={
                "tenant_value": f"{tenant_auto}%",
                "peer_average": f"{peer_auto}%",
                "difference_percent": self._calc_percent_diff(tenant_auto, peer_auto)
            }
        ))

        return sections

    def _generate_comprehensive_sections(
        self,
        tenant_data: Dict[str, Any],
        peer_data: Dict[str, Any]
    ) -> List[ReportSection]:
        """Generate comprehensive report sections"""
        sections = []
        sections.extend(self._generate_performance_sections(tenant_data, peer_data))
        sections.extend(self._generate_usage_sections(tenant_data, peer_data))
        sections.extend(self._generate_efficiency_sections(tenant_data, peer_data))
        return sections

    def _generate_summary(self, sections: List[ReportSection]) -> Dict[str, Any]:
        """Generate report summary"""
        total_recommendations = sum(len(s.recommendations) for s in sections)
        total_insights = sum(len(s.insights) for s in sections)

        return {
            "total_sections": len(sections),
            "total_insights": total_insights,
            "total_recommendations": total_recommendations,
            "health_score": max(0, 100 - total_recommendations * 10)
        }

    def _calc_percent_diff(self, value1: float, value2: float) -> float:
        """Calculate percentage difference"""
        if value2 == 0:
            return 0
        return round(((value1 - value2) / value2) * 100, 1)

    def get_report(self, report_id: str) -> Optional[ComparisonReport]:
        """Get a report by ID"""
        for report in self._reports:
            if report.report_id == report_id:
                return report
        return None

    def get_tenant_reports(
        self,
        tenant_id: str,
        limit: int = 10
    ) -> List[ComparisonReport]:
        """Get reports for a tenant"""
        reports = [r for r in self._reports if r.tenant_id == tenant_id]
        return sorted(reports, key=lambda x: x.generated_at, reverse=True)[:limit]

    def export_report(
        self,
        report_id: str,
        format: str = "json"
    ) -> Optional[str]:
        """Export a report"""
        report = self.get_report(report_id)
        if not report:
            return None

        if format == "json":
            import json

            data = {
                "report_id": report.report_id,
                "tenant_id": report.tenant_id,
                "type": report.report_type.value,
                "generated_at": report.generated_at.isoformat(),
                "summary": report.summary,
                "sections": [
                    {
                        "title": s.title,
                        "metrics": s.metrics,
                        "insights": s.insights,
                        "recommendations": s.recommendations
                    }
                    for s in report.sections
                ]
            }

            return json.dumps(data, indent=2)

        return None
