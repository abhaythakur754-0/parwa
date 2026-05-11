"""
PARWA Jarvis Multi-Agent Command Layer (Phase 3)

The real command layer — multi-agentic, LangGraph-based, ZAI SDK-powered.

When Jarvis has awareness of a problem (Phase 2 alert), this layer decides
WHAT TO DO about it by routing to specialized agent nodes. Each agent is a
LangGraph node that can independently reason and take action.

Architecture:
  Awareness Alert → Command Router Agent (ZAI SDK LLM decides which agent)
      → EscalationAgent     — Escalates tickets to humans
      → SLAProtectionAgent  — Protects SLA deadlines
      → QualityRecoveryAgent— Recovers from quality drops
      → ReassignmentAgent   — Reassigns tickets between agents/variants
      → NotificationAgent   — Sends proactive notifications
  → Command Executor — Executes the agent's decision, writes audit trail

This replaces the simple regex-based jarvis_command_service with a proper
multi-agent system where Jarvis THINKS before acting, just like a human
employee would.

BC-001: company_id first parameter on all public methods.
BC-008: Every agent node wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from app.services.jarvis_agents.zai_client import ZAIClient
from app.services.jarvis_agents.command_graph import (
    JarvisCommandGraph,
    get_command_graph,
    run_command_from_alert,
    run_command_from_nl,
)
from app.services.jarvis_agents.command_state import JarvisCommandState

__all__ = [
    "ZAIClient",
    "JarvisCommandGraph",
    "JarvisCommandState",
    "get_command_graph",
    "run_command_from_alert",
    "run_command_from_nl",
]
