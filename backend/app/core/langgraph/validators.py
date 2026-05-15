"""
ParwaGraphState Validators — State Transition Validation & Sanitization

This module provides runtime validation for state transitions in the PARWA
LangGraph system. Because ParwaGraphState is a plain TypedDict, any node
can write any value to any field. These validators enforce constraints on
the critical enumerated and bounded fields.

Design Principles:
  1. Never raise exceptions — return errors as strings (BC-008)
  2. Only validate fields present in the update dict (partial updates)
  3. Log warnings for invalid values
  4. Correct invalid values to safe defaults where possible (clamping)
  5. For enumerated fields, fall back to the first (safest) allowed value
  6. For bounded numeric fields, clamp to [min, max]

Validated Fields (13):
  - variant_tier          : "mini" | "pro" | "high"
  - channel               : "email" | "sms" | "voice" | "chat" | "api"
  - intent                : "faq" | "refund" | "technical" | "billing" | "complaint" | "escalation" | "general" | "greeting"
  - action_type           : "informational" | "monetary" | "destructive" | "escalation"
  - approval_decision     : "approved" | "rejected" | "needs_human_approval" | "auto_approved" | ""
  - system_mode           : "auto" | "supervised" | "shadow" | "paused"
  - delivery_status       : "pending" | "sent" | "delivered" | "failed" | "bounced" | ""
  - emergency_state       : "normal" | "yellow_alert" | "red_alert" | "full_stop"
  - agent_confidence      : float in [0.0, 1.0]
  - complexity_score      : float in [0.0, 1.0]
  - sentiment_score       : float in [0.0, 1.0]
  - urgency               : "low" | "medium" | "high" | "critical"
  - circuit_breaker_state : "closed" | "open" | "half_open"

Usage in Nodes:
  from app.core.langgraph.validators import validate_state_transition, sanitize_state_update
  from app.core.langgraph.state import validate_and_sanitize_node_output

  # Option 1: Validate only (check before writing)
  errors = validate_state_transition(my_update)
  if errors:
      logger.warning("state_validation_errors", errors=errors)

  # Option 2: Sanitize (auto-correct invalid values)
  clean_update = sanitize_state_update(my_update)

  # Option 3: Full helper (validate + sanitize + log)
  clean_update = validate_and_sanitize_node_output("my_node", my_update)
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Tuple

from app.logger import get_logger

logger = get_logger("langgraph_validators")


# ══════════════════════════════════════════════════════════════════
# FIELD CONSTRAINT DEFINITIONS
# ══════════════════════════════════════════════════════════════════

# Enumerated fields: {field_name: (allowed_values_tuple, default_value)}
ENUM_CONSTRAINTS: Dict[str, Tuple[Tuple[str, ...], str]] = {
    "variant_tier": (
        ("mini", "pro", "high"),
        "mini",  # safest fallback — minimal permissions
    ),
    "channel": (
        ("email", "sms", "voice", "chat", "api"),
        "chat",  # safest fallback — most common interactive channel
    ),
    "intent": (
        ("faq", "refund", "technical", "billing", "complaint", "escalation", "general", "greeting"),
        "general",  # safest fallback — no risky action implied
    ),
    "action_type": (
        ("informational", "monetary", "destructive", "escalation"),
        "informational",  # safest fallback — no side effects
    ),
    "approval_decision": (
        ("approved", "rejected", "needs_human_approval", "auto_approved", ""),
        "",  # safest fallback — no decision made yet
    ),
    "system_mode": (
        ("auto", "supervised", "shadow", "paused"),
        "auto",  # normal operating mode
    ),
    "delivery_status": (
        ("pending", "sent", "delivered", "failed", "bounced", ""),
        "pending",  # safest fallback — hasn't been sent yet
    ),
    "emergency_state": (
        ("normal", "yellow_alert", "red_alert", "full_stop"),
        "normal",  # safest fallback — no emergency
    ),
    "urgency": (
        ("low", "medium", "high", "critical"),
        "medium",  # safest fallback — not ignored, not panicked
    ),
    "circuit_breaker_state": (
        ("closed", "open", "half_open"),
        "closed",  # safest fallback — circuit is healthy
    ),
}

# Bounded numeric fields: {field_name: (min_value, max_value)}
RANGE_CONSTRAINTS: Dict[str, Tuple[float, float]] = {
    "agent_confidence": (0.0, 1.0),
    "complexity_score": (0.0, 1.0),
    "sentiment_score": (0.0, 1.0),
}

# Combined set of all validated field names for quick lookup
VALIDATED_FIELDS = set(ENUM_CONSTRAINTS.keys()) | set(RANGE_CONSTRAINTS.keys())


# ══════════════════════════════════════════════════════════════════
# CORE VALIDATION: validate_state_transition
# ══════════════════════════════════════════════════════════════════


def validate_state_transition(update: Dict[str, Any]) -> List[str]:
    """
    Validate a partial state update dict against known constraints.

    Checks only fields that are present in the update dict. Returns a list
    of validation error strings — an empty list means all present fields
    are valid.

    This function NEVER raises exceptions (BC-008). Any unexpected types
    or values are reported as error strings.

    Args:
        update: Partial state update dict (only contains fields being written)

    Returns:
        List of validation error strings. Empty list = all fields valid.

    Examples:
        >>> validate_state_transition({"variant_tier": "pro"})
        []

        >>> validate_state_transition({"variant_tier": "enterprise"})
        ["variant_tier: invalid value 'enterprise', must be one of: mini, pro, high"]

        >>> validate_state_transition({"agent_confidence": 1.5})
        ["agent_confidence: value 1.5 exceeds maximum 1.0"]
    """
    errors: List[str] = []

    for field_name, value in update.items():
        # Skip fields we don't validate
        if field_name not in VALIDATED_FIELDS:
            continue

        # --- Enumerated field validation ---
        if field_name in ENUM_CONSTRAINTS:
            allowed_values, _default = ENUM_CONSTRAINTS[field_name]
            if not isinstance(value, str):
                errors.append(
                    f"{field_name}: expected str, got {type(value).__name__} ({value!r})"
                )
                continue
            if value not in allowed_values:
                errors.append(
                    f"{field_name}: invalid value '{value}', "
                    f"must be one of: {', '.join(allowed_values)}"
                )

        # --- Bounded numeric field validation ---
        elif field_name in RANGE_CONSTRAINTS:
            min_val, max_val = RANGE_CONSTRAINTS[field_name]
            if not isinstance(value, (int, float)):
                errors.append(
                    f"{field_name}: expected numeric, got {type(value).__name__} ({value!r})"
                )
                continue
            # bool is a subclass of int in Python — reject it explicitly
            if isinstance(value, bool):
                errors.append(
                    f"{field_name}: expected numeric, got bool ({value!r})"
                )
                continue
            if value < min_val:
                errors.append(
                    f"{field_name}: value {value} is below minimum {min_val}"
                )
            elif value > max_val:
                errors.append(
                    f"{field_name}: value {value} exceeds maximum {max_val}"
                )

    # Log warnings if any errors found
    if errors:
        logger.warning(
            "state_transition_validation_errors",
            errors=errors,
            fields_validated=list(update.keys()),
        )

    return errors


# ══════════════════════════════════════════════════════════════════
# CORE SANITIZATION: sanitize_state_update
# ══════════════════════════════════════════════════════════════════


def sanitize_state_update(update: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize a partial state update dict by correcting invalid values
    to safe defaults.

    For enumerated fields:
      - Invalid string values are replaced with the field's safe default
      - Non-string values are replaced with the field's safe default

    For bounded numeric fields:
      - Values below minimum are clamped to minimum
      - Values above maximum are clamped to maximum
      - Non-numeric values are replaced with the minimum (0.0)
      - Boolean values are replaced with the minimum (0.0)

    Each correction is logged as a warning.

    This function NEVER raises exceptions (BC-008). If anything goes
    wrong, the original value is kept unchanged.

    Args:
        update: Partial state update dict (only contains fields being written)

    Returns:
        New dict with the same keys but invalid values corrected to safe defaults.

    Examples:
        >>> sanitize_state_update({"variant_tier": "enterprise"})
        {"variant_tier": "mini"}  # with warning logged

        >>> sanitize_state_update({"agent_confidence": 1.5})
        {"agent_confidence": 1.0}  # with warning logged

        >>> sanitize_state_update({"urgency": "high", "message": "hello"})
        {"urgency": "high", "message": "hello"}  # unchanged
    """
    sanitized = copy.deepcopy(update)

    for field_name, value in update.items():
        # Skip fields we don't validate
        if field_name not in VALIDATED_FIELDS:
            continue

        # --- Enumerated field sanitization ---
        if field_name in ENUM_CONSTRAINTS:
            allowed_values, default_value = ENUM_CONSTRAINTS[field_name]

            if not isinstance(value, str) or value not in allowed_values:
                original_repr = repr(value) if not isinstance(value, str) else f"'{value}'"
                logger.warning(
                    "state_field_sanitized",
                    field=field_name,
                    original=original_repr,
                    sanitized=default_value,
                    reason=(
                        f"not a string" if not isinstance(value, str)
                        else f"not in allowed values {allowed_values}"
                    ),
                )
                sanitized[field_name] = default_value

        # --- Bounded numeric field sanitization ---
        elif field_name in RANGE_CONSTRAINTS:
            min_val, max_val = RANGE_CONSTRAINTS[field_name]

            # Reject bools (they're int subclass in Python)
            if isinstance(value, bool):
                logger.warning(
                    "state_field_sanitized",
                    field=field_name,
                    original=repr(value),
                    sanitized=min_val,
                    reason="bool is not a valid numeric score",
                )
                sanitized[field_name] = min_val
                continue

            if not isinstance(value, (int, float)):
                logger.warning(
                    "state_field_sanitized",
                    field=field_name,
                    original=repr(value),
                    sanitized=min_val,
                    reason=f"expected numeric, got {type(value).__name__}",
                )
                sanitized[field_name] = min_val
                continue

            # Clamp to range
            if value < min_val:
                logger.warning(
                    "state_field_sanitized",
                    field=field_name,
                    original=value,
                    sanitized=min_val,
                    reason=f"below minimum {min_val}",
                )
                sanitized[field_name] = min_val
            elif value > max_val:
                logger.warning(
                    "state_field_sanitized",
                    field=field_name,
                    original=value,
                    sanitized=max_val,
                    reason=f"exceeds maximum {max_val}",
                )
                sanitized[field_name] = max_val

    return sanitized


