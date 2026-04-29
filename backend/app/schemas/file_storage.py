"""
PARWA File Storage Schemas

Pydantic models for file upload request/response payloads.
These are the public-facing schemas used by API endpoints.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FileUploadRequest(BaseModel):
    """Metadata for a file upload request.

    Used when the client sends file metadata alongside the
    actual file content (e.g., via multipart form data).
    """

    content_type: str = Field(
        description="MIME type of the uploaded file.",
    )
    tier: str = Field(
        default="mini_parwa",
        description="Subscription tier for file size limits (starter/growth/high).",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional custom metadata key-value pairs.",
    )


class FileUploadResponse(BaseModel):
    """Response returned after a successful file upload."""

    id: str = Field(description="Unique file identifier (UUID).")
    company_id: str = Field(description="Tenant ID that owns the file.")
    file_path: str = Field(
        description="Logical storage path within the backend.")
    file_name: str = Field(description="Sanitized file name.")
    original_filename: Optional[str] = Field(
        default=None,
        description="Original filename before sanitization.",
    )
    content_type: str = Field(description="MIME type of the stored file.")
    size_bytes: int = Field(description="File size in bytes.")
    checksum_md5: str = Field(
        description="MD5 checksum for integrity verification.")
    uploaded_at: Optional[str] = Field(
        default=None,
        description="ISO-8601 upload timestamp.",
    )
    uploaded_by: Optional[str] = Field(
        default=None,
        description="ID of the user who uploaded the file.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata key-value pairs.",
    )


class FileMetadataResponse(BaseModel):
    """Response with file metadata (no content)."""

    company_id: str
    file_path: str
    file_name: str
    content_type: str
    size_bytes: int
    checksum_md5: str
    uploaded_at: Optional[str] = None
    exists: bool = True


class FileListResponse(BaseModel):
    """Paginated list of files."""

    items: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of file metadata dicts.",
    )
    total: int = Field(description="Total number of files.")
    offset: int = Field(description="Applied pagination offset.")
    limit: int = Field(description="Applied pagination limit.")


class FileDownloadResponse(BaseModel):
    """Response for file download requests."""

    content: bytes = Field(description="Raw file bytes.")
    content_type: str = Field(description="MIME type of the file.")
    file_id: str = Field(description="File identifier.")
    company_id: str = Field(description="Tenant ID.")


class FileValidationResponse(BaseModel):
    """Response from file validation check."""

    is_valid: bool
    sanitized_filename: Optional[str] = None
    error: Optional[str] = None
    max_size_bytes: Optional[int] = None
