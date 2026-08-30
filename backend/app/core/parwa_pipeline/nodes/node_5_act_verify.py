"""
Node 5: Act + Verify

Question: Did we DO the right thing?

Techniques (in order):
  1. IdempotencyCheck             (non-LLM) — prevent duplicate actions
  2. SmartRouter                  (non-LLM) — skip ReAct for simple actions
  3. NearDedup                    (non-LLM) — flag similar actions for same customer
  4. Rule-based action check      (non-LLM)
  5. GSD.decompose()              (non-LLM)
  6. MAKER.bridge()               (non-LLM)
  7. NumericalConsistencyCheck    (non-LLM) — verify amount against CRM
  8. ReAct.execute()              (LLM — for complex actions)
  9. SafetyNet                    (non-LLM) — scrub PII from observations
 10. Reverse Thinking.verify()    (LLM)
 11. ContradictionCheck           (non-LLM) — ReAct vs ReverseThinking
 12. ZeroShotValidator.flag()     (non-LLM)
 13. Escalation                   (non-LLM) — auto-escalate high risk
 14. SufficiencyCheck             (non-LLM) — did we solve the problem?
 15. MAKER.FinalCheck + StrictMode (non-LLM) — critical gaps → BLOCK
 16. PolicyCitationChecker        (non-LLM) — action cites policy
 17. MetaLearner                  (non-LLM) — adjust from past patterns
 18. ActionAuditTrail             (non-LLM) — structured compliance record
 19. UCB execute action           (via external_tool_bus)
 20. tier_permissions check       (non-LLM)

LLM calls: 1-2 (ReAct + Reverse Thinking, only for complex actions)
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.parwa_pipeline.llm_client import llm_call
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_5")

# Import execution limits from config
# (defined in node_2 but referenced here for action verification)
# NOTE: Must match node_2_smart_route.EXECUTION_LIMITS exactly.
# Mini was removed 2026-07-26 — only parwa + high remain.
_CAPABILITY_MATRIX = {
    "parwa": {"execute_refund": True, "execute_credit": True, "account_change": True},
    "high": {"execute_refund": True, "execute_credit": True, "account_change": True},
}
# Refund/credit limits removed — both variants can execute any amount.
# Approval queue (BC-009) still enforces human approval for dangerous actions.
_EXEC_LIMITS = {
    "parwa": {"max_refund": float("inf"), "max_credit": float("inf")},
    "high": {"max_refund": float("inf"), "max_credit": float("inf")},
}


# ── Agent-aware tool input extraction ─────────────────────────────
# When a ticket routes to a Builder-created agent that has a linked Superglue
# tool, we need to extract the right inputs (customerEmail, transactionId, etc.)
# from the ticket details. This is a lightweight regex-based extractor — no LLM
# needed. The agent's tool's inputSchema defines what fields are expected.
# If extraction fails, falls back to the LLM-selection path.


def _extract_tool_inputs(details: Dict, action: str, knowledge: str) -> Dict[str, Any]:
    """Extract common tool inputs from ticket details + knowledge text.

    Looks for: emails, transaction IDs, order numbers, amounts, customer names.
    Returns a dict suitable for Superglue execute_tool(input_data).
    """
    import re

    inputs: Dict[str, Any] = {}

    # Combine all available text to scan
    text = " ".join([
        str(details or {}),
        knowledge or "",
        action or "",
    ])

    # Email
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    if email_match:
        inputs["customerEmail"] = email_match.group(0).rstrip(".")

    # Transaction ID (txn_xxx, ch_xxx, pi_xxx for Stripe/Paddle)
    txn_match = re.search(r'\b(txn_|ch_|pi_|re_|sub_|ctm_)[A-Za-z0-9]{6,}', text)
    if txn_match:
        inputs["transactionId"] = txn_match.group(0)

    # Order number (#1234, ORD-1234, order 1234)
    order_match = re.search(r'(?:order|ord|#)\s*[-:]?\s*([A-Z0-9]{4,12})', text, re.IGNORECASE)
    if order_match:
        inputs["orderNumber"] = order_match.group(1)

    # Amount ($50, $99.99, 100 cents)
    amount_match = re.search(r'\$(\d+(?:\.\d+)?)', text)
    if amount_match:
        # Convert dollars to cents (Superglue tools expect cents)
        try:
            dollars = float(amount_match.group(1))
            inputs["amount"] = int(dollars * 100)
        except ValueError:
            pass

    # Customer name (heuristic: "my name is X" or "I'm X")
    name_match = re.search(r'(?:my name is|i am|i\'m)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)', text)
    if name_match:
        inputs["customerName"] = name_match.group(1)

    # Date (next Tuesday, tomorrow, 2024-01-15)
    date_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', text)
    if date_match:
        inputs["dateTime"] = date_match.group(1)

    return inputs


# ── Rule-based action check (non-LLM) ─────────────────────────────


def _rule_based_check(
    action: str, amount: float, tier: str
) -> Dict[str, Any]:
    """Check if action can be executed based on variant rules."""
    caps = _CAPABILITY_MATRIX.get(tier, _CAPABILITY_MATRIX["parwa"])
    limits = _EXEC_LIMITS.get(tier, _EXEC_LIMITS["parwa"])

    can_execute = True
    reason = ""

    if action == "execute_refund":
        if not caps["execute_refund"]:
            can_execute = False
            reason = f"Tier '{tier}' cannot execute refunds — recommend only"
        elif amount > limits["max_refund"]:
            can_execute = False
            reason = f"Amount ${amount} exceeds tier '{tier}' limit of ${limits['max_refund']}"

    elif action == "execute_credit":
        if not caps["execute_credit"]:
            can_execute = False
            reason = f"Tier '{tier}' cannot execute credits — recommend only"
        elif amount > limits["max_credit"]:
            can_execute = False
            reason = f"Amount ${amount} exceeds tier '{tier}' limit of ${limits['max_credit']}"

    elif action == "account_change":
        if not caps["account_change"]:
            can_execute = False
            reason = f"Tier '{tier}' cannot execute account changes — recommend only"

    elif action == "provide_info":
        can_execute = True
        reason = "Information provision — no execution needed"

    else:
        can_execute = True
        reason = f"Action '{action}' — no restrictions apply"

    return {"can_execute": can_execute, "reason": reason}


# ── GSD: Decompose multi-step actions (non-LLM) ──────────────────


def _gsd_decompose_action(action: str, details: Dict) -> List[str]:
    """Break multi-step actions into individual steps."""
    if action == "execute_refund":
        return [
            "Verify customer identity and purchase",
            "Calculate refund amount",
            "Check refund policy eligibility",
            "Process refund through payment system",
            "Generate confirmation",
        ]
    elif action == "execute_credit":
        return [
            "Verify customer account status",
            "Determine credit amount",
            "Apply credit to account",
            "Notify customer",
        ]
    elif action == "account_change":
        return [
            "Verify requested change",
            "Validate new value",
            "Apply change",
            "Confirm with customer",
        ]
    else:
        return [f"Provide information about: {action}"]


# ── MAKER: Bridge action knowledge gaps (non-LLM) ─────────────────


def _maker_bridge_action(action: str, knowledge: str, crm_data: Dict) -> str:
    """Bridge knowledge gaps during action execution."""
    # Connect knowledge to action steps
    action_keywords = action.replace("_", " ").split()
    knowledge_lower = knowledge.lower()

    relevant_lines = []
    for line in knowledge_lower.split("."):
        if any(kw in line for kw in action_keywords):
            relevant_lines.append(line.strip())

    return " ".join(relevant_lines) if relevant_lines else "No direct knowledge bridge found for this action"


# ── ReAct: Think-Act-Observe loop (LLM) ───────────────────────────


async def _execute_real_refund(
    tenant_id: str, details: Dict, crm_data: Dict,
) -> Dict[str, Any]:
    """Execute a REAL refund via Stripe API using the tenant's stored credentials.

    This calls the Stripe Refunds API to actually move money back to the
    customer's card. The tenant must have Stripe connected via the
    integration catalog (credentials stored in the integrations table).

    Returns:
        Dict with: success (bool), amount (float), refund_id (str), error (str)
    """
    import httpx
    from database.base import SessionLocal
    from app.services.integration_service import IntegrationService

    # Extract refund details from the action details or CRM data
    amount = details.get("amount", 0)
    payment_intent_id = details.get("payment_intent_id", "")
    order_id = details.get("order_id", "")
    charge_id = details.get("charge_id", "")

    # Try to find the payment_intent_id from CRM/ecommerce data
    if not payment_intent_id and crm_data:
        orders = crm_data.get("ecommerce_orders")
        if orders:
            if isinstance(orders, list) and len(orders) > 0:
                order = orders[0] if isinstance(orders[0], dict) else {}
                payment_intent_id = order.get("payment_intent_id", "") or order.get("transaction_id", "")
                if not amount:
                    amount = order.get("total_price", 0) or order.get("amount", 0)

    if not amount or float(amount) <= 0:
        return {"success": False, "amount": 0, "refund_id": "", "error": "No refund amount specified"}

    # Load the tenant's Stripe credentials
    db = SessionLocal()
    try:
        service = IntegrationService(db)
        creds = service.get_credential_config(tenant_id, "stripe")
        if not creds or not creds.get("api_key"):
            return {
                "success": False,
                "amount": amount,
                "refund_id": "",
                "error": "Stripe not connected — tenant has not provided Stripe API key",
            }

        stripe_key = creds["api_key"]

        # Call Stripe Refunds API
        # https://stripe.com/docs/api/refunds/create
        refund_payload = {
            "amount": int(float(amount) * 100),  # Stripe uses cents
            "reason": "requested_by_customer",
        }
        if payment_intent_id:
            refund_payload["payment_intent"] = payment_intent_id
        elif charge_id:
            refund_payload["charge"] = charge_id

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.stripe.com/v1/refunds",
                headers={
                    "Authorization": f"Bearer {stripe_key}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data=refund_payload,
            )

        if response.status_code == 200:
            refund_data = response.json()
            logger.info(
                "stripe_refund_executed tenant=%s amount=%s refund_id=%s",
                tenant_id, amount, refund_data.get("id", ""),
            )
            return {
                "success": True,
                "amount": amount,
                "refund_id": refund_data.get("id", ""),
                "status": refund_data.get("status", "pending"),
            }
        else:
            error_msg = response.json().get("error", {}).get("message", f"Stripe API returned {response.status_code}")
            logger.warning("stripe_refund_failed tenant=%s error=%s", tenant_id, error_msg[:200])
            return {
                "success": False,
                "amount": amount,
                "refund_id": "",
                "error": error_msg,
            }
    except Exception as exc:
        logger.warning("stripe_refund_exception tenant=%s error=%s", tenant_id, str(exc)[:200])
        return {
            "success": False,
            "amount": amount,
            "refund_id": "",
            "error": f"Refund execution error: {str(exc)[:150]}",
        }
    finally:
        db.close()


async def _react_execute(
    action: str, details: Dict, knowledge: str, crm_data: Dict,
    tenant_id: str = "", state: Dict = None, logs: list = None,
) -> Dict[str, Any]:
    """Think-Act-Observe loop for complex action execution.

    Previously this was a stub that returned "Action simulated successfully"
    without calling any real tool. Now it dispatches to the ReActToolRegistry
    which has 7 real tools (CRMTool→HubSpot, BillingTool, OrderTool→Shopify,
    TicketTool, ServiceHealthChecker, KnownIssueDetector, ConfigValidator).

    The LLM generates a THOUGHT about what tool to call, then we map common
    action keywords to tool actions and execute them. If no tool matches,
    we fall back to the LLM-generated thought + a honest "no_tool_executed"
    observation so the AI knows the action wasn't actually performed.
    """
    prompt = f"""You are executing a customer support action.

