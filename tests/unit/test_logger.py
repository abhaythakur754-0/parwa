import json
import logging
import pytest
from io import StringIO

from shared.core_functions.logger import get_logger, redact_sensitive_data, REDACTION_TEXT

class LogCaptureHandler(logging.StreamHandler):
    """Custom handler to capture logs in memory for testing."""
    def __init__(self):
        self.stream = StringIO()
        super().__init__(self.stream)

    def get_logs(self):
        return self.stream.getvalue()

@pytest.fixture
def logger_with_capture():
    # Use a unique name to avoid conflicts across tests
    logger = get_logger("test_logger_unique")
    
    # Remove existing handlers (e.g. stdout) and add capture handler just for test
    logger.handlers.clear()
    capture_handler = LogCaptureHandler()
    
    from shared.core_functions.logger import JSONFormatter
    capture_handler.setFormatter(JSONFormatter())
    logger.addHandler(capture_handler)
    
    return logger, capture_handler

def test_json_formatting(logger_with_capture):
    logger, capture_handler = logger_with_capture
    
    logger.info("Test message", extra={"user_id": "user-123", "context": {"action": "login"}})
    
    log_output = capture_handler.get_logs().strip()
    log_dict = json.loads(log_output)
    
    assert log_dict["level"] == "INFO"
    assert "test_logger" in log_dict["module"]  # file test_logger.py -> test_logger
    assert log_dict["message"] == "Test message"
    assert log_dict["user_id"] == "user-123"
    assert log_dict["context"] == {"action": "login"}
    assert "timestamp" in log_dict

def test_sensitive_data_redaction():
    sensitive_context = {
        "event": "payment",
        "user_data": {
            "name": "John Doe",
            "credit_card": "1234-5678-9012-3456",
            "api_key": "sk_test_12345"
        },
        "password_hash": "hashed_value_here"
    }
    
    redacted = redact_sensitive_data(sensitive_context)
    
    assert redacted["event"] == "payment"
    assert redacted["user_data"]["name"] == "John Doe"
    assert redacted["user_data"]["credit_card"] == REDACTION_TEXT
    assert redacted["user_data"]["api_key"] == REDACTION_TEXT
    assert redacted["password_hash"] == REDACTION_TEXT

def test_logger_sensitive_data_redaction(logger_with_capture):
    logger, capture_handler = logger_with_capture
    
    logger.error("Payment failed", extra={"context": {"api_key": "secret123", "amount": 50}})
    
    log_dict = json.loads(capture_handler.get_logs().strip())
    assert log_dict["context"]["api_key"] == REDACTION_TEXT
    assert log_dict["context"]["amount"] == 50

def test_exception_logging(logger_with_capture):
    logger, capture_handler = logger_with_capture
    
    try:
        1 / 0
    except ZeroDivisionError:
        logger.error("An error occurred", exc_info=True)
        
    log_dict = json.loads(capture_handler.get_logs().strip())
    
    assert log_dict["level"] == "ERROR"
    assert log_dict["message"] == "An error occurred"
    assert "exception" in log_dict["context"]
    assert "ZeroDivisionError" in log_dict["context"]["exception"]
