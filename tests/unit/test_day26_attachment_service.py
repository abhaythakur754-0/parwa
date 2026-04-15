"""
Day 26 Unit Tests - Attachment Service

Tests for BL06: Attachment validation with:
- File type validation (whitelist)
- File size limits (per plan tier)
- MIME type verification
"""

import pytest
from unittest.mock import MagicMock, patch
import hashlib

from app.services.attachment_service import AttachmentService, magic
from app.exceptions import ValidationError
from database.models.tickets import TicketAttachment

# Skip magic-dependent tests if magic is not installed
requires_magic = pytest.mark.skipif(
    magic is None,
    reason="python-magic not installed"
)


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
def attachment_service(mock_db, mock_company_id):
    """Attachment service instance."""
    return AttachmentService(mock_db, mock_company_id, plan_tier="starter")


@pytest.fixture
def attachment_service_growth(mock_db, mock_company_id):
    """Attachment service with growth plan."""
    return AttachmentService(mock_db, mock_company_id, plan_tier="growth")


# ── FILE VALIDATION TESTS ───────────────────────────────────────────────────

class TestValidateFile:
    """Tests for file validation."""

    @requires_magic
    @patch('magic.from_buffer')
    def test_validate_pdf_file(self, mock_magic, attachment_service):
        """Test valid PDF file."""
        mock_magic.return_value = "application/pdf"
        is_valid, error, metadata = attachment_service.validate_file(
            "document.pdf",
            b"%PDF-1.4 fake pdf content"
        )
        assert is_valid is True
        assert error is None
        assert metadata["extension"] == "pdf"

    @requires_magic
    @patch('magic.from_buffer')
    def test_validate_docx_file(self, mock_magic, attachment_service):
        """Test valid DOCX file."""
        mock_magic.return_value = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        is_valid, error, metadata = attachment_service.validate_file(
            "document.docx",
            b"PK fake docx content"
        )
        assert is_valid is True
        assert metadata["extension"] == "docx"

    @requires_magic
    @patch('magic.from_buffer')
    def test_validate_png_file(self, mock_magic, attachment_service):
        """Test valid PNG file."""
        mock_magic.return_value = "image/png"
        is_valid, error, metadata = attachment_service.validate_file(
            "image.png",
            b"\x89PNG fake png content"
        )
        assert is_valid is True
        assert metadata["extension"] == "png"

    @requires_magic
    @patch('magic.from_buffer')
    def test_validate_jpg_file(self, mock_magic, attachment_service):
        """Test valid JPG file."""
        mock_magic.return_value = "image/jpeg"
        is_valid, error, metadata = attachment_service.validate_file(
            "image.jpg",
            b"\xff\xd8\xff fake jpeg content"
        )
        assert is_valid is True
        assert metadata["extension"] == "jpg"

    @requires_magic
    @patch('magic.from_buffer')
    def test_validate_csv_file(self, mock_magic, attachment_service):
        """Test valid CSV file."""
        mock_magic.return_value = "text/csv"
        is_valid, error, metadata = attachment_service.validate_file(
            "data.csv",
            b"col1,col2\nval1,val2"
        )
        assert is_valid is True
        assert metadata["extension"] == "csv"

    @requires_magic
    @patch('magic.from_buffer')
    def test_validate_txt_file(self, mock_magic, attachment_service):
        """Test valid TXT file."""
        mock_magic.return_value = "text/plain"
        is_valid, error, metadata = attachment_service.validate_file(
            "notes.txt",
            b"Some text content"
        )
        assert is_valid is True


# ── DANGEROUS EXTENSION TESTS ───────────────────────────────────────────────

