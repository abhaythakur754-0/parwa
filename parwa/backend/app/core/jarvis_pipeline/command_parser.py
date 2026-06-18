"""
Jarvis Command Parser — 2-Tier Intent Classification

Tier 1 (FAST, 0 tokens): Regex patterns for known commands.
  - Instant response, no LLM call needed
  - Covers ~80% of daily usage

Tier 2 (SMART, 1 LLM call ~200 tokens): For everything else.
  - Falls back to LLM classification
  - Structured JSON output

Total cost per interaction: 0-1 LLM calls depending on tier hit.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("jarvis.parser")

# ── Intent Families ───────────────────────────────────────────

INTENT_QUERIES = {
    "query_status",       # system status, uptime, mode
    "query_errors",       # error logs, failures
    "query_tickets",      # ticket counts, specific tickets
    "query_quality",      # accuracy, performance, drift
    "query_quota",        # usage, remaining, limits
    "query_notifications",# show notifications, what's PARWA-NFY-001
    "query_flags",        # what rules are active, show my rules
    "query_audit",        # who did what, show history
    "query_health",       # Wave 2: integration health, uptime, pings
    "query_cost",         # Wave 2: LLM costs, token usage, spend
    "query_flow",         # Wave 2: ticket flow metrics, node-by-node
    "query_load",         # Wave 2: variant load, concurrency, bottlenecks
    "query_stuck",        # Wave 2: stuck tickets with escalation tiers
}

INTENT_CONTROLS = {
    "control_pause",      # pause refunds, pause all
    "control_resume",     # resume refunds
    "control_route",      # redirect channel to AI/human
    "control_mode",       # change Shadow/Supervised/Graduated
    "control_disable_rule", # undo/disable last rule
    "control_skill_assign", # move skill between variants
    "control_approval_override", # always auto-approve this type (Wave 3)
}

INTENT_APPROVALS = {
    "approve_batch",      # approve grouped items
    "reject_batch",       # reject grouped items
    "approve_single",     # approve one ticket
    "reject_single",      # reject one ticket
}

INTENT_EMERGENCIES = {
    "emergency_shutdown", # stop all AI
    "emergency_recall",   # recall sent messages
    "emergency_void",     # void pending messages
}

INTENT_EXPLAIN = {
    "explain_ticket",     # why did X happen, show GSD state
    "explain_flag",       # why is this rule active
}

INTENT_TEACH = {
    "teach_skill",        # here's how to handle X
}

INTENT_AGENT = {
    "create_agent",       # add/provision new agents
}

INTENT_UNKNOWN = "unknown"

ALL_INTENTS = (
    INTENT_QUERIES | INTENT_CONTROLS | INTENT_APPROVALS |
    INTENT_EMERGENCIES | INTENT_EXPLAIN | INTENT_TEACH | INTENT_AGENT |
    {INTENT_UNKNOWN}
)


# ═══════════════════════════════════════════════════════════════
# TIER 1: REGEX FAST PATH (0 tokens, instant)
# ═══════════════════════════════════════════════════════════════

# Each pattern: (compiled_regex, intent, target_extractor)
# target_extractor takes the match object and returns a target string

_TIER1_PATTERNS = [
    # ── Queries ───────────────────────────────────────────────
    # System status
    (re.compile(r"\b(show|what'?s?|what is|tell me about|get)\b.*(system\s*status|uptime|mode)\b", re.I),
     "query_status", lambda m: "system"),

    (re.compile(r"\b(show|what'?s?|how many|tell me|get)\b.*(error|failure|failed|errors?)\b", re.I),
     "query_errors", lambda m: "all"),

    # Wave 2 Queries
    (re.compile(r"\b(show|what'?s?|check|tell me|get)\b.*(integration|service|services?)\s*(health|status|uptime)\b", re.I),
     "query_health", lambda m: "all"),

    (re.compile(r"\b(show|what'?s?|how much|tell me|get)\b.*(cost|spend|spending|tokens?|bills?|llm)\b", re.I),
     "query_cost", lambda m: "all"),

    (re.compile(r"\b(show|what'?s?|tell me|get|how many)\b.*(ticket\s*flow|flow\s*metric|pipeline|funnel|resolved|escalated)\b", re.I),
     "query_flow", lambda m: "all"),

    (re.compile(r"\b(show|what'?s?|check|tell me|get)\b.*(load|concurrent|capacity|bottleneck|busy)\b", re.I),
     "query_load", lambda m: "all"),

    (re.compile(r"\b(show|what'?s?|how many|tell me|get)\b.*(stuck|stale|waiting|pending.?approvals?)\b", re.I),
     "query_stuck", lambda m: "all"),

    # Generic ticket
    (re.compile(r"\b(show|what'?s?|how many|tell me|get|list)\b.*(ticket|tickets)\b", re.I),
     "query_tickets", lambda m: "all"),

    (re.compile(r"\b(show|what'?s?|how|tell me|get)\b.*(quality|accuracy|performance|drift)\b", re.I),
     "query_quality", lambda m: "all"),

    (re.compile(r"\b(show|what'?s?|how much|tell me|get)\b.*(quota|usage|remaining|limit|burn)\b", re.I),
     "query_quota", lambda m: "all"),

    (re.compile(r"\b(show|list|what'?s?)\b.*(notification|alert|nfy|notifications?)\b", re.I),
     "query_notifications", lambda m: "all"),

    (re.compile(r"PARWA-NFY-\d+", re.I),
     "query_notifications", lambda m: m.group()),

    (re.compile(r"\b(show|list|what|active)\b.*(rule|rules|flag|flags)\b", re.I),
     "query_flags", lambda m: "all"),

    (re.compile(r"\b(show|list|what|who)\b.*(audit|history|log|activity)\b", re.I),
     "query_audit", lambda m: "all"),

    # ── Emergencies (BEFORE controls — "stop everything" overlaps with pause) ──
    (re.compile(r"\b(shut\s*down|shut everything|stop everything|kill|rage quit|emergency stop)\b", re.I),
     "emergency_shutdown", lambda m: "all"),

    (re.compile(r"\b(recall)\b.*(email|message|sent|all)\b", re.I),
     "emergency_recall", lambda m: _extract_target(m, "email|message|all")),

    (re.compile(r"\b(void|delete|cancel)\b.*(pending|queued|outbox)\b", re.I),
     "emergency_void", lambda m: "pending"),

    # ── Controls ──────────────────────────────────────────────
    # Approval override (must be before generic approve)
    (re.compile(r"\b(always|permanently)\s*(auto\s*-?approve)\b", re.I),
     "control_approval_override", lambda m: "auto_approve"),

    (re.compile(r"\b(auto\s*-?approve)\b.*(always|permanently|forever)\b", re.I),
     "control_approval_override", lambda m: "auto_approve"),

    # Pause — no trailing \b on targets to handle plurals
    (re.compile(r"\b(pause|stop|disable)\b.*(refund|return|account_change)", re.I),
     "control_pause", lambda m: _extract_target(m, "refund|return|account_change")),

    (re.compile(r"\b(pause|stop|disable)\b.*(all|everything)\b", re.I),
     "control_pause", lambda m: "all"),

    # Resume
    (re.compile(r"\b(resume|enable|start|unpause|re\s*-?enable)\b.*(refund|return|account_change)", re.I),
     "control_resume", lambda m: _extract_target(m, "refund|return|account_change")),

    (re.compile(r"\b(resume|enable|start|unpause|re\s*-?enable)\b.*(all|everything|processing)\b", re.I),
     "control_resume", lambda m: "all"),

    # Bare resume/unpause without target
    (re.compile(r"\b(resume|enable|start|unpause|re\s*-?enable)\b$", re.I),
     "control_resume", lambda m: "all"),

    # Route
    (re.compile(r"\b(handle|redirect|route)\b.*(instagram|email|call|dm|sms|whatsapp|all)\b", re.I),
     "control_route", lambda m: _extract_target(m, "instagram|email|call|dm|sms|whatsapp|all")),

    # Mode
    (re.compile(r"\b(switch|change|set)\b.*(mode|shadow|supervised|graduated)\b", re.I),
     "control_mode", lambda m: _extract_target(m, "shadow|supervised|graduated")),

    # Disable rule
    (re.compile(r"\b(undo|disable|revoke|remove)\b.*(last|my|the)\s*(rule|flag|pause)\b", re.I),
     "control_disable_rule", lambda m: "last"),

    # Skill assignment
    (re.compile(r"\b(move|reassign|transfer)\b.*\b(from|to)\b", re.I),
     "control_skill_assign", lambda m: "skill_reassign"),

    (re.compile(r"\b(add|assign)\b.*\b(skill|capability)\b.*\b(to)\b", re.I),
     "control_skill_assign", lambda m: "skill_add"),

    # ── Approvals ─────────────────────────────────────────────
    (re.compile(r"\b(approve)\b.*(batch|all|group|them)\b", re.I),
     "approve_batch", lambda m: "all"),

    (re.compile(r"\b(reject|deny)\b.*(batch|all|group|them)\b", re.I),
     "reject_batch", lambda m: "all"),

    (re.compile(r"\b(approve)\b.*(ticket|this|it|#?\d+)\b", re.I),
     "approve_single", lambda m: _extract_target(m, r"#?\d+|ticket|this|it")),

    (re.compile(r"\b(reject|deny)\b.*(ticket|this|it|#?\d+)\b", re.I),
     "reject_single", lambda m: _extract_target(m, r"#?\d+|ticket|this|it")),

    # ── Explain ───────────────────────────────────────────────
    (re.compile(r"\b(why|explain|how did|what happened)\b.*(ticket|this|that|TKT-?\d*|#?\d+)\b", re.I),
     "explain_ticket", lambda m: _extract_target(m, r"TKT-?\d*|#?\d+|ticket|this|that")),

    (re.compile(r"\b(why|explain)\b.*(rule|flag|pause|redirect)\b", re.I),
     "explain_flag", lambda m: "active_rule"),

    # ── Teach ─────────────────────────────────────────────────
    (re.compile(r"\b(here'?s? how|teach|learn|handle it like|the process is|the way to)\b.*\b(handle|process|deal with|respond to|do)\b", re.I),
     "teach_skill", lambda m: "custom_process"),

    # ── Agent Creation ────────────────────────────────────────
    (re.compile(r"\b(add|provision|scale|create)\b\s*(\d+)?\s*(agent|mini|parwa|high|bot|worker)s?\b", re.I),
     "create_agent", lambda m: m.group() if m else "agent"),
]


def _extract_target(match, targets_pattern) -> str:
    """Extract the target from a match using a pattern of alternatives."""
    if isinstance(targets_pattern, str):
        targets_pattern = re.compile(targets_pattern, re.I)
    m2 = targets_pattern.search(match.group())
    return m2.group().lower() if m2 else "all"


def _tier1_classify(input_text: str) -> Optional[Dict[str, Any]]:
    """Try regex-based classification. Returns None if no match."""
    text = input_text.strip()
    if not text:
        return None

    for pattern, intent, target_fn in _TIER1_PATTERNS:
        m = pattern.search(text)
        if m:
            target = target_fn(m)
            return {
                "intent": intent,
                "target": target,
                "scope": _infer_scope(text),
                "confidence": 0.92,
                "classification_method": "regex",
                "raw_input": text,
            }

    return None


def _infer_scope(text: str) -> str:
    """Infer scope from the input text."""
    if re.search(r"\bfor today\b|\btoday\b|\bthis weekend\b|\bfor \d+ hours?\b|\bfor \d+ minutes?\b", text, re.I):
        return "temporary"
    if re.search(r"\balways\b|\bpermanently\b|\bpermanent\b|\bforever\b", text, re.I):
        return "permanent"
    return "global"


# ═══════════════════════════════════════════════════════════════
# TIER 2: LLM CLASSIFICATION (1 call, ~200 tokens)
# ═══════════════════════════════════════════════════════════════

_LLM_CLASSIFY_PROMPT = """Classify this Jarvis command. Return ONLY valid JSON.

