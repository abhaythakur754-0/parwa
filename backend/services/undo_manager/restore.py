"""
PARWA State Restoration Service.

Provides state restoration capabilities for undo operations.
Works with the Undo Manager and Snapshot services to revert system state.

Features:
- Restore system to previous state
- Validate restoration is safe
- Log all restoration attempts
- Support partial restoration
"""
from typing import Any, Dict, Optional, List, Callable, Awaitable, Set
from datetime import datetime, timezone
from uuid import uuid4
from dataclasses import dataclass, field
from enum import Enum
import json
import asyncio
from copy import deepcopy

from shared.core_functions.logger import get_logger
from shared.core_functions.audit_trail import log_financial_action

logger = get_logger(__name__)


class RestorationStatus(str, Enum):
    """Status of restoration operations."""
    PENDING = "pending"
    VALIDATING = "validating"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RestorationType(str, Enum):
    """Types of restoration."""
    FULL = "full"
    PARTIAL = "partial"
    INCREMENTAL = "incremental"


class ValidationLevel(str, Enum):
    """Validation levels for restoration."""
    NONE = "none"
    BASIC = "basic"
    STRICT = "strict"
    PARANOID = "paranoid"


@dataclass
class RestorationAttempt:
    """Records a restoration attempt."""
    attempt_id: str
    snapshot_id: str
    action_id: str
    company_id: str
    restoration_type: RestorationType
    validation_level: ValidationLevel
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: RestorationStatus = RestorationStatus.PENDING
    restored_state: Optional[Dict[str, Any]] = None
    validation_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    performed_by: Optional[str] = None
    rollback_data: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Result of restoration validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    blocked_reasons: List[str] = field(default_factory=list)


