"""AgentContext — Per-agent state that accumulates across owned nodes.

Each of the 6 agents maintains its own context bag as it processes nodes.
When a node in the Knowledge Agent runs (FAQ_MATCHER → KB_RETRIEVER →
CONTEXT_MANAGER → INTEGRATION_LOOKUP), each node's output is captured
in the agent's context so subsequent nodes can reference it.

This gives agents a "memory" of what happened in their previous nodes —
something that was previously implicit in the global TicketState.

Key design decisions:
  - AgentContext is read from and written to the global TicketState
    via the `agent_contexts` dict field (keyed by agent name)
  - Each context is a lightweight dict — no Pydantic overhead per agent
  - Contexts are immutable once written (append-only) to prevent
    downstream nodes from corrupting upstream context
  - Contexts are scoped to a single ticket — not shared across tickets

Usage inside a node (automatic via AgentOrchestrator middleware):
    # The orchestrator automatically reads/writes agent context
    # Nodes don't need to interact with AgentContext directly

Usage in agent-level code:
    ctx = AgentContext(agent_name="Knowledge Agent")
    ctx.add_node_output("FAQ_MATCHER", {"faq_match": {...}, "frameworks_used": [...]})
    ctx.add_node_output("KB_RETRIEVER", {"kb_results": [...], "frameworks_used": [...]})
    # Subsequent nodes in this agent can see all previous outputs
    faq_output = ctx.get_node_output("FAQ_MATCHER")
    all_frameworks = ctx.get_all_frameworks()
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("parwa.agents.context")


class AgentContext:
    """Per-agent context that accumulates across owned nodes.

    An AgentContext is created when the first node of an agent starts
    and is finalized when the last node of that agent completes. It
    captures all node outputs, frameworks used, timing, and errors
    within the agent's scope.

    Attributes:
        agent_name: The agent's display name (e.g. "Knowledge Agent").
        node_outputs: OrderedDict of node_name → output_dict.
        node_timings: Dict of node_name → execution_time_ms.
        frameworks_used: List of all frameworks activated in this agent.
        errors: List of errors encountered by this agent's nodes.
        started_at: Timestamp when the first node started.
        completed_at: Timestamp when the last node completed.
    """

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self.node_outputs: dict[str, dict[str, Any]] = {}
        self.node_timings: dict[str, float] = {}
        self.frameworks_used: list[str] = []
        self.errors: list[dict[str, Any]] = []
        self.started_at: float = 0.0
        self.completed_at: float = 0.0
        self._active_node: str | None = None
        self._active_start: float = 0.0

    def start(self) -> None:
        """Mark the agent as started (first node beginning)."""
        if self.started_at == 0.0:
            self.started_at = time.monotonic()
            logger.debug("AgentContext: %s started", self.agent_name)

    def complete(self) -> None:
        """Mark the agent as completed (last node finished)."""
        self.completed_at = time.monotonic()
        logger.debug(
            "AgentContext: %s completed in %.1fms",
            self.agent_name,
            self.elapsed_ms,
        )

    def start_node(self, node_name: str) -> None:
        """Mark a node as starting execution within this agent."""
        self.start()  # Ensure agent is marked as started
        self._active_node = node_name
        self._active_start = time.monotonic()
        logger.debug(
            "AgentContext: %s → %s started",
            self.agent_name, node_name,
        )

    def end_node(self, node_name: str, output: dict[str, Any]) -> None:
        """Record a node's output and timing within this agent."""
        # Record timing
        if self._active_node == node_name and self._active_start > 0:
            elapsed = (time.monotonic() - self._active_start) * 1000
            self.node_timings[node_name] = elapsed
        else:
            self.node_timings[node_name] = 0.0

        # Record output
        self.node_outputs[node_name] = output

        # Track frameworks used in this node
        node_frameworks = output.get("active_frameworks", [])
        if isinstance(node_frameworks, list):
            for fw in node_frameworks:
                if fw not in self.frameworks_used:
                    self.frameworks_used.append(fw)

        # Track errors
        if output.get("node_error"):
            self.errors.append({
                "node": node_name,
                "error": output["node_error"],
            })

        self._active_node = None
        self._active_start = 0.0

        logger.debug(
            "AgentContext: %s → %s completed (%.1fms, %d frameworks)",
            self.agent_name, node_name,
            self.node_timings.get(node_name, 0),
            len(node_frameworks) if isinstance(node_frameworks, list) else 0,
        )

    def add_error(self, node_name: str, error: str) -> None:
        """Record an error from a node within this agent."""
        self.errors.append({
            "node": node_name,
            "error": error,
        })

    def get_node_output(self, node_name: str) -> dict[str, Any] | None:
        """Get a specific node's output from this agent's context."""
        return self.node_outputs.get(node_name)

    def get_all_frameworks(self) -> list[str]:
        """Get all frameworks used across this agent's nodes."""
        return list(self.frameworks_used)

    def get_node_names(self) -> list[str]:
        """Get the names of all nodes that have completed in this agent."""
        return list(self.node_outputs.keys())

    def has_node_completed(self, node_name: str) -> bool:
        """Check if a specific node has completed in this agent."""
        return node_name in self.node_outputs

    def get_total_time_ms(self) -> float:
        """Get total elapsed time for this agent's nodes."""
        return sum(self.node_timings.values())

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time since agent started, or total if completed."""
        if self.completed_at > 0:
            return (self.completed_at - self.started_at) * 1000
        if self.started_at > 0:
            return (time.monotonic() - self.started_at) * 1000
        return 0.0

    @property
    def is_completed(self) -> bool:
        """Check if this agent has completed all its nodes."""
        return self.completed_at > 0

    @property
    def error_count(self) -> int:
        """Number of errors encountered by this agent's nodes."""
        return len(self.errors)

    @property
    def has_errors(self) -> bool:
        """Whether this agent encountered any errors."""
        return len(self.errors) > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the agent context for storage in TicketState."""
        return {
            "agent_name": self.agent_name,
            "node_outputs": self.node_outputs,
            "node_timings": self.node_timings,
            "frameworks_used": self.frameworks_used,
            "errors": self.errors,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "is_completed": self.is_completed,
            "elapsed_ms": self.elapsed_ms,
            "error_count": self.error_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentContext:
        """Deserialize an AgentContext from a dict (e.g. from TicketState)."""
        ctx = cls(agent_name=data.get("agent_name", "Unknown Agent"))
        ctx.node_outputs = data.get("node_outputs", {})
        ctx.node_timings = data.get("node_timings", {})
        ctx.frameworks_used = data.get("frameworks_used", [])
        ctx.errors = data.get("errors", [])
        ctx.started_at = data.get("started_at", 0.0)
        ctx.completed_at = data.get("completed_at", 0.0)
        return ctx

    def __repr__(self) -> str:
        nodes = len(self.node_outputs)
        frameworks = len(self.frameworks_used)
        errors = len(self.errors)
        return (
            f"AgentContext({self.agent_name!r}, "
            f"nodes={nodes}, frameworks={frameworks}, errors={errors})"
        )
