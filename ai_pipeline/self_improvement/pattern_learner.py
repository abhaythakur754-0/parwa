"""Pattern Learner — Identifies failure patterns in escalated tickets.

The pattern learner analyzes tickets that were escalated to humans and
identifies common patterns:

  - "Refund tickets with 'subscription' keyword fail 40% of the time"
  - "Tech tickets with error code 500 always get escalated"
  - "Billing tickets on weekends have lower resolution rates"

These patterns drive the PromptAdjuster and TechniqueTuner to make
targeted improvements.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from parwa.self_improvement.feedback_collector import (
    FeedbackCollector,
    OutcomeType,
    TicketOutcome,
)

logger = logging.getLogger("parwa.self_improvement.pattern_learner")


@dataclass
class FailurePattern:
    """A identified pattern in failed tickets.

    Attributes:
        pattern_id: Unique identifier for this pattern.
        subgraph: Which subgraph this pattern was found in.
        description: Human-readable description of the pattern.
        frequency: How often this pattern appears in failures.
        impact: Estimated resolution rate improvement if fixed.
        evidence: Example ticket IDs that match this pattern.
        suggested_fix: What to change to fix this pattern.
    """
    pattern_id: str = ""
    subgraph: str = ""
    description: str = ""
    frequency: int = 0
    impact: float = 0.0
    evidence: list[str] = field(default_factory=list)
    suggested_fix: str = ""


class PatternLearner:
    """Learns from failed tickets to identify improvement opportunities.

    The learner runs on a schedule (e.g., nightly) and produces a list
    of FailurePatterns that the PromptAdjuster and TechniqueTuner can act on.

    Usage:
        learner = PatternLearner(collector)
        patterns = learner.analyze(days=7)
        for pattern in patterns:
            print(f"{pattern.description}: frequency={pattern.frequency}, impact={pattern.impact}")
    """

    def __init__(self, collector: FeedbackCollector) -> None:
        self.collector = collector

    def analyze(self, days: int = 7) -> list[FailurePattern]:
        """Analyze recent failures and identify patterns.

        Args:
            days: How many days of data to analyze.

        Returns:
            List of identified failure patterns, sorted by impact.
        """
        patterns: list[FailurePattern] = []

        escalated = [
            o for o in self.collector.get_recent(days)
            if o.outcome == OutcomeType.ESCALATED
        ]

        if not escalated:
            logger.info("pattern_learner: no escalations in last %d days", days)
            return patterns

        # Pattern 1: Subgraph-specific failure rates
        patterns.extend(self._subgraph_failure_patterns(escalated, days))

        # Pattern 2: Technique gap patterns (missing techniques)
        patterns.extend(self._technique_gap_patterns(escalated))

        # Pattern 3: Keyword-based failure patterns
        patterns.extend(self._keyword_failure_patterns(escalated))

        # Pattern 4: Complexity mismatch patterns
        patterns.extend(self._complexity_mismatch_patterns(escalated))

        # Pattern 5: Low KB retrieval patterns
        patterns.extend(self._kb_retrieval_patterns(escalated))

        # Sort by impact (highest first)
        patterns.sort(key=lambda p: p.impact, reverse=True)

        logger.info(
            "pattern_learner: found %d patterns from %d escalations",
            len(patterns), len(escalated),
        )

        return patterns

    def _subgraph_failure_patterns(
        self, escalated: list[TicketOutcome], days: int
    ) -> list[FailurePattern]:
        """Identify subgraphs with high escalation rates."""
        patterns = []
        rates = self.collector.resolution_rate_by_subgraph(days)

        for subgraph, rate in rates.items():
            if rate < 0.5:  # Less than 50% resolution rate
                patterns.append(FailurePattern(
                    pattern_id=f"subgraph_low_res_{subgraph}",
                    subgraph=subgraph,
                    description=f"Subgraph '{subgraph}' has low resolution rate ({rate:.0%})",
                    frequency=sum(1 for o in escalated if o.subgraph == subgraph),
                    impact=(0.5 - rate) * 100,  # Potential improvement
                    evidence=[o.ticket_id for o in escalated if o.subgraph == subgraph][:5],
                    suggested_fix=f"Review and optimize {subgraph} subgraph prompts and technique priorities",
                ))

        return patterns

    def _technique_gap_patterns(self, escalated: list[TicketOutcome]) -> list[FailurePattern]:
        """Identify cases where more/better techniques might have helped."""
        patterns = []

        # Group by which techniques were used
        technique_outcomes: dict[str, list[str]] = {}
        for o in escalated:
            key = ",".join(sorted(o.techniques_used)) if o.techniques_used else "none"
            technique_outcomes.setdefault(key, []).append(o.ticket_id)

        # If many escalations used the same techniques, those techniques may be insufficient
        for technique_combo, ticket_ids in technique_outcomes.items():
            if len(ticket_ids) >= 2:  # Pattern needs at least 2 examples
                patterns.append(FailurePattern(
                    pattern_id=f"technique_gap_{technique_combo}",
                    subgraph="multiple",
                    description=f"Techniques [{technique_combo}] failed for {len(ticket_ids)} tickets",
                    frequency=len(ticket_ids),
                    impact=len(ticket_ids) * 5.0,
                    evidence=ticket_ids[:5],
                    suggested_fix=f"Consider adding Reverse Thinking or Self-Consistency to complement {technique_combo}",
                ))

        return patterns

    def _keyword_failure_patterns(self, escalated: list[TicketOutcome]) -> list[FailurePattern]:
        """Identify keywords associated with escalation."""
        patterns = []

        # Extract keywords from escalated messages
        word_counter: Counter[str] = Counter()
        stop_words = {"the", "a", "an", "is", "it", "i", "my", "me", "to", "and", "for", "of", "in", "on", "that", "this", "with", "was", "but", "not", "have", "has", "are", "be", "at", "or", "so", "if", "we", "you", "they", "do", "can", "will"}

        for o in escalated:
            if o.message:
                words = re.findall(r'\b\w{3,}\b', o.message.lower())
                for w in words:
                    if w not in stop_words:
                        word_counter[w] += 1

        # Keywords that appear in many escalations are failure signals
        for keyword, count in word_counter.most_common(10):
            if count >= 2:
                patterns.append(FailurePattern(
                    pattern_id=f"keyword_{keyword}",
                    subgraph="multiple",
                    description=f"Keyword '{keyword}' appears in {count} escalated tickets",
                    frequency=count,
                    impact=count * 2.0,
                    evidence=[],
                    suggested_fix=f"Add '{keyword}' to KB search boosting and prompt examples",
                ))

        return patterns

    def _complexity_mismatch_patterns(self, escalated: list[TicketOutcome]) -> list[FailurePattern]:
        """Identify tickets where complexity was misclassified."""
        patterns = []

        # Low confidence + escalated = likely complexity mismatch
        mismatched = [
            o for o in escalated
            if o.confidence < 0.5 and o.complexity in ("simple", "medium")
        ]

        if len(mismatched) >= 2:
            patterns.append(FailurePattern(
                pattern_id="complexity_mismatch",
                subgraph="multiple",
                description=f"{len(mismatched)} tickets with low confidence were classified as simple/medium but needed escalation",
                frequency=len(mismatched),
                impact=len(mismatched) * 3.0,
                evidence=[o.ticket_id for o in mismatched][:5],
                suggested_fix="Adjust complexity classification thresholds: require confidence > 0.7 for simple classification",
            ))

        return patterns

    def _kb_retrieval_patterns(self, escalated: list[TicketOutcome]) -> list[FailurePattern]:
        """Identify tickets where KB retrieval failed to find relevant docs."""
        patterns = []

        low_kb = [o for o in escalated if o.kb_results_count <= 1]

        if len(low_kb) >= 2:
            patterns.append(FailurePattern(
                pattern_id="low_kb_retrieval",
                subgraph="multiple",
                description=f"{len(low_kb)} escalated tickets had 0-1 KB results (poor retrieval)",
                frequency=len(low_kb),
                impact=len(low_kb) * 4.0,
                evidence=[o.ticket_id for o in low_kb][:5],
                suggested_fix="Improve KB content coverage and search query enhancement via HyDE/MultiQuery",
            ))

        return patterns
