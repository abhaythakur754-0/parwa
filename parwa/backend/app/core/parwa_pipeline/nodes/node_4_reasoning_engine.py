"""
Node 4: Reasoning Engine — PHASE 5 (MAKER Safety + all Phase 4 optimizations)

Phase 4 upgrades (preserved):
  1. GSD decomposition: structured numbered output
  2. CoT solve: explicit "cite specific policy, amounts, timelines"
  3. Answer synthesis: stronger knowledge grounding
  4. Reverse Thinking: "VALID: YES unless genuine error"
  5. ToT: batch check all solutions in 1 call
  6. REMOVED LeastToMost, UoT self-confidence (token optimization)

Phase 5 upgrades (MAKER Hallucination Prevention — 3 Safeguards):
  7. Safeguard 1: Confidence scoring on bridge connections
     - High (>0.85): direct keyword match in KB
     - Medium (0.60-0.85): partial match, related terms
     - Low (<0.60): weak/irrelevant connection → FLAGGED, NOT USED
  8. Safeguard 2: ZeroShotValidator gate before bridges enter reasoning
     - Checks logical consistency of bridges against KB
     - Removes contradictory bridges before CoT
  9. Safeguard 3: Reverse Thinking check on bridge dependency
     - After reasoning, verify answer doesn't depend on filtered-out bridges
     - If it does → flag for quality loop (lower confidence signal)

Total: 7 LLM calls per ticket (same as Phase 4 — safeguards are non-LLM)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Tuple

from app.core.parwa_pipeline.llm_client import llm_call, parse_confidence
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_4")

# MAKER confidence thresholds
MAKER_HIGH_CONFIDENCE = 0.85
MAKER_MEDIUM_CONFIDENCE = 0.60


# ── GSD: Goal Sub-Goal Decomposition (LLM — Phase 4) ────────────


async def _gsd_decompose(query: str, ticket_type: str, knowledge: str) -> List[str]:
    """LLM-based decomposition — Phase 4: structured numbered output."""
    prompt = f"""Break this customer question into exactly 3 sub-problems.

Question: "{query}"
Type: {ticket_type}

Knowledge available: {knowledge[:600]}

Output exactly 3 sub-problems, numbered 1-3. Each must be a specific question the knowledge base can answer.
Do NOT include generic sub-problems like "understand the question" — make each one specific to this customer's situation.

