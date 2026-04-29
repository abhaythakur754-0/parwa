"""
Graceful Escalation Framework (Week 10 Day 5)

Provides a unified escalation system that bridges partial failure
handling, GSD engine escalation, collision detection, and session
monitoring. Manages escalation rules, cooldowns, rate limiting,
notification channels, and resolution tracking.

Core Responsibilities:
- Evaluate escalation triggers with configurable rules
- Manage escalation cooldowns (per company, per ticket)
- Rate limiting (per hour limits per company)
- Multi-channel notification support
- Escalation lifecycle management (create → acknowledge → resolve)
- Severity-based priority ordering
- VIP customer fast-track escalation
- Auto-resolution for stale escalations
- Escalation analytics and statistics

Building Codes: BC-001, BC-008, BC-012
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("graceful_escalation")


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class EscalationTrigger(str, Enum):
    """What triggered the escalation.

    Attributes:
        HIGH_FRUSTRATION: Customer frustration score exceeded threshold.
        LEGAL_SENSITIVE: Legal or regulatory topic detected.
        MULTIPLE_FAILURES: Pipeline failures exceeded threshold.
        COLLISION_CONFLICT: Concurrent agent collision detected.
        STALE_SESSION: Session has been idle too long.
        TIMEOUT: Operation timed out.
        CONFIDENCE_LOW: AI confidence below acceptable threshold.
        VIP_CUSTOMER: VIP customer requesting priority handling.
        MANUAL_REQUEST: Human agent or supervisor requested escalation.
        LOOP_DETECTED: Conversation stuck in a repetitive loop.
        CAPACITY_OVERFLOW: System capacity exceeded.
        PARTIAL_FAILURE_CRITICAL: Critical partial failure in pipeline.
    """
    HIGH_FRUSTRATION = "high_frustration"
    LEGAL_SENSITIVE = "legal_sensitive"
    MULTIPLE_FAILURES = "multiple_failures"
    COLLISION_CONFLICT = "collision_conflict"
    STALE_SESSION = "stale_session"
    TIMEOUT = "timeout"
    CONFIDENCE_LOW = "confidence_low"
    VIP_CUSTOMER = "vip_customer"
    MANUAL_REQUEST = "manual_request"
    LOOP_DETECTED = "loop_detected"
    CAPACITY_OVERFLOW = "capacity_overflow"
    PARTIAL_FAILURE_CRITICAL = "partial_failure_critical"


class EscalationSeverity(str, Enum):
    """Severity of escalation.

    Attributes:
        LOW: Informational, can be handled async.
        MEDIUM: Needs attention within SLA.
        HIGH: Urgent, immediate attention required.
        CRITICAL: System issue, page on-call.
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EscalationChannel(str, Enum):
    """Channel for escalation notification.

    Attributes:
        IN_APP: In-app notification to dashboard.
        EMAIL: Email notification.
        WEBHOOK: External webhook callback.
        SLACK: Slack message notification.
        SMS: SMS text message.
        PAGERDUTY: PagerDuty alert.
    """
    IN_APP = "in_app"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    SMS = "sms"
    PAGERDUTY = "pagerduty"


class EscalationOutcome(str, Enum):
    """Resolution outcome of an escalation.

    Attributes:
        RESOLVED: Escalation was resolved normally.
        HUMAN_TOOK_OVER: A human agent took over the conversation.
        AUTO_RESOLVED: Escalation was auto-resolved (stale or resolved).
        DISMISSED: Escalation was dismissed as not needed.
        EXPIRED: Escalation expired without action.
        REASSIGNED: Escalation was reassigned to another agent/team.
    """
    RESOLVED = "resolved"
    HUMAN_TOOK_OVER = "human_took_over"
    AUTO_RESOLVED = "auto_resolved"
    DISMISSED = "dismissed"
    EXPIRED = "expired"
    REASSIGNED = "reassigned"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class EscalationContext:
    """Context surrounding an escalation event.

    Provides all relevant information for evaluating whether an
    escalation should occur, at what severity, and through which
    channel.

    Attributes:
        company_id: Tenant company identifier (BC-001).
        ticket_id: Support ticket being processed.
        trigger: EscalationTrigger value identifying the cause.
        severity: EscalationSeverity value (may be overridden by rules).
        description: Human-readable description of the escalation reason.
        gsd_state: Current GSD state if applicable.
        variant: PARWA variant (mini_parwa, parwa, high_parwa).
        agent_id: ID of the AI agent that detected the issue.
        frustration_score: Current customer frustration (0-100).
        confidence_score: Current AI confidence (0.0-1.0).
        failure_count: Number of pipeline failures encountered.
        customer_tier: Customer tier (free, pro, enterprise, vip).
        conversation_turns: Number of turns in the conversation.
        metadata: Arbitrary additional context data.
    """
    company_id: str
    ticket_id: str
    trigger: str
    severity: str
    description: str
    gsd_state: str = ""
    variant: str = "parwa"
    agent_id: str = ""
    frustration_score: float = 0.0
    confidence_score: float = 0.0
    failure_count: int = 0
    customer_tier: str = ""
    conversation_turns: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EscalationRecord:
    """Record of an escalation event.

    Tracks the full lifecycle of an escalation from creation through
    acknowledgment and resolution.

    Attributes:
        escalation_id: Unique identifier for this escalation.
        company_id: Tenant company identifier (BC-001).
        ticket_id: Associated support ticket.
        trigger: What triggered the escalation.
        severity: Escalation severity level.
        channel: Notification channel used.
        status: Current status (pending, acknowledged, in_progress, resolved).
        context: Serialized EscalationContext data.
        created_at: UTC ISO-8601 creation timestamp (BC-012).
        acknowledged_at: UTC ISO-8601 acknowledgment timestamp.
        resolved_at: UTC ISO-8601 resolution timestamp.
        resolved_by: Who resolved the escalation.
        outcome: Resolution outcome (EscalationOutcome).
        assigned_to: Agent or team assigned to handle this.
        response_message: Response or notes from the resolver.
        cooldown_until: UTC ISO-8601 cooldown expiry timestamp.
        metadata: Additional data attached to the record.
    """
    escalation_id: str
    company_id: str
    ticket_id: str
    trigger: str
    severity: str
    channel: str
    status: str
    context: Dict[str, Any]
    created_at: str
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    outcome: Optional[str] = None
    assigned_to: Optional[str] = None
    response_message: Optional[str] = None
    cooldown_until: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EscalationRule:
    """Rule defining when and how to escalate.

    Each rule maps a trigger type to conditions, severity, channel,
    and rate-limiting parameters. Rules are evaluated in priority
    order (lower number = higher priority).

    Attributes:
        name: Unique rule identifier.
        trigger: EscalationTrigger this rule handles.
        severity: Default severity for matches.
        condition: Dict of condition thresholds (e.g. frustration_threshold).
        channel: Preferred notification channel.
        cooldown_seconds: Cooldown between escalations for this trigger.
        max_per_hour: Maximum escalations per hour for this rule.
        auto_resolve_after_seconds: Auto-resolve after this many seconds.
        priority: Rule priority (lower = higher priority).
        enabled: Whether the rule is active.
    """
    name: str
    trigger: str
    severity: str
    condition: Dict[str, Any]
    channel: str
    cooldown_seconds: float = 300.0
    max_per_hour: int = 5
    auto_resolve_after_seconds: Optional[float] = None
    priority: int = 10
    enabled: bool = True


