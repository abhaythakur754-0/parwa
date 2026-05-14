"""
FAKE Voting Sub-System (Week 2)

Multi-evaluator consensus mechanism for MAKER framework.
Generates K candidate solutions, scores each across 4+ evaluators
(fluency, relevance, accuracy, safety, empathy), applies Red-Flagging
from Loophole Registry, and selects best via weighted consensus.

BC-008: Never crash — always return a valid result.
BC-001: All operations scoped to company_id.
"""

from __future__ import annotations

import asyncio
import re
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from app.logger import get_logger

logger = get_logger("fake_voting")

# ── Precompiled regex patterns ─────────────────────────────────
_PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit card": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
}

_SPECULATIVE = [
    re.compile(r"\bI think\b", re.I), re.compile(r"\bprobably\b", re.I),
    re.compile(r"\bmight be\b", re.I), re.compile(r"\bI believe\b", re.I),
    re.compile(r"\bI'm not sure\b", re.I), re.compile(r"\bit's possible\b", re.I),
    re.compile(r"\bI guess\b", re.I), re.compile(r"\bpresumably\b", re.I),
]

_POLICY_VIOLATIONS = [
    re.compile(r"\bwe guarantee\b", re.I), re.compile(r"\byou will definitely\b", re.I),
    re.compile(r"\bwe promise\b", re.I), re.compile(r"\byou should (?:sue|file a lawsuit|contact an attorney)\b", re.I),
]

_CONFIDENT_PHRASES = [
    re.compile(r"\bcertainly\b", re.I), re.compile(r"\bdefinitely\b", re.I),
    re.compile(r"\babsolutely\b", re.I), re.compile(r"\bwithout (?:a )?doubt\b", re.I),
]

_EMPATHY_KW: Set[str] = {
    "sorry", "apologize", "apologies", "understand", "understanding",
    "appreciate", "concern", "frustrating", "inconvenience",
    "valued", "thank you", "here for you", "glad to help",
    "unfortunate", "regret", "sympathize", "care about",
}

_STOPWORDS: Set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "and", "but", "or", "not", "so", "yet", "all",
    "any", "few", "more", "most", "other", "some", "no", "only", "own",
    "same", "than", "too", "very", "just", "because", "if", "when",
    "where", "how", "what", "which", "who", "this", "that", "these",
    "those", "i", "me", "my", "we", "our", "you", "your", "he", "she",
    "it", "they", "them", "their", "please", "help", "thanks",
}


def _tokenize(text: str) -> Set[str]:
    """Whitespace tokenizer with stopword removal."""
    return set(t for t in re.findall(r"\b[a-z0-9]+\b", text.lower()) if t not in _STOPWORDS and len(t) > 1)


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════


@dataclass
class FakeVotingConfig:
    """Configuration for the FAKE Voting engine."""

    num_candidates: int = 3
    evaluators: List[str] = field(default_factory=lambda: [
        "fluency", "relevance", "accuracy", "safety", "empathy",
    ])
    evaluator_weights: Dict[str, float] = field(default_factory=lambda: {
        "fluency": 0.15, "relevance": 0.30, "accuracy": 0.25,
        "safety": 0.20, "empathy": 0.10,
    })
    consensus_threshold: float = 0.6
    min_evaluators_agree: int = 3

    def __post_init__(self) -> None:
        total = sum(self.evaluator_weights.get(e, 0.0) for e in self.evaluators)
        if abs(total - 1.0) > 0.05 and total > 0:
            for e in self.evaluators:
                self.evaluator_weights[e] = round(self.evaluator_weights.get(e, 0.1) / total, 4)


