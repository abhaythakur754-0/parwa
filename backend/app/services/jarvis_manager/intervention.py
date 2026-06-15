"""
Jarvis Intervention — When Jarvis needs to ACT, not just observe.

Intervention types:
  1. AUTO_FIX: Jarvis automatically fixes a variant's response
  2. RE_GENERATE: Jarvis triggers re-generation with better context
  3. ASK_CLIENT: Jarvis asks the client for clarification
  4. ESCALATE: Jarvis escalates to a human agent
  5. NOTIFY: Jarvis sends a notification to the client
  6. REDIRECT: Jarvis redirects the ticket to a different variant
  7. APPROVE: Jarvis approves an action that needs approval

OpenClaw-inspired: Jarvis doesn't just observe, it ACTS.
When it sees a problem, it fixes it. When it's unsure, it asks.
When it can't handle it, it escalates. But it never just sits there.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger
from app.core.unified_variant.permission_config import (
    get_permission_config,
    VariantTier,
    needs_approval,
)

logger = get_logger("jarvis_intervention")


class InterventionType:
    """Types of interventions Jarvis can perform."""
    AUTO_FIX = "auto_fix"
    RE_GENERATE = "re_generate"
    ASK_CLIENT = "ask_client"
    ESCALATE = "escalate"
    NOTIFY = "notify"
    REDIRECT = "redirect"
    APPROVE = "approve"


class InterventionResult:
    """Result of a Jarvis intervention."""

    def __init__(
        self,
        intervention_type: str,
        success: bool,
        company_id: str,
        ticket_id: str = "",
        details: Dict[str, Any] = None,
    ):
        self.intervention_type = intervention_type
        self.success = success
        self.company_id = company_id
        self.ticket_id = ticket_id
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intervention_type": self.intervention_type,
            "success": self.success,
            "company_id": self.company_id,
            "ticket_id": self.ticket_id,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class JarvisIntervention:
    """Jarvis's action engine — when monitoring detects issues, this acts.

    This is the "hands" of Jarvis. The monitor detects problems,
    the intervention engine fixes them.

    Usage:
        intervention = JarvisIntervention(company_id="comp_123")

        # When monitor detects a low-confidence response
        result = intervention.handle_low_confidence(pipeline_result)

        # When monitor detects a quality failure
        result = intervention.handle_quality_failure(pipeline_result)

        # When variant needs client input
        result = intervention.handle_ask_client(pipeline_result)
    """

    def __init__(self, company_id: str):
        self.company_id = company_id
        self._interventions: List[InterventionResult] = []

    def handle_low_confidence(
        self,
        pipeline_result: Dict[str, Any],
    ) -> InterventionResult:
        """Handle a low-confidence response from a variant.

        Strategy:
          1. If confidence < 0.3 → escalate to human
          2. If 0.3-0.5 → ask client for clarification
          3. If 0.5-0.7 → re-generate with better context
          4. If 0.7+ → auto-fix and approve
        """
        ticket_id = pipeline_result.get("ticket_id", "")
        confidence = pipeline_result.get("confidence_score", 0.0)
        variant_tier = pipeline_result.get("variant_tier", "")

        try:
            if confidence < 0.3:
                # Critical low confidence → escalate
                result = InterventionResult(
                    intervention_type=InterventionType.ESCALATE,
                    success=True,
                    company_id=self.company_id,
                    ticket_id=ticket_id,
                    details={
                        "reason": f"Very low confidence ({confidence:.2f})",
                        "original_response": pipeline_result.get("agent_response", "")[:200],
                        "variant_tier": variant_tier,
                    },
                )
            elif confidence < 0.5:
                # Ask client for clarification
                result = InterventionResult(
                    intervention_type=InterventionType.ASK_CLIENT,
                    success=True,
                    company_id=self.company_id,
                    ticket_id=ticket_id,
                    details={
                        "question": self._generate_ask_question(pipeline_result),
                        "options": ["Approve response", "I need different approach", "Connect me to a human"],
                        "confidence": confidence,
                        "variant_tier": variant_tier,
                    },
                )
            elif confidence < 0.7:
                # Re-generate with better context
                result = InterventionResult(
                    intervention_type=InterventionType.RE_GENERATE,
                    success=True,
                    company_id=self.company_id,
                    ticket_id=ticket_id,
                    details={
                        "reason": f"Moderate confidence ({confidence:.2f}), re-generating",
                        "variant_tier": variant_tier,
                    },
                )
            else:
                # Acceptable confidence → auto-fix any issues
                result = InterventionResult(
                    intervention_type=InterventionType.AUTO_FIX,
                    success=True,
                    company_id=self.company_id,
                    ticket_id=ticket_id,
                    details={
                        "confidence": confidence,
                        "fixes_applied": ["tone", "empathy"],
                        "variant_tier": variant_tier,
                    },
                )

            self._interventions.append(result)
            return result

        except Exception:
            logger.exception("handle_low_confidence failed")
            return InterventionResult(
                intervention_type=InterventionType.ESCALATE,
                success=False,
                company_id=self.company_id,
                ticket_id=ticket_id,
                details={"error": "intervention_failed"},
            )

    def handle_quality_failure(
        self,
        pipeline_result: Dict[str, Any],
    ) -> InterventionResult:
        """Handle a quality gate failure.

        Strategy:
          1. If retries remaining → re-generate
          2. If retries exhausted → escalate
        """
        ticket_id = pipeline_result.get("ticket_id", "")
        variant_tier = pipeline_result.get("variant_tier", "")
        config = get_permission_config(variant_tier)
        retry_count = pipeline_result.get("quality_retry_count", 0)

        if retry_count < config.max_quality_retries:
            result = InterventionResult(
                intervention_type=InterventionType.RE_GENERATE,
                success=True,
                company_id=self.company_id,
                ticket_id=ticket_id,
                details={
                    "retry_count": retry_count,
                    "max_retries": config.max_quality_retries,
                    "quality_score": pipeline_result.get("quality_score", 0.0),
                },
            )
        else:
            result = InterventionResult(
                intervention_type=InterventionType.ESCALATE,
                success=True,
                company_id=self.company_id,
                ticket_id=ticket_id,
                details={
                    "reason": "quality_retries_exhausted",
                    "quality_score": pipeline_result.get("quality_score", 0.0),
                },
            )

        self._interventions.append(result)
        return result

    def handle_ask_client(
        self,
        pipeline_result: Dict[str, Any],
    ) -> InterventionResult:
        """Handle a variant that needs client input (ask-when-unsure).

        This creates a notification in the Notification CRM that
        the client can click to open a Jarvis chat.
        """
        ticket_id = pipeline_result.get("ticket_id", "")

        try:
            from app.services.notification_crm.manager import NotificationManager
            notif_mgr = NotificationManager(self.company_id)

            batch = notif_mgr.create_notification(
                notification_type="ask_client",
                title=f"Variant needs your input: {pipeline_result.get('ask_client_reason', 'Uncertain')}",
                description=pipeline_result.get("agent_response", ""),
                customer_id=pipeline_result.get("customer_id", ""),
                ticket_id=ticket_id,
                conversation_id=pipeline_result.get("conversation_id", ""),
                variant_tier=pipeline_result.get("variant_tier", ""),
                confidence=pipeline_result.get("confidence_score", 0.0),
                context=pipeline_result,
                ask_client_question=pipeline_result.get("ask_client_reason", ""),
                ask_client_options=["Approve", "Modify", "Reject", "Escalate to human"],
            )

            result = InterventionResult(
                intervention_type=InterventionType.ASK_CLIENT,
                success=True,
                company_id=self.company_id,
                ticket_id=ticket_id,
                details={
                    "notification_batch_id": batch.id,
                    "question": pipeline_result.get("ask_client_reason", ""),
                    "options": ["Approve", "Modify", "Reject", "Escalate to human"],
                },
            )

            self._interventions.append(result)
            return result

        except Exception:
            logger.exception("handle_ask_client failed")
            return InterventionResult(
                intervention_type=InterventionType.ASK_CLIENT,
                success=False,
                company_id=self.company_id,
                ticket_id=ticket_id,
                details={"error": "notification_creation_failed"},
            )

    def handle_maker_red_flag(
        self,
        pipeline_result: Dict[str, Any],
    ) -> InterventionResult:
        """Handle a MAKER validator red flag.

        Strategy:
          - If the action needs approval for this tier → escalate
          - If auto-approvable → approve with note
        """
        ticket_id = pipeline_result.get("ticket_id", "")
        variant_tier = pipeline_result.get("variant_tier", "")
        action_type = pipeline_result.get("action_type", "informational")

        if needs_approval(action_type, variant_tier):
            result = InterventionResult(
                intervention_type=InterventionType.ESCALATE,
                success=True,
                company_id=self.company_id,
                ticket_id=ticket_id,
                details={
                    "reason": "maker_red_flag_needs_approval",
                    "action_type": action_type,
                    "variant_tier": variant_tier,
                },
            )
        else:
            result = InterventionResult(
                intervention_type=InterventionType.APPROVE,
                success=True,
                company_id=self.company_id,
                ticket_id=ticket_id,
                details={
                    "reason": "maker_red_flag_auto_approved",
                    "action_type": action_type,
                    "variant_tier": variant_tier,
                    "note": "High tier auto-approved, but flagged for review",
                },
            )

        self._interventions.append(result)
        return result

    def get_interventions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent interventions."""
        return [i.to_dict() for i in self._interventions[-limit:]]

    def _generate_ask_question(self, pipeline_result: Dict[str, Any]) -> str:
        """Generate a question for the client based on the pipeline result."""
        intent = pipeline_result.get("intent", "general")
        confidence = pipeline_result.get("confidence_score", 0.0)

        questions = {
            "refund": "I'm not fully confident about this refund request. Would you like me to process it as-is, or would you prefer to review it first?",
            "billing": "This billing inquiry seems complex. Should I proceed with the standard resolution, or would you like to provide more specific guidance?",
            "technical": "I'm analyzing this technical issue but want to make sure I understand correctly. Can you confirm the main problem?",
            "complaint": "I want to make sure I handle this complaint appropriately. What's your preferred approach?",
            "cancellation": "This looks like it might be a cancellation risk. How would you like me to handle it?",
        }

        return questions.get(
            intent,
            f"I'm {confidence:.0%} confident about this response. Would you like me to proceed, or would you prefer to review it?"
        )
