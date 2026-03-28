"""
Plan Manager for SaaS Advanced Module.

Provides plan management including:
- Plan comparison logic
- Feature matrix per plan
- Price calculation (monthly/annual)
- Discount application
- Plan recommendations based on usage
- Custom plan support for enterprise
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PlanTier(str, Enum):
    """Plan tier enumeration."""
    MINI = "mini"
    PARWA = "parwa"
    PARWA_HIGH = "parwa_high"
    ENTERPRISE = "enterprise"


class BillingFrequency(str, Enum):
    """Billing frequency enumeration."""
    MONTHLY = "monthly"
    ANNUAL = "annual"
    QUARTERLY = "quarterly"


@dataclass
class PlanFeature:
    """Represents a plan feature."""
    name: str
    description: str
    included: bool = True
    limit: Optional[int] = None
    limit_unit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "included": self.included,
            "limit": self.limit,
            "limit_unit": self.limit_unit,
        }


@dataclass
class Plan:
    """Represents a subscription plan."""
    tier: PlanTier
    display_name: str
    description: str
    monthly_price: float
    annual_price: float
    features: List[PlanFeature] = field(default_factory=list)
    is_custom: bool = False
    custom_pricing: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "tier": self.tier.value,
            "display_name": self.display_name,
            "description": self.description,
            "monthly_price": self.monthly_price,
            "annual_price": self.annual_price,
            "features": [f.to_dict() for f in self.features],
            "is_custom": self.is_custom,
            "custom_pricing": self.custom_pricing,
        }


# Plan configurations
PLANS: Dict[PlanTier, Plan] = {
    PlanTier.MINI: Plan(
        tier=PlanTier.MINI,
        display_name="Mini",
        description="Perfect for small teams getting started with AI support",
        monthly_price=49.0,
        annual_price=470.0,  # ~20% discount
        features=[
            PlanFeature("AI Chat Support", "24/7 AI-powered chat support", True),
            PlanFeature("FAQ Automation", "Automated FAQ responses", True),
            PlanFeature("Email Support", "AI email handling", True),
            PlanFeature("Tickets per Month", "Monthly ticket limit", True, 500, "tickets"),
            PlanFeature("Voice Minutes", "Voice support minutes", True, 100, "minutes"),
            PlanFeature("AI Interactions", "Monthly AI interactions", True, 1000, "interactions"),
            PlanFeature("Max Concurrent Calls", "Simultaneous voice calls", True, 2, "calls"),
            PlanFeature("SMS Support", "SMS support channel", False),
            PlanFeature("Refund Execution", "Automated refund processing", False),
            PlanFeature("Custom Integrations", "Custom API integrations", False),
            PlanFeature("Analytics Dashboard", "Basic analytics", True),
            PlanFeature("Team Members", "Included team seats", True, 3, "seats"),
        ],
    ),
    PlanTier.PARWA: Plan(
        tier=PlanTier.PARWA,
        display_name="PARWA Junior",
        description="Ideal for growing businesses with advanced support needs",
        monthly_price=149.0,
        annual_price=1430.0,
        features=[
            PlanFeature("AI Chat Support", "24/7 AI-powered chat support", True),
            PlanFeature("FAQ Automation", "Automated FAQ responses", True),
            PlanFeature("Email Support", "AI email handling", True),
            PlanFeature("Tickets per Month", "Monthly ticket limit", True, 2000, "tickets"),
            PlanFeature("Voice Minutes", "Voice support minutes", True, 500, "minutes"),
            PlanFeature("AI Interactions", "Monthly AI interactions", True, 5000, "interactions"),
            PlanFeature("Max Concurrent Calls", "Simultaneous voice calls", True, 3, "calls"),
            PlanFeature("SMS Support", "SMS support channel", True),
            PlanFeature("Refund Execution", "Automated refund processing", True),
            PlanFeature("Custom Integrations", "Custom API integrations", False),
            PlanFeature("Analytics Dashboard", "Advanced analytics", True),
            PlanFeature("Team Members", "Included team seats", True, 10, "seats"),
            PlanFeature("Learning Agent", "Continuous improvement AI", True),
            PlanFeature("Approval Workflow", "Human approval for critical actions", True),
        ],
    ),
    PlanTier.PARWA_HIGH: Plan(
        tier=PlanTier.PARWA_HIGH,
        display_name="PARWA High",
        description="Enterprise-grade support with advanced AI capabilities",
        monthly_price=499.0,
        annual_price=4790.0,
        features=[
            PlanFeature("AI Chat Support", "24/7 AI-powered chat support", True),
            PlanFeature("FAQ Automation", "Automated FAQ responses", True),
            PlanFeature("Email Support", "AI email handling", True),
            PlanFeature("Tickets per Month", "Monthly ticket limit", True, 10000, "tickets"),
            PlanFeature("Voice Minutes", "Voice support minutes", True, 2000, "minutes"),
            PlanFeature("AI Interactions", "Monthly AI interactions", True, 25000, "interactions"),
            PlanFeature("Max Concurrent Calls", "Simultaneous voice calls", True, 5, "calls"),
            PlanFeature("SMS Support", "SMS support channel", True),
            PlanFeature("Refund Execution", "Automated refund processing", True),
            PlanFeature("Custom Integrations", "Custom API integrations", True),
            PlanFeature("Analytics Dashboard", "Full analytics suite", True),
            PlanFeature("Team Members", "Included team seats", True, 25, "seats"),
            PlanFeature("Learning Agent", "Continuous improvement AI", True),
            PlanFeature("Approval Workflow", "Human approval for critical actions", True),
            PlanFeature("Video Support", "Video call support", True),
            PlanFeature("Customer Success Agent", "Proactive customer success", True),
            PlanFeature("Coordination Agent", "Multi-team coordination", True),
            PlanFeature("SLA Monitoring", "Service level tracking", True),
            PlanFeature("HIPAA Compliance", "Healthcare compliance", True),
            PlanFeature("PCI DSS Compliance", "Payment compliance", True),
        ],
    ),
    PlanTier.ENTERPRISE: Plan(
        tier=PlanTier.ENTERPRISE,
        display_name="Enterprise",
        description="Custom solutions for large organizations",
        monthly_price=1499.0,
        annual_price=14390.0,
        features=[
            PlanFeature("Everything in PARWA High", "All PARWA High features", True),
            PlanFeature("Unlimited Tickets", "No ticket limits", True),
            PlanFeature("Unlimited Voice Minutes", "No voice minute limits", True),
            PlanFeature("Unlimited AI Interactions", "No interaction limits", True),
            PlanFeature("Dedicated Account Manager", "Personal support", True),
            PlanFeature("Custom SLA", "Tailored service levels", True),
            PlanFeature("SSO/SAML", "Single sign-on integration", True),
            PlanFeature("Custom Branding", "White-label support", True),
            PlanFeature("API Rate Limit Override", "Custom rate limits", True),
            PlanFeature("Priority Support", "24/7 priority support", True),
            PlanFeature("Custom Training", "Custom AI training", True),
            PlanFeature("On-premise Option", "Self-hosted deployment", True),
        ],
        is_custom=True,
        custom_pricing=True,
    ),
}


class PlanManager:
    """
    Manages subscription plans and comparisons.

    Features:
    - Plan comparison logic
    - Feature matrix management
    - Price calculation
    - Discount application
    - Usage-based recommendations
    - Custom enterprise plans
    """

    def __init__(self, client_id: str = ""):
        """
        Initialize plan manager.

        Args:
            client_id: Client identifier for multi-tenant isolation
        """
        self.client_id = client_id

    def get_plan(self, tier: PlanTier) -> Plan:
        """
        Get plan details for a tier.

        Args:
            tier: Plan tier

        Returns:
            Plan details
        """
        return PLANS.get(tier, PLANS[PlanTier.MINI])

    def get_all_plans(self) -> List[Plan]:
        """
        Get all available plans.

        Returns:
            List of all plans
        """
        return list(PLANS.values())

    def compare_plans(
        self,
        tier1: PlanTier,
        tier2: PlanTier
    ) -> Dict[str, Any]:
        """
        Compare two plans side by side.

        Args:
            tier1: First plan tier
            tier2: Second plan tier

        Returns:
            Dict with comparison details
        """
        plan1 = self.get_plan(tier1)
        plan2 = self.get_plan(tier2)

        feature_comparison = []
        all_feature_names = set()

        for feature in plan1.features:
            all_feature_names.add(feature.name)
        for feature in plan2.features:
            all_feature_names.add(feature.name)

        for name in sorted(all_feature_names):
            feat1 = next((f for f in plan1.features if f.name == name), None)
            feat2 = next((f for f in plan2.features if f.name == name), None)

            feature_comparison.append({
                "name": name,
                "plan1": feat1.to_dict() if feat1 else {"name": name, "included": False},
                "plan2": feat2.to_dict() if feat2 else {"name": name, "included": False},
                "difference": self._calculate_feature_difference(feat1, feat2),
            })

        monthly_diff = plan2.monthly_price - plan1.monthly_price
        annual_diff = plan2.annual_price - plan1.annual_price

        return {
            "plan1": plan1.to_dict(),
            "plan2": plan2.to_dict(),
            "feature_comparison": feature_comparison,
            "price_difference": {
                "monthly": monthly_diff,
                "annual": annual_diff,
                "monthly_formatted": f"${abs(monthly_diff):+.2f}",
                "annual_formatted": f"${abs(annual_diff):+.2f}",
            },
            "tier1_lower": monthly_diff > 0,
        }

    def calculate_price(
        self,
        tier: PlanTier,
        billing_frequency: BillingFrequency,
        seats: int = 1,
        discount_code: Optional[str] = None,
        custom_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate total price for a plan.

        Args:
            tier: Plan tier
            billing_frequency: Billing frequency
            seats: Number of seats (for seat-based pricing)
            discount_code: Optional discount code
            custom_price: Optional custom price for enterprise

        Returns:
            Dict with pricing details
        """
        plan = self.get_plan(tier)

        # Base price calculation
        if custom_price is not None:
            base_price = custom_price
        elif billing_frequency == BillingFrequency.ANNUAL:
            base_price = plan.annual_price
        elif billing_frequency == BillingFrequency.QUARTERLY:
            base_price = plan.monthly_price * 3 * 0.9  # 10% quarterly discount
        else:
            base_price = plan.monthly_price

        # Apply seat multiplier for plans with seat limits
        included_seats = self._get_included_seats(plan)
        extra_seats = max(0, seats - included_seats)
        seat_price = extra_seats * 15.0  # $15 per extra seat

        subtotal = base_price + seat_price

        # Apply discount
        discount_amount = 0.0
        discount_percent = 0.0
        if discount_code:
            discount = self._apply_discount_code(discount_code, subtotal)
            discount_amount = discount["amount"]
            discount_percent = discount["percent"]

        total = subtotal - discount_amount

        return {
            "tier": tier.value,
            "billing_frequency": billing_frequency.value,
            "base_price": base_price,
            "seats": seats,
            "included_seats": included_seats,
            "extra_seats": extra_seats,
            "seat_price": seat_price,
            "subtotal": subtotal,
            "discount_code": discount_code,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "total": max(0, total),
            "currency": "USD",
            "effective_monthly": total / 12 if billing_frequency == BillingFrequency.ANNUAL else total,
        }

    def recommend_plan(
        self,
        usage_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recommend a plan based on usage patterns.

        Args:
            usage_data: Current usage metrics

        Returns:
            Dict with recommended plan and reasoning
        """
        current_tier = PlanTier(usage_data.get("current_tier", "mini"))
        monthly_tickets = usage_data.get("monthly_tickets", 0)
        voice_minutes = usage_data.get("voice_minutes", 0)
        ai_interactions = usage_data.get("ai_interactions", 0)
        concurrent_calls = usage_data.get("concurrent_calls", 1)
        needs_sms = usage_data.get("needs_sms", False)
        needs_refund_execution = usage_data.get("needs_refund_execution", False)
        needs_video = usage_data.get("needs_video", False)
        team_size = usage_data.get("team_size", 3)

        # Calculate score for each tier
        scores = {}

        # Mini score
        mini_plan = PLANS[PlanTier.MINI]
        scores[PlanTier.MINI] = self._score_plan(
            mini_plan, monthly_tickets, voice_minutes,
            ai_interactions, concurrent_calls, needs_sms,
            needs_refund_execution, needs_video, team_size
        )

        # PARWA score
        parwa_plan = PLANS[PlanTier.PARWA]
        scores[PlanTier.PARWA] = self._score_plan(
            parwa_plan, monthly_tickets, voice_minutes,
            ai_interactions, concurrent_calls, needs_sms,
            needs_refund_execution, needs_video, team_size
        )

        # PARWA High score
        high_plan = PLANS[PlanTier.PARWA_HIGH]
        scores[PlanTier.PARWA_HIGH] = self._score_plan(
            high_plan, monthly_tickets, voice_minutes,
            ai_interactions, concurrent_calls, needs_sms,
            needs_refund_execution, needs_video, team_size
        )

        # Enterprise score
        enterprise_plan = PLANS[PlanTier.ENTERPRISE]
        scores[PlanTier.ENTERPRISE] = self._score_plan(
            enterprise_plan, monthly_tickets, voice_minutes,
            ai_interactions, concurrent_calls, needs_sms,
            needs_refund_execution, needs_video, team_size
        )

        # Find best fit
        recommended_tier = max(scores, key=scores.get)
        recommended_plan = PLANS[recommended_tier]

        reasoning = []
        if monthly_tickets > 2000:
            reasoning.append(f"Ticket volume ({monthly_tickets}/mo) exceeds PARWA limits")
        if voice_minutes > 500:
            reasoning.append(f"Voice usage ({voice_minutes} min) requires higher tier")
        if concurrent_calls > 3:
            reasoning.append(f"Concurrent call requirement ({concurrent_calls}) needs PARWA High")
        if needs_video:
            reasoning.append("Video support requires PARWA High or higher")
        if team_size > 25:
            reasoning.append(f"Team size ({team_size}) requires Enterprise")

        # Check if current tier is adequate
        current_score = scores.get(current_tier, 0)
        recommended_score = scores[recommended_tier]

        if current_tier == recommended_tier:
            reasoning.append("Current plan meets all requirements")
        elif recommended_score > current_score + 10:
            reasoning.append(f"Strong recommendation to upgrade to {recommended_tier.value}")
        elif recommended_score > current_score:
            reasoning.append(f"Consider upgrading to {recommended_tier.value} for better value")

        return {
            "current_tier": current_tier.value,
            "recommended_tier": recommended_tier.value,
            "recommended_plan": recommended_plan.to_dict(),
            "scores": {tier.value: score for tier, score in scores.items()},
            "reasoning": reasoning,
            "upgrade_recommended": recommended_tier != current_tier and recommended_score > current_score,
        }

    def get_feature_matrix(self) -> Dict[str, Any]:
        """
        Get feature matrix across all plans.

        Returns:
            Dict with feature comparison matrix
        """
        all_features = set()
        for plan in PLANS.values():
            for feature in plan.features:
                all_features.add(feature.name)

        matrix = {}
        for feature_name in sorted(all_features):
            matrix[feature_name] = {}
            for tier, plan in PLANS.items():
                feature = next((f for f in plan.features if f.name == feature_name), None)
                if feature:
                    matrix[feature_name][tier.value] = {
                        "included": feature.included,
                        "limit": feature.limit,
                        "limit_unit": feature.limit_unit,
                    }
                else:
                    matrix[feature_name][tier.value] = {
                        "included": False,
                        "limit": None,
                        "limit_unit": None,
                    }

        return {
            "features": matrix,
            "plans": [plan.to_dict() for plan in PLANS.values()],
        }

    def create_custom_plan(
        self,
        base_tier: PlanTier,
        custom_features: List[Dict[str, Any]],
        custom_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create a custom enterprise plan.

        Args:
            base_tier: Base tier to customize
            custom_features: List of custom feature configurations
            custom_price: Optional custom price

        Returns:
            Dict with custom plan details
        """
        base_plan = self.get_plan(base_tier)

        features = []
        for base_feature in base_plan.features:
            # Check for custom override
            custom_override = next(
                (f for f in custom_features if f.get("name") == base_feature.name),
                None
            )

            if custom_override:
                features.append(PlanFeature(
                    name=base_feature.name,
                    description=base_feature.description,
                    included=custom_override.get("included", base_feature.included),
                    limit=custom_override.get("limit", base_feature.limit),
                    limit_unit=custom_override.get("limit_unit", base_feature.limit_unit),
                ))
            else:
                features.append(base_feature)

        # Add new custom features
        for custom_feat in custom_features:
            if custom_feat.get("name") not in [f.name for f in features]:
                features.append(PlanFeature(
                    name=custom_feat["name"],
                    description=custom_feat.get("description", "Custom feature"),
                    included=custom_feat.get("included", True),
                    limit=custom_feat.get("limit"),
                    limit_unit=custom_feat.get("limit_unit"),
                ))

        custom_plan = Plan(
            tier=PlanTier.ENTERPRISE,
            display_name=f"Custom {base_plan.display_name}",
            description="Custom enterprise plan",
            monthly_price=custom_price or base_plan.monthly_price * 1.5,
            annual_price=custom_price or base_plan.annual_price * 1.5,
            features=features,
            is_custom=True,
            custom_pricing=custom_price is not None,
        )

        return {
            "custom_plan": custom_plan.to_dict(),
            "base_tier": base_tier.value,
            "customizations": custom_features,
        }

    def _calculate_feature_difference(
        self,
        feat1: Optional[PlanFeature],
        feat2: Optional[PlanFeature]
    ) -> Dict[str, Any]:
        """Calculate difference between two feature versions."""
        if not feat1 and not feat2:
            return {"type": "none"}

        if not feat1:
            return {"type": "added", "value": feat2.to_dict()}

        if not feat2:
            return {"type": "removed", "value": feat1.to_dict()}

        if feat1.included != feat2.included:
            return {
                "type": "availability_change",
                "from": feat1.included,
                "to": feat2.included,
            }

        if feat1.limit != feat2.limit:
            return {
                "type": "limit_change",
                "from": feat1.limit,
                "to": feat2.limit,
            }

        return {"type": "same"}

    def _get_included_seats(self, plan: Plan) -> int:
        """Get number of included seats for a plan."""
        seats_feature = next((f for f in plan.features if "Team Members" in f.name), None)
        return seats_feature.limit if seats_feature else 1

    def _apply_discount_code(
        self,
        code: str,
        subtotal: float
    ) -> Dict[str, Any]:
        """Apply a discount code to subtotal."""
        # Mock discount codes for testing
        discount_codes = {
            "LAUNCH20": {"percent": 20, "type": "percent"},
            "ANNUAL15": {"percent": 15, "type": "percent"},
            "FLAT50": {"amount": 50, "type": "flat"},
            "STARTUP": {"percent": 30, "type": "percent"},
        }

        discount = discount_codes.get(code.upper(), {"percent": 0, "type": "none"})

        if discount["type"] == "flat":
            return {"amount": discount["amount"], "percent": 0}

        percent = discount.get("percent", 0)
        return {
            "amount": subtotal * (percent / 100),
            "percent": percent,
        }

    def _score_plan(
        self,
        plan: Plan,
        tickets: int,
        voice_minutes: int,
        ai_interactions: int,
        concurrent_calls: int,
        needs_sms: bool,
        needs_refund: bool,
        needs_video: bool,
        team_size: int
    ) -> float:
        """Score a plan based on usage requirements."""
        score = 0.0

        # Check ticket limit
        ticket_feature = next((f for f in plan.features if "Tickets per Month" in f.name), None)
        if ticket_feature:
            if ticket_feature.limit is None or ticket_feature.limit >= tickets:
                score += 25
            elif ticket_feature.limit >= tickets * 0.8:
                score += 15
            else:
                score -= 10

        # Check voice minutes
        voice_feature = next((f for f in plan.features if "Voice Minutes" in f.name), None)
        if voice_feature:
            if voice_feature.limit is None or voice_feature.limit >= voice_minutes:
                score += 20
            elif voice_feature.limit >= voice_minutes * 0.8:
                score += 10

        # Check concurrent calls
        calls_feature = next((f for f in plan.features if "Concurrent Calls" in f.name), None)
        if calls_feature and calls_feature.limit:
            if calls_feature.limit >= concurrent_calls:
                score += 15
            else:
                score -= 15

        # Check required features
        if needs_sms:
            sms_feature = next((f for f in plan.features if "SMS" in f.name), None)
            if sms_feature and sms_feature.included:
                score += 10
            else:
                score -= 20

        if needs_refund:
            refund_feature = next((f for f in plan.features if "Refund Execution" in f.name), None)
            if refund_feature and refund_feature.included:
                score += 10
            else:
                score -= 15

        if needs_video:
            video_feature = next((f for f in plan.features if "Video" in f.name), None)
            if video_feature and video_feature.included:
                score += 15
            else:
                score -= 25

        # Check team size
        seats_feature = next((f for f in plan.features if "Team Members" in f.name), None)
        if seats_feature and seats_feature.limit:
            if seats_feature.limit >= team_size:
                score += 10
            else:
                score -= 10

        return score


# Export for testing
__all__ = [
    "PlanManager",
    "Plan",
    "PlanFeature",
    "PlanTier",
    "BillingFrequency",
    "PLANS",
]
