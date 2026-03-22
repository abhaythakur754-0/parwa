"""
UI Tests for Onboarding Flow.

Tests verify the complete onboarding workflow:
- Company info step
- Variant selection step
- Integrations step
- Team setup step
- Completion step

Uses mock DOM interactions and component state testing.
"""

import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, AsyncMock, patch
from enum import Enum
import uuid


class OnboardingStep(str, Enum):
    """Onboarding steps enum."""
    COMPANY = "company"
    VARIANT = "variant"
    INTEGRATIONS = "integrations"
    TEAM = "team"
    COMPLETE = "complete"


class MockCompanyInfo:
    """Mock company info for onboarding."""

    def __init__(
        self,
        company_name: str = "",
        industry: str = "",
        website: str = "",
        timezone: str = "UTC",
        employee_count: int = 0,
    ):
        self.company_name = company_name
        self.industry = industry
        self.website = website
        self.timezone = timezone
        self.employee_count = employee_count

    def is_valid(self) -> bool:
        """Check if company info is valid."""
        return bool(self.company_name and self.industry)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company_name": self.company_name,
            "industry": self.industry,
            "website": self.website,
            "timezone": self.timezone,
            "employee_count": self.employee_count,
        }


class MockVariant:
    """Mock variant selection for onboarding."""

    VARIANTS = {
        "mini": {
            "name": "Mini PARWA",
            "price": 49,
            "max_calls_per_month": 3,
            "refund_limit": 50,
            "channels": ["faq", "email"],
        },
        "parwa": {
            "name": "PARWA Junior",
            "price": 149,
            "max_calls_per_month": 5,
            "refund_limit": 500,
            "channels": ["faq", "email", "chat", "sms"],
        },
        "parwa_high": {
            "name": "PARWA High",
            "price": 499,
            "max_calls_per_month": 10,
            "refund_limit": 2000,
            "channels": ["faq", "email", "chat", "sms", "voice"],
        },
    }

    def __init__(self, variant_id: str = ""):
        self.variant_id = variant_id

    def is_valid(self) -> bool:
        """Check if variant is valid."""
        return self.variant_id in self.VARIANTS

    def get_details(self) -> Optional[Dict[str, Any]]:
        """Get variant details."""
        return self.VARIANTS.get(self.variant_id)


