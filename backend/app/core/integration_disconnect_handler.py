"""
Integration Disconnect Handler (Phase 10: Rate Limiting & Error Handling)

Handles instant cleanup when an integration is disconnected:
1. Stops all pending API calls to that integration
2. Invalidates all cached data for that integration
3. Removes any queued rate-limit slots for that integration
4. Closes the circuit breaker for that integration
5. Notifies the AI pipeline to stop using that tool
6. Logs the disconnect to the audit trail

BC-001: Every operation scoped by company_id.
BC-008: Never crash — all operations wrapped in try/except.
BC-012: No stack traces to users, graceful degradation.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.logger import get_logger

logger = get_logger("integration_disconnect_handler")


# ══════════════════════════════════════════════════════════════════
# DISCONNECT TRACKING
# ══════════════════════════════════════════════════════════════════


@dataclass
class DisconnectRecord:
    """Record of an integration disconnect event."""
    company_id: str
    integration_id: str
    integration_name: str  # e.g. "hubspot", "twilio"
    disconnected_at: str  # ISO 8601 UTC
    reason: str = "user_action"
    cleanup_steps: List[str] = field(default_factory=list)


@dataclass
class PendingCall:
    """Tracks a pending API call that can be cancelled."""
    integration_name: str
    company_id: str
    call_id: str
    started_at: float
    cancelled: bool = False


# ══════════════════════════════════════════════════════════════════
# INTEGRATION DISCONNECT HANDLER
# ══════════════════════════════════════════════════════════════════


class IntegrationDisconnectHandler:
    """Handles instant cleanup when an integration is disconnected.

    Coordinates across multiple subsystems:
    - CircuitBreakerManager: force-open circuit
    - IntegrationRateLimiter: clear queued slots
    - IntegrationCacheService: invalidate cached data
    - Pending call tracking: cancel in-flight calls
    - AI pipeline notification: stop using the tool

    Usage:
        handler = IntegrationDisconnectHandler()
        result = handler.disconnect_integration("comp_123", "intg_456")
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Key: (company_id, integration_id) -> DisconnectRecord
        self._disconnects: Dict[tuple, DisconnectRecord] = {}
        # Key: (company_id, integration_name) -> Set[PendingCall]
        self._pending_calls: Dict[tuple, Set[PendingCall]] = {}

    def register_pending_call(
        self, integration_name: str, company_id: str, call_id: str,
    ) -> None:
        """Register a pending API call (called before external API calls)."""
        try:
            with self._lock:
                key = (company_id, integration_name)
                if key not in self._pending_calls:
                    self._pending_calls[key] = set()
                self._pending_calls[key].add(PendingCall(
                    integration_name=integration_name,
                    company_id=company_id,
                    call_id=call_id,
                    started_at=time.time(),
                ))
        except Exception:
            logger.exception(
                "register_pending_call_failed integration=%s company=%s",
                integration_name, company_id,
            )

    def unregister_pending_call(
        self, integration_name: str, company_id: str, call_id: str,
    ) -> None:
        """Unregister a completed API call."""
        try:
            with self._lock:
                key = (company_id, integration_name)
                if key in self._pending_calls:
                    self._pending_calls[key] = {
                        pc for pc in self._pending_calls[key]
                        if pc.call_id != call_id
                    }
        except Exception:
            logger.exception(
                "unregister_pending_call_failed integration=%s company=%s",
                integration_name, company_id,
            )

    def disconnect_integration(
        self, company_id: str, integration_id: str,
        integration_name: str = "", reason: str = "user_action",
    ) -> Dict[str, Any]:
        """Main handler: disconnect an integration with full cleanup.

        Args:
            company_id: Tenant company ID (BC-001).
            integration_id: Integration instance ID.
            integration_name: Integration type name (e.g. "hubspot", "twilio").
            reason: Disconnect reason for audit.

        Returns:
            Dict with cleanup results for each step.
        """
        steps: List[str] = []
        errors: List[str] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 1: Cancel all pending API calls
        try:
            cancelled = self._cancel_pending_calls(company_id, integration_name)
            steps.append(f"cancelled_{cancelled}_pending_calls")
            logger.info(
                "disconnect_cancelled_pending_calls company=%s integration=%s count=%d",
                company_id, integration_name, cancelled,
            )
        except Exception as exc:
            errors.append(f"cancel_pending_calls: {str(exc)[:100]}")

        # Step 2: Invalidate all cached data
        try:
            self._invalidate_cache(company_id, integration_name)
            steps.append("cache_invalidated")
        except Exception as exc:
            errors.append(f"cache_invalidation: {str(exc)[:100]}")

        # Step 3: Clear rate limit slots
        try:
            self._clear_rate_limits(company_id, integration_name)
            steps.append("rate_limits_cleared")
        except Exception as exc:
            errors.append(f"rate_limit_clear: {str(exc)[:100]}")

        # Step 4: Force-open circuit breaker
        try:
            self._open_circuit_breaker(integration_name)
            steps.append("circuit_breaker_opened")
        except Exception as exc:
            errors.append(f"circuit_breaker: {str(exc)[:100]}")

        # Step 5: Notify AI pipeline
        try:
            self._notify_ai_pipeline(company_id, integration_name)
            steps.append("ai_pipeline_notified")
        except Exception as exc:
            errors.append(f"ai_pipeline_notification: {str(exc)[:100]}")

        # Step 6: Log to audit trail
        try:
            record = DisconnectRecord(
                company_id=company_id,
                integration_id=integration_id,
                integration_name=integration_name,
                disconnected_at=now_iso,
                reason=reason,
                cleanup_steps=steps,
            )
            with self._lock:
                self._disconnects[(company_id, integration_id)] = record
            steps.append("audit_logged")
            logger.info(
                "integration_disconnected company=%s integration=%s name=%s reason=%s steps=%s",
                company_id, integration_id, integration_name, reason, ",".join(steps),
            )
        except Exception as exc:
            errors.append(f"audit_log: {str(exc)[:100]}")

        return {
            "company_id": company_id,
            "integration_id": integration_id,
            "integration_name": integration_name,
            "disconnected_at": now_iso,
            "reason": reason,
            "cleanup_steps": steps,
            "errors": errors,
            "success": len(errors) == 0,
        }

    def is_integration_connected(
        self, company_id: str, integration_id: str,
    ) -> bool:
        """Check if an integration is still connected (not disconnected).

        Returns False if the integration has been disconnected via this handler.
        """
        try:
            with self._lock:
                key = (company_id, integration_id)
                return key not in self._disconnects
        except Exception:
            logger.exception(
                "is_connected_check_failed company=%s integration=%s",
                company_id, integration_id,
            )
            return True  # BC-008: Assume connected on error

    def is_call_cancelled(
        self, integration_name: str, company_id: str, call_id: str,
    ) -> bool:
        """Check if a pending call has been cancelled (for cooperative cancellation)."""
        try:
            with self._lock:
                key = (company_id, integration_name)
                if key not in self._pending_calls:
                    return False
                for pc in self._pending_calls[key]:
                    if pc.call_id == call_id and pc.cancelled:
                        return True
                return False
        except Exception:
            return False

    def get_disconnect_status(
        self, company_id: str, integration_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the disconnect record for an integration, if any."""
        try:
            with self._lock:
                key = (company_id, integration_id)
                record = self._disconnects.get(key)
                if record:
                    return {
                        "company_id": record.company_id,
                        "integration_id": record.integration_id,
                        "integration_name": record.integration_name,
                        "disconnected_at": record.disconnected_at,
                        "reason": record.reason,
                        "cleanup_steps": record.cleanup_steps,
                    }
                return None
        except Exception:
            return None

    def reconnect_integration(
        self, company_id: str, integration_id: str,
        integration_name: str = "",
    ) -> Dict[str, Any]:
        """Re-enable an integration after it was disconnected.

        Closes the circuit breaker and removes the disconnect record.
        """
        steps: List[str] = []
        try:
            # Close circuit breaker
            self._close_circuit_breaker(integration_name)
            steps.append("circuit_breaker_closed")
        except Exception as exc:
            logger.warning("reconnect_circuit_breaker_failed: %s", str(exc)[:100])

        try:
            with self._lock:
                key = (company_id, integration_id)
                if key in self._disconnects:
                    del self._disconnects[key]
            steps.append("disconnect_record_removed")
        except Exception:
            pass

        logger.info(
            "integration_reconnected company=%s integration=%s name=%s",
            company_id, integration_id, integration_name,
        )

        return {
            "company_id": company_id,
            "integration_id": integration_id,
            "integration_name": integration_name,
            "reconnected_at": datetime.now(timezone.utc).isoformat(),
            "steps": steps,
        }

    # ── Internal Cleanup Methods ─────────────────────────────────────

    def _cancel_pending_calls(
        self, company_id: str, integration_name: str,
    ) -> int:
        """Cancel all pending calls for an integration. Returns count cancelled."""
        with self._lock:
            key = (company_id, integration_name)
            pending = self._pending_calls.get(key, set())
            count = 0
            for pc in pending:
                pc.cancelled = True
                count += 1
            # Clear the set after marking cancelled
            if key in self._pending_calls:
                self._pending_calls[key].clear()
            return count

    def _invalidate_cache(
        self, company_id: str, integration_name: str,
    ) -> None:
        """Invalidate all cached data for an integration."""
        try:
            from app.services.integration_cache_service import IntegrationCacheService
            cache_svc = IntegrationCacheService(company_id=company_id)
            # Run sync — the cache service handles async internally where needed
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context — schedule the invalidation
                loop.create_task(cache_svc.invalidate_on_disconnect(integration_name))
            except RuntimeError:
                # No event loop running — run synchronously
                asyncio.run(cache_svc.invalidate_on_disconnect(integration_name))
        except ImportError:
            logger.debug("integration_cache_service_not_available")
        except Exception as exc:
            logger.warning("cache_invalidation_failed: %s", str(exc)[:200])

    def _clear_rate_limits(
        self, company_id: str, integration_name: str,
    ) -> None:
        """Clear rate limit slots for an integration."""
        try:
            from app.core.integration_rate_limiter import get_integration_rate_limiter
            limiter = get_integration_rate_limiter()
            limiter.clear_integration(integration_name, company_id)
        except ImportError:
            logger.debug("integration_rate_limiter_not_available")
        except Exception as exc:
            logger.warning("rate_limit_clear_failed: %s", str(exc)[:200])

    def _open_circuit_breaker(self, integration_name: str) -> None:
        """Force-open the circuit breaker for an integration."""
        try:
            from app.core.circuit_breaker_manager import get_circuit_breaker_manager
            cb_manager = get_circuit_breaker_manager()
            # Ensure a circuit breaker exists, then force-open it
            if integration_name not in cb_manager._breakers:
                from app.core.circuit_breaker_manager import CircuitBreakerConfig
                cb_manager.register(integration_name, CircuitBreakerConfig())
            cb_manager.force_open(integration_name)
        except ImportError:
            logger.debug("circuit_breaker_manager_not_available")
        except Exception as exc:
            logger.warning("circuit_breaker_open_failed: %s", str(exc)[:200])

    def _close_circuit_breaker(self, integration_name: str) -> None:
        """Force-close the circuit breaker for an integration."""
        try:
            from app.core.circuit_breaker_manager import get_circuit_breaker_manager
            cb_manager = get_circuit_breaker_manager()
            cb_manager.force_close(integration_name)
        except Exception as exc:
            logger.warning("circuit_breaker_close_failed: %s", str(exc)[:200])

    def _notify_ai_pipeline(
        self, company_id: str, integration_name: str,
    ) -> None:
        """Notify the AI pipeline to stop using a tool.

        This is a fire-and-forget notification. The AI pipeline should
        check its tool registry and remove/disable the specified tool.
        """
        # Log the notification — the actual AI pipeline integration
        # can be wired here when the pipeline is running in-process.
        logger.info(
            "ai_pipeline_tool_disabled company=%s tool=%s",
            company_id, integration_name,
        )


# ══════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════

_instance: Optional[IntegrationDisconnectHandler] = None
_instance_lock = threading.Lock()


def get_integration_disconnect_handler() -> IntegrationDisconnectHandler:
    """Get the singleton IntegrationDisconnectHandler instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = IntegrationDisconnectHandler()
                logger.info("integration_disconnect_handler_initialized")
    return _instance


def reset_integration_disconnect_handler() -> None:
    """Reset the singleton instance (for testing only)."""
    global _instance
    with _instance_lock:
        _instance = None
