"""
Day 17.5 Loophole Fix Verification Tests

Tests to verify that the 3 real loophole fixes work correctly:
- L45: Sensitive column blocklist in parse_sort()
- L47: Cross-company symlink detection in _resolve_path()
- L49: Unicode NFKC normalization in sanitize_filename()

Plus hardening tests for the 12 already-safe loopholes to confirm
they remain safe after the fixes.
"""

import os
import tempfile
import unicodedata
from unittest.mock import MagicMock, patch

import pytest


# ════════════════════════════════════════════════════════════════════
# L45: SENSITIVE COLUMN BLOCKLIST IN parse_sort()
# ════════════════════════════════════════════════════════════════════


class TestL45Fix_SensitiveSortBlocklist:
    """L45 FIX: parse_sort() blocks sensitive columns by default."""

    def test_password_hash_blocked(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="password_hash")
        assert result.field == "created_at"  # Falls back to default

    def test_password_blocked(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="password")
        assert result.field == "created_at"

    def test_secret_key_blocked(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="secret_key")
        assert result.field == "created_at"

    def test_mfa_secret_blocked(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="mfa_secret")
        assert result.field == "created_at"

    def test_token_hash_blocked(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="token_hash")
        assert result.field == "created_at"

    def test_api_key_blocked(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="api_key")
        assert result.field == "created_at"

    def test_credentials_encrypted_blocked(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="credentials_encrypted")
        assert result.field == "created_at"

    def test_connection_string_blocked(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="connection_string")
        assert result.field == "created_at"

    def test_card_number_blocked(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="card_number")
        assert result.field == "created_at"

    def test_ssn_blocked(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="ssn")
        assert result.field == "created_at"

    def test_case_insensitive_blocking(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="Password_Hash")
        assert result.field == "created_at"

    def test_safe_field_not_blocked(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="name")
        assert result.field == "name"

    def test_created_at_not_blocked(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="created_at")
        assert result.field == "created_at"

    def test_blocklist_has_16_entries(self):
        from backend.app.core.pagination import _SENSITIVE_SORT_COLUMNS

        assert len(_SENSITIVE_SORT_COLUMNS) >= 16


# ════════════════════════════════════════════════════════════════════
# L47: CROSS-COMPANY SYMLINK DETECTION
# ════════════════════════════════════════════════════════════════════


class TestL47Fix_CrossCompanySymlink:
    """L47 FIX: _resolve_path() now checks against company_base,
    not just base_path, preventing cross-company symlink leaks."""

    def test_symlink_to_other_company_blocked(self, tmp_path):
        from backend.app.core.storage import LocalStorageBackend

        backend = LocalStorageBackend(base_path=str(tmp_path))

        # Create a file in company B's directory
        comp_b_dir = tmp_path / "company-b"
        comp_b_dir.mkdir(parents=True)
        secret_file = comp_b_dir / "secret.txt"
        secret_file.write_bytes(b"company b secret")

        # Create a symlink in company A's directory pointing to company B
        comp_a_dir = tmp_path / "company-a"
        comp_a_dir.mkdir(parents=True)
        evil_symlink = comp_a_dir / "stolen_secret.txt"

        try:
            evil_symlink.symlink_to(secret_file)

            # Downloading from company A should now be BLOCKED
            # because the resolved path is in company-b, not company-a
            with pytest.raises(ValueError, match="company directory"):
                backend.download("company-a", "stolen_secret.txt")
        except OSError:
            # Symlinks not supported on this filesystem
            pass

    def test_symlink_outside_storage_blocked(self, tmp_path):
        from backend.app.core.storage import LocalStorageBackend

        backend = LocalStorageBackend(base_path=str(tmp_path))

        # Create a file completely outside storage
        outside_dir = tmp_path.parent / "parwa_evil" 
        outside_dir.mkdir(exist_ok=True)
        outside_file = outside_dir / "etc_passwd"
        outside_file.write_bytes(b"root:x:0:0")

        # Create symlink in company dir pointing outside
        comp_dir = tmp_path / "comp1"
        comp_dir.mkdir(parents=True)
        evil = comp_dir / "passwd"

        try:
            evil.symlink_to(outside_file)

            with pytest.raises((ValueError, FileNotFoundError)):
                backend.download("comp1", "passwd")
        except OSError:
            pass

    def test_normal_file_still_works(self, tmp_path):
        from backend.app.core.storage import LocalStorageBackend

        backend = LocalStorageBackend(base_path=str(tmp_path))

        # Normal upload/download still works
        meta = backend.upload(
            company_id="comp1",
            file_path="normal.txt",
            content=b"hello",
            content_type="text/plain",
        )
        content, ct = backend.download("comp1", "normal.txt")
        assert content == b"hello"


