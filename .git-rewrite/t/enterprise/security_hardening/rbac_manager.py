"""
RBAC Manager - Week 54 Advanced Security Hardening
Builder 4: Role-Based Access Control

Provides comprehensive role-based access control with hierarchy support,
permission inheritance, and dynamic role assignment.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Set, Dict, List
from datetime import datetime
from enum import Enum
import threading
import logging
import fnmatch

logger = logging.getLogger(__name__)


class PermissionEffect(Enum):
    """Effect of a permission rule."""
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class Permission:
    """
    Represents a permission with resource, action, and conditions.
    
    Attributes:
        resource: Resource pattern (e.g., "documents/*", "users/:id")
        action: Action pattern (e.g., "read", "write", "*")
        effect: Whether this permission allows or denies
        conditions: Optional conditions for the permission
        id: Unique permission identifier
    """
    resource: str
    action: str
    effect: PermissionEffect = PermissionEffect.ALLOW
    conditions: dict = field(default_factory=dict, hash=False)
    id: Optional[str] = None
    
    def __post_init__(self):
        if self.id is None:
            object.__setattr__(self, 'id', f"{self.resource}:{self.action}:{self.effect.value}")
    
    def matches(self, resource: str, action: str) -> bool:
        """Check if this permission matches the given resource and action."""
        resource_match = fnmatch.fnmatch(resource, self.resource)
        action_match = fnmatch.fnmatch(action, self.action)
        return resource_match and action_match
    
    def evaluate_conditions(self, context: dict) -> bool:
        """Evaluate permission conditions against context."""
        if not self.conditions:
            return True
        
        for key, expected_value in self.conditions.items():
            actual_value = context.get(key)
            
            # Handle different condition types
            if isinstance(expected_value, dict):
                # Complex condition
                if "in" in expected_value:
                    if actual_value not in expected_value["in"]:
                        return False
                elif "not_in" in expected_value:
                    if actual_value in expected_value["not_in"]:
                        return False
                elif "gt" in expected_value:
                    if not (actual_value and actual_value > expected_value["gt"]):
                        return False
                elif "lt" in expected_value:
                    if not (actual_value and actual_value < expected_value["lt"]):
                        return False
            elif isinstance(expected_value, list):
                if actual_value not in expected_value:
                    return False
            else:
                if actual_value != expected_value:
                    return False
        
        return True


@dataclass
class Role:
    """
    Represents a role with permissions and inheritance.
    
    Attributes:
        name: Role name (e.g., "admin", "editor", "viewer")
        permissions: Set of permissions granted to this role
        inherits: List of role names this role inherits from
        description: Human-readable description
        created_at: When the role was created
        metadata: Additional role metadata
    """
    name: str
    permissions: Set[Permission] = field(default_factory=set)
    inherits: List[str] = field(default_factory=list)
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
    
    def add_permission(self, permission: Permission) -> None:
        """Add a permission to this role."""
        self.permissions.add(permission)
    
    def remove_permission(self, permission_id: str) -> bool:
        """Remove a permission by ID."""
        for perm in list(self.permissions):
            if perm.id == permission_id:
                self.permissions.remove(perm)
                return True
        return False
    
    def has_permission(self, resource: str, action: str) -> Optional[Permission]:
        """
        Check if role has a matching permission.
        
        Returns the matching permission if found, None otherwise.
        """
        for perm in self.permissions:
            if perm.matches(resource, action):
                return perm
        return None


@dataclass
class RoleAssignment:
    """
    Represents a role assignment to a user.
    
    Attributes:
        user_id: User identifier
        role_name: Name of the assigned role
        assigned_at: When the role was assigned
        assigned_by: Who assigned the role
        expires_at: Optional expiration time
        conditions: Conditions for this assignment
    """
    user_id: str
    role_name: str
    assigned_at: datetime = field(default_factory=datetime.utcnow)
    assigned_by: Optional[str] = None
    expires_at: Optional[datetime] = None
    conditions: dict = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if this assignment has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if this assignment is valid (not expired)."""
        return not self.is_expired()


