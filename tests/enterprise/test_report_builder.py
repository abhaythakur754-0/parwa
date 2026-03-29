"""
Tests for Report Builder
Enterprise Analytics & Reporting - Week 44 Builder 3
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from enterprise.analytics.report_builder import (
    ReportBuilder,
    ReportDefinition,
    ReportSection,
    ReportStatus,
    ReportFormat,
    ReportType,
    GeneratedReport
)
from enterprise.analytics.report_templates import (
    TemplateLibrary,
    ReportTemplate,
    TemplateCategory,
    TemplateVariable
)
from enterprise.analytics.report_exporter import (
    DataExporter,
    ReportExporter,
    ExportResult,
    ExportFormat
)


# Test Fixtures
@pytest.fixture
def report_builder():
    """Create a test report builder"""
    return ReportBuilder()


@pytest.fixture
def template_library():
    """Create a test template library"""
    return TemplateLibrary()


@pytest.fixture
def data_exporter():
    """Create a test data exporter"""
    return DataExporter()


@pytest.fixture
def report_exporter():
    """Create a test report exporter"""
    return ReportExporter()


# ReportBuilder Tests
class TestReportBuilder:
    """Tests for ReportBuilder"""
    
    def test_builder_initialization(self, report_builder):
        """Test builder initializes correctly"""
        assert report_builder is not None
        assert len(report_builder._templates) > 0
    
    def test_create_report(self, report_builder):
        """Test creating a report"""
        report = report_builder.create_report(
            name="Test Report",
            description="Test description",
            report_type=ReportType.SUMMARY
        )
        
        assert report.id is not None
        assert report.name == "Test Report"
        assert report.report_type == ReportType.SUMMARY
    
    def test_get_report(self, report_builder):
        """Test getting a report"""
        created = report_builder.create_report(
            name="Test",
            description="Test",
            report_type=ReportType.DETAILED
        )
        
        retrieved = report_builder.get_report(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
    
    def test_list_reports(self, report_builder):
        """Test listing reports"""
        report_builder.create_report("R1", "Test", ReportType.SUMMARY)
        report_builder.create_report("R2", "Test", ReportType.DETAILED)
        
        reports = report_builder.list_reports()
        assert len(reports) == 2
    
    def test_update_report(self, report_builder):
        """Test updating a report"""
        report = report_builder.create_report("Test", "Test", ReportType.SUMMARY)
        
        updated = report_builder.update_report(report.id, name="Updated Name")
        
        assert updated.name == "Updated Name"
    
    def test_delete_report(self, report_builder):
        """Test deleting a report"""
        report = report_builder.create_report("Test", "Test", ReportType.SUMMARY)
        
        result = report_builder.delete_report(report.id)
        
        assert result is True
        assert report_builder.get_report(report.id) is None
    
    def test_add_section(self, report_builder):
        """Test adding a section to report"""
        report = report_builder.create_report("Test", "Test", ReportType.SUMMARY)
        section = ReportSection("s1", "Test Section", "kpi_summary")
        
        report.add_section(section)
        
        assert len(report.sections) == 1
    
    def test_create_from_template(self, report_builder):
        """Test creating report from template"""
        report = report_builder.create_from_template(
            "template_executive_summary",
            "My Executive Summary"
        )
        
        assert report is not None
        assert report.name == "My Executive Summary"
        assert len(report.sections) > 0
    
    def test_list_templates(self, report_builder):
        """Test listing templates"""
        templates = report_builder.list_templates()
        
        assert len(templates) > 0
    
    @pytest.mark.asyncio
    async def test_generate_report(self, report_builder):
        """Test generating a report"""
        report = report_builder.create_report("Test", "Test", ReportType.SUMMARY)
        report.add_section(ReportSection("s1", "Summary", "kpi_summary"))
        
        generated = await report_builder.generate_report(
            report.id,
            format=ReportFormat.PDF
        )
        
        assert generated is not None
        assert generated.status == ReportStatus.COMPLETED
    
    def test_schedule_report(self, report_builder):
        """Test scheduling a report"""
        report = report_builder.create_report("Test", "Test", ReportType.SUMMARY)
        
        scheduled = report_builder.schedule_report(report.id, "0 9 * * *")
        
        assert scheduled.schedule == "0 9 * * *"
    
    def test_get_scheduled_reports(self, report_builder):
        """Test getting scheduled reports"""
        report = report_builder.create_report("Test", "Test", ReportType.SUMMARY)
        report_builder.schedule_report(report.id, "0 9 * * *")
        
        scheduled = report_builder.get_scheduled_reports()
        
        assert len(scheduled) == 1


# ReportDefinition Tests
class TestReportDefinition:
    """Tests for ReportDefinition"""
    
    def test_report_creation(self):
        """Test report definition can be created"""
        report = ReportDefinition(
            id="test-id",
            name="Test Report",
            description="Test",
            report_type=ReportType.EXECUTIVE
        )
        
        assert report.id == "test-id"
        assert report.name == "Test Report"
    
    def test_report_to_dict(self):
        """Test report serialization"""
        report = ReportDefinition(
            id="test",
            name="Test",
            description="Test",
            report_type=ReportType.DETAILED
        )
        
        data = report.to_dict()
        
        assert data["id"] == "test"
        assert data["report_type"] == "detailed"


# ReportSection Tests
class TestReportSection:
    """Tests for ReportSection"""
    
    def test_section_creation(self):
        """Test section can be created"""
        section = ReportSection(
            id="s1",
            title="Test Section",
            type="kpi_summary"
        )
        
        assert section.id == "s1"
        assert section.title == "Test Section"
    
    def test_section_to_dict(self):
        """Test section serialization"""
        section = ReportSection(
            id="s1",
            title="Test",
            type="chart",
            config={"chart_type": "line"}
        )
        
        data = section.to_dict()
        
        assert data["id"] == "s1"
        assert data["type"] == "chart"


# GeneratedReport Tests
class TestGeneratedReport:
    """Tests for GeneratedReport"""
    
    def test_generated_report_creation(self):
        """Test generated report can be created"""
        report = GeneratedReport(
            id="gen-1",
            report_definition_id="def-1",
            name="Generated Report",
            status=ReportStatus.COMPLETED,
            format=ReportFormat.PDF
        )
        
        assert report.id == "gen-1"
        assert report.status == ReportStatus.COMPLETED
    
    def test_generated_report_to_dict(self):
        """Test generated report serialization"""
        report = GeneratedReport(
            id="gen-1",
            report_definition_id="def-1",
            name="Test",
            status=ReportStatus.COMPLETED,
            format=ReportFormat.CSV
        )
        
        data = report.to_dict()
        
        assert data["status"] == "completed"
        assert data["format"] == "csv"


# TemplateLibrary Tests
class TestTemplateLibrary:
    """Tests for TemplateLibrary"""
    
    def test_library_initialization(self, template_library):
        """Test library initializes with templates"""
        assert len(template_library._templates) > 0
    
    def test_get_template(self, template_library):
        """Test getting a template"""
        template = template_library.get_template("tpl_exec_summary")
        
        assert template is not None
        assert template.name == "Executive Summary Report"
    
    def test_list_templates(self, template_library):
        """Test listing templates"""
        templates = template_library.list_templates()
        
        assert len(templates) > 0
    
    def test_list_templates_by_category(self, template_library):
        """Test filtering templates by category"""
        templates = template_library.list_templates(category=TemplateCategory.EXECUTIVE)
        
        for t in templates:
            assert t.category == TemplateCategory.EXECUTIVE
    
    def test_list_templates_by_tags(self, template_library):
        """Test filtering templates by tags"""
        templates = template_library.list_templates(tags=["executive"])
        
        for t in templates:
            assert "executive" in t.tags
    
    def test_register_template(self, template_library):
        """Test registering a new template"""
        template = ReportTemplate(
            id="tpl_custom",
            name="Custom Template",
            description="Custom",
            category=TemplateCategory.CUSTOM,
            sections=[]
        )
        
        template_library.register_template(template)
        
        assert template_library.get_template("tpl_custom") is not None
    
    def test_duplicate_template(self, template_library):
        """Test duplicating a template"""
        duplicate = template_library.duplicate_template("tpl_exec_summary", "My Copy")
        
        assert duplicate is not None
        assert duplicate.name == "My Copy"
        assert duplicate.id != "tpl_exec_summary"
    
    def test_search_templates(self, template_library):
        """Test searching templates"""
        results = template_library.search_templates("executive")
        
        assert len(results) > 0
        for t in results:
            assert "executive" in t.name.lower() or "executive" in t.description.lower()


# ReportTemplate Tests
class TestReportTemplate:
    """Tests for ReportTemplate"""
    
    def test_template_creation(self):
        """Test template can be created"""
        template = ReportTemplate(
            id="test",
            name="Test Template",
            description="Test",
            category=TemplateCategory.OPERATIONAL,
            sections=[]
        )
        
        assert template.id == "test"
        assert template.category == TemplateCategory.OPERATIONAL
    
    def test_template_to_dict(self):
        """Test template serialization"""
        template = ReportTemplate(
            id="test",
            name="Test",
            description="Test",
            category=TemplateCategory.ANALYTICAL,
            sections=[],
            variables=[
                TemplateVariable("date", "Date", "date")
            ]
        )
        
        data = template.to_dict()
        
        assert data["id"] == "test"
        assert len(data["variables"]) == 1


# TemplateVariable Tests
class TestTemplateVariable:
    """Tests for TemplateVariable"""
    
    def test_variable_creation(self):
        """Test variable can be created"""
        var = TemplateVariable(
            name="date_range",
            display_name="Date Range",
            variable_type="select",
            options=["7d", "30d", "90d"]
        )
        
        assert var.name == "date_range"
        assert len(var.options) == 3
    
    def test_variable_to_dict(self):
        """Test variable serialization"""
        var = TemplateVariable(
            name="test",
            display_name="Test",
            variable_type="string",
            required=True
        )
        
        data = var.to_dict()
        
        assert data["name"] == "test"
        assert data["required"] is True


# DataExporter Tests
class TestDataExporter:
    """Tests for DataExporter"""
    
    @pytest.mark.asyncio
    async def test_export_csv(self, data_exporter):
        """Test exporting to CSV"""
        data = {
            "columns": [{"field": "name"}, {"field": "value"}],
            "rows": [{"name": "A", "value": 1}, {"name": "B", "value": 2}]
        }
        
        result = await data_exporter.export(data, ExportFormat.CSV)
        
        assert result.success is True
        assert result.format == ExportFormat.CSV
        assert result.content is not None
    
    @pytest.mark.asyncio
    async def test_export_json(self, data_exporter):
        """Test exporting to JSON"""
        data = {"metrics": {"total": 100, "resolved": 95}}
        
        result = await data_exporter.export(data, ExportFormat.JSON)
        
        assert result.success is True
        assert result.format == ExportFormat.JSON
    
    @pytest.mark.asyncio
    async def test_export_html(self, data_exporter):
        """Test exporting to HTML"""
        data = {
            "kpis": [
                {"name": "Total", "value": 100, "change": 5},
                {"name": "Resolved", "value": 95, "change": 3}
            ]
        }
        
        result = await data_exporter.export(data, ExportFormat.HTML)
        
        assert result.success is True
        assert result.format == ExportFormat.HTML
        assert b"<html>" in result.content
    
    @pytest.mark.asyncio
    async def test_export_kpi_csv(self, data_exporter):
        """Test exporting KPI list to CSV"""
        data = {
            "kpis": [
                {"name": "Response Time", "value": "15m", "change": -2.5},
                {"name": "Resolution Rate", "value": "95%", "change": 1.2}
            ]
        }
        
        result = await data_exporter.export(data, ExportFormat.CSV)
        
        assert result.success is True


# ReportExporter Tests
class TestReportExporter:
    """Tests for ReportExporter"""
    
    @pytest.mark.asyncio
    async def test_export_report(self, report_exporter):
        """Test exporting a complete report"""
        report_data = {
            "sections_data": {
                "s1": {"kpis": [{"name": "Total", "value": 100}]},
                "s2": {"columns": [{"field": "id"}], "rows": [{"id": 1}]}
            }
        }
        
        result = await report_exporter.export_report(
            report_data,
            ExportFormat.JSON,
            "Test Report"
        )
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_export_multiple_formats(self, report_exporter):
        """Test exporting in multiple formats"""
        data = {"metrics": {"total": 100}}
        
        results = await report_exporter.export_multiple_formats(
            data,
            [ExportFormat.JSON, ExportFormat.CSV]
        )
        
        assert ExportFormat.JSON in results
        assert ExportFormat.CSV in results
        assert results[ExportFormat.JSON].success is True
        assert results[ExportFormat.CSV].success is True


# Enum Tests
class TestEnums:
    """Tests for enum values"""
    
    def test_report_status(self):
        """Test ReportStatus enum"""
        assert ReportStatus.DRAFT.value == "draft"
        assert ReportStatus.COMPLETED.value == "completed"
    
    def test_report_format(self):
        """Test ReportFormat enum"""
        assert ExportFormat.CSV.value == "csv"
        assert ExportFormat.PDF.value == "pdf"
    
    def test_report_type(self):
        """Test ReportType enum"""
        assert ReportType.SUMMARY.value == "summary"
        assert ReportType.EXECUTIVE.value == "executive"
    
    def test_template_category(self):
        """Test TemplateCategory enum"""
        assert TemplateCategory.EXECUTIVE.value == "executive"
        assert TemplateCategory.OPERATIONAL.value == "operational"
