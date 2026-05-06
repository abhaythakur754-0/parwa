"""
Message Templates Service

Provides message templates for various communication types including
onboarding, check-ins, feature announcements, retention, and custom templates.
Supports variable interpolation.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class TemplateCategory(str, Enum):
    """Categories of message templates."""
    ONBOARDING = "onboarding"
    CHECK_IN = "check_in"
    ANNOUNCEMENT = "announcement"
    RETENTION = "retention"
    SUPPORT = "support"
    ALERT = "alert"
    RENEWAL = "renewal"
    CUSTOM = "custom"


@dataclass
class MessageTemplate:
    """A message template with variable interpolation support."""
    template_id: str
    name: str
    category: TemplateCategory
    subject_template: str
    body_template: str
    variables: List[str]  # List of required variables
    channel: str  # email, in_app, sms
    description: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class MessageTemplates:
    """
    Message templates management.

    Provides:
    - Onboarding templates
    - Check-in templates
    - Feature announcement templates
    - Retention templates
    - Custom template support
    - Variable interpolation
    """

    # Default templates
    DEFAULT_TEMPLATES = [
        # Onboarding templates
        MessageTemplate(
            template_id="onboarding_welcome",
            name="Welcome to PARWA",
            category=TemplateCategory.ONBOARDING,
            subject_template="Welcome to PARWA, {client_name}!",
            body_template="""Hi {client_name},

Welcome to PARWA! We're excited to have you on board.

Your onboarding journey has begun. Here's what you can do next:
1. Complete your company profile
2. Set up your branding
3. Connect your integrations
4. Build your knowledge base

If you have any questions, our team is here to help.

Best regards,
The PARWA Team""",
            variables=["client_name"],
            channel="email",
            description="Welcome email for new clients"
        ),
        MessageTemplate(
            template_id="onboarding_step_complete",
            name="Onboarding Step Complete",
            category=TemplateCategory.ONBOARDING,
            subject_template="Great progress, {client_name}!",
            body_template="""Hi {client_name},

Congratulations on completing the {step_name} step!

Your onboarding is now {completion_percentage}% complete.

Next up: {next_step}

Keep up the great work!

The PARWA Team""",
            variables=["client_name", "step_name", "completion_percentage", "next_step"],
            channel="email",
            description="Notification when onboarding step is completed"
        ),
        MessageTemplate(
            template_id="onboarding_stuck",
            name="Onboarding Assistance",
            category=TemplateCategory.ONBOARDING,
            subject_template="Need help with your setup?",
            body_template="""Hi {client_name},

We noticed you might be stuck on the {stuck_step} step of your onboarding.

Would you like to schedule a quick call with our team to help you get back on track?

[Schedule a Call]

We're here to help you succeed!

The PARWA Team""",
            variables=["client_name", "stuck_step"],
            channel="email",
            description="Offer help when client is stuck on onboarding"
        ),

        # Check-in templates
        MessageTemplate(
            template_id="check_in_weekly",
            name="Weekly Check-in",
            category=TemplateCategory.CHECK_IN,
            subject_template="How's your week going, {client_name}?",
            body_template="""Hi {client_name},

Just checking in to see how things are going with PARWA this week.

Here's a quick summary of your performance:
- Tickets handled: {tickets_handled}
- Resolution rate: {resolution_rate}%
- Average response time: {avg_response_time}

Is there anything we can help you with?

Best,
The PARWA Team""",
            variables=["client_name", "tickets_handled", "resolution_rate", "avg_response_time"],
            channel="email",
            description="Weekly performance check-in"
        ),
        MessageTemplate(
            template_id="check_in_monthly",
            name="Monthly Success Review",
            category=TemplateCategory.CHECK_IN,
            subject_template="Your Monthly Success Report, {client_name}",
            body_template="""Hi {client_name},

Here's your monthly success report for {month}:

Key Metrics:
- Total conversations: {total_conversations}
- Customer satisfaction: {satisfaction_rate}%
- Time saved: {time_saved} hours

Highlights:
{highlights}

