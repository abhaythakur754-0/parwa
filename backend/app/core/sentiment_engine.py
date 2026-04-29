"""
Sentiment Analysis / Empathy Engine (F-063)

Analyzes customer messages to produce:
- Frustration score (0-100): escalation at 60+, VIP routing at 80+
- Tone recommendation: empathetic, urgent, de-escalation, standard
- Emotion classification: angry, frustrated, disappointed, neutral, happy, delighted
- Urgency level: low, medium, high, critical
- Empathy signals: specific phrases that indicate emotional state

Design Principles:
- BC-001: All operations scoped to company_id
- BC-008: Graceful degradation — never crashes on bad input
- Cache pattern: same as signal_extraction.py (Redis with company_id, variant_type, query_hash)
- Conversation trend analysis: improving, stable, worsening

Parent: Week 9 Day 7 (Sunday)
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("sentiment_engine")


# ── Emotion & Urgency Constants ──────────────────────────────────────


class EmotionType(str):
    """Valid emotion types for classification."""

    ANGRY = "angry"
    FRUSTRATED = "frustrated"
    DISAPPOINTED = "disappointed"
    NEUTRAL = "neutral"
    HAPPY = "happy"
    DELIGHTED = "delighted"


class UrgencyLevel(str):
    """Valid urgency levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToneRecommendation(str):
    """Valid tone recommendations."""

    EMPATHETIC = "empathetic"
    URGENT = "urgent"
    DE_ESCALATION = "de-escalation"
    STANDARD = "standard"


class TrendDirection(str):
    """Conversation sentiment trend."""

    IMPROVING = "improving"
    STABLE = "stable"
    WORSENING = "worsening"


# ── Frustration Lexicons ─────────────────────────────────────────────

# Strong frustration/anger words
FRUSTRATION_STRONG = {
    "furious",
    "enraged",
    "livid",
    "outraged",
    "disgusted",
    "infuriated",
    "unacceptable",
    "appalling",
    "atrocious",
    "abysmal",
    "horrendous",
    "intolerable",
    "unbearable",
    "excruciating",
    "catastrophic",
    "devastating",
    "despicable",
    "vile",
    "pathetic",
    "contemptible",
    "repulsive",
}

# Moderate frustration words
FRUSTRATION_MODERATE = {
    "angry",
    "annoyed",
    "annoying",
    "frustrated",
    "frustrating",
    "irritated",
    "irritating",
    "mad",
    "upset",
    "disappointed",
    "disappointing",
    "unhappy",
    "dissatisfied",
    "aggravated",
    "aggravating",
    "bothered",
    "bothering",
    "disturbed",
    "troubled",
    "worried",
    "concerned",
    "terrible",
    "awful",
    "horrible",
    "worst",
    "rude",
    "useless",
    "ridiculous",
    "scam",
    "garbage",
    "trash",
    "waste",
    "broken",
    "unfair",
    "unhelpful",
    "wrong",
    "disgusting",
    "deplorable",
}

# Mild frustration words
FRUSTRATION_MILD = {
    "issue",
    "problem",
    "confused",
    "unclear",
    "uncertain",
    "inconvenient",
    "difficult",
    "complicated",
    "slow",
    "bad",
    "wrong",
    "error",
    "fail",
    "fault",
}

# ── Empathy Signal Patterns ──────────────────────────────────────────