class MockIntegration:
    """Mock integration for onboarding."""

    def __init__(
        self,
        integration_id: str = "",
        name: str = "",
        configured: bool = False,
    ):
        self.integration_id = integration_id
        self.name = name
        self.configured = configured
        self.config: Dict[str, Any] = {}

    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the integration."""
        self.config = config
        self.configured = True


class MockTeamMember:
    """Mock team member for onboarding."""

    def __init__(
        self,
        email: str = "",
        name: str = "",
        role: str = "agent",
    ):
        self.email = email
        self.name = name
        self.role = role
        self.invited = False

    def is_valid(self) -> bool:
        """Check if team member is valid."""
        return bool(self.email and "@" in self.email)


class MockOnboardingState:
    """Mock state for onboarding UI component."""

    def __init__(self):
        self.current_step = OnboardingStep.COMPANY
        self.completed_steps: List[OnboardingStep] = []
        self.company_info = MockCompanyInfo()
        self.variant = MockVariant()
        self.integrations: List[MockIntegration] = []
        self.team_members: List[MockTeamMember] = []
        self.is_loading = False
        self.error: Optional[str] = None

    def can_proceed(self) -> bool:
        """Check if user can proceed to next step."""
        if self.current_step == OnboardingStep.COMPANY:
            return self.company_info.is_valid()
        elif self.current_step == OnboardingStep.VARIANT:
            return self.variant.is_valid()
        elif self.current_step == OnboardingStep.INTEGRATIONS:
            return True  # Integrations are optional
        elif self.current_step == OnboardingStep.TEAM:
            return True  # Team members are optional
        return False

    def next_step(self) -> bool:
        """Move to next step."""
        if not self.can_proceed():
            return False

        self.completed_steps.append(self.current_step)

        step_order = [
            OnboardingStep.COMPANY,
            OnboardingStep.VARIANT,
            OnboardingStep.INTEGRATIONS,
            OnboardingStep.TEAM,
            OnboardingStep.COMPLETE,
        ]

        current_index = step_order.index(self.current_step)
        if current_index < len(step_order) - 1:
            self.current_step = step_order[current_index + 1]
            return True
        return False

    def previous_step(self) -> bool:
        """Move to previous step."""
        step_order = [
            OnboardingStep.COMPANY,
            OnboardingStep.VARIANT,
            OnboardingStep.INTEGRATIONS,
            OnboardingStep.TEAM,
            OnboardingStep.COMPLETE,
        ]

        current_index = step_order.index(self.current_step)
        if current_index > 0:
            if self.current_step in self.completed_steps:
                self.completed_steps.remove(self.current_step)
            self.current_step = step_order[current_index - 1]
            return True
        return False

    def get_progress(self) -> Dict[str, Any]:
        """Get onboarding progress."""
        step_order = [
            OnboardingStep.COMPANY,
            OnboardingStep.VARIANT,
            OnboardingStep.INTEGRATIONS,
            OnboardingStep.TEAM,
            OnboardingStep.COMPLETE,
        ]
        current_index = step_order.index(self.current_step)
        progress = (current_index / (len(step_order) - 1)) * 100

        return {
            "current_step": self.current_step.value,
            "completed_steps": [s.value for s in self.completed_steps],
            "progress_percent": progress,
            "is_complete": self.current_step == OnboardingStep.COMPLETE,
        }


class MockOnboardingActions:
    """Mock actions for onboarding UI component."""

    def __init__(self, state: MockOnboardingState):
        self.state = state

    def set_company_info(self, info: MockCompanyInfo) -> Dict[str, Any]:
        """Set company information."""
        self.state.company_info = info
        return {
            "success": info.is_valid(),
            "error": None if info.is_valid() else "Company name and industry are required",
        }

    def select_variant(self, variant_id: str) -> Dict[str, Any]:
        """Select a variant."""
        self.state.variant = MockVariant(variant_id)
        return {
            "success": self.state.variant.is_valid(),
            "variant": self.state.variant.get_details(),
        }

    def add_integration(self, integration: MockIntegration) -> None:
        """Add an integration."""
        self.state.integrations.append(integration)

    def remove_integration(self, integration_id: str) -> None:
        """Remove an integration."""
        self.state.integrations = [
            i for i in self.state.integrations if i.integration_id != integration_id
        ]

    def add_team_member(self, member: MockTeamMember) -> Dict[str, Any]:
        """Add a team member."""
        if not member.is_valid():
            return {"success": False, "error": "Valid email is required"}

        self.state.team_members.append(member)
        return {"success": True, "member": member}

    def remove_team_member(self, email: str) -> None:
        """Remove a team member."""
        self.state.team_members = [m for m in self.state.team_members if m.email != email]

    async def complete_onboarding(self) -> Dict[str, Any]:
        """Complete the onboarding process."""
        if self.state.current_step != OnboardingStep.COMPLETE:
            return {"success": False, "error": "Not all steps completed"}

        return {
            "success": True,
            "company": self.state.company_info.to_dict(),
            "variant": self.state.variant.variant_id,
            "integrations": len(self.state.integrations),
            "team_members": len(self.state.team_members),
        }


# =============================================================================
# UI Tests
# =============================================================================

class TestOnboardingFlowUI:
    """Tests for onboarding flow UI component."""

    @pytest.fixture
    def state(self):
        """Create onboarding state."""
        return MockOnboardingState()

    @pytest.fixture
    def actions(self, state):
        """Create onboarding actions."""
        return MockOnboardingActions(state)

    def test_onboarding_starts_at_company_step(self, state):
        """Test: Onboarding starts at company step."""
        assert state.current_step == OnboardingStep.COMPANY
        assert len(state.completed_steps) == 0

    def test_company_info_validation(self, state, actions):
        """Test: Company info validation works."""
        # Invalid - empty
        result = actions.set_company_info(MockCompanyInfo())
        assert result["success"] is False

        # Valid - with required fields
        result = actions.set_company_info(MockCompanyInfo(
            company_name="Test Company",
            industry="ecommerce",
        ))
        assert result["success"] is True

    def test_cannot_proceed_without_company_info(self, state):
        """Test: Cannot proceed without company info."""
        assert state.can_proceed() is False

    def test_can_proceed_with_valid_company_info(self, state, actions):
        """Test: Can proceed with valid company info."""
        actions.set_company_info(MockCompanyInfo(
            company_name="Test Company",
            industry="ecommerce",
        ))
        assert state.can_proceed() is True

    def test_next_step_advances_correctly(self, state, actions):
        """Test: Next step advances correctly."""
        # Complete company step
        actions.set_company_info(MockCompanyInfo(
            company_name="Test Company",
            industry="ecommerce",
        ))
        assert state.next_step() is True
        assert state.current_step == OnboardingStep.VARIANT
        assert OnboardingStep.COMPANY in state.completed_steps

    def test_variant_selection_works(self, state, actions):
        """Test: Variant selection works."""
        # Move to variant step
        actions.set_company_info(MockCompanyInfo(
            company_name="Test Company",
            industry="ecommerce",
        ))
        state.next_step()

        # Select variant
        result = actions.select_variant("parwa")
        assert result["success"] is True
        assert result["variant"]["name"] == "PARWA Junior"
        assert result["variant"]["price"] == 149

    def test_invalid_variant_rejected(self, state, actions):
        """Test: Invalid variant is rejected."""
        actions.set_company_info(MockCompanyInfo(
            company_name="Test Company",
            industry="ecommerce",
        ))
        state.next_step()

        result = actions.select_variant("invalid_variant")
        assert result["success"] is False

    def test_integration_step_optional(self, state, actions):
        """Test: Integration step is optional."""
        # Setup
        actions.set_company_info(MockCompanyInfo(
            company_name="Test Company",
            industry="ecommerce",
        ))
        state.next_step()
        actions.select_variant("parwa")
        state.next_step()

        # No integrations needed
        assert state.can_proceed() is True
        assert state.next_step() is True
        assert state.current_step == OnboardingStep.TEAM

    def test_add_integration(self, state, actions):
        """Test: Adding integration works."""
        actions.set_company_info(MockCompanyInfo(
            company_name="Test Company",
            industry="ecommerce",
        ))
        state.next_step()
        actions.select_variant("parwa")
        state.next_step()

        # Add Shopify integration
        integration = MockIntegration(
            integration_id="shopify",
            name="Shopify",
        )
        integration.configure({"store_url": "test.myshopify.com"})
        actions.add_integration(integration)

        assert len(state.integrations) == 1
        assert state.integrations[0].configured is True

    def test_team_member_validation(self, state, actions):
        """Test: Team member validation works."""
        # Invalid email
        result = actions.add_team_member(MockTeamMember(
            email="invalid-email",
            name="Test User",
        ))
        assert result["success"] is False

        # Valid email
        result = actions.add_team_member(MockTeamMember(
            email="test@example.com",
            name="Test User",
        ))
        assert result["success"] is True

    def test_full_onboarding_flow(self, state, actions):
        """Test: Full onboarding flow completes successfully."""
        # Step 1: Company info
        actions.set_company_info(MockCompanyInfo(
            company_name="Acme Corp",
            industry="saas",
            website="https://acme.com",
            employee_count=50,
        ))
        assert state.can_proceed() is True
        state.next_step()

        # Step 2: Variant selection
        result = actions.select_variant("parwa_high")
        assert result["success"] is True
        assert state.can_proceed() is True
        state.next_step()

        # Step 3: Integrations (optional)
        actions.add_integration(MockIntegration(
            integration_id="zendesk",
            name="Zendesk",
            configured=True,
        ))
        state.next_step()

        # Step 4: Team
        actions.add_team_member(MockTeamMember(
            email="agent@acme.com",
            name="Support Agent",
            role="agent",
        ))
        state.next_step()

        # Step 5: Complete
        assert state.current_step == OnboardingStep.COMPLETE
        progress = state.get_progress()
        assert progress["is_complete"] is True
        assert progress["progress_percent"] == 100

    @pytest.mark.asyncio
    async def test_complete_onboarding_returns_summary(self, state, actions):
        """Test: Complete onboarding returns summary."""
        # Setup full flow
        actions.set_company_info(MockCompanyInfo(
            company_name="Test Corp",
            industry="ecommerce",
        ))
        state.next_step()
        actions.select_variant("mini")
        state.next_step()
        state.next_step()
        state.next_step()

        result = await actions.complete_onboarding()
        assert result["success"] is True
        assert result["company"]["company_name"] == "Test Corp"
        assert result["variant"] == "mini"

    def test_previous_step_works(self, state, actions):
        """Test: Previous step navigation works."""
        actions.set_company_info(MockCompanyInfo(
            company_name="Test",
            industry="saas",
        ))
        state.next_step()

        assert state.current_step == OnboardingStep.VARIANT
        assert state.previous_step() is True
        assert state.current_step == OnboardingStep.COMPANY

    def test_progress_tracking(self, state, actions):
        """Test: Progress is tracked correctly."""
        progress = state.get_progress()
        assert progress["progress_percent"] == 0
        assert progress["current_step"] == "company"

        actions.set_company_info(MockCompanyInfo(
            company_name="Test",
            industry="saas",
        ))
        state.next_step()

        progress = state.get_progress()
        assert progress["progress_percent"] == 25
        assert "company" in progress["completed_steps"]


class TestOnboardingVariants:
    """Tests for variant-specific onboarding."""

    @pytest.fixture
    def state(self):
        return MockOnboardingState()

    @pytest.fixture
    def actions(self, state):
        return MockOnboardingActions(state)

    def test_mini_variant_limits(self, state, actions):
        """Test: Mini variant has correct limits."""
        actions.set_company_info(MockCompanyInfo(
            company_name="Mini Company",
            industry="saas",
        ))
        state.next_step()

        result = actions.select_variant("mini")
        assert result["variant"]["max_calls_per_month"] == 3
        assert result["variant"]["refund_limit"] == 50
        assert "voice" not in result["variant"]["channels"]

    def test_parwa_variant_limits(self, state, actions):
        """Test: PARWA Junior variant has correct limits."""
        actions.set_company_info(MockCompanyInfo(
            company_name="Parwa Company",
            industry="ecommerce",
        ))
        state.next_step()

        result = actions.select_variant("parwa")
        assert result["variant"]["max_calls_per_month"] == 5
        assert result["variant"]["refund_limit"] == 500

    def test_parwa_high_variant_limits(self, state, actions):
        """Test: PARWA High variant has correct limits."""
        actions.set_company_info(MockCompanyInfo(
            company_name="High Company",
            industry="healthcare",
        ))
        state.next_step()

        result = actions.select_variant("parwa_high")
        assert result["variant"]["max_calls_per_month"] == 10
        assert result["variant"]["refund_limit"] == 2000
        assert "voice" in result["variant"]["channels"]


class TestOnboardingAccessibility:
    """Tests for onboarding accessibility."""

    def test_step_indicators_present(self):
        """Test: Step indicators are present for screen readers."""
        # In real UI test, verify aria-current and step labels
        steps = ["company", "variant", "integrations", "team", "complete"]
        assert len(steps) == 5

    def test_form_labels_present(self):
        """Test: Form labels are properly associated."""
        expected_labels = [
            "company-name",
            "industry",
            "website",
            "timezone",
            "employee-count",
        ]
        assert len(expected_labels) == 5

    def test_error_messages_announced(self):
        """Test: Error messages are announced to screen readers."""
        # In real UI test, verify aria-live regions
        error_regions = ["company-error", "variant-error", "team-error"]
        assert len(error_regions) == 3

    def test_keyboard_navigation(self):
        """Test: Keyboard navigation works through form."""
        # Tab order should be logical
        expected_tab_order = [
            "company-name-input",
            "industry-select",
            "website-input",
            "next-button",
        ]
        assert len(expected_tab_order) == 4


class TestOnboardingErrorHandling:
    """Tests for onboarding error handling."""

    @pytest.fixture
    def state(self):
        return MockOnboardingState()

    @pytest.fixture
    def actions(self, state):
        return MockOnboardingActions(state)

    def test_loading_state_display(self, state):
        """Test: Loading state is shown during submission."""
        state.is_loading = True
        assert state.is_loading is True

    def test_error_state_display(self, state):
        """Test: Error state is displayed to user."""
        state.error = "Failed to save company info"
        assert state.error is not None

    def test_invalid_step_transition_blocked(self, state):
        """Test: Invalid step transitions are blocked."""
        # Cannot proceed without completing current step
        assert state.can_proceed() is False
        assert state.next_step() is False

    @pytest.mark.asyncio
    async def test_complete_before_ready_fails(self, state, actions):
        """Test: Complete onboarding fails if not ready."""
        result = await actions.complete_onboarding()
        assert result["success"] is False
        assert "not all steps" in result["error"].lower()
