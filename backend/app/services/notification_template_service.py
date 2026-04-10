"""
Notification Template Service - Template management (MF05)

Handles:
- CRUD operations for notification templates
- Template versioning
- Variable validation
- Template preview/rendering
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationError
from database.models.tickets import NotificationTemplate


class NotificationTemplateService:
    """
    Service for managing notification templates.
    
    Features:
    - Template CRUD
    - Variable extraction and validation
    - Template versioning
    - Preview rendering
    """
    
    # Valid template variables by event type
    TEMPLATE_VARIABLES = {
        "ticket_created": [
            "ticket_id", "ticket_subject", "customer_name", "customer_email",
            "priority", "category", "channel", "created_at",
        ],
        "ticket_updated": [
            "ticket_id", "ticket_subject", "updated_fields", "updated_by",
            "old_values", "new_values", "updated_at",
        ],
        "ticket_assigned": [
            "ticket_id", "ticket_subject", "assignee_name", "assignee_type",
            "assigned_by", "assigned_at",
        ],
        "ticket_resolved": [
            "ticket_id", "ticket_subject", "resolved_by", "resolution_time",
            "resolved_at", "resolution_notes",
        ],
        "ticket_closed": [
            "ticket_id", "ticket_subject", "closed_by", "closed_at",
            "resolution_summary", "csat_rating",
        ],
        "ticket_reopened": [
            "ticket_id", "ticket_subject", "reopened_by", "reopen_reason",
            "reopen_count", "reopened_at",
        ],
        "sla_warning": [
            "ticket_id", "ticket_subject", "time_remaining", "sla_type",
            "deadline", "warning_level",
        ],
        "sla_breached": [
            "ticket_id", "ticket_subject", "breached_at", "breach_type",
            "time_elapsed", "escalation_level",
        ],
        "ticket_escalated": [
            "ticket_id", "ticket_subject", "escalation_reason", "escalated_to",
            "ai_summary", "escalated_at",
        ],
        "mention": [
            "ticket_id", "ticket_subject", "mentioned_by", "excerpt",
            "mention_context", "mentioned_at",
        ],
        "bulk_action_completed": [
            "action_type", "success_count", "failure_count", "total_count",
            "undo_token", "completed_at",
        ],
        "incident_created": [
            "incident_id", "incident_title", "status_update", "affected_services",
            "created_at", "estimated_resolution",
        ],
        "incident_resolved": [
            "incident_id", "incident_title", "resolution_summary", "duration",
            "resolved_at",
        ],
    }
    
    # System default templates (cannot be deleted)
    SYSTEM_TEMPLATES = [
        "ticket_created",
        "ticket_assigned",
        "ticket_resolved",
        "ticket_closed",
        "sla_warning",
        "sla_breached",
        "ticket_escalated",
    ]
    
    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
    
    def create_template(
        self,
        event_type: str,
        channel: str,
        subject_template: str,
        body_template: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: bool = True,
    ) -> NotificationTemplate:
        """
        Create a new notification template.
        
        Args:
            event_type: Event type this template is for
            channel: Channel (email, in_app, push)
            subject_template: Subject line template with variables
            body_template: Body template with variables
            name: Human-readable template name
            description: Template description
            is_active: Whether template is active
            
        Returns:
            Created NotificationTemplate
        """
        # Validate event type
        if event_type not in self.TEMPLATE_VARIABLES:
            raise ValidationError(f"Invalid event type: {event_type}")
        
        # Validate channel
        if channel not in ["email", "in_app", "push"]:
            raise ValidationError(f"Invalid channel: {channel}")
        
        # Validate template variables
        self._validate_template_variables(event_type, subject_template, "subject")
        self._validate_template_variables(event_type, body_template, "body")
        
        # Check for existing template
        existing = self.db.query(NotificationTemplate).filter(
            NotificationTemplate.company_id == self.company_id,
            NotificationTemplate.event_type == event_type,
            NotificationTemplate.channel == channel,
        ).first()
        
        if existing:
            # Create new version
            existing.is_active = False
            existing.version += 1
        
        template = NotificationTemplate(
            id=str(uuid4()),
            company_id=self.company_id,
            event_type=event_type,
            channel=channel,
            name=name or f"{event_type}_{channel}",
            description=description,
            subject_template=subject_template,
            body_template=body_template,
            is_active=is_active,
            version=existing.version + 1 if existing else 1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        return template
    
    def get_template(self, template_id: str) -> NotificationTemplate:
        """Get template by ID."""
        template = self.db.query(NotificationTemplate).filter(
            NotificationTemplate.id == template_id,
            NotificationTemplate.company_id == self.company_id,
        ).first()
        
        if not template:
            raise NotFoundError(f"Template {template_id} not found")
        
        return template
    
    def get_template_by_event(
        self,
        event_type: str,
        channel: str = "email",
    ) -> Optional[NotificationTemplate]:
        """Get active template for event type and channel."""
        return self.db.query(NotificationTemplate).filter(
            NotificationTemplate.company_id == self.company_id,
            NotificationTemplate.event_type == event_type,
            NotificationTemplate.channel == channel,
            NotificationTemplate.is_active == True,
        ).first()
    
    def list_templates(
        self,
        event_type: Optional[str] = None,
        channel: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[NotificationTemplate], int]:
        """
        List templates with filters.
        
        Args:
            event_type: Filter by event type
            channel: Filter by channel
            is_active: Filter by active status
            limit: Max results
            offset: Offset for pagination
            
        Returns:
            Tuple of (templates, total count)
        """
        query = self.db.query(NotificationTemplate).filter(
            NotificationTemplate.company_id == self.company_id,
        )
        
        if event_type:
            query = query.filter(NotificationTemplate.event_type == event_type)
        
        if channel:
            query = query.filter(NotificationTemplate.channel == channel)
        
        if is_active is not None:
            query = query.filter(NotificationTemplate.is_active == is_active)
        
        total = query.count()
        
        templates = query.order_by(
            desc(NotificationTemplate.updated_at)
        ).offset(offset).limit(limit).all()
        
        return templates, total
    
    def update_template(
        self,
        template_id: str,
        subject_template: Optional[str] = None,
        body_template: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> NotificationTemplate:
        """Update template."""
        template = self.get_template(template_id)
        
        if subject_template is not None:
            self._validate_template_variables(
                template.event_type, subject_template, "subject"
            )
            template.subject_template = subject_template
        
        if body_template is not None:
            self._validate_template_variables(
                template.event_type, body_template, "body"
            )
            template.body_template = body_template
        
        if name is not None:
            template.name = name
        
        if description is not None:
            template.description = description
        
        if is_active is not None:
            template.is_active = is_active
        
        template.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(template)
        
        return template
    
    def delete_template(self, template_id: str) -> bool:
        """Delete template (soft delete for system templates)."""
        template = self.get_template(template_id)
        
        if template.event_type in self.SYSTEM_TEMPLATES:
            # Soft delete - just deactivate
            template.is_active = False
            template.updated_at = datetime.utcnow()
        else:
            # Hard delete for custom templates
            self.db.delete(template)
        
        self.db.commit()
        return True
    
    def preview_template(
        self,
        template_id: str,
        sample_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Preview rendered template with sample data.
        
        Args:
            template_id: Template ID
            sample_data: Sample data for rendering
            
        Returns:
            Dict with rendered subject and body
        """
        template = self.get_template(template_id)
        
        # Generate sample data if not provided
        if not sample_data:
            sample_data = self._generate_sample_data(template.event_type)
        
        return {
            "subject": self._render(template.subject_template, sample_data),
            "body": self._render(template.body_template, sample_data),
            "event_type": template.event_type,
            "channel": template.channel,
        }
    
    def get_template_variables(self, event_type: str) -> List[str]:
        """Get valid variables for an event type."""
        return self.TEMPLATE_VARIABLES.get(event_type, [])
    
    def get_template_versions(
        self,
        event_type: str,
        channel: str,
    ) -> List[NotificationTemplate]:
        """Get all versions of a template."""
        return self.db.query(NotificationTemplate).filter(
            NotificationTemplate.company_id == self.company_id,
            NotificationTemplate.event_type == event_type,
            NotificationTemplate.channel == channel,
        ).order_by(desc(NotificationTemplate.version)).all()
    
    def restore_version(self, template_id: str) -> NotificationTemplate:
        """Restore a previous version as active."""
        template = self.get_template(template_id)
        
        # Deactivate current active version
        self.db.query(NotificationTemplate).filter(
            NotificationTemplate.company_id == self.company_id,
            NotificationTemplate.event_type == template.event_type,
            NotificationTemplate.channel == template.channel,
            NotificationTemplate.is_active == True,
        ).update({"is_active": False})
        
        # Activate this version
        template.is_active = True
        template.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(template)
        
        return template
    
    def clone_template(
        self,
        template_id: str,
        new_event_type: Optional[str] = None,
        new_channel: Optional[str] = None,
    ) -> NotificationTemplate:
        """Clone a template."""
        template = self.get_template(template_id)
        
        return self.create_template(
            event_type=new_event_type or template.event_type,
            channel=new_channel or template.channel,
            subject_template=template.subject_template,
            body_template=template.body_template,
            name=f"Clone of {template.name}",
            description=template.description,
        )
    
    def _validate_template_variables(
        self,
        event_type: str,
        template: str,
        field_name: str,
    ) -> None:
        """Validate that template only uses valid variables."""
        valid_vars = set(self.TEMPLATE_VARIABLES.get(event_type, []))
        
        # Extract variables from template
        pattern = r'\{\{(\w+)\}\}'
        found_vars = set(re.findall(pattern, template))
        
        invalid_vars = found_vars - valid_vars
        
        if invalid_vars:
            raise ValidationError(
                f"Invalid variables in {field_name}: {', '.join(invalid_vars)}. "
                f"Valid variables: {', '.join(valid_vars)}"
            )
    
    def _render(self, template: str, data: Dict[str, Any]) -> str:
        """Render template with data."""
        result = template
        for key, value in data.items():
            placeholder = "{{" + key + "}}"
            result = result.replace(placeholder, str(value) if value else "")
        return result
    
    def _generate_sample_data(self, event_type: str) -> Dict[str, Any]:
        """Generate sample data for preview."""
        samples = {
            "ticket_created": {
                "ticket_id": "TICKET-123",
                "ticket_subject": "Sample Ticket Subject",
                "customer_name": "John Doe",
                "customer_email": "john@example.com",
                "priority": "high",
                "category": "technical",
                "channel": "email",
                "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            },
            "ticket_assigned": {
                "ticket_id": "TICKET-123",
                "ticket_subject": "Sample Ticket Subject",
                "assignee_name": "Jane Agent",
                "assignee_type": "human",
                "assigned_by": "System",
                "assigned_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            },
            "ticket_resolved": {
                "ticket_id": "TICKET-123",
                "ticket_subject": "Sample Ticket Subject",
                "resolved_by": "Jane Agent",
                "resolution_time": "2 hours",
                "resolved_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                "resolution_notes": "Issue was fixed by restarting the service.",
            },
            "ticket_closed": {
                "ticket_id": "TICKET-123",
                "ticket_subject": "Sample Ticket Subject",
                "closed_by": "John Doe",
                "closed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                "resolution_summary": "Ticket resolved successfully.",
                "csat_rating": "5",
            },
            "sla_warning": {
                "ticket_id": "TICKET-123",
                "ticket_subject": "Sample Ticket Subject",
                "time_remaining": "2 hours",
                "sla_type": "first_response",
                "deadline": (datetime.utcnow()).strftime("%Y-%m-%d %H:%M"),
                "warning_level": "75%",
            },
            "sla_breached": {
                "ticket_id": "TICKET-123",
                "ticket_subject": "Sample Ticket Subject",
                "breached_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                "breach_type": "first_response",
                "time_elapsed": "5 hours",
                "escalation_level": "1",
            },
            "ticket_escalated": {
                "ticket_id": "TICKET-123",
                "ticket_subject": "Sample Ticket Subject",
                "escalation_reason": "Customer requested human agent",
                "escalated_to": "Human Queue",
                "ai_summary": "Customer had issues with login. Tried password reset but still unable to access.",
                "escalated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            },
            "incident_created": {
                "incident_id": "INC-001",
                "incident_title": "API Service Degradation",
                "status_update": "We are investigating reports of slow API response times.",
                "affected_services": "API, Dashboard",
                "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                "estimated_resolution": "1 hour",
            },
        }
        
        return samples.get(event_type, {"message": "Sample notification content"})
    
    def seed_default_templates(self) -> int:
        """Seed default templates for all event types."""
        count = 0
        
        default_templates = {
            "ticket_created": {
                "subject": "New Ticket: {{ticket_subject}}",
                "body": """
A new ticket has been created.

Ticket ID: {{ticket_id}}
Subject: {{ticket_subject}}
Customer: {{customer_name}} ({{customer_email}})
Priority: {{priority}}
Category: {{category}}
Channel: {{channel}}
Created: {{created_at}}

Please respond at your earliest convenience.
""".strip(),
            },
            "ticket_assigned": {
                "subject": "Ticket Assigned to You: {{ticket_subject}}",
                "body": """
A ticket has been assigned to you.

Ticket ID: {{ticket_id}}
Subject: {{ticket_subject}}
Assigned by: {{assigned_by}}
Assigned at: {{assigned_at}}

Please review and take action.
""".strip(),
            },
            "ticket_resolved": {
                "subject": "Your Ticket Has Been Resolved: {{ticket_subject}}",
                "body": """
Your support ticket has been resolved.

Ticket ID: {{ticket_id}}
Subject: {{ticket_subject}}
Resolution Time: {{resolution_time}}
Resolved at: {{resolved_at}}

Resolution Notes:
{{resolution_notes}}

If you have any further questions, please reply to this email.
""".strip(),
            },
            "ticket_closed": {
                "subject": "Ticket Closed: {{ticket_subject}}",
                "body": """
Your support ticket has been closed.

Ticket ID: {{ticket_id}}
Subject: {{ticket_subject}}
Closed at: {{closed_at}}

Summary: {{resolution_summary}}

Thank you for contacting us!
""".strip(),
            },
            "ticket_reopened": {
                "subject": "Ticket Reopened: {{ticket_subject}}",
                "body": """
A ticket has been reopened.

Ticket ID: {{ticket_id}}
Subject: {{ticket_subject}}
Reopened by: {{reopened_by}}
Reason: {{reopen_reason}}
Reopen Count: {{reopen_count}}

Please review and take action.
""".strip(),
            },
            "sla_warning": {
                "subject": "[SLA Warning] Ticket Requires Attention: {{ticket_subject}}",
                "body": """
SLA WARNING - Action Required

Ticket ID: {{ticket_id}}
Subject: {{ticket_subject}}
SLA Type: {{sla_type}}
Time Remaining: {{time_remaining}}
Deadline: {{deadline}}
Warning Level: {{warning_level}}

Please respond before the SLA deadline.
""".strip(),
            },
            "sla_breached": {
                "subject": "[SLA BREACHED] Immediate Action Required: {{ticket_subject}}",
                "body": """
SLA BREACHED - Escalated

Ticket ID: {{ticket_id}}
Subject: {{ticket_subject}}
SLA Type: {{breach_type}}
Breached At: {{breached_at}}
Time Elapsed: {{time_elapsed}}
Escalation Level: {{escalation_level}}

This ticket requires immediate attention.
""".strip(),
            },
            "ticket_escalated": {
                "subject": "Ticket Escalated: {{ticket_subject}}",
                "body": """
A ticket has been escalated to you.

Ticket ID: {{ticket_id}}
Subject: {{ticket_subject}}
Reason: {{escalation_reason}}
Escalated At: {{escalated_at}}

AI Conversation Summary:
{{ai_summary}}

Please take over this conversation.
""".strip(),
            },
        }
        
        for event_type, templates in default_templates.items():
            try:
                self.create_template(
                    event_type=event_type,
                    channel="email",
                    subject_template=templates["subject"],
                    body_template=templates["body"],
                    name=f"Default {event_type} Email",
                    description=f"Default email template for {event_type}",
                )
                count += 1
            except Exception:
                # Template may already exist
                pass
        
        return count
