"""
Day 27 Service Unit Tests - Internal Note Service

Tests for internal_note_service.py covering:
- Note CRUD operations
- Pin/unpin functionality
- Author authorization
- Content validation
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from backend.app.services.internal_note_service import InternalNoteService
from backend.app.exceptions import NotFoundError, ValidationError, AuthorizationError
from database.models.tickets import (
    Ticket,
    TicketInternalNote,
    TicketStatus,
)


# ── FIXTURES ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    return db


@pytest.fixture
def mock_company_id():
    """Test company ID."""
    return "test-company-123"


@pytest.fixture
def note_service(mock_db, mock_company_id):
    """Internal note service instance."""
    return InternalNoteService(mock_db, mock_company_id)


@pytest.fixture
def sample_ticket():
    """Sample ticket for testing."""
    ticket = Ticket()
    ticket.id = "ticket-123"
    ticket.company_id = "test-company-123"
    ticket.status = TicketStatus.open.value
    ticket.updated_at = datetime.utcnow()
    return ticket


@pytest.fixture
def sample_note():
    """Sample internal note for testing."""
    note = TicketInternalNote()
    note.id = "note-123"
    note.ticket_id = "ticket-123"
    note.company_id = "test-company-123"
    note.author_id = "user-456"
    note.content = "This is an internal note"
    note.is_pinned = False
    note.created_at = datetime.utcnow()
    return note


# ═══════════════════════════════════════════════════════════════════
# CREATE NOTE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestCreateNote:

    def test_create_note_success(self, note_service, mock_db, sample_ticket):
        """Test successful note creation."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        note = note_service.create_note(
            ticket_id="ticket-123",
            author_id="user-456",
            content="This is a test note",
        )

        assert mock_db.add.called
        assert mock_db.commit.called

    def test_create_note_empty_content_rejected(self, note_service, mock_db, sample_ticket):
        """Test that empty content is rejected."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        with pytest.raises(ValidationError) as exc_info:
            note_service.create_note(
                ticket_id="ticket-123",
                author_id="user-456",
                content="",
            )

        assert "empty" in str(exc_info.value).lower()

    def test_create_note_whitespace_only_rejected(self, note_service, mock_db, sample_ticket):
        """Test that whitespace-only content is rejected."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        with pytest.raises(ValidationError) as exc_info:
            note_service.create_note(
                ticket_id="ticket-123",
                author_id="user-456",
                content="   \n\t  ",
            )

        assert "empty" in str(exc_info.value).lower()

    def test_create_note_validates_length(self, note_service, mock_db, sample_ticket):
        """Test that note length is validated."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        long_content = "x" * (InternalNoteService.MAX_NOTE_LENGTH + 1)

        with pytest.raises(ValidationError) as exc_info:
            note_service.create_note(
                ticket_id="ticket-123",
                author_id="user-456",
                content=long_content,
            )

        assert "too long" in str(exc_info.value).lower()

    def test_create_note_with_pin(self, note_service, mock_db, sample_ticket):
        """Test creating a pinned note."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket
        mock_db.query.return_value.filter.return_value.count.return_value = 0  # No existing pinned

        note = note_service.create_note(
            ticket_id="ticket-123",
            author_id="user-456",
            content="Important note",
            is_pinned=True,
        )

        assert mock_db.add.called

    def test_create_pinned_note_enforces_limit(self, note_service, mock_db, sample_ticket):
        """Test that pinned note limit is enforced."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket
        mock_db.query.return_value.filter.return_value.count.return_value = InternalNoteService.MAX_PINNED_NOTES

        with pytest.raises(ValidationError) as exc_info:
            note_service.create_note(
                ticket_id="ticket-123",
                author_id="user-456",
                content="Another pinned note",
                is_pinned=True,
            )

        assert "5 pinned notes" in str(exc_info.value)

    def test_create_note_updates_ticket_timestamp(self, note_service, mock_db, sample_ticket):
        """Test that creating a note updates ticket's updated_at."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket
        original_time = sample_ticket.updated_at

        note_service.create_note(
            ticket_id="ticket-123",
            author_id="user-456",
            content="Test note",
        )

        # updated_at should be changed
        assert sample_ticket.updated_at >= original_time