EMPATHY_PATTERNS: Dict[str, Dict[str, Any]] = {
    "apology_expectation": {
        "keywords": [
            "you should be ashamed",
            "how dare you",
            "you owe me",
            "apologize",
            "apology",
            "you need to say sorry",
            "this is your fault",
            "blame",
            "responsible for this",
            "negligence",
            "careless",
        ],
        "weight": 0.8,
    },
    "timeline_pressure": {
        "keywords": [
            "right now",
            "immediately",
            "asap",
            "urgent",
            "emergency",
            "deadline",
            "today",
            "by tomorrow",
            "running out of time",
            "time sensitive",
            "critical deadline",
            "past due",
            "overdue",
            "days ago",
            "weeks ago",
            "still waiting",
        ],
        "weight": 0.7,
    },
    "financial_impact": {
        "keywords": [
            "lost money",
            "losing money",
            "cost me",
            "charged me",
            "overcharged",
            "double charged",
            "stolen",
            "theft",
            "bankrupt",
            "financial",
            "expensive",
            "overpriced",
            "refund",
            "money back",
            "compensation",
            "damages",
        ],
        "weight": 0.9,
    },
    "personal_impact": {
        "keywords": [
            "ruined my",
            "destroyed my",
            "wasted my",
            "lost my",
            "my family",
            "my children",
            "my business",
            "my job",
            "my reputation",
            "health",
            "safety",
            "dangerous",
            "stressed",
            "anxiety",
            "panic",
            "crying",
            "tears",
        ],
        "weight": 1.0,
    },
    "repeated_contacts": {
        # Detected via conversation_history, not keywords
        "keywords": [],
        "weight": 0.6,
    },
}

# ── Tone Recommendation Keywords ─────────────────────────────────────

POSITIVE_WORDS = {
    "awesome",
    "brilliant",
    "excellent",
    "fantastic",
    "good",
    "great",
    "happy",
    "helpful",
    "love",
    "perfect",
    "pleased",
    "quick",
    "satisfied",
    "superb",
    "thank",
    "thanks",
    "wonderful",
    "amazing",
    "impressed",
    "outstanding",
    "phenomenal",
    "remarkable",
    "stellar",
    "magnificent",
    "splendid",
    "terrific",
    "marvelous",
    "exceptional",
    "delightful",
    "grateful",
    "appreciate",
    "efficient",
    "reliable",
    "professional",
    "friendly",
    "polite",
    "responsive",
    "smooth",
    "seamless",
    "easy",
}

# ── Data Classes ─────────────────────────────────────────────────────


