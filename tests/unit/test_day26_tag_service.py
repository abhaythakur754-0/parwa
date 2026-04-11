"""
Day 26 Unit Tests - Tag Service

Tests for MF03: Tag management with:
- Auto-tagging from content
- Tag CRUD operations
- Tag cleaning and validation
- Tag statistics
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from app.services.tag_service import TagService
from database.models.tickets import Ticket


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
def tag_service(mock_db, mock_company_id):
    """Tag service instance."""
    return TagService(mock_db, mock_company_id)


@pytest.fixture
def sample_ticket():
    """Sample ticket for testing."""
    ticket = Ticket()
    ticket.id = "ticket-123"
    ticket.company_id = "test-company-123"
    ticket.tags = "[]"
    return ticket


# ── AUTO TAG TESTS ──────────────────────────────────────────────────────────

class TestAutoTag:
    """Tests for automatic tag generation."""

    def test_auto_tag_api_keywords(self, tag_service):
        """Test auto-tagging with API keywords."""
        tags = tag_service.auto_tag("Having issues with the API endpoint")
        assert "api" in tags

    def test_auto_tag_mobile_keywords(self, tag_service):
        """Test auto-tagging with mobile keywords."""
        tags = tag_service.auto_tag("The mobile app crashes on iOS")
        assert "mobile" in tags

    def test_auto_tag_bug_keywords(self, tag_service):
        """Test auto-tagging with bug keywords."""
        tags = tag_service.auto_tag("Found a bug in the dashboard")
        assert "bug" in tags
        assert "dashboard" in tags

    def test_auto_tag_urgent_keywords(self, tag_service):
        """Test auto-tagging with urgent keywords."""
        tags = tag_service.auto_tag("This is urgent, need help ASAP")
        assert "urgent" in tags

    def test_auto_tag_performance_keywords(self, tag_service):
        """Test auto-tagging with performance keywords."""
        tags = tag_service.auto_tag("The system is very slow and timing out")
        assert "performance" in tags

    def test_auto_tag_security_keywords(self, tag_service):
        """Test auto-tagging with security keywords."""
        tags = tag_service.auto_tag("Potential security vulnerability found")
        assert "security" in tags

    def test_auto_tag_enterprise_keywords(self, tag_service):
        """Test auto-tagging with enterprise keywords."""
        tags = tag_service.auto_tag("For enterprise contract customers only")
        assert "enterprise" in tags

    def test_auto_tag_multiple_matches(self, tag_service):
        """Test auto-tagging with multiple keyword matches."""
        tags = tag_service.auto_tag(
            "Urgent: API integration bug causing slow performance"
        )
        assert "urgent" in tags
        assert "api" in tags
        assert "bug" in tags
        assert "performance" in tags

    def test_auto_tag_no_matches(self, tag_service):
        """Test auto-tagging with no matches."""
        tags = tag_service.auto_tag("Hello, how are you?")
        assert len(tags) == 0

    def test_auto_tag_empty_text(self, tag_service):
        """Test auto-tagging with empty text."""
        tags = tag_service.auto_tag("")
        assert len(tags) == 0

    def test_auto_tag_none_text(self, tag_service):
        """Test auto-tagging with None text."""
        tags = tag_service.auto_tag(None)
        assert len(tags) == 0


# ── TAG CLEANING TESTS ──────────────────────────────────────────────────────

class TestCleanTags:
    """Tests for tag cleaning and validation."""

    def test_clean_tags_lowercase(self, tag_service):
        """Test tags are lowercased."""
        tags = tag_service._clean_tags(["URGENT", "Billing"])
        assert tags == ["urgent", "billing"]

    def test_clean_tags_spaces_to_dashes(self, tag_service):
        """Test spaces converted to dashes."""
        tags = tag_service._clean_tags(["High Priority", "Tech Support"])
        assert tags == ["high-priority", "tech-support"]

    def test_clean_tags_remove_invalid_chars(self, tag_service):
        """Test invalid characters removed."""
        tags = tag_service._clean_tags(["tag@123", "test!tag"])
        assert tags == ["tag123", "testtag"]

    def test_clean_tags_max_length(self, tag_service):
        """Test tags exceeding max length are rejected."""
        long_tag = "a" * 100
        tags = tag_service._clean_tags([long_tag])
        # Tags exceeding MAX_TAG_LENGTH should be rejected (not truncated)
        assert len(tags) == 0

    def test_clean_tags_empty_removed(self, tag_service):
        """Test empty tags are removed."""
        tags = tag_service._clean_tags(["valid", "", "also-valid"])
        assert tags == ["valid", "also-valid"]

    def test_clean_tags_duplicates_removed(self, tag_service):
        """Test duplicate tags are removed."""
        tags = tag_service._clean_tags(["urgent", "URGENT", "Urgent"])
        assert tags == ["urgent"]

    def test_clean_tags_preserves_order(self, tag_service):
        """Test tag order is preserved."""
        tags = tag_service._clean_tags(["third", "first", "second"])
        assert tags == ["third", "first", "second"]


# ── ADD TAGS TESTS ───────────────────────────────────────────────────────────

class TestAddTags:
    """Tests for adding tags to tickets."""

    def test_add_tags_success(self, tag_service, mock_db, sample_ticket):
        """Test successfully adding tags."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        current_tags, added = tag_service.add_tags("ticket-123", ["urgent", "api"])

        assert "urgent" in current_tags
        assert "api" in current_tags
        assert set(added) == {"urgent", "api"}

    def test_add_tags_no_duplicates(self, tag_service, mock_db, sample_ticket):
        """Test adding duplicate tags doesn't create duplicates."""
        sample_ticket.tags = json.dumps(["urgent"])
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        current_tags, added = tag_service.add_tags("ticket-123", ["urgent", "new"])

        assert current_tags.count("urgent") == 1
        assert "new" in added
        assert "urgent" not in added

    def test_add_tags_max_limit(self, tag_service, mock_db, sample_ticket):
        """Test max tags per ticket limit."""
        # Start with max tags
        sample_ticket.tags = json.dumps([f"tag{i}" for i in range(20)])
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        current_tags, added = tag_service.add_tags("ticket-123", ["new-tag"])

        # Should not add beyond limit
        assert len(json.loads(sample_ticket.tags)) == 20

    def test_add_tags_ticket_not_found(self, tag_service, mock_db):
        """Test adding tags to non-existent ticket."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        current_tags, added = tag_service.add_tags("nonexistent", ["tag"])

        assert current_tags == []
        assert added == []


# ── REMOVE TAGS TESTS ───────────────────────────────────────────────────────

class TestRemoveTags:
    """Tests for removing tags from tickets."""

    def test_remove_tag_success(self, tag_service, mock_db, sample_ticket):
        """Test successfully removing a tag."""
        sample_ticket.tags = json.dumps(["urgent", "api", "billing"])
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        current_tags, removed = tag_service.remove_tags("ticket-123", ["api"])

        assert "api" not in current_tags
        assert "urgent" in current_tags
        assert "billing" in current_tags
        assert removed == ["api"]

    def test_remove_nonexistent_tag(self, tag_service, mock_db, sample_ticket):
        """Test removing tag that doesn't exist."""
        sample_ticket.tags = json.dumps(["urgent"])
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        current_tags, removed = tag_service.remove_tags("ticket-123", ["nonexistent"])

        assert current_tags == ["urgent"]
        assert removed == []

    def test_remove_multiple_tags(self, tag_service, mock_db, sample_ticket):
        """Test removing multiple tags."""
        sample_ticket.tags = json.dumps(["urgent", "api", "billing"])
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        current_tags, removed = tag_service.remove_tags(
            "ticket-123", ["urgent", "billing"]
        )

        assert current_tags == ["api"]
        assert set(removed) == {"urgent", "billing"}


