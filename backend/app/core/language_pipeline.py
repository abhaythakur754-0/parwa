"""
Language Detection/Translation Pipeline (SG-29)

8-step pipeline that handles multilingual customer queries:
1. Detection    — Detect input language (character-set + lexicon based)
2. Confidence   — Score detection confidence (0.0–1.0)
3. Tenant Language — Check tenant's configured language preference
4. Translate    — Translate to English (simulated mock)
5. AI Process   — Mark that AI processing happens in this step (pass-through)
6. Translate Back — Translate response back to original language (simulated)
7. Quality Check — Validate translation quality
8. Fallback     — If translation fails, return original text with warning

BC-001: All cache keys scoped to company_id.
BC-008: Graceful degradation — never crash, always return usable result.

Parent: Week 9 Day 7
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("language_pipeline")


# ── Supported Languages ────────────────────────────────────────────────


class Language(str, Enum):
    """Supported languages for detection and translation."""

    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    PORTUGUESE = "pt"
    HINDI = "hi"
    CHINESE = "zh"
    JAPANESE = "ja"
    ARABIC = "ar"
    KOREAN = "ko"
    UNKNOWN = "unknown"


class StepStatus(str, Enum):
    """Status of a pipeline step."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


# ── Character-range definitions per language ───────────────────────────

# Unicode ranges for CJK, Arabic, etc.
_CJK_RANGES = [
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0x3400, 0x4DBF),  # CJK Extension A
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
]

_HIRAGANA_KATAKANA_RANGES = [
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
]

_HANGUL_RANGES = [
    (0xAC00, 0xD7AF),  # Hangul Syllables
    (0x1100, 0x11FF),  # Hangul Jamo
]

_ARABIC_RANGES = [
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
]

_DEVANAGARI_RANGES = [
    (0x0900, 0x097F),  # Devanagari
]

_LATIN_EXTENDED = [
    (0x00C0, 0x00FF),  # Latin-1 Supplement (accents)
    (0x0100, 0x017F),  # Latin Extended-A
    (0x0180, 0x024F),  # Latin Extended-B
]


def _char_in_ranges(char: str, ranges: List[Tuple[int, int]]) -> bool:
    """Check if a character's code point falls within any of the given ranges."""
    cp = ord(char)
    return any(start <= cp <= end for start, end in ranges)


# ── Common word patterns for disambiguation ────────────────────────────

