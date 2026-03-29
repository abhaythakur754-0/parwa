"""Webhook Validator - URL and Payload Validation"""
from typing import Dict, Optional, Any, List
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    valid: bool
    errors: List[str]

class WebhookValidator:
    ALLOWED_SCHEMES = ['https']
    BLOCKED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', 'internal', 'private']
    MAX_URL_LENGTH = 2048
    MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB

    def validate_url(self, url: str) -> ValidationResult:
        errors = []

        if not url:
            errors.append("URL is required")
            return ValidationResult(False, errors)

        if len(url) > self.MAX_URL_LENGTH:
            errors.append(f"URL exceeds maximum length of {self.MAX_URL_LENGTH}")

        url_pattern = r'^(https?)://([^/:]+)(:\d+)?(/.*)?$'
        match = re.match(url_pattern, url)

        if not match:
            errors.append("Invalid URL format")
            return ValidationResult(False, errors)

        scheme, host, port, path = match.groups()

        if scheme.lower() not in self.ALLOWED_SCHEMES:
            errors.append(f"URL scheme must be one of: {self.ALLOWED_SCHEMES}")

        for blocked in self.BLOCKED_HOSTS:
            if blocked in host.lower():
                errors.append(f"URL contains blocked host: {blocked}")

        private_ip_pattern = r'^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)'
        if re.match(private_ip_pattern, host):
            errors.append("URL points to private IP address")

        return ValidationResult(len(errors) == 0, errors)

    def validate_payload(self, payload: Any) -> ValidationResult:
        errors = []

        if payload is None:
            errors.append("Payload cannot be None")
            return ValidationResult(False, errors)

        try:
            payload_str = str(payload)
            if len(payload_str) > self.MAX_PAYLOAD_SIZE:
                errors.append(f"Payload exceeds maximum size of {self.MAX_PAYLOAD_SIZE} bytes")
        except Exception as e:
            errors.append(f"Invalid payload: {e}")

        return ValidationResult(len(errors) == 0, errors)

    def validate_events(self, events: List[str], allowed_events: List[str]) -> ValidationResult:
        errors = []

        if not events:
            errors.append("At least one event must be specified")
            return ValidationResult(False, errors)

        for event in events:
            if event not in allowed_events and event != "*":
                errors.append(f"Invalid event type: {event}")

        return ValidationResult(len(errors) == 0, errors)

    def validate_headers(self, headers: Dict[str, str]) -> ValidationResult:
        errors = []

        for key, value in headers.items():
            if not re.match(r'^[A-Za-z0-9-]+$', key):
                errors.append(f"Invalid header name: {key}")
            if len(str(value)) > 4096:
                errors.append(f"Header value too long for: {key}")

        return ValidationResult(len(errors) == 0, errors)

    def validate_webhook_config(self, url: str, events: List[str], headers: Dict[str, str], allowed_events: List[str]) -> ValidationResult:
        all_errors = []

        url_result = self.validate_url(url)
        all_errors.extend(url_result.errors)

        events_result = self.validate_events(events, allowed_events)
        all_errors.extend(events_result.errors)

        headers_result = self.validate_headers(headers)
        all_errors.extend(headers_result.errors)

        return ValidationResult(len(all_errors) == 0, all_errors)