@dataclass
class SentimentResult:
    """Output of sentiment analysis (F-063)."""

    frustration_score: float  # 0-100
    emotion: str  # EmotionType value
    urgency_level: str  # UrgencyLevel value
    tone_recommendation: str  # ToneRecommendation value
    empathy_signals: List[str]  # list of detected signal types
    sentiment_score: float  # 0.0-1.0 (matching signal_extraction.py)
    emotion_breakdown: Dict[str, float]  # emotion → score
    processing_time_ms: float
    conversation_trend: str = "stable"  # TrendDirection value
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for caching."""
        return {
            "frustration_score": self.frustration_score,
            "emotion": self.emotion,
            "urgency_level": self.urgency_level,
            "tone_recommendation": self.tone_recommendation,
            "empathy_signals": self.empathy_signals,
            "sentiment_score": round(self.sentiment_score, 4),
            "emotion_breakdown": {
                k: round(v, 4) for k, v in self.emotion_breakdown.items()
            },
            "processing_time_ms": self.processing_time_ms,
            "conversation_trend": self.conversation_trend,
        }


# ── Frustration Detector ─────────────────────────────────────────────


class FrustrationDetector:
    """Detects frustration beyond simple lexicon matching.

    Uses patterns: ALL CAPS, exclamation marks, repeated words,
    question mark density.
    """

    def detect(self, query: str) -> float:
        """Return frustration score from 0 to 100."""
        if not query or not isinstance(query, str):
            return 0.0

        query_stripped = query.strip()
        if not query_stripped:
            return 0.0

        score = 0.0

        # 1. Lexicon-based scoring (0-50 points)
        score += self._lexicon_score(query_stripped)

        # 2. ALL CAPS detection (0-10 points)
        score += self._caps_score(query_stripped)

        # 3. Exclamation mark density (0-15 points)
        score += self._exclamation_score(query_stripped)

        # 4. Repeated words/phrases (0-10 points)
        score += self._repetition_score(query_stripped)

        # 5. Question mark density (0-10 points)
        score += self._question_score(query_stripped)

        # 6. Intensifier presence (0-5 points)
        score += self._intensifier_score(query_stripped)

        return min(100.0, max(0.0, round(score, 2)))

    def _lexicon_score(self, query: str) -> float:
        """Score based on frustration word presence (0-50 pts).

        G9-GAP-03 FIX: Uses word-boundary matching for mild words to prevent
        false positives (e.g., 'issue' in 'tissue', 'bad' in 'badge').
        Strong/moderate words use substring matching to catch variations
        like 'annoying', 'frustrating', 'furious', etc.
        """
        query_lower = query.lower()
        query_words = set(re.findall(r"\b\w+\b", query_lower))

        strong_hits = sum(1 for w in FRUSTRATION_STRONG if w in query_lower)
        moderate_hits = sum(1 for w in FRUSTRATION_MODERATE if w in query_lower)
        # G9-GAP-03: Word-boundary matching for mild frustration words
        mild_hits = sum(1 for w in FRUSTRATION_MILD if w in query_words)

        score = strong_hits * 12 + moderate_hits * 5 + mild_hits * 1.5
        return min(50.0, score)

    def _caps_score(self, query: str) -> float:
        """Detect ALL CAPS words (0-10 pts)."""
        words = query.split()
        if not words:
            return 0.0

        caps_words = [w for w in words if w.isalpha() and w.isupper() and len(w) > 1]
        if not caps_words:
            return 0.0

        caps_ratio = len(caps_words) / len(words)
        if caps_ratio > 0.5:
            return 10.0
        elif caps_ratio > 0.3:
            return 6.0
        elif caps_ratio > 0.1:
            return 3.0
        return 1.0

    def _exclamation_score(self, query: str) -> float:
        """Score exclamation mark density (0-15 pts)."""
        excl_count = query.count("!")
        if excl_count == 0:
            return 0.0

        if excl_count >= 5:
            return 15.0
        elif excl_count >= 3:
            return 10.0
        elif excl_count >= 2:
            return 5.0
        return 2.0

    def _repetition_score(self, query: str) -> float:
        """Detect repeated words (0-10 pts)."""
        words = re.findall(r"\b\w+\b", query.lower())
        if len(words) < 3:
            return 0.0

        from collections import Counter

        word_counts = Counter(words)
        # Any word appearing 3+ times
        repeated = sum(1 for w, c in word_counts.items() if c >= 3)
        if repeated >= 3:
            return 10.0
        elif repeated >= 2:
            return 6.0
        elif repeated >= 1:
            return 3.0
        return 0.0

    def _question_score(self, query: str) -> float:
        """Score question mark density (0-10 pts)."""
        q_count = query.count("?")
        word_count = len(re.findall(r"\b\w+\b", query))
        if word_count == 0:
            return 0.0

        q_density = q_count / max(word_count, 1)
        if q_density > 0.3:
            return 10.0
        elif q_density > 0.15:
            return 6.0
        elif q_density > 0.05:
            return 3.0
        return 0.0

    def _intensifier_score(self, query: str) -> float:
        """Score intensifier presence (0-5 pts)."""
        query_lower = query.lower()
        intensifiers = [
            "very",
            "extremely",
            "really",
            "so",
            "incredibly",
            "absolutely",
            "totally",
            "completely",
            "utterly",
            "never ever",
            "absolutely not",
            "completely unacceptable",
        ]
        hits = sum(1 for i in intensifiers if i in query_lower)
        return min(5.0, hits * 1.5)


# ── Empathy Signal Detector ──────────────────────────────────────────


class EmpathySignalDetector:
    """Detects specific empathy signals in customer messages."""

    def detect(
        self,
        query: str,
        conversation_history: Optional[List[str]] = None,
        customer_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Return list of detected empathy signal types."""
        if not query or not isinstance(query, str):
            return []

        signals: List[str] = []
        query_lower = query.lower()

        for signal_type, config in EMPATHY_PATTERNS.items():
            if signal_type == "repeated_contacts":
                # Detected from conversation history
                if self._detect_repeated_contacts(query, conversation_history):
                    signals.append(signal_type)
                continue

            keywords = config.get("keywords", [])
            for kw in keywords:
                if kw in query_lower:
                    signals.append(signal_type)
                    break

        return signals

    def _detect_repeated_contacts(
        self,
        query: str,
        history: Optional[List[str]] = None,
    ) -> bool:
        """Detect if this is a repeated contact (similar messages in history)."""
        if not history or len(history) < 2:
            return False

        query_lower = query.lower().strip()
        if not query_lower:
            return False

        # Check if the current query is very similar to 2+ messages in history
        from difflib import SequenceMatcher

        similar = 0
        for msg in history[-5:]:
            if not msg or not isinstance(msg, str):
                continue
            past = msg.lower().strip()
            if not past:
                continue
            ratio = SequenceMatcher(None, query_lower, past).ratio()
            if ratio >= 0.8:
                similar += 1

        return similar >= 2


