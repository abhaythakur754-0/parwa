"""AgentOrchestrator — Coordinates the 6 agents through the pipeline.

The AgentOrchestrator is the brain behind the 6 agents. It:
  1. Tracks which agent is currently active for each ticket
  2. Manages agent context lifecycle (create → populate → finalize)
  3. Handles agent handoffs (when control passes from one agent to another)
  4. Enables cross-agent state sharing (read-only from other agents' contexts)
  5. Integrates with AgentRecovery for error handling
  6. Feeds metrics to AgentMetrics for monitoring

How it works:
  The orchestrator wraps each node function with middleware that:
  - Identifies which agent owns the current node
  - Starts/continues the agent's context
  - Records the node output in the agent's context
  - Detects agent handoffs (when the agent changes between nodes)
  - Finalizes the previous agent's context on handoff
  - Handles errors via AgentRecovery

  This is done WITHOUT modifying LangGraph's routing. The orchestrator
  is a sidecar that observes and records — it doesn't control flow.

Integration point:
  The orchestrator is integrated via `orchestrated_node()` — a wrapper
  that replaces raw node functions in graph.py with orchestrated versions.
  The graph structure remains unchanged; only the node execution gains
  agent-awareness.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from parwa.agents.context import AgentContext
from parwa.agents.metrics import get_agent_metrics
from parwa.agents.recovery import AgentRecovery, RecoveryStrategy

logger = logging.getLogger("parwa.agents.orchestrator")


# Node name → Agent name mapping (from CLAUDE.md)
_NODE_TO_AGENT: dict[str, str] = {
    # Router Agent (nodes 1, 2, 18, 20)
    "ingest": "Router Agent",
    "intent_classifier": "Router Agent",
    "sentiment_analyzer": "Router Agent",
    "escalation_decision": "Router Agent",
    # Knowledge Agent (nodes 3, 4, 19, 5)
    "faq_matcher": "Knowledge Agent",
    "kb_retriever": "Knowledge Agent",
    "context_manager": "Knowledge Agent",
    "integration_lookup": "Knowledge Agent",
    # Reasoning Agent (nodes 6, 10, 12, 11)
    "reasoning_engine": "Reasoning Agent",
    "reverse_thinker": "Reasoning Agent",
    "tree_of_thoughts": "Reasoning Agent",
    "strategy_planner": "Reasoning Agent",
    # Action Agent (nodes 7, 8, 9)
    "action_planner": "Action Agent",
    "action_executor": "Action Agent",
    "action_verifier": "Action Agent",
    # Proactive Agent (nodes 13, 14, 22)
    "proactive_checker": "Proactive Agent",
    "prediction_engine": "Proactive Agent",
    "feedback_loop": "Proactive Agent",
    # Compliance Agent (nodes 15, 16, 21, 17)
    "pii_compliance_guard": "Compliance Agent",
    "audit_logger": "Compliance Agent",
    "quality_scorer": "Compliance Agent",
    "response_formatter": "Compliance Agent",
    # Internal node
    "loop_back_handler": "Router Agent",
}

# Order of nodes within each agent (for context sequencing)
_AGENT_NODE_ORDER: dict[str, list[str]] = {
    "Router Agent": ["ingest", "intent_classifier", "sentiment_analyzer", "escalation_decision"],
    "Knowledge Agent": ["faq_matcher", "kb_retriever", "context_manager", "integration_lookup"],
    "Reasoning Agent": ["reasoning_engine", "reverse_thinker", "tree_of_thoughts", "strategy_planner"],
    "Action Agent": ["action_planner", "action_executor", "action_verifier"],
    "Proactive Agent": ["proactive_checker", "prediction_engine", "feedback_loop"],
    "Compliance Agent": ["pii_compliance_guard", "audit_logger", "quality_scorer", "response_formatter"],
}

# How many nodes each agent owns
_AGENT_NODE_COUNTS: dict[str, int] = {
    name: len(nodes) for name, nodes in _AGENT_NODE_ORDER.items()
}


class AgentOrchestrator:
    """Coordinates the 6 agents through the PARWA pipeline.

    The orchestrator tracks agent contexts, handles handoffs, and
    provides cross-agent state sharing. It doesn't control the flow
    (LangGraph does that) — it observes and enriches.

    Usage:
        orchestrator = get_orchestrator()
        # Wrap node functions with orchestration middleware
        wrapped_node = orchestrator.orchestrated_node(my_node_func, "reasoning_engine")
        # Use wrapped_node in graph.add_node() instead of my_node_func
    """

    def __init__(self) -> None:
        self._recovery = AgentRecovery()
        self._metrics = get_agent_metrics()

    def get_agent_for_node(self, node_name: str) -> str:
        """Get the agent that owns a given node."""
        return _NODE_TO_AGENT.get(node_name, "Unknown Agent")

    def get_agent_context(self, state: dict[str, Any], agent_name: str) -> AgentContext | None:
        """Get an agent's context from the ticket state."""
        contexts = state.get("agent_contexts", {})
        if not isinstance(contexts, dict):
            return None
        ctx_data = contexts.get(agent_name)
        if ctx_data is None:
            return None
        if isinstance(ctx_data, AgentContext):
            return ctx_data
        if isinstance(ctx_data, dict):
            return AgentContext.from_dict(ctx_data)
        return None

    def get_or_create_context(self, state: dict[str, Any], agent_name: str) -> AgentContext:
        """Get an existing agent context or create a new one."""
        ctx = self.get_agent_context(state, agent_name)
        if ctx is None:
            ctx = AgentContext(agent_name=agent_name)
        return ctx

    def _save_context(self, state: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        """Save an agent context back to the ticket state."""
        contexts = state.get("agent_contexts", {})
        if not isinstance(contexts, dict):
            contexts = {}
        contexts = dict(contexts)  # Copy to avoid mutation
        contexts[ctx.agent_name] = ctx.to_dict()
        return {"agent_contexts": contexts}

    def _detect_handoff(self, prev_agent: str | None, current_agent: str) -> bool:
        """Detect if there's an agent handoff (agent change between nodes)."""
        if prev_agent is None:
            return False
        return prev_agent != current_agent

    def _finalize_agent_if_needed(
        self,
        state: dict[str, Any],
        agent_name: str,
        node_name: str,
    ) -> dict[str, Any]:
        """Finalize an agent's context if this is its last node.

        Checks if the current node is the last node in the agent's
        sequence. If so, marks the context as complete and records
        metrics.
        """
        ctx = self.get_agent_context(state, agent_name)
        if ctx is None or ctx.is_completed:
            return {}

        agent_nodes = _AGENT_NODE_ORDER.get(agent_name, [])
        if not agent_nodes:
            return {}

        # Check if this is the last node in the agent's sequence
        # A node is "last" if all subsequent nodes in the agent have NOT run
        node_idx = -1
        for i, name in enumerate(agent_nodes):
            if name == node_name:
                node_idx = i
                break

        if node_idx == -1:
            return {}

        # Check if all nodes after this one haven't been completed
        is_last_so_far = True
        for later_node in agent_nodes[node_idx + 1:]:
            if ctx.has_node_completed(later_node):
                is_last_so_far = False
                break

        # Also consider that some nodes may be skipped due to routing
        # So we also finalize if we detect an agent handoff
        # (handled separately in orchestrated_node)

        if is_last_so_far:
            ctx.complete()
            self._metrics.record_agent_run(agent_name, ctx)
            return self._save_context(state, ctx)

        return {}

    def orchestrated_node(
        self,
        node_func: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        node_name: str,
    ) -> Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]:
        """Wrap a node function with agent orchestration middleware.

        The wrapper:
          1. Identifies which agent owns this node
          2. Gets or creates the agent's context
          3. Detects agent handoffs (finalizes previous agent)
          4. Records node start in agent context
          5. Calls the original node function
          6. Records node output in agent context
          7. Detects if this is the agent's last node (finalizes)
          8. Returns the node output + agent context updates

        Args:
            node_func: The original async node function.
            node_name: The node name (e.g. "reasoning_engine").

        Returns:
            An orchestrated version of the node function.
        """
        agent_name = self.get_agent_for_node(node_name)

        async def wrapper(state: dict[str, Any]) -> dict[str, Any]:
            # 1. Detect agent handoff
            prev_agent = state.get("_current_agent")
            is_handoff = self._detect_handoff(prev_agent, agent_name)

            handoff_updates: dict[str, Any] = {}

            if is_handoff and prev_agent is not None:
                # Finalize the previous agent's context
                prev_ctx = self.get_agent_context(state, prev_agent)
                if prev_ctx and not prev_ctx.is_completed:
                    prev_ctx.complete()
                    self._metrics.record_agent_run(prev_agent, prev_ctx)
                    ctx_updates = self._save_context(state, prev_ctx)
                    handoff_updates.update(ctx_updates)

                logger.debug(
                    "AgentOrchestrator: handoff %s → %s",
                    prev_agent, agent_name,
                )

            # 2. Get or create agent context
            ctx = self.get_or_create_context(state, agent_name)

            # 3. Record node start
            ctx.start_node(node_name)

            # 4. Call the original node function
            try:
                result = await node_func(state)
            except Exception as exc:
                # Node failed — record in context
                ctx.add_error(node_name, str(exc))
                ctx.end_node(node_name, {"node_error": str(exc)})

                # Decide recovery strategy
                decision = self._recovery.decide(
                    agent_name, node_name,
                    str(exc), type(exc).__name__,
                )

                # For now, re-raise the exception (safe_node handles fallback)
                # Recovery decisions are logged and tracked for future use
                # (actual retry/redirect will be added in Phase 7)
                raise

            # 5. Record node output in agent context
            if not isinstance(result, dict):
                result = {}

            ctx.end_node(node_name, result)

            # 6. Check if this is the agent's last node
            finalize_updates = self._finalize_agent_if_needed(
                state, agent_name, node_name,
            )

            # 7. Build the combined output
            output = dict(result)
            output.update(handoff_updates)
            output.update(finalize_updates)

            # 8. Update current agent tracking
            output["_current_agent"] = agent_name

            # 9. Save context updates
            ctx_updates = self._save_context(state, ctx)
            output.update(ctx_updates)

            # 10. Record confidence if available
            if "quality_score" in result:
                confidence = result["quality_score"] / 100.0
                self._metrics.record_confidence(agent_name, confidence)

            return output

        # Preserve the original function's name for debugging
        wrapper.__name__ = f"orchestrated_{node_name}"
        wrapper.__qualname__ = f"orchestrated_{node_name}"
        wrapper.__wrapped__ = node_func  # type: ignore[attr-defined]

        return wrapper

    def get_agent_summary(self, state: dict[str, Any]) -> dict[str, Any]:
        """Get a summary of all agent contexts for a ticket.

        Useful for debugging and auditing — shows which agents ran,
        what they produced, and how long they took.
        """
        contexts = state.get("agent_contexts", {})
        if not isinstance(contexts, dict):
            return {}

        summary = {}
        for agent_name, ctx_data in contexts.items():
            if isinstance(ctx_data, AgentContext):
                ctx = ctx_data
            elif isinstance(ctx_data, dict):
                ctx = AgentContext.from_dict(ctx_data)
            else:
                continue

            summary[agent_name] = {
                "completed": ctx.is_completed,
                "nodes_run": ctx.get_node_names(),
                "frameworks_used": ctx.get_all_frameworks(),
                "elapsed_ms": round(ctx.elapsed_ms, 2),
                "errors": ctx.error_count,
            }

        return summary

    def get_cross_agent_context(
        self,
        state: dict[str, Any],
        requesting_agent: str,
        target_agent: str,
        field: str,
    ) -> Any:
        """Read a field from another agent's context (cross-agent sharing).

        Agents can READ (not write) outputs from other agents' completed
        nodes. This enables, for example, the Action Agent to read the
        Reasoning Agent's conclusion without tight coupling.

        Args:
            state: The current ticket state.
            requesting_agent: The agent requesting the data.
            target_agent: The agent whose context to read from.
            field: The specific field to look up (searches all node outputs).

        Returns:
            The field value, or None if not found.
        """
        ctx = self.get_agent_context(state, target_agent)
        if ctx is None:
            return None

        # Search all node outputs for the requested field
        for node_name, output in ctx.node_outputs.items():
            if isinstance(output, dict) and field in output:
                value = output[field]
                logger.debug(
                    "Cross-agent read: %s ← %s/%s/%s",
                    requesting_agent, target_agent, node_name, field,
                )
                return value

        return None

    @property
    def recovery(self) -> AgentRecovery:
        """Access the recovery engine for testing."""
        return self._recovery

    def reset(self) -> None:
        """Reset orchestrator state (for testing)."""
        self._recovery.reset()


# Singleton
_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    """Get or create the singleton AgentOrchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


def reset_orchestrator() -> None:
    """Reset the singleton orchestrator (for testing)."""
    global _orchestrator
    _orchestrator = None
