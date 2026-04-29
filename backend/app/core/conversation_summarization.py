"""
PARWA Conversation Summarization Service (F-160)

Supports long conversations (50+ messages) by providing multi-turn
summarization to manage context windows. Three modes:
  - Extractive: pick key sentences from the conversation
  - Abstractive: AI-generated condensed summary
  - Hybrid: both extractive and abstractive combined

GAP Fix — W9-GAP-024 (MEDIUM):
  Conversation state protection via version counters. Every new message
  increments the version. Before summarization the version is captured;
  after summarization it is checked. If the version changed during
  processing (new messages arrived), the summarization is re-run.
  An in-memory lock is held for the duration of summarization to
  serialise concurrent runs on the same conversation.

BC-001: All public methods take `company_id` as the first parameter.
BC-008: Every public method is wrapped in try/except — never crashes.
"""

from __future__ import annotations

import math
import re
import threading
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEFAULT_MAX_CONTEXT_MESSAGES: int = 20
_SUMMARIZATION_THRESHOLD_MESSAGES: int = 15
_VERSION_LOCK_TTL_SECONDS: int = 30

# Keywords that carry conversational weight
_HIGH_VALUE_KEYWORDS: frozenset = frozenset(
    {
        "problem",
        "issue",
        "error",
        "bug",
        "broken",
        "not working",
        "need",
        "help",
        "please",
        "urgent",
        "asap",
        "important",
        "thank",
        "thanks",
        "resolved",
        "fixed",
        "update",
        "refund",
        "cancel",
        "return",
        "exchange",
        "order",
        "delivery",
        "shipping",
        "payment",
        "charge",
        "billing",
        "account",
        "password",
        "login",
        "signup",
        "register",
        "expect",
        "promise",
        "guarantee",
        "deadline",
        "follow-up",
    }
)

# Common filler words to exclude from keyword density scoring
_STOP_WORDS: frozenset = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
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
        "can",
        "shall",
        "to",
        "o",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "they",
        "them",
        "their",
        "and",
        "but",
        "or",
        "so",
        "i",
        "then",
        "not",
        "no",
        "yes",
        "just",
        "also",
        "very",
        "too",
    }
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class SummarizationMode(str, Enum):
    """Strategy used to produce a conversation summary."""

    EXTRACTIVE = "extractive"  # Pick key sentences
    ABSTRACTIVE = "abstractive"  # AI-generated summary
    HYBRID = "hybrid"  # Both


class SummaryStatus(str, Enum):
    """Lifecycle status of a single summary artefact."""

    PENDING = "pending"
    COMPLETED = "completed"
    STALE = "stale"
    FAILED = "failed"


class ConversationState(str, Enum):
    """Current state of a conversation (used by external callers)."""

    ACTIVE = "active"
    SUMMARIZING = "summarizing"
    LOCKED = "locked"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class ConversationMessage:
    """A single message within a conversation."""

    message_id: str
    content: str
    role: str  # "customer" or "agent"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict = field(default_factory=dict)


@dataclass
class ConversationSummary:
    """Produced summary for a conversation."""

    summary_id: str
    conversation_id: str
    company_id: str
    mode: SummarizationMode
    status: SummaryStatus
    extractive_summary: str = ""
    abstractive_summary: str = ""
    hybrid_summary: str = ""
    key_points: List[str] = field(default_factory=list)
    conversation_version: int = 0
    message_count: int = 0
    original_message_count: int = 0
    compression_ratio: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    generation_time_ms: float = 0.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class ConversationContext:
    """Full context object for a conversation."""

    conversation_id: str
    company_id: str
    messages: List[ConversationMessage] = field(default_factory=list)
    summaries: List[ConversationSummary] = field(default_factory=list)
    current_version: int = 0
    is_locked: bool = False
    last_summarized_at: Optional[datetime] = None
    token_count: int = 0
    max_context_messages: int = _DEFAULT_MAX_CONTEXT_MESSAGES


@dataclass
class SummarizationRequest:
    """Parameters controlling a single summarization run."""

    company_id: str
    conversation_id: str
    mode: SummarizationMode = SummarizationMode.HYBRID
    max_messages: int = 0  # 0 = all
    include_key_points: bool = True
    force: bool = False  # Force re-summarization even if recent


