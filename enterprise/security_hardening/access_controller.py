"""
Access Controller - Week 54 Advanced Security Hardening
Builder 4: Access Control System

Provides centralized access control with caching, decision logging,
and integration with RBAC and permission engines.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from datetime import datetime, timedelta
import hashlib
import threading
import logging

logger = logging.getLogger(__name__)


class AccessDecision(Enum):
    """Enumeration of access control decisions."""
    ALLOW = "allow"
    DENY = "deny"
    CHALLENGE = "challenge"  # Requires additional authentication


@dataclass
class AccessRequest:
    """
    Represents an access request with user, resource, action, and context.
    
    Attributes:
        user: User identifier or user object
        resource: Resource being accessed (e.g., "/api/users", "document:123")
        action: Action being performed (e.g., "read", "write", "delete")
        context: Additional context (ip_address, time, session, etc.)
        request_id: Unique identifier for tracking
        timestamp: When the request was made
    """
    user: str
    resource: str
    action: str
    context: dict = field(default_factory=dict)
    request_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_cache_key(self) -> str:
        """Generate a cache key for this request."""
        key_data = f"{self.user}:{self.resource}:{self.action}"
        # Include relevant context in cache key
        if self.context:
            sorted_context = sorted(self.context.items())
            key_data += f":{str(sorted_context)}"
        return hashlib.sha256(key_data.encode()).hexdigest()


@dataclass
class AccessResponse:
    """
    Represents an access control decision response.
    
    Attributes:
        decision: The access decision (ALLOW, DENY, CHALLENGE)
        reasons: List of reasons explaining the decision
        request_id: ID of the original request
        timestamp: When the decision was made
        expires_at: When cached decision expires (if cached)
        matched_rules: List of rule IDs that matched
        metadata: Additional metadata about the decision
    """
    decision: AccessDecision
    reasons: list = field(default_factory=list)
    request_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    matched_rules: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    @property
    def is_allowed(self) -> bool:
        """Check if access is allowed."""
        return self.decision == AccessDecision.ALLOW
    
    @property
    def is_denied(self) -> bool:
        """Check if access is denied."""
        return self.decision == AccessDecision.DENY
    
    @property
    def requires_challenge(self) -> bool:
        """Check if additional authentication is required."""
        return self.decision == AccessDecision.CHALLENGE


class AccessCache:
    """
    Thread-safe cache for access decisions.
    
    Provides caching with TTL support for improved performance.
    """
    
    def __init__(self, ttl_seconds: int = 300, max_size: int = 10000):
        """
        Initialize the access cache.
        
        Args:
            ttl_seconds: Time-to-live for cached entries
            max_size: Maximum number of entries in cache
        """
        self._cache: dict = {}
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[AccessResponse]:
        """Get a cached response if it exists and hasn't expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            
            response, expires_at = entry
            if datetime.utcnow() > expires_at:
                del self._cache[key]
                self._misses += 1
                return None
            
            self._hits += 1
            return response
    
    def set(self, key: str, response: AccessResponse) -> None:
        """Cache a response with TTL."""
        with self._lock:
            # Evict oldest entries if at capacity
            if len(self._cache) >= self._max_size:
                self._evict_oldest()
            
            expires_at = datetime.utcnow() + timedelta(seconds=self._ttl)
            self._cache[key] = (response, expires_at)
    
    def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache entry."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def invalidate_user(self, user: str) -> int:
        """Invalidate all cache entries for a user."""
        count = 0
        with self._lock:
            keys_to_remove = [
                k for k, (resp, _) in self._cache.items()
                if hasattr(resp, 'metadata') and resp.metadata.get('user') == user
            ]
            for key in keys_to_remove:
                del self._cache[key]
                count += 1
        return count
    
    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def _evict_oldest(self) -> None:
        """Evict the oldest 10% of entries."""
        if not self._cache:
            return
        
        # Sort by expiration time and remove oldest
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1][1]
        )
        to_remove = max(1, len(sorted_items) // 10)
        for key, _ in sorted_items[:to_remove]:
            del self._cache[key]
    
    @property
    def stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "size": len(self._cache),
            "max_size": self._max_size
        }


