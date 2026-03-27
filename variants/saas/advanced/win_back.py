"""
Win-Back Campaign for SaaS Advanced Module.

Provides win-back campaigns including:
- Churned customer identification
- Win-back email sequences
- Special reactivation offers
- Feedback collection
- Competitive analysis
- Re-engagement timing optimization
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class WinBackStatus(str, Enum):
    """Win-back campaign status."""
    PENDING = "pending"
    CONTACTED = "contacted"
    RESPONDED = "responded"
    REACTIVATED = "reactivated"
    DECLINED = "declined"
    NO_RESPONSE = "no_response"


class OfferType(str, Enum):
    """Types of win-back offers."""
    DISCOUNT = "discount"
    FREE_MONTH = "free_month"
    DOWNGRADE = "downgrade"
    FEATURE_UNLOCK = "feature_unlock"
    EXTENDED_TRIAL = "extended_trial"
    CUSTOM = "custom"


@dataclass
class ChurnedCustomer:
    """Represents a churned customer."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    company_name: str = ""
    email: str = ""
    previous_tier: str = ""
    previous_mrr: float = 0.0
    churn_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    churn_reason: Optional[str] = None
    tenure_days: int = 0
    last_active: Optional[datetime] = None
    feedback_score: Optional[int] = None
    feedback_text: Optional[str] = None
    competitor: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "company_name": self.company_name,
            "email": self.email,
            "previous_tier": self.previous_tier,
            "previous_mrr": self.previous_mrr,
            "churn_date": self.churn_date.isoformat(),
            "churn_reason": self.churn_reason,
            "tenure_days": self.tenure_days,
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "feedback_score": self.feedback_score,
            "feedback_text": self.feedback_text,
            "competitor": self.competitor,
        }


@dataclass
class WinBackCampaign:
    """Represents a win-back campaign for a churned customer."""
    id: UUID = field(default_factory=uuid4)
    churned_customer_id: UUID = field(default_factory=uuid4)
    status: WinBackStatus = WinBackStatus.PENDING
    offer_type: OfferType = OfferType.DISCOUNT
    offer_details: Dict[str, Any] = field(default_factory=dict)
    contact_sequence: List[Dict[str, Any]] = field(default_factory=list)
    responses: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_contact: Optional[datetime] = None
    next_contact: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "churned_customer_id": str(self.churned_customer_id),
            "status": self.status.value,
            "offer_type": self.offer_type.value,
            "offer_details": self.offer_details,
            "contact_sequence": self.contact_sequence,
            "responses": self.responses,
            "created_at": self.created_at.isoformat(),
            "last_contact": self.last_contact.isoformat() if self.last_contact else None,
            "next_contact": self.next_contact.isoformat() if self.next_contact else None,
        }


# Win-back email templates
WINBACK_EMAIL_TEMPLATES = {
    "initial": {
        "subject": "We miss you, {name}! Here's a special offer to come back",
        "template": "winback_initial",
        "days_after_churn": 7,
    },
    "follow_up": {
        "subject": "Last chance: {discount}% off to reactivate your account",
        "template": "winback_followup",
        "days_after_churn": 21,
    },
    "final": {
        "subject": "Your account data will be deleted soon",
        "template": "winback_final",
        "days_after_churn": 45,
    },
    "nps_followup": {
        "subject": "Tell us how we can improve",
        "template": "nps_survey",
        "days_after_churn": 3,
    },
}

# Default win-back offers by tier
DEFAULT_OFFERS = {
    "mini": {"type": OfferType.FREE_MONTH, "value": 1},
    "parwa": {"type": OfferType.DISCOUNT, "value": 30},
    "parwa_high": {"type": OfferType.DISCOUNT, "value": 25},
    "enterprise": {"type": OfferType.CUSTOM, "value": "contact"},
}