@dataclass
class SummarizationResult:
    """Outcome of a summarization attempt."""

    success: bool
    summary: Optional[ConversationSummary] = None
    error: str = ""
    version_mismatch: bool = False
    re_summarized: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _conv_key(company_id: str, conversation_id: str) -> str:
    """Build a canonical dict key for a conversation."""
    return f"{company_id}:{conversation_id}"


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return max(0, len(text) // 4)


def _split_sentences(text: str) -> List[str]:
    """Split *text* into sentences using regex.

    Handles common abbreviations (Mr., Dr., etc.) and trailing whitespace.
    """
    if not text:
        return []
    # Protect known abbreviations from being treated as sentence ends
    protected = text
    for abbr in (
        "Mr.",
        "Mrs.",
        "Ms.",
        "Dr.",
        "e.g.",
        "i.e.",
        "etc.",
        "vs.",
        "Jr.",
        "Sr.",
    ):
        protected = protected.replace(abbr, abbr.replace(".", "DOTPROTECT"))

    raw_parts = re.split(r"(?<=[.!?])\s+", protected)
    # Restore abbreviations
    sentences = []
    for part in raw_parts:
        restored = part.replace("DOTPROTECT", ".")
        stripped = restored.strip()
        if stripped:
            sentences.append(stripped)
    return sentences


# ---------------------------------------------------------------------------
# Sentence scorer for extractive summarization
# ---------------------------------------------------------------------------
def _score_sentence(
    sentence: str,
    idx: int,
    total: int,
    word_freq: Counter,
    total_words: int,
) -> float:
    """Score a single sentence on multiple signals.

    Signals (each normalised to 0-1):
      1. **Position** — first and last sentences score higher.
      2. **Length** — mid-range sentences preferred (5–30 words).
      3. **Keyword density** — overlap with high-value keywords.
      4. **Question presence** — sentences ending with '?'.
      5. **TF-IDF-like score** — word rarity across the document.

    Returns:
        A float score ≥ 0.
    """
    if not sentence:
        return 0.0

    words = re.findall(r"\b\w+\b", sentence.lower())
    word_count = len(words)
    if word_count == 0:
        return 0.0

    # --- 1. Position score ---
    # First 3 sentences and last sentence get a boost
    if idx < 3:
        pos_score = 1.0 - (idx / 3.0) * 0.3
    elif idx >= total - 1:
        pos_score = 0.85
    else:
        # Gradual decay from the front
        pos_score = max(0.3, 1.0 - (idx / total))

    # --- 2. Length score ---
    # Ideal length 5–30 words; penalise very short or very long sentences
    if 5 <= word_count <= 30:
        len_score = 1.0
    elif word_count < 5:
        len_score = word_count / 5.0
    else:
        len_score = max(0.2, 1.0 - ((word_count - 30) / 40.0))

    # --- 3. Keyword density ---
    hits = sum(1 for w in words if w in _HIGH_VALUE_KEYWORDS)
    kw_score = min(1.0, hits / max(1, word_count * 0.3))

    # --- 4. Question bonus ---
    question_score = 1.0 if sentence.strip().endswith("?") else 0.3

    # --- 5. TF-IDF-like rarity score ---
    non_stop = [w for w in words if w not in _STOP_WORDS]
    if non_stop and total_words > 0:
        avg_log_freq = sum(math.log(1 + word_freq.get(w, 0)) for w in non_stop) / len(
            non_stop
        )
        # Lower average frequency → rarer words → higher score
        max_possible = math.log(1 + max(word_freq.values(), default=1))
        rarity_score = 1.0 - (avg_log_freq / max(1.0, max_possible))
    else:
        rarity_score = 0.3

    # Weighted combination
    score = (
        pos_score * 0.25
        + len_score * 0.15
        + kw_score * 0.25
        + question_score * 0.15
        + rarity_score * 0.20
    )
    return score


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------
class ConversationSummarizationService:
    """Multi-turn conversation summarization with version protection.

    Stores conversation state and summaries in-process (dict-backed).
    Thread-safe via per-conversation locks.

    For AI-backed abstractive summarization callers can inject an
    ``abstractive_generator`` callable that receives a list of
    ``ConversationMessage`` and returns a summary string.  When *None*
    (the default) a built-in rule-based condensation is used so that
    tests run without external dependencies.
    """

    def __init__(
        self,
        abstractive_generator: Optional[
            Callable[[List[ConversationMessage]], str]
        ] = None,
    ) -> None:
        self._conversation_store: Dict[str, ConversationContext] = {}
        self._version_counters: Dict[str, int] = {}
        self._summary_cache: Dict[str, List[ConversationSummary]] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._stats: Dict[str, Dict[str, Any]] = {}
        self._abstractive_generator = abstractive_generator

    # -- internal helpers ---------------------------------------------------

    def _get_lock(self, key: str) -> threading.Lock:
        """Return (or create) a per-conversation threading.Lock."""
        with self._global_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]

    def _get_or_create_context(
        self, company_id: str, conversation_id: str
    ) -> ConversationContext:
        key = _conv_key(company_id, conversation_id)
        if key not in self._conversation_store:
            self._conversation_store[key] = ConversationContext(
                conversation_id=conversation_id,
                company_id=company_id,
            )
        return self._conversation_store[key]

    def _init_stats(self, company_id: str) -> Dict[str, Any]:
        return {
            "total_summarizations": 0,
            "successful_summarizations": 0,
            "failed_summarizations": 0,
            "version_mismatches": 0,
            "re_summarizations": 0,
            "total_messages_processed": 0,
            "avg_generation_time_ms": 0.0,
        }

    def _update_stats_avg(
        self, stats: Dict[str, Any], field_name: str, value: float, count: int
    ) -> None:
        """Running average update for *field_name* in *stats*."""
        if count <= 0:
            stats[field_name] = 0.0
        else:
            stats[field_name] = round(
                (stats[field_name] * (count - 1) + value) / count, 2
            )

    # -- public API ---------------------------------------------------------

    def add_message(
        self,
        company_id: str,
        conversation_id: str,
        message: ConversationMessage,
    ) -> int:
        """Add a message and increment the version counter.

        Returns the new version number.
        """
        try:
            ctx = self._get_or_create_context(company_id, conversation_id)
            ctx.messages.append(message)
            ctx.token_count += _estimate_tokens(message.content)

            key = _conv_key(company_id, conversation_id)
            new_version = self._version_counters.get(key, 0) + 1
            self._version_counters[key] = new_version
            ctx.current_version = new_version

            logger.info(
                "message_added",
                extra={
                    "company_id": company_id,
                    "conversation_id": conversation_id,
                    "message_id": message.message_id,
                    "new_version": new_version,
                },
            )
            return new_version
        except Exception as exc:
            logger.error(
                "add_message_failed",
                extra={
                    "company_id": company_id,
                    "conversation_id": conversation_id,
                    "error": str(exc),
                },
            )
            return 0

    def should_summarize(
        self,
        company_id: str,
        conversation_id: str,
        threshold: int = _SUMMARIZATION_THRESHOLD_MESSAGES,
    ) -> bool:
        """Return ``True`` if the conversation has enough new messages
        since the last summarization to warrant re-summarization.
        """
        try:
            key = _conv_key(company_id, conversation_id)
            ctx = self._get_or_create_context(company_id, conversation_id)

            if ctx.last_summarized_at is None:
                return len(ctx.messages) >= threshold

            # Count messages added after last summarization timestamp
            new_count = sum(
                1 for m in ctx.messages if m.timestamp > ctx.last_summarized_at
            )
            return new_count >= threshold
        except Exception as exc:
            logger.error(
                "should_summarize_failed",
                extra={
                    "company_id": company_id,
                    "conversation_id": conversation_id,
                    "error": str(exc),
                },
            )
            return False

    def summarize(
        self,
        company_id: str,
        conversation_id: str,
        request: Optional[SummarizationRequest] = None,
    ) -> SummarizationResult:
        """Run summarization with full version protection (W9-GAP-024).

        Steps:
          1. Capture version before summarization.
          2. Acquire per-conversation lock.
          3. Run summarization.
          4. Check if version changed → re-run if needed.
          5. Store result, release lock.

        Returns a ``SummarizationResult`` with the produced summary or
        error details.
        """
        if request is None:
            request = SummarizationRequest(
                company_id=company_id,
                conversation_id=conversation_id,
            )

        key = _conv_key(company_id, conversation_id)
        lock = self._get_lock(key)
        stats = self._stats.setdefault(company_id, self._init_stats(company_id))

        try:
            # Ensure company_id on request matches
            if request.company_id != company_id:
                return SummarizationResult(
                    success=False,
                    error="company_id mismatch between parameter and request",
                )

            # --- Step 1: capture version before ---
            version_before = self._version_counters.get(key, 0)

            ctx = self._get_or_create_context(company_id, conversation_id)
            messages = list(ctx.messages)

            if request.max_messages > 0:
                messages = messages[-request.max_messages :]

            if not messages:
                return SummarizationResult(
                    success=False,
                    error="No messages to summarize",
                )

            # --- Step 2: acquire lock ---
            acquired = lock.acquire(timeout=_VERSION_LOCK_TTL_SECONDS)
            if not acquired:
                logger.warning(
                    "summarize_lock_timeout",
                    extra={
                        "company_id": company_id,
                        "conversation_id": conversation_id,
                    },
                )
                return SummarizationResult(
                    success=False,
                    error="Could not acquire summarization lock (timeout)",
                )

            try:
                stats["total_summarizations"] += 1
                re_summarized = False
                version_mismatch = False
                result_summary: Optional[ConversationSummary] = None

                for attempt in range(2):  # max 2 attempts (initial + 1 re-run)
                    # Re-check version on each attempt
                    current_version = self._version_counters.get(key, 0)
                    if attempt > 0 and current_version != version_before:
                        version_mismatch = True
                        stats["version_mismatches"] += 1
                        stats["re_summarizations"] += 1
                        re_summarized = True
                        # Refresh messages for re-run
                        messages = list(ctx.messages)
                        if request.max_messages > 0:
                            messages = messages[-request.max_messages :]
                        logger.info(
                            "summarize_version_changed_re_running",
                            extra={
                                "company_id": company_id,
                                "conversation_id": conversation_id,
                                "attempt": attempt + 1,
                            },
                        )

                    # --- Step 3: run summarization ---
                    start_ms = time.monotonic() * 1000
                    result_summary = self._run_summarization(
                        messages=messages,
                        request=request,
                        conversation_version=current_version,
                    )
                    gen_time = time.monotonic() * 1000 - start_ms
                    if result_summary is not None:
                        result_summary.generation_time_ms = round(gen_time, 2)

                    # --- Step 4: check if version changed ---
                    version_after = self._version_counters.get(key, 0)
                    if attempt == 0 and version_after != version_before:
                        # Mark previous summary as stale
                        if result_summary is not None:
                            result_summary.status = SummaryStatus.STALE
                        version_before = version_after  # use new baseline
                        continue  # re-run
                    break

                if (
                    result_summary is not None
                    and result_summary.status == SummaryStatus.STALE
                ):
                    # Second run also went stale — keep last result but mark
                    # failed
                    result_summary.status = SummaryStatus.FAILED
                    stats["failed_summarizations"] += 1
                    stats["total_messages_processed"] += len(messages)
                    self._update_stats_avg(
                        stats,
                        "avg_generation_time_ms",
                        result_summary.generation_time_ms,
                        stats["total_summarizations"],
                    )
                    return SummarizationResult(
                        success=False,
                        summary=result_summary,
                        error="Version changed twice during summarization",
                        version_mismatch=version_mismatch,
                        re_summarized=re_summarized,
                    )

                # --- Step 5: store result ---
                if result_summary is not None:
                    result_summary.status = SummaryStatus.COMPLETED
                    self._summary_cache.setdefault(key, []).append(result_summary)
                    ctx.summaries.append(result_summary)
                    ctx.last_summarized_at = datetime.now(timezone.utc)
                    stats["successful_summarizations"] += 1
                    stats["total_messages_processed"] += len(messages)
                    self._update_stats_avg(
                        stats,
                        "avg_generation_time_ms",
                        result_summary.generation_time_ms,
                        stats["total_summarizations"],
                    )

                    logger.info(
                        "summarize_completed",
                        extra={
                            "company_id": company_id,
                            "conversation_id": conversation_id,
                            "summary_id": result_summary.summary_id,
                            "mode": request.mode.value,
                            "re_summarized": re_summarized,
                        },
                    )

                    return SummarizationResult(
                        success=True,
                        summary=result_summary,
                        version_mismatch=version_mismatch,
                        re_summarized=re_summarized,
                    )

                return SummarizationResult(
                    success=False,
                    error="Summarization returned no result",
                    version_mismatch=version_mismatch,
                    re_summarized=re_summarized,
                )
            finally:
                lock.release()

        except Exception as exc:
            logger.error(
                "summarize_failed",
                extra={
                    "company_id": company_id,
                    "conversation_id": conversation_id,
                    "error": str(exc),
                },
            )
            return SummarizationResult(success=False, error=str(exc))

    # -- internal summarization dispatch ------------------------------------

    def _run_summarization(
        self,
        messages: List[ConversationMessage],
        request: SummarizationRequest,
        conversation_version: int,
    ) -> Optional[ConversationSummary]:
        """Dispatch to the correct summarization mode and build a
        ``ConversationSummary``."""
        mode = request.mode
        original_count = len(messages)
        original_chars = sum(len(m.content) for m in messages)

        extractive = ""
        abstractive = ""
        key_points: List[str] = []

        try:
            if mode in (SummarizationMode.EXTRACTIVE, SummarizationMode.HYBRID):
                extractive, key_points = self._extractive_summarize(messages)

            if mode in (SummarizationMode.ABSTRACTIVE, SummarizationMode.HYBRID):
                abstractive = self._abstractive_summarize(messages)

            # Build hybrid summary text
            hybrid = ""
            if mode == SummarizationMode.HYBRID:
                parts: List[str] = []
                if abstractive:
                    parts.append(f"Summary: {abstractive}")
                if extractive:
                    parts.append(f"Key excerpts: {extractive}")
                if key_points:
                    parts.append("Key points: " + "; ".join(key_points))
                hybrid = " | ".join(parts)

            summary_chars = len(extractive) + len(abstractive) + len(hybrid)
            compression_ratio = (
                round(1.0 - (summary_chars / max(1, original_chars)), 4)
                if original_chars > 0
                else 0.0
            )

            if not request.include_key_points:
                key_points = []

            return ConversationSummary(
                summary_id=str(uuid.uuid4()),
                conversation_id=request.conversation_id,
                company_id=request.company_id,
                mode=mode,
                status=SummaryStatus.PENDING,  # caller upgrades to COMPLETED
                extractive_summary=extractive,
                abstractive_summary=abstractive,
                hybrid_summary=hybrid,
                key_points=key_points,
                conversation_version=conversation_version,
                message_count=len(messages),
                original_message_count=original_count,
                compression_ratio=compression_ratio,
            )
        except Exception as exc:
            logger.error(
                "run_summarization_internal_error",
                extra={"error": str(exc)},
            )
            return None

    # -- extractive summarization -------------------------------------------

    def _extractive_summarize(
        self, messages: List[ConversationMessage]
    ) -> Tuple[str, List[str]]:
        """Extract key sentences from messages.

        Scoring signals:
          - Position (first/last sentences boosted)
          - Length (5–30 words ideal)
          - Keyword density (high-value words)
          - Question presence
          - TF-IDF-like rarity

        Returns:
            ``(summary_text, key_points)``
        """
        # Concatenate all message content with role prefix
        all_sentences: List[Tuple[str, str]] = []  # (sentence, role)
        for msg in messages:
            role_tag = f"[{msg.role}] "
            sentences = _split_sentences(msg.content)
            for sent in sentences:
                all_sentences.append((f"{role_tag}{sent}", msg.role))

        if not all_sentences:
            return "", []

        # Build word frequency across the entire corpus
        all_text = " ".join(s[0] for s in all_sentences)
        all_words = re.findall(r"\b\w+\b", all_text.lower())
        word_freq: Counter = Counter(all_words)
        total_words = len(all_words)

        # Score every sentence
        scored: List[Tuple[float, int, str]] = []
        for idx, (sentence, _role) in enumerate(all_sentences):
            score = _score_sentence(
                sentence, idx, len(all_sentences), word_freq, total_words
            )
            scored.append((score, idx, sentence))

        # Pick top N sentences (cap at ~30 % of total, min 2, max 7)
        n = min(7, max(2, len(all_sentences) // 3))
        top = sorted(scored, key=lambda x: x[0], reverse=True)[:n]

        # Re-order by original position for readability
        top.sort(key=lambda x: x[1])

        extractive_summary = " ".join(s[2] for s in top)

        # Derive key points — highest-scoring unique sentences, deduplicated
        seen = set()
        key_points: List[str] = []
        for _score, _idx, sent in sorted(scored, key=lambda x: x[0], reverse=True):
            # Normalise for dedup
            norm = re.sub(r"\s+", " ", sent.lower().strip())
            if norm not in seen and norm:
                seen.add(norm)
                key_points.append(sent)
            if len(key_points) >= 5:
                break

        return extractive_summary, key_points

    # -- abstractive summarization ------------------------------------------

    def _abstractive_summarize(self, messages: List[ConversationMessage]) -> str:
        """Generate a condensed summary.

        If an ``abstractive_generator`` callable was provided at
        construction time it is called.  Otherwise a rule-based
        condensation is applied (no external AI calls required, making
        tests fast and deterministic).
        """
        if self._abstractive_generator is not None:
            try:
                return self._abstractive_generator(messages)
            except Exception as exc:
                logger.warning(
                    "abstractive_generator_failed_falling_back",
                    extra={"error": str(exc)},
                )
                # Fall through to rule-based

        return self._rule_based_abstractive(messages)

    def _rule_based_abstractive(self, messages: List[ConversationMessage]) -> str:
        """Built-in rule-based condensation.

        Strategy:
          1. Merge consecutive messages from the same role.
          2. Pick the first sentence from each merged block.
          3. Count topic shifts (different subjects across blocks).
          4. Build a flowing narrative: topic overview + per-topic summary.
        """
        if not messages:
            return ""

        # --- 1. Merge consecutive same-role messages ---
        blocks: List[Tuple[str, str]] = []  # (role, merged_content)
        for msg in messages:
            if blocks and blocks[-1][0] == msg.role:
                blocks[-1] = (blocks[-1][0], blocks[-1][1] + " " + msg.content)
            else:
                blocks.append((msg.role, msg.content))

        # --- 2. Extract first sentence per block ---
        block_sentences: List[Tuple[str, str]] = []  # (role, first_sentence)
        for role, content in blocks:
            sentences = _split_sentences(content)
            if sentences:
                # Truncate to ~60 chars max for compactness
                first = sentences[0]
                if len(first) > 60:
                    first = first[:57] + "..."
                block_sentences.append((role, first))

        if not block_sentences:
            return ""

        # --- 3. Build condensed narrative ---
        parts: List[str] = []

        # Opening overview
        customer_msgs = sum(1 for r, _ in block_sentences if r == "customer")
        agent_msgs = sum(1 for r, _ in block_sentences if r == "agent")
        parts.append(
            f"Conversation with {customer_msgs} customer messages and "
            f"{agent_msgs} agent responses."
        )

        # Collect key first-sentences (skip very short ones)
        key_excerpts: List[str] = []
        for role, sent in block_sentences:
            word_count = len(re.findall(r"\b\w+\b", sent))
            if word_count >= 3:
                key_excerpts.append(f"{role}: {sent}")

        if key_excerpts:
            # Show up to 8 key excerpts
            selected = key_excerpts[:8]
            if len(key_excerpts) > 8:
                parts.append(
                    "Key exchanges: "
                    + "; ".join(selected)
                    + f" (and {len(key_excerpts) - 8} more exchanges)"
                )
            else:
                parts.append("Key exchanges: " + "; ".join(selected))

        # Check for high-value keywords for a topic hint
        all_text = " ".join(m.content for m in messages).lower()
        topic_words = [kw for kw in _HIGH_VALUE_KEYWORDS if kw in all_text]
        if topic_words:
            parts.append("Topics discussed: " + ", ".join(sorted(set(topic_words))))

        return " ".join(parts)

    # -- context retrieval --------------------------------------------------

    def get_context(
        self,
        company_id: str,
        conversation_id: str,
    ) -> Optional[ConversationContext]:
        """Return the current ``ConversationContext`` or ``None``."""
        try:
            key = _conv_key(company_id, conversation_id)
            return self._conversation_store.get(key)
        except Exception as exc:
            logger.error(
                "get_context_failed",
                extra={
                    "company_id": company_id,
                    "conversation_id": conversation_id,
                    "error": str(exc),
                },
            )
            return None

    def get_latest_summary(
        self,
        company_id: str,
        conversation_id: str,
    ) -> Optional[ConversationSummary]:
        """Return the most recent summary or ``None``."""
        try:
            key = _conv_key(company_id, conversation_id)
            cached = self._summary_cache.get(key)
            if cached:
                return cached[-1]
            ctx = self._conversation_store.get(key)
            if ctx and ctx.summaries:
                return ctx.summaries[-1]
            return None
        except Exception as exc:
            logger.error(
                "get_latest_summary_failed",
                extra={
                    "company_id": company_id,
                    "conversation_id": conversation_id,
                    "error": str(exc),
                },
            )
            return None

    def get_context_window(
        self,
        company_id: str,
        conversation_id: str,
        max_messages: int = _DEFAULT_MAX_CONTEXT_MESSAGES,
    ) -> Dict:
        """Build the context window for downstream consumers.

        Returns a dict with:
          - ``messages``: the last *max_messages* messages
          - ``summary``: the latest summary (if any)
          - ``total_messages``: total messages in the conversation
          - ``version``: current version counter
          - ``token_count``: estimated token count for the window
        """
        try:
            key = _conv_key(company_id, conversation_id)
            ctx = self._get_or_create_context(company_id, conversation_id)
            msgs = ctx.messages[-max_messages:]

            latest_summary = None
            cached = self._summary_cache.get(key)
            if cached:
                latest_summary = cached[-1]
            elif ctx.summaries:
                latest_summary = ctx.summaries[-1]

            window_tokens = sum(_estimate_tokens(m.content) for m in msgs)
            if latest_summary:
                window_tokens += _estimate_tokens(
                    latest_summary.extractive_summary
                    + latest_summary.abstractive_summary
                    + latest_summary.hybrid_summary
                )

            return {
                "messages": [
                    {
                        "message_id": m.message_id,
                        "content": m.content,
                        "role": m.role,
                        "timestamp": m.timestamp.isoformat(),
                    }
                    for m in msgs
                ],
                "summary": (
                    {
                        "summary_id": latest_summary.summary_id,
                        "mode": latest_summary.mode.value,
                        "extractive_summary": latest_summary.extractive_summary,
                        "abstractive_summary": latest_summary.abstractive_summary,
                        "hybrid_summary": latest_summary.hybrid_summary,
                        "key_points": latest_summary.key_points,
                        "compression_ratio": latest_summary.compression_ratio,
                    }
                    if latest_summary
                    else None
                ),
                "total_messages": len(ctx.messages),
                "version": self._version_counters.get(key, 0),
                "token_count": window_tokens,
            }
        except Exception as exc:
            logger.error(
                "get_context_window_failed",
                extra={
                    "company_id": company_id,
                    "conversation_id": conversation_id,
                    "error": str(exc),
                },
            )
            return {
                "messages": [],
                "summary": None,
                "total_messages": 0,
                "version": 0,
                "token_count": 0,
            }

    def get_conversation_version(
        self,
        company_id: str,
        conversation_id: str,
    ) -> int:
        """Return the current version counter for a conversation."""
        try:
            key = _conv_key(company_id, conversation_id)
            return self._version_counters.get(key, 0)
        except Exception as exc:
            logger.error(
                "get_conversation_version_failed",
                extra={
                    "company_id": company_id,
                    "conversation_id": conversation_id,
                    "error": str(exc),
                },
            )
            return 0

    def clear_conversation(
        self,
        company_id: str,
        conversation_id: str,
    ) -> bool:
        """Remove all stored data for a conversation.

        Returns ``True`` on success, ``False`` on error.
        """
        try:
            key = _conv_key(company_id, conversation_id)
            self._conversation_store.pop(key, None)
            self._version_counters.pop(key, None)
            self._summary_cache.pop(key, None)
            with self._global_lock:
                self._locks.pop(key, None)

            logger.info(
                "conversation_cleared",
                extra={
                    "company_id": company_id,
                    "conversation_id": conversation_id,
                },
            )
            return True
        except Exception as exc:
            logger.error(
                "clear_conversation_failed",
                extra={
                    "company_id": company_id,
                    "conversation_id": conversation_id,
                    "error": str(exc),
                },
            )
            return False

    def get_stats(self, company_id: str) -> Dict:
        """Return summarization statistics for a company."""
        try:
            return dict(self._stats.get(company_id, self._init_stats(company_id)))
        except Exception as exc:
            logger.error(
                "get_stats_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
            return self._init_stats(company_id)

    def reset(self) -> None:
        """Clear all internal state. Intended for use in tests."""
        try:
            self._conversation_store.clear()
            self._version_counters.clear()
            self._summary_cache.clear()
            with self._global_lock:
                self._locks.clear()
            self._stats.clear()
            logger.info("service_reset")
        except Exception as exc:
            logger.error("reset_failed", extra={"error": str(exc)})
