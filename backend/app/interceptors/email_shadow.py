"""
Email Shadow Interceptor

Intercepts outbound emails and evaluates them against the shadow mode
4-layer decision system before sending.

Day 2 Implementation - Channel Interceptors
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from database.base import SessionLocal
from database.models.shadow_mode import ShadowLog

logger = logging.getLogger("parwa.interceptors.email_shadow")


@dataclass
class EmailShadowResult:
    """Result of email shadow evaluation."""

    requires_approval: bool
    auto_execute: bool
    mode: str
    risk_score: float
    reason: str
    shadow_log_id: Optional[str] = None
    layers: Optional[Dict[str, Any]] = None

    # Additional context
    company_mode: str = "supervised"
    stage_0: bool = False
    shadow_actions_remaining: Optional[int] = None


def evaluate_email_shadow(
    company_id: str,
    email_payload: Dict[str, Any],
    shadow_service=None,
) -> EmailShadowResult:
    """
    Evaluate an outbound email against shadow mode rules.

    Args:
        company_id: Company UUID (BC-001).
        email_payload: Dict with email details:
            - to: Recipient email address
            - subject: Email subject
            - body: Email body content
            - from_address: Sender email address
            - reply_to: Optional reply-to address
            - attachments: Optional list of attachment info
            - template_id: Optional template ID if using templates
        shadow_service: Optional ShadowModeService instance (created if not provided)

    Returns:
        EmailShadowResult with evaluation outcome.

    When auto_execute=True, the email is sent immediately and logged
    to the undo queue for potential reversal.
    """
    try:
        # Lazy import to avoid circular dependencies
        from app.interceptors.base_interceptor import ShadowInterceptor
        from app.services.shadow_mode_service import ShadowModeService

        service = shadow_service or ShadowModeService()
        interceptor = ShadowInterceptor()

        # Evaluate using the 4-layer system
        evaluation = service.evaluate_action_risk(
            company_id=company_id,
            action_type="email_reply",
            action_payload=email_payload,
        )

        auto_execute = evaluation.get("auto_execute", False)
        requires_approval = evaluation.get("requires_approval", True)
        risk_score = evaluation.get("risk_score", 0.5)
        mode = evaluation.get("mode", "supervised")

        # Always log the action to shadow_log for audit trail
        log_entry = service.log_shadow_action(
            company_id=company_id,
            action_type="email_reply",
            action_payload=email_payload,
            risk_score=risk_score,
            mode=mode,
        )
        shadow_log_id = log_entry.get("id")

        # Auto-execute: send the email immediately
        if auto_execute and not requires_approval:
            _execute_email_action(
                company_id=company_id,
                email_payload=email_payload,
                shadow_log_id=shadow_log_id,
            )
            # Log to undo queue for potential reversal
            interceptor._log_to_undo_queue(
                company_id=company_id,
                shadow_log_id=shadow_log_id,
                action_type="email_reply",
                action_data=email_payload,
            )
            logger.info(
                "email_auto_executed company_id=%s log_id=%s risk=%.2f",
                company_id,
                shadow_log_id,
                risk_score,
            )

        return EmailShadowResult(
            requires_approval=requires_approval,
            auto_execute=auto_execute,
            mode=mode,
            risk_score=risk_score,
            reason=evaluation.get("reason", ""),
            shadow_log_id=shadow_log_id,
            layers=evaluation.get("layers"),
            company_mode=evaluation.get("company_mode", "supervised"),
            stage_0=evaluation.get("stage_0", False),
            shadow_actions_remaining=evaluation.get("shadow_actions_remaining"),
        )

    except Exception as e:
        logger.error(
            "email_shadow_evaluation_failed company_id=%s error=%s",
            company_id,
            str(e),
            exc_info=True,
        )
        # Safe fallback: always require approval
        return EmailShadowResult(
            requires_approval=True,
            auto_execute=False,
            mode="supervised",
            risk_score=0.5,
            reason=f"Evaluation failed: {str(e)}",
        )


def _execute_email_action(
    company_id: str,
    email_payload: Dict[str, Any],
    shadow_log_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute an email send action that was auto-approved.

    Delegates to the email service for actual sending.

    Args:
        company_id: Company UUID (BC-001).
        email_payload: Dict with email details.
        shadow_log_id: Optional shadow log ID for audit trail.

    Returns:
        Dict with execution result.
    """
    try:
        from app.services.email_service import EmailService

        email_service = EmailService()

        result = email_service.send_email(
            to=email_payload.get("to"),
            subject=email_payload.get("subject"),
            body=email_payload.get("body"),
            from_address=email_payload.get("from_address"),
            reply_to=email_payload.get("reply_to"),
            company_id=company_id,
        )

        logger.info(
            "email_executed company_id=%s to=%s shadow_id=%s",
            company_id,
            email_payload.get("to"),
            shadow_log_id,
        )

        return {
            "status": "sent",
            "shadow_log_id": shadow_log_id,
            "email_result": result,
            "sent_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(
            "email_execution_failed company_id=%s shadow_id=%s error=%s",
            company_id,
            shadow_log_id,
            str(e),
            exc_info=True,
        )
        return {
            "status": "error",
            "shadow_log_id": shadow_log_id,
            "error": str(e),
        }


def process_email_after_approval(
    company_id: str,
    shadow_log_id: str,
    email_service=None,
) -> Dict[str, Any]:
    """
    Process an email that was held in shadow queue after approval.

    This should be called when a manager approves an email action
    from the shadow queue.

    Args:
        company_id: Company UUID (BC-001).
        shadow_log_id: Shadow log entry UUID.
        email_service: Optional email service instance.

    Returns:
        Dict with processing result.
    """
    try:
        pass

        with SessionLocal() as db:
            # Get the shadow log entry
            shadow_entry = (
                db.query(ShadowLog)
                .filter(
                    ShadowLog.id == shadow_log_id,
                    ShadowLog.company_id == company_id,
                )
                .first()
            )

            if not shadow_entry:
                return {
                    "status": "error",
                    "error": "Shadow log entry not found",
                }

            email_payload = shadow_entry.action_payload or {}

            # Here you would integrate with your email sending service
            # For now, we return the payload for the caller to process
            logger.info(
                "email_shadow_approved shadow_id=%s company_id=%s",
                shadow_log_id,
                company_id,
            )

            return {
                "status": "ready_to_send",
                "shadow_log_id": shadow_log_id,
                "email_payload": email_payload,
                "approved_at": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(
            "email_shadow_approval_processing_failed shadow_id=%s error=%s",
            shadow_log_id,
            str(e),
            exc_info=True,
        )
        return {
            "status": "error",
            "error": str(e),
        }
