"""
SG-20: AI Self-Healing Engine — Per-Variant Autonomous Recovery.

Monitors AI engine health and automatically takes corrective actions
when problems are detected. Each variant (mini_parwa, parwa, high_parwa)
has isolated healing state and independent rules.

Healing Actions:
- Provider Auto-Switch: Redirect traffic away from failing providers.
- Threshold Auto-Adjust: Temporarily lower confidence thresholds during
  score drops, restore when scores recover.
- Error Spike Detection: Disable providers on sudden error surges,
  re-enable after sustained recovery.
- Latency Spike Handling: Switch to faster providers when latency
  degrades, restore original after recovery.

BC-001: company_id is always first parameter on public methods.
BC-008: Never crash — every public method is wrapped in try/except.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("self_healing")


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class ConditionType(str, Enum):
    """Types of conditions the healing engine can detect."""
    CONSECUTIVE_FAILURES = "consecutive_failures"
    ERROR_SPIKE = "error_spike"
    LATENCY_SPIKE = "latency_spike"
    CONFIDENCE_DROP = "confidence_drop"
    RATE_LIMIT_HIT = "rate_limit_hit"
    PROVIDER_UNHEALTHY = "provider_unhealthy"


class ActionType(str, Enum):
    """Types of healing actions the engine can take."""
    PROVIDER_DISABLE = "provider_disable"
    PROVIDER_ENABLE = "provider_enable"
    PROVIDER_SWITCH = "provider_switch"
    THRESHOLD_LOWER = "threshold_lower"
    THRESHOLD_RESTORE = "threshold_restore"
    TRAFFIC_RAMP_UP = "traffic_ramp_up"
    ALERT_CREATED = "alert_created"
    NO_ACTION = "no_action"


class HealingStatus(str, Enum):
    """Status of a healing action."""
    TRIGGERED = "triggered"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    EXPIRED = "expired"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class HealingRule:
    """A rule that maps a condition to a healing action."""
    rule_id: str
    condition_type: str
    action_type: str
    priority: int = 5
    enabled: bool = True
    cooldown_seconds: int = 300  # 5 minutes default
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealingAction:
    """Record of a healing action taken by the engine."""
    timestamp: str
    company_id: str
    variant: str
    condition_type: str
    action_type: str
    details: Dict[str, Any] = field(default_factory=dict)
    status: str = HealingStatus.TRIGGERED.value
    rule_id: str = ""


@dataclass
class ProviderState:
    """Per-provider healing state within a variant."""
    provider: str
    model_id: str
    tier: str
    status: str = "healthy"  # healthy, degraded, disabled, recovering
    consecutive_failures: int = 0
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    traffic_percentage: int = 100  # 0-100
    disabled_at: Optional[str] = None
    disabled_reason: str = ""
    recovery_stage: int = 0  # 0=full, 1=10%, 2=25%, 3=50%, 4=100%
    last_recovery_attempt: Optional[str] = None


@dataclass
class ThresholdAdjustment:
    """Record of a confidence threshold adjustment."""
    original_threshold: float
    current_threshold: float
    adjusted_at: str
    reason: str
    low_score_count: int = 0


@dataclass
class VariantHealingState:
    """Complete healing state for one variant within a company."""
    variant: str
    provider_states: Dict[str, ProviderState] = field(default_factory=dict)
    threshold_adjustments: Dict[str, ThresholdAdjustment] = field(
        default_factory=dict,
    )
    consecutive_low_scores: int = 0
    consecutive_high_scores: int = 0
    error_window: List[Dict[str, Any]] = field(default_factory=list)
    latency_window: List[float] = field(default_factory=list)
    last_error_check: Optional[str] = None
    last_latency_check: Optional[str] = None
    last_confidence_check: Optional[str] = None
    active_healings: List[str] = field(default_factory=list)


@dataclass
class VariantHealthSummary:
    """Health summary for one variant."""
    variant: str
    healthy: bool = True
    issues: List[str] = field(default_factory=list)
    active_healings: int = 0
    provider_status: Dict[str, str] = field(default_factory=dict)
    threshold_current: float = 85.0
    threshold_original: float = 85.0


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════


# Default confidence thresholds per variant
_VARIANT_THRESHOLDS: Dict[str, float] = {
    "mini_parwa": 95.0,
    "parwa": 85.0,
    "high_parwa": 75.0,
}

# Minimum floor thresholds (never adjust below these)
_VARIANT_FLOOR: Dict[str, float] = {
    "mini_parwa": 80.0,
    "parwa": 70.0,
    "high_parwa": 60.0,
}

# Default recovery traffic percentages per stage
_RECOVERY_STAGES: List[int] = [10, 25, 50, 100]

# Known providers per tier
_TIER_PROVIDERS: Dict[str, List[str]] = {
    "light": ["cerebras", "groq", "google"],
    "medium": ["google", "cerebras", "groq"],
    "heavy": ["google", "cerebras", "groq"],
}

# Window sizes for rolling analysis
_ERROR_WINDOW_SIZE = 100
_LATENCY_WINDOW_SIZE = 100

# Thresholds for healing triggers
_CONSECUTIVE_FAILURE_LIMIT = 5
_ERROR_SPIKE_THRESHOLD = 0.20  # 20% jump
_LATENCY_SPIKE_MULTIPLIER = 3.0
_LOW_SCORE_CONSECUTIVE = 10
_RECOVERY_HIGH_SCORE_CONSECUTIVE = 20
_RECOVERY_COOLDOWN_SECONDS = 600  # 10 min between recovery attempts
_LATENCY_RECOVERY_SECONDS = 600  # 10 min of normal latency before switch back

_MAX_HEALING_HISTORY = 100


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _now_utc() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str) -> Optional[datetime]:
    """Parse an ISO timestamp string, returning None on failure."""
    if not ts:
        return None
    try:
        ts_clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_clean)
    except (ValueError, TypeError):
        return None


def _seconds_since(ts: str) -> float:
    """Return seconds elapsed since a timestamp, or infinity if invalid."""
    parsed = _parse_iso(ts)
    if parsed is None:
        return float("inf")
    return (datetime.now(timezone.utc) - parsed).total_seconds()


def _default_threshold(variant: str) -> float:
    """Get the default confidence threshold for a variant."""
    return _VARIANT_THRESHOLDS.get(variant, 85.0)


def _floor_threshold(variant: str) -> float:
    """Get the minimum floor threshold for a variant."""
    return _VARIANT_FLOOR.get(variant, 70.0)


def _provider_key(provider: str, model_id: str) -> str:
    """Generate a unique key for a provider+model combo."""
    return f"{provider}:{model_id}"


# ══════════════════════════════════════════════════════════════════
# MAIN SERVICE
# ══════════════════════════════════════════════════════════════════


class SelfHealingEngine:
    """AI Self-Healing Engine (SG-20).

    Monitors AI engine health and autonomously takes corrective
    actions when anomalies are detected. Each variant has
    independent healing state.

    BC-001: company_id first parameter.
    BC-008: Never crash.
    BC-012: All timestamps UTC.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

        # company_id -> variant -> VariantHealingState
        self._state: Dict[str, Dict[str, VariantHealingState]] = (
            defaultdict(dict)
        )

        # company_id -> list of HealingAction (audit trail)
        self._history: Dict[str, List[HealingAction]] = defaultdict(list)

        # company_id -> list of enabled HealingRules
        self._rules: Dict[str, List[HealingRule]] = {}

        # Initialise default rules
        self._init_default_rules()

    # ── Reset ──────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear all healing state and history. For testing."""
        with self._lock:
            self._state.clear()
            self._history.clear()
            self._rules.clear()
            self._init_default_rules()

    # ── Default Rules ──────────────────────────────────────────

    def _init_default_rules(self) -> None:
        """Create built-in healing rules."""
        self._default_rules = [
            HealingRule(
                rule_id="consecutive_failures_disable",
                condition_type=ConditionType.CONSECUTIVE_FAILURES.value,
                action_type=ActionType.PROVIDER_DISABLE.value,
                priority=10,
                cooldown_seconds=300,
                params={"failure_limit": _CONSECUTIVE_FAILURE_LIMIT},
            ),
            HealingRule(
                rule_id="error_spike_disable",
                condition_type=ConditionType.ERROR_SPIKE.value,
                action_type=ActionType.PROVIDER_DISABLE.value,
                priority=9,
                cooldown_seconds=300,
                params={"spike_threshold": _ERROR_SPIKE_THRESHOLD},
            ),
            HealingRule(
                rule_id="latency_spike_switch",
                condition_type=ConditionType.LATENCY_SPIKE.value,
                action_type=ActionType.PROVIDER_SWITCH.value,
                priority=7,
                cooldown_seconds=600,
                params={
                    "multiplier": _LATENCY_SPIKE_MULTIPLIER,
                    "recovery_seconds": _LATENCY_RECOVERY_SECONDS,
                },
            ),
            HealingRule(
                rule_id="confidence_drop_lower",
                condition_type=ConditionType.CONFIDENCE_DROP.value,
                action_type=ActionType.THRESHOLD_LOWER.value,
                priority=6,
                cooldown_seconds=300,
                params={"drop_by": 5.0},
            ),
            HealingRule(
                rule_id="rate_limit_switch",
                condition_type=ConditionType.RATE_LIMIT_HIT.value,
                action_type=ActionType.PROVIDER_SWITCH.value,
                priority=8,
                cooldown_seconds=300,
            ),
            HealingRule(
                rule_id="provider_unhealthy_disable",
                condition_type=ConditionType.PROVIDER_UNHEALTHY.value,
                action_type=ActionType.PROVIDER_DISABLE.value,
                priority=10,
                cooldown_seconds=300,
            ),
        ]

    # ── Or Get / Manage Rules ──────────────────────────────────

    def get_rules(
        self, company_id: str,
    ) -> List[HealingRule]:
        """Get healing rules for a company. Returns defaults if none set."""
        try:
            with self._lock:
                rules = self._rules.get(company_id)
                if rules is None:
                    return list(self._default_rules)
                return list(rules)
        except Exception:
            logger.exception(
                "self_healing_get_rules_failed company_id=%s",
                company_id,
            )
            return list(self._default_rules)

    def set_rules(
        self, company_id: str, rules: List[HealingRule],
    ) -> None:
        """Set custom healing rules for a company."""
        try:
            with self._lock:
                self._rules[company_id] = list(rules)
        except Exception:
            logger.exception(
                "self_healing_set_rules_failed company_id=%s",
                company_id,
            )

    def enable_rule(
        self, company_id: str, rule_id: str, enabled: bool = True,
    ) -> bool:
        """Enable or disable a specific healing rule."""
        try:
            with self._lock:
                rules = self._rules.get(company_id)
                if rules is None:
                    import copy as _copy
                    rules = _copy.deepcopy(self._default_rules)
                    self._rules[company_id] = rules
                for rule in rules:
                    if rule.rule_id == rule_id:
                        rule.enabled = enabled
                        return True
            return False
        except Exception:
            logger.exception(
                "self_healing_enable_rule_failed company_id=%s",
                company_id,
            )
            return False

    # ── Record Query Result (Master Input Method) ──────────────

    def record_query_result(
        self,
        company_id: str,
        variant_type: str,
        provider: str,
        model_id: str,
        tier: str,
        confidence_score: float,
        latency_ms: float,
        error: Optional[str] = None,
    ) -> List[HealingAction]:
        """Record a query result and check if healing is needed.

        This is the main input method. Call it after each query
        completes. It updates internal state and triggers healing
        actions if conditions are met.

        Returns a list of healing actions taken (may be empty).
        """
        try:
            with self._lock:
                state = self._get_or_create_variant_state(
                    company_id, variant_type,
                )
                pkey = _provider_key(provider, model_id)
                now = _now_utc()

                # Update provider state
                if pkey not in state.provider_states:
                    state.provider_states[pkey] = ProviderState(
                        provider=provider,
                        model_id=model_id,
                        tier=tier,
                    )

                ps = state.provider_states[pkey]

                if error is None:
                    # Success
                    ps.consecutive_failures = 0
                    ps.last_success = now
                    state.error_window.append(
                        {"timestamp": now, "error": False},
                    )
                    state.latency_window.append(latency_ms)

                    # Check for recovery (disabled or recovering)
                    if ps.status in ("disabled", "recovering"):
                        self._attempt_recovery(
                            company_id, variant_type, pkey,
                        )
                else:
                    # Failure
                    ps.consecutive_failures += 1
                    ps.last_failure = now
                    state.error_window.append(
                        {"timestamp": now, "error": True, "type": error},
                    )

                # Confidence tracking
                default_thresh = _default_threshold(variant_type)
                if confidence_score < default_thresh:
                    state.consecutive_low_scores += 1
                    state.consecutive_high_scores = 0
                else:
                    state.consecutive_high_scores += 1
                    state.consecutive_low_scores = 0

                # Prune windows
                if len(state.error_window) > _ERROR_WINDOW_SIZE:
                    state.error_window = state.error_window[
                        -_ERROR_WINDOW_SIZE:
                    ]
                if len(state.latency_window) > _LATENCY_WINDOW_SIZE:
                    state.latency_window = state.latency_window[
                        -_LATENCY_WINDOW_SIZE:
                    ]

            # Run healing checks (outside lock for safety)
            return self._run_healing_checks(
                company_id, variant_type, provider, model_id, tier,
                confidence_score, error,
            )

        except Exception:
            logger.exception(
                "self_healing_record_query_failed company_id=%s",
                company_id,
            )
            return []

    # ── Healing Checks ─────────────────────────────────────────

    def _run_healing_checks(
        self,
        company_id: str,
        variant_type: str,
        provider: str,
        model_id: str,
        tier: str,
        confidence_score: float,
        error: Optional[str],
    ) -> List[HealingAction]:
        """Run all healing checks and return actions taken."""
        actions: List[HealingAction] = []
        rules = self.get_rules(company_id)
        enabled_rules = [r for r in rules if r.enabled]

        with self._lock:
            state = self._get_or_create_variant_state(
                company_id, variant_type,
            )

        for rule in enabled_rules:
            try:
                action = self._check_rule(
                    company_id, variant_type, rule,
                    provider, model_id, tier, confidence_score, error,
                )
                if action is not None:
                    actions.append(action)
                    self._record_action(company_id, action)
            except Exception:
                logger.exception(
                    "self_healing_rule_check_failed rule_id=%s "
                    "company_id=%s", rule.rule_id, company_id,
                )

        return actions

    def _check_rule(
        self,
        company_id: str,
        variant_type: str,
        rule: HealingRule,
        provider: str,
        model_id: str,
        tier: str,
        confidence_score: float,
        error: Optional[str],
    ) -> Optional[HealingAction]:
        """Check a single healing rule and return action if triggered."""
        # Confidence recovery bypasses cooldown: if we have enough
        # consecutive high scores and a lowered threshold, restore it.
        if rule.condition_type == ConditionType.CONFIDENCE_DROP.value:
            with self._lock:
                state = self._get_or_create_variant_state(
                    company_id, variant_type,
                )
                if (state.consecutive_high_scores
                        >= _RECOVERY_HIGH_SCORE_CONSECUTIVE
                        and variant_type
                        in state.threshold_adjustments):
                    default_thresh = _default_threshold(variant_type)
                    state.threshold_adjustments.pop(variant_type)
                    return HealingAction(
                        timestamp=_now_utc(),
                        company_id=company_id,
                        variant=variant_type,
                        condition_type=(
                            ConditionType.CONFIDENCE_DROP.value
                        ),
                        action_type=(
                            ActionType.THRESHOLD_RESTORE.value
                        ),
                        details={
                            "variant": variant_type,
                            "new_threshold": default_thresh,
                            "reason": (
                                f"Restored to {default_thresh} after "
                                f"{state.consecutive_high_scores} "
                                "consecutive high scores"
                            ),
                            "consecutive_high_scores": (
                                state.consecutive_high_scores
                            ),
                        },
                        status=HealingStatus.COMPLETED.value,
                        rule_id=rule.rule_id,
                    )

        # Cooldown check
        last_action = self._get_last_action_for_rule(
            company_id, rule.rule_id,
        )
        if last_action is not None:
            if _seconds_since(last_action.timestamp) < rule.cooldown_seconds:
                return None

        with self._lock:
            state = self._get_or_create_variant_state(
                company_id, variant_type,
            )
            pkey = _provider_key(provider, model_id)
            ps = state.provider_states.get(pkey)

        # ── Consecutive Failures ───────────────────────────
        if rule.condition_type == ConditionType.CONSECUTIVE_FAILURES.value:
            if ps and ps.consecutive_failures >= rule.params.get(
                "failure_limit", _CONSECUTIVE_FAILURE_LIMIT,
            ):
                return self._action_disable_provider(
                    company_id, variant_type, pkey,
                    ps, f"Consecutive failures: {ps.consecutive_failures}",
                    rule.rule_id,
                )

        # ── Error Spike ───────────────────────────────────
        elif rule.condition_type == ConditionType.ERROR_SPIKE.value:
            spike = self._detect_error_spike(state, rule)
            if spike:
                if ps:
                    return self._action_disable_provider(
                        company_id, variant_type, pkey,
                        ps,
                        f"Error spike detected: {spike:.1%}",
                        rule.rule_id,
                    )

        # ── Latency Spike ─────────────────────────────────
        elif rule.condition_type == ConditionType.LATENCY_SPIKE.value:
            latency_info = self._detect_latency_spike(state, rule)
            if latency_info is not None:
                baseline_avg, current_p90 = latency_info
                multiplier = rule.params.get(
                    "multiplier", _LATENCY_SPIKE_MULTIPLIER,
                )
                if ps and ps.status not in ("disabled",):
                    return HealingAction(
                        timestamp=_now_utc(),
                        company_id=company_id,
                        variant=variant_type,
                        condition_type=ConditionType.LATENCY_SPIKE.value,
                        action_type=ActionType.PROVIDER_SWITCH.value,
                        details={
                            "provider": provider,
                            "model_id": model_id,
                            "baseline_avg": baseline_avg,
                            "current_p90": current_p90,
                            "multiplier": multiplier,
                            "message": (
                                f"P90 latency {current_p90:.0f}ms "
                                f"> {multiplier}x baseline "
                                f"{baseline_avg:.0f}ms"
                            ),
                        },
                        status=HealingStatus.TRIGGERED.value,
                        rule_id=rule.rule_id,
                    )

        # ── Confidence Drop ───────────────────────────────
        elif rule.condition_type == ConditionType.CONFIDENCE_DROP.value:
            threshold_info = self._check_confidence_drop(
                variant_type, state, rule,
            )
            if threshold_info is not None:
                new_thresh, reason = threshold_info
                return HealingAction(
                    timestamp=_now_utc(),
                    company_id=company_id,
                    variant=variant_type,
                    condition_type=ConditionType.CONFIDENCE_DROP.value,
                    action_type=ActionType.THRESHOLD_LOWER.value,
                    details={
                        "variant": variant_type,
                        "new_threshold": new_thresh,
                        "reason": reason,
                        "consecutive_low_scores": (
                            state.consecutive_low_scores
                        ),
                    },
                    status=HealingStatus.TRIGGERED.value,
                    rule_id=rule.rule_id,
                )

        # ── Rate Limit ────────────────────────────────────
        elif rule.condition_type == ConditionType.RATE_LIMIT_HIT.value:
            if error and "rate_limit" in error.lower():
                if ps and ps.status not in ("disabled",):
                    return HealingAction(
                        timestamp=_now_utc(),
                        company_id=company_id,
                        variant=variant_type,
                        condition_type=ConditionType.RATE_LIMIT_HIT.value,
                        action_type=ActionType.PROVIDER_SWITCH.value,
                        details={
                            "provider": provider,
                            "model_id": model_id,
                            "message": f"Rate limit hit on {provider}",
                        },
                        status=HealingStatus.TRIGGERED.value,
                        rule_id=rule.rule_id,
                    )

        # ── Provider Unhealthy ────────────────────────────
        elif (rule.condition_type
              == ConditionType.PROVIDER_UNHEALTHY.value):
            if ps and ps.status == "unhealthy":
                return self._action_disable_provider(
                    company_id, variant_type, pkey,
                    ps, "Provider reported unhealthy",
                    rule.rule_id,
                )

        return None

    # ── Detection Helpers ──────────────────────────────────────

    def _detect_error_spike(
        self,
        state: VariantHealingState,
        rule: HealingRule,
    ) -> Optional[float]:
        """Detect if error rate has spiked compared to previous window.

        Returns the current error rate if spike detected, else None.
        """
        window = state.error_window
        if len(window) < 20:
            return None

        half = len(window) // 2
        prev_window = window[:half]
        curr_window = window[half:]

        prev_errors = sum(1 for e in prev_window if e.get("error"))
        curr_errors = sum(1 for e in curr_window if e.get("error"))

        prev_rate = prev_errors / len(prev_window) if prev_window else 0
        curr_rate = curr_errors / len(curr_window) if curr_window else 0

        spike_threshold = rule.params.get(
            "spike_threshold", _ERROR_SPIKE_THRESHOLD,
        )

        if prev_rate > 0 and curr_rate > 0:
            jump = curr_rate - prev_rate
            if jump >= spike_threshold:
                return curr_rate
        elif curr_rate >= spike_threshold and prev_rate == 0:
            return curr_rate

        return None

    def _detect_latency_spike(
        self,
        state: VariantHealingState,
        rule: HealingRule,
    ) -> Optional[Tuple[float, float]]:
        """Detect if P90 latency has spiked.

        Returns (baseline_avg, current_p90) if spike detected, else None.
        """
        window = state.latency_window
        if len(window) < 20:
            return None

        half = len(window) // 2
        baseline = window[:half]
        current = window[half:]

        if not baseline or not current:
            return None

        import math
        baseline_avg = sum(baseline) / len(baseline)
        sorted_curr = sorted(current)
        p90_idx = int(math.ceil(0.9 * len(sorted_curr))) - 1
        p90_idx = max(0, min(p90_idx, len(sorted_curr) - 1))
        current_p90 = sorted_curr[p90_idx]

        multiplier = rule.params.get(
            "multiplier", _LATENCY_SPIKE_MULTIPLIER,
        )
        threshold = baseline_avg * multiplier

        if baseline_avg > 0 and current_p90 > threshold:
            return (baseline_avg, current_p90)

        return None

    def _check_confidence_drop(
        self,
        variant_type: str,
        state: VariantHealingState,
        rule: HealingRule,
    ) -> Optional[Tuple[float, str]]:
        """Check if confidence has dropped and threshold should lower.

        Returns (new_threshold, reason) if adjustment needed, else None.
        """
        default_thresh = _default_threshold(variant_type)
        floor = _floor_threshold(variant_type)

        # Get current adjusted threshold
        adj_key = variant_type
        if adj_key in state.threshold_adjustments:
            current_thresh = (
                state.threshold_adjustments[adj_key].current_threshold
            )
        else:
            current_thresh = default_thresh

        drop_by = rule.params.get("drop_by", 5.0)

        with self._lock:
            if state.consecutive_low_scores >= _LOW_SCORE_CONSECUTIVE:
                new_thresh = current_thresh - drop_by
                if new_thresh < floor:
                    new_thresh = floor
                if new_thresh >= current_thresh:
                    return None  # Already at or below adjustment

                state.threshold_adjustments[adj_key] = ThresholdAdjustment(
                    original_threshold=default_thresh,
                    current_threshold=new_thresh,
                    adjusted_at=_now_utc(),
                    reason=(
                        "Consecutive low scores: "
                        f"{state.consecutive_low_scores}"
                    ),
                    low_score_count=state.consecutive_low_scores,
                )
                return (
                    new_thresh,
                    f"Lowered from {current_thresh} to {new_thresh} "
                    f"(floor: {floor})",
                )

            # Check for recovery
            if (
                state.consecutive_high_scores >= _RECOVERY_HIGH_SCORE_CONSECUTIVE
                and adj_key in state.threshold_adjustments
            ):
                state.threshold_adjustments.pop(adj_key)
                return (
                    default_thresh,
                    f"Restored to {default_thresh} after "
                    f"{state.consecutive_high_scores} consecutive high scores",
                )

        return None

    # ── Action Helpers ─────────────────────────────────────────

    def _action_disable_provider(
        self,
        company_id: str,
        variant_type: str,
        pkey: str,
        ps: ProviderState,
        reason: str,
        rule_id: str,
    ) -> HealingAction:
        """Create a disable-provider healing action."""
        with self._lock:
            ps.status = "disabled"
            ps.disabled_at = _now_utc()
            ps.disabled_reason = reason
            ps.traffic_percentage = 0
            ps.recovery_stage = 0

        return HealingAction(
            timestamp=_now_utc(),
            company_id=company_id,
            variant=variant_type,
            condition_type="provider_issue",
            action_type=ActionType.PROVIDER_DISABLE.value,
            details={
                "provider": ps.provider,
                "model_id": ps.model_id,
                "reason": reason,
                "consecutive_failures": ps.consecutive_failures,
            },
            status=HealingStatus.TRIGGERED.value,
            rule_id=rule_id,
        )

    def _attempt_recovery(
        self,
        company_id: str,
        variant_type: str,
        pkey: str,
    ) -> Optional[HealingAction]:
        """Attempt to recover a disabled/failing provider."""
        state = self._get_or_create_variant_state(
            company_id, variant_type,
        )
        ps = state.provider_states.get(pkey)
        if ps is None:
            return None

        if ps.status not in ("disabled", "recovering"):
            return None

        # Check cooldown between recovery attempts
        if (ps.last_recovery_attempt is not None
                and _seconds_since(ps.last_recovery_attempt)
                < _RECOVERY_COOLDOWN_SECONDS):
            return None

        with self._lock:
            ps.status = "recovering"
            ps.recovery_stage += 1
            ps.last_recovery_attempt = _now_utc()

            if ps.recovery_stage >= len(_RECOVERY_STAGES):
                # Full recovery
                ps.status = "healthy"
                ps.traffic_percentage = 100
                ps.recovery_stage = 0
                ps.disabled_at = None
                ps.disabled_reason = ""

                action = HealingAction(
                    timestamp=_now_utc(),
                    company_id=company_id,
                    variant=variant_type,
                    condition_type="recovery",
                    action_type=ActionType.PROVIDER_ENABLE.value,
                    details={
                        "provider": ps.provider,
                        "model_id": ps.model_id,
                        "traffic_percentage": 100,
                        "message": "Full recovery achieved",
                    },
                    status=HealingStatus.COMPLETED.value,
                    rule_id="recovery",
                )
                self._record_action(company_id, action)
                return action

            traffic = _RECOVERY_STAGES[ps.recovery_stage - 1]
            ps.traffic_percentage = traffic

            action = HealingAction(
                timestamp=_now_utc(),
                company_id=company_id,
                variant=variant_type,
                condition_type="recovery",
                action_type=ActionType.TRAFFIC_RAMP_UP.value,
                details={
                    "provider": ps.provider,
                    "model_id": ps.model_id,
                    "recovery_stage": ps.recovery_stage,
                    "traffic_percentage": traffic,
                    "message": (
                        f"Ramping up traffic to {traffic}% "
                        f"(stage {ps.recovery_stage}/{len(_RECOVERY_STAGES)})"
                    ),
                },
                status=HealingStatus.IN_PROGRESS.value,
                rule_id="recovery",
            )
            self._record_action(company_id, action)
            return action

    # ── Internal State Management ──────────────────────────────

    def _get_or_create_variant_state(
        self, company_id: str, variant_type: str,
    ) -> VariantHealingState:
        """Get or create healing state for a variant."""
        if variant_type not in self._state[company_id]:
            self._state[company_id][variant_type] = VariantHealingState(
                variant=variant_type,
            )
        return self._state[company_id][variant_type]

    def _record_action(
        self, company_id: str, action: HealingAction,
    ) -> None:
        """Record a healing action in the audit trail."""
        with self._lock:
            history = self._history[company_id]
            history.append(action)
            if len(history) > _MAX_HEALING_HISTORY:
                self._history[company_id] = history[-_MAX_HEALING_HISTORY:]

    def _get_last_action_for_rule(
        self, company_id: str, rule_id: str,
    ) -> Optional[HealingAction]:
        """Get the most recent action for a specific rule."""
        history = self._history.get(company_id, [])
        for action in reversed(history):
            if action.rule_id == rule_id:
                return action
        return None

    # ── Public Query Methods ───────────────────────────────────

    def get_healing_history(
        self, company_id: str,
    ) -> List[HealingAction]:
        """Get the healing action audit trail for a company."""
        try:
            with self._lock:
                return list(self._history.get(company_id, []))
        except Exception:
            logger.exception(
                "self_healing_get_history_failed company_id=%s",
                company_id,
            )
            return []

    def get_active_healings(
        self, company_id: str,
    ) -> List[HealingAction]:
        """Get currently active healing processes."""
        try:
            with self._lock:
                all_actions = self._history.get(company_id, [])
                active = [
                    a for a in all_actions
                    if a.status in (
                        HealingStatus.TRIGGERED.value,
                        HealingStatus.IN_PROGRESS.value,
                    )
                ]
                return list(active)
        except Exception:
            logger.exception(
                "self_healing_get_active_failed company_id=%s",
                company_id,
            )
            return []

    def get_variant_health(
        self, company_id: str,
    ) -> List[VariantHealthSummary]:
        """Get per-variant health summary."""
        try:
            summaries: List[VariantHealthSummary] = []
            with self._lock:
                company_state = self._state.get(company_id, {})

                for variant, vstate in company_state.items():
                    default_thresh = _default_threshold(variant)
                    current_thresh = default_thresh

                    # Check for threshold adjustment
                    if variant in vstate.threshold_adjustments:
                        current_thresh = (
                            vstate.threshold_adjustments[
                                variant
                            ].current_threshold
                        )

                    issues: List[str] = []
                    provider_status: Dict[str, str] = {}

                    for pkey, ps in vstate.provider_states.items():
                        provider_status[pkey] = ps.status
                        if ps.status in ("disabled", "unhealthy"):
                            issues.append(
                                f"{pkey}: {ps.status} "
                                f"({ps.disabled_reason or 'unknown'})"
                            )
                        if ps.consecutive_failures > 0:
                            issues.append(
                                f"{pkey}: "
                                f"{ps.consecutive_failures} "
                                "consecutive failures"
                            )

                    if vstate.consecutive_low_scores > 3:
                        issues.append(
                            "Low confidence: "
                            f"{vstate.consecutive_low_scores} "
                            "consecutive low scores"
                        )

                    active = [
                        a for a in self._history.get(company_id, [])
                        if (a.variant == variant
                            and a.status in (
                                HealingStatus.TRIGGERED.value,
                                HealingStatus.IN_PROGRESS.value,
                            ))
                    ]

                    summaries.append(VariantHealthSummary(
                        variant=variant,
                        healthy=len(issues) == 0,
                        issues=issues,
                        active_healings=len(active),
                        provider_status=provider_status,
                        threshold_current=current_thresh,
                        threshold_original=default_thresh,
                    ))

            return summaries
        except Exception:
            logger.exception(
                "self_healing_variant_health_failed company_id=%s",
                company_id,
            )
            return []

    def get_system_health(self) -> Dict[str, Any]:
        """Get global health across all companies (admin view)."""
        try:
            total_companies = 0
            total_healings = 0
            company_summaries: Dict[str, Any] = {}

            with self._lock:
                for company_id, company_state in self._state.items():
                    total_companies += 1
                    healings = len(self._history.get(company_id, []))
                    total_healings += healings

                    variant_health = []
                    for variant, vstate in company_state.items():
                        disabled_count = sum(
                            1 for ps in vstate.provider_states.values()
                            if ps.status in ("disabled", "unhealthy")
                        )
                        variant_health.append({
                            "variant": variant,
                            "disabled_providers": disabled_count,
                            "total_providers": len(
                                vstate.provider_states,
                            ),
                            "low_score_streak": (
                                vstate.consecutive_low_scores
                            ),
                        })

                    company_summaries[company_id] = {
                        "variants": variant_health,
                        "total_healings": healings,
                    }

            return {
                "total_companies": total_companies,
                "total_healings": total_healings,
                "companies": company_summaries,
                "timestamp": _now_utc(),
            }
        except Exception:
            logger.exception("self_healing_system_health_failed")
            return {
                "total_companies": 0,
                "total_healings": 0,
                "companies": {},
                "timestamp": _now_utc(),
            }

    def get_current_threshold(
        self, company_id: str, variant_type: str,
    ) -> float:
        """Get the current (possibly adjusted) threshold for a variant."""
        try:
            with self._lock:
                state = self._get_or_create_variant_state(
                    company_id, variant_type,
                )
                if variant_type in state.threshold_adjustments:
                    return (
                        state.threshold_adjustments[
                            variant_type
                        ].current_threshold
                    )
                return _default_threshold(variant_type)
        except Exception:
            logger.exception(
                "self_healing_get_threshold_failed company_id=%s",
                company_id,
            )
            return _default_threshold(variant_type)

    def get_provider_state(
        self,
        company_id: str,
        variant_type: str,
        provider: str,
        model_id: str,
    ) -> Optional[ProviderState]:
        """Get the healing state for a specific provider+model."""
        try:
            with self._lock:
                state = self._get_or_create_variant_state(
                    company_id, variant_type,
                )
                pkey = _provider_key(provider, model_id)
                return state.provider_states.get(pkey)
        except Exception:
            logger.exception(
                "self_healing_get_provider_state_failed company_id=%s",
                company_id,
            )
            return None

    def manually_enable_provider(
        self,
        company_id: str,
        variant_type: str,
        provider: str,
        model_id: str,
    ) -> bool:
        """Manually re-enable a disabled provider."""
        try:
            with self._lock:
                state = self._get_or_create_variant_state(
                    company_id, variant_type,
                )
                pkey = _provider_key(provider, model_id)
                ps = state.provider_states.get(pkey)
                if ps is None:
                    return False
                ps.status = "healthy"
                ps.traffic_percentage = 100
                ps.recovery_stage = 0
                ps.disabled_at = None
                ps.disabled_reason = ""
                ps.consecutive_failures = 0

                action = HealingAction(
                    timestamp=_now_utc(),
                    company_id=company_id,
                    variant=variant_type,
                    condition_type="manual",
                    action_type=ActionType.PROVIDER_ENABLE.value,
                    details={
                        "provider": provider,
                        "model_id": model_id,
                        "message": "Manually re-enabled by admin",
                    },
                    status=HealingStatus.COMPLETED.value,
                    rule_id="manual",
                )
                self._record_action(company_id, action)
            return True
        except Exception:
            logger.exception(
                "self_healing_manual_enable_failed company_id=%s",
                company_id,
            )
            return False

    def manually_disable_provider(
        self,
        company_id: str,
        variant_type: str,
        provider: str,
        model_id: str,
        reason: str = "manual_disable",
    ) -> bool:
        """Manually disable a provider."""
        try:
            with self._lock:
                state = self._get_or_create_variant_state(
                    company_id, variant_type,
                )
                pkey = _provider_key(provider, model_id)
                if pkey not in state.provider_states:
                    state.provider_states[pkey] = ProviderState(
                        provider=provider,
                        model_id=model_id,
                        tier="unknown",
                    )
                ps = state.provider_states[pkey]
                ps.status = "disabled"
                ps.disabled_at = _now_utc()
                ps.disabled_reason = reason
                ps.traffic_percentage = 0
                ps.recovery_stage = 0

                action = HealingAction(
                    timestamp=_now_utc(),
                    company_id=company_id,
                    variant=variant_type,
                    condition_type="manual",
                    action_type=ActionType.PROVIDER_DISABLE.value,
                    details={
                        "provider": provider,
                        "model_id": model_id,
                        "reason": reason,
                    },
                    status=HealingStatus.COMPLETED.value,
                    rule_id="manual",
                )
                self._record_action(company_id, action)
            return True
        except Exception:
            logger.exception(
                "self_healing_manual_disable_failed company_id=%s",
                company_id,
            )
            return False

    def record_provider_status(
        self,
        company_id: str,
        variant_type: str,
        provider: str,
        model_id: str,
        status: str,
    ) -> None:
        """Record an external provider status update."""
        try:
            with self._lock:
                state = self._get_or_create_variant_state(
                    company_id, variant_type,
                )
                pkey = _provider_key(provider, model_id)
                if pkey not in state.provider_states:
                    state.provider_states[pkey] = ProviderState(
                        provider=provider,
                        model_id=model_id,
                        tier="unknown",
                    )
                state.provider_states[pkey].status = status
        except Exception:
            logger.exception(
                "self_healing_record_status_failed company_id=%s",
                company_id,
            )
