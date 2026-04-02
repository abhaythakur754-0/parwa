"""
Day 17 Tests: PaginatedResponse + File Storage + Audit Persistence

Tests for the three Day 17 deliverables:
1. PaginatedResponse utility + SQLAlchemy pagination helper
2. File storage service (core + service layer)
3. Audit persistence enhancements (flush bug fix, query, stats, etc.)
"""

import hashlib
import os
import tempfile
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from database.base import SessionLocal


# ════════════════════════════════════════════════════════════════════
# PART 1: PAGINATED RESPONSE TESTS
# ════════════════════════════════════════════════════════════════════


class TestPaginatedResponse:
    """Tests for core PaginatedResponse[T] model."""

    def test_basic_response_creation(self):
        from backend.app.core.pagination import PaginatedResponse

        resp = PaginatedResponse[str](
            items=["a", "b"],
            total=2,
            offset=0,
            limit=20,
            has_next=False,
            has_prev=False,
            total_pages=1,
        )
        assert resp.total == 2
        assert resp.items == ["a", "b"]
        assert resp.total_pages == 1

    def test_has_next_true(self):
        from backend.app.core.pagination import PaginatedResponse

        resp = PaginatedResponse[str](
            items=["a"],
            total=10,
            offset=0,
            limit=5,
            has_next=True,
            has_prev=False,
            total_pages=2,
        )
        assert resp.has_next is True
        assert resp.has_prev is False

    def test_has_prev_true(self):
        from backend.app.core.pagination import PaginatedResponse

        resp = PaginatedResponse[str](
            items=[],
            total=10,
            offset=5,
            limit=5,
            has_next=True,
            has_prev=True,
            total_pages=2,
        )
        assert resp.has_prev is True

    def test_empty_page(self):
        from backend.app.core.pagination import PaginatedResponse

        resp = PaginatedResponse[str](
            items=[],
            total=0,
            offset=0,
            limit=20,
            has_next=False,
            has_prev=False,
            total_pages=1,
        )
        assert resp.total == 0
        assert resp.items == []
        assert resp.total_pages == 1

    def test_model_config_has_example(self):
        from backend.app.core.pagination import PaginatedResponse

        assert "examples" in PaginatedResponse.model_config.get("json_schema_extra", {})


class TestPaginateQuery:
    """Tests for paginate_query() with SQLite."""

    def test_paginate_with_sqlite(self):
        from backend.app.core.pagination import paginate_query
        from database.models.core import Company
        from shared.utils.pagination import parse_pagination

        db = SessionLocal()
        try:
            # Create test data (append to any existing data)
            for i in range(3):
                c = Company(
                    id=str(uuid.uuid4()),
                    name=f"PagTest Co {uuid.uuid4().hex[:6]}",
                    industry="test_industry",
                    subscription_tier="starter",
                    mode="shadow",
                )
                db.add(c)
            db.commit()

            params = parse_pagination(offset=0, limit=2)
            query = db.query(Company).order_by(Company.name)
            items, total = paginate_query(query, params, db)

            assert total >= 3
            assert len(items) <= 2
            assert all(isinstance(item, Company) for item in items)
        finally:
            db.rollback()
            db.close()

    def test_paginate_returns_empty_for_no_data(self):
        from backend.app.core.pagination import paginate_query
        from database.models.core import Company
        from shared.utils.pagination import parse_pagination

        db = SessionLocal()
        try:
            # Clear companies
            db.query(Company).delete()
            db.commit()

            params = parse_pagination(offset=0, limit=20)
            query = db.query(Company)
            items, total = paginate_query(query, params, db)

            assert total == 0
            assert items == []
        finally:
            db.rollback()
            db.close()


