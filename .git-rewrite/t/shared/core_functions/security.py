"""
PARWA Security Module
Provides JWT authentication, password hashing, and input sanitization.
Depends on: config.py (Week 1 Day 2), logger.py (Week 1 Day 3)
"""

import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)

# --- Password Hashing ---

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with a random salt.

    Args:
        password: The plaintext password to hash.

    Returns:
        A string in the format 'salt:hash'.

    Raises:
        ValueError: If password is empty or too short.
    """
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    logger.info({"event": "password_hashed", "context": {}})
    return f"{salt}:{hashed}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a stored hash.

    Args:
        password: The plaintext password to verify.
        hashed: The stored hash in 'salt:hash' format.

    Returns:
        True if the password matches, False otherwise.
    """
    if not password or not hashed:
        return False

    try:
        salt, stored_hash = hashed.split(":")
        computed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return hmac.compare_digest(computed, stored_hash)
    except (ValueError, AttributeError):
        return False


# --- JWT Token Management ---


def create_access_token(
    data: Dict[str, Any],
    secret_key: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token.

    Args:
        data: The payload data to encode in the token.
        secret_key: The secret key for signing.
        expires_delta: Optional expiration time delta.

    Returns:
        A signed JWT token string.

    Raises:
        ValueError: If secret_key is empty.
    """
    if not secret_key:
        raise ValueError("JWT secret key must not be empty")

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=1))
    to_encode.update({"exp": expire.timestamp(), "iat": datetime.now(timezone.utc).timestamp()})

    token = jwt.encode(to_encode, secret_key, algorithm="HS256")
    logger.info({"event": "access_token_created", "context": {"user_id": data.get("sub")}})
    return token


def decode_access_token(token: str, secret_key: str) -> Dict[str, Any]:
    """Decode and verify a JWT access token.

    Args:
        token: The JWT token string.
        secret_key: The secret key for verification.

    Returns:
        The decoded token payload.

    Raises:
        ValueError: If the token is invalid or expired.
    """
    if not token or not secret_key:
        raise ValueError("Token and secret key must not be empty")

    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return payload
    except Exception as e:
        logger.error("Token decode failed", extra={"context": {"error": str(e)}})
        
        # Manually raise specific errors to match test expectations
        if "ExpiredSignatureError" in str(type(e)):
            raise ValueError("Token has expired") from e
        
        raise ValueError(f"Invalid token: {e}") from e


# --- Input Sanitization ---


def sanitize_input(user_input: str, max_length: int = 10000) -> str:
    """Sanitize user input to prevent injection attacks.

    Args:
        user_input: The raw user input string.
        max_length: Maximum allowed length.

    Returns:
        A sanitized string safe for processing.

    Raises:
        ValueError: If input exceeds max_length.
    """
    if not isinstance(user_input, str):
        raise ValueError("Input must be a string")

    if len(user_input) > max_length:
        raise ValueError(f"Input exceeds maximum length of {max_length}")

    # Strip script tags and their contents
    cleaned = re.sub(r"<script[^>]*>.*?</script>", "", user_input, flags=re.IGNORECASE | re.DOTALL)
    
    # Strip remaining HTML tags
    cleaned = re.sub(r"<[^>]*>", "", cleaned)

    # Remove null bytes
    cleaned = cleaned.replace("\x00", "")

    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()

    return cleaned


def validate_email(email: str) -> bool:
    """Validate email format.

    Args:
        email: The email address to validate.

    Returns:
        True if the email is valid, False otherwise.
    """
    if not email or not isinstance(email, str):
        return False

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))
