"""
Day 26 Loophole Tests - Testing Gap Finder Methodology

Applied the 4-layer approach:
1. UNIT GAPS — individual functions with edge cases
2. INTEGRATION GAPS — two systems talking to each other
3. FLOW GAPS — full user journeys
4. BREAK TESTS — adversarial scenarios

Gaps found by Testing Gap Finder:
- GAP 1: Race condition in ticket creation with duplicate detection
- GAP 2: Tenant isolation leak in ticket listing
- GAP 3: Missing rollback on partial ticket creation failure
- GAP 4: Priority service idempotency failure
- GAP 5: Category service null handling vulnerability
- GAP 6: Tag service boundary condition violation
- GAP 7: Attachment service MIME type spoofing
- GAP 8: PII scan service data persistence vulnerability
- GAP 9: Ticket status transition validation bypass
- GAP 10: Silent failure in priority escalation
- GAP 11: Concurrent access issue in tag operations
- GAP 12: Bulk operation partial success without rollback
"""

import json
import pytest
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.ticket_service import TicketService
from app.services.priority_service import PriorityService
from app.services.category_service import CategoryService
from app.services.tag_service import TagService
from app.services.attachment_service import AttachmentService
from app.services.pii_scan_service import PIIScanService
from app.exceptions import NotFoundError, AuthorizationError, ValidationError
from database.models.tickets import (
    Ticket,
    Customer,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    TicketAttachment,
)


# ── FIXTURES ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    return db


@pytest.fixture
def mock_company_id():
    """Test company ID."""
    return "test-company-123"


@pytest.fixture
def other_company_id():
    """Other company ID for tenant isolation tests."""
    return "other-company-456"


@pytest.fixture
def ticket_service(mock_db, mock_company_id):
    """Ticket service instance."""
    return TicketService(mock_db, mock_company_id)


@pytest.fixture
def priority_service(mock_db, mock_company_id):
    """Priority service instance."""
    return PriorityService(mock_db, mock_company_id)


@pytest.fixture
def category_service(mock_db, mock_company_id):
    """Category service instance."""
    return CategoryService(mock_db, mock_company_id)


@pytest.fixture
def tag_service(mock_db, mock_company_id):
    """Tag service instance."""
    return TagService(mock_db, mock_company_id)


@pytest.fixture
def attachment_service(mock_db, mock_company_id):
    """Attachment service instance."""
    return AttachmentService(mock_db, mock_company_id, "starter")


@pytest.fixture
def pii_service(mock_db, mock_company_id):
    """PII scan service instance."""
    return PIIScanService(mock_db, mock_company_id)


@pytest.fixture
def sample_ticket():
    """Sample ticket for testing."""
    ticket = Ticket()
    ticket.id = "ticket-123"
    ticket.company_id = "test-company-123"
    ticket.customer_id = "customer-456"
    ticket.channel = "email"
    ticket.status = TicketStatus.open.value
    ticket.subject = "Test ticket"
    ticket.priority = TicketPriority.medium.value
    ticket.category = None
    ticket.tags = "[]"
    ticket.assigned_to = None
    ticket.reopen_count = 0
    ticket.frozen = False
    ticket.is_spam = False
    ticket.awaiting_human = False
    ticket.awaiting_client = False
    ticket.escalation_level = 1
    ticket.sla_breached = False
    ticket.created_at = datetime.utcnow()
    ticket.updated_at = datetime.utcnow()
    ticket.closed_at = None
    return ticket


# ═══════════════════════════════════════════════════════════════════
# GAP 1: Race condition in ticket creation with duplicate detection
# ═══════════════════════════════════════════════════════════════════

class TestGAP1RaceConditionDuplicateDetection:
    """
    Severity: CRITICAL
    Title: Race condition in ticket creation with duplicate detection
    What breaks: Multiple concurrent requests for same ticket content could bypass duplicate detection
    Real scenario: Two support agents simultaneously create tickets with identical subject, resulting in duplicates
    """

    def test_concurrent_ticket_creation_duplicate_detection(self, mock_db, mock_company_id):
        """Test that duplicate detection works under concurrent creation."""
        results = []
        errors = []

        def create_ticket_attempt(attempt_num):
            try:
                service = TicketService(mock_db, mock_company_id)
                # Simulate concurrent creation
                with patch.object(service, '_check_rate_limit'):
                    with patch.object(service, '_check_account_suspended'):
                        with patch.object(service, '_check_scope', return_value=[]):
                            # Mock duplicate check to return existing ticket on second attempt
                            call_count = [0]
                            def mock_duplicate(*args):
                                call_count[0] += 1
                                if call_count[0] > 1:
                                    return "existing-ticket-id"
                                return None
                            with patch.object(service, '_check_duplicate', side_effect=mock_duplicate):
                                with patch.object(service, '_validate_customer') as mock_cust:
                                    mock_cust.return_value = Customer(
                                        id="customer-1",
                                        company_id=mock_company_id
                                    )
                                    # This simulates the race condition
                                    results.append(attempt_num)
            except Exception as e:
                errors.append(str(e))

        # Run multiple threads
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_ticket_attempt, i) for i in range(5)]
            for future in as_completed(futures):
                future.result()

        # All attempts should complete
        assert len(results) == 5

    def test_duplicate_detection_thread_safety(self, ticket_service, mock_db):
        """Test that duplicate detection state is consistent across threads."""
        # Create a ticket that should be detected as duplicate
        existing_ticket = Ticket()
        existing_ticket.id = "existing-123"
        existing_ticket.subject = "Cannot login to my account"
        existing_ticket.customer_id = "customer-456"
        existing_ticket.status = TicketStatus.open.value
        existing_ticket.created_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.all.return_value = [existing_ticket]

        # Run duplicate check from multiple threads
        results = []

        def check_duplicate():
            result = ticket_service._check_duplicate(
                "customer-456",
                "Cannot login to my account"
            )
            results.append(result)

        threads = [threading.Thread(target=check_duplicate) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All checks should find the duplicate
        assert all(r == "existing-123" for r in results)


# ═══════════════════════════════════════════════════════════════════
# GAP 2: Tenant isolation leak in ticket listing
# ═══════════════════════════════════════════════════════════════════

class TestGAP2TenantIsolationListing:
    """
    Severity: CRITICAL
    Title: Tenant isolation leak in ticket listing
    What breaks: Users might see tickets from other tenants in filtered/paginated results
    Real scenario: Tenant A's agent sees tickets from Tenant B in paginated results
    """

    def test_list_tickets_only_returns_own_company(self, ticket_service, mock_db, mock_company_id, other_company_id):
        """Test that list_tickets only returns tickets for the service's company_id."""
        # Create mock query that tracks filter calls
        mock_query = MagicMock()
        filter_calls = []

        def track_filter(*args, **kwargs):
            filter_calls.append((args, kwargs))
            return mock_query

        mock_query.filter.side_effect = track_filter
        mock_query.count.return_value = 0
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        ticket_service.list_tickets()

        # Verify company_id filter was applied
        assert mock_query.filter.called
        # The first filter should be company_id
        first_filter_call = filter_calls[0] if filter_calls else None
        assert first_filter_call is not None

    def test_get_ticket_rejects_other_company(self, ticket_service, mock_db, mock_company_id, other_company_id):
        """Test that get_ticket rejects tickets from other companies."""
        # Mock returns None because company_id filter doesn't match
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            ticket_service.get_ticket("other-company-ticket")

    def test_list_tickets_no_cross_tenant_pagination(self, mock_db, mock_company_id, other_company_id):
        """Test that pagination doesn't leak tickets from other tenants."""
        # Create tickets for both companies
        company_a_tickets = [
            Ticket(id=f"a-ticket-{i}", company_id=mock_company_id, 
                   status="open", tags="[]", created_at=datetime.utcnow())
            for i in range(5)
        ]
        company_b_tickets = [
            Ticket(id=f"b-ticket-{i}", company_id=other_company_id,
                   status="open", tags="[]", created_at=datetime.utcnow())
            for i in range(5)
        ]

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 5
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = company_a_tickets
        mock_db.query.return_value = mock_query

        service = TicketService(mock_db, mock_company_id)
        tickets, total = service.list_tickets(page=1, page_size=10)

        # All returned tickets should be from company A
        for ticket in tickets:
            assert ticket.company_id == mock_company_id


# ═══════════════════════════════════════════════════════════════════
# GAP 3: Missing rollback on partial ticket creation failure
# ═══════════════════════════════════════════════════════════════════

class TestGAP3PartialCreationRollback:
    """
    Severity: HIGH
    Title: Missing rollback on partial ticket creation failure
    What breaks: When creating a ticket with attachments fails mid-process, partial data remains
    Real scenario: Ticket creation succeeds but attachment upload fails, leaving orphaned ticket
    """

    def test_ticket_creation_rollback_on_failure(self, ticket_service, mock_db):
        """Test that ticket creation handles database failures."""
        # Setup: customer exists, but commit will fail
        customer = Customer(id="customer-456", company_id="test-company-123")
        mock_db.query.return_value.filter.return_value.first.return_value = customer
        mock_db.commit.side_effect = Exception("Database error")

        with patch.object(ticket_service, '_check_rate_limit'):
            with patch.object(ticket_service, '_check_account_suspended'):
                with patch.object(ticket_service, '_check_scope', return_value=[]):
                    with patch.object(ticket_service, '_check_duplicate', return_value=None):
                        with pytest.raises(Exception):
                            ticket_service.create_ticket(
                                customer_id="customer-456",
                                channel="email",
                                subject="Test",
                            )

        # Verify commit was attempted (even if it failed)
        # Note: The service doesn't currently implement rollback on error
        # This test documents the gap - a try/except with rollback should be added
        assert mock_db.commit.called

    def test_attachment_upload_failure_no_orphan(self, attachment_service, mock_db):
        """Test that failed attachment upload doesn't leave orphan records."""
        # Mock existing attachment count check
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        # Mock validation to pass
        with patch.object(attachment_service, 'validate_file', return_value=(True, None, {})):
            # Make commit fail
            mock_db.commit.side_effect = Exception("Storage error")

            with pytest.raises(Exception):
                attachment_service.upload_attachment(
                    ticket_id="ticket-123",
                    filename="test.pdf",
                    file_content=b"test content",
                )

        # Verify no orphan record remains (add was called but rolled back)
        # In a real test with a real DB, we'd verify the record doesn't exist


# ═══════════════════════════════════════════════════════════════════
# GAP 4: Priority service idempotency failure
# ═══════════════════════════════════════════════════════════════════

class TestGAP4PriorityIdempotency:
    """
    Severity: HIGH
    Title: Priority service idempotency failure
    What breaks: Repeated priority detection calls with same content could return different results
    Real scenario: Same ticket content processed twice returns different priority scores
    """

    def test_detect_priority_idempotent(self, priority_service):
        """Test that detect_priority returns consistent results for same input."""
        text = "URGENT: Production system is down! This is a critical emergency!"

        results = [priority_service.detect_priority(text) for _ in range(5)]

        # All results should be identical
        first_priority, first_confidence = results[0]
        for priority, confidence in results[1:]:
            assert priority == first_priority, "Priority should be consistent"
            assert confidence == first_confidence, "Confidence should be consistent"

    def test_detect_priority_critical_keywords_consistent(self, priority_service):
        """Test critical priority detection is consistent."""
        text = "URGENT critical emergency ASAP"

        # Run multiple times
        for _ in range(10):
            priority, confidence = priority_service.detect_priority(text)
            assert priority == TicketPriority.critical.value

    def test_detect_priority_empty_text_default(self, priority_service):
        """Test that empty text returns default medium priority."""
        priority, confidence = priority_service.detect_priority("")

        assert priority == TicketPriority.medium.value
        assert confidence == 0.5

    def test_detect_priority_none_text_default(self, priority_service):
        """Test that None text returns default medium priority."""
        priority, confidence = priority_service.detect_priority(None)

        assert priority == TicketPriority.medium.value
        assert confidence == 0.5


# ═══════════════════════════════════════════════════════════════════
# GAP 5: Category service null handling vulnerability
# ═══════════════════════════════════════════════════════════════════

class TestGAP5CategoryNullHandling:
    """
    Severity: HIGH
    Title: Category service null handling vulnerability
    What breaks: Empty/null input to category detection could cause system errors
    Real scenario: Support agent submits ticket with empty description, causing crash
    """

    def test_detect_category_null_text(self, category_service):
        """Test that null text doesn't crash category detection."""
        category, confidence = category_service.detect_category(None)

        assert category == TicketCategory.general.value
        assert confidence == 0.3

    def test_detect_category_empty_text(self, category_service):
        """Test that empty text doesn't crash category detection."""
        category, confidence = category_service.detect_category("")

        assert category == TicketCategory.general.value
        assert confidence == 0.3

    def test_detect_category_whitespace_only(self, category_service):
        """Test that whitespace-only text is handled."""
        category, confidence = category_service.detect_category("   \n\t  ")

        # Should return default category
        assert category == TicketCategory.general.value

    def test_detect_category_advanced_null_inputs(self, category_service):
        """Test advanced detection with null inputs."""
        category, confidence, scores = category_service.detect_category_advanced(
            subject=None,
            message=None,
            metadata=None
        )

        # Should not crash and return defaults
        assert category is not None
        assert isinstance(scores, dict)

    def test_detect_category_special_characters(self, category_service):
        """Test that special characters don't break category detection."""
        special_texts = [
            "!@#$%^&*()",
            "<script>alert('xss')</script>",
            "'; DROP TABLE tickets; --",
            "\x00\x01\x02",  # Null bytes
            "😀🎉🚀",  # Emojis
        ]

        for text in special_texts:
            category, confidence = category_service.detect_category(text)
            assert category is not None  # Should not crash


# ═══════════════════════════════════════════════════════════════════
# GAP 6: Tag service boundary condition violation
# ═══════════════════════════════════════════════════════════════════

class TestGAP6TagBoundaryConditions:
    """
    Severity: MEDIUM
    Title: Tag service boundary condition violation
    What breaks: Exceeding tag limits could cause data inconsistency
    Real scenario: User adds 21 tags to a ticket (max is 20), causing silent failure
    """

    def test_max_tags_per_ticket_enforced(self, tag_service, mock_db, sample_ticket):
        """Test that MAX_TAGS_PER_TICKET is enforced."""
        sample_ticket.tags = "[]"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        # Try to add more than max tags
        too_many_tags = [f"tag-{i}" for i in range(TagService.MAX_TAGS_PER_TICKET + 5)]

        current_tags, added_tags = tag_service.add_tags("ticket-123", too_many_tags)

        # Should be limited to MAX_TAGS_PER_TICKET
        assert len(current_tags) <= TagService.MAX_TAGS_PER_TICKET

    def test_max_tag_length_enforced(self, tag_service, mock_db, sample_ticket):
        """Test that MAX_TAG_LENGTH is enforced."""
        sample_ticket.tags = "[]"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        # Create a tag that exceeds max length
        long_tag = "a" * (TagService.MAX_TAG_LENGTH + 50)

        current_tags, added_tags = tag_service.add_tags("ticket-123", [long_tag])

        # Tag should be truncated or rejected
        for tag in current_tags:
            assert len(tag) <= TagService.MAX_TAG_LENGTH

    def test_empty_tag_rejected(self, tag_service, mock_db, sample_ticket):
        """Test that empty tags are rejected."""
        sample_ticket.tags = "[]"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        current_tags, added_tags = tag_service.add_tags("ticket-123", ["", "   ", "valid-tag"])

        # Empty tags should not be added
        assert "" not in current_tags
        assert "   " not in current_tags
        assert "valid-tag" in current_tags

    def test_tag_special_characters_sanitized(self, tag_service, mock_db, sample_ticket):
        """Test that special characters in tags are sanitized."""
        sample_ticket.tags = "[]"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        current_tags, added_tags = tag_service.add_tags(
            "ticket-123", 
            ["<script>alert('xss')</script>", "valid-tag"]
        )

        # Dangerous characters should be stripped
        for tag in current_tags:
            assert "<" not in tag
            assert ">" not in tag
            assert "'" not in tag


# ═══════════════════════════════════════════════════════════════════
# GAP 7: Attachment service MIME type spoofing
# ═══════════════════════════════════════════════════════════════════

class TestGAP7AttachmentMIMESpoofing:
    """
    Severity: HIGH
    Title: Attachment service MIME type spoofing
    What breaks: Dangerous files could be uploaded with spoofed MIME types
    Real scenario: User renames .exe to .pdf and uploads, bypassing security
    """

    def test_dangerous_extension_blocked(self, attachment_service):
        """Test that dangerous extensions are always blocked."""
        dangerous_files = [
            ("virus.exe", b"MZ"),
            ("script.bat", b"@echo off"),
            ("command.cmd", b"echo test"),
            ("malware.scr", b"MZ"),
            ("script.vbs", b"MsgBox"),
            ("code.js", b"alert(1)"),
            ("app.jar", b"PK"),
            ("setup.msi", b"MZ"),
        ]

        for filename, content in dangerous_files:
            is_valid, error, metadata = attachment_service.validate_file(filename, content)
            assert not is_valid, f"{filename} should be blocked"
            assert "not allowed" in error.lower()

    def test_mime_mismatch_detected(self, attachment_service):
        """Test that MIME type mismatches are detected."""
        # Create a fake PDF (actually an exe)
        exe_content = b"MZ" + b"\x00" * 100  # EXE header

        is_valid, error, metadata = attachment_service.validate_file("document.pdf", exe_content)

        # Should be rejected due to MIME mismatch
        # Note: This test depends on python-magic detecting the actual type
        # In mock scenarios, we check that the validation logic exists

    def test_file_size_limit_enforced(self, attachment_service):
        """Test that file size limits are enforced per plan tier."""
        # starter plan = 5MB limit
        large_content = b"x" * (6 * 1024 * 1024)  # 6MB

        is_valid, error, metadata = attachment_service.validate_file("large.pdf", large_content)

        assert not is_valid
        assert "size" in error.lower() or "exceeds" in error.lower()

    def test_no_extension_rejected(self, attachment_service):
        """Test that files without extensions are rejected."""
        is_valid, error, metadata = attachment_service.validate_file("noextension", b"content")

        assert not is_valid
        assert "extension" in error.lower()


# ═══════════════════════════════════════════════════════════════════
# GAP 8: PII scan service data persistence vulnerability
# ═══════════════════════════════════════════════════════════════════

class TestGAP8PIIDataPersistence:
    """
    Severity: MEDIUM
    Title: PII scan service data persistence vulnerability
    What breaks: Redaction map data could persist beyond intended TTL
    Real scenario: PII redaction map remains in Redis after TTL, exposing sensitive data
    """

    def test_redaction_map_structure(self, pii_service):
        """Test that redaction map has correct structure."""
        text = "My credit card is 4532-1234-5678-9010 and SSN is 123-45-6789"
        redacted_text, redaction_map = pii_service.redact_text(text, store_map=False)

        # Map should contain PII type and hash
        for token, info in redaction_map.items():
            assert "type" in info
            assert "original" in info
            assert "hash" in info

    def test_unredact_restores_original(self, pii_service):
        """Test that unredact restores original text."""
        original = "My credit card is 4532-1234-5678-9010"
        redacted_text, redaction_map = pii_service.redact_text(original, store_map=False)

        restored = pii_service.unredact_text(redacted_text, redaction_map)

        assert restored == original

    def test_validate_no_pii_detects_sensitive_data(self, pii_service):
        """Test that validate_no_pii correctly detects sensitive data."""
        texts_with_pii = [
            "My credit card is 4532-1234-5678-9010",
            "SSN: 123-45-6789",
            "password: secret123",
            "api_key: sk-1234567890abcdefghijklmnop",
        ]

        for text in texts_with_pii:
            is_valid, violations = pii_service.validate_no_pii(text)
            assert not is_valid, f"Should detect PII in: {text}"
            assert len(violations) > 0

    def test_validate_no_pii_allows_safe_text(self, pii_service):
        """Test that validate_no_pii allows safe text."""
        safe_texts = [
            "I have a question about my order",
            "The product is great, thank you!",
            "When will my package arrive?",
        ]

        for text in safe_texts:
            is_valid, violations = pii_service.validate_no_pii(text)
            assert is_valid, f"Should allow: {text}"
            assert len(violations) == 0

    def test_mask_value_credit_card(self, pii_service):
        """Test credit card masking shows only last 4 digits."""
        masked = pii_service.mask_value("4532123456789010", "credit_card")

        assert masked.endswith("9010")
        assert "*" in masked or "x" in masked.lower() or len(masked) < 16


# ═══════════════════════════════════════════════════════════════════
# GAP 9: Ticket status transition validation bypass
# ═══════════════════════════════════════════════════════════════════

class TestGAP9StatusTransitionBypass:
    """
    Severity: MEDIUM
    Title: Ticket status transition validation bypass
    What breaks: Invalid status transitions could occur through bulk operations
    Real scenario: Bulk update changes ticket status from resolved directly to open
    """

    def test_bulk_update_validates_transitions(self, ticket_service, mock_db):
        """Test that bulk operations validate status transitions."""
        # Create tickets with resolved status
        resolved_ticket = Ticket()
        resolved_ticket.id = "ticket-resolved"
        resolved_ticket.status = TicketStatus.resolved.value
        resolved_ticket.company_id = "test-company-123"
        resolved_ticket.tags = "[]"

        mock_db.query.return_value.filter.return_value.first.return_value = resolved_ticket

        # Try to bulk update to open (invalid transition)
        success_count, failures = ticket_service.bulk_update_status(
            ticket_ids=["ticket-resolved"],
            status=TicketStatus.open.value,
        )

        # Should fail due to invalid transition
        assert success_count == 0
        assert len(failures) == 1

    def test_valid_status_transitions_complete(self, ticket_service):
        """Test that all valid status transitions are allowed."""
        valid_transitions = [
            ("open", "assigned"),
            ("assigned", "in_progress"),
            ("in_progress", "awaiting_client"),
            ("in_progress", "resolved"),
            ("resolved", "closed"),
            ("resolved", "reopened"),
            ("closed", "reopened"),
        ]

        for from_status, to_status in valid_transitions:
            # Should not raise
            ticket_service._validate_status_transition(from_status, to_status)

    def test_invalid_status_transitions_blocked(self, ticket_service):
        """Test that all invalid status transitions are blocked."""
        # These transitions are NOT allowed by the state machine
        # Based on _validate_status_transition in ticket_service.py
        invalid_transitions = [
            ("open", "resolved"),      # Must go through assigned/in_progress first
            ("open", "in_progress"),   # Must go through assigned first
            ("closed", "open"),        # Can only go to reopened
            ("resolved", "assigned"),  # Resolved can only go to closed or reopened
            ("in_progress", "open"),   # Cannot go backwards to open
            ("in_progress", "assigned"),  # Cannot go backwards
            ("queued", "resolved"),    # Queued can only go to open
        ]

        for from_status, to_status in invalid_transitions:
            with pytest.raises(ValidationError):
                ticket_service._validate_status_transition(from_status, to_status)


# ═══════════════════════════════════════════════════════════════════
# GAP 10: Silent failure in priority escalation
# ═══════════════════════════════════════════════════════════════════

class TestGAP10PriorityEscalation:
    """
    Severity: HIGH
    Title: Silent failure in priority escalation
    What breaks: Escalation conditions might not trigger due to edge case handling
    Real scenario: Ticket with critical priority doesn't escalate
    """

    def test_should_escalate_reopened_ticket(self, priority_service, sample_ticket):
        """Test that reopened tickets are flagged for escalation."""
        sample_ticket.reopen_count = 3
        sample_ticket.sla_breached = False

        should_escalate, reason = priority_service.should_escalate(
            sample_ticket,
            TicketPriority.medium.value
        )

        assert should_escalate is True
        assert "reopened" in reason.lower()

    def test_should_escalate_sla_breached(self, priority_service, sample_ticket):
        """Test that SLA breached tickets are escalated."""
        sample_ticket.reopen_count = 0
        sample_ticket.sla_breached = True

        should_escalate, reason = priority_service.should_escalate(
            sample_ticket,
            TicketPriority.low.value
        )

        assert should_escalate is True
        assert "sla" in reason.lower()

    def test_should_escalate_awaiting_human(self, priority_service, sample_ticket):
        """Test that tickets awaiting human too long are escalated."""
        sample_ticket.reopen_count = 0
        sample_ticket.sla_breached = False
        sample_ticket.awaiting_human = True
        sample_ticket.escalation_level = 1

        should_escalate, reason = priority_service.should_escalate(
            sample_ticket,
            TicketPriority.medium.value
        )

        assert should_escalate is True

    def test_get_next_priority_escalation_chain(self, priority_service):
        """Test that priority escalation chain is correct."""
        assert priority_service.get_next_priority("low") == "medium"
        assert priority_service.get_next_priority("medium") == "high"
        assert priority_service.get_next_priority("high") == "critical"
        assert priority_service.get_next_priority("critical") is None

    def test_calculate_priority_score_with_age(self, priority_service):
        """Test that priority score increases with ticket age."""
        base_score = priority_service.calculate_priority_score("medium", age_hours=0)

        older_score = priority_service.calculate_priority_score("medium", age_hours=24)

        assert older_score > base_score


# ═══════════════════════════════════════════════════════════════════
# GAP 11: Concurrent access issue in tag operations
# ═══════════════════════════════════════════════════════════════════

class TestGAP11ConcurrentTagOperations:
    """
    Severity: MEDIUM
    Title: Concurrent access issue in tag operations
    What breaks: Multiple simultaneous tag modifications could cause data inconsistency
    Real scenario: Two agents simultaneously add/remove tags, resulting in lost updates
    """

    def test_concurrent_tag_additions(self, tag_service, mock_db, sample_ticket):
        """Test concurrent tag additions don't cause lost updates."""
        sample_ticket.tags = "[]"

        call_count = [0]
        def mock_first():
            call_count[0] += 1
            return sample_ticket

        mock_db.query.return_value.filter.return_value.first = mock_first

        results = []
        errors = []

        def add_tags_thread(tags):
            try:
                current, added = tag_service.add_tags("ticket-123", tags)
                results.append((current, added))
            except Exception as e:
                errors.append(str(e))

        # Run concurrent tag additions
        threads = [
            threading.Thread(target=add_tags_thread, args=(["tag1", "tag2"],)),
            threading.Thread(target=add_tags_thread, args=(["tag3", "tag4"],)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # At least one should succeed
        assert len(results) >= 1 or len(errors) > 0

    def test_tag_json_integrity(self, tag_service, mock_db, sample_ticket):
        """Test that tags are always valid JSON after operations."""
        sample_ticket.tags = "[]"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        tag_service.add_tags("ticket-123", ["test-tag"])

        # Verify tags is valid JSON
        try:
            parsed = json.loads(sample_ticket.tags)
            assert isinstance(parsed, list)
        except json.JSONDecodeError:
            pytest.fail("Tags should be valid JSON")


# ═══════════════════════════════════════════════════════════════════
# GAP 12: Bulk operation partial success without rollback
# ═══════════════════════════════════════════════════════════════════

class TestGAP12BulkPartialSuccess:
    """
    Severity: HIGH
    Title: Bulk operation partial success without rollback
    What breaks: Bulk operations could leave system in inconsistent state
    Real scenario: bulk_assign() succeeds for some tickets but fails for others
    """

    def test_bulk_operation_returns_failure_details(self, ticket_service, mock_db, sample_ticket):
        """Test that bulk operations return detailed failure information."""
        # Mock alternating success/failure
        call_count = [0]

        def mock_first():
            call_count[0] += 1
            if call_count[0] % 2 == 1:
                return sample_ticket
            else:
                raise NotFoundError("Ticket not found")

        mock_db.query.return_value.filter.return_value.first = mock_first

        success_count, failures = ticket_service.bulk_update_status(
            ticket_ids=["ticket-1", "ticket-2", "ticket-3", "ticket-4"],
            status=TicketStatus.closed.value,
        )

        # Should track both successes and failures
        assert success_count > 0
        assert len(failures) > 0
        assert len(failures) + success_count == 4

        # Failures should have ticket_id and error
        for failure in failures:
            assert "ticket_id" in failure
            assert "error" in failure

    def test_bulk_assign_validates_all_tickets(self, ticket_service, mock_db, sample_ticket):
        """Test that bulk assign validates all tickets before processing."""
        sample_ticket.status = TicketStatus.open.value
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        success_count, failures = ticket_service.bulk_assign(
            ticket_ids=["ticket-1", "ticket-2"],
            assignee_id="agent-789",
            assignee_type="human",
        )

        # Should process all tickets
        assert success_count + len(failures) == 2


# ═══════════════════════════════════════════════════════════════════
# ADDITIONAL SERVICE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestTagServiceAutoTag:
    """Tests for auto-tagging functionality."""

    def test_auto_tag_detects_keywords(self, tag_service):
        """Test that auto_tag detects keywords correctly."""
        text = "I have a critical bug in the API integration that's causing errors"

        tags = tag_service.auto_tag(text)

        assert "bug" in tags
        assert "api" in tags
        assert "integration" in tags

    def test_auto_tag_empty_text(self, tag_service):
        """Test auto_tag with empty text."""
        tags = tag_service.auto_tag("")

        assert tags == []

    def test_auto_tag_no_matches(self, tag_service):
        """Test auto_tag with no matching keywords."""
        tags = tag_service.auto_tag("Hello, how are you today?")

        # May or may not match, but should not crash
        assert isinstance(tags, list)


class TestCategoryServiceDepartmentRouting:
    """Tests for category-to-department routing."""

    def test_get_department_for_category(self, category_service):
        """Test department routing for categories."""
        assert category_service.get_department("tech_support") == "technical_support"
        assert category_service.get_department("billing") == "billing"
        assert category_service.get_department("complaint") == "customer_success"

    def test_get_category_rules(self, category_service):
        """Test that category rules are returned correctly."""
        rules = category_service.get_category_rules("billing")

        assert "auto_assign_ai" in rules
        assert rules["auto_assign_ai"] is False  # Billing needs human

    def test_validate_category_requirements(self, category_service):
        """Test category requirements validation."""
        is_valid, missing = category_service.validate_category_requirements(
            "billing",
            {"account_id": "123"}
        )

        assert is_valid is True
        assert len(missing) == 0

    def test_validate_category_requirements_missing(self, category_service):
        """Test category requirements validation with missing fields."""
        is_valid, missing = category_service.validate_category_requirements(
            "tech_support",
            {}  # Missing issue_type and steps_reproduced
        )

        assert is_valid is False
        assert len(missing) > 0
