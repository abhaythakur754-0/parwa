"""
PARWA Ticket Export API - Ticket-Specific Export Endpoints (Day 5)

Provides ticket-specific export functionality:
- Export single ticket as PDF/JSON
- Export filtered tickets as CSV/JSON
- Duplicate ticket detection
- Merge preview endpoint
"""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from app.api.deps import get_current_user, get_db, require_roles
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from database.models.tickets import Ticket, TicketAttachment, TicketMessage

router = APIRouter(
    prefix="/tickets/export",
    tags=["ticket-export"],
    dependencies=[Depends(require_roles("owner", "admin", "agent"))],
)

EXPORT_DIR = "/tmp/parwa_exports"


@router.post(
    "/csv",
    summary="Export tickets to CSV",
)
async def export_tickets_csv(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Export filtered tickets to CSV file.

    Request body:
    - ticket_ids: List of ticket IDs to export (optional)
    - filters: Filter criteria (status, priority, date_range, etc.)
    """
    company_id = current_user.get("company_id")

    body = await request.json() if await request.body() else {}
    ticket_ids = body.get("ticket_ids", [])
    filters = body.get("filters", {})

    # Build query
    query = db.query(Ticket).filter(Ticket.company_id == company_id)

    if ticket_ids:
        query = query.filter(Ticket.id.in_(ticket_ids))

    # Apply filters
    if filters.get("status"):
        query = query.filter(Ticket.status == filters["status"])
    if filters.get("priority"):
        query = query.filter(Ticket.priority == filters["priority"])
    if filters.get("category"):
        query = query.filter(Ticket.category == filters["category"])
    if filters.get("assigned_to"):
        query = query.filter(Ticket.assigned_to == filters["assigned_to"])
    if filters.get("date_from"):
        query = query.filter(Ticket.created_at >= filters["date_from"])
    if filters.get("date_to"):
        query = query.filter(Ticket.created_at <= filters["date_to"])

    tickets = query.order_by(desc(Ticket.created_at)).limit(10000).all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        [
            "Ticket ID",
            "Subject",
            "Status",
            "Priority",
            "Category",
            "Channel",
            "Customer ID",
            "Assigned To",
            "Created At",
            "Updated At",
            "First Response At",
            "Resolved At",
            "Closed At",
            "SLA Status",
            "Tags",
            "CSAT Score",
        ]
    )

    # Data rows
    for t in tickets:
        writer.writerow(
            [
                str(t.id),
                t.subject or "",
                t.status or "",
                t.priority or "",
                t.category or "",
                getattr(t, "channel", "") or "",
                str(t.customer_id or ""),
                str(t.assigned_to or ""),
                t.created_at.isoformat() if t.created_at else "",
                t.updated_at.isoformat() if t.updated_at else "",
                t.first_response_at.isoformat() if t.first_response_at else "",
                t.resolved_at.isoformat() if t.resolved_at else "",
                t.closed_at.isoformat() if t.closed_at else "",
                getattr(t, "sla_status", "") or "",
                json.dumps(t.tags) if t.tags else "[]",
                str(getattr(t, "csat_score", "") or ""),
            ]
        )

    output.seek(0)

    # Stream response
    filename = f"tickets_export_{
        datetime.now(
            timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post(
    "/json",
    summary="Export tickets to JSON",
)
async def export_tickets_json(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Export filtered tickets to JSON file.

    Includes full ticket details including messages.
    """
    company_id = current_user.get("company_id")

    body = await request.json() if await request.body() else {}
    ticket_ids = body.get("ticket_ids", [])
    filters = body.get("filters", {})
    include_messages = body.get("include_messages", True)

    # Build query
    query = db.query(Ticket).filter(Ticket.company_id == company_id)

    if ticket_ids:
        query = query.filter(Ticket.id.in_(ticket_ids))

    # Apply filters
    if filters.get("status"):
        query = query.filter(Ticket.status == filters["status"])
    if filters.get("priority"):
        query = query.filter(Ticket.priority == filters["priority"])
    if filters.get("date_from"):
        query = query.filter(Ticket.created_at >= filters["date_from"])
    if filters.get("date_to"):
        query = query.filter(Ticket.created_at <= filters["date_to"])

    tickets = query.order_by(desc(Ticket.created_at)).limit(1000).all()

    # Build JSON export
    export_data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "company_id": company_id,
        "total_tickets": len(tickets),
        "tickets": [],
    }

    for t in tickets:
        ticket_data = {
            "id": str(t.id),
            "subject": t.subject,
            "status": t.status,
            "priority": t.priority,
            "category": t.category,
            "channel": getattr(t, "channel", None),
            "customer_id": str(t.customer_id) if t.customer_id else None,
            "assigned_to": str(t.assigned_to) if t.assigned_to else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            "first_response_at": (
                t.first_response_at.isoformat() if t.first_response_at else None
            ),
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            "tags": t.tags or [],
            "custom_fields": json.loads(t.custom_fields) if t.custom_fields else {},
            "metadata": json.loads(t.metadata_json) if t.metadata_json else {},
        }

        if include_messages:
            messages = (
                db.query(TicketMessage)
                .filter(TicketMessage.ticket_id == t.id)
                .order_by(TicketMessage.created_at)
                .all()
            )

            ticket_data["messages"] = [
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "channel": m.channel,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "is_internal": m.is_internal,
                    "ai_confidence": (
                        float(m.ai_confidence) if m.ai_confidence else None
                    ),
                }
                for m in messages
            ]

        export_data["tickets"].append(ticket_data)

    return export_data


