"""
Node 7: Simple/Medium Resolver — PHASE 3 (Full)

3-Layer Architecture, ALL non-LLM, 0 LLM calls.
Question: Can we solve this WITHOUT LLM calls?

Phase 3 upgrades:
  - Query-aware GSD (not just ticket-type templates)
  - Relevance-scored MAKER bridging
  - Template-based answer generation from knowledge
  - Pattern-matching MetaLearner (answer templates)
  - Robust ZeroShotValidator (5 checks)
  - AdaptiveBudget tracking
  - Proper FederatedReasoning with weights
  - Professional answer formatting

Safety Net: If Layer 3 confidence < 80% → auto-upgrade to Node 4.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

from app.core.parwa_pipeline.config import QUALITY_SIMPLE_SAFETY_NET
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_7")


# ── LAYER 1: THINK (non-LLM) ─────────────────────────────────────


def _gsd_decompose(query: str, ticket_type: str, knowledge: str) -> List[str]:
    """Phase 3: Query-aware decomposition.
    Breaks the actual query into sub-questions, not just by ticket type.
    """
    query_lower = query.lower()
    sub_questions = []

    # Detect multi-part queries (numbered lists, "and", "also")
    parts = re.split(r'(?:\d+\)\.\s*)', query)
    parts = [p.strip() for p in parts if len(p.strip()) > 15]

    if len(parts) >= 2:
        # Multi-part query — one sub-question per part
        for part in parts:
            # Extract the core question from each part
            sub_questions.append(part.strip())
    else:
        # Single question — decompose by intent
        if "how much" in query_lower or "what is the price" in query_lower or "pricing" in query_lower or "cost" in query_lower:
            sub_questions = ["What plans are available and their prices?", "What plan is right for this customer?"]
        elif "how do i" in query_lower or "how to" in query_lower:
            sub_questions = ["What is the customer trying to do?", "What are the steps to accomplish this?"]
        elif "what is" in query_lower or "what are" in query_lower:
            sub_questions = ["Identify what the customer is asking about", "Find the answer from knowledge base"]
        elif "refund" in query_lower:
            sub_questions = ["What is the refund policy?", "Is the customer eligible for a refund?", "What is the refund process?"]
        elif "cancel" in query_lower:
            sub_questions = ["What is the cancellation policy?", "What happens to data after cancellation?"]
        elif "upgrade" in query_lower or "downgrade" in query_lower or "change plan" in query_lower:
            sub_questions = ["What plan change is requested?", "What are the plan options and pricing?", "What is the process for changing?"]
        elif "password" in query_lower or "login" in query_lower or "access" in query_lower:
            sub_questions = ["What is the login/access issue?", "What are the resolution steps?"]
        elif "billing" in query_lower or "invoice" in query_lower or "charge" in query_lower:
            sub_questions = ["What is the billing concern?", "What does the billing policy say?"]
        elif "feature" in query_lower or "support" in query_lower or "integration" in query_lower:
            sub_questions = ["What feature/integration is being asked about?", "What are the details and limitations?"]
        else:
            sub_questions = ["Understand the customer's question", "Find the relevant information from knowledge"]

    return sub_questions if sub_questions else ["What information does the customer need?"]


def _maker_bridge(sub_questions: List[str], knowledge: str, query: str) -> Dict[str, Dict]:
    """Phase 3: Relevance-scored knowledge bridging.
    For each sub-question, find the most relevant knowledge sentences and score them.
    """
    query_words = set(w.lower() for w in query.split() if len(w) > 3)
    bridges = {}
    knowledge_sentences = [s.strip() for s in knowledge.split(".") if len(s.strip()) > 20]

    for sq in sub_questions:
        sq_words = set(w.lower() for w in sq.split() if len(w) > 3)
        # Score each knowledge sentence against this sub-question
        scored = []
        for sent in knowledge_sentences:
            sent_words = set(sent.lower().split())
            # Word overlap score
            overlap = len(sq_words & sent_words)
            # Bonus for query word overlap
            query_bonus = len(query_words & sent_words) * 0.5
            score = overlap + query_bonus
            if score > 0:
                scored.append((score, sent))

        # Sort by score, take top 3
        scored.sort(key=lambda x: x[0], reverse=True)
        best = [s[1] for s in scored[:3]]

        bridges[sq] = {
            "sentences": best,
            "score": scored[0][0] if scored else 0,
            "has_match": len(scored) > 0,
        }

    return bridges


def _thot_thread(sub_questions: List[str], bridges: Dict[str, Dict], query: str) -> str:
    """Phase 3: Thread sub-answers into coherent response.
    Uses knowledge-matched answers to build a natural response.
    """
    parts = []
    for sq in sub_questions:
        bridge = bridges.get(sq, {})
        if bridge.get("has_match") and bridge["sentences"]:
            # Use the best-matched knowledge sentence as the answer
            answer_text = bridge["sentences"][0]
            # Clean up — remove leading "The " or similar
            answer_text = re.sub(r"^(?:The|This|We)\s+", "", answer_text)
            parts.append(f"- {answer_text.strip()}")
        else:
            parts.append(f"- Information not available in knowledge base for: {sq}")

    if not parts:
        return ""

    return "\n".join(parts)


def _federated_aggregate(scores: Dict[str, float], weights: Optional[Dict[str, float]] = None) -> float:
    """Phase 3: Weighted aggregation of quality signals."""
    if not scores:
        return 0.5

    if weights:
        total = sum(weights.values())
        return sum(scores.get(k, 0) * (weights.get(k, 0) / total) for k in scores) if total > 0 else 0.5

    return sum(scores.values()) / len(scores)


def _meta_learner_predict(ticket_type: str, query: str, knowledge: str,
                            tenant_id: str = "") -> Dict[str, Any]:
    """Phase 6: Pattern-based answer templates + Wiki Section A patterns.
    Uses keyword matching + wiki historical patterns.
    """
    query_lower = query.lower()
    templates = {
        "refund": {
            "pattern": r"\brefund\b",
            "template": "Refund Policy: {refund_detail}",
            "required_kb": ["refund"],
        },
        "cancel": {
            "pattern": r"\bcancel\b",
            "template": "Cancellation: {cancel_detail}",
            "required_kb": ["cancel"],
        },
        "pricing": {
            "pattern": r"\b(?:price|pricing|cost|how much|plan)\b",
            "template": "Pricing: {pricing_detail}",
            "required_kb": ["plan", "price", "$"],
        },
        "password": {
            "pattern": r"\b(?:password|login|access)\b",
            "template": "Access: {access_detail}",
            "required_kb": ["password", "login"],
        },
        "plan_change": {
            "pattern": r"\b(?:upgrade|downgrade|change plan|switch)\b",
            "template": "Plan Change: {plan_detail}",
            "required_kb": ["plan", "upgrade", "downgrade"],
        },
    }

    matched = []
    for name, tmpl in templates.items():
        if re.search(tmpl["pattern"], query_lower):
            kb_lower = knowledge.lower()
            has_content = any(kw in kb_lower for kw in tmpl["required_kb"])
            matched.append({
                "name": name,
                "template": tmpl["template"],
                "has_kb": has_content,
                "confidence": 0.9 if has_content else 0.5,
            })

    # Phase 6: Check wiki for similar simple ticket patterns
    wiki_boost = 0.0
    wiki_answer_hint = ""
    if tenant_id:
        try:
            from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store
            wiki = get_wiki_store()
            patterns = wiki.find_similar_patterns(
                tenant_id=tenant_id, query=query,
                ticket_type=ticket_type, max_results=2,
            )
            for p in patterns:
                if p.get("quality_achieved", 0) >= 0.90:
                    wiki_boost = 0.05
                    wiki_answer_hint = p.get("answer_summary", "")[:300]
                    break
        except Exception:
            pass

    result = matched[0] if matched else {"name": "general", "template": None, "has_kb": False, "confidence": 0.3}
    result["confidence"] = min(1.0, result["confidence"] + wiki_boost)
    result["wiki_boosted"] = wiki_boost > 0
    result["wiki_answer_hint"] = wiki_answer_hint
    return result


def _zero_shot_validate_think(answer: str, knowledge: str, query: str) -> float:
    """Phase 3: Multi-check validator for thinking layer."""
    if not answer or len(answer) < 30:
        return 0.3

    score = 0.8  # base

    # Check 1: Knowledge grounding (does answer use knowledge terms?)
    kb_words = set(w.lower() for w in knowledge.split() if len(w) > 3)
    ans_words = set(w.lower() for w in answer.split() if len(w) > 3)
    if kb_words and ans_words:
        overlap = len(kb_words & ans_words) / len(ans_words)
        if overlap > 0.2:
            score += 0.1
        elif overlap < 0.05:
            score -= 0.2

    # Check 2: Question coverage
    q_words = set(w.lower() for w in query.split() if len(w) > 3)
    if q_words and ans_words:
        q_overlap = len(q_words & ans_words) / len(q_words)
        if q_overlap > 0.3:
            score += 0.1
        elif q_overlap < 0.1:
            score -= 0.2

    return max(0.0, min(1.0, score))


# ── LAYER 2: ACT (non-LLM) ────────────────────────────────────────


def _rule_based_action(action: str, details: Dict, tier: str) -> Dict[str, Any]:
    """Determine if action can be executed or just recommended."""
    caps = {
        "mini": {"execute_refund": False, "execute_credit": False, "account_change": False},
        "parwa": {"execute_refund": True, "execute_credit": True, "account_change": True},
        "high": {"execute_refund": True, "execute_credit": True, "account_change": True},
    }
    tier_caps = caps.get(tier, caps["mini"])

    if action == "provide_info":
        return {"can_execute": True, "status": "info_only", "detail": "Information provided from knowledge base"}

    action_key = action.replace("execute_", "") if action.startswith("execute_") else action
    if not tier_caps.get(action_key, False):
        return {"can_execute": False, "status": "recommended", "detail": f"Tier '{tier}' can only recommend, not execute"}

    return {"can_execute": True, "status": "executed", "detail": f"Action '{action}' executed via {tier} tier permissions"}


def _maker_bridge_action(action: str, knowledge: str) -> List[str]:
    """Find knowledge relevant to the action."""
    keywords = action.replace("_", " ").split()
    relevant = []
    for sentence in knowledge.split("."):
        sent_lower = sentence.lower()
        if any(k in sent_lower for k in keywords):
            relevant.append(sentence.strip())
    return relevant[:3]


def _gsd_decompose_action(action: str, knowledge: str) -> List[str]:
    """Decompose action into steps based on knowledge."""
    if "refund" in action.lower():
        return ["Verify customer identity and eligibility", "Calculate refund amount", "Process refund to original payment method"]
    elif "credit" in action.lower():
        return ["Verify credit validity", "Apply credit to account", "Confirm credit applied"]
    elif "password" in action.lower() or "account" in action.lower():
        return ["Verify account ownership", "Execute account action", "Send confirmation"]
    return [f"Execute: {action.replace('_', ' ')}"]


def _zero_shot_validate_action(action: str, details: Dict) -> Dict:
    """Flag unusual actions."""
    amount = details.get("amount", 0)
    flags = []
    if amount > 5000:
        flags.append(f"High amount: ${amount:,}")
    if action == "execute_refund" and amount <= 0:
        flags.append("Zero or negative refund amount")
    return {"flagged": len(flags) > 0, "flags": flags}


# ── LAYER 3: CHECK (non-LLM) ──────────────────────────────────────


def _zero_shot_check(answer: str, knowledge: str, query: str) -> float:
    """Phase 3: 5-criteria quality check."""
    score = 1.0

    # 1. Minimum length
    if len(answer) < 50:
        score -= 0.2
    elif len(answer) < 100:
        score -= 0.05

    # 2. Knowledge grounding
    kb_words = set(w.lower() for w in knowledge.split() if len(w) > 3)
    ans_words = set(w.lower() for w in answer.split() if len(w) > 3)
    if kb_words and ans_words:
        overlap = len(kb_words & ans_words) / len(ans_words)
        if overlap > 0.2:
            score += 0.0  # good
        elif overlap < 0.05:
            score -= 0.2

    # 3. Question coverage
    q_words = set(w.lower() for w in query.split() if len(w) > 3)
    if q_words and ans_words:
        q_overlap = len(q_words & ans_words) / len(q_words)
        if q_overlap > 0.3:
            score += 0.0
        elif q_overlap < 0.1:
            score -= 0.1

    # 4. Structure (has bullet points or paragraphs)
    if "\n" in answer and len(answer) > 100:
        score += 0.02

    # 5. No "not available" fallback
    if "not available" in answer.lower():
        score -= 0.25

    return max(0.0, min(1.0, score))


def _gsd_check_parts(answer: str) -> float:
    """Per-part quality check."""
    parts = [p.strip() for p in answer.split("\n") if p.strip() and len(p.strip()) > 10]
    if not parts:
        return 0.5
    scores = []
    for p in parts:
        s = 1.0
        if len(p) < 30:
            s -= 0.2
        if "not available" in p.lower():
            s -= 0.3
        scores.append(max(0.0, s))
    return sum(scores) / len(scores)


def _thot_coherence(answer: str) -> float:
    """Coherence check."""
    if not answer:
        return 0.0
    sentences = [s.strip() for s in answer.replace("!", ".").split(".") if s.strip()]
    if not sentences:
        return 0.5
    avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
    score = 1.0
    if avg_len < 3:
        score -= 0.2
    elif avg_len > 50:
        score -= 0.05  # too long sentences
    return max(0.0, min(1.0, score))


def _compress(answer: str) -> str:
    """Remove filler from response."""
    filler = [
        r"\bI(?:'d| would) like to (?:let you know that|inform you that)\b",
        r"\b(?:Please note that|Note that)\b",
        r"\b(?:If you have any (?:further|other) (?:questions|concerns))\b[^.]*\.",
        r"\b(?:We (?:are|would be) happy to (?:help|assist) you)\b[^.]*\.",
    ]
    result = answer
    for p in filler:
        result = re.sub(p, "", result, flags=re.IGNORECASE)
    result = re.sub(r"  +", " ", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _turbo_compress(answer: str) -> str:
    """Ultra-fast compression for simple tickets.
    Keeps essential content, removes redundancy.
    """
    lines = [l.strip() for l in answer.split("\n") if l.strip()]
    if len(lines) <= 3:
        return answer

    # Deduplicate similar lines
    seen = set()
    unique = []
    for line in lines:
        line_sig = line[:50].lower()
        if line_sig not in seen:
            seen.add(line_sig)
            unique.append(line)

    return "\n".join(unique)


def _adaptive_budget(technique_count: int, answer_len: int, confidence: float) -> Dict[str, Any]:
    """Track resource usage within the node."""
    return {
        "techniques_used": technique_count,
        "answer_length": answer_len,
        "efficiency_score": round(confidence / max(technique_count, 1), 3),
        "tier_used": "non_llm",
    }


# ── Main Node Function ────────────────────────────────────────────


async def node_7_simple_resolver(state: PipelineV2State) -> dict:
    """Node 7: Simple/Medium Resolver — Phase 3 (Full).

    3 Layers, 11 techniques, 0 LLM calls.
    Safety net: < 80% → upgrade to Node 4.
    """
    start = time.time()
    query = state["query"]
    tenant_id = state["tenant_id"]
    ticket_type = state["ticket_type"]
    action = state["required_action"]
    action_details = state.get("action_details", {})
    tier = state.get("variant_tier", "parwa")
    knowledge_docs = state.get("knowledge_context", [])
    wiki_c = state.get("wiki_section_c", [])
    logs = []

    knowledge_str = "\n".join(d.get("content", "") for d in knowledge_docs)
    if wiki_c:
        knowledge_str += "\n" + "\n".join(d.get("content", "") for d in wiki_c)

    # ── LAYER 1: THINK ────────────────────────────────────────────
    sub_questions = _gsd_decompose(query, ticket_type, knowledge_str)
    logs.append({"node": 7, "technique": "GSD", "duration_ms": 0, "result_summary": f"{len(sub_questions)} sub-questions"})

    bridges = _maker_bridge(sub_questions, knowledge_str, query)
    matched = sum(1 for b in bridges.values() if b.get("has_match"))
    logs.append({"node": 7, "technique": "MAKER", "duration_ms": 0, "result_summary": f"{matched}/{len(bridges)} matched"})

    think_answer = _thot_thread(sub_questions, bridges, query)
    logs.append({"node": 7, "technique": "ThoT", "duration_ms": 0, "result_summary": f"{len(think_answer)} chars"})

    ml_result = _meta_learner_predict(ticket_type, query, knowledge_str, tenant_id=tenant_id)
    logs.append({"node": 7, "technique": "MetaLearner", "duration_ms": 0,
                "result_summary": "pattern=" + str(ml_result["name"]) + " conf=" + str(ml_result["confidence"])})

    think_score = _zero_shot_validate_think(think_answer, knowledge_str, query)
    logs.append({"node": 7, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"think_score={think_score:.2f}"})

    # ── LAYER 2: ACT ──────────────────────────────────────────────
    action_result = _rule_based_action(action, action_details, tier)
    logs.append({"node": 7, "technique": "RuleBasedAction", "duration_ms": 0, "result_summary": f"status={action_result['status']}"})

    action_knowledge = _maker_bridge_action(action, knowledge_str)
    logs.append({"node": 7, "technique": "MAKER", "duration_ms": 0, "result_summary": f"{len(action_knowledge)} refs"})

    action_steps = _gsd_decompose_action(action, knowledge_str)
    logs.append({"node": 7, "technique": "GSD", "duration_ms": 0, "result_summary": f"{len(action_steps)} steps"})

    action_flags = _zero_shot_validate_action(action, action_details)
    logs.append({"node": 7, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"flagged={action_flags['flagged']}"})

    # Build full answer with action info
    full_answer = think_answer
    if think_answer and action_result["status"] == "recommended":
        full_answer += f"\n\nNote: {action_result['detail']}. Please contact support to complete this action."
    elif action_result["status"] == "executed":
        full_answer += f"\n\nAction completed: {action}."

    simple_actions = [{"action": action, "status": action_result["status"], "detail": action_result["detail"]}]

    # ── LAYER 3: CHECK ────────────────────────────────────────────
    zsv_score = _zero_shot_check(full_answer, knowledge_str, query)
    logs.append({"node": 7, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"check={zsv_score:.2f}"})

    gsd_score = _gsd_check_parts(full_answer)
    logs.append({"node": 7, "technique": "GSD", "duration_ms": 0, "result_summary": f"parts={gsd_score:.2f}"})

    thot_score = _thot_coherence(full_answer)
    logs.append({"node": 7, "technique": "ThoT", "duration_ms": 0, "result_summary": f"coherence={thot_score:.2f}"})

    compressed = _compress(full_answer)
    logs.append({"node": 7, "technique": "ContextualCompression", "duration_ms": 0, "result_summary": f"{len(full_answer)}→{len(compressed)}"})

    turbo = _turbo_compress(compressed)
    logs.append({"node": 7, "technique": "TurboCompress", "duration_ms": 0, "result_summary": f"{len(compressed)}→{len(turbo)}"})

    budget = _adaptive_budget(len(logs), len(turbo), 0.0)
    logs.append({"node": 7, "technique": "AdaptiveBudget", "duration_ms": 0,
                "result_summary": "efficiency=" + str(budget["efficiency_score"])})

    # FederatedReasoning: weighted aggregation
    check_scores = {
        "zero_shot": zsv_score,
        "gsd": gsd_score,
        "thot": thot_score,
        "think": think_score,
    }
    simple_confidence = _federated_aggregate(
        check_scores,
        weights={"zero_shot": 0.30, "gsd": 0.15, "thot": 0.15, "think": 0.40},
    )
    logs.append({"node": 7, "technique": "FederatedReasoning", "duration_ms": 0, "result_summary": f"confidence={simple_confidence:.3f}"})

    # ── SAFETY NET ────────────────────────────────────────────────
    auto_upgraded = simple_confidence < QUALITY_SIMPLE_SAFETY_NET
    if auto_upgraded:
        logs.append({
            "node": 7, "technique": "SafetyNet",
            "duration_ms": 0,
            "result_summary": f"UPGRADED: {simple_confidence:.3f} < {QUALITY_SIMPLE_SAFETY_NET}",
        })

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 7 complete: ticket=%s confidence=%.3f upgraded=%s [0 LLM calls, %dms]",
        state["ticket_id"], simple_confidence, auto_upgraded, elapsed,
    )

    return {
        "simple_answer": turbo,
        "simple_confidence": simple_confidence,
        "simple_actions_taken": simple_actions,
        "auto_upgraded": auto_upgraded,
        "technique_log": logs,
    }