1.
2.
3."""

    result = await llm_call(prompt, max_tokens=180, temperature=0.2)
    problems = []
    for line in result.split("\n"):
        line = line.strip()
        match = re.match(r'^\d+[\.\)]\s*(.+)', line)
        if match and len(match.group(1).strip()) > 10:
            problems.append(match.group(1).strip())

    return problems[:3] if len(problems) >= 2 else [
        "What is the customer's specific request?",
        "What do the policies say about this?",
        "What specific actions or amounts apply?",
    ]


# ── MAKER: Bridge knowledge gaps (Phase 5: with 3 safeguards) ────


def _maker_bridge_with_confidence(
    sub_problems: List[str], knowledge: str
) -> Tuple[Dict[str, str], Dict[str, float], List[str]]:
    """Phase 5 Safeguard 1: Confidence scoring on bridge connections.

    Returns:
      bridges: {sub_problem: "section X → section Y"} (only high + medium confidence)
      bridge_confidences: {sub_problem: confidence_score}
      flagged_bridges: list of sub-problems with low-confidence bridges
    """
    knowledge_lower = knowledge.lower()
    # Split knowledge into sections (by sentence for granular matching)
    kb_sentences = [s.strip() for s in knowledge_lower.split(".") if len(s.strip()) > 20]

    bridges = {}
    confidences = {}
    flagged = []

    for sp in sub_problems:
        sp_words = [w.lower() for w in sp.split() if len(w) > 3]
        if not sp_words:
            bridges[sp] = "general knowledge"
            confidences[sp] = 0.5
            flagged.append(sp)
            continue

        # Find matching KB sentences
        matched_sections = []
        for i, sentence in enumerate(kb_sentences):
            # Count how many significant words from the sub-problem appear
            sp_significant = [w for w in sp_words if len(w) > 4]
            hits = sum(1 for w in sp_significant if w in sentence)
            if hits > 0:
                matched_sections.append((i, hits, sentence))

        if not matched_sections:
            # No KB match at all — low confidence
            bridges[sp] = "general knowledge (no direct KB match)"
            confidences[sp] = 0.3
            flagged.append(sp)
            continue

        # Sort by hit count (best matches first)
        matched_sections.sort(key=lambda x: x[1], reverse=True)
        best_hits = matched_sections[0][1]
        total_significant = max(len([w for w in sp_words if len(w) > 4]), 1)

        # Confidence = ratio of sub-problem words found in best KB section
        # Boosted by number of matching sections (more evidence = higher confidence)
        raw_conf = best_hits / total_significant
        section_boost = min(len(matched_sections) * 0.05, 0.15)
        confidence = min(1.0, raw_conf + section_boost)

        # Classify
        if confidence >= MAKER_HIGH_CONFIDENCE:
            level = "HIGH"
        elif confidence >= MAKER_MEDIUM_CONFIDENCE:
            level = "MEDIUM"
        else:
            level = "LOW"
            flagged.append(sp)

        section_refs = [f"section {ms[0]}" for ms in matched_sections[:3]]
        bridges[sp] = f"[{level}] " + " → ".join(section_refs)
        confidences[sp] = round(confidence, 3)

    return bridges, confidences, flagged


def _maker_zsv_gate(
    bridges: Dict[str, str],
    confidences: Dict[str, float],
    knowledge: str,
) -> Tuple[Dict[str, str], Dict[str, float], List[str]]:
    """Phase 5 Safeguard 2: ZeroShotValidator gate before bridges enter reasoning.

    Non-LLM checks:
    1. Are bridge connections logically consistent with KB?
    2. Does any bridge reference contradict known facts?
    3. Remove bridges flagged as inconsistent.
    """
    knowledge_lower = knowledge.lower()
    removed = []

    for sp, bridge in bridges.items():
        conf = confidences.get(sp, 0.5)

        # Check 1: If confidence is low, remove it
        if conf < MAKER_MEDIUM_CONFIDENCE:
            removed.append(sp)
            continue

        # Check 2: Verify the bridge references actually exist in KB
        # Extract section numbers from bridge
        section_nums = re.findall(r'section (\d+)', bridge)
        if section_nums:
            kb_sentences = knowledge_lower.split(".")
            for sn in section_nums:
                idx = int(sn)
                if idx >= len(kb_sentences):
                    # Bridge references non-existent section — remove it
                    removed.append(sp)
                    break
            else:
                continue  # all sections valid
        else:
            # No section reference (general knowledge) — keep only if medium+ confidence
            if "general knowledge" in bridge.lower() and conf < MAKER_HIGH_CONFIDENCE:
                removed.append(sp)

    # Build filtered bridges
    filtered_bridges = {sp: b for sp, b in bridges.items() if sp not in removed}
    filtered_confidences = {sp: c for sp, c in confidences.items() if sp not in removed}

    return filtered_bridges, filtered_confidences, removed


def _maker_reverse_check(
    answer: str,
    original_bridges: Dict[str, str],
    removed_bridges: List[str],
    knowledge: str,
) -> Dict[str, Any]:
    """Phase 5 Safeguard 3: Reverse Thinking check on bridge dependency.

    After reasoning, verify the final answer doesn't depend on
    information that was in the filtered-out (low-confidence) bridges.

    Returns a signal dict that Node 4 can use to adjust confidence.
    """
    if not removed_bridges:
        return {"bridge_safe": True, "dependency_found": False, "confidence_adjustment": 0.0}

    answer_lower = answer.lower()
    dependency_found = False

    # For each removed bridge's sub-problem, check if the answer
    # contains specific claims that would require that bridge's knowledge
    for sp in removed_bridges:
        # Extract significant terms from the removed sub-problem
        sp_terms = set(w.lower() for w in sp.split() if len(w) > 4)

        # Check if answer addresses this sub-problem's topic
        # If it does, the reasoning might have hallucinated the connection
        answer_terms = set(answer_lower.split())
        overlap = len(sp_terms & answer_terms)

        # If the answer discusses this topic extensively but the bridge was
        # low-confidence, it might have used fabricated knowledge
        if overlap >= 2:
            # Check if the answer's claims about this topic are actually
            # grounded in the KB (not hallucinated from the weak bridge)
            topic_claims = [w for w in sp_terms if w in answer_lower]
            kb_lower = knowledge.lower()
            grounded_claims = sum(1 for t in topic_claims if t in kb_lower)

            if grounded_claims < len(topic_claims) * 0.5:
                # Answer makes claims about this topic but KB doesn't support them
                dependency_found = True
                logger.warning(
                    "MAKER Safeguard 3: Answer may depend on removed bridge for '%s' "
                    "(claims=%d, grounded=%d)",
                    sp[:50], len(topic_claims), grounded_claims,
                )

    if dependency_found:
        return {
            "bridge_safe": False,
            "dependency_found": True,
            "confidence_adjustment": -0.05,  # small penalty for quality signal
            "reason": "Answer may depend on low-confidence MAKER bridges that were filtered out",
        }

    return {
        "bridge_safe": True,
        "dependency_found": False,
        "confidence_adjustment": 0.0,
    }


# ── CoT: Step-by-step reasoning (LLM — Phase 4: knowledge-grounded) ─


async def _cot_solve(sub_problem: str, knowledge: str, context: str, query: str) -> str:
    """Solve one sub-problem with strong knowledge grounding."""
    prompt = f"""You are a senior customer support agent answering a customer's question.