class TestSortParams:
    """Tests for SortParams and parse_sort()."""

    def test_default_sort(self):
        from backend.app.core.pagination import parse_sort, DEFAULT_SORT_DIRECTION

        result = parse_sort()
        assert result.field == "created_at"
        assert result.direction == DEFAULT_SORT_DIRECTION

    def test_custom_sort(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_by="name", sort_dir="asc")
        assert result.field == "name"
        assert result.direction == "asc"

    def test_invalid_direction_falls_back(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(sort_dir="invalid")
        assert result.direction == "desc"

    def test_whitelist_rejects_unknown_field(self):
        from backend.app.core.pagination import parse_sort

        result = parse_sort(
            sort_by="password_hash",
            allowed_fields=["name", "email"],
        )
        # Should fall back to default
        assert result.field == "created_at"


class TestFilterParams:
    """Tests for FilterParams and apply_filters()."""

    def test_basic_eq_filter(self):
        from backend.app.core.pagination import FilterParams, apply_filters
        from database.models.core import Company

        db = SessionLocal()
        try:
            query = db.query(Company)
            filters = [
                FilterParams(field="subscription_tier", operator="eq", value="starter"),
            ]
            filtered = apply_filters(query, Company, filters)
            assert filtered is not None
        finally:
            db.close()

    def test_unknown_field_skipped(self):
        from backend.app.core.pagination import FilterParams, apply_filters
        from database.models.core import Company

        db = SessionLocal()
        try:
            query = db.query(Company)
            filters = [
                FilterParams(field="nonexistent_field", operator="eq", value="test"),
            ]
            filtered = apply_filters(query, Company, filters)
            # Should not raise, just skip
            assert filtered is not None
        finally:
            db.close()

    def test_none_value_skipped(self):
        from backend.app.core.pagination import FilterParams, apply_filters
        from database.models.core import Company

        db = SessionLocal()
        try:
            query = db.query(Company)
            filters = [
                FilterParams(field="name", operator="eq", value=None),
            ]
            filtered = apply_filters(query, Company, filters)
            assert filtered is not None
        finally:
            db.close()

    def test_unsupported_operator_raises(self):
        from backend.app.core.pagination import FilterParams, apply_filters
        from database.models.core import Company

        db = SessionLocal()
        try:
            query = db.query(Company)
            filters = [
                FilterParams(field="name", operator="regex", value="test"),
            ]
            with pytest.raises(ValueError, match="Unsupported filter operator"):
                apply_filters(query, Company, filters)
        finally:
            db.close()

    def test_gte_filter(self):
        from backend.app.core.pagination import FilterParams, apply_filters
        from database.models.core import Company

        db = SessionLocal()
        try:
            query = db.query(Company)
            filters = [
                FilterParams(field="subscription_tier", operator="neq", value="free"),
            ]
            filtered = apply_filters(query, Company, filters)
            assert filtered is not None
        finally:
            db.close()


class TestPaginationRequestSchema:
    """Tests for PaginationRequest Pydantic schema."""

    def test_defaults(self):
        from backend.app.schemas.pagination import PaginationRequest

        req = PaginationRequest()
        assert req.offset == 0
        assert req.limit == 20
        assert req.sort_dir == "desc"

    def test_clamp_limit(self):
        from backend.app.schemas.pagination import PaginationRequest

        req = PaginationRequest(limit=999)
        assert req.limit == 100

    def test_clamp_offset(self):
        from backend.app.schemas.pagination import PaginationRequest

        req = PaginationRequest(offset=99999)
        assert req.offset == 10000

    def test_invalid_sort_dir_corrected(self):
        from backend.app.schemas.pagination import PaginationRequest

        req = PaginationRequest(sort_dir="sideways")
        assert req.sort_dir == "desc"


# ════════════════════════════════════════════════════════════════════
# PART 2: FILE STORAGE TESTS
# ════════════════════════════════════════════════════════════════════


class TestPathValidation:
    """Tests for path traversal prevention."""

    def test_reject_directory_traversal_in_company_id(self):
        from backend.app.core.storage import _validate_company_id

        with pytest.raises(ValueError, match=".."):
            _validate_company_id("../etc")

    def test_reject_slash_in_company_id(self):
        from backend.app.core.storage import _validate_company_id

        with pytest.raises(ValueError, match="/"):
            _validate_company_id("comp/sub")

    def test_reject_backslash_in_company_id(self):
        from backend.app.core.storage import _validate_company_id

        with pytest.raises(ValueError, match="backslash"):
            _validate_company_id("comp\\sub")

    def test_reject_empty_company_id(self):
        from backend.app.core.storage import _validate_company_id

        with pytest.raises(ValueError, match="required"):
            _validate_company_id("")

    def test_reject_leading_whitespace_company_id(self):
        from backend.app.core.storage import _validate_company_id

        with pytest.raises(ValueError, match="whitespace"):
            _validate_company_id(" comp123 ")

    def test_accept_valid_company_id(self):
        from backend.app.core.storage import _validate_company_id

        # Should not raise
        _validate_company_id("comp-abc-123")

    def test_reject_absolute_file_path(self):
        from backend.app.core.storage import _validate_file_path

        with pytest.raises(ValueError, match="must not start"):
            _validate_file_path("/etc/passwd")

    def test_reject_traversal_in_file_path(self):
        from backend.app.core.storage import _validate_file_path

        with pytest.raises(ValueError, match="directory traversal"):
            _validate_file_path("uploads/../../../etc/passwd")

    def test_reject_null_byte_in_file_path(self):
        from backend.app.core.storage import _validate_file_path

        with pytest.raises(ValueError, match="null bytes"):
            _validate_file_path("file\x00.txt")

    def test_reject_backslash_in_file_path(self):
        from backend.app.core.storage import _validate_file_path

        with pytest.raises(ValueError, match="backslash"):
            _validate_file_path("path\\to\\file.txt")


class TestFileValidation:
    """Tests for file upload validation."""

    def test_accept_pdf(self):
        from backend.app.core.storage import validate_file_upload

        result = validate_file_upload("test.pdf", "application/pdf", 1024)
        assert result == "test.pdf"

    def test_reject_exe_content_type(self):
        from backend.app.core.storage import validate_file_upload

        with pytest.raises(ValueError, match="not allowed"):
            validate_file_upload("virus.exe", "application/octet-stream", 1024)

    def test_reject_zero_file_size(self):
        from backend.app.core.storage import validate_file_upload

        with pytest.raises(ValueError, match="greater than 0"):
            validate_file_upload("test.pdf", "application/pdf", 0)

    def test_reject_oversized_file_starter(self):
        from backend.app.core.storage import validate_file_upload

        # Starter tier: 10MB limit
        with pytest.raises(ValueError, match="exceeds the limit"):
            validate_file_upload("big.pdf", "application/pdf", 11 * 1024 * 1024)

    def test_accept_max_starter(self):
        from backend.app.core.storage import validate_file_upload

        # Exactly 10MB should pass for starter
        result = validate_file_upload("big.pdf", "application/pdf", 10 * 1024 * 1024)
        assert result == "big.pdf"

    def test_high_tier_allows_50mb(self):
        from backend.app.core.storage import validate_file_upload

        result = validate_file_upload(
            "big.pdf", "application/pdf", 50 * 1024 * 1024, tier="high"
        )
        assert result == "big.pdf"

    def test_content_type_extension_mismatch(self):
        from backend.app.core.storage import validate_file_upload

        with pytest.raises(ValueError, match="does not match"):
            # Claiming PDF content type but file has .csv extension
            validate_file_upload("data.csv", "application/pdf", 1024)

    def test_sanitize_filename(self):
        from backend.app.core.storage import sanitize_filename

        result = sanitize_filename('report <script>alert(1)</script>.pdf')
        # Angle brackets are removed but the word 'script' may remain
        assert "<" not in result
        assert ">" not in result
        assert result.endswith(".pdf")

    def test_empty_filename_rejected(self):
        from backend.app.core.storage import sanitize_filename

        with pytest.raises(ValueError, match="empty"):
            sanitize_filename("")

    def test_allowed_extensions_set(self):
        from backend.app.core.storage import ALLOWED_EXTENSIONS

        assert ".pdf" in ALLOWED_EXTENSIONS
        assert ".exe" not in ALLOWED_EXTENSIONS
        assert ".docx" in ALLOWED_EXTENSIONS


class TestLocalStorageBackend:
    """Tests for LocalStorageBackend with temp directories."""

    @pytest.fixture
    def temp_storage(self, tmp_path):
        from backend.app.core.storage import LocalStorageBackend

        backend = LocalStorageBackend(base_path=str(tmp_path))
        return backend

    def test_upload_and_download(self, temp_storage):
        content = b"Hello, PARWA!"
        meta = temp_storage.upload(
            company_id="comp1",
            file_path="uploads/test.txt",
            content=content,
            content_type="text/plain",
        )

        assert meta.file_name == "test.txt"
        assert meta.size_bytes == len(content)

        downloaded, ct = temp_storage.download("comp1", "uploads/test.txt")
        assert downloaded == content
        assert ct == "text/plain"

    def test_upload_creates_checksum(self, temp_storage):
        content = b"checksum test data"
        meta = temp_storage.upload(
            company_id="comp1",
            file_path="uploads/check.txt",
            content=content,
            content_type="text/plain",
        )

        expected = hashlib.md5(content).hexdigest()
        assert meta.checksum_md5 == expected

    def test_delete_file(self, temp_storage):
        temp_storage.upload(
            company_id="comp1",
            file_path="uploads/del.txt",
            content=b"delete me",
            content_type="text/plain",
        )

        result = temp_storage.delete("comp1", "uploads/del.txt")
        assert result is True

        assert not temp_storage.exists("comp1", "uploads/del.txt")

    def test_delete_nonexistent_returns_false(self, temp_storage):
        result = temp_storage.delete("comp1", "uploads/nope.txt")
        assert result is False

    def test_exists_check(self, temp_storage):
        assert not temp_storage.exists("comp1", "uploads/nope.txt")

        temp_storage.upload(
            company_id="comp1",
            file_path="uploads/real.txt",
            content=b"data",
            content_type="text/plain",
        )
        assert temp_storage.exists("comp1", "uploads/real.txt")

    def test_list_files(self, temp_storage):
        temp_storage.upload(
            company_id="comp1", file_path="a.txt", content=b"a", content_type="text/plain"
        )
        temp_storage.upload(
            company_id="comp1", file_path="b.pdf", content=b"b", content_type="application/pdf"
        )

        files = temp_storage.list_files("comp1")
        assert len(files) == 2

    def test_list_files_empty_company(self, temp_storage):
        files = temp_storage.list_files("nocompany")
        assert files == []

    def test_company_isolation(self, temp_storage):
        temp_storage.upload(
            company_id="comp1", file_path="secret.txt", content=b"secret", content_type="text/plain"
        )

        # comp2 should not see comp1's files
        with pytest.raises(FileNotFoundError):
            temp_storage.download("comp2", "secret.txt")

    def test_get_file_size(self, temp_storage):
        content = b"x" * 100
        temp_storage.upload(
            company_id="comp1", file_path="size.txt", content=content, content_type="text/plain"
        )

        assert temp_storage.get_file_size("comp1", "size.txt") == 100

    def test_signed_url_returns_path(self, temp_storage):
        temp_storage.upload(
            company_id="comp1", file_path="url.txt", content=b"data", content_type="text/plain"
        )

        url = temp_storage.get_signed_url("comp1", "url.txt")
        assert "url.txt" in url


class TestStorageBackendFactory:
    """Tests for get_storage_backend() factory."""

    def test_returns_local_by_default(self):
        from backend.app.core.storage import (
            get_storage_backend,
            reset_storage_backend,
            LocalStorageBackend,
        )

        reset_storage_backend()
        backend = get_storage_backend()
        assert isinstance(backend, LocalStorageBackend)
        reset_storage_backend()

    def test_singleton_behavior(self):
        from backend.app.core.storage import get_storage_backend, reset_storage_backend

        reset_storage_backend()
        b1 = get_storage_backend()
        b2 = get_storage_backend()
        assert b1 is b2
        reset_storage_backend()


class TestFileStorageService:
    """Tests for FileStorageService high-level operations."""

    @pytest.fixture
    def service_and_backend(self, tmp_path):
        from backend.app.core.storage import LocalStorageBackend, reset_storage_backend
        from backend.app.services.file_storage_service import FileStorageService

        reset_storage_backend()
        backend = LocalStorageBackend(base_path=str(tmp_path))
        svc = FileStorageService(backend=backend)
        return svc, backend

    def test_upload_file(self, service_and_backend):
        svc, _ = service_and_backend
        content = b"test content"
        result = svc.upload_file(
            company_id="comp1",
            content=content,
            file_name="report.pdf",
            content_type="application/pdf",
            uploaded_by="user1",
        )

        assert result["company_id"] == "comp1"
        assert result["file_name"] == "report.pdf"
        assert result["size_bytes"] == len(content)
        assert result["checksum_md5"]
        assert "uploaded_at" in result

    def test_upload_file_audit_called(self, service_and_backend):
        svc, _ = service_and_backend
        with patch("backend.app.services.audit_service.log_audit") as mock_audit:
            svc.upload_file(
                company_id="comp1",
                content=b"audit test",
                file_name="audit.pdf",
                content_type="application/pdf",
                uploaded_by="user1",
            )
            mock_audit.assert_called_once()

    def test_upload_rejects_invalid_type(self, service_and_backend):
        svc, _ = service_and_backend
        with pytest.raises(ValueError, match="not allowed"):
            svc.upload_file(
                company_id="comp1",
                content=b"malware",
                file_name="virus.exe",
                content_type="application/octet-stream",
            )

    def test_upload_rejects_no_company(self, service_and_backend):
        svc, _ = service_and_backend
        with pytest.raises(ValueError, match="company_id"):
            svc.upload_file(
                company_id="",
                content=b"data",
                file_name="test.pdf",
                content_type="application/pdf",
            )

    def test_list_files(self, service_and_backend):
        svc, _ = service_and_backend
        svc.upload_file("comp1", b"a", "a.pdf", "application/pdf")
        svc.upload_file("comp1", b"bb", "b.pdf", "application/pdf")

        result = svc.list_files("comp1")
        assert result["total"] == 2
        assert len(result["items"]) == 2

    def test_list_files_paginated(self, service_and_backend):
        svc, _ = service_and_backend
        for i in range(5):
            svc.upload_file("comp1", b"x", f"f{i}.pdf", "application/pdf")

        result = svc.list_files("comp1", offset=0, limit=2)
        assert result["total"] == 5
        assert len(result["items"]) == 2

    def test_check_file_exists(self, service_and_backend):
        svc, _ = service_and_backend
        upload = svc.upload_file("comp1", b"exists", "e.pdf", "application/pdf")

        assert svc.check_file_exists("comp1", upload["file_path"]) is True
        assert svc.check_file_exists("comp1", "no/such/path.txt") is False

    def test_generate_download_url(self, service_and_backend):
        svc, _ = service_and_backend
        upload = svc.upload_file("comp1", b"url", "u.pdf", "application/pdf")

        url = svc.generate_download_url("comp1", upload["file_path"])
        assert url  # Should return something

    def test_delete_file(self, service_and_backend):
        svc, _ = service_and_backend
        upload = svc.upload_file("comp1", b"del", "d.pdf", "application/pdf")

        result = svc.delete_file("comp1", upload["file_path"], deleted_by="user1")
        assert result is True


class TestFileStorageSchemas:
    """Tests for file storage Pydantic schemas."""

    def test_upload_request_defaults(self):
        from backend.app.schemas.file_storage import FileUploadRequest

        req = FileUploadRequest(content_type="application/pdf")
        assert req.tier == "starter"
        assert req.metadata is None

    def test_upload_response_fields(self):
        from backend.app.schemas.file_storage import FileUploadResponse

        resp = FileUploadResponse(
            id="abc",
            company_id="comp1",
            file_path="uploads/abc/test.pdf",
            file_name="test.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            checksum_md5="md5hash",
        )
        assert resp.id == "abc"
        assert resp.company_id == "comp1"

    def test_list_response(self):
        from backend.app.schemas.file_storage import FileListResponse

        resp = FileListResponse(items=[], total=0, offset=0, limit=50)
        assert resp.items == []

    def test_validation_response(self):
        from backend.app.schemas.file_storage import FileValidationResponse

        resp = FileValidationResponse(is_valid=True, sanitized_filename="test.pdf")
        assert resp.is_valid is True


# ════════════════════════════════════════════════════════════════════
# PART 3: AUDIT PERSISTENCE TESTS
# ════════════════════════════════════════════════════════════════════


class TestAuditFlushFix:
    """Tests for the critical log_audit() flush fix."""

    def test_log_audit_uses_flush_not_commit(self):
        from backend.app.services.audit_service import log_audit
        from database.base import SessionLocal
        from database.models.integration import AuditTrail

        db = SessionLocal()
        try:
            result = log_audit(
                company_id="comp1",
                action="create",
                resource_type="test",
                db=db,
            )

            assert result["company_id"] == "comp1"

            # After flush(), the object should be in the session identity map.
            # Query the session (without commit) to verify it was flushed.
            # flush() adds to identity map even though db.new is cleared.
            from sqlalchemy import inspect as sa_inspect
            audit_id = result["id"]
            obj = db.get(AuditTrail, audit_id)
            # If flush was used, the object is visible within the transaction
            assert obj is not None, "AuditTrail not found after flush — commit may have been used instead"

            # Rollback to prove it wasn't committed to DB permanently
            db.rollback()

            # After rollback, a new session should NOT see the entry
            db2 = SessionLocal()
            try:
                obj2 = db2.get(AuditTrail, audit_id)
                assert obj2 is None, "Entry survived rollback — commit() was used instead of flush()"
            finally:
                db2.close()
        finally:
            db.close()

    def test_log_audit_returns_dict(self):
        from backend.app.services.audit_service import log_audit

        result = log_audit(
            company_id="comp1",
            actor_type="system",
            action="login",
        )
        assert isinstance(result, dict)
        assert "id" in result
        assert "company_id" in result
        assert "created_at" in result


class TestAuditQueryTrail:
    """Tests for query_audit_trail() function."""

    def test_query_with_filters(self):
        from backend.app.services.audit_service import log_audit, query_audit_trail
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            # Create audit entries
            log_audit(company_id="comp-q", action="create", resource_type="ticket", db=db)
            log_audit(company_id="comp-q", action="update", resource_type="user", db=db)
            log_audit(company_id="comp-q", action="delete", resource_type="ticket", db=db)
            db.commit()

            # Query all
            items, total = query_audit_trail(db, company_id="comp-q")
            assert total == 3
            assert len(items) == 3

            # Filter by action
            items, total = query_audit_trail(db, company_id="comp-q", action="create")
            assert total == 1
            assert items[0]["action"] == "create"

            # Filter by resource_type
            items, total = query_audit_trail(db, company_id="comp-q", resource_type="ticket")
            assert total == 2

            # Pagination
            items, total = query_audit_trail(db, company_id="comp-q", limit=1, offset=0)
            assert total == 3
            assert len(items) == 1
        finally:
            db.rollback()
            db.close()

    def test_query_empty_company(self):
        from backend.app.services.audit_service import query_audit_trail
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            items, total = query_audit_trail(db, company_id="nonexistent")
            assert total == 0
            assert items == []
        finally:
            db.close()

    def test_query_requires_company_id(self):
        from backend.app.services.audit_service import query_audit_trail

        with pytest.raises(ValueError, match="company_id"):
            query_audit_trail(None, company_id="")


class TestAuditStats:
    """Tests for get_audit_stats() function."""

    def test_stats_with_data(self):
        from backend.app.services.audit_service import get_audit_stats, log_audit
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            for i in range(5):
                log_audit(company_id="stats-comp", action="create", db=db)
            log_audit(company_id="stats-comp", action="delete", db=db)
            db.commit()

            stats = get_audit_stats(db, company_id="stats-comp", days=30)
            assert stats["total_count"] == 6
            assert "create" in stats["action_counts"]
            assert stats["action_counts"]["create"] == 5
            assert stats["action_counts"]["delete"] == 1
            assert stats["recent_24h_count"] == 6
            assert "actor_type_counts" in stats
        finally:
            db.rollback()
            db.close()

    def test_stats_empty_company(self):
        from backend.app.services.audit_service import get_audit_stats
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            stats = get_audit_stats(db, company_id="no-company", days=30)
            assert stats["total_count"] == 0
            assert stats["recent_24h_count"] == 0
        finally:
            db.close()


class TestAuditExport:
    """Tests for export_audit_trail() function."""

    def test_export_json(self):
        from backend.app.services.audit_service import export_audit_trail, log_audit
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            log_audit(company_id="export-comp", action="create", db=db)
            log_audit(company_id="export-comp", action="update", db=db)
            db.commit()

            items = export_audit_trail(db, company_id="export-comp", format="json")
            assert len(items) == 2
            assert items[0]["company_id"] == "export-comp"
            assert "created_at" in items[0]
        finally:
            db.rollback()
            db.close()

    def test_export_unsupported_format(self):
        from backend.app.services.audit_service import export_audit_trail
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            with pytest.raises(ValueError, match="Unsupported"):
                export_audit_trail(db, company_id="comp", format="csv")
        finally:
            db.close()


class TestAuditAsyncLogging:
    """Tests for async_log_audit() via Redis queue."""

    @pytest.mark.asyncio
    async def test_async_log_audit(self):
        from backend.app.services.audit_service import async_log_audit

        mock_redis = MagicMock()
        mock_redis.rpush = MagicMock(return_value=None)

        result = await async_log_audit(
            mock_redis,
            company_id="async-comp",
            action="login",
            actor_type="user",
        )

        assert result["company_id"] == "async-comp"
        mock_redis.rpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_log_audit_redis_failure(self):
        from backend.app.services.audit_service import async_log_audit

        mock_redis = MagicMock()
        mock_redis.rpush = MagicMock(side_effect=Exception("Redis down"))

        # Should still return the entry dict (fire-and-forget)
        result = await async_log_audit(
            mock_redis,
            company_id="comp",
            action="login",
        )

        assert result["company_id"] == "comp"


class TestAuditProcessQueue:
    """Tests for process_audit_queue() function."""

    def test_process_queue_no_redis(self):
        from backend.app.services.audit_service import process_audit_queue

        # Without Redis running, should handle gracefully
        result = process_audit_queue()
        # Should either fail gracefully or process 0 entries
        assert "status" in result


class TestAuditCleanup:
    """Tests for cleanup_old_audit_entries() function."""

    def test_cleanup_with_no_old_entries(self):
        from backend.app.services.audit_service import cleanup_old_audit_entries

        # No entries older than 365 days
        deleted = cleanup_old_audit_entries(retention_days=365)
        assert deleted == 0

    def test_cleanup_scoped_to_company(self):
        from backend.app.services.audit_service import cleanup_old_audit_entries

        # Scoped cleanup should also work
        deleted = cleanup_old_audit_entries(
            company_id="nonexistent", retention_days=365
        )
        assert deleted == 0


class TestAuditEntryToJson:
    """Tests for AuditEntry.to_json() method."""

    def test_to_json_serializes_datetime(self):
        from backend.app.services.audit_service import AuditEntry

        entry = AuditEntry(
            company_id="comp1",
            action="test",
        )
        json_str = entry.to_json()

        assert "comp1" in json_str
        assert "test" in json_str
        # Should be valid JSON
        import json
        parsed = json.loads(json_str)
        assert parsed["company_id"] == "comp1"

    def test_to_json_datetime_is_string(self):
        from backend.app.services.audit_service import AuditEntry

        entry = AuditEntry(company_id="c1", action="a")
        import json
        parsed = json.loads(entry.to_json())
        assert isinstance(parsed["created_at"], str)


# ════════════════════════════════════════════════════════════════════
# PART 4: PERIODIC TASKS (AUDIT)
# ════════════════════════════════════════════════════════════════════


class TestAuditPeriodicTasks:
    """Tests for audit periodic Celery tasks."""

    def test_flush_audit_queue_task_exists(self):
        from backend.app.tasks.periodic import flush_audit_queue

        assert callable(flush_audit_queue)

    def test_cleanup_audit_trail_task_exists(self):
        from backend.app.tasks.periodic import cleanup_audit_trail

        assert callable(cleanup_audit_trail)

    def test_flush_audit_queue_in_beat_schedule(self):
        from backend.app.tasks.celery_app import app as celery_app

        schedule = celery_app.conf.get("beat_schedule", {})
        assert "flush-audit-queue" in schedule
        assert schedule["flush-audit-queue"]["schedule"] == 60.0

    def test_cleanup_audit_trail_in_beat_schedule(self):
        from backend.app.tasks.celery_app import app as celery_app

        schedule = celery_app.conf.get("beat_schedule", {})
        assert "cleanup-audit-trail" in schedule

    def test_beat_schedule_has_5_entries(self):
        from backend.app.tasks.celery_app import app as celery_app

        schedule = celery_app.conf.get("beat_schedule", {})
        assert len(schedule) == 5


# ════════════════════════════════════════════════════════════════════
# PART 5: IMPORT VERIFICATION
# ════════════════════════════════════════════════════════════════════


class TestDay17Imports:
    """Verify all Day 17 modules are importable."""

    def test_import_core_pagination(self):
        from backend.app.core.pagination import (
            PaginatedResponse,
            paginate_query,
            paginate_query_v2,
            build_paginated_response,
            SortParams,
            parse_sort,
            FilterParams,
            apply_filters,
        )
        assert all(f is not None for f in [
            PaginatedResponse, paginate_query, build_paginated_response,
            SortParams, parse_sort, FilterParams, apply_filters,
        ])

    def test_import_schemas_pagination(self):
        from backend.app.schemas.pagination import (
            PaginationRequest,
            PaginatedResponseSchema,
        )
        assert PaginationRequest is not None
        assert PaginatedResponseSchema is not None

    def test_import_core_storage(self):
        from backend.app.core.storage import (
            StorageBackend,
            LocalStorageBackend,
            GCPStorageBackend,
            FileMetadata,
            get_storage_backend,
            validate_file_upload,
            sanitize_filename,
        )
        assert all(f is not None for f in [
            StorageBackend, LocalStorageBackend, GCPStorageBackend,
            FileMetadata, validate_file_upload, sanitize_filename,
        ])

    def test_import_file_storage_service(self):
        from backend.app.services.file_storage_service import FileStorageService
        assert FileStorageService is not None

    def test_import_file_storage_schemas(self):
        from backend.app.schemas.file_storage import (
            FileUploadRequest,
            FileUploadResponse,
            FileMetadataResponse,
            FileListResponse,
        )
        assert all(f is not None for f in [
            FileUploadRequest, FileUploadResponse,
            FileMetadataResponse, FileListResponse,
        ])

    def test_import_audit_enhancements(self):
        from backend.app.services.audit_service import (
            async_log_audit,
            process_audit_queue,
            query_audit_trail,
            export_audit_trail,
            get_audit_stats,
            cleanup_old_audit_entries,
        )
        assert all(f is not None for f in [
            async_log_audit, process_audit_queue,
            query_audit_trail, export_audit_trail,
            get_audit_stats, cleanup_old_audit_entries,
        ])
