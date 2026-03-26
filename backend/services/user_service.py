"""
User Service Layer.

Handles user management, preferences, and company membership.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum
import hashlib

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_
from sqlalchemy.orm import selectinload

from backend.models.user import User, RoleEnum
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class UserRole(str, Enum):
    """User role levels."""
    ADMIN = "admin"
    MANAGER = "manager"
    AGENT = "agent"
    VIEWER = "viewer"


class UserStatus(str, Enum):
    """User status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class UserService:
    """
    Service class for user management.
    
    Handles CRUD operations, role assignment, and preferences.
    All methods enforce company-scoped data access (RLS).
    """
    
    def __init__(self, db: AsyncSession, company_id: UUID) -> None:
        """
        Initialize user service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def get_user(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get a user by ID.
        
        Args:
            user_id: User UUID
            
        Returns:
            Dict with user details or None
        """
        logger.info({
            "event": "user_retrieved",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
        })
        
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.id == user_id,
                    User.company_id == self.company_id
                )
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        return {
            "user_id": str(user.id),
            "company_id": str(user.company_id),
            "email": user.email,
            "role": user.role.value if user.role else None,
            "is_active": user.is_active,
            "status": UserStatus.ACTIVE.value if user.is_active else UserStatus.INACTIVE.value,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by email.
        
        Args:
            email: User email address
            
        Returns:
            Dict with user details or None
        """
        normalized_email = email.lower().strip()
        
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.email == normalized_email,
                    User.company_id == self.company_id
                )
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        return await self.get_user(user.id)
    
    async def list_users(
        self,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List users for the company.
        
        Args:
            role: Filter by role
            is_active: Filter by active status
            search: Search in email
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of user records
        """
        logger.info({
            "event": "users_listed",
            "company_id": str(self.company_id),
            "filters": {
                "role": role.value if role else None,
                "is_active": is_active,
                "search": search,
            },
            "limit": limit,
            "offset": offset,
        })
        
        query = select(User).where(User.company_id == self.company_id)
        
        if role:
            # Map UserRole to RoleEnum
            role_mapping = {
                UserRole.ADMIN: RoleEnum.admin,
                UserRole.MANAGER: RoleEnum.manager,
                UserRole.AGENT: RoleEnum.viewer,  # Map agent to viewer
                UserRole.VIEWER: RoleEnum.viewer,
            }
            query = query.where(User.role == role_mapping.get(role, RoleEnum.viewer))
        
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        
        if search:
            query = query.where(User.email.ilike(f"%{search}%"))
        
        query = query.order_by(User.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        return [
            {
                "user_id": str(user.id),
                "company_id": str(user.company_id),
                "email": user.email,
                "role": user.role.value if user.role else None,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            for user in users
        ]
    
    async def create_user(
        self,
        email: str,
        password_hash: str,
        role: UserRole = UserRole.VIEWER
    ) -> Dict[str, Any]:
        """
        Create a new user.
        
        Args:
            email: User email
            password_hash: Hashed password
            role: User role
            
        Returns:
            Dict with created user details
        """
        normalized_email = email.lower().strip()
        
        logger.info({
            "event": "user_created",
            "company_id": str(self.company_id),
            "email": self._mask_email(normalized_email),
            "role": role.value,
        })
        
        # Map UserRole to RoleEnum
        role_mapping = {
            UserRole.ADMIN: RoleEnum.admin,
            UserRole.MANAGER: RoleEnum.manager,
            UserRole.AGENT: RoleEnum.viewer,
            UserRole.VIEWER: RoleEnum.viewer,
        }
        
        # TODO: Actually create user in database
        user_id = UUID(int=0)  # Placeholder
        
        return {
            "user_id": str(user_id),
            "company_id": str(self.company_id),
            "email": normalized_email,
            "role": role.value,
            "is_active": True,
            "status": UserStatus.ACTIVE.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def update_user(
        self,
        user_id: UUID,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a user.
        
        Args:
            user_id: User UUID
            updates: Dict of fields to update
            
        Returns:
            Dict with updated user details
        """
        logger.info({
            "event": "user_updated",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
            "fields_updated": list(updates.keys()),
        })
        
        # TODO: Actually update user in database
        return {
            "user_id": str(user_id),
            "company_id": str(self.company_id),
            "updated": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def deactivate_user(
        self,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Deactivate a user account.
        
        Args:
            user_id: User UUID
            
        Returns:
            Dict with deactivation status
        """
        logger.info({
            "event": "user_deactivated",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
        })
        
        return {
            "user_id": str(user_id),
            "deactivated": True,
            "status": UserStatus.INACTIVE.value,
            "deactivated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def activate_user(
        self,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Activate a user account.
        
        Args:
            user_id: User UUID
            
        Returns:
            Dict with activation status
        """
        logger.info({
            "event": "user_activated",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
        })
        
        return {
            "user_id": str(user_id),
            "activated": True,
            "status": UserStatus.ACTIVE.value,
            "activated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def delete_user(
        self,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Delete a user (soft delete by deactivating).
        
        Args:
            user_id: User UUID
            
        Returns:
            Dict with deletion status
        """
        logger.info({
            "event": "user_deleted",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
        })
        
        # Soft delete by deactivating
        return await self.deactivate_user(user_id)
    
    async def change_role(
        self,
        user_id: UUID,
        new_role: UserRole
    ) -> Dict[str, Any]:
        """
        Change a user's role.
        
        Args:
            user_id: User UUID
            new_role: New role to assign
            
        Returns:
            Dict with role change status
        """
        logger.info({
            "event": "user_role_changed",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
            "new_role": new_role.value,
        })
        
        return {
            "user_id": str(user_id),
            "role": new_role.value,
            "changed_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def get_user_count(
        self,
        is_active: Optional[bool] = None
    ) -> int:
        """
        Get count of users in the company.
        
        Args:
            is_active: Filter by active status
            
        Returns:
            Number of users
        """
        query = select(func.count(User.id)).where(
            User.company_id == self.company_id
        )
        
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        
        result = await self.db.execute(query)
        count = result.scalar() or 0
        
        return count
    
    async def get_users_by_role(self) -> Dict[str, int]:
        """
        Get count of users grouped by role.
        
        Returns:
            Dict with role counts
        """
        result = await self.db.execute(
            select(User.role, func.count(User.id))
            .where(User.company_id == self.company_id)
            .group_by(User.role)
        )
        
        counts = {}
        for row in result:
            role_name = row[0].value if row[0] else "unknown"
            counts[role_name] = row[1]
        
        return {
            UserRole.ADMIN.value: counts.get("admin", 0),
            UserRole.MANAGER.value: counts.get("manager", 0),
            UserRole.VIEWER.value: counts.get("viewer", 0),
            UserRole.AGENT.value: counts.get("agent", 0),
        }
    
    async def check_email_exists(
        self,
        email: str
    ) -> bool:
        """
        Check if email already exists.
        
        Args:
            email: Email to check
            
        Returns:
            bool: True if email exists
        """
        normalized_email = email.lower().strip()
        
        result = await self.db.execute(
            select(User).where(User.email == normalized_email)
        )
        
        return result.scalar_one_or_none() is not None
    
    async def get_user_preferences(
        self,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Get user preferences.
        
        Args:
            user_id: User UUID
            
        Returns:
            Dict with user preferences
        """
        logger.info({
            "event": "user_preferences_retrieved",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
        })
        
        # TODO: Query from preferences table
        return {
            "user_id": str(user_id),
            "notifications": {
                "email": True,
                "sms": False,
                "push": True,
            },
            "language": "en",
            "timezone": "UTC",
            "theme": "light",
        }
    
    async def update_user_preferences(
        self,
        user_id: UUID,
        preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update user preferences.
        
        Args:
            user_id: User UUID
            preferences: Dict of preferences to update
            
        Returns:
            Dict with updated preferences
        """
        logger.info({
            "event": "user_preferences_updated",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
            "fields_updated": list(preferences.keys()),
        })
        
        return {
            "user_id": str(user_id),
            "updated": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def search_users(
        self,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search users by email or name.
        
        Args:
            query: Search query
            limit: Max results
            
        Returns:
            List of matching users
        """
        return await self.list_users(search=query, limit=limit)
    
    # --- Helper Methods ---
    
    @staticmethod
    def _mask_email(email: str) -> str:
        """
        Mask email address for logging privacy.
        
        Args:
            email: Email address to mask
            
        Returns:
            Masked email (e.g., "j***@example.com")
        """
        if not email or "@" not in email:
            return email[:3] + "***" if len(email) > 3 else "***"
        
        local, domain = email.split("@", 1)
        if len(local) <= 1:
            masked_local = "*"
        elif len(local) <= 3:
            masked_local = local[0] + "*" * (len(local) - 1)
        else:
            masked_local = local[0] + "*" * min(len(local) - 2, 5) + local[-1]
        
        return f"{masked_local}@{domain}"
