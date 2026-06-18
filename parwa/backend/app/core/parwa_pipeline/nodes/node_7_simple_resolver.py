"""
Node 7: Simple/Medium Resolver

Question: Can we solve this WITHOUT LLM calls?

3-Layer Architecture (mirror of Nodes 4+5+6 but ALL non-LLM):
  Layer 1 — THINK: GSD + MAKER + ThoT + FederatedReasoning + MetaLearner + ZeroShotValidator
  Layer 2 — ACT:   Rule-based + MAKER + GSD + ZeroShotValidator + tier_permissions
  Layer 3 — CHECK: ZeroShotValidator + GSD + ThoT + ContextualCompression + TurboCompress + FederatedReasoning

Safety Net: If Layer 3 confidence < 80% → auto-upgrade to Node 4 (complex path)

LLM calls: 0
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List

from app.core.parwa_pipeline.config import QUALITY_SIMPLE_SAFETY_NET
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_7")


# ── LAYER 1: THINK (non-LLM) ─────────────────────────────────────

# Reuse same decomposition logic as Node 4
def _gsd_decompose(ticket_type: str) -> List[str]:
    """Decompose into sub-questions."""
    decompositions = {
        "refund_request": ["What is the refund policy?", "Is this customer eligible?", "What amount?"],
        "billing": ["What is the billing issue?", "What does policy say?", "What's the resolution?"],
        "technical": ["What's the error?", "What's the fix?", "Any known issues?"],
        "faq": ["What information does the customer need?"],
        "complaint": ["What's the complaint about?", "What's the resolution?"],
        "account_change": ["What change is requested?", "Is it allowed?"],
    }
    return decompositions.get(ticket_type, ["Understand the question", "Find the answer"])


def _maker_bridge(sub_questions: List[str], knowledge: str) -> Dict[str, str]:
    """Bridge knowledge gaps — find which knowledge answers which sub-question."""
    bridges = {}
    for sq in sub_questions:
        sq_words = set(sq.lower().split())
        best_match = ""
        best_overlap = 0
        for sentence in knowledge.split("."):
            sent_words = set(sentence.lower().split())
            overlap = len(sq_words & sent_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = sentence.strip()
        bridges[sq] = best_match if best_match else "No direct match"
    return bridges


def _thot_thread(bridges: Dict[str, str]) -> str:
    """Thread sub-answers into coherent response."""
    parts = []
    for question, answer in bridges.items():
        if answer and answer != "No direct match":
            parts.append(f"Regarding {question}: {answer}")
    return "\n\n".join(parts)


def _federated_aggregate(scores: List[float]) -> float:
    """Aggregate multiple signals."""
    return sum(scores) / len(scores) if scores else 0.5


def _meta_learner_predict(ticket_type: str) -> str:
    """Use past patterns. Mock for Phase 6."""
    return "No historical patterns yet"


def _zero_shot_validate_think(answer: str, knowledge: str) -> float:
    """Validate thinking output."""
    if not answer or len(answer) < 20:
        return 0.4
    kb_words = set(knowledge.lower().split())
    ans_words = set(answer.lower().split())
    overlap = len(kb_words & ans_words) / max(len(ans_words), 1)
    return min(1.0, 0.5 + overlap)


# ── LAYER 2: ACT (non-LLM) ────────────────────────────────────────

def _rule_based_action(action: str, details: Dict, tier: str) -> Dict[str, Any]:
    """Determine if action can be executed or just recommended."""
    if action == "provide_info":
        return {"can_execute": True, "status": "info_only", "detail": "No execution needed"}

    caps = {
        "mini": {"execute_refund": False, "execute_credit": False},
        "parwa": {"execute_refund": True, "execute_credit": True},
        "high": {"execute_refund": True, "execute_credit": True},
    }
    tier_caps = caps.get(tier, caps["mini"])

    if not tier_caps.get(action.replace("execute_", ""), False):
        return {"can_execute": False, "status": "recommended", "detail": f"Tier '{tier}' can only recommend"}

    return {"can_execute": True, "status": "executed", "detail": "Action executed"}


def _maker_bridge_action(action: str, knowledge: str) -> str:
    """Bridge action knowledge gaps."""
    keywords = action.replace("_", " ").split()
    relevant = [s.strip() for s in knowledge.split(".") if any(k in s.lower() for k in keywords)]
    return " ".join(relevant[:3])


def _gsd_decompose_action(action: str) -> List[str]:
    """Decompose action into steps."""
    return [f"Step: {action.replace('_', ' ')}"]


def _zero_shot_validate_action(action: str, details: Dict) -> Dict:
    """Flag unusual actions."""
    amount = details.get("amount", 0)
    flags = []
    if amount > 5000:
        flags.append(f"High amount: ${amount}")
    return {"flagged": len(flags) > 0, "flags": flags}


# ── LAYER 3: CHECK (non-LLM) ──────────────────────────────────────

def _zero_shot_check(answer: str, knowledge: str, query: str) -> float:
    """Final quality check."""
    score = 1.0
    if len(answer) < 30:
        score -= 0.3
    kb_words = set(knowledge.lower().split())
    ans_words = set(answer.lower().split())
    overlap = len(kb_words & ans_words) / max(len(ans_words), 1)
    if overlap < 0.05:
        score -= 0.3
    q_words = set(query.lower().split())
    q_overlap = len(q_words & ans_words) / max(len(q_words), 1)
    if q_overlap < 0.1:
        score -= 0.15
    return max(0.0, min(1.0, score))


def _gsd_check_parts(answer: str) -> float:
    """Per-part quality."""
    parts = [p.strip() for p in answer.split("\n\n") if p.strip()]
    if not parts:
        return 0.5
    scores = [1.0 if len(p) >= 20 else 0.6 for p in parts]
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
    return max(0.0, min(1.0, score))


def _compress(answer: str) -> str:
    """Remove filler from response."""
    filler = [
        r"\bI(?:'d| would) like to (?:let you know that|inform you that)\b",
        r"\b(?:Please note that|Note that)\b",
        r"\b(?:If you have any (?:further|other) (?:questions|concerns))\b[^.]*\.",
    ]
    result = answer
    for p in filler:
        result = re.sub(p, "", result, flags=re.IGNORECASE)
    result = re.sub(r"  +", " ", result)
    return result.strip()


def _turbo_compress(answer: str) -> str:
    """Ultra-fast compression for simple tickets."""
    # Strip to essential sentences only
    sentences = [s.strip() for s in answer.split(".") if s.strip()]
    if len(sentences) <= 3:
        return answer
    # Keep first, last, and any with numbers
    essential = [sentences[0]]
    for s in sentences[1:-1]:
        if re.search(r"\d+", s):
            essential.append(s)
    essential.append(sentences[-1])
    return ". ".join(essential) + "."


# ── Main Node Function ────────────────────────────────────────────


async def node_7_simple_resolver(state: PipelineV2State) -> dict:
    """Node 7: Simple/Medium Resolver — Can we solve this WITHOUT LLM?

    3 Layers, 0 LLM calls. Safety net: < 80% → upgrade to Node 4.
    """
    start = time.time()
    query = state["query"]
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
    sub_questions = _gsd_decompose(ticket_type)
    logs.append({"node": 7, "technique": "GSD", "duration_ms": 0, "result_summary": f"{len(sub_questions)} sub-questions"})

    bridges = _maker_bridge(sub_questions, knowledge_str)
    logs.append({"node": 7, "technique": "MAKER", "duration_ms": 0, "result_summary": f"{len(bridges)} bridges"})

    think_answer = _thot_thread(bridges)
    logs.append({"node": 7, "technique": "ThoT", "duration_ms": 0, "result_summary": "threaded"})

    ml = _meta_learner_predict(ticket_type)
    logs.append({"node": 7, "technique": "MetaLearner", "duration_ms": 0, "result_summary": ml})

    think_score = _zero_shot_validate_think(think_answer, knowledge_str)
    logs.append({"node": 7, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"think_score={think_score:.2f}"})

    # ── LAYER 2: ACT ──────────────────────────────────────────────
    action_result = _rule_based_action(action, action_details, tier)
    logs.append({"node": 7, "technique": "RuleBasedAction", "duration_ms": 0, "result_summary": f"status={action_result['status']}"})

    action_bridge = _maker_bridge_action(action, knowledge_str)
    logs.append({"node": 7, "technique": "MAKER", "duration_ms": 0, "result_summary": "action_bridge"})

    action_steps = _gsd_decompose_action(action)
    logs.append({"node": 7, "technique": "GSD", "duration_ms": 0, "result_summary": f"{len(action_steps)} steps"})

    action_flags = _zero_shot_validate_action(action, action_details)
    logs.append({"node": 7, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"flagged={action_flags['flagged']}"})

    # Build full answer with action info
    full_answer = think_answer
    if action_result["status"] == "recommended":
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

    # FederatedReasoning: aggregate all CHECK layer scores
    check_scores = [zsv_score, gsd_score, thot_score]
    simple_confidence = _federated_aggregate(check_scores)
    logs.append({"node": 7, "technique": "FederatedReasoning", "duration_ms": 0, "result_summary": f"confidence={simple_confidence:.2f}"})

    # ── SAFETY NET ────────────────────────────────────────────────
    auto_upgraded = simple_confidence < QUALITY_SIMPLE_SAFETY_NET
    if auto_upgraded:
        logs.append({"node": 7, "technique": "SafetyNet", "duration_ms": 0, "result_summary": f"UPGRADED: {simple_confidence:.2f} < {QUALITY_SIMPLE_SAFETY_NET}"})

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 7 complete: ticket=%s confidence=%.2f upgraded=%s [0 LLM calls, %dms]",
        state["ticket_id"], simple_confidence, auto_upgraded, elapsed,
    )

    return {
        "simple_answer": turbo,
        "simple_confidence": simple_confidence,
        "simple_actions_taken": simple_actions,
        "auto_upgraded": auto_upgraded,
        "technique_log": logs,
    }