"""
LLM-Driven Action Executor — the "brain" that decides what API to call.

This replaces Node 5's hardcoded if/else with LLM-driven decisions.

Flow:
  1. Ticket needs an action (e.g., "refund $149 for ORD-9999")
  2. LLM sees: ticket + connected integrations + available endpoints
  3. LLM decides: "Call Stripe POST /v1/refunds {amount: 14900, payment_intent: pi_xxx}"
  4. Safety check: validate the call
  5. Generic executor runs it
  6. If multi-step needed → LLM chains: "Step 1: lookup in Shopify, Step 2: refund in Stripe"

This is the n8n-type behavior — but LLM-driven, not human-built.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.llm_action_executor")

MAX_STEPS = 5  # Safety: max API calls per ticket


async def execute_action_llm(
    tenant_id: str,
    action: str,
    details: Dict[str, Any],
    ticket_text: str,
    knowledge: str = "",
) -> Dict[str, Any]:
    """Let the LLM decide what API calls to make, then execute them.

    This replaces the hardcoded if/else in Node 5.

    Args:
        tenant_id: Tenant's company_id
        action: Detected action (e.g., "execute_refund", "cancel_order")
        details: Action details (amount, order_id, etc.)
        ticket_text: The original customer ticket
        knowledge: KB articles (for context)

    Returns:
        Dict with: success (bool), steps_executed (list), result (str), error (str)

    Example:
        result = await execute_action_llm(
            tenant_id="company_123",
            action="execute_refund",
            details={"amount": 149, "order_id": "ORD-9999"},
            ticket_text="I want a refund of $149 for order ORD-9999",
        )
        → LLM sees Stripe connected → decides to call POST /v1/refunds
        → Executor calls Stripe API → refund processed
        → Returns {"success": True, "result": "Refund of $149 processed via Stripe"}
    """
    from app.core.generic_api_executor import list_available_actions, execute_api_call

    # ── Step 1: Get available tools for this tenant ──
    available = await list_available_actions(tenant_id)

    if not available:
        return {
            "success": False,
            "error": "No integrations connected. Cannot execute actions.",
            "steps_executed": [],
            "result": "",
        }

    # Build a description of available tools for the LLM
    tools_description = ""
    for integ, info in available.items():
        tools_description += f"\n{integ} (connected):\n"
        for endpoint in info.get("actions", []):
            tools_description += f"  - {endpoint}\n"

    # ── Step 2: Ask LLM what to do ──
    prompt = f"""You are a customer support agent. You need to take an action for a customer.

Customer ticket: "{ticket_text}"

Action needed: {action}
Details: {json.dumps(details, indent=2)}

Knowledge base context: {knowledge[:1000]}

Available integrations and their API endpoints:
{tools_description}

Based on what's connected, decide what API call(s) to make to resolve this ticket.

If you need MULTIPLE steps (e.g., look up order in Shopify, then refund in Stripe),
list each step.

If NO connected integration can handle this action, respond with:
{{"action": "escalate", "reason": "No integration can handle {action}"}}

Otherwise, respond with JSON:
{{
  "steps": [
    {{
      "integration": "stripe",
      "method": "POST",
      "endpoint": "/v1/refunds",
      "body": {{"amount": 14900, "reason": "requested_by_customer"}},
      "purpose": "Process refund of $149"
    }}
  ],
  "expected_result": "Refund processed, customer notified"
}}

