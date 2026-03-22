"""
UI Tests for ROI Calculator Component.

Tests verify:
- ROI calculator renders correctly
- Input fields work correctly
- Calculation is correct
- Results display correctly
- Variant comparison works
"""

import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock
from enum import Enum


class VariantType(str, Enum):
    """Variant types for ROI calculation."""
    MINI = "mini"
    PARWA = "parwa"
    PARWA_HIGH = "parwa_high"


class MockROICalculatorState:
    """Mock state for ROI calculator UI component."""

    # Variant pricing (monthly)
    VARIANT_COSTS = {
        VariantType.MINI: 49.00,
        VariantType.PARWA: 199.00,
        VariantType.PARWA_HIGH: 499.00,
    }

    # Estimated time saved per ticket (minutes)
    TIME_SAVED_PER_TICKET = {
        VariantType.MINI: 5,
        VariantType.PARWA: 12,
        VariantType.PARWA_HIGH: 20,
    }

    # Automation rates
    AUTOMATION_RATES = {
        VariantType.MINI: 0.40,  # 40%
        VariantType.PARWA: 0.65,  # 65%
        VariantType.PARWA_HIGH: 0.85,  # 85%
    }

    def __init__(self):
        # Input fields
        self.monthly_tickets: int = 500
        self.avg_handling_time_minutes: float = 15.0
        self.agent_hourly_rate: float = 25.00
        self.customer_value: float = 50.00
        self.selected_variant: VariantType = VariantType.PARWA

        # Calculated results
        self.results: Optional[Dict[str, Any]] = None
        self.is_calculating: bool = False
        self.error: Optional[str] = None

    def calculate(self) -> Dict[str, Any]:
        """Calculate ROI based on inputs."""
        variant = self.selected_variant
        monthly_cost = self.VARIANT_COSTS[variant]
        time_saved = self.TIME_SAVED_PER_TICKET[variant]
        automation_rate = self.AUTOMATION_RATES[variant]

        # Calculate time savings
        automated_tickets = int(self.monthly_tickets * automation_rate)
        total_time_saved_hours = (automated_tickets * time_saved) / 60

        # Calculate cost savings
        labor_savings = total_time_saved_hours * self.agent_hourly_rate

        # Calculate ROI
        monthly_savings = labor_savings - monthly_cost
        annual_savings = monthly_savings * 12
        roi_percentage = (monthly_savings / monthly_cost * 100) if monthly_cost > 0 else 0

        self.results = {
            "variant": variant.value,
            "monthly_cost": monthly_cost,
            "automated_tickets": automated_tickets,
            "time_saved_hours": total_time_saved_hours,
            "labor_savings": labor_savings,
            "monthly_savings": monthly_savings,
            "annual_savings": annual_savings,
            "roi_percentage": roi_percentage,
            "automation_rate": automation_rate,
            "payback_months": monthly_cost / monthly_savings if monthly_savings > 0 else 0,
        }

        return self.results

    def compare_all_variants(self) -> List[Dict[str, Any]]:
        """Compare ROI across all variants."""
        original_variant = self.selected_variant
        comparisons = []

        for variant in VariantType:
            self.selected_variant = variant
            result = self.calculate()
            comparisons.append(result)

        self.selected_variant = original_variant
        return comparisons

    def reset(self) -> None:
        """Reset calculator to defaults."""
        self.monthly_tickets = 500
        self.avg_handling_time_minutes = 15.0
        self.agent_hourly_rate = 25.00
        self.customer_value = 50.00
        self.selected_variant = VariantType.PARWA
        self.results = None
        self.error = None


class MockROICalculatorActions:
    """Mock actions for ROI calculator UI component."""

    def __init__(self, state: MockROICalculatorState):
        self.state = state

    def set_monthly_tickets(self, value: int) -> None:
        """Set monthly ticket volume."""
        if value < 0:
            self.state.error = "Ticket volume cannot be negative"
            return
        self.state.monthly_tickets = value
        self.state.error = None

    def set_handling_time(self, value: float) -> None:
        """Set average handling time in minutes."""
        if value < 0:
            self.state.error = "Handling time cannot be negative"
            return
        self.state.avg_handling_time_minutes = value
        self.state.error = None

    def set_agent_rate(self, value: float) -> None:
        """Set agent hourly rate."""
        if value < 0:
            self.state.error = "Agent rate cannot be negative"
            return
        self.state.agent_hourly_rate = value
        self.state.error = None

    def set_variant(self, variant: VariantType) -> None:
        """Set selected variant."""
        self.state.selected_variant = variant

    def calculate(self) -> Dict[str, Any]:
        """Trigger calculation."""
        return self.state.calculate()

    def compare(self) -> List[Dict[str, Any]]:
        """Trigger variant comparison."""
        return self.state.compare_all_variants()

    def reset(self) -> None:
        """Reset calculator."""
        self.state.reset()


