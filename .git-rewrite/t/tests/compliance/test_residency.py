"""
Data Residency Tests.

Tests for data residency enforcement and GDPR compliance.
"""

import pytest
from datetime import datetime
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.compliance.residency.residency_enforcer import (
    ResidencyEnforcer,
    ResidencyConfig,
    ResidencyViolation,
    Region,
    get_residency_enforcer
)
from backend.compliance.residency.region_router import (
    RegionRouter,
    RoutingDecision,
    get_region_router
)
from backend.compliance.residency.sovereignty_checker import (
    SovereigntyChecker,
    SovereigntyCheck,
    ComplianceFramework,
    get_sovereignty_checker
)
from backend.compliance.residency.gdpr_export import (
    GDPrexport,
    ExportRequest,
    ExportStatus,
    get_gdpr_export
)


class TestResidencyEnforcer:
    """Test residency enforcer."""

    def test_enforcer_creation(self):
        """Test creating a residency enforcer."""
        enforcer = ResidencyEnforcer()
        assert enforcer is not None
        assert enforcer.config.enabled is True

    def test_register_client(self):
        """Test registering a client to a region."""
        enforcer = ResidencyEnforcer()
        enforcer.register_client("client_001", Region.EU)

        region = enforcer.get_client_region("client_001")
        assert region == Region.EU

    def test_validate_access_allowed(self):
        """Test access is allowed when region matches."""
        enforcer = ResidencyEnforcer()
        enforcer.register_client("client_001", Region.EU)

        allowed = enforcer.validate_access(
            client_id="client_001",
            source_region=Region.EU,
            data_type="personal_data"
        )

        assert allowed is True

    def test_validate_access_blocked(self):
        """Test cross-region access is blocked."""
        enforcer = ResidencyEnforcer(config=ResidencyConfig(strict_mode=False))
        enforcer.register_client("client_001", Region.EU)

        allowed = enforcer.validate_access(
            client_id="client_001",
            source_region=Region.US,
            data_type="personal_data"
        )

        assert allowed is False

    def test_validate_access_strict_mode_raises(self):
        """Test strict mode raises exception on violation."""
        enforcer = ResidencyEnforcer(config=ResidencyConfig(strict_mode=True))
        enforcer.register_client("client_001", Region.EU)

        with pytest.raises(ResidencyViolation):
            enforcer.validate_access(
                client_id="client_001",
                source_region=Region.US,
                data_type="personal_data"
            )

    def test_violations_recorded(self):
        """Test that violations are recorded."""
        enforcer = ResidencyEnforcer(config=ResidencyConfig(strict_mode=False))
        enforcer.register_client("client_001", Region.EU)

        enforcer.validate_access(
            client_id="client_001",
            source_region=Region.US,
            data_type="personal_data"
        )

        violations = enforcer.get_violations()
        assert len(violations) == 1
        assert violations[0].client_id == "client_001"

    def test_access_log(self):
        """Test access logging."""
        enforcer = ResidencyEnforcer()
        enforcer.register_client("client_001", Region.EU)

        enforcer.validate_access(
            client_id="client_001",
            source_region=Region.EU,
            data_type="personal_data"
        )

        log = enforcer.get_access_log()
        assert len(log) == 1

    def test_stats(self):
        """Test statistics."""
        enforcer = ResidencyEnforcer()
        enforcer.register_client("client_001", Region.EU)
        enforcer.register_client("client_002", Region.US)

        stats = enforcer.get_stats()
        assert stats["total_clients"] == 2
        assert stats["clients_by_region"]["eu-west-1"] == 1
        assert stats["clients_by_region"]["us-east-1"] == 1


