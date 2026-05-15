"""
Unit Tests for Security Gaps S-01 through S-07

Tests each fix in isolation using mocks for external dependencies.

Gaps covered:
  S-01: Hardcoded DATA_ENCRYPTION_KEY fallback
  S-02: Hardcoded SECRET_KEY fallback
  S-03: Hardcoded JWT_SECRET_KEY fallback
  S-04: Hardcoded PRICING_SIGNING_KEY fallback
  S-05: time.sleep() blocking event loop
  S-06: Paddle webhook idempotency (Redis-backed)
  S-07: Verification tokens unpeppered (HMAC-SHA256)
"""

import asyncio
import hashlib
import hmac
import os
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════
# S-01: DATA_ENCRYPTION_KEY — no hardcoded fallback
# ══════════════════════════════════════════════════════════════════

class TestS01DataEncryptionKey:
    """S-01: DATA_ENCRYPTION_KEY must NOT fall back to a hardcoded dev key."""

    def test_none_raises_runtime_error(self):
        """DATA_ENCRYPTION_KEY=None must raise RuntimeError."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((RuntimeError, ValidationError)):
                Settings(DATA_ENCRYPTION_KEY=None, SECRET_KEY="test-secret-key-for-unit-test", JWT_SECRET_KEY="test-jwt-secret-key-for-unit-test", PRICING_SIGNING_KEY="test-pricing-signing-key-for-unit-test")

    def test_empty_string_raises_runtime_error(self):
        """DATA_ENCRYPTION_KEY='' must raise RuntimeError."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((RuntimeError, ValidationError)):
                Settings(DATA_ENCRYPTION_KEY="", SECRET_KEY="test-secret-key-for-unit-test", JWT_SECRET_KEY="test-jwt-secret-key-for-unit-test", PRICING_SIGNING_KEY="test-pricing-signing-key-for-unit-test")

    def test_valid_key_accepted(self):
        """A valid 32-char key should be accepted."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            from app.config import Settings

            s = Settings(
                DATA_ENCRYPTION_KEY="a" * 32,
                SECRET_KEY="test-secret-key-for-unit-test",
                JWT_SECRET_KEY="test-jwt-secret-key-for-unit-test",
                PRICING_SIGNING_KEY="test-pricing-signing-key-for-unit-test",
            )
            assert s.DATA_ENCRYPTION_KEY == "a" * 32

    def test_production_wrong_length_raises(self):
        """In production, wrong-length key must raise ValueError."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((ValueError, ValidationError)):
                Settings(
                    DATA_ENCRYPTION_KEY="short",
                    SECRET_KEY="a" * 32,
                    JWT_SECRET_KEY="a" * 32,
                    PRICING_SIGNING_KEY="a" * 32,
                )


# ══════════════════════════════════════════════════════════════════
# S-02: SECRET_KEY — no hardcoded fallback
# ══════════════════════════════════════════════════════════════════

