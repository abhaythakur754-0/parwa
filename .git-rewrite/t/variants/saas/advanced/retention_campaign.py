"""
Retention Campaign for SaaS Advanced Module.

Provides retention campaigns including:
- Automated retention workflows
- Personalized outreach messages
- Discount/incentive offers
- Feature engagement prompts
- Check-in email sequences
- Success manager assignment
- A/B testing for campaigns
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CampaignType(str, Enum):
    """Types of retention campaigns."""
    ENGAGEMENT = "engagement"
    RE_ENGAGEMENT = "re_engagement"
    VALUE_DEMONSTRATION = "value_demonstration"
    CHECK_IN = "check_in"
    DISCOUNT = "discount"
    FEATURE_SPOTLIGHT = "feature_spotlight"
    SUCCESS_REVIEW = "success_review"


class CampaignStatus(str, Enum):
    """Campaign status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MessageChannel(str, Enum):
    """Message delivery channels."""
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"
    PUSH = "push"
    PHONE = "phone"


@dataclass
class CampaignMessage:
    """Represents a campaign message."""
    id: UUID = field(default_factory=uuid4)
    campaign_id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    message_type: str = ""
    subject: str = ""
    body: str = ""
    channel: MessageChannel = MessageChannel.EMAIL
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "campaign_id": str(self.campaign_id),
            "client_id": self.client_id,
            "message_type": self.message_type,
            "subject": self.subject,
            "channel": self.channel.value,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "clicked_at": self.clicked_at.isoformat() if self.clicked_at else None,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
        }


@dataclass
class RetentionCampaign:
    """Represents a retention campaign."""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    campaign_type: CampaignType = CampaignType.ENGAGEMENT
    status: CampaignStatus = CampaignStatus.DRAFT
    target_segment: str = ""
    trigger_conditions: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    discount_offer: Optional[Dict[str, Any]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    ab_test_variant: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "name": self.name,
            "campaign_type": self.campaign_type.value,
            "status": self.status.value,
            "target_segment": self.target_segment,
            "trigger_conditions": self.trigger_conditions,
            "messages": self.messages,
            "discount_offer": self.discount_offer,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "ab_test_variant": self.ab_test_variant,
            "metrics": self.metrics,
            "created_at": self.created_at.isoformat(),
        }


# Campaign templates
CAMPAIGN_TEMPLATES = {
    CampaignType.ENGAGEMENT: {
        "name": "Engagement Boost",
        "trigger": {"usage_decline": True, "days_inactive": 7},
        "messages": [
            {
                "day": 0,
                "type": "check_in",
                "subject": "We miss you at {company_name}!",
                "template": "engagement_check_in",
            },
            {
                "day": 3,
                "type": "feature_spotlight",
                "subject": "Discover what's new",
                "template": "feature_update",
            },
        ],
    },
    CampaignType.RE_ENGAGEMENT: {
        "name": "Re-Engagement Series",
        "trigger": {"days_inactive": 14, "login_frequency": "low"},
        "messages": [
            {
                "day": 0,
                "type": "personalized",
                "subject": "Let's get you back on track",
                "template": "re_engagement_intro",
            },
            {
                "day": 5,
                "type": "value_reminder",
                "subject": "Your {product_name} highlights",
                "template": "value_summary",
            },
            {
                "day": 10,
                "type": "incentive",
                "subject": "Special offer just for you",
                "template": "discount_offer",
            },
        ],
    },
    CampaignType.DISCOUNT: {
        "name": "Retention Discount",
        "trigger": {"churn_risk": "high", "tenure_days": 90},
        "messages": [
            {
                "day": 0,
                "type": "discount",
                "subject": "Exclusive discount for loyal customers",
                "template": "loyalty_discount",
            },
        ],
        "discount": {"percent": 20, "validity_days": 30},
    },
    CampaignType.SUCCESS_REVIEW: {
        "name": "Success Review",
        "trigger": {"churn_risk": "critical", "annual_value": 1000},
        "messages": [
            {
                "day": 0,
                "type": "executive_outreach",
                "subject": "Let's schedule your success review",
                "template": "success_review_invite",
            },
        ],
    },
}


