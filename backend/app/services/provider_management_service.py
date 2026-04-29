"""
LLM Provider Management Service.

Management layer for the 3 free LLM providers (Google AI Studio, Cerebras,
Groq). Wraps and extends SmartRouter's ProviderHealthTracker with persistent
status tracking, health check scheduling, usage analytics, API key rotation,
and alerting on provider degradation.

Integrates with:
- SmartRouter's ProviderHealthTracker (real-time health data)
- SmartRouter's MODEL_REGISTRY (model configuration)
- In-memory store for alerts, API keys, disabled models, usage stats
- Redis cache for cross-worker state sharing (optional, fail-open)

BC-001: company_id is second parameter on all public methods.
BC-008: Never crash — all public methods are wrapped in try/except.
BC-012: All timestamps UTC.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional

from app.exceptions import ParwaBaseError
from app.logger import get_logger

logger = get_logger("provider_management")


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class ProviderStatus(str, Enum):
    """Health status of a provider+model combination."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RATE_LIMITED = "rate_limited"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class AlertLevel(str, Enum):
    """Severity level for provider alerts."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# Provider display names for human-readable output.
_PROVIDER_DISPLAY_NAMES: Dict[str, str] = {
    "google": "Google AI Studio",
    "cerebras": "Cerebras",
    "groq": "Groq",
}

# Ordered list of providers for iteration.
_KNOWN_PROVIDERS: List[str] = ["google", "cerebras", "groq"]

# Status priority for computing worst-status across models.
# Higher index = worse status. Used to bubble up provider summary.
_STATUS_PRIORITY: Dict[str, int] = {
    ProviderStatus.HEALTHY.value: 0,
    ProviderStatus.UNKNOWN.value: 1,
    ProviderStatus.DEGRADED.value: 2,
    ProviderStatus.RATE_LIMITED.value: 3,
    ProviderStatus.UNHEALTHY.value: 4,
    ProviderStatus.DISABLED.value: 5,
}


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class ProviderModelStatus:
    """Health and usage snapshot for a single provider+model pair.

    Aggregates data from SmartRouter's ProviderHealthTracker with
    any manual overrides (disabled models, etc.).
    """
    provider: str  # google, cerebras, groq
    model_id: str
    display_name: str
    tier: str  # light, medium, heavy, guardrail
    status: str  # ProviderStatus value
    daily_requests: int
    daily_limit: int
    daily_remaining: int
    minute_tokens: int
    minute_limit: int
    consecutive_failures: int
    last_error: str
    is_rate_limited: bool
    rate_limit_expires_at: Optional[str]
    last_success_at: Optional[str]
    avg_latency_ms: float
    total_requests_today: int


@dataclass
class ProviderSummary:
    """Aggregated health summary for one provider across all its models."""
    provider: str
    display_name: str
    status: str  # worst status across its models
    total_models: int
    healthy_models: int
    degraded_models: int
    unhealthy_models: int
    total_requests_today: int
    models: List[ProviderModelStatus] = field(default_factory=list)


@dataclass
class ProviderAlert:
    """An alert generated for a provider health event."""
    id: str
    provider: str
    model_id: Optional[str]
    level: str  # AlertLevel value
    message: str
    created_at: str  # UTC ISO-8601
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None


@dataclass
class ProviderUsageStats:
    """Usage analytics for a provider over a date range."""
    provider: str
    date: str  # YYYY-MM-DD
    total_requests: int
    successful_requests: int
    failed_requests: int
    rate_limited_count: int
    avg_latency_ms: float
    total_tokens_used: int
    error_types: Dict[str, int] = field(default_factory=dict)


@dataclass
class APIKeyConfig:
    """Configuration for a provider API key."""
    provider: str
    key_id: str
    key_value: str  # full value stored here; masked in responses
    is_active: bool
    created_at: str  # UTC ISO-8601
    last_used_at: Optional[str]
    expires_at: Optional[str]
    request_count: int = 0


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════


def _utc_now() -> str:
    """Return current UTC time as ISO-8601 string (BC-012)."""
    return datetime.now(timezone.utc).isoformat()


def _utc_today() -> str:
    """Return today's date as YYYY-MM-DD UTC (BC-012)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _mask_api_key(key_value: str) -> str:
    """Mask API key for safe display — show first 8 chars + ****.

    If key is shorter than 8 chars, show first 4 chars + ****.
    If key is empty, return '****'.
    """
    if not key_value:
        return "****"
    visible = min(8, max(4, len(key_value) // 2))
    return key_value[:visible] + "****"


def _validate_company_id(company_id: str) -> None:
    """Validate company_id is non-empty (BC-001).

    Raises:
        ParwaBaseError: If company_id is empty or whitespace-only.
    """
    if not company_id or not str(company_id).strip():
        raise ParwaBaseError(
            error_code="INVALID_COMPANY_ID",
            message="company_id is required and cannot be empty (BC-001)",
            status_code=400,
        )


def _worst_status(statuses: List[str]) -> str:
    """Return the worst ProviderStatus from a list of status strings."""
    if not statuses:
        return ProviderStatus.UNKNOWN.value
    worst = statuses[0]
    for s in statuses[1:]:
        if _STATUS_PRIORITY.get(s, 0) > _STATUS_PRIORITY.get(worst, 0):
            worst = s
    return worst


# ══════════════════════════════════════════════════════════════════
# PROVIDER MANAGEMENT SERVICE
# ══════════════════════════════════════════════════════════════════


class ProviderManagementService:
    """Management layer for LLM provider health, usage, and configuration.

    Wraps SmartRouter's ProviderHealthTracker to provide:
    - Persistent provider status with manual disable/enable controls
    - Provider health check scheduling
    - Usage analytics per provider
    - API key management with rotation support
    - Alerting on provider degradation

    All state is stored in-memory. Company-scoped data is isolated
    in dictionaries keyed by company_id.

    BC-001: company_id is second parameter on all public methods.
    BC-008: Never crash — graceful degradation with safe defaults.
    """

    # Maximum alerts retained per company before pruning.
    _MAX_ALERTS_PER_COMPANY = 500

    def __init__(self, db=None) -> None:
        """Initialize the service.

        Args:
            db: Optional database session. Not used for core provider
                management (in-memory), available for future persistence.
        """
        self.db = db

        # Lazy-loaded references to SmartRouter components.
        self._smart_router = None
        self._model_registry = None
        self._health_tracker = None

        # ── In-memory stores (company_id → data) ──
        # Manually disabled models: {company_id: {(provider, model_id):
        # reason}}
        self._disabled_models: Dict[str, Dict[tuple, str]] = {}

        # Alerts: {company_id: [ProviderAlert, ...]}
        self._alerts: Dict[str, List[ProviderAlert]] = {}

        # API keys: {company_id: [APIKeyConfig, ...]}
        self._api_keys: Dict[str, List[APIKeyConfig]] = {}

        # Usage stats accumulator: {company_id: {provider: {date: stats}}}
        self._usage_stats: Dict[str, Dict[str, Dict[str, dict]]] = {}

        # Last success timestamps: {company_id: {(provider, model_id):
        # iso_str}}
        self._last_success: Dict[str, Dict[tuple, str]] = {}

        # Latency accumulator: {company_id: {(provider, model_id): [ms, ...]}}
        self._latency_samples: Dict[str, Dict[tuple, List[float]]] = {}

        logger.info("provider_management_service_initialized")

    # ── Lazy Import Helpers ──────────────────────────────────────

    def _get_health_tracker(self):
        """Lazy-load ProviderHealthTracker from SmartRouter."""
        if self._health_tracker is None:
            try:
                from app.core.smart_router import ProviderHealthTracker

                self._health_tracker = ProviderHealthTracker()
            except Exception as exc:
                logger.error(
                    "failed_to_load_health_tracker",
                    error=str(exc),
                )
                return None
        return self._health_tracker

    def _get_model_registry(self) -> dict:
        """Lazy-load MODEL_REGISTRY from SmartRouter."""
        if self._model_registry is None:
            try:
                from app.core.smart_router import MODEL_REGISTRY

                self._model_registry = MODEL_REGISTRY
            except Exception as exc:
                logger.error(
                    "failed_to_load_model_registry",
                    error=str(exc),
                )
                return {}
        return self._model_registry

    def _get_smart_router(self):
        """Lazy-load SmartRouter instance."""
        if self._smart_router is None:
            try:
                from app.core.smart_router import SmartRouter

                self._smart_router = SmartRouter()
            except Exception as exc:
                logger.error(
                    "failed_to_load_smart_router",
                    error=str(exc),
                )
                return None
        return self._smart_router

    # ════════════════════════════════════════════════════════════
    # PUBLIC API — STATUS & HEALTH
    # ════════════════════════════════════════════════════════════

    def get_all_providers_status(
        self, company_id: str,
    ) -> List[ProviderSummary]:
        """Return full status overview for all 3 providers.

        Aggregates health data from ProviderHealthTracker for each
        model in MODEL_REGISTRY, applying any manual disable overrides.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            List of ProviderSummary, one per provider, sorted by
            provider name.
        """
        try:
            _validate_company_id(company_id)
            summaries: List[ProviderSummary] = []

            for provider in _KNOWN_PROVIDERS:
                try:
                    summary = self._build_provider_summary(
                        company_id, provider,
                    )
                    summaries.append(summary)
                except Exception as exc:
                    logger.warning(
                        "failed_to_build_provider_summary",
                        extra={
                            "company_id": company_id,
                            "provider": provider,
                            "error": str(exc),
                        },
                    )
                    summaries.append(ProviderSummary(
                        provider=provider,
                        display_name=_PROVIDER_DISPLAY_NAMES.get(
                            provider, provider,
                        ),
                        status=ProviderStatus.UNKNOWN.value,
                        total_models=0,
                        healthy_models=0,
                        degraded_models=0,
                        unhealthy_models=0,
                        total_requests_today=0,
                    ))

            logger.info(
                "all_providers_status_retrieved",
                extra={
                    "company_id": company_id,
                    "provider_count": len(summaries),
                },
            )
            return summaries

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "get_all_providers_status_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
            # BC-008: Return safe defaults
            return [
                ProviderSummary(
                    provider=p,
                    display_name=_PROVIDER_DISPLAY_NAMES.get(p, p),
                    status=ProviderStatus.UNKNOWN.value,
                    total_models=0,
                    healthy_models=0,
                    degraded_models=0,
                    unhealthy_models=0,
                    total_requests_today=0,
                )
                for p in _KNOWN_PROVIDERS
            ]

    def get_provider_status(
        self, company_id: str, provider: str,
    ) -> ProviderSummary:
        """Return health summary for a single provider.

        Args:
            company_id: Tenant identifier (BC-001).
            provider: Provider name ('google', 'cerebras', 'groq').

        Returns:
            ProviderSummary for the requested provider. Returns UNKNOWN
            status if provider is not recognised (BC-008).
        """
        try:
            _validate_company_id(company_id)
            provider = provider.lower().strip()
            if provider not in _KNOWN_PROVIDERS:
                logger.warning(
                    "unknown_provider_requested",
                    extra={
                        "company_id": company_id,
                        "provider": provider,
                    },
                )
                return ProviderSummary(
                    provider=provider,
                    display_name=_PROVIDER_DISPLAY_NAMES.get(
                        provider,
                        provider),
                    status=ProviderStatus.UNKNOWN.value,
                    total_models=0,
                    healthy_models=0,
                    degraded_models=0,
                    unhealthy_models=0,
                    total_requests_today=0,
                )

            return self._build_provider_summary(company_id, provider)

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "get_provider_status_failed",
                extra={
                    "company_id": company_id,
                    "provider": provider,
                    "error": str(exc),
                },
            )
            return ProviderSummary(
                provider=provider,
                display_name=_PROVIDER_DISPLAY_NAMES.get(provider, provider),
                status=ProviderStatus.UNKNOWN.value,
                total_models=0,
                healthy_models=0,
                degraded_models=0,
                unhealthy_models=0,
                total_requests_today=0,
            )

    def get_model_status(
        self, company_id: str, provider: str, model_id: str,
    ) -> ProviderModelStatus:
        """Return status for a single provider+model combination.

        Args:
            company_id: Tenant identifier (BC-001).
            provider: Provider name ('google', 'cerebras', 'groq').
            model_id: Model identifier (e.g. 'llama-3.1-8b').

        Returns:
            ProviderModelStatus with current health snapshot.
        """
        try:
            _validate_company_id(company_id)
            provider = provider.lower().strip()

            registry = self._get_model_registry()
            tracker = self._get_health_tracker()

            # Find the matching model config(s) in registry.
            model_statuses = self._build_all_model_statuses(
                company_id, provider, registry, tracker,
            )
            for ms in model_statuses:
                if ms.model_id == model_id:
                    return ms

            # Model not found in registry — return unknown status.
            return ProviderModelStatus(
                provider=provider,
                model_id=model_id,
                display_name=model_id,
                tier="unknown",
                status=ProviderStatus.UNKNOWN.value,
                daily_requests=0,
                daily_limit=0,
                daily_remaining=0,
                minute_tokens=0,
                minute_limit=0,
                consecutive_failures=0,
                last_error="",
                is_rate_limited=False,
                rate_limit_expires_at=None,
                last_success_at=None,
                avg_latency_ms=0.0,
                total_requests_today=0,
            )

        except Exception as exc:
            logger.error(
                "get_model_status_failed",
                extra={
                    "company_id": company_id,
                    "provider": provider,
                    "model_id": model_id,
                    "error": str(exc),
                },
            )
            return ProviderModelStatus(
                provider=provider,
                model_id=model_id,
                display_name=model_id,
                tier="unknown",
                status=ProviderStatus.UNKNOWN.value,
                daily_requests=0,
                daily_limit=0,
                daily_remaining=0,
                minute_tokens=0,
                minute_limit=0,
                consecutive_failures=0,
                last_error="",
                is_rate_limited=False,
                rate_limit_expires_at=None,
                last_success_at=None,
                avg_latency_ms=0.0,
                total_requests_today=0,
            )

    def disable_provider_model(
        self,
        company_id: str,
        provider: str,
        model_id: str,
        reason: str,
    ) -> dict:
        """Manually disable a specific provider+model combination.

        Disabled models are skipped by the SmartRouter during routing.
        This override is tracked in-memory and applies per-company.

        Args:
            company_id: Tenant identifier (BC-001).
            provider: Provider name.
            model_id: Model identifier.
            reason: Human-readable reason for disabling.

        Returns:
            Confirmation dict with provider, model_id, and status.
        """
        try:
            _validate_company_id(company_id)
            provider = provider.lower().strip()

            if company_id not in self._disabled_models:
                self._disabled_models[company_id] = {}

            key = (provider, model_id)
            self._disabled_models[company_id][key] = reason

            # Create an alert for the disable action.
            self.create_alert(
                company_id=company_id,
                provider=provider,
                model_id=model_id,
                level=AlertLevel.WARNING.value,
                message=(
                    f"Model {model_id} ({provider}) manually disabled. "
                    f"Reason: {reason}"
                ),
            )

            logger.info(
                "provider_model_disabled",
                extra={
                    "company_id": company_id,
                    "provider": provider,
                    "model_id": model_id,
                    "reason": reason,
                },
            )
            return {
                "company_id": company_id,
                "provider": provider,
                "model_id": model_id,
                "status": ProviderStatus.DISABLED.value,
                "reason": reason,
                "disabled_at": _utc_now(),
            }

        except Exception as exc:
            logger.error(
                "disable_provider_model_failed",
                extra={
                    "company_id": company_id,
                    "provider": provider,
                    "model_id": model_id,
                    "error": str(exc),
                },
            )
            return {"error": str(exc), "status": "failed"}

    def enable_provider_model(
        self,
        company_id: str,
        provider: str,
        model_id: str,
    ) -> dict:
        """Re-enable a previously disabled provider+model combination.

        Args:
            company_id: Tenant identifier (BC-001).
            provider: Provider name.
            model_id: Model identifier.

        Returns:
            Confirmation dict with status.
        """
        try:
            _validate_company_id(company_id)
            provider = provider.lower().strip()

            key = (provider, model_id)
            disabled = self._disabled_models.get(company_id, {})
            if key in disabled:
                del disabled[key]
                logger.info(
                    "provider_model_enabled",
                    extra={
                        "company_id": company_id,
                        "provider": provider,
                        "model_id": model_id,
                    },
                )
            else:
                logger.info(
                    "provider_model_enable_noop",
                    extra={
                        "company_id": company_id,
                        "provider": provider,
                        "model_id": model_id,
                    },
                )

            return {
                "company_id": company_id,
                "provider": provider,
                "model_id": model_id,
                "status": ProviderStatus.HEALTHY.value,
                "enabled_at": _utc_now(),
            }

        except Exception as exc:
            logger.error(
                "enable_provider_model_failed",
                extra={
                    "company_id": company_id,
                    "provider": provider,
                    "model_id": model_id,
                    "error": str(exc),
                },
            )
            return {"error": str(exc), "status": "failed"}

    def health_check(self, company_id: str) -> dict:
        """Run a health check across all providers.

        Checks availability, rate limit status, and consecutive
        failures for every model in the registry. Returns an
        aggregated report.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            Dict with 'overall_status', 'providers', 'checked_at'.
        """
        try:
            _validate_company_id(company_id)
            tracker = self._get_health_tracker()
            registry = self._get_model_registry()

            if not tracker or not registry:
                return {
                    "overall_status": ProviderStatus.UNKNOWN.value,
                    "providers": {},
                    "checked_at": _utc_now(),
                    "error": "Health tracker or model registry unavailable",
                }

            provider_results: Dict[str, dict] = {}
            all_statuses: List[str] = []

            for provider in _KNOWN_PROVIDERS:
                model_results = []
                model_statuses = []

                for reg_key, config in registry.items():
                    if config.provider.value != provider:
                        continue

                    # Check if manually disabled.
                    disabled = self._disabled_models.get(company_id, {})
                    is_disabled = (
                        (provider, config.model_id) in disabled
                    )
                    if is_disabled:
                        model_statuses.append(
                            ProviderStatus.DISABLED.value
                        )
                        model_results.append({
                            "model_id": config.model_id,
                            "display_name": config.display_name,
                            "status": ProviderStatus.DISABLED.value,
                            "reason": disabled.get(
                                (provider, config.model_id), "manual",
                            ),
                        })
                        continue

                    # Check availability via tracker.
                    try:
                        from app.core.smart_router import ModelProvider

                        mp = ModelProvider(provider)
                        available = tracker.is_available(
                            mp, config.model_id,
                        )
                    except Exception:
                        available = True  # fail-open

                    # Determine status.
                    status = ProviderStatus.HEALTHY.value
                    if not available:
                        # Check if rate limited.
                        try:
                            from app.core.smart_router import (
                                ModelProvider,
                            )

                            mp = ModelProvider(provider)
                            rate_limited = tracker.check_rate_limit(
                                mp, config.model_id,
                            )
                        except Exception:
                            rate_limited = False

                        if rate_limited:
                            status = ProviderStatus.RATE_LIMITED.value
                        else:
                            status = ProviderStatus.UNHEALTHY.value

                    model_statuses.append(status)
                    model_results.append({
                        "model_id": config.model_id,
                        "display_name": config.display_name,
                        "status": status,
                        "tier": config.tier.value,
                    })

                worst = _worst_status(
                    model_statuses) if model_statuses else ProviderStatus.UNKNOWN.value
                all_statuses.append(worst)

                provider_results[provider] = {
                    "display_name": _PROVIDER_DISPLAY_NAMES.get(
                        provider, provider,
                    ),
                    "status": worst,
                    "total_models": len(model_results),
                    "models": model_results,
                }

                # Auto-alert on critical degradation.
                if worst in (
                    ProviderStatus.UNHEALTHY.value,
                    ProviderStatus.DISABLED.value,
                ):
                    self.create_alert(
                        company_id=company_id,
                        provider=provider,
                        level=AlertLevel.CRITICAL.value,
                        message=(
                            f"Health check: provider '{provider}' is "
                            f"{worst}. {len(model_results)} models checked."
                        ),
                    )

            overall = _worst_status(
                all_statuses) if all_statuses else ProviderStatus.UNKNOWN.value

            logger.info(
                "health_check_completed",
                extra={
                    "company_id": company_id,
                    "overall_status": overall,
                },
            )

            return {
                "company_id": company_id,
                "overall_status": overall,
                "providers": provider_results,
                "checked_at": _utc_now(),
            }

        except Exception as exc:
            logger.error(
                "health_check_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
            return {
                "overall_status": ProviderStatus.UNKNOWN.value,
                "providers": {},
                "checked_at": _utc_now(),
                "error": str(exc),
            }

    # ════════════════════════════════════════════════════════════
    # PUBLIC API — ALERTS
    # ════════════════════════════════════════════════════════════

    def get_alerts(
        self,
        company_id: str,
        level: Optional[str] = None,
        acknowledged: Optional[bool] = None,
        limit: int = 50,
    ) -> List[ProviderAlert]:
        """Retrieve alerts for a company, optionally filtered.

        Args:
            company_id: Tenant identifier (BC-001).
            level: Optional AlertLevel filter ('info', 'warning', 'critical').
            acknowledged: Optional boolean filter.
            limit: Max alerts to return (default 50, capped at 500).

        Returns:
            List of ProviderAlert, newest first.
        """
        try:
            _validate_company_id(company_id)
            limit = max(1, min(limit, 500))

            alerts = list(self._alerts.get(company_id, []))

            # Filter by level.
            if level:
                alerts = [a for a in alerts if a.level == level.lower()]

            # Filter by acknowledgement status.
            if acknowledged is not None:
                alerts = [
                    a for a in alerts if a.acknowledged == acknowledged
                ]

            # Sort newest first.
            alerts.sort(key=lambda a: a.created_at, reverse=True)

            return alerts[:limit]

        except Exception as exc:
            logger.error(
                "get_alerts_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
            return []

    def acknowledge_alert(
        self,
        company_id: str,
        alert_id: str,
        user_id: str,
    ) -> ProviderAlert:
        """Acknowledge an alert, marking it as reviewed.

        Args:
            company_id: Tenant identifier (BC-001).
            alert_id: UUID of the alert to acknowledge.
            user_id: ID of the user acknowledging the alert.

        Returns:
            The updated ProviderAlert.

        Raises:
            ValueError: If alert not found.
        """
        try:
            _validate_company_id(company_id)

            alerts = self._alerts.get(company_id, [])
            for alert in alerts:
                if alert.id == alert_id:
                    alert.acknowledged = True
                    alert.acknowledged_by = user_id
                    logger.info(
                        "alert_acknowledged",
                        extra={
                            "company_id": company_id,
                            "alert_id": alert_id,
                            "user_id": user_id,
                        },
                    )
                    return alert

            raise ValueError(
                f"Alert '{alert_id}' not found for company '{company_id}'"
            )

        except (ValueError, TypeError):
            raise
        except Exception as exc:
            logger.error(
                "acknowledge_alert_failed",
                extra={
                    "company_id": company_id,
                    "alert_id": alert_id,
                    "error": str(exc),
                },
            )
            raise

    def create_alert(
        self,
        company_id: str,
        provider: str,
        model_id: Optional[str] = None,
        level: str = AlertLevel.WARNING.value,
        message: str = "",
    ) -> ProviderAlert:
        """Create a new provider alert.

        Used internally and externally to record degradation events,
        manual disables, and other noteworthy provider incidents.

        Args:
            company_id: Tenant identifier (BC-001).
            provider: Provider name.
            model_id: Optional model identifier.
            level: AlertLevel value (default 'warning').
            message: Human-readable alert description.

        Returns:
            The created ProviderAlert.
        """
        try:
            if company_id not in self._alerts:
                self._alerts[company_id] = []

            alert = ProviderAlert(
                id=str(uuid.uuid4()),
                provider=provider.lower().strip(),
                model_id=model_id,
                level=level.lower(),
                message=message,
                created_at=_utc_now(),
                acknowledged=False,
            )

            self._alerts[company_id].append(alert)

            # Prune old alerts to prevent unbounded memory growth.
            if len(self._alerts[company_id]) > self._MAX_ALERTS_PER_COMPANY:
                self._alerts[company_id] = self._alerts[company_id][
                    -self._MAX_ALERTS_PER_COMPANY // 2:
                ]

            logger.debug(
                "alert_created",
                extra={
                    "company_id": company_id,
                    "alert_id": alert.id,
                    "provider": alert.provider,
                    "level": alert.level,
                },
            )
            return alert

        except Exception as exc:
            logger.error(
                "create_alert_failed",
                extra={
                    "company_id": company_id,
                    "provider": provider,
                    "error": str(exc),
                },
            )
            # Return a minimal alert even on failure (BC-008).
            return ProviderAlert(
                id=str(uuid.uuid4()),
                provider=provider,
                model_id=model_id,
                level=level,
                message=message,
                created_at=_utc_now(),
                acknowledged=False,
            )

    # ════════════════════════════════════════════════════════════
    # PUBLIC API — USAGE ANALYTICS
    # ════════════════════════════════════════════════════════════

    def get_usage_stats(
        self,
        company_id: str,
        provider: Optional[str] = None,
        days: int = 7,
    ) -> List[ProviderUsageStats]:
        """Retrieve usage analytics for providers.

        Returns daily aggregated stats. When no tracked data exists,
        returns synthetic entries derived from ProviderHealthTracker
        for the current day.

        Args:
            company_id: Tenant identifier (BC-001).
            provider: Optional provider filter. None = all providers.
            days: Number of days to look back (default 7, max 90).

        Returns:
            List of ProviderUsageStats, one per provider per day.
        """
        try:
            _validate_company_id(company_id)
            days = max(1, min(days, 90))

            tracker = self._get_health_tracker()
            registry = self._get_model_registry()
            now = datetime.now(timezone.utc)
            results: List[ProviderUsageStats] = []

            providers = (
                [provider.lower().strip()]
                if provider
                else _KNOWN_PROVIDERS
            )

            for prov in providers:
                for day_offset in range(days):
                    date = (
                        now - timedelta(days=day_offset)
                    ).strftime("%Y-%m-%d")

                    if date == _utc_today() and tracker and registry:
                        # Build today's stats from live tracker data.
                        stats = self._build_today_usage_stats(
                            company_id, prov, registry, tracker,
                        )
                        stats.date = date
                    else:
                        # Look up stored historical data.
                        stored = (
                            self._usage_stats
                            .get(company_id, {})
                            .get(prov, {})
                            .get(date)
                        )
                        if stored:
                            stats = ProviderUsageStats(
                                provider=prov,
                                date=date,
                                total_requests=stored.get(
                                    "total_requests", 0,
                                ),
                                successful_requests=stored.get(
                                    "successful_requests", 0,
                                ),
                                failed_requests=stored.get(
                                    "failed_requests", 0,
                                ),
                                rate_limited_count=stored.get(
                                    "rate_limited_count", 0,
                                ),
                                avg_latency_ms=stored.get(
                                    "avg_latency_ms", 0.0,
                                ),
                                total_tokens_used=stored.get(
                                    "total_tokens_used", 0,
                                ),
                                error_types=stored.get(
                                    "error_types", {},
                                ),
                            )
                        else:
                            # No data for this day — zero entry.
                            stats = ProviderUsageStats(
                                provider=prov,
                                date=date,
                                total_requests=0,
                                successful_requests=0,
                                failed_requests=0,
                                rate_limited_count=0,
                                avg_latency_ms=0.0,
                                total_tokens_used=0,
                            )

                    results.append(stats)

            # Sort by date descending, then provider.
            results.sort(key=lambda s: (s.date, s.provider), reverse=True)

            return results

        except Exception as exc:
            logger.error(
                "get_usage_stats_failed",
                extra={
                    "company_id": company_id,
                    "provider": provider,
                    "error": str(exc),
                },
            )
            return []

    # ════════════════════════════════════════════════════════════
    # PUBLIC API — API KEY MANAGEMENT
    # ════════════════════════════════════════════════════════════

    def get_api_keys(
        self,
        company_id: str,
        provider: Optional[str] = None,
    ) -> List[dict]:
        """List API key configurations (keys masked in responses).

        Args:
            company_id: Tenant identifier (BC-001).
            provider: Optional provider filter.

        Returns:
            List of dicts with masked key values.
        """
        try:
            _validate_company_id(company_id)
            keys = list(self._api_keys.get(company_id, []))

            if provider:
                keys = [k for k in keys if k.provider
                        == provider.lower().strip()]

            # Return masked representation.
            return [
                {
                    "provider": k.provider,
                    "key_id": k.key_id,
                    "key_value_masked": _mask_api_key(k.key_value),
                    "is_active": k.is_active,
                    "created_at": k.created_at,
                    "last_used_at": k.last_used_at,
                    "expires_at": k.expires_at,
                    "request_count": k.request_count,
                }
                for k in keys
            ]

        except Exception as exc:
            logger.error(
                "get_api_keys_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
            return []

    def rotate_api_key(
        self,
        company_id: str,
        provider: str,
        new_key: str,
    ) -> dict:
        """Rotate a provider's API key.

        Deactivates the current active key and creates a new one.
        The old key is kept in history but marked inactive.

        Args:
            company_id: Tenant identifier (BC-001).
            provider: Provider name to rotate key for.
            new_key: The new API key value.

        Returns:
            Dict with the new key config (masked).
        """
        try:
            _validate_company_id(company_id)
            provider = provider.lower().strip()

            if not new_key or not new_key.strip():
                raise ValueError("new_key must not be empty")

            if company_id not in self._api_keys:
                self._api_keys[company_id] = []

            # Deactivate existing keys for this provider.
            for key_config in self._api_keys[company_id]:
                if key_config.provider == provider and key_config.is_active:
                    key_config.is_active = False
                    logger.info(
                        "api_key_deactivated",
                        extra={
                            "company_id": company_id,
                            "provider": provider,
                            "key_id": key_config.key_id,
                        },
                    )

            # Create new active key.
            new_config = APIKeyConfig(
                provider=provider,
                key_id=str(uuid.uuid4()),
                key_value=new_key.strip(),
                is_active=True,
                created_at=_utc_now(),
                last_used_at=None,
                expires_at=None,
                request_count=0,
            )
            self._api_keys[company_id].append(new_config)

            # Create info alert for audit trail.
            self.create_alert(
                company_id=company_id,
                provider=provider,
                level=AlertLevel.INFO.value,
                message=f"API key rotated for provider '{provider}'. "
                f"New key ID: {new_config.key_id}",
            )

            logger.info(
                "api_key_rotated",
                extra={
                    "company_id": company_id,
                    "provider": provider,
                    "new_key_id": new_config.key_id,
                },
            )

            return {
                "company_id": company_id,
                "provider": provider,
                "key_id": new_config.key_id,
                "key_value_masked": _mask_api_key(new_config.key_value),
                "is_active": True,
                "created_at": new_config.created_at,
                "rotated_at": _utc_now(),
            }

        except (ValueError, TypeError):
            raise
        except Exception as exc:
            logger.error(
                "rotate_api_key_failed",
                extra={
                    "company_id": company_id,
                    "provider": provider,
                    "error": str(exc),
                },
            )
            return {"error": str(exc), "status": "failed"}

    # ════════════════════════════════════════════════════════════
    # PUBLIC API — DASHBOARD DATA
    # ════════════════════════════════════════════════════════════

    def get_dashboard_data(self, company_id: str) -> dict:
        """Return aggregated dashboard data for provider management UI.

        Combines provider summaries, recent alerts, usage overview,
        and API key status into a single response.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            Dict with keys: 'providers', 'alerts', 'usage_summary',
            'api_keys', 'generated_at'.
        """
        try:
            _validate_company_id(company_id)

            providers = self.get_all_providers_status(company_id)
            recent_alerts = self.get_alerts(
                company_id, limit=10,
            )
            api_keys = self.get_api_keys(company_id)

            # Build usage summary from today's stats.
            usage_summary = self._build_usage_summary(company_id)

            return {
                "company_id": company_id,
                "providers": [
                    {
                        "provider": p.provider,
                        "display_name": p.display_name,
                        "status": p.status,
                        "total_models": p.total_models,
                        "healthy_models": p.healthy_models,
                        "unhealthy_models": p.unhealthy_models,
                        "total_requests_today": p.total_requests_today,
                    }
                    for p in providers
                ],
                "alerts": [
                    {
                        "id": a.id,
                        "provider": a.provider,
                        "model_id": a.model_id,
                        "level": a.level,
                        "message": a.message,
                        "created_at": a.created_at,
                        "acknowledged": a.acknowledged,
                    }
                    for a in recent_alerts
                ],
                "usage_summary": usage_summary,
                "api_keys": api_keys,
                "generated_at": _utc_now(),
            }

        except Exception as exc:
            logger.error(
                "get_dashboard_data_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
            return {
                "company_id": company_id,
                "providers": [],
                "alerts": [],
                "usage_summary": {},
                "api_keys": [],
                "generated_at": _utc_now(),
                "error": str(exc),
            }

    # ════════════════════════════════════════════════════════════
    # PRIVATE — INTERNAL BUILDERS
    # ════════════════════════════════════════════════════════════

    def _build_provider_summary(
        self,
        company_id: str,
        provider: str,
    ) -> ProviderSummary:
        """Build a ProviderSummary by aggregating all model statuses."""
        registry = self._get_model_registry()
        tracker = self._get_health_tracker()

        model_statuses = self._build_all_model_statuses(
            company_id, provider, registry, tracker,
        )

        if not model_statuses:
            return ProviderSummary(
                provider=provider,
                display_name=_PROVIDER_DISPLAY_NAMES.get(provider, provider),
                status=ProviderStatus.UNKNOWN.value,
                total_models=0,
                healthy_models=0,
                degraded_models=0,
                unhealthy_models=0,
                total_requests_today=0,
            )

        status_list = [m.status for m in model_statuses]
        worst = _worst_status(status_list)
        healthy_count = sum(
            1 for s in status_list
            if s == ProviderStatus.HEALTHY.value
        )
        degraded_count = sum(
            1 for s in status_list
            if s == ProviderStatus.DEGRADED.value
        )
        unhealthy_count = sum(
            1 for s in status_list
            if s in (
                ProviderStatus.UNHEALTHY.value,
                ProviderStatus.DISABLED.value,
                ProviderStatus.RATE_LIMITED.value,
            )
        )
        total_requests = sum(m.total_requests_today for m in model_statuses)

        return ProviderSummary(
            provider=provider,
            display_name=_PROVIDER_DISPLAY_NAMES.get(provider, provider),
            status=worst,
            total_models=len(model_statuses),
            healthy_models=healthy_count,
            degraded_models=degraded_count,
            unhealthy_models=unhealthy_count,
            total_requests_today=total_requests,
            models=model_statuses,
        )

    def _build_all_model_statuses(
        self,
        company_id: str,
        provider: str,
        registry: dict,
        tracker,
    ) -> List[ProviderModelStatus]:
        """Build ProviderModelStatus for every model of a provider."""
        model_statuses: List[ProviderModelStatus] = []
        disabled = self._disabled_models.get(company_id, {})

        for reg_key, config in registry.items():
            if config.provider.value != provider:
                continue

            model_id = config.model_id
            key = (provider, model_id)

            # Check manual disable override.
            if key in disabled:
                model_statuses.append(ProviderModelStatus(
                    provider=provider,
                    model_id=model_id,
                    display_name=config.display_name,
                    tier=config.tier.value,
                    status=ProviderStatus.DISABLED.value,
                    daily_requests=0,
                    daily_limit=config.max_requests_per_day,
                    daily_remaining=config.max_requests_per_day,
                    minute_tokens=0,
                    minute_limit=config.max_tokens_per_minute,
                    consecutive_failures=0,
                    last_error=disabled[key],
                    is_rate_limited=False,
                    rate_limit_expires_at=None,
                    last_success_at=self._last_success.get(
                        company_id, {},
                    ).get(key),
                    avg_latency_ms=self._avg_latency(
                        company_id, provider, model_id,
                    ),
                    total_requests_today=0,
                ))
                continue

            # Pull live data from ProviderHealthTracker.
            daily_requests = 0
            daily_limit = config.max_requests_per_day
            daily_remaining = daily_limit
            minute_tokens = 0
            minute_limit = config.max_tokens_per_minute
            consecutive_failures = 0
            last_error = ""
            is_rate_limited = False
            rate_limit_expires_at = None

            if tracker:
                try:
                    from app.core.smart_router import ModelProvider

                    mp = ModelProvider(provider)
                    daily_requests = tracker.get_daily_usage(
                        mp, model_id,
                    )
                    daily_remaining = tracker.get_daily_remaining(
                        mp, model_id,
                    )
                    is_rate_limited = tracker.check_rate_limit(
                        mp, model_id,
                    )

                    # Get raw usage for minute tokens and failures.
                    all_status = tracker.get_all_status()
                    registry_key = f"{model_id}-{provider}"
                    raw = all_status.get(registry_key, {})
                    minute_tokens = raw.get("minute_count", 0)
                    minute_limit = raw.get(
                        "minute_limit", config.max_tokens_per_minute,
                    )
                    consecutive_failures = raw.get(
                        "consecutive_failures", 0,
                    )
                    last_error = raw.get("last_error", "")

                    if is_rate_limited and raw.get("rate_limited"):
                        # Estimate expiry from last error message.
                        rate_limit_expires_at = (
                            _utc_now()
                        )  # Approximation.

                except Exception as exc:
                    logger.warning(
                        "tracker_read_error",
                        extra={
                            "provider": provider,
                            "model_id": model_id,
                            "error": str(exc),
                        },
                    )

            # Determine status.
            status = ProviderStatus.HEALTHY.value
            if is_rate_limited:
                status = ProviderStatus.RATE_LIMITED.value
            elif consecutive_failures >= 3:
                status = ProviderStatus.UNHEALTHY.value
            elif consecutive_failures >= 1:
                status = ProviderStatus.DEGRADED.value

            # Check if daily limit is exhausted.
            if daily_remaining <= 0 and daily_requests >= daily_limit:
                status = ProviderStatus.RATE_LIMITED.value

            model_statuses.append(ProviderModelStatus(
                provider=provider,
                model_id=model_id,
                display_name=config.display_name,
                tier=config.tier.value,
                status=status,
                daily_requests=daily_requests,
                daily_limit=daily_limit,
                daily_remaining=max(0, daily_remaining),
                minute_tokens=minute_tokens,
                minute_limit=minute_limit,
                consecutive_failures=consecutive_failures,
                last_error=last_error,
                is_rate_limited=is_rate_limited,
                rate_limit_expires_at=rate_limit_expires_at,
                last_success_at=self._last_success.get(
                    company_id, {},
                ).get(key),
                avg_latency_ms=self._avg_latency(
                    company_id, provider, model_id,
                ),
                total_requests_today=daily_requests,
            ))

        return model_statuses

    def _build_today_usage_stats(
        self,
        company_id: str,
        provider: str,
        registry: dict,
        tracker,
    ) -> ProviderUsageStats:
        """Build today's ProviderUsageStats from live tracker data."""
        total_requests = 0
        successful = 0
        failed = 0
        rate_limited = 0
        total_tokens = 0
        error_types: Dict[str, int] = defaultdict(int)

        for reg_key, config in registry.items():
            if config.provider.value != provider:
                continue

            try:
                from app.core.smart_router import ModelProvider

                mp = ModelProvider(provider)
                daily = tracker.get_daily_usage(mp, config.model_id)
                total_requests += daily

                is_rl = tracker.check_rate_limit(mp, config.model_id)
                if is_rl:
                    rate_limited += 1

                all_status = tracker.get_all_status()
                raw = all_status.get(reg_key, {})
                failures = raw.get("consecutive_failures", 0)
                if failures >= 3:
                    failed += 1
                else:
                    successful += max(0, daily - failures)

                err = raw.get("last_error", "")
                if err:
                    error_types[err] += 1

                total_tokens += raw.get("minute_count", 0)

            except Exception:
                continue

        avg_lat = self._avg_latency_for_provider(company_id, provider)

        return ProviderUsageStats(
            provider=provider,
            date=_utc_today(),
            total_requests=total_requests,
            successful_requests=max(0, successful),
            failed_requests=max(0, failed),
            rate_limited_count=rate_limited,
            avg_latency_ms=avg_lat,
            total_tokens_used=total_tokens,
            error_types=dict(error_types),
        )

    def _build_usage_summary(self, company_id: str) -> dict:
        """Build a concise usage summary for the dashboard."""
        summary: Dict[str, dict] = {}

        for prov in _KNOWN_PROVIDERS:
            try:
                stats = self.get_usage_stats(
                    company_id, provider=prov, days=1,
                )
                if stats:
                    s = stats[0]
                    summary[prov] = {
                        "total_requests": s.total_requests,
                        "successful_requests": s.successful_requests,
                        "failed_requests": s.failed_requests,
                        "rate_limited_count": s.rate_limited_count,
                        "avg_latency_ms": s.avg_latency_ms,
                    }
                else:
                    summary[prov] = {
                        "total_requests": 0,
                        "successful_requests": 0,
                        "failed_requests": 0,
                        "rate_limited_count": 0,
                        "avg_latency_ms": 0.0,
                    }
            except Exception:
                summary[prov] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "rate_limited_count": 0,
                    "avg_latency_ms": 0.0,
                }

        # Add totals across all providers.
        totals = {
            "total_requests": sum(
                v["total_requests"] for v in summary.values()
            ),
            "successful_requests": sum(
                v["successful_requests"] for v in summary.values()
            ),
            "failed_requests": sum(
                v["failed_requests"] for v in summary.values()
            ),
            "rate_limited_count": sum(
                v["rate_limited_count"] for v in summary.values()
            ),
        }

        return {"by_provider": summary, "totals": totals}

    # ── Latency Tracking ────────────────────────────────────────

    def _avg_latency(
        self, company_id: str, provider: str, model_id: str,
    ) -> float:
        """Get average latency for a provider+model from samples."""
        samples = (
            self._latency_samples
            .get(company_id, {})
            .get((provider, model_id), [])
        )
        if not samples:
            return 0.0
        return sum(samples) / len(samples)

    def _avg_latency_for_provider(
        self, company_id: str, provider: str,
    ) -> float:
        """Get average latency across all models for a provider."""
        provider_samples: List[float] = []
        for (prov, _model), samples in (
            self._latency_samples.get(company_id, {}).items()
        ):
            if prov == provider and samples:
                provider_samples.extend(samples)
        if not provider_samples:
            return 0.0
        return sum(provider_samples) / len(provider_samples)

    def record_latency(
        self,
        company_id: str,
        provider: str,
        model_id: str,
        latency_ms: float,
    ) -> None:
        """Record a latency sample for a provider+model.

        Keeps the last 100 samples per model for rolling average.
        Called by external code (e.g. SmartRouter) after LLM calls.

        Args:
            company_id: Tenant identifier (BC-001).
            provider: Provider name.
            model_id: Model identifier.
            latency_ms: Request latency in milliseconds.
        """
        try:
            if company_id not in self._latency_samples:
                self._latency_samples[company_id] = {}

            key = (provider.lower().strip(), model_id)
            if key not in self._latency_samples[company_id]:
                self._latency_samples[company_id][key] = []

            samples = self._latency_samples[company_id][key]
            samples.append(float(latency_ms))

            # Keep last 100 samples.
            if len(samples) > 100:
                self._latency_samples[company_id][key] = samples[-100:]

        except Exception as exc:
            logger.warning(
                "record_latency_failed",
                extra={
                    "company_id": company_id,
                    "provider": provider,
                    "model_id": model_id,
                    "error": str(exc),
                },
            )

    def record_success(
        self,
        company_id: str,
        provider: str,
        model_id: str,
    ) -> None:
        """Record a successful call timestamp for a provider+model.

        Args:
            company_id: Tenant identifier (BC-001).
            provider: Provider name.
            model_id: Model identifier.
        """
        try:
            if company_id not in self._last_success:
                self._last_success[company_id] = {}

            key = (provider.lower().strip(), model_id)
            self._last_success[company_id][key] = _utc_now()
        except Exception as exc:
            logger.warning(
                "record_success_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )

    # ── Disable Check ───────────────────────────────────────────

    def is_model_disabled(
        self,
        company_id: str,
        provider: str,
        model_id: str,
    ) -> bool:
        """Check if a provider+model is manually disabled.

        Can be called by SmartRouter to respect manual overrides.

        Args:
            company_id: Tenant identifier (BC-001).
            provider: Provider name.
            model_id: Model identifier.

        Returns:
            True if the model is manually disabled.
        """
        try:
            key = (provider.lower().strip(), model_id)
            return key in self._disabled_models.get(company_id, {})
        except Exception:
            return False  # BC-008: fail-open

    def get_disabled_models(
        self, company_id: str,
    ) -> Dict[str, List[dict]]:
        """Get all manually disabled models for a company.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            Dict mapping provider name to list of disabled model info.
        """
        try:
            _validate_company_id(company_id)
            disabled = self._disabled_models.get(company_id, {})
            result: Dict[str, List[dict]] = {}

            for (prov, model_id), reason in disabled.items():
                if prov not in result:
                    result[prov] = []
                result[prov].append({
                    "model_id": model_id,
                    "reason": reason,
                })

            return result

        except Exception as exc:
            logger.error(
                "get_disabled_models_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
            return {}
