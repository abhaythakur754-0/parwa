"""
PARWA ReAct Tool — Service Health Checker (Day 3)

Provides real-time service status checking for the AI agent's ReAct pattern.
Exposes health-related actions:
- check_service_status     Check if a specific service is operational
- check_all_services       Get overall system health dashboard
- get_service_incidents    Retrieve active incidents for a service
- get_service_uptime       Get uptime percentage for a service over a period

All actions are scoped to *company_id* (BC-001) and return
structured ToolResult (BC-008). Every method wrapped in try/except — never crash.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import ActionSchema, BaseReactTool, ToolResult, ToolSchema

logger = logging.getLogger(__name__)

# ── Simulated Service Registry ─────────────────────────────────────

SERVICES: dict[str, dict[str, Any]] = {
    "api_gateway": {
        "name": "API Gateway",
        "category": "core",
        "sla_target": 99.9,
        "description": "Main API entry point for all client requests",
    },
    "auth_service": {
        "name": "Authentication Service",
        "category": "core",
        "sla_target": 99.95,
        "description": "Login, session management, and token validation",
    },
    "billing_service": {
        "name": "Billing Service",
        "category": "financial",
        "sla_target": 99.9,
        "description": "Subscription, invoicing, and payment processing",
    },
    "ai_pipeline": {
        "name": "AI Pipeline",
        "category": "ai",
        "sla_target": 99.5,
        "description": "AI response generation and technique execution",
    },
    "knowledge_base": {
        "name": "Knowledge Base",
        "category": "data",
        "sla_target": 99.8,
        "description": "RAG retrieval and knowledge search",
    },
    "email_service": {
        "name": "Email Service",
        "category": "channels",
        "sla_target": 99.7,
        "description": "Inbound/outbound email processing",
    },
    "chat_widget": {
        "name": "Chat Widget Service",
        "category": "channels",
        "sla_target": 99.8,
        "description": "Real-time chat widget and WebSocket connections",
    },
    "sms_service": {
        "name": "SMS Service",
        "category": "channels",
        "sla_target": 99.5,
        "description": "SMS channel via Twilio integration",
    },
    "webhook_service": {
        "name": "Webhook Service",
        "category": "integration",
        "sla_target": 99.7,
        "description": "Outbound webhook delivery and retry logic",
    },
    "analytics_service": {
        "name": "Analytics Service",
        "category": "data",
        "sla_target": 99.5,
        "description": "Metrics, dashboards, and reporting",
    },
}

# Incident severity levels
INCIDENT_SEVERITIES = ["low", "medium", "high", "critical"]

# Incident templates for simulation
INCIDENT_TEMPLATES: list[dict[str, Any]] = [
    {
        "title": "Increased API latency",
        "description": "Response times elevated by 200-500ms for some endpoints",
        "severity": "low",
        "affected_services": ["api_gateway"],
    },
    {
        "title": "Email delivery delays",
        "description": "Outbound emails experiencing 5-15 minute delays",
        "severity": "medium",
        "affected_services": ["email_service"],
    },
    {
        "title": "AI pipeline degraded",
        "description": "AI response generation slower than normal; fallback models activated",
        "severity": "medium",
        "affected_services": ["ai_pipeline"],
    },
    {
        "title": "Billing sync issues",
        "description": "Payment status updates delayed; Paddle webhook backlog",
        "severity": "high",
        "affected_services": ["billing_service"],
    },
    {
        "title": "Chat widget connection issues",
        "description": "Intermittent WebSocket disconnections affecting some users",
        "severity": "medium",
        "affected_services": ["chat_widget"],
    },
    {
        "title": "Knowledge base index stale",
        "description": "Recent KB articles not appearing in search results",
        "severity": "low",
        "affected_services": ["knowledge_base"],
    },
]


def _generate_service_status(service_id: str) -> dict[str, Any]:
    """Generate a simulated service status."""
    config = SERVICES.get(service_id, {})
    # 90% chance service is operational
    is_healthy = random.random() < 0.90
    status = "operational" if is_healthy else random.choice(["degraded", "partial_outage", "major_outage"])

    uptime_30d = round(random.uniform(99.0, 99.99) if is_healthy else random.uniform(95.0, 99.0), 2)

    return {
        "service_id": service_id,
        "service_name": config.get("name", service_id),
        "category": config.get("category", "unknown"),
        "status": status,
        "is_healthy": is_healthy,
        "uptime_30d": uptime_30d,
        "sla_target": config.get("sla_target", 99.9),
        "sla_met": uptime_30d >= config.get("sla_target", 99.9),
        "response_time_ms": round(random.uniform(20, 200) if is_healthy else random.uniform(200, 2000), 1),
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }


def _generate_incident(
    service_id: str,
    template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a simulated incident."""
    if template is None:
        template = random.choice(INCIDENT_TEMPLATES)

    started_at = datetime.now(timezone.utc) - timedelta(
        minutes=random.randint(5, 480)
    )
    is_resolved = random.random() < 0.3

    return {
        "incident_id": f"INC-{uuid.uuid4().hex[:8].upper()}",
        "title": template["title"],
        "description": template["description"],
        "severity": template["severity"],
        "status": "resolved" if is_resolved else "investigating",
        "affected_services": template["affected_services"],
        "started_at": started_at.isoformat(),
        "resolved_at": (started_at + timedelta(minutes=random.randint(10, 120))).isoformat() if is_resolved else None,
        "eta_minutes": random.randint(15, 240) if not is_resolved else 0,
        "updates": [
            {
                "timestamp": started_at.isoformat(),
                "message": "Incident detected and investigation started",
            },
        ],
    }