@router.get(
    "/{ticket_id}/pdf",
    summary="Export single ticket to PDF",
)
async def export_ticket_pdf(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Export a single ticket as PDF document."""
    company_id = current_user.get("company_id")

    ticket = (
        db.query(Ticket)
        .filter(
            Ticket.id == ticket_id,
            Ticket.company_id == company_id,
        )
        .first()
    )

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
        )

    # Get messages
    messages = (
        db.query(TicketMessage)
        .filter(TicketMessage.ticket_id == ticket_id)
        .order_by(TicketMessage.created_at)
        .all()
    )

    # Generate PDF
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        os.makedirs(EXPORT_DIR, exist_ok=True)
        file_path = os.path.join(EXPORT_DIR, f"{ticket_id}.pdf")

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
            "Title",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=10,
        )
        label_style = ParagraphStyle(
            "Label",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.grey,
        )

        elements = []

        # Title
        elements.append(Paragraph(f"Ticket #{ticket_id[:8]}", title_style))
        elements.append(Paragraph(ticket.subject or "No Subject", styles["Heading2"]))
        elements.append(Spacer(1, 10))

        # Ticket metadata table
        meta_data = [
            ["Status", ticket.status or ""],
            ["Priority", ticket.priority or ""],
            ["Category", ticket.category or ""],
            ["Channel", getattr(ticket, "channel", "") or ""],
            [
                "Created",
                (
                    ticket.created_at.strftime("%Y-%m-%d %H:%M")
                    if ticket.created_at
                    else ""
                ),
            ],
            [
                "Assigned To",
                str(ticket.assigned_to) if ticket.assigned_to else "Unassigned",
            ],
        ]

        meta_table = Table(meta_data, colWidths=[80, 200])
        meta_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
                    ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(meta_table)
        elements.append(Spacer(1, 20))

        # Messages
        elements.append(Paragraph("Conversation History", styles["Heading3"]))
        elements.append(Spacer(1, 10))

        for msg in messages:
            role_label = {
                "customer": "Customer",
                "agent": "Agent",
                "ai": "AI Assistant",
                "system": "System",
            }.get(msg.role, msg.role)

            role_color = {
                "customer": colors.HexColor("#3b82f6"),
                "agent": colors.HexColor("#10b981"),
                "ai": colors.HexColor("#8b5cf6"),
                "system": colors.grey,
            }.get(msg.role, colors.black)

            # Role header
            role_style = ParagraphStyle(
                "Role",
                parent=styles["Normal"],
                fontSize=10,
                textColor=role_color,
                fontName="Helvetica-Bold",
            )
            created = (
                msg.created_at.strftime("%Y-%m-%d %H:%M") if msg.created_at else ""
            )
            elements.append(Paragraph(f"{role_label} - {created}", role_style))

            # Message content
            content = msg.content or ""
            # Truncate very long messages
            if len(content) > 2000:
                content = content[:2000] + "..."

            elements.append(Paragraph(content.replace("\n", "<br/>"), styles["Normal"]))
            elements.append(Spacer(1, 10))

        doc.build(elements)

        # Return file
        from fastapi.responses import FileResponse

        return FileResponse(
            file_path,
            media_type="application/pdf",
            filename=f"ticket_{ticket_id[:8]}.pdf",
        )

    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF generation not available",
        )


@router.get(
    "/duplicates",
    summary="Find potential duplicate tickets",
)
async def find_duplicate_tickets(
    threshold: float = Query(0.7, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Find potential duplicate tickets based on subject and content similarity.

    Returns pairs of tickets that might be duplicates.
    """
    company_id = current_user.get("company_id")

    # Get open tickets for comparison
    tickets = (
        db.query(Ticket)
        .filter(
            Ticket.company_id == company_id,
            Ticket.status.in_(["open", "assigned", "in_progress"]),
        )
        .order_by(desc(Ticket.created_at))
        .limit(500)
        .all()
    )

    from difflib import SequenceMatcher

    duplicates = []

    for i, t1 in enumerate(tickets):
        for t2 in tickets[i + 1 :]:
            # Compare subjects
            subject_similarity = SequenceMatcher(
                None, (t1.subject or "").lower(), (t2.subject or "").lower()
            ).ratio()

            if subject_similarity >= threshold:
                duplicates.append(
                    {
                        "ticket_1": {
                            "id": str(t1.id),
                            "subject": t1.subject,
                            "status": t1.status,
                            "created_at": (
                                t1.created_at.isoformat() if t1.created_at else None
                            ),
                        },
                        "ticket_2": {
                            "id": str(t2.id),
                            "subject": t2.subject,
                            "status": t2.status,
                            "created_at": (
                                t2.created_at.isoformat() if t2.created_at else None
                            ),
                        },
                        "similarity": round(subject_similarity, 2),
                        "match_type": "subject",
                    }
                )

                if len(duplicates) >= limit:
                    return {"duplicates": duplicates, "total": len(duplicates)}

    return {"duplicates": duplicates, "total": len(duplicates)}


@router.post(
    "/merge-preview",
    summary="Preview ticket merge",
)
async def preview_ticket_merge(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Preview what would happen if tickets are merged.

    Shows messages, attachments, and internal notes that would be transferred.
    """
    company_id = current_user.get("company_id")

    body = await request.json()
    primary_ticket_id = body.get("primary_ticket_id")
    merged_ticket_ids = body.get("merged_ticket_ids", [])

    if not primary_ticket_id or not merged_ticket_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="primary_ticket_id and merged_ticket_ids are required",
        )

    # Get primary ticket
    primary = (
        db.query(Ticket)
        .filter(
            Ticket.id == primary_ticket_id,
            Ticket.company_id == company_id,
        )
        .first()
    )

    if not primary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Primary ticket not found"
        )

    # Get tickets to merge
    tickets_to_merge = (
        db.query(Ticket)
        .filter(
            Ticket.id.in_(merged_ticket_ids),
            Ticket.company_id == company_id,
        )
        .all()
    )

    # Count items to transfer
    total_messages = 0
    total_attachments = 0
    total_notes = 0

    for t in tickets_to_merge:
        total_messages += (
            db.query(TicketMessage).filter(TicketMessage.ticket_id == t.id).count()
        )

        total_attachments += (
            db.query(TicketAttachment)
            .filter(TicketAttachment.ticket_id == t.id)
            .count()
        )

    return {
        "primary_ticket": {
            "id": str(primary.id),
            "subject": primary.subject,
            "status": primary.status,
            "message_count": db.query(TicketMessage)
            .filter(TicketMessage.ticket_id == primary.id)
            .count(),
        },
        "tickets_to_merge": [
            {
                "id": str(t.id),
                "subject": t.subject,
                "status": t.status,
            }
            for t in tickets_to_merge
        ],
        "merge_summary": {
            "messages_to_transfer": total_messages,
            "attachments_to_transfer": total_attachments,
            "tickets_to_close": len(tickets_to_merge),
        },
        "can_merge": len(tickets_to_merge) == len(merged_ticket_ids),
        "missing_ticket_ids": list(
            set(merged_ticket_ids) - set(str(t.id) for t in tickets_to_merge)
        ),
    }
