"""
Unit tests for PARWA Compliance Layer.

Tests cover:
- JurisdictionManager: Jurisdiction-based compliance rules
- SLACalculator: SLA breach detection and calculation
- GDPREngine: GDPR data export and erasure
- HealthcareGuard: BAA verification and PHI protection
"""
import pytest
from datetime import datetime, timedelta, time

from shared.compliance.jurisdiction import (
    JurisdictionManager,
    JurisdictionCode,
    JurisdictionRules,
    ConsentType,
    CommunicationType,
    TimeWindow,
)
from shared.compliance.sla_calculator import (
    SLACalculator,
    SLATier,
    SLAType,
    SLABreachStatus,
    SLAPolicy,
)
from shared.compliance.gdpr_engine import (
    GDPREngine,
    GDPRRequestType,
    GDPRRequestStatus,
    PIIFieldType,
)
from shared.compliance.healthcare_guard import (
    HealthcareGuard,
    BAAStatus,
    BAARecord,
    PHIType,
    AccessPurpose,
    HealthcareClientType,
)


# =============================================================================
# Jurisdiction Manager Tests
# =============================================================================

class TestJurisdictionManager:
    """Tests for Jurisdiction Manager."""

    def test_jurisdiction_manager_initialization(self):
        """Test jurisdiction manager initializes correctly."""
        manager = JurisdictionManager()

        assert manager is not None
        assert len(manager._rules) >= 8  # At least 8 jurisdictions

    def test_get_us_rules(self):
        """Test getting US jurisdiction rules."""
        manager = JurisdictionManager()
        rules = manager.get_rules(JurisdictionCode.US)

        assert rules.jurisdiction_code == JurisdictionCode.US
        assert rules.regulation_name == "TCPA (Telephone Consumer Protection Act)"
        assert rules.consent_type_required == ConsentType.EXPRESS_WRITTEN
        assert rules.ai_disclosure_required is True

    def test_get_in_rules(self):
        """Test getting India (IN) jurisdiction rules."""
        manager = JurisdictionManager()
        rules = manager.get_rules(JurisdictionCode.IN)

        assert rules.jurisdiction_code == JurisdictionCode.IN
        assert rules.regulation_name == "DPDPA (Digital Personal Data Protection Act)"
        assert rules.data_residency_required is True

    def test_detect_jurisdiction_from_country_code(self):
        """Test jurisdiction detection from country code."""
        manager = JurisdictionManager()

        # Test various country codes
        assert manager.detect_jurisdiction(country_code="US") == JurisdictionCode.US
        assert manager.detect_jurisdiction(country_code="IN") == JurisdictionCode.IN
        assert manager.detect_jurisdiction(country_code="UK") == JurisdictionCode.UK
        assert manager.detect_jurisdiction(country_code="EU") == JurisdictionCode.EU

    def test_detect_jurisdiction_from_phone(self):
        """Test jurisdiction detection from phone number."""
        manager = JurisdictionManager()

        # US phone
        assert manager.detect_jurisdiction(phone_number="+11234567890") == JurisdictionCode.US

        # India phone
        assert manager.detect_jurisdiction(phone_number="+919876543210") == JurisdictionCode.IN

    def test_check_compliance_all_conditions_met(self):
        """Test compliance check when all conditions are met."""
        manager = JurisdictionManager()

        # Pass a time within allowed window (8:00 - 21:00)
        result = manager.check_compliance(
            jurisdiction=JurisdictionCode.US,
            communication_type=CommunicationType.SMS,
            has_consent=True,
            consent_type=ConsentType.EXPRESS_WRITTEN,
            check_time=time(12, 0),  # Noon - within allowed window
            contacts_today=1,
            is_on_dnc_list=False
        )

        assert result.is_compliant is True
        assert len(result.violations) == 0

    def test_check_compliance_missing_consent(self):
        """Test compliance check when consent is missing."""
        manager = JurisdictionManager()

        result = manager.check_compliance(
            jurisdiction=JurisdictionCode.US,
            communication_type=CommunicationType.SMS,
            has_consent=False,
            contacts_today=1,
            is_on_dnc_list=False
        )

        assert result.is_compliant is False
        assert "Consent required" in " ".join(result.violations)

    def test_check_compliance_dnc_list(self):
        """Test compliance check when on DNC list."""
        manager = JurisdictionManager()

        result = manager.check_compliance(
            jurisdiction=JurisdictionCode.US,
            communication_type=CommunicationType.VOICE,
            has_consent=True,
            consent_type=ConsentType.EXPRESS_WRITTEN,
            contacts_today=1,
            is_on_dnc_list=True
        )

        assert result.is_compliant is False
        assert "Do Not Call" in " ".join(result.violations)

    def test_check_compliance_max_contacts_exceeded(self):
        """Test compliance check when max contacts exceeded."""
        manager = JurisdictionManager()
        rules = manager.get_rules(JurisdictionCode.US)

        result = manager.check_compliance(
            jurisdiction=JurisdictionCode.US,
            communication_type=CommunicationType.SMS,
            has_consent=True,
            consent_type=ConsentType.EXPRESS_WRITTEN,
            contacts_today=rules.max_contacts_per_day + 1,
            is_on_dnc_list=False
        )

        assert result.is_compliant is False
        assert "Maximum daily contacts" in " ".join(result.violations)

    def test_get_disclosure_text(self):
        """Test disclosure text generation."""
        manager = JurisdictionManager()

        text = manager.get_disclosure_text(JurisdictionCode.US, include_ai_disclosure=True)

        assert "AI assistant" in text
        assert len(text) > 0

    def test_get_opt_out_keywords(self):
        """Test opt-out keyword retrieval."""
        manager = JurisdictionManager()

        keywords = manager.get_opt_out_keywords(JurisdictionCode.US)

        assert "STOP" in keywords
        assert "CANCEL" in keywords
        assert len(keywords) >= 3

    def test_is_opt_out_message(self):
        """Test opt-out message detection."""
        manager = JurisdictionManager()

        assert manager.is_opt_out_message("STOP", JurisdictionCode.US) is True
        assert manager.is_opt_out_message("Please stop", JurisdictionCode.US) is True
        assert manager.is_opt_out_message("Hello", JurisdictionCode.US) is False

    def test_stats_tracking(self):
        """Test statistics tracking."""
        manager = JurisdictionManager()

        manager.check_compliance(
            jurisdiction=JurisdictionCode.US,
            communication_type=CommunicationType.SMS,
            has_consent=True
        )

        stats = manager.get_stats()
        assert stats["checks_performed"] == 1


