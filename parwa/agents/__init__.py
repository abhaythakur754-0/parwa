"""PARWA Agent definitions and orchestration layer.

6 Agents, each owning specific nodes. All 6 agents work simultaneously
on every ticket on every variant. The concurrency number (3/4/6) refers
to concurrent TICKETS, not agents.

Phase 6: Added Agent Orchestration Layer:
  - AgentContext: Per-agent state that accumulates across owned nodes
  - AgentOrchestrator: Coordinates agents, manages handoffs & cross-agent sharing
  - AgentRecovery: Agent-level error recovery (retry/skip/redirect/degrade/escalate)
  - AgentMetrics: Per-agent performance tracking (latency, errors, frameworks)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from parwa.agents.context import AgentContext
from parwa.agents.orchestrator import (
    AgentOrchestrator,
    get_orchestrator,
    reset_orchestrator,
)
from parwa.agents.metrics import (
    AgentMetrics,
    get_agent_metrics,
    reset_agent_metrics,
)
from parwa.agents.recovery import (
    AgentRecovery,
    RecoveryStrategy,
    RecoveryDecision,
)


@dataclass
class Agent:
    """A PARWA agent that owns a set of nodes."""
    name: str
    emoji: str
    node_ids: list[int]
    node_names: list[str]
    primary_role: str


# ─── 6 Agent Definitions ─────────────────────────────────────────────────────────

ROUTER_AGENT = Agent(
    name="Router Agent",
    emoji="🧭",
    node_ids=[1, 2, 18, 20],
    node_names=["INGEST", "INTENT_CLASSIFIER", "SENTIMENT_ANALYZER", "ESCALATION_DECISION"],
    primary_role="Decides where the ticket goes, classifies intent, detects emotion, and determines if escalation is needed",
)

KNOWLEDGE_AGENT = Agent(
    name="Knowledge Agent",
    emoji="📚",
    node_ids=[3, 4, 19, 5],
    node_names=["FAQ_MATCHER", "KB_RETRIEVER", "CONTEXT_MANAGER", "INTEGRATION_LOOKUP"],
    primary_role="Finds and manages all information: FAQs, knowledge base, conversation history, and data from connected systems",
)

REASONING_AGENT = Agent(
    name="Reasoning Agent",
    emoji="🧠",
    node_ids=[6, 10, 12, 11],
    node_names=["REASONING_ENGINE", "REVERSE_THINKER", "TREE_OF_THOUGHTS", "STRATEGY_PLANNER"],
    primary_role="The brain — thinks through problems using all frameworks, explores multiple paths, plans strategies",
)

ACTION_AGENT = Agent(
    name="Action Agent",
    emoji="⚡",
    node_ids=[7, 8, 9],
    node_names=["ACTION_PLANNER", "ACTION_EXECUTOR", "ACTION_VERIFIER"],
    primary_role="Plans actions, executes them (or recommends if permission-gated), verifies the result",
)

COMPLIANCE_AGENT = Agent(
    name="Compliance Agent",
    emoji="🛡️",
    node_ids=[15, 16, 21, 17],
    node_names=["PII_COMPLIANCE_GUARD", "AUDIT_LOGGER", "QUALITY_SCORER", "RESPONSE_FORMATTER"],
    primary_role="Ensures everything is legal, compliant, high-quality, and properly formatted before sending",
)

PROACTIVE_AGENT = Agent(
    name="Proactive Agent",
    emoji="🔮",
    node_ids=[13, 14, 22],
    node_names=["PROACTIVE_CHECKER", "PREDICTION_ENGINE", "FEEDBACK_LOOP"],
    primary_role="Anticipates future needs, predicts follow-up issues, captures feedback for continuous improvement",
)

ALL_AGENTS = [ROUTER_AGENT, KNOWLEDGE_AGENT, REASONING_AGENT, ACTION_AGENT, COMPLIANCE_AGENT, PROACTIVE_AGENT]

# Map node_id → agent
NODE_TO_AGENT: dict[int, Agent] = {}
for agent in ALL_AGENTS:
    for nid in agent.node_ids:
        NODE_TO_AGENT[nid] = agent

__all__ = [
    # Agent definitions
    "Agent",
    "ROUTER_AGENT",
    "KNOWLEDGE_AGENT",
    "REASONING_AGENT",
    "ACTION_AGENT",
    "COMPLIANCE_AGENT",
    "PROACTIVE_AGENT",
    "ALL_AGENTS",
    "NODE_TO_AGENT",
    # Phase 6: Agent Orchestration
    "AgentContext",
    "AgentOrchestrator",
    "get_orchestrator",
    "reset_orchestrator",
    "AgentMetrics",
    "get_agent_metrics",
    "reset_agent_metrics",
    "AgentRecovery",
    "RecoveryStrategy",
    "RecoveryDecision",
]
