"""
Comprehensive tests for Quality Enhancer modules (Week 55 Builder 3)

Tests cover:
- response_quality.py (ResponseQualityScorer, QualityMetric, QualityScore)
- hallucination_detector.py (HallucinationDetector, HallucinationType, HallucinationResult)
- quality_validator.py (QualityValidator, ValidationRule, ValidationPipeline)
"""

import pytest
from datetime import datetime
from typing import Dict, List

# Import from response_quality module
from enterprise.ai_optimization.response_quality import (
    QualityMetric,
    QualityLevel,
    QualityScore,
    ScoringThreshold,
    ResponseQualityScorer,
)

# Import from hallucination_detector module
from enterprise.ai_optimization.hallucination_detector import (
    HallucinationType,
    HallucinationSeverity,
    Evidence,
    HallucinationResult,
    FactCheckResult,
    FactChecker,
    HallucinationDetector,
)

# Import from quality_validator module
from enterprise.ai_optimization.quality_validator import (
    ValidationStatus,
    ValidationStage,
    ValidationSeverity,
    ValidationCondition,
    ValidationRule,
    RuleResult,
    StageResult,
    ValidationResult,
    ValidationPipeline,
    QualityValidator,
    create_simple_validator,
)


# =============================================================================
# Tests for QualityMetric Enum
# =============================================================================

class TestQualityMetric:
    """Tests for QualityMetric enum."""
    
    def test_quality_metric_values(self):
        """Test that all expected quality metrics exist."""
        assert QualityMetric.RELEVANCE.value == "relevance"
        assert QualityMetric.COHERENCE.value == "coherence"
        assert QualityMetric.ACCURACY.value == "accuracy"
        assert QualityMetric.HELPFULNESS.value == "helpfulness"
    
    def test_quality_metric_count(self):
        """Test that there are exactly 4 quality metrics."""
        assert len(QualityMetric) == 4


# =============================================================================
# Tests for QualityScore
# =============================================================================

class TestQualityScore:
    """Tests for QualityScore dataclass."""
    
    def test_quality_score_creation(self):
        """Test creating a quality score."""
        score = QualityScore(
            overall=75.0,
            per_metric={QualityMetric.RELEVANCE: 80.0, QualityMetric.COHERENCE: 70.0},
            metadata={"test": "value"}
        )
        assert score.overall == 75.0
        assert score.level == QualityLevel.GOOD
        assert len(score.per_metric) == 2
    
    def test_quality_score_level_assignment(self):
        """Test automatic level assignment based on score."""
        levels = [
            (95.0, QualityLevel.EXCELLENT),
            (75.0, QualityLevel.GOOD),
            (55.0, QualityLevel.ACCEPTABLE),
            (35.0, QualityLevel.POOR),
            (15.0, QualityLevel.UNACCEPTABLE),
        ]
        for overall, expected_level in levels:
            score = QualityScore(overall=overall)
            assert score.level == expected_level, f"Score {overall} should be {expected_level}"
    
    def test_quality_score_to_dict(self):
        """Test converting quality score to dictionary."""
        score = QualityScore(
            overall=80.0,
            per_metric={QualityMetric.RELEVANCE: 85.0},
            metadata={"key": "value"}
        )
        result = score.to_dict()
        assert result["overall"] == 80.0
        assert "relevance" in result["per_metric"]
        assert result["level"] == "good"
    
    def test_quality_score_is_passing(self):
        """Test is_passing method with different thresholds."""
        score = QualityScore(overall=60.0)
        assert score.is_passing(50.0) is True
        assert score.is_passing(70.0) is False


# =============================================================================
# Tests for ScoringThreshold
# =============================================================================