class TestTimeWindow:
    """Tests for TimeWindow."""

    def test_time_window_within(self):
        """Test time within window."""
        window = TimeWindow(start_hour=8, end_hour=21)

        assert window.is_within_window(time(12, 0)) is True
        assert window.is_within_window(time(9, 30)) is True
        assert window.is_within_window(time(20, 59)) is True

    def test_time_window_outside(self):
        """Test time outside window."""
        window = TimeWindow(start_hour=8, end_hour=21)

        assert window.is_within_window(time(7, 59)) is False
        assert window.is_within_window(time(21, 1)) is False
        assert window.is_within_window(time(23, 0)) is False

    def test_time_window_midnight_crossing(self):
        """Test window that crosses midnight."""
        window = TimeWindow(start_hour=22, end_hour=6)

        assert window.is_within_window(time(23, 0)) is True
        assert window.is_within_window(time(3, 0)) is True
        assert window.is_within_window(time(12, 0)) is False


# =============================================================================
# SLA Calculator Tests
# =============================================================================

class TestSLACalculator:
    """Tests for SLA Calculator."""

    def test_sla_calculator_initialization(self):
        """Test SLA calculator initializes correctly."""
        calc = SLACalculator()

        assert calc is not None
        assert len(calc._policies) >= 4  # At least 4 tiers

    def test_get_critical_policy(self):
        """Test getting CRITICAL tier policy."""
        calc = SLACalculator()
        policy = calc.get_policy(SLATier.CRITICAL)

        assert policy.tier == SLATier.CRITICAL
        assert policy.first_response_hours == 1
        assert policy.business_hours_only is False  # 24/7

    def test_get_standard_policy(self):
        """Test getting STANDARD tier policy."""
        calc = SLACalculator()
        policy = calc.get_policy(SLATier.STANDARD)

        assert policy.tier == SLATier.STANDARD
        assert policy.first_response_hours == 4
        assert policy.resolution_hours == 48

    def test_calculate_sla_within_limit(self):
        """Test SLA calculation within limit."""
        calc = SLACalculator()
        created = datetime.now() - timedelta(minutes=30)

        result = calc.calculate_sla(
            ticket_id="TKT-001",
            tier=SLATier.CRITICAL,
            sla_type=SLAType.FIRST_RESPONSE,
            created_at=created
        )

        assert result.status == SLABreachStatus.OK
        assert result.is_breached is False
        assert result.percentage_used <= 50

    def test_calculate_sla_breach(self):
        """Test SLA breach detection."""
        calc = SLACalculator()
        created = datetime.now() - timedelta(hours=2)

        result = calc.calculate_sla(
            ticket_id="TKT-002",
            tier=SLATier.CRITICAL,
            sla_type=SLAType.FIRST_RESPONSE,
            created_at=created
        )

        assert result.is_breached is True
        assert result.status in [SLABreachStatus.BREACHED, SLABreachStatus.CRITICAL_BREACH]
        assert result.should_escalate is True

    def test_calculate_sla_warning(self):
        """Test SLA warning detection."""
        calc = SLACalculator()
        # Critical tier = 1 hour, warning at 75% = 45 minutes
        created = datetime.now() - timedelta(minutes=50)

        result = calc.calculate_sla(
            ticket_id="TKT-003",
            tier=SLATier.CRITICAL,
            sla_type=SLAType.FIRST_RESPONSE,
            created_at=created
        )

        assert result.is_warning is True or result.is_breached is True

    def test_check_breach_all_types(self):
        """Test checking all SLA types."""
        calc = SLACalculator()
        created = datetime.now() - timedelta(hours=1)

        results = calc.check_breach(
            ticket_id="TKT-004",
            tier=SLATier.STANDARD,
            created_at=created
        )

        assert SLAType.FIRST_RESPONSE in results
        assert SLAType.RESOLUTION in results
        assert SLAType.UPDATE in results

    def test_estimate_deadline(self):
        """Test deadline estimation."""
        calc = SLACalculator()

        deadline = calc.estimate_deadline(
            tier=SLATier.STANDARD,
            sla_type=SLAType.FIRST_RESPONSE
        )

        assert deadline > datetime.now()

    def test_get_summary(self):
        """Test SLA summary generation."""
        calc = SLACalculator()

        results = [
            calc.calculate_sla("TKT-001", SLATier.STANDARD, SLAType.FIRST_RESPONSE, datetime.now() - timedelta(minutes=30)),
            calc.calculate_sla("TKT-002", SLATier.STANDARD, SLAType.FIRST_RESPONSE, datetime.now() - timedelta(minutes=60)),
        ]

        summary = calc.get_summary(results)

        assert summary.total_tickets == 2
        assert summary.within_sla + summary.warnings + summary.breached + summary.critical_breaches == 2

    def test_stats_tracking(self):
        """Test statistics tracking."""
        calc = SLACalculator()

        calc.calculate_sla(
            ticket_id="TKT-TEST",
            tier=SLATier.STANDARD,
            sla_type=SLAType.FIRST_RESPONSE,
            created_at=datetime.now()
        )

        stats = calc.get_stats()
        assert stats["calculations_performed"] == 1


