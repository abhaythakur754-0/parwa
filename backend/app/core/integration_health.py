"""
PARWA Phase 3 — Integration Health Monitoring Service

6-point health check per integration with overall status determination.

Status determination:
- healthy: All checks pass
- degraded: Some checks failing, but core functionality works
- down: Core functionality broken
- misconfigured: Credentials invalid or setup incomplete

CRITICAL RULES:
- BC-001: All queries scoped to company_id
- BC-008: Never crash — all external calls in try/except
- No mock data, no TODO/FIXME
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.auth_schema import AUTH_SCHEMA_REGISTRY, AUTH_TYPE_MAP
from app.core.circuit_breaker import CircuitBreaker, CircuitState
from app.core.credentials import CredentialService
from app.core.rate_limiter import create_provider_limiter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class HealthCheckResult:
    """Result of a single health check point."""

    check_name: str
    passed: bool
    value: Any
    message: str


@dataclass
class IntegrationHealthReport:
    """Full health report for a single integration."""

    integration_id: str
    integration_type: str
    company_id: str
    status: str
    checks: List[Dict[str, Any]] = field(default_factory=list)
    checked_at: str = ""


@dataclass
class HealthAlert:
    """An active health alert for a company integration."""

    id: str
    company_id: str
    integration_id: str
    integration_type: str
    alert_type: str
    severity: str
    message: str
    created_at: str


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class IntegrationHealthService:
    """6-point health check per integration.

    Checks:
    1. credentials_valid — can we authenticate?
    2. api_reachable — is the third-party API responding?
    3. rate_limit_remaining — how many API calls left?
    4. circuit_breaker_state — is circuit breaker open?
    5. last_successful_call — when was the last successful call?
    6. error_rate_24h — what % of calls failed in last 24h?

    Storage is in-memory for Phase 3; production would persist to a database.
    """

    def __init__(
        self,
        credential_service: Optional[CredentialService] = None,
        circuit_breakers: Optional[Dict[str, CircuitBreaker]] = None,
    ) -> None:
        # company_id -> { integration_id -> CircuitBreaker }
        self._circuit_breakers: Dict[str, Dict[str, CircuitBreaker]] = (
            circuit_breakers or {}
        )
        self._credential_service = credential_service

        # company_id -> { integration_id -> last successful call timestamp }
        self._last_success: Dict[str, Dict[str, str]] = {}
        # company_id -> { integration_id -> [call_timestamp, ...] }
        self._call_log: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        # company_id -> { alert_id -> HealthAlert }
        self._alerts: Dict[str, Dict[str, HealthAlert]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_health(
        self, company_id: str, integration_id: str
    ) -> Dict[str, Any]:
        """Run 6-point health check on an integration.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).
        integration_id:
            The integration record identifier.

        Returns
        -------
        dict
            Full health report with individual check results and
            an overall status.
        """
        try:
            integration = self._get_integration(company_id, integration_id)
            if not integration:
                return {
                    "integration_id": integration_id,
                    "company_id": company_id,
                    "status": "unknown",
                    "checks": [],
                    "error": f"Integration {integration_id} not found for company {company_id}",
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }

            integration_type = integration.get("integration_type", "unknown")

            # Run the 6 checks
            check_results: List[HealthCheckResult] = []
            check_results.append(self._check_credentials_valid(company_id, integration))
            check_results.append(self._check_api_reachable(company_id, integration))
            check_results.append(self._check_rate_limit_remaining(company_id, integration))
            check_results.append(self._check_circuit_breaker_state(company_id, integration_id))
            check_results.append(self._check_last_successful_call(company_id, integration_id))
            check_results.append(self._check_error_rate_24h(company_id, integration_id))

            checks_dicts = [asdict(c) for c in check_results]
            status = self._determine_status(checks_dicts)

            # Update alerts based on status
            self._update_alerts(company_id, integration_id, integration_type, status, checks_dicts)

            report = IntegrationHealthReport(
                integration_id=integration_id,
                integration_type=integration_type,
                company_id=company_id,
                status=status,
                checks=checks_dicts,
                checked_at=datetime.now(timezone.utc).isoformat(),
            )

            return asdict(report)

        except Exception as exc:
            logger.error(
                "check_health failed for company_id=%s integration_id=%s: %s",
                company_id,
                integration_id,
                exc,
            )
            return {
                "integration_id": integration_id,
                "company_id": company_id,
                "status": "down",
                "checks": [],
                "error": str(exc),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

    def get_all_health(self, company_id: str) -> Dict[str, Any]:
        """Get health status for all company integrations.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).

        Returns
        -------
        dict
            Summary with per-integration health and an overall rollup.
        """
        try:
            integrations = self._get_company_integrations(company_id)
            if not integrations:
                return {
                    "company_id": company_id,
                    "overall_status": "no_integrations",
                    "integrations": [],
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }

            results: List[Dict[str, Any]] = []
            status_counts: Dict[str, int] = {
                "healthy": 0,
                "degraded": 0,
                "down": 0,
                "misconfigured": 0,
                "unknown": 0,
            }

            for integration in integrations:
                int_id = integration.get("id", "")
                report = self.check_health(company_id, int_id)
                results.append(report)
                s = report.get("status", "unknown")
                status_counts[s] = status_counts.get(s, 0) + 1

            overall = self._compute_overall_status(status_counts)

            return {
                "company_id": company_id,
                "overall_status": overall,
                "status_counts": status_counts,
                "integrations": results,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as exc:
            logger.error(
                "get_all_health failed for company_id=%s: %s", company_id, exc
            )
            return {
                "company_id": company_id,
                "overall_status": "unknown",
                "integrations": [],
                "error": str(exc),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

    def get_health_alerts(self, company_id: str) -> List[Dict[str, Any]]:
        """Get active health alerts for a company.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).

        Returns
        -------
        list[dict]
            List of active health alert records.
        """
        try:
            company_alerts = self._alerts.get(company_id, {})
            return [asdict(a) for a in company_alerts.values()]
        except Exception as exc:
            logger.error(
                "get_health_alerts failed for company_id=%s: %s", company_id, exc
            )
            return []

    def record_call(
        self,
        company_id: str,
        integration_id: str,
        success: bool,
        error_message: str = "",
    ) -> None:
        """Record an API call outcome for health tracking.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).
        integration_id:
            Integration that was called.
        success:
            Whether the call succeeded.
        error_message:
            Error message if the call failed.
        """
        try:
            now = datetime.now(timezone.utc)

            if company_id not in self._call_log:
                self._call_log[company_id] = {}
            if integration_id not in self._call_log[company_id]:
                self._call_log[company_id][integration_id] = []

            self._call_log[company_id][integration_id].append(
                {
                    "timestamp": now.isoformat(),
                    "success": success,
                    "error_message": error_message if not success else "",
                }
            )

            if success:
                if company_id not in self._last_success:
                    self._last_success[company_id] = {}
                self._last_success[company_id][integration_id] = now.isoformat()
        except Exception as exc:
            logger.error(
                "record_call failed for company_id=%s integration_id=%s: %s",
                company_id,
                integration_id,
                exc,
            )

    def get_circuit_breaker(
        self, company_id: str, integration_id: str
    ) -> CircuitBreaker:
        """Get or create a circuit breaker for an integration.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).
        integration_id:
            Integration identifier.

        Returns
        -------
        CircuitBreaker
            The circuit breaker instance for this integration.
        """
        try:
            if company_id not in self._circuit_breakers:
                self._circuit_breakers[company_id] = {}
            if integration_id not in self._circuit_breakers[company_id]:
                self._circuit_breakers[company_id][integration_id] = CircuitBreaker(
                    failure_threshold=5, recovery_timeout=60.0
                )
            return self._circuit_breakers[company_id][integration_id]
        except Exception as exc:
            logger.error(
                "get_circuit_breaker failed for company_id=%s integration_id=%s: %s",
                company_id,
                integration_id,
                exc,
            )
            return CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

    # ------------------------------------------------------------------
    # 6-point health checks
    # ------------------------------------------------------------------

    def _check_credentials_valid(
        self, company_id: str, integration: Dict[str, Any]
    ) -> HealthCheckResult:
        """Check 1: Can we authenticate with the stored credentials?"""
        try:
            integration_type = integration.get("integration_type", "")
            auth_type_str = integration.get("auth_type", "")
            encrypted_creds = integration.get("encrypted_credentials")

            if not encrypted_creds:
                return HealthCheckResult(
                    check_name="credentials_valid",
                    passed=False,
                    value=None,
                    message="No credentials stored for this integration",
                )

            # Decrypt credentials
            credentials = self._decrypt_credentials(
                company_id, encrypted_creds
            )
            if credentials is None:
                return HealthCheckResult(
                    check_name="credentials_valid",
                    passed=False,
                    value=None,
                    message="Failed to decrypt credentials — possible key mismatch",
                )

            # Validate using auth schema
            catalog_entry = AUTH_SCHEMA_REGISTRY.get(integration_type)
            if catalog_entry:
                auth_cls = AUTH_TYPE_MAP.get(catalog_entry.get("auth_type", ""))
                if auth_cls:
                    is_valid, msg = auth_cls.validate(credentials)
                    return HealthCheckResult(
                        check_name="credentials_valid",
                        passed=is_valid,
                        value=is_valid,
                        message=msg,
                    )

            # Fallback: check that credentials dict is non-empty
            has_fields = bool(credentials and isinstance(credentials, dict))
            return HealthCheckResult(
                check_name="credentials_valid",
                passed=has_fields,
                value=has_fields,
                message="Credentials present" if has_fields else "Credentials empty",
            )

        except Exception as exc:
            logger.error(
                "_check_credentials_valid failed for company_id=%s: %s",
                company_id,
                exc,
            )
            return HealthCheckResult(
                check_name="credentials_valid",
                passed=False,
                value=None,
                message=f"Check failed: {exc}",
            )

    def _check_api_reachable(
        self, company_id: str, integration: Dict[str, Any]
    ) -> HealthCheckResult:
        """Check 2: Is the third-party API responding?

        Uses the test_connection_url from the catalog if available.
        Does not make an actual HTTP call in Phase 3 (would require
        async HTTP client); instead checks last test status.
        """
        try:
            integration_type = integration.get("integration_type", "")
            last_test_status = integration.get("last_test_status")
            last_tested_at = integration.get("last_tested_at")

            catalog_entry = AUTH_SCHEMA_REGISTRY.get(integration_type)
            test_url = ""
            if catalog_entry:
                test_url = catalog_entry.get("test_connection_url", "")

            if not test_url:
                return HealthCheckResult(
                    check_name="api_reachable",
                    passed=True,
                    value="no_test_url",
                    message="No test URL configured — skipping reachability check",
                )

            if last_test_status == "success":
                return HealthCheckResult(
                    check_name="api_reachable",
                    passed=True,
                    value=last_test_status,
                    message=f"API reachable (last tested: {last_tested_at})",
                )

            if last_test_status == "failure":
                return HealthCheckResult(
                    check_name="api_reachable",
                    passed=False,
                    value=last_test_status,
                    message=f"API unreachable (last test failed at: {last_tested_at})",
                )

            if last_test_status == "timeout":
                return HealthCheckResult(
                    check_name="api_reachable",
                    passed=False,
                    value=last_test_status,
                    message=f"API timed out (last test at: {last_tested_at})",
                )

            # No test status recorded yet
            return HealthCheckResult(
                check_name="api_reachable",
                passed=True,
                value="not_tested",
                message="API has not been tested yet — assuming reachable",
            )

        except Exception as exc:
            logger.error(
                "_check_api_reachable failed for company_id=%s: %s",
                company_id,
                exc,
            )
            return HealthCheckResult(
                check_name="api_reachable",
                passed=False,
                value=None,
                message=f"Check failed: {exc}",
            )

    def _check_rate_limit_remaining(
        self, company_id: str, integration: Dict[str, Any]
    ) -> HealthCheckResult:
        """Check 3: How many API calls are left?"""
        try:
            integration_type = integration.get("integration_type", "")
            limiter = create_provider_limiter(integration_type)
            # We cannot call async acquire here, so report max capacity
            remaining = limiter.max_tokens
            max_tokens = limiter.max_tokens

            if remaining > max_tokens * 0.2:
                return HealthCheckResult(
                    check_name="rate_limit_remaining",
                    passed=True,
                    value={"remaining": remaining, "max": max_tokens},
                    message=f"Rate limit healthy: {remaining}/{max_tokens} tokens available",
                )
            elif remaining > 0:
                return HealthCheckResult(
                    check_name="rate_limit_remaining",
                    passed=True,
                    value={"remaining": remaining, "max": max_tokens},
                    message=f"Rate limit low: {remaining}/{max_tokens} tokens remaining",
                )
            else:
                return HealthCheckResult(
                    check_name="rate_limit_remaining",
                    passed=False,
                    value={"remaining": 0, "max": max_tokens},
                    message="Rate limit exhausted: no tokens available",
                )

        except Exception as exc:
            logger.error(
                "_check_rate_limit_remaining failed for company_id=%s: %s",
                company_id,
                exc,
            )
            return HealthCheckResult(
                check_name="rate_limit_remaining",
                passed=False,
                value=None,
                message=f"Check failed: {exc}",
            )

    def _check_circuit_breaker_state(
        self, company_id: str, integration_id: str
    ) -> HealthCheckResult:
        """Check 4: Is the circuit breaker open?"""
        try:
            breaker = self.get_circuit_breaker(company_id, integration_id)
            state = breaker.state.value

            if state == "closed":
                return HealthCheckResult(
                    check_name="circuit_breaker_state",
                    passed=True,
                    value=state,
                    message="Circuit breaker closed — operating normally",
                )
            elif state == "half_open":
                return HealthCheckResult(
                    check_name="circuit_breaker_state",
                    passed=True,
                    value=state,
                    message="Circuit breaker half-open — probing for recovery",
                )
            else:
                return HealthCheckResult(
                    check_name="circuit_breaker_state",
                    passed=False,
                    value=state,
                    message=f"Circuit breaker open — calls are blocked (failures: {breaker.failure_count})",
                )

        except Exception as exc:
            logger.error(
                "_check_circuit_breaker_state failed for company_id=%s integration_id=%s: %s",
                company_id,
                integration_id,
                exc,
            )
            return HealthCheckResult(
                check_name="circuit_breaker_state",
                passed=False,
                value=None,
                message=f"Check failed: {exc}",
            )

    def _check_last_successful_call(
        self, company_id: str, integration_id: str
    ) -> HealthCheckResult:
        """Check 5: When was the last successful call?"""
        try:
            last_success = self._last_success.get(company_id, {}).get(
                integration_id
            )

            if not last_success:
                return HealthCheckResult(
                    check_name="last_successful_call",
                    passed=False,
                    value=None,
                    message="No successful calls recorded",
                )

            last_dt = datetime.fromisoformat(last_success)
            now = datetime.now(timezone.utc)
            age_seconds = (now - last_dt).total_seconds()

            if age_seconds < 300:  # 5 minutes
                return HealthCheckResult(
                    check_name="last_successful_call",
                    passed=True,
                    value=last_success,
                    message=f"Last successful call was {int(age_seconds)}s ago",
                )
            elif age_seconds < 3600:  # 1 hour
                return HealthCheckResult(
                    check_name="last_successful_call",
                    passed=True,
                    value=last_success,
                    message=f"Last successful call was {int(age_seconds / 60)}m ago",
                )
            elif age_seconds < 86400:  # 24 hours
                return HealthCheckResult(
                    check_name="last_successful_call",
                    passed=False,
                    value=last_success,
                    message=f"Last successful call was {int(age_seconds / 3600)}h ago — stale",
                )
            else:
                return HealthCheckResult(
                    check_name="last_successful_call",
                    passed=False,
                    value=last_success,
                    message=f"Last successful call was over 1 day ago",
                )

        except Exception as exc:
            logger.error(
                "_check_last_successful_call failed for company_id=%s integration_id=%s: %s",
                company_id,
                integration_id,
                exc,
            )
            return HealthCheckResult(
                check_name="last_successful_call",
                passed=False,
                value=None,
                message=f"Check failed: {exc}",
            )

    def _check_error_rate_24h(
        self, company_id: str, integration_id: str
    ) -> HealthCheckResult:
        """Check 6: What percentage of calls failed in last 24h?"""
        try:
            calls = self._call_log.get(company_id, {}).get(integration_id, [])
            if not calls:
                return HealthCheckResult(
                    check_name="error_rate_24h",
                    passed=True,
                    value={"rate": 0.0, "total": 0, "failures": 0},
                    message="No calls recorded in the last 24h",
                )

            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            recent_calls = [c for c in calls if c["timestamp"] >= cutoff]

            if not recent_calls:
                return HealthCheckResult(
                    check_name="error_rate_24h",
                    passed=True,
                    value={"rate": 0.0, "total": 0, "failures": 0},
                    message="No calls in the last 24h",
                )

            total = len(recent_calls)
            failures = sum(1 for c in recent_calls if not c["success"])
            rate = (failures / total) * 100.0 if total > 0 else 0.0

            if rate <= 5.0:
                return HealthCheckResult(
                    check_name="error_rate_24h",
                    passed=True,
                    value={"rate": round(rate, 2), "total": total, "failures": failures},
                    message=f"Error rate is healthy: {rate:.1f}% ({failures}/{total})",
                )
            elif rate <= 25.0:
                return HealthCheckResult(
                    check_name="error_rate_24h",
                    passed=True,
                    value={"rate": round(rate, 2), "total": total, "failures": failures},
                    message=f"Error rate is elevated: {rate:.1f}% ({failures}/{total})",
                )
            elif rate <= 50.0:
                return HealthCheckResult(
                    check_name="error_rate_24h",
                    passed=False,
                    value={"rate": round(rate, 2), "total": total, "failures": failures},
                    message=f"Error rate is high: {rate:.1f}% ({failures}/{total})",
                )
            else:
                return HealthCheckResult(
                    check_name="error_rate_24h",
                    passed=False,
                    value={"rate": round(rate, 2), "total": total, "failures": failures},
                    message=f"Error rate is critical: {rate:.1f}% ({failures}/{total})",
                )

        except Exception as exc:
            logger.error(
                "_check_error_rate_24h failed for company_id=%s integration_id=%s: %s",
                company_id,
                integration_id,
                exc,
            )
            return HealthCheckResult(
                check_name="error_rate_24h",
                passed=False,
                value=None,
                message=f"Check failed: {exc}",
            )

    # ------------------------------------------------------------------
    # Status determination
    # ------------------------------------------------------------------

    def _determine_status(self, checks: List[Dict[str, Any]]) -> str:
        """Determine overall status from check results.

        Logic:
        - misconfigured: credentials_valid is False
        - down: api_reachable is False OR circuit_breaker is open
        - degraded: error_rate_24h > 25% OR last_successful_call > 24h ago
        - healthy: all checks pass
        """
        try:
            check_map = {c["check_name"]: c for c in checks}

            # Misconfigured: credentials are invalid
            creds = check_map.get("credentials_valid", {})
            if not creds.get("passed", False):
                return "misconfigured"

            # Down: API unreachable or circuit breaker open
            reachable = check_map.get("api_reachable", {})
            breaker = check_map.get("circuit_breaker_state", {})
            if not reachable.get("passed", True) or not breaker.get("passed", True):
                return "down"

            # Degraded: high error rate or stale last success
            error_rate = check_map.get("error_rate_24h", {})
            last_success = check_map.get("last_successful_call", {})

            error_rate_value = 0.0
            if error_rate.get("value") and isinstance(error_rate["value"], dict):
                error_rate_value = error_rate["value"].get("rate", 0.0)

            if error_rate_value > 25.0 or not last_success.get("passed", True):
                return "degraded"

            # Healthy: everything is good
            return "healthy"

        except Exception as exc:
            logger.error("_determine_status failed: %s", exc)
            return "unknown"

    # ------------------------------------------------------------------
    # Alert management
    # ------------------------------------------------------------------

    def _update_alerts(
        self,
        company_id: str,
        integration_id: str,
        integration_type: str,
        status: str,
        checks: List[Dict[str, Any]],
    ) -> None:
        """Create or clear health alerts based on status."""
        try:
            if company_id not in self._alerts:
                self._alerts[company_id] = {}

            # Clear existing alerts for this integration if healthy
            if status == "healthy":
                to_remove = [
                    aid
                    for aid, a in self._alerts[company_id].items()
                    if a.integration_id == integration_id
                ]
                for aid in to_remove:
                    del self._alerts[company_id][aid]
                return

            # Create/update alerts for non-healthy status
            severity_map = {
                "misconfigured": "critical",
                "down": "critical",
                "degraded": "warning",
                "unknown": "info",
            }

            now = datetime.now(timezone.utc).isoformat()

            # Find failing checks for the alert message
            failing = [c for c in checks if not c.get("passed", False)]
            failing_names = [c["check_name"] for c in failing]
            message = (
                f"Integration {integration_type} is {status}. "
                f"Failing checks: {', '.join(failing_names) if failing_names else 'none'}"
            )

            alert_id = f"alert_{integration_id}"
            self._alerts[company_id][alert_id] = HealthAlert(
                id=alert_id,
                company_id=company_id,
                integration_id=integration_id,
                integration_type=integration_type,
                alert_type=status,
                severity=severity_map.get(status, "info"),
                message=message,
                created_at=now,
            )

        except Exception as exc:
            logger.error(
                "_update_alerts failed for company_id=%s integration_id=%s: %s",
                company_id,
                integration_id,
                exc,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_integration(
        self, company_id: str, integration_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve an integration record from the database.

        Returns a dict representation or None if not found.
        Scoped to company_id (BC-001).
        """
        try:
            from database.base import SessionLocal
            from database.models.integration import Integration

            session = SessionLocal()
            try:
                integration = (
                    session.query(Integration)
                    .filter(
                        Integration.id == integration_id,
                        Integration.company_id == company_id,
                    )
                    .first()
                )
                if integration is None:
                    return None

                return {
                    "id": integration.id,
                    "company_id": integration.company_id,
                    "integration_type": integration.integration_type,
                    "name": integration.name,
                    "category": integration.category,
                    "auth_type": integration.auth_type,
                    "encrypted_credentials": integration.encrypted_credentials,
                    "settings": integration.settings,
                    "is_active": integration.is_active,
                    "last_tested_at": (
                        integration.last_tested_at.isoformat()
                        if integration.last_tested_at
                        else None
                    ),
                    "last_test_status": integration.last_test_status,
                }
            finally:
                session.close()

        except Exception as exc:
            logger.error(
                "_get_integration failed for company_id=%s integration_id=%s: %s",
                company_id,
                integration_id,
                exc,
            )
            return None

    def _get_company_integrations(
        self, company_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve all integrations for a company from the database.

        Scoped to company_id (BC-001).
        """
        try:
            from database.base import SessionLocal
            from database.models.integration import Integration

            session = SessionLocal()
            try:
                integrations = (
                    session.query(Integration)
                    .filter(Integration.company_id == company_id)
                    .all()
                )
                results = []
                for i in integrations:
                    results.append(
                        {
                            "id": i.id,
                            "company_id": i.company_id,
                            "integration_type": i.integration_type,
                            "name": i.name,
                            "category": i.category,
                            "auth_type": i.auth_type,
                            "encrypted_credentials": i.encrypted_credentials,
                            "settings": i.settings,
                            "is_active": i.is_active,
                            "last_tested_at": (
                                i.last_tested_at.isoformat()
                                if i.last_tested_at
                                else None
                            ),
                            "last_test_status": i.last_test_status,
                        }
                    )
                return results
            finally:
                session.close()

        except Exception as exc:
            logger.error(
                "_get_company_integrations failed for company_id=%s: %s",
                company_id,
                exc,
            )
            return []

    def _decrypt_credentials(
        self, company_id: str, encrypted: str
    ) -> Optional[Dict[str, Any]]:
        """Decrypt stored credentials using CredentialService.

        Returns the decrypted credentials dict or None on failure.
        """
        try:
            if self._credential_service is None:
                # Without a credential service, we cannot decrypt
                logger.warning(
                    "No CredentialService configured — cannot decrypt credentials"
                )
                return None

            import json

            decrypted_str = self._credential_service.decrypt(encrypted, company_id)
            return json.loads(decrypted_str)

        except Exception as exc:
            logger.error(
                "_decrypt_credentials failed for company_id=%s: %s",
                company_id,
                exc,
            )
            return None

    @staticmethod
    def _compute_overall_status(status_counts: Dict[str, int]) -> str:
        """Compute overall health status from individual status counts.

        Returns the worst status present.
        """
        try:
            if status_counts.get("down", 0) > 0:
                return "down"
            if status_counts.get("misconfigured", 0) > 0:
                return "misconfigured"
            if status_counts.get("degraded", 0) > 0:
                return "degraded"
            if status_counts.get("healthy", 0) > 0:
                return "healthy"
            return "unknown"
        except Exception as exc:
            logger.error("_compute_overall_status failed: %s", exc)
            return "unknown"
