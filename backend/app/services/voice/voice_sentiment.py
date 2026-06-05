"""
Voice Sentiment Analyzer — Real-time & Batch Sentiment Analysis

Analyzes voice call transcriptions for sentiment signals using
keyword/rule-based analysis (no external ML API needed):

1. Batch transcript analysis with sentiment, urgency, key phrases
2. Real-time partial transcript analysis with shift detection
3. Empathy adjustment triggers for the empathy engine

Sentiment rules:
- Negative keywords: frustrated, angry, upset, terrible, horrible,
  unhappy, disappointed, annoyed, furious, disgusted, hate, worst
- Positive keywords: happy, great, thanks, wonderful, excellent,
  amazing, love, perfect, awesome, fantastic, pleased, satisfied
- Neutral keywords: please, help, question, wondering, info,
  need, would, could, can

Urgency rules:
- Critical: immediately, urgent, asap, emergency, right now,
  critical, life-threatening, danger
- High: soon, quickly, important, deadline, running out
- Medium: whenever, at some point, eventually
- Low: no rush, whenever convenient, take your time

Building Codes:
- BC-001: All operations scoped by company_id (multi-tenant isolation)
- BC-008: Never crash — wrap all operations in try/except, return error dicts
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("parwa.voice.voice_sentiment")

# ── Sentiment Keyword Dictionaries ────────────────────────────

NEGATIVE_KEYWORDS: Dict[str, float] = {
    "frustrated": 0.85,
    "angry": 0.95,
    "upset": 0.80,
    "terrible": 0.90,
    "horrible": 0.90,
    "unhappy": 0.75,
    "disappointed": 0.70,
    "annoyed": 0.65,
    "furious": 0.95,
    "disgusted": 0.90,
    "hate": 0.85,
    "worst": 0.85,
    "awful": 0.80,
    "pathetic": 0.80,
    "ridiculous": 0.75,
    "unacceptable": 0.80,
    "complaint": 0.60,
    "problem": 0.50,
    "issue": 0.40,
    "broken": 0.65,
    "not working": 0.60,
    "doesn't work": 0.60,
    "can't use": 0.55,
    "never": 0.50,
    "waste": 0.70,
    "scam": 0.90,
    "refund": 0.50,
    "cancel": 0.55,
    "switching": 0.55,
    "leave": 0.45,
    "lawyer": 0.85,
    "sue": 0.90,
    "supervisor": 0.60,
    "manager": 0.55,
}

POSITIVE_KEYWORDS: Dict[str, float] = {
    "happy": 0.80,
    "great": 0.70,
    "thanks": 0.60,
    "thank you": 0.65,
    "wonderful": 0.80,
    "excellent": 0.85,
    "amazing": 0.80,
    "love": 0.80,
    "perfect": 0.85,
    "awesome": 0.75,
    "fantastic": 0.80,
    "pleased": 0.70,
    "satisfied": 0.70,
    "good": 0.50,
    "nice": 0.55,
    "helpful": 0.65,
    "appreciate": 0.70,
    "resolved": 0.60,
    "working": 0.40,
    "fixed": 0.55,
    "best": 0.70,
    "impressed": 0.75,
}

NEUTRAL_KEYWORDS: Dict[str, float] = {
    "please": 0.30,
    "help": 0.35,
    "question": 0.25,
    "wondering": 0.20,
    "info": 0.15,
    "information": 0.15,
    "need": 0.30,
    "would": 0.10,
    "could": 0.10,
    "can": 0.10,
    "looking for": 0.25,
    "trying to": 0.25,
    "how do": 0.20,
    "what is": 0.15,
}

# ── Urgency Keywords ──────────────────────────────────────────

CRITICAL_URGENCY_KEYWORDS: List[str] = [
    "immediately", "urgent", "asap", "emergency",
    "right now", "critical", "life-threatening", "danger",
    "right away", "can't wait", "desperate",
]

HIGH_URGENCY_KEYWORDS: List[str] = [
    "soon", "quickly", "important", "deadline",
    "running out", "time-sensitive", "pressing",
    "needs attention", "before today", "today",
    "tomorrow morning", "by end of day",
]

MEDIUM_URGENCY_KEYWORDS: List[str] = [
    "at some point", "eventually",
    "when possible", "convenient",
]

LOW_URGENCY_KEYWORDS: List[str] = [
    "take your time", "whenever convenient",
    "not in a hurry", "no hurry",
    "whenever", "no rush",
]

# ── Emotional Indicators ──────────────────────────────────────

EMOTIONAL_INDICATORS: Dict[str, List[str]] = {
    "frustration": [
        "ugh", "argh", "come on", "seriously",
        "again", "still not", "every time",
    ],
    "anger": [
        "ridiculous", "unacceptable", "how dare",
        "fed up", "enough", "done with",
    ],
    "anxiety": [
        "worried", "concerned", "anxious", "nervous",
        "stressed", "afraid", "scared",
    ],
    "gratitude": [
        "thank you", "appreciate", "grateful",
        "so helpful", "means a lot",
    ],
    "confusion": [
        "confused", "don't understand", "unclear",
        "what do you mean", "I don't get it",
    ],
}


class VoiceSentimentAnalyzer:
    """Analyzes voice call transcriptions for sentiment signals.

    Uses keyword/rule-based sentiment analysis. No external ML API
    is required. All methods are scoped by company_id (BC-001)
    and never crash (BC-008).
    """

    # ═══════════════════════════════════════════════════════════
    # Batch Transcript Analysis
    # ═══════════════════════════════════════════════════════════

    def analyze_transcript(
        self,
        transcript: str,
        company_id: str,
    ) -> dict:
        """Analyze a complete transcription for sentiment signals.

        Performs keyword-based sentiment analysis on the full transcript,
        detecting sentiment, urgency, key phrases, and emotional indicators.

        Args:
            transcript: Full transcription text.
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with:
                sentiment (str): positive/negative/neutral/mixed
                confidence (float): 0.0-1.0 confidence score
                urgency_level (str): low/medium/high/critical
                key_phrases (list): Notable phrases detected
                emotional_indicators (list): Detected emotions
                status (str): Always present (BC-008)
        """
        try:
            if not transcript or not transcript.strip():
                return {
                    "status": "success",
                    "sentiment": "neutral",
                    "confidence": 0.0,
                    "urgency_level": "low",
                    "key_phrases": [],
                    "emotional_indicators": [],
                }

            text_lower = transcript.lower()

            # Score sentiment
            negative_score, negative_hits = self._score_keywords(
                text_lower, NEGATIVE_KEYWORDS
            )
            positive_score, positive_hits = self._score_keywords(
                text_lower, POSITIVE_KEYWORDS
            )
            neutral_score, neutral_hits = self._score_keywords(
                text_lower, NEUTRAL_KEYWORDS
            )

            # Determine sentiment
            sentiment, confidence = self._determine_sentiment(
                negative_score, positive_score, neutral_score
            )

            # Detect urgency
            urgency_level = self._detect_urgency(text_lower)

            # Extract key phrases
            key_phrases = self._extract_key_phrases(
                text_lower,
                negative_hits + positive_hits + neutral_hits,
            )

            # Detect emotional indicators
            emotional_indicators = self._detect_emotional_indicators(
                text_lower
            )

            logger.info(
                "transcript_analyzed",
                extra={
                    "company_id": company_id,
                    "sentiment": sentiment,
                    "confidence": confidence,
                    "urgency_level": urgency_level,
                    "key_phrase_count": len(key_phrases),
                    "emotion_count": len(emotional_indicators),
                },
            )

            return {
                "status": "success",
                "sentiment": sentiment,
                "confidence": round(confidence, 3),
                "urgency_level": urgency_level,
                "key_phrases": key_phrases,
                "emotional_indicators": emotional_indicators,
            }

        except Exception as exc:
            logger.error(
                "analyze_transcript_failed company_id=%s error=%s",
                company_id, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Sentiment analysis failed: {str(exc)[:200]}",
                "sentiment": "neutral",
                "confidence": 0.0,
                "urgency_level": "low",
                "key_phrases": [],
                "emotional_indicators": [],
            }

    # ═══════════════════════════════════════════════════════════
    # Real-time Sentiment Analysis
    # ═══════════════════════════════════════════════════════════

    def real_time_sentiment(
        self,
        partial_transcript: str,
        previous_sentiment: dict,
        company_id: str,
    ) -> dict:
        """Analyze a partial transcription in real-time for sentiment shifts.

        Compares the current partial transcript's sentiment with the
        previous sentiment state to detect shifts (e.g., from positive
        to negative) that may require agent intervention.

        Args:
            partial_transcript: Current partial transcription text.
            previous_sentiment: Previous sentiment dict (from last call
                to this method or analyze_transcript).
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with:
                updated_sentiment (dict): Current sentiment analysis.
                shift_detected (bool): Whether a sentiment shift occurred.
                shift_direction (str): Direction of shift if detected
                    (e.g., "positive_to_negative", "neutral_to_critical").
                status (str): Always present (BC-008)
        """
        try:
            # Analyze current partial transcript
            current = self.analyze_transcript(partial_transcript, company_id)

            if current.get("status") == "error":
                return {
                    "status": "error",
                    "error": current.get("error", "Analysis failed"),
                    "updated_sentiment": previous_sentiment or self._default_sentiment(),
                    "shift_detected": False,
                    "shift_direction": "none",
                }

            # Compare with previous sentiment
            prev_sentiment = previous_sentiment.get("sentiment", "neutral") if previous_sentiment else "neutral"
            prev_urgency = previous_sentiment.get("urgency_level", "low") if previous_sentiment else "low"
            prev_confidence = previous_sentiment.get("confidence", 0.0) if previous_sentiment else 0.0

            curr_sentiment = current.get("sentiment", "neutral")
            curr_urgency = current.get("urgency_level", "low")
            curr_confidence = current.get("confidence", 0.0)

            # Detect shift
            shift_detected = False
            shift_direction = "none"

            # Check for sentiment shift
            sentiment_order = {"positive": 3, "neutral": 2, "mixed": 1, "negative": 0}
            prev_rank = sentiment_order.get(prev_sentiment, 2)
            curr_rank = sentiment_order.get(curr_sentiment, 2)

            if prev_rank != curr_rank and curr_confidence >= 0.4:
                shift_detected = True
                shift_direction = f"{prev_sentiment}_to_{curr_sentiment}"

            # Check for urgency escalation
            urgency_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            prev_urgency_rank = urgency_order.get(prev_urgency, 0)
            curr_urgency_rank = urgency_order.get(curr_urgency, 0)

            if curr_urgency_rank > prev_urgency_rank:
                shift_detected = True
                if shift_direction == "none":
                    shift_direction = f"urgency_{prev_urgency}_to_{curr_urgency}"
                else:
                    shift_direction += f"_urgency_{prev_urgency}_to_{curr_urgency}"

            # Significant confidence change
            if abs(curr_confidence - prev_confidence) >= 0.3 and curr_confidence > prev_confidence:
                shift_detected = True
                if shift_direction == "none":
                    shift_direction = "confidence_increase"

            logger.info(
                "real_time_sentiment",
                extra={
                    "company_id": company_id,
                    "shift_detected": shift_detected,
                    "shift_direction": shift_direction,
                    "prev_sentiment": prev_sentiment,
                    "curr_sentiment": curr_sentiment,
                    "curr_urgency": curr_urgency,
                },
            )

            return {
                "status": "success",
                "updated_sentiment": current,
                "shift_detected": shift_detected,
                "shift_direction": shift_direction,
            }

        except Exception as exc:
            logger.error(
                "real_time_sentiment_failed company_id=%s error=%s",
                company_id, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Real-time sentiment failed: {str(exc)[:200]}",
                "updated_sentiment": previous_sentiment or self._default_sentiment(),
                "shift_detected": False,
                "shift_direction": "none",
            }

    # ═══════════════════════════════════════════════════════════
    # Empathy Adjustment
    # ═══════════════════════════════════════════════════════════

    def trigger_empathy_adjustment(
        self,
        sentiment: dict,
        company_id: str,
    ) -> dict:
        """Trigger empathy engine adjustments based on sentiment analysis.

        Based on the sentiment analysis results, suggests response tone
        adjustments, escalation recommendations, and priority changes
        for the empathy engine.

        Args:
            sentiment: Sentiment analysis result dict (from analyze_transcript
                or real_time_sentiment).
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with:
                suggested_response_tone (str): Recommended agent tone.
                escalation_recommended (bool): Whether to escalate.
                priority_adjustment (str): Suggested priority change.
                status (str): Always present (BC-008)
        """
        try:
            # Extract sentiment data with safe defaults
            sentiment_value = sentiment.get("sentiment", "neutral")
            confidence = sentiment.get("confidence", 0.0)
            urgency_level = sentiment.get("urgency_level", "low")
            emotional_indicators = sentiment.get("emotional_indicators", [])
            key_phrases = sentiment.get("key_phrases", [])

            # Determine response tone
            suggested_tone = self._determine_response_tone(
                sentiment_value, urgency_level, emotional_indicators
            )

            # Determine escalation recommendation
            escalation_recommended = self._should_escalate(
                sentiment_value, confidence, urgency_level, emotional_indicators
            )

            # Determine priority adjustment
            priority_adjustment = self._determine_priority(
                sentiment_value, urgency_level, emotional_indicators
            )

            logger.info(
                "empathy_adjustment_triggered",
                extra={
                    "company_id": company_id,
                    "sentiment": sentiment_value,
                    "suggested_tone": suggested_tone,
                    "escalation": escalation_recommended,
                    "priority": priority_adjustment,
                },
            )

            return {
                "status": "success",
                "suggested_response_tone": suggested_tone,
                "escalation_recommended": escalation_recommended,
                "priority_adjustment": priority_adjustment,
            }

        except Exception as exc:
            logger.error(
                "trigger_empathy_adjustment_failed company_id=%s error=%s",
                company_id, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Empathy adjustment failed: {str(exc)[:200]}",
                "suggested_response_tone": "professional",
                "escalation_recommended": False,
                "priority_adjustment": "medium",
            }

    # ═══════════════════════════════════════════════════════════
    # Private Helpers — Sentiment Scoring
    # ═══════════════════════════════════════════════════════════

    def _score_keywords(
        self,
        text: str,
        keyword_dict: Dict[str, float],
    ) -> Tuple[float, List[str]]:
        """Score text against a keyword dictionary.

        Args:
            text: Lowercase text to analyze.
            keyword_dict: Dict of keyword -> weight.

        Returns:
            Tuple of (total_score, list_of_matched_keywords).
        """
        total_score = 0.0
        hits: List[str] = []

        for keyword, weight in keyword_dict.items():
            # Use word boundary search for single words,
            # substring search for phrases
            if " " in keyword:
                pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            else:
                pattern = re.compile(
                    r"\b" + re.escape(keyword) + r"\b",
                    re.IGNORECASE,
                )

            matches = pattern.findall(text)
            if matches:
                count = len(matches)
                # Diminishing returns for repeated keywords
                adjusted_weight = weight * (1 + 0.5 * (count - 1))
                total_score += adjusted_weight
                hits.append(keyword)

        return total_score, hits

    def _determine_sentiment(
        self,
        negative_score: float,
        positive_score: float,
        neutral_score: float,
    ) -> Tuple[str, float]:
        """Determine overall sentiment from keyword scores.

        Args:
            negative_score: Total negative keyword weight.
            positive_score: Total positive keyword weight.
            neutral_score: Total neutral keyword weight.

        Returns:
            Tuple of (sentiment_label, confidence).
        """
        total = negative_score + positive_score + neutral_score

        if total == 0:
            return "neutral", 0.0

        neg_ratio = negative_score / total
        pos_ratio = positive_score / total

        # Determine sentiment with confidence
        if neg_ratio > 0.5 and pos_ratio < 0.2:
            confidence = min(neg_ratio, 0.95)
            return "negative", confidence
        elif pos_ratio > 0.5 and neg_ratio < 0.2:
            confidence = min(pos_ratio, 0.95)
            return "positive", confidence
        elif neg_ratio > 0.3 and pos_ratio > 0.3:
            # Both positive and negative signals — mixed
            confidence = min(abs(neg_ratio - pos_ratio) + 0.3, 0.85)
            return "mixed", confidence
        else:
            # Predominantly neutral or weak signals
            confidence = min(neutral_score / total if total > 0 else 0, 0.7)
            return "neutral", confidence

    def _detect_urgency(self, text: str) -> str:
        """Detect urgency level from text.

        Args:
            text: Lowercase text to analyze.

        Returns:
            Urgency level string: low/medium/high/critical.
        """
        # Check critical first (highest priority)
        for keyword in CRITICAL_URGENCY_KEYWORDS:
            if keyword in text:
                return "critical"

        # Check high
        for keyword in HIGH_URGENCY_KEYWORDS:
            if keyword in text:
                return "high"

        # Check medium
        for keyword in MEDIUM_URGENCY_KEYWORDS:
            if keyword in text:
                return "medium"

        # Check low (explicit low-urgency signals)
        for keyword in LOW_URGENCY_KEYWORDS:
            if keyword in text:
                return "low"

        # Default urgency
        return "low"

    def _extract_key_phrases(
        self,
        text: str,
        matched_keywords: List[str],
    ) -> List[str]:
        """Extract notable key phrases from text.

        Returns matched keywords that are significant enough to
        report as key phrases.

        Args:
            text: Lowercase text.
            matched_keywords: List of keywords that matched.

        Returns:
            List of key phrase strings (deduplicated).
        """
        seen = set()
        key_phrases: List[str] = []

        for keyword in matched_keywords:
            if keyword not in seen:
                seen.add(keyword)
                key_phrases.append(keyword)

        # Limit to top 10 key phrases
        return key_phrases[:10]

    def _detect_emotional_indicators(
        self,
        text: str,
    ) -> List[str]:
        """Detect emotional indicators in text.

        Args:
            text: Lowercase text to analyze.

        Returns:
            List of detected emotion labels.
        """
        detected: List[str] = []

        for emotion, indicators in EMOTIONAL_INDICATORS.items():
            for indicator in indicators:
                if indicator in text:
                    if emotion not in detected:
                        detected.append(emotion)
                    break

        return detected

    # ═══════════════════════════════════════════════════════════
    # Private Helpers — Empathy Adjustments
    # ═══════════════════════════════════════════════════════════

    def _determine_response_tone(
        self,
        sentiment: str,
        urgency: str,
        emotional_indicators: List[str],
    ) -> str:
        """Determine the recommended response tone.

        Args:
            sentiment: Sentiment label.
            urgency: Urgency level.
            emotional_indicators: List of detected emotions.

        Returns:
            Recommended tone string.
        """
        # Critical/angry situations
        if urgency == "critical" or "anger" in emotional_indicators:
            return "calm_reassuring"

        # Negative sentiment
        if sentiment == "negative":
            if "frustration" in emotional_indicators:
                return "patient_empathetic"
            if "anxiety" in emotional_indicators:
                return "reassuring_supportive"
            return "empathetic_apologetic"

        # Mixed sentiment
        if sentiment == "mixed":
            if "confusion" in emotional_indicators:
                return "clear_guiding"
            return "balanced_professional"

        # High urgency with neutral/positive sentiment
        if urgency == "high":
            return "efficient_focused"

        # Positive sentiment
        if sentiment == "positive":
            return "warm_friendly"

        # Default neutral
        return "professional_helpful"

    def _should_escalate(
        self,
        sentiment: str,
        confidence: float,
        urgency: str,
        emotional_indicators: List[str],
    ) -> bool:
        """Determine if escalation is recommended.

        Args:
            sentiment: Sentiment label.
            confidence: Confidence score.
            urgency: Urgency level.
            emotional_indicators: List of detected emotions.

        Returns:
            True if escalation is recommended.
        """
        # Always escalate critical urgency with high confidence
        if urgency == "critical" and confidence >= 0.5:
            return True

        # Escalate high urgency with negative sentiment
        if urgency == "high" and sentiment == "negative" and confidence >= 0.5:
            return True

        # Escalate strong anger signals
        if "anger" in emotional_indicators and confidence >= 0.6:
            return True

        # Escalate legal threats
        if "lawyer" in str(emotional_indicators) or "sue" in str(emotional_indicators):
            return True

        return False

    def _determine_priority(
        self,
        sentiment: str,
        urgency: str,
        emotional_indicators: List[str],
    ) -> str:
        """Determine the recommended ticket priority.

        Args:
            sentiment: Sentiment label.
            urgency: Urgency level.
            emotional_indicators: List of detected emotions.

        Returns:
            Priority string: low/medium/high/urgent.
        """
        # Critical urgency = urgent priority
        if urgency == "critical":
            return "urgent"

        # High urgency with negative sentiment = high priority
        if urgency == "high":
            if sentiment == "negative":
                return "high"
            return "high"

        # Negative sentiment with strong emotions = high priority
        if sentiment == "negative" and (
            "anger" in emotional_indicators
            or "frustration" in emotional_indicators
        ):
            return "high"

        # Negative sentiment = medium-high priority
        if sentiment == "negative":
            return "medium"

        # Mixed sentiment with anxiety = medium priority
        if sentiment == "mixed" and "anxiety" in emotional_indicators:
            return "medium"

        # Everything else = low/medium
        if urgency == "medium":
            return "medium"

        return "low"

    def _default_sentiment(self) -> dict:
        """Return a default neutral sentiment result.

        Returns:
            Default sentiment dict.
        """
        return {
            "status": "success",
            "sentiment": "neutral",
            "confidence": 0.0,
            "urgency_level": "low",
            "key_phrases": [],
            "emotional_indicators": [],
        }