@dataclass
class EscalationConfig:
    """Per-company escalation configuration.

    Controls global escalation behaviour for a tenant including
    rate limits, cooldowns, and notification preferences.

    Attributes:
        company_id: Tenant company identifier (BC-001).
        default_severity: Default severity when not specified by rules.
        default_channel: Default notification channel.
        max_active_escalations: Maximum active escalations before rejection.
        cooldown_seconds: Default cooldown between escalations.
        auto_resolve_after_seconds: Auto-resolve stale escalations.
        enable_rate_limiting: Whether per-hour rate limiting is active.
        max_escalations_per_hour: Per-company escalations per hour cap.
        vip_multiplier: VIP cooldown multiplier (0.7 = 70% of normal).
        on_call_enabled: Whether on-call paging is enabled.
        on_call_webhook_url: Webhook URL for on-call notifications.
    """
    company_id: str = ""
    default_severity: str = "medium"
    default_channel: str = "in_app"
    max_active_escalations: int = 50
    cooldown_seconds: float = 300.0
    auto_resolve_after_seconds: float = 3600.0
    enable_rate_limiting: bool = True
    max_escalations_per_hour: int = 20
    vip_multiplier: float = 0.7
    on_call_enabled: bool = False
    on_call_webhook_url: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Severity ordering for comparison (higher index = higher severity)
_SEVERITY_ORDER: Dict[str, int] = {
    EscalationSeverity.LOW.value: 0,
    EscalationSeverity.MEDIUM.value: 1,
    EscalationSeverity.HIGH.value: 2,
    EscalationSeverity.CRITICAL.value: 3,
}

# VIP customer tiers
_VIP_TIERS: frozenset = frozenset({"enterprise", "vip", "premium"})

# Valid escalation statuses
_VALID_STATUSES: frozenset = frozenset({
    "pending", "acknowledged", "in_progress", "resolved",
})

# Maximum notification log entries retained in memory
_MAX_NOTIFICATION_LOG: int = 500


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _now_utc() -> str:
    """Return current UTC timestamp as ISO-8601 string (BC-012)."""
    return datetime.now(timezone.utc).isoformat()


def _generate_id() -> str:
    """Generate a unique escalation ID using UUID4."""
    return f"esc_{uuid.uuid4().hex[:16]}"


def _is_vip(customer_tier: str) -> bool:
    """Check if a customer tier qualifies as VIP."""
    return customer_tier.lower().strip() in _VIP_TIERS if customer_tier else False


def _higher_severity(a: str, b: str) -> str:
    """Return the higher of two severity values."""
    order_a = _SEVERITY_ORDER.get(a, 0)
    order_b = _SEVERITY_ORDER.get(b, 0)
    return a if order_a >= order_b else b