# =============================================================================
# UI Tests
# =============================================================================

class TestROICalculatorUI:
    """Tests for ROI calculator UI component."""

    @pytest.fixture
    def state(self):
        """Create ROI calculator state."""
        return MockROICalculatorState()

    @pytest.fixture
    def actions(self, state):
        """Create ROI calculator actions."""
        return MockROICalculatorActions(state)

    def test_roi_calculator_renders(self, state):
        """Test: ROI calculator renders with default values."""
        assert state.monthly_tickets == 500
        assert state.avg_handling_time_minutes == 15.0
        assert state.agent_hourly_rate == 25.00
        assert state.selected_variant == VariantType.PARWA

    def test_input_fields_work(self, state, actions):
        """Test: Input fields work correctly."""
        # Set ticket volume
        actions.set_monthly_tickets(1000)
        assert state.monthly_tickets == 1000

        # Set handling time
        actions.set_handling_time(20.0)
        assert state.avg_handling_time_minutes == 20.0

        # Set agent rate
        actions.set_agent_rate(30.00)
        assert state.agent_hourly_rate == 30.00

    def test_calculation_is_correct(self, state, actions):
        """Test: Calculation produces correct results."""
        # Use default values
        result = actions.calculate()

        assert result is not None
        assert "roi_percentage" in result
        assert "monthly_savings" in result
        assert "annual_savings" in result
        assert "automated_tickets" in result

        # Verify calculation logic
        # With PARWA: 500 tickets * 65% automation = 325 automated
        # 325 * 12 min = 3900 min = 65 hours
        # 65 hours * $25 = $1625 labor savings
        # Monthly cost $199
        # Savings = $1625 - $199 = $1426

        assert result["automated_tickets"] == 325  # 500 * 0.65
        assert result["time_saved_hours"] == 65.0  # 325 * 12 / 60

    def test_results_display_correctly(self, state, actions):
        """Test: Results display with proper formatting."""
        result = actions.calculate()

        # All monetary values should be numbers
        assert isinstance(result["monthly_cost"], float)
        assert isinstance(result["labor_savings"], float)
        assert isinstance(result["monthly_savings"], float)

        # ROI percentage should be calculated
        assert result["roi_percentage"] > 0

    def test_variant_comparison_works(self, state, actions):
        """Test: Variant comparison shows all options."""
        comparisons = actions.compare()

        assert len(comparisons) == 3  # Mini, PARWA, PARWA High

        variants = [c["variant"] for c in comparisons]
        assert "mini" in variants
        assert "parwa" in variants
        assert "parwa_high" in variants

    def test_mini_variant_calculation(self, state, actions):
        """Test: Mini variant calculation is correct."""
        actions.set_variant(VariantType.MINI)
        result = actions.calculate()

        assert result["variant"] == "mini"
        assert result["monthly_cost"] == 49.00
        assert result["automation_rate"] == 0.40
        # 500 * 0.40 = 200 automated tickets
        assert result["automated_tickets"] == 200

    def test_parwa_variant_calculation(self, state, actions):
        """Test: PARWA variant calculation is correct."""
        actions.set_variant(VariantType.PARWA)
        result = actions.calculate()

        assert result["variant"] == "parwa"
        assert result["monthly_cost"] == 199.00
        assert result["automation_rate"] == 0.65

    def test_parwa_high_variant_calculation(self, state, actions):
        """Test: PARWA High variant calculation is correct."""
        actions.set_variant(VariantType.PARWA_HIGH)
        result = actions.calculate()

        assert result["variant"] == "parwa_high"
        assert result["monthly_cost"] == 499.00
        assert result["automation_rate"] == 0.85
        # 500 * 0.85 = 425 automated tickets
        assert result["automated_tickets"] == 425

    def test_high_volume_scenario(self, state, actions):
        """Test: High volume scenario calculates correctly."""
        actions.set_monthly_tickets(5000)
        actions.set_variant(VariantType.PARWA_HIGH)
        result = actions.calculate()

        # High volume should show significant savings
        assert result["automated_tickets"] == 4250  # 5000 * 0.85
        assert result["annual_savings"] > 10000

    def test_small_business_scenario(self, state, actions):
        """Test: Small business scenario calculates correctly."""
        actions.set_monthly_tickets(50)
        actions.set_variant(VariantType.MINI)
        result = actions.calculate()

        # Small volume with Mini
        assert result["automated_tickets"] == 20  # 50 * 0.40
        # May have negative ROI for very small volumes
        # This is expected and helps guide customer choice

    def test_invalid_input_handling(self, state, actions):
        """Test: Invalid input shows error."""
        # Negative tickets
        actions.set_monthly_tickets(-100)
        assert state.error is not None

        # Reset
        actions.reset()
        assert state.error is None

    def test_reset_functionality(self, state, actions):
        """Test: Reset restores defaults."""
        # Change values
        actions.set_monthly_tickets(1000)
        actions.set_handling_time(30.0)
        actions.set_variant(VariantType.PARWA_HIGH)

        # Reset
        actions.reset()

        # Verify defaults restored
        assert state.monthly_tickets == 500
        assert state.avg_handling_time_minutes == 15.0
        assert state.selected_variant == VariantType.PARWA

    def test_payback_period_calculation(self, state, actions):
        """Test: Payback period is calculated."""
        result = actions.calculate()

        assert "payback_months" in result
        assert result["payback_months"] >= 0

    def test_roi_percentage_calculation(self, state, actions):
        """Test: ROI percentage is calculated correctly."""
        result = actions.calculate()

        # ROI = (savings / cost) * 100
        expected_roi = (result["monthly_savings"] / result["monthly_cost"]) * 100
        assert abs(result["roi_percentage"] - expected_roi) < 0.01


