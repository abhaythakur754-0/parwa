"""
Base Shadow Interceptor

Base class for all channel-specific shadow mode interceptors.
Provides the core evaluate_shadow() method that uses ShadowModeService
for risk evaluation and logs to the shadow_log table.

BC-001: All operations scoped by company_id.
BC-008: Never crash the caller — defensive error handling.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from database.base import SessionLocal
from database.models.shadow_mode import ShadowLog

logger = logging.getLogger("parwa.interceptors.base")


class ShadowInterceptor:
    """
    Base class for channel-specific shadow mode interceptors.

    Provides the core evaluation logic that determines whether an action
    should be held for approval (shadow/supervised) or auto-executed (graduated).

    Subclasses should implement channel-specific intercept methods that call
    evaluate_shadow() and then handle the result appropriately.

    Usage:
        class EmailShadowInterceptor(ShadowInterceptor):
            def intercept_outbound_email(self, company_id, email_data):
                result = self.evaluate_shadow(
                    company_id=company_id,
                    action_type="email_reply",
                    payload=email_data,
                )
                if result["requires_hold"]:
                    # Save to shadow queue, return pending
                    ...
                else:
                    # Execute immediately, log to undo queue
                    ...
    """

    def __init__(self):
        """Initialize the interceptor with a ShadowModeService instance."""
        # Lazy import to avoid circular dependencies
        from app.services.shadow_mode_service import ShadowModeService
        self._shadow_service = ShadowModeService()

    def evaluate_shadow(
        self,
        company_id: str,
        action_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate whether an action requires shadow mode hold.

        Uses the ShadowModeService's 4-layer decision system:
          Layer 1: Heuristic risk scoring based on action type and payload
          Layer 2: Per-category preferences (shadow/supervised/graduated)
          Layer 3: Historical pattern analysis (avg risk scores)
          Layer 4: Hard safety floor (certain actions always require approval)

        Args:
            company_id: Company UUID (BC-001).
            action_type: Type of action (e.g., 'email_reply', 'sms_reply').
            payload: The action payload for risk evaluation.

        Returns:
            Dict with keys:
                - requires_hold: bool - True if action should be held for approval
                - risk_score: float - Computed risk score (0.0-1.0)
                - mode: str - Effective mode ('shadow', 'supervised', 'graduated')
                - shadow_log_id: str - UUID of the created shadow log entry
                - auto_execute: bool - True if action can execute immediately
                - reason: str - Human-readable explanation

        BC-008: Never crashes the caller - returns safe defaults on error.
        """
        try:
            # Step 1: Evaluate risk using ShadowModeService
            eval_result = self._shadow_service.evaluate_action_risk(
                company_id=company_id,
                action_type=action_type,
                action_payload=payload,
            )

            risk_score = eval_result.get("risk_score", 0.5)
            mode = eval_result.get("mode", "supervised")
            requires_approval = eval_result.get("requires_approval", True)
            auto_execute = eval_result.get("auto_execute", False)

            # Step 2: Log the action to shadow_log
            log_result = self._shadow_service.log_shadow_action(
                company_id=company_id,
                action_type=action_type,
                action_payload=payload,
                risk_score=risk_score,
                mode=mode,
            )

            shadow_log_id = log_result.get("id")

            # Step 3: Determine if hold is required
            requires_hold = requires_approval and not auto_execute

            logger.info(
                "shadow_evaluated company_id=%s action=%s mode=%s risk=%.2f hold=%s log_id=%s",
                company_id, action_type, mode, risk_score, requires_hold, shadow_log_id,
            )

            return {
                "requires_hold": requires_hold,
                "risk_score": risk_score,
                "mode": mode,
                "shadow_log_id": shadow_log_id,
                "auto_execute": auto_execute,
                "reason": eval_result.get("reason", ""),
                "evaluation": eval_result,
            }

        except Exception as e:
            # BC-008: Never crash the caller - return safe defaults
            logger.error(
                "shadow_evaluation_failed company_id=%s action=%s error=%s",
                company_id, action_type, str(e), exc_info=True,
            )

            # Create a fallback log entry
            shadow_log_id = self._create_fallback_log(
                company_id=company_id,
                action_type=action_type,
                payload=payload,
                error=str(e),
            )

            return {
                "requires_hold": True,  # Safe default: require approval
                "risk_score": 0.5,
                "mode": "supervised",
                "shadow_log_id": shadow_log_id,
                "auto_execute": False,
                "reason": f"Evaluation failed: {str(e)}",
                "error": str(e),
            }

    def _create_fallback_log(
        self,
        company_id: str,
        action_type: str,
        payload: Dict[str, Any],
        error: str,
    ) -> Optional[str]:
        """
        Create a fallback shadow log entry when evaluation fails.

        This ensures we always have an audit trail, even on errors.

        Args:
            company_id: Company UUID.
            action_type: Type of action.
            payload: The action payload.
            error: Error message from the failed evaluation.

        Returns:
            The shadow log ID or None if logging also failed.
        """
        try:
            with SessionLocal() as db:
                entry = ShadowLog(
                    company_id=company_id,
                    action_type=action_type,
                    action_payload={"original": payload, "error": error},
                    jarvis_risk_score=0.5,
                    mode="supervised",
                    created_at=datetime.utcnow(),
                )
                db.add(entry)
                db.commit()
                db.refresh(entry)
                return entry.id
        except Exception as log_error:
            logger.error(
                "fallback_log_failed company_id=%s action=%s error=%s",
                company_id, action_type, str(log_error),
            )
            return None

    def _log_to_undo_queue(
        self,
        company_id: str,
        shadow_log_id: str,
        action_type: str,
        action_data: Dict[str, Any],
    ) -> Optional[str]:
        """
        Log an executed action to the undo queue for potential reversal.

        Called when an action is auto-executed (graduated mode) to enable
        managers to undo it if needed.

        Args:
            company_id: Company UUID.
            shadow_log_id: The shadow log entry ID.
            action_type: Type of action executed.
            action_data: The data that was executed.

        Returns:
            The executed action ID or None on error.
        """
        try:
            from database.models.approval import ExecutedAction, UndoLog

            with SessionLocal() as db:
                # Create executed action record
                executed = ExecutedAction(
                    company_id=company_id,
                    action_type=action_type,
                    action_data=str(action_data),
                    created_at=datetime.utcnow(),
                )
                db.add(executed)
                db.flush()

                # Create undo log entry (empty undo_data, to be filled if undone)
                undo_log = UndoLog(
                    company_id=company_id,
                    executed_action_id=executed.id,
                    undo_type="reversal",
                    original_data=str(action_data),
                    undo_data=None,
                    undo_reason=None,
                    undone_by=None,
                    created_at=datetime.utcnow(),
                )
                db.add(undo_log)
                db.commit()

                logger.info(
                    "undo_log_created company_id=%s action=%s executed_id=%s",
                    company_id, action_type, executed.id,
                )

                return executed.id

        except Exception as e:
            logger.error(
                "undo_log_failed company_id=%s action=%s error=%s",
                company_id, action_type, str(e), exc_info=True,
            )
            return None

    def approve_queued_action(
        self,
        company_id: str,
        shadow_log_id: str,
        manager_id: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Approve a queued action that was held for review.

        Args:
            company_id: Company UUID (BC-001).
            shadow_log_id: The shadow log entry ID.
            manager_id: UUID of the approving manager.
            note: Optional approval note.

        Returns:
            Dict with approval result and queued action data.
        """
        try:
            result = self._shadow_service.approve_shadow_action(
                shadow_log_id=shadow_log_id,
                manager_id=manager_id,
                note=note,
            )
            logger.info(
                "queued_action_approved company_id=%s log_id=%s manager=%s",
                company_id, shadow_log_id, manager_id,
            )
            return result
        except Exception as e:
            logger.error(
                "approve_queued_failed company_id=%s log_id=%s error=%s",
                company_id, shadow_log_id, str(e), exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
            }

    def reject_queued_action(
        self,
        company_id: str,
        shadow_log_id: str,
        manager_id: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reject a queued action that was held for review.

        Args:
            company_id: Company UUID (BC-001).
            shadow_log_id: The shadow log entry ID.
            manager_id: UUID of the rejecting manager.
            note: Optional rejection reason.

        Returns:
            Dict with rejection result.
        """
        try:
            result = self._shadow_service.reject_shadow_action(
                shadow_log_id=shadow_log_id,
                manager_id=manager_id,
                note=note,
            )
            logger.info(
                "queued_action_rejected company_id=%s log_id=%s manager=%s",
                company_id, shadow_log_id, manager_id,
            )
            return result
        except Exception as e:
            logger.error(
                "reject_queued_failed company_id=%s log_id=%s error=%s",
                company_id, shadow_log_id, str(e), exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
            }