# ── Emotion Classifier ──────────────────────────────────────────────


class EmotionClassifier:
    """Classifies text into one of 6 emotion types."""

    # Emotion keyword sets
    EMOTION_LEXICON: Dict[str, Dict[str, Any]] = {
        "angry": {
            "keywords": [
                "furious",
                "enraged",
                "livid",
                "outraged",
                "disgusted",
                "infuriated",
                "hate",
                "loathe",
                "despise",
                "angry",
                "mad",
                "rage",
                "how dare",
                "unacceptable",
                "atrocious",
                "vile",
                "despicable",
            ],
            "weight": 1.0,
        },
        "frustrated": {
            "keywords": [
                "frustrated",
                "annoyed",
                "irritated",
                "aggravated",
                "bothered",
                "impossible",
                "ridiculous",
                "stupid",
                "useless",
                "waste of time",
                "run around",
                "circular",
                "nowhere",
                "doing nothing",
                "not helping",
                "ignoring me",
            ],
            "weight": 1.0,
        },
        "disappointed": {
            "keywords": [
                "disappointed",
                "let down",
                "underwhelmed",
                "expected more",
                "not what I expected",
                "below standard",
                "subpar",
                "mediocre",
                "unfortunate",
                "sad",
                "unhappy",
                "dissatisfied",
                "poor quality",
                "not good enough",
            ],
            "weight": 1.0,
        },
        "happy": {
            "keywords": [
                "happy",
                "glad",
                "pleased",
                "satisfied",
                "thankful",
                "great",
                "good",
                "nice",
                "wonderful",
                "helpful",
                "appreciate",
                "thanks",
                "thank you",
                "well done",
                "sorted",
                "resolved",
                "working now",
                "fixed",
            ],
            "weight": 1.0,
        },
        "delighted": {
            "keywords": [
                "delighted",
                "amazed",
                "astounded",
                "impressed",
                "outstanding",
                "excellent",
                "brilliant",
                "fantastic",
                "superb",
                "phenomenal",
                "stellar",
                "exceptional",
                "love it",
                "best ever",
                "above and beyond",
                "incredible",
            ],
            "weight": 1.0,
        },
    }

    def classify(
        self,
        query: str,
        frustration_score: float = 0.0,
    ) -> Tuple[str, Dict[str, float]]:
        """Classify emotion and return breakdown scores.

        Returns (primary_emotion, emotion_breakdown_dict).
        """
        if not query or not isinstance(query, str):
            return EmotionType.NEUTRAL, {
                "neutral": 1.0,
                "angry": 0.0,
                "frustrated": 0.0,
                "disappointed": 0.0,
                "happy": 0.0,
                "delighted": 0.0,
            }

        query_lower = query.lower()
        words = set(re.findall(r"\b\w+\b", query_lower))

        # Score each emotion
        scores: Dict[str, float] = {
            "angry": 0.0,
            "frustrated": 0.0,
            "disappointed": 0.0,
            "neutral": 0.1,  # small base for neutral
            "happy": 0.0,
            "delighted": 0.0,
        }

        for emotion, config in self.EMOTION_LEXICON.items():
            keywords = config.get("keywords", [])
            weight = config.get("weight", 1.0)
            hits = sum(1 for kw in keywords if kw in query_lower)
            scores[emotion] = hits * weight

        # Frustration score influences angry/frustrated
        if frustration_score > 70:
            scores["angry"] += (frustration_score - 70) * 0.1
        elif frustration_score > 40:
            scores["frustrated"] += (frustration_score - 40) * 0.05

        # Sentiment-based boost for positive emotions
        neg_count = sum(
            1 for w in words if w in FRUSTRATION_STRONG | FRUSTRATION_MODERATE
        )
        pos_count = sum(1 for w in words if w in POSITIVE_WORDS)
        if pos_count > neg_count and pos_count > 0:
            scores["happy"] += pos_count * 0.5
            if pos_count >= 3:
                scores["delighted"] += (pos_count - 2) * 0.5
        elif neg_count == 0 and pos_count == 0:
            scores["neutral"] += 0.5

        # Normalize scores
        total = sum(scores.values())
        if total > 0:
            scores = {k: round(v / total, 4) for k, v in scores.items()}
        else:
            scores = {k: 0.0 for k in scores}

        primary = max(scores, key=scores.get)

        return primary, scores


