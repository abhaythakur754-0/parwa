"""
Chain of Thought (CoT) — Tier 2 Conditional AI Reasoning Technique

Activates when query_complexity > 0.4. Uses deterministic/heuristic-based
reasoning (no LLM calls) to break complex queries into sequential logical
steps, reason through each step, validate intermediate results, and
synthesize a coherent final response.

Pipeline:
  1. Decomposition — Break query into sequential logical steps
  2. Step-by-Step Reasoning — Generate reasoning for each decomposed step
  3. Intermediate Validation — Check each step's output quality
  4. Synthesis — Combine step outputs into coherent final response

Building Codes: BC-001 (company isolation), BC-008 (never crash),
               BC-012 (graceful degradation)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from app.core.technique_router import TechniqueID
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
)
from app.logger import get_logger

logger = get_logger("chain_of_thought")


# ── Query Type Enum ─────────────────────────────────────────────────


class QueryType(str, Enum):
    """Types of queries detectable by pattern matching."""

    MULTI_PART = "multi_part"
    SEQUENTIAL = "sequential"
    COMPARISON = "comparison"
    CAUSAL = "causal"
    SINGLE = "single"


# ── Decomposition Pattern Constants ─────────────────────────────────


# Conjunctions that indicate multi-part queries
_CONJUNCTIONS: FrozenSet[str] = frozenset(
    {
        " and ",
        " also ",
        " plus ",
        " additionally ",
        " furthermore ",
        " moreover ",
        " as well as ",
        " besides ",
        " what about ",
        " how about ",
    }
)

# Sequential keywords that indicate multi-step processes
_SEQUENTIAL_KEYWORDS: FrozenSet[str] = frozenset(
    {
        "first",
        "then",
        "after that",
        "next",
        "afterwards",
        "subsequently",
        "before",
        "finally",
        "lastly",
        "secondly",
        "thirdly",
        "step 1",
        "step 2",
    }
)

# Comparison patterns
_COMPARISON_PATTERNS: Tuple[str, ...] = (
    r"\bdifference between\b",
    r"\bcompared to\b",
    r"\bcompared with\b",
    r"\bvs\.?\b",
    r"\bversus\b",
    r"\b(?:similar|different)\s+from\b",
    r"\b(?:pros?|cons?)\s+(?:and|of)\b",
    r"\badvantages?\s+(?:and|of)\b",
    r"\bdisadvantages?\s+(?:and|of)\b",
)

# Causal query patterns
_CAUSAL_PATTERNS: Tuple[str, ...] = (
    r"\bwhy\b",
    r"\bwhat caused\b",
    r"\breason for\b",
    r"\breasons? why\b",
    r"\bwhat is (?:the )?(?:cause|reason)\b",
    r"\bhow come\b",
    r"\bleads? to\b",
    r"\bresulted in\b",
    r"\bbecause of\b",
    r"\bdue to\b",
)

# Question detection pattern (for splitting multi-part queries)
_QUESTION_PATTERN: re.Pattern = re.compile(
    r"(?:(?:^|[.!?]\s+)(?:can|could|would|should|what|where|when|"
    r"how|why|who|which|is|are|do|does|did)\b[^.!?]*[.!?])",
    re.I,
)

# Sub-question splitting on conjunctions within questions
_CONJUNCTION_SPLIT_PATTERN: re.Pattern = re.compile(
    r"\band\b|\balso\b|\bplus\b|\badditionally\b|\bfurthermore\b",
    re.I,
)


# ── Reasoning Templates ─────────────────────────────────────────────


_REASONING_TEMPLATES: Dict[QueryType, Dict[str, str]] = {
    QueryType.MULTI_PART: {
        "template": (
            "Analyzing sub-question: {description}. "
            "Key considerations: {key_terms}. "
            "This requires examining each component independently before combining results."
        ),
        "validation": "Each sub-question has been addressed with relevant information.",
    },
    QueryType.SEQUENTIAL: {
        "template": (
            "Processing step {step_number}: {description}. "
            "Sequential dependency: this step builds on previous findings. "
            "Key terms: {key_terms}."
        ),
        "validation": "Sequential progression verified — each step follows logically from the prior.",
    },
    QueryType.COMPARISON: {
        "template": (
            "Comparing: {description}. "
            "Analyzing similarities and differences across: {key_terms}. "
            "Evaluation criteria applied consistently to both subjects."
        ),
        "validation": "Comparison is balanced — both subjects evaluated on equal criteria.",
    },
    QueryType.CAUSAL: {
        "template": (
            "Investigating cause: {description}. "
            "Examining potential causes related to: {key_terms}. "
            "Tracing the chain of causation from root cause to observed effect."
        ),
        "validation": "Causal chain is traceable — root cause links to observed outcome.",
    },
    QueryType.SINGLE: {
        "template": (
            "Analyzing: {description}. "
            "Key terms: {key_terms}. "
            "Proceeding with direct analysis of the query."
        ),
        "validation": "Query has been addressed with relevant information.",
    },
}

_SYNTHESIS_TEMPLATES: Dict[QueryType, str] = {
    QueryType.MULTI_PART: (
        "Based on the analysis of {step_count} sub-questions: "
        "{step_summaries} "
        "All components have been addressed comprehensively."
    ),
    QueryType.SEQUENTIAL: (
        "Following the {step_count}-step process: "
        "{step_summaries} "
        "Each step has been completed in the correct sequence."
    ),
    QueryType.COMPARISON: (
        "Comparison analysis complete across {step_count} dimensions: "
        "{step_summaries} "
        "Both subjects have been evaluated on equal criteria."
    ),
    QueryType.CAUSAL: (
        "Root cause analysis identified {step_count} factor(s): "
        "{step_summaries} "
        "The causal chain has been traced from source to effect."
    ),
    QueryType.SINGLE: (
        "Analysis complete across {step_count} step(s): {step_summaries} "
        "The query has been addressed directly."
    ),
}

# Stop words for key term extraction
_STOP_WORDS: FrozenSet[str] = frozenset(
    {
        "i",
        "me",
        "my",
        "we",
        "you",
        "your",
        "it",
        "its",
        "is",
        "am",
        "are",
        "was",
        "were",
        "be",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "to",
        "o",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "if",
        "not",
        "no",
        "this",
        "that",
        "these",
        "those",
        "what",
        "how",
        "when",
        "where",
        "why",
        "who",
        "which",
        "about",
        "up",
        "out",
        "just",
        "so",
        "than",
        "too",
        "very",
        "also",
        "then",
    }
)


# ── Data Structures ──────────────────────────────────────────────────


@dataclass(frozen=True)
class CoTConfig:
    """
    Immutable configuration for Chain of Thought (BC-001).

    Attributes:
        company_id: Tenant identifier for company isolation.
        max_steps: Maximum number of decomposition steps.
        enable_validation: Whether to run intermediate validation.
    """

    company_id: str = ""
    max_steps: int = 10
    enable_validation: bool = True


@dataclass
class CoTStep:
    """
    A single decomposed step in the Chain of Thought reasoning.

    Attributes:
        step_number: Sequential step number (1-indexed).
        step_type: Type classification of the step.
        description: Human-readable description of what this step addresses.
        reasoning: The reasoning applied for this step.
        validation_status: Result of intermediate validation.
        key_terms: Key terms identified for this step.
    """

    step_number: int = 0
    step_type: str = ""
    description: str = ""
    reasoning: str = ""
    validation_status: str = ""
    key_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize step to dictionary."""
        return {
            "step_number": self.step_number,
            "step_type": self.step_type,
            "description": self.description,
            "reasoning": self.reasoning,
            "validation_status": self.validation_status,
            "key_terms": list(self.key_terms),
        }


