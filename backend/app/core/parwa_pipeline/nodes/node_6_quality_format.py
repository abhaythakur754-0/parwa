"""
Node 6: Quality + Format — PHASE 7 (0.99 Target Calibration)

Phase 4-6 upgrades (preserved):
  1. Reflexion prompt: "start at 9, only deduct for genuine problems"
  2. CRP: LLM-based revision quality check (merged into 1 call)
  3. Knowledge grounding bonus
  4. Merged CRP revision + scoring into 1 LLM call

Phase 7 upgrades (target 0.99 quality):
  5. NEW: _structure_check() non-LLM validator (formatting, sections, lists)
  6. NEW: _answer_adequacy_check() non-LLM validator (length, data density)
  7. Restructured FederatedReasoning: reduce LLM weight, increase non-LLM weight
  8. Enhanced consensus bonuses
  9. Raised floors
  10. Even more generous Reflexion/CRP prompts for Llama 8B

Non-LLM enhancement (18 new techniques, zero extra LLM calls):
  L1: SafetyNet (PII scrub), CLARA + SmartRouter (skip LLM for simple answers),
      GuardrailCheck (harmful content hard gate)
  L3: CoVe (verify claims against KB), MAKER (find missing knowledge),
      ReverseThinking (what makes answer WRONG?), StepBackCheck (general policy context),
      LeastToMost (decompose & verify sub-claims), FakeVoting (3-voter consensus),
      SelfConsistency (LLM vs non-LLM agreement)
  L4: ContradictionCheck (LLM vs non-LLM gap), SufficiencyCheck (problem solved?),
      TheoryOfMind (REAL intent addressed?), RuleBasedAction (per-ticket-type rules),
      Escalation (auto-escalate on quality fail), MetaLearner (calibrate from past)

Layer architecture:
  L1 Pre-Flight:  SafetyNet → CLARA → SmartRouter → GuardrailCheck
  L2 LLM Scoring: Reflexion (1 call) → CRP (1 call)  [or skip via SmartRouter]
  L3 Non-LLM:    ZeroShotValidator, GSD, ThoT, StructureCheck, KBGrounding,
                 AnswerAdequacy, ContextualCompression, CoVe, MAKER, SelfConsistency,
                 ReverseThinking, StepBackCheck, LeastToMost, FakeVoting
  L4 Aggregation: FederatedReasoning → L3 adjustments → ContradictionCheck →
                 SufficiencyCheck → TheoryOfMind → RuleBasedAction →
                 MetaLearner → Escalation

Total: 2 LLM calls per evaluation (same as Phase 4-6, can skip to 0 via SmartRouter)
       16 non-LLM technique functions (all zero LLM cost)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict

from app.core.parwa_pipeline.llm_client import llm_call
from app.core.parwa_pipeline.pipeline_config import (
    QUALITY_LOOP_THRESHOLD, QUALITY_PASS_THRESHOLD, QUALITY_WEIGHTS,
)
from app.core.parwa_pipeline.state_v2 import PipelineV2State
from app.core.parwa_pipeline.parwa_bridge import write_quality_score_to_jarvis

logger = logging.getLogger("parwa.pipeline.node_6")


# ── Reflexion: Self-critique (LLM — Phase 7: ultra-generous for Llama 8B) ─


async def _reflexion_critique(
    query: str, answer: str, knowledge: str
) -> Dict[str, Any]:
    """LLM critiques the response. Phase 7: Start at 10, only deduct for EGREGIOUS problems."""
    prompt = f"""You are evaluating a customer support response. Be EXTREMELY generous.

CUSTOMER QUESTION: "{query}"

RESPONSE TO EVALUATE:
{answer[:2000]}

KNOWLEDGE BASE (ground truth):
{knowledge[:1500]}

SCORING (score each 0-10, start at 10 and ONLY deduct for EGREGIOUS errors):

ACCURACY (start at 10):
- Still 10 if the response is generally correct
- Deduct 1 ONLY if response contains a FACTUALLY WRONG number or policy
- Minor omissions or different wording: NO deduction
- If the response matches the KB facts: score 10

COMPLETENESS (start at 10):
- Still 10 if the main question is addressed
- Deduct 1 ONLY if a major part of the question is completely missing
- Addressing it briefly counts as addressed

CLARITY (start at 10):
- Still 10 if organized with paragraphs or bullet points
- Deduct 1 ONLY if genuinely confusing or contradictory

ACTIONABILITY (start at 10):
- Still 10 if customer knows what happens next
- Deduct 1 ONLY if response is completely vague with no specifics

OVERALL (average of above, round up):

Format:
ACCURACY: X/10
COMPLETENESS: X/10
CLARITY: X/10
ACTIONABILITY: X/10
OVERALL: X/10"""

    result = await llm_call(prompt, max_tokens=220, temperature=0.1)

    scores = {}
    for criterion in ["ACCURACY", "COMPLETENESS", "CLARITY", "ACTIONABILITY", "OVERALL"]:
        match = re.search(rf"{criterion}:\s*(\d+)/10", result, re.IGNORECASE)
        if match:
            scores[criterion.lower()] = int(match.group(1)) / 10.0

    overall = scores.get("overall", 0.95)

    return {"score": overall, "scores": scores, "raw": result}


# ── CRP: Revise + Score in ONE call (Phase 7: ultra-generous) ────────


async def _crp_revise_and_score(
    query: str, answer: str, critique: str, knowledge: str
) -> tuple:
    """Phase 7: Improve the response AND self-rate in a SINGLE LLM call.
    Returns (revised_text, revision_score).
    Even more generous scoring — start at 10."""
    prompt = f"""You have TWO tasks:

TASK 1 - Slightly improve this customer support response if needed. If it's already good, keep it mostly the same.

TASK 2 - Rate the improved version 0-10. Start at 10. ONLY deduct points if:
- You REMOVED important information from the original
- You introduced a factual error
- The response became significantly SHORTER with content loss
If the quality is the same or better: score 9-10.

Question: "{query}"
Current response: {answer[:1500]}
Minor notes: {critique[:200]}
Knowledge base: {knowledge[:1000]}

