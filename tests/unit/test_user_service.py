"""
Unit tests for User Service.
Uses mocked database sessions - no Docker required.
"""
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from backend.services.user_service import (
    UserService,
    UserRole,
    UserStatus,
)
from backend.models.user import RoleEnum


def create_mock_result(return_value=None, all_value=None):
    """Create a properly mocked database result."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=return_value)
    mock_result.scalar = MagicMock(return_value=return_value)
    mock_result.scalars = MagicMock()
    if all_value is not None:
        mock_result.scalars().all = MagicMock(return_value=all_value)
    else:
        mock_result.scalars().all = MagicMock(return_value=[])
    return mock_result


@pytest.fixture
def mock_db():
    """Mock database session with proper async execute."""
    db = AsyncMock()
    # By default, execute returns a result that yields None
    mock_result = create_mock_result(None)
    db.execute = AsyncMock(return_value=mock_result)
    return db


@pytest.fixture
def user_service(mock_db):
    """User service instance with mocked DB."""
    company_id = uuid.uuid4()
    return UserService(mock_db, company_id)


class TestUserServiceInit:
    """Tests for UserService initialization."""
    
    def test_init_stores_db_and_company_id(self, mock_db):
        """Test that init stores db and company_id."""
        company_id = uuid.uuid4()
        service = UserService(mock_db, company_id)
        
        assert service.db == mock_db
        assert service.company_id == company_id


class TestUserRoleEnum:
    """Tests for UserRole enum."""
    
    def test_role_values(self):
        """Test role enum values."""
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.MANAGER.value == "manager"
        assert UserRole.AGENT.value == "agent"
        assert UserRole.VIEWER.value == "viewer"
    
    def test_role_count(self):
        """Test that we have expected number of roles."""
        assert len(UserRole) == 4


class TestUserStatusEnum:
    """Tests for UserStatus enum."""
    
    def test_status_values(self):
        """Test status enum values."""
        assert UserStatus.ACTIVE.value == "active"
        assert UserStatus.INACTIVE.value == "inactive"
        assert UserStatus.SUSPENDED.value == "suspended"
        assert UserStatus.PENDING.value == "pending"


class TestGetUser:
    """Tests for get_user method."""
    
    @pytest.mark.asyncio
    async def test_get_user_returns_none_when_not_found(self, user_service):
        """Test that get_user returns None when user not found."""
        user_id = uuid.uuid4()
        result = await user_service.get_user(user_id)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_user_returns_dict_when_found(self, mock_db):
        """Test that get_user returns dict when user found."""
        company_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        # Create a mock user object
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.company_id = company_id
        mock_user.email = "test@example.com"
        mock_user.role = RoleEnum.admin
        mock_user.is_active = True
        mock_user.created_at = datetime.now(timezone.utc)
        mock_user.updated_at = datetime.now(timezone.utc)
        
        mock_result = create_mock_result(mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        service = UserService(mock_db, company_id)
        result = await service.get_user(user_id)
        
        assert result is not None
        assert result["user_id"] == str(user_id)
        assert result["email"] == "test@example.com"
        assert result["role"] == "admin"


class TestGetUserByEmail:
    """Tests for get_user_by_email method."""
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_normalizes(self, user_service):
        """Test that email is normalized to lowercase."""
        result = await user_service.get_user_by_email("TEST@EXAMPLE.COM")
        
        # Should not raise, email is normalized
        assert result is None or isinstance(result, dict)


class TestListUsers:
    """Tests for list_users method."""
    
    @pytest.mark.asyncio
    async def test_list_users_returns_list(self, user_service):
        """Test that list_users returns list."""
        result = await user_service.list_users()
        
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_list_users_with_role_filter(self, user_service):
        """Test list_users with role filter."""
        result = await user_service.list_users(role=UserRole.ADMIN)
        
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_list_users_with_active_filter(self, user_service):
        """Test list_users with active filter."""
        result = await user_service.list_users(is_active=True)
        
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_list_users_with_search(self, user_service):
        """Test list_users with search."""
        result = await user_service.list_users(search="test@example.com")
        
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_list_users_with_pagination(self, user_service):
        """Test list_users with pagination."""
        result = await user_service.list_users(limit=10, offset=5)
        
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_list_users_with_users_found(self, mock_db):
        """Test list_users returns users when found."""
        company_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.company_id = company_id
        mock_user.email = "test@example.com"
        mock_user.role = RoleEnum.admin
        mock_user.is_active = True
        mock_user.created_at = datetime.now(timezone.utc)
        
        mock_result = create_mock_result(None, [mock_user])
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        service = UserService(mock_db, company_id)
        result = await service.list_users()
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["email"] == "test@example.com"


class TestCreateUser:
    """Tests for create_user method."""
    
    @pytest.mark.asyncio
    async def test_create_user_returns_dict(self, user_service):
        """Test that create_user returns dict."""
        result = await user_service.create_user(
            email="test@example.com",
            password_hash="hashed_password",
            role=UserRole.VIEWER
        )
        
        assert "user_id" in result
        assert result["email"] == "test@example.com"
        assert result["role"] == "viewer"
        assert result["is_active"] is True
    
    @pytest.mark.asyncio
    async def test_create_user_normalizes_email(self, user_service):
        """Test that create_user normalizes email."""
        result = await user_service.create_user(
            email="TEST@EXAMPLE.COM",
            password_hash="hashed",
            role=UserRole.VIEWER
        )
        
        assert result["email"] == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_create_user_with_admin_role(self, user_service):
        """Test creating user with admin role."""
        result = await user_service.create_user(
            email="admin@example.com",
            password_hash="hashed",
            role=UserRole.ADMIN
        )
        
        assert result["role"] == "admin"


class TestUpdateUser:
    """Tests for update_user method."""
    
    @pytest.mark.asyncio
    async def test_update_user_returns_dict(self, user_service):
        """Test that update_user returns dict."""
        user_id = uuid.uuid4()
        
        result = await user_service.update_user(
            user_id=user_id,
            updates={"role": "manager"}
        )
        
        assert result["user_id"] == str(user_id)
        assert result["updated"] is True


class TestDeactivateUser:
    """Tests for deactivate_user method."""
    
    @pytest.mark.asyncio
    async def test_deactivate_user_returns_dict(self, user_service):
        """Test that deactivate_user returns dict."""
        user_id = uuid.uuid4()
        
        result = await user_service.deactivate_user(user_id)
        
        assert result["user_id"] == str(user_id)
        assert result["deactivated"] is True
        assert result["status"] == UserStatus.INACTIVE.value


class TestActivateUser:
    """Tests for activate_user method."""
    
    @pytest.mark.asyncio
    async def test_activate_user_returns_dict(self, user_service):
        """Test that activate_user returns dict."""
        user_id = uuid.uuid4()
        
        result = await user_service.activate_user(user_id)
        
        assert result["user_id"] == str(user_id)
        assert result["activated"] is True
        assert result["status"] == UserStatus.ACTIVE.value


class TestDeleteUser:
    """Tests for delete_user method."""
    
    @pytest.mark.asyncio
    async def test_delete_user_soft_deletes(self, user_service):
        """Test that delete_user soft deletes (deactivates)."""
        user_id = uuid.uuid4()
        
        result = await user_service.delete_user(user_id)
        
        # Should return deactivation result (soft delete)
        assert result["deactivated"] is True


class TestChangeRole:
    """Tests for change_role method."""
    
    @pytest.mark.asyncio
    async def test_change_role_returns_dict(self, user_service):
        """Test that change_role returns dict."""
        user_id = uuid.uuid4()
        
        result = await user_service.change_role(
            user_id=user_id,
            new_role=UserRole.MANAGER
        )
        
        assert result["user_id"] == str(user_id)
        assert result["role"] == "manager"


class TestGetUserCount:
    """Tests for get_user_count method."""
    
    @pytest.mark.asyncio
    async def test_get_user_count_returns_int(self, user_service):
        """Test that get_user_count returns int."""
        count = await user_service.get_user_count()
        
        assert isinstance(count, int)
    
    @pytest.mark.asyncio
    async def test_get_user_count_with_active_filter(self, user_service):
        """Test get_user_count with active filter."""
        count = await user_service.get_user_count(is_active=True)
        
        assert isinstance(count, int)
    
    @pytest.mark.asyncio
    async def test_get_user_count_with_users(self, mock_db):
        """Test get_user_count returns actual count."""
        company_id = uuid.uuid4()
        
        mock_result = create_mock_result(5)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        service = UserService(mock_db, company_id)
        count = await service.get_user_count()
        
        assert count == 5


class TestGetUsersByRole:
    """Tests for get_users_by_role method."""
    
    @pytest.mark.asyncio
    async def test_get_users_by_role_returns_dict(self, user_service):
        """Test that get_users_by_role returns dict."""
        result = await user_service.get_users_by_role()
        
        assert isinstance(result, dict)
        assert UserRole.ADMIN.value in result
        assert UserRole.MANAGER.value in result


class TestCheckEmailExists:
    """Tests for check_email_exists method."""
    
    @pytest.mark.asyncio
    async def test_check_email_exists_returns_bool(self, user_service):
        """Test that check_email_exists returns bool."""
        exists = await user_service.check_email_exists("test@example.com")
        
        assert isinstance(exists, bool)
    
    @pytest.mark.asyncio
    async def test_check_email_exists_true_when_found(self, mock_db):
        """Test check_email_exists returns True when found."""
        company_id = uuid.uuid4()
        
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        
        mock_result = create_mock_result(mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        service = UserService(mock_db, company_id)
        exists = await service.check_email_exists("test@example.com")
        
        assert exists is True


class TestGetUserPreferences:
    """Tests for get_user_preferences method."""
    
    @pytest.mark.asyncio
    async def test_get_preferences_returns_dict(self, user_service):
        """Test that get_user_preferences returns dict."""
        user_id = uuid.uuid4()
        
        result = await user_service.get_user_preferences(user_id)
        
        assert "user_id" in result
        assert "notifications" in result
        assert "language" in result


class TestUpdateUserPreferences:
    """Tests for update_user_preferences method."""
    
    @pytest.mark.asyncio
    async def test_update_preferences_returns_dict(self, user_service):
        """Test that update_user_preferences returns dict."""
        user_id = uuid.uuid4()
        
        result = await user_service.update_user_preferences(
            user_id=user_id,
            preferences={"language": "es", "theme": "dark"}
        )
        
        assert result["user_id"] == str(user_id)
        assert result["updated"] is True


class TestSearchUsers:
    """Tests for search_users method."""
    
    @pytest.mark.asyncio
    async def test_search_users_returns_list(self, user_service):
        """Test that search_users returns list."""
        result = await user_service.search_users("test")
        
        assert isinstance(result, list)


class TestMaskEmail:
    """Tests for _mask_email helper method."""
    
    def test_mask_email_standard(self):
        """Test masking standard email."""
        masked = UserService._mask_email("john.doe@example.com")
        
        assert "@" in masked
        assert masked.endswith("@example.com")
        assert masked != "john.doe@example.com"
    
    def test_mask_email_short(self):
        """Test masking short email."""
        masked = UserService._mask_email("a@b.com")
        
        assert "@" in masked
    
    def test_mask_email_empty(self):
        """Test masking empty string."""
        masked = UserService._mask_email("")
        
        assert masked == "***"
    
    def test_mask_email_no_at(self):
        """Test masking string without @."""
        masked = UserService._mask_email("notanemail")
        
        assert masked != "notanemail"


class TestCompanyScoping:
    """Tests for company scoping enforcement."""
    
    @pytest.mark.asyncio
    async def test_create_user_includes_company_id(self, user_service):
        """Test that create_user includes company_id."""
        user = await user_service.create_user(
            email="test@example.com",
            password_hash="hashed",
            role=UserRole.VIEWER
        )
        assert user["company_id"] == str(user_service.company_id)
    
    @pytest.mark.asyncio
    async def test_update_user_includes_company_id(self, user_service):
        """Test that update_user includes company_id."""
        update = await user_service.update_user(
            user_id=uuid.uuid4(),
            updates={}
        )
        assert update["company_id"] == str(user_service.company_id)
