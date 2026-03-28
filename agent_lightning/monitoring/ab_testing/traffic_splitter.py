"""
Traffic Splitter for A/B Testing.

Splits traffic between model variants using:
- Consistent hashing for user assignment
- Multi-variant support (A/B/C/D)
- Gradual rollout support
- Client-level isolation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import hashlib
import logging

logger = logging.getLogger(__name__)


class Variant(Enum):
    """Available variants."""
    CONTROL = "control"  # A - current model
    TREATMENT = "treatment"  # B - new model
    VARIANT_C = "variant_c"
    VARIANT_D = "variant_d"


@dataclass
class SplitConfig:
    """Configuration for traffic splitting."""
    control_percentage: float = 90.0
    treatment_percentage: float = 10.0
    variant_c_percentage: float = 0.0
    variant_d_percentage: float = 0.0
    salt: str = "ab_test_salt"
    enforce_client_isolation: bool = True


@dataclass
class VariantAssignment:
    """Result of variant assignment."""
    user_id: str
    client_id: str
    variant: Variant
    experiment_id: str
    assignment_reason: str = "hash_based"
    metadata: Dict[str, Any] = field(default_factory=dict)


class TrafficSplitter:
    """
    Splits traffic between model variants.

    Uses consistent hashing to ensure users always get the same variant.
    Supports gradual rollout and multi-variant experiments.
    """

    def __init__(self, config: Optional[SplitConfig] = None):
        """
        Initialize the traffic splitter.

        Args:
            config: Split configuration
        """
        self.config = config or SplitConfig()
        self._validate_percentages()
        self._assignment_cache: Dict[str, Variant] = {}

    def _validate_percentages(self):
        """Validate that percentages sum to 100."""
        total = (
            self.config.control_percentage +
            self.config.treatment_percentage +
            self.config.variant_c_percentage +
            self.config.variant_d_percentage
        )
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Percentages must sum to 100, got {total}")

    def _hash_user(self, user_id: str, client_id: str) -> float:
        """
        Generate consistent hash for user assignment.

        Args:
            user_id: User identifier
            client_id: Client identifier

        Returns:
            Hash value in [0, 100)
        """
        # Include client_id in hash for client isolation
        hash_input = f"{client_id}:{user_id}:{self.config.salt}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        return (hash_value % 10000) / 100.0

    def assign_variant(
        self,
        user_id: str,
        client_id: str,
        experiment_id: str = "default"
    ) -> VariantAssignment:
        """
        Assign a user to a variant.

        Args:
            user_id: User identifier
            client_id: Client identifier
            experiment_id: Experiment identifier

        Returns:
            VariantAssignment with variant details
        """
        # Check cache first
        cache_key = f"{client_id}:{user_id}:{experiment_id}"
        if cache_key in self._assignment_cache:
            variant = self._assignment_cache[cache_key]
            return VariantAssignment(
                user_id=user_id,
                client_id=client_id,
                variant=variant,
                experiment_id=experiment_id,
                assignment_reason="cached"
            )

        # Calculate hash-based assignment
        hash_value = self._hash_user(user_id, client_id)

        # Assign to variant based on percentages
        if hash_value < self.config.control_percentage:
            variant = Variant.CONTROL
        elif hash_value < self.config.control_percentage + self.config.treatment_percentage:
            variant = Variant.TREATMENT
        elif hash_value < (
            self.config.control_percentage +
            self.config.treatment_percentage +
            self.config.variant_c_percentage
        ):
            variant = Variant.VARIANT_C
        else:
            variant = Variant.VARIANT_D

        # Cache assignment
        self._assignment_cache[cache_key] = variant

        logger.debug(
            f"Assigned user {user_id} from client {client_id} to {variant.value}"
        )

        return VariantAssignment(
            user_id=user_id,
            client_id=client_id,
            variant=variant,
            experiment_id=experiment_id,
            assignment_reason="hash_based",
            metadata={"hash_value": hash_value}
        )

    def get_variant_distribution(self) -> Dict[str, float]:
        """Get current variant distribution percentages."""
        return {
            "control": self.config.control_percentage,
            "treatment": self.config.treatment_percentage,
            "variant_c": self.config.variant_c_percentage,
            "variant_d": self.config.variant_d_percentage,
        }

    def update_distribution(
        self,
        control: Optional[float] = None,
        treatment: Optional[float] = None,
        variant_c: Optional[float] = None,
        variant_d: Optional[float] = None
    ):
        """
        Update traffic distribution.

        Args:
            control: New control percentage
            treatment: New treatment percentage
            variant_c: New variant C percentage
            variant_d: New variant D percentage
        """
        if control is not None:
            self.config.control_percentage = control
        if treatment is not None:
            self.config.treatment_percentage = treatment
        if variant_c is not None:
            self.config.variant_c_percentage = variant_c
        if variant_d is not None:
            self.config.variant_d_percentage = variant_d

        self._validate_percentages()
        # Clear cache on distribution change
        self._assignment_cache.clear()

        logger.info(f"Updated distribution: {self.get_variant_distribution()}")

    def gradual_rollout(
        self,
        target_treatment_percentage: float,
        steps: int = 5
    ) -> List[float]:
        """
        Generate gradual rollout schedule.

        Args:
            target_treatment_percentage: Target percentage for treatment
            steps: Number of rollout steps

        Returns:
            List of treatment percentages for each step
        """
        current = self.config.treatment_percentage
        step_size = (target_treatment_percentage - current) / steps

        schedule = []
        for i in range(1, steps + 1):
            schedule.append(current + step_size * i)

        logger.info(f"Rollout schedule: {schedule}")
        return schedule

    def get_stats(self) -> Dict[str, Any]:
        """Get splitter statistics."""
        return {
            "config": {
                "control": self.config.control_percentage,
                "treatment": self.config.treatment_percentage,
                "variant_c": self.config.variant_c_percentage,
                "variant_d": self.config.variant_d_percentage,
            },
            "cached_assignments": len(self._assignment_cache),
            "salt": self.config.salt
        }


def get_traffic_splitter(
    treatment_percentage: float = 10.0
) -> TrafficSplitter:
    """
    Factory function to create a traffic splitter.

    Args:
        treatment_percentage: Percentage for treatment variant

    Returns:
        Configured TrafficSplitter instance
    """
    config = SplitConfig(
        control_percentage=100.0 - treatment_percentage,
        treatment_percentage=treatment_percentage
    )
    return TrafficSplitter(config=config)