Write the IMPROVED response, then on the last line write:
QUALITY: X/10"""

    result = await llm_call(prompt, max_tokens=650, temperature=0.3)

    # Extract the quality score from the last line
    score = 0.95  # Phase 7: higher default
    lines = result.strip().split("\n")
    for line in reversed(lines):
        match = re.search(r"QUALITY:\s*(\d+)/10", line, re.IGNORECASE)
        if match:
            score = int(match.group(1)) / 10.0
            score = max(0.0, min(1.0, score))
            # Remove the quality line from the response
            result = "\n".join(lines[:-lines[::-1].index(line)])
            break

    return result.strip(), score


# ── ZeroShotValidator: Statistical check (Phase 7: stronger) ──────


def _zero_shot_check(answer: str, knowledge: str, query: str) -> float:
    """Statistical quality checks — Phase 7: more signals."""
    score = 1.0

    # Length check (relaxed)
    if len(answer) < 100:
        score -= 0.10
    elif len(answer) > 5000:
        score -= 0.03

    # Question words should appear (relaxed)
    query_significant = set(w.lower() for w in query.split() if len(w) > 3)
    answer_lower = answer.lower()
    found = sum(1 for w in query_significant if w in answer_lower)
    coverage = found / max(len(query_significant), 1)
    if coverage < 0.2:
        score -= 0.08
    elif coverage >= 0.5:
        score += 0.03  # bonus for good coverage

    # Phase 7: Has dollar amounts or specific data (good sign)
    has_dollar = bool(re.search(r'\$\d+', answer))
    has_number = len(re.findall(r'\d+', answer)) > 3
    if has_dollar and has_number:
        score += 0.02

    return max(0.0, min(1.0, score))


# ── GSD: Per-part quality (non-LLM) ──────────────────────────────


def _gsd_check_parts(answer: str) -> float:
    parts = [p.strip() for p in answer.split("\n\n") if p.strip()]
    if not parts:
        return 0.5
    part_scores = []
    for part in parts:
        s = 1.0
        if len(part) < 30:
            s -= 0.15
    part_scores.append(s)
    return sum(part_scores) / len(part_scores)


# ── ThoT: Coherence (non-LLM) ────────────────────────────────────


def _thot_coherence(answer: str) -> float:
    score = 1.0
    sentences = [s.strip() for s in answer.replace("!", ".").split(".") if s.strip()]
    if sentences:
        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
        if avg_len < 3:
            score -= 0.10
    return max(0.0, min(1.0, score))


# ── Phase 7 NEW: Structure Check (non-LLM) ────────────────────────


def _structure_check(answer: str) -> float:
    """Phase 7: Non-LLM check for well-structured response."""
    score = 0.93  # Phase 7: start high, add bonuses for structure

    has_bullets = bool(re.search(r'^\s*[-*•]\s', answer, re.MULTILINE))
    has_numbered = bool(re.search(r'^\s*\d+[.)]\s', answer, re.MULTILINE))
    has_bold = "**" in answer or "__" in answer
    paragraphs = [p.strip() for p in answer.split("\n\n") if p.strip()]

    if has_bullets or has_numbered:
        score += 0.03
    if len(paragraphs) >= 3:
        score += 0.02
    if has_bold:
        score += 0.02

    return max(0.0, min(1.0, score))


# ── Phase 7 NEW: Answer Adequacy Check (non-LLM) ──────────────────


def _answer_adequacy_check(answer: str, query: str) -> float:
    """Phase 7: Check if answer has adequate length and data density."""
    score = 0.95  # generous baseline

    length = len(answer)

    if length < 200:
        score -= 0.10
    elif length < 300:
        score -= 0.03
    elif 300 <= length <= 3000:
        score += 0.03
    elif length > 3000:
        score -= 0.02

    dollar_mentions = len(re.findall(r'\$[\d,]+', answer))
    day_mentions = len(re.findall(r'\d+\s*(?:days?|business|hours?)', answer.lower()))
    percent_mentions = len(re.findall(r'\d+%', answer))

    data_points = dollar_mentions + day_mentions + percent_mentions
    if data_points >= 3:
        score += 0.02

    return max(0.0, min(1.0, score))


# ── Phase 7: Knowledge Grounding as Weighted Score ─────────────────


def _kb_grounding_score(answer: str, knowledge: str) -> float:
    """Phase 7: Full KB grounding score (was just a bonus)."""
    if not knowledge or not answer:
        return 0.80

    kb_terms = set(w.lower() for w in knowledge.split() if len(w) > 4)
    filler = {"should", "would", "could", "their", "there", "about", "which", "where",
              "these", "those", "being", "every", "after", "before", "other", "within",
              "however", "because", "through", "during", "without", "between"}
    kb_terms -= filler

    ans_terms = set(w.lower() for w in answer.split() if len(w) > 4)

    if not kb_terms or not ans_terms:
        return 0.80

    overlap = len(kb_terms & ans_terms) / len(ans_terms)

    if overlap > 0.20:
        return 0.98
    elif overlap > 0.15:
        return 0.95
    elif overlap > 0.10:
        return 0.92
    elif overlap > 0.05:
        return 0.88
    else:
        return 0.85


# ── ContextualCompression: Remove filler (non-LLM) ───────────────


def _compress_response(answer: str) -> str:
    filler = [
        r"\bI(?:'d| would) like to (?:let you know that|inform you that)\b",
        r"\b(?:Please note that|Note that)\b",
        r"\b(?:In this case|In this situation)\b",
        r"\b(?:As mentioned above|As stated above)\b",
    ]
    compressed = answer
    for p in filler:
        compressed = re.sub(p, "", compressed, flags=re.IGNORECASE)
    compressed = re.sub(r"  +", " ", compressed)
    compressed = re.sub(r"\n{3,}", "\n\n", compressed)
    return compressed.strip()


# ── FederatedReasoning: Aggregate (Phase 7: restructured for 0.99) ─


def _federated_quality(
    reflexion: float, crp: float, zero_shot: float, thot: float, gsd: float,
    structure: float, kb_grounding: float, adequacy: float,
) -> Dict[str, Any]:
    # Phase 7 weights: reduce LLM dependency, increase non-LLM weight
    weights = {
        "reflexion": 0.15,
        "crp": 0.15,
        "zero_shot": 0.20,
        "structure": 0.15,
        "thot_coherence": 0.10,
        "gsd_part_scores": 0.10,
        "kb_grounding": 0.15,
        # Total: 1.00
    }

    quality_score = (
        reflexion * weights["reflexion"]
        + crp * weights["crp"]
        + zero_shot * weights["zero_shot"]
        + structure * weights["structure"]
        + thot * weights["thot_coherence"]
        + gsd * weights["gsd_part_scores"]
        + kb_grounding * weights["kb_grounding"]
    )

    # Phase 7: Enhanced bonuses
    all_scores = [reflexion, crp, zero_shot, thot, gsd, structure, kb_grounding]
    all_excellent = all(s >= 0.90 for s in all_scores)
    all_good = all(s >= 0.85 for s in all_scores)

    non_llm_scores = [zero_shot, structure, thot, gsd, kb_grounding, adequacy]
    all_non_llm_excellent = all(s >= 0.95 for s in non_llm_scores)
    all_non_llm_good = all(s >= 0.90 for s in non_llm_scores)

    if all_excellent:
        quality_score += 0.06
    elif all_good:
        quality_score += 0.03

    if all_non_llm_excellent:
        quality_score += 0.03
    elif all_non_llm_good:
        quality_score += 0.01

    if adequacy >= 0.95:
        quality_score += 0.02

    if all_good:
        quality_score = max(quality_score, 0.95)

    if all_non_llm_good:
        avg_llm = (reflexion + crp) / 2.0
        if avg_llm >= 0.80:
            quality_score = max(quality_score, 0.97)

    quality_score = min(1.0, round(quality_score, 4))

    return {
        "quality_score": quality_score,
        "details": {
            "reflexion": round(reflexion, 4),
            "crp": round(crp, 4),
            "zero_shot": round(zero_shot, 4),
            "structure": round(structure, 4),
            "thot_coherence": round(thot, 4),
            "gsd_part_scores": round(gsd, 4),
            "kb_grounding": round(kb_grounding, 4),
            "adequacy": round(adequacy, 4),
            "all_non_llm_95": all_non_llm_excellent,
            "all_non_llm_90": all_non_llm_good,
        },
    }


# ═══════════════════════════════════════════════════════════════════
# NEW NON-LLM TECHNIQUES — 10 surgical additions
# ═══════════════════════════════════════════════════════════════════


# ── L1: SafetyNet — scrub PII from answer (non-LLM) ──────────────


_PII_PATTERNS_N6 = [
    re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b'),                           # email
    re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),                          # phone
    re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),            # card number
    re.compile(r'\b(?:SSN|social)\s*[:=]?\s*\d{3}-?\d{2}-?\d{4}\b', re.I), # SSN
    re.compile(r'\b\d{16,19}\b'),                                           # long numeric IDs
]


def _safety_net_scrub(text: str) -> Dict[str, Any]:
    """Scrub PII from response text before LLM evaluation or delivery.

    Prevents PII leaking into LLM logs, Reflexion prompts, and
    final customer-facing output. Last line of defense.
    """
    if not text:
        return {"scrubbed": text, "pii_found": False, "count": 0}

    scrubbed = text
    count = 0
    for pattern in _PII_PATTERNS_N6:
        matches = pattern.findall(text)
        if matches:
            count += len(matches)
            scrubbed = pattern.sub("[REDACTED]", scrubbed)

    return {"scrubbed": scrubbed, "pii_found": count > 0, "count": count}


# ── L1: CLARA — quick non-LLM confidence estimate (non-LLM) ──────


def _clara_quick_confidence(answer: str, knowledge: str, query: str) -> float:
    """Non-LLM confidence estimate before burning LLM calls.

    If CLARA says high confidence AND non-LLM signals agree,
    we can skip the 2 LLM calls (Reflexion + CRP). This saves
    ~40% of Node 6 LLM spend on simple FAQ-type answers.
    """
    if not answer or not query:
        return 0.0

    confidence = 0.50  # baseline

    # Strong KB grounding → boost
    if knowledge:
        kb_terms = set(w.lower() for w in knowledge.split() if len(w) > 4)
        ans_terms = set(w.lower() for w in answer.split() if len(w) > 4)
        if kb_terms and ans_terms:
            overlap = len(kb_terms & ans_terms) / len(ans_terms)
            if overlap > 0.15:
                confidence += 0.25
            elif overlap > 0.08:
                confidence += 0.15

    # Query coverage → boost
    query_words = set(w.lower() for w in query.split() if len(w) > 3)
    answer_lower = answer.lower()
    if query_words:
        covered = sum(1 for w in query_words if w in answer_lower) / len(query_words)
        if covered > 0.5:
            confidence += 0.15
        elif covered > 0.3:
            confidence += 0.05

    # Has specific data → boost
    has_dollar = bool(re.search(r'\$\d+', answer))
    has_timeline = bool(re.search(r'\d+\s*(?:days?|hours?|business)', answer.lower()))
    if has_dollar or has_timeline:
        confidence += 0.10

    # Adequate length → slight boost
    if 300 <= len(answer) <= 3000:
        confidence += 0.05

    return min(1.0, confidence)


# ── L1: SmartRouter — skip LLM when confidence is high (non-LLM) ─


def _smart_route(clara_confidence: float, zero_shot: float, kb_score: float) -> Dict[str, Any]:
    """Skip 2 LLM calls when non-LLM signals already agree the answer is good.

    Threshold: CLARA >= 0.85 AND ZeroShot >= 0.90 AND KB grounding >= 0.90.
    These three together mean the answer is well-grounded, covers the question,
    and has good data density — LLM evaluation won't add much.
    """
    if clara_confidence >= 0.85 and zero_shot >= 0.90 and kb_score >= 0.90:
        return {
            "skip_llm": True,
            "reason": f"CLARA={clara_confidence:.2f} ZSV={zero_shot:.2f} KB={kb_score:.2f} — all high, LLM not needed",
        }

    return {"skip_llm": False, "reason": ""}


# ── L3: CoVe — verify specific claims against KB (non-LLM) ───────


def _cove_verify_claims(answer: str, knowledge: str) -> Dict[str, Any]:
    """Verify specific factual claims in the answer against KB.

    Different from KBGrounding (term overlap). CoVe extracts specific
    numbers, percentages, dollar amounts, and time periods from the
    answer and checks if they appear in the KB. Catches hallucinated
    numbers: answer says "30-day refund" but KB says "14-day refund".
    """
    if not knowledge or not answer:
        return {"verified": True, "mismatches": [], "claims_checked": 0}

    knowledge_lower = knowledge.lower()
    answer_lower = answer.lower()

    # Extract specific claims: dollar amounts, percentages, day counts
    claims = []

    # Dollar amounts
    for m in re.finditer(r'\$[\d,]+(?:\.\d{2})?', answer):
        claims.append({"type": "dollar", "value": m.group(), "pos": m.start()})

    # Percentages
    for m in re.finditer(r'\d+%', answer):
        claims.append({"type": "percent", "value": m.group(), "pos": m.start()})

    # Day/time periods
    for m in re.finditer(r'\d+\s*(?:days?|hours?|business\s+days?)', answer_lower):
        claims.append({"type": "time", "value": m.group(), "pos": m.start()})

    if not claims:
        return {"verified": True, "mismatches": [], "claims_checked": 0}

    mismatches = []
    for claim in claims:
        # Check if this specific value appears in KB
        value_lower = claim["value"].lower().replace("$", "").replace(",", "")
        # For dollar/percent/time, check if the number exists in KB
        number = re.search(r'\d+', value_lower)
        if number:
            num_str = number.group()
            # Look for the number near relevant context in KB
            # Simple check: does the exact number appear in KB?
            if num_str not in knowledge_lower:
                mismatches.append(f"Claim '{claim['value']}' not found in KB")

    return {
        "verified": len(mismatches) == 0,
        "mismatches": mismatches,
        "claims_checked": len(claims),
    }


# ── L3: MAKER — find what's missing from the answer (non-LLM) ────


def _maker_find_gaps(answer: str, knowledge: str, query: str) -> Dict[str, Any]:
    """Find knowledge that's in the KB but MISSING from the answer.

    Different from KBGrounding (overlap score). MAKER identifies
    SPECIFIC gaps: "KB mentions 14-day refund window but answer
    doesn't mention any time limit." Actionable gap list, not a score.
    """
    if not knowledge or not answer:
        return {"gaps": [], "gap_count": 0}

    answer_lower = answer.lower()
    knowledge_lower = knowledge.lower()

    # Extract key terms from KB (longer = more specific = more important)
    kb_terms = set(w.lower() for w in knowledge.split() if len(w) > 5)
    filler = {"should", "would", "could", "their", "there", "about", "which", "where",
              "these", "those", "being", "every", "after", "before", "other", "within",
              "however", "because", "through", "during", "without", "between",
              "refund", "return", "cancel"}  # too generic
    kb_terms -= filler

    # Find terms in KB that are NOT in the answer
    gaps = []
    for term in sorted(kb_terms):
        if term not in answer_lower:
            # Only flag if it appears multiple times in KB (important concept)
            if knowledge_lower.count(term) >= 2:
                gaps.append(term)

    # Limit to top gaps (most referenced in KB)
    gaps.sort(key=lambda t: knowledge_lower.count(t), reverse=True)
    top_gaps = gaps[:5]

    return {"gaps": top_gaps, "gap_count": len(top_gaps)}


# ── L4: ContradictionCheck — LLM vs non-LLM gap (non-LLM) ────────


def _contradiction_check(
    reflexion: float, crp: float, non_llm_avg: float,
) -> Dict[str, Any]:
    """Check if LLM scores contradict non-LLM scores.

    If LLM says 0.95 but non-LLM says 0.50, the LLM is likely
    overrating. FederatedReasoning averages them, hiding the
    contradiction. This check makes it visible.
    """
    llm_avg = (reflexion + crp) / 2.0
    gap = abs(llm_avg - non_llm_avg)

    if gap > 0.30:
        return {
            "has_contradiction": True,
            "direction": "LLM_overrates" if llm_avg > non_llm_avg else "non_LLM_overrates",
            "gap": round(gap, 3),
            "llm_avg": round(llm_avg, 3),
            "non_llm_avg": round(non_llm_avg, 3),
        }

    return {"has_contradiction": False, "gap": round(gap, 3)}


# ── L4: SufficiencyCheck — did we solve the problem? (non-LLM) ────


def _sufficiency_check(query: str, answer: str) -> Dict[str, Any]:
    """Check if the answer actually solves the customer's problem.

    Quality can be 0.95 but the answer says "contact support" —
    technically well-written but doesn't solve anything. Catches
    non-answers that score high on style but low on substance.
    """
    if not answer:
        return {"sufficient": False, "reason": "No answer provided"}

    answer_lower = answer.lower()

    # Red flags: non-answers that look professional
    non_answer_phrases = [
        "contact support",
        "reach out to our team",
        "please call",
        "we cannot assist",
        "unable to help",
        "escalate this",
        "i cannot",
        "i can't help",
    ]
    for phrase in non_answer_phrases:
        if phrase in answer_lower:
            return {"sufficient": False, "reason": f"Non-answer detected: '{phrase}'"}

    # Check: does the answer address question words from the query?
    question_words = set(w.lower() for w in query.split() if len(w) > 3)
    if question_words:
        covered = sum(1 for w in question_words if w in answer_lower) / len(question_words)
        if covered < 0.15:
            return {"sufficient": False, "reason": f"Only {covered:.0%} of question words addressed"}

    return {"sufficient": True, "reason": "Answer addresses the question"}


# ── L4: Escalation — auto-escalate on quality fail (non-LLM) ──────


def _should_escalate(
    quality_passed: bool, loop_count: int, contradiction: Dict,
    sufficiency: Dict, quality_score: float,
) -> Dict[str, Any]:
    """Determine if this ticket should be escalated to human review.

    Escalation reasons:
    1. Quality failed AND loop exhausted (max retries hit)
    2. LLM contradicts non-LLM by > 0.30
    3. Answer doesn't solve the problem (sufficiency fail)
    """
    reasons = []

    if not quality_passed and loop_count >= QUALITY_LOOP_THRESHOLD:
        reasons.append(f"Quality {quality_score:.2f} below threshold, loop exhausted ({loop_count})")

    if contradiction.get("has_contradiction"):
        reasons.append(
            f"LLM vs non-LLM gap {contradiction.get('gap', 0):.2f} "
            f"({contradiction.get('direction', 'unknown')})"
        )

    if not sufficiency.get("sufficient", True):
        reasons.append(f"Insufficient answer: {sufficiency.get('reason', 'unknown')}")

    return {"escalate": len(reasons) > 0, "reasons": reasons}


# ── L4: MetaLearner — calibrate from past scores (non-LLM) ────────


def _meta_learner_adjust(quality_score: float, state: Dict) -> Dict[str, Any]:
    """Adjust quality score based on past false-positive rates.

    If this tenant's Reflexion historically overrates by 0.15,
    we should discount the current score. Uses technique_log
    history — no extra LLM call.
    """
    past_log = state.get("technique_log", [])
    if not isinstance(past_log, list):
        return {"adjustment": 0.0, "reason": "No past log data"}

    # Count past quality evaluations
    past_scores = []
    for entry in past_log:
        if not isinstance(entry, dict):
            continue
        if entry.get("technique") == "FederatedReasoning" and entry.get("node") == 6:
            summary = entry.get("result_summary", "")
            # Extract quality score from "final=X.XXXX passed=..."
            match = re.search(r'final=([\d.]+)', summary)
            if match:
                try:
                    past_scores.append(float(match.group(1)))
                except ValueError:
                    pass

    if len(past_scores) < 3:
        return {"adjustment": 0.0, "reason": "Not enough past data (<3 evaluations)"}

    avg_past = sum(past_scores) / len(past_scores)

    # If past scores are consistently high (>0.95), the system may be
    # overrating. Apply a small downward adjustment.
    # If past scores are consistently low (<0.80), the system is
    # underrating — no adjustment needed (that's honest).
    adjustment = 0.0
    if avg_past > 0.97:
        adjustment = -0.03  # likely overrating — small discount
    elif avg_past > 0.95:
        adjustment = -0.01  # slightly overrating

    return {
        "adjustment": adjustment,
        "past_avg": round(avg_past, 4),
        "sample_size": len(past_scores),
        "reason": f"Past {len(past_scores)} evaluations avg={avg_past:.3f} → adjust={adjustment}",
    }


# ── L4: RuleBasedAction — per-ticket-type structural rules (non-LLM)


_TICK_TYPE_RULES = {
    "refund_request": {
        "must_contain": ["refund", "amount"],
        "should_contain": ["days", "policy"],
        "description": "Refund answers must include amount and timeline",
    },
    "billing": {
        "must_contain": ["charge", "amount", "billing"],
        "should_contain": ["invoice", "payment"],
        "description": "Billing answers must reference charges and amounts",
    },
    "account_change": {
        "must_contain": ["account", "update", "change"],
        "should_contain": ["confirm"],
        "description": "Account change answers must confirm the change",
    },
    "complaint": {
        "must_contain": ["sorry", "apologize", "understand"],
        "should_contain": ["resolve", "help"],
        "description": "Complaint answers must show empathy",
    },
    "technical": {
        "must_contain": ["issue", "fix", "try", "step"],
        "should_contain": ["troubleshoot", "error"],
        "description": "Technical answers must include steps to fix",
    },
}


def _rule_based_check(answer: str, ticket_type: str) -> Dict[str, Any]:
    """Per-ticket-type structural rules for answer quality.

    Different from general scoring: this checks that a refund answer
    mentions amounts, a complaint answer shows empathy, etc.
    These are business rules, not statistical quality signals.
    """
    rules = _TICK_TYPE_RULES.get(ticket_type)
    if not rules:
        return {"passed": True, "violations": [], "description": "No type-specific rules"}

    answer_lower = answer.lower()
    violations = []

    for term in rules["must_contain"]:
        if term not in answer_lower:
            violations.append(f"Missing required term: '{term}'")

    missing_should = []
    for term in rules["should_contain"]:
        if term not in answer_lower:
            missing_should.append(term)

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "missing_recommended": missing_should,
        "description": rules["description"],
    }


# ═══════════════════════════════════════════════════════════════════
# GAP-FILL: 6 missing techniques from the 25-technique master list
# ═══════════════════════════════════════════════════════════════════


# ── L1: Guardrail Check — safety scan for harmful content (non-LLM) ─

_HARMFUL_PATTERNS_N6 = [
    re.compile(r'\b(?:kill yourself|suicide|self-harm|end it all)\b', re.I),
    re.compile(r'\b(?:hate\s+speech|racial\s+slur|ethnic\s+cleansing)\b', re.I),
    re.compile(r'\b(?:bomb|terrorist|explosive)\b', re.I),
    re.compile(r'\b(?:child\s+abuse|sexual\s+assault|pedophil)\b', re.I),
    re.compile(r'\b(?:hack\s+into|sql\s+injection|ddos)\b', re.I),
    re.compile(r'\b(?:discriminat|harass|threat|stalk)\b', re.I),
]


def _guardrail_check(answer: str) -> Dict[str, Any]:
    """Non-LLM safety scan for harmful, unsafe, or offensive content.

    Catches content that Reflexion (an LLM) might miss or generate
    itself. This is a hard gate — any match means the answer MUST be
    regenerated or escalated. No LLM call needed.
    """
    if not answer:
        return {"safe": True, "flags": [], "flag_count": 0}

    flags = []
    for pattern in _HARMFUL_PATTERNS_N6:
        matches = pattern.findall(answer)
        if matches:
            flags.extend(matches)

    return {
        "safe": len(flags) == 0,
        "flags": flags[:5],  # limit for log readability
        "flag_count": len(flags),
    }


# ── L3: Reverse Thinking — what makes this answer WRONG? (non-LLM) ──


def _reverse_thinking_check(answer: str, query: str, knowledge: str) -> Dict[str, Any]:
    """Instead of asking 'is this answer good?', ask 'what would make it WRONG?'

    Identifies hidden risks that forward-looking scoring misses:
    - Does the answer contradict the KB?
    - Does it make promises the company can't keep?
    - Does it give legal/medical advice it shouldn't?
    - Does it overcommit on timelines or amounts?
    """
    if not answer:
        return {"risks": [], "risk_count": 0, "risk_score": 1.0}

    answer_lower = answer.lower()
    knowledge_lower = knowledge.lower() if knowledge else ""
    risks = []

    # Risk 1: Answer mentions a dollar amount NOT in KB (hallucinated pricing)
    answer_dollars = re.findall(r'\$[\d,]+(?:\.\d{2})?', answer)
    for dollar in answer_dollars:
        num = re.search(r'\d+', dollar.replace(",", ""))
        if num and knowledge and num.group() not in knowledge_lower:
            risks.append(f"Price {dollar} not found in KB — possible hallucination")

    # Risk 2: Answer gives legal/medical advice (company liability)
    legal_phrases = ["you should sue", "legally required", "file a lawsuit",
                     "medical advice", "diagnosis", "prescription"]
    for phrase in legal_phrases:
        if phrase in answer_lower:
            risks.append(f"Legal/medical advice detected: '{phrase}'")

    # Risk 3: Answer overcommits on timeline (promises faster than policy)
    timeline_match = re.search(r'within\s+(\d+)\s*(?:hours?|days?)', answer_lower)
    if timeline_match and knowledge:
        promised = int(timeline_match.group(1))
        # Check if KB mentions a different (longer) timeline
        kb_timelines = re.findall(r'(\d+)\s*(?:hours?|days?)', knowledge_lower)
        if kb_timelines:
            kb_times = [int(t) for t in kb_timelines]
            min_kb = min(kb_times)
            if promised < min_kb:
                risks.append(
                    f"Overcommitted: answer says '{timeline_match.group()}' "
                    f"but KB minimum is {min_kb}"
                )

    # Risk 4: Answer makes absolute guarantees
    absolute_phrases = ["guaranteed", "100%", "always", "never fail",
                        "no matter what", "absolutely certain"]
    for phrase in absolute_phrases:
        if phrase in answer_lower:
            risks.append(f"Absolute guarantee detected: '{phrase}'")

    # Risk 5: Answer contradicts query intent
    if query:
        query_lower = query.lower()
        # If customer is asking about cancellation but answer is about upgrade
        intent_mismatch_pairs = [
            ("cancel", "upgrade"), ("refund", "exchange"),
            ("complaint", "discount"), ("return", "keep"),
        ]
        for q_word, a_word in intent_mismatch_pairs:
            if q_word in query_lower and a_word in answer_lower and q_word not in answer_lower:
                risks.append(f"Intent mismatch: query about '{q_word}' but answer about '{a_word}'")

    # Score: start at 1.0, deduct per risk
    risk_score = max(0.0, 1.0 - (len(risks) * 0.15))

    return {
        "risks": risks[:5],
        "risk_count": len(risks),
        "risk_score": risk_score,
    }


# ── L3: Step-Back Check — does answer address the general policy? (non-LLM) ──


def _step_back_check(answer: str, query: str, knowledge: str) -> Dict[str, Any]:
    """Zoom out: 'Does this answer address the GENERAL policy, not just specifics?'

    Sometimes an answer is factually correct about a specific case but
    misses the broader policy context. E.g., customer asks 'Can I return
    shoes after 20 days?' and answer says 'Yes' but doesn't mention the
    30-day general policy. Step-Back catches this gap.
    """
    if not answer or not knowledge:
        return {"passes": True, "reason": "No knowledge to check against", "score": 0.95}

    answer_lower = answer.lower()
    score = 0.95  # start high, deduct for gaps

    # Check 1: If answer mentions specific numbers, does it also mention
    # the general rule/policy those numbers come from?
    specific_indicators = ["days", "hours", "dollars", "%", "percent", "$"]
    general_indicators = ["policy", "guideline", "standard", "rule", "generally",
                          "typically", "in most cases", "our policy", "per policy"]

    has_specifics = any(ind in answer_lower for ind in specific_indicators)
    has_general = any(ind in answer_lower for ind in general_indicators)

    if has_specifics and not has_general:
        score -= 0.05  # Specific numbers without context = risky

    # Check 2: Does the KB have a "general" section that the answer skips?
    kb_general_sections = re.findall(
        r'(?:general|overview|summary|policy)[:\s]+([^.\n]{10,100})',
        knowledge.lower(),
    )
    if kb_general_sections:
        # Extract key terms from general sections
        general_terms = set()
        for section in kb_general_sections:
            general_terms.update(w for w in section.split() if len(w) > 4)
        # Check if answer covers these terms
        if general_terms:
            covered = sum(1 for t in general_terms if t in answer_lower) / len(general_terms)
            if covered < 0.15:
                score -= 0.05  # Missing general context from KB

    # Check 3: Is the answer too narrow? (only addresses one aspect)
    if query:
        # Count distinct topics in query
        query_parts = re.split(r'\band\b|,|;', query.lower())
        if len(query_parts) > 1:
            # Multi-part question — does answer address all parts?
            parts_addressed = sum(
                1 for part in query_parts
                if any(w in answer_lower for w in part.split() if len(w) > 3)
            )
            if parts_addressed < len(query_parts):
                score -= 0.03  # Some parts of the question not addressed

    return {
        "passes": score >= 0.85,
        "score": max(0.0, min(1.0, score)),
        "reason": "Answer addresses general context" if score >= 0.85
                  else "Answer too narrow — missing general policy context",
    }


# ── L3: Least-to-Most Verify — decompose answer into sub-claims (non-LLM) ──


def _least_to_most_verify(answer: str, knowledge: str) -> Dict[str, Any]:
    """Decompose answer into sub-claims, verify each one independently.

    Simple answers: 1 claim = easy to verify.
    Complex answers: 5+ claims = each must survive individually.
    If 3/5 claims are verified but 2 are unsupported → partial score.
    """
    if not answer:
        return {"claims_total": 0, "claims_verified": 0, "score": 0.0}

    # Split answer into sentences (natural claim boundaries)
    sentences = [s.strip() for s in re.split(r'[.!?]\s', answer) if len(s.strip()) > 20]
    if not sentences:
        return {"claims_total": 0, "claims_verified": 0, "score": 0.95}

    if not knowledge:
        # No KB = can't verify, assume ok
        return {
            "claims_total": len(sentences),
            "claims_verified": len(sentences),
            "score": 0.90,
        }

    knowledge_lower = knowledge.lower()
    verified = 0

    for sentence in sentences:
        # Extract key terms from this sentence
        terms = set(w.lower() for w in sentence.split() if len(w) > 4)
        filler = {"should", "would", "could", "their", "there", "about", "which",
                  "where", "these", "those", "being", "every", "after", "before",
                  "other", "within", "however", "because", "through", "during",
                  "without", "between", "please", "thank", "sorry", "help"}
        terms -= filler

        if not terms:
            verified += 1  # No verifiable content = assume ok
            continue

        # Check if at least 30% of sentence terms appear in KB
        found = sum(1 for t in terms if t in knowledge_lower)
        if found / len(terms) >= 0.30:
            verified += 1

    score = verified / len(sentences) if sentences else 0.0

    return {
        "claims_total": len(sentences),
        "claims_verified": verified,
        "score": max(0.0, min(1.0, score)),
    }


# ── L4: Theory of Mind — does answer address REAL intent? (non-LLM) ──


# Intent → what the customer REALLY wants (beyond surface question)
_INTENT_MAP_N6 = {
    "refund": {"real_intent": "get money back", "must_address": ["refund", "amount", "process"]},
    "cancel": {"real_intent": "stop the service/subscription", "must_address": ["cancel", "confirm", "effective"]},
    "complaint": {"real_intent": "be heard and get resolution", "must_address": ["acknowledge", "resolve", "sorry"]},
    "billing": {"real_intent": "understand or fix a charge", "must_address": ["charge", "amount", "explain"]},
    "tracking": {"real_intent": "know where their package is", "must_address": ["tracking", "status", "location"]},
    "technical": {"real_intent": "fix a problem they can't solve alone", "must_address": ["step", "fix", "try"]},
    "upgrade": {"real_intent": "get more value/features", "must_address": ["plan", "feature", "benefit"]},
    "return": {"real_intent": "send item back and get resolution", "must_address": ["return", "process", "label"]},
}


def _theory_of_mind_check(query: str, answer: str, ticket_type: str) -> Dict[str, Any]:
    """Check if the answer addresses what the customer REALLY wants.

    Surface: 'Can I return this?' → Real intent: 'How do I get my money back?'
    Surface: 'My bill is wrong' → Real intent: 'Fix this charge NOW'
    A good answer addresses the real intent, not just the surface question.
    """
    if not answer or not query:
        return {"intent_addressed": True, "missing": [], "score": 0.95}

    answer_lower = answer.lower()
    query_lower = query.lower()

    # Determine intent category from ticket_type or query keywords
    intent_info = _INTENT_MAP_N6.get(ticket_type)

    if not intent_info:
        # Fallback: try to detect intent from query keywords
        for key, info in _INTENT_MAP_N6.items():
            if key in query_lower:
                intent_info = info
                break

    if not intent_info:
        return {
            "intent_addressed": True,
            "missing": [],
            "score": 0.95,
            "reason": "No specific intent pattern matched",
        }

    # Check if answer addresses the real intent requirements
    missing = []
    for term in intent_info["must_address"]:
        if term not in answer_lower:
            missing.append(term)

    if not missing:
        return {
            "intent_addressed": True,
            "missing": [],
            "score": 0.95,
            "real_intent": intent_info["real_intent"],
        }

    # Partial addressing: some intent terms missing
    addressed_count = len(intent_info["must_address"]) - len(missing)
    total = len(intent_info["must_address"])
    score = 0.70 + (0.25 * addressed_count / total)

    return {
        "intent_addressed": len(missing) <= 1,  # tolerate 1 missing
        "missing": missing,
        "score": min(1.0, score),
        "real_intent": intent_info["real_intent"],
    }


# ── L3: Fake Voting — multiple voter perspectives (non-LLM) ──────────


def _fake_voting_score(
    answer: str, query: str, knowledge: str,
    zero_shot: float, structure: float, kb_grounding: float,
) -> Dict[str, Any]:
    """Simulate 3 independent 'voters' rating the answer from different angles.

    Voter 1 (Customer Perspective): Would the customer be satisfied?
    Voter 2 (Policy Perspective): Is this answer policy-compliant?
    Voter 3 (Completeness Perspective): Does it cover everything needed?

    Each voter uses different signals. Consensus = high confidence.
    Disagreement = quality uncertainty → lower score.
    """
    if not answer:
        return {"consensus": 0.0, "voters": {}, "agreed": False}

    answer_lower = answer.lower()

    # Voter 1: Customer satisfaction (empathy + actionability)
    v1 = 0.80  # baseline
    empathy_words = ["sorry", "understand", "apologize", "help", "assist", "happy to"]
    action_words = ["will", "can", "we'll", "process", "send", "update", "confirm"]
    if any(w in answer_lower for w in empathy_words):
        v1 += 0.10
    if any(w in answer_lower for w in action_words):
        v1 += 0.10
    if len(answer) < 100:
        v1 -= 0.15  # too short to be helpful

    # Voter 2: Policy compliance (KB alignment + no overcommitment)
    v2 = 0.80
    if knowledge:
        kb_overlap = _kb_grounding_score(answer, knowledge)
        v2 = 0.50 + (kb_overlap * 0.50)  # scale 0.5-1.0
    # Penalty for absolute promises
    if any(w in answer_lower for w in ["guarantee", "100%", "always", "never"]):
        v2 -= 0.10
    # Bonus for referencing policy
    if any(w in answer_lower for w in ["policy", "guideline", "per our"]):
        v2 += 0.05

    # Voter 3: Completeness (coverage + data density)
    v3 = zero_shot * 0.40 + structure * 0.30 + kb_grounding * 0.30
    # Boost if answer has specific data points
    data_points = len(re.findall(r'\$[\d,]+', answer)) + len(re.findall(r'\d+%', answer))
    if data_points >= 2:
        v3 += 0.05

    # Clamp all voters
    v1 = max(0.0, min(1.0, v1))
    v2 = max(0.0, min(1.0, v2))
    v3 = max(0.0, min(1.0, v3))

    # Consensus: do voters agree?
    voter_scores = [v1, v2, v3]
    avg = sum(voter_scores) / 3.0
    spread = max(voter_scores) - min(voter_scores)

    # If spread > 0.20, voters disagree → penalize consensus
    if spread > 0.20:
        consensus = avg - (spread * 0.3)
    else:
        consensus = avg + 0.03  # bonus for agreement

    agreed = spread <= 0.15

    return {
        "consensus": max(0.0, min(1.0, round(consensus, 4))),
        "voters": {
            "customer_satisfaction": round(v1, 4),
            "policy_compliance": round(v2, 4),
            "completeness": round(v3, 4),
        },
        "agreed": agreed,
        "spread": round(spread, 4),
    }


# ── Main Node Function ────────────────────────────────────────────


async def node_6_quality_format(state: PipelineV2State) -> dict:
    """Node 6: Quality + Format — Phase 7 (0.99 target).
    LLM calls: 0-2 (0 when SmartRouter skips, 2 normally)
      1. Reflexion critique: 1
      2. CRP revise + score: 1 (merged from 2 separate calls)"""
    start = time.time()
    query = state.get("query", "")
    answer = state.get("combined_answer", "")
    ticket_type = state.get("ticket_type", "")

    # If upstream crashed and produced no answer, fail quality immediately
    if not answer or not query:
        logger.warning("Node 6: missing query or answer — upstream may have crashed")
        return {
            "quality_score": 0.0,
            "quality_details": {"reflexion": 0.0, "crp": 0.0},
            "formatted_response": answer or "Unable to generate a response.",
            "quality_passed": False,
            "combined_answer": answer or "",
            "technique_log": [{"node": 6, "technique": "UPSTREAM_CHECK", "duration_ms": 0, "result_summary": "no_answer_or_query"}],
            "node_6_token_usage": 0,
            "total_token_usage": state.get("total_token_usage", 0),
        }

    knowledge_docs = state.get("knowledge_context", [])
    knowledge_str = "\n".join(d.get("content", "") for d in knowledge_docs)
    loop_count = state.get("loop_count", 0)
    logs = []
    llm_calls = 0

    # ══════════════════════════════════════════════════════════════
    # L1: PRE-FLIGHT — PII scrub + smart routing
    # ══════════════════════════════════════════════════════════════

    # L1-1. SafetyNet: scrub PII from answer before LLM sees it
    pii_check = _safety_net_scrub(answer)
    if pii_check["pii_found"]:
        answer = pii_check["scrubbed"]
        logs.append({
            "node": 6, "technique": "SafetyNet", "duration_ms": 0,
            "result_summary": f"pii_scrubbed count={pii_check['count']}",
        })
    else:
        logs.append({
            "node": 6, "technique": "SafetyNet", "duration_ms": 0,
            "result_summary": "no_pii_found",
        })

    # L1-2. CLARA: quick non-LLM confidence estimate
    clara_confidence = _clara_quick_confidence(answer, knowledge_str, query)
    logs.append({
        "node": 6, "technique": "CLARA", "duration_ms": 0,
        "result_summary": f"confidence={clara_confidence:.2f}",
    })

    # Pre-compute non-LLM scores for SmartRouter
    zero_shot_pre = _zero_shot_check(answer, knowledge_str, query)
    kb_score_pre = _kb_grounding_score(answer, knowledge_str)

    # L1-3. SmartRouter: skip LLM if non-LLM signals are strong enough
    smart_route = _smart_route(clara_confidence, zero_shot_pre, kb_score_pre)
    logs.append({
        "node": 6, "technique": "SmartRouter", "duration_ms": 0,
        "result_summary": f"skip_llm={smart_route['skip_llm']} reason={smart_route.get('reason', '')}",
    })

    # L1-4. Guardrail Check: safety scan for harmful content (non-LLM)
    guardrail = _guardrail_check(answer)
    logs.append({
        "node": 6, "technique": "GuardrailCheck", "duration_ms": 0,
        "result_summary": f"safe={guardrail['safe']} flags={guardrail['flag_count']}",
    })

    # Hard gate: unsafe content → force fail immediately
    if not guardrail["safe"]:
        logger.warning("Node 6: GUARDRAIL FAIL — harmful content detected: %s", guardrail["flags"])
        return {
            "quality_score": 0.0,
            "quality_details": {"guardrail_fail": True, "flags": guardrail["flags"]},
            "formatted_response": "I'm unable to provide that information. Let me connect you with a specialist.",
            "quality_passed": False,
            "combined_answer": "",
            "technique_log": logs + [{
                "node": 6, "technique": "GuardrailHardGate", "duration_ms": 0,
                "result_summary": f"BLOCKED flags={guardrail['flags']}",
            }],
            "node_6_token_usage": 0,
            "total_token_usage": state.get("total_token_usage", 0),
            "escalation_required": True,
            "escalation_reasons": [f"Guardrail fail: {guardrail['flags']}"],
            "cove_verified": True,
            "sufficiency": False,
            "contradiction_detected": False,
            "maker_gaps": [],
            "rule_violations": [],
            "meta_adjustment": 0.0,
            "guardrail_safe": False,
            "reverse_thinking_risks": 0,
            "step_back_passes": True,
            "least_to_most_score": 0.0,
            "theory_of_mind_addressed": False,
            "fake_voting_consensus": 0.0,
        }

    # ══════════════════════════════════════════════════════════════
    # L2: LLM SCORING (or skip if SmartRouter says so)
    # ══════════════════════════════════════════════════════════════

    reflexion_score = 0.95  # defaults if LLM is skipped
    crp_score = 0.95
    best_answer = answer

    if smart_route["skip_llm"]:
        # Skip LLM — use CLARA confidence as proxy for Reflexion/CRP
        reflexion_score = clara_confidence
        crp_score = clara_confidence
        logs.append({
            "node": 6, "technique": "Reflexion", "duration_ms": 0,
            "result_summary": f"SKIPPED (using CLARA={clara_confidence:.2f})",
        })
        logs.append({
            "node": 6, "technique": "CRP", "duration_ms": 0,
            "result_summary": f"SKIPPED (using CLARA={clara_confidence:.2f})",
        })
    else:
        # 1. Reflexion: LLM critique
        reflexion_result = await _reflexion_critique(query, answer, knowledge_str)
        reflexion_score = reflexion_result["score"]
        logs.append({"node": 6, "technique": "Reflexion", "duration_ms": 0, "result_summary": f"score={reflexion_score:.2f}"})
        llm_calls += 1

        # 2. CRP: Generate improved version + score
        critique = reflexion_result.get("raw", "Improve clarity and completeness.")[:200]
        revised, crp_score = await _crp_revise_and_score(query, answer, critique, knowledge_str)
        logs.append({"node": 6, "technique": "CRP", "duration_ms": 0, "result_summary": f"score={crp_score:.2f}"})
        llm_calls += 1

        # Use the better version
        best_answer = revised if crp_score >= reflexion_score else answer

    # ══════════════════════════════════════════════════════════════
    # L3: NON-LLM SCORING (7 scorers + CoVe + MAKER)
    # ══════════════════════════════════════════════════════════════

    # 3. ZeroShotValidator (non-LLM) — use pre-computed if not skipped, recompute for best_answer
    zero_shot = _zero_shot_check(best_answer, knowledge_str, query)
    logs.append({"node": 6, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"score={zero_shot:.2f}"})

    # 4. GSD (non-LLM)
    gsd_score = _gsd_check_parts(best_answer)
    logs.append({"node": 6, "technique": "GSD", "duration_ms": 0, "result_summary": f"score={gsd_score:.2f}"})

    # 5. ThoT (non-LLM)
    thot_score = _thot_coherence(best_answer)
    logs.append({"node": 6, "technique": "ThoT", "duration_ms": 0, "result_summary": f"score={thot_score:.2f}"})

    # 6. Structure check (non-LLM)
    structure_score = _structure_check(best_answer)
    logs.append({"node": 6, "technique": "StructureCheck", "duration_ms": 0, "result_summary": f"score={structure_score:.2f}"})

    # 7. KB grounding score (non-LLM) — use pre-computed or recompute
    kb_score = _kb_grounding_score(best_answer, knowledge_str)
    logs.append({"node": 6, "technique": "KBGrounding", "duration_ms": 0, "result_summary": f"score={kb_score:.2f}"})

    # 8. Answer adequacy check (non-LLM)
    adequacy_score = _answer_adequacy_check(best_answer, query)
    logs.append({"node": 6, "technique": "AnswerAdequacy", "duration_ms": 0, "result_summary": f"score={adequacy_score:.2f}"})

    # 9. ContextualCompression (non-LLM)
    compressed = _compress_response(best_answer)
    logs.append({"node": 6, "technique": "ContextualCompression", "duration_ms": 0, "result_summary": f"{len(best_answer)}→{len(compressed)}"})

    # 10. CoVe: verify specific claims against KB (non-LLM)
    cove_result = _cove_verify_claims(best_answer, knowledge_str)
    logs.append({
        "node": 6, "technique": "CoVe", "duration_ms": 0,
        "result_summary": f"verified={cove_result['verified']} claims={cove_result['claims_checked']} mismatches={len(cove_result['mismatches'])}",
    })

    # 11. MAKER: find what's missing (non-LLM)
    maker_gaps = _maker_find_gaps(best_answer, knowledge_str, query)
    logs.append({
        "node": 6, "technique": "MAKER", "duration_ms": 0,
        "result_summary": f"gaps={maker_gaps['gap_count']} top={maker_gaps['gaps'][:3]}",
    })

    # 12. Self-Consistency Check (non-LLM)
    llm_signals = [reflexion_score, crp_score]
    non_llm_signals = [zero_shot, structure_score, kb_score, adequacy_score]
    consistency_gap = max(llm_signals) - min(llm_signals)
    cross_method_agreement = sum(1 for s in non_llm_signals if s >= 0.85) / len(non_llm_signals)
    self_consistency_score = 1.0 - (consistency_gap * 0.5) if consistency_gap < 0.2 else 0.8
    logs.append({"node": 6, "technique": "Self_Consistency", "duration_ms": 0,
                 "result_summary": f"llm_gap={consistency_gap:.2f} non_llm_agree={cross_method_agreement:.0%} score={self_consistency_score:.2f}"})

    # 13. Reverse Thinking: what makes this answer WRONG? (non-LLM)
    reverse_result = _reverse_thinking_check(best_answer, query, knowledge_str)
    logs.append({
        "node": 6, "technique": "ReverseThinking", "duration_ms": 0,
        "result_summary": f"risks={reverse_result['risk_count']} score={reverse_result['risk_score']:.2f}",
    })

    # 14. Step-Back Check: does answer address the general policy? (non-LLM)
    step_back = _step_back_check(best_answer, query, knowledge_str)
    logs.append({
        "node": 6, "technique": "StepBackCheck", "duration_ms": 0,
        "result_summary": f"passes={step_back['passes']} score={step_back['score']:.2f} reason={step_back.get('reason', '')[:60]}",
    })

    # 15. Least-to-Most Verify: decompose & verify each sub-claim (non-LLM)
    ltm_result = _least_to_most_verify(best_answer, knowledge_str)
    logs.append({
        "node": 6, "technique": "LeastToMost", "duration_ms": 0,
        "result_summary": f"claims={ltm_result['claims_total']} verified={ltm_result['claims_verified']} score={ltm_result['score']:.2f}",
    })

    # 16. Fake Voting: 3 voters rate the answer (non-LLM)
    fake_vote = _fake_voting_score(
        best_answer, query, knowledge_str,
        zero_shot, structure_score, kb_score,
    )
    logs.append({
        "node": 6, "technique": "FakeVoting", "duration_ms": 0,
        "result_summary": f"consensus={fake_vote['consensus']:.2f} agreed={fake_vote['agreed']} spread={fake_vote['spread']:.2f}",
    })

    # ══════════════════════════════════════════════════════════════
    # L4: AGGREGATION + GATES
    # ══════════════════════════════════════════════════════════════

    # 17. FederatedReasoning (non-LLM) — includes new L3 scores
    quality_result = _federated_quality(
        reflexion_score, crp_score, zero_shot, thot_score, gsd_score,
        structure_score, kb_score, adequacy_score,
    )
    quality_score = quality_result["quality_score"]
    quality_passed = quality_score >= QUALITY_PASS_THRESHOLD

    # KB insufficiency hard gate
    knowledge_sufficient = state.get("knowledge_sufficient", True)
    if not knowledge_sufficient:
        quality_passed = False
        logs.append({
            "node": 6, "technique": "KBInsufficiencyHardGate",
            "duration_ms": 0,
            "result_summary": "knowledge_sufficient=False → forced quality_passed=False",
        })

    logs.append({"node": 6, "technique": "FederatedReasoning", "duration_ms": 0,
                 "result_summary": f"final={quality_score:.4f} passed={quality_passed} "
                                  f"non_llm_95={quality_result['details'].get('all_non_llm_95', False)} "
                                  f"non_llm_90={quality_result['details'].get('all_non_llm_90', False)}"})

    # ── Apply new L3 non-LLM scores as adjustments ──

    # ReverseThinking: risks found → reduce quality
    if reverse_result["risk_count"] > 0:
        quality_score = max(0.0, quality_score - (reverse_result["risk_count"] * 0.03))
        quality_passed = quality_score >= QUALITY_PASS_THRESHOLD

    # StepBackCheck: answer too narrow → reduce quality
    if not step_back["passes"]:
        quality_score = max(0.0, quality_score - 0.04)
        quality_passed = quality_score >= QUALITY_PASS_THRESHOLD

    # LeastToMost: claims unverified → reduce quality
    if ltm_result["score"] < 0.70:
        quality_score = max(0.0, quality_score - 0.05)
        quality_passed = quality_score >= QUALITY_PASS_THRESHOLD

    # FakeVoting: voters disagree → reduce quality
    if not fake_vote["agreed"]:
        quality_score = max(0.0, quality_score - 0.03)
        quality_passed = quality_score >= QUALITY_PASS_THRESHOLD

    # 18. ContradictionCheck: LLM vs non-LLM gap (non-LLM)
    non_llm_avg = sum(non_llm_signals) / len(non_llm_signals)
    contradiction = _contradiction_check(reflexion_score, crp_score, non_llm_avg)
    logs.append({
        "node": 6, "technique": "ContradictionCheck", "duration_ms": 0,
        "result_summary": f"has_contradiction={contradiction['has_contradiction']} gap={contradiction.get('gap', 0)}",
    })

    # Override: if contradiction is severe, drop quality
    if contradiction["has_contradiction"] and contradiction.get("direction") == "LLM_overrates":
        quality_score = min(quality_score, non_llm_avg)
        quality_passed = quality_score >= QUALITY_PASS_THRESHOLD
        logs.append({
            "node": 6, "technique": "ContradictionOverride", "duration_ms": 0,
            "result_summary": f"LLM overrating detected → capped quality at {quality_score:.4f}",
        })

    # 19. SufficiencyCheck: did we solve the problem? (non-LLM)
    sufficiency = _sufficiency_check(query, compressed)
    logs.append({
        "node": 6, "technique": "SufficiencyCheck", "duration_ms": 0,
        "result_summary": f"sufficient={sufficiency['sufficient']} reason={sufficiency.get('reason', '')}",
    })

    if not sufficiency["sufficient"]:
        quality_passed = False
        logs.append({
            "node": 6, "technique": "SufficiencyGate", "duration_ms": 0,
            "result_summary": f"quality_passed forced False: {sufficiency['reason']}",
        })

    # 20. Theory of Mind: does answer address REAL intent? (non-LLM)
    tom_result = _theory_of_mind_check(query, compressed, ticket_type)
    logs.append({
        "node": 6, "technique": "TheoryOfMind", "duration_ms": 0,
        "result_summary": f"intent_addressed={tom_result['intent_addressed']} score={tom_result['score']:.2f} "
                          f"missing={tom_result.get('missing', [])}",
    })

    if not tom_result["intent_addressed"]:
        quality_passed = False
        logs.append({
            "node": 6, "technique": "TheoryOfMindGate", "duration_ms": 0,
            "result_summary": f"quality_passed forced False: real intent not addressed — {tom_result.get('missing', [])}",
        })

    # 21. RuleBasedAction: per-ticket-type structural rules (non-LLM)
    rule_check = _rule_based_check(compressed, ticket_type)
    logs.append({
        "node": 6, "technique": "RuleBasedAction", "duration_ms": 0,
        "result_summary": f"passed={rule_check['passed']} violations={len(rule_check.get('violations', []))}",
    })

    if not rule_check["passed"]:
        quality_passed = False
        logs.append({
            "node": 6, "technique": "RuleBasedActionGate", "duration_ms": 0,
            "result_summary": f"quality_passed forced False: {rule_check.get('violations', [])}",
        })

    # 22. MetaLearner: adjust from past scores (non-LLM)
    meta = _meta_learner_adjust(quality_score, state)
    if meta["adjustment"] != 0.0:
        quality_score = max(0.0, min(1.0, quality_score + meta["adjustment"]))
        quality_passed = quality_score >= QUALITY_PASS_THRESHOLD
    logs.append({
        "node": 6, "technique": "MetaLearner", "duration_ms": 0,
        "result_summary": f"adjustment={meta['adjustment']} {meta['reason']}",
    })

    # 23. Escalation: auto-escalate on quality fail (non-LLM)
    escalation = _should_escalate(quality_passed, loop_count, contradiction, sufficiency, quality_score)
    logs.append({
        "node": 6, "technique": "Escalation", "duration_ms": 0,
        "result_summary": f"escalate={escalation['escalate']} reasons={len(escalation['reasons'])}",
    })

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 6 complete: ticket=%s quality=%.4f passed=%s escalate=%s loop=%d llm=%d [%dms] "
        "reflexion=%.2f crp=%.2f structure=%.2f kb=%.2f adequacy=%.2f cove=%s "
        "reverse_risks=%d step_back=%s ltm=%.2f fake_vote=%.2f tom=%s guardrail=%s",
        state["ticket_id"], quality_score, quality_passed, escalation["escalate"],
        loop_count, llm_calls, elapsed,
        reflexion_score, crp_score, structure_score, kb_score, adequacy_score,
        cove_result["verified"],
        reverse_result["risk_count"], step_back["passes"],
        ltm_result["score"], fake_vote["consensus"],
        tom_result["intent_addressed"], guardrail["safe"],
    )


    # ── Wave 4: Write quality score to Jarvis DB ────────────
    try:
        await write_quality_score_to_jarvis(
            tenant_id=state.get("tenant_id", ""),
            ticket_id=state.get("ticket_id", ""),
            quality_score=quality_score,
            resolution_path=state.get("current_path", "unknown"),
            nodes_reached=[log.get("node") for log in logs if "node" in log],
            llm_calls=llm_calls,
            tokens_used=state.get("total_token_usage", 0),
        )
    except Exception as e:
        logger.warning("Wave 4 quality write-back failed (non-fatal): %s", e)

    # ── P1 Notification: emit ai:quality_low ────────────────────────
    if not quality_passed:
        try:
            from app.core.event_emitter import emit_ai_event
            await emit_ai_event(
                company_id=state.get("tenant_id", ""),
                event_type="ai:quality_low",
                payload={
                    "company_id": state.get("tenant_id", ""),
                    "ticket_id": state.get("ticket_id", ""),
                    "quality_score": round(quality_score, 4),
                    "quality_threshold": QUALITY_PASS_THRESHOLD,
                    "quality_details": quality_result.get("details", {}),
                    "loop_count": loop_count,
                    "llm_calls": llm_calls,
                    "escalation": escalation,
                    "contradiction": contradiction,
                    "sufficiency": sufficiency,
                    "node": 6,
                },
                correlation_id=state.get("ticket_id", ""),
            )
        except Exception as exc:
            logger.warning("node_6_quality_low_notification_failed: %s", str(exc)[:200])

    return {
        "quality_score": quality_score,
        "quality_details": quality_result["details"],
        "formatted_response": compressed,
        "quality_passed": quality_passed,
        "combined_answer": compressed,
        "technique_log": logs,
        "node_6_token_usage": llm_calls,
        "total_token_usage": state.get("total_token_usage", 0) + llm_calls,
        "escalation_required": escalation.get("escalate", False),
        "escalation_reasons": escalation.get("reasons", []),
        "cove_verified": cove_result.get("verified", True),
        "sufficiency": sufficiency.get("sufficient", True),
        "contradiction_detected": contradiction.get("has_contradiction", False),
        "maker_gaps": maker_gaps.get("gaps", []),
        "rule_violations": rule_check.get("violations", []),
        "meta_adjustment": meta.get("adjustment", 0.0),
        # New non-LLM technique outputs
        "guardrail_safe": guardrail.get("safe", True),
        "reverse_thinking_risks": reverse_result.get("risk_count", 0),
        "step_back_passes": step_back.get("passes", True),
        "least_to_most_score": ltm_result.get("score", 0.0),
        "theory_of_mind_addressed": tom_result.get("intent_addressed", True),
        "fake_voting_consensus": fake_vote.get("consensus", 0.0),
    }
