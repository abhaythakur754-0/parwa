"""
PARWA Agent Provisioning Service (F-095) — Jarvis "Create Agent"

Natural-language agent creation via Jarvis commands with full lifecycle
management. Handles parsing, validation, provisioning, setup tracking,
and activation of AI support agents.

Features:
- Parse NL commands to extract agent configuration
- Validate name uniqueness and plan limits per tenant
- Specialty disambiguation with clarification questions
- Financial action flagging for approval queue (BC-009)
- Agent record creation with setup log tracking
- Training trigger via Celery task (BC-004)
- Full agent lifecycle management

Methods:
- create_agent_from_command() — Parse NL command + validate + provision
- create_agent() — Direct agent creation from config
- complete_setup() — Finalize agent setup and activate
- get_setup_status() — Get current setup progress
- check_plan_limits() — Check current/max agents for tenant
- list_agents() — List agents with optional status filter
- get_agent_status() — Detailed agent status with metrics
- get_specialty_templates() — Get pre-defined specialty templates

Building Codes: BC-001 (multi-tenant), BC-007 (AI model),
               BC-009 (approval for financial), BC-011 (auth), BC-004 (Celery)
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.logger import get_logger

logger = get_logger("agent_provisioning_service")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Pre-defined specialty templates
SPECIALTY_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "billing_specialist": {
        "specialty": "billing_specialist",
        "display_name": "Billing Specialist",
        "description": "Handles billing inquiries, payment processing, "
                       "invoice management, and subscription questions.",
        "default_channels": ["chat", "email"],
        "default_permission_level": "advanced",
        "suggested_base_model": "gpt-4",
        "is_financial": True,
        "default_instructions": {
            "behavioral_rules": [
                "Always verify customer identity before discussing billing",
                "Never promise specific refund amounts without approval",
                "Escalate disputes over $100 to human agents",
            ],
            "tone_guidelines": {
                "formality": "professional",
                "empathy_level": "high",
            },
            "escalation_triggers": [
                "refund request > $100",
                "chargeback mention",
                "legal threats",
            ],
        },
    },
    "returns_specialist": {
        "specialty": "returns_specialist",
        "display_name": "Returns Specialist",
        "description": "Manages return requests, exchange processing, "
                       "and refund tracking.",
        "default_channels": ["chat", "email"],
        "default_permission_level": "advanced",
        "suggested_base_model": "gpt-4",
        "is_financial": True,
        "default_instructions": {
            "behavioral_rules": [
                "Verify order details before processing returns",
                "Check return policy eligibility automatically",
                "Escalate return requests exceeding policy limits",
            ],
            "tone_guidelines": {
                "formality": "friendly",
                "empathy_level": "high",
            },
            "escalation_triggers": [
                "return value > $200",
                "return outside policy window",
                "suspected fraud",
            ],
        },
    },
    "technical_support": {
        "specialty": "technical_support",
        "display_name": "Technical Support",
        "description": "Provides technical troubleshooting, product "
                       "guidance, and issue resolution.",
        "default_channels": ["chat", "email", "sms"],
        "default_permission_level": "standard",
        "suggested_base_model": "gpt-4",
        "is_financial": False,
        "default_instructions": {
            "behavioral_rules": [
                "Gather system details before diagnosing",
                "Walk through steps one at a time",
                "Escalate if issue persists after 3 attempts",
            ],
            "tone_guidelines": {
                "formality": "professional",
                "empathy_level": "medium",
            },
            "escalation_triggers": [
                "system outage detected",
                "data loss reported",
                "security concern",
            ],
        },
    },
    "general_support": {
        "specialty": "general_support",
        "display_name": "General Support",
        "description": "Handles general customer inquiries, FAQ, "
                       "and routing to specialized agents.",
        "default_channels": ["chat", "email", "sms"],
        "default_permission_level": "basic",
        "suggested_base_model": "gpt-3.5-turbo",
        "is_financial": False,
        "default_instructions": {
            "behavioral_rules": [
                "Greet customers by name when available",
                "Provide concise, helpful answers",
                "Route complex issues to specialized agents",
            ],
            "tone_guidelines": {
                "formality": "friendly",
                "empathy_level": "medium",
            },
            "escalation_triggers": [
                "customer expresses frustration",
                "issue outside general knowledge",
                "VIP customer detected",
            ],
        },
    },
    "sales_assistant": {
        "specialty": "sales_assistant",
        "display_name": "Sales Assistant",
        "description": "Assists with product inquiries, pricing questions, "
                       "and purchase guidance.",
        "default_channels": ["chat", "email"],
        "default_permission_level": "standard",
        "suggested_base_model": "gpt-4",
        "is_financial": False,
        "default_instructions": {
            "behavioral_rules": [
                "Focus on customer needs before suggesting products",
                "Provide accurate pricing information",
                "Never pressure customers into purchases",
            ],
            "tone_guidelines": {
                "formality": "friendly",
                "empathy_level": "medium",
            },
            "escalation_triggers": [
                "enterprise pricing request",
                "custom deal negotiation",
                "bulk order inquiry",
            ],
        },
    },
    "onboarding_guide": {
        "specialty": "onboarding_guide",
        "display_name": "Onboarding Guide",
        "description": "Helps new customers through the setup process, "
                       "feature walkthroughs, and initial configuration.",
        "default_channels": ["chat", "email"],
        "default_permission_level": "basic",
        "suggested_base_model": "gpt-3.5-turbo",
        "is_financial": False,
        "default_instructions": {
            "behavioral_rules": [
                "Guide customers step by step through setup",
                "Check completion status before proceeding",
                "Offer proactive tips and best practices",
            ],
            "tone_guidelines": {
                "formality": "friendly",
                "empathy_level": "high",
            },
            "escalation_triggers": [
                "setup failure after 2 attempts",
                "integration issues",
                "customer requests human help",
            ],
        },
    },
    "vip_concierge": {
        "specialty": "vip_concierge",
        "display_name": "VIP Concierge",
        "description": "Dedicated support for VIP customers with "
                       "priority handling and personalized service.",
        "default_channels": ["chat", "email", "sms", "whatsapp"],
        "default_permission_level": "advanced",
        "suggested_base_model": "gpt-4",
        "is_financial": False,
        "default_instructions": {
            "behavioral_rules": [
                "Always prioritize VIP requests",
                "Use customer's preferred communication channel",
                "Remember previous interactions and preferences",
            ],
            "tone_guidelines": {
                "formality": "professional",
                "empathy_level": "high",
            },
            "escalation_triggers": [
                "any unresolved issue after 1 hour",
                "customer dissatisfaction detected",
                "revenue-impacting request",
            ],
        },
    },
    "feedback_collector": {
        "specialty": "feedback_collector",
        "display_name": "Feedback Collector",
        "description": "Gathers and categorizes customer feedback, "
                       "surveys, and satisfaction data.",
        "default_channels": ["chat", "email"],
        "default_permission_level": "basic",
        "suggested_base_model": "gpt-3.5-turbo",
        "is_financial": False,
        "default_instructions": {
            "behavioral_rules": [
                "Request feedback at natural conversation points",
                "Keep surveys short and focused",
                "Thank customers for their feedback",
            ],
            "tone_guidelines": {
                "formality": "friendly",
                "empathy_level": "high",
            },
            "escalation_triggers": [
                "negative feedback about critical issue",
                "feature request with high demand signals",
                "competitor comparison feedback",
            ],
        },
    },
}

# Permission level definitions
PERMISSION_LEVELS: Dict[str, Dict[str, Any]] = {
    "basic": {
        "permissions": [
            "read_tickets", "respond_tickets", "view_customers",
        ],
    },
    "standard": {
        "permissions": [
            "read_tickets", "respond_tickets", "view_customers",
            "escalate_tickets", "tag_tickets", "assign_tickets",
        ],
    },
    "advanced": {
        "permissions": [
            "read_tickets", "respond_tickets", "view_customers",
            "escalate_tickets", "tag_tickets", "assign_tickets",
            "process_refunds", "access_pii", "configure_integrations",
        ],
    },
    "admin": {
        "permissions": [
            "read_tickets", "respond_tickets", "view_customers",
            "escalate_tickets", "tag_tickets", "assign_tickets",
            "process_refunds", "access_pii", "configure_integrations",
            "manage_agents", "manage_settings", "view_analytics",
        ],
    },
}

# Plan-based agent limits
PLAN_AGENT_LIMITS: Dict[str, int] = {
    "free": 1,
    "starter": 3,
    "growth": 10,
    "pro": 25,
    "enterprise": -1,  # unlimited
}

# Setup steps in order
SETUP_STEPS = [
    "configuration", "training", "integration_setup",
    "permission_config", "testing", "activation",
]

# Specialty alias mapping (for NL parsing)
SPECIALTY_ALIASES: Dict[str, str] = {
    "billing": "billing_specialist",
    "bill": "billing_specialist",
    "finance": "billing_specialist",
    "payment": "billing_specialist",
    "refund": "billing_specialist",
    "returns": "returns_specialist",
    "return": "returns_specialist",
    "exchange": "returns_specialist",
    "tech": "technical_support",
    "technical": "technical_support",
    "support": "general_support",
    "general": "general_support",
    "sales": "sales_assistant",
    "onboarding": "onboarding_guide",
    "setup": "onboarding_guide",
    "vip": "vip_concierge",
    "concierge": "vip_concierge",
    "priority": "vip_concierge",
    "feedback": "feedback_collector",
    "survey": "feedback_collector",
}


# ══════════════════════════════════════════════════════════════════
# SERVICE CLASS
# ══════════════════════════════════════════════════════════════════


class AgentProvisioningService:
    """Agent Provisioning Service (F-095) — Jarvis "Create Agent".

    Manages the full lifecycle of AI support agent provisioning:
    from natural language command parsing through setup tracking
    to activation.

    BC-001: All methods scoped by company_id.
    BC-007: AI model configuration and training.
    BC-009: Financial actions flagged for approval.
    BC-011: Auth-scoped operations.
    BC-004: Celery task triggers for training.
    """

    def __init__(self, company_id: str):
        """Initialize the service for a specific tenant.

        Args:
            company_id: Tenant identifier (BC-001).
        """
        self.company_id = company_id

    # ── Core Methods ────────────────────────────────────────────

    def create_agent_from_command(
        self,
        user_id: str,
        command_text: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Parse NL command and create agent.

        Flow:
        1. Parse NL command to extract config
        2. Validate name uniqueness and plan limits
        3. Generate clarification questions if ambiguous
        4. Flag financial specialties for approval
        5. Create agent record with status="initializing"
        6. Create setup log entries
        7. Trigger training via Celery task

        Args:
            user_id: Creating user's ID (BC-011).
            command_text: Natural language command text.
            db: Database session.

        Returns:
            Dict with agent data, clarification questions,
            and approval flag.
        """
        # Parse the command
        config = self._parse_command(command_text)

        # Validate plan limits
        limits = self.check_plan_limits(db)
        if not limits["can_create"]:
            from app.exceptions import ValidationError
            raise ValidationError(
                message="Agent limit reached for current plan",
                details={
                    "current_agents": limits["current_agents"],
                    "max_agents": limits["max_agents"],
                    "upgrade_required": True,
                },
            )

        # Create the agent
        return self.create_agent(
            user_id=user_id,
            config=config,
            db=db,
        )

    def create_agent(
        self,
        user_id: str,
        config: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Any]:
        """Create agent from parsed configuration.

        Args:
            user_id: Creating user's ID.
            config: Agent configuration dict.
            db: Database session.

        Returns:
            Created agent data with clarification/approval info.
        """
        from database.models.agent import Agent, AgentSetupLog

        name = config.get("name", "").strip()
        specialty = config.get("specialty", "general_support")

        # Validate name
        if not name:
            from app.exceptions import ValidationError
            raise ValidationError(
                message="Agent name is required",
                details={"field": "name"},
            )

        # Check name uniqueness per tenant
        existing = db.query(Agent).filter(
            Agent.company_id == self.company_id,
            Agent.name == name,
            Agent.status != "deprovisioned",
        ).first()
        if existing:
            from app.exceptions import ValidationError
            raise ValidationError(
                message=f"Agent name '{name}' already exists",
                details={
                    "field": "name",
                    "existing_agent_id": existing.id,
                },
            )

        # Get specialty template for defaults
        template = SPECIALTY_TEMPLATES.get(specialty)
        is_financial = template.get("is_financial", False) if template else False

        # Resolve permissions
        permission_level = config.get("permission_level", "standard")
        if template and not config.get("permission_level"):
            permission_level = template.get(
                "default_permission_level", "standard",
            )

        permissions = self._build_permissions(
            level=permission_level,
            custom=config.get("custom_permissions"),
        )

        # Resolve channels
        channels = config.get("channels", [])
        if template and not channels:
            channels = template.get("default_channels", ["chat"])

        # Resolve base model
        base_model = config.get("base_model")
        if not base_model and template:
            base_model = template.get("suggested_base_model")

        # Build agent record
        agent = Agent(
            company_id=self.company_id,
            name=name,
            specialty=specialty,
            description=config.get("description") or (
                template.get("description") if template else None
            ),
            status="initializing",
            channels=json.dumps({"channels": channels}),
            permissions=json.dumps({
                "level": permission_level,
                "permissions": permissions,
            }),
            base_model=base_model,
            created_by=user_id,
        )
        db.add(agent)
        db.flush()

        # Create setup log entries
        for step in SETUP_STEPS:
            log_entry = AgentSetupLog(
                agent_id=agent.id,
                company_id=self.company_id,
                step=step,
                status="pending",
            )
            db.add(log_entry)

        # Complete the configuration step immediately
        config_log = db.query(AgentSetupLog).filter(
            AgentSetupLog.agent_id == agent.id,
            AgentSetupLog.step == "configuration",
        ).first()
        if config_log:
            config_log.status = "completed"
            config_log.configuration = json.dumps({
                "name": name,
                "specialty": specialty,
                "channels": channels,
                "permission_level": permission_level,
                "base_model": base_model,
            })
            config_log.completed_at = datetime.utcnow()

        db.flush()

        # Check for clarification needs
        clarification_questions = self._get_clarification_questions(
            command_text="", specialty=specialty, config=config,
        )

        # Determine if approval is needed (BC-009)
        requires_approval = is_financial or config.get(
            "requires_approval", False,
        )

        logger.info(
            "agent_created",
            company_id=self.company_id,
            agent_id=agent.id,
            agent_name=name,
            specialty=specialty,
            requires_approval=requires_approval,
            user_id=user_id,
        )

        return {
            "agent": self._serialize_agent(agent),
            "requires_approval": requires_approval,
            "clarification_needed": len(clarification_questions) > 0,
            "clarification_questions": clarification_questions,
            "message": "Agent created successfully" if not requires_approval
                       else "Agent created and pending approval",
        }

    def complete_setup(
        self,
        agent_id: str,
        configuration: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Any]:
        """Complete agent setup and activate.

        Marks all remaining setup steps as completed and transitions
        the agent to "active" status. Optionally triggers training.

        Args:
            agent_id: Agent UUID.
            configuration: Final configuration overrides.
            db: Database session.

        Returns:
            Activation result with timestamps.
        """
        from database.models.agent import Agent, AgentSetupLog

        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.company_id == self.company_id,
        ).first()

        if not agent:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message="Agent not found",
                details={"agent_id": agent_id},
            )

        if agent.status not in ("initializing", "training", "paused"):
            from app.exceptions import ValidationError
            raise ValidationError(
                message=f"Cannot complete setup for agent in "
                        f"'{agent.status}' status",
                details={
                    "agent_id": agent_id,
                    "current_status": agent.status,
                    "allowed_statuses": [
                        "initializing", "training", "paused",
                    ],
                },
            )

        now = datetime.utcnow()

        # Complete all pending setup steps
        pending_logs = db.query(AgentSetupLog).filter(
            AgentSetupLog.agent_id == agent_id,
            AgentSetupLog.company_id == self.company_id,
            AgentSetupLog.status == "pending",
        ).all()

        for log_entry in pending_logs:
            log_entry.status = "completed"
            log_entry.completed_at = now
            if log_entry.step == "permission_config":
                log_entry.configuration = json.dumps(
                    configuration.get("permissions", {}),
                )

        # Activate the agent
        agent.status = "active"
        agent.activated_at = now
        agent.updated_at = now

        db.flush()

        logger.info(
            "agent_setup_completed",
            company_id=self.company_id,
            agent_id=agent_id,
            user_action="complete_setup",
        )

        return {
            "agent_id": agent.id,
            "status": agent.status,
            "message": "Agent setup completed and activated",
            "activated_at": now.isoformat(),
        }

    def get_setup_status(
        self,
        agent_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Get the current setup progress for an agent.

        Args:
            agent_id: Agent UUID.
            db: Database session.

        Returns:
            Setup status with step-by-step progress.
        """
        from database.models.agent import Agent, AgentSetupLog

        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.company_id == self.company_id,
        ).first()

        if not agent:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message="Agent not found",
                details={"agent_id": agent_id},
            )

        setup_logs = db.query(AgentSetupLog).filter(
            AgentSetupLog.agent_id == agent_id,
        ).order_by(AgentSetupLog.created_at).all()

        steps = []
        completed_count = 0
        started_at = None
        completed_at = None

        for log_entry in setup_logs:
            step_data = {
                "step": log_entry.step,
                "status": log_entry.status,
                "configuration": (
                    json.loads(log_entry.configuration)
                    if log_entry.configuration
                    else {}
                ),
                "error_message": log_entry.error_message,
                "created_at": (
                    log_entry.created_at.isoformat()
                    if log_entry.created_at else None
                ),
                "completed_at": (
                    log_entry.completed_at.isoformat()
                    if log_entry.completed_at else None
                ),
            }
            steps.append(step_data)

            if log_entry.status == "completed":
                completed_count += 1
                if log_entry.completed_at:
                    if completed_at is None or \
                       log_entry.completed_at > completed_at:
                        completed_at = log_entry.completed_at

            if started_at is None and log_entry.created_at:
                started_at = log_entry.created_at

        # Determine overall status
        has_failed = any(s["status"] == "failed" for s in steps)
        all_completed = completed_count == len(steps)

        if has_failed:
            overall = "error"
        elif all_completed:
            overall = "completed"
        elif completed_count > 0:
            overall = "in_progress"
        else:
            overall = "pending"

        return {
            "agent_id": agent_id,
            "overall_status": overall,
            "steps": steps,
            "completed_steps": completed_count,
            "total_steps": len(steps),
            "started_at": (
                started_at.isoformat() if started_at else None
            ),
            "completed_at": (
                completed_at.isoformat() if completed_at else None
            ),
        }

    def check_plan_limits(
        self,
        db: Session,
    ) -> Dict[str, Any]:
        """Check current agent count vs plan limit.

        Args:
            db: Database session.

        Returns:
            Plan limits info with current/max counts.
        """
        from database.models.agent import Agent
        from database.models.core import Company

        # Get company plan
        company = db.query(Company).filter(
            Company.id == self.company_id,
        ).first()

        plan = "free"
        if company and hasattr(company, "plan"):
            plan = getattr(company, "plan", "free")

        max_agents = PLAN_AGENT_LIMITS.get(plan, 1)

        # Count active agents (excluding deprovisioned)
        current_count = db.query(Agent).filter(
            Agent.company_id == self.company_id,
            Agent.status != "deprovisioned",
        ).count()

        if max_agents == -1:  # unlimited
            return {
                "current_agents": current_count,
                "max_agents": -1,
                "available_slots": -1,
                "can_create": True,
                "plan": plan,
            }

        return {
            "current_agents": current_count,
            "max_agents": max_agents,
            "available_slots": max(0, max_agents - current_count),
            "can_create": current_count < max_agents,
            "plan": plan,
        }

    def list_agents(
        self,
        db: Session,
        status_filter: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List agents for the tenant.

        Args:
            db: Database session.
            status_filter: Optional status to filter by.
            limit: Pagination limit.
            offset: Pagination offset.

        Returns:
            Paginated agent list.
        """
        from database.models.agent import Agent

        query = db.query(Agent).filter(
            Agent.company_id == self.company_id,
        )

        if status_filter:
            query = query.filter(Agent.status == status_filter)

        total = query.count()
        agents = query.order_by(
            Agent.created_at.desc(),
        ).offset(offset).limit(limit).all()

        return {
            "agents": [self._serialize_agent(a) for a in agents],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_agent_status(
        self,
        agent_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Get detailed agent status with metrics.

        Args:
            agent_id: Agent UUID.
            db: Database session.

        Returns:
            Detailed agent status with setup, instructions, and metrics.
        """
        from database.models.agent import Agent

        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.company_id == self.company_id,
        ).first()

        if not agent:
            from app.exceptions import NotFoundError
            raise NotFoundError(
                message="Agent not found",
                details={"agent_id": agent_id},
            )

        result = {
            "agent": self._serialize_agent(agent),
            "setup_status": None,
            "active_instructions": None,
            "active_ab_test": None,
            "metrics": {},
        }

        # Get setup status if agent is not active
        if agent.status in ("initializing", "training", "error"):
            result["setup_status"] = self.get_setup_status(
                agent_id, db,
            )

        return result

    @staticmethod
    def get_specialty_templates() -> Dict[str, Any]:
        """Get all pre-defined specialty templates.

        Returns:
            Dict of specialty key → template data.
        """
        return {
            "templates": list(SPECIALTY_TEMPLATES.values()),
            "total": len(SPECIALTY_TEMPLATES),
        }

    # ── Command Parsing ─────────────────────────────────────────

    def _parse_command(self, command_text: str) -> Dict[str, Any]:
        """Parse natural language command into agent configuration.

        Extracts: name, specialty, description, channels, permissions.

        Args:
            command_text: Raw NL command text.

        Returns:
            Parsed configuration dict.
        """
        text = command_text.lower().strip()

        # Extract agent name (look for quoted names or "called X")
        name = self._extract_name(command_text)

        # Extract specialty
        specialty = self._extract_specialty(text)

        # Extract channels
        channels = self._extract_channels(text)

        # Extract permission level hints
        permission_level = self._extract_permission_level(text)

        # Build config
        config = {
            "name": name,
            "specialty": specialty,
            "channels": channels,
            "permission_level": permission_level,
            "clarification_needed": False,
            "clarification_questions": [],
        }

        # Check for financial actions
        template = SPECIALTY_TEMPLATES.get(specialty)
        if template:
            config["requires_approval"] = template.get(
                "is_financial", False,
            )

        return config

    def _extract_name(self, text: str) -> str:
        """Extract agent name from command text."""
        import re

        # Look for quoted name: "create agent named 'Alice'"
        quoted = re.findall(r'["\']([^"\']+)["\']', text)
        if quoted:
            return quoted[0].strip().title()

        # Look for "called X", "named X", "called X"
        patterns = [
            r"(?:called|named|name)\s+(\w+(?:\s+\w+)?)",
            r"agent\s+(\w+(?:\s+\w+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip().title()
                # Filter out common non-name words
                skip_words = {
                    "for", "with", "that", "this", "the", "a", "an",
                    "new", "create", "make", "add",
                }
                if name.lower() not in skip_words:
                    return name

        return ""

    def _extract_specialty(self, text: str) -> str:
        """Extract specialty from command text."""
        best_match = "general_support"
        best_match_len = 0

        for alias, specialty in SPECIALTY_ALIASES.items():
            if alias in text and len(alias) > best_match_len:
                best_match = specialty
                best_match_len = len(alias)

        return best_match

    def _extract_channels(self, text: str) -> List[str]:
        """Extract channel preferences from command text."""
        channels = []
        channel_keywords = {
            "chat": ["chat", "widget", "webchat"],
            "email": ["email", "mail"],
            "sms": ["sms", "text", "message"],
            "whatsapp": ["whatsapp"],
            "voice": ["voice", "call", "phone"],
        }

        for channel, keywords in channel_keywords.items():
            for kw in keywords:
                if kw in text:
                    channels.append(channel)
                    break

        return channels or ["chat"]

    def _extract_permission_level(self, text: str) -> str:
        """Extract permission level hints from command text."""
        if any(w in text for w in ["admin", "full access", "manage"]):
            return "admin"
        if any(w in text for w in ["advanced", "refund", "pii", "sensitive"]):
            return "advanced"
        if any(w in text for w in ["standard", "normal", "regular"]):
            return "standard"
        return "standard"

    def _get_clarification_questions(
        self,
        command_text: str,
        specialty: str,
        config: Dict[str, Any],
    ) -> List[str]:
        """Generate clarification questions for ambiguous commands.

        Args:
            command_text: Original command text.
            specialty: Resolved specialty.
            config: Parsed configuration.

        Returns:
            List of clarification questions (empty if unambiguous).
        """
        questions = []

        # No name provided
        if not config.get("name", "").strip():
            questions.append(
                "What would you like to name this agent?"
            )

        # Ambiguous specialty (e.g., "support" could be general or technical)
        if specialty == "general_support" and "support" in command_text:
            template = SPECIALTY_TEMPLATES.get("general_support")
            if template:
                questions.append(
                    "I'll create a general support agent. "
                    "Did you want a more specialized type? "
                    "(technical support, billing specialist, etc.)"
                )

        # Financial specialty
        if specialty in ("billing_specialist", "returns_specialist"):
            questions.append(
                "This agent will handle financial actions "
                "(refunds, billing). It will require admin "
                "approval before activation. Continue?"
            )

        return questions

    # ── Permissions ─────────────────────────────────────────────

    @staticmethod
    def _build_permissions(
        level: str = "standard",
        custom: Optional[List[str]] = None,
    ) -> List[str]:
        """Build permission list from level and custom additions.

        Args:
            level: Permission level name.
            custom: Additional custom permissions.

        Returns:
            Complete list of permission strings.
        """
        level_def = PERMISSION_LEVELS.get(level, PERMISSION_LEVELS["standard"])
        perms = list(level_def.get("permissions", []))

        if custom:
            for p in custom:
                if p not in perms:
                    perms.append(p)

        return perms

    # ── Serialization ───────────────────────────────────────────

    @staticmethod
    def _serialize_agent(agent: Any) -> Dict[str, Any]:
        """Serialize an Agent ORM object to dict."""
        channels_data = {}
        if hasattr(agent, "channels") and agent.channels:
            try:
                channels_data = json.loads(agent.channels)
            except (json.JSONDecodeError, TypeError):
                channels_data = {}

        permissions_data = {}
        if hasattr(agent, "permissions") and agent.permissions:
            try:
                permissions_data = json.loads(agent.permissions)
            except (json.JSONDecodeError, TypeError):
                permissions_data = {}

        return {
            "id": agent.id,
            "company_id": agent.company_id,
            "name": agent.name,
            "specialty": agent.specialty,
            "description": agent.description,
            "status": agent.status,
            "channels": channels_data,
            "permissions": permissions_data,
            "base_model": agent.base_model,
            "model_checkpoint_id": agent.model_checkpoint_id,
            "created_by": (
                str(agent.created_by) if agent.created_by else None
            ),
            "created_at": (
                agent.created_at.isoformat() if agent.created_at else None
            ),
            "activated_at": (
                agent.activated_at.isoformat() if agent.activated_at else None
            ),
            "updated_at": (
                agent.updated_at.isoformat() if agent.updated_at else None
            ),
        }


# ══════════════════════════════════════════════════════════════════
# LAZY SERVICE LOADING (BC-008)
# ══════════════════════════════════════════════════════════════════

_service_cache: Dict[str, AgentProvisioningService] = {}


def get_agent_provisioning_service(
    company_id: str,
) -> AgentProvisioningService:
    """Get or create an AgentProvisioningService for a tenant.

    Args:
        company_id: Tenant identifier (BC-001).

    Returns:
        AgentProvisioningService instance.
    """
    if company_id not in _service_cache:
        _service_cache[company_id] = AgentProvisioningService(company_id)
    return _service_cache[company_id]


__all__ = [
    "AgentProvisioningService",
    "get_agent_provisioning_service",
    "SPECIALTY_TEMPLATES",
    "PERMISSION_LEVELS",
    "PLAN_AGENT_LIMITS",
]