# =============================================================================
# GDPR Engine Tests
# =============================================================================

class TestGDPREngine:
    """Tests for GDPR Engine."""

    def test_gdpr_engine_initialization(self):
        """Test GDPR engine initializes correctly."""
        engine = GDPREngine()

        assert engine is not None
        assert engine.config is not None

    def test_create_access_request(self):
        """Test creating GDPR access request."""
        engine = GDPREngine()

        request = engine.create_access_request(
            user_id="user-123",
            request_type=GDPRRequestType.ACCESS
        )

        assert request.user_id == "user-123"
        assert request.request_type == GDPRRequestType.ACCESS
        assert request.status == GDPRRequestStatus.PENDING
        assert request.request_id.startswith("GDPR-ACCESS-")

    def test_export_user_data(self):
        """Test user data export."""
        engine = GDPREngine()

        export = engine.export_user_data(user_id="user-123")

        assert export.user_id == "user-123"
        assert export.export_version == "1.0"
        assert export.total_records >= 0
        assert export.checksum is not None

    def test_export_masks_pii_by_default(self):
        """Test that export masks PII by default."""
        engine = GDPREngine()

        export = engine.export_user_data(user_id="user-123", include_pii=False)

        # Check that PII fields are redacted
        for category_data in export.data_categories.values():
            data_str = str(category_data)
            # If email was in data, it should be redacted
            if "email" in data_str.lower():
                assert "[REDACTED]" in data_str

    def test_process_erasure_request(self):
        """Test erasure request processing."""
        engine = GDPREngine()

        result = engine.process_erasure_request(user_id="user-456")

        assert result.user_id == "user-456"
        assert result.success is True
        assert result.completed_at is not None

    def test_mask_pii(self):
        """Test PII masking."""
        engine = GDPREngine()

        data = {
            "email": "test@example.com",
            "name": "John Doe",
            "phone": "+1234567890",
            "preferences": {"newsletter": True}
        }

        masked = engine.mask_pii(data)

        assert masked["email"] == "[REDACTED]"
        assert masked["phone"] == "[REDACTED]"
        assert masked["preferences"]["newsletter"] is True

    def test_anonymize_data_hash(self):
        """Test data anonymization with hash method."""
        engine = GDPREngine()

        data = {
            "email": "test@example.com",
            "phone": "+1234567890"
        }

        anonymized = engine.anonymize_data(data, method="hash")

        assert anonymized["email"] != "test@example.com"
        assert anonymized["phone"] != "+1234567890"

    def test_check_retention(self):
        """Test retention check."""
        engine = GDPREngine()

        # Recent data
        recent = datetime.now() - timedelta(days=30)
        result_recent = engine.check_retention(recent, retention_days=365)
        assert result_recent["within_retention"] is True

        # Old data
        old = datetime.now() - timedelta(days=400)
        result_old = engine.check_retention(old, retention_days=365)
        assert result_old["within_retention"] is False

    def test_stats_tracking(self):
        """Test statistics tracking."""
        engine = GDPREngine()

        engine.export_user_data("user-1")
        engine.process_erasure_request("user-2")

        stats = engine.get_stats()
        assert stats["exports_generated"] == 1
        assert stats["erasures_completed"] == 1


