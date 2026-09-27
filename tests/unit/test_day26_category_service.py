"""
Day 26 Unit Tests - Category Service

Tests for MF02: Category routing with:
- Category detection from keywords
- Category-to-department mapping
- Category rules
"""

import pytest
from unittest.mock import MagicMock

from app.services.category_service import CategoryService
from database.models.tickets import TicketCategory


# ── FIXTURES ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def mock_company_id():
    """Test company ID."""
    return "test-company-123"


@pytest.fixture
def category_service(mock_db, mock_company_id):
    """Category service instance."""
    return CategoryService(mock_db, mock_company_id)


# ── CATEGORY DETECTION TESTS ────────────────────────────────────────────────

class TestDetectCategory:
    """Tests for category detection from text."""

    def test_detect_tech_support_keywords(self, category_service):
        """Test detection of tech support keywords."""
        category, confidence = category_service.detect_category(
            "I'm getting an error when trying to login"
        )
        assert category == TicketCategory.tech_support.value
        assert confidence > 0.5

    def test_detect_tech_support_api(self, category_service):
        """Test detection of API-related tech support."""
        category, confidence = category_service.detect_category(
            "The API integration is not working properly"
        )
        assert category == TicketCategory.tech_support.value

    def test_detect_billing_keywords(self, category_service):
        """Test detection of billing keywords."""
        category, confidence = category_service.detect_category(
            "I need a refund for my last invoice"
        )
        assert category == TicketCategory.billing.value

    def test_detect_billing_subscription(self, category_service):
        """Test detection of subscription billing."""
        category, confidence = category_service.detect_category(
            "How do I cancel my subscription?"
        )
        assert category == TicketCategory.billing.value

    def test_detect_feature_request_keywords(self, category_service):
        """Test detection of feature request keywords."""
        category, confidence = category_service.detect_category(
            "Would be great if you could add dark mode"
        )
        assert category == TicketCategory.feature_request.value

    def test_detect_bug_report_keywords(self, category_service):
        """Test detection of bug report keywords."""
        category, confidence = category_service.detect_category(
            "There is a defect in the code with unexpected incorrect results"
        )
        # Bug report or tech_support are both valid matches for bug-related text
        assert category in [TicketCategory.bug_report.value, TicketCategory.tech_support.value]

    def test_detect_complaint_keywords(self, category_service):
        """Test detection of complaint keywords."""
        category, confidence = category_service.detect_category(
            "I am very unhappy with your terrible service"
        )
        assert category == TicketCategory.complaint.value

    def test_detect_general_keywords(self, category_service):
        """Test detection of general inquiry keywords."""
        category, confidence = category_service.detect_category(
            "How do I change my settings?"
        )
        assert category == TicketCategory.general.value

    def test_detect_category_empty_text(self, category_service):
        """Test detection with empty text."""
        category, confidence = category_service.detect_category("")
        assert category == TicketCategory.general.value
        assert confidence == 0.3

    def test_detect_category_none_text(self, category_service):
        """Test detection with None text."""
        category, confidence = category_service.detect_category(None)
        assert category == TicketCategory.general.value


# ── ADVANCED DETECTION TESTS ────────────────────────────────────────────────

class TestDetectCategoryAdvanced:
    """Tests for advanced category detection."""

    def test_detect_with_subject_and_message(self, category_service):
        """Test detection combining subject and message."""
        category, confidence, scores = category_service.detect_category_advanced(
            subject="Billing question",
            message="I need to update my payment method"
        )
        assert category == TicketCategory.billing.value
        assert "billing" in scores

    def test_detect_with_metadata_channel(self, category_service):
        """Test detection boosted by channel metadata."""
        category1, _, scores1 = category_service.detect_category_advanced(
            subject="Question", message="", metadata={"channel": "email"}
        )
        # Email boosts billing category
        assert scores1["billing"] > 0.1

    def test_detect_with_metadata_customer_tier(self, category_service):
        """Test detection boosted by enterprise tier."""
        category, confidence, scores = category_service.detect_category_advanced(
            subject="Feature suggestion",
            message="",
            metadata={"customer_tier": "enterprise"}
        )
        # Enterprise boosts feature request
        assert scores["feature_request"] > 0.1

    def test_detect_returns_all_scores(self, category_service):
        """Test that all category scores are returned."""
        category, confidence, scores = category_service.detect_category_advanced(
            subject="Test", message="Test"
        )
        assert len(scores) == 6  # All categories


