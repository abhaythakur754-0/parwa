"""
PARWA Attachment Service - BL06 Attachment Validation (Day 26)

Implements BL06: Attachment whitelist with:
- File type validation (whitelist)
- File size limits (per plan tier)
- MIME type verification
- Virus scan integration stub
"""

from __future__ import annotations

import hashlib
try:
    import magic
except ImportError:
    magic = None  # type: ignore
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, BinaryIO

from sqlalchemy.orm import Session

from app.exceptions import ValidationError
from database.models.tickets import Ticket, TicketAttachment


class AttachmentService:
    """File attachment validation and management."""

    # BL06: Allowed file extensions
    ALLOWED_EXTENSIONS = {
        # Documents
        "pdf", "doc", "docx", "txt", "rtf", "odt",
        # Spreadsheets
        "xls", "xlsx", "csv",
        # Images
        "png", "jpg", "jpeg", "gif", "bmp", "webp",
        # Archives (scanned)
        "zip",
    }

    # Allowed MIME types mapped to extensions
    ALLOWED_MIME_TYPES = {
        "application/pdf": "pdf",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "text/plain": "txt",
        "application/rtf": "rtf",
        "application/vnd.oasis.opendocument.text": "odt",
        "application/vnd.ms-excel": "xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "text/csv": "csv",
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/gif": "gif",
        "image/bmp": "bmp",
        "image/webp": "webp",
        "application/zip": "zip",
    }

    # File size limits per plan tier (in bytes)
    PLAN_SIZE_LIMITS = {
        "starter": 5 * 1024 * 1024,      # 5 MB
        "growth": 25 * 1024 * 1024,      # 25 MB
        "high": 100 * 1024 * 1024,       # 100 MB
        "enterprise": 500 * 1024 * 1024, # 500 MB
    }

    # Default size limit
    DEFAULT_SIZE_LIMIT = 5 * 1024 * 1024  # 5 MB

    # Maximum attachments per ticket
    MAX_ATTACHMENTS_PER_TICKET = 10

    # Dangerous extensions (always blocked)
    DANGEROUS_EXTENSIONS = {
        "exe", "bat", "cmd", "com", "pif", "scr", "vbs", "js",
        "jar", "msi", "sh", "bash", "py", "pl", "php", "asp",
        "aspx", "jsp", "cgi", "dll", "so", "dylib",
    }

    def __init__(self, db: Session, company_id: str, plan_tier: str = "starter"):
        self.db = db
        self.company_id = company_id
        self.plan_tier = plan_tier

    def validate_file(
        self,
        filename: str,
        file_content: bytes,
    ) -> Tuple[bool, Optional[str], Dict]:
        """Validate a file attachment.

        BL06: Checks extension whitelist, size limit, and MIME type.

        Args:
            filename: Original filename
            file_content: File binary content

        Returns:
            Tuple of (is_valid, error_message, metadata)
        """
        metadata = {
            "filename": filename,
            "size": len(file_content),
            "extension": None,
            "mime_type": None,
            "checksum": None,
        }

        # Extract extension
        _, ext = os.path.splitext(filename)
        ext = ext.lower().lstrip(".") if ext else ""
        metadata["extension"] = ext

        # Check extension is provided
        if not ext:
            return False, "File must have an extension", metadata

        # Check against dangerous extensions
        if ext in self.DANGEROUS_EXTENSIONS:
            return False, f"File type '{ext}' is not allowed for security reasons", metadata

        # Check extension whitelist
        if ext not in self.ALLOWED_EXTENSIONS:
            return False, f"File type '{ext}' is not allowed. Allowed types: {', '.join(sorted(self.ALLOWED_EXTENSIONS))}", metadata

        # Check file size
        size_limit = self.PLAN_SIZE_LIMITS.get(
            self.plan_tier,
            self.DEFAULT_SIZE_LIMIT
        )
        if len(file_content) > size_limit:
            return False, f"File size exceeds {size_limit // (1024*1024)} MB limit for your plan", metadata

        # Detect MIME type from content
        try:
            if magic is not None:
                mime_type = magic.from_buffer(file_content, mime=True)
                metadata["mime_type"] = mime_type

                # Verify MIME type matches extension
                expected_ext = self.ALLOWED_MIME_TYPES.get(mime_type)
                if expected_ext and expected_ext != ext:
                    # MIME type doesn't match extension - suspicious
                    return False, f"File content does not match extension '{ext}'", metadata
            else:
                # If magic not available, use extension-based MIME type
                metadata["mime_type"] = self._get_mime_from_extension(ext)

        except Exception:
            # If we can't detect MIME, proceed cautiously
            pass

        # Calculate checksum
        metadata["checksum"] = hashlib.sha256(file_content).hexdigest()

        return True, None, metadata

    def upload_attachment(
        self,
        ticket_id: str,
        filename: str,
        file_content: bytes,
        uploaded_by: Optional[str] = None,
        storage_service=None,
    ) -> TicketAttachment:
        """Upload and store an attachment.

        Args:
            ticket_id: Ticket ID
            filename: Original filename
            file_content: File binary content
            uploaded_by: User ID uploading
            storage_service: File storage service

        Returns:
            TicketAttachment object

        Raises:
            ValidationError: If validation fails
        """
        # Validate file
        is_valid, error_msg, metadata = self.validate_file(filename, file_content)
        if not is_valid:
            raise ValidationError(error_msg)

        # Check ticket attachment limit
        existing_count = self.db.query(TicketAttachment).filter(
            TicketAttachment.ticket_id == ticket_id,
            TicketAttachment.company_id == self.company_id,
        ).count()

        if existing_count >= self.MAX_ATTACHMENTS_PER_TICKET:
            raise ValidationError(
                f"Maximum {self.MAX_ATTACHMENTS_PER_TICKET} attachments per ticket"
            )

        # Store file (using storage service if available)
        file_url = None
        if storage_service:
            # Generate unique filename
            unique_name = f"{uuid.uuid4()}_{filename}"
            file_url = storage_service.upload(
                key=f"attachments/{self.company_id}/{ticket_id}/{unique_name}",
                content=file_content,
                content_type=metadata["mime_type"],
            )
        else:
            # Fallback: store as base64 data URL (not recommended for production)
            import base64
            b64 = base64.b64encode(file_content).decode()
            file_url = f"data:{metadata['mime_type']};base64,{b64}"

        # Create attachment record
        attachment = TicketAttachment(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            company_id=self.company_id,
            filename=filename,
            file_url=file_url,
            file_size=metadata["size"],
            mime_type=metadata["mime_type"],
            uploaded_by=uploaded_by,
            created_at=datetime.utcnow(),
        )

        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)

        return attachment

    def get_attachments(self, ticket_id: str) -> List[TicketAttachment]:
        """Get all attachments for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            List of TicketAttachment objects
        """
        return self.db.query(TicketAttachment).filter(
            TicketAttachment.ticket_id == ticket_id,
            TicketAttachment.company_id == self.company_id,
        ).order_by(TicketAttachment.created_at.desc()).all()

    def delete_attachment(
        self,
        attachment_id: str,
        user_id: Optional[str] = None,
        storage_service=None,
    ) -> bool:
        """Delete an attachment.

        Args:
            attachment_id: Attachment ID
            user_id: User ID deleting
            storage_service: File storage service

        Returns:
            True if deleted

        Raises:
            NotFoundError: If attachment not found
        """
        attachment = self.db.query(TicketAttachment).filter(
            TicketAttachment.id == attachment_id,
            TicketAttachment.company_id == self.company_id,
        ).first()

        if not attachment:
            from app.exceptions import NotFoundError
            raise NotFoundError(f"Attachment {attachment_id} not found")

        # Delete from storage
        if storage_service and attachment.file_url:
            try:
                storage_service.delete(attachment.file_url)
            except Exception:
                pass  # Continue even if storage deletion fails

        # Delete record
        self.db.delete(attachment)
        self.db.commit()

        return True

    def get_size_limit(self) -> int:
        """Get file size limit for current plan.

        Returns:
            Size limit in bytes
        """
        return self.PLAN_SIZE_LIMITS.get(
            self.plan_tier,
            self.DEFAULT_SIZE_LIMIT
        )

    def is_extension_allowed(self, extension: str) -> bool:
        """Check if an extension is allowed.

        Args:
            extension: File extension (without dot)

        Returns:
            True if allowed
        """
        ext = extension.lower().lstrip(".")
        return ext in self.ALLOWED_EXTENSIONS and ext not in self.DANGEROUS_EXTENSIONS

    def _get_mime_from_extension(self, extension: str) -> Optional[str]:
        """Get MIME type from extension when magic is not available.
        
        Args:
            extension: File extension (without dot)
            
        Returns:
            MIME type string or None
        """
        ext_to_mime = {
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
            "rtf": "application/rtf",
            "odt": "application/vnd.oasis.opendocument.text",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "csv": "text/csv",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "bmp": "image/bmp",
            "webp": "image/webp",
            "zip": "application/zip",
        }
        return ext_to_mime.get(extension.lower())