Input: "{input}"

Intent families:
- query_status: system status, uptime, mode
- query_errors: error logs, failures
- query_tickets: ticket counts, specific tickets
- query_quality: accuracy, performance, drift, health
- query_quota: usage, remaining, limits
- query_notifications: show notifications, NFY keys
- query_flags: active rules, flags
- query_audit: history, who did what
- control_pause: pause an action/channel
- control_resume: resume paused action
- control_route: redirect channel to AI/human
- control_mode: change Shadow/Supervised/Graduated
- control_disable_rule: undo/disable a rule
- control_skill_assign: move skill between variants
- approve_batch / reject_batch: batch actions
- approve_single / reject_single: single item
- emergency_shutdown: stop all AI
- emergency_recall: recall sent messages
- emergency_void: void pending messages
- explain_ticket: why did X happen
- explain_flag: why is this rule active
- teach_skill: teaching a new process
- create_agent: provision new agents
- unknown: cannot classify

Return: {{"intent":"...","target":"...","scope":"...","confidence":0.0}}"""


async def _tier2_classify(input_text: str) -> Dict[str, Any]:
    """LLM-based classification for inputs that regex can't handle."""
    from app.core.parwa_pipeline.llm_client import llm_call

    prompt = _LLM_CLASSIFY_PROMPT.format(input=input_text)
    try:
        response = await llm_call(prompt, max_tokens=100, temperature=0.0)
        # Parse JSON from response
        text = response.strip()
        # Handle markdown code blocks
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        result = json.loads(text)

        intent = result.get("intent", "unknown")
        if intent not in ALL_INTENTS:
            intent = "unknown"

        return {
            "intent": intent,
            "target": result.get("target", "all"),
            "scope": result.get("scope", "global"),
            "confidence": float(result.get("confidence", 0.7)),
            "classification_method": "llm",
            "raw_input": input_text,
        }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("LLM classification parse failed: %s → %s", e, response[:100] if 'response' in dir() else "?")
        return {
            "intent": "unknown",
            "target": "all",
            "scope": "global",
            "confidence": 0.3,
            "classification_method": "llm_failed",
            "raw_input": input_text,
        }
    except Exception as e:
        logger.warning("LLM classification error: %s", e)
        return {
            "intent": "unknown",
            "target": "all",
            "scope": "global",
            "confidence": 0.2,
            "classification_method": "llm_error",
            "raw_input": input_text,
        }


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

