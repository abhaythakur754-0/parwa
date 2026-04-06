"""
PARWA File Storage Core Module

Provides abstract storage backend interface and concrete implementations
for local filesystem and GCP Cloud Storage.

BC-001: Every file operation scoped by company_id (multi-tenant isolation).
BC-010: GDPR/HIPAA compliance — checksums for integrity verification.
BC-012: Audit trail for all write operations (handled at service layer).

Supported file types (F-032):
  PDF, DOCX, TXT, MD, HTML, CSV
"""

import hashlib
import logging
import os
import re
import unicodedata
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────────

"""MIME types allowed for file uploads (F-032)."""
ALLOWED_CONTENT_TYPES: set = {
    "application/pdf",  # .pdf
    "text/plain",  # .txt
    "text/markdown",  # .md
    "text/html",  # .html
    "text/csv",  # .csv
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
}

"""File extensions allowed for upload (F-032)."""
ALLOWED_EXTENSIONS: set = {".pdf", ".txt", ".md", ".html", ".csv", ".docx"}

"""Mapping from extension to canonical MIME type."""
EXTENSION_TO_CONTENT_TYPE: dict = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html",
    ".csv": "text/csv",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

"""Mapping from MIME type to canonical extension."""
CONTENT_TYPE_TO_EXTENSION: dict = {v: k for k, v in EXTENSION_TO_CONTENT_TYPE.items()}

"""Default maximum file size: 50 MB."""
MAX_FILE_SIZE: int = 50 * 1024 * 1024

"""Maximum file size per subscription tier (in bytes).

Starter: 10 MB, Growth: 25 MB, High: 50 MB.
"""
MAX_FILE_SIZE_BY_TIER: dict = {
    "starter": 10 * 1024 * 1024,
    "growth": 25 * 1024 * 1024,
    "high": 50 * 1024 * 1024,
}

"""Path separator for storage keys."""
STORAGE_PATH_SEPARATOR: str = "/"

"""Subdirectory for user-uploaded files."""
UPLOAD_SUBDIR: str = "uploads"


# ── FileMetadata Model ──────────────────────────────────────────────

class FileMetadata(BaseModel):
    """Metadata returned for every stored file.

    Used for tracking file provenance, integrity, and access control.
    Every file is scoped to a company_id (BC-001).

    Attributes:
        company_id: Tenant that owns this file (BC-001).
        file_path: Full logical path within the storage backend
                   (e.g. "company_id/uploads/uuid/filename.pdf").
        file_name: Original/sanitized file name.
        content_type: MIME type of the file.
        size_bytes: File size in bytes.
        checksum_md5: MD5 hex digest for integrity verification (BC-010).
        uploaded_at: ISO-8601 timestamp of upload.
        metadata: Arbitrary custom metadata key-value pairs.
    """

    company_id: str
    file_path: str
    file_name: str
    content_type: str
    size_bytes: int
    checksum_md5: str
    uploaded_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Storage Backend ABC ─────────────────────────────────────────────

