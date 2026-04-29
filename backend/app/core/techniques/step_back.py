"""
F-142: Step-Back Prompting — Tier 2 Conditional

Broadens narrow or stuck reasoning by stepping back to generate broader
contextual questions, analyzing them first, then narrowing back to answer
the original query with enriched context.

Pipeline:
  1. Detection — identify narrow context or stuck reasoning
  2. Step-Back — generate broader contextual questions
  3. Broader Analysis — answer broader question first, then narrow back
  4. Refined Response — answer original query with broader context

Trigger: confidence < 0.7 OR reasoning_loop_detected OR gsd_state == DIAGNOSIS

Performance: deterministic/heuristic-based (NO LLM calls).
Building Codes: BC-001 (company isolation), BC-008 (never crash),
               BC-012 (graceful degradation)
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.technique_router import (
    TechniqueID,
    TECHNIQUE_REGISTRY,
)
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
    GSDState,
)
from app.logger import get_logger

logger = get_logger("step_back")


# ── Entity / Jargon Patterns ─────────────────────────────────────────

# Patterns that indicate a specific entity reference (order, invoice, etc.)
_ENTITY_PATTERNS: Tuple[str, ...] = (
    r"\border\s*(?:#|num(?:ber)?)\s*\w+",
    r"\binvoice\s*(?:#|num(?:ber)?)\s*\w+",
    r"\bticket\s*(?:#|num(?:ber)?)?\s*\w+",
    r"\bcase\s*(?:#|num(?:ber)?)?\s*\w+",
    r"\bsubscription\s*(?:#|id)?\s*\w+",
    r"\bpayment\s*(?:#|id|ref)?\s*\w+",
    r"\brefund\s*(?:#|id|req(?:uest)?)?\s*\w+",
    r"\btracking\s*(?:#|num(?:ber)?)?\s*\w+",
    r"\baccount\s*(?:#|id)?\s*\w+",
    r"\btxn\s*(?:#|id)?\s*\w+",
    r"\btransaction\s*(?:#|id)?\s*\w+",
    r"#\w+",
)

# Technical jargon terms that suggest a need for clarification
_TECHNICAL_JARGON: Set[str] = {
    "api", "webhook", "endpoint", "oauth", "ssl", "tls", "dns",
    "cdn", "latency", "throughput", "bandwidth", "payload",
    "middleware", "microservice", "container", "kubernetes", "docker",
    "load balancer", "rate limit", "idempotent", "cron", "daemon",
    "protobuf", "graphql", "rest", "grpc", "tcp", "udp", "http",
    "ssh", "sftp", "ci/cd", "deployment", "rollback", "hotfix",
    "schema", "migration", "index", "replica", "shard", "cluster",
    "serialization", "deserialization", "authentication", "authorization",
    "jwt", "token", "nonce", "hash", "salt", "encryption",
}

# Ambiguous intent trigger words (could mean multiple things)
_AMBIGUOUS_WORDS: Set[str] = {
    "fix", "update", "change", "issue", "problem", "help", "check",
    "what", "how", "why", "when", "set up", "setup", "configure",
    "manage", "access", "connect", "integrate", "sync", "transfer",
}

# ── Broadening Templates ─────────────────────────────────────────────

_BROADENING_TEMPLATES: Dict[str, List[str]] = {
    "entity_specific": [
        "What is the customer trying to accomplish with {entity}?",
        "What is the broader context around {entity}?",
        "What history or status is relevant to {entity}?",
    ],
    "single_word": [
        "Can you provide more details about '{query}'?",
        "What specific aspect of '{query}' do you need help with?",
        "Are you asking about '{query}' in relation to an order, account, or billing?",
    ],
    "technical_jargon": [
        "What business problem is the customer experiencing that involves technical terms?",
        "How can the technical request be translated into a concrete action?",
        "What system or feature is the customer referring to with these technical terms?",
    ],
    "ambiguous_intent": [
        "What are the possible interpretations of this customer request?",
        "What additional context would clarify the customer's intent?",
        "Which department or feature area does this request relate to?",
    ],
    "stuck_reasoning": [
        "What broader information is needed to break out of the current reasoning loop?",
        "What alternative approach could be taken to resolve this issue?",
        "What context from earlier in the conversation has been overlooked?",
    ],
}


# ── Data Structures ──────────────────────────────────────────────────


@dataclass(frozen=True)
class StepBackConfig:
    """Immutable configuration for Step-Back processing (BC-001)."""

    company_id: str = ""
    max_broadening_levels: int = 3
    enable_context_injection: bool = True


@dataclass
class StepBackResult:
    """Output of Step-Back processing."""

    detection_result: Optional[NarrowQueryDetector] = None
    broadened_queries: List[str] = field(default_factory=list)
    analysis_result: str = ""
    refined_response: str = ""
    steps_applied: List[str] = field(default_factory=list)
    context_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detection_result": {
                "is_narrow": self.detection_result.is_narrow,
                "narrow_type": self.detection_result.narrow_type,
                "confidence": self.detection_result.confidence,
                "suggested_broadening": self.detection_result.suggested_broadening,
            } if self.detection_result else None,
            "broadened_queries": self.broadened_queries,
            "analysis_result": self.analysis_result,
            "refined_response": self.refined_response,
            "steps_applied": self.steps_applied,
            "context_score": round(
                self.context_score,
                4),
        }


@dataclass
class NarrowQueryDetector:
    """Result of narrow query detection."""

    is_narrow: bool = False
    narrow_type: str = ""
    confidence: float = 0.0
    suggested_broadening: str = ""


# ── Step-Back Processor ─────────────────────────────────────────────


class StepBackProcessor:
    """
    Step-Back Prompting processor (F-142).

    Deterministic, heuristic-based (no LLM calls).
    Broadens narrow context or unsticks reasoning loops.

    Pipeline:
      1. Detect narrow queries or stuck reasoning
      2. Generate broader contextual questions
      3. Analyze broadened context quality
      4. Produce refined response with broader context
    """

    def __init__(self, config: Optional[StepBackConfig] = None):
        self.config = config or StepBackConfig()
        self._entity_patterns = self._compile_entity_patterns()

    # ── Pattern Compilation ────────────────────────────────────────

    def _compile_entity_patterns(self) -> List[re.Pattern]:
        """Compile entity reference regex patterns."""
        patterns = []
        for pattern_str in _ENTITY_PATTERNS:
            try:
                patterns.append(re.compile(pattern_str, re.I))
            except re.error:
                logger.warning(
                    "step_back_invalid_entity_pattern",
                    pattern=pattern_str)
        return patterns

    # ── Step 1: Detection ──────────────────────────────────────────

    async def detect_narrow_query(
        self,
        query: str,
        reasoning_thread: Optional[List[str]] = None,
    ) -> NarrowQueryDetector:
        """
        Detect whether a query is narrow or reasoning is stuck.

        Checks in priority order:
          1. stuck_reasoning — reasoning loop detected
          2. entity_specific — specific entity but no context
          3. single_word — very short query (1-3 words)
          4. technical_jargon — heavy jargon without clarification
          5. ambiguous_intent — multiple possible intents
        """
        if not query or not query.strip():
            return NarrowQueryDetector(
                is_narrow=True,
                narrow_type="single_word",
                confidence=1.0,
                suggested_broadening="Empty or blank query",
            )

        stripped = query.strip()

        # 1. Check for stuck reasoning
        if reasoning_thread:
            detector = self._detect_stuck_reasoning(reasoning_thread)
            if detector.is_narrow:
                return detector

        # 2. Check for entity-specific queries
        detector = self._detect_entity_specific(stripped)
        if detector.is_narrow:
            return detector

        # 3. Check for ambiguous intent (before single_word to
        #    prioritize specificity — 3 ambiguous words > just 'short')
        detector = self._detect_ambiguous_intent(stripped)
        if detector.is_narrow:
            return detector

        # 4. Check for single-word queries
        detector = self._detect_single_word(stripped)
        if detector.is_narrow:
            return detector

        # 5. Check for technical jargon
        detector = self._detect_technical_jargon(stripped)
        if detector.is_narrow:
            return detector

        return NarrowQueryDetector(
            is_narrow=False,
            narrow_type="none",
            confidence=0.0,
            suggested_broadening="",
        )

    def _detect_stuck_reasoning(
        self, reasoning_thread: List[str],
    ) -> NarrowQueryDetector:
        """Detect if reasoning is looping (same words 3+ times)."""
        if not reasoning_thread:
            return NarrowQueryDetector()

        # Combine all reasoning entries and count word frequencies
        all_text = " ".join(reasoning_thread).lower()
        words = re.findall(r"\b\w+\b", all_text)
        if not words:
            return NarrowQueryDetector()

        # Filter out common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "and", "but", "or", "nor", "not", "so",
            "if", "then", "than", "too", "very", "just", "about", "also",
            "that", "this", "these", "those", "it", "its", "i", "me",
            "my", "we", "our", "you", "your", "he", "she", "they", "them",
        }
        content_words = [w for w in words if w not in stop_words]
        if not content_words:
            return NarrowQueryDetector()

        word_counts = Counter(content_words)

        # Check if any word appears 3+ times across the reasoning thread
        loop_words = [w for w, c in word_counts.items() if c >= 3]
        if loop_words:
            top_word = loop_words[0]
            confidence = min(
                1.0,
                word_counts[top_word] /
                len(reasoning_thread))
            return NarrowQueryDetector(
                is_narrow=True,
                narrow_type="stuck_reasoning",
                confidence=round(confidence, 4),
                suggested_broadening=(
                    f"Reasoning loop detected: '{top_word}' repeated "
                    f"{word_counts[top_word]} times across thread"
                ),
            )

        return NarrowQueryDetector()

    def _detect_entity_specific(self, query: str) -> NarrowQueryDetector:
        """Detect specific entity mentions lacking context."""
        matches = []
        for pattern in self._entity_patterns:
            found = pattern.findall(query)
            matches.extend(found)

        if matches:
            # If the query is JUST the entity reference, it's narrow
            words = re.findall(r"\b\w+\b", query.lower())
            # Very short query with entity = definitely narrow
            if len(words) <= 5:
                entity = matches[0]
                confidence = max(0.7, 1.0 - len(words) * 0.05)
                return NarrowQueryDetector(
                    is_narrow=True,
                    narrow_type="entity_specific",
                    confidence=round(confidence, 4),
                    suggested_broadening=(
                        f"Specific entity '{entity}' detected with "
                        f"limited context ({len(words)} words)"
                    ),
                )

        return NarrowQueryDetector()

    def _detect_single_word(self, query: str) -> NarrowQueryDetector:
        """Detect very short queries (1-3 words)."""
        words = re.findall(r"\b\w+\b", query)
        word_count = len(words)

        if word_count <= 3:
            confidence = 1.0 - (word_count * 0.2)
            return NarrowQueryDetector(
                is_narrow=True,
                narrow_type="single_word",
                confidence=round(max(0.3, confidence), 4),
                suggested_broadening=(
                    f"Very short query ({word_count} words): "
                    f"'{query}'"
                ),
            )

        return NarrowQueryDetector()

    def _detect_technical_jargon(self, query: str) -> NarrowQueryDetector:
        """Detect queries heavy on jargon without clarification."""
        words = re.findall(r"\b\w+\b", query.lower())
        if not words:
            return NarrowQueryDetector()

        jargon_count = sum(1 for w in words if w in _TECHNICAL_JARGON)
        jargon_ratio = jargon_count / len(words)

        # If > 30% of words are jargon and query is short-ish
        if jargon_ratio >= 0.3 and len(words) <= 15:
            confidence = min(1.0, jargon_ratio + 0.3)
            return NarrowQueryDetector(
                is_narrow=True,
                narrow_type="technical_jargon",
                confidence=round(confidence, 4),
                suggested_broadening=(
                    f"High jargon density ({jargon_ratio:.0%}): "
                    f"{jargon_count}/{len(words)} technical terms detected"
                ),
            )

        return NarrowQueryDetector()

    def _detect_ambiguous_intent(self, query: str) -> NarrowQueryDetector:
        """Detect queries with multiple possible intents."""
        words = re.findall(r"\b\w+\b", query.lower())
        if not words:
            return NarrowQueryDetector()

        ambiguous_count = sum(1 for w in words if w in _AMBIGUOUS_WORDS)
        # If query is mostly ambiguous words and not very long
        if ambiguous_count >= 2 and len(words) <= 10:
            confidence = min(1.0, ambiguous_count / len(words) + 0.2)
            return NarrowQueryDetector(
                is_narrow=True,
                narrow_type="ambiguous_intent",
                confidence=round(confidence, 4),
                suggested_broadening=(
                    f"Ambiguous intent: {ambiguous_count} ambiguous "
                    f"words in {len(words)}-word query"
                ),
            )

        return NarrowQueryDetector()

    # ── Step 2: Step-Back (Broadening) ─────────────────────────────

    async def generate_broadened_queries(
        self,
        query: str,
        detection: NarrowQueryDetector,
    ) -> List[str]:
        """
        Generate broader contextual questions based on narrow type.

        Uses template-based broadening (no LLM calls).
        Returns up to max_broadening_levels queries.
        """
        if not detection.is_narrow:
            return []

        narrow_type = detection.narrow_type
        templates = _BROADENING_TEMPLATES.get(narrow_type, [])

        if not templates:
            return []

        broadened: List[str] = []
        entity = self._extract_entity(
            query) if narrow_type == "entity_specific" else None

        for i, template in enumerate(templates):
            if i >= self.config.max_broadening_levels:
                break
            try:
                if entity:
                    broadened_query = template.format(
                        entity=entity, query=query)
                else:
                    broadened_query = template.format(query=query)
                broadened.append(broadened_query)
            except KeyError:
                # Template has {entity} but entity not found — skip
                continue

        return broadened

    def _extract_entity(self, query: str) -> Optional[str]:
        """Extract the entity reference from a query."""
        for pattern in self._entity_patterns:
            match = pattern.search(query)
            if match:
                return match.group(0).strip()
        return None

    # ── Step 3: Broader Analysis ───────────────────────────────────

    async def analyze_broadened_context(
        self,
        query: str,
        broadened_queries: List[str],
    ) -> Tuple[str, float]:
        """
        Heuristic analysis of broadened context quality.

        Returns (analysis_summary, context_score).
        Score range: 0.0 (no improvement) to 1.0 (excellent broadening).
        """
        if not broadened_queries:
            return "No broadening possible", 0.0

        # Score based on multiple heuristics
        scores: List[float] = []

        # 1. Breadth score: broadened queries cover more words than original
        original_words = set(re.findall(r"\b\w+\b", query.lower()))
        all_broadened_words: Set[str] = set()
        for bq in broadened_queries:
            all_broadened_words.update(re.findall(r"\b\w+\b", bq.lower()))

        new_words = all_broadened_words - original_words
        if original_words:
            breadth = min(1.0, len(new_words) / max(len(original_words), 1))
        else:
            breadth = 0.5 if all_broadened_words else 0.0
        scores.append(breadth)

        # 2. Coverage score: how many broadened queries were generated
        coverage = min(1.0, len(broadened_queries) /
                       max(self.config.max_broadening_levels, 1))
        scores.append(coverage)

        # 3. Clarity score: broadened queries are longer and more specific
        avg_broadened_len = sum(len(bq.split())
                                for bq in broadened_queries) / len(broadened_queries)
        original_len = max(1, len(query.split()))
        clarity = min(1.0, avg_broadened_len / original_len)
        scores.append(clarity)

        # 4. Context injection score: broadened queries add contextual framing
        contextual_words = {
            "context", "history", "status", "accomplish", "aspect",
            "specific", "relation", "problem", "feature", "area",
            "alternative", "approach", "information", "earlier",
        }
        context_words_found = sum(
            1 for w in all_broadened_words if w in contextual_words
        )
        context_injection = min(
            1.0, context_words_found / max(len(broadened_queries), 1))
        scores.append(context_injection)

        # Weighted average
        weights = [0.3, 0.2, 0.2, 0.3]
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        context_score = round(weighted_sum, 4)

        # Generate analysis summary
        analysis_parts = [
            f"Original query: {
                len(original_words)} unique words",
            f"Broadened: {
                len(broadened_queries)} questions with {
                len(new_words)} new terms",
            f"Breadth: {
                breadth:.2f}, Coverage: {
                coverage:.2f}, " f"Clarity: {
                clarity:.2f}, Context: {
                context_injection:.2f}",
        ]
        analysis_summary = "; ".join(analysis_parts)

        return analysis_summary, context_score

    # ── Step 4: Refined Response ───────────────────────────────────

    async def refine_response(
        self,
        original_query: str,
        broadened_queries: List[str],
        context_score: float,
    ) -> str:
        """
        Produce a refined response combining original query with
        broader context.

        If enable_context_injection is True, prepends contextual framing.
        """
        if not broadened_queries or context_score < 0.1:
            return original_query

        if not self.config.enable_context_injection:
            return original_query

        # Build contextual framing from the best broadened query
        best_query = broadened_queries[0]  # first is most relevant

        refined = (
            f"[Step-Back Context: {best_query}] "
            f"{original_query}"
        )

        return refined

    # ── Full Pipeline ──────────────────────────────────────────────

    async def process(
        self,
        query: str,
        reasoning_thread: Optional[List[str]] = None,
    ) -> StepBackResult:
        """
        Run the full Step-Back pipeline.

        Args:
            query: The original customer query.
            reasoning_thread: Previous reasoning steps (for loop detection).

        Returns:
            StepBackResult with detection, broadening, analysis, and refinement.
        """
        steps_applied: List[str] = []

        if not query or not query.strip():
            return StepBackResult(
                detection_result=NarrowQueryDetector(
                    is_narrow=True,
                    narrow_type="single_word",
                    confidence=1.0,
                    suggested_broadening="Empty query — no processing needed",
                ),
                steps_applied=["empty_input"],
            )

        try:
            # Step 1: Detection
            detection = await self.detect_narrow_query(query, reasoning_thread)
            steps_applied.append("detection")

            if not detection.is_narrow:
                return StepBackResult(
                    detection_result=detection,
                    steps_applied=steps_applied + ["not_narrow"],
                    context_score=0.0,
                )

            # Step 2: Step-Back (Broadening)
            broadened_queries = await self.generate_broadened_queries(
                query, detection,
            )
            if broadened_queries:
                steps_applied.append("broadening")

            # Step 3: Broader Analysis
            analysis_result, context_score = await self.analyze_broadened_context(
                query, broadened_queries,
            )
            steps_applied.append("analysis")

            # Step 4: Refined Response
            refined_response = await self.refine_response(
                query, broadened_queries, context_score,
            )
            if refined_response != query:
                steps_applied.append("refinement")

            return StepBackResult(
                detection_result=detection,
                broadened_queries=broadened_queries,
                analysis_result=analysis_result,
                refined_response=refined_response,
                steps_applied=steps_applied,
                context_score=context_score,
            )

        except Exception as exc:
            # BC-008: Never crash — return original on error
            logger.warning(
                "step_back_processing_error",
                error=str(exc),
                company_id=self.config.company_id,
            )
            return StepBackResult(
                refined_response=query,
                steps_applied=["error_fallback"],
                context_score=0.0,
            )


# ── StepBackNode (LangGraph node) ───────────────────────────────────


class StepBackNode(BaseTechniqueNode):
    """
    F-142: Step-Back Prompting — Tier 2 conditional.

    Extends BaseTechniqueNode for integration into the PARWA technique
    pipeline. Wraps StepBackProcessor and records results in
    ConversationState.
    """

    def __init__(
        self,
        config: Optional[StepBackConfig] = None,
    ):
        self._config = config or StepBackConfig()
        self._processor = StepBackProcessor(config=self._config)
        # Initialize technique_info from registry
        # type: ignore[assignment]
        self.technique_info = TECHNIQUE_REGISTRY[TechniqueID.STEP_BACK]

    @property
    def technique_id(self) -> TechniqueID:
        return TechniqueID.STEP_BACK

    async def should_activate(self, state: ConversationState) -> bool:
        """
        Activate when:
          - confidence < 0.7, OR
          - reasoning_loop_detected, OR
          - gsd_state == DIAGNOSIS
        """
        return (
            state.signals.confidence_score < 0.7
            or state.signals.reasoning_loop_detected
            or state.gsd_state == GSDState.DIAGNOSIS
        )

    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the 4-step Step-Back pipeline and update state.

        BC-008: Wraps in try/except, returns original state on error.
        """
        try:
            reasoning_thread = state.reasoning_thread if state.reasoning_thread else None

            result = await self._processor.process(
                query=state.query,
                reasoning_thread=reasoning_thread,
            )

            # Record result in state
            self.record_result(
                state,
                result=result.to_dict(),
                tokens_used=self.technique_info.estimated_tokens,
            )

            # Update response with refined query if context injection enabled
            if (
                self._config.enable_context_injection
                and result.refined_response
                and result.refined_response != state.query
            ):
                state.response_parts.append(result.refined_response)

            return state

        except Exception as exc:
            # BC-008: Never crash — return original state on error
            logger.warning(
                "step_back_execute_error",
                error=str(exc),
                company_id=self._config.company_id,
            )
            self.record_skip(state, reason="execution_error")
            return state
