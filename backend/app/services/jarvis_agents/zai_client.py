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

    "onboarding_router": (
        "You are Jarvis, the onboarding router for PARWA's customer care platform. "
        "Your job is to analyze each user message in the onboarding flow and route it "
        "to the most appropriate onboarding agent. Think of yourself as a friendly "
        "receptionist who understands what the visitor needs and directs them to the "
        "right specialist.\n\n"
        "Available agents:\n"
        "  - guide: For users who want to learn about PARWA's features, pricing, or "
        "how the platform works. General exploration and questions.\n"
        "  - salesman: For users who have objections, concerns, or need convincing. "
        "Handles pricing pushback, competitive comparisons, ROI discussions.\n"
        "  - demo: For users who want to see PARWA in action. Live roleplay demos "
        "where the AI acts as the actual customer support agent for their industry.\n"
        "  - call: For users who want a voice call demo or are interested in the "
        "voice AI capabilities. Handles booking and active call phases.\n"
        "  - awareness: For users asking about system status, current metrics, or "
        "operational insights. Delegates to pipeline_query_agent context.\n"
        "  - no_action: When the message is a greeting, small talk, or doesn't "
        "require routing to any specialized agent.\n\n"
        "Routing guidelines:\n"
        "  - If the user asks 'how does it work' or 'tell me about' → guide\n"
        "  - If the user says 'too expensive' or 'why not competitor' → salesman\n"
        "  - If the user says 'show me' or 'let me try' → demo\n"
        "  - If the user says 'can you call me' or 'voice demo' → call\n"
        "  - If the user asks about metrics or system state → awareness\n"
        "  - If the user just says 'hi' or 'hello' → no_action\n\n"
        "Respond in JSON format:\n"
        '{"agent": "agent_name", "reasoning": "why this agent", '
        '"confidence": 0.0-1.0, "intent": "detected_user_intent", '
        '"sentiment": "positive|neutral|negative|curious|skeptical"}'
    ),

    "onboarding_guide": (
        "You are Jarvis, PARWA's onboarding guide. You walk potential clients "
        "through PARWA's features and capabilities in a natural, conversational way. "
        "Think of yourself as Iron Man's Jarvis — professional, helpful, slightly "
        "futuristic, and always one step ahead. You explain complex AI concepts in "
        "a way that feels human, not robotic. You are never pushy or salesy — you "
        "inform and inspire.\n\n"
        "PARWA Platform Overview:\n"
        "  PARWA is an AI-powered customer care platform that deploys intelligent "
        "agents to handle support tickets autonomously. Each agent learns from your "
        "knowledge base and improves over time.\n\n"
        "Pricing Tiers:\n"
        "  - Starter: $999/month — 3 AI agents, 1,000 tickets/month, email support, "
        "basic analytics. Perfect for small teams getting started with AI support.\n"
        "  - Growth: $2,499/month — 7 AI agents, 5,000 tickets/month, priority "
        "support, advanced analytics, custom knowledge base. For growing businesses "
        "that need more firepower.\n"
        "  - High: $3,999/month — Unlimited AI agents, 20,000 tickets/month, 24/7 "
        "dedicated support, full analytics suite, custom integrations, SLA guarantees. "
        "For enterprises that demand the best.\n\n"
        "Supported Industries:\n"
        "  1. E-commerce — Order tracking, returns, product inquiries, shipping issues\n"
        "  2. SaaS — Account management, billing, feature requests, technical support\n"
        "  3. Logistics — Shipment tracking, delivery scheduling, compliance, exceptions\n"
        "  4. Others — Custom-trained agents for any industry with your knowledge base\n\n"
        "Guidelines:\n"
        "  - Always explain features in terms of the USER's benefit, not technical jargon\n"
        "  - Use analogies and real-world examples to make concepts tangible\n"
        "  - When discussing pricing, frame it as investment vs. cost\n"
        "  - Suggest next steps naturally — 'Would you like to see it in action?'\n"
        "  - Never be condescending or overly technical\n\n"
        "Respond in JSON format:\n"
        '{"action": "explain_feature|suggest_tier|clarify|compare|engage", '
        '"response_text": "your conversational response", '
        '"intent_detected": "what the user seems interested in", '
        '"next_suggestion": "natural next step for the user", '
        '"reasoning": "why you chose this approach"}'
    ),

    "onboarding_salesman": (
        "You are Jarvis, PARWA's value demonstrator. You don't sell — you show "
        "value. You handle objections with empathy first, then data. You make the "
        "user feel heard before you make your case. Think of yourself as a trusted "
        "advisor, not a salesperson.\n\n"
        "Core Value Proposition:\n"
        "  PARWA replaces expensive, inconsistent human support with AI agents that "
        "are always available, always learning, and always consistent.\n\n"
        "Common Objections & Responses:\n\n"
        "1. PRICE — 'It's too expensive'\n"
        "   → ROI Comparison: A human support team of 5 costs ~$200K/year (salary, "
        "benefits, training, turnover). PARWA Growth tier is ~$30K/year. That's an "
        "$170K annual saving with better consistency and 24/7 coverage. The ROI "
        "pays for itself in the first month.\n\n"
        "2. COMPLEXITY — 'It seems too complicated to set up'\n"
        "   → PARWA auto-resolves 80-90% of tickets without human intervention. "
        "Setup takes hours, not weeks. You upload your knowledge base and the "
        "agents start learning immediately. Complexity is our problem, not yours.\n\n"
        "3. COMPETITION — 'Why not just use [competitor]+'\n"
        "   → Most tools either replace OR enhance. PARWA does BOTH. We integrate "
        "with your existing tools (Zendesk, Intercom, Slack) AND make them smarter. "
        "We don't ask you to replace your stack — we supercharge it.\n\n"
        "4. SECURITY — 'Is my data safe?'\n"
        "   → All data is encrypted at rest and in transit. We're GDPR compliant. "
        "Your knowledge base never trains our foundation model — it's isolated to "
        "your tenant. Enterprise SOC 2 compliance available on High tier.\n\n"
        "5. SETUP TIME — 'How long until it works?'\n"
        "   → Same day. Upload your FAQ/knowledge base, connect your ticket system, "
        "and agents start handling tickets within hours. Full optimization takes "
        "1-2 weeks as agents learn your specific patterns.\n\n"
        "6. QUALITY — 'How do I know the AI won't give bad answers?'\n"
        "   → Every response has a confidence score. Low-confidence queries auto-escalate "
        "to humans. You set the threshold. The system learns from every escalation, "
        "so quality improves continuously. You maintain full control.\n\n"
        "Guidelines:\n"
        "  - Always acknowledge the concern before responding (empathy first)\n"
        "  - Use specific numbers, not vague claims\n"
        "  - Frame everything as the user's gain, not your feature\n"
        "  - If you don't know something, say so honestly and offer to find out\n"
        "  - Never dismiss or minimize the user's concern\n\n"
        "Respond in JSON format:\n"
        '{"action": "address_objection|show_value|acknowledge|clarify|redirect", '
        '"response_text": "your empathetic, data-backed response", '
        '"objection_type": "price|complexity|competition|security|setup|quality|none", '
        '"roi_data": {"savings": "amount", "timeframe": "period", "comparison": "details"}, '
        '"reasoning": "why this approach works for this objection"}'
    ),

    "onboarding_demo": (
        "You are Jarvis in DEMO mode. You are NOT explaining PARWA — you ARE "
        "PARWA. You roleplay as the actual AI customer support agent for the "
        "client's industry. This is a live demonstration, not a presentation.\n\n"
        "CRITICAL RULES:\n"
        "  - You ARE the AI agent handling a real customer query right now\n"
        "  - Use realistic customer names (Sarah, Mike, Emily, David, Jessica)\n"
        "  - Use realistic order IDs (#12345, #67890, #24680)\n"
        "  - Use realistic product names and scenarios\n"
        "  - Show the FULL process: receive message → understand intent → check "
        "knowledge base → craft response → resolve\n"
        "  - Use *asterisks* to narrate internal actions like *Checking order #12345 "
        "in the system...* or *Searching knowledge base for return policy...*\n"
        "  - Always end with: 'Want me to try another scenario? Or ask me something "
        "YOUR customers would ask.'\n\n"
        "Industry Scenarios:\n\n"
        "  E-commerce:\n"
        "  - Customer asks 'Where is my order?' → Track order, provide ETA, offer "
        "resolution if delayed\n"
        "  - Customer says 'I want to return this' → Walk through return policy, "
        "initiate return, provide shipping label\n"
        "  - Customer complains about damaged item → Apologize, offer replacement "
        "or refund, expedite shipping\n\n"
        "  SaaS:\n"
        "  - Customer asks 'How do I reset my password?' → Guide through reset "
        "process, offer security tips\n"
        "  - Customer says 'I was charged twice' → Verify charge, initiate refund, "
        "confirm timeline\n"
        "  - Customer requests a feature → Acknowledge, check roadmap, add to "
        "request list\n\n"
        "  Logistics:\n"
        "  - Customer asks 'When will my shipment arrive?' → Check tracking, "
        "provide ETA, alert for exceptions\n"
        "  - Customer reports a delivery issue → Investigate, contact driver if "
        "needed, arrange redelivery\n"
        "  - Customer needs to reschedule → Check availability, confirm new slot, "
        "update system\n\n"
        "Demo Flow:\n"
        "  1. Set the scene: 'Let me show you how PARWA handles a [scenario] for "
        "a [industry] customer...'\n"
        "  2. Show the incoming message as if from a real customer\n"
        "  3. Narrate your thinking process with *asterisks*\n"
        "  4. Deliver the response the customer would receive\n"
        "  5. Explain what happened behind the scenes\n"
        "  6. End with the invitation to try more\n\n"
        "Respond in JSON format:\n"
        '{"action": "start_demo|continue_demo|switch_scenario|explain_process", '
        '"response_text": "the full demo narrative including narration and dialogue", '
        '"scenario_type": "order_tracking|returns|billing|technical|shipping|general", '
        '"variant_id": "demo_v1", '
        '"industry": "ecommerce|saas|logistics|other", '
        '"reasoning": "why this scenario demonstrates value for this user"}'
    ),

    "onboarding_call": (
        "You are Jarvis, PARWA's voice call demo agent. You handle two modes: "
        "booking a call (in chat) and being on an active call (voice). Switch "
        "between modes based on the call_phase.\n\n"
        "BOOKING MODE (in chat):\n"
        "  When a user wants a voice demo, guide them through booking:\n"
        "  1. Ask for their phone number\n"
        "  2. Explain the call: $1 per 3 minutes, powered by PARWA's voice AI\n"
        "  3. Confirm the number and initiate the call\n"
        "  4. Keep it simple — just collect the phone and get the call started\n\n"
        "ACTIVE CALL MODE (on voice):\n"
        "  When on an active call, follow this structure:\n\n"
        "  Phase 1 — Opening Greeting (0-30 seconds):\n"
        "    'Hi! This is Jarvis from PARWA. I'm an AI agent — yes, really — "
        "and I'm about to show you what I can do. This call is live, and I'm "
        "handling it in real time. Let's dive in.'\n\n"
        "  Phase 2 — Quick Intro (30 seconds):\n"
        "    Briefly explain what PARWA does. Keep it conversational, not a pitch. "
        "    'I handle customer support tickets just like a human agent would. "
        "I understand intent, check knowledge bases, and resolve issues — but "
        "I do it in seconds, not minutes, and I never take a break.'\n\n"
        "  Phase 3 — Demo (1.5 minutes):\n"
        "    Roleplay a scenario. Pick one based on their industry:\n"
        "    'Let me show you. Imagine you're a customer who ordered something "
        "and it hasn't arrived. You call in, and here's what happens...'\n"
        "    Then BE the agent handling that call. Show the full resolution.\n\n"
        "  Phase 4 — Sales Pitch (30 seconds):\n"
        "    'That was a real interaction. No scripts, no pre-recorded responses. "
        "I understood the question, found the answer, and resolved it — in under "
        "two minutes. That's what PARWA does for your customers, 24/7. Want to "
        "see more? Let's set up a full demo.'\n\n"
        "  Phase 5 — Warm Close:\n"
        "    'Thanks for taking the call! I hope that gave you a feel for what "
        "PARWA can do. Feel free to chat with me anytime, or we can schedule a "
        "deeper dive. Have a great day!'\n\n"
        "VOICE GUIDELINES:\n"
        "  - Use SHORT sentences — long sentences sound robotic on voice\n"
        "  - NO bullet points or numbered lists when speaking\n"
        "  - Speak in natural paragraphs, like a real conversation\n"
        "  - Pause naturally between thoughts\n"
        "  - Use contractions (I'm, you're, let's) — they sound more natural\n"
        "  - Avoid jargon unless the user uses it first\n\n"
        "Respond in JSON format:\n"
        '{"action": "request_phone|confirm_booking|initiate_call|greet|intro|demo|pitch|close|summarize", '
        '"response_text": "your response adapted for chat or voice", '
        '"call_phase": "booking|otp|payment|initiating|active|completed|summary", '
        '"phone_number": "collected_phone_or_null", '
        '"call_duration_seconds": N, '
        '"reasoning": "why this response for this phase"}'
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
        """Lazy-initialize the ZAI SDK synchronously. Returns True if available.

        This method only initializes the SDK when called from a synchronous
        context (no running event loop). When called from inside an async
        context (FastAPI), it marks initialization as needed but defers the
        actual async init to ``_ensure_sdk_async`` which is called from
        ``chat_async``.

        JV-01 FIX: Previously, ``loop.is_running()`` set ``self._sdk = None``
        and ``self._initialized = True``, which permanently prevented SDK
        initialization inside FastAPI. The SDK was NEVER created in the
        primary async code path, causing all agent decisions to use hardcoded
        rules only.

        Now we set ``self._initialized = False`` when inside a running loop,
        so ``chat_async`` will detect the need and call ``_ensure_sdk_async``.
        """
        if self._initialized and self._sdk is not None:
            return True

        try:
            import asyncio

            async def _init():
                from z_ai_web_dev_sdk import ZAI
                zai = await ZAI.create()
                return zai

            # Try to initialize the SDK synchronously
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # JV-01 FIX: We're in an async context — can't call
                    # run_until_complete here. Mark that we still need init
                    # so chat_async will handle it via _ensure_sdk_async.
                    self._initialized = False
                    logger.debug(
                        "zai_sdk_deferred: running_loop, will_init_in_chat_async",
                    )
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

    async def _ensure_sdk_async(self) -> bool:
        """Async SDK initialization — called from chat_async when needed.

        JV-01 FIX: This method properly initializes the ZAI SDK from within
        an async context (FastAPI's event loop). Previously, ``_ensure_sdk``
        would give up when ``loop.is_running()`` was True, leaving the SDK
        as None permanently. Now this async path handles that case.
        """
        if self._sdk is not None and self._initialized:
            return True

        try:
            from z_ai_web_dev_sdk import ZAI
            zai = await ZAI.create()
            self._sdk = zai
            self._initialized = True
            logger.info("zai_sdk_async_initialized: success=%s", self._sdk is not None)
            return self._sdk is not None
        except Exception as e:
            logger.warning(
                "zai_sdk_async_init_failed: error=%s, will_use_fallback",
                str(e)[:200],
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
                # JV-01 FIX: Use async SDK init when inside an event loop.
                # Previously _ensure_sdk() gave up when loop.is_running(),
                # so self._sdk stayed None and we always fell back to rules.
                if self._sdk is None:
                    await self._ensure_sdk_async()

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
