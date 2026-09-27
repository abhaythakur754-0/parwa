"""
PARWA Jarvis Multi-Agent Command Layer (Phase 4)

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
      → PipelineQueryAgent  — Queries variant pipeline state (Phase 4)
  → ApprovalGate (Phase 4) — Human-in-the-loop approval check
  → Command Executor — Executes the agent's decision, writes audit trail

Phase 4 — Jarvis↔Variant LangGraph Integration:
  - variant_bridge: Bidirectional bridge between command graph and main pipeline
  - approval_gate: Human-in-the-loop approval based on variant tier
  - pipeline_query_agent: Agent-to-agent communication channel
  - pipeline_feedback: Feedback loop from command execution back to pipeline
  - jarvis_awareness_injector: Main pipeline node that reads Jarvis state

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

# Phase 4: Bridge and feedback modules
from app.services.jarvis_agents.variant_bridge import (
    inject_jarvis_state_into_pipeline,
    read_pipeline_state_for_jarvis,
    sync_awareness_to_pipeline,
    apply_command_to_pipeline_state,
    get_variant_aware_command_config,
    check_jarvis_approval_needed,
    inject_jarvis_state_sync,
    read_pipeline_state_sync,
    sync_awareness_sync,
    apply_command_sync,
)
from app.services.jarvis_agents.pipeline_feedback import (
    apply_command_feedback,
    apply_command_feedback_sync,
    get_feedback_history,
)

__all__ = [
    "ZAIClient",
    "JarvisCommandGraph",
    "JarvisCommandState",
    "get_command_graph",
    "run_command_from_alert",
    "run_command_from_nl",
    # Phase 4: Bridge
    "inject_jarvis_state_into_pipeline",
    "read_pipeline_state_for_jarvis",
    "sync_awareness_to_pipeline",
    "apply_command_to_pipeline_state",
    "get_variant_aware_command_config",
    "check_jarvis_approval_needed",
    "inject_jarvis_state_sync",
    "read_pipeline_state_sync",
    "sync_awareness_sync",
    "apply_command_sync",
    # Phase 4: Feedback
    "apply_command_feedback",
    "apply_command_feedback_sync",
    "get_feedback_history",
]
