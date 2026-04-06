"""Tests for Day 22 periodic dispatch tasks."""

from unittest.mock import MagicMock, patch  # noqa: E402
from tests.unit.test_day22_setup import setup_day22_tests  # noqa: E402
setup_day22_tests()
from backend.app.tasks.periodic import (  # noqa: E402
    dispatch_approval_timeout_check,
    dispatch_approval_reminder,
    dispatch_daily_overage,
    dispatch_drift_detection,
    dispatch_metric_aggregation,
    dispatch_training_mistake_check,
)


def _make_company(cid):
    """Create a mock Company object."""
    c = MagicMock()
    c.id = cid
    c.subscription_status = "active"
    return c


class TestDispatchApprovalTimeoutCheck:
    def test_returns_dict_on_db_error(self):
        result = dispatch_approval_timeout_check()
        assert isinstance(result, dict)
        assert "status" in result

    def test_queue_is_default(self):
        assert dispatch_approval_timeout_check.queue == "default"

    def test_task_name_registered(self):
        assert "approval_timeout" in dispatch_approval_timeout_check.name

    def test_max_retries_is_1(self):
        assert dispatch_approval_timeout_check.max_retries == 1


class TestDispatchApprovalReminder:
    def test_returns_dict_on_db_error(self):
        result = dispatch_approval_reminder()
        assert isinstance(result, dict)
        assert "status" in result

    def test_queue_is_default(self):
        assert dispatch_approval_reminder.queue == "default"

    def test_task_name_registered(self):
        assert "reminder" in dispatch_approval_reminder.name

    def test_max_retries_is_1(self):
        assert dispatch_approval_reminder.max_retries == 1


class TestDispatchDailyOverage:
    def test_returns_dict_on_db_error(self):
        result = dispatch_daily_overage()
        assert isinstance(result, dict)
        assert "status" in result

    def test_queue_is_default(self):
        assert dispatch_daily_overage.queue == "default"

    def test_task_name_registered(self):
        assert "daily_overage" in dispatch_daily_overage.name

    def test_max_retries_is_1(self):
        assert dispatch_daily_overage.max_retries == 1


class TestDispatchDriftDetection:
    def test_returns_dict_on_db_error(self):
        result = dispatch_drift_detection()
        assert isinstance(result, dict)
        assert "status" in result

    def test_queue_is_analytics(self):
        assert dispatch_drift_detection.queue == "analytics"

    def test_task_name_registered(self):
        assert "drift_detection" in dispatch_drift_detection.name

    def test_max_retries_is_1(self):
        assert dispatch_drift_detection.max_retries == 1


class TestDispatchMetricAggregation:
    def test_returns_dict_on_db_error(self):
        result = dispatch_metric_aggregation()
        assert isinstance(result, dict)
        assert "status" in result

    def test_queue_is_analytics(self):
        assert dispatch_metric_aggregation.queue == "analytics"

    def test_task_name_registered(self):
        assert "metric_aggregation" in dispatch_metric_aggregation.name

    def test_max_retries_is_1(self):
        assert dispatch_metric_aggregation.max_retries == 1


class TestDispatchTrainingMistakeCheck:
    def test_returns_dict_on_db_error(self):
        result = dispatch_training_mistake_check()
        assert isinstance(result, dict)
        assert "status" in result

    def test_queue_is_training(self):
        assert dispatch_training_mistake_check.queue == "training"

    def test_task_name_registered(self):
        assert "training_mistake_check" in dispatch_training_mistake_check.name

    def test_max_retries_is_1(self):
        assert dispatch_training_mistake_check.max_retries == 1


