"""Technique Tuner — Automatically adjusts technique priorities based on outcomes.

When the PatternLearner identifies that certain techniques consistently fail
for specific ticket types, the TechniqueTuner adjusts the technique priority
order so that more effective techniques run first.

For example:
  - If CoT alone fails for refund tickets → bump Reverse Thinking to run alongside CoT
  - If ReAct takes too long for simple tech tickets → reduce ReAct priority for simple complexity
  - If Self-Consistency improves billing resolution → move it higher in priority

This is a feedback-driven optimization loop that runs automatically.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from parwa.self_improvement.feedback_collector import FeedbackCollector, OutcomeType
from parwa.self_improvement.pattern_learner import FailurePattern
from parwa.subgraphs.technique_configs import SUBGRAPH_TECHNIQUE_PRIORITIES, SUBGRAPH_TECHNIQUE_CAPS

logger = logging.getLogger("parwa.self_improvement.technique_tuner")


@dataclass
class TechniqueAdjustment:
    """A technique priority adjustment.

    Attributes:
        adjustment_id: Unique identifier.
        subgraph: Which subgraph's technique config to adjust.
        node: Which node's technique list to adjust.
        change_type: Type of change (promote, demote, add, remove, increase_cap, decrease_cap).
        technique: Which technique is affected.
        details: Human-readable description of the change.
        confidence: How confident we are this will help (0-1).
        status: Current status (pending, applied, verified, rejected).
    """
    adjustment_id: str = ""
    subgraph: str = ""
    node: str = ""
    change_type: str = "promote"  # promote, demote, add, remove, increase_cap, decrease_cap
    technique: str = ""
    details: str = ""
    confidence: float = 0.5
    status: str = "pending"


class TechniqueTuner:
    """Tunes technique priorities based on outcome data.

    The tuner uses two signals:
      1. Which techniques are used in successful resolutions
      2. Which techniques are missing from escalations

    If a technique consistently appears in successful resolutions but
    isn't being used enough, it gets promoted. If a technique appears
    in many escalations, alternatives get promoted instead.

    Usage:
        tuner = TechniqueTuner(collector)
        adjustments = tuner.analyze(days=7)
        for adj in adjustments:
            if adj.confidence > 0.6:
                tuner.apply(adj)
    """

    def __init__(
        self,
        collector: FeedbackCollector,
        storage_path: str | None = None,
    ) -> None:
        self.collector = collector
        self._storage_path = storage_path
        self._custom_priorities: dict[str, dict[str, list[str]]] = {}
        self._custom_caps: dict[str, dict[str, int]] = {}

        if storage_path and os.path.exists(storage_path):
            self._load()

    def analyze(self, days: int = 7) -> list[TechniqueAdjustment]:
        """Analyze outcomes and propose technique adjustments.

        Args:
            days: How many days of data to analyze.

        Returns:
            List of proposed technique adjustments.
        """
        adjustments: list[TechniqueAdjustment] = []
        recent = self.collector.get_recent(days)

        if not recent:
            return adjustments

        resolved = [o for o in recent if o.outcome in (OutcomeType.RESOLVED, OutcomeType.LOOP_RESOLVED)]
        escalated = [o for o in recent if o.outcome == OutcomeType.ESCALATED]

        # Signal 1: Techniques that appear in successful resolutions
        successful_techniques: dict[str, int] = {}
        for o in resolved:
            for tech in o.techniques_used:
                successful_techniques[tech] = successful_techniques.get(tech, 0) + 1

        # Signal 2: Techniques that appear in escalations (may be insufficient)
        failed_techniques: dict[str, int] = {}
        for o in escalated:
            for tech in o.techniques_used:
                failed_techniques[tech] = failed_techniques.get(tech, 0) + 1

        # Generate adjustments per subgraph
        for subgraph in ("refund", "tech", "billing", "general"):
            sub_adjustments = self._analyze_subgraph(
                subgraph, resolved, escalated, successful_techniques, failed_techniques,
            )
            adjustments.extend(sub_adjustments)

        # Sort by confidence
        adjustments.sort(key=lambda a: a.confidence, reverse=True)

        logger.info(
            "technique_tuner: generated %d adjustments from %d resolved, %d escalated",
            len(adjustments), len(resolved), len(escalated),
        )

        return adjustments

    def _analyze_subgraph(
        self,
        subgraph: str,
        resolved: list[Any],
        escalated: list[Any],
        success_techs: dict[str, int],
        fail_techs: dict[str, int],
    ) -> list[TechniqueAdjustment]:
        """Analyze technique effectiveness for a specific subgraph."""
        adjustments: list[TechniqueAdjustment] = []

        subgraph_resolved = [o for o in resolved if o.subgraph == subgraph]
        subgraph_escalated = [o for o in escalated if o.subgraph == subgraph]

        if not subgraph_escalated:
            return adjustments  # No failures = no changes needed

        # Count techniques in this subgraph's failures
        sub_fail_techs: dict[str, int] = {}
        for o in subgraph_escalated:
            for tech in o.techniques_used:
                sub_fail_techs[tech] = sub_fail_techs.get(tech, 0) + 1

        # Count techniques in this subgraph's successes
        sub_success_techs: dict[str, int] = {}
        for o in subgraph_resolved:
            for tech in o.techniques_used:
                sub_success_techs[tech] = sub_success_techs.get(tech, 0) + 1

        # Rule 1: If a technique appears in many failures but few successes, demote it
        for tech, fail_count in sub_fail_techs.items():
            success_count = sub_success_techs.get(tech, 0)
            if fail_count > success_count * 2 and fail_count >= 2:
                # Find alternative technique to promote
                alternatives = self._find_alternative(tech, subgraph)
                for alt in alternatives:
                    adjustments.append(TechniqueAdjustment(
                        adjustment_id=f"tech_{subgraph}_demote_{tech}_promote_{alt}",
                        subgraph=subgraph,
                        node="REASONING_ENGINE",
                        change_type="promote",
                        technique=alt,
                        details=f"'{tech}' fails often in {subgraph} — promote '{alt}' as alternative",
                        confidence=min(0.4 + (fail_count * 0.1), 0.85),
                        status="pending",
                    ))

        # Rule 2: If a technique appears in many successes but not in failures, promote it
        for tech, success_count in sub_success_techs.items():
            fail_count = sub_fail_techs.get(tech, 0)
            if success_count > fail_count * 2 and success_count >= 3:
                adjustments.append(TechniqueAdjustment(
                    adjustment_id=f"tech_{subgraph}_promote_{tech}",
                    subgraph=subgraph,
                    node="REASONING_ENGINE",
                    change_type="promote",
                    technique=tech,
                    details=f"'{tech}' succeeds often in {subgraph} — promote to higher priority",
                    confidence=min(0.5 + (success_count * 0.05), 0.9),
                    status="pending",
                ))

        # Rule 3: If subgraph has high escalation rate for complex tickets, increase technique cap
        complex_escalated = [o for o in subgraph_escalated if o.complexity in ("complex", "critical")]
        if len(complex_escalated) >= 2:
            adjustments.append(TechniqueAdjustment(
                adjustment_id=f"tech_{subgraph}_increase_cap",
                subgraph=subgraph,
                node="REASONING_ENGINE",
                change_type="increase_cap",
                technique="",
                details=f"{len(complex_escalated)} complex/critical tickets escalated in {subgraph} — increase technique cap",
                confidence=0.6,
                status="pending",
            ))

        return adjustments

    def _find_alternative(self, failing_technique: str, subgraph: str) -> list[str]:
        """Find alternative techniques for a failing one."""
        # Map of technique alternatives
        alternatives_map = {
            "chain_of_thought": ["reverse_thinking", "self_consistency"],
            "react": ["chain_of_thought", "tree_of_thoughts"],
            "tree_of_thoughts": ["react", "uncertainty_of_thought"],
            "reverse_thinking": ["chain_of_thought", "self_consistency"],
            "uncertainty_of_thought": ["tree_of_thoughts", "graph_of_strategic_thought"],
        }

        return alternatives_map.get(failing_technique, ["chain_of_thought"])

    def apply(self, adjustment: TechniqueAdjustment) -> None:
        """Apply a technique adjustment to the configuration.

        This modifies the in-memory technique priorities and caps.
        In production, this would be persisted and picked up by running pipelines.
        """
        subgraph = adjustment.subgraph
        node = adjustment.node

        # Initialize custom config if needed
        if subgraph not in self._custom_priorities:
            # Start with a deep copy of the defaults
            self._custom_priorities[subgraph] = copy.deepcopy(
                SUBGRAPH_TECHNIQUE_PRIORITIES.get(subgraph, {})
            )
        if subgraph not in self._custom_caps:
            self._custom_caps[subgraph] = copy.deepcopy(
                SUBGRAPH_TECHNIQUE_CAPS.get(subgraph, {})
            )

        if adjustment.change_type == "promote" and adjustment.technique:
            # Move the technique to the front of the list for this node
            node_techniques = self._custom_priorities[subgraph].get(node, [])
            if adjustment.technique in node_techniques:
                node_techniques.remove(adjustment.technique)
            node_techniques.insert(0, adjustment.technique)
            self._custom_priorities[subgraph][node] = node_techniques

        elif adjustment.change_type == "demote" and adjustment.technique:
            # Move the technique to the end of the list
            node_techniques = self._custom_priorities[subgraph].get(node, [])
            if adjustment.technique in node_techniques:
                node_techniques.remove(adjustment.technique)
                node_techniques.append(adjustment.technique)
            self._custom_priorities[subgraph][node] = node_techniques

        elif adjustment.change_type == "add" and adjustment.technique:
            node_techniques = self._custom_priorities[subgraph].get(node, [])
            if adjustment.technique not in node_techniques:
                node_techniques.append(adjustment.technique)
            self._custom_priorities[subgraph][node] = node_techniques

        elif adjustment.change_type == "increase_cap":
            for complexity in ("complex", "critical"):
                current = self._custom_caps[subgraph].get(complexity, 3)
                self._custom_caps[subgraph][complexity] = min(current + 1, 5)

        elif adjustment.change_type == "decrease_cap":
            for complexity in ("simple", "medium"):
                current = self._custom_caps[subgraph].get(complexity, 2)
                self._custom_caps[subgraph][complexity] = max(current - 1, 1)

        adjustment.status = "applied"

        logger.info(
            "technique_tuner: applied %s (%s) for subgraph=%s node=%s",
            adjustment.adjustment_id, adjustment.change_type,
            adjustment.subgraph, adjustment.node,
        )

        if self._storage_path:
            self._save()

    def get_techniques(self, subgraph: str, node: str) -> list[str]:
        """Get the (possibly adjusted) technique list for a subgraph+node."""
        if subgraph in self._custom_priorities:
            return self._custom_priorities[subgraph].get(node, [])
        return SUBGRAPH_TECHNIQUE_PRIORITIES.get(subgraph, {}).get(node, [])

    def get_cap(self, subgraph: str, complexity: str) -> int:
        """Get the (possibly adjusted) technique cap for a subgraph+complexity."""
        if subgraph in self._custom_caps:
            return self._custom_caps[subgraph].get(complexity, 2)
        return SUBGRAPH_TECHNIQUE_CAPS.get(subgraph, {}).get(complexity, 2)

    def summary(self) -> dict[str, Any]:
        """Get a summary of technique adjustments."""
        return {
            "custom_subgraphs": list(self._custom_priorities.keys()),
            "custom_priorities": self._custom_priorities,
            "custom_caps": self._custom_caps,
        }

    def _save(self) -> None:
        """Persist custom config to JSON."""
        if not self._storage_path:
            return
        try:
            data = {
                "custom_priorities": self._custom_priorities,
                "custom_caps": self._custom_caps,
            }
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            with open(self._storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            logger.warning("technique_tuner: failed to save: %s", exc)

    def _load(self) -> None:
        """Load custom config from JSON."""
        if not self._storage_path or not os.path.exists(self._storage_path):
            return
        try:
            with open(self._storage_path) as f:
                data = json.load(f)
            self._custom_priorities = data.get("custom_priorities", {})
            self._custom_caps = data.get("custom_caps", {})
            logger.info("technique_tuner: loaded custom config for subgraphs: %s", list(self._custom_priorities.keys()))
        except Exception as exc:
            logger.warning("technique_tuner: failed to load: %s", exc)
