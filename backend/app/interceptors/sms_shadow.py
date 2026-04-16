"""
SMS Shadow Interceptor

Intercepts outbound SMS messages and evaluates them through the shadow mode system.
If requires_hold, saves to sms_shadow_queue for manager review.
If auto_execute, sends immediately and logs to undo queue.

BC-001: All operations scoped by company_id.
BC-008: Never crash the caller — defensive error handling.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB

from database.base import Base, SessionLocal
from app.interceptors.base_interceptor import ShadowInterceptor

logger = logging.getLogger("parwa.interceptors.sms")


# ── SMS Shadow Queue Model ─────────────────────────────────────────

def _uuid() -> str:
    import uuid
    return str(uuid.uuid4())


class SMSShadowQueue(Base):
    """
    Queue for SMS messages held in shadow mode pending manager approval.

    When an outbound SMS is intercepted and requires_hold is True,
    the message is saved here until a manager approves or rejects it.

    BC-001: company_id is required on every record.
    """
    __tablename__ = "sms_shadow_queue"

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
    # SMS details
    to_number = Column(String(20), nullable=False)
    from_number = Column(String(20), nullable=True)
    message = Column(Text, nullable=False)
    # Additional metadata
    ticket_id = Column(String(36), ForeignKey("tickets.id"), nullable=True)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=True)
    media_urls = Column(JSONB, nullable=True)  # List of MMS media URLs
    # Status tracking
    status = Column(String(20), nullable=False, default="pending")
    # pending, approved, rejected, sent, failed
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    message_sid = Column(String(100), nullable=True)  # Twilio message SID
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
        Index("idx_sms_shadow_queue_company_status", "company_id", "status"),
        Index("idx_sms_shadow_queue_created", "created_at"),
    )


# ── SMS Shadow Interceptor ─────────────────────────────────────────

class SMSShadowInterceptor(ShadowInterceptor):
    """
    Interceptor for outbound SMS messages in the shadow mode system.

    Evaluates outbound SMS through the 4-layer risk evaluation system.
    Based on the result:
      - requires_hold=True: Save to sms_shadow_queue, return pending status
      - auto_execute=True: Send SMS immediately, log to undo queue

    Usage:
        interceptor = SMSShadowInterceptor()
        result = interceptor.intercept_outbound_sms(
            company_id="acme-uuid",
            sms_data={
                "to": "+1234567890",
                "message": "Your order has shipped!",
                "ticket_id": "ticket-uuid",
            },
        )
        if result["status"] == "pending":
            # SMS queued for approval
            notify_managers(result["shadow_log_id"])
        elif result["status"] == "sent":
            # SMS sent immediately
            log_success(result["message_sid"])
    """

    def intercept_outbound_sms(
        self,
        company_id: str,
        sms_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Intercept an outbound SMS and apply shadow mode evaluation.

        Args:
            company_id: Company UUID (BC-001).
            sms_data: Dict with SMS details:
                - to: Recipient phone number (required)
                - from_number: Sender phone number (optional)
                - message: SMS message body (required)
                - ticket_id: Related ticket ID (optional)
                - customer_id: Related customer ID (optional)
                - media_urls: List of MMS media URLs (optional)

        Returns:
            Dict with keys:
                - status: 'pending', 'sent', or 'error'
                - shadow_log_id: UUID of the shadow log entry
                - queue_id: UUID of sms_shadow_queue entry (if pending)
                - message_sid: SMS provider message SID (if sent)
                - risk_score: Computed risk score
                - mode: Effective shadow mode
                - requires_hold: Whether SMS was held for approval

        BC-008: Never crashes - returns error status on failure.
        """
        try:
            # Validate required fields
            to_number = sms_data.get("to")
            message = sms_data.get("message")

            if not to_number or not message:
                return {
                    "status": "error",
                    "error": "Missing required fields: 'to' and 'message' are required",
                    "shadow_log_id": None,
                }

            # Step 1: Evaluate through shadow mode
            eval_result = self.evaluate_shadow(
                company_id=company_id,
                action_type="sms_reply",
                payload=sms_data,
            )

            shadow_log_id = eval_result.get("shadow_log_id")
            risk_score = eval_result.get("risk_score", 0.5)
            mode = eval_result.get("mode", "supervised")
            requires_hold = eval_result.get("requires_hold", True)
            auto_execute = eval_result.get("auto_execute", False)

            # Step 2: Handle based on evaluation result
            if requires_hold:
                # Save to sms_shadow_queue for manager review
                queue_result = self._queue_sms(
                    company_id=company_id,
                    shadow_log_id=shadow_log_id,
                    sms_data=sms_data,
                )

                logger.info(
                    "sms_queued_for_approval company_id=%s to=%s log_id=%s queue_id=%s risk=%.2f",
                    company_id, to_number, shadow_log_id, queue_result.get("queue_id"), risk_score,
                )

                return {
                    "status": "pending",
                    "shadow_log_id": shadow_log_id,
                    "queue_id": queue_result.get("queue_id"),
                    "risk_score": risk_score,
                    "mode": mode,
                    "requires_hold": True,
                    "reason": eval_result.get("reason", "SMS requires manager approval"),
                }

            else:
                # Auto-execute: send immediately
                send_result = self._send_sms(
                    company_id=company_id,
                    sms_data=sms_data,
                )

                if send_result.get("success"):
                    # Log to undo queue
                    self._log_to_undo_queue(
                        company_id=company_id,
                        shadow_log_id=shadow_log_id,
                        action_type="sms_reply",
                        action_data=sms_data,
                    )

                    logger.info(
                        "sms_auto_sent company_id=%s to=%s log_id=%s sid=%s",
                        company_id, to_number, shadow_log_id, send_result.get("message_sid"),
                    )

                    return {
                        "status": "sent",
                        "shadow_log_id": shadow_log_id,
                        "message_sid": send_result.get("message_sid"),
                        "risk_score": risk_score,
                        "mode": mode,
                        "requires_hold": False,
                        "auto_execute": auto_execute,
                    }
                else:
                    # Send failed
                    logger.error(
                        "sms_auto_send_failed company_id=%s to=%s error=%s",
                        company_id, to_number, send_result.get("error"),
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
                "sms_intercept_failed company_id=%s error=%s",
                company_id, str(e), exc_info=True,
            )

            return {
                "status": "error",
                "error": str(e),
                "shadow_log_id": None,
            }

    def _queue_sms(
        self,
        company_id: str,
        shadow_log_id: str,
        sms_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Save an SMS to the shadow queue for manager review.

        Args:
            company_id: Company UUID.
            shadow_log_id: The shadow log entry ID.
            sms_data: The SMS data to queue.

        Returns:
            Dict with queue_id and status.
        """
        try:
            with SessionLocal() as db:
                queue_entry = SMSShadowQueue(
                    company_id=company_id,
                    shadow_log_id=shadow_log_id,
                    to_number=sms_data.get("to"),
                    from_number=sms_data.get("from_number"),
                    message=sms_data.get("message"),
                    ticket_id=sms_data.get("ticket_id"),
                    customer_id=sms_data.get("customer_id"),
                    media_urls=sms_data.get("media_urls"),
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
                "sms_queue_save_failed company_id=%s log_id=%s error=%s",
                company_id, shadow_log_id, str(e), exc_info=True,
            )
            return {
                "queue_id": None,
                "status": "error",
                "error": str(e),
            }

    def _send_sms(
        self,
        company_id: str,
        sms_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send an SMS using the configured SMS provider.

        This method delegates to the actual SMS sending service.
        In production, this would call Twilio or similar provider.

        Args:
            company_id: Company UUID.
            sms_data: The SMS data to send.

        Returns:
            Dict with success status and message_sid or error.
        """
        try:
            # Import SMS service lazily to avoid circular imports
            from app.services.sms_channel_service import SMSChannelService

            sms_service = SMSChannelService()

            # Send the SMS
            result = sms_service.send_sms(
                to=sms_data.get("to"),
                body=sms_data.get("message"),
                from_number=sms_data.get("from_number"),
                media_urls=sms_data.get("media_urls"),
                company_id=company_id,
            )

            return {
                "success": True,
                "message_sid": result.get("sid") or result.get("message_sid"),
            }

        except Exception as e:
            logger.error(
                "sms_send_failed company_id=%s to=%s error=%s",
                company_id, sms_data.get("to"), str(e), exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
            }

    def get_queued_sms(
        self,
        company_id: str,
        status: str = "pending",
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Get paginated list of queued SMS for a company.

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
                query = db.query(SMSShadowQueue).filter(
                    SMSShadowQueue.company_id == company_id,
                    SMSShadowQueue.status == status,
                )

                total = query.count()

                offset = (page - 1) * page_size
                items = query.order_by(
                    SMSShadowQueue.created_at.desc()
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
                "get_queued_sms_failed company_id=%s error=%s",
                company_id, str(e), exc_info=True,
            )
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "error": str(e),
            }

    def approve_queued_sms(
        self,
        company_id: str,
        queue_id: str,
        manager_id: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Approve and send a queued SMS.

        Args:
            company_id: Company UUID (BC-001).
            queue_id: The sms_shadow_queue entry ID.
            manager_id: UUID of the approving manager.
            note: Optional approval note.

        Returns:
            Dict with result including message_sid if sent successfully.
        """
        try:
            with SessionLocal() as db:
                queue_entry = db.query(SMSShadowQueue).filter(
                    SMSShadowQueue.id == queue_id,
                    SMSShadowQueue.company_id == company_id,
                    SMSShadowQueue.status == "pending",
                ).first()

                if not queue_entry:
                    return {
                        "success": False,
                        "error": "Queued SMS not found or already processed",
                    }

                # Approve in shadow log
                approve_result = self.approve_queued_action(
                    company_id=company_id,
                    shadow_log_id=queue_entry.shadow_log_id,
                    manager_id=manager_id,
                    note=note,
                )

                # Send the SMS
                sms_data = {
                    "to": queue_entry.to_number,
                    "from_number": queue_entry.from_number,
                    "message": queue_entry.message,
                    "ticket_id": queue_entry.ticket_id,
                    "customer_id": queue_entry.customer_id,
                    "media_urls": queue_entry.media_urls,
                }

                send_result = self._send_sms(
                    company_id=company_id,
                    sms_data=sms_data,
                )

                if send_result.get("success"):
                    queue_entry.status = "sent"
                    queue_entry.approved_by = manager_id
                    queue_entry.approved_at = datetime.utcnow()
                    queue_entry.sent_at = datetime.utcnow()
                    queue_entry.message_sid = send_result.get("message_sid")
                else:
                    queue_entry.status = "failed"
                    queue_entry.error_message = send_result.get("error")

                db.commit()

                logger.info(
                    "queued_sms_approved company_id=%s queue_id=%s manager=%s sent=%s",
                    company_id, queue_id, manager_id, send_result.get("success"),
                )

                return {
                    "success": send_result.get("success"),
                    "queue_id": queue_id,
                    "status": queue_entry.status,
                    "message_sid": send_result.get("message_sid"),
                    "error": send_result.get("error"),
                }

        except Exception as e:
            logger.error(
                "approve_queued_sms_failed company_id=%s queue_id=%s error=%s",
                company_id, queue_id, str(e), exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
            }

    def reject_queued_sms(
        self,
        company_id: str,
        queue_id: str,
        manager_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reject a queued SMS.

        Args:
            company_id: Company UUID (BC-001).
            queue_id: The sms_shadow_queue entry ID.
            manager_id: UUID of the rejecting manager.
            reason: Optional rejection reason.

        Returns:
            Dict with result.
        """
        try:
            with SessionLocal() as db:
                queue_entry = db.query(SMSShadowQueue).filter(
                    SMSShadowQueue.id == queue_id,
                    SMSShadowQueue.company_id == company_id,
                    SMSShadowQueue.status == "pending",
                ).first()

                if not queue_entry:
                    return {
                        "success": False,
                        "error": "Queued SMS not found or already processed",
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
                    "queued_sms_rejected company_id=%s queue_id=%s manager=%s",
                    company_id, queue_id, manager_id,
                )

                return {
                    "success": True,
                    "queue_id": queue_id,
                    "status": "rejected",
                }

        except Exception as e:
            logger.error(
                "reject_queued_sms_failed company_id=%s queue_id=%s error=%s",
                company_id, queue_id, str(e), exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
            }

    def _queue_entry_to_dict(self, entry: SMSShadowQueue) -> Dict[str, Any]:
        """Convert a queue entry to a dictionary."""
        return {
            "id": entry.id,
            "company_id": entry.company_id,
            "shadow_log_id": entry.shadow_log_id,
            "to_number": entry.to_number,
            "from_number": entry.from_number,
            "message": entry.message,
            "ticket_id": entry.ticket_id,
            "customer_id": entry.customer_id,
            "status": entry.status,
            "approved_by": entry.approved_by,
            "approved_at": entry.approved_at.isoformat() if entry.approved_at else None,
            "rejection_reason": entry.rejection_reason,
            "sent_at": entry.sent_at.isoformat() if entry.sent_at else None,
            "message_sid": entry.message_sid,
            "error_message": entry.error_message,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