# ── Urgency Scorer ──────────────────────────────────────────────────


class UrgencyScorer:
    """Scores urgency level from 0-100, maps to discrete levels."""

    # Urgency keywords with weights
    URGENCY_KEYWORDS: Dict[str, float] = {
        "immediately": 0.9,
        "urgent": 0.8,
        "asap": 0.8,
        "emergency": 0.95,
        "critical": 0.9,
        "right now": 0.85,
        "deadline": 0.7,
        "today": 0.6,
        "by tomorrow": 0.7,
        "hours": 0.5,
        "overdue": 0.7,
        "past due": 0.75,
        "expiring": 0.65,
        "final notice": 0.8,
        "last chance": 0.7,
        "outage": 0.85,
        "down": 0.6,  # system down context
        "broken": 0.5,
        "cannot access": 0.6,
        "locked out": 0.7,
        "data loss": 0.9,
        "security": 0.8,
        "breach": 0.95,
    }

    def score(self, query: str, frustration_score: float = 0.0) -> str:
        """Return urgency level string.

        Maps numeric score to: low (0-30), medium (31-60), high (61-80), critical (81-100).
        """
        if not query or not isinstance(query, str):
            return UrgencyLevel.LOW

        query_lower = query.lower()
        raw_score = 0.0

        # G9-GAP-09 FIX: Word-boundary matching for multi-word keywords,
        # substring matching for single-word context-dependent keywords
        query_words_str = " " + query_lower + " "
        for keyword, weight in self.URGENCY_KEYWORDS.items():
            if " " in keyword:
                # Multi-word keyword: require exact phrase match
                if keyword in query_words_str:
                    raw_score += weight * 40
            else:
                # Single-word keyword: use word-boundary matching
                # to prevent false positives like 'down' in 'download'
                pattern = r"\b" + re.escape(keyword) + r"\b"
                if re.search(pattern, query_lower):
                    raw_score += weight * 40  # scale to 0-100 range

        # Frustration contribution (up to 20 pts)
        raw_score += min(20.0, frustration_score * 0.2)

        # Exclamation marks contribute urgency
        excl = query.count("!")
        raw_score += min(10.0, excl * 2.0)

        # ALL CAPS words boost urgency
        words = query.split()
        if words:
            caps_ratio = sum(
                1 for w in words if w.isalpha() and w.isupper() and len(w) > 1
            ) / len(words)
            raw_score += min(10.0, caps_ratio * 20.0)

        raw_score = min(100.0, max(0.0, raw_score))

        # Map to levels
        if raw_score > 80:
            return UrgencyLevel.CRITICAL
        elif raw_score > 60:
            return UrgencyLevel.HIGH
        elif raw_score > 30:
            return UrgencyLevel.MEDIUM
        return UrgencyLevel.LOW


# ── Tone Advisor ─────────────────────────────────────────────────────


