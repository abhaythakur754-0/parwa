"""
Report Builder
Enterprise Analytics & Reporting - Week 44 Builder 3
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Type
import json
import uuid
import logging

logger = logging.getLogger(__name__)


class ReportStatus(str, Enum):
    """Report status"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportFormat(str, Enum):
    """Export format"""
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"
    HTML = "html"


class ReportType(str, Enum):
    """Report types"""
    SUMMARY = "summary"
    DETAILED = "detailed"
    TREND = "trend"
    COMPARISON = "comparison"
    EXECUTIVE = "executive"


@dataclass
class ReportSection:
    """A section in a report"""
    id: str
    title: str
    type: str  # text, chart, table, kpi_summary
    data_source: Optional[str] = None
    query: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    order: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "data_source": self.data_source,
            "query": self.query,
            "config": self.config,
            "order": self.order
        }


@dataclass
class ReportDefinition:
    """Definition of a report"""
    id: str
    name: str
    description: str
    report_type: ReportType
    sections: List[ReportSection] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    schedule: Optional[str] = None  # Cron expression
    owner_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_run: Optional[datetime] = None
    run_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "report_type": self.report_type.value,
            "sections": [s.to_dict() for s in self.sections],
            "filters": self.filters,
            "parameters": self.parameters,
            "schedule": self.schedule,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "run_count": self.run_count
        }
    
    def add_section(self, section: ReportSection) -> None:
        """Add a section to the report"""
        section.order = len(self.sections)
        self.sections.append(section)
        self.updated_at = datetime.utcnow()


@dataclass
class GeneratedReport:
    """A generated report instance"""
    id: str
    report_definition_id: str
    name: str
    status: ReportStatus
    format: ReportFormat
    parameters: Dict[str, Any] = field(default_factory=dict)
    sections_data: Dict[str, Any] = field(default_factory=dict)
    file_path: Optional[str] = None
    generated_at: Optional[datetime] = None
    generated_by: Optional[str] = None
    size_bytes: int = 0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "report_definition_id": self.report_definition_id,
            "name": self.name,
            "status": self.status.value,
            "format": self.format.value,
            "parameters": self.parameters,
            "file_path": self.file_path,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "generated_by": self.generated_by,
            "size_bytes": self.size_bytes,
            "error": self.error
        }


