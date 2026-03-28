"""
Tests for Healthcare HIPAA Module (Week 33).

Tests cover:
- PHIHandler: Detection, sanitization, pattern matching
- HIPAAComplianceManager: Compliance checks, audit logging
- BAAManager: BAA lifecycle management
- MedicalKnowledgeBase: Term lookup, code lookup
- EHRIntegration: Connection, patient/appointment operations
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from variants.healthcare.phi_handler import (
    PHIHandler,
    PHIType,
    PHIDetectionResult,
    SanitizationMethod,
)
from variants.healthcare.hipaa_compliance import (
    HIPAAComplianceManager,
    ComplianceStatus,
    ComplianceCheck,
)
from variants.healthcare.baa_manager import (
    BAAManager,
    BAAStatus,
    BAAType,
    BAARecord,
)
from variants.healthcare.medical_kb import (
    MedicalKnowledgeBase,
    MedicalTermCategory,
)
from variants.healthcare.ehr_integration import (
    EHRIntegration,
    EHRProvider,
    EHRConnection,
)


# =============================================================================
# PHI Handler Tests
# =============================================================================

class TestPHIHandler:
    """Tests for PHIHandler class."""

    @pytest.fixture
    def handler(self):
        """Create a PHI handler instance."""
        return PHIHandler(client_id="test_client_001")

    def test_handler_initializes(self, handler):
        """Test that handler initializes correctly."""
        assert handler.client_id == "test_client_001"
        assert handler.sensitivity == "high"

    def test_detect_ssn(self, handler):
        """Test SSN detection."""
        text = "Patient SSN is 123-45-6789"
        results = handler.detect(text)

        assert len(results) >= 1
        assert any(r.phi_type == PHIType.SSN for r in results)

    def test_detect_ssn_no_dashes(self, handler):
        """Test SSN detection without dashes."""
        text = "SSN: 123456789"
        results = handler.detect(text)

        assert any(r.phi_type == PHIType.SSN for r in results)

    def test_detect_email(self, handler):
        """Test email detection."""
        text = "Contact: patient@example.com"
        results = handler.detect(text)

        assert any(r.phi_type == PHIType.EMAIL for r in results)

    def test_detect_phone(self, handler):
        """Test phone number detection."""
        text = "Call 555-123-4567"
        results = handler.detect(text)

        assert any(r.phi_type == PHIType.PHONE for r in results)

    def test_detect_mrn(self, handler):
        """Test MRN detection."""
        text = "MRN: MRN12345678"
        results = handler.detect(text)

        assert any(r.phi_type == PHIType.MRN for r in results)

    def test_detect_credit_card(self, handler):
        """Test credit card detection."""
        text = "Card: 4532-1234-5678-9010"
        results = handler.detect(text)

        assert any(r.phi_type == PHIType.CREDIT_CARD for r in results)

    def test_detect_multiple_phi(self, handler):
        """Test detection of multiple PHI types."""
        text = "SSN: 123-45-6789, Email: test@example.com, Phone: 555-123-4567"
        results = handler.detect(text)

        phi_types = {r.phi_type for r in results}
        assert PHIType.SSN in phi_types
        assert PHIType.EMAIL in phi_types
        assert PHIType.PHONE in phi_types

    def test_sanitize_redact(self, handler):
        """Test sanitization with redaction."""
        text = "SSN: 123-45-6789"
        sanitized = handler.sanitize(text)

        assert "123-45-6789" not in sanitized
        assert "[SSN-REDACTED]" in sanitized

    def test_sanitize_hash(self, handler):
        """Test sanitization with hashing."""
        handler.default_method = SanitizationMethod.HASH
        text = "Email: test@example.com"
        sanitized = handler.sanitize(text)

        assert "test@example.com" not in sanitized
        assert "[HASH:" in sanitized

    def test_sanitize_mask(self, handler):
        """Test sanitization with masking."""
        handler.default_method = SanitizationMethod.MASK
        text = "Phone: 5551234567"
        sanitized = handler.sanitize(text)

        assert "5551234567" not in sanitized

    def test_contains_phi(self, handler):
        """Test quick PHI check."""
        assert handler.contains_phi("SSN: 123-45-6789") is True
        assert handler.contains_phi("Hello world") is False

    def test_get_phi_count(self, handler):
        """Test PHI counting."""
        text = "SSN: 123-45-6789 and SSN: 987-65-4321"
        counts = handler.get_phi_count(text)

        assert counts.get(PHIType.SSN, 0) == 2

    def test_context_extraction(self, handler):
        """Test context extraction around PHI."""
        text = "The patient SSN 123-45-6789 is registered"
        results = handler.detect(text)

        assert len(results) >= 1
        assert "patient" in results[0].context.lower()

    def test_healthcare_context_boost(self, handler):
        """Test confidence boost from healthcare context."""
        text1 = "SSN: 123-45-6789"
        text2 = "Patient SSN: 123-45-6789"

        results1 = handler.detect(text1)
        results2 = handler.detect(text2)

        # Healthcare context should boost confidence
        if results1 and results2:
            assert results2[0].confidence >= results1[0].confidence


# =============================================================================
# HIPAA Compliance Tests
# =============================================================================

class TestHIPAAComplianceManager:
    """Tests for HIPAAComplianceManager class."""

    @pytest.fixture
    def manager(self):
        """Create a compliance manager instance."""
        return HIPAAComplianceManager(client_id="test_client_001")

    def test_manager_initializes(self, manager):
        """Test that manager initializes correctly."""
        assert manager.client_id == "test_client_001"
        assert manager.baa_verified is False

    def test_run_baa_check_fails(self, manager):
        """Test BAA check fails when no BAA."""
        result = manager.run_compliance_check(ComplianceCheck.BAA_VERIFICATION)

        assert result.passed is False
        assert result.status == ComplianceStatus.NON_COMPLIANT

    def test_run_baa_check_passes(self, manager):
        """Test BAA check passes when BAA verified."""
        manager.baa_verified = True
        result = manager.run_compliance_check(ComplianceCheck.BAA_VERIFICATION)

        assert result.passed is True
        assert result.status == ComplianceStatus.COMPLIANT

    def test_run_all_checks(self, manager):
        """Test running all required checks."""
        results = manager.run_all_checks()

        assert len(results) == len(manager.REQUIRED_CHECKS)

    def test_log_phi_access(self, manager):
        """Test PHI access logging."""
        entry = manager.log_phi_access(
            user_id="user_001",
            action="VIEW_RECORD",
            resource_type="patient_record",
            resource_id="patient_123",
            justification="Treatment purposes",
        )

        assert entry.entry_id is not None
        assert entry.phi_accessed is True
        assert len(manager._audit_logs) == 1

    def test_minimum_necessary_allowed(self, manager):
        """Test minimum necessary allows appropriate access."""
        allowed, reason = manager.check_minimum_necessary(
            user_role="provider",
            requested_data="medical_records",
            purpose="treatment",
        )

        assert allowed is True

    def test_minimum_necessary_denied(self, manager):
        """Test minimum necessary denies inappropriate access."""
        allowed, reason = manager.check_minimum_necessary(
            user_role="support",
            requested_data="medical_records",
            purpose="curiosity",
        )

        assert allowed is False

    def test_emergency_access(self, manager):
        """Test emergency access logging."""
        granted, reason = manager.emergency_access(
            user_id="user_001",
            patient_id="patient_123",
            reason="Patient unconscious, critical care needed",
        )

        assert granted is True
        assert len(manager._audit_logs) == 1

    def test_get_compliance_summary(self, manager):
        """Test compliance summary."""
        manager.run_all_checks()
        summary = manager.get_compliance_summary()

        assert "overall_status" in summary
        assert "checks_run" in summary


# =============================================================================
# BAA Manager Tests
# =============================================================================

class TestBAAManager:
    """Tests for BAAManager class."""

    @pytest.fixture
    def manager(self):
        """Create a BAA manager instance."""
        return BAAManager(client_id="test_client_001")

    def test_manager_initializes(self, manager):
        """Test that manager initializes correctly."""
        assert manager.client_id == "test_client_001"

    def test_create_baa(self, manager):
        """Test BAA creation."""
        baa = manager.create_baa(
            client_name="Test Healthcare",
            baa_type=BAAType.STANDARD,
        )

        assert baa.baa_id is not None
        assert baa.status == BAAStatus.DRAFT
        assert baa.client_name == "Test Healthcare"

    def test_sign_baa(self, manager):
        """Test BAA signing."""
        baa = manager.create_baa("Test Healthcare")
        signed = manager.sign_baa(
            baa_id=baa.baa_id,
            signed_by="John Doe",
        )

        assert signed.status == BAAStatus.ACTIVE
        assert signed.signed_by == "John Doe"
        assert signed.effective_date is not None

    def test_verify_baa(self, manager):
        """Test BAA verification."""
        # No BAA
        result = manager.verify_baa()
        assert result["valid"] is False

        # Create and sign BAA
        baa = manager.create_baa("Test Healthcare")
        manager.sign_baa(baa.baa_id, "John Doe")

        result = manager.verify_baa()
        assert result["valid"] is True

    def test_check_expiry_warnings(self, manager):
        """Test expiry warning detection."""
        baa = manager.create_baa("Test Healthcare")
        manager.sign_baa(baa.baa_id, "John Doe", term_years=0)  # Very short term

        warnings = manager.check_expiry_warnings()
        # Should have warnings for expiring BAA
        assert isinstance(warnings, list)

    def test_terminate_baa(self, manager):
        """Test BAA termination."""
        baa = manager.create_baa("Test Healthcare")
        manager.sign_baa(baa.baa_id, "John Doe")

        terminated = manager.terminate_baa(
            baa_id=baa.baa_id,
            reason="Contract ended",
        )

        assert terminated.status == BAAStatus.TERMINATED
        assert terminated.termination_reason == "Contract ended"

    def test_renew_baa(self, manager):
        """Test BAA renewal."""
        baa = manager.create_baa("Test Healthcare")
        manager.sign_baa(baa.baa_id, "John Doe")

        renewed = manager.renew_baa(baa.baa_id)

        assert renewed.status == BAAStatus.ACTIVE
        assert renewed.baa_id != baa.baa_id

    def test_report_breach(self, manager):
        """Test breach reporting."""
        baa = manager.create_baa("Test Healthcare")
        manager.sign_baa(baa.baa_id, "John Doe")

        report = manager.report_breach(
            baa_id=baa.baa_id,
            breach_details={"type": "unauthorized_access", "records": 100},
        )

        assert report["baa_id"] == baa.baa_id
        assert report["notification_required"] is True


# =============================================================================
# Medical Knowledge Base Tests
# =============================================================================

class TestMedicalKnowledgeBase:
    """Tests for MedicalKnowledgeBase class."""

    @pytest.fixture
    def kb(self):
        """Create a medical KB instance."""
        return MedicalKnowledgeBase(client_id="test_client_001")

    def test_kb_initializes(self, kb):
        """Test that KB initializes correctly."""
        assert kb.client_id == "test_client_001"
        assert len(kb._terms) > 0  # Pre-loaded terms

    def test_lookup_term(self, kb):
        """Test term lookup."""
        results = kb.lookup_term("hypertension")

        assert len(results) >= 1
        assert results[0].category == MedicalTermCategory.CONDITION

    def test_lookup_icd_code(self, kb):
        """Test ICD code lookup."""
        result = kb.lookup_code("I10")

        assert result is not None
        assert result.code_type == "icd-10"
        assert "hypertension" in result.description.lower()

    def test_lookup_cpt_code(self, kb):
        """Test CPT code lookup."""
        result = kb.lookup_code("99213")

        assert result is not None
        assert result.code_type == "cpt"
        assert "office" in result.description.lower()

    def test_expand_abbreviation(self, kb):
        """Test abbreviation expansion."""
        expanded = kb.expand_abbreviation("BP")

        assert expanded == "Blood Pressure"

    def test_assess_urgency_emergency(self, kb):
        """Test emergency urgency detection."""
        assessment = kb.assess_urgency("Patient has chest pain and difficulty breathing")

        assert assessment["level"] == "emergency"

    def test_assess_urgency_urgent(self, kb):
        """Test urgent detection."""
        assessment = kb.assess_urgency("Patient has high fever and severe pain")

        assert assessment["level"] == "urgent"

    def test_assess_urgency_routine(self, kb):
        """Test routine assessment."""
        assessment = kb.assess_urgency("Patient needs prescription refill")

        assert assessment["level"] == "routine"

    def test_get_patient_friendly_explanation(self, kb):
        """Test patient-friendly explanation."""
        explanation = kb.get_patient_friendly_explanation("I10")

        assert "explanation" in explanation
        assert explanation["type"] == "code"


# =============================================================================
# EHR Integration Tests
# =============================================================================

class TestEHRIntegration:
    """Tests for EHRIntegration class."""

    @pytest.fixture
    def ehr(self):
        """Create an EHR integration instance."""
        return EHRIntegration(
            client_id="test_client_001",
            provider=EHRProvider.EPIC,
        )

    def test_ehr_initializes(self, ehr):
        """Test that EHR initializes correctly."""
        assert ehr.client_id == "test_client_001"
        assert ehr.provider == EHRProvider.EPIC

    def test_connect(self, ehr):
        """Test EHR connection."""
        conn = ehr.connect(
            base_url="https://epic.example.com/api",
            client_id="test_client",
            client_secret="test_secret",
        )

        assert conn.is_connected is True
        assert conn.provider == EHRProvider.EPIC

    def test_disconnect(self, ehr):
        """Test EHR disconnection."""
        ehr.connect("https://epic.example.com/api", "client", "secret")
        result = ehr.disconnect()

        assert result is True
        assert ehr._connection.is_connected is False

    def test_get_patient(self, ehr):
        """Test getting patient."""
        ehr.connect("https://epic.example.com/api", "client", "secret")

        patient = ehr.get_patient("P12345")

        assert patient is not None
        assert patient.patient_id == "P12345"

    def test_search_patients(self, ehr):
        """Test patient search."""
        ehr.connect("https://epic.example.com/api", "client", "secret")

        patients = ehr.search_patients("Smith", limit=5)

        assert len(patients) <= 5

    def test_get_appointments(self, ehr):
        """Test getting appointments."""
        ehr.connect("https://epic.example.com/api", "client", "secret")

        appointments = ehr.get_appointments(patient_id="P12345")

        assert isinstance(appointments, list)

    def test_create_appointment(self, ehr):
        """Test creating appointment."""
        ehr.connect("https://epic.example.com/api", "client", "secret")

        appt = ehr.create_appointment(
            patient_id="P12345",
            provider_id="DR001",
            appointment_type="Office Visit",
            scheduled_time=datetime.utcnow() + timedelta(days=7),
        )

        assert appt.appointment_id is not None
        assert appt.status == "scheduled"

    def test_cancel_appointment(self, ehr):
        """Test canceling appointment."""
        ehr.connect("https://epic.example.com/api", "client", "secret")
        appt = ehr.create_appointment(
            patient_id="P12345",
            provider_id="DR001",
            appointment_type="Office Visit",
            scheduled_time=datetime.utcnow() + timedelta(days=7),
        )

        result = ehr.cancel_appointment(appt.appointment_id, "Patient request")

        assert result is True

    def test_get_medical_records(self, ehr):
        """Test getting medical records."""
        ehr.connect("https://epic.example.com/api", "client", "secret")

        records = ehr.get_medical_records("P12345")

        assert isinstance(records, list)


# =============================================================================
# Integration Tests
# =============================================================================

class TestHealthcareIntegration:
    """Integration tests for healthcare modules."""

    @pytest.mark.asyncio
    async def test_phi_to_compliance_workflow(self):
        """Test PHI detection to compliance logging workflow."""
        client_id = "test_integration_001"

        # Detect PHI
        handler = PHIHandler(client_id=client_id)
        text = "Patient SSN: 123-45-6789 called about appointment"
        detections = handler.detect(text)

        assert len(detections) > 0

        # Sanitize for logging
        sanitized = handler.sanitize(text)

        # Log access
        manager = HIPAAComplianceManager(client_id=client_id)
        manager.log_phi_access(
            user_id="agent_001",
            action="VIEW_INTERACTION",
            resource_type="interaction",
            resource_id="INT-001",
            justification="Customer support request",
        )

        assert len(manager._audit_logs) == 1

    @pytest.mark.asyncio
    async def test_baa_to_phi_access_workflow(self):
        """Test BAA verification before PHI access."""
        client_id = "test_baa_001"

        # Create and sign BAA
        baa_manager = BAAManager(client_id=client_id)
        baa = baa_manager.create_baa("Test Healthcare")
        baa_manager.sign_baa(baa.baa_id, "Admin")

        # Verify BAA before allowing PHI access
        verification = baa_manager.verify_baa()
        assert verification["valid"] is True

        # Now allow PHI operations
        if verification["valid"]:
            handler = PHIHandler(client_id=client_id)
            result = handler.contains_phi("SSN: 123-45-6789")
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
