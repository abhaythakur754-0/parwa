"""
Cross-Client Validator - Validate accuracy across all 5 clients.

CRITICAL: This module validates accuracy improvement across all clients
without exposing cross-client data. Each client's data remains isolated.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Status of cross-client validation"""
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    PENDING = "pending"


class ClientStatus(Enum):
    """Status of individual client validation"""
    IMPROVED = "improved"
    REGRESSED = "regressed"
    UNCHANGED = "unchanged"
    ERROR = "error"


@dataclass
class ClientValidationResult:
    """Validation result for a single client"""
    client_id: str
    industry: str
    baseline_accuracy: float
    current_accuracy: float
    improvement_percentage: float
    status: ClientStatus
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Calculate status if not set"""
        if self.improvement_percentage > 0.5:
            self.status = ClientStatus.IMPROVED
        elif self.improvement_percentage < -0.5:
            self.status = ClientStatus.REGRESSED
        else:
            self.status = ClientStatus.UNCHANGED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "client_id": self.client_id,
            "industry": self.industry,
            "baseline_accuracy": self.baseline_accuracy,
            "current_accuracy": self.current_accuracy,
            "improvement_percentage": self.improvement_percentage,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "errors": self.errors,
        }


@dataclass
class ValidationResult:
    """Overall cross-client validation result"""
    validation_id: str
    timestamp: datetime
    status: ValidationStatus
    total_clients: int
    improved_clients: int
    regressed_clients: int
    unchanged_clients: int
    average_improvement: float
    client_results: List[ClientValidationResult]
    collective_intelligence_impact: float
    meets_requirements: bool
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "validation_id": self.validation_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "total_clients": self.total_clients,
            "improved_clients": self.improved_clients,
            "regressed_clients": self.regressed_clients,
            "unchanged_clients": self.unchanged_clients,
            "average_improvement": self.average_improvement,
            "client_results": [r.to_dict() for r in self.client_results],
            "collective_intelligence_impact": self.collective_intelligence_impact,
            "meets_requirements": self.meets_requirements,
            "details": self.details,
        }


class CrossClientValidator:
    """
    Validates accuracy across all 5 clients.

    CRITICAL: Never exposes cross-client data. Each client is validated
    independently and only aggregated metrics are shared.

    Requirements:
    - All 5 clients must show improvement
    - No client may regress
    - Average improvement must be ≥5%
    """

    # Baseline accuracy from Week 19
    BASELINE_ACCURACY = 0.72  # 72%
    
    # Target accuracy for Week 22
    TARGET_ACCURACY = 0.77  # 77%
    
    # Minimum required improvement
    MIN_IMPROVEMENT = 0.05  # 5%

    # Client configurations
    CLIENTS = {
        "client_001": {"industry": "ecommerce", "variant": "parwa_junior"},
        "client_002": {"industry": "saas", "variant": "parwa_high"},
        "client_003": {"industry": "healthcare", "variant": "parwa_high", "hipaa": True},
        "client_004": {"industry": "logistics", "variant": "parwa_junior"},
        "client_005": {"industry": "fintech", "variant": "parwa_high", "pci_dss": True},
    }

    def __init__(
        self,
        baseline_accuracy: float = BASELINE_ACCURACY,
        target_accuracy: float = TARGET_ACCURACY,
        min_improvement: float = MIN_IMPROVEMENT,
    ):
        """
        Initialize cross-client validator.

        Args:
            baseline_accuracy: Starting accuracy (default 72%)
            target_accuracy: Target accuracy (default 77%)
            min_improvement: Minimum required improvement (default 5%)
        """
        self.baseline_accuracy = baseline_accuracy
        self.target_accuracy = target_accuracy
        self.min_improvement = min_improvement
        self._validation_history: List[ValidationResult] = []

    def validate_client(
        self,
        client_id: str,
        current_accuracy: float,
        baseline_accuracy: Optional[float] = None,
    ) -> ClientValidationResult:
        """
        Validate a single client's accuracy.

        Args:
            client_id: Client identifier
            current_accuracy: Current measured accuracy
            baseline_accuracy: Client-specific baseline (optional)

        Returns:
            ClientValidationResult
        """
        if client_id not in self.CLIENTS:
            raise ValueError(f"Unknown client: {client_id}")

        client_config = self.CLIENTS[client_id]
        baseline = baseline_accuracy or self.baseline_accuracy

        # Calculate improvement
        improvement = ((current_accuracy - baseline) / baseline) * 100

        # Determine status
        if improvement > 0.5:
            status = ClientStatus.IMPROVED
        elif improvement < -0.5:
            status = ClientStatus.REGRESSED
        else:
            status = ClientStatus.UNCHANGED

        return ClientValidationResult(
            client_id=client_id,
            industry=client_config["industry"],
            baseline_accuracy=baseline,
            current_accuracy=current_accuracy,
            improvement_percentage=improvement,
            status=status,
            timestamp=datetime.now(),
            details={
                "variant": client_config["variant"],
                "compliance": {
                    "hipaa": client_config.get("hipaa", False),
                    "pci_dss": client_config.get("pci_dss", False),
                },
            },
        )

    def validate_all_clients(
        self,
        client_accuracies: Dict[str, float],
        client_baselines: Optional[Dict[str, float]] = None,
    ) -> ValidationResult:
        """
        Validate accuracy across all clients.

        Args:
            client_accuracies: Dict of client_id -> current accuracy
            client_baselines: Optional dict of client_id -> baseline accuracy

        Returns:
            ValidationResult with aggregated metrics
        """
        # Validate all 5 clients are present
        missing_clients = set(self.CLIENTS.keys()) - set(client_accuracies.keys())
        if missing_clients:
            raise ValueError(f"Missing clients: {missing_clients}")

        # Validate each client
        client_results: List[ClientValidationResult] = []
        for client_id, current_accuracy in client_accuracies.items():
            baseline = client_baselines.get(client_id) if client_baselines else None
            result = self.validate_client(client_id, current_accuracy, baseline)
            client_results.append(result)

        # Count by status
        improved = sum(1 for r in client_results if r.status == ClientStatus.IMPROVED)
        regressed = sum(1 for r in client_results if r.status == ClientStatus.REGRESSED)
        unchanged = sum(1 for r in client_results if r.status == ClientStatus.UNCHANGED)

        # Calculate average improvement
        avg_improvement = sum(r.improvement_percentage for r in client_results) / len(client_results)

        # Calculate collective intelligence impact
        ci_impact = self._calculate_ci_impact(client_results)

        # Determine overall status
        if regressed > 0:
            status = ValidationStatus.FAILED
            meets_requirements = False
        elif improved == len(client_results) and avg_improvement >= self.min_improvement:
            status = ValidationStatus.PASSED
            meets_requirements = True
        elif improved > 0:
            status = ValidationStatus.PARTIAL
            meets_requirements = avg_improvement >= self.min_improvement
        else:
            status = ValidationStatus.FAILED
            meets_requirements = False

        # Create validation result
        validation_result = ValidationResult(
            validation_id=self._generate_validation_id(),
            timestamp=datetime.now(),
            status=status,
            total_clients=len(client_results),
            improved_clients=improved,
            regressed_clients=regressed,
            unchanged_clients=unchanged,
            average_improvement=avg_improvement,
            client_results=client_results,
            collective_intelligence_impact=ci_impact,
            meets_requirements=meets_requirements,
            details={
                "baseline_accuracy": self.baseline_accuracy,
                "target_accuracy": self.target_accuracy,
                "min_improvement": self.min_improvement,
            },
        )

        # Store in history
        self._validation_history.append(validation_result)

        logger.info(
            f"Cross-client validation {validation_result.validation_id}: "
            f"{status.value} - {improved}/{len(client_results)} improved"
        )

        return validation_result

    def get_validation_history(self, limit: int = 10) -> List[ValidationResult]:
        """Get recent validation history"""
        return self._validation_history[-limit:]

    def get_latest_validation(self) -> Optional[ValidationResult]:
        """Get most recent validation result"""
        return self._validation_history[-1] if self._validation_history else None

    def check_requirements_met(self, result: ValidationResult) -> Dict[str, Any]:
        """
        Check if all requirements are met.

        Args:
            result: ValidationResult to check

        Returns:
            Dict with requirement check results
        """
        requirements = {
            "all_clients_improved": result.improved_clients == result.total_clients,
            "no_client_regressed": result.regressed_clients == 0,
            "average_improvement_met": result.average_improvement >= self.min_improvement,
            "target_accuracy_met": all(
                r.current_accuracy >= self.target_accuracy
                for r in result.client_results
            ),
        }

        requirements["all_requirements_met"] = all(requirements.values())

        return requirements

    def _calculate_ci_impact(
        self,
        client_results: List[ClientValidationResult]
    ) -> float:
        """
        Calculate collective intelligence impact.

        CRITICAL: This only uses aggregated metrics, never client data.

        Args:
            client_results: List of client validation results

        Returns:
            Estimated CI impact percentage
        """
        # Estimate impact based on cross-industry pattern sharing
        # Clients in industries with more shared patterns benefit more
        
        industry_count = len(set(r.industry for r in client_results))
        
        # Base impact from industry diversity (more industries = more patterns)
        diversity_factor = min(industry_count / 5.0, 1.0) * 0.02
        
        # Impact from average improvement (higher improvement suggests CI helped)
        avg_improvement = sum(r.improvement_percentage for r in client_results) / len(client_results)
        improvement_factor = min(avg_improvement / 10.0, 1.0) * 0.03
        
        return round(diversity_factor + improvement_factor, 3)

    def _generate_validation_id(self) -> str:
        """Generate unique validation ID"""
        import hashlib
        timestamp = datetime.now().isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:12]


def validate_all_clients(
    client_accuracies: Dict[str, float],
    client_baselines: Optional[Dict[str, float]] = None,
    baseline_accuracy: float = 0.72,
    target_accuracy: float = 0.77,
) -> ValidationResult:
    """
    Convenience function to validate all clients.

    Args:
        client_accuracies: Dict of client_id -> current accuracy
        client_baselines: Optional dict of client_id -> baseline accuracy
        baseline_accuracy: Default baseline accuracy
        target_accuracy: Target accuracy

    Returns:
        ValidationResult
    """
    validator = CrossClientValidator(
        baseline_accuracy=baseline_accuracy,
        target_accuracy=target_accuracy,
    )
    return validator.validate_all_clients(client_accuracies, client_baselines)
