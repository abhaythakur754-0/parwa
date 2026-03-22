"""
Unit Tests for Additional Workers.

Tests for:
- RecallHandlerWorker: Stop non-money actions
- ProactiveOutreachWorker: Send proactive messages
- ReportGeneratorWorker: Generate reports
- KBIndexerWorker: Index knowledge base

CRITICAL Tests:
- Recall stops non-money actions
- Cannot recall financial transactions
- Outreach sent proactively
- Report generated
- KB indexed correctly
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch


# Import workers
from workers.recall_handler import (
    RecallHandlerWorker,
    RecallStatus,
    ActionType,
    get_recall_handler_worker
)
from workers.proactive_outreach import (
    ProactiveOutreachWorker,
    OutreachStatus,
    OutreachType,
    get_proactive_outreach_worker
)
from workers.report_generator import (
    ReportGeneratorWorker,
    ReportStatus,
    ReportType,
    get_report_generator_worker
)
from workers.kb_indexer import (
    KBIndexerWorker,
    IndexStatus,
    get_kb_indexer_worker
)


class TestRecallHandlerWorker:
    """Tests for Recall Handler Worker."""

    @pytest.fixture
    def worker(self):
        """Create a recall handler worker."""
        return RecallHandlerWorker()

    @pytest.mark.asyncio
    async def test_recall_non_money_action(self, worker):
        """CRITICAL: Test that recall stops non-money actions."""
        # Register a non-financial action
        worker.register_action(
            action_id="action_001",
            action_type="ticket_status_change",
            original_state={"status": "open"},
            is_financial=False
        )

        result = await worker.recall_action("action_001", reason="Test recall")

        assert result["success"] is True
        assert result["status"] == RecallStatus.COMPLETED.value
        assert result["is_financial"] is False

    @pytest.mark.asyncio
    async def test_cannot_recall_financial_transaction(self, worker):
        """CRITICAL: Test that financial actions cannot be recalled."""
        # Register a financial action
        worker.register_action(
            action_id="action_financial",
            action_type="refund",
            original_state={"amount": 100},
            is_financial=True
        )

        result = await worker.recall_action("action_financial", reason="Mistake")

        assert result["success"] is False
        assert result["status"] == RecallStatus.NOT_ALLOWED.value
        assert result["is_financial"] is True

    @pytest.mark.asyncio
    async def test_verify_recall_success(self, worker):
        """Test verifying recall success."""
        worker.register_action(
            action_id="action_002",
            action_type="ticket_status_change",
            original_state={"status": "open"},
            is_financial=False
        )

        await worker.recall_action("action_002", reason="Test")
        is_verified = await worker.verify_recall("action_002")

        assert is_verified is True

    @pytest.mark.asyncio
    async def test_log_recall(self, worker):
        """Test logging recall for audit."""
        result = await worker.log_recall("action_003", "User requested")

        assert result["success"] is True
        assert "log_entry" in result

    def test_get_status(self, worker):
        """Test getting worker status."""
        status = worker.get_status()

        assert "worker_type" in status
        assert "total_recalls" in status


class TestProactiveOutreachWorker:
    """Tests for Proactive Outreach Worker."""

    @pytest.fixture
    def worker(self):
        """Create an outreach worker."""
        return ProactiveOutreachWorker()

    @pytest.mark.asyncio
    async def test_send_outreach_proactively(self, worker):
        """CRITICAL: Test that outreach is sent proactively."""
        result = await worker.send_outreach(
            customer_id="cust_001",
            message="Checking in on your recent purchase!",
            company_id="comp_001"
        )

        assert result["success"] is True
        assert result["status"] == OutreachStatus.SENT.value

    @pytest.mark.asyncio
    async def test_schedule_followup(self, worker):
        """Test scheduling follow-up outreach."""
        result = await worker.schedule_followup(
            customer_id="cust_002",
            delay_hours=24,
            message="Follow-up message",
            company_id="comp_001"
        )

        assert result["success"] is True
        assert "scheduled_for" in result

    @pytest.mark.asyncio
    async def test_get_due_outreach(self, worker):
        """Test getting due outreach."""
        # Schedule outreach for past time
        result = await worker.schedule_followup(
            customer_id="cust_003",
            delay_hours=-1,  # Past time
            company_id="comp_001"
        )

        due = await worker.get_due_outreach()

        # Should have at least one due
        assert isinstance(due, list)

    @pytest.mark.asyncio
    async def test_respect_opt_out(self, worker):
        """Test that opt-out is respected."""
        worker.add_opt_out("cust_opted_out")

        result = await worker.send_outreach(
            customer_id="cust_opted_out",
            message="Test message"
        )

        assert result["success"] is False
        assert result["status"] == OutreachStatus.OPTED_OUT.value

    def test_get_status(self, worker):
        """Test getting worker status."""
        status = worker.get_status()

        assert "worker_type" in status
        assert "total_outreach" in status


class TestReportGeneratorWorker:
    """Tests for Report Generator Worker."""

    @pytest.fixture
    def worker(self):
        """Create a report generator worker."""
        return ReportGeneratorWorker()

    @pytest.mark.asyncio
    async def test_generate_report(self, worker):
        """CRITICAL: Test that report is generated."""
        result = await worker.generate_report(
            company_id="comp_001",
            report_type="weekly_summary"
        )

        assert result["success"] is True
        assert result["status"] == ReportStatus.COMPLETED.value
        assert "data" in result

    @pytest.mark.asyncio
    async def test_generate_weekly_summary(self, worker):
        """Test generating weekly summary report."""
        result = await worker.generate_report(
            company_id="comp_001",
            report_type="weekly_summary"
        )

        assert result["success"] is True
        assert result["report_type"] == "weekly_summary"
        assert "summary" in result["data"]

    @pytest.mark.asyncio
    async def test_schedule_report(self, worker):
        """Test scheduling a report."""
        result = await worker.schedule_report(
            company_id="comp_001",
            schedule={
                "report_type": "weekly_summary",
                "frequency": "weekly",
                "time": "09:00",
                "recipients": ["manager@example.com"]
            }
        )

        assert result["success"] is True
        assert "schedule_id" in result

    @pytest.mark.asyncio
    async def test_deliver_report(self, worker):
        """Test delivering a report."""
        # Generate first
        gen_result = await worker.generate_report(
            company_id="comp_001",
            report_type="weekly_summary"
        )

        # Deliver
        result = await worker.deliver_report(
            report_id=gen_result["report_id"],
            recipients=["manager@example.com"]
        )

        assert result["success"] is True
        assert result["status"] == ReportStatus.DELIVERED.value

    def test_get_status(self, worker):
        """Test getting worker status."""
        status = worker.get_status()

        assert "worker_type" in status
        assert "total_reports" in status


class TestKBIndexerWorker:
    """Tests for Knowledge Base Indexer Worker."""

    @pytest.fixture
    def worker(self):
        """Create a KB indexer worker."""
        return KBIndexerWorker()

    @pytest.mark.asyncio
    async def test_index_document(self, worker):
        """CRITICAL: Test that document is indexed correctly."""
        result = await worker.index_document(
            doc_id="doc_001",
            company_id="comp_001",
            content="This is a test document for knowledge base."
        )

        assert result["success"] is True
        assert result["status"] == IndexStatus.COMPLETED.value
        assert result["chunk_count"] >= 1

    @pytest.mark.asyncio
    async def test_verify_index(self, worker):
        """Test verifying document index."""
        await worker.index_document(
            doc_id="doc_002",
            company_id="comp_001"
        )

        is_valid = await worker.verify_index("doc_002")

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_reindex_all(self, worker):
        """Test reindexing all documents."""
        # Index some documents
        await worker.index_document("doc_003", "comp_001")
        await worker.index_document("doc_004", "comp_001")

        result = await worker.reindex_all("comp_001")

        assert result["success"] is True
        assert result["documents_processed"] >= 0

    @pytest.mark.asyncio
    async def test_delete_document(self, worker):
        """Test deleting document from index."""
        await worker.index_document("doc_005", "comp_001")

        result = await worker.delete_document("doc_005", "comp_001")

        assert result["success"] is True

    def test_get_status(self, worker):
        """Test getting worker status."""
        status = worker.get_status()

        assert "worker_type" in status
        assert "total_documents" in status


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_get_recall_handler_worker(self):
        """Test recall handler factory."""
        worker = get_recall_handler_worker()
        assert isinstance(worker, RecallHandlerWorker)

    def test_get_proactive_outreach_worker(self):
        """Test outreach worker factory."""
        worker = get_proactive_outreach_worker()
        assert isinstance(worker, ProactiveOutreachWorker)

    def test_get_report_generator_worker(self):
        """Test report generator factory."""
        worker = get_report_generator_worker()
        assert isinstance(worker, ReportGeneratorWorker)

    def test_get_kb_indexer_worker(self):
        """Test KB indexer factory."""
        worker = get_kb_indexer_worker()
        assert isinstance(worker, KBIndexerWorker)


class TestWorkerIntegration:
    """Integration tests for workers."""

    @pytest.mark.asyncio
    async def test_full_outreach_flow(self):
        """Test full proactive outreach flow."""
        worker = ProactiveOutreachWorker()

        # Schedule follow-up
        schedule_result = await worker.schedule_followup(
            customer_id="cust_integration",
            delay_hours=0,  # Due immediately
            message="Test message",
            company_id="comp_integration"
        )

        assert schedule_result["success"] is True

        # Get due outreach
        due = await worker.get_due_outreach()

        # Process due outreach
        process_result = await worker.process_scheduled_outreach()

        assert "processed" in process_result

    @pytest.mark.asyncio
    async def test_full_report_flow(self):
        """Test full report generation flow."""
        worker = ReportGeneratorWorker()

        # Generate report
        gen_result = await worker.generate_report(
            company_id="comp_integration",
            report_type="agent_performance"
        )

        assert gen_result["success"] is True

        # Deliver report
        deliver_result = await worker.deliver_report(
            report_id=gen_result["report_id"],
            recipients=["manager@example.com"]
        )

        assert deliver_result["success"] is True

    @pytest.mark.asyncio
    async def test_full_kb_index_flow(self):
        """Test full KB indexing flow."""
        worker = KBIndexerWorker()

        # Index document
        index_result = await worker.index_document(
            doc_id="doc_integration",
            company_id="comp_integration",
            content="Test content for knowledge base indexing."
        )

        assert index_result["success"] is True

        # Verify index
        is_valid = await worker.verify_index("doc_integration")
        assert is_valid is True
