"""
PARWA Provider Failover.

Manages failover between LLM providers when rate limits
or errors occur.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from enum import Enum

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ProviderStatus(str, Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class FailoverManager:
    """
    Provider Failover Manager.

    Features:
    - Track provider health
    - Automatic failover on errors
    - Rate limit handling
    - Recovery detection
    """

    ERROR_THRESHOLD = 5
    RECOVERY_INTERVAL = 300  # 5 minutes

    def __init__(self) -> None:
        """Initialize Failover Manager."""
        self._provider_status: Dict[str, ProviderStatus] = {}
        self._error_counts: Dict[str, int] = {}
        self._last_error_time: Dict[str, datetime] = {}
        self._primary_provider = settings.llm_primary_provider
        self._fallback_provider = settings.llm_fallback_provider

    def get_provider(self) -> str:
        """
        Get the best available provider.

        Returns:
            Provider name to use
        """
        # Check primary
        if self._is_available(self._primary_provider):
            return self._primary_provider

        # Fall back to secondary
        if self._fallback_provider and self._is_available(self._fallback_provider):
            logger.warning({
                "event": "provider_failover",
                "primary": self._primary_provider,
                "fallback": self._fallback_provider,
            })
            return self._fallback_provider

        # All providers potentially down - return primary anyway
        logger.error({
            "event": "all_providers_degraded",
            "returning": self._primary_provider,
        })
        return self._primary_provider

    def _is_available(self, provider: str) -> bool:
        """Check if provider is available."""
        status = self._provider_status.get(provider, ProviderStatus.HEALTHY)

        if status == ProviderStatus.UNHEALTHY:
            # Check if recovery time has passed
            last_error = self._last_error_time.get(provider)
            if last_error:
                elapsed = (datetime.now(timezone.utc) - last_error).total_seconds()
                if elapsed > self.RECOVERY_INTERVAL:
                    # Reset to degraded for retry
                    self._provider_status[provider] = ProviderStatus.DEGRADED
                    return True
            return False

        return True

    def record_success(self, provider: str) -> None:
        """
        Record successful request.

        Args:
            provider: Provider name
        """
        self._error_counts[provider] = 0
        self._provider_status[provider] = ProviderStatus.HEALTHY

        logger.debug({
            "event": "provider_success",
            "provider": provider,
        })

    def record_error(self, provider: str, error_type: str = "unknown") -> None:
        """
        Record provider error.

        Args:
            provider: Provider name
            error_type: Type of error
        """
        count = self._error_counts.get(provider, 0) + 1
        self._error_counts[provider] = count
        self._last_error_time[provider] = datetime.now(timezone.utc)

        if count >= self.ERROR_THRESHOLD:
            self._provider_status[provider] = ProviderStatus.UNHEALTHY
        else:
            self._provider_status[provider] = ProviderStatus.DEGRADED

        logger.warning({
            "event": "provider_error",
            "provider": provider,
            "error_type": error_type,
            "error_count": count,
            "status": self._provider_status[provider].value,
        })

    def record_rate_limit(self, provider: str) -> None:
        """
        Record rate limit hit.

        Args:
            provider: Provider name
        """
        self.record_error(provider, "rate_limit")

    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all providers.

        Returns:
            Dict with provider statuses
        """
        return {
            "primary": {
                "name": self._primary_provider,
                "status": self._provider_status.get(
                    self._primary_provider, ProviderStatus.HEALTHY
                ).value,
                "error_count": self._error_counts.get(self._primary_provider, 0),
            },
            "fallback": {
                "name": self._fallback_provider,
                "status": self._provider_status.get(
                    self._fallback_provider, ProviderStatus.HEALTHY
                ).value,
                "error_count": self._error_counts.get(self._fallback_provider, 0),
            } if self._fallback_provider else None,
        }

    def reset_provider(self, provider: str) -> None:
        """
        Reset provider status to healthy.

        Args:
            provider: Provider name to reset
        """
        self._provider_status[provider] = ProviderStatus.HEALTHY
        self._error_counts[provider] = 0
        if provider in self._last_error_time:
            del self._last_error_time[provider]

        logger.info({
            "event": "provider_reset",
            "provider": provider,
        })
