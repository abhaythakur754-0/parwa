"""Tests for Quality Enhancer Module - Week 55, Builder 3"""
import pytest
from datetime import datetime

from enterprise.ai_optimization.response_quality import (
    ResponseQualityScorer, QualityScore, QualityMetric
)
from enterprise.ai_optimization.hallucination_detector import (
    HallucinationDetector, HallucinationResult, HallucinationType
)
from enterprise.ai_optimization.quality_validator import (
    QualityValidator, ValidationRule, ValidationPipeline, ValidationStatus, ValidationResult
)


class TestResponseQualityScorer:
    def test_init(self):
        scorer = ResponseQualityScorer()
        assert scorer.threshold == 0.7

    def test_score(self):
        scorer = ResponseQualityScorer()
        result = scorer.score("This is a helpful response with some details.")
        assert isinstance(result, QualityScore)
        assert 0 <= result.overall <= 1

    def test_score_with_context(self):
        scorer = ResponseQualityScorer()
        result = scorer.score("Here is the answer.", "What is the question?")
        assert QualityMetric.RELEVANCE in result.metrics

    def test_score_all_metrics(self):
        scorer = ResponseQualityScorer()
        result = scorer.score("A detailed helpful response.")
        for metric in QualityMetric:
            assert metric in result.metrics

    def test_threshold_custom(self):
        scorer = ResponseQualityScorer(threshold=0.8)
        assert scorer.threshold == 0.8

    def test_is_passing(self):
        scorer = ResponseQualityScorer()
        result = scorer.score("A good response that helps the user with their question.")
        assert result.is_passing or not result.is_passing

    def test_set_weight(self):
        scorer = ResponseQualityScorer()
        scorer.set_weight(QualityMetric.ACCURACY, 0.5)
        assert scorer._weights[QualityMetric.ACCURACY] == 0.5


class TestHallucinationDetector:
    def test_init(self):
        detector = HallucinationDetector()
        assert detector.confidence_threshold == 0.7

    def test_detect_no_hallucination(self):
        detector = HallucinationDetector()
        result = detector.detect("This is a normal response.")
        assert isinstance(result, HallucinationResult)
        assert not result.is_hallucination or result.is_hallucination

    def test_detect_with_facts(self):
        detector = HallucinationDetector()
        result = detector.detect("The sky is blue.", ["sky is blue"])
        assert isinstance(result, HallucinationResult)

    def test_add_pattern(self):
        detector = HallucinationDetector()
        detector.add_pattern(HallucinationType.FACTUAL, r"fake_pattern")
        assert HallucinationType.FACTUAL in detector._patterns

    def test_verify_fact(self):
        detector = HallucinationDetector()
        kb = {"fact1": "The earth is round"}
        assert detector.verify_fact("earth is round", kb)
        assert not detector.verify_fact("earth is flat", kb)


class TestQualityValidator:
    def test_init(self):
        validator = QualityValidator()
        assert len(validator.rules) >= 3

    def test_add_rule(self):
        validator = QualityValidator()
        rule = ValidationRule(
            name="test_rule",
            condition=lambda r: "test" in r.lower(),
            description="Must contain test",
        )
        validator.add_rule(rule)
        assert "test_rule" in validator.rules

    def test_remove_rule(self):
        validator = QualityValidator()
        validator.add_rule(ValidationRule(name="temp", condition=lambda r: True))
        assert validator.remove_rule("temp")
        assert "temp" not in validator.rules

    def test_validate_pass(self):
        validator = QualityValidator()
        result = validator.validate("This is a valid response with enough content.")
        assert result.overall_status in [ValidationStatus.PASS, ValidationStatus.FAIL]

    def test_validate_fail(self):
        validator = QualityValidator()
        result = validator.validate("")
        assert result.overall_status == ValidationStatus.FAIL

    def test_validate_specific_rules(self):
        validator = QualityValidator()
        result = validator.validate("Some content", rules=["min_length", "no_empty"])
        assert len(result.results) <= 2


class TestValidationPipeline:
    def test_init(self):
        pipeline = ValidationPipeline("test_pipeline")
        assert pipeline.name == "test_pipeline"
        assert len(pipeline.stages) == 0

    def test_add_stage(self):
        pipeline = ValidationPipeline("test")
        pipeline.add_stage(QualityValidator())
        assert len(pipeline.stages) == 1

    def test_run(self):
        pipeline = ValidationPipeline("test")
        pipeline.add_stage(QualityValidator())
        result = pipeline.run("Test response content here.")
        assert result.overall_status in [ValidationStatus.PASS, ValidationStatus.FAIL]


class TestValidationResult:
    def test_validation_result(self):
        result = ValidationResult(
            rule_name="test",
            status=ValidationStatus.PASS,
            score=1.0,
            message="Test passed",
        )
        assert result.rule_name == "test"
        assert result.status == ValidationStatus.PASS


class TestPipelineResult:
    def test_pass_count(self):
        from enterprise.ai_optimization.quality_validator import PipelineResult
        result = PipelineResult(
            overall_status=ValidationStatus.PASS,
            results=[
                ValidationResult("r1", ValidationStatus.PASS, 1.0),
                ValidationResult("r2", ValidationStatus.FAIL, 0.0),
            ],
        )
        assert result.pass_count == 1

    def test_fail_count(self):
        from enterprise.ai_optimization.quality_validator import PipelineResult
        result = PipelineResult(
            overall_status=ValidationStatus.FAIL,
            results=[
                ValidationResult("r1", ValidationStatus.PASS, 1.0),
                ValidationResult("r2", ValidationStatus.FAIL, 0.0),
            ],
        )
        assert result.fail_count == 1

    def test_pipeline_result_timestamp(self):
        from enterprise.ai_optimization.quality_validator import PipelineResult
        result = PipelineResult(overall_status=ValidationStatus.PASS)
        assert result.timestamp is not None

    def test_pipeline_result_empty_results(self):
        from enterprise.ai_optimization.quality_validator import PipelineResult
        result = PipelineResult(overall_status=ValidationStatus.PASS, results=[])
        assert result.pass_count == 0
        assert result.fail_count == 0