# ── SET TAGS TESTS ───────────────────────────────────────────────────────────

class TestSetTags:
    """Tests for setting (replacing) all tags."""

    def test_set_tags_replaces_all(self, tag_service, mock_db, sample_ticket):
        """Test set_tags replaces all existing tags."""
        sample_ticket.tags = json.dumps(["old1", "old2"])
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = tag_service.set_tags("ticket-123", ["new1", "new2"])

        assert result == ["new1", "new2"]
        assert json.loads(sample_ticket.tags) == ["new1", "new2"]

    def test_set_tags_enforces_limit(self, tag_service, mock_db, sample_ticket):
        """Test set_tags enforces max limit."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        # Try to set more than max
        many_tags = [f"tag{i}" for i in range(30)]
        result = tag_service.set_tags("ticket-123", many_tags)

        assert len(result) == 20  # MAX_TAGS_PER_TICKET

    def test_set_tags_cleans_input(self, tag_service, mock_db, sample_ticket):
        """Test set_tags cleans input tags."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = tag_service.set_tags("ticket-123", ["UPPER CASE", "with spaces"])

        assert result == ["upper-case", "with-spaces"]


# ── POPULAR TAGS TESTS ──────────────────────────────────────────────────────

class TestGetPopularTags:
    """Tests for getting popular tags."""

    def test_get_popular_tags_counts_correctly(self, tag_service, mock_db):
        """Test popular tags are counted correctly."""
        mock_db.query.return_value.filter.return_value.all.return_value = [
            ('["urgent", "api"]',),
            ('["urgent", "billing"]',),
            ('["urgent"]',),
        ]

        popular = tag_service.get_popular_tags(limit=10)

        assert ("urgent", 3) in popular
        assert ("api", 1) in popular
        assert ("billing", 1) in popular

    def test_get_popular_tags_limit(self, tag_service, mock_db):
        """Test popular tags limit is respected."""
        mock_db.query.return_value.filter.return_value.all.return_value = [
            (f'["tag{i}"]',) for i in range(100)
        ]

        popular = tag_service.get_popular_tags(limit=10)

        assert len(popular) == 10

    def test_get_popular_tags_by_category(self, tag_service, mock_db):
        """Test popular tags filtered by category."""
        mock_db.query.return_value.filter.return_value.all.return_value = [
            ('["urgent", "api", "bug"]',),
            ('["urgent", "billing"]',),
        ]

        popular = tag_service.get_popular_tags(limit=10, category="status")

        # "urgent" is in status category
        assert any(tag == "urgent" for tag, count in popular)