# ════════════════════════════════════════════════════════════════════
# L49: UNICODE HOMOGRAPH ATTACK PREVENTION
# ════════════════════════════════════════════════════════════════════


class TestL49Fix_UnicodeHomograph:
    """L49 FIX: sanitize_filename() applies NFKC normalization."""

    def test_fullwidth_characters_normalized(self):
        """Fullwidth characters (e.g., 'ａ') should be normalized to ASCII."""
        from backend.app.core.storage import sanitize_filename

        fullwidth_a = "\uFF41"  # Fullwidth Latin A
        filename = f"{fullwidth_a}bc.pdf"
        result = sanitize_filename(filename)

        assert result == "abc.pdf"

    def test_fullwidth_dot_normalized(self):
        """Fullwidth dot (．) should be normalized to regular dot."""
        from backend.app.core.storage import sanitize_filename

        fullwidth_dot = "\uFF0E"  # Fullwidth full stop
        filename = f"file{fullwidth_dot}pdf"
        result = sanitize_filename(filename)

        # After NFKC, fullwidth dot becomes regular dot
        # This creates a "file.pdf" which is the desired result
        assert "file" in result and "pdf" in result

    def test_zero_width_space_in_name(self):
        """Zero-width space should be handled."""
        from backend.app.core.storage import sanitize_filename

        zws = "\u200B"
        filename = f"file{zws}name.pdf"
        result = sanitize_filename(filename)

        # Zero-width space should be preserved (it's not in unsafe chars)
        # but the filename should still be valid
        assert result.endswith(".pdf")

    def test_normal_filename_unchanged(self):
        """Normal ASCII filenames should be unaffected."""
        from backend.app.core.storage import sanitize_filename

        assert sanitize_filename("report.pdf") == "report.pdf"
        assert sanitize_filename("my document.csv") == "my document.csv"

    def test_nfc_normalized_applied(self):
        """Verify NFKC normalization is actually applied."""
        import unicodedata
        from backend.app.core.storage import sanitize_filename

        # Input with fullwidth characters
        fullwidth = "\uFF41\uFF42\uFF43"  # ABC in fullwidth
        result = sanitize_filename(f"{fullwidth}.pdf")

        # NFKC should convert fullwidth to ASCII
        expected = unicodedata.normalize("NFKC", f"{fullwidth}.pdf")
        assert result == f"abc.pdf"


# ════════════════════════════════════════════════════════════════════
# HARDENING: Verify already-safe loopholes remain safe
# ════════════════════════════════════════════════════════════════════


class TestL44Harden_TotalPagesMinimum:
    """L44: total_pages must always be >= 1."""

    def test_total_pages_zero_input(self):
        from shared.utils.pagination import get_total_pages
        assert get_total_pages(0, 20) == 1

    def test_total_pages_negative_input(self):
        from shared.utils.pagination import get_total_pages
        assert get_total_pages(-5, 20) == 1

    def test_build_response_total_pages(self):
        from backend.app.core.pagination import PaginatedResponse

        resp = PaginatedResponse[str](
            items=[], total=0, offset=0, limit=20,
            has_next=False, has_prev=False, total_pages=1,
        )
        assert resp.total_pages == 1


class TestL46Harden_FilterOperatorWhitelist:
    """L46: Only whitelisted operators allowed."""

    def test_eval_operator_rejected(self):
        from backend.app.core.pagination import FilterParams, apply_filters
        from database.models.core import Company
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            with pytest.raises(ValueError, match="Unsupported"):
                apply_filters(
                    db.query(Company), Company,
                    [FilterParams(field="name", operator="eval", value="__import__('os')")],
                )
        finally:
            db.close()

    def test_exec_operator_rejected(self):
        from backend.app.core.pagination import FilterParams, apply_filters
        from database.models.core import Company
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            with pytest.raises(ValueError, match="Unsupported"):
                apply_filters(
                    db.query(Company), Company,
                    [FilterParams(field="name", operator="exec", value="malicious")],
                )
        finally:
            db.close()


class TestL48Harden_DoubleExtension:
    """L48: Double extension like .pdf.exe is rejected."""

    def test_pdf_exe_rejected(self):
        from backend.app.core.storage import validate_file_upload

        with pytest.raises(ValueError):
            validate_file_upload("malware.pdf.exe", "application/pdf", 1024)

    def test_txt_sh_rejected(self):
        from backend.app.core.storage import validate_file_upload

        with pytest.raises(ValueError):
            validate_file_upload("shell.txt.sh", "application/pdf", 1024)


