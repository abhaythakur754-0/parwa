"""
Sovereignty Checker for Data Residency.

Checks data sovereignty requirements:
- Validate client region assignment
- Check compliance per region
- Audit sovereignty status
- Report violations
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Region(str, Enum):
    """Available regions."""
    EU = "eu-west-1"
    US = "us-east-1"
    APAC = "ap-southeast-1"


class ComplianceFramework(str, Enum):
    """Compliance frameworks by region."""
    GDPR = "GDPR"  # EU
    CCPA = "CCPA"  # US
    APAC_DATA_LAWS = "APAC_DATA_LAWS"  # APAC


@dataclass
class SovereigntyRule:
    """Rule for data sovereignty."""
    region: Region
    framework: ComplianceFramework
    data_types: List[str]
    restrictions: List[str]
    retention_days: int


@dataclass
class SovereigntyCheck:
    """Result of a sovereignty check."""
    client_id: str
    region: Region
    compliant: bool
    framework: ComplianceFramework
    violations: List[str]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "client_id": self.client_id,
            "region": self.region.value,
            "compliant": self.compliant,
            "framework": self.framework.value,
            "violations": self.violations,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class SovereigntyAudit:
    """Audit record for sovereignty."""
    audit_id: str
    timestamp: datetime
    checks_performed: int
    compliant_clients: int
    non_compliant_clients: int
    violations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp.isoformat(),
            "checks_performed": self.checks_performed,
            "compliant_clients": self.compliant_clients,
            "non_compliant_clients": self.non_compliant_clients,
            "violations": self.violations
        }


class SovereigntyChecker:
    """
    Checks data sovereignty requirements.

    Features:
    - Check data sovereignty requirements
    - Validate client region assignment
    - Check compliance per region
    - Audit sovereignty status
    - Report violations
    """

    # Default sovereignty rules by region
    DEFAULT_RULES: Dict[Region, SovereigntyRule] = {
        Region.EU: SovereigntyRule(
            region=Region.EU,
            framework=ComplianceFramework.GDPR,
            data_types=["personal_data", "pii", "financial", "health"],
            restrictions=[
                "no_transfer_outside_eu",
                "encryption_required",
                "right_to_erasure",
                "data_portability"
            ],
            retention_days=90
        ),
        Region.US: SovereigntyRule(
            region=Region.US,
            framework=ComplianceFramework.CCPA,
            data_types=["personal_data", "pii", "financial"],
            restrictions=[
                "consumer_rights",
                "opt_out_rights",
                "disclosure_requirements"
            ],
            retention_days=90
        ),
        Region.APAC: SovereigntyRule(
            region=Region.APAC,
            framework=ComplianceFramework.APAC_DATA_LAWS,
            data_types=["personal_data", "pii"],
            restrictions=[
                "local_storage_required",
                "consent_requirements"
            ],
            retention_days=90
        )
    }

    def __init__(
        self,
        client_region_mapping: Optional[Dict[str, Region]] = None,
        custom_rules: Optional[Dict[Region, SovereigntyRule]] = None
    ):
        """
        Initialize the sovereignty checker.

        Args:
            client_region_mapping: Mapping of client IDs to regions
            custom_rules: Custom sovereignty rules
        """
        self._client_regions: Dict[str, Region] = client_region_mapping or {}
        self._rules: Dict[Region, SovereigntyRule] = custom_rules or self.DEFAULT_RULES
        self._checks: List[SovereigntyCheck] = []
        self._audits: List[SovereigntyAudit] = []

    def register_client(self, client_id: str, region: Region) -> None:
        """
        Register a client with their assigned region.

        Args:
            client_id: Client identifier
            region: Assigned region
        """
        self._client_regions[client_id] = region
        logger.info(f"Registered client {client_id} to region {region.value}")

    def get_client_region(self, client_id: str) -> Optional[Region]:
        """Get the assigned region for a client."""
        return self._client_regions.get(client_id)

    def check_sovereignty(
        self,
        client_id: str,
        data_types: Optional[List[str]] = None,
        region: Optional[Region] = None
    ) -> SovereigntyCheck:
        """
        Check sovereignty compliance for a client.

        Args:
            client_id: Client identifier
            data_types: Types of data being stored
            region: Region to check (uses assigned if not provided)

        Returns:
            SovereigntyCheck result
        """
        assigned_region = region or self.get_client_region(client_id)

        if not assigned_region:
            return SovereigntyCheck(
                client_id=client_id,
                region=Region.EU,  # Default
                compliant=False,
                framework=ComplianceFramework.GDPR,
                violations=["Client not assigned to any region"]
            )

        rule = self._rules.get(assigned_region)
        if not rule:
            return SovereigntyCheck(
                client_id=client_id,
                region=assigned_region,
                compliant=False,
                framework=ComplianceFramework.GDPR,
                violations=[f"No sovereignty rules for region {assigned_region.value}"]
            )

        violations = []

        # Check data types
        if data_types:
            for data_type in data_types:
                if data_type not in rule.data_types:
                    violations.append(
                        f"Data type '{data_type}' not allowed in region {assigned_region.value}"
                    )

        # Check client assignment
        if client_id not in self._client_regions:
            violations.append("Client not properly registered for region")

        compliant = len(violations) == 0

        check = SovereigntyCheck(
            client_id=client_id,
            region=assigned_region,
            compliant=compliant,
            framework=rule.framework,
            violations=violations
        )

        self._checks.append(check)

        if not compliant:
            logger.warning(
                f"Sovereignty check failed for {client_id}: {violations}"
            )

        return check

    def validate_region_assignment(self, client_id: str, region: Region) -> bool:
        """
        Validate that a client is properly assigned to a region.

        Args:
            client_id: Client identifier
            region: Expected region

        Returns:
            True if assignment is valid
        """
        assigned = self.get_client_region(client_id)
        if assigned != region:
            logger.warning(
                f"Region assignment mismatch for {client_id}: "
                f"expected {region.value}, got {assigned.value if assigned else 'None'}"
            )
            return False
        return True

    def get_compliance_framework(self, region: Region) -> Optional[ComplianceFramework]:
        """Get the compliance framework for a region."""
        rule = self._rules.get(region)
        return rule.framework if rule else None

    def get_region_restrictions(self, region: Region) -> List[str]:
        """Get restrictions for a region."""
        rule = self._rules.get(region)
        return rule.restrictions if rule else []

    def run_audit(self) -> SovereigntyAudit:
        """
        Run a full sovereignty audit.

        Returns:
            SovereigntyAudit with results
        """
        audit_id = f"audit-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        checks_performed = 0
        compliant = 0
        non_compliant = 0
        all_violations = []

        for client_id, region in self._client_regions.items():
            check = self.check_sovereignty(client_id)
            checks_performed += 1

            if check.compliant:
                compliant += 1
            else:
                non_compliant += 1
                all_violations.extend([
                    f"{client_id}: {v}" for v in check.violations
                ])

        audit = SovereigntyAudit(
            audit_id=audit_id,
            timestamp=datetime.now(),
            checks_performed=checks_performed,
            compliant_clients=compliant,
            non_compliant_clients=non_compliant,
            violations=all_violations
        )

        self._audits.append(audit)

        logger.info(
            f"Sovereignty audit {audit_id} completed: "
            f"{compliant} compliant, {non_compliant} non-compliant"
        )

        return audit

    def get_checks(self, client_id: Optional[str] = None) -> List[SovereigntyCheck]:
        """Get sovereignty checks."""
        if client_id:
            return [c for c in self._checks if c.client_id == client_id]
        return self._checks.copy()

    def get_audits(self) -> List[SovereigntyAudit]:
        """Get all audits."""
        return self._audits.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get sovereignty checker statistics."""
        total_checks = len(self._checks)
        compliant_checks = len([c for c in self._checks if c.compliant])

        return {
            "total_clients": len(self._client_regions),
            "total_checks": total_checks,
            "compliant_checks": compliant_checks,
            "non_compliant_checks": total_checks - compliant_checks,
            "compliance_rate": compliant_checks / total_checks if total_checks > 0 else 1.0,
            "total_audits": len(self._audits),
            "clients_by_region": {
                region.value: len([c for c, r in self._client_regions.items() if r == region])
                for region in Region
            }
        }


def get_sovereignty_checker() -> SovereigntyChecker:
    """Factory function to create a sovereignty checker."""
    return SovereigntyChecker()