class TestScoringThreshold:
    """Tests for ScoringThreshold dataclass."""
    
    def test_default_threshold(self):
        """Test default threshold values."""
        threshold = ScoringThreshold()
        assert threshold.minimum_score == 50.0
        assert threshold.excellent_threshold == 90.0
        assert threshold.good_threshold == 70.0
    
    def test_metric_weights_sum_to_one(self):
        """Test that default metric weights sum to 1.0."""
        threshold = ScoringThreshold()
        assert threshold.validate() is True
    
    def test_get_weight(self):
        """Test getting weight for specific metric."""
        threshold = ScoringThreshold()
        weight = threshold.get_weight(QualityMetric.RELEVANCE)
        assert weight == 0.25
    
    def test_custom_weights(self):
        """Test custom metric weights."""
        threshold = ScoringThreshold(
            metric_weights={
                QualityMetric.RELEVANCE: 0.4,
                QualityMetric.COHERENCE: 0.3,
                QualityMetric.ACCURACY: 0.2,
                QualityMetric.HELPFULNESS: 0.1,
            }
        )
        assert threshold.validate() is True
        assert threshold.get_weight(QualityMetric.RELEVANCE) == 0.4


# =============================================================================
# Tests for ResponseQualityScorer
# =============================================================================

class TestResponseQualityScorer:
    """Tests for ResponseQualityScorer class."""
    
    def test_scorer_initialization(self):
        """Test scorer initialization."""
        scorer = ResponseQualityScorer()
        assert scorer.threshold is not None
    
    def test_score_response(self):
        """Test scoring a basic response."""
        scorer = ResponseQualityScorer()
        response = "This is a helpful response that addresses the user's question. It provides clear and accurate information."
        score = scorer.score(response)
        assert score.overall >= 0
        assert len(score.per_metric) == 4
    
    def test_score_empty_response(self):
        """Test scoring an empty response."""
        scorer = ResponseQualityScorer()
        score = scorer.score("")
        assert score.overall == 0.0
    
    def test_score_with_context(self):
        """Test scoring with context for relevance."""
        scorer = ResponseQualityScorer()
        context = "What is machine learning?"
        response = "Machine learning is a subset of artificial intelligence that enables systems to learn from data."
        score = scorer.score(response, context=context)
        assert QualityMetric.RELEVANCE in score.per_metric
    
    def test_score_with_expected_facts(self):
        """Test scoring with expected facts for accuracy."""
        scorer = ResponseQualityScorer()
        response = "Paris is the capital of France."
        expected_facts = ["Paris is the capital of France"]
        score = scorer.score(response, expected_facts=expected_facts)
        assert QualityMetric.ACCURACY in score.per_metric
    
    def test_batch_score(self):
        """Test batch scoring."""
        scorer = ResponseQualityScorer()
        responses = [
            "First response with some content.",
            "Second response with different content.",
        ]
        scores = scorer.batch_score(responses)
        assert len(scores) == 2
    
    def test_get_statistics(self):
        """Test getting scorer statistics."""
        scorer = ResponseQualityScorer()
        scorer.score("Test response one.")
        scorer.score("Test response two.")
        stats = scorer.get_statistics()
        assert stats["total_scores"] == 2
        assert "average_score" in stats


# =============================================================================
# Tests for HallucinationType Enum
# =============================================================================

class TestHallucinationType:
    """Tests for HallucinationType enum."""
    
    def test_hallucination_type_values(self):
        """Test hallucination type values."""
        assert HallucinationType.FACTUAL.value == "factual"
        assert HallucinationType.LOGICAL.value == "logical"
        assert HallucinationType.INCONSISTENCY.value == "inconsistency"
    
    def test_hallucination_type_count(self):
        """Test that there are exactly 3 hallucination types."""
        assert len(HallucinationType) == 3


# =============================================================================
# Tests for Evidence
# =============================================================================

class TestEvidence:
    """Tests for Evidence dataclass."""
    
    def test_evidence_creation(self):
        """Test creating evidence."""
        evidence = Evidence(
            claim="Test claim",
            evidence_type="contradicting",
            source="test_source",
            confidence=0.8,
            details="Test details"
        )
        assert evidence.claim == "Test claim"
        assert evidence.confidence == 0.8
    
    def test_evidence_to_dict(self):
        """Test converting evidence to dictionary."""
        evidence = Evidence(
            claim="Test",
            evidence_type="supporting",
            source="test"
        )
        result = evidence.to_dict()
        assert result["claim"] == "Test"
        assert result["evidence_type"] == "supporting"


# =============================================================================
# Tests for HallucinationResult
# =============================================================================

