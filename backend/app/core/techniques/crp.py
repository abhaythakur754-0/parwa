"""
F-140: Concise Response Protocol (CRP) — Tier 1 Always-Active

Minimizes token waste by eliminating filler words, compressing verbose
explanations, removing redundancy, and enforcing token budgets.

CRP runs BEFORE Guardrails (F-057) in the pipeline:
  CRP (efficiency)  ->  Guardrails (safety)  ->  CLARA (quality)

Performance targets:
  - 30-40% fewer tokens
  - > 95% key facts preserved
  - No increase in response time (deterministic, no LLM calls)

Building Codes: BC-001 (company isolation), BC-008 (never crash),
               BC-012 (graceful degradation)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from app.logger import get_logger

logger = get_logger("crp")


# ── Default Filler Patterns ─────────────────────────────────────────

# Opening pleasantries
_OPENING_FILLERS: Tuple[str, ...] = (
    r"I(?:'d| would) be happy to help you with that\.?",
    r"Certainly,?\s*I can assist",
    r"Of course!?\s*I(?:'d| would) be (?:glad|happy) to",
    r"Absolutely!?\s*Let me",
    r"Sure (?:thing)?!?\s*I can",
    r"Great question!?\s*",
    r"Thanks for (?:reaching out|contacting us|your question)\!?\s*",
    r"I(?:'d| would) love to help",
    r"Happy to (?:help|assist)!?\s*",
    r"No problem!?\s*(?:I can|let me|at all)",
)

# Closing pleasantries
_CLOSING_FILLERS: Tuple[str, ...] = (
    r"Please (?:don't|do not) hesitate to (?:reach out|contact us|ask)",
    r"I hope this (?:helps|answers your question|was helpful)\!?",
    r"Let me know if (?:there's|there is) anything else",
    r"Feel free to (?:reach out|contact us|ask) if",
    r"If you (?:have any (?:other|further) questions?|need anything else)",
    r"We(?:'re| are) always here to help",
    r"Thank you for your patience",
    r"Is there anything else I can help you with\??",
)

# Transition / padding phrases
_TRANSITION_FILLERS: Tuple[str, ...] = (
    r"Let me look into that for you\.?",
    r"As I (?:mentioned|said) earlier,?",
    r"Just to clarify,?",
    r"In terms of your question,?",
    r"Moving forward,?",
    r"With that being said,?",
    r"It'?s worth noting that",
    r"As a quick reminder,?",
    r"To give you some context,?",
    r"For what it'?s worth,?",
    r"At the end of the day,?",
    r"When it comes down to it,?",
)

# Empathy padding (kept only for sentiment < 0.5)
_EMPATHY_FILLERS: Tuple[str, ...] = (
    r"I (?:completely |fully )?understand (?:how |your )?(?:frustrating|difficult|confusing) this (?:can be|must be|is|might be)",
    r"I'?m sorry to hear (?:that|about this)",
    r"I apologize for (?:the inconvenience|any confusion|the trouble)",
    r"I can see (?:how|why) this (?:would be|might be|is) (?:frustrating|concerning|confusing)",
    r"That (?:sounds|must be|seems) (?:really )?(?:frustrating|difficult|inconvenient)",
)

# Combined default filler list (includes empathy by default;
# excluded when keep_empathy=True in CRPConfig)
DEFAULT_FILLERS: FrozenSet[str] = frozenset(
    _OPENING_FILLERS + _CLOSING_FILLERS + _TRANSITION_FILLERS
    + _EMPATHY_FILLERS
)

# Empathy patterns as a set for efficient lookup during keep_empathy filtering
_EMPATHY_PATTERN_SET: FrozenSet[str] = frozenset(_EMPATHY_FILLERS)

# Compression patterns (verbose -> concise)
_COMPRESSION_RULES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bIn order to\b", re.I), "To"),
    (re.compile(r"\bFor the purpose of\b", re.I), "To"),
    (re.compile(r"\bAs a result of\b", re.I), "Due to"),
    (re.compile(r"\bIn the event that\b", re.I), "If"),
    (re.compile(r"\bIt is important to note that\b", re.I), "Note:"),
    (re.compile(r"\bAt this point in time\b", re.I), "Currently"),
    (re.compile(r"\bIn the near future\b", re.I), "Soon"),
    (re.compile(r"\bA (?:large )?number of\b", re.I), "Many"),
    (re.compile(r"\bEach and every\b", re.I), "Every"),
    (re.compile(r"\bIn (?:the|order to) (?:event|case) of\b", re.I), "If"),
    (re.compile(r"\bWith regard to\b", re.I), "Regarding"),
    (re.compile(r"\bOn (?:the|a) (?:regular|daily) basis\b", re.I), "Regularly"),
    (re.compile(r"\b(?:Prior|Previous) to\b", re.I), "Before"),
    (re.compile(r"\bSubsequent to\b", re.I), "After"),
    (re.compile(r"\b(?:In spite of|Despite the fact that)\b", re.I), "Although"),
    (re.compile(r"\b(?:In addition|Additionally)\b", re.I), "Also"),
    (re.compile(r"\b(?:Furthermore|Moreover)\b", re.I), "Also"),
    (re.compile(r"\b(?:Consequently|As a consequence)\b", re.I), "So"),
    (re.compile(r"\b(?:Nevertheless|Nonetheless)\b", re.I), "However"),
    (re.compile(r"\b(?:On the other hand|Conversely)\b", re.I), "But"),
    (re.compile(r"\b(?:In other words|To put it differently)\b", re.I), "i.e."),
    (re.compile(r"\b(?:For example|For instance)\b", re.I), "e.g."),
    (re.compile(r"\b(?:That is|Which is) to say\b", re.I), "Meaning"),
    (re.compile(r"\b(?:First(?:ly)?|Second(?:ly)?|Third(?:ly)?)\b,\s*", re.I),
     lambda m: f"{m.group(0).strip().rstrip(',')}. "),
]

# Reserved phrases never to compress (key facts / critical terms)
_RESERVED_PHRASES: FrozenSet[str] = frozenset({
    "refund", "cancellation", "payment", "charge", "invoice",
    "subscription", "billing", "prorated", "policy", "deadline",
    "contract", "termination", "credit", "debit", "amount",
})


# ── Data Structures ──────────────────────────────────────────────────


@dataclass(frozen=True)
class CRPConfig:
    """Immutable configuration for CRP processing (BC-001)."""

    company_id: str = ""
    custom_fillers: Tuple[str, ...] = ()
    custom_compressions: Tuple[Tuple[str, str], ...] = ()
    min_token_budget: int = 20
    enable_compression: bool = True
    enable_redundancy_removal: bool = True
    keep_empathy: bool = False  # keep empathy phrases for upset customers


@dataclass
class CRPResult:
    """Output of CRP processing."""

    processed_text: str = ""
    original_tokens: int = 0
    processed_tokens: int = 0
    reduction_pct: float = 0.0
    steps_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "processed_text": self.processed_text,
            "original_tokens": self.original_tokens,
            "processed_tokens": self.processed_tokens,
            "reduction_pct": round(self.reduction_pct, 2),
            "steps_applied": self.steps_applied,
        }


# ── CRP Processor ────────────────────────────────────────────────────


class CRPProcessor:
    """
    Concise Response Protocol processor (F-140).

    Deterministic, regex/heuristic-based (no LLM calls).
    Target: sub-50ms processing time.

    Pipeline:
      1. Filler elimination
      2. Response compression
      3. Redundancy removal
      4. Token budget enforcement
    """

    def __init__(self, config: Optional[CRPConfig] = None):
        self.config = config or CRPConfig()
        self._filler_patterns = self._compile_fillers()
        self._compression_rules = self._compile_compressions()

    # ── Pattern Compilation ────────────────────────────────────────

    def _compile_fillers(self) -> List[re.Pattern]:
        """Compile all filler regex patterns."""
        patterns = []
        for pattern_str in DEFAULT_FILLERS:
            try:
                patterns.append(re.compile(pattern_str, re.I))
            except re.error:
                logger.warning(
                    "crp_invalid_filler_pattern",
                    pattern=pattern_str)

        # keep_empathy: when True, exclude empathy fillers so upset
        # customers still receive empathetic language.
        if self.config.keep_empathy:
            filtered = []
            for compiled in patterns:
                if compiled.pattern not in _EMPATHY_PATTERN_SET:
                    filtered.append(compiled)
            patterns = filtered

        # Add custom company-specific fillers
        for pattern_str in self.config.custom_fillers:
            try:
                patterns.append(re.compile(pattern_str, re.I))
            except re.error:
                logger.warning(
                    "crp_invalid_custom_filler",
                    company_id=self.config.company_id,
                    pattern=pattern_str,
                )
        return patterns

    def _compile_compressions(self) -> List[Tuple[re.Pattern, str]]:
        """Compile compression rules including custom overrides."""
        rules = list(_COMPRESSION_RULES)
        for src, dst in self.config.custom_compressions:
            try:
                rules.append((re.compile(src, re.I), dst))
            except re.error:
                logger.warning(
                    "crp_invalid_compression",
                    company_id=self.config.company_id,
                    pattern=src,
                )
        return rules

    # ── Core Methods ───────────────────────────────────────────────

    async def eliminate_fillers(self, text: str) -> str:
        """Remove filler phrases from text."""
        if not text:
            return text
        result = text
        for pattern in self._filler_patterns:
            result = pattern.sub("", result)
        # Clean up double spaces and leading/trailing whitespace
        result = re.sub(r"  +", " ", result)
        result = result.strip()
        return result

    async def compress_response(self, text: str) -> str:
        """Compress verbose phrases to concise equivalents."""
        if not text or not self.config.enable_compression:
            return text
        result = text
        for pattern, replacement in self._compression_rules:
            if callable(replacement):
                result = pattern.sub(replacement, result)
            else:
                result = pattern.sub(replacement, result)
        # Clean up
        result = re.sub(r"  +", " ", result)
        result = re.sub(r"\.\s+\.", ".", result)
        result = result.strip()
        return result

    async def remove_redundancy(self, text: str) -> str:
        """Remove duplicate information across sentences."""
        if not text or not self.config.enable_redundancy_removal:
            return text
        sentences = self._split_sentences(text)
        if len(sentences) <= 2:
            return text

        kept: List[str] = []
        kept_normalized: List[Set[str]] = []

        for sentence in sentences:
            sentence_normalized = self._normalize(sentence)
            if self._is_redundant(sentence_normalized, kept_normalized):
                continue
            kept.append(sentence)
            kept_normalized.append(sentence_normalized)

        return self._join_sentences(kept) if kept else text

    async def enforce_token_budget(
        self, text: str, max_tokens: int,
    ) -> str:
        """Truncate text to fit within token budget at sentence boundary."""
        if not text:
            return text
        effective_budget = max(max_tokens, self.config.min_token_budget)
        current_tokens = self.estimate_tokens(text)

        if current_tokens <= effective_budget:
            return text

        # Truncate at last complete sentence within budget
        sentences = self._split_sentences(text)
        result_parts: List[str] = []
        running_tokens = 0

        for sentence in sentences:
            sentence_tokens = self.estimate_tokens(sentence)
            if running_tokens + sentence_tokens > effective_budget:
                break
            result_parts.append(sentence)
            running_tokens += sentence_tokens

        return self._join_sentences(result_parts)

    async def process(
        self,
        text: str,
        complexity: float = 0.5,
        max_tokens: Optional[int] = None,
    ) -> CRPResult:
        """
        Run the full CRP pipeline.

        Args:
            text: The response text to process.
            complexity: Query complexity (0.0-1.0). Higher complexity
                = more generous token budget.
            max_tokens: Override token budget. If None, auto-calculated
                based on original token count and complexity.

        Returns:
            CRPResult with processed text and metrics.
        """
        original_tokens = self.estimate_tokens(text)
        steps_applied: List[str] = []

        if not text or not text.strip():
            return CRPResult(
                processed_text=text,
                original_tokens=original_tokens,
                processed_tokens=original_tokens,
                reduction_pct=0.0,
                steps_applied=["empty_input"],
            )

        try:
            # Step 1: Filler elimination
            result = await self.eliminate_fillers(text)
            if result != text:
                steps_applied.append("filler_elimination")
                text = result

            # Step 2: Compression
            result = await self.compress_response(text)
            if result != text:
                steps_applied.append("compression")
                text = result

            # Step 3: Redundancy removal
            result = await self.remove_redundancy(text)
            if result != text:
                steps_applied.append("redundancy_removal")
                text = result

            # Step 4: Token budget enforcement
            if max_tokens is None:
                max_tokens = self._calculate_budget(
                    original_tokens, complexity,
                )
            result = await self.enforce_token_budget(text, max_tokens)
            if result != text:
                steps_applied.append("token_budget_enforcement")
                text = result

        except Exception as exc:
            # BC-008: Never crash — return original on error
            logger.warning(
                "crp_processing_error",
                error=str(exc),
                company_id=self.config.company_id,
            )
            return CRPResult(
                processed_text=text,
                original_tokens=original_tokens,
                processed_tokens=original_tokens,
                reduction_pct=0.0,
                steps_applied=["error_fallback"],
            )

        processed_tokens = self.estimate_tokens(text)
        reduction = 0.0
        if original_tokens > 0:
            reduction = (
                (original_tokens - processed_tokens)
                / original_tokens
                * 100.0
            )

        return CRPResult(
            processed_text=text,
            original_tokens=original_tokens,
            processed_tokens=processed_tokens,
            reduction_pct=reduction,
            steps_applied=steps_applied,
        )

    # ── Utility Methods ───────────────────────────────────────────

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count (~4 chars per token)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split text into sentences on period, exclamation, question."""
        if not text:
            return []
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s.strip() for s in parts if s.strip()]

    @staticmethod
    def _join_sentences(sentences: List[str]) -> str:
        """Join sentences with proper spacing."""
        return " ".join(sentences)

    @staticmethod
    def _normalize(sentence: str) -> Set[str]:
        """Normalize a sentence to a set of lowercase words."""
        words = re.findall(r"\b\w+\b", sentence.lower())
        return set(words)

    @staticmethod
    def _is_reserved(word: str) -> bool:
        """Check if a word is in the reserved phrases list.

        Reserved words (e.g. refund, payment, invoice) are critical
        business terms that should never be compressed or removed.
        """
        return word.lower() in _RESERVED_PHRASES

    @staticmethod
    def _is_redundant(
        sentence_words: Set[str],
        previous_sentences: List[Set[str]],
        threshold: float = 0.7,
    ) -> bool:
        """Check if a sentence is redundant with any previous one."""
        if not sentence_words:
            return True
        for prev in previous_sentences:
            if not prev:
                continue
            intersection = sentence_words & prev
            union = sentence_words | prev
            if not union:
                continue
            similarity = len(intersection) / len(union)
            if similarity >= threshold:
                return True
        return False

    @staticmethod
    def _calculate_budget(
        original_tokens: int, complexity: float,
    ) -> int:
        """Calculate token budget based on complexity level."""
        # Low complexity = aggressive compression (60% of original)
        # Medium = moderate (80%)
        # High = light (95%)
        if complexity <= 0.3:
            ratio = 0.6
        elif complexity <= 0.7:
            ratio = 0.8
        else:
            ratio = 0.95

        budget = int(original_tokens * ratio)
        return max(budget, 20)  # minimum 20 tokens