class TestRegionRouter:
    """Test region router."""

    def test_router_creation(self):
        """Test creating a region router."""
        router = RegionRouter()
        assert router is not None

    def test_register_client(self):
        """Test registering a client."""
        router = RegionRouter()
        router.register_client("client_001", Region.EU)

        region = router.get_region("client_001")
        assert region == Region.EU

    def test_route_to_assigned_region(self):
        """Test routing to assigned region."""
        router = RegionRouter()
        router.register_client("client_001", Region.EU)

        decision = router.route("client_001")

        assert decision.selected_region == Region.EU
        assert decision.reason == "Assigned region"

    def test_route_unregistered_client(self):
        """Test routing for unregistered client."""
        router = RegionRouter()

        decision = router.route("unknown_client")

        assert decision.selected_region in [Region.EU, Region.US, Region.APAC]
        assert decision.reason == "Best available region"

    def test_route_with_failover(self):
        """Test routing with failover."""
        router = RegionRouter()
        router.register_client("client_001", Region.EU)
        router.update_region_health(Region.EU, False)  # Mark EU as unhealthy

        decision = router.route_with_failover("client_001")

        assert decision.selected_region != Region.EU
        assert decision.reason == "Failover"

    def test_update_region_health(self):
        """Test updating region health."""
        router = RegionRouter()

        router.update_region_health(Region.EU, False)
        healthy = router.get_healthy_regions()

        assert Region.EU not in healthy

    def test_get_all_regions(self):
        """Test getting all regions."""
        router = RegionRouter()
        regions = router.get_all_regions()

        assert Region.EU in regions
        assert Region.US in regions
        assert Region.APAC in regions

    def test_routing_stats(self):
        """Test routing statistics."""
        router = RegionRouter()
        router.register_client("client_001", Region.EU)
        router.route("client_001")

        stats = router.get_routing_stats()
        assert stats["total_routes"] == 1
        assert stats["registered_clients"] == 1


class TestSovereigntyChecker:
    """Test sovereignty checker."""

    def test_checker_creation(self):
        """Test creating a sovereignty checker."""
        checker = SovereigntyChecker()
        assert checker is not None

    def test_register_client(self):
        """Test registering a client."""
        checker = SovereigntyChecker()
        checker.register_client("client_001", Region.EU)

        region = checker.get_client_region("client_001")
        assert region == Region.EU

    def test_check_sovereignty_compliant(self):
        """Test sovereignty check for compliant client."""
        checker = SovereigntyChecker()
        checker.register_client("client_001", Region.EU)

        result = checker.check_sovereignty("client_001")

        assert result.compliant is True
        assert result.framework == ComplianceFramework.GDPR

    def test_check_sovereignty_non_compliant(self):
        """Test sovereignty check for non-compliant data types."""
        checker = SovereigntyChecker()
        checker.register_client("client_001", Region.US)

        result = checker.check_sovereignty(
            client_id="client_001",
            data_types=["restricted_health_data"]
        )

        assert result.compliant is False
        assert len(result.violations) > 0

    def test_get_compliance_framework(self):
        """Test getting compliance framework for region."""
        checker = SovereigntyChecker()

        framework = checker.get_compliance_framework(Region.EU)
        assert framework == ComplianceFramework.GDPR

        framework = checker.get_compliance_framework(Region.US)
        assert framework == ComplianceFramework.CCPA

    def test_get_region_restrictions(self):
        """Test getting region restrictions."""
        checker = SovereigntyChecker()

        eu_restrictions = checker.get_region_restrictions(Region.EU)
        assert "no_transfer_outside_eu" in eu_restrictions

    def test_run_audit(self):
        """Test running a sovereignty audit."""
        checker = SovereigntyChecker()
        checker.register_client("client_001", Region.EU)
        checker.register_client("client_002", Region.US)

        audit = checker.run_audit()

        assert audit.checks_performed == 2
        assert audit.audit_id.startswith("audit-")

    def test_stats(self):
        """Test statistics."""
        checker = SovereigntyChecker()
        checker.register_client("client_001", Region.EU)
        checker.check_sovereignty("client_001")

        stats = checker.get_stats()
        assert stats["total_clients"] == 1
        assert stats["total_checks"] == 1


