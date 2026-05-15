"""
PARWA Jarvis ZAI SDK Client

The LLM brain behind Jarvis's multi-agent command layer.
Uses the ZAI SDK (z-ai-web-dev-sdk) for all LLM calls instead of
raw HTTP requests. This is how Jarvis THINKS.

Architecture:
  ZAIClient is a singleton that wraps the z-ai-web-dev-sdk.
  All agent nodes call ZAIClient.chat() to reason about what to do.

  Example flow:
    EscalationAgent gets a "ticket_volume_spike" alert
      → calls ZAIClient.chat("Given this spike of 3x normal volume...")
      → LLM responds with structured action plan
      → Agent executes the plan

  The client handles:
    - SDK initialization (lazy, thread-safe)
    - Retry logic (3 attempts with exponential backoff)
    - Fallback to rule-based decisions if SDK fails (BC-008)
    - Token tracking and cost awareness
    - System prompt management per agent type

BC-008: Never crash — if ZAI SDK fails, fall back to rule-based logic.
BC-012: All timestamps UTC.
"""

import json
import logging
import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("jarvis_zai_client")


# ══════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS PER AGENT TYPE
# ══════════════════════════════════════════════════════════════════

AGENT_SYSTEM_PROMPTS = {
    "command_router": (
        "You are Jarvis, the AI command router for PARWA customer care platform. "
        "Your job is to analyze awareness alerts and decide which specialized agent "
        "should handle the situation. You are like a senior employee who notices "
        "problems and delegates them to the right specialist.\n\n"
        "Available agents:\n"
        "  - escalation_agent: For critical issues needing human intervention\n"
        "  - sla_protection_agent: For SLA deadline risks and breaches\n"
        "  - quality_recovery_agent: For quality score drops and drift\n"
        "  - reassignment_agent: For ticket reassignment and load balancing\n"
        "  - notification_agent: For proactive user notifications\n"
        "  - pipeline_query_agent: For querying pipeline state (quality scores, volumes, agent status)\n"
        "  - no_action: When the alert doesn't require automated action\n\n"
        "Respond in JSON format:\n"
        '{"agent": "agent_name", "reasoning": "why", "urgency": "low|medium|high|critical", '
        '"parameters": {}}'
    ),

    "escalation_agent": (
        "You are Jarvis's Escalation Agent. You handle situations where tickets "
        "or issues need to be escalated to human agents. You decide:\n"
        "  - Which tickets to escalate\n"
        "  - Who to escalate to (tier 1, tier 2, manager)\n"
        "  - What context to include\n"
        "  - Whether to escalate all at once or gradually\n\n"
        "Respond in JSON format:\n"
        '{"action": "escalate", "scope": "all_urgent|specific_tickets", '
        '"escalation_tier": "tier1|tier2|manager", "ticket_ids": [], '
        '"reason": "why escalating", "context_summary": "brief summary"}'
    ),

    "sla_protection_agent": (
        "You are Jarvis's SLA Protection Agent. You prevent SLA breaches by:\n"
        "  - Identifying at-risk tickets before they breach\n"
        "  - Prioritizing tickets closest to SLA deadline\n"
        "  - Suggesting auto-responses for simple cases\n"
        "  - Requesting SLA extensions when appropriate\n\n"
        "Respond in JSON format:\n"
        '{"action": "protect_sla", "at_risk_count": N, "strategy": "prioritize|auto_respond|extend", '
        '"ticket_ids": [], "estimated_breach_count": N, "recommendation": "what to do"}'
    ),

    "quality_recovery_agent": (
        "You are Jarvis's Quality Recovery Agent. You handle quality drops by:\n"
        "  - Identifying which variant/agent is producing low quality\n"
        "  - Suggesting technique changes (e.g., switch from CoT to ReAct)\n"
        "  - Recommending retraining triggers\n"
        "  - Adjusting confidence thresholds temporarily\n\n"
        "Respond in JSON format:\n"
        '{"action": "recover_quality", "strategy": "switch_technique|retrain|adjust_threshold", '
        '"affected_agents": [], "current_score": X, "target_score": Y, '
        '"steps": ["step1", "step2"]}'
    ),

    "reassignment_agent": (
        "You are Jarvis's Reassignment Agent. You handle ticket load balancing by:\n"
        "  - Identifying overloaded agents/variants\n"
        "  - Moving tickets to underutilized agents\n"
        "  - Suggesting variant tier upgrades when capacity is exhausted\n"
        "  - Queueing overflow tickets intelligently\n\n"
        "Respond in JSON format:\n"
        '{"action": "reassign", "from_agent": "id", "to_agent": "id", '
        '"ticket_count": N, "reason": "why reassigning", "upgrade_suggested": false}'
    ),

    "notification_agent": (
        "You are Jarvis's Notification Agent. You craft and send proactive "
        "notifications to users about system events. You decide:\n"
        "  - What to notify about\n"
        "  - The right tone and urgency\n"
        "  - Which channel to use (chat, email, SMS)\n"
        "  - Whether action is required from the user\n\n"
        "Respond in JSON format:\n"
        '{"action": "notify", "channel": "chat|email|sms", "severity": "info|warning|critical", '
        '"title": "brief title", "message": "full message", "action_required": false, '
        '"action_url": "/path"}'
    ),

    "co_pilot": (
        "You are Jarvis's Co-Pilot mode. When a user asks an open question like "
        "'what should I do about the ticket spike?', you analyze the current "
        "awareness state and provide actionable suggestions.\n\n"
        "Respond in JSON format:\n"
        '{"suggestion": "what to do", "suggestion_type": "policy_reminder|action_suggestion|'
        'best_practice|warning", "suggested_command": "optional NL command", '
        '"confidence": 0.0-1.0, "reasoning": "why"}'
    ),

    "pipeline_query_agent": (
        "You are Jarvis's Pipeline Query Agent. You answer questions about the "
        "current state of the variant LangGraph pipeline. You have access to "
        "real-time pipeline data and awareness metrics.\n\n"
        "You can answer questions like:\n"
        "  - What's the current quality score?\n"
        "  - How many tickets are being processed?\n"
        "  - Is any agent overloaded?\n"
        "  - What's the drift status?\n"
        "  - Are there any emergency alerts?\n\n"
        "Respond in JSON format:\n"
        '{"query_type": "quality|volume|agent|drift|emergency|general", '
        '"answer": "concise answer", "reasoning": "how you arrived at the answer", '
        '"data_points": {"key": "value"}}'
    ),
}