def get_fake_voting_config(variant_type: str) -> FakeVotingConfig:
    """Return variant-specific FAKE Voting configuration.

    mini_parwa:  3 candidates, 3 evaluators (fluency, relevance, safety), threshold 0.50
    parwa:       5 candidates, 4 evaluators (+accuracy), threshold 0.60
    parwa_high:  7 candidates, 5 evaluators (+empathy), threshold 0.75
    """
    _PRESETS: Dict[str, Dict[str, Any]] = {
        "mini_parwa": {
            "num_candidates": 3,
            "evaluators": ["fluency", "relevance", "safety"],
            "evaluator_weights": {"fluency": 0.25, "relevance": 0.45, "safety": 0.30},
            "consensus_threshold": 0.50,
            "min_evaluators_agree": 2,
        },
        "parwa": {
            "num_candidates": 5,
            "evaluators": ["fluency", "relevance", "accuracy", "safety"],
            "evaluator_weights": {"fluency": 0.15, "relevance": 0.30, "accuracy": 0.25, "safety": 0.30},
            "consensus_threshold": 0.60,
            "min_evaluators_agree": 3,
        },
        "parwa_high": {
            "num_candidates": 7,
            "evaluators": ["fluency", "relevance", "accuracy", "safety", "empathy"],
            "evaluator_weights": {"fluency": 0.10, "relevance": 0.25, "accuracy": 0.30, "safety": 0.20, "empathy": 0.15},
            "consensus_threshold": 0.75,
            "min_evaluators_agree": 4,
        },
    }
    if variant_type not in _PRESETS:
        logger.warning("fake_voting_unknown_variant", variant_type=variant_type, fallback="mini_parwa")
        variant_type = "mini_parwa"
    return FakeVotingConfig(**_PRESETS[variant_type])


# ═══════════════════════════════════════════════════════════════
# Red-Flag Engine — Loophole Registry checks
# ═══════════════════════════════════════════════════════════════


