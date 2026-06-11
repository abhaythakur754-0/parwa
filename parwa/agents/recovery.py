"""AgentRecovery — Agent-level error recovery strategies.

When a node within an agent fails, AgentRecovery decides the best
recovery strategy based on the agent type, the failing node, and
the error severity. This is smarter than the global safe_node fallback
because it understands the agent's internal structure.

Recovery strategies:
  1. RETRY: Re-run the same node (for transient failures like LLM timeouts)
  2. SKIP: Skip the failed node and continue with the next one in the agent
     (for optional nodes like PREDICTION_ENGINE when the main path is solid)
  3. REDIRECT: Switch to an alternative node within the same agent
     (e.g., if KB_RETRIEVER fails, try FAQ_MATCHER as a fallback data source)
  4. DEGRADE: Fall back to a simpler processing mode within the agent
     (e.g., skip advanced reasoning if FrameworkBrain crashes)
  5. ESCALATE: Signal that this agent can't recover and needs external help

Key design decisions:
  - Recovery strategies are defined per-agent-type, not per-node
  - Each agent knows which of its nodes are "critical" vs "optional"
  - Maximum 2 retries per node before escalating
  - Recovery decisions are logged for audit and debugging
  - Recovery attempts are tracked in AgentContext
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger("parwa.agents.recovery")


class RecoveryStrategy(str, Enum):
    """Available recovery strategies when a node fails."""
    RETRY = "retry"
    SKIP = "skip"
    REDIRECT = "redirect"
    DEGRADE = "degrade"
    ESCALATE = "escalate"


# Which nodes are critical vs optional per agent
_AGENT_CRITICAL_NODES: dict[str, dict[str, bool]] = {
    "Router Agent": {
        "INGEST": True,           # Must run — entry point
        "INTENT_CLASSIFIER": True, # Must run — downstream depends on intent
        "SENTIMENT_ANALYZER": False, # Optional — routing uses it but has fallbacks
        "ESCALATION_DECISION": False, # Optional — only triggered for angry/critical
    },
    "Knowledge Agent": {
        "FAQ_MATCHER": False,      # Optional — KB_RETRIEVER can provide data
        "KB_RETRIEVER": True,      # Critical — primary data source for reasoning
        "CONTEXT_MANAGER": False,  # Optional — improves quality but not required
        "INTEGRATION_LOOKUP": False, # Optional — enriches but not critical
    },
    "Reasoning Agent": {
        "REASONING_ENGINE": True,   # Must run — core thinking
        "REVERSE_THINKER": False,   # Optional — advanced reasoning
        "TREE_OF_THOUGHTS": False,  # Optional — advanced reasoning
        "STRATEGY_PLANNER": False,  # Optional — advanced reasoning
    },
    "Action Agent": {
        "ACTION_PLANNER": True,     # Must run — decides what to do
        "ACTION_EXECUTOR": True,    # Must run — carries out the plan
        "ACTION_VERIFIER": False,   # Optional — verification is good but not always needed
    },
    "Compliance Agent": {
        "PII_COMPLIANCE_GUARD": True, # Must run — legal requirement
        "AUDIT_LOGGER": True,         # Must run — audit trail
        "QUALITY_SCORER": True,       # Must run — quality gate
        "RESPONSE_FORMATTER": True,   # Must run — produces the output
    },
    "Proactive Agent": {
        "PROACTIVE_CHECKER": False, # Optional — nice to have
        "PREDICTION_ENGINE": False, # Optional — nice to have
        "FEEDBACK_LOOP": False,     # Optional — learning, not essential for this ticket
    },
}

# Redirect targets when a node fails (fallback within same agent)
_REDIRECT_TARGETS: dict[str, dict[str, str | None]] = {
    "Knowledge Agent": {
        "KB_RETRIEVER": "FAQ_MATCHER",     # If KB fails, try FAQ
        "CONTEXT_MANAGER": None,            # No redirect — skip
        "INTEGRATION_LOOKUP": "KB_RETRIEVER", # If integration fails, KB might have data
        "FAQ_MATCHER": None,                # No redirect — KB is the fallback for FAQ
    },
    "Reasoning Agent": {
        "REVERSE_THINKER": None,            # Skip — not critical
        "TREE_OF_THOUGHTS": None,           # Skip — not critical
        "STRATEGY_PLANNER": None,           # Skip — not critical
    },
    "Action Agent": {
        "ACTION_VERIFIER": None,            # Skip verification on failure
    },
    "Proactive Agent": {
        "PROACTIVE_CHECKER": None,          # Skip — optional
        "PREDICTION_ENGINE": None,          # Skip — optional
        "FEEDBACK_LOOP": None,              # Skip — optional
    },
}

# Maximum retries per node before escalating
_MAX_RETRIES = 2


class RecoveryDecision:
    """A recovery decision made by AgentRecovery.

    Attributes:
        strategy: The chosen recovery strategy.
        retry_count: How many times this node has been retried.
        redirect_target: The alternative node (if strategy is REDIRECT).
        reason: Human-readable explanation of the decision.
    """

    def __init__(
        self,
        strategy: RecoveryStrategy,
        retry_count: int = 0,
        redirect_target: str | None = None,
        reason: str = "",
    ) -> None:
        self.strategy = strategy
        self.retry_count = retry_count
        self.redirect_target = redirect_target
        self.reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "retry_count": self.retry_count,
            "redirect_target": self.redirect_target,
            "reason": self.reason,
        }

    def __repr__(self) -> str:
        return (
            f"RecoveryDecision(strategy={self.strategy.value}, "
            f"retries={self.retry_count}, "
            f"redirect={self.redirect_target}, "
            f"reason={self.reason!r})"
        )


class AgentRecovery:
    """Agent-level error recovery decision engine.

    When a node within an agent fails, AgentRecovery evaluates the
    context and decides the best recovery strategy. It considers:
      - Whether the failing node is critical or optional
      - How many times this node has already been retried
      - Whether there's a redirect target available
      - The type of error (transient vs permanent)
    """

    def __init__(self) -> None:
        self._retry_counts: dict[str, int] = {}
        self._recovery_history: list[dict[str, Any]] = []

    def decide(
        self,
        agent_name: str,
        node_name: str,
        error: str,
        error_type: str = "",
    ) -> RecoveryDecision:
        """Decide the recovery strategy for a failed node.

        Args:
            agent_name: The agent that owns this node.
            node_name: The node that failed.
            error: The error message.
            error_type: The error class name (e.g. "TimeoutError").

        Returns:
            A RecoveryDecision with the chosen strategy.
        """
        # Track retry count
        key = f"{agent_name}:{node_name}"
        self._retry_counts[key] = self._retry_counts.get(key, 0) + 1
        retry_count = self._retry_counts[key]

        # Determine if the node is critical
        is_critical = self._is_critical(agent_name, node_name)

        # Check for transient errors (retry-able)
        is_transient = self._is_transient_error(error, error_type)

        # Make the decision
        if is_transient and retry_count <= _MAX_RETRIES:
            decision = RecoveryDecision(
                strategy=RecoveryStrategy.RETRY,
                retry_count=retry_count,
                reason=f"Transient error ({error_type}), retry {retry_count}/{_MAX_RETRIES}",
            )
        elif not is_critical:
            # Optional node — try redirect first, then skip
            redirect = self._get_redirect_target(agent_name, node_name)
            if redirect:
                decision = RecoveryDecision(
                    strategy=RecoveryStrategy.REDIRECT,
                    retry_count=retry_count,
                    redirect_target=redirect,
                    reason=f"Optional node failed, redirecting to {redirect}",
                )
            else:
                decision = RecoveryDecision(
                    strategy=RecoveryStrategy.SKIP,
                    retry_count=retry_count,
                    reason="Optional node failed, skipping",
                )
        elif is_critical and retry_count <= _MAX_RETRIES:
            # Critical node — try one more time, then degrade
            if retry_count < _MAX_RETRIES:
                decision = RecoveryDecision(
                    strategy=RecoveryStrategy.RETRY,
                    retry_count=retry_count,
                    reason=f"Critical node failed, retry {retry_count}/{_MAX_RETRIES}",
                )
            else:
                decision = RecoveryDecision(
                    strategy=RecoveryStrategy.DEGRADE,
                    retry_count=retry_count,
                    reason=f"Critical node failed after {retry_count} retries, degrading",
                )
        else:
            # Exhausted all options — escalate
            decision = RecoveryDecision(
                strategy=RecoveryStrategy.ESCALATE,
                retry_count=retry_count,
                reason=f"Cannot recover: critical node {node_name} failed after {retry_count} attempts",
            )

        # Log the decision
        logger.info(
            "AgentRecovery: %s/%s → %s (%s)",
            agent_name, node_name, decision.strategy.value, decision.reason,
        )

        # Record in history
        self._recovery_history.append({
            "agent": agent_name,
            "node": node_name,
            "error": error[:200],
            "error_type": error_type,
            "decision": decision.to_dict(),
        })

        return decision

    def _is_critical(self, agent_name: str, node_name: str) -> bool:
        """Check if a node is critical for its agent."""
        agent_nodes = _AGENT_CRITICAL_NODES.get(agent_name, {})
        return agent_nodes.get(node_name, True)  # Default to critical if unknown

    def _is_transient_error(self, error: str, error_type: str) -> bool:
        """Check if an error is likely transient (retry-able)."""
        transient_indicators = [
            "timeout", "timed out", "connection", "rate limit",
            "503", "502", "429", "temporarily", "retry",
            "circuit_breaker", "overloaded",
        ]
        error_lower = (error + " " + error_type).lower()
        return any(indicator in error_lower for indicator in transient_indicators)

    def _get_redirect_target(self, agent_name: str, node_name: str) -> str | None:
        """Get the redirect target for a failed node within an agent."""
        targets = _REDIRECT_TARGETS.get(agent_name, {})
        return targets.get(node_name)

    def get_retry_count(self, agent_name: str, node_name: str) -> int:
        """Get the current retry count for a specific node."""
        key = f"{agent_name}:{node_name}"
        return self._retry_counts.get(key, 0)

    def get_recovery_history(self) -> list[dict[str, Any]]:
        """Get the history of all recovery decisions made."""
        return list(self._recovery_history)

    def reset(self) -> None:
        """Reset retry counts and history (for testing)."""
        self._retry_counts.clear()
        self._recovery_history.clear()

    @staticmethod
    def get_critical_nodes(agent_name: str) -> list[str]:
        """Get the list of critical nodes for an agent."""
        agent_nodes = _AGENT_CRITICAL_NODES.get(agent_name, {})
        return [name for name, critical in agent_nodes.items() if critical]

    @staticmethod
    def get_optional_nodes(agent_name: str) -> list[str]:
        """Get the list of optional nodes for an agent."""
        agent_nodes = _AGENT_CRITICAL_NODES.get(agent_name, {})
        return [name for name, critical in agent_nodes.items() if not critical]
