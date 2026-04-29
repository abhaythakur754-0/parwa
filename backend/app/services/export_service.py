"""
PARWA Export Report Service (F-045)

Generates CSV and PDF reports from analytics data.
Provides async report generation via Celery with download link management.

Features:
- CSV export for all report types (summary, tickets, agents, sla, csat, forecast, full)
- PDF report generation with formatted tables
- Async job tracking with status polling
- Download link generation and management
- Auto-cleanup of old report files

Methods:
- create_export_job() — Start async report generation
- get_export_job_status() — Check job progress
- generate_csv_report() — Create CSV file
- generate_pdf_report() — Create PDF file

Building Codes: BC-001 (multi-tenant), BC-002 (financial precision),
               BC-010 (GDPR), BC-012 (error handling)
"""

from __future__ import annotations

import csv
import io
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc

from app.logger import get_logger

logger = get_logger("export_service")

# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

VALID_REPORT_TYPES = {
    "summary", "tickets", "agents", "sla", "csat", "forecast", "full",
}
VALID_FORMATS = {"csv", "pdf"}

# Export storage directory
EXPORT_DIR = "/tmp/parwa_exports"

# In-memory job tracking (for single-instance; Redis for production)
_export_jobs: Dict[str, Dict[str, Any]] = {}


# ══════════════════════════════════════════════════════════════════
# EXPORT JOB MANAGEMENT
# ══════════════════════════════════════════════════════════════════