class ZAIClient:
    """ZAI SDK client for Jarvis agent LLM calls.

    This is the brain behind every Jarvis agent decision. Instead of
    hardcoded rules, each agent asks the LLM "what should I do?" and
    gets a structured response.

    The client is lazy-initialized (only creates SDK instance when first
    needed) and thread-safe. If the SDK fails, each agent has a built-in
    rule-based fallback (BC-008).
    """

    _instance: Optional["ZAIClient"] = None
    _sdk = None
    _initialized: bool = False

    def __new__(cls) -> "ZAIClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_sdk(self) -> bool:
        """Lazy-initialize the ZAI SDK. Returns True if available."""
        if self._initialized:
            return self._sdk is not None

        try:
            import asyncio

            async def _init():
                from z_ai_web_dev_sdk import ZAI
                zai = await ZAI.create()
                return zai

            # Try to initialize the SDK
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, can't await here
                    # Will initialize on first chat call
                    self._sdk = None
                    self._initialized = True
                    return False
                self._sdk = loop.run_until_complete(_init())
            except RuntimeError:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, _init())
                    self._sdk = future.result(timeout=30)

            self._initialized = True
            logger.info("zai_sdk_initialized: success=%s", self._sdk is not None)
            return self._sdk is not None

        except Exception as e:
            logger.warning(
                "zai_sdk_init_failed: error=%s, will_use_fallback", str(e)[:200],
            )
            self._initialized = True
            self._sdk = None
            return False

    async def chat_async(
        self,
        agent_type: str,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Async: Ask the LLM a question from an agent and get a structured response.

        This is the primary method for agent reasoning. Each agent calls this
        with its specific agent_type to get the right system prompt.

        Args:
            agent_type: Which agent is asking (determines system prompt).
            user_message: The question/situation description.
            context: Additional context to include in the message.
            max_retries: Number of retry attempts.

        Returns:
            Dict with the LLM's structured response. Falls back to
            rule-based decision if LLM fails.
        """
        system_prompt = AGENT_SYSTEM_PROMPTS.get(
            agent_type, AGENT_SYSTEM_PROMPTS["command_router"],
        )

        # Build the full message with context
        full_message = user_message
        if context:
            full_message = f"Context:\n{json.dumps(context, default=str, indent=2)}\n\n{user_message}"

        for attempt in range(max_retries):
            try:
                # Try ZAI SDK
                if self._sdk is None:
                    self._ensure_sdk()

                if self._sdk is not None:
                    completion = await self._sdk.chat.completions.create(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": full_message},
                        ],
                        temperature=0.3,  # Low temperature for structured decisions
                        max_tokens=500,
                    )

                    content = completion.choices[0].message.content
                    if content:
                        return self._parse_llm_response(content, agent_type)

            except Exception as e:
                logger.warning(
                    "zai_chat_retry: agent=%s, attempt=%d/%d, error=%s",
                    agent_type, attempt + 1, max_retries, str(e)[:200],
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff

        # Fallback: rule-based decision
        logger.info("zai_chat_fallback: agent=%s, using_rule_based", agent_type)
        return self._rule_based_fallback(agent_type, user_message, context)

    def chat(
        self,
        agent_type: str,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for chat_async.

        Uses asyncio.run() or ThreadPoolExecutor depending on context.
        """
        try:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Already in async context, use thread pool
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(
                            asyncio.run,
                            self.chat_async(agent_type, user_message, context),
                        )
                        return future.result(timeout=30)
                else:
                    return loop.run_until_complete(
                        self.chat_async(agent_type, user_message, context),
                    )
            except RuntimeError:
                return asyncio.run(
                    self.chat_async(agent_type, user_message, context),
                )
        except Exception as e:
            logger.warning(
                "zai_chat_sync_failed: agent=%s, error=%s, using_fallback",
                agent_type, str(e)[:200],
            )
            return self._rule_based_fallback(agent_type, user_message, context)

    def _parse_llm_response(
        self, content: str, agent_type: str,
    ) -> Dict[str, Any]:
        """Parse the LLM response into a structured dict.

        The LLM should return JSON. If it doesn't, we try to extract
        JSON from the response, or fall back to a basic structure.
        """
        # Try direct JSON parse
        try:
            result = json.loads(content.strip())
            if isinstance(result, dict):
                result["_source"] = "zai_llm"
                result["_agent_type"] = agent_type
                result["_parsed_at"] = datetime.now(timezone.utc).isoformat()
                return result
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code block
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            try:
                result = json.loads(json_match.group(1).strip())
                if isinstance(result, dict):
                    result["_source"] = "zai_llm"
                    result["_agent_type"] = agent_type
                    result["_parsed_at"] = datetime.now(timezone.utc).isoformat()
                    return result
            except json.JSONDecodeError:
                pass

        # Try to find JSON-like content
        brace_match = re.search(r'\{[\s\S]*\}', content)
        if brace_match:
            try:
                result = json.loads(brace_match.group(0))
                if isinstance(result, dict):
                    result["_source"] = "zai_llm"
                    result["_agent_type"] = agent_type
                    result["_parsed_at"] = datetime.now(timezone.utc).isoformat()
                    return result
            except json.JSONDecodeError:
                pass

        # Last resort: wrap the text response
        logger.warning(
            "zai_response_unparseable: agent=%s, content_len=%d",
            agent_type, len(content),
        )
        return {
            "_source": "zai_llm_unparsed",
            "_agent_type": agent_type,
            "_parsed_at": datetime.now(timezone.utc).isoformat(),
            "raw_response": content[:500],
            "agent": agent_type.replace("_agent", ""),
            "reasoning": content[:200],
        }

    def _rule_based_fallback(
        self,
        agent_type: str,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Rule-based fallback when ZAI SDK is unavailable.

        Each agent type has hardcoded rules that approximate what the LLM
        would decide. This ensures Jarvis can ALWAYS make decisions, even
        without the LLM (BC-008).
        """
        ctx = context or {}
        now = datetime.now(timezone.utc).isoformat()

        if agent_type == "command_router":
            # Route based on alert type
            alert_type = ctx.get("alert_type", "")
            severity = ctx.get("severity", "info")

            routing_rules = {
                "ticket_volume_spike": "escalation_agent",
                "quality_drop": "quality_recovery_agent",
                "drift_detected": "quality_recovery_agent",
                "sla_breach_risk": "sla_protection_agent",
                "agent_pool_exhausted": "reassignment_agent",
                "emergency_state_change": "escalation_agent",
                "error_rate_high": "notification_agent",
                "quality_query": "pipeline_query_agent",
                "volume_query": "pipeline_query_agent",
                "agent_query": "pipeline_query_agent",
                "drift_query": "pipeline_query_agent",
                "system_status_query": "pipeline_query_agent",
            }

            agent = routing_rules.get(alert_type, "notification_agent")
            if severity in ("critical", "emergency"):
                if alert_type in ("quality_drop", "drift_detected"):
                    agent = "escalation_agent"

            return {
                "_source": "rule_based_fallback",
                "_agent_type": agent_type,
                "_parsed_at": now,
                "agent": agent,
                "reasoning": f"Rule-based routing: alert_type={alert_type}, severity={severity}",
                "urgency": severity if severity in ("low", "medium", "high", "critical") else "medium",
                "parameters": ctx,
            }

        elif agent_type == "escalation_agent":
            return {
                "_source": "rule_based_fallback",
                "_agent_type": agent_type,
                "_parsed_at": now,
                "action": "escalate",
                "scope": "all_urgent",
                "escalation_tier": "tier2",
                "ticket_ids": ctx.get("ticket_ids", []),
                "reason": f"Automated escalation due to {ctx.get('alert_type', 'system alert')}",
                "context_summary": ctx.get("message", "System alert triggered escalation"),
            }

        elif agent_type == "sla_protection_agent":
            return {
                "_source": "rule_based_fallback",
                "_agent_type": agent_type,
                "_parsed_at": now,
                "action": "protect_sla",
                "at_risk_count": ctx.get("at_risk_count", 0),
                "strategy": "prioritize",
                "ticket_ids": ctx.get("ticket_ids", []),
                "estimated_breach_count": ctx.get("at_risk_count", 0),
                "recommendation": "Prioritize at-risk tickets to prevent SLA breaches",
            }

        elif agent_type == "quality_recovery_agent":
            return {
                "_source": "rule_based_fallback",
                "_agent_type": agent_type,
                "_parsed_at": now,
                "action": "recover_quality",
                "strategy": "switch_technique",
                "affected_agents": ctx.get("affected_agents", []),
                "current_score": ctx.get("quality_score", 0.5),
                "target_score": 0.85,
                "steps": [
                    "Switch to ReAct technique for low-confidence queries",
                    "Enable MAKER validator with conservative mode",
                    "Trigger retraining if quality stays below 0.7 for 30 minutes",
                ],
            }

        elif agent_type == "reassignment_agent":
            return {
                "_source": "rule_based_fallback",
                "_agent_type": agent_type,
                "_parsed_at": now,
                "action": "reassign",
                "from_agent": ctx.get("overloaded_agent", "unknown"),
                "to_agent": ctx.get("available_agent", "any_available"),
                "ticket_count": ctx.get("overflow_count", 0),
                "reason": "Agent pool utilization exceeded threshold",
                "upgrade_suggested": ctx.get("utilization", 0) > 95,
            }

        elif agent_type == "notification_agent":
            return {
                "_source": "rule_based_fallback",
                "_agent_type": agent_type,
                "_parsed_at": now,
                "action": "notify",
                "channel": "chat",
                "severity": ctx.get("severity", "info"),
                "title": ctx.get("title", "System Notification"),
                "message": ctx.get("message", "Jarvis detected a system event."),
                "action_required": ctx.get("action_required", False),
                "action_url": "/dashboard",
            }

        elif agent_type == "co_pilot":
            return {
                "_source": "rule_based_fallback",
                "_agent_type": agent_type,
                "_parsed_at": now,
                "suggestion": f"Based on current system state, consider reviewing the {ctx.get('alert_type', 'system')} alert.",
                "suggestion_type": "action_suggestion",
                "suggested_command": "check system health",
                "confidence": 0.6,
                "reasoning": "Rule-based co-pilot suggestion based on alert context",
            }

        elif agent_type == "pipeline_query_agent":
            return {
                "_source": "rule_based_fallback",
                "_agent_type": agent_type,
                "_parsed_at": now,
                "query_type": "general",
                "action": "query_pipeline",
                "answer": (
                    f"System overview: Health={ctx.get('system_health', 'unknown')}, "
                    f"Quality={ctx.get('quality_score', 'N/A')}, "
                    f"Volume={ctx.get('ticket_volume_today', 0)}, "
                    f"Agents={ctx.get('active_agents', 0)}, "
                    f"Drift={ctx.get('drift_status', 'none')}."
                ),
                "reasoning": "Rule-based pipeline query response",
                "data_points": {
                    "system_health": ctx.get("system_health", "unknown"),
                    "quality_score": ctx.get("quality_score"),
                    "drift_status": ctx.get("drift_status", "none"),
                    "variant_tier": ctx.get("variant_tier", "mini_parwa"),
                },
            }

        else:
            return {
                "_source": "rule_based_fallback",
                "_agent_type": agent_type,
                "_parsed_at": now,
                "action": "no_action",
                "reasoning": f"Unknown agent type '{agent_type}', no action taken",
            }


# Singleton accessor
def get_zai_client() -> ZAIClient:
    """Get the global ZAI client instance."""
    return ZAIClient()