Rules:
- Use ONLY the integrations listed above
- Amounts for Stripe must be in CENTS (149 dollars = 14900)
- For Shopify, use API version 2024-01 in the path
- If you need data from one API to use in another, chain the steps
- Maximum {MAX_STEPS} steps
- If unsure, escalate (don't guess)

Respond with ONLY the JSON, no other text."""

    try:
        llm_response = await _call_llm(prompt)
        if not llm_response:
            return {
                "success": False,
                "error": "LLM did not respond. Cannot decide action.",
                "steps_executed": [],
                "result": "",
            }

        # ── Step 3: Parse LLM decision ──
        decision = _parse_llm_decision(llm_response)

        if decision.get("action") == "escalate":
            return {
                "success": False,
                "error": decision.get("reason", "Escalated by LLM"),
                "steps_executed": [],
                "result": "",
                "escalate": True,
            }

        steps = decision.get("steps", [])
        if not steps:
            return {
                "success": False,
                "error": "LLM did not provide any steps.",
                "steps_executed": [],
                "result": "",
            }

        # ── Step 4: Execute each step ──
        steps_executed = []
        last_result = None
        step_results = {}

        for i, step in enumerate(steps[:MAX_STEPS]):
            integration = step.get("integration", "")
            method = step.get("method", "GET")
            endpoint = step.get("endpoint", "")
            body = step.get("body", {})
            purpose = step.get("purpose", "")

            # ── Safety check before executing ──
            safety = _safety_check(integration, method, endpoint, body, action)
            if not safety["safe"]:
                steps_executed.append({
                    "step": i + 1,
                    "integration": integration,
                    "endpoint": endpoint,
                    "status": "blocked",
                    "reason": safety["reason"],
                })
                break

            # ── Substitute variables from previous steps ──
            # e.g., endpoint "/v1/refunds" → "/v1/refunds" (no change)
            # But body might reference {step1.id} → replace with actual value
            if last_result and last_result.get("data"):
                body = _substitute_variables(body, step_results)

            # ── Execute the API call ──
            result = await execute_api_call(
                tenant_id=tenant_id,
                integration_type=integration,
                method=method,
                endpoint=endpoint,
                body=body,
            )

            steps_executed.append({
                "step": i + 1,
                "integration": integration,
                "method": method,
                "endpoint": endpoint,
                "purpose": purpose,
                "status": "success" if result["success"] else "failed",
                "response_code": result.get("status_code", 0),
            })

            step_results[f"step{i+1}"] = result
            last_result = result

            # If a step fails, stop
            if not result["success"]:
                break

            # ── Ask LLM if more steps needed (dynamic chaining) ──
            if i < len(steps) - 1:
                # Continue to next step in the plan
                continue
            else:
                # Last step — check if LLM wants to do more based on result
                more = await _check_if_more_needed(
                    ticket_text, result, available, action
                )
                if more.get("needs_more"):
                    steps.extend(more.get("new_steps", [])[:MAX_STEPS - len(steps)])

        # ── Step 5: Summarize results ──
        success = all(s["status"] == "success" for s in steps_executed) if steps_executed else False

        summary = await _summarize_result(ticket_text, steps_executed, step_results)

        return {
            "success": success,
            "steps_executed": steps_executed,
            "result": summary,
            "error": None if success else steps_executed[-1].get("reason", "Action failed"),
        }

    except Exception as exc:
        logger.error("execute_action_llm error: %s", str(exc)[:300])
        return {
            "success": False,
            "error": str(exc)[:300],
            "steps_executed": [],
            "result": "",
        }


async def _call_llm(prompt: str) -> str:
    """Call the LLM (Groq llama-3.1-8b-instant preferred).

    User validation (2026-08-12): llama-3.1-8b is best for ALL pipeline tasks.
    Was NVIDIA GLM-5.2 but it took ~58s/call → action executor timed out.
    """
    # Try Groq first (fastest, user-validated best model)
    if os.environ.get("GROQ_API_KEY"):
        try:
            from app.core.parwa_pipeline.llm_client import _call_groq_direct
            result = await _call_groq_direct(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=800,
                call_id=0,
            )
            if result and len(result.strip()) > 10:
                return result
        except Exception as exc:
            logger.warning("Groq call failed for action executor: %s", str(exc)[:200])

    # Fallback: any other provider (Cerebras, Mistral, etc.)
    try:
        from app.core.parwa_pipeline.llm_client import llm_call
        result = await llm_call(prompt, max_tokens=800, temperature=0.1)
        return result or ""
    except Exception as exc:
        logger.error("LLM call failed: %s", str(exc)[:200])
        return ""


def _parse_llm_decision(response: str) -> Dict[str, Any]:
    """Parse the LLM's JSON response into a decision dict."""
    if not response:
        return {"action": "escalate", "reason": "Empty LLM response"}

    # Try to extract JSON from the response
    cleaned = response.strip()

    # Remove markdown code blocks
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    # Try direct JSON parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the response
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {"action": "escalate", "reason": f"Could not parse LLM response: {cleaned[:200]}"}


def _safety_check(
    integration: str,
    method: str,
    endpoint: str,
    body: Dict[str, Any],
    action: str,
) -> Dict[str, Any]:
    """Validate the API call before executing.

    Checks:
    - Integration is in the allowed list
    - Method is valid (GET, POST, PUT, DELETE, PATCH)
    - Endpoint doesn't contain suspicious patterns
    - Body doesn't contain dangerous values (negative amounts, etc.)

    Returns: {"safe": bool, "reason": str}
    """
    # Check integration
    allowed_integrations = ["stripe", "razorpay", "shopify", "twilio", "brevo", "custom", "custom_api"]
    if integration.lower() not in allowed_integrations:
        return {"safe": False, "reason": f"Unknown integration: {integration}"}

    # Check method
    allowed_methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    if method.upper() not in allowed_methods:
        return {"safe": False, "reason": f"Invalid method: {method}"}

    # Check endpoint for suspicious patterns
    suspicious = ["../", "..\\", "localhost", "127.0.0.1", "0.0.0.0", "file://", "<script"]
    endpoint_lower = endpoint.lower()
    for pattern in suspicious:
        if pattern in endpoint_lower:
            return {"safe": False, "reason": f"Suspicious pattern in endpoint: {pattern}"}

    # Check body for dangerous values
    if body:
        # Check for negative amounts (would charge customer instead of refund)
        amount = body.get("amount")
        if amount is not None and isinstance(amount, (int, float)) and amount < 0:
            return {"safe": False, "reason": f"Negative amount not allowed: {amount}"}

        # Check for extremely large amounts (safety cap)
        if amount is not None and isinstance(amount, (int, float)) and amount > 10000000:
            return {"safe": False, "reason": f"Amount too large: {amount}"}

    return {"safe": True, "reason": "passed"}


def _substitute_variables(body: Dict[str, Any], step_results: Dict[str, Any]) -> Dict[str, Any]:
    """Replace {step1.id} type variables with actual values from previous steps.

    Example:
      body = {"payment_intent": "{step1.data.id}"}
      step_results = {"step1": {"data": {"id": "pi_xxx"}}}
      → body becomes {"payment_intent": "pi_xxx"}
    """
    if not body:
        return body

    body_str = json.dumps(body)

    # Replace {stepN.data.field} patterns
    for step_key, step_result in step_results.items():
        if not step_result.get("data"):
            continue

        # Simple: {step1.data.id} → value
        for field, value in _flatten_dict(step_result["data"]).items():
            placeholder = f"{{{step_key}.data.{field}}}"
            if placeholder in body_str:
                body_str = body_str.replace(placeholder, str(value))

    try:
        return json.loads(body_str)
    except json.JSONDecodeError:
        return body


def _flatten_dict(d: Dict, parent: str = "", sep: str = ".") -> Dict[str, Any]:
    """Flatten a nested dict for variable substitution."""
    items = {}
    for k, v in d.items():
        new_key = f"{parent}{sep}{k}" if parent else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, new_key, sep))
        else:
            items[new_key] = v
    return items


async def _check_if_more_needed(
    ticket_text: str,
    last_result: Dict[str, Any],
    available: Dict[str, Any],
    action: str,
) -> Dict[str, Any]:
    """Check if the LLM wants to do more steps based on the last result."""
    # For now, just return no more steps needed
    # In the future, we can ask the LLM: "Based on this result, do you need to do anything else?"
    return {"needs_more": False, "new_steps": []}


async def _summarize_result(
    ticket_text: str,
    steps_executed: List[Dict[str, Any]],
    step_results: Dict[str, Any],
) -> str:
    """Generate a human-readable summary of what happened."""
    if not steps_executed:
        return "No actions were taken."

    summary_parts = []
    for step in steps_executed:
        status = step.get("status", "unknown")
        integration = step.get("integration", "?")
        endpoint = step.get("endpoint", "?")
        purpose = step.get("purpose", "")

        if status == "success":
            summary_parts.append(f"✅ {integration}: {purpose} ({endpoint})")
        else:
            summary_parts.append(f"❌ {integration}: {purpose} failed ({endpoint})")

    return " | ".join(summary_parts)
