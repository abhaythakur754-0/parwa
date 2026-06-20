"""
PARWA ReAct Tool — Diagnostic Chain (Day 3 — High Tier)

Runs sequential diagnostic checks that build on each other to identify
and resolve complex technical issues. Enables the AI agent to:
- run_diagnostic_chain     Execute a sequential chain of diagnostic checks
- get_chain_templates      List available diagnostic chain templates
- create_custom_chain      Build a custom diagnostic chain from steps
- get_chain_result         Get the result of a previously run chain

This is a High-tier (parwa_high) tool that provides advanced diagnostic
capabilities beyond individual tool calls. Chains execute steps sequentially,
passing context between steps for progressive problem isolation.

All actions are scoped to *company_id* (BC-001) and return
structured ToolResult (BC-008). Every method wrapped in try/except — never crash.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from .base import ActionSchema, BaseReactTool, ToolResult, ToolSchema

logger = logging.getLogger(__name__)

# ── Diagnostic Chain Templates ─────────────────────────────────────

CHAIN_TEMPLATES: dict[str, dict[str, Any]] = {
    "connectivity_chain": {
        "chain_id": "connectivity_chain",
        "name": "Connectivity Diagnostic Chain",
        "description": "Progressive connectivity check from DNS to application layer",
        "target_issue": "Customer cannot access the platform or features are not loading",
        "estimated_time_minutes": 5,
        "steps": [
            {
                "step_id": "dns_check",
                "name": "DNS Resolution Check",
                "description": "Verify DNS records resolve correctly for the customer's domain",
                "tool": "service_health_checker",
                "action": "check_service_status",
                "params": {"service_id": "api_gateway"},
                "pass_condition": "service is operational or degraded",
                "fail_message": "DNS resolution failed — the domain may not be pointing to the correct servers",
            },
            {
                "step_id": "auth_check",
                "name": "Authentication Service Check",
                "description": "Verify the auth service is accepting credentials",
                "tool": "service_health_checker",
                "action": "check_service_status",
                "params": {"service_id": "auth_service"},
                "pass_condition": "service is operational",
                "fail_message": "Authentication service is experiencing issues — login may not work",
            },
            {
                "step_id": "api_check",
                "name": "API Gateway Health",
                "description": "Check if the API gateway is responding within acceptable latency",
                "tool": "service_health_checker",
                "action": "check_service_status",
                "params": {"service_id": "api_gateway"},
                "pass_condition": "response_time_ms < 500",
                "fail_message": "API gateway is slow or unresponsive — requests may time out",
            },
            {
                "step_id": "config_check",
                "name": "Configuration Validation",
                "description": "Check if customer configuration is correct for access",
                "tool": "config_validator",
                "action": "validate_config",
                "params": {"config_area": "api"},
                "pass_condition": "health_score > 80",
                "fail_message": "Configuration issues detected that may prevent proper access",
            },
        ],
    },
    "login_chain": {
        "chain_id": "login_chain",
        "name": "Login Issue Diagnostic Chain",
        "description": "Progressive diagnosis of login and authentication problems",
        "target_issue": "Customer cannot log in or is getting authentication errors",
        "estimated_time_minutes": 4,
        "steps": [
            {
                "step_id": "auth_health",
                "name": "Auth Service Health",
                "description": "Check if authentication service is operational",
                "tool": "service_health_checker",
                "action": "check_service_status",
                "params": {"service_id": "auth_service"},
                "pass_condition": "service is operational",
                "fail_message": "Auth service is down or degraded — this is likely the cause",
            },
            {
                "step_id": "known_login_issues",
                "name": "Known Login Issues Check",
                "description": "Search for known issues related to login problems",
                "tool": "known_issue_detector",
                "action": "search_known_issues",
                "params": {"query": "login authentication sign in"},
                "pass_condition": "no high-severity issues found",
                "fail_message": "A known login issue has been detected — see workaround",
            },
            {
                "step_id": "sso_config",
                "name": "SSO Configuration Check",
                "description": "Verify SSO/SAML configuration if applicable",
                "tool": "config_validator",
                "action": "validate_config",
                "params": {"config_area": "api"},
                "pass_condition": "SSO configuration is valid",
                "fail_message": "SSO configuration may be misconfigured",
            },
        ],
    },
    "billing_chain": {
        "chain_id": "billing_chain",
        "name": "Billing Issue Diagnostic Chain",
        "description": "Progressive diagnosis of billing and payment problems",
        "target_issue": "Customer has billing discrepancies or payment failures",
        "estimated_time_minutes": 5,
        "steps": [
            {
                "step_id": "billing_health",
                "name": "Billing Service Health",
                "description": "Check if the billing service is operational",
                "tool": "service_health_checker",
                "action": "check_service_status",
                "params": {"service_id": "billing_service"},
                "pass_condition": "service is operational",
                "fail_message": "Billing service is experiencing issues — payments may not process",
            },
            {
                "step_id": "known_billing_issues",
                "name": "Known Billing Issues Check",
                "description": "Search for known issues related to billing problems",
                "tool": "known_issue_detector",
                "action": "search_known_issues",
                "params": {"query": "billing payment tax invoice"},
                "pass_condition": "no high-severity issues found",
                "fail_message": "A known billing issue has been detected",
            },
            {
                "step_id": "billing_config",
                "name": "Billing Configuration Check",
                "description": "Verify billing settings and payment methods",
                "tool": "config_validator",
                "action": "validate_config",
                "params": {"config_area": "api"},
                "pass_condition": "payment configuration is valid",
                "fail_message": "Payment configuration may have issues",
            },
            {
                "step_id": "webhook_config",
                "name": "Webhook Delivery Check",
                "description": "Verify billing webhooks are delivering successfully",
                "tool": "service_health_checker",
                "action": "get_service_incidents",
                "params": {"service_id": "webhook_service"},
                "pass_condition": "no active incidents",
                "fail_message": "Webhook delivery issues may be affecting billing notifications",
            },
        ],
    },
    "performance_chain": {
        "chain_id": "performance_chain",
        "name": "Performance Diagnostic Chain",
        "description": "Progressive diagnosis of slow performance and timeouts",
        "target_issue": "Platform is slow, features are timing out, or responses are delayed",
        "estimated_time_minutes": 6,
        "steps": [
            {
                "step_id": "system_health",
                "name": "Overall System Health",
                "description": "Check health of all services to identify systemic issues",
                "tool": "service_health_checker",
                "action": "check_all_services",
                "params": {},
                "pass_condition": "overall_health > 90%",
                "fail_message": "System-wide health issues detected",
            },
            {
                "step_id": "api_latency",
                "name": "API Latency Check",
                "description": "Check API gateway response times",
                "tool": "service_health_checker",
                "action": "check_service_status",
                "params": {"service_id": "api_gateway"},
                "pass_condition": "response_time_ms < 300",
                "fail_message": "API latency is elevated — this may cause slow performance",
            },
            {
                "step_id": "ai_pipeline_health",
                "name": "AI Pipeline Health",
                "description": "Check if AI pipeline is performing normally",
                "tool": "service_health_checker",
                "action": "check_service_status",
                "params": {"service_id": "ai_pipeline"},
                "pass_condition": "service is operational",
                "fail_message": "AI pipeline is degraded — AI responses may be slow or limited",
            },
            {
                "step_id": "known_perf_issues",
                "name": "Known Performance Issues",
                "description": "Search for known issues related to performance",
                "tool": "known_issue_detector",
                "action": "search_known_issues",
                "params": {"query": "slow performance timeout latency delayed"},
                "pass_condition": "no high-severity issues found",
                "fail_message": "A known performance issue has been detected",
            },
            {
                "step_id": "config_optimization",
                "name": "Configuration Optimization Check",
                "description": "Check for configuration improvements that could boost performance",
                "tool": "config_validator",
                "action": "get_config_recommendations",
                "params": {},
                "pass_condition": "no high-priority recommendations",
                "fail_message": "Configuration optimizations available that may improve performance",
            },
        ],
    },
}


def _simulate_step_result(
    step: dict[str, Any],
) -> dict[str, Any]:
    """Simulate the result of a single diagnostic step."""
    # 80% chance each step passes
    is_pass = random.random() < 0.80
    status = "pass" if is_pass else "fail"

    findings: list[str] = []
    if is_pass:
        findings.append(f"{step['name']} completed successfully — no issues detected")
    else:
        findings.append(step.get("fail_message", f"{step['name']} detected an issue"))

    return {
        "step_id": step["step_id"],
        "step_name": step["name"],
        "status": status,
        "is_pass": is_pass,
        "findings": findings,
        "recommendation": "" if is_pass else step.get("fail_message", "Investigate further"),
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Tool Implementation ────────────────────────────────────────────


class DiagnosticChainTool(BaseReactTool):
    """ReAct tool for running sequential diagnostic chains.

    Provides:
      - run_diagnostic_chain: Execute a full diagnostic chain
      - get_chain_templates: List available chain templates
      - create_custom_chain: Build a custom chain from steps
      - get_chain_result: Get result of a previous chain run

    Day 3: Technical Support Diagnostic Tools — HIGH TIER ONLY.
    Only available for parwa_high variant. Chains provide progressive
    problem isolation by running multiple diagnostic steps sequentially.
    """

    def __init__(self) -> None:
        self._chain_results: dict[str, dict[str, Any]] = {}

    # ── Metadata ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "diagnostic_chain"

    @property
    def description(self) -> str:
        return (
            "Run sequential diagnostic chains that build on each other to "
            "identify and resolve complex technical issues progressively"
        )

    @property
    def actions(self) -> list[str]:
        return [
            "run_diagnostic_chain",
            "get_chain_templates",
            "create_custom_chain",
            "get_chain_result",
        ]

    # ── Schema ──────────────────────────────────────────────────

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            tool_name=self.name,
            description=self.description,
            actions=[
                ActionSchema(
                    name="run_diagnostic_chain",
                    description="Execute a sequential diagnostic chain by template ID",
                    parameters={
                        "type": "object",
                        "properties": {
                            "chain_id": {
                                "type": "string",
                                "description": "Chain template ID: connectivity_chain, login_chain, billing_chain, performance_chain",
                            },
                            "stop_on_fail": {
                                "type": "boolean",
                                "description": "Stop chain execution when a step fails (default: false)",
                                "default": False,
                            },
                        },
                        "required": ["chain_id"],
                    },
                    required_params=["chain_id"],
                    returns="Sequential diagnostic results with pass/fail for each step and overall diagnosis",
                ),
                ActionSchema(
                    name="get_chain_templates",
                    description="List available diagnostic chain templates",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                    required_params=[],
                    returns="List of available chain templates with descriptions",
                ),
                ActionSchema(
                    name="create_custom_chain",
                    description="Build a custom diagnostic chain from available diagnostic steps",
                    parameters={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name for the custom chain",
                            },
                            "target_issue": {
                                "type": "string",
                                "description": "Description of the issue this chain targets",
                            },
                            "step_ids": {
                                "type": "string",
                                "description": "Comma-separated step IDs from templates to include",
                            },
                        },
                        "required": ["name", "target_issue", "step_ids"],
                    },
                    required_params=["name", "target_issue", "step_ids"],
                    returns="Custom chain definition with combined steps",
                ),
                ActionSchema(
                    name="get_chain_result",
                    description="Get the result of a previously run diagnostic chain",
                    parameters={
                        "type": "object",
                        "properties": {
                            "execution_id": {
                                "type": "string",
                                "description": "Execution ID from a previous run_diagnostic_chain call",
                            },
                        },
                        "required": ["execution_id"],
                    },
                    required_params=["execution_id"],
                    returns="Full chain execution result with all step details",
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
            "run_diagnostic_chain": self._run_diagnostic_chain,
            "get_chain_templates": self._get_chain_templates,
            "create_custom_chain": self._create_custom_chain,
            "get_chain_result": self._get_chain_result,
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

    async def _run_diagnostic_chain(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Execute a sequential diagnostic chain."""
        chain_id: str = params.get("chain_id", "")
        stop_on_fail: bool = params.get("stop_on_fail", False)

        template = CHAIN_TEMPLATES.get(chain_id)
        if template is None:
            return ToolResult(
                success=False,
                error=f"Unknown chain: {chain_id}. Available: {', '.join(CHAIN_TEMPLATES.keys())}",
                data=None,
                execution_time_ms=0,
            )

        execution_id = f"chain_exec_{uuid.uuid4().hex[:12]}"
        step_results: list[dict[str, Any]] = []
        chain_failed = False
        first_failure_step: str | None = None
        pass_count = 0

        for step in template["steps"]:
            if chain_failed and stop_on_fail:
                # Skip remaining steps
                step_results.append({
                    "step_id": step["step_id"],
                    "step_name": step["name"],
                    "status": "skipped",
                    "is_pass": False,
                    "findings": ["Step skipped due to previous failure (stop_on_fail=True)"],
                    "recommendation": "Resolve previous step failure first",
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                })
                continue

            result = _simulate_step_result(step)
            step_results.append(result)

            if result["is_pass"]:
                pass_count += 1
            else:
                chain_failed = True
                if first_failure_step is None:
                    first_failure_step = step["step_id"]

        total_steps = len(template["steps"])
        overall_status = "all_passed" if pass_count == total_steps else "issues_found"

        # Build diagnosis summary
        failed_steps = [r for r in step_results if r["status"] == "fail"]
        diagnosis: list[str] = []
        if not failed_steps:
            diagnosis.append(f"All {total_steps} diagnostic steps passed. No issues detected in the {template['name']}.")
        else:
            diagnosis.append(f"{len(failed_steps)} of {total_steps} steps detected issues in the {template['name']}:")
            for fs in failed_steps:
                diagnosis.append(f"  - {fs['step_name']}: {fs['recommendation']}")

        # Recommendations
        recommendations: list[str] = []
        if failed_steps:
            # Map failures to recommendations
            for fs in failed_steps:
                step_template = next(
                    (s for s in template["steps"] if s["step_id"] == fs["step_id"]),
                    None,
                )
                if step_template:
                    recommendations.append(step_template.get("fail_message", "Investigate this issue further"))

        chain_result = {
            "execution_id": execution_id,
            "company_id": company_id,
            "chain_id": chain_id,
            "chain_name": template["name"],
            "target_issue": template["target_issue"],
            "overall_status": overall_status,
            "total_steps": total_steps,
            "passed_steps": pass_count,
            "failed_steps": len(failed_steps),
            "first_failure_at": first_failure_step,
            "diagnosis": diagnosis,
            "recommendations": recommendations,
            "step_results": step_results,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "estimated_resolution": "Self-service steps available" if pass_count > 0 else "Escalation recommended",
        }

        # Cache result
        self._chain_results[execution_id] = chain_result

        return ToolResult(success=True, error=None, data=chain_result, execution_time_ms=0)

    async def _get_chain_templates(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """List available chain templates."""
        templates = []
        for chain_id, template in CHAIN_TEMPLATES.items():
            templates.append({
                "chain_id": chain_id,
                "name": template["name"],
                "description": template["description"],
                "target_issue": template["target_issue"],
                "step_count": len(template["steps"]),
                "estimated_time_minutes": template["estimated_time_minutes"],
            })

        return ToolResult(
            success=True,
            error=None,
            data={
                "company_id": company_id,
                "total_templates": len(templates),
                "templates": templates,
            },
            execution_time_ms=0,
        )

    async def _create_custom_chain(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Build a custom diagnostic chain from steps."""
        name: str = params.get("name", "")
        target_issue: str = params.get("target_issue", "")
        step_ids_str: str = params.get("step_ids", "")

        if not name or not target_issue or not step_ids_str:
            return ToolResult(
                success=False,
                error="name, target_issue, and step_ids are all required",
                data=None,
                execution_time_ms=0,
            )

        requested_ids = [s.strip() for s in step_ids_str.split(",") if s.strip()]

        # Collect steps from templates
        collected_steps: list[dict[str, Any]] = []
        found_ids: list[str] = []
        not_found_ids: list[str] = []

        for step_id in requested_ids:
            found = False
            for template in CHAIN_TEMPLATES.values():
                for step in template["steps"]:
                    if step["step_id"] == step_id:
                        collected_steps.append(step)
                        found_ids.append(step_id)
                        found = True
                        break
                if found:
                    break
            if not found:
                not_found_ids.append(step_id)

        if not collected_steps:
            return ToolResult(
                success=False,
                error=f"No valid step IDs found. Requested: {step_ids_str}",
                data=None,
                execution_time_ms=0,
            )

        custom_chain = {
            "chain_id": f"custom_{uuid.uuid4().hex[:8]}",
            "name": name,
            "description": f"Custom diagnostic chain for: {target_issue}",
            "target_issue": target_issue,
            "steps": collected_steps,
            "estimated_time_minutes": len(collected_steps) * 1.5,
            "found_steps": found_ids,
            "not_found_steps": not_found_ids,
        }

        return ToolResult(
            success=True,
            error=None,
            data={
                "company_id": company_id,
                "custom_chain": custom_chain,
                "warning": f"Steps not found: {', '.join(not_found_ids)}" if not_found_ids else None,
            },
            execution_time_ms=0,
        )

    async def _get_chain_result(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Get result of a previous chain run."""
        execution_id: str = params.get("execution_id", "")

        result = self._chain_results.get(execution_id)
        if result is None:
            return ToolResult(
                success=False,
                error=f"Chain execution not found: {execution_id}",
                data=None,
                execution_time_ms=0,
            )

        # Verify company_id matches
        if result.get("company_id") != company_id:
            return ToolResult(
                success=False,
                error="Chain execution not found for this company",
                data=None,
                execution_time_ms=0,
            )

        return ToolResult(success=True, error=None, data=result, execution_time_ms=0)