_LANGUAGE_LEXICONS: Dict[str, List[str]] = {
    Language.SPANISH: [
        "el",
        "la",
        "los",
        "las",
        "de",
        "del",
        "en",
        "que",
        "por",
        "para",
        "con",
        "una",
        "uno",
        "es",
        "fue",
        "pero",
        "como",
        "más",
        "este",
        "esta",
        "hola",
        "gracias",
        "por favor",
        "también",
        "puedo",
        "por qué",
        "cuando",
        "donde",
        "bien",
        "muy",
        "todo",
        "tiene",
        "hay",
        "ser",
    ],
    Language.FRENCH: [
        "le",
        "la",
        "les",
        "de",
        "des",
        "du",
        "en",
        "que",
        "est",
        "pour",
        "avec",
        "une",
        "un",
        "il",
        "elle",
        "nous",
        "vous",
        "mais",
        "comme",
        "bonjour",
        "merci",
        "s'il vous plaît",
        "aussi",
        "je peux",
        "pourquoi",
        "quand",
        "où",
        "bien",
        "très",
        "tout",
        "a",
        "est",
        "sont",
    ],
    Language.GERMAN: [
        "der",
        "die",
        "das",
        "den",
        "dem",
        "des",
        "ein",
        "eine",
        "und",
        "ist",
        "nicht",
        "mit",
        "von",
        "au",
        "für",
        "an",
        "aber",
        "auch",
        "hallo",
        "danke",
        "bitte",
        "kann",
        "ich",
        "wie",
        "was",
        "wann",
        "wo",
        "gut",
        "sehr",
        "alle",
        "hat",
        "haben",
        "werden",
    ],
    Language.PORTUGUESE: [
        "o",
        "a",
        "os",
        "as",
        "de",
        "do",
        "da",
        "dos",
        "das",
        "em",
        "que",
        "para",
        "com",
        "uma",
        "um",
        "não",
        "sim",
        "olá",
        "obrigado",
        "por favor",
        "também",
        "posso",
        "por que",
        "quando",
        "onde",
        "bem",
        "muito",
        "todo",
        "tem",
        "há",
        "ser",
        "foi",
        "mas",
        "como",
    ],
    Language.HINDI: [
        "है",
        "हैं",
        "को",
        "का",
        "की",
        "में",
        "से",
        "ने",
        "पर",
        "के",
        "लिए",
        "यह",
        "वह",
        "और",
        "नहीं",
        "हाँ",
        "नमस्ते",
        "धन्यवाद",
        "कृपया",
        "कैसे",
        "क्या",
        "कब",
        "कहाँ",
        "बहुत",
        "सब",
        "अच्छा",
        "हो",
    ],
    Language.JAPANESE: [
        "です",
        "ます",
        "は",
        "が",
        "の",
        "に",
        "を",
        "で",
        "と",
        "も",
        "こんにちは",
        "ありがとうございます",
        "お願いします",
        "できます",
        "なぜ",
        "いつ",
        "どこ",
        "とても",
        "いい",
        "ですか",
        "してください",
    ],
    Language.KOREAN: [
        "은",
        "는",
        "이",
        "가",
        "을",
        "를",
        "에",
        "에서",
        "으로",
        "와",
        "과",
        "안녕하세요",
        "감사합니다",
        "제발",
        "할",
        "수",
        "있습니다",
        "왜",
        "언제",
        "어디",
        "매우",
        "잘",
        "좋은",
        "하지만",
    ],
    Language.ARABIC: [
        "في",
        "من",
        "على",
        "إلى",
        "عن",
        "مع",
        "هذا",
        "هذه",
        "التي",
        "الذي",
        "مرحبا",
        "شكرا",
        "من فضلك",
        "يمكن",
        "كيف",
        "متى",
        "أين",
        "لماذا",
        "جدا",
        "كل",
        "ليس",
        "ولكن",
        "أو",
        "أن",
    ],
}


# ── Data Classes ──────────────────────────────────────────────────────


