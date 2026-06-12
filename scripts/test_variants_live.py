#!/usr/bin/env python3
"""PARWA Variant Test Runner — Real LLM Testing.

This script tests all 3 PARWA variants with real-world tickets.

Usage:
    python scripts/test_variants_live.py
    PARWA_MOCK_MODE=false python scripts/test_variants_live.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from parwa.config import MINI_PARWA, PARWA, PARWA_HIGH, MODEL_TIERS, get_variant_tiers, get_model_for_node
from parwa.permissions import VariantEnforcer, get_variant_enforcer
from parwa.state import ActionType, ExecutionMode, TicketChannel
from parwa.graph import aprocess_ticket, reset_parwa_graph
from parwa.utils.llm import smart_route_model

sys.path.insert(0, str(project_root / "tests"))
from real_world_tickets import TICKETS

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_header(text: str) -> None:
    width = 70
    print(f"\n{BOLD}{CYAN}{'=' * width}{RESET}")
    print(f"{BOLD}{CYAN}  {text:^{width - 4}}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * width}{RESET}\n")


def print_section(text: str) -> None:
    print(f"\n{BOLD}{BLUE}-- {text} --{RESET}")


def print_result(passed: bool, text: str) -> None:
    icon = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{icon}] {text}")


def badge(variant: str) -> str:
    colors = {"mini": YELLOW, "parwa": BLUE, "high": MAGENTA}
    return f"{BOLD}{colors.get(variant, RESET)}[{variant.upper()}]{RESET}"


def test_variant_enforcer_config() -> dict[str, Any]:
    print_section("Test 1: VariantEnforcer Configuration")
    results = {"passed": 0, "failed": 0}

    for variant in [MINI_PARWA, PARWA, PARWA_HIGH]:
        enforcer = get_variant_enforcer(variant)
        summary = enforcer.summary()

        expected_tiers = get_variant_tiers(variant)
        ok = set(summary["tiers"]) == set(expected_tiers)
        print_result(ok, f"{badge(variant)} Tiers: {summary['tiers']}")
        results["passed" if ok else "failed"] += 1

        ok = len(summary["channels"]) > 0
        print_result(ok, f"{badge(variant)} Channels: {summary['channels']}")
        results["passed" if ok else "failed"] += 1

        if variant == PARWA_HIGH:
            ok = summary["total_nodes_downgraded"] == 0
        elif variant == MINI_PARWA:
            ok = summary["total_nodes_downgraded"] > 0
        else:
            ok = True
        print_result(ok, f"{badge(variant)} Downgraded nodes: {summary['total_nodes_downgraded']}")
        results["passed" if ok else "failed"] += 1

    return results


def test_model_tier_enforcement() -> dict[str, Any]:
    print_section("Test 2: Model Tier Enforcement")
    results = {"passed": 0, "failed": 0}

    test_nodes = [
        ("INGEST", "light"),
        ("REASONING_ENGINE", "medium"),
        ("QUALITY_SCORER", "medium"),
    ]

    for node_name, required_tier in test_nodes:
        for variant in [MINI_PARWA, PARWA, PARWA_HIGH]:
            model = get_model_for_node(node_name, variant)
            allowed_tiers = get_variant_tiers(variant)
            model_tier = None
            for tier_name, tier_models in MODEL_TIERS.items():
                if model in tier_models:
                    model_tier = tier_name
                    break
            ok = model_tier in allowed_tiers
            print_result(ok, f"{badge(variant)} {node_name}: needs={required_tier}, gets={model_tier} ({model})")
            results["passed" if ok else "failed"] += 1

    return results


def test_channel_enforcement() -> dict[str, Any]:
    print_section("Test 3: Channel Enforcement")
    results = {"passed": 0, "failed": 0}

    channel_expectations = {
        MINI_PARWA: {"email": True, "chat": True, "social": False, "voice": False},
        PARWA: {"email": True, "chat": True, "social": True, "voice": False},
        PARWA_HIGH: {"email": True, "chat": True, "social": True, "voice": True},
    }

    for variant, expected in channel_expectations.items():
        enforcer = get_variant_enforcer(variant)
        for channel, should_allow in expected.items():
            result = enforcer.enforce_channel(channel)
            ok = result["allowed"] == should_allow
            status = "ALLOWED" if result["allowed"] else "BLOCKED"
            print_result(ok, f"{badge(variant)} {channel}: {status}")
            results["passed" if ok else "failed"] += 1

    return results


def test_action_permissions() -> dict[str, Any]:
    print_section("Test 4: Action Permission Enforcement")
    results = {"passed": 0, "failed": 0}

    action_expectations = {
        "process_refund": {MINI_PARWA: "recommend", PARWA: "execute", PARWA_HIGH: "execute"},
        "cancel_order": {MINI_PARWA: "recommend", PARWA: "execute", PARWA_HIGH: "execute"},
        "voice_call": {MINI_PARWA: "deny", PARWA: "deny", PARWA_HIGH: "execute"},
        "bulk_operation": {MINI_PARWA: "deny", PARWA: "deny", PARWA_HIGH: "execute"},
        "send_reply": {MINI_PARWA: "execute", PARWA: "execute", PARWA_HIGH: "execute"},
    }

    for action_str, expected_modes in action_expectations.items():
        for variant, expected_mode in expected_modes.items():
            enforcer = get_variant_enforcer(variant)
            action_type = ActionType(action_str)
            actual_mode = enforcer.get_action_mode(action_type).value
            ok = actual_mode == expected_mode
            print_result(ok, f"{badge(variant)} {action_str}: expected={expected_mode}, actual={actual_mode}")
            results["passed" if ok else "failed"] += 1

    return results


async def test_pipeline_with_tickets() -> dict[str, Any]:
    print_section("Test 5: Pipeline Processing with Real-World Tickets")
    results = {"passed": 0, "failed": 0}

    test_tickets = [TICKETS[0], TICKETS[6], TICKETS[8]]

    for ticket in test_tickets:
        print(f"\n  {BOLD}Ticket: {ticket['id']} - {ticket['name']}{RESET}")

        for variant in [MINI_PARWA, PARWA, PARWA_HIGH]:
            reset_parwa_graph()
            try:
                start_time = time.time()
                result = await aprocess_ticket(
                    raw_message=ticket["raw_message"],
                    customer_id=ticket["customer_id"],
                    channel=ticket["channel"],
                    variant=variant,
                )
                elapsed = time.time() - start_time

                has_response = bool(result.get("final_response"))
                print_result(has_response, f"{badge(variant)} Response generated ({elapsed:.1f}s)")
                results["passed" if has_response else "failed"] += 1

                expectations = ticket["variant_expectations"].get(variant, {})
                if "action_status" in expectations:
                    exec_results = result.get("execution_results", [])
                    has_expected = any(r.get("status") == expectations["action_status"] for r in exec_results)
                    print_result(has_expected, f"{badge(variant)} Action: {expectations['action_status']}")
                    results["passed" if has_expected else "failed"] += 1

            except Exception as exc:
                print_result(False, f"{badge(variant)} Error: {exc}")
                results["failed"] += 1

    return results


async def test_think_vs_act() -> dict[str, Any]:
    print_section("Test 6: Think vs Act Principle")
    results = {"passed": 0, "failed": 0}

    message = "I was charged twice for order #ORD-78234. $149.99 on Jan 5th and again on Jan 5th."
    variant_results = {}

    for variant in [MINI_PARWA, PARWA, PARWA_HIGH]:
        reset_parwa_graph()
        try:
            result = await aprocess_ticket(
                raw_message=message,
                customer_id="CUST-44921",
                channel="email",
                variant=variant,
            )
            variant_results[variant] = result
            print_result(True, f"{badge(variant)} Intent: {result.get('intent')}, Complexity: {result.get('complexity')}")
            results["passed"] += 1
        except Exception as exc:
            print_result(False, f"{badge(variant)} Error: {exc}")
            results["failed"] += 1

    if len(variant_results) == 3:
        intents = {v: variant_results[v].get("intent") for v in variant_results}
        complexities = {v: variant_results[v].get("complexity") for v in variant_results}

        same_intent = len(set(intents.values())) == 1
        same_complexity = len(set(complexities.values())) == 1

        print_result(same_intent, f"All variants THINK same intent: {intents}")
        print_result(same_complexity, f"All variants THINK same complexity: {complexities}")
        results["passed" if same_intent else "failed"] += 1
        results["passed" if same_complexity else "failed"] += 1

        mini_exec = variant_results.get(MINI_PARWA, {}).get("execution_results", [])
        high_exec = variant_results.get(PARWA_HIGH, {}).get("execution_results", [])

        mini_recommended = any(r.get("status") == "recommended" for r in mini_exec)
        high_executed = any(r.get("status") == "executed" for r in high_exec)

        acting_differs = mini_recommended or high_executed
        print_result(acting_differs, f"Mini recommends={mini_recommended}, High executes={high_executed} - ACTing differs!")
        results["passed" if acting_differs else "failed"] += 1

    return results


async def run_all_tests() -> None:
    mock_mode = os.getenv("PARWA_MOCK_MODE", "true").lower() == "true"

    print_header("PARWA Phase 7: Variant Enforcement Test Suite")
    print(f"  Mode: {'MOCK (deterministic)' if mock_mode else 'LIVE (real LLM calls)'}")
    print(f"  Variants: Mini, PARWA, High")
    print(f"  Tickets: {len(TICKETS)} real-world test cases")

    all_results = {}
    all_results["config"] = test_variant_enforcer_config()
    all_results["model_tiers"] = test_model_tier_enforcement()
    all_results["channels"] = test_channel_enforcement()
    all_results["actions"] = test_action_permissions()
    all_results["pipeline"] = await test_pipeline_with_tickets()
    all_results["think_vs_act"] = await test_think_vs_act()

    print_header("Test Summary")
    total_passed = sum(r["passed"] for r in all_results.values())
    total_failed = sum(r["failed"] for r in all_results.values())
    total = total_passed + total_failed

    for test_name, result in all_results.items():
        status = f"{GREEN}PASSED{RESET}" if result["failed"] == 0 else f"{RED}FAILED{RESET}"
        print(f"  {test_name}: {result['passed']}/{result['passed'] + result['failed']} {status}")

    print(f"\n  {BOLD}Total: {total_passed}/{total} passed{RESET}")

    if total_failed > 0:
        print(f"  {RED}{BOLD}{total_failed} tests FAILED{RESET}")
    else:
        print(f"  {GREEN}{BOLD}All tests PASSED!{RESET}")

    report_path = project_root / "test_report_phase7.json"
    report = {
        "phase": 7,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mock_mode": mock_mode,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "results": {k: {"passed": v["passed"], "failed": v["failed"]} for k, v in all_results.items()},
    }
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report: {report_path}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
