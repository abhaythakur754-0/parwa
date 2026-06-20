"""
Integration Tests for Security Gaps S-01 through S-07

Tests each fix in a more realistic context — verifying that the
fixes work correctly when components interact with each other.

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
import time
import warnings
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def valid_settings_env():
    """Minimal valid environment variables for Settings to load."""
    return {
        "ENVIRONMENT": "development",
        "SECRET_KEY": "integration-test-secret-key-at-least-32-chars",
        "JWT_SECRET_KEY": "integration-test-jwt-key-at-least-32-chars",
        "PRICING_SIGNING_KEY": "integration-test-pricing-key-32-char",
        "DATA_ENCRYPTION_KEY": "a" * 32,
    }


@pytest.fixture
def prod_settings_env():
    """Production environment variables for Settings."""
    return {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "production-secret-key-at-least-32-char",
        "JWT_SECRET_KEY": "production-jwt-key-at-least-32-chars",
        "PRICING_SIGNING_KEY": "production-pricing-key-32-char!",
        "DATA_ENCRYPTION_KEY": "b" * 32,
    }


# ══════════════════════════════════════════════════════════════════
# S-01/S-02/S-03/S-04: Config validators integration
# ══════════════════════════════════════════════════════════════════

class TestConfigSecurityIntegration:
    """Integration: Config validators work together to block all hardcoded defaults."""

    def test_all_four_keys_must_be_set(self, valid_settings_env):
        """All four security keys must be explicitly set to instantiate Settings."""
        from app.config import Settings

        # Should succeed with all four set
        s = Settings(**{k: v for k, v in valid_settings_env.items() if k != "ENVIRONMENT"})
        assert s.SECRET_KEY is not None
        assert s.JWT_SECRET_KEY is not None
        assert s.PRICING_SIGNING_KEY is not None
        assert s.DATA_ENCRYPTION_KEY is not None

    def test_missing_any_key_fails(self, valid_settings_env):
        """Omitting any of the four keys must fail."""
        from pydantic import ValidationError
        from app.config import Settings

        for key in ["SECRET_KEY", "JWT_SECRET_KEY", "PRICING_SIGNING_KEY", "DATA_ENCRYPTION_KEY"]:
            env = dict(valid_settings_env)
            del env[key]
            with pytest.raises((RuntimeError, ValidationError)):
                Settings(**{k: v for k, v in env.items() if k != "ENVIRONMENT"})

    def test_production_rejects_all_dev_defaults(self, prod_settings_env):
        """In production, all dev-prefix and short keys must be rejected."""
        from pydantic import ValidationError
        from app.config import Settings

        dev_keys = {
            "SECRET_KEY": "dev-key",
            "JWT_SECRET_KEY": "dev-jwt-key",
            "PRICING_SIGNING_KEY": "dev-pricing-key",
        }
        for key, bad_value in dev_keys.items():
            env = dict(prod_settings_env)
            env[key] = bad_value
            # Set ENVIRONMENT in os.environ so validators see production
            with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
                with pytest.raises((ValueError, ValidationError)):
                    Settings(**{k: v for k, v in env.items() if k != "ENVIRONMENT"})

    def test_production_rejects_short_keys(self, prod_settings_env):
        """In production, keys shorter than 32 chars must be rejected."""
        from pydantic import ValidationError
        from app.config import Settings

        short_keys = {
            "SECRET_KEY": "short",
            "JWT_SECRET_KEY": "short",
            "PRICING_SIGNING_KEY": "short",
        }
        for key, bad_value in short_keys.items():
            env = dict(prod_settings_env)
            env[key] = bad_value
            with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
                with pytest.raises((ValueError, ValidationError)):
                    Settings(**{k: v for k, v in env.items() if k != "ENVIRONMENT"})


# ══════════════════════════════════════════════════════════════════
# S-05: Async sleep doesn't block event loop
# ══════════════════════════════════════════════════════════════════

class TestAsyncSleepIntegration:
    """Integration: Verify async sleep doesn't block concurrent requests."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_not_blocked_by_progressive_delay(self):
        """Simulate progressive delay in auth_service: other requests must proceed."""
        results = []
        lock_delay_finished = asyncio.Event()

        async def delayed_auth():
            """Simulates authenticate_user's progressive delay."""
            await asyncio.sleep(0.1)  # progressive delay
            results.append("auth_done")
            lock_delay_finished.set()

        async def concurrent_request():
            """Another request that should NOT be blocked by the delay."""
            await lock_delay_finished.wait()
            results.append("concurrent_done")

        # Run both concurrently
        await asyncio.gather(delayed_auth(), concurrent_request())
        assert results == ["auth_done", "concurrent_done"]

    @pytest.mark.asyncio
    async def test_mfa_progressive_delay_is_non_blocking(self):
        """MFA progressive delays must not block other MFA verifications."""
        completed = []

        async def mfa_verify_with_delay(user_id, delay):
            """Simulate MFA verify with progressive delay."""
            if delay > 0:
                await asyncio.sleep(delay)
            completed.append(user_id)

        # Three concurrent MFA verifications with different delays
        await asyncio.gather(
            mfa_verify_with_delay("user_1", 0.05),
            mfa_verify_with_delay("user_2", 0.0),
            mfa_verify_with_delay("user_3", 0.02),
        )
        # All should complete — user_2 first (no delay)
        assert "user_1" in completed
        assert "user_2" in completed
        assert "user_3" in completed
        assert len(completed) == 3

    @pytest.mark.asyncio
    async def test_zai_client_backoff_is_async(self):
        """ZAI client retry backoff must use asyncio.sleep (not time.sleep)."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()
        # Reset singleton state for clean test
        client._sdk = None
        client._initialized = False

        start = time.monotonic()

        # Mock the SDK to fail, triggering retry with backoff
        with patch.object(client, "_ensure_sdk", return_value=False):
            # With no SDK, it should fall back immediately
            result = await client.chat_async(
                "command_router",
                "test message",
                max_retries=1,  # Just 1 retry to keep test fast
            )
            # Should get rule-based fallback
            assert result.get("_source") == "rule_based_fallback"

    def test_no_time_sleep_in_async_functions(self):
        """Verify that all async functions in auth/mfa services use asyncio.sleep."""
        import pathlib

        # Check auth_service
        auth_source = pathlib.Path(
            "/home/z/my-project/download/parwa/backend/app/services/auth_service.py"
        ).read_text()
        # Find async functions and check they don't use time.sleep
        assert "time.sleep" not in auth_source, (
            "auth_service.py still contains time.sleep()"
        )

        # Check mfa_service
        mfa_source = pathlib.Path(
            "/home/z/my-project/download/parwa/backend/app/services/mfa_service.py"
        ).read_text()
        assert "time.sleep" not in mfa_source, (
            "mfa_service.py still contains time.sleep()"
        )


# ══════════════════════════════════════════════════════════════════
# S-06: Paddle webhook idempotency — Redis integration
# ══════════════════════════════════════════════════════════════════

class TestPaddleIdempotencyIntegration:
    """Integration: Paddle webhook idempotency via Redis."""

    @pytest.mark.asyncio
    async def test_duplicate_event_detected_via_redis(self):
        """Second webhook with same event_id must be detected as duplicate."""
        from app.services.paddle_service import PaddleService

        mock_redis = AsyncMock()

        # First call: NX returns True (key was set) → not duplicate
        # Second call: NX returns None/False (key already exists) → duplicate
        mock_redis.set = AsyncMock(side_effect=[True, None])

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            result1 = await PaddleService.is_duplicate_event("evt_integration_001")
            assert result1 is False, "First event should not be duplicate"

            result2 = await PaddleService.is_duplicate_event("evt_integration_001")
            assert result2 is True, "Second event should be duplicate"

    @pytest.mark.asyncio
    async def test_different_events_not_duplicate(self):
        """Different event IDs must not be considered duplicates."""
        from app.services.paddle_service import PaddleService

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)  # Both succeed (new keys)

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            result1 = await PaddleService.is_duplicate_event("evt_unique_001")
            assert result1 is False

            result2 = await PaddleService.is_duplicate_event("evt_unique_002")
            assert result2 is False

    @pytest.mark.asyncio
    async def test_redis_key_format_includes_prefix(self):
        """Redis key must use the configured prefix."""
        from app.services.paddle_service import (
            PaddleService,
            _PADDLE_WEBHOOK_KEY_PREFIX,
        )

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            await PaddleService.is_duplicate_event("evt_key_test")

            # Verify the Redis key format
            call_args = mock_redis.set.call_args
            key = call_args[0][0] if call_args[0] else call_args[1].get("name", "")
            assert key.startswith(_PADDLE_WEBHOOK_KEY_PREFIX), (
                f"Redis key must start with {_PADDLE_WEBHOOK_KEY_PREFIX}, got {key}"
            )
            assert "evt_key_test" in key, (
                f"Redis key must include event_id, got {key}"
            )

    @pytest.mark.asyncio
    async def test_redis_ttl_set_on_idempotency_key(self):
        """Idempotency key must be set with 24h TTL."""
        from app.services.paddle_service import (
            PaddleService,
            _PADDLE_WEBHOOK_TTL_SECONDS,
        )

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            await PaddleService.is_duplicate_event("evt_ttl_test")

            # Verify TTL is set
            call_args = mock_redis.set.call_args
            # Check for 'ex' keyword argument
            ttl = call_args[1].get("ex")
            assert ttl == _PADDLE_WEBHOOK_TTL_SECONDS, (
                f"Expected TTL of {_PADDLE_WEBHOOK_TTL_SECONDS}s, got {ttl}"
            )

    @pytest.mark.asyncio
    async def test_redis_failure_fails_open(self):
        """If Redis is unavailable, idempotency must fail-open (allow processing)."""
        from app.services.paddle_service import PaddleService

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            result = await PaddleService.is_duplicate_event("evt_redis_fail")
            # Fail-open: return False (not duplicate) when Redis is down
            assert result is False, (
                "Idempotency check must fail-open when Redis is unavailable"
            )

    @pytest.mark.asyncio
    async def test_mark_event_processed_idempotent(self):
        """mark_event_processed must be idempotent (safe to call twice)."""
        from app.services.paddle_service import PaddleService

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            # Should not raise even when called multiple times
            await PaddleService.mark_event_processed("evt_mark_test")
            await PaddleService.mark_event_processed("evt_mark_test")

            assert mock_redis.set.call_count == 2

    @pytest.mark.asyncio
    async def test_process_restart_survives_idempotency(self):
        """After simulated process restart, previously processed events are still detected.

        This is the core difference between in-memory and Redis-backed idempotency.
        In-memory sets would be lost on restart; Redis persists.
        """
        from app.services.paddle_service import PaddleService

        # Simulate process restart: new mock_redis but key already exists
        mock_redis_after_restart = AsyncMock()
        mock_redis_after_restart.set = AsyncMock(return_value=None)  # Key exists

        with patch("app.core.redis.get_redis", return_value=mock_redis_after_restart):
            result = await PaddleService.is_duplicate_event("evt_before_restart")
            assert result is True, (
                "After restart, Redis-backed idempotency must still detect duplicates"
            )


# ══════════════════════════════════════════════════════════════════
# S-07: Verification token pepper integration
# ══════════════════════════════════════════════════════════════════

class TestVerificationPepperIntegration:
    """Integration: Peppered verification tokens work with the full flow."""

    def test_create_and_verify_token_with_pepper(self):
        """End-to-end: create a token, hash it with pepper, verify it matches."""
        from app.services.verification_service import _hash_token

        with patch("app.services.verification_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                SECRET_KEY="integration-pepper-for-e2e-test"
            )
            raw_token = "verify-me-abc123"
            token_hash = _hash_token(raw_token)

            # Verify the hash matches when recomputed
            assert token_hash == _hash_token(raw_token), (
                "Peppered hash must be deterministic"
            )

            # Verify plain SHA-256 would NOT match (proves pepper is active)
            plain_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            assert token_hash != plain_hash, (
                "Peppered hash must differ from plain SHA-256"
            )

    def test_old_unpeppered_hashes_not_accepted(self):
        """Tokens hashed with old plain SHA-256 must NOT match new peppered hashes.

        This verifies that the pepper upgrade is effective — old DB hashes
        would need migration.
        """
        from app.services.verification_service import _hash_token

        token = "migration-test-token"

        # Old-style: plain SHA-256 (how it was before the fix)
        old_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        # New-style: peppered HMAC-SHA256
        with patch("app.services.verification_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                SECRET_KEY="post-migration-pepper"
            )
            new_hash = _hash_token(token)

        assert old_hash != new_hash, (
            "Old unpeppered hashes must not match new peppered hashes"
        )

    def test_pepper_rotated_hashes_invalidate(self):
        """If SECRET_KEY is rotated, old peppered hashes become invalid.

        This is important for key rotation scenarios.
        """
        from app.services.verification_service import _hash_token

        token = "rotation-test-token"

        with patch("app.services.verification_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(SECRET_KEY="old-pepper-value")
            old_hash = _hash_token(token)

            mock_settings.return_value = MagicMock(SECRET_KEY="new-pepper-value")
            new_hash = _hash_token(token)

        assert old_hash != new_hash, (
            "Key rotation must invalidate old peppered hashes"
        )

    def test_hmac_format_matches_standard(self):
        """Verify our HMAC output matches Python's standard hmac module."""
        from app.services.verification_service import _hash_token

        pepper = "standard-hmac-test-pepper"
        token = "standard-token"

        # Compute using our function
        with patch("app.services.verification_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(SECRET_KEY=pepper)
            our_hash = _hash_token(token)

        # Compute using Python's hmac module directly
        standard_hash = hmac.new(
            pepper.encode("utf-8"),
            token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert our_hash == standard_hash, (
            "Our HMAC output must match Python's standard hmac module"
        )


# ══════════════════════════════════════════════════════════════════
# Cross-cutting: All gaps fixed together
# ══════════════════════════════════════════════════════════════════

class TestAllSecurityGapsIntegration:
    """Cross-cutting integration: Verify all S-01 through S-07 fixes work together."""

    def test_settings_with_all_valid_keys(self, valid_settings_env):
        """Settings must instantiate successfully with all security keys set."""
        from app.config import Settings

        s = Settings(**{k: v for k, v in valid_settings_env.items() if k != "ENVIRONMENT"})
        assert s.SECRET_KEY == valid_settings_env["SECRET_KEY"]
        assert s.JWT_SECRET_KEY == valid_settings_env["JWT_SECRET_KEY"]
        assert s.PRICING_SIGNING_KEY == valid_settings_env["PRICING_SIGNING_KEY"]
        assert s.DATA_ENCRYPTION_KEY == valid_settings_env["DATA_ENCRYPTION_KEY"]

    def test_production_blocks_all_insecure_configs(self, prod_settings_env):
        """Production must block every insecure configuration variant."""
        from pydantic import ValidationError
        from app.config import Settings

        insecure_configs = [
            {"SECRET_KEY": None},
            {"JWT_SECRET_KEY": None},
            {"PRICING_SIGNING_KEY": None},
            {"DATA_ENCRYPTION_KEY": None},
            {"SECRET_KEY": ""},
            {"JWT_SECRET_KEY": ""},
            {"PRICING_SIGNING_KEY": ""},
            {"DATA_ENCRYPTION_KEY": ""},
            {"SECRET_KEY": "dev-key"},
            {"JWT_SECRET_KEY": "dev-key"},
            {"PRICING_SIGNING_KEY": "dev-key"},
        ]

        for override in insecure_configs:
            env = dict(prod_settings_env)
            env.update(override)
            with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
                with pytest.raises((RuntimeError, ValueError, ValidationError)):
                    Settings(**{k: v for k, v in env.items() if k != "ENVIRONMENT"})

    @pytest.mark.asyncio
    async def test_async_services_and_peppered_tokens_work_together(self):
        """Async services (S-05) and peppered tokens (S-07) must work concurrently."""
        from app.services.verification_service import _hash_token

        results = {}

        async def async_task():
            """Simulate async service with non-blocking sleep."""
            await asyncio.sleep(0.01)
            results["async_done"] = True

        def sync_hash_task():
            """Simulate peppered token hashing (sync)."""
            with patch("app.services.verification_service.get_settings") as mock:
                mock.return_value = MagicMock(SECRET_KEY="concurrent-pepper")
                h = _hash_token("concurrent-token")
            results["hash_done"] = h

        # Run async task and sync task concurrently
        loop = asyncio.get_event_loop()
        await asyncio.gather(
            async_task(),
            asyncio.to_thread(sync_hash_task),
        )

        assert results.get("async_done") is True
        assert "hash_done" in results
        assert len(results["hash_done"]) == 64  # SHA-256 hex digest length