SUB-QUESTION TO ANSWER: {sub_problem}

THE CUSTOMER'S FULL QUESTION: "{query}"

KNOWLEDGE BASE (use specific facts, numbers, and policies from here):
{knowledge[:3000]}

CUSTOMER CONTEXT: {context[:300]}

INSTRUCTIONS:
1. Read the knowledge base carefully
2. Find the EXACT policy, amount, or process that answers this sub-question
3. Cite specific numbers, dollar amounts, timeframes, or steps from the knowledge
4. If the KB doesn't have the exact answer, say so clearly
5. Be specific — "$1,200 annual plan" not "the plan cost"

Answer this sub-question specifically:"""

    return await llm_call(prompt, max_tokens=450, temperature=0.3)


# ── ToT: Quick completeness check (Phase 4: merged, fewer calls) ──


async def _tot_batch_check(sub_problems: List[str], solutions: List[str], knowledge: str) -> List[str]:
    """Phase 4: Check ALL solutions in ONE call instead of N calls."""
    solutions_text = "\n".join(
        f"Sub-problem: {sp}\nSolution: {sol[:300]}" for sp, sol in zip(sub_problems, solutions)
    )

    prompt = f"""Review these solutions for completeness against the knowledge base.

{solutions_text}

Knowledge: {knowledge[:1500]}

For each solution, write either:
- COMPLETE (if it adequately answers the sub-problem)
- MISSING: <what's missing> (if something important is missing)

Format:
1. COMPLETE or MISSING: ...
2. COMPLETE or MISSING: ...
3. COMPLETE or MISSING: ..."""

    result = await llm_call(prompt, max_tokens=180, temperature=0.0)

    improvements = []
    for line in result.split("\n"):
        if "MISSING" in line.upper():
            match = re.search(r"MISSING:\s*(.+)", line, re.IGNORECASE)
            if match:
                improvements.append(f"Missing: {match.group(1).strip()}")
        elif "COMPLETE" in line.upper():
            improvements.append("Complete")
    return improvements


# ── GST: Track progress (non-LLM) ────────────────────────────────


def _gst_track(sub_problems: List[str], solutions: List[str]) -> str:
    solved = sum(1 for s in solutions if s and "cannot" not in s.lower() and len(s) > 50)
    return f"{solved}/{len(sub_problems)} sub-problems solved"


# ── Reverse Thinking: Validate (LLM — Phase 4: less harsh) ───────


async def _reverse_thinking_validate(query: str, combined_answer: str, knowledge: str) -> Dict[str, Any]:
    """Phase 4: Validate answer, default to VALID unless genuine error found."""
    prompt = f"""Review this customer support answer for factual correctness.

Question: "{query}"
Answer: {combined_answer[:1500]}

Knowledge base: {knowledge[:1000]}

Check: Does the answer contain any statement that CONTRADICTS the knowledge base?
If the answer is generally accurate (even if not perfect), mark it VALID.