# ══════════════════════════════════════════════════════════════════
# UTILITY: Get constraint info for a field
# ══════════════════════════════════════════════════════════════════


def get_field_constraints(field_name: str) -> Dict[str, Any] | None:
    """
    Get constraint information for a validated field.

    Args:
        field_name: Name of the state field

    Returns:
        Dict with constraint info, or None if the field is not validated.

    Examples:
        >>> get_field_constraints("variant_tier")
        {"type": "enum", "allowed": ("mini", "pro", "high"), "default": "mini"}

        >>> get_field_constraints("agent_confidence")
        {"type": "range", "min": 0.0, "max": 1.0}
    """
    if field_name in ENUM_CONSTRAINTS:
        allowed, default = ENUM_CONSTRAINTS[field_name]
        return {
            "type": "enum",
            "allowed": allowed,
            "default": default,
        }
    elif field_name in RANGE_CONSTRAINTS:
        min_val, max_val = RANGE_CONSTRAINTS[field_name]
        return {
            "type": "range",
            "min": min_val,
            "max": max_val,
        }
    return None


def get_all_validated_fields() -> Dict[str, Dict[str, Any]]:
    """
    Get constraint information for all validated fields.

    Returns:
        Dict mapping field name to constraint info.
    """
    result: Dict[str, Dict[str, Any]] = {}
    for field_name in VALIDATED_FIELDS:
        info = get_field_constraints(field_name)
        if info is not None:
            result[field_name] = info
    return result