class TestHallucinationResult:
    """Tests for HallucinationResult dataclass."""
    
    def test_result_creation(self):
        """Test creating a hallucination result."""
        result = HallucinationResult(
            is_hallucination=True,
            hallucination_type=HallucinationType.FACTUAL,
            confidence=0.9,
            severity=HallucinationSeverity.HIGH
        )
        assert result.is_hallucination is True
        assert result.hallucination_type == HallucinationType.FACTUAL
    
    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = HallucinationResult(
            is_hallucination=True,
            hallucination_type=HallucinationType.LOGICAL,
            confidence=0.7
        )
        d = result.to_dict()
        assert d["is_hallucination"] is True
        assert d["hallucination_type"] == "logical"
    
    def test_add_evidence(self):
        """Test adding evidence to result."""
        result = HallucinationResult(is_hallucination=True)
        evidence = Evidence(claim="Test", evidence_type="supporting", source="test")
        result.add_evidence(evidence)
        assert len(result.evidence) == 1


# =============================================================================
# Tests for FactChecker
# =============================================================================

class TestFactChecker:
    """Tests for FactChecker class."""
    
    def test_fact_checker_initialization(self):
        """Test fact checker initialization."""
        checker = FactChecker()
        stats = checker.get_statistics()
        assert "known_facts" in stats
    
    def test_check_known_true_fact(self):
        """Test checking a known true fact."""
        checker = FactChecker()
        result = checker.check_fact("The Earth is round")
        assert result.is_verified is True
    
    def test_check_known_false_fact(self):
        """Test checking a known false fact."""
        checker = FactChecker()
        result = checker.check_fact("The Earth is flat")
        assert result.is_verified is False
    
    def test_check_unknown_fact(self):
        """Test checking an unknown fact."""
        checker = FactChecker()
        result = checker.check_fact("Some random unknown claim xyz123")
        assert result.confidence == 0.5  # Default for unknown
    
    def test_add_known_fact(self):
        """Test adding a new known fact."""
        checker = FactChecker()
        checker.add_known_fact("Custom fact for testing", True)
        result = checker.check_fact("Custom fact for testing")
        assert result.is_verified is True


# =============================================================================
# Tests for HallucinationDetector
# =============================================================================

class TestHallucinationDetector:
    """Tests for HallucinationDetector class."""
    
    def test_detector_initialization(self):
        """Test detector initialization."""
        detector = HallucinationDetector()
        assert detector.fact_checker is not None
    
    def test_detect_empty_response(self):
        """Test detecting hallucinations in empty response."""
        detector = HallucinationDetector()
        results = detector.detect("")
        assert results == []
    
    def test_detect_factual_hallucination(self):
        """Test detecting factual hallucinations."""
        detector = HallucinationDetector()
        # Use a claim that directly matches the known false fact
        response = "The earth is flat."
        results = detector.detect(response, detection_types=[HallucinationType.FACTUAL])
        assert len(results) > 0
    
    def test_detect_with_known_facts(self):
        """Test detection with provided known facts."""
        detector = HallucinationDetector()
        response = "Paris is the capital of Germany."
        known_facts = {"paris is the capital of france": True}
        results = detector.detect(response, known_facts=known_facts)
        assert isinstance(results, list)
    
    def test_detect_all_types(self):
        """Test detecting all hallucination types."""
        detector = HallucinationDetector()
        response = "All programmers never make mistakes. All code is always perfect."
        results = detector.detect(response)
        assert isinstance(results, list)
    
    def test_get_hallucination_score(self):
        """Test getting hallucination score."""
        detector = HallucinationDetector()
        response = "The Earth is flat and Paris is in Germany."
        score = detector.get_hallucination_score(response)
        assert 0.0 <= score <= 1.0
    
    def test_get_statistics(self):
        """Test getting detector statistics."""
        detector = HallucinationDetector()
        detector.detect("Test response for detection.")
        stats = detector.get_statistics()
        assert "total_detections" in stats


# =============================================================================
# Tests for ValidationCondition
# =============================================================================

