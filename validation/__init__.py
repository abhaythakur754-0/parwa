"""
Validation Package - Cross-Client Accuracy Verification

This package provides cross-client validation capabilities for PARWA:
- Cross-client validation across all 5 clients
- Per-client accuracy metrics
- Industry-specific benchmarks
- Improvement tracking

CRITICAL: All validation maintains client isolation and privacy.
"""

from .cross_client_validator import (
    CrossClientValidator,
    ValidationResult,
    validate_all_clients,
)
from .per_client_accuracy import (
    PerClientAccuracy,
    ClientMetrics,
    calculate_client_accuracy,
)
from .industry_benchmarks import (
    IndustryBenchmarks,
    IndustryStandard,
    get_industry_benchmark,
)
from .improvement_tracker import (
    ImprovementTracker,
    ImprovementRecord,
    track_improvement,
)

__version__ = "1.0.0"
__all__ = [
    # Cross-client validation
    "CrossClientValidator",
    "ValidationResult",
    "validate_all_clients",
    # Per-client accuracy
    "PerClientAccuracy",
    "ClientMetrics",
    "calculate_client_accuracy",
    # Industry benchmarks
    "IndustryBenchmarks",
    "IndustryStandard",
    "get_industry_benchmark",
    # Improvement tracking
    "ImprovementTracker",
    "ImprovementRecord",
    "track_improvement",
]