Action: {action}
Details: {details}
Knowledge: {knowledge[:1500]}
Customer Data: {str(crm_data)[:500]}

Think about what needs to happen:
THOUGHT:"""

    try:
        thought = await llm_call(prompt, max_tokens=200, temperature=0.2)
    except Exception as e:
        thought = f"Action execution failed: {e}"

    # ── PRIMARY: Superglue (handles ALL API connections) ──────────
    # Superglue is the universal integration layer. It handles:
    #   - Public APIs (Stripe, Razorpay, Shopify)
    #   - Private APIs (banking, medical, internal)
    #   - Custom APIs (user-defined)
    # PARWA's LLM decides which tool to call → Superglue executes it.
    observation = None
    tool_executed = None

    try:
        from app.core.superglue_client import is_configured as sg_configured

        if sg_configured():
            from app.core.superglue_client import get_available_tools_description, execute_tool
            from app.core.parwa_pipeline.llm_client import llm_call

            # ── NEW: Agent-aware tool routing ────────────────────────
            # If a Builder-created agent is handling this ticket AND it has
            # a linked Superglue tool, skip the LLM tool-selection step
            # entirely and call the agent's pre-assigned tool directly.
            # This is the fast path: 0 LLM calls, ~5-7s per ticket.
            # Use verified_agent_id from Node 2 (falls back to builder_agent_id from Node 1)
            routed_agent_id = state.get("verified_agent_id") or state.get("builder_agent_id")
            if routed_agent_id:
                try:
                    from database.base import SessionLocal
                    from database.models.variant_engine import AIAgentAssignment
                    _db = SessionLocal()
                    try:
                        _agent = _db.query(AIAgentAssignment).filter(
                            AIAgentAssignment.id == routed_agent_id,
                        ).first()
                        if _agent and _agent.superglue_tool_id and _agent.superglue_tool_status == "active":
                            # Tool exists and active — use it
                            # Initialize variables that might be used in approval gate
                            _tool_id = _agent.superglue_tool_id
                            _tool_input = _extract_tool_inputs(details, action, knowledge)
                            result = {"success": False, "error": "not executed"}
                            # ── APPROVAL GATE (eliminates the risky part) ──
                            # If this agent's tool does dangerous actions (refund, cancel),
                            # check if approval is required BEFORE executing.
                            # If approval needed → ticket moves to "Pending Approval" queue,
                            # tool execution is PAUSED until admin approves.
                            if _agent.approval_required:
                                _amount = _tool_input.get("amount", 0) if isinstance(_tool_input, dict) else 0
                                _threshold = _agent.approval_threshold_cents or 0
                                # threshold=0 means "always require approval" (e.g. cancel sub)
                                # threshold>0 means "require approval above this amount"
                                _needs_approval = (_threshold == 0) or (_amount > _threshold)
                                if _needs_approval:
                                    observation = (
                                        f"APPROVAL_REQUIRED: Agent '{_agent.agent_name}' wants to execute "
                                        f"tool '{_agent.superglue_tool_id}' with input={_tool_input}. "
                                        f"Approval threshold={_threshold} cents, requested amount={_amount} cents. "
                                        f"Ticket moved to Pending Approval queue."
                                    )
                                    tool_executed = f"pending_approval:agent:{routed_agent_id}:superglue:{_agent.superglue_tool_id}"
                                    logs.append(
                                        f"node5: approval gate triggered (agent={_agent.agent_name}, "
                                        f"amount={_amount}c, threshold={_threshold}c)"
                                    )
                                    # Mark state for Node 6 to route to Pending Approval queue
                                    state["pending_approval"] = True
                                    state["pending_approval_reason"] = (
                                        f"Agent '{_agent.agent_name}' wants to execute "
                                        f"{_agent.superglue_tool_id} (amount={_amount}c, threshold={_threshold}c)"
                                    )
                                    # SKIP execute_tool — ticket goes to approval queue instead
                                    import json as _json_approval
                                    state["pending_approval_tool_input"] = _json_approval.dumps(_tool_input) if isinstance(_tool_input, dict) else str(_tool_input)
                                    state["pending_approval_agent_id"] = routed_agent_id
                                    state["pending_approval_tool_id"] = _agent.superglue_tool_id
                                    # Break out of the try block — observation is set, tool_executed is set
                                    # The rest of Node 5 will route this to the approval queue
                                else:
                                    # Amount below threshold → execute immediately
                                    # ── IDEMPOTENCY: prevent double execution ──
                                    _ticket_id_5 = state.get("ticket_id", "")
                                    _idem_key = f"{_ticket_id_5}:{_tool_id}:{action}"
                                    result = await _execute_with_idempotency(
                                        _tool_id, _tool_input, _idem_key, _ticket_id_5, action, tenant_id
                                    )
                            else:
                                # No approval required → execute immediately (read-only tools, lookups, etc.)
                                # _tool_id and _tool_input already initialized above

                                # ── VERIFY TOOL EXISTS before calling (Gap #1 fix) ──
                                # If Superglue server was reset, the tool won't exist.
                                # Mark the agent's tool status as 'failed' + fall through to LLM.
                                from app.core.superglue_client import verify_tool_exists
                                _tool_ok = await verify_tool_exists(_tool_id, tenant_id=tenant_id)
                                if not _tool_ok:
                                    logger.warning(
                                        "node5: tool %s not found on Superglue — marking agent tool as failed, falling through to LLM",
                                        _tool_id[:50],
                                    )
                                    # Update agent's tool status to failed (so admin sees it)
                                    try:
                                        _agent.superglue_tool_status = "failed"
                                        _db.commit()
                                    except Exception:
                                        pass
                                    # Fall through to LLM-based tool selection
                                    observation = None
                                    tool_executed = None
                                else:
                                    result = await _execute_with_idempotency(
                                        _tool_id, _tool_input,
                                        f"{state.get('ticket_id','')}:{_tool_id}:{action}",
                                        state.get("ticket_id",""), action, tenant_id
                                    )

                            # If approval was required by agent config, observation is already set — skip result check
                            # If safety gate blocked or requires approval, handle specially
                            if not state.get("pending_approval"):
                                if result.get("guardrail_blocked"):
                                    observation = (
                                        f"ACTION BLOCKED by safety guardrails: {result.get('error', '')}. "
                                        f"Agent '{_agent.agent_name}' tool '{_tool_id}' not executed."
                                    )
                                    tool_executed = f"agent:{routed_agent_id}:superglue:{_tool_id} (guardrail_blocked)"
                                    logs.append(f"node5: safety gate blocked agent tool={_tool_id}: {result.get('error', '')[:100]}")
                                elif result.get("safety_approval_required"):
                                    import json as _json_sg
                                    state["pending_approval"] = True
                                    state["pending_approval_reason"] = f"Safety gate: {result.get('error', '')}. Agent={_agent.agent_name}, Tool={_tool_id}"
                                    state["pending_approval_tool_input"] = _json_sg.dumps(_tool_input) if isinstance(_tool_input, dict) else str(_tool_input)
                                    state["pending_approval_agent_id"] = routed_agent_id
                                    state["pending_approval_tool_id"] = _tool_id
                                    observation = f"APPROVAL_REQUIRED: Safety gate classified tool '{_tool_id}' as {result.get('safety_level', 'unknown')}. Ticket moved to Pending Approval queue."
                                    tool_executed = f"pending_approval:agent:{routed_agent_id}:superglue:{_tool_id}"
                                    logs.append(f"node5: safety gate triggered approval for agent tool={_tool_id} level={result.get('safety_level', '')}")
                                elif result.get("success"):
                                    observation = (
                                        f"ACTION EXECUTED via agent '{_agent.agent_name}' "
                                        f"Superglue tool '{_tool_id}': "
                                        f"{str(result.get('data', ''))[:300]}"
                                    )
                                    tool_executed = f"agent:{routed_agent_id}:superglue:{_tool_id}"
                                    logs.append(
                                        f"node5: agent-aware tool call succeeded "
                                        f"(tool={_tool_id}, steps={len(result.get('step_results', []))})"
                                    )
                                else:
                                    observation = (
                                        f"Agent tool '{_tool_id}' failed: "
                                        f"{result.get('error', 'unknown')}. Falling back to LLM selection."
                                    )
                                    tool_executed = None
                                    logs.append(f"node5: agent tool failed, falling back: {result.get('error', '')[:100]}")
                    finally:
                        _db.close()
                except Exception as agent_exc:
                    logger.warning("agent_tool_lookup_failed: %s", str(agent_exc)[:200])

            # ── Fallback: LLM picks from all available tools ────────
            if observation is None:
                # Step 1: Get available tools from Superglue
                tools_desc = await get_available_tools_description()

                # Step 2: Build context with connected database info
                connected_dbs = state.get("connected_databases", [])
                db_context = ""
                if connected_dbs:
                    db_lines = ["Connected databases:"]
                    for db_info in connected_dbs:
                        readonly = " (read-only)" if db_info.get("readonly", True) else ""
                        db_lines.append(f"  - {db_info['name']}: {db_info['db_type']}{readonly}")
                    db_context = "\n".join(db_lines) + "\n\n"

                # Step 3: Ask LLM which tool to call
                tool_prompt = f"""You are deciding which tool to call for a customer support action.