class TestValidationCondition:
    """Tests for ValidationCondition class."""
    
    def test_equals_condition(self):
        """Test equals operator."""
        condition = ValidationCondition(operator="eq", value="test")
        assert condition.evaluate("test") is True
        assert condition.evaluate("other") is False
    
    def test_greater_than_condition(self):
        """Test greater than operator."""
        condition = ValidationCondition(operator="gt", value=50)
        assert condition.evaluate(60) is True
        assert condition.evaluate(40) is False
    
    def test_contains_condition(self):
        """Test contains operator."""
        condition = ValidationCondition(operator="contains", value="hello")
        assert condition.evaluate("hello world") is True
        assert condition.evaluate("goodbye") is False
    
    def test_length_condition(self):
        """Test length operators."""
        condition = ValidationCondition(operator="length_gte", value=5)
        assert condition.evaluate("hello") is True
        assert condition.evaluate("hi") is False
    
    def test_matches_condition(self):
        """Test regex matches operator."""
        condition = ValidationCondition(operator="matches", value=r'\d+')
        assert condition.evaluate("123") is True
        assert condition.evaluate("abc") is False


# =============================================================================
# Tests for ValidationRule
# =============================================================================

class TestValidationRule:
    """Tests for ValidationRule dataclass."""
    
    def test_rule_creation(self):
        """Test creating a validation rule."""
        rule = ValidationRule(
            rule_id="test_001",
            name="test_rule",
            condition=ValidationCondition(operator="ne", value=""),
            severity=ValidationSeverity.HIGH
        )
        assert rule.rule_id == "test_001"
        assert rule.enabled is True
    
    def test_rule_validate_pass(self):
        """Test rule validation that passes."""
        rule = ValidationRule(
            rule_id="test_001",
            name="not_empty",
            condition=ValidationCondition(operator="ne", value=""),
        )
        result = rule.validate("some content")
        assert result.status == ValidationStatus.PASS
    
    def test_rule_validate_fail(self):
        """Test rule validation that fails."""
        rule = ValidationRule(
            rule_id="test_001",
            name="not_empty",
            condition=ValidationCondition(operator="ne", value=""),
            severity=ValidationSeverity.CRITICAL,
            error_message="Value cannot be empty"
        )
        result = rule.validate("")
        assert result.status == ValidationStatus.FAIL
    
    def test_disabled_rule(self):
        """Test that disabled rules are skipped."""
        rule = ValidationRule(
            rule_id="test_001",
            name="test",
            condition=ValidationCondition(operator="eq", value="test"),
            enabled=False
        )
        result = rule.validate("other")
        assert result.status == ValidationStatus.SKIP


# =============================================================================
# Tests for RuleResult
# =============================================================================

class TestRuleResult:
    """Tests for RuleResult dataclass."""
    
    def test_result_creation(self):
        """Test creating a rule result."""
        result = RuleResult(
            rule_id="test_001",
            rule_name="test_rule",
            status=ValidationStatus.PASS
        )
        assert result.passed is True
    
    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = RuleResult(
            rule_id="test_001",
            rule_name="test_rule",
            status=ValidationStatus.FAIL,
            message="Test message"
        )
        d = result.to_dict()
        assert d["status"] == "fail"
        assert d["message"] == "Test message"


# =============================================================================
# Tests for ValidationPipeline
# =============================================================================

class TestValidationPipeline:
    """Tests for ValidationPipeline class."""
    
    def test_pipeline_creation(self):
        """Test creating a validation pipeline."""
        pipeline = ValidationPipeline(name="test")
        assert pipeline.name == "test"
    
    def test_add_rule(self):
        """Test adding rules to pipeline."""
        pipeline = ValidationPipeline()
        rule = ValidationRule(
            rule_id="test_001",
            name="test_rule",
            condition=ValidationCondition(operator="ne", value=""),
            stage=ValidationStage.PRE_PROCESSING
        )
        pipeline.add_rule(rule)
        assert len(pipeline.get_all_rules()) == 1
    
    def test_remove_rule(self):
        """Test removing rules from pipeline."""
        pipeline = ValidationPipeline()
        rule = ValidationRule(
            rule_id="test_001",
            name="test_rule",
            condition=ValidationCondition(operator="ne", value=""),
        )
        pipeline.add_rule(rule)
        assert pipeline.remove_rule("test_001") is True
        assert len(pipeline.get_all_rules()) == 0
    
    def test_run_pipeline(self):
        """Test running the pipeline."""
        pipeline = ValidationPipeline()
        pipeline.add_rule(ValidationRule(
            rule_id="test_001",
            name="not_empty",
            condition=ValidationCondition(operator="ne", value=""),
            stage=ValidationStage.PRE_PROCESSING
        ))
        result = pipeline.run({"response": "test content"})
        assert isinstance(result, ValidationResult)
    
    def test_get_statistics(self):
        """Test getting pipeline statistics."""
        pipeline = ValidationPipeline()
        pipeline.add_rule(ValidationRule(
            rule_id="test_001",
            name="test",
            condition=ValidationCondition(operator="ne", value=""),
        ))
        stats = pipeline.get_statistics()
        assert "rules_count" in stats


