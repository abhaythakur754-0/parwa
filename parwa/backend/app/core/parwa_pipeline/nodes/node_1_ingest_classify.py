"""
Node 1: Ingest + Classify

Question: WHAT is this ticket?

Techniques (in order):
  1. SmartRouter.classify()      — ticket type + complexity (non-LLM)
  2. DynamicContext.pull()       — customer history, account info (non-LLM)
  3. MetaLearner.predict()       — past routing patterns (non-LLM)
  4. UoT.measure()               — confidence on classification (LLM)

LLM calls: 1 (UoT only)
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict

from app.core.parwa_pipeline.llm_client import llm_call, parse_confidence
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_1")

# ── Ticket type patterns (SmartRouter — rule-based classification) ─

TICKET_PATTERNS: Dict[str, list] = {
    "refund_request": [
        r"\brefund\b", r"\bmoney back\b", r"\breturn my\b",
        r"\bcancel.*refund\b", r"\brefund.*cancel\b",
        r"\bget my money\b", r"\bchargeback\b",
    ],
    "billing": [
        r"\bbilling\b", r"\binvoice\b", r"\bpayment\b",
        r"\bcharged\b", r"\bovercharge\b", r"\bdouble charge\b",
        r"\bsubscription.*price\b", r"\bhow much.*cost\b",
    ],
    "technical": [
        r"\bbug\b", r"\berror\b", r"\bcrash\b", r"\bbroken\b",
        r"\bnot working\b", r"\bcan't access\b", r"\bdoesn't load\b",
        r"\blogin issue\b", r"\b404\b", r"\b500\b",
    ],
    "faq": [
        r"\bwhat is\b", r"\bhow do i\b", r"\bhow does\b",
        r"\bwhere is\b", r"\bpricing\b", r"\bplan\b",
        r"\bfeature\b", r"\bdo you (have|offer|support)\b",
    ],
    "complaint": [
        r"\bterrible\b", r"\bworst\b", r"\bunacceptable\b",
        r"\bfrustrated\b", r"\bangry\b", r"\bdisappointed\b",
        r"\bnever again\b", r"\bcancel.*service\b",
    ],
    "account_change": [
        r"\bchange.*email\b", r"\bchange.*password\b",
        r"\bupdate.*account\b", r"\bupgrade\b", r"\bdowngrade\b",
        r"\bswitch.*plan\b", r"\btransfer\b",
    ],
}

# Complexity indicators
COMPLEXITY_KEYWORDS_HARD = [
    "multiple", "several", "both", "also", "and another",
    "complicated", "complex", "been going on", "for weeks",
    "manager", "supervisor", "escalate", "formal complaint",
]

COMPLEXITY_KEYWORDS_MEDIUM = [
    "but", "however", "except", "still", "yet",
    "previously", "again", "second time", "another",
]

# Phase 7: Multi-issue detection signals — when a query contains
# TWO or more distinct issues, it's at minimum "complex".
# Each signal is independently detectable (no ordering dependency).
MULTI_ISSUE_SIGNALS = [
    # "twice" or "double" (replication/duplicate issue)
    r"\btwice\b",
    r"\bdouble\s+charge\b",
    # Pricing discrepancy / inconsistency
    r"\bdifferent\s+(?:price|prices|pricing|rate|amount|charge|cost)\b",
    r"\b(?:wrong|incorrect)\s+(?:price|prices|pricing|charge|amount)\b",
    # "same ... as" comparison pattern (user comparing their situation)
    r"\bsame\s+(?:workspace|account|plan|team)\b",
    # Multiple questions (2+ question marks)
    r"\?[^?]*\?",
    # "and" joining two distinct topics
    r"\band\s+(?:also|why|how|what|when)\b",
    # Monetary amount mentioned + dispute language
    r"\$[\d,.]+.*(?:overcharge|duplicate|wrong|incorrect|twice|dispute)",
]

# Action extraction patterns
ACTION_PATTERNS = [
    (r"\brefund.*?\$?(\d+(?:\.\d{2})?)", "execute_refund", "amount"),
    (r"\bcredit.*?\$?(\d+(?:\.\d{2})?)", "execute_credit", "amount"),
    (r"\bchange.*(?:email|password|plan)", "account_change", "field"),
    (r"\b(?:cancel|close).*account", "cancel_account", None),
    (r"\b(?:upgrade|switch).*plan", "plan_change", "plan"),
    # Phase 7: Pricing dispute (NOT a plan change — customer is questioning, not requesting)
    (r"\b(?:why|how come)\s+(?:am\s+)?(?:i\s+)?(?:seeing|charged|paying|getting)\b", "investigate_billing", None),
    (r"\b(?:different|wrong|incorrect)\s+(?:price|prices|pricing|rate|charge|amount)\b", "investigate_billing", None),
    (r"\bcharged\s+\$?[\d,.]+\s+twice\b", "investigate_billing", "amount"),
]


# ── SmartRouter: Classify (non-LLM) ──────────────────────────────


def _classify_ticket_type(query: str) -> tuple:
    """Rule-based ticket type classification using pattern matching.
    Returns (ticket_type, matched_keywords)."""
    query_lower = query.lower()
    scores: Dict[str, int] = {}

    for ttype, patterns in TICKET_PATTERNS.items():
        count = 0
        matched = []
        for pat in patterns:
            if re.search(pat, query_lower):
                count += 1
                matched.append(pat)
        if count > 0:
            scores[ttype] = count

    if not scores:
        return "general", []

    best_type = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best_type, []


def _classify_complexity(query: str, ticket_type: str) -> str:
    """Rule-based complexity classification.
    Phase 7: Added multi-issue detection for dual-problem tickets."""
    query_lower = query.lower()

    # Phase 7: Multi-issue detection — if 2+ signals, it's complex at minimum
    multi_signals = sum(1 for pat in MULTI_ISSUE_SIGNALS if re.search(pat, query_lower, re.DOTALL))
    if multi_signals >= 2:
        return "complex"
    if multi_signals == 1:
        return "medium"

    # Check for hard complexity indicators
    hard_count = sum(1 for kw in COMPLEXITY_KEYWORDS_HARD if kw in query_lower)
    if hard_count >= 2:
        return "hard"
    if hard_count == 1:
        return "complex"

    # Check for medium complexity indicators
    medium_count = sum(1 for kw in COMPLEXITY_KEYWORDS_MEDIUM if kw in query_lower)
    if medium_count >= 2:
        return "medium"

    # Certain ticket types default to higher complexity
    if ticket_type in ("complaint", "account_change"):
        return "medium"

    return "simple"


def _extract_action(query: str, ticket_type: str = "") -> tuple:
    """Extract required action and details from query.
    Returns (action, details_dict).
    Phase 7: Added investigate_billing for pricing disputes; prioritizes
    investigation patterns over plan_change when the user is questioning
    charges rather than requesting changes."""
    # First pass: find ALL matching actions with their positions
    matches = []
    for pattern, action, detail_key in ACTION_PATTERNS:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            details = {}
            if detail_key and match.lastindex and match.lastindex >= 1 and match.group(1):
                details[detail_key] = float(match.group(1))
            matches.append((match.start(), action, details))

    if not matches:
        return "provide_info", {}

    # If multiple actions match, pick the one that appears first in the query
    # (the primary intent is usually stated first)
    matches.sort(key=lambda x: x[0])

    # Phase 7: If we matched both plan_change AND investigate_billing,
    # prefer investigate_billing — the user is questioning, not requesting.
    actions_found = [m[1] for m in matches]
    if "investigate_billing" in actions_found:
        idx = actions_found.index("investigate_billing")
        return matches[idx][1], matches[idx][2]

    # Otherwise return the first match
    return matches[0][1], matches[0][2]


# ── DynamicContext: Pull customer context (non-LLM) ───────────────


def _pull_dynamic_context(
    tenant_id: str, customer_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Pull relevant context for classification.
    In production: fetches from DB/Redis. For now: enriches from input."""
    ctx = {
        "account_tier": customer_context.get("account_tier", "free"),
        "customer_tenure_days": customer_context.get("customer_tenure_days", 0),
        "recent_ticket_count": customer_context.get("recent_ticket_count", 0),
        "lifetime_value": customer_context.get("lifetime_value", 0),
    }

    # Simple rule: long-tenure + high-value = likely simple resolution
    if ctx["customer_tenure_days"] > 365 and ctx["lifetime_value"] > 500:
        ctx["priority_customer"] = True
    else:
        ctx["priority_customer"] = False

    return ctx