class ToneAdvisor:
    """Recommends response tone based on frustration + emotion."""

    def recommend(
        self,
        frustration_score: float,
        emotion: str,
        urgency_level: str,
    ) -> str:
        """Recommend response tone.

        Rules:
        - De-escalation: frustration >= 90 OR (emotion == angry AND frustration >= 70)
        - Urgent: urgency_level in (high, critical) AND frustration >= 60
        - Empathetic: frustration >= 40 OR emotion in (angry, frustrated, disappointed)
        - Standard: everything else
        """
        if frustration_score >= 90 or (emotion == "angry" and frustration_score >= 70):
            return ToneRecommendation.DE_ESCALATION

        if (
            urgency_level in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL)
            and frustration_score >= 60
        ):
            return ToneRecommendation.URGENT

        if frustration_score >= 40 or emotion in (
            "angry",
            "frustrated",
            "disappointed",
        ):
            return ToneRecommendation.EMPATHETIC

        return ToneRecommendation.STANDARD


# ── Conversation Trend Analyzer ──────────────────────────────────────


class ConversationTrendAnalyzer:
    """Analyzes conversation history for sentiment trajectory."""

    def analyze(
        self,
        conversation_history: Optional[List[str]],
    ) -> str:
        """Determine conversation trend: improving, stable, worsening.

        Analyzes the last few messages for frustration trajectory.
        """
        if not conversation_history or len(conversation_history) < 3:
            return TrendDirection.STABLE

        # Filter out None/empty
        valid_msgs = [
            m for m in conversation_history if m and isinstance(m, str) and m.strip()
        ]
        if len(valid_msgs) < 3:
            return TrendDirection.STABLE

        detector = FrustrationDetector()

        # Get frustration scores for recent messages
        # Use last 5 messages maximum
        recent = valid_msgs[-5:]
        scores = [detector.detect(m) for m in recent]

        if len(scores) < 2:
            return TrendDirection.STABLE

        # Compare first half to second half
        mid = len(scores) // 2
        early_avg = sum(scores[:mid]) / mid
        late_avg = sum(scores[mid:]) / (len(scores) - mid)

        diff = late_avg - early_avg

        if diff < -10:
            return TrendDirection.IMPROVING
        elif diff > 10:
            return TrendDirection.WORSENING
        return TrendDirection.STABLE


# ── Sentiment Analyzer (Main Class) ──────────────────────────────────