Action needed: {action}
Details: {details}
Ticket context: {knowledge[:500] if knowledge else str(details)}

{db_context}{tools_desc}

Based on the ticket and available tools, which tool should you call?
Respond with ONLY JSON:
{{"tool_id": "the-tool-id", "input": {{}}, "reasoning": "why"}}

If no tool matches, respond with:
{{"tool_id": "none", "reasoning": "no matching tool"}}"""

                llm_response = await llm_call(tool_prompt, max_tokens=300, temperature=0.1)

                # Parse LLM decision
                import json as _json
                import re as _re
                match = _re.search(r'\{.*\}', llm_response or "", _re.DOTALL)
                if match:
                    decision = _json.loads(match.group())
                    tool_id = decision.get("tool_id", "none")

                    if tool_id and tool_id != "none":
                        # Step 3: Run Action Safety Gate before execution
                        tool_input = decision.get("input", {})
                        variant_tier = state.get("variant_tier", "parwa")
                        safety_gate = _run_action_safety_gate(
                            tool_id, action, tool_input, tenant_id, variant_tier)

                        if safety_gate["blocked"]:
                            # Guardrail blocked — do not execute
                            observation = (
                                f"ACTION BLOCKED by safety guardrails: {safety_gate['reason']}. "
                                f"Tool '{tool_id}' not executed."
                            )
                            tool_executed = f"superglue:{tool_id} (guardrail_blocked)"
                            logs.append(f"node5: safety gate blocked tool={tool_id}: {safety_gate['reason'][:100]}")
                        elif safety_gate["needs_approval"]:
                            # Safety classifier says FINANCIAL/DESTRUCTIVE → approval queue
                            import json as _json_approval
                            state["pending_approval"] = True
                            state["pending_approval_reason"] = (
                                f"Safety gate: {safety_gate['reason']}. Tool={tool_id}"
                            )
                            state["pending_approval_tool_input"] = _json_approval.dumps(tool_input)
                            state["pending_approval_agent_id"] = None
                            state["pending_approval_tool_id"] = tool_id
                            observation = (
                                f"APPROVAL_REQUIRED: Safety gate classified tool '{tool_id}' as "
                                f"{safety_gate['safety_level']}. Reason: {safety_gate['reason']}. "
                                f"Ticket moved to Pending Approval queue."
                            )
                            tool_executed = f"pending_approval:superglue:{tool_id}"
                            logs.append(
                                f"node5: safety gate triggered approval for tool={tool_id} "
                                f"level={safety_gate['safety_level']}"
                            )
                        else:
                            # Step 4: Execute the tool via Superglue
                            result = await execute_tool(tool_id, tool_input)

                            if result.get("success"):
                                observation = f"ACTION EXECUTED via Superglue tool '{tool_id}': {str(result.get('data', ''))[:300]}"
                                tool_executed = f"superglue:{tool_id}"
                                logs.append(f"node5: safety gate passed (level={safety_gate['safety_level']}), tool executed")
                            else:
                                observation = f"Superglue tool '{tool_id}' failed: {result.get('error', 'unknown')}"
                                tool_executed = f"superglue:{tool_id} (failed)"
                else:
                    observation = f"No matching Superglue tool for action '{action}'. LLM said: {decision.get('reasoning', '')}"
                    tool_executed = None
            else:
                observation = "Could not parse LLM tool selection response."
                tool_executed = None
        else:
            observation = None  # Superglue not configured → fall through to LLM executor

    except ImportError:
        pass  # Superglue client not available → fall through
    except Exception as exc:
        logger.warning("superglue_executor failed: %s", str(exc)[:200])
        observation = f"Superglue error: {str(exc)[:100]}. Trying fallback."
        tool_executed = None

    # ── FALLBACK: LLM-Driven Action Executor (if Superglue not configured/failed) ──
    if observation is None:
      try:
        from app.core.llm_action_executor import execute_action_llm

        llm_action_result = await execute_action_llm(
            tenant_id=tenant_id,
            action=action,
            details=details,
            ticket_text=knowledge[:500] if knowledge else str(details),
            knowledge=knowledge[:1000] if knowledge else "",
        )

        if llm_action_result.get("success"):
            observation = (
                f"ACTION EXECUTED: {llm_action_result.get('result', 'Action completed')}. "
                f"Steps: {len(llm_action_result.get('steps_executed', []))}"
            )
            tool_executed = "llm_driven_executor"
        elif llm_action_result.get("escalate"):
            observation = (
                f"Could not execute action: {llm_action_result.get('error', 'unknown')}. "
                f"Escalating to human."
            )
            tool_executed = "llm_driven_executor (escalated)"
        else:
            # LLM executor failed — fall back to hardcoded tools
            observation = f"LLM executor: {llm_action_result.get('error', 'failed')}. Trying fallback tools."
            tool_executed = None

      except ImportError:
        pass
      except Exception as exc:
        logger.warning("llm_action_executor failed: %s", str(exc)[:200])
        observation = f"LLM executor error: {str(exc)[:100]}. Trying fallback."
        tool_executed = None

    # ── FALLBACK: Hardcoded ReActToolRegistry (if LLM executor failed) ──
    if observation is None:
      try:
        from app.core.react_tools import ReActToolRegistry
        registry = ReActToolRegistry()
        # initialize_defaults registers all 7 tools.
        try:
            import asyncio
            asyncio.get_event_loop()
            # If we're in an async context, can't call the async init —
            # use the sync variant.
            registry.register_tool_sync = registry.register_tool_sync  # noqa
        except RuntimeError:
            pass
        # Initialize synchronously (the tools' __init__ are sync).
        try:
            await registry.initialize_defaults()
        except Exception:
            # initialize_defaults might be async; fall back to manual sync registration.
            try:
                from app.core.react_tools.order_tool import OrderTool
                from app.core.react_tools.billing_tool import BillingTool
                from app.core.react_tools.crm_tool import CRMTool
                from app.core.react_tools.ticket_tool import TicketTool
                registry.register_tool_sync(OrderTool())
                registry.register_tool_sync(BillingTool())
                registry.register_tool_sync(CRMTool())
                registry.register_tool_sync(TicketTool())
            except Exception:
                pass

        action_lower = action.lower()
        details_str = str(details)

        # Map action → tool call based on keywords.
        if any(kw in action_lower for kw in ("customer", "contact", "crm", "lookup")):
            customer_id = details.get("customer_id", "") or details.get("id", "")
            if customer_id and tenant_id:
                result = await registry.execute("crm_integration", "get_customer", tenant_id, customer_id=customer_id)
                if result.success:
                    observation = f"Customer lookup succeeded: {str(result.data)[:300]}"
                    tool_executed = "crm_integration.get_customer"
                else:
                    observation = f"Customer lookup failed: {result.error}"
                    tool_executed = "crm_integration.get_customer (failed)"

        elif any(kw in action_lower for kw in ("order", "ecommerce", "shopify")):
            order_id = details.get("order_id", "") or details.get("id", "")
            if order_id and tenant_id:
                result = await registry.execute("order_management", "get_order", tenant_id, order_id=order_id)
                if result.success:
                    observation = f"Order lookup succeeded: {str(result.data)[:300]}"
                    tool_executed = "order_management.get_order"
                else:
                    observation = f"Order lookup failed: {result.error}"
                    tool_executed = "order_management.get_order (failed)"

        elif any(kw in action_lower for kw in ("billing", "invoice", "payment", "refund")):
            if tenant_id:
                # ── REAL STRIPE REFUND EXECUTION ──────────────────────
                # When the action is execute_refund AND the tenant has Stripe
                # connected, actually call the Stripe API to process the refund.
                # This updates the company's Stripe account (real money movement)
                # and Node 6.5 will push the result to their CRM.
                if action == "execute_refund":
                    refund_result = await _execute_real_refund(
                        tenant_id, details, crm_data,
                    )
                    if refund_result["success"]:
                        observation = (
                            f"REFUND EXECUTED via Stripe: ${refund_result['amount']} "
                            f"refund ID: {refund_result['refund_id']}. "
                            f"The customer's payment has been refunded."
                        )
                        tool_executed = "stripe.execute_refund"
                    else:
                        observation = (
                            f"Refund execution failed: {refund_result['error']}. "
                            f"Falling back to recommendation only."
                        )
                        tool_executed = "stripe.execute_refund (failed)"
                else:
                    # Non-refund billing action — use the billing tool (lookup)
                    result = await registry.execute("billing_system", "get_billing_summary", tenant_id)
                    if result.success:
                        observation = f"Billing lookup succeeded: {str(result.data)[:300]}"
                        tool_executed = "billing_system.get_billing_summary"
                    else:
                        observation = f"Billing lookup failed: {result.error}"
                        tool_executed = "billing_system.get_billing_summary (failed)"

        elif any(kw in action_lower for kw in ("ticket", "escalate", "resolve")):
            ticket_id = details.get("ticket_id", "") or details.get("id", "")
            if ticket_id and tenant_id:
                result = await registry.execute("ticket_system", "get_ticket", tenant_id, ticket_id=ticket_id)
                if result.success:
                    observation = f"Ticket lookup succeeded: {str(result.data)[:300]}"
                    tool_executed = "ticket_system.get_ticket"
                else:
                    observation = f"Ticket lookup failed: {result.error}"
                    tool_executed = "ticket_system.get_ticket (failed)"

      except Exception as exc:
        observation = f"Tool dispatch failed: {str(exc)[:200]}"
        tool_executed = None

    if observation is None:
        # No tool matched the action — honest observation so the AI knows.
        observation = f"No tool executed for action '{action}'. Thought: {thought[:200]}"
        tool_executed = None

    return {
        "action": action,
        "thought": thought,
        "observation": observation,
        "tool_executed": tool_executed,
        "status": "completed",
    }


# ── L4: RuleBasedAction Enhanced — time/frequency/category rules (non-LLM) ─


def _rule_based_check_enhanced(
    action: str, details: Dict, tier: str, dynamic_ctx: Dict,
) -> Dict[str, Any]:
    """Enhanced rule-based check beyond tier+amount.

    The basic _rule_based_check only validates tier permissions and
    amount limits. This enhanced check adds:
    - Time window violations (refund on 45-day-old order)
    - Frequency violations (3rd refund this week)
    - Category restrictions (digital downloads non-refundable)

    Returns can_execute + all reasons if blocked.
    """
    # Start with the basic check result
    basic = _rule_based_check(action, details.get("amount", 0), tier)

    # If basic check already blocks, no need to check further
    if not basic["can_execute"]:
        return basic

    # Check dynamic context blocks (time, frequency, category)
    blocks = dynamic_ctx.get("blocks", [])
    if blocks:
        return {
            "can_execute": False,
            "reason": f"Rule violation: {'; '.join(blocks)}",
            "blocks": blocks,
        }

    return {
        "can_execute": True,
        "reason": basic.get("reason", ""),
        "blocks": [],
    }


# ── Reverse Thinking: Verify by reversibility (LLM) ───────────────


async def _reverse_verify(action: str, result: Dict, knowledge: str) -> Dict[str, Any]:
    """If I reverse this action, do I get back to original state?"""
    prompt = f"""An action was taken:
Action: {action}
Result: {result.get('observation', 'unknown')}

Knowledge: {knowledge[:1000]}

Verify: Is this action correct and reversible? What could go wrong?
RESPOND:
VERIFIED: YES/NO
RISK: <low/medium/high>
DETAILS: <brief>"""

    try:
        text = await llm_call(prompt, max_tokens=150, temperature=0.2)
        verified = "VERIFIED: YES" in text.upper()
        risk = "medium"
        if "RISK: LOW" in text.upper():
            risk = "low"
        elif "RISK: HIGH" in text.upper():
            risk = "high"
        return {"verified": verified, "risk": risk, "analysis": text}
    except Exception:
        return {"verified": False, "risk": "medium", "analysis": "Verification failed"}


# ── ZeroShotValidator: Flag wrong actions (non-LLM) ────────────────


def _zero_shot_flag_action(action: str, details: Dict, knowledge: str) -> Dict[str, Any]:
    """Flag statistically unusual actions."""
    flags = []

    amount = details.get("amount", 0)
    if amount > 5000:
        flags.append(f"High-value action: ${amount}")
    if amount < 0:
        flags.append("Negative amount detected")

    # Check if action type matches knowledge
    action_in_kb = action.replace("_", " ") in knowledge.lower()
    if not action_in_kb and action != "provide_info":
        flags.append(f"Action type '{action}' not found in knowledge base")

    return {
        "flagged": len(flags) > 0,
        "flags": flags,
        "severity": "high" if amount > 5000 else "low",
    }


# ═══════════════════════════════════════════════════════════════════
# NEW NON-LLM TECHNIQUES — 14 surgical additions
# ═══════════════════════════════════════════════════════════════════


# ── L2: DynamicContext — enrich action with real-time data (non-LLM) ─


# Time-window rules: how many days since purchase before refund is blocked
_REFUND_TIME_WINDOWS = {
    "default": 30,       # 30 days default
    "digital": 15,       # digital products: 15 days
    "subscription": 7,   # subscription refunds: 7 days
}

# Frequency limits: max actions per customer per time period
_FREQUENCY_LIMITS = {
    "execute_refund": {"max_per_week": 3, "max_per_month": 8},
    "execute_credit": {"max_per_week": 2, "max_per_month": 5},
    "account_change": {"max_per_week": 5, "max_per_month": 20},
}

# Non-refundable categories
_NON_REFUNDABLE_CATEGORIES = {"digital_download", "gift_card", "final_sale"}


def _dynamic_context(
    action: str, details: Dict, crm_data: Dict, state: Dict,
) -> Dict[str, Any]:
    """Enrich action context with real-time data.

    Adds three things ReAct doesn't have:
    1. Today's date — for "within 30 days" policy checks
    2. Recent action frequency — "3rd refund this week" → block
    3. Order category — "digital download" → non-refundable

    Returns enriched context + any time/frequency/category blocks.
    """
    now = datetime.now(timezone.utc)
    context = {
        "current_date": now.isoformat(),
        "blocks": [],
        "warnings": [],
    }

    # 1. Time-window check: is this order too old for a refund?
    if action in ("execute_refund", "execute_credit"):
        order_date = None
        if isinstance(crm_data, dict):
            orders = crm_data.get("ecommerce_orders", [])
            if isinstance(orders, list) and len(orders) > 0:
                order = orders[0] if isinstance(orders[0], dict) else {}
                raw_date = order.get("created_at", "") or order.get("order_date", "")
                if raw_date:
                    try:
                        # Parse common date formats
                        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
                            try:
                                order_date = datetime.strptime(raw_date[:19], fmt).replace(tzinfo=timezone.utc)
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass

        if order_date:
            days_since_order = (now - order_date).days
            # Determine category for time window
            category = "default"
            if isinstance(crm_data, dict):
                orders = crm_data.get("ecommerce_orders", [])
                if isinstance(orders, list) and len(orders) > 0:
                    order = orders[0] if isinstance(orders[0], dict) else {}
                    product_type = str(order.get("product_type", "")).lower()
                    if "digital" in product_type or "download" in product_type:
                        category = "digital"
                    elif "subscription" in product_type or "recurring" in product_type:
                        category = "subscription"

            window = _REFUND_TIME_WINDOWS.get(category, _REFUND_TIME_WINDOWS["default"])
            if days_since_order > window:
                context["blocks"].append(
                    f"Order {days_since_order}d old — exceeds {category} refund window of {window}d"
                )
            else:
                context["warnings"].append(
                    f"Order {days_since_order}d old (within {window}d {category} window)"
                )

    # 2. Frequency check: too many actions for this customer recently?
    freq_limits = _FREQUENCY_LIMITS.get(action)
    if freq_limits:
        recent_actions = state.get("recent_customer_actions", [])
        if isinstance(recent_actions, list):
            this_week = 0
            this_month = 0
            for ra in recent_actions:
                if not isinstance(ra, dict) or ra.get("action") != action:
                    continue
                ra_time = ra.get("timestamp", 0)
                if ra_time:
                    try:
                        ra_dt = datetime.fromtimestamp(ra_time, tz=timezone.utc)
                        if (now - ra_dt).days <= 7:
                            this_week += 1
                        if (now - ra_dt).days <= 30:
                            this_month += 1
                    except Exception:
                        pass

            if this_week >= freq_limits["max_per_week"]:
                context["blocks"].append(
                    f"{this_week} {action} actions this week (limit: {freq_limits['max_per_week']})"
                )
            elif this_month >= freq_limits["max_per_month"]:
                context["blocks"].append(
                    f"{this_month} {action} actions this month (limit: {freq_limits['max_per_month']})"
                )
            else:
                context["warnings"].append(
                    f"{action} frequency: {this_week}/wk {this_month}/mo"
                )

    # 3. Category check: non-refundable product types
    if action == "execute_refund":
        if isinstance(crm_data, dict):
            orders = crm_data.get("ecommerce_orders", [])
            if isinstance(orders, list) and len(orders) > 0:
                order = orders[0] if isinstance(orders[0], dict) else {}
                product_category = str(order.get("product_category", "")).lower()
                if product_category in _NON_REFUNDABLE_CATEGORIES:
                    context["blocks"].append(
                        f"Product category '{product_category}' is non-refundable"
                    )

    context["blocked"] = len(context["blocks"]) > 0
    return context


# ── L1: IdempotencyCheck — prevent duplicate actions (non-LLM) ────


def _idempotency_check(action: str, ticket_id: str, state: Dict) -> Dict[str, Any]:
    """Check if this exact action was already executed for this ticket.

    Prevents double-refund, double-credit on pipeline retries or
    duplicate tickets. Checks both current-run actions_taken and
    prior-run technique_log entries.
    """
    # Check current run's actions_taken
    actions_taken = state.get("actions_taken", [])
    for prev in actions_taken:
        if isinstance(prev, dict) and prev.get("action") == action:
            return {
                "already_done": True,
                "previous_status": prev.get("status", "unknown"),
            }

    # Check prior Node 5 runs (retry scenario — technique_log may have ReAct entries)
    prior_log = state.get("technique_log", [])
    if isinstance(prior_log, list):
        for entry in prior_log:
            if isinstance(entry, dict) and entry.get("node") == 5 and entry.get("technique") == "ReAct":
                if action in entry.get("result_summary", ""):
                    return {"already_done": True, "previous_status": "prior_run"}

    return {"already_done": False}


# ── L1: SmartRouter — skip ReAct for simple actions (non-LLM) ─────


def _smart_route(action: str, details: Dict) -> Dict[str, Any]:
    """Route simple actions past ReAct to save 1-2 LLM calls.

    About 40% of Node 5 tickets are provide_info or zero-amount
    actions that don't need the ReAct think-act-observe loop.
    """
    simple_actions = {"provide_info", "faq_response", "acknowledge"}
    if action in simple_actions:
        return {"skip_react": True, "reason": f"Action '{action}' is info-only — no execution needed"}

    # Zero amount = no money movement = no need for ReAct
    amount = details.get("amount", 0)
    if not amount or float(amount) == 0:
        if action in ("execute_refund", "execute_credit"):
            return {"skip_react": True, "reason": "Zero amount — no execution needed"}

    return {"skip_react": False, "reason": ""}


# ── L1: NearDedup — flag similar actions for same customer (non-LLM)


def _near_dedup(action: str, details: Dict, crm_data: Dict, state: Dict) -> Dict[str, Any]:
    """Check if a similar action was recently executed for same customer+order.

    Catches cross-ticket double execution: same customer, same order,
    different ticket number. Does NOT block — only flags for review.
    """
    customer_id = details.get("customer_id", "") or (crm_data.get("customer_id", "") if isinstance(crm_data, dict) else "")
    order_id = details.get("order_id", "") or (crm_data.get("order_id", "") if isinstance(crm_data, dict) else "")

    if not customer_id and not order_id:
        return {"duplicate_suspect": False, "reason": "No customer/order ID to compare"}

    recent_actions = state.get("recent_customer_actions", [])
    if not isinstance(recent_actions, list):
        return {"duplicate_suspect": False, "reason": "No recent action history"}

    for ra in recent_actions:
        if not isinstance(ra, dict):
            continue
        if ra.get("action") == action:
            if ra.get("customer_id") == customer_id or ra.get("order_id") == order_id:
                return {
                    "duplicate_suspect": True,
                    "reason": f"Same {action} for customer={customer_id} order={order_id}",
                }

    return {"duplicate_suspect": False}


# ── L2: NumericalConsistencyCheck — verify amounts vs CRM (non-LLM)


def _numerical_consistency_check(action: str, details: Dict, crm_data: Dict) -> Dict[str, Any]:
    """Cross-check action amount against CRM order data.

    Prevents wrong-amount refunds: if the action says refund $500 but
    the CRM order shows $200, something is wrong. Blocks the action
    before it reaches Stripe.
    """
    amount = float(details.get("amount", 0))
    if amount == 0 or action not in ("execute_refund", "execute_credit"):
        return {"consistent": True, "reason": "No amount to verify or non-monetary action"}

    # Try to find order amount from CRM
    crm_amount = None
    if isinstance(crm_data, dict):
        orders = crm_data.get("ecommerce_orders", [])
        if isinstance(orders, list) and len(orders) > 0:
            order = orders[0] if isinstance(orders[0], dict) else {}
            raw_amount = order.get("total_price", 0) or order.get("amount", 0)
            if raw_amount:
                crm_amount = float(raw_amount)

    if crm_amount is None or crm_amount == 0:
        return {"consistent": True, "reason": "No CRM amount to compare against"}

    # Refund amount should not exceed order amount
    if action == "execute_refund" and amount > crm_amount:
        return {
            "consistent": False,
            "reason": f"Refund ${amount} exceeds order total ${crm_amount}",
        }

    # Credit amount should not exceed 2x order amount (generous buffer)
    if action == "execute_credit" and amount > crm_amount * 2:
        return {
            "consistent": False,
            "reason": f"Credit ${amount} is >2x order total ${crm_amount}",
        }

    return {"consistent": True, "reason": f"Amount ${amount} within expected range of ${crm_amount}"}


# ── L2: SafetyNet — scrub PII from observations (non-LLM) ────────


_PII_PATTERNS = [
    re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b'),                           # email
    re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),                          # phone (US-like)
    re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),            # card number (16 digits)
    re.compile(r'\b(?:SSN|social)\s*[:=]?\s*\d{3}-?\d{2}-?\d{4}\b', re.I), # SSN
    re.compile(r'\b\d{16,19}\b'),                                           # long numeric IDs
]


def _safety_net_scrub(text: str) -> Dict[str, Any]:
    """Scrub PII from text (observations, logs, verification output).

    Catches email addresses, phone numbers, card numbers, SSNs, and
    long numeric identifiers that could be payment cards. Replaces
    each match with [REDACTED] to preserve readability.
    """
    if not text:
        return {"scrubbed": text, "pii_found": False, "count": 0}

    scrubbed = text
    count = 0
    for pattern in _PII_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            count += len(matches)
            scrubbed = pattern.sub("[REDACTED]", scrubbed)

    return {"scrubbed": scrubbed, "pii_found": count > 0, "count": count}


# ── L3: ContradictionCheck — ReAct vs ReverseThinking (non-LLM) ──


def _contradiction_check(react_result: Dict, reverse_result: Dict) -> Dict[str, Any]:
    """Check if execution result contradicts verification result.

    Catches: ReAct says 'completed' but Reverse says 'high risk' or
    'not verified'. These disagreements mean the action needs human
    review before shipping.
    """
    contradictions = []

    if not react_result or not reverse_result:
        return {"has_contradiction": False, "contradictions": []}

    # ReAct succeeded but Reverse says not verified
    if react_result.get("status") == "completed" and not reverse_result.get("verified"):
        contradictions.append("Action completed but verification failed")

    # ReAct failed but Reverse says verified (suspicious)
    if react_result.get("status") not in ("completed", "recommended") and reverse_result.get("verified"):
        contradictions.append("Action failed but verification passed — suspicious")

    # ReAct success but Reverse says high risk
    if react_result.get("status") == "completed" and reverse_result.get("risk") == "high":
        contradictions.append("Action completed but high risk flagged")

    return {"has_contradiction": len(contradictions) > 0, "contradictions": contradictions}


# ── L3: Escalation — auto-escalate high risk (non-LLM) ────────────


def _should_escalate(
    action: str, reverse_result: Dict, zsv_result: Dict,
    contradiction: Dict, tier: str,
) -> Dict[str, Any]:
    """Determine if this action should be escalated to human review.

    Checks multiple signals: reverse verification risk, ZSV flags,
    contradictions, and tier-specific rules. Returns escalate=True
    with all reasons so the human knows WHY.
    """
    reasons = []

    if not reverse_result:
        pass  # No reverse result (skipped action)
    else:
        if reverse_result.get("risk") == "high":
            reasons.append("Reverse verification: HIGH risk")
        if reverse_result.get("verified") is False:
            reasons.append("Reverse verification: NOT verified")

    if zsv_result.get("flagged") and zsv_result.get("severity") == "high":
        reasons.append(f"ZeroShotValidator high-severity: {zsv_result.get('flags', [])}")

    if contradiction.get("has_contradiction"):
        reasons.append(f"Contradiction: {contradiction.get('contradictions', [])}")

    # Growth tier: always flag refunds >$400 (close to $500 cap)
    if tier == "parwa" and action in ("execute_refund", "execute_credit"):
        for flag in zsv_result.get("flags", []):
            if "High-value" in str(flag):
                reasons.append("High-value action on Growth tier — near limit")

    return {"escalate": len(reasons) > 0, "reasons": reasons}


# ── L4: SufficiencyCheck — did we solve the problem? (non-LLM) ────


def _sufficiency_check(
    action: str, actions_taken: List[Dict], original_query: str,
) -> Dict[str, Any]:
    """Check if the actions taken actually address the original problem.

    Catches: action 'succeeded' but solved the WRONG problem, or
    execution completed but no actual result was produced.
    """
    if not actions_taken:
        return {"sufficient": False, "reason": "No actions were taken"}

    # Map action types to expected outcome signals
    expected_outcomes = {
        "execute_refund": ["refund", "money back", "credited", "reimburse"],
        "execute_credit": ["credit", "applied", "adjusted", "compensation"],
        "account_change": ["updated", "changed", "modified", "confirmed"],
        "provide_info": ["information", "provided", "answered", "explained"],
    }

    expected = expected_outcomes.get(action, [])

    if not expected:
        # No expected pattern — trust the status
        any_completed = any(a.get("status") == "completed" for a in actions_taken if isinstance(a, dict))
        return {
            "sufficient": any_completed,
            "reason": "No expected outcome pattern — using completion status",
        }

    # Check if any action result contains expected outcome signals
    all_observations = " ".join(
        (a.get("observation", "") + " " + a.get("thought", ""))
        for a in actions_taken if isinstance(a, dict)
    ).lower()

    matched = [e for e in expected if e in all_observations]

    if matched:
        return {"sufficient": True, "reason": f"Expected outcomes found: {matched}"}

    # Even without keyword match, completed status = sufficient
    any_completed = any(a.get("status") == "completed" for a in actions_taken if isinstance(a, dict))
    if any_completed:
        return {"sufficient": True, "reason": "Action completed (status=completed)"}

    return {"sufficient": False, "reason": f"Expected {expected} but no match in results"}


# ── L4: MAKER FinalCheck + StrictMode (non-LLM) ──────────────────


def _maker_final_check(
    action: str, knowledge: str, bridge_result: str,
    execution_ok: bool, verification_ok: bool,
) -> Dict[str, Any]:
    """Final safety gate: any critical gap → BLOCK the action.

    StrictMode: 2+ critical gaps = hard block (no override possible).
    Single gap = soft block (human override allowed).
    This is the last check before the action result ships downstream.
    """
    critical_gaps = []

    # No knowledge at all for this action
    if not knowledge.strip():
        critical_gaps.append("No knowledge base content available")

    # Bridge found nothing relevant
    if "No direct knowledge bridge" in bridge_result:
        critical_gaps.append("MAKER bridge: no relevant knowledge found")

    # Execution failed
    if not execution_ok:
        critical_gaps.append("Action execution did not succeed")

    # Verification failed
    if not verification_ok:
        critical_gaps.append("Action verification did not pass")

    should_block = len(critical_gaps) > 0
    strict_mode = len(critical_gaps) >= 2  # 2+ gaps = strict block

    return {
        "should_block": should_block,
        "strict_mode": strict_mode,
        "critical_gaps": critical_gaps,
    }


# ── L4: PolicyCitationChecker — action cites policy (non-LLM) ─────


_POLICY_KEYWORDS = {
    "execute_refund": ["refund policy", "return policy", "cancellation policy", "money-back", "30-day", "refund eligibility"],
    "execute_credit": ["credit policy", "compensation policy", "adjustment policy", "goodwill"],
    "account_change": ["account policy", "terms of service", "account management", "privacy policy"],
}


def _policy_citation_check(action: str, knowledge: str, observation: str) -> Dict[str, Any]:
    """Check if the action result references a specific policy from KB.

    Legal protection: if a refund is processed without citing the
    company's refund policy, it's a compliance gap. This check
    ensures every financial action has a policy anchor.
    """
    policies = _POLICY_KEYWORDS.get(action, [])
    if not policies:
        return {"cited": True, "reason": "No policy requirement for this action type"}

    combined = (knowledge + " " + observation).lower()
    found = [p for p in policies if p in combined]

    if found:
        return {"cited": True, "reason": f"Policy referenced: {found}"}

    return {"cited": False, "reason": f"No policy citation found. Expected one of: {policies}"}


# ── L4: ActionAuditTrail — structured compliance record (non-LLM) ─


def _build_audit_trail(
    action: str, details: Dict, tier: str,
    rule_check: Dict, react_result: Dict, reverse_result: Dict,
    zsv_result: Dict, escalation: Dict, final_verified: bool,
) -> Dict[str, Any]:
    """Build structured audit record for compliance and debugging.

    Every financial action should have a complete audit trail:
    what was attempted, what succeeded, what failed, who approved it.
    This record is stored in technique_log for downstream nodes.
    """
    return {
        "action": action,
        "amount": details.get("amount", 0),
        "tier": tier,
        "rule_check_passed": rule_check.get("can_execute", False),
        "execution_status": react_result.get("status", "not_executed") if react_result else "not_executed",
        "tool_executed": react_result.get("tool_executed") if react_result else None,
        "verification_passed": reverse_result.get("verified", False) if reverse_result else None,
        "verification_risk": reverse_result.get("risk", "unknown") if reverse_result else None,
        "zsv_flagged": zsv_result.get("flagged", False),
        "escalated": escalation.get("escalate", False),
        "final_verified": final_verified,
        "timestamp": time.time(),
    }


# ── L4: MetaLearner — adjust confidence from past patterns (non-LLM)


def _meta_learner_adjust(action: str, tier: str, state: Dict) -> Dict[str, Any]:
    """Adjust confidence based on past action success rates.

    If refunds for this tenant have failed 60% of the time, reduce
    confidence. If they succeed 95% of the time, boost it. Uses
    technique_log history — no extra LLM call.
    """
    past_log = state.get("technique_log", [])
    if not isinstance(past_log, list):
        return {"confidence_adjustment": 0.0, "reason": "No past log data"}

    action_type_count = 0
    action_success_count = 0

    for entry in past_log:
        if not isinstance(entry, dict):
            continue
        if entry.get("technique") == "ReAct" and action in entry.get("result_summary", ""):
            action_type_count += 1
            if "status=completed" in entry.get("result_summary", ""):
                action_success_count += 1

    if action_type_count == 0:
        return {"confidence_adjustment": 0.0, "reason": "No past data for this action"}

    success_rate = action_success_count / action_type_count

    # Adjust confidence: past success < 50% → reduce, > 80% → boost
    adjustment = 0.0
    if success_rate < 0.5:
        adjustment = -0.2
    elif success_rate > 0.8:
        adjustment = 0.1

    return {
        "confidence_adjustment": adjustment,
        "success_rate": round(success_rate, 2),
        "sample_size": action_type_count,
        "reason": f"Past success rate {success_rate:.0%} ({action_success_count}/{action_type_count})",
    }


# ── Main Node Function ────────────────────────────────────────────


async def node_5_act_verify(state: PipelineV2State) -> dict:
    """Node 5: Act + Verify — Did we DO the right thing?"""
    start = time.time()
    action = state.get("required_action", "provide_info")
    details = state.get("action_details", {})
    tier = state.get("variant_tier", "parwa")
    tenant_id = state.get("tenant_id", "")
    knowledge_docs = state.get("knowledge_context", [])
    crm_data = state.get("crm_data", {})
    logs = []
    llm_calls = 0

    # Short-circuit: when action=escalate_human (no agent claims the capability),
    # PAUSE the pipeline and ask for guidance instead of just giving up.
    # The human or a higher-tier variant can provide guidance on how to handle
    # this ticket type, and the pipeline will resume with that guidance.
    if action == "escalate_human":
        from langgraph.types import interrupt

        # ── Customer-facing message (shown to the customer in their ticket thread) ──
        # This replaces the old internal-vocabulary message that leaked
        # "No AI agent claims the capability" and "push it back to the CRM"
        # to customers. The customer sees a friendly escalation notice;
        # the human agent sees the full internal question separately.
        customer_message = (
            "Thank you for reaching out. I've reviewed your request, and to ensure "
            "you receive the most accurate and helpful response, I'm escalating your "
            "ticket to a human specialist who will follow up with you shortly. "
            "Your ticket is now in our priority queue and a team member will contact "
            "you soon. Thank you for your patience."
        )

        # ── Internal question (for the human agent / dashboard only) ──
        internal_question = (
            f"No AI agent claims the capability needed for this ticket "
            f"(action={action}, ticket_type={state.get('ticket_type', '?')}, "
            f"capability={details.get('capability', '?')}). "
            f"The customer has been told their ticket is escalated. "
            f"Please provide guidance on how to handle this ticket type, "
            f"or confirm it should be pushed back to the CRM as unresolved."
        )

        guidance = interrupt({
            "node": 5,
            "question": internal_question,  # Internal — for human agent
            "customer_message": customer_message,  # Customer-facing
            "ticket_id": state.get("ticket_id", ""),
            "action": action,
            "action_details": details,
        })
        # ── When resumed, execution continues HERE ─────────────────
        # If guidance was provided, inject it and continue the pipeline.
        # If the guidance says "push to CRM", we'll set force_human_handoff.
        logger.info(
            "Node 5 resumed with guidance: %s (ticket=%s)",
            str(guidance)[:100], state.get("ticket_id", ""),
        )
        elapsed = int((time.time() - start) * 1000)
        # Check if guidance indicates CRM push-back (couldn't solve)
        guidance_lower = str(guidance).lower()
        if "crm" in guidance_lower or "can't solve" in guidance_lower or "cannot solve" in guidance_lower or "push back" in guidance_lower:
            # Human says: push to CRM, can't solve
            return {
                "actions_taken": [],
                "actions_verified": False,
                "verification_result": {
                    "verified": False,
                    "risk": "high",
                    "analysis": f"Guidance: push to CRM. Reason: {str(guidance)[:200]}",
                },
                "technique_log": [{
                    "node": 5, "technique": "GuidanceCRM pushback",
                    "duration_ms": elapsed,
                    "result_summary": "guidance=push_to_crm",
                }],
                "node_5_token_usage": 0,
                "total_token_usage": state.get("total_token_usage", 0),
                "force_human_handoff": True,
                "push_to_crm": True,
                "crm_reason": str(guidance)[:500],
            }
        # Guidance provided — inject it and continue normally
        knowledge_docs = knowledge_docs + [{"content": f"Guidance: {guidance}", "source": "human_guidance"}]
        logs.append({
            "node": 5, "technique": "GuidanceInjection",
            "duration_ms": elapsed,
            "result_summary": f"guidance injected ({len(str(guidance))} chars) → continuing",
        })

    knowledge_str = "\n".join(d.get("content", "") for d in knowledge_docs)

    # ══════════════════════════════════════════════════════════════
    # L1: PRE-CHECK GUARDS
    # ══════════════════════════════════════════════════════════════

    # L1-1. IdempotencyCheck: skip if action already done
    idempotency = _idempotency_check(action, state.get("ticket_id", ""), state)
    logs.append({
        "node": 5, "technique": "IdempotencyCheck", "duration_ms": 0,
        "result_summary": f"already_done={idempotency['already_done']}",
    })
    if idempotency["already_done"]:
        elapsed = int((time.time() - start) * 1000)
        logger.info(
            "Node 5 idempotency skip: ticket=%s action=%s [%dms]",
            state.get("ticket_id", ""), action, elapsed,
        )
        return {
            "actions_taken": state.get("actions_taken", []),
            "actions_verified": True,
            "verification_result": f"Action '{action}' already executed — skipping duplicate",
            "technique_log": logs,
            "node_5_token_usage": 0,
            "total_token_usage": state.get("total_token_usage", 0),
        }

    # L1-2. SmartRouter: skip ReAct for simple actions
    smart_route = _smart_route(action, details)
    logs.append({
        "node": 5, "technique": "SmartRouter", "duration_ms": 0,
        "result_summary": f"skip_react={smart_route['skip_react']} reason={smart_route.get('reason', '')}",
    })

    # L1-3. NearDedup: flag similar actions for same customer
    near_dedup = _near_dedup(action, details, crm_data, state)
    logs.append({
        "node": 5, "technique": "NearDedup", "duration_ms": 0,
        "result_summary": f"duplicate_suspect={near_dedup['duplicate_suspect']}",
    })

    # L1-4. DynamicContext: enrich with real-time data (date, frequency, category)
    dynamic_ctx = _dynamic_context(action, details, crm_data, state)
    logs.append({
        "node": 5, "technique": "DynamicContext", "duration_ms": 0,
        "result_summary": f"blocked={dynamic_ctx['blocked']} blocks={len(dynamic_ctx.get('blocks', []))} warnings={len(dynamic_ctx.get('warnings', []))}",
    })

    # L1-5. Rule-based action check (enhanced with time/frequency/category)
    rule_check = _rule_based_check_enhanced(action, details, tier, dynamic_ctx)
    logs.append({"node": 5, "technique": "RuleBasedAction", "duration_ms": 0, "result_summary": f"execute={rule_check['can_execute']}"})

    # L1-6. GSD: decompose multi-step actions
    steps = _gsd_decompose_action(action, details)
    logs.append({"node": 5, "technique": "GSD", "duration_ms": 0, "result_summary": f"{len(steps)} steps"})

    # L1-7. MAKER: bridge action knowledge gaps
    bridge = _maker_bridge_action(action, knowledge_str, crm_data)
    logs.append({"node": 5, "technique": "MAKER", "duration_ms": 0, "result_summary": "bridge_done"})

    # ══════════════════════════════════════════════════════════════
    # L2: EXECUTE (with pre-flight checks)
    # ══════════════════════════════════════════════════════════════

    actions_taken = []
    react_result = None
    reverse_result = None

    if smart_route["skip_react"]:
        # SmartRouter says skip ReAct — simple action, no execution needed
        actions_taken.append({
            "action": action,
            "thought": f"SmartRouter: {smart_route['reason']}",
            "observation": "Skipped ReAct — simple action, no execution needed",
            "status": "completed",
        })
        verified = True
        verification_result = f"SmartRouter: {smart_route['reason']}"

    elif near_dedup["duplicate_suspect"]:
        # NearDedup flagged — don't execute, note for review
        actions_taken.append({
            "action": action,
            "thought": f"NearDedup: {near_dedup['reason']}",
            "observation": "Similar action already executed for this customer — flagged for review",
            "status": "flagged",
        })
        verified = True
        verification_result = f"NearDedup: {near_dedup['reason']}"

    elif rule_check["can_execute"] and action != "provide_info":
        # L2-1. NumericalConsistencyCheck: verify amount against CRM BEFORE execution
        num_check = _numerical_consistency_check(action, details, crm_data)
        logs.append({
            "node": 5, "technique": "NumericalConsistencyCheck", "duration_ms": 0,
            "result_summary": f"consistent={num_check['consistent']}",
        })

        if not num_check["consistent"]:
            # Amount doesn't match CRM — BLOCK before Stripe gets called
            actions_taken.append({
                "action": action,
                "thought": f"NumericalConsistencyCheck BLOCKED: {num_check['reason']}",
                "observation": "Action blocked — amount inconsistent with CRM data",
                "status": "blocked",
            })
            verified = False
            verification_result = num_check["reason"]
            logger.warning(
                "Node 5 numerical block: ticket=%s action=%s %s",
                state.get("ticket_id", ""), action, num_check["reason"],
            )

        else:
            # Amount looks good — proceed with ReAct execution
            react_result = await _react_execute(action, details, knowledge_str, crm_data, tenant_id=tenant_id, state=state, logs=logs)

            # L2-2. SafetyNet: scrub PII from observation AFTER execution
            if react_result.get("observation"):
                pii_check = _safety_net_scrub(react_result["observation"])
                if pii_check["pii_found"]:
                    react_result["observation"] = pii_check["scrubbed"]
                    logs.append({
                        "node": 5, "technique": "SafetyNet", "duration_ms": 0,
                        "result_summary": f"pii_scrubbed count={pii_check['count']}",
                    })
                else:
                    logs.append({
                        "node": 5, "technique": "SafetyNet", "duration_ms": 0,
                        "result_summary": "no_pii_found",
                    })

            actions_taken.append(react_result)
            logs.append({"node": 5, "technique": "ReAct", "duration_ms": 0, "result_summary": f"status={react_result['status']}"})
            llm_calls += 1

            # ══════════════════════════════════════════════════════
            # L3: VERIFY
            # ══════════════════════════════════════════════════════

            # Reverse Thinking: verify (LLM)
            reverse_result = await _reverse_verify(action, react_result, knowledge_str)
            logs.append({"node": 5, "technique": "ReverseThinking", "duration_ms": 0, "result_summary": f"verified={reverse_result['verified']}"})
            llm_calls += 1

            verified = reverse_result["verified"]
            verification_result = reverse_result["analysis"]

    else:
        # Can't execute or provide_info — recommend instead
        if not rule_check["can_execute"]:
            actions_taken.append({
                "action": action,
                "thought": f"Cannot execute: {rule_check['reason']}. Providing recommendation instead.",
                "observation": "Recommendation provided (not executed)",
                "status": "recommended",
            })
            verified = True  # recommendation is always "safe"
            verification_result = rule_check["reason"]
        else:
            actions_taken.append({
                "action": "provide_info",
                "thought": "Information provision — no execution needed",
                "observation": "Information provided from knowledge base",
                "status": "completed",
            })
            verified = True
            verification_result = "No execution required"

    # ══════════════════════════════════════════════════════════════
    # L3: POST-VERIFICATION CHECKS
    # ══════════════════════════════════════════════════════════════

    # L3-1. ContradictionCheck: ReAct vs ReverseThinking
    contradiction = _contradiction_check(react_result or {}, reverse_result or {})
    logs.append({
        "node": 5, "technique": "ContradictionCheck", "duration_ms": 0,
        "result_summary": f"has_contradiction={contradiction['has_contradiction']}",
    })

    # L3-2. ZeroShotValidator: flag unusual actions
    zsv = _zero_shot_flag_action(action, details, knowledge_str)
    logs.append({"node": 5, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"flagged={zsv['flagged']}"})

    if zsv["flagged"]:
        for flag in zsv["flags"]:
            logs.append({"node": 5, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"flag: {flag}"})

    # L3-3. Escalation: auto-escalate high risk
    escalation = _should_escalate(action, reverse_result or {}, zsv, contradiction, tier)
    logs.append({
        "node": 5, "technique": "Escalation", "duration_ms": 0,
        "result_summary": f"escalate={escalation['escalate']} reasons={len(escalation['reasons'])}",
    })

    # ══════════════════════════════════════════════════════════════
    # L4: POST-CHECK — final safety gates before shipping
    # ══════════════════════════════════════════════════════════════

    # L4-1. SufficiencyCheck: did we solve the customer's problem?
    sufficiency = _sufficiency_check(action, actions_taken, state.get("original_query", ""))
    logs.append({
        "node": 5, "technique": "SufficiencyCheck", "duration_ms": 0,
        "result_summary": f"sufficient={sufficiency['sufficient']}",
    })

    # L4-2. MAKER FinalCheck + StrictMode
    execution_ok = any(a.get("status") in ("completed", "recommended") for a in actions_taken if isinstance(a, dict))
    verification_ok = verified
    maker_final = _maker_final_check(action, knowledge_str, bridge, execution_ok, verification_ok)
    logs.append({
        "node": 5, "technique": "MAKER.FinalCheck", "duration_ms": 0,
        "result_summary": f"block={maker_final['should_block']} strict={maker_final['strict_mode']} gaps={len(maker_final['critical_gaps'])}",
    })

    # StrictMode: 2+ critical gaps → hard block
    if maker_final["strict_mode"]:
        logger.warning(
            "Node 5 STRICT MODE BLOCK: ticket=%s action=%s gaps=%s",
            state.get("ticket_id", ""), action, maker_final["critical_gaps"],
        )
        verified = False
        verification_result = f"STRICT MODE BLOCK: {maker_final['critical_gaps']}"

    # L4-3. PolicyCitationChecker
    observation_for_check = " ".join(
        a.get("observation", "") for a in actions_taken if isinstance(a, dict)
    )
    policy_check = _policy_citation_check(action, knowledge_str, observation_for_check)
    logs.append({
        "node": 5, "technique": "PolicyCitationChecker", "duration_ms": 0,
        "result_summary": f"cited={policy_check['cited']}",
    })

    # L4-4. MetaLearner: adjust confidence from past patterns
    meta = _meta_learner_adjust(action, tier, state)
    logs.append({
        "node": 5, "technique": "MetaLearner", "duration_ms": 0,
        "result_summary": f"adjustment={meta['confidence_adjustment']} {meta['reason']}",
    })

    # L4-5. ActionAuditTrail
    audit = _build_audit_trail(
        action, details, tier, rule_check, react_result, reverse_result,
        zsv, escalation, verified,
    )
    logs.append({
        "node": 5, "technique": "ActionAuditTrail", "duration_ms": 0,
        "result_summary": f"action={action} verified={verified} escalated={escalation['escalate']}",
    })

    # ── Wave 4: Check Jarvis approval_overrides ─────────────
    system_flags = state.get("system_flags", {})
    approval_overrides = system_flags.get("approval_overrides", [])
    ticket_type = state.get("ticket_type", "")
    required_action = state.get("required_action", "")

    # If this action type has an approval override, auto-approve
    is_auto_approved = (
        required_action in approval_overrides
        or ticket_type in approval_overrides
        or "all" in approval_overrides
    )
    if is_auto_approved:
        logs.append({"node": 5, "technique": "JARVIS_APPROVAL_OVERRIDE", "duration_ms": 0,
                     "result_summary": f"auto_approved action={required_action} type={ticket_type}"})
        logger.info("Node 5: Auto-approved by Jarvis override: action=%s type=%s", required_action, ticket_type)


    # 7. UCB execute (mock — wired in Phase 7)
    logs.append({"node": 5, "technique": "UCB", "duration_ms": 0, "result_summary": f"action_executed auto_approved={is_auto_approved}"})

    # ── P0 Notification: emit ai:action_taken for each action ──────
    # Tells Jarvis CC (and any human watching) what the AI actually did.
    # Includes the tool_executed field so the human knows if a real tool
    # ran (HubSpot lookup, Shopify order check, etc.) or if no tool matched.
    try:
        from app.core.event_emitter import emit_ai_event
        tenant_id_for_emit = state.get("tenant_id", "")
        ticket_id_for_emit = state.get("ticket_id", "")
        for at in actions_taken:
            await emit_ai_event(
                company_id=tenant_id_for_emit,
                event_type="ai:action_taken",
                payload={
                    "company_id": tenant_id_for_emit,
                    "ticket_id": ticket_id_for_emit,
                    "action": at.get("action", ""),
                    "tool_executed": at.get("tool_executed"),
                    "observation": (at.get("observation") or "")[:500],
                    "verified": verified,
                    "auto_approved": is_auto_approved,
                    "node": 5,
                },
                correlation_id=ticket_id_for_emit,
            )
    except Exception as exc:
        logger.warning("node_5_action_notification_failed: %s", str(exc)[:200])

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 5 complete: ticket=%s action=%s verified=%s escalate=%s llm=%d [%dms]",
        state["ticket_id"], action, verified, escalation.get("escalate", False), llm_calls, elapsed,
    )

    return {
        "actions_taken": actions_taken,
        "actions_verified": verified,
        "verification_result": verification_result,
        "technique_log": logs,
        "node_5_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
        "action_audit": audit,
        "escalation_required": escalation.get("escalate", False),
        "escalation_reasons": escalation.get("reasons", []),
        "maker_final_block": maker_final.get("should_block", False),
        "policy_cited": policy_check.get("cited", True),
        "sufficiency": sufficiency.get("sufficient", True),
        "meta_confidence_adjustment": meta.get("confidence_adjustment", 0.0),
    }


def _run_action_safety_gate(tool_id: str, description: str, tool_input: dict,
                            tenant_id: str, variant_tier: str) -> dict:
    """Run the Superglue Action Safety pipeline before tool execution.

    Pipeline: classify_action → check_financial_guardrails → needs_approval check.

    Returns dict with keys:
      - blocked (bool): if True, do NOT execute the tool
      - reason (str): human-readable explanation
      - safety_level (str): the classified level
      - needs_approval (bool): whether this action requires human approval
      - guardrail_result (dict|None): raw guardrail result if applicable

    BC-008: never crashes — returns {blocked: False} on any error so
    execution proceeds as normal.
    """
    default = {"blocked": False, "reason": "", "safety_level": "read",
               "needs_approval": False, "guardrail_result": None}
    try:
        from app.core.action_safety import classify_action, needs_approval as _needs_approval
        from app.core.action_safety import ActionSafetyLevel
        from app.core.regulatory_guardrails import check_financial_guardrails

        # Step 1: Classify the action
        safety = classify_action(tool_id, description)
        logs_safe = []  # will be assigned by caller if needed

        # Step 2: For FINANCIAL actions, check tier-based guardrails
        guardrail_result = None
        if safety.level == ActionSafetyLevel.FINANCIAL:
            amount = float(tool_input.get("amount", 0)) if isinstance(tool_input, dict) else 0.0
            gr = check_financial_guardrails(safety.level.value, amount, variant_tier, tool_id)
            guardrail_result = {"allowed": gr.allowed, "reason": gr.reason,
                                "limit": gr.limit, "remaining": gr.remaining}
            if not gr.allowed:
                return {"blocked": True, "reason": f"Guardrail blocked: {gr.reason}",
                        "safety_level": safety.level.value, "needs_approval": True,
                        "guardrail_result": guardrail_result}

        # Step 3: Check if approval is required for this safety level
        approval = _needs_approval(safety.level)
        return {"blocked": False, "reason": safety.reasoning,
                "safety_level": safety.level.value, "needs_approval": approval,
                "guardrail_result": guardrail_result}
    except Exception as exc:
        logger.debug("action_safety_gate_error: %s", str(exc)[:150])
        return default


async def _execute_with_idempotency(tool_id, tool_input, idempotency_key, ticket_id, action, tenant_id=""):
    """Execute a Superglue tool with idempotency + safety gate protection.

    Pipeline: action safety gate → idempotency check → execute.
    Returns special keys "guardrail_blocked" and "safety_approval_required" so
    the caller can distinguish safety blocks from normal failures.
    """
    from app.core.superglue_client import execute_tool
    from database.base import SessionLocal
    from sqlalchemy import text as _sql_text

    # ── ACTION SAFETY GATE (runs before idempotency check) ──
    try:
        _sg = _run_action_safety_gate(tool_id, action, tool_input or {}, tenant_id, "parwa")
        if _sg["blocked"]:
            return {"success": False, "error": _sg["reason"],
                    "guardrail_blocked": True, "safety_level": _sg["safety_level"]}
        if _sg["needs_approval"]:
            return {"success": False, "error": f"Safety approval required: {_sg['reason']}",
                    "safety_approval_required": True, "safety_level": _sg["safety_level"]}
    except Exception as _sg_exc:
        logger.debug("idempotency_safety_gate_error: %s", str(_sg_exc)[:100])

    # ── IDEMPOTENCY CHECK ──
    try:
        _idb = SessionLocal()
        try:
            # Check if already executed
            _existing = _idb.execute(_sql_text(
                "SELECT 1 FROM ticket_tool_executions "
                "WHERE idempotency_key = :key LIMIT 1"
            ), {"key": idempotency_key}).fetchone()

            if _existing:
                logger.warning(
                    "IDEMPOTENCY_BLOCK: ticket=%s tool=%s action=%s already executed — SKIP",
                    ticket_id[:8], tool_id[:20], action,
                )
                return {"success": False, "error": "already_executed", "skipped": True}

            # Not executed → execute now
            result = await execute_tool(tool_id, tool_input, tenant_id=tenant_id)

            # Record execution (prevent future duplicates)
            if result.get("success"):
                _idb.execute(_sql_text(
                    "INSERT INTO ticket_tool_executions "
                    "(idempotency_key, ticket_id, tool_id, action, executed_at) "
                    "VALUES (:key, :tid, :tool, :action, NOW()) "
                    "ON CONFLICT (idempotency_key) DO NOTHING"
                ), {"key": idempotency_key, "tid": ticket_id, "tool": tool_id, "action": action})
                _idb.commit()

            return result
        finally:
            _idb.close()
    except Exception as exc:
        # Table doesn't exist yet — just execute (backward compat)
        logger.debug("idempotency_check_skipped: %s", str(exc)[:100])
        return await execute_tool(tool_id, tool_input, tenant_id=tenant_id)