# =============================================================================
# Tests for QualityValidator
# =============================================================================

class TestQualityValidator:
    """Tests for QualityValidator class."""
    
    def test_validator_initialization(self):
        """Test validator initialization with default pipeline."""
        validator = QualityValidator()
        assert validator.pipeline is not None
    
    def test_validate_response(self):
        """Test validating a response."""
        validator = QualityValidator()
        result = validator.validate("This is a test response with some content.")
        assert isinstance(result, ValidationResult)
        assert result.overall_status in [ValidationStatus.PASS, ValidationStatus.FAIL, ValidationStatus.WARNING]
    
    def test_validate_empty_response(self):
        """Test validating an empty response."""
        validator = QualityValidator()
        result = validator.validate("")
        assert result.overall_status == ValidationStatus.FAIL
    
    def test_batch_validate(self):
        """Test batch validation."""
        validator = QualityValidator()
        responses = [
            "First response with enough content.",
            "Second response with enough content.",
        ]
        results = validator.batch_validate(responses)
        assert len(results) == 2
    
    def test_add_custom_rule(self):
        """Test adding custom rule to validator."""
        validator = QualityValidator()
        custom_rule = ValidationRule(
            rule_id="custom_001",
            name="custom_check",
            condition=ValidationCondition(operator="contains", value="test"),
            stage=ValidationStage.CONTENT_ANALYSIS
        )
        validator.add_custom_rule(custom_rule)
        # Rule should be added
        assert any(r.rule_id == "custom_001" for r in validator.pipeline.get_all_rules())
    
    def test_get_pass_fail_report(self):
        """Test getting pass/fail report."""
        validator = QualityValidator()
        validator.validate("Test response one.")
        validator.validate("Test response two.")
        report = validator.get_pass_fail_report()
        assert "summary" in report
        assert "total" in report["summary"]


# =============================================================================
# Tests for create_simple_validator
# =============================================================================

class TestCreateSimpleValidator:
    """Tests for create_simple_validator helper function."""
    
    def test_simple_validator_creation(self):
        """Test creating a simple validator."""
        validator = create_simple_validator()
        assert isinstance(validator, QualityValidator)
    
    def test_simple_validator_with_custom_thresholds(self):
        """Test simple validator with custom thresholds."""
        validator = create_simple_validator(min_length=20, quality_threshold=60.0)
        # Short response should fail (HIGH severity -> WARNING status)
        result = validator.validate("Too short")
        assert result.overall_status == ValidationStatus.WARNING
        assert any(r.status == ValidationStatus.FAIL for r in result.get_all_failures())


# =============================================================================
# Tests for ValidationStage and ValidationStatus
# =============================================================================

