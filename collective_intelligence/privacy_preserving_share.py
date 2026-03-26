"""
Privacy Preserving Share - Differential privacy and k-anonymity for sharing.

CRITICAL: Implements privacy guarantees for all cross-client data sharing.
Uses differential privacy, k-anonymity, and data minimization.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from enum import Enum
import hashlib
import json
import logging
import random
import math

logger = logging.getLogger(__name__)


class PrivacyLevel(Enum):
    """Privacy protection levels"""
    STANDARD = "standard"
    HIGH = "high"
    MAXIMUM = "maximum"


class ShareStatus(Enum):
    """Status of a share operation"""
    APPROVED = "approved"
    BLOCKED = "blocked"
    PENDING = "pending"
    OPTED_OUT = "opted_out"


@dataclass
class DifferentialPrivacyConfig:
    """Configuration for differential privacy"""
    epsilon: float = 1.0  # Privacy budget
    delta: float = 1e-5  # Privacy failure probability
    sensitivity: float = 1.0  # Query sensitivity

    def __post_init__(self):
        """Validate configuration"""
        if self.epsilon <= 0:
            raise ValueError("Epsilon must be positive")
        if self.delta < 0 or self.delta >= 1:
            raise ValueError("Delta must be in [0, 1)")
        if self.sensitivity <= 0:
            raise ValueError("Sensitivity must be positive")


@dataclass
class KAnonymityConfig:
    """Configuration for k-anonymity"""
    k: int = 5  # Minimum group size
    quasi_identifiers: List[str] = field(default_factory=lambda: [
        "industry", "region", "company_size", "subscription_tier"
    ])

    def __post_init__(self):
        """Validate configuration"""
        if self.k < 2:
            raise ValueError("K must be at least 2")


@dataclass
class ShareAuditEntry:
    """Audit entry for a share operation"""
    share_id: str
    timestamp: datetime
    source_client: str  # Hashed
    target_clients: int  # Count only
    data_type: str
    privacy_level: PrivacyLevel
    status: ShareStatus
    epsilon_used: float
    k_anonymity_k: int
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "share_id": self.share_id,
            "timestamp": self.timestamp.isoformat(),
            "source_client": self.source_client,
            "target_clients": self.target_clients,
            "data_type": self.data_type,
            "privacy_level": self.privacy_level.value,
            "status": self.status.value,
            "epsilon_used": self.epsilon_used,
            "k_anonymity_k": self.k_anonymity_k,
            "details": self.details,
        }


class PrivacyPreservingShare:
    """
    Implements privacy-preserving data sharing mechanisms.

    CRITICAL: All sharing must pass privacy checks:
    1. Differential privacy for numerical data
    2. K-anonymity for categorical data
    3. Data minimization
    4. Client opt-out support
    5. Full audit trail
    """

    def __init__(
        self,
        dp_config: Optional[DifferentialPrivacyConfig] = None,
        k_config: Optional[KAnonymityConfig] = None,
        privacy_level: PrivacyLevel = PrivacyLevel.STANDARD
    ):
        """
        Initialize privacy-preserving share.

        Args:
            dp_config: Differential privacy configuration
            k_config: K-anonymity configuration
            privacy_level: Privacy protection level
        """
        self.dp_config = dp_config or DifferentialPrivacyConfig()
        self.k_config = k_config or KAnonymityConfig()
        self.privacy_level = privacy_level
        self._audit_log: List[ShareAuditEntry] = []
        self._opted_out_clients: Set[str] = set()
        self._privacy_budget_used: Dict[str, float] = {}  # client_id -> budget

    def register_opt_out(self, client_id: str) -> None:
        """Register a client's opt-out from sharing"""
        self._opted_out_clients.add(client_id)
        logger.info(f"Client {self._hash_client(client_id)} opted out of sharing")

    def can_share(
        self,
        source_client: str,
        data_type: str,
        data: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Check if data can be shared.

        Args:
            source_client: Source client ID
            data_type: Type of data to share
            data: Data to validate

        Returns:
            Tuple of (can_share, reason)
        """
        # Check opt-out
        if source_client in self._opted_out_clients:
            return False, "Client has opted out of sharing"

        # Check for sensitive data
        if self._contains_sensitive_data(data):
            return False, "Data contains sensitive information"

        # Check privacy budget
        budget_used = self._privacy_budget_used.get(source_client, 0)
        if budget_used + self.dp_config.epsilon > 5.0:  # Max budget per client
            return False, "Privacy budget exhausted"

        return True, "Approved"

    def apply_differential_privacy(
        self,
        value: float,
        sensitivity: Optional[float] = None
    ) -> float:
        """
        Apply differential privacy to a numerical value.

        Uses Laplace mechanism: noise ~ Lap(0, sensitivity/epsilon)

        Args:
            value: Original value
            sensitivity: Query sensitivity (uses config if not provided)

        Returns:
            Privacy-protected value
        """
        sens = sensitivity or self.dp_config.sensitivity

        # Laplace noise scale
        scale = sens / self.dp_config.epsilon

        # Generate Laplace noise
        noise = self._laplace_noise(scale)

        return round(value + noise, 4)

    def apply_k_anonymity(
        self,
        data: List[Dict[str, Any]],
        quasi_identifiers: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Apply k-anonymity to a dataset.

        Suppresses records that don't meet k requirement.

        Args:
            data: List of records
            quasi_identifiers: QI attributes

        Returns:
            K-anonymous dataset
        """
        qi = quasi_identifiers or self.k_config.quasi_identifiers

        # Group by quasi-identifiers
        groups: Dict[str, List[Dict]] = {}
        for record in data:
            key = self._create_qi_key(record, qi)
            if key not in groups:
                groups[key] = []
            groups[key].append(record)

        # Only keep groups with k or more records
        anonymized = []
        for key, group in groups.items():
            if len(group) >= self.k_config.k:
                anonymized.extend(group)
            else:
                logger.debug(f"Suppressed group of size {len(group)}")

        return anonymized

    def minimize_data(
        self,
        data: Dict[str, Any],
        allowed_fields: List[str]
    ) -> Dict[str, Any]:
        """
        Minimize data to only allowed fields.

        Args:
            data: Original data
            allowed_fields: Fields that can be shared

        Returns:
            Minimized data
        """
        return {
            k: v for k, v in data.items()
            if k in allowed_fields
        }

    def share_with_audit(
        self,
        source_client: str,
        target_client_count: int,
        data_type: str,
        data: Dict[str, Any]
    ) -> ShareAuditEntry:
        """
        Share data with full audit trail.

        Args:
            source_client: Source client ID
            target_client_count: Number of target clients
            data_type: Type of data
            data: Data to share

        Returns:
            Audit entry
        """
        # Check if sharing is allowed
        can_share, reason = self.can_share(source_client, data_type, data)

        # Create audit entry
        share_id = self._generate_share_id()
        audit_entry = ShareAuditEntry(
            share_id=share_id,
            timestamp=datetime.now(),
            source_client=self._hash_client(source_client),
            target_clients=target_client_count,
            data_type=data_type,
            privacy_level=self.privacy_level,
            status=ShareStatus.APPROVED if can_share else ShareStatus.BLOCKED,
            epsilon_used=self.dp_config.epsilon if can_share else 0,
            k_anonymity_k=self.k_config.k,
            details={"reason": reason},
        )

        # Log the share
        self._audit_log.append(audit_entry)

        # Update privacy budget
        if can_share:
            current_budget = self._privacy_budget_used.get(source_client, 0)
            self._privacy_budget_used[source_client] = (
                current_budget + self.dp_config.epsilon
            )

        logger.info(f"Share {share_id}: {audit_entry.status.value}")
        return audit_entry

    def get_audit_log(
        self,
        client_id: Optional[str] = None,
        limit: int = 100
    ) -> List[ShareAuditEntry]:
        """
        Get audit log entries.

        Args:
            client_id: Filter by client (optional)
            limit: Maximum entries to return

        Returns:
            List of audit entries
        """
        if client_id:
            hashed = self._hash_client(client_id)
            entries = [
                e for e in self._audit_log
                if e.source_client == hashed
            ]
        else:
            entries = self._audit_log

        return entries[-limit:]

    def get_privacy_stats(self) -> Dict[str, Any]:
        """Get privacy protection statistics"""
        return {
            "total_shares": len(self._audit_log),
            "approved_shares": sum(
                1 for e in self._audit_log
                if e.status == ShareStatus.APPROVED
            ),
            "blocked_shares": sum(
                1 for e in self._audit_log
                if e.status == ShareStatus.BLOCKED
            ),
            "opted_out_clients": len(self._opted_out_clients),
            "privacy_level": self.privacy_level.value,
            "dp_config": {
                "epsilon": self.dp_config.epsilon,
                "delta": self.dp_config.delta,
            },
            "k_anonymity_k": self.k_config.k,
            "total_epsilon_used": sum(self._privacy_budget_used.values()),
        }

    def validate_privacy_compliance(self) -> Dict[str, Any]:
        """
        Validate privacy compliance.

        Returns:
            Compliance report
        """
        issues = []

        # Check for exhausted budgets
        for client_id, budget in self._privacy_budget_used.items():
            if budget > 4.0:  # Warning threshold
                issues.append({
                    "type": "high_privacy_budget",
                    "client": self._hash_client(client_id),
                    "budget_used": budget,
                })

        # Check for failed shares
        failed_shares = [
            e for e in self._audit_log
            if e.status == ShareStatus.BLOCKED
        ]
        if failed_shares:
            issues.append({
                "type": "blocked_shares",
                "count": len(failed_shares),
            })

        return {
            "compliant": len(issues) == 0,
            "issues": issues,
            "recommendations": self._get_recommendations(issues),
        }

    def _contains_sensitive_data(self, data: Dict[str, Any]) -> bool:
        """Check if data contains sensitive information"""
        data_str = json.dumps(data).lower()

        sensitive_patterns = [
            "email", "phone", "ssn", "credit_card",
            "password", "api_key", "secret", "token",
            "patient", "medical_record", "phi",
            "social_security", "date_of_birth",
            "home_address", "ip_address",
            "@",  # Email address indicator
        ]

        for pattern in sensitive_patterns:
            if pattern in data_str:
                # Check if it's actually a value (not just a key name)
                if f'"{pattern}":' not in data_str and f'"{pattern}": null' not in data_str:
                    return True

        return False

    def _laplace_noise(self, scale: float) -> float:
        """Generate Laplace noise"""
        # Inverse CDF method
        u = random.random() - 0.5
        return -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))

    def _create_qi_key(
        self,
        record: Dict[str, Any],
        quasi_identifiers: List[str]
    ) -> str:
        """Create key from quasi-identifiers"""
        values = []
        for qi in quasi_identifiers:
            value = record.get(qi, "NULL")
            values.append(str(value))
        return "|".join(values)

    def _hash_client(self, client_id: str) -> str:
        """Hash client ID for audit log"""
        return hashlib.sha256(client_id.encode()).hexdigest()[:12]

    def _generate_share_id(self) -> str:
        """Generate unique share ID"""
        timestamp = datetime.now().isoformat()
        random_salt = random.randint(0, 10000)
        content = f"{timestamp}_{random_salt}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_recommendations(self, issues: List[Dict]) -> List[str]:
        """Generate recommendations based on issues"""
        recommendations = []

        for issue in issues:
            if issue["type"] == "high_privacy_budget":
                recommendations.append(
                    f"Consider reducing data collection for client with high privacy budget"
                )
            elif issue["type"] == "blocked_shares":
                recommendations.append(
                    "Review blocked shares to identify common rejection reasons"
                )

        return recommendations


def create_privacy_preserving_share(
    privacy_level: PrivacyLevel = PrivacyLevel.STANDARD
) -> PrivacyPreservingShare:
    """
    Factory function to create privacy-preserving share.

    Args:
        privacy_level: Desired privacy level

    Returns:
        Configured PrivacyPreservingShare instance
    """
    configs = {
        PrivacyLevel.STANDARD: (
            DifferentialPrivacyConfig(epsilon=1.0),
            KAnonymityConfig(k=3),
        ),
        PrivacyLevel.HIGH: (
            DifferentialPrivacyConfig(epsilon=0.5),
            KAnonymityConfig(k=5),
        ),
        PrivacyLevel.MAXIMUM: (
            DifferentialPrivacyConfig(epsilon=0.1),
            KAnonymityConfig(k=10),
        ),
    }

    dp_config, k_config = configs.get(
        privacy_level,
        configs[PrivacyLevel.STANDARD]
    )

    return PrivacyPreservingShare(
        dp_config=dp_config,
        k_config=k_config,
        privacy_level=privacy_level,
    )
