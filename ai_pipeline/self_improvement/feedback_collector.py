"""Feedback Collector — Records ticket outcomes for the self-improvement loop.

Every ticket that goes through the pipeline gets its outcome recorded:
  - Resolved automatically → success
  - Escalated to human → failure (the system couldn't handle it)
  - Resolved after loop-back → partial success (needed retry)

The collector stores these outcomes so the PatternLearner can analyze them.
In production, this would write to a database. For now, it uses in-memory
storage with optional JSON persistence.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger("parwa.self_improvement.feedback")


class OutcomeType(str, Enum):
    """Possible ticket outcomes."""
    RESOLVED = "resolved"           # System resolved the ticket without human
    ESCALATED = "escalated"         # Had to escalate to human
    LOOP_RESOLVED = "loop_resolved" # Resolved after quality loop-back
    PARTIAL = "partial"             # Partially resolved, customer needed follow-up


class TicketOutcome:
    """Record of a single ticket's outcome.

    Captures everything needed for the pattern learner to analyze:
    - What the ticket was about
    - Which subgraph handled it
    - What techniques were activated
    - What the quality score was
    - Whether it was resolved or escalated
    - The customer's feedback (if any)
    """

    def __init__(
        self,
        ticket_id: str,
        intent: str,
        subgraph: str,
        outcome: OutcomeType,
        *,
        message: str = "",
        techniques_used: list[str] | None = None,
        quality_score: float = 0.0,
        confidence: float = 0.0,
        complexity: str = "simple",
        kb_results_count: int = 0,
        response: str = "",
        customer_feedback: str = "",
        timestamp: str | None = None,
    ) -> None:
        self.ticket_id = ticket_id
        self.intent = intent
        self.subgraph = subgraph
        self.outcome = outcome
        self.message = message
        self.techniques_used = techniques_used or []
        self.quality_score = quality_score
        self.confidence = confidence
        self.complexity = complexity
        self.kb_results_count = kb_results_count
        self.response = response
        self.customer_feedback = customer_feedback
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "intent": self.intent,
            "subgraph": self.subgraph,
            "outcome": self.outcome.value,
            "message": self.message[:200],  # Truncate for storage
            "techniques_used": self.techniques_used,
            "quality_score": self.quality_score,
            "confidence": self.confidence,
            "complexity": self.complexity,
            "kb_results_count": self.kb_results_count,
            "response_length": len(self.response),
            "customer_feedback": self.customer_feedback,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TicketOutcome:
        return cls(
            ticket_id=data.get("ticket_id", ""),
            intent=data.get("intent", ""),
            subgraph=data.get("subgraph", "general"),
            outcome=OutcomeType(data.get("outcome", "resolved")),
            message=data.get("message", ""),
            techniques_used=data.get("techniques_used", []),
            quality_score=data.get("quality_score", 0.0),
            confidence=data.get("confidence", 0.0),
            complexity=data.get("complexity", "simple"),
            kb_results_count=data.get("kb_results_count", 0),
            response="",  # Don't store full response
            customer_feedback=data.get("customer_feedback", ""),
            timestamp=data.get("timestamp", ""),
        )


class FeedbackCollector:
    """Collects and stores ticket outcomes for the self-improvement loop.

    Usage:
        collector = FeedbackCollector()
        collector.record(TicketOutcome(...))

        # Later, analyze:
        outcomes = collector.get_recent(days=7)
        resolution_rate = collector.resolution_rate(days=7)
    """

    def __init__(self, storage_path: str | None = None) -> None:
        self._outcomes: list[TicketOutcome] = []
        self._storage_path = storage_path

        # Load existing data if available
        if storage_path and os.path.exists(storage_path):
            self._load()

    def record(self, outcome: TicketOutcome) -> None:
        """Record a ticket outcome."""
        self._outcomes.append(outcome)
        logger.info(
            "feedback: recorded %s outcome for ticket=%s subgraph=%s intent=%s",
            outcome.outcome.value, outcome.ticket_id, outcome.subgraph, outcome.intent,
        )

        # Persist if path is set
        if self._storage_path:
            self._save()

    def get_recent(self, days: int = 7) -> list[TicketOutcome]:
        """Get outcomes from the last N days."""
        cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
        recent = []
        for o in self._outcomes:
            try:
                ts = datetime.fromisoformat(o.timestamp).timestamp()
                if ts >= cutoff:
                    recent.append(o)
            except (ValueError, TypeError):
                recent.append(o)  # Include if timestamp is unparseable
        return recent

    def get_by_subgraph(self, subgraph: str) -> list[TicketOutcome]:
        """Get all outcomes for a specific subgraph."""
        return [o for o in self._outcomes if o.subgraph == subgraph]

    def get_by_outcome(self, outcome_type: OutcomeType) -> list[TicketOutcome]:
        """Get all outcomes of a specific type."""
        return [o for o in self._outcomes if o.outcome == outcome_type]

    def resolution_rate(self, days: int = 7) -> float:
        """Calculate the resolution rate over the last N days."""
        recent = self.get_recent(days)
        if not recent:
            return 0.0
        resolved = sum(1 for o in recent if o.outcome in (OutcomeType.RESOLVED, OutcomeType.LOOP_RESOLVED))
        return resolved / len(recent)

    def resolution_rate_by_subgraph(self, days: int = 7) -> dict[str, float]:
        """Calculate resolution rate per subgraph."""
        recent = self.get_recent(days)
        by_subgraph: dict[str, list[TicketOutcome]] = {}
        for o in recent:
            by_subgraph.setdefault(o.subgraph, []).append(o)

        rates = {}
        for subgraph, outcomes in by_subgraph.items():
            resolved = sum(1 for o in outcomes if o.outcome in (OutcomeType.RESOLVED, OutcomeType.LOOP_RESOLVED))
            rates[subgraph] = resolved / len(outcomes) if outcomes else 0.0
        return rates

    def escalation_reasons(self, days: int = 7) -> list[dict[str, Any]]:
        """Get common escalation patterns."""
        escalated = self.get_by_outcome(OutcomeType.ESCALATED)
        recent_escalated = [
            o for o in escalated
            if o in self.get_recent(days)
        ]

        # Group by intent
        by_intent: dict[str, int] = {}
        for o in recent_escalated:
            by_intent[o.intent] = by_intent.get(o.intent, 0) + 1

        return [
            {"intent": intent, "count": count}
            for intent, count in sorted(by_intent.items(), key=lambda x: -x[1])
        ]

    @property
    def total_outcomes(self) -> int:
        return len(self._outcomes)

    def summary(self) -> dict[str, Any]:
        """Get a summary of collected outcomes."""
        return {
            "total_outcomes": len(self._outcomes),
            "resolution_rate": self.resolution_rate(days=30),
            "resolution_rate_7d": self.resolution_rate(days=7),
            "by_subgraph": self.resolution_rate_by_subgraph(days=30),
            "escalation_reasons": self.escalation_reasons(days=30),
        }

    def _save(self) -> None:
        """Persist outcomes to JSON."""
        if not self._storage_path:
            return
        try:
            data = [o.to_dict() for o in self._outcomes]
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            with open(self._storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            logger.warning("feedback: failed to save: %s", exc)

    def _load(self) -> None:
        """Load outcomes from JSON."""
        if not self._storage_path or not os.path.exists(self._storage_path):
            return
        try:
            with open(self._storage_path) as f:
                data = json.load(f)
            self._outcomes = [TicketOutcome.from_dict(d) for d in data]
            logger.info("feedback: loaded %d outcomes from %s", len(self._outcomes), self._storage_path)
        except Exception as exc:
            logger.warning("feedback: failed to load: %s", exc)
