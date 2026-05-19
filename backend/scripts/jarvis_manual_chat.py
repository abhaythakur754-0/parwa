#!/usr/bin/env python3
"""
PARWA Jarvis Manual Chat Test — Chat with Jarvis like a real client

This script lets you type natural messages to Jarvis and see how it responds.
It simulates the FULL Jarvis pipeline:
  1. User types a natural message (e.g., "show me my transaction history")
  2. Message is sent to LLM with function definitions as tools
  3. LLM picks the right function (or just chats)
  4. Safety gate checks the function call
  5. Function is executed (simulated with mock data)
  6. Result is fed back to LLM for a natural conversational response

Usage:
  cd backend && python scripts/jarvis_manual_chat.py

Or import:
  from scripts.jarvis_manual_chat import JarvisChatTester
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import Jarvis modules
from app.services.jarvis_function_registry import (
    FUNCTION_REGISTRY,
    get_function_definitions,
    get_function_names,
    get_safety_level,
    SAFETY_NONE,
    SAFETY_CONFIRMATION,
    SAFETY_APPROVAL,
)
from app.services.jarvis_safety_gate import (
    check_safety,
    SafetyCheckResult,
    force_approve,
    clear_all_pending,
)
from app.services.jarvis_orchestrator import (
    build_system_prompt,
    decide_mode,
    execute_function,
)
from app.services.fake_request_generator import generate_fake_requests


# ══════════════════════════════════════════════════════════════════
# MOCK CONTEXT FOR TESTING
# ══════════════════════════════════════════════════════════════════

MOCK_COMPANY_ID = "test-company-001"
MOCK_SESSION_ID = "test-session-001"
MOCK_USER_ID = "test-user-001"

MOCK_AWARENESS = {
    "system_health": "healthy",
    "ticket_volume_today": 47,
    "agent_pool_utilization": "72%",
    "quality_score": "94%",
    "drift_score": 0.03,
    "active_alerts_count": 2,
    "current_plan": "Parwa Pro",
    "plan_usage_today": "68%",
    "subscription_status": "active",
}

MOCK_CONTEXT = {
    "company_id": MOCK_COMPANY_ID,
    "session_id": MOCK_SESSION_ID,
    "session": {
        "id": MOCK_SESSION_ID,
        "type": "admin",
        "variant_tier": "parwa",
        "industry": "ecommerce",
        "mode": "customer_care",
    },
    "awareness": MOCK_AWARENESS,
    "history": [],
    "tier": "parwa",
}

# Simulated recent tickets
MOCK_RECENT_TICKETS = [
    {"id": "TKT-001", "subject": "App keeps crashing on startup", "status": "open", "priority": "high", "category": "tech_support", "customer": "Sarah Johnson"},
    {"id": "TKT-002", "subject": "Charged twice for this month", "status": "in_progress", "priority": "high", "category": "billing", "customer": "Mike Chen"},
    {"id": "TKT-003", "subject": "Order hasn't arrived after 2 weeks", "status": "open", "priority": "high", "category": "order_tracking", "customer": "Priya Sharma"},
    {"id": "TKT-004", "subject": "Want to return a damaged product", "status": "open", "priority": "high", "category": "returns_refunds", "customer": "David Kim"},
    {"id": "TKT-005", "subject": "Dashboard loading very slowly", "status": "resolved", "priority": "medium", "category": "tech_support", "customer": "Emma Wilson"},
    {"id": "TKT-006", "subject": "Need to update payment method", "status": "open", "priority": "medium", "category": "billing", "customer": "Carlos Rodriguez"},
    {"id": "TKT-007", "subject": "Wrong item delivered, need exchange", "status": "in_progress", "priority": "high", "category": "delivery_issues", "customer": "Aisha Patel"},
    {"id": "TKT-008", "subject": "Terrible customer service experience", "status": "open", "priority": "high", "category": "complaint", "customer": "Tom Anderson"},
    {"id": "TKT-009", "subject": "Request for WhatsApp integration", "status": "open", "priority": "medium", "category": "feature_request", "customer": "Lisa Wang"},
    {"id": "TKT-010", "subject": "Package delivered to wrong address", "status": "open", "priority": "critical", "category": "delivery_issues", "customer": "James Brown"},
]


# ══════════════════════════════════════════════════════════════════
# LLM CALLER USING z-ai-web-dev-sdk PATTERN
# ══════════════════════════════════════════════════════════════════


async def call_llm(
    system_prompt: str,
    messages: List[Dict[str, str]],
    function_defs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Call LLM with function calling using OpenAI-compatible API.
    
    Tries:
      1. ZAI gateway (if ZAI_API_KEY is set)
      2. OpenAI-compatible API (if OPENAI_API_KEY is set)
      3. Pattern-matching fallback (no LLM available)
    """
    # Try OpenAI-compatible API
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    model = os.environ.get("JARVIS_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    
    # Also check for ZAI key
    zai_key = os.environ.get("ZAI_API_KEY", "")
    
    if api_key or zai_key:
        try:
            import httpx
            
            # Use whichever key is available
            use_key = zai_key if zai_key else api_key
            use_url = base_url if api_key else os.environ.get("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {use_key}",
            }
            
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "max_tokens": 800,
                "temperature": 0.7,
            }
            
            if function_defs:
                # Convert our function defs to OpenAI tools format
                tools = []
                for func in function_defs:
                    tool = {
                        "type": "function",
                        "function": {
                            "name": func["name"],
                            "description": func["description"],
                            "parameters": func["parameters"],
                        }
                    }
                    tools.append(tool)
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            
            async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=60.0)) as client:
                response = await client.post(
                    f"{use_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
            
            if response.status_code != 200:
                print(f"  ⚠ LLM API returned status {response.status_code}: {response.text[:200]}")
                return _fallback_llm_response(messages, function_defs)
            
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return _fallback_llm_response(messages, function_defs)
            
            choice = choices[0]
            msg = choice.get("message", {})
            content = msg.get("content", "")
            
            # Check for tool calls
            function_call = None
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                tc = tool_calls[0]
                func = tc.get("function", {})
                func_name = func.get("name", "")
                func_args = func.get("arguments", "{}")
                if isinstance(func_args, str):
                    try:
                        func_args = json.loads(func_args)
                    except json.JSONDecodeError:
                        func_args = {}
                function_call = {
                    "name": func_name,
                    "arguments": func_args,
                }
            
            return {
                "content": content,
                "function_call": function_call,
                "model": data.get("model", model),
                "tokens_used": data.get("usage", {}).get("total_tokens", 0),
            }
            
        except Exception as e:
            print(f"  ⚠ LLM API error: {e}")
            return _fallback_llm_response(messages, function_defs)
    
    # No API key — use pattern matching fallback
    return _fallback_llm_response(messages, function_defs)


def _fallback_llm_response(
    messages: List[Dict[str, str]],
    function_defs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Pattern-matching fallback when no LLM API is available.
    
    This simulates what the LLM would do — it reads the user's message,
    tries to match it to a function, and generates a plausible response.
    """
    if not messages:
        return {"content": "Hey! I'm Jarvis. How can I help you today?", "function_call": None, "model": "fallback", "tokens_used": 0}
    
    last_msg = messages[-1].get("content", "").lower()
    
    # Pattern matching for common intents
    function_call = None
    response_text = ""
    
    if any(kw in last_msg for kw in ["health", "how is", "how's", "status", "system"]):
        function_call = {"name": "check_system_health", "arguments": {}}
        response_text = "Let me check on that for you."
    elif any(kw in last_msg for kw in ["transaction", "history", "recent ticket", "show all", "list ticket", "show ticket", "open ticket"]):
        function_call = {"name": "list_recent_tickets", "arguments": {"limit": 10, "status": "all"}}
        response_text = "Let me pull that up for you."
    elif any(kw in last_msg for kw in ["upgrade", "plan", "subscription", "billing info"]):
        function_call = {"name": "get_subscription_info", "arguments": {}}
        response_text = "Let me check your subscription details."
    elif any(kw in last_msg for kw in ["pause ai", "stop ai", "turn off ai"]):
        function_call = {"name": "pause_all_ai", "arguments": {"reason": "User requested via chat"}}
        response_text = "I'll pause the AI agents for you."
    elif any(kw in last_msg for kw in ["resume ai", "start ai", "turn on ai"]):
        function_call = {"name": "resume_all_ai", "arguments": {}}
        response_text = "I'll get the AI agents back online."
    elif any(kw in last_msg for kw in ["ticket stat", "how many ticket", "ticket volume", "ticket count"]):
        function_call = {"name": "get_ticket_stats", "arguments": {"time_range": "today"}}
        response_text = "Let me get the ticket numbers for you."
    elif any(kw in last_msg for kw in ["error", "bug", "issue", "wrong", "broken"]):
        function_call = {"name": "show_recent_errors", "arguments": {"count": 5}}
        response_text = "Let me check for any recent errors."
    elif any(kw in last_msg for kw in ["refund", "money back"]):
        function_call = {"name": "process_refund", "arguments": {"customer_id": "auto", "amount": 0, "reason": "Customer request"}}
        response_text = "I can help process a refund."
    elif any(kw in last_msg for kw in ["escalat", "urgent", "critical"]):
        function_call = {"name": "escalate_urgent_tickets", "arguments": {"priority": "urgent"}}
        response_text = "I'll escalate those urgent tickets right away."
    elif any(kw in last_msg for kw in ["agent", "capacity", "utilization"]):
        function_call = {"name": "get_agent_status", "arguments": {}}
        response_text = "Let me check on the agents."
    elif any(kw in last_msg for kw in ["performance", "metric", "report", "analytics"]):
        function_call = {"name": "get_performance_metrics", "arguments": {}}
        response_text = "Let me pull up the performance data."
    elif any(kw in last_msg for kw in ["create ticket", "new ticket", "open ticket"]):
        function_call = {"name": "create_ticket", "arguments": {"subject": "New support request", "message": "Customer needs help", "priority": "medium"}}
        response_text = "I'll create a ticket for that."
    elif any(kw in last_msg for kw in ["fake request", "generate request", "test request", "simulate"]):
        function_call = {"name": "generate_fake_requests", "arguments": {"count": 5, "category": "mixed"}}
        response_text = "I'll generate some test requests for you."
    elif any(kw in last_msg for kw in ["solve", "resolve", "batch"]):
        function_call = {"name": "batch_solve_tickets", "arguments": {"max_tickets": 5}}
        response_text = "I'll have the AI solve those tickets."
    elif any(kw in last_msg for kw in ["emergency", "shutdown", "kill switch"]):
        function_call = {"name": "emergency_stop", "arguments": {"reason": "User requested emergency stop"}}
        response_text = "Emergency stop requested."
    elif any(kw in last_msg for kw in ["integration", "channel", "connect"]):
        function_call = {"name": "list_integrations", "arguments": {}}
        response_text = "Let me check your integrations."
    elif any(kw in last_msg for kw in ["knowledge", "article", "faq"]):
        function_call = {"name": "search_knowledge_base", "arguments": {"query": last_msg}}
        response_text = "Let me search the knowledge base."
    else:
        response_text = "I'm here to help! I can check system health, show tickets, manage AI agents, handle billing, and more. What would you like to do?"
    
    return {
        "content": response_text,
        "function_call": function_call,
        "model": "fallback-pattern",
        "tokens_used": 0,
    }


# ══════════════════════════════════════════════════════════════════
# MOCK EXECUTOR (for testing without a real database)
# ══════════════════════════════════════════════════════════════════


def mock_execute_function(function_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a function with mock data (no real database needed)."""
    
    if function_name == "check_system_health":
        return {
            "success": True,
            "data": MOCK_AWARENESS,
            "message": (
                f"System is {MOCK_AWARENESS['system_health']}. You've had "
                f"{MOCK_AWARENESS['ticket_volume_today']} tickets today, AI quality is at "
                f"{MOCK_AWARENESS['quality_score']}, and agent utilization is "
                f"{MOCK_AWARENESS['agent_pool_utilization']}."
            ),
        }
    
    elif function_name == "list_recent_tickets":
        limit = params.get("limit", 10)
        status_filter = params.get("status", "all")
        tickets = MOCK_RECENT_TICKETS[:limit]
        if status_filter != "all":
            tickets = [t for t in tickets if t["status"] == status_filter]
        ticket_list = "\n".join(
            f"  • {t['id']} | {t['status']:13} | {t['priority']:8} | {t['category']:16} | {t['subject']}"
            for t in tickets
        )
        return {
            "success": True,
            "data": {"tickets": tickets, "total": len(tickets)},
            "message": f"Here are your recent tickets ({len(tickets)} found):\n{ticket_list}",
        }
    
    elif function_name == "get_subscription_info":
        return {
            "success": True,
            "data": MOCK_AWARENESS,
            "message": (
                f"You're on the {MOCK_AWARENESS['current_plan']} plan. "
                f"Usage today: {MOCK_AWARENESS['plan_usage_today']}. "
                f"Subscription status: {MOCK_AWARENESS['subscription_status']}."
            ),
        }
    
    elif function_name == "get_ticket_stats":
        return {
            "success": True,
            "data": {
                "tickets_today": 47,
                "open": 12,
                "in_progress": 8,
                "resolved": 27,
                "avg_response_time": "3.2 min",
                "resolution_rate": "87%",
            },
            "message": (
                "You've had 47 tickets today — 12 open, 8 in progress, 27 resolved. "
                "Average response time is 3.2 min with an 87% resolution rate."
            ),
        }
    
    elif function_name == "pause_all_ai":
        return {
            "success": True,
            "data": {"ai_paused": True},
            "message": "All AI agents are now paused. They won't handle any tickets until you tell me to resume them.",
        }
    
    elif function_name == "resume_all_ai":
        return {
            "success": True,
            "data": {"ai_paused": False},
            "message": "AI agents are back online! They'll start handling tickets again.",
        }
    
    elif function_name == "show_recent_errors":
        return {
            "success": True,
            "data": {"errors": [
                {"type": "RedisTimeoutError", "component": "cache", "severity": "warning", "time": "2 min ago"},
                {"type": "SlackWebhookError", "component": "integration", "severity": "error", "time": "15 min ago"},
            ]},
            "message": "Found 2 recent errors. One Redis timeout (warning) and one Slack webhook failure (error).",
        }
    
    elif function_name == "escalate_urgent_tickets":
        return {
            "success": True,
            "data": {"escalated_count": 3},
            "message": "Done! Escalated 3 urgent-priority tickets to your human team.",
        }
    
    elif function_name == "get_agent_status":
        return {
            "success": True,
            "data": {"active_ai_agents": 5, "active_human_agents": 3, "utilization": "72%", "queue_depth": 4},
            "message": "You have 5 AI agents and 3 human agents active. Utilization is at 72% with 4 tickets in the queue.",
        }
    
    elif function_name == "get_performance_metrics":
        return {
            "success": True,
            "data": {
                "avg_response_time": "3.2 min",
                "resolution_rate": "87%",
                "csat": "4.2/5",
                "ai_accuracy": "94%",
                "sla_compliance": "98%",
            },
            "message": (
                "Performance looking solid — 3.2 min avg response, 87% resolution rate, "
                "4.2/5 CSAT, 94% AI accuracy, and 98% SLA compliance."
            ),
        }
    
    elif function_name == "process_refund":
        amount = params.get("amount", 0)
        return {
            "success": True,
            "data": {"refund_amount": amount, "status": "processed"},
            "message": f"Refund of ${amount} has been processed for the customer.",
        }
    
    elif function_name == "create_ticket":
        return {
            "success": True,
            "data": {"ticket_id": f"TKT-{uuid.uuid4().hex[:6].upper()}", "status": "open"},
            "message": f"Created a new ticket for '{params.get('subject', 'Support request')}'. It's been assigned to the AI variant pipeline.",
        }
    
    elif function_name == "list_integrations":
        return {
            "success": True,
            "data": {
                "integrations": [
                    {"name": "Email (Gmail)", "status": "active", "health": "healthy"},
                    {"name": "SMS (Twilio)", "status": "active", "health": "healthy"},
                    {"name": "Chat Widget", "status": "active", "health": "healthy"},
                    {"name": "Slack", "status": "inactive", "health": "error"},
                ]
            },
            "message": "You have 3 active integrations (Email, SMS, Chat Widget) and 1 inactive (Slack — error).",
        }
    
    elif function_name == "emergency_stop":
        return {
            "success": True,
            "data": {"ai_paused": True, "emergency": True},
            "message": "Emergency stop is active. ALL automated operations are paused. Nothing will run until you tell me to resume.",
        }
    
    elif function_name == "generate_fake_requests":
        count = params.get("count", 5)
        category = params.get("category", "mixed")
        requests = generate_fake_requests(count=count, category=category)
        request_list = "\n".join(
            f"  • {r['customer_name']} ({r['customer_email']}) — {r['subject']} [{r['priority']}]"
            for r in requests
        )
        return {
            "success": True,
            "data": {"requests": requests, "count": len(requests)},
            "message": f"Generated {len(requests)} fake customer requests:\n{request_list}",
        }
    
    elif function_name == "batch_solve_tickets":
        max_tickets = params.get("max_tickets", 5)
        open_tickets = [t for t in MOCK_RECENT_TICKETS if t["status"] == "open"][:max_tickets]
        return {
            "success": True,
            "data": {"solved_count": len(open_tickets), "tickets": open_tickets},
            "message": f"Solved {len(open_tickets)} open tickets through the AI variant pipeline. Responses have been generated.",
        }
    
    elif function_name == "search_knowledge_base":
        return {
            "success": True,
            "data": {"results": [
                {"title": "Getting Started Guide", "relevance": 0.92},
                {"title": "FAQ: Billing & Payments", "relevance": 0.78},
            ]},
            "message": "Found 2 articles matching your query. The most relevant is 'Getting Started Guide' (92% match).",
        }
    
    elif function_name == "solve_ticket":
        return {
            "success": True,
            "data": {"ticket_id": params.get("ticket_id"), "status": "resolved"},
            "message": f"Ticket {params.get('ticket_id', 'TKT-001')} has been solved by the AI variant. A response has been sent to the customer.",
        }
    
    else:
        return {
            "success": False,
            "data": {},
            "message": f"I don't know how to do '{function_name}' yet, but I'm learning!",
        }


# ══════════════════════════════════════════════════════════════════
# MAIN JARVIS CHAT TESTER
# ══════════════════════════════════════════════════════════════════


class JarvisChatTester:
    """Interactive Jarvis chat tester — type messages and see responses."""
    
    def __init__(self):
        self.conversation_history: List[Dict[str, str]] = []
        self.mode = "command"
        self.company_id = MOCK_COMPANY_ID
        self.session_id = MOCK_SESSION_ID
        self.user_id = MOCK_USER_ID
        self.pending_safety: Optional[Dict[str, Any]] = None
    
    async def process_message(self, user_message: str) -> str:
        """Full Jarvis pipeline — same as the real orchestrator."""
        
        # 1. Build context
        context = MOCK_CONTEXT.copy()
        context["history"] = self.conversation_history[-20:]
        
        # 2. Check for pending safety confirmation
        from app.services.jarvis_safety_gate import get_pending_status
        pending = get_pending_status(self.company_id, self.session_id)
        
        # 3. Build system prompt
        system_prompt = build_system_prompt(self.mode, context, pending)
        
        # 4. Get function definitions for this mode
        function_defs = get_function_definitions(mode=self.mode, tier="parwa")
        
        # 5. Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})
        
        # 6. Call LLM with function calling
        llm_result = await call_llm(system_prompt, self.conversation_history, function_defs)
        
        function_call = llm_result.get("function_call")
        content = llm_result.get("content", "")
        model_used = llm_result.get("model", "unknown")
        
        # 7. If LLM chose a function call
        if function_call:
            func_name = function_call.get("name", "")
            func_params = function_call.get("arguments", {})
            
            # 7a. Safety gate check
            safety = check_safety(
                company_id=self.company_id,
                session_id=self.session_id,
                function_name=func_name,
                function_params=func_params,
                user_message=user_message,
            )
            
            if safety.is_approved:
                # 7b. Execute function (mock)
                result = mock_execute_function(func_name, func_params)
                
                # 7c. Feed result back to LLM for natural response
                result_context = (
                    f"[Function '{func_name}' was executed. Result: {result.get('message', 'Done.')}]\n\n"
                    f"Now respond to the user naturally based on this result. "
                    f"Don't mention the function call — just tell them what happened."
                )
                
                self.conversation_history.append({"role": "assistant", "content": content})
                
                # Generate final conversational response
                final_result = await call_llm(
                    system_prompt,
                    self.conversation_history + [{"role": "system", "content": result_context}],
                    [],  # No functions for the follow-up
                )
                
                final_response = final_result.get("content", result.get("message", "Done!"))
                
                # If LLM didn't generate a good follow-up, use the executor message
                if not final_response or len(final_response) < 10:
                    final_response = result.get("message", "Done!")
                
                self.conversation_history.append({"role": "assistant", "content": final_response})
                
                return final_response, {
                    "function_called": func_name,
                    "safety_status": "approved",
                    "execution_result": result,
                    "model": model_used,
                }
            
            elif safety.needs_human_input:
                # Safety gate wants confirmation
                self.pending_safety = safety.to_dict()
                self.conversation_history.append({
                    "role": "assistant",
                    "content": safety.message,
                })
                return safety.message, {
                    "function_called": func_name,
                    "safety_status": safety.status,
                    "safety_level": safety.safety_level,
                    "model": model_used,
                }
            
            else:
                # Rejected
                self.conversation_history.append({
                    "role": "assistant",
                    "content": safety.message,
                })
                return safety.message, {
                    "function_called": func_name,
                    "safety_status": safety.status,
                    "model": model_used,
                }
        
        else:
            # No function call — just conversational response
            if not content:
                content = "I'm here to help! I can check system health, show tickets, manage AI agents, and more. What would you like to do?"
            
            self.conversation_history.append({"role": "assistant", "content": content})
            return content, {
                "function_called": None,
                "model": model_used,
            }
    
    async def chat_loop(self):
        """Interactive chat loop — type messages and see Jarvis respond."""
        
        print()
        print("═" * 70)
        print("  🤖 JARVIS CHAT — Manual Test")
        print("═" * 70)
        print()
        print("  Type natural messages to chat with Jarvis.")
        print("  Try things like:")
        print("    • 'show me my transaction history'")
        print("    • 'upgrade my plan' or 'what's my subscription?'")
        print("    • 'pause all AI'")
        print("    • 'show me recent tickets'")
        print("    • 'how's the system doing?'")
        print("    • 'escalate urgent tickets'")
        print("    • 'generate 5 fake requests'")
        print("    • 'batch solve open tickets'")
        print("    • 'emergency stop'")
        print()
        print("  Commands: 'quit' to exit, 'clear' to reset conversation")
        print("═" * 70)
        print()
        
        # Show available functions
        func_names = get_function_names(mode="command", tier="parwa")
        print(f"  📋 Available functions ({len(func_names)}): {', '.join(func_names[:8])}...")
        print()
        
        while True:
            try:
                user_input = input("  👤 You: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n  👋 Bye!")
                break
            
            if not user_input:
                continue
            
            if user_input.lower() == "quit":
                print("  👋 Bye!")
                break
            
            if user_input.lower() == "clear":
                self.conversation_history = []
                clear_all_pending(self.company_id, self.session_id)
                self.pending_safety = None
                print("  🔄 Conversation cleared.")
                continue
            
            # Process through Jarvis
            response, metadata = await self.process_message(user_input)
            
            # Show the result
            func_called = metadata.get("function_called")
            safety = metadata.get("safety_status")
            model = metadata.get("model", "unknown")
            
            print()
            print(f"  🤖 Jarvis: {response}")
            if func_called:
                print(f"     ─── [Function: {func_called} | Safety: {safety or 'N/A'} | Model: {model}]")
            print()
    
    async def run_test_suite(self):
        """Run a pre-defined test suite — no interactive input needed."""
        
        print()
        print("═" * 70)
        print("  🤖 JARVIS AUTOMATED TEST SUITE")
        print("═" * 70)
        print()
        
        test_cases = [
            ("show me my transaction history", "list_recent_tickets"),
            ("what's my subscription? upgrade my plan", "get_subscription_info"),
            ("how's the system doing?", "check_system_health"),
            ("pause all AI agents", "pause_all_ai"),
            ("yes", "confirm_pause"),
            ("show me recent tickets", "list_recent_tickets"),
            ("escalate urgent tickets", "escalate_urgent_tickets"),
            ("generate 5 fake requests", "generate_fake_requests"),
            ("batch solve open tickets", "batch_solve_tickets"),
            ("what are my integrations?", "list_integrations"),
            ("show me recent errors", "show_recent_errors"),
            ("what's the performance like?", "get_performance_metrics"),
        ]
        
        results = []
        
        for i, (message, expected_intent) in enumerate(test_cases, 1):
            print(f"  Test {i:2d}/{len(test_cases)}: \"{message}\"")
            
            response, metadata = await self.process_message(message)
            
            func_called = metadata.get("function_called")
            safety = metadata.get("safety_status")
            model = metadata.get("model", "unknown")
            
            # Check if the function matches the expected intent
            matched = False
            if expected_intent == "confirm_pause" and safety == "approved":
                matched = True
            elif func_called == expected_intent:
                matched = True
            elif func_called and expected_intent in func_called:
                matched = True
            
            status = "✅" if matched else "⚠️"
            
            print(f"    {status} Function: {func_called or 'none'} | Safety: {safety or 'N/A'} | Model: {model}")
            print(f"    Response: {response[:120]}{'...' if len(response) > 120 else ''}")
            print()
            
            results.append({
                "test": i,
                "message": message,
                "expected": expected_intent,
                "actual": func_called,
                "matched": matched,
                "safety": safety,
            })
        
        # Summary
        passed = sum(1 for r in results if r["matched"])
        total = len(results)
        print("═" * 70)
        print(f"  RESULTS: {passed}/{total} tests matched expected functions")
        print("═" * 70)
        print()
        
        for r in results:
            status = "✅" if r["matched"] else "⚠️"
            print(f"  {status} Test {r['test']}: '{r['message'][:40]}' → got '{r['actual']}', expected '{r['expected']}'")
        
        return results


# ══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════


async def main():
    """Run the Jarvis chat tester."""
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Run automated test suite
        tester = JarvisChatTester()
        await tester.run_test_suite()
    else:
        # Interactive chat
        tester = JarvisChatTester()
        await tester.chat_loop()


if __name__ == "__main__":
    asyncio.run(main())
