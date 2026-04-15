"""Tests for Day 22 email tasks."""

import uuid

from tests.unit.test_day22_setup import setup_day22_tests  # noqa: E402
setup_day22_tests()
from backend.app.tasks.email_tasks import (  # noqa: E402
    send_email,
    render_template,
    send_bulk_notification,
)


class TestSendEmail:
    def test_returns_dict_on_success(self):
        result = send_email("company-123", "user@example.com", "Subject", "<p>Body</p>")
        assert isinstance(result, dict)

    def test_return_has_status_sent(self):
        result = send_email("company-123", "user@example.com", "Subject", "<p>Body</p>")
        assert result["status"] == "sent"

    def test_return_has_message_id(self):
        result = send_email("company-123", "user@example.com", "Subject", "<p>Body</p>")
        assert "message_id" in result

    def test_return_has_to_field(self):
        result = send_email("company-123", "user@example.com", "Subject", "<p>Body</p>")
        assert result["to"] == "user@example.com"

    def test_message_id_is_valid_uuid(self):
        result = send_email("company-123", "user@example.com", "Subject", "<p>Body</p>")
        assert isinstance(uuid.UUID(result["message_id"]), uuid.UUID)

    def test_custom_message_id_preserved(self):
        custom_id = str(uuid.uuid4())
        result = send_email("company-123", "user@example.com", "Subject", "<p>Body</p>", message_id=custom_id)
        assert result["message_id"] == custom_id

    def test_queue_is_email(self):
        assert send_email.queue == "email"

    def test_max_retries_is_3(self):
        assert send_email.max_retries == 3

    def test_soft_time_limit(self):
        assert send_email.soft_time_limit == 30

    def test_time_limit(self):
        assert send_email.time_limit == 60

    def test_task_name_registered(self):
        assert "email.send_email" in send_email.name

    def test_optional_params(self):
        result = send_email("c1", "a@b.com", "S", "B", from_email="x@y.com", reply_to="z@w.com")
        assert result["status"] == "sent"


class TestRenderTemplate:
    def test_returns_dict_on_success(self):
        result = render_template("company-123", "welcome_email", {"name": "Alice"})
        assert isinstance(result, dict)

    def test_return_has_status_rendered(self):
        result = render_template("company-123", "welcome_email", {"name": "Alice"})
        assert result["status"] == "rendered"

    def test_return_has_template_name(self):
        result = render_template("company-123", "welcome_email", {"name": "Alice"})
        assert result["template_name"] == "welcome_email"

    def test_return_has_rendered_length(self):
        result = render_template("company-123", "welcome_email", {"name": "Alice"})
        assert "rendered_length" in result
        assert result["rendered_length"] > 0

    def test_queue_is_email(self):
        assert render_template.queue == "email"

    def test_max_retries_is_2(self):
        assert render_template.max_retries == 2

    def test_soft_time_limit(self):
        assert render_template.soft_time_limit == 15

    def test_time_limit(self):
        assert render_template.time_limit == 30

    def test_task_name_registered(self):
        assert "email.render_template" in render_template.name

    def test_empty_context(self):
        result = render_template("c1", "tpl", {})
        assert result["status"] == "rendered"


class TestSendBulkNotification:
    def test_returns_dict_on_success(self):
        result = send_bulk_notification("company-123", ["a@b.com"], "Subject", "<p>Body</p>")
        assert isinstance(result, dict)

    def test_return_has_status_completed(self):
        result = send_bulk_notification("company-123", ["a@b.com"], "Subject", "<p>Body</p>")
        assert result["status"] == "completed"

    def test_return_has_batch_id(self):
        result = send_bulk_notification("company-123", ["a@b.com"], "Subject", "<p>Body</p>")
        assert "batch_id" in result

    def test_batch_id_is_valid_uuid(self):
        result = send_bulk_notification("company-123", ["a@b.com"], "Subject", "<p>Body</p>")
        assert isinstance(uuid.UUID(result["batch_id"]), uuid.UUID)

    def test_total_matches_recipients(self):
        result = send_bulk_notification("company-123", ["a@b.com", "c@d.com"], "Subject", "<p>Body</p>")
        assert result["total"] == 2
        assert result["sent"] == 2

    def test_queue_is_email(self):
        assert send_bulk_notification.queue == "email"

    def test_max_retries_is_3(self):
        assert send_bulk_notification.max_retries == 3

    def test_soft_time_limit(self):
        assert send_bulk_notification.soft_time_limit == 120

    def test_time_limit(self):
        assert send_bulk_notification.time_limit == 300

    def test_task_name_registered(self):
        assert "email.send_bulk_notification" in send_bulk_notification.name

    def test_custom_batch_id_preserved(self):
        custom = str(uuid.uuid4())
        result = send_bulk_notification("c1", ["a@b.com"], "S", "B", batch_id=custom)
        assert result["batch_id"] == custom

    def test_empty_recipients(self):
        result = send_bulk_notification("c1", [], "S", "B")
        assert result["total"] == 0
        assert result["sent"] == 0

    def test_failed_count_is_zero(self):
        result = send_bulk_notification("c1", ["a@b.com"], "S", "B")
        assert result["failed"] == 0