# ── Tool Implementation ────────────────────────────────────────────


class ServiceHealthCheckerTool(BaseReactTool):
    """ReAct tool for real-time service health checking.

    Provides:
      - check_service_status: Check if a specific service is operational
      - check_all_services: Get overall system health dashboard
      - get_service_incidents: Retrieve active incidents for a service
      - get_service_uptime: Get uptime percentage for a service over a period

    Day 3: Technical Support Diagnostic Tools — Pro tier.
    Used by the AI agent to check service health during tech support interactions,
    enabling real-time status communication to customers.
    """

    def __init__(self) -> None:
        self._incident_cache: dict[str, list[dict[str, Any]]] = {}

    # ── Metadata ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "service_health_checker"

    @property
    def description(self) -> str:
        return (
            "Check real-time service status, view active incidents, "
            "get uptime metrics, and assess system health for customer support"
        )

    @property
    def actions(self) -> list[str]:
        return [
            "check_service_status",
            "check_all_services",
            "get_service_incidents",
            "get_service_uptime",
        ]

    # ── Schema ──────────────────────────────────────────────────

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            tool_name=self.name,
            description=self.description,
            actions=[
                ActionSchema(
                    name="check_service_status",
                    description="Check if a specific service is currently operational",
                    parameters={
                        "type": "object",
                        "properties": {
                            "service_id": {
                                "type": "string",
                                "description": "Service to check: api_gateway, auth_service, billing_service, ai_pipeline, knowledge_base, email_service, chat_widget, sms_service, webhook_service, analytics_service",
                            },
                        },
                        "required": ["service_id"],
                    },
                    required_params=["service_id"],
                    returns="Service status object with health, uptime, and response time",
                ),
                ActionSchema(
                    name="check_all_services",
                    description="Get overall system health dashboard for all services",
                    parameters={
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Filter by category: core, financial, ai, data, channels, integration",
                            },
                        },
                        "required": [],
                    },
                    required_params=[],
                    returns="System health dashboard with per-service status and overall health score",
                ),
                ActionSchema(
                    name="get_service_incidents",
                    description="Retrieve active or recent incidents for a service",
                    parameters={
                        "type": "object",
                        "properties": {
                            "service_id": {
                                "type": "string",
                                "description": "Service to check incidents for",
                            },
                            "include_resolved": {
                                "type": "boolean",
                                "description": "Include recently resolved incidents (default: false)",
                                "default": False,
                            },
                        },
                        "required": ["service_id"],
                    },
                    required_params=["service_id"],
                    returns="List of incidents with severity, status, and ETA",
                ),
                ActionSchema(
                    name="get_service_uptime",
                    description="Get uptime percentage for a service over a specified period",
                    parameters={
                        "type": "object",
                        "properties": {
                            "service_id": {
                                "type": "string",
                                "description": "Service to check uptime for",
                            },
                            "period_days": {
                                "type": "integer",
                                "description": "Number of days to check (7, 30, 90)",
                                "default": 30,
                            },
                        },
                        "required": ["service_id"],
                    },
                    required_params=["service_id"],
                    returns="Uptime metrics with SLA compliance status",
                ),
            ],
        )

    # ── Execution ───────────────────────────────────────────────

    async def _do_execute(
        self,
        action: str,
        company_id: str,
        **params: Any,
    ) -> ToolResult:
        """Route action to the appropriate handler."""
        # Simulate API latency
        await asyncio.sleep(random.uniform(0.02, 0.10))

        if action == "__health_check__":
            return ToolResult(success=True, error=None, data={"status": "ok"}, execution_time_ms=0)

        handler = {
            "check_service_status": self._check_service_status,
            "check_all_services": self._check_all_services,
            "get_service_incidents": self._get_service_incidents,
            "get_service_uptime": self._get_service_uptime,
        }.get(action)

        if handler is None:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}. Available: {', '.join(self.actions)}",
                data=None,
                execution_time_ms=0,
            )

        return await handler(company_id, **params)

    # ── Action Handlers ─────────────────────────────────────────

    async def _check_service_status(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Check if a specific service is operational."""
        service_id: str = params.get("service_id", "")

        if service_id not in SERVICES:
            return ToolResult(
                success=False,
                error=f"Unknown service: {service_id}. Available: {', '.join(SERVICES.keys())}",
                data=None,
                execution_time_ms=0,
            )

        status = _generate_service_status(service_id)

        # Add company-specific context
        status["company_id"] = company_id
        status["customer_impact"] = self._assess_customer_impact(
            service_id, status["status"]
        )

        return ToolResult(success=True, error=None, data=status, execution_time_ms=0)

    async def _check_all_services(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Get overall system health dashboard."""
        category: str | None = params.get("category")

        services_to_check = SERVICES
        if category:
            services_to_check = {
                sid: cfg
                for sid, cfg in SERVICES.items()
                if cfg.get("category") == category
            }

        all_status = {}
        healthy_count = 0
        total_count = len(services_to_check)

        for service_id in services_to_check:
            status = _generate_service_status(service_id)
            all_status[service_id] = status
            if status["is_healthy"]:
                healthy_count += 1

        overall_health = round((healthy_count / total_count) * 100, 1) if total_count > 0 else 100.0

        # Determine overall system status
        if overall_health == 100:
            system_status = "all_operational"
        elif overall_health >= 80:
            system_status = "partial_degradation"
        elif overall_health >= 50:
            system_status = "major_degradation"
        else:
            system_status = "system_outage"

        return ToolResult(
            success=True,
            error=None,
            data={
                "company_id": company_id,
                "system_status": system_status,
                "overall_health_percentage": overall_health,
                "healthy_services": healthy_count,
                "total_services": total_count,
                "services": all_status,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "category_filter": category,
            },
            execution_time_ms=0,
        )

    async def _get_service_incidents(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Retrieve active or recent incidents for a service."""
        service_id: str = params.get("service_id", "")
        include_resolved: bool = params.get("include_resolved", False)

        if service_id not in SERVICES:
            return ToolResult(
                success=False,
                error=f"Unknown service: {service_id}. Available: {', '.join(SERVICES.keys())}",
                data=None,
                execution_time_ms=0,
            )

        # Generate incidents (70% chance of at least one active incident)
        incidents: list[dict[str, Any]] = []
        if random.random() < 0.70:
            # Generate 1-3 incidents for this service
            num_incidents = random.randint(1, 3)
            for _ in range(num_incidents):
                # Pick templates that affect this service
                matching_templates = [
                    t for t in INCIDENT_TEMPLATES
                    if service_id in t["affected_services"]
                ]
                if matching_templates:
                    template = random.choice(matching_templates)
                else:
                    template = random.choice(INCIDENT_TEMPLATES)

                incident = _generate_incident(service_id, template)
                if not include_resolved and incident["status"] == "resolved":
                    continue
                incidents.append(incident)

        # Sort by severity (critical first)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        incidents.sort(key=lambda x: severity_order.get(x["severity"], 4))

        active_count = sum(1 for i in incidents if i["status"] != "resolved")

        return ToolResult(
            success=True,
            error=None,
            data={
                "company_id": company_id,
                "service_id": service_id,
                "active_incidents": active_count,
                "total_incidents": len(incidents),
                "incidents": incidents,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            },
            execution_time_ms=0,
        )

    async def _get_service_uptime(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Get uptime percentage for a service over a period."""
        service_id: str = params.get("service_id", "")
        period_days: int = min(max(params.get("period_days", 30), 1), 90)

        if service_id not in SERVICES:
            return ToolResult(
                success=False,
                error=f"Unknown service: {service_id}. Available: {', '.join(SERVICES.keys())}",
                data=None,
                execution_time_ms=0,
            )

        config = SERVICES[service_id]
        sla_target = config.get("sla_target", 99.9)

        # Generate simulated uptime data
        uptime_percentage = round(random.uniform(99.0, 99.99), 4)
        downtime_minutes = round((100 - uptime_percentage) / 100 * period_days * 24 * 60, 1)

        # Daily breakdown for the period
        daily_data: list[dict[str, Any]] = []
        for i in range(min(period_days, 7)):  # Last 7 days detail
            day = datetime.now(timezone.utc) - timedelta(days=i)
            day_uptime = round(random.uniform(99.5, 100.0), 2)
            daily_data.append({
                "date": day.strftime("%Y-%m-%d"),
                "uptime": day_uptime,
                "incidents": random.randint(0, 2),
            })

        sla_met = uptime_percentage >= sla_target

        return ToolResult(
            success=True,
            error=None,
            data={
                "company_id": company_id,
                "service_id": service_id,
                "service_name": config.get("name", service_id),
                "period_days": period_days,
                "uptime_percentage": uptime_percentage,
                "downtime_minutes": downtime_minutes,
                "sla_target": sla_target,
                "sla_met": sla_met,
                "daily_breakdown": daily_data,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            },
            execution_time_ms=0,
        )

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _assess_customer_impact(service_id: str, status: str) -> str:
        """Assess how a service status impacts customers."""
        if status == "operational":
            return "No customer impact — service is fully functional"

        impact_map = {
            "api_gateway": {
                "degraded": "Slower response times for all API interactions",
                "partial_outage": "Some API endpoints unavailable; requests may fail intermittently",
                "major_outage": "Platform largely inaccessible; customers cannot access most features",
            },
            "auth_service": {
                "degraded": "Login may be slower than usual",
                "partial_outage": "Some users unable to log in or maintain sessions",
                "major_outage": "Most users unable to access the platform",
            },
            "billing_service": {
                "degraded": "Billing operations slower than normal",
                "partial_outage": "Payment processing and invoice generation affected",
                "major_outage": "No billing operations possible; payments will not process",
            },
            "ai_pipeline": {
                "degraded": "AI responses slower; fallback models may be used",
                "partial_outage": "AI responses limited or unavailable for some conversations",
                "major_outage": "AI-powered support unavailable; all conversations require human agents",
            },
            "knowledge_base": {
                "degraded": "Knowledge search results may be less relevant",
                "partial_outage": "Knowledge base search unavailable; AI responses may be less accurate",
                "major_outage": "No knowledge retrieval; AI responses may be generic without KB context",
            },
            "email_service": {
                "degraded": "Email delivery slower than normal",
                "partial_outage": "Some emails delayed or not delivered",
                "major_outage": "Email channel completely unavailable",
            },
            "chat_widget": {
                "degraded": "Chat widget may be slower to load",
                "partial_outage": "Chat widget intermittent; some users cannot connect",
                "major_outage": "Chat widget unavailable; customers cannot use live chat",
            },
            "sms_service": {
                "degraded": "SMS delivery slower than normal",
                "partial_outage": "Some SMS messages delayed or not delivered",
                "major_outage": "SMS channel completely unavailable",
            },
            "webhook_service": {
                "degraded": "Webhook delivery slightly delayed",
                "partial_outage": "Some webhooks not delivered; integrations may be stale",
                "major_outage": "Webhook delivery stopped; all integrations affected",
            },
            "analytics_service": {
                "degraded": "Dashboard loads slower than usual",
                "partial_outage": "Some analytics data may be stale or incomplete",
                "major_outage": "Analytics dashboard unavailable",
            },
        }

        service_impacts = impact_map.get(service_id, {})
        return service_impacts.get(
            status,
            f"Service {service_id} is in {status} state — customer impact may vary",
        )
