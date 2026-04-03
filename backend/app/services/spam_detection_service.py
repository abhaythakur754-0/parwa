"""
Spam Detection Service - PS15 + MF21: Spam detection (Day 32)

Handles:
- Spam scoring for tickets
- Rate limiting per client
- Auto-flagging suspected spam
- Admin alerts for spam patterns
- Spam moderation workflow
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from backend.app.exceptions import NotFoundError, ValidationError
from database.models.tickets import Ticket, TicketStatus
from database.models.core import User


class SpamDetectionService:
    """
    PS15 + MF21: Spam detection and moderation.
    
    Features:
    - Spam scoring based on content analysis
    - Rate limiting per client/IP
    - Auto-flagging suspected spam
    - Admin alerts for spam patterns
    - Spam moderation workflow
    
    Spam Indicators:
    - Repetitive content
    - Known spam patterns
    - High frequency submissions
    - Suspicious links
    - Gibberish content
    """
    
    # Spam score thresholds
    SPAM_THRESHOLD_LOW = 30      # Low confidence
    SPAM_THRESHOLD_MEDIUM = 50   # Medium confidence
    SPAM_THRESHOLD_HIGH = 70     # High confidence
    SPAM_THRESHOLD_AUTO = 85     # Auto-flag as spam
    
    # Rate limits (per hour)
    DEFAULT_RATE_LIMITS = {
        "tickets_per_hour": 10,
        "tickets_per_day": 50,
        "messages_per_hour": 30,
    }
    
    # Known spam patterns
    SPAM_PATTERNS = [
        # Promotional content
        r"(?i)(buy now|click here|free|discount|offer|limited time)",
        # Suspicious links
        r"(?i)(bit\.ly|tinyurl|goo\.gl|t\.co)",
        # Financial scams
        r"(?i)(lottery|winner|inheritance|prince|million dollars)",
        # Pharma spam
        r"(?i)(viagra|cialis|pharmacy|medication|pills)",
        # Repetitive characters
        r"(.)\1{4,}",
        # All caps
        r"^[A-Z\s!?.]+$",
    ]
    
    # Gibberish detection patterns
    GIBBERISH_PATTERNS = [
        r"^[asdfghjkl]+$",  # Keyboard mash
        r"^[qwertyuiop]+$",  # Keyboard mash
        r"^[\W_]+$",  # Only special chars
    ]
    
    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
    
    def analyze_ticket(
        self,
        subject: str,
        content: str,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a ticket for spam indicators.
        
        Args:
            subject: Ticket subject
            content: Ticket content/message
            customer_id: Customer ID
            metadata: Additional metadata
            
        Returns:
            Spam analysis result with score and indicators
        """
        score = 0
        indicators = []
        
        # Check spam patterns
        pattern_score, pattern_indicators = self._check_spam_patterns(subject, content)
        score += pattern_score
        indicators.extend(pattern_indicators)
        
        # Check gibberish
        gibberish_score, gibberish_indicators = self._check_gibberish(subject, content)
        score += gibberish_score
        indicators.extend(gibberish_indicators)
        
        # Check rate limits
        if customer_id:
            rate_score, rate_indicators = self._check_rate_limits(customer_id)
            score += rate_score
            indicators.extend(rate_indicators)
        
        # Check content quality
        quality_score, quality_indicators = self._check_content_quality(subject, content)
        score += quality_score
        indicators.extend(quality_indicators)
        
        # Determine spam level
        if score >= self.SPAM_THRESHOLD_AUTO:
            spam_level = "auto_flag"
        elif score >= self.SPAM_THRESHOLD_HIGH:
            spam_level = "high"
        elif score >= self.SPAM_THRESHOLD_MEDIUM:
            spam_level = "medium"
        elif score >= self.SPAM_THRESHOLD_LOW:
            spam_level = "low"
        else:
            spam_level = "none"
        
        return {
            "spam_score": min(score, 100),
            "spam_level": spam_level,
            "is_spam": spam_level != "none",
            "should_auto_flag": spam_level == "auto_flag",
            "indicators": indicators,
            "analyzed_at": datetime.utcnow().isoformat(),
        }
    
    def mark_as_spam(
        self,
        ticket_id: str,
        reason: str,
        marked_by: Optional[str] = None,
    ) -> Ticket:
        """
        Mark a ticket as spam.
        
        Args:
            ticket_id: Ticket ID
            reason: Reason for marking as spam
            marked_by: User ID who marked it
            
        Returns:
            Updated ticket
        """
        ticket = self._get_ticket(ticket_id)
        
        if ticket.is_spam:
            raise ValidationError("Ticket is already marked as spam")
        
        # Update ticket
        ticket.is_spam = True
        ticket.spam_score = 100
        ticket.spam_reason = reason
        ticket.spam_marked_at = datetime.utcnow()
        ticket.spam_marked_by = marked_by
        
        # Close the ticket if not already closed
        if ticket.status != TicketStatus.closed.value:
            from backend.app.services.ticket_state_machine import TicketStateMachine
            
            state_machine = TicketStateMachine(self.db, self.company_id)
            state_machine.transition(
                ticket=ticket,
                to_status=TicketStatus.closed,
                reason="spam",
                actor_id=marked_by,
            )
        
        self.db.commit()
        self.db.refresh(ticket)
        
        # Send admin notification
        self._notify_admins(ticket, "marked_as_spam", reason)
        
        return ticket
    
    def unmark_as_spam(
        self,
        ticket_id: str,
        reason: str,
        unmarked_by: Optional[str] = None,
    ) -> Ticket:
        """
        Remove spam marking from a ticket.
        
        Args:
            ticket_id: Ticket ID
            reason: Reason for unmarking
            unmarked_by: User ID who unmarked it
            
        Returns:
            Updated ticket
        """
        ticket = self._get_ticket(ticket_id)
        
        if not ticket.is_spam:
            raise ValidationError("Ticket is not marked as spam")
        
        # Update ticket
        ticket.is_spam = False
        ticket.spam_unmarked_at = datetime.utcnow()
        ticket.spam_unmarked_by = unmarked_by
        ticket.spam_unmark_reason = reason
        
        # Reopen the ticket
        from backend.app.services.ticket_state_machine import TicketStateMachine
        
        state_machine = TicketStateMachine(self.db, self.company_id)
        
        try:
            state_machine.transition(
                ticket=ticket,
                to_status=TicketStatus.open,
                reason="not_spam",
                actor_id=unmarked_by,
            )
        except ValidationError:
            # If can't reopen, just update status
            ticket.status = TicketStatus.open.value
        
        self.db.commit()
        self.db.refresh(ticket)
        
        return ticket
    
    def check_rate_limit(
        self,
        customer_id: str,
        action: str = "ticket_create",
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if customer has exceeded rate limits.
        
        Args:
            customer_id: Customer ID
            action: Action type
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        # Count tickets in last hour
        tickets_last_hour = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.customer_id == customer_id,
            Ticket.created_at >= hour_ago,
        ).count()
        
        # Count tickets in last day
        tickets_last_day = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.customer_id == customer_id,
            Ticket.created_at >= day_ago,
        ).count()
        
        limits = self.DEFAULT_RATE_LIMITS
        
        rate_info = {
            "tickets_last_hour": tickets_last_hour,
            "tickets_last_day": tickets_last_day,
            "hourly_limit": limits["tickets_per_hour"],
            "daily_limit": limits["tickets_per_day"],
        }
        
        is_allowed = (
            tickets_last_hour < limits["tickets_per_hour"]
            and tickets_last_day < limits["tickets_per_day"]
        )
        
        rate_info["is_allowed"] = is_allowed
        rate_info["reason"] = None if is_allowed else "Rate limit exceeded"
        
        return is_allowed, rate_info
    
    def get_spam_queue(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Ticket], int]:
        """
        Get tickets flagged for spam review.
        
        Args:
            limit: Max results
            offset: Offset for pagination
            
        Returns:
            Tuple of (tickets, total count)
        """
        query = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            or_(
                Ticket.is_spam == True,
                Ticket.spam_score >= self.SPAM_THRESHOLD_LOW,
            ),
        )
        
        total = query.count()
        
        tickets = query.order_by(
            desc(Ticket.spam_score),
            desc(Ticket.created_at),
        ).offset(offset).limit(limit).all()
        
        return list(tickets), total
    
    def get_spam_statistics(
        self,
    ) -> Dict[str, Any]:
        """Get spam statistics for the company."""
        # Total spam tickets
        total_spam = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.is_spam == True,
        ).count()
        
        # Total non-spam tickets
        total_non_spam = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.is_spam == False,
        ).count()
        
        # By spam level (using simplified approach since spam_score is not on model)
        by_level = {
            "low": 0,
            "medium": 0,
            "high": 0,
            "auto_flagged": total_spam,
        }
        
        return {
            "total_spam": total_spam,
            "pending_review": 0,  # Would require spam_score column
            "auto_flagged_today": 0,  # Would require spam_marked_at column
            "by_level": by_level,
        }
    
    def detect_spam_patterns(
        self,
        time_window_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Detect spam patterns in recent tickets.
        
        Args:
            time_window_hours: Time window to analyze
            
        Returns:
            Detected patterns and statistics
        """
        since = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        # Get recent tickets
        recent_tickets = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.created_at >= since,
        ).all()
        
        # Analyze patterns
        patterns = {
            "high_frequency_customers": [],
            "repetitive_content": [],
            "similar_subjects": [],
        }
        
        # Group by customer
        customer_counts = {}
        subject_contents = {}
        
        for ticket in recent_tickets:
            # Count by customer
            if ticket.customer_id:
                if ticket.customer_id not in customer_counts:
                    customer_counts[ticket.customer_id] = []
                customer_counts[ticket.customer_id].append(ticket)
            
            # Group by subject similarity
            subject_key = ticket.subject.lower().strip()[:50] if ticket.subject else ""
            if subject_key:
                if subject_key not in subject_contents:
                    subject_contents[subject_key] = []
                subject_contents[subject_key].append(ticket)
        
        # Find high frequency customers
        for customer_id, tickets in customer_counts.items():
            if len(tickets) > 5:  # More than 5 tickets in window
                patterns["high_frequency_customers"].append({
                    "customer_id": customer_id,
                    "ticket_count": len(tickets),
                })
        
        # Find similar subjects
        for subject_key, tickets in subject_contents.items():
            if len(tickets) > 2:  # Same subject pattern
                patterns["similar_subjects"].append({
                    "subject_pattern": subject_key,
                    "ticket_count": len(tickets),
                })
        
        return {
            "time_window_hours": time_window_hours,
            "total_tickets_analyzed": len(recent_tickets),
            "patterns": patterns,
            "analyzed_at": datetime.utcnow().isoformat(),
        }
    
    def _check_spam_patterns(
        self,
        subject: str,
        content: str,
    ) -> Tuple[int, List[str]]:
        """Check for known spam patterns."""
        score = 0
        indicators = []
        
        text = f"{subject} {content}"
        
        for pattern in self.SPAM_PATTERNS:
            if re.search(pattern, text):
                score += 15
                indicators.append(f"spam_pattern:{pattern[:30]}")
        
        return score, indicators
    
    def _check_gibberish(
        self,
        subject: str,
        content: str,
    ) -> Tuple[int, List[str]]:
        """Check for gibberish content."""
        score = 0
        indicators = []
        
        for pattern in self.GIBBERISH_PATTERNS:
            if re.search(pattern, subject) or re.search(pattern, content[:100]):
                score += 20
                indicators.append("gibberish_detected")
        
        # Check for very short content
        if len(content.strip()) < 5:
            score += 15
            indicators.append("content_too_short")
        
        return score, indicators
    
    def _check_rate_limits(
        self,
        customer_id: str,
    ) -> Tuple[int, List[str]]:
        """Check customer's recent activity rate."""
        score = 0
        indicators = []
        
        is_allowed, rate_info = self.check_rate_limit(customer_id)
        
        if not is_allowed:
            score += 25
            indicators.append("rate_limit_exceeded")
        
        # High frequency even if under limit
        if rate_info["tickets_last_hour"] > 5:
            score += 10
            indicators.append("high_frequency")
        
        return score, indicators
    
    def _check_content_quality(
        self,
        subject: str,
        content: str,
    ) -> Tuple[int, List[str]]:
        """Check content quality indicators."""
        score = 0
        indicators = []
        
        # Check for excessive links
        link_count = len(re.findall(r'https?://', content))
        if link_count > 3:
            score += 15
            indicators.append("excessive_links")
        
        # Check for excessive caps
        caps_ratio = sum(1 for c in content if c.isupper()) / max(len(content), 1)
        if caps_ratio > 0.7:
            score += 10
            indicators.append("excessive_caps")
        
        # Check for excessive punctuation
        punct_count = len(re.findall(r'[!?.]{3,}', content))
        if punct_count > 2:
            score += 5
            indicators.append("excessive_punctuation")
        
        return score, indicators
    
    def _get_ticket(
        self,
        ticket_id: str,
    ) -> Ticket:
        """Get ticket by ID."""
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == self.company_id,
        ).first()
        
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")
        
        return ticket
    
    def _notify_admins(
        self,
        ticket: Ticket,
        event: str,
        reason: str,
    ) -> None:
        """Notify admins about spam event."""
        from backend.app.services.notification_service import NotificationService
        
        notification_service = NotificationService(self.db, self.company_id)
        
        # Get admins
        admins = self.db.query(User).filter(
            User.company_id == self.company_id,
            User.role.in_(["admin", "manager"]),
        ).all()
        
        if not admins:
            return
        
        notification_service.send_notification(
            event_type="ticket_updated",
            recipient_ids=[a.id for a in admins],
            data={
                "ticket_id": ticket.id,
                "ticket_subject": ticket.subject,
                "update_type": "spam_marked",
                "message": f"Ticket marked as spam: {reason}",
            },
            channels=["in_app"],
            priority="medium",
            ticket_id=ticket.id,
        )
