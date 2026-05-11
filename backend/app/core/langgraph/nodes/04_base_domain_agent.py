"""
Base Domain Agent — Abstract base class for all domain agents.

This is NOT a direct LangGraph node. It is a base class that provides
shared logic for all domain agent implementations (FAQ, Refund, Technical,
Billing, Complaint, Escalation). Each subclass sets its own:
  - agent_name:  str            (e.g., "faq", "refund", "technical")
  - system_prompt: str          (Domain-specific system prompt)
  - domain_knowledge: Dict      (Domain-specific knowledge config)

Shared Methods:
  - _apply_techniques()   — Applies the technique stack to enrich context
  - _generate_response()  — Calls response generator with enriched context
  - _classify_action()    — Classifies the proposed action type

State Contract:
  Reads:  pii_redacted_message, intent, tenant_id, variant_tier,
          sentiment_score, technique_stack, signals_extracted,
          conversation_id, gsd_state, context_health
  Writes: agent_response, agent_confidence, proposed_action,
          action_type, agent_reasoning, agent_type

BC-008: Never crash — returns safe defaults on any failure.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.langgraph.config import classify_action_type, get_variant_config
from app.logger import get_logger

logger = get_logger("node_base_domain_agent")


# ──────────────────────────────────────────────────────────────
# Default fallback values for domain agent output
# ──────────────────────────────────────────────────────────────

_DEFAULT_AGENT_STATE: Dict[str, Any] = {
    "agent_response": "",
    "agent_confidence": 0.0,
    "proposed_action": "respond",
    "action_type": "informational",
    "agent_reasoning": "",
    "agent_type": "",
}


class BaseDomainAgent(ABC):
    """
    Abstract base class for all PARWA domain agents.

    Each domain agent (FAQ, Refund, Technical, Billing, Complaint,
    Escalation) extends this class and provides:
      - agent_name:  Unique agent identifier string
      - system_prompt: Domain-specific system prompt for LLM
      - domain_knowledge: Domain-specific configuration dict

    The `run(state)` method is the main entry point that orchestrates:
      1. Technique application
      2. Response generation
      3. Action classification
      4. State update construction

    Usage in a LangGraph node::

        def faq_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
            agent = FAQAgent()
            return agent.run(state)
    """

    # ── Subclass must override these ───────────────────────────
    agent_name: str = "base"
    """Unique agent identifier (e.g., 'faq', 'refund')."""

    system_prompt: str = "You are a helpful customer support agent."
    """Domain-specific system prompt for LLM generation."""

    domain_knowledge: Dict[str, Any] = {}
    """Domain-specific knowledge configuration."""

    def __init__(self) -> None:
        self._logger = get_logger(f"agent_{self.agent_name}")

    # ──────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the domain agent logic and return a partial state update.

        Orchestrates the full agent pipeline:
          1. Apply techniques to enrich the message context
          2. Generate the response using the domain's system prompt
          3. Classify the proposed action type
          4. Construct and return the state update

        Args:
            state: Current ParwaGraphState dict.

        Returns:
            Partial state update dict with domain agent output fields.
        """
        tenant_id = state.get("tenant_id", "unknown")
        variant_tier = state.get("variant_tier", "mini")

        self._logger.info(
            "domain_agent_start",
            agent_name=self.agent_name,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
        )

        try:
            # ── Extract state fields ────────────────────────────
            message = state.get("pii_redacted_message", "") or state.get("message", "")
            intent = state.get("intent", "general")
            sentiment_score = state.get("sentiment_score", 0.5)
            technique_stack = state.get("technique_stack", [])
            signals_extracted = state.get("signals_extracted", {})
            conversation_id = state.get("conversation_id", "")
            gsd_state = state.get("gsd_state", "new")
            context_health = state.get("context_health", 1.0)

            # ── Step 1: Apply techniques ────────────────────────
            enriched_context = self._apply_techniques(
                message=message,
                technique_stack=technique_stack,
                signals=signals_extracted,
                sentiment_score=sentiment_score,
                tenant_id=tenant_id,
            )

            # ── Step 2: Generate response ───────────────────────
            generation_result = self._generate_response(
                message=message,
                enriched_context=enriched_context,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                gsd_state=gsd_state,
                context_health=context_health,
                sentiment_score=sentiment_score,
            )

            agent_response = generation_result.get("response", "")
            agent_confidence = float(generation_result.get("confidence", 0.0))
            proposed_action = str(generation_result.get("proposed_action", "respond"))
            agent_reasoning = str(generation_result.get("reasoning", ""))

            # Clamp confidence
            agent_confidence = round(max(0.0, min(1.0, agent_confidence)), 2)

            # ── Step 3: Classify action type ────────────────────
            action_type = self._classify_action(proposed_action)

            # ── Step 4: Build state update ──────────────────────
            result = {
                "agent_response": agent_response,
                "agent_confidence": agent_confidence,
                "proposed_action": proposed_action,
                "action_type": action_type,
                "agent_reasoning": agent_reasoning,
                "agent_type": self.agent_name,
            }

            # ── Allow subclass to add extra fields ──────────────
            extra = self._extra_state_update(state, generation_result)
            if extra and isinstance(extra, dict):
                result.update(extra)

            self._logger.info(
                "domain_agent_success",
                agent_name=self.agent_name,
                tenant_id=tenant_id,
                agent_confidence=agent_confidence,
                proposed_action=proposed_action,
                action_type=action_type,
            )

            return result

        except Exception as exc:
            self._logger.error(
                "domain_agent_failed",
                agent_name=self.agent_name,
                tenant_id=tenant_id,
                error=str(exc),
            )
            return {
                **_DEFAULT_AGENT_STATE,
                "agent_type": self.agent_name,
                "errors": [f"{self.agent_name} agent failed: {exc}"],
            }

    # ──────────────────────────────────────────────────────────
    # Technique application
    # ──────────────────────────────────────────────────────────

    def _apply_techniques(
        self,
        message: str,
        technique_stack: List[str],
        signals: Dict[str, Any],
        sentiment_score: float,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """
        Apply the technique stack to enrich the message context.

        Each technique in the stack is applied sequentially, with
        each technique's output feeding into the next. Falls back
        to basic context enrichment if the techniques module is
        unavailable.

        Args:
            message: The PII-redacted message.
            technique_stack: Ordered list of technique IDs.
            signals: Extracted query signals.
            sentiment_score: Current sentiment score.
            tenant_id: Tenant identifier (BC-001).

        Returns:
            Dict containing enriched context for response generation.
        """
        enriched: Dict[str, Any] = {
            "original_message": message,
            "applied_techniques": [],
            "technique_outputs": {},
            "signals": signals,
            "sentiment_score": sentiment_score,
        }

        for technique_id in technique_stack:
            try:
                # Attempt lazy import of the technique module
                technique_fn = self._get_technique_function(technique_id)
                if technique_fn is not None:
                    output = technique_fn(
                        message=message,
                        signals=signals,
                        sentiment_score=sentiment_score,
                    )
                    if isinstance(output, dict):
                        enriched["technique_outputs"][technique_id] = output
                        # Techniques may modify the working message
                        message = output.get("refined_message", message)

                    enriched["applied_techniques"].append(technique_id)
                else:
                    # Technique function not available — skip
                    enriched["applied_techniques"].append(f"{technique_id}_skipped")

            except Exception as tech_exc:
                self._logger.warning(
                    "technique_application_failed",
                    agent_name=self.agent_name,
                    tenant_id=tenant_id,
                    technique_id=technique_id,
                    error=str(tech_exc),
                )
                enriched["applied_techniques"].append(f"{technique_id}_error")

        enriched["refined_message"] = message
        return enriched

    def _get_technique_function(self, technique_id: str) -> Optional[Any]:
        """
        Lazily import and return a technique function by ID.

        Technique modules are expected to expose a function with the
        same name as the technique_id in app.core.techniques.

        Args:
            technique_id: Technique identifier string.

        Returns:
            Technique function if available, None otherwise.
        """
        try:
            import app.core.techniques as techniques_module  # type: ignore[import-untyped]

            fn = getattr(techniques_module, technique_id, None)
            if callable(fn):
                return fn
        except ImportError:
            pass

        # Try individual technique module import
        try:
            module_path = f"app.core.techniques.{technique_id}"
            module = __import__(module_path, fromlist=[technique_id])
            fn = getattr(module, "apply", None) or getattr(module, technique_id, None)
            if callable(fn):
                return fn
        except (ImportError, AttributeError):
            pass

        return None

    # ──────────────────────────────────────────────────────────
    # Response generation
    # ──────────────────────────────────────────────────────────

    def _generate_response(
        self,
        message: str,
        enriched_context: Dict[str, Any],
        tenant_id: str,
        conversation_id: str,
        gsd_state: str,
        context_health: float,
        sentiment_score: float,
    ) -> Dict[str, Any]:
        """
        Generate the domain agent's response.

        Uses the production response_generator when available.
        Falls back to a template-based response.

        Args:
            message: The PII-redacted message.
            enriched_context: Output from _apply_techniques().
            tenant_id: Tenant identifier (BC-001).
            conversation_id: Conversation ID for continuity.
            gsd_state: Current GSD state machine state.
            context_health: Context health score 0.0-1.0.
            sentiment_score: Sentiment score 0.0-1.0.

        Returns:
            Dict with 'response', 'confidence', 'proposed_action', 'reasoning'.
        """
        try:
            from app.core.response_generator import generate_response  # type: ignore[import-untyped]

            result = generate_response(
                message=message,
                system_prompt=self.system_prompt,
                enriched_context=enriched_context,
                domain_knowledge=self.domain_knowledge,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                gsd_state=gsd_state,
                context_health=context_health,
                sentiment_score=sentiment_score,
                agent_name=self.agent_name,
            )

            return {
                "response": result.get("response", ""),
                "confidence": float(result.get("confidence", 0.0)),
                "proposed_action": result.get("proposed_action", "respond"),
                "reasoning": result.get("reasoning", ""),
            }

        except ImportError:
            self._logger.warning(
                "response_generator_unavailable_using_fallback",
                agent_name=self.agent_name,
                tenant_id=tenant_id,
            )
        except Exception as gen_exc:
            self._logger.warning(
                "response_generator_error_using_fallback",
                agent_name=self.agent_name,
                tenant_id=tenant_id,
                error=str(gen_exc),
            )

        # ── Fallback: template-based response ──────────────────
        return self._fallback_generate_response(
            message=message,
            enriched_context=enriched_context,
            sentiment_score=sentiment_score,
        )

    def _fallback_generate_response(
        self,
        message: str,
        enriched_context: Dict[str, Any],
        sentiment_score: float,
    ) -> Dict[str, Any]:
        """
        Template-based response generation fallback.

        Produces a simple acknowledgment response when the
        response_generator module is unavailable.

        Args:
            message: The PII-redacted message.
            enriched_context: Enriched context from techniques.
            sentiment_score: Sentiment score.

        Returns:
            Dict with response, confidence, proposed_action, reasoning.
        """
        # Adjust tone based on sentiment
        if sentiment_score <= 0.3:
            tone_prefix = "I understand your frustration, and I'm here to help. "
        elif sentiment_score >= 0.7:
            tone_prefix = "Great to hear from you! "
        else:
            tone_prefix = "Thank you for reaching out. "

        response = (
            f"{tone_prefix}"
            f"I've received your query regarding: \"{message[:100]}{'...' if len(message) > 100 else ''}\". "
            f"Let me look into this for you."
        )

        return {
            "response": response,
            "confidence": 0.3,
            "proposed_action": "respond",
            "reasoning": (
                f"Fallback template response for {self.agent_name} agent. "
                "Response generator module unavailable."
            ),
        }

    # ──────────────────────────────────────────────────────────
    # Action classification
    # ──────────────────────────────────────────────────────────

    def _classify_action(self, proposed_action: str) -> str:
        """
        Classify a proposed action into an action type category.

        Uses the config's classify_action_type function, which maps
        actions to informational, monetary, destructive, or escalation.

        Args:
            proposed_action: The action string proposed by the agent.

        Returns:
            Action type string.
        """
        try:
            return classify_action_type(proposed_action)
        except Exception:
            # Ultimate fallback
            return "informational"

    # ──────────────────────────────────────────────────────────
    # Hook for subclass extra state
    # ──────────────────────────────────────────────────────────

    def _extra_state_update(
        self,
        state: Dict[str, Any],
        generation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Hook for subclasses to add extra fields to the state update.

        Override this in domain agent subclasses that produce
        additional state fields beyond the standard domain agent
        output (e.g., RAG documents for FAQ agent).

        Args:
            state: Current ParwaGraphState dict.
            generation_result: Output from _generate_response().

        Returns:
            Dict of additional state fields to merge.
        """
        return {}

    # ──────────────────────────────────────────────────────────
    # GSD engine integration
    # ──────────────────────────────────────────────────────────

    def _get_gsd_context(
        self,
        conversation_id: str,
        tenant_id: str,
        gsd_state: str,
    ) -> Dict[str, Any]:
        """
        Retrieve Guided Support Dialogue context for conversation
        continuity.

        Uses the production gsd_engine when available.
        Returns minimal context dict otherwise.

        Args:
            conversation_id: Conversation identifier.
            tenant_id: Tenant identifier (BC-001).
            gsd_state: Current GSD state.

        Returns:
            Dict with GSD context information.
        """
        try:
            from app.core.gsd_engine import get_gsd_context  # type: ignore[import-untyped]

            return get_gsd_context(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                current_state=gsd_state,
            )
        except ImportError:
            self._logger.info(
                "gsd_engine_unavailable",
                agent_name=self.agent_name,
                tenant_id=tenant_id,
            )
        except Exception as gsd_exc:
            self._logger.warning(
                "gsd_engine_error",
                agent_name=self.agent_name,
                tenant_id=tenant_id,
                error=str(gsd_exc),
            )

        return {
            "conversation_id": conversation_id,
            "gsd_state": gsd_state,
            "gsd_step": "",
        }
