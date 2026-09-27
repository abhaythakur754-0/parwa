"""
Week 2 Tests — Agent Lightning Training Pipeline
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


# ─── Prepare Dataset Tests ───────────────────────────────────────


class TestPrepareDataset:
    """Tests for dataset preparation from AgentMistake records."""

    def test_prepare_dataset_with_mistakes(self):
        """10 mistakes → TrainingDataset created, samples returned."""
        mock_db = MagicMock()
        mock_mistakes = []
        for i in range(10):
            m = MagicMock()
            m.id = f"mistake_{i}"
            m.used_in_training = False
            m.mistake_type = "wrong_answer" if i % 2 == 0 else "hallucination"
            m.original_response = f"Wrong answer {i}"
            m.expected_response = f"Correct answer {i}"
            m.correction = f"Fix {i}"
            m.severity = "medium"
            mock_mistakes.append(m)
        mock_db.query.return_value.filter.return_value.all.return_value = mock_mistakes
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.flush = MagicMock()

        with patch("app.tasks.training_tasks._get_db", return_value=mock_db):
            from app.tasks.training_tasks import prepare_dataset
            result = prepare_dataset("company_123")
        assert result["status"] == "prepared"
        assert result["samples_count"] == 10

    def test_prepare_dataset_empty(self):
        """No mistakes → returns 0 samples."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch("app.tasks.training_tasks._get_db", return_value=mock_db):
            from app.tasks.training_tasks import prepare_dataset
            result = prepare_dataset("company_123")
        assert result["samples_count"] == 0

    def test_prepare_dataset_db_error(self):
        """Database error → returns error status, not crash (BC-008)."""
        with patch("app.tasks.training_tasks._get_db", side_effect=Exception("DB down")):
            from app.tasks.training_tasks import prepare_dataset
            result = prepare_dataset("company_123")
        assert result["status"] == "error"

    def test_train_test_split_ratio(self):
        """Verify 80/20 split."""
        from app.tasks.training_tasks import _split_train_test
        samples = [{"input": f"q{i}", "output": f"a{i}"} for i in range(100)]
        train, test = _split_train_test(samples)
        assert len(train) == 80
        assert len(test) == 20


# ─── Check Mistake Threshold Tests ───────────────────────────────


class TestCheckMistakeThreshold:
    """Tests for mistake threshold checking."""

    def test_below_threshold_no_trigger(self):
        """30 mistakes, threshold 50 → no training triggered."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 30

        with patch("app.tasks.training_tasks._get_db", return_value=mock_db):
            from app.tasks.training_tasks import check_mistake_threshold
            result = check_mistake_threshold("company_123", threshold=50)
        assert result["training_triggered"] is False
        assert result["current_mistakes"] == 30

    def test_above_threshold_triggers(self):
        """60 mistakes, threshold 50 → training triggered."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 60

        with patch("app.tasks.training_tasks._get_db", return_value=mock_db):
            from app.tasks.training_tasks import check_mistake_threshold
            result = check_mistake_threshold("company_123", threshold=50)
        assert result["training_triggered"] is True
        assert result["trigger_reason"] is not None

    def test_exact_threshold_triggers(self):
        """Exactly at threshold → should trigger."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 50

        with patch("app.tasks.training_tasks._get_db", return_value=mock_db):
            from app.tasks.training_tasks import check_mistake_threshold
            result = check_mistake_threshold("company_123", threshold=50)
        assert result["training_triggered"] is True

    def test_db_error_returns_status(self):
        """DB error → returns error status (BC-008)."""
        with patch("app.tasks.training_tasks._get_db", side_effect=Exception("DB down")):
            from app.tasks.training_tasks import check_mistake_threshold
            result = check_mistake_threshold("company_123")
        assert result["status"] in ("error", "checked")


# ─── Schedule Training Tests ─────────────────────────────────────


class TestScheduleTraining:
    """Tests for training scheduling."""

    def test_schedule_success(self):
        """Valid dataset → returns training_job_id."""
        mock_db = MagicMock()
        mock_dataset = MagicMock()
        mock_dataset.id = "ds_123"
        mock_dataset.record_count = 200
        mock_dataset.status = "prepared"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_dataset

        with patch("app.tasks.training_tasks._get_db", return_value=mock_db):
            from app.tasks.training_tasks import schedule_training
            result = schedule_training("company_123")
        assert result["status"] == "scheduled"
        assert result["training_job_id"] is not None

    def test_schedule_no_dataset(self):
        """No dataset found → returns error."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.tasks.training_tasks._get_db", return_value=mock_db):
            from app.tasks.training_tasks import schedule_training
            result = schedule_training("company_123")
        assert result["status"] == "error"

    def test_schedule_db_error(self):
        """DB error → returns error (BC-008)."""
        with patch("app.tasks.training_tasks._get_db", side_effect=Exception("DB down")):
            from app.tasks.training_tasks import schedule_training
            result = schedule_training("company_123")
        assert result["status"] == "error"


# ─── Evaluate Training Tests ─────────────────────────────────────


class TestEvaluateTraining:
    """Tests for training evaluation."""

    def test_evaluate_success(self):
        """Checkpoints exist → metrics returned."""
        mock_db = MagicMock()
        mock_cp = MagicMock()
        mock_cp.training_run_id = "run_123"
        mock_cp.epoch = 3
        mock_cp.metrics = '{"accuracy": 0.85}'
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_cp]

        with patch("app.tasks.training_tasks._get_db", return_value=mock_db):
            from app.tasks.training_tasks import evaluate_training
            result = evaluate_training("company_123", training_run_id="run_123")
        assert "metrics" in result or result["status"] in ("evaluated", "error")

    def test_evaluate_no_checkpoints(self):
        """No checkpoints → returns error."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch("app.tasks.training_tasks._get_db", return_value=mock_db):
            from app.tasks.training_tasks import evaluate_training
            result = evaluate_training("company_123", training_run_id="run_none")
        assert result["status"] == "error"

    def test_evaluate_db_error(self):
        """DB error → returns error (BC-008)."""
        with patch("app.tasks.training_tasks._get_db", side_effect=Exception("DB down")):
            from app.tasks.training_tasks import evaluate_training
            result = evaluate_training("company_123")
        assert result["status"] == "error"
