"""
Tests for Week 17 Day 3 — F-100 Agent Lightning Training Loop + F-101 50-Mistake Threshold

Covers:
- AgentTrainingService: training run creation, progress tracking, checkpoint management
- MistakeThresholdService: mistake reporting, threshold checking, auto-training trigger
- LOCKED threshold of 50 (BC-007 rule 10)
- Training API endpoints

Building Codes tested:
- BC-001: Multi-tenant isolation
- BC-004: Background Jobs (Celery task queueing)
- BC-007: LOCKED threshold at 50
- BC-012: Error handling
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

def _mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.query = MagicMock()
    db.flush = MagicMock()
    db.rollback = MagicMock()
    return db


def _make_mock_filter_chain(
        query_result=None,
        scalar_result=None,
        all_result=None,
        first_result=None):
    """Create a properly chained mock filter query."""
    f = MagicMock()
    f.first.return_value = first_result if first_result is not None else (
        query_result if query_result else None)
    f.scalar.return_value = scalar_result if scalar_result is not None else 0
    f.order_by.return_value = f
    f.group_by.return_value = f
    f.limit.return_value = f
    f.offset.return_value = f
    f.all.return_value = all_result if all_result is not None else []
    f.update.return_value = 0
    q = MagicMock()
    q.filter.return_value = f
    return q, f


# ═══════════════════════════════════════════════════════════════════════════════
# F-101: Mistake Threshold Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMistakeThreshold:
    """Test F-101: 50-Mistake Threshold Trigger."""

    def test_locked_threshold_value(self):
        """BC-007 Rule 10: Threshold MUST be 50."""
        from app.services.mistake_threshold_service import MISTAKE_THRESHOLD

        assert MISTAKE_THRESHOLD == 50, (
            "CRITICAL: MISTAKE_THRESHOLD has been modified from the required value of 50. "
            "This violates BC-007 rule 10."
        )

    def test_report_mistake_increments_count(self):
        """Reporting a mistake should increment the count."""
        from app.services.mistake_threshold_service import MistakeThresholdService

        db = _mock_db()
        service = MistakeThresholdService(db)

        # Mock mistake count query
        q, f = _make_mock_filter_chain(scalar_result=1, first_result=None)
        db.query.return_value = q

        result = service.report_mistake(
            company_id="company-1",
            agent_id="agent-1",
            mistake_type="incorrect_response",
            severity="medium",
        )

        assert result["status"] == "reported"
        assert result["mistake_id"] is not None
        db.add.assert_called_once()

    def test_threshold_not_triggered_below_50(self):
        """Below 50 mistakes should not trigger training."""
        from app.services.mistake_threshold_service import MistakeThresholdService

        db = _mock_db()
        service = MistakeThresholdService(db)

        # Mock mistake count at 49
        q, f = _make_mock_filter_chain(scalar_result=49)
        db.query.return_value = q

        result = service.report_mistake(
            company_id="company-1",
            agent_id="agent-1",
            mistake_type="incorrect_response",
        )

        assert result["training_triggered"] is False
        assert result["current_count"] == 49

    def test_threshold_triggered_at_50(self):
        """At exactly 50 mistakes, training should be triggered."""
        from app.services.mistake_threshold_service import MistakeThresholdService

        db = _mock_db()
        service = MistakeThresholdService(db)

        # Mock mistake count at 50
        call_count = [0]

        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: count query
                return _make_mock_filter_chain(scalar_result=50)[0]
            elif call_count[0] == 2:
                # Second call: existing training run check
                return _make_mock_filter_chain(first_result=None)[0]
            else:
                return _make_mock_filter_chain(first_result=None)[0]

        db.query.side_effect = query_side_effect

        # Mock dataset creation
        mock_dataset = MagicMock()
        mock_dataset.id = uuid.uuid4()
        mock_mistakes = [MagicMock() for _ in range(50)]

        with patch.object(service, '_create_dataset_from_mistakes') as mock_create:
            mock_create.return_value = {
                "dataset_id": "dataset-1", "sample_count": 50}

            with patch.object(service, '_trigger_training_if_needed') as mock_trigger:
                mock_trigger.return_value = (True, "run-1")

                result = service.report_mistake(
                    company_id="company-1",
                    agent_id="agent-1",
                    mistake_type="incorrect_response",
                )

        assert result["current_count"] == 50

    def test_get_threshold_status(self):
        """Test threshold status retrieval."""
        from app.services.mistake_threshold_service import MistakeThresholdService

        db = _mock_db()
        service = MistakeThresholdService(db)

        q, f = _make_mock_filter_chain(scalar_result=25)
        db.query.return_value = q

        status = service.get_threshold_status("company-1", "agent-1")

        assert status["current_count"] == 25
        assert status["threshold"] == 50
        assert status["percentage"] == 50.0
        assert status["triggered"] is False
        assert status["remaining"] == 25

    def test_get_mistake_stats(self):
        """Test mistake statistics retrieval."""
        from app.services.mistake_threshold_service import MistakeThresholdService

        db = _mock_db()
        service = MistakeThresholdService(db)

        # Mock total count
        total_q, total_f = _make_mock_filter_chain(scalar_result=30)

        # Mock by_type query
        by_type_q, by_type_f = _make_mock_filter_chain(all_result=[
            ("incorrect_response", 15), ("hallucination", 10), ("tone_issue", 5)
        ])

        # Mock by_severity query
        by_sev_q, by_sev_f = _make_mock_filter_chain(all_result=[
            ("low", 5), ("medium", 15), ("high", 10)
        ])

        # Mock used_in_training count
        used_q, used_f = _make_mock_filter_chain(scalar_result=10)

        call_idx = [0]

        def query_side_effect(*args, **kwargs):
            call_idx[0] += 1
            if call_idx[0] == 1:
                return total_q
            elif call_idx[0] == 2:
                return by_type_q
            elif call_idx[0] == 3:
                return by_sev_q
            else:
                return used_q

        db.query.side_effect = query_side_effect

        stats = service.get_mistake_stats("company-1", "agent-1")

        assert stats["total_mistakes"] == 30
        assert stats["threshold"] == 50
        assert stats["by_type"]["incorrect_response"] == 15
        assert stats["by_severity"]["medium"] == 15
        assert stats["available_for_training"] == 20


class TestMistakeThresholdImmutable:
    """Test that the threshold cannot be changed."""

    def test_threshold_constant_exists(self):
        """Verify the threshold constant is imported correctly."""
        from app.services.mistake_threshold_service import MISTAKE_THRESHOLD

        # This test will fail if the threshold is changed
        assert MISTAKE_THRESHOLD == 50

    def test_threshold_not_in_db(self):
        """Verify that threshold is not stored in database."""
        # This is a design verification - threshold should be code-only
        from app.services.mistake_threshold_service import MistakeThresholdService

        # The service should NOT have any DB query for threshold
        # It should use the constant directly
        service = MistakeThresholdService(_mock_db())
        status = service.get_threshold_status("company-1", "agent-1")

        # Hard-coded value in response
        assert status["threshold"] == 50


# ═══════════════════════════════════════════════════════════════════════════════
# F-100: Agent Training Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentTrainingService:
    """Test F-100: Agent Lightning Training Loop."""

    def test_create_training_run(self):
        """Test creating a new training run."""
        from app.services.agent_training_service import AgentTrainingService

        db = _mock_db()
        service = AgentTrainingService(db)

        # Mock dataset query
        mock_dataset = MagicMock()
        mock_dataset.id = uuid.uuid4()
        mock_dataset.record_count = 100
        mock_dataset.status = "ready"

        q, f = _make_mock_filter_chain(
            first_result=mock_dataset, scalar_result=0)
        db.query.return_value = q

        with patch.object(service, '_queue_training_task') as mock_queue:
            result = service.create_training_run(
                company_id="company-1",
                agent_id="agent-1",
                dataset_id="dataset-1",
            )

        assert result["status"] == "created"
        assert result["run_id"] is not None
        assert result["epochs"] == 3  # Default
        db.add.assert_called()

    def test_create_training_run_insufficient_samples(self):
        """Training should fail with less than 50 samples."""
        from app.services.agent_training_service import AgentTrainingService

        db = _mock_db()
        service = AgentTrainingService(db)

        # Mock dataset with too few samples
        mock_dataset = MagicMock()
        mock_dataset.id = uuid.uuid4()
        mock_dataset.record_count = 30  # Below minimum

        q, f = _make_mock_filter_chain(first_result=mock_dataset)
        db.query.return_value = q

        result = service.create_training_run(
            company_id="company-1",
            agent_id="agent-1",
            dataset_id="dataset-1",
        )

        assert result["status"] == "error"
        assert "50" in result["error"]

    def test_create_training_run_already_training(self):
        """Cannot create training run if agent is already training."""
        from app.services.agent_training_service import AgentTrainingService

        db = _mock_db()
        service = AgentTrainingService(db)

        # Mock dataset with enough samples
        mock_dataset = MagicMock()
        mock_dataset.record_count = 100

        # Mock existing running training
        mock_existing_run = MagicMock()
        mock_existing_run.id = uuid.uuid4()

        call_idx = [0]

        def query_side_effect(*args, **kwargs):
            call_idx[0] += 1
            if call_idx[0] == 1:
                return _make_mock_filter_chain(first_result=mock_dataset)[0]
            else:
                return _make_mock_filter_chain(
                    first_result=mock_existing_run)[0]

        db.query.side_effect = query_side_effect

        result = service.create_training_run(
            company_id="company-1",
            agent_id="agent-1",
            dataset_id="dataset-1",
        )

        assert result["status"] == "error"
        assert "already" in result["error"].lower()

    def test_update_progress(self):
        """Test updating training progress."""
        from app.services.agent_training_service import AgentTrainingService

        db = _mock_db()
        service = AgentTrainingService(db)

        # Mock training run
        mock_run = MagicMock()
        mock_run.id = uuid.uuid4()
        mock_run.status = "running"
        mock_run.metrics = {}

        q, f = _make_mock_filter_chain(first_result=mock_run)
        db.query.return_value = q

        result = service.update_progress(
            company_id="company-1",
            run_id="run-1",
            epoch=2,
            progress_pct=66.0,
            metrics={"loss": 0.15, "accuracy": 0.85},
        )

        assert result["status"] == "updated"
        assert mock_run.current_epoch == 2
        assert mock_run.progress_pct == 66.0

    def test_complete_training_run(self):
        """Test completing a training run."""
        from app.services.agent_training_service import AgentTrainingService

        db = _mock_db()
        service = AgentTrainingService(db)

        # Mock training run
        mock_run = MagicMock()
        mock_run.id = uuid.uuid4()
        mock_run.status = "running"
        mock_run.metrics = {}

        q, f = _make_mock_filter_chain(first_result=mock_run)
        db.query.return_value = q

        result = service.complete_training_run(
            company_id="company-1",
            run_id="run-1",
            model_path="/models/run-1/final",
            final_metrics={"loss": 0.1, "accuracy": 0.9},
            cost_usd=1.5,
        )

        assert result["status"] == "completed"
        assert mock_run.model_path == "/models/run-1/final"

    def test_fail_training_run(self):
        """Test failing a training run."""
        from app.services.agent_training_service import AgentTrainingService

        db = _mock_db()
        service = AgentTrainingService(db)

        # Mock training run
        mock_run = MagicMock()
        mock_run.id = uuid.uuid4()

        q, f = _make_mock_filter_chain(first_result=mock_run)
        db.query.return_value = q

        result = service.fail_training_run(
            company_id="company-1",
            run_id="run-1",
            error_message="GPU instance crashed",
        )

        assert result["status"] == "failed"
        assert mock_run.error_message == "GPU instance crashed"

    def test_list_training_runs(self):
        """Test listing training runs."""
        from app.services.agent_training_service import AgentTrainingService

        db = _mock_db()
        service = AgentTrainingService(db)

        # Mock training runs
        mock_runs = []
        for i in range(3):
            run = MagicMock()
            run.id = uuid.uuid4()
            run.company_id = "company-1"
            run.agent_id = "agent-1"
            run.dataset_id = None
            run.name = f"Run {i}"
            run.trigger = "manual"
            run.base_model = "gpt-4"
            run.status = "completed"
            run.progress_pct = 100
            run.current_epoch = 3
            run.total_epochs = 3
            run.epochs = 3
            run.learning_rate = 0.0001
            run.batch_size = 16
            run.metrics = {}
            run.model_path = None
            run.checkpoint_path = None
            run.provider = None
            run.instance_id = None
            run.gpu_type = None
            run.cost_usd = 1.5
            run.started_at = datetime.now(timezone.utc)
            run.completed_at = datetime.now(timezone.utc)
            run.created_at = datetime.now(timezone.utc)
            run.error_message = None
            mock_runs.append(run)

        q, f = _make_mock_filter_chain(all_result=mock_runs, scalar_result=3)
        db.query.return_value = q

        result = service.list_training_runs("company-1")

        assert result["total"] == 3
        assert len(result["runs"]) == 3

    def test_get_training_stats(self):
        """Test getting training statistics."""
        from app.services.agent_training_service import AgentTrainingService

        db = _mock_db()
        service = AgentTrainingService(db)

        # Mock training runs with different statuses
        mock_runs = []
        for status, count in [
                ("completed", 5), ("failed", 2), ("running", 1), ("queued", 1)]:
            for _ in range(count):
                run = MagicMock()
                run.status = status
                run.trigger = "manual"
                run.cost_usd = 1.5
                mock_runs.append(run)

        q, f = _make_mock_filter_chain(all_result=mock_runs)
        db.query.return_value = q

        stats = service.get_training_stats("company-1")

        assert stats["total_runs"] == 9
        assert stats["completed"] == 5
        assert stats["failed"] == 2


class TestTrainingCheckpoints:
    """Test checkpoint management."""

    def test_create_checkpoint(self):
        """Test creating a training checkpoint."""
        from app.services.agent_training_service import AgentTrainingService

        db = _mock_db()
        service = AgentTrainingService(db)

        # Mock training run
        mock_run = MagicMock()
        mock_run.id = uuid.uuid4()

        q, f = _make_mock_filter_chain(first_result=mock_run)
        db.query.return_value = q

        result = service.create_checkpoint(
            company_id="company-1",
            run_id="run-1",
            epoch=2,
            checkpoint_name="epoch_2_checkpoint",
            metrics={"loss": 0.15, "accuracy": 0.85},
            is_best=True,
        )

        assert result["status"] == "created"
        assert result["is_best"] is True
        db.add.assert_called()

    def test_get_best_checkpoint(self):
        """Test retrieving the best checkpoint."""
        from app.services.agent_training_service import AgentTrainingService

        db = _mock_db()
        service = AgentTrainingService(db)

        # Mock checkpoint
        mock_checkpoint = MagicMock()
        mock_checkpoint.id = uuid.uuid4()
        mock_checkpoint.checkpoint_name = "best_checkpoint"
        mock_checkpoint.model_path = "/models/best.pt"
        mock_checkpoint.s3_path = None
        mock_checkpoint.epoch = 3
        mock_checkpoint.metrics = {"loss": 0.1, "accuracy": 0.9}
        mock_checkpoint.created_at = datetime.now(timezone.utc)

        q, f = _make_mock_filter_chain(first_result=mock_checkpoint)
        db.query.return_value = q

        result = service.get_best_checkpoint("company-1", "run-1")

        assert result is not None
        assert result["checkpoint_name"] == "best_checkpoint"


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrainingIntegration:
    """Integration tests for F-100 + F-101."""

    def test_mistake_triggers_training_flow(self):
        """When 50 mistakes are reached, training should be triggered."""
        from app.services.mistake_threshold_service import MistakeThresholdService

        db = _mock_db()
        mistake_service = MistakeThresholdService(db)

        # Simulate reaching threshold
        call_idx = [0]

        def query_side_effect(*args, **kwargs):
            call_idx[0] += 1
            if call_idx[0] == 1:
                # Mistake count at threshold
                return _make_mock_filter_chain(scalar_result=50)[0]
            else:
                return _make_mock_filter_chain(first_result=None)[0]

        db.query.side_effect = query_side_effect

        with patch.object(mistake_service, '_create_dataset_from_mistakes') as mock_dataset:
            mock_dataset.return_value = {
                "dataset_id": "dataset-1", "sample_count": 50}

            with patch.object(mistake_service, '_trigger_training_if_needed') as mock_trigger:
                mock_trigger.return_value = (True, "run-1")

                with patch.object(mistake_service, '_create_audit_trail'):
                    with patch.object(mistake_service, '_send_threshold_notification'):
                        result = mistake_service.report_mistake(
                            company_id="company-1",
                            agent_id="agent-1",
                            mistake_type="incorrect_response",
                        )

        # Verify training was triggered
        mock_trigger.assert_called_once()
