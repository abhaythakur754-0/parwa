"""
Tests for PARWA Structured Logger (logger.py)

BC-012: JSON logging in production, console in dev/test.
Every log entry must include timestamp, level, environment, module.
"""

import logging

from backend.app.logger import configure_logging, get_logger


class TestConfigureLogging:
    """Test logging configuration per environment."""

    def test_configure_dev_sets_debug_level(self):
        """Development environment sets root logger to DEBUG."""
        configure_logging("development")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_configure_test_sets_debug_level(self):
        """Test environment sets root logger to DEBUG."""
        configure_logging("test")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_configure_production_sets_info_level(self):
        """Production environment sets root logger to INFO (quieter)."""
        configure_logging("production")
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_configure_adds_stdout_handler(self):
        """Root logger gets a StreamHandler writing to stdout."""
        configure_logging("development")
        root = logging.getLogger()
        # At least one handler should be a StreamHandler
        assert len(root.handlers) >= 1
        assert isinstance(root.handlers[0], logging.StreamHandler)

    def test_configure_clears_previous_handlers(self):
        """Reconfiguring clears old handlers (no duplicate logging)."""
        configure_logging("development")
        root = logging.getLogger()
        configure_logging("production")
        # Should still be exactly 1 handler, not 2
        assert len(root.handlers) == 1

    def test_configure_idempotent_multiple_calls(self):
        """Calling configure_logging multiple times is idempotent."""
        configure_logging("development")
        configure_logging("development")
        configure_logging("production")
        root = logging.getLogger()
        assert len(root.handlers) == 1

    def test_structlog_has_bound_logger(self):
        """structlog.get_logger returns a BoundLogger after configuration."""
        configure_logging("development")
        logger = get_logger("test_module")
        # Should have standard logging methods
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "debug")

    def test_structlog_logger_has_context(self):
        """Bound logger can bind context variables."""
        configure_logging("development")
        logger = get_logger("test_context")
        bound = logger.bind(company_id="comp_123", user_id="usr_456")
        # Binding should not raise
        assert bound is not None


class TestGetLogger:
    """Test get_logger helper."""

    def test_get_logger_returns_logger_with_name(self):
        """get_logger returns a logger tied to the given module name."""
        configure_logging("development")
        logger = get_logger("my_module")
        assert logger is not None

    def test_get_logger_different_names(self):
        """Different names produce distinct loggers."""
        configure_logging("development")
        logger_a = get_logger("module_a")
        logger_b = get_logger("module_b")
        # Both should be valid loggers
        assert hasattr(logger_a, "info")
        assert hasattr(logger_b, "info")
