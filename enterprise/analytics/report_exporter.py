"""
Report Exporter
Enterprise Analytics & Reporting - Week 44 Builder 3
"""

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    """Export formats"""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    PDF = "pdf"
    HTML = "html"


@dataclass
class ExportResult:
    """Result of an export operation"""
    success: bool
    format: ExportFormat
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    content: Optional[bytes] = None
    size_bytes: int = 0
    error: Optional[str] = None
    exported_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "format": self.format.value,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "size_bytes": self.size_bytes,
            "error": self.error,
            "exported_at": self.exported_at.isoformat()
        }


class DataExporter:
    """Exports data in various formats"""
    
    def __init__(self, output_dir: str = "/tmp/reports"):
        self.output_dir = output_dir
    
    async def export(
        self,
        data: Dict[str, Any],
        format: ExportFormat,
        filename: Optional[str] = None
    ) -> ExportResult:
        """Export data to specified format"""
        try:
            if not filename:
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                filename = f"report_{timestamp}.{format.value}"
            
            if format == ExportFormat.CSV:
                return await self._export_csv(data, filename)
            elif format == ExportFormat.JSON:
                return await self._export_json(data, filename)
            elif format == ExportFormat.EXCEL:
                return await self._export_excel(data, filename)
            elif format == ExportFormat.HTML:
                return await self._export_html(data, filename)
            elif format == ExportFormat.PDF:
                return await self._export_pdf(data, filename)
            else:
                return ExportResult(
                    success=False,
                    format=format,
                    error=f"Unsupported format: {format}"
                )
                
        except Exception as e:
            logger.error(f"Export error: {e}")
            return ExportResult(
                success=False,
                format=format,
                error=str(e)
            )
    
    async def _export_csv(
        self,
        data: Dict[str, Any],
        filename: str
    ) -> ExportResult:
        """Export data to CSV"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Handle different data structures
        if "columns" in data and "rows" in data:
            # Table format
            writer.writerow([col.get("header", col.get("field", "")) for col in data["columns"]])
            for row in data["rows"]:
                writer.writerow([row.get(col.get("field", ""), "") for col in data["columns"]])
        elif "data" in data:
            # Chart/dataset format
            if isinstance(data["data"], dict):
                if "labels" in data["data"] and "datasets" in data["data"]:
                    writer.writerow(["Label"] + [d.get("label", f"Series{i}") for i, d in enumerate(data["data"]["datasets"])])
                    for i, label in enumerate(data["data"]["labels"]):
                        row = [label]
                        for dataset in data["data"]["datasets"]:
                            row.append(dataset.get("data", [])[i] if i < len(dataset.get("data", [])) else "")
                        writer.writerow(row)
        elif "kpis" in data:
            # KPI list format
            writer.writerow(["Metric", "Value", "Change"])
            for kpi in data["kpis"]:
                writer.writerow([kpi.get("name", ""), kpi.get("value", ""), kpi.get("change", "")])
        else:
            # Generic key-value format
            writer.writerow(["Key", "Value"])
            for key, value in data.items():
                if isinstance(value, (list, dict)):
                    writer.writerow([key, json.dumps(value)])
                else:
                    writer.writerow([key, value])
        
        content = output.getvalue().encode("utf-8")
        
        return ExportResult(
            success=True,
            format=ExportFormat.CSV,
            file_name=filename,
            content=content,
            size_bytes=len(content)
        )
    
    async def _export_json(
        self,
        data: Dict[str, Any],
        filename: str
    ) -> ExportResult:
        """Export data to JSON"""
        content = json.dumps(data, indent=2, default=str).encode("utf-8")
        
        return ExportResult(
            success=True,
            format=ExportFormat.JSON,
            file_name=filename,
            content=content,
            size_bytes=len(content)
        )
    
    async def _export_excel(
        self,
        data: Dict[str, Any],
        filename: str
    ) -> ExportResult:
        """Export data to Excel (simplified - creates CSV with .xlsx extension)"""
        # In real implementation, would use openpyxl or xlsxwriter
        # For now, return CSV format
        csv_result = await self._export_csv(data, filename.replace(".xlsx", ".csv"))
        
        if csv_result.success:
            csv_result.format = ExportFormat.EXCEL
            csv_result.file_name = filename
        
        return csv_result
    
    async def _export_html(
        self,
        data: Dict[str, Any],
        filename: str
    ) -> ExportResult:
        """Export data to HTML"""
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #4CAF50; color: white; }",
            "tr:nth-child(even) { background-color: #f2f2f2; }",
            ".kpi-card { background: #f9f9f9; padding: 15px; margin: 10px 0; border-radius: 5px; }",
            ".kpi-value { font-size: 24px; font-weight: bold; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>Report - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}</h1>"
        ]
        
        # Process different data structures
        if "kpis" in data:
            html_parts.append("<div class='kpi-section'><h2>Key Metrics</h2>")
            for kpi in data["kpis"]:
                change_class = "positive" if kpi.get("change", 0) >= 0 else "negative"
                html_parts.append(f"""
                    <div class='kpi-card'>
                        <h3>{kpi.get('name', 'Metric')}</h3>
                        <div class='kpi-value'>{kpi.get('value', 'N/A')}</div>
                        <div class='{change_class}'>Change: {kpi.get('change', 0)}%</div>
                    </div>
                """)
            html_parts.append("</div>")
        
        if "columns" in data and "rows" in data:
            html_parts.append("<h2>Data Table</h2>")
            html_parts.append("<table>")
            html_parts.append("<tr>")
            for col in data["columns"]:
                html_parts.append(f"<th>{col.get('header', col.get('field', ''))}</th>")
            html_parts.append("</tr>")
            for row in data["rows"]:
                html_parts.append("<tr>")
                for col in data["columns"]:
                    html_parts.append(f"<td>{row.get(col.get('field', ''), '')}</td>")
                html_parts.append("</tr>")
            html_parts.append("</table>")
        
        html_parts.extend(["</body>", "</html>"])
        
        content = "\n".join(html_parts).encode("utf-8")
        
        return ExportResult(
            success=True,
            format=ExportFormat.HTML,
            file_name=filename,
            content=content,
            size_bytes=len(content)
        )
    
    async def _export_pdf(
        self,
        data: Dict[str, Any],
        filename: str
    ) -> ExportResult:
        """Export data to PDF (simplified - creates HTML)"""
        # In real implementation, would use reportlab or weasyprint
        # For now, return HTML format
        html_result = await self._export_html(data, filename.replace(".pdf", ".html"))
        
        if html_result.success:
            html_result.format = ExportFormat.PDF
            html_result.file_name = filename
        
        return html_result


class ReportExporter:
    """Exports complete reports"""
    
    def __init__(self):
        self.data_exporter = DataExporter()
    
    async def export_report(
        self,
        report_data: Dict[str, Any],
        format: ExportFormat,
        report_name: str = "Report"
    ) -> ExportResult:
        """Export a complete report"""
        # Combine all sections
        combined_data = {
            "report_name": report_name,
            "exported_at": datetime.utcnow().isoformat(),
            "sections": []
        }
        
        for section_id, section_data in report_data.get("sections_data", {}).items():
            combined_data["sections"].append({
                "section_id": section_id,
                "data": section_data
            })
        
        # Add summary if available
        if "summary" in report_data:
            combined_data["summary"] = report_data["summary"]
        
        return await self.data_exporter.export(combined_data, format, f"{report_name}.{format.value}")
    
    async def export_section(
        self,
        section_data: Dict[str, Any],
        format: ExportFormat,
        section_name: str = "Section"
    ) -> ExportResult:
        """Export a single report section"""
        return await self.data_exporter.export(section_data, format, f"{section_name}.{format.value}")
    
    async def export_multiple_formats(
        self,
        data: Dict[str, Any],
        formats: List[ExportFormat]
    ) -> Dict[ExportFormat, ExportResult]:
        """Export data in multiple formats"""
        results = {}
        
        for fmt in formats:
            results[fmt] = await self.data_exporter.export(data, fmt)
        
        return results
