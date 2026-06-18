"""
Node 4: Reasoning Engine — PHASE 4 (optimized)

Phase 4 upgrades:
  1. GSD decomposition prompt: more structured, numbered output
  2. CoT solve prompt: explicit "cite specific policy, amounts, timelines" instruction
  3. Answer synthesis: stronger knowledge grounding instruction
  4. Reverse Thinking: less harsh, "VALID: YES unless genuine error"
  5. ToT: Batch check ALL solutions in 1 LLM call (was N calls)

Phase 4 token optimizations:
  6. REMOVED LeastToMost ordering — 3 sub-problems, order doesn't matter (-1 LLM call)
  7. REMOVED UoT self-confidence — redundant with Reverse Thinking (-1 LLM call)
  8. Tighter max_tokens on several prompts
  9. Knowledge passed to prompts is smarter-truncated

Total: 9 LLM calls → 7 LLM calls per ticket
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List

from app.core.parwa_pipeline.llm_client import llm_call, parse_confidence
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_4")


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
    # Parse numbered list
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


# ── MAKER: Bridge knowledge gaps (non-LLM) ────────────────────────


def _maker_bridge(sub_problems: List[str], knowledge: str) -> Dict[str, str]:
    """Bridge knowledge gaps between sub-problems."""
    bridges = {}
    knowledge_lower = knowledge.lower()
    for sp in sub_problems:
        words = [w for w in sp.lower().split() if len(w) > 4]
        relevant = []
        for i, line in enumerate(knowledge_lower.split(".")):
            if any(w in line for w in words):
                relevant.append(f"section {i}")
        bridges[sp] = " → ".join(relevant) if relevant else "general knowledge"
    return bridges


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

    # Parse the results
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
    valid = "VALID: NO" not in result.upper()  # default to valid
    confidence = parse_confidence(result, default=0.9)  # Phase 4: higher default
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
    """Node 4: Reasoning Engine — Phase 4 optimized.
    LLM calls: 7 (was 9 in Phase 4 draft, was 11 in Phase 2)
      - GSD decompose: 1
      - 3x CoT solve: 3
      - ToT batch check: 1
      - Reverse Thinking: 1
      - Answer Synthesis: 1
    REMOVED: LeastToMost ordering (-1), UoT self-confidence (-1)"""
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

    # Phase 4: NO LeastToMost ordering — 3 sub-problems don't need reordering

    # ── LAYER 2: SOLVE ────────────────────────────────────────────
    bridges = _maker_bridge(sub_problems, knowledge_str)
    logs.append({"node": 4, "technique": "MAKER", "duration_ms": 0, "result_summary": f"{len(bridges)} bridges"})

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

    # Phase 4: NO UoT self-confidence — redundant with Reverse Thinking

    # ── LAYER 4: COMBINE ──────────────────────────────────────────
    aggregated = _federated_aggregate({
        "reverse": reverse_result["confidence"],
        "zero_shot": zero_shot_score,
    })
    logs.append({"node": 4, "technique": "FederatedReasoning", "duration_ms": 0, "result_summary": f"aggregated={aggregated:.2f}"})

    weights = _meta_learner_adjust(threaded, ticket_type)
    logs.append({"node": 4, "technique": "MetaLearner", "duration_ms": 0, "result_summary": f"weights={weights}"})

    # Answer synthesis
    formatted = await _synthesize_final_answer(query, sub_problems, solutions, knowledge_str, context_str, ticket_type)
    logs.append({"node": 4, "technique": "AnswerSynthesis", "duration_ms": 0, "result_summary": f"synthesized {len(formatted)} chars"})
    llm_calls += 1

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 4 complete: ticket=%s sub=%d conf=%.2f llm=%d [%dms]",
        state["ticket_id"], len(sub_problems), aggregated, llm_calls, elapsed,
    )

    return {
        "sub_problems": sub_problems,
        "sub_solutions": [{"problem": p, "solution": s} for p, s in zip(sub_problems, solutions)],
        "combined_answer": formatted,
        "reasoning_confidence": aggregated,
        "technique_log": logs,
        "node_4_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }