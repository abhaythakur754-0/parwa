"""
Tests for PARWA Celery Application (BC-004)

Tests verify Celery app configuration without requiring a running
Celery worker or Redis broker.
"""


class TestCeleryAppCreated:
    """Test that the Celery app is created with correct configuration."""

    def test_celery_app_created(self):
        """Celery app exists and has correct name 'parwa'."""
        from backend.app.tasks.celery_app import app
        assert app.main is not None
        assert app.main == "parwa"


class TestQueuesDefined:
    """Test that all 7 queues are configured."""

    def test_queues_defined(self):
        """All 8 queues are configured in the Celery app (7 + DLQ)."""
        from backend.app.tasks.celery_app import (
            QUEUE_NAMES,
            app,
        )
        # Verify QUEUE_NAMES has all 8 expected queues (Day 16: added dead_letter)
        expected_queues = [
            "default",
            "ai_heavy",
            "ai_light",
            "email",
            "webhook",
            "analytics",
            "training",
            "dead_letter",  # Day 16: DLQ
        ]
        assert len(QUEUE_NAMES) == 8
        assert set(QUEUE_NAMES) == set(expected_queues)

        # Verify queues are configured in the app
        configured_queues = app.conf.task_queues
        for q in expected_queues:
            assert q in configured_queues

    def test_default_queue(self):
        """Default queue is 'default'."""
        from backend.app.tasks.celery_app import app
        assert app.conf.task_default_queue == "default"


class TestTaskSerializer:
    """Test serialization configuration."""

    def test_task_serializer(self):
        """Task serializer is JSON."""
        from backend.app.tasks.celery_app import app
        assert app.conf.task_serializer == "json"

    def test_result_serializer(self):
        """Result serializer is JSON."""
        from backend.app.tasks.celery_app import app
        assert app.conf.result_serializer == "json"

    def test_accept_content(self):
        """Only JSON content is accepted."""
        from backend.app.tasks.celery_app import app
        assert app.conf.accept_content == ["json"]


class TestTimezoneUTC:
    """Test timezone configuration."""

    def test_timezone_utc(self):
        """Timezone is UTC."""
        from backend.app.tasks.celery_app import app
        assert app.conf.timezone == "UTC"

    def test_enable_utc(self):
        """UTC is enabled."""
        from backend.app.tasks.celery_app import app
        assert app.conf.enable_utc is True


class TestTaskRouting:
    """Test task routing configuration."""

    def test_email_routes(self):
        """Email tasks route to 'email' queue."""
        from backend.app.tasks.celery_app import app
        routes = app.conf.task_routes
        # Routes use 'app.tasks.*' prefix (Celery runs inside backend/)
        assert "app.tasks.email.*" in routes
        assert routes["app.tasks.email.*"]["queue"] == "email"

    def test_webhook_routes(self):
        """Webhook tasks route to 'webhook' queue."""
        from backend.app.tasks.celery_app import app
        routes = app.conf.task_routes
        assert "app.tasks.webhook.*" in routes
        assert routes["app.tasks.webhook.*"]["queue"] == "webhook"

    def test_analytics_routes(self):
        """Analytics tasks route to 'analytics' queue."""
        from backend.app.tasks.celery_app import app
        routes = app.conf.task_routes
        assert "app.tasks.analytics.*" in routes
        assert routes["app.tasks.analytics.*"]["queue"] == "analytics"

    def test_ai_heavy_routes(self):
        """Heavy AI tasks route to 'ai_heavy' queue."""
        from backend.app.tasks.celery_app import app
        routes = app.conf.task_routes
        assert "app.tasks.ai.heavy.*" in routes
        assert routes["app.tasks.ai.heavy.*"]["queue"] == "ai_heavy"

    def test_ai_light_routes(self):
        """Light AI tasks route to 'ai_light' queue."""
        from backend.app.tasks.celery_app import app
        routes = app.conf.task_routes
        assert "app.tasks.ai.light.*" in routes
        assert routes["app.tasks.ai.light.*"]["queue"] == "ai_light"

    def test_training_routes(self):
        """Training tasks route to 'training' queue."""
        from backend.app.tasks.celery_app import app
        routes = app.conf.task_routes
        assert "app.tasks.training.*" in routes
        assert routes["app.tasks.training.*"]["queue"] == "training"


class TestAutodiscover:
    """Test autodiscover is configured."""

    def test_autodiscover_tasks(self):
        """Autodiscover is configured for app.tasks."""
        from backend.app.tasks.celery_app import app
        # Celery stores autodiscover in _autodiscover_tasks_from
        # or in the imports list
        assert "app.tasks.example_tasks" in app.conf.imports
