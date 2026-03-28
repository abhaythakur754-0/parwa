# Data Classifier - Week 49 Builder 3
# Data classification engine for governance

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import re
import uuid


class SensitivityLevel(Enum):
    LOW = 1
    MEDIUM = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class ClassificationRule:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    pattern: str = ""  # Regex pattern
    classification: str = "internal"
    sensitivity: SensitivityLevel = SensitivityLevel.MEDIUM
    tags: List[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class ClassificationResult:
    matched: bool = False
    classification: str = "unknown"
    sensitivity: SensitivityLevel = SensitivityLevel.LOW
    confidence: float = 0.0
    matched_rules: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


class DataClassifier:
    """Classifies data based on patterns and rules"""

    def __init__(self):
        self._rules: List[ClassificationRule] = []
        self._metrics = {
            "total_classifications": 0,
            "by_classification": {},
            "total_matched_rules": 0
        }
        self._initialize_default_rules()

    def _initialize_default_rules(self) -> None:
        """Initialize default classification rules"""
        defaults = [
            ClassificationRule(
                name="SSN Pattern",
                pattern=r"\b\d{3}-\d{2}-\d{4}\b",
                classification="pii",
                sensitivity=SensitivityLevel.HIGH,
                tags=["pii", "ssn"]
            ),
            ClassificationRule(
                name="Email Pattern",
                pattern=r"\b[\w.-]+@[\w.-]+\.\w+\b",
                classification="pii",
                sensitivity=SensitivityLevel.MEDIUM,
                tags=["pii", "email"]
            ),
            ClassificationRule(
                name="Credit Card",
                pattern=r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
                classification="financial",
                sensitivity=SensitivityLevel.CRITICAL,
                tags=["pci", "credit_card"]
            ),
            ClassificationRule(
                name="Phone Number",
                pattern=r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
                classification="pii",
                sensitivity=SensitivityLevel.LOW,
                tags=["pii", "phone"]
            ),
            ClassificationRule(
                name="IP Address",
                pattern=r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
                classification="system",
                sensitivity=SensitivityLevel.LOW,
                tags=["system", "ip"]
            )
        ]
        self._rules.extend(defaults)

    def add_rule(self, rule: ClassificationRule) -> None:
        """Add a classification rule"""
        self._rules.append(rule)

    def classify(self, data: str) -> ClassificationResult:
        """Classify data based on rules"""
        result = ClassificationResult()
        self._metrics["total_classifications"] += 1

        for rule in self._rules:
            if not rule.enabled:
                continue

            if re.search(rule.pattern, data):
                result.matched = True
                result.matched_rules.append(rule.name)
                result.tags.extend(rule.tags)
                result.classification = rule.classification

                if rule.sensitivity.value > result.sensitivity.value:
                    result.sensitivity = rule.sensitivity

                self._metrics["total_matched_rules"] += 1

        if result.matched:
            cls_key = result.classification
            self._metrics["by_classification"][cls_key] = \
                self._metrics["by_classification"].get(cls_key, 0) + 1

        result.confidence = len(result.matched_rules) / max(len(self._rules), 1)

        return result

    def classify_batch(self, data_list: List[str]) -> List[ClassificationResult]:
        """Classify multiple data items"""
        return [self.classify(data) for data in data_list]

    def get_rules(self) -> List[ClassificationRule]:
        """Get all classification rules"""
        return self._rules.copy()

    def get_rule(self, rule_id: str) -> Optional[ClassificationRule]:
        """Get a rule by ID"""
        for rule in self._rules:
            if rule.id == rule_id:
                return rule
        return None

    def update_rule(self, rule_id: str, **kwargs) -> Optional[ClassificationRule]:
        """Update a classification rule"""
        rule = self.get_rule(rule_id)
        if not rule:
            return None

        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        return rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a classification rule"""
        for i, rule in enumerate(self._rules):
            if rule.id == rule_id:
                self._rules.pop(i)
                return True
        return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get classifier metrics"""
        return self._metrics.copy()