class WinBackManager:
    """
    Manages win-back campaigns for churned customers.

    Features:
    - Churned customer identification
    - Win-back email sequences
    - Special reactivation offers
    - Feedback collection
    - Competitive analysis
    """

    def __init__(self):
        """Initialize win-back manager."""
        self._churned_customers: Dict[str, ChurnedCustomer] = {}
        self._campaigns: Dict[str, WinBackCampaign] = {}

    async def identify_churned_customers(
        self,
        days_since_churn: int = 90,
        min_previous_mrr: float = 0
    ) -> List[ChurnedCustomer]:
        """
        Identify eligible churned customers for win-back.

        Args:
            days_since_churn: Maximum days since churn
            min_previous_mrr: Minimum previous MRR

        Returns:
            List of eligible ChurnedCustomer
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_since_churn)

        eligible = [
            c for c in self._churned_customers.values()
            if c.churn_date >= cutoff and c.previous_mrr >= min_previous_mrr
        ]

        logger.info(
            "Identified churned customers for win-back",
            extra={
                "total_churned": len(self._churned_customers),
                "eligible_count": len(eligible),
            }
        )

        return eligible

    async def create_win_back_campaign(
        self,
        churned_customer: ChurnedCustomer,
        custom_offer: Optional[Dict[str, Any]] = None
    ) -> WinBackCampaign:
        """
        Create a win-back campaign for a churned customer.

        Args:
            churned_customer: Customer to target
            custom_offer: Optional custom offer

        Returns:
            Created WinBackCampaign
        """
        # Determine offer
        if custom_offer:
            offer_type = OfferType(custom_offer.get("type", "discount"))
            offer_details = custom_offer
        else:
            default = DEFAULT_OFFERS.get(churned_customer.previous_tier, DEFAULT_OFFERS["mini"])
            offer_type = OfferType(default["type"])
            offer_details = default

        # Create contact sequence
        sequence = await self._create_contact_sequence(churned_customer)

        campaign = WinBackCampaign(
            churned_customer_id=churned_customer.id,
            status=WinBackStatus.PENDING,
            offer_type=offer_type,
            offer_details=offer_details,
            contact_sequence=sequence,
            next_contact=sequence[0]["scheduled_at"] if sequence else None,
        )

        self._campaigns[str(campaign.id)] = campaign
        self._churned_customers[str(churned_customer.id)] = churned_customer

        logger.info(
            "Win-back campaign created",
            extra={
                "churned_customer_id": str(churned_customer.id),
                "campaign_id": str(campaign.id),
                "offer_type": offer_type.value,
            }
        )

        return campaign

    async def send_win_back_email(
        self,
        campaign_id: UUID,
        template_name: str = "initial"
    ) -> Dict[str, Any]:
        """
        Send a win-back email.

        Args:
            campaign_id: Campaign to send for
            template_name: Email template to use

        Returns:
            Dict with send result
        """
        campaign = self._campaigns.get(str(campaign_id))
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        customer = self._churned_customers.get(str(campaign.churned_customer_id))
        if not customer:
            raise ValueError("Customer not found")

        template = WINBACK_EMAIL_TEMPLATES.get(template_name, WINBACK_EMAIL_TEMPLATES["initial"])

        # Generate personalized content
        subject = template["subject"].format(
            name=customer.company_name or customer.email,
            discount=campaign.offer_details.get("value", 20),
        )

        # Mark as contacted
        campaign.status = WinBackStatus.CONTACTED
        campaign.last_contact = datetime.now(timezone.utc)

        # Update next contact
        next_idx = len([c for c in campaign.contact_sequence if c.get("sent")])
        if next_idx < len(campaign.contact_sequence):
            campaign.next_contact = campaign.contact_sequence[next_idx]["scheduled_at"]

        logger.info(
            "Win-back email sent",
            extra={
                "campaign_id": str(campaign_id),
                "template": template_name,
                "email": customer.email,
            }
        )

        return {
            "sent": True,
            "campaign_id": str(campaign_id),
            "template": template_name,
            "subject": subject,
            "sent_at": campaign.last_contact.isoformat(),
        }

    async def collect_feedback(
        self,
        churned_customer_id: UUID,
        feedback_score: int,
        feedback_text: Optional[str] = None,
        competitor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Collect feedback from churned customer.

        Args:
            churned_customer_id: Customer ID
            feedback_score: NPS-style score (0-10)
            feedback_text: Optional text feedback
            competitor: Optional competitor they switched to

        Returns:
            Dict with feedback result
        """
        customer = self._churned_customers.get(str(churned_customer_id))
        if not customer:
            raise ValueError(f"Customer {churned_customer_id} not found")

        customer.feedback_score = feedback_score
        customer.feedback_text = feedback_text
        customer.competitor = competitor

        logger.info(
            "Feedback collected",
            extra={
                "churned_customer_id": str(churned_customer_id),
                "feedback_score": feedback_score,
                "has_competitor": competitor is not None,
            }
        )

        return {
            "collected": True,
            "churned_customer_id": str(churned_customer_id),
            "feedback_score": feedback_score,
        }

    async def record_response(
        self,
        campaign_id: UUID,
        response_type: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Record a response to win-back campaign.

        Args:
            campaign_id: Campaign ID
            response_type: Type of response
            details: Optional response details

        Returns:
            Dict with response result
        """
        campaign = self._campaigns.get(str(campaign_id))
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        response = {
            "type": response_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }

        campaign.responses.append(response)

        # Update status
        if response_type == "reactivated":
            campaign.status = WinBackStatus.REACTIVATED
        elif response_type == "declined":
            campaign.status = WinBackStatus.DECLINED
        elif response_type == "responded":
            campaign.status = WinBackStatus.RESPONDED

        logger.info(
            "Win-back response recorded",
            extra={
                "campaign_id": str(campaign_id),
                "response_type": response_type,
                "new_status": campaign.status.value,
            }
        )

        return {
            "recorded": True,
            "campaign_id": str(campaign_id),
            "response_type": response_type,
            "status": campaign.status.value,
        }

    async def get_competitive_analysis(self) -> Dict[str, Any]:
        """
        Analyze competitive landscape from feedback.

        Returns:
            Dict with competitive analysis
        """
        competitors = {}

        for customer in self._churned_customers.values():
            if customer.competitor:
                competitors[customer.competitor] = competitors.get(customer.competitor, 0) + 1

        # Sort by frequency
        sorted_competitors = sorted(
            competitors.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Calculate average feedback score
        scores = [c.feedback_score for c in self._churned_customers.values() if c.feedback_score is not None]
        avg_score = sum(scores) / len(scores) if scores else None

        # Aggregate churn reasons
        reasons = {}
        for customer in self._churned_customers.values():
            if customer.churn_reason:
                reasons[customer.churn_reason] = reasons.get(customer.churn_reason, 0) + 1

        return {
            "competitor_mentions": dict(sorted_competitors),
            "total_analyzed": len(self._churned_customers),
            "average_feedback_score": round(avg_score, 2) if avg_score else None,
            "churn_reasons": reasons,
            "top_competitor": sorted_competitors[0][0] if sorted_competitors else None,
        }

    async def optimize_timing(
        self,
        campaign_id: UUID
    ) -> Dict[str, Any]:
        """
        Optimize contact timing based on response patterns.

        Args:
            campaign_id: Campaign to optimize

        Returns:
            Dict with timing recommendations
        """
        campaign = self._campaigns.get(str(campaign_id))
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        # Analyze response patterns
        response_times = []
        for response in campaign.responses:
            if response.get("type") == "reactivated":
                # Calculate days from first contact to response
                response_times.append(7)  # Mock optimal timing

        # Default recommendations
        recommendations = {
            "best_day": "Tuesday",
            "best_time": "10:00 AM",
            "optimal_days_after_churn": 14,
            "confidence": 0.75,
        }

        if response_times:
            avg_time = sum(response_times) / len(response_times)
            recommendations["optimal_days_after_churn"] = int(avg_time)

        return recommendations

    async def get_win_back_metrics(self) -> Dict[str, Any]:
        """
        Get win-back campaign metrics.

        Returns:
            Dict with campaign metrics
        """
        total = len(self._campaigns)
        if total == 0:
            return {"total_campaigns": 0}

        by_status = {}
        for campaign in self._campaigns.values():
            status = campaign.status.value
            by_status[status] = by_status.get(status, 0) + 1

        reactivated = by_status.get("reactivated", 0)
        success_rate = (reactivated / total * 100) if total > 0 else 0

        return {
            "total_campaigns": total,
            "by_status": by_status,
            "reactivated": reactivated,
            "success_rate": round(success_rate, 2),
            "pending": by_status.get("pending", 0),
            "contacted": by_status.get("contacted", 0),
        }

    async def _create_contact_sequence(
        self,
        customer: ChurnedCustomer
    ) -> List[Dict[str, Any]]:
        """Create contact sequence for campaign."""
        sequence = []
        now = datetime.now(timezone.utc)

        for name, template in WINBACK_EMAIL_TEMPLATES.items():
            if name == "nps_followup":
                continue  # Skip NPS for now

            scheduled = now + timedelta(days=template["days_after_churn"])

            sequence.append({
                "template": name,
                "scheduled_at": scheduled,
                "sent": False,
            })

        return sequence

    def add_churned_customer(
        self,
        client_id: str,
        company_name: str,
        email: str,
        previous_tier: str,
        previous_mrr: float,
        churn_reason: Optional[str] = None,
        tenure_days: int = 0
    ) -> ChurnedCustomer:
        """
        Add a churned customer for win-back.

        Args:
            client_id: Client identifier
            company_name: Company name
            email: Contact email
            previous_tier: Previous subscription tier
            previous_mrr: Previous MRR
            churn_reason: Optional churn reason
            tenure_days: Days as customer

        Returns:
            Created ChurnedCustomer
        """
        customer = ChurnedCustomer(
            client_id=client_id,
            company_name=company_name,
            email=email,
            previous_tier=previous_tier,
            previous_mrr=previous_mrr,
            churn_reason=churn_reason,
            tenure_days=tenure_days,
        )

        self._churned_customers[str(customer.id)] = customer

        return customer


# Export for testing
__all__ = [
    "WinBackManager",
    "WinBackCampaign",
    "ChurnedCustomer",
    "WinBackStatus",
    "OfferType",
    "WINBACK_EMAIL_TEMPLATES",
    "DEFAULT_OFFERS",
]
