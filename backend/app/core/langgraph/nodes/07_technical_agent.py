"""
Technical Agent Node — Group 4 Domain Agent (Technical Support / Troubleshooting)

Specialized domain agent for handling technical support, troubleshooting,
and bug report requests. Extends BaseDomainAgent with tool-based reasoning
for step-by-step diagnosis and system status checks.

State Contract:
  Reads:  pii_redacted_message, intent, tenant_id, variant_tier,
          sentiment_score, technique_stack, signals_extracted,
          conversation_id, gsd_state, context_health
  Writes: agent_response, agent_confidence, proposed_action,
          action_type, agent_reasoning, agent_type,
          troubleshooting_steps, system_status

BC-008: Never crash — returns safe defaults on any failure.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from typing import Any, Dict, List

import importlib

from app.core.langgraph.config import get_variant_config
from app.logger import get_logger

logger = get_logger("node_technical_agent")

# Lazy import of BaseDomainAgent — module name starts with digit so
# we use importlib instead of a standard import statement.
_base_agent_module = importlib.import_module(
    "app.core.langgraph.nodes.04_base_domain_agent"
)
BaseDomainAgent = _base_agent_module.BaseDomainAgent


# ──────────────────────────────────────────────────────────────
# Technical Agent Implementation
# ──────────────────────────────────────────────────────────────


class TechnicalAgent(BaseDomainAgent):
    """
    Technical Domain Agent — handles technical support, troubleshooting,
    and bug report requests.

    Specializes the base domain agent with:
      - Technical-oriented system prompt
      - Tool-based reasoning via react_tools
      - Step-by-step troubleshooting guidance
      - Error diagnosis and system status checks

    This agent is available on ALL tiers (mini, pro, high).
    """

    agent_name: str = "technical"

    system_prompt: str = (
        "You are a skilled and patient technical support agent. "
        "Your goal is to help customers resolve technical issues through "
        "systematic troubleshooting and clear step-by-step guidance. "
        "Always start by understanding the exact problem, then work "
        "through diagnosis methodically. Use available tools to check "
        "system status and gather diagnostic information. When creating "
        "support tickets, include all relevant technical details. "
        "Escalate to engineering when issues require code-level "
        "investigation or when system-wide outages are detected. "
        "Keep instructions clear and numbered. Avoid jargon unless "
        "the customer demonstrates technical proficiency."
    )

    domain_knowledge: Dict[str, Any] = {
        "domains": [
            "technical_support",
            "troubleshooting",
            "bug_reports",
            "error_diagnosis",
            "system_status",
        ],
        "proposed_actions": {
            "respond": "informational",
            "create_ticket": "informational",
            "escalate": "escalation",
        },
        "troubleshooting": {
            "max_steps": 8,
            "require_error_details": True,
            "auto_system_status_check": True,
            "known_issues_db_enabled": True,
        },
        "ticket_creation": {
            "auto_include_diagnostics": True,
            "priority_levels": ["low", "medium", "high", "critical"],
            "default_priority": "medium",
        },
    }

    # ── System status check ───────────────────────────────────

    def _check_system_status(
        self,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """
        Check current system status and known incidents.

        Uses app.core.react_tools for system status lookups.
        Falls back to unknown status if tools are unavailable.

        Args:
            tenant_id: Tenant identifier (BC-001).

        Returns:
            Dict with 'overall_status', 'active_incidents', 'services'.
        """
        try:
            from app.core.react_tools import get_system_status  # type: ignore[import-untyped]

            result = get_system_status(tenant_id=tenant_id)

            logger.info(
                "system_status_check_success",
                tenant_id=tenant_id,
                overall_status=result.get("overall_status", "unknown"),
            )

            return {
                "overall_status": result.get("overall_status", "unknown"),
                "active_incidents": result.get("active_incidents", []),
                "services": result.get("services", {}),
            }

        except ImportError:
            logger.warning(
                "react_tools_unavailable",
                tenant_id=tenant_id,
            )
        except Exception as status_exc:
            logger.warning(
                "system_status_check_error",
                tenant_id=tenant_id,
                error=str(status_exc),
            )

        # Fallback: unknown status
        return {
            "overall_status": "unknown",
            "active_incidents": [],
            "services": {},
        }

    # ── Troubleshooting step generation ───────────────────────

    def _generate_troubleshooting_steps(
        self,
        message: str,
        signals: Dict[str, Any],
        system_status: Dict[str, Any],
        tenant_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate structured troubleshooting steps for the issue.

        Uses app.core.react_tools for tool-based reasoning when
        available. Falls back to basic step templates.

        Args:
            message: The PII-redacted message describing the issue.
            signals: Extracted query signals.
            system_status: Current system status information.
            tenant_id: Tenant identifier (BC-001).

        Returns:
            List of troubleshooting step dicts.
        """
        try:
            from app.core.react_tools import diagnose_issue  # type: ignore[import-untyped]

            result = diagnose_issue(
                query=message,
                tenant_id=tenant_id,
                context={
                    "signals": signals,
                    "system_status": system_status,
                },
            )

            steps = result.get("steps", [])

            logger.info(
                "troubleshooting_steps_generated",
                tenant_id=tenant_id,
                step_count=len(steps),
            )

            return steps

        except ImportError:
            logger.warning(
                "react_tools_diagnose_unavailable",
                tenant_id=tenant_id,
            )
        except Exception as diag_exc:
            logger.warning(
                "troubleshooting_generation_error",
                tenant_id=tenant_id,
                error=str(diag_exc),
            )

        # Fallback: basic troubleshooting template
        overall_status = system_status.get("overall_status", "unknown")
        active_incidents = system_status.get("active_incidents", [])

        steps = [
            {
                "step": 1,
                "action": "Verify the issue",
                "description": "Confirm the exact error message or unexpected behavior.",
            },
            {
                "step": 2,
                "action": "Check for known issues",
                "description": (
                    f"Current system status: {overall_status}. "
                    f"Active incidents: {len(active_incidents)}."
                ),
            },
            {
                "step": 3,
                "action": "Basic resolution",
                "description": (
                    "Try refreshing the page, clearing cache, or restarting "
                    "the application."
                ),
            },
        ]

        return steps

    # ── Extra state update ────────────────────────────────────

    def _extra_state_update(
        self,
        state: Dict[str, Any],
        generation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Add technical-specific fields to the state update.

        Extends the base state update with:
          - troubleshooting_steps: List of structured troubleshooting steps
          - system_status: Current system status and incidents

        Args:
            state: Current ParwaGraphState dict.
            generation_result: Output from _generate_response().

        Returns:
            Dict with additional technical state fields.
        """
        tenant_id = state.get("tenant_id", "unknown")
        message = state.get("pii_redacted_message", "") or state.get("message", "")
        signals = state.get("signals_extracted", {})

        # Check system status
        system_status = self._check_system_status(tenant_id=tenant_id)

        # Generate troubleshooting steps
        troubleshooting_steps = self._generate_troubleshooting_steps(
            message=message,
            signals=signals,
            system_status=system_status,
            tenant_id=tenant_id,
        )

        return {
            "troubleshooting_steps": troubleshooting_steps,
            "system_status": system_status,
        }


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def technical_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Technical Agent Node — LangGraph agent node.

    Handles technical support, troubleshooting, and bug report requests.
    Uses tool-based reasoning for systematic diagnosis and provides
    step-by-step guidance. Checks system status for known incidents.

    This agent is available on ALL tiers (mini, pro, high).

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with domain agent output fields
        plus troubleshooting steps and system status fields.
    """
    tenant_id = state.get("tenant_id", "unknown")

    logger.info(
        "technical_agent_node_start",
        tenant_id=tenant_id,
        intent=state.get("intent", "unknown"),
    )

    try:
        agent = TechnicalAgent()
        return agent.run(state)
    except Exception as exc:
        logger.error(
            "technical_agent_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )
        return {
            "agent_response": "",
            "agent_confidence": 0.0,
            "proposed_action": "respond",
            "action_type": "informational",
            "agent_reasoning": f"Technical agent fatal error: {exc}",
            "agent_type": "technical",
            "troubleshooting_steps": [],
            "system_status": {
                "overall_status": "unknown",
                "active_incidents": [],
                "services": {},
            },
            "errors": [f"Technical agent fatal error: {exc}"],
        }
