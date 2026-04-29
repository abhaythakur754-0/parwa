"""
F-201: Context Health Meter (Week 10 Day 12)

Tracks context quality over conversation turns and alerts when
context quality degrades. Six health metrics are monitored:

  - token_usage_ratio:     How much of the token budget is used
  - compression_ratio:     How much context has been compressed
  - relevance_score:       How relevant context is to the query
  - freshness_score:       How recent the context is
  - signal_preservation:   How well key signals survived compression
  - context_coherence:     Logical coherence of compressed context

Health statuses:
  - HEALTHY   (>= 0.7):   All metrics within acceptable bounds
  - DEGRADING (0.4-0.7):  Some metrics degrading, action advised
  - CRITICAL  (0.2-0.4):  Multiple metrics failing, immediate action
  - EXHAUSTED (< 0.2):    Context is no longer usable

BC-001: All public methods take company_id as the first parameter.
BC-008: Every public method is wrapped in try/except; never crashes.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("context_health")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Weights for each metric in the overall health score
_HEALTH_WEIGHTS: Dict[str, float] = {
    "token_usage_ratio": 0.20,
    "compression_ratio": 0.15,
    "relevance_score": 0.25,
    "freshness_score": 0.15,
    "signal_preservation": 0.15,
    "context_coherence": 0.10,
}

# Default thresholds for each metric
_DEFAULT_HEALTH_THRESHOLDS: Dict[str, float] = {
    "token_usage_ratio": 0.8,
    "compression_ratio": 0.4,
    "relevance_score": 0.5,
    "freshness_score": 0.4,
    "signal_preservation": 0.5,
    "context_coherence": 0.6,
}

# Per-variant health configurations
_VARIANT_HEALTH_CONFIGS: Dict[str, Dict[str, float]] = {
    "mini_parwa": {
        "token_budget_threshold": 0.9,
        "compression_ratio_threshold": 0.3,
        "relevance_decay_rate": 0.15,
        "freshness_decay_minutes": 20,
    },
    "parwa": {
        "token_budget_threshold": 0.8,
        "compression_ratio_threshold": 0.4,
        "relevance_decay_rate": 0.10,
        "freshness_decay_minutes": 30,
    },
    "high_parwa": {
        "token_budget_threshold": 0.7,
        "compression_ratio_threshold": 0.5,
        "relevance_decay_rate": 0.05,
        "freshness_decay_minutes": 45,
    },
}

_HEALTH_CHECK_TTL_HOURS: int = 24
_MAX_HISTORY_LENGTH: int = 100


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class HealthStatus(str, Enum):
    """Overall health status based on the weighted score."""
    HEALTHY = "healthy"      # Score >= 0.7
    DEGRADING = "degrading"  # Score 0.4-0.7
    CRITICAL = "critical"    # Score 0.2-0.4
    EXHAUSTED = "exhausted"  # Score < 0.2


class HealthAlertType(str, Enum):
    """Types of health alerts that can be triggered."""
    TOKEN_BUDGET_LOW = "token_budget_low"
    COMPRESSION_RATIO_HIGH = "compression_ratio_high"
    SIGNAL_DEGRADATION = "signal_degradation"
    CONTEXT_DRIFT = "context_drift"
    FRESHNESS_EXPIRED = "freshness_expired"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class HealthMetrics:
    """Individual health metric measurements for a single turn."""
    token_usage_ratio: float = 0.0
    compression_ratio: float = 1.0
    relevance_score: float = 1.0
    freshness_score: float = 1.0
    signal_preservation: float = 1.0
    context_coherence: float = 1.0


@dataclass
class HealthAlert:
    """A single alert generated when a metric crosses a threshold."""
    alert_type: HealthAlertType
    severity: HealthStatus
    message: str
    metric_name: str
    metric_value: float
    threshold: float
    timestamp: str = ""


@dataclass
class HealthReport:
    """Complete health report for a conversation turn."""
    company_id: str = ""
    conversation_id: str = ""
    overall_score: float = 1.0
    status: HealthStatus = HealthStatus.HEALTHY
    metrics: HealthMetrics = field(default_factory=HealthMetrics)
    alerts: List[HealthAlert] = field(default_factory=list)
    turn_number: int = 0
    timestamp: str = ""
    recommendations: List[str] = field(default_factory=list)


@dataclass
class HealthConfig:
    """Configuration for the ContextHealthMeter."""
    company_id: str = ""
    variant_type: str = "parwa"
    token_budget_threshold: float = 0.8
    compression_ratio_threshold: float = 0.4
    relevance_decay_rate: float = 0.1
    freshness_decay_minutes: int = 30
    health_check_interval_turns: int = 1
    alert_cooldown_seconds: int = 60


# ══════════════════════════════════════════════════════════════════
# EXCEPTION
# ══════════════════════════════════════════════════════════════════


class ContextHealthError(Exception):
    """Raised when context health checks fail critically.

    Inherits from Exception for BC-008 graceful degradation.
    """

    def __init__(
        self,
        message: str = "Context health check failed",
        company_id: str = "",
    ) -> None:
        self.message = message
        self.company_id = company_id
        super().__init__(self.message)


# ══════════════════════════════════════════════════════════════════
# CONTEXT HEALTH METER
# ══════════════════════════════════════════════════════════════════


class ContextHealthMeter:
    """F-201: Context Health Meter.

    Monitors context quality over conversation turns. Computes a
    weighted health score from six metrics and generates alerts
    when thresholds are crossed. Maintains per-conversation
    history with bounded length.

    BC-001: company_id first parameter on public methods.
    BC-008: Never crash — graceful degradation.
    BC-012: All timestamps UTC.
    """

    def __init__(
        self, config: Optional[HealthConfig] = None,
    ) -> None:
        self._config = config or HealthConfig()
        self._turn_history: Dict[str, List[HealthReport]] = {}
        self._last_alerts: Dict[str, Dict[str, str]] = {}

        logger.info(
            "context_health_meter_initialized",
            variant_type=self._config.variant_type,
            company_id=self._config.company_id,
        )

    # ── Public API ─────────────────────────────────────────────

    async def check_health(
        self,
        company_id: str,
        conversation_id: str,
        metrics: HealthMetrics,
        turn_number: int = 0,
        **kwargs: Any,
    ) -> HealthReport:
        """Check context health for a conversation turn.

        Calculates the overall weighted score, determines the
        health status, checks all metric thresholds, generates
        alerts, and produces recommendations.

        Args:
            company_id: Tenant company ID (BC-001).
            conversation_id: Unique conversation identifier.
            metrics: Measured health metrics for this turn.
            turn_number: Current turn number in the conversation.
            **kwargs: Optional extra context.

        Returns:
            HealthReport with score, status, alerts, and
            recommendations.
        """
        try:
            overall_score = self._calculate_overall_score(metrics)
            status = self._determine_status(overall_score)
            alerts = self._check_alerts(
                company_id, conversation_id, metrics,
                overall_score,
            )
            recommendations = self._generate_recommendations_from_status(
                status, alerts,
            )

            now = datetime.now(timezone.utc).isoformat()
            report = HealthReport(
                company_id=company_id,
                conversation_id=conversation_id,
                overall_score=round(overall_score, 4),
                status=status,
                metrics=metrics,
                alerts=alerts,
                turn_number=turn_number,
                timestamp=now,
                recommendations=recommendations,
            )

            # Store in history
            conv_key = self._conv_key(
                company_id, conversation_id,
            )
            if conv_key not in self._turn_history:
                self._turn_history[conv_key] = []
            self._turn_history[conv_key].append(report)

            # Prune old history
            if (
                len(self._turn_history[conv_key])
                > _MAX_HISTORY_LENGTH
            ):
                self._turn_history[conv_key] = (
                    self._turn_history[conv_key]
                    [-_MAX_HISTORY_LENGTH:]
                )

            logger.info(
                "health_check_completed",
                company_id=company_id,
                conversation_id=conversation_id,
                turn_number=turn_number,
                score=round(overall_score, 4),
                status=status.value,
                alert_count=len(alerts),
            )

            return report

        except Exception as exc:
            # BC-008: Graceful degradation
            logger.warning(
                "health_check_failed",
                error=str(exc),
                company_id=company_id,
                conversation_id=conversation_id,
            )
            return HealthReport(
                company_id=company_id,
                conversation_id=conversation_id,
                overall_score=0.0,
                status=HealthStatus.EXHAUSTED,
                turn_number=turn_number,
                timestamp=datetime.now(
                    timezone.utc,
                ).isoformat(),
                recommendations=[
                    "Health check encountered an error; "
                    "context quality could not be assessed",
                ],
            )

    # ── Score Calculation ──────────────────────────────────────

    def _calculate_overall_score(
        self, metrics: HealthMetrics,
    ) -> float:
        """Compute the weighted average of all health metrics.

        token_usage_ratio is inverted (1.0 - ratio) so that
        higher token usage produces a lower contribution.
        compression_ratio is used as-is (1.0 = no compression).
        """
        weights = _HEALTH_WEIGHTS

        # Token usage is inversely related to health
        token_health = max(
            0.0, 1.0 - metrics.token_usage_ratio,
        )

        # Compression ratio: 1.0 = healthy, lower = degraded
        compression_health = min(
            1.0, metrics.compression_ratio,
        )

        score = (
            token_health * weights["token_usage_ratio"]
            + compression_health * weights["compression_ratio"]
            + metrics.relevance_score * weights["relevance_score"]
            + metrics.freshness_score * weights["freshness_score"]
            + metrics.signal_preservation
            * weights["signal_preservation"]
            + metrics.context_coherence
            * weights["context_coherence"]
        )

        return max(0.0, min(1.0, score))

    def _determine_status(self, score: float) -> HealthStatus:
        """Map a numeric score to a HealthStatus enum."""
        if score >= 0.7:
            return HealthStatus.HEALTHY
        if score >= 0.4:
            return HealthStatus.DEGRADING
        if score >= 0.2:
            return HealthStatus.CRITICAL
        return HealthStatus.EXHAUSTED

    # ── Alert Checking ─────────────────────────────────────────

    def _check_alerts(
        self,
        company_id: str,
        conversation_id: str,
        metrics: HealthMetrics,
        score: float,
    ) -> List[HealthAlert]:
        """Check each metric against thresholds.

        Applies cooldown so the same alert type is not repeated
        within the configured cooldown window.
        """
        alerts: List[HealthAlert] = []
        now = datetime.now(timezone.utc).isoformat()
        cooldown = self._config.alert_cooldown_seconds
        conv_key = self._conv_key(
            company_id, conversation_id,
        )

        # Ensure last_alerts entry exists
        if conv_key not in self._last_alerts:
            self._last_alerts[conv_key] = {}

        last_alert_times = self._last_alerts[conv_key]

        def _should_alert(alert_type: str) -> bool:
            """Check cooldown for an alert type."""
            last_time = last_alert_times.get(alert_type, "")
            if not last_time:
                return True
            try:
                last_dt = datetime.fromisoformat(
                    last_time.replace("Z", "+00:00"),
                )
                elapsed = (
                    datetime.now(timezone.utc) - last_dt
                ).total_seconds()
                return elapsed >= cooldown
            except (ValueError, TypeError):
                return True

        # Token budget alert
        if metrics.token_usage_ratio >= (
            self._config.token_budget_threshold
        ):
            atype = HealthAlertType.TOKEN_BUDGET_LOW
            if _should_alert(atype.value):
                alert = HealthAlert(
                    alert_type=atype,
                    severity=self._determine_status(
                        max(0.0, 1.0 - metrics.token_usage_ratio),
                    ),
                    message=(
                        f"Token budget at "
                        f"{metrics.token_usage_ratio:.0%}, "
                        f"threshold "
                        f"{self._config.token_budget_threshold:.0%}"
                    ),
                    metric_name="token_usage_ratio",
                    metric_value=metrics.token_usage_ratio,
                    threshold=self._config.token_budget_threshold,
                    timestamp=now,
                )
                alerts.append(alert)
                last_alert_times[atype.value] = now

        # Compression ratio alert
        if metrics.compression_ratio <= (
            self._config.compression_ratio_threshold
        ):
            atype = HealthAlertType.COMPRESSION_RATIO_HIGH
            if _should_alert(atype.value):
                alert = HealthAlert(
                    alert_type=atype,
                    severity=HealthStatus.DEGRADING,
                    message=(
                        f"Context compressed to "
                        f"{metrics.compression_ratio:.0%}, "
                        f"below threshold "
                        f"{self._config.compression_ratio_threshold:.0%}"
                    ),
                    metric_name="compression_ratio",
                    metric_value=metrics.compression_ratio,
                    threshold=(
                        self._config.compression_ratio_threshold
                    ),
                    timestamp=now,
                )
                alerts.append(alert)
                last_alert_times[atype.value] = now

        # Signal preservation alert
        sig_threshold = _DEFAULT_HEALTH_THRESHOLDS.get(
            "signal_preservation", 0.5,
        )
        if metrics.signal_preservation < sig_threshold:
            atype = HealthAlertType.SIGNAL_DEGRADATION
            if _should_alert(atype.value):
                alert = HealthAlert(
                    alert_type=atype,
                    severity=HealthStatus.CRITICAL,
                    message=(
                        f"Signal preservation at "
                        f"{metrics.signal_preservation:.2f}, "
                        f"below {sig_threshold}"
                    ),
                    metric_name="signal_preservation",
                    metric_value=metrics.signal_preservation,
                    threshold=sig_threshold,
                    timestamp=now,
                )
                alerts.append(alert)
                last_alert_times[atype.value] = now

        # Context drift (relevance + coherence both low)
        if (
            metrics.relevance_score < 0.5
            and metrics.context_coherence < 0.6
        ):
            atype = HealthAlertType.CONTEXT_DRIFT
            if _should_alert(atype.value):
                alert = HealthAlert(
                    alert_type=atype,
                    severity=HealthStatus.DEGRADING,
                    message=(
                        "Context drift detected: relevance and "
                        "coherence both below acceptable levels"
                    ),
                    metric_name="context_drift",
                    metric_value=(
                        metrics.relevance_score
                        * metrics.context_coherence
                    ),
                    threshold=0.3,
                    timestamp=now,
                )
                alerts.append(alert)
                last_alert_times[atype.value] = now

        # Freshness expired alert
        fresh_threshold = _DEFAULT_HEALTH_THRESHOLDS.get(
            "freshness_score", 0.4,
        )
        if metrics.freshness_score < fresh_threshold:
            atype = HealthAlertType.FRESHNESS_EXPIRED
            if _should_alert(atype.value):
                alert = HealthAlert(
                    alert_type=atype,
                    severity=HealthStatus.DEGRADING,
                    message=(
                        f"Context freshness at "
                        f"{metrics.freshness_score:.2f}, "
                        f"below {fresh_threshold} — "
                        "consider refreshing context"
                    ),
                    metric_name="freshness_score",
                    metric_value=metrics.freshness_score,
                    threshold=fresh_threshold,
                    timestamp=now,
                )
                alerts.append(alert)
                last_alert_times[atype.value] = now

        return alerts

    # ── Recommendations ────────────────────────────────────────

    def _generate_recommendations_from_status(
        self,
        status: HealthStatus,
        alerts: List[HealthAlert],
    ) -> List[str]:
        """Generate actionable recommendations.

        Based on the health status and active alerts.
        """
        recommendations: List[str] = []

        if status == HealthStatus.HEALTHY:
            recommendations.append(
                "Context health is good — no action needed",
            )
            return recommendations

        if status == HealthStatus.EXHAUSTED:
            recommendations.append(
                "CRITICAL: Context is exhausted. "
                "Start a new conversation or reset context.",
            )

        # Check specific alerts for targeted recommendations
        alert_types = {a.alert_type for a in alerts}

        if HealthAlertType.TOKEN_BUDGET_LOW in alert_types:
            recommendations.append(
                "Consider compressing older context or "
                "summarizing earlier conversation turns "
                "to free up token budget",
            )

        if HealthAlertType.COMPRESSION_RATIO_HIGH in alert_types:
            recommendations.append(
                "Compression is aggressive — review which "
                "chunks are being retained and adjust "
                "priority thresholds",
            )

        if HealthAlertType.SIGNAL_DEGRADATION in alert_types:
            recommendations.append(
                "Key signals are being lost during "
                "compression — increase priority weights "
                "for signal-carrying content",
            )

        if HealthAlertType.CONTEXT_DRIFT in alert_types:
            recommendations.append(
                "Context is drifting from the current query "
                "topic — consider injecting fresh retrieval "
                "results",
            )

        if HealthAlertType.FRESHNESS_EXPIRED in alert_types:
            recommendations.append(
                "Context is stale — refresh with recent "
                "knowledge base retrieval or request "
                "user clarification",
            )

        if not recommendations:
            recommendations.append(
                "Monitor context health on subsequent turns",
            )

        return recommendations

    # ── History Management ─────────────────────────────────────

    def get_history(
        self,
        company_id: str,
        conversation_id: str,
    ) -> List[HealthReport]:
        """Get the full health history for a conversation."""
        try:
            conv_key = self._conv_key(
                company_id, conversation_id,
            )
            return list(
                self._turn_history.get(conv_key, []),
            )
        except Exception as exc:
            logger.warning(
                "get_history_failed",
                error=str(exc),
                company_id=company_id,
                conversation_id=conversation_id,
            )
            return []

    def get_latest_report(
        self,
        company_id: str,
        conversation_id: str,
    ) -> Optional[HealthReport]:
        """Get the most recent health report for a conversation."""
        try:
            conv_key = self._conv_key(
                company_id, conversation_id,
            )
            history = self._turn_history.get(conv_key, [])
            return history[-1] if history else None
        except Exception as exc:
            logger.warning(
                "get_latest_report_failed",
                error=str(exc),
                company_id=company_id,
                conversation_id=conversation_id,
            )
            return None

    def reset(
        self,
        company_id: str,
        conversation_id: str,
    ) -> None:
        """Clear health history and alerts for a conversation."""
        try:
            conv_key = self._conv_key(
                company_id, conversation_id,
            )
            self._turn_history.pop(conv_key, None)
            self._last_alerts.pop(conv_key, None)

            logger.info(
                "health_meter_reset",
                company_id=company_id,
                conversation_id=conversation_id,
            )
        except Exception as exc:
            logger.warning(
                "health_meter_reset_failed",
                error=str(exc),
                company_id=company_id,
                conversation_id=conversation_id,
            )

    def reset_all(self) -> None:
        """Clear all health history. For testing."""
        try:
            self._turn_history.clear()
            self._last_alerts.clear()
            logger.info("health_meter_reset_all")
        except Exception as exc:
            logger.warning(
                "health_meter_reset_all_failed",
                error=str(exc),
            )

    # ── Config Helpers ─────────────────────────────────────────

    @staticmethod
    def get_variant_config(
        variant_type: str,
    ) -> Dict[str, float]:
        """Get the default health thresholds for a variant."""
        return dict(
            _VARIANT_HEALTH_CONFIGS.get(
                variant_type,
                _VARIANT_HEALTH_CONFIGS["parwa"],
            ),
        )

    def get_config(self) -> HealthConfig:
        """Return the current health meter configuration."""
        return self._config

    # ── Internal Helpers ───────────────────────────────────────

    @staticmethod
    def _conv_key(company_id: str, conversation_id: str) -> str:
        """Build a canonical dict key for a conversation."""
        return f"{company_id}:{conversation_id}"
