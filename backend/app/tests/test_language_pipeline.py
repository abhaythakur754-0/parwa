"""
Tests for Language Pipeline (SG-29) and Response Formatters (SG-26)

Covers:
- LanguageDetector: detection for all supported languages, confidence scoring,
  edge cases (mixed scripts, short text, empty text)
- LanguagePipeline: all 8 steps, step statuses, error handling, quality checks,
  fallback behavior, cache
- TranslationSimulator: basic functionality
- TranslationQualityChecker: untranslated segments, mixed scripts, garbled text
- Unicode/non-ASCII handling, empty/null input (BC-008), very long input
- All 15 response formatters individually
- FormatterRegistry: register, get, apply_all, duplicate registration
- Per-variant defaults, FormattingContext validation, composability
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.language_pipeline import (
    Language,
    LanguageDetector,
    LanguagePipeline,
    PipelineResult,
    PipelineStepResult,
    StepStatus,
    TranslationQualityChecker,
    TranslationSimulator,
)
from app.core.response_formatters import (
    ActionItemFormatter,
    BaseFormatter,
    BoldFormatter,
    CitationFormatter,
    CodeBlockFormatter,
    DisambiguationFormatter,
    EmojiFormatter,
    EscalationFormatter,
    FormattingContext,
    FormattingResult,
    FormatterRegistry,
    LengthFormatter,
    LinkFormatter,
    ListFormatter,
    MarkdownFormatter,
    SignatureFormatter,
    ToneFormatter,
    TokenLimitFormatter,
    WhitespaceFormatter,
    create_default_registry,
)

# ═══════════════════════════════════════════════════════════════════════
# LANGUAGE DETECTOR TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestLanguageDetector:
    def setup_method(self):
        self.detector = LanguageDetector()

    # ── English ──────────────────────────────────────────────────────

    def test_english_simple(self):
        lang, conf = self.detector.detect("Hello, how are you today?")
        assert lang == Language.ENGLISH
        assert conf > 0.0

    def test_english_long(self):
        lang, conf = self.detector.detect(
            "I need help with my account. The password reset is not working "
            "and I have been trying for three days. Can someone please assist me?"
        )
        assert lang == Language.ENGLISH
        assert conf > 0.3

    # ── Spanish ──────────────────────────────────────────────────────

    def test_spanish_simple(self):
        lang, conf = self.detector.detect("Hola, ¿cómo estás?")
        assert lang == Language.SPANISH
        assert conf > 0.0

    def test_spanish_paragraph(self):
        lang, conf = self.detector.detect(
            "Hola, necesito ayuda con mi pedido. Quiero un reembolso "
            "porque el producto llegó dañado. Por favor, ayúdame."
        )
        assert lang == Language.SPANISH
        assert conf > 0.2

    # ── French ───────────────────────────────────────────────────────

    def test_french_simple(self):
        lang, conf = self.detector.detect("Bonjour, comment allez-vous?")
        assert lang == Language.FRENCH
        assert conf > 0.0

    def test_french_paragraph(self):
        lang, conf = self.detector.detect(
            "Bonjour, j'ai besoin d'aide avec ma commande. Je veux un "
            "remboursement car le produit est endommagé. Merci de m'aider."
        )
        assert lang == Language.FRENCH
        assert conf > 0.2

    # ── German ───────────────────────────────────────────────────────

    def test_german_simple(self):
        lang, conf = self.detector.detect("Hallo, wie geht es Ihnen?")
        assert lang == Language.GERMAN
        assert conf > 0.0

    def test_german_paragraph(self):
        lang, conf = self.detector.detect(
            "Hallo, ich brauche Hilfe mit meiner Bestellung. Ich möchte eine "
            "Rückerstattung weil das Produkt beschädigt ist. Bitte helfen Sie mir."
        )
        assert lang == Language.GERMAN
        assert conf > 0.2

    # ── Portuguese ───────────────────────────────────────────────────

    def test_portuguese_simple(self):
        lang, conf = self.detector.detect("Olá, como você está?")
        assert lang == Language.PORTUGUESE
        assert conf > 0.0

    def test_portuguese_paragraph(self):
        lang, conf = self.detector.detect(
            "Olá, preciso de ajuda com meu pedido. Quero um reembolso "
            "porque o produto chegou danificado. Por favor, me ajude."
        )
        assert lang == Language.PORTUGUESE
        assert conf > 0.2

    # ── Hindi ────────────────────────────────────────────────────────

    def test_hindi_simple(self):
        lang, conf = self.detector.detect("नमस्ते, आप कैसे हैं?")
        assert lang == Language.HINDI
        assert conf > 0.0

    def test_hindi_paragraph(self):
        lang, conf = self.detector.detect(
            "नमस्ते, मुझे अपने ऑर्डर में मदद चाहिए। मैं एक वापसी चाहता हूं "
            "क्योंकि उत्पाद क्षतिग्रस्त है। कृपया मेरी मदद करें।"
        )
        assert lang == Language.HINDI
        assert conf > 0.0

    # ── Chinese (Simplified) ─────────────────────────────────────────

    def test_chinese_simple(self):
        lang, conf = self.detector.detect("你好，你好吗？")
        assert lang == Language.CHINESE
        assert conf > 0.0

    def test_chinese_paragraph(self):
        lang, conf = self.detector.detect(
            "您好，我需要帮助处理我的订单。产品已损坏，我想要退款。"
            "请帮助我解决这个问题。"
        )
        assert lang == Language.CHINESE
        assert conf > 0.0

    # ── Japanese ─────────────────────────────────────────────────────

    def test_japanese_simple(self):
        lang, conf = self.detector.detect("こんにちは、お元気ですか？")
        assert lang == Language.JAPANESE
        assert conf > 0.0

    def test_japanese_paragraph(self):
        lang, conf = self.detector.detect(
            "こんにちは、注文について助けが必要です。商品が破損しているため、"
            "返金をお願いします。どうぞよろしくお願いします。"
        )
        assert lang == Language.JAPANESE
        assert conf > 0.0

    # ── Arabic ───────────────────────────────────────────────────────

    def test_arabic_simple(self):
        lang, conf = self.detector.detect("مرحبا، كيف حالك؟")
        assert lang == Language.ARABIC
        assert conf > 0.0

    def test_arabic_paragraph(self):
        lang, conf = self.detector.detect(
            "مرحبا، أحتاج مساعدة مع طلبي. المنتج تالف وأريد استرداد الأموال. "
            "يرجى المساعدة."
        )
        assert lang == Language.ARABIC
        assert conf > 0.0

    # ── Korean ───────────────────────────────────────────────────────

    def test_korean_simple(self):
        lang, conf = self.detector.detect("안녕하세요, 어떻게 지내세요?")
        assert lang == Language.KOREAN
        assert conf > 0.0

    def test_korean_paragraph(self):
        lang, conf = self.detector.detect(
            "안녕하세요, 주문에 대해 도움이 필요합니다. 제품이 손상되어 "
            "환불을 요청합니다. 도와주세요."
        )
        assert lang == Language.KOREAN
        assert conf > 0.0

    # ── Edge Cases ───────────────────────────────────────────────────

    def test_empty_string(self):
        lang, conf = self.detector.detect("")
        assert lang == Language.UNKNOWN
        assert conf == 0.0

    def test_whitespace_only(self):
        lang, conf = self.detector.detect("   \n\t  ")
        assert lang == Language.UNKNOWN
        assert conf == 0.0

    def test_single_word(self):
        lang, conf = self.detector.detect("Hello")
        assert lang == Language.ENGLISH
        assert conf > 0.0

    def test_mixed_scripts_latin_and_cjk(self):
        # Japanese text mixed with Latin
        lang, conf = self.detector.detect("こんにちは、これはテストtestです")
        # Should detect Japanese due to hiragana/katakana
        assert lang == Language.JAPANESE

    def test_numbers_only(self):
        lang, conf = self.detector.detect("12345 67890")
        assert lang == Language.UNKNOWN

    def test_special_characters_only(self):
        lang, conf = self.detector.detect("@#$%^&*()!")
        assert lang == Language.UNKNOWN

    def test_very_short_text(self):
        lang, conf = self.detector.detect("Hi")
        assert lang == Language.ENGLISH
        assert conf > 0.0

    def test_confidence_range(self):
        """All confidence values should be 0.0-1.0."""
        texts = [
            "Hello",
            "Hola",
            "Bonjour",
            "Hallo",
            "Olá",
            "你好",
            "こんにちは",
            "مرحبا",
            "안녕하세요",
            "नमस्ते",
        ]
        for text in texts:
            _, conf = self.detector.detect(text)
            assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of range for: {text}"

    def test_unicode_emoji_text(self):
        """Emoji-heavy text should still be detected."""
        lang, conf = self.detector.detect("I need help 😊🎉 with my order")
        assert lang == Language.ENGLISH


# ═══════════════════════════════════════════════════════════════════════
# TRANSLATION SIMULATOR TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestTranslationSimulator:
    def setup_method(self):
        self.simulator = TranslationSimulator()

    def test_translate_empty_string(self):
        text, success = self.simulator.translate("", "es", "en")
        assert text == ""
        assert success is True

    def test_translate_same_language(self):
        text, success = self.simulator.translate("Hello", "en", "en")
        assert text == "Hello"
        assert success is True

    def test_translate_spanish_known_phrase(self):
        text, success = self.simulator.translate("hola", "es", "en")
        assert text == "hello"
        assert success is True

    def test_translate_spanish_sentence(self):
        text, success = self.simulator.translate("hola gracias por favor", "es", "en")
        assert "hello" in text.lower()
        assert success is True

    def test_translate_french_known_phrase(self):
        text, success = self.simulator.translate("bonjour", "fr", "en")
        assert text == "hello"
        assert success is True

    def test_translate_german_known_phrase(self):
        text, success = self.simulator.translate("hallo", "de", "en")
        assert text == "hello"
        assert success is True

    def test_translate_portuguese_known_phrase(self):
        text, success = self.simulator.translate("olá", "pt", "en")
        assert text == "hello"
        assert success is True

    def test_translate_chinese_simulated(self):
        text, success = self.simulator.translate("你好", "zh", "en")
        assert "Translated from Chinese" in text
        assert success is True

    def test_translate_japanese_simulated(self):
        text, success = self.simulator.translate("こんにちは", "ja", "en")
        assert "Translated from Japanese" in text
        assert success is True

    def test_translate_hindi_simulated(self):
        text, success = self.simulator.translate("नमस्ते", "hi", "en")
        assert "Translated from Hindi" in text
        assert success is True

    def test_translate_arabic_simulated(self):
        text, success = self.simulator.translate("مرحبا", "ar", "en")
        assert "Translated from Arabic" in text
        assert success is True

    def test_translate_korean_simulated(self):
        text, success = self.simulator.translate("안녕하세요", "ko", "en")
        assert "Translated from Korean" in text
        assert success is True

    def test_translate_back_empty(self):
        text, success = self.simulator.translate_back("", "es", "en")
        assert text == ""
        assert success is True

    def test_translate_back_same_language(self):
        text, success = self.simulator.translate_back("hello", "en", "en")
        assert text == "hello"
        assert success is True

    def test_translate_back_spanish(self):
        text, success = self.simulator.translate_back("hello help please", "es", "en")
        # Should have some reverse-translated words
        assert success is True

    def test_translate_back_chinese_suffix(self):
        text, success = self.simulator.translate_back("hello world", "zh", "en")
        assert "中文翻译" in text or "translated" in text.lower()
        assert success is True


# ═══════════════════════════════════════════════════════════════════════
# TRANSLATION QUALITY CHECKER TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestTranslationQualityChecker:
    def setup_method(self):
        self.checker = TranslationQualityChecker()

    def test_clean_translation(self):
        score, issues = self.checker.check(
            "This is a clean translated text.", "es", "en"
        )
        assert score >= 0.7
        assert len(issues) == 0

    def test_empty_translation(self):
        score, issues = self.checker.check("", "es", "en")
        assert score == 0.0
        assert "empty_translation" in issues

    def test_untranslated_segments(self):
        # "hola" is a Spanish word remaining in English text
        score, issues = self.checker.check("Hello hola how are you", "es", "en")
        assert any("untranslated" in i for i in issues)

    def test_no_untranslated_for_same_language(self):
        score, issues = self.checker.check("Hello hola how are you", "en", "en")
        assert not any("untranslated" in i for i in issues)

    def test_mixed_scripts_detected(self):
        score, issues = self.checker.check(
            "This is English これは日本語 text", "ja", "en"
        )
        assert any("mixed" in i for i in issues)

    def test_garbled_repeated_chars(self):
        score, issues = self.checker.check("aaaaaaaaa bbbbbbbbb test", "es", "en")
        assert any("garbled" in i for i in issues) or any(
            "repeated" in i for i in issues
        )

    def test_garbled_replacement_chars(self):
        score, issues = self.checker.check(
            "Some text \ufffd\ufffd more text", "es", "en"
        )
        assert any("garbled" in i for i in issues) or any(
            "replacement" in i for i in issues
        )

    def test_placeholder_detected(self):
        score, issues = self.checker.check(
            "Some text [translation failed] more", "es", "en"
        )
        assert any("placeholder" in i for i in issues)

    def test_score_bounded(self):
        for text in ["a", "normal text", "x" * 1000]:
            score, _ = self.checker.check(text, "es", "en")
            assert 0.0 <= score <= 1.0


# ═══════════════════════════════════════════════════════════════════════
# LANGUAGE PIPELINE TESTS (Full 8-step)
# ═══════════════════════════════════════════════════════════════════════


class TestLanguagePipeline:
    def setup_method(self):
        self.pipeline = LanguagePipeline()

    @pytest.mark.asyncio
    async def test_english_passthrough(self):
        """English text should skip translation steps."""
        result = await self.pipeline.process(
            "Hello, I need help with my order.", "company_123"
        )
        assert result.detected_language == Language.ENGLISH
        assert result.translation_performed is False
        assert result.original_text == result.translated_text

    @pytest.mark.asyncio
    async def test_spanish_detection_and_translation(self):
        """Spanish text should be detected and translated."""
        result = await self.pipeline.process(
            "Hola, necesito ayuda con mi pedido.", "company_123"
        )
        assert result.detected_language == Language.SPANISH
        assert result.translation_performed is True
        assert len(result.pipeline_steps) == 8

    @pytest.mark.asyncio
    async def test_french_detection(self):
        result = await self.pipeline.process(
            "Bonjour, j'ai besoin d'aide.", "company_123"
        )
        assert result.detected_language == Language.FRENCH

    @pytest.mark.asyncio
    async def test_chinese_detection(self):
        result = await self.pipeline.process("你好，我需要帮助。", "company_123")
        assert result.detected_language == Language.CHINESE

    @pytest.mark.asyncio
    async def test_japanese_detection(self):
        result = await self.pipeline.process(
            "こんにちは、助けてください。", "company_123"
        )
        assert result.detected_language == Language.JAPANESE

    @pytest.mark.asyncio
    async def test_arabic_detection(self):
        result = await self.pipeline.process("مرحبا، أحتاج مساعدة.", "company_123")
        assert result.detected_language == Language.ARABIC

    @pytest.mark.asyncio
    async def test_korean_detection(self):
        result = await self.pipeline.process("안녕하세요, 도와주세요.", "company_123")
        assert result.detected_language == Language.KOREAN

    @pytest.mark.asyncio
    async def test_hindi_detection(self):
        result = await self.pipeline.process("नमस्ते, मुझे मदद चाहिए।", "company_123")
        assert result.detected_language == Language.HINDI

    @pytest.mark.asyncio
    async def test_eight_steps(self):
        """Pipeline should always have exactly 8 steps."""
        result = await self.pipeline.process("Hello there", "company_123")
        assert len(result.pipeline_steps) == 8
        step_names = [s.step_name for s in result.pipeline_steps]
        expected = [
            "detection",
            "confidence",
            "tenant_language",
            "translate",
            "ai_process",
            "translate_back",
            "quality_check",
            "fallback",
        ]
        assert step_names == expected

    @pytest.mark.asyncio
    async def test_step_statuses_english(self):
        """For English: translate=skipped, translate_back=skipped, quality_check=skipped."""
        result = await self.pipeline.process("Hello, I need help.", "company_123")
        steps_by_name = {s.step_name: s.status for s in result.pipeline_steps}
        assert steps_by_name["translate"] == StepStatus.SKIPPED
        assert steps_by_name["translate_back"] == StepStatus.SKIPPED
        assert steps_by_name["quality_check"] == StepStatus.SKIPPED
        assert steps_by_name["detection"] == StepStatus.SUCCESS
        assert steps_by_name["ai_process"] == StepStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_step_statuses_spanish(self):
        """For Spanish: translate=success, translate_back=success, quality_check=success."""
        result = await self.pipeline.process("Hola, necesito ayuda.", "company_123")
        steps_by_name = {s.step_name: s.status for s in result.pipeline_steps}
        assert steps_by_name["translate"] == StepStatus.SUCCESS
        assert steps_by_name["translate_back"] == StepStatus.SUCCESS
        assert steps_by_name["quality_check"] == StepStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_tenant_language_parameter(self):
        """Tenant language should be recorded in the result."""
        result = await self.pipeline.process(
            "Hello", "company_123", tenant_language="es"
        )
        assert result.tenant_language == "es"

    @pytest.mark.asyncio
    async def test_tenant_language_none(self):
        result = await self.pipeline.process(
            "Hello", "company_123", tenant_language=None
        )
        assert result.tenant_language is None

    @pytest.mark.asyncio
    async def test_confidence_score_present(self):
        result = await self.pipeline.process(
            "Bonjour comment allez-vous", "company_123"
        )
        assert 0.0 <= result.detection_confidence <= 1.0

    @pytest.mark.asyncio
    async def test_quality_score_present(self):
        result = await self.pipeline.process(
            "Hola necesito ayuda con mi pedido", "company_123"
        )
        assert 0.0 <= result.quality_score <= 1.0

    @pytest.mark.asyncio
    async def test_processing_time_present(self):
        result = await self.pipeline.process("Hello", "company_123")
        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_step_durations_present(self):
        result = await self.pipeline.process("Hello", "company_123")
        for step in result.pipeline_steps:
            assert step.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_empty_query_bc008(self):
        """Empty input returns gracefully (BC-008)."""
        result = await self.pipeline.process("", "company_123")
        assert result.detected_language == Language.UNKNOWN
        assert result.fallback_used is True
        assert result.fallback_warning is not None

    @pytest.mark.asyncio
    async def test_none_query_bc008(self):
        """None input returns gracefully (BC-008)."""
        result = await self.pipeline.process(None, "company_123")  # type: ignore[arg-type]
        assert result.fallback_used is True

    @pytest.mark.asyncio
    async def test_whitespace_query_bc008(self):
        result = await self.pipeline.process("   \n\t  ", "company_123")
        assert result.fallback_used is True

    @pytest.mark.asyncio
    async def test_very_long_input(self):
        """Very long input (>10k chars) should not crash."""
        long_text = "Hello, I need help with my order. " * 500
        assert len(long_text) > 10000
        result = await self.pipeline.process(long_text, "company_123")
        assert result.detected_language == Language.ENGLISH
        assert len(result.pipeline_steps) == 8

    @pytest.mark.asyncio
    async def test_unicode_input(self):
        """Unicode/non-ASCII should be handled correctly."""
        result = await self.pipeline.process(
            "Grüß Gott! こんにちは! مرحبا!", "company_123"
        )
        assert isinstance(result.detected_language, str)

    @pytest.mark.asyncio
    async def test_cache_fail_open(self):
        """Redis failure should not crash pipeline (BC-008)."""
        with patch(
            "app.core.redis.cache_get",
            new_callable=AsyncMock,
            side_effect=Exception("Redis down"),
        ):
            with patch(
                "app.core.redis.cache_set",
                new_callable=AsyncMock,
                side_effect=Exception("Redis down"),
            ):
                result = await self.pipeline.process(
                    "Hola, necesito ayuda.", "company_123"
                )
                assert result.detected_language == Language.SPANISH
                assert len(result.pipeline_steps) == 8

    @pytest.mark.asyncio
    async def test_fallback_not_used_on_success(self):
        """Fallback should not be used when all steps succeed."""
        result = await self.pipeline.process("Hello, I need help.", "company_123")
        assert result.fallback_used is False
        assert result.fallback_warning is None

    @pytest.mark.asyncio
    async def test_result_serialization(self):
        """PipelineResult.to_dict() should work."""
        result = await self.pipeline.process("Hello", "company_123")
        d = result.to_dict()
        assert "original_text" in d
        assert "detected_language" in d
        assert "pipeline_steps" in d
        assert isinstance(d["pipeline_steps"], list)


# ═══════════════════════════════════════════════════════════════════════
# PIPELINE DATA CLASS TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineDataClasses:
    def test_pipeline_step_result(self):
        step = PipelineStepResult(
            step_name="test_step",
            status=StepStatus.SUCCESS,
            duration_ms=1.5,
            metadata={"key": "value"},
        )
        assert step.step_name == "test_step"
        assert step.status == StepStatus.SUCCESS
        assert step.duration_ms == 1.5
        assert step.metadata == {"key": "value"}

    def test_pipeline_result_defaults(self):
        result = PipelineResult(
            original_text="hello",
            detected_language="en",
            detection_confidence=0.9,
            translated_text="hello",
            tenant_language=None,
            translation_performed=False,
            quality_score=1.0,
            quality_issues=[],
            processing_time_ms=5.0,
            pipeline_steps=[],
        )
        assert result.fallback_used is False
        assert result.fallback_warning is None

    def test_pipeline_result_to_dict(self):
        result = PipelineResult(
            original_text="hola",
            detected_language="es",
            detection_confidence=0.85,
            translated_text="hello",
            tenant_language="en",
            translation_performed=True,
            quality_score=0.9,
            quality_issues=[],
            processing_time_ms=10.0,
            pipeline_steps=[
                PipelineStepResult(
                    step_name="detection",
                    status=StepStatus.SUCCESS,
                    duration_ms=2.0,
                ),
            ],
        )
        d = result.to_dict()
        assert d["original_text"] == "hola"
        assert d["detected_language"] == "es"
        assert len(d["pipeline_steps"]) == 1
        assert d["pipeline_steps"][0]["step_name"] == "detection"
        assert d["pipeline_steps"][0]["status"] == "success"


# ═══════════════════════════════════════════════════════════════════════
# RESPONSE FORMATTER TESTS
# ═══════════════════════════════════════════════════════════════════════


# ── 1. TokenLimitFormatter ────────────────────────────────────────────


class TestTokenLimitFormatter:
    def setup_method(self):
        self.formatter = TokenLimitFormatter()
        self.ctx = FormattingContext(model_tier="standard")

    def test_short_text_unchanged(self):
        result = self.formatter.format("Short text.", self.ctx)
        assert result == "Short text."

    def test_long_text_truncated(self):
        # 2048 tokens * 4 chars = 8192 chars
        long_text = "word " * 3000  # ~15000 chars
        result = self.formatter.format(long_text, self.ctx)
        assert len(result) < len(long_text)

    def test_mini_model_limit(self):
        ctx = FormattingContext(model_tier="mini")
        # 512 tokens * 4 = 2048 chars
        long_text = "a" * 5000
        result = self.formatter.format(long_text, ctx)
        assert len(result) <= 2100

    def test_empty_response(self):
        result = self.formatter.format("", self.ctx)
        assert result == ""

    def test_truncates_at_sentence(self):
        long = "This is sentence one. " * 500
        result = self.formatter.format(long, self.ctx)
        assert result.endswith(".") or result.endswith("...")

    def test_name(self):
        assert self.formatter.name == "token_limit"


# ── 2. MarkdownFormatter ─────────────────────────────────────────────


class TestMarkdownFormatter:
    def setup_method(self):
        self.formatter = MarkdownFormatter()
        self.ctx = FormattingContext()

    def test_fix_header_no_space(self):
        result = self.formatter.format("##Header without space", self.ctx)
        assert "## Header" in result

    def test_fix_broken_bullet(self):
        result = self.formatter.format("-item without space", self.ctx)
        assert "- item" in result

    def test_fix_broken_numbered_list(self):
        result = self.formatter.format("1.first item", self.ctx)
        assert "1. first" in result

    def test_fix_empty_link(self):
        result = self.formatter.format("Click [here]()", self.ctx)
        assert "[here](#)" in result

    def test_empty_response(self):
        result = self.formatter.format("", self.ctx)
        assert result == ""

    def test_no_change_needed(self):
        text = "## Proper Header\n\n- Proper bullet\n\n1. Proper numbered"
        result = self.formatter.format(text, self.ctx)
        assert result == text

    def test_name(self):
        assert self.formatter.name == "markdown"


# ── 3. CitationFormatter ─────────────────────────────────────────────


class TestCitationFormatter:
    def setup_method(self):
        self.formatter = CitationFormatter()
        self.ctx = FormattingContext()

    def test_adds_sources_section(self):
        text = "According to research [1] and another study [2], the results show."
        result = self.formatter.format(text, self.ctx)
        assert "**Sources:**" in result

    def test_single_citation_no_sources(self):
        text = "According to research [1], the results show."
        result = self.formatter.format(text, self.ctx)
        assert "**Sources:**" not in result

    def test_no_citations_unchanged(self):
        text = "No citations here."
        result = self.formatter.format(text, self.ctx)
        assert result == text

    def test_no_duplicate_sources(self):
        text = "Research [1] shows [1] and [1] this."
        result = self.formatter.format(text, self.ctx)
        # Should not add sources (only 1 unique citation)
        assert "**Sources:**" not in result

    def test_empty_response(self):
        result = self.formatter.format("", self.ctx)
        assert result == ""

    def test_name(self):
        assert self.formatter.name == "citation"


# ── 4. ToneFormatter ──────────────────────────────────────────────────


class TestToneFormatter:
    def setup_method(self):
        self.formatter = ToneFormatter()

    def test_casual_contractions(self):
        ctx = FormattingContext(brand_voice="casual")
        result = self.formatter.format("I will help you with that.", ctx)
        assert "I'll" in result

    def test_professional_no_slang(self):
        ctx = FormattingContext(brand_voice="professional")
        result = self.formatter.format("Hey yeah that's gonna be cool.", ctx)
        assert "Hey" not in result or "Hello" in result

    def test_friendly_mild_contractions(self):
        ctx = FormattingContext(brand_voice="friendly")
        result = self.formatter.format("I will do it now.", ctx)
        assert "I'll" in result

    def test_empty_response(self):
        ctx = FormattingContext()
        result = self.formatter.format("", ctx)
        assert result == ""

    def test_neutral_voice_unchanged(self):
        ctx = FormattingContext(brand_voice="neutral")
        text = "I will help you."
        result = self.formatter.format(text, ctx)
        assert result == text

    def test_name(self):
        assert self.formatter.name == "tone"


# ── 5. LengthFormatter ────────────────────────────────────────────────


class TestLengthFormatter:
    def setup_method(self):
        self.formatter = LengthFormatter()

    def test_concise_for_happy_user(self):
        ctx = FormattingContext(sentiment_score=0.9)
        text = "Needless to say, As a matter of fact, this is the answer."
        result = self.formatter.format(text, ctx)
        assert "Needless to say" not in result

    def test_detailed_for_unhappy_user(self):
        ctx = FormattingContext(sentiment_score=0.2)
        short = "Fixed."
        result = self.formatter.format(short, ctx)
        assert len(result) > len(short)

    def test_standard_for_neutral(self):
        ctx = FormattingContext(sentiment_score=0.5)
        text = "This is a normal response."
        result = self.formatter.format(text, ctx)
        assert "This is a normal response." in result

    def test_empty_response(self):
        ctx = FormattingContext()
        result = self.formatter.format("", ctx)
        assert result == ""

    def test_condense_multiple_fillers(self):
        ctx = FormattingContext(sentiment_score=0.9)
        text = "At the end of the day, it is worth noting that this works fine."
        result = self.formatter.format(text, ctx)
        assert "At the end of the day" not in result

    def test_name(self):
        assert self.formatter.name == "length"


# ── 6. CodeBlockFormatter ────────────────────────────────────────────


class TestCodeBlockFormatter:
    def setup_method(self):
        self.formatter = CodeBlockFormatter()
        self.ctx = FormattingContext()

    def test_adds_language_tag(self):
        result = self.formatter.format("```\ncode here\n```", self.ctx)
        assert "```text" in result

    def test_fixes_unclosed_code_block(self):
        result = self.formatter.format("```\ncode here", self.ctx)
        assert result.endswith("```")

    def test_closed_block_unchanged(self):
        text = "```python\nprint('hello')\n```"
        result = self.formatter.format(text, self.ctx)
        assert "```python" in result

    def test_empty_response(self):
        result = self.formatter.format("", self.ctx)
        assert result == ""

    def test_name(self):
        assert self.formatter.name == "code_block"


# ── 7. ListFormatter ──────────────────────────────────────────────────


class TestListFormatter:
    def setup_method(self):
        self.formatter = ListFormatter()
        self.ctx = FormattingContext()

    def test_normalize_bullets(self):
        result = self.formatter.format("* item one\n• item two\n- item three", self.ctx)
        lines = result.strip().split("\n")
        for line in lines:
            assert line.lstrip().startswith("- ")

    def test_preserves_indentation(self):
        result = self.formatter.format("  * indented item", self.ctx)
        assert "  - indented item" in result

    def test_no_lists_unchanged(self):
        text = "Just a paragraph of text."
        result = self.formatter.format(text, self.ctx)
        assert result == text

    def test_empty_response(self):
        result = self.formatter.format("", self.ctx)
        assert result == ""

    def test_name(self):
        assert self.formatter.name == "list"


# ── 8. BoldFormatter ─────────────────────────────────────────────────


class TestBoldFormatter:
    def setup_method(self):
        self.formatter = BoldFormatter()
        self.ctx = FormattingContext()

    def test_excessive_bold_removed(self):
        # 6 bold sections
        text = "**a** **b** **c** **d** **e** **f**"
        result = self.formatter.format(text, self.ctx)
        assert "**" not in result

    def test_normal_bold_preserved(self):
        text = "**important** and **also important**"
        result = self.formatter.format(text, self.ctx)
        assert "**important**" in result

    def test_triple_asterisk_removed(self):
        text = "***bold and italic***"
        result = self.formatter.format(text, self.ctx)
        assert "***" not in result

    def test_empty_response(self):
        result = self.formatter.format("", self.ctx)
        assert result == ""

    def test_name(self):
        assert self.formatter.name == "bold"


# ── 9. LinkFormatter ──────────────────────────────────────────────────


class TestLinkFormatter:
    def setup_method(self):
        self.formatter = LinkFormatter()
        self.ctx = FormattingContext()

    def test_valid_url_unchanged(self):
        result = self.formatter.format(
            "Visit https://example.com for more info.", self.ctx
        )
        assert "https://example.com" in result

    def test_trailing_punctuation_removed(self):
        result = self.formatter.format("See https://example.com.", self.ctx)
        assert result.rstrip().endswith("example.com")

    def test_empty_response(self):
        result = self.formatter.format("", self.ctx)
        assert result == ""

    def test_no_urls_unchanged(self):
        text = "No URLs here."
        result = self.formatter.format(text, self.ctx)
        assert result == text

    def test_name(self):
        assert self.formatter.name == "link"


# ── 10. EmojiFormatter ────────────────────────────────────────────────


class TestEmojiFormatter:
    def setup_method(self):
        self.formatter = EmojiFormatter()

    def test_high_formality_strips_all(self):
        ctx = FormattingContext(formality_level="high")
        result = self.formatter.format("Hello 😊🎉😃👍", ctx)
        assert "😊" not in result
        assert "🎉" not in result

    def test_low_formality_keeps_all(self):
        ctx = FormattingContext(formality_level="low")
        text = "Hello 😊🎉😃👍🌟"
        result = self.formatter.format(text, ctx)
        assert result == text

    def test_medium_formality_limits(self):
        ctx = FormattingContext(formality_level="medium")
        text = "A😊 B🎉 C😃 D👍 E🌟"
        result = self.formatter.format(text, ctx)
        emojis = [c for c in result if ord(c) > 0x1F000]
        assert len(emojis) <= 2

    def test_no_emojis_unchanged(self):
        ctx = FormattingContext(formality_level="high")
        text = "No emojis here."
        result = self.formatter.format(text, ctx)
        assert result == text

    def test_empty_response(self):
        ctx = FormattingContext(formality_level="high")
        result = self.formatter.format("", ctx)
        assert result == ""

    def test_name(self):
        assert self.formatter.name == "emoji"


# ── 11. WhitespaceFormatter ───────────────────────────────────────────


class TestWhitespaceFormatter:
    def setup_method(self):
        self.formatter = WhitespaceFormatter()
        self.ctx = FormattingContext()

    def test_collapse_blank_lines(self):
        result = self.formatter.format("line 1\n\n\n\n\nline 2", self.ctx)
        assert "\n\n\n" not in result

    def test_collapse_spaces(self):
        result = self.formatter.format("too  many   spaces    here", self.ctx)
        assert "  " not in result

    def test_preserves_code_block_spaces(self):
        text = "Normal text\n```\n  indented  code\n```"
        result = self.formatter.format(text, self.ctx)
        # Code block content should be preserved
        assert "```" in result

    def test_trailing_whitespace_removed(self):
        result = self.formatter.format("text   \nnext   ", self.ctx)
        lines = result.split("\n")
        assert not lines[0].endswith(" ")
        assert not lines[1].endswith(" ")

    def test_empty_response(self):
        result = self.formatter.format("", self.ctx)
        assert result == ""

    def test_name(self):
        assert self.formatter.name == "whitespace"


# ── 12. SignatureFormatter ───────────────────────────────────────────


class TestSignatureFormatter:
    def setup_method(self):
        self.formatter = SignatureFormatter()

    def test_adds_professional_signature(self):
        ctx = FormattingContext(brand_voice="professional")
        text = "I have processed your refund. You will see it in 5-7 business days."
        result = self.formatter.format(text, ctx)
        assert "Best regards" in result
        assert "Support Team" in result

    def test_adds_friendly_signature(self):
        ctx = FormattingContext(brand_voice="friendly")
        text = (
            "Your issue has been resolved. The refund has been processed successfully."
        )
        result = self.formatter.format(text, ctx)
        assert "Cheers" in result

    def test_adds_casual_signature(self):
        ctx = FormattingContext(brand_voice="casual")
        text = "All done! Your refund is on the way. Let me know if you need anything else!"
        result = self.formatter.format(text, ctx)
        assert "Support Team" in result

    def test_no_duplicate_signature(self):
        ctx = FormattingContext(brand_voice="professional")
        text = "Done.\n\nBest regards,\nSupport Team"
        result = self.formatter.format(text, ctx)
        assert result.count("Best regards") == 1

    def test_short_text_no_signature(self):
        ctx = FormattingContext(brand_voice="professional")
        result = self.formatter.format("OK.", ctx)
        assert "Best regards" not in result

    def test_empty_response(self):
        ctx = FormattingContext()
        result = self.formatter.format("", ctx)
        assert result == ""

    def test_name(self):
        assert self.formatter.name == "signature"


# ── 13. DisambiguationFormatter ──────────────────────────────────────


class TestDisambiguationFormatter:
    def setup_method(self):
        self.formatter = DisambiguationFormatter()

    def test_adds_suggestions_for_reset(self):
        ctx = FormattingContext(intent_type="general")
        text = "I want to reset my settings. Please go to the settings page and click reset."
        result = self.formatter.format(text, ctx)
        assert "Did you mean" in result

    def test_no_suggestions_for_technical(self):
        ctx = FormattingContext(intent_type="technical")
        text = "I want to reset my settings."
        result = self.formatter.format(text, ctx)
        assert "Did you mean" not in result

    def test_no_duplicate_suggestions(self):
        ctx = FormattingContext(intent_type="inquiry")
        text = "Did you mean password reset? I want to reset."
        result = self.formatter.format(text, ctx)
        # Should not add duplicate "Did you mean"
        assert result.count("Did you mean") == 1

    def test_empty_response(self):
        ctx = FormattingContext(intent_type="general")
        result = self.formatter.format("", ctx)
        assert result == ""

    def test_name(self):
        assert self.formatter.name == "disambiguation"


# ── 14. ActionItemFormatter ───────────────────────────────────────────


class TestActionItemFormatter:
    def setup_method(self):
        self.formatter = ActionItemFormatter()
        self.ctx = FormattingContext()

    def test_extracts_action_items(self):
        text = "You can reset your password by going to settings. Please update your profile."
        result = self.formatter.format(text, self.ctx)
        assert "**Action Items:**" in result

    def test_no_duplicate_section(self):
        text = "**Action Items:**\n- item 1\n\nYou should do this."
        result = self.formatter.format(text, self.ctx)
        assert result.count("**Action Items:**") == 1

    def test_no_actions_no_section(self):
        text = "The weather is nice today."
        result = self.formatter.format(text, self.ctx)
        assert "**Action Items:**" not in result

    def test_empty_response(self):
        result = self.formatter.format("", self.ctx)
        assert result == ""

    def test_max_five_items(self):
        text = (
            "You should do step one. "
            "Please complete step two. "
            "Make sure to do step three. "
            "You can proceed with step four. "
            "Please handle step five. "
            "You should also do step six."
        )
        result = self.formatter.format(text, self.ctx)
        # Count items
        items = result.count("- ")
        assert items <= 7  # 5 action items + any existing in text

    def test_name(self):
        assert self.formatter.name == "action_item"


# ── 15. EscalationFormatter ───────────────────────────────────────────


class TestEscalationFormatter:
    def setup_method(self):
        self.formatter = EscalationFormatter()

    def test_escalation_gets_header(self):
        ctx = FormattingContext(intent_type="escalation")
        result = self.formatter.format("I am very unhappy with this service.", ctx)
        assert "Priority:" in result
        assert "Escalation Notice" in result

    def test_complaint_gets_header(self):
        ctx = FormattingContext(intent_type="complaint")
        result = self.formatter.format("This is a formal complaint.", ctx)
        assert "Priority:" in result

    def test_general_no_header(self):
        ctx = FormattingContext(intent_type="general")
        result = self.formatter.format("How do I reset my password?", ctx)
        assert "Priority:" not in result

    def test_vip_gets_critical(self):
        ctx = FormattingContext(intent_type="escalation", customer_tier="vip")
        result = self.formatter.format("Issue description.", ctx)
        assert "CRITICAL" in result

    def test_no_duplicate_formatting(self):
        ctx = FormattingContext(intent_type="escalation")
        text = "**Priority: HIGH** | Escalation Notice\n\nAlready formatted."
        result = self.formatter.format(text, ctx)
        assert result.count("Priority:") == 1

    def test_empty_response(self):
        ctx = FormattingContext(intent_type="escalation")
        result = self.formatter.format("", ctx)
        assert result == ""

    def test_name(self):
        assert self.formatter.name == "escalation"


# ═══════════════════════════════════════════════════════════════════════
# FORMATTING CONTEXT TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestFormattingContext:
    def test_defaults(self):
        ctx = FormattingContext()
        assert ctx.company_id == ""
        assert ctx.variant_type == "parwa"
        assert ctx.brand_voice == "professional"
        assert ctx.model_tier == "standard"
        assert ctx.customer_tier == "free"
        assert ctx.intent_type == "general"
        assert ctx.sentiment_score == 0.5
        assert ctx.formality_level == "medium"

    def test_normalization(self):
        ctx = FormattingContext(
            variant_type="PARWA_HIGH",
            formality_level="HIGH",
            customer_tier="VIP",
            intent_type="ESCALATION",
        )
        assert ctx.variant_type == "high_parwa"
        assert ctx.formality_level == "high"
        assert ctx.customer_tier == "vip"
        assert ctx.intent_type == "escalation"


# ═══════════════════════════════════════════════════════════════════════
# FORMATTING RESULT TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestFormattingResult:
    def test_defaults(self):
        result = FormattingResult(
            formatted_text="test",
            formatters_applied=["markdown"],
            total_time_ms=1.5,
        )
        assert result.errors == []

    def test_to_dict(self):
        result = FormattingResult(
            formatted_text="hello",
            formatters_applied=["token_limit", "markdown"],
            total_time_ms=2.5,
            errors=["some_error"],
        )
        d = result.to_dict()
        assert d["formatted_text"] == "hello"
        assert len(d["formatters_applied"]) == 2
        assert d["total_time_ms"] == 2.5
        assert len(d["errors"]) == 1


# ═══════════════════════════════════════════════════════════════════════
# FORMATTER REGISTRY TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestFormatterRegistry:
    def setup_method(self):
        self.registry = FormatterRegistry()

    def test_register_and_get(self):
        f = TokenLimitFormatter()
        self.registry.register("token_limit", f)
        assert self.registry.get("token_limit") is f

    def test_get_nonexistent(self):
        assert self.registry.get("nonexistent") is None

    def test_duplicate_registration_ignored(self):
        f1 = TokenLimitFormatter()
        f2 = TokenLimitFormatter()
        self.registry.register("token_limit", f1)
        self.registry.register("token_limit", f2)
        assert self.registry.get("token_limit") is f1

    def test_list_registered(self):
        self.registry.register("a", TokenLimitFormatter())
        self.registry.register("b", MarkdownFormatter())
        assert sorted(self.registry.list_registered()) == ["a", "b"]

    def test_list_registered_empty(self):
        assert self.registry.list_registered() == []

    def test_apply_all_specific_formatters(self):
        self.registry.register("whitespace", WhitespaceFormatter())
        ctx = FormattingContext()
        result = self.registry.apply_all("  hello   \n\n\nworld  ", ctx, ["whitespace"])
        assert result.formatted_text != "  hello   \n\n\nworld  "
        assert "whitespace" in result.formatters_applied

    def test_apply_all_missing_formatter(self):
        ctx = FormattingContext()
        result = self.registry.apply_all("hello", ctx, ["nonexistent"])
        assert result.formatted_text == "hello"
        assert len(result.errors) == 1
        assert "formatter_not_found" in result.errors[0]

    def test_apply_all_none_uses_variant_defaults(self):
        self.registry.register("token_limit", TokenLimitFormatter())
        self.registry.register("markdown", MarkdownFormatter())
        self.registry.register("whitespace", WhitespaceFormatter())
        ctx = FormattingContext(variant_type="mini_parwa")
        result = self.registry.apply_all("hello", ctx)
        assert len(result.formatters_applied) == 3

    def test_get_defaults_for_variant(self):
        defaults = self.registry.get_defaults_for_variant("mini_parwa")
        assert defaults == ["token_limit", "markdown", "whitespace"]

    def test_get_defaults_parwa(self):
        defaults = self.registry.get_defaults_for_variant("parwa")
        assert len(defaults) == 6

    def test_get_defaults_high_parwa(self):
        defaults = self.registry.get_defaults_for_variant("high_parwa")
        assert len(defaults) == 15

    def test_get_defaults_unknown_variant(self):
        defaults = self.registry.get_defaults_for_variant("unknown")
        assert defaults == self.registry.get_defaults_for_variant("parwa")

    def test_apply_all_with_errors(self):
        registry = FormatterRegistry()

        class BrokenFormatter(BaseFormatter):
            @property
            def name(self):
                return "broken"

            def format(self, response, context):
                raise RuntimeError("formatter error")

        registry.register("broken", BrokenFormatter())
        ctx = FormattingContext()
        result = registry.apply_all("hello", ctx, ["broken"])
        assert result.formatted_text == "hello"
        assert len(result.errors) == 1


# ═══════════════════════════════════════════════════════════════════════
# COMPOSABILITY & INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestComposability:
    def test_multiple_formatters_sequential(self):
        """Applying multiple formatters in sequence should work."""
        registry = create_default_registry()
        ctx = FormattingContext()
        text = "  **Hello** **World** **and** **everyone** **else** **too**  \n\n\n\n"
        result = registry.apply_all(text, ctx, ["bold", "whitespace"])
        # Bold formatter removes excessive bold (>5 sections)
        # Whitespace formatter cleans up newlines
        assert "\n\n\n" not in result.formatted_text

    def test_full_mini_parwa_pipeline(self):
        """mini_parwa gets 3 formatters."""
        registry = create_default_registry()
        ctx = FormattingContext(variant_type="mini_parwa")
        result = registry.apply_all(
            "##No space header\n\n- bullet without space\n\nHello   world",
            ctx,
        )
        assert len(result.formatters_applied) == 3
        assert "## No space header" in result.formatted_text

    def test_full_parwa_pipeline(self):
        """parwa gets 6 formatters."""
        registry = create_default_registry()
        ctx = FormattingContext(variant_type="parwa", brand_voice="professional")
        text = "##Header\n- bullet\nResearch [1] and [2] show results."
        result = registry.apply_all(text, ctx)
        assert len(result.formatters_applied) == 6

    def test_full_high_parwa_pipeline(self):
        """high_parwa gets all 15 formatters."""
        registry = create_default_registry()
        ctx = FormattingContext(
            variant_type="high_parwa",
            brand_voice="professional",
            formality_level="high",
            intent_type="general",
        )
        text = (
            "##Header\n- bullet\nResearch [1] and [2] show results. "
            "I want to reset. You should do this."
        )
        result = registry.apply_all(text, ctx)
        assert len(result.formatters_applied) == 15

    def test_formatters_preserve_content(self):
        """Formatters should not lose the core content."""
        registry = create_default_registry()
        ctx = FormattingContext(variant_type="parwa")
        text = "Your refund of $50 has been processed successfully."
        result = registry.apply_all(text, ctx)
        assert "$50" in result.formatted_text
        assert "refund" in result.formatted_text

    def test_empty_response_through_registry(self):
        """Empty response should pass through all formatters."""
        registry = create_default_registry()
        ctx = FormattingContext()
        result = registry.apply_all("", ctx, ["token_limit", "markdown", "whitespace"])
        assert result.formatted_text == ""

    def test_very_long_response(self):
        """Very long response should be handled gracefully."""
        registry = create_default_registry()
        ctx = FormattingContext(variant_type="mini_parwa", model_tier="mini")
        long_text = "word " * 5000
        result = registry.apply_all(long_text, ctx)
        # Token limit should truncate
        assert len(result.formatted_text) < len(long_text)

    def test_special_characters(self):
        """Special characters should not break formatters."""
        registry = create_default_registry()
        ctx = FormattingContext(variant_type="parwa")
        text = "Special chars: @#$%^&*()_+-=[]{}|;:',.<>?/~`"
        result = registry.apply_all(text, ctx)
        assert "@" in result.formatted_text


class TestCreateDefaultRegistry:
    def test_creates_all_15_formatters(self):
        registry = create_default_registry()
        assert len(registry.list_registered()) == 15

    def test_all_names_unique(self):
        registry = create_default_registry()
        names = registry.list_registered()
        assert len(names) == len(set(names))

    def test_all_formatters_gettable(self):
        registry = create_default_registry()
        for name in registry.list_registered():
            assert registry.get(name) is not None


class TestFormattingContextInFormatters:
    """Test that FormattingContext properly affects formatter behavior."""

    def test_model_tier_affects_token_limit(self):
        formatter = TokenLimitFormatter()
        long = "word " * 1000

        mini_ctx = FormattingContext(model_tier="mini")
        standard_ctx = FormattingContext(model_tier="standard")
        high_ctx = FormattingContext(model_tier="high")

        mini_result = formatter.format(long, mini_ctx)
        standard_result = formatter.format(long, standard_ctx)
        high_result = formatter.format(long, high_ctx)

        assert len(mini_result) <= len(standard_result)
        assert len(standard_result) <= len(high_result)

    def test_customer_tier_affects_escalation(self):
        formatter = EscalationFormatter()
        text = "I am very upset."

        free_ctx = FormattingContext(intent_type="escalation", customer_tier="free")
        vip_ctx = FormattingContext(intent_type="escalation", customer_tier="vip")

        free_result = formatter.format(text, free_ctx)
        vip_result = formatter.format(text, vip_ctx)

        assert "CRITICAL" in vip_result
        assert "CRITICAL" not in free_result