# ── DEPARTMENT MAPPING TESTS ────────────────────────────────────────────────

class TestGetDepartment:
    """Tests for category to department mapping."""

    def test_department_tech_support(self, category_service):
        """Test tech support maps to technical_support."""
        dept = category_service.get_department(TicketCategory.tech_support.value)
        assert dept == "technical_support"

    def test_department_billing(self, category_service):
        """Test billing maps to billing."""
        dept = category_service.get_department(TicketCategory.billing.value)
        assert dept == "billing"

    def test_department_feature_request(self, category_service):
        """Test feature request maps to product."""
        dept = category_service.get_department(TicketCategory.feature_request.value)
        assert dept == "product"

    def test_department_bug_report(self, category_service):
        """Test bug report maps to engineering."""
        dept = category_service.get_department(TicketCategory.bug_report.value)
        assert dept == "engineering"

    def test_department_complaint(self, category_service):
        """Test complaint maps to customer_success."""
        dept = category_service.get_department(TicketCategory.complaint.value)
        assert dept == "customer_success"

    def test_department_general(self, category_service):
        """Test general maps to general."""
        dept = category_service.get_department(TicketCategory.general.value)
        assert dept == "general"


# ── CATEGORY RULES TESTS ────────────────────────────────────────────────────

class TestGetCategoryRules:
    """Tests for category routing rules."""

    def test_rules_tech_support(self, category_service):
        """Test tech support routing rules."""
        rules = category_service.get_category_rules(TicketCategory.tech_support.value)
        assert rules["auto_assign_ai"] is True
        assert "issue_type" in rules["required_fields"]

    def test_rules_billing(self, category_service):
        """Test billing routing rules."""
        rules = category_service.get_category_rules(TicketCategory.billing.value)
        assert rules["auto_assign_ai"] is False  # Billing needs human
        assert rules["priority_boost"] == 10

    def test_rules_feature_request(self, category_service):
        """Test feature request routing rules."""
        rules = category_service.get_category_rules(TicketCategory.feature_request.value)
        assert rules["auto_assign_ai"] is False
        assert rules["priority_boost"] == -10  # Lower priority

    def test_rules_bug_report(self, category_service):
        """Test bug report routing rules."""
        rules = category_service.get_category_rules(TicketCategory.bug_report.value)
        assert rules["auto_assign_ai"] is True
        assert "steps_to_reproduce" in rules["required_fields"]

    def test_rules_complaint(self, category_service):
        """Test complaint routing rules."""
        rules = category_service.get_category_rules(TicketCategory.complaint.value)
        assert rules["auto_assign_ai"] is False
        assert rules["auto_escalate"] is True
        assert rules["priority_boost"] == 20

    def test_rules_general(self, category_service):
        """Test general routing rules."""
        rules = category_service.get_category_rules(TicketCategory.general.value)
        assert rules["auto_assign_ai"] is True
        assert rules["priority_boost"] == 0


# ── VALIDATION TESTS ────────────────────────────────────────────────────────

class TestValidateCategoryRequirements:
    """Tests for category requirements validation."""

    def test_validate_missing_required_fields(self, category_service):
        """Test validation detects missing required fields."""
        is_valid, missing = category_service.validate_category_requirements(
            TicketCategory.bug_report.value,
            {}  # Missing steps_to_reproduce
        )
        assert is_valid is False
        assert "steps_to_reproduce" in missing

    def test_validate_all_fields_present(self, category_service):
        """Test validation passes with all required fields."""
        is_valid, missing = category_service.validate_category_requirements(
            TicketCategory.bug_report.value,
            {
                "steps_to_reproduce": "Click button",
                "expected_behavior": "Should work"
            }
        )
        assert is_valid is True
        assert len(missing) == 0

    def test_validate_no_required_fields(self, category_service):
        """Test validation for category with no required fields."""
        is_valid, missing = category_service.validate_category_requirements(
            TicketCategory.general.value,
            {}
        )
        assert is_valid is True