# =============================================================================
# Healthcare Guard Tests
# =============================================================================

class TestHealthcareGuard:
    """Tests for Healthcare Guard."""

    def test_healthcare_guard_initialization(self):
        """Test healthcare guard initializes correctly."""
        guard = HealthcareGuard()

        assert guard is not None
        assert guard.config is not None

    def test_register_baa(self):
        """Test BAA registration."""
        guard = HealthcareGuard()

        baa = BAARecord(
            baa_id="BAA-001",
            client_id="client-123",
            client_name="Test Hospital",
            client_type=HealthcareClientType.COVERED_ENTITY,
            status=BAAStatus.ACTIVE,
            effective_date=datetime.now(),
            expiry_date=datetime.now() + timedelta(days=365),
            permitted_uses=[AccessPurpose.TREATMENT, AccessPurpose.PAYMENT]
        )

        result = guard.register_baa(baa)

        assert result.baa_id == "BAA-001"
        assert result.status == BAAStatus.ACTIVE

    def test_verify_baa_active(self):
        """Test BAA verification for active BAA."""
        guard = HealthcareGuard()

        # Register active BAA
        baa = BAARecord(
            baa_id="BAA-002",
            client_id="client-456",
            client_name="Test Clinic",
            client_type=HealthcareClientType.BUSINESS_ASSOCIATE,
            status=BAAStatus.ACTIVE,
            effective_date=datetime.now() - timedelta(days=30),
            expiry_date=datetime.now() + timedelta(days=335),
            permitted_uses=[AccessPurpose.TREATMENT]
        )
        guard.register_baa(baa)

        result = guard.verify_baa("client-456")

        assert result["valid"] is True

    def test_verify_baa_not_found(self):
        """Test BAA verification when not found."""
        guard = HealthcareGuard()

        result = guard.verify_baa("unknown-client")

        assert result["valid"] is False
        assert result["reason"] == "No BAA on file"

    def test_verify_baa_expired(self):
        """Test BAA verification for expired BAA."""
        guard = HealthcareGuard()

        baa = BAARecord(
            baa_id="BAA-003",
            client_id="client-789",
            client_name="Old Partner",
            client_type=HealthcareClientType.BUSINESS_ASSOCIATE,
            status=BAAStatus.ACTIVE,
            effective_date=datetime.now() - timedelta(days=400),
            expiry_date=datetime.now() - timedelta(days=35),  # Expired
            permitted_uses=[AccessPurpose.TREATMENT]
        )
        guard.register_baa(baa)

        result = guard.verify_baa("client-789", check_expiry=True)

        assert result["valid"] is False
        assert result["status"] == BAAStatus.EXPIRED

    def test_check_phi_access_granted(self):
        """Test PHI access check when granted."""
        guard = HealthcareGuard()

        # Register BAA first
        baa = BAARecord(
            baa_id="BAA-004",
            client_id="client-phi",
            client_name="PHI Test Client",
            client_type=HealthcareClientType.COVERED_ENTITY,
            status=BAAStatus.ACTIVE,
            permitted_uses=[AccessPurpose.TREATMENT]
        )
        guard.register_baa(baa)

        result = guard.check_phi_access(
            client_id="client-phi",
            data={"name": "Patient Name"},
            purpose=AccessPurpose.TREATMENT
        )

        assert result.access_granted is True

    def test_check_phi_access_no_baa(self):
        """Test PHI access check without BAA."""
        guard = HealthcareGuard()

        result = guard.check_phi_access(
            client_id="no-baa-client",
            data={"name": "Patient"},
            purpose=AccessPurpose.TREATMENT
        )

        assert result.access_granted is False
        assert "BAA verification failed" in " ".join(result.violations)

    def test_detect_phi_in_text(self):
        """Test PHI detection in text."""
        guard = HealthcareGuard()

        # SSN
        phi_types = guard.detect_phi_in_text("SSN: 123-45-6789")
        assert PHIType.SSN in phi_types

        # Phone
        phi_types = guard.detect_phi_in_text("Call 555-123-4567")
        assert PHIType.PHONE in phi_types

        # Email
        phi_types = guard.detect_phi_in_text("Email: patient@example.com")
        assert PHIType.EMAIL in phi_types

    def test_redact_phi(self):
        """Test PHI redaction."""
        guard = HealthcareGuard()

        data = {
            "ssn": "123-45-6789",
            "diagnosis": "Condition X",
            "name": "Patient Name",
            "safe_field": "Not PHI"
        }

        redacted = guard.redact_phi(data)

        assert redacted["ssn"] == "[PHI_REDACTED]"
        assert redacted["diagnosis"] == "[PHI_REDACTED]"
        assert redacted["safe_field"] == "Not PHI"

    def test_is_safe_to_log(self):
        """Test safe logging check."""
        guard = HealthcareGuard()

        safe_data = {"id": "123", "status": "active"}
        assert guard.is_safe_to_log(safe_data) is True

        unsafe_data = {"ssn": "123-45-6789"}
        assert guard.is_safe_to_log(unsafe_data) is False

    def test_create_safe_log_entry(self):
        """Test safe log entry creation."""
        guard = HealthcareGuard()

        data = {"ssn": "123-45-6789", "status": "active"}
        safe_entry = guard.create_safe_log_entry(data, context="test")

        assert "phi_redacted" in safe_entry
        assert safe_entry["context"] == "test"

    def test_stats_tracking(self):
        """Test statistics tracking."""
        guard = HealthcareGuard()

        baa = BAARecord(
            baa_id="BAA-STATS",
            client_id="stats-client",
            client_name="Stats Test",
            client_type=HealthcareClientType.COVERED_ENTITY,
            status=BAAStatus.ACTIVE,
            permitted_uses=[AccessPurpose.TREATMENT]
        )
        guard.register_baa(baa)

        guard.check_phi_access(
            client_id="stats-client",
            data={"name": "Test"},
            purpose=AccessPurpose.TREATMENT
        )

        stats = guard.get_stats()
        assert stats["checks_performed"] == 1