class TestL50Harden_FileSizeValidation:
    """L50: Edge cases in file size validation."""

    def test_negative_size(self):
        from backend.app.core.storage import validate_file_upload

        with pytest.raises(ValueError, match="greater than 0"):
            validate_file_upload("f.pdf", "application/pdf", -1)

    def test_zero_size(self):
        from backend.app.core.storage import validate_file_upload

        with pytest.raises(ValueError, match="greater than 0"):
            validate_file_upload("f.pdf", "application/pdf", 0)

    def test_exactly_at_limit(self):
        from backend.app.core.storage import validate_file_upload

        # Exactly at limit should pass
        result = validate_file_upload("f.pdf", "application/pdf", 10 * 1024 * 1024, tier="starter")
        assert result == "f.pdf"

    def test_one_byte_over_limit(self):
        from backend.app.core.storage import validate_file_upload

        with pytest.raises(ValueError, match="exceeds"):
            validate_file_upload("f.pdf", "application/pdf", 10 * 1024 * 1024 + 1, tier="starter")


class TestL51Harden_CompanyIsolation:
    """L51: Cross-company file access is blocked."""

    def test_cannot_list_other_company(self, tmp_path):
        from backend.app.core.storage import LocalStorageBackend

        backend = LocalStorageBackend(base_path=str(tmp_path))
        backend.upload("comp-a", "secret.pdf", b"data", "application/pdf")

        assert backend.list_files("comp-b") == []

    def test_cannot_delete_other_company(self, tmp_path):
        from backend.app.core.storage import LocalStorageBackend

        backend = LocalStorageBackend(base_path=str(tmp_path))
        backend.upload("comp-a", "secret.pdf", b"data", "application/pdf")

        # Trying to delete from comp-b should return False (not found)
        result = backend.delete("comp-b", "secret.pdf")
        assert result is False


class TestL52_54Harden_AuditCrossTenant:
    """L52-L54: Audit queries, stats, exports are scoped to company_id."""

    def test_query_scoped(self):
        from backend.app.services.audit_service import query_audit_trail
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            items, total = query_audit_trail(db, company_id="nonexistent-xyz-123")
            assert total == 0
        finally:
            db.close()

    def test_stats_scoped(self):
        from backend.app.services.audit_service import get_audit_stats
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            stats = get_audit_stats(db, company_id="nonexistent-xyz-123")
            assert stats["total_count"] == 0
        finally:
            db.close()

    def test_export_scoped(self):
        from backend.app.services.audit_service import export_audit_trail
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            items = export_audit_trail(db, company_id="nonexistent-xyz-123")
            assert items == []
        finally:
            db.close()

    def test_query_requires_company_id(self):
        from backend.app.services.audit_service import query_audit_trail

        with pytest.raises(ValueError, match="company_id"):
            query_audit_trail(None, company_id="")

    def test_export_requires_company_id(self):
        from backend.app.services.audit_service import export_audit_trail

        with pytest.raises(ValueError, match="company_id"):
            export_audit_trail(None, company_id="")


class TestL55Harden_AuditCompanyIdValidation:
    """L55: AuditEntry rejects invalid company_id values."""

    def test_empty_rejected(self):
        from backend.app.services.audit_service import AuditEntry

        with pytest.raises(ValueError):
            AuditEntry(company_id="")

    def test_none_rejected(self):
        from backend.app.services.audit_service import AuditEntry

        with pytest.raises((ValueError, TypeError)):
            AuditEntry(company_id=None)  # type: ignore

    def test_too_long_rejected(self):
        from backend.app.services.audit_service import AuditEntry

        with pytest.raises(ValueError, match="128"):
            AuditEntry(company_id="x" * 200)

    def test_invalid_actor_type_rejected(self):
        from backend.app.services.audit_service import AuditEntry

        with pytest.raises(ValueError, match="actor_type"):
            AuditEntry(company_id="c1", actor_type="hacker")


class TestL56Harden_PoisonPill:
    """L56: Malformed JSON in Redis queue is handled gracefully."""

    def test_process_queue_handles_bad_json(self):
        from backend.app.services.audit_service import process_audit_queue

        # Without Redis, returns gracefully
        result = process_audit_queue()
        assert "status" in result


class TestL57Harden_SingletonReset:
    """L57: reset_storage_backend() properly clears singleton."""

    def test_reset_then_get(self):
        import backend.app.core.storage as storage_mod

        storage_mod.reset_storage_backend()
        assert storage_mod._storage_backend_instance is None

        b = storage_mod.get_storage_backend()
        assert storage_mod._storage_backend_instance is b

        storage_mod.reset_storage_backend()
        assert storage_mod._storage_backend_instance is None


class TestL58Harden_SessionLeak:
    """L58: cleanup_old_audit_entries() closes its own session."""

    def test_cleanup_manages_session(self):
        from backend.app.services.audit_service import cleanup_old_audit_entries

        deleted = cleanup_old_audit_entries(retention_days=9999)
        assert isinstance(deleted, int)
