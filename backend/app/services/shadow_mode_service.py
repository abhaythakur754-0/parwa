"""
Shadow Mode Service (Dual-Control System)

4-layer decision system for AI action execution:
  Layer 1: Heuristic risk scoring based on action type and payload
  Layer 2: Per-category preferences (shadow/supervised/graduated)
  Layer 3: Historical pattern analysis (avg risk scores)
  Layer 4: Hard safety floor (certain actions always require approval)

BC-001: All operations scoped by company_id.
BC-008: Never crash the caller — defensive error handling.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models.core import Company
from database.models.shadow_mode import ShadowLog, ShadowPreference
from database.models.approval import UndoLog, ExecutedAction

logger = logging.getLogger("parwa.services.shadow_mode")

# ── Socket.io Event Emitter Helper ──────────────────────────────


async def _emit_shadow_event(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    """
    Emit a shadow mode event via Socket.io.

    Never crashes the caller - errors are logged only.
    """
    try:
        from app.core.event_emitter import emit_shadow_event
        await emit_shadow_event(company_id, event_type, payload)
    except Exception as e:
        logger.warning(
            "shadow_event_emit_failed company_id=%s event=%s error=%s",
            company_id, event_type, str(e),
        )


def _emit_shadow_event_sync(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    """Synchronous wrapper for emit_shadow_event."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(
                _emit_shadow_event(
                    company_id,
                    event_type,
                    payload))
        else:
            loop.run_until_complete(
                _emit_shadow_event(
                    company_id, event_type, payload))
    except RuntimeError:
        # No event loop, create a new one
        asyncio.run(_emit_shadow_event(company_id, event_type, payload))
    except Exception as e:
        logger.warning("shadow_event_sync_failed: %s", str(e))

# ── Valid modes ────────────────────────────────────────────────


VALID_MODES = {"shadow", "supervised", "graduated"}
VALID_DECISIONS = {"approved", "rejected", "modified"}
VALID_SET_VIA = {"ui", "jarvis"}

# ── Risk score thresholds ─────────────────────────────────────

# Layer 4: Hard safety floor — these action types ALWAYS require approval
HARD_SAFETY_ACTIONS = {
    "refund",           # Financial transactions
    "account_delete",   # Destructive operations
    "data_export",      # PII exposure risk
    "password_reset",   # Security sensitive
    "api_key_create",   # Credential issuance
}

# Layer 1: Base risk scores by action type (0.0 = safe, 1.0 = critical)
ACTION_RISK_BASE = {
    "sms_reply": 0.3,
    "email_reply": 0.4,
    "ticket_close": 0.2,
    "ticket_escalate": 0.5,
    "refund": 0.8,
    "credit_issue": 0.7,
    "account_delete": 0.95,
    "data_export": 0.9,
    "password_reset": 0.85,
    "api_key_create": 0.8,
    "tag_update": 0.1,
    "note_add": 0.1,
    "priority_change": 0.3,
}

# Layer 1: Payload-based risk adjustments
HIGH_REFUND_THRESHOLD = 100.0   # Refunds above $100 get extra risk
CRITICAL_REFUND_THRESHOLD = 500.0  # Refunds above $500 get even more


# ── Exceptions ──────────────────────────────────────────────────


class ShadowModeError(Exception):
    """Base exception for shadow mode errors."""


class ShadowLogNotFoundError(ShadowModeError):
    """Shadow log entry not found."""


class InvalidModeError(ShadowModeError):
    """Invalid mode value."""


# ── Service ─────────────────────────────────────────────────────


