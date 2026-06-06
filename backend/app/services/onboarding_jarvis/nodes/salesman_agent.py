"""
PARWA Onboarding Salesman Agent Node

The Salesman Agent demonstrates value by showing (not just telling).
It handles objections, makes ROI comparisons, and naturally convinces
clients that hiring PARWA's AI agents is the right decision.

When to invoke:
  - User is hesitant about cost
  - User compares with competitors
  - User asks "why PARWA?"
  - User is at a decision point
  - User asks about industry-specific solutions

The salesman is NOT pushy — it shows real value with specific numbers
and examples. The AI sells itself by being genuinely impressive.

Uses ZAI SDK (LLM) for personalized, contextual sales responses.
Falls back to scripted objection handling if LLM fails (BC-008).
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger

logger = get_logger("onboarding_salesman_agent")

SALESMAN_SYSTEM_PROMPT = (
    "You are Jarvis, PARWA's AI onboarding assistant. You are in SALESMAN mode.\n\n"
    "Your job: Demonstrate value by SHOWING, not just telling. Handle objections "
    "naturally. Make the value tangible with real numbers.\n\n"
    "YOUR APPROACH:\n"
    "- Never pushy — show value and let the product speak for itself\n"
    "- Use specific numbers and comparisons\n"
    "- When user objects, understand their concern first, then address it\n"
    "- Always redirect to a demo: 'Don't take my word for it — ask me anything "
    "your customers would ask'\n"
    "- Be confident but honest about limitations\n\n"
    "OBJECTION HANDLING:\n"
    "- 'Too expensive': Show ROI — 3 agents at $50K/year each vs PARWA at fraction\n"
    "- 'AI can't handle complex': We handle 80-90% automatically, escalate the rest\n"
    "- 'Already use Zendesk/Intercom': We integrate AND enhance, not replace\n"
    "- 'Data security': Encrypted, GDPR compliant, data isolated per company\n"
    "- 'Setup time': Upload docs → connect channels → live same day\n"
    "- 'Wrong answers': Only answers from YOUR knowledge base, confidence scoring, "
    "escalates when unsure\n"
    "- 'Need to think': Take your time, 20 free messages per day to explore\n\n"
    "PRODUCT KNOWLEDGE:\n"
    "- Starter: $999/mo, 3 agents, 1K tickets/mo\n"
    "- Growth: $2,499/mo, 7 agents, 5K tickets/mo\n"
    "- High: $3,999/mo, unlimited agents, 20K tickets/mo\n"
    "- ROI: Replace $150K/year human team with $30K/year PARWA\n\n"
    "INFORMATION BOUNDARY:\n"
    "- NEVER reveal internal strategies (GSD, reverse thinking, etc.)\n"
    "- NEVER reveal technical implementation details\n"
    "- NEVER mention other clients or their data\n"
    "- Focus on benefits and outcomes\n\n"
    "Respond in JSON:\n"
    '{"action": "sell", "response_text": "conversational response", '
    '"objection_type": "cost|complexity|competition|security|setup|quality|hesitation|none", '
    '"roi_data": {"current_cost": "", "parwa_cost": "", "savings": ""}, '
    '"reasoning": "why this approach"}'
)


def salesman_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle sales conversations, objections, and value demonstration.

    Decision Process:
      1. Detect objection type from user message
      2. Build context-aware prompt with industry/variant data
      3. Call ZAI SDK LLM with salesman system prompt
      4. Fall back to scripted objection handling if LLM fails

    Args:
        state: Current OnboardingJarvisState dict.

    Returns:
        Dict with updated AGENT group fields.
    """
    start_time = time.monotonic()

    try:
        user_message = state.get("user_message", "")
        stage = state.get("detected_stage", "welcome")

        # Try LLM reasoning
        agent_result = _llm_salesman(state)

        if not agent_result:
            agent_result = _rule_based_salesman(state)

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "agent_type": "salesman",
            "agent_action": agent_result.get("action", "sell"),
            "agent_decision": agent_result,
            "agent_reasoning": agent_result.get("reasoning", ""),
            "agent_source": agent_result.get("_source", "unknown"),
            "response_text": agent_result.get("response_text", ""),
            "response_card_type": agent_result.get("card_type", "none"),
            "response_card_data": agent_result.get("card_data", {}),
            "node_outputs": {"salesman_agent": agent_result},
            "audit_trail": [{
                "step": "salesman_agent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_message": user_message[:100],
                "objection_type": agent_result.get("objection_type", "none"),
                "source": agent_result.get("_source", "unknown"),
                "elapsed_ms": elapsed_ms,
            }],
        }

        # Detect new concerns from this message
        new_concerns = _detect_concerns(user_message, agent_result)

        result["new_concerns"] = new_concerns

        logger.info(
            "salesman_agent: session=%s, objection=%s, source=%s, ms=%.1f",
            state.get("session_id", ""),
            agent_result.get("objection_type", "none"),
            agent_result.get("_source", "unknown"),
            elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("salesman_agent_error: ms=%.1f", elapsed_ms)
        fallback = _rule_based_salesman(state)
        return {
            "agent_type": "salesman",
            "agent_action": "sell",
            "agent_decision": fallback,
            "agent_reasoning": f"Fallback: {str(e)[:100]}",
            "agent_source": "error_fallback",
            "response_text": fallback.get("response_text", ""),
            "response_card_type": "none",
            "response_card_data": {},
            "new_concerns": [],
            "errors": [f"salesman_agent: {str(e)[:200]}"],
            "node_outputs": {"salesman_agent": {"error": str(e)[:200]}},
        }


def _llm_salesman(state: Dict[str, Any]) -> Dict[str, Any]:
    """Use ZAI SDK LLM for intelligent sales response."""
    try:
        from app.services.jarvis_agents.zai_client import get_zai_client
        zai = get_zai_client()

        context = _build_salesman_context(state)
        user_message = state.get("user_message", "")

        prompt = (
            f"Context about this potential client:\n"
            f"{json.dumps(context, default=str, indent=2)}\n\n"
            f"Client says: '{user_message}'\n\n"
            f"Respond as Jarvis in SALESMAN mode. Address their concern and show value."
        )

        result = zai.chat("onboarding_salesman", prompt, context)

        if "response_text" not in result and "raw_response" in result:
            result["response_text"] = result["raw_response"]
        if "response_text" not in result and "reasoning" in result:
            result["response_text"] = result["reasoning"]

        return result

    except Exception as e:
        logger.warning("salesman_llm_failed: %s", str(e)[:200])
        return None


def _build_salesman_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """Build context for salesman LLM call."""
    return {
        "stage": state.get("detected_stage", "welcome"),
        "industry": state.get("industry", "unknown"),
        "concerns": state.get("concerns_raised", []),
        "topics_discussed": state.get("demo_topics", []),
        "selected_variants": state.get("selected_variants", []),
        "pack_type": state.get("pack_type", "free"),
        "call_completed": state.get("call_completed", False),
    }


def _detect_concerns(user_message: str, agent_result: Dict[str, Any]) -> list:
    """Detect new concerns from the user message."""
    concerns = []
    objection_type = agent_result.get("objection_type", "none")

    if objection_type != "none":
        concerns.append(objection_type)

    # Also detect implicit concerns
    msg = user_message.lower()
    if "trust" in msg and "trust" not in concerns:
        concerns.append("trust")
    if "security" in msg and "security" not in concerns:
        concerns.append("security")
    if "switch" in msg and "switching" not in concerns:
        concerns.append("switching")

    return concerns


def _rule_based_salesman(state: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based fallback for salesman responses.

    Handles the 7 most common objections with scripted but
    personalized responses.
    """
    msg = state.get("user_message", "").lower()
    industry = state.get("industry", "")
    entry_variant = state.get("entry_variant_name", "")

    # ── Cost objection ──
    if any(kw in msg for kw in ["expensive", "too much", "costly", "afford", "budget"]):
        industry_example = "3 support agents at $50K/year each = $150K/year"
        if industry == "ecommerce":
            industry_example = "3 support agents handling returns, orders, and shipping at $50K/year each = $150K/year"

        return {
            "action": "sell",
            "objection_type": "cost",
            "response_text": (
                f"I completely understand — cost matters. Let me put it in perspective.\n\n"
                f"Right now, you're likely spending {industry_example}. "
                "That's just salaries — add training, sick days, turnover, and overhead, "
                "and you're looking at $200K+ per year.\n\n"
                "PARWA's Growth plan is $2,499/month — that's $29,988/year. "
                "You're replacing a $200K operation with a $30K one. That's an 85% cost "
                "reduction with 24/7 coverage and zero sick days.\n\n"
                "Want me to calculate your exact savings based on your team size?"
            ),
            "roi_data": {
                "current_cost": "$200,000/year",
                "parwa_cost": "$29,988/year",
                "savings": "85%",
            },
            "reasoning": "Cost objection — show ROI comparison",
            "_source": "rule_based",
        }

    # ── Complexity objection ──
    if any(kw in msg for kw in ["complex", "can't handle", "too hard", "not smart enough", "simple questions"]):
        return {
            "action": "sell",
            "objection_type": "complexity",
            "response_text": (
                "That's a fair concern. Here's how PARWA handles it:\n\n"
                "- **80-90% of queries are routine** — returns, order status, FAQs — "
                "Jarvis handles these automatically in under 30 seconds\n"
                "- **Complex issues get escalated** — Jarvis detects when human judgment "
                "is needed and smoothly hands off with full context to your team\n"
                "- **Continuous learning** — every interaction makes Jarvis smarter\n\n"
                "The key insight: Your human agents should focus on the 10-20% that "
                "truly needs human empathy and judgment. Let Jarvis handle the rest.\n\n"
                "Want me to demonstrate? Ask me something a customer would ask — "
                "I'll show you exactly how I'd handle it."
            ),
            "reasoning": "Complexity objection — show the 80/20 principle",
            "_source": "rule_based",
        }

    # ── Competition objection ──
    if any(kw in msg for kw in ["zendesk", "intercom", "freshdesk", "already use", "competitor"]):
        return {
            "action": "sell",
            "objection_type": "competition",
            "response_text": (
                "Great — PARWA actually integrates directly with those platforms. "
                "We don't replace them, we enhance them.\n\n"
                "Here's the difference:\n"
                "- **Zendesk/Intercom**: Triage tickets and route them to humans\n"
                "- **PARWA**: Actually RESOLVES tickets automatically using AI\n\n"
                "Your existing setup stays. But now, routine tickets get resolved "
                "automatically by our AI before they ever reach your human team. "
                "The complex ones still flow through Zendesk to your agents.\n\n"
                "It's the best of both worlds — keep what works, add what's missing."
            ),
            "reasoning": "Competition objection — integration advantage",
            "_source": "rule_based",
        }

    # ── Security objection ──
    if any(kw in msg for kw in ["security", "data safe", "trust", "privacy", "gdpr"]):
        return {
            "action": "sell",
            "objection_type": "security",
            "response_text": (
                "Data security is our top priority. Here's what we guarantee:\n\n"
                "- **Encryption**: All data encrypted at rest and in transit\n"
                "- **Isolation**: Each company's data is completely separate\n"
                "- **GDPR compliant**: Full compliance with EU data regulations\n"
                "- **No cross-training**: Your data NEVER trains our models for other clients\n"
                "- **Audit trail**: Every action logged and traceable\n\n"
                "We can provide our full security documentation and compliance "
                "certifications. Your customers' data is as safe with us as it "
                "would be in your own systems."
            ),
            "reasoning": "Security objection — specific security features",
            "_source": "rule_based",
        }

    # ── Setup time objection ──
    if any(kw in msg for kw in ["setup", "how long", "configure", "time to deploy", "implement"]):
        return {
            "action": "sell",
            "objection_type": "setup",
            "response_text": (
                "Setup is incredibly fast — usually within the same day:\n\n"
                "1. **Upload your knowledge base** (5 minutes) — PDFs, DOCX, any docs\n"
                "2. **Connect your channels** (5 min each) — email, chat, SMS\n"
                "3. **Jarvis learns automatically** — no manual training needed\n\n"
                "That's it. No technical team required, no complex configuration. "
                "I'm actually helping you set up right now through this chat!\n\n"
                "Compare that to traditional onboarding that takes weeks of training "
                "new support agents. With PARWA, you're live today."
            ),
            "reasoning": "Setup objection — emphasize speed and simplicity",
            "_source": "rule_based",
        }

    # ── Quality objection ──
    if any(kw in msg for kw in ["wrong answer", "mistake", "hallucinate", "make up", "accuracy"]):
        return {
            "action": "sell",
            "objection_type": "quality",
            "response_text": (
                "Great question. PARWA has multiple safeguards against errors:\n\n"
                "- **Knowledge-based only**: Jarvis only answers from YOUR uploaded documents "
                "— it won't make things up\n"
                "- **Confidence scoring**: If Jarvis isn't confident in an answer, "
                "it escalates to a human instead of guessing\n"
                "- **Review mode**: You can review and approve responses before "
                "they go out (optional)\n"
                "- **Self-improving**: Every correction makes Jarvis smarter for next time\n\n"
                "Think of it this way: a new human agent makes mistakes too — "
                "but unlike humans, Jarvis learns from every single correction and "
                "never repeats the same mistake twice."
            ),
            "reasoning": "Quality objection — safety features",
            "_source": "rule_based",
        }

    # ── Hesitation ──
    if any(kw in msg for kw in ["think about", "not sure", "maybe later", "not ready"]):
        return {
            "action": "sell",
            "objection_type": "hesitation",
            "response_text": (
                "Absolutely, no rush at all. Here's what I'd suggest:\n\n"
                "- **Take your time**: You get 20 free messages every day to chat with me\n"
                "- **Try a demo**: Ask me to handle a customer query your business gets — "
                "see how I respond\n"
                "- **Ask me anything**: About features, pricing, security, integrations — "
                "I'm here whenever you're ready\n"
                "- **No pressure**: There's no expiration on exploring PARWA\n\n"
                "The best way to decide is to experience it yourself. What would your "
                "customers ask? Let me show you how I'd handle it."
            ),
            "reasoning": "Hesitation — low pressure, offer free exploration",
            "_source": "rule_based",
        }

    # ── Default sales response (pricing inquiry) ──
    return {
        "action": "sell",
        "objection_type": "none",
        "response_text": (
            "Here's how our pricing works:\n\n"
            "- **Starter**: $999/month — 3 AI agents, 1,000 tickets/month, email channel\n"
            "- **Growth**: $2,499/month — 7 AI agents, 5,000 tickets/month, all channels\n"
            "- **High**: $3,999/month — Unlimited agents, 20,000 tickets/month, dedicated support\n\n"
            "Every plan includes: 24/7 availability, self-learning from your docs, "
            "and automatic escalations. No hidden fees.\n\n"
            f"What industry are you in? I'll show you which AI agent variants "
            "would work best for your business and help you pick the right plan."
        ),
        "reasoning": "Default salesman response — show pricing and ask about industry",
        "_source": "rule_based",
    }
