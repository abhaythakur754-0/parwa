"""
PARWA Export Reports API Routes (Week 15 — Dashboard + Analytics)

FastAPI router endpoints for report generation and download.

Endpoints:
- POST /api/reports/export — Create export job (F-045)
- GET  /api/reports/jobs — List export jobs (F-045)
- GET  /api/reports/jobs/{job_id} — Get job status (F-045)
- GET  /api/reports/download/{job_id} — Download report file (F-045)

Building Codes: BC-001 (tenant isolation), BC-010 (GDPR),
               BC-011 (auth), BC-012 (error handling)
"""

from app.api.deps import (
    get_company_id,
    get_current_user,
    require_roles,
)
from app.exceptions import ValidationError
from app.logger import get_logger
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database.base import get_db
from database.models.core import User

logger = get_logger("reports_api")

router = APIRouter(
    prefix="/api/reports",
    tags=["reports", "export"],
    dependencies=[Depends(require_roles("owner", "admin"))],
)


# ══════════════════════════════════════════════════════════════════
# F-045: EXPORT REPORTS
# ══════════════════════════════════════════════════════════════════


@router.post("/export")
async def create_export(
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new export report job.

    Generates a report in the specified format (CSV or PDF).
    Supported report types: summary, tickets, agents, sla, csat, forecast, full.

    F-045: Export Reports
    BC-001: Scoped by company_id.
    BC-010: Only exports data belonging to the requesting tenant.
    BC-011: Requires authentication.
    """
    try:
        body = await request.json()
    except Exception:
        raise ValidationError(
            message="Invalid JSON body",
            details={"expected": {"report_type": "string", "format": "string"}},
        )

    report_type = body.get("report_type", "summary")
    format_type = body.get("format", "csv")
    date_start = body.get("date_range_start")
    date_end = body.get("date_range_end")
    filters = body.get("filters", {})

    try:
        from app.services.export_service import create_export_job

        result = create_export_job(
            company_id=company_id,
            report_type=report_type,
            format=format_type,
            date_range_start=date_start,
            date_range_end=date_end,
            filters=filters,
            created_by=str(user.id),
        )

        logger.info(
            "export_job_created",
            company_id=company_id,
            user_id=str(user.id),
            report_type=report_type,
            format=format_type,
            job_id=result.get("job_id"),
            status=result.get("status"),
        )

        return result

    except Exception as exc:
        logger.error(
            "export_create_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get("/jobs")
async def list_export_jobs(
    limit: int = Query(20, ge=1, le=100, description="Max jobs to return"),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """List recent export jobs for the current tenant.

    F-045: Export Reports
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.export_service import list_export_jobs

        jobs = list_export_jobs(company_id, limit=limit)

        return {
            "jobs": jobs,
            "total": len(jobs),
        }

    except Exception as exc:
        logger.error(
            "export_list_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get("/jobs/{job_id}")
async def get_export_job(
    job_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """Get the status of a specific export job.

    Returns status, download URL (when completed), and error (if failed).

    F-045: Export Reports
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.export_service import get_export_job_status

        result = get_export_job_status(job_id)

        if "error" in result and result.get("job_id") == job_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["error"],
            )

        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "export_status_error",
            company_id=company_id,
            job_id=job_id,
            error=str(exc),
        )
        raise


@router.get("/download/{job_id}")
async def download_report(
    job_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """Download a completed export report file.

    Returns the CSV or PDF file for download.

    F-045: Export Reports
    BC-001: Scoped by company_id (only download own reports).
    BC-011: Requires authentication.
    """
    try:
        import os

        from app.services.export_service import EXPORT_DIR, get_export_job_status

        result = get_export_job_status(job_id)

        # Verify the job belongs to this company
        if not result.get("job_id"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Export job not found",
            )

        if result.get("status") != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Report is not ready. Current status: {
                    result.get('status')}",
            )

        # Find the file
        # Try CSV first, then PDF
        csv_path = os.path.join(EXPORT_DIR, f"{job_id}.csv")
        pdf_path = os.path.join(EXPORT_DIR, f"{job_id}.pdf")

        file_path = None
        media_type = None

        if os.path.exists(csv_path):
            file_path = csv_path
            media_type = "text/csv"
        elif os.path.exists(pdf_path):
            file_path = pdf_path
            media_type = "application/pdf"

        if not file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report file not found",
            )

        filename = os.path.basename(file_path)

        logger.info(
            "report_downloaded",
            company_id=company_id,
            user_id=str(user.id),
            job_id=job_id,
            filename=filename,
        )

        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=f"parwa_report_{job_id[:8]}{os.path.splitext(file_path)[1]}",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "report_download_error",
            company_id=company_id,
            job_id=job_id,
            error=str(exc),
        )
        raise