# ── MetaLearner: Predict from past patterns (non-LLM) ─────────────


def _meta_learner_predict(
    tenant_id: str, ticket_type: str, complexity: str, query: str = ""
) -> Dict[str, Any]:
    """Phase 6: Predict routing based on Wiki Section A past patterns.
    
    Searches the AI Wiki for similar ticket patterns and uses
    their historical outcomes to guide routing.
    Non-LLM — keyword search only.
    """
    from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store
    
    wiki = get_wiki_store()
    
    try:
        patterns = wiki.find_similar_patterns(
            tenant_id=tenant_id, query=query,
            ticket_type=ticket_type, max_results=3,
        )
        
        if not patterns:
            return {
                "similar_tickets_found": 0,
                "historical_accuracy": 0.0,
                "suggested_path": None,
                "wiki_boosted": False,
            }
        
        # Analyze patterns for routing guidance
        total_quality = sum(p["quality_achieved"] for p in patterns)
        avg_quality = total_quality / len(patterns)
        
        # Check if similar tickets were successfully resolved
        successful = sum(1 for p in patterns if p["quality_achieved"] >= 0.90)
        success_rate = successful / len(patterns)
        
        # Extract most common techniques that worked
        all_techniques = []
        for p in patterns:
            all_techniques.extend(p.get("techniques_that_worked", []))
        technique_counts = {}
        for t in all_techniques:
            technique_counts[t] = technique_counts.get(t, 0) + 1
        top_techniques = sorted(technique_counts, key=technique_counts.get, reverse=True)[:5]
        
        # Suggest path based on historical success
        suggested_path = None
        if success_rate >= 0.7 and avg_quality >= 0.90:
            # Similar tickets were resolved well — suggest same approach
            suggested_path = "complex_path" if complexity in ("complex", "hard") else "simple_medium_path"
        elif success_rate < 0.3:
            # Similar tickets struggled — suggest complex path for more thorough reasoning
            suggested_path = "complex_path"
        
        return {
            "similar_tickets_found": len(patterns),
            "historical_accuracy": round(success_rate, 3),
            "suggested_path": suggested_path,
            "wiki_boosted": True,
            "avg_historical_quality": round(avg_quality, 4),
            "top_techniques": top_techniques,
            "pattern_entry_keys": [p["entry_key"] for p in patterns],
        }
    except Exception as e:
        return {
            "similar_tickets_found": 0,
            "historical_accuracy": 0.0,
            "suggested_path": None,
            "wiki_boosted": False,
        }