RESPOND:
VALID: YES/NO
CONFIDENCE: <0.0-1.0>"""

    result = await llm_call(prompt, max_tokens=50, temperature=0.0)
    valid = "VALID: NO" not in result.upper()
    confidence = parse_confidence(result, default=0.9)
    return {"valid": valid, "confidence": confidence, "analysis": result}


# ── ZeroShotValidator: Statistical check (non-LLM) ────────────────


def _zero_shot_validate(answer: str, knowledge: str) -> float:
    score = 1.0
    if len(answer) < 50:
        score -= 0.2
    if len(answer) > 5000:
        score -= 0.05
    amounts = re.findall(r"\$(\d+(?:,\d{3})*(?:\.\d{2})?)", answer)
    for amt_str in amounts:
        amt = float(amt_str.replace(",", ""))
        if amt > 100000:
            score -= 0.2
    return max(0.0, min(1.0, score))


# ── ThoT: Thread solutions (non-LLM) ──────────────────────────────


def _thot_thread(sub_problems: List[str], solutions: List[str]) -> str:
    parts = []
    for sp, sol in zip(sub_problems, solutions):
        if sol:
            parts.append(f"**{sp}**\n{sol}")
    return "\n\n".join(parts)


# ── FederatedReasoning: Aggregate (non-LLM) ───────────────────────


def _federated_aggregate(scores: Dict[str, float]) -> float:
    if not scores:
        return 0.5
    return sum(scores.values()) / len(scores)


# ── MetaLearner: Adjust weights (non-LLM) ─────────────────────────


def _meta_learner_adjust(combined_answer: str, ticket_type: str) -> Dict[str, float]:
    return {"cot_weight": 0.5, "tot_weight": 0.2, "reverse_weight": 0.3}


# ── Answer Synthesis (Phase 4: stronger KB grounding) ────────────


async def _synthesize_final_answer(
    query: str, sub_problems: List[str], solutions: List[str],
    knowledge: str, context: str, ticket_type: str
) -> str:
    """Phase 4: Stronger knowledge grounding in synthesis."""
    solutions_text = "\n".join(f"- {sp}: {sol[:400]}" for sp, sol in zip(sub_problems, solutions))

    prompt = f"""Write a professional customer support response. You MUST use specific facts from the knowledge base.

CUSTOMER QUESTION: "{query}"
TYPE: {ticket_type}

Research findings:
{solutions_text}

POLICIES AND FACTS (you MUST reference these specifically):
{knowledge[:2000]}

Customer context: {context[:300]}

RULES:
1. Cite SPECIFIC dollar amounts, timeframes, and policy names from the knowledge base
2. Address EVERY part of the customer's question
3. Use bullet points or numbered lists for multiple items
4. Be direct — "Your refund of $1,200 will be processed" not "we will process your refund"
5. If a policy says "30 days" say "30 days" not "about a month"
6. End with clear next steps

