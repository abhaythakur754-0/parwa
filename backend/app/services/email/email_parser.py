"""
PARWA Email Parser Service — Day 5 (Email Deep + Email MCP Server)

Parses inbound HTML emails into clean text, tracks conversation threads
via In-Reply-To / References headers, extracts attachments with
tenant-scoped storage, and strips quoted replies and signatures.

Building Codes:
- BC-001: All operations scoped by company_id (multi-tenant isolation)
- BC-008: Never crash — all exceptions caught, return error dicts
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger("parwa.email_parser")

# ── Signature Detection Patterns ─────────────────────────────────

# Lines that typically start an email signature block
SIGNATURE_START_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^--\s*$", re.MULTILINE),            # Standard sig separator
    re.compile(r"^—\s*$", re.MULTILINE),              # Em-dash separator
    re.compile(r"^\s*--\s*$", re.MULTILINE),          # Whitespace-padded separator
    re.compile(
        r"^\s*(?:best\s+regards|regards|sincerely|cheers|warmly|"
        r"kind\s+regards|yours\s+truly|respectfully|thank\s*you|"
        r"thanks|thx|with\s+gratitude|cordially)",
        re.IGNORECASE | re.MULTILINE,
    ),
]

# "On ... wrote:" separator — marks start of quoted reply
ON_WROTE_PATTERN = re.compile(
    r"^\s*On\s+.+\s+wrote\s*:\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Lines starting with ">" — quoted reply text
QUOTED_LINE_PATTERN = re.compile(r"^>\s?", re.MULTILINE)

# ── Attachment Support ───────────────────────────────────────────

# Supported image MIME types and their file extensions
IMAGE_EXTENSIONS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
}

# Supported document MIME types and their file extensions
DOCUMENT_EXTENSIONS: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
}

# All supported content types combined
SUPPORTED_CONTENT_TYPES: dict[str, str] = {**IMAGE_EXTENSIONS, **DOCUMENT_EXTENSIONS}

# Base directory for email attachment storage
ATTACHMENT_BASE_DIR = "/tmp/parwa_uploads"


class EmailParser:
    """Parse inbound HTML emails into clean text, track threads, and
    extract attachments.

    All operations are scoped by ``company_id`` (BC-001) and are
    resilient to malformed input (BC-008).
    """

    # ── HTML Parsing ─────────────────────────────────────────────

    def parse_html_email(self, html_content: str) -> dict:
        """Extract clean text from an HTML email using BeautifulSoup.

        Preserves meaningful formatting (bold, italic, links as text),
        strips inline images, scripts, and styles, then collapses
        whitespace for a readable plain-text representation.

        Args:
            html_content: Raw HTML email body.

        Returns:
            Dict with keys:
            - status: ``"ok"`` or ``"error"``
            - text: Cleaned plain-text string (``""`` on error)
            - links: List of dicts with ``href`` and ``text`` for links found
            - has_images: Whether the email contained ``<img>`` tags
            - error: Error message if status is ``"error"``
        """
        if not html_content:
            return {
                "status": "ok",
                "text": "",
                "links": [],
                "has_images": False,
            }

        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove script and style elements
            for tag in soup.find_all(["script", "style", "head"]):
                tag.decompose()

            # Collect links before stripping tags
            links: list[dict[str, str]] = []
            for a_tag in soup.find_all("a", href=True):
                link_text = a_tag.get_text(strip=True) or a_tag["href"]
                links.append({"href": a_tag["href"], "text": link_text})

            # Check for images
            has_images = bool(soup.find_all("img"))

            # Preserve bold/italic as text markers by replacing tags
            # inline so markers stay on the same line as content
            for tag in soup.find_all(["strong", "b"]):
                inner = tag.get_text()
                tag.replace_with(f"**{inner}**")
            for tag in soup.find_all(["em", "i"]):
                inner = tag.get_text()
                tag.replace_with(f"_{inner}_")

            # Convert links to inline text: "text (url)"
            for a_tag in soup.find_all("a", href=True):
                link_text = a_tag.get_text(strip=True)
                href = a_tag["href"]
                if link_text and link_text != href:
                    replacement = f"{link_text} ({href})"
                else:
                    replacement = href
                a_tag.replace_with(replacement)

            # Get text content
            text = soup.get_text(separator="\n")

            # Collapse multiple blank lines into at most two newlines
            text = re.sub(r"\n{3,}", "\n\n", text)

            # Strip leading/trailing whitespace per line
            lines = [line.strip() for line in text.splitlines()]
            text = "\n".join(lines)

            # Remove leading/trailing blank lines
            text = text.strip()

            return {
                "status": "ok",
                "text": text,
                "links": links,
                "has_images": has_images,
            }

        except Exception as exc:
            logger.error(
                "email_parse_html_failed",
                extra={"error": str(exc)[:200]},
            )
            return {
                "status": "error",
                "text": "",
                "links": [],
                "has_images": False,
                "error": str(exc)[:500],
            }

    # ── Thread Tracking ──────────────────────────────────────────

    def track_thread(
        self,
        message_id: str,
        in_reply_to: Optional[str],
        references: Optional[str],
        company_id: str,
    ) -> dict:
        """Track conversation threads via In-Reply-To / References headers.

        Groups related emails by thread.  If ``in_reply_to`` or
        ``references`` are present, they are used to derive a stable
        ``thread_id``.  Otherwise a new thread is created.

        Args:
            message_id: RFC 2822 Message-ID of the current email.
            in_reply_to: The In-Reply-To header value (parent Message-ID).
            references: Space-separated chain of ancestor Message-IDs.
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with keys:
            - status: ``"ok"`` or ``"error"``
            - thread_id: Stable thread identifier (UUID-based)
            - message_ids: Ordered list of Message-IDs in the thread
            - is_new_thread: Whether this is a brand-new thread
            - error: Error message if status is ``"error"``
        """
        try:
            # Parse existing message IDs from References header
            existing_ids: list[str] = []
            if references:
                existing_ids = self._parse_references(references)

            # Determine thread root — earliest known Message-ID
            if in_reply_to:
                in_reply_to = in_reply_to.strip().strip("<>")
                if in_reply_to not in existing_ids:
                    existing_ids.insert(0, in_reply_to)

            # Derive a stable thread_id from the earliest message
            is_new_thread = len(existing_ids) == 0
            if existing_ids:
                thread_root = existing_ids[0]
                # Create a deterministic thread_id from the root Message-ID
                # so that the same thread always gets the same thread_id
                thread_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"parwa:{company_id}:{thread_root}"))
            else:
                # Brand-new thread — generate a fresh thread_id
                thread_id = str(uuid.uuid4())

            # Append current message_id to the chain
            clean_msg_id = message_id.strip().strip("<>") if message_id else ""
            if clean_msg_id and clean_msg_id not in existing_ids:
                existing_ids.append(clean_msg_id)

            return {
                "status": "ok",
                "thread_id": thread_id,
                "message_ids": existing_ids,
                "is_new_thread": is_new_thread,
            }

        except Exception as exc:
            logger.error(
                "email_track_thread_failed",
                extra={
                    "company_id": company_id,
                    "message_id": message_id,
                    "error": str(exc)[:200],
                },
            )
            return {
                "status": "error",
                "thread_id": None,
                "message_ids": [],
                "is_new_thread": True,
                "error": str(exc)[:500],
            }

    # ── Attachment Extraction ────────────────────────────────────

    def extract_attachments(
        self,
        email_data: dict,
        company_id: str,
    ) -> dict:
        """Extract attachments from a parsed email.

        Supports images (jpg, png, gif), PDFs, and documents (doc,
        docx, txt).  Files are stored in a tenant-scoped directory.

        Args:
            email_data: Dict with key ``attachments`` — a list of
                dicts each containing ``filename``, ``content_type``,
                ``content`` (bytes or base64 string), and optionally
                ``size``.
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with keys:
            - status: ``"ok"`` or ``"error"``
            - attachments: List of dicts with ``filename``,
              ``content_type``, ``size``, ``storage_path``
            - skipped: List of attachment filenames that were skipped
              (unsupported type, missing data, etc.)
            - error: Error message if status is ``"error"``
        """
        try:
            raw_attachments = email_data.get("attachments", [])
            if not raw_attachments or not isinstance(raw_attachments, list):
                return {
                    "status": "ok",
                    "attachments": [],
                    "skipped": [],
                }

            # Ensure tenant-scoped directory exists
            attachment_dir = os.path.join(
                ATTACHMENT_BASE_DIR,
                company_id,
                "email_attachments",
            )
            os.makedirs(attachment_dir, exist_ok=True)

            saved: list[dict[str, str | int]] = []
            skipped: list[str] = []

            for att in raw_attachments:
                if not isinstance(att, dict):
                    continue

                filename = att.get("filename", "")
                content_type = att.get("content_type", "")
                content = att.get("content", b"")
                size = att.get("size", 0)

                # Skip empty attachments
                if not content:
                    skipped.append(filename or "(unnamed)")
                    continue

                # Validate content type
                if content_type and content_type not in SUPPORTED_CONTENT_TYPES:
                    # Try inferring from filename extension
                    inferred = self._infer_content_type(filename)
                    if inferred:
                        content_type = inferred
                    else:
                        skipped.append(filename or "(unsupported type)")
                        continue

                # If no content_type but we have a filename, try to infer
                if not content_type and filename:
                    content_type = self._infer_content_type(filename) or ""

                # Determine extension
                ext = SUPPORTED_CONTENT_TYPES.get(content_type, "")
                if not ext and filename:
                    _, ext = os.path.splitext(filename)

                # Generate a unique filename to avoid collisions
                safe_name = self._sanitize_filename(filename)
                unique_id = str(uuid.uuid4())[:8]
                base_name, file_ext = os.path.splitext(safe_name)
                if not file_ext and ext:
                    file_ext = ext
                storage_filename = f"{base_name}_{unique_id}{file_ext}"

                storage_path = os.path.join(attachment_dir, storage_filename)

                # Write file to disk
                try:
                    if isinstance(content, bytes):
                        file_bytes = content
                    elif isinstance(content, str):
                        # Assume base64-encoded content
                        import base64

                        file_bytes = base64.b64decode(content)
                    else:
                        skipped.append(filename or "(invalid content)")
                        continue

                    with open(storage_path, "wb") as f:
                        f.write(file_bytes)

                    actual_size = len(file_bytes)

                    saved.append({
                        "filename": filename or storage_filename,
                        "content_type": content_type,
                        "size": size or actual_size,
                        "storage_path": storage_path,
                    })

                except Exception as write_exc:
                    logger.warning(
                        "email_attachment_write_failed",
                        extra={
                            "company_id": company_id,
                            "filename": filename,
                            "error": str(write_exc)[:200],
                        },
                    )
                    skipped.append(filename or "(write error)")

            return {
                "status": "ok",
                "attachments": saved,
                "skipped": skipped,
            }

        except Exception as exc:
            logger.error(
                "email_extract_attachments_failed",
                extra={
                    "company_id": company_id,
                    "error": str(exc)[:200],
                },
            )
            return {
                "status": "error",
                "attachments": [],
                "skipped": [],
                "error": str(exc)[:500],
            }

    # ── Quoted Reply Stripping ───────────────────────────────────

    def strip_quoted_reply(self, text: str) -> str:
        """Remove quoted reply text and common separators.

        Strips lines starting with ``">"`` and removes the common
        ``"On ... wrote:"`` separator line along with everything
        after it.

        Args:
            text: Plain-text email body.

        Returns:
            Cleaned text with quoted replies removed.
        """
        if not text:
            return ""

        try:
            # Remove "On ... wrote:" separator and everything after
            # This is the most common pattern for email clients
            match = ON_WROTE_PATTERN.search(text)
            if match:
                text = text[: match.start()]

            # Remove lines starting with ">"
            lines = text.splitlines()
            cleaned_lines: list[str] = []
            for line in lines:
                if QUOTED_LINE_PATTERN.match(line):
                    continue
                cleaned_lines.append(line)

            text = "\n".join(cleaned_lines)

            # Remove trailing whitespace and blank lines
            text = text.strip()

            # Collapse multiple blank lines
            text = re.sub(r"\n{3,}", "\n\n", text)

            return text

        except Exception as exc:
            logger.warning(
                "email_strip_quoted_reply_failed",
                extra={"error": str(exc)[:200]},
            )
            return text  # Return original on error (BC-008)

    # ── Signature Detection ──────────────────────────────────────

    def detect_email_signature(self, text: str) -> tuple[str, str]:
        """Split body text from email signature.

        Detects common signature patterns (``"--"``, ``"Best regards"``,
        ``"Regards"``, ``"Sincerely"``, etc.) and returns the body
        and signature as separate strings.

        Args:
            text: Plain-text email body (preferably after quoted-reply
                stripping).

        Returns:
            Tuple of ``(body, signature)``.  If no signature is
            detected, ``signature`` is an empty string.
        """
        if not text:
            return ("", "")

        try:
            lines = text.splitlines()
            sig_start_index: Optional[int] = None

            for i, line in enumerate(lines):
                # Check against all signature start patterns
                for pattern in SIGNATURE_START_PATTERNS:
                    if pattern.search(line):
                        sig_start_index = i
                        break
                if sig_start_index is not None:
                    break

            if sig_start_index is None:
                return (text, "")

            body = "\n".join(lines[:sig_start_index]).strip()
            signature = "\n".join(lines[sig_start_index:]).strip()

            return (body, signature)

        except Exception as exc:
            logger.warning(
                "email_detect_signature_failed",
                extra={"error": str(exc)[:200]},
            )
            return (text, "")  # Return original body on error (BC-008)

    # ── Private Helpers ──────────────────────────────────────────

    def _parse_references(self, references: str) -> list[str]:
        """Parse the References header into a list of Message-IDs.

        Handles angle-bracket-wrapped IDs and whitespace-separated
        bare IDs.

        Args:
            references: The References header value.

        Returns:
            Ordered list of Message-ID strings (without angle brackets).
        """
        if not references:
            return []

        # Extract Message-IDs from angle brackets
        ids = re.findall(r"<([^>]+)>", references)
        if ids:
            return ids

        # Fallback: split by whitespace
        return [r.strip() for r in references.split() if r.strip()]

    @staticmethod
    def _infer_content_type(filename: str) -> str:
        """Infer MIME content type from a filename extension.

        Args:
            filename: Filename to infer type from.

        Returns:
            MIME type string, or empty string if unknown.
        """
        if not filename:
            return ""

        _, ext = os.path.splitext(filename.lower())
        extension_map: dict[str, str] = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
        }
        return extension_map.get(ext, "")

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Sanitize a filename for safe filesystem storage.

        Removes path traversal attempts and problematic characters.

        Args:
            filename: Raw filename string.

        Returns:
            Sanitized filename string.
        """
        if not filename:
            return "unnamed_attachment"

        # Remove any path components
        filename = os.path.basename(filename)

        # Replace problematic characters
        filename = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", filename)

        # Limit length
        name, ext = os.path.splitext(filename)
        if len(name) > 200:
            name = name[:200]
        filename = name + ext

        return filename or "unnamed_attachment"
