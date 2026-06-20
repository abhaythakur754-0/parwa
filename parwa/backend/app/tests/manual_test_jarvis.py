#!/usr/bin/env python3
"""
PARWA Jarvis CLI — Manual Test Script

This script lets you chat with Jarvis directly from the terminal
to test the new ticket creation, variant solving, and fake request
generation capabilities.

Usage:
  python manual_test_jarvis.py

You'll be able to type messages and see Jarvis respond in real-time.
Try things like:
  - "create a ticket about a login issue"
  - "generate 5 fake customer requests"
  - "generate 3 billing requests and auto-solve them"
  - "show me recent tickets"
  - "solve all open tickets"
  - "how's everything going?"
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Add the project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Test company/user IDs
TEST_COMPANY_ID = "manual-test-company-001"
TEST_SESSION_ID = f"manual-test-session-{uuid.uuid4().hex[:8]}"
TEST_USER_ID = "manual-test-user-001"


def print_header():
    """Print the test script header."""
    print("\n" + "=" * 70)
    print("  JARVIS CLI — Manual Test")
    print("=" * 70)
    print()
    print("  Type naturally and Jarvis will respond.")
    print("  Try these commands:")
    print()
    print("  • 'create a ticket about a login issue'")
    print("  • 'generate 5 fake customer requests'")
    print("  • 'generate 3 billing requests and auto-solve them'")
    print("  • 'show me recent tickets'")
    print("  • 'solve all open tickets'")
    print("  • 'how's everything going?'")
    print("  • 'pause my AI for a bit'")
    print()
    print("  Type 'quit' or 'exit' to stop.")
    print("  Type 'mode' to see current mode.")
    print("  Type 'functions' to see available functions.")
    print()
    print(f"  Company: {TEST_COMPANY_ID}")
    print(f"  Session: {TEST_SESSION_ID}")
    print(f"  User:    {TEST_USER_ID}")
    print()
    print("=" * 70 + "\n")


def print_response(result: Dict[str, Any]):
    """Pretty-print Jarvis's response."""
    print()
    print(f"  🤖 Jarvis: {result.get('response', 'No response')}")
    print()

    # Show metadata
    mode = result.get("mode", "unknown")
    func = result.get("function_called")
    safety = result.get("safety_status")

    meta_parts = []
    if mode:
        meta_parts.append(f"mode={mode}")
    if func:
        meta_parts.append(f"function={func}")
    if safety:
        meta_parts.append(f"safety={safety}")

    latency = result.get("latency_ms", 0)
    meta_parts.append(f"latency={latency:.0f}ms")

    if meta_parts:
        print(f"  📊 {', '.join(meta_parts)}")

    exec_result = result.get("execution_result")
    if exec_result and isinstance(exec_result, dict):
        data = exec_result.get("data", {})
        if data:
            # Show key data points
            for key in ["ticket_id", "tickets_created", "generated_count",
                         "solved_count", "variant_tier", "quality_score"]:
                if key in data:
                    print(f"  📋 {key}: {data[key]}")

    print()


async def run_manual_test():
    """Run the manual test loop."""
    print_header()

    # Import the orchestrator
    try:
        from app.services.jarvis_orchestrator import process_message, load_context, decide_mode
        from app.services.jarvis_function_registry import get_function_names, get_function_definitions
        from app.services.jarvis_safety_gate import clear_all_pending
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        print("  Make sure you're running from the parwa/backend directory")
        print("  and the virtual environment is activated.")
        return

    # We need a mock DB for standalone testing
    # In production, this would be a real SQLAlchemy session
    mock_db = None

    print("  ⚠️  Note: This test uses simulated responses since we don't have")
    print("  a live database connection. For full testing with a real DB,")
    print("  start the FastAPI server and use the HTTP API.\n")

    # Simulate the conversation loop
    conversation_history = []
    current_mode = "command"

    while True:
        try:
            user_input = input("  👤 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Bye! 👋\n")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "bye"):
            print("\n  Bye! 👋\n")
            break

        if user_input.lower() == "mode":
            print(f"\n  Current mode: {current_mode}\n")
            continue

        if user_input.lower() == "functions":
            names = get_function_names(mode=current_mode, tier="parwa")
            print(f"\n  Available functions ({len(names)}):")
            for i, name in enumerate(names, 1):
                print(f"    {i}. {name}")
            print()
            continue

        # Process through the orchestrator
        # Since we don't have a real DB, we simulate the response
        try:
            # Try with real orchestrator if DB is available
            result = await _simulate_jarvis_response(
                user_input=user_input,
                conversation_history=conversation_history,
                mode=current_mode,
            )

            print_response(result)

            # Update history
            conversation_history.append({"role": "user", "content": user_input})
            conversation_history.append({"role": "assistant", "content": result.get("response", "")})

        except Exception as e:
            print(f"\n  ❌ Error: {e}\n")


