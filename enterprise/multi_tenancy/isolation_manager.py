"""
Tenant Isolation Manager

Enforces strict tenant isolation to prevent cross-tenant data access.
Provides validation, monitoring, and enforcement mechanisms.
"""

from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import logging
import threading
import hashlib

logger = logging.getLogger(__name__)


class IsolationLevel(str, Enum):
    """Levels of tenant isolation"""
    STRICT = "strict"  # Complete isolation, no cross-tenant access
    MODERATE = "moderate"  # Limited cross-tenant for specific features
    RELAXED = "relaxed"  # Isolation for sensitive data only


class IsolationViolationType(str, Enum):
    """Types of isolation violations"""
    CROSS_TENANT_READ = "cross_tenant_read"
    CROSS_TENANT_WRITE = "cross_tenant_write"
    DATA_LEAK = "data_leak"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    CONFIGURATION_ERROR = "configuration_error"
    QUERY_INJECTION = "query_injection"


@dataclass
class IsolationViolation:
    """Represents an isolation violation"""
    violation_id: str
    violation_type: IsolationViolationType
    source_tenant: str
    target_tenant: Optional[str]
    resource: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)
    blocked: bool = True
    severity: str = "high"


@dataclass
class TenantContext:
    """Context for tenant operations"""
    tenant_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    request_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class IsolationManager:
    """
    Manages tenant isolation enforcement.

    Features:
    - Request-level tenant context validation
    - Cross-tenant access prevention
    - Query validation and sanitization
    - Violation detection and logging
    - Isolation health monitoring
    """

    def __init__(
        self,
        isolation_level: IsolationLevel = IsolationLevel.STRICT,
        enable_logging: bool = True
    ):
        self.isolation_level = isolation_level
        self.enable_logging = enable_logging

        # Active contexts
        self._active_contexts: Dict[str, TenantContext] = {}
        self._context_lock = threading.Lock()

        # Violation tracking
        self._violations: List[IsolationViolation] = []
        self._violation_counts: Dict[str, int] = {}

        # Tenant data ownership tracking
        self._data_ownership: Dict[str, Set[str]] = {}  # resource -> tenant_ids

        # Blocked tenants (security measure)
        self._blocked_tenants: Set[str] = set()

        # Metrics
        self._metrics = {
            "total_requests": 0,
            "isolated_requests": 0,
            "violations_blocked": 0,
            "violations_allowed": 0
        }

    def create_context(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> TenantContext:
        """
        Create a new tenant context for a request.

        Args:
            tenant_id: The tenant making the request
            user_id: Optional user ID within the tenant
            session_id: Optional session ID
            ip_address: Optional client IP address
            request_id: Optional request tracking ID

        Returns:
            TenantContext for the request
        """
        context = TenantContext(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            request_id=request_id or self._generate_request_id()
        )

        with self._context_lock:
            self._active_contexts[context.request_id] = context

        self._metrics["total_requests"] += 1

        logger.debug(f"Created context for tenant {tenant_id}, request {context.request_id}")
        return context

    def _generate_request_id(self) -> str:
        """Generate unique request ID"""
        timestamp = datetime.utcnow().timestamp()
        return f"req_{hashlib.md5(str(timestamp).encode()).hexdigest()[:12]}"

    def get_context(self, request_id: str) -> Optional[TenantContext]:
        """Get context by request ID"""
        return self._active_contexts.get(request_id)

    def release_context(self, request_id: str) -> bool:
        """Release a tenant context"""
        with self._context_lock:
            if request_id in self._active_contexts:
                del self._active_contexts[request_id]
                return True
        return False

    def validate_access(
        self,
        context: TenantContext,
        resource: str,
        action: str,
        resource_tenant_id: Optional[str] = None
    ) -> bool:
        """
        Validate that a context has access to a resource.

        Args:
            context: The tenant context
            resource: Resource being accessed
            action: Action being performed (read, write, delete)
            resource_tenant_id: Tenant that owns the resource (if known)

        Returns:
            True if access is allowed, False otherwise
        """
        # Check if tenant is blocked
        if context.tenant_id in self._blocked_tenants:
            self._record_violation(
                IsolationViolationType.UNAUTHORIZED_ACCESS,
                context.tenant_id,
                resource_tenant_id,
                resource,
                {"reason": "Tenant blocked"}
            )
            return False

        # In strict mode, always validate tenant ownership
        if self.isolation_level == IsolationLevel.STRICT:
            if resource_tenant_id and resource_tenant_id != context.tenant_id:
                self._record_violation(
                    IsolationViolationType.CROSS_TENANT_READ
                    if action == "read" else IsolationViolationType.CROSS_TENANT_WRITE,
                    context.tenant_id,
                    resource_tenant_id,
                    resource,
                    {"action": action}
                )
                return False

        self._metrics["isolated_requests"] += 1
        return True

    def validate_query(
        self,
        context: TenantContext,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate and sanitize a query for tenant isolation.

        Args:
            context: The tenant context
            query: SQL or query string
            params: Query parameters

        Returns:
            Dict with validation result and sanitized query
        """
        result = {
            "valid": True,
            "query": query,
            "params": params or {},
            "warnings": []
        }

        # Check for potential injection patterns
        injection_patterns = [
            "tenant_id = '",
            "tenant_id=\"",
            "WHERE 1=1",
            "OR 1=1",
            "'; DROP",
            "UNION SELECT"
        ]

        query_lower = query.lower()
        for pattern in injection_patterns:
            if pattern.lower() in query_lower:
                result["warnings"].append(f"Potential injection pattern detected: {pattern}")

        # Ensure tenant filter is present
        if "tenant_id" not in query_lower:
            # Add tenant filter automatically
            if "where" in query_lower:
                result["query"] = query.replace(
                    "WHERE", f"WHERE tenant_id = '{context.tenant_id}' AND", 1
                )
            elif "WHERE" in query:
                result["query"] = query.replace(
                    "WHERE", f"WHERE tenant_id = '{context.tenant_id}' AND", 1
                )
            else:
                # Append WHERE clause
                result["query"] = f"{query} WHERE tenant_id = '{context.tenant_id}'"

            result["warnings"].append("Tenant filter automatically added")

        if result["warnings"]:
            logger.warning(f"Query validation warnings for tenant {context.tenant_id}: {result['warnings']}")

        return result

    def validate_data_access(
        self,
        context: TenantContext,
        data: Dict[str, Any],
        operation: str
    ) -> bool:
        """
        Validate data access for tenant isolation.

        Args:
            context: The tenant context
            data: Data being accessed
            operation: Operation type (read, write, update, delete)

        Returns:
            True if access is valid, False otherwise
        """
        # Check if data has tenant_id field
        if "tenant_id" not in data:
            # No tenant_id, allow if not strict mode
            if self.isolation_level == IsolationLevel.STRICT:
                self._record_violation(
                    IsolationViolationType.CONFIGURATION_ERROR,
                    context.tenant_id,
                    None,
                    "data_validation",
                    {"reason": "Data missing tenant_id field"}
                )
                return False
            return True

        # Check tenant ownership
        data_tenant = data.get("tenant_id")
        if data_tenant != context.tenant_id:
            violation_type = (
                IsolationViolationType.CROSS_TENANT_READ
                if operation == "read"
                else IsolationViolationType.CROSS_TENANT_WRITE
            )
            self._record_violation(
                violation_type,
                context.tenant_id,
                data_tenant,
                "data_record",
                {"operation": operation}
            )
            return False

        return True

    def _record_violation(
        self,
        violation_type: IsolationViolationType,
        source_tenant: str,
        target_tenant: Optional[str],
        resource: str,
        details: Dict[str, Any]
    ) -> None:
        """Record an isolation violation"""
        violation_id = f"viol_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(self._violations)}"

        violation = IsolationViolation(
            violation_id=violation_id,
            violation_type=violation_type,
            source_tenant=source_tenant,
            target_tenant=target_tenant,
            resource=resource,
            details=details,
            blocked=self.isolation_level == IsolationLevel.STRICT
        )

        self._violations.append(violation)

        # Update violation counts
        key = f"{source_tenant}:{violation_type.value}"
        self._violation_counts[key] = self._violation_counts.get(key, 0) + 1

        if violation.blocked:
            self._metrics["violations_blocked"] += 1
        else:
            self._metrics["violations_allowed"] += 1

        logger.warning(
            f"Isolation violation: {violation_type.value} from tenant {source_tenant} "
            f"to tenant {target_tenant}, resource: {resource}, blocked: {violation.blocked}"
        )

    def block_tenant(self, tenant_id: str) -> bool:
        """Block a tenant from all access"""
        self._blocked_tenants.add(tenant_id)
        logger.warning(f"Blocked tenant: {tenant_id}")
        return True

    def unblock_tenant(self, tenant_id: str) -> bool:
        """Unblock a tenant"""
        if tenant_id in self._blocked_tenants:
            self._blocked_tenants.remove(tenant_id)
            logger.info(f"Unblocked tenant: {tenant_id}")
            return True
        return False

    def is_tenant_blocked(self, tenant_id: str) -> bool:
        """Check if tenant is blocked"""
        return tenant_id in self._blocked_tenants

    def register_data_ownership(
        self,
        resource: str,
        tenant_ids: Set[str]
    ) -> None:
        """Register which tenants own a resource"""
        self._data_ownership[resource] = tenant_ids

    def get_data_owners(self, resource: str) -> Set[str]:
        """Get tenants that own a resource"""
        return self._data_ownership.get(resource, set())

    def get_violations(
        self,
        tenant_id: Optional[str] = None,
        violation_type: Optional[IsolationViolationType] = None,
        limit: int = 100
    ) -> List[IsolationViolation]:
        """
        Get violations, optionally filtered.

        Args:
            tenant_id: Filter by source tenant
            violation_type: Filter by violation type
            limit: Maximum number of violations to return

        Returns:
            List of matching violations
        """
        violations = self._violations

        if tenant_id:
            violations = [v for v in violations if v.source_tenant == tenant_id]

        if violation_type:
            violations = [v for v in violations if v.violation_type == violation_type]

        return violations[-limit:]

    def get_violation_summary(self) -> Dict[str, Any]:
        """Get summary of violations"""
        summary = {
            "total_violations": len(self._violations),
            "blocked_violations": sum(1 for v in self._violations if v.blocked),
            "by_type": {},
            "by_tenant": {},
            "recent_violations": []
        }

        for violation in self._violations:
            # By type
            type_key = violation.violation_type.value
            summary["by_type"][type_key] = summary["by_type"].get(type_key, 0) + 1

            # By tenant
            tenant_key = violation.source_tenant
            summary["by_tenant"][tenant_key] = summary["by_tenant"].get(tenant_key, 0) + 1

        # Recent violations (last 10)
        summary["recent_violations"] = [
            {
                "violation_id": v.violation_id,
                "type": v.violation_type.value,
                "source_tenant": v.source_tenant,
                "target_tenant": v.target_tenant,
                "resource": v.resource,
                "blocked": v.blocked,
                "timestamp": v.timestamp.isoformat()
            }
            for v in self._violations[-10:]
        ]

        return summary

    def get_metrics(self) -> Dict[str, Any]:
        """Get isolation metrics"""
        return {
            **self._metrics,
            "active_contexts": len(self._active_contexts),
            "blocked_tenants": len(self._blocked_tenants),
            "isolation_level": self.isolation_level.value
        }

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on isolation"""
        issues = []

        # Check for unblocked violations
        unblocked = [v for v in self._violations if not v.blocked]
        if unblocked:
            issues.append(f"{len(unblocked)} unblocked violations recorded")

        # Check for blocked tenants
        if self._blocked_tenants:
            issues.append(f"{len(self._blocked_tenants)} tenants blocked")

        return {
            "healthy": len(issues) == 0,
            "issues": issues,
            "isolation_level": self.isolation_level.value,
            "total_violations": len(self._violations),
            "metrics": self._metrics
        }

    def clear_violations(self, before: Optional[datetime] = None) -> int:
        """Clear violations, optionally before a date"""
        if before:
            initial_count = len(self._violations)
            self._violations = [v for v in self._violations if v.timestamp >= before]
            return initial_count - len(self._violations)
        else:
            count = len(self._violations)
            self._violations.clear()
            return count

    def verify_isolation(self, tenant_a: str, tenant_b: str) -> Dict[str, Any]:
        """
        Verify isolation between two tenants.

        Returns:
            Dict with isolation status and any cross-tenant access records
        """
        cross_tenant_violations = [
            v for v in self._violations
            if (v.source_tenant == tenant_a and v.target_tenant == tenant_b) or
               (v.source_tenant == tenant_b and v.target_tenant == tenant_a)
        ]

        return {
            "tenants": [tenant_a, tenant_b],
            "is_isolated": len(cross_tenant_violations) == 0,
            "violation_count": len(cross_tenant_violations),
            "violations": [
                {
                    "type": v.violation_type.value,
                    "source": v.source_tenant,
                    "target": v.target_tenant,
                    "blocked": v.blocked
                }
                for v in cross_tenant_violations
            ]
        }

    def audit_tenant_access(self, tenant_id: str) -> Dict[str, Any]:
        """
        Audit all access for a specific tenant.

        Returns:
            Comprehensive audit of tenant access patterns
        """
        tenant_violations = [
            v for v in self._violations
            if v.source_tenant == tenant_id or v.target_tenant == tenant_id
        ]

        return {
            "tenant_id": tenant_id,
            "is_blocked": tenant_id in self._blocked_tenants,
            "total_violations": len(tenant_violations),
            "violations_as_source": len([v for v in tenant_violations if v.source_tenant == tenant_id]),
            "violations_as_target": len([v for v in tenant_violations if v.target_tenant == tenant_id]),
            "violation_types": list(set(v.violation_type.value for v in tenant_violations)),
            "recent_activity": [
                {
                    "type": v.violation_type.value,
                    "resource": v.resource,
                    "blocked": v.blocked,
                    "timestamp": v.timestamp.isoformat()
                }
                for v in sorted(tenant_violations, key=lambda x: x.timestamp, reverse=True)[:20]
            ]
        }
