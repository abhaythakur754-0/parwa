"""
Complaint Agent Node — Group 4 Domain Agent (Complaints / Dissatisfaction / Negative Feedback)

Specialized domain agent for handling customer complaints, dissatisfaction,
and negative feedback. Extends BaseDomainAgent with empathetic
acknowledgment, resolution offers, and service recovery capabilities.

State Contract:
  Reads:  pii_redacted_message, intent, tenant_id, variant_tier,
          sentiment_score, technique_stack, signals_extracted,
          conversation_id, gsd_state, context_health
  Writes: agent_response, agent_confidence, proposed_action,
          action_type, agent_reasoning, agent_type,
          complaint_classification, recovery_action

BC-008: Never crash — returns safe defaults on any failure.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from typing import Any, Dict, List

import importlib

from app.core.langgraph.config import get_variant_config
from app.logger import get_logger

logger = get_logger("node_complaint_agent")

# Lazy import of BaseDomainAgent — module name starts with digit so
# we use importlib instead of a standard import statement.
_base_agent_module = importlib.import_module(
    "app.core.langgraph.nodes.04_base_domain_agent"
)
BaseDomainAgent = _base_agent_module.BaseDomainAgent


# ──────────────────────────────────────────────────────────────
# Complaint Agent Implementation
# ──────────────────────────────────────────────────────────────


class ComplaintAgent(BaseDomainAgent):
    """
    Complaint Domain Agent — handles customer complaints, dissatisfaction,
    and negative feedback.

    Specializes the base domain agent with:
      - Complaint-oriented system prompt with empathy focus
      - Empathetic acknowledgment and validation
      - Resolution offers (discounts, credits, escalation)
      - Service recovery tracking

    This agent is available on Pro + High tiers ONLY (not mini).
    Tier check is performed in the node function; mini-tier requests
    fall back to a safe escalation response.
    """

    agent_name: str = "complaint"

    system_prompt: str = (
        "You are an empathetic and solution-focused complaint resolution agent. "
        "Your primary goal is to acknowledge the customer's frustration, "
        "validate their experience, and offer meaningful resolution. Always "
        "start with genuine empathy before moving to solutions. Never "
        "minimize the customer's concerns or be defensive. When offering "
        "compensation (discounts, credits), be specific about the amount "
        "and reason. If the complaint involves a systemic issue, flag it "
        "for escalation. Track recovery actions to ensure follow-through. "
        "Your tone should be warm, understanding, and proactive — the "
        "customer should feel heard and valued throughout the interaction."
    )

    domain_knowledge: Dict[str, Any] = {
        "domains": [
            "customer_complaints",
            "dissatisfaction",
            "negative_feedback",
            "service_recovery",
            "complaint_escalation",
        ],
        "proposed_actions": {
            "respond": "informational",
            "discount": "monetary",
            "credit": "monetary",
            "escalate": "escalation",
        },
        "recovery_policy": {
            "max_discount_percent": 30,
            "max_credit_amount": 100.00,
            "auto_credit_for_service_failures": True,
            "escalation_on_legal_threat": True,
            "escalation_on_repeat_complaint": True,
            "repeat_complaint_threshold": 3,
        },
        "empathy_guidelines": {
            "always_acknowledge_first": True,
            "never_deflect_blame": True,
            "use_customer_language": True,
            "offer_timeline_for_resolution": True,
        },
    }

    # ── Tier availability ─────────────────────────────────────

    _AVAILABLE_TIERS = {"pro", "high"}

    @classmethod
    def is_available_for_tier(cls, variant_tier: str) -> bool:
        """
        Check if this agent is available for the given variant tier.

        Complaint agent is only available on Pro and High tiers.

        Args:
            variant_tier: Variant tier string.

        Returns:
            True if available for this tier.
        """
        return variant_tier in cls._AVAILABLE_TIERS

    # ── Complaint classification ──────────────────────────────

    def _classify_complaint(
        self,
        message: str,
        sentiment_score: float,
        signals: Dict[str, Any],
        tenant_id: str,
    ) -> Dict[str, Any]:
        """
        Classify the complaint type and severity.

        Analyzes the message, sentiment, and signals to determine
        the complaint category and severity level.

        Args:
            message: The PII-redacted message.
            sentiment_score: Current sentiment score.
            signals: Extracted query signals.
            tenant_id: Tenant identifier (BC-001).

        Returns:
            Dict with 'category', 'severity', 'requires_escalation'.
        """
        try:
            # Keyword-based classification
            message_lower = message.lower()

            category = "general_dissatisfaction"
            if any(kw in message_lower for kw in ["legal", "lawyer", "sue", "attorney"]):
                category = "legal_threat"
            elif any(kw in message_lower for kw in ["discrimination", "harassment", "safety"]):
                category = "serious_allegation"
            elif any(kw in message_lower for kw in ["overcharged", "charged twice", "billing error"]):
                category = "billing_complaint"
            elif any(kw in message_lower for kw in ["broken", "defective", "doesn't work", "not working"]):
                category = "product_quality"
            elif any(kw in message_lower for kw in ["rude", "unprofessional", "disrespectful"]):
                category = "service_quality"
            elif any(kw in message_lower for kw in ["slow", "delayed", "waiting", "no response"]):
                category = "service_speed"

            # Severity based on sentiment and category
            severity = "medium"
            requires_escalation = False

            if category in ("legal_threat", "serious_allegation"):
                severity = "critical"
                requires_escalation = True
            elif sentiment_score <= 0.2:
                severity = "high"
                requires_escalation = True
            elif sentiment_score <= 0.3:
                severity = "high"
            elif sentiment_score <= 0.5:
                severity = "medium"

            # Check for repeat complaint signal
            complaint_count = 0
            if signals and isinstance(signals, dict):
                complaint_count = int(signals.get("complaint_count", 0))
            repeat_threshold = self.domain_knowledge.get(
                "recovery_policy", {}
            ).get("repeat_complaint_threshold", 3)

            if complaint_count >= repeat_threshold:
                requires_escalation = True
                if severity != "critical":
                    severity = "high"

            return {
                "category": category,
                "severity": severity,
                "requires_escalation": requires_escalation,
                "complaint_count": complaint_count,
            }

        except Exception as classify_exc:
            logger.warning(
                "complaint_classification_error",
                tenant_id=tenant_id,
                error=str(classify_exc),
            )
            return {
                "category": "general_dissatisfaction",
                "severity": "medium",
                "requires_escalation": False,
                "complaint_count": 0,
            }

    # ── Service recovery action ───────────────────────────────

    def _determine_recovery_action(
        self,
        complaint_classification: Dict[str, Any],
        sentiment_score: float,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """
        Determine the appropriate service recovery action.

        Based on complaint severity and sentiment, recommends
        a recovery action (discount, credit, or escalation).

        Args:
            complaint_classification: Output from _classify_complaint().
            sentiment_score: Current sentiment score.
            tenant_id: Tenant identifier (BC-001).

        Returns:
            Dict with 'recovery_type', 'recovery_value', 'reasoning'.
        """
        try:
            policy = self.domain_knowledge.get("recovery_policy", {})
            max_discount = policy.get("max_discount_percent", 30)
            max_credit = policy.get("max_credit_amount", 100.00)

            severity = complaint_classification.get("severity", "medium")
            category = complaint_classification.get("category", "general_dissatisfaction")
            requires_escalation = complaint_classification.get(
                "requires_escalation", False
            )

            # Legal threats and serious allegations always escalate
            if requires_escalation or category in ("legal_threat", "serious_allegation"):
                return {
                    "recovery_type": "escalate",
                    "recovery_value": 0.0,
                    "reasoning": (
                        f"Complaint category '{category}' with severity "
                        f"'{severity}' requires escalation to a specialist."
                    ),
                }

            # High severity: offer credit
            if severity == "high":
                credit_amount = min(max_credit, 50.00)
                return {
                    "recovery_type": "credit",
                    "recovery_value": credit_amount,
                    "reasoning": (
                        f"High severity complaint (sentiment: {sentiment_score:.2f}). "
                        f"Offering ${credit_amount:.2f} account credit as recovery."
                    ),
                }

            # Medium severity: offer discount
            if severity == "medium":
                discount_percent = min(max_discount, 15)
                return {
                    "recovery_type": "discount",
                    "recovery_value": discount_percent,
                    "reasoning": (
                        f"Medium severity complaint (sentiment: {sentiment_score:.2f}). "
                        f"Offering {discount_percent}% discount as recovery."
                    ),
                }

            # Low severity: informational response
            return {
                "recovery_type": "respond",
                "recovery_value": 0.0,
                "reasoning": (
                    f"Low severity complaint (sentiment: {sentiment_score:.2f}). "
                    "Empathetic acknowledgment and resolution guidance."
                ),
            }

        except Exception as recovery_exc:
            logger.warning(
                "recovery_action_error",
                tenant_id=tenant_id,
                error=str(recovery_exc),
            )
            return {
                "recovery_type": "respond",
                "recovery_value": 0.0,
                "reasoning": f"Could not determine recovery action: {recovery_exc}",
            }

    # ── Extra state update ────────────────────────────────────

    def _extra_state_update(
        self,
        state: Dict[str, Any],
        generation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Add complaint-specific fields to the state update.

        Extends the base state update with:
          - complaint_classification: Category, severity, escalation flag
          - recovery_action: Recommended service recovery action

        Args:
            state: Current ParwaGraphState dict.
            generation_result: Output from _generate_response().

        Returns:
            Dict with additional complaint state fields.
        """
        tenant_id = state.get("tenant_id", "unknown")
        message = state.get("pii_redacted_message", "") or state.get("message", "")
        sentiment_score = state.get("sentiment_score", 0.5)
        signals = state.get("signals_extracted", {})

        # Classify the complaint
        complaint_classification = self._classify_complaint(
            message=message,
            sentiment_score=sentiment_score,
            signals=signals,
            tenant_id=tenant_id,
        )

        # Determine recovery action
        recovery_action = self._determine_recovery_action(
            complaint_classification=complaint_classification,
            sentiment_score=sentiment_score,
            tenant_id=tenant_id,
        )

        return {
            "complaint_classification": complaint_classification,
            "recovery_action": recovery_action,
        }


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def complaint_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Complaint Agent Node — LangGraph agent node.

    Handles customer complaints, dissatisfaction, and negative feedback.
    Provides empathetic acknowledgment, classifies complaint severity,
    and recommends service recovery actions (discounts, credits,
    or escalation).

    This agent is available on Pro + High tiers ONLY. For mini-tier
    requests, returns a safe escalation response directing the
    customer to human support.

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with domain agent output fields
        plus complaint classification and recovery action fields.
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")

    logger.info(
        "complaint_agent_node_start",
        tenant_id=tenant_id,
        intent=state.get("intent", "unknown"),
        variant_tier=variant_tier,
    )

    try:
        # ── Tier gate: Complaint agent not available on mini ────
        if not ComplaintAgent.is_available_for_tier(variant_tier):
            logger.info(
                "complaint_agent_tier_unavailable",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
                message="Complaint agent requires Pro or High tier",
            )
            return {
                "agent_response": (
                    "I'm truly sorry to hear about your experience, and I "
                    "take your concerns very seriously. Our dedicated "
                    "complaint resolution team is available on our Pro and "
                    "High service plans. Let me connect you with a human "
                    "support specialist who can address this properly."
                ),
                "agent_confidence": 0.5,
                "proposed_action": "escalate",
                "action_type": "escalation",
                "agent_reasoning": (
                    f"Complaint agent not available for tier '{variant_tier}'. "
                    "Escalating to human support for proper resolution."
                ),
                "agent_type": "complaint",
                "complaint_classification": {
                    "category": "general_dissatisfaction",
                    "severity": "medium",
                    "requires_escalation": True,
                    "complaint_count": 0,
                },
                "recovery_action": {
                    "recovery_type": "escalate",
                    "recovery_value": 0.0,
                    "reason": "Agent not available for this tier.",
                },
            }

        agent = ComplaintAgent()
        return agent.run(state)
    except Exception as exc:
        logger.error(
            "complaint_agent_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )
        return {
            "agent_response": "",
            "agent_confidence": 0.0,
            "proposed_action": "respond",
            "action_type": "informational",
            "agent_reasoning": f"Complaint agent fatal error: {exc}",
            "agent_type": "complaint",
            "complaint_classification": {
                "category": "general_dissatisfaction",
                "severity": "medium",
                "requires_escalation": False,
                "complaint_count": 0,
            },
            "recovery_action": {
                "recovery_type": "respond",
                "recovery_value": 0.0,
                "reason": f"Agent error: {exc}",
            },
            "errors": [f"Complaint agent fatal error: {exc}"],
        }