class TestS02SecretKey:
    """S-02: SECRET_KEY must NOT fall back to a hardcoded dev key."""

    def test_none_raises_runtime_error(self):
        """SECRET_KEY=None must raise RuntimeError."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((RuntimeError, ValidationError)):
                Settings(
                    SECRET_KEY=None,
                    JWT_SECRET_KEY="test-jwt-secret-key-for-unit-test",
                    PRICING_SIGNING_KEY="test-pricing-signing-key-for-unit-test",
                    DATA_ENCRYPTION_KEY="a" * 32,
                )

    def test_empty_string_raises_runtime_error(self):
        """SECRET_KEY='' must raise RuntimeError (gap fix: previously only warned)."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((RuntimeError, ValidationError)):
                Settings(
                    SECRET_KEY="",
                    JWT_SECRET_KEY="test-jwt-secret-key-for-unit-test",
                    PRICING_SIGNING_KEY="test-pricing-signing-key-for-unit-test",
                    DATA_ENCRYPTION_KEY="a" * 32,
                )

    def test_dev_prefix_warns_in_dev(self):
        """SECRET_KEY starting with 'dev-' should warn in development."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            from app.config import Settings

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                s = Settings(
                    SECRET_KEY="dev-something",
                    JWT_SECRET_KEY="test-jwt-secret-key-for-unit-test",
                    PRICING_SIGNING_KEY="test-pricing-signing-key-for-unit-test",
                    DATA_ENCRYPTION_KEY="a" * 32,
                )
                assert s.SECRET_KEY == "dev-something"
                assert any("development SECRET_KEY" in str(warning.message) for warning in w)

    def test_dev_prefix_raises_in_production(self):
        """SECRET_KEY starting with 'dev-' must raise in production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((ValueError, ValidationError)):
                Settings(
                    SECRET_KEY="dev-something",
                    JWT_SECRET_KEY="a" * 32,
                    PRICING_SIGNING_KEY="a" * 32,
                    DATA_ENCRYPTION_KEY="a" * 32,
                )

    def test_production_too_short_raises(self):
        """SECRET_KEY shorter than 32 chars must raise in production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((ValueError, ValidationError)):
                Settings(
                    SECRET_KEY="too-short-key",
                    JWT_SECRET_KEY="a" * 32,
                    PRICING_SIGNING_KEY="a" * 32,
                    DATA_ENCRYPTION_KEY="a" * 32,
                )


# ══════════════════════════════════════════════════════════════════
# S-03: JWT_SECRET_KEY — no hardcoded fallback
# ══════════════════════════════════════════════════════════════════

class TestS03JwtSecretKey:
    """S-03: JWT_SECRET_KEY must NOT fall back to a hardcoded dev key."""

    def test_none_raises_runtime_error(self):
        """JWT_SECRET_KEY=None must raise RuntimeError."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((RuntimeError, ValidationError)):
                Settings(
                    JWT_SECRET_KEY=None,
                    SECRET_KEY="test-secret-key-for-unit-test",
                    PRICING_SIGNING_KEY="test-pricing-signing-key-for-unit-test",
                    DATA_ENCRYPTION_KEY="a" * 32,
                )

    def test_empty_string_raises_runtime_error(self):
        """JWT_SECRET_KEY='' must raise RuntimeError."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((RuntimeError, ValidationError)):
                Settings(
                    JWT_SECRET_KEY="",
                    SECRET_KEY="test-secret-key-for-unit-test",
                    PRICING_SIGNING_KEY="test-pricing-signing-key-for-unit-test",
                    DATA_ENCRYPTION_KEY="a" * 32,
                )

    def test_dev_prefix_warns_in_dev(self):
        """JWT_SECRET_KEY starting with 'dev-' should warn in development."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            from app.config import Settings

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                s = Settings(
                    JWT_SECRET_KEY="dev-jwt-key",
                    SECRET_KEY="test-secret-key-for-unit-test",
                    PRICING_SIGNING_KEY="test-pricing-signing-key-for-unit-test",
                    DATA_ENCRYPTION_KEY="a" * 32,
                )
                assert s.JWT_SECRET_KEY == "dev-jwt-key"
                assert any("development JWT_SECRET_KEY" in str(warning.message) for warning in w)

    def test_production_too_short_raises(self):
        """JWT_SECRET_KEY shorter than 32 chars must raise in production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((ValueError, ValidationError)):
                Settings(
                    JWT_SECRET_KEY="too-short-key",
                    SECRET_KEY="a" * 32,
                    PRICING_SIGNING_KEY="a" * 32,
                    DATA_ENCRYPTION_KEY="a" * 32,
                )


# ══════════════════════════════════════════════════════════════════
# S-04: PRICING_SIGNING_KEY — no hardcoded fallback
# ══════════════════════════════════════════════════════════════════

class TestS04PricingSigningKey:
    """S-04: PRICING_SIGNING_KEY must NOT fall back to a hardcoded dev key."""

    def test_none_raises_runtime_error(self):
        """PRICING_SIGNING_KEY=None must raise RuntimeError."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((RuntimeError, ValidationError)):
                Settings(
                    PRICING_SIGNING_KEY=None,
                    SECRET_KEY="test-secret-key-for-unit-test",
                    JWT_SECRET_KEY="test-jwt-secret-key-for-unit-test",
                    DATA_ENCRYPTION_KEY="a" * 32,
                )

    def test_empty_string_raises_runtime_error(self):
        """PRICING_SIGNING_KEY='' must raise RuntimeError (gap fix: previously only warned)."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((RuntimeError, ValidationError)):
                Settings(
                    PRICING_SIGNING_KEY="",
                    SECRET_KEY="test-secret-key-for-unit-test",
                    JWT_SECRET_KEY="test-jwt-secret-key-for-unit-test",
                    DATA_ENCRYPTION_KEY="a" * 32,
                )

    def test_dev_prefix_warns_in_dev(self):
        """PRICING_SIGNING_KEY starting with 'dev-' should warn in dev."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            from app.config import Settings

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                s = Settings(
                    PRICING_SIGNING_KEY="dev-pricing-key",
                    SECRET_KEY="test-secret-key-for-unit-test",
                    JWT_SECRET_KEY="test-jwt-secret-key-for-unit-test",
                    DATA_ENCRYPTION_KEY="a" * 32,
                )
                assert s.PRICING_SIGNING_KEY == "dev-pricing-key"
                assert any("development PRICING_SIGNING_KEY" in str(warning.message) for warning in w)

    def test_dev_prefix_raises_in_production(self):
        """PRICING_SIGNING_KEY starting with 'dev-' must raise in production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((ValueError, ValidationError)):
                Settings(
                    PRICING_SIGNING_KEY="dev-pricing-key",
                    SECRET_KEY="a" * 32,
                    JWT_SECRET_KEY="a" * 32,
                    DATA_ENCRYPTION_KEY="a" * 32,
                )

    def test_production_too_short_raises(self):
        """PRICING_SIGNING_KEY shorter than 32 chars must raise in production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            from pydantic import ValidationError
            from app.config import Settings

            with pytest.raises((ValueError, ValidationError)):
                Settings(
                    PRICING_SIGNING_KEY="too-short-key",
                    SECRET_KEY="a" * 32,
                    JWT_SECRET_KEY="a" * 32,
                    DATA_ENCRYPTION_KEY="a" * 32,
                )


