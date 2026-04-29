"""
F-149: Thread of Thought (ThoT) — Tier 2 Conditional AI Reasoning Technique

Maintains reasoning coherence across multi-turn conversations by extracting
the reasoning thread, checking continuity, and enhancing context when the
conversation drifts or loops.

Activates when conversation has been going on for 6+ messages (turn_count > 5).

Pipeline:
  1. Thread Extraction — Parse reasoning thread, identify topic/intent, detect shifts
  2. Continuity Check — Verify coherence, detect contradictions, score 0.0-1.0
  3. Context Enhancement — Summarize key points, detect loops, generate prefix

Performance target: ~150 tokens, sub-500ms processing.
Deterministic/heuristic-based (NO LLM calls).

Building Codes: BC-001 (company isolation), BC-008 (never crash),
               BC-012 (graceful degradation)
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from app.core.technique_router import (
    TechniqueID,
    TECHNIQUE_REGISTRY,
)
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
)
from app.logger import get_logger

logger = get_logger("thread_of_thought")


# ── Topic Shift Enum ─────────────────────────────────────────────────


class TopicShift(str, Enum):
    """Classification of topic continuity between turns."""
    NONE = "none"           # No shift — continuing same topic
    PARTIAL = "partial"     # Partial shift — related but different aspect
    COMPLETE = "complete"   # Complete shift — entirely new topic


# ── Stop Words (for content extraction) ──────────────────────────────


_STOP_WORDS: FrozenSet[str] = frozenset({
    "i", "me", "my", "we", "you", "your", "it", "its",
    "is", "am", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "and", "but", "or", "nor", "not", "so",
    "if", "then", "than", "too", "very", "just", "about", "also",
    "that", "this", "these", "those", "what", "how", "when", "where",
    "why", "who", "which", "up", "out", "a", "an", "the",
})

# Negation words useful for contradiction detection
_NEGATION_WORDS: FrozenSet[str] = frozenset({
    "not", "no", "never", "neither", "nor", "none", "nothing",
    "nowhere", "nobody", "cannot", "can't", "don't", "doesn't",
    "didn't", "won't", "wouldn't", "shouldn't", "couldn't",
    "isn't", "aren't", "wasn't", "weren't", "hasn't", "haven't",
})

# Contradiction indicator pairs (word → its antonym cluster)
_CONTRADICTION_PAIRS: List[Tuple[Set[str], Set[str]]] = [
    ({"yes", "correct", "right", "true", "confirmed"}, {"no", "incorrect", "wrong", "false", "denied"}),
    ({"working", "active", "functional", "operational"}, {"broken", "inactive", "defective", "down", "offline"}),
    ({"refund", "refunded", "reimbursed"}, {"charge", "charged", "billed", "invoiced"}),
    ({"increase", "higher", "more", "greater"}, {"decrease", "lower", "less", "smaller"}),
    ({"approved", "accepted", "confirmed"}, {"rejected", "denied", "declined", "cancelled"}),
    ({"success", "successful", "completed", "resolved"}, {"fail", "failed", "error", "unresolved"}),
]

# Topic domain keywords for shift detection
_TOPIC_DOMAINS: Dict[str, FrozenSet[str]] = {
    "billing": frozenset({
        "bill", "billing", "invoice", "charge", "payment", "fee", "cost",
        "price", "refund", "credit", "debit", "amount", "subscription",
        "prorated", "proration", "overdue", "balance", "transaction",
    }),
    "technical": frozenset({
        "bug", "error", "crash", "broken", "not work", "fix", "issue",
        "slow", "fail", "login", "password", "install", "setup", "config",
        "connect", "sync", "integration", "api", "webhook", "endpoint",
        "feature", "update", "deploy", "server", "database",
    }),
    "account": frozenset({
        "account", "profile", "email", "username", "settings", "notification",
        "pref", "subscription", "plan", "tier", "upgrade", "downgrade",
        "cancel", "reactivate", "verify", "verification",
    }),
    "order": frozenset({
        "order", "shipment", "shipping", "delivery", "track", "tracking",
        "package", "item", "product", "return", "exchange", "address",
    }),
    "general": frozenset({
        "help", "support", "contact", "speak", "agent", "representative",
        "question", "information", "detail", "explain",
    }),
}


# ── Data Structures ──────────────────────────────────────────────────


@dataclass(frozen=True)
class ThoTConfig:
    """
    Immutable configuration for Thread of Thought (BC-001).

    Attributes:
        company_id: Tenant identifier for company isolation.
        min_turns: Minimum turn count to activate (default 5).
        continuity_threshold: Score below which context enhancement triggers.
        max_thread_length: Maximum reasoning thread entries to process.
    """

    company_id: str = ""
    min_turns: int = 5
    continuity_threshold: float = 0.6
    max_thread_length: int = 50


@dataclass
class ThreadAnalysis:
    """
    Analysis of the reasoning thread continuity.

    Attributes:
        turn_count: Number of turns analyzed.
        topic_continuity: Continuity score 0.0-1.0.
        contradictions: List of detected contradiction descriptions.
        repeated_info: List of repeated information descriptions.
        loop_detected: Whether a reasoning loop was detected.
        summary: Summary of key points from the thread.
    """

    turn_count: int = 0
    topic_continuity: float = 0.0
    contradictions: List[str] = field(default_factory=list)
    repeated_info: List[str] = field(default_factory=list)
    loop_detected: bool = False
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_count": self.turn_count,
            "topic_continuity": round(self.topic_continuity, 4),
            "contradictions": self.contradictions,
            "repeated_info": self.repeated_info,
            "loop_detected": self.loop_detected,
            "summary": self.summary,
        }


@dataclass
class ThoTResult:
    """
    Output of the Thread of Thought pipeline.

    Attributes:
        thread_analysis: The analysis of the reasoning thread.
        context_prefix: Generated context-aware response prefix.
        enhanced_response: Full enhanced response (prefix + original query).
        steps_applied: Names of pipeline steps executed.
        continuity_score: Final continuity score (0.0-1.0).
    """

    thread_analysis: ThreadAnalysis = field(default_factory=ThreadAnalysis)
    context_prefix: str = ""
    enhanced_response: str = ""
    steps_applied: List[str] = field(default_factory=list)
    continuity_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_analysis": self.thread_analysis.to_dict(),
            "context_prefix": self.context_prefix,
            "enhanced_response": self.enhanced_response,
            "steps_applied": self.steps_applied,
            "continuity_score": round(self.continuity_score, 4),
        }


# ── ThoT Processor ───────────────────────────────────────────────────


class ThoTProcessor:
    """
    Thread of Thought processor (F-149).

    Deterministic, heuristic-based (no LLM calls).
    Maintains reasoning coherence across multi-turn conversations.

    Pipeline:
      1. Thread Extraction — Parse reasoning thread, identify topics
      2. Continuity Check — Score coherence, detect contradictions and loops
      3. Context Enhancement — Summarize, detect repetition, generate prefix
    """

    def __init__(self, config: Optional[ThoTConfig] = None):
        self.config = config or ThoTConfig()

    # ── Step 1: Thread Extraction ──────────────────────────────────

    async def extract_thread(
        self,
        reasoning_thread: List[str],
        current_query: str,
    ) -> Tuple[List[str], str, TopicShift]:
        """
        Extract and analyze the reasoning thread.

        Args:
            reasoning_thread: List of previous reasoning step strings.
            current_query: The current customer query.

        Returns:
            Tuple of (truncated_thread, current_topic, topic_shift).
        """
        # Identify current topic regardless of thread state
        current_topic = self._identify_topic(
            [current_query] if current_query else [])

        if not reasoning_thread:
            return [], current_topic, TopicShift.NONE

        # Truncate to max length (most recent entries)
        thread = reasoning_thread[-self.config.max_thread_length:]

        # Extract previous topic from the last entries
        prev_topic = self._identify_topic(thread)

        # Detect topic shift
        shift = self._detect_topic_shift(prev_topic, current_topic, thread)

        return thread, current_topic, shift

    def _identify_topic(self, entries: List[str]) -> str:
        """
        Identify the dominant topic domain from a list of text entries.

        Returns the topic domain name with the highest keyword density,
        or "unknown" if no domain matches.
        """
        if not entries:
            return "unknown"

        combined = " ".join(entries).lower()
        words = set(re.findall(r"\b\w+\b", combined)) - _STOP_WORDS

        if not words:
            return "unknown"

        best_domain = "unknown"
        best_score = 0.0

        for domain, keywords in _TOPIC_DOMAINS.items():
            hits = sum(1 for kw in keywords if kw in combined)
            if hits == 0:
                continue
            density = hits / max(len(words), 1)
            if density > best_score:
                best_score = density
                best_domain = domain

        return best_domain

    def _detect_topic_shift(
        self,
        prev_topic: str,
        current_topic: str,
        thread: List[str],
    ) -> TopicShift:
        """
        Detect the type of topic shift between previous and current topic.

        Uses the last few thread entries to compare against the current query.
        """
        if not prev_topic or prev_topic == "unknown":
            return TopicShift.NONE
        if not current_topic or current_topic == "unknown":
            return TopicShift.PARTIAL

        if prev_topic == current_topic:
            return TopicShift.NONE

        # Check if topics share any keywords (partial overlap → partial shift)
        prev_keywords = _TOPIC_DOMAINS.get(prev_topic, frozenset())
        curr_keywords = _TOPIC_DOMAINS.get(current_topic, frozenset())
        overlap = prev_keywords & curr_keywords

        if overlap:
            return TopicShift.PARTIAL

        return TopicShift.COMPLETE

    # ── Step 2: Continuity Check ───────────────────────────────────

    async def check_continuity(
        self,
        thread: List[str],
        current_query: str,
        topic_shift: TopicShift,
    ) -> ThreadAnalysis:
        """
        Check reasoning coherence across the thread.

        Evaluates:
          - Topic continuity score (0.0-1.0)
          - Contradictions with earlier reasoning
          - Repeated information
          - Reasoning loops

        Args:
            thread: Previous reasoning thread entries.
            current_query: Current customer query.
            topic_shift: Detected topic shift type.

        Returns:
            ThreadAnalysis with all findings.
        """
        turn_count = len(thread)

        if not thread:
            return ThreadAnalysis(
                turn_count=0,
                topic_continuity=1.0,
                summary="",
            )

        # 1. Score topic continuity
        topic_score = self._score_topic_continuity(topic_shift)

        # 2. Detect contradictions
        contradictions = self._detect_contradictions(thread)

        # 3. Detect repeated information
        repeated_info = self._detect_repeated_info(thread)

        # 4. Detect reasoning loops
        loop_detected = self._detect_loop(thread)

        # 5. Generate summary
        summary = self._summarize_thread(thread)

        # Calculate overall continuity score
        contradiction_penalty = min(0.3, len(contradictions) * 0.1)
        repetition_penalty = min(0.2, len(repeated_info) * 0.05)
        loop_penalty = 0.3 if loop_detected else 0.0

        continuity = max(0.0, min(1.0, topic_score -
                                  contradiction_penalty -
                                  repetition_penalty -
                                  loop_penalty), )

        return ThreadAnalysis(
            turn_count=turn_count,
            topic_continuity=continuity,
            contradictions=contradictions,
            repeated_info=repeated_info,
            loop_detected=loop_detected,
            summary=summary,
        )

    def _score_topic_continuity(self, topic_shift: TopicShift) -> float:
        """Map topic shift to a continuity score."""
        scores = {
            TopicShift.NONE: 1.0,
            TopicShift.PARTIAL: 0.65,
            TopicShift.COMPLETE: 0.3,
        }
        return scores.get(topic_shift, 0.5)

    def _detect_contradictions(self, thread: List[str]) -> List[str]:
        """
        Detect contradictions between reasoning thread entries.

        Compares consecutive entries for contradictory keyword clusters.
        Returns list of contradiction descriptions.
        """
        if len(thread) < 2:
            return []

        contradictions: List[str] = []
        entries_lower = [entry.lower() for entry in thread]

        for i in range(len(entries_lower) - 1):
            current_words = set(
                re.findall(
                    r"\b\w+\b",
                    entries_lower[i])) - _STOP_WORDS
            next_words = set(re.findall(
                r"\b\w+\b", entries_lower[i + 1])) - _STOP_WORDS

            for cluster_a, cluster_b in _CONTRADICTION_PAIRS:
                a_hits = current_words & cluster_a
                b_hits = next_words & cluster_b

                if a_hits and b_hits:
                    word_a = list(a_hits)[0]
                    word_b = list(b_hits)[0]
                    contradictions.append(
                        f"Turn {i + 1}->{i + 2}: '{word_a}' contradicts '{word_b}'"
                    )

                # Also check reverse direction
                a_hits_rev = current_words & cluster_b
                b_hits_rev = next_words & cluster_a

                if a_hits_rev and b_hits_rev:
                    word_a = list(a_hits_rev)[0]
                    word_b = list(b_hits_rev)[0]
                    # Avoid duplicate if already found in forward direction
                    desc = f"Turn {i +
                                   1}->{i +
                                        2}: '{word_a}' contradicts '{word_b}'"
                    if desc not in contradictions:
                        contradictions.append(desc)

        return contradictions[:10]  # Cap at 10 contradictions

    def _detect_repeated_info(self, thread: List[str]) -> List[str]:
        """
        Detect repeated information in the reasoning thread.

        Compares each entry against previous entries using word overlap.
        Returns list of descriptions for entries with high similarity.
        """
        if len(thread) < 2:
            return []

        repeated: List[str] = []

        for i, entry in enumerate(thread):
            if i == 0:
                continue

            entry_words = set(
                re.findall(
                    r"\b\w+\b",
                    entry.lower())) - _STOP_WORDS
            if not entry_words:
                continue

            for j in range(i):
                prev_words = set(
                    re.findall(
                        r"\b\w+\b",
                        thread[j].lower())) - _STOP_WORDS
                if not prev_words:
                    continue

                intersection = entry_words & prev_words
                union = entry_words | prev_words
                if not union:
                    continue

                jaccard = len(intersection) / len(union)
                if jaccard >= 0.6:
                    repeated.append(
                        f"Turn {i + 1} repeats turn {j + 1} "
                        f"(similarity: {jaccard:.2f})"
                    )

        return repeated[:10]  # Cap at 10 repeated entries

    def _detect_loop(self, thread: List[str]) -> bool:
        """
        Detect a reasoning loop in the thread.

        A loop is detected when the same content words appear across
        3+ consecutive entries with high similarity.
        """
        if len(thread) < 3:
            return False

        # Get content words for each entry
        entry_words: List[Set[str]] = []
        for entry in thread:
            words = set(re.findall(r"\b\w+\b", entry.lower())) - _STOP_WORDS
            entry_words.append(words)

        # Check last 5 entries for a loop pattern (3+ with similar words)
        check_window = min(5, len(entry_words))
        recent = entry_words[-check_window:]

        for i in range(len(recent) - 2):
            group = recent[i:i + 3]
            # All three entries must have some content words
            if any(not g for g in group):
                continue

            # Check pairwise similarity
            similarities = []
            for a_idx in range(len(group)):
                for b_idx in range(a_idx + 1, len(group)):
                    a, b = group[a_idx], group[b_idx]
                    if not a or not b:
                        similarities.append(0.0)
                        continue
                    intersection = a & b
                    union = a | b
                    sim = len(intersection) / len(union) if union else 0.0
                    similarities.append(sim)

            # If all pairs have similarity >= 0.6, it's a loop
            if all(s >= 0.6 for s in similarities) and len(similarities) >= 3:
                return True

        return False

    def _summarize_thread(self, thread: List[str]) -> str:
        """
        Summarize key points from the reasoning thread.

        Extracts the most significant content words and constructs
        a brief summary of the thread's focus areas.
        """
        if not thread:
            return ""

        # Get all content words with frequency
        all_text = " ".join(thread).lower()
        words = re.findall(r"\b\w{3,}\b", all_text)
        content_words = [w for w in words if w not in _STOP_WORDS]

        if not content_words:
            return ""

        word_counts = Counter(content_words)
        # Get top keywords (excluding very common words)
        top_keywords = [
            word for word, count in word_counts.most_common(8)
            if count >= 2
        ]

        if not top_keywords:
            # Fall back to most frequent content words
            top_keywords = [word for word, _ in word_counts.most_common(5)]

        # Identify dominant topic
        topic = self._identify_topic(thread)

        summary_parts = [f"Topic: {topic}"]
        if top_keywords:
            summary_parts.append(f"Key points: {', '.join(top_keywords)}")
        summary_parts.append(f"Thread depth: {len(thread)} entries")

        return "; ".join(summary_parts)

    # ── Step 3: Context Enhancement ────────────────────────────────

    async def enhance_context(
        self,
        analysis: ThreadAnalysis,
        thread: List[str],
        current_query: str,
        topic_shift: TopicShift,
    ) -> Tuple[str, str]:
        """
        Enhance the context if continuity is low.

        Generates a context-aware prefix and builds the enhanced response.

        Args:
            analysis: The thread analysis result.
            thread: The reasoning thread.
            current_query: The current query.
            topic_shift: The detected topic shift.

        Returns:
            Tuple of (context_prefix, enhanced_response).
        """
        if analysis.topic_continuity >= self.config.continuity_threshold:
            return "", current_query

        prefix_parts: List[str] = []

        # Include summary if available
        if analysis.summary:
            prefix_parts.append(f"[Context: {analysis.summary}]")

        # Flag contradictions
        if analysis.contradictions:
            contradiction_count = len(analysis.contradictions)
            prefix_parts.append(
                f"[Note: {contradiction_count} contradiction(s) detected in reasoning history]")

        # Flag loops
        if analysis.loop_detected:
            prefix_parts.append(
                "[Warning: Potential reasoning loop detected — shifting approach]"
            )

        # Flag repeated info
        if analysis.repeated_info:
            repeat_count = len(analysis.repeated_info)
            prefix_parts.append(
                f"[Note: {repeat_count} repeated information pattern(s) detected]")

        # Handle topic shift
        if topic_shift == TopicShift.COMPLETE:
            prefix_parts.append(
                "[Topic shift detected: New topic — previous context may not apply]"
            )
        elif topic_shift == TopicShift.PARTIAL:
            prefix_parts.append(
                "[Partial topic shift: Transitioning to related aspect]"
            )

        context_prefix = " ".join(prefix_parts)
        enhanced_response = f"{context_prefix} {current_query}".strip(
        ) if context_prefix else current_query

        return context_prefix, enhanced_response

    # ── Full Pipeline ──────────────────────────────────────────────

    async def process(
        self,
        reasoning_thread: List[str],
        current_query: str,
    ) -> ThoTResult:
        """
        Run the full 3-step ThoT pipeline.

        Args:
            reasoning_thread: Previous reasoning steps from ConversationState.
            current_query: The current customer query.

        Returns:
            ThoTResult with analysis, context prefix, and enhanced response.
        """
        steps_applied: List[str] = []

        if not reasoning_thread and not current_query:
            return ThoTResult(
                steps_applied=["empty_input"],
                continuity_score=1.0,
            )

        try:
            # Step 1: Thread Extraction
            thread, current_topic, topic_shift = await self.extract_thread(
                reasoning_thread, current_query,
            )
            if thread or current_query:
                steps_applied.append("thread_extraction")

            # Step 2: Continuity Check
            analysis = await self.check_continuity(
                thread, current_query, topic_shift,
            )
            if thread:
                steps_applied.append("continuity_check")

            # Step 3: Context Enhancement
            context_prefix, enhanced_response = await self.enhance_context(
                analysis, thread, current_query, topic_shift,
            )
            if context_prefix:
                steps_applied.append("context_enhancement")

            return ThoTResult(
                thread_analysis=analysis,
                context_prefix=context_prefix,
                enhanced_response=enhanced_response,
                steps_applied=steps_applied,
                continuity_score=analysis.topic_continuity,
            )

        except Exception as exc:
            # BC-008: Never crash — return graceful fallback
            logger.warning(
                "thot_processing_error",
                error=str(exc),
                company_id=self.config.company_id,
            )
            return ThoTResult(
                enhanced_response=current_query,
                steps_applied=["error_fallback"],
                continuity_score=0.0,
            )


# ── ThreadOfThoughtNode (LangGraph compatible) ──────────────────────


class ThreadOfThoughtNode(BaseTechniqueNode):
    """
    F-149: Thread of Thought — Tier 2 Conditional.

    Extends BaseTechniqueNode for integration into the PARWA technique
    pipeline (F-060). Wraps ThoTProcessor and records results in
    ConversationState.

    Activation trigger: state.signals.turn_count > 5
    """

    def __init__(
        self,
        config: Optional[ThoTConfig] = None,
    ):
        self._config = config or ThoTConfig()
        self._processor = ThoTProcessor(config=self._config)
        # Initialize technique_info from registry
        # type: ignore[assignment]
        self.technique_info = TECHNIQUE_REGISTRY[TechniqueID.THREAD_OF_THOUGHT]

    @property
    def technique_id(self) -> TechniqueID:
        """Return the TechniqueID for this node."""
        return TechniqueID.THREAD_OF_THOUGHT

    async def should_activate(self, state: ConversationState) -> bool:
        """
        Check if ThoT should activate.

        Triggers when turn_count > 5 (conversation has been going on
        for 6+ messages).
        """
        return state.signals.turn_count > self._config.min_turns

    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the 3-step ThoT pipeline and update state.

        Pipeline:
          1. Thread Extraction
          2. Continuity Check
          3. Context Enhancement

        Updates ConversationState with:
          - technique_results: recorded ThoT output
          - reasoning_thread: appends current query
          - response_parts: adds enhanced response if context was enhanced

        BC-008: Wraps in try/except, returns original state on error.
        """
        try:
            reasoning_thread = state.reasoning_thread or []

            result = await self._processor.process(
                reasoning_thread=reasoning_thread,
                current_query=state.query,
            )

            # Record result in state
            self.record_result(
                state,
                result=result.to_dict(),
                tokens_used=self.technique_info.estimated_tokens,
            )

            # Append current query to reasoning thread for future turns
            if state.query:
                state.reasoning_thread.append(state.query)

            # If context was enhanced, add to response parts
            if result.context_prefix:
                state.response_parts.append(result.enhanced_response)

            # Update signal: flag reasoning loop if detected
            if result.thread_analysis.loop_detected:
                state.signals.reasoning_loop_detected = True

            return state

        except Exception as exc:
            # BC-008: Never crash — return original state on error
            logger.warning(
                "thot_execute_error",
                error=str(exc),
                company_id=self._config.company_id,
            )
            self.record_skip(state, reason="execution_error")
            return state