class TestDispatchDelayCalls:
    @patch("backend.app.tasks.approval_tasks.approval_timeout_check")
    @patch("database.base.SessionLocal")
    def test_dispatches_approval_timeout_check(self, mock_sl, mock_task):
        import sys
        from database.models.core import Company
        sys.modules["database.models.companies"] = type(sys)("companies")
        sys.modules["database.models.companies"].Company = Company
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [
            _make_company("c1"),
        ]
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_sl.return_value = mock_db
        result = dispatch_approval_timeout_check()
        assert result["status"] == "ok"
        mock_task.delay.assert_called_once_with("c1")

    @patch("backend.app.tasks.approval_tasks.approval_reminder")
    @patch("database.base.SessionLocal")
    def test_dispatches_approval_reminder(self, mock_sl, mock_task):
        import sys
        from database.models.core import Company
        sys.modules["database.models.companies"] = type(sys)("companies")
        sys.modules["database.models.companies"].Company = Company
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [
            _make_company("c1"),
        ]
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_sl.return_value = mock_db
        result = dispatch_approval_reminder()
        assert result["status"] == "ok"
        mock_task.delay.assert_called_once_with("c1")

    @patch("backend.app.tasks.billing_tasks.daily_overage_charge")
    @patch("database.base.SessionLocal")
    def test_dispatches_daily_overage(self, mock_sl, mock_task):
        import sys
        from database.models.core import Company
        sys.modules["database.models.companies"] = type(sys)("companies")
        sys.modules["database.models.companies"].Company = Company
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [
            _make_company("c1"),
        ]
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_sl.return_value = mock_db
        result = dispatch_daily_overage()
        assert result["status"] == "ok"
        mock_task.delay.assert_called_once_with("c1")

    @patch("backend.app.tasks.analytics_tasks.drift_detection")
    @patch("database.base.SessionLocal")
    def test_dispatches_drift_detection(self, mock_sl, mock_task):
        import sys
        from database.models.core import Company
        sys.modules["database.models.companies"] = type(sys)("companies")
        sys.modules["database.models.companies"].Company = Company
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [
            _make_company("c1"),
        ]
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_sl.return_value = mock_db
        result = dispatch_drift_detection()
        assert result["status"] == "ok"
        mock_task.delay.assert_called_once_with("c1")

    @patch("backend.app.tasks.analytics_tasks.aggregate_metrics")
    @patch("database.base.SessionLocal")
    def test_dispatches_metric_aggregation(self, mock_sl, mock_task):
        import sys
        from database.models.core import Company
        sys.modules["database.models.companies"] = type(sys)("companies")
        sys.modules["database.models.companies"].Company = Company
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [
            _make_company("c1"),
        ]
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_sl.return_value = mock_db
        result = dispatch_metric_aggregation()
        assert result["status"] == "ok"
        mock_task.delay.assert_called_once_with("c1", period="5min")

    @patch("backend.app.tasks.training_tasks.check_mistake_threshold")
    @patch("database.base.SessionLocal")
    def test_dispatches_training_mistake_check(self, mock_sl, mock_task):
        import sys
        from database.models.core import Company
        sys.modules["database.models.companies"] = type(sys)("companies")
        sys.modules["database.models.companies"].Company = Company
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [
            _make_company("c1"),
        ]
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_sl.return_value = mock_db
        result = dispatch_training_mistake_check()
        assert result["status"] == "ok"
        mock_task.delay.assert_called_once_with("c1")


class TestMetaDispatchTests:
    def test_all_dispatch_tasks_exist(self):
        assert callable(dispatch_approval_timeout_check)
        assert callable(dispatch_approval_reminder)
        assert callable(dispatch_daily_overage)
        assert callable(dispatch_drift_detection)
        assert callable(dispatch_metric_aggregation)
        assert callable(dispatch_training_mistake_check)

    def test_all_dispatch_tasks_have_names(self):
        prefix = "backend.app.tasks.periodic"
        assert dispatch_approval_timeout_check.name.startswith(prefix)
        assert dispatch_approval_reminder.name.startswith(prefix)
        assert dispatch_daily_overage.name.startswith(prefix)
        assert dispatch_drift_detection.name.startswith(prefix)
        assert dispatch_metric_aggregation.name.startswith(prefix)
        assert dispatch_training_mistake_check.name.startswith(prefix)

    def test_all_dispatch_tasks_use_correct_queues(self):
        assert dispatch_approval_timeout_check.queue == "default"
        assert dispatch_approval_reminder.queue == "default"
        assert dispatch_daily_overage.queue == "default"
        assert dispatch_drift_detection.queue == "analytics"
        assert dispatch_metric_aggregation.queue == "analytics"
        assert dispatch_training_mistake_check.queue == "training"

    def test_all_dispatch_tasks_have_max_retries_1(self):
        assert dispatch_approval_timeout_check.max_retries == 1
        assert dispatch_approval_reminder.max_retries == 1
        assert dispatch_daily_overage.max_retries == 1
        assert dispatch_drift_detection.max_retries == 1
        assert dispatch_metric_aggregation.max_retries == 1
        assert dispatch_training_mistake_check.max_retries == 1

    def test_all_names_contain_expected_substrings(self):
        assert "approval_timeout" in dispatch_approval_timeout_check.name
        assert "reminder" in dispatch_approval_reminder.name
        assert "daily_overage" in dispatch_daily_overage.name
        assert "drift_detection" in dispatch_drift_detection.name
        assert "metric_aggregation" in dispatch_metric_aggregation.name
        assert "training_mistake_check" in dispatch_training_mistake_check.name
