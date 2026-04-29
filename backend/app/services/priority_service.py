"""
PARWA Priority Service - MF01 Priority Auto-Assignment (Day 26)

Implements MF01: Priority system with:
- Auto-priority detection based on keywords
- Priority escalation rules
- Priority-based SLA mapping
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from database.models.tickets import Ticket, TicketPriority


class PriorityService:
    """Priority auto-assignment and management."""

    # Priority keywords for auto-detection
    CRITICAL_KEYWORDS = [
        "urgent",
        "critical",
        "emergency",
        "asap",
        "immediately",
        "down",
        "outage",
        "security breach",
        "data loss",
        "production down",
    ]

    HIGH_KEYWORDS = [
        "important",
        "high priority",
        "serious",
        "blocking",
        "cannot access",
        "error",
        "failed",
        "broken",
    ]

    LOW_KEYWORDS = [
        "whenever",
        "no rush",
        "low priority",
        "minor",
        "small issue",
        "just wondering",
        "curious",
        "question",
    ]

    # Priority weights for scoring
    PRIORITY_WEIGHTS = {
        TicketPriority.critical.value: 100,
        TicketPriority.high.value: 75,
        TicketPriority.medium.value: 50,
        TicketPriority.low.value: 25,
    }

    # Default SLA targets by priority (in minutes)
    DEFAULT_SLA_TARGETS = {
        TicketPriority.critical.value: {
            "first_response_minutes": 60,
            "resolution_minutes": 480,  # 8 hours
        },
        TicketPriority.high.value: {
            "first_response_minutes": 240,  # 4 hours
            "resolution_minutes": 1440,  # 24 hours
        },
        TicketPriority.medium.value: {
            "first_response_minutes": 720,  # 12 hours
            "resolution_minutes": 2880,  # 48 hours
        },
        TicketPriority.low.value: {
            "first_response_minutes": 1440,  # 24 hours
            "resolution_minutes": 4320,  # 72 hours
        },
    }

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    def detect_priority(self, text: str) -> Tuple[str, float]:
        """Detect priority from text content.

        Analyzes text for priority-indicating keywords.

        Args:
            text: Text to analyze (subject, message, etc.)

        Returns:
            Tuple of (priority, confidence_score)
        """
        if not text:
            return TicketPriority.medium.value, 0.5

        text_lower = text.lower()

        # Check for critical keywords
        critical_matches = sum(1 for kw in self.CRITICAL_KEYWORDS if kw in text_lower)
        if critical_matches > 0:
            confidence = min(0.95, 0.7 + (critical_matches * 0.1))
            return TicketPriority.critical.value, confidence

        # Check for high keywords
        high_matches = sum(1 for kw in self.HIGH_KEYWORDS if kw in text_lower)
        if high_matches > 0:
            confidence = min(0.9, 0.6 + (high_matches * 0.1))
            return TicketPriority.high.value, confidence

        # Check for low keywords
        low_matches = sum(1 for kw in self.LOW_KEYWORDS if kw in text_lower)
        if low_matches > 0:
            confidence = min(0.85, 0.6 + (low_matches * 0.08))
            return TicketPriority.low.value, confidence

        # Default to medium
        return TicketPriority.medium.value, 0.5

    def get_sla_target(
        self,
        priority: str,
        plan_tier: str = "mini_parwa",
    ) -> Dict[str, int]:
        """Get SLA targets for a priority level.

        Args:
            priority: Priority level
            plan_tier: Subscription plan tier

        Returns:
            Dict with first_response_minutes and resolution_minutes
        """
        base_targets = self.DEFAULT_SLA_TARGETS.get(
            priority, self.DEFAULT_SLA_TARGETS[TicketPriority.medium.value]
        )

        # Adjust based on plan tier
        multipliers = {
            "mini_parwa": 1.0,
            "parwa": 0.75,  # Better SLAs for higher tiers
            "high": 0.5,
            "enterprise": 0.4,
        }

        multiplier = multipliers.get(plan_tier, 1.0)

        return {
            "first_response_minutes": int(
                base_targets["first_response_minutes"] * multiplier
            ),
            "resolution_minutes": int(base_targets["resolution_minutes"] * multiplier),
        }

    def calculate_priority_score(
        self,
        priority: str,
        age_hours: float = 0,
        reopen_count: int = 0,
    ) -> float:
        """Calculate overall priority score for queue sorting.

        Higher score = higher priority for handling.

        Args:
            priority: Ticket priority level
            age_hours: Hours since ticket creation
            reopen_count: Number of times ticket was reopened

        Returns:
            Priority score (0-200)
        """
        base_score = self.PRIORITY_WEIGHTS.get(priority, 50)

        # Age factor: older tickets get slight boost
        age_boost = min(20, age_hours * 0.5)

        # Reopen penalty: reopened tickets need attention
        reopen_boost = min(30, reopen_count * 15)

        return min(200, base_score + age_boost + reopen_boost)

    def should_escalate(
        self,
        ticket: Ticket,
        current_priority: str,
    ) -> Tuple[bool, str]:
        """Determine if ticket should be escalated.

        Args:
            ticket: Ticket object
            current_priority: Current priority level

        Returns:
            Tuple of (should_escalate, reason)
        """
        # Escalate if reopened multiple times
        if ticket.reopen_count and ticket.reopen_count >= 2:
            if current_priority != TicketPriority.critical.value:
                return True, "Ticket reopened multiple times"

        # Escalate if SLA breached
        if ticket.sla_breached:
            if current_priority in [
                TicketPriority.low.value,
                TicketPriority.medium.value,
            ]:
                return True, "SLA breached"

        # Escalate if waiting too long for human
        if ticket.awaiting_human and ticket.escalation_level < 3:
            return True, "Awaiting human response too long"

        return False, ""

    def get_next_priority(self, current_priority: str) -> Optional[str]:
        """Get next higher priority level.

        Args:
            current_priority: Current priority level

        Returns:
            Next higher priority or None if already critical
        """
        escalation_order = [
            TicketPriority.low.value,
            TicketPriority.medium.value,
            TicketPriority.high.value,
            TicketPriority.critical.value,
        ]

        try:
            current_index = escalation_order.index(current_priority)
            if current_index < len(escalation_order) - 1:
                return escalation_order[current_index + 1]
        except ValueError:
            pass

        return None