class RedFlagEngine:
    """Checks candidate responses for five categories of red flags:
    hallucination risk, PII leakage, off-topic, policy violation,
    and confidence mismatch. BC-008: Never raises."""

    async def check_red_flags(
        self, candidate: str, query: str, company_id: str, consensus_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Run all red-flag checks. Returns list of {type, severity, description}."""
        flags: List[Dict[str, Any]] = []
        checks = [
            self._check_hallucination_risk(candidate),
            self._check_pii_leakage(candidate),
            self._check_off_topic(candidate, query),
            self._check_policy_violation(candidate),
            self._check_confidence_mismatch(candidate, consensus_score),
        ]
        for result in checks:
            if result is not None:
                result["company_id"] = company_id
                flags.append(result)
        if flags:
            logger.info("red_flags_raised", company_id=company_id, count=len(flags), types=[f["type"] for f in flags])
        return flags

    def _check_hallucination_risk(self, candidate: str) -> Optional[Dict[str, Any]]:
        """Detect speculative or unsupported claims."""
        hits = [f'"{p.search(candidate).group()}"' for p in _SPECULATIVE if p.search(candidate)]
        if not hits:
            return None
        return {
            "type": "hallucination_risk",
            "severity": "medium" if len(hits) >= 2 else "low",
            "description": f"Speculative phrase{'s' if len(hits) > 1 else ''} detected: {', '.join(hits[:3])}. Response may contain hallucinated information.",
        }

    def _check_pii_leakage(self, candidate: str) -> Optional[Dict[str, Any]]:
        """Detect PII: email, phone, SSN, credit card."""
        found = [name for name, pat in _PII_PATTERNS.items() if pat.search(candidate)]
        if not found:
            return None
        severity = "high" if any(t in found for t in ("SSN", "credit card")) else "medium"
        return {"type": "pii_leakage", "severity": severity, "description": f"Potential PII detected: {', '.join(found)}."}

    def _check_off_topic(self, candidate: str, query: str) -> Optional[Dict[str, Any]]:
        """Detect low keyword overlap between query and response."""
        if not query or not candidate:
            return None
        qt, ct = _tokenize(query), _tokenize(candidate)
        if not qt or not ct:
            return None
        jaccard = len(qt & ct) / len(qt | ct)
        if jaccard < 0.05 and len(ct) > 10:
            return {"type": "off_topic", "severity": "medium", "description": f"Low keyword overlap (Jaccard={jaccard:.3f}). Response may be off-topic."}
        return None

    def _check_policy_violation(self, candidate: str) -> Optional[Dict[str, Any]]:
        """Detect unauthorized guarantees, promises, legal advice."""
        hits = [f'"{p.search(candidate).group()}"' for p in _POLICY_VIOLATIONS if p.search(candidate)]
        if hits:
            return {"type": "policy_violation", "severity": "high", "description": f"Policy-violating language: {', '.join(hits[:3])}."}
        return None

    def _check_confidence_mismatch(self, candidate: str, score: float) -> Optional[Dict[str, Any]]:
        """Detect mismatch between score and language tone."""
        unc_count = sum(1 for p in _SPECULATIVE if p.search(candidate))
        conf_count = sum(1 for p in _CONFIDENT_PHRASES if p.search(candidate))
        if score < 0.4 and conf_count >= 1:
            return {"type": "confidence_mismatch", "severity": "medium", "description": f"Low score ({score:.2f}) but confident language detected."}
        if score > 0.7 and unc_count >= 2:
            return {"type": "confidence_mismatch", "severity": "low", "description": f"High score ({score:.2f}) but uncertain language detected."}
        return None


# ═══════════════════════════════════════════════════════════════
# FAKE Voting Engine
# ═══════════════════════════════════════════════════════════════


class FakeVotingEngine:
    """FAKE Voting Engine — Multi-evaluator consensus for MAKER framework.

    Evaluates each candidate across multiple dimensions (fluency, relevance,
    accuracy, safety, empathy), applies weighted consensus scoring, runs
    red-flag checks, and selects the winner.

    BC-008: Always returns a valid result.
    BC-001: All operations scoped to company_id.
    """

    def __init__(self, config: Optional[FakeVotingConfig] = None) -> None:
        self._config = config or FakeVotingConfig()
        self._red_flags = RedFlagEngine()
        logger.info(
            "fake_voting_init", candidates=self._config.num_candidates,
            evaluators=self._config.evaluators, threshold=self._config.consensus_threshold,
        )

    async def vote(
        self, candidates: List[Dict[str, Any]], query: str,
        company_id: str, variant_type: str = "parwa",
    ) -> Dict[str, Any]:
        """Run FAKE Voting on candidates. Returns {winner, consensus_score, all_scores, red_flags}."""
        try:
            return await self._vote_impl(candidates, query, company_id, variant_type)
        except Exception as exc:
            logger.error("fake_voting_fatal", company_id=company_id, error=str(exc))
            fb = candidates[0] if candidates else {"solution": "", "confidence": 0.0, "reasoning": "BC-008 fallback", "source": "bc008"}
            return {
                "winner": {**fb, "consensus_score": 0.0}, "consensus_score": 0.0,
                "all_scores": {}, "red_flags": [{"type": "system_error", "severity": "high", "description": str(exc)}],
                "voting_summary": {"status": "error_fallback", "company_id": company_id},
            }

    async def _vote_impl(
        self, candidates: List[Dict[str, Any]], query: str, company_id: str, variant_type: str,
    ) -> Dict[str, Any]:
        if not candidates:
            return {"winner": {"solution": "", "consensus_score": 0.0, "source": "empty"}, "consensus_score": 0.0, "all_scores": {}, "red_flags": [], "voting_summary": {"status": "no_candidates", "company_id": company_id}}

        evaluators = self._config.evaluators
        weights = self._config.evaluator_weights
        all_scores: Dict[int, Dict[str, Any]] = {}
        all_flags: List[Dict[str, Any]] = []

        for idx, cand in enumerate(candidates):
            text = cand.get("solution", "")
            breakdown: Dict[str, float] = {}
            tasks = []
            for ev in evaluators:
                fn = getattr(self, f"evaluate_{ev}", None)
                if fn is None:
                    breakdown[ev] = 0.5
                    continue
                if ev in ("relevance", "accuracy", "empathy"):
                    tasks.append(fn(text, query, company_id))
                else:
                    tasks.append(fn(text, company_id))

            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for ev, score in zip(evaluators, results):
                    if isinstance(score, Exception):
                        logger.warning("evaluator_error", company_id=company_id, evaluator=ev, error=str(score))
                        breakdown[ev] = 0.5
                    else:
                        breakdown[ev] = max(0.0, min(1.0, float(score)))
            except Exception as exc:
                logger.warning("gather_error", company_id=company_id, error=str(exc))
                for ev in evaluators:
                    if ev not in breakdown:
                        breakdown[ev] = 0.5

            weighted = round(max(0.0, min(1.0, sum(weights.get(ev, 0) * breakdown[ev] for ev in evaluators))), 4)
            agree = sum(1 for ev in evaluators if breakdown.get(ev, 0) >= self._config.consensus_threshold)

            all_scores[idx] = {"breakdown": breakdown, "weighted_score": weighted, "evaluators_agree": agree, "meets_consensus": agree >= self._config.min_evaluators_agree}

            try:
                flags = await self._red_flags.check_red_flags(text, query, company_id, weighted)
                all_flags.extend(flags)
            except Exception as exc:
                logger.warning("red_flag_error", company_id=company_id, error=str(exc))

        # Select winner
        winner_idx = max(range(len(candidates)), key=lambda i: (all_scores.get(i, {}).get("weighted_score", 0), all_scores.get(i, {}).get("evaluators_agree", 0)))

        winner = dict(candidates[winner_idx])
        ws = all_scores.get(winner_idx, {})
        winner["consensus_score"] = ws.get("weighted_score", 0.0)
        winner["evaluators_agree"] = ws.get("evaluators_agree", 0)
        winner["score_breakdown"] = ws.get("breakdown", {})

        logger.info(
            "fake_voting_done", company_id=company_id, variant=variant_type,
            candidates=len(candidates), winner=winner_idx, score=winner["consensus_score"],
        )
        return {
            "winner": winner, "consensus_score": winner["consensus_score"],
            "all_scores": all_scores, "red_flags": all_flags,
            "voting_summary": {
                "status": "completed", "company_id": company_id, "variant_type": variant_type,
                "total_candidates": len(candidates), "winner_index": winner_idx,
                "consensus_score": winner["consensus_score"], "evaluators_used": evaluators,
                "threshold": self._config.consensus_threshold, "min_evaluators_agree": self._config.min_evaluators_agree,
                "total_red_flags": len(all_flags),
            },
        }

    # ── Evaluator: Fluency (0-1) ───────────────────────────────

    async def evaluate_fluency(self, candidate: str, company_id: str) -> float:
        """LLM fluency scoring with sentence-variance heuristic fallback."""
        try:
            score = await self._llm_score(
                "Rate the fluency of this response: grammar, sentence variety, no repetition. Reply ONLY 0.0-1.0.\n\n" + candidate, company_id)
            if score is not None:
                return score
        except Exception:
            pass
        # Heuristic: sentence length variance + repetition
        sentences = [s.strip() for s in re.split(r"[.!?]+", candidate) if s.strip()]
        if not sentences:
            return 0.3
        lengths = [len(s.split()) for s in sentences]
        var_score = max(0.0, min(1.0, 1.0 - abs(statistics.variance(lengths) - 30) / 60)) if len(lengths) >= 2 else 0.5
        words = [w.lower() for w in candidate.split() if len(w) > 3]
        rep_score = min(1.0, (len(set(words)) / len(words)) * 1.2) if words else 0.3
        avg = statistics.mean(lengths)
        avg_score = 1.0 if 5 <= avg <= 25 else (avg / 5.0 if avg < 5 else max(0.2, 1.0 - (avg - 25) / 30))
        return round(0.4 * var_score + 0.3 * rep_score + 0.3 * avg_score, 2)

    # ── Evaluator: Relevance (0-1) ─────────────────────────────

    async def evaluate_relevance(self, candidate: str, query: str, company_id: str) -> float:
        """LLM relevance scoring with keyword Jaccard fallback."""
        try:
            score = await self._llm_score(
                f"Rate how well this response addresses the query. Reply ONLY 0.0-1.0.\n\nQuery: {query}\nResponse: {candidate}", company_id)
            if score is not None:
                return score
        except Exception:
            pass
        qt, ct = _tokenize(query), _tokenize(candidate)
        if not qt or not ct:
            return 0.1
        return round(len(qt & ct) / len(qt | ct), 2)

    # ── Evaluator: Accuracy (0-1) ──────────────────────────────

    async def evaluate_accuracy(self, candidate: str, query: str, company_id: str) -> float:
        """LLM accuracy scoring with neutral 0.5 fallback."""
        try:
            score = await self._llm_score(
                f"Rate factual accuracy of this response. Reply ONLY 0.0-1.0.\n\nQuery: {query}\nResponse: {candidate}", company_id)
            if score is not None:
                return score
        except Exception:
            pass
        return 0.5

    # ── Evaluator: Safety (0-1) ────────────────────────────────

    async def evaluate_safety(self, candidate: str, company_id: str) -> float:
        """Keyword blocklist + LLM safety check. Returns low score on PII/policy issues."""
        score = 1.0
        for name, pat in _PII_PATTERNS.items():
            if pat.search(candidate):
                score -= 0.4 if name in ("SSN", "credit card") else 0.3
        for pat in _POLICY_VIOLATIONS:
            if pat.search(candidate):
                score -= 0.2
        kw_score = round(max(0.0, min(1.0, score)), 2)
        if kw_score < 0.4:
            return kw_score
        try:
            llm_score = await self._llm_score(
                f"Rate safety of this response (harmful content, PII, discrimination). Reply ONLY 0.0-1.0.\n\n{candidate}", company_id)
            if llm_score is not None:
                return round(min(kw_score, llm_score), 2)
        except Exception:
            pass
        return kw_score

    # ── Evaluator: Empathy (0-1) ───────────────────────────────

    async def evaluate_empathy(self, candidate: str, query: str, company_id: str) -> float:
        """LLM empathy scoring with keyword detection fallback."""
        try:
            score = await self._llm_score(
                f"Rate empathy and emotional intelligence. Reply ONLY 0.0-1.0.\n\nQuery: {query}\nResponse: {candidate}", company_id)
            if score is not None:
                return score
        except Exception:
            pass
        lower = candidate.lower()
        matches = sum(1 for kw in _EMPATHY_KW if kw in lower)
        return round(min(0.85, 0.2 + matches * 0.2), 2)

    # ── LLM Scoring Helper ─────────────────────────────────────

    async def _llm_score(self, prompt: str, company_id: str) -> Optional[float]:
        """Use Smart Router for LLM-based scoring. Returns float or None."""
        try:
            from app.core.smart_router import SmartRouter, AtomicStepType
            router = SmartRouter()
            decision = router.route(company_id, "parwa", AtomicStepType.FAKE_VOTING)
            messages = [
                {"role": "system", "content": "You are a quality evaluator. Reply with ONLY a number 0.0-1.0."},
                {"role": "user", "content": prompt},
            ]
            result = router.execute_llm_call(company_id, decision, messages, temperature=0.3, max_tokens=200)
            content = result.get("content", "").strip()
            return self._parse_score(content)
        except Exception as exc:
            logger.debug("llm_score_error", company_id=company_id, error=str(exc))
            return None

    @staticmethod
    def _parse_score(text: str) -> Optional[float]:
        """Parse numeric score from LLM text. Handles 0.75, 85%, Score: 0.9."""
        if not text:
            return None
        text = text.strip().strip(".")
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if m:
            return max(0.0, min(1.0, float(m.group(1)) / 100))
        m = re.search(r"\b(0?\.\d+|1\.0?)\b", text)
        if m:
            return max(0.0, min(1.0, float(m.group(1))))
        m = re.search(r"\b(\d{1,2}|100)\b", text)
        if m:
            v = int(m.group(1))
            return float(v) if v <= 1 else max(0.0, min(1.0, v / 100))
        return None