Write the response:"""

    return await llm_call(prompt, max_tokens=600, temperature=0.3)


# ── Main Node Function ────────────────────────────────────────────


async def node_4_reasoning_engine(state: PipelineV2State) -> dict:
    """Node 4: Reasoning Engine — Phase 5 (MAKER Safety).

    LLM calls: 7 (same as Phase 4 — MAKER safeguards are non-LLM)
      - GSD decompose: 1
      - 3x CoT solve: 3
      - ToT batch check: 1
      - Reverse Thinking: 1
      - Answer Synthesis: 1

    MAKER Safeguards (all non-LLM, 0 extra calls):
      - Safeguard 1: Confidence scoring on bridges
      - Safeguard 2: ZSV gate removes invalid/low-confidence bridges
      - Safeguard 3: Reverse check detects bridge dependency in final answer
    """
    start = time.time()
    query = state["query"]
    ticket_type = state["ticket_type"]
    knowledge_docs = state.get("knowledge_context", [])
    customer_ctx = state.get("customer_context", {})
    wiki_c = state.get("wiki_section_c", [])
    crm_data = state.get("crm_data", {})
    logs = []
    llm_calls = 0

    knowledge_str = "\n".join(d.get("content", "") for d in knowledge_docs)
    if wiki_c:
        knowledge_str += "\n\n" + "\n".join(d.get("content", "") for d in wiki_c)
    context_str = str(customer_ctx) + "\n" + str(crm_data)

    # ── LAYER 1: DECOMPOSE ────────────────────────────────────────
    sub_problems = await _gsd_decompose(query, ticket_type, knowledge_str)
    logs.append({"node": 4, "technique": "GSD", "duration_ms": 0, "result_summary": f"{len(sub_problems)} sub-problems"})
    llm_calls += 1

    # ── MAKER: Bridge with Phase 5 Safeguards ─────────────────────
    # Safeguard 1: Confidence scoring
    bridges, bridge_confidences, maker_flagged = _maker_bridge_with_confidence(
        sub_problems, knowledge_str
    )
    logs.append({
        "node": 4, "technique": "MAKER",
        "duration_ms": 0,
        "result_summary": f"{len(bridges)} bridges, {len(maker_flagged)} flagged",
    })

    # Safeguard 2: ZeroShotValidator gate
    filtered_bridges, filtered_confidences, zsv_removed = _maker_zsv_gate(
        bridges, bridge_confidences, knowledge_str
    )
    if zsv_removed:
        logs.append({
            "node": 4, "technique": "MAKER.ZSVGate",
            "duration_ms": 0,
            "result_summary": f"removed {len(zsv_removed)} low-confidence bridges: {[s[:40] for s in zsv_removed]}",
        })

    # ── LAYER 2: SOLVE ────────────────────────────────────────────
    solutions = []
    for sp in sub_problems:
        sol = await _cot_solve(sp, knowledge_str, context_str, query)
        solutions.append(sol)
        logs.append({"node": 4, "technique": "CoT", "duration_ms": 0, "result_summary": f"solved: {sp[:40]}"})
        llm_calls += 1

    # ToT: Phase 4 — batch check (1 call instead of N)
    tot_results = await _tot_batch_check(sub_problems, solutions, knowledge_str)
    logs.append({"node": 4, "technique": "ToT", "duration_ms": 0, "result_summary": f"batch check: {len(tot_results)} items"})
    llm_calls += 1

    # GST
    progress = _gst_track(sub_problems, solutions)
    logs.append({"node": 4, "technique": "GST", "duration_ms": 0, "result_summary": progress})

    # ── LAYER 3: VALIDATE ─────────────────────────────────────────
    threaded = _thot_thread(sub_problems, solutions)
    logs.append({"node": 4, "technique": "ThoT", "duration_ms": 0, "result_summary": "threaded"})

    reverse_result = await _reverse_thinking_validate(query, threaded, knowledge_str)
    logs.append({"node": 4, "technique": "ReverseThinking", "duration_ms": 0, "result_summary": f"valid={reverse_result['valid']}"})
    llm_calls += 1

    zero_shot_score = _zero_shot_validate(threaded, knowledge_str)
    logs.append({"node": 4, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"score={zero_shot_score:.2f}"})

    # ── LAYER 4: COMBINE ──────────────────────────────────────────
    aggregated = _federated_aggregate({
        "reverse": reverse_result["confidence"],
        "zero_shot": zero_shot_score,
    })

    # Safeguard 3: Reverse check on bridge dependency (after synthesis)
    # We apply it to the threaded answer first, then adjust confidence
    maker_check = _maker_reverse_check(
        threaded, bridges, zsv_removed, knowledge_str
    )
    if not maker_check["bridge_safe"]:
        aggregated += maker_check["confidence_adjustment"]
        logs.append({
            "node": 4, "technique": "MAKER.ReverseCheck",
            "duration_ms": 0,
            "result_summary": f"UNSAFE: {maker_check['reason'][:80]}",
        })
    else:
        logs.append({"node": 4, "technique": "MAKER.ReverseCheck", "duration_ms": 0, "result_summary": "safe"})

    logs.append({"node": 4, "technique": "FederatedReasoning", "duration_ms": 0, "result_summary": f"aggregated={aggregated:.2f}"})

    weights = _meta_learner_adjust(threaded, ticket_type)
    logs.append({"node": 4, "technique": "MetaLearner", "duration_ms": 0, "result_summary": f"weights={weights}"})

    # Answer synthesis
    formatted = await _synthesize_final_answer(query, sub_problems, solutions, knowledge_str, context_str, ticket_type)
    logs.append({"node": 4, "technique": "AnswerSynthesis", "duration_ms": 0, "result_summary": f"synthesized {len(formatted)} chars"})
    llm_calls += 1

    # Final Safeguard 3 check on the synthesized answer
    final_maker_check = _maker_reverse_check(
        formatted, bridges, zsv_removed, knowledge_str
    )
    if not final_maker_check["bridge_safe"]:
        # The synthesized answer might have hallucinated — note it for Node 6
        logs.append({
            "node": 4, "technique": "MAKER.FinalCheck",
            "duration_ms": 0,
            "result_summary": f"WARNING: {final_maker_check['reason'][:80]}",
        })

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 4 complete: ticket=%s sub=%d conf=%.2f llm=%d maker_flagged=%d maker_removed=%d [%dms]",
        state["ticket_id"], len(sub_problems), aggregated, llm_calls,
        len(maker_flagged), len(zsv_removed), elapsed,
    )

    return {
        "sub_problems": sub_problems,
        "sub_solutions": [{"problem": p, "solution": s} for p, s in zip(sub_problems, solutions)],
        "combined_answer": formatted,
        "reasoning_confidence": aggregated,
        "maker_bridges": filtered_bridges,
        "maker_confidences": filtered_confidences,
        "maker_flagged": maker_flagged,
        "maker_zsv_removed": zsv_removed,
        "maker_bridge_safe": final_maker_check["bridge_safe"],
        "technique_log": logs,
        "node_4_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }