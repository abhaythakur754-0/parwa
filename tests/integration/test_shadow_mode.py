"""
Shadow Mode Integration Tests.

Tests for shadow mode processing - ensuring the AI processes tickets
correctly WITHOUT sending responses to customers.

CRITICAL: All tests verify that no real responses are ever sent.
"""
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from clients.shadow_mode_handler import (
    ShadowModeHandler,
    ShadowTicket,
    ShadowDecision,
    HumanDecision,
    ShadowResult,
    DecisionType,
    ShadowModeStatus,
    create_mock_ai_processor
)


class TestShadowModeHandler:
    """Tests for ShadowModeHandler."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def handler(self, temp_output_dir):
        """Create a shadow mode handler."""
        return ShadowModeHandler(
            client_id="test_client",
            output_dir=temp_output_dir
        )

    @pytest.fixture
    def sample_ticket(self):
        """Create a sample ticket."""
        return ShadowTicket(
            ticket_id=f"TKT-{uuid.uuid4().hex[:8].upper()}",
            client_id="test_client",
            subject="Test Subject",
            body="This is a test ticket body about a refund request.",
            customer_email="test@example.com",
            category="returns",
            priority="high"
        )

    @pytest.fixture
    def mock_processor(self):
        """Create a mock AI processor."""
        return create_mock_ai_processor()

    def test_handler_initialization(self, handler):
        """Test that handler initializes correctly."""
        assert handler.client_id == "test_client"
        assert handler._processed_count == 0
        assert handler._error_count == 0
        assert handler._response_send_attempts == 0

    def test_process_single_ticket(self, handler, sample_ticket, mock_processor):
        """Test processing a single ticket in shadow mode."""
        result = handler.process_ticket(sample_ticket, mock_processor)

        assert result is not None
        assert result.ticket_id == sample_ticket.ticket_id
        assert result.shadow_decision is not None
        assert result.shadow_decision.decision_type in DecisionType
        assert result.shadow_decision.confidence >= 0
        assert result.shadow_decision.confidence <= 1

    def test_no_response_sent_to_customer(self, handler, sample_ticket, mock_processor):
        """CRITICAL: Verify no response is sent to customer."""
        result = handler.process_ticket(sample_ticket, mock_processor)

        # Verify safety checks
        assert handler._response_send_attempts == 0
        assert "NO response sent" in result.notes

        # Verify class-level safety check
        assert ShadowModeHandler.verify_no_responses_sent() is True

    def test_cross_tenant_isolation(self, handler, mock_processor):
        """Test that cross-tenant access is blocked."""
        # Create a ticket for a different client
        other_client_ticket = ShadowTicket(
            ticket_id="TKT-OTHER",
            client_id="other_client",
            subject="Test",
            body="Test body",
            customer_email="other@example.com"
        )

        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            handler.process_ticket(other_client_ticket, mock_processor)

        assert "Cross-tenant violation" in str(exc_info.value)

    def test_process_batch_tickets(self, handler, mock_processor):
        """Test processing multiple tickets."""
        tickets = [
            ShadowTicket(
                ticket_id=f"TKT-{i}",
                client_id="test_client",
                subject=f"Test {i}",
                body="I want a refund for my order.",
                customer_email=f"customer{i}@example.com"
            )
            for i in range(10)
        ]

        results = handler.process_batch(tickets, mock_processor)

        assert len(results) == 10
        assert handler._processed_count == 10

    def test_progress_callback(self, handler, mock_processor):
        """Test that progress callback is called."""
        tickets = [
            ShadowTicket(
                ticket_id=f"TKT-{i}",
                client_id="test_client",
                subject=f"Test {i}",
                body="Test body",
                customer_email=f"test{i}@example.com"
            )
            for i in range(5)
        ]

        progress_values = []

        def callback(current, total):
            progress_values.append((current, total))

        handler.process_batch(tickets, mock_processor, progress_callback=callback)

        assert len(progress_values) == 5
        assert progress_values[-1] == (5, 5)

    def test_compare_with_human_decision(self, handler, sample_ticket, mock_processor):
        """Test comparing AI decision with human decision."""
        # Process ticket first
        result = handler.process_ticket(sample_ticket, mock_processor)

        # Create human decision
        human_decision = HumanDecision(
            ticket_id=sample_ticket.ticket_id,
            decision_type=DecisionType.REFUND_APPROVE,
            actual_response="Your refund has been processed.",
            human_agent="human_001"
        )

        # Compare
        updated_result = handler.compare_with_human(
            sample_ticket.ticket_id,
            human_decision
        )

        assert updated_result.human_decision is not None
        assert updated_result.is_match is not None
        assert updated_result.accuracy_score is not None

    def test_accuracy_metrics(self, handler, mock_processor):
        """Test accuracy metrics calculation."""
        # Process some tickets
        for i in range(5):
            ticket = ShadowTicket(
                ticket_id=f"TKT-{i}",
                client_id="test_client",
                subject="Refund request",
                body="I need a refund.",
                customer_email=f"test{i}@example.com"
            )
            handler.process_ticket(ticket, mock_processor)

            # Add human comparison
            human = HumanDecision(
                ticket_id=f"TKT-{i}",
                decision_type=DecisionType.REFUND_APPROVE,
                actual_response="Refund processed",
                human_agent="agent_1"
            )
            handler.compare_with_human(f"TKT-{i}", human)

        metrics = handler.get_accuracy_metrics()

        assert "total_processed" in metrics
        assert metrics["total_processed"] == 5
        assert "accuracy" in metrics
        assert "avg_confidence" in metrics

    def test_export_results(self, handler, mock_processor):
        """Test exporting results to file."""
        ticket = ShadowTicket(
            ticket_id="TKT-EXPORT",
            client_id="test_client",
            subject="Export test",
            body="Test export",
            customer_email="export@example.com"
        )
        handler.process_ticket(ticket, mock_processor)

        export_path = handler.export_results("test_export.json")

        assert Path(export_path).exists()

        # Verify export content
        with open(export_path, 'r') as f:
            data = json.load(f)

        assert data["client_id"] == "test_client"
        assert data["safety_verification"]["all_responses_prevented"] is True
        assert data["safety_verification"]["response_send_attempts"] == 0

    def test_pii_redaction(self, handler, sample_ticket, mock_processor):
        """Test that PII is redacted in logs."""
        handler.process_ticket(sample_ticket, mock_processor)

        # Find the log file
        log_files = list(Path(handler.output_dir).glob("shadow_log_*.jsonl"))
        assert len(log_files) > 0

        # Read log and check PII redaction
        with open(log_files[0], 'r') as f:
            log_content = f.read()

        # Email should be redacted
        assert "test@example.com" not in log_content
        assert "***" in log_content

    def test_error_handling(self, handler):
        """Test error handling during processing."""
        ticket = ShadowTicket(
            ticket_id="TKT-ERROR",
            client_id="test_client",
            subject="Error test",
            body="This will cause an error",
            customer_email="error@example.com"
        )

        def error_processor(ticket):
            raise Exception("Simulated processing error")

        result = handler.process_ticket(ticket, error_processor)

        assert result.shadow_decision.decision_type == DecisionType.UNKNOWN
        assert "processing error" in result.notes.lower()
        assert handler._error_count == 1


class TestShadowDecision:
    """Tests for ShadowDecision."""

    def test_decision_creation(self):
        """Test creating a shadow decision."""
        decision = ShadowDecision(
            ticket_id="TKT-001",
            decision_type=DecisionType.REFUND_APPROVE,
            confidence=0.95,
            reasoning="Customer eligible for refund",
            suggested_response="Your refund is approved.",
            suggested_actions=["initiate_refund", "notify_customer"],
            agent_used="refund_agent"
        )

        assert decision.ticket_id == "TKT-001"
        assert decision.decision_type == DecisionType.REFUND_APPROVE
        assert decision.confidence == 0.95
        assert len(decision.suggested_actions) == 2

    def test_decision_types(self):
        """Test all decision types are available."""
        expected_types = [
            "auto_reply", "escalate", "refund_approve", "refund_deny",
            "faq_answer", "order_status", "need_info", "unknown"
        ]

        actual_types = [dt.value for dt in DecisionType]

        for expected in expected_types:
            assert expected in actual_types


class TestShadowTicket:
    """Tests for ShadowTicket."""

    def test_ticket_creation(self):
        """Test creating a shadow ticket."""
        ticket = ShadowTicket(
            ticket_id="TKT-001",
            client_id="client_001",
            subject="Test Subject",
            body="Test body content",
            customer_email="customer@example.com",
            category="returns",
            priority="high"
        )

        assert ticket.ticket_id == "TKT-001"
        assert ticket.client_id == "client_001"
        assert ticket.created_at is not None

    def test_ticket_defaults(self):
        """Test ticket default values."""
        ticket = ShadowTicket(
            ticket_id="TKT-002",
            client_id="client_001",
            subject="Test",
            body="Body",
            customer_email="test@example.com"
        )

        assert ticket.category is None
        assert ticket.priority is None
        assert ticket.metadata == {}


class TestMockAIProcessor:
    """Tests for the mock AI processor."""

    def test_refund_detection(self):
        """Test that refund requests are detected."""
        processor = create_mock_ai_processor()

        ticket = ShadowTicket(
            ticket_id="TKT-REFUND",
            client_id="test",
            subject="Refund",
            body="I want a refund for my order",
            customer_email="test@example.com"
        )

        decision = processor(ticket)

        assert decision.decision_type == DecisionType.REFUND_APPROVE
        assert decision.confidence > 0.8

    def test_order_status_detection(self):
        """Test that order status requests are detected."""
        processor = create_mock_ai_processor()

        ticket = ShadowTicket(
            ticket_id="TKT-ORDER",
            client_id="test",
            subject="Order",
            body="Where is my order status?",
            customer_email="test@example.com"
        )

        decision = processor(ticket)

        assert decision.decision_type == DecisionType.ORDER_STATUS

    def test_escalation_detection(self):
        """Test that escalation requests are detected."""
        processor = create_mock_ai_processor()

        ticket = ShadowTicket(
            ticket_id="TKT-ESC",
            client_id="test",
            subject="Escalation",
            body="I need to speak to a manager please",
            customer_email="test@example.com"
        )

        decision = processor(ticket)

        assert decision.decision_type == DecisionType.ESCALATE
        assert decision.confidence > 0.9


class TestSafetyVerification:
    """Tests for safety verification of shadow mode."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_class_level_safety_check(self, temp_output_dir):
        """Test class-level safety verification."""
        # Create multiple handlers
        handler1 = ShadowModeHandler("client_1", temp_output_dir)
        handler2 = ShadowModeHandler("client_2", temp_output_dir)

        # Verify all instances have zero send attempts
        assert ShadowModeHandler.verify_no_responses_sent() is True

    def test_response_send_attempts_never_increased(self, temp_output_dir):
        """Test that response_send_attempts is never increased during normal processing."""
        handler = ShadowModeHandler("test_client", temp_output_dir)
        processor = create_mock_ai_processor()
        
        ticket = ShadowTicket(
            ticket_id="TKT-SAFETY",
            client_id="test_client",
            subject="Safety Test",
            body="Test body",
            customer_email="safety@example.com"
        )
        
        handler.process_ticket(ticket, processor)

        # The handler should never increment this counter
        assert handler._response_send_attempts == 0


class TestIntegration:
    """Integration tests for shadow mode."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_50_tickets_processed_without_errors(self, temp_output_dir):
        """Test processing 50 tickets as required by Week 19."""
        handler = ShadowModeHandler(
            client_id="integration_test",
            output_dir=temp_output_dir
        )
        processor = create_mock_ai_processor()

        tickets = [
            ShadowTicket(
                ticket_id=f"TKT-{i:04d}",
                client_id="integration_test",
                subject=f"Test Ticket {i}",
                body="I have a question about my refund order status.",
                customer_email=f"customer{i}@example.com"
            )
            for i in range(50)
        ]

        results = handler.process_batch(tickets, processor)

        # Verify all 50 processed
        assert len(results) == 50
        assert handler._processed_count == 50

        # Verify no errors
        assert handler._error_count == 0

        # Verify no responses sent
        assert handler._response_send_attempts == 0

    def test_full_workflow(self, temp_output_dir):
        """Test the complete shadow mode workflow."""
        handler = ShadowModeHandler(
            client_id="workflow_test",
            output_dir=temp_output_dir
        )
        processor = create_mock_ai_processor()

        # Process tickets
        for i in range(10):
            ticket = ShadowTicket(
                ticket_id=f"TKT-WF-{i}",
                client_id="workflow_test",
                subject=f"Workflow Test {i}",
                body="Test body for workflow",
                customer_email=f"wf{i}@example.com"
            )
            handler.process_ticket(ticket, processor)

        # Add human comparisons
        for i in range(10):
            human = HumanDecision(
                ticket_id=f"TKT-WF-{i}",
                decision_type=DecisionType.AUTO_REPLY,
                actual_response="Response sent",
                human_agent="agent_1"
            )
            handler.compare_with_human(f"TKT-WF-{i}", human)

        # Get metrics
        metrics = handler.get_accuracy_metrics()
        assert metrics["total_processed"] == 10
        assert metrics["total_compared"] == 10

        # Export results
        export_path = handler.export_results()
        assert Path(export_path).exists()

        # Verify export
        with open(export_path, 'r') as f:
            data = json.load(f)

        assert data["safety_verification"]["all_responses_prevented"] is True


class TestEdgeCases:
    """Tests for edge cases and error scenarios."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_empty_ticket_body(self, temp_output_dir):
        """Test handling of empty ticket body."""
        handler = ShadowModeHandler("test", temp_output_dir)
        processor = create_mock_ai_processor()

        ticket = ShadowTicket(
            ticket_id="TKT-EMPTY",
            client_id="test",
            subject="Empty",
            body="",
            customer_email="empty@example.com"
        )

        result = handler.process_ticket(ticket, processor)

        # Should still process without crashing
        assert result is not None

    def test_very_long_ticket_body(self, temp_output_dir):
        """Test handling of very long ticket body."""
        handler = ShadowModeHandler("test", temp_output_dir)
        processor = create_mock_ai_processor()

        long_body = "This is a long message. " * 1000

        ticket = ShadowTicket(
            ticket_id="TKT-LONG",
            client_id="test",
            subject="Long",
            body=long_body,
            customer_email="long@example.com"
        )

        result = handler.process_ticket(ticket, processor)

        assert result is not None

    def test_special_characters_in_ticket(self, temp_output_dir):
        """Test handling of special characters."""
        handler = ShadowModeHandler("test", temp_output_dir)
        processor = create_mock_ai_processor()

        ticket = ShadowTicket(
            ticket_id="TKT-SPECIAL",
            client_id="test",
            subject="Special chars: <>&\"'",
            body="Body with emoji 🎉 and special chars: <script>alert('test')</script>",
            customer_email="special@example.com"
        )

        result = handler.process_ticket(ticket, processor)

        assert result is not None

    def test_compare_nonexistent_ticket(self, temp_output_dir):
        """Test comparing a ticket that wasn't processed."""
        handler = ShadowModeHandler("test", temp_output_dir)

        human = HumanDecision(
            ticket_id="NONEXISTENT",
            decision_type=DecisionType.AUTO_REPLY,
            actual_response="Response",
            human_agent="agent"
        )

        with pytest.raises(ValueError):
            handler.compare_with_human("NONEXISTENT", human)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
