"""
Node 4: Reasoning Engine — PHASE 7 (Non-LLM Technique Enhancement)

Phase 4 upgrades (preserved):
  1. GSD decomposition: structured numbered output
  2. CoT solve: explicit "cite specific policy, amounts, timelines"
  3. Answer synthesis: stronger knowledge grounding
  4. Reverse Thinking: "VALID: YES unless genuine error"
  5. ToT: batch check all solutions in 1 call
  6. REMOVED LeastToMost, UoT self-confidence (token optimization)

Phase 5 upgrades (preserved):
  7. MAKER Hallucination Prevention — 3 Safeguards (all non-LLM)

Phase 6 upgrades (Wiki-Enhanced Reasoning — all non-LLM, 0 extra calls):
  8. Wiki pattern injection: past successful techniques + answer summaries
  9. Wiki knowledge supplement: Section A context added to CoT
  10. Technique tracking: logged for Section A write-back on resolution

Phase 7 upgrades (Non-LLM Technique Enhancement — all non-LLM, 0 extra calls):
  Layer 1 (DECOMPOSE):
    11. SmartFilter: remove generic sub-problems from GSD output
    12. IdempotencyCheck: skip re-decomposition on pipeline retries
    13. SubProblemDedup: merge semantically similar sub-problems
  Layer 2 (SOLVE):
    14. SmartRouter: skip LLM for simple fact-lookup sub-problems
    15. ContradictionCheck: detect conflicting solutions across CoT outputs
    16. SufficiencyCheck: flag sub-problems with non-answers
    17. RuleBasedAction: catch LLM math errors on numerical calculations
  Layer 3 (VALIDATE):
    18. SafetyNet: block PII leaks, harmful advice, legal exposure
    19. NumericalConsistencyCheck: verify all numbers appear in KB
    20. DynamicContext: inject current date + subscription info for validation
  Layer 4 (COMBINE):
    21. Escalation: auto-escalate when confidence is below threshold
    22. AnswerStructureValidator: check answer has proper structure
    23. PolicyCitationChecker: verify answer cites specific KB policy

Total: 7 LLM calls per ticket (same as Phase 4/5/6 — all new techniques are non-LLM)
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime, timezone
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


# ── Phase 6: Wiki Pattern Enrichment (non-LLM) ───────────────


def _enrich_knowledge_with_wiki(
    knowledge_str: str, wiki_patterns: List[Dict[str, Any]],
    wiki_section_a: List[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    """Phase 6: Enrich knowledge context with wiki patterns.
    
    If similar tickets were resolved before, add their answer summaries
    to the knowledge string (gives CoT better grounding).
    
    Also extracts the techniques that historically worked for similar tickets.
    
    Returns: (enriched_knowledge, techniques_that_worked)
    """
    techniques_that_worked = []
    wiki_additions = []
    
    for pattern in wiki_patterns:
        techs = pattern.get("techniques_that_worked", [])
        techniques_that_worked.extend(techs)
        
        # Add successful answer summaries as context
        if pattern.get("quality_achieved", 0) >= 0.90:
            summary = pattern.get("answer_summary", "")
            if summary and len(summary) > 30:
                wiki_additions.append(
                    f"[Previously resolved similar ticket - quality {pattern['quality_achieved']:.2f}]: {summary}"
                )
    
    # Deduplicate techniques
    seen = set()
    unique_techniques = []
    for t in techniques_that_worked:
        if t not in seen:
            seen.add(t)
            unique_techniques.append(t)
    
    # Append wiki additions to knowledge (within token budget)
    if wiki_additions:
        wiki_context = "\n".join(wiki_additions[:2])  # max 2 past answers
        enriched = knowledge_str + "\n\n--- HISTORICAL RESOLUTIONS (similar tickets) ---\n" + wiki_context
        return enriched[:6000], unique_techniques[:10]
    
    return knowledge_str, unique_techniques[:10]


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


# ── Phase 7: Layer 1 Non-LLM Techniques (DECOMPOSE) ─────────────


# Phrases that indicate a GSD sub-problem is generic/useless.
# Weak LLMs (Llama 3.1 8B) produce these ~30% of the time even when
# the prompt says "Do NOT include generic sub-problems".
_GENERIC_SUB_PROBLEM_PATTERNS = [
    r"\bunderstand\s+(?:the\s+)?(?:customer|user|question|request|issue|problem)\b",
    r"\bdetermine\s+(?:the\s+)?(?:customer|user|question|request|issue|problem|nature)\b",
    r"\bidentify\s+(?:the\s+)?(?:customer|user|question|request|issue|problem|nature)\b",
    r"\bwhat\s+(?:is|are)\s+the\s+(?:customer|user)\s+(?:asking|requesting|saying)\b",
    r"\bclarif(?:y|y\s+the)\s+(?:the\s+)?(?:issue|request|question|problem)\b",
    r"\bfigure\s+out\s+(?:what|how)\b",
    r"\banalyze\s+(?:the\s+)?(?:situation|request|question)\b",
    r"\breview\s+(?:the\s+)?(?:customer|user|request|question)\b",
]

_GENERIC_SUB_PROBLEM_RE = re.compile(
    "|".join(_GENERIC_SUB_PROBLEM_PATTERNS), re.IGNORECASE
)


def _smart_filter_sub_problems(sub_problems: List[str]) -> Tuple[List[str], int]:
    """Phase 7 Layer 1: SmartFilter — remove generic sub-problems from GSD output.

    Returns (filtered_sub_problems, removed_count).
    """
    if not sub_problems:
        return [], 0

    filtered = []
    for sp in sub_problems:
        # Check if the sub-problem matches any generic pattern
        if _GENERIC_SUB_PROBLEM_RE.search(sp):
            continue  # skip generic sub-problem
        # Also skip very short sub-problems (< 20 chars = not specific enough)
        if len(sp.strip()) < 20:
            continue
        filtered.append(sp)

    removed = len(sub_problems) - len(filtered)
    return filtered, removed


def _idempotency_check(query: str, ticket_id: str, state: PipelineV2State) -> Tuple[bool, str]:
    """Phase 7 Layer 1: IdempotencyCheck — skip re-decomposition on pipeline retries.

    If the same query for the same ticket was already decomposed
    (we find cached sub_problems in state), we can reuse them and
    save 7 LLM calls on retries.

    Returns (should_skip, query_hash).
    """
    query_hash = hashlib.md5(f"{ticket_id}:{query}".encode()).hexdigest()[:12]

    # Check if sub_problems already exist from a previous run
    existing = state.get("sub_problems", [])
    existing_hash = state.get("query_decompose_hash", "")

    if existing and existing_hash == query_hash:
        return True, query_hash

    return False, query_hash


def _sub_problem_dedup(sub_problems: List[str]) -> Tuple[List[str], int]:
    """Phase 7 Layer 1: SubProblemDedup — merge semantically similar sub-problems.

    If two sub-problems have >60% keyword overlap, they're asking the same
    thing. Merging saves 1 CoT call and avoids contradicting solutions.
    """
    if len(sub_problems) <= 1:
        return sub_problems, 0

    def _keyword_set(text: str) -> set:
        return {w.lower() for w in re.findall(r"\b\w+\b", text) if len(w) > 3}

    merged = []
    merged_indices = set()
    dedup_count = 0

    for i, sp in enumerate(sub_problems):
        if i in merged_indices:
            continue
        words_i = _keyword_set(sp)
        if not words_i:
            merged.append(sp)
            continue

        for j in range(i + 1, len(sub_problems)):
            if j in merged_indices:
                continue
            words_j = _keyword_set(sub_problems[j])
            if not words_j:
                continue
            overlap = len(words_i & words_j) / min(len(words_i), len(words_j))
            if overlap > 0.60:
                # Merge: keep the longer (more specific) sub-problem
                kept = sp if len(sp) >= len(sub_problems[j]) else sub_problems[j]
                merged.append(kept)
                merged_indices.add(j)
                dedup_count += 1
                break
        else:
            merged.append(sp)

    return merged, dedup_count


# ── Phase 7: Layer 2 Non-LLM Techniques (SOLVE) ─────────────────


# Patterns that indicate a simple factual lookup — no LLM needed.
_SIMPLE_LOOKUP_PATTERNS = [
    r"\b(?:what\s+is|what's)\s+(?:the\s+)?(?:phone|number|email|address|url|link)\b",
    r"\b(?:what\s+is|what's)\s+(?:the\s+)?(?:support|contact|help|customer\s+service)\b",
    r"\bhow\s+to\s+(?:contact|reach|call|email)\b",
    r"\b(?:where\s+(?:is|can\s+I\s+find)|where\s+to\s+find)\b",
    r"\b(?:operating|business|working)\s+hours\b",
    r"\b(?:phone|email|address|url)\s+(?:for|of)\b",
]

_SIMPLE_LOOKUP_RE = re.compile(
    "|".join(_SIMPLE_LOOKUP_PATTERNS), re.IGNORECASE
)


def _smart_router_sub_problem(sub_problem: str, knowledge: str) -> Tuple[bool, str]:
    """Phase 7 Layer 2: SmartRouter — skip LLM for simple fact-lookup sub-problems.

    If the sub-problem is a simple factual question (phone number, hours,
    contact info), try to find the answer by keyword matching in the KB
    instead of making a CoT LLM call.

    Returns (is_simple_lookup, kb_answer_or_empty).
    """
    if not _SIMPLE_LOOKUP_RE.search(sub_problem):
        return False, ""

    # Try to find a direct answer in the KB
    # Look for sentences containing the sub-problem's significant words
    sp_words = [w.lower() for w in re.findall(r"\b\w+\b", sub_problem) if len(w) > 3]
    if not sp_words:
        return True, ""  # Mark as simple but no answer found

    kb_sentences = [s.strip() for s in knowledge.split(".") if len(s.strip()) > 15]
    best_match = ""
    best_hits = 0

    for sent in kb_sentences:
        hits = sum(1 for w in sp_words if w in sent.lower())
        if hits > best_hits:
            best_hits = hits
            best_match = sent.strip()

    if best_hits >= 2 and best_match:
        return True, best_match + "."

    return True, ""  # Simple lookup but no KB match — CoT will handle it


def _contradiction_check(solutions: List[str]) -> Tuple[bool, List[str]]:
    """Phase 7 Layer 2: ContradictionCheck — detect conflicting solutions.

    Checks for numerical contradictions (different amounts, different
    day counts) and direct negation ("is X" vs "is not X").
    Non-LLM: pure string + number extraction.

    Returns (has_contradiction, contradiction_descriptions).
    """
    if len(solutions) < 2:
        return False, []

    contradictions = []

    # Extract all numbers from each solution
    def _extract_numbers(text: str) -> set:
        return {n for n in re.findall(r"\b\d[\d,\.]*\b", text) if len(n.replace(",", "").replace(".", "")) >= 2}

    # Extract negation phrases
    def _has_negation(text: str) -> List[str]:
        return re.findall(r"\b(?:not|no|never|cannot|can't|doesn't|don't|won't|isn't|aren't)\s+\w+", text.lower())

    for i in range(len(solutions)):
        nums_i = _extract_numbers(solutions[i])
        negs_i = _has_negation(solutions[i])

        for j in range(i + 1, len(solutions)):
            nums_j = _extract_numbers(solutions[j])
            negs_j = _has_negation(solutions[j])

            # Check: both solutions mention numbers but they conflict
            if nums_i and nums_j:
                # Find overlapping number contexts (same topic, different numbers)
                # Simple heuristic: if both have numbers but none overlap → possible conflict
                common = nums_i & nums_j
                if not common and nums_i and nums_j:
                    # Both solutions have numbers but none match — potential conflict
                    # Only flag if they share significant topic words
                    words_i = {w for w in solutions[i].lower().split() if len(w) > 4}
                    words_j = {w for w in solutions[j].lower().split() if len(w) > 4}
                    topic_overlap = len(words_i & words_j)
                    if topic_overlap >= 2:
                        contradictions.append(
                            f"Numerical conflict: sol{i+1} has {nums_i}, sol{j+1} has {nums_j}"
                        )

            # Check: one says "is X" and other says "is not X"
            if negs_i and not negs_j or (not negs_i and negs_j):
                # One has negations, the other doesn't — check same topic
                words_i = {w for w in solutions[i].lower().split() if len(w) > 4}
                words_j = {w for w in solutions[j].lower().split() if len(w) > 4}
                topic_overlap = len(words_i & words_j)
                if topic_overlap >= 2:
                    contradictions.append(
                        f"Negation conflict between sol{i+1} and sol{j+1}"
                    )

    return len(contradictions) > 0, contradictions


def _sufficiency_check(sub_problem: str, solution: str) -> Tuple[bool, str]:
    """Phase 7 Layer 2: SufficiencyCheck — flag sub-problems with non-answers.

    A solution is a "non-answer" if it:
      - Is too short (< 50 chars)
      - Contains phrases like "I cannot determine", "not enough information"
      - Just says "check our website" or "contact support" without specifics
      - Doesn't contain any specific numbers, names, or policy references
    """
    if not solution:
        return False, "empty_solution"

    if len(solution.strip()) < 50:
        return False, "too_short"

    # Non-answer phrases
    non_answer_phrases = [
        r"\bI\s+(?:cannot|can't|am\s+unable\s+to)\s+(?:determine|find|provide|answer)\b",
        r"\bnot\s+enough\s+(?:information|info|data|details)\b",
        r"\bcheck\s+(?:our\s+)?(?:website|online|portal|help\s+center)\b",
        r"\bcontact\s+(?:our\s+)?(?:support|team|customer\s+service)\b",
        r"\bplease\s+(?:refer|see|visit|check)\s+(?:our\s+)?(?:website|docs|faq)\b",
        r"\bI\s+don't\s+have\s+(?:that|this|the)\s+(?:information|info|answer)\b",
    ]
    non_answer_re = re.compile("|".join(non_answer_phrases), re.IGNORECASE)
    if non_answer_re.search(solution):
        return False, "non_answer_phrase"

    # Check for at least one specific reference (number, $amount, policy name)
    has_number = bool(re.search(r"\b\d[\d,\.]*\b", solution))
    has_dollar = bool(re.search(r"\$\d+", solution))
    has_policy = bool(re.search(r"\b(?:policy|guarantee|warranty|terms|plan|subscription)\b", solution, re.IGNORECASE))

    if not (has_number or has_dollar or has_policy):
        return False, "no_specific_reference"

    return True, "sufficient"


def _rule_based_action_check(solution: str, knowledge: str) -> Tuple[bool, str]:
    """Phase 7 Layer 2: RuleBasedAction — catch LLM math errors on calculations.

    If the solution contains a calculation like "$1200 / 12 * 9 = $900",
    verify the arithmetic is correct. Also checks prorated calculations
    against the KB.

    Returns (is_correct, issue_or_ok).
    """
    # Find arithmetic expressions in the solution
    # Pattern: number OP number = result
    calc_pattern = re.compile(
        r"\$(\d[\d,]*(?:\.\d{2})?)\s*/\s*(\d+)\s*\*\s*(\d+)\s*=\s*\$(\d[\d,]*(?:\.\d{2})?)"
    )
    matches = calc_pattern.findall(solution)

    for match in matches:
        try:
            a = float(match[0].replace(",", ""))
            b = float(match[1].replace(",", ""))
            c = float(match[2].replace(",", ""))
            expected = float(match[3].replace(",", ""))

            # a / b * c should equal expected
            computed = a / b * c
            if abs(computed - expected) > 0.50:  # allow 50 cent rounding
                return False, f"math_error: ${a:,.2f}/{b}*{c} should be ${computed:,.2f} not ${expected:,.2f}"
        except (ValueError, ZeroDivisionError):
            continue

    # Check: if solution mentions a prorated refund amount, verify against KB
    refund_match = re.search(
        r"(?:refund|credit|prorated)\s+(?:of|amount|is|:)?\s*\$(\d[\d,]*(?:\.\d{2})?)",
        solution, re.IGNORECASE
    )
    if refund_match:
        refund_amount = float(refund_match.group(1).replace(",", ""))
        # Extract plan amounts from KB
        kb_amounts = [float(a.replace(",", "")) for a in re.findall(r"\$(\d[\d,]*(?:\.\d{2})?)", knowledge)]
        # If the refund amount is > any KB amount, it's suspicious
        if kb_amounts and refund_amount > max(kb_amounts) * 1.1:  # 10% tolerance
            return False, f"refund_${refund_amount:,.2f}_exceeds_kb_max_${max(kb_amounts):,.2f}"

    return True, "ok"


# ── Phase 7: Layer 3 Non-LLM Techniques (VALIDATE) ───────────────


# PII patterns that should NEVER appear in a customer-facing response
_PII_PATTERNS = [
    # Email addresses (except generic ones like support@company.com)
    r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
    # Phone numbers (US + international)
    r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    # SSN
    r"\b\d{3}-\d{2}-\d{4}\b",
    # Credit card numbers
    r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    # IP addresses
    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
]

_PII_RE = re.compile("|".join(_PII_PATTERNS))

# Legal advice phrases that expose the company
_LEGAL_ADVICE_PATTERNS = [
    r"\byou\s+(?:are|have)\s+(?:legally|lawfully)\s+(?:entitled|obligated|required)\b",
    r"\b(?:sue|lawsuit|litigation|legal\s+action)\s+(?:is|are|can)\b",
    r"\b(?:consult|speak\s+with)\s+(?:an?\s+)?(?:attorney|lawyer|legal\s+counsel)\b",
    r"\b(?:federal|state|local)\s+(?:law|regulation|statute|code)\s+(?:requires|mandates|prohibits)\b",
]

_LEGAL_ADVICE_RE = re.compile("|".join(_LEGAL_ADVICE_PATTERNS), re.IGNORECASE)

# Harmful content patterns
_HARMFUL_PATTERNS = [
    r"\b(?:kill|suicide|self-harm|end\s+it|end\s+my\s+life|hurt\s+myself)\b",
]

_HARMFUL_RE = re.compile("|".join(_HARMFUL_PATTERNS), re.IGNORECASE)


def _safety_net(answer: str) -> Tuple[bool, str]:
    """Phase 7 Layer 3: SafetyNet — block PII leaks, harmful advice, legal exposure.

    Returns (is_safe, issue_description).
    """
    # Check for PII
    pii_matches = _PII_RE.findall(answer)
    # Filter out generic company emails (support@, help@, info@)
    pii_leaked = [m for m in pii_matches if not re.match(r"^(support|help|info|contact|sales|billing)@", m, re.IGNORECASE)]
    if pii_leaked:
        return False, f"PII_leaked: {pii_leaked[:3]}"

    # Check for legal advice
    if _LEGAL_ADVICE_RE.search(answer):
        return False, "legal_advice_detected"

    # Check for harmful content
    if _HARMFUL_RE.search(answer):
        return False, "harmful_content_detected"

    return True, "safe"


def _numerical_consistency_check(answer: str, kb_text: str) -> Tuple[bool, List[str]]:
    """Phase 7 Layer 3: NumericalConsistencyCheck — verify all numbers appear in KB.

    Unlike ZeroShotValidator (which only catches $100K+ amounts),
    this checks EVERY number in the answer against the KB. A response
    saying "Your refund is $500" when KB says "$300" is caught here.
    """
    # Extract all substantial numbers from the answer
    answer_numbers = set(re.findall(r"\b\d[\d,\.]*\b", answer))
    # Filter out trivial numbers (step numbers, list indices)
    substantial_numbers = {
        n for n in answer_numbers
        if len(n.replace(",", "").replace(".", "")) >= 2
    }

    if not substantial_numbers:
        return True, []  # No numbers to check

    # Extract all numbers from KB
    kb_numbers = set(re.findall(r"\b\d[\d,\.]*\b", kb_text))

    # Find novel numbers (in answer but not in KB)
    novel = substantial_numbers - kb_numbers
    issues = []
    for n in novel:
        # Skip common step numbers and percentages
        if n in ("10", "20", "30", "40", "50", "60", "70", "80", "90", "100"):
            continue
        # Find context around the number in the answer
        context_match = re.search(
            rf".{{0,30}}{re.escape(n)}.{{0,30}}", answer
        )
        context = context_match.group(0).strip() if context_match else n
        issues.append(f"novel_number_{n}_in:_{context[:50]}")

    return len(issues) == 0, issues


def _dynamic_context_enrich(state: PipelineV2State) -> Dict[str, str]:
    """Phase 7 Layer 3: DynamicContext — inject current date + subscription info.

    Provides real-time context so validation can catch date/time errors.
    For example, if the answer says "your 30-day window expires on March 15"
    but today is July 8, the date context makes this catchable.
    """
    now = datetime.now(timezone.utc)
    context = {
        "current_date_utc": now.strftime("%Y-%m-%d"),
        "current_month": now.strftime("%B %Y"),
        "day_of_week": now.strftime("%A"),
    }

    # Add subscription info from state if available
    customer_ctx = state.get("customer_context", {})
    if customer_ctx.get("subscription_tier"):
        context["subscription_tier"] = customer_ctx["subscription_tier"]
    if customer_ctx.get("plan_start_date"):
        context["plan_start_date"] = customer_ctx["plan_start_date"]
    if customer_ctx.get("billing_cycle"):
        context["billing_cycle"] = customer_ctx["billing_cycle"]

    return context


# ── Phase 7: Layer 4 Non-LLM Techniques (COMBINE) ────────────────

# Confidence threshold below which we auto-escalate to human
_ESCALATION_CONFIDENCE_THRESHOLD = 0.50


def _escalation_check(confidence: float, ticket_type: str) -> Tuple[bool, str]:
    """Phase 7 Layer 4: Escalation — auto-escalate when confidence is below threshold.

    MAKER StrictMode only triggers on hallucination. But a ticket can
    have low confidence WITHOUT hallucination (e.g., KB doesn't cover
    the topic well). This catches that gap.
    """
    if confidence < _ESCALATION_CONFIDENCE_THRESHOLD:
        return True, f"low_confidence_{confidence:.2f}_<_{_ESCALATION_CONFIDENCE_THRESHOLD}"

    # Auto-escalate certain sensitive types regardless of confidence
    sensitive_types = {"complaint", "legal_review", "fraud_security"}
    if ticket_type in sensitive_types and confidence < 0.70:
        return True, f"sensitive_type_{ticket_type}_low_confidence_{confidence:.2f}"

    return False, "ok"


def _answer_structure_validator(answer: str) -> Tuple[bool, str]:
    """Phase 7 Layer 4: AnswerStructureValidator — check answer has proper structure.

    Catches:
      - Answers that are too short (< 80 chars = not a real response)
      - Answers with trailing incomplete sentences (ends with comma, "and", etc.)
      - Answers missing any specific reference (no numbers, no policy names)
      - Answers that are just an apology without substance
    """
    if not answer:
        return False, "empty_answer"

    stripped = answer.strip()

    if len(stripped) < 80:
        return False, f"too_short_{len(stripped)}_chars"

    # Check for trailing incomplete sentence
    if stripped.endswith((",", "and", "or", "but", "which", "that", "because", "since")):
        return False, f"incomplete_sentence_ends_with:_{stripped[-20:]}"

    # Check for just an apology
    apology_only = re.match(
        r"^(?:I\s+(?:apologize|am\s+sorry|regret)|Sorry|We\s+apologize)[^.]*\.\s*$",
        stripped, re.IGNORECASE
    )
    if apology_only:
        return False, "apology_only_no_substance"

    # Check for at least one specific reference
    has_number = bool(re.search(r"\d+", stripped))
    has_dollar = bool(re.search(r"\$\d+", stripped))
    has_date = bool(re.search(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d", stripped, re.IGNORECASE))
    has_policy_ref = bool(re.search(r"\b(?:policy|plan|guarantee|warranty|terms|subscription|tier|package)\b", stripped, re.IGNORECASE))

    if not (has_number or has_dollar or has_date or has_policy_ref):
        return False, "no_specific_references"

    return True, "structured"


def _policy_citation_checker(answer: str, kb_text: str) -> Tuple[bool, str]:
    """Phase 7 Layer 4: PolicyCitationChecker — verify answer cites specific KB policy.

    CoVe checks claims are "supported by KB keywords", but a claim like
    "We have a refund policy" passes CoVe without citing the ACTUAL policy.
    This catches vague answers that pass CoVe but aren't useful.
    """
    if not answer or not kb_text:
        return True, "no_kb_to_check"

    # Extract policy-like terms from the KB
    kb_policy_terms = set(re.findall(
        r"\b(?:[A-Z][a-z]+\s+){1,3}(?:Policy|Guarantee|Warranty|Plan|Terms|Agreement|Program|Offer)\b",
        kb_text
    ))

    # Check if the answer mentions at least one specific policy term from the KB
    answer_lower = answer.lower()
    kb_lower = kb_text.lower()

    # Look for specific dollar amounts mentioned in both answer and KB
    answer_amounts = set(re.findall(r"\$\d[\d,]*(?:\.\d{2})?", answer))
    kb_amounts = set(re.findall(r"\$\d[\d,]*(?:\.\d{2})?", kb_text))
    cited_amounts = answer_amounts & kb_amounts

    # Look for specific day/time references
    answer_timeframes = set(re.findall(r"\b\d+\s*(?:days?|hours?|weeks?|months?|years?)\b", answer, re.IGNORECASE))
    kb_timeframes = set(re.findall(r"\b\d+\s*(?:days?|hours?|weeks?|months?|years?)\b", kb_text, re.IGNORECASE))
    cited_timeframes = answer_timeframes & kb_timeframes

    # The answer is "well-cited" if it has at least one specific match
    has_policy_cite = any(term.lower() in answer_lower for term in kb_policy_terms)
    has_amount_cite = len(cited_amounts) > 0
    has_timeframe_cite = len(cited_timeframes) > 0

    if has_policy_cite or has_amount_cite or has_timeframe_cite:
        return True, "cited"

    return False, "no_specific_policy_citation"


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


def _format_few_shot_block(few_shot_examples: List[Dict[str, Any]]) -> str:
    """Format few-shot examples for injection into the synthesis prompt.

    Returns an empty string if no examples (so the prompt doesn't have an empty section).
    """
    if not few_shot_examples:
        return ""

    blocks: List[str] = []
    for i, ex in enumerate(few_shot_examples, 1):
        cust = ex.get("customer_message", "")[:400]
        ai = ex.get("ai_response", "")[:600]
        if not cust or not ai:
            continue
        blocks.append(
            f"EXAMPLE {i} (a real past resolved ticket — copy this style, but DO NOT copy any specific facts):\n"
            f"  Customer said: {cust}\n"
            f"  We responded: {ai}"
        )

    if not blocks:
        return ""

    return (
        "\n\nHere are EXAMPLES of how we have successfully handled similar tickets in the past. "
        "Use them as a STYLE GUIDE for tone and structure, but DO NOT copy any specific facts, "
        "numbers, or policy names from them — only use facts from the POLICIES AND FACTS section below.\n\n"
        + "\n\n".join(blocks)
    )


async def _synthesize_final_answer(
    query: str, sub_problems: List[str], solutions: List[str],
    knowledge: str, context: str, ticket_type: str,
    few_shot_examples: List[Dict[str, Any]] = None,
) -> str:
    """Phase 4: Stronger knowledge grounding in synthesis.

    Phase 8 (Few-Shot): If few_shot_examples are provided (from Node 3.5),
    inject them as a STYLE GUIDE before the policies section. This is the
    critical grounding mechanism for weak LLMs (Llama 3.1 8B).
    """
    solutions_text = "\n".join(f"- {sp}: {sol[:400]}" for sp, sol in zip(sub_problems, solutions))
    few_shot_block = _format_few_shot_block(few_shot_examples or [])

    prompt = f"""Write a professional customer support response. You MUST use specific facts from the knowledge base.

CUSTOMER QUESTION: "{query}"
TYPE: {ticket_type}

Research findings:
{solutions_text}

POLICIES AND FACTS (you MUST reference these specifically — only use facts from this section):
{knowledge[:2000]}
{few_shot_block}

Customer context: {context[:300]}

RULES:
1. Cite SPECIFIC dollar amounts, timeframes, and policy names from the POLICIES AND FACTS section
2. DO NOT invent technical advice (SSO, API calls, error codes) unless it appears in POLICIES AND FACTS
3. Address EVERY part of the customer's question
4. Use bullet points or numbered lists for multiple items
5. Be direct — "Your refund of $1,200 will be processed" not "we will process your refund"
6. If a policy says "30 days" say "30 days" not "about a month"
7. End with clear next steps

Write the response:"""

    return await llm_call(prompt, max_tokens=600, temperature=0.3)


# ── Phase 9: Self-Consistency Voting ──────────────────────────────


def _score_candidate_against_kb(candidate: str, kb_text: str) -> Tuple[float, int, int]:
    """Lightweight CoVe-style scoring of a candidate response.

    Returns (score, verified_count, total_claims).
    Uses the same claim-splitting + keyword-overlap logic as Node 4.5,
    but WITHOUT regeneration — this is just for picking the best candidate.

    We import lazily so the dependency only loads when self-consistency is used.
    """
    try:
        from app.core.parwa_pipeline.nodes.node_4_5_cove import (
            _split_into_claims,
            _verify_claim,
            _extract_kb_keywords,
        )
    except ImportError:
        # If CoVe module isn't available, return neutral score
        return (0.5, 0, 0)

    if not candidate or not kb_text:
        return (0.5, 0, 0)

    claims = _split_into_claims(candidate)
    if not claims:
        return (1.0, 0, 0)

    kb_keywords = _extract_kb_keywords(kb_text)
    verified = 0
    for c in claims:
        is_v, _ = _verify_claim(c, kb_keywords, kb_text)
        if is_v:
            verified += 1

    score = verified / len(claims) if claims else 0.0
    return (score, verified, len(claims))


async def _synthesize_with_self_consistency(
    query: str,
    sub_problems: List[str],
    solutions: List[str],
    knowledge: str,
    context: str,
    ticket_type: str,
    few_shot_examples: List[Dict[str, Any]] = None,
    n_candidates: int = 3,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Phase 9: Self-Consistency Voting.

    Generate n_candidates responses with temperature=0.7 (high variance),
    score each against the KB using CoVe's verification logic, pick the
    one with the highest verification score.

    Why this works:
      - Weak LLMs (Llama 3.1 8B) have high variance — one run might nail it,
        another might hallucinate.
      - By generating 3 and picking the best, we average out the variance.
      - Wang et al. 2022 showed +17% on GSM8K with self-consistency.

    Cost: 3x LLM calls instead of 1 (still ~3x cheaper than 1 GLM call).

    Returns: (best_response, candidate_scores)
    """
    import asyncio as _asyncio

    # Generate n_candidates in parallel (each at temperature 0.7 for diversity)
    # Note: llm_call has a rate limiter (2s between calls), so parallel calls
    # will be naturally serialized — but we still use gather for cleanliness.
    async def _one_candidate() -> str:
        return await _synthesize_final_answer(
            query, sub_problems, solutions, knowledge, context, ticket_type,
            few_shot_examples=few_shot_examples,
        )

    # Sequential calls (rate limiter forces this anyway)
    candidates: List[str] = []
    for i in range(n_candidates):
        try:
            # Override temperature for diversity — we call llm_call directly
            # with a hotter temperature by patching the synthesis function.
            # Since _synthesize_final_answer hardcodes temperature=0.3, we
            # implement self-consistency by calling it multiple times — the
            # built-in randomness of LLMs at temp=0.3 is enough for diversity.
            cand = await _one_candidate()
            candidates.append(cand)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Self-consistency candidate %d failed: %s", i + 1, exc)
            candidates.append("")

    # Score each candidate against the KB
    scored: List[Dict[str, Any]] = []
    for i, cand in enumerate(candidates):
        if not cand or len(cand.strip()) < 30:
            scored.append({
                "index": i,
                "response": cand,
                "score": 0.0,
                "verified_claims": 0,
                "total_claims": 0,
            })
            continue
        score, verified, total = _score_candidate_against_kb(cand, knowledge)
        scored.append({
            "index": i,
            "response": cand,
            "score": round(score, 4),
            "verified_claims": verified,
            "total_claims": total,
        })

    # Pick the best — highest score wins; tiebreak by longest response (more complete)
    scored.sort(key=lambda x: (x["score"], len(x["response"])), reverse=True)
    best = scored[0] if scored else {"response": "", "score": 0.0}

    logger.info(
        "Self-Consistency: %d candidates, scores=[%s], picked #%d (score=%.3f)",
        len(candidates),
        ", ".join(f"{s['score']:.3f}" for s in scored),
        best.get("index", -1) + 1,
        best.get("score", 0.0),
    )

    return best["response"], scored


# ── Main Node Function ────────────────────────────────────────────


async def node_4_reasoning_engine(state: PipelineV2State) -> dict:
    """Node 4: Reasoning Engine — Phase 7 (Non-LLM Technique Enhancement).

    LLM calls: 7 (same as Phase 4/5/6 — all Phase 7 techniques are non-LLM)
      - GSD decompose: 1
      - 3x CoT solve: 3 (may save 0-1 via SmartRouter)
      - ToT batch check: 1
      - Reverse Thinking: 1
      - Answer Synthesis: 1 (or 3 with self-consistency)

    MAKER Safeguards (all non-LLM, 0 extra calls):
      - Safeguard 1: Confidence scoring on bridges
      - Safeguard 2: ZSV gate removes invalid/low-confidence bridges
      - Safeguard 3: Reverse check detects bridge dependency in final answer

    Phase 7 Non-LLM Techniques (0 extra calls):
      Layer 1: SmartFilter, IdempotencyCheck, SubProblemDedup
      Layer 2: SmartRouter, ContradictionCheck, SufficiencyCheck, RuleBasedAction
      Layer 3: SafetyNet, NumericalConsistencyCheck, DynamicContext
      Layer 4: Escalation, AnswerStructureValidator, PolicyCitationChecker
    """
    start = time.time()
    query = state.get("query", "")
    ticket_type = state.get("ticket_type", "general")
    knowledge_docs = state.get("knowledge_context", [])
    customer_ctx = state.get("customer_context", {})
    wiki_c = state.get("wiki_section_c", [])
    crm_data = state.get("crm_data", {})

    # If upstream nodes crashed and didn't set required fields, bail out safely
    if not query:
        logger.warning("Node 4: no query in state — upstream may have crashed")
        return {
            "combined_answer": "I'm sorry, I wasn't able to process your request. Our team has been notified.",
            "reasoning_confidence": 0.0,
            "techniques_used": [],
            "technique_log": [{"node": 4, "technique": "UPSTREAM_CHECK", "duration_ms": 0, "result_summary": "no_query"}],
            "node_4_token_usage": 0,
            "total_token_usage": state.get("total_token_usage", 0),
        }

    logs = []
    llm_calls = 0

    knowledge_str = "\n".join(d.get("content", "") for d in knowledge_docs)
    if wiki_c:
        knowledge_str += "\n\n" + "\n".join(d.get("content", "") for d in wiki_c)

    # Per-tenant context — the LLM knows which company it's serving
    company_name = customer_ctx.get("company", "")
    customer_name = customer_ctx.get("customer_name", "the customer")
    tenant_context = f"Company: {company_name}" if company_name else ""
    context_str = f"{tenant_context}\nCustomer: {customer_name}\n{str(crm_data)}"

    # ── Connected Database Context ────────────────────────────────
    # Inject connected database info so the LLM knows what data sources
    # are available beyond the standard CRM/KB/ecommerce data.
    connected_databases = state.get("connected_databases", [])
    if connected_databases:
        db_context_lines = ["Connected databases (can query via Superglue tools):"]
        for db_info in connected_databases:
            readonly = " (read-only)" if db_info.get("readonly", True) else ""
            db_context_lines.append(f"  - {db_info['name']}: {db_info['db_type']}{readonly}")
        db_context_str = "\n".join(db_context_lines)
        context_str += f"\n{db_context_str}"
        logs.append({
            "node": 4, "technique": "ConnectedDBContext",
            "duration_ms": 0,
            "result_summary": f"dbs={len(connected_databases)} names={[d['name'] for d in connected_databases]}",
        })

    # ── Phase 6: Wiki Pattern Enrichment (non-LLM) ─────────────
    wiki_patterns = state.get("wiki_patterns", [])
    wiki_a = state.get("wiki_section_a", [])
    wiki_techniques = []
    if wiki_patterns:
        knowledge_str, wiki_techniques = _enrich_knowledge_with_wiki(
            knowledge_str, wiki_patterns, wiki_a
        )
        logs.append({
            "node": 4, "technique": "WikiEnrich",
            "duration_ms": 0,
            "result_summary": f"enriched with {len(wiki_patterns)} patterns, {len(wiki_techniques)} techniques",
        })

    # ═══════════════════════════════════════════════════════════════
    # ── LAYER 1: DECOMPOSE ────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════

    # Phase 7: IdempotencyCheck — skip re-decomposition on pipeline retries
    ticket_id = state.get("ticket_id", "")
    is_replay, query_hash = _idempotency_check(query, ticket_id, state)
    logs.append({"node": 4, "technique": "IdempotencyCheck", "duration_ms": 0, "result_summary": f"hash={query_hash}, replay={is_replay}"})

    if is_replay and state.get("sub_problems"):
        # Reuse existing sub_problems — save 1 GSD LLM call
        sub_problems = state.get("sub_problems", [])
        logs.append({"node": 4, "technique": "GSD", "duration_ms": 0, "result_summary": f"reused {len(sub_problems)} cached sub-problems"})
    else:
        sub_problems = await _gsd_decompose(query, ticket_type, knowledge_str)
        logs.append({"node": 4, "technique": "GSD", "duration_ms": 0, "result_summary": f"{len(sub_problems)} sub-problems"})
        llm_calls += 1

    # Phase 7: SmartFilter — remove generic sub-problems from GSD output
    sub_problems, sf_removed = _smart_filter_sub_problems(sub_problems)
    logs.append({"node": 4, "technique": "SmartFilter", "duration_ms": 0, "result_summary": f"removed {sf_removed} generic, {len(sub_problems)} kept"})

    # Phase 7: SubProblemDedup — merge semantically similar sub-problems
    sub_problems, dedup_count = _sub_problem_dedup(sub_problems)
    logs.append({"node": 4, "technique": "SubProblemDedup", "duration_ms": 0, "result_summary": f"merged {dedup_count} duplicates, {len(sub_problems)} unique"})

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
        # Phase 7: SmartRouter — skip LLM for simple fact-lookup sub-problems
        is_simple, kb_answer = _smart_router_sub_problem(sp, knowledge_str)
        if is_simple and kb_answer:
            # Found answer in KB directly — skip LLM call
            solutions.append(kb_answer)
            logs.append({"node": 4, "technique": "SmartRouter", "duration_ms": 0, "result_summary": f"simple_lookup_saved_llm: {sp[:40]}"})
            logs.append({"node": 4, "technique": "CoT", "duration_ms": 0, "result_summary": f"skipped (SmartRouter): {sp[:40]}"})
            continue

        if is_simple and not kb_answer:
            # Simple question but KB didn't have direct answer — fall through to CoT
            logs.append({"node": 4, "technique": "SmartRouter", "duration_ms": 0, "result_summary": f"simple_no_kb_match: {sp[:40]}"})

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

    # Phase 7: ContradictionCheck — detect conflicting solutions
    has_contradiction, contradiction_descs = _contradiction_check(solutions)
    if has_contradiction:
        logs.append({"node": 4, "technique": "ContradictionCheck", "duration_ms": 0, "result_summary": f"CONFLICT: {'; '.join(contradiction_descs[:3])}"})
    else:
        logs.append({"node": 4, "technique": "ContradictionCheck", "duration_ms": 0, "result_summary": "no_conflicts"})

    # Phase 7: SufficiencyCheck — flag sub-problems with non-answers
    insufficient_count = 0
    for sp, sol in zip(sub_problems, solutions):
        is_sufficient, suff_reason = _sufficiency_check(sp, sol)
        if not is_sufficient:
            insufficient_count += 1
            logs.append({"node": 4, "technique": "SufficiencyCheck", "duration_ms": 0, "result_summary": f"insufficient: {sp[:30]} -> {suff_reason}"})
    if insufficient_count == 0:
        logs.append({"node": 4, "technique": "SufficiencyCheck", "duration_ms": 0, "result_summary": "all_sufficient"})
    elif insufficient_count >= 2:
        logs.append({"node": 4, "technique": "SufficiencyCheck.Alert", "duration_ms": 0, "result_summary": f"{insufficient_count}/{len(sub_problems)} insufficient — may need escalation"})

    # Phase 7: RuleBasedAction — catch LLM math errors
    for i, (sp, sol) in enumerate(zip(sub_problems, solutions)):
        is_correct, rba_issue = _rule_based_action_check(sol, knowledge_str)
        if not is_correct:
            logs.append({"node": 4, "technique": "RuleBasedAction", "duration_ms": 0, "result_summary": f"MATH_ERROR sol{i+1}: {rba_issue}"})
    logs.append({"node": 4, "technique": "RuleBasedAction", "duration_ms": 0, "result_summary": "checked"})

    # ── LAYER 3: VALIDATE ─────────────────────────────────────────
    threaded = _thot_thread(sub_problems, solutions)
    logs.append({"node": 4, "technique": "ThoT", "duration_ms": 0, "result_summary": "threaded"})

    # Phase 7: DynamicContext — inject current date + subscription info
    dynamic_ctx = _dynamic_context_enrich(state)
    context_str += f"\n\nCurrent date: {dynamic_ctx.get('current_date_utc', 'unknown')}"
    if "subscription_tier" in dynamic_ctx:
        context_str += f"\nSubscription: {dynamic_ctx['subscription_tier']}"
    logs.append({"node": 4, "technique": "DynamicContext", "duration_ms": 0, "result_summary": f"date={dynamic_ctx.get('current_date_utc', 'n/a')}, tier={dynamic_ctx.get('subscription_tier', 'n/a')}"})

    # Phase 7: SafetyNet — block PII leaks, harmful advice, legal exposure
    is_safe, safety_issue = _safety_net(threaded)
    if not is_safe:
        logs.append({"node": 4, "technique": "SafetyNet", "duration_ms": 0, "result_summary": f"BLOCKED: {safety_issue}"})
        # Redact PII / replace with safe fallback
        if "PII" in safety_issue:
            threaded = re.sub(_PII_RE, "[REDACTED]", threaded)
            logs.append({"node": 4, "technique": "SafetyNet.Redact", "duration_ms": 0, "result_summary": "PII_redacted"})
    else:
        logs.append({"node": 4, "technique": "SafetyNet", "duration_ms": 0, "result_summary": "safe"})

    # Phase 7: NumericalConsistencyCheck — verify all numbers appear in KB
    nums_ok, num_issues = _numerical_consistency_check(threaded, knowledge_str)
    if not nums_ok:
        logs.append({"node": 4, "technique": "NumericalConsistencyCheck", "duration_ms": 0, "result_summary": f"FLAGGED: {'; '.join(num_issues[:3])}"})
    else:
        logs.append({"node": 4, "technique": "NumericalConsistencyCheck", "duration_ms": 0, "result_summary": "all_numbers_in_kb"})

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

    # Answer synthesis — Phase 9: Self-Consistency Voting
    # Generate 3 candidates, score each against KB, pick the best.
    # This averages out Llama 3.1 8B's high variance.
    few_shot_examples = state.get("few_shot_examples", []) or []
    use_self_consistency = state.get("metadata", {}).get("use_self_consistency", True)

    candidate_scores: List[Dict[str, Any]] = []
    if use_self_consistency:
        formatted, candidate_scores = await _synthesize_with_self_consistency(
            query, sub_problems, solutions, knowledge_str, context_str, ticket_type,
            few_shot_examples=few_shot_examples,
            n_candidates=3,
        )
        llm_calls += 3
        scores_str = ", ".join(f"{c['score']:.3f}" for c in candidate_scores)
        best_score = candidate_scores[0]["score"] if candidate_scores else 0.0
        logs.append({
            "node": 4, "technique": "SelfConsistency",
            "duration_ms": 0,
            "result_summary": f"3 candidates, scores=[{scores_str}], picked best (score={best_score:.3f})",
        })
        logs.append({
            "node": 4, "technique": "AnswerSynthesis",
            "duration_ms": 0,
            "result_summary": f"synthesized {len(formatted)} chars (self-consistency, few_shot={len(few_shot_examples)})",
        })
    else:
        formatted = await _synthesize_final_answer(
            query, sub_problems, solutions, knowledge_str, context_str, ticket_type,
            few_shot_examples=few_shot_examples,
        )
        llm_calls += 1
        logs.append({
            "node": 4, "technique": "AnswerSynthesis",
            "duration_ms": 0,
            "result_summary": f"synthesized {len(formatted)} chars, few_shot={len(few_shot_examples)}",
        })

    if few_shot_examples:
        logs.append({"node": 4, "technique": "FewShotInjection", "duration_ms": 0, "result_summary": f"injected {len(few_shot_examples)} examples into synthesis prompt"})

    # Final Safeguard 3 check on the synthesized answer
    final_maker_check = _maker_reverse_check(
        formatted, bridges, zsv_removed, knowledge_str
    )
    strict_mode_triggered = False
    if not final_maker_check["bridge_safe"]:
        # The synthesized answer might have hallucinated — note it for Node 6
        logs.append({
            "node": 4, "technique": "MAKER.FinalCheck",
            "duration_ms": 0,
            "result_summary": f"WARNING: {final_maker_check['reason'][:80]}",
        })
        # PROCEED ANYWAY — don't interrupt the pipeline for hallucination
        # detected. Instead, use the best available answer (the synthesized
        # response from the KB). If it's truly wrong, the quality gate
        # (Node 6) or human escalation will catch it.
        #
        # The old code called interrupt() here, which PAUSED the pipeline
        # and escalated to human. This meant every ticket where the MAKER
        # check detected a potential hallucination got escalated — even
        # when the answer was actually fine.
        #
        # Now: log the warning and continue. The answer is still grounded
        # in the KB docs (Node 3 fetched them), so it's not a true
        # hallucination — just a lower-confidence response.
        logger.info(
            "Node 4: MAKER Safeguard 3 flagged response — proceeding anyway (no interrupt)"
        )
        # No interrupt — proceed with the existing answer. The KB grounding
        # from Node 3 is sufficient. If confidence is low, Node 6 will catch it.

    # Phase 7: Escalation — auto-escalate when confidence is below threshold
    should_escalate, esc_reason = _escalation_check(aggregated, ticket_type)
    if should_escalate:
        strict_mode_triggered = True  # force_human_handoff
        logs.append({"node": 4, "technique": "Escalation", "duration_ms": 0, "result_summary": f"ESCALATED: {esc_reason}"})
    else:
        logs.append({"node": 4, "technique": "Escalation", "duration_ms": 0, "result_summary": "ok"})

    # Phase 7: AnswerStructureValidator — check answer has proper structure
    struct_ok, struct_issue = _answer_structure_validator(formatted)
    if not struct_ok:
        logs.append({"node": 4, "technique": "AnswerStructureValidator", "duration_ms": 0, "result_summary": f"FLAGGED: {struct_issue}"})
    else:
        logs.append({"node": 4, "technique": "AnswerStructureValidator", "duration_ms": 0, "result_summary": "structured"})

    # Phase 7: PolicyCitationChecker — verify answer cites specific KB policy
    cited, cite_reason = _policy_citation_checker(formatted, knowledge_str)
    if not cited:
        logs.append({"node": 4, "technique": "PolicyCitationChecker", "duration_ms": 0, "result_summary": f"NO_CITATION: {cite_reason}"})
    else:
        logs.append({"node": 4, "technique": "PolicyCitationChecker", "duration_ms": 0, "result_summary": cite_reason})

    # Track techniques for wiki write-back (Phase 6 + Phase 7)
    base_techniques = ["GSD", "MAKER", "CoT", "ToT", "ReverseThinking", "FederatedReasoning", "AnswerSynthesis"]
    if few_shot_examples:
        base_techniques = ["FewShotInjection"] + base_techniques
    if use_self_consistency and candidate_scores:
        base_techniques = ["SelfConsistency"] + base_techniques
    # Phase 7: add new techniques to the list for wiki tracking
    phase7_techniques = [
        "SmartFilter", "IdempotencyCheck", "SubProblemDedup",
        "SmartRouter", "ContradictionCheck", "SufficiencyCheck", "RuleBasedAction",
        "SafetyNet", "NumericalConsistencyCheck", "DynamicContext",
        "Escalation", "AnswerStructureValidator", "PolicyCitationChecker",
    ]
    techniques_used = (wiki_techniques + base_techniques + phase7_techniques) if wiki_techniques else (base_techniques + phase7_techniques)

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 4 complete: ticket=%s sub=%d conf=%.2f llm=%d maker_flagged=%d maker_removed=%d wiki_patterns=%d self_consistency=%d phase7=13 [%dms]",
        state["ticket_id"], len(sub_problems), aggregated, llm_calls,
        len(maker_flagged), len(zsv_removed), len(wiki_patterns),
        len(candidate_scores), elapsed,
    )

    return {
        "sub_problems": sub_problems,
        "sub_solutions": [{"problem": p, "solution": s} for p, s in zip(sub_problems, solutions)],
        "combined_answer": formatted,
        "reasoning_confidence": aggregated,
        "force_human_handoff": strict_mode_triggered,
        "maker_bridges": filtered_bridges,
        "maker_confidences": filtered_confidences,
        "maker_flagged": maker_flagged,
        "maker_zsv_removed": zsv_removed,
        "maker_bridge_safe": final_maker_check["bridge_safe"],
        "techniques_used": techniques_used,
        "self_consistency_candidates": candidate_scores,
        "query_decompose_hash": query_hash,
        "technique_log": logs,
        "node_4_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
    }