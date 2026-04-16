"""
Email Shadow Interceptor

Intercepts outbound emails and evaluates them through the shadow mode system.
If requires_hold, saves to email_shadow_queue for manager review.
If auto_execute, sends immediately and logs to undo queue.

BC-001: All operations scoped by company_id.
BC-008: Never crash the caller — defensive error handling.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB

from database.base import Base, SessionLocal
from app.interceptors.base_interceptor import ShadowInterceptor

logger = logging.getLogger("parwa.interceptors.email")


# ── Email Shadow Queue Model ──────────────────────────────────────

def _uuid() -> str:
    import uuid
    return str(uuid.uuid4())


class EmailShadowQueue(Base):
    """
    Queue for emails held in shadow mode pending manager approval.

    When an outbound email is intercepted and requires_hold is True,
    the email is saved here until a manager approves or rejects it.

    BC-001: company_id is required on every record.
    """
    __tablename__ = "email_shadow_queue"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Link to the shadow log entry
    shadow_log_id = Column(
        String(36),
        ForeignKey("shadow_log.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Email details
    to_address = Column(String(255), nullable=False)
    cc_addresses = Column(Text, nullable=True)  # JSON array as text
    bcc_addresses = Column(Text, nullable=True)  # JSON array as text
    subject = Column(String(500), nullable=False)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    # Additional metadata
    ticket_id = Column(String(36), ForeignKey("tickets.id"), nullable=True)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=True)
    attachments = Column(JSONB, nullable=True)  # List of attachment metadata
    # Status tracking
    status = Column(String(20), nullable=False, default="pending")
    # pending, approved, rejected, sent, failed
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    message_id = Column(String(255), nullable=True)  # Email provider message ID
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_email_shadow_queue_company_status", "company_id", "status"),
        Index("idx_email_shadow_queue_created", "created_at"),
    )


# ── Email Shadow Interceptor ───────────────────────────────────────

class EmailShadowInterceptor(ShadowInterceptor):
    """
    Interceptor for outbound emails in the shadow mode system.

    Evaluates outbound emails through the 4-layer risk evaluation system.
    Based on the result:
      - requires_hold=True: Save to email_shadow_queue, return pending status
      - auto_execute=True: Send email immediately, log to undo queue

    Usage:
        interceptor = EmailShadowInterceptor()
        result = interceptor.intercept_outbound_email(
            company_id="acme-uuid",
            email_data={
                "to": "customer@example.com",
                "subject": "Re: Your order",
                "body_text": "...",
                "ticket_id": "ticket-uuid",
            },
        )
        if result["status"] == "pending":
            # Email queued for approval
            notify_managers(result["shadow_log_id"])
        elif result["status"] == "sent":
            # Email sent immediately
            log_success(result["message_id"])
    """

    def intercept_outbound_email(
        self,
        company_id: str,
        email_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Intercept an outbound email and apply shadow mode evaluation.

        Args:
            company_id: Company UUID (BC-001).
            email_data: Dict with email details:
                - to: Recipient email address (required)
                - cc: List of CC addresses (optional)
                - bcc: List of BCC addresses (optional)
                - subject: Email subject (required)
                - body_text: Plain text body (optional)
                - body_html: HTML body (optional)
                - ticket_id: Related ticket ID (optional)
                - customer_id: Related customer ID (optional)
                - attachments: List of attachment metadata (optional)

        Returns:
            Dict with keys:
                - status: 'pending', 'sent', or 'error'
                - shadow_log_id: UUID of the shadow log entry
                - queue_id: UUID of email_shadow_queue entry (if pending)
                - message_id: Email provider message ID (if sent)
                - risk_score: Computed risk score
                - mode: Effective shadow mode
                - requires_hold: Whether email was held for approval

        BC-008: Never crashes - returns error status on failure.
        """
        try:
            # Validate required fields
            to_address = email_data.get("to")
            subject = email_data.get("subject")

            if not to_address or not subject:
                return {
                    "status": "error",
                    "error": "Missing required fields: 'to' and 'subject' are required",
                    "shadow_log_id": None,
                }

            # Step 1: Evaluate through shadow mode
            eval_result = self.evaluate_shadow(
                company_id=company_id,
                action_type="email_reply",
                payload=email_data,
            )

            shadow_log_id = eval_result.get("shadow_log_id")
            risk_score = eval_result.get("risk_score", 0.5)
            mode = eval_result.get("mode", "supervised")
            requires_hold = eval_result.get("requires_hold", True)
            auto_execute = eval_result.get("auto_execute", False)

            # Step 2: Handle based on evaluation result
            if requires_hold:
                # Save to email_shadow_queue for manager review
                queue_result = self._queue_email(
                    company_id=company_id,
                    shadow_log_id=shadow_log_id,
                    email_data=email_data,
                )

                logger.info(
                    "email_queued_for_approval company_id=%s to=%s log_id=%s queue_id=%s risk=%.2f",
                    company_id, to_address, shadow_log_id, queue_result.get("queue_id"), risk_score,
                )

                return {
                    "status": "pending",
                    "shadow_log_id": shadow_log_id,
                    "queue_id": queue_result.get("queue_id"),
                    "risk_score": risk_score,
                    "mode": mode,
                    "requires_hold": True,
                    "reason": eval_result.get("reason", "Email requires manager approval"),
                }

            else:
                # Auto-execute: send immediately
                send_result = self._send_email(
                    company_id=company_id,
                    email_data=email_data,
                )

                if send_result.get("success"):
                    # Log to undo queue
                    self._log_to_undo_queue(
                        company_id=company_id,
                        shadow_log_id=shadow_log_id,
                        action_type="email_reply",
                        action_data=email_data,
                    )

                    logger.info(
                        "email_auto_sent company_id=%s to=%s log_id=%s message_id=%s",
                        company_id, to_address, shadow_log_id, send_result.get("message_id"),
                    )

                    return {
                        "status": "sent",
                        "shadow_log_id": shadow_log_id,
                        "message_id": send_result.get("message_id"),
                        "risk_score": risk_score,
                        "mode": mode,
                        "requires_hold": False,
                        "auto_execute": auto_execute,
                    }
                else:
                    # Send failed - still return sent status but with error info
                    logger.error(
                        "email_auto_send_failed company_id=%s to=%s error=%s",
                        company_id, to_address, send_result.get("error"),
                    )

                    return {
                        "status": "error",
                        "shadow_log_id": shadow_log_id,
                        "error": send_result.get("error"),
                        "risk_score": risk_score,
                        "mode": mode,
                    }

        except Exception as e:
            # BC-008: Never crash the caller
            logger.error(
                "email_intercept_failed company_id=%s error=%s",
                company_id, str(e), exc_info=True,
            )

            return {
                "status": "error",
                "error": str(e),
                "shadow_log_id": None,
            }

    def _queue_email(
        self,
        company_id: str,
        shadow_log_id: str,
        email_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Save an email to the shadow queue for manager review.

        Args:
            company_id: Company UUID.
            shadow_log_id: The shadow log entry ID.
            email_data: The email data to queue.

        Returns:
            Dict with queue_id and status.
        """
        try:
            with SessionLocal() as db:
                import json

                queue_entry = EmailShadowQueue(
                    company_id=company_id,
                    shadow_log_id=shadow_log_id,
                    to_address=email_data.get("to"),
                    cc_addresses=json.dumps(email_data.get("cc", [])) if email_data.get("cc") else None,
                    bcc_addresses=json.dumps(email_data.get("bcc", [])) if email_data.get("bcc") else None,
                    subject=email_data.get("subject"),
                    body_text=email_data.get("body_text"),
                    body_html=email_data.get("body_html"),
                    ticket_id=email_data.get("ticket_id"),
                    customer_id=email_data.get("customer_id"),
                    attachments=email_data.get("attachments"),
                    status="pending",
                    created_at=datetime.utcnow(),
                )
                db.add(queue_entry)
                db.commit()
                db.refresh(queue_entry)

                return {
                    "queue_id": queue_entry.id,
                    "status": "queued",
                }

        except Exception as e:
            logger.error(
                "email_queue_save_failed company_id=%s log_id=%s error=%s",
                company_id, shadow_log_id, str(e), exc_info=True,
            )
            return {
                "queue_id": None,
                "status": "error",
                "error": str(e),
            }

    def _send_email(
        self,
        company_id: str,
        email_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send an email using the configured email service.

        This method delegates to the actual email sending service.
        In production, this would call the email provider API.

        Args:
            company_id: Company UUID.
            email_data: The email data to send.

        Returns:
            Dict with success status and message_id or error.
        """
        try:
            # Import email service lazily to avoid circular imports
            from app.services.email_service import EmailService

            email_service = EmailService()

            # Send the email
            result = email_service.send_email(
                to=email_data.get("to"),
                subject=email_data.get("subject"),
                body_text=email_data.get("body_text"),
                body_html=email_data.get("body_html"),
                cc=email_data.get("cc"),
                bcc=email_data.get("bcc"),
                attachments=email_data.get("attachments"),
                company_id=company_id,
            )

            return {
                "success": True,
                "message_id": result.get("message_id"),
            }

        except Exception as e:
            logger.error(
                "email_send_failed company_id=%s to=%s error=%s",
                company_id, email_data.get("to"), str(e), exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
            }

    def get_queued_emails(
        self,
        company_id: str,
        status: str = "pending",
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Get paginated list of queued emails for a company.

        Args:
            company_id: Company UUID (BC-001).
            status: Filter by status ('pending', 'approved', 'rejected', etc.)
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Dict with items, total, page info.
        """
        try:
            with SessionLocal() as db:
                query = db.query(EmailShadowQueue).filter(
                    EmailShadowQueue.company_id == company_id,
                    EmailShadowQueue.status == status,
                )

                total = query.count()

                offset = (page - 1) * page_size
                items = query.order_by(
                    EmailShadowQueue.created_at.desc()
                ).offset(offset).limit(page_size).all()

                return {
                    "items": [self._queue_entry_to_dict(item) for item in items],
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
                }

        except Exception as e:
            logger.error(
                "get_queued_emails_failed company_id=%s error=%s",
                company_id, str(e), exc_info=True,
            )
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "error": str(e),
            }

    def approve_queued_email(
        self,
        company_id: str,
        queue_id: str,
        manager_id: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Approve and send a queued email.

        Args:
            company_id: Company UUID (BC-001).
            queue_id: The email_shadow_queue entry ID.
            manager_id: UUID of the approving manager.
            note: Optional approval note.

        Returns:
            Dict with result including message_id if sent successfully.
        """
        try:
            with SessionLocal() as db:
                queue_entry = db.query(EmailShadowQueue).filter(
                    EmailShadowQueue.id == queue_id,
                    EmailShadowQueue.company_id == company_id,
                    EmailShadowQueue.status == "pending",
                ).first()

                if not queue_entry:
                    return {
                        "success": False,
                        "error": "Queued email not found or already processed",
                    }

                # Approve in shadow log
                approve_result = self.approve_queued_action(
                    company_id=company_id,
                    shadow_log_id=queue_entry.shadow_log_id,
                    manager_id=manager_id,
                    note=note,
                )

                # Send the email
                email_data = {
                    "to": queue_entry.to_address,
                    "subject": queue_entry.subject,
                    "body_text": queue_entry.body_text,
                    "body_html": queue_entry.body_html,
                    "ticket_id": queue_entry.ticket_id,
                    "customer_id": queue_entry.customer_id,
                    "attachments": queue_entry.attachments,
                }

                send_result = self._send_email(
                    company_id=company_id,
                    email_data=email_data,
                )

                if send_result.get("success"):
                    queue_entry.status = "sent"
                    queue_entry.approved_by = manager_id
                    queue_entry.approved_at = datetime.utcnow()
                    queue_entry.sent_at = datetime.utcnow()
                    queue_entry.message_id = send_result.get("message_id")
                else:
                    queue_entry.status = "failed"
                    queue_entry.error_message = send_result.get("error")

                db.commit()

                logger.info(
                    "queued_email_approved company_id=%s queue_id=%s manager=%s sent=%s",
                    company_id, queue_id, manager_id, send_result.get("success"),
                )

                return {
                    "success": send_result.get("success"),
                    "queue_id": queue_id,
                    "status": queue_entry.status,
                    "message_id": send_result.get("message_id"),
                    "error": send_result.get("error"),
                }

        except Exception as e:
            logger.error(
                "approve_queued_email_failed company_id=%s queue_id=%s error=%s",
                company_id, queue_id, str(e), exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
            }

    def reject_queued_email(
        self,
        company_id: str,
        queue_id: str,
        manager_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reject a queued email.

        Args:
            company_id: Company UUID (BC-001).
            queue_id: The email_shadow_queue entry ID.
            manager_id: UUID of the rejecting manager.
            reason: Optional rejection reason.

        Returns:
            Dict with result.
        """
        try:
            with SessionLocal() as db:
                queue_entry = db.query(EmailShadowQueue).filter(
                    EmailShadowQueue.id == queue_id,
                    EmailShadowQueue.company_id == company_id,
                    EmailShadowQueue.status == "pending",
                ).first()

                if not queue_entry:
                    return {
                        "success": False,
                        "error": "Queued email not found or already processed",
                    }

                # Reject in shadow log
                reject_result = self.reject_queued_action(
                    company_id=company_id,
                    shadow_log_id=queue_entry.shadow_log_id,
                    manager_id=manager_id,
                    note=reason,
                )

                # Update queue entry
                queue_entry.status = "rejected"
                queue_entry.approved_by = manager_id
                queue_entry.approved_at = datetime.utcnow()
                queue_entry.rejection_reason = reason

                db.commit()

                logger.info(
                    "queued_email_rejected company_id=%s queue_id=%s manager=%s",
                    company_id, queue_id, manager_id,
                )

                return {
                    "success": True,
                    "queue_id": queue_id,
                    "status": "rejected",
                }

        except Exception as e:
            logger.error(
                "reject_queued_email_failed company_id=%s queue_id=%s error=%s",
                company_id, queue_id, str(e), exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
            }

    def _queue_entry_to_dict(self, entry: EmailShadowQueue) -> Dict[str, Any]:
        """Convert a queue entry to a dictionary."""
        return {
            "id": entry.id,
            "company_id": entry.company_id,
            "shadow_log_id": entry.shadow_log_id,
            "to_address": entry.to_address,
            "subject": entry.subject,
            "ticket_id": entry.ticket_id,
            "customer_id": entry.customer_id,
            "status": entry.status,
            "approved_by": entry.approved_by,
            "approved_at": entry.approved_at.isoformat() if entry.approved_at else None,
            "rejection_reason": entry.rejection_reason,
            "sent_at": entry.sent_at.isoformat() if entry.sent_at else None,
            "message_id": entry.message_id,
            "error_message": entry.error_message,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
