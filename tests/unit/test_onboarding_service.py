"""
Unit tests for Onboarding Service.
Uses mocked database sessions - no Docker required.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime

from backend.services.onboarding_service import (
    OnboardingService,
    OnboardingStep,
    ONBOARDING_STEPS
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def onboarding_service(mock_db):
    """Onboarding service instance with mocked DB."""
    company_id = uuid4()
    return OnboardingService(mock_db, company_id)


class TestOnboardingServiceInit:
    """Tests for OnboardingService initialization."""
    
    def test_init_with_company_id(self, mock_db):
        """Test init with company_id."""
        company_id = uuid4()
        service = OnboardingService(mock_db, company_id)
        
        assert service.db == mock_db
        assert service.company_id == company_id
    
    def test_init_without_company_id(self, mock_db):
        """Test init without company_id (new onboarding)."""
        service = OnboardingService(mock_db)
        
        assert service.db == mock_db
        assert service.company_id is None
    
    def test_init_requires_db(self):
        """Test that init requires db parameter."""
        with pytest.raises(ValueError):
            OnboardingService(None)


class TestOnboardingStepEnum:
    """Tests for OnboardingStep enum."""
    
    def test_all_steps_defined(self):
        """Test that all expected steps are defined."""
        assert OnboardingStep.COMPANY_INFO == "company_info"
        assert OnboardingStep.ADMIN_USER == "admin_user"
        assert OnboardingStep.SUBSCRIPTION == "subscription"
        assert OnboardingStep.INTEGRATION == "integration"
        assert OnboardingStep.TRAINING == "training"
        assert OnboardingStep.COMPLETE == "complete"
    
    def test_onboarding_steps_order(self):
        """Test that steps are in correct order."""
        assert ONBOARDING_STEPS[0] == OnboardingStep.COMPANY_INFO
        assert ONBOARDING_STEPS[-1] == OnboardingStep.COMPLETE
    
    def test_onboarding_steps_count(self):
        """Test that there are exactly 6 steps."""
        assert len(ONBOARDING_STEPS) == 6


class TestStartOnboarding:
    """Tests for start_onboarding method."""
    
    @pytest.mark.asyncio
    async def test_start_onboarding_creates_company(self, onboarding_service, mock_db):
        """Test that start_onboarding creates company record."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await onboarding_service.start_onboarding(
            company_name="Test Company",
            admin_email="admin@test.com",
            admin_name="Admin User"
        )
        
        mock_db.add.assert_called()
    
    @pytest.mark.asyncio
    async def test_start_onboarding_returns_company_id(self, onboarding_service, mock_db):
        """Test that start_onboarding returns company_id."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await onboarding_service.start_onboarding(
            company_name="Test Company",
            admin_email="admin@test.com",
            admin_name="Admin User"
        )
        
        assert "company_id" in result
        assert "current_step" in result
    
    @pytest.mark.asyncio
    async def test_start_onboarding_validates_required_fields(self, onboarding_service):
        """Test that start_onboarding validates required fields."""
        with pytest.raises(ValueError):
            await onboarding_service.start_onboarding(
                company_name="",
                admin_email="admin@test.com",
                admin_name="Admin User"
            )
    
    @pytest.mark.asyncio
    async def test_start_onboarding_validates_email(self, onboarding_service, mock_db):
        """Test that start_onboarding validates email format."""
        with pytest.raises(ValueError):
            await onboarding_service.start_onboarding(
                company_name="Test Company",
                admin_email="invalid-email",
                admin_name="Admin User"
            )
    
    @pytest.mark.asyncio
    async def test_start_onboarding_validates_admin_name(self, onboarding_service, mock_db):
        """Test that start_onboarding validates admin name."""
        with pytest.raises(ValueError):
            await onboarding_service.start_onboarding(
                company_name="Test Company",
                admin_email="admin@test.com",
                admin_name=""
            )


class TestCompleteOnboardingStep:
    """Tests for complete_onboarding_step method."""
    
    @pytest.mark.asyncio
    async def test_complete_step_returns_next_step(self, onboarding_service, mock_db):
        """Test that completing step returns next step."""
        mock_company = MagicMock()
        mock_company.id = onboarding_service.company_id
        mock_company.steps_completed = []
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_company
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        
        result = await onboarding_service.complete_onboarding_step(
            step=OnboardingStep.COMPANY_INFO,
            data={"name": "Updated Name"}
        )
        
        assert result is not None
        assert "success" in result
    
    @pytest.mark.asyncio
    async def test_complete_step_updates_progress(self, onboarding_service, mock_db):
        """Test that completing step updates progress."""
        mock_company = MagicMock()
        mock_company.id = onboarding_service.company_id
        mock_company.steps_completed = []
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_company
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        
        result = await onboarding_service.complete_onboarding_step(
            step=OnboardingStep.COMPANY_INFO,
            data={}
        )
        
        mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_complete_step_requires_company_id(self, mock_db):
        """Test that complete_step requires company_id."""
        service = OnboardingService(mock_db, None)
        
        with pytest.raises(ValueError):
            await service.complete_onboarding_step(
                step=OnboardingStep.COMPANY_INFO,
                data={}
            )


class TestGetOnboardingStatus:
    """Tests for get_onboarding_status method."""
    
    @pytest.mark.asyncio
    async def test_get_status_returns_progress(self, onboarding_service, mock_db):
        """Test that get_onboarding_status returns progress."""
        mock_company = MagicMock()
        mock_company.id = onboarding_service.company_id
        mock_company.steps_completed = [OnboardingStep.COMPANY_INFO.value]
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_company
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await onboarding_service.get_onboarding_status()
        
        assert "current_step" in result
        assert "steps_completed" in result
        assert "progress_percentage" in result
    
    @pytest.mark.asyncio
    async def test_get_status_requires_company_id(self, mock_db):
        """Test that get_status requires company_id."""
        service = OnboardingService(mock_db, None)
        
        with pytest.raises(ValueError):
            await service.get_onboarding_status()


class TestSetupCompanyDefaults:
    """Tests for setup_company_defaults method."""
    
    @pytest.mark.asyncio
    async def test_setup_defaults_returns_dict(self, onboarding_service, mock_db):
        """Test that setup_defaults returns defaults dict."""
        result = await onboarding_service.setup_company_defaults()
        
        assert "company_id" in result
        assert "defaults" in result
    
    @pytest.mark.asyncio
    async def test_setup_defaults_includes_timezone(self, onboarding_service, mock_db):
        """Test that defaults include timezone."""
        result = await onboarding_service.setup_company_defaults()
        
        assert "timezone" in result["defaults"]
    
    @pytest.mark.asyncio
    async def test_setup_defaults_requires_company_id(self, mock_db):
        """Test that setup_defaults requires company_id."""
        service = OnboardingService(mock_db, None)
        
        with pytest.raises(ValueError):
            await service.setup_company_defaults()


class TestCreateAdminUser:
    """Tests for create_admin_user method."""
    
    @pytest.mark.asyncio
    async def test_create_admin_user_creates_record(self, onboarding_service, mock_db):
        """Test that admin user is created."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Mock checking for existing user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await onboarding_service.create_admin_user(
            email="admin@test.com",
            name="Admin User",
            password="securepassword123"
        )
        
        mock_db.add.assert_called()
    
    @pytest.mark.asyncio
    async def test_create_admin_user_validates_email(self, onboarding_service, mock_db):
        """Test that create_admin_user validates email."""
        with pytest.raises(ValueError):
            await onboarding_service.create_admin_user(
                email="invalid-email",
                name="Admin User",
                password="securepassword123"
            )
    
    @pytest.mark.asyncio
    async def test_create_admin_user_validates_password_length(self, onboarding_service, mock_db):
        """Test that password must be at least 8 characters."""
        with pytest.raises(ValueError):
            await onboarding_service.create_admin_user(
                email="admin@test.com",
                name="Admin User",
                password="short"
            )
    
    @pytest.mark.asyncio
    async def test_create_admin_user_requires_company_id(self, mock_db):
        """Test that create_admin_user requires company_id."""
        service = OnboardingService(mock_db, None)
        
        with pytest.raises(ValueError):
            await service.create_admin_user(
                email="admin@test.com",
                name="Admin User",
                password="securepassword123"
            )


