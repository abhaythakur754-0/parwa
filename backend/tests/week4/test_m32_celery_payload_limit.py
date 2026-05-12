"""
Week 4 — M-32: Celery task payload must be limited to 1MB.

Tests that the before_task_publish signal enforces the MAX_TASK_PAYLOAD_BYTES
limit and rejects oversized payloads.
"""
import json
import pytest
from unittest.mock import patch, MagicMock


class TestM32CeleryPayloadLimit:
    """Tests for M-32 Celery payload size enforcement."""

    def test_max_payload_constant_defined(self):
        """MAX_TASK_PAYLOAD_BYTES must be 1MB."""
        from app.tasks.celery_app import MAX_TASK_PAYLOAD_BYTES
        assert MAX_TASK_PAYLOAD_BYTES == 1 * 1024 * 1024

    def test_signal_handler_exists(self):
        """_enforce_max_payload_size function must exist."""
        from app.tasks import celery_app
        assert hasattr(celery_app, '_enforce_max_payload_size'), (
            "_enforce_max_payload_size function not found in celery_app module"
        )

    def test_small_payload_allowed(self):
        """Payloads under 1MB should be allowed (return None)."""
        from app.tasks.celery_app import _enforce_max_payload_size
        small_body = {"data": "x" * 100}  # 100 bytes
        result = _enforce_max_payload_size(
            sender="test_task",
            headers={},
            body=small_body,
        )
        # None return means "allow dispatch"
        assert result is None

    def test_large_payload_rejected(self):
        """Payloads over 1MB should return False (reject dispatch)."""
        from app.tasks.celery_app import MAX_TASK_PAYLOAD_BYTES, _enforce_max_payload_size
        # Create a payload slightly over 1MB
        large_body = {"data": "x" * (MAX_TASK_PAYLOAD_BYTES + 100)}
        result = _enforce_max_payload_size(
            sender="test_task",
            headers={},
            body=large_body,
        )
        assert result is False, (
            "Oversized payload should be rejected (return False)"
        )

    def test_none_body_allowed(self):
        """None body should be allowed (task may have no args)."""
        from app.tasks.celery_app import _enforce_max_payload_size
        result = _enforce_max_payload_size(
            sender="test_task",
            headers={},
            body=None,
        )
        assert result is None

    def test_empty_body_allowed(self):
        """Empty body should be allowed."""
        from app.tasks.celery_app import _enforce_max_payload_size
        result = _enforce_max_payload_size(
            sender="test_task",
            headers={},
            body={},
        )
        assert result is None

    def test_string_body_measured_correctly(self):
        """String bodies should be measured by length."""
        from app.tasks.celery_app import MAX_TASK_PAYLOAD_BYTES, _enforce_max_payload_size
        # String body just over 1MB
        large_string = "x" * (MAX_TASK_PAYLOAD_BYTES + 100)
        result = _enforce_max_payload_size(
            sender="test_task",
            headers={},
            body=large_string,
        )
        assert result is False

    def test_bytes_body_measured_correctly(self):
        """Bytes bodies should be measured by length."""
        from app.tasks.celery_app import MAX_TASK_PAYLOAD_BYTES, _enforce_max_payload_size
        large_bytes = b"x" * (MAX_TASK_PAYLOAD_BYTES + 100)
        result = _enforce_max_payload_size(
            sender="test_task",
            headers={},
            body=large_bytes,
        )
        assert result is False

    def test_error_in_handler_does_not_crash(self):
        """Exceptions in the handler should be caught, not crash dispatch."""
        from app.tasks.celery_app import _enforce_max_payload_size
        # Pass a body that can't be serialized — should not raise
        result = _enforce_max_payload_size(
            sender="test_task",
            headers={},
            body=object(),  # Can't json.dumps this
        )
        # Should return None (allow) since the check failed gracefully
        assert result is None

    def test_worker_limits_configured(self):
        """Worker-level memory and task limits must be configured."""
        from app.tasks.celery_app import _build_config
        config = _build_config()
        assert config.get("worker_max_tasks_per_child") == 1000
        assert config.get("worker_max_memory_per_child") == 200_000

    def test_just_under_limit_allowed(self):
        """Payload exactly 1 byte under limit should be allowed."""
        from app.tasks.celery_app import MAX_TASK_PAYLOAD_BYTES, _enforce_max_payload_size
        # Use a dict that serializes to just under 1MB
        data_size = MAX_TASK_PAYLOAD_BYTES - 200  # Leave room for JSON overhead
        body = {"data": "x" * data_size}
        result = _enforce_max_payload_size(
            sender="test_task",
            headers={},
            body=body,
        )
        assert result is None