Areas for improvement:
{improvements}

Let's schedule your monthly review call to discuss these insights.

The PARWA Team""",
            variables=["client_name", "month", "total_conversations", "satisfaction_rate", "time_saved", "highlights", "improvements"],
            channel="email",
            description="Monthly success review email"
        ),

        # Announcement templates
        MessageTemplate(
            template_id="feature_announcement",
            name="New Feature Announcement",
            category=TemplateCategory.ANNOUNCEMENT,
            subject_template="New Feature: {feature_name}",
            body_template="""Hi {client_name},

We're excited to announce a new feature: {feature_name}!

{feature_description}

How to use it:
{usage_instructions}

This feature is now available in your dashboard. We'd love to hear your feedback!

Best,
The PARWA Team""",
            variables=["client_name", "feature_name", "feature_description", "usage_instructions"],
            channel="email",
            description="Announce new features to clients"
        ),

        # Retention templates
        MessageTemplate(
            template_id="retention_at_risk",
            name="At-Risk Client Outreach",
            category=TemplateCategory.RETENTION,
            subject_template="We value your partnership, {client_name}",
            body_template="""Hi {client_name},

We noticed you haven't been using PARWA as much lately, and we wanted to reach out.

Your success is our top priority. Is there anything we can do to help you get more value from PARWA?

We'd love to:
- Schedule a strategy session
- Provide additional training
- Discuss your current challenges

[Book a Call]

We're here to help you succeed.

The PARWA Team""",
            variables=["client_name"],
            channel="email",
            description="Outreach for at-risk clients"
        ),
        MessageTemplate(
            template_id="retention_win_back",
            name="Win-Back Campaign",
            category=TemplateCategory.RETENTION,
            subject_template="We miss you, {client_name}",
            body_template="""Hi {client_name},

It's been a while since we've seen you on PARWA.

We've made some exciting improvements since you were last here:
{improvements_list}

As a valued customer, we'd like to offer you:
{special_offer}

We'd love to have you back!

The PARWA Team""",
            variables=["client_name", "improvements_list", "special_offer"],
            channel="email",
            description="Win-back campaign for churned clients"
        ),

        # Support templates
        MessageTemplate(
            template_id="support_follow_up",
            name="Support Follow-up",
            category=TemplateCategory.SUPPORT,
            subject_template="Following up on your support ticket",
            body_template="""Hi {client_name},

We're following up on your recent support ticket regarding {ticket_subject}.

Did our solution resolve your issue? If not, please let us know and we'll continue to help.

[Rate Your Experience]

Thank you for being a PARWA customer!

The PARWA Team""",
            variables=["client_name", "ticket_subject"],
            channel="email",
            description="Follow-up after support resolution"
        ),

        # Alert templates
        MessageTemplate(
            template_id="alert_health_drop",
            name="Health Score Alert",
            category=TemplateCategory.ALERT,
            subject_template="Health Alert for {client_name}",
            body_template="""Alert: {client_name} health score has dropped.

Previous score: {previous_score}
Current score: {current_score}
Change: -{score_change} points

Primary concerns:
{concerns}

Recommended actions:
{recommendations}

This requires immediate attention.""",
            variables=["client_name", "previous_score", "current_score", "score_change", "concerns", "recommendations"],
            channel="in_app",
            description="Internal alert for health score drops"
        ),

        # Renewal templates
        MessageTemplate(
            template_id="renewal_reminder",
            name="Renewal Reminder",
            category=TemplateCategory.RENEWAL,
            subject_template="Your PARWA renewal is approaching",
            body_template="""Hi {client_name},

Your PARWA subscription is set to renew on {renewal_date}.

Current plan: {current_plan}
Annual value: {annual_value}

Let's schedule a quick call to discuss your renewal and ensure PARWA continues to meet your needs.

[Schedule Renewal Discussion]

Thank you for being a valued customer!