# ══════════════════════════════════════════════════════════════════
# S-05: time.sleep() does NOT block event loop
# ══════════════════════════════════════════════════════════════════

class TestS05NoBlockingSleep:
    """S-05: Verify asyncio.sleep is used in async contexts, not time.sleep."""

    def test_auth_service_no_time_sleep(self):
        """auth_service.py must not call time.sleep() anywhere."""
        import pathlib
        source = pathlib.Path(
            "/home/z/my-project/download/parwa/backend/app/services/auth_service.py"
        ).read_text()
        # time.sleep should NOT appear in auth_service (we removed the import)
        assert "time.sleep" not in source, (
            "auth_service.py still contains time.sleep() — "
            "blocking call in async context"
        )

    def test_mfa_service_no_time_sleep(self):
        """mfa_service.py must not call time.sleep() anywhere."""
        import pathlib
        source = pathlib.Path(
            "/home/z/my-project/download/parwa/backend/app/services/mfa_service.py"
        ).read_text()
        assert "time.sleep" not in source, (
            "mfa_service.py still contains time.sleep() — "
            "blocking call in async context"
        )

    def test_zai_client_uses_async_sleep(self):
        """zai_client.py must use asyncio.sleep in chat_async, not time.sleep."""
        import pathlib
        source = pathlib.Path(
            "/home/z/my-project/download/parwa/backend/app/services/jarvis_agents/zai_client.py"
        ).read_text()
        # Find the chat_async method section
        chat_async_start = source.find("async def chat_async")
        assert chat_async_start != -1, "Could not find chat_async method"
        # Get the method body (rough)
        next_method = source.find("\n    def ", chat_async_start + 1)
        if next_method == -1:
            next_method = len(source)
        chat_async_source = source[chat_async_start:next_method]
        assert "asyncio.sleep" in chat_async_source, (
            "ZAIClient.chat_async must use asyncio.sleep, not time.sleep"
        )
        assert "time.sleep" not in chat_async_source, (
            "ZAIClient.chat_async should not use time.sleep"
        )

    def test_auth_service_progressive_delay_is_async(self):
        """authenticate_user must use await asyncio.sleep for progressive delay."""
        import pathlib
        source = pathlib.Path(
            "/home/z/my-project/download/parwa/backend/app/services/auth_service.py"
        ).read_text()
        # Find authenticate_user method
        method_start = source.find("async def authenticate_user")
        assert method_start != -1, "Could not find authenticate_user"
        next_method = source.find("\ndef ", method_start + 1)
        if next_method == -1:
            next_method = len(source)
        method_source = source[method_start:next_method]
        assert "await asyncio.sleep" in method_source, (
            "authenticate_user must use 'await asyncio.sleep' for progressive delay"
        )

    def test_mfa_service_progressive_delay_is_async(self):
        """verify_mfa_login must use await asyncio.sleep for progressive delay."""
        import pathlib
        source = pathlib.Path(
            "/home/z/my-project/download/parwa/backend/app/services/mfa_service.py"
        ).read_text()
        # Find verify_mfa_login method
        method_start = source.find("async def verify_mfa_login")
        assert method_start != -1, "Could not find verify_mfa_login"
        next_method = source.find("\ndef ", method_start + 1)
        if next_method == -1:
            next_method = len(source)
        method_source = source[method_start:next_method]
        assert "await asyncio.sleep" in method_source, (
            "verify_mfa_login must use 'await asyncio.sleep' for progressive delay"
        )

    def test_async_sleep_does_not_block_event_loop(self):
        """Verify asyncio.sleep yields control (does not block the event loop)."""
        results = []

        async def task_a():
            await asyncio.sleep(0.05)
            results.append("a")

        async def task_b():
            results.append("b")

        async def main():
            # Both tasks should interleave — asyncio.sleep yields
            t1 = asyncio.create_task(task_a())
            t2 = asyncio.create_task(task_b())
            await t1
            await t2

        asyncio.run(main())
        # task_b should complete first (no sleep), then task_a
        assert results == ["b", "a"], (
            f"Expected ['b', 'a'], got {results} — event loop may be blocked"
        )