class TestInitializeSubscription:
    """Tests for initialize_subscription method."""
    
    @pytest.mark.asyncio
    async def test_initialize_subscription_creates_record(self, onboarding_service, mock_db):
        """Test that subscription is created."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await onboarding_service.initialize_subscription(
            tier="parwa",
            billing_email="billing@test.com"
        )
        
        mock_db.add.assert_called()
    
    @pytest.mark.asyncio
    async def test_initialize_subscription_uses_correct_tier(self, onboarding_service, mock_db):
        """Test that subscription uses specified tier."""
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await onboarding_service.initialize_subscription(
            tier="parwa_high",
            billing_email="billing@test.com"
        )
        
        assert result is not None
        assert result["tier"] == "parwa_high"
    
    @pytest.mark.asyncio
    async def test_initialize_subscription_validates_tier(self, onboarding_service, mock_db):
        """Test that tier is validated."""
        with pytest.raises(ValueError):
            await onboarding_service.initialize_subscription(
                tier="invalid_tier",
                billing_email="billing@test.com"
            )
    
    @pytest.mark.asyncio
    async def test_initialize_subscription_validates_email(self, onboarding_service, mock_db):
        """Test that billing email is validated."""
        with pytest.raises(ValueError):
            await onboarding_service.initialize_subscription(
                tier="parwa",
                billing_email="invalid-email"
            )


class TestSendWelcomeEmail:
    """Tests for send_welcome_email method."""
    
    @pytest.mark.asyncio
    async def test_send_welcome_email_returns_sent(self, onboarding_service, mock_db):
        """Test that welcome email is marked as sent."""
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "test@example.com"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await onboarding_service.send_welcome_email(mock_user.id)
        
        assert "sent" in result
        assert result["sent"] is True
    
    @pytest.mark.asyncio
    async def test_send_welcome_email_includes_email(self, onboarding_service, mock_db):
        """Test that response includes email."""
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "test@example.com"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await onboarding_service.send_welcome_email(mock_user.id)
        
        assert result["email"] == "test@example.com"


class TestValidateOnboardingData:
    """Tests for validate_onboarding_data method."""
    
    @pytest.mark.asyncio
    async def test_validate_company_info_step(self, onboarding_service):
        """Test validating company_info step data."""
        result = await onboarding_service.validate_onboarding_data(
            step=OnboardingStep.COMPANY_INFO,
            data={"name": "Valid Company", "industry": "Tech"}
        )
        
        assert "valid" in result
        assert "errors" in result
        assert result["valid"] is True
    
    @pytest.mark.asyncio
    async def test_validate_returns_errors_for_invalid_data(self, onboarding_service):
        """Test that validation returns errors for invalid data."""
        result = await onboarding_service.validate_onboarding_data(
            step=OnboardingStep.COMPANY_INFO,
            data={"name": ""}  # Empty name should fail
        )
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
    
    @pytest.mark.asyncio
    async def test_validate_admin_user_step(self, onboarding_service):
        """Test validating admin_user step data."""
        result = await onboarding_service.validate_onboarding_data(
            step=OnboardingStep.ADMIN_USER,
            data={
                "email": "admin@test.com",
                "name": "Admin",
                "password": "password123"
            }
        )
        
        assert result["valid"] is True
    
    @pytest.mark.asyncio
    async def test_validate_subscription_step(self, onboarding_service):
        """Test validating subscription step data."""
        result = await onboarding_service.validate_onboarding_data(
            step=OnboardingStep.SUBSCRIPTION,
            data={
                "tier": "parwa",
                "billing_email": "billing@test.com"
            }
        )
        
        assert result["valid"] is True


class TestGetOnboardingProgressPercentage:
    """Tests for get_onboarding_progress_percentage method."""
    
    @pytest.mark.asyncio
    async def test_progress_zero_at_start(self, onboarding_service, mock_db):
        """Test progress is 0% at start."""
        mock_company = MagicMock()
        mock_company.steps_completed = []
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_company
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await onboarding_service.get_onboarding_progress_percentage()
        
        assert result == 0.0
    
    @pytest.mark.partial
    async def test_progress_100_when_complete(self, onboarding_service, mock_db):
        """Test progress is 100% when complete."""
        mock_company = MagicMock()
        mock_company.steps_completed = [s.value for s in ONBOARDING_STEPS]
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_company
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await onboarding_service.get_onboarding_progress_percentage()
        
        assert result == 100.0
    
    @pytest.mark.asyncio
    async def test_progress_partial(self, onboarding_service, mock_db):
        """Test partial progress calculation."""
        mock_company = MagicMock()
        mock_company.steps_completed = [
            OnboardingStep.COMPANY_INFO.value,
            OnboardingStep.ADMIN_USER.value,
        ]
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_company
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await onboarding_service.get_onboarding_progress_percentage()
        
        # 2 out of 6 steps = ~33.3%
        assert result > 0
        assert result < 100
    
    @pytest.mark.asyncio
    async def test_progress_without_company_id(self, mock_db):
        """Test progress returns 0 without company_id."""
        service = OnboardingService(mock_db, None)
        
        result = await service.get_onboarding_progress_percentage()
        
        assert result == 0.0


class TestEmailValidation:
    """Tests for email validation helper."""
    
    def test_valid_email(self, onboarding_service):
        """Test valid email passes validation."""
        assert onboarding_service._validate_email("test@example.com") is True
        assert onboarding_service._validate_email("user.name@domain.org") is True
    
    def test_invalid_email(self, onboarding_service):
        """Test invalid email fails validation."""
        assert onboarding_service._validate_email("invalid") is False
        assert onboarding_service._validate_email("invalid@") is False
        assert onboarding_service._validate_email("@domain.com") is False
        assert onboarding_service._validate_email("") is False
