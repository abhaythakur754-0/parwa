"""
PARWA Onboarding Jarvis — Agentic Multi-Agent System

The Onboarding Jarvis is built in the same agentic format as the post-onboarding
Jarvis. Each AI capability is an agent/node in a LangGraph graph that:
  - Reasons via LLM (ZAI SDK) to make intelligent decisions
  - Has awareness of the client's demo context (variant, entry source, industry)
  - Can take actions (book demo call, select variants, pitch product, etc.)
  - Falls back to rule-based logic when LLM fails (BC-008)

Graph Topology:
  START → onboarding_router → [agent_selector] → specialist_agent
        → onboarding_executor → END

  Specialist Agents:
    - guide_agent:     Walks user through PARWA features naturally
    - salesman_agent:  Demonstrates value, handles objections, pitches
    - demo_agent:      Roleplays as customer care agent in realistic scenarios
    - call_agent:      Handles voice call demo with sales pitch
    - awareness_agent: Tracks demo context, detects stage, enriches state

  All specialist agents flow to onboarding_executor which takes the
  agent's decision and executes it (create ticket, book call, show
  bill summary, upload docs, etc.)

BC-001: company_id first parameter on all public methods.
BC-008: Every node wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from app.services.onboarding_jarvis.onboarding_graph import (
    OnboardingJarvisGraph,
    get_onboarding_graph,
    run_onboarding_from_message,
)
from app.services.onboarding_jarvis.onboarding_state import (
    OnboardingJarvisState,
    create_onboarding_state,
)

__all__ = [
    "OnboardingJarvisGraph",
    "get_onboarding_graph",
    "run_onboarding_from_message",
    "OnboardingJarvisState",
    "create_onboarding_state",
]
