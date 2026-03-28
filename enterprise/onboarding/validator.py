"""
Enterprise Onboarding - Validator
Validates onboarding completion
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class ValidationLevel(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationResult(BaseModel):
    """Result of validation check"""
    check_name: str
    level: ValidationLevel
    passed: bool
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class OnboardingValidator:
    """
    Validates enterprise client onboarding completion.
    """

    def __init__(self):
        self.required_checks = [
            "database_configured",
            "api_keys_generated",
            "webhooks_configured",
            "users_created",
            "integrations_setup"
        ]

    def validate_client(self, client_id: str, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate client onboarding"""
        results = []

        for check in self.required_checks:
            result = self._run_check(client_id, check, config)
            results.append(result)

        return results

    def _run_check(
        self,
        client_id: str,
        check_name: str,
        config: Dict[str, Any]
    ) -> ValidationResult:
        """Run a specific validation check"""
        # Simulate validation
        passed = config.get(check_name, True)

        return ValidationResult(
            check_name=check_name,
            level=ValidationLevel.ERROR if not passed else ValidationLevel.INFO,
            passed=passed,
            message=f"Check {check_name} {'passed' if passed else 'failed'}"
        )

    def is_onboarding_complete(self, results: List[ValidationResult]) -> bool:
        """Check if all validations passed"""
        return all(r.passed for r in results if r.level == ValidationLevel.ERROR)

    def get_missing_requirements(self, results: List[ValidationResult]) -> List[str]:
        """Get list of failed checks"""
        return [r.check_name for r in results if not r.passed]
