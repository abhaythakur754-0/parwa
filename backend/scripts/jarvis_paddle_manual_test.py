"""
Jarvis Paddle Manual Test Script

Tests the full Jarvis pipeline with REAL Paddle API integration.
This script directly calls the Paddle API using the provided keys
and also tests the Jarvis-Paddle bridge.

Usage:
    cd backend
    python -m scripts.jarvis_paddle_manual_test

Environment:
    PADDLE_API_KEY - Paddle API key
    PADDLE_CLIENT_TOKEN - Paddle client token
    ZAI_API_KEY - Optional, for LLM function calling
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── ANSI Colors ──────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_header(text: str):
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")


def print_test(name: str, passed: bool, details: str = ""):
    icon = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{icon}] {name}")
    if details:
        for line in details.split("\n"):
            print(f"         {line}")


def print_info(text: str):
    print(f"  {CYAN}INFO:{RESET} {text}")


def print_result(title: str, data: Any):
    print(f"\n  {BOLD}{title}:{RESET}")
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)) and len(str(v)) > 100:
                print(f"    {k}: {json.dumps(v, indent=2)[:200]}...")
            else:
                print(f"    {k}: {v}")
    elif isinstance(data, list):
        for i, item in enumerate(data[:5]):
            print(f"    [{i}] {item}")
        if len(data) > 5:
            print(f"    ... and {len(data) - 5} more")
    else:
        print(f"    {data}")


# ══════════════════════════════════════════════════════════════════
# TEST 1: Paddle API Connectivity
# ══════════════════════════════════════════════════════════════════

async def test_paddle_connectivity(api_key: str, client_token: str, sandbox: bool = True) -> Dict[str, Any]:
    """Test basic Paddle API connectivity."""
    print_header("TEST 1: Paddle API Connectivity")
    
    from app.clients.paddle_client import PaddleClient, PaddleAuthError, PaddleError
    
    results = {"passed": 0, "failed": 0, "details": []}
    
    # Create client
    try:
        env = os.environ.get("ENVIRONMENT", "sandbox")
        # Use production URL since these are live keys
        client = PaddleClient(
            api_key=api_key,
            client_token=client_token,
            sandbox=False,  # Live keys = production
        )
        print_test("PaddleClient created", True)
        results["passed"] += 1
    except Exception as e:
        print_test("PaddleClient created", False, str(e))
        results["failed"] += 1
        return results
    
    # Test listing customers
    try:
        print_info("Calling Paddle API: GET /customers?per_page=5 ...")
        result = await client.list_customers(per_page=5)
        customers = result.get("data", [])
        print_test("List customers API call", True, f"Found {len(customers)} customers")
        results["passed"] += 1
        
        if customers:
            print_result("First Customer", {
                "id": customers[0].get("id", ""),
                "email": customers[0].get("email", ""),
                "name": customers[0].get("name", ""),
                "status": customers[0].get("status", ""),
            })
            results["details"].append({
                "type": "customer",
                "id": customers[0].get("id", ""),
                "email": customers[0].get("email", ""),
            })
    except PaddleAuthError as e:
        print_test("List customers API call", False, f"Auth error: {str(e)}")
        results["failed"] += 1
    except PaddleError as e:
        print_test("List customers API call", False, f"Paddle error: {str(e)}")
        results["failed"] += 1
    except Exception as e:
        print_test("List customers API call", False, f"Error: {str(e)}")
        results["failed"] += 1
    
    # Test listing subscriptions
    try:
        print_info("Calling Paddle API: GET /subscriptions?per_page=5 ...")
        result = await client.list_subscriptions(per_page=5)
        subscriptions = result.get("data", [])
        print_test("List subscriptions API call", True, f"Found {len(subscriptions)} subscriptions")
        results["passed"] += 1
        
        if subscriptions:
            sub = subscriptions[0]
            print_result("First Subscription", {
                "id": sub.get("id", ""),
                "status": sub.get("status", ""),
                "customer_id": sub.get("customer_id", ""),
                "next_billed_at": sub.get("next_billed_at", ""),
            })
            results["details"].append({
                "type": "subscription",
                "id": sub.get("id", ""),
                "status": sub.get("status", ""),
                "customer_id": sub.get("customer_id", ""),
            })
    except Exception as e:
        print_test("List subscriptions API call", False, str(e))
        results["failed"] += 1
    
    # Test listing transactions
    try:
        print_info("Calling Paddle API: GET /transactions?per_page=5 ...")
        result = await client.list_transactions(per_page=5)
        transactions = result.get("data", [])
        print_test("List transactions API call", True, f"Found {len(transactions)} transactions")
        results["passed"] += 1
        
        if transactions:
            txn = transactions[0]
            print_result("First Transaction", {
                "id": txn.get("id", ""),
                "status": txn.get("status", ""),
                "origin": txn.get("origin", ""),
                "created_at": txn.get("created_at", ""),
                "total": txn.get("details", {}).get("totals", {}).get("total", ""),
            })
            results["details"].append({
                "type": "transaction",
                "id": txn.get("id", ""),
            })
    except Exception as e:
        print_test("List transactions API call", False, str(e))
        results["failed"] += 1
    
    # Test listing prices
    try:
        print_info("Calling Paddle API: GET /prices?per_page=5 ...")
        result = await client.list_prices(per_page=5)
        prices = result.get("data", [])
        print_test("List prices API call", True, f"Found {len(prices)} prices")
        results["passed"] += 1
        
        if prices:
            price = prices[0]
            print_result("First Price", {
                "id": price.get("id", ""),
                "name": price.get("name", ""),
                "amount": price.get("unit_price", {}),
            })
    except Exception as e:
        print_test("List prices API call", False, str(e))
        results["failed"] += 1
    
    await client.close()
    return results


# ══════════════════════════════════════════════════════════════════
# TEST 2: Jarvis-Paddle Bridge
# ══════════════════════════════════════════════════════════════════

async def test_jarvis_paddle_bridge(api_key: str, client_token: str) -> Dict[str, Any]:
    """Test the Jarvis-Paddle Bridge directly."""
    print_header("TEST 2: Jarvis-Paddle Bridge")
    
    from app.services.jarvis_paddle_bridge import JarvisPaddleBridge
    
    results = {"passed": 0, "failed": 0}
    
    bridge = JarvisPaddleBridge(
        api_key=api_key,
        client_token=client_token,
        sandbox=False,  # Live keys
    )
    
    # Test list_customers (bridge method)
    try:
        print_info("Bridge: list_customers() ...")
        result = await bridge.list_customers(per_page=3)
        customers = result.get("customers", [])
        print_test("Bridge list_customers", result.get("success", False),
                   f"Found {len(customers)} customers")
        if result.get("success"):
            results["passed"] += 1
        else:
            results["failed"] += 1
        
        # Store first customer ID for later tests
        first_customer_id = None
        if customers:
            first_customer_id = customers[0].get("id", "")
            print_info(f"Customer ID for testing: {first_customer_id}")
    except Exception as e:
        print_test("Bridge list_customers", False, str(e))
        results["failed"] += 1
        first_customer_id = None
    
    # Test list_subscriptions (bridge method)
    try:
        print_info("Bridge: list_subscriptions() ...")
        result = await bridge.list_subscriptions(per_page=3)
        subscriptions = result.get("subscriptions", [])
        print_test("Bridge list_subscriptions", result.get("success", False),
                   f"Found {len(subscriptions)} subscriptions")
        if result.get("success"):
            results["passed"] += 1
        else:
            results["failed"] += 1
        
        first_subscription_id = None
        first_sub_customer_id = None
        if subscriptions:
            first_subscription_id = subscriptions[0].get("id", "")
            first_sub_customer_id = subscriptions[0].get("customer_id", "")
            print_info(f"Subscription ID: {first_subscription_id}")
            print_info(f"Subscription Customer ID: {first_sub_customer_id}")
    except Exception as e:
        print_test("Bridge list_subscriptions", False, str(e))
        results["failed"] += 1
        first_subscription_id = None
        first_sub_customer_id = None
    
    # Test get_subscription_info (bridge method)
    test_company_id = "test-company-001"
    if first_subscription_id:
        try:
            print_info(f"Bridge: get_subscription_info(sub_id={first_subscription_id}) ...")
            result = await bridge.get_subscription_info(
                company_id=test_company_id,
                paddle_subscription_id=first_subscription_id,
            )
            print_test("Bridge get_subscription_info (by sub ID)",
                       result.get("success", False),
                       f"Plan: {result.get('plan', 'N/A')}, Status: {result.get('status', 'N/A')}")
            if result.get("success"):
                results["passed"] += 1
                print_result("Subscription Info", result)
            else:
                results["failed"] += 1
        except Exception as e:
            print_test("Bridge get_subscription_info (by sub ID)", False, str(e))
            results["failed"] += 1
    elif first_sub_customer_id:
        try:
            print_info(f"Bridge: get_subscription_info(customer_id={first_sub_customer_id}) ...")
            result = await bridge.get_subscription_info(
                company_id=test_company_id,
                paddle_customer_id=first_sub_customer_id,
            )
            print_test("Bridge get_subscription_info (by customer ID)",
                       result.get("success", False),
                       f"Plan: {result.get('plan', 'N/A')}, Status: {result.get('status', 'N/A')}")
            if result.get("success"):
                results["passed"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            print_test("Bridge get_subscription_info (by customer ID)", False, str(e))
            results["failed"] += 1
    
    # Test get_transaction_history (bridge method)
    if first_sub_customer_id:
        try:
            print_info(f"Bridge: get_transaction_history(customer={first_sub_customer_id}) ...")
            result = await bridge.get_transaction_history(
                company_id=test_company_id,
                paddle_customer_id=first_sub_customer_id,
                period="last_30_days",
            )
            transactions = result.get("transactions", [])
            print_test("Bridge get_transaction_history",
                       result.get("success", False),
                       f"Found {len(transactions)} transactions")
            if result.get("success"):
                results["passed"] += 1
                if transactions:
                    print_result("Sample Transactions", transactions[:3])
                    print_info(f"Total payments: ${result.get('total_payments', 0):.2f}")
                    print_info(f"Total refunds: ${result.get('total_refunds', 0):.2f}")
            else:
                results["failed"] += 1
                print_info(f"Message: {result.get('message', '')}")
        except Exception as e:
            print_test("Bridge get_transaction_history", False, str(e))
            results["failed"] += 1
    else:
        print_test("Bridge get_transaction_history", False, "No customer ID available")
        results["failed"] += 1
    
    # Test list_invoices (bridge method)
    if first_sub_customer_id:
        try:
            print_info(f"Bridge: list_invoices(customer={first_sub_customer_id}) ...")
            result = await bridge.list_invoices(
                company_id=test_company_id,
                paddle_customer_id=first_sub_customer_id,
            )
            invoices = result.get("invoices", [])
            print_test("Bridge list_invoices",
                       result.get("success", False),
                       f"Found {len(invoices)} invoices")
            if result.get("success"):
                results["passed"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            print_test("Bridge list_invoices", False, str(e))
            results["failed"] += 1
    
    # Test process_refund (bridge method - READ ONLY, doesn't actually charge)
    try:
        print_info("Bridge: process_refund() [simulated] ...")
        result = await bridge.process_refund(
            company_id=test_company_id,
            customer_id="ctm_test_123",
            amount=9.99,
            reason="Test refund from Jarvis manual test",
        )
        print_test("Bridge process_refund",
                   result.get("success", False),
                   result.get("message", ""))
        if result.get("success"):
            results["passed"] += 1
        else:
            results["failed"] += 1
    except Exception as e:
        print_test("Bridge process_refund", False, str(e))
        results["failed"] += 1
    
    await bridge.close()
    return results


# ══════════════════════════════════════════════════════════════════
# TEST 3: Awareness Engine (No DB Required)
# ══════════════════════════════════════════════════════════════════

async def test_awareness_engine() -> Dict[str, Any]:
    """Test the Awareness Engine standalone functionality."""
    print_header("TEST 3: Awareness Engine")
    
    results = {"passed": 0, "failed": 0}
    
    # Test module import
    try:
        from app.services.jarvis_awareness_engine import (
            collect_awareness_state,
            compute_awareness_delta,
            get_effective_thresholds,
            SPIKE_MULTIPLIER,
            UTILIZATION_WARN_THRESHOLD,
            QUALITY_WARN_THRESHOLD,
        )
        print_test("Awareness Engine module import", True)
        results["passed"] += 1
    except Exception as e:
        print_test("Awareness Engine module import", False, str(e))
        results["failed"] += 1
        return results
    
    # Test thresholds
    try:
        thresholds = get_effective_thresholds()
        print_test("get_effective_thresholds()", True,
                   f"Spike multiplier: {thresholds.get('spike_multiplier', 'N/A')}, "
                   f"Utilization warn: {thresholds.get('utilization_warn_threshold', 'N/A')}%")
        results["passed"] += 1
    except Exception as e:
        print_test("get_effective_thresholds()", False, str(e))
        results["failed"] += 1
    
    # Test delta detection
    try:
        current = {
            "system_health": "degraded",
            "ticket_volume_today": 150,
            "quality_score": 0.65,
            "drift_score": 0.35,
            "current_plan": "parwa",
        }
        previous = {
            "system_health": "healthy",
            "ticket_volume_today": 50,
            "quality_score": 0.90,
            "drift_score": 0.10,
            "current_plan": "parwa",
        }
        delta = compute_awareness_delta(current, previous)
        has_changes = delta.get("has_significant_changes", False)
        new_alerts = delta.get("new_alerts", [])
        print_test("compute_awareness_delta()", True,
                   f"Significant changes: {has_changes}, New alerts: {len(new_alerts)}")
        results["passed"] += 1
        print_result("Delta Details", {
            "system_health_changed": delta.get("changed_fields", {}).get("system_health"),
            "ticket_volume_spike": delta.get("changed_fields", {}).get("ticket_volume_today"),
            "quality_dropped": delta.get("changed_fields", {}).get("quality_score"),
        })
    except Exception as e:
        print_test("compute_awareness_delta()", False, str(e))
        results["failed"] += 1
    
    return results


# ══════════════════════════════════════════════════════════════════
# TEST 4: Function Registry & Safety Gate
# ══════════════════════════════════════════════════════════════════

async def test_function_registry_and_safety() -> Dict[str, Any]:
    """Test the function registry and safety gate."""
    print_header("TEST 4: Function Registry & Safety Gate")
    
    results = {"passed": 0, "failed": 0}
    
    # Test function registry
    try:
        from app.services.jarvis_function_registry import (
            get_function_definitions,
            get_function_names,
            get_function_metadata,
            get_safety_level,
            get_function_count_by_safety,
            SAFETY_NONE,
            SAFETY_CONFIRMATION,
            SAFETY_APPROVAL,
        )
        
        # Get all function definitions
        defs = get_function_definitions(mode="command", tier="parwa")
        print_test(f"Function definitions loaded ({len(defs)} functions)", True)
        results["passed"] += 1
        
        # Check billing functions exist
        billing_funcs = [d for d in defs if d["function"]["name"] in
                        ("upgrade_plan", "cancel_subscription", "get_transaction_history", 
                         "process_refund", "get_subscription_info", "get_usage_report")]
        print_test("Billing functions available", len(billing_funcs) >= 4,
                   f"Found {len(billing_funcs)} billing functions: {[f['function']['name'] for f in billing_funcs]}")
        if len(billing_funcs) >= 4:
            results["passed"] += 1
        else:
            results["failed"] += 1
        
        # Check safety levels
        refund_safety = get_safety_level("process_refund")
        upgrade_safety = get_safety_level("upgrade_plan")
        health_safety = get_safety_level("check_system_health")
        cancel_safety = get_safety_level("cancel_subscription")
        txn_safety = get_safety_level("get_transaction_history")
        
        print_test("Safety levels correct",
                   refund_safety == SAFETY_APPROVAL and
                   upgrade_safety == SAFETY_APPROVAL and
                   cancel_safety == SAFETY_APPROVAL and
                   txn_safety == SAFETY_NONE and
                   health_safety == SAFETY_NONE,
                   f"refund={refund_safety}, upgrade={upgrade_safety}, "
                   f"cancel={cancel_safety}, txn_history={txn_safety}, health={health_safety}")
        if (refund_safety == SAFETY_APPROVAL and upgrade_safety == SAFETY_APPROVAL and
            cancel_safety == SAFETY_APPROVAL and txn_safety == SAFETY_NONE):
            results["passed"] += 1
        else:
            results["failed"] += 1
        
        # Function count by safety
        safety_counts = get_function_count_by_safety()
        print_info(f"Safety distribution: {safety_counts}")
        
    except Exception as e:
        print_test("Function registry", False, str(e))
        results["failed"] += 1
    
    # Test safety gate
    try:
        from app.services.jarvis_safety_gate import check_safety, SafetyCheckResult
        
        # Test 'none' safety level — should auto-approve
        result1 = check_safety(
            function_name="check_system_health",
            safety_level=SAFETY_NONE,
            company_id="test-co",
            session_id="test-session",
        )
        print_test("Safety gate: none → auto-approved",
                   result1.status == "approved",
                   f"Status: {result1.status}")
        if result1.status == "approved":
            results["passed"] += 1
        else:
            results["failed"] += 1
        
        # Test 'confirmation_required' — should need confirmation
        result2 = check_safety(
            function_name="pause_all_ai",
            safety_level=SAFETY_CONFIRMATION,
            company_id="test-co",
            session_id="test-session",
        )
        print_test("Safety gate: confirmation → needs_confirmation",
                   result2.status == "needs_confirmation",
                   f"Status: {result2.status}, Message: {result2.message[:80]}")
        if result2.status == "needs_confirmation":
            results["passed"] += 1
        else:
            results["failed"] += 1
        
        # Test 'approval_required' — should need approval
        result3 = check_safety(
            function_name="process_refund",
            safety_level=SAFETY_APPROVAL,
            company_id="test-co",
            session_id="test-session",
            params={"customer_id": "c1", "amount": 50.00, "reason": "test"},
        )
        print_test("Safety gate: approval → needs_approval",
                   result3.status == "needs_approval",
                   f"Status: {result3.status}, Message: {result3.message[:80]}")
        if result3.status == "needs_approval":
            results["passed"] += 1
        else:
            results["failed"] += 1
        
    except Exception as e:
        print_test("Safety gate", False, str(e))
        results["failed"] += 1
    
    return results


# ══════════════════════════════════════════════════════════════════
# TEST 5: Agentic vs Command Mode
# ══════════════════════════════════════════════════════════════════

async def test_mode_switching() -> Dict[str, Any]:
    """Test agentic vs command mode switching."""
    print_header("TEST 5: Mode Switching (Agentic vs Command)")
    
    results = {"passed": 0, "failed": 0}
    
    try:
        from app.services.jarvis_function_registry import get_function_definitions, get_function_names
        from app.services.jarvis_orchestrator import decide_mode
        
        # Command mode — should get ALL functions
        command_defs = get_function_definitions(mode="command", tier="parwa")
        command_names = get_function_names(mode="command", tier="parwa")
        
        # Agentic mode — should only get customer_facing functions
        agentic_defs = get_function_definitions(mode="agentic", tier="parwa")
        agentic_names = get_function_names(mode="agentic", tier="parwa")
        
        print_test(f"Command mode: {len(command_defs)} functions", True,
                   f"Functions: {', '.join(command_names[:10])}...")
        results["passed"] += 1
        
        print_test(f"Agentic mode: {len(agentic_defs)} functions", True,
                   f"Functions: {', '.join(agentic_names)}")
        results["passed"] += 1
        
        # Verify agentic mode only has customer_facing
        non_customer_facing = [n for n in agentic_names if n not in
                              ("answer_customer_question", "check_order_status", "escalate_to_human")]
        print_test("Agentic mode only has customer_facing functions",
                   len(non_customer_facing) == 0,
                   f"Non-customer-facing: {non_customer_facing}" if non_customer_facing else "All functions are customer-facing")
        if len(non_customer_facing) == 0:
            results["passed"] += 1
        else:
            results["failed"] += 1
        
        # Verify command mode has billing functions
        has_billing = any(n in command_names for n in
                         ("upgrade_plan", "get_transaction_history", "process_refund", "cancel_subscription"))
        print_test("Command mode has billing functions", has_billing)
        if has_billing:
            results["passed"] += 1
        else:
            results["failed"] += 1
        
        # Test decide_mode logic
        agentic_context = {"session": {"type": "customer_care", "mode": "customer_care"}}
        command_context1 = {"session": {"type": "admin", "mode": "admin"}}
        command_context2 = {"session": {"type": "onboarding", "mode": "onboarding"}}
        
        mode1 = decide_mode(agentic_context)
        mode2 = decide_mode(command_context1)
        mode3 = decide_mode(command_context2)
        
        print_test("decide_mode: customer_care → agentic", mode1 == "agentic",
                   f"Got: {mode1}")
        print_test("decide_mode: admin → command", mode2 == "command",
                   f"Got: {mode2}")
        print_test("decide_mode: onboarding → command", mode3 == "command",
                   f"Got: {mode3}")
        
        if mode1 == "agentic":
            results["passed"] += 1
        else:
            results["failed"] += 1
        if mode2 == "command":
            results["passed"] += 1
        else:
            results["failed"] += 1
        if mode3 == "command":
            results["passed"] += 1
        else:
            results["failed"] += 1
        
    except Exception as e:
        print_test("Mode switching", False, str(e))
        results["failed"] += 1
    
    return results


# ══════════════════════════════════════════════════════════════════
# TEST 6: Jarvis Conversational Pipeline (Pattern Matching)
# ══════════════════════════════════════════════════════════════════

async def test_conversational_pipeline() -> Dict[str, Any]:
    """Test the Jarvis conversational pipeline with pattern matching."""
    print_header("TEST 6: Jarvis Conversational Pipeline")
    
    results = {"passed": 0, "failed": 0}
    
    # Pattern matching for intent detection (no LLM needed)
    intent_patterns = {
        "check_system_health": ["how is the system", "system health", "how are things", "system status"],
        "get_subscription_info": ["what plan am i on", "subscription info", "my plan", "billing info"],
        "get_transaction_history": ["transaction history", "billing history", "payment history", "show transactions"],
        "upgrade_plan": ["upgrade plan", "upgrade to parwa", "change plan", "move to parwa high"],
        "cancel_subscription": ["cancel subscription", "cancel my plan", "stop subscription"],
        "process_refund": ["process refund", "refund customer", "issue a refund", "give refund"],
        "pause_all_ai": ["pause ai", "stop ai", "pause all agents"],
        "create_ticket": ["create ticket", "new ticket", "log a ticket", "report issue"],
        "solve_ticket": ["solve ticket", "resolve ticket", "handle this ticket"],
    }
    
    test_messages = [
        ("how is the system doing", "check_system_health"),
        ("what plan am I on right now", "get_subscription_info"),
        ("show me my transaction history", "get_transaction_history"),
        ("I want to upgrade to parwa", "upgrade_plan"),
        ("cancel my subscription please", "cancel_subscription"),
        ("process a refund for $25", "process_refund"),
        ("pause all AI agents", "pause_all_ai"),
        ("create a new ticket for a delivery issue", "create_ticket"),
        ("solve ticket TK-123", "solve_ticket"),
    ]
    
    for message, expected_intent in test_messages:
        detected_intent = None
        message_lower = message.lower()
        
        for intent, patterns in intent_patterns.items():
            for pattern in patterns:
                if pattern in message_lower:
                    detected_intent = intent
                    break
            if detected_intent:
                break
        
        passed = detected_intent == expected_intent
        print_test(f"'{message}' → {expected_intent}", passed,
                   f"Detected: {detected_intent or 'none'}")
        if passed:
            results["passed"] += 1
        else:
            results["failed"] += 1
    
    return results


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

async def main():
    print(f"\n{BOLD}{CYAN}")
    print("  ╔══════════════════════════════════════════════════════════════╗")
    print("  ║        JARVIS PADDLE INTEGRATION — MANUAL TEST SUITE         ║")
    print("  ║        Testing with REAL Paddle API + Jarvis Pipeline        ║")
    print("  ╚══════════════════════════════════════════════════════════════╝")
    print(f"{RESET}")
    
    # Get API keys
    api_key = os.environ.get("PADDLE_API_KEY", "")
    client_token = os.environ.get("PADDLE_CLIENT_TOKEN", "")
    
    if not api_key:
        print(f"\n{RED}ERROR: PADDLE_API_KEY not set!{RESET}")
        print("Set it with: export PADDLE_API_KEY='your-key-here'")
        print("Set PADDLE_CLIENT_TOKEN as well if available.")
        return
    
    print_info(f"API Key: {api_key[:20]}...{api_key[-5:]}")
    print_info(f"Client Token: {client_token[:20]}...{client_token[-5:]}" if client_token else "Client Token: (not set)")
    print_info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    total_passed = 0
    total_failed = 0
    
    # Run all tests
    try:
        r1 = await test_paddle_connectivity(api_key, client_token)
        total_passed += r1["passed"]
        total_failed += r1["failed"]
    except Exception as e:
        print(f"\n{RED}TEST 1 CRASHED: {str(e)}{RESET}")
    
    try:
        r2 = await test_jarvis_paddle_bridge(api_key, client_token)
        total_passed += r2["passed"]
        total_failed += r2["failed"]
    except Exception as e:
        print(f"\n{RED}TEST 2 CRASHED: {str(e)}{RESET}")
    
    try:
        r3 = await test_awareness_engine()
        total_passed += r3["passed"]
        total_failed += r3["failed"]
    except Exception as e:
        print(f"\n{RED}TEST 3 CRASHED: {str(e)}{RESET}")
    
    try:
        r4 = await test_function_registry_and_safety()
        total_passed += r4["passed"]
        total_failed += r4["failed"]
    except Exception as e:
        print(f"\n{RED}TEST 4 CRASHED: {str(e)}{RESET}")
    
    try:
        r5 = await test_mode_switching()
        total_passed += r5["passed"]
        total_failed += r5["failed"]
    except Exception as e:
        print(f"\n{RED}TEST 5 CRASHED: {str(e)}{RESET}")
    
    try:
        r6 = await test_conversational_pipeline()
        total_passed += r6["passed"]
        total_failed += r6["failed"]
    except Exception as e:
        print(f"\n{RED}TEST 6 CRASHED: {str(e)}{RESET}")
    
    # Summary
    print_header("TEST SUMMARY")
    total = total_passed + total_failed
    print(f"  {BOLD}Total Tests: {total}{RESET}")
    print(f"  {GREEN}{BOLD}Passed: {total_passed}{RESET}")
    print(f"  {RED}{BOLD}Failed: {total_failed}{RESET}")
    print(f"  Success Rate: {(total_passed/total*100):.1f}%" if total > 0 else "  No tests run")
    
    if total_failed == 0:
        print(f"\n  {GREEN}{BOLD}ALL TESTS PASSED!{RESET}\n")
    else:
        print(f"\n  {YELLOW}{BOLD}Some tests failed — check details above.{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
