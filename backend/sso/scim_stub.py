"""
SCIM 2.0 Stub Implementation for Enterprise User Provisioning.

This module provides SCIM (System for Cross-domain Identity Management)
stub functionality for enterprise user provisioning from identity providers
like Okta, Azure AD, and Google Workspace.

SCIM 2.0 compliant endpoints:
- /scim/v2/Users
- /scim/v2/Groups
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class SCIMUser(BaseModel):
    """SCIM 2.0 User model."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    external_id: Optional[str] = None
    user_name: str
    name: Dict[str, str] = Field(default_factory=lambda: {
        "givenName": "",
        "familyName": "",
        "formatted": ""
    })
    display_name: Optional[str] = None
    emails: List[Dict[str, Any]] = Field(default_factory=list)
    active: bool = True
    title: Optional[str] = None
    locale: str = "en"
    timezone: str = "UTC"
    groups: List[Dict[str, str]] = Field(default_factory=list)
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_modified: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    meta: Dict[str, str] = Field(default_factory=dict)
    
    def __init__(self, **data):
        super().__init__(**data)
        self.meta = {
            "resourceType": "User",
            "location": f"https://api.parwa.ai/scim/v2/Users/{self.id}",
            "version": f'W/"{hashlib.md5(str(self.last_modified).encode()).hexdigest()}"'
        }