class AccessController:
    """
    Centralized access control system.
    
    Provides:
    - Access decision evaluation
    - Caching for performance
    - Integration with RBAC and permission engines
    - Audit logging
    """
    
    def __init__(
        self,
        cache_ttl: int = 300,
        cache_max_size: int = 10000,
        enable_cache: bool = True,
        default_decision: AccessDecision = AccessDecision.DENY
    ):
        """
        Initialize the access controller.
        
        Args:
            cache_ttl: Cache time-to-live in seconds
            cache_max_size: Maximum cache entries
            enable_cache: Whether to enable caching
            default_decision: Default decision when no rules match
        """
        self._cache = AccessCache(ttl_seconds=cache_ttl, max_size=cache_max_size)
        self._enable_cache = enable_cache
        self._default_decision = default_decision
        self._rules: list = []
        self._rbac_manager = None
        self._permission_engine = None
        self._audit_log: list = []
        self._lock = threading.RLock()
    
    def set_rbac_manager(self, rbac_manager: Any) -> None:
        """Set the RBAC manager for role-based checks."""
        self._rbac_manager = rbac_manager
    
    def set_permission_engine(self, permission_engine: Any) -> None:
        """Set the permission engine for rule evaluation."""
        self._permission_engine = permission_engine
    
    def add_rule(
        self,
        rule_id: str,
        resource_pattern: str,
        action_pattern: str,
        decision: AccessDecision,
        condition: Optional[callable] = None,
        priority: int = 0
    ) -> None:
        """
        Add an access control rule.
        
        Args:
            rule_id: Unique rule identifier
            resource_pattern: Resource pattern (supports wildcards)
            action_pattern: Action pattern (supports wildcards)
            decision: Decision when rule matches
            condition: Optional condition function
            priority: Rule priority (higher = evaluated first)
        """
        with self._lock:
            rule = {
                "id": rule_id,
                "resource_pattern": resource_pattern,
                "action_pattern": action_pattern,
                "decision": decision,
                "condition": condition,
                "priority": priority
            }
            self._rules.append(rule)
            # Sort by priority (descending)
            self._rules.sort(key=lambda r: r["priority"], reverse=True)
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        with self._lock:
            for i, rule in enumerate(self._rules):
                if rule["id"] == rule_id:
                    del self._rules[i]
                    return True
            return False
    
    def check_access(self, request: AccessRequest) -> AccessResponse:
        """
        Check if access should be granted for the given request.
        
        Args:
            request: The access request to evaluate
            
        Returns:
            AccessResponse with the decision and reasons
        """
        # Check cache first
        if self._enable_cache:
            cache_key = request.to_cache_key()
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for request: {request.request_id}")
                return cached
        
        # Evaluate the request
        response = self._evaluate_request(request)
        
        # Cache the result
        if self._enable_cache and response.decision != AccessDecision.CHALLENGE:
            self._cache.set(cache_key, response)
        
        # Log the decision
        self._log_decision(request, response)
        
        return response
    
    def _evaluate_request(self, request: AccessRequest) -> AccessResponse:
        """Evaluate an access request against all rules and systems."""
        reasons = []
        matched_rules = []
        final_decision = self._default_decision
        
        # Check RBAC if available
        if self._rbac_manager:
            rbac_decision = self._check_rbac(request)
            if rbac_decision:
                reasons.extend(rbac_decision.get("reasons", []))
                decision = rbac_decision.get("decision")
                # Handle both AccessDecision and PermissionEffect enums
                decision_value = decision.value if hasattr(decision, 'value') else str(decision)
                if decision_value == "deny":
                    return AccessResponse(
                        decision=AccessDecision.DENY,
                        reasons=reasons,
                        request_id=request.request_id,
                        matched_rules=matched_rules,
                        metadata={"user": request.user}
                    )
                if decision_value == "allow":
                    final_decision = AccessDecision.ALLOW
                    matched_rules.extend(rbac_decision.get("matched_roles", []))
        
        # Check permission engine if available
        if self._permission_engine:
            perm_decision = self._check_permissions(request)
            if perm_decision:
                reasons.extend(perm_decision.get("reasons", []))
                decision = perm_decision.get("decision")
                # Handle both AccessDecision and PermissionResult enums
                decision_value = decision.value if hasattr(decision, 'value') else str(decision)
                if decision_value == "deny":
                    return AccessResponse(
                        decision=AccessDecision.DENY,
                        reasons=reasons,
                        request_id=request.request_id,
                        matched_rules=matched_rules,
                        metadata={"user": request.user}
                    )
                if decision_value == "allow":
                    final_decision = AccessDecision.ALLOW
                    matched_rules.extend(perm_decision.get("matched_permissions", []))
        
        # Check local rules
        for rule in self._rules:
            if self._rule_matches(rule, request):
                matched_rules.append(rule["id"])
                
                # Check condition if present
                if rule["condition"] and not rule["condition"](request):
                    reasons.append(f"Rule {rule['id']} condition not met")
                    continue
                
                reasons.append(f"Matched rule: {rule['id']}")
                
                # First matching rule wins for DENY, accumulate for ALLOW
                if rule["decision"] == AccessDecision.DENY:
                    return AccessResponse(
                        decision=AccessDecision.DENY,
                        reasons=reasons,
                        request_id=request.request_id,
                        matched_rules=matched_rules,
                        metadata={"user": request.user}
                    )
                elif rule["decision"] == AccessDecision.CHALLENGE:
                    final_decision = AccessDecision.CHALLENGE
                elif rule["decision"] == AccessDecision.ALLOW:
                    final_decision = AccessDecision.ALLOW
        
        if not reasons:
            reasons.append(f"No matching rules, using default: {self._default_decision.value}")
        
        return AccessResponse(
            decision=final_decision,
            reasons=reasons,
            request_id=request.request_id,
            matched_rules=matched_rules,
            metadata={"user": request.user}
        )
    
    def _rule_matches(self, rule: dict, request: AccessRequest) -> bool:
        """Check if a rule matches the request."""
        import fnmatch
        
        resource_match = fnmatch.fnmatch(request.resource, rule["resource_pattern"])
        action_match = fnmatch.fnmatch(request.action, rule["action_pattern"])
        
        return resource_match and action_match
    
    def _check_rbac(self, request: AccessRequest) -> Optional[dict]:
        """Check access using RBAC manager."""
        if not self._rbac_manager:
            return None
        
        try:
            return self._rbac_manager.check_access(
                request.user,
                request.resource,
                request.action,
                request.context
            )
        except Exception as e:
            logger.error(f"RBAC check failed: {e}")
            return {"decision": AccessDecision.DENY, "reasons": [f"RBAC error: {str(e)}"]}
    
    def _check_permissions(self, request: AccessRequest) -> Optional[dict]:
        """Check access using permission engine."""
        if not self._permission_engine:
            return None
        
        try:
            return self._permission_engine.check(
                request.user,
                request.resource,
                request.action,
                request.context
            )
        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            return {"decision": AccessDecision.DENY, "reasons": [f"Permission error: {str(e)}"]}
    
    def _log_decision(self, request: AccessRequest, response: AccessResponse) -> None:
        """Log the access decision for audit purposes."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.request_id,
            "user": request.user,
            "resource": request.resource,
            "action": request.action,
            "decision": response.decision.value,
            "reasons": response.reasons,
            "context": request.context
        }
        self._audit_log.append(entry)
        
        # Keep log bounded
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]
    
    def invalidate_cache(self, user: Optional[str] = None) -> int:
        """
        Invalidate cached decisions.
        
        Args:
            user: If provided, invalidate only for this user
            
        Returns:
            Number of entries invalidated
        """
        if user:
            return self._cache.invalidate_user(user)
        self._cache.clear()
        return -1  # Indicates full clear
    
    def get_cache_stats(self) -> dict:
        """Get cache performance statistics."""
        return self._cache.stats
    
    def get_audit_log(self, limit: int = 100) -> list:
        """Get recent audit log entries."""
        return self._audit_log[-limit:]
    
    @property
    def rule_count(self) -> int:
        """Get the number of registered rules."""
        return len(self._rules)


# Convenience functions
def check_access(
    user: str,
    resource: str,
    action: str,
    context: Optional[dict] = None
) -> AccessResponse:
    """
    Convenience function for quick access checks.
    
    Creates a temporary AccessController instance for one-off checks.
    For repeated checks, use an AccessController instance directly.
    """
    controller = AccessController()
    request = AccessRequest(
        user=user,
        resource=resource,
        action=action,
        context=context or {}
    )
    return controller.check_access(request)
