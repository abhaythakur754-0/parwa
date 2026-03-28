"""
Intervention Engine Service

Automated interventions for at-risk clients including automated check-ins,
proactive support offers, feature adoption nudges, and success manager alerts.
"""
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import asyncio

logger = logging.getLogger(__name__)


class InterventionType(str, Enum):
    """Types of automated interventions."""
    AUTOMATED_CHECK_IN = "automated_check_in"
    PROACTIVE_SUPPORT = "proactive_support"
    FEATURE_NUDGE = "feature_nudge"
    SUCCESS_MANAGER_ALERT = "success_manager_alert"
    WIN_BACK_CAMPAIGN = "win_back_campaign"
    USAGE_TIP = "usage_tip"
    TRAINING_OFFER = "training_offer"
    RENEWAL_REMINDER = "renewal_reminder"


class InterventionStatus(str, Enum):
    """Status of an intervention."""
    PENDING = "pending"
    TRIGGERED = "triggered"
    SENT = "sent"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TriggerCondition(str, Enum):
    """Conditions that trigger interventions."""
    LOW_ENGAGEMENT = "low_engagement"
    HIGH_RISK_SCORE = "high_risk_score"
    DECLINING_USAGE = "declining_usage"
    ACCURACY_DROP = "accuracy_drop"
    PAYMENT_ISSUE = "payment_issue"
    INACTIVITY = "inactivity"
    RENEWAL_APPROACHING = "renewal_approaching"
    SUPPORT_SPIKE = "support_spike"


@dataclass
class InterventionTemplate:
    """Template for an intervention."""
    template_id: str
    intervention_type: InterventionType
    name: str
    description: str
    trigger_conditions: List[TriggerCondition]
    channel: str  # email, in_app, sms
    subject_template: str
    body_template: str
    priority: int = 1
    cooldown_hours: int = 24