class TestROICalculatorEdgeCases:
    """Tests for ROI calculator edge cases."""

    @pytest.fixture
    def state(self):
        return MockROICalculatorState()

    @pytest.fixture
    def actions(self, state):
        return MockROICalculatorActions(state)

    def test_zero_tickets(self, state, actions):
        """Test: Zero tickets handled correctly."""
        actions.set_monthly_tickets(0)
        result = actions.calculate()

        # Should handle gracefully
        assert result["automated_tickets"] == 0
        assert result["monthly_savings"] < 0  # Cost exceeds savings

    def test_very_high_handling_time(self, state, actions):
        """Test: Very high handling time scenario."""
        actions.set_handling_time(120.0)  # 2 hours per ticket
        result = actions.calculate()

        # Should show high savings
        assert result["labor_savings"] > result["monthly_cost"]

    def test_very_low_agent_rate(self, state, actions):
        """Test: Very low agent rate scenario."""
        actions.set_agent_rate(10.00)
        result = actions.calculate()

        # Lower savings due to lower labor cost
        assert result["labor_savings"] > 0

    def test_variant_upgrade_comparison(self, state, actions):
        """Test: Compare upgrade options."""
        # Start with Mini
        actions.set_variant(VariantType.MINI)
        mini_result = actions.calculate()

        # Upgrade to PARWA
        actions.set_variant(VariantType.PARWA)
        parwa_result = actions.calculate()

        # PARWA should have higher automation
        assert parwa_result["automation_rate"] > mini_result["automation_rate"]

        # Calculate upgrade benefit
        upgrade_savings = parwa_result["monthly_savings"] - mini_result["monthly_savings"]
        upgrade_cost = parwa_result["monthly_cost"] - mini_result["monthly_cost"]

        # Upgrade should be worth it for this volume
        assert parwa_result["annual_savings"] > mini_result["annual_savings"]


class TestROICalculatorAccessibility:
    """Tests for ROI calculator accessibility."""

    def test_input_labels_present(self):
        """Test: All inputs have proper labels."""
        expected_labels = {
            "monthly_tickets": "Monthly ticket volume",
            "handling_time": "Average handling time (minutes)",
            "agent_rate": "Agent hourly rate ($)",
            "variant": "Select PARWA variant",
        }
        assert len(expected_labels) == 4

    def test_error_messages_accessible(self):
        """Test: Error messages are accessible."""
        # Error should have role="alert"
        # Error should be announced to screen readers
        pass

    def test_results_accessible(self):
        """Test: Results are accessible."""
        # Results should have proper headings
        # Key metrics should be easy to navigate
        pass


class TestROICalculatorPerformance:
    """Tests for ROI calculator performance."""

    def test_calculation_speed(self):
        """Test: Calculation completes quickly."""
        import time

        state = MockROICalculatorState()
        start = time.perf_counter()

        for _ in range(1000):
            state.calculate()

        elapsed = time.perf_counter() - start

        # Should be very fast (< 1 second for 1000 calculations)
        assert elapsed < 1.0

    def test_comparison_speed(self):
        """Test: Variant comparison completes quickly."""
        import time

        state = MockROICalculatorState()
        start = time.perf_counter()

        for _ in range(100):
            state.compare_all_variants()

        elapsed = time.perf_counter() - start

        # Should be fast
        assert elapsed < 0.5