class TestValidationEnums:
    """Tests for validation-related enums."""
    
    def test_validation_status_values(self):
        """Test ValidationStatus enum values."""
        assert ValidationStatus.PASS.value == "pass"
        assert ValidationStatus.FAIL.value == "fail"
        assert ValidationStatus.WARNING.value == "warning"
    
    def test_validation_stage_values(self):
        """Test ValidationStage enum values."""
        assert ValidationStage.PRE_PROCESSING.value == "pre_processing"
        assert ValidationStage.QUALITY_CHECK.value == "quality_check"
    
    def test_validation_severity_values(self):
        """Test ValidationSeverity enum values."""
        assert ValidationSeverity.CRITICAL.value == "critical"
        assert ValidationSeverity.HIGH.value == "high"


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple modules."""
    
    def test_quality_scoring_with_validation(self):
        """Test using quality scorer with validator."""
        scorer = ResponseQualityScorer()
        validator = QualityValidator()
        
        response = "This is a detailed response that provides helpful information about the topic. It includes multiple sentences and comprehensive coverage."
        
        # Score the response
        quality_score = scorer.score(response)
        
        # Validate with quality score
        result = validator.validate(response, quality_score=quality_score.overall)
        
        assert quality_score.overall > 0
        assert isinstance(result, ValidationResult)
    
    def test_hallucination_detection_with_validation(self):
        """Test hallucination detection with validation pipeline."""
        detector = HallucinationDetector()
        
        # Create validator with custom rule for hallucination score
        pipeline = ValidationPipeline(name="hallucination_aware")
        
        pipeline.add_rule(ValidationRule(
            rule_id="hallucination_001",
            name="low_hallucination_score",
            condition=ValidationCondition(operator="lte", value=0.3),
            threshold=0.3,
            severity=ValidationSeverity.HIGH,
            stage=ValidationStage.HALLUCINATION_CHECK,
            error_message="High hallucination score detected"
        ))
        
        validator = QualityValidator(pipeline)
        
        response = "The Earth revolves around the Sun."
        hallucination_score = detector.get_hallucination_score(response)
        
        result = validator.validate(
            response, 
            additional_data={"hallucination_score": hallucination_score}
        )
        
        assert isinstance(result, ValidationResult)
    
    def test_full_quality_pipeline(self):
        """Test full quality assessment pipeline."""
        # Setup all components
        scorer = ResponseQualityScorer()
        detector = HallucinationDetector()
        validator = QualityValidator()
        
        response = "Python is a programming language created by Guido van Rossum. It is widely used for web development, data science, and automation. Python emphasizes code readability and simplicity."
        
        # Score quality
        quality = scorer.score(response)
        
        # Check for hallucinations
        hallucinations = detector.detect(response)
        hallucination_score = detector.get_hallucination_score(response)
        
        # Validate
        result = validator.validate(
            response,
            quality_score=quality.overall,
            additional_data={"hallucination_score": hallucination_score}
        )
        
        assert quality.overall > 0
        assert isinstance(hallucinations, list)
        assert 0.0 <= hallucination_score <= 1.0
        assert isinstance(result, ValidationResult)


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_very_long_response(self):
        """Test scoring a very long response."""
        scorer = ResponseQualityScorer()
        response = "This is a test sentence. " * 1000
        score = scorer.score(response)
        assert score.overall > 0
    
    def test_special_characters_in_response(self):
        """Test handling special characters."""
        scorer = ResponseQualityScorer()
        detector = HallucinationDetector()
        
        response = "Special chars: @#$%^&*()_+-=[]{}|;':\",./<>?"
        
        score = scorer.score(response)
        hallucinations = detector.detect(response)
        
        assert isinstance(score, QualityScore)
        assert isinstance(hallucinations, list)
    
    def test_unicode_response(self):
        """Test handling unicode characters."""
        scorer = ResponseQualityScorer()
        response = "Hello 你好 مرحبا שלום 🌍"
        score = scorer.score(response)
        assert score.overall >= 0
    
    def test_whitespace_only_response(self):
        """Test handling whitespace-only response."""
        scorer = ResponseQualityScorer()
        validator = QualityValidator()
        
        response = "   \n\t  "
        
        score = scorer.score(response)
        result = validator.validate(response)
        
        assert score.overall == 0.0
        # Whitespace passes "not empty" check but fails length check
        # HIGH severity failures result in WARNING status
        assert result.overall_status in [ValidationStatus.FAIL, ValidationStatus.WARNING]
        assert any(r.status == ValidationStatus.FAIL for r in result.get_all_failures())
    
    def test_concurrent_validations(self):
        """Test multiple sequential validations don't interfere."""
        validator = QualityValidator()
        
        results = []
        for i in range(5):
            result = validator.validate(f"Test response number {i}")
            results.append(result)
        
        assert len(results) == 5
        assert all(isinstance(r, ValidationResult) for r in results)