def _parse_iso(ts: str) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp string to a datetime object."""
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _context_to_dict(ctx: EscalationContext) -> Dict[str, Any]:
    """Serialize an EscalationContext to a dictionary."""
    return {
        "company_id": ctx.company_id,
        "ticket_id": ctx.ticket_id,
        "trigger": ctx.trigger,
        "severity": ctx.severity,
        "description": ctx.description,
        "gsd_state": ctx.gsd_state,
        "variant": ctx.variant,
        "agent_id": ctx.agent_id,
        "frustration_score": ctx.frustration_score,
        "confidence_score": ctx.confidence_score,
        "failure_count": ctx.failure_count,
        "customer_tier": ctx.customer_tier,
        "conversation_turns": ctx.conversation_turns,
        "metadata": ctx.metadata,
    }


# ══════════════════════════════════════════════════════════════════
# MAIN SERVICE
# ══════════════════════════════════════════════════════════════════


class GracefulEscalationManager:
    """Graceful Escalation Framework for PARWA.

    Provides a unified escalation system that bridges partial failure
    handling, GSD engine escalation, collision detection, and session
    monitoring. Manages escalation rules, cooldowns, rate limiting,
    notification channels, and resolution tracking.

    Key capabilities:
    - Evaluate escalation triggers with configurable rules
    - Manage escalation cooldowns (per company, per ticket)
    - Rate limiting (per hour limits)
    - Multi-channel notification support
    - Escalation lifecycle management (create -> acknowledge -> resolve)
    - Severity-based priority ordering
    - VIP customer fast-track escalation
    - Auto-resolution for stale escalations
    - Escalation analytics and statistics

    BC-001: company_id first parameter on all public methods.
    BC-008: Every public method wrapped in try/except — never crash.
    BC-012: All timestamps UTC.
    """

    def __init__(self) -> None:
        """Initialize the escalation manager with default rules and state.

        Sets up internal data structures for tracking escalations,
        rules, configs, rate limits, cooldowns, and notification logs.
        Registers all built-in default escalation rules.
        """
        self._lock = threading.RLock()
        # Active escalations: {escalation_id: EscalationRecord}
        self._escalations: Dict[str, EscalationRecord] = {}
        # Company escalation index: {company_id: [escalation_ids]}
        self._company_escalations: Dict[str, List[str]] = defaultdict(list)
        # Ticket escalation index: {(company_id, ticket_id): [escalation_ids]}
        self._ticket_escalations: Dict[Tuple[str,
                                             str], List[str]] = defaultdict(list)
        # Escalation rules: {rule_name: EscalationRule}
        self._rules: Dict[str, EscalationRule] = {}
        # Company configs: {company_id: EscalationConfig}
        self._configs: Dict[str, EscalationConfig] = {}
        # Rate limiting: {company_id: [timestamps]}
        self._rate_limit_log: Dict[str, List[float]] = defaultdict(list)
        # Cooldown tracking: {(company_id, ticket_id, trigger): expires_at}
        self._cooldowns: Dict[Tuple[str, str, str], str] = {}
        # Notification dispatch log: {company_id: [notification dicts]}
        self._notification_log: Dict[str,
                                     List[Dict[str, Any]]] = defaultdict(list)
        # Event listeners
        self._listeners: List[Callable] = []
        # Max notification log entries
        self._max_notification_log = _MAX_NOTIFICATION_LOG

        # Register built-in default rules
        self._register_default_rules()

        logger.info(
            "graceful_escalation_manager_initialized",
            default_rules=len(self._rules),
        )

    # ── Default Rule Registration ───────────────────────────────

    def _register_default_rules(self) -> None:
        """Register all built-in default escalation rules.

        Covers the 10 standard escalation triggers with sensible
        defaults for conditions, severity, channel, and cooldown.
        """
        default_rules: List[EscalationRule] = [
            EscalationRule(
                name="high_frustration",
                trigger=EscalationTrigger.HIGH_FRUSTRATION.value,
                severity=EscalationSeverity.HIGH.value,
                condition={"frustration_threshold": 80},
                channel=EscalationChannel.IN_APP.value,
                cooldown_seconds=300.0,
                max_per_hour=5,
                priority=2,
            ),
            EscalationRule(
                name="legal_sensitive",
                trigger=EscalationTrigger.LEGAL_SENSITIVE.value,
                severity=EscalationSeverity.HIGH.value,
                condition={},
                channel=EscalationChannel.SLACK.value,
                cooldown_seconds=0.0,
                max_per_hour=10,
                priority=1,
            ),
            EscalationRule(
                name="multiple_failures",
                trigger=EscalationTrigger.MULTIPLE_FAILURES.value,
                severity=EscalationSeverity.HIGH.value,
                condition={"failure_threshold": 3},
                channel=EscalationChannel.EMAIL.value,
                cooldown_seconds=300.0,
                max_per_hour=5,
                priority=3,
            ),
            EscalationRule(
                name="collision_conflict",
                trigger=EscalationTrigger.COLLISION_CONFLICT.value,
                severity=EscalationSeverity.HIGH.value,
                condition={},
                channel=EscalationChannel.IN_APP.value,
                cooldown_seconds=120.0,
                max_per_hour=10,
                priority=2,
            ),
            EscalationRule(
                name="stale_session",
                trigger=EscalationTrigger.STALE_SESSION.value,
                severity=EscalationSeverity.MEDIUM.value,
                condition={},
                channel=EscalationChannel.IN_APP.value,
                cooldown_seconds=600.0,
                max_per_hour=5,
                priority=8,
            ),
            EscalationRule(
                name="timeout",
                trigger=EscalationTrigger.TIMEOUT.value,
                severity=EscalationSeverity.MEDIUM.value,
                condition={},
                channel=EscalationChannel.IN_APP.value,
                cooldown_seconds=300.0,
                max_per_hour=8,
                priority=6,
            ),
            EscalationRule(
                name="confidence_low",
                trigger=EscalationTrigger.CONFIDENCE_LOW.value,
                severity=EscalationSeverity.MEDIUM.value,
                condition={"confidence_threshold": 0.3, "min_turns": 5},
                channel=EscalationChannel.IN_APP.value,
                cooldown_seconds=300.0,
                max_per_hour=5,
                priority=5,
            ),
            EscalationRule(
                name="vip_customer",
                trigger=EscalationTrigger.VIP_CUSTOMER.value,
                severity=EscalationSeverity.HIGH.value,
                condition={},
                channel=EscalationChannel.EMAIL.value,
                cooldown_seconds=150.0,
                max_per_hour=10,
                priority=1,
            ),
            EscalationRule(
                name="loop_detected",
                trigger=EscalationTrigger.LOOP_DETECTED.value,
                severity=EscalationSeverity.MEDIUM.value,
                condition={},
                channel=EscalationChannel.IN_APP.value,
                cooldown_seconds=300.0,
                max_per_hour=5,
                priority=7,
            ),
            EscalationRule(
                name="capacity_overflow",
                trigger=EscalationTrigger.CAPACITY_OVERFLOW.value,
                severity=EscalationSeverity.MEDIUM.value,
                condition={},
                channel=EscalationChannel.SLACK.value,
                cooldown_seconds=600.0,
                max_per_hour=3,
                priority=4,
            ),
        ]

        for rule in default_rules:
            self._rules[rule.name] = rule

    # ── Configuration Management ────────────────────────────────

    def configure(self, company_id: str, config: EscalationConfig) -> None:
        """Set per-company escalation configuration.

        Args:
            company_id: Tenant company identifier (BC-001).
            config: EscalationConfig with company-specific settings.
        """
        try:
            config.company_id = company_id
            with self._lock:
                self._configs[company_id] = config
            logger.info(
                "escalation_config_updated",
                company_id=company_id,
                default_severity=config.default_severity,
                max_per_hour=config.max_escalations_per_hour,
                auto_resolve_after=config.auto_resolve_after_seconds,
            )
        except Exception:
            logger.exception(
                "configure_crashed",
                company_id=company_id,
            )

    def get_config(self, company_id: str) -> EscalationConfig:
        """Get escalation configuration for a company.

        Falls back to a default EscalationConfig if no company-specific
        configuration has been set.

        Args:
            company_id: Tenant company identifier (BC-001).

        Returns:
            EscalationConfig for the company.
        """
        try:
            with self._lock:
                if company_id and company_id in self._configs:
                    return self._configs[company_id]
                return EscalationConfig(company_id=company_id or "")
        except Exception:
            logger.exception(
                "get_config_crashed",
                company_id=company_id,
            )
            return EscalationConfig(company_id=company_id or "")

    # ── Rule Management ─────────────────────────────────────────

    def add_rule(self, rule: EscalationRule) -> None:
        """Add or replace an escalation rule.

        If a rule with the same name already exists, it will be
        replaced by the new rule.

        Args:
            rule: EscalationRule to add or replace.
        """
        try:
            with self._lock:
                self._rules[rule.name] = rule
            logger.info(
                "escalation_rule_added",
                rule_name=rule.name,
                trigger=rule.trigger,
                severity=rule.severity,
                priority=rule.priority,
                enabled=rule.enabled,
            )
        except Exception:
            logger.exception(
                "add_rule_crashed",
                rule_name=getattr(rule, "name", "unknown"),
            )

    def remove_rule(self, rule_name: str) -> None:
        """Remove an escalation rule by name.

        Args:
            rule_name: Name of the rule to remove.
        """
        try:
            with self._lock:
                removed = self._rules.pop(rule_name, None)
            if removed:
                logger.info(
                    "escalation_rule_removed",
                    rule_name=rule_name,
                )
            else:
                logger.warning(
                    "escalation_rule_not_found_for_removal",
                    rule_name=rule_name,
                )
        except Exception:
            logger.exception(
                "remove_rule_crashed",
                rule_name=rule_name,
            )

    def get_rules(self, company_id: str) -> List[EscalationRule]:
        """Get all active (enabled) escalation rules sorted by priority.

        Args:
            company_id: Tenant company identifier (BC-001).

        Returns:
            List of enabled EscalationRule instances sorted by priority.
        """
        try:
            with self._lock:
                active = [
                    rule for rule in self._rules.values()
                    if rule.enabled
                ]
                active.sort(key=lambda r: r.priority)
                return active
        except Exception:
            logger.exception(
                "get_rules_crashed",
                company_id=company_id,
            )
            return []

    # ── Escalation Evaluation ───────────────────────────────────

    def evaluate_escalation(
        self,
        company_id: str,
        context: EscalationContext,
    ) -> Tuple[bool, List[EscalationRule], str]:
        """Check if escalation should trigger given an EscalationContext.

        Evaluates all enabled rules against the provided context,
        checking trigger matching, condition thresholds, cooldowns,
        and rate limits. If multiple rules match, the highest severity
        and lowest priority number are selected.

        Args:
            company_id: Tenant company identifier (BC-001).
            context: EscalationContext with current state information.

        Returns:
            Tuple of (should_escalate, matched_rules, severity).
            - should_escalate: True if at least one rule matches.
            - matched_rules: List of matching EscalationRule instances.
            - severity: Resulting severity (highest among matches).
        """
        try:
            config = self.get_config(company_id)
            rules = self.get_rules(company_id)
            matched_rules: List[EscalationRule] = []
            result_severity = config.default_severity

            for rule in rules:
                # Step 1: Match trigger
                if rule.trigger != context.trigger:
                    continue

                # Step 2: Check conditions
                if not self._check_rule_conditions(rule, context):
                    continue

                # Step 3: Check cooldown (VIP bypasses cooldown)
                is_vip_customer = _is_vip(context.customer_tier)
                if not is_vip_customer:
                    cooldown_active = self.check_cooldown(
                        company_id, context.ticket_id, context.trigger,
                    )
                    if cooldown_active:
                        continue

                # Step 4: Check per-rule rate limit
                if not self._check_rule_rate_limit(company_id, rule):
                    continue

                # Rule matches
                matched_rules.append(rule)
                result_severity = _higher_severity(
                    result_severity, rule.severity,
                )

            should_escalate = len(matched_rules) > 0

            if should_escalate:
                # Also check company-wide rate limit
                if config.enable_rate_limiting:
                    rate_limited = self.check_rate_limit(company_id)
                    if rate_limited:
                        logger.warning(
                            "escalation_blocked_rate_limit",
                            company_id=company_id,
                            ticket_id=context.ticket_id,
                            trigger=context.trigger,
                        )
                        return False, matched_rules, result_severity

                logger.info(
                    "escalation_evaluated_should_escalate",
                    company_id=company_id,
                    ticket_id=context.ticket_id,
                    trigger=context.trigger,
                    severity=result_severity,
                    matched_rules=len(matched_rules),
                    is_vip=_is_vip(context.customer_tier),
                )
            else:
                logger.debug(
                    "escalation_evaluated_no_trigger",
                    company_id=company_id,
                    ticket_id=context.ticket_id,
                    trigger=context.trigger,
                )

            return should_escalate, matched_rules, result_severity

        except Exception:
            logger.exception(
                "evaluate_escalation_crashed",
                company_id=company_id,
                ticket_id=getattr(context, "ticket_id", ""),
            )
            # BC-008: Return safe defaults — do not escalate on error
            return False, [], "low"

    def _check_rule_conditions(
        self, rule: EscalationRule, context: EscalationContext,
    ) -> bool:
        """Check if a rule's conditions are satisfied by the context.

        Evaluates condition thresholds such as frustration_score,
        confidence_score, and failure_count against the rule's
        condition dictionary.

        GAP 6 FIX: All values are captured atomically from the context
        to prevent race conditions where values change between checks.
        This ensures that if frustration crosses the threshold between
        the time it's calculated and when the escalation check runs,
        the system still correctly triggers escalation.

        Args:
            rule: EscalationRule with condition thresholds.
            context: EscalationContext with current values.

        Returns:
            True if all conditions are met.
        """
        conditions = rule.condition
        if not conditions:
            return True

        # GAP 6 FIX: Capture all context values atomically at the start
        # This prevents race conditions where frustration score changes
        # between the threshold check and the escalation decision
        frustration_score = float(context.frustration_score)
        confidence_score = float(context.confidence_score)
        failure_count = int(context.failure_count)
        conversation_turns = int(context.conversation_turns)

        # Frustration threshold
        frustration_threshold = conditions.get("frustration_threshold")
        if frustration_threshold is not None:
            if frustration_score < float(frustration_threshold):
                return False

        # Failure threshold
        failure_threshold = conditions.get("failure_threshold")
        if failure_threshold is not None:
            if failure_count < int(failure_threshold):
                return False

        # Confidence threshold (below this triggers escalation)
        confidence_threshold = conditions.get("confidence_threshold")
        if confidence_threshold is not None:
            if confidence_score >= float(confidence_threshold):
                return False

        # Minimum turns requirement
        min_turns = conditions.get("min_turns")
        if min_turns is not None:
            if conversation_turns < int(min_turns):
                return False

        return True

    def _check_rule_rate_limit(
        self, company_id: str, rule: EscalationRule,
    ) -> bool:
        """Check per-rule rate limit for a company.

        Args:
            company_id: Tenant identifier.
            rule: EscalationRule to check rate for.

        Returns:
            True if under the rate limit, False if exceeded.
        """
        try:
            with self._lock:
                key = f"{company_id}:{rule.name}"
                timestamps = self._rate_limit_log.get(key, [])
                now = time.time()
                cutoff = now - 3600.0  # Last hour

                # Clean old entries
                recent = [ts for ts in timestamps if ts > cutoff]

                if len(recent) >= rule.max_per_hour:
                    return False

                return True
        except Exception:
            return True  # Allow escalation on error

    # ── Escalation Lifecycle ────────────────────────────────────

    def create_escalation(
        self,
        company_id: str,
        context: EscalationContext,
        channel_override: Optional[str] = None,
    ) -> Optional[EscalationRecord]:
        """Create an escalation record after evaluation.

        Performs cooldown and rate limit checks before creating the
        record. Sets cooldown for the trigger on the ticket. Logs
        the notification dispatch.

        Args:
            company_id: Tenant company identifier (BC-001).
            context: EscalationContext with full event details.
            channel_override: Override the notification channel.

        Returns:
            EscalationRecord if created successfully, None if blocked.
        """
        try:
            config = self.get_config(company_id)
            now = _now_utc()

            # Check active escalation cap
            active = self.get_active_escalations(company_id)
            if len(active) >= config.max_active_escalations:
                logger.warning(
                    "escalation_blocked_max_active",
                    company_id=company_id,
                    ticket_id=context.ticket_id,
                    active_count=len(active),
                    max_active=config.max_active_escalations,
                )
                return None

            # Determine channel
            channel = channel_override or config.default_channel
            if not channel_override:
                # Use highest-priority matching rule's channel
                _, matched_rules, _ = self.evaluate_escalation(
                    company_id, context,
                )
                if matched_rules:
                    channel = matched_rules[0].channel

            # Generate escalation ID and build record
            escalation_id = _generate_id()
            is_vip_customer = _is_vip(context.customer_tier)

            # Calculate cooldown expiry
            cooldown_seconds = config.cooldown_seconds
            if is_vip_customer:
                cooldown_seconds = cooldown_seconds * config.vip_multiplier
            cooldown_dt = datetime.fromtimestamp(
                time.time() + cooldown_seconds, tz=timezone.utc,
            )

            record = EscalationRecord(
                escalation_id=escalation_id,
                company_id=company_id,
                ticket_id=context.ticket_id,
                trigger=context.trigger,
                severity=context.severity,
                channel=channel,
                status="pending",
                context=_context_to_dict(context),
                created_at=now,
                cooldown_until=cooldown_dt.isoformat(),
                metadata={
                    "is_vip": is_vip_customer,
                    "auto_resolve_after": config.auto_resolve_after_seconds,
                },
            )

            with self._lock:
                # Store record
                self._escalations[escalation_id] = record
                self._company_escalations[company_id].append(escalation_id)
                self._ticket_escalations[
                    (company_id, context.ticket_id)
                ].append(escalation_id)

                # Set cooldown
                cooldown_key = (company_id, context.ticket_id, context.trigger)
                self._cooldowns[cooldown_key] = record.cooldown_until

                # Track rate limit
                rate_key = f"{company_id}:{context.trigger}"
                self._rate_limit_log[rate_key].append(time.time())

            # Log notification dispatch
            self._log_notification(
                company_id, escalation_id, channel, context,
            )

            # Emit event to listeners
            self._emit_event("escalation_created", {
                "escalation_id": escalation_id,
                "company_id": company_id,
                "ticket_id": context.ticket_id,
                "trigger": context.trigger,
                "severity": context.severity,
                "channel": channel,
                "is_vip": is_vip_customer,
            })

            logger.warning(
                "escalation_created",
                escalation_id=escalation_id,
                company_id=company_id,
                ticket_id=context.ticket_id,
                trigger=context.trigger,
                severity=context.severity,
                channel=channel,
                is_vip=is_vip_customer,
                cooldown_seconds=cooldown_seconds,
            )

            return record

        except Exception:
            logger.exception(
                "create_escalation_crashed",
                company_id=company_id,
                ticket_id=getattr(context, "ticket_id", ""),
            )
            return None

    def acknowledge_escalation(
        self,
        company_id: str,
        escalation_id: str,
        acknowledged_by: str,
    ) -> Optional[EscalationRecord]:
        """Mark an escalation as acknowledged.

        Updates the escalation status to 'acknowledged' and records
        who acknowledged it and when.

        Args:
            company_id: Tenant company identifier (BC-001).
            escalation_id: ID of the escalation to acknowledge.
            acknowledged_by: Identifier of the acknowledging agent.

        Returns:
            Updated EscalationRecord, or None if not found.
        """
        try:
            with self._lock:
                record = self._escalations.get(escalation_id)
                if not record or record.company_id != company_id:
                    logger.warning(
                        "acknowledge_escalation_not_found",
                        company_id=company_id,
                        escalation_id=escalation_id,
                    )
                    return None

                if record.status == "resolved":
                    logger.warning(
                        "acknowledge_escalation_already_resolved",
                        escalation_id=escalation_id,
                    )
                    return record

                record.status = "acknowledged"
                record.acknowledged_at = _now_utc()
                record.assigned_to = acknowledged_by

            self._emit_event("escalation_acknowledged", {
                "escalation_id": escalation_id,
                "company_id": company_id,
                "acknowledged_by": acknowledged_by,
            })

            logger.info(
                "escalation_acknowledged",
                escalation_id=escalation_id,
                company_id=company_id,
                acknowledged_by=acknowledged_by,
            )

            return record

        except Exception:
            logger.exception(
                "acknowledge_escalation_crashed",
                company_id=company_id,
                escalation_id=escalation_id,
            )
            return None

    def resolve_escalation(
        self,
        company_id: str,
        escalation_id: str,
        outcome: str,
        resolved_by: str,
        response_message: Optional[str] = None,
    ) -> Optional[EscalationRecord]:
        """Mark an escalation as resolved.

        Updates the escalation status to 'resolved', records the
        outcome, who resolved it, when, and any response notes.

        Args:
            company_id: Tenant company identifier (BC-001).
            escalation_id: ID of the escalation to resolve.
            outcome: EscalationOutcome value describing resolution.
            resolved_by: Identifier of the resolving agent.
            response_message: Optional resolution notes.

        Returns:
            Updated EscalationRecord, or None if not found.
        """
        try:
            now = _now_utc()
            with self._lock:
                record = self._escalations.get(escalation_id)
                if not record or record.company_id != company_id:
                    logger.warning(
                        "resolve_escalation_not_found",
                        company_id=company_id,
                        escalation_id=escalation_id,
                    )
                    return None

                if record.status == "resolved":
                    logger.warning(
                        "resolve_escalation_already_resolved",
                        escalation_id=escalation_id,
                    )
                    return record

                record.status = "resolved"
                record.resolved_at = now
                record.resolved_by = resolved_by
                record.outcome = outcome
                record.response_message = response_message

            self._emit_event("escalation_resolved", {
                "escalation_id": escalation_id,
                "company_id": company_id,
                "ticket_id": record.ticket_id,
                "outcome": outcome,
                "resolved_by": resolved_by,
            })

            logger.info(
                "escalation_resolved",
                escalation_id=escalation_id,
                company_id=company_id,
                ticket_id=record.ticket_id,
                outcome=outcome,
                resolved_by=resolved_by,
            )

            return record

        except Exception:
            logger.exception(
                "resolve_escalation_crashed",
                company_id=company_id,
                escalation_id=escalation_id,
            )
            return None

    def dismiss_escalation(
        self,
        company_id: str,
        escalation_id: str,
        reason: str = "",
    ) -> Optional[EscalationRecord]:
        """Dismiss an escalation as not needed.

        Marks the escalation as resolved with a DISMISSED outcome.

        Args:
            company_id: Tenant company identifier (BC-001).
            escalation_id: ID of the escalation to dismiss.
            reason: Reason for dismissal.

        Returns:
            Updated EscalationRecord, or None if not found.
        """
        try:
            return self.resolve_escalation(
                company_id=company_id,
                escalation_id=escalation_id,
                outcome=EscalationOutcome.DISMISSED.value,
                resolved_by="system",
                response_message=f"Dismissed: {reason}" if reason else "Dismissed",
            )
        except Exception:
            logger.exception(
                "dismiss_escalation_crashed",
                company_id=company_id,
                escalation_id=escalation_id,
            )
            return None

    def reassign_escalation(
        self,
        company_id: str,
        escalation_id: str,
        assigned_to: str,
    ) -> Optional[EscalationRecord]:
        """Reassign an escalation to a different agent or team.

        Args:
            company_id: Tenant company identifier (BC-001).
            escalation_id: ID of the escalation to reassign.
            assigned_to: New agent or team identifier.

        Returns:
            Updated EscalationRecord, or None if not found.
        """
        try:
            with self._lock:
                record = self._escalations.get(escalation_id)
                if not record or record.company_id != company_id:
                    logger.warning(
                        "reassign_escalation_not_found",
                        company_id=company_id,
                        escalation_id=escalation_id,
                    )
                    return None

                previous_assignee = record.assigned_to
                record.assigned_to = assigned_to
                record.status = "in_progress"
                record.metadata["reassigned_from"] = previous_assignee
                record.metadata["reassigned_at"] = _now_utc()

            self._emit_event("escalation_reassigned", {
                "escalation_id": escalation_id,
                "company_id": company_id,
                "previous_assignee": previous_assignee,
                "new_assignee": assigned_to,
            })

            logger.info(
                "escalation_reassigned",
                escalation_id=escalation_id,
                company_id=company_id,
                from_assignee=previous_assignee,
                to_assignee=assigned_to,
            )

            return record

        except Exception:
            logger.exception(
                "reassign_escalation_crashed",
                company_id=company_id,
                escalation_id=escalation_id,
            )
            return None

    # ── Query Methods ───────────────────────────────────────────

    def get_escalation(
        self,
        company_id: str,
        escalation_id: str,
    ) -> Optional[EscalationRecord]:
        """Get escalation details by ID.

        Args:
            company_id: Tenant company identifier (BC-001).
            escalation_id: ID of the escalation to retrieve.

        Returns:
            EscalationRecord if found and belongs to the company, None otherwise.
        """
        try:
            with self._lock:
                record = self._escalations.get(escalation_id)
                if record and record.company_id == company_id:
                    return record
                return None
        except Exception:
            logger.exception(
                "get_escalation_crashed",
                company_id=company_id,
                escalation_id=escalation_id,
            )
            return None

    def get_active_escalations(
        self, company_id: str,
    ) -> List[EscalationRecord]:
        """List all active (non-resolved) escalations for a company.

        Returns records with status 'pending', 'acknowledged', or
        'in_progress', sorted by creation time (most recent first).

        Args:
            company_id: Tenant company identifier (BC-001).

        Returns:
            List of active EscalationRecord instances.
        """
        try:
            with self._lock:
                escalation_ids = self._company_escalations.get(company_id, [])
                active: List[EscalationRecord] = []
                for eid in escalation_ids:
                    record = self._escalations.get(eid)
                    if record and record.status in (
                        "pending", "acknowledged", "in_progress",
                    ):
                        active.append(record)

                # Sort by creation time (most recent first)
                active.sort(
                    key=lambda r: r.created_at, reverse=True,
                )
                return active
        except Exception:
            logger.exception(
                "get_active_escalations_crashed",
                company_id=company_id,
            )
            return []

    def get_ticket_escalations(
        self,
        company_id: str,
        ticket_id: str,
    ) -> List[EscalationRecord]:
        """List all escalations for a specific ticket.

        Includes both active and resolved escalations, sorted by
        creation time (most recent first).

        Args:
            company_id: Tenant company identifier (BC-001).
            ticket_id: Ticket ID to filter by.

        Returns:
            List of EscalationRecord instances for the ticket.
        """
        try:
            with self._lock:
                key = (company_id, ticket_id)
                escalation_ids = self._ticket_escalations.get(key, [])
                records: List[EscalationRecord] = []
                for eid in escalation_ids:
                    record = self._escalations.get(eid)
                    if record:
                        records.append(record)

                records.sort(
                    key=lambda r: r.created_at, reverse=True,
                )
                return records
        except Exception:
            logger.exception(
                "get_ticket_escalations_crashed",
                company_id=company_id,
                ticket_id=ticket_id,
            )
            return []

    def get_escalations_by_severity(
        self,
        company_id: str,
        severity: str,
    ) -> List[EscalationRecord]:
        """Filter escalations by severity level.

        Returns all active escalations matching the given severity.

        Args:
            company_id: Tenant company identifier (BC-001).
            severity: EscalationSeverity value to filter by.

        Returns:
            List of matching EscalationRecord instances.
        """
        try:
            active = self.get_active_escalations(company_id)
            return [
                r for r in active
                if r.severity == severity
            ]
        except Exception:
            logger.exception(
                "get_escalations_by_severity_crashed",
                company_id=company_id,
                severity=severity,
            )
            return []

    # ── Cooldown Management ─────────────────────────────────────

    def check_cooldown(
        self,
        company_id: str,
        ticket_id: str,
        trigger: str,
    ) -> bool:
        """Check if a cooldown is active for a specific trigger.

        Automatically clears expired cooldowns before checking.

        Args:
            company_id: Tenant company identifier (BC-001).
            ticket_id: Ticket ID to check cooldown for.
            trigger: EscalationTrigger value.

        Returns:
            True if cooldown is currently active, False otherwise.
        """
        try:
            cooldown_key = (company_id, ticket_id, trigger)
            now = datetime.now(timezone.utc)

            with self._lock:
                expires_at_str = self._cooldowns.get(cooldown_key)
                if not expires_at_str:
                    return False

                expires_at = _parse_iso(expires_at_str)
                if not expires_at:
                    # Invalid timestamp — clear it
                    del self._cooldowns[cooldown_key]
                    return False

                if now >= expires_at:
                    # Cooldown expired — clear it
                    del self._cooldowns[cooldown_key]
                    return False

                # Cooldown is still active
                remaining = (expires_at - now).total_seconds()
                logger.debug(
                    "escalation_cooldown_active",
                    company_id=company_id,
                    ticket_id=ticket_id,
                    trigger=trigger,
                    remaining_seconds=remaining,
                )
                return True

        except Exception:
            logger.exception(
                "check_cooldown_crashed",
                company_id=company_id,
                ticket_id=ticket_id,
                trigger=trigger,
            )
            return False

    def set_cooldown(
        self,
        company_id: str,
        ticket_id: str,
        trigger: str,
        seconds: float,
    ) -> None:
        """Manually set a cooldown for a specific trigger.

        Args:
            company_id: Tenant company identifier (BC-001).
            ticket_id: Ticket ID to set cooldown for.
            trigger: EscalationTrigger value.
            seconds: Duration of the cooldown in seconds.
        """
        try:
            expires_dt = datetime.fromtimestamp(
                time.time() + seconds, tz=timezone.utc,
            )
            cooldown_key = (company_id, ticket_id, trigger)

            with self._lock:
                self._cooldowns[cooldown_key] = expires_dt.isoformat()

            logger.info(
                "escalation_cooldown_set",
                company_id=company_id,
                ticket_id=ticket_id,
                trigger=trigger,
                cooldown_seconds=seconds,
            )
        except Exception:
            logger.exception(
                "set_cooldown_crashed",
                company_id=company_id,
                ticket_id=ticket_id,
                trigger=trigger,
            )

    # ── Rate Limiting ───────────────────────────────────────────

    def check_rate_limit(self, company_id: str) -> bool:
        """Check if company-level rate limit has been reached.

        Counts escalations created in the last hour (3600 seconds)
        for the given company. Returns True if the limit is reached.

        Args:
            company_id: Tenant company identifier (BC-001).

        Returns:
            True if rate limit is reached (blocked), False if OK.
        """
        try:
            config = self.get_config(company_id)
            if not config.enable_rate_limiting:
                return False

            now = time.time()
            cutoff = now - 3600.0

            with self._lock:
                timestamps = self._rate_limit_log.get(company_id, [])
                # Clean old entries
                recent = [ts for ts in timestamps if ts > cutoff]
                self._rate_limit_log[company_id] = recent

                return len(recent) >= config.max_escalations_per_hour

        except Exception:
            logger.exception(
                "check_rate_limit_crashed",
                company_id=company_id,
            )
            return False  # Allow on error

    # ── Auto-Resolution ─────────────────────────────────────────

    def auto_resolve_stale(self, company_id: str) -> int:
        """Auto-resolve escalations that have exceeded the auto-resolve threshold.

        Scans all active escalations for the company and resolves any
        that have been pending for longer than the configured
        auto_resolve_after_seconds.

        Args:
            company_id: Tenant company identifier (BC-001).

        Returns:
            Number of escalations that were auto-resolved.
        """
        try:
            config = self.get_config(company_id)
            active = self.get_active_escalations(company_id)
            now = datetime.now(timezone.utc)
            resolved_count = 0

            for record in active:
                created_at = _parse_iso(record.created_at)
                if not created_at:
                    continue

                # Per-record auto-resolve override
                auto_resolve_seconds = record.metadata.get(
                    "auto_resolve_after", config.auto_resolve_after_seconds,
                )

                elapsed = (now - created_at).total_seconds()
                if elapsed >= auto_resolve_seconds:
                    self.resolve_escalation(
                        company_id=company_id,
                        escalation_id=record.escalation_id,
                        outcome=EscalationOutcome.EXPIRED.value,
                        resolved_by="auto_resolve",
                        response_message=(
                            f"Auto-resolved after {elapsed:.0f}s "
                            f"(threshold: {auto_resolve_seconds:.0f}s)"
                        ),
                    )
                    resolved_count += 1

            if resolved_count > 0:
                logger.info(
                    "auto_resolved_stale_escalations",
                    company_id=company_id,
                    resolved_count=resolved_count,
                    checked_count=len(active),
                )

            return resolved_count

        except Exception:
            logger.exception(
                "auto_resolve_stale_crashed",
                company_id=company_id,
            )
            return 0

    # ── Statistics ──────────────────────────────────────────────

    def get_statistics(self, company_id: str) -> Dict[str, Any]:
        """Generate escalation analytics for a company.

        Computes aggregate statistics including total escalations,
        breakdowns by trigger and severity, average resolution time,
        cooldown hit rate, and outcome distribution.

        Args:
            company_id: Tenant company identifier (BC-001).

        Returns:
            Dictionary with escalation statistics.
        """
        try:
            with self._lock:
                escalation_ids = self._company_escalations.get(company_id, [])
                records = [
                    self._escalations[eid]
                    for eid in escalation_ids
                    if eid in self._escalations
                ]

            if not records:
                return {
                    "company_id": company_id,
                    "total_escalations": 0,
                    "active_escalations": 0,
                    "resolved_escalations": 0,
                    "by_trigger": {},
                    "by_severity": {},
                    "by_outcome": {},
                    "avg_resolution_time_seconds": 0.0,
                    "cooldown_active_count": 0,
                    "rate_limit_current": 0,
                }

            # Totals
            active = [r for r in records if r.status != "resolved"]
            resolved = [r for r in records if r.status == "resolved"]

            # By trigger
            by_trigger: Dict[str, int] = defaultdict(int)
            for r in records:
                by_trigger[r.trigger] += 1

            # By severity
            by_severity: Dict[str, int] = defaultdict(int)
            for r in records:
                by_severity[r.severity] += 1

            # By outcome
            by_outcome: Dict[str, int] = defaultdict(int)
            for r in resolved:
                outcome = r.outcome or "unknown"
                by_outcome[outcome] += 1

            # Average resolution time
            resolution_times: List[float] = []
            for r in resolved:
                if r.resolved_at and r.created_at:
                    resolved_dt = _parse_iso(r.resolved_at)
                    created_dt = _parse_iso(r.created_at)
                    if resolved_dt and created_dt:
                        delta = (resolved_dt - created_dt).total_seconds()
                        resolution_times.append(delta)

            avg_resolution = (
                sum(resolution_times) / len(resolution_times)
                if resolution_times else 0.0
            )

            # Cooldown active count
            cooldown_count = 0
            with self._lock:
                for key, expires_at_str in self._cooldowns.items():
                    if key[0] == company_id:
                        expires_at = _parse_iso(expires_at_str)
                        if expires_at and expires_at > datetime.now(
                                timezone.utc):
                            cooldown_count += 1

            # Current rate limit count
            now = time.time()
            cutoff = now - 3600.0
            with self._lock:
                company_timestamps = self._rate_limit_log.get(company_id, [])
                rate_current = sum(
                    1 for ts in company_timestamps if ts > cutoff
                )

            return {
                "company_id": company_id,
                "total_escalations": len(records),
                "active_escalations": len(active),
                "resolved_escalations": len(resolved),
                "by_trigger": dict(by_trigger),
                "by_severity": dict(by_severity),
                "by_outcome": dict(by_outcome),
                "avg_resolution_time_seconds": round(avg_resolution, 2),
                "cooldown_active_count": cooldown_count,
                "rate_limit_current": rate_current,
            }

        except Exception:
            logger.exception(
                "get_statistics_crashed",
                company_id=company_id,
            )
            return {
                "company_id": company_id,
                "total_escalations": 0,
                "active_escalations": 0,
                "resolved_escalations": 0,
                "by_trigger": {},
                "by_severity": {},
                "by_outcome": {},
                "avg_resolution_time_seconds": 0.0,
                "cooldown_active_count": 0,
                "rate_limit_current": 0,
            }

    # ── Notification & Messaging ────────────────────────────────

    def get_notification_log(
        self,
        company_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent notification dispatches for a company.

        Returns the most recent notification log entries, up to
        the specified limit.

        Args:
            company_id: Tenant company identifier (BC-001).
            limit: Maximum number of entries to return.

        Returns:
            List of notification log dictionaries (most recent first).
        """
        try:
            with self._lock:
                entries = list(self._notification_log.get(company_id, []))
                # Return most recent first, limited
                return list(reversed(entries[-limit:]))
        except Exception:
            logger.exception(
                "get_notification_log_crashed",
                company_id=company_id,
            )
            return []

    def build_escalation_message(
        self,
        company_id: str,
        record: EscalationRecord,
    ) -> str:
        """Generate a human-readable escalation notification message.

        Produces a formatted string summarizing the escalation event
        for display in dashboards, logs, or notification channels.

        Args:
            company_id: Tenant company identifier (BC-001).
            record: EscalationRecord to build a message for.

        Returns:
            Formatted escalation message string.
        """
        try:
            ctx = record.context
            severity_emoji = {
                "low": "ℹ️",
                "medium": "⚠️",
                "high": "🔴",
                "critical": "🚨",
            }.get(record.severity, "📋")

            trigger_label = record.trigger.replace("_", " ").title()
            channel_label = record.channel.replace("_", " ").title()

            lines: List[str] = [
                f"{severity_emoji} Escalation Alert [{
                    record.severity.upper()}]", "", f"Trigger: {trigger_label}", f"Ticket: {
                    record.ticket_id}", f"Escalation ID: {
                    record.escalation_id}", f"Channel: {channel_label}", f"Status: {
                    record.status.replace(
                        '_', ' ').title()}", f"Created: {
                            record.created_at}", ]

            # Add context details if available
            if ctx:
                description = ctx.get("description", "")
                if description:
                    lines.append("")
                    lines.append(f"Description: {description}")

                frustration = ctx.get("frustration_score", 0.0)
                if frustration > 0:
                    lines.append(f"Frustration Score: {frustration:.0f}/100")

                confidence = ctx.get("confidence_score", 0.0)
                if confidence > 0:
                    lines.append(f"Confidence Score: {confidence:.2f}")

                failure_count = ctx.get("failure_count", 0)
                if failure_count > 0:
                    lines.append(f"Failure Count: {failure_count}")

                customer_tier = ctx.get("customer_tier", "")
                if customer_tier:
                    lines.append(f"Customer Tier: {customer_tier}")

                gsd_state = ctx.get("gsd_state", "")
                if gsd_state:
                    lines.append(f"GSD State: {gsd_state}")

                variant = ctx.get("variant", "")
                if variant:
                    lines.append(f"Variant: {variant}")

            # Add assignment info
            if record.assigned_to:
                lines.append(f"Assigned To: {record.assigned_to}")

            if record.response_message:
                lines.append("")
                lines.append(f"Response: {record.response_message}")

            lines.append("")
            lines.append("— PARWA Escalation System")

            return "\n".join(lines)

        except Exception:
            logger.exception(
                "build_escalation_message_crashed",
                company_id=company_id,
                escalation_id=getattr(record, "escalation_id", ""),
            )
            return (
                f"Escalation Alert: {
                    getattr(
                        record,
                        'escalation_id',
                        'unknown')} " f"| Severity: {
                    getattr(
                        record,
                        'severity',
                        'unknown')} " f"| Ticket: {
                    getattr(
                        record,
                        'ticket_id',
                        'unknown')}")

    def _log_notification(
        self,
        company_id: str,
        escalation_id: str,
        channel: str,
        context: EscalationContext,
    ) -> None:
        """Log a notification dispatch event.

        Appends a notification entry to the company's notification log,
        maintaining the maximum log size.

        Args:
            company_id: Tenant identifier.
            escalation_id: ID of the escalation.
            channel: Notification channel used.
            context: EscalationContext for the notification.
        """
        try:
            entry: Dict[str, Any] = {
                "escalation_id": escalation_id,
                "channel": channel,
                "trigger": context.trigger,
                "severity": context.severity,
                "ticket_id": context.ticket_id,
                "timestamp": _now_utc(),
            }
            with self._lock:
                log = self._notification_log[company_id]
                log.append(entry)
                # Trim to max size
                if len(log) > self._max_notification_log:
                    self._notification_log[company_id] = log[
                        -self._max_notification_log:
                    ]
        except Exception:
            logger.exception(
                "log_notification_crashed",
                company_id=company_id,
                escalation_id=escalation_id,
            )

    # ── Event Listeners ─────────────────────────────────────────

    def add_event_listener(self, callback: Callable) -> None:
        """Register an event listener callback.

        The callback will be invoked for escalation lifecycle events
        (created, acknowledged, resolved, reassigned). The callback
        receives (event_name: str, event_data: dict).

        Args:
            callback: Callable accepting (event_name, event_data).
        """
        try:
            with self._lock:
                if callback not in self._listeners:
                    self._listeners.append(callback)
            logger.info(
                "escalation_event_listener_added",
                listener_count=len(self._listeners),
            )
        except Exception:
            logger.exception("add_event_listener_crashed")

    def remove_event_listener(self, callback: Callable) -> None:
        """Remove a previously registered event listener.

        Args:
            callback: The callback to remove.
        """
        try:
            with self._lock:
                if callback in self._listeners:
                    self._listeners.remove(callback)
            logger.info(
                "escalation_event_listener_removed",
                listener_count=len(self._listeners),
            )
        except Exception:
            logger.exception("remove_event_listener_crashed")

    def _emit_event(
        self, event_name: str, event_data: Dict[str, Any],
    ) -> None:
        """Emit an event to all registered listeners.

        Each listener is called with (event_name, event_data).
        Errors in individual listeners are caught and logged so
        they don't affect other listeners.

        Args:
            event_name: Name of the event (e.g. "escalation_created").
            event_data: Dictionary with event details.
        """
        try:
            with self._lock:
                listeners = list(self._listeners)

            for callback in listeners:
                try:
                    callback(event_name, event_data)
                except Exception:
                    logger.exception(
                        "escalation_event_listener_error",
                        event_name=event_name,
                    )
        except Exception:
            logger.exception("emit_event_crashed")

    # ── Data Management ─────────────────────────────────────────

    def clear_company_data(self, company_id: str) -> None:
        """Clear all escalation data for a company.

        Removes all escalations, indexes, rate limits, cooldowns,
        and notification logs for the specified company.

        Args:
            company_id: Tenant company identifier (BC-001).
        """
        try:
            with self._lock:
                # Collect escalation IDs to remove
                escalation_ids = self._company_escalations.pop(
                    company_id, [],
                )

                # Remove each escalation record
                for eid in escalation_ids:
                    self._escalations.pop(eid, None)

                # Remove ticket indexes for this company
                keys_to_remove = [
                    k for k in self._ticket_escalations
                    if k[0] == company_id
                ]
                for key in keys_to_remove:
                    del self._ticket_escalations[key]

                # Clear rate limits
                self._rate_limit_log.pop(company_id, None)

                # Clear cooldowns for this company
                cooldown_keys_to_remove = [
                    k for k in self._cooldowns
                    if k[0] == company_id
                ]
                for key in cooldown_keys_to_remove:
                    del self._cooldowns[key]

                # Clear notification log
                self._notification_log.pop(company_id, None)

                # Clear config
                self._configs.pop(company_id, None)

            logger.info(
                "escalation_company_data_cleared",
                company_id=company_id,
                escalations_removed=len(escalation_ids),
            )
        except Exception:
            logger.exception(
                "clear_company_data_crashed",
                company_id=company_id,
            )