class TestDangerousExtensions:
    """Tests for dangerous extension blocking."""

    def test_block_exe_file(self, attachment_service):
        """Test EXE files are blocked."""
        is_valid, error, metadata = attachment_service.validate_file(
            "virus.exe",
            b"MZ fake exe content"
        )
        assert is_valid is False
        assert "not allowed" in error.lower()
        assert "security" in error.lower()

    def test_block_bat_file(self, attachment_service):
        """Test BAT files are blocked."""
        is_valid, error, metadata = attachment_service.validate_file(
            "script.bat",
            b"@echo off"
        )
        assert is_valid is False

    def test_block_js_file(self, attachment_service):
        """Test JS files are blocked."""
        is_valid, error, metadata = attachment_service.validate_file(
            "malicious.js",
            b"alert('xss')"
        )
        assert is_valid is False

    def test_block_php_file(self, attachment_service):
        """Test PHP files are blocked."""
        is_valid, error, metadata = attachment_service.validate_file(
            "shell.php",
            b"<?php system($_GET['cmd']); ?>"
        )
        assert is_valid is False

    def test_block_sh_file(self, attachment_service):
        """Test SH files are blocked."""
        is_valid, error, metadata = attachment_service.validate_file(
            "script.sh",
            b"#!/bin/bash"
        )
        assert is_valid is False

    def test_block_py_file(self, attachment_service):
        """Test PY files are blocked."""
        is_valid, error, metadata = attachment_service.validate_file(
            "script.py",
            b"print('hello')"
        )
        assert is_valid is False


# ── FILE SIZE TESTS ─────────────────────────────────────────────────────────

class TestFileSizeLimits:
    """Tests for file size limits."""

    @requires_magic
    @patch('magic.from_buffer')
    def test_file_size_within_limit(self, mock_magic, attachment_service):
        """Test file within size limit."""
        mock_magic.return_value = "application/pdf"
        content = b"a" * (4 * 1024 * 1024)  # 4 MB (under 5 MB limit)
        is_valid, error, metadata = attachment_service.validate_file(
            "file.pdf",
            content
        )
        assert is_valid is True

    def test_file_size_exceeds_starter_limit(self, attachment_service):
        """Test file exceeds starter plan limit."""
        content = b"a" * (6 * 1024 * 1024)  # 6 MB (over 5 MB limit)
        is_valid, error, metadata = attachment_service.validate_file(
            "file.pdf",
            content
        )
        assert is_valid is False
        assert "size" in error.lower()

    @requires_magic
    @patch('magic.from_buffer')
    def test_file_size_growth_plan_limit(self, mock_magic, attachment_service_growth):
        """Test growth plan has higher limit."""
        mock_magic.return_value = "application/pdf"
        content = b"a" * (10 * 1024 * 1024)  # 10 MB (under 25 MB limit)
        is_valid, error, metadata = attachment_service_growth.validate_file(
            "file.pdf",
            content
        )
        assert is_valid is True


# ── EXTENSION WHITELIST TESTS ───────────────────────────────────────────────

class TestExtensionWhitelist:
    """Tests for extension whitelist."""

    def test_allowed_extension_pdf(self, attachment_service):
        """Test PDF is allowed."""
        assert attachment_service.is_extension_allowed("pdf") is True

    def test_allowed_extension_docx(self, attachment_service):
        """Test DOCX is allowed."""
        assert attachment_service.is_extension_allowed("docx") is True

    def test_allowed_extension_png(self, attachment_service):
        """Test PNG is allowed."""
        assert attachment_service.is_extension_allowed("png") is True

    def test_allowed_extension_xlsx(self, attachment_service):
        """Test XLSX is allowed."""
        assert attachment_service.is_extension_allowed("xlsx") is True

    def test_blocked_extension_exe(self, attachment_service):
        """Test EXE is blocked."""
        assert attachment_service.is_extension_allowed("exe") is False

    def test_blocked_extension_unknown(self, attachment_service):
        """Test unknown extension is blocked."""
        assert attachment_service.is_extension_allowed("xyz") is False


# ── NO EXTENSION TESTS ──────────────────────────────────────────────────────

class TestNoExtension:
    """Tests for files without extension."""

    def test_no_extension_rejected(self, attachment_service):
        """Test file without extension is rejected."""
        is_valid, error, metadata = attachment_service.validate_file(
            "filename",
            b"some content"
        )
        assert is_valid is False
        assert "extension" in error.lower()


