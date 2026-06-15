"""Unified Subgraph Dispatcher — Routes and runs tickets through the right subgraph.

This is the main entry point for the subgraph architecture. It:
  1. Routes the ticket to the correct subgraph using SubgraphRouter
  2. Injects the specialized system prompt from PromptAdjuster
  3. Runs the ticket through the subgraph
  4. Records the outcome in FeedbackCollector
  5. Triggers the self-improvement loop if enough data has accumulated

Usage:
    from parwa.subgraphs.dispatcher import SubgraphDispatcher

    dispatcher = SubgraphDispatcher()
    result = await dispatcher.process({
        "raw_message": "I want a refund for my subscription",
        "ticket_id": "TICKET-123",
    })
"""

from __future__ import annotations

import logging
import os
from typing import Any

from parwa.subgraphs.router import SubgraphRouter, route_to_subgraph
from parwa.subgraphs.refund_graph import RefundGraph
from parwa.subgraphs.tech_graph import TechGraph
from parwa.subgraphs.billing_graph import BillingGraph
from parwa.subgraphs.general_graph import GeneralGraph
from parwa.subgraphs.prompts import (
    REFUND_SYSTEM_PROMPT, TECH_SYSTEM_PROMPT,
    BILLING_SYSTEM_PROMPT, GENERAL_SYSTEM_PROMPT,
)
from parwa.self_improvement.feedback_collector import FeedbackCollector, TicketOutcome, OutcomeType
from parwa.self_improvement.pattern_learner import PatternLearner
from parwa.self_improvement.prompt_adjuster import PromptAdjuster
from parwa.self_improvement.technique_tuner import TechniqueTuner

logger = logging.getLogger("parwa.subgraphs.dispatcher")

# Minimum outcomes before self-improvement kicks in
_IMPROVEMENT_MIN_OUTCOMES = 10

# How often to run the improvement cycle (in number of outcomes)
_IMPROVEMENT_INTERVAL = 20