The PARWA Team""",
            variables=["client_name", "renewal_date", "current_plan", "annual_value"],
            channel="email",
            description="Reminder for upcoming renewal"
        ),
    ]

    def __init__(self):
        """Initialize message templates."""
        self._templates: Dict[str, MessageTemplate] = {
            t.template_id: t for t in self.DEFAULT_TEMPLATES
        }

    def get_template(self, template_id: str) -> Optional[MessageTemplate]:
        """
        Get a template by ID.

        Args:
            template_id: Template identifier

        Returns:
            MessageTemplate if found, None otherwise
        """
        return self._templates.get(template_id)

    def get_templates_by_category(
        self,
        category: TemplateCategory
    ) -> List[MessageTemplate]:
        """
        Get all templates in a category.

        Args:
            category: Template category

        Returns:
            List of templates in category
        """
        return [
            t for t in self._templates.values()
            if t.category == category and t.is_active
        ]

    def render_template(
        self,
        template_id: str,
        variables: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Render a template with variable interpolation.

        Args:
            template_id: Template identifier
            variables: Dict of variable names to values

        Returns:
            Dict with 'subject' and 'body' keys

        Raises:
            ValueError: If template not found or missing variables
        """
        template = self._templates.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        # Check for missing variables
        missing = [v for v in template.variables if v not in variables]
        if missing:
            raise ValueError(f"Missing variables: {missing}")

        # Interpolate variables
        subject = self._interpolate(template.subject_template, variables)
        body = self._interpolate(template.body_template, variables)

        return {
            "subject": subject,
            "body": body,
            "template_id": template_id,
        }

    def _interpolate(
        self,
        template_str: str,
        variables: Dict[str, Any]
    ) -> str:
        """
        Interpolate variables into template string.

        Supports {variable_name} syntax.
        """
        def replace_var(match):
            var_name = match.group(1)
            value = variables.get(var_name, match.group(0))
            return str(value)

        # Find all {variable} patterns and replace
        pattern = r'\{(\w+)\}'
        return re.sub(pattern, replace_var, template_str)

    def add_template(self, template: MessageTemplate) -> None:
        """
        Add a custom template.

        Args:
            template: MessageTemplate to add
        """
        template.created_at = datetime.utcnow()
        template.updated_at = datetime.utcnow()
        self._templates[template.template_id] = template
        logger.info(f"Added template: {template.name}")

    def update_template(
        self,
        template_id: str,
        updates: Dict[str, Any]
    ) -> Optional[MessageTemplate]:
        """
        Update an existing template.

        Args:
            template_id: Template identifier
            updates: Dict of fields to update

        Returns:
            Updated MessageTemplate
        """
        template = self._templates.get(template_id)
        if not template:
            return None

        for key, value in updates.items():
            if hasattr(template, key):
                setattr(template, key, value)

        template.updated_at = datetime.utcnow()
        logger.info(f"Updated template: {template_id}")
        return template

    def deactivate_template(self, template_id: str) -> bool:
        """Deactivate a template."""
        template = self._templates.get(template_id)
        if template:
            template.is_active = False
            template.updated_at = datetime.utcnow()
            return True
        return False

    def get_all_templates(self) -> List[MessageTemplate]:
        """Get all templates."""
        return list(self._templates.values())

    def get_active_templates(self) -> List[MessageTemplate]:
        """Get all active templates."""
        return [t for t in self._templates.values() if t.is_active]

    def validate_template(
        self,
        subject_template: str,
        body_template: str
    ) -> List[str]:
        """
        Validate a template for variable syntax.

        Args:
            subject_template: Subject template string
            body_template: Body template string

        Returns:
            List of variable names found
        """
        pattern = r'\{(\w+)\}'
        subject_vars = re.findall(pattern, subject_template)
        body_vars = re.findall(pattern, body_template)
        return list(set(subject_vars + body_vars))

    def get_template_summary(self) -> Dict[str, Any]:
        """Get summary of all templates."""
        by_category = {}
        for template in self._templates.values():
            cat = template.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "total_templates": len(self._templates),
            "active_templates": len(self.get_active_templates()),
            "by_category": by_category,
        }