# ── UoT: Measure classification confidence (LLM) ──────────────────


async def _uot_measure_confidence(
    query: str, ticket_type: str, complexity: str, action: str
) -> float:
    """Use LLM to measure uncertainty in classification.
    Returns confidence score 0.0-1.0."""

    prompt = f"""You are a ticket classification validator. Given the classification below, rate your confidence that it is correct.

Customer message: "{query}"
Classified as: type={ticket_type}, complexity={complexity}, action={action}

Rate your confidence from 0.0 to 1.0. Consider:
- Does the ticket type match the customer's intent?
- Is the complexity level appropriate?
- Is the required action correct?

Respond with ONLY a number between 0.0 and 1.0. No explanation."""

    try:
        text = await llm_call(prompt, max_tokens=10, temperature=0.0)
        return parse_confidence(text, default=0.7)
    except Exception as e:
        logger.warning("UoT LLM call failed, using default confidence: %s", e)
        return 0.7


# ── Main Node Function ────────────────────────────────────────────


async def node_1_ingest_classify(state: PipelineV2State) -> dict:
    """Node 1: Ingest + Classify — WHAT is this ticket?

    Runs: SmartRouter → DynamicContext → MetaLearner → UoT
    """
    start = time.time()
    # ── Wave 4: Load and check Jarvis system flags (shutdown) ───────
    system_flags = state.get("system_flags")
    if not system_flags:
        try:
            from app.core.parwa_pipeline.parwa_bridge import load_system_flags
            system_flags = await load_system_flags(state.get("tenant_id", ""))
        except Exception:
            system_flags = {}
    if system_flags.get("global_shutdown"):
        logger.warning("Node 1: GLOBAL SHUTDOWN active — rejecting ticket %s", state["ticket_id"])
        return {
            "status": "rejected",
            "final_response": "System is currently under maintenance. Your request cannot be processed at this time.",
            "technique_log": [{"node": 1, "technique": "JARVIS_SHUTDOWN_CHECK", "duration_ms": 0, "result_summary": "rejected_due_to_shutdown"}],
            "errors": [{"node": "node_1", "error": "global_shutdown_active", "details": "Ticket rejected due to emergency shutdown flag"}],
            "total_token_usage": state.get("total_token_usage", 0),
        }

    query = state["query"]
    tenant_id = state["tenant_id"]
    customer_context = state.get("customer_context", {})
    logs = []

    # 1. SmartRouter: classify ticket type (non-LLM)
    ticket_type, _ = _classify_ticket_type(query)
    logs.append({"node": 1, "technique": "SmartRouter", "duration_ms": 0, "result_summary": f"type={ticket_type}"})

    # 2. SmartRouter: classify complexity (non-LLM)
    complexity = _classify_complexity(query, ticket_type)
    logs.append({"node": 1, "technique": "SmartRouter.complexity", "duration_ms": 0, "result_summary": f"complexity={complexity}"})

    # 3. SmartRouter: extract required action (non-LLM)
    required_action, action_details = _extract_action(query, ticket_type)
    logs.append({"node": 1, "technique": "SmartRouter.action", "duration_ms": 0, "result_summary": f"action={required_action}"})

    # 4. DynamicContext: pull customer context (non-LLM)
    dynamic_ctx = _pull_dynamic_context(tenant_id, customer_context)
    logs.append({"node": 1, "technique": "DynamicContext", "duration_ms": 0, "result_summary": "context_pulled"})

    # 5. MetaLearner: predict from past patterns (Phase 6: reads Wiki Section A)
    ml_result = _meta_learner_predict(tenant_id, ticket_type, complexity, query)
    ml_summary = f"similar={ml_result['similar_tickets_found']}"
    if ml_result.get("wiki_boosted"):
        ml_summary += f" hist_acc={ml_result['historical_accuracy']}"
        if ml_result.get("suggested_path"):
            ml_summary += f" suggest={ml_result['suggested_path']}"
    logs.append({"node": 1, "technique": "MetaLearner", "duration_ms": 0, "result_summary": ml_summary})

    # 6. UoT: measure classification confidence (LLM call)
    confidence = await _uot_measure_confidence(query, ticket_type, complexity, required_action)
    logs.append({"node": 1, "technique": "UoT", "duration_ms": int((time.time() - start) * 1000), "result_summary": f"confidence={confidence:.2f}"})

    # Phase 6: If wiki has seen similar tickets, boost confidence (AFTER LLM call)
    if ml_result.get("wiki_boosted") and ml_result.get("suggested_path"):
        confidence = min(1.0, confidence + 0.05)

    # Routing suggestion: use wiki-guided suggestion if available
    if ml_result.get("suggested_path"):
        routing_suggestion = ml_result["suggested_path"]
    elif complexity in ("simple", "medium"):
        routing_suggestion = "simple_medium_path"
    else:
        routing_suggestion = "complex_path"

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 1 complete: ticket=%s type=%s complexity=%s action=%s confidence=%.2f [%dms]",
        state["ticket_id"], ticket_type, complexity, required_action, confidence, elapsed,
    )

    return {
        "ticket_type": ticket_type,
        "complexity": complexity,
        "required_action": required_action,
        "action_details": action_details,
        "classification_confidence": confidence,
        "routing_suggestion": routing_suggestion,
        "customer_context": {**customer_context, **dynamic_ctx},
        "system_flags": system_flags,
        "technique_log": logs,
        "node_1_token_usage": 1,  # 1 LLM call (UoT)
        "total_token_usage": state.get("total_token_usage", 0) + 1,
    }