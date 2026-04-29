"""
PARWA File Storage Service

High-level file storage service that orchestrates file upload/download/delete
operations using the pluggable storage backend from core/storage.py.

Every operation is scoped by company_id (BC-001). All writes are logged
to the audit trail (BC-012).

Security measures:
    - Path traversal prevention in all file operations
    - Company isolation (BC-001) — every query filtered by company_id
    - File size validation per subscription tier
    - Content type whitelist enforcement
    - Filename sanitization
    - MD5 checksums for integrity (BC-010)
"""

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.storage import (
    StorageBackend,
    UPLOAD_SUBDIR,
    validate_file_upload,
)
from app.core.storage import (
    get_storage_backend as _get_storage_backend,
)

logger = logging.getLogger("parwa.file_storage")


class FileStorageService:
    """High-level file storage operations.

    Wraps the pluggable StorageBackend with business logic including
    validation, audit logging, and paginated file listing.

    Usage::

        svc = FileStorageService()
        result = svc.upload_file("comp-123", content, "report.pd", "application/pd", uploaded_by="user-456")
    """

    def __init__(self, backend: Optional[StorageBackend] = None) -> None:
        """Initialize with a storage backend.

        Args:
            backend: Optional StorageBackend instance. If None, uses
                     the global singleton from get_storage_backend().
        """
        self._backend = backend

    @property
    def backend(self) -> StorageBackend:
        """Lazy-load the storage backend."""
        if self._backend is None:
            self._backend = _get_storage_backend()
        return self._backend

    def upload_file(
        self,
        company_id: str,
        content: bytes,
        file_name: str,
        content_type: str,
        uploaded_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tier: str = "mini_parwa",
    ) -> Dict[str, Any]:
        """Upload a file with validation and audit logging.

        Validates the file, generates a unique storage path, computes
        checksums, stores the file via the backend, and returns metadata.

        Args:
            company_id: Tenant ID (BC-001 — required).
            content: Raw file bytes.
            file_name: Original filename from user upload.
            content_type: MIME type declared for the upload.
            uploaded_by: Optional ID of the user who uploaded.
            metadata: Optional custom metadata key-value pairs.
            tier: Subscription tier for file size limits (starter/growth/high).

        Returns:
            Dict with keys: id, company_id, file_path, file_name,
            content_type, size_bytes, checksum_md5, uploaded_at, uploaded_by,
            metadata.

        Raises:
            ValueError: If validation fails (file type, size, etc.).
            OSError: If storage write fails.
        """
        if not company_id:
            raise ValueError("company_id is required for file upload (BC-001)")

        file_size = len(content)

        # Validate the upload
        sanitized_name = validate_file_upload(
            filename=file_name,
            content_type=content_type,
            file_size=file_size,
            tier=tier,
        )

        # Generate unique storage path
        unique_id = str(uuid.uuid4())
        storage_path = f"{UPLOAD_SUBDIR}/{unique_id}/{sanitized_name}"

        # Build upload metadata
        upload_metadata = metadata or {}
        upload_metadata["original_filename"] = file_name
        upload_metadata["uploaded_by"] = uploaded_by
        upload_metadata["tier"] = tier

        # Store via backend
        file_meta = self.backend.upload(
            company_id=company_id,
            file_path=storage_path,
            content=content,
            content_type=content_type,
            metadata=upload_metadata,
        )

        logger.info(
            "File uploaded: company_id=%s, path=%s, size=%d, by=%s",
            company_id,
            storage_path,
            file_size,
            uploaded_by,
        )

        # Audit log
        try:
            from app.services.audit_service import log_audit

            log_audit(
                company_id=company_id,
                actor_id=uploaded_by,
                actor_type="user" if uploaded_by else "system",
                action="create",
                resource_type="file",
                resource_id=unique_id,
                new_value=f"{sanitized_name} ({file_size} bytes)",
            )
        except Exception as exc:
            # Audit must never break main flow (BC-012)
            logger.warning("Failed to log file upload audit: %s", exc)

        return {
            "id": unique_id,
            "company_id": company_id,
            "file_path": storage_path,
            "file_name": sanitized_name,
            "original_filename": file_name,
            "content_type": content_type,
            "size_bytes": file_meta.size_bytes,
            "checksum_md5": file_meta.checksum_md5,
            "uploaded_at": (
                file_meta.uploaded_at.isoformat() if file_meta.uploaded_at else None
            ),
            "uploaded_by": uploaded_by,
            "metadata": upload_metadata,
        }

    def download_file(
        self,
        company_id: str,
        file_id: str,
    ) -> Dict[str, Any]:
        """Download a file by its storage path.

        Args:
            company_id: Tenant ID (BC-001 — required).
            file_id: The UUID portion of the storage path (from upload response).

        Returns:
            Dict with keys: content (bytes), content_type, file_name.

        Raises:
            FileNotFoundError: If the file does not exist.
            PermissionError: If company_id doesn't match.
        """
        if not company_id:
            raise ValueError("company_id is required (BC-001)")
        if not file_id:
            raise ValueError("file_id is required")

        # Try common upload paths
        content, content_type = self.backend.download(
            company_id=company_id,
            file_path=f"{UPLOAD_SUBDIR}/{file_id}",
        )

        logger.info(
            "File downloaded: company_id=%s, file_id=%s",
            company_id,
            file_id,
        )

        return {
            "content": content,
            "content_type": content_type,
            "file_id": file_id,
            "company_id": company_id,
        }

    def delete_file(
        self,
        company_id: str,
        file_path: str,
        deleted_by: Optional[str] = None,
    ) -> bool:
        """Delete a file.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Storage path of the file to delete.
            deleted_by: Optional ID of user performing deletion.

        Returns:
            True if file was deleted, False if not found.
        """
        if not company_id:
            raise ValueError("company_id is required (BC-001)")

        result = self.backend.delete(
            company_id=company_id,
            file_path=file_path,
        )

        if result:
            logger.info(
                "File deleted: company_id=%s, path=%s, by=%s",
                company_id,
                file_path,
                deleted_by,
            )

            # Audit log
            try:
                from app.services.audit_service import log_audit

                log_audit(
                    company_id=company_id,
                    actor_id=deleted_by,
                    actor_type="user" if deleted_by else "system",
                    action="delete",
                    resource_type="file",
                    resource_id=file_path,
                    old_value=file_path,
                )
            except Exception:
                pass

        return result

    def list_files(
        self,
        company_id: str,
        prefix: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List files with pagination.

        Args:
            company_id: Tenant ID (BC-001).
            prefix: Optional path prefix filter.
            offset: Pagination offset.
            limit: Pagination limit (max 100).

        Returns:
            Dict with keys: items, total, offset, limit.
        """
        if not company_id:
            raise ValueError("company_id is required (BC-001)")

        from shared.utils.pagination import parse_pagination

        params = parse_pagination(offset=offset, limit=limit, max_limit=100)

        files = self.backend.list_files(
            company_id=company_id,
            prefix=prefix,
        )

        total = len(files)
        page_files = files[params.offset : params.offset + params.limit]

        return {
            "items": [
                {
                    "file_path": f.file_path,
                    "file_name": f.file_name,
                    "content_type": f.content_type,
                    "size_bytes": f.size_bytes,
                    "checksum_md5": f.checksum_md5,
                    "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
                }
                for f in page_files
            ],
            "total": total,
            "offset": params.offset,
            "limit": params.limit,
        }

    def get_file_metadata(
        self,
        company_id: str,
        file_path: str,
    ) -> Dict[str, Any]:
        """Get metadata for a single file.

        Checks existence and returns file info from the storage backend.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Storage path of the file.

        Returns:
            Dict with file metadata fields.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if not company_id:
            raise ValueError("company_id is required (BC-001)")

        if not self.backend.exists(company_id, file_path):
            raise FileNotFoundError(
                f"File not found: {file_path} for company {company_id}"
            )

        size = self.backend.get_file_size(company_id, file_path)
        file_name = Path(file_path).name
        ext = Path(file_path).suffix.lower()
        from app.core.storage import EXTENSION_TO_CONTENT_TYPE

        content_type = EXTENSION_TO_CONTENT_TYPE.get(ext, "application/octet-stream")

        return {
            "company_id": company_id,
            "file_path": file_path,
            "file_name": file_name,
            "content_type": content_type,
            "size_bytes": size,
            "exists": True,
        }

    def generate_download_url(
        self,
        company_id: str,
        file_path: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a signed URL for direct file download.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Storage path of the file.
            expires_in: URL validity in seconds (default 1 hour).

        Returns:
            Signed URL string or local path (for local backend).

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if not company_id:
            raise ValueError("company_id is required (BC-001)")

        return self.backend.get_signed_url(
            company_id=company_id,
            file_path=file_path,
            expires_in=expires_in,
        )

    def check_file_exists(
        self,
        company_id: str,
        file_path: str,
    ) -> bool:
        """Check if a file exists.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Storage path.

        Returns:
            True if file exists, False otherwise.
        """
        if not company_id:
            raise ValueError("company_id is required (BC-001)")

        return self.backend.exists(company_id, file_path)
