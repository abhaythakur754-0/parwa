"""
Chat Shadow Interceptor

Intercepts outbound chat widget messages and evaluates them through the shadow mode system.
If requires_hold, saves to chat_shadow_queue for manager review.
If auto_execute, sends immediately and logs to undo queue.

BC-001: All operations scoped by company_id.
BC-008: Never crash the caller — defensive error handling.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from database.base import SessionLocal
from database.models.shadow_mode import ChatShadowQueue
from app.interceptors.base_interceptor import ShadowInterceptor

logger = logging.getLogger("parwa.interceptors.chat")


# ── Chat Shadow Interceptor ────────────────────────────────────────


class ChatShadowInterceptor(ShadowInterceptor):
    """
    Interceptor for outbound chat widget messages in the shadow mode system.

    Evaluates outbound chat messages through the 4-layer risk evaluation system.
    Based on the result:
      - requires_hold=True: Save to chat_shadow_queue, return pending status
      - auto_execute=True: Send message immediately, log to undo queue

    Usage:
        interceptor = ChatShadowInterceptor()
        result = interceptor.intercept_outbound_chat(
            company_id="acme-uuid",
            message_data={
                "session_id": "chat-session-123",
                "message": "Hello! How can I help you today?",
                "customer_id": "customer-uuid",
            },
        )
        if result["status"] == "pending":
            # Message queued for approval
            notify_managers(result["shadow_log_id"])
        elif result["status"] == "sent":
            # Message sent immediately
            log_success(result["message_uuid"])
    """

    def intercept_outbound_chat(
        self,
        company_id: str,
        message_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Intercept an outbound chat message and apply shadow mode evaluation.

        Args:
            company_id: Company UUID (BC-001).
            message_data: Dict with chat message details:
                - session_id: Chat session ID (required)
                - message: Message text (required)
                - conversation_id: Related conversation ID (optional)
                - message_type: Message type (optional, default 'text')
                - customer_id: Related customer ID (optional)
                - visitor_id: Visitor ID for anonymous users (optional)
                - attachments: List of attachments (optional)
                - quick_replies: Quick reply options (optional)
                - suggested_response: Original AI suggestion (optional)
                - confidence_score: AI confidence level (optional)

        Returns:
            Dict with keys:
                - status: 'pending', 'sent', or 'error'
                - shadow_log_id: UUID of the shadow log entry
                - queue_id: UUID of chat_shadow_queue entry (if pending)
                - message_uuid: Chat message UUID (if sent)
                - risk_score: Computed risk score
                - mode: Effective shadow mode
                - requires_hold: Whether message was held for approval

        BC-008: Never crashes - returns error status on failure.
        """
        try:
            # Validate required fields
            session_id = message_data.get("session_id")
            message = message_data.get("message")

            if not session_id or not message:
                return {
                    "status": "error",
                    "error": "Missing required fields: 'session_id' and 'message' are required",
                    "shadow_log_id": None,
                }

            # Step 1: Evaluate through shadow mode
            eval_result = self.evaluate_shadow(
                company_id=company_id,
                action_type="chat_reply",
                payload=message_data,
            )

            shadow_log_id = eval_result.get("shadow_log_id")
            risk_score = eval_result.get("risk_score", 0.5)
            mode = eval_result.get("mode", "supervised")
            requires_hold = eval_result.get("requires_hold", True)
            auto_execute = eval_result.get("auto_execute", False)

            # Step 2: Handle based on evaluation result
            if requires_hold:
                # Save to chat_shadow_queue for manager review
                queue_result = self._queue_chat_message(
                    company_id=company_id,
                    shadow_log_id=shadow_log_id,
                    message_data=message_data,
                )

                logger.info(
                    "chat_queued_for_approval company_id=%s session=%s log_id=%s queue_id=%s risk=%.2f",
                    company_id,
                    session_id,
                    shadow_log_id,
                    queue_result.get("queue_id"),
                    risk_score,
                )

                return {
                    "status": "pending",
                    "shadow_log_id": shadow_log_id,
                    "queue_id": queue_result.get("queue_id"),
                    "risk_score": risk_score,
                    "mode": mode,
                    "requires_hold": True,
                    "reason": eval_result.get(
                        "reason", "Chat message requires manager approval"
                    ),
                }

            else:
                # Auto-execute: send immediately
                send_result = self._send_chat_message(
                    company_id=company_id,
                    message_data=message_data,
                )

                if send_result.get("success"):
                    # Log to undo queue
                    self._log_to_undo_queue(
                        company_id=company_id,
                        shadow_log_id=shadow_log_id,
                        action_type="chat_reply",
                        action_data=message_data,
                    )

                    logger.info(
                        "chat_auto_sent company_id=%s session=%s log_id=%s uuid=%s",
                        company_id,
                        session_id,
                        shadow_log_id,
                        send_result.get("message_uuid"),
                    )

                    return {
                        "status": "sent",
                        "shadow_log_id": shadow_log_id,
                        "message_uuid": send_result.get("message_uuid"),
                        "risk_score": risk_score,
                        "mode": mode,
                        "requires_hold": False,
                        "auto_execute": auto_execute,
                    }
                else:
                    # Send failed
                    logger.error(
                        "chat_auto_send_failed company_id=%s session=%s error=%s",
                        company_id,
                        session_id,
                        send_result.get("error"),
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
                "chat_intercept_failed company_id=%s error=%s",
                company_id,
                str(e),
                exc_info=True,
            )

            return {
                "status": "error",
                "error": str(e),
                "shadow_log_id": None,
            }

    def _queue_chat_message(
        self,
        company_id: str,
        shadow_log_id: str,
        message_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Save a chat message to the shadow queue for manager review.

        Args:
            company_id: Company UUID.
            shadow_log_id: The shadow log entry ID.
            message_data: The message data to queue.

        Returns:
            Dict with queue_id and status.
        """
        try:
            with SessionLocal() as db:
                queue_entry = ChatShadowQueue(
                    company_id=company_id,
                    shadow_log_id=shadow_log_id,
                    session_id=message_data.get("session_id"),
                    conversation_id=message_data.get("conversation_id"),
                    message_text=message_data.get("message"),
                    message_type=message_data.get("message_type", "text"),
                    attachments=message_data.get("attachments"),
                    quick_replies=message_data.get("quick_replies"),
                    customer_id=message_data.get("customer_id"),
                    visitor_id=message_data.get("visitor_id"),
                    suggested_response=message_data.get("suggested_response"),
                    confidence_score=message_data.get("confidence_score"),
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
                "chat_queue_save_failed company_id=%s log_id=%s error=%s",
                company_id,
                shadow_log_id,
                str(e),
                exc_info=True,
            )
            return {
                "queue_id": None,
                "status": "error",
                "error": str(e),
            }

    def _send_chat_message(
        self,
        company_id: str,
        message_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send a chat message through the chat widget.

        This method delegates to the chat widget service to push
        the message to the connected client.

        Args:
            company_id: Company UUID.
            message_data: The message data to send.

        Returns:
            Dict with success status and message_uuid or error.
        """
        try:
            # Import chat service lazily to avoid circular imports
            from app.services.chat_widget_service import ChatWidgetService

            chat_service = ChatWidgetService()

            # Send the message
            result = chat_service.send_message(
                session_id=message_data.get("session_id"),
                message=message_data.get("message"),
                message_type=message_data.get("message_type", "text"),
                attachments=message_data.get("attachments"),
                quick_replies=message_data.get("quick_replies"),
                company_id=company_id,
            )

            return {
                "success": True,
                "message_uuid": result.get("uuid") or result.get("message_uuid"),
            }

        except Exception as e:
            logger.error(
                "chat_send_failed company_id=%s session=%s error=%s",
                company_id,
                message_data.get("session_id"),
                str(e),
                exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
            }

    def get_queued_messages(
        self,
        company_id: str,
        status: str = "pending",
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Get paginated list of queued chat messages for a company.

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
                query = db.query(ChatShadowQueue).filter(
                    ChatShadowQueue.company_id == company_id,
                    ChatShadowQueue.status == status,
                )

                total = query.count()

                offset = (page - 1) * page_size
                items = (
                    query.order_by(ChatShadowQueue.created_at.desc())
                    .offset(offset)
                    .limit(page_size)
                    .all()
                )

                return {
                    "items": [self._queue_entry_to_dict(item) for item in items],
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (
                        (total + page_size - 1) // page_size if page_size > 0 else 0
                    ),
                }

        except Exception as e:
            logger.error(
                "get_queued_chat_failed company_id=%s error=%s",
                company_id,
                str(e),
                exc_info=True,
            )
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "error": str(e),
            }

    def approve_queued_message(
        self,
        company_id: str,
        queue_id: str,
        manager_id: str,
        note: Optional[str] = None,
        edited_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Approve and send a queued chat message.

        Optionally, the manager can edit the message before sending.

        Args:
            company_id: Company UUID (BC-001).
            queue_id: The chat_shadow_queue entry ID.
            manager_id: UUID of the approving manager.
            note: Optional approval note.
            edited_message: Optional edited message text (if manager modified it).

        Returns:
            Dict with result including message_uuid if sent successfully.
        """
        try:
            with SessionLocal() as db:
                queue_entry = (
                    db.query(ChatShadowQueue)
                    .filter(
                        ChatShadowQueue.id == queue_id,
                        ChatShadowQueue.company_id == company_id,
                        ChatShadowQueue.status == "pending",
                    )
                    .first()
                )

                if not queue_entry:
                    return {
                        "success": False,
                        "error": "Queued chat message not found or already processed",
                    }

                # Approve in shadow log
                approve_result = self.approve_queued_action(
                    company_id=company_id,
                    shadow_log_id=queue_entry.shadow_log_id,
                    manager_id=manager_id,
                    note=note,
                )

                # Determine message to send
                message_to_send = edited_message or queue_entry.message_text

                # Track if message was edited
                was_edited = bool(
                    edited_message and edited_message != queue_entry.message_text
                )
                if was_edited:
                    queue_entry.was_edited = True
                    queue_entry.original_message = queue_entry.message_text
                    queue_entry.edited_message = edited_message

                # Send the message
                send_data = {
                    "session_id": queue_entry.session_id,
                    "message": message_to_send,
                    "conversation_id": queue_entry.conversation_id,
                    "message_type": queue_entry.message_type,
                    "attachments": queue_entry.attachments,
                    "quick_replies": queue_entry.quick_replies,
                    "customer_id": queue_entry.customer_id,
                    "visitor_id": queue_entry.visitor_id,
                }

                send_result = self._send_chat_message(
                    company_id=company_id,
                    message_data=send_data,
                )

                if send_result.get("success"):
                    queue_entry.status = "sent"
                    queue_entry.approved_by = manager_id
                    queue_entry.approved_at = datetime.utcnow()
                    queue_entry.sent_at = datetime.utcnow()
                    queue_entry.message_uuid = send_result.get("message_uuid")
                else:
                    queue_entry.status = "failed"
                    queue_entry.error_message = send_result.get("error")

                db.commit()

                logger.info(
                    "queued_chat_approved company_id=%s queue_id=%s manager=%s sent=%s edited=%s",
                    company_id,
                    queue_id,
                    manager_id,
                    send_result.get("success"),
                    was_edited,
                )

                return {
                    "success": send_result.get("success"),
                    "queue_id": queue_id,
                    "status": queue_entry.status,
                    "message_uuid": send_result.get("message_uuid"),
                    "was_edited": was_edited,
                    "error": send_result.get("error"),
                }

        except Exception as e:
            logger.error(
                "approve_queued_chat_failed company_id=%s queue_id=%s error=%s",
                company_id,
                queue_id,
                str(e),
                exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
            }

    def reject_queued_message(
        self,
        company_id: str,
        queue_id: str,
        manager_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reject a queued chat message.

        Args:
            company_id: Company UUID (BC-001).
            queue_id: The chat_shadow_queue entry ID.
            manager_id: UUID of the rejecting manager.
            reason: Optional rejection reason.

        Returns:
            Dict with result.
        """
        try:
            with SessionLocal() as db:
                queue_entry = (
                    db.query(ChatShadowQueue)
                    .filter(
                        ChatShadowQueue.id == queue_id,
                        ChatShadowQueue.company_id == company_id,
                        ChatShadowQueue.status == "pending",
                    )
                    .first()
                )

                if not queue_entry:
                    return {
                        "success": False,
                        "error": "Queued chat message not found or already processed",
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
                    "queued_chat_rejected company_id=%s queue_id=%s manager=%s",
                    company_id,
                    queue_id,
                    manager_id,
                )

                return {
                    "success": True,
                    "queue_id": queue_id,
                    "status": "rejected",
                }

        except Exception as e:
            logger.error(
                "reject_queued_chat_failed company_id=%s queue_id=%s error=%s",
                company_id,
                queue_id,
                str(e),
                exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
            }

    def _queue_entry_to_dict(self, entry: ChatShadowQueue) -> Dict[str, Any]:
        """Convert a queue entry to a dictionary."""
        return {
            "id": entry.id,
            "company_id": entry.company_id,
            "shadow_log_id": entry.shadow_log_id,
            "session_id": entry.session_id,
            "conversation_id": entry.conversation_id,
            "message_text": entry.message_text,
            "message_type": entry.message_type,
            "customer_id": entry.customer_id,
            "visitor_id": entry.visitor_id,
            "suggested_response": entry.suggested_response,
            "confidence_score": entry.confidence_score,
            "status": entry.status,
            "approved_by": entry.approved_by,
            "approved_at": entry.approved_at.isoformat() if entry.approved_at else None,
            "rejection_reason": entry.rejection_reason,
            "sent_at": entry.sent_at.isoformat() if entry.sent_at else None,
            "message_uuid": entry.message_uuid,
            "error_message": entry.error_message,
            "was_edited": entry.was_edited,
            "original_message": entry.original_message,
            "edited_message": entry.edited_message,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