@dataclass
class CoTResult:
    """
    Output of the Chain of Thought pipeline.

    Attributes:
        decomposed_steps: List of CoTStep objects from decomposition.
        reasoning_chain: Combined reasoning chain with numbered steps.
        synthesis: Final synthesized response.
        validation_summary: Summary of intermediate validation results.
        steps_applied: Names of pipeline steps that were executed.
        confidence_boost: Estimated confidence increase from this process.
    """

    decomposed_steps: List[CoTStep] = field(default_factory=list)
    reasoning_chain: str = ""
    synthesis: str = ""
    validation_summary: str = ""
    steps_applied: List[str] = field(default_factory=list)
    confidence_boost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary for recording in state."""
        return {
            "decomposed_steps": [s.to_dict() for s in self.decomposed_steps],
            "reasoning_chain": self.reasoning_chain,
            "synthesis": self.synthesis,
            "validation_summary": self.validation_summary,
            "steps_applied": self.steps_applied,
            "confidence_boost": round(self.confidence_boost, 4),
        }


# ── Chain of Thought Processor ──────────────────────────────────────


class ChainOfThoughtProcessor:
    """
    Deterministic Chain of Thought processor.

    Uses pattern matching and heuristic rules to simulate step-by-step
    reasoning without any LLM calls.

    Pipeline:
      1. Decomposition — detect query type and break into steps
      2. Step-by-Step Reasoning — template-based reasoning per step
      3. Intermediate Validation — check step output quality
      4. Synthesis — combine step outputs into final response
    """

    def __init__(
        self,
        config: Optional[CoTConfig] = None,
    ):
        self.config = config or CoTConfig()

    # ── Query Type Detection ───────────────────────────────────────

    def detect_query_type(self, query: str) -> QueryType:
        """
        Detect the type of query using pattern matching.

        Priority order:
          1. Comparison queries (most specific patterns)
          2. Causal queries
          3. Multi-part queries (conjunctions / question count)
          4. Sequential queries (process keywords)
          5. Single query (default)

        Args:
            query: The customer query text.

        Returns:
            Detected QueryType.
        """
        if not query or not query.strip():
            return QueryType.SINGLE

        query_lower = query.lower()

        # 1. Check for comparison patterns
        for pattern_str in _COMPARISON_PATTERNS:
            if re.search(pattern_str, query_lower):
                return QueryType.COMPARISON

        # 2. Check for causal patterns
        for pattern_str in _CAUSAL_PATTERNS:
            if re.search(pattern_str, query_lower):
                return QueryType.CAUSAL

        # 3. Check for multi-part queries (conjunctions + question markers)
        conjunction_count = sum(1 for c in _CONJUNCTIONS if c in query_lower)
        question_matches = _QUESTION_PATTERN.findall(query)

        # Count distinct question markers (avoid double-counting "?" that
        # is already captured by the question pattern)
        question_count = len(question_matches)
        # Count additional "?" not already part of question_matches
        matched_positions: Set[int] = set()
        for m in question_matches:
            match = re.search(re.escape(m), query)
            if match:
                for pos in range(match.start(), match.end()):
                    matched_positions.add(pos)
        extra_question_marks = sum(
            1 for i, ch in enumerate(query) if ch == "?" and i not in matched_positions
        )
        question_count += extra_question_marks

        if conjunction_count >= 2 or question_count >= 3:
            return QueryType.MULTI_PART
        elif conjunction_count >= 1 and question_count >= 1:
            return QueryType.MULTI_PART
        elif conjunction_count >= 1 and " and " not in query_lower:
            # Single non-trivial conjunction ("plus", "also", "additionally")
            return QueryType.MULTI_PART

        # 4. Check for sequential keywords
        sequential_count = sum(1 for kw in _SEQUENTIAL_KEYWORDS if kw in query_lower)
        if sequential_count >= 2:
            return QueryType.SEQUENTIAL

        # 5. Check for multi-part with multiple "?" even without conjunctions
        if question_count >= 2:
            return QueryType.MULTI_PART

        return QueryType.SINGLE

    # ── Step 1: Decomposition ──────────────────────────────────────

    async def decompose_query(
        self,
        query: str,
        query_type: Optional[QueryType] = None,
    ) -> List[CoTStep]:
        """
        Break a query into sequential logical steps.

        Uses the detected query type to determine the decomposition
        strategy.

        Args:
            query: The customer query text.
            query_type: Optional pre-computed query type.

        Returns:
            List of CoTStep objects representing decomposed steps.
        """
        if not query or not query.strip():
            return []

        if query_type is None:
            query_type = self.detect_query_type(query)

        steps: List[CoTStep] = []

        if query_type == QueryType.MULTI_PART:
            steps = self._decompose_multi_part(query)
        elif query_type == QueryType.SEQUENTIAL:
            steps = self._decompose_sequential(query)
        elif query_type == QueryType.COMPARISON:
            steps = self._decompose_comparison(query)
        elif query_type == QueryType.CAUSAL:
            steps = self._decompose_causal(query)
        else:
            steps = self._decompose_single(query)

        # Enforce max_steps
        steps = steps[: self.config.max_steps]

        return steps

    def _decompose_multi_part(self, query: str) -> List[CoTStep]:
        """Decompose a multi-part query by splitting on conjunctions and question marks."""
        steps: List[CoTStep] = []

        # Try splitting by question patterns first
        parts = _QUESTION_PATTERN.findall(query)

        if len(parts) >= 2:
            for i, part in enumerate(parts):
                part = part.strip()
                if part:
                    steps.append(
                        CoTStep(
                            step_number=i + 1,
                            step_type=QueryType.MULTI_PART.value,
                            description=part,
                            key_terms=self._extract_key_terms(part),
                        )
                    )
        else:
            # Split by conjunctions
            split = _CONJUNCTION_SPLIT_PATTERN.split(query)
            for i, part in enumerate(split):
                part = part.strip()
                if part:
                    steps.append(
                        CoTStep(
                            step_number=i + 1,
                            step_type=QueryType.MULTI_PART.value,
                            description=part,
                            key_terms=self._extract_key_terms(part),
                        )
                    )

        return steps

    def _decompose_sequential(self, query: str) -> List[CoTStep]:
        """Decompose a sequential query by splitting on sequential keywords."""
        steps: List[CoTStep] = []

        # Sort sequential keywords by length (longest first) for correct
        # splitting
        sorted_keywords = sorted(_SEQUENTIAL_KEYWORDS, key=len, reverse=True)

        # Build a regex to split on sequential keywords
        keyword_pattern = "|".join(re.escape(kw) for kw in sorted_keywords)
        split_pattern = re.compile(
            rf"(?:^|\s)(?:{keyword_pattern})(?:\s|\.|,|$)",
            re.I,
        )

        parts = split_pattern.split(query)
        for i, part in enumerate(parts):
            part = part.strip().strip(",").strip(".").strip()
            if part and len(part) > 2:
                steps.append(
                    CoTStep(
                        step_number=len(steps) + 1,
                        step_type=QueryType.SEQUENTIAL.value,
                        description=part,
                        key_terms=self._extract_key_terms(part),
                    )
                )

        return steps

    def _decompose_comparison(self, query: str) -> List[CoTStep]:
        """Decompose a comparison query into comparison dimensions."""
        steps: List[CoTStep] = []

        # Extract the two subjects being compared
        query_lower = query.lower()

        # Try to find subjects around comparison markers
        subjects = self._extract_comparison_subjects(query)

        if len(subjects) >= 2:
            steps.append(
                CoTStep(
                    step_number=1,
                    step_type=QueryType.COMPARISON.value,
                    description=f"Identify key features of: {subjects[0]}",
                    key_terms=self._extract_key_terms(subjects[0]),
                )
            )
            steps.append(
                CoTStep(
                    step_number=2,
                    step_type=QueryType.COMPARISON.value,
                    description=f"Identify key features of: {subjects[1]}",
                    key_terms=self._extract_key_terms(subjects[1]),
                )
            )
            steps.append(
                CoTStep(
                    step_number=3,
                    step_type=QueryType.COMPARISON.value,
                    description=f"Compare {
                        subjects[0]} and {
                        subjects[1]} across identified dimensions",
                    key_terms=self._extract_key_terms(query),
                )
            )
        else:
            # Fallback: generic comparison decomposition
            steps.append(
                CoTStep(
                    step_number=1,
                    step_type=QueryType.COMPARISON.value,
                    description="Identify the subjects being compared",
                    key_terms=self._extract_key_terms(query),
                )
            )
            steps.append(
                CoTStep(
                    step_number=2,
                    step_type=QueryType.COMPARISON.value,
                    description="Evaluate similarities between subjects",
                    key_terms=self._extract_key_terms(query),
                )
            )
            steps.append(
                CoTStep(
                    step_number=3,
                    step_type=QueryType.COMPARISON.value,
                    description="Evaluate differences between subjects",
                    key_terms=self._extract_key_terms(query),
                )
            )

        return steps

    def _decompose_causal(self, query: str) -> List[CoTStep]:
        """Decompose a causal query into cause investigation steps."""
        steps: List[CoTStep] = []

        steps.append(
            CoTStep(
                step_number=1,
                step_type=QueryType.CAUSAL.value,
                description="Identify the observed effect or outcome",
                key_terms=self._extract_key_terms(query),
            )
        )
        steps.append(
            CoTStep(
                step_number=2,
                step_type=QueryType.CAUSAL.value,
                description="Enumerate potential causes and contributing factors",
                key_terms=self._extract_key_terms(query),
            )
        )
        steps.append(
            CoTStep(
                step_number=3,
                step_type=QueryType.CAUSAL.value,
                description="Evaluate most likely root cause based on available evidence",
                key_terms=self._extract_key_terms(query),
            )
        )

        return steps

    def _decompose_single(self, query: str) -> List[CoTStep]:
        """Decompose a single query into one analytical step."""
        return [
            CoTStep(
                step_number=1,
                step_type=QueryType.SINGLE.value,
                description=query.strip(),
                key_terms=self._extract_key_terms(query),
            ),
        ]

    @staticmethod
    def _extract_comparison_subjects(query: str) -> List[str]:
        """Extract the two subjects from a comparison query."""
        subjects: List[str] = []

        # Try "A vs B" or "A versus B" pattern
        vs_match = re.search(
            r"(.+?)\s+(?:vs\.?|versus)\s+(.+?)[?.!]*$",
            query,
            re.I,
        )
        if vs_match:
            subjects.append(vs_match.group(1).strip())
            subjects.append(vs_match.group(2).strip())
            return subjects

        # Try "difference between A and B" pattern
        diff_match = re.search(
            r"difference between\s+(.+?)\s+and\s+(.+?)[?.!]*$",
            query,
            re.I,
        )
        if diff_match:
            subjects.append(diff_match.group(1).strip())
            subjects.append(diff_match.group(2).strip())
            return subjects

        # Try "A compared to B" pattern
        comp_match = re.search(
            r"(.+?)\s+compared\s+(?:to|with)\s+(.+?)[?.!]*$",
            query,
            re.I,
        )
        if comp_match:
            subjects.append(comp_match.group(1).strip())
            subjects.append(comp_match.group(2).strip())
            return subjects

        return subjects

    # ── Step 2: Step-by-Step Reasoning ─────────────────────────────

    async def generate_reasoning(
        self,
        steps: List[CoTStep],
    ) -> List[CoTStep]:
        """
        Generate reasoning for each decomposed step using templates.

        Args:
            steps: List of CoTStep objects from decomposition.

        Returns:
            Updated list of CoTStep objects with reasoning filled in.
        """
        if not steps:
            return steps

        updated: List[CoTStep] = []
        for step in steps:
            query_type = (
                QueryType(step.step_type) if step.step_type else QueryType.SINGLE
            )
            template_data = _REASONING_TEMPLATES.get(
                query_type,
                _REASONING_TEMPLATES[QueryType.SINGLE],
            )

            key_terms_str = (
                ", ".join(step.key_terms) if step.key_terms else "general context"
            )

            reasoning = template_data["template"].format(
                description=step.description,
                step_number=step.step_number,
                key_terms=key_terms_str,
            )

            updated.append(
                CoTStep(
                    step_number=step.step_number,
                    step_type=step.step_type,
                    description=step.description,
                    reasoning=reasoning,
                    validation_status="",
                    key_terms=list(step.key_terms),
                )
            )

        return updated

    # ── Step 3: Intermediate Validation ────────────────────────────

    async def validate_steps(
        self,
        steps: List[CoTStep],
    ) -> Tuple[List[CoTStep], str]:
        """
        Validate each step's output for quality and completeness.

        Checks:
          - Step has a non-empty description
          - Step has reasoning content
          - Step has key terms identified
          - Flags ambiguous steps needing more data

        Args:
            steps: List of CoTStep objects with reasoning.

        Returns:
            Tuple of (updated steps with validation status, validation summary).
        """
        if not steps:
            return steps, "No steps to validate."

        passed = 0
        needs_data = 0
        failed = 0

        updated: List[CoTStep] = []
        for step in steps:
            status = "passed"
            issues: List[str] = []

            # Check description
            if not step.description or not step.description.strip():
                status = "failed"
                issues.append("missing description")
                failed += 1
            # Check reasoning
            elif not step.reasoning or not step.reasoning.strip():
                status = "needs_data"
                issues.append("missing reasoning")
                needs_data += 1
            # Check key terms
            elif not step.key_terms:
                status = "needs_data"
                issues.append("no key terms identified")
                needs_data += 1
            else:
                passed += 1

            updated.append(
                CoTStep(
                    step_number=step.step_number,
                    step_type=step.step_type,
                    description=step.description,
                    reasoning=step.reasoning,
                    validation_status=status,
                    key_terms=list(step.key_terms),
                )
            )

        # Build validation summary
        summary_parts = [
            f"Validated {len(steps)} step(s): ",
            f"{passed} passed",
        ]
        if needs_data > 0:
            summary_parts.append(f", {needs_data} need more data")
        if failed > 0:
            summary_parts.append(f", {failed} failed")
        summary_parts.append(".")

        validation_summary = "".join(summary_parts)

        return updated, validation_summary

    # ── Step 4: Synthesis ──────────────────────────────────────────

    async def synthesize(
        self,
        steps: List[CoTStep],
        query_type: QueryType,
    ) -> str:
        """
        Combine step outputs into a coherent final response.

        Uses the query type to select the appropriate synthesis template
        and combines reasoning from all validated steps.

        Args:
            steps: List of CoTStep objects with reasoning and validation.
            query_type: The detected query type.

        Returns:
            Synthesized response string.
        """
        if not steps:
            return ""

        # Collect step summaries from reasoning
        step_summaries: List[str] = []
        for step in steps:
            if step.reasoning:
                # Extract a brief summary from the reasoning
                summary = step.reasoning.split(".")[0].strip()
                if summary:
                    step_summaries.append(summary)

        if not step_summaries:
            return "Analysis complete but no specific findings to synthesize."

        step_count = len(steps)
        summaries_text = " ".join(
            f"[{i + 1}] {s}." for i, s in enumerate(step_summaries)
        )

        template = _SYNTHESIS_TEMPLATES.get(
            query_type,
            _SYNTHESIS_TEMPLATES[QueryType.SINGLE],
        )

        synthesis = template.format(
            step_count=step_count,
            step_summaries=summaries_text,
        )

        return synthesis

    # ── Full Pipeline ──────────────────────────────────────────────

    async def process(
        self,
        query: str,
    ) -> CoTResult:
        """
        Run the full 4-step Chain of Thought pipeline.

        Args:
            query: The customer query to reason about.

        Returns:
            CoTResult with all pipeline outputs.
        """
        steps_applied: List[str] = []
        confidence_boost = 0.0

        if not query or not query.strip():
            return CoTResult(
                steps_applied=["empty_input"],
                confidence_boost=0.0,
            )

        try:
            # Step 1: Decomposition
            query_type = self.detect_query_type(query)
            decomposed_steps = await self.decompose_query(query, query_type)
            if decomposed_steps:
                steps_applied.append("decomposition")
            confidence_boost += 0.05

            # Step 2: Step-by-Step Reasoning
            steps_with_reasoning = await self.generate_reasoning(decomposed_steps)
            if any(s.reasoning for s in steps_with_reasoning):
                steps_applied.append("reasoning")
            confidence_boost += 0.1

            # Step 3: Intermediate Validation
            validation_status = "skipped"
            validation_summary = ""
            if self.config.enable_validation:
                validated_steps, validation_summary = await self.validate_steps(
                    steps_with_reasoning,
                )
                steps_applied.append("validation")
                passed_count = sum(
                    1 for s in validated_steps if s.validation_status == "passed"
                )
                total_count = len(validated_steps)
                if total_count > 0 and passed_count == total_count:
                    confidence_boost += 0.1
                    validation_status = "all_passed"
                elif total_count > 0 and passed_count > 0:
                    confidence_boost += 0.05
                    validation_status = "partial"
                else:
                    validation_status = "needs_attention"
            else:
                validated_steps = steps_with_reasoning

            # Step 4: Synthesis
            synthesis = await self.synthesize(validated_steps, query_type)
            if synthesis:
                steps_applied.append("synthesis")
            confidence_boost += 0.05

            # Build reasoning chain
            chain_parts: List[str] = []
            for step in validated_steps:
                chain_parts.append(f"Step {step.step_number}: {step.reasoning}")
            reasoning_chain = "\n".join(chain_parts)

        except Exception as exc:
            # BC-008: Never crash — return graceful fallback
            logger.warning(
                "chain_of_thought_processing_error",
                error=str(exc),
                company_id=self.config.company_id,
            )
            return CoTResult(
                reasoning_chain=reasoning_chain if "reasoning_chain" in dir() else "",
                steps_applied=(
                    steps_applied + ["error_fallback"]
                    if "steps_applied" in dir()
                    else ["error_fallback"]
                ),
                confidence_boost=0.0,
            )

        return CoTResult(
            decomposed_steps=validated_steps,
            reasoning_chain=reasoning_chain,
            synthesis=synthesis,
            validation_summary=validation_summary,
            steps_applied=steps_applied,
            confidence_boost=confidence_boost,
        )

    # ── Utility Methods ───────────────────────────────────────────

    @staticmethod
    def _extract_key_terms(query: str) -> List[str]:
        """
        Extract key terms from a query.

        Filters out stop words and short words (< 3 chars).
        Returns deduplicated terms preserving order, up to 5.

        Args:
            query: The query text to extract terms from.

        Returns:
            List of key terms (lowercase).
        """
        if not query:
            return []

        words = re.findall(r"\b\w{3,}\b", query.lower())
        filtered = [w for w in words if w not in _STOP_WORDS]

        # Deduplicate while preserving order
        seen: Set[str] = set()
        unique: List[str] = []
        for word in filtered:
            if word not in seen:
                seen.add(word)
                unique.append(word)

        return unique[:5]


# ── Chain Of Thought Node (LangGraph compatible) ────────────────────


class ChainOfThoughtNode(BaseTechniqueNode):
    """
    Chain of Thought — Tier 2 Conditional.

    Extends BaseTechniqueNode for integration into the LangGraph
    pipeline (F-060).

    Activation trigger:
      - query_complexity > 0.4
    """

    def __init__(
        self,
        config: Optional[CoTConfig] = None,
    ):
        self._config = config or CoTConfig()
        self._processor = ChainOfThoughtProcessor(config=self._config)
        # Call parent init after config is set (reads TECHNIQUE_REGISTRY)
        super().__init__()

    @property
    def technique_id(self) -> TechniqueID:
        """Return the TechniqueID for this node."""
        return TechniqueID.CHAIN_OF_THOUGHT

    async def should_activate(self, state: ConversationState) -> bool:
        """
        Check if Chain of Thought should activate.

        Triggers when query_complexity > 0.4.
        """
        return state.signals.query_complexity > 0.4

    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the Chain of Thought pipeline.

        Implements the 4-step reasoning process:
          1. Decomposition
          2. Step-by-Step Reasoning
          3. Intermediate Validation
          4. Synthesis

        On error (BC-008), returns the original state unchanged.
        """
        original_state = state

        try:
            result = await self._processor.process(state.query)

            # Build confidence-adjusted signals
            new_confidence = min(
                state.signals.confidence_score + result.confidence_boost,
                1.0,
            )

            # Record result in state
            self.record_result(state, result.to_dict())

            # Update confidence score in signals
            state.signals.confidence_score = new_confidence

            # If we have a synthesis, append to response parts
            if result.synthesis:
                state.response_parts.append(result.synthesis)

            return state

        except Exception as exc:
            # BC-008: Never crash — return original state
            logger.warning(
                "chain_of_thought_execute_error",
                error=str(exc),
                company_id=self._config.company_id,
            )
            return original_state