class ReportBuilder:
    """Builds and manages reports"""
    
    def __init__(self):
        self._definitions: Dict[str, ReportDefinition] = {}
        self._generated: Dict[str, GeneratedReport] = []
        self._templates: Dict[str, ReportDefinition] = {}
        self._data_sources: Dict[str, Any] = {}
        self._register_default_templates()
    
    def _register_default_templates(self) -> None:
        """Register default report templates"""
        # Executive Summary Template
        executive_template = ReportDefinition(
            id="template_executive_summary",
            name="Executive Summary",
            description="High-level overview for executives",
            report_type=ReportType.EXECUTIVE,
            sections=[
                ReportSection("s1", "Key Metrics", "kpi_summary", order=0),
                ReportSection("s2", "Trend Overview", "chart", order=1),
                ReportSection("s3", "Top Issues", "table", order=2)
            ]
        )
        self._templates[executive_template.id] = executive_template
        
        # Detailed Analysis Template
        detailed_template = ReportDefinition(
            id="template_detailed_analysis",
            name="Detailed Analysis",
            description="Comprehensive data analysis",
            report_type=ReportType.DETAILED,
            sections=[
                ReportSection("s1", "Summary Statistics", "kpi_summary", order=0),
                ReportSection("s2", "Data Breakdown", "table", order=1),
                ReportSection("s3", "Trends", "chart", order=2),
                ReportSection("s4", "Comparisons", "chart", order=3)
            ]
        )
        self._templates[detailed_template.id] = detailed_template
    
    def create_report(
        self,
        name: str,
        description: str,
        report_type: ReportType,
        owner_id: Optional[str] = None
    ) -> ReportDefinition:
        """Create a new report definition"""
        report_id = str(uuid.uuid4())
        
        report = ReportDefinition(
            id=report_id,
            name=name,
            description=description,
            report_type=report_type,
            owner_id=owner_id
        )
        
        self._definitions[report_id] = report
        logger.info(f"Created report: {name}")
        
        return report
    
    def get_report(self, report_id: str) -> Optional[ReportDefinition]:
        """Get a report definition by ID"""
        return self._definitions.get(report_id)
    
    def list_reports(
        self,
        owner_id: Optional[str] = None,
        report_type: Optional[ReportType] = None
    ) -> List[ReportDefinition]:
        """List report definitions"""
        reports = list(self._definitions.values())
        
        if owner_id:
            reports = [r for r in reports if r.owner_id == owner_id]
        
        if report_type:
            reports = [r for r in reports if r.report_type == report_type]
        
        return reports
    
    def update_report(
        self,
        report_id: str,
        **kwargs
    ) -> Optional[ReportDefinition]:
        """Update a report definition"""
        report = self._definitions.get(report_id)
        if not report:
            return None
        
        for key, value in kwargs.items():
            if hasattr(report, key) and key not in ["id", "created_at"]:
                setattr(report, key, value)
        
        report.updated_at = datetime.utcnow()
        return report
    
    def delete_report(self, report_id: str) -> bool:
        """Delete a report definition"""
        if report_id in self._definitions:
            del self._definitions[report_id]
            return True
        return False
    
    def create_from_template(
        self,
        template_id: str,
        name: str,
        owner_id: Optional[str] = None
    ) -> Optional[ReportDefinition]:
        """Create report from template"""
        template = self._templates.get(template_id)
        if not template:
            return None
        
        report = self.create_report(
            name=name,
            description=template.description,
            report_type=template.report_type,
            owner_id=owner_id
        )
        
        # Copy sections
        for section in template.sections:
            new_section = ReportSection(
                id=str(uuid.uuid4()),
                title=section.title,
                type=section.type,
                data_source=section.data_source,
                query=section.query,
                config=section.config.copy(),
                order=section.order
            )
            report.sections.append(new_section)
        
        return report
    
    def list_templates(self) -> List[ReportDefinition]:
        """List available templates"""
        return list(self._templates.values())
    
    def register_data_source(
        self,
        name: str,
        source: Any
    ) -> None:
        """Register a data source"""
        self._data_sources[name] = source
    
    async def generate_report(
        self,
        report_id: str,
        format: ReportFormat = ReportFormat.PDF,
        parameters: Optional[Dict[str, Any]] = None,
        generated_by: Optional[str] = None
    ) -> GeneratedReport:
        """Generate a report"""
        report = self._definitions.get(report_id)
        if not report:
            return GeneratedReport(
                id=str(uuid.uuid4()),
                report_definition_id=report_id,
                name="Unknown",
                status=ReportStatus.FAILED,
                format=format,
                error="Report definition not found"
            )
        
        generated = GeneratedReport(
            id=str(uuid.uuid4()),
            report_definition_id=report_id,
            name=report.name,
            status=ReportStatus.GENERATING,
            format=format,
            parameters=parameters or {},
            generated_by=generated_by
        )
        
        try:
            # Generate section data
            for section in report.sections:
                section_data = await self._generate_section(section, parameters)
                generated.sections_data[section.id] = section_data
            
            # Export to format
            generated.file_path = await self._export_report(generated, report)
            generated.status = ReportStatus.COMPLETED
            generated.generated_at = datetime.utcnow()
            
            # Update report stats
            report.last_run = datetime.utcnow()
            report.run_count += 1
            
        except Exception as e:
            generated.status = ReportStatus.FAILED
            generated.error = str(e)
            logger.error(f"Report generation failed: {e}")
        
        self._generated.append(generated)
        return generated
    
    async def _generate_section(
        self,
        section: ReportSection,
        parameters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate data for a report section"""
        # Mock data generation - in real impl would query data sources
        if section.type == "kpi_summary":
            return {
                "kpis": [
                    {"name": "Total Tickets", "value": 1234, "change": 5.2},
                    {"name": "Avg Response Time", "value": "15m", "change": -2.1},
                    {"name": "Resolution Rate", "value": "95%", "change": 1.5}
                ]
            }
        elif section.type == "chart":
            return {
                "chart_type": "line",
                "data": {
                    "labels": ["Mon", "Tue", "Wed", "Thu", "Fri"],
                    "datasets": [{"label": "Tickets", "data": [120, 150, 180, 160, 140]}]
                }
            }
        elif section.type == "table":
            return {
                "columns": [
                    {"field": "id", "header": "ID"},
                    {"field": "subject", "header": "Subject"},
                    {"field": "status", "header": "Status"}
                ],
                "rows": [
                    {"id": "T001", "subject": "Issue 1", "status": "Open"},
                    {"id": "T002", "subject": "Issue 2", "status": "Resolved"}
                ]
            }
        elif section.type == "text":
            return {"content": section.config.get("content", "")}
        
        return {}
    
    async def _export_report(
        self,
        generated: GeneratedReport,
        definition: ReportDefinition
    ) -> str:
        """Export report to file"""
        # In real implementation, would generate actual files
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{definition.name.replace(' ', '_')}_{timestamp}.{generated.format.value}"
        return f"/reports/{filename}"
    
    def get_generated_report(self, generated_id: str) -> Optional[GeneratedReport]:
        """Get a generated report by ID"""
        for report in self._generated:
            if report.id == generated_id:
                return report
        return None
    
    def list_generated_reports(
        self,
        report_definition_id: Optional[str] = None,
        status: Optional[ReportStatus] = None,
        limit: int = 50
    ) -> List[GeneratedReport]:
        """List generated reports"""
        reports = self._generated
        
        if report_definition_id:
            reports = [r for r in reports if r.report_definition_id == report_definition_id]
        
        if status:
            reports = [r for r in reports if r.status == status]
        
        return reports[-limit:]
    
    def schedule_report(
        self,
        report_id: str,
        schedule: str
    ) -> Optional[ReportDefinition]:
        """Schedule a report for automatic generation"""
        return self.update_report(report_id, schedule=schedule)
    
    def unschedule_report(self, report_id: str) -> Optional[ReportDefinition]:
        """Remove schedule from a report"""
        return self.update_report(report_id, schedule=None)
    
    def get_scheduled_reports(self) -> List[ReportDefinition]:
        """Get all scheduled reports"""
        return [r for r in self._definitions.values() if r.schedule]