async def classify_command(input_text: str) -> Dict[str, Any]:
    """Classify a natural language Jarvis command.

    2-tier approach:
      1. Regex fast-path (0 tokens, instant) — covers ~80% of commands
      2. LLM fallback (1 call, ~200 tokens) — for everything else

    Returns dict with: intent, target, scope, confidence, classification_method
    """
    # Tier 1: Try regex first (instant, free)
    result = _tier1_classify(input_text)
    if result:
        logger.debug("Tier 1 hit: %s → %s (confidence=%.2f)", input_text[:50], result["intent"], result["confidence"])
        return result

    # Tier 2: LLM classification
    logger.debug("Tier 1 miss, falling back to LLM: %s", input_text[:50])
    result = await _tier2_classify(input_text)
    logger.info("Tier 2 classified: %s → %s (confidence=%.2f)", input_text[:50], result["intent"], result["confidence"])
    return result


def classify_command_sync(input_text: str) -> Dict[str, Any]:
    """Synchronous version — regex only, no LLM. For testing."""
    result = _tier1_classify(input_text)
    if result:
        return result
    return {
        "intent": "unknown",
        "target": "all",
        "scope": "global",
        "confidence": 0.0,
        "classification_method": "sync_fallback",
        "raw_input": input_text,
    }


# ── Intent Category Helpers ───────────────────────────────────

def is_query_intent(intent: str) -> bool:
    return intent in INTENT_QUERIES

def is_control_intent(intent: str) -> bool:
    return intent in INTENT_CONTROLS

def is_approval_intent(intent: str) -> bool:
    return intent in INTENT_APPROVALS

def is_emergency_intent(intent: str) -> bool:
    return intent in INTENT_EMERGENCIES

def requires_admin(intent: str) -> bool:
    """Intents that require admin/owner/supervisor role."""
    admin_intents = INTENT_CONTROLS | INTENT_EMERGENCIES | INTENT_TEACH | INTENT_AGENT
    return intent in admin_intents

def requires_owner(intent: str) -> bool:
    """Intents that require owner role only."""
    return intent in {"emergency_shutdown", "create_agent"}