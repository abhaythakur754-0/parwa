"""
Document parsing for KB uploads — MarkItDown (Microsoft), optional.

Fixes: the upload endpoint decodes PDF/DOCX bytes with UTF-8 'replace',
which produces mangled garbage for binary formats. This module returns
clean text for PDF/DOCX/XLSX/PPT/HTML and falls back to plain UTF-8 for
text formats (txt/md/csv/json).
"""

from __future__ import annotations

import importlib.util
import logging
import os
from typing import Optional

logger = logging.getLogger("parwa.oss.docparse")

_TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".html", ".htm", ".xml", ".log"}
_BINARY_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"}


def is_available() -> bool:
    try:
        if importlib.util.find_spec("markitdown") is None:
            return False
        return os.environ.get("OSS_DOCPARSE", "1").strip() in ("1", "true", "yes", "on")
    except Exception:
        return False


def parse(filename: str, content: bytes) -> Optional[str]:
    """Convert uploaded bytes to clean text.

    Returns None only when parsing is impossible AND the file is binary
    (caller should then reject with a clear message instead of storing junk).
    For text extensions, always falls back to UTF-8 decode.
    """
    name = (filename or "").lower()
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""

    if ext in _BINARY_EXTENSIONS and not is_available():
        # Binary format but no parser — refuse honestly instead of storing garbage.
        return None

    if ext in _TEXT_EXTENSIONS or ext not in _BINARY_EXTENSIONS:
        try:
            text = content.decode("utf-8", errors="replace")
            if text.strip():
                return text
        except Exception:
            pass

    if not is_available():
        return None

    try:
        from markitdown import MarkItDown

        converter = MarkItDown()
        result = converter.convert_stream(
            __import__("io").BytesIO(content), file_extension=ext or ".txt"
        )
        text = getattr(result, "text_content", None) or ""
        return text.strip() or None
    except Exception as exc:
        logger.warning("oss_docparse failed for %s: %s", filename, str(exc)[:200])
        return None


def chunk_text(text: str, target: int = 500) -> list:
    """Paragraph-aware chunking, ~target chars, with hard-window fallback.
    Mirrors the upload endpoint's existing logic so behaviour stays familiar."""
    raw_paras = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
    chunks: list = []
    current = ""
    for para in raw_paras:
        if len(current) + len(para) + 2 < target:
            current = (current + "\n\n" + para).strip() if current else para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    if not chunks and (text or "").strip():
        for i in range(0, len(text), target):
            piece = text[i : i + target].strip()
            if piece:
                chunks.append(piece)
    return chunks
