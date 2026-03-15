"""
Unit tests for the GDPR/CCPA compliance module.
"""
import pytest
from shared.core_functions.compliance import (
    mask_pii, 
    generate_portability_report, 
    process_erasure_request
)


def test_mask_pii_basic_fields():
    """Test that explicit PII fields are redacted."""
    raw_data = {
        "user_id": "123",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "phone": "+1234567890",
        "credit_card": "4111222233334444",
        "ssn": "000-00-0000",
        "address": "123 Main St",
        "favorite_color": "blue"
    }
    
    masked = mask_pii(raw_data)
    
    assert masked["user_id"] == "123"
    assert masked["favorite_color"] == "blue"
    
    # Check redacted fields
    assert masked["first_name"] == "[REDACTED]"
    assert masked["last_name"] == "[REDACTED]"
    assert masked["email"] == "[REDACTED]"
    assert masked["phone"] == "[REDACTED]"
    assert masked["credit_card"] == "[REDACTED]"
    assert masked["ssn"] == "[REDACTED]"
    assert masked["address"] == "[REDACTED]"


def test_mask_pii_nested_dict():
    """Test that PII masking works recursively on nested dictionaries."""
    raw_data = {
        "user_id": "123",
        "profile": {
            "email": "test@test.com",
            "settings": {
                "theme": "dark",
                "phone": "555-5555"
            }
        }
    }
    
    masked = mask_pii(raw_data)
    
    assert masked["user_id"] == "123"
    assert masked["profile"]["settings"]["theme"] == "dark"
    assert masked["profile"]["email"] == "[REDACTED]"
    assert masked["profile"]["settings"]["phone"] == "[REDACTED]"


def test_mask_pii_invalid_input():
    """Test that masking rejects non-dictionary inputs."""
    with pytest.raises(TypeError):
        mask_pii("not a dict")


def test_generate_portability_report():
    """Test generating a GDPR portability report."""
    def mock_fetcher(uid):
        return {"orders": [1, 2], "name": "Jane"}
        
    report = generate_portability_report("user_456", mock_fetcher)
    
    assert report["user_id"] == "user_456"
    assert report["metadata"]["report_type"] == "GDPR_PORTABILITY"
    assert "orders" in report["data"]
    assert report["data"]["name"] == "Jane"


def test_process_erasure_request_success():
    """Test successful erasure request processing."""
    def mock_deleter(uid):
        return True
        
    result = process_erasure_request("user_789", mock_deleter)
    assert result is True


def test_process_erasure_request_failure():
    """Test failed erasure request handling."""
    def mock_deleter(uid):
        return False
        
    result = process_erasure_request("user_789", mock_deleter)
    assert result is False


def test_process_erasure_request_invalid_id():
    """Test erasure request validates user_id."""
    with pytest.raises(ValueError):
        process_erasure_request("", None)
        
    with pytest.raises(TypeError):
        process_erasure_request(123, None) # Must be a string