# ══════════════════════════════════════════════════════════════════
# S-06: Paddle webhook idempotency — Redis-backed
# ══════════════════════════════════════════════════════════════════

class TestS06PaddleIdempotency:
    """S-06: Paddle webhook idempotency must be Redis-backed (not in-memory)."""

    def test_no_in_memory_set_for_idempotency(self):
        """paddle_service.py must NOT use a Python set for idempotency tracking."""
        import inspect
        from app.services import paddle_service

        source = inspect.getsource(paddle_service)
        # Should not have a module-level set for tracking
        assert "_processed_events" not in source, (
            "paddle_service still uses in-memory _processed_events set"
        )
        assert "_seen_events" not in source, (
            "paddle_service still uses in-memory _seen_events set"
        )

    def test_is_duplicate_event_uses_redis(self):
        """is_duplicate_event must use Redis SET with NX+EX, not in-memory."""
        import inspect
        from app.services.paddle_service import PaddleService

        source = inspect.getsource(PaddleService.is_duplicate_event)
        assert "redis" in source.lower(), (
            "is_duplicate_event must use Redis for idempotency"
        )
        assert "nx=True" in source, (
            "is_duplicate_event must use Redis NX (set-if-not-exists)"
        )
        assert "ex=" in source, (
            "is_duplicate_event must set TTL with EX parameter"
        )

    def test_is_duplicate_event_is_async(self):
        """is_duplicate_event must be async (Redis calls are async)."""
        from app.services.paddle_service import PaddleService

        assert asyncio.iscoroutinefunction(
            PaddleService.is_duplicate_event
        ), "is_duplicate_event must be an async method"

    @pytest.mark.asyncio
    async def test_is_duplicate_event_redis_flow(self):
        """Simulate Redis-backed idempotency: first call = new, second = duplicate."""
        from app.services.paddle_service import PaddleService

        mock_redis = AsyncMock()
        # First call: NX returns True (key set) → not duplicate
        # Second call: NX returns None (key exists) → duplicate
        mock_redis.set = AsyncMock(side_effect=[True, None])

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            result1 = await PaddleService.is_duplicate_event("evt_001")
            assert result1 is False

            result2 = await PaddleService.is_duplicate_event("evt_001")
            assert result2 is True

    @pytest.mark.asyncio
    async def test_is_duplicate_event_empty_id_returns_false(self):
        """Empty event_id should return False (not a duplicate)."""
        from app.services.paddle_service import PaddleService

        result = await PaddleService.is_duplicate_event("")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_duplicate_event_redis_failure_fail_open(self):
        """If Redis is unavailable, fail-open (return False = not duplicate)."""
        from app.services.paddle_service import PaddleService

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            result = await PaddleService.is_duplicate_event("evt_redis_down")
            assert result is False

    def test_ttl_is_24_hours(self):
        """Idempotency TTL must be 24 hours (Paddle's retry window)."""
        from app.services.paddle_service import _PADDLE_WEBHOOK_TTL_SECONDS

        assert _PADDLE_WEBHOOK_TTL_SECONDS == 86400, (
            f"Expected 86400s (24h) TTL, got {_PADDLE_WEBHOOK_TTL_SECONDS}"
        )