@dataclass
class Intervention:
    """An intervention instance."""
    intervention_id: str
    client_id: str
    intervention_type: InterventionType
    status: InterventionStatus
    trigger_condition: TriggerCondition
    template_used: str
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    recipient: Optional[str] = None
    response_received: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class InterventionEngine:
    """
    Automated intervention engine for client retention.

    Provides:
    - Automated check-ins
    - Proactive support offers
    - Feature adoption nudges
    - Success manager alerts
    - Intervention templates
    """

    # Default intervention templates
    DEFAULT_TEMPLATES = [
        InterventionTemplate(
            template_id="low_engagement_checkin",
            intervention_type=InterventionType.AUTOMATED_CHECK_IN,
            name="Low Engagement Check-in",
            description="Automated check-in for clients with low engagement",
            trigger_conditions=[TriggerCondition.LOW_ENGAGEMENT, TriggerCondition.INACTIVITY],
            channel="email",
            subject_template="Checking in: How can we help you succeed?",
            body_template="Hi {client_name}, we noticed you haven't been using PARWA lately. Is there anything we can help with?",
            priority=2,
            cooldown_hours=72,
        ),
        InterventionTemplate(
            template_id="high_risk_alert",
            intervention_type=InterventionType.SUCCESS_MANAGER_ALERT,
            name="High Risk Alert",
            description="Alert success manager for high-risk clients",
            trigger_conditions=[TriggerCondition.HIGH_RISK_SCORE],
            channel="in_app",
            subject_template="ALERT: {client_id} requires immediate attention",
            body_template="Client {client_id} has been flagged as high risk. Risk score: {risk_score}. Recommended actions: {recommended_actions}",
            priority=1,
            cooldown_hours=0,
        ),
        InterventionTemplate(
            template_id="feature_nudge",
            intervention_type=InterventionType.FEATURE_NUDGE,
            name="Feature Adoption Nudge",
            description="Encourage adoption of underutilized features",
            trigger_conditions=[TriggerCondition.DECLINING_USAGE, TriggerCondition.LOW_ENGAGEMENT],
            channel="email",
            subject_template="Discover features you might be missing",
            body_template="Hi {client_name}, did you know about these features? {features_list}",
            priority=3,
            cooldown_hours=168,
        ),
        InterventionTemplate(
            template_id="proactive_support",
            intervention_type=InterventionType.PROACTIVE_SUPPORT,
            name="Proactive Support Offer",
            description="Offer support to clients with accuracy or support issues",
            trigger_conditions=[TriggerCondition.ACCURACY_DROP, TriggerCondition.SUPPORT_SPIKE],
            channel="email",
            subject_template="We're here to help improve your experience",
            body_template="Hi {client_name}, we noticed some challenges and want to help. Would you like a dedicated support session?",
            priority=2,
            cooldown_hours=48,
        ),
        InterventionTemplate(
            template_id="training_offer",
            intervention_type=InterventionType.TRAINING_OFFER,
            name="Training Session Offer",
            description="Offer additional training to improve outcomes",
            trigger_conditions=[TriggerCondition.ACCURACY_DROP, TriggerCondition.DECLINING_USAGE],
            channel="email",
            subject_template="Free training session for your team",
            body_template="Hi {client_name}, we'd like to offer a complimentary training session to help you get the most from PARWA.",
            priority=3,
            cooldown_hours=168,
        ),
        InterventionTemplate(
            template_id="renewal_reminder",
            intervention_type=InterventionType.RENEWAL_REMINDER,
            name="Renewal Reminder",
            description="Reminder for upcoming renewal",
            trigger_conditions=[TriggerCondition.RENEWAL_APPROACHING],
            channel="email",
            subject_template="Your PARWA renewal is coming up",
            body_template="Hi {client_name}, your subscription renews on {renewal_date}. Let's discuss your success so far.",
            priority=1,
            cooldown_hours=0,
        ),
    ]

    # All supported clients
    SUPPORTED_CLIENTS = [
        "client_001", "client_002", "client_003", "client_004", "client_005",
        "client_006", "client_007", "client_008", "client_009", "client_010"
    ]

    def __init__(self):
        """Initialize intervention engine."""
        self._templates: Dict[str, InterventionTemplate] = {
            t.template_id: t for t in self.DEFAULT_TEMPLATES
        }
        self._interventions: Dict[str, List[Intervention]] = {
            client: [] for client in self.SUPPORTED_CLIENTS
        }
        self._intervention_counter = 0
        self._channel_handlers: Dict[str, Callable] = {}

    def register_channel_handler(
        self,
        channel: str,
        handler: Callable
    ) -> None:
        """
        Register a handler for an intervention channel.

        Args:
            channel: Channel name (email, in_app, sms)
            handler: Async callable to handle sending
        """
        self._channel_handlers[channel] = handler
        logger.info(f"Registered handler for channel: {channel}")

    def evaluate_triggers(
        self,
        client_id: str,
        client_data: Dict[str, Any]
    ) -> List[TriggerCondition]:
        """
        Evaluate which trigger conditions are met.

        Args:
            client_id: Client identifier
            client_data: Client metrics and data

        Returns:
            List of met trigger conditions
        """
        triggers = []

        # Low engagement
        engagement = client_data.get("engagement_score", 100)
        if engagement < 50:
            triggers.append(TriggerCondition.LOW_ENGAGEMENT)

        # High risk score
        risk_score = client_data.get("risk_score", 0)
        if risk_score >= 60:
            triggers.append(TriggerCondition.HIGH_RISK_SCORE)

        # Declining usage
        usage_trend = client_data.get("usage_trend", 0)
        if usage_trend < -15:
            triggers.append(TriggerCondition.DECLINING_USAGE)

        # Accuracy drop
        accuracy = client_data.get("accuracy_rate", 100)
        prev_accuracy = client_data.get("previous_accuracy", accuracy)
        if accuracy < 75 or (prev_accuracy - accuracy) > 10:
            triggers.append(TriggerCondition.ACCURACY_DROP)

        # Payment issue
        payment_issues = client_data.get("payment_issues", 0)
        if payment_issues > 0:
            triggers.append(TriggerCondition.PAYMENT_ISSUE)

        # Inactivity
        last_activity = client_data.get("last_activity_days", 0)
        if last_activity > 7:
            triggers.append(TriggerCondition.INACTIVITY)

        # Renewal approaching
        days_to_renewal = client_data.get("days_to_renewal", 180)
        if 0 < days_to_renewal < 30:
            triggers.append(TriggerCondition.RENEWAL_APPROACHING)

        # Support spike
        tickets = client_data.get("support_tickets_30d", 0)
        if tickets > 5:
            triggers.append(TriggerCondition.SUPPORT_SPIKE)

        return triggers

    def get_triggered_interventions(
        self,
        client_id: str,
        triggers: List[TriggerCondition]
    ) -> List[InterventionTemplate]:
        """
        Get interventions that should be triggered.

        Args:
            client_id: Client identifier
            triggers: Met trigger conditions

        Returns:
            List of applicable intervention templates
        """
        triggered = []

        for template in self._templates.values():
            # Check if any trigger condition matches
            for condition in template.trigger_conditions:
                if condition in triggers:
                    # Check cooldown
                    if not self._is_in_cooldown(client_id, template):
                        triggered.append(template)
                        break

        # Sort by priority
        triggered.sort(key=lambda t: t.priority)
        return triggered

    def _is_in_cooldown(
        self,
        client_id: str,
        template: InterventionTemplate
    ) -> bool:
        """Check if client is in cooldown period for this template."""
        if template.cooldown_hours == 0:
            return False

        history = self._interventions.get(client_id, [])
        cutoff = datetime.utcnow() - timedelta(hours=template.cooldown_hours)

        for intervention in history:
            if (intervention.template_used == template.template_id
                and intervention.triggered_at >= cutoff):
                return True

        return False

    async def trigger_intervention(
        self,
        client_id: str,
        template: InterventionTemplate,
        trigger_condition: TriggerCondition,
        context: Optional[Dict[str, Any]] = None
    ) -> Intervention:
        """
        Trigger an intervention for a client.

        Args:
            client_id: Client identifier
            template: Intervention template to use
            trigger_condition: Condition that triggered this
            context: Optional context for template rendering

        Returns:
            Created Intervention
        """
        self._intervention_counter += 1
        intervention_id = f"intervention_{self._intervention_counter:06d}"

        intervention = Intervention(
            intervention_id=intervention_id,
            client_id=client_id,
            intervention_type=template.intervention_type,
            status=InterventionStatus.TRIGGERED,
            trigger_condition=trigger_condition,
            template_used=template.template_id,
            metadata=context or {},
        )

        self._interventions[client_id].append(intervention)

        # Send via channel
        success = await self._send_intervention(intervention, template, context)

        if success:
            intervention.status = InterventionStatus.SENT
            intervention.sent_at = datetime.utcnow()
        else:
            intervention.status = InterventionStatus.FAILED

        logger.info(f"Intervention {intervention_id} triggered for {client_id}: {template.name}")
        return intervention

    async def _send_intervention(
        self,
        intervention: Intervention,
        template: InterventionTemplate,
        context: Optional[Dict[str, Any]]
    ) -> bool:
        """Send intervention through appropriate channel."""
        handler = self._channel_handlers.get(template.channel)

        if handler:
            try:
                await handler(intervention, template, context)
                return True
            except Exception as e:
                logger.error(f"Failed to send intervention: {e}")
                return False
        else:
            # Simulate sending
            logger.info(f"Simulating send via {template.channel}: {template.subject_template}")
            await asyncio.sleep(0.1)  # Simulate async operation
            return True

    def mark_completed(
        self,
        intervention_id: str,
        response_received: bool = False
    ) -> Optional[Intervention]:
        """
        Mark an intervention as completed.

        Args:
            intervention_id: Intervention identifier
            response_received: Whether client responded

        Returns:
            Updated Intervention
        """
        for client_id, interventions in self._interventions.items():
            for intervention in interventions:
                if intervention.intervention_id == intervention_id:
                    intervention.status = InterventionStatus.COMPLETED
                    intervention.completed_at = datetime.utcnow()
                    intervention.response_received = response_received
                    return intervention

        return None

    async def run_automated_interventions(
        self,
        clients_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, List[Intervention]]:
        """
        Run automated interventions for all clients.

        Args:
            clients_data: Dict mapping client_id to their data

        Returns:
            Dict mapping client_id to triggered interventions
        """
        results = {}

        for client_id, data in clients_data.items():
            if client_id not in self.SUPPORTED_CLIENTS:
                continue

            # Evaluate triggers
            triggers = self.evaluate_triggers(client_id, data)

            if not triggers:
                continue

            # Get applicable interventions
            templates = self.get_triggered_interventions(client_id, triggers)

            # Trigger interventions
            interventions = []
            for template in templates[:3]:  # Max 3 interventions per run
                # Use first matching trigger condition
                matching_trigger = next(
                    (t for t in triggers if t in template.trigger_conditions),
                    triggers[0]
                )
                intervention = await self.trigger_intervention(
                    client_id=client_id,
                    template=template,
                    trigger_condition=matching_trigger,
                    context=data
                )
                interventions.append(intervention)

            if interventions:
                results[client_id] = interventions

        logger.info(f"Automated interventions triggered for {len(results)} clients")
        return results

    def get_client_interventions(
        self,
        client_id: str,
        status: Optional[InterventionStatus] = None
    ) -> List[Intervention]:
        """Get interventions for a specific client."""
        interventions = self._interventions.get(client_id, [])

        if status:
            interventions = [i for i in interventions if i.status == status]

        return sorted(interventions, key=lambda i: i.triggered_at, reverse=True)

    def get_pending_interventions(self) -> List[Intervention]:
        """Get all pending (triggered but not sent) interventions."""
        pending = []
        for interventions in self._interventions.values():
            for intervention in interventions:
                if intervention.status in [InterventionStatus.PENDING, InterventionStatus.TRIGGERED]:
                    pending.append(intervention)

        return sorted(pending, key=lambda i: i.triggered_at)

    def get_intervention_summary(self) -> Dict[str, Any]:
        """Get summary of all interventions."""
        total = 0
        by_status = {s.value: 0 for s in InterventionStatus}
        by_type = {t.value: 0 for t in InterventionType}
        responses = 0

        for interventions in self._interventions.values():
            for intervention in interventions:
                total += 1
                by_status[intervention.status.value] += 1
                by_type[intervention.intervention_type.value] += 1
                if intervention.response_received:
                    responses += 1

        response_rate = (responses / total * 100) if total > 0 else 0

        return {
            "total_interventions": total,
            "by_status": by_status,
            "by_type": by_type,
            "response_rate": round(response_rate, 1),
            "pending_count": by_status.get("pending", 0) + by_status.get("triggered", 0),
        }

    def add_template(self, template: InterventionTemplate) -> None:
        """Add a custom intervention template."""
        self._templates[template.template_id] = template
        logger.info(f"Added template: {template.name}")

    def get_templates(self) -> List[InterventionTemplate]:
        """Get all intervention templates."""
        return list(self._templates.values())