class SentimentAnalyzer:
    """Sentiment Analysis / Empathy Engine (F-063).

    Analyzes customer messages to produce frustration scores, emotion
    classification, urgency levels, tone recommendations, and empathy
    signal detection.

    All operations scoped to company_id (BC-001).
    Graceful degradation on errors (BC-008).
    """

    CACHE_TTL_SECONDS = 60

    def __init__(self):
        self._frustration_detector = FrustrationDetector()
        self._empathy_detector = EmpathySignalDetector()
        self._emotion_classifier = EmotionClassifier()
        self._urgency_scorer = UrgencyScorer()
        self._tone_advisor = ToneAdvisor()
        self._trend_analyzer = ConversationTrendAnalyzer()

    async def analyze(
        self,
        query: str,
        company_id: str = "",
        variant_type: str = "parwa",
        conversation_history: Optional[List[str]] = None,
        customer_metadata: Optional[Dict[str, Any]] = None,
    ) -> SentimentResult:
        """Analyze customer message for sentiment signals.

        Args:
            query: Customer message text.
            company_id: Tenant identifier (BC-001).
            variant_type: mini_parwa, parwa, high_parwa.
            conversation_history: Previous messages for trend analysis.
            customer_metadata: Optional customer context (tier, VIP, etc.)

        Returns:
            SentimentResult with all analysis outputs.
        """
        # ── BC-008: Input validation ────────────────────────────
        if not query or not isinstance(query, str):
            logger.info(
                "sentiment_empty_input",
                company_id=company_id,
                reason="empty_or_invalid_query",
            )
            return self._default_result("empty_input")

        cleaned = query.strip()
        if not cleaned:
            return self._default_result("empty_input")

        # ── Cache check (same pattern as signal_extraction.py) ──
        # G9-GAP-02 FIX: Include conversation_history in cache key to
        # prevent stale cached trends for same query with different history
        query_hash = self._compute_query_hash(cleaned)
        history_hash = self._compute_history_hash(conversation_history)
        cache_key = (
            f"sentiment_cache:{company_id}:{variant_type}:{query_hash}:{history_hash}"
        )

        try:
            from app.core.redis import cache_get, cache_set

            cached = await cache_get(company_id, cache_key)
            if cached is not None and isinstance(cached, dict):
                logger.debug("sentiment_cache_hit", key=cache_key)
                result = SentimentResult(
                    frustration_score=cached["frustration_score"],
                    emotion=cached["emotion"],
                    urgency_level=cached["urgency_level"],
                    tone_recommendation=cached["tone_recommendation"],
                    empathy_signals=cached.get("empathy_signals", []),
                    sentiment_score=cached["sentiment_score"],
                    emotion_breakdown=cached.get("emotion_breakdown", {}),
                    processing_time_ms=cached.get("processing_time_ms", 0.0),
                    conversation_trend=cached.get("conversation_trend", "stable"),
                    cached=True,
                )
                return result
        except Exception as exc:
            logger.warning("sentiment_cache_read_error", error=str(exc))

        # ── Full analysis ───────────────────────────────────────
        start_time = time.monotonic()

        # 1. Frustration detection
        frustration_score = self._frustration_detector.detect(cleaned)

        # 2. Emotion classification
        emotion, emotion_breakdown = self._emotion_classifier.classify(
            cleaned,
            frustration_score,
        )

        # 3. Urgency scoring
        urgency_level = self._urgency_scorer.score(cleaned, frustration_score)

        # 4. Empathy signal detection
        empathy_signals = self._empathy_detector.detect(
            cleaned,
            conversation_history,
            customer_metadata,
        )

        # 5. Tone recommendation
        tone_recommendation = self._tone_advisor.recommend(
            frustration_score,
            emotion,
            urgency_level,
        )

        # 6. Sentiment score (0.0-1.0) — inverse of frustration, normalized
        sentiment_score = max(0.0, min(1.0, 1.0 - (frustration_score / 100.0)))

        # 7. Conversation trend
        conversation_trend = self._trend_analyzer.analyze(conversation_history)

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = SentimentResult(
            frustration_score=frustration_score,
            emotion=emotion,
            urgency_level=urgency_level,
            tone_recommendation=tone_recommendation,
            empathy_signals=empathy_signals,
            sentiment_score=round(sentiment_score, 4),
            emotion_breakdown=emotion_breakdown,
            processing_time_ms=elapsed_ms,
            conversation_trend=conversation_trend,
        )

        logger.info(
            "sentiment_analysis_complete",
            company_id=company_id,
            variant_type=variant_type,
            frustration=frustration_score,
            emotion=emotion,
            urgency=urgency_level,
            tone=tone_recommendation,
            empathy_signals=empathy_signals,
            elapsed_ms=elapsed_ms,
        )

        # ── Cache store ─────────────────────────────────────────
        try:
            await cache_set(
                company_id,
                cache_key,
                result.to_dict(),
                ttl_seconds=self.CACHE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning("sentiment_cache_write_error", error=str(exc))

        return result

    def _default_result(self, reason: str) -> SentimentResult:
        """BC-008: Return safe default for empty/invalid input."""
        return SentimentResult(
            frustration_score=0.0,
            emotion=EmotionType.NEUTRAL,
            urgency_level=UrgencyLevel.LOW,
            tone_recommendation=ToneRecommendation.STANDARD,
            empathy_signals=[],
            sentiment_score=0.5,
            emotion_breakdown={
                "neutral": 1.0,
                "angry": 0.0,
                "frustrated": 0.0,
                "disappointed": 0.0,
                "happy": 0.0,
                "delighted": 0.0,
            },
            processing_time_ms=0.0,
            conversation_trend=TrendDirection.STABLE,
        )

    @staticmethod
    def _compute_query_hash(query: str) -> str:
        """Compute deterministic SHA-256 hash for cache key."""
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _compute_history_hash(conversation_history: Optional[List[str]]) -> str:
        """Compute hash from conversation_history for cache key (G9-GAP-02).

        Returns a short hash of the last 3 messages, or 'none' if no history.
        """
        if not conversation_history:
            return "none"
        recent = [m for m in conversation_history[-3:] if m and isinstance(m, str)]
        if not recent:
            return "none"
        combined = "|".join(m.lower().strip() for m in recent)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:8]