# ── SUGGEST TAGS TESTS ──────────────────────────────────────────────────────

class TestSuggestTags:
    """Tests for tag suggestions."""

    def test_suggest_tags_excludes_existing(self, tag_service):
        """Test suggested tags exclude existing tags."""
        suggestions = tag_service.suggest_tags(
            "Urgent API bug",
            existing_tags=["urgent"]
        )
        assert "urgent" not in suggestions
        assert "api" in suggestions

    def test_suggest_tags_from_content(self, tag_service):
        """Test suggested tags come from content."""
        suggestions = tag_service.suggest_tags("Mobile app performance issue")
        assert "mobile" in suggestions
        assert "performance" in suggestions


# ── TAG CATEGORY TESTS ───────────────────────────────────────────────────────

class TestGetTagCategory:
    """Tests for tag category lookup."""

    def test_get_tag_category_product(self, tag_service):
        """Test product tags category."""
        category = tag_service.get_tag_category("api")
        assert category == "product"

    def test_get_tag_category_issue(self, tag_service):
        """Test issue tags category."""
        category = tag_service.get_tag_category("bug")
        assert category == "issue"

    def test_get_tag_category_customer(self, tag_service):
        """Test customer tags category."""
        category = tag_service.get_tag_category("enterprise")
        assert category == "customer"

    def test_get_tag_category_status(self, tag_service):
        """Test status tags category."""
        category = tag_service.get_tag_category("urgent")
        assert category == "status"

    def test_get_tag_category_unknown(self, tag_service):
        """Test unknown tag returns None."""
        category = tag_service.get_tag_category("randomtag")
        assert category is None
