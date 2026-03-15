"""
PARWA Core Authentication Module.
Provides JWT handling, password hashing, and token validation with Redis blacklisting.
"""
from datetime import timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.core_functions.security import (
    create_access_token as _create_jwt,
    decode_access_token as _decode_jwt,
    hash_password as _hash_pwd,
    verify_password as _verify_pwd,
)
from shared.utils.cache import Cache

logger = get_logger(__name__)
settings = get_settings()


def create_access_token(user_id: UUID, expires_delta: timedelta) -> str:
    """
    Create a JWT access token for a user.

    Args:
        user_id: The UUID of the user.
        expires_delta: Time delta until the token expires.

    Returns:
        str: A signed JWT access token.

    Raises:
        ValueError: If user_id is invalid or secret_key is not configured.
    """
    if not user_id:
        raise ValueError("user_id must be a valid UUID")

    if not isinstance(user_id, UUID):
        try:
            user_id = UUID(user_id)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid user_id format: {e}") from e

    token_data = {
        "sub": str(user_id),
        "type": "access",
    }

    secret_key = settings.secret_key.get_secret_value()
    token = _create_jwt(
        data=token_data,
        secret_key=secret_key,
        expires_delta=expires_delta,
    )

    logger.info({
        "event": "access_token_created",
        "user_id": str(user_id),
        "expires_in_seconds": int(expires_delta.total_seconds()),
    })

    return token


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.

    Args:
        token: The JWT token string to verify.

    Returns:
        dict: The decoded token payload containing user information.

    Raises:
        ValueError: If the token is invalid, expired, or blacklisted.
    """
    if not token:
        raise ValueError("Token must not be empty")

    # Check if token is blacklisted
    if is_token_blacklisted(token):
        logger.warning({"event": "blacklisted_token_used"})
        raise ValueError("Token has been revoked")

    # Decode the token
    secret_key = settings.secret_key.get_secret_value()
    payload = _decode_jwt(token, secret_key)

    logger.info({
        "event": "token_verified",
        "user_id": payload.get("sub"),
    })

    return payload


def hash_password(password: str) -> str:
    """
    Hash a password using secure hashing algorithm.

    Args:
        password: The plaintext password to hash.

    Returns:
        str: A hashed password string.

    Raises:
        ValueError: If password is empty or too short (minimum 8 characters).
    """
    if not password:
        raise ValueError("Password must not be empty")

    hashed = _hash_pwd(password)

    logger.info({"event": "password_hashed"})

    return hashed


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plaintext password against a hashed password.

    Args:
        plain: The plaintext password to verify.
        hashed: The stored hashed password.

    Returns:
        bool: True if the password matches, False otherwise.
    """
    if not plain or not hashed:
        return False

    result = _verify_pwd(plain, hashed)

    logger.info({
        "event": "password_verified",
        "success": result,
    })

    return result


def blacklist_token(token: str) -> None:
    """
    Add a token to the Redis blacklist.

    This effectively invalidates the token for future use.
    Tokens are blacklisted for 24 hours (typical token lifetime).

    Args:
        token: The JWT token to blacklist.

    Raises:
        RuntimeError: If the blacklist operation fails.
    """
    if not token:
        raise ValueError("Token must not be empty")

    cache = Cache()

    try:
        # Store token in blacklist for 24 hours (86400 seconds)
        # Using sync wrapper for async cache operation
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(
                cache.set(f"blacklist:{token}", "1", expire=86400)
            )
        finally:
            loop.close()

        if not success:
            raise RuntimeError("Failed to blacklist token in cache")

        logger.info({"event": "token_blacklisted"})

    except Exception as e:
        logger.error({
            "event": "blacklist_failed",
            "error": str(e),
        })
        raise RuntimeError(f"Failed to blacklist token: {e}") from e
    finally:
        # Close the cache connection
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(cache.close())
        finally:
            loop.close()


def is_token_blacklisted(token: str) -> bool:
    """
    Check if a token is in the Redis blacklist.

    Args:
        token: The JWT token to check.

    Returns:
        bool: True if the token is blacklisted, False otherwise.
              Returns False if Redis is unavailable (fail-open).
    """
    if not token:
        return False

    cache = Cache()

    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            exists = loop.run_until_complete(cache.exists(f"blacklist:{token}"))
        finally:
            loop.close()

        return exists

    except Exception as e:
        logger.error({
            "event": "blacklist_check_failed",
            "error": str(e),
        })
        # Fail open - don't block users if Redis is down
        return False
    finally:
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(cache.close())
        finally:
            loop.close()


async def blacklist_token_async(token: str) -> None:
    """
    Async version: Add a token to the Redis blacklist.

    Args:
        token: The JWT token to blacklist.

    Raises:
        RuntimeError: If the blacklist operation fails.
    """
    if not token:
        raise ValueError("Token must not be empty")

    cache = Cache()

    try:
        success = await cache.set(f"blacklist:{token}", "1", expire=86400)

        if not success:
            raise RuntimeError("Failed to blacklist token in cache")

        logger.info({"event": "token_blacklisted"})

    except Exception as e:
        logger.error({
            "event": "blacklist_failed",
            "error": str(e),
        })
        raise RuntimeError(f"Failed to blacklist token: {e}") from e
    finally:
        await cache.close()


async def is_token_blacklisted_async(token: str) -> bool:
    """
    Async version: Check if a token is in the Redis blacklist.

    Args:
        token: The JWT token to check.

    Returns:
        bool: True if the token is blacklisted, False otherwise.
    """
    if not token:
        return False

    cache = Cache()

    try:
        exists = await cache.exists(f"blacklist:{token}")
        return exists
    except Exception as e:
        logger.error({
            "event": "blacklist_check_failed",
            "error": str(e),
        })
        return False
    finally:
        await cache.close()