# =============================================================================
# Integration Tests
# =============================================================================

class TestComplianceIntegration:
    """Integration tests for compliance layer."""

    def test_full_compliance_workflow(self):
        """Test full compliance check workflow."""
        # Setup
        jurisdiction_mgr = JurisdictionManager()
        sla_calc = SLACalculator()
        gdpr_engine = GDPREngine()
        healthcare_guard = HealthcareGuard()

        # Jurisdiction check
        jurisdiction = jurisdiction_mgr.detect_jurisdiction(country_code="IN")
        assert jurisdiction == JurisdictionCode.IN

        # SLA check
        sla_result = sla_calc.calculate_sla(
            ticket_id="TKT-INT-001",
            tier=SLATier.HIGH,
            sla_type=SLAType.FIRST_RESPONSE,
            created_at=datetime.now() - timedelta(minutes=30)
        )
        assert sla_result.status == SLABreachStatus.OK

        # GDPR export
        export = gdpr_engine.export_user_data(user_id="user-int-001")
        assert export.user_id == "user-int-001"

        # Healthcare check
        baa = BAARecord(
            baa_id="BAA-INT",
            client_id="int-client",
            client_name="Integration Test",
            client_type=HealthcareClientType.BUSINESS_ASSOCIATE,
            status=BAAStatus.ACTIVE,
            permitted_uses=[AccessPurpose.TREATMENT]
        )
        healthcare_guard.register_baa(baa)

        phi_result = healthcare_guard.check_phi_access(
            client_id="int-client",
            data={"patient_name": "Test Patient"},
            purpose=AccessPurpose.TREATMENT
        )
        assert phi_result.access_granted is True

    def test_healthcare_client_triggers_baa_requirement(self):
        """Test that healthcare clients require BAA."""
        guard = HealthcareGuard()

        # Covered entity should require BAA
        result = guard.check_phi_access(
            client_id="covered-entity-1",
            data={"patient": "data"},
            purpose=AccessPurpose.TREATMENT
        )

        assert result.access_granted is False  # No BAA on file


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
