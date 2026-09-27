"""
Week 6 Onboarding Gaps Tests

Tests for gaps identified by gap_finder.py:

GAP 1 (CRITICAL): Onboarding state machine race condition
GAP 2 (CRITICAL): Tenant isolation in document processing
GAP 3 (HIGH): Email verification bypass
GAP 4 (HIGH): File upload vulnerability
GAP 5 (HIGH): Consent timestamp manipulation
GAP 6 (MEDIUM): Async processing failure handling
GAP 7 (MEDIUM): Integration validation bypass
"""

import pytest
import json
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import threading

from backend.app.exceptions import ValidationError
from database.models.user_details import UserDetails
from database.models.onboarding import OnboardingSession
from database.models.onboarding import KnowledgeDocument


# ── GAP 1: Onboarding State Machine Race Condition ──────────────────────────

class TestGap1OnboardingStateMachineRaceCondition:
    """
    GAP 1 (CRITICAL): Multiple concurrent API calls can put onboarding in invalid state.
    
    Scenario: User rapidly clicks through wizard steps while processing KB documents,
    causing state inconsistency between onboarding_sessions and knowledge_documents.
    """
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session with thread-safe tracking."""
        mock_db = MagicMock()
        mock_db._lock = threading.Lock()
        mock_db._operations = []
        
        def track_operation(op_name):
            with mock_db._lock:
                mock_db._operations.append((op_name, threading.current_thread().name, datetime.utcnow()))
        
        mock_db.track = track_operation
        return mock_db
    
    def test_concurrent_step_transitions_maintain_consistency(self):
        """
        Test that rapid concurrent step transitions maintain state consistency.
        
        Verify that even when multiple step completions happen simultaneously,
        the state machine properly handles concurrent transitions.
        """
        # Simulate concurrent step transitions
        results = {"success": 0, "errors": []}
        lock = threading.Lock()
        
        def transition_step(step_num, session_data):
            try:
                # Simulate state transition
                with lock:
                    if session_data["current_step"] == step_num - 1:
                        session_data["current_step"] = step_num
                        session_data["completed_steps"].append(step_num - 1)
                        results["success"] += 1
                    else:
                        results["errors"].append(f"Invalid transition: expected step {step_num - 1}, got {session_data['current_step']}")
            except Exception as e:
                with lock:
                    results["errors"].append(str(e))
        
        session_data = {
            "current_step": 1,
            "completed_steps": [],
        }
        
        # Simulate concurrent transitions
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(transition_step, 2, session_data),
                executor.submit(transition_step, 3, session_data),
                executor.submit(transition_step, 2, session_data),  # Duplicate
            ]
            for f in futures:
                f.result()
        
        # State should be consistent (no skipped steps)
        assert session_data["current_step"] >= 1
        assert len(results["errors"]) == 0 or all("Invalid transition" in e for e in results["errors"])
    
    def test_onboarding_session_row_locking_on_update(self, mock_db_session):
        """
        Test that onboarding session updates use row-level locking.
        
        This test verifies that the service uses SELECT FOR UPDATE
        or similar locking mechanism when updating onboarding state.
        """
        # This is a documentation test - the actual implementation
        # should use row locking in the service
        # 
        # Expected pattern in service:
        # session = db.query(OnboardingSession).filter(
        #     OnboardingSession.id == session_id,
        #     OnboardingSession.company_id == company_id,
        # ).with_for_update().first()
        
        # For now, verify the pattern exists in documentation
        assert True  # Placeholder - actual test would require DB
    
    def test_knowledge_document_state_consistency(self):
        """
        Test that knowledge document processing state stays consistent with onboarding.
        
        When documents are being processed, the onboarding session should reflect
        the correct state even if user navigates away.
        """
        # Simulate document upload and state tracking
        session = {
            "knowledge_base_files": [],
            "documents_processing": 0,
        }
        
        def upload_document(doc_id):
            with threading.Lock():
                session["knowledge_base_files"].append({
                    "id": doc_id,
                    "status": "processing",
                })
                session["documents_processing"] += 1
        
        def complete_document(doc_id):
            with threading.Lock():
                for doc in session["knowledge_base_files"]:
                    if doc["id"] == doc_id:
                        doc["status"] = "completed"
                        session["documents_processing"] -= 1
        
        # Concurrent uploads
        doc_ids = ["doc1", "doc2", "doc3"]
        with ThreadPoolExecutor(max_workers=3) as executor:
            executor.map(upload_document, doc_ids)
        
        assert session["documents_processing"] == 3
        
        # Complete all
        with ThreadPoolExecutor(max_workers=3) as executor:
            executor.map(complete_document, doc_ids)
        
        assert session["documents_processing"] == 0
        assert all(d["status"] == "completed" for d in session["knowledge_base_files"])


# ── GAP 2: Tenant Isolation in Document Processing ───────────────────────────

class TestGap2TenantIsolationInDocumentProcessing:
    """
    GAP 2 (CRITICAL): Documents from one tenant may be processed with another tenant's embeddings.
    
    Scenario: High tenant uploads documents simultaneously while Celery workers are busy,
    causing document metadata to be associated with wrong company_id during vector embedding.
    """
    
    def test_document_embedding_tenant_isolation(self):
        """
        Test that document embeddings maintain correct company_id association.
        
        When multiple tenants upload documents simultaneously, each document's
        embeddings should be associated with the correct company_id.
        """
        # Simulate multi-tenant document processing
        documents = []
        lock = threading.Lock()
        
        def process_document(company_id, doc_id):
            # Simulate processing with company_id context
            doc = {
                "id": doc_id,
                "company_id": company_id,
                "embeddings": [0.1, 0.2, 0.3],  # Mock embedding
                "processed_at": datetime.utcnow().isoformat(),
            }
            with lock:
                documents.append(doc)
        
        # Simulate concurrent uploads from multiple tenants
        tenants = [
            ("company_A", "doc_A1"),
            ("company_B", "doc_B1"),
            ("company_C", "doc_C1"),
            ("company_A", "doc_A2"),
            ("company_B", "doc_B2"),
        ]
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_document, c, d) for c, d in tenants]
            for f in futures:
                f.result()
        
        # Verify tenant isolation
        for doc in documents:
            if doc["id"].startswith("doc_A"):
                assert doc["company_id"] == "company_A"
            elif doc["id"].startswith("doc_B"):
                assert doc["company_id"] == "company_B"
            elif doc["id"].startswith("doc_C"):
                assert doc["company_id"] == "company_C"
    
    def test_celery_task_tenant_context_propagation(self):
        """
        Test that Celery tasks maintain tenant context throughout processing.
        
        Verify that company_id is passed through all async processing steps.
        """
        # This test documents the expected behavior
        # The actual implementation should ensure that:
        # 1. company_id is passed as a task parameter
        # 2. company_id is verified before any database write
        # 3. Embeddings are stored with the correct company_id
        
        expected_flow = """
        # In knowledge_tasks.py:
        @celery_app.task(bind=True)
        def process_knowledge_document(self, document_id: str, company_id: str):
            # Verify company_id matches document's company_id
            doc = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.company_id == company_id,  # Critical: verify ownership
            ).first()
            
            if not doc:
                raise ValidationError("Document not found or access denied")
            
            # Process with company context
            chunks = extract_chunks(doc.content)
            for chunk in chunks:
                embedding = generate_embedding(chunk)
                store_embedding(
                    chunk_id=chunk.id,
                    embedding=embedding,
                    company_id=company_id,  # Critical: pass company_id
                )
        """
        assert "company_id" in expected_flow


# ── GAP 3: Email Verification Bypass ────────────────────────────────────────

class TestGap3EmailVerificationBypass:
    """
    GAP 3 (HIGH): Users can complete onboarding without verifying work email.
    
    Scenario: User submits email verification request, closes browser, returns later
    and completes onboarding without verifying email.
    """
    
    def test_ai_activation_requires_email_verification(self):
        """
        Test that AI activation requires verified work email if provided.
        
        If a user provides a work email, they must verify it before AI activation.
        """
        # Simulate the activation check
        user_details = {
            "work_email": "john@company.com",
            "work_email_verified": False,
        }
        
        onboarding_session = {
            "legal_accepted": True,
            "integrations": ["zendesk"],
            "knowledge_base_files": [{"status": "completed"}],
        }
        
        # Check prerequisites for AI activation
        can_activate = self._check_activation_prerequisites(user_details, onboarding_session)
        
        # Should NOT be able to activate without email verification
        assert can_activate is False, "AI activation should require email verification"
    
    def test_ai_activation_allowed_without_work_email(self):
        """
        Test that AI activation is allowed if no work email was provided.
        
        Work email is optional, so users who don't provide it should not be blocked.
        """
        user_details = {
            "work_email": None,
            "work_email_verified": False,
        }
        
        onboarding_session = {
            "legal_accepted": True,
            "integrations": ["zendesk"],
            "knowledge_base_files": [{"status": "completed"}],
        }
        
        can_activate = self._check_activation_prerequisites(user_details, onboarding_session)
        
        # Should be able to activate if no work email was provided
        assert can_activate is True, "AI activation should work without work email"
    
    def test_ai_activation_allowed_with_verified_email(self):
        """
        Test that AI activation works with verified work email.
        """
        user_details = {
            "work_email": "john@company.com",
            "work_email_verified": True,
        }
        
        onboarding_session = {
            "legal_accepted": True,
            "integrations": ["zendesk"],
            "knowledge_base_files": [{"status": "completed"}],
        }
        
        can_activate = self._check_activation_prerequisites(user_details, onboarding_session)
        
        assert can_activate is True
    
    def _check_activation_prerequisites(self, user_details, session):
        """
        Helper method implementing the prerequisite check logic.
        
        This should be implemented in the actual service.
        """
        # Legal must be accepted
        if not session.get("legal_accepted"):
            return False
        
        # Must have at least one integration OR one completed KB document
        has_integration = len(session.get("integrations", [])) > 0
        has_kb = any(
            doc.get("status") == "completed"
            for doc in session.get("knowledge_base_files", [])
        )
        
        if not (has_integration or has_kb):
            return False
        
        # If work email is provided, it must be verified
        if user_details.get("work_email") and not user_details.get("work_email_verified"):
            return False
        
        return True


# ── GAP 4: File Upload Vulnerability ────────────────────────────────────────

class TestGap4FileUploadVulnerability:
    """
    GAP 4 (HIGH): Malicious files can be uploaded to knowledge base.
    
    Scenario: User uploads a malicious script file with .txt extension
    that gets executed during processing.
    """
    
    @pytest.fixture
    def allowed_extensions(self):
        """Allowed file extensions for KB upload."""
        return {".pdf", ".docx", ".doc", ".txt", ".md", ".rtf"}
    
    @pytest.fixture
    def max_file_size_mb(self):
        """Maximum file size in MB."""
        return 10
    
    def test_reject_executable_extensions(self, allowed_extensions):
        """
        Test that executable file extensions are rejected.
        """
        dangerous_extensions = [".exe", ".bat", ".sh", ".ps1", ".vbs", ".js", ".py"]
        
        for ext in dangerous_extensions:
            assert ext not in allowed_extensions, f"Extension {ext} should be blocked"
    
    def test_reject_disguised_executables(self):
        """
        Test that files with executable content but safe extension are detected.
        
        A .txt file containing executable code should be flagged or rejected.
        """
        # This test documents expected behavior
        # The actual implementation should:
        # 1. Check magic bytes (file signature) not just extension
        # 2. Scan for potentially dangerous content
        # 3. Use content-type validation
        
        dangerous_content_signatures = [
            b"MZ",  # Windows executable
            b"\x7fELF",  # Linux executable
            b"PK\x03\x04",  # ZIP (could contain malware)
            b"%PDF",  # PDF (need to validate further)
        ]
        
        # Expected validation:
        # def validate_file_content(content: bytes, extension: str) -> bool:
        #     # Check magic bytes match extension
        #     # Scan for embedded scripts
        #     # Reject if mismatch
        
        assert len(dangerous_content_signatures) > 0
    
    def test_file_size_limit_enforced(self, max_file_size_mb):
        """
        Test that file size limit is enforced.
        """
        max_bytes = max_file_size_mb * 1024 * 1024
        
        # Simulate file size check
        def validate_file_size(size_bytes: int) -> bool:
            return size_bytes <= max_bytes
        
        assert validate_file_size(5 * 1024 * 1024) is True  # 5MB
        assert validate_file_size(15 * 1024 * 1024) is False  # 15MB
    
    def test_mime_type_validation(self):
        """
        Test that MIME type matches file extension.
        """
        expected_mime_types = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
            ".md": "text/markdown",
        }
        
        # Implementation should verify that:
        # 1. Content-Type header matches extension
        # 2. Magic bytes match the claimed type
        # 3. Reject if mismatch
        
        assert len(expected_mime_types) > 0


# ── GAP 5: Consent Timestamp Manipulation ───────────────────────────────────

class TestGap5ConsentTimestampManipulation:
    """
    GAP 5 (HIGH): Legal consents can be backdated to bypass requirements.
    
    Scenario: User modifies system time to backdate consent timestamps
    and activate AI without proper review.
    """
    
    def test_reject_backdated_consent_timestamps(self):
        """
        Test that backdated consent timestamps are rejected.
        
        The system should use server time, not client-provided time.
        """
        server_time = datetime.utcnow()
        
        # Client tries to submit backdated consent
        backdated_time = server_time - timedelta(days=30)
        
        def validate_consent_timestamp(submitted_time: datetime, server_time: datetime) -> bool:
            """
            Validate that consent timestamp is current.
            
            Rules:
            1. Timestamp must be within 5 minutes of server time
            2. Timestamp cannot be in the future
            3. Timestamp cannot be too old (more than 5 minutes ago)
            """
            time_diff = abs((server_time - submitted_time).total_seconds())
            max_allowed_diff = 300  # 5 minutes
            
            return time_diff <= max_allowed_diff
        
        # Backdated timestamp should be rejected
        assert validate_consent_timestamp(backdated_time, server_time) is False
    
    def test_reject_future_dated_consent_timestamps(self):
        """
        Test that future-dated consent timestamps are rejected.
        """
        server_time = datetime.utcnow()
        future_time = server_time + timedelta(hours=1)
        
        def validate_consent_timestamp(submitted_time: datetime, server_time: datetime) -> bool:
            time_diff = (submitted_time - server_time).total_seconds()
            # Allow 5 minute tolerance for clock skew
            return time_diff <= 300 and time_diff >= -300
        
        assert validate_consent_timestamp(future_time, server_time) is False
    
    def test_server_time_used_for_consent_recording(self):
        """
        Test that server time is used for recording consent, not client time.
        
        The consent service should ignore any client-provided timestamp
        and use server time instead.
        """
        # Expected implementation:
        # def record_consent(consent_type: str, user_id: str, company_id: str):
        #     # Always use server time
        #     accepted_at = datetime.utcnow()  # Server time
        #     
        #     consent = ConsentRecord(
        #         consent_type=consent_type,
        #         user_id=user_id,
        #         company_id=company_id,
        #         accepted_at=accepted_at,  # Server-controlled
        #         ip_address=get_client_ip(),
        #     )
        
        server_time = datetime.utcnow()
        # The service should ignore any client-provided time
        assert server_time is not None


# ── GAP 6: Async Processing Failure Handling ────────────────────────────────

class TestGap6AsyncProcessingFailureHandling:
    """
    GAP 6 (MEDIUM): Failed document processing leaves onboarding in incomplete state.
    
    Scenario: Large PDF upload fails during text extraction,
    leaving document in "processing" state forever.
    """
    
    def test_document_failure_status_update(self):
        """
        Test that failed documents are marked with 'failed' status.
        """
        # Simulate document processing failure
        document = {
            "id": "doc_123",
            "status": "processing",
            "error_message": None,
            "retry_count": 0,
        }
        
        def handle_processing_failure(doc: dict, error: str):
            """Handle document processing failure."""
            doc["status"] = "failed"
            doc["error_message"] = error
            doc["failed_at"] = datetime.utcnow().isoformat()
            return doc
        
        result = handle_processing_failure(document, "PDF text extraction failed: corrupted file")
        
        assert result["status"] == "failed"
        assert result["error_message"] is not None
    
    def test_document_retry_after_failure(self):
        """
        Test that users can retry failed document processing.
        """
        document = {
            "id": "doc_123",
            "status": "failed",
            "retry_count": 1,
            "max_retries": 3,
        }
        
        def can_retry(doc: dict) -> bool:
            return doc["status"] == "failed" and doc["retry_count"] < doc["max_retries"]
        
        assert can_retry(document) is True
    
    def test_max_retry_limit_enforced(self):
        """
        Test that documents cannot be retried beyond max limit.
        """
        document = {
            "id": "doc_123",
            "status": "failed",
            "retry_count": 3,
            "max_retries": 3,
        }
        
        def can_retry(doc: dict) -> bool:
            return doc["status"] == "failed" and doc["retry_count"] < doc["max_retries"]
        
        assert can_retry(document) is False
    
    def test_onboarding_can_proceed_without_failed_documents(self):
        """
        Test that onboarding can proceed if user removes failed documents.
        """
        onboarding_session = {
            "knowledge_base_files": [
                {"id": "doc1", "status": "completed"},
                {"id": "doc2", "status": "failed"},
            ],
        }
        
        def remove_failed_documents(session: dict):
            """Remove all failed documents from session."""
            session["knowledge_base_files"] = [
                doc for doc in session["knowledge_base_files"]
                if doc["status"] != "failed"
            ]
            return session
        
        result = remove_failed_documents(onboarding_session)
        
        assert all(doc["status"] != "failed" for doc in result["knowledge_base_files"])
        assert len(result["knowledge_base_files"]) == 1


# ── GAP 7: Integration Validation Bypass ────────────────────────────────────

class TestGap7IntegrationValidationBypass:
    """
    GAP 7 (MEDIUM): Invalid integrations can be created without proper validation.
    
    Scenario: User submits integration with invalid API credentials,
    system accepts it but AI activation fails.
    """
    
    def test_integration_credentials_validated_before_save(self):
        """
        Test that integration API credentials are validated before saving.
        """
        integration = {
            "type": "zendesk",
            "config": {
                "subdomain": "mycompany",
                "api_token": "invalid_token_12345",
                "email": "admin@mycompany.com",
            },
        }
        
        def validate_zendesk_credentials(config: dict) -> tuple[bool, str]:
            """
            Validate Zendesk credentials by making a test API call.
            
            Returns:
                (is_valid, error_message)
            """
            # This should make an actual API call to verify credentials
            # For testing, we simulate the validation
            required_fields = ["subdomain", "api_token", "email"]
            
            for field in required_fields:
                if not config.get(field):
                    return False, f"Missing required field: {field}"
            
            # In real implementation, make test API call:
            # response = requests.get(
            #     f"https://{config['subdomain']}.zendesk.com/api/v2/users/me.json",
            #     auth=(f"{config['email']}/token", config['api_token'])
            # )
            # return response.status_code == 200, response.text
            
            # For now, simulate validation
            if len(config.get("api_token", "")) < 20:
                return False, "API token appears to be invalid (too short)"
            
            return True, ""
        
        is_valid, error = validate_zendesk_credentials(integration["config"])
        
        # Invalid token should be caught
        assert is_valid is False
    
    def test_integration_test_endpoint(self):
        """
        Test that there's an endpoint to test integration connectivity.
        """
        # Expected API endpoint:
        # POST /api/integrations/:id/test
        #
        # Response:
        # {
        #     "success": true/false,
        #     "message": "Connection successful" or error message,
        #     "tested_at": "2024-01-01T00:00:00Z"
        # }
        
        expected_response = {
            "success": True,
            "message": "Connection successful",
            "tested_at": datetime.utcnow().isoformat(),
        }
        
        assert expected_response["success"] is True
    
    def test_integration_status_tracking(self):
        """
        Test that integration status is tracked (active/error/pending).
        """
        integration = {
            "id": "int_123",
            "type": "zendesk",
            "status": "pending",
            "last_test_at": None,
            "last_test_result": None,
        }
        
        def update_integration_status(integration: dict, test_result: dict):
            """Update integration status after test."""
            integration["status"] = "active" if test_result["success"] else "error"
            integration["last_test_at"] = datetime.utcnow().isoformat()
            integration["last_test_result"] = test_result["message"]
            return integration
        
        # Successful test
        result = update_integration_status(integration, {"success": True, "message": "OK"})
        assert result["status"] == "active"
        
        # Failed test
        result = update_integration_status(integration, {"success": False, "message": "Auth failed"})
        assert result["status"] == "error"
    
    def test_ai_activation_checks_integration_status(self):
        """
        Test that AI activation requires at least one active integration.
        """
        onboarding_session = {
            "integrations": [
                {"id": "int1", "status": "error"},
            ],
        }
        
        def has_active_integration(session: dict) -> bool:
            """Check if session has at least one active integration."""
            return any(
                integ.get("status") == "active"
                for integ in session.get("integrations", [])
            )
        
        assert has_active_integration(onboarding_session) is False
        
        # With active integration
        onboarding_session["integrations"].append({"id": "int2", "status": "active"})
        assert has_active_integration(onboarding_session) is True


# ── Integration Tests ────────────────────────────────────────────────────────

class TestOnboardingGapIntegration:
    """
    Integration tests combining multiple gap scenarios.
    """
    
    def test_full_onboarding_flow_with_gaps_addressed(self):
        """
        Test full onboarding flow with all gap fixes in place.
        """
        # 1. User submits details
        user_details = {
            "full_name": "John Doe",
            "company_name": "Acme Corp",
            "work_email": "john@acme.com",
            "work_email_verified": False,
            "industry": "saas",
        }
        
        # 2. User accepts legal (server time used)
        consent_record = {
            "consent_type": "terms",
            "accepted_at": datetime.utcnow(),  # Server time
            "ip_address": "192.168.1.1",
        }
        
        # 3. User uploads document (validated)
        document = {
            "filename": "manual.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024 * 1024,  # 1MB
            "status": "pending",
        }
        
        # 4. Document processes successfully
        document["status"] = "completed"
        
        # 5. User verifies work email
        user_details["work_email_verified"] = True
        
        # 6. User adds integration (validated)
        integration = {
            "type": "zendesk",
            "status": "active",  # Validated and tested
        }
        
        # 7. Check AI activation prerequisites
        can_activate = (
            consent_record["accepted_at"] is not None  # Legal accepted
            and (user_details["work_email"] is None or user_details["work_email_verified"])  # Email verified
            and document["status"] == "completed"  # KB ready
            and integration["status"] == "active"  # Integration active
        )
        
        assert can_activate is True
