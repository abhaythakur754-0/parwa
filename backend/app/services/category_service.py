"""
PARWA Category Service - MF02 Category Routing (Day 26)

Implements MF02: Category classification with:
- Auto-category detection based on keywords
- Category-to-department routing
- Category-based assignment rules
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from database.models.tickets import TicketCategory


class CategoryService:
    """Category auto-detection and routing."""

    # Category keywords for auto-detection
    CATEGORY_KEYWORDS = {
        TicketCategory.tech_support.value: [
            "error",
            "bug",
            "crash",
            "not working",
            "broken",
            "issue",
            "cannot access",
            "login problem",
            "password reset",
            "installation",
            "configuration",
            "api",
            "integration",
            "sync",
            "connection",
            "timeout",
            "slow",
            "performance",
            "down",
            "offline",
        ],
        TicketCategory.billing.value: [
            "invoice",
            "payment",
            "charge",
            "refund",
            "billing",
            "subscription",
            "plan",
            "price",
            "cost",
            "credit",
            "receipt",
            "overcharge",
            "cancel subscription",
            "upgrade",
            "downgrade",
            "prorated",
        ],
        TicketCategory.feature_request.value: [
            "feature",
            "suggestion",
            "would be great",
            "could you add",
            "request",
            "enhancement",
            "improve",
            "new functionality",
            "wish",
            "idea",
            "roadmap",
            "vote for",
        ],
        TicketCategory.bug_report.value: [
            "bug",
            "defect",
            "unexpected",
            "incorrect",
            "wrong result",
            "reproduce",
            "steps to",
            "screenshot",
            "stack trace",
            "exception",
            "error message",
            "crash",
            "data corruption",
            "security issue",
        ],
        TicketCategory.complaint.value: [
            "complaint",
            "unhappy",
            "dissatisfied",
            "terrible",
            "awful",
            "worst",
            "disappointed",
            "frustrated",
            "angry",
            "manager",
            "escalate",
            "formal complaint",
            "legal",
            "attorney",
        ],
        TicketCategory.general.value: [
            "question",
            "how do i",
            "how to",
            "what is",
            "help",
            "information",
            "clarification",
            "curious",
            "wondering",
        ],
    }

    # Category to department mapping (default)
    CATEGORY_DEPARTMENT_MAP = {
        TicketCategory.tech_support.value: "technical_support",
        TicketCategory.billing.value: "billing",
        TicketCategory.feature_request.value: "product",
        TicketCategory.bug_report.value: "engineering",
        TicketCategory.complaint.value: "customer_success",
        TicketCategory.general.value: "general",
    }

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    def detect_category(self, text: str) -> Tuple[str, float]:
        """Detect category from text content.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (category, confidence_score)
        """
        if not text:
            return TicketCategory.general.value, 0.3

        text_lower = text.lower()

        # Score each category
        scores: Dict[str, float] = {}

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            if matches > 0:
                # Confidence based on number of matches
                confidence = min(0.95, 0.5 + (matches * 0.15))
                scores[category] = confidence

        if not scores:
            return TicketCategory.general.value, 0.3

        # Return category with highest score
        best_category = max(scores, key=scores.get)
        return best_category, scores[best_category]

    def detect_category_advanced(
        self,
        subject: str,
        message: str = "",
        metadata: Optional[Dict] = None,
    ) -> Tuple[str, float, Dict[str, float]]:
        """Advanced category detection with multiple signals.

        Args:
            subject: Ticket subject
            message: First message content
            metadata: Additional metadata

        Returns:
            Tuple of (category, confidence, all_scores)
        """
        combined_text = f"{subject} {message}".lower()

        # Score each category
        all_scores: Dict[str, float] = {}

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in combined_text)
            if matches > 0:
                confidence = min(0.95, 0.4 + (matches * 0.12))
                all_scores[category] = confidence
            else:
                all_scores[category] = 0.1

        # Boost certain categories based on metadata
        if metadata:
            # Source channel can indicate category
            channel = metadata.get("channel", "")
            if channel == "email":
                all_scores[TicketCategory.billing.value] *= 1.1
            elif channel == "chat":
                all_scores[TicketCategory.tech_support.value] *= 1.1

            # Customer tier can indicate category
            customer_tier = metadata.get("customer_tier", "")
            if customer_tier == "enterprise":
                all_scores[TicketCategory.feature_request.value] *= 1.2

        # Get best category
        if all_scores:
            best_category = max(all_scores, key=all_scores.get)
            confidence = all_scores[best_category]
        else:
            best_category = TicketCategory.general.value
            confidence = 0.3

        return best_category, confidence, all_scores

    def get_department(self, category: str) -> str:
        """Get department for a category.

        Args:
            category: Category value

        Returns:
            Department name
        """
        return self.CATEGORY_DEPARTMENT_MAP.get(
            category, self.CATEGORY_DEPARTMENT_MAP[TicketCategory.general.value]
        )

    def get_category_rules(self, category: str) -> Dict:
        """Get routing rules for a category.

        Args:
            category: Category value

        Returns:
            Dict with routing rules
        """
        rules = {
            TicketCategory.tech_support.value: {
                "auto_assign_ai": True,
                "priority_boost": 0,
                "sla_multiplier": 1.0,
                "required_fields": ["issue_type", "steps_reproduced"],
            },
            TicketCategory.billing.value: {
                "auto_assign_ai": False,  # Billing often needs human
                "priority_boost": 10,
                "sla_multiplier": 0.8,
                "required_fields": ["account_id"],
            },
            TicketCategory.feature_request.value: {
                "auto_assign_ai": False,
                "priority_boost": -10,
                "sla_multiplier": 1.5,
                "required_fields": ["feature_description"],
            },
            TicketCategory.bug_report.value: {
                "auto_assign_ai": True,
                "priority_boost": 5,
                "sla_multiplier": 0.9,
                "required_fields": ["steps_to_reproduce", "expected_behavior"],
            },
            TicketCategory.complaint.value: {
                "auto_assign_ai": False,
                "priority_boost": 20,
                "sla_multiplier": 0.7,
                "required_fields": [],
                "auto_escalate": True,
            },
            TicketCategory.general.value: {
                "auto_assign_ai": True,
                "priority_boost": 0,
                "sla_multiplier": 1.0,
                "required_fields": [],
            },
        }

        return rules.get(category, rules[TicketCategory.general.value])

    def validate_category_requirements(
        self,
        category: str,
        metadata: Dict,
    ) -> Tuple[bool, List[str]]:
        """Validate that category requirements are met.

        Args:
            category: Category value
            metadata: Ticket metadata

        Returns:
            Tuple of (is_valid, missing_fields)
        """
        rules = self.get_category_rules(category)
        required_fields = rules.get("required_fields", [])

        missing = []
        for field in required_fields:
            if field not in metadata or not metadata[field]:
                missing.append(field)

        return len(missing) == 0, missing