class StateValidator:
    """
    Validates state before and during restoration.

    Features:
    - Check state integrity
    - Validate relationships
    - Check for conflicts
    - Financial state protection
    """

    def __init__(self, validation_level: ValidationLevel = ValidationLevel.BASIC):
        """
        Initialize State Validator.

        Args:
            validation_level: Level of validation to perform
        """
        self._validation_level = validation_level
        self._custom_validators: Dict[str, Callable[..., Awaitable[ValidationResult]]] = {}

        logger.info({
            "event": "state_validator_initialized",
            "validation_level": validation_level.value,
        })

    async def validate_for_restoration(
        self,
        current_state: Dict[str, Any],
        target_state: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate that restoration is safe to perform.

        Args:
            current_state: Current system state
            target_state: Target state to restore to
            context: Additional context (company_id, action_type, etc.)

        Returns:
            ValidationResult with status and any errors/warnings
        """
        errors: List[str] = []
        warnings: List[str] = []
        blocked_reasons: List[str] = []

        # Skip validation if level is NONE
        if self._validation_level == ValidationLevel.NONE:
            return ValidationResult(is_valid=True)

        # Basic validation
        if self._validation_level in [ValidationLevel.BASIC, ValidationLevel.STRICT, ValidationLevel.PARANOID]:
            basic_errors = await self._basic_validation(current_state, target_state, context)
            errors.extend(basic_errors)

        # Strict validation
        if self._validation_level in [ValidationLevel.STRICT, ValidationLevel.PARANOID]:
            strict_errors, strict_warnings = await self._strict_validation(current_state, target_state, context)
            errors.extend(strict_errors)
            warnings.extend(strict_warnings)

        # Paranoid validation
        if self._validation_level == ValidationLevel.PARANOID:
            paranoid_errors, paranoid_warnings = await self._paranoid_validation(current_state, target_state, context)
            errors.extend(paranoid_errors)
            warnings.extend(paranoid_warnings)

        # Run custom validators
        action_type = context.get("action_type", "")
        if action_type in self._custom_validators:
            custom_result = await self._custom_validators[action_type](current_state, target_state, context)
            errors.extend(custom_result.errors)
            warnings.extend(custom_result.warnings)
            blocked_reasons.extend(custom_result.blocked_reasons)

        # Check for financial data changes
        if self._has_financial_changes(current_state, target_state):
            blocked_reasons.append("Restoration involves financial data changes - requires approval")

        is_valid = len(errors) == 0 and len(blocked_reasons) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            blocked_reasons=blocked_reasons,
        )

    async def _basic_validation(
        self,
        current_state: Dict[str, Any],
        target_state: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[str]:
        """Perform basic validation checks."""
        errors = []

        # Check required keys exist
        required_keys = ["id"]
        for key in required_keys:
            if key not in target_state:
                errors.append(f"Target state missing required key: {key}")

        return errors

    async def _strict_validation(
        self,
        current_state: Dict[str, Any],
        target_state: Dict[str, Any],
        context: Dict[str, Any]
    ) -> tuple[List[str], List[str]]:
        """Perform strict validation checks."""
        errors = []
        warnings = []

        # Check for state structure mismatch
        current_keys = set(current_state.keys())
        target_keys = set(target_state.keys())

        missing_keys = target_keys - current_keys
        if missing_keys:
            warnings.append(f"Target state has keys not in current state: {missing_keys}")

        # Check data types match
        for key in current_keys & target_keys:
            current_type = type(current_state[key])
            target_type = type(target_state[key])
            if current_type != target_type:
                errors.append(f"Type mismatch for key '{key}': {current_type.__name__} vs {target_type.__name__}")

        return errors, warnings

    async def _paranoid_validation(
        self,
        current_state: Dict[str, Any],
        target_state: Dict[str, Any],
        context: Dict[str, Any]
    ) -> tuple[List[str], List[str]]:
        """Perform paranoid validation checks."""
        errors = []
        warnings = []

        # Check for any references to other entities that might be affected
        referenced_entities = self._extract_references(target_state)
        if referenced_entities:
            warnings.append(f"Target state references entities: {referenced_entities}")

        # Check for cascading effects
        if "cascade" in context and context["cascade"]:
            warnings.append("Restoration may have cascading effects on related entities")

        return errors, warnings

    def _has_financial_changes(
        self,
        current_state: Dict[str, Any],
        target_state: Dict[str, Any]
    ) -> bool:
        """Check if restoration involves financial data changes."""
        financial_keys = {
            "amount", "balance", "credit", "debit",
            "refund_amount", "charge_amount", "payment_amount",
            "subscription_tier", "price", "cost"
        }

        for key in financial_keys:
            if key in current_state or key in target_state:
                if current_state.get(key) != target_state.get(key):
                    return True

        return False

    def _extract_references(self, state: Dict[str, Any]) -> Set[str]:
        """Extract entity references from state."""
        references = set()
        ref_keys = {"user_id", "company_id", "ticket_id", "order_id", "subscription_id"}

        def extract(obj: Any):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in ref_keys and isinstance(value, str):
                        references.add(f"{key}:{value}")
                    else:
                        extract(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract(item)

        extract(state)
        return references

    def register_validator(
        self,
        action_type: str,
        validator: Callable[..., Awaitable[ValidationResult]]
    ) -> None:
        """Register a custom validator for an action type."""
        self._custom_validators[action_type] = validator


class StateRestorer:
    """
    Handles state restoration operations.

    Features:
    - Restore system to previous state
    - Validate restoration is safe
    - Log all restoration attempts
    - Support partial restoration
    - Rollback on failure

    Example:
        restorer = StateRestorer()
        validator = StateValidator(validation_level=ValidationLevel.STRICT)

        # Validate first
        result = await restorer.validate_and_restore({
            "snapshot_id": "snap_123",
            "action_id": "action_456",
            "company_id": "comp_789",
            "performed_by": "user_001",
        })

        if result["success"]:
            print("Restoration completed!")
    """

    def __init__(
        self,
        validator: Optional[StateValidator] = None,
        validation_level: ValidationLevel = ValidationLevel.BASIC,
    ):
        """
        Initialize State Restorer.

        Args:
            validator: StateValidator instance
            validation_level: Default validation level
        """
        self._validator = validator or StateValidator(validation_level)
        self._restoration_attempts: Dict[str, RestorationAttempt] = {}
        self._restoration_handlers: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {}

        logger.info({
            "event": "state_restorer_initialized",
            "validation_level": validation_level.value,
        })

    async def validate_and_restore(
        self,
        restoration_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate and perform state restoration.

        Args:
            restoration_data: Dict with:
                - snapshot_id: ID of snapshot to restore
                - action_id: ID of action being undone
                - company_id: Company identifier
                - current_state: Current system state
                - target_state: Target state to restore to
                - performed_by: User performing restoration
                - restoration_type: Type of restoration
                - validation_level: Level of validation

        Returns:
            Dict with restoration result
        """
        attempt_id = f"restore_{uuid4().hex[:16]}"
        started_at = datetime.now(timezone.utc)

        snapshot_id = restoration_data.get("snapshot_id", "")
        action_id = restoration_data.get("action_id", "")
        company_id = restoration_data.get("company_id", "")
        performed_by = restoration_data.get("performed_by")

        restoration_type_str = restoration_data.get("restoration_type", "full")
        try:
            restoration_type = RestorationType(restoration_type_str)
        except ValueError:
            restoration_type = RestorationType.FULL

        validation_level_str = restoration_data.get("validation_level", "basic")
        try:
            validation_level = ValidationLevel(validation_level_str)
        except ValueError:
            validation_level = ValidationLevel.BASIC

        # Create attempt record
        attempt = RestorationAttempt(
            attempt_id=attempt_id,
            snapshot_id=snapshot_id,
            action_id=action_id,
            company_id=company_id,
            restoration_type=restoration_type,
            validation_level=validation_level,
            started_at=started_at,
            performed_by=performed_by,
        )

        self._restoration_attempts[attempt_id] = attempt

        try:
            # Get states
            current_state = restoration_data.get("current_state", {})
            target_state = restoration_data.get("target_state", {})

            # If target_state not provided, try to get from snapshot
            if not target_state and snapshot_id:
                # In production, this would fetch from SnapshotStorage
                target_state = restoration_data.get("snapshot_state", {})

            # Validation phase
            attempt.status = RestorationStatus.VALIDATING
            logger.info({
                "event": "restoration_validating",
                "attempt_id": attempt_id,
                "validation_level": validation_level.value,
            })

            validation_result = await self._validator.validate_for_restoration(
                current_state=current_state,
                target_state=target_state,
                context={
                    "company_id": company_id,
                    "action_id": action_id,
                    "action_type": restoration_data.get("action_type", ""),
                    "performed_by": performed_by,
                },
            )

            if not validation_result.is_valid:
                attempt.status = RestorationStatus.FAILED
                attempt.validation_errors = validation_result.errors
                attempt.warnings = validation_result.warnings

                logger.warning({
                    "event": "restoration_validation_failed",
                    "attempt_id": attempt_id,
                    "errors": validation_result.errors,
                    "blocked_reasons": validation_result.blocked_reasons,
                })

                return {
                    "success": False,
                    "status": RestorationStatus.FAILED.value,
                    "attempt_id": attempt_id,
                    "errors": validation_result.errors,
                    "blocked_reasons": validation_result.blocked_reasons,
                }

            # Store rollback data
            attempt.rollback_data = deepcopy(current_state)

            # Restoration phase
            attempt.status = RestorationStatus.IN_PROGRESS
            logger.info({
                "event": "restoration_in_progress",
                "attempt_id": attempt_id,
                "restoration_type": restoration_type.value,
            })

            # Perform actual restoration
            restore_result = await self._perform_restoration(
                current_state=current_state,
                target_state=target_state,
                restoration_type=restoration_type,
                restoration_data=restoration_data,
            )

            if not restore_result.get("success"):
                # Attempt rollback
                await self._rollback_restoration(attempt)
                return {
                    "success": False,
                    "status": RestorationStatus.ROLLED_BACK.value,
                    "attempt_id": attempt_id,
                    "error": restore_result.get("error", "Restoration failed"),
                }

            # Success
            attempt.status = RestorationStatus.COMPLETED
            attempt.completed_at = datetime.now(timezone.utc)
            attempt.restored_state = restore_result.get("restored_state")

            logger.info({
                "event": "restoration_completed",
                "attempt_id": attempt_id,
                "company_id": company_id,
                "performed_by": performed_by,
                "duration_ms": int((attempt.completed_at - attempt.started_at).total_seconds() * 1000),
            })

            return {
                "success": True,
                "status": RestorationStatus.COMPLETED.value,
                "attempt_id": attempt_id,
                "restored_state": attempt.restored_state,
                "warnings": validation_result.warnings,
            }

        except Exception as e:
            attempt.status = RestorationStatus.FAILED
            attempt.completed_at = datetime.now(timezone.utc)
            attempt.validation_errors = [str(e)]

            logger.error({
                "event": "restoration_exception",
                "attempt_id": attempt_id,
                "error": str(e),
            })

            return {
                "success": False,
                "status": RestorationStatus.FAILED.value,
                "attempt_id": attempt_id,
                "error": str(e),
            }

    async def _perform_restoration(
        self,
        current_state: Dict[str, Any],
        target_state: Dict[str, Any],
        restoration_type: RestorationType,
        restoration_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Perform the actual state restoration.

        Args:
            current_state: Current state
            target_state: Target state
            restoration_type: Type of restoration
            restoration_data: Additional restoration data

        Returns:
            Restoration result
        """
        action_type = restoration_data.get("action_type", "")

        # Check for custom handler
        if action_type in self._restoration_handlers:
            handler = self._restoration_handlers[action_type]
            return await handler(current_state, target_state, restoration_data)

        # Default restoration based on type
        if restoration_type == RestorationType.FULL:
            return await self._full_restoration(current_state, target_state, restoration_data)
        elif restoration_type == RestorationType.PARTIAL:
            return await self._partial_restoration(current_state, target_state, restoration_data)
        elif restoration_type == RestorationType.INCREMENTAL:
            return await self._incremental_restoration(current_state, target_state, restoration_data)

        return {
            "success": False,
            "error": f"Unknown restoration type: {restoration_type}",
        }

    async def _full_restoration(
        self,
        current_state: Dict[str, Any],
        target_state: Dict[str, Any],
        restoration_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform full state restoration."""
        # In production, this would actually restore state in the database
        # For now, we return the target state as restored

        logger.debug({
            "event": "full_restoration_performed",
            "keys_restored": list(target_state.keys()),
        })

        return {
            "success": True,
            "restored_state": deepcopy(target_state),
            "restoration_type": RestorationType.FULL.value,
        }

    async def _partial_restoration(
        self,
        current_state: Dict[str, Any],
        target_state: Dict[str, Any],
        restoration_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform partial state restoration (only specified keys)."""
        keys_to_restore = restoration_data.get("keys_to_restore", list(target_state.keys()))

        restored_state = deepcopy(current_state)
        for key in keys_to_restore:
            if key in target_state:
                restored_state[key] = deepcopy(target_state[key])

        logger.debug({
            "event": "partial_restoration_performed",
            "keys_restored": keys_to_restore,
        })

        return {
            "success": True,
            "restored_state": restored_state,
            "keys_restored": keys_to_restore,
            "restoration_type": RestorationType.PARTIAL.value,
        }

    async def _incremental_restoration(
        self,
        current_state: Dict[str, Any],
        target_state: Dict[str, Any],
        restoration_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform incremental restoration (apply changes step by step)."""
        # Calculate diff
        changes = restoration_data.get("changes", {})
        if not changes:
            # Calculate diff if not provided
            changes = self._calculate_changes(current_state, target_state)

        restored_state = deepcopy(current_state)

        # Apply changes incrementally
        for change in changes:
            if change.get("type") == "set":
                restored_state[change["key"]] = deepcopy(change["value"])
            elif change.get("type") == "delete":
                restored_state.pop(change["key"], None)

        logger.debug({
            "event": "incremental_restoration_performed",
            "changes_count": len(changes),
        })

        return {
            "success": True,
            "restored_state": restored_state,
            "changes_applied": len(changes),
            "restoration_type": RestorationType.INCREMENTAL.value,
        }

    def _calculate_changes(
        self,
        current_state: Dict[str, Any],
        target_state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Calculate changes needed to transform current to target state."""
        changes = []

        current_keys = set(current_state.keys())
        target_keys = set(target_state.keys())

        # Additions and modifications
        for key in target_keys:
            if key not in current_state:
                changes.append({"type": "set", "key": key, "value": target_state[key]})
            elif current_state[key] != target_state[key]:
                changes.append({"type": "set", "key": key, "value": target_state[key]})

        # Deletions
        for key in current_keys - target_keys:
            changes.append({"type": "delete", "key": key})

        return changes

    async def _rollback_restoration(self, attempt: RestorationAttempt) -> None:
        """Rollback a failed restoration."""
        if not attempt.rollback_data:
            logger.warning({
                "event": "rollback_no_data",
                "attempt_id": attempt.attempt_id,
            })
            return

        logger.info({
            "event": "restoration_rollback",
            "attempt_id": attempt.attempt_id,
        })

        # In production, this would restore the rollback_data to the database
        attempt.status = RestorationStatus.ROLLED_BACK
        attempt.completed_at = datetime.now(timezone.utc)

    def register_restoration_handler(
        self,
        action_type: str,
        handler: Callable[..., Awaitable[Dict[str, Any]]]
    ) -> None:
        """Register a custom restoration handler for an action type."""
        self._restoration_handlers[action_type] = handler
        logger.info({
            "event": "restoration_handler_registered",
            "action_type": action_type,
        })

    async def get_restoration_attempt(
        self,
        attempt_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get details of a restoration attempt.

        Args:
            attempt_id: Restoration attempt ID

        Returns:
            Attempt details or None if not found
        """
        attempt = self._restoration_attempts.get(attempt_id)
        if not attempt:
            return None

        return {
            "attempt_id": attempt.attempt_id,
            "snapshot_id": attempt.snapshot_id,
            "action_id": attempt.action_id,
            "company_id": attempt.company_id,
            "restoration_type": attempt.restoration_type.value,
            "validation_level": attempt.validation_level.value,
            "status": attempt.status.value,
            "started_at": attempt.started_at.isoformat(),
            "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
            "performed_by": attempt.performed_by,
            "validation_errors": attempt.validation_errors,
            "warnings": attempt.warnings,
        }

    async def get_restoration_history(
        self,
        company_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get restoration history for a company.

        Args:
            company_id: Company identifier
            limit: Maximum number of attempts to return

        Returns:
            List of restoration attempts
        """
        attempts = [
            attempt for attempt in self._restoration_attempts.values()
            if attempt.company_id == company_id
        ]

        # Sort by started_at descending
        attempts.sort(key=lambda x: x.started_at, reverse=True)

        return [
            {
                "attempt_id": a.attempt_id,
                "action_id": a.action_id,
                "status": a.status.value,
                "started_at": a.started_at.isoformat(),
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                "performed_by": a.performed_by,
            }
            for a in attempts[:limit]
        ]

    async def log_restoration_attempt(
        self,
        attempt_id: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a restoration attempt for audit purposes.

        Args:
            attempt_id: Restoration attempt ID
            additional_data: Additional data to log
        """
        attempt = self._restoration_attempts.get(attempt_id)
        if not attempt:
            return

        log_data = {
            "event": "restoration_attempt_logged",
            "attempt_id": attempt_id,
            "snapshot_id": attempt.snapshot_id,
            "action_id": attempt.action_id,
            "company_id": attempt.company_id,
            "status": attempt.status.value,
            "performed_by": attempt.performed_by,
            "started_at": attempt.started_at.isoformat(),
            "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
        }

        if additional_data:
            log_data.update(additional_data)

        logger.info(log_data)

        # If financial data involved, log to audit trail
        if attempt.restored_state and self._has_financial_data(attempt.restored_state):
            log_financial_action(
                action_type="state_restoration",
                amount=0.0,  # No direct financial impact from restoration itself
                target_id=attempt.action_id,
                user_id=attempt.performed_by or "system",
                metadata={
                    "attempt_id": attempt_id,
                    "snapshot_id": attempt.snapshot_id,
                    "restoration_type": attempt.restoration_type.value,
                    "note": "State restoration involving financial data",
                },
            )

    def _has_financial_data(self, state: Dict[str, Any]) -> bool:
        """Check if state contains financial data."""
        financial_keys = {
            "amount", "balance", "credit", "debit",
            "refund_amount", "charge_amount", "payment_amount",
            "subscription_tier", "price", "cost"
        }

        def check(obj: Any) -> bool:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in financial_keys:
                        return True
                    if check(value):
                        return True
            elif isinstance(obj, list):
                for item in obj:
                    if check(item):
                        return True
            return False

        return check(state)


# Global instances
_validator: Optional[StateValidator] = None
_restorer: Optional[StateRestorer] = None


def get_state_validator(
    validation_level: ValidationLevel = ValidationLevel.BASIC
) -> StateValidator:
    """Get or create the global StateValidator instance."""
    global _validator
    if _validator is None:
        _validator = StateValidator(validation_level)
    return _validator


def get_state_restorer(
    validation_level: ValidationLevel = ValidationLevel.BASIC
) -> StateRestorer:
    """Get or create the global StateRestorer instance."""
    global _restorer
    if _restorer is None:
        _restorer = StateRestorer(validator=get_state_validator(validation_level))
    return _restorer