class SubgraphDispatcher:
    """Main entry point: routes and processes tickets through subgraphs.

    The dispatcher orchestrates the entire flow:
      1. Route → 2. Process → 3. Record → 4. Improve (periodically)

    It maintains references to all 4 subgraphs and the self-improvement
    components. In production, these would be shared across worker processes.
    """

    def __init__(self, data_dir: str | None = None) -> None:
        # Initialize subgraphs
        self._refund_graph = RefundGraph()
        self._tech_graph = TechGraph()
        self._billing_graph = BillingGraph()
        self._general_graph = GeneralGraph()

        # Initialize self-improvement components
        storage_dir = data_dir or os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(storage_dir, exist_ok=True)

        self._collector = FeedbackCollector(
            storage_path=os.path.join(storage_dir, "feedback.json")
        )
        self._prompt_adjuster = PromptAdjuster(
            storage_path=os.path.join(storage_dir, "prompt_adjustments.json")
        )
        self._technique_tuner = TechniqueTuner(
            collector=self._collector,
            storage_path=os.path.join(storage_dir, "technique_adjustments.json"),
        )
        self._pattern_learner = PatternLearner(self._collector)

        self._process_count = 0

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process a ticket through the subgraph architecture.

        Args:
            state: Ticket state dict. Must have at least 'raw_message'.
                   Can optionally have 'ticket_id', 'intent', 'complexity'.

        Returns:
            Updated state with resolution, response, and metadata.
        """
        ticket_id = state.get("ticket_id", f"T-{id(state)}")

        # Step 1: Route to the correct subgraph
        subgraph_name = await route_to_subgraph(state)
        state["_subgraph"] = subgraph_name

        # Step 2: Inject specialized system prompt (with adjustments)
        base_prompts = {
            "refund": REFUND_SYSTEM_PROMPT,
            "tech": TECH_SYSTEM_PROMPT,
            "billing": BILLING_SYSTEM_PROMPT,
            "general": GENERAL_SYSTEM_PROMPT,
        }
        base_prompt = base_prompts.get(subgraph_name, GENERAL_SYSTEM_PROMPT)
        state["_system_prompt"] = self._prompt_adjuster.get_adjusted_prompt(
            subgraph_name, base_prompt
        )

        # Step 3: Inject technique configuration
        state["_technique_priorities"] = self._technique_tuner.get_techniques(
            subgraph_name, "REASONING_ENGINE"
        )
        state["_technique_cap"] = self._technique_tuner.get_cap(
            subgraph_name, state.get("complexity", "simple")
        )

        logger.info(
            "dispatcher: processing ticket=%s subgraph=%s complexity=%s",
            ticket_id, subgraph_name, state.get("complexity", "simple"),
        )

        # Step 4: Run through the subgraph
        try:
            subgraph_map = {
                "refund": self._refund_graph,
                "tech": self._tech_graph,
                "billing": self._billing_graph,
                "general": self._general_graph,
            }
            subgraph = subgraph_map.get(subgraph_name, self._general_graph)
            result = await subgraph.process(state)

            # Merge result with input state
            state.update(result)

        except Exception as exc:
            logger.error("dispatcher: subgraph %s failed for ticket=%s: %s", subgraph_name, ticket_id, exc)
            state["final_response"] = "I apologize, but I encountered an issue processing your request. A team member will follow up with you shortly."
            state["quality_score"] = 0.0

        # Step 5: Record the outcome
        outcome = self._determine_outcome(state)
        self._collector.record(TicketOutcome(
            ticket_id=ticket_id,
            intent=state.get("intent", "unknown"),
            subgraph=subgraph_name,
            outcome=outcome,
            message=state.get("raw_message", ""),
            techniques_used=state.get("active_frameworks", []),
            quality_score=state.get("quality_score", 0.0),
            confidence=state.get("intent_confidence", 0.0),
            complexity=state.get("complexity", "simple"),
            kb_results_count=len(state.get("kb_results", [])),
            response=state.get("final_response", ""),
        ))

        # Step 6: Trigger self-improvement if enough data accumulated
        self._process_count += 1
        if self._process_count % _IMPROVEMENT_INTERVAL == 0:
            await self._run_improvement_cycle()

        return state

    def _determine_outcome(self, state: dict[str, Any]) -> OutcomeType:
        """Determine the outcome type from the final state."""
        quality_score = state.get("quality_score", 0.0)
        execution_results = state.get("execution_results", [])
        was_escalated = any(
            r.get("action") == "escalate_to_human" for r in execution_results if isinstance(r, dict)
        )

        if was_escalated:
            return OutcomeType.ESCALATED
        elif quality_score >= 80:
            return OutcomeType.RESOLVED
        elif quality_score >= 60:
            return OutcomeType.PARTIAL
        else:
            return OutcomeType.ESCALATED

    async def _run_improvement_cycle(self) -> None:
        """Run the self-improvement cycle: learn → adjust → tune."""
        total = self._collector.total_outcomes
        if total < _IMPROVEMENT_MIN_OUTCOMES:
            logger.info("dispatcher: skipping improvement cycle (only %d outcomes, need %d)", total, _IMPROVEMENT_MIN_OUTCOMES)
            return

        logger.info("dispatcher: running self-improvement cycle with %d outcomes", total)

        # Step 1: Learn patterns from failures
        patterns = self._pattern_learner.analyze(days=30)

        # Step 2: Generate prompt adjustments
        prompt_adjustments = self._prompt_adjuster.generate_adjustments(patterns)

        # Step 3: Apply high-confidence prompt adjustments
        for adj in prompt_adjustments:
            if adj.confidence >= 0.6:
                self._prompt_adjuster.apply(adj)

        # Step 4: Generate technique adjustments
        technique_adjustments = self._technique_tuner.analyze(days=30)

        # Step 5: Apply high-confidence technique adjustments
        for adj in technique_adjustments:
            if adj.confidence >= 0.6:
                self._technique_tuner.apply(adj)

        logger.info(
            "dispatcher: improvement cycle complete — %d patterns, %d prompt adjustments, %d technique adjustments",
            len(patterns),
            len([a for a in prompt_adjustments if a.status == "applied"]),
            len([a for a in technique_adjustments if a.status == "applied"]),
        )

    def get_status(self) -> dict[str, Any]:
        """Get the current status of the dispatcher and all components."""
        return {
            "process_count": self._process_count,
            "feedback_summary": self._collector.summary(),
            "prompt_adjustments": self._prompt_adjuster.summary(),
            "technique_tuning": self._technique_tuner.summary(),
            "current_resolution_rate": self._collector.resolution_rate(days=30),
            "resolution_by_subgraph": self._collector.resolution_rate_by_subgraph(days=30),
        }
