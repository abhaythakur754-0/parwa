"""
conftest.py for ai_engine tests.

Pre-imports app.logger so that unittest.mock.patch("app.logger.get_logger", ...)
can resolve the dotted name correctly before any source module imports it.
"""

# Ensure app.logger is importable before any test file tries to patch it.
# Without this, patch("app.logger.get_logger") fails with:
#   AttributeError: module 'app' has no attribute 'logger'
import app.logger  # noqa: F401
