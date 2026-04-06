"""Tests for Day 22 training tasks."""

from tests.unit.test_day22_setup import setup_day22_tests  # noqa: E402
setup_day22_tests()
from backend.app.tasks.training_tasks import (  # noqa: E402
    prepare_dataset,
    check_mistake_threshold,
    schedule_training,
)


class TestPrepareDataset:
    def test_returns_dict_on_success(self):
        result = prepare_dataset("company-123")
        assert isinstance(result, dict)

    def test_return_has_status_prepared(self):
        result = prepare_dataset("company-123")
        assert result["status"] == "prepared"

    def test_return_has_dataset_type(self):
        result = prepare_dataset("company-123", dataset_type="sentiment")
        assert result["dataset_type"] == "sentiment"

    def test_return_has_samples_count(self):
        result = prepare_dataset("company-123")
        assert "samples_count" in result

    def test_return_has_train_and_test_count(self):
        result = prepare_dataset("company-123")
        assert "train_count" in result
        assert "test_count" in result

    def test_default_dataset_type(self):
        result = prepare_dataset("company-123")
        assert result["dataset_type"] == "classification"

    def test_queue_is_training(self):
        assert prepare_dataset.queue == "training"

    def test_max_retries_is_2(self):
        assert prepare_dataset.max_retries == 2

    def test_soft_time_limit(self):
        assert prepare_dataset.soft_time_limit == 300

    def test_time_limit(self):
        assert prepare_dataset.time_limit == 600

    def test_task_name_registered(self):
        assert "training.prepare_dataset" in prepare_dataset.name

    def test_custom_min_samples(self):
        result = prepare_dataset("c1", min_samples=500)
        assert result["status"] == "prepared"


class TestCheckMistakeThreshold:
    def test_returns_dict_on_success(self):
        result = check_mistake_threshold("company-123")
        assert isinstance(result, dict)

    def test_return_has_status_checked(self):
        result = check_mistake_threshold("company-123")
        assert result["status"] == "checked"

    def test_return_has_company_id(self):
        result = check_mistake_threshold("company-123")
        assert result["company_id"] == "company-123"

    def test_return_has_current_mistakes(self):
        result = check_mistake_threshold("company-123")
        assert "current_mistakes" in result

    def test_return_has_threshold(self):
        result = check_mistake_threshold("company-123")
        assert "threshold" in result

    def test_return_has_training_triggered(self):
        result = check_mistake_threshold("company-123")
        assert "training_triggered" in result

    def test_training_triggered_is_bool(self):
        result = check_mistake_threshold("company-123")
        assert isinstance(result["training_triggered"], bool)

    def test_default_threshold(self):
        result = check_mistake_threshold("company-123")
        assert result["threshold"] == 50

    def test_custom_threshold(self):
        result = check_mistake_threshold("company-123", threshold=100)
        assert result["threshold"] == 100

    def test_queue_is_training(self):
        assert check_mistake_threshold.queue == "training"

    def test_max_retries_is_2(self):
        assert check_mistake_threshold.max_retries == 2

    def test_soft_time_limit(self):
        assert check_mistake_threshold.soft_time_limit == 60

    def test_time_limit(self):
        assert check_mistake_threshold.time_limit == 120

    def test_task_name_registered(self):
        assert "training.check_mistake_threshold" in check_mistake_threshold.name


class TestScheduleTraining:
    def test_returns_dict_on_success(self):
        result = schedule_training("company-123")
        assert isinstance(result, dict)

    def test_return_has_status_scheduled(self):
        result = schedule_training("company-123")
        assert result["status"] == "scheduled"

    def test_return_has_model_type(self):
        result = schedule_training("company-123")
        assert "model_type" in result

    def test_return_has_training_job_id(self):
        result = schedule_training("company-123")
        assert "training_job_id" in result

    def test_default_model_type(self):
        result = schedule_training("company-123")
        assert result["model_type"] == "classification"

    def test_custom_model_type(self):
        result = schedule_training("company-123", model_type="sentiment")
        assert result["model_type"] == "sentiment"

    def test_queue_is_training(self):
        assert schedule_training.queue == "training"

    def test_max_retries_is_1(self):
        assert schedule_training.max_retries == 1

    def test_soft_time_limit(self):
        assert schedule_training.soft_time_limit == 60

    def test_time_limit(self):
        assert schedule_training.time_limit == 120

    def test_task_name_registered(self):
        assert "training.schedule_training" in schedule_training.name

    def test_custom_dataset_version(self):
        result = schedule_training("c1", dataset_version="v2.1")
        assert result["status"] == "scheduled"
