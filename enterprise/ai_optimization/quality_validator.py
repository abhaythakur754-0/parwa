"""
Quality Validation Pipeline Module

This module provides a comprehensive quality validation pipeline for AI-generated responses.
It includes validation rules, multi-stage pipelines, and pass/fail reporting.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from datetime import datetime
import re


class ValidationStatus(Enum):
    """Status of a validation result."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"
    ERROR = "error"


class ValidationStage(Enum):
    """Stages in the validation pipeline."""
    PRE_PROCESSING = "pre_processing"
    CONTENT_ANALYSIS = "content_analysis"
    QUALITY_CHECK = "quality_check"
    HALLUCINATION_CHECK = "hallucination_check"
    POST_PROCESSING = "post_processing"


class ValidationSeverity(Enum):
    """Severity level for validation failures."""
    CRITICAL = "critical"    # Must pass
    HIGH = "high"           # Should pass
    MEDIUM = "medium"       # Warning if fails
    LOW = "low"             # Informational


@dataclass
class ValidationCondition:
    """
    Condition for validation rule evaluation.
    
    Attributes:
        operator: Comparison operator (eq, ne, gt, lt, gte, lte, contains, matches, in, not_in)
        value: Value to compare against
        field: Field in the data to check (optional, for nested data)
    """
    operator: str
    value: Any
    field: Optional[str] = None
    
    def evaluate(self, input_value: Any) -> bool:
        """Evaluate the condition against an input value."""
        try:
            if self.operator == "eq":
                return input_value == self.value
            elif self.operator == "ne":
                return input_value != self.value
            elif self.operator == "gt":
                return input_value > self.value
            elif self.operator == "lt":
                return input_value < self.value
            elif self.operator == "gte":
                return input_value >= self.value
            elif self.operator == "lte":
                return input_value <= self.value
            elif self.operator == "contains":
                return self.value in str(input_value)
            elif self.operator == "not_contains":
                return self.value not in str(input_value)
            elif self.operator == "matches":
                return bool(re.search(self.value, str(input_value)))
            elif self.operator == "in":
                return input_value in self.value
            elif self.operator == "not_in":
                return input_value not in self.value
            elif self.operator == "length_gte":
                return len(str(input_value)) >= self.value
            elif self.operator == "length_lte":
                return len(str(input_value)) <= self.value
            elif self.operator == "length_eq":
                return len(str(input_value)) == self.value
            else:
                return False
        except Exception:
            return False