# ══════════════════════════════════════════════════════════════════
# S-07: Verification tokens peppered with SECRET_KEY
# ══════════════════════════════════════════════════════════════════

class TestS07VerificationTokenPepper:
    """S-07: Verification token hashing must use HMAC-SHA256 with pepper."""

    def test_hash_token_uses_hmac(self):
        """_hash_token must use HMAC-SHA256, not plain SHA-256."""
        import inspect
        from app.services.verification_service import _hash_token

        source = inspect.getsource(_hash_token)
        assert "hmac" in source, (
            "_hash_token must use HMAC for peppered hashing"
        )
        # Should NOT be plain sha256
        assert "hashlib.sha256(\n" not in source, (
            "_hash_token should not use plain SHA-256 without pepper"
        )

    def test_hash_token_includes_pepper(self):
        """_hash_token must include SECRET_KEY as a pepper."""
        import inspect
        from app.services.verification_service import _hash_token

        source = inspect.getsource(_hash_token)
        assert "SECRET_KEY" in source, (
            "_hash_token must reference SECRET_KEY as the pepper"
        )
        assert "pepper" in source.lower(), (
            "_hash_token should document the pepper usage"
        )

    def test_same_token_different_peppers_different_hash(self):
        """Same token with different peppers must produce different hashes."""
        with patch("app.services.verification_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(SECRET_KEY="pepper-1")
            from app.services.verification_service import _hash_token
            hash1 = _hash_token("test-token-abc")

            mock_settings.return_value = MagicMock(SECRET_KEY="pepper-2")
            # Need to re-import to pick up new settings
            hash2 = _hash_token("test-token-abc")

        assert hash1 != hash2, (
            "Same token with different peppers must produce different hashes"
        )

    def test_different_tokens_same_pepper_different_hash(self):
        """Different tokens with same pepper must produce different hashes."""
        with patch("app.services.verification_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(SECRET_KEY="same-pepper-for-test")
            from app.services.verification_service import _hash_token
            hash1 = _hash_token("token-alpha")
            hash2 = _hash_token("token-beta")

        assert hash1 != hash2, (
            "Different tokens must produce different hashes"
        )

    def test_hash_is_deterministic(self):
        """Same token + same pepper must always produce the same hash."""
        with patch("app.services.verification_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(SECRET_KEY="deterministic-pepper")
            from app.services.verification_service import _hash_token
            hash1 = _hash_token("deterministic-token")
            hash2 = _hash_token("deterministic-token")

        assert hash1 == hash2, "Same input must always produce same hash"

    def test_hash_not_match_plain_sha256(self):
        """Peppered hash must NOT match plain SHA-256 (proves pepper is active)."""
        token = "test-token-xyz"
        plain_sha256 = hashlib.sha256(token.encode("utf-8")).hexdigest()

        with patch("app.services.verification_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(SECRET_KEY="my-pepper-value")
            from app.services.verification_service import _hash_token
            peppered_hash = _hash_token(token)

        assert peppered_hash != plain_sha256, (
            "Peppered hash must differ from plain SHA-256 — pepper is not active"
        )

    def test_hash_length_is_64_chars(self):
        """HMAC-SHA256 output must be 64 hex characters."""
        with patch("app.services.verification_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(SECRET_KEY="length-test-pepper")
            from app.services.verification_service import _hash_token
            result = _hash_token("some-token")

        assert len(result) == 64, f"Expected 64-char hex digest, got {len(result)}"