class TestGDPrexport:
    """Test GDPR export handler."""

    def test_export_handler_creation(self):
        """Test creating an export handler."""
        handler = GDPrexport()
        assert handler is not None

    def test_register_client(self):
        """Test registering a client."""
        handler = GDPrexport()
        handler.register_client("client_001", Region.EU)

        region = handler.get_client_region("client_001")
        assert region == Region.EU

    def test_request_export(self):
        """Test requesting an export."""
        handler = GDPrexport()
        handler.register_client("client_001", Region.EU)

        request = handler.request_export("client_001")

        assert request.client_id == "client_001"
        assert request.region == Region.EU
        assert request.status == ExportStatus.PENDING

    def test_process_export(self):
        """Test processing an export."""
        handler = GDPrexport()
        handler.register_client("client_001", Region.EU)

        request = handler.request_export("client_001")
        processed = handler.process_export(request.request_id)

        assert processed.status == ExportStatus.COMPLETED
        assert processed.data is not None
        assert processed.data["region"] == "eu-west-1"

    def test_export_only_from_assigned_region(self):
        """Test that export only includes data from assigned region."""
        handler = GDPrexport()
        handler.register_client("client_001", Region.US)

        request = handler.request_export("client_001")
        processed = handler.process_export(request.request_id)

        assert processed.data["region"] == "us-east-1"

    def test_get_export_json(self):
        """Test getting export as JSON."""
        handler = GDPrexport()
        handler.register_client("client_001", Region.EU)

        request = handler.request_export("client_001")
        handler.process_export(request.request_id)

        json_data = handler.get_export_json(request.request_id)

        assert json_data is not None
        assert "client_id" in json_data
        assert "eu-west-1" in json_data

    def test_create_inventory(self):
        """Test creating a data inventory."""
        handler = GDPrexport()
        handler.register_client("client_001", Region.EU)

        inventory = handler.create_inventory(
            client_id="client_001",
            data_types=["profile", "tickets", "interactions"],
            total_records=100,
            size_bytes=50000
        )

        assert inventory.client_id == "client_001"
        assert inventory.region == Region.EU
        assert inventory.total_records == 100

    def test_export_unregistered_client_raises(self):
        """Test that export for unregistered client raises error."""
        handler = GDPrexport()

        with pytest.raises(ValueError):
            handler.request_export("unknown_client")

    def test_stats(self):
        """Test statistics."""
        handler = GDPrexport()
        handler.register_client("client_001", Region.EU)
        handler.request_export("client_001")

        stats = handler.get_stats()
        assert stats["total_requests"] == 1
        assert stats["pending"] == 1


class TestCrossRegionIsolation:
    """Test cross-region isolation (CRITICAL)."""

    def test_eu_client_blocked_from_us(self):
        """Test EU client cannot access US region data."""
        enforcer = ResidencyEnforcer(config=ResidencyConfig(strict_mode=False))
        enforcer.register_client("eu_client", Region.EU)

        allowed = enforcer.validate_access(
            client_id="eu_client",
            source_region=Region.US,
            data_type="personal_data"
        )

        assert allowed is False, "EU client should NOT access US region"

    def test_us_client_blocked_from_eu(self):
        """Test US client cannot access EU region data."""
        enforcer = ResidencyEnforcer(config=ResidencyConfig(strict_mode=False))
        enforcer.register_client("us_client", Region.US)

        allowed = enforcer.validate_access(
            client_id="us_client",
            source_region=Region.EU,
            data_type="personal_data"
        )

        assert allowed is False, "US client should NOT access EU region"

    def test_export_from_correct_region_only(self):
        """Test GDPR export only returns data from assigned region."""
        handler = GDPrexport()

        # Register clients in different regions
        handler.register_client("eu_client", Region.EU)
        handler.register_client("us_client", Region.US)

        # Export EU client data
        eu_request = handler.request_export("eu_client")
        eu_export = handler.process_export(eu_request.request_id)

        # Export US client data
        us_request = handler.request_export("us_client")
        us_export = handler.process_export(us_request.request_id)

        # Verify region isolation
        assert eu_export.data["region"] == "eu-west-1"
        assert us_export.data["region"] == "us-east-1"

    def test_no_data_leaks_in_violations(self):
        """Test that violations don't leak data."""
        enforcer = ResidencyEnforcer(config=ResidencyConfig(strict_mode=False))
        enforcer.register_client("client_001", Region.EU)

        # Attempt cross-region access
        enforcer.validate_access(
            client_id="client_001",
            source_region=Region.US,
            data_type="personal_data"
        )

        violations = enforcer.get_violations()

        # Verify violation was recorded but no data leaked
        assert len(violations) == 1
        assert violations[0].source_region == Region.US
        assert violations[0].target_region == Region.EU


class TestResidencyModuleStructure:
    """Test residency module structure."""

    def test_residency_module_exists(self):
        """Test that residency module exists."""
        from backend.compliance.residency import ResidencyEnforcer, RegionRouter
        assert ResidencyEnforcer is not None
        assert RegionRouter is not None

    def test_all_exports(self):
        """Test all module exports."""
        from backend.compliance.residency import (
            ResidencyEnforcer,
            RegionRouter,
            SovereigntyChecker,
            GDPrexport
        )

        assert callable(ResidencyEnforcer)
        assert callable(RegionRouter)
        assert callable(SovereigntyChecker)
        assert callable(GDPrexport)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
