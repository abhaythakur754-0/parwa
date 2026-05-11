"""
Escalation Agent Node — Group 5 Domain Agent (Escalation / Human handoff)

Specialized domain agent for handling escalation requests, manager
requests, legal threats, and supervisor handoffs. Extends BaseDomainAgent
with graceful escalation capabilities.

Availability: Pro + High tiers ONLY.
Mini tier falls back to FAQ agent for escalation intents (handled by router).

State Contract:
  Reads:  pii_redacted_message, intent, tenant_id, variant_tier,
          sentiment_score, technique_stack, signals_extracted,
          conversation_id, gsd_state, context_health,
          legal_threat_detected, urgency
  Writes: agent_response, agent_confidence, proposed_action,
          action_type, agent_reasoning, agent_type

BC-008: Never crash — returns safe defaults on any failure.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List

from app.logger import get_logger

logger = get_logger("node_escalation_agent")

# Lazy import of BaseDomainAgent — module name starts with digit so
# we use importlib instead of a standard import statement.
_base_agent_module = importlib.import_module(
    "app.core.langgraph.nodes.04_base_domain_agent"
)
BaseDomainAgent = _base_agent_module.BaseDomainAgent


# ──────────────────────────────────────────────────────────────
# Escalation Agent Implementation
# ──────────────────────────────────────────────────────────────


class EscalationAgent(BaseDomainAgent):
    """
    Escalation Domain Agent — handles escalation to human agents,
    manager requests, supervisor handoffs, and legal threats.

    Specializes the base domain agent with:
      - Escalation-oriented system prompt (empathetic + urgent)
      - Graceful escalation integration
      - Always sets action_type = "escalation" (high urgency)
      - Proposed actions: "escalate" or "human_handoff"

    This agent is only available for Pro and High tiers.
    Mini tier escalation intents are routed to the FAQ fallback agent.
    """

    agent_name: str = "escalation"

    system_prompt: str = (
        "You are an empathetic escalation support agent. "
        "Your role is to acknowledge the customer's need for elevated "
        "support, validate their concern, and prepare a warm handoff "
        "to a human agent or manager. Never dismiss escalation requests. "
        "If a legal threat is detected, treat it with the highest urgency "
        "and ensure the customer understands their concern is being taken "
        "seriously. Provide clear next steps and expected response times. "
        "Maintain a professional, calm, and reassuring tone even when "
        "the customer is frustrated. Always propose an escalation action."
    )

    domain_knowledge: Dict[str, Any] = {
        "domains": [
            "escalation",
            "manager_request",
            "supervisor_request",
            "legal_threat",
            "urgent_handoff",
            "complaint_escalation",
        ],
        "max_escalation_priority": "high",
        "always_escalate": True,
        "fallback_to_general": False,
    }

    def _classify_action(self, proposed_action: str) -> str:
        """
        Override: Escalation agent ALWAYS classifies as 'escalation'.

        Regardless of what the LLM proposes, the escalation agent
        always sets action_type = "escalation" because every
        interaction requires human involvement.

        Args:
            proposed_action: The action string proposed by the agent.

        Returns:
            Always returns "escalation".
        """
        return "escalation"

    def _extra_state_update(
        self,
        state: Dict[str, Any],
        generation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Add escalation-specific fields to the state update.

        Ensures proposed_action is always an escalation-type action
        and sets high urgency indicators.

        Args:
            state: Current ParwaGraphState dict.
            generation_result: Output from _generate_response().

        Returns:
            Dict with escalation-specific state overrides.
        """
        tenant_id = state.get("tenant_id", "unknown")

        # Normalize proposed_action to escalation actions only
        proposed_action = generation_result.get("proposed_action", "escalate")
        if proposed_action not in ("escalate", "human_handoff"):
            proposed_action = "escalate"

        # Use graceful_escalation module if available
        escalation_context = self._get_graceful_escalation_context(
            state=state,
            tenant_id=tenant_id,
        )

        extra: Dict[str, Any] = {
            "proposed_action": proposed_action,
            "action_type": "escalation",
            "urgency": "high",
        }

        # Merge any context from graceful_escalation
        if escalation_context:
            extra["agent_reasoning"] = (
                generation_result.get("reasoning", "")
                + f" | Escalation context: {escalation_context.get('summary', 'standard escalation')}"
            )

        return extra

    def _get_graceful_escalation_context(
        self,
        state: Dict[str, Any],
        tenant_id: str,
    ) -> Dict[str, Any]:
        """
        Retrieve graceful escalation context from the
        app.core.graceful_escalation module.

        Uses lazy import to avoid coupling. Falls back to empty
        context if the module is unavailable.

        Args:
            state: Current ParwaGraphState dict.
            tenant_id: Tenant identifier (BC-001).

        Returns:
            Dict with escalation context information.
        """
        try:
            from app.core.graceful_escalation import get_escalation_context  # type: ignore[import-untyped]

            legal_threat = state.get("legal_threat_detected", False)
            urgency = state.get("urgency", "high")
            message = state.get("pii_redacted_message", "")

            result = get_escalation_context(
                message=message,
                legal_threat=legal_threat,
                urgency=urgency,
                tenant_id=tenant_id,
            )

            logger.info(
                "graceful_escalation_context_retrieved",
                tenant_id=tenant_id,
                escalation_type=result.get("escalation_type", "standard"),
            )

            return result

        except ImportError:
            logger.info(
                "graceful_escalation_unavailable",
                tenant_id=tenant_id,
            )
        except Exception as esc_exc:
            logger.warning(
                "graceful_escalation_error",
                tenant_id=tenant_id,
                error=str(esc_exc),
            )

        return {}

    def _fallback_generate_response(
        self,
        message: str,
        enriched_context: Dict[str, Any],
        sentiment_score: float,
    ) -> Dict[str, Any]:
        """
        Template-based escalation response fallback.

        Produces an empathetic escalation acknowledgment when the
        response_generator module is unavailable. Always proposes
        an escalation action.

        Args:
            message: The PII-redacted message.
            enriched_context: Enriched context from techniques.
            sentiment_score: Sentiment score.

        Returns:
            Dict with response, confidence, proposed_action, reasoning.
        """
        # Escalation responses are always urgent and empathetic
        if sentiment_score <= 0.3:
            response = (
                "I completely understand your frustration, and I want to ensure "
                "you get the best possible support. I'm escalating this to a "
                "specialist who can give your concern the attention it deserves. "
                "A team member will reach out to you shortly."
            )
        elif sentiment_score <= 0.5:
            response = (
                "Thank you for bringing this to our attention. I'm going to "
                "connect you with a specialist who can better assist you with "
                "this matter. You'll hear from them soon."
            )
        else:
            response = (
                "I appreciate you reaching out. To make sure we handle this "
                "properly, I'm escalating this to our specialist team. "
                "Someone will be in touch with you shortly."
            )

        return {
            "response": response,
            "confidence": 0.7,  # Escalation agent is usually confident about escalating
            "proposed_action": "escalate",
            "reasoning": (
                "Fallback escalation template response. "
                "Customer requested escalation or trigger detected. "
                "Response generator module unavailable."
            ),
        }


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def escalation_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Escalation Agent Node — LangGraph agent node.

    Handles escalation requests, manager requests, supervisor
    handoffs, and legal threats. Always sets action_type = "escalation"
    and ensures proposed_action is either "escalate" or "human_handoff".

    This agent is ONLY available for Pro and High tiers.
    Mini tier escalation intents are routed to FAQ by the router.

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with domain agent output fields
        with action_type always set to "escalation".
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")

    logger.info(
        "escalation_agent_node_start",
        tenant_id=tenant_id,
        intent=state.get("intent", "unknown"),
        variant_tier=variant_tier,
    )

    try:
        # ── Tier guard: mini should not reach this agent ─────────
        # If somehow a mini-tier request arrives, redirect to FAQ
        if variant_tier == "mini":
            logger.warning(
                "escalation_agent_mini_tier_fallback",
                tenant_id=tenant_id,
                message="Mini tier should not reach escalation agent; redirecting to faq",
            )
            return {
                "agent_response": (
                    "I'd be happy to help you with this. Let me find the best "
                    "resources to assist you with your concern."
                ),
                "agent_confidence": 0.3,
                "proposed_action": "respond",
                "action_type": "informational",
                "agent_reasoning": (
                    "Escalation agent received mini-tier request. "
                    "Falling back to informational response since "
                    "escalation is not available for mini tier."
                ),
                "agent_type": "escalation",
            }

        # ── Run escalation agent ─────────────────────────────────
        agent = EscalationAgent()
        result = agent.run(state)

        # ── Force action_type = escalation (safety net) ──────────
        result["action_type"] = "escalation"

        # ── Force proposed_action to escalation actions only ─────
        if result.get("proposed_action") not in ("escalate", "human_handoff"):
            result["proposed_action"] = "escalate"

        logger.info(
            "escalation_agent_node_success",
            tenant_id=tenant_id,
            proposed_action=result.get("proposed_action"),
            action_type=result.get("action_type"),
        )

        return result

    except Exception as exc:
        logger.error(
            "escalation_agent_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )
        return {
            "agent_response": (
                "I understand you need to speak with someone. "
                "I'm connecting you with a human agent now."
            ),
            "agent_confidence": 0.5,
            "proposed_action": "escalate",
            "action_type": "escalation",
            "agent_reasoning": f"Escalation agent fatal error: {exc}",
            "agent_type": "escalation",
            "errors": [f"Escalation agent fatal error: {exc}"],
        }