class SCIMGroup(BaseModel):
    """SCIM 2.0 Group model."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    external_id: Optional[str] = None
    display_name: str
    members: List[Dict[str, str]] = Field(default_factory=list)
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_modified: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    meta: Dict[str, str] = Field(default_factory=dict)
    
    def __init__(self, **data):
        super().__init__(**data)
        self.meta = {
            "resourceType": "Group",
            "location": f"https://api.parwa.ai/scim/v2/Groups/{self.id}",
            "version": f'W/"{hashlib.md5(str(self.last_modified).encode()).hexdigest()}"'
        }


class SCIMStub:
    """
    SCIM 2.0 Stub for enterprise user provisioning.
    
    Provides basic SCIM operations for user lifecycle management
    (create, read, update, delete) from identity providers.
    """
    
    def __init__(self, tenant_id: str):
        """
        Initialize SCIM Stub for a tenant.
        
        Args:
            tenant_id: Tenant identifier for isolation
        """
        self.tenant_id = tenant_id
        self._users: Dict[str, SCIMUser] = {}
        self._groups: Dict[str, SCIMGroup] = {}
        self._user_name_index: Dict[str, str] = {}  # username -> user_id
        self._tokens: Dict[str, Dict[str, Any]] = {}  # SCIM tokens
    
    # ==================== USER OPERATIONS ====================
    
    def create_user(
        self,
        user_name: str,
        given_name: str,
        family_name: str,
        email: str,
        active: bool = True,
        title: Optional[str] = None,
        external_id: Optional[str] = None
    ) -> SCIMUser:
        """
        Create a new SCIM user.
        
        Args:
            user_name: Unique username (usually email)
            given_name: User's first name
            family_name: User's last name
            email: User's email address
            active: Whether user is active
            title: User's job title
            external_id: External identifier from IdP
            
        Returns:
            Created SCIMUser
            
        Raises:
            ValueError: If username already exists
        """
        if user_name in self._user_name_index:
            raise ValueError(f"User with username '{user_name}' already exists")
        
        user = SCIMUser(
            external_id=external_id,
            user_name=user_name,
            name={
                "givenName": given_name,
                "familyName": family_name,
                "formatted": f"{given_name} {family_name}"
            },
            display_name=f"{given_name} {family_name}",
            emails=[{
                "value": email,
                "type": "work",
                "primary": True
            }],
            active=active,
            title=title
        )
        
        self._users[user.id] = user
        self._user_name_index[user_name] = user.id
        
        return user
    
    def get_user(self, user_id: str) -> Optional[SCIMUser]:
        """
        Get a user by ID.
        
        Args:
            user_id: User identifier
            
        Returns:
            SCIMUser or None if not found
        """
        return self._users.get(user_id)
    
    def get_user_by_username(self, user_name: str) -> Optional[SCIMUser]:
        """
        Get a user by username.
        
        Args:
            user_name: Username to look up
            
        Returns:
            SCIMUser or None if not found
        """
        user_id = self._user_name_index.get(user_name)
        if user_id:
            return self._users.get(user_id)
        return None
    
    def update_user(
        self,
        user_id: str,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        email: Optional[str] = None,
        active: Optional[bool] = None,
        title: Optional[str] = None
    ) -> Optional[SCIMUser]:
        """
        Update a user's information.
        
        Args:
            user_id: User identifier
            given_name: New first name
            family_name: New last name
            email: New email
            active: New active status
            title: New job title
            
        Returns:
            Updated SCIMUser or None if not found
        """
        user = self._users.get(user_id)
        if not user:
            return None
        
        if given_name is not None:
            user.name["givenName"] = given_name
        if family_name is not None:
            user.name["familyName"] = family_name
        if given_name or family_name:
            user.name["formatted"] = f"{user.name['givenName']} {user.name['familyName']}"
            user.display_name = user.name["formatted"]
        if email is not None:
            user.emails = [{"value": email, "type": "work", "primary": True}]
        if active is not None:
            user.active = active
        if title is not None:
            user.title = title
        
        user.last_modified = datetime.now(timezone.utc)
        
        return user
    
    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if deleted, False if not found
        """
        user = self._users.get(user_id)
        if not user:
            return False
        
        # Remove from index
        if user.user_name in self._user_name_index:
            del self._user_name_index[user.user_name]
        
        # Remove user
        del self._users[user_id]
        
        return True
    
    def list_users(
        self,
        start_index: int = 1,
        count: int = 100,
        filter_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List users with pagination and optional filtering.
        
        Args:
            start_index: 1-based start index
            count: Maximum number of results
            filter_query: SCIM filter query (e.g., 'userName eq "john@example.com"')
            
        Returns:
            SCIM list response dictionary
        """
        users = list(self._users.values())
        
        # Apply filter if provided (basic implementation)
        if filter_query:
            if "userName eq" in filter_query:
                username = filter_query.split('"')[1]
                users = [u for u in users if u.user_name == username]
            elif "active eq true" in filter_query:
                users = [u for u in users if u.active]
            elif "active eq false" in filter_query:
                users = [u for u in users if not u.active]
        
        total = len(users)
        
        # Apply pagination
        start = max(0, start_index - 1)
        end = min(start + count, total)
        paginated = users[start:end]
        
        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": total,
            "startIndex": start_index,
            "itemsPerPage": len(paginated),
            "Resources": [self._user_to_dict(u) for u in paginated]
        }
    
    # ==================== GROUP OPERATIONS ====================
    
    def create_group(
        self,
        display_name: str,
        members: Optional[List[str]] = None,
        external_id: Optional[str] = None
    ) -> SCIMGroup:
        """
        Create a new SCIM group.
        
        Args:
            display_name: Group display name
            members: List of user IDs to add as members
            external_id: External identifier from IdP
            
        Returns:
            Created SCIMGroup
        """
        group_members = []
        if members:
            for user_id in members:
                user = self._users.get(user_id)
                if user:
                    group_members.append({
                        "value": user.id,
                        "display": user.display_name
                    })
        
        group = SCIMGroup(
            external_id=external_id,
            display_name=display_name,
            members=group_members
        )
        
        self._groups[group.id] = group
        
        return group
    
    def get_group(self, group_id: str) -> Optional[SCIMGroup]:
        """
        Get a group by ID.
        
        Args:
            group_id: Group identifier
            
        Returns:
            SCIMGroup or None if not found
        """
        return self._groups.get(group_id)
    
    def update_group_members(
        self,
        group_id: str,
        add_members: Optional[List[str]] = None,
        remove_members: Optional[List[str]] = None
    ) -> Optional[SCIMGroup]:
        """
        Update group membership.
        
        Args:
            group_id: Group identifier
            add_members: User IDs to add
            remove_members: User IDs to remove
            
        Returns:
            Updated SCIMGroup or None if not found
        """
        group = self._groups.get(group_id)
        if not group:
            return None
        
        current_members = {m["value"]: m for m in group.members}
        
        # Add new members
        if add_members:
            for user_id in add_members:
                user = self._users.get(user_id)
                if user and user_id not in current_members:
                    current_members[user_id] = {
                        "value": user.id,
                        "display": user.display_name
                    }
        
        # Remove members
        if remove_members:
            for user_id in remove_members:
                if user_id in current_members:
                    del current_members[user_id]
        
        group.members = list(current_members.values())
        group.last_modified = datetime.now(timezone.utc)
        
        return group
    
    def delete_group(self, group_id: str) -> bool:
        """
        Delete a group.
        
        Args:
            group_id: Group identifier
            
        Returns:
            True if deleted, False if not found
        """
        if group_id in self._groups:
            del self._groups[group_id]
            return True
        return False
    
    def list_groups(
        self,
        start_index: int = 1,
        count: int = 100
    ) -> Dict[str, Any]:
        """
        List groups with pagination.
        
        Args:
            start_index: 1-based start index
            count: Maximum number of results
            
        Returns:
            SCIM list response dictionary
        """
        groups = list(self._groups.values())
        total = len(groups)
        
        start = max(0, start_index - 1)
        end = min(start + count, total)
        paginated = groups[start:end]
        
        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": total,
            "startIndex": start_index,
            "itemsPerPage": len(paginated),
            "Resources": [self._group_to_dict(g) for g in paginated]
        }
    
    # ==================== TOKEN MANAGEMENT ====================
    
    def create_scim_token(self, description: str = "SCIM Provisioning Token") -> str:
        """
        Create a new SCIM bearer token for IdP integration.
        
        Args:
            description: Token description
            
        Returns:
            Generated token
        """
        token = secrets.token_urlsafe(32)
        
        self._tokens[token] = {
            "token": token,
            "description": description,
            "tenant_id": self.tenant_id,
            "created_at": datetime.now(timezone.utc)
        }
        
        return token
    
    def validate_scim_token(self, token: str) -> bool:
        """
        Validate a SCIM bearer token.
        
        Args:
            token: Token to validate
            
        Returns:
            True if valid, False otherwise
        """
        return token in self._tokens
    
    def revoke_scim_token(self, token: str) -> bool:
        """
        Revoke a SCIM token.
        
        Args:
            token: Token to revoke
            
        Returns:
            True if revoked, False if not found
        """
        if token in self._tokens:
            del self._tokens[token]
            return True
        return False
    
    # ==================== HELPER METHODS ====================
    
    def _user_to_dict(self, user: SCIMUser) -> Dict[str, Any]:
        """Convert SCIMUser to dictionary for API response."""
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "id": user.id,
            "externalId": user.external_id,
            "userName": user.user_name,
            "name": user.name,
            "displayName": user.display_name,
            "emails": user.emails,
            "active": user.active,
            "title": user.title,
            "locale": user.locale,
            "timezone": user.timezone,
            "groups": user.groups,
            "meta": user.meta
        }
    
    def _group_to_dict(self, group: SCIMGroup) -> Dict[str, Any]:
        """Convert SCIMGroup to dictionary for API response."""
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "id": group.id,
            "externalId": group.external_id,
            "displayName": group.display_name,
            "members": group.members,
            "meta": group.meta
        }
    
    # ==================== SERVICE PROVIDER CONFIG ====================
    
    def get_service_provider_config(self) -> Dict[str, Any]:
        """
        Get SCIM service provider configuration.
        
        Returns:
            Service provider configuration dictionary
        """
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
            "patch": {
                "supported": True
            },
            "bulk": {
                "supported": True,
                "maxOperations": 100,
                "maxPayloadSize": 1048576
            },
            "filter": {
                "supported": True,
                "maxResults": 1000
            },
            "changePassword": {
                "supported": True
            },
            "sort": {
                "supported": True
            },
            "authenticationSchemes": [
                {
                    "name": "OAuth Bearer Token",
                    "description": "Authentication using OAuth 2.0 Bearer Token",
                    "specUri": "http://www.rfc-editor.org/info/rfc6750",
                    "type": "oauthbearertoken",
                    "primary": True
                }
            ],
            "meta": {
                "location": f"https://api.parwa.ai/scim/v2/ServiceProviderConfig",
                "resourceType": "ServiceProviderConfig"
            }
        }
    
    def get_resource_types(self) -> Dict[str, Any]:
        """
        Get SCIM resource types.
        
        Returns:
            Resource types dictionary
        """
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
            "totalResults": 2,
            "Resources": [
                {
                    "id": "User",
                    "name": "User",
                    "endpoint": "/scim/v2/Users",
                    "description": "User Account",
                    "schema": "urn:ietf:params:scim:schemas:core:2.0:User",
                    "meta": {
                        "location": "https://api.parwa.ai/scim/v2/ResourceTypes/User",
                        "resourceType": "ResourceType"
                    }
                },
                {
                    "id": "Group",
                    "name": "Group",
                    "endpoint": "/scim/v2/Groups",
                    "description": "Group",
                    "schema": "urn:ietf:params:scim:schemas:core:2.0:Group",
                    "meta": {
                        "location": "https://api.parwa.ai/scim/v2/ResourceTypes/Group",
                        "resourceType": "ResourceType"
                    }
                }
            ]
        }


def get_scim_stub_for_tenant(tenant_id: str) -> SCIMStub:
    """
    Factory function to get SCIM stub for a tenant.
    
    Args:
        tenant_id: Tenant identifier
        
    Returns:
        SCIMStub instance for the tenant
    """
    return SCIMStub(tenant_id)