async def _simulate_jarvis_response(
    user_input: str,
    conversation_history: list,
    mode: str,
) -> Dict[str, Any]:
    """Simulate a Jarvis response for manual testing without a DB.

    This provides realistic-looking responses so you can see how Jarvis
    would behave, without needing a running database.
    """
    from app.services.jarvis_function_registry import get_function_metadata

    input_lower = user_input.lower()

    # ── Create ticket ──
    if any(kw in input_lower for kw in ["create ticket", "new ticket", "open ticket", "log a ticket", "report an issue"]):
        ticket_id = f"tkt-{uuid.uuid4().hex[:8]}"
        subject = "Customer support request"
        # Try to extract a subject from the message
        for prefix in ["about ", "for ", "regarding "]:
            if prefix in input_lower:
                subject = input_lower.split(prefix, 1)[1].strip().title()
                break

        return {
            "response": (
                f"Done! I've created ticket {ticket_id} for '{subject}'. "
                f"It's set to medium priority and the variant pipeline will pick it up. "
                f"Want me to solve it right away, or leave it in the queue?"
            ),
            "mode": "command",
            "function_called": "create_ticket",
            "safety_status": "approved",
            "execution_result": {
                "success": True,
                "data": {"ticket_id": ticket_id, "subject": subject, "status": "open"},
            },
            "latency_ms": 245,
            "model": "simulated",
            "tokens_used": 0,
        }

    # ── Generate fake requests ──
    if any(kw in input_lower for kw in ["generate fake", "fake request", "test data", "demo data", "simulate request"]):
        count = 5
        for word in user_input.split():
            if word.isdigit():
                count = min(25, max(1, int(word)))

        auto_solve = "auto-solve" in input_lower or "and solve" in input_lower

        ticket_ids = [f"tkt-{uuid.uuid4().hex[:6]}" for _ in range(count)]

        if auto_solve:
            return {
                "response": (
                    f"I generated {count} fake customer requests and created tickets for them. "
                    f"I also ran them through the variant pipeline — they've all been resolved with AI responses. "
                    f"Quality scores ranged from 0.78 to 0.94 across different categories. "
                    f"Want to see the details of any specific ticket?"
                ),
                "mode": "command",
                "function_called": "generate_fake_requests",
                "safety_status": "approved",
                "execution_result": {
                    "success": True,
                    "data": {
                        "generated_count": count,
                        "tickets_created": count,
                        "auto_solved": count,
                        "tickets": [
                            {"ticket_id": tid, "subject": f"Fake request #{i+1}"}
                            for i, tid in enumerate(ticket_ids)
                        ],
                    },
                },
                "latency_ms": 1850,
                "model": "simulated",
                "tokens_used": 0,
            }
        else:
            return {
                "response": (
                    f"I generated {count} fake customer requests and created tickets for them. "
                    f"They're all sitting in the queue as open tickets, ready for the variant pipeline to pick up. "
                    f"Want me to solve them all, or would you like to pick specific ones?"
                ),
                "mode": "command",
                "function_called": "generate_fake_requests",
                "safety_status": "approved",
                "execution_result": {
                    "success": True,
                    "data": {
                        "generated_count": count,
                        "tickets_created": count,
                        "auto_solved": None,
                        "tickets": [
                            {"ticket_id": tid, "subject": f"Fake request #{i+1}"}
                            for i, tid in enumerate(ticket_ids)
                        ],
                    },
                },
                "latency_ms": 680,
                "model": "simulated",
                "tokens_used": 0,
            }

    # ── List recent tickets ──
    if any(kw in input_lower for kw in ["recent ticket", "show ticket", "list ticket", "open ticket", "ticket queue"]):
        return {
            "response": (
                "Here are your recent tickets (3 open, 2 in_progress, 5 resolved). "
                "The open ones include a billing question and a tech support issue. "
                "Want me to solve any of them, or do you need details on a specific one?"
            ),
            "mode": "command",
            "function_called": "list_recent_tickets",
            "safety_status": "approved",
            "execution_result": {
                "success": True,
                "data": {
                    "total_returned": 10,
                    "status_summary": {"open": 3, "in_progress": 2, "resolved": 5},
                },
            },
            "latency_ms": 120,
            "model": "simulated",
            "tokens_used": 0,
        }

    # ── Solve ticket ──
    if any(kw in input_lower for kw in ["solve ticket", "resolve ticket", "handle ticket"]):
        return {
            "response": (
                "I'll route this ticket through the variant pipeline for AI solving. "
                "The AI will generate a response to resolve the customer's issue. Shall I go ahead?"
            ),
            "mode": "command",
            "function_called": "solve_ticket",
            "safety_status": "needs_confirmation",
            "execution_result": None,
            "latency_ms": 89,
            "model": "simulated",
            "tokens_used": 0,
        }

    # ── Batch solve ──
    if any(kw in input_lower for kw in ["solve all", "batch solve", "clear queue", "resolve all"]):
        return {
            "response": (
                "I'll solve up to 10 open tickets through the variant pipeline. "
                "Each one will get an AI-generated response. Want me to proceed?"
            ),
            "mode": "command",
            "function_called": "batch_solve_tickets",
            "safety_status": "needs_confirmation",
            "execution_result": None,
            "latency_ms": 95,
            "model": "simulated",
            "tokens_used": 0,
        }

    # ── System health ──
    if any(kw in input_lower for kw in ["how's everything", "system health", "how are things", "status"]):
        return {
            "response": (
                "Things are looking good! System is healthy, you've had 47 tickets today, "
                "AI quality is at 94%, and agent utilization is at 72%. "
                "Anything specific you want to check?"
            ),
            "mode": "command",
            "function_called": "check_system_health",
            "safety_status": "approved",
            "execution_result": {
                "success": True,
                "data": {
                    "system_health": "healthy",
                    "tickets_today": 47,
                    "quality_score": 0.94,
                    "agent_utilization": "72%",
                },
            },
            "latency_ms": 67,
            "model": "simulated",
            "tokens_used": 0,
        }

    # ── Pause AI ──
    if any(kw in input_lower for kw in ["pause ai", "stop ai", "pause everything"]):
        return {
            "response": (
                "I'll pause all AI agents for you. They'll stop handling tickets "
                "until you tell me to resume. Shall I go ahead?"
            ),
            "mode": "command",
            "function_called": "pause_all_ai",
            "safety_status": "needs_confirmation",
            "execution_result": None,
            "latency_ms": 78,
            "model": "simulated",
            "tokens_used": 0,
        }

    # ── Confirmation responses ──
    if any(kw in input_lower for kw in ["yes", "go ahead", "confirm", "sure", "do it", "proceed"]):
        # If there was a pending confirmation, we'd execute now
        return {
            "response": "Done! The action has been executed. Anything else you need?",
            "mode": "command",
            "function_called": None,
            "safety_status": "approved",
            "execution_result": {"success": True, "data": {}},
            "latency_ms": 150,
            "model": "simulated",
            "tokens_used": 0,
        }

    # ── Default conversational response ──
    return {
        "response": (
            "Hey! I can help you manage your support operations. "
            "You can ask me to create tickets, generate test data, solve tickets "
            "through the variant pipeline, check system health, or pretty much "
            "anything else related to your support platform. What would you like to do?"
        ),
        "mode": "command",
        "function_called": None,
        "safety_status": None,
        "execution_result": None,
        "latency_ms": 200,
        "model": "simulated",
        "tokens_used": 0,
    }


if __name__ == "__main__":
    asyncio.run(run_manual_test())