class RBACManager:
    """
    Role-Based Access Control Manager.
    
    Provides:
    - Role creation and management
    - Role assignment to users
    - Permission checking with hierarchy support
    - Dynamic role resolution
    """
    
    def __init__(self):
        """Initialize the RBAC manager."""
        self._roles: Dict[str, Role] = {}
        self._user_roles: Dict[str, List[RoleAssignment]] = {}
        self._permission_cache: Dict[str, dict] = {}
        self._lock = threading.RLock()
        self._role_change_callbacks: List[callable] = []
    
    def create_role(
        self,
        name: str,
        permissions: Optional[List[Permission]] = None,
        inherits: Optional[List[str]] = None,
        description: str = ""
    ) -> Role:
        """
        Create a new role.
        
        Args:
            name: Role name
            permissions: List of permissions for the role
            inherits: List of role names to inherit from
            description: Human-readable description
            
        Returns:
            The created Role instance
            
        Raises:
            ValueError: If role already exists or inherits from non-existent role
        """
        with self._lock:
            if name in self._roles:
                raise ValueError(f"Role '{name}' already exists")
            
            # Validate inheritance
            if inherits:
                for parent_name in inherits:
                    if parent_name not in self._roles:
                        raise ValueError(f"Parent role '{parent_name}' does not exist")
            
            role = Role(
                name=name,
                permissions=set(permissions) if permissions else set(),
                inherits=inherits or [],
                description=description
            )
            
            self._roles[name] = role
            self._invalidate_cache_for_role(name)
            self._notify_role_change("create", name)
            
            logger.info(f"Created role: {name}")
            return role
    
    def get_role(self, name: str) -> Optional[Role]:
        """Get a role by name."""
        return self._roles.get(name)
    
    def update_role(
        self,
        name: str,
        permissions: Optional[List[Permission]] = None,
        inherits: Optional[List[str]] = None,
        description: Optional[str] = None
    ) -> Optional[Role]:
        """
        Update an existing role.
        
        Args:
            name: Role name
            permissions: New permissions (replaces existing)
            inherits: New inheritance list (replaces existing)
            description: New description
            
        Returns:
            Updated Role or None if not found
        """
        with self._lock:
            role = self._roles.get(name)
            if not role:
                return None
            
            if permissions is not None:
                role.permissions = set(permissions)
            
            if inherits is not None:
                # Validate inheritance
                for parent_name in inherits:
                    if parent_name not in self._roles:
                        raise ValueError(f"Parent role '{parent_name}' does not exist")
                role.inherits = inherits
            
            if description is not None:
                role.description = description
            
            self._invalidate_cache_for_role(name)
            self._notify_role_change("update", name)
            
            return role
    
    def delete_role(self, name: str) -> bool:
        """
        Delete a role.
        
        Args:
            name: Role name
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if name not in self._roles:
                return False
            
            # Check if other roles inherit from this one
            for role in self._roles.values():
                if name in role.inherits:
                    raise ValueError(
                        f"Cannot delete role '{name}': role '{role.name}' inherits from it"
                    )
            
            del self._roles[name]
            
            # Remove assignments
            for user_id in list(self._user_roles.keys()):
                self._user_roles[user_id] = [
                    a for a in self._user_roles[user_id] if a.role_name != name
                ]
            
            self._notify_role_change("delete", name)
            logger.info(f"Deleted role: {name}")
            return True
    
    def assign_role(
        self,
        user_id: str,
        role_name: str,
        assigned_by: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        conditions: Optional[dict] = None
    ) -> RoleAssignment:
        """
        Assign a role to a user.
        
        Args:
            user_id: User identifier
            role_name: Name of role to assign
            assigned_by: Who is assigning the role
            expires_at: When the assignment expires
            conditions: Conditions for this assignment
            
        Returns:
            The RoleAssignment instance
            
        Raises:
            ValueError: If role does not exist
        """
        with self._lock:
            if role_name not in self._roles:
                raise ValueError(f"Role '{role_name}' does not exist")
            
            assignment = RoleAssignment(
                user_id=user_id,
                role_name=role_name,
                assigned_by=assigned_by,
                expires_at=expires_at,
                conditions=conditions or {}
            )
            
            if user_id not in self._user_roles:
                self._user_roles[user_id] = []
            
            self._user_roles[user_id].append(assignment)
            self._invalidate_user_cache(user_id)
            
            logger.info(f"Assigned role '{role_name}' to user '{user_id}'")
            return assignment
    
    def revoke_role(self, user_id: str, role_name: str) -> bool:
        """
        Revoke a role from a user.
        
        Args:
            user_id: User identifier
            role_name: Name of role to revoke
            
        Returns:
            True if revoked, False if not found
        """
        with self._lock:
            if user_id not in self._user_roles:
                return False
            
            original_count = len(self._user_roles[user_id])
            self._user_roles[user_id] = [
                a for a in self._user_roles[user_id]
                if a.role_name != role_name
            ]
            
            if len(self._user_roles[user_id]) < original_count:
                self._invalidate_user_cache(user_id)
                logger.info(f"Revoked role '{role_name}' from user '{user_id}'")
                return True
            
            return False
    
    def get_user_roles(self, user_id: str) -> List[Role]:
        """
        Get all valid roles for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of valid Role instances
        """
        roles = []
        seen = set()
        
        assignments = self._user_roles.get(user_id, [])
        for assignment in assignments:
            if not assignment.is_valid():
                continue
            
            role = self._roles.get(assignment.role_name)
            if role and role.name not in seen:
                roles.append(role)
                seen.add(role.name)
        
        return roles
    
    def get_user_assignments(self, user_id: str) -> List[RoleAssignment]:
        """Get all role assignments for a user (including expired)."""
        return self._user_roles.get(user_id, [])
    
    def check_permission(
        self,
        user_id: str,
        resource: str,
        action: str
    ) -> bool:
        """
        Check if a user has permission for an action on a resource.
        
        Args:
            user_id: User identifier
            resource: Resource being accessed
            action: Action being performed
            
        Returns:
            True if permitted, False otherwise
        """
        result = self.check_access(user_id, resource, action)
        return result.get("decision") == PermissionEffect.ALLOW
    
    def check_access(
        self,
        user_id: str,
        resource: str,
        action: str,
        context: Optional[dict] = None
    ) -> dict:
        """
        Comprehensive access check with detailed response.
        
        Args:
            user_id: User identifier
            resource: Resource being accessed
            action: Action being performed
            context: Additional context for condition evaluation
            
        Returns:
            Dict with decision, reasons, and matched roles/permissions
        """
        context = context or {}
        reasons = []
        matched_roles = []
        matched_permissions = []
        
        # Get all roles including inherited
        all_roles = self._get_all_roles_with_inheritance(user_id)
        
        # Check for explicit deny first
        for role in all_roles:
            for perm in role.permissions:
                if perm.matches(resource, action):
                    if perm.effect == PermissionEffect.DENY:
                        if perm.evaluate_conditions(context):
                            return {
                                "decision": PermissionEffect.DENY,
                                "reasons": [f"Denied by permission '{perm.id}' in role '{role.name}'"],
                                "matched_roles": [role.name],
                                "matched_permissions": [perm.id]
                            }
        
        # Check for allow
        for role in all_roles:
            for perm in role.permissions:
                if perm.matches(resource, action):
                    if perm.effect == PermissionEffect.ALLOW:
                        if perm.evaluate_conditions(context):
                            matched_roles.append(role.name)
                            matched_permissions.append(perm.id)
                            reasons.append(f"Allowed by permission '{perm.id}' in role '{role.name}'")
        
        if matched_permissions:
            return {
                "decision": PermissionEffect.ALLOW,
                "reasons": reasons,
                "matched_roles": list(set(matched_roles)),
                "matched_permissions": matched_permissions
            }
        
        return {
            "decision": PermissionEffect.DENY,
            "reasons": ["No matching permission found"],
            "matched_roles": [],
            "matched_permissions": []
        }
    
    def _get_all_roles_with_inheritance(self, user_id: str) -> List[Role]:
        """Get all roles for a user including inherited roles."""
        direct_roles = self.get_user_roles(user_id)
        all_roles = []
        seen = set()
        
        def collect_roles(role: Role):
            if role.name in seen:
                return
            seen.add(role.name)
            all_roles.append(role)
            
            # Collect inherited roles
            for parent_name in role.inherits:
                parent_role = self._roles.get(parent_name)
                if parent_role:
                    collect_roles(parent_role)
        
        for role in direct_roles:
            collect_roles(role)
        
        return all_roles
    
    def add_permission_to_role(
        self,
        role_name: str,
        permission: Permission
    ) -> bool:
        """Add a permission to a role."""
        with self._lock:
            role = self._roles.get(role_name)
            if not role:
                return False
            
            role.add_permission(permission)
            self._invalidate_cache_for_role(role_name)
            return True
    
    def remove_permission_from_role(
        self,
        role_name: str,
        permission_id: str
    ) -> bool:
        """Remove a permission from a role."""
        with self._lock:
            role = self._roles.get(role_name)
            if not role:
                return False
            
            result = role.remove_permission(permission_id)
            if result:
                self._invalidate_cache_for_role(role_name)
            return result
    
    def list_roles(self) -> List[str]:
        """List all role names."""
        return list(self._roles.keys())
    
    def get_users_with_role(self, role_name: str) -> List[str]:
        """Get all users with a specific role."""
        users = []
        for user_id, assignments in self._user_roles.items():
            for assignment in assignments:
                if assignment.role_name == role_name and assignment.is_valid():
                    users.append(user_id)
                    break
        return users
    
    def on_role_change(self, callback: callable) -> None:
        """Register a callback for role changes."""
        self._role_change_callbacks.append(callback)
    
    def _notify_role_change(self, action: str, role_name: str) -> None:
        """Notify callbacks of role changes."""
        for callback in self._role_change_callbacks:
            try:
                callback(action, role_name)
            except Exception as e:
                logger.error(f"Role change callback error: {e}")
    
    def _invalidate_cache_for_role(self, role_name: str) -> None:
        """Invalidate cache entries related to a role."""
        # Invalidate all users with this role
        for user_id in self.get_users_with_role(role_name):
            self._invalidate_user_cache(user_id)
    
    def _invalidate_user_cache(self, user_id: str) -> None:
        """Invalidate cache for a specific user."""
        if user_id in self._permission_cache:
            del self._permission_cache[user_id]
    
    @property
    def role_count(self) -> int:
        """Get the number of roles."""
        return len(self._roles)
    
    @property
    def assignment_count(self) -> int:
        """Get the total number of role assignments."""
        return sum(len(assignments) for assignments in self._user_roles.values())


# Predefined common roles
def create_default_roles(manager: RBACManager) -> None:
    """Create default roles with common permission sets."""
    
    # Viewer role - read-only access
    manager.create_role(
        name="viewer",
        permissions=[
            Permission(resource="*", action="read", effect=PermissionEffect.ALLOW)
        ],
        description="Read-only access to all resources"
    )
    
    # Editor role - read and write
    manager.create_role(
        name="editor",
        permissions=[
            Permission(resource="*", action="read", effect=PermissionEffect.ALLOW),
            Permission(resource="*", action="write", effect=PermissionEffect.ALLOW),
            Permission(resource="*", action="update", effect=PermissionEffect.ALLOW)
        ],
        description="Read and write access to all resources"
    )
    
    # Admin role - full access
    manager.create_role(
        name="admin",
        permissions=[
            Permission(resource="*", action="*", effect=PermissionEffect.ALLOW)
        ],
        description="Full administrative access"
    )
    
    # Super admin - inherits from admin plus special permissions
    manager.create_role(
        name="super_admin",
        inherits=["admin"],
        permissions=[
            Permission(resource="admin/*", action="*", effect=PermissionEffect.ALLOW),
            Permission(resource="system/*", action="*", effect=PermissionEffect.ALLOW)
        ],
        description="Super administrator with system access"
    )
