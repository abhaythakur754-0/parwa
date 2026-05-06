"""
Enterprise SSO - User Provisioner
Auto-provision users from SSO
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class ProvisioningAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DEACTIVATE = "deactivate"


class ProvisionedUser(BaseModel):
    """Provisioned user data"""
    user_id: str
    email: str
    name: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    groups: List[str] = Field(default_factory=list)
    active: bool = True
    provisioned_at: datetime = Field(default_factory=datetime.utcnow)
    last_sync: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict()


class ProvisioningRule(BaseModel):
    """User provisioning rule"""
    attribute: str
    value: str
    action: ProvisioningAction
    roles: List[str] = Field(default_factory=list)

    model_config = ConfigDict()


class UserProvisioner:
    """
    Auto-provision users from SSO.
    """

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.users: Dict[str, ProvisionedUser] = {}
        self.rules: List[ProvisioningRule] = []

    def add_rule(self, rule: ProvisioningRule) -> None:
        """Add a provisioning rule"""
        self.rules.append(rule)

    def provision_user(
        self,
        user_id: str,
        email: str,
        name: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> ProvisionedUser:
        """Provision a user from SSO"""
        # Check if user exists
        if user_id in self.users:
            # Update existing user
            user = self.users[user_id]
            user.email = email
            user.name = name
            user.last_sync = datetime.utcnow()
        else:
            # Create new user
            user = ProvisionedUser(
                user_id=user_id,
                email=email,
                name=name
            )
            self.users[user_id] = user

        # Apply provisioning rules
        self._apply_rules(user, attributes or {})

        return user

    def _apply_rules(self, user: ProvisionedUser, attributes: Dict[str, Any]) -> None:
        """Apply provisioning rules to user"""
        for rule in self.rules:
            attr_value = attributes.get(rule.attribute)
            if attr_value == rule.value:
                if rule.action == ProvisioningAction.CREATE:
                    for role in rule.roles:
                        if role not in user.roles:
                            user.roles.append(role)
                elif rule.action == ProvisioningAction.DEACTIVATE:
                    user.active = False

    def deprovision_user(self, user_id: str) -> bool:
        """Deprovision a user"""
        if user_id in self.users:
            self.users[user_id].active = False
            return True
        return False

    def sync_users(self, sso_users: List[Dict[str, Any]]) -> Dict[str, int]:
        """Sync users from SSO"""
        results = {"created": 0, "updated": 0, "deactivated": 0}

        for sso_user in sso_users:
            user_id = sso_user.get("user_id")
            if user_id:
                if user_id in self.users:
                    results["updated"] += 1
                else:
                    results["created"] += 1
                self.provision_user(
                    user_id=user_id,
                    email=sso_user.get("email", ""),
                    name=sso_user.get("name"),
                    attributes=sso_user
                )

        return results

    def get_active_users(self) -> List[ProvisionedUser]:
        """Get all active users"""
        return [u for u in self.users.values() if u.active]