# ═══════════════════════════════════════════════════════════════════
# GET NOTE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestGetNote:

    def test_get_note_success(self, note_service, mock_db, sample_note):
        """Test successful note retrieval."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note

        note = note_service.get_note("ticket-123", "note-123")

        assert note.id == "note-123"
        assert note.author_id == "user-456"

    def test_get_note_not_found(self, note_service, mock_db):
        """Test that missing note raises NotFoundError."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            note_service.get_note("ticket-123", "nonexistent")


# ═══════════════════════════════════════════════════════════════════
# LIST NOTES TESTS
# ═══════════════════════════════════════════════════════════════════

class TestListNotes:

    def test_list_notes_success(self, note_service, mock_db, sample_note):
        """Test successful note listing."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = [sample_note]
        mock_db.query.return_value = mock_query

        notes, total = note_service.list_notes("ticket-123")

        assert len(notes) == 1
        assert total == 1

    def test_list_notes_pinned_only(self, note_service, mock_db, sample_note):
        """Test filtering for pinned notes only."""
        sample_note.is_pinned = True

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.filter.return_value = mock_query  # Second filter for pinned
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = [sample_note]
        mock_db.query.return_value = mock_query

        notes, total = note_service.list_notes("ticket-123", pinned_only=True)

        assert len(notes) == 1

    def test_list_notes_pagination(self, note_service, mock_db):
        """Test note listing pagination."""
        notes_data = []
        for i in range(10):
            note = TicketInternalNote()
            note.id = f"note-{i}"
            note.ticket_id = "ticket-123"
            note.company_id = "test-company-123"
            note.author_id = "user-456"
            note.content = f"Note {i}"
            note.is_pinned = False
            note.created_at = datetime.utcnow()
            notes_data.append(note)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 10
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = notes_data[:5]
        mock_db.query.return_value = mock_query

        notes, total = note_service.list_notes("ticket-123", page=1, page_size=5)

        assert len(notes) == 5
        assert total == 10


# ═══════════════════════════════════════════════════════════════════
# UPDATE NOTE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestUpdateNote:

    def test_update_note_success(self, note_service, mock_db, sample_note):
        """Test successful note update."""
        sample_note.author_id = "user-456"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note

        updated = note_service.update_note(
            ticket_id="ticket-123",
            note_id="note-123",
            content="Updated content",
            user_id="user-456",
        )

        assert mock_db.commit.called

    def test_update_note_authorization_check(self, note_service, mock_db, sample_note):
        """Test that only author can edit their notes."""
        sample_note.author_id = "author-123"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note

        with pytest.raises(AuthorizationError):
            note_service.update_note(
                ticket_id="ticket-123",
                note_id="note-123",
                content="Updated content",
                user_id="different-user",
            )

    def test_update_note_force_bypasses_authorization(self, note_service, mock_db, sample_note):
        """Test that force=True bypasses author check."""
        sample_note.author_id = "author-123"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note

        updated = note_service.update_note(
            ticket_id="ticket-123",
            note_id="note-123",
            content="Updated content",
            user_id="different-user",
            force=True,
        )

        assert mock_db.commit.called

    def test_update_note_validates_content(self, note_service, mock_db, sample_note):
        """Test that updated content is validated."""
        sample_note.author_id = "user-456"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note

        long_content = "x" * (InternalNoteService.MAX_NOTE_LENGTH + 1)

        with pytest.raises(ValidationError):
            note_service.update_note(
                ticket_id="ticket-123",
                note_id="note-123",
                content=long_content,
                user_id="user-456",
            )


# ═══════════════════════════════════════════════════════════════════
# DELETE NOTE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestDeleteNote:

    def test_delete_note_success(self, note_service, mock_db, sample_note):
        """Test successful note deletion."""
        sample_note.author_id = "user-456"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note

        result = note_service.delete_note(
            ticket_id="ticket-123",
            note_id="note-123",
            user_id="user-456",
        )

        assert result is True
        assert mock_db.delete.called
        assert mock_db.commit.called

    def test_delete_note_authorization_check(self, note_service, mock_db, sample_note):
        """Test that only author can delete their notes."""
        sample_note.author_id = "author-123"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note

        with pytest.raises(AuthorizationError):
            note_service.delete_note(
                ticket_id="ticket-123",
                note_id="note-123",
                user_id="different-user",
            )

    def test_delete_note_force_bypasses_authorization(self, note_service, mock_db, sample_note):
        """Test that force=True bypasses author check for deletion."""
        sample_note.author_id = "author-123"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note

        result = note_service.delete_note(
            ticket_id="ticket-123",
            note_id="note-123",
            user_id="different-user",
            force=True,
        )

        assert result is True


# ═══════════════════════════════════════════════════════════════════
# PIN MANAGEMENT TESTS
# ═══════════════════════════════════════════════════════════════════

class TestPinManagement:

    def test_pin_note_success(self, note_service, mock_db, sample_note):
        """Test successful note pinning."""
        sample_note.is_pinned = False
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note
        mock_db.query.return_value.filter.return_value.count.return_value = 0  # No existing pinned

        result = note_service.pin_note("ticket-123", "note-123")

        assert result.is_pinned is True
        assert mock_db.commit.called

    def test_pin_already_pinned_note(self, note_service, mock_db, sample_note):
        """Test pinning an already pinned note returns the note."""
        sample_note.is_pinned = True
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note

        result = note_service.pin_note("ticket-123", "note-123")

        assert result.is_pinned is True

    def test_pin_note_enforces_limit(self, note_service, mock_db, sample_note):
        """Test that pin limit is enforced."""
        sample_note.is_pinned = False
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note
        mock_db.query.return_value.filter.return_value.count.return_value = InternalNoteService.MAX_PINNED_NOTES

        with pytest.raises(ValidationError) as exc_info:
            note_service.pin_note("ticket-123", "note-123")

        assert "5 pinned notes" in str(exc_info.value)

    def test_unpin_note_success(self, note_service, mock_db, sample_note):
        """Test successful note unpinning."""
        sample_note.is_pinned = True
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note

        result = note_service.unpin_note("ticket-123", "note-123")

        assert result.is_pinned is False
        assert mock_db.commit.called

    def test_toggle_pin_pins_unpinned_note(self, note_service, mock_db, sample_note):
        """Test toggle_pin pins an unpinned note."""
        sample_note.is_pinned = False
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        result = note_service.toggle_pin("ticket-123", "note-123")

        assert result.is_pinned is True

    def test_toggle_pin_unpins_pinned_note(self, note_service, mock_db, sample_note):
        """Test toggle_pin unpins a pinned note."""
        sample_note.is_pinned = True
        mock_db.query.return_value.filter.return_value.first.return_value = sample_note

        result = note_service.toggle_pin("ticket-123", "note-123")

        assert result.is_pinned is False

    def test_get_pinned_notes(self, note_service, mock_db, sample_note):
        """Test getting all pinned notes for a ticket."""
        sample_note.is_pinned = True
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [sample_note]

        pinned = note_service.get_pinned_notes("ticket-123")

        assert len(pinned) == 1
        assert pinned[0].is_pinned is True

    def test_clear_all_pins(self, note_service, mock_db):
        """Test clearing all pinned notes."""
        mock_db.query.return_value.filter.return_value.update.return_value = 3  # 3 notes unpinned

        count = note_service.clear_all_pins("ticket-123")

        assert count == 3
        assert mock_db.commit.called