@dataclass
class ValidationRule:
    """
    Validation rule with condition and threshold.
    
    Attributes:
        rule_id: Unique identifier for the rule
        name: Human-readable name
        description: Description of what the rule checks
        condition: Condition to evaluate
        threshold: Threshold value for pass/fail determination
        severity: Severity level if rule fails
        stage: Pipeline stage this rule belongs to
        enabled: Whether the rule is active
        error_message: Custom error message on failure
        tags: Tags for categorization
    """
    rule_id: str
    name: str
    condition: ValidationCondition
    threshold: float = 50.0
    severity: ValidationSeverity = ValidationSeverity.MEDIUM
    stage: ValidationStage = ValidationStage.QUALITY_CHECK
    description: str = ""
    enabled: bool = True
    error_message: str = ""
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Set default error message if not provided."""
        if not self.error_message:
            self.error_message = f"Validation rule '{self.name}' failed"
    
    def validate(self, input_value: Any) -> 'RuleResult':
        """Validate input against this rule."""
        if not self.enabled:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                status=ValidationStatus.SKIP,
                message="Rule is disabled",
                severity=self.severity
            )
        
        try:
            passed = self.condition.evaluate(input_value)
            status = ValidationStatus.PASS if passed else ValidationStatus.FAIL
            message = "" if passed else self.error_message
            
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                status=status,
                message=message,
                severity=self.severity,
                actual_value=input_value,
                expected_value=self.threshold
            )
        except Exception as e:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                status=ValidationStatus.ERROR,
                message=f"Error during validation: {str(e)}",
                severity=self.severity
            )


@dataclass
class RuleResult:
    """
    Result of a single validation rule.
    
    Attributes:
        rule_id: ID of the rule that was evaluated
        rule_name: Name of the rule
        status: Pass/fail status
        message: Message explaining the result
        severity: Severity level of the rule
        actual_value: Actual value that was validated
        expected_value: Expected value or threshold
        timestamp: When the validation occurred
    """
    rule_id: str
    rule_name: str
    status: ValidationStatus
    message: str = ""
    severity: ValidationSeverity = ValidationSeverity.MEDIUM
    actual_value: Any = None
    expected_value: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "status": self.status.value,
            "message": self.message,
            "severity": self.severity.value,
            "actual_value": str(self.actual_value) if self.actual_value is not None else None,
            "expected_value": self.expected_value,
            "timestamp": self.timestamp.isoformat()
        }
    
    @property
    def passed(self) -> bool:
        """Check if the rule passed."""
        return self.status == ValidationStatus.PASS or self.status == ValidationStatus.SKIP


@dataclass
class StageResult:
    """
    Result of a validation pipeline stage.
    
    Attributes:
        stage: The pipeline stage
        status: Overall status of the stage
        rule_results: Results of all rules in the stage
        duration_ms: Duration of stage execution in milliseconds
        metadata: Additional metadata about the stage
    """
    stage: ValidationStage
    status: ValidationStatus
    rule_results: List[RuleResult] = field(default_factory=list)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stage": self.stage.value,
            "status": self.status.value,
            "rule_results": [r.to_dict() for r in self.rule_results],
            "duration_ms": self.duration_ms,
            "metadata": self.metadata
        }
    
    @property
    def passed(self) -> bool:
        """Check if all critical/high rules passed."""
        for result in self.rule_results:
            if result.status == ValidationStatus.FAIL:
                if result.severity in (ValidationSeverity.CRITICAL, ValidationSeverity.HIGH):
                    return False
        return True
    
    def get_failures(self) -> List[RuleResult]:
        """Get all failed rule results."""
        return [r for r in self.rule_results if r.status == ValidationStatus.FAIL]


@dataclass
class ValidationResult:
    """
    Complete validation result from the pipeline.
    
    Attributes:
        overall_status: Overall pass/fail status
        stage_results: Results from each pipeline stage
        score: Overall quality score (0-100)
        total_rules: Total number of rules evaluated
        passed_rules: Number of rules that passed
        failed_rules: Number of rules that failed
        warnings: Number of warning-level failures
        timestamp: When validation was performed
        metadata: Additional metadata
    """
    overall_status: ValidationStatus
    stage_results: List[StageResult] = field(default_factory=list)
    score: float = 0.0
    total_rules: int = 0
    passed_rules: int = 0
    failed_rules: int = 0
    warnings: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "overall_status": self.overall_status.value,
            "stage_results": [s.to_dict() for s in self.stage_results],
            "score": self.score,
            "total_rules": self.total_rules,
            "passed_rules": self.passed_rules,
            "failed_rules": self.failed_rules,
            "warnings": self.warnings,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @property
    def passed(self) -> bool:
        """Check if overall validation passed."""
        return self.overall_status == ValidationStatus.PASS
    
    @property
    def pass_rate(self) -> float:
        """Calculate pass rate."""
        if self.total_rules == 0:
            return 1.0
        return self.passed_rules / self.total_rules
    
    def get_all_failures(self) -> List[RuleResult]:
        """Get all failed rule results across all stages."""
        failures = []
        for stage in self.stage_results:
            failures.extend(stage.get_failures())
        return failures
    
    def get_failures_by_severity(self, severity: ValidationSeverity) -> List[RuleResult]:
        """Get failures filtered by severity."""
        return [f for f in self.get_all_failures() if f.severity == severity]


class ValidationPipeline:
    """
    Multi-stage validation pipeline.
    
    This class manages a pipeline of validation stages with rules
    organized by stage.
    """
    
    def __init__(self, name: str = "default"):
        """
        Initialize the validation pipeline.
        
        Args:
            name: Name of the pipeline
        """
        self.name = name
        self._stages: Dict[ValidationStage, List[ValidationRule]] = {
            stage: [] for stage in ValidationStage
        }
        self._stage_order = list(ValidationStage)
        self._validation_history: List[ValidationResult] = []
    
    def add_rule(self, rule: ValidationRule) -> None:
        """Add a rule to the appropriate stage."""
        self._stages[rule.stage].append(rule)
    
    def add_rules(self, rules: List[ValidationRule]) -> None:
        """Add multiple rules to the pipeline."""
        for rule in rules:
            self.add_rule(rule)
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        for stage in self._stages:
            for i, rule in enumerate(self._stages[stage]):
                if rule.rule_id == rule_id:
                    self._stages[stage].pop(i)
                    return True
        return False
    
    def get_rules_by_stage(self, stage: ValidationStage) -> List[ValidationRule]:
        """Get all rules for a specific stage."""
        return self._stages.get(stage, [])
    
    def get_all_rules(self) -> List[ValidationRule]:
        """Get all rules in the pipeline."""
        rules = []
        for stage in self._stage_order:
            rules.extend(self._stages[stage])
        return rules
    
    def set_stage_order(self, order: List[ValidationStage]) -> None:
        """Set custom stage execution order."""
        self._stage_order = order
    
    def run_stage(
        self, 
        stage: ValidationStage, 
        data: Dict[str, Any]
    ) -> StageResult:
        """Run validation for a single stage."""
        import time
        start_time = time.time()
        
        rules = self._stages.get(stage, [])
        rule_results: List[RuleResult] = []
        
        for rule in rules:
            # Get the input value for the rule
            if rule.condition.field:
                input_value = data.get(rule.condition.field)
            else:
                input_value = data.get("response", data.get("input", ""))
            
            result = rule.validate(input_value)
            rule_results.append(result)
        
        # Determine stage status
        has_critical_failure = any(
            r.status == ValidationStatus.FAIL and r.severity == ValidationSeverity.CRITICAL
            for r in rule_results
        )
        has_high_failure = any(
            r.status == ValidationStatus.FAIL and r.severity == ValidationSeverity.HIGH
            for r in rule_results
        )
        
        if has_critical_failure:
            status = ValidationStatus.FAIL
        elif has_high_failure:
            status = ValidationStatus.WARNING
        else:
            status = ValidationStatus.PASS
        
        duration_ms = (time.time() - start_time) * 1000
        
        return StageResult(
            stage=stage,
            status=status,
            rule_results=rule_results,
            duration_ms=duration_ms
        )
    
    def run(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Run the complete validation pipeline.
        
        Args:
            data: Dictionary containing data to validate
                  Expected keys: 'response', 'context', etc.
        
        Returns:
            ValidationResult with complete validation details
        """
        stage_results: List[StageResult] = []
        total_rules = 0
        passed_rules = 0
        failed_rules = 0
        warnings = 0
        
        for stage in self._stage_order:
            stage_result = self.run_stage(stage, data)
            stage_results.append(stage_result)
            
            for rule_result in stage_result.rule_results:
                total_rules += 1
                if rule_result.status == ValidationStatus.PASS:
                    passed_rules += 1
                elif rule_result.status == ValidationStatus.FAIL:
                    failed_rules += 1
                    if rule_result.severity == ValidationSeverity.MEDIUM:
                        warnings += 1
        
        # Calculate overall score
        score = (passed_rules / max(total_rules, 1)) * 100
        
        # Determine overall status
        critical_failures = sum(
            1 for s in stage_results 
            for r in s.rule_results 
            if r.status == ValidationStatus.FAIL and r.severity == ValidationSeverity.CRITICAL
        )
        high_failures = sum(
            1 for s in stage_results 
            for r in s.rule_results 
            if r.status == ValidationStatus.FAIL and r.severity == ValidationSeverity.HIGH
        )
        
        if critical_failures > 0:
            overall_status = ValidationStatus.FAIL
        elif high_failures > 0:
            overall_status = ValidationStatus.WARNING
        else:
            overall_status = ValidationStatus.PASS
        
        result = ValidationResult(
            overall_status=overall_status,
            stage_results=stage_results,
            score=score,
            total_rules=total_rules,
            passed_rules=passed_rules,
            failed_rules=failed_rules,
            warnings=warnings,
            metadata={"pipeline_name": self.name}
        )
        
        self._validation_history.append(result)
        return result
    
    def get_history(self, limit: int = 10) -> List[ValidationResult]:
        """Get recent validation history."""
        return self._validation_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear validation history."""
        self._validation_history = []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        if not self._validation_history:
            return {
                "total_validations": 0,
                "pass_rate": 0.0,
                "average_score": 0.0,
                "rules_count": sum(len(rules) for rules in self._stages.values())
            }
        
        passes = sum(1 for v in self._validation_history if v.passed)
        total_score = sum(v.score for v in self._validation_history)
        
        return {
            "total_validations": len(self._validation_history),
            "pass_rate": passes / len(self._validation_history),
            "average_score": total_score / len(self._validation_history),
            "rules_count": sum(len(rules) for rules in self._stages.values()),
            "stages_count": len([s for s in self._stages if self._stages[s]])
        }


class QualityValidator:
    """
    Main quality validation class.
    
    This class provides a high-level interface for validating
    AI-generated responses using a configurable pipeline.
    """
    
    def __init__(self, pipeline: Optional[ValidationPipeline] = None):
        """
        Initialize the quality validator.
        
        Args:
            pipeline: Optional custom validation pipeline
        """
        self.pipeline = pipeline or self._create_default_pipeline()
        self._validation_history: List[ValidationResult] = []
    
    def _create_default_pipeline(self) -> ValidationPipeline:
        """Create default validation pipeline with standard rules."""
        pipeline = ValidationPipeline(name="default_quality")
        
        # Pre-processing rules
        pipeline.add_rules([
            ValidationRule(
                rule_id="pre_001",
                name="response_not_empty",
                description="Check that response is not empty",
                condition=ValidationCondition(operator="ne", value=""),
                severity=ValidationSeverity.CRITICAL,
                stage=ValidationStage.PRE_PROCESSING,
                error_message="Response cannot be empty"
            ),
            ValidationRule(
                rule_id="pre_002",
                name="minimum_length",
                description="Check minimum response length",
                condition=ValidationCondition(operator="length_gte", value=10),
                threshold=10,
                severity=ValidationSeverity.HIGH,
                stage=ValidationStage.PRE_PROCESSING,
                error_message="Response is too short (minimum 10 characters)"
            ),
        ])
        
        # Content analysis rules
        pipeline.add_rules([
            ValidationRule(
                rule_id="content_001",
                name="no_html_tags",
                description="Check for HTML tags in response",
                condition=ValidationCondition(operator="not_contains", value="<"),
                severity=ValidationSeverity.LOW,
                stage=ValidationStage.CONTENT_ANALYSIS,
                error_message="Response contains HTML tags"
            ),
            ValidationRule(
                rule_id="content_002",
                name="proper_ending",
                description="Check response ends with proper punctuation",
                condition=ValidationCondition(operator="matches", value=r'[.!?]$'),
                severity=ValidationSeverity.LOW,
                stage=ValidationStage.CONTENT_ANALYSIS,
                error_message="Response should end with proper punctuation"
            ),
        ])
        
        # Quality check rules
        pipeline.add_rules([
            ValidationRule(
                rule_id="quality_001",
                name="quality_score_threshold",
                description="Check overall quality score meets threshold",
                condition=ValidationCondition(operator="gte", value=50.0),
                threshold=50.0,
                severity=ValidationSeverity.HIGH,
                stage=ValidationStage.QUALITY_CHECK,
                error_message="Quality score below threshold"
            ),
        ])
        
        return pipeline
    
    def validate(
        self,
        response: str,
        context: Optional[str] = None,
        quality_score: Optional[float] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate a response using the pipeline.
        
        Args:
            response: The AI-generated response to validate
            context: Optional context for validation
            quality_score: Optional pre-computed quality score
            additional_data: Optional additional data for validation
        
        Returns:
            ValidationResult with validation details
        """
        data = {
            "response": response,
            "context": context or "",
            "quality_score": quality_score or 0.0,
        }
        
        if additional_data:
            data.update(additional_data)
        
        result = self.pipeline.run(data)
        self._validation_history.append(result)
        return result
    
    def batch_validate(
        self,
        responses: List[str],
        contexts: Optional[List[str]] = None,
        quality_scores: Optional[List[float]] = None
    ) -> List[ValidationResult]:
        """
        Validate multiple responses.
        
        Args:
            responses: List of responses to validate
            contexts: Optional list of contexts
            quality_scores: Optional list of quality scores
        
        Returns:
            List of ValidationResult objects
        """
        results = []
        for i, response in enumerate(responses):
            context = contexts[i] if contexts and i < len(contexts) else None
            score = quality_scores[i] if quality_scores and i < len(quality_scores) else None
            results.append(self.validate(response, context, score))
        return results
    
    def add_custom_rule(self, rule: ValidationRule) -> None:
        """Add a custom rule to the pipeline."""
        self.pipeline.add_rule(rule)
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule from the pipeline."""
        return self.pipeline.remove_rule(rule_id)
    
    def get_validation_history(self, limit: int = 10) -> List[ValidationResult]:
        """Get recent validation history."""
        return self._validation_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear validation history."""
        self._validation_history = []
        self.pipeline.clear_history()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get validator statistics."""
        pipeline_stats = self.pipeline.get_statistics()
        
        if not self._validation_history:
            return {
                "total_validations": 0,
                "pass_rate": 0.0,
                "average_score": 0.0,
                **pipeline_stats
            }
        
        passes = sum(1 for v in self._validation_history if v.passed)
        total_score = sum(v.score for v in self._validation_history)
        
        return {
            "total_validations": len(self._validation_history),
            "pass_rate": passes / len(self._validation_history),
            "average_score": total_score / len(self._validation_history),
            "pipeline": pipeline_stats
        }
    
    def get_pass_fail_report(self, limit: int = 10) -> Dict[str, Any]:
        """
        Generate a pass/fail report.
        
        Args:
            limit: Maximum number of recent validations to include
        
        Returns:
            Dictionary with pass/fail report details
        """
        recent = self._validation_history[-limit:]
        
        report = {
            "summary": {
                "total": len(recent),
                "passed": sum(1 for v in recent if v.overall_status == ValidationStatus.PASS),
                "failed": sum(1 for v in recent if v.overall_status == ValidationStatus.FAIL),
                "warnings": sum(1 for v in recent if v.overall_status == ValidationStatus.WARNING),
            },
            "details": []
        }
        
        report["summary"]["pass_rate"] = (
            report["summary"]["passed"] / len(recent) if recent else 0.0
        )
        
        for validation in recent:
            detail = {
                "timestamp": validation.timestamp.isoformat(),
                "status": validation.overall_status.value,
                "score": validation.score,
                "failures": [
                    {"rule": f.rule_name, "severity": f.severity.value, "message": f.message}
                    for f in validation.get_all_failures()
                ]
            }
            report["details"].append(detail)
        
        return report
    
    def set_quality_threshold(self, threshold: float) -> None:
        """
        Set the quality score threshold.
        
        Args:
            threshold: New threshold value (0-100)
        """
        # Find and update the quality score rule
        for stage in self.pipeline._stages:
            for rule in self.pipeline._stages[stage]:
                if rule.rule_id == "quality_001":
                    rule.threshold = threshold
                    rule.condition = ValidationCondition(operator="gte", value=threshold)
                    break


def create_simple_validator(
    min_length: int = 10,
    quality_threshold: float = 50.0
) -> QualityValidator:
    """
    Create a simple quality validator with basic rules.
    
    Args:
        min_length: Minimum response length
        quality_threshold: Quality score threshold
    
    Returns:
        Configured QualityValidator instance
    """
    pipeline = ValidationPipeline(name="simple")
    
    pipeline.add_rules([
        ValidationRule(
            rule_id="simple_001",
            name="not_empty",
            condition=ValidationCondition(operator="ne", value=""),
            severity=ValidationSeverity.CRITICAL,
            stage=ValidationStage.PRE_PROCESSING,
            error_message="Response is empty"
        ),
        ValidationRule(
            rule_id="simple_002",
            name="min_length",
            condition=ValidationCondition(operator="length_gte", value=min_length),
            threshold=min_length,
            severity=ValidationSeverity.HIGH,
            stage=ValidationStage.PRE_PROCESSING,
            error_message=f"Response shorter than {min_length} characters"
        ),
        ValidationRule(
            rule_id="simple_003",
            name="quality_threshold",
            condition=ValidationCondition(operator="gte", value=quality_threshold),
            threshold=quality_threshold,
            severity=ValidationSeverity.HIGH,
            stage=ValidationStage.QUALITY_CHECK,
            error_message=f"Quality score below {quality_threshold}"
        ),
    ])
    
    return QualityValidator(pipeline)
