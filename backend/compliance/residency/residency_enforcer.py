"""
Residency Enforcer for Data Residency Compliance.

Enforces data stays in assigned region:
- Blocks cross-region data access
- Validates region assignment on read/write
- Logs all cross-region attempts
- Alerts on violations
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Region(str, Enum):
    """Available regions for data residency."""
    EU = "eu-west-1"
    US = "us-east-1"
    APAC = "ap-southeast-1"


class ResidencyViolation(Exception):
    """Exception raised when data residency is violated."""
    pass


@dataclass
class ResidencyConfig:
    """Configuration for residency enforcement."""
    enabled: bool = True
    strict_mode: bool = True
    log_all_access: bool = True
    alert_on_violation: bool = True
    max_violations_before_block: int = 3


@dataclass
class AccessAttempt:
    """Record of a data access attempt."""
    client_id: str
    source_region: Region
    target_region: Region
    data_type: str
    allowed: bool
    timestamp: datetime = field(default_factory=datetime.now)
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "client_id": self.client_id,
            "source_region": self.source_region.value,
            "target_region": self.target_region.value,
            "data_type": self.data_type,
            "allowed": self.allowed,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason
        }


@dataclass
class ViolationRecord:
    """Record of a residency violation."""
    client_id: str
    source_region: Region
    target_region: Region
    data_type: str
    violation_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "client_id": self.client_id,
            "source_region": self.source_region.value,
            "target_region": self.target_region.value,
            "data_type": self.data_type,
            "violation_type": self.violation_type,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved
        }


class ResidencyEnforcer:
    """
    Enforces data residency requirements.

    Features:
    - Block cross-region data access
    - Validate region assignment on read/write
    - Log all cross-region attempts
    - Alert on violations
    """

    def __init__(
        self,
        config: Optional[ResidencyConfig] = None,
        client_region_mapping: Optional[Dict[str, Region]] = None
    ):
        """
        Initialize the residency enforcer.

        Args:
            config: Residency configuration
            client_region_mapping: Mapping of client IDs to regions
        """
        self.config = config or ResidencyConfig()
        self._client_regions: Dict[str, Region] = client_region_mapping or {}
        self._access_log: List[AccessAttempt] = []
        self._violations: List[ViolationRecord] = []
        self._violation_counts: Dict[str, int] = {}

    def register_client(self, client_id: str, region: Region) -> None:
        """
        Register a client with their assigned region.

        Args:
            client_id: Client identifier
            region: Assigned region for client data
        """
        self._client_regions[client_id] = region
        logger.info(f"Registered client {client_id} to region {region.value}")

    def get_client_region(self, client_id: str) -> Optional[Region]:
        """
        Get the assigned region for a client.

        Args:
            client_id: Client identifier

        Returns:
            Assigned region or None if not registered
        """
        return self._client_regions.get(client_id)

    def validate_access(
        self,
        client_id: str,
        source_region: Region,
        data_type: str,
        operation: str = "read"
    ) -> bool:
        """
        Validate if access is allowed based on residency rules.

        Args:
            client_id: Client identifier
            source_region: Region where access is attempted
            data_type: Type of data being accessed
            operation: Operation type (read/write)

        Returns:
            True if access is allowed

        Raises:
            ResidencyViolation: If access violates residency rules
        """
        if not self.config.enabled:
            return True

        target_region = self.get_client_region(client_id)

        if target_region is None:
            # Client not registered - allow with warning
            logger.warning(f"Client {client_id} not registered for any region")
            return True

        allowed = source_region == target_region

        # Log the access attempt
        attempt = AccessAttempt(
            client_id=client_id,
            source_region=source_region,
            target_region=target_region,
            data_type=data_type,
            allowed=allowed,
            reason="Region match" if allowed else "Cross-region access blocked"
        )

        if self.config.log_all_access:
            self._access_log.append(attempt)
            logger.info(f"Access attempt: {attempt.to_dict()}")

        if not allowed:
            # Record violation
            self._record_violation(
                client_id=client_id,
                source_region=source_region,
                target_region=target_region,
                data_type=data_type,
                violation_type="cross_region_access"
            )

            if self.config.strict_mode:
                raise ResidencyViolation(
                    f"Cross-region access blocked: client {client_id} "
                    f"(assigned: {target_region.value}, attempted: {source_region.value})"
                )

        return allowed

    def validate_write(
        self,
        client_id: str,
        target_region: Region,
        data_type: str
    ) -> bool:
        """
        Validate if write operation is allowed.

        Args:
            client_id: Client identifier
            target_region: Region where data will be written
            data_type: Type of data being written

        Returns:
            True if write is allowed

        Raises:
            ResidencyViolation: If write violates residency rules
        """
        if not self.config.enabled:
            return True

        assigned_region = self.get_client_region(client_id)

        if assigned_region is None:
            logger.warning(f"Client {client_id} not registered for any region")
            return True

        allowed = target_region == assigned_region

        if not allowed:
            self._record_violation(
                client_id=client_id,
                source_region=target_region,
                target_region=assigned_region,
                data_type=data_type,
                violation_type="cross_region_write"
            )

            if self.config.strict_mode:
                raise ResidencyViolation(
                    f"Cross-region write blocked: client {client_id} "
                    f"(assigned: {assigned_region.value}, attempted: {target_region.value})"
                )

        return allowed

    def _record_violation(
        self,
        client_id: str,
        source_region: Region,
        target_region: Region,
        data_type: str,
        violation_type: str
    ) -> None:
        """Record a residency violation."""
        violation = ViolationRecord(
            client_id=client_id,
            source_region=source_region,
            target_region=target_region,
            data_type=data_type,
            violation_type=violation_type
        )
        self._violations.append(violation)

        # Update violation count
        key = f"{client_id}:{violation_type}"
        self._violation_counts[key] = self._violation_counts.get(key, 0) + 1

        if self.config.alert_on_violation:
            logger.warning(
                f"RESIDENCY VIOLATION: {violation_type} for client {client_id} "
                f"(source: {source_region.value}, target: {target_region.value})"
            )

    def get_violations(self, client_id: Optional[str] = None) -> List[ViolationRecord]:
        """
        Get violation records.

        Args:
            client_id: Optional client ID to filter by

        Returns:
            List of violation records
        """
        if client_id:
            return [v for v in self._violations if v.client_id == client_id]
        return self._violations.copy()

    def get_access_log(self, client_id: Optional[str] = None) -> List[AccessAttempt]:
        """
        Get access log.

        Args:
            client_id: Optional client ID to filter by

        Returns:
            List of access attempts
        """
        if client_id:
            return [a for a in self._access_log if a.client_id == client_id]
        return self._access_log.copy()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get residency enforcement statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_clients": len(self._client_regions),
            "total_access_attempts": len(self._access_log),
            "total_violations": len(self._violations),
            "allowed_accesses": len([a for a in self._access_log if a.allowed]),
            "blocked_accesses": len([a for a in self._access_log if not a.allowed]),
            "clients_by_region": {
                region.value: len([c for c, r in self._client_regions.items() if r == region])
                for region in Region
            },
            "violation_counts": dict(self._violation_counts)
        }

    def clear_logs(self) -> None:
        """Clear access logs and violations."""
        self._access_log.clear()
        self._violations.clear()
        self._violation_counts.clear()
        logger.info("Residency logs cleared")


def get_residency_enforcer(
    enabled: bool = True,
    strict_mode: bool = True
) -> ResidencyEnforcer:
    """
    Factory function to create a residency enforcer.

    Args:
        enabled: Whether enforcement is enabled
        strict_mode: Whether to raise exceptions on violations

    Returns:
        Configured ResidencyEnforcer instance
    """
    config = ResidencyConfig(
        enabled=enabled,
        strict_mode=strict_mode
    )
    return ResidencyEnforcer(config=config)
