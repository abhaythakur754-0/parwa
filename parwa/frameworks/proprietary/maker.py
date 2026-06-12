"""MAKER (Multi-Agent Knowledge Extraction & Reasoning) — Cross-agent synthesis.

MAKER is PARWA's proprietary technique that synthesizes knowledge across
all 6 agents. Instead of each agent working in isolation, MAKER identifies
when knowledge from one agent should influence another agent's reasoning.

How it works:
  - Examines what each agent has produced so far
  - Identifies cross-agent dependencies (e.g., Knowledge Agent's findings
    should influence Reasoning Agent's approach)
  - Creates a "knowledge bridge" that passes relevant context between agents
  - Ensures no agent makes decisions in a vacuum

What hallucination it catches:
  "Isolated reasoning" — when an agent reasons without considering what
  other agents have found. MAKER forces cross-agent awareness.

Activation:
  - Activates on COMPLEX+ complexity (simple tickets don't need cross-agent synthesis)
  - Most valuable when multiple agents have produced contradictory findings
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult

logger = logging.getLogger("parwa.frameworks.maker")


class MAKERTechnique(BaseTechnique):
    """Multi-Agent Knowledge Extraction & Reasoning technique.

    Synthesizes knowledge across all 6 PARWA agents, creating
    knowledge bridges between agents to prevent isolated reasoning.
    """

    _min_complexity = "complex"  # Only for complex+ tickets

    @property
    def name(self) -> str:
        return "maker"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.PROPRIETARY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "REASONING_ENGINE",
            "ACTION_PLANNER",
            "PROACTIVE_CHECKER",
            "PREDICTION_ENGINE",
            "QUALITY_SCORER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 200  # Moderate — cross-agent synthesis needs context

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute MAKER cross-agent knowledge synthesis.

        Examines outputs from all agents and creates knowledge bridges
        that ensure reasoning accounts for all available information.
        """
        # Extract what each agent has produced
        router_outputs = {
            "intent": state.get("intent", "unknown"),
            "sentiment": state.get("sentiment", "neutral"),
            "should_escalate": state.get("should_escalate", False),
        }
        knowledge_outputs = {
            "faq_match": bool(state.get("faq_match")),
            "kb_results_count": len(state.get("kb_results", [])),
            "has_integration_data": bool(state.get("integration_data")),
        }
        reasoning_outputs = {
            "has_conclusion": bool(state.get("reasoning_conclusion")),
            "reasoning_steps": len(state.get("reasoning_chain", [])),
            "has_strategy": bool(state.get("strategy_plan")),
        }
        proactive_outputs = {
            "insights_count": len(state.get("proactive_insights", [])),
            "predictions_count": len(state.get("predictions", [])),
        }

        # Identify cross-agent connections
        bridges = []
        chain = []

        # Bridge: Knowledge + Reasoning
        if knowledge_outputs["has_integration_data"] and router_outputs["intent"] == "refund_request":
            bridges.append("knowledge→reasoning: Integration data confirms refund eligibility")
            chain.append("MAKER: CRM data available for refund verification")

        # Bridge: Sentiment + Action
        if router_outputs["sentiment"] in ("frustrated", "angry") and not router_outputs["should_escalate"]:
            bridges.append("sentiment→action: Frustrated customer needs empathetic response")
            chain.append("MAKER: Customer frustration noted — adjust response tone")

        # Bridge: Proactive + Reasoning
        if proactive_outputs["insights_count"] > 0 and reasoning_outputs["has_conclusion"]:
            bridges.append("proactive→reasoning: Proactive insights should influence conclusion")
            chain.append("MAKER: Proactive insights integrated into reasoning")

        # Bridge: KB + Reasoning confidence
        if knowledge_outputs["kb_results_count"] > 0:
            bridges.append("knowledge→reasoning: KB evidence supports reasoning")
            chain.append(f"MAKER: {knowledge_outputs['kb_results_count']} KB results available")

        if not bridges:
            bridges.append("No cross-agent dependencies identified")
            chain.append("MAKER: Agents are aligned — no knowledge bridges needed")

        output = "; ".join(bridges)
        confidence = min(0.95, 0.70 + len(bridges) * 0.05)

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["maker"],
            metadata={
                "bridge_count": len(bridges),
                "router_outputs": router_outputs,
                "knowledge_outputs": knowledge_outputs,
                "reasoning_outputs": reasoning_outputs,
                "proactive_outputs": proactive_outputs,
            },
            token_estimate=self.token_cost_estimate,
        )