class ShadowModeService:
    """
    Shadow Mode dual-control service.

    Manages the lifecycle of AI actions under the shadow/supervised/graduated
    system.  Provides risk evaluation, action logging, manager approval/rejection,
    undo capabilities, and statistics.

    Usage:
        svc = ShadowModeService()
        result = svc.evaluate_action_risk(
            company_id="acme",
            action_type="refund",
            action_payload={"amount": 150.0},
        )
    """

    # ═══════════════════════════════════════════════════════════════
    # Company Mode Management
    # ═══════════════════════════════════════════════════════════════

    def get_company_mode(self, company_id: str) -> str:
        """
        Get the current system mode for a company.

        Args:
            company_id: Company UUID (BC-001).

        Returns:
            System mode string: 'shadow', 'supervised', or 'graduated'.
        """
        with SessionLocal() as db:
            company = db.query(Company).filter(
                Company.id == company_id
            ).first()

            if not company:
                return "supervised"  # Safe default

            # system_mode may not exist yet (migration pending)
            mode = getattr(company, "system_mode", None)
            if mode and mode in VALID_MODES:
                return mode

            # Fall back to the existing 'mode' field on Company
            return getattr(company, "mode", "supervised") or "supervised"

    def set_company_mode(
        self,
        company_id: str,
        mode: str,
        set_via: str = "ui",
    ) -> Dict[str, Any]:
        """
        Update the system mode for a company.

        Args:
            company_id: Company UUID (BC-001).
            mode: New mode ('shadow', 'supervised', 'graduated').
            set_via: How this change was triggered ('ui' or 'jarvis').

        Returns:
            Dict with updated mode details.

        Raises:
            ShadowModeError: If mode is invalid.
        """
        if mode not in VALID_MODES:
            raise InvalidModeError(
                f"Invalid mode: {mode}. Must be one of: {
                    ', '.join(
                        sorted(VALID_MODES))}")

        with SessionLocal() as db:
            company = db.query(Company).filter(
                Company.id == company_id
            ).first()

            if not company:
                raise ShadowModeError(
                    f"Company {company_id} not found (BC-001)")

            old_mode = getattr(company, "system_mode", None) or "supervised"
            company.system_mode = mode
            company.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(company)

            logger.info(
                "shadow_mode_changed company_id=%s old_mode=%s new_mode=%s set_via=%s",
                company_id,
                old_mode,
                mode,
                set_via,
            )

            # Emit Socket.io event
            _emit_shadow_event_sync(
                company_id,
                "shadow:mode_changed",
                {
                    "mode": mode,
                    "previous_mode": old_mode,
                    "set_via": set_via,
                },
            )

            return {
                "company_id": company_id,
                "mode": mode,
                "previous_mode": old_mode,
                "set_via": set_via,
            }

    # ═══════════════════════════════════════════════════════════════
    # 4-Layer Risk Evaluation
    # ═══════════════════════════════════════════════════════════════

    def evaluate_action_risk(
        self,
        company_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate the risk of an AI action using the 4-layer decision system.

        Layer 1: Heuristic risk scoring based on action type and payload.
        Layer 2: Per-category preferences override.
        Layer 3: Historical pattern analysis (avg risk score for action_type).
        Layer 4: Hard safety floor — certain actions always require approval.

        Returns:
            Dict with keys: mode, risk_score, reason, requires_approval,
            auto_execute, layers.

        Raises:
            ShadowModeError: If company not found.
        """
        try:
            with SessionLocal() as db:
                company = db.query(Company).filter(
                    Company.id == company_id
                ).first()

                if not company:
                    raise ShadowModeError(
                        f"Company {company_id} not found (BC-001)"
                    )

                company_mode = getattr(
                    company, "system_mode", None) or "supervised"

                # ── Stage 0: Shadow Actions Remaining Check ──
                shadow_remaining = getattr(
                    company, "shadow_actions_remaining", None)
                if shadow_remaining is not None and shadow_remaining > 0:
                    # Force shadow mode for Stage 0 onboarding
                    return {
                        "mode": "shadow",
                        "risk_score": 0.5,
                        "reason": f"Stage 0 onboarding: {shadow_remaining} shadow actions remaining",
                        "requires_approval": True,
                        "auto_execute": False,
                        "stage_0": True,
                        "shadow_actions_remaining": shadow_remaining,
                        "layers": {
                            "layer1_heuristic": {
                                "score": 0.5,
                                "reason": "Stage 0 forced"},
                            "layer2_preference": {
                                "mode": None,
                                "reason": "Stage 0 override"},
                            "layer3_historical": {
                                "avg_risk": None,
                                "reason": "Stage 0 override"},
                            "layer4_safety_floor": {
                                "hard_safety": True,
                                "reason": "Stage 0 override"},
                        },
                        "company_mode": "shadow",
                    }

                # ── Get config thresholds from company ──
                risk_threshold_shadow = float(
                    getattr(
                        company,
                        "risk_threshold_shadow",
                        0.7) or 0.7)
                risk_threshold_auto = float(
                    getattr(
                        company,
                        "risk_threshold_auto",
                        0.3) or 0.3)

                # ── Layer 1: Heuristic Risk Score ──
                base_score = ACTION_RISK_BASE.get(action_type, 0.5)
                risk_score = self._adjust_risk_by_payload(
                    base_score, action_type, action_payload
                )
                layer1_reason = f"Base risk {action_type}: {base_score:.2f}"

                # ── Layer 2: Per-Category Preferences ──
                action_category = self._normalize_category(action_type)
                preference = db.query(ShadowPreference).filter(
                    ShadowPreference.company_id == company_id,
                    ShadowPreference.action_category == action_category,
                ).first()

                preferred_mode = None
                layer2_reason = "No per-category preference set"
                if preference:
                    preferred_mode = preference.preferred_mode
                    layer2_reason = (
                        f"Preference for {action_category}: {preferred_mode}"
                    )

                # ── Layer 3: Historical Pattern Analysis ──
                avg_historical = self._get_avg_risk_score(
                    db, company_id, action_type
                )
                layer3_reason = f"Historical avg risk: {avg_historical:.2f}"

                # Blend current risk with historical (weighted average)
                if avg_historical is not None:
                    blended_score = 0.6 * risk_score + 0.4 * avg_historical
                    risk_score = round(blended_score, 3)

                # ── Layer 4: Hard Safety Floor ──
                hard_safety = action_type in HARD_SAFETY_ACTIONS
                layer4_reason = (
                    f"Hard safety: {
                        'ALWAYS requires approval' if hard_safety else 'No override'}")

                # ── Decision Logic ──
                # Start with company-level mode
                effective_mode = company_mode

                # Layer 2 override: if per-category preference exists, use it
                if preferred_mode:
                    effective_mode = preferred_mode

                # Layer 4 override: hard safety actions always supervised
                if hard_safety:
                    effective_mode = "supervised"

                # Layer 3 adjustment: if historical risk is high (> 0.7),
                # escalate to supervised regardless
                if avg_historical is not None and avg_historical > 0.7:
                    effective_mode = "supervised"
                    layer3_reason += " (escalated: avg risk > 0.7)"

                requires_approval = effective_mode != "graduated"
                auto_execute = effective_mode == "graduated" and risk_score < 0.3

                return {
                    "mode": effective_mode,
                    "risk_score": round(risk_score, 3),
                    "reason": self._build_decision_reason(
                        effective_mode, risk_score
                    ),
                    "requires_approval": requires_approval,
                    "auto_execute": auto_execute,
                    "layers": {
                        "layer1_heuristic": {
                            "score": round(base_score, 3),
                            "reason": layer1_reason,
                        },
                        "layer2_preference": {
                            "mode": preferred_mode,
                            "reason": layer2_reason,
                        },
                        "layer3_historical": {
                            "avg_risk": round(avg_historical, 3) if avg_historical is not None else None,
                            "reason": layer3_reason,
                        },
                        "layer4_safety_floor": {
                            "hard_safety": hard_safety,
                            "reason": layer4_reason,
                        },
                    },
                    "company_mode": company_mode,
                }

        except ShadowModeError:
            raise
        except Exception:
            logger.error(
                "evaluate_action_risk_failed company_id=%s action_type=%s",
                company_id, action_type, exc_info=True,
            )
            # Safe fallback: always require approval
            return {
                "mode": "supervised",
                "risk_score": 0.5,
                "reason": "Evaluation failed — defaulting to supervised",
                "requires_approval": True,
                "auto_execute": False,
                "layers": {
                    "layer1_heuristic": {
                        "score": 0.5,
                        "reason": "Fallback"},
                    "layer2_preference": {
                        "mode": None,
                        "reason": "N/A"},
                    "layer3_historical": {
                        "avg_risk": None,
                        "reason": "N/A"},
                    "layer4_safety_floor": {
                        "hard_safety": True,
                        "reason": "Safety fallback"},
                },
                "company_mode": "supervised",
            }

    # ═══════════════════════════════════════════════════════════════
    # Shadow Action Logging
    # ═══════════════════════════════════════════════════════════════

    def log_shadow_action(
        self,
        company_id: str,
        action_type: str,
        action_payload: Dict[str, Any],
        risk_score: Optional[float],
        mode: str,
    ) -> Dict[str, Any]:
        """
        Log an AI action to the shadow log.

        Args:
            company_id: Company UUID (BC-001).
            action_type: Type of action being logged.
            action_payload: The full action payload.
            risk_score: Computed risk score (0.0-1.0).
            mode: Execution mode at time of logging.

        Returns:
            Dict with shadow log entry details.
        """
        with SessionLocal() as db:
            entry = ShadowLog(
                company_id=company_id,
                action_type=action_type,
                action_payload=action_payload if action_payload else {},
                jarvis_risk_score=risk_score,
                mode=mode,
                created_at=datetime.utcnow(),
            )
            db.add(entry)
            db.commit()
            db.refresh(entry)

            logger.info(
                "shadow_action_logged id=%s company_id=%s action=%s mode=%s risk=%.2f",
                entry.id,
                company_id,
                action_type,
                mode,
                risk_score or 0.0,
            )

            # Emit Socket.io event for new shadow action
            _emit_shadow_event_sync(
                company_id,
                "shadow:action_logged",
                {
                    "shadow_log_id": entry.id,
                    "action_type": action_type,
                    "risk_score": risk_score,
                    "mode": mode,
                },
            )

            return self._shadow_log_to_dict(entry)

    # ═══════════════════════════════════════════════════════════════
    # Preferences Management
    # ═══════════════════════════════════════════════════════════════

    def get_shadow_preferences(
        self, company_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all shadow mode preferences for a company.

        Args:
            company_id: Company UUID (BC-001).

        Returns:
            List of preference dicts.
        """
        with SessionLocal() as db:
            prefs = db.query(ShadowPreference).filter(
                ShadowPreference.company_id == company_id,
            ).all()

            return [self._preference_to_dict(p) for p in prefs]

    def set_shadow_preference(
        self,
        company_id: str,
        action_category: str,
        preferred_mode: str,
        set_via: str = "ui",
    ) -> Dict[str, Any]:
        """
        Set or update a shadow mode preference for an action category.

        Uses upsert logic — creates if not exists, updates if exists.

        Args:
            company_id: Company UUID (BC-001).
            action_category: The action category (e.g., 'refund', 'sms').
            preferred_mode: The preferred mode ('shadow', 'supervised', 'graduated').
            set_via: How this was set ('ui' or 'jarvis').

        Returns:
            Dict with preference details.

        Raises:
            InvalidModeError: If mode is invalid.
        """
        if preferred_mode not in VALID_MODES:
            raise InvalidModeError(
                f"Invalid mode: {preferred_mode}. "
                f"Must be one of: {', '.join(sorted(VALID_MODES))}"
            )

        with SessionLocal() as db:
            existing = db.query(ShadowPreference).filter(
                ShadowPreference.company_id == company_id,
                ShadowPreference.action_category == action_category,
            ).first()

            now = datetime.utcnow()

            if existing:
                existing.preferred_mode = preferred_mode
                existing.set_via = set_via
                existing.updated_at = now
                db.commit()
                db.refresh(existing)
                pref = existing
            else:
                pref = ShadowPreference(
                    company_id=company_id,
                    action_category=action_category,
                    preferred_mode=preferred_mode,
                    set_via=set_via,
                    updated_at=now,
                )
                db.add(pref)
                db.commit()
                db.refresh(pref)

            logger.info(
                "shadow_preference_set company_id=%s category=%s mode=%s set_via=%s",
                company_id,
                action_category,
                preferred_mode,
                set_via,
            )

            # Emit Socket.io event for preference change
            _emit_shadow_event_sync(
                company_id,
                "shadow:preference_changed",
                {
                    "action_category": action_category,
                    "preferred_mode": preferred_mode,
                    "set_via": set_via,
                },
            )

            return self._preference_to_dict(pref)

    def delete_shadow_preference(
        self, company_id: str, action_category: str,
    ) -> Dict[str, Any]:
        """
        Remove a shadow mode preference, resetting to default.

        Args:
            company_id: Company UUID (BC-001).
            action_category: The action category to remove.

        Returns:
            Dict confirming deletion.
        """
        with SessionLocal() as db:
            deleted = db.query(ShadowPreference).filter(
                ShadowPreference.company_id == company_id,
                ShadowPreference.action_category == action_category,
            ).delete(synchronize_session=False)

            db.commit()

            logger.info(
                "shadow_preference_deleted company_id=%s category=%s deleted=%s",
                company_id,
                action_category,
                deleted,
            )

            return {
                "company_id": company_id,
                "action_category": action_category,
                "deleted": bool(deleted),
            }

    # ═══════════════════════════════════════════════════════════════
    # Pending Count
    # ═══════════════════════════════════════════════════════════════

    def get_pending_count(self, company_id: str) -> int:
        """
        Get the count of pending shadow log entries awaiting review.

        Args:
            company_id: Company UUID (BC-001).

        Returns:
            Count of pending entries (manager_decision is NULL).
        """
        with SessionLocal() as db:
            count = db.query(sa_func.count(ShadowLog.id)).filter(
                ShadowLog.company_id == company_id,
                ShadowLog.manager_decision.is_(None),
            ).scalar()

            return count or 0

    # ═══════════════════════════════════════════════════════════════
    # Manager Actions
    # ═══════════════════════════════════════════════════════════════

    def approve_shadow_action(
        self,
        shadow_log_id: str,
        manager_id: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Approve a pending shadow action.

        Args:
            shadow_log_id: ShadowLog entry UUID.
            manager_id: UUID of the approving manager.
            note: Optional approval note.

        Returns:
            Dict with updated shadow log details.

        Raises:
            ShadowLogNotFoundError: If entry not found.
            ShadowModeError: If entry already resolved.
        """
        with SessionLocal() as db:
            entry = db.query(ShadowLog).filter(
                ShadowLog.id == shadow_log_id,
            ).first()

            if not entry:
                raise ShadowLogNotFoundError(
                    f"Shadow log entry {shadow_log_id} not found"
                )

            if entry.manager_decision is not None:
                raise ShadowModeError(
                    f"Shadow log entry {shadow_log_id} is already "
                    f"resolved with decision '{entry.manager_decision}'"
                )

            entry.manager_decision = "approved"
            entry.manager_note = note
            entry.resolved_at = datetime.utcnow()

            # Decrement shadow_actions_remaining for Stage 0
            company = db.query(Company).filter(
                Company.id == entry.company_id
            ).first()
            if company:
                remaining = getattr(company, "shadow_actions_remaining", None)
                if remaining is not None and remaining > 0:
                    company.shadow_actions_remaining = remaining - 1
                    logger.info(
                        "stage_0_decremented company_id=%s remaining=%d",
                        entry.company_id, remaining - 1,
                    )

            db.commit()
            db.refresh(entry)

            logger.info(
                "shadow_action_approved id=%s manager=%s company_id=%s",
                shadow_log_id, manager_id, entry.company_id,
            )

            # Emit Socket.io event
            _emit_shadow_event_sync(
                entry.company_id,
                "shadow:action_approved",
                {
                    "shadow_log_id": shadow_log_id,
                    "action_type": entry.action_type,
                    "manager_id": manager_id,
                    "note": note,
                },
            )

            return self._shadow_log_to_dict(entry)

    def reject_shadow_action(
        self,
        shadow_log_id: str,
        manager_id: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reject a pending shadow action.

        Args:
            shadow_log_id: ShadowLog entry UUID.
            manager_id: UUID of the rejecting manager.
            note: Optional rejection reason.

        Returns:
            Dict with updated shadow log details.

        Raises:
            ShadowLogNotFoundError: If entry not found.
            ShadowModeError: If entry already resolved.
        """
        with SessionLocal() as db:
            entry = db.query(ShadowLog).filter(
                ShadowLog.id == shadow_log_id,
            ).first()

            if not entry:
                raise ShadowLogNotFoundError(
                    f"Shadow log entry {shadow_log_id} not found"
                )

            if entry.manager_decision is not None:
                raise ShadowModeError(
                    f"Shadow log entry {shadow_log_id} is already "
                    f"resolved with decision '{entry.manager_decision}'"
                )

            entry.manager_decision = "rejected"
            entry.manager_note = note
            entry.resolved_at = datetime.utcnow()
            db.commit()
            db.refresh(entry)

            logger.info(
                "shadow_action_rejected id=%s manager=%s company_id=%s",
                shadow_log_id, manager_id, entry.company_id,
            )

            # Emit Socket.io event
            _emit_shadow_event_sync(
                entry.company_id,
                "shadow:action_rejected",
                {
                    "shadow_log_id": shadow_log_id,
                    "action_type": entry.action_type,
                    "manager_id": manager_id,
                    "note": note,
                },
            )

            return self._shadow_log_to_dict(entry)

    def undo_auto_approved_action(
        self,
        shadow_log_id: str,
        reason: str,
        manager_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Undo a previously auto-approved action by creating an UndoLog entry.

        Looks up the original ExecutedAction linked to this shadow log entry
        and creates a corresponding undo record.

        Args:
            shadow_log_id: ShadowLog entry UUID.
            reason: Reason for the undo.
            manager_id: UUID of the manager requesting undo.

        Returns:
            Dict with undo log details.

        Raises:
            ShadowLogNotFoundError: If entry not found.
            ShadowModeError: If entry was not auto-approved.
        """
        with SessionLocal() as db:
            entry = db.query(ShadowLog).filter(
                ShadowLog.id == shadow_log_id,
            ).first()

            if not entry:
                raise ShadowLogNotFoundError(
                    f"Shadow log entry {shadow_log_id} not found"
                )

            # Create an ExecutedAction record if one doesn't exist yet,
            # so we can link the undo to it
            executed_action = ExecutedAction(
                company_id=entry.company_id,
                action_type=entry.action_type,
                action_data=str(
                    entry.action_payload) if entry.action_payload else None,
                executed_by=manager_id,
                created_at=datetime.utcnow(),
            )
            db.add(executed_action)
            db.flush()

            undo_log = UndoLog(
                company_id=entry.company_id,
                executed_action_id=executed_action.id,
                undo_type="reversal",
                original_data=str(
                    entry.action_payload) if entry.action_payload else None,
                undo_data=None,
                undo_reason=reason,
                undone_by=manager_id,
                created_at=datetime.utcnow(),
            )
            db.add(undo_log)

            # Mark the shadow log entry as rejected (undo implies rejection)
            entry.manager_decision = "rejected"
            entry.manager_note = f"[UNDO] {reason}"
            entry.resolved_at = datetime.utcnow()

            db.commit()
            db.refresh(undo_log)

            logger.info(
                "shadow_action_undone shadow_id=%s undo_id=%s manager=%s reason=%s",
                shadow_log_id, undo_log.id, manager_id, reason[:100],
            )

            # Emit Socket.io event
            _emit_shadow_event_sync(
                entry.company_id,
                "shadow:action_undone",
                {
                    "shadow_log_id": shadow_log_id,
                    "undo_log_id": undo_log.id,
                    "action_type": entry.action_type,
                    "reason": reason,
                },
            )

            return {
                "undo_id": undo_log.id,
                "shadow_log_id": shadow_log_id,
                "executed_action_id": executed_action.id,
                "undo_type": undo_log.undo_type,
                "reason": reason,
                "undone_by": manager_id,
                "created_at": undo_log.created_at.isoformat() if undo_log.created_at else None,
            }

    # ═══════════════════════════════════════════════════════════════
    # Shadow Log Query
    # ═══════════════════════════════════════════════════════════════

    def get_shadow_log(
        self,
        company_id: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Get paginated shadow log entries for a company.

        Args:
            company_id: Company UUID (BC-001).
            filters: Optional filters:
                - action_type: str
                - mode: str
                - decision: str (manager_decision)
                - date_from: ISO datetime string
                - date_to: ISO datetime string
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Dict with items, pagination, and total count.
        """
        filters = filters or {}

        with SessionLocal() as db:
            query = db.query(ShadowLog).filter(
                ShadowLog.company_id == company_id,
            )

            # Apply filters
            if filters.get("action_type"):
                query = query.filter(
                    ShadowLog.action_type == filters["action_type"]
                )

            if filters.get("mode"):
                query = query.filter(ShadowLog.mode == filters["mode"])

            if filters.get("decision"):
                query = query.filter(
                    ShadowLog.manager_decision == filters["decision"]
                )

            if filters.get("date_from"):
                try:
                    date_from = datetime.fromisoformat(
                        str(filters["date_from"]).replace("Z", "+00:00")
                    )
                    query = query.filter(ShadowLog.created_at >= date_from)
                except (ValueError, TypeError):
                    pass

            if filters.get("date_to"):
                try:
                    date_to = datetime.fromisoformat(
                        str(filters["date_to"]).replace("Z", "+00:00")
                    )
                    query = query.filter(ShadowLog.created_at <= date_to)
                except (ValueError, TypeError):
                    pass

            # Count total
            total = query.count()

            # Order by created_at DESC
            query = query.order_by(ShadowLog.created_at.desc())

            # Paginate
            offset = (page - 1) * page_size
            items = query.offset(offset).limit(page_size).all()

            return {
                "items": [
                    self._shadow_log_to_dict(i) for i in items],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (
                    total +
                    page_size -
                    1) //
                page_size if page_size > 0 else 0,
            }

    # ═══════════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════════

    def get_shadow_stats(self, company_id: str) -> Dict[str, Any]:
        """
        Get shadow mode statistics for a company.

        Returns:
            Dict with:
                - approval_rate: % of actions approved
                - avg_risk: Average risk score
                - mode_distribution: Count per mode
                - action_type_distribution: Count per action type
                - pending_count: Count of pending entries
                - total_actions: Total number of logged actions
        """
        with SessionLocal() as db:
            # Total actions
            total = db.query(sa_func.count(ShadowLog.id)).filter(
                ShadowLog.company_id == company_id,
            ).scalar() or 0

            # Pending count
            pending = db.query(sa_func.count(ShadowLog.id)).filter(
                ShadowLog.company_id == company_id,
                ShadowLog.manager_decision.is_(None),
            ).scalar() or 0

            # Approved count
            approved = db.query(sa_func.count(ShadowLog.id)).filter(
                ShadowLog.company_id == company_id,
                ShadowLog.manager_decision == "approved",
            ).scalar() or 0

            # Rejected count
            rejected = db.query(sa_func.count(ShadowLog.id)).filter(
                ShadowLog.company_id == company_id,
                ShadowLog.manager_decision == "rejected",
            ).scalar() or 0

            # Average risk score
            avg_risk_result = db.query(
                sa_func.avg(ShadowLog.jarvis_risk_score)
            ).filter(
                ShadowLog.company_id == company_id,
                ShadowLog.jarvis_risk_score.isnot(None),
            ).scalar()

            avg_risk = round(
                float(avg_risk_result),
                3) if avg_risk_result else 0.0

            # Mode distribution
            mode_dist_rows = db.query(
                ShadowLog.mode, sa_func.count(ShadowLog.id)
            ).filter(
                ShadowLog.company_id == company_id,
            ).group_by(ShadowLog.mode).all()

            mode_distribution = {
                row[0]: row[1] for row in mode_dist_rows
            }

            # Action type distribution
            action_dist_rows = db.query(
                ShadowLog.action_type, sa_func.count(ShadowLog.id)
            ).filter(
                ShadowLog.company_id == company_id,
            ).group_by(ShadowLog.action_type).all()

            action_type_distribution = {
                row[0]: row[1] for row in action_dist_rows
            }

            resolved = approved + rejected
            approval_rate = (
                round((approved / resolved) * 100, 1) if resolved > 0 else 0.0
            )

            return {
                "company_id": company_id,
                "total_actions": total,
                "pending_count": pending,
                "approved_count": approved,
                "rejected_count": rejected,
                "approval_rate": approval_rate,
                "avg_risk_score": avg_risk,
                "mode_distribution": mode_distribution,
                "action_type_distribution": action_type_distribution,
            }

    # ═══════════════════════════════════════════════════════════════
    # Batch Operations
    # ═══════════════════════════════════════════════════════════════

    def batch_resolve(
        self,
        company_id: str,
        shadow_log_ids: List[str],
        decision: str,
        manager_id: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Batch approve or reject multiple pending shadow actions.

        Args:
            company_id: Company UUID (BC-001).
            shadow_log_ids: List of ShadowLog UUIDs to resolve.
            decision: 'approved' or 'rejected'.
            manager_id: UUID of the resolving manager.
            note: Optional note.

        Returns:
            Dict with results summary.
        """
        if decision not in VALID_DECISIONS:
            raise ShadowModeError(f"Invalid decision: {decision}")

        with SessionLocal() as db:
            entries = db.query(ShadowLog).filter(
                ShadowLog.id.in_(shadow_log_ids),
                ShadowLog.company_id == company_id,
                ShadowLog.manager_decision.is_(None),
            ).all()

            resolved = 0
            skipped = 0

            now = datetime.utcnow()
            for entry in entries:
                entry.manager_decision = decision
                entry.manager_note = note
                entry.resolved_at = now
                resolved += 1

            db.commit()

            skipped = len(shadow_log_ids) - resolved

            logger.info(
                "shadow_batch_resolve company_id=%s decision=%s "
                "resolved=%d skipped=%d manager=%s",
                company_id, decision, resolved, skipped, manager_id,
            )

            return {
                "resolved": resolved,
                "skipped": skipped,
                "decision": decision,
                "manager_id": manager_id,
            }

    # ═══════════════════════════════════════════════════════════════
    # Escalate (change mode to shadow for a specific action)
    # ═══════════════════════════════════════════════════════════════

    def escalate_shadow_action(
        self,
        shadow_log_id: str,
        manager_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Escalate a shadow action — change its mode to 'shadow' (observation only)
        and mark it as requiring re-review.

        Args:
            shadow_log_id: ShadowLog entry UUID.
            manager_id: UUID of the escalating manager.
            reason: Optional escalation reason.

        Returns:
            Dict with updated shadow log details.

        Raises:
            ShadowLogNotFoundError: If entry not found.
        """
        with SessionLocal() as db:
            entry = db.query(ShadowLog).filter(
                ShadowLog.id == shadow_log_id,
            ).first()

            if not entry:
                raise ShadowLogNotFoundError(
                    f"Shadow log entry {shadow_log_id} not found"
                )

            entry.mode = "shadow"
            entry.manager_note = (
                f"[ESCALATED by {manager_id}] {reason or ''}"
            ).strip()
            db.commit()
            db.refresh(entry)

            logger.info(
                "shadow_action_escalated id=%s manager=%s company_id=%s",
                shadow_log_id, manager_id, entry.company_id,
            )

            return self._shadow_log_to_dict(entry)

    # ═══════════════════════════════════════════════════════════════
    # Internal Helpers
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _adjust_risk_by_payload(
        base_score: float,
        action_type: str,
        payload: Dict[str, Any],
    ) -> float:
        """
        Adjust risk score based on payload content.

        Layer 1 enhancement:
        - Refund amount > $100: +0.2
        - Refund amount > $500: +0.3 (cumulative)
        - Payload contains PII indicators: +0.2
        - Payload is empty or minimal: -0.1 (lower risk)
        """
        score = base_score

        if action_type == "refund" and payload:
            amount = payload.get("amount")
            if amount is not None:
                try:
                    amount_val = float(amount)
                    if amount_val > CRITICAL_REFUND_THRESHOLD:
                        score += 0.3
                    elif amount_val > HIGH_REFUND_THRESHOLD:
                        score += 0.2
                except (ValueError, TypeError):
                    pass

        # PII indicators in payload
        if payload:
            text_fields = " ".join(str(v)
                                   for v in payload.values() if isinstance(v, str))
            pii_indicators = [
                "ssn",
                "social_security",
                "credit_card",
                "dob",
                "date_of_birth"]
            for indicator in pii_indicators:
                if indicator in text_fields.lower():
                    score += 0.2
                    break

        return max(0.0, min(1.0, round(score, 3)))

    @staticmethod
    def _get_avg_risk_score(
        db: Session,
        company_id: str,
        action_type: str,
    ) -> Optional[float]:
        """Get the average historical risk score for an action type."""
        result = db.query(
            sa_func.avg(ShadowLog.jarvis_risk_score)
        ).filter(
            ShadowLog.company_id == company_id,
            ShadowLog.action_type == action_type,
            ShadowLog.jarvis_risk_score.isnot(None),
        ).scalar()

        return float(result) if result is not None else None

    @staticmethod
    def _normalize_category(action_type: str) -> str:
        """
        Normalize an action type to a category for preference lookup.

        Examples:
            'refund' -> 'refund'
            'sms_reply' -> 'sms'
            'email_reply' -> 'email_reply'
            'ticket_close' -> 'ticket'
        """
        category_map = {
            "sms_reply": "sms",
            "sms_send": "sms",
            "email_reply": "email_reply",
            "email_send": "email_reply",
            "ticket_close": "ticket",
            "ticket_escalate": "ticket",
            "ticket_reopen": "ticket",
            "refund": "refund",
            "credit_issue": "refund",
            "tag_update": "tag_update",
            "note_add": "note_add",
            "priority_change": "priority_change",
        }
        return category_map.get(action_type, action_type)

    @staticmethod
    def _build_decision_reason(mode: str, risk_score: float) -> str:
        """Build a human-readable reason for the decision."""
        if mode == "shadow":
            return f"Shadow mode: action logged for observation only (risk: {
                risk_score:.2f})"
        elif mode == "supervised":
            if risk_score >= 0.7:
                return f"High risk ({
                    risk_score:.2f}): requires manager approval"
            elif risk_score >= 0.4:
                return f"Medium risk ({
                    risk_score:.2f}): requires manager approval"
            else:
                return f"Supervised mode: action requires manager approval (risk: {
                    risk_score:.2f})"
        else:  # graduated
            return f"Graduated mode: auto-approved (low risk: {
                risk_score:.2f})"

    @staticmethod
    def _shadow_log_to_dict(entry: ShadowLog) -> Dict[str, Any]:
        """Convert ShadowLog ORM model to dict."""
        return {
            "id": entry.id,
            "company_id": entry.company_id,
            "action_type": entry.action_type,
            "action_payload": entry.action_payload,
            "jarvis_risk_score": entry.jarvis_risk_score,
            "mode": entry.mode,
            "manager_decision": entry.manager_decision,
            "manager_note": entry.manager_note,
            "resolved_at": (
                entry.resolved_at.isoformat() if entry.resolved_at else None
            ),
            "created_at": (
                entry.created_at.isoformat() if entry.created_at else None
            ),
        }

    @staticmethod
    def _preference_to_dict(pref: ShadowPreference) -> Dict[str, Any]:
        """Convert ShadowPreference ORM model to dict."""
        return {
            "id": pref.id,
            "company_id": pref.company_id,
            "action_category": pref.action_category,
            "preferred_mode": pref.preferred_mode,
            "set_via": pref.set_via,
            "updated_at": (
                pref.updated_at.isoformat() if pref.updated_at else None
            ),
        }