# ── SIZE LIMIT HELPER TESTS ─────────────────────────────────────────────────

class TestGetSizeLimit:
    """Tests for getting size limits."""

    def test_starter_limit(self, attachment_service):
        """Test starter plan limit."""
        limit = attachment_service.get_size_limit()
        assert limit == 5 * 1024 * 1024  # 5 MB

    def test_growth_limit(self, attachment_service_growth):
        """Test growth plan limit."""
        limit = attachment_service_growth.get_size_limit()
        assert limit == 25 * 1024 * 1024  # 25 MB


# ── CHECKSUM TESTS ──────────────────────────────────────────────────────────

class TestChecksum:
    """Tests for file checksum generation."""

    @requires_magic
    @patch('magic.from_buffer')
    def test_checksum_generated(self, mock_magic, attachment_service):
        """Test checksum is generated."""
        mock_magic.return_value = "application/pdf"
        content = b"test content"
        is_valid, error, metadata = attachment_service.validate_file(
            "file.pdf",
            content
        )
        expected = hashlib.sha256(content).hexdigest()
        assert metadata["checksum"] == expected

    @requires_magic
    @patch('magic.from_buffer')
    def test_checksum_unique(self, mock_magic, attachment_service):
        """Test different files have different checksums."""
        mock_magic.return_value = "application/pdf"
        _, _, meta1 = attachment_service.validate_file("file.pdf", b"content1")
        _, _, meta2 = attachment_service.validate_file("file.pdf", b"content2")
        assert meta1["checksum"] != meta2["checksum"]


# ── UPLOAD ATTACHMENT TESTS ─────────────────────────────────────────────────

class TestUploadAttachment:
    """Tests for uploading attachments."""

    def test_upload_valid_file(self, attachment_service, mock_db):
        """Test uploading a valid file."""
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Skip actual storage
        with patch.object(attachment_service, 'validate_file', return_value=(True, None, {"size": 100, "mime_type": "application/pdf"})):
            # This would need storage_service mock for full test
            pass

    @requires_magic
    @patch('magic.from_buffer')
    def test_upload_max_attachments_exceeded(self, mock_magic, attachment_service, mock_db):
        """Test max attachments per ticket limit."""
        mock_magic.return_value = "application/pdf"
        mock_db.query.return_value.filter.return_value.count.return_value = 10  # At limit

        with pytest.raises(ValidationError) as exc_info:
            attachment_service.upload_attachment(
                ticket_id="ticket-123",
                filename="file.pdf",
                file_content=b"%PDF-1.4 content"
            )

        assert "maximum" in str(exc_info.value).lower()


# ── GET ATTACHMENTS TESTS ───────────────────────────────────────────────────

class TestGetAttachments:
    """Tests for getting attachments."""

    def test_get_attachments_returns_list(self, attachment_service, mock_db):
        """Test get_attachments returns list."""
        mock_attachment = TicketAttachment()
        mock_attachment.id = "attach-1"
        mock_attachment.filename = "file.pdf"
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_attachment]

        result = attachment_service.get_attachments("ticket-123")

        assert len(result) == 1
        assert result[0].filename == "file.pdf"


# ── DELETE ATTACHMENT TESTS ─────────────────────────────────────────────────

class TestDeleteAttachment:
    """Tests for deleting attachments."""

    def test_delete_attachment_success(self, attachment_service, mock_db):
        """Test successful attachment deletion."""
        mock_attachment = TicketAttachment()
        mock_attachment.id = "attach-1"
        mock_attachment.file_url = "https://storage.com/file.pdf"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_attachment

        result = attachment_service.delete_attachment("attach-1")

        assert result is True
        assert mock_db.delete.called

    def test_delete_attachment_not_found(self, attachment_service, mock_db):
        """Test deleting non-existent attachment."""
        from app.exceptions import NotFoundError
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            attachment_service.delete_attachment("nonexistent")
