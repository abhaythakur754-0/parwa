"""
Data Quality Management System

Provides data quality assessment, validation, and monitoring capabilities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
import re
import threading


class QualityDimension(Enum):
    """Dimensions of data quality."""
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    VALIDITY = "validity"
    UNIQUENESS = "uniqueness"
    INTEGRITY = "integrity"


class QualityRuleType(Enum):
    """Types of quality rules."""
    REQUIRED = "required"
    PATTERN = "pattern"
    RANGE = "range"
    ENUM = "enum"
    CUSTOM = "custom"
    UNIQUE = "unique"
    FOREIGN_KEY = "foreign_key"
    NOT_NULL = "not_null"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"


class QualityStatus(Enum):
    """Status of quality check results."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class QualityRule:
    """Defines a data quality rule."""
    rule_id: str
    name: str
    dimension: QualityDimension
    rule_type: QualityRuleType
    field: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    threshold: float = 1.0  # Minimum pass rate (0-1)
    enabled: bool = True
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "dimension": self.dimension.value,
            "rule_type": self.rule_type.value,
            "field": self.field,
            "parameters": self.parameters,
            "threshold": self.threshold,
            "enabled": self.enabled,
            "description": self.description
        }


@dataclass
class QualityScore:
    """Represents a quality score for a dimension."""
    dimension: QualityDimension
    score: float  # 0-100
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    records_checked: int = 0
    records_passed: int = 0
    issues: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def pass_rate(self) -> float:
        """Calculate pass rate."""
        if self.records_checked == 0:
            return 0.0
        return self.records_passed / self.records_checked
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert score to dictionary."""
        return {
            "dimension": self.dimension.value,
            "score": self.score,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "records_checked": self.records_checked,
            "records_passed": self.records_passed,
            "pass_rate": self.pass_rate,
            "issues": self.issues
        }


@dataclass
class QualityReport:
    """Complete quality report for a dataset."""
    dataset_id: str
    scores: Dict[QualityDimension, QualityScore]
    overall_score: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_records: int = 0
    rules_checked: int = 0
    rules_passed: int = 0
    
    def get_dimension_score(self, dimension: QualityDimension) -> Optional[float]:
        """Get score for a specific dimension."""
        if dimension in self.scores:
            return self.scores[dimension].score
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "dataset_id": self.dataset_id,
            "overall_score": self.overall_score,
            "timestamp": self.timestamp.isoformat(),
            "total_records": self.total_records,
            "rules_checked": self.rules_checked,
            "rules_passed": self.rules_passed,
            "scores": {
                d.value: s.to_dict() for d, s in self.scores.items()
            }
        }


class QualityRuleValidator:
    """Validates data against quality rules."""
    
    def __init__(self):
        self._validators: Dict[QualityRuleType, Callable] = {
            QualityRuleType.REQUIRED: self._validate_required,
            QualityRuleType.NOT_NULL: self._validate_not_null,
            QualityRuleType.PATTERN: self._validate_pattern,
            QualityRuleType.RANGE: self._validate_range,
            QualityRuleType.ENUM: self._validate_enum,
            QualityRuleType.MIN_LENGTH: self._validate_min_length,
            QualityRuleType.MAX_LENGTH: self._validate_max_length,
            QualityRuleType.UNIQUE: self._validate_unique,
            QualityRuleType.CUSTOM: self._validate_custom,
        }
    
    def validate(
        self,
        data: List[Dict[str, Any]],
        rule: QualityRule
    ) -> tuple[int, int, List[Dict[str, Any]]]:
        """
        Validate data against a rule.
        
        Returns:
            Tuple of (records_checked, records_passed, issues)
        """
        if rule.rule_type not in self._validators:
            return len(data), 0, [{"error": f"Unknown rule type: {rule.rule_type}"}]
        
        validator = self._validators[rule.rule_type]
        passed = 0
        issues = []
        
        for idx, record in enumerate(data):
            is_valid, issue = validator(record, rule)
            if is_valid:
                passed += 1
            elif issue:
                issues.append({
                    "record_index": idx,
                    "field": rule.field,
                    "issue": issue,
                    "value": record.get(rule.field)
                })
        
        return len(data), passed, issues
    
    def _validate_required(
        self,
        record: Dict[str, Any],
        rule: QualityRule
    ) -> tuple[bool, Optional[str]]:
        """Validate that field is present and not empty."""
        value = record.get(rule.field)
        if value is None or value == "":
            return False, "Field is required but missing or empty"
        return True, None
    
    def _validate_not_null(
        self,
        record: Dict[str, Any],
        rule: QualityRule
    ) -> tuple[bool, Optional[str]]:
        """Validate that field is not null."""
        value = record.get(rule.field)
        if value is None:
            return False, "Field is null"
        return True, None
    
    def _validate_pattern(
        self,
        record: Dict[str, Any],
        rule: QualityRule
    ) -> tuple[bool, Optional[str]]:
        """Validate field against regex pattern."""
        value = record.get(rule.field)
        if value is None:
            return True, None  # Null is valid for pattern check
        
        pattern = rule.parameters.get("pattern", ".*")
        if not re.match(pattern, str(value)):
            return False, f"Value does not match pattern: {pattern}"
        return True, None
    
    def _validate_range(
        self,
        record: Dict[str, Any],
        rule: QualityRule
    ) -> tuple[bool, Optional[str]]:
        """Validate numeric field is within range."""
        value = record.get(rule.field)
        if value is None:
            return True, None
        
        try:
            num_value = float(value)
            min_val = rule.parameters.get("min")
            max_val = rule.parameters.get("max")
            
            if min_val is not None and num_value < min_val:
                return False, f"Value {num_value} below minimum {min_val}"
            if max_val is not None and num_value > max_val:
                return False, f"Value {num_value} above maximum {max_val}"
            return True, None
        except (TypeError, ValueError):
            return False, "Value is not a valid number"
    
    def _validate_enum(
        self,
        record: Dict[str, Any],
        rule: QualityRule
    ) -> tuple[bool, Optional[str]]:
        """Validate field value is in allowed set."""
        value = record.get(rule.field)
        if value is None:
            return True, None
        
        allowed = rule.parameters.get("values", [])
        if value not in allowed:
            return False, f"Value '{value}' not in allowed values: {allowed}"
        return True, None
    
    def _validate_min_length(
        self,
        record: Dict[str, Any],
        rule: QualityRule
    ) -> tuple[bool, Optional[str]]:
        """Validate string minimum length."""
        value = record.get(rule.field)
        if value is None:
            return True, None
        
        min_length = rule.parameters.get("min_length", 0)
        if len(str(value)) < min_length:
            return False, f"Length {len(str(value))} below minimum {min_length}"
        return True, None
    
    def _validate_max_length(
        self,
        record: Dict[str, Any],
        rule: QualityRule
    ) -> tuple[bool, Optional[str]]:
        """Validate string maximum length."""
        value = record.get(rule.field)
        if value is None:
            return True, None
        
        max_length = rule.parameters.get("max_length", float('inf'))
        if len(str(value)) > max_length:
            return False, f"Length {len(str(value))} above maximum {max_length}"
        return True, None
    
    def _validate_unique(
        self,
        record: Dict[str, Any],
        rule: QualityRule
    ) -> tuple[bool, Optional[str]]:
        """Validate uniqueness (placeholder - requires context)."""
        # Note: Actual uniqueness check requires all data context
        # This is a simplified version
        return True, None
    
    def _validate_custom(
        self,
        record: Dict[str, Any],
        rule: QualityRule
    ) -> tuple[bool, Optional[str]]:
        """Validate using custom function."""
        custom_func = rule.parameters.get("function")
        if custom_func and callable(custom_func):
            try:
                result = custom_func(record.get(rule.field), record)
                return bool(result), None if result else "Custom validation failed"
            except Exception as e:
                return False, f"Custom validation error: {str(e)}"
        return True, None


class DataQualityManager:
    """
    Main data quality management system.
    
    Manages rules, executes quality checks, and generates reports.
    """
    
    def __init__(self):
        self._rules: Dict[str, QualityRule] = {}
        self._validator = QualityRuleValidator()
        self._reports: List[QualityReport] = []
        self._lock = threading.Lock()
        self._thresholds: Dict[QualityDimension, float] = {}
    
    def add_rule(self, rule: QualityRule) -> None:
        """Add a quality rule."""
        with self._lock:
            self._rules[rule.rule_id] = rule
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a quality rule."""
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                return True
        return False
    
    def get_rule(self, rule_id: str) -> Optional[QualityRule]:
        """Get a specific rule."""
        return self._rules.get(rule_id)
    
    def get_rules(
        self,
        dimension: Optional[QualityDimension] = None,
        enabled_only: bool = True
    ) -> List[QualityRule]:
        """
        Get rules with optional filtering.
        
        Args:
            dimension: Filter by quality dimension
            enabled_only: Only return enabled rules
            
        Returns:
            List of matching rules
        """
        with self._lock:
            rules = list(self._rules.values())
        
        if dimension:
            rules = [r for r in rules if r.dimension == dimension]
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        
        return rules
    
    def set_threshold(self, dimension: QualityDimension, threshold: float) -> None:
        """Set minimum threshold for a dimension."""
        self._thresholds[dimension] = threshold
    
    def get_threshold(self, dimension: QualityDimension) -> float:
        """Get threshold for a dimension (default 0.95)."""
        return self._thresholds.get(dimension, 0.95)
    
    def check(
        self,
        data: List[Dict[str, Any]],
        rules: Optional[List[QualityRule]] = None,
        dataset_id: str = ""
    ) -> QualityReport:
        """
        Perform quality check on data.
        
        Args:
            data: List of records to check
            rules: Specific rules to check (None for all)
            dataset_id: Identifier for the dataset
            
        Returns:
            QualityReport with results
        """
        rules = rules or self.get_rules(enabled_only=True)
        
        # Group rules by dimension
        dimension_rules: Dict[QualityDimension, List[QualityRule]] = {}
        for rule in rules:
            if rule.dimension not in dimension_rules:
                dimension_rules[rule.dimension] = []
            dimension_rules[rule.dimension].append(rule)
        
        # Calculate scores per dimension
        scores: Dict[QualityDimension, QualityScore] = {}
        total_rules_checked = 0
        total_rules_passed = 0
        
        for dimension, dim_rules in dimension_rules.items():
            records_checked = 0
            records_passed = 0
            all_issues: List[Dict[str, Any]] = []
            
            for rule in dim_rules:
                checked, passed, issues = self._validator.validate(data, rule)
                records_checked += checked
                records_passed += passed
                all_issues.extend(issues)
                total_rules_checked += 1
                if passed / checked >= rule.threshold if checked > 0 else True:
                    total_rules_passed += 1
            
            # Calculate dimension score
            if records_checked > 0:
                pass_rate = records_passed / records_checked
                score = pass_rate * 100
            else:
                score = 100.0
            
            scores[dimension] = QualityScore(
                dimension=dimension,
                score=score,
                records_checked=records_checked // len(dim_rules) if dim_rules else 0,
                records_passed=records_passed // len(dim_rules) if dim_rules else 0,
                issues=all_issues[:100]  # Limit issues stored
            )
        
        # Calculate overall score
        if scores:
            overall = sum(s.score for s in scores.values()) / len(scores)
        else:
            overall = 100.0
        
        report = QualityReport(
            dataset_id=dataset_id,
            scores=scores,
            overall_score=overall,
            total_records=len(data),
            rules_checked=total_rules_checked,
            rules_passed=total_rules_passed
        )
        
        with self._lock:
            self._reports.append(report)
        
        return report
    
    def check_field(
        self,
        data: List[Dict[str, Any]],
        field: str,
        dimension: QualityDimension
    ) -> QualityScore:
        """
        Check quality for a specific field and dimension.
        
        Args:
            data: Data to check
            field: Field name
            dimension: Quality dimension to check
            
        Returns:
            QualityScore for the field
        """
        rules = self.get_rules(dimension=dimension, enabled_only=True)
        field_rules = [r for r in rules if r.field == field]
        
        if not field_rules:
            return QualityScore(
                dimension=dimension,
                score=100.0,
                records_checked=0,
                records_passed=0
            )
        
        records_checked = 0
        records_passed = 0
        issues = []
        
        for rule in field_rules:
            checked, passed, rule_issues = self._validator.validate(data, rule)
            records_checked += checked
            records_passed += passed
            issues.extend(rule_issues)
        
        score = (records_passed / records_checked * 100) if records_checked > 0 else 100.0
        
        return QualityScore(
            dimension=dimension,
            score=score,
            records_checked=records_checked,
            records_passed=records_passed,
            issues=issues[:100]
        )
    
    def get_reports(
        self,
        dataset_id: Optional[str] = None,
        limit: int = 100
    ) -> List[QualityReport]:
        """Get quality reports with optional filtering."""
        with self._lock:
            reports = self._reports.copy()
        
        if dataset_id:
            reports = [r for r in reports if r.dataset_id == dataset_id]
        
        return reports[-limit:]
    
    def get_latest_report(self, dataset_id: str) -> Optional[QualityReport]:
        """Get the latest report for a dataset."""
        reports = self.get_reports(dataset_id=dataset_id, limit=1)
        return reports[0] if reports else None
    
    def create_rule(
        self,
        rule_id: str,
        name: str,
        dimension: QualityDimension,
        rule_type: QualityRuleType,
        field: str,
        parameters: Optional[Dict[str, Any]] = None,
        threshold: float = 1.0,
        description: str = ""
    ) -> QualityRule:
        """Factory method to create and add a rule."""
        rule = QualityRule(
            rule_id=rule_id,
            name=name,
            dimension=dimension,
            rule_type=rule_type,
            field=field,
            parameters=parameters or {},
            threshold=threshold,
            description=description
        )
        self.add_rule(rule)
        return rule
    
    def get_quality_summary(self) -> Dict[str, Any]:
        """Get summary of quality across all reports."""
        with self._lock:
            reports = self._reports.copy()
        
        if not reports:
            return {
                "total_reports": 0,
                "average_score": 0,
                "dimension_averages": {}
            }
        
        # Calculate averages
        dimension_totals: Dict[QualityDimension, List[float]] = {}
        overall_scores = []
        
        for report in reports:
            overall_scores.append(report.overall_score)
            for dimension, score in report.scores.items():
                if dimension not in dimension_totals:
                    dimension_totals[dimension] = []
                dimension_totals[dimension].append(score.score)
        
        dimension_averages = {
            d.value: sum(scores) / len(scores)
            for d, scores in dimension_totals.items()
        }
        
        return {
            "total_reports": len(reports),
            "average_score": sum(overall_scores) / len(overall_scores),
            "dimension_averages": dimension_averages
        }
    
    def clear_reports(self) -> int:
        """Clear all stored reports."""
        with self._lock:
            count = len(self._reports)
            self._reports = []
        return count


def create_quality_manager() -> DataQualityManager:
    """Factory function to create a data quality manager."""
    return DataQualityManager()