def create_export_job(
    company_id: str,
    report_type: str,
    format: str,
    date_range_start: Optional[str] = None,
    date_range_end: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an export job and start report generation.

    Generates the report synchronously (for Celery async, wrap in task).
    Returns job details with download URL when complete.

    F-045: Export Reports
    BC-001: Scoped by company_id.
    BC-010: All exported data is tenant-isolated.
    """
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Validate inputs
    if report_type not in VALID_REPORT_TYPES:
        return {
            "error": f"Invalid report_type '{report_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_REPORT_TYPES))}",
        }
    if format not in VALID_FORMATS:
        return {
            "error": f"Invalid format '{format}'. "
            f"Must be one of: {', '.join(sorted(VALID_FORMATS))}",
        }

    job = {
        "job_id": job_id,
        "company_id": company_id,
        "report_type": report_type,
        "format": format,
        "status": "processing",
        "download_url": None,
        "file_size_bytes": None,
        "created_at": now.isoformat(),
        "completed_at": None,
        "error": None,
        "created_by": created_by,
    }

    _export_jobs[job_id] = job

    logger.info(
        "export_job_created",
        company_id=company_id,
        job_id=job_id,
        report_type=report_type,
        format=format,
    )

    # Generate report immediately (in production, dispatch to Celery)
    try:
        os.makedirs(EXPORT_DIR, exist_ok=True)

        if format == "csv":
            result = generate_csv_report(
                company_id=company_id,
                report_type=report_type,
                date_range_start=date_range_start,
                date_range_end=date_range_end,
                filters=filters or {},
                job_id=job_id,
            )
        else:
            result = generate_pdf_report(
                company_id=company_id,
                report_type=report_type,
                date_range_start=date_range_start,
                date_range_end=date_range_end,
                filters=filters or {},
                job_id=job_id,
            )

        if result.get("error"):
            job["status"] = "failed"
            job["error"] = result["error"]
        else:
            job["status"] = "completed"
            job["download_url"] = result.get("download_url")
            job["file_size_bytes"] = result.get("file_size_bytes", 0)
            job["completed_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)[:500]
        logger.error(
            "export_job_failed",
            company_id=company_id,
            job_id=job_id,
            error=str(exc),
        )

    return _job_to_response(job)


def get_export_job_status(job_id: str) -> Dict[str, Any]:
    """Get the status of an export job.

    Returns job details including status, download URL (when complete),
    and error message (if failed).
    """
    job = _export_jobs.get(job_id)
    if not job:
        return {
            "error": "Export job not found",
            "job_id": job_id,
        }
    return _job_to_response(job)


def list_export_jobs(
    company_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """List export jobs for a company."""
    company_jobs = [
        _job_to_response(j)
        for j in _export_jobs.values()
        if j.get("company_id") == company_id
    ]
    # Sort by created_at descending
    company_jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return company_jobs[:limit]


# ══════════════════════════════════════════════════════════════════
# CSV REPORT GENERATION
# ══════════════════════════════════════════════════════════════════


def generate_csv_report(
    company_id: str,
    report_type: str,
    date_range_start: Optional[str] = None,
    date_range_end: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a CSV report file.

    Returns a dict with download_url and file_size_bytes on success.
    """
    try:
        output = io.StringIO()
        writer = csv.writer(output)

        # Get data based on report type
        if report_type == "tickets":
            rows = _get_ticket_csv_data(
                company_id, date_range_start, date_range_end, filters)
        elif report_type == "summary":
            rows = _get_summary_csv_data(
                company_id, date_range_start, date_range_end, filters)
        elif report_type == "agents":
            rows = _get_agents_csv_data(
                company_id, date_range_start, date_range_end, filters)
        elif report_type == "sla":
            rows = _get_sla_csv_data(
                company_id,
                date_range_start,
                date_range_end,
                filters)
        elif report_type == "csat":
            rows = _get_csat_csv_data(
                company_id, date_range_start, date_range_end, filters)
        elif report_type == "forecast":
            rows = _get_forecast_csv_data(
                company_id, date_range_start, date_range_end, filters)
        elif report_type == "full":
            rows = _get_full_csv_data(
                company_id, date_range_start, date_range_end, filters)
        else:
            rows = _get_summary_csv_data(
                company_id, date_range_start, date_range_end, filters)

        if not rows:
            return {"error": "No data available for the selected filters"}

        # Write CSV
        writer.writerows(rows)

        csv_content = output.getvalue()
        file_path = os.path.join(EXPORT_DIR, f"{job_id or uuid.uuid4()}.csv")

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            f.write(csv_content)

        file_size = os.path.getsize(file_path)

        logger.info(
            "csv_report_generated",
            company_id=company_id,
            report_type=report_type,
            file_size=file_size,
            rows=len(rows) - 1,  # minus header
        )

        return {
            "download_url": f"/api/reports/download/{job_id or 'unknown'}",
            "file_size_bytes": file_size,
        }

    except Exception as exc:
        logger.error(
            "csv_generation_error",
            company_id=company_id,
            report_type=report_type,
            error=str(exc),
        )
        return {"error": str(exc)[:200]}


# ══════════════════════════════════════════════════════════════════
# PDF REPORT GENERATION
# ══════════════════════════════════════════════════════════════════


def generate_pdf_report(
    company_id: str,
    report_type: str,
    date_range_start: Optional[str] = None,
    date_range_end: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a PDF report file.

    Creates a structured PDF with tables using ReportLab.
    Falls back to CSV if ReportLab is not available.
    """
    try:
        # Try to use ReportLab
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
            )

            file_path = os.path.join(
                EXPORT_DIR, f"{
                    job_id or uuid.uuid4()}.pdf")

            doc = SimpleDocTemplate(
                file_path,
                pagesize=A4,
                rightMargin=20 * mm,
                leftMargin=20 * mm,
                topMargin=20 * mm,
                bottomMargin=20 * mm,
            )

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=18,
                spaceAfter=12,
                textColor=colors.HexColor("#1a1a2e"),
            )
            subtitle_style = ParagraphStyle(
                "CustomSubtitle",
                parent=styles["Normal"],
                fontSize=10,
                textColor=colors.grey,
                spaceAfter=20,
            )

            elements = []

            # Title
            report_titles = {
                "summary": "PARWA Analytics Summary Report",
                "tickets": "PARWA Ticket Report",
                "agents": "PARWA Agent Performance Report",
                "sla": "PARWA SLA Compliance Report",
                "csat": "PARWA Customer Satisfaction Report",
                "forecast": "PARWA Volume Forecast Report",
                "full": "PARWA Full Analytics Report",
            }
            elements.append(Paragraph(
                report_titles.get(report_type, "PARWA Report"),
                title_style,
            ))
            elements.append(Paragraph(
                f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  |  "
                f"Period: {date_range_start or 'All time'} to {date_range_end or 'Now'}",
                subtitle_style,
            ))
            elements.append(Spacer(1, 12))

            # Get CSV data and convert to table
            if report_type == "tickets":
                rows = _get_ticket_csv_data(
                    company_id, date_range_start, date_range_end, filters)
            elif report_type == "summary":
                rows = _get_summary_csv_data(
                    company_id, date_range_start, date_range_end, filters)
            elif report_type == "agents":
                rows = _get_agents_csv_data(
                    company_id, date_range_start, date_range_end, filters)
            elif report_type == "sla":
                rows = _get_sla_csv_data(
                    company_id, date_range_start, date_range_end, filters)
            elif report_type == "csat":
                rows = _get_csat_csv_data(
                    company_id, date_range_start, date_range_end, filters)
            elif report_type == "forecast":
                rows = _get_forecast_csv_data(
                    company_id, date_range_start, date_range_end, filters)
            elif report_type == "full":
                rows = _get_full_csv_data(
                    company_id, date_range_start, date_range_end, filters)
            else:
                rows = _get_summary_csv_data(
                    company_id, date_range_start, date_range_end, filters)

            if rows:
                # Build table
                table = Table(rows)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                elements.append(table)

            doc.build(elements)

            file_size = os.path.getsize(file_path)

            logger.info(
                "pdf_report_generated",
                company_id=company_id,
                report_type=report_type,
                file_size=file_size,
            )

            return {
                "download_url": f"/api/reports/download/{job_id or 'unknown'}",
                "file_size_bytes": file_size,
            }

        except ImportError:
            # ReportLab not available, fall back to CSV
            logger.warning(
                "reportlab_not_available",
                message="Falling back to CSV generation",
            )
            return generate_csv_report(
                company_id, report_type,
                date_range_start, date_range_end, filters, job_id,
            )

    except Exception as exc:
        logger.error(
            "pdf_generation_error",
            company_id=company_id,
            report_type=report_type,
            error=str(exc),
        )
        return {"error": str(exc)[:200]}


# ══════════════════════════════════════════════════════════════════
# CSV DATA PROVIDERS
# ══════════════════════════════════════════════════════════════════


def _get_summary_csv_data(
    company_id: str,
    start: Optional[str],
    end: Optional[str],
    filters: Optional[Dict[str, Any]],
) -> List[List[str]]:
    """Get summary report CSV data."""
    try:
        from app.services.dashboard_service import get_key_metrics
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            data = get_key_metrics(company_id, db, period="last_30d")
            kpis = data.get("kpis", [])

            rows = [["KPI", "Value", "Previous", "Change %", "Unit"]]
            for kpi in kpis:
                rows.append([
                    kpi.get("label", ""),
                    str(kpi.get("value", "")),
                    str(kpi.get("previous_value", "")),
                    str(kpi.get("change_pct", "")),
                    kpi.get("unit", ""),
                ])

            return rows
        finally:
            db.close()
    except Exception:
        return [["Error", "Could not generate summary data"]]


def _get_ticket_csv_data(
    company_id: str,
    start: Optional[str],
    end: Optional[str],
    filters: Optional[Dict[str, Any]],
) -> List[List[str]]:
    """Get ticket report CSV data."""
    try:
        from database.base import SessionLocal
        from database.models.tickets import Ticket

        db = SessionLocal()
        try:
            query = db.query(Ticket).filter(Ticket.company_id == company_id)

            if start:
                query = query.filter(Ticket.created_at >= start)
            if end:
                query = query.filter(Ticket.created_at <= end)

            status_filter = (filters or {}).get("status")
            if status_filter:
                query = query.filter(Ticket.status == status_filter)

            tickets = query.order_by(desc(Ticket.created_at)).limit(5000).all()

            rows = [
                ["Ticket ID", "Subject", "Status", "Priority", "Category",
                 "Created At", "Updated At", "Assigned To", "Channel"],
            ]
            for t in tickets:
                rows.append([
                    str(t.id),
                    t.subject or "",
                    t.status or "",
                    t.priority or "",
                    t.category or "",
                    t.created_at.isoformat() if t.created_at else "",
                    t.updated_at.isoformat() if t.updated_at else "",
                    str(t.assigned_to or ""),
                    getattr(t, "channel", "") or "",
                ])

            return rows
        finally:
            db.close()
    except Exception:
        return [["Error", "Could not generate ticket data"]]


def _get_agents_csv_data(
    company_id: str,
    start: Optional[str],
    end: Optional[str],
    filters: Optional[Dict[str, Any]],
) -> List[List[str]]:
    """Get agent performance report CSV data."""
    try:
        from app.services.ticket_analytics_service import (
            TicketAnalyticsService, DateRange,
        )
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            svc = TicketAnalyticsService(db, company_id)
            dr = None
            if start and end:
                dr = DateRange(
                    start_date=datetime.fromisoformat(start),
                    end_date=datetime.fromisoformat(end),
                )
            elif start:
                dr = DateRange(
                    start_date=datetime.fromisoformat(start),
                    end_date=datetime.now(timezone.utc),
                )

            metrics = svc.get_agent_metrics(dr)

            rows = [
                ["Agent ID", "Agent Name", "Assigned", "Resolved", "Open",
                 "Resolution Rate", "CSAT Avg", "CSAT Count"],
            ]
            for m in metrics:
                rows.append([
                    m.agent_id,
                    m.agent_name or "",
                    str(m.tickets_assigned),
                    str(m.tickets_resolved),
                    str(m.tickets_open),
                    f"{m.resolution_rate:.1%}",
                    str(m.csat_avg or ""),
                    str(m.csat_count),
                ])

            return rows
        finally:
            db.close()
    except Exception:
        return [["Error", "Could not generate agent data"]]


def _get_sla_csv_data(
    company_id: str,
    start: Optional[str],
    end: Optional[str],
    filters: Optional[Dict[str, Any]],
) -> List[List[str]]:
    """Get SLA report CSV data."""
    try:
        from app.services.ticket_analytics_service import (
            TicketAnalyticsService, DateRange,
        )
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            svc = TicketAnalyticsService(db, company_id)
            dr = None
            if start and end:
                dr = DateRange(
                    start_date=datetime.fromisoformat(start),
                    end_date=datetime.fromisoformat(end),
                )
            elif start:
                dr = DateRange(
                    start_date=datetime.fromisoformat(start),
                    end_date=datetime.now(timezone.utc),
                )

            sla = svc.get_sla_metrics(dr)

            rows = [["SLA Metric", "Value"]]
            rows.append(["Total Tickets with SLA",
                        str(sla.total_tickets_with_sla)])
            rows.append(["Breached Count", str(sla.breached_count)])
            rows.append(["Approaching Count", str(sla.approaching_count)])
            rows.append(["Compliant Count", str(sla.compliant_count)])
            rows.append(["Compliance Rate", f"{sla.compliance_rate:.1%}"])
            rows.append(["Avg First Response (min)", str(
                sla.avg_first_response_minutes or "")])
            rows.append(["Avg Resolution (min)", str(
                sla.avg_resolution_minutes or "")])

            return rows
        finally:
            db.close()
    except Exception:
        return [["Error", "Could not generate SLA data"]]


def _get_csat_csv_data(
    company_id: str,
    start: Optional[str],
    end: Optional[str],
    filters: Optional[Dict[str, Any]],
) -> List[List[str]]:
    """Get CSAT report CSV data."""
    try:
        from app.services.analytics_intelligence_service import get_csat_trends
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            data = get_csat_trends(company_id, db, days=30)

            rows = [["Date", "Avg Rating", "Total Ratings"]]
            for day in data.get("daily_trend", []):
                rows.append([
                    day["date"],
                    str(day["avg_rating"]),
                    str(day["total_ratings"]),
                ])

            # Add breakdowns
            rows.append([])
            rows.append(["CSAT by Agent", "Avg Rating", "Total Ratings"])
            for agent in data.get("by_agent", []):
                rows.append([
                    agent["dimension_name"],
                    str(agent["avg_rating"]),
                    str(agent["total_ratings"]),
                ])

            rows.append([])
            rows.append(["CSAT by Category", "Avg Rating", "Total Ratings"])
            for cat in data.get("by_category", []):
                rows.append([
                    cat["dimension_name"],
                    str(cat["avg_rating"]),
                    str(cat["total_ratings"]),
                ])

            return rows
        finally:
            db.close()
    except Exception:
        return [["Error", "Could not generate CSAT data"]]


def _get_forecast_csv_data(
    company_id: str,
    start: Optional[str],
    end: Optional[str],
    filters: Optional[Dict[str, Any]],
) -> List[List[str]]:
    """Get forecast report CSV data."""
    try:
        from app.services.analytics_intelligence_service import get_ticket_forecast
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            data = get_ticket_forecast(company_id, db)

            rows = [["Date", "Type", "Value", "Lower Bound", "Upper Bound"]]

            for point in data.get("historical", []):
                rows.append([
                    point["date"], "Historical",
                    str(point.get("actual", "")), "", "",
                ])

            for point in data.get("forecast", []):
                rows.append([
                    point["date"], "Forecast",
                    str(point.get("predicted", "")),
                    str(point.get("lower_bound", "")),
                    str(point.get("upper_bound", "")),
                ])

            rows.append([])
            rows.append(["Metric", "Value"])
            rows.append(["Model", data.get("model_type", "")])
            rows.append(["Trend Direction", data.get("trend_direction", "")])
            rows.append(["Avg Daily Volume", str(
                data.get("avg_daily_volume", ""))])
            rows.append(["Seasonality Detected", str(
                data.get("seasonality_detected", ""))])

            return rows
        finally:
            db.close()
    except Exception:
        return [["Error", "Could not generate forecast data"]]


def _get_full_csv_data(
    company_id: str,
    start: Optional[str],
    end: Optional[str],
    filters: Optional[Dict[str, Any]],
) -> List[List[str]]:
    """Get full report CSV data (combines all reports)."""
    rows = []

    # Summary section
    rows.append(["=== SUMMARY ==="])
    rows.extend(_get_summary_csv_data(company_id, start, end, filters))
    rows.append([])

    # Ticket section
    rows.append(["=== TICKETS ==="])
    rows.extend(_get_ticket_csv_data(company_id, start, end, filters))
    rows.append([])

    # SLA section
    rows.append(["=== SLA ==="])
    rows.extend(_get_sla_csv_data(company_id, start, end, filters))
    rows.append([])

    # CSAT section
    rows.append(["=== CSAT ==="])
    rows.extend(_get_csat_csv_data(company_id, start, end, filters))
    rows.append([])

    # Forecast section
    rows.append(["=== FORECAST ==="])
    rows.extend(_get_forecast_csv_data(company_id, start, end, filters))

    return rows


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════


def _job_to_response(job: Dict[str, Any]) -> Dict[str, Any]:
    """Convert internal job dict to API response."""
    return {
        "job_id": job["job_id"],
        "report_type": job["report_type"],
        "format": job["format"],
        "status": job["status"],
        "download_url": job.get("download_url"),
        "file_size_bytes": job.get("file_size_bytes"),
        "created_at": job["created_at"],
        "completed_at": job.get("completed_at"),
        "error": job.get("error"),
    }
