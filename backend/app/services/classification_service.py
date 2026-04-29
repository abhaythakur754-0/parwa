"""
PARWA Classification Service - Rule-Based Ticket Classification (Day 28)

Implements F-049: Ticket classification with:
- Rule-based intent classification (AI stub for Week 9)
- Intent categories: refund, technical, billing, complaint, feature_request, general
- Urgency levels: urgent, routine, informational
- Confidence scoring
- Human correction workflow for training data

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from database.models.tickets import (
    Ticket,
    TicketMessage,
    TicketIntent,
    ClassificationCorrection,
    TicketPriority,
)
from app.exceptions import NotFoundError


class IntentCategory:
    """Intent category constants."""

    REFUND = "refund"
    TECHNICAL = "technical"
    BILLING = "billing"
    COMPLAINT = "complaint"
    FEATURE_REQUEST = "feature_request"
    GENERAL = "general"

    ALL = [REFUND, TECHNICAL, BILLING, COMPLAINT, FEATURE_REQUEST, GENERAL]


class UrgencyLevel:
    """Urgency level constants."""

    URGENT = "urgent"
    ROUTINE = "routine"
    INFORMATIONAL = "informational"

    ALL = [URGENT, ROUTINE, INFORMATIONAL]


class ClassificationService:
    """Rule-based ticket classification service.

    Week 4: Rule-based classification using keyword matching.
    Week 9: Will be replaced with AI-based classification.
    """

    # Classification rules (keyword -> intent mappings)
    INTENT_KEYWORDS = {
        IntentCategory.REFUND: [
            "refund",
            "money back",
            "return",
            "reimburse",
            "credit back",
            "chargeback",
            "cancel order",
            "want my money",
            "get my money back",
        ],
        IntentCategory.TECHNICAL: [
            "error",
            "bug",
            "not working",
            "broken",
            "crash",
            "issue",
            "problem",
            "doesn't work",
            "failed",
            "glitch",
            "not loading",
            "slow",
            "connection",
            "timeout",
            "offline",
            "down",
        ],
        IntentCategory.BILLING: [
            "bill",
            "invoice",
            "charge",
            "payment",
            "subscription",
            "price",
            "cost",
            "fee",
            "overcharge",
            "duplicate charge",
            "unauthorized charge",
            "subscription cancel",
            "renewal",
        ],
        IntentCategory.COMPLAINT: [
            "complaint",
            "unhappy",
            "disappointed",
            "frustrated",
            "angry",
            "terrible",
            "awful",
            "worst",
            "horrible",
            "unacceptable",
            "speak to manager",
            "escalate",
            "report",
            "formal complaint",
        ],
        IntentCategory.FEATURE_REQUEST: [
            "feature",
            "suggestion",
            "would be great",
            "wish you had",
            "please add",
            "would like to see",
            "enhancement",
            "improve",
            "new functionality",
            "missing feature",
            "roadmap",
        ],
    }

    # Urgency indicators
    URGENCY_KEYWORDS = {
        UrgencyLevel.URGENT: [
            "urgent",
            "emergency",
            "asap",
            "immediately",
            "right now",
            "critical",
            "production down",
            "system down",
            "data loss",
            "security breach",
            "hacked",
            "leaked",
            "legal",
        ],
        UrgencyLevel.INFORMATIONAL: [
            "just wondering",
            "curious",
            "question about",
            "how do i",
            "what is",
            "can you explain",
            "information",
            "documentation",
            "help me understand",
            "guide",
        ],
    }

    # Category to priority mapping
    CATEGORY_PRIORITY_BOOST = {
        IntentCategory.COMPLAINT: 1,  # Boost priority (lower number = higher)
        IntentCategory.TECHNICAL: 2,
        IntentCategory.BILLING: 2,
        IntentCategory.REFUND: 2,
        IntentCategory.FEATURE_REQUEST: 4,  # Lower priority
        IntentCategory.GENERAL: 3,
    }

    # Urgency to priority mapping
    URGENCY_PRIORITY_BOOST = {
        UrgencyLevel.URGENT: 1,
        UrgencyLevel.ROUTINE: 3,
        UrgencyLevel.INFORMATIONAL: 4,
    }

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    # ── CLASSIFICATION ───────────────────────────────────────────────────────

    def classify(
        self,
        ticket_id: str,
        force_reclassify: bool = False,
    ) -> Dict[str, Any]:
        """Classify a ticket by its content.

        Args:
            ticket_id: Ticket ID to classify
            force_reclassify: Force reclassification even if already classified

        Returns:
            Classification result with intent, urgency, confidence

        Raises:
            NotFoundError: If ticket not found
        """
        # Get ticket
        ticket = (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == self.company_id,
            )
            .first()
        )

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        # Check if already classified
        existing = (
            self.db.query(TicketIntent)
            .filter(
                TicketIntent.ticket_id == ticket_id,
                TicketIntent.company_id == self.company_id,
            )
            .first()
        )

        if existing and not force_reclassify:
            return {
                "ticket_id": ticket_id,
                "intent": existing.intent,
                "urgency": existing.urgency,
                "confidence": float(existing.confidence),
                "already_classified": True,
            }

        # Get ticket content
        content = self._get_ticket_content(ticket)

        # Classify
        intent, intent_confidence = self._classify_intent(content)
        urgency, urgency_confidence = self._classify_urgency(content)

        # Overall confidence is average of intent and urgency
        confidence = (intent_confidence + urgency_confidence) / 2

        # Create or update classification record
        if existing:
            existing.intent = intent
            existing.urgency = urgency
            existing.confidence = confidence
            existing.variant_version = "rule-based-v1"
        else:
            classification = TicketIntent(
                id=str(uuid.uuid4()),
                ticket_id=ticket_id,
                company_id=self.company_id,
                intent=intent,
                urgency=urgency,
                confidence=confidence,
                variant_version="rule-based-v1",
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(classification)

        # Update ticket
        ticket.classification_intent = intent
        ticket.classification_type = urgency

        self.db.commit()

        return {
            "ticket_id": ticket_id,
            "intent": intent,
            "urgency": urgency,
            "confidence": confidence,
            "intent_confidence": intent_confidence,
            "urgency_confidence": urgency_confidence,
            "already_classified": False,
            "suggested_priority": self._suggest_priority(intent, urgency),
        }

    def classify_text(
        self,
        subject: Optional[str] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Classify text without creating a ticket.

        Args:
            subject: Subject text
            message: Message content
            metadata: Additional metadata

        Returns:
            Classification result
        """
        # Combine content
        content_parts = []
        if subject:
            content_parts.append(subject)
        if message:
            content_parts.append(message)
        if metadata:
            # Extract relevant metadata
            for key in ["category", "type", "tags"]:
                if key in metadata:
                    content_parts.append(str(metadata[key]))

        content = " ".join(content_parts)

        # Classify
        intent, intent_confidence = self._classify_intent(content)
        urgency, urgency_confidence = self._classify_urgency(content)
        confidence = (intent_confidence + urgency_confidence) / 2

        # Get all scores
        all_intent_scores = self._get_all_intent_scores(content)
        all_urgency_scores = self._get_all_urgency_scores(content)

        return {
            "intent": intent,
            "urgency": urgency,
            "confidence": confidence,
            "intent_confidence": intent_confidence,
            "urgency_confidence": urgency_confidence,
            "all_intent_scores": all_intent_scores,
            "all_urgency_scores": all_urgency_scores,
            "suggested_priority": self._suggest_priority(intent, urgency),
        }

    # ── CORRECTIONS ──────────────────────────────────────────────────────────

    def record_correction(
        self,
        ticket_id: str,
        original_intent: str,
        corrected_intent: str,
        original_urgency: Optional[str] = None,
        corrected_urgency: Optional[str] = None,
        corrected_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> ClassificationCorrection:
        """Record a human correction to classification.

        This feeds into the training data for AI models.

        Args:
            ticket_id: Ticket ID
            original_intent: Original classified intent
            corrected_intent: Correct intent
            original_urgency: Original urgency
            corrected_urgency: Correct urgency
            corrected_by: User ID who made correction
            reason: Reason for correction

        Returns:
            ClassificationCorrection record
        """
        correction = ClassificationCorrection(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            company_id=self.company_id,
            original_intent=original_intent,
            corrected_intent=corrected_intent,
            original_urgency=original_urgency,
            corrected_urgency=corrected_urgency,
            corrected_by=corrected_by,
            reason=reason,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(correction)

        # Update ticket classification
        ticket = (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == self.company_id,
            )
            .first()
        )

        if ticket:
            ticket.classification_intent = corrected_intent
            if corrected_urgency:
                ticket.classification_type = corrected_urgency

        # Update intent record
        intent_record = (
            self.db.query(TicketIntent)
            .filter(
                TicketIntent.ticket_id == ticket_id,
                TicketIntent.company_id == self.company_id,
            )
            .first()
        )

        if intent_record:
            intent_record.intent = corrected_intent
            if corrected_urgency:
                intent_record.urgency = corrected_urgency
            intent_record.confidence = 1.0  # Human correction = 100% confidence

        self.db.commit()

        return correction

    def get_corrections(
        self,
        page: int = 1,
        page_size: int = 20,
        intent_filter: Optional[str] = None,
    ) -> Tuple[List[Dict], int]:
        """Get all corrections for training data.

        Args:
            page: Page number
            page_size: Items per page
            intent_filter: Filter by original or corrected intent

        Returns:
            Tuple of (corrections list, total count)
        """
        query = self.db.query(ClassificationCorrection).filter(
            ClassificationCorrection.company_id == self.company_id,
        )

        if intent_filter:
            query = query.filter(
                or_(
                    ClassificationCorrection.original_intent == intent_filter,
                    ClassificationCorrection.corrected_intent == intent_filter,
                )
            )

        total = query.count()

        offset = (page - 1) * page_size
        corrections = (
            query.order_by(desc(ClassificationCorrection.created_at))
            .offset(offset)
            .limit(page_size)
            .all()
        )

        results = []
        for c in corrections:
            results.append(
                {
                    "id": c.id,
                    "ticket_id": c.ticket_id,
                    "original_intent": c.original_intent,
                    "corrected_intent": c.corrected_intent,
                    "original_urgency": c.original_urgency,
                    "corrected_urgency": c.corrected_urgency,
                    "corrected_by": c.corrected_by,
                    "reason": c.reason,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
            )

        return results, total

    def get_classification_stats(self) -> Dict[str, Any]:
        """Get classification statistics.

        Returns:
            Dict with intent distribution, correction rate, etc.
        """
        # Get intent distribution
        intent_counts = (
            self.db.query(
                TicketIntent.intent,
                func.count(TicketIntent.id),
            )
            .filter(
                TicketIntent.company_id == self.company_id,
            )
            .group_by(TicketIntent.intent)
            .all()
        )

        intent_distribution = {k: v for k, v in intent_counts}

        # Get urgency distribution
        urgency_counts = (
            self.db.query(
                TicketIntent.urgency,
                func.count(TicketIntent.id),
            )
            .filter(
                TicketIntent.company_id == self.company_id,
            )
            .group_by(TicketIntent.urgency)
            .all()
        )

        urgency_distribution = {k: v for k, v in urgency_counts}

        # Get correction stats
        total_classifications = (
            self.db.query(TicketIntent)
            .filter(
                TicketIntent.company_id == self.company_id,
            )
            .count()
        )

        total_corrections = (
            self.db.query(ClassificationCorrection)
            .filter(
                ClassificationCorrection.company_id == self.company_id,
            )
            .count()
        )

        correction_rate = (
            total_corrections / total_classifications * 100
            if total_classifications > 0
            else 0
        )

        # Get average confidence
        avg_confidence = (
            self.db.query(
                func.avg(TicketIntent.confidence),
            )
            .filter(
                TicketIntent.company_id == self.company_id,
            )
            .scalar()
            or 0
        )

        return {
            "total_classifications": total_classifications,
            "total_corrections": total_corrections,
            "correction_rate": round(correction_rate, 2),
            "average_confidence": round(float(avg_confidence), 4),
            "intent_distribution": intent_distribution,
            "urgency_distribution": urgency_distribution,
        }

    # ── PRIVATE HELPERS ─────────────────────────────────────────────────────

    def _get_ticket_content(self, ticket: Ticket) -> str:
        """Get combined content from ticket and messages."""
        parts = []

        if ticket.subject:
            parts.append(ticket.subject)

        # Get first few messages
        messages = (
            self.db.query(TicketMessage)
            .filter(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.company_id == self.company_id,
            )
            .order_by(TicketMessage.created_at)
            .limit(3)
            .all()
        )

        for msg in messages:
            if msg.content:
                parts.append(msg.content)

        return " ".join(parts)

    def _classify_intent(self, content: str) -> Tuple[str, float]:
        """Classify intent from content.

        Args:
            content: Text content to classify

        Returns:
            Tuple of (intent, confidence)
        """
        content_lower = content.lower()
        scores = {}

        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in content_lower:
                    # Weight by keyword length (longer = more specific)
                    score += len(keyword.split())

            scores[intent] = score

        # Get best match
        if not scores or max(scores.values()) == 0:
            return IntentCategory.GENERAL, 0.3

        best_intent = max(scores, key=scores.get)
        total_score = sum(scores.values())
        confidence = scores[best_intent] / total_score if total_score > 0 else 0.3

        # Cap confidence at 0.95 for rule-based (reserving 1.0 for human)
        confidence = min(confidence, 0.95)

        return best_intent, round(confidence, 4)

    def _classify_urgency(self, content: str) -> Tuple[str, float]:
        """Classify urgency from content.

        Args:
            content: Text content to classify

        Returns:
            Tuple of (urgency, confidence)
        """
        content_lower = content.lower()
        scores = {}

        for urgency, keywords in self.URGENCY_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in content_lower:
                    score += len(keyword.split())

            scores[urgency] = score

        # Default to routine
        if not scores or max(scores.values()) == 0:
            return UrgencyLevel.ROUTINE, 0.5

        best_urgency = max(scores, key=scores.get)
        total_score = sum(scores.values())
        confidence = scores[best_urgency] / total_score if total_score > 0 else 0.5

        return best_urgency, round(confidence, 4)

    def _get_all_intent_scores(self, content: str) -> Dict[str, float]:
        """Get all intent scores for content."""
        content_lower = content.lower()
        scores = {}

        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in content_lower:
                    score += len(keyword.split())
            scores[intent] = score

        # Normalize
        total = sum(scores.values())
        if total > 0:
            return {k: round(v / total, 4) for k, v in scores.items()}

        return {k: 0.0 for k in IntentCategory.ALL}

    def _get_all_urgency_scores(self, content: str) -> Dict[str, float]:
        """Get all urgency scores for content."""
        content_lower = content.lower()
        scores = {}

        for urgency, keywords in self.URGENCY_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in content_lower:
                    score += len(keyword.split())
            scores[urgency] = score

        # Normalize
        total = sum(scores.values())
        if total > 0:
            return {k: round(v / total, 4) for k, v in scores.items()}

        # Default to routine
        return {
            UrgencyLevel.URGENT: 0.0,
            UrgencyLevel.ROUTINE: 1.0,
            UrgencyLevel.INFORMATIONAL: 0.0,
        }

    def _suggest_priority(
        self,
        intent: str,
        urgency: str,
    ) -> str:
        """Suggest ticket priority based on classification.

        Args:
            intent: Classified intent
            urgency: Classified urgency

        Returns:
            Suggested priority level
        """
        # Get base priority from category
        category_score = self.CATEGORY_PRIORITY_BOOST.get(intent, 3)

        # Get urgency modifier
        urgency_score = self.URGENCY_PRIORITY_BOOST.get(urgency, 3)

        # Combined score (lower = higher priority)
        combined = (category_score + urgency_score) / 2

        if combined <= 1.5:
            return TicketPriority.critical.value
        elif combined <= 2.5:
            return TicketPriority.high.value
        elif combined <= 3.5:
            return TicketPriority.medium.value
        else:
            return TicketPriority.low.value
