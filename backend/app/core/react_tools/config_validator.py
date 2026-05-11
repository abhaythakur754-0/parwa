"""
PARWA ReAct Tool — Config Validator (Day 3)

Verifies customer settings and configuration to detect misconfigurations
that may cause issues. Enables the AI agent to:
- validate_config        Validate a specific configuration area
- check_all_configs      Run full configuration health check
- get_config_recommendations  Get recommendations for configuration improvements
- compare_config_to_best  Compare customer config to best practices

All actions are scoped to *company_id* (BC-001) and return
structured ToolResult (BC-008). Every method wrapped in try/except — never crash.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Any

from .base import ActionSchema, BaseReactTool, ToolResult, ToolSchema

logger = logging.getLogger(__name__)

# ── Configuration Areas and Validation Rules ────────────────────────

CONFIG_AREAS: dict[str, dict[str, Any]] = {
    "email_channel": {
        "name": "Email Channel Configuration",
        "description": "Email routing, forwarding, and sender settings",
        "checks": [
            {
                "check_id": "email_fwd",
                "name": "Email forwarding configured",
                "description": "Verify that email forwarding is set up for inbound messages",
                "critical": True,
                "best_practice": "Set up forwarding from your support email to your Parwa inbox address",
            },
            {
                "check_id": "email_sender",
                "name": "Custom sender domain verified",
                "description": "DKIM and SPF records configured for custom sending domain",
                "critical": False,
                "best_practice": "Add DKIM and SPF DNS records to improve email deliverability",
            },
            {
                "check_id": "email_signature",
                "name": "Email signature configured",
                "description": "Agent email signature is set for professional communication",
                "critical": False,
                "best_practice": "Set a consistent email signature with company branding",
            },
        ],
    },
    "chat_widget": {
        "name": "Chat Widget Configuration",
        "description": "Widget appearance, behavior, and deployment settings",
        "checks": [
            {
                "check_id": "widget_deployed",
                "name": "Widget script deployed on website",
                "description": "Chat widget JavaScript is installed on the customer website",
                "critical": True,
                "best_practice": "Add the widget script to all customer-facing pages for maximum availability",
            },
            {
                "check_id": "widget_branding",
                "name": "Widget branding customized",
                "description": "Widget colors and logo match company branding",
                "critical": False,
                "best_practice": "Customize widget colors, logo, and welcome message for brand consistency",
            },
            {
                "check_id": "widget_hours",
                "name": "Business hours configured",
                "description": "Chat availability hours are set for the widget",
                "critical": False,
                "best_practice": "Set business hours to manage customer expectations for response times",
            },
            {
                "check_id": "widget_offline_form",
                "name": "Offline form enabled",
                "description": "Offline message form is configured for after-hours visitors",
                "critical": False,
                "best_practice": "Enable the offline form so visitors can leave messages outside business hours",
            },
        ],
    },
    "automation": {
        "name": "Automation Rules",
        "description": "Triggers, assignment rules, and workflow automations",
        "checks": [
            {
                "check_id": "auto_assign",
                "name": "Auto-assignment rules active",
                "description": "At least one automatic ticket assignment rule is configured",
                "critical": True,
                "best_practice": "Set up auto-assignment rules based on channel, category, or priority to distribute workload evenly",
            },
            {
                "check_id": "triggers",
                "name": "Automation triggers configured",
                "description": "At least one automation trigger is active",
                "critical": False,
                "best_practice": "Create triggers for common scenarios: new ticket notification, SLA warnings, auto-tagging",
            },
            {
                "check_id": "sla_rules",
                "name": "SLA rules defined",
                "description": "Service Level Agreement rules are configured for response times",
                "critical": True,
                "best_practice": "Define SLA rules for each priority level to ensure timely responses",
            },
        ],
    },
    "knowledge_base": {
        "name": "Knowledge Base",
        "description": "KB articles, categories, and search settings",
        "checks": [
            {
                "check_id": "kb_articles",
                "name": "Minimum articles published",
                "description": "At least 10 KB articles are published for AI context",
                "critical": True,
                "best_practice": "Create at least 20-30 KB articles covering common questions, procedures, and policies for better AI accuracy",
            },
            {
                "check_id": "kb_categories",
                "name": "Categories organized",
                "description": "KB articles are organized into logical categories",
                "critical": False,
                "best_practice": "Use clear category names that match how customers think about their problems",
            },
            {
                "check_id": "kb_freshness",
                "name": "Articles recently updated",
                "description": "At least some articles have been updated in the last 30 days",
                "critical": False,
                "best_practice": "Review and update KB articles regularly to keep information current",
            },
        ],
    },
    "team": {
        "name": "Team & Agents",
        "description": "Agent accounts, roles, and team structure",
        "checks": [
            {
                "check_id": "agents_active",
                "name": "Active agents configured",
                "description": "At least one agent account is active and can receive tickets",
                "critical": True,
                "best_practice": "Ensure sufficient agent coverage for your expected ticket volume",
            },
            {
                "check_id": "agent_groups",
                "name": "Agent groups defined",
                "description": "Agents are organized into groups for specialized routing",
                "critical": False,
                "best_practice": "Create agent groups by specialization (billing, technical, general) for efficient routing",
            },
            {
                "check_id": "roles_configured",
                "name": "Roles and permissions set",
                "description": "Custom roles with appropriate permissions are configured",
                "critical": False,
                "best_practice": "Set up role-based access to control who can view, edit, and manage different areas",
            },
        ],
    },
    "api": {
        "name": "API & Integrations",
        "description": "API keys, webhooks, and third-party integrations",
        "checks": [
            {
                "check_id": "api_key_active",
                "name": "Active API key exists",
                "description": "At least one API key is active for integration access",
                "critical": False,
                "best_practice": "Create separate API keys for different integrations and rotate them periodically",
            },
            {
                "check_id": "webhooks_configured",
                "name": "Webhooks configured",
                "description": "Outbound webhooks are set up for event notifications",
                "critical": False,
                "best_practice": "Configure webhooks for key events (ticket.created, ticket.resolved) to sync with external systems",
            },
            {
                "check_id": "webhook_endpoint",
                "name": "Webhook endpoints returning 200",
                "description": "All registered webhook endpoints are responding successfully",
                "critical": True,
                "best_practice": "Monitor webhook delivery rates and set up retry logic on your endpoint",
            },
        ],
    },
}


def _simulate_config_check(
    company_id: str, check: dict[str, Any]
) -> dict[str, Any]:
    """Simulate a configuration check result."""
    # Simulate: 75% pass rate for critical checks, 85% for non-critical
    pass_rate = 0.75 if check.get("critical") else 0.85
    is_pass = random.random() < pass_rate

    status = "pass" if is_pass else random.choice(["fail", "warning"])

    return {
        "check_id": check["check_id"],
        "name": check["name"],
        "description": check["description"],
        "status": status,
        "is_pass": status == "pass",
        "is_critical": check.get("critical", False),
        "best_practice": check.get("best_practice", ""),
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }


# ── Tool Implementation ────────────────────────────────────────────


class ConfigValidatorTool(BaseReactTool):
    """ReAct tool for validating customer configuration settings.

    Provides:
      - validate_config: Validate a specific configuration area
      - check_all_configs: Run full configuration health check
      - get_config_recommendations: Get improvement recommendations
      - compare_config_to_best: Compare against best practices

    Day 3: Technical Support Diagnostic Tools — Pro tier.
    Used by the AI agent to verify customer settings and detect
    misconfigurations that may be causing issues.
    """

    def __init__(self) -> None:
        self._results_cache: dict[str, dict[str, Any]] = {}

    # ── Metadata ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "config_validator"

    @property
    def description(self) -> str:
        return (
            "Validate customer configuration settings, detect misconfigurations, "
            "check against best practices, and recommend improvements"
        )

    @property
    def actions(self) -> list[str]:
        return [
            "validate_config",
            "check_all_configs",
            "get_config_recommendations",
            "compare_config_to_best",
        ]

    # ── Schema ──────────────────────────────────────────────────

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            tool_name=self.name,
            description=self.description,
            actions=[
                ActionSchema(
                    name="validate_config",
                    description="Validate a specific configuration area for the customer",
                    parameters={
                        "type": "object",
                        "properties": {
                            "config_area": {
                                "type": "string",
                                "description": "Config area to validate: email_channel, chat_widget, automation, knowledge_base, team, api",
                            },
                        },
                        "required": ["config_area"],
                    },
                    required_params=["config_area"],
                    returns="Validation results for the specified config area",
                ),
                ActionSchema(
                    name="check_all_configs",
                    description="Run a full configuration health check across all areas",
                    parameters={
                        "type": "object",
                        "properties": {
                            "include_non_critical": {
                                "type": "boolean",
                                "description": "Include non-critical checks (default: true)",
                                "default": True,
                            },
                        },
                        "required": [],
                    },
                    required_params=[],
                    returns="Full config health dashboard with scores and issues",
                ),
                ActionSchema(
                    name="get_config_recommendations",
                    description="Get improvement recommendations based on current configuration",
                    parameters={
                        "type": "object",
                        "properties": {
                            "config_area": {
                                "type": "string",
                                "description": "Config area to get recommendations for (optional, omit for all)",
                            },
                        },
                        "required": [],
                    },
                    required_params=[],
                    returns="List of prioritized recommendations with expected impact",
                ),
                ActionSchema(
                    name="compare_config_to_best",
                    description="Compare customer configuration against industry best practices",
                    parameters={
                        "type": "object",
                        "properties": {
                            "config_area": {
                                "type": "string",
                                "description": "Config area to compare (optional, omit for all)",
                            },
                            "industry": {
                                "type": "string",
                                "description": "Industry for best practice context: ecommerce, logistics, saas, general",
                                "default": "general",
                            },
                        },
                        "required": [],
                    },
                    required_params=[],
                    returns="Best practice comparison with compliance score and gaps",
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
        await asyncio.sleep(random.uniform(0.02, 0.08))

        if action == "__health_check__":
            return ToolResult(success=True, error=None, data={"status": "ok"}, execution_time_ms=0)

        handler = {
            "validate_config": self._validate_config,
            "check_all_configs": self._check_all_configs,
            "get_config_recommendations": self._get_config_recommendations,
            "compare_config_to_best": self._compare_config_to_best,
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

    async def _validate_config(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Validate a specific configuration area."""
        config_area: str = params.get("config_area", "")

        if config_area not in CONFIG_AREAS:
            return ToolResult(
                success=False,
                error=f"Unknown config area: {config_area}. Available: {', '.join(CONFIG_AREAS.keys())}",
                data=None,
                execution_time_ms=0,
            )

        area_config = CONFIG_AREAS[config_area]
        check_results = []
        pass_count = 0
        critical_fails = 0

        for check in area_config["checks"]:
            result = _simulate_config_check(company_id, check)
            check_results.append(result)
            if result["is_pass"]:
                pass_count += 1
            elif result["is_critical"]:
                critical_fails += 1

        total = len(check_results)
        health_score = round((pass_count / total) * 100, 1) if total > 0 else 100.0

        return ToolResult(
            success=True,
            error=None,
            data={
                "company_id": company_id,
                "config_area": config_area,
                "area_name": area_config["name"],
                "health_score": health_score,
                "total_checks": total,
                "passed_checks": pass_count,
                "critical_failures": critical_fails,
                "check_results": check_results,
                "validated_at": datetime.now(timezone.utc).isoformat(),
            },
            execution_time_ms=0,
        )

    async def _check_all_configs(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Run full configuration health check."""
        include_non_critical: bool = params.get("include_non_critical", True)

        all_results: dict[str, Any] = {}
        total_checks = 0
        total_passes = 0
        total_critical_fails = 0

        for area_id, area_config in CONFIG_AREAS.items():
            checks_to_run = area_config["checks"]
            if not include_non_critical:
                checks_to_run = [c for c in checks_to_run if c.get("critical")]

            area_results = []
            area_passes = 0

            for check in checks_to_run:
                result = _simulate_config_check(company_id, check)
                area_results.append(result)
                if result["is_pass"]:
                    area_passes += 1
                elif result["is_critical"]:
                    total_critical_fails += 1

            area_total = len(area_results)
            total_checks += area_total
            total_passes += area_passes

            all_results[area_id] = {
                "area_name": area_config["name"],
                "health_score": round((area_passes / area_total) * 100, 1) if area_total > 0 else 100.0,
                "checks": area_results,
            }

        overall_score = round((total_passes / total_checks) * 100, 1) if total_checks > 0 else 100.0

        return ToolResult(
            success=True,
            error=None,
            data={
                "company_id": company_id,
                "overall_health_score": overall_score,
                "total_checks": total_checks,
                "passed_checks": total_passes,
                "critical_failures": total_critical_fails,
                "config_areas": all_results,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            },
            execution_time_ms=0,
        )

    async def _get_config_recommendations(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Get improvement recommendations."""
        config_area: str | None = params.get("config_area")

        areas_to_check = {config_area: CONFIG_AREAS[config_area]} if config_area and config_area in CONFIG_AREAS else CONFIG_AREAS

        recommendations: list[dict[str, Any]] = []

        for area_id, area_config in areas_to_check.items():
            for check in area_config["checks"]:
                result = _simulate_config_check(company_id, check)
                if not result["is_pass"]:
                    priority = "high" if check.get("critical") else "medium"
                    recommendations.append({
                        "config_area": area_id,
                        "area_name": area_config["name"],
                        "check_id": check["check_id"],
                        "check_name": check["name"],
                        "current_status": result["status"],
                        "priority": priority,
                        "recommendation": check.get("best_practice", "Review this configuration setting"),
                        "expected_impact": "High" if check.get("critical") else "Medium",
                    })

        # Sort by priority (high first)
        recommendations.sort(key=lambda x: 0 if x["priority"] == "high" else 1)

        return ToolResult(
            success=True,
            error=None,
            data={
                "company_id": company_id,
                "total_recommendations": len(recommendations),
                "high_priority_count": sum(1 for r in recommendations if r["priority"] == "high"),
                "recommendations": recommendations[:10],  # Limit to top 10
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            execution_time_ms=0,
        )

    async def _compare_config_to_best(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Compare customer config against best practices."""
        config_area: str | None = params.get("config_area")
        industry: str = params.get("industry", "general")

        areas_to_check = {config_area: CONFIG_AREAS[config_area]} if config_area and config_area in CONFIG_AREAS else CONFIG_AREAS

        # Industry-specific best practice benchmarks
        industry_benchmarks: dict[str, dict[str, float]] = {
            "ecommerce": {"email_channel": 90.0, "chat_widget": 95.0, "automation": 85.0, "knowledge_base": 80.0, "team": 75.0, "api": 70.0},
            "saas": {"email_channel": 85.0, "chat_widget": 80.0, "automation": 90.0, "knowledge_base": 95.0, "team": 80.0, "api": 90.0},
            "logistics": {"email_channel": 85.0, "chat_widget": 70.0, "automation": 90.0, "knowledge_base": 75.0, "team": 80.0, "api": 85.0},
            "general": {"email_channel": 85.0, "chat_widget": 80.0, "automation": 80.0, "knowledge_base": 80.0, "team": 80.0, "api": 75.0},
        }

        benchmarks = industry_benchmarks.get(industry, industry_benchmarks["general"])

        comparisons: list[dict[str, Any]] = []
        for area_id, area_config in areas_to_check.items():
            checks = area_config["checks"]
            pass_count = sum(1 for c in checks if random.random() < (0.75 if c.get("critical") else 0.85))
            score = round((pass_count / len(checks)) * 100, 1) if checks else 100.0
            benchmark = benchmarks.get(area_id, 80.0)
            gap = round(benchmark - score, 1)

            comparisons.append({
                "config_area": area_id,
                "area_name": area_config["name"],
                "current_score": score,
                "industry_benchmark": benchmark,
                "gap": gap,
                "meets_benchmark": score >= benchmark,
                "priority": "high" if gap > 20 else "medium" if gap > 10 else "low",
            })

        # Sort by gap (largest gap first)
        comparisons.sort(key=lambda x: x["gap"], reverse=True)

        current_avg = round(sum(c["current_score"] for c in comparisons) / len(comparisons), 1) if comparisons else 0
        benchmark_avg = round(sum(c["industry_benchmark"] for c in comparisons) / len(comparisons), 1) if comparisons else 0

        return ToolResult(
            success=True,
            error=None,
            data={
                "company_id": company_id,
                "industry": industry,
                "current_avg_score": current_avg,
                "industry_benchmark_avg": benchmark_avg,
                "overall_gap": round(benchmark_avg - current_avg, 1),
                "areas_meeting_benchmark": sum(1 for c in comparisons if c["meets_benchmark"]),
                "total_areas": len(comparisons),
                "comparisons": comparisons,
                "compared_at": datetime.now(timezone.utc).isoformat(),
            },
            execution_time_ms=0,
        )
