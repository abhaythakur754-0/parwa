"""
PARWA Input Validators

Validates common input formats: email, phone (E.164), UUID.
All validators return boolean — they never raise exceptions.
Used throughout the API for input sanitization.
"""

import re


# Precompiled regex patterns for performance
_EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

# E.164 format: + followed by 7-15 digits
_PHONE_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")

# UUID v4 pattern (or any UUID version)
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def is_valid_email(email: str) -> bool:
    """Validate email format.

    Checks basic RFC 5322 compliance (simplified).
    Rejects empty strings, whitespace-only, and malformed addresses.
    Does NOT check deliverability — only format.

    Args:
        email: String to validate.

    Returns:
        True if email format is valid, False otherwise.
    """
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if len(email) > 254:  # RFC 5321 max length
        return False
    if " " in email or ".." in email:
        return False
    return bool(_EMAIL_PATTERN.match(email))


def is_valid_phone(phone: str) -> bool:
    """Validate phone number in E.164 international format.

    E.164 format: starts with '+', followed by 7-15 digits.
    Examples: '+14155552671', '+919876543210'.
    Rejects anything without country code or with invalid characters.

    Args:
        phone: String to validate.

    Returns:
        True if phone is valid E.164, False otherwise.
    """
    if not phone or not isinstance(phone, str):
        return False
    phone = phone.strip()
    return bool(_PHONE_PATTERN.match(phone))


def is_valid_uuid(value: str) -> bool:
    """Validate UUID format (any version).

    Accepts UUID v1, v3, v4, v5. Case-insensitive.
    Rejects malformed strings and non-string inputs.

    Args:
        value: String to validate.

    Returns:
        True if value is a valid UUID string, False otherwise.
    """
    if not value or not isinstance(value, str):
        return False
    return bool(_UUID_PATTERN.match(value.strip()))


def is_valid_url(url: str) -> bool:
    """Validate URL format (basic check).

    Checks for scheme (http/https) and non-empty host.
    Does NOT check reachability or certificate validity.

    Args:
        url: String to validate.

    Returns:
        True if URL format is valid, False otherwise.
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return False
    # Extract host part after scheme
    try:
        parts = url.split("://", 1)[1]
        if not parts or "/" not in parts and "." not in parts:
            return False
        host = parts.split("/")[0]
        if not host or "." not in host:
            return False
        return True
    except (IndexError, ValueError):
        return False


def sanitize_string(value: str, max_length: int = 500) -> str:
    """Sanitize a string for safe storage.

    Strips leading/trailing whitespace, collapses multiple spaces,
    and truncates to max_length.

    Args:
        value: String to sanitize.
        max_length: Maximum allowed length (default 500).

    Returns:
        Sanitized string.
    """
    if not isinstance(value, str):
        return ""
    # Strip null bytes first (prevent log injection / data corruption)
    value = value.replace('\x00', '')
    value = value.strip()
    # Collapse multiple whitespace into single space
    value = " ".join(value.split())
    if len(value) > max_length:
        value = value[:max_length]
    return value