@dataclass
class PipelineStepResult:
    """Result of a single pipeline step."""

    step_name: str
    status: StepStatus
    duration_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Result of the full language pipeline."""

    original_text: str
    detected_language: str
    detection_confidence: float
    translated_text: str
    tenant_language: Optional[str]
    translation_performed: bool
    quality_score: float
    quality_issues: List[str]
    processing_time_ms: float
    pipeline_steps: List[PipelineStepResult]
    fallback_used: bool = False
    fallback_warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "original_text": self.original_text,
            "detected_language": self.detected_language,
            "detection_confidence": round(self.detection_confidence, 4),
            "translated_text": self.translated_text,
            "tenant_language": self.tenant_language,
            "translation_performed": self.translation_performed,
            "quality_score": round(self.quality_score, 4),
            "quality_issues": self.quality_issues,
            "processing_time_ms": round(self.processing_time_ms, 2),
            "pipeline_steps": [
                {
                    "step_name": s.step_name,
                    "status": s.status.value,
                    "duration_ms": round(s.duration_ms, 2),
                    "metadata": s.metadata,
                }
                for s in self.pipeline_steps
            ],
            "fallback_used": self.fallback_used,
            "fallback_warning": self.fallback_warning,
        }


# ── Language Detector ──────────────────────────────────────────────────


class LanguageDetector:
    """Detects language from character sets and common word patterns.

    Supports: en, es, fr, de, pt, hi, zh, ja, ar, ko
    Uses a combination of Unicode range analysis and lexicon matching.
    """

    def detect(self, text: str) -> Tuple[str, float]:
        """Detect the language of the given text.

        Args:
            text: Input text to analyze.

        Returns:
            Tuple of (language_code, confidence_score).
            confidence_score is 0.0–1.0.
        """
        if not text or not text.strip():
            return Language.UNKNOWN, 0.0

        text = text.strip()

        # Count characters by script category
        script_counts: Dict[str, int] = {
            "cjk": 0,
            "hiragana_katakana": 0,
            "hangul": 0,
            "arabic": 0,
            "devanagari": 0,
            "latin": 0,
            "other": 0,
        }

        total_chars = 0
        for char in text:
            if char.isspace() or not char.isprintable():
                continue
            total_chars += 1
            cp = ord(char)

            matched = False
            if _char_in_ranges(char, _CJK_RANGES):
                script_counts["cjk"] += 1
                matched = True
            if _char_in_ranges(char, _HIRAGANA_KATAKANA_RANGES):
                script_counts["hiragana_katakana"] += 1
                matched = True
            if _char_in_ranges(char, _HANGUL_RANGES):
                script_counts["hangul"] += 1
                matched = True
            if _char_in_ranges(char, _ARABIC_RANGES):
                script_counts["arabic"] += 1
                matched = True
            if _char_in_ranges(char, _DEVANAGARI_RANGES):
                script_counts["devanagari"] += 1
                matched = True
            if char.isascii() and char.isalpha():
                script_counts["latin"] += 1
                matched = True
            if not matched:
                script_counts["other"] += 1

        if total_chars == 0:
            return Language.UNKNOWN, 0.0

        # ── Script-based detection ──
        # Japanese: has hiragana/katakana (even with CJK)
        hk_ratio = script_counts["hiragana_katakana"] / total_chars
        if hk_ratio > 0.05:
            return Language.JAPANESE, min(1.0, 0.5 + hk_ratio * 2)

        # Chinese: CJK without hiragana/katakana
        cjk_ratio = script_counts["cjk"] / total_chars
        if cjk_ratio > 0.3:
            return Language.CHINESE, min(1.0, 0.4 + cjk_ratio)

        # Korean
        hangul_ratio = script_counts["hangul"] / total_chars
        if hangul_ratio > 0.1:
            return Language.KOREAN, min(1.0, 0.5 + hangul_ratio * 2)

        # Arabic
        arabic_ratio = script_counts["arabic"] / total_chars
        if arabic_ratio > 0.2:
            return Language.ARABIC, min(1.0, 0.4 + arabic_ratio * 2)

        # Hindi/Devanagari
        devanagari_ratio = script_counts["devanagari"] / total_chars
        if devanagari_ratio > 0.1:
            return Language.HINDI, min(1.0, 0.5 + devanagari_ratio * 2)

        # ── Lexicon-based detection for Latin-script languages ──
        if script_counts["latin"] > 0:
            words = re.findall(r"\b[\w']+\b", text.lower())
            if not words:
                return Language.UNKNOWN, 0.0

            best_lang = Language.ENGLISH
            best_score = 0.0

            for lang_code, lexicon in _LANGUAGE_LEXICONS.items():
                if lang_code in (
                    Language.HINDI,
                    Language.JAPANESE,
                    Language.KOREAN,
                    Language.ARABIC,
                    Language.CHINESE,
                ):
                    continue  # Skip non-Latin-script lexicons here
                matches = sum(1 for word in words if word in lexicon)
                score = matches / len(words)
                if score > best_score:
                    best_score = score
                    best_lang = lang_code

            # English is default for Latin text; boost confidence if clearly
            # non-English
            if best_lang == Language.ENGLISH and best_score < 0.1:
                return Language.ENGLISH, 0.4  # Low confidence English

            confidence = min(1.0, 0.3 + best_score * 1.5)
            return best_lang, confidence

        return Language.UNKNOWN, 0.1


# ── Translation Simulator ─────────────────────────────────────────────


class TranslationSimulator:
    """Mock translation that simulates delay and returns predictable output.

    In production, this would call Google Translate API or similar.
    """

    # Simulated translation patterns for common phrases
    _TRANSLATION_MAP: Dict[str, Dict[str, str]] = {
        Language.SPANISH: {
            "hola": "hello",
            "gracias": "thank you",
            "por favor": "please",
            "ayuda": "help",
            "problema": "problem",
            "reembolso": "refund",
            "quiero un reembolso": "I want a refund",
            "necesito ayuda": "I need help",
            "mi pedido": "my order",
        },
        Language.FRENCH: {
            "bonjour": "hello",
            "merci": "thank you",
            "s'il vous plaît": "please",
            "aide": "help",
            "problème": "problem",
            "remboursement": "refund",
            "je veux un remboursement": "I want a refund",
            "j'ai besoin d'aide": "I need help",
            "ma commande": "my order",
        },
        Language.GERMAN: {
            "hallo": "hello",
            "danke": "thank you",
            "bitte": "please",
            "hilfe": "help",
            "problem": "problem",
            "rückerstattung": "refund",
            "ich möchte eine rückerstattung": "I want a refund",
            "ich brauche hilfe": "I need help",
            "meine bestellung": "my order",
        },
        Language.PORTUGUESE: {
            "olá": "hello",
            "obrigado": "thank you",
            "por favor": "please",
            "ajuda": "help",
            "problema": "problem",
            "reembolso": "refund",
            "quero um reembolso": "I want a refund",
            "preciso de ajuda": "I need help",
            "meu pedido": "my order",
        },
    }

    # Character-based languages get a generic simulated translation
    _SIMULATED_PREFIX: Dict[str, str] = {
        Language.HINDI: "[Translated from Hindi] ",
        Language.CHINESE: "[Translated from Chinese] ",
        Language.JAPANESE: "[Translated from Japanese] ",
        Language.ARABIC: "[Translated from Arabic] ",
        Language.KOREAN: "[Translated from Korean] ",
    }

    def translate(
        self, text: str, source_lang: str, target_lang: str = "en"
    ) -> Tuple[str, bool]:
        """Translate text from source_lang to target_lang (simulated).

        Args:
            text: Text to translate.
            source_lang: Source language code.
            target_lang: Target language code (default: "en").

        Returns:
            Tuple of (translated_text, success_flag).
        """
        if not text or not text.strip():
            return "", True

        if source_lang == target_lang:
            return text, True

        # Simulate a small processing delay (0.5ms)
        # In tests this is near-instant

        # For supported Latin-script languages, try phrase matching
        text_lower = text.lower()
        lang_map = self._TRANSLATION_MAP.get(source_lang, {})

        if lang_map:
            # Try direct match
            if text_lower in lang_map:
                return lang_map[text_lower], True

            # Try word-by-word translation for known words
            translated_parts = []
            any_matched = False
            words = text.split()
            for word in words:
                word_lower = word.lower()
                if word_lower in lang_map:
                    translated_parts.append(lang_map[word_lower])
                    any_matched = True
                else:
                    translated_parts.append(word)
            if any_matched:
                return " ".join(translated_parts), True

        # For character-based languages or unrecognized text,
        # use the simulated prefix
        prefix = self._SIMULATED_PREFIX.get(source_lang, "")
        if prefix:
            return f"{prefix}{text}", True

        # Fallback: return original with notation
        return f"[Translation simulated] {text}", True

    def translate_back(
        self, text: str, original_lang: str, translated_lang: str = "en"
    ) -> Tuple[str, bool]:
        """Translate response back to the original language (simulated).

        Args:
            text: English text to translate back.
            original_lang: Original language to translate to.
            translated_lang: Current language of the text (default: "en").

        Returns:
            Tuple of (translated_text, success_flag).
        """
        if not text or not text.strip():
            return "", True

        if translated_lang == original_lang:
            return text, True

        # Reverse translation simulation
        reverse_map: Dict[str, Dict[str, str]] = {}
        for lang, fwd_map in self._TRANSLATION_MAP.items():
            reverse_map[lang] = {v: k for k, v in fwd_map.items()}

        lang_reverse = reverse_map.get(original_lang, {})

        if lang_reverse:
            translated_parts = []
            any_matched = False
            words = text.split()
            for word in words:
                word_lower = word.lower()
                if word_lower in lang_reverse:
                    translated_parts.append(lang_reverse[word_lower])
                    any_matched = True
                else:
                    translated_parts.append(word)
            if any_matched:
                return " ".join(translated_parts), True

        # For character-based languages, use simulated suffix
        suffix_map = {
            Language.HINDI: " [हिंदी में अनुवादित]",
            Language.CHINESE: " [中文翻译]",
            Language.JAPANESE: " [日本語訳]",
            Language.ARABIC: " [مترجم]",
            Language.KOREAN: " [한국어 번역]",
        }
        suffix = suffix_map.get(original_lang, " [translated]")
        return f"{text}{suffix}", True


# ── Translation Quality Checker ────────────────────────────────────────


class TranslationQualityChecker:
    """Check for common translation issues.

    Detects:
    - Untranslated segments (foreign words remaining in output)
    - Mixed scripts (e.g., Latin + CJK in same sentence)
    - Garbled text (repeated characters, question marks, mojibake)
    """

    def check(
        self, translated_text: str, source_lang: str, target_lang: str
    ) -> Tuple[float, List[str]]:
        """Check translation quality.

        Args:
            translated_text: The translated text to check.
            source_lang: Original language code.
            target_lang: Target language code.

        Returns:
            Tuple of (quality_score 0.0–1.0, list of issue descriptions).
        """
        if not translated_text or not translated_text.strip():
            return 0.0, ["empty_translation"]

        issues: List[str] = []
        score = 1.0

        # Check for untranslated segments
        untranslated = self._detect_untranslated_segments(
            translated_text, source_lang, target_lang
        )
        if untranslated:
            issues.append(f"untranslated_segments: {untranslated}")
            score -= 0.2 * min(len(untranslated), 3)

        # Check for mixed scripts
        mixed = self._detect_mixed_scripts(translated_text, target_lang)
        if mixed:
            issues.append(f"mixed_scripts_detected: {mixed}")
            score -= 0.15

        # Check for garbled text
        garbled = self._detect_garbled_text(translated_text)
        if garbled:
            issues.append(f"garbled_text_detected: {garbled}")
            score -= 0.3

        # Check for placeholder text (indicating translation failure)
        placeholder = self._detect_placeholders(translated_text)
        if placeholder:
            issues.append(f"placeholder_detected: {placeholder}")
            score -= 0.2

        # Check for excessive length difference (could indicate issues)
        length_issue = self._detect_length_anomaly(translated_text)
        if length_issue:
            issues.append(length_issue)
            score -= 0.1

        score = max(0.0, min(1.0, score))
        return score, issues

    def _detect_untranslated_segments(
        self, text: str, source_lang: str, target_lang: str
    ) -> List[str]:
        """Detect words that appear to be from the source language."""
        if source_lang == target_lang:
            return []

        lexicon = _LANGUAGE_LEXICONS.get(source_lang, [])
        if not lexicon:
            return []

        words = re.findall(r"\b[\w']+\b", text.lower())
        untranslated = [w for w in words if w in lexicon]
        return untranslated[:5]  # Cap at 5 for reporting

    def _detect_mixed_scripts(self, text: str, target_lang: str) -> str:
        """Detect if the text contains characters from unexpected scripts."""
        has_latin = any(c.isascii() and c.isalpha() for c in text)
        has_cjk = any(_char_in_ranges(c, _CJK_RANGES) for c in text)
        has_hk = any(_char_in_ranges(c, _HIRAGANA_KATAKANA_RANGES) for c in text)
        has_hangul = any(_char_in_ranges(c, _HANGUL_RANGES) for c in text)
        has_arabic = any(_char_in_ranges(c, _ARABIC_RANGES) for c in text)
        has_devanagari = any(_char_in_ranges(c, _DEVANAGARI_RANGES) for c in text)

        scripts_present = []
        if has_cjk:
            scripts_present.append("CJK")
        if has_hk:
            scripts_present.append("hiragana/katakana")
        if has_hangul:
            scripts_present.append("hangul")
        if has_arabic:
            scripts_present.append("arabic")
        if has_devanagari:
            scripts_present.append("devanagari")
        if has_latin:
            scripts_present.append("latin")

        if len(scripts_present) > 1:
            return ", ".join(scripts_present)
        return ""

    def _detect_garbled_text(self, text: str) -> str:
        """Detect garbled text patterns."""
        issues = []

        # Repeated characters (e.g., "aaaaaaa", "?????")
        if re.search(r"(.)\1{8,}", text):
            issues.append("repeated_characters")

        # Lots of question marks (mojibake indicator)
        q_count = text.count("?")
        if q_count > len(text) * 0.15 and q_count > 3:
            issues.append("excessive_question_marks")

        # Replacement characters (U+FFFD)
        if "\ufffd" in text:
            issues.append("replacement_characters")

        # Common mojibake patterns
        mojibake_patterns = [
            r"Ã[^\s]{1,5}",  # UTF-8 decoded as Latin-1
            r"Â[^\s]{1,3}",
            r"\x00",  # null bytes
        ]
        for pattern in mojibake_patterns:
            if re.search(pattern, text):
                issues.append("mojibake_pattern")
                break

        return "; ".join(issues)

    def _detect_placeholders(self, text: str) -> str:
        """Detect placeholder text that indicates translation failure."""
        placeholders = [
            r"\[translation [^\]]*failed[^\]]*\]",
            r"\[not translated\]",
            r"\[untranslated\]",
            r"TODO:",
            r"<translate>",
            r"\{\{[^\}]*\}\}",  # template variables that shouldn't be there
        ]
        for pattern in placeholders:
            if re.search(pattern, text, re.IGNORECASE):
                return "translation_placeholder_found"
        return ""

    def _detect_length_anomaly(self, text: str) -> str:
        """Detect if translated text seems unusually long or short."""
        # This is a heuristic — in production would compare to source
        # For now just flag extremely short translations of longer text
        words = text.split()
        if len(words) == 1 and len(words[0]) > 50:
            return "suspicious_single_word"
        return ""


# ── Language Pipeline ──────────────────────────────────────────────────


class LanguagePipeline:
    """8-step pipeline for handling multilingual customer queries.

    Steps:
        1. Detection    — Detect input language
        2. Confidence   — Score detection confidence
        3. Tenant Language — Check tenant's configured language preference
        4. Translate    — Translate to English (simulated)
        5. AI Process   — Mark that AI processing happens in this step
        6. Translate Back — Translate response back to original language
        7. Quality Check — Validate translation quality
        8. Fallback     — Return original text with warning if translation fails

    BC-001: Cache keys scoped to company_id.
    BC-008: Graceful degradation — never crash.
    """

    CACHE_TTL_SECONDS = 120

    def __init__(self):
        self._detector = LanguageDetector()
        self._translator = TranslationSimulator()
        self._quality_checker = TranslationQualityChecker()

    async def process(
        self,
        query: str,
        company_id: str,
        tenant_language: Optional[str] = None,
    ) -> PipelineResult:
        """Process a multilingual query through all 8 pipeline steps.

        Args:
            query: The customer's query text.
            company_id: Tenant company ID (BC-001).
            tenant_language: Optional tenant-configured language preference.

        Returns:
            PipelineResult with all step results and final output.
        """
        start_time = time.monotonic()
        steps: List[PipelineStepResult] = []

        # BC-008: Handle empty/None input gracefully
        if not query or not str(query).strip():
            return PipelineResult(
                original_text=str(query) if query is not None else "",
                detected_language=Language.UNKNOWN,
                detection_confidence=0.0,
                translated_text=str(query) if query is not None else "",
                tenant_language=tenant_language,
                translation_performed=False,
                quality_score=0.0,
                quality_issues=["empty_input"],
                processing_time_ms=round((time.monotonic() - start_time) * 1000, 2),
                pipeline_steps=steps,
                fallback_used=True,
                fallback_warning="Empty query — no processing performed",
            )

        original_text = str(query)
        detected_language = Language.UNKNOWN
        confidence = 0.0
        translated_text = original_text
        translation_performed = False
        quality_score = 1.0
        quality_issues: List[str] = []
        fallback_used = False
        fallback_warning: Optional[str] = None

        # ── Step 1: Detection ───────────────────────────────────────
        step_start = time.monotonic()
        try:
            detected_language, confidence = self._detector.detect(original_text)
            steps.append(
                PipelineStepResult(
                    step_name="detection",
                    status=StepStatus.SUCCESS,
                    duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                    metadata={"language": detected_language, "confidence": confidence},
                )
            )
        except Exception as exc:
            logger.warning("pipeline_detection_failed", error=str(exc))
            steps.append(
                PipelineStepResult(
                    step_name="detection",
                    status=StepStatus.FAILED,
                    duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                    metadata={"error": str(exc)},
                )
            )
            detected_language = Language.UNKNOWN
            confidence = 0.0

        # ── Step 2: Confidence ──────────────────────────────────────
        step_start = time.monotonic()
        try:
            is_confident = confidence >= 0.5
            status = StepStatus.SUCCESS if is_confident else StepStatus.SKIPPED
            steps.append(
                PipelineStepResult(
                    step_name="confidence",
                    status=status,
                    duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                    metadata={
                        "confidence": confidence,
                        "threshold": 0.5,
                        "is_confident": is_confident,
                    },
                )
            )
        except Exception as exc:
            logger.warning("pipeline_confidence_failed", error=str(exc))
            steps.append(
                PipelineStepResult(
                    step_name="confidence",
                    status=StepStatus.FAILED,
                    duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                    metadata={"error": str(exc)},
                )
            )

        # ── Step 3: Tenant Language ─────────────────────────────────
        step_start = time.monotonic()
        try:
            effective_lang = tenant_language or detected_language
            needs_translation = (
                detected_language != Language.ENGLISH
                and effective_lang == Language.ENGLISH
            )
            steps.append(
                PipelineStepResult(
                    step_name="tenant_language",
                    status=StepStatus.SUCCESS,
                    duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                    metadata={
                        "tenant_language": tenant_language,
                        "detected_language": detected_language,
                        "effective_language": effective_lang,
                        "needs_translation": needs_translation,
                    },
                )
            )
        except Exception as exc:
            logger.warning("pipeline_tenant_language_failed", error=str(exc))
            needs_translation = detected_language != Language.ENGLISH
            steps.append(
                PipelineStepResult(
                    step_name="tenant_language",
                    status=StepStatus.FAILED,
                    duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                    metadata={"error": str(exc)},
                )
            )

        # ── Step 4: Translate to English ────────────────────────────
        step_start = time.monotonic()
        if detected_language != Language.ENGLISH:
            try:
                translated_text, success = self._translator.translate(
                    original_text, detected_language, Language.ENGLISH
                )
                if success and translated_text:
                    translation_performed = True
                    steps.append(
                        PipelineStepResult(
                            step_name="translate",
                            status=StepStatus.SUCCESS,
                            duration_ms=round(
                                (time.monotonic() - step_start) * 1000, 2
                            ),
                            metadata={
                                "source": detected_language,
                                "target": Language.ENGLISH,
                                "success": True,
                            },
                        )
                    )
                else:
                    steps.append(
                        PipelineStepResult(
                            step_name="translate",
                            status=StepStatus.FAILED,
                            duration_ms=round(
                                (time.monotonic() - step_start) * 1000, 2
                            ),
                            metadata={
                                "source": detected_language,
                                "target": Language.ENGLISH,
                                "success": False,
                            },
                        )
                    )
                    translated_text = original_text
            except Exception as exc:
                logger.warning("pipeline_translate_failed", error=str(exc))
                steps.append(
                    PipelineStepResult(
                        step_name="translate",
                        status=StepStatus.FAILED,
                        duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                        metadata={"error": str(exc)},
                    )
                )
                translated_text = original_text
        else:
            # Already English — skip
            steps.append(
                PipelineStepResult(
                    step_name="translate",
                    status=StepStatus.SKIPPED,
                    duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                    metadata={"reason": "source_is_english"},
                )
            )

        # ── Step 5: AI Process (pass-through marker) ────────────────
        step_start = time.monotonic()
        try:
            steps.append(
                PipelineStepResult(
                    step_name="ai_process",
                    status=StepStatus.SUCCESS,
                    duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                    metadata={
                        "text_length": len(translated_text),
                        "note": "AI processing would happen here in production",
                    },
                )
            )
        except Exception as exc:
            logger.warning("pipeline_ai_process_failed", error=str(exc))
            steps.append(
                PipelineStepResult(
                    step_name="ai_process",
                    status=StepStatus.FAILED,
                    duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                    metadata={"error": str(exc)},
                )
            )

        # ── Step 6: Translate Back (simulated) ──────────────────────
        step_start = time.monotonic()
        if translation_performed and detected_language != Language.ENGLISH:
            try:
                back_text, success = self._translator.translate_back(
                    translated_text, detected_language, Language.ENGLISH
                )
                if success:
                    steps.append(
                        PipelineStepResult(
                            step_name="translate_back",
                            status=StepStatus.SUCCESS,
                            duration_ms=round(
                                (time.monotonic() - step_start) * 1000, 2
                            ),
                            metadata={
                                "target": detected_language,
                                "success": True,
                            },
                        )
                    )
                    # For pipeline result, keep the English translation
                    # back_text is what would be shown to user
                else:
                    steps.append(
                        PipelineStepResult(
                            step_name="translate_back",
                            status=StepStatus.FAILED,
                            duration_ms=round(
                                (time.monotonic() - step_start) * 1000, 2
                            ),
                            metadata={"target": detected_language, "success": False},
                        )
                    )
            except Exception as exc:
                logger.warning("pipeline_translate_back_failed", error=str(exc))
                steps.append(
                    PipelineStepResult(
                        step_name="translate_back",
                        status=StepStatus.FAILED,
                        duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                        metadata={"error": str(exc)},
                    )
                )
        else:
            steps.append(
                PipelineStepResult(
                    step_name="translate_back",
                    status=StepStatus.SKIPPED,
                    duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                    metadata={"reason": "no_translation_performed"},
                )
            )

        # ── Step 7: Quality Check ───────────────────────────────────
        step_start = time.monotonic()
        if translation_performed:
            try:
                quality_score, quality_issues = self._quality_checker.check(
                    translated_text, detected_language, Language.ENGLISH
                )
                steps.append(
                    PipelineStepResult(
                        step_name="quality_check",
                        status=StepStatus.SUCCESS,
                        duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                        metadata={
                            "quality_score": quality_score,
                            "issues_count": len(quality_issues),
                            "issues": quality_issues,
                        },
                    )
                )
            except Exception as exc:
                logger.warning("pipeline_quality_check_failed", error=str(exc))
                quality_score = 0.5
                quality_issues = ["quality_check_error"]
                steps.append(
                    PipelineStepResult(
                        step_name="quality_check",
                        status=StepStatus.FAILED,
                        duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                        metadata={"error": str(exc)},
                    )
                )
        else:
            steps.append(
                PipelineStepResult(
                    step_name="quality_check",
                    status=StepStatus.SKIPPED,
                    duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                    metadata={"reason": "no_translation_performed"},
                )
            )

        # ── Step 8: Fallback ────────────────────────────────────────
        step_start = time.monotonic()
        failed_steps = [s for s in steps if s.status == StepStatus.FAILED]
        if failed_steps:
            fallback_used = True
            failed_names = [s.step_name for s in failed_steps]
            fallback_warning = f"Pipeline completed with {
                    len(failed_steps)} failed step(s): " f"{
                    ', '.join(failed_names)}. Original text returned as fallback."
            translated_text = original_text
            translation_performed = False
        steps.append(
            PipelineStepResult(
                step_name="fallback",
                status=StepStatus.SUCCESS if not failed_steps else StepStatus.FAILED,
                duration_ms=round((time.monotonic() - step_start) * 1000, 2),
                metadata={
                    "fallback_used": fallback_used,
                    "failed_steps": [s.step_name for s in failed_steps],
                },
            )
        )

        # ── Cache result (BC-001: scoped to company_id) ─────────────
        total_ms = round((time.monotonic() - start_time) * 1000, 2)
        try:
            from app.core.redis import cache_get, cache_set

            query_hash = hashlib.sha256(
                original_text.lower().strip().encode("utf-8")
            ).hexdigest()[:16]
            # G9-GAP-10 FIX: Include tenant_language in cache key to prevent
            # returning stale cached results for different language preferences
            lang_suffix = (tenant_language or "none").lower()
            cache_key = f"lang_pipeline:{company_id}:{query_hash}:{lang_suffix}"
            # Try to read cache (for logging)
            cached = await cache_get(company_id, cache_key)
            if cached is None:
                # Write result to cache
                result_dict = {
                    "detected_language": detected_language,
                    "detection_confidence": confidence,
                    "translated_text": translated_text,
                    "translation_performed": translation_performed,
                    "quality_score": quality_score,
                }
                await cache_set(
                    company_id,
                    cache_key,
                    result_dict,
                    ttl_seconds=self.CACHE_TTL_SECONDS,
                )
        except Exception as exc:
            # BC-008: Cache failure must not affect pipeline
            logger.warning("pipeline_cache_error", error=str(exc))

        logger.info(
            "language_pipeline_complete",
            company_id=company_id,
            detected_language=detected_language,
            confidence=round(confidence, 2),
            translation_performed=translation_performed,
            quality_score=round(quality_score, 2),
            elapsed_ms=total_ms,
        )

        return PipelineResult(
            original_text=original_text,
            detected_language=detected_language,
            detection_confidence=confidence,
            translated_text=translated_text,
            tenant_language=tenant_language,
            translation_performed=translation_performed,
            quality_score=quality_score,
            quality_issues=quality_issues,
            processing_time_ms=total_ms,
            pipeline_steps=steps,
            fallback_used=fallback_used,
            fallback_warning=fallback_warning,
        )
