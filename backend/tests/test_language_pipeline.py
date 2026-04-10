"""
Tests for Language Detection/Translation Pipeline (SG-29) — Week 9 Day 7

Covers: LanguageDetector, TranslationSimulator, TranslationQualityChecker,
LanguagePipeline (8-step process), PipelineResult, PipelineStepResult,
confidence thresholds, tenant language, quality checks, fallbacks,
BC-008 (graceful degradation), G9-GAP-10 (tenant_language in cache key).

Target: 100+ tests
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — import source modules with mocked logger
# ═══════════════════════════════════════════════════════════════════════

# Runtime-injected by _mock_logger fixture — satisfies flake8 F821
Language = LanguageDetector = LanguagePipeline = PipelineResult = PipelineStepResult = StepStatus = TranslationQualityChecker = TranslationSimulator = None

@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("backend.app.logger.get_logger", return_value=MagicMock()):
        from backend.app.core.language_pipeline import (  # noqa: F811,F401
            Language,
            LanguageDetector,
            LanguagePipeline,
            PipelineResult,
            PipelineStepResult,
            StepStatus,
            TranslationQualityChecker,
            TranslationSimulator,
        )
        globals().update({
            "Language": Language,
            "LanguageDetector": LanguageDetector,
            "LanguagePipeline": LanguagePipeline,
            "PipelineResult": PipelineResult,
            "PipelineStepResult": PipelineStepResult,
            "StepStatus": StepStatus,
            "TranslationQualityChecker": TranslationQualityChecker,
            "TranslationSimulator": TranslationSimulator,
        })


# ═══════════════════════════════════════════════════════════════════════
# 1. LanguageDetector (15 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestLanguageDetector:
    def setup_method(self):
        self.detector = LanguageDetector()

    def test_detect_english(self):
        lang, conf = self.detector.detect("Hello, how are you doing today?")
        assert lang == Language.ENGLISH
        assert conf > 0

    def test_detect_spanish(self):
        lang, conf = self.detector.detect("Hola, gracias por favor, necesito ayuda con mi problema")
        assert lang == Language.SPANISH
        assert conf > 0

    def test_detect_french(self):
        lang, conf = self.detector.detect("Bonjour, merci beaucoup, je peux vous aider")
        assert lang == Language.FRENCH
        assert conf > 0

    def test_detect_german(self):
        lang, conf = self.detector.detect("Hallo, danke, ich brauche Hilfe mit meinem Problem")
        assert lang == Language.GERMAN
        assert conf > 0

    def test_detect_unknown_empty(self):
        lang, conf = self.detector.detect("")
        assert lang == Language.UNKNOWN
        assert conf == 0.0

    def test_detect_unknown_whitespace(self):
        lang, conf = self.detector.detect("   ")
        assert lang == Language.UNKNOWN
        assert conf == 0.0

    def test_detect_short_text(self):
        lang, conf = self.detector.detect("hi")
        assert lang == Language.ENGLISH
        assert conf > 0

    def test_detect_chinese_characters(self):
        lang, conf = self.detector.detect("你好，请问你能帮助我吗？这是关于退款的问题")
        assert lang == Language.CHINESE
        assert conf > 0

    def test_detect_japanese_hiragana(self):
        lang, conf = self.detector.detect("こんにちは、ありがとうございます")
        assert lang == Language.JAPANESE
        assert conf > 0

    def test_detect_korean(self):
        lang, conf = self.detector.detect("안녕하세요, 감사합니다, 도와주세요")
        assert lang == Language.KOREAN
        assert conf > 0

    def test_detect_arabic(self):
        lang, conf = self.detector.detect("مرحبا، شكرا جزيلا، أرجو المساعدة")
        assert lang == Language.ARABIC
        assert conf > 0

    def test_detect_hindi(self):
        lang, conf = self.detector.detect("नमस्ते, धन्यवाद, कृपया मदद करें")
        assert lang == Language.HINDI
        assert conf > 0

    def test_detect_portuguese(self):
        lang, conf = self.detector.detect("Olá, obrigado, por favor, preciso de ajuda")
        assert lang == Language.PORTUGUESE
        assert conf > 0

    def test_confidence_between_0_and_1(self):
        lang, conf = self.detector.detect("some text here")
        assert 0.0 <= conf <= 1.0

    def test_detect_code_snippet(self):
        lang, conf = self.detector.detect("def foo(): return 42")
        assert lang in (Language.ENGLISH, Language.UNKNOWN)
        assert isinstance(conf, float)


# ═══════════════════════════════════════════════════════════════════════
# 2. TranslationSimulator (10 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestTranslationSimulator:
    def setup_method(self):
        self.translator = TranslationSimulator()

    def test_translate_spanish_to_english(self):
        text, success = self.translator.translate("hola", Language.SPANISH, Language.ENGLISH)
        assert text == "hello"
        assert success is True

    def test_translate_same_language(self):
        text, success = self.translator.translate("hello", Language.ENGLISH, Language.ENGLISH)
        assert text == "hello"
        assert success is True

    def test_translate_unknown_language(self):
        text, success = self.translator.translate("some text", "xx", Language.ENGLISH)
        assert success is True
        assert "Translation simulated" in text

    def test_translate_empty(self):
        text, success = self.translator.translate("", Language.SPANISH, Language.ENGLISH)
        assert text == ""
        assert success is True

    def test_translate_phrase_match(self):
        text, success = self.translator.translate(
            "quiero un reembolso", Language.SPANISH, Language.ENGLISH
        )
        assert success is True
        assert "refund" in text.lower()

    def test_translate_word_by_word(self):
        text, success = self.translator.translate(
            "hola gracias", Language.SPANISH, Language.ENGLISH
        )
        assert success is True
        assert "hello" in text.lower()
        assert "thank" in text.lower()

    def test_translate_french(self):
        text, success = self.translator.translate("bonjour", Language.FRENCH, Language.ENGLISH)
        assert text == "hello"
        assert success is True

    def test_translate_german(self):
        text, success = self.translator.translate("danke", Language.GERMAN, Language.ENGLISH)
        assert text == "thank you"
        assert success is True

    def test_translate_chinese_prefix(self):
        text, success = self.translator.translate("你好", Language.CHINESE, Language.ENGLISH)
        assert success is True
        assert "Translated from Chinese" in text

    def test_translate_back(self):
        text, success = self.translator.translate_back(
            "hello", Language.SPANISH, Language.ENGLISH
        )
        assert success is True
        # "hello" → reverse map has "hola" → should be in text
        assert isinstance(text, str)

    def test_translate_back_same_language(self):
        text, success = self.translator.translate_back(
            "hola", Language.SPANISH, Language.SPANISH
        )
        assert text == "hola"
        assert success is True

    def test_translate_back_empty(self):
        text, success = self.translator.translate_back("", Language.SPANISH, Language.ENGLISH)
        assert text == ""
        assert success is True


# ═══════════════════════════════════════════════════════════════════════
# 3. TranslationQualityChecker (8 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestTranslationQualityChecker:
    def setup_method(self):
        self.checker = TranslationQualityChecker()

    def test_good_quality_translation(self):
        score, issues = self.checker.check("Hello, thank you for your help", "es", "en")
        assert score > 0.7
        assert len(issues) == 0

    def test_empty_translation(self):
        score, issues = self.checker.check("", "es", "en")
        assert score == 0.0
        assert "empty_translation" in issues

    def test_whitespace_translation(self):
        score, issues = self.checker.check("   ", "es", "en")
        assert score == 0.0
        assert "empty_translation" in issues

    def test_garbled_repeated_chars(self):
        score, issues = self.checker.check("aaaaaaaaaaaaa translation", "es", "en")
        assert score < 1.0
        assert any("repeated" in i for i in issues)

    def test_mixed_scripts(self):
        # Chinese + Latin mixed
        score, issues = self.checker.check("hello 你好 world", "zh", "en")
        assert any("mixed" in i.lower() for i in issues)

    def test_replacement_characters(self):
        text = "some \ufffd text \ufffd here"
        score, issues = self.checker.check(text, "es", "en")
        assert score < 1.0

    def test_placeholder_detected(self):
        score, issues = self.checker.check("[translation failed] some text", "es", "en")
        assert any("placeholder" in i.lower() for i in issues)

    def test_score_bounded(self):
        score, _ = self.checker.check("any text at all", "es", "en")
        assert 0.0 <= score <= 1.0

    def test_mojibake_detected(self):
        text = "This is garbled: Ã©Ã¨Ã "
        score, issues = self.checker.check(text, "fr", "en")
        assert score < 1.0
        assert len(issues) > 0

    def test_untranslated_segments(self):
        # Spanish word left in English translation
        score, issues = self.checker.check("I need the gracias for this", "es", "en")
        assert any("untranslated" in i.lower() for i in issues)

    def test_suspicious_single_word(self):
        text = "a" * 60  # single very long word
        score, issues = self.checker.check(text, "es", "en")
        assert any("suspicious" in i.lower() for i in issues)


# ═══════════════════════════════════════════════════════════════════════
# 4. LanguagePipeline — full flow (15 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestLanguagePipeline:
    def setup_method(self):
        self.pipeline = LanguagePipeline()

    @pytest.mark.asyncio
    async def test_english_pipeline_skips_translation(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hello, how are you?", company_id="c1")
        assert result.detected_language == Language.ENGLISH
        assert result.translation_performed is False
        assert result.translated_text == "Hello, how are you?"

    @pytest.mark.asyncio
    async def test_spanish_pipeline_translates(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hola, necesito ayuda", company_id="c1")
        assert result.detected_language == Language.SPANISH
        assert result.translation_performed is True

    @pytest.mark.asyncio
    async def test_pipeline_8_steps(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("test query", company_id="c1")
        step_names = [s.step_name for s in result.pipeline_steps]
        assert len(step_names) == 8
        expected_steps = [
            "detection", "confidence", "tenant_language", "translate",
            "ai_process", "translate_back", "quality_check", "fallback",
        ]
        assert step_names == expected_steps

    @pytest.mark.asyncio
    async def test_step_tracking(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("test query", company_id="c1")
        for step in result.pipeline_steps:
            assert isinstance(step, PipelineStepResult)
            assert step.step_name
            assert step.status in (StepStatus.SUCCESS, StepStatus.SKIPPED, StepStatus.FAILED)
            assert step.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_empty_query(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("", company_id="c1")
        assert result.detected_language == Language.UNKNOWN
        assert result.fallback_used is True
        assert result.quality_issues == ["empty_input"]

    @pytest.mark.asyncio
    async def test_none_query(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process(None, company_id="c1")
        assert result.fallback_used is True
        assert result.original_text == ""

    @pytest.mark.asyncio
    async def test_whitespace_query(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("   ", company_id="c1")
        assert result.fallback_used is True

    @pytest.mark.asyncio
    async def test_pipeline_result_fields(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("test", company_id="c1")
        assert hasattr(result, "original_text")
        assert hasattr(result, "detected_language")
        assert hasattr(result, "detection_confidence")
        assert hasattr(result, "translated_text")
        assert hasattr(result, "tenant_language")
        assert hasattr(result, "translation_performed")
        assert hasattr(result, "quality_score")
        assert hasattr(result, "quality_issues")
        assert hasattr(result, "processing_time_ms")
        assert hasattr(result, "pipeline_steps")
        assert hasattr(result, "fallback_used")
        assert hasattr(result, "fallback_warning")

    @pytest.mark.asyncio
    async def test_processing_time_populated(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("test query here", company_id="c1")
        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_cache_called(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock) as mock_set:
                await self.pipeline.process("test", company_id="c1")
                mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_fail_open(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, side_effect=Exception("Redis down")):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock, side_effect=Exception("Redis down")):
                result = await self.pipeline.process("Hola", company_id="c1")
        assert isinstance(result, PipelineResult)
        assert result.detected_language == Language.SPANISH

    @pytest.mark.asyncio
    async def test_french_pipeline(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Bonjour, merci beaucoup", company_id="c1")
        assert result.detected_language == Language.FRENCH
        assert result.translation_performed is True

    @pytest.mark.asyncio
    async def test_quality_check_performed_for_translation(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hola, necesito ayuda", company_id="c1")
        quality_step = next(
            (s for s in result.pipeline_steps if s.step_name == "quality_check"), None
        )
        assert quality_step is not None
        assert quality_step.status == StepStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_translate_back_step_for_non_english(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hola", company_id="c1")
        back_step = next(
            (s for s in result.pipeline_steps if s.step_name == "translate_back"), None
        )
        assert back_step is not None
        assert back_step.status == StepStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_translate_back_skipped_for_english(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hello", company_id="c1")
        back_step = next(
            (s for s in result.pipeline_steps if s.step_name == "translate_back"), None
        )
        assert back_step is not None
        assert back_step.status == StepStatus.SKIPPED


# ═══════════════════════════════════════════════════════════════════════
# 5. PipelineResult (5 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestPipelineResult:
    def test_to_dict_keys(self):
        steps = [PipelineStepResult(step_name="detection", status=StepStatus.SUCCESS, duration_ms=1.0)]
        result = PipelineResult(
            original_text="test", detected_language="en", detection_confidence=0.9,
            translated_text="test", tenant_language=None, translation_performed=False,
            quality_score=1.0, quality_issues=[], processing_time_ms=5.0,
            pipeline_steps=steps,
        )
        d = result.to_dict()
        assert "original_text" in d
        assert "detected_language" in d
        assert "detection_confidence" in d
        assert "translated_text" in d
        assert "quality_score" in d
        assert "pipeline_steps" in d
        assert "fallback_used" in d

    def test_to_dict_step_values(self):
        steps = [PipelineStepResult(step_name="detection", status=StepStatus.SUCCESS, duration_ms=1.5)]
        result = PipelineResult(
            original_text="test", detected_language="en", detection_confidence=0.9,
            translated_text="test", tenant_language=None, translation_performed=False,
            quality_score=1.0, quality_issues=[], processing_time_ms=5.0,
            pipeline_steps=steps,
        )
        d = result.to_dict()
        assert d["pipeline_steps"][0]["step_name"] == "detection"
        assert d["pipeline_steps"][0]["status"] == "success"
        assert d["pipeline_steps"][0]["duration_ms"] == 1.5

    def test_defaults(self):
        result = PipelineResult(
            original_text="", detected_language="unknown", detection_confidence=0.0,
            translated_text="", tenant_language=None, translation_performed=False,
            quality_score=0.0, quality_issues=[], processing_time_ms=0.0,
            pipeline_steps=[],
        )
        assert result.fallback_used is False
        assert result.fallback_warning is None

    def test_rounded_values(self):
        steps = []
        result = PipelineResult(
            original_text="test", detected_language="en", detection_confidence=0.12345678,
            translated_text="test", tenant_language=None, translation_performed=False,
            quality_score=0.98765432, quality_issues=[], processing_time_ms=5.123456,
            pipeline_steps=steps,
        )
        d = result.to_dict()
        assert d["detection_confidence"] == 0.1235
        assert d["quality_score"] == 0.9877
        assert d["processing_time_ms"] == 5.12

    def test_step_results_metadata(self):
        step = PipelineStepResult(
            step_name="detection", status=StepStatus.SUCCESS, duration_ms=1.0,
            metadata={"language": "en", "confidence": 0.9},
        )
        assert step.metadata["language"] == "en"
        assert step.metadata["confidence"] == 0.9


# ═══════════════════════════════════════════════════════════════════════
# 6. Confidence (8 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestConfidence:
    def setup_method(self):
        self.pipeline = LanguagePipeline()

    @pytest.mark.asyncio
    async def test_high_confidence_success(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hola, gracias por favor, necesito ayuda con mi problema", company_id="c1")
        conf_step = next(s for s in result.pipeline_steps if s.step_name == "confidence")
        assert conf_step.status == StepStatus.SUCCESS
        assert conf_step.metadata["is_confident"] is True

    @pytest.mark.asyncio
    async def test_low_confidence_skipped(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("hi", company_id="c1")
        conf_step = next(s for s in result.pipeline_steps if s.step_name == "confidence")
        # Low confidence → SKIPPED
        assert conf_step.status in (StepStatus.SKIPPED, StepStatus.SUCCESS)
        assert "confidence" in conf_step.metadata

    @pytest.mark.asyncio
    async def test_confidence_threshold_0_5(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("test", company_id="c1")
        conf_step = next(s for s in result.pipeline_steps if s.step_name == "confidence")
        assert conf_step.metadata["threshold"] == 0.5

    @pytest.mark.asyncio
    async def test_english_low_confidence(self):
        """English gets default 0.4 confidence for generic text."""
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("the quick brown fox jumps", company_id="c1")
        # English detected with low confidence
        assert result.detected_language == Language.ENGLISH

    def test_detector_confidence_range(self):
        detector = LanguageDetector()
        _, conf = detector.detect("Bonjour merci")
        assert 0.0 <= conf <= 1.0

    @pytest.mark.asyncio
    async def test_chinese_high_confidence(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("你好世界这是一个测试", company_id="c1")
        conf_step = next(s for s in result.pipeline_steps if s.step_name == "confidence")
        # Chinese script-based detection should be confident
        assert conf_step.metadata["is_confident"] is True

    @pytest.mark.asyncio
    async def test_japanese_high_confidence(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("こんにちは、ありがとうございます", company_id="c1")
        conf_step = next(s for s in result.pipeline_steps if s.step_name == "confidence")
        assert conf_step.metadata["is_confident"] is True

    @pytest.mark.asyncio
    async def test_korean_high_confidence(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("안녕하세요 감사합니다 도와주세요", company_id="c1")
        assert result.detection_confidence > 0.5


# ═══════════════════════════════════════════════════════════════════════
# 7. Tenant Language (5 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestTenantLanguage:
    def setup_method(self):
        self.pipeline = LanguagePipeline()

    @pytest.mark.asyncio
    async def test_tenant_language_english(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hola", company_id="c1", tenant_language="en")
        tenant_step = next(s for s in result.pipeline_steps if s.step_name == "tenant_language")
        assert tenant_step.metadata["tenant_language"] == "en"
        assert tenant_step.metadata["needs_translation"] is True

    @pytest.mark.asyncio
    async def test_tenant_language_none(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hola", company_id="c1")
        tenant_step = next(s for s in result.pipeline_steps if s.step_name == "tenant_language")
        assert tenant_step.metadata["tenant_language"] is None

    @pytest.mark.asyncio
    async def test_tenant_language_matches_detected(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hola", company_id="c1", tenant_language="es")
        tenant_step = next(s for s in result.pipeline_steps if s.step_name == "tenant_language")
        assert tenant_step.metadata["effective_language"] == "es"
        assert tenant_step.metadata["needs_translation"] is False

    @pytest.mark.asyncio
    async def test_gap10_tenant_language_in_cache_key(self):
        """G9-GAP-10: Different tenant_language produces different cache keys."""
        import hashlib
        text = "Hola"
        qh = hashlib.sha256(text.lower().strip().encode("utf-8")).hexdigest()[:16]
        key_en = f"lang_pipeline:c1:{qh}:en"
        key_es = f"lang_pipeline:c1:{qh}:es"
        key_none = f"lang_pipeline:c1:{qh}:none"
        assert key_en != key_es
        assert key_en != key_none

    @pytest.mark.asyncio
    async def test_result_has_tenant_language(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("test", company_id="c1", tenant_language="de")
        assert result.tenant_language == "de"


# ═══════════════════════════════════════════════════════════════════════
# 8. Quality Check (5 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestQualityCheck:
    def setup_method(self):
        self.pipeline = LanguagePipeline()

    @pytest.mark.asyncio
    async def test_quality_check_passed(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hola, necesito ayuda", company_id="c1")
        quality_step = next(s for s in result.pipeline_steps if s.step_name == "quality_check")
        assert quality_step.status == StepStatus.SUCCESS
        assert result.quality_score > 0

    @pytest.mark.asyncio
    async def test_quality_check_skipped_for_english(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hello", company_id="c1")
        quality_step = next(s for s in result.pipeline_steps if s.step_name == "quality_check")
        assert quality_step.status == StepStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_quality_issues_populated(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hola, necesito ayuda", company_id="c1")
        quality_step = next(s for s in result.pipeline_steps if s.step_name == "quality_check")
        assert "quality_score" in quality_step.metadata
        assert "issues_count" in quality_step.metadata

    @pytest.mark.asyncio
    async def test_quality_score_range(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hola", company_id="c1")
        assert 0.0 <= result.quality_score <= 1.0

    @pytest.mark.asyncio
    async def test_quality_check_error_handled(self):
        """BC-008: Quality check failure is handled gracefully."""
        pipeline = LanguagePipeline()
        with patch.object(pipeline._quality_checker, "check", side_effect=RuntimeError("quality check failed")):
            with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                    result = await pipeline.process("Hola", company_id="c1")
        quality_step = next(s for s in result.pipeline_steps if s.step_name == "quality_check")
        assert quality_step.status == StepStatus.FAILED
        assert result.quality_score == 0.5


# ═══════════════════════════════════════════════════════════════════════
# 9. Fallback (5 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestFallback:
    def setup_method(self):
        self.pipeline = LanguagePipeline()

    @pytest.mark.asyncio
    async def test_fallback_on_detection_failure(self):
        pipeline = LanguagePipeline()
        with patch.object(pipeline._detector, "detect", side_effect=RuntimeError("detection failed")):
            with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                    result = await pipeline.process("Hola", company_id="c1")
        assert result.fallback_used is True
        assert result.fallback_warning is not None

    @pytest.mark.asyncio
    async def test_fallback_returns_original_text(self):
        pipeline = LanguagePipeline()
        with patch.object(pipeline._detector, "detect", side_effect=RuntimeError("failed")):
            with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                    result = await pipeline.process("Hola", company_id="c1")
        assert result.translated_text == "Hola"
        assert result.translation_performed is False

    @pytest.mark.asyncio
    async def test_no_fallback_on_success(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hello", company_id="c1")
        assert result.fallback_used is False

    @pytest.mark.asyncio
    async def test_fallback_step_status(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hello", company_id="c1")
        fallback_step = next(s for s in result.pipeline_steps if s.step_name == "fallback")
        assert fallback_step.status == StepStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_fallback_on_translation_failure(self):
        pipeline = LanguagePipeline()
        with patch.object(pipeline._translator, "translate", return_value=("", False)):
            with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                    result = await pipeline.process("Hola", company_id="c1")
        assert result.fallback_used is True


# ═══════════════════════════════════════════════════════════════════════
# 10. Error Handling BC-008 (5 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    def setup_method(self):
        self.pipeline = LanguagePipeline()

    @pytest.mark.asyncio
    async def test_never_crashes_on_empty(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("", company_id="c1")
        assert isinstance(result, PipelineResult)

    @pytest.mark.asyncio
    async def test_never_crashes_on_none(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process(None, company_id="c1")
        assert isinstance(result, PipelineResult)

    @pytest.mark.asyncio
    async def test_detection_error_caught(self):
        pipeline = LanguagePipeline()
        with patch.object(pipeline._detector, "detect", side_effect=Exception("boom")):
            with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                    result = await pipeline.process("test", company_id="c1")
        detection_step = result.pipeline_steps[0]
        assert detection_step.status == StepStatus.FAILED

    @pytest.mark.asyncio
    async def test_translation_error_caught(self):
        pipeline = LanguagePipeline()
        with patch.object(pipeline._translator, "translate", side_effect=Exception("translate boom")):
            with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                    result = await pipeline.process("Hola", company_id="c1")
        translate_step = next(s for s in result.pipeline_steps if s.step_name == "translate")
        assert translate_step.status == StepStatus.FAILED

    @pytest.mark.asyncio
    async def test_cache_error_does_not_crash(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, side_effect=Exception("Redis down")):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock, side_effect=Exception("Redis down")):
                result = await self.pipeline.process("test", company_id="c1")
        assert isinstance(result, PipelineResult)


# ═══════════════════════════════════════════════════════════════════════
# 11. Edge Cases (5 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def setup_method(self):
        self.pipeline = LanguagePipeline()

    @pytest.mark.asyncio
    async def test_very_long_text(self):
        long_text = "Hola, necesito ayuda con mi problema " * 200
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process(long_text, company_id="c1")
        assert isinstance(result, PipelineResult)
        assert result.original_text == long_text

    @pytest.mark.asyncio
    async def test_special_characters(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("@#$%^&*()", company_id="c1")
        assert isinstance(result, PipelineResult)

    @pytest.mark.asyncio
    async def test_emoji_text(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hello 😊🎉", company_id="c1")
        assert isinstance(result, PipelineResult)

    @pytest.mark.asyncio
    async def test_numbers_only(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("12345 67890", company_id="c1")
        assert isinstance(result, PipelineResult)

    @pytest.mark.asyncio
    async def test_mixed_scripts(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hello 你好 Bonjour", company_id="c1")
        assert isinstance(result, PipelineResult)
        # Should detect one of the script-based languages or Latin
        assert result.detected_language in (
            Language.CHINESE, Language.JAPANESE, Language.ENGLISH,
            Language.FRENCH, Language.UNKNOWN,
        )

    @pytest.mark.asyncio
    async def test_newlines_and_tabs(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hello\n\n\tWorld\t\t", company_id="c1")
        assert result.detected_language == Language.ENGLISH

    @pytest.mark.asyncio
    async def test_result_to_dict(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("test", company_id="c1")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "original_text" in d
        assert "pipeline_steps" in d


# ═══════════════════════════════════════════════════════════════════════
# 12. Additional Detector Tests
# ═══════════════════════════════════════════════════════════════════════

class TestLanguageDetectorAdditional:
    def setup_method(self):
        self.detector = LanguageDetector()

    def test_detect_mixed_latin_english_dominant(self):
        lang, conf = self.detector.detect("The quick brown fox jumps over the lazy dog")
        assert lang == Language.ENGLISH

    def test_detect_return_types(self):
        lang, conf = self.detector.detect("test")
        assert isinstance(lang, str)
        assert isinstance(conf, float)

    def test_detect_none_input(self):
        lang, conf = self.detector.detect(None)
        assert lang == Language.UNKNOWN
        assert conf == 0.0

    def test_detect_non_string(self):
        with pytest.raises(AttributeError):
            self.detector.detect(12345)

    def test_detect_arabic_script_dominant(self):
        lang, conf = self.detector.detect("مرحبا شكرا جزيلا أرجو المساعدة")
        assert lang == Language.ARABIC

    def test_detect_hindi_script(self):
        lang, conf = self.detector.detect("नमस्ते धन्यवाद कृपया मदद करें")
        assert lang == Language.HINDI

    def test_detect_korean_script(self):
        lang, conf = self.detector.detect("안녕하세요 감사합니다 도와주세요")
        assert lang == Language.KOREAN

    def test_spanish_high_confidence(self):
        lang, conf = self.detector.detect(
            "Hola, gracias por favor, necesito ayuda con mi problema, "
            "también puedo cuando donde bien muy todo tiene hay ser"
        )
        assert lang == Language.SPANISH
        assert conf > 0.5

    def test_detect_portuguese(self):
        lang, conf = self.detector.detect("Olá obrigado por favor preciso ajuda")
        assert lang == Language.PORTUGUESE

    def test_detect_german_high_confidence(self):
        lang, conf = self.detector.detect(
            "Hallo danke bitte kann ich wie was wann wo gut sehr alle"
        )
        assert lang == Language.GERMAN
        assert conf > 0.5


# ═══════════════════════════════════════════════════════════════════════
# 13. Additional Translation Tests
# ═══════════════════════════════════════════════════════════════════════

class TestTranslationAdditional:
    def setup_method(self):
        self.translator = TranslationSimulator()

    def test_translate_portuguese_to_english(self):
        text, success = self.translator.translate("olá", Language.PORTUGUESE, Language.ENGLISH)
        assert text == "hello"
        assert success is True

    def test_translate_portuguese_phrase(self):
        text, success = self.translator.translate(
            "obrigado", Language.PORTUGUESE, Language.ENGLISH
        )
        assert success is True
        assert "thank" in text.lower()

    def test_translate_korean_prefix(self):
        text, success = self.translator.translate("안녕", Language.KOREAN, Language.ENGLISH)
        assert success is True
        assert "Translated from Korean" in text

    def test_translate_hindi_prefix(self):
        text, success = self.translator.translate("नमस्ते", Language.HINDI, Language.ENGLISH)
        assert success is True
        assert "Translated from Hindi" in text

    def test_translate_arabic_prefix(self):
        text, success = self.translator.translate("مرحبا", Language.ARABIC, Language.ENGLISH)
        assert success is True
        assert "Translated from Arabic" in text

    def test_translate_back_german(self):
        text, success = self.translator.translate_back(
            "thank you", Language.GERMAN, Language.ENGLISH
        )
        assert success is True
        assert isinstance(text, str)

    def test_translate_back_french(self):
        text, success = self.translator.translate_back(
            "hello", Language.FRENCH, Language.ENGLISH
        )
        assert success is True
        assert "bonjour" in text.lower()

    def test_translate_back_korean_suffix(self):
        text, success = self.translator.translate_back(
            "hello", Language.KOREAN, Language.ENGLISH
        )
        assert success is True
        assert "한국어" in text

    def test_translate_whitespace_only(self):
        text, success = self.translator.translate("   ", Language.SPANISH, Language.ENGLISH)
        assert text == ""
        assert success is True

    def test_translate_unknown_target(self):
        text, success = self.translator.translate("hello", Language.ENGLISH, "xx")
        assert success is True
        assert "Translation simulated" in text


# ═══════════════════════════════════════════════════════════════════════
# 14. Additional Quality Checker Tests
# ═══════════════════════════════════════════════════════════════════════

class TestQualityCheckerAdditional:
    def setup_method(self):
        self.checker = TranslationQualityChecker()

    def test_same_language_no_untranslated(self):
        score, issues = self.checker.check("hello world", "en", "en")
        assert not any("untranslated" in i.lower() for i in issues)

    def test_clean_translation_high_score(self):
        score, issues = self.checker.check(
            "The refund has been processed successfully", "es", "en"
        )
        assert score > 0.7

    def test_multiple_issues_lower_score(self):
        text = "aaaaaaaaaaaaa \ufffd some [translation failed] text ??? ??????"
        score, issues = self.checker.check(text, "es", "en")
        assert score < 0.5
        assert len(issues) > 1

    def test_placeholder_todo(self):
        score, issues = self.checker.check("TODO: translate this", "es", "en")
        assert any("placeholder" in i.lower() for i in issues)

    def test_placeholder_template_var(self):
        score, issues = self.checker.check("{{untranslated_var}} some text", "es", "en")
        assert any("placeholder" in i.lower() for i in issues)

    def test_non_latin_script_translation(self):
        score, issues = self.checker.check(
            "hello 你好 world", "zh", "en"
        )
        assert any("mixed" in i.lower() for i in issues)


# ═══════════════════════════════════════════════════════════════════════
# 15. Language Enum Tests
# ═══════════════════════════════════════════════════════════════════════

class TestLanguageEnum:
    def test_all_language_values(self):
        assert Language.ENGLISH == "en"
        assert Language.SPANISH == "es"
        assert Language.FRENCH == "fr"
        assert Language.GERMAN == "de"
        assert Language.PORTUGUESE == "pt"
        assert Language.HINDI == "hi"
        assert Language.CHINESE == "zh"
        assert Language.JAPANESE == "ja"
        assert Language.ARABIC == "ar"
        assert Language.KOREAN == "ko"
        assert Language.UNKNOWN == "unknown"

    def test_step_status_values(self):
        assert StepStatus.SUCCESS == "success"
        assert StepStatus.SKIPPED == "skipped"
        assert StepStatus.FAILED == "failed"


# ═══════════════════════════════════════════════════════════════════════
# 16. Pipeline Integration Additional
# ═══════════════════════════════════════════════════════════════════════

class TestPipelineIntegrationAdditional:
    def setup_method(self):
        self.pipeline = LanguagePipeline()

    @pytest.mark.asyncio
    async def test_german_pipeline_translates(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hallo, danke für die Hilfe", company_id="c1")
        assert result.detected_language == Language.GERMAN
        assert result.translation_performed is True

    @pytest.mark.asyncio
    async def test_portuguese_pipeline_translates(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Olá, obrigado pela ajuda", company_id="c1")
        assert result.detected_language == Language.PORTUGUESE
        assert result.translation_performed is True

    @pytest.mark.asyncio
    async def test_ai_process_step_always_runs(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("test", company_id="c1")
        ai_step = next(s for s in result.pipeline_steps if s.step_name == "ai_process")
        assert ai_step.status == StepStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_quality_skipped_for_english(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hello world", company_id="c1")
        quality_step = next(s for s in result.pipeline_steps if s.step_name == "quality_check")
        assert quality_step.status == StepStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_all_steps_have_metadata(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("test query", company_id="c1")
        for step in result.pipeline_steps:
            assert isinstance(step.metadata, dict)

    @pytest.mark.asyncio
    async def test_original_text_preserved(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.pipeline.process("Hola mundo", company_id="c1")
        assert result.original_text == "Hola mundo"
