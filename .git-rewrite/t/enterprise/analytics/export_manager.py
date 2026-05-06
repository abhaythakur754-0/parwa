"""
Enterprise Analytics - Export Manager
Export reports in multiple formats
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import json
import csv
import io


class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    EXCEL = "excel"


class ExportJob(BaseModel):
    """Export job definition"""
    job_id: str
    format: ExportFormat
    data: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"

    model_config = ConfigDict()


class ExportManager:
    """
    Export manager for enterprise analytics reports.
    """

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.jobs: Dict[str, ExportJob] = {}

    def create_export(self, data: Dict[str, Any], format: ExportFormat) -> ExportJob:
        """Create an export job"""
        job_id = f"export_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        job = ExportJob(
            job_id=job_id,
            format=format,
            data=data
        )
        self.jobs[job_id] = job
        return job

    def export_json(self, data: Dict[str, Any]) -> str:
        """Export as JSON"""
        return json.dumps(data, indent=2, default=str)

    def export_csv(self, data: Dict[str, Any]) -> str:
        """Export as CSV"""
        output = io.StringIO()
        writer = csv.writer(output)

        # Flatten data for CSV
        if isinstance(data, dict):
            writer.writerow(data.keys())
            writer.writerow(data.values())

        return output.getvalue()

    def get_export(self, job_id: str) -> Optional[str]:
        """Get exported data"""
        if job_id not in self.jobs:
            return None

        job = self.jobs[job_id]
        if job.format == ExportFormat.JSON:
            return self.export_json(job.data)
        elif job.format == ExportFormat.CSV:
            return self.export_csv(job.data)

        return json.dumps(job.data)