class RetentionCampaignManager:
    """
    Manages retention campaigns for SaaS customers.

    Features:
    - Automated workflows
    - Personalized messaging
    - Discount offers
    - Feature prompts
    - Check-in sequences
    - A/B testing
    """

    def __init__(
        self,
        client_id: str = "",
        company_name: str = "",
        email: str = ""
    ):
        """
        Initialize retention campaign manager.

        Args:
            client_id: Client identifier
            company_name: Company name for personalization
            email: Contact email
        """
        self.client_id = client_id
        self.company_name = company_name
        self.email = email

        self._campaigns: Dict[str, RetentionCampaign] = {}
        self._messages: Dict[str, CampaignMessage] = {}

    async def create_campaign(
        self,
        campaign_type: CampaignType,
        trigger_conditions: Optional[Dict[str, Any]] = None,
        custom_messages: Optional[List[Dict[str, Any]]] = None,
        discount_offer: Optional[Dict[str, Any]] = None,
        ab_test: bool = False
    ) -> RetentionCampaign:
        """
        Create a new retention campaign.

        Args:
            campaign_type: Type of campaign
            trigger_conditions: Conditions to trigger campaign
            custom_messages: Custom message templates
            discount_offer: Optional discount offer
            ab_test: Whether to enable A/B testing

        Returns:
            Created RetentionCampaign
        """
        template = CAMPAIGN_TEMPLATES.get(campaign_type, {})

        campaign = RetentionCampaign(
            name=template.get("name", f"{campaign_type.value.title()} Campaign"),
            campaign_type=campaign_type,
            status=CampaignStatus.DRAFT,
            target_segment=self._determine_segment(campaign_type),
            trigger_conditions=trigger_conditions or template.get("trigger", {}),
            messages=custom_messages or template.get("messages", []),
            discount_offer=discount_offer or template.get("discount"),
            ab_test_variant="A" if ab_test else None,
        )

        self._campaigns[str(campaign.id)] = campaign

        logger.info(
            "Retention campaign created",
            extra={
                "client_id": self.client_id,
                "campaign_id": str(campaign.id),
                "campaign_type": campaign_type.value,
            }
        )

        return campaign

    async def trigger_campaign(
        self,
        campaign_id: UUID,
        trigger_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger a campaign for a client.

        Args:
            campaign_id: Campaign to trigger
            trigger_data: Data that triggered the campaign

        Returns:
            Dict with trigger result
        """
        campaign = self._campaigns.get(str(campaign_id))
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        if campaign.status != CampaignStatus.ACTIVE:
            raise ValueError(f"Campaign is {campaign.status.value}")

        # Check trigger conditions
        if not await self._check_conditions(campaign.trigger_conditions, trigger_data):
            return {
                "triggered": False,
                "reason": "conditions_not_met",
            }

        # Create personalized messages
        messages = await self._create_messages(campaign)

        logger.info(
            "Retention campaign triggered",
            extra={
                "client_id": self.client_id,
                "campaign_id": str(campaign_id),
                "message_count": len(messages),
            }
        )

        return {
            "triggered": True,
            "campaign_id": str(campaign_id),
            "messages_created": len(messages),
            "first_message_scheduled": messages[0].scheduled_at.isoformat() if messages else None,
        }

    async def send_personalized_message(
        self,
        message_type: str,
        template_vars: Dict[str, Any],
        channel: MessageChannel = MessageChannel.EMAIL
    ) -> CampaignMessage:
        """
        Send a personalized message.

        Args:
            message_type: Type of message
            template_vars: Variables for personalization
            channel: Delivery channel

        Returns:
            CampaignMessage sent
        """
        # Generate personalized content
        subject, body = await self._generate_personalized_content(
            message_type, template_vars
        )

        message = CampaignMessage(
            client_id=self.client_id,
            message_type=message_type,
            subject=subject,
            body=body,
            channel=channel,
            sent_at=datetime.now(timezone.utc),
        )

        self._messages[str(message.id)] = message

        logger.info(
            "Personalized message sent",
            extra={
                "client_id": self.client_id,
                "message_type": message_type,
                "channel": channel.value,
            }
        )

        return message

    async def offer_discount(
        self,
        discount_percent: float,
        validity_days: int = 30,
        reason: str = "retention"
    ) -> Dict[str, Any]:
        """
        Create and offer a discount.

        Args:
            discount_percent: Discount percentage
            validity_days: Days until expiration
            reason: Reason for discount

        Returns:
            Dict with discount details
        """
        code = f"RETAIN{uuid4().hex[:8].upper()}"

        discount = {
            "code": code,
            "percent": discount_percent,
            "validity_days": validity_days,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=validity_days)).isoformat(),
            "reason": reason,
            "client_id": self.client_id,
        }

        logger.info(
            "Discount offered",
            extra={
                "client_id": self.client_id,
                "discount_percent": discount_percent,
                "code": code,
            }
        )

        return discount

    async def assign_success_manager(
        self,
        manager_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Assign a customer success manager.

        Args:
            manager_id: Optional specific manager ID

        Returns:
            Dict with assignment details
        """
        # In production, this would query available managers
        assigned_manager = manager_id or f"csm_{uuid4().hex[:6]}"

        logger.info(
            "Success manager assigned",
            extra={
                "client_id": self.client_id,
                "manager_id": assigned_manager,
            }
        )

        return {
            "assigned": True,
            "client_id": self.client_id,
            "manager_id": assigned_manager,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
        }

    async def create_ab_test(
        self,
        campaign_id: UUID,
        variant_a: Dict[str, Any],
        variant_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create A/B test for campaign.

        Args:
            campaign_id: Campaign to test
            variant_a: Control variant
            variant_b: Test variant

        Returns:
            Dict with test configuration
        """
        campaign = self._campaigns.get(str(campaign_id))
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        test_id = f"ab_{uuid4().hex[:8]}"

        logger.info(
            "A/B test created",
            extra={
                "client_id": self.client_id,
                "campaign_id": str(campaign_id),
                "test_id": test_id,
            }
        )

        return {
            "test_id": test_id,
            "campaign_id": str(campaign_id),
            "variant_a": variant_a,
            "variant_b": variant_b,
            "split_ratio": 0.5,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_campaign_metrics(
        self,
        campaign_id: UUID
    ) -> Dict[str, Any]:
        """
        Get metrics for a campaign.

        Args:
            campaign_id: Campaign to analyze

        Returns:
            Dict with campaign metrics
        """
        campaign = self._campaigns.get(str(campaign_id))
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        # Calculate metrics from messages
        campaign_messages = [
            m for m in self._messages.values()
            if str(m.campaign_id) == str(campaign_id)
        ]

        sent = len([m for m in campaign_messages if m.sent_at])
        opened = len([m for m in campaign_messages if m.opened_at])
        clicked = len([m for m in campaign_messages if m.clicked_at])

        metrics = {
            "campaign_id": str(campaign_id),
            "total_messages": len(campaign_messages),
            "sent": sent,
            "opened": opened,
            "clicked": clicked,
            "open_rate": round(opened / sent * 100, 2) if sent > 0 else 0,
            "click_rate": round(clicked / sent * 100, 2) if sent > 0 else 0,
        }

        campaign.metrics = metrics

        return metrics

    async def activate_campaign(self, campaign_id: UUID) -> Dict[str, Any]:
        """
        Activate a campaign.

        Args:
            campaign_id: Campaign to activate

        Returns:
            Dict with activation result
        """
        campaign = self._campaigns.get(str(campaign_id))
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        campaign.status = CampaignStatus.ACTIVE
        campaign.start_date = datetime.now(timezone.utc)

        return {
            "activated": True,
            "campaign_id": str(campaign_id),
            "status": campaign.status.value,
        }

    def _determine_segment(self, campaign_type: CampaignType) -> str:
        """Determine target segment for campaign type."""
        segments = {
            CampaignType.ENGAGEMENT: "at_risk_engagement",
            CampaignType.RE_ENGAGEMENT: "inactive_users",
            CampaignType.DISCOUNT: "high_churn_risk",
            CampaignType.SUCCESS_REVIEW: "high_value_at_risk",
            CampaignType.FEATURE_SPOTLIGHT: "low_feature_adoption",
            CampaignType.CHECK_IN: "all_active",
        }
        return segments.get(campaign_type, "general")

    async def _check_conditions(
        self,
        conditions: Dict[str, Any],
        trigger_data: Dict[str, Any]
    ) -> bool:
        """Check if trigger conditions are met."""
        for key, expected in conditions.items():
            actual = trigger_data.get(key)
            if actual is None:
                continue
            if isinstance(expected, bool) and expected != actual:
                return False
            if isinstance(expected, (int, float)) and actual < expected:
                return False
        return True

    async def _create_messages(
        self,
        campaign: RetentionCampaign
    ) -> List[CampaignMessage]:
        """Create scheduled messages for campaign."""
        messages = []
        now = datetime.now(timezone.utc)

        for msg_config in campaign.messages:
            scheduled = now + timedelta(days=msg_config.get("day", 0))

            message = CampaignMessage(
                campaign_id=campaign.id,
                client_id=self.client_id,
                message_type=msg_config.get("type", "standard"),
                subject=msg_config.get("subject", ""),
                channel=MessageChannel.EMAIL,
                scheduled_at=scheduled,
            )

            self._messages[str(message.id)] = message
            messages.append(message)

        return messages

    async def _generate_personalized_content(
        self,
        message_type: str,
        template_vars: Dict[str, Any]
    ) -> tuple:
        """Generate personalized message content."""
        templates = {
            "check_in": {
                "subject": "Checking in on your {product_name} experience",
                "body": "Hi {name}, we wanted to check in and see how things are going...",
            },
            "feature_spotlight": {
                "subject": "Discover {feature_name} - our latest feature",
                "body": "Hi {name}, have you tried {feature_name} yet?...",
            },
            "discount_offer": {
                "subject": "Special offer: {discount}% off for you",
                "body": "Hi {name}, as a valued customer, we're offering you...",
            },
            "success_review": {
                "subject": "Let's schedule your success review",
                "body": "Hi {name}, I'd like to schedule time to discuss your goals...",
            },
        }

        template = templates.get(message_type, templates["check_in"])

        subject = template["subject"].format(**template_vars)
        body = template["body"].format(**template_vars)

        return subject, body


# Export for testing
__all__ = [
    "RetentionCampaignManager",
    "RetentionCampaign",
    "CampaignMessage",
    "CampaignType",
    "CampaignStatus",
    "MessageChannel",
    "CAMPAIGN_TEMPLATES",
]