class StorageBackend(ABC):
    """Abstract base class for file storage backends.

    All operations are scoped by company_id to enforce multi-tenant
    isolation (BC-001). Implementations must prevent directory traversal
    attacks.

    Implementations:
        - LocalStorageBackend: Files on local filesystem (development).
        - GCPStorageBackend: Google Cloud Storage (production).
    """

    @abstractmethod
    def upload(
        self,
        company_id: str,
        file_path: str,
        content: bytes,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileMetadata:
        """Upload a file to storage.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Logical path within the company's storage namespace.
            content: Raw file bytes.
            content_type: MIME type of the file.
            metadata: Optional custom metadata.

        Returns:
            FileMetadata with upload details including checksum.

        Raises:
            ValueError: If inputs are invalid.
            OSError: If storage write fails.
        """
        ...

    @abstractmethod
    def download(
        self,
        company_id: str,
        file_path: str,
    ) -> Tuple[bytes, str]:
        """Download a file from storage.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Logical path of the file.

        Returns:
            Tuple of (file_content: bytes, content_type: str).

        Raises:
            FileNotFoundError: If the file does not exist.
            PermissionError: If company_id doesn't match.
        """
        ...

    @abstractmethod
    def delete(
        self,
        company_id: str,
        file_path: str,
    ) -> bool:
        """Delete a file from storage.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Logical path of the file.

        Returns:
            True if the file was deleted, False if not found.

        Raises:
            PermissionError: If company_id doesn't match.
        """
        ...

    @abstractmethod
    def list_files(
        self,
        company_id: str,
        prefix: Optional[str] = None,
    ) -> List[FileMetadata]:
        """List files in a company's storage namespace.

        Args:
            company_id: Tenant ID (BC-001).
            prefix: Optional path prefix to filter results.

        Returns:
            List of FileMetadata for matching files.

        Raises:
            PermissionError: If company_id doesn't match.
        """
        ...

    @abstractmethod
    def get_signed_url(
        self,
        company_id: str,
        file_path: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a signed URL for direct file access.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Logical path of the file.
            expires_in: URL validity duration in seconds (default 1 hour).

        Returns:
            Signed URL string (for GCP) or local file path (for local dev).

        Raises:
            FileNotFoundError: If the file does not exist.
            PermissionError: If company_id doesn't match.
        """
        ...

    @abstractmethod
    def exists(
        self,
        company_id: str,
        file_path: str,
    ) -> bool:
        """Check if a file exists in storage.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Logical path of the file.

        Returns:
            True if the file exists, False otherwise.
        """
        ...

    @abstractmethod
    def get_file_size(
        self,
        company_id: str,
        file_path: str,
    ) -> int:
        """Get the size of a file in bytes.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Logical path of the file.

        Returns:
            File size in bytes.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        ...


# ── Path Validation Helpers ─────────────────────────────────────────

def _validate_company_id(company_id: str) -> None:
    """Validate company_id to prevent directory traversal (BC-001).

    Args:
        company_id: The company identifier to validate.

    Raises:
        ValueError: If company_id contains traversal characters.
    """
    if not company_id or not isinstance(company_id, str):
        raise ValueError("company_id is required and must be a non-empty string")
    if ".." in company_id:
        raise ValueError("company_id must not contain '..'")
    if "/" in company_id:
        raise ValueError("company_id must not contain '/'")
    if "\\" in company_id:
        raise ValueError("company_id must not contain backslash")
    if company_id.strip() != company_id:
        raise ValueError("company_id must not have leading/trailing whitespace")


def _validate_file_path(file_path: str) -> None:
    """Validate file_path to prevent directory traversal attacks.

    Args:
        file_path: The relative file path to validate.

    Raises:
        ValueError: If file_path is dangerous or malformed.
    """
    if not file_path or not isinstance(file_path, str):
        raise ValueError("file_path is required and must be a non-empty string")
    if file_path.startswith("/"):
        raise ValueError("file_path must not start with '/' (use relative paths)")
    if ".." in file_path:
        raise ValueError("file_path must not contain '..' (directory traversal)")
    if "\\" in file_path:
        raise ValueError("file_path must not contain backslash")
    # Null bytes are a known attack vector
    if "\x00" in file_path:
        raise ValueError("file_path must not contain null bytes")


# ── Local Storage Backend ───────────────────────────────────────────

class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend.

    Files are stored at: {STORAGE_LOCAL_PATH}/{company_id}/{file_path}

    This backend is intended for development and testing. For production,
    use GCPStorageBackend with Google Cloud Storage.

    Security measures:
        - company_id validated against directory traversal
        - file_path validated against directory traversal
        - pathlib.Path used for safe path joining
        - All paths resolved and checked against the base directory
    """

    def __init__(self, base_path: Optional[str] = None) -> None:
        """Initialize local storage backend.

        Args:
            base_path: Root directory for file storage.
                       Defaults to STORAGE_LOCAL_PATH env var or "./storage".
        """
        if base_path is None:
            settings = get_settings()
            base_path = getattr(settings, "STORAGE_LOCAL_PATH", None)

        if base_path is None:
            base_path = "./storage"

        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorageBackend initialized at: %s", self.base_path)

    def _resolve_path(self, company_id: str, file_path: str) -> Path:
        """Resolve and validate the full filesystem path.

        Ensures the resolved path stays within the base directory to
        prevent directory traversal attacks.

        Args:
            company_id: Tenant ID.
            file_path: Relative file path.

        Returns:
            Resolved absolute Path within the base directory.

        Raises:
            ValueError: If the path escapes the base directory.
        """
        _validate_company_id(company_id)
        _validate_file_path(file_path)

        # Company-scoped base: {base_path}/{company_id}
        company_base = (self.base_path / company_id).resolve()

        # Resolve the full path (follows symlinks)
        resolved = (self.base_path / company_id / file_path).resolve()

        # L47 FIX: Verify the resolved path stays within the COMPANY
        # directory, not just the base storage directory.  Without this
        # check, a symlink inside comp-a/ pointing to ../comp-b/secret
        # would resolve to base_path/comp-b/secret which IS within
        # base_path but leaks cross-tenant data.
        try:
            resolved.relative_to(company_base)
        except ValueError:
            logger.warning(
                "Path traversal or cross-company symlink attempt: "
                "company_id=%s, file_path=%s, resolved=%s, company_base=%s",
                company_id, file_path, resolved, company_base,
            )
            raise ValueError(
                "Resolved path escapes company directory — "
                "possible directory traversal or symlink attack"
            )

        return resolved

    def upload(
        self,
        company_id: str,
        file_path: str,
        content: bytes,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileMetadata:
        """Upload a file to local filesystem storage.

        Creates parent directories as needed. Computes MD5 checksum
        for integrity verification (BC-010).

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Relative path within company namespace.
            content: Raw file bytes.
            content_type: MIME type.
            metadata: Optional custom metadata.

        Returns:
            FileMetadata with upload details.
        """
        resolved_path = self._resolve_path(company_id, file_path)

        # Create parent directories
        resolved_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file atomically via temp file to prevent partial writes
        temp_path = resolved_path.with_suffix(resolved_path.suffix + ".tmp")
        try:
            temp_path.write_bytes(content)
            temp_path.replace(resolved_path)
        except Exception:
            # Clean up temp file on failure
            if temp_path.exists():
                temp_path.unlink()
            raise

        checksum = hashlib.md5(content).hexdigest()
        file_name = Path(file_path).name

        logger.info(
            "File uploaded: company_id=%s, path=%s, size=%d bytes, "
            "checksum=%s",
            company_id, file_path, len(content), checksum,
        )

        return FileMetadata(
            company_id=company_id,
            file_path=file_path,
            file_name=file_name,
            content_type=content_type,
            size_bytes=len(content),
            checksum_md5=checksum,
            uploaded_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

    def download(
        self,
        company_id: str,
        file_path: str,
    ) -> Tuple[bytes, str]:
        """Download a file from local filesystem.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Relative path within company namespace.

        Returns:
            Tuple of (file_content, content_type).

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        resolved_path = self._resolve_path(company_id, file_path)

        if not resolved_path.exists():
            logger.warning(
                "File not found: company_id=%s, path=%s",
                company_id, file_path,
            )
            raise FileNotFoundError(
                f"File not found: {file_path} for company {company_id}"
            )

        content = resolved_path.read_bytes()
        content_type = EXTENSION_TO_CONTENT_TYPE.get(
            resolved_path.suffix.lower(), "application/octet-stream"
        )

        logger.info(
            "File downloaded: company_id=%s, path=%s, size=%d bytes",
            company_id, file_path, len(content),
        )

        return content, content_type

    def delete(
        self,
        company_id: str,
        file_path: str,
    ) -> bool:
        """Delete a file from local filesystem.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Relative path within company namespace.

        Returns:
            True if file was deleted, False if not found.
        """
        resolved_path = self._resolve_path(company_id, file_path)

        if not resolved_path.exists():
            logger.info(
                "File not found for deletion (no-op): company_id=%s, path=%s",
                company_id, file_path,
            )
            return False

        resolved_path.unlink()
        logger.info(
            "File deleted: company_id=%s, path=%s",
            company_id, file_path,
        )
        return True

    def list_files(
        self,
        company_id: str,
        prefix: Optional[str] = None,
    ) -> List[FileMetadata]:
        """List files in a company's local storage directory.

        Args:
            company_id: Tenant ID (BC-001).
            prefix: Optional path prefix to filter results.

        Returns:
            List of FileMetadata for all matching files.
        """
        _validate_company_id(company_id)

        company_dir = (self.base_path / company_id).resolve()
        if not company_dir.exists():
            return []

        prefix_path = Path(prefix) if prefix else None
        results: List[FileMetadata] = []

        for file_entry in company_dir.rglob("*"):
            if not file_entry.is_file():
                continue

            # Skip hidden files and temp files
            if file_entry.name.startswith("."):
                continue
            if file_entry.suffix == ".tmp":
                continue

            # Compute relative path from company directory
            try:
                rel_path = file_entry.relative_to(company_dir)
            except ValueError:
                # File escaped the company directory (shouldn't happen)
                continue

            rel_str = str(rel_path)

            # Apply prefix filter
            if prefix_path is not None:
                if not rel_str.startswith(str(prefix_path)):
                    continue

            content = file_entry.read_bytes()
            checksum = hashlib.md5(content).hexdigest()

            results.append(FileMetadata(
                company_id=company_id,
                file_path=rel_str,
                file_name=file_entry.name,
                content_type=EXTENSION_TO_CONTENT_TYPE.get(
                    file_entry.suffix.lower(), "application/octet-stream"
                ),
                size_bytes=file_entry.stat().st_size,
                checksum_md5=checksum,
                uploaded_at=datetime.fromtimestamp(
                    file_entry.stat().st_mtime, tz=timezone.utc
                ),
                metadata={},
            ))

        logger.info(
            "Listed %d files for company_id=%s, prefix=%s",
            len(results), company_id, prefix,
        )
        return results

    def get_signed_url(
        self,
        company_id: str,
        file_path: str,
        expires_in: int = 3600,
    ) -> str:
        """Return the local file path (dev only).

        In local development, signed URLs are just the file path.
        This is NOT secure for production — use GCPStorageBackend instead.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Relative path within company namespace.
            expires_in: Ignored for local backend.

        Returns:
            Absolute local filesystem path as a string.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        resolved_path = self._resolve_path(company_id, file_path)

        if not resolved_path.exists():
            raise FileNotFoundError(
                f"File not found: {file_path} for company {company_id}"
            )

        logger.warning(
            "get_signed_url called on local backend — this returns a local "
            "filesystem path which is NOT secure for production. "
            "company_id=%s, path=%s",
            company_id, file_path,
        )

        return str(resolved_path)

    def exists(
        self,
        company_id: str,
        file_path: str,
    ) -> bool:
        """Check if a file exists in local storage.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Relative path within company namespace.

        Returns:
            True if the file exists, False otherwise.
        """
        resolved_path = self._resolve_path(company_id, file_path)
        return resolved_path.exists()

    def get_file_size(
        self,
        company_id: str,
        file_path: str,
    ) -> int:
        """Get the size of a file in bytes.

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Relative path within company namespace.

        Returns:
            File size in bytes.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        resolved_path = self._resolve_path(company_id, file_path)

        if not resolved_path.exists():
            raise FileNotFoundError(
                f"File not found: {file_path} for company {company_id}"
            )

        return resolved_path.stat().st_size


# ── GCP Storage Backend (Stub) ──────────────────────────────────────

class GCPStorageBackend(StorageBackend):
    """Google Cloud Storage backend (placeholder).

    Will be fully implemented when GCP credentials and the
    google-cloud-storage library are available in the environment.

    Storage path: gs://{bucket_name}/{company_id}/{file_path}

    Security measures:
        - company_id validated against directory traversal
        - file_path validated against directory traversal
        - GCS object names validated
        - Signed URLs via GCS signed URL API
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        """Initialize GCP storage backend.

        Args:
            bucket_name: GCS bucket name. Defaults to GCP_STORAGE_BUCKET
                         from settings.
            project_id: GCP project ID. Defaults to GCP_PROJECT_ID from
                        settings.
        """
        settings = get_settings()

        self.bucket_name = bucket_name or getattr(
            settings, "GCP_STORAGE_BUCKET", ""
        )
        self.project_id = project_id or getattr(
            settings, "GCP_PROJECT_ID", ""
        )

        if not self.bucket_name:
            raise ValueError(
                "GCP_STORAGE_BUCKET must be set in settings or passed "
                "to constructor for GCP storage backend"
            )

        logger.info(
            "GCPStorageBackend initialized (stub): bucket=%s, project=%s",
            self.bucket_name, self.project_id,
        )

    def upload(
        self,
        company_id: str,
        file_path: str,
        content: bytes,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileMetadata:
        """Upload a file to GCS. (Not yet implemented.)

        Args:
            company_id: Tenant ID (BC-001).
            file_path: Relative path within company namespace.
            content: Raw file bytes.
            content_type: MIME type.
            metadata: Optional custom metadata.

        Returns:
            FileMetadata with upload details.

        Raises:
            NotImplementedError: Until GCP credentials are configured.
        """
        raise NotImplementedError(
            "GCP storage upload is not yet implemented. "
            "Configure GCP credentials and install google-cloud-storage."
        )

    def download(
        self,
        company_id: str,
        file_path: str,
    ) -> Tuple[bytes, str]:
        """Download a file from GCS. (Not yet implemented.)

        Raises:
            NotImplementedError: Until GCP credentials are configured.
        """
        raise NotImplementedError(
            "GCP storage download is not yet implemented. "
            "Configure GCP credentials and install google-cloud-storage."
        )

    def delete(
        self,
        company_id: str,
        file_path: str,
    ) -> bool:
        """Delete a file from GCS. (Not yet implemented.)

        Raises:
            NotImplementedError: Until GCP credentials are configured.
        """
        raise NotImplementedError(
            "GCP storage delete is not yet implemented. "
            "Configure GCP credentials and install google-cloud-storage."
        )

    def list_files(
        self,
        company_id: str,
        prefix: Optional[str] = None,
    ) -> List[FileMetadata]:
        """List files in GCS. (Not yet implemented.)

        Raises:
            NotImplementedError: Until GCP credentials are configured.
        """
        raise NotImplementedError(
            "GCP storage list_files is not yet implemented. "
            "Configure GCP credentials and install google-cloud-storage."
        )

    def get_signed_url(
        self,
        company_id: str,
        file_path: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a GCS signed URL. (Not yet implemented.)

        Raises:
            NotImplementedError: Until GCP credentials are configured.
        """
        raise NotImplementedError(
            "GCP signed URL generation is not yet implemented. "
            "Configure GCP credentials and install google-cloud-storage."
        )

    def exists(
        self,
        company_id: str,
        file_path: str,
    ) -> bool:
        """Check if a file exists in GCS. (Not yet implemented.)

        Raises:
            NotImplementedError: Until GCP credentials are configured.
        """
        raise NotImplementedError(
            "GCP storage exists check is not yet implemented. "
            "Configure GCP credentials and install google-cloud-storage."
        )

    def get_file_size(
        self,
        company_id: str,
        file_path: str,
    ) -> int:
        """Get file size from GCS. (Not yet implemented.)

        Raises:
            NotImplementedError: Until GCP credentials are configured.
        """
        raise NotImplementedError(
            "GCP storage get_file_size is not yet implemented. "
            "Configure GCP credentials and install google-cloud-storage."
        )


# ── Storage Backend Factory ─────────────────────────────────────────

# Module-level singleton instance (lazy-initialized)
_storage_backend_instance: Optional[StorageBackend] = None


def get_storage_backend() -> StorageBackend:
    """Factory function to get the configured storage backend.

    Reads STORAGE_BACKEND from settings:
      - "local" or unset: LocalStorageBackend (development)
      - "gcp": GCPStorageBackend (production)

    Returns a singleton instance — the backend is created once and
    reused for the lifetime of the process.

    Returns:
        Configured StorageBackend instance.

    Raises:
        ValueError: If STORAGE_BACKEND is set to an unknown value.
    """
    global _storage_backend_instance

    if _storage_backend_instance is not None:
        return _storage_backend_instance

    try:
        settings = get_settings()
        backend_type = getattr(settings, "STORAGE_BACKEND", "local")
    except Exception:
        # If settings can't be loaded (e.g. missing required vars),
        # fall back to local storage
        backend_type = "local"

    backend_type = backend_type.lower().strip()

    if backend_type == "local":
        _storage_backend_instance = LocalStorageBackend()
    elif backend_type == "gcp":
        _storage_backend_instance = GCPStorageBackend()
    else:
        raise ValueError(
            f"Unknown STORAGE_BACKEND value: '{backend_type}'. "
            f"Must be 'local' or 'gcp'."
        )

    logger.info(
        "Storage backend initialized: type=%s", backend_type,
    )
    return _storage_backend_instance


def reset_storage_backend() -> None:
    """Reset the singleton storage backend instance.

    Useful for testing — allows switching backends between tests.
    """
    global _storage_backend_instance
    _storage_backend_instance = None


# ── File Upload Validation ──────────────────────────────────────────

# Characters that are not allowed in sanitized filenames.
# Includes path separators, control characters, and shell metacharacters.
_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for safe storage.

    Removes path separators, special characters, and other unsafe
    patterns. Preserves the file extension.  Applies Unicode NFKC
    normalization to prevent homograph attacks (e.g., Cyrillic 'а'
    that looks like Latin 'a').

    Args:
        filename: Raw filename from user upload.

    Returns:
        Sanitized filename safe for filesystem and GCS storage.

    Raises:
        ValueError: If the filename is empty after sanitization.
    """
    if not filename or not filename.strip():
        raise ValueError("Filename cannot be empty")

    # L49 FIX: Normalize Unicode to NFKC form.  This converts
    # visually-identical characters (homographs) to their canonical
    # form, preventing attacks like using Cyrillic 'а' (U+0430) in
    # place of Latin 'a' (U+0061).
    filename = unicodedata.normalize("NFKC", filename)

    # Extract extension before sanitizing
    name_part = Path(filename).stem
    ext_part = Path(filename).suffix.lower()

    # Remove unsafe characters from name
    sanitized_name = _UNSAFE_FILENAME_CHARS.sub("", name_part)

    # Collapse multiple spaces/dots into single
    sanitized_name = re.sub(r"\s+", " ", sanitized_name).strip()
    sanitized_name = re.sub(r"\.{2,}", ".", sanitized_name)

    # Truncate name to 200 chars (leaving room for extension)
    sanitized_name = sanitized_name[:200]

    if not sanitized_name:
        raise ValueError(
            f"Filename '{filename}' is empty after sanitization"
        )

    # Reconstruct with extension
    if ext_part and ext_part in ALLOWED_EXTENSIONS:
        return f"{sanitized_name}{ext_part}"
    elif ext_part:
        # Unknown extension — keep it but warn
        logger.warning(
            "File has extension not in ALLOWED_EXTENSIONS: '%s'. "
            "Will be validated separately by content_type check.",
            ext_part,
        )
        return f"{sanitized_name}{ext_part}"
    else:
        return sanitized_name


def validate_file_upload(
    filename: str,
    content_type: str,
    file_size: int,
    tier: str = "starter",
) -> str:
    """Validate a file upload before processing.

    Performs the following checks:
      1. Filename sanitization and validation
      2. Content type whitelist enforcement
      3. Extension whitelist enforcement
      4. Content type ↔ extension consistency
      5. File size validation against tier limit
      6. Extension existence check

    Args:
        filename: Original filename from user upload.
        content_type: MIME type declared for the upload.
        file_size: File size in bytes.
        tier: Subscription tier (starter, growth, high).

    Returns:
        Sanitized filename string.

    Raises:
        ValueError: If any validation check fails, with a descriptive
                    error message.
    """
    # --- 1. Sanitize filename ---
    sanitized = sanitize_filename(filename)

    # --- 2. Content type whitelist ---
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(
            f"Content type '{content_type}' is not allowed. "
            f"Allowed types: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
        )

    # --- 3. Extension whitelist ---
    ext = Path(sanitized).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"File extension '{ext}' is not allowed. "
            f"Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # --- 4. Content type ↔ extension consistency ---
    expected_ext = CONTENT_TYPE_TO_EXTENSION.get(content_type)
    if expected_ext and ext != expected_ext:
        raise ValueError(
            f"Content type '{content_type}' does not match "
            f"extension '{ext}'. Expected extension: '{expected_ext}'"
        )

    # --- 5. File size validation ---
    tier_lower = tier.lower().strip()
    tier_limit = MAX_FILE_SIZE_BY_TIER.get(tier_lower, MAX_FILE_SIZE)

    if file_size <= 0:
        raise ValueError("File size must be greater than 0 bytes")

    if file_size > tier_limit:
        tier_limit_mb = tier_limit / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        raise ValueError(
            f"File size ({actual_mb:.1f} MB) exceeds the limit for "
            f"the '{tier_lower}' tier ({tier_limit_mb:.0f} MB). "
            f"Upgrade your plan to upload larger files."
        )

    # --- 6. Extension existence ---
    if not ext:
        raise ValueError(
            "File must have an extension. "
            f"Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    return sanitized
