"""
Report Templates
Enterprise Analytics & Reporting - Week 44 Builder 3
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TemplateCategory(str, Enum):
    """Template categories"""
    EXECUTIVE = "executive"
    OPERATIONAL = "operational"
    ANALYTICAL = "analytical"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


@dataclass
class TemplateVariable:
    """A variable in a template"""
    name: str
    display_name: str
    variable_type: str  # string, number, date, select
    default_value: Optional[Any] = None
    required: bool = False
    options: List[str] = field(default_factory=list)  # For select type
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "variable_type": self.variable_type,
            "default_value": self.default_value,
            "required": self.required,
            "options": self.options
        }


@dataclass
class ReportTemplate:
    """A report template"""
    id: str
    name: str
    description: str
    category: TemplateCategory
    sections: List[Dict[str, Any]]
    variables: List[TemplateVariable] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "sections": self.sections,
            "variables": [v.to_dict() for v in self.variables],
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class TemplateLibrary:
    """Library of report templates"""
    
    def __init__(self):
        self._templates: Dict[str, ReportTemplate] = {}
        self._register_default_templates()
    
    def _register_default_templates(self) -> None:
        """Register all default templates"""
        templates = [
            # Executive Templates
            ReportTemplate(
                id="tpl_exec_summary",
                name="Executive Summary Report",
                description="High-level overview for leadership",
                category=TemplateCategory.EXECUTIVE,
                sections=[
                    {"title": "Performance Overview", "type": "kpi_grid"},
                    {"title": "Trend Analysis", "type": "line_chart"},
                    {"title": "Key Insights", "type": "bullet_list"}
                ],
                variables=[
                    TemplateVariable("date_range", "Date Range", "select", 
                                   options=["last_7_days", "last_30_days", "last_quarter"]),
                    TemplateVariable("department", "Department", "string")
                ],
                tags=["executive", "summary", "leadership"]
            ),
            ReportTemplate(
                id="tpl_exec_scorecard",
                name="Executive Scorecard",
                description="KPI scorecard for executives",
                category=TemplateCategory.EXECUTIVE,
                sections=[
                    {"title": "Scorecard Summary", "type": "scorecard"},
                    {"title": "Target vs Actual", "type": "comparison_chart"}
                ],
                variables=[
                    TemplateVariable("period", "Period", "select",
                                   options=["monthly", "quarterly", "yearly"])
                ],
                tags=["executive", "scorecard", "kpi"]
            ),
            
            # Operational Templates
            ReportTemplate(
                id="tpl_ops_daily",
                name="Daily Operations Report",
                description="Daily operational metrics",
                category=TemplateCategory.OPERATIONAL,
                sections=[
                    {"title": "Daily Summary", "type": "kpi_cards"},
                    {"title": "Ticket Volume", "type": "bar_chart"},
                    {"title": "Team Performance", "type": "table"},
                    {"title": "Pending Items", "type": "list"}
                ],
                variables=[
                    TemplateVariable("date", "Date", "date", required=True)
                ],
                tags=["operational", "daily", "metrics"]
            ),
            ReportTemplate(
                id="tpl_ops_weekly",
                name="Weekly Operations Report",
                description="Weekly operational summary",
                category=TemplateCategory.OPERATIONAL,
                sections=[
                    {"title": "Week Overview", "type": "summary"},
                    {"title": "Volume Trends", "type": "line_chart"},
                    {"title": "Response Times", "type": "bar_chart"},
                    {"title": "Team Breakdown", "type": "table"}
                ],
                variables=[
                    TemplateVariable("week_start", "Week Start", "date"),
                    TemplateVariable("team_filter", "Team", "string")
                ],
                tags=["operational", "weekly", "summary"]
            ),
            
            # Analytical Templates
            ReportTemplate(
                id="tpl_analytics_performance",
                name="Performance Analysis Report",
                description="Detailed performance analytics",
                category=TemplateCategory.ANALYTICAL,
                sections=[
                    {"title": "Performance Metrics", "type": "detailed_table"},
                    {"title": "Trend Analysis", "type": "multi_line_chart"},
                    {"title": "Correlation Analysis", "type": "scatter_plot"},
                    {"title": "Anomalies", "type": "highlight_table"}
                ],
                variables=[
                    TemplateVariable("metric", "Metric", "select",
                                   options=["response_time", "resolution_rate", "satisfaction"]),
                    TemplateVariable("granularity", "Granularity", "select",
                                   options=["hourly", "daily", "weekly"])
                ],
                tags=["analytics", "performance", "trends"]
            ),
            ReportTemplate(
                id="tpl_analytics_comparison",
                name="Comparative Analysis",
                description="Compare metrics across dimensions",
                category=TemplateCategory.ANALYTICAL,
                sections=[
                    {"title": "Comparison Overview", "type": "comparison_grid"},
                    {"title": "Side by Side", "type": "dual_chart"},
                    {"title": "Differences", "type": "variance_table"}
                ],
                variables=[
                    TemplateVariable("dimension", "Dimension", "select",
                                   options=["team", "channel", "category"]),
                    TemplateVariable("period_1", "Period 1", "date"),
                    TemplateVariable("period_2", "Period 2", "date")
                ],
                tags=["analytics", "comparison", "benchmarking"]
            ),
            
            # Compliance Templates
            ReportTemplate(
                id="tpl_compliance_sl",
                name="SLA Compliance Report",
                description="SLA compliance metrics",
                category=TemplateCategory.COMPLIANCE,
                sections=[
                    {"title": "SLA Summary", "type": "gauge_grid"},
                    {"title": "Compliance Details", "type": "detailed_table"},
                    {"title": "Breaches", "type": "incident_table"}
                ],
                variables=[
                    TemplateVariable("sla_type", "SLA Type", "select",
                                   options=["response", "resolution", "all"]),
                    TemplateVariable("period", "Period", "select",
                                   options=["daily", "weekly", "monthly"])
                ],
                tags=["compliance", "sla", "metrics"]
            ),
            ReportTemplate(
                id="tpl_compliance_audit",
                name="Audit Report",
                description="Compliance audit documentation",
                category=TemplateCategory.COMPLIANCE,
                sections=[
                    {"title": "Audit Summary", "type": "summary"},
                    {"title": "Compliance Checklist", "type": "checklist"},
                    {"title": "Findings", "type": "findings_list"},
                    {"title": "Recommendations", "type": "recommendations"}
                ],
                variables=[
                    TemplateVariable("audit_date", "Audit Date", "date"),
                    TemplateVariable("auditor", "Auditor", "string")
                ],
                tags=["compliance", "audit", "documentation"]
            ),
            
            # Custom Templates
            ReportTemplate(
                id="tpl_custom_blank",
                name="Blank Report",
                description="Start from scratch",
                category=TemplateCategory.CUSTOM,
                sections=[],
                variables=[],
                tags=["custom", "blank"]
            )
        ]
        
        for template in templates:
            self._templates[template.id] = template
    
    def get_template(self, template_id: str) -> Optional[ReportTemplate]:
        """Get a template by ID"""
        return self._templates.get(template_id)
    
    def list_templates(
        self,
        category: Optional[TemplateCategory] = None,
        tags: Optional[List[str]] = None
    ) -> List[ReportTemplate]:
        """List templates with optional filtering"""
        templates = list(self._templates.values())
        
        if category:
            templates = [t for t in templates if t.category == category]
        
        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]
        
        return templates
    
    def register_template(self, template: ReportTemplate) -> None:
        """Register a new template"""
        self._templates[template.id] = template
        logger.info(f"Registered template: {template.name}")
    
    def duplicate_template(
        self,
        template_id: str,
        new_name: str
    ) -> Optional[ReportTemplate]:
        """Create a copy of a template"""
        original = self._templates.get(template_id)
        if not original:
            return None
        
        import uuid
        new_template = ReportTemplate(
            id=f"tpl_{uuid.uuid4().hex[:8]}",
            name=new_name,
            description=original.description,
            category=original.category,
            sections=[s.copy() for s in original.sections],
            variables=[TemplateVariable(**{k: v for k, v in var.__dict__.items()}) 
                      for var in original.variables],
            tags=original.tags.copy()
        )
        
        self._templates[new_template.id] = new_template
        return new_template
    
    def delete_template(self, template_id: str) -> bool:
        """Delete a template"""
        if template_id in self._templates:
            del self._templates[template_id]
            return True
        return False
    
    def get_templates_by_tag(self, tag: str) -> List[ReportTemplate]:
        """Get templates by tag"""
        return [t for t in self._templates.values() if tag in t.tags]
    
    def search_templates(self, query: str) -> List[ReportTemplate]:
        """Search templates by name or description"""
        query_lower = query.lower()
        return [
            t for t in self._templates.values()
            if query_lower in t.name.lower() or query_lower in t.description.lower()
        ]
