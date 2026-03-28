"""
Tests for Week 54 Advanced Security Hardening - Builder 4: Access Controller

Tests cover:
- access_controller.py (AccessController, AccessDecision, AccessRequest/Response)
- rbac_manager.py (RBACManager, Role, Permission)
- permission_engine.py (PermissionEngine, PermissionPolicy, Condition evaluation)

Total tests: 25+
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

# Import modules under test
import sys
sys.path.insert(0, '/home/z/my-project/parwa')

from enterprise.security_hardening.access_controller import (
    AccessController,
    AccessDecision,
    AccessRequest,
    AccessResponse,
    AccessCache,
    check_access
)
from enterprise.security_hardening.rbac_manager import (
    RBACManager,
    Role,
    Permission,
    PermissionEffect,
    RoleAssignment,
    create_default_roles
)
from enterprise.security_hardening.permission_engine import (
    PermissionEngine,
    PermissionPolicy,
    PermissionRule,
    PermissionResult,
    Condition,
    ConditionType,
    BulkCheckRequest,
    BulkCheckResult
)


# =============================================================================
# Access Controller Tests (9 tests)
# =============================================================================

class TestAccessDecision:
    """Tests for AccessDecision enum."""
    
    def test_access_decision_values(self):
        """Test AccessDecision enum has correct values."""
        assert AccessDecision.ALLOW.value == "allow"
        assert AccessDecision.DENY.value == "deny"
        assert AccessDecision.CHALLENGE.value == "challenge"
    
    def test_access_decision_count(self):
        """Test AccessDecision has exactly 3 values."""
        assert len(AccessDecision) == 3


class TestAccessRequest:
    """Tests for AccessRequest dataclass."""
    
    def test_access_request_creation(self):
        """Test creating an AccessRequest."""
        request = AccessRequest(
            user="user123",
            resource="/api/documents",
            action="read"
        )
        assert request.user == "user123"
        assert request.resource == "/api/documents"
        assert request.action == "read"
        assert request.context == {}
        assert request.timestamp is not None
    
    def test_access_request_with_context(self):
        """Test AccessRequest with context."""
        request = AccessRequest(
            user="user123",
            resource="/api/admin",
            action="delete",
            context={"ip_address": "192.168.1.1", "session_id": "abc123"}
        )
        assert request.context["ip_address"] == "192.168.1.1"
        assert request.context["session_id"] == "abc123"
    
    def test_access_request_cache_key(self):
        """Test cache key generation."""
        request1 = AccessRequest(user="user1", resource="/api/data", action="read")
        request2 = AccessRequest(user="user1", resource="/api/data", action="read")
        request3 = AccessRequest(user="user2", resource="/api/data", action="read")
        
        # Same requests should have same cache key
        assert request1.to_cache_key() == request2.to_cache_key()
        # Different users should have different cache keys
        assert request1.to_cache_key() != request3.to_cache_key()


class TestAccessResponse:
    """Tests for AccessResponse dataclass."""
    
    def test_access_response_allowed(self):
        """Test AccessResponse for allowed access."""
        response = AccessResponse(
            decision=AccessDecision.ALLOW,
            reasons=["Permission granted"]
        )
        assert response.is_allowed is True
        assert response.is_denied is False
        assert response.requires_challenge is False
    
    def test_access_response_denied(self):
        """Test AccessResponse for denied access."""
        response = AccessResponse(
            decision=AccessDecision.DENY,
            reasons=["Insufficient permissions"]
        )
        assert response.is_allowed is False
        assert response.is_denied is True
        assert response.requires_challenge is False
    
    def test_access_response_challenge(self):
        """Test AccessResponse for challenge."""
        response = AccessResponse(
            decision=AccessDecision.CHALLENGE,
            reasons=["MFA required"]
        )
        assert response.is_allowed is False
        assert response.is_denied is False
        assert response.requires_challenge is True


class TestAccessCache:
    """Tests for AccessCache."""
    
    def test_cache_set_and_get(self):
        """Test setting and getting from cache."""
        cache = AccessCache(ttl_seconds=60)
        response = AccessResponse(decision=AccessDecision.ALLOW, reasons=["Test"])
        key = "test_key"
        
        cache.set(key, response)
        cached = cache.get(key)
        
        assert cached is not None
        assert cached.decision == AccessDecision.ALLOW
    
    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = AccessCache()
        result = cache.get("nonexistent_key")
        assert result is None
    
    def test_cache_invalidation(self):
        """Test cache invalidation."""
        cache = AccessCache()
        response = AccessResponse(decision=AccessDecision.ALLOW, reasons=["Test"])
        key = "test_key"
        
        cache.set(key, response)
        assert cache.get(key) is not None
        
        cache.invalidate(key)
        assert cache.get(key) is None
    
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = AccessCache()
        response = AccessResponse(decision=AccessDecision.ALLOW)
        
        cache.set("key1", response)
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1


class TestAccessController:
    """Tests for AccessController class."""
    
    def test_controller_creation(self):
        """Test creating an AccessController."""
        controller = AccessController()
        assert controller.rule_count == 0
        assert controller._enable_cache is True
    
    def test_add_rule(self):
        """Test adding rules to controller."""
        controller = AccessController()
        controller.add_rule(
            rule_id="rule1",
            resource_pattern="/api/*",
            action_pattern="read",
            decision=AccessDecision.ALLOW
        )
        assert controller.rule_count == 1
    
    def test_remove_rule(self):
        """Test removing rules from controller."""
        controller = AccessController()
        controller.add_rule(
            rule_id="rule1",
            resource_pattern="/api/*",
            action_pattern="read",
            decision=AccessDecision.ALLOW
        )
        result = controller.remove_rule("rule1")
        assert result is True
        assert controller.rule_count == 0
    
    def test_check_access_deny_by_default(self):
        """Test access is denied by default."""
        controller = AccessController(default_decision=AccessDecision.DENY)
        request = AccessRequest(
            user="user1",
            resource="/api/secret",
            action="read"
        )
        response = controller.check_access(request)
        assert response.decision == AccessDecision.DENY
    
    def test_check_access_with_rule(self):
        """Test access check with matching rule."""
        controller = AccessController(default_decision=AccessDecision.DENY)
        controller.add_rule(
            rule_id="allow_read",
            resource_pattern="/api/public/*",
            action_pattern="read",
            decision=AccessDecision.ALLOW
        )
        
        request = AccessRequest(
            user="user1",
            resource="/api/public/data",
            action="read"
        )
        response = controller.check_access(request)
        assert response.decision == AccessDecision.ALLOW


# =============================================================================
# RBAC Manager Tests (9 tests)
# =============================================================================

class TestPermission:
    """Tests for Permission dataclass."""
    
    def test_permission_creation(self):
        """Test creating a Permission."""
        perm = Permission(
            resource="documents/*",
            action="read",
            effect=PermissionEffect.ALLOW
        )
        assert perm.resource == "documents/*"
        assert perm.action == "read"
        assert perm.effect == PermissionEffect.ALLOW
        assert perm.id is not None
    
    def test_permission_matches(self):
        """Test permission matching."""
        perm = Permission(resource="documents/*", action="read")
        
        assert perm.matches("documents/123", "read") is True
        assert perm.matches("documents/abc", "read") is True
        assert perm.matches("documents/123", "write") is False
        assert perm.matches("users/123", "read") is False


class TestRole:
    """Tests for Role dataclass."""
    
    def test_role_creation(self):
        """Test creating a Role."""
        role = Role(name="editor")
        assert role.name == "editor"
        assert len(role.permissions) == 0
    
    def test_role_add_permission(self):
        """Test adding permissions to a role."""
        role = Role(name="editor")
        perm = Permission(resource="documents/*", action="write")
        
        role.add_permission(perm)
        
        assert len(role.permissions) == 1
    
    def test_role_remove_permission(self):
        """Test removing permissions from a role."""
        role = Role(name="editor")
        perm = Permission(resource="documents/*", action="write")
        role.add_permission(perm)
        
        result = role.remove_permission(perm.id)
        
        assert result is True
        assert len(role.permissions) == 0


class TestRBACManager:
    """Tests for RBACManager class."""
    
    def test_create_role(self):
        """Test creating a role."""
        manager = RBACManager()
        role = manager.create_role(name="viewer")
        
        assert role.name == "viewer"
        assert manager.role_count == 1
    
    def test_create_duplicate_role(self):
        """Test creating duplicate role raises error."""
        manager = RBACManager()
        manager.create_role(name="viewer")
        
        with pytest.raises(ValueError):
            manager.create_role(name="viewer")
    
    def test_assign_role(self):
        """Test assigning a role to a user."""
        manager = RBACManager()
        manager.create_role(name="viewer")
        
        assignment = manager.assign_role(user_id="user1", role_name="viewer")
        
        assert assignment.user_id == "user1"
        assert assignment.role_name == "viewer"
    
    def test_assign_nonexistent_role(self):
        """Test assigning non-existent role raises error."""
        manager = RBACManager()
        
        with pytest.raises(ValueError):
            manager.assign_role(user_id="user1", role_name="nonexistent")
    
    def test_check_permission(self):
        """Test permission checking."""
        manager = RBACManager()
        manager.create_role(
            name="editor",
            permissions=[
                Permission(resource="documents/*", action="read", effect=PermissionEffect.ALLOW),
                Permission(resource="documents/*", action="write", effect=PermissionEffect.ALLOW)
            ]
        )
        manager.assign_role(user_id="user1", role_name="editor")
        
        assert manager.check_permission("user1", "documents/123", "read") is True
        assert manager.check_permission("user1", "documents/123", "write") is True
        assert manager.check_permission("user1", "documents/123", "delete") is False
    
    def test_revoke_role(self):
        """Test revoking a role from a user."""
        manager = RBACManager()
        manager.create_role(name="viewer")
        manager.assign_role(user_id="user1", role_name="viewer")
        
        result = manager.revoke_role(user_id="user1", role_name="viewer")
        
        assert result is True
        roles = manager.get_user_roles("user1")
        assert len(roles) == 0
    
    def test_role_inheritance(self):
        """Test role inheritance."""
        manager = RBACManager()
        
        # Create base role
        manager.create_role(
            name="base",
            permissions=[
                Permission(resource="documents/*", action="read", effect=PermissionEffect.ALLOW)
            ]
        )
        
        # Create derived role that inherits from base
        manager.create_role(
            name="advanced",
            permissions=[
                Permission(resource="documents/*", action="write", effect=PermissionEffect.ALLOW)
            ],
            inherits=["base"]
        )
        
        manager.assign_role(user_id="user1", role_name="advanced")
        
        # User should have both read (from base) and write (from advanced)
        assert manager.check_permission("user1", "documents/123", "read") is True
        assert manager.check_permission("user1", "documents/123", "write") is True


# =============================================================================
# Permission Engine Tests (10 tests)
# =============================================================================

class TestCondition:
    """Tests for Condition class."""
    
    def test_time_based_condition_business_hours(self):
        """Test time-based condition for business hours."""
        # During business hours
        condition = Condition(
            type=ConditionType.TIME_BASED,
            config={"business_hours": {"start": "09:00", "end": "17:00"}}
        )
        
        # Create a datetime during business hours
        business_time = datetime(2024, 1, 15, 10, 30)  # 10:30 AM
        context = {"current_time": business_time}
        
        assert condition.evaluate(context) is True
        
        # Create a datetime outside business hours
        after_hours = datetime(2024, 1, 15, 18, 30)  # 6:30 PM
        context_after = {"current_time": after_hours}
        
        assert condition.evaluate(context_after) is False
    
    def test_attribute_based_condition(self):
        """Test attribute-based condition."""
        condition = Condition(
            type=ConditionType.ATTRIBUTE_BASED,
            config={"department": "engineering"}
        )
        
        # Matching attribute
        context_match = {"attributes": {"department": "engineering"}}
        assert condition.evaluate(context_match) is True
        
        # Non-matching attribute
        context_no_match = {"attributes": {"department": "sales"}}
        assert condition.evaluate(context_no_match) is False
    
    def test_context_based_condition_ip(self):
        """Test context-based condition for IP restriction."""
        condition = Condition(
            type=ConditionType.CONTEXT_BASED,
            config={"ip_address": {"allowed_ips": ["192.168.1.100", "10.0.0.1"]}}
        )
        
        # Allowed IP
        context_allowed = {"ip_address": "192.168.1.100"}
        assert condition.evaluate(context_allowed) is True
        
        # Not allowed IP
        context_denied = {"ip_address": "1.2.3.4"}
        assert condition.evaluate(context_denied) is False


class TestPermissionRule:
    """Tests for PermissionRule class."""
    
    def test_rule_creation(self):
        """Test creating a permission rule."""
        rule = PermissionRule(
            id="rule1",
            name="Allow Read",
            resource_pattern="/api/*",
            action_pattern="read",
            result=PermissionResult.ALLOW
        )
        
        assert rule.id == "rule1"
        assert rule.matches("/api/users", "read") is True
        assert rule.matches("/api/users", "write") is False
    
    def test_rule_with_condition(self):
        """Test rule with condition."""
        condition = Condition(
            type=ConditionType.CONTEXT_BASED,
            config={"mfa_verified": True}
        )
        
        rule = PermissionRule(
            id="rule1",
            name="Admin Access",
            resource_pattern="/admin/*",
            action_pattern="*",
            result=PermissionResult.ALLOW,
            conditions=[condition]
        )
        
        # Condition not met
        context_no_mfa = {"mfa_verified": False}
        assert rule.evaluate(context_no_mfa) == PermissionResult.ABSTAIN
        
        # Condition met
        context_with_mfa = {"mfa_verified": True}
        assert rule.evaluate(context_with_mfa) == PermissionResult.ALLOW


class TestPermissionPolicy:
    """Tests for PermissionPolicy class."""
    
    def test_policy_creation(self):
        """Test creating a permission policy."""
        policy = PermissionPolicy(
            id="policy1",
            name="Basic Policy",
            description="A basic permission policy"
        )
        
        assert policy.id == "policy1"
        assert policy.name == "Basic Policy"
        assert len(policy.rules) == 0
    
    def test_policy_add_rule(self):
        """Test adding rules to policy."""
        policy = PermissionPolicy(id="p1", name="Test")
        rule = PermissionRule(
            id="r1",
            name="Rule",
            resource_pattern="*",
            action_pattern="*",
            result=PermissionResult.ALLOW
        )
        
        policy.add_rule(rule)
        
        assert len(policy.rules) == 1


class TestPermissionEngine:
    """Tests for PermissionEngine class."""
    
    def test_engine_creation(self):
        """Test creating a permission engine."""
        engine = PermissionEngine()
        assert engine.policy_count == 0
    
    def test_create_policy(self):
        """Test creating a policy."""
        engine = PermissionEngine()
        policy = engine.create_policy(
            policy_id="policy1",
            name="Test Policy"
        )
        
        assert engine.policy_count == 1
        assert policy.id == "policy1"
    
    def test_assign_policy_and_check(self):
        """Test assigning policy and checking permissions."""
        engine = PermissionEngine()
        
        # Create policy with rule
        policy = engine.create_policy(
            policy_id="policy1",
            name="Read Policy"
        )
        
        rule = PermissionRule(
            id="r1",
            name="Allow Reads",
            resource_pattern="/api/data/*",
            action_pattern="read",
            result=PermissionResult.ALLOW
        )
        engine.add_rule_to_policy("policy1", rule)
        
        # Assign to user
        engine.assign_policy_to_user("user1", "policy1")
        
        # Check permissions
        assert engine.is_allowed("user1", "/api/data/items", "read") is True
        assert engine.is_allowed("user1", "/api/data/items", "write") is False
    
    def test_bulk_check(self):
        """Test bulk permission checking."""
        engine = PermissionEngine()
        
        policy = engine.create_policy(policy_id="p1", name="Test")
        engine.add_rule_to_policy("p1", PermissionRule(
            id="r1", name="Read", resource_pattern="/api/*", action_pattern="read",
            result=PermissionResult.ALLOW
        ))
        engine.add_rule_to_policy("p1", PermissionRule(
            id="r2", name="Write", resource_pattern="/api/public/*", action_pattern="write",
            result=PermissionResult.ALLOW
        ))
        engine.assign_policy_to_user("user1", "p1")
        
        request = BulkCheckRequest(
            user="user1",
            checks=[
                {"resource": "/api/data", "action": "read"},
                {"resource": "/api/data", "action": "write"},
                {"resource": "/api/public/data", "action": "write"},
            ]
        )
        
        result = engine.bulk_check(request)
        
        assert result.results["/api/data:read"]["allowed"] is True
        assert result.results["/api/data:write"]["allowed"] is False
        assert result.results["/api/public/data:write"]["allowed"] is True
    
    def test_time_based_rule_creation(self):
        """Test creating time-based rules."""
        engine = PermissionEngine()
        
        rule = engine.create_time_based_rule(
            rule_id="business_hours",
            name="Business Hours Access",
            resource_pattern="/sensitive/*",
            action_pattern="*",
            result=PermissionResult.ALLOW,
            business_hours={"start": "09:00", "end": "17:00"},
            allowed_days=[0, 1, 2, 3, 4]  # Mon-Fri
        )
        
        assert rule.id == "business_hours"
        assert len(rule.conditions) == 1
        assert rule.conditions[0].type == ConditionType.TIME_BASED
    
    def test_attribute_based_rule_creation(self):
        """Test creating attribute-based rules."""
        engine = PermissionEngine()
        
        rule = engine.create_attribute_based_rule(
            rule_id="dept_rule",
            name="Department Rule",
            resource_pattern="/dept/*",
            action_pattern="read",
            result=PermissionResult.ALLOW,
            attributes={"department": "engineering"}
        )
        
        assert rule.id == "dept_rule"
        assert rule.conditions[0].type == ConditionType.ATTRIBUTE_BASED


# =============================================================================
# Integration Tests (3 tests)
# =============================================================================

class TestIntegration:
    """Integration tests combining all three modules."""
    
    def test_access_controller_with_rbac(self):
        """Test AccessController with RBACManager integration."""
        # Create RBAC manager with role
        rbac = RBACManager()
        rbac.create_role(
            name="admin",
            permissions=[
                Permission(resource="*", action="*", effect=PermissionEffect.ALLOW)
            ]
        )
        rbac.assign_role(user_id="admin_user", role_name="admin")
        
        # Create access controller with RBAC
        controller = AccessController()
        controller.set_rbac_manager(rbac)
        
        # Check access
        request = AccessRequest(
            user="admin_user",
            resource="/api/admin/settings",
            action="delete"
        )
        
        response = controller.check_access(request)
        assert response.decision == AccessDecision.ALLOW
    
    def test_access_controller_with_permission_engine(self):
        """Test AccessController with PermissionEngine integration."""
        # Create permission engine
        engine = PermissionEngine()
        policy = engine.create_policy(policy_id="p1", name="Test")
        engine.add_rule_to_policy("p1", PermissionRule(
            id="r1", name="Allow", resource_pattern="/api/*", action_pattern="*",
            result=PermissionResult.ALLOW
        ))
        engine.assign_policy_to_user("user1", "p1")
        
        # Create access controller with permission engine
        controller = AccessController()
        controller.set_permission_engine(engine)
        
        # Check access
        request = AccessRequest(
            user="user1",
            resource="/api/data",
            action="read"
        )
        
        response = controller.check_access(request)
        assert response.decision == AccessDecision.ALLOW
    
    def test_full_integration_all_systems(self):
        """Test full integration of all three systems."""
        # Create RBAC manager
        rbac = RBACManager()
        rbac.create_role(
            name="editor",
            permissions=[
                Permission(resource="documents/*", action="read", effect=PermissionEffect.ALLOW),
                Permission(resource="documents/*", action="write", effect=PermissionEffect.ALLOW)
            ]
        )
        rbac.assign_role(user_id="editor1", role_name="editor")
        
        # Create permission engine with a rule that allows read (matching RBAC)
        engine = PermissionEngine()
        policy = engine.create_policy(policy_id="time_policy", name="Time Policy")
        engine.add_rule_to_policy("time_policy", engine.create_time_based_rule(
            rule_id="business_only",
            name="Business Hours Only",
            resource_pattern="documents/*",
            action_pattern="write",
            result=PermissionResult.ALLOW,
            business_hours={"start": "09:00", "end": "17:00"}
        ))
        # Add a rule that always allows read on documents
        engine.add_rule_to_policy("time_policy", PermissionRule(
            id="allow_read",
            name="Allow Read",
            resource_pattern="documents/*",
            action_pattern="read",
            result=PermissionResult.ALLOW
        ))
        engine.assign_policy_to_user("editor1", "time_policy")
        
        # Create access controller with both
        controller = AccessController()
        controller.set_rbac_manager(rbac)
        controller.set_permission_engine(engine)
        
        # Test read (should work for editor via both RBAC and permission engine)
        read_request = AccessRequest(
            user="editor1",
            resource="documents/report",
            action="read"
        )
        read_response = controller.check_access(read_request)
        assert read_response.decision == AccessDecision.ALLOW


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
