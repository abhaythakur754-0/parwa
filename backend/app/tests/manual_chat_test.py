"""
PARWA Jarvis Manual Chat Test — Talk to Jarvis and see how it reacts

This script simulates a real user chatting with Jarvis through the
orchestrator. It tests various scenarios:
  1. Simple question → conversational response
  2. Action request → safety gate → confirmation/approval
  3. Agentic vs command mode
  4. Conversational feel

Run with: python -m app.tests.manual_chat_test
"""

import asyncio
import json
import sys
import os

# Ensure we can import from the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class MockDB:
    """Mock database that returns safe defaults."""
    def query(self, *args, **kwargs):
        return self
    
    def filter(self, *args, **kwargs):
        return self
    
    def first(self):
        return None
    
    def all(self):
        return []
    
    def order_by(self, *args, **kwargs):
        return self
    
    def limit(self, n):
        return self
    
    def offset(self, n):
        return self
    
    def count(self):
        return 0
    
    def add(self, obj):
        pass
    
    def flush(self):
        pass
    
    def commit(self):
        pass
    
    def desc(self, *args):
        return self


async def chat_test():
    """Run manual chat tests with Jarvis."""
    from app.services.jarvis_orchestrator import process_message
    from app.services.jarvis_safety_gate import clear_all_pending, get_pending_status
    from app.services.jarvis_function_registry import get_function_names
    
    db = MockDB()
    company_id = "test_company_demo"
    session_id = "test_session_demo"
    user_id = "test_user_demo"
    
    # Clear any pending confirmations
    clear_all_pending(company_id, session_id)
    
    print("=" * 70)
    print("  JARVIS CHAT TEST — Talking to Jarvis like a real client")
    print("=" * 70)
    print()
    
    # Show available functions
    funcs = get_function_names(mode="command", tier="parwa")
    print(f"Available functions (command mode): {len(funcs)}")
    print(f"Functions: {', '.join(funcs[:5])}... and {len(funcs) - 5} more")
    print()
    
    # Test scenarios
    scenarios = [
        ("how's everything going?", "Simple status check — should use check_system_health"),
        ("pause my AI", "Action request — should need confirmation"),
        ("yes go ahead", "Confirming pause — should approve"),
        ("show me my tickets", "Query — should get ticket stats"),
        ("I need to refund a customer $50", "Monetary action — should need approval"),
        ("ok sure", "Vague response — should still need approval"),
        ("yes confirm the refund", "Explicit confirm — should approve"),
    ]
    
    for i, (message, description) in enumerate(scenarios, 1):
        print(f"─── Scenario {i}: {description} ───")
        print(f"👤 Client: {message}")
        
        result = await process_message(
            db=db,
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            user_message=message,
        )
        
        response = result.get("response", "")
        mode = result.get("mode", "?")
        func = result.get("function_called")
        safety = result.get("safety_status")
        latency = result.get("latency_ms", 0)
        
        print(f"🤖 Jarvis: {response}")
        print(f"   Mode: {mode} | Function: {func or 'none'} | Safety: {safety or 'n/a'} | Latency: {latency:.0f}ms")
        
        # Check pending status
        pending = get_pending_status(company_id, session_id)
        if pending:
            print(f"   ⏳ Pending: {pending['function_name']} (safety: {pending['safety_level']})")
        else:
            print(f"   ⏳ No pending confirmations")
        print()
    
    # Test agentic mode
    print("─── Agentic Mode Test ───")
    from app.services.jarvis_orchestrator import decide_mode
    
    agentic_context = {"session": {"type": "customer_care", "mode": "customer_care"}}
    command_context = {"session": {"type": "onboarding", "mode": "onboarding"}}
    
    print(f"Customer care session → mode: {decide_mode(agentic_context)}")
    print(f"Onboarding session → mode: {decide_mode(command_context)}")
    
    agentic_funcs = get_function_names(mode="agentic", tier="parwa")
    command_funcs = get_function_names(mode="command", tier="parwa")
    print(f"Agentic functions: {agentic_funcs}")
    print(f"Command functions: {len(command_funcs)} total")
    print()
    
    # Test safety level checks
    print("─── Safety Level Summary ───")
    from app.services.jarvis_function_registry import get_function_count_by_safety
    counts = get_function_count_by_safety()
    for level, count in counts.items():
        print(f"  {level}: {count} functions")
    print()
    
    print("=" * 70)
    print("  CHAT TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(chat_test())